"""Frame QC: the rendered master must show what the approved proxies show.

Born 2026-08-19: a unit bug placed every caption overlay at ~80% of its
length, so the final phrase of each beat (and every caption emoji) was
missing from the master — while the per-beat proxies Caleb had approved in
the Edit Room were perfect. Only a lucky manual spot-check caught it. The
proxies ARE the approved picture, so this check samples frames from both and
compares them mechanically.

Method: per beat, two probe offsets (45% and 85% of the beat — tails are
where truncation bugs live). Master frame and proxy frame are reduced to
480x270 grayscale and mean/std-normalized (the master is color graded, the
proxy is not; normalization makes the comparison structural, not tonal).
Score = mean absolute difference of the normalized images, for the full
frame and for the bottom band (captions live there). A beat whose worst
probe exceeds the threshold is flagged.

Thresholds were calibrated on real ground truth: the verified-good master
hmns_173404 (all beats must pass) vs the known-bad hmns_163434 with the
truncated captions (the broken beats must flag).

This check REPORTS; it never blocks — legitimate re-edits after a re-proxy
also diff, and the human decides.
"""
from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

from .ingest import work_path, analysis_dir, IngestError

PROBE_FRACS = (0.45, 0.85, 0.95)   # 0.95 catches tail truncation (BT05 class)
SIZE = (480, 270)
BAND_FRAC = 0.25          # bottom band height (captions)
# The master is probed at small time offsets around each sample and the best
# match wins: seek rounding and mid-word caption pops otherwise flag healthy
# beats. A missing overlay has no matching neighbor frame, so real breakage
# survives the jitter.
JITTER = (-0.083, -0.042, 0.0, 0.042, 0.083)
# Calibrated 2026-08-19 against the good/bad HMNS masters: the good master's
# worst beat scored band 0.200 / full 0.247; the truncated-caption master's
# broken beats scored band 0.269-0.421. Thresholds sit in the gap.
FULL_THRESHOLD = 0.32
BAND_THRESHOLD = 0.235


def _frames(path: str, at: float, n: int = 1) -> "list[np.ndarray]":
    """n consecutive frames starting at `at`, already 480x270 grayscale.

    One ffmpeg call per probe: the 5-frame jitter window is just 5
    consecutive frames at 23.976fps, so decoding them in one pass (with the
    scale done in-filter) is ~5x cheaper than seeking per frame.
    """
    with tempfile.TemporaryDirectory() as td:
        proc = subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-ss", "%.3f" % max(at, 0.0),
             "-i", path, "-frames:v", str(n),
             "-vf", "scale=%d:%d,format=gray" % SIZE,
             str(Path(td) / "f%03d.png")],
            capture_output=True, text=True)
        if proc.returncode != 0:
            return []
        out = []
        for p in sorted(Path(td).glob("f*.png")):
            out.append(np.asarray(Image.open(p), dtype=np.float64))
    return out


def _norm(a: "np.ndarray") -> "np.ndarray":
    return (a - a.mean()) / (a.std() + 1e-6)


def _score(m: "np.ndarray", p: "np.ndarray") -> "tuple[float, float]":
    """(full-frame, bottom-band) mean absolute difference, normalized."""
    d = np.abs(_norm(m) - _norm(p))
    band = int(SIZE[1] * (1 - BAND_FRAC))
    return float(d.mean()), float(d[band:, :].mean())


def _in_zoom_segment(beat: "dict", off: float) -> bool:
    """Zoom punches are applied by Resolve on the master but not baked into
    the proxy, so punched segments differ structurally even when correct —
    probes inside them are skipped."""
    for seg in beat["segments"]:
        if not seg.get("zoom"):
            continue
        s = seg["record_s"] - beat["record_s"]
        if s <= off <= s + (seg["src_e"] - seg["src_s"]):
            return True
    return False


def _probe(master: str, proxy: str, beat: "dict",
           frac: float) -> "tuple[float, float, float] | None":
    dur = beat["record_e"] - beat["record_s"]
    off = min(dur * frac, dur - 0.1)
    if off <= 0 or _in_zoom_segment(beat, off):
        return None
    ps = _frames(proxy, off, 1)
    if not ps:
        return None
    p = ps[0]
    best = None
    for m in _frames(master, beat["record_s"] + off + JITTER[0], len(JITTER)):
        full, band = _score(m, p)
        if best is None or band < best[1]:
            best = (full, band, off)
    return best


def compare(slug: str, master: "Path | str", log=print,
            thresholds: "tuple[float, float] | None" = None) -> "list[dict]":
    """Score every beat's master frames against its proxy. Returns flags."""
    master = str(master)
    tl = json.loads((analysis_dir(slug) / "timeline_map.json").read_text())
    pdir = work_path(slug) / "proxies"
    full_t, band_t = thresholds or (FULL_THRESHOLD, BAND_THRESHOLD)
    if full_t is None:
        raise IngestError("qc_frames thresholds are not calibrated")

    flags, scored = [], 0
    for beat in tl["beats"]:
        proxies = sorted(pdir.glob(beat["id"] + ".*.mp4"))
        if not proxies:
            continue
        proxy = str(proxies[-1])
        worst = (0.0, 0.0, 0.0)
        for frac in PROBE_FRACS:
            best = _probe(master, proxy, beat, frac)
            if best is None:
                continue
            scored += 1
            if best[1] > worst[1]:
                worst = best
        if worst[0] > full_t or worst[1] > band_t:
            flags.append({"beat": beat["id"], "full": round(worst[0], 3),
                          "band": round(worst[1], 3), "at": round(worst[2], 2)})
    for f in flags:
        log("[qcframes] %-6s differs from its approved proxy "
            "(full %.2f band %.2f at +%.1fs)" % (f["beat"], f["full"],
                                                 f["band"], f["at"]))
    log("[qcframes] %d frames scored, %d beats flagged" % (scored, len(flags)))
    return flags


def scores(slug: str, master: "Path | str", log=print) -> "list[dict]":
    """Raw per-beat worst scores — used to calibrate the thresholds."""
    master = str(master)
    tl = json.loads((analysis_dir(slug) / "timeline_map.json").read_text())
    pdir = work_path(slug) / "proxies"
    rows = []
    for beat in tl["beats"]:
        proxies = sorted(pdir.glob(beat["id"] + ".*.mp4"))
        if not proxies:
            continue
        proxy = str(proxies[-1])
        worst_full = worst_band = 0.0
        for frac in PROBE_FRACS:
            best = _probe(master, proxy, beat, frac)
            if best is None:
                continue
            worst_full = max(worst_full, best[0])
            worst_band = max(worst_band, best[1])
        rows.append({"beat": beat["id"], "full": round(worst_full, 3),
                     "band": round(worst_band, 3)})
    return rows
