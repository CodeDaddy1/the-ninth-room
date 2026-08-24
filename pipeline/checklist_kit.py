# -*- coding: utf-8 -*-
"""Checklist cards & the room map — the season's one-thread engagement set.

Source of truth: the **Checklist Cards & Room Map** canvas on
claude.ai/design (project e9501d68-5f42-4314-8ac3-90bbef2b04e3), ported
2026-08-23 the same way the Cyanotype kit and the VFX pack were: same
geometry, same keyframes, same delays, copy parameterised. Design it there
first; re-implement what comes back — never the other way round.

Five beats that carry one thread through an episode:

  hit_list     opens the room — three to five items, the last one seeds the
               ninth-room thread; the counter reads 0 / N.
  check_off    fires the moment an item is found. Low-left over live
               footage; the yellow chip is the frame's one yellow moment.
  check_recap  closes the room — found items dim, the one still open holds
               the yellow outline and carries the tension forward.
  room_map     the season at a glance, run as a chapter beat every episode:
               rooms done fill yellow, this week's room takes the cyan
               outline, and the ninth slot stays off the map.
  map_payoff   the reveal. Eight known rooms fall back and light floods up
               the ninth passage — the only motion and the only yellow.

Data model (all fields ride the Studio card editor's existing controls):
  rows      [{label}] — the checklist items / the eight room names
  active    how many are found (hit_list starts at 0; check_recap dims the
            first `active` rows) — and, on room_map, this week's room number
  chapters  check_off only: total squares in the progress strip
  tag       check_recap: the label on the still-open row ("Still locked")
  shape     room_map: "arch" (default) or "square" tiles
  text/kicker/subtext as everywhere; empty map headlines are derived the
  way the canvas's logic derived them.

The check-off chip and the map tiles are filled yellow shapes carrying
text. That is not a plate creeping back in: like the quiz flood and the
poll bar, the fill IS the subject of the frame (design-system rule 1's own
carve-out), sanctioned on the canvas itself.

Fill-mode doctrine (learned porting the VFX pack, 2026-08-23): every
animation here is a REVEAL whose 0% frame hides the element, so
`both` fill is correct throughout — nothing paints before its delay and
nothing needs the bridge/snap machinery the cover transitions use.

This module registers itself into overlay_kit.RENDERERS at its own tail
(the vfx_kit pattern) so either import order survives the cycle.
"""
from __future__ import annotations

from .overlay_kit import (
    CHALK,
    CYAN,
    EASE_REVEAL,
    FONT_DISPLAY,
    NAVY,
    NAVY_700,
    SHADOW_CHALK,
    SHADOW_DISPLAY,
    SLATE_300,
    SLATE_400,
    SLATE_500,
    YELLOW,
    _display,
    _e,
    _eyebrow,
    _fit,
    _fscale,
)

INERT_BORDER = "rgba(234,244,255,.4)"     # a row nobody has checked yet
BOX_BORDER = "rgba(234,244,255,.55)"      # the empty checkbox
DIM_BORDER = "rgba(234,244,255,.22)"      # a row already resolved
SQUARE_BORDER = "rgba(234,244,255,.34)"   # an unfilled progress square

_NUM_WORDS = ("one", "two", "three", "four", "five", "six",
              "seven", "eight", "nine", "ten", "eleven", "twelve")


def _word(n: "int") -> str:
    return _NUM_WORDS[n - 1] if 1 <= n <= len(_NUM_WORDS) else str(n)


def _labels(card: "dict") -> "list[str]":
    """The item list. `rows` is the editable field; strings tolerated."""
    out = []
    for r in card.get("rows") or []:
        if isinstance(r, dict):
            out.append(str(r.get("label", "")))
        else:
            out.append(str(r))
    return [x for x in out if x.strip()]


def _num(card: "dict", key: str, default: int) -> int:
    try:
        return int(float(card.get(key, default)))
    except (TypeError, ValueError):
        return default


