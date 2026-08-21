"""Per-beat proxy renders — the unit of iteration for the Edit Room.

The whole point: a note on one shot must never cost a full-video render.
Each beat becomes its own 480p mp4 — the beat's spliced take audio+video,
its b-roll cutaways, its cards and captions composited on top — built by
ffmpeg alone in a few seconds. Resolve renders once, at picture lock.

Caching: a beat's proxy is named by a hash of everything that shaped it
(the beat's plan JSON, its caption text, its cards' specs, the pacing
constants). Change a trim and only that beat re-renders; run it twice and
the second run is free. Stale proxies for a beat are deleted so the
directory always holds exactly one proxy per beat.

Overlays reuse the baked 1080p ProRes clips (graphics/<id>.mov,
captions/<bid>.mov) scaled down in the filter graph — the proxy shows the
REAL overlay, not an approximation. A missing overlay clip becomes a visible
"[overlay not baked]" badge rather than a silent absence.

What breaks if this is wrong: the Edit Room shows a beat that differs from
what Resolve will render, and Caleb approves shots that ship differently —
the one failure mode this system exists to prevent.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path

from .ingest import work_path, analysis_dir, IngestError

W, H = 854, 480
SCALE = W / 1920.0
CRF = 26


def _hash_spec(spec) -> str:
    return hashlib.sha1(json.dumps(spec, sort_keys=True).encode()).hexdigest()[:12]


def _load(slug: str) -> "tuple":
    out = analysis_dir(slug)
    work = work_path(slug)
    tl = json.loads((out / "timeline_map.json").read_text())
    catalog = {f["name"]: f for f in json.loads((out / "catalog.json").read_text())["files"]}
    caps = {}
    cap_path = work / "captions.json"
    if cap_path.exists():
        caps = {c["beat_id"]: c["text"] for c in json.loads(cap_path.read_text())["beats"]}
    cards_by_beat: "dict[str, list]" = {}
    gp_path = work / "graphics_plan.json"
    if gp_path.exists():
        for c in json.loads(gp_path.read_text())["cards"]:
            cards_by_beat.setdefault(c["beat_id"], []).append(c)
    return tl, catalog, caps, cards_by_beat


def _relative_beat(beat: "dict") -> "dict":
    """The beat with all record times rebased to 0.

    A beat's pixels depend only on beat-RELATIVE timing (segments are
    concatenated, overlays are placed at `record - rec0`), so the cache key
    must not include absolute record position — otherwise removing one shot
    invalidates every proxy downstream of it, which is exactly the
    full-re-render loop this cache exists to break.
    """
    import copy
    b = copy.deepcopy(beat)
    r0 = b["record_s"]
    b["record_s"] = 0.0
    b["record_e"] = round(b["record_e"] - r0, 6)
    for seg in b.get("segments", []):
        if "record_s" in seg:
            seg["record_s"] = round(seg["record_s"] - r0, 6)
        if "record_e" in seg:
            seg["record_e"] = round(seg["record_e"] - r0, 6)
    for br in b.get("broll", []):
        if "record_s" in br:
            br["record_s"] = round(br["record_s"] - r0, 6)
    return b


def beat_spec(beat: "dict", caption_text: str, cards: "list") -> "dict":
    """Everything that shapes this beat's pixels — the cache key."""
    from . import timeline as tl_mod
    from . import captions as captions_mod
    from . import animate as animate_mod
    return {
        "beat": _relative_beat(beat), "caption": caption_text,
        "cards": [{k: c.get(k) for k in ("id", "type", "kit_type", "at", "duration",
                                          "kicker", "text", "stat", "subtext",
                                          "emphasis", "rows", "entries", "animation")}
                  for c in cards],
        "pace": [tl_mod.MAX_KEEP_GAP_SEC, tl_mod.KEEP_PAD_SEC,
                 tl_mod.HEAD_PAD_SEC, tl_mod.TAIL_PAD_SEC],
        # The RENDERER versions belong in the key: the Cyanotype restyle
        # changed every caption's and card's pixels while changing no text
        # and no spec, and 74 review proxies sat stale showing the old look
        # (Caleb caught it against Resolve, 2026-08-21). A hand-bumped local
        # "v" cannot catch a style change made in another module.
        "captions_v": captions_mod.CAPTIONS_V,
        "bake_v": animate_mod.BAKE_V,
        "v": 5,  # for proxy-pipeline changes themselves (trim/sync/layout)
    }


