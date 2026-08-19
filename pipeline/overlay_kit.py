"""The HMNS Overlay Kit v2 — overlays authored in Claude Design, rendered here.

Source of truth: the "YouTube text overlay project" canvas on claude.ai/design
(`HMNS Overlay Kit v2.dc.html`). That file is a *design document*: each screen
shows one overlay on a 1920×1080 stage plus a spec panel describing its
timing. This module is the runtime version of that document — same markup,
same CSS keyframes, same easing and delays, with the copy parameterised so
the pipeline can fill it per card.

Why re-implement rather than render the .dc.html directly: the canvas file is
wrapped in the Claude Design runtime (`support.js`, `<x-dc>`, `<sc-if>`,
replay buttons) and lays every screen out side by side with explanatory
panels. We need one overlay alone on a transparent 1920×1080 canvas. The
markup inside each `<sc-if>` is what matters, and that is what lives below.

Design language (from the kit, deliberately different from the older cards):
  accent  #12B76A green, ink #09090B at 82%, text #FCFCFA, muted #9A9A94
  type    Gabarito (display, 800 weight, tight negative tracking) + Manrope
  motion  per-line wipe-up staggered ~100ms, blur-in reveals, grow-x rules,
          pop/tick for numbers — all on cubic-bezier(.16,1,.3,1)

Renders through `pipeline.animate`, which seeks the CSS animation frame by
frame in headless Chrome, so the timings here are the timings on screen.

What breaks if this is wrong: overlays drift from the approved design (wrong
accent, wrong easing), or text overflows its plate — always render-test a card
with real copy before shipping it.
"""
from __future__ import annotations

import html

# --- kit tokens -----------------------------------------------------------

ACCENT = "#12B76A"
INK = "rgba(9,9,11,.82)"
HAIRLINE = "rgba(252,252,250,.14)"
TEXT = "#FCFCFA"
MUTED = "#9A9A94"

FONT_DISPLAY = "Gabarito, 'Helvetica Neue', sans-serif"
FONT_BODY = "Manrope, 'Helvetica Neue', sans-serif"

EASE_OUT = "cubic-bezier(.16,1,.3,1)"
EASE_STD = "cubic-bezier(.22,.61,.36,1)"

# Every keyframe the kit defines, copied verbatim so motion matches the canvas.
KEYFRAMES = """
@keyframes bUp{from{opacity:0;transform:translateY(14px)}to{opacity:1;transform:translateY(0)}}
@keyframes bDown{from{opacity:0;transform:translateY(-10px)}to{opacity:1;transform:translateY(0)}}
@keyframes bFade{from{opacity:0}to{opacity:1}}
@keyframes bBlur{from{opacity:0;filter:blur(7px)}to{opacity:1;filter:blur(0)}}
@keyframes bWipeUp{from{clip-path:inset(105% 0 0 0)}to{clip-path:inset(0 0 0 0)}}
@keyframes bWipeR{from{clip-path:inset(0 100% 0 0)}to{clip-path:inset(0 0 0 0)}}
@keyframes bGrowX{from{transform:scaleX(0)}to{transform:scaleX(1)}}
@keyframes bRing{from{opacity:0;transform:scale(1.4)}to{opacity:1;transform:scale(1)}}
@keyframes bPlate{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:translateY(0)}}
@keyframes bPop{0%{opacity:0;transform:scale(.7)}60%{opacity:1;transform:scale(1.14)}100%{opacity:1;transform:scale(1)}}
@keyframes bTick{0%{transform:translateY(0) scale(1)}35%{transform:translateY(-16px) scale(1.3)}100%{transform:translateY(0) scale(1)}}
@keyframes bStamp{0%{opacity:0;transform:rotate(-14deg) scale(1.9)}55%{opacity:1;transform:rotate(-4deg) scale(.94)}75%{transform:rotate(-8deg) scale(1.04)}100%{opacity:1;transform:rotate(-6deg) scale(1)}}
@keyframes bBurst{0%{opacity:1;transform:translate(0,0) scale(1)}100%{opacity:0;transform:translate(0,-260px) scale(.3)}}
@keyframes bFlash{0%{opacity:0;transform:scale(.4)}30%{opacity:1;transform:scale(1.1)}100%{opacity:0;transform:scale(1.5)}}
@keyframes bWobble{0%{opacity:0;transform:rotate(-7deg) scale(.8)}45%{opacity:1;transform:rotate(4deg) scale(1.08)}70%{transform:rotate(-2deg) scale(.98)}100%{opacity:1;transform:rotate(-2deg) scale(1)}}
@keyframes bBar{from{transform:scaleX(0)}to{transform:scaleX(1)}}
@keyframes bFlap{0%,100%{transform:scaleX(1) rotate(0)}50%{transform:scaleX(.72) rotate(-5deg)}}
@keyframes bSweepIn{from{transform:translateX(-105%)}to{transform:translateX(0)}}
@keyframes bSweepOut{from{transform:translateX(0)}to{transform:translateX(105%)}}
"""

