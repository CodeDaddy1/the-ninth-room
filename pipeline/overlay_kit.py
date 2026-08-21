"""The Ninth Room Overlay Kit — Cyanotype (kit v4).

Source of truth: the **Ninth Room Design System** on claude.ai/design
(project 4b8bb4a4-b234-45ed-aa84-b35ce761648b), whose own readme names
`uploads/The Ninth Room - Cyanotype Kit.dc.html` as ground truth for
everything that appears on video. This module is the runtime version of that
canvas: same geometry, same keyframes, same delays, with the copy
parameterised so the pipeline fills it per card.

The system in one paragraph. Navy `#0B2340` is the ground. Every line of type
is chalk `#EAF4FF` carrying a double text-shadow, which is what removes the
need for a box behind it. Cyan `#38E1F0` is *structural* — eyebrow rules,
speaker tags, crop marks, anything that means "verified". Yellow `#FFE04D` is
*the one thing to look at*. Slate `#7C9BBC` carries losing values and never
accents anything. Where footage is too bright to read against, the answer is
a gradient scrim, never a panel.

Two rules govern every component here, and both are enforced in code rather
than left to the caller:

    1. NO FILLED PLATES.  There is no `background:` on any text container in
       this file. Legibility comes from `SHADOW_CHALK` and, where needed,
       `_scrim()`. The only filled shapes in the kit are the arch's light,
       a quiz answer flooding, and a poll bar — each of which is the subject,
       not a backdrop.
    2. ONE YELLOW MOMENT PER FRAME.  `emphasize()` marks only the FIRST
       emphasis term it finds (see its docstring). If two things are yellow,
       neither is the thing to look at.

**Emoji are encouraged** (Caleb, 2026-08-20 — this overrides the design
system readme's "no emoji anywhere", which was written from the earlier
uploads). They are the channel's playfulness, and a family channel that
refuses them reads colder than it is.

They are treated as PICTURES, not type, which is what keeps them from
fighting the Cyanotype palette:

  * they ride in the *language* lines — hooks, reactions, captions, stamps,
    option labels — never inside structural type (eyebrows, labels, CTAs
    stay clean caps, because that type is the system talking, not a person);
  * they carry a `drop-shadow` matching the chalk text-shadow, so they sit
    on footage exactly the way the type does rather than floating;
  * they do NOT consume the frame's yellow moment. An emoji is a picture and
    the yellow word is still the thing to look at.

Renders through `pipeline.animate`, which pauses every CSS animation and
seeks `currentTime` frame by frame in headless Chrome — so the delays and
curves written here are the ones that reach the timeline.

What breaks if this is wrong: overlays drift off-brand in ways that are hard
to see in one frame and obvious across a channel (a plate creeping back in, a
second yellow element stealing the eye, cyan used decoratively). Always
render-test a card with REAL copy before shipping it — the long-text guards
below shrink type, but they cannot invent room that is not there.
"""
from __future__ import annotations

import html
import re

from . import design_tokens as _dt

# --- Cyanotype tokens ------------------------------------------------------
# Pulled from brand/design-system/tokens/colors.css, which is synced from the
# design system. The literals are the documented fallback for a missing file.

_T = _dt.load()


def _tok(name: str, fallback: str) -> str:
    return _dt.resolve(_T, name, fallback) or fallback


NAVY = _tok("navy-900", "#0B2340")        # base. scrims, washes, type on accents
NAVY_800 = _tok("navy-800", "#173456")    # deep surface
NAVY_700 = _tok("navy-700", "#1C4570")    # inert structure
CHALK = _tok("chalk", "#EAF4FF")          # all type on video
YELLOW = _tok("yellow", "#FFE04D")        # the one thing to look at
CYAN = _tok("cyan", "#38E1F0")            # verified. rules, eyebrows, crop marks
SLATE_300 = _tok("slate-300", "#8FB3D6")  # supporting copy
SLATE_400 = _tok("slate-400", "#7C9BBC")  # losing values. never an accent
SLATE_500 = _tok("slate-500", "#5F81A6")  # captions under specimens

FONT_DISPLAY = _tok("font-display", "'Bricolage Grotesque',system-ui,sans-serif")
FONT_SERIF = _tok("font-serif", "'Newsreader',Georgia,serif")
FONT_UI = _tok("font-ui", "'Manrope',system-ui,sans-serif")

# The double shadow IS the plate. Never remove it from chalk type on footage.
SHADOW_CHALK = _tok("shadow-chalk",
                    "0 0 4px rgba(4,16,32,.95),0 4px 18px rgba(4,16,32,.9)")
SHADOW_STRONG = _tok("shadow-chalk-strong",
                     "0 0 5px rgba(4,16,32,1),0 4px 18px rgba(4,16,32,.95)")
SHADOW_DISPLAY = _tok("shadow-chalk-display",
                      "0 0 5px rgba(4,16,32,.95),0 5px 24px rgba(4,16,32,.9)")
SHADOW_STAT = _tok("shadow-stat", "0 6px 30px rgba(4,16,32,.85)")

EASE_REVEAL = _tok("ease-reveal", "cubic-bezier(.16,1,.3,1)")   # things arriving
EASE_RULE = _tok("ease-rule", "cubic-bezier(.22,.61,.36,1)")    # rules and wipes

SCRIM_LOWER = _tok("scrim-lower", "linear-gradient(180deg,rgba(11,35,64,0) 48%,"
                                  "rgba(11,35,64,.6) 76%,rgba(11,35,64,.9) 100%)")
SCRIM_LOWER_TALL = _tok("scrim-lower-tall", "linear-gradient(180deg,rgba(11,35,64,0) 30%,"
                                            "rgba(11,35,64,.7) 72%,rgba(11,35,64,.94) 100%)")
SCRIM_SIDE = _tok("scrim-side", "linear-gradient(90deg,rgba(11,35,64,0) 22%,"
                                "rgba(11,35,64,.72) 52%,rgba(11,35,64,.93) 100%)")
WASH_CHAPTER = _tok("wash-chapter", "rgba(11,35,64,.86)")
WASH_TEASER = _tok("wash-teaser", "rgba(11,35,64,.72)")

STROKE = 3          # minimum on video so an outline survives compression
STROKE_CALLOUT = 4
INERT = "rgba(234,244,255,.4)"    # an option nobody has picked yet
HAIRLINE = "rgba(234,244,255,.28)"

# Legacy aliases so any straggling import keeps resolving. The Midnight names
# are gone from the brand; these map onto their Cyanotype equivalents.
ICE = CHALK
TRUE_BLUE = CYAN
FUN = YELLOW
MUTED = SLATE_400
SUBTLE = SLATE_300
ACCENT = YELLOW
TEXT = CHALK

# The kit's keyframes, verbatim from the Cyanotype canvas. Names are prefixed
# `y` there; kept identical so a diff against the canvas is readable.
KEYFRAMES = """
@keyframes yFade{from{opacity:0}to{opacity:1}}
@keyframes yUp{from{opacity:0;transform:translateY(16px)}to{opacity:1;transform:translateY(0)}}
@keyframes ySlide{from{opacity:0;transform:translateX(-14px)}to{opacity:1;transform:translateX(0)}}
@keyframes yGrow{from{transform:scaleX(0)}to{transform:scaleX(1)}}
@keyframes yGrowY{from{transform:scaleY(0)}to{transform:scaleY(1)}}
@keyframes yStretch{0%{opacity:0;transform:scaleY(.55) scaleX(1.16)}60%{opacity:1;transform:scaleY(1.07) scaleX(.98)}100%{opacity:1;transform:scale(1)}}
@keyframes yPop{0%{opacity:0;transform:scale(.78)}62%{opacity:1;transform:scale(1.07)}100%{opacity:1;transform:scale(1)}}
@keyframes yRing{from{transform:rotate(0)}to{transform:rotate(360deg)}}
@keyframes yCount{0%{opacity:0;transform:scale(1.5)}8%{opacity:1;transform:scale(1)}100%{opacity:0;transform:scale(1)}}
@keyframes yCountHold{0%{opacity:0;transform:scale(1.5)}8%{opacity:1;transform:scale(1)}100%{opacity:1;transform:scale(1)}}
@keyframes yDim{from{opacity:1}to{opacity:.28}}
@keyframes yDot{0%{opacity:0;transform:scale(.5)}100%{opacity:1;transform:scale(1)}}
@keyframes yPulse{0%,100%{transform:scale(1);opacity:1}50%{transform:scale(1.035);opacity:.82}}
@keyframes yTick{0%{transform:translateY(0) scale(1)}36%{transform:translateY(-16px) scale(1.28)}100%{transform:translateY(0) scale(1)}}
@keyframes yRule{0%,12%{left:-1%}62%,100%{left:101%}}
@keyframes yReveal{0%,12%{clip-path:inset(0 100% 0 0)}62%,100%{clip-path:inset(0 0 0 0)}}
@keyframes yIris{0%{clip-path:inset(0 0 0 0)}44%,56%{clip-path:inset(42% 46% 42% 46%)}100%{clip-path:inset(0 0 0 0)}}
@keyframes yMark{0%{opacity:0;transform:scale(1.5)}30%,66%{opacity:1;transform:scale(1)}100%{opacity:0;transform:scale(1.5)}}
@keyframes yColUp{0%,10%{transform:scaleY(0)}44%,58%{transform:scaleY(1)}94%,100%{transform:scaleY(0)}}
@keyframes yColShow{0%,46%{opacity:0}56%,100%{opacity:1}}
@keyframes yPushOut{0%,10%{transform:translateX(0)}58%,100%{transform:translateX(-100%)}}
/* yPulse, yMark and yPushOut are defined here to stay 1:1 with the Cyanotype
   canvas but have no caller in this module. yPushOut is the interesting one:
   the push cut pushes an OUTGOING layer out, and an overlay clip has no
   outgoing layer — that half of the cut is done by the footage in Resolve.
   Keep them; an `animation:` naming a keyframe that does NOT exist renders
   the element static, which is invisible in a still frame. */
@keyframes yPushIn{0%,10%{transform:translateX(100%)}58%,100%{transform:translateX(0)}}
@keyframes yBracket{0%,10%{transform:scaleX(0);opacity:0}22%{opacity:1}44%{transform:scaleX(1);opacity:1}62%,100%{opacity:0}}
@keyframes yDraw{to{stroke-dashoffset:0}}
@keyframes yBurst{0%{opacity:1;transform:translate(0,0) scale(1)}100%{opacity:0;transform:translate(0,-260px) scale(.3)}}
@keyframes yInk{from{color:#EAF4FF;text-shadow:0 0 4px rgba(4,16,32,.95),0 4px 18px rgba(4,16,32,.9)}to{color:#0B2340;text-shadow:0 0 4px rgba(4,16,32,0),0 4px 18px rgba(4,16,32,0)}}
"""

