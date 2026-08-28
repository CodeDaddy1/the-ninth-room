"""Snap explicit cut edges to true acoustic silence.

Why: the editor (human or agent) places `cuts[]` spans using whisper word
timings, but whisper stretches words across pauses and mis-times fast speech,
so an edge placed "on a word boundary" can land mid-syllable — exactly the
"ecologi-", "terrib-", doubled-"so much" fragments the QC review caught.
Transcripts guess; the waveform knows.

Method: for each cut edge, scan ±SEARCH_SEC of the source audio at 10ms
resolution (ffmpeg astats RMS per frame) and move the edge to the quietest
point. A cut placed in a trough of actual silence cannot clip a syllable, no
matter what whisper thinks the word spans are.

Run once against the plan: `/usr/bin/python3 -m pipeline.cli snap-cuts <slug>`.
It rewrites edit_plan.json in place (backing up first) and prints every move.

What breaks if this is wrong: edges snap into the wrong trough and eat a
short word — the search window is deliberately small (0.45s) so an edge can
only move to silence near where the editor put it, never to a different
sentence.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess

from .ingest import work_path, analysis_dir

SEARCH_SEC = 0.45
FRAME_SEC = 0.010


def _rms_track(path: str, start: float, dur: float) -> "list[tuple]":
    """(time, rms_db) every FRAME_SEC across [start, start+dur] of the file."""
    proc = subprocess.run(
        ["ffmpeg", "-hide_banner", "-ss", "%.3f" % start, "-t", "%.3f" % dur,
         "-i", path, "-vn", "-af",
         "astats=metadata=1:reset=1:length=%f,ametadata=print:key=lavfi.astats.Overall.RMS_level" % FRAME_SEC,
         "-f", "null", "-"],
        capture_output=True, text=True)
    out = []
    t = start
    for line in proc.stderr.splitlines():
        m = re.search(r"RMS_level=(-?[\d.]+|-inf)", line)
        if m:
            v = -90.0 if m.group(1) == "-inf" else float(m.group(1))
            out.append((t, v))
            t += FRAME_SEC
    return out

def quietest_near(path: str, t: float) -> "tuple":
    """The quietest instant within ±SEARCH_SEC of t. Returns (time, rms_db)."""
    track = _rms_track(path, max(0.0, t - SEARCH_SEC), 2 * SEARCH_SEC)
    if not track:
        return t, 0.0
    return min(track, key=lambda x: x[1])


def snap(slug: str, log=print) -> int:
    work = work_path(slug)
    plan_path = work / "edit_plan.json"
    shutil.copyfile(plan_path, work / "edit_plan_presnap.json")
    plan = json.loads(plan_path.read_text())
    takes = {t["id"]: t for t in json.loads(
        (analysis_dir(slug) / "takes.json").read_text())["takes"]}
    cat = {f["name"]: f for f in json.loads(
        (analysis_dir(slug) / "catalog.json").read_text())["files"]}

    moved = 0
    for b in plan["beats"]:
        cuts = b.get("cuts")
        if not cuts:
            continue
        # A picture beat has no take and no words: there is no speech to
        # snap a cut to, and indexing takes[None] would raise (2026-08-28).
        if not b.get("take_id"):
            continue
        path = cat[takes[b["take_id"]]["file"]]["path"]
        trim = b.get("trim") or {}
        for c in cuts:
            for edge in ("s", "e"):
                t0 = c[edge]
                t1, db = quietest_near(path, t0)
                # keep edges inside the trim so validation holds
                if trim:
                    t1 = min(max(t1, trim.get("s", t1)), trim.get("e", t1))
                if abs(t1 - t0) >= 0.02:
                    log("[snap] %-6s cut %s %8.2f -> %8.2f (%.1f dB)"
                        % (b["id"], edge, t0, t1, db))
                    c[edge] = round(t1, 3)
                    moved += 1
        # a snapped span can invert or collapse; drop degenerates
        b["cuts"] = [c for c in cuts if c["e"] - c["s"] > 0.08]

    plan_path.write_text(json.dumps(plan, indent=2))
    log("[snap] moved %d cut edges" % moved)
    return moved
