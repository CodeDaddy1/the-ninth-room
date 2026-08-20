"""The Ninth Room Overlay Kit v3 — overlays authored in Claude Design.

Source of truth: the design handoff bundle (README + `Locked Overlay
Structure.dc.html`) delivered 2026-08-19 — the approved "Cutout" chip
structure (direction 2b) in the approved Midnight palette (3c). This module
is the runtime version: same chip geometry, same keyframes, same stagger
timings, with the copy parameterised so the pipeline fills it per card.

The system in one paragraph: every line of type is its own CHIP — a
midnight-deep (or accent) box with a 5px ice outline, 12px radius, a hard
offset shadow (no blur), tilted ±1–2°, landing 140ms after the one before.
Chips shrink-wrap their text. Ice blue (#9DC6E8) means "this is true" —
facts, labels, measurements. Hot amber (#FFAE3B) means "this is a joke" —
votes, stamps, reactions, scoreboards. One accent per chip, never both.
Type on an accent is always midnight-deep.

Tilt note: the design files set a static `transform:rotate(…)` on chips AND
animate `transform` — in real CSS the animation's fill-mode would erase the
rest tilt. Here every keyframe carries `rotate(var(--tilt))` so chips land
and STAY on their tilt, which is what the mocks intend.

Renders through `pipeline.animate`, which seeks the CSS animations frame by
frame in headless Chrome, so the timings here are the timings on screen.

What breaks if this is wrong: overlays drift from the approved design (wrong
accent role, missing outline, blurred shadow), or text overflows its chip —
always render-test a card with real copy before shipping it.
"""
from __future__ import annotations

import html

# --- Midnight tokens (locked palette) --------------------------------------

MIDNIGHT = "#0F1826"        # brand base
DEEP = "#0B121C"            # chip and plate fill (>= .94 alpha over footage)
SURFACE = "#2C3E56"         # raised navy; unlit rooms in the mark on dark
ICE = "#E8EFF6"             # type on midnight; the outline on every chip
TRUE_BLUE = "#9DC6E8"       # means "this is true"
FUN = "#FFAE3B"             # means "this is a joke"
MUTED = "#5F7186"           # secondary type on dark
SUBTLE = "#93A2B2"          # secondary type inside a chip

SHADOW = "8px 8px 0 rgba(5,9,15,.6)"     # hard offset, no blur
SHADOW_SM = "7px 7px 0 rgba(5,9,15,.6)"
SHADOW_XS = "6px 6px 0 rgba(5,9,15,.5)"

FONT_DISPLAY = "'Bricolage Grotesque', 'Gabarito', sans-serif"
FONT_BODY = "Manrope, 'Helvetica Neue', sans-serif"
FONT_SERIF = "Newsreader, Georgia, serif"

EASE_OUT = "cubic-bezier(.16,1,.3,1)"
EASE_STD = "cubic-bezier(.22,.61,.36,1)"

# Legacy aliases so the v2 worked-example components (compare, flight_path,
# contact) keep rendering, now in Midnight colors.
ACCENT = FUN
INK = "rgba(11,18,28,.94)"
HAIRLINE = "rgba(232,239,246,.3)"
TEXT = ICE

