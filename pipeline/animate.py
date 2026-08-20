"""Render CSS animations from the design system into alpha video clips.

The problem this solves: Resolve drops transform keyframes on import and its
API cannot animate a clip, so motion has to arrive pre-baked. Until now that
meant approximating motion with ffmpeg expressions — linear moves that ignore
the brand's motion language.

This does it properly. The card is an HTML page whose animation is written in
CSS using the design system's own tokens (`--dur-reveal`, `--ease-out-soft`,
…). To capture it, we exploit a browser behaviour: a **negative
`animation-delay` seeks into an animation**, and `animation-play-state:
paused` freezes it there. So for frame N we load the page with the animation
frozen at N/fps seconds and screenshot it. Stitch the frames, and the result
is the exact curve the design system specifies — cubic-bezier and all — not an
approximation.

Cost: one headless-Chrome launch per frame (~0.3s), so a 1s reveal at 24fps is
about 8 seconds of rendering. Fine for a handful of cards per video.

What breaks if this is wrong: cards appear frozen (delay not applied), the
motion eases differently from the rest of the brand (tokens not loaded), or
the clip loses alpha (see the ProRes flags in `encode_frames`).
"""
from __future__ import annotations

import html as html_mod
import os
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image

from . import design_tokens as _dt
from .graphics import CHROME, card_html
from .ingest import IngestError

# Bump when animate.py, overlay_kit.py, or the design tokens change rendered
# pixels — it invalidates every cached card bake (see graphics.build_cards).
BAKE_V = 1

# Frames rendered per Chrome launch. A launch costs ~2.3s regardless of page
# size, so batching is nearly free speedup; 6 keeps the tallest page
# (portrait, 1920x11520) comfortably under Chrome's render limits.
CHROME_BATCH = 6

_PAL = _dt.palette()
_TOKENS = _dt.load()

REVEAL_MS = int(str(_dt.resolve(_TOKENS, "dur-reveal", "700ms")).replace("ms", "") or 700)
HOLD_MS = int(str(_dt.resolve(_TOKENS, "reveal-hold", "900ms")).replace("ms", "") or 900)
EASE = _dt.resolve(_TOKENS, "ease-out-soft", "cubic-bezier(0.16,1,0.3,1)")
EASE_INOUT = _dt.resolve(_TOKENS, "ease-in-out", "cubic-bezier(0.45,0,0.55,1)")


def _perf_cores() -> int:
    """Physical performance cores, or 0 if the platform will not say.

    `os.cpu_count()` counts *logical* CPUs, which on Apple silicon includes the
    efficiency cores. Frame rendering is CPU-bound and gets scheduled onto the
    performance cores, so sizing the pool off the logical count oversubscribes
    them by more than half.
    """
    try:
        out = subprocess.run(["sysctl", "-n", "hw.perflevel0.logicalcpu"],
                             capture_output=True, text=True, timeout=5)
        return int(out.stdout.strip())
    except (OSError, ValueError, subprocess.SubprocessError):
        return 0


