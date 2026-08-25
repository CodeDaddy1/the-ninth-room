# -*- coding: utf-8 -*-
"""Fitting a source of one shape onto a canvas of another, without lying.

Every scale in this pipeline was `scale=W:H` with no aspect handling, so a
16:9 clip on a vertical canvas STRETCHED — proxy.py already carries a
comment about the incident that caused on the other axis. It did not matter
while every project was one shape end to end. It matters now: a vertical
episode sources stock, and stock is 16:9.

Caleb's call, 2026-08-25: **centre-crop, never stretch.** Fill the frame
from the middle of the source and lose the edges, which is right for
talking heads and centred subjects and is never dishonest about
proportions. A per-clip nudge comes later, once he has seen where the middle
is the wrong place to look.

What breaks if this is wrong: faces get narrower or wider than they are,
and nobody reports it as a bug — they just think the video looks cheap.
"""
from __future__ import annotations


def crop_rect(src_w: int, src_h: int, dst_w: int, dst_h: int) -> "tuple":
    """The (w, h, x, y) of the largest centred region of the source that has
    the destination's aspect ratio.

    Pure and integer-only: ffmpeg's crop filter takes pixels, and a
    fractional crop silently rounds somewhere else in the chain.
    """
    for name, v in (("src_w", src_w), ("src_h", src_h),
                    ("dst_w", dst_w), ("dst_h", dst_h)):
        if not isinstance(v, int) or isinstance(v, bool) or v <= 0:
            raise ValueError("%s must be a positive int, got %r" % (name, v))
    # Compare aspects by cross-multiplying: no float, no rounding surprise
    # at 1920x1080 vs 3840x2160, which are the same shape and must produce
    # a no-op crop rather than a one-pixel sliver.
    if src_w * dst_h == src_h * dst_w:
        return (_even(src_w), _even(src_h), 0, 0)
    if src_w * dst_h > src_h * dst_w:
        # source is WIDER than the target: keep full height, trim the sides
        w = _even(min(src_w, int(round(src_h * dst_w / float(dst_h)))))
        h = _even(src_h)
        return (w, h, (src_w - w) // 2, 0)
    # source is TALLER: keep full width, trim top and bottom
    h = _even(min(src_h, int(round(src_w * dst_h / float(dst_w)))))
    w = _even(src_w)
    return (w, h, 0, (src_h - h) // 2)


def fit_expr(dst_w: int, dst_h: int) -> str:
    """The same centre-crop, written so ffmpeg computes it per input.

    The proxy builder does not know its sources' dimensions and probing
    every clip would cost an ffprobe per beat. crop takes EXPRESSIONS, so
    the rule can be stated once and evaluated against each input's real
    `iw`/`ih`:

        keep width  = min(iw, ih * A)      A = the canvas aspect
        keep height = min(ih, iw / A)

    Whichever axis is proportionally too big gets trimmed and the other
    passes through whole; x and y default to centred. When the source
    already matches the canvas both mins pick the source's own dimension,
    so it is a no-op and nothing changes for a single-orientation project.

    `trunc(v/2)*2` keeps both even — odd dimensions break yuv420p, and the
    failure surfaces later as an ffmpeg error about something else.
    """
    if dst_h <= 0 or dst_w <= 0:
        raise ValueError("canvas must be positive, got %dx%d" % (dst_w, dst_h))
    a = "%d/%d" % (dst_w, dst_h)
    return ("crop=w='trunc(min(iw,ih*(%s))/2)*2':"
            "h='trunc(min(ih,iw/(%s))/2)*2',scale=%d:%d"
            % (a, a, dst_w, dst_h))


def _even(v: int) -> int:
    """Round DOWN to even, floored at 2. Odd dimensions break yuv420p
    encoders, and the failure surfaces three stages later as an ffmpeg
    error about the wrong thing. A pass-through dimension needs this as
    much as a computed one — an odd source width stayed odd until a test
    caught it."""
    return max(2, v - (v % 2))


def fit_filter(src_w: int, src_h: int, dst_w: int, dst_h: int) -> str:
    """The ffmpeg filter chain that puts this source on that canvas.

    Returns `scale=...` alone when the shapes already agree, so the common
    case — every clip in a single-orientation project — adds no crop pass
    and no behaviour change at all.
    """
    w, h, x, y = crop_rect(src_w, src_h, dst_w, dst_h)
    scale = "scale=%d:%d" % (dst_w, dst_h)
    if (w, h) == (src_w, src_h):
        return scale
    return "crop=%d:%d:%d:%d,%s" % (w, h, x, y, scale)