# Overlay types this module renders. `compare`, `contact`, `vote` and
# `flight_path` from the kit also need raster assets and are not built yet.
KIT_TYPES = ("hook", "name_reveal", "lower_third", "chapter", "scoreboard",
             "payoff", "caption_plate", "stamp")


def _e(text: str) -> str:
    return html.escape(str(text))


def _lines(text: str, size: int, delay0: int = 90, step: int = 100) -> str:
    """Display copy as staggered wipe-up lines — the kit's signature move.

    Each line is clipped by its own overflow box so the text rises out of
    nothing rather than sliding over the footage.
    """
    out = []
    for i, line in enumerate(text.split("\n")):
        out.append(
            '<div style="overflow:hidden"><div style="animation:bWipeUp 380ms %s %dms both">%s</div></div>'
            % (EASE_OUT, delay0 + i * step, line))
    return ('<div style="font-family:%s;font-size:%dpx;line-height:1.03;font-weight:800;'
            'letter-spacing:-.045em">%s</div>' % (FONT_DISPLAY, size, "".join(out)))


def _mark(word: str) -> str:
    """The kit marks the payoff word with a solid accent box, nothing else."""
    return ('<span style="background:%s;color:%s;padding:0 12px">%s</span>'
            % (ACCENT, TEXT, _e(word)))


def emphasize(text: str, emphasis: "list[str]") -> str:
    out = _e(text)
    for word in emphasis or []:
        out = out.replace(_e(word), _mark(word))
    return out


# --- the overlays ---------------------------------------------------------

def hook(card: "dict") -> str:
    """01 Hook — eyebrow with a live dot, then two lines wiping up."""
    body = emphasize(card.get("text", ""), card.get("emphasis"))
    return """
<div style="position:absolute;left:120px;top:130px;color:%(text)s;font-family:%(body_font)s">
  <div style="display:flex;align-items:center;gap:14px;animation:bFade 240ms ease both">
    <div style="width:10px;height:10px;border-radius:999px;background:%(accent)s"></div>
    <span style="font-size:22px;font-weight:700;letter-spacing:.18em;text-transform:uppercase">%(kicker)s</span>
  </div>
  <div style="margin-top:22px">%(lines)s</div>
</div>""" % {"text": TEXT, "body_font": FONT_BODY, "accent": ACCENT,
             "kicker": _e(card.get("kicker", "")),
             "lines": _lines(body, 112)}


def lower_third(card: "dict") -> str:
    """03 Lower third — accent spine, label wipes right, then the big line."""
    return """
<div style="position:absolute;left:120px;top:130px;display:flex;align-items:stretch;
            animation:bUp 260ms %(ease_std)s both;font-family:%(body_font)s">
  <div style="width:6px;background:%(accent)s"></div>
  <div style="background:%(ink)s;border:1px solid %(hair)s;border-left:0;padding:26px 40px 28px;
              color:%(text)s;overflow:hidden">
    <div style="font-size:20px;font-weight:700;letter-spacing:.18em;text-transform:uppercase;
                color:%(accent)s;animation:bWipeR 300ms %(ease_std)s 120ms both">%(kicker)s</div>
    <div style="font-family:%(display)s;font-size:58px;font-weight:800;letter-spacing:-.04em;
                margin-top:10px;animation:bWipeR 360ms %(ease_std)s 200ms both">%(text_line)s</div>
    %(sub)s
  </div>
</div>""" % {"ease_std": EASE_STD, "body_font": FONT_BODY, "accent": ACCENT,
             "ink": INK, "hair": HAIRLINE, "text": TEXT, "display": FONT_DISPLAY,
             "kicker": _e(card.get("kicker", "")),
             "text_line": _e(card.get("text", "")),
             "sub": ('<div style="font-size:26px;color:%s;margin-top:8px;'
                     'animation:bFade 220ms ease 420ms both">%s</div>'
                     % (MUTED, _e(card["subtext"]))) if card.get("subtext") else ""}


