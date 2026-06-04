"""Centralized config for the Curated Curiosities pipeline.

All env-based settings live here; modules import from this file rather than
reading os.environ themselves. Loads `.env` at the repo root on import so the
worker doesn't need a venv-activation shim.
"""

from __future__ import annotations
import os
from pathlib import Path

# --- Paths ---------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
WORKER_DIR = Path(__file__).resolve().parent
FETCH_SCRIPT = PROJECT_ROOT / "scripts" / "fetch_assets.py"


# --- .env loader (no python-dotenv dependency) ---------------------------
def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        k, _, v = line.partition("=")
        k = k.strip()
        v = v.strip().strip("'").strip('"')
        # Don't clobber a value the shell already exported.
        os.environ.setdefault(k, v)


_load_dotenv(PROJECT_ROOT / ".env")


def env(name: str, default: str | None = None) -> str | None:
    v = os.environ.get(name, default)
    return v if v else default


# --- Brand ---------------------------------------------------------------
# Used for placeholder slates and the watermark margin. Keep in sync with
# brand/visual-identity.md.
BRAND_NAVY = "0x0E1B2C"
BRAND_AMBER = "0xE8A33D"
BRAND_CREAM = "0xF4EFE6"
WATERMARK_MARGIN_PX = 48

# --- Video output --------------------------------------------------------
LANDSCAPE = (1920, 1080)          # YouTube long-form
PORTRAIT = (1080, 1920)            # Reels, Shorts
DEFAULT_FPS = 30

# --- Work dirs -----------------------------------------------------------
# WORK_DIR is configurable so launchd / dev can point at a non-default
# location without code changes.
WORK_DIR = Path(env("WORK_DIR") or (PROJECT_ROOT / "work"))

# --- Supabase ------------------------------------------------------------
SUPABASE_URL = env("SUPABASE_URL")
SUPABASE_PROJECT_REF = env("SUPABASE_PROJECT_REF")
SUPABASE_ANON_KEY = env("SUPABASE_ANON_KEY")
SUPABASE_SERVICE_KEY = env("SUPABASE_SERVICE_KEY")

# --- Worker daemon + control surface -------------------------------------
WORKER_HOST = env("WORKER_HOST") or "127.0.0.1"   # localhost-only by default
WORKER_PORT = int(env("WORKER_PORT") or "8787")
WORKER_SECRET = env("WORKER_SECRET")
# Daemon poll cadence and per-job retry budget.
POLL_INTERVAL_SEC = float(env("POLL_INTERVAL_SEC") or "5")
JOB_MAX_ATTEMPTS = int(env("JOB_MAX_ATTEMPTS") or "3")

# --- Stock asset providers ----------------------------------------------
PEXELS_API_KEY = env("PEXELS_API_KEY")
PIXABAY_API_KEY = env("PIXABAY_API_KEY")

# --- Push-to-device (Phase 7) -------------------------------------------
ICLOUD_DROP_DIR = env("ICLOUD_DROP_DIR")

# --- Deferred / monetization-gated --------------------------------------
# Wired only if you've uncommented the keys in .env.
ELEVENLABS_API_KEY = env("ELEVENLABS_API_KEY")
ELEVENLABS_VOICE_ID = env("ELEVENLABS_VOICE_ID")
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
