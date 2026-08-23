# -*- coding: utf-8 -*-
"""The VFX pack — the "VFX and custom video transitions" canvas, re-implemented.

Source of truth: Claude Design project 0eb765c9 (`VfxPack.dc.html` +
`vfx-pack-piece.jsx`), ported 2026-08-23 per the doctrine: design it in
Claude Design first, re-implement the returned canvas here, never the other
way round. Three families, 33 screens:

  fx_*   ten repeatable effects — punch-in, freeze, spotlight, speed ramp,
         rewind, impact shake, letterbox, glitch, live underline, pause pulse
  cut_*  fourteen custom transitions — arch doorway, light flood, crop
         punch, waveform riser, colonnade, nine doors, room meter, rule
         drop, bracket squeeze, mark swap, scrim fade, figure walk, slice
         exit, split rule
  ed_*   furniture for nine of the ten classic editorial cuts — jump ticks,
         J/L waveforms, action streak, match marks, the Meanwhile inset,
         cross-cut rule, smash flash, montage. The hard cut is deliberately
         ABSENT: the canvas's own rule is "no furniture, ever".

What an overlay can and cannot carry, honestly: these bake to alpha clips
composited OVER footage (animate.py samples the CSS keyframes frame by
frame), so every mark, rule, wash, waveform and label ports exactly — but a
transform OF the footage (the punch-in's zoom, the shake's kick, the
freeze's stop, the glitch's slice offsets) is the editor's move in Resolve
underneath. Each such screen says so in its docstring. The cut_* family
covers the frame at its midpoint — place the overlay across a HARD CUT and
time the cut to the cover; the canvas's reveal-of-shot-B becomes
cover-then-reveal, which is the same cut wearing the constraint this
pipeline actually has (transitions do not survive FCPXML; opaque cover
does).

Ration rules, from the canvas: never two effects on one beat; every effect
fires once (the pause pulse is the only sanctioned loop); freeze once per
episode; glitch reserved for room-nine lore; arch doorway once a video;
figure walk once a season; the meter is the episode's last cut.
"""
from __future__ import annotations

from .overlay_kit import (
    CHALK, CYAN, NAVY, SLATE_300, YELLOW, INERT,
    EASE_RULE, EASE_REVEAL, FONT_DISPLAY, FONT_SERIF, SHADOW_DISPLAY,
    _display, _e, _eyebrow, _fit, _fscale, _scrim,
)

# Washes: the canvas dims footage with navy at fixed alphas. These are
# legibility washes over video (sanctioned), never text plates.
def _wash(alpha, delay_ms=0, dur_ms=300):
    return ('<div style="position:absolute;inset:0;background:rgba(11,35,64,%s);'
            'animation:yFade %dms ease %dms both"></div>'
            % (alpha, dur_ms, delay_ms))


def _marks(left, top, w, h, color=YELLOW, delay_ms=0, size=34, stroke=4):
    """Four crop marks framing a box — the kit's second primitive."""
    corner = []
    for x, y in (("left", "top"), ("right", "top"),
                 ("left", "bottom"), ("right", "bottom")):
        corner.append(
            '<div style="position:absolute;%s:-4px;%s:-4px;width:%dpx;height:%dpx;'
            'border-%s:%dpx solid %s;border-%s:%dpx solid %s"></div>'
            % (x, y, size, size, x, stroke, color, y, stroke, color))
    return ('<div style="position:absolute;left:%s;top:%s;width:%s;height:%s;'
            'animation:yPop 260ms %s %dms both">%s</div>'
            % (_px(left), _px(top), _px(w), _px(h), EASE_REVEAL, delay_ms,
               "".join(corner)))


def _px(v):
    return v if isinstance(v, str) else "%dpx" % v


def _eye_label(F, kicker, text, card, delay_kicker=200, delay_text=500,
               tone=CYAN, size=62):
    """The canvas's Eye + Label pair, bottom-left at the frame's insets."""
    parts = []
    if kicker:
        parts.append(_eyebrow(kicker, tone, delay_kicker, 28))
    if text:
        parts.append('<div style="%s;animation:yUp 400ms %s %dms both">%s</div>'
                     % (_display(_fit(text, size, budget=F["inner"],
                                      fscale=_fscale(card))),
                        EASE_REVEAL, delay_text, _e(text)))
    return ('<div style="position:absolute;left:%dpx;bottom:%dpx;display:flex;'
            'flex-direction:column;gap:14px">%s</div>'
            % (F["side"], F["bottom"] + 20, "".join(parts)))


# --------------------------------------------------------------------------
# fx_* — the ten effects
# --------------------------------------------------------------------------

def fx_punch(card, F):
    """Punch-in furniture: crop marks land on the detail; the two-step zoom
    itself is the editor's move on the footage underneath. Use on any noun
    worth a second look; cut on the beat."""
    mx = "62%" if not F["portrait"] else "50%"
    return (
        _wash(".35")
        + _marks("calc(%s - 170px)" % mx, "28%", 340, 260, YELLOW, 900)
        + _eye_label(F, card.get("kicker") or "Punch-in · cut on the beat",
                     card.get("text") or "Look closer.", card, tone=YELLOW)
    )


def fx_freeze(card, F):
    """Freeze frame: the editor stops the footage; this overlay names the
    moment — dim, marks, PAUSED bars, the record-scratch caption. Once per
    episode, max."""
    bars = ('<div style="position:absolute;right:%dpx;top:%dpx;display:flex;'
            'gap:8px;align-items:center;animation:yFade 200ms ease 1200ms both">'
            '<div style="width:8px;height:34px;background:%s"></div>'
            '<div style="width:8px;height:34px;background:%s"></div>'
            '<span style="font-family:%s;font-size:26px;font-weight:800;'
            'letter-spacing:.22em;text-transform:uppercase;color:%s;'
            'margin-left:8px">PAUSED</span></div>'
            % (F["side"], F["top"] - 34, CHALK, CHALK, FONT_DISPLAY, CHALK))
    return (
        _wash(".66", 1200, 200)
        + _marks("36%", "24%", "27%", "52%", YELLOW, 1250)
        + bars
        + _eye_label(F, card.get("kicker") or "Yep, that's us",
                     card.get("text")
                     or "You're probably wondering how we got here.",
                     card, 1250, 1500)
    )