# --- text hygiene ----------------------------------------------------------

# Ranges that cover the emoji and pictograph blocks plus the variation
# selector and zero-width joiner that stitch sequences together. The brand
# bans all of them; see the module docstring.
_EMOJI_RE = re.compile(
    "[\U0001F000-\U0001FAFF\u2190-\u21FF\u2300-\u27BF\u2B00-\u2BFF"
    "\uFE0F\u200D\u2060\U0001F1E6-\U0001F1FF]+")


# Apple Color Emoji is what headless Chrome resolves these to on macOS, so
# what bakes is what the Mac shows. The shadow mirrors --shadow-chalk.
EMOJI_SHADOW = ("drop-shadow(0 0 3px rgba(4,16,32,.95)) "
                "drop-shadow(0 3px 12px rgba(4,16,32,.9))")


def _no_emoji(text: str) -> str:
    """Strip emoji. Used for MEASUREMENT only, never for what reaches screen.

    `_fit()` sizes display type by character count, and an emoji is one
    codepoint that renders as wide as a capital letter or wider — counting the
    raw string is close enough, but counting a ZWJ sequence as its five
    component codepoints is not. This gives the sizer a clean string.
    """
    out = _EMOJI_RE.sub("", str(text))
    out = re.sub(r"[ \t]{2,}", " ", out)
    return out.strip()


def _emoji_spans(escaped: str) -> str:
    """Wrap every emoji run so it sits on footage like the type around it.

    Runs on ALREADY-ESCAPED html — emoji are outside the ASCII range that
    `html.escape` touches, so the regex still matches cleanly and no entity
    can be split.
    """
    return _EMOJI_RE.sub(
        lambda m: '<span style="filter:%s;text-shadow:none">%s</span>'
                  % (EMOJI_SHADOW, m.group(0)), escaped)


# Straight quotes are a document convention; the brand sets curly throughout.
def _smart(text: str) -> str:
    # Coerce first: a graphics_plan is JSON, so a count or a percentage may
    # arrive as an int or float rather than a string ({"value": 3}). The
    # schema accepts that, so a bare re.sub would raise TypeError mid-bake —
    # after minutes of rendering, from a plan that validated clean.
    text = text if isinstance(text, str) else str(text)
    out = re.sub(r"(^|[\s(\[])\"", "\\1\u201c", text)
    out = out.replace('"', "\u201d")
    out = re.sub(r"(\w)'(\w)", "\\1\u2019\\2", out)
    out = re.sub(r"(^|[\s(\[])'", "\\1\u2018", out)
    return out.replace("'", "\u2019")


def _e(text: str) -> str:
    """Escape for HTML, tidy quotes, and give any emoji its own shadow.

    Every user-visible string goes through here. Emoji are kept and wrapped
    (see `_emoji_spans`); they are part of the voice, not something to clean
    out of it.
    """
    return _emoji_spans(html.escape(_smart(text)))


def _caps(text: str) -> str:
    """Structural type only — eyebrows, labels, CTAs. Never a sentence.

    `.upper()` is applied to the SOURCE, before escaping and emoji wrapping,
    so an uppercased string can never mangle an html entity (`&amp;` ->
    `&AMP;`) or a style attribute. Emoji are unaffected by casing and ride
    through, which is why an eyebrow may still carry one.
    """
    return _e(str(text).upper())


def emphasize(text: str, emphasis: "list | None") -> str:
    """Mark ONE term yellow. The rest of the line stays chalk.

    The brand's central rule is one yellow moment per frame, so this marks
    only the first emphasis term that actually occurs in the text, even when
    the caller passes several. A graphics plan that lists three keywords is
    not wrong — it is expressing preference order, and this picks the winner.

    What breaks if this is wrong: two or three yellow words compete, and the
    frame loses its single point of focus.
    """
    out = _e(text)
    for word in emphasis or []:
        needle = _e(word)
        if needle and needle in out:
            return out.replace(needle,
                               '<span style="color:%s">%s</span>' % (YELLOW, needle),
                               1)
    return out


# --- frame geometry --------------------------------------------------------

def _frame(w: int, h: int) -> "dict":
    """Fixed insets for this aspect. The design system forbids nudging them.

    Landscape (1920x1080): captions 150 from the bottom, 120 sides, watermark
    72/64 top-right. Vertical (1080x1920): 180 top, 320 bottom, 64 sides —
    the 320 clears the Shorts UI, the 180 clears the top chrome.
    """
    portrait = h > w
    return {
        "w": w, "h": h, "portrait": portrait,
        "side": 64 if portrait else 120,
        "bottom": 320 if portrait else 150,
        "top": 180 if portrait else 130,
        "hook_left": 64 if portrait else 130,
        "chapter_left": 64 if portrait else 140,
        "inner": (w - 128) if portrait else 1560,
    }


# Measured, not guessed: Bricolage Grotesque ExtraBold averages 51px of
# advance per character at font-size 100 across real card copy (mixed case,
# digits, spaces). Sampled 2026-08-20 with the repo's own font file — an
# earlier guess of 22 under-shrank by more than 2x and would have let long
# lines run straight off the frame.
ADVANCE_PER_100 = 51.0

# Emoji are square-ish and wider than a letter at the same size.
EMOJI_ADVANCE_PER_100 = 108.0


def _text_width(text: str, size: int) -> float:
    """Approximate rendered width in px, counting emoji at their real width."""
    plain = _no_emoji(text)
    n_emoji = len(_EMOJI_RE.findall(str(text)))
    return (len(plain) * ADVANCE_PER_100 + n_emoji * EMOJI_ADVANCE_PER_100) \
        * (size / 100.0)


def _fit(text: str, base: int, per_char: "int | None" = None,
         floor_ratio: float = 0.52, budget: int = 1560,
         lines: int = 1) -> int:
    """Shrink display type when the copy is longer than the frame allows.

    The kit's sizes assume the brand's length caps (three-to-five-word hooks,
    two-or-three-word chapter titles). Real copy sometimes runs longer, and a
    silent overflow is worse than a smaller headline.

    `lines` is how many lines the block is allowed to wrap onto — the width
    budget multiplies by it, since wrapping is a legitimate way to fit.

    `per_char` is accepted and IGNORED. Call sites used to pass hand-tuned
    values that were all wrong in the same direction; the measured model above
    replaced them and every in-repo caller has been migrated off it. The
    parameter survives only so an outside caller does not break — do not pass
    it, and do not tune it expecting an effect.

    What breaks if this is wrong: a long lower third runs past the frame edge
    and the last word is cut in half — invisible in a plan, obvious on screen.
    """
    width = _text_width(text, base)
    allowed = float(budget) * max(1, lines)
    if width <= allowed:
        return base
    scaled = int(base * allowed / width)
    return max(int(base * floor_ratio), scaled)


# --- shared primitives -----------------------------------------------------
# Four drawn shapes make the whole system: the rule, the crop mark, the grid,
# and the dimension bracket. Everything below is built from these.

def _rule(width: int, color: str = CYAN, delay: int = 0, origin: str = "left",
          thick: int = STROKE) -> str:
    return ('<div style="width:%dpx;height:%dpx;background:%s;transform-origin:%s;'
            'animation:yGrow 260ms %s %dms both"></div>'
            % (width, thick, color, origin, EASE_RULE, delay))


def _eyebrow(text: str, color: str = CYAN, delay: int = 0, size: int = 26,
             centered: bool = False, track: str = ".22em") -> str:
    """Cyan rule plus caps label — the most-used element in the kit."""
    if not text:
        return ""
    label = ('<span style="font-family:%s;font-size:%dpx;font-weight:800;'
             'letter-spacing:%s;text-transform:uppercase;color:%s">%s</span>'
             % (FONT_DISPLAY, size, track, color, _caps(text)))
    bar = 44 if centered else 56
    tail = _rule(bar, color, delay, "right") if centered else ""
    return ('<div style="display:flex;align-items:center;gap:12px;'
            'animation:yFade 200ms ease %dms both">%s%s%s</div>'
            % (delay, _rule(bar, color, delay), label, tail))


def _display(size: int, tracking: str = "-.04em", color: str = CHALK,
             weight: int = 800, lh: str = "1.04") -> str:
    return ("font-family:%s;font-size:%dpx;line-height:%s;font-weight:%d;"
            "letter-spacing:%s;color:%s;text-shadow:%s"
            % (FONT_DISPLAY, size, lh, weight, tracking, color, SHADOW_DISPLAY))


def _scrim(kind: str = "lower") -> str:
    """The answer to bright footage. Never a filled panel."""
    grad = {"lower": SCRIM_LOWER, "tall": SCRIM_LOWER_TALL,
            "side": SCRIM_SIDE}.get(kind, SCRIM_LOWER)
    return '<div style="position:absolute;inset:0;background:%s"></div>' % grad


def _wash(alpha: str) -> str:
    return '<div style="position:absolute;inset:0;background:%s"></div>' % alpha