KEYFRAMES = """
@keyframes lPop{0%{opacity:0;transform:scale(.76) rotate(var(--tilt,0deg))}62%{opacity:1;transform:scale(1.1) rotate(var(--tilt,0deg))}100%{opacity:1;transform:scale(1) rotate(var(--tilt,0deg))}}
@keyframes lPopT{0%{opacity:0;transform:scale(.76) rotate(-6deg)}62%{opacity:1;transform:scale(1.08) rotate(2deg)}100%{opacity:1;transform:scale(1) rotate(var(--tilt,-2deg))}}
@keyframes lFade{from{opacity:0}to{opacity:1}}
@keyframes lUp{from{opacity:0;transform:translateY(16px) rotate(var(--tilt,0deg))}to{opacity:1;transform:translateY(0) rotate(var(--tilt,0deg))}}
@keyframes lTick{0%{transform:translateY(0) scale(1)}36%{transform:translateY(-18px) scale(1.32)}100%{transform:translateY(0) scale(1)}}
@keyframes lSlam{0%{opacity:0;transform:rotate(-16deg) scale(2)}52%{opacity:1;transform:rotate(-5deg) scale(.93)}74%{transform:rotate(-9deg) scale(1.05)}100%{opacity:1;transform:rotate(-7deg) scale(1)}}
@keyframes lRule{from{transform:scaleX(0)}to{transform:scaleX(1)}}
@keyframes lWipeUp{from{clip-path:inset(105% 0 0 0)}to{clip-path:inset(0 0 0 0)}}
@keyframes lWob{0%,100%{transform:scale(1) rotate(0deg)}50%{transform:scale(1.05) rotate(3deg)}}
@keyframes bUp{from{opacity:0;transform:translateY(14px)}to{opacity:1;transform:translateY(0)}}
@keyframes bFade{from{opacity:0}to{opacity:1}}
@keyframes bWipeUp{from{clip-path:inset(105% 0 0 0)}to{clip-path:inset(0 0 0 0)}}
@keyframes bGrowX{from{transform:scaleX(0)}to{transform:scaleX(1)}}
@keyframes bPop{0%{opacity:0;transform:scale(.7)}60%{opacity:1;transform:scale(1.14)}100%{opacity:1;transform:scale(1)}}
@keyframes bBurst{0%{opacity:1;transform:translate(0,0) scale(1)}100%{opacity:0;transform:translate(0,-260px) scale(.3)}}
@keyframes bFlash{0%{opacity:0;transform:scale(.4)}30%{opacity:1;transform:scale(1.1)}100%{opacity:0;transform:scale(1.5)}}
@keyframes bSweepIn{from{transform:translateX(-105%)}to{transform:translateX(0)}}
@keyframes bSweepOut{from{transform:translateX(0)}to{transform:translateX(105%)}}
"""

KIT_TYPES = ("hook", "lower_third", "chapter", "scoreboard", "payoff",
             "caption_plate", "stamp", "stat", "vote", "reaction",
             "transition", "emoji", "watermark")


def _e(text: str) -> str:
    return html.escape(str(text))


def _accent(card: "dict", default: str) -> str:
    """Resolve the card's accent role: 'true' -> ice blue, 'fun' -> amber."""
    role = card.get("accent")
    if role == "true":
        return TRUE_BLUE
    if role == "fun":
        return FUN
    return default


def _chip(inner: str, fill: str = DEEP, color: str = ICE, tilt: float = -1.0,
          delay: int = 0, dur: int = 360, pill: bool = False,
          outline: str = "", shadow: str = SHADOW, pad: str = "10px 26px",
          radius: int = 12, anim: str = "lPop", extra: str = "") -> str:
    """One chip. The whole kit is this box."""
    return ('<div style="background:%s;color:%s;border:%s;border-radius:%s;'
            'padding:%s;box-shadow:%s;--tilt:%.1fdeg;'
            'transform:rotate(%.1fdeg);animation:%s %dms %s %dms both;%s">%s</div>'
            % (fill, color, outline or ("5px solid %s" % ICE),
               "999px" if pill else "%dpx" % radius, pad, shadow, tilt, tilt,
               anim, dur, EASE_OUT, delay, extra, inner))


def _kicker_pill(text: str, fill: str, delay: int = 0, size: int = 26,
                 shadow: str = SHADOW, tracking: str = ".18em") -> str:
    inner = ('<span style="font-family:%s;font-size:%dpx;font-weight:800;'
             'letter-spacing:%s;text-transform:uppercase">%s</span>'
             % (FONT_BODY, size, tracking, _e(text)))
    return _chip(inner, fill=fill, color=DEEP, tilt=-2, delay=delay, dur=340,
                 pill=True, shadow=shadow, pad="10px 28px", anim="lPopT")


def _mark(word: str) -> str:
    """The active/emphasized word sits on its own little amber chip."""
    return ('<span style="background:%s;color:%s;border-radius:8px;'
            'padding:0 12px">%s</span>' % (FUN, DEEP, _e(word)))


def emphasize(text: str, emphasis: "list[str]") -> str:
    out = _e(text)
    for word in emphasis or []:
        out = out.replace(_e(word), _mark(word))
    return out


def _display(size: int, tracking: str = "-.04em") -> str:
    return ("font-family:%s;font-size:%dpx;line-height:1;font-weight:800;"
            "letter-spacing:%s" % (FONT_DISPLAY, size, tracking))


# --- the twelve components -------------------------------------------------

