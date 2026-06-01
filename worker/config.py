"""Centralized config for the Curated Curiosities pipeline.

All env-based settings live here; modules import from this file rather than
reading os.environ themselves.
"""

from __future__ import annotations
import os
from pathlib import Path

# --- Paths ---------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROGRAM_DIR = Path(__file__).resolve().parent
WORK_DIR = PROGRAM_DIR / "work"
FETCH_SCRIPT = PROJECT_ROOT / "scripts" / "fetch_assets.py"

# --- Brand ---------------------------------------------------------------
# Used for placeholder slates and the watermark margin. Keep in sync with
# brand/visual-identity.md.
BRAND_NAVY = "0x0E1B2C"          # ffmpeg uses 0xRRGGBB
BRAND_AMBER = "0xE8A33D"
BRAND_CREAM = "0xF4EFE6"
WATERMARK_MARGIN_PX = 48          # bottom-right inset

# --- Video output --------------------------------------------------------
LANDSCAPE = (1920, 1080)          # YouTube long-form
PORTRAIT = (1080, 1920)            # Reels, Shorts
DEFAULT_FPS = 30

# --- API keys (read at use-site so missing keys give clear errors) -------
def env(name: str, default: str | None = None) -> str | None:
    v = os.environ.get(name, default)
    return v if v else default

PEXELS_API_KEY = env("PEXELS_API_KEY")
PIXABAY_API_KEY = env("PIXABAY_API_KEY")
ELEVENLABS_API_KEY = env("ELEVENLABS_API_KEY")
ELEVENLABS_VOICE_ID = env("ELEVENLABS_VOICE_ID")  # user's chosen voice
ELEVENLABS_MODEL = env("ELEVENLABS_MODEL", "eleven_multilingual_v2")
OPENAI_API_KEY = env("OPENAI_API_KEY")
OPENAI_TTS_MODEL = env("OPENAI_TTS_MODEL", "tts-1-hd")
OPENAI_TTS_VOICE = env("OPENAI_TTS_VOICE", "onyx")

# --- Helpers -------------------------------------------------------------
def work_path(slug: str) -> Path:
    """Return the work dir for a given video slug, creating it if needed."""
    p = WORK_DIR / slug
    p.mkdir(parents=True, exist_ok=True)
    return p

def output_resolution(shot_list: dict) -> tuple[int, int]:
    """Pick output WxH from the shot list's orientation."""
    orient = (shot_list.get("default_orientation") or "landscape").lower()
    return PORTRAIT if orient == "portrait" else LANDSCAPE
