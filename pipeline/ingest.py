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

import contextlib
import json
import subprocess
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from . import fill
from . import screen as screen_mod

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
    """A pipeline failure, optionally with a STABLE CODE.

    The message is for a human reading a log; the code is for the desk
    that has to explain the failure and offer a way out. Matching on prose
    is how a reworded error silently turns a fix door into a dead end, so
    the Studio matches on `code` and falls back to the message when there
    is none — which is most of them, deliberately. Only the failures a
    desk can actually do something about earn a code.
    """

    def __init__(self, msg, code=None):
        super().__init__(msg)
        self.code = code


def work_path(slug: str) -> Path:
    return WORK_DIR / slug


# slug -> callback, installed by whoever is RUNNING the ingest.
#
# `write_progress` is the one funnel every stage already goes through —
# transcribe, takes and b-roll all call it — so an observer here reaches
# all three without changing a single signature.
_PROGRESS_HOOKS: "dict" = {}
_HOOK_LOCK = threading.Lock()


@contextlib.contextmanager
def observing(slug: str, fn):
    """While this is open, every `write_progress` for `slug` is also handed
    to `fn`.

    The engine has always known its own progress — byte-weighted, with an
    ETA, written per file since the ingest work. It reached the project
    row and the Footage desk and never the JOB, so the Activity dock, the
    one surface whose whole purpose is showing what is running, sat at a
    hardcoded 2% for the entire transcription and said "probe +
    transcribe" (Caleb, 2026-08-26).
    """
    with _HOOK_LOCK:
        _PROGRESS_HOOKS[slug] = fn
    try:
        yield
    finally:
        with _HOOK_LOCK:
            _PROGRESS_HOOKS.pop(slug, None)


def write_progress(slug: str, **fields) -> None:
    """Heartbeat for the desks' phase bars. Best-effort by design — a
    progress write must never be able to sink real pipeline work."""
    fields["ts"] = time.time()
    try:
        p = work_path(slug) / "ingest_progress.json"
        # a tmp name NOBODY ELSE CAN BE USING. A fixed `.tmp` sibling is
        # worse than no atomicity once two writers exist: one's replace
        # moves the file out from under the other. Auto-ingest fires per
        # upload, so two runs 35 seconds apart is ordinary (2026-08-26).
        tmp = p.with_suffix(".%d.%d.tmp" % (os.getpid(), threading.get_ident()))
        try:
            tmp.write_text(json.dumps(fields))
            os.replace(tmp, p)
        except BaseException:
            try:
                tmp.unlink()
            except OSError:
                pass
            raise
    except Exception:
        pass
    # the observer runs even if the WRITE failed: a dock that keeps moving
    # is worth more than a file nobody is reading yet
    with _HOOK_LOCK:
        fn = _PROGRESS_HOOKS.get(slug)
    if fn is not None:
        try:
            fn(dict(fields))
        except Exception:
            pass


def facts_rejected(slug: str) -> "set":
    """Names rejected at triage. Empty when nothing has been triaged.

    Read through a late import: `facts` resolves work_path through THIS
    module, so importing it at module scope would close the circle.
    A missing or unreadable sidecar means "nothing rejected" — triage
    data must never be able to stop an analysis from running.
    """
    try:
        from . import facts
        return facts.read_rejected(slug)
    except Exception:
        return set()