def hook(card: "dict") -> str:
    """1 · Hook — kicker pill, title chips alternating ink/amber, subline.

    Pill at 0ms, title chips at 140/280ms, subline at 440ms. Hold 1.8s.
    """
    parts = [_kicker_pill(card.get("kicker", ""), FUN)]
    lines = [l for l in card.get("text", "").split("\n") if l.strip()]
    for i, line in enumerate(lines):
        amber = i % 2 == 1
        inner = '<span style="%s">%s</span>' % (
            _display(100), _e(line) if amber else emphasize(line, card.get("emphasis")))
        parts.append(_chip(inner, fill=FUN if amber else DEEP,
                           color=DEEP if amber else ICE,
                           tilt=1.5 if amber else -1.5, delay=140 + i * 140))
    if card.get("subtext"):
        inner = ('<span style="font-family:%s;font-size:30px;font-weight:600">%s</span>'
                 % (FONT_BODY, _e(card["subtext"])))
        parts.append(_chip(inner, color=SUBTLE, tilt=-1,
                           delay=140 + len(lines) * 140 + 20, dur=320,
                           outline="4px solid rgba(232,239,246,.6)",
                           shadow=SHADOW_XS, pad="8px 22px", radius=10))
    return ('<div style="position:absolute;left:130px;top:270px;display:flex;'
            'flex-direction:column;align-items:flex-start;gap:14px">%s</div>'
            % "".join(parts))


def chapter(card: "dict") -> str:
    """2 · Chapter card — full-frame scrim, rule, kicker, huge wiped title."""
    text = card.get("text", "")
    size = 150 if len(text) <= 12 else (112 if len(text) <= 22 else 84)
    sub = ""
    if card.get("subtext"):
        sub = ('<div style="font-family:%s;font-size:30px;color:%s;'
               'animation:lFade 240ms ease 480ms both">%s</div>'
               % (FONT_BODY, MUTED, _e(card["subtext"])))
    return """
<div style="position:absolute;inset:0;background:rgba(11,18,28,.84);animation:lFade 240ms ease both"></div>
<div style="position:absolute;left:130px;top:0;bottom:0;display:flex;flex-direction:column;justify-content:center;gap:18px;color:%(ice)s">
  <div style="display:flex;align-items:center;gap:16px">
    <div style="width:70px;height:3px;background:%(true)s;transform-origin:left;animation:lRule 260ms %(ease_std)s both"></div>
    <span style="font-family:%(body)s;font-size:22px;font-weight:800;letter-spacing:.18em;text-transform:uppercase;color:%(true)s;animation:lFade 220ms ease 80ms both">%(kicker)s</span>
  </div>
  <div style="%(display)s;overflow:hidden"><div style="animation:lWipeUp 420ms %(ease)s 160ms both">%(title)s</div></div>
  %(sub)s
</div>""" % {"ice": ICE, "true": TRUE_BLUE, "ease_std": EASE_STD,
             "body": FONT_BODY, "kicker": _e(card.get("kicker", "")),
             "display": _display(size, "-.055em"), "ease": EASE_OUT,
             "title": _e(text), "sub": sub}


def lower_third(card: "dict") -> str:
    """3 · Lower third — a verified fact: ice kicker pill, headline, detail.

    Bottom edge sits at y=800 so it clears the caption band and a person
    standing frame-right. Chips shrink-wrap; long names widen up to 1400px.
    """
    parts = [_kicker_pill(card.get("kicker", ""), _accent(card, TRUE_BLUE),
                          size=22, shadow=SHADOW_SM)]
    inner = ('<span style="%s">%s</span>'
             % (_display(58, "-.035em"),
                emphasize(card.get("text", ""), card.get("emphasis"))))
    parts.append(_chip(inner, tilt=1, delay=140, dur=340,
                       extra="max-width:1400px"))
    if card.get("subtext"):
        italic = "font-style:italic;" if card.get("subtext_italic", True) else ""
        inner = ('<span style="font-family:%s;font-size:28px;font-weight:600;%s">%s</span>'
                 % (FONT_BODY, italic, _e(card["subtext"])))
        parts.append(_chip(inner, color=SUBTLE, tilt=-1, delay=280, dur=320,
                           outline="4px solid rgba(232,239,246,.6)",
                           shadow=SHADOW_XS, pad="8px 22px", radius=10))
    return ('<div style="position:absolute;left:120px;bottom:280px;display:flex;'
            'flex-direction:column;align-items:flex-start;gap:12px">%s</div>'
            % "".join(parts))


