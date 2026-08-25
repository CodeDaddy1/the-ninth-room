# -*- coding: utf-8 -*-
"""Set aside footage that cannot earn its ingest, before whisper runs.

A shoot arrives with mis-fires in it: a lens-cap take, a half-second
fragment from a fumbled record button, the same clip copied twice off two
cards. Ingest used to transcribe and contact-sheet every one of them —
368 files at ~0.84x real time, and a black clip costs exactly as much as
a good one.

Two rules govern this module, and they are the reason it is safe to run
automatically:

* **It never moves and never deletes.** A screened-out clip stays exactly
  where it is; the catalog entry carries `screened_out` and a reason, and
  ingest skips the EXPENSIVE stages for it. Undoing a wrong call is
  editing one field, not restoring a file.
* **It never judges content.** Nothing here has an opinion about whether
  a shot is good — only whether it is mechanically useless: no video, too
  short to cut, all black, or a byte-identical copy of a file already in
  hand. Judgement about takes happens later, over transcripts, where
  there is something to judge (see takes.take_flags).
"""
from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

MIN_USABLE_S = 1.0     # under the 1.8s cover floor with nothing to trim
BLACK_SAMPLE_S = 6.0   # how much of a clip to sample when looking for black
# blackdetect reports up to the START of the last black frame, so a
# wholly black 3s clip measures 2.917s — a 0.98 ratio never matches. 0.95
# leaves room for the uncounted frame without admitting a real fade.
BLACK_RATIO = 0.95


def content_sig(path: "Path", size: int) -> str:
    """Cheap content signature: sha1 of the first+last MB. Two multi-GB
    camera files agreeing on size AND both ends are the same recording.
    Canonical here because ingest needs it and cannot import editroom
    (editroom imports ingest); editroom delegates to this one."""
    with open(path, "rb") as fh:
        head = fh.read(1 << 20)
        tail = b""
        if size > (1 << 20):
            fh.seek(max(size - (1 << 20), 0))
            tail = fh.read(1 << 20)
    return hashlib.sha1(head + tail).hexdigest()[:16]


def screen_flags(entry: "dict", seen_sigs: "dict") -> "list":
    """PURE. Mechanical reasons this file cannot be cut, from what
    `probe_file` already returned. `seen_sigs` maps a content signature to
    the name that claimed it first — pass the same dict down the loop and
    the second copy of a file names the first.
    """
    flags = []
    if entry.get("kind") != "video" and not entry.get("has_audio"):
        flags.append("no video or audio")
    elif entry.get("kind") == "video" and not entry.get("width"):
        flags.append("no video stream")
    dur = float(entry.get("duration") or 0)
    if 0 < dur < MIN_USABLE_S:
        flags.append("only %.1fs — too short to cut" % dur)
    sig = entry.get("sig")
    if sig:
        first = seen_sigs.get(sig)
        if first and first != entry.get("name"):
            flags.append("identical to %s" % first)
        else:
            seen_sigs.setdefault(sig, entry.get("name"))
    return flags


def is_black(path: "Path", duration: float, sample_s: float = BLACK_SAMPLE_S,
             ratio: float = BLACK_RATIO) -> bool:
    """Is the clip essentially all black? Samples the MIDDLE of the clip —
    fades and lens caps live at the ends, and a clip that is black in the
    middle is black. One decode of a few seconds, never the whole file.
    """
    if duration <= 0:
        return False
    span = min(sample_s, duration)
    start = max(0.0, (duration - span) / 2.0)
    # Decode the camera's 720p proxy when one exists, never the 4K master.
    # Measured 2026-08-24: 3.97s per file against the MP4 — 24 minutes
    # over a 367-file shoot, to find nothing. The same .LRF fast path that
    # made contact sheets 17x faster applies here for the same reason.
    from .broll import _prefer_proxy
    src = _prefer_proxy(path)
    proc = subprocess.run(
        ["ffmpeg", "-nostdin", "-loglevel", "info", "-ss", "%.2f" % start,
         "-t", "%.2f" % span, "-i", str(src),
         "-vf", "blackdetect=d=0.1:pic_th=0.98", "-an", "-f", "null", "-"],
        capture_output=True, text=True)
    black = 0.0
    for line in (proc.stderr or "").splitlines():
        if "black_start" in line:
            for tok in line.split():
                if tok.startswith("black_duration:"):
                    try:
                        black += float(tok.split(":", 1)[1])
                    except ValueError:
                        pass
    return black >= span * ratio


def screen(entry: "dict", seen_sigs: "dict", check_black: bool = True) -> "dict":
    """Return the entry, stamped with `screened_out` + `screen_reason`
    when it cannot be cut. Cheap checks first; the decode only runs on a
    file that has passed everything else."""
    flags = screen_flags(entry, seen_sigs)
    if not flags and check_black and entry.get("kind") == "video":
        try:
            if is_black(Path(entry["path"]), float(entry.get("duration") or 0)):
                flags.append("all black")
        except (OSError, subprocess.SubprocessError):
            pass          # a probe that cannot run is not evidence of black
    if flags:
        out = dict(entry)
        out["screened_out"] = True
        out["screen_reason"] = "; ".join(flags)
        return out
    return entry


def tally(entries: "list") -> "str":
    """One line for the ingest log: how many were set aside, and why."""
    out = [e for e in entries if e.get("screened_out")]
    if not out:
        return "set aside 0 of %d" % len(entries)
    kinds: "dict" = {}
    for e in out:
        head = str(e.get("screen_reason", "")).split(";")[0].split(" —")[0]
        head = "duplicate" if head.startswith("identical to") else head
        kinds[head] = kinds.get(head, 0) + 1
    detail = ", ".join("%d %s" % (n, k) for k, n in
                       sorted(kinds.items(), key=lambda kv: -kv[1]))
    return "set aside %d of %d — %s" % (len(out), len(entries), detail)
