"""Phase 3 — b-roll catalog: give every non-speech clip an id and a contact
sheet the agents can SEE.

Claude Code subagents can read images, so a 3x3 grid of frames per clip is
how the story-designer "watches" b-roll without watching video. The sheet
plus duration is enough to decide "this is the dinosaur hall wide shot, use
it under beat 2." The agent writes its descriptions/tags into broll.json's
`description` field later (Phase 4 pre-work) — Python leaves it empty.

What breaks if this is wrong: the agent places b-roll blind (missing/black
frames on the sheet) or references clips that don't exist (bad ids).
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from PIL import Image

from .ingest import analysis_dir, IngestError, _write_atomic

import threading

from .ingest import work_path

TILE_W, TILE_H = 480, 270  # 16:9 tiles; portrait sources letterbox inside


# --- the manual sidecar ----------------------------------------------------
#
# Caleb's tags, and the takes he has admitted as picture. A SIDECAR for the
# same reason `footage_sources.json` is one (CLAUDE.md): ingest owns
# catalog.json and rebuilds it from probe on every run, and build_catalog
# rebuilds broll.json from that — so anything written into either is erased
# by the next analyze. A promoted take erased that way would take its B-id
# with it, and every cover in the cut referencing that id by name would
# silently point at nothing.
#
# Keyed by FILENAME, not by clip id: a file that has never been catalogued
# has no id yet, and the filename is the one name that survives both
# rebuilds. Absent, unreadable and half-written all mean "nothing manual
# here", which is the same bargain read_sources makes.
#
# The Footage desk's TRIMS are the same bargain again, in `facts`'
# `footage_trims.json` — read here through `takes.trim_window` and carried
# onto each clip as `trim`. They are not stored in this file only because
# the Footage desk writes them before a clip is ever catalogued as b-roll.

_MANUAL_LOCK = threading.Lock()


def _manual_path(slug: str) -> Path:
    return work_path(slug) / "broll_manual.json"


def read_manual(slug: str) -> "dict":
    """`{"tags": {filename: [str]}, "promoted": [filename]}` — always both
    keys, always the right types, whatever is on disk."""
    empty = {"tags": {}, "promoted": []}
    p = _manual_path(slug)
    if not p.exists():
        return empty
    try:
        data = json.loads(p.read_text())
    except (ValueError, OSError):
        return empty
    if not isinstance(data, dict):
        return empty
    tags = data.get("tags")
    promoted = data.get("promoted")
    return {
        "tags": {k: [str(t) for t in v]
                 for k, v in (tags or {}).items()
                 if isinstance(v, list)} if isinstance(tags, dict) else {},
        "promoted": [str(x) for x in promoted] if isinstance(promoted, list) else [],
    }


def _write_manual(slug: str, data: "dict") -> None:
    p = _manual_path(slug)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".%d.tmp" % threading.get_ident())
    try:
        tmp.write_text(json.dumps(data, indent=2))
        tmp.replace(p)
    except BaseException:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise


def set_tags(slug: str, name: str, tags) -> "list":
    """Caleb's keywords for one file. Replaces his list, never the
    agent's — the two are kept apart so a hand-typed tag is not lost to the
    next description pass and an agent tag is not lost to a typo here."""
    clean, seen = [], set()
    for t in (tags or []):
        t = str(t).strip().lower()
        if t and t not in seen:
            seen.add(t)
            clean.append(t)
    with _MANUAL_LOCK:
        data = read_manual(slug)
        if clean:
            data["tags"][name] = clean
        else:
            data["tags"].pop(name, None)
        _write_manual(slug, data)
    return clean


def promote(slug: str, name: str, on: bool = True) -> bool:
    """Admit a file into the b-roll catalog that its class would exclude —
    a spoken take, or one the story cut.

    It plays SILENT and nothing had to be done to make that true: the
    timeline writes every cover as an FCPXML `<video>` element on lane 2,
    not an `<asset-clip>`, so a cover contributes picture and never audio.
    That was built to stop museum crowd noise leaking over the narration
    and it is exactly what "removing the audio makes it b-roll" means here.

    Being cut from the story is left alone: the kill list is the
    designer's judgement about what to SAY, and this is about what to
    SHOW. A take can be both cut and useful.
    """
    with _MANUAL_LOCK:
        data = read_manual(slug)
        has = name in data["promoted"]
        if on and not has:
            data["promoted"].append(name)
        elif not on and has:
            data["promoted"] = [x for x in data["promoted"] if x != name]
        else:
            return has
        _write_manual(slug, data)
    return on

GRID = 3  # 3x3 = 9 frames per sheet


def _union_tags(agent, manual) -> "list":
    """Both lists, in agent-then-manual order, without duplicates."""
    out, seen = [], set()
    for t in list(agent or []) + list(manual or []):
        t = str(t)
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


def _prefer_proxy(src: Path) -> Path:
    """Use a DJI .LRF low-res proxy for frame grabs when one sits next to the
    real file — decoding 720p H.264 beats decoding 4K HEVC ~10x. The sheet is
    only 480px tiles, so proxy quality is plenty."""
    real = src.resolve()
    for suffix in (".LRF", ".lrf"):
        proxy = real.with_suffix(suffix)
        if proxy.exists() and proxy.stat().st_size > 100_000:
            return proxy
    return real


def contact_sheet(src: Path, duration: float, dest: Path, tmp_dir: Path,
                  in_s: float = 0.0, out_s: "float | None" = None) -> None:
    """Grab GRID*GRID evenly spaced frames and paste them into one jpg.

    Sampled across the clip's USABLE window when Caleb has trimmed it on
    the Footage desk (2026-08-28). The agents choose and tag shots by
    reading these sheets, so a sheet spread over the whole file offers nine
    frames of which several are from the walk-up the trim exists to
    exclude — and a shot chosen there cannot be cut. Defaults sample the
    whole file, which is what an untrimmed clip is.
    """
    src = _prefer_proxy(src)
    n = GRID * GRID
    lo = max(0.0, float(in_s))
    hi = float(duration if out_s is None else out_s)
    if not (lo < hi < float("inf")):
        # a window we cannot sample is not a window; show the whole clip.
        # `not (...)` rather than `>=` so an unbounded or NaN edge lands
        # here too, instead of asking ffmpeg to seek to infinity.
        lo, hi = 0.0, float(duration)
    span = hi - lo
    tmp_dir.mkdir(parents=True, exist_ok=True)
    frames = []
    for i in range(n):
        # Sample the middle of each of n equal slices: avoids the black/blurry
        # first frame and the tail ramp.
        t = lo + span * (i + 0.5) / n
        frame = tmp_dir / ("f%02d.jpg" % i)
        proc = subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-ss", "%.3f" % t,
             "-i", str(src), "-frames:v", "1",
             "-vf", "scale=%d:%d:force_original_aspect_ratio=decrease" % (TILE_W, TILE_H),
             str(frame)],
            capture_output=True, text=True)
        if proc.returncode == 0 and frame.exists():
            frames.append(frame)
    if not frames:
        raise IngestError("no frames extracted from %s" % src.name)

    sheet = Image.new("RGB", (TILE_W * GRID, TILE_H * GRID), (14, 27, 44))
    for i, frame in enumerate(frames):
        img = Image.open(frame)
        x = (i % GRID) * TILE_W + (TILE_W - img.width) // 2
        y = (i // GRID) * TILE_H + (TILE_H - img.height) // 2
        sheet.paste(img, (x, y))
    sheet.save(dest, quality=82)
    for frame in frames:
        frame.unlink()


def catalog_broll(slug: str, log=print) -> Path:
    """Read catalog.json, write analysis/broll.json + analysis/sheets/*.jpg."""
    out = analysis_dir(slug)
    catalog_path = out / "catalog.json"
    if not catalog_path.exists():
        raise IngestError("no catalog.json — run ingest first")
    catalog = json.loads(catalog_path.read_text())

    sheets_dir = out / "sheets"
    sheets_dir.mkdir(exist_ok=True)
    tmp_dir = out / "tmp_frames"

    from .ingest import write_progress
    # PROMOTED files join the catalog whatever their class says. A spoken
    # take Caleb has admitted as picture is b-roll for every purpose that
    # matters downstream, and the timeline already plays a cover silent.
    # Read before the loop so a re-analyze cannot drop one — dropping it
    # would take its B-id with it, and covers reference ids by name.
    manual = read_manual(slug)
    promoted = set(manual["promoted"])
    # The Footage desk's trims ride a SIDECAR for the same reason the tags
    # and promotions above do, and NOT the merge-from-previous mechanism
    # `description` uses: a trim is Caleb's, so it must survive a rebuild
    # that has never seen it, not merely survive being copied forward from
    # the last broll.json. Read through takes.py's one door.
    from .takes import file_trims, trim_window
    trims = file_trims(slug)
    todo = [f for f in catalog["files"]
            if f.get("kind") == "video" and not f.get("screened_out")
            and (f.get("class") == "broll" or f.get("name") in promoted)]
    # MERGE, never rebuild (2026-08-25). Two things were being destroyed
    # by every re-catalog, and both are load-bearing:
    #
    #  * the DESCRIPTIONS. Python writes "" and the story-designer fills
    #    them as pre-work; a rebuild wiped all 186 of them, which is the
    #    exact text the coverage editor reads to justify every cover.
    #  * the IDS. They were positional — B%03d of len(clips)+1 — so
    #    removing or screening out any earlier clip renumbered every clip
    #    after it, while 60 covers in the cut reference those ids BY NAME.
    #    They would have silently pointed at different footage.
    #
    # So a file keeps whatever id and description it already had, and only
    # genuinely new files are given fresh ids after the highest in use.
    prev = {}
    out_path = out / "broll.json"
    if out_path.exists():
        try:
            for c in json.loads(out_path.read_text()).get("clips", []):
                if c.get("file"):
                    prev[c["file"]] = c
        except ValueError:
            prev = {}
    next_n = 0
    for c in prev.values():
        try:
            next_n = max(next_n, int(str(c.get("id", "B0"))[1:]))
        except ValueError:
            continue
    import time as _time
    t0 = _time.time()
    clips = []
    for f in todo:
        n = len(clips)
        elapsed = _time.time() - t0
        eta = elapsed / n * (len(todo) - n) if n else None
        write_progress(slug, stage="broll", done=n, total=len(todo),
                       current=f["name"], pct=(n / len(todo)) if todo else 1,
                       eta_s=round(eta) if eta else None)
        was = prev.get(f["name"])
        if was:
            cid = was.get("id") or "B%03d" % (next_n + 1)
        else:
            next_n += 1
            cid = "B%03d" % next_n
        t_in, t_out = trim_window(trims, f["name"], f["duration"])
        # Recorded only when the window is real and leaves something: a
        # junk sidecar entry must not be able to fail validation and stop
        # the analysis (ingest.py:131-143). Absent means the whole clip is
        # usable, which is what most clips are.
        trim = ({"in": round(t_in, 3), "out": round(t_out, 3)}
                if f["name"] in trims and t_in < t_out < float("inf") else None)
        sheet_name = f["name"] + ".sheet.jpg"
        sheet_path = sheets_dir / sheet_name
        # cached across reruns, like transcriptions. A trim written on the
        # desk drops the stale sheet at that moment (editroom
        # `_set_footage_trim`), so what lands here is sampled across the
        # window that is current.
        if not sheet_path.exists():
            contact_sheet(Path(f["path"]), f["duration"], sheet_path, tmp_dir,
                          in_s=t_in, out_s=t_out)
        clips.append({
            "id": cid,
            "file": f["name"],
            "duration": f["duration"],
            "width": f.get("width"),
            "height": f.get("height"),
            # the clip's OWN rate: this shoot is 363 files at 23.976,
            # three at 24.0, one at 25.0 and one at 29.97, and a frame
            # picker using the project's rate would miscount five of them
            "fps": f.get("fps"),
            "sheet": "sheets/" + sheet_name,
            # kept across re-analysis; "" only for a file never seen before
            "description": (was or {}).get("description", ""),
            # The agent's tags and Caleb's are kept APART and unioned for
            # anyone filtering. Merging them into one list would mean the
            # next description pass could silently drop a hand-typed
            # keyword, and a typo here could drop the agent's.
            "tags": _union_tags((was or {}).get("tags", []),
                                manual["tags"].get(f["name"], [])),
            "manual_tags": manual["tags"].get(f["name"], []),
            # what this clip is doing here, when its class would exclude it
            "promoted": f["name"] in promoted,
            "from_class": f.get("class"),
        })
        if trim:
            # BESIDE `duration`, never instead of it. `duration` stays the
            # length of the media on disk, because it is the source-time
            # bound `_clamp_cover` and `_validate_spine` measure every
            # `src_s` against, and every plan ever built states its covers
            # in that clock. Redefining it would silently reinterpret all
            # of them. The trim is additive: which part of that clock is
            # usable.
            clips[-1]["trim"] = trim
        log("[broll] %s %s %.1fs%s -> %s"
            % (cid, f["name"], f["duration"],
               (" trim %.1f-%.1fs" % (trim["in"], trim["out"])) if trim else "",
               sheet_name))

    if tmp_dir.exists():
        try:
            tmp_dir.rmdir()
        except OSError:
            pass

    data = {"slug": slug, "clips": clips}
    from . import schemas
    errors = schemas.validate_broll(data)
    if errors:
        raise IngestError("broll.json failed validation:\n  " + "\n  ".join(errors))
    path = out / "broll.json"
    # Atomic: a half-written broll.json is a parse error for every reader,
    # and this is written at the end of a long job that can be killed
    # (2026-08-27). Same rule as the catalog and the sidecars.
    _write_atomic(path, data)
    write_progress(slug, stage="done", done=len(todo), total=len(todo),
                   pct=1.0, eta_s=0)
    log("[broll] wrote %s (%d clips)" % (path, len(clips)))
    return path
