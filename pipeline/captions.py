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

# --- Ninth Room caption tokens (design handoff, 2026-08-19) ---------------
# Captions are CHIPS, matching overlay_kit.py exactly: a midnight-deep plate
# at 0.94 alpha with a 5px ice outline, 14px radius, and a hard offset
# shadow. The active word sits on its own little amber chip with
# midnight text. Over bright footage the plate alone is enough — the spec
# forbids adding a stroke as well.
ICE = (232, 239, 246)         # --ice-paper, type on the plate
DEEP = (11, 18, 28)           # --midnight-deep
PLATE = (11, 18, 28, 240)     # plate fill at 0.94 alpha
AMBER = (255, 174, 59)        # --fun: the active-word chip
SHADOW_FILL = (5, 9, 15, 153) # hard offset shadow, no blur
CREAM = ICE                   # legacy alias for old call sites

# Legacy word-chip constants (word_chip renderer, kept for old callers).
NAVY_CHIP = (11, 18, 28, 240)
CHIP_ANCHOR_Y = {"portrait": 1290, "landscape": 830}
CHIP_FONT_SIZE = {"portrait": 110, "landscape": 84}

PHRASE_MAX_WORDS = 4
PHRASE_MAX_CHARS = 26
PHRASE_GAP_SEC = 0.9          # a pause this long always starts a new phrase
PHRASE_FONT_SIZE = {"portrait": 72, "landscape": 56}
BOTTOM_INSET = {"portrait": 320, "landscape": 120}  # chip bottom edge
WORD_GAP = 14                 # column gap between words on the plate
PLATE_PAD_X = 30
PLATE_PAD_Y = 16
PLATE_RADIUS = 14
OUTLINE_PX = 5
ACTIVE_PAD_X = 12             # the amber chip around the active word
ACTIVE_RADIUS = 8
SHADOW_OFFSET = 8


# --- emoji in captions (Caleb, 2026-08-19) --------------------------------
# Emoji ride INSIDE the caption line, popping with the spoken word — attached
# to the joke, never covering a face, inheriting the caption's visibility
# treatment. A standalone centered emoji card (overlay_kit.emoji_pop) is the
# fallback only for moments with no caption on screen.
EMOJI_TTC = "/System/Library/Fonts/Apple Color Emoji.ttc"
EMOJI_SCALE = 1.22            # relative to the caption font size

# Bump when anything in this module changes rendered pixels — it invalidates
# every cached caption bake (see produce._beat_caption_clips).
CAPTIONS_V = 2   # v2: Ninth Room chip captions (design handoff 2026-08-19)
_EMOJI_CACHE: "dict" = {}


def _is_emoji(tok: str) -> bool:
    """True for tokens that are pictographs, not words (no letters/digits)."""
    t = tok.strip()
    return bool(t) and not any(c.isalnum() for c in t) and \
        any(ord(c) >= 0x2190 for c in t)


def _emoji_img(tok: str, px: int) -> "Image.Image | None":
    """The emoji rendered to a tight RGBA image `px` tall (cached).

    Apple Color Emoji is a bitmap (sbix) font: Pillow 11 scales most sizes
    but rejects a few (137). Render at 160 and resize — always works.
    """
    key = (tok, px)
    if key in _EMOJI_CACHE:
        return _EMOJI_CACHE[key]
    try:
        f = ImageFont.truetype(EMOJI_TTC, 160)
    except OSError:
        _EMOJI_CACHE[key] = None
        return None
    canvas = Image.new("RGBA", (200 * len(tok), 220), (0, 0, 0, 0))
    ImageDraw.Draw(canvas).text((20, 20), tok, font=f, embedded_color=True)
    bb = canvas.getbbox()
    if not bb:
        _EMOJI_CACHE[key] = None
        return None
    img = canvas.crop(bb)
    img = img.resize((max(1, round(img.width * px / img.height)), px),
                     Image.LANCZOS)
    _EMOJI_CACHE[key] = img
    return img


_FONT_CACHE: "dict" = {}


