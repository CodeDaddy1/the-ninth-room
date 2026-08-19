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

CREAM = (252, 252, 250)   # kit --text
AMBER = (18, 183, 106)    # kit accent (green); name kept for call sites
NAVY_CHIP = (9, 9, 11, 210)  # kit ink plate

# Caption baseline sits above the platform UI safe zone (bottom caption bar,
# right-side action buttons) — the y values proven in the v1 renders.
CHIP_ANCHOR_Y = {"portrait": 1290, "landscape": 830}
CHIP_FONT_SIZE = {"portrait": 110, "landscape": 84}

# --- phrase captions (the YouTube-grade style) ---------------------------
# A single word in a box reads as a 2010s subtitle. What modern short-form
# uses instead: a short PHRASE held on screen with the word being spoken
# highlighted, set in heavy type with an outline and a soft shadow so it
# survives any background without a box.
PHRASE_MAX_WORDS = 4
PHRASE_MAX_CHARS = 26
PHRASE_GAP_SEC = 0.9          # a pause this long always starts a new phrase
PHRASE_FONT_SIZE = {"portrait": 96, "landscape": 78}
PHRASE_BASELINE = {"portrait": 1330, "landscape": 858}   # top of the text block
PHRASE_LINE_GAP = 12
STROKE_PX = {"portrait": 9, "landscape": 7}
SHADOW_OFFSET = 6
POP_SCALE = 1.06              # the active word is drawn slightly larger


def _font(size: int, heavy: bool = True):
    """Brand body face. Avenir Next Heavy (index 8) is the punchy weight that
    holds up over busy footage; Bold and Arial Bold are the fallbacks."""
    candidates = [
        (str(Path.home() / "Library/Fonts/Gabarito-Variable.ttf"), 0),
        ("/System/Library/Fonts/Avenir Next.ttc", 8 if heavy else 0),
        ("/System/Library/Fonts/Avenir Next.ttc", 0),
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


def group_phrases(timed_words: "list[dict]") -> "list[list[dict]]":
    """Chunk timed words into short phrases: break on a long pause, on
    sentence-ending punctuation, or when the line gets too long to read."""
    phrases: "list[list[dict]]" = []
    cur: "list[dict]" = []
    for i, w in enumerate(timed_words):
        if cur:
            prev = cur[-1]
            too_long = (len(cur) >= PHRASE_MAX_WORDS or
                        sum(len(x["disp"]) + 1 for x in cur) + len(w["disp"]) > PHRASE_MAX_CHARS)
            paused = w["t"] - prev["t"] >= PHRASE_GAP_SEC
            ended = prev["disp"].rstrip().endswith((".", "!", "?", ","))
            if too_long or paused or ended:
                phrases.append(cur)
                cur = []
        cur.append(w)
    if cur:
        phrases.append(cur)
    return phrases


def phrase_png(words: "list[str]", active: int, dest: Path, w: int, h: int,
               orientation: str) -> None:
    """Render one phrase with `active` highlighted in amber.

    Heavy type, dark stroke and a soft drop shadow — legible over bright
    foliage or dark cave walls without a box behind it.
    """
    size = PHRASE_FONT_SIZE[orientation]
    stroke = STROKE_PX[orientation]
    base_font = _font(size)
    pop_font = _font(int(size * POP_SCALE))

    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # Lay the words out on one line, measuring with each word's own font so
    # the popped word doesn't overlap its neighbours.
    space = d.textlength(" ", font=base_font)
    widths = []
    for i, word in enumerate(words):
        f = pop_font if i == active else base_font
        widths.append(d.textlength(word, font=f))
    total = sum(widths) + space * (len(words) - 1)
    x = (w - total) / 2
    y = PHRASE_BASELINE[orientation]

    for i, word in enumerate(words):
        f = pop_font if i == active else base_font
        color = AMBER if i == active else CREAM
        # popped word sits slightly higher so both baselines look aligned
        wy = y - (pop_font.size - base_font.size) * 0.72 if i == active else y
        d.text((x + SHADOW_OFFSET, wy + SHADOW_OFFSET), word, font=f,
               fill=(0, 0, 0, 110), stroke_width=stroke, stroke_fill=(0, 0, 0, 110))
        d.text((x, wy), word, font=f, fill=color,
               stroke_width=stroke, stroke_fill=(12, 20, 32, 235))
        x += widths[i] + space
    img.save(dest)


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
    """Bake one beat's caption track as a transparent ProRes clip.

    timed_words: [{"disp","t"}] with t RELATIVE to the clip start (the caller
    retimes source seconds to beat-local seconds). Words are grouped into
    short phrases; one frame-state per word shows the whole phrase with the
    spoken word highlighted, held from its start until the next word begins.
    """
    if not timed_words:
        raise IngestError("bake_caption_clip: no words")
    tmp_dir.mkdir(parents=True, exist_ok=True)

    phrases = group_phrases(timed_words)
    states = []  # (png_path, start, end)
    idx = 0
    for p_i, phrase in enumerate(phrases):
        words = [x["disp"] for x in phrase]
        for w_i, word in enumerate(phrase):
            png = tmp_dir / ("cap_%03d.png" % idx)
            phrase_png(words, w_i, png, w, h, orientation)
            start = word["t"]
            if w_i + 1 < len(phrase):
                end = phrase[w_i + 1]["t"]
            elif p_i + 1 < len(phrases):
                # hold the finished phrase until the next one starts, but not
                # through a long silence — drop it after a beat of quiet.
                end = min(phrases[p_i + 1][0]["t"], start + 1.6)
            else:
                end = duration
            states.append((png, start, end))
            idx += 1

    inputs = ["-f", "lavfi", "-i",
              "color=c=black@0.0:s=%dx%d:r=%d:d=%.3f,format=rgba" % (w, h, fps, duration)]
    chains = []
    prev = "[0:v]"
    for i, (png, s, e) in enumerate(states):
        inputs += ["-loop", "1", "-t", "%.3f" % duration, "-r", str(fps), "-i", str(png)]
        s = max(0.0, min(s, duration - 0.05))
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
