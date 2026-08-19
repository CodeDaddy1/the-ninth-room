"""Level the narration across clips before Resolve ever sees it.

Why here and not in Resolve: the scripting API exposes no clip gain or track
volume — `TimelineItem.SetProperty` covers video transforms only (checked in
the API docs). So leveling has to happen on the media.

Why it matters on this footage: the Death by Natural Causes chapter was
narrated quietly while reading placards (mean −31 to −37 dB) while the
butterfly chapter runs −20 to −24 dB. Cut together untouched, viewers reach
for the volume knob halfway through and get blasted at the next chapter.

Method: measure each source file's mean and peak with ffmpeg `volumedetect`,
compute the gain that brings the mean to TARGET_MEAN_DB, then clamp that gain
so the peak still lands under PEAK_CEILING_DB. Files needing less than
MIN_GAIN_DB of correction are left completely alone (no copy, no re-encode).
For the rest we write an audio-only re-encode with `-c:v copy`, so 4K HEVC
video is never touched — a 90-second clip takes about a second.

What breaks if this is wrong: a chapter is inaudible (gain not applied), or
the boost drives peaks into distortion (ceiling ignored), which is worse than
quiet because it cannot be undone.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from .ingest import work_path, analysis_dir, IngestError

TARGET_MEAN_DB = -21.0    # where well-recorded narration in this shoot sits
PEAK_CEILING_DB = -1.5    # leave headroom for the encoder
MIN_GAIN_DB = 1.5         # below this, leave the file untouched
MAX_GAIN_DB = 16.0

_MEAN_RE = re.compile(r"mean_volume:\s*(-?\d+(?:\.\d+)?) dB")
_MAX_RE = re.compile(r"max_volume:\s*(-?\d+(?:\.\d+)?) dB")


def measure(path: str, start: float = 0.0, duration: "float | None" = None) -> "dict":
    """mean/max dBFS for a file or a span of it."""
    cmd = ["ffmpeg", "-hide_banner"]
    if start:
        cmd += ["-ss", "%.3f" % start]
    cmd += ["-i", path]
    if duration:
        cmd += ["-t", "%.3f" % duration]
    cmd += ["-vn", "-af", "volumedetect", "-f", "null", "-"]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    mean = _MEAN_RE.search(proc.stderr)
    peak = _MAX_RE.search(proc.stderr)
    return {"mean": float(mean.group(1)) if mean else None,
            "max": float(peak.group(1)) if peak else None}


def gain_for(mean_db: float, max_db: float) -> float:
    """Gain that hits the target mean without pushing the peak past ceiling."""
    wanted = TARGET_MEAN_DB - mean_db
    headroom = PEAK_CEILING_DB - max_db
    return max(0.0, min(wanted, headroom, MAX_GAIN_DB))


def normalize_files(slug: str, files: "list[dict]", log=print) -> "dict[str, str]":
    """Level every file that needs it. Returns {original name: path to use}.

    Only the audio stream is re-encoded; the video stream is stream-copied.
    Results are cached in analysis/audio.json so reruns are instant.
    """
    out_dir = work_path(slug) / "normalized"
    out_dir.mkdir(exist_ok=True)
    cache_path = analysis_dir(slug) / "audio.json"
    cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}

    mapping: "dict[str, str]" = {}
    changed = False
    for f in files:
        name = f["name"]
        entry = cache.get(name)
        if entry is None:
            m = measure(f["path"])
            if m["mean"] is None:
                cache[name] = {"gain": 0.0, "mean": None}
                changed = True
                continue
            g = round(gain_for(m["mean"], m["max"] if m["max"] is not None else 0.0), 2)
            entry = {"gain": g, "mean": m["mean"], "max": m["max"]}
            cache[name] = entry
            changed = True

        gain = entry.get("gain", 0.0)
        if gain < MIN_GAIN_DB:
            continue
        dest = out_dir / (Path(name).stem + "_norm.mp4")
        if not dest.exists():
            proc = subprocess.run(
                ["ffmpeg", "-y", "-loglevel", "error", "-i", f["path"],
                 "-c:v", "copy", "-af", "volume=%.2fdB" % gain,
                 "-c:a", "aac", "-b:a", "192k", str(dest)],
                capture_output=True, text=True)
            if proc.returncode != 0:
                raise IngestError("audio normalize failed for %s: %s"
                                  % (name, proc.stderr[-300:]))
            log("[audio] %s  %+.1f dB (mean %.1f -> %.1f)"
                % (name[-16:], gain, entry["mean"], entry["mean"] + gain))
        mapping[name] = str(dest)

    if changed:
        cache_path.write_text(json.dumps(cache, indent=2))
    return mapping
