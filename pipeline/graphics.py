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

NAVY = "#0E1B2C"
AMBER = "#E8A33D"
CREAM = "#F4EFE6"
SLATE = "#6B7C93"

CARD_TYPES = ("hook_title", "section", "stat", "quote", "outro")
ANIMATIONS = ("slide_up", "slide_down", "fade")

# Portrait canvas; landscape formats swap these.
CANVAS = {"portrait": (1080, 1920), "landscape": (1920, 1080)}


# --- HTML -----------------------------------------------------------------

_BASE_CSS = """
* { margin: 0; padding: 0; box-sizing: border-box; }
html, body { width: %(w)spx; height: %(h)spx; background: transparent; }
body { font-family: "Avenir Next", "Helvetica Neue", sans-serif; color: %(cream)s;
       display: flex; align-items: %(valign)s; justify-content: center; }
.card { background: %(navy)sE6; border-left: 10px solid %(amber)s;
        border-radius: 28px; padding: 64px 72px; max-width: 82%%;
        margin-bottom: %(mb)spx; margin-top: %(mt)spx; }
.kicker { color: %(amber)s; font-size: 34px; letter-spacing: 0.18em;
          text-transform: uppercase; font-weight: 600; margin-bottom: 18px; }
.display { font-family: Didot, "Bodoni 72", serif; font-weight: 700;
           font-size: 92px; line-height: 1.08; }
.display .em { color: %(amber)s; }
.body { font-size: 40px; line-height: 1.35; color: %(cream)s; }
.stat-number { font-family: Didot, "Bodoni 72", serif; font-size: 200px;
               line-height: 1; color: %(amber)s; }
.stat-label { font-size: 44px; margin-top: 12px; }
.quote-mark { color: %(amber)s; font-family: Didot, serif; font-size: 120px;
              line-height: 0.6; }
.attribution { color: %(slate)s; font-size: 36px; margin-top: 24px; }
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
    # Hooks sit slightly above center (thumb-zone safe); others center.
    valign, mt, mb = ("center", 0, int(h * 0.12)) if ctype == "hook_title" else ("center", 0, 0)
    css = _BASE_CSS % {"w": w, "h": h, "navy": NAVY, "amber": AMBER,
                       "cream": CREAM, "slate": SLATE,
                       "valign": valign, "mt": mt, "mb": mb}
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

    w, h = CANVAS[orientation]
    out_dir = work / "graphics"
    out_dir.mkdir(exist_ok=True)
    tmp_dir = out_dir / "tmp"
    movs = []
    for card in plan["cards"]:
        png = tmp_dir / (card["id"] + ".png")
        mov = out_dir / (card["id"] + ".mov")
        render_png(card, png, w, h, tmp_dir)
        bake_mov(png, mov, float(card["duration"]), w, h,
                 anim=card.get("animation", "slide_up"))
        movs.append(mov)
        log("[graphics] %s (%s, %.1fs) -> %s" % (card["id"], card["type"],
                                                 card["duration"], mov.name))
    return movs