def _scrim(card: "dict", side: bool = True) -> str:
    """A darkening wash behind full-frame overlays.

    The kit previews these on a dark placeholder clip, so its green kicker and
    muted subtext read fine there. Over real footage — a bright museum sky —
    they wash out. This gradient keeps the design intact and buys contrast;
    pass `scrim: false` on a card to turn it off for an already-dark shot.
    """
    if card.get("scrim") is False:
        return ""
    grad = ("linear-gradient(90deg, rgba(9,9,11,.86) 0%, rgba(9,9,11,.72) 45%, rgba(9,9,11,0) 78%)"
            if side else
            "linear-gradient(0deg, rgba(9,9,11,.86) 0%, rgba(9,9,11,.35) 45%, rgba(9,9,11,0) 75%)")
    return ('<div style="position:absolute;inset:0;background:%s;'
            'animation:bFade 240ms ease both"></div>' % grad)


def chapter(card: "dict") -> str:
    """10 Chapter turn — a full-bleed act break: rule, kicker, huge title."""
    return _scrim(card) + """
<div style="position:absolute;left:130px;top:0;bottom:0;display:flex;flex-direction:column;
            justify-content:center;gap:18px;color:%(text)s;font-family:%(body_font)s">
  <div style="display:flex;align-items:center;gap:16px">
    <div style="width:70px;height:3px;background:%(accent)s;transform-origin:left;
                animation:bGrowX 260ms %(ease_std)s both"></div>
    <span style="font-size:22px;font-weight:700;letter-spacing:.18em;text-transform:uppercase;
                 color:%(accent)s;animation:bFade 220ms ease 80ms both">%(kicker)s</span>
  </div>
  <div style="font-family:%(display)s;font-size:%(size)dpx;line-height:1;font-weight:800;
              letter-spacing:-.055em;overflow:hidden">
    <div style="animation:bWipeUp 420ms %(ease_out)s 160ms both">%(title)s</div>
  </div>
  %(sub)s
</div>""" % {"text": TEXT, "body_font": FONT_BODY, "accent": ACCENT,
             "ease_std": EASE_STD, "ease_out": EASE_OUT, "display": FONT_DISPLAY,
             "kicker": _e(card.get("kicker", "")),
             "title": _e(card.get("text", "")),
             # 150px is the kit's size for a one-word title; longer titles
             # must shrink or they run off the 1920px stage.
             "size": 150 if len(card.get("text", "")) <= 12 else
                     (110 if len(card.get("text", "")) <= 22 else 78),
             "sub": ('<div style="font-size:30px;color:%s;animation:bFade 240ms ease 480ms both">%s</div>'
                     % (MUTED, _e(card["subtext"]))) if card.get("subtext") else ""}


def scoreboard(card: "dict") -> str:
    """11 Scoreboard — the running tally; the changed number ticks."""
    cells = []
    for entry in card.get("entries", []):
        hot = entry.get("highlight")
        cells.append(
            '<div><div style="font-size:26px;font-weight:700;color:%s">%s</div>'
            '<div style="font-family:%s;font-size:76px;font-weight:800;letter-spacing:-.04em;'
            'line-height:1;%s">%s</div></div>'
            % (ACCENT if hot else MUTED, _e(entry.get("label", "")), FONT_DISPLAY,
               ("color:%s;animation:bTick 520ms %s 700ms both" % (ACCENT, EASE_OUT)) if hot else "",
               _e(entry.get("value", ""))))
    return """
<div style="position:absolute;left:110px;top:90px;background:%(ink)s;border:1px solid %(hair)s;
            border-radius:16px;padding:26px 30px;color:%(text)s;font-family:%(body_font)s;
            animation:bPop 320ms %(ease_out)s both">
  <div style="font-size:20px;font-weight:700;letter-spacing:.18em;text-transform:uppercase;
              color:%(accent)s">%(kicker)s</div>
  <div style="display:flex;gap:34px;margin-top:20px;align-items:flex-end">%(cells)s</div>
</div>""" % {"ink": INK, "hair": HAIRLINE, "text": TEXT, "body_font": FONT_BODY,
             "ease_out": EASE_OUT, "accent": ACCENT,
             "kicker": _e(card.get("kicker", "")), "cells": "".join(cells)}