def fx_spotlight(card, F):
    """Spotlight: everything dims except the crop-marked subject — the dim
    is a wash with a hole, so it composites over live footage. Use when the
    frame is busy."""
    # the hole, as the canvas cut it: a polygon window in the wash
    hole = ("polygon(0 0,100%% 0,100%% 100%%,0 100%%,0 34%%,58%% 34%%,"
            "58%% 76%%,88%% 76%%,88%% 34%%,0 34%%)")
    wash = ('<div style="position:absolute;inset:0;background:rgba(11,35,64,.78);'
            'clip-path:%s;animation:yFade 400ms %s 800ms both"></div>'
            % (hole, EASE_RULE))
    return (
        wash
        + _marks("58%", "34%", "30%", "42%", YELLOW, 1100)
        + _eye_label(F, card.get("kicker") or "Ignore everything else",
                     card.get("text") or "This one. This is the one.",
                     card, 1300, 1550)
    )


def fx_ramp(card, F):
    """Speed ramp furniture: cyan speed lines streak past (the 4x transit
    and the skew are the footage's). For transit between rooms."""
    lines = []
    for i, y in enumerate((210, 380, 520, 700, 860)):
        top = "%d%%" % int(y / 10.8)
        lines.append(
            '<div style="position:absolute;left:-30%%;top:%s;width:%dpx;'
            'height:%dpx;background:%s;'
            'animation:yStreak %dms linear %dms infinite"></div>'
            % (top, 220 + i * 40, 3 if i % 2 else 5,
               YELLOW if i == 2 else CYAN, 900 + i * 120, i * 90))
    window = ('<div style="position:absolute;inset:0;'
              'animation:yWindow 1ms linear 600ms both">%s</div>'
              % "".join(lines))
    return (
        window
        + _eye_label(F, card.get("kicker") or "4× · rooms 4 through 7",
                     card.get("text") or "Nothing happened in these.",
                     card, 200, 450, YELLOW)
    )


def fx_rewind(card, F):
    """Rewind: chalk rewind glyphs cycle, the yellow tick scrubber runs
    backward. The scrub of the footage is the editor's. For callbacks."""
    tris = "".join(
        '<div style="width:0;height:0;border-top:17px solid transparent;'
        'border-bottom:17px solid transparent;border-right:26px solid %s;'
        'animation:yBlink 750ms steps(1) %dms infinite"></div>'
        % (CHALK, i * 250) for i in range(3))
    ticks_dim = "".join(
        '<div style="width:3px;height:%dpx;background:%s"></div>'
        % (24 if i % 4 == 0 else 14, INERT) for i in range(24))
    ticks_yellow = "".join(
        '<div style="width:3px;height:%dpx;background:%s"></div>'
        % (24 if i % 4 == 0 else 14, YELLOW) for i in range(24))
    line = card.get("text") or "Hold on. Rewind."
    return (
        _wash(".4")
        + ('<div style="position:absolute;left:0;right:0;top:%dpx;display:flex;'
           'justify-content:center;gap:12px">%s</div>' % (F["top"] - 34, tris))
        + ('<div style="position:absolute;left:0;right:0;bottom:%dpx;'
           'display:flex;justify-content:center">'
           '<div style="position:relative;display:flex;gap:12px;align-items:flex-end">'
           '<div style="position:absolute;inset:0;display:flex;gap:12px;'
           'align-items:flex-end">%s</div>'
           '<div style="display:flex;gap:12px;align-items:flex-end;'
           'clip-path:inset(0 0 0 100%%);'
           'animation:yScrub 1500ms %s 700ms both">%s</div>'
           '</div></div>'
           % (F["bottom"] + 110, ticks_yellow, EASE_RULE, ticks_dim))
        + ('<div style="position:absolute;left:0;right:0;bottom:%dpx;'
           'text-align:center"><div style="%s;animation:yUp 400ms %s both">%s'
           '</div></div>'
           % (F["bottom"], _display(_fit(line, 62, budget=F["inner"],
                                         fscale=_fscale(card))),
              EASE_REVEAL, _e(line)))
    )


def fx_shake(card, F):
    """Impact shake furniture: the giant yellow stat lands with its
    sub-line (the frame kick is the editor's). Only under a stat."""
    stat = card.get("stat") or card.get("value") or "65 million"
    sub = card.get("text") or "years. In a hallway."
    return (
        _wash(".5", 900, 250)
        + ('<div style="position:absolute;inset:0;display:flex;flex-direction:'
           'column;align-items:center;justify-content:center;gap:10px">'
           '<div style="font-family:%s;font-size:%dpx;line-height:1;'
           'font-weight:800;letter-spacing:-.015em;color:%s;'
           'text-shadow:0 6px 30px rgba(4,16,32,.85);'
           'animation:yPop 300ms %s 1000ms both">%s</div>'
           '<div style="font-family:%s;font-size:44px;font-weight:700;color:%s;'
           'text-shadow:%s;animation:yUp 400ms %s 1400ms both">%s</div></div>'
           % (FONT_DISPLAY, _fit(str(stat), 200, budget=F["inner"]),
              YELLOW, EASE_REVEAL, _e(str(stat)),
              FONT_DISPLAY, CHALK, SHADOW_DISPLAY, EASE_REVEAL, _e(sub)))
    )


def fx_letterbox(card, F):
    """Letterbox: navy bars close to cinema ratio for the serif beat. For
    the takeaway."""
    bar_h = int(F["h"] * 0.14)
    line = card.get("text") or "It wasn't on the map."
    return (
        _wash(".45")
        + ('<div style="position:absolute;left:0;right:0;top:0;height:%dpx;'
           'background:%s;transform-origin:top;'
           'animation:yGrowY 600ms %s 400ms both"></div>' % (bar_h, NAVY, EASE_RULE))
        + ('<div style="position:absolute;left:0;right:0;bottom:0;height:%dpx;'
           'background:%s;transform-origin:bottom;'
           'animation:yGrowY 600ms %s 400ms both"></div>' % (bar_h, NAVY, EASE_RULE))
        + ('<div style="position:absolute;left:0;right:0;bottom:%dpx;'
           'text-align:center;animation:yUp 500ms %s 1200ms both">'
           '<div style="font-family:%s;font-size:%dpx;font-style:italic;'
           'letter-spacing:-.02em;color:%s;text-shadow:%s">%s</div></div>'
           % (bar_h + 60, EASE_REVEAL, FONT_SERIF,
              _fit(line, 66, budget=F["inner"], fscale=_fscale(card)),
              CHALK, SHADOW_DISPLAY, _e(line)))
    )


