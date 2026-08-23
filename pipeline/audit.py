"""Splice audit: no whisper word may straddle a segment boundary, and no cut
may land while a voice is still speaking.

Born from the second HMNS QC review: three splices clipped words mid-syllable
("ecologi-", "terrib-", a doubled "so much"), and every one was findable
without listening — a word whose span crosses a segment's in or out point
will be audibly cut. This check runs over the computed timeline map, so it
sees the REAL boundaries (word-snapped trims, silence cuts, explicit cuts)
rather than the plan's nominal ones.

`audit_speech_edges` is the second net (added 2026-08-19): whisper's word
timings themselves can be wrong — it placed the end of "Monopoly." at the
/p/-closure dip INSIDE the word, so the splice audit passed while the cut
still beheaded the word. This check ignores whisper and measures the source
audio directly: if there is sustained voice-level energy just OUTSIDE a kept
region, the cut probably interrupted someone.

Run before every build: `/usr/bin/python3 -m pipeline.cli audit <slug>`.

A flagged boundary is not always wrong — whisper stretches some words far
past their audible end, and cutting away from background chatter is often
intentional — so both checks REPORT; only the splice audit's severe count
affects the exit code.

What breaks if this is skipped: exactly what got the last cut a FAIL.
"""
from __future__ import annotations

import audioop
import json
import math
import subprocess
import tempfile
import wave
from pathlib import Path

from .ingest import analysis_dir, IngestError

# Speech-edge thresholds: 50ms RMS windows; >= 2 consecutive hot windows
# within the first 250ms past the cut means a voice was interrupted.
EDGE_PROBE_SEC = 0.35
EDGE_WINDOW_SEC = 0.05
EDGE_HOT_DB = -36.0
EDGE_WITHIN_SEC = 0.25
# Only peaks this hot are reported. Tuned on the finished HMNS edit: museum
# ambience and background chatter fill -36..-26 dB (54 warnings, all
# deliberate cut-aways), while an interrupted on-mic speaker measures far
# hotter — the clipped "Monopoly." peaked at -14.6 dB.
EDGE_REPORT_DB = -26.0


def _timeline_map(slug: str) -> "dict":
    """The audit measures the COMPUTED layout, so it needs a built timeline.
    A project still at story or footage phase has no map, which is a normal
    state -- say so plainly instead of throwing a FileNotFoundError traceback
    at whoever ran the command (crooise, 2026-08-23)."""
    p = analysis_dir(slug) / "timeline_map.json"
    if not p.exists():
        raise IngestError(
            "%s has no timeline yet -- run `build-timeline %s` first; "
            "the audit measures the built layout, not the plan" % (slug, slug))
    return json.loads(p.read_text())


def audit_splices(slug: str, log=print) -> "list[dict]":
    out = analysis_dir(slug)
    tl = _timeline_map(slug)
    catalog = json.loads((out / "catalog.json").read_text())
    by_name = {f["name"]: f for f in catalog["files"]}
    wcache: "dict[str, list]" = {}

    def words_for(fname: str) -> "list[dict]":
        if fname not in wcache:
            wf = by_name[fname].get("words_file")
            wcache[fname] = (json.loads((out / wf).read_text())
                             if wf and (out / wf).exists() else [])
        return wcache[fname]

    problems = []
    for beat in tl["beats"]:
        words = words_for(beat["file"])
        n = len(beat["segments"])
        for j, seg in enumerate(beat["segments"]):
            for kind, t, edge_ok in (("in", seg["src_s"], j == 0),
                                     ("out", seg["src_e"], j == n - 1)):
                for w in words:
                    if w["s"] < t < w["e"]:
                        frac = (t - w["s"]) / max(w["e"] - w["s"], 0.001)
                        # An out-point deep into a word is usually fine
                        # (whisper stretches tails); early crossings clip.
                        severe = frac < 0.65 if kind == "out" else frac > 0.35
                        problems.append({
                            "beat": beat["id"], "segment": j, "edge": kind,
                            "t": round(t, 3), "word": w["w"],
                            "word_span": (w["s"], w["e"]),
                            "frac": round(frac, 2), "severe": severe,
                        })
    severe = [p for p in problems if p["severe"]]
    for p in problems:
        log("[audit] %-6s seg%d %-3s %8.2fs cuts %r at %d%%%s"
            % (p["beat"], p["segment"], p["edge"], p["t"], p["word"],
               p["frac"] * 100, "  <-- SEVERE" if p["severe"] else ""))
    log("[audit] %d boundary crossings, %d severe" % (len(problems), len(severe)))
    return problems