def stat(card: "dict") -> str:
    """A number card in the kit's language: label, then the figure pops."""
    return """
<div style="position:absolute;left:110px;top:130px;background:%(ink)s;border:1px solid %(hair)s;
            border-radius:16px;padding:30px 40px 34px;color:%(text)s;font-family:%(body_font)s;
            animation:bPlate 260ms %(ease_std)s both">
  <div style="font-size:20px;font-weight:700;letter-spacing:.18em;text-transform:uppercase;
              color:%(accent)s">%(kicker)s</div>
  <div style="font-family:%(display)s;font-size:150px;line-height:1;font-weight:800;
              letter-spacing:-.05em;margin-top:10px;
              animation:bPop 340ms %(ease_out)s 220ms both">%(stat)s</div>
  <div style="font-size:30px;color:%(muted)s;margin-top:10px;
              animation:bFade 240ms ease 520ms both">%(label)s</div>
</div>""" % {"ink": INK, "hair": HAIRLINE, "text": TEXT, "body_font": FONT_BODY,
             "ease_std": EASE_STD, "ease_out": EASE_OUT, "accent": ACCENT,
             "display": FONT_DISPLAY, "muted": MUTED,
             "kicker": _e(card.get("kicker", "")), "stat": _e(card.get("stat", "")),
             "label": _e(card.get("text", ""))}


def payoff(card: "dict") -> str:
    """09 Payoff — the quotable line, held alone."""
    return _scrim(card, side=False) + """
<div style="position:absolute;left:130px;right:130px;top:0;bottom:0;display:flex;
            flex-direction:column;justify-content:center;color:%(text)s;font-family:%(body_font)s">
  <div style="width:70px;height:3px;background:%(accent)s;transform-origin:left;
              animation:bGrowX 260ms %(ease_std)s both;margin-bottom:26px"></div>
  %(lines)s
  %(attr)s
</div>""" % {"text": TEXT, "body_font": FONT_BODY, "accent": ACCENT,
             "ease_std": EASE_STD,
             "lines": _lines(emphasize(card.get("text", ""), card.get("emphasis")), 96,
                             delay0=140, step=110),
             "attr": ('<div style="font-size:28px;color:%s;margin-top:24px;'
                      'animation:bFade 240ms ease 700ms both">— %s</div>'
                      % (MUTED, _e(card["attribution"]))) if card.get("attribution") else ""}


def stamp(card: "dict") -> str:
    """12 Stamp — a verdict slammed onto the frame."""
    return """
<div style="position:absolute;right:150px;top:180px;color:%(accent)s;font-family:%(display)s;
            font-size:120px;font-weight:800;letter-spacing:-.04em;border:8px solid %(accent)s;
            border-radius:14px;padding:12px 34px;transform:rotate(-6deg);
            animation:bStamp 520ms %(ease_out)s both">%(text)s</div>
""" % {"accent": ACCENT, "display": FONT_DISPLAY, "ease_out": EASE_OUT,
       "text": _e(card.get("text", ""))}


def caption_plate(card: "dict") -> str:
    """08 Captions — the kit's caption treatment, one phrase at a time."""
    words = card.get("words") or [card.get("text", "")]
    active = card.get("active", 0)
    spans = []
    for i, w in enumerate(words):
        spans.append('<span style="%s">%s</span>'
                     % ("color:%s" % ACCENT if i == active else "", _e(w)))
    return """
<div style="position:absolute;left:0;right:0;bottom:96px;display:flex;justify-content:center;
            font-family:%(display)s">
  <div style="background:%(ink)s;border:1px solid %(hair)s;border-radius:14px;padding:18px 34px;
              color:%(text)s;font-size:64px;font-weight:800;letter-spacing:-.03em;
              animation:bPlate 200ms %(ease_std)s both">%(spans)s</div>
</div>""" % {"display": FONT_DISPLAY, "ink": INK, "hair": HAIRLINE, "text": TEXT,
             "ease_std": EASE_STD, "spans": " ".join(spans)}


