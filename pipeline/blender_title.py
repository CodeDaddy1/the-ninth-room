"""A 3D title card built from the flat kit's own numbers.

The flat title (`overlay_kit.transition`) is chalk Bricolage at 120px,
tracked -.055em, 140px from the left edge, a cyan rule-and-eyebrow above it,
a double navy shadow under it, rising 16px on `ease-reveal` with the eyebrow
200ms ahead. This module hands exactly those numbers to Blender — colours,
font file, sizes, easing curve, shadow offsets — and Blender adds the one
thing CSS cannot: depth. The letters are extruded 6px with a bevelled edge
whose side faces sit in navy-800 and catch a cyan rim light, so at rest the
card reads as the flat kit and in motion the type is a solid object
settling into place.

Not one brand value is typed here. Every colour, font and curve comes from
`overlay_kit`, which reads the design tokens, so a token change re-renders
this card the same way it re-renders the CSS one. The hex-to-linear step is
the only arithmetic: Blender's materials take scene-linear values, and with
the view transform pinned to Standard a linear chalk comes out of the
encoder as chalk.

Shape of a build: spec JSON -> `bridge/blender_title_build.py` inside
Blender (factory startup, so no user addon or preference can leak into the
scene) -> a .blend -> `blender_render.render_blend` -> ProRes 4444 alpha.
The .blend is kept next to the clip on purpose: open it in Blender with the
MCP addon running and the scene is there to be argued with.

What breaks if this is wrong: the chalk comes out grey-green (view
transform not Standard), the type is Regular weight (a font file whose
default instance is not ExtraBold), or the card lands 16px low (the rise
keyframe never resolved because the layered-action lookup missed).
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Optional

from . import overlay_kit as kit
from .blender_render import BLENDER, render_blend
from .ingest import IngestError

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FONT_DISPLAY_FILE = PROJECT_ROOT / "brand" / "fonts" / "Bricolage.ttf"
BUILD_BRIDGE = Path(__file__).resolve().parent / "bridge" / "blender_title_build.py"

PX_PER_UNIT = 100.0   # one Blender unit is 100 CSS px; the frame is 19.2 x 10.8

# Blender's text `size` is not a CSS font-size. Measured 2026-09-15 on
# Bricolage: a capital H at size 8.0 under a 100 px/unit camera is 378 px
# tall; the same H at font-size 800px through FreeType is 528 px. Height
# ratio 1.397, so a CSS px of type is 1.40 Blender-size px. The width ratio
# is 1.32 — Blender draws the glyph ~6% wider for its height — so any line
# fitting must measure in Blender, never with Pillow.
BLENDER_TEXT_SCALE = 1.40

_BEZIER_RE = re.compile(r"cubic-bezier\(\s*([-.\d]+)\s*,\s*([-.\d]+)\s*,\s*([-.\d]+)\s*,\s*([-.\d]+)\s*\)")
_SHADOW_RE = re.compile(r"(-?[\d.]+)(?:px)?\s+(-?[\d.]+)(?:px)?\s+(-?[\d.]+)(?:px)?\s+"
                        r"rgba\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*([.\d]+)\s*\)")


def hex_to_linear(value: str) -> "list[float]":
    """#RRGGBB (sRGB) -> scene-linear RGB, the space Blender materials use."""
    r, g, b = kit._dt.hex_to_rgb(value)
    out = []
    for c in (r, g, b):
        c = c / 255.0
        out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return out


def parse_bezier(css: str) -> "list[float]":
    m = _BEZIER_RE.search(css)
    if not m:
        raise IngestError("easing token is not a cubic-bezier: %r" % css)
    return [float(m.group(i)) for i in (1, 2, 3, 4)]


def parse_shadows(css: str) -> "list[dict]":
    """CSS text-shadow list -> [{dx, dy, blur, rgb(linear), alpha}], y up."""
    out = []
    for m in _SHADOW_RE.finditer(css):
        dx, dy, blur = (float(m.group(i)) for i in (1, 2, 3))
        rgb = "#%02x%02x%02x" % tuple(int(m.group(i)) for i in (4, 5, 6))
        out.append({"dx": dx, "dy": -dy, "blur": blur,
                    "rgb": hex_to_linear(rgb), "alpha": float(m.group(7))})
    if not out:
        raise IngestError("shadow token has no rgba shadow: %r" % css)
    return out


def title_spec(text: str, kicker: str = "Next", fps: int = 24,
               seconds: float = 3.0, w: int = 1920, h: int = 1080) -> dict:
    """Everything the bridge needs, in the kit's numbers, nothing invented."""
    if not text.strip():
        raise IngestError("a title card needs text")
    if not FONT_DISPLAY_FILE.is_file():
        raise IngestError("display font missing: %s" % FONT_DISPLAY_FILE)
    portrait = h > w
    return {
        "w": w, "h": h, "px_per_unit": PX_PER_UNIT,
        "text_scale": BLENDER_TEXT_SCALE,
        "fps": fps, "frames": max(1, int(round(seconds * fps))),
        "font": str(FONT_DISPLAY_FILE),
        "colors": {
            "chalk": hex_to_linear(kit.CHALK),
            "cyan": hex_to_linear(kit.CYAN),
            "side": hex_to_linear(kit.NAVY_800),
        },
        "title": {
            "text": text, "size_px": 120, "spacing": 1.0 - 0.055,
            "left_px": 64 if portrait else 140,
            "inner_px": (w - 128) if portrait else 1560,
            "extrude_px": 6, "bevel_px": 1.5,
        },
        "eyebrow": {
            "text": kicker.upper(), "size_px": 26, "spacing": 1.0 + 0.24,
            "rule_px": 56, "rule_thick_px": kit.STROKE, "gap_px": 12,
            "block_gap_px": 16,
        },
        "motion": {
            "ease_reveal": parse_bezier(kit.EASE_REVEAL),
            "ease_rule": parse_bezier(kit.EASE_RULE),
            "rise_px": 16, "tilt_deg": 12,
            "eyebrow_ms": [0, 200], "rule_ms": [0, 260], "title_ms": [200, 600],
        },
        "shadows": parse_shadows(kit.SHADOW_DISPLAY),
    }


def build_command(spec_path: Path) -> "list[str]":
    return [BLENDER, "--background", "--factory-startup", "--python-exit-code", "1",
            "--python", str(BUILD_BRIDGE), "--", str(spec_path)]


def build_title(text: str, out_mov: Path, kicker: str = "Next", fps: int = 24,
                seconds: float = 3.0, blend: Optional[Path] = None) -> Path:
    """Build the .blend for `text`, render it, return the ProRes clip."""
    out_mov = Path(out_mov)
    if not os.path.exists(BLENDER):
        raise IngestError("Blender not found at %s" % BLENDER)
    out_mov.parent.mkdir(parents=True, exist_ok=True)
    blend = Path(blend) if blend else out_mov.with_suffix(".blend")
    spec = title_spec(text, kicker=kicker, fps=fps, seconds=seconds)
    spec["blend"] = str(blend)
    spec_path = out_mov.parent / (out_mov.stem + "_title.json")
    spec_path.write_text(json.dumps(spec, indent=1))

    proc = subprocess.run(build_command(spec_path), capture_output=True, text=True)
    if proc.returncode != 0:
        raise IngestError("blender title build failed (exit %d): %s"
                          % (proc.returncode, (proc.stderr or proc.stdout)[-400:]))
    if not blend.is_file():
        raise IngestError("blender title build wrote no .blend at %s" % blend)
    return render_blend(blend, out_mov, fps=fps, start=1, end=spec["frames"])
