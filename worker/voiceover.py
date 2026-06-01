"""Voiceover generation.

Three providers, in priority order:
  1. ElevenLabs  — best quality for narration; needs ELEVENLABS_API_KEY +
                   ELEVENLABS_VOICE_ID.
  2. OpenAI TTS  — solid fallback; needs OPENAI_API_KEY.
  3. manual      — caller supplies voiceover.mp3 themselves; this stage is a
                   no-op and just verifies the file exists.

The narration text is read from:
  work/<slug>/voiceover.txt           (preferred — clean spoken text)
  work/<slug>/shot_list.json          (fallback — joined `script_line` fields)

The output is always:
  work/<slug>/voiceover.mp3
"""

from __future__ import annotations
import json
import sys
from pathlib import Path
from typing import Optional

import requests

from . import config


# --- Text sourcing -------------------------------------------------------

def load_narration_text(work_dir: Path) -> str:
    """Return the spoken text for this video.

    Prefers a hand-tuned voiceover.txt; if missing, joins script_line values
    from the shot list as a reasonable default.
    """
    vo_txt = work_dir / "voiceover.txt"
    if vo_txt.exists():
        text = vo_txt.read_text().strip()
        if text:
            return text

    shot_list_path = work_dir / "shot_list.json"
    if not shot_list_path.exists():
        raise FileNotFoundError(
            "Need either voiceover.txt or shot_list.json with script_line fields"
        )
    data = json.loads(shot_list_path.read_text())
    lines = [s.get("script_line", "").strip() for s in data.get("shots", [])]
    lines = [ln for ln in lines if ln]
    if not lines:
        raise ValueError("No narration text found in shot_list.json")
    return " ".join(lines)


# --- Providers -----------------------------------------------------------

def _tts_elevenlabs(text: str, dest: Path) -> None:
    if not config.ELEVENLABS_API_KEY or not config.ELEVENLABS_VOICE_ID:
        raise RuntimeError("ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID not set")
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{config.ELEVENLABS_VOICE_ID}"
    headers = {
        "xi-api-key": config.ELEVENLABS_API_KEY,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }
    body = {
        "text": text,
        "model_id": config.ELEVENLABS_MODEL,
        "voice_settings": {"stability": 0.45, "similarity_boost": 0.75},
    }
    r = requests.post(url, json=body, headers=headers, timeout=180)
    if r.status_code != 200:
        raise RuntimeError(f"ElevenLabs error {r.status_code}: {r.text[:300]}")
    dest.write_bytes(r.content)


def _tts_openai(text: str, dest: Path) -> None:
    if not config.OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY not set")
    url = "https://api.openai.com/v1/audio/speech"
    headers = {
        "Authorization": f"Bearer {config.OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    body = {
        "model": config.OPENAI_TTS_MODEL,
        "voice": config.OPENAI_TTS_VOICE,
        "input": text,
        "response_format": "mp3",
    }
    r = requests.post(url, json=body, headers=headers, timeout=180)
    if r.status_code != 200:
        raise RuntimeError(f"OpenAI TTS error {r.status_code}: {r.text[:300]}")
    dest.write_bytes(r.content)


def _resolve_provider(requested: Optional[str]) -> str:
    """Pick a provider — explicit request wins, else auto-detect by keys."""
    if requested and requested != "auto":
        return requested
    if config.ELEVENLABS_API_KEY and config.ELEVENLABS_VOICE_ID:
        return "elevenlabs"
    if config.OPENAI_API_KEY:
        return "openai"
    return "manual"


# --- Entry point ---------------------------------------------------------

def generate(slug: str, provider: Optional[str] = None) -> Path:
    """Generate voiceover.mp3 for the given video slug. Returns the file path."""
    work = config.work_path(slug)
    out = work / "voiceover.mp3"
    chosen = _resolve_provider(provider)

    print(f"[voiceover] provider: {chosen}")

    if chosen == "manual":
        if not out.exists():
            raise FileNotFoundError(
                f"Manual mode but {out} doesn't exist. Drop your voiceover.mp3 "
                f"into the work dir or set ELEVENLABS_API_KEY/OPENAI_API_KEY."
            )
        print(f"[voiceover] manual mode — using existing {out.name}")
        return out

    text = load_narration_text(work)
    print(f"[voiceover] narrating {len(text)} chars → {out.name}")

    if chosen == "elevenlabs":
        _tts_elevenlabs(text, out)
    elif chosen == "openai":
        _tts_openai(text, out)
    else:
        raise ValueError(f"Unknown provider: {chosen}")

    print(f"[voiceover] ✓ {out}")
    return out
