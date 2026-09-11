"""Machine-specific locations, in one place.

Precedence: environment variable, then the repo-root .env, then a default
derived from PATH or the home directory. Nothing under pipeline/ may spell a
home directory; tests/test_paths.py enforces that. A wrong value fails at
first use with the path in the error, never silently.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _dotenv(key: str) -> Optional[str]:
    env = PROJECT_ROOT / ".env"
    if not env.exists():
        return None
    for line in env.read_text().splitlines():
        line = line.strip()
        if line.startswith(key + "="):
            return line.split("=", 1)[1].strip().strip('"').strip("'") or None
    return None


def setting(key: str) -> Optional[str]:
    """The value of `key` from the environment, else from .env, else None."""
    return os.environ.get(key) or _dotenv(key)


def claude_bin() -> str:
    """The Claude Code binary the dispatcher launches."""
    return (setting("NINTH_ROOM_CLAUDE_BIN")
            or shutil.which("claude")
            or str(Path.home() / ".local" / "bin" / "claude"))


def work_dir() -> Path:
    """Where per-episode work directories live."""
    raw = setting("WORK_DIR")
    return Path(raw).expanduser() if raw else PROJECT_ROOT / "work"
