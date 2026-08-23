"""Phase 2 — ingest: probe + transcribe everything in work/<slug>/footage/.

Outputs (all under work/<slug>/analysis/):
    catalog.json          one entry per raw file: probe facts, speech/broll
                          class, word counts, silence gaps
    <file>.words.json     whisper word timings for speech files: [{"w","s","e"}]

Classification logic: a file with no audio stream is b-roll. A file with
audio gets transcribed; if it barely contains words (ambient sound, wind,
room tone) it is b-roll too. Everything else is speech — the talking-head
takes the rest of the pipeline cuts between.

What breaks if this is wrong: dead-space cuts land mid-word (bad timings) or
b-roll gets treated as a take (bad classification) — every downstream stage
trusts this file.
"""
from __future__ import annotations

import json
import subprocess
import os
import time
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
WORK_DIR = PROJECT_ROOT / "work"

# .webm: MediaRecorder's container — the Studio teleprompter records VO
# takes in the browser (2026-08-23). THE authoritative footage allowlist;
# editroom's upload gate imports it (a second copy is how the upload
# accepted a file ingest then refused to see).
VIDEO_EXT = (".mp4", ".mov", ".m4v", ".mts", ".avi", ".mkv", ".webm")
AUDIO_EXT = (".wav", ".m4a", ".mp3", ".aiff", ".aif")

# A "speech" file must say at least this many words at a plausible rate.
MIN_SPEECH_WORDS = 8
MIN_SPEECH_WPM = 20.0
# A gap this long between consecutive words counts as dead space.
MIN_SILENCE_GAP_SEC = 0.6


class IngestError(RuntimeError):
    pass


def work_path(slug: str) -> Path:
    return WORK_DIR / slug


def write_progress(slug: str, **fields) -> None:
    """Heartbeat for the Edit Room's phase bar. Best-effort by design — a
    progress write must never be able to sink real pipeline work."""
    try:
        p = work_path(slug) / "ingest_progress.json"
        fields["ts"] = time.time()
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(fields))
        os.replace(tmp, p)
    except Exception:
        pass


def analysis_dir(slug: str) -> Path:
    d = work_path(slug) / "analysis"
    d.mkdir(parents=True, exist_ok=True)
    return d


# --- probing --------------------------------------------------------------

def probe_file(path: Path) -> "dict":
    """ffprobe one file into the fields the pipeline cares about."""
    proc = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json",
         "-show_streams", "-show_format", str(path)],
        capture_output=True, text=True)
    if proc.returncode != 0:
        raise IngestError("ffprobe failed for %s: %s" % (path.name, proc.stderr[-300:]))
    info = json.loads(proc.stdout)
    v = next((s for s in info.get("streams", []) if s.get("codec_type") == "video"
              and s.get("disposition", {}).get("attached_pic", 0) != 1), None)
    a = next((s for s in info.get("streams", []) if s.get("codec_type") == "audio"), None)
    fmt = info.get("format", {})
    entry = {
        "name": path.name,
        "path": str(path),
        "kind": "video" if v else "audio",
        "duration": float(fmt.get("duration") or 0.0),
        "has_audio": a is not None,
    }
    if v:
        num, _, den = (v.get("avg_frame_rate") or "0/1").partition("/")
        try:
            fps = float(num) / float(den or 1)
        except (ValueError, ZeroDivisionError):
            fps = 0.0
        entry.update({
            "width": int(v.get("width") or 0),
            "height": int(v.get("height") or 0),
            "fps": round(fps, 3),
            "vcodec": v.get("codec_name"),
        })
    return entry


# --- transcription --------------------------------------------------------

_model = [None]


def _whisper():
    """Load faster-whisper once per process (the import alone takes seconds)."""
    if _model[0] is None:
        from faster_whisper import WhisperModel
        _model[0] = WhisperModel("base.en", device="cpu", compute_type="int8")
    return _model[0]


def transcribe(path: Path) -> "list[dict]":
    """Whisper word timings: [{"w": "Hello", "s": 0.0, "e": 0.42}, ...]."""
    segments, _info = _whisper().transcribe(str(path), word_timestamps=True)
    words = []
    for seg in segments:
        for w in seg.words or []:
            words.append({"w": w.word.strip(), "s": round(w.start, 3), "e": round(w.end, 3)})
    return words


def silence_gaps(words: "list[dict]", duration: float,
                 min_gap: float = MIN_SILENCE_GAP_SEC) -> "list[dict]":
    """Gaps (incl. lead-in and tail) where nothing is said for >= min_gap."""
    gaps = []
    prev_end = 0.0
    for w in words:
        if w["s"] - prev_end >= min_gap:
            gaps.append({"s": round(prev_end, 3), "e": round(w["s"], 3),
                         "d": round(w["s"] - prev_end, 3)})
        prev_end = max(prev_end, w["e"])
    if duration - prev_end >= min_gap:
        gaps.append({"s": round(prev_end, 3), "e": round(duration, 3),
                     "d": round(duration - prev_end, 3)})
    return gaps


