"""Video assembly via FFmpeg.

Reads `shot_list.json` + the `assets/` folder + optional `voiceover.mp3` +
optional `watermark.png` and produces `rough_cut.mp4`.

Stages run as discrete ffmpeg calls so failures are debuggable:
  1. normalize each shot → tmp/<id>.mp4 (uniform res / fps / codec, no audio)
  2. concat → tmp/combined.mp4
  3. mux voiceover (if present) → tmp/with_vo.mp4
  4. overlay watermark (if present) → rough_cut.mp4

Non-stock shots get a brand-navy placeholder slate of the right duration so
pacing in the rough cut is correct; you swap them in your NLE later.
"""

from __future__ import annotations
import json
import shutil
import subprocess
import sys
from pathlib import Path

from . import config


# --- Preflight -----------------------------------------------------------

def ensure_ffmpeg() -> None:
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("ffmpeg not found on PATH. Install with `brew install ffmpeg` or `apt install ffmpeg`.")


def run(cmd: list[str], *, allow_fail: bool = False) -> subprocess.CompletedProcess:
    """Run a subprocess; print the command on failure for easy debugging."""
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0 and not allow_fail:
        print("\n[ffmpeg] command failed:\n  " + " ".join(cmd), file=sys.stderr)
        print(proc.stderr[-1500:], file=sys.stderr)
        raise RuntimeError("ffmpeg call failed")
    return proc


# --- Asset resolution ----------------------------------------------------

def shot_folder(assets_root: Path, shot_id: str) -> Path | None:
    """Find the assets folder for a shot (named like `S01_<slug>/`)."""
    for child in assets_root.iterdir():
        if child.is_dir() and child.name.startswith(f"{shot_id}_"):
            return child
    return None


def pick_asset(assets_root: Path, shot_id: str, selections: dict) -> Path | None:
    """Return the chosen file for this shot, or None if no stock candidates exist."""
    folder = shot_folder(assets_root, shot_id)
    if not folder:
        return None
    # explicit selection wins
    chosen_name = selections.get(shot_id)
    if chosen_name:
        p = folder / chosen_name
        if p.exists():
            return p
    # else first candidate found
    candidates = sorted(folder.glob(f"{shot_id}_cand*.mp4"))
    return candidates[0] if candidates else None


# --- Per-shot ffmpeg ----------------------------------------------------

def normalize_stock_shot(src: Path, dest: Path, dur: float, w: int, h: int) -> None:
    """Trim + scale-and-crop a real clip to the target output dims."""
    vf = (
        f"scale={w}:{h}:force_original_aspect_ratio=increase,"
        f"crop={w}:{h},fps={config.DEFAULT_FPS},setsar=1,format=yuv420p"
    )
    cmd = [
        "ffmpeg", "-y", "-i", str(src),
        "-t", f"{dur:.3f}",
        "-vf", vf,
        "-an",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        str(dest),
    ]
    run(cmd)


def placeholder_slate(dest: Path, dur: float, w: int, h: int, label: str) -> None:
    """Generate a brand-navy slate of the given duration; attempt to burn the
    shot label in cream — if the system has no usable font for drawtext, fall
    back to a plain colored slate."""
    base_input = f"color=c={config.BRAND_NAVY}:s={w}x{h}:r={config.DEFAULT_FPS}:d={dur:.3f}"

    # Attempt with drawtext label
    safe = label.replace(":", " ").replace("'", "").replace("\\", "")
    vf_with_text = (
        f"drawtext=text='{safe}':fontcolor={config.BRAND_CREAM}:fontsize={int(h*0.035)}:"
        f"x=(w-text_w)/2:y=(h-text_h)/2,format=yuv420p"
    )
    with_text = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", base_input,
        "-vf", vf_with_text,
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
        str(dest),
    ]
    proc = run(with_text, allow_fail=True)
    if proc.returncode == 0:
        return

    # Fallback: plain colored slate, no text (no font available)
    plain = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", base_input,
        "-vf", "format=yuv420p",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
        str(dest),
    ]
    run(plain)


# --- Concat + mux + overlay ---------------------------------------------

def concat_clips(clip_paths: list[Path], dest: Path, tmp_dir: Path) -> None:
    """Concatenate uniformly-encoded clips via the concat demuxer."""
    list_file = tmp_dir / "concat.txt"
    list_file.write_text("\n".join(f"file '{p.as_posix()}'" for p in clip_paths))
    cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(list_file), "-c", "copy", str(dest),
    ]
    proc = run(cmd, allow_fail=True)
    if proc.returncode == 0:
        return
    # Fallback: re-encode concat in case copy mode rejects something
    cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(list_file),
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-pix_fmt", "yuv420p", str(dest),
    ]
    run(cmd)