def _default_parallel() -> int:
    """How many headless Chromes may run at once.

    One headless Chrome is not one process: it is a browser process plus a
    renderer, a GPU process and utility helpers -- roughly five processes and
    ~500 MB each. A hard-coded 6 on this 10-core M5 (4 performance + 6
    efficiency) put ~30 processes and 6.3 GB against 4 usable cores and drove
    the load average past 30, which makes the whole machine unusable for the
    length of a render (observed 2026-08-18, 21-card video).

    So: one Chrome per performance core, clamped to 2..8, overridable with
    CC_RENDER_WORKERS when rendering on a bigger box.

    What breaks if this is wrong: too high and the Mac locks up while a video
    renders, and frames start tripping the 120s timeout in `shoot`; too low and
    a long video takes noticeably longer than it needs to.
    """
    env = os.environ.get("CC_RENDER_WORKERS", "").strip()
    if env:
        try:
            return max(1, int(env))
        except ValueError:
            pass  # a typo in the override must never stop a render
    cores = _perf_cores() or max(1, (os.cpu_count() or 4) // 2)
    return max(2, min(8, cores))


PARALLEL = _default_parallel()

# Animation presets, expressed the way the design system would express them.
# `enter` runs at the start, `exit` at the end; both use brand easing.
PRESETS = {
    "reveal_up": {
        "from": "opacity:0; transform:translateY(48px) scale(0.985);",
        "to": "opacity:1; transform:translateY(0) scale(1);",
    },
    "reveal_down": {
        "from": "opacity:0; transform:translateY(-48px) scale(0.985);",
        "to": "opacity:1; transform:translateY(0) scale(1);",
    },
    "fade": {
        "from": "opacity:0;",
        "to": "opacity:1;",
    },
    "wipe_left": {
        "from": "opacity:0; transform:translateX(-64px); clip-path:inset(0 100% 0 0);",
        "to": "opacity:1; transform:translateX(0); clip-path:inset(0 0 0 0);",
    },
}


def _kit_html(card: "dict", w: int, h: int, t_ms: int) -> str:
    """An Overlay Kit card frozen at t_ms.

    The kit's own CSS carries every animation (staggered wipes, blur-ins,
    pops), so freezing is simpler than for the older cards: pause everything
    on the page and seek all of it to the same instant with one negative
    delay. `animation-delay` on `*` overrides each element's own delay, so
    the per-element delays are re-added by keeping them in the shorthand and
    only shifting the global clock — hence the `!important`-free approach of
    setting `animation-delay` per element via a CSS variable is unnecessary:
    Chrome applies the negative delay on top of the declared one.
    """
    from . import overlay_kit
    base = overlay_kit.overlay_html(card, w, h)
    freeze = """
<style>
.stage *, .stage { animation-play-state: paused !important; }
</style>
<script>
document.addEventListener('DOMContentLoaded', function () {
  var t = %(t)d;
  document.getAnimations().forEach(function (a) {
    a.pause();
    try { a.currentTime = t; } catch (e) {}
  });
});
</script>
""" % {"t": t_ms}
    return base.replace("</head>", freeze + "</head>")


def _animated_html(card: "dict", w: int, h: int, preset: str, t_ms: int,
                   duration_ms: int) -> str:
    """The card's HTML with its animation frozen at t_ms.

    ONE animation covering enter → hold → exit, not two stacked ones: a
    second animation with `both` fill applies its start state on top of the
    first, which pinned the card to fully-visible for the whole clip
    (verified 2026-08-18). Per-keyframe `animation-timing-function` gives each
    segment its own brand easing while the animation itself runs linear.
    """
    p = PRESETS.get(preset, PRESETS["reveal_up"])
    base = card_html(card, w, h)
    total = max(duration_ms, 2 * REVEAL_MS + 200)
    enter_pct = 100.0 * REVEAL_MS / total
    exit_pct = 100.0 * (total - REVEAL_MS) / total
    css = """
<style>
@keyframes ccCard {
  0%%      { %(from)s animation-timing-function: %(ease)s; }
  %(ep).3f%%  { %(to)s animation-timing-function: linear; }
  %(xp).3f%%  { %(to)s animation-timing-function: %(ease_out)s; }
  100%%    { %(from)s }
}
.card {
  animation: ccCard %(total)dms linear both;
  animation-play-state: paused;
  animation-delay: -%(t)dms;
}
</style>
""" % {"from": p["from"], "to": p["to"], "ease": EASE, "ease_out": EASE_INOUT,
       "ep": enter_pct, "xp": exit_pct, "total": total, "t": t_ms}
    # The frozen-frame CSS must come last so it wins the cascade.
    return base.replace("</head>", css + "</head>")


def render_animation(card: "dict", out_mov: Path, duration: float, w: int, h: int,
                     tmp_dir: Path, preset: str = "reveal_up", fps: int = 24,
                     log=print) -> Path:
    """Screenshot the CSS animation frame by frame, then encode with alpha."""
    tmp_dir.mkdir(parents=True, exist_ok=True)
    frames_dir = tmp_dir / (card["id"] + "_frames")
    frames_dir.mkdir(exist_ok=True)
    n = max(1, int(round(duration * fps)))
    duration_ms = int(duration * 1000)

    use_kit = bool(card.get("kit_type")) or card.get("kit", False)

    # A card is: reveal, hold, exit. Every frame of the hold is byte-identical,
    # and a Chrome launch costs ~2.3s, so rendering the hold would burn minutes
    # per card producing copies of one image. Render the moving parts only and
    # copy the held frame across the middle.
    move_ms = REVEAL_MS + 120
    exit_from = max(duration_ms - REVEAL_MS - 120, move_ms)
    def moving(i):
        t = i * 1000.0 / fps
        return t <= move_ms or t >= exit_from

    todo = [i for i in range(n) if moving(i)]
    # The held frame is the last one of the reveal — the settled state.
    hold_src = max([i for i in todo if i * 1000.0 / fps <= move_ms] or [0])

    def frame_html(i):
        t_ms = int(round(i * 1000.0 / fps))
        return (_kit_html(card, w, h, t_ms) if use_kit
                else _animated_html(card, w, h, preset, t_ms, duration_ms))

    def shoot_group(group):
        """Render up to CHROME_BATCH frames with ONE Chrome launch.

        Each frame's page goes into its own <iframe srcdoc> — iframes fully
        isolate the kit's CSS so instances cannot collide — stacked
        vertically, and the single screenshot is cropped back into the
        individual frame PNGs. (2026-08-19: a full card bake was ~1800
        Chrome launches at ~2.3s each; batching divides that by six.)
        """
        iframes = "\n".join(
            '<iframe scrolling="no" srcdoc="%s"></iframe>'
            % html_mod.escape(frame_html(i), quote=True) for i in group)
        page = ("<!doctype html><html><head><style>"
                "*{margin:0;padding:0;border:0}"
                "html,body{background:transparent}"
                "iframe{display:block;width:%dpx;height:%dpx;overflow:hidden;"
                "background:transparent}"
                "</style></head><body>%s</body></html>" % (w, h, iframes))
        tag = "g%04d" % group[0]
        html_path = (frames_dir / (tag + ".html")).resolve()
        shot_path = (frames_dir / (tag + "_shot.png")).resolve()
        html_path.write_text(page)
        cmd = [CHROME, "--headless=new", "--disable-gpu",
               "--force-device-scale-factor=1",
               "--window-size=%d,%d" % (w, h * len(group)),
               "--default-background-color=00000000",
               "--screenshot=" + str(shot_path), "file://" + str(html_path)]
        # Chrome occasionally hangs under system load (a single hung frame
        # sank a 30-minute produce on 2026-08-19); a fresh launch almost
        # always succeeds, so retry before giving up on the whole card.
        err = ""
        for attempt in range(3):
            try:
                proc = subprocess.run(cmd, capture_output=True, text=True,
                                      timeout=120)
                err = (proc.stderr or "")[-200:]
            except subprocess.TimeoutExpired:
                err = "chrome timed out after 120s"
                continue
            if proc.returncode == 0 and shot_path.exists():
                break
        html_path.unlink(missing_ok=True)
        if not shot_path.exists():
            raise IngestError("animation frames %s failed for %s: %s"
                              % (list(group), card["id"], err))
        sheet = Image.open(shot_path).convert("RGBA")
        if sheet.size != (w, h * len(group)):
            raise IngestError("batch screenshot for %s is %s, expected %s"
                              % (card["id"], sheet.size, (w, h * len(group))))
        for j, i in enumerate(group):
            sheet.crop((0, j * h, w, (j + 1) * h)).save(
                frames_dir / ("f%04d.png" % i))
        shot_path.unlink()

    groups = [todo[k:k + CHROME_BATCH] for k in range(0, len(todo), CHROME_BATCH)]
    # Groups are independent, so shoot them concurrently. Chrome is heavy;
    # more than a handful at once just thrashes.
    with ThreadPoolExecutor(max_workers=PARALLEL) as pool:
        list(pool.map(shoot_group, groups))

    src = frames_dir / ("f%04d.png" % hold_src)
    for i in range(n):
        if not moving(i):
            shutil.copyfile(src, frames_dir / ("f%04d.png" % i))

    log("[animate] %s: %d frames @ %dfps (%d rendered, %d held)"
        % (card["id"], n, fps, len(todo), n - len(todo)))
    return encode_frames(frames_dir, out_mov, fps)


def encode_frames(frames_dir: Path, out_mov: Path, fps: int) -> Path:
    """PNG sequence -> ProRes 4444 with a real alpha channel."""
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(fps),
           "-i", str(frames_dir / "f%04d.png"),
           "-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le",
           str(out_mov)]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise IngestError("animation encode failed: %s" % proc.stderr[-300:])
    for png in frames_dir.glob("*.png"):
        png.unlink()
    return out_mov