def compare(card: "dict") -> str:
    """07 Compare — the teaching moment, full frame, two images side by side.

    Images are file paths (footage stills or licensed stock, see
    brand/design-system/overlay-assets/); they are inlined as file:// URLs
    because the renderer screenshots a local page.
    """
    cols = []
    for i, side in enumerate(card.get("sides", [])[:2]):
        cols.append("""
      <div style="flex:1;animation:bUp 340ms %(ease)s %(delay)dms both">
        <img src="file://%(src)s" alt="" style="display:block;width:100%%;height:330px;
             object-fit:cover;border-radius:12px;border:1px solid %(hair)s">
        <div style="font-size:20px;font-weight:700;letter-spacing:.18em;text-transform:uppercase;
                    color:%(label_color)s;margin-top:18px">%(label)s</div>
        <div style="font-family:%(display)s;font-size:52px;font-weight:800;letter-spacing:-.03em;
                    margin-top:6px">%(title)s</div>
        <div style="font-size:24px;color:%(muted)s;margin-top:8px">%(note)s</div>
      </div>""" % {"ease": EASE_OUT, "delay": 120 + i * 140,
                   "src": side.get("image", ""), "hair": HAIRLINE,
                   "label_color": ACCENT if side.get("highlight") else MUTED,
                   "label": _e(side.get("label", "")), "display": FONT_DISPLAY,
                   "title": _e(side.get("title", "")), "muted": MUTED,
                   "note": _e(side.get("note", ""))})
    return """
<div style="position:absolute;inset:0;background:%(ink_solid)s;
            animation:bFade 240ms ease both"></div>
<div style="position:absolute;left:150px;right:150px;top:0;bottom:0;display:flex;
            flex-direction:column;justify-content:center;color:%(text)s;font-family:%(body_font)s">
  <div style="font-family:%(display)s;font-size:64px;font-weight:800;letter-spacing:-.04em;
              margin-bottom:34px;overflow:hidden">
    <div style="animation:bWipeUp 380ms %(ease)s both">%(headline)s</div>
  </div>
  <div style="display:flex;gap:44px;align-items:flex-start">%(cols)s</div>
</div>""" % {"ink_solid": "#09090B", "text": TEXT, "body_font": FONT_BODY,
             "display": FONT_DISPLAY, "ease": EASE_OUT,
             "headline": _e(card.get("text", "")), "cols": "".join(cols)}


def flight_path(card: "dict") -> str:
    """16 Flight path — a dashed trail draws across frame with a butterfly on it.

    The trail and the butterfly are SVG (see overlay-assets/marks.py), so the
    stroke draws itself and the wings hinge independently — both impossible
    with the original flat PNGs.
    """
    import sys
    from pathlib import Path
    assets = Path(__file__).resolve().parent.parent / "brand" / "design-system" / "overlay-assets"
    sys.path.insert(0, str(assets))
    import marks  # noqa: E402

    # Prefer the real artwork when it is on disk (cut out of the kit's
    # reference image and recoloured to the accent); fall back to the vector
    # silhouette, which is serviceable but plainly a silhouette.
    png = assets / "butterfly.png"
    flier = ('<img src="file://%s" alt="" style="width:110px;display:block">' % png
             if png.exists() else marks.butterfly(110, ACCENT))

    travel = card.get("travel_ms", 2200)
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
<div style="position:absolute;left:130px;bottom:150px;color:%(text)s;font-family:%(body_font)s">
  <div style="font-size:20px;font-weight:700;letter-spacing:.18em;text-transform:uppercase;
              color:%(accent)s;animation:bFade 220ms ease both">%(kicker)s</div>
  <div style="font-family:%(display)s;font-size:76px;font-weight:800;letter-spacing:-.04em;
              margin-top:10px;overflow:hidden">
    <div style="animation:bWipeUp 380ms %(ease)s 160ms both">%(text_line)s</div>
  </div>