def _write_atomic(path: Path, data) -> None:
    """tmp + replace, with a tmp name nobody else can be using.

    A fixed `.tmp` sibling is worse than no atomicity once two writers
    exist — one's replace moves the file out from under the other. The
    same rule `facts._write_atomic` and `editroom._write_json` carry.
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
        # The FILE NAME is the whole value of this error on a 368-clip
        # drop, so it leads; ffprobe's stderr is trimmed to its last real
        # line ("moov atom not found") rather than 300 characters of it.
        why = next((ln.strip() for ln in reversed(proc.stderr.splitlines())
                    if ln.strip()), "ffprobe gave no reason")
        raise IngestError("could not read %s — %s" % (path.name, why[:200]),
                          code="bad_file")
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
    # WHEN it was shot. `-show_format` has always been requested and every
    # tag it returns was thrown away, so shot order could only ever be
    # guessed from filenames — which breaks the moment two cameras are
    # rolling, because each numbers its own card from 0001 (2026-08-27).
    # Cameras write it as UTC ISO-8601; a container that carries none
    # simply has no `created_at`, and the desk omits the fact rather than
    # inventing one (non-negotiable 7).
    created = (fmt.get("tags") or {}).get("creation_time")
    if isinstance(created, str) and created.strip():
        entry["created_at"] = created.strip()
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
        # DO NOT "optimise" these settings. Measured 2026-08-24 over 10
        # real speech clips (172s) against the current beam_size=5:
        #   beam_size=1      26% faster, 1/10 transcripts identical,
        #                    word agreement 0.52
        #   vad_filter=True  51% faster, 0/10 identical, agreement 0.43
        # The words genuinely change on this museum audio — one 19s clip
        # went from "the turkeys don't stop eating" to "the toilet's not
        # the store" to "a term of the story of the man". Transcripts
        # drive take selection, the edit plan and the captions, so the
        # speedup is paid for in the only currency that matters.
        # (If transcript QUALITY ever becomes the problem, the lever is a
        # BIGGER model — small.en — not a cheaper decode.)
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
        raise IngestError("no footage dir: %s" % footage, code="no_media")
    files = sorted(p for p in footage.iterdir()
                   if p.suffix.lower() in VIDEO_EXT + AUDIO_EXT
                   and not p.name.startswith(".")
                   # an upload in flight lives under _tmp. until its rename —
                   # ingest once transcribed a half-uploaded clip (2026-08-23)
                   and not p.name.startswith("_tmp."))
    if not files:
        raise IngestError("no media files in %s" % footage, code="no_media")

    # PASS 2 respects the triage pass 1 enabled.
    #
    # A rejected clip is not transcribed, not sheeted and not catalogued:
    # that is the entire point of splitting the passes. Whisper is the
    # expensive stage, and spending it on footage Caleb has already looked
    # at and thrown away was the inversion this work exists to fix
    # (2026-08-27). Rejection lives in a sidecar, so a re-ingest cannot
    # silently undo it — the same reason take verdicts do.
    #
    # A project with no verdicts (and every project made before this) is
    # unaffected: the set is empty and every file goes through.
    rejected = facts_rejected(slug)
    if rejected:
        before = len(files)
        files = [p for p in files if p.name not in rejected]
        log("[ingest] %d of %d clips rejected at triage — not transcribed"
            % (before - len(files), before))
        if not files:
            raise IngestError(
                "every clip is rejected — nothing left to analyze",
                code="all_rejected")

    out = analysis_dir(slug)
    entries = []
    skipped = []
    seen_sigs: "dict" = {}   # content signature -> first file that claimed it
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
        # The pre-screen: mechanically useless footage costs the same to
        # transcribe and sheet as good footage. Set it aside BEFORE that
        # bill is paid — never moving or deleting it, only flagging why
        # (2026-08-24).
        try:
            entry["sig"] = screen_mod.content_sig(path, sizes[path])
        except OSError:
            pass
        entry = screen_mod.screen(entry, seen_sigs)
        if entry.get("screened_out"):
            # `class` is REQUIRED on every catalog file, and this branch
            # jumps past both places that set it — so the first
            # screened-out clip in a shoot failed the whole ingest at
            # validation with "catalog.files[N]: missing 'class'", and no
            # catalog was written at all (2026-08-26).
            #
            # `broll` is the honest value: whisper never ran on this file,
            # so it is certainly not speech, and it carries no words_file
            # — which validate_catalog demands of anything claiming to be.
            # Nothing downstream is misled: every other consumer keys on
            # class == "speech", and broll.py, the one that looks for
            # "broll", already excludes screened_out on the next line.
            # What governs this file is `screened_out`, not its class.
            entry["class"] = "broll"
            entries.append(entry)
            log("[ingest] SET ASIDE %s — %s"
                % (entry["name"], entry["screen_reason"]))
            continue
        log("[ingest] %s  %.1fs %s" % (entry["name"], entry["duration"],
                                       "audio" if entry["kind"] == "audio" else
                                       "%dx%d@%s" % (entry.get("width", 0), entry.get("height", 0), entry.get("fps"))))
        # A vertical clip keeps its shape and gains a ground (Caleb,
        # 2026-08-24): bake a 16:9 companion — same frame zoomed, blurred
        # and dimmed behind the native-aspect original — and point the
        # CATALOG at it. proxy.py, produce.py and deliver.py all resolve
        # media through the catalog, so this one redirect is the whole
        # integration; nothing downstream learns about orientation.
        if fill.is_portrait(entry.get("width"), entry.get("height")):
            from . import timeline  # lazy: timeline imports from us
            canvas = timeline.CANVAS["landscape"]
            dest = fill.filled_path(work_path(slug), entry["name"])
            try:
                if not dest.exists():
                    fill.bake(Path(entry["path"]), dest, canvas, log=log)
                entry = fill.redirect(entry, dest, canvas)
            except (RuntimeError, OSError) as e:
                # a failed fill must not sink the ingest: the clip stays
                # usable in its native shape, pillarboxed, and says so
                log("[ingest] fill FAILED for %s (%s) — using it native"
                    % (entry["name"], e))
        if entry["has_audio"]:
            # Transcriptions are cached per file so a rerun (or a timeout
            # recovery) never repeats whisper work it already did.
            words_file = entry["name"] + ".words.json"
            words_path = out / words_file
            words = None
            if words_path.exists():
                try:
                    words = json.loads(words_path.read_text())
                except ValueError:
                    # A crash mid-write leaves a truncated .words.json,
                    # and this used to read it unguarded — so EVERY later
                    # ingest of that project raised JSONDecodeError until
                    # someone deleted the file by hand. A corrupt cache is
                    # a cache miss, not a failure (2026-08-27).
                    log("         cached transcript unreadable — re-transcribing")
                    try:
                        words_path.unlink()
                    except OSError:
                        pass
                    words = None
            if words is None:
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
    # Atomic, like every other multi-writer file in this engine. A plain
    # write_text leaves a HALF catalog if the process dies mid-write, and
    # `_catalog_read` degrades that to "nothing analyzed" — which is the
    # right failure but not one worth having (2026-08-27).
    _write_atomic(catalog_path, catalog)
    log("[ingest] wrote %s (%d files)" % (catalog_path, len(entries)))
    log("[ingest] %s" % screen_mod.tally(entries))
    return catalog_path
