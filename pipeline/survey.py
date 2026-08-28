# -*- coding: utf-8 -*-
"""Pass 1 — see the shoot before spending whisper on it.

Ingest used to be one pass: probe, screen, fill, TRANSCRIBE, classify,
takes, b-roll. Whisper ran on every clip with an audio stream before a
human had looked at anything, and the desk's own thumbnails were a side
effect of a GET request that shelled ffprobe and ffmpeg per file while
the page waited. So the cheap, decision-enabling work was hidden inside
a page load and the expensive, unattended work was the thing with a
progress bar. Caleb could not reject a clip before it had already cost
him the whisper minutes, because he could not see it until they were
spent (audit, 2026-08-27).

This is the cheap half, on its own, as a job you can watch:

    probe (one ffprobe)  ->  screen  ->  poster frame  ->  1080p proxy

No transcription. No takes. No b-roll. It writes `analysis/survey.json`
and nothing downstream reads it except the desk and pass 2, so a survey
can be re-run, interrupted, or skipped entirely without the cut noticing.

RESUMABLE by construction: every file is keyed by (size, mtime) and a
file whose key is unchanged AND whose poster and proxy are both still on
disk is skipped. Interrupting a 148-clip survey and starting it again
costs only the clips it had not reached.

What breaks if this is wrong: the desk shows a poster for one clip
against the duration of another, and every judgment made at triage is
made about the wrong footage.

Run: /usr/bin/python3 -m pipeline.cli survey <slug>
"""
import json
import os
import subprocess
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from . import screen as screen_mod
from .ingest import (AUDIO_EXT, VIDEO_EXT, IngestError, analysis_dir,
                     probe_file, work_path, write_progress)

SURVEY_VERSION = 1

# Proxies live beside the footage, hidden like .thumbs and .trash — ingest
# skips dot-names, so they can never be mistaken for footage themselves.
PROXY_DIR = ".proxies"
THUMB_DIR = ".thumbs"

# 1080p, H.264, faststart. The long edge is capped at 1920 and the short
# at 1080 with the aspect preserved, so a portrait clip becomes 608x1080
# rather than a 1080-tall clip 1920 wide. `min(...)` against the source's
# own dimensions is what stops a 720p clip being UPSCALED into a bigger,
# slower file than the original it is meant to make cheap.
PROXY_VF = ("scale='min(1920,iw)':'min(1080,ih)'"
            ":force_original_aspect_ratio=decrease:force_divisible_by=2")
THUMB_W = 320


def _write_atomic(path: Path, data: "dict") -> None:
    """tmp + os.replace, with a tmp name nobody else can be using.

    Written here rather than borrowed from editroom: editroom imports
    ingest, so a survey that imported editroom would close the circle.
    A fixed `.tmp` sibling is worse than no atomicity once two writers
    exist — one's replace moves the file out from under the other, which
    is the hazard `facts._write_atomic` documents.
    """
    tmp = path.with_suffix(".%d.%d.tmp" % (os.getpid(), threading.get_ident()))
    try:
        tmp.write_text(json.dumps(data, indent=2))
        os.replace(tmp, path)
    except BaseException:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise


def survey_path(slug: str) -> Path:
    return analysis_dir(slug) / "survey.json"


def read_survey(slug: str) -> "dict | None":
    """The survey, or None when there isn't one or it is unreadable.

    A half-written survey must degrade to "not surveyed yet" rather than
    take the desk down — the same rule `_catalog_read` follows for the
    catalog, and for the same reason.
    """
    p = survey_path(slug)
    if not p.exists():
        return None
    try:
        d = json.loads(p.read_text())
    except ValueError:
        return None
    return d if isinstance(d, dict) and isinstance(d.get("files"), list) else None


def _media_files(footage: Path) -> "list":
    return sorted(p for p in footage.iterdir()
                  if p.is_file()
                  and p.suffix.lower() in VIDEO_EXT + AUDIO_EXT
                  and not p.name.startswith(".")
                  # an upload in flight lives under _tmp. until its rename
                  and not p.name.startswith("_tmp."))


