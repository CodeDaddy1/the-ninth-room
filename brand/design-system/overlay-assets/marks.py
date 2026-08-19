"""Vector replacements for the Overlay Kit's raster marks.

Why these exist: the kit's PNG assets (butterfly, dashed arrow, rosette, seal,
folder) are larger than the 256 KiB ceiling on reading a file back out of a
Claude Design project, so they arrive truncated and unusable. Redrawing them
as inline SVG is not a workaround — it is the better asset for this pipeline:

  * no transfer limit, and nothing to keep in sync with the design project
  * resolution-independent, so the same mark is sharp at 1080p and 4K
  * recolorable from brand tokens instead of baked-in pixels
  * animatable per-part — the butterfly's wings flap independently, and the
    dashed trail draws itself with stroke-dashoffset, which a flat PNG cannot do

Each function returns an SVG string sized to its slot. Swap any of these for
the original artwork later by dropping the file in this directory and pointing
the kit at it; nothing else changes.
"""
from __future__ import annotations

ACCENT = "#12B76A"
INK = "#09090B"
CREAM = "#FCFCFA"


def butterfly(size: int = 120, color: str = ACCENT) -> str:
    """A simple symmetrical silhouette whose wing pairs animate separately.

    The kit flaps the whole PNG with `bFlap`; here each wing group has its own
    transform origin at the body, so the flap reads as wings hinging rather
    than the whole image squashing.
    """
    return """
<svg viewBox="0 0 120 120" width="%(size)d" height="%(size)d" fill="none"
     xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
  <g fill="%(color)s">
    <g class="wing-l" style="transform-origin:60px 60px">
      <path d="M58 58C48 30 26 16 14 22 2 28 4 52 18 64c9 8 24 10 40 2z"/>
      <path d="M58 64C50 82 34 96 22 94 10 92 10 76 20 68c8-6 22-8 38-4z"/>
    </g>
    <g class="wing-r" style="transform-origin:60px 60px">
      <path d="M62 58c10-28 32-42 44-36 12 6 10 30-4 42-9 8-24 10-40 2z"/>
      <path d="M62 64c8 18 24 32 36 30 12-2 12-18 2-26-8-6-22-8-38-4z"/>
    </g>
    <ellipse cx="60" cy="62" rx="4.5" ry="22"/>
    <path d="M60 42c-3-8-8-13-13-15M60 42c3-8 8-13 13-15" stroke="%(color)s"
          stroke-width="2.5" stroke-linecap="round" fill="none"/>
  </g>
</svg>""" % {"size": size, "color": color}


def dashed_arrow(width: int = 1000, color: str = ACCENT) -> str:
    """The flight trail: a dashed curve that draws itself, plus a head.

    `pathLength="100"` normalises the dash math so the draw-on animation is
    the same regardless of how the curve is scaled.
    """
    return """
<svg viewBox="0 0 1000 300" width="%(w)d" height="%(h)d" fill="none"
     xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
  <path class="trail" pathLength="100"
        d="M20 250C170 250 250 60 430 60S760 210 960 90"
        stroke="%(color)s" stroke-width="7" stroke-linecap="round"
        stroke-dasharray="6 10"/>
  <path d="M930 66l32 24-36 20" stroke="%(color)s" stroke-width="7"
        stroke-linecap="round" stroke-linejoin="round"/>
</svg>""" % {"w": width, "h": int(width * 0.3), "color": color}


def rosette(size: int = 150, color: str = ACCENT, label: str = "1st") -> str:
    """An award rosette for the scoreboard's winner."""
    points = []
    import math
    for i in range(12):
        a = math.radians(i * 30)
        points.append("%.1f,%.1f" % (75 + 46 * math.cos(a), 62 + 46 * math.sin(a)))
    return """
<svg viewBox="0 0 150 150" width="%(size)d" height="%(size)d" fill="none"
     xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
  <g>
    %(petals)s
    <circle cx="75" cy="62" r="34" fill="%(color)s"/>
    <circle cx="75" cy="62" r="34" fill="none" stroke="%(ink)s" stroke-opacity=".25" stroke-width="2"/>
    <text x="75" y="72" text-anchor="middle" font-family="Gabarito, sans-serif"
          font-size="27" font-weight="800" fill="%(cream)s">%(label)s</text>
    <path d="M56 92l-12 46 31-17 31 17-12-46" fill="%(color)s"/>
  </g>
</svg>""" % {"size": size, "color": color, "ink": INK, "cream": CREAM,
             "label": label,
             "petals": "".join(
                 '<circle cx="%.1f" cy="%.1f" r="17" fill="%s" fill-opacity=".55"/>'
                 % (float(p.split(",")[0]), float(p.split(",")[1]), color)
                 for p in points)}


def seal(size: int = 170, color: str = ACCENT, label: str = "TRUE") -> str:
    """A wax-seal style stamp for verdicts (kit screen 12)."""
    return """
<svg viewBox="0 0 170 170" width="%(size)d" height="%(size)d" fill="none"
     xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
  <circle cx="85" cy="85" r="72" fill="%(color)s"/>
  <circle cx="85" cy="85" r="72" fill="none" stroke="%(ink)s" stroke-opacity=".28" stroke-width="3"/>
  <circle cx="85" cy="85" r="58" fill="none" stroke="%(cream)s" stroke-opacity=".55"
          stroke-width="2" stroke-dasharray="5 7"/>
  <text x="85" y="95" text-anchor="middle" font-family="Gabarito, sans-serif"
        font-size="30" font-weight="800" fill="%(cream)s"
        letter-spacing="1">%(label)s</text>
</svg>""" % {"size": size, "color": color, "ink": INK, "cream": CREAM, "label": label}


def folder(width: int = 660, color: str = ACCENT) -> str:
    """The case-file folder the stamp lands on (kit screen 12)."""
    return """
<svg viewBox="0 0 660 420" width="%(w)d" height="%(h)d" fill="none"
     xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
  <path d="M24 92c0-13 11-24 24-24h188l38 40h362c13 0 24 11 24 24v264c0 13-11 24-24 24H48
           c-13 0-24-11-24-24z" fill="#1D1D20" stroke="%(cream)s" stroke-opacity=".16" stroke-width="2"/>
  <rect x="70" y="150" width="300" height="12" rx="6" fill="%(cream)s" fill-opacity=".22"/>
  <rect x="70" y="188" width="460" height="12" rx="6" fill="%(cream)s" fill-opacity=".14"/>
  <rect x="70" y="226" width="380" height="12" rx="6" fill="%(cream)s" fill-opacity=".14"/>
  <rect x="70" y="264" width="240" height="12" rx="6" fill="%(color)s" fill-opacity=".55"/>
</svg>""" % {"w": width, "h": int(width * 420 / 660), "color": color, "cream": CREAM}