def render_beat(slug: str, beat: "dict", catalog: "dict", caption_text: str,
                cards: "list", out_path: Path, log=print) -> Path:
    work = work_path(slug)
    src = catalog[beat["file"]]["path"]
    rec0 = beat["record_s"]
    # ffmpeg writes to a temp name the Edit Room's BT*.mp4 glob can't see,
    # then an atomic rename publishes it — a browser must never fetch a
    # half-encoded proxy (that is exactly how BT103 broke).
    tmp_path = out_path.parent / ("_tmp.%s" % out_path.name)

    # --- inputs -----------------------------------------------------------
    inputs, seg_labels = [], []
    for i, seg in enumerate(beat["segments"]):
        inputs += ["-ss", "%.3f" % seg["src_s"],
                   "-t", "%.3f" % (seg["src_e"] - seg["src_s"]), "-i", src]
        seg_labels.append(i)
    n_seg = len(seg_labels)

    idx = n_seg
    overlay_inputs = []  # (input_idx, kind, start_rel, dur, path)
    beat_len = beat["record_e"] - rec0
    for br in beat.get("broll", []):
        bsrc = catalog[br["file"]]["path"]
        # A b-roll clamped to the beat's end must outlast the base in the
        # filter graph: the concat base rounds UP a frame or two at fps=24
        # while an exactly-trimmed overlay rounds DOWN, so the A-roll flashed
        # through for the final frames (BT94's mammoth, 2026-08-19). Padding
        # the input is safe — overlay ends with the base, extra frames drop.
        # Mid-beat b-roll is NOT padded: it would show longer than it ships.
        at_rel = br["record_s"] - rec0
        pad = 0.3 if at_rel + br["duration"] >= beat_len - 0.05 else 0.0
        inputs += ["-ss", "%.3f" % br.get("src_s", 0.0),
                   "-t", "%.3f" % (br["duration"] + pad), "-i", bsrc]
        overlay_inputs.append((idx, "broll", at_rel, br["duration"], bsrc))
        idx += 1
    missing = []
    cap_mov = work / "captions" / ("%s.mov" % beat["id"])
    if caption_text:
        if cap_mov.exists():
            inputs += ["-i", str(cap_mov)]
            overlay_inputs.append((idx, "alpha", 0.0, beat["record_e"] - rec0, cap_mov))
            idx += 1
        else:
            missing.append("captions")
    for c in cards:
        mov = work / "graphics" / ("%s.mov" % c["id"])
        if mov.exists():
            inputs += ["-i", str(mov)]
            overlay_inputs.append((idx, "alpha", float(c["at"]), float(c["duration"]), mov))
            idx += 1
        else:
            missing.append(c["id"])

    # --- filter graph -----------------------------------------------------
    fc = []
    for i in seg_labels:
        seg = beat["segments"][i]
        seg_dur = seg["src_e"] - seg["src_s"]
        # Trim BOTH streams to the exact segment length before concat. The
        # aac decoder hands back whole packets (a priming packet rides in at
        # negative pts) and the fps filter rounds frames up, so every segment
        # overran by a frame or two and the overruns ACCUMULATE through
        # concat: on six-segment BT101 the tail ran ~0.3s long and "Monopoly"
        # played clipped at the file end (Caleb's round-2 flag). Video trims
        # by frame count (round, not ceil/floor — the error must not
        # accumulate); audio trims to [0, dur) so the negative-pts priming
        # packet is dropped. Measured after the fix: A/V within 4ms.
        n_frames = max(1, int(round(seg_dur * 24)))
        fc.append("[%d:v]scale=%d:%d,fps=24,setsar=1,trim=end_frame=%d,"
                  "setpts=PTS-STARTPTS[v%d];[%d:a]atrim=start=0:end=%.3f,"
                  "asetpts=PTS-STARTPTS,aformat=sample_rates=48000:"
                  "channel_layouts=stereo[a%d]" % (i, W, H, n_frames, i, i, seg_dur, i))
    fc.append("%sconcat=n=%d:v=1:a=1[base][aud]"
              % ("".join("[v%d][a%d]" % (i, i) for i in seg_labels), n_seg))
    cur = "base"
    for j, (k, kind, at, dur, _p) in enumerate(overlay_inputs):
        lbl = "ov%d" % j
        if kind == "broll":
            fc.append("[%d:v]scale=%d:%d,fps=24,setsar=1,setpts=PTS-STARTPTS+%.3f/TB[%s]"
                      % (k, W, H, max(at, 0.0), lbl))
        else:
            fc.append("[%d:v]scale=%d:%d,fps=24,setpts=PTS-STARTPTS+%.3f/TB[%s]"
                      % (k, W, H, max(at, 0.0), lbl))
        nxt = "m%d" % j
        fc.append("[%s][%s]overlay=0:0:eof_action=pass[%s]" % (cur, lbl, nxt))
        cur = nxt
    if missing:
        # a visible badge beats a silent absence
        txt = "overlay not baked: " + ",".join(missing[:3])
        fc.append("[%s]drawbox=x=8:y=8:w=%d:h=26:color=black@0.6:t=fill[%s]"
                  % (cur, min(10 + 7 * len(txt), W - 16), "bdg"))
        cur = "bdg"

    cmd = (["ffmpeg", "-y", "-loglevel", "error"] + inputs +
           ["-filter_complex", ";".join(fc), "-map", "[%s]" % cur, "-map", "[aud]",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", str(CRF),
            "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", str(tmp_path)])
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        if tmp_path.exists():
            tmp_path.unlink()
        raise IngestError("proxy %s failed: %s" % (beat["id"], proc.stderr[-300:]))
    os.replace(tmp_path, out_path)
    return out_path


def build(slug: str, only_beats: "list | None" = None, log=print) -> "dict":
    """Render proxies for all (or named) beats. Returns {beat_id: proxy path}."""
    tl, catalog, caps, cards_by_beat = _load(slug)
    proxy_dir = work_path(slug) / "proxies"
    proxy_dir.mkdir(exist_ok=True)
    for orphan in proxy_dir.glob("_tmp.*.mp4"):  # leftovers from a crashed run
        orphan.unlink()
    result, fresh = {}, 0
    for beat in tl["beats"]:
        bid = beat["id"]
        if only_beats and bid not in only_beats:
            continue
        cards = cards_by_beat.get(bid, [])
        spec = beat_spec(beat, caps.get(bid, ""), cards)
        h = _hash_spec(spec)
        out = proxy_dir / ("%s.%s.mp4" % (bid, h))
        if not out.exists():
            for stale in proxy_dir.glob("%s.*.mp4" % bid):
                stale.unlink()
            render_beat(slug, beat, catalog, caps.get(bid, ""), cards, out, log=log)
            fresh += 1
            log("[proxy] %s rendered (%.1fs)" % (bid, beat["record_e"] - beat["record_s"]))
        result[bid] = str(out)
    log("[proxy] %d beats, %d rendered fresh, %d cached"
        % (len(result), fresh, len(result) - fresh))
    return result