</div>""" % {"travel": travel, "ease": EASE_OUT,
             "arrow": marks.dashed_arrow(1000, ACCENT),
             "fly": flier,
             "text": TEXT, "body_font": FONT_BODY, "accent": ACCENT,
             "display": FONT_DISPLAY, "kicker": _e(card.get("kicker", "")),
             "text_line": _e(card.get("text", ""))}


def contact(card: "dict") -> str:
    """13 Contact — a ring flash and drifting dots on the frame something
    lands. The smallest moment in the footage gets the biggest reaction."""
    import random
    x = int(card.get("x", 1120))
    y = int(card.get("y", 560))
    rng = random.Random(card.get("id", "contact"))
    dots = []
    for i in range(7):
        size = rng.choice([14, 16, 22, 26, 26, 36])
        dx = x + 60 + rng.randint(0, 200)
        dy = y + 130 + rng.randint(0, 40)
        colour = ACCENT if i % 3 else TEXT
        dots.append('<div style="position:absolute;left:%dpx;top:%dpx;width:%dpx;height:%dpx;'
                    'border-radius:999px;background:%s;opacity:.%d;'
                    'animation:bBurst %dms %s %dms both"></div>'
                    % (dx, dy, size, size, colour, rng.randint(7, 9),
                       900 + i * 30, EASE_OUT, 80 + i * 60))
    return """
<div style="position:absolute;inset:0">
  <div style="position:absolute;left:%(x)dpx;top:%(y)dpx;width:300px;height:300px;
              border:4px solid %(accent)s;border-radius:999px;
              animation:bFlash 620ms ease-out both"></div>
  %(dots)s
</div>""" % {"x": x, "y": y, "accent": ACCENT, "dots": "".join(dots)}


def reaction(card: "dict") -> str:
    """14 Reaction — a quoted line at full volume, wobbling in."""
    lines = card.get("text", "").split("\n")
    parts = []
    for i, line in enumerate(lines):
        marked = i == len(lines) - 1 and card.get("mark_last", True)
        style = ("background:%s;color:%s;padding:0 16px;" % (ACCENT, TEXT)) if marked else ""
        parts.append('<div style="display:inline-block;font-family:%s;font-size:108px;'
                     'line-height:1;font-weight:800;letter-spacing:-.05em;color:%s;'
                     'text-shadow:0 4px 22px rgba(9,9,11,.85);%s'
                     'margin-top:%dpx;animation:bWobble 460ms %s %dms both">%s</div>'
                     % (FONT_DISPLAY, TEXT, style, 14 if i else 0, EASE_OUT,
                        i * 160, _e(line)))
    return """
<div style="position:absolute;left:140px;top:230px;right:520px;font-family:%(body_font)s">
  %(parts)s
  %(attr)s
</div>""" % {"body_font": FONT_BODY, "parts": "".join(parts),
             "attr": ('<div style="font-size:30px;font-weight:700;letter-spacing:.16em;'
                      'text-transform:uppercase;color:%s;margin-top:26px;'
                      'animation:bFade 220ms ease 520ms both">%s</div>'
                      % (ACCENT, _e(card["attribution"]))) if card.get("attribution") else ""}


def vote(card: "dict") -> str:
    """15 Vote — a tally with bars that grow; the punchline is the last row."""
    total = max((int(r.get("value", 0)) for r in card.get("rows", [])), default=1) or 1
    rows = []
    for i, r in enumerate(card.get("rows", [])):
        lead = r.get("highlight")
        pct = 100.0 * int(r.get("value", 0)) / total
        rows.append("""
      <div style="margin-top:%(mt)dpx">
        <div style="display:flex;justify-content:space-between;align-items:baseline;
                    font-family:%(display)s;font-size:40px;font-weight:800;
                    letter-spacing:-.025em;%(dim)s">
          <span>%(label)s</span><span%(vcol)s>%(value)s</span></div>
        <div style="height:14px;background:rgba(252,252,250,.14);border-radius:999px;
                    margin-top:12px;overflow:hidden">
          <div style="height:100%%;width:%(pct).1f%%;background:%(bar)s;transform-origin:left;
                      animation:bBar 520ms %(ease)s %(delay)dms both"></div></div>
      </div>""" % {"mt": 34 if i == 0 else 30, "display": FONT_DISPLAY,
                   "dim": "" if lead else "color:#B5B5AF;",
                   "label": _e(r.get("label", "")),
                   "vcol": ' style="color:%s"' % ACCENT if lead else "",
                   "value": _e(r.get("value", "")), "pct": max(pct, 4),
                   "bar": ACCENT if lead else "rgba(252,252,250,.34)",
                   "ease": EASE_OUT, "delay": 120 + i * 110})
    return """
