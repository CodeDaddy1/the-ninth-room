# -*- coding: utf-8 -*-
"""Move failing silence-cut edges to the nearest spot that passes the audit.

Why this exists: the splice audit's speech-edge check kept finding voice
hard against the automatic dead-space cuts (49 audible warnings on
`testing`). The first fix attempt snapped edges to the quietest single
INSTANT — and made the count worse (49 -> 51, 2026-08-23): an instant
minimum can sit in the dip between two voice bursts, and the audit measures
a sustained 250ms stretch, not an instant. Optimizing a different metric
than the one that judges you is how a fix fails its own test.

So this module scores candidates with the AUDIT'S OWN ARITHMETIC — same
16kHz mono decode, same 50ms RMS windows, same two-consecutive-hot streak
(audit.py's _edge_hot) — and moves an edge only when:

    1. the edge, where it is, FAILS that check (voice just outside), and
    2. some candidate inside the allowed window PASSES it —

to the nearest passing candidate. An edge that already passes never moves;
an edge that cannot be saved never moves (churn buys nothing measurable).
Snapped-map warnings at these edges therefore only ever decrease.

The direction rule is the content-safety half: an edge may only move INTO
the removed gap, so segments only GROW — audio that survived before cannot
be lost now. Hard cuts (flubs) are out of jurisdiction entirely: growing
across a flub boundary would re-include the flub.

Measurements cache per (file, edge, window) in analysis/trough_cache.json;
footage is immutable, so the second map regeneration costs no ffmpeg.
"""
from __future__ import annotations

import audioop
import json
import math
import subprocess
import tempfile
import wave
from pathlib import Path

SEARCH_SEC = 0.45   # how far an edge may travel into the gap
GUARD_SEC = 0.06    # the removal must survive as a removal
STEP_SEC = 0.01     # candidate spacing

# The audit's own constants (audit.py) — matched, not approximated. If the
# audit's thresholds move, move these with them or the guarantee breaks.
EDGE_WINDOW_SEC = 0.05
EDGE_WITHIN_SEC = 0.25
EDGE_HOT_DB = -36.0
SAMPLE_RATE = 16000


class _EdgeAudio:
    """One decoded stretch of source audio, RMS of any window in O(1).

    Prefix sums of squared samples make an arbitrary [t, t+w] RMS a
    subtraction — the audit's 50ms windows at every 10ms candidate without
    re-decoding.
    """

    def __init__(self, path: str, start: float, dur: float):
        self.start = max(0.0, start)
        self.samples = _decode(path, self.start, dur)
        self.prefix = [0]
        for s in self.samples:
            self.prefix.append(self.prefix[-1] + s * s)

    def rms_db(self, t: float, w: float = EDGE_WINDOW_SEC) -> "float | None":
        i = int(round((t - self.start) * SAMPLE_RATE))
        j = i + int(round(w * SAMPLE_RATE))
        if i < 0 or j > len(self.samples) or j <= i:
            return None
        mean_sq = (self.prefix[j] - self.prefix[i]) / (j - i)
        return 20 * math.log10(max(math.sqrt(mean_sq), 1) / 32768.0)

    def edge_hot(self, t: float, direction: int) -> "float | None":
        """audit._edge_hot, verbatim in spirit: is there a streak of two
        consecutive hot 50ms windows within 250ms just OUTSIDE a cut at t?
        direction +1 probes after t (an out-edge), -1 before (an in-edge).
        Returns the peak dB of the probe when hot, None when the edge passes.
        """
        n = int(EDGE_WITHIN_SEC / EDGE_WINDOW_SEC)
        vals = []
        for k in range(n):
            w_t = t + k * EDGE_WINDOW_SEC if direction > 0 \
                else t - (k + 1) * EDGE_WINDOW_SEC
            db = self.rms_db(w_t)
            if db is None:
                break
            vals.append(db)
        streak = 0
        for db in vals:
            streak = streak + 1 if db > EDGE_HOT_DB else 0
            if streak >= 2:
                return max(vals)
        return None