def _font(size: int, heavy: bool = True):
    """Bricolage Grotesque ExtraBold — the kit's chip face (repo copy in
    brand/fonts). Gabarito and system faces are the fallbacks."""
    key = (size, heavy)
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]
    repo_fonts = Path(__file__).resolve().parent.parent / "brand" / "fonts"
    bricolage = repo_fonts / "Bricolage.ttf"
    if bricolage.exists():
        try:
            f = ImageFont.truetype(str(bricolage), size)
            f.set_variation_by_name("ExtraBold" if heavy else "SemiBold")
            _FONT_CACHE[key] = f
            return f
        except OSError:
            pass
    candidates = [
        (str(Path.home() / "Library/Fonts/Gabarito-Variable.ttf"), 0),
        ("/System/Library/Fonts/Avenir Next.ttc", 8 if heavy else 0),
        ("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 0),
        ("/System/Library/Fonts/Helvetica.ttc", 0),
    ]
    for path, index in candidates:
        if os.path.exists(path):
            try:
                f = ImageFont.truetype(path, size, index=index)
                _FONT_CACHE[key] = f
                return f
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
            # an emoji reacts to the phrase it follows — never orphan it into
            # its own phrase just because the line it tags ended in punctuation
            if _is_emoji(w["disp"]):
                too_long = ended = False
            if too_long or paused or ended:
                phrases.append(cur)
                cur = []
        cur.append(w)
    if cur:
        phrases.append(cur)
    return phrases


def phrase_png(words: "list[str]", active: int, dest: Path, w: int, h: int,
               orientation: str) -> None:
    """Render one phrase as a Ninth Room caption chip.

    The whole phrase sits on a midnight-deep plate (0.94 alpha, 5px ice
    outline, hard offset shadow); the active word sits on its own amber
    chip with midnight text. Matches overlay_kit.caption_plate exactly.
    """
    size = PHRASE_FONT_SIZE[orientation]
    font = _font(size)

    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # Measure. The active word carries its chip padding; emoji measure by
    # their rendered image.
    ascent, descent = font.getmetrics()
    line_h = ascent + descent
    widths, emoji_imgs = [], {}
    for i, word in enumerate(words):
        if _is_emoji(word):
            px = int(size * EMOJI_SCALE * (1.12 if i == active else 1.0))
            em = _emoji_img(word, px)
            emoji_imgs[i] = em
            widths.append(em.width if em else 0)
        else:
            tw = d.textlength(word, font=font)
            if i == active:
                tw += ACTIVE_PAD_X * 2
            widths.append(tw)
    total = sum(widths) + WORD_GAP * (len(words) - 1)

    plate_w = int(total + PLATE_PAD_X * 2)
    plate_h = int(line_h + PLATE_PAD_Y * 2)
    px0 = int((w - plate_w) / 2)
    py0 = h - BOTTOM_INSET[orientation] - plate_h

    # Hard offset shadow, then plate, then the 5px ice outline.
    d.rounded_rectangle((px0 + SHADOW_OFFSET, py0 + SHADOW_OFFSET,
                         px0 + plate_w + SHADOW_OFFSET, py0 + plate_h + SHADOW_OFFSET),
                        radius=PLATE_RADIUS, fill=SHADOW_FILL)
    d.rounded_rectangle((px0, py0, px0 + plate_w, py0 + plate_h),
                        radius=PLATE_RADIUS, fill=PLATE,
                        outline=tuple(ICE), width=OUTLINE_PX)

    x = px0 + PLATE_PAD_X
    ty = py0 + PLATE_PAD_Y
    mid_y = ty + line_h * 0.52
    for i, word in enumerate(words):
        if i in emoji_imgs:
            em = emoji_imgs[i]
            if em is not None:
                ey = int(mid_y - em.height / 2)
                img.alpha_composite(em, (int(x), ey))
                d = ImageDraw.Draw(img)   # plate edits above may invalidate
            x += widths[i] + WORD_GAP
            continue
        if i == active:
            # the amber chip behind the spoken word, midnight text on it
            cw = widths[i]
            cy0 = ty + max(0, ascent - size)  # hug the glyph box
            d.rounded_rectangle((x, py0 + PLATE_PAD_Y - 4,
                                 x + cw, py0 + plate_h - PLATE_PAD_Y + 4),
                                radius=ACTIVE_RADIUS, fill=tuple(AMBER))
            d.text((x + ACTIVE_PAD_X, ty), word, font=font, fill=tuple(DEEP))
        else:
            d.text((x, ty), word, font=font, fill=tuple(ICE))
        x += widths[i] + WORD_GAP
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
            if _norm(tok) or _is_emoji(tok)]
    # emoji never match the transcript — a sentinel keeps difflib from
    # pairing their empty normalization with a stray empty whisper token
    S = ["\x00emoji" if _is_emoji(d) else _norm(d) for d in disp]
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
    # an emoji tagged onto a line inherits its neighbour's timestamp — pop it
    # a breath AFTER the word it reacts to instead of on top of it
    for i, o in enumerate(out):
        if _is_emoji(o["disp"]) and i > 0 and o["t"] <= out[i - 1]["t"] + 0.05:
            o["t"] = round(out[i - 1]["t"] + 0.3, 3)
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
                # The final phrase also drops after a beat of quiet instead of
                # holding to the clip end: when a beat's captions are cut short
                # on purpose (BT09, Caleb's round-2 review), speech continues
                # uncaptioned and a stale held phrase reads as a caption bug.
                # Beats whose audio ends with the last word are unaffected —
                # their tail pad is far shorter than the 1.6s hold.
                end = min(duration, start + 1.6)
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