def _crop_marks(color: str = CYAN, size: int = 26, delay: int = 0) -> str:
    """An L of two strokes at each corner — the kit's bracket device."""
    corners = (("left:0;top:0", "border-left:%dpx solid %s;border-top:%dpx solid %s"),
               ("right:0;top:0", "border-right:%dpx solid %s;border-top:%dpx solid %s"),
               ("left:0;bottom:0", "border-left:%dpx solid %s;border-bottom:%dpx solid %s"),
               ("right:0;bottom:0", "border-right:%dpx solid %s;border-bottom:%dpx solid %s"))
    out = []
    for pos, borders in corners:
        out.append('<div style="position:absolute;%s;width:%dpx;height:%dpx;%s;'
                   'animation:yFade 240ms ease %dms both"></div>'
                   % (pos, size, size, borders % (STROKE, color, STROKE, color), delay))
    return "".join(out)


def _outline_option(text: str, delay: int, won: bool = False, dim: int = 0,
                    size: int = 46, flood_at: int = 0) -> str:
    """An option is an OUTLINE. The answer is that outline flooding with yellow.

    There are no filled cards on video — a filled box is the thing the brand
    calls a template. `flood_at` (ms) drives the yellow sweeping in behind the
    winning option; `dim` (ms) drops the losers to 28%.
    """
    border = YELLOW if won else INERT
    weight = 800 if won else 700
    anim = "yUp 280ms %s %dms both" % (EASE_REVEAL, delay)
    if dim:
        anim += ",yDim 260ms ease %dms both" % dim
    flood, ink = "", ""
    if flood_at:
        flood = ('<div style="position:absolute;inset:0;background:%s;'
                 'transform-origin:left;animation:yGrow 420ms %s %dms both"></div>'
                 % (YELLOW, EASE_RULE, flood_at))
        # Type on either accent is always navy (the design note on the quiz
        # card says so outright). Interpolating both colour and shadow means
        # the line darkens exactly as the yellow sweeps under it, and holds.
        ink = ";animation:yInk 300ms %s %dms both" % (EASE_RULE, flood_at + 180)
    return ('<div style="position:relative;border:%dpx solid %s;padding:16px 32px;'
            'font-family:%s;font-size:%dpx;font-weight:%d;color:%s;text-align:center;'
            'text-shadow:%s;animation:%s">%s'
            '<span style="position:relative;color:%s;text-shadow:%s%s">%s</span></div>'
            % (STROKE, border, FONT_DISPLAY, size, weight, CHALK, SHADOW_CHALK,
               anim, flood, CHALK, SHADOW_CHALK, ink, _e(text)))


def _ticks(delay: int = 620) -> str:
    """The dimension bracket under a stat — the kit's one flourish, last in."""
    bars = []
    for i in range(7):
        tall = i % 3 == 0
        bars.append('<div style="width:2px;height:%dpx;background:rgba(234,244,255,%s)"></div>'
                    % (14 if tall else 8, ".5" if tall else ".28"))
    return ('<div style="display:flex;gap:12px;align-items:flex-end;height:14px;'
            'margin-top:22px;animation:yFade 300ms ease %dms both">%s</div>'
            % (delay, "".join(bars)))


def _arch(width: int, outline: str = CYAN, light: str = YELLOW,
          shadow: str = NAVY, figure: bool = True, stroke: int = 4,
          animate: bool = False) -> str:
    """The Archway mark, drawn to the documented 8u x 10u grid.

    u = width/8, so the arch radius is exactly 4u — a true semicircle, never a
    squashed oval. The wall's thickness is thrown as the offset shadow inside
    the arch; that shadow is the only shadow the brand owns. The figure is
    dropped below 48px tall by the caller (see `size ladder` in the kit).

    What breaks if this is wrong: the head stops being a semicircle and the
    mark reads as a generic rounded rectangle.
    """
    u = width / 8.0
    h = int(u * 10)
    r = int(u * 4)
    sx, sy = int(u * 2.6), int(u * 1.1)
    fw, fh = int(u * 0.7), int(u * 2.0)
    fl, hd = int(u * 1.3), int(u * 0.5)
    a1 = ";animation:yPop 380ms %s both" % EASE_REVEAL if animate else ""
    a2 = (";animation:yGrowY 460ms %s 300ms both;transform-origin:bottom"
          % EASE_REVEAL if animate else "")
    a3 = ";animation:yFade 380ms ease 620ms both" if animate else ""
    a4 = ";animation:ySlide 520ms %s 860ms both" % EASE_REVEAL if animate else ""
    fig = ""
    if figure:
        fig = ('<div style="position:absolute;left:%dpx;bottom:0;width:%dpx;height:%dpx;'
               'background:%s;border-radius:%dpx %dpx 0 0%s"></div>'
               '<div style="position:absolute;left:%dpx;bottom:%dpx;width:%dpx;height:%dpx;'
               'border-radius:999px;background:%s%s"></div>'
               % (fl, fw, fh, shadow, int(u * .28), int(u * .28), a4,
                  fl + 1, fh, hd, hd, shadow, a4))
    return ('<div style="position:relative;width:%dpx;height:%dpx;box-sizing:border-box;'
            'border:%dpx solid %s;border-bottom:0;border-radius:%dpx %dpx 0 0;'
            'overflow:hidden;transform-origin:bottom%s">'
            '<div style="position:absolute;inset:0;background:%s%s"></div>'
            '<div style="position:absolute;left:%dpx;top:%dpx;width:%dpx;height:%dpx;'
            'border-radius:%dpx %dpx 0 0;background:%s%s"></div>%s</div>'
            % (int(width), h, stroke, outline, r, r, a1,
               light, a2, sx, sy, int(width), h, r, r, shadow, a3, fig))


# --- the overlays ----------------------------------------------------------
# Eight components, one to one with the Cyanotype canvas.

def hook(card: "dict", F: "dict") -> str:
    """1 · Hook — the only overlay allowed two lines of display type.

    Yellow lands on the SECOND line, never the first: the eye should read the
    setup before it reads the payoff word.
    """
    text = str(card.get("text", ""))
    lines = [l for l in text.split("\n") if l.strip()]
    if len(lines) == 1:
        # Break a single line near the middle so the accent has a second line
        # to land on, which is where the design puts it.
        words = lines[0].split()
        if len(words) > 3:
            cut = len(words) // 2
            lines = [" ".join(words[:cut]), " ".join(words[cut:])]
    size = _fit(lines[0] if lines else text,
                104 if not F["portrait"] else 92, budget=F["inner"])
    # Yellow belongs on the SECOND line by design — the eye should read the
    # setup before the payoff word. But if the emphasis only occurs on the
    # first line, marking nothing leaves the hook with no yellow at all,
    # which is worse than breaking the preference. So: prefer a later line,
    # fall back to whichever line actually contains the term.
    emph = card.get("emphasis") or []
    accent_on = None
    for idx in list(range(1, len(lines))) + [0]:
        if any(_e(w) and _e(w) in _e(lines[idx]) for w in emph):
            accent_on = idx
            break
    rows = []
    for i, line in enumerate(lines):
        marked = emphasize(line, emph) if i == accent_on else _e(line)
        rows.append('<div style="animation:yUp 340ms %s %dms both">%s</div>'
                    % (EASE_REVEAL, 120 + i * 120, marked))
    sub = ""
    if card.get("subtext"):
        sub = ('<div style="font-family:%s;font-size:34px;font-weight:600;color:%s;'
               'margin-top:24px;text-shadow:%s;animation:yFade 240ms ease 460ms both">%s</div>'
               % (FONT_DISPLAY, SLATE_300, SHADOW_CHALK, _e(card["subtext"])))
    return """%(scrim)s
<div style="position:absolute;left:%(left)dpx;top:%(top)dpx;right:%(right)dpx">
  %(eyebrow)s
  <div style="%(display)s;margin-top:22px">%(rows)s</div>
  %(sub)s
</div>""" % {"scrim": _scrim("lower") if F["portrait"] else "",
             "left": F["hook_left"], "top": 280 if not F["portrait"] else 420,
             "right": 300 if not F["portrait"] else F["side"],
             "eyebrow": _eyebrow(card.get("kicker", ""), CYAN, 0, 28, track=".24em"),
             "display": _display(size, "-.045em", lh="1.03"),
             "rows": "".join(rows), "sub": sub}


def lower_third(card: "dict", F: "dict") -> str:
    """2 · Lower third — a verified fact.

    The specimen name in `subtext` is the one place the serif appears on
    video, set italic, because it reads as a label off a museum case. The
    jokey name belongs in the eyebrow instead ("Verified · Slothzilla,
    officially") — never in the serif line.
    """
    text = card.get("text", "")
    size = _fit(text, 70 if not F["portrait"] else 62, lines=2,
                budget=1080 if not F["portrait"] else F["inner"])
    sub = ""
    if card.get("subtext"):
        italic = "font-style:italic;" if card.get("subtext_italic", True) else ""
        sub = ('<div style="height:2px;background:%s;margin-top:18px;transform-origin:left;'
               'animation:yGrow 320ms %s 300ms both"></div>'
               '<div style="font-family:%s;%sfont-size:34px;color:%s;margin-top:14px;'
               'text-shadow:%s;animation:yFade 240ms ease 400ms both">%s</div>'
               % (HAIRLINE, EASE_RULE, FONT_SERIF, italic, SLATE_300,
                  SHADOW_CHALK, _e(card["subtext"])))
    return """%(scrim)s
<div style="position:absolute;left:%(left)dpx;bottom:%(bottom)dpx;width:%(width)dpx">
  %(eyebrow)s
  <div style="%(display)s;margin-top:16px;animation:yUp 320ms %(ease)s 120ms both">%(text)s</div>
  %(sub)s
</div>""" % {"scrim": _scrim("lower"), "left": F["side"],
             "bottom": 200 if not F["portrait"] else F["bottom"] + 120,
             "width": 1080 if not F["portrait"] else F["inner"],
             "eyebrow": _eyebrow(card.get("kicker", ""), CYAN, 0, 26, track=".24em"),
             "display": _display(size), "ease": EASE_REVEAL,
             "text": emphasize(text, card.get("emphasis")), "sub": sub}


