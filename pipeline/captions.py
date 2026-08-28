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

def effective_captions(caps_doc: "dict", orientation: str,
                       vo_beats: "set | frozenset | None" = None) -> "dict":
    """beat_id -> caption text, AFTER the caption policy.

    Three rules, stacked in this order:

    1. PORTRAIT keeps every line, always. Short form is watched muted and
       is the discovery engine — no rule below may take a caption off a
       Short (Caleb, 2026-08-23).
    2. A VO beat in LANDSCAPE gets no caption: the voice is narration
       over footage and nobody is on screen to caption (Caleb,
       2026-08-24, as the format moved VO-led).
    3. Otherwise the punchline policy: with `"style": "punchline"` only
       beats marked `selected` bake — ~30% of lines, the ones that punch.
       Classic (no style field) bakes every line, which is what every
       episode captioned before 2026-08-23 keeps.

    `vo_beats` is the set of beat ids whose take is a `vo_` recording —
    the SAME predicate `schemas.coverage_notes` uses for its VO
    exemption, passed in rather than re-derived so the two rules cannot
    drift apart. Omitting it means "no VO beats", which is exactly right
    for a cut that has none: hmns is frozen at 82 beats and 0 VO beats,
    so this change cannot move its spec keys.
    """
    beats = (caps_doc or {}).get("beats", [])
    if orientation == "portrait":
        return {c["beat_id"]: c["text"] for c in beats}
    vo = vo_beats or frozenset()
    keep = [c for c in beats if c["beat_id"] not in vo]
    if (caps_doc or {}).get("style") == "punchline":
        keep = [c for c in keep if c.get("selected")]
    return {c["beat_id"]: c["text"] for c in keep}


def vo_beats_of(tl_map: "dict") -> "frozenset":
    """Beat ids carried by a voice-over recording. One definition, used
    by every caller — a `vo_` take id is the same marker the coverage
    bar exempts from its ratio and landing rules."""
    # The map carries `kind`, resolved from the TAKE when it was built.
    # This used to test `take_id.startswith("vo_")` and could never be
    # true — ids are T01, T02; the prefix lives on the file (2026-08-28).
    return frozenset(b["id"] for b in (tl_map or {}).get("beats", [])
                     if b.get("kind") == "vo")


import difflib
import os
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .ingest import IngestError

# --- Ninth Room caption tokens (Cyanotype design system, 2026-08-20) ------
# Captions carry NO PLATE. The brand's protection method is "shadow and
# scrim, never capsule": each chalk word is drawn over a double dark shadow
# (a tight one and a soft dropped one), which is exactly what removes the
# need for a box. One keyword per line scales up in yellow — the frame's
# single yellow moment. Emoji are banned brand-wide and are stripped, not
# rendered.
#
# What breaks if this is wrong: a plate creeps back in and every caption
# reads as a template, which is the one thing the identity is built to avoid.
CHALK = (234, 244, 255)       # --chalk: all caption type
NAVY = (11, 35, 64)           # --navy-900
YELLOW = (255, 224, 77)       # --yellow: the keyword, the only accent
CYAN = (56, 225, 240)         # --cyan: speaker tag (overlay kit draws it)
SHADOW_INK = (4, 16, 32)      # the colour both text shadows are made of

# The two shadows, in 1080-class pixels. Mirrors --shadow-chalk exactly:
#   0 0 4px rgba(4,16,32,.95), 0 4px 18px rgba(4,16,32,.9)
# Burned captions use the STRONG variant (--shadow-chalk-strong), which the
# canvas itself specifies for the bright-footage frame:
#   0 0 5px rgba(4,16,32,1), 0 4px 18px rgba(4,16,32,.95)
# A burned caption cannot know what is behind it, so it is always sized for
# the worst case. The tight core is composited twice to reach full density,
# which Pillow's single blurred pass cannot do on its own.
SHADOW_TIGHT_BLUR = 5
SHADOW_TIGHT_ALPHA = 255      # 1.0
SHADOW_TIGHT_PASSES = 2
SHADOW_SOFT_BLUR = 18
SHADOW_SOFT_DY = 4
SHADOW_SOFT_ALPHA = 242       # .95

# Legacy aliases so any old call site still resolves to an on-brand colour.
ICE = CHALK
DEEP = NAVY
CREAM = CHALK
AMBER = YELLOW

PHRASE_MAX_WORDS = 4
PHRASE_MAX_CHARS = 26
PHRASE_GAP_SEC = 0.9          # a pause this long always starts a new phrase
# Caption size and seat are CALEB'S values, not the design system's
# (2026-08-21: "captions smaller and a little bit lower"). The system's
# on-video ramp said 64px at 150 from the bottom; the shipped look is 54px
# at 105 — the spec values still govern every OTHER overlay. Portrait keeps
# its 320 bottom inset: that one is the Shorts UI safe zone, a platform
# constraint rather than a style choice, and lowering into it puts words
# under YouTube's own chrome.
PHRASE_FONT_SIZE = {"portrait": 66, "landscape": 54}
KEYWORD_SCALE = 86 / 64.0     # the spoken word scales up, it does not get a chip
BOTTOM_INSET = {"portrait": 320, "landscape": 105}
WORD_GAP = 20                 # `gap:0 20px` on the caption row
SIDE_INSET = {"portrait": 64, "landscape": 180}


