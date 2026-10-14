# -*- coding: utf-8 -*-
"""The Blender kit types: 3D titles beside the CSS cards, never replacing them.

Decision 8 (docs/decisions-illustrations.md): `chapter_3d` and `hook_3d`
are real `kit_type`s the graphics-director can pick. Their stand-in in the
kit is the flat screen of the same name (the Studio's hover preview, the
picker and `validate_graphics_plan` all read RENDERERS), which is also
their canvas under CLAUDE.md rule six: the 3D render must match the flat
card's left edge, cap height and line count, not the other way round.

`graphics.build_cards` routes these to `blender_title.build_title`;
everything downstream (the .mov, the proxy, the export, Resolve's V3) is
unchanged. `template_sha` is what the cache key sees: the two bridge
scripts, the measured text scale and any .blend under brand/blender/, so
a template edit re-bakes exactly the Blender cards and no flat one.
"""
import hashlib
from pathlib import Path

from . import overlay_kit as _kit
from . import paths

BLENDER_KITS = {"chapter_3d": "chapter", "hook_3d": "hook"}
BLENDER_DIR = paths.PROJECT_ROOT / "brand" / "blender"
BRIDGE_DIR = Path(__file__).resolve().parent / "bridge"

BLENDER_TEMPLATES = {
    "chapter_3d": {"kicker": "", "text": "Chapter title", "duration": 3},
    "hook_3d": {"kicker": "The setup", "text": "A headline that opens the loop",
                "duration": 3},
}
BLENDER_GROUPS = [{"title": "3D titles", "kits": ["chapter_3d", "hook_3d"]}]


def is_blender_kit(kit_type) -> bool:
    return str(kit_type or "") in BLENDER_KITS


def template_sha() -> str:
    """What a Blender bake depends on that the card spec does not name."""
    from . import blender_title
    h = hashlib.sha1()
    for name in ("blender_frames.py", "blender_title_build.py"):
        h.update((BRIDGE_DIR / name).read_bytes())
    h.update(str(blender_title.BLENDER_TEXT_SCALE).encode())
    if BLENDER_DIR.is_dir():
        for blend in sorted(BLENDER_DIR.glob("*.blend")):
            h.update(blend.name.encode())
            h.update(blend.read_bytes())
    return h.hexdigest()[:12]


# the stand-ins: the flat screens, so every reader of RENDERERS works
for _three_d, _flat in BLENDER_KITS.items():
    _kit.RENDERERS[_three_d] = _kit.RENDERERS[_flat]
    if _flat in _kit.SCRIM_CENTER:
        _kit.SCRIM_CENTER.add(_three_d)
    if _flat in _kit.SCRIM_BAND:
        _kit.SCRIM_BAND.add(_three_d)