def caption_plate(card: "dict", F: "dict") -> str:
    """3 · Caption — words slide 100ms apart, one keyword scales up in yellow.

    Named `caption_plate` for continuity with older graphics plans. There is
    no plate: the speaker tag sits between two cyan rules and the words carry
    the chalk shadow. Bottom inset is fixed at 150px (320 vertical).
    """
    text = str(card.get("text", ""))
    words = card.get("words") or text.split()
    keys = [_no_emoji(k) for k in (card.get("emphasis") or [])]
    spans, marked = [], False
    for i, word in enumerate(words):
        delay = 100 + i * 100
        is_key = (not marked) and any(
            k and k.lower().strip(".,!?") == word.lower().strip(".,!?") for k in keys)
        if is_key:
            marked = True
            spans.append('<span style="font-size:86px;color:%s;'
                         'animation:yStretch 320ms %s %dms both">%s</span>'
                         % (YELLOW, EASE_REVEAL, delay, _e(word)))
        else:
            spans.append('<span style="animation:ySlide 180ms ease %dms both">%s</span>'
                         % (delay, _e(word)))
    return """%(scrim)s
<div style="position:absolute;left:0;right:0;bottom:%(bottom)dpx;display:flex;
            flex-direction:column;align-items:center;gap:16px">
  %(eyebrow)s
  <div style="font-family:%(display)s;font-size:64px;font-weight:800;letter-spacing:-.035em;
              color:%(chalk)s;display:flex;flex-wrap:wrap;gap:0 20px;justify-content:center;
              align-items:baseline;max-width:%(maxw)dpx;text-shadow:%(shadow)s">%(spans)s</div>
</div>""" % {"scrim": _scrim("lower"), "bottom": F["bottom"],
             "eyebrow": _eyebrow(card.get("speaker", ""), CYAN, 0, 26, centered=True),
             "display": FONT_DISPLAY, "chalk": CHALK, "maxw": F["inner"],
             "shadow": SHADOW_STRONG, "spans": "".join(spans)}


def stat(card: "dict", F: "dict") -> str:
    """4 · Stat — the number is the whole overlay.

    Numbers are honest: hedge in the label ("give or take"), never invent a
    percentage. Measurement ticks arrive last.
    """
    value = card.get("stat") or card.get("text", "")
    size = _fit(str(value), 230 if not F["portrait"] else 180,
                budget=F["inner"])
    label = ""
    if card.get("stat") and card.get("text"):
        label = ('<div style="font-family:%s;font-size:44px;font-weight:700;'
                 'letter-spacing:-.01em;color:%s;text-shadow:%s;'
                 'animation:yUp 300ms %s 380ms both">%s</div>'
                 % (FONT_DISPLAY, CHALK, SHADOW_CHALK, EASE_REVEAL, _e(card["text"])))
    return """%(scrim)s
<div style="position:absolute;inset:0;display:flex;flex-direction:column;
            align-items:center;justify-content:center;gap:8px">
  %(eyebrow)s
  <div style="font-family:%(display)s;font-size:%(size)dpx;line-height:1;font-weight:800;
              letter-spacing:-.06em;color:%(yellow)s;text-shadow:%(statshadow)s;
              animation:yStretch 420ms %(ease)s 160ms both">%(value)s</div>
  %(label)s
  %(ticks)s
</div>""" % {"scrim": _scrim("lower") if F["portrait"] else "",
             "eyebrow": _eyebrow(card.get("kicker", ""), CYAN, 0, 28,
                                 centered=True, track=".24em"),
             "display": FONT_DISPLAY, "size": size, "yellow": YELLOW,
             "statshadow": SHADOW_STAT, "ease": EASE_REVEAL,
             "value": _e(value), "label": label, "ticks": _ticks()}


def callout(card: "dict", F: "dict") -> str:
    """5 · Callout — a square frame with crop marks, not a circle.

    The leader line draws toward the label and stops level with the frame's
    centre. `x`/`y` are the frame's top-left in 1920x1080 space.
    """
    x = int(card.get("x", 1180))
    y = int(card.get("y", 400))
    bw, bh = int(card.get("size", 380)), 280
    mid = y + bh // 2
    lead_right = x - 20
    lead_left = max(F["side"] + 540, 700)
    marks = []
    for pos, w, h in (("left:-1px;top:-38px", 1, 32), ("left:-38px;top:-1px", 32, 1),
                      ("right:-1px;bottom:-38px", 1, 32), ("right:-38px;bottom:-1px", 32, 1)):
        marks.append('<div style="position:absolute;%s;width:%dpx;height:%dpx;'
                     'background:%s"></div>' % (pos, w, h, YELLOW))
    return """
<div style="position:absolute;left:%(x)dpx;top:%(y)dpx;width:%(bw)dpx;height:%(bh)dpx;
            animation:yPop 320ms %(ease)s 240ms both">
  <div style="position:absolute;inset:0;border:%(cw)dpx solid %(yellow)s"></div>%(marks)s
</div>
<div style="position:absolute;left:%(ll)dpx;top:%(mid)dpx;width:%(lw)dpx;height:3px;
            background:%(yellow)s;transform-origin:right;
            animation:yGrow 280ms %(easerule)s 420ms both"></div>
<div style="position:absolute;left:%(side)dpx;top:%(ly)dpx;width:540px;
            animation:yUp 300ms %(ease)s 540ms both">
  <div style="font-family:%(display)s;font-size:26px;font-weight:800;letter-spacing:.24em;
              text-transform:uppercase;color:%(yellow)s">%(kicker)s</div>
  <div style="%(headline)s;margin-top:12px">%(text)s</div>
</div>""" % {"x": x, "y": y, "bw": bw, "bh": bh, "cw": STROKE_CALLOUT,
             "yellow": YELLOW, "marks": "".join(marks), "ease": EASE_REVEAL,
             "easerule": EASE_RULE, "ll": lead_left,
             "lw": max(60, lead_right - lead_left), "mid": mid,
             "side": F["side"] + 30, "ly": mid - 74, "display": FONT_DISPLAY,
             "kicker": _caps(card.get("kicker", "Look here")),
             "headline": _display(_fit(card.get("text", ""), 62, lines=3, budget=540)),
             "text": _e(card.get("text", ""))}


def chapter(card: "dict", F: "dict") -> str:
    """6 · Chapter card — the progress meter doubles as the chapter marker.

    Nine squares, `active` of them lit, so the viewer always knows how much is
    left. Titles are two or three words; longer copy shrinks rather than wraps
    into the meter. Holds >= 2.5s (the validator enforces the duration).
    """
    text = card.get("text", "")
    size = _fit(text, 150 if not F["portrait"] else 110, lines=2,
                budget=F["inner"])
    active = int(card.get("active", 3) or 3)
    rooms = []
    for i in range(9):
        if i < active:
            rooms.append('<div style="width:20px;height:20px;background:%s;'
                         'animation:yDot 200ms ease %dms both"></div>'
                         % (YELLOW, 160 + i * 80))
        else:
            rooms.append('<div style="width:20px;height:20px;border:2px solid %s;'
                         'box-sizing:border-box"></div>' % HAIRLINE)
    sub = ""
    if card.get("subtext"):
        sub = ('<div style="font-family:%s;font-size:34px;font-weight:600;color:%s;'
               'animation:yFade 240ms ease 620ms both">%s</div>'
               % (FONT_DISPLAY, SLATE_300, _e(card["subtext"])))
    return """%(wash)s
<div style="position:absolute;left:%(left)dpx;top:0;bottom:0;right:%(side)dpx;display:flex;
            flex-direction:column;justify-content:center;gap:20px">
  <div style="display:flex;align-items:center;gap:20px;animation:yFade 240ms ease both">
    <div style="display:flex;gap:7px">%(rooms)s</div>
    <span style="font-family:%(display)s;font-size:26px;font-weight:800;letter-spacing:.24em;
                 text-transform:uppercase;color:%(cyan)s">%(kicker)s</span>
  </div>
  <div style="%(title)s;animation:yUp 400ms %(ease)s 200ms both">%(text)s</div>
  <div style="width:220px;height:3px;background:%(yellow)s;transform-origin:left;
              animation:yGrow 320ms %(easerule)s 520ms both"></div>
  %(sub)s
</div>""" % {"wash": _wash(WASH_CHAPTER), "left": F["chapter_left"],
             "side": F["side"], "rooms": "".join(rooms), "display": FONT_DISPLAY,
             "cyan": CYAN,
             "kicker": _caps(card.get("kicker") or "Room %d of nine" % active),
             "title": _display(size, "-.055em", lh="1"), "ease": EASE_REVEAL,
             "text": _e(text), "yellow": YELLOW, "easerule": EASE_RULE, "sub": sub}


def payoff(card: "dict", F: "dict") -> str:
    """7 · Quote — the one overlay set in the serif, italic.

    Reserved for the takeaway line, once per video. No accent word: this line
    is the whole point, so nothing competes with it.
    """
    text = card.get("text", "")
    size = _fit(text, 78 if not F["portrait"] else 66, lines=3,
                budget=F["inner"] - 140)
    attr = ""
    if card.get("attribution"):
        attr = ('<div style="font-family:%s;font-size:26px;font-weight:800;'
                'letter-spacing:.24em;text-transform:uppercase;color:%s;margin-top:20px;'
                'animation:yFade 240ms ease 560ms both">%s</div>'
                % (FONT_DISPLAY, CYAN, _caps(card["attribution"])))
    return """%(scrim)s
<div style="position:absolute;left:%(side)dpx;right:%(side)dpx;bottom:%(bottom)dpx;text-align:center">
  <div style="font-family:%(serif)s;font-size:%(size)dpx;line-height:1.14;font-weight:400;
              font-style:italic;letter-spacing:-.02em;color:%(chalk)s;
              text-shadow:0 4px 22px rgba(4,16,32,.9);
              animation:yUp 380ms %(ease)s both">&ldquo;%(text)s&rdquo;</div>
  <div style="width:180px;height:2px;background:%(yellow)s;margin:30px auto 0;
              transform-origin:center;animation:yGrow 320ms %(easerule)s 420ms both"></div>
  %(attr)s
</div>""" % {"scrim": _scrim("tall"), "side": 190 if not F["portrait"] else F["side"],
             "bottom": 200 if not F["portrait"] else F["bottom"] + 60,
             "serif": FONT_SERIF, "size": size, "chalk": CHALK,
             "ease": EASE_REVEAL, "text": _e(text), "yellow": YELLOW,
             "easerule": EASE_RULE, "attr": attr}