def _head(card: "dict", F: "dict", default_kicker: str, default_text: str,
          top: int, size: int = 80, gap: int = 24) -> "tuple":
    """Eyebrow + headline column, centered — the checklist screens' opener.

    Same portrait clamp as _engagement_head: content authored below 180px
    or it renders under the Shorts chrome.
    """
    top = max(top, F["top"]) if F["portrait"] else top
    text = card.get("text") or default_text
    head = (
        '<div style="position:absolute;left:%(side)dpx;right:%(side)dpx;'
        'top:%(top)dpx;display:flex;flex-direction:column;align-items:center;'
        'gap:%(gap)dpx">%(eyebrow)s'
        '<div style="%(display)s;text-align:center">%(text)s</div>'
        % {"side": F["side"], "top": top, "gap": gap,
           "eyebrow": _eyebrow(card.get("kicker") or default_kicker,
                               CYAN, 0, 26, centered=True),
           "display": _display(_fit(text, size, lines=2, budget=F["inner"],
                                    fscale=_fscale(card)))
                      + ";animation:yUp 320ms %s 120ms both" % EASE_REVEAL,
           "text": _e(text)})
    return head, "</div>"


# --- 01 · the hit list ------------------------------------------------------

def hit_list(card: "dict", F: "dict") -> str:
    """Opens the room: the items we came for, all boxes empty, 0 / N.

    The last item always seeds the ninth-room thread — that is editorial
    policy, not code; the renderer draws whatever rows it is given.
    """
    items = _labels(card) or ["The one thing we came to see"]
    found = max(0, min(_num(card, "active", 0), len(items)))
    width = min(1200, F["inner"])
    fs = _fscale(card)
    rows = []
    for i, label in enumerate(items):
        rows.append(
            '<div style="display:flex;align-items:center;gap:26px;'
            'border:3px solid %(border)s;padding:16px 32px;'
            'animation:yUp 280ms %(ease)s %(delay)dms both">'
            '<div style="box-sizing:border-box;width:40px;height:40px;'
            'border:3px solid %(box)s;flex-shrink:0"></div>'
            '<span style="font-family:%(font)s;font-size:%(size)dpx;'
            'font-weight:700;color:%(chalk)s;text-shadow:%(shadow)s">'
            '%(label)s</span>'
            '<span style="margin-left:auto;font-family:%(font)s;'
            'font-size:26px;font-weight:800;letter-spacing:.2em;'
            'color:%(slate)s">%(nn)02d</span></div>'
            % {"border": INERT_BORDER, "box": BOX_BORDER,
               "ease": EASE_REVEAL, "delay": 280 + i * 100,
               "font": FONT_DISPLAY,
               "size": _fit(label, 46, budget=width - 220, fscale=fs),
               "chalk": CHALK, "shadow": SHADOW_CHALK, "label": _e(label),
               "slate": SLATE_400, "nn": i + 1})
    head, close = _head(card, F, "The hit list",
                        "%s things we came to see" % _word(len(items)).capitalize(),
                        140)
    return head + (
        '<div style="display:flex;flex-direction:column;gap:16px;'
        'width:%dpx;margin-top:8px">%s</div>'
        '<div style="font-family:%s;font-size:46px;font-weight:800;'
        'letter-spacing:-.04em;color:%s;text-shadow:%s;'
        'animation:yUp 280ms %s %dms both">%d / %d</div>'
        % (width, "".join(rows), FONT_DISPLAY, YELLOW, SHADOW_CHALK,
           EASE_REVEAL, 300 + len(items) * 100, found, len(items))) + close


# --- 02 · the check-off -----------------------------------------------------

def check_off(card: "dict", F: "dict") -> str:
    """Fires when an item is found. Low-left over live footage; the chip is
    the frame's one yellow moment (the fill is the subject, not a plate).

    `active` of `chapters` squares are filled; the kicker usually says the
    same thing in words ("Found it · two of four").
    """
    total = max(1, min(_num(card, "chapters", 4), 12))
    found = max(0, min(_num(card, "active", 2), total))
    text = card.get("text") or "The thing we just found"
    squares = "".join(
        ('<div style="width:20px;height:20px;background:%s"></div>' % YELLOW)
        if i < found else
        ('<div style="box-sizing:border-box;width:20px;height:20px;'
         'border:2px solid %s"></div>' % SQUARE_BORDER)
        for i in range(total))
    left = 120 if not F["portrait"] else F["side"]
    bottom = 150 if not F["portrait"] else F["bottom"] + 60
    kicker = card.get("kicker") or (
        "Found it · %s of %s" % (_word(found), _word(total)))
    return (
        '<div style="position:absolute;left:%(left)dpx;bottom:%(bottom)dpx;'
        'display:flex;flex-direction:column;align-items:flex-start;gap:20px">'
        '%(eyebrow)s'
        '<div style="background:%(yellow)s;padding:14px 30px;'
        'animation:yPop 320ms %(ease)s 160ms both">'
        '<span style="font-family:%(font)s;font-size:%(size)dpx;'
        'font-weight:800;letter-spacing:-.04em;color:%(navy)s">%(text)s</span>'
        '</div>'
        '<div style="display:flex;gap:7px;animation:yFade 220ms ease 420ms '
        'both">%(squares)s</div></div>'
        % {"left": left, "bottom": bottom,
           "eyebrow": _eyebrow(kicker, CYAN, 0, 26),
           "yellow": YELLOW, "ease": EASE_REVEAL, "font": FONT_DISPLAY,
           "size": _fit(text, 46, budget=F["inner"] - 240,
                        fscale=_fscale(card)),
           "navy": NAVY, "text": _e(text), "squares": squares})