def stat(card: "dict") -> str:
    """4 · Stat card — one big number, label on an ice chip below."""
    parts = []
    if card.get("kicker"):
        parts.append(_kicker_pill(card["kicker"], _accent(card, TRUE_BLUE), size=22,
                                  shadow=SHADOW_SM))
    inner = '<span style="%s">%s</span>' % (_display(180, "-.05em"),
                                            _e(card.get("stat", "")))
    parts.append(_chip(inner, tilt=1, delay=120, dur=380))
    if card.get("text"):
        inner = ('<span style="font-family:%s;font-size:34px;font-weight:700">%s</span>'
                 % (FONT_BODY, _e(card["text"])))
        parts.append(_chip(inner, fill=_accent(card, TRUE_BLUE), color=DEEP,
                           tilt=-1, delay=300, dur=340))
    return ('<div style="position:absolute;left:0;right:0;top:330px;display:flex;'
            'flex-direction:column;align-items:center;gap:16px">%s</div>'
            % "".join(parts))


def payoff(card: "dict") -> str:
    """5 · Quote / payoff — speaker pill above the quote chip."""
    parts = []
    if card.get("attribution"):
        parts.append(_kicker_pill(card["attribution"], FUN, size=22,
                                  shadow=SHADOW_SM))
    inner = ('<span style="%s;line-height:1.06;display:inline-block">%s</span>'
             % (_display(76), emphasize(card.get("text", ""), card.get("emphasis"))))
    parts.append(_chip(inner, tilt=1, delay=120, dur=340, anim="lUp",
                       extra="max-width:1500px;text-align:center"))
    return ('<div style="position:absolute;left:0;right:0;top:400px;display:flex;'
            'flex-direction:column;align-items:center;gap:16px">%s</div>'
            % "".join(parts))


def vote(card: "dict") -> str:
    """6 · Vote — amber kicker, question chip, option cards; digits tick."""
    parts = [_kicker_pill(card.get("kicker", ""), FUN)]
    if card.get("text"):
        inner = '<span style="%s">%s</span>' % (_display(76), _e(card["text"]))
        parts.append(_chip(inner, tilt=1, delay=140, pad="10px 28px"))
    opts = []
    for i, r in enumerate(card.get("rows", [])):
        win = r.get("highlight")
        tick = ("animation:lTick 460ms %s 1000ms both" % EASE_OUT) if win else ""
        opts.append(
            '<div style="background:%s;border:5px solid %s;border-radius:16px;'
            'padding:18px 36px;color:%s;text-align:center;box-shadow:%s;'
            '--tilt:%ddeg;transform:rotate(%ddeg);animation:lPop 340ms %s %dms both">'
            '<div style="font-family:%s;font-size:32px;font-weight:%d">%s</div>'
            '<div style="%s;font-size:68px;line-height:1.1;%s%s">%s</div></div>'
            % (FUN if win else DEEP,
               ICE if win else "rgba(232,239,246,.7)",
               DEEP if win else ICE, SHADOW,
               2 if win else -2, 2 if win else -2, EASE_OUT, 300 + i * 100,
               FONT_BODY, 800 if win else 700, _e(r.get("label", "")),
               _display(68, "-.04em"),
               "" if win else "color:%s;" % MUTED, tick,
               _e(r.get("value", ""))))
    parts.append('<div style="display:flex;gap:24px;margin-top:14px">%s</div>'
                 % "".join(opts))
    return ('<div style="position:absolute;left:0;right:0;top:150px;display:flex;'
            'flex-direction:column;align-items:center;gap:16px">%s</div>'
            % "".join(parts))


def scoreboard(card: "dict") -> str:
    """7 · Scoreboard — one big card; the winner row is its own amber chip."""
    rows = []
    for entry in card.get("entries", []):
        win = entry.get("highlight")
        row = ('<span>%s</span><span style="%s">%s</span>'
               % (_e(entry.get("label", "")),
                  ("animation:lTick 460ms %s 560ms both;display:inline-block" % EASE_OUT)
                  if win else "", _e(entry.get("value", ""))))
        if win:
            rows.append('<div style="background:%s;color:%s;border-radius:18px;'
                        'padding:6px 20px;display:flex;justify-content:space-between;'
                        'gap:40px;%s;font-size:52px;'
                        'animation:lPop 340ms %s 260ms both">%s</div>'
                        % (FUN, DEEP, _display(52, "-.03em"), EASE_OUT, row))
        else:
            rows.append('<div style="display:flex;justify-content:space-between;'
                        'gap:40px;padding:6px 20px;color:%s;%s;font-size:48px">%s</div>'
                        % (MUTED, _display(48, "-.03em"), row))
    return """
<div style="position:absolute;left:120px;top:130px;min-width:480px;background:%(deep)s;border:8px solid %(ice)s;border-radius:30px;padding:26px 30px;box-shadow:16px 16px 0 rgba(5,9,15,.6);--tilt:-1deg;transform:rotate(-1deg);animation:lPop 380ms %(ease)s both">
  <div style="font-family:%(body)s;font-size:24px;font-weight:800;letter-spacing:.18em;text-transform:uppercase;color:%(fun)s;margin-bottom:14px">%(kicker)s</div>
  <div style="display:flex;flex-direction:column;gap:8px">%(rows)s</div>
</div>""" % {"deep": DEEP, "ice": ICE, "ease": EASE_OUT, "body": FONT_BODY,
             "fun": FUN, "kicker": _e(card.get("kicker", "")),
             "rows": "".join(rows)}