def watermark(card: "dict", F: "dict") -> str:
    """8 · Watermark — top right, and it never moves.

    Outline at 70% chalk, the light at full yellow so the mark still reads at
    phone size. The shadow inside the arch is cut out here, not filled, so
    footage shows through it.
    """
    u = 52 / 8.0
    mark = ('<div style="position:relative;width:52px;height:65px;box-sizing:border-box;'
            'border:%dpx solid rgba(234,244,255,.7);border-bottom:0;'
            'border-radius:26px 26px 0 0;overflow:hidden">'
            '<div style="position:absolute;left:0;right:17px;top:0;bottom:0;'
            'border-radius:26px 0 0 0;background:%s"></div>'
            '<div style="position:absolute;left:8px;bottom:0;width:5px;height:13px;'
            'background:%s;border-radius:2px 2px 0 0"></div></div>'
            % (STROKE, YELLOW, NAVY))
    return """
<div style="position:absolute;right:%(right)dpx;top:%(top)dpx;display:flex;align-items:center;
            gap:16px;opacity:.9;animation:yFade 300ms ease both">
  %(mark)s
  <div style="font-family:%(display)s;font-size:26px;font-weight:800;letter-spacing:.22em;
              text-transform:uppercase;color:rgba(234,244,255,.82)">Ninth Room</div>
</div>""" % {"right": 72 if not F["portrait"] else 48,
             "top": 64 if not F["portrait"] else 120,
             "mark": mark, "display": FONT_DISPLAY}


# --- engagement ------------------------------------------------------------
# Cards that hand the viewer a job. Every option is an outline; the answer is
# that outline flooding with yellow.

def _engagement_head(card: "dict", F: "dict", eyebrow_color: str,
                     default_eyebrow: str, top: int, q_size: int = 80) -> "tuple":
    """The shared eyebrow + question column every engagement card opens with.

    `top` is authored in 1920x1080 coordinates. In portrait it must never sit
    above the vertical safe inset, or the eyebrow renders underneath YouTube's
    Shorts chrome — the channel avatar and title sit in the top 180px, and a
    card there is simply not readable. quiz/true_false (130), countdown (150)
    and vote (170) all breached it before this clamp.
    """
    top = max(top, F["top"]) if F["portrait"] else top
    q = card.get("text", "")
    head = """
<div style="position:absolute;left:%(side)dpx;right:%(side)dpx;top:%(top)dpx;display:flex;
            flex-direction:column;align-items:center;gap:22px">
  %(eyebrow)s
  <div style="%(display)s;text-align:center">%(q)s</div>
""" % {"side": F["side"], "top": top,
       "eyebrow": _eyebrow(card.get("kicker") or default_eyebrow, eyebrow_color,
                           0, 26, centered=True),
       "display": _display(_fit(q, q_size, lines=2, budget=F["inner"]))
                  + ";animation:yUp 320ms %s 120ms both" % EASE_REVEAL,
       "q": _e(q)}
    return head, "</div>"


def quiz(card: "dict", F: "dict") -> str:
    """Quiz — at 2.5s the wrong options drop to 28% and yellow floods the answer.

    `rows` is a list of {"label": …, "correct": true}. Exactly one row should
    carry `correct`; if none does, nothing floods and the card reads as an
    open question, which is a legitimate use.
    """
    flood_at = int(card.get("reveal_ms", 2500))
    head, close = _engagement_head(card, F, CYAN, "One of these is true", 130)
    opts = []
    for i, r in enumerate(card.get("rows", [])):
        won = bool(r.get("correct"))
        opts.append(_outline_option(r.get("label", ""), 280 + i * 100, won=won,
                                    dim=0 if won else flood_at,
                                    flood_at=flood_at if won else 0))
    return head + ("""
  <div style="display:flex;flex-direction:column;gap:16px;width:%dpx;margin-top:10px">%s</div>
""" % (min(1200, F["inner"]), "".join(opts))) + close


def countdown(card: "dict", F: "dict") -> str:
    """Countdown — a hairline ring, three stacked numerals a second each.

    Cut on the frame the ring closes. The viewer is given a job here, which is
    the point of the whole engagement set.
    """
    head, close = _engagement_head(card, F, YELLOW, "Guess before we do", 150)
    nums = []
    for i, n in enumerate(("3", "2", "1")):
        anim = "yCountHold" if i == 2 else "yCount"
        nums.append('<span style="position:absolute;animation:%s 1s %s %dms both">%s</span>'
                    % (anim, EASE_REVEAL, 420 + i * 1000, n))
    sub = _e(card.get("subtext") or "Say it out loud. We\u2019ll wait.")
    return head + ("""
  <div style="position:relative;width:240px;height:240px;margin-top:10px;
              animation:yFade 240ms ease 280ms both">
    <div style="position:absolute;inset:0;border-radius:999px;border:6px solid rgba(234,244,255,.22)"></div>
    <div style="position:absolute;inset:0;border-radius:999px;border:6px solid transparent;
                border-top-color:%s;animation:yRing 3s linear 420ms both"></div>
    <div style="position:absolute;inset:0;display:flex;align-items:center;justify-content:center;
                font-family:%s;font-size:140px;font-weight:800;color:%s;text-shadow:%s">%s</div>
  </div>
  <div style="font-family:%s;font-size:32px;font-weight:700;color:%s;text-shadow:%s;
              animation:yFade 240ms ease 600ms both">%s</div>
""" % (YELLOW, FONT_DISPLAY, CHALK, SHADOW_CHALK, "".join(nums),
       FONT_DISPLAY, SLATE_300, SHADOW_CHALK, sub)) + close


def poll(card: "dict", F: "dict") -> str:
    """Poll — 6px rules, not pill bars. Losing bar in slate so yellow is alone.

    Real numbers only. `rows` is [{"label", "value"}] where value is a percent;
    the largest wins the yellow.
    """
    rows = card.get("rows", [])[:4]
    try:
        top = max(range(len(rows)),
                  key=lambda i: float(str(rows[i].get("value", "0")).rstrip("%") or 0))
    except (ValueError, TypeError):
        top = 0
    bars = []
    for i, r in enumerate(rows):
        won = i == top
        pct = str(r.get("value", "0")).rstrip("%")
        bars.append("""
  <div style="margin-top:%(mt)dpx;animation:yFade 220ms ease %(d)dms both">
    <div style="display:flex;justify-content:space-between;align-items:baseline;
                font-family:%(display)s;font-size:40px;font-weight:700;color:%(lc)s;
                text-shadow:%(shadow)s"><span>%(label)s</span>
      <span style="font-size:52px;font-weight:800;color:%(vc)s">%(pct)s%%</span></div>
    <div style="height:%(rule)dpx;background:rgba(234,244,255,.24);margin-top:14px;position:relative">
      <div style="position:absolute;inset:0;width:%(pct)s%%;background:%(bar)s;transform-origin:left;
                  animation:yGrow 700ms %(easerule)s %(bd)dms both"></div></div>
  </div>""" % {"mt": 40 if not i else 32, "d": 300 + i * 100,
               "display": FONT_DISPLAY, "lc": CHALK if won else SLATE_400,
               "shadow": SHADOW_CHALK, "label": _e(r.get("label", "")),
               "vc": YELLOW if won else SLATE_400, "pct": _e(pct),
               "rule": 6, "bar": YELLOW if won else SLATE_400,
               "easerule": EASE_RULE, "bd": 420 + i * 140})
    note = ""
    if card.get("subtext"):
        note = ('<div style="font-size:28px;color:%s;margin-top:32px;font-family:%s;'
                'text-shadow:%s;animation:yFade 240ms ease 900ms both">%s</div>'
                % (SLATE_400, FONT_DISPLAY, SHADOW_CHALK, _e(card["subtext"])))
    return """%(scrim)s
<div style="position:absolute;right:%(side)dpx;top:%(top)dpx;width:%(width)dpx;color:%(chalk)s">
  %(eyebrow)s
  <div style="%(display)s;margin-top:16px;animation:yUp 300ms %(ease)s 120ms both">%(q)s</div>
  %(bars)s
  %(note)s
</div>""" % {"scrim": _scrim("side" if not F["portrait"] else "lower"),
             "side": F["side"], "top": 230 if not F["portrait"] else 520,
             "width": 880 if not F["portrait"] else F["inner"], "chalk": CHALK,
             "eyebrow": _eyebrow(card.get("kicker") or "You picked", YELLOW, 0, 26),
             "display": _display(_fit(card.get("text", ""), 68, lines=2,
                                      budget=880)),
             "ease": EASE_REVEAL, "q": _e(card.get("text", "")),
             "bars": "".join(bars), "note": note}


