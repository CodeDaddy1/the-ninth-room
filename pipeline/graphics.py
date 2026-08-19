"""Phase 5 — design cards: brand-styled HTML -> transparent PNG -> animated
ProRes 4444 alpha clip.

Why this shape: Resolve's FCPXML import drops transform keyframes (see
docs/resolve-findings.md), so a card cannot be animated on the timeline.
Instead every card is rendered as a short .mov WITH its animation baked in
(slide/fade via ffmpeg overlay expressions), and the timeline simply places
the clip on V3. Alpha survives — verified in the Phase 0 spike.

Rendering chain per card:
    card spec (graphics_plan.json, written by the graphics-director agent)
      -> HTML with brand tokens (Navy/Amber/Cream/Slate, Didot + Avenir Next)
      -> headless Chrome screenshot with a transparent background
      -> ffmpeg bake: animation + ProRes 4444 alpha

What breaks if this is wrong: cards appear as black rectangles (alpha lost),
render transparent (missing -loop 1 on the still input — the Phase 0 bug), or
look off-brand (colors/fonts drift from brand/visual-identity.md).
"""
from __future__ import annotations

import html
import json
import subprocess
from pathlib import Path

from .ingest import work_path, IngestError

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

# Brand values come from the synced design system so the video matches the
# thumbnails, site, and social kits (pipeline/design_tokens.py). The literals
# below are only the fallback when the token files are missing.
from . import design_tokens as _dt  # noqa: E402

_PAL = _dt.palette()
NAVY = _PAL["navy"]
AMBER = _PAL["amber"]
CREAM = _PAL["cream"]
SLATE = _PAL["slate"]
FONT_DISPLAY = _PAL["font_display"]
FONT_SANS = _PAL["font_sans"]
LS_EYEBROW = _PAL["ls_eyebrow"]

CARD_TYPES = ("hook_title", "section", "stat", "quote", "outro")
ANIMATIONS = ("slide_up", "slide_down", "fade")

# Portrait canvas; landscape formats swap these.
CANVAS = {"portrait": (1080, 1920), "landscape": (1920, 1080)}


# --- HTML -----------------------------------------------------------------

_BASE_CSS = """
* { margin: 0; padding: 0; box-sizing: border-box; }
html, body { width: %(w)spx; height: %(h)spx; background: transparent; }
body { font-family: %(font_sans)s; color: %(cream)s;
       display: flex; align-items: %(valign)s; justify-content: %(halign)s;
       padding: %(pad)spx; }
/* A translucent slab reads as a lower-third, not a dialog box: no hard
   border, a soft shadow to lift it off the footage, and an amber rule under
   the kicker instead of a border on the side. */
.card { background: linear-gradient(135deg, %(navy)sF2 0%%, %(navy)sD9 100%%);
        border-radius: 22px; padding: 48px 60px 52px; max-width: %(maxw)s%%;
        box-shadow: 0 24px 60px rgba(0,0,0,0.45);
        border-top: 3px solid %(amber)s66; }
.kicker { color: %(amber)s; font-size: %(kicker)spx; letter-spacing: %(ls_eyebrow)s;
          text-transform: uppercase; font-weight: 700; margin-bottom: 14px; }
.kicker::after { content: ""; display: block; width: 64px; height: 3px;
                 background: %(amber)s; margin-top: 14px; border-radius: 2px; }
.display { font-family: %(font_display)s; font-weight: 700;
           font-size: %(display)spx; line-height: 1.06;
           text-shadow: 0 3px 18px rgba(0,0,0,0.35); }
.display .em { color: %(amber)s; }
.body { font-size: %(body)spx; line-height: 1.35; color: %(cream)s; opacity: 0.92; }
.stat-number { font-family: %(font_display)s; font-size: %(stat)spx;
               line-height: 1; color: %(amber)s;
               text-shadow: 0 4px 24px rgba(0,0,0,0.4); }
.stat-label { font-size: %(body)spx; margin-top: 10px; }
.quote-mark { color: %(amber)s; font-family: %(font_display)s; font-size: 120px;
              line-height: 0.6; }
.attribution { color: %(slate)s; font-size: 34px; margin-top: 22px; }
"""


def _emphasize(text: str, emphasis: "list[str]") -> str:
    """HTML-escape text, then wrap emphasized words in amber."""
    out = html.escape(text)
    for word in emphasis or []:
        out = out.replace(html.escape(word),
                          '<span class="em">%s</span>' % html.escape(word))
    return out