def fx_glitch(card, F):
    """Brand-safe glitch furniture: the cyan and yellow scan rules flicker
    (the three slice offsets are the footage's). Reserved for room-nine
    lore."""
    return (
        ('<div style="position:absolute;left:0;right:0;top:33.5%%;height:3px;'
         'background:%s;opacity:0;'
         'animation:yFlicker 1300ms steps(1) 800ms infinite"></div>' % CYAN)
        + ('<div style="position:absolute;left:0;right:0;top:61.5%%;height:3px;'
           'background:%s;opacity:0;'
           'animation:yFlicker 1300ms steps(1) 800ms infinite"></div>' % YELLOW)
        + _eye_label(F, card.get("kicker") or "Footage recovered · room nine",
                     card.get("text") or "This is the only shot we have.",
                     card)
    )


def fx_underline(card, F):
    """Live underline: the spoken keyword gets the yellow rule as it's
    said. `text` is the line, `underline` the word that matters."""
    line = card.get("text") or "They never counted the rooms."
    word = card.get("underline") or "counted"
    words = line.split(" ")
    out = []
    hit = False
    for i, w in enumerate(words):
        core = w.strip(".,!?…")
        if not hit and word and core == word.strip(".,!?…"):
            hit = True
            out.append(
                '<span style="position:relative;display:inline-block;'
                'animation:yUp 180ms %s %dms both">%s'
                '<span style="position:absolute;left:0;bottom:-12px;height:6px;'
                'width:100%%;background:%s;transform-origin:left;'
                'animation:yGrow 350ms %s 1400ms both"></span></span>'
                % (EASE_REVEAL, 400 + i * 100, _e(w), YELLOW, EASE_RULE))
        else:
            out.append('<span style="display:inline-block;'
                       'animation:yUp 180ms %s %dms both">%s</span>'
                       % (EASE_REVEAL, 400 + i * 100, _e(w)))
    return (
        _scrim("tall")
        + ('<div style="position:absolute;left:0;right:0;bottom:%dpx;'
           'text-align:center"><div style="%s;display:inline-flex;gap:20px;'
           'flex-wrap:wrap;justify-content:center">%s</div></div>'
           % (F["bottom"], _display(_fit(line, 64, budget=F["inner"],
                                         fscale=_fscale(card)), "-.035em"),
              "".join(out)))
    )


def fx_pause(card, F):
    """Pause pulse — THE sanctioned loop: two yellow bars pulse over a held
    frame. When you actually want them to pause."""
    line = card.get("text") or "Pause it. Read the last line."
    sub = card.get("subtext") or "We'll wait in the comments."
    return (
        _wash(".55")
        + ('<div style="position:absolute;inset:0;display:flex;flex-direction:'
           'column;align-items:center;justify-content:center;gap:26px">'
           '<div style="display:flex;gap:14px;'
           'animation:yPulse 1550ms ease-in-out infinite alternate">'
           '<div style="width:14px;height:64px;background:%s"></div>'
           '<div style="width:14px;height:64px;background:%s"></div></div>'
           '<div style="%s;animation:yUp 400ms %s 400ms both">%s</div>'
           '<div style="font-family:%s;font-size:30px;font-weight:600;color:%s;'
           'animation:yUp 400ms %s 800ms both">%s</div></div>'
           % (YELLOW, YELLOW,
              _display(_fit(line, 62, budget=F["inner"], fscale=_fscale(card))),
              EASE_REVEAL, _e(line),
              FONT_DISPLAY, SLATE_300, EASE_REVEAL, _e(sub)))
    )


# --------------------------------------------------------------------------
# cut_* — fourteen custom transitions. Every one covers the frame at its
# midpoint: place the overlay ACROSS a hard cut, cut under the cover.
# --------------------------------------------------------------------------

def _cover_note(kicker, F, card, tone=CYAN):
    return _eyebrow(kicker, tone, 100, 28) and (
        '<div style="position:absolute;left:%dpx;top:%dpx;'
        'animation:yCueFade 1ms linear both">%s</div>'
        % (F["side"], F["top"] - 34, _eyebrow(kicker, tone, 100, 28)))


def cut_arch(card, F):
    """Arch doorway — the mark in motion. A yellow-edged arch grows from
    the floor, navy in the passage with warm light, covers the frame at the
    cut, and fades. Entering a room that matters; once a video."""
    return (
        '<div style="position:absolute;left:50%;bottom:0;width:160px;height:200px;'
        'transform:translateX(-50%);transform-origin:bottom center;'
        'border-radius:999px 999px 0 0;background:' + NAVY + ';'
        'box-shadow:0 0 0 5px ' + YELLOW + ';overflow:hidden;'
        'animation:yArchGrow 950ms ' + EASE_RULE + ' 550ms both,'
        'yFadeOut 1ms linear 1580ms forwards">'
        '<div style="position:absolute;inset:0;background:'
        'linear-gradient(0deg, rgba(255,224,77,.55), rgba(255,224,77,0) 70%);'
        'animation:yFadeOut 850ms linear 550ms both"></div></div>'
        + '<div style="position:absolute;inset:0;background:' + NAVY + ';'
        'opacity:0;animation:yCoverBridge 600ms linear 1500ms forwards">'
        '</div>'
        + _cover_note(card.get("kicker")
                      or "Arch doorway · cut under the cover", F, card, YELLOW)
    )


def cut_flood(card, F):
    """Light flood: warm light sweeps up over the frame, holds one covered
    beat — the cut — and recedes upward. Dark to lit."""
    return (
        '<div style="position:absolute;left:0;right:0;top:0;height:240%;'
        'background:linear-gradient(0deg, rgba(255,224,77,0) 4%, ' + YELLOW +
        ' 22%, ' + YELLOW + ' 78%, rgba(255,224,77,0) 96%);'
        'transform:translateY(100%);'
        'animation:ySweepUp 1800ms ' + EASE_RULE + ' 450ms both"></div>'
        + _cover_note(card.get("kicker")
                      or "Light flood · the light does the cut", F, card, YELLOW)
    )