def vote(card: "dict", F: "dict") -> str:
    """Vote — the winning side takes the yellow outline; only the digit ticks.

    `rows` is [{"label", "value"}]. The highest value wins. Nothing here is a
    filled box: an option is an outline, always.
    """
    rows = card.get("rows") or card.get("entries") or []
    def _val(r):
        try:
            return float(str(r.get("value", 0)))
        except (TypeError, ValueError):
            return 0.0
    # Exactly ONE winner, or none. The previous form OR-ed two independent
    # signals, so a `highlight` that disagreed with the numeric lead crowned
    # BOTH — two yellow outlines, which breaks the rule the whole identity
    # rests on. An explicit highlight is authoritative (it is a human saying
    # "this one"), and only the first is honoured; otherwise the numeric lead
    # wins, and a table of all-zeros has no winner at all.
    shown = rows[:4]
    explicit = [i for i, r in enumerate(shown) if r.get("highlight")]
    if explicit:
        winner = explicit[0]
    else:
        lead = max(range(len(shown)), key=lambda i: _val(shown[i])) if shown else -1
        winner = lead if lead >= 0 and _val(shown[lead]) > 0 else -1
    wins = [i == winner for i in range(len(shown))]
    # Three different answers is not a contest. With no winner, slate would
    # make every value the dimmest thing on screen — so the values stay chalk
    # and the eyebrow keeps the frame's one yellow moment.
    contested = any(wins)
    boxes = []
    for i, r in enumerate(rows[:4]):
        won = wins[i]
        boxes.append("""
    <div style="border:%(s)dpx solid %(bc)s;padding:20px 44px;text-align:center;
                animation:yUp 300ms %(ease)s %(d)dms both">
      <div style="font-family:%(display)s;font-size:34px;font-weight:%(fw)d;color:%(lc)s;
                  text-shadow:%(shadow)s">%(label)s</div>
      <div style="font-family:%(display)s;font-size:76px;font-weight:800;color:%(vc)s;
                  line-height:1.05;text-shadow:%(shadow)s%(tick)s">%(value)s</div>
    </div>""" % {"s": STROKE, "bc": YELLOW if won else INERT, "ease": EASE_REVEAL,
                 "d": 300 + i * 100, "display": FONT_DISPLAY,
                 "fw": 800 if won else 700,
                 "lc": YELLOW if won else (SLATE_300 if contested else CHALK),
                 "shadow": SHADOW_CHALK, "label": _e(r.get("label", "")),
                 "vc": CHALK if (won or not contested) else SLATE_500,
                 "tick": ";animation:yTick 460ms %s 1000ms both" % EASE_REVEAL if won else "",
                 "value": _e(r.get("value", ""))})
    head, close = _engagement_head(card, F, YELLOW, "Cast your vote", 170, q_size=76)
    return head + ('<div style="display:flex;gap:28px;margin-top:16px;flex-wrap:wrap;'
                   'justify-content:center">%s</div>' % "".join(boxes)) + close


def scoreboard(card: "dict", F: "dict") -> str:
    """Scoreboard — the vote card with a running tally. Same rules, more rows."""
    spec = dict(card)
    spec.setdefault("kicker", "Final count")
    spec["rows"] = card.get("entries") or card.get("rows") or []
    return vote(spec, F)


def true_false(card: "dict", F: "dict") -> str:
    """True or false — a two-option quiz. `answer` is "true" or "false"."""
    ans = str(card.get("answer", "")).lower()
    spec = dict(card)
    spec["rows"] = [{"label": "True", "correct": ans == "true"},
                    {"label": "False", "correct": ans == "false"}]
    spec.setdefault("kicker", "True or false")
    return quiz(spec, F)


def prediction(card: "dict", F: "dict") -> str:
    """Prediction — the question, then a held beat. No options, on purpose.

    The viewer says it out loud; the footage answers. Yellow sits on the
    eyebrow because there is no option for it to land on.
    """
    head, close = _engagement_head(card, F, YELLOW, "Call it now", 260)
    sub = _e(card.get("subtext") or "We\u2019ll find out in a second.")
    return head + ("""
  <div style="width:180px;height:3px;background:%s;margin-top:34px;transform-origin:center;
              animation:yGrow 320ms %s 420ms both"></div>
  <div style="font-family:%s;font-size:34px;font-weight:600;color:%s;margin-top:24px;
              text-shadow:%s;animation:yFade 240ms ease 600ms both">%s</div>
""" % (YELLOW, EASE_RULE, FONT_DISPLAY, SLATE_300, SHADOW_CHALK, sub)) + close


def this_that(card: "dict", F: "dict") -> str:
    """This or that — two outlined options, neither pre-won. The viewer picks."""
    spec = dict(card)
    spec.setdefault("kicker", "Pick one")
    spec["rows"] = [{"label": s.get("label", s.get("title", ""))}
                    for s in (card.get("sides") or card.get("rows") or [])[:2]]
    head, close = _engagement_head(spec, F, YELLOW, "Pick one", 200, q_size=76)
    opts = []
    for i, r in enumerate(spec["rows"]):
        opts.append(_outline_option(r.get("label", ""), 300 + i * 100, size=52))
    return head + ('<div style="display:flex;gap:28px;margin-top:24px">%s</div>'
                   % "".join(opts)) + close


def rank(card: "dict", F: "dict") -> str:
    """Rank — an ordered list. Only the top row is yellow."""
    rows = card.get("rows") or card.get("entries") or []
    items = []
    for i, r in enumerate(rows[:5]):
        won = i == 0
        items.append("""
    <div style="display:flex;align-items:baseline;gap:26px;margin-top:%(mt)dpx;
                animation:yUp 280ms %(ease)s %(d)dms both">
      <span style="font-family:%(display)s;font-size:44px;font-weight:800;color:%(nc)s;
                   width:64px;text-shadow:%(shadow)s">%(n)d</span>
      <span style="font-family:%(display)s;font-size:52px;font-weight:%(fw)d;color:%(lc)s;
                   text-shadow:%(shadow)s">%(label)s</span>
    </div>""" % {"mt": 0 if not i else 18, "ease": EASE_REVEAL, "d": 300 + i * 100,
                 "display": FONT_DISPLAY, "nc": YELLOW if won else SLATE_400,
                 "shadow": SHADOW_CHALK, "n": i + 1,
                 "fw": 800 if won else 700, "lc": CHALK if won else SLATE_400,
                 "label": _e(r.get("label", ""))})
    head, close = _engagement_head(card, F, CYAN, "In order", 190, q_size=72)
    return head + ('<div style="margin-top:26px;width:%dpx">%s</div>'
                   % (min(1100, F["inner"]), "".join(items))) + close


def scale(card: "dict", F: "dict") -> str:
    """Scale — a dimension bracket with a marker. `value` is 0-100."""
    try:
        pct = max(0.0, min(100.0, float(card.get("value", 50))))
    except (TypeError, ValueError):
        pct = 50.0
    ticks = "".join('<div style="width:2px;height:%dpx;background:rgba(234,244,255,%s)"></div>'
                    % (20 if i % 5 == 0 else 11, ".5" if i % 5 == 0 else ".28")
                    for i in range(21))
    head, close = _engagement_head(card, F, CYAN, "How weird is it", 200, q_size=72)
    lo = _e(card.get("low", "Normal"))
    hi = _e(card.get("high", "Very"))
    return head + ("""
  <div style="position:relative;width:%(w)dpx;margin-top:40px;animation:yFade 240ms ease 300ms both">
    <div style="display:flex;justify-content:space-between;align-items:flex-end;height:20px">%(ticks)s</div>
    <div style="height:3px;background:rgba(234,244,255,.4);margin-top:6px"></div>
    <div style="position:absolute;left:%(pct).1f%%;top:-26px;transform:translateX(-50%%);
                animation:yPop 380ms %(ease)s 620ms both">
      <div style="width:4px;height:64px;background:%(yellow)s;margin:0 auto"></div>
    </div>
    <div style="display:flex;justify-content:space-between;margin-top:22px;font-family:%(display)s;
                font-size:30px;font-weight:700;color:%(slate)s;text-shadow:%(shadow)s">
      <span>%(lo)s</span><span>%(hi)s</span></div>
  </div>
""" % {"w": min(1200, F["inner"]), "ticks": ticks, "pct": pct, "ease": EASE_REVEAL,
       "yellow": YELLOW, "display": FONT_DISPLAY, "slate": SLATE_400,
       "shadow": SHADOW_CHALK, "lo": lo, "hi": hi}) + close


def spot_it(card: "dict", F: "dict") -> str:
    """Spot it — the callout frame, empty, with a countdown eyebrow.

    The viewer hunts the frame before the reveal. Same crop-mark device as the
    callout, so it never reads as a different system.
    """
    spec = dict(card)
    spec.setdefault("kicker", "Spot it")
    spec.setdefault("text", card.get("text", "Find it before we point"))
    return callout(spec, F)


def verdict(card: "dict", F: "dict") -> str:
    """Verdict — lit doors out of five. The rating unit, never stars."""
    try:
        score = max(0, min(5, int(card.get("value", 4))))
    except (TypeError, ValueError):
        score = 4
    doors = []
    for i in range(5):
        lit = i < score
        doors.append('<div style="animation:yPop 300ms %s %dms both">%s</div>'
                     % (EASE_REVEAL, 300 + i * 100,
                        _arch(64, outline=YELLOW if lit else INERT,
                              light=YELLOW if lit else "transparent",
                              shadow=NAVY if lit else "transparent",
                              figure=False, stroke=STROKE)))
    head, close = _engagement_head(card, F, CYAN, "The verdict", 200, q_size=72)
    label = ""
    if card.get("subtext"):
        label = ('<div style="font-family:%s;font-size:34px;font-weight:600;color:%s;'
                 'margin-top:26px;text-shadow:%s;animation:yFade 240ms ease 800ms both">%s</div>'
                 % (FONT_DISPLAY, SLATE_300, SHADOW_CHALK, _e(card["subtext"])))
    return head + ('<div style="display:flex;gap:26px;margin-top:40px;align-items:flex-end">%s</div>%s'
                   % ("".join(doors), label)) + close


def streak(card: "dict", F: "dict") -> str:
    """Streak — the nine-room progress meter at full size, as its own beat."""
    spec = dict(card)
    spec.setdefault("kicker", "Where we are")
    return chapter(spec, F)


# --- transitions -----------------------------------------------------------

