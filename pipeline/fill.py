# -*- coding: utf-8 -*-
"""Vertical footage keeps its shape; the frame around it stops being a void.

A 9:16 phone clip dropped into a 16:9 episode has three bad answers and
one good one. Cropping to fill throws away the top and bottom of a shot
someone framed deliberately. Stretching is worse. Black pillarbox reads
as a mistake. So: keep the clip at its native aspect, centred and full
height, and fill the sides with the SAME frame zoomed to cover, blurred
and darkened — the background says "here", never competes for the eye
(Caleb, 2026-08-24).

This BAKES a companion file rather than compositing in the NLE. Free
Resolve blocks external scripting, and this pipeline already bakes what
an NLE would fight over (overlays become ProRes clips for the same
reason). Once baked, the file is an ordinary landscape clip and every
downstream stage — proxies, FCPXML, conform, master — needs no special
case at all.

The redirection point is `catalog.json`: proxy.py, produce.py and
deliver.py all resolve media through it, so pointing one entry's `path`
at the filled file is the entire integration.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

BLUR_SIGMA = 24      # enough to kill detail, not so much it turns to mud
DIM = 0.75           # background brightness multiplier
FILL_CRF = 16        # near-visually-lossless; this file becomes the master source


def is_portrait(width: "int | None", height: "int | None") -> bool:
    """Taller than wide. Square is NOT portrait — it pillarboxes fine and
    a square clip zoomed into a 16:9 background gains nothing."""
    try:
        return int(height or 0) > int(width or 0) > 0
    except (TypeError, ValueError):
        return False


def fill_filter(canvas_w: int, canvas_h: int,
                blur: float = BLUR_SIGMA, dim: float = DIM) -> str:
    """The ffmpeg filter_complex, built as a string so it is testable
    without ffmpeg. Two copies of one input: one scaled to COVER the
    canvas (so no black shows through), blurred and dimmed; the other
    scaled to the canvas HEIGHT, keeping its own aspect, centred on top.

    `force_original_aspect_ratio=increase` then `crop` is the cover
    idiom — scaling to exact canvas dimensions would squash the
    background, which is the very thing we refuse to do to the subject.
    """
    return (
        "[0:v]split=2[bg][fg];"
        "[bg]scale=%(w)d:%(h)d:force_original_aspect_ratio=increase,"
        "crop=%(w)d:%(h)d,gblur=sigma=%(blur).1f,"
        # lutyuv MULTIPLIES luma. `eq=brightness` is an ADDITIVE offset in
        # [-1,1] — using it for "75% as bright" subtracted ~64 levels and
        # measured out at 15% of the centre, near black (2026-08-24).
        "lutyuv=y=val*%(dim).3f[bgv];"
        "[fg]scale=-2:%(h)d[fgv];"
        "[bgv][fgv]overlay=(W-w)/2:0,setsar=1[v]"
        % {"w": canvas_w, "h": canvas_h, "blur": blur, "dim": dim}
    )


def filled_dir(work: Path) -> Path:
    return work / "filled"


def filled_path(work: Path, name: str) -> Path:
    return filled_dir(work) / (Path(name).stem + ".mp4")


def bake(src: Path, dest: Path, canvas: "tuple[int, int]",
         log=print) -> Path:
    """Render the filled companion. Audio is copied through untouched —
    the picture is the only thing being changed, and a re-encode here
    would cost quality for nothing."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".partial.mp4")
    from .graphics import h264_encode_args
    cmd = (["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-i", str(src),
            "-filter_complex", fill_filter(canvas[0], canvas[1]),
            "-map", "[v]", "-map", "0:a?"]
           # hardware above 1920 wide: measured 2.6x at 4K and effectively
           # free (0.11s over the decode-only floor), while software wins
           # outright at proxy size
           + h264_encode_args(canvas[0], crf=FILL_CRF)
           + ["-c:a", "copy", str(tmp)])
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0 or not tmp.exists():
        tmp.unlink(missing_ok=True)
        raise RuntimeError("fill bake failed for %s: %s"
                           % (src.name, (proc.stderr or "")[-400:]))
    tmp.replace(dest)          # a half-written fill must never be catalogued
    log("[fill] %s -> %dx%d with a blurred ground" % (src.name, canvas[0], canvas[1]))
    return dest


def redirect(entry: "dict", filled: Path, canvas: "tuple[int, int]") -> "dict":
    """PURE: point a catalog entry at its filled companion, keeping the
    original on the record. Provenance matters — `source_path` is what a
    re-bake reads, and native_w/h is how the desk can still say what was
    actually shot."""
    out = dict(entry)
    out["source_path"] = entry.get("source_path") or entry.get("path")
    out["native_width"] = entry.get("native_width") or entry.get("width")
    out["native_height"] = entry.get("native_height") or entry.get("height")
    out["path"] = str(filled)
    out["width"], out["height"] = canvas
    out["filled"] = True
    return out