def stamp(card: "dict") -> str:
    """8 · Stamp — slammed amber verdict, rests at −7°."""
    inner = '<span style="%s">%s</span>' % (_display(88, "-.04em"),
                                            _e(card.get("text", "")))
    return ('<div style="position:absolute;left:0;right:0;top:330px;display:flex;'
            'justify-content:center">'
            '<div style="background:%s;color:%s;border:9px solid %s;'
            'border-radius:26px;padding:22px 52px;'
            'box-shadow:14px 14px 0 rgba(5,9,15,.6);'
            'animation:lSlam 520ms %s both">%s</div></div>'
            % (FUN, DEEP, ICE, EASE_OUT, inner))


def reaction(card: "dict") -> str:
    """9 · Reaction pop — words blown up on amber chips for one beat."""
    lines = [l for l in card.get("text", "").split("\n") if l.strip()]
    size = 150 if max((len(l) for l in lines), default=0) <= 10 else 108
    parts = []
    for i, line in enumerate(lines):
        inner = '<span style="%s">%s</span>' % (_display(size, "-.05em"), _e(line))
        parts.append(_chip(inner, fill=FUN, color=DEEP, tilt=-2 if i % 2 == 0 else 2,
                           delay=i * 140, dur=380, anim="lPopT",
                           pad="14px 36px", radius=18))
    if card.get("attribution"):
        parts.append(_kicker_pill(card["attribution"], TRUE_BLUE, size=22,
                                  delay=len(lines) * 140 + 80, shadow=SHADOW_SM))
    return ('<div style="position:absolute;left:0;right:0;top:380px;display:flex;'
            'flex-direction:column;align-items:center;gap:16px">%s</div>'
            % "".join(parts))