def cut_scrim(card, F):
    """Scrim fade — the quiet cut: the navy scrim rises to a full wash,
    holds a beat over the cut, and falls away."""
    return (
        '<div style="position:absolute;left:0;right:0;top:0;height:240%;'
        'background:linear-gradient(0deg, rgba(11,35,64,0) 4%, ' + NAVY +
        ' 22%, ' + NAVY + ' 78%, rgba(11,35,64,0) 96%);'
        'transform:translateY(100%);'
        'animation:ySweepUp 1800ms ' + EASE_RULE + ' 400ms both"></div>'
        + _cover_note(card.get("kicker") or "Scrim fade · the quiet cut",
                      F, card)
    )


def cut_crop(card, F):
    """Crop punch: marks land on the detail and blow past the frame as the
    navy dip takes the cut. The next shot is inside this one."""
    return (
        '<div style="position:absolute;left:50%;top:50%;width:400px;height:400px;'
        'transform:translate(-50%,-50%);'
        'animation:yMarksBlow 1050ms ' + EASE_RULE + ' 800ms both">'
        + _marks(0, 0, "100%", "100%", YELLOW, 300) + '</div>'
        + '<div style="position:absolute;inset:0;background:' + NAVY + ';'
        'opacity:0;animation:yDip 400ms linear 1150ms both"></div>'
        + _cover_note(card.get("kicker")
                      or "Crop punch · the next shot is inside this one",
                      F, card, YELLOW)
    )


def cut_wave(card, F):
    """Waveform riser: cyan bars rise staggered to fill the frame, hold the
    cut, and fall away. When the sound changes before the place does."""
    n = 18 if F["portrait"] else 32
    bars = "".join(
        '<div style="flex:1;background:%s;transform:scaleY(0);'
        'transform-origin:bottom;height:%d%%;'
        'animation:yBarRiseFall 1600ms %s %dms both"></div>'
        % (CYAN, 102 + (i * 37) % 5 * 4, EASE_RULE, 350 + i * 12)
        for i in range(n))
    return (
        ('<div style="position:absolute;inset:0;display:flex;'
         'align-items:flex-end;gap:16px;padding:0 8px">%s</div>' % bars)
        + _cover_note(card.get("kicker")
                      or "Waveform riser · the sound changes first", F, card)
    )


def cut_doors(card, F):
    """Nine doors: navy arch-topped columns rise from the floor centre-out,
    cover, and fall. Room to room."""
    cols = "".join(
        '<div style="flex:1;background:%s;border-radius:999px 999px 0 0;'
        'transform:scaleY(0);transform-origin:bottom;height:121%%;'
        'animation:yBarRiseFall 1700ms %s %dms both"></div>'
        % (NAVY, EASE_RULE, 400 + abs(i - 4) * 50) for i in range(9))
    return (
        ('<div style="position:absolute;inset:0;display:flex;'
         'align-items:flex-end;gap:6px;padding:0 3px">%s</div>' % cols)
        + _cover_note(card.get("kicker") or "Nine doors · room to room",
                      F, card)
    )


def cut_colonnade(card, F):
    """Colonnade: eight chalk arches line the hall, the lit ninth grows to
    take the frame. Room-to-room with continuity."""
    others = "".join(
        '<div style="position:absolute;left:%dpx;top:%dpx;width:150px;'
        'height:187px;border-radius:75px 75px 0 0;'
        'border:3px solid rgba(234,244,255,.42);border-bottom:none">'
        '</div>' % (5 + i * 220, int(F["h"] * 0.475))
        for i in (0, 1, 2, 3, 5, 6, 7, 8))
    return (
        _wash(".45")
        + ('<div style="position:absolute;inset:0;'
           'animation:yRowIn 700ms %s 250ms both">'
           '<div style="position:absolute;inset:0;'
           'animation:yFadeOut 250ms linear 1350ms both">%s</div></div>'
           % (EASE_REVEAL, others))
        + ('<div style="position:absolute;left:50%%;bottom:0;width:150px;'
           'height:187px;transform:translateX(-50%%);transform-origin:bottom center;'
           'border-radius:999px 999px 0 0;background:%s;'
           'box-shadow:0 0 0 4px %s, 0 -30px 80px rgba(255,224,77,.5);'
           'animation:yArchGrow 950ms %s 1350ms both,'
           'yFadeOut 1ms linear 2380ms forwards"></div>'
           % (NAVY, YELLOW, EASE_RULE))
        + '<div style="position:absolute;inset:0;background:' + NAVY + ';'
        'opacity:0;animation:yCoverBridge 500ms linear 2300ms forwards"></div>'
        + _cover_note(card.get("kicker") or "Colonnade · nine doors, one lit",
                      F, card, YELLOW)
    )


def cut_meter(card, F):
    """Room meter: the nine squares fill one per beat; the ninth square IS
    the cut. The episode's last transition."""
    cells = "".join(
        '<div style="width:26px;height:26px;border:3px solid %s;'
        'box-sizing:border-box;position:relative">'
        '<div style="position:absolute;inset:-3px;background:%s;opacity:0;'
        'animation:yCueFade 1ms linear %dms both"></div></div>'
        % (INERT, YELLOW, 350 + i * 160) for i in range(9))
    return (
        ('<div style="position:absolute;left:0;right:0;bottom:%dpx;'
         'display:flex;justify-content:center;gap:12px;'
         'animation:yFadeOut 400ms linear 2200ms both">%s</div>'
         % (F["bottom"], cells))
        + ('<div style="position:absolute;left:%dpx;top:%dpx;'
           'animation:yFadeOut 400ms linear 2200ms both">%s</div>'
           % (F["side"], F["top"] - 34,
              _eyebrow(card.get("kicker")
                       or "Room meter · the ninth square is the cut",
                       YELLOW, 100, 28)))
    )