# 4K HEVC DECODE is the whole cost of a proxy, not the encode.
#
# Measured 2026-08-27 on a 142 MB 13.8s DJI clip: decode-to-null 8.40s,
# libx264 veryfast 8.51s total, h264_videotoolbox 8.47s (and twice the
# file). Hardware DECODE took the same job to 2.66s with a byte-identical
# encode — 3.2x, because the encoder was never the bottleneck. Reaching
# for the hardware ENCODER would have bought nothing and cost quality.
HWACCEL = ["-hwaccel", "videotoolbox"]


def _run_ffmpeg(args: "list", src: Path, out: Path,
                pre: "list | None" = None) -> bool:
    """ffmpeg with hardware decode, falling back to software.

    `pre` goes BEFORE -i. That position is load-bearing for `-ss`: after
    -i it is an output option and ffmpeg decodes the clip from frame 0 to
    reach the seek point, which on 4K HEVC costs the entire decode this
    function exists to avoid.

    Not every container decodes on the media engine, and a machine
    without VideoToolbox must still produce previews — so a hwaccel
    failure is a retry, never an error the user sees.
    """
    for accel in (HWACCEL, []):
        r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error"] + accel
                           + (pre or []) + ["-i", str(src)] + args
                           + [str(out)],
                           capture_output=True)
        if r.returncode == 0 and out.exists() and out.stat().st_size > 0:
            return True
        try:
            out.unlink()
        except OSError:
            pass
    return False


def _poster(src: Path, dest: Path, duration: float) -> bool:
    """One frame, 320px wide. Seeks to mid-clip, never past the end."""
    # Mid-clip, never frame 0: the first frame of a shot is routinely a
    # fade-in, a lens still racking, or the operator's hand — the one
    # frame that cannot tell you whether the clip is worth keeping. Capped
    # at 1s so a long clip still seeks cheaply.
    at = min(1.0, max(duration / 2.0, 0.0)) if duration else 0.0
    tmp = dest.with_suffix(".%d.tmp.jpg" % os.getpid())
    ok = _run_ffmpeg(["-frames:v", "1", "-vf", "scale=%d:-2" % THUMB_W],
                     src, tmp, pre=["-ss", "%.2f" % at])
    if not ok:
        return False
    os.replace(tmp, dest)
    return True


def _proxy(src: Path, dest: Path) -> bool:
    """A scrubbable 1080p H.264 copy.

    Written to a `.partial` sibling and renamed, so a survey killed
    mid-encode leaves no half-file that the next run would trust and the
    desk would try to play. Same discipline as proxy.py and fill.py.
    """
    tmp = dest.with_suffix(".partial.mp4")
    ok = _run_ffmpeg(
        ["-vf", PROXY_VF,
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
         "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "128k", "-ac", "2",
         "-movflags", "+faststart"], src, tmp)
    if not ok:
        return False
    os.replace(tmp, dest)
    return True