<div style="position:absolute;right:120px;top:250px;width:820px;color:%(text)s;
            font-family:%(body_font)s">
  <div style="font-size:22px;font-weight:700;letter-spacing:.18em;text-transform:uppercase;
              color:%(accent)s;animation:bFade 220ms ease both">%(kicker)s</div>
  %(rows)s
</div>""" % {"text": TEXT, "body_font": FONT_BODY, "accent": ACCENT,
             "kicker": _e(card.get("kicker", "")), "rows": "".join(rows)}


def transition(card: "dict") -> str:
    """A glass panel that sweeps across the cut, carrying the next title.

    Hard cuts between chapters read as abrupt; Resolve's API cannot add a
    dissolve, so the transition is drawn instead: a near-opaque ink panel
    wipes in over the outgoing shot, holds the title, and wipes off the
    incoming one. Place it centred on the cut so it hides the seam.
    """
    total = int(float(card.get("duration", 1.4)) * 1000)
    sweep = 380
    hold = max(total - 2 * sweep, 200)
    return """
<div style="position:absolute;inset:0;overflow:hidden">
  <div style="position:absolute;inset:0;background:linear-gradient(100deg,
              rgba(9,9,11,.97) 0%%, rgba(22,22,26,.94) 55%%, rgba(9,9,11,.97) 100%%);
              animation:bSweepIn %(sweep)dms %(ease)s both,
                        bSweepOut %(sweep)dms %(ease_in)s %(out)dms both">
    <div style="position:absolute;left:130px;top:0;bottom:0;display:flex;flex-direction:column;
                justify-content:center;gap:16px;color:%(fg)s;font-family:%(body_font)s">
      <div style="display:flex;align-items:center;gap:16px">
        <div style="width:70px;height:3px;background:%(accent)s;transform-origin:left;
                    animation:bGrowX 260ms %(ease)s %(sweep)dms both"></div>
        <span style="font-size:22px;font-weight:700;letter-spacing:.18em;text-transform:uppercase;
                     color:%(accent)s;animation:bFade 200ms ease %(sweep)dms both">%(kicker)s</span>
      </div>
      <div style="font-family:%(display)s;font-size:104px;line-height:1;font-weight:800;
                  letter-spacing:-.05em;overflow:hidden">
        <div style="animation:bWipeUp 380ms %(ease)s %(t2)dms both">%(text)s</div>
      </div>
    </div>
  </div>
</div>""" % {"sweep": sweep, "ease": EASE_OUT, "ease_in": EASE_STD,
             "out": sweep + hold, "fg": TEXT, "body_font": FONT_BODY,
             "accent": ACCENT, "display": FONT_DISPLAY, "t2": sweep + 80,
             "kicker": _e(card.get("kicker", "")),
             # NB: the colour key is "fg", not "text" — a second "text" entry
             # here (the title) silently overwrote the first, so `color:` got
             # the title string, was dropped as invalid, and every chapter
             # transition rendered black-on-black (found 2026-08-18).
             "text": _e(card.get("text", ""))}


RENDERERS = {
    "hook": hook,
    "compare": compare,
    "flight_path": flight_path,
    "contact": contact,
    "reaction": reaction,
    "vote": vote,
    "transition": transition,
    "hook_title": hook,          # aliases so existing graphics plans keep working
    "lower_third": lower_third,
    "section": lower_third,
    "chapter": chapter,
    "scoreboard": scoreboard,
    "stat": stat,
    "payoff": payoff,
    "quote": payoff,
    "outro": chapter,
    "stamp": stamp,
    "caption_plate": caption_plate,
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