def cut_ruledrop(card, F):
    """Rule drop: a cyan rule falls down the frame with the navy cover
    behind it; full at the bottom — the cut — then everything fades."""
    return (
        ('<div style="position:absolute;left:0;right:0;top:-100%%;height:100%%;'
         'background:%s;animation:yDropCover 650ms %s 450ms both,'
         'yFadeOut 1ms linear 1180ms forwards"></div>'
         % (NAVY, EASE_RULE))
        + ('<div style="position:absolute;left:0;right:0;top:-5px;height:5px;'
           'background:%s;animation:yDropRule 650ms %s 450ms both"></div>'
           % (CYAN, EASE_RULE))
        + ('<div style="position:absolute;inset:0;background:%s;opacity:0;'
           'animation:yCoverBridge 550ms linear 1100ms forwards"></div>' % NAVY)
        + _cover_note(card.get("kicker")
                      or "Rule drop · the horizontal house cut", F, card)
    )


def cut_bracket(card, F):
    """Bracket squeeze: yellow dimension caps ride navy panels closing from
    both sides; the meet is the cut. Measured out of frame."""
    return (
        ('<div style="position:absolute;top:0;bottom:0;left:-50%%;width:50%%;'
         'background:%s;animation:ySlideInL 700ms %s 500ms both,'
         'yFadeOut 1ms linear 1280ms forwards">'
         '<div style="position:absolute;right:0;top:45%%;width:3px;height:100px;'
         'background:%s"></div></div>' % (NAVY, EASE_RULE, YELLOW))
        + ('<div style="position:absolute;top:0;bottom:0;right:-50%%;width:50%%;'
           'background:%s;animation:ySlideInR 700ms %s 500ms both,'
           'yFadeOut 1ms linear 1280ms forwards">'
           '<div style="position:absolute;left:0;top:45%%;width:3px;height:100px;'
           'background:%s"></div></div>' % (NAVY, EASE_RULE, YELLOW))
        + ('<div style="position:absolute;inset:0;background:%s;opacity:0;'
           'animation:yCoverBridge 600ms linear 1200ms forwards"></div>' % NAVY)
        + _cover_note(card.get("kicker")
                      or "Bracket squeeze · measured out of frame",
                      F, card, YELLOW)
    )


def cut_marks(card, F):
    """Mark swap: four crop marks fly to the centre, the navy dip takes the
    swap inside them, and they fly back out."""
    return (
        ('<div style="position:absolute;left:50%%;top:50%%;width:2000px;'
         'height:1160px;transform:translate(-50%%,-50%%);'
         'animation:yMarksInOut 1500ms %s 400ms both">%s</div>'
         % (EASE_RULE, _marks(0, 0, "100%", "100%", YELLOW, 0)))
        + ('<div style="position:absolute;inset:0;background:%s;opacity:0;'
           'animation:yDip 400ms linear 950ms both"></div>' % NAVY)
        + _cover_note(card.get("kicker")
                      or "Mark swap · the shot changes inside the frame",
                      F, card, YELLOW)
    )


def cut_figure(card, F):
    """Figure walk: the chalk figure crosses the frame with the navy cover
    following behind. Once a season."""
    return (
        ('<div style="position:absolute;top:0;bottom:0;left:-100%%;width:100%%;'
         'background:%s;animation:ySlideAcross 1850ms %s 350ms both,'
         'yFadeOut 1ms linear 2280ms forwards"></div>'
         % (NAVY, EASE_RULE))
        + ('<div style="position:absolute;top:%dpx;left:-40px;'
           'animation:yWalkX 1850ms %s 350ms both">'
           '<div style="animation:yBob 220ms ease-in-out infinite alternate">'
           '<div style="width:26px;height:26px;border-radius:50%%;background:%s;'
           'margin:0 auto 5px"></div>'
           '<div style="width:20px;height:74px;border-radius:10px 10px 3px 3px;'
           'background:%s;margin:0 auto"></div></div></div>'
           % (int(F["h"] * 0.79), EASE_RULE, CHALK, CHALK))
        + ('<div style="position:absolute;inset:0;background:%s;opacity:0;'
           'animation:yCoverBridge 450ms linear 2200ms forwards"></div>' % NAVY)
        + _cover_note(card.get("kicker") or "Figure walk · once a season",
                      F, card)
    )


def cut_slices(card, F):
    """Slice exit: three navy bands cross the frame alternating sides, cyan
    rules on their edges; the middle pass is the cut."""
    bands = []
    for i, (a, b) in enumerate(((0, 34), (34, 62), (62, 100))):
        anim = "ySliceR" if i % 2 else "ySliceL"
        bands.append(
            '<div style="position:absolute;left:0;right:0;top:%d%%;height:%d%%;'
            'overflow:hidden"><div style="position:absolute;inset:0;'
            'background:%s;transform:translateX(%s);'
            'animation:%s 1100ms %s %dms both">'
            '<div style="position:absolute;left:0;right:0;bottom:0;height:3px;'
            'background:%s"></div></div></div>'
            % (a, b - a, NAVY, "-100%" if i % 2 == 0 else "100%",
               anim, EASE_RULE, 500 + i * 140, CYAN))
    return "".join(bands) + _cover_note(
        card.get("kicker") or "Slice exit · three bands, alternating", F, card)


def cut_split(card, F):
    """Split rule: the yellow rule draws across the middle, navy halves
    close onto it — the cut — then slide apart."""
    return (
        ('<div style="position:absolute;left:0;right:0;top:0;height:50%%;'
         'background:%s;transform:translateY(-100%%);'
         'animation:yCloseTop 1400ms %s 850ms both"></div>' % (NAVY, EASE_RULE))
        + ('<div style="position:absolute;left:0;right:0;bottom:0;height:50%%;'
           'background:%s;transform:translateY(100%%);'
           'animation:yCloseBottom 1400ms %s 850ms both"></div>' % (NAVY, EASE_RULE))
        + ('<div style="position:absolute;left:0;top:calc(50%% - 3px);height:5px;'
           'width:100%%;background:%s;transform:scaleX(0);transform-origin:left;'
           'animation:yGrow 350ms %s 350ms both"></div>' % (YELLOW, EASE_RULE))
        + _cover_note(card.get("kicker")
                      or "Split rule · the frame comes apart on the line",
                      F, card, YELLOW)
    )