def survey(slug: str, log=print, force: bool = False) -> Path:
    """Probe, screen, poster and proxy every file. Writes survey.json.

    TWO PHASES, and the order is the whole point.

    Posters are cheap (one frame) and previews are not (a full decode and
    re-encode). Doing them together means clip 40's poster waits behind
    clip 39's encode, so a 148-clip shoot shows nothing for most of an
    hour. Phase A posters everything and writes the survey; the desk
    fills with real frames in about a minute. Phase B then encodes the
    previews and rewrites the survey as it goes, so tiles gain playback
    progressively instead of all at the end (Caleb's call, 2026-08-27).

    What breaks if this is wrong: the desk sits on placeholder tiles for
    the length of a full transcode and the survey has bought nothing.
    """
    footage = work_path(slug) / "footage"
    if not footage.is_dir():
        raise IngestError("no footage dir: %s" % footage, code="no_media")
    files = _media_files(footage)
    if not files:
        raise IngestError("no media files in %s" % footage, code="no_media")

    thumbs = footage / THUMB_DIR
    proxies = footage / PROXY_DIR
    thumbs.mkdir(exist_ok=True)
    proxies.mkdir(exist_ok=True)

    prev = {} if force else {
        e["name"]: e for e in ((read_survey(slug) or {}).get("files") or [])
        if isinstance(e, dict) and e.get("name")}

    entries, skipped = [], []
    seen_sigs = {}
    reused = 0

    # ---- phase A: probe, screen, poster ----------------------------------
    for i, path in enumerate(files):
        try:
            st = path.stat()
            st_size, mtime = st.st_size, int(st.st_mtime)
        except OSError:
            st_size, mtime = 0, 0
        write_progress(slug, stage="survey", done=i, total=len(files),
                       current=path.name,
                       pct=round(i / float(len(files)), 4), eta_s=None)

        old = prev.get(path.name)
        thumb = thumbs / (path.name + ".jpg")
        if (old and old.get("size") == st_size and old.get("mtime") == mtime
                and (not old.get("thumb") or thumb.exists())):
            if old.get("sig"):
                seen_sigs.setdefault(old["sig"], path.name)
            entries.append(dict(old))
            reused += 1
            continue

        try:
            entry = probe_file(path)
        except IngestError as e:
            # ONE unreadable clip must never sink a 148-file survey — the
            # same bargain ingest makes. It is named, not swallowed.
            log("[survey] SKIP %s — %s" % (path.name, e))
            skipped.append({"name": path.name, "why": str(e),
                            "code": getattr(e, "code", None) or "bad_file"})
            continue
        if entry["duration"] <= 0:
            log("[survey] SKIP %s — zero duration (interrupted recording?)"
                % path.name)
            skipped.append({"name": path.name,
                            "why": "zero duration (interrupted recording?)",
                            "code": "bad_file"})
            continue

        entry["size"] = st_size
        entry["mtime"] = mtime
        try:
            entry["sig"] = screen_mod.content_sig(path, st_size)
        except OSError:
            entry["sig"] = None
        entry = screen_mod.screen(entry, seen_sigs)
        entry["still"] = path.stem.endswith("_still")
        entry["thumb"] = None
        entry["proxy"] = None
        if entry["kind"] == "video" and _poster(path, thumb, entry["duration"]):
            entry["thumb"] = str(thumb)
        entries.append(entry)

    _save(slug, entries, skipped)
    log("[survey] posters done — %d files, %d reused, %d set aside"
        % (len(entries), reused, len(skipped)))

    # ---- phase B: previews ----------------------------------------------
    # A clip already set aside is not worth an encode: it is unreadable, a
    # duplicate, black, or too short to cut.
    todo = [e for e in entries
            if e["kind"] == "video" and not e.get("screened_out")
            and not (e.get("proxy") and Path(e["proxy"]).exists())]
    total_bytes = sum(e.get("size") or 0 for e in todo) or 1
    done_bytes = 0
    t0 = time.time()
    last_save = t0
    made = 0
    for n, entry in enumerate(todo):
        src = footage / entry["name"]
        elapsed = time.time() - t0
        rate = done_bytes / elapsed if elapsed > 1 and done_bytes else 0
        write_progress(slug, stage="previews", done=n, total=len(todo),
                       current=entry["name"],
                       pct=round(done_bytes / float(total_bytes), 4),
                       eta_s=int((total_bytes - done_bytes) / rate) if rate else None)
        dest = proxies / (entry["name"] + ".mp4")
        if _proxy(src, dest):
            entry["proxy"] = str(dest)
            made += 1
        else:
            log("[survey] preview FAILED for %s — the original still plays"
                % entry["name"])
        done_bytes += entry.get("size") or 0
        # Rewrite as we go so the desk gains playback progressively.
        #
        # By TIME, not by count: `made % 5` wrote nothing at all on a
        # four-clip shoot, so every preview landed in one jump at the end
        # — the exact all-at-once reveal the phase split exists to avoid
        # (measured 2026-08-27).
        if time.time() - last_save > 8:
            _save(slug, entries, skipped)
            last_save = time.time()

    _save(slug, entries, skipped)
    write_progress(slug, stage="done", done=len(files), total=len(files),
                   pct=1.0, eta_s=None)
    log("[survey] %d files · %d reused · %d set aside · %d previews"
        % (len(entries), reused, len(skipped), made))
    return survey_path(slug)


def _save(slug: str, entries: "list", skipped: "list") -> None:
    _write_atomic(survey_path(slug), {
        "slug": slug,
        "version": SURVEY_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "files": entries,
        "skipped": skipped,
    })