def _decode(path: str, start: float, dur: float) -> "list[int]":
    with tempfile.TemporaryDirectory() as td:
        wav_p = Path(td) / "edge.wav"
        proc = subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-ss", "%.3f" % start,
             "-t", "%.3f" % dur, "-i", path, "-vn", "-ac", "1",
             "-ar", str(SAMPLE_RATE), str(wav_p)],
            capture_output=True, text=True)
        if proc.returncode != 0 or not wav_p.exists():
            return []
        w = wave.open(str(wav_p))
        data = w.readframes(w.getnframes())
        w.close()
    n = len(data) // 2
    return [audioop.getsample(data, 2, i) for i in range(n)]


# --- the direction rules, pure and tested ----------------------------------

def out_edge_window(edge: float, removal_end: float,
                    search: float = SEARCH_SEC,
                    guard: float = GUARD_SEC) -> "tuple | None":
    """Where a segment's OUT edge (removal start) may search: later only —
    toward the gap's middle. Earlier would remove MORE audio, which is the
    beheading this module exists to stop."""
    hi = min(edge + search, removal_end - guard)
    if hi <= edge:
        return None
    return (edge, hi)


def in_edge_window(edge: float, removal_start: float,
                   search: float = SEARCH_SEC,
                   guard: float = GUARD_SEC) -> "tuple | None":
    """Where the next segment's IN edge (removal end) may search: earlier
    only — the incoming word may start before silencedetect said the gap
    closed; later would clip its first syllable."""
    lo = max(edge - search, removal_start + guard)
    if lo >= edge:
        return None
    return (lo, edge)


def _rescue(edge: float, lo: float, hi: float, direction: int,
            audio: "_EdgeAudio") -> "float | None":
    """The move rule: an edge that PASSES stays; a failing edge moves to the
    NEAREST candidate that passes; a doomed edge stays (churn buys nothing).
    Returns the new position, or None for no move."""
    if audio.edge_hot(edge, direction) is None:
        return None  # already passes — the common case, and free
    # candidates ordered nearest-first so the timeline changes least
    cands = []
    t = lo
    while t <= hi + 1e-9:
        cands.append(round(t, 3))
        t += STEP_SEC
    cands.sort(key=lambda c: abs(c - edge))
    for c in cands:
        if abs(c - edge) < STEP_SEC / 2:
            continue
        if audio.edge_hot(c, direction) is None:
            return c
    return None


def snap_removal(path: str, rs: float, re_: float,
                 cache: "dict", audio_factory=None) -> "tuple":
    """One silence removal (rs, re_) -> its rescued self.

    The OUT edge settles first; the IN edge's floor then respects the moved
    OUT edge, so the removal cannot invert. Results cache by edge+window —
    footage is immutable, so a decided edge is decided forever.
    """
    factory = audio_factory or _EdgeAudio

    def decide(edge: float, lo: float, hi: float, direction: int) -> float:
        key = "%s|%d|%.2f|%.2f|%.2f" % (Path(path).name, direction, edge, lo, hi)
        if key not in cache:
            pad = EDGE_WITHIN_SEC + EDGE_WINDOW_SEC
            audio = factory(path, lo - pad, (hi - lo) + 2 * pad)
            if not getattr(audio, "samples", True):
                # deaf (permissions, missing file): no move is the safe
                # answer, but it is NOT a decision — never cache it, or a
                # sandboxed run poisons every later sighted one (2026-08-23)
                return edge
            cache[key] = _rescue(edge, lo, hi, direction, audio)
        moved = cache[key]
        return edge if moved is None else float(moved)

    new_rs = rs
    w = out_edge_window(rs, re_)
    if w:
        new_rs = decide(rs, w[0], w[1], +1)

    new_re = re_
    w = in_edge_window(re_, new_rs)
    if w:
        new_re = decide(re_, w[0], w[1], -1)

    if new_re - new_rs < GUARD_SEC:  # never let the removal collapse
        return rs, re_
    return new_rs, new_re


def load_cache(analysis_dir: Path) -> "dict":
    p = analysis_dir / "trough_cache.json"
    if p.exists():
        try:
            return json.loads(p.read_text())
        except ValueError:
            return {}
    return {}


def save_cache(analysis_dir: Path, cache: "dict") -> None:
    p = analysis_dir / "trough_cache.json"
    p.write_text(json.dumps(cache))