# --------------------------------------------------------------------------
# ed_* — furniture for the classic editorial cuts. The hard cut has NO
# renderer on purpose: the canvas's own rule is "no furniture, ever".
# --------------------------------------------------------------------------

_WAVE = (14, 30, 22, 40, 18, 34, 26, 12, 38, 20, 30, 16, 42, 24, 14, 32)


def _waveform(F, color, delay_ms=0, fade_out_ms=None):
    bars = "".join('<div style="width:4px;height:%dpx;background:%s"></div>' % (h, color)
                   for h in _WAVE)
    fade = ("animation:yFade 300ms ease %dms both" % delay_ms
            if fade_out_ms is None else
            "animation:yFadeOut 600ms ease %dms both" % fade_out_ms)
    return ('<div style="position:absolute;left:%dpx;top:%dpx;display:flex;'
            'gap:6px;align-items:center;height:44px;%s">'
            '<span style="font-family:%s;font-size:22px;font-weight:800;'
            'letter-spacing:.2em;text-transform:uppercase;color:%s;'
            'margin-right:10px">AUDIO</span>%s</div>'
            % (F["side"], F["top"] - 34, fade, FONT_DISPLAY, color, bars))


def ed_jump(card, F):
    """Jump-cut furniture: three yellow ticks advance and the minute counter
    admits the skip. Furniture appears because the cut plays with time."""
    minutes = int(card.get("value") or 20)
    ticks = "".join(
        '<div style="width:26px;height:5px;background:%s;position:relative">'
        '<div style="position:absolute;inset:0;background:%s;opacity:0;'
        'animation:yCueFade 1ms linear %dms both"></div></div>'
        % (INERT, YELLOW, 400 + i * 800) for i in range(3))
    counters = "".join(
        '<span style="position:absolute;right:0;font-family:%s;font-size:24px;'
        'font-weight:800;letter-spacing:.16em;text-transform:uppercase;color:%s;'
        'opacity:0;animation:yHoldStep 800ms steps(1) %dms %s">%s</span>'
        % (FONT_DISPLAY, CHALK, 400 + i * 800,
           "forwards" if i == 2 else "none", "+%d min" % (minutes * (i + 1)))
        for i in range(3))
    return (
        ('<div style="position:absolute;right:%dpx;top:%dpx;display:flex;'
         'gap:10px;align-items:center;padding-right:120px;position:absolute">'
         '%s%s</div>' % (F["side"], F["top"] - 30, ticks, counters))
        + _eye_label(F, card.get("kicker") or "Jump cut · the ticks admit the skip",
                     "", card, 100, 0, YELLOW)
    )


def ed_j(card, F):
    """J-cut furniture: shot B's cyan waveform arrives before its picture.
    Place ending AT the cut; pair with the pipeline's audio_lead."""
    sub = card.get("text") or "next room, already talking…"
    return (
        _waveform(F, CYAN, 500)
        + ('<div style="position:absolute;left:%dpx;top:%dpx;font-family:%s;'
           'font-size:22px;font-weight:700;color:%s;'
           'animation:yFade 300ms ease 700ms both">%s</div>'
           % (F["side"], F["top"] + 26, FONT_DISPLAY, SLATE_300, _e(sub)))
        + _eye_label(F, card.get("kicker") or "J-cut · sound leads the picture",
                     "", card, 100, 0)
    )


def ed_l(card, F):
    """L-cut furniture: shot A's slate waveform hangs on over the new
    picture, then fades. Pair with audio_tail."""
    return (
        _waveform(F, SLATE_300, 0, fade_out_ms=2000)
        + _eye_label(F, card.get("kicker") or "L-cut · the last line carries over",
                     "", card, 100, 0)
    )


def ed_action(card, F):
    """Cut-on-action furniture: the yellow streak and box ride the movement
    across the splice — the eye follows the motion over the cut."""
    return (
        ('<div style="position:absolute;left:-240px;top:44%%;'
         'animation:yStreakAcross 1900ms %s 300ms both">'
         '<div style="position:absolute;right:40px;top:18px;width:190px;'
         'height:5px;background:%s;opacity:.9"></div>'
         '<div style="width:40px;height:40px;border:4px solid %s;'
         'box-sizing:border-box"></div></div>' % (EASE_RULE, YELLOW, YELLOW))
        + _eye_label(F, card.get("kicker") or "Cut on action · the eye rides the streak",
                     "", card, 100, 0, YELLOW)
    )


def ed_match(card, F):
    """Match-cut furniture: the crop marks hold the exact same box while the
    shot changes under them — same shape, same place."""
    return (
        _marks("40%", "28%", "20%", "40%", YELLOW, 200)
        + ('<div style="position:absolute;left:42%%;top:31%%;width:16%%;'
           'height:34%%;box-sizing:border-box;border:4px solid %s;'
           'animation:yArchToRing 600ms %s 1500ms both"></div>' % (CYAN, EASE_RULE))
        + _eye_label(F, card.get("kicker") or "Match cut · same shape, same box",
                     "", card, 100, 0)
    )


def ed_cutaway(card, F):
    """Cutaway furniture: the yellow inset frame and Meanwhile tag mark
    where the b-roll lands while shot A's audio keeps running. Place the
    b-roll itself with the desk's b-roll tool; this is its frame."""
    w, h = (int(F["w"] * 0.55), int(F["w"] * 0.55 * 9 / 16)) if F["portrait"] \
        else (640, 360)
    tag = card.get("kicker") or "Meanwhile"
    return (
        _waveform(F, SLATE_300)
        + ('<div style="position:absolute;right:%dpx;top:%dpx;width:%dpx;'
           'height:%dpx;animation:yPop 300ms %s 1000ms both">'
           '<div style="position:absolute;inset:0;border:4px solid %s"></div>'
           '<div style="position:absolute;left:0;bottom:-46px;font-family:%s;'
           'font-size:24px;font-weight:800;letter-spacing:.2em;'
           'text-transform:uppercase;color:%s">%s</div></div>'
           % (F["side"], F["top"] + 60, w, h, EASE_REVEAL, YELLOW,
              FONT_DISPLAY, YELLOW, _e(tag)))
        + _eye_label(F, "Cutaway · proof while he talks", "", card, 100, 0)
    )