def emoji_pop(card: "dict") -> str:
    """10 · Big emoji moment — 260px on the mandatory dark radial disc.

    Only for beats with no caption on screen (policy 2026-08-19: an emoji
    rides inside captions whenever one is up). Pop 360ms, then a 2.4s
    ease-in-out wobble. 1–3 emoji max: a punchline mark, not confetti.
    """
    spans = []
    n = len(card.get("emojis", []))
    for i, e in enumerate(card.get("emojis", [])):
        size = int(e.get("size", 260))
        disc = size + int(size * 0.30)
        x = int(e.get("x", 960 - (n * disc + (n - 1) * 40) // 2 + i * (disc + 40)))
        y = int(e.get("y", 540 - disc // 2))
        delay = int(e.get("delay_ms", i * 120))
        spans.append(
            '<div style="position:absolute;left:%dpx;top:%dpx;width:%dpx;height:%dpx;'
            'border-radius:50%%;'
            'background:radial-gradient(circle, rgba(11,18,28,.96) 55%%, rgba(11,18,28,0) 100%%);'
            'display:flex;align-items:center;justify-content:center;'
            'font-size:%dpx;font-family:\'Apple Color Emoji\',sans-serif;line-height:1;'
            'animation:lPop 360ms %s %dms both, lWob 2.4s ease-in-out %dms infinite">%s</div>'
            % (x, y, disc, disc, size, EASE_OUT, delay, delay + 360,
               _e(e.get("char", "😱"))))
    return "".join(spans)


def caption_plate(card: "dict") -> str:
    """11 · Caption look, single phrase (the live captions render in Pillow —
    pipeline/captions.py — and must match this exactly)."""
    words = card.get("words") or [card.get("text", "")]
    active = card.get("active", 0)
    spans = []
    for i, w in enumerate(words):
        spans.append(_mark(w) if i == active else
                     "<span>%s</span>" % _e(w))
    speaker = ""
    if card.get("speaker"):
        speaker = _kicker_pill(card["speaker"], FUN, size=22, shadow=SHADOW_XS,
                               tracking=".2em")
    return """
<div style="position:absolute;left:0;right:0;bottom:120px;display:flex;flex-direction:column;align-items:center;gap:10px">
  %(speaker)s
  <div style="background:rgba(11,18,28,.94);border:5px solid %(ice)s;border-radius:14px;padding:16px 30px;box-shadow:%(shadow)s;animation:lUp 180ms %(ease_std)s 120ms both">
    <div style="%(display)s;color:%(ice)s;display:flex;flex-wrap:wrap;gap:0 14px;justify-content:center;align-items:center">%(spans)s</div>
  </div>
</div>""" % {"speaker": speaker, "ice": ICE, "shadow": SHADOW,
             "ease_std": EASE_STD, "display": _display(56, "-.03em"),
             "spans": " ".join(spans)}


def watermark(card: "dict") -> str:
    """The mark, top-left over footage: eight ice rooms, the ninth amber,
    on a small deep plate (the mark never sits on bare footage)."""
    px = int(card.get("size", 58))
    gap = max(round(px / 20), 2)
    room = (px - 2 * gap) / 3.0
    cells = []
    for i in range(9):
        cells.append('<div style="width:%.1fpx;height:%.1fpx;background:%s"></div>'
                     % (room, room, FUN if i == 8 else ICE))
    return ('<div style="position:absolute;left:120px;top:70px;'
            'background:rgba(11,18,28,.94);border-radius:8px;padding:8px;'
            'animation:lFade 240ms ease both">'
            '<div style="display:grid;grid-template-columns:repeat(3,1fr);'
            'gap:%dpx;width:%dpx;height:%dpx">%s</div></div>'
            % (gap, px, px, "".join(cells)))


def outro(card: "dict") -> str:
    """13 · Outro end card — the brand sign-off that owns the whole frame.

    Near-solid midnight cover, centered column: the 3x3 mark builds room by
    room with the ninth lighting amber last, "The Ninth Room" wordmark in
    Newsreader under it, a TRUE kicker pill, the editable sign-off chip,
    and an amber CTA pill that slams in at the end. Every element persists
    (fill both) so the card can hold as long as the edit needs.
    """
    px, gap = 132, 6
    room = (px - 2 * gap) / 3.0
    cells = []
    for i in range(9):
        if i == 8:
            a = "lPop 340ms %s 620ms both" % EASE_OUT
        else:
            a = "lFade 240ms ease %dms both" % (80 + i * 45)
        cells.append('<div style="width:%.1fpx;height:%.1fpx;background:%s;'
                     'animation:%s"></div>'
                     % (room, room, FUN if i == 8 else ICE, a))
    parts = [
        '<div style="display:grid;grid-template-columns:repeat(3,1fr);'
        'gap:%dpx;width:%dpx;height:%dpx">%s</div>'
        % (gap, px, px, "".join(cells)),
        '<div style="font-family:%s;font-size:58px;font-weight:600;color:%s;'
        'letter-spacing:.01em;margin-top:30px;'
        'animation:lFade 300ms ease 340ms both">The Ninth Room</div>'
        % (FONT_SERIF, ICE),
    ]
    if card.get("kicker"):
        parts.append('<div style="margin-top:30px">%s</div>'
                     % _kicker_pill(card["kicker"], TRUE_BLUE, delay=560,
                                    size=22, shadow=SHADOW_SM))
    if card.get("text"):
        inner = ('<span style="%s">%s</span>'
                 % (_display(64, "-.035em"),
                    emphasize(card["text"], card.get("emphasis"))))
        parts.append('<div style="margin-top:14px">%s</div>'
                     % _chip(inner, tilt=1, delay=740, dur=340,
                             extra="max-width:1500px"))
    if card.get("subtext"):
        parts.append('<div style="font-family:%s;font-size:26px;color:%s;'
                     'margin-top:10px;animation:lFade 260ms ease 940ms both">'
                     '%s</div>' % (FONT_BODY, MUTED, _e(card["subtext"])))
    if card.get("cta"):
        inner = ('<span style="font-family:%s;font-size:30px;font-weight:800;'
                 'letter-spacing:.14em;text-transform:uppercase">%s</span>'
                 % (FONT_BODY, _e(card["cta"])))
        parts.append('<div style="margin-top:26px">%s</div>'
                     % _chip(inner, fill=FUN, color=DEEP, delay=1080, dur=420,
                             pad="12px 34px", pill=True, anim="lSlam",
                             outline="5px solid %s" % ICE))
    return ('<div style="position:absolute;inset:0;background:rgba(11,18,28,.97);'
            'animation:lFade 300ms ease both"></div>'
            '<div style="position:absolute;inset:0;display:flex;'
            'flex-direction:column;align-items:center;justify-content:center">'
            '%s</div>' % "".join(parts))


def transition(card: "dict") -> str:
    """A midnight panel that sweeps across a chapter cut, carrying the title.

    Hard cuts between chapters read as abrupt; Resolve's API cannot add a
    dissolve, so the transition is drawn: the panel wipes in over the
    outgoing shot, the title chip pops, and it wipes off the incoming one.
    Minimum hold 2.5s (Caleb, 2026-08-19).
    """
    total = int(float(card.get("duration", 2.5)) * 1000)
    sweep = 380
    hold = max(total - 2 * sweep, 200)
    kicker = _kicker_pill(card.get("kicker", ""), TRUE_BLUE, size=22,
                          delay=sweep, shadow=SHADOW_SM)
    inner = '<span style="%s">%s</span>' % (_display(104, "-.05em"),
                                            _e(card.get("text", "")))
    title = _chip(inner, tilt=1, delay=sweep + 80, dur=380)
    return """
<div style="position:absolute;inset:0;overflow:hidden">
  <div style="position:absolute;inset:0;background:linear-gradient(100deg,
              rgba(11,18,28,.9) 0%%, rgba(15,24,38,.82) 45%%,
              rgba(157,198,232,.12) 52%%, rgba(15,24,38,.82) 59%%,
              rgba(11,18,28,.9) 100%%);
              animation:bSweepIn %(sweep)dms %(ease)s both,
                        bSweepOut %(sweep)dms %(ease_std)s %(out)dms both">
    <div style="position:absolute;left:130px;top:0;bottom:0;display:flex;flex-direction:column;
                justify-content:center;align-items:flex-start;gap:16px">
      %(kicker)s
      %(title)s
    </div>
  </div>
</div>""" % {"sweep": sweep, "ease": EASE_OUT, "ease_std": EASE_STD,
             "out": sweep + hold, "kicker": kicker, "title": title}


# --- v2 worked-example components, kept and recolored ----------------------

def compare(card: "dict") -> str:
    """Full-frame teaching compare — two images side by side on midnight."""
    cols = []
    for i, side in enumerate(card.get("sides", [])[:2]):
        cols.append("""
      <div style="flex:1;animation:bUp 340ms %(ease)s %(delay)dms both">
        <img src="file://%(src)s" alt="" style="display:block;width:100%%;height:330px;
             object-fit:cover;border-radius:12px;border:5px solid %(ice)s;
             box-shadow:%(shadow)s">
        <div style="font-family:%(body)s;font-size:20px;font-weight:800;letter-spacing:.18em;text-transform:uppercase;
                    color:%(label_color)s;margin-top:18px">%(label)s</div>
        <div style="%(display)s;margin-top:6px">%(title)s</div>
        <div style="font-family:%(body)s;font-size:24px;color:%(muted)s;margin-top:8px">%(note)s</div>
      </div>""" % {"ease": EASE_OUT, "delay": 120 + i * 140,
                   "src": side.get("image", ""), "ice": ICE, "shadow": SHADOW,
                   "body": FONT_BODY,
                   "label_color": TRUE_BLUE if side.get("highlight") else MUTED,
                   "label": _e(side.get("label", "")),
                   "display": _display(52, "-.03em"),
                   "title": _e(side.get("title", "")), "muted": MUTED,
                   "note": _e(side.get("note", ""))})
    return """
<div style="position:absolute;inset:0;background:%(midnight)s;animation:bFade 240ms ease both"></div>
<div style="position:absolute;left:150px;right:150px;top:0;bottom:0;display:flex;
            flex-direction:column;justify-content:center;color:%(ice)s">
  <div style="%(display)s;margin-bottom:34px;overflow:hidden">
    <div style="animation:bWipeUp 380ms %(ease)s both">%(headline)s</div>
  </div>
  <div style="display:flex;gap:44px;align-items:flex-start">%(cols)s</div>
</div>""" % {"midnight": MIDNIGHT, "ice": ICE, "ease": EASE_OUT,
             "display": _display(64, "-.04em"),
             "headline": _e(card.get("text", "")), "cols": "".join(cols)}


def flight_path(card: "dict") -> str:
    """Dashed trail draws across frame with a butterfly on it (episode kit)."""
    import sys
    from pathlib import Path
    assets = Path(__file__).resolve().parent.parent / "brand" / "design-system" / "overlay-assets"
    sys.path.insert(0, str(assets))
    import marks  # noqa: E402

    png = assets / "butterfly.png"
    flier = ('<img src="file://%s" alt="" style="width:110px;display:block">' % png
             if png.exists() else marks.butterfly(110, TRUE_BLUE))

    travel = card.get("travel_ms", 2200)
    kicker = _kicker_pill(card.get("kicker", ""), TRUE_BLUE, size=22,
                          shadow=SHADOW_SM)
    inner = '<span style="%s">%s</span>' % (_display(76), _e(card.get("text", "")))
    title = _chip(inner, tilt=1, delay=160, dur=360)
    return """
<style>
.trail{stroke-dashoffset:100;animation:draw %(travel)dms %(ease)s 120ms both}
@keyframes draw{to{stroke-dashoffset:0}}
@keyframes fly{from{offset-distance:0%%}to{offset-distance:100%%}}
@keyframes flapL{0%%,100%%{transform:rotateY(0deg)}50%%{transform:rotateY(58deg)}}
@keyframes flapR{0%%,100%%{transform:rotateY(0deg)}50%%{transform:rotateY(-58deg)}}
.flier .wing-l{animation:flapL 480ms ease-in-out infinite}
.flier .wing-r{animation:flapR 480ms ease-in-out infinite}
.flier{offset-path:path("M20 250C170 250 250 60 430 60S760 210 960 90");
       animation:fly %(travel)dms %(ease)s 120ms both}
</style>
<div style="position:absolute;left:420px;top:290px;width:1000px">%(arrow)s
  <div class="flier" style="position:absolute;left:0;top:0">%(fly)s</div>
</div>
<div style="position:absolute;left:130px;bottom:150px;display:flex;flex-direction:column;
            align-items:flex-start;gap:12px">
  %(kicker)s
  %(title)s
</div>""" % {"travel": travel, "ease": EASE_OUT,
             "arrow": marks.dashed_arrow(1000, TRUE_BLUE),
             "fly": flier, "kicker": kicker, "title": title}


def contact(card: "dict") -> str:
    """A ring flash and drifting dots where something lands (episode kit)."""
    import random
    x = int(card.get("x", 1120))
    y = int(card.get("y", 560))
    rng = random.Random(card.get("id", "contact"))
    dots = []
    for i in range(7):
        size = rng.choice([14, 16, 22, 26, 26, 36])
        dx = x + 60 + rng.randint(0, 200)
        dy = y + 130 + rng.randint(0, 40)
        colour = TRUE_BLUE if i % 3 else ICE
        dots.append('<div style="position:absolute;left:%dpx;top:%dpx;width:%dpx;height:%dpx;'
                    'border-radius:999px;background:%s;opacity:.%d;'
                    'animation:bBurst %dms %s %dms both"></div>'
                    % (dx, dy, size, size, colour, rng.randint(7, 9),
                       900 + i * 30, EASE_OUT, 80 + i * 60))
    return """
<div style="position:absolute;inset:0">
  <div style="position:absolute;left:%(x)dpx;top:%(y)dpx;width:300px;height:300px;
              border:4px solid %(true)s;border-radius:999px;
              animation:bFlash 620ms ease-out both"></div>
  %(dots)s
</div>""" % {"x": x, "y": y, "true": TRUE_BLUE, "dots": "".join(dots)}


RENDERERS = {
    "hook": hook,
    "compare": compare,
    "flight_path": flight_path,
    "contact": contact,
    "reaction": reaction,
    "vote": vote,
    "transition": transition,
    "emoji": emoji_pop,
    "hook_title": hook,          # aliases so existing graphics plans keep working
    "lower_third": lower_third,
    "section": lower_third,
    "chapter": chapter,
    "scoreboard": scoreboard,
    "stat": stat,
    "payoff": payoff,
    "quote": payoff,
    "outro": outro,
    "stamp": stamp,
    "caption_plate": caption_plate,
    "watermark": watermark,
}


def overlay_html(card: "dict", w: int = 1920, h: int = 1080) -> str:
    """A full transparent page containing one overlay, ready to screenshot."""
    kind = card.get("kit_type") or card.get("type", "lower_third")
    render = RENDERERS.get(kind)
    if render is None:
        raise ValueError("no kit renderer for type %r" % kind)
    return """<!doctype html><html><head><meta charset="utf-8">
<style>
*{margin:0;padding:0;box-sizing:border-box}
html,body{width:%(w)dpx;height:%(h)dpx;background:transparent}
%(keyframes)s
</style></head><body><div class="stage" style="position:relative;width:%(w)dpx;height:%(h)dpx">%(body)s</div></body></html>
""" % {"w": w, "h": h, "keyframes": KEYFRAMES, "body": render(card)}