# --- emoji in captions (Caleb, 2026-08-19, reaffirmed 2026-08-20) ---------
# Emoji are ENCOURAGED. They ride INSIDE the caption line, popping with the
# spoken word — attached to the joke, never covering a face, and inheriting
# the caption's visibility treatment. A standalone burst with no caption on
# screen is overlay_kit.emoji_pop instead.
#
# They are drawn from Apple Color Emoji as images, so they carry the same
# double shadow the chalk type does — otherwise a bright emoji floats off a
# bright frame while the words beside it stay anchored.
EMOJI_TTC = "/System/Library/Fonts/Apple Color Emoji.ttc"
EMOJI_SCALE = 1.22            # relative to the caption font size

# Bump when anything in this module changes rendered pixels — it invalidates
# every cached caption bake (see produce._beat_caption_clips).
CAPTIONS_V = 6   # v6: smaller, lower captions (Caleb) — size/inset are not keyed
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
    """Bricolage Grotesque ExtraBold — everything on video is set in it
    (repo copy in brand/fonts). System faces are the fallbacks."""
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
               orientation: str) -> int:
    """Render one caption phrase the Cyanotype way: chalk type, no plate.

    Returns the band's y offset: the image written to `dest` is only the
    caption BAND, not the full canvas — the caller overlays it at (0, y0).
    Rendering the band instead of the frame, and deriving both shadows from
    the text layer's own alpha at HALF resolution, is what took the bake
    from ~63 s a beat to a few seconds (workflow audit P0-3): the Gaussian
    blurs were burning full-canvas UHD passes per word-state.

    The half-res shadows are visually lossless — a blur is soft by
    definition, and it is upscaled bilinearly — while the text layer stays
    full resolution, so glyph edges keep their razor. Deriving shadows from
    the text alpha also covers emoji automatically (they composite into the
    text layer and their silhouette rides into both shadows).

    What breaks if this is wrong: captions become illegible over bright
    footage (shadows too weak), the band clips a tall phrase (pad too
    small), or a visible seam appears at the band edge (it must stay fully
    transparent at its top row).
    """
    s = min(w, h) / 1080.0
    size = int(round(PHRASE_FONT_SIZE[orientation] * s))
    key_size = int(round(size * KEYWORD_SCALE))
    word_gap = int(round(WORD_GAP * s))
    bottom_inset = int(round(BOTTOM_INSET[orientation] * s))
    side_inset = int(round(SIDE_INSET[orientation] * s))
    max_w = w - side_inset * 2

    if not words:
        Image.new("RGBA", (w, 4), (0, 0, 0, 0)).save(dest)
        return h - 4

    # Curly apostrophes throughout — the brand sets them, and whisper emits
    # straight ones. Purely typographic; never changes which word is spoken.
    # Emoji tokens pass through untouched.
    words = [wd if _is_emoji(wd) else wd.replace("'", "\u2019") for wd in words]

    font = _font(size)
    key_font = _font(key_size)
    probe = ImageDraw.Draw(Image.new("RGBA", (8, 8)))

    def _wf(i):
        return key_font if i == active else font

    # Emoji measure by their rendered image, not by the text font. The spoken
    # one is scaled up like a keyword would be.
    emoji_imgs = {}
    widths = []
    for i, word in enumerate(words):
        if _is_emoji(word):
            px = int(size * EMOJI_SCALE * (KEYWORD_SCALE if i == active else 1.0))
            em = _emoji_img(word, px)
            emoji_imgs[i] = em
            widths.append(float(em.width) if em is not None else 0.0)
        else:
            widths.append(probe.textlength(word, font=_wf(i)))

    # An emoji that Apple Color Emoji cannot rasterise comes back as None.
    # Keeping it as a zero-width token left its word_gap behind on BOTH sides,
    # so the caption rendered a visible double space where the glyph should
    # have been. A token that cannot be drawn should not occupy layout at all:
    # drop it, and remap the keyword index so the wrong word is not
    # highlighted. (Deferred kit defect, closed 2026-08-23.)
    drop = {i for i in emoji_imgs if emoji_imgs[i] is None}
    if drop:
        keep = [i for i in range(len(words)) if i not in drop]
        if active in drop:
            active = -1
        elif isinstance(active, int) and active >= 0:
            active = keep.index(active)
        words = [words[i] for i in keep]
        widths = [widths[i] for i in keep]
        emoji_imgs = {keep.index(i): im for i, im in emoji_imgs.items()
                      if i in keep}

    # Wrap into lines that fit between the side insets.
    lines, cur, cur_w = [], [], 0.0
    for i, word in enumerate(words):
        add = widths[i] + (word_gap if cur else 0)
        if cur and cur_w + add > max_w:
            lines.append(cur)
            cur, cur_w = [i], widths[i]
        else:
            cur.append(i)
            cur_w += add
    if cur:
        lines.append(cur)

    ascent, descent = key_font.getmetrics()
    line_h = int((ascent + descent) * 1.06)
    block_h = line_h * len(lines)
    top = h - bottom_inset - block_h
    # Shadow bleed pad: the soft blur reaches ~2.5x its radius plus its drop.
    pad = int((SHADOW_SOFT_BLUR * 2.5 + SHADOW_SOFT_DY + 8) * s)
    y0 = max(0, top - pad)
    bh = h - y0

    soft_dy = int(round(SHADOW_SOFT_DY * s))
    text_layer = Image.new("RGBA", (w, bh), (0, 0, 0, 0))
    dx = ImageDraw.Draw(text_layer)
    for row, idxs in enumerate(lines):
        total = sum(widths[i] for i in idxs) + word_gap * (len(idxs) - 1)
        x = (w - total) / 2.0
        y = (top - y0) + row * line_h
        for i in idxs:
            if i in emoji_imgs:
                em = emoji_imgs[i]
                if em is not None:
                    ey = int(y + (ascent - em.height) * 0.86)
                    text_layer.alpha_composite(em, (int(x), ey))
                    dx = ImageDraw.Draw(text_layer)
                x += widths[i] + word_gap
                continue
            f = _wf(i)
            a, _ = f.getmetrics()
            wy = y + (ascent - a)
            dx.text((x, wy), words[i], font=f,
                    fill=(YELLOW if i == active else CHALK) + (255,))
            x += widths[i] + word_gap

    # Shadows: the text layer's own alpha, halved, blurred at half radius,
    # upscaled. One source of truth for the silhouette; a fraction of the
    # blur cost.
    from PIL import ImageFilter
    sil = text_layer.getchannel("A").resize(
        (max(1, w // 2), max(1, bh // 2)), Image.BILINEAR)
    tight_m = sil.filter(ImageFilter.GaussianBlur(max(0.5, SHADOW_TIGHT_BLUR * s / 4.0)))
    soft_m = sil.filter(ImageFilter.GaussianBlur(max(0.5, SHADOW_SOFT_BLUR * s / 4.0)))
    tight_m = tight_m.resize((w, bh), Image.BILINEAR)
    soft_m = soft_m.resize((w, bh), Image.BILINEAR)
    if SHADOW_SOFT_ALPHA < 255:
        soft_m = soft_m.point(lambda v: v * SHADOW_SOFT_ALPHA // 255)

    img = Image.new("RGBA", (w, bh), (0, 0, 0, 0))
    soft_rgba = Image.new("RGBA", (w, bh), SHADOW_INK + (0,))
    soft_rgba.putalpha(soft_m)
    img.alpha_composite(soft_rgba, (0, soft_dy))
    tight_rgba = Image.new("RGBA", (w, bh), SHADOW_INK + (0,))
    tight_rgba.putalpha(tight_m)
    for _ in range(SHADOW_TIGHT_PASSES):
        img.alpha_composite(tight_rgba)
    img.alpha_composite(text_layer)
    img.save(dest)
    return y0


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

# `word_chip` (one big word on a rounded navy chip) was removed in the
# Cyanotype rebrand — a filled chip is precisely what the brand forbids, and
# nothing called it. The caption renderer above is the only word treatment.


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
            y0 = phrase_png(words, w_i, png, w, h, orientation)
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
            states.append((png, start, end, y0))
            idx += 1

    inputs = ["-f", "lavfi", "-i",
              "color=c=black@0.0:s=%dx%d:r=%d:d=%.3f,format=rgba" % (w, h, fps, duration)]
    chains = []
    prev = "[0:v]"
    for i, (png, s, e, y0) in enumerate(states):
        inputs += ["-loop", "1", "-t", "%.3f" % duration, "-r", str(fps), "-i", str(png)]
        s = max(0.0, min(s, duration - 0.05))
        e = max(s + 0.05, min(e, duration))
        # the state PNG is only the caption BAND; place it at its own y
        chains.append("%s[%d:v]overlay=0:%d:format=auto:enable='between(t,%.3f,%.3f)'[v%d]"
                      % (prev, i + 1, y0, s, e, i))
        prev = "[v%d]" % i
    from .graphics import prores_encode_args
    cmd = (["ffmpeg", "-y", "-loglevel", "error"] + inputs +
           ["-filter_complex", ";".join(chains), "-map", prev,
            "-t", "%.3f" % duration]
           + prores_encode_args() + [str(out_mov)])
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise IngestError("caption bake failed: %s" % proc.stderr[-300:])