def ed_cross(card, F):
    """Cross-cut furniture: the cyan rule splits the wings and the dim
    alternates sides — the active side holds full colour."""
    return (
        ('<div style="position:absolute;top:0;bottom:0;left:calc(50%% - 2px);'
         'width:4px;background:%s"></div>' % CYAN)
        + ('<div style="position:absolute;top:0;bottom:0;left:0;width:50%;'
           'background:rgba(11,35,64,.62);'
           'animation:yAlternate 1500ms steps(1) infinite"></div>')
        + ('<div style="position:absolute;top:0;bottom:0;right:0;width:50%;'
           'background:rgba(11,35,64,.62);'
           'animation:yAlternate 1500ms steps(1) 750ms infinite"></div>')
        + _eye_label(F, card.get("kicker") or "Cross-cut · two wings, one clock",
                     "", card, 100, 0)
    )


def ed_smash(card, F):
    """Smash-cut furniture: one yellow flash, two frames long, at the cut.
    That's the whole effect — silence smashes to chaos through it."""
    return (
        ('<div style="position:absolute;inset:0;background:%s;opacity:0;'
         'animation:yFlash 90ms steps(1) 1400ms forwards"></div>' % YELLOW)
        + _eye_label(F, card.get("kicker")
                     or "Smash cut · one yellow frame, that's the whole effect",
                     "", card, 100, 0, YELLOW)
    )


def ed_montage(card, F):
    """Montage: six quick rooms stack into the grid while the nine-room
    meter fills. Full-frame on navy — the one opaque ed_* screen, as the
    canvas draws it."""
    labels = card.get("items") or ["room one", "room two", "room three",
                                   "room four", "room five", "room six"]
    shades = ("#173456", "#0F3B44", "#3D3620")
    cells = "".join(
        '<div style="position:relative;overflow:hidden;opacity:0;'
        'animation:yCellIn 300ms %s %dms both">'
        '<div style="position:absolute;inset:0;background:%s;display:flex;'
        'align-items:center;justify-content:center;font-family:%s;'
        'font-size:20px;letter-spacing:.16em;text-transform:uppercase;'
        'color:rgba(234,244,255,.45)">%s</div>'
        '<div style="position:absolute;inset:0;border:4px solid %s;'
        'box-sizing:border-box;opacity:0;'
        'animation:yHoldStep 450ms steps(1) %dms none"></div></div>'
        % (EASE_REVEAL, i * 450, shades[i % 3], FONT_DISPLAY,
           _e(str(label)), YELLOW, i * 450)
        for i, label in enumerate(labels[:6]))
    meter = "".join(
        '<div style="width:20px;height:20px;border:2px solid %s;'
        'box-sizing:border-box;position:relative">'
        '<div style="position:absolute;inset:-2px;background:%s;opacity:0;'
        'animation:yCueFade 1ms linear %dms both"></div></div>'
        % (INERT, YELLOW, i * 450) for i in range(9))
    return (
        ('<div style="position:absolute;inset:0;background:%s"></div>' % NAVY)
        + ('<div style="position:absolute;left:%dpx;right:%dpx;top:%dpx;'
           'bottom:%dpx;display:grid;grid-template-columns:repeat(3,1fr);'
           'grid-template-rows:1fr 1fr;gap:18px">%s</div>'
           % (F["side"], F["side"], F["top"], F["bottom"] + 150, cells))
        + ('<div style="position:absolute;left:0;right:0;bottom:%dpx;'
           'display:flex;justify-content:center;gap:10px">%s</div>'
           % (F["bottom"] + 20, meter))
        + _eye_label(F, card.get("kicker") or "Montage · six rooms in three seconds",
                     "", card, 100, 0)
    )


# --------------------------------------------------------------------------
# registry — merged into overlay_kit.RENDERERS (which stays authoritative)
# --------------------------------------------------------------------------

VFX_RENDERERS = {
    "fx_punch": fx_punch, "fx_freeze": fx_freeze, "fx_spotlight": fx_spotlight,
    "fx_ramp": fx_ramp, "fx_rewind": fx_rewind, "fx_shake": fx_shake,
    "fx_letterbox": fx_letterbox, "fx_glitch": fx_glitch,
    "fx_underline": fx_underline, "fx_pause": fx_pause,
    "cut_arch": cut_arch, "cut_flood": cut_flood, "cut_crop": cut_crop,
    "cut_wave": cut_wave, "cut_colonnade": cut_colonnade,
    "cut_doors": cut_doors, "cut_meter": cut_meter,
    "cut_ruledrop": cut_ruledrop, "cut_bracket": cut_bracket,
    "cut_marks": cut_marks, "cut_scrim": cut_scrim, "cut_figure": cut_figure,
    "cut_slices": cut_slices, "cut_split": cut_split,
    "ed_jump": ed_jump, "ed_j": ed_j, "ed_l": ed_l, "ed_action": ed_action,
    "ed_match": ed_match, "ed_cutaway": ed_cutaway, "ed_cross": ed_cross,
    "ed_smash": ed_smash, "ed_montage": ed_montage,
}

