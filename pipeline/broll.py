"""Phase 3 — b-roll catalog: give every non-speech clip an id and a contact
sheet the agents can SEE.

Claude Code subagents can read images, so a 3x3 grid of frames per clip is
how the story-designer "watches" b-roll without watching video. The sheet
plus duration is enough to decide "this is the dinosaur hall wide shot, use
it under beat 2." The agent writes its descriptions/tags into broll.json's
`description` field later (Phase 4 pre-work) — Python leaves it empty.

What breaks if this is wrong: the agent places b-roll blind (missing/black
frames on the sheet) or references clips that don't exist (bad ids).
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from PIL import Image

from .ingest import analysis_dir, IngestError

TILE_W, TILE_H = 480, 270  # 16:9 tiles; portrait sources letterbox inside
GRID = 3  # 3x3 = 9 frames per sheet


def contact_sheet(src: Path, duration: float, dest: Path, tmp_dir: Path) -> None:
    """Grab GRID*GRID evenly spaced frames and paste them into one jpg."""
    n = GRID * GRID
    tmp_dir.mkdir(parents=True, exist_ok=True)
    frames = []
    for i in range(n):
        # Sample the middle of each of n equal slices: avoids the black/blurry
        # first frame and the tail ramp.
        t = duration * (i + 0.5) / n
        frame = tmp_dir / ("f%02d.jpg" % i)
        proc = subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-ss", "%.3f" % t,
             "-i", str(src), "-frames:v", "1",
             "-vf", "scale=%d:%d:force_original_aspect_ratio=decrease" % (TILE_W, TILE_H),
             str(frame)],
            capture_output=True, text=True)
        if proc.returncode == 0 and frame.exists():
            frames.append(frame)
    if not frames:
        raise IngestError("no frames extracted from %s" % src.name)

    sheet = Image.new("RGB", (TILE_W * GRID, TILE_H * GRID), (14, 27, 44))
    for i, frame in enumerate(frames):
        img = Image.open(frame)
        x = (i % GRID) * TILE_W + (TILE_W - img.width) // 2
        y = (i // GRID) * TILE_H + (TILE_H - img.height) // 2
        sheet.paste(img, (x, y))
    sheet.save(dest, quality=82)
    for frame in frames:
        frame.unlink()


def catalog_broll(slug: str, log=print) -> Path:
    """Read catalog.json, write analysis/broll.json + analysis/sheets/*.jpg."""
    out = analysis_dir(slug)
    catalog_path = out / "catalog.json"
    if not catalog_path.exists():
        raise IngestError("no catalog.json — run ingest first")
    catalog = json.loads(catalog_path.read_text())

    sheets_dir = out / "sheets"
    sheets_dir.mkdir(exist_ok=True)
    tmp_dir = out / "tmp_frames"

    clips = []
    for f in catalog["files"]:
        if f.get("class") != "broll" or f.get("kind") != "video":
            continue
        cid = "B%03d" % (len(clips) + 1)
        sheet_name = f["name"] + ".sheet.jpg"
        sheet_path = sheets_dir / sheet_name
        if not sheet_path.exists():  # cached across reruns, like transcriptions
            contact_sheet(Path(f["path"]), f["duration"], sheet_path, tmp_dir)
        clips.append({
            "id": cid,
            "file": f["name"],
            "duration": f["duration"],
            "width": f.get("width"),
            "height": f.get("height"),
            "sheet": "sheets/" + sheet_name,
            "description": "",  # filled by the story-designer's pre-work
            "tags": [],
        })
        log("[broll] %s %s %.1fs -> %s" % (cid, f["name"], f["duration"], sheet_name))

    if tmp_dir.exists():
        try:
            tmp_dir.rmdir()
        except OSError:
            pass

    data = {"slug": slug, "clips": clips}
    from . import schemas
    errors = schemas.validate_broll(data)
    if errors:
        raise IngestError("broll.json failed validation:\n  " + "\n  ".join(errors))
    path = out / "broll.json"
    path.write_text(json.dumps(data, indent=2))
    log("[broll] wrote %s (%d clips)" % (path, len(clips)))
    return path
