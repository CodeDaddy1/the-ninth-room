"""Phase 5 — captions: word-pop caption clips with alpha, timed by whisper.

The rule (learned in v1, docs/reference-renderers/_build_synced.py): caption
TEXT comes from a human-readable script — here, the caption-editor agent's
cleaned lines in captions.json — because Whisper mishears; caption TIMING
comes from Whisper's word timestamps, aligned to the cleaned text with
difflib (equal blocks anchor, everything else interpolates linearly).

Output: one ProRes 4444 alpha .mov per beat (word-pop chips over a
transparent canvas), placed on V4 by the timeline builder. Text is rendered
by Pillow — this Mac's ffmpeg has no drawtext.

What breaks if this is wrong: captions drift off the voice (bad alignment),
sit inside the platform UI safe zones (bad anchor), or the whole clip renders
transparent (the -loop 1 bake bug — see graphics.py).
"""
from __future__ import annotations

import difflib
import os
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .ingest import IngestError

CREAM = (244, 239, 230)
NAVY_CHIP = (14, 27, 44, 190)

# Caption baseline sits above the platform UI safe zone (bottom caption bar,
# right-side action buttons) — the y values proven in the v1 renders.
CHIP_ANCHOR_Y = {"portrait": 1290, "landscape": 830}
CHIP_FONT_SIZE = {"portrait": 110, "landscape": 84}


def _font(size: int):
    """Brand body is a humanist sans; Avenir Next ships with macOS. Arial
    Bold is the proven fallback."""
    candidates = [
        ("/System/Library/Fonts/Avenir Next.ttc", 2),  # index 2 ≈ Bold face
        ("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 0),
        ("/System/Library/Fonts/Helvetica.ttc", 0),
    ]
    for path, index in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size, index=index)
            except OSError:
                continue
    return ImageFont.load_default()


def _norm(s: str) -> str:
    return "".join(c for c in s.lower() if c.isalnum())


# --- alignment ------------------------------------------------------------

def align_words(display_text: str, whisper_words: "list[dict]") -> "list[dict]":
    """Time each display word off the whisper stream.

    Returns [{"disp": "Hoover", "t": 12.44}, ...] with t in the same timebase
    as the whisper words (source-file seconds). difflib equal blocks copy
    times across; unmatched display words interpolate between the nearest
    anchors, so a mis-heard word still pops at roughly the right moment.
    """
    disp = [tok.strip(".,—") for tok in display_text.replace("—", " ").split()
            if _norm(tok)]
    S = [_norm(d) for d in disp]
    T = [_norm(w["w"]) for w in whisper_words]
    Tt = [w["s"] for w in whisper_words]
    times: "list" = [None] * len(S)
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, S, T, autojunk=False).get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                times[i1 + k] = Tt[j1 + k]
    known = [(i, t) for i, t in enumerate(times) if t is not None]
    if not known:
        raise IngestError("caption text shares no words with the transcript: %r"
                          % display_text[:60])
    for idx in range(len(times)):
        if times[idx] is None:
            prev = [k for k in known if k[0] < idx]
            nxt = [k for k in known if k[0] > idx]
            if prev and nxt:
                (pi, pt), (ni, nt) = prev[-1], nxt[0]
                times[idx] = pt + (nt - pt) * ((idx - pi) / (ni - pi))
            elif prev:
                times[idx] = prev[-1][1]
            else:
                times[idx] = nxt[0][1]
    out = [{"disp": d, "t": round(float(t), 3)} for d, t in zip(disp, times)]
    out.sort(key=lambda x: x["t"])
    return out


# --- rendering ------------------------------------------------------------

def word_chip(word: str, dest: Path, w: int, h: int, orientation: str) -> None:
    """One big word on a rounded navy chip, centered, safe-zone anchored."""
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    fo = _font(CHIP_FONT_SIZE[orientation])
    bb = d.textbbox((0, 0), word, font=fo)
    tw = bb[2] - bb[0]
    x = (w - tw) / 2 - bb[0]
    y = CHIP_ANCHOR_Y[orientation]
    pad = 40
    d.rounded_rectangle(
        [x + bb[0] - pad, y - pad, x + bb[0] + tw + pad, y + (bb[3] - bb[1]) + pad + 16],
        radius=32, fill=NAVY_CHIP)
    d.text((x, y - bb[1]), word, font=fo, fill=CREAM)
    img.save(dest)


def bake_caption_clip(timed_words: "list[dict]", duration: float, out_mov: Path,
                      w: int, h: int, orientation: str, tmp_dir: Path,
                      fps: int = 30) -> None:
    """Bake one beat's word-pop caption track as a transparent ProRes clip.

    timed_words: [{"disp","t"}] with t RELATIVE to the clip start (the caller
    retimes source seconds to beat-local seconds). Each word shows from its t
    until the next word's t (last word holds to the end).
    """
    if not timed_words:
        raise IngestError("bake_caption_clip: no words")
    tmp_dir.mkdir(parents=True, exist_ok=True)
    inputs = ["-f", "lavfi", "-i",
              "color=c=black@0.0:s=%dx%d:r=%d:d=%.3f,format=rgba" % (w, h, fps, duration)]
    chains = []
    prev = "[0:v]"
    for i, tw_ in enumerate(timed_words):
        png = tmp_dir / ("cap_%03d.png" % i)
        word_chip(tw_["disp"], png, w, h, orientation)
        inputs += ["-loop", "1", "-t", "%.3f" % duration, "-r", str(fps), "-i", str(png)]
        s = max(0.0, min(tw_["t"], duration - 0.05))
        e = timed_words[i + 1]["t"] if i + 1 < len(timed_words) else duration
        e = max(s + 0.05, min(e, duration))
        chains.append("%s[%d:v]overlay=0:0:format=auto:enable='between(t,%.3f,%.3f)'[v%d]"
                      % (prev, i + 1, s, e, i))
        prev = "[v%d]" % i
    cmd = (["ffmpeg", "-y", "-loglevel", "error"] + inputs +
           ["-filter_complex", ";".join(chains), "-map", prev,
            "-t", "%.3f" % duration,
            "-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le",
            str(out_mov)])
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise IngestError("caption bake failed: %s" % proc.stderr[-300:])
