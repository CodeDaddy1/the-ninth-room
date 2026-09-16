"""Render a Blender scene into the same ProRes 4444 alpha clip a card bakes to.

The pipeline already has one rule for motion graphics: Resolve drops
transform keyframes on import, so every animated overlay arrives pre-baked
as a ProRes 4444 alpha clip (see `animate.py`). Chrome makes those frames
from CSS. This module makes them from a .blend, then hands the folder to
the very same `encode_frames`, so a 3D title, a turntable of a generated
model, a terrain flyover or a 2.5D push over a still reaches the timeline
exactly the way a card does — alpha intact, nothing for the import to lose.

Blender runs headless (`--background`) with `bridge/blender_frames.py`
inside it. The .blend owns the look; the bridge script forces only the
contract (RGBA PNG, transparent film, our fps, f0000.png naming). This side
owns the guards: the app must exist, Blender must exit clean, and the frame
count must match before a single byte is encoded — a partial render must
never become a short clip that plays fine and ends early.

Cost: Eevee renders a 1080p frame in well under a second on this machine;
Cycles is the template's choice and its own bill. The .blend is the cache
key nothing here tracks yet — re-rendering an unchanged scene is the
template layer's problem, the same way `graphics.build_cards` owns card
caching, not `animate.py`.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional

from .animate import encode_frames
from .ingest import IngestError

BLENDER = "/Applications/Blender.app/Contents/MacOS/Blender"
BRIDGE = Path(__file__).resolve().parent / "bridge" / "blender_frames.py"


def blender_command(blend: Path, frames_dir: Path, fps: int,
                    start: Optional[int], end: Optional[int]) -> "list[str]":
    """The exact argv, kept separate so a test can check it without Blender."""
    # Blender exits 0 when a --python script raises; this flag makes it
    # exit 1 instead, so the guard below can see a broken bridge.
    cmd = [BLENDER, "--background", "--python-exit-code", "1", str(blend),
           "--python", str(BRIDGE), "--", str(frames_dir), str(fps)]
    if start is not None or end is not None:
        if start is None or end is None:
            raise IngestError("give both --start and --end, or neither")
        cmd += [str(start), str(end)]
    return cmd


def render_blend(blend: Path, out_mov: Path, fps: int = 24,
                 start: Optional[int] = None, end: Optional[int] = None,
                 tmp_dir: Optional[Path] = None) -> Path:
    """Render `blend` to `out_mov` (ProRes 4444 alpha) at `fps`.

    `start`/`end` are the scene's frame numbers, inclusive; omit both to
    render the scene's own range. Frames are staged in `tmp_dir` (default:
    next to the output) and deleted by `encode_frames` on success.
    """
    blend = Path(blend)
    out_mov = Path(out_mov)
    if not os.path.exists(BLENDER):
        raise IngestError("Blender not found at %s" % BLENDER)
    if not blend.is_file():
        raise IngestError("no such .blend: %s" % blend)
    if fps <= 0:
        raise IngestError("fps must be positive, got %r" % fps)

    frames_dir = (tmp_dir or out_mov.parent) / (out_mov.stem + "_frames")
    if frames_dir.exists():
        shutil.rmtree(frames_dir)
    frames_dir.mkdir(parents=True)
    out_mov.parent.mkdir(parents=True, exist_ok=True)

    cmd = blender_command(blend, frames_dir, fps, start, end)
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise IngestError("blender render failed (exit %d): %s"
                          % (proc.returncode, (proc.stderr or proc.stdout)[-400:]))

    written = sorted(frames_dir.glob("f[0-9][0-9][0-9][0-9].png"))
    if not written:
        raise IngestError("blender wrote no frames for %s" % blend.name)
    if start is not None and end is not None:
        expected = end - start + 1
        if len(written) != expected:
            raise IngestError("blender wrote %d frames, expected %d (%s)"
                              % (len(written), expected, blend.name))
    for i, png in enumerate(written):
        if png.name != "f%04d.png" % i:
            raise IngestError("frame sequence has a gap at %s (%s)"
                              % (png.name, blend.name))

    return encode_frames(frames_dir, out_mov, fps)