def transition(card: "dict", F: "dict") -> str:
    """The house cut. Four styles, all built from the same four shapes.

    `style`: rule (a bar sweeps and reveals), iris (crop marks close and open),
    grid (six cyan columns), push (a dimension bracket pushes the frame).
    A cut is never a plugin — it is the kit's own shapes, moving.
    """
    style = card.get("style", "rule")
    title = card.get("text", "")
    label = ""
    if title:
        label = """
<div style="position:absolute;left:%(left)dpx;top:0;bottom:0;display:flex;flex-direction:column;
            justify-content:center;gap:16px;animation:yColShow 540ms linear both">
  %(eyebrow)s
  <div style="%(display)s">%(title)s</div>
</div>""" % {"left": F["chapter_left"],
             "eyebrow": _eyebrow(card.get("kicker") or "Next", CYAN, 0, 26,
                                 track=".24em"),
             "display": _display(_fit(title, 120, lines=2, budget=F["inner"]),
                                 "-.055em", lh="1"),
             "title": _e(title)}
    if style == "iris":
        body = ('<div style="position:absolute;inset:0;background:%s;'
                'animation:yIris 620ms %s both"></div>' % (NAVY, EASE_RULE))
    elif style == "grid":
        cols = "".join(
            '<div style="flex:1;background:%s;transform-origin:bottom;'
            'animation:yColUp 540ms %s %dms both"></div>' % (NAVY, EASE_RULE, i * 40)
            for i in range(6))
        body = ('<div style="position:absolute;inset:0;display:flex;gap:6px">%s</div>'
                % cols)
    elif style == "push":
        body = ('<div style="position:absolute;inset:0;background:%s;'
                'animation:yPushIn 420ms %s both"></div>'
                '<div style="position:absolute;left:0;right:0;top:50%%;height:3px;background:%s;'
                'transform-origin:center;animation:yBracket 480ms %s both"></div>'
                % (NAVY, EASE_RULE, CYAN, EASE_RULE))
    else:
        body = ('<div style="position:absolute;inset:0;background:%s;'
                'animation:yReveal 480ms %s both"></div>'
                '<div style="position:absolute;top:0;bottom:0;width:6px;background:%s;'
                'animation:yRule 480ms %s both"></div>'
                % (NAVY, EASE_RULE, YELLOW, EASE_RULE))
    return body + label


# --- outro -----------------------------------------------------------------

def takeaway(card: "dict", F: "dict") -> str:
    """Outro beat 1 · takeaway, 2.4s. Serif italic, no accent word.

    This line is the whole point of the video, so nothing competes with it.
    """
    text = card.get("text", "")
    return """%(scrim)s
<div style="position:absolute;left:%(side)dpx;right:%(side)dpx;bottom:%(bottom)dpx;text-align:center">
  <div style="font-family:%(display)s;font-size:26px;font-weight:800;letter-spacing:.24em;
              text-transform:uppercase;color:%(cyan)s;animation:yFade 220ms ease both">%(kicker)s</div>
  <div style="font-family:%(serif)s;font-size:%(size)dpx;line-height:1.12;font-style:italic;
              letter-spacing:-.02em;color:%(chalk)s;margin-top:22px;
              text-shadow:0 4px 22px rgba(4,16,32,.9);
              animation:yUp 400ms %(ease)s 140ms both">%(text)s</div>
</div>""" % {"scrim": _scrim("tall"),
             "side": 170 if not F["portrait"] else F["side"],
             "bottom": 220 if not F["portrait"] else F["bottom"] + 80,
             "display": FONT_DISPLAY, "cyan": CYAN,
             "kicker": _caps(card.get("kicker") or "The takeaway"),
             "serif": FONT_SERIF,
             "size": _fit(text, 82 if not F["portrait"] else 68, lines=3,
                          budget=F["inner"] - 120),
             "chalk": CHALK, "ease": EASE_REVEAL, "text": _e(text)}


def next_room(card: "dict", F: "dict") -> str:
    """Outro beat 2 · next-video card, 3s.

    The subscribe box is an OUTLINE, never a filled button — the same rule as
    everything else in the kit.
    """
    title = card.get("text", "")
    cta = _caps(card.get("cta") or "Subscribe")
    sub = ""
    if card.get("subtext"):
        sub = ('<div style="font-family:%s;font-size:36px;font-weight:600;color:%s;'
               'text-shadow:%s;animation:yFade 240ms ease 480ms both">%s</div>'
               % (FONT_DISPLAY, SLATE_300, SHADOW_CHALK, _e(card["subtext"])))
    return """%(wash)s
<div style="position:absolute;left:%(left)dpx;right:%(side)dpx;top:0;bottom:0;display:flex;
            flex-direction:column;justify-content:center;gap:18px">
  %(eyebrow)s
  <div style="%(display)s;animation:yUp 400ms %(ease)s 160ms both">%(title)s</div>
  %(sub)s
  <div style="display:flex;align-items:center;gap:16px;margin-top:14px;
              animation:yFade 240ms ease 640ms both">
    <div style="border:%(s)dpx solid %(cyan)s;padding:12px 30px;font-family:%(font)s;
                font-size:30px;font-weight:800;letter-spacing:.16em;text-transform:uppercase;
                color:%(cyan)s">%(cta)s</div>
    <span style="font-family:%(font)s;font-size:28px;font-weight:600;color:%(slate)s;
                 text-shadow:%(shadow)s">one room a week</span>
  </div>
</div>""" % {"wash": _wash(WASH_TEASER), "left": F["chapter_left"],
             "side": F["side"],
             "eyebrow": _eyebrow(card.get("kicker") or "Next room", YELLOW, 0, 28,
                                 track=".24em"),
             "display": _display(_fit(title, 132 if not F["portrait"] else 100,
                                      lines=2, budget=F["inner"]),
                                 "-.055em", lh="1"),
             "ease": EASE_REVEAL, "title": _e(title), "sub": sub, "s": STROKE,
             "cyan": CYAN, "font": FONT_DISPLAY, "cta": cta, "slate": SLATE_300,
             "shadow": SHADOW_CHALK}


def outro(card: "dict", F: "dict") -> str:
    """Outro beat 3 · end plate, 3.5s hold.

    The payoff for the whole identity: the arch draws, light floods up the
    passage, then the figure walks to the threshold and stops. It is the last
    thing on screen, so it sits on flat navy, not on footage.
    """
    tagline = _caps(card.get("subtext") or "Nine rooms. One you can\u2019t find.")
    return """
<div style="position:absolute;inset:0;background:%(navy)s"></div>
<div style="position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;
            justify-content:center;gap:34px">
  <div style="position:relative;padding:26px">%(marks)s%(arch)s</div>
  <div style="font-family:%(serif)s;font-size:84px;line-height:1;letter-spacing:-.03em;
              font-weight:600;color:%(chalk)s;animation:yFade 300ms ease 1000ms both">The Ninth Room</div>
  <div style="display:flex;align-items:center;gap:14px;animation:yFade 260ms ease 1200ms both">
    <div style="width:40px;height:2px;background:%(cyan)s"></div>
    <span style="font-family:%(display)s;font-size:28px;font-weight:800;letter-spacing:.26em;
                 text-transform:uppercase;color:%(cyan)s">%(tagline)s</span>
    <div style="width:40px;height:2px;background:%(cyan)s"></div>
  </div>
</div>""" % {"navy": NAVY, "marks": _crop_marks(CYAN, 26, 900),
             "arch": _arch(200, animate=True), "serif": FONT_SERIF,
             "chalk": CHALK, "cyan": CYAN, "display": FONT_DISPLAY,
             "tagline": tagline}


# --- legacy screens, restyled ----------------------------------------------
# Kept so graphics plans written before the rebrand still render. Each one is
# now built from Cyanotype parts — no chips, no plates.

def stamp(card: "dict", F: "dict") -> str:
    """A stamp — an outlined yellow mark, tilted, that slams on.

    The Midnight kit filled this; the Cyanotype kit outlines it, because a
    filled badge is exactly the "template" look the brand rejects.
    """
    text = card.get("text", "")
    return """
<div style="position:absolute;left:0;right:0;top:0;bottom:0;display:flex;align-items:center;
            justify-content:center">
  <div style="border:%(s)dpx solid %(yellow)s;padding:22px 52px;transform:rotate(-7deg);
              animation:yPop 380ms %(ease)s both">
    <div style="font-family:%(display)s;font-size:%(size)dpx;font-weight:800;
                letter-spacing:.14em;text-transform:uppercase;color:%(yellow)s;
                text-shadow:%(shadow)s">%(text)s</div>
  </div>
</div>""" % {"s": STROKE_CALLOUT, "yellow": YELLOW, "ease": EASE_REVEAL,
             "display": FONT_DISPLAY,
             "size": _fit(text, 72, budget=1200),
             "shadow": SHADOW_CHALK, "text": _e(text)}


def reaction(card: "dict", F: "dict") -> str:
    """A reaction line — someone in the room said this. Chalk, cyan speaker tag.

    Emoji are stripped by `_e`, so a card whose whole text was emoji renders
    as its attribution alone. That is the correct failure: the brand does not
    put emoji on screen, and an empty line is easier to spot than a wrong one.
    """
    text = card.get("text", "")
    return """%(scrim)s
<div style="position:absolute;left:0;right:0;top:0;bottom:0;display:flex;flex-direction:column;
            align-items:center;justify-content:center;gap:20px">
  <div style="%(display)s;text-align:center;max-width:%(maxw)dpx;
              animation:yStretch 320ms %(ease)s both">%(text)s</div>
  %(attr)s
</div>""" % {"scrim": _scrim("lower"),
             "display": _display(_fit(text, 96, lines=2, budget=F["inner"])),
             "maxw": F["inner"], "ease": EASE_REVEAL, "text": _e(text),
             "attr": ('<div style="font-family:%s;font-size:26px;font-weight:800;'
                      'letter-spacing:.24em;text-transform:uppercase;color:%s;'
                      'animation:yFade 240ms ease 320ms both">%s</div>'
                      % (FONT_DISPLAY, CYAN, _caps(card["attribution"]))
                      ) if card.get("attribution") else ""}


