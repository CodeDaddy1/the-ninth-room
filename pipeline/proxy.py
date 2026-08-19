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


def beat_spec(beat: "dict", caption_text: str, cards: "list") -> "dict":
    """Everything that shapes this beat's pixels — the cache key."""
    from . import timeline as tl_mod
    return {
        "beat": beat, "caption": caption_text,
        "cards": [{k: c.get(k) for k in ("id", "type", "kit_type", "at", "duration",
                                          "kicker", "text", "stat", "subtext",
                                          "emphasis", "rows", "entries", "animation")}
                  for c in cards],
        "pace": [tl_mod.MAX_KEEP_GAP_SEC, tl_mod.KEEP_PAD_SEC,
                 tl_mod.HEAD_PAD_SEC, tl_mod.TAIL_PAD_SEC],
        "v": 3,  # bump to invalidate every cached proxy after a renderer change
    }


def render_beat(slug: str, beat: "dict", catalog: "dict", caption_text: str,
                cards: "list", out_path: Path, log=print) -> Path:
    work = work_path(slug)
    src = catalog[beat["file"]]["path"]
    rec0 = beat["record_s"]

    # --- inputs -----------------------------------------------------------
    inputs, seg_labels = [], []
    for i, seg in enumerate(beat["segments"]):
        inputs += ["-ss", "%.3f" % seg["src_s"],
                   "-t", "%.3f" % (seg["src_e"] - seg["src_s"]), "-i", src]
        seg_labels.append(i)
    n_seg = len(seg_labels)

    idx = n_seg
    overlay_inputs = []  # (input_idx, kind, start_rel, dur, path)
    for br in beat.get("broll", []):
        bsrc = catalog[br["file"]]["path"]
        inputs += ["-ss", "%.3f" % br.get("src_s", 0.0),
                   "-t", "%.3f" % br["duration"], "-i", bsrc]
        overlay_inputs.append((idx, "broll", br["record_s"] - rec0, br["duration"], bsrc))
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
        fc.append("[%d:v]scale=%d:%d,fps=24,setsar=1[v%d];[%d:a]aformat=sample_rates=48000:"
                  "channel_layouts=stereo[a%d]" % (i, W, H, i, i, i))
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
            "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", str(out_path)])
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise IngestError("proxy %s failed: %s" % (beat["id"], proc.stderr[-300:]))
    return out_path


def build(slug: str, only_beats: "list | None" = None, log=print) -> "dict":
    """Render proxies for all (or named) beats. Returns {beat_id: proxy path}."""
    tl, catalog, caps, cards_by_beat = _load(slug)
    proxy_dir = work_path(slug) / "proxies"
    proxy_dir.mkdir(exist_ok=True)
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