# --- 03 · the recap ---------------------------------------------------------

def check_recap(card: "dict", F: "dict") -> str:
    """Closes the room. The first `active` rows are found and dim; every row
    after them still holds the yellow outline and the `tag` ("Still locked"),
    carrying the tension into the next episode.
    """
    items = _labels(card) or ["The one that got away"]
    found = max(0, min(_num(card, "active", len(items) - 1), len(items)))
    tag = card.get("tag") or "Still locked"
    width = min(1200, F["inner"])
    fs = _fscale(card)
    rows = []
    for i, label in enumerate(items):
        done = i < found
        delay = 280 + i * 100 + (0 if done else 40)
        if done:
            rows.append(
                '<div style="display:flex;align-items:center;gap:26px;'
                'border:3px solid %(border)s;padding:16px 32px;'
                'animation:yUp 280ms %(ease)s %(delay)dms both">'
                '<div style="width:40px;height:40px;background:%(yellow)s;'
                'flex-shrink:0"></div>'
                '<span style="font-family:%(font)s;font-size:%(size)dpx;'
                'font-weight:700;color:%(chalk)s;opacity:.55">%(label)s</span>'
                '</div>'
                % {"border": DIM_BORDER, "ease": EASE_REVEAL, "delay": delay,
                   "yellow": YELLOW, "font": FONT_DISPLAY,
                   "size": _fit(label, 46, budget=width - 160, fscale=fs),
                   "chalk": CHALK, "label": _e(label)})
        else:
            rows.append(
                '<div style="display:flex;align-items:center;gap:26px;'
                'border:3px solid %(yellow)s;padding:16px 32px;'
                'animation:yUp 280ms %(ease)s %(delay)dms both">'
                '<div style="box-sizing:border-box;width:40px;height:40px;'
                'border:3px solid rgba(234,244,255,.7);flex-shrink:0"></div>'
                '<span style="font-family:%(font)s;font-size:%(size)dpx;'
                'font-weight:700;color:%(chalk)s;text-shadow:%(shadow)s">'
                '%(label)s</span>'
                '<span style="margin-left:auto;font-family:%(font)s;'
                'font-size:24px;font-weight:800;letter-spacing:.22em;'
                'color:%(cyan)s">%(tag)s</span></div>'
                % {"yellow": YELLOW, "ease": EASE_REVEAL, "delay": delay,
                   "font": FONT_DISPLAY,
                   "size": _fit(label, 46, budget=width - 380, fscale=fs),
                   "chalk": CHALK, "shadow": SHADOW_CHALK,
                   "label": _e(label), "cyan": CYAN, "tag": _e(tag)})
    open_n = len(items) - found
    default_head = ("%s found. %s left." % (
        _word(found).capitalize(),
        ("One door" if open_n == 1 else "%s doors" % _word(max(open_n, 1)).capitalize())))
    head, close = _head(card, F, "Before we go", default_head, 140)
    return head + (
        '<div style="display:flex;flex-direction:column;gap:16px;'
        'width:%dpx;margin-top:8px">%s</div>' % (width, "".join(rows))) + close


# --- 04 · the map — all rooms ----------------------------------------------

