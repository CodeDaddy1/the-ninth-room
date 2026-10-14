# -*- coding: utf-8 -*-
"""The RECONSTRUCTION marker: one kit screen the ENGINE owns.

Decision 6 (docs/decisions-illustrations.md): a photoreal reconstruction
carries the kit eyebrow RECONSTRUCTION for its whole length, so a viewer
in the moment can tell, not only a reader of the description. The screen
is the kit's own eyebrow primitive (cyan rule and caps label, the element
that already means "the system talking"), inside the safe inset, top
left, both orientations, no scrim: the kit's one visual rule stands.

The cards that use it (`MARK<n>`, kit_type `provenance`) are written by
`illustration.sync_markers` from the timeline map, never by hand and never
by the graphics-director; a session that rewrites the plan loses them and
the runner puts them back. The stand-in carve-out in CLAUDE.md rule six
does not apply here: this IS a kit screen, registered the way vfx_kit and
checklist_kit register, and its canvas is the Cyanotype kit's eyebrow.
"""
from . import overlay_kit as _kit


def provenance(card: "dict", F: "dict") -> str:
    """The eyebrow alone, at the top of the safe inset."""
    label = card.get("kicker") or card.get("text") or "RECONSTRUCTION"
    return ('<div style="position:absolute;left:%dpx;top:%dpx">%s</div>'
            % (F["side"], F["top"], _kit._eyebrow(label, _kit.CYAN, 0, 26, track=".24em")))


MARKER_RENDERERS = {"provenance": provenance}
MARKER_TEMPLATES = {
    "provenance": {"text": "RECONSTRUCTION", "kicker": "RECONSTRUCTION", "duration": 5},
}
MARKER_GROUPS = [{"title": "Markers", "kits": ["provenance"]}]

_kit.RENDERERS.update(MARKER_RENDERERS)