def mux_voiceover(video_in: Path, vo_path: Path, dest: Path) -> None:
    cmd = [
        "ffmpeg", "-y", "-i", str(video_in), "-i", str(vo_path),
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        "-shortest", str(dest),
    ]
    run(cmd)


def overlay_watermark(video_in: Path, wm_path: Path, dest: Path) -> None:
    m = config.WATERMARK_MARGIN_PX
    cmd = [
        "ffmpeg", "-y", "-i", str(video_in), "-i", str(wm_path),
        "-filter_complex", f"[0:v][1:v]overlay=W-w-{m}:H-h-{m}:format=auto[v]",
        "-map", "[v]", "-map", "0:a?",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-c:a", "copy",
        str(dest),
    ]
    run(cmd)


# --- Entry point ---------------------------------------------------------

def assemble(slug: str) -> Path:
    """Build rough_cut.mp4 for the given video slug. Returns the output path."""
    ensure_ffmpeg()

    work = config.work_path(slug)
    shot_list_path = work / "shot_list.json"
    if not shot_list_path.exists():
        raise FileNotFoundError(f"Missing {shot_list_path}")

    shot_list = json.loads(shot_list_path.read_text())
    w, h = config.output_resolution(shot_list)
    print(f"[assemble] output {w}x{h} @ {config.DEFAULT_FPS}fps")

    assets_root = work / "assets" / _video_title_slug(shot_list)
    if not assets_root.exists():
        # Fallback: maybe a single nested dir under assets/
        candidates = [p for p in (work / "assets").iterdir() if p.is_dir()] if (work / "assets").exists() else []
        if len(candidates) == 1:
            assets_root = candidates[0]
        else:
            assets_root = work / "assets"

    selections_path = work / "selections.json"
    selections = json.loads(selections_path.read_text()) if selections_path.exists() else {}

    tmp_dir = work / "tmp"
    tmp_dir.mkdir(exist_ok=True)
    per_shot: list[Path] = []

    for shot in shot_list.get("shots", []):
        sid = shot.get("shot_id", "S?")
        dur = float(shot.get("duration_sec", 3))
        stype = shot.get("source_type", "stock")
        clip_out = tmp_dir / f"{sid}.mp4"

        if stype == "stock":
            asset = pick_asset(assets_root, sid, selections)
            if asset:
                print(f"  [{sid}] normalize {asset.name} → {dur:.2f}s")
                normalize_stock_shot(asset, clip_out, dur, w, h)
            else:
                print(f"  [{sid}] NO STOCK CANDIDATE — slate placeholder")
                placeholder_slate(clip_out, dur, w, h, f"{sid} · missing stock")
        else:
            label = f"{sid} · {stype.upper()} · {shot.get('visual','')[:80]}"
            print(f"  [{sid}] {stype} → slate")
            placeholder_slate(clip_out, dur, w, h, label)

        per_shot.append(clip_out)

    if not per_shot:
        raise RuntimeError("No shots assembled — empty shot_list?")

    combined = tmp_dir / "combined.mp4"
    print(f"[assemble] concat {len(per_shot)} clips")
    concat_clips(per_shot, combined, tmp_dir)

    # Voiceover
    vo = work / "voiceover.mp3"
    after_vo = tmp_dir / "with_vo.mp4"
    if vo.exists():
        print(f"[assemble] mux voiceover ({vo.name})")
        mux_voiceover(combined, vo, after_vo)
    else:
        print("[assemble] no voiceover.mp3 — output will be silent")
        after_vo = combined

    # Watermark — work dir overrides, otherwise use the brand default
    wm = work / "watermark.png"
    if not wm.exists():
        default_wm = config.PROJECT_ROOT / "brand" / "exports" / "watermark.png"
        if default_wm.exists():
            wm = default_wm
    final = work / "rough_cut.mp4"
    if wm.exists():
        print(f"[assemble] overlay watermark ({wm.name})")
        overlay_watermark(after_vo, wm, final)
    else:
        print("[assemble] no watermark.png — skipping overlay")
        shutil.copy2(after_vo, final)

    print(f"[assemble] ✓ {final}")
    return final


# --- Internal ------------------------------------------------------------

def _video_title_slug(shot_list: dict) -> str:
    """Mirror fetch_assets.py's slug() for the assets root folder."""
    import re
    title = shot_list.get("video_title", "video")
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:40] or "video"
