"""Illustrations: pictures no camera could film, and where they came from.

The vocabulary is CONTEXT.md's; the decisions are
docs/decisions-illustrations.md. This module owns the one fact every rule
about an illustration reads, its PROVENANCE, and the pure helpers around
it. Provenance is derived once, at catalog time, from the Library manifest
(`work/<slug>/assets/assets.json`): a row whose `honesty` names one of the
two values is an illustration, and the footage file it became is matched
by `promoted_as` first (the name `_use_asset` gave it), then by the row's
own file name, then by the `<stem>_still.mp4` a still is baked into.
Absent means camera, everywhere.

What breaks if this is wrong: a plate is graded through the camera LUT
(build_api reads provenance to leave it alone), a re-analyze forgets which
clips are illustrations (catalog_broll derives it fresh each run, so it
cannot), or a rule keyed on provenance goes blind.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from .ingest import work_path
from .schemas import HONESTY  # noqa: F401  (re-exported: the two values)


def provenance_of(assets_dir: Path, name: str) -> Optional[str]:
    """The honesty value of the manifest row `name` came from, or None."""
    man_p = Path(assets_dir) / "assets.json"
    try:
        rows = json.loads(man_p.read_text()).get("assets", [])
    except (OSError, ValueError):
        return None
    for a in rows:
        honesty = a.get("honesty")
        if honesty not in HONESTY:
            continue
        f = str(a.get("file") or "")
        if name in (a.get("promoted_as"), f, Path(f).stem + "_still.mp4"):
            return honesty
    return None


def exempt_files(slug: str) -> "set[str]":
    """Footage file names the colour pipeline must leave alone: every
    catalogued clip carrying a provenance. Pure over analysis/broll.json."""
    p = work_path(slug) / "analysis" / "broll.json"
    try:
        clips = json.loads(p.read_text()).get("clips", [])
    except (OSError, ValueError):
        return set()
    return {c["file"] for c in clips
            if isinstance(c, dict) and c.get("provenance") and c.get("file")}