def card_html(card: "dict", w: int, h: int) -> str:
    ctype = card["type"]
    portrait = h > w
    # Landscape cards sit low-left like a broadcast lower-third and leave the
    # frame's centre (usually the person) clear; portrait cards centre above
    # the caption band. Type scales with the canvas so 4K and 1080 match.
    if portrait:
        valign, halign, maxw = "center", "center", 84
        scale = w / 1080.0
    else:
        valign, halign, maxw = "flex-end", "flex-start", 52
        scale = w / 1920.0
    css = _BASE_CSS % {
        "w": w, "h": h, "navy": NAVY, "amber": AMBER, "cream": CREAM,
        "slate": SLATE, "valign": valign, "halign": halign, "maxw": maxw,
        "font_display": FONT_DISPLAY, "font_sans": FONT_SANS,
        "ls_eyebrow": LS_EYEBROW,
        "pad": int((110 if portrait else 96) * scale),
        "kicker": int(30 * scale), "display": int((86 if portrait else 76) * scale),
        "body": int(38 * scale), "stat": int(180 * scale),
    }
    kicker = ('<div class="kicker">%s</div>' % html.escape(card["kicker"])) if card.get("kicker") else ""
    if ctype in ("hook_title", "section", "outro"):
        body = '%s<div class="display">%s</div>' % (
            kicker, _emphasize(card["text"], card.get("emphasis", [])))
        if ctype == "outro" and card.get("subtext"):
            body += '<div class="body" style="margin-top:28px">%s</div>' % html.escape(card["subtext"])
    elif ctype == "stat":
        body = '%s<div class="stat-number">%s</div><div class="stat-label">%s</div>' % (
            kicker, html.escape(card["stat"]), _emphasize(card["text"], card.get("emphasis", [])))
    elif ctype == "quote":
        body = '<div class="quote-mark">&ldquo;</div><div class="display">%s</div>' % (
            _emphasize(card["text"], card.get("emphasis", [])))
        if card.get("attribution"):
            body += '<div class="attribution">&mdash; %s</div>' % html.escape(card["attribution"])
    else:
        raise IngestError("unknown card type: %s" % ctype)
    return "<!doctype html><html><head><meta charset='utf-8'><style>%s</style></head>" \
           "<body><div class='card'>%s</div></body></html>" % (css, body)


# --- render + bake --------------------------------------------------------

def render_png(card: "dict", out_png: Path, w: int, h: int, tmp_dir: Path) -> None:
    """Headless-Chrome screenshot at 2x with a transparent background."""
    tmp_dir.mkdir(parents=True, exist_ok=True)
    html_path = (tmp_dir / (card["id"] + ".html")).resolve()
    html_path.write_text(card_html(card, w, h))
    proc = subprocess.run(
        [CHROME, "--headless=new", "--disable-gpu", "--force-device-scale-factor=2",
         "--window-size=%d,%d" % (w, h),
         "--default-background-color=00000000",
         "--screenshot=" + str(Path(out_png).resolve()),
         "file://" + str(html_path)],
        capture_output=True, text=True, timeout=60)
    if proc.returncode != 0 or not out_png.exists():
        raise IngestError("chrome screenshot failed for %s: %s"
                          % (card["id"], (proc.stderr or "")[-300:]))


def bake_mov(png: Path, out_mov: Path, duration: float, w: int, h: int,
             anim: str = "slide_up", fps: int = 30) -> None:
    """Bake the animated alpha clip. The still input MUST use -loop 1 or the
    fade filter collapses it to a single transparent frame (Phase 0 lesson)."""
    rise = int(h * 0.06)
    if anim == "slide_up":
        y_expr = "(H-h)/2+%d*(1-min(t/0.5,1))" % rise
    elif anim == "slide_down":
        y_expr = "(H-h)/2-%d*(1-min(t/0.5,1))" % rise
    else:  # fade
        y_expr = "(H-h)/2"
    fade_out_start = max(duration - 0.4, 0.4)
    filters = (
        "[1:v]format=rgba,scale=%d:%d,"
        "fade=in:st=0:d=0.35:alpha=1,fade=out:st=%.3f:d=0.4:alpha=1[card];"
        "[0:v][card]overlay=x=(W-w)/2:y='%s':format=auto"
        % (w, h, fade_out_start, y_expr)
    )
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "lavfi", "-i",
        "color=c=black@0.0:s=%dx%d:r=%d:d=%.3f,format=rgba" % (w, h, fps, duration),
        "-loop", "1", "-t", "%.3f" % duration, "-r", str(fps), "-i", str(png),
        "-filter_complex", filters,
        "-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le",
        str(out_mov),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise IngestError("bake failed for %s: %s" % (png.name, proc.stderr[-300:]))


# --- the stage ------------------------------------------------------------

def build_cards(slug: str, orientation: str = "portrait", log=print) -> "list[Path]":
    """Render every card in work/<slug>/graphics_plan.json to graphics/<id>.mov."""
    work = work_path(slug)
    plan_path = work / "graphics_plan.json"
    if not plan_path.exists():
        raise IngestError("no graphics_plan.json — run the graphics-director agent first")
    plan = json.loads(plan_path.read_text())
    from . import schemas
    errors = schemas.validate_graphics_plan(plan)
    if errors:
        raise IngestError("graphics_plan failed validation:\n  " + "\n  ".join(errors))

    # Animate in the browser with the design system's own motion tokens.
    # Imported lazily because pipeline.animate imports card_html from here.
    from . import animate as animate_mod

    # graphics_plan speaks in simple names; map them to the CSS presets.
    PRESET_FOR = {"slide_up": "reveal_up", "slide_down": "reveal_down",
                  "fade": "fade", "wipe_left": "wipe_left"}

    w, h = CANVAS[orientation]
    out_dir = work / "graphics"
    out_dir.mkdir(exist_ok=True)
    tmp_dir = out_dir / "tmp"
    movs = []
    for card in plan["cards"]:
        mov = out_dir / (card["id"] + ".mov")
        preset = PRESET_FOR.get(card.get("animation", "slide_up"), "reveal_up")
        animate_mod.render_animation(card, mov, float(card["duration"]), w, h,
                                     tmp_dir, preset=preset, log=log)
        movs.append(mov)
        log("[graphics] %s (%s, %.1fs) -> %s" % (card["id"], card["type"],
                                                 card["duration"], mov.name))
    return movs