def emoji_pop(card: "dict", F: "dict") -> str:
    """A burst of big emoji, popped in sequence over the footage.

    `emojis` is a list of {"char", optional "x"/"y" as 0-1 fractions of the
    frame}. Given none, positions fan across the middle third. Each one pops
    100ms after the last and carries the chalk drop-shadow so it reads on any
    footage.

    This is the one screen where emoji ARE the content, so the usual "they
    ride inside a language line" guidance does not apply.
    """
    items = card.get("emojis") or ([{"char": card.get("text", "")}]
                                   if card.get("text") else [])
    n = max(1, len(items))
    out = []
    for i, item in enumerate(items):
        char = item.get("char", "") if isinstance(item, dict) else str(item)
        if not char:
            continue
        fx = item.get("x") if isinstance(item, dict) else None
        fy = item.get("y") if isinstance(item, dict) else None
        x = float(fx) if fx is not None else (i + 1) / float(n + 1)
        y = float(fy) if fy is not None else (0.42 + (0.08 if i % 2 else -0.08))
        size = int(item.get("size", 260) if isinstance(item, dict) else 260)
        if F["portrait"]:
            size = int(size * 0.85)
        out.append('<div style="position:absolute;left:%.2f%%;top:%.2f%%;'
                   'transform:translate(-50%%,-50%%);font-size:%dpx;line-height:1;'
                   'filter:%s;animation:yPop 380ms %s %dms both">%s</div>'
                   % (x * 100, y * 100, size, EMOJI_SHADOW, EASE_REVEAL,
                      i * 100, html.escape(char)))
    return '<div style="position:absolute;inset:0">%s</div>' % "".join(out)


def compare(card: "dict", F: "dict") -> str:
    """Two images side by side on navy — the teaching compare.

    Images sit inside cyan crop-mark frames rather than rounded cards, so the
    screen belongs to the same system as the callout.
    """
    cols = []
    for i, side in enumerate(card.get("sides", [])[:2]):
        cols.append("""
      <div style="flex:1;animation:yUp 340ms %(ease)s %(delay)dms both">
        <div style="position:relative;padding:14px">%(marks)s
          <img src="file://%(src)s" alt="" style="display:block;width:100%%;height:330px;
               object-fit:cover;border:%(s)dpx solid %(border)s"></div>
        <div style="font-family:%(display)s;font-size:26px;font-weight:800;letter-spacing:.22em;
                    text-transform:uppercase;color:%(label_color)s;margin-top:18px">%(label)s</div>
        <div style="%(title_css)s;margin-top:6px">%(title)s</div>
        <div style="font-family:%(display)s;font-size:28px;font-weight:600;color:%(slate)s;
                    margin-top:8px">%(note)s</div>
      </div>""" % {"ease": EASE_REVEAL, "delay": 120 + i * 140,
                   "marks": _crop_marks(YELLOW if side.get("highlight") else CYAN,
                                        22, 120 + i * 140),
                   "src": side.get("image", ""), "s": STROKE,
                   "border": YELLOW if side.get("highlight") else INERT,
                   "display": FONT_DISPLAY,
                   "label_color": YELLOW if side.get("highlight") else CYAN,
                   "label": _caps(side.get("label", "")),
                   "title_css": _display(52, "-.03em"),
                   "title": _e(side.get("title", "")), "slate": SLATE_300,
                   "note": _e(side.get("note", ""))})
    return """
<div style="position:absolute;inset:0;background:%(navy)s;animation:yFade 240ms ease both"></div>
<div style="position:absolute;left:%(side)dpx;right:%(side)dpx;top:0;bottom:0;display:flex;
            flex-direction:column;justify-content:center">
  <div style="%(display)s;margin-bottom:34px;animation:yUp 380ms %(ease)s both">%(headline)s</div>
  <div style="display:flex;gap:44px;align-items:flex-start">%(cols)s</div>
</div>""" % {"navy": NAVY, "side": F["side"] + 30, "display": _display(64),
             "ease": EASE_REVEAL, "headline": _e(card.get("text", "")),
             "cols": "".join(cols)}


def flight_path(card: "dict", F: "dict") -> str:
    """A dashed trail draws across frame with a flier on it (episode kit)."""
    import sys
    from pathlib import Path
    assets = Path(__file__).resolve().parent.parent / "brand" / "design-system" / "overlay-assets"
    sys.path.insert(0, str(assets))
    import marks as _marks  # noqa: E402

    png = assets / "butterfly.png"
    flier = ('<img src="file://%s" alt="" style="width:110px;display:block">' % png
             if png.exists() else _marks.butterfly(110, CYAN))
    travel = int(card.get("travel_ms", 2200))
    return """
<style>
.flier{offset-path:path("M20 250C170 250 250 60 430 60S760 210 960 90");
       animation:fly %(travel)dms %(ease)s 120ms both}
@keyframes fly{from{offset-distance:0%%}to{offset-distance:100%%}}
@keyframes flapL{0%%,100%%{transform:rotateY(0deg)}50%%{transform:rotateY(58deg)}}
@keyframes flapR{0%%,100%%{transform:rotateY(0deg)}50%%{transform:rotateY(-58deg)}}
.flier .wing-l{animation:flapL 480ms ease-in-out infinite}
.flier .wing-r{animation:flapR 480ms ease-in-out infinite}
.trail{stroke-dashoffset:100;animation:yDraw %(travel)dms %(ease)s 120ms both}
</style>
<div style="position:absolute;left:420px;top:290px;width:1000px">%(arrow)s
  <div class="flier" style="position:absolute;left:0;top:0">%(fly)s</div>
</div>
%(scrim)s
<div style="position:absolute;left:%(side)dpx;bottom:%(bottom)dpx;width:1080px">
  %(eyebrow)s
  <div style="%(display)s;margin-top:16px;animation:yUp 320ms %(ease)s 160ms both">%(text)s</div>
</div>""" % {"travel": travel, "ease": EASE_REVEAL,
             "arrow": _marks.dashed_arrow(1000, CYAN), "fly": flier,
             "scrim": _scrim("lower"), "side": F["side"],
             "bottom": 200 if not F["portrait"] else F["bottom"] + 120,
             "eyebrow": _eyebrow(card.get("kicker", ""), CYAN, 0, 26, track=".24em"),
             "display": _display(_fit(card.get("text", ""), 70, lines=2, budget=1080)),
             "text": emphasize(card.get("text", ""), card.get("emphasis"))}


def contact(card: "dict", F: "dict") -> str:
    """A ring flash and drifting motes where something lands (episode kit)."""
    import random
    x = int(card.get("x", 1120))
    y = int(card.get("y", 560))
    rng = random.Random(card.get("id", "contact"))
    dots = []
    for i in range(7):
        size = rng.choice([14, 16, 22, 26, 26, 36])
        dx = x + 60 + rng.randint(0, 200)
        dy = y + 130 + rng.randint(0, 40)
        colour = CYAN if i % 3 else CHALK
        dots.append('<div style="position:absolute;left:%dpx;top:%dpx;width:%dpx;height:%dpx;'
                    'border-radius:999px;background:%s;opacity:.%d;'
                    'animation:yBurst %dms %s %dms both"></div>'
                    % (dx, dy, size, size, colour, rng.randint(7, 9),
                       900 + i * 30, EASE_REVEAL, 80 + i * 60))
    return """
<div style="position:absolute;inset:0">
  <div style="position:absolute;left:%(x)dpx;top:%(y)dpx;width:300px;height:300px;
              border:%(s)dpx solid %(cyan)s;border-radius:999px;
              animation:yPop 620ms %(ease)s both"></div>
  %(dots)s
</div>""" % {"x": x, "y": y, "s": STROKE_CALLOUT, "cyan": CYAN,
             "ease": EASE_REVEAL, "dots": "".join(dots)}


# --- registry --------------------------------------------------------------
# Every key an existing graphics_plan or Edit Room overlay may carry. Aliases
# are deliberate: `section` has always meant a lower third, `quote` a payoff.

RENDERERS = {
    # the eight overlays
    "hook": hook,
    "hook_title": hook,
    "lower_third": lower_third,
    "section": lower_third,
    "caption_plate": caption_plate,
    "stat": stat,
    "callout": callout,
    "chapter": chapter,
    "payoff": payoff,
    "quote": payoff,
    "watermark": watermark,
    # engagement
    "quiz": quiz,
    "countdown": countdown,
    "poll": poll,
    "vote": vote,
    "scoreboard": scoreboard,
    "true_false": true_false,
    "prediction": prediction,
    "this_that": this_that,
    "rank": rank,
    "scale": scale,
    "spot_it": spot_it,
    "verdict": verdict,
    "streak": streak,
    # transitions + outro
    "transition": transition,
    "takeaway": takeaway,
    "next_room": next_room,
    "outro": outro,
    "end_plate": outro,
    # legacy screens
    "stamp": stamp,
    "reaction": reaction,
    "emoji": emoji_pop,
    "compare": compare,
    "flight_path": flight_path,
    "contact": contact,
}


def overlay_html(card: "dict", w: int = 1920, h: int = 1080) -> str:
    """A full transparent page containing one overlay, ready to screenshot.

    The page is authored at true frame pixels (1920x1080, or 1080x1920 for a
    Short) and rendered at a device pixel ratio by `pipeline.animate`, so a 4K
    bake is this exact layout at four times the pixels.
    """
    kind = card.get("kit_type") or card.get("type", "lower_third")
    render = RENDERERS.get(kind)
    if render is None:
        raise ValueError("no kit renderer for type %r" % kind)
    return """<!doctype html><html><head><meta charset="utf-8">
<style>
*{margin:0;padding:0;box-sizing:border-box}
html,body{width:%(w)dpx;height:%(h)dpx;background:transparent}
%(keyframes)s
</style></head><body><div class="stage" style="position:relative;width:%(w)dpx;height:%(h)dpx;overflow:hidden">%(body)s</div></body></html>
""" % {"w": w, "h": h, "keyframes": KEYFRAMES, "body": render(card, _frame(w, h))}
