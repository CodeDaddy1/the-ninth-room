"""Optional OpenAI Whisper transcription for ingest (`ingest <slug> --api`).

Why it exists: the local base.en model mis-hears proper nouns and placard
reads ("Vendo Mitzelgore" for Bandō Mitsugorō VIII), and every mis-hearing
becomes downstream work for the caption-editor. The API's larger model gets
far more of these right on the first pass. Cost is a few cents per shoot;
local stays the default and the automatic fallback, so the $0 baseline holds.

Two things this module must preserve for the rest of the pipeline:

1. **The words format**: [{"w","s","e"}] — same as local transcription.
2. **Punctuation on the words.** The API's word list strips punctuation, but
   sentence-boundary gating (no cut mid-sentence) reads it off the words. So
   the words are re-tokenised from the punctuated segment text and zipped
   with the API's word timings; on a count mismatch the raw API words are
   kept for that segment (timing beats punctuation when we can't have both).

Stdlib only (urllib multipart, same pattern as the watch skill's client).
Audio ships as mono 16 kHz 64 kbps mp3 — a 4-minute clip is ~2 MB, far under
the API's 25 MB cap; anything that would exceed it falls back to local.

What breaks if this is wrong: word times drift and every cut/caption in the
video inherits the drift — verify a sample file's words against the local
engine's before trusting a new variant of this code.
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
import uuid
from pathlib import Path
from urllib.request import Request, urlopen

ENDPOINT = "https://api.openai.com/v1/audio/transcriptions"
MODEL = "whisper-1"
MAX_UPLOAD_BYTES = 24 * 1024 * 1024
KEY_FILE = Path.home() / ".config" / "watch" / ".env"


class WhisperApiError(RuntimeError):
    pass


def load_key() -> "str | None":
    key = os.environ.get("OPENAI_API_KEY")
    if key:
        return key.strip()
    if KEY_FILE.exists():
        for line in KEY_FILE.read_text().splitlines():
            if line.strip().startswith("OPENAI_API_KEY="):
                v = line.split("=", 1)[1].strip()
                if v and not v.startswith("..."):
                    return v
    return None


def _extract_audio(video: str) -> Path:
    out = Path(tempfile.gettempdir()) / ("wapi_%s.mp3" % uuid.uuid4().hex[:10])
    proc = subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", video, "-vn",
         "-ac", "1", "-ar", "16000", "-b:a", "64k", str(out)],
        capture_output=True, text=True)
    if proc.returncode != 0 or not out.exists():
        raise WhisperApiError("audio extract failed: %s" % proc.stderr[-200:])
    return out


def _multipart(fields: "list", file_field: str, filename: str, blob: bytes) -> "tuple":
    """fields is a list of (name, value) pairs — the transcription endpoint
    needs `timestamp_granularities[]` REPEATED (word AND segment); with only
    `word` requested the response carries no segments at all, and without
    segments there is no punctuation to merge (found empirically)."""
    boundary = "----wapi" + uuid.uuid4().hex
    parts = []
    for k, v in fields:
        parts.append(("--%s\r\nContent-Disposition: form-data; name=\"%s\"\r\n\r\n%s\r\n"
                      % (boundary, k, v)).encode())
    parts.append(("--%s\r\nContent-Disposition: form-data; name=\"%s\"; filename=\"%s\"\r\n"
                  "Content-Type: audio/mpeg\r\n\r\n" % (boundary, file_field, filename)).encode())
    parts.append(blob)
    parts.append(("\r\n--%s--\r\n" % boundary).encode())
    return b"".join(parts), "multipart/form-data; boundary=" + boundary


def _merge_punctuation(segments: "list", words: "list[dict]") -> "list[dict]":
    """Give the timed words the punctuation their segment text carries."""
    out = []
    for seg in segments or []:
        seg_words = [w for w in words
                     if seg["start"] - 0.05 <= w["s"] and w["e"] <= seg["end"] + 0.05]
        tokens = [t for t in str(seg.get("text", "")).split() if t]
        if len(tokens) == len(seg_words):
            for tok, w in zip(tokens, seg_words):
                out.append({"w": tok, "s": w["s"], "e": w["e"]})
        else:
            out.extend(seg_words)
    known = {(w["s"], w["e"]) for w in out}
    out.extend(w for w in words if (w["s"], w["e"]) not in known)
    out.sort(key=lambda w: w["s"])
    return out


def transcribe(video: str, key: "str | None" = None) -> "list[dict]":
    """Word-timed transcription via the API. Raises WhisperApiError on any
    failure so the caller can fall back to the local engine."""
    key = key or load_key()
    if not key:
        raise WhisperApiError("no OPENAI_API_KEY available")
    audio = _extract_audio(video)
    try:
        blob = audio.read_bytes()
        if len(blob) > MAX_UPLOAD_BYTES:
            raise WhisperApiError("audio %0.1f MB exceeds upload cap" % (len(blob) / 1e6))
        body, ctype = _multipart(
            [("model", MODEL), ("response_format", "verbose_json"),
             ("timestamp_granularities[]", "word"),
             ("timestamp_granularities[]", "segment")],
            "file", audio.name, blob)
        req = Request(ENDPOINT, data=body, method="POST",
                      headers={"Authorization": "Bearer " + key,
                               "Content-Type": ctype})
        with urlopen(req, timeout=600) as resp:
            data = json.loads(resp.read().decode())
    except WhisperApiError:
        raise
    except Exception as exc:  # noqa: BLE001 — network/API errors become one type
        raise WhisperApiError(str(exc)[:300])
    finally:
        audio.unlink(missing_ok=True)

    words = [{"w": str(w.get("word", "")).strip(),
              "s": round(float(w.get("start", 0.0)), 3),
              "e": round(float(w.get("end", 0.0)), 3)}
             for w in data.get("words", []) if str(w.get("word", "")).strip()]
    if not words:
        raise WhisperApiError("API returned no words")
    segs = [{"start": float(s.get("start", 0)), "end": float(s.get("end", 0)),
             "text": s.get("text", "")} for s in data.get("segments", [])]
    return _merge_punctuation(segs, words)