def _rms_windows(path: str, start: float, dur: float) -> "list[float]":
    """dB RMS per 50ms window of source audio, measured from the file."""
    with tempfile.TemporaryDirectory() as td:
        wav = Path(td) / "edge.wav"
        proc = subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-ss", "%.3f" % max(start, 0.0),
             "-t", "%.3f" % dur, "-i", path, "-vn", "-ac", "1", "-ar", "16000",
             str(wav)], capture_output=True, text=True)
        if proc.returncode != 0 or not wav.exists():
            return []
        w = wave.open(str(wav))
        data = w.readframes(w.getnframes())
        w.close()
    win = int(16000 * EDGE_WINDOW_SEC) * 2
    out = []
    for i in range(0, len(data), win):
        chunk = data[i:i + win]
        if len(chunk) < 640:
            break
        r = audioop.rms(chunk, 2)
        out.append(20 * math.log10(max(r, 1) / 32768.0))
    return out


def _edge_hot(path: str, t: float, direction: int) -> "float | None":
    """Is there sustained voice just outside the cut at source-time t?

    direction +1 probes AFTER t (an out-edge), -1 probes BEFORE t (an
    in-edge). Returns the peak dB of the offending stretch, or None.
    """
    start = t if direction > 0 else max(t - EDGE_PROBE_SEC, 0.0)
    vals = _rms_windows(path, start, EDGE_PROBE_SEC)
    if direction < 0:
        vals = list(reversed(vals))  # walk outward from the cut either way
    near = int(EDGE_WITHIN_SEC / EDGE_WINDOW_SEC)
    streak = 0
    for db in vals[:near]:
        streak = streak + 1 if db > EDGE_HOT_DB else 0
        if streak >= 2:
            return max(vals[:near])
    return None


def audit_speech_edges(slug: str, log=print) -> "list[dict]":
    """Flag cut edges with measured voice energy just outside the kept audio."""
    out = analysis_dir(slug)
    tl = _timeline_map(slug)
    catalog = json.loads((out / "catalog.json").read_text())
    path_by_name = {f["name"]: f["path"] for f in catalog["files"]}

    flags = []
    for beat in tl["beats"]:
        path = path_by_name[beat["file"]]
        segs = beat["segments"]
        for j, seg in enumerate(segs):
            edges = []
            if j == len(segs) - 1:
                edges.append(("end", seg["src_e"], +1))
            else:
                edges.append(("cut-out", seg["src_e"], +1))
            if j > 0:
                edges.append(("cut-in", seg["src_s"], -1))
            for kind, t, direction in edges:
                peak = _edge_hot(path, t, direction)
                if peak is not None:
                    flags.append({"beat": beat["id"], "kind": kind,
                                  "t": round(t, 3), "peak_db": round(peak, 1)})
    quiet = [f for f in flags if f["peak_db"] < EDGE_REPORT_DB]
    flags = sorted((f for f in flags if f["peak_db"] >= EDGE_REPORT_DB),
                   key=lambda f: -f["peak_db"])
    for f in flags:
        log("[audit] %-6s %-7s %8.2fs voice at %.1f dB just outside the cut"
            % (f["beat"], f["kind"], f["t"], f["peak_db"]))
    log("[audit] %d speech-edge warnings (%d quieter than %.0f dB suppressed)"
        % (len(flags), len(quiet), EDGE_REPORT_DB))
    return flags