def _tiles(card: "dict", F: "dict") -> "tuple":
    """Shared tile geometry: names, sizes, and the arch/square radius."""
    names = _labels(card) or ["Great hall", "Fossils", "Gem vault",
                              "Deep sea", "Clockworks", "Old maps",
                              "Armory", "Archives"]
    names = names[:8]
    if F["portrait"]:
        # cells sized so nine tiles AND their uppercase labels clear a
        # 936px portrait inner width — 16px labels collided at 88px cells
        geo = {"tw": 84, "th": 105, "cell": 92, "gap": 10,
               "label": 13, "num": 24, "pad": 10}
    else:
        geo = {"tw": 120, "th": 150, "cell": 126, "gap": 28,
               "label": 24, "num": 34, "pad": 16}
    arch = str(card.get("shape") or "arch").strip().lower() != "square"
    geo["radius"] = ("%dpx %dpx 0 0" % (geo["tw"] // 2, geo["tw"] // 2)
                     if arch else "0")
    return names, geo


def _tile(geo: "dict", i: int, box: str, num_html: str,
          label: str, label_color: str) -> str:
    return (
        '<div style="display:flex;flex-direction:column;align-items:center;'
        'gap:16px;width:%(cell)dpx;animation:yUp 280ms %(ease)s %(delay)dms '
        'both">'
        '<div style="position:relative;overflow:hidden;box-sizing:border-box;'
        'width:%(tw)dpx;height:%(th)dpx;border-radius:%(radius)s;%(box)s'
        'display:flex;align-items:flex-end;justify-content:center;'
        'padding-bottom:%(pad)dpx">%(num)s</div>'
        '<div style="font-family:%(font)s;font-size:%(label_size)dpx;'
        'font-weight:700;letter-spacing:.08em;text-transform:uppercase;'
        'text-align:center;line-height:1.25;color:%(label_color)s;'
        'text-shadow:%(shadow)s">%(label)s</div></div>'
        % {"cell": geo["cell"], "ease": EASE_REVEAL, "delay": 320 + i * 80,
           "tw": geo["tw"], "th": geo["th"], "radius": geo["radius"],
           "box": box, "pad": geo["pad"], "num": num_html,
           "font": FONT_DISPLAY, "label_size": geo["label"],
           "label_color": label_color, "shadow": SHADOW_CHALK,
           "label": _e(label)})


def _tile_num(geo: "dict", n: "int | str", color: str) -> str:
    return ('<span style="position:relative;font-family:%s;font-size:%dpx;'
            'font-weight:800;color:%s">%s</span>'
            % (FONT_DISPLAY, geo["num"], color, n))


def room_map(card: "dict", F: "dict") -> str:
    """The season at a glance. Rooms before `active` fill yellow, `active`
    takes the cyan outline, the rest wait, and the ninth slot stays off the
    map. Headline and support derive from `active` when left empty.
    """
    names, geo = _tiles(card, F)
    cur = max(1, min(_num(card, "active", 5), len(names)))
    tiles = []
    for i, name in enumerate(names):
        n = i + 1
        if n < cur:
            tiles.append(_tile(geo, i, "background:%s;" % YELLOW,
                               _tile_num(geo, n, NAVY), name, CHALK))
        elif n == cur:
            tiles.append(_tile(geo, i, "border:3px solid %s;" % CYAN,
                               _tile_num(geo, n, CYAN), name, CHALK))
        else:
            tiles.append(_tile(geo, i,
                               "border:3px solid rgba(234,244,255,.28);",
                               _tile_num(geo, n, SLATE_400), name, SLATE_400))
    tiles.append(_tile(geo, len(names),
                       "border:3px solid %s;" % NAVY_700, "",
                       "Not on the map", SLATE_500))
    default_head = ("%s rooms on the map" % _word(len(names)).capitalize()
                    if cur < len(names)
                    else "%s down. The map ends here." % _word(len(names)).capitalize())
    support = card.get("subtext") or (
        "Room %s this week. Guess before we do." % _word(cur))
    head, close = _head(card, F, "The map", default_head, 150, gap=30)
    return head + (
        '<div style="display:flex;align-items:flex-start;justify-content:'
        'center;flex-wrap:wrap;gap:%dpx;margin-top:14px;max-width:%dpx">'
        '%s</div>'
        '<div style="font-family:%s;font-size:34px;font-weight:600;color:%s;'
        'text-shadow:%s;animation:yFade 260ms ease 1100ms both">%s</div>'
        % (geo["gap"], F["inner"], "".join(tiles),
           FONT_DISPLAY, SLATE_300, SHADOW_CHALK, _e(support))) + close


# --- 05 · the payoff --------------------------------------------------------

def map_payoff(card: "dict", F: "dict") -> str:
    """The reveal. The eight known rooms fall back; light floods up the
    ninth passage — the only motion and the only yellow in the frame.
    """
    names, geo = _tiles(card, F)
    tiles = []
    for i, name in enumerate(names):
        tiles.append(_tile(geo, i,
                           "border:3px solid rgba(234,244,255,.24);",
                           _tile_num(geo, i + 1, "rgba(234,244,255,.35)"),
                           name, "rgba(124,155,188,.6)"))
    flood = ('<div style="position:absolute;inset:0;background:%s;'
             'transform-origin:bottom;animation:yGrowY 520ms %s 1150ms both">'
             '</div>' % (YELLOW, EASE_REVEAL))
    tiles.append(_tile(geo, len(names),
                       "border:3px solid %s;" % YELLOW,
                       flood + _tile_num(geo, len(names) + 1, NAVY),
                       "Room %s" % _word(len(names) + 1), YELLOW))
    head, close = _head(card, F, "Found it", "It was never on the map.",
                        150, size=90, gap=30)
    support = card.get("subtext") or ""
    tail = (
        '<div style="font-family:%s;font-size:34px;font-weight:600;color:%s;'
        'text-shadow:%s;animation:yFade 260ms ease 1700ms both">%s</div>'
        % (FONT_DISPLAY, SLATE_300, SHADOW_CHALK, _e(support))
        if support else "")
    return head + (
        '<div style="display:flex;align-items:flex-start;justify-content:'
        'center;flex-wrap:wrap;gap:%dpx;margin-top:14px;max-width:%dpx">'
        '%s</div>' % (geo["gap"], F["inner"], "".join(tiles))) + tail + close


# --- registration -----------------------------------------------------------

CHECKLIST_RENDERERS = {
    "hit_list": hit_list,
    "check_off": check_off,
    "check_recap": check_recap,
    "room_map": room_map,
    "map_payoff": map_payoff,
}

# Demo copy straight off the canvas, durations sized to each screen's last
# delay plus a beat of hold.
CHECKLIST_TEMPLATES = {
    "hit_list": {
        "kicker": "Room four · the hit list",
        "text": "Four things we came to see",
        "rows": [{"label": "The blue whale heart"},
                 {"label": "A rock 4.6bn years old, give or take"},
                 {"label": "The clockwork librarian"},
                 {"label": "A door with no handle"}],
        "active": 0, "duration": 4,
    },
    "check_off": {
        "kicker": "Found it · two of four",
        "text": "A rock 4.6bn years old, give or take",
        "active": 2, "chapters": 4, "duration": 3,
    },
    "check_recap": {
        "kicker": "Room four · before we go",
        "text": "Three found. One door left.",
        "rows": [{"label": "The blue whale heart"},
                 {"label": "A rock 4.6bn years old, give or take"},
                 {"label": "The clockwork librarian"},
                 {"label": "A door with no handle"}],
        "active": 3, "tag": "Still locked", "duration": 4,
    },
    "room_map": {
        "kicker": "The Ninth Room · the map",
        "text": "",
        "rows": [{"label": "Great hall"}, {"label": "Fossils"},
                 {"label": "Gem vault"}, {"label": "Deep sea"},
                 {"label": "Clockworks"}, {"label": "Old maps"},
                 {"label": "Armory"}, {"label": "Archives"}],
        "active": 5, "shape": "arch", "subtext": "", "duration": 4.5,
    },
    "map_payoff": {
        "kicker": "Room nine · found it",
        "text": "It was never on the map.",
        "rows": [{"label": "Great hall"}, {"label": "Fossils"},
                 {"label": "Gem vault"}, {"label": "Deep sea"},
                 {"label": "Clockworks"}, {"label": "Old maps"},
                 {"label": "Armory"}, {"label": "Archives"}],
        "subtext": "The door with no handle opens next week.",
        "duration": 5,
    },
}

CHECKLIST_GROUPS = [
    {"title": "Checklist & map",
     "kits": ["hit_list", "check_off", "check_recap",
              "room_map", "map_payoff"]},
]

# ---------------------------------------------------------------------------
# Registration — the set merges itself into the kit at ITS tail (the vfx_kit
# pattern): whichever module loads first, these lines run exactly once,
# after every name above exists. The canvas frames all five over a scrim;
# check_off sits low like a lower third and takes the band, the rest are
# center-format like the engagement cards.
# ---------------------------------------------------------------------------
from . import overlay_kit as _kit  # noqa: E402

_kit.RENDERERS.update(CHECKLIST_RENDERERS)
_kit.SCRIM_CENTER |= {"hit_list", "check_recap", "room_map", "map_payoff"}
_kit.SCRIM_BAND |= {"check_off"}