# --- the stage ------------------------------------------------------------

def ingest(slug: str, log=print, use_api: bool = False) -> Path:
    """Probe + transcribe + classify every file; write analysis/catalog.json.

    use_api routes transcription through OpenAI Whisper (pipeline/whisper_api)
    for far better proper-noun accuracy, falling back to the local engine per
    file on any failure. Cached words are reused either way — delete a
    .words.json to force re-transcription with the other engine.
    """
    footage = work_path(slug) / "footage"
    if not footage.is_dir():
        raise IngestError("no footage dir: %s" % footage)
    files = sorted(p for p in footage.iterdir()
                   if p.suffix.lower() in VIDEO_EXT + AUDIO_EXT
                   and not p.name.startswith(".")
                   # an upload in flight lives under _tmp. until its rename —
                   # ingest once transcribed a half-uploaded clip (2026-08-23)
                   and not p.name.startswith("_tmp."))
    if not files:
        raise IngestError("no media files in %s" % footage)

    out = analysis_dir(slug)
    entries = []
    skipped = []
    # ETA is byte-weighted: file size tracks duration closely for same-camera
    # footage, is known instantly, and self-corrects as cached transcriptions
    # fly by. Sizes are captured up front so a file removed mid-run (Caleb
    # pruning the inventory while ingest runs) cannot crash the accounting.
    sizes = {}
    for p in files:
        try:
            sizes[p] = p.stat().st_size
        except OSError:
            sizes[p] = 0
    total_bytes = sum(sizes.values()) or 1
    done_bytes = 0
    t0 = time.time()
    for i, path in enumerate(files):
        elapsed = time.time() - t0
        eta = (elapsed / done_bytes * (total_bytes - done_bytes)
               if done_bytes else None)
        write_progress(slug, stage="transcribe", done=i, total=len(files),
                       current=path.name, pct=done_bytes / total_bytes,
                       eta_s=round(eta) if eta else None)
        done_bytes += sizes[path]  # counted up front so `continue` paths and
        # skip branches below can never desync the accounting
        # One corrupt clip (e.g. a DJI recording stub cut off mid-write) must
        # never sink the whole batch — skip it loudly and move on.
        try:
            entry = probe_file(path)
        except IngestError as e:
            skipped.append(path.name)
            log("[ingest] SKIP %s — unreadable (%s)" % (path.name, e))
            continue
        if entry["duration"] <= 0:
            skipped.append(path.name)
            log("[ingest] SKIP %s — zero duration (interrupted recording?)" % path.name)
            continue
        log("[ingest] %s  %.1fs %s" % (entry["name"], entry["duration"],
                                       "audio" if entry["kind"] == "audio" else
                                       "%dx%d@%s" % (entry.get("width", 0), entry.get("height", 0), entry.get("fps"))))
        if entry["has_audio"]:
            # Transcriptions are cached per file so a rerun (or a timeout
            # recovery) never repeats whisper work it already did.
            words_file = entry["name"] + ".words.json"
            words_path = out / words_file
            if words_path.exists():
                words = json.loads(words_path.read_text())
            else:
                words = None
                if use_api:
                    from . import whisper_api
                    try:
                        words = whisper_api.transcribe(str(path))
                        log("         transcribed via API")
                    except whisper_api.WhisperApiError as e:
                        log("         API transcription failed (%s) — using local" % e)
                if words is None:
                    words = transcribe(path)
                # Fix whisper's phonetic name spellings before anything
                # downstream reads them (brand/names.json — e.g. Sofia).
                from . import names as names_mod
                fixed = names_mod.correct_words(words)
                if fixed:
                    log("         %d name spellings corrected" % fixed)
                words_path.write_text(json.dumps(words))
            n = len(words)
            minutes = entry["duration"] / 60.0 if entry["duration"] else 1.0
            wpm = n / minutes
            is_speech = n >= MIN_SPEECH_WORDS and wpm >= MIN_SPEECH_WPM
            entry["class"] = "speech" if is_speech else "broll"
            entry["n_words"] = n
            entry["wpm"] = round(wpm, 1)
            entry["words_file"] = words_file
            if is_speech:
                entry["silence"] = silence_gaps(words, entry["duration"])
                log("         speech: %d words (%.0f wpm), %d silence gaps"
                    % (n, wpm, len(entry["silence"])))
            else:
                log("         broll (audio but only %d words)" % n)
        else:
            entry["class"] = "broll"
            log("         broll (no audio)")
        entries.append(entry)

    catalog = {
        "slug": slug,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "files": entries,
        "skipped": skipped,
    }
    from . import schemas
    errors = schemas.validate_catalog(catalog)
    if errors:
        raise IngestError("catalog failed validation:\n  " + "\n  ".join(errors))
    catalog_path = out / "catalog.json"
    catalog_path.write_text(json.dumps(catalog, indent=2))
    log("[ingest] wrote %s (%d files)" % (catalog_path, len(entries)))
    return catalog_path