# Starter copy per screen (the picker's hover previews render these) with
# the canvas's own demo lines, and each scene's canvas duration.
VFX_TEMPLATES = {
    "fx_punch": {"kicker": "Punch-in · cut on the beat", "text": "Look closer.",
                 "duration": 3.5},
    "fx_freeze": {"kicker": "Yep, that's us",
                  "text": "You're probably wondering how we got here.",
                  "duration": 4},
    "fx_spotlight": {"kicker": "Ignore everything else",
                     "text": "This one. This is the one.", "duration": 4},
    "fx_ramp": {"kicker": "4× · rooms 4 through 7",
                "text": "Nothing happened in these.", "duration": 3.5},
    "fx_rewind": {"text": "Hold on. Rewind.", "duration": 3},
    "fx_shake": {"stat": "65 million", "text": "years. In a hallway.",
                 "duration": 3.5},
    "fx_letterbox": {"text": "It wasn't on the map.", "duration": 4},
    "fx_glitch": {"kicker": "Footage recovered · room nine",
                  "text": "This is the only shot we have.", "duration": 4},
    "fx_underline": {"text": "They never counted the rooms.",
                     "underline": "counted", "duration": 3.5},
    "fx_pause": {"text": "Pause it. Read the last line.",
                 "subtext": "We'll wait in the comments.", "duration": 3.5},
    "cut_arch": {"duration": 3}, "cut_flood": {"duration": 2.5},
    "cut_crop": {"duration": 2.5}, "cut_wave": {"duration": 2.5},
    "cut_colonnade": {"duration": 3}, "cut_doors": {"duration": 2.5},
    "cut_meter": {"duration": 3}, "cut_ruledrop": {"duration": 2.5},
    "cut_bracket": {"duration": 2.5}, "cut_marks": {"duration": 2.5},
    "cut_scrim": {"duration": 2.5}, "cut_figure": {"duration": 3},
    "cut_slices": {"duration": 2.5}, "cut_split": {"duration": 2.5},
    "ed_jump": {"value": 20, "duration": 3},
    "ed_j": {"text": "next room, already talking…", "duration": 3},
    "ed_l": {"duration": 3}, "ed_action": {"duration": 2.5},
    "ed_match": {"duration": 3},
    "ed_cutaway": {"kicker": "Meanwhile", "duration": 3},
    "ed_cross": {"duration": 3}, "ed_smash": {"duration": 2.5},
    "ed_montage": {"items": ["room one", "room two", "room three",
                             "room four", "room five", "room six"],
                   "duration": 3.5},
}

VFX_GROUPS = [
    {"title": "Effects", "kits": [k for k in VFX_TEMPLATES if k.startswith("fx_")]},
    {"title": "Transitions", "kits": [k for k in VFX_TEMPLATES if k.startswith("cut_")]},
    {"title": "Cut furniture", "kits": [k for k in VFX_TEMPLATES if k.startswith("ed_")]},
]

# Keyframes the pack adds to the kit page (y-prefixed like the kit's own).
VFX_KEYFRAMES = """
@keyframes yFadeOut{from{opacity:1}to{opacity:0}}
@keyframes yCueFade{from{opacity:0}to{opacity:1}}
@keyframes yFlicker{0%{opacity:1}14%{opacity:1}15%{opacity:0}100%{opacity:0}}
@keyframes yBlink{0%{opacity:1}33%{opacity:1}34%{opacity:.3}100%{opacity:.3}}
@keyframes yPulse{from{opacity:.5}to{opacity:1}}
@keyframes yScrub{from{clip-path:inset(0 0 0 100%)}to{clip-path:inset(0 0 0 0)}}
@keyframes yStreak{from{transform:translateX(0)}to{transform:translateX(260vw)}}
@keyframes yWindow{from{opacity:0}to{opacity:1}}
@keyframes yArchGrow{from{transform:translateX(-50%) scale(1)}to{transform:translateX(-50%) scale(19)}}
@keyframes yCoverBridge{0%,35%{opacity:1}100%{opacity:0}}
@keyframes ySweepUp{from{transform:translateY(100%)}to{transform:translateY(-100%)}}
@keyframes yMarksBlow{0%{transform:translate(-50%,-50%) scale(1);opacity:1}80%{opacity:1}100%{transform:translate(-50%,-50%) scale(5.2);opacity:0}}
@keyframes yDip{0%{opacity:0}25%{opacity:.85}75%{opacity:.85}100%{opacity:0}}
@keyframes yBarRiseFall{0%{transform:scaleY(0)}38%{transform:scaleY(1)}62%{transform:scaleY(1)}100%{transform:scaleY(0)}}
@keyframes yRowIn{from{transform:translateX(900px);opacity:0}to{transform:translateX(0);opacity:1}}
@keyframes yDropCover{from{transform:translateY(0)}to{transform:translateY(100%)}}
@keyframes yDropRule{from{transform:translateY(0)}to{transform:translateY(102vh)}}
@keyframes ySlideInL{from{transform:translateX(0)}to{transform:translateX(100%)}}
@keyframes ySlideInR{from{transform:translateX(0)}to{transform:translateX(-100%)}}
@keyframes yMarksInOut{0%{transform:translate(-50%,-50%) scale(1);opacity:0}12%{opacity:1}38%{transform:translate(-50%,-50%) scale(.22)}62%{transform:translate(-50%,-50%) scale(.22)}88%{opacity:1}100%{transform:translate(-50%,-50%) scale(1);opacity:0}}
@keyframes ySlideAcross{from{transform:translateX(0)}to{transform:translateX(102%)}}
@keyframes yWalkX{from{transform:translateX(0)}to{transform:translateX(104vw)}}
@keyframes yBob{from{transform:translateY(0)}to{transform:translateY(-7px)}}
@keyframes ySliceL{from{transform:translateX(-100%)}to{transform:translateX(100%)}}
@keyframes ySliceR{from{transform:translateX(100%)}to{transform:translateX(-100%)}}
@keyframes yCloseTop{0%{transform:translateY(-100%)}25%{transform:translateY(0)}60%{transform:translateY(0)}100%{transform:translateY(-100%)}}
@keyframes yCloseBottom{0%{transform:translateY(100%)}25%{transform:translateY(0)}60%{transform:translateY(0)}100%{transform:translateY(100%)}}
@keyframes yHoldStep{0%{opacity:1}99%{opacity:1}100%{opacity:0}}
@keyframes yStreakAcross{from{transform:translateX(0)}to{transform:translateX(120vw)}}
@keyframes yArchToRing{from{border-radius:150px 150px 0 0}to{border-radius:999px}}
@keyframes yAlternate{0%{opacity:0}50%{opacity:1}100%{opacity:0}}
@keyframes yFlash{0%{opacity:1}100%{opacity:0}}
@keyframes yCellIn{from{opacity:0;transform:scale(.94)}to{opacity:1;transform:scale(1)}}
"""


# ---------------------------------------------------------------------------
# Registration — the pack merges itself into the kit. This lives HERE, not
# in overlay_kit, so both import orders survive the cycle: whichever module
# loads first, these lines run exactly once, after every name above exists.
# ---------------------------------------------------------------------------
from . import overlay_kit as _kit  # noqa: E402

_kit.RENDERERS.update(VFX_RENDERERS)
_kit.KEYFRAMES = _kit.KEYFRAMES + VFX_KEYFRAMES
