"""Job stage functions — the actual compute the worker daemon runs.

These are deliberately plain functions (no Supabase coupling) so they can be
called three ways:
  - by the daemon's job runner (worker/orchestrator/daemon.py),
  - directly from the CLI (`worker/cli.py fetch|assemble`),
  - from a test harness.

Each raises on failure and returns the produced path on success. The caller
owns status/state bookkeeping and event emission.
"""

from __future__ import annotations
import subprocess
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from worker import config, assemble  # noqa: E402
else:
    from . import config, assemble


class JobError(RuntimeError):
    """A job stage failed for a reason worth surfacing to the dashboard."""


# --- fetch ---------------------------------------------------------------

def run_fetch(slug: str, per_shot: int = 3) -> Path:
    """Download stock candidates for every shot into work/<slug>/assets/.

    Shells out to scripts/fetch_assets.py (which owns provider fan-out, alt
    queries, and slate fallback). Returns the assets dir.
    """
    work = config.work_path(slug)
    shot_list = work / "shot_list.json"
    if not shot_list.exists():
        raise JobError(f"missing {shot_list.name} — run the asset-scout agent first")

    assets_out = work / "assets"
    assets_out.mkdir(exist_ok=True)

    cmd = [
        sys.executable, str(config.FETCH_SCRIPT), str(shot_list),
        "--out", str(assets_out), "--per-shot", str(per_shot),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "")[-1500:]
        raise JobError(f"fetch_assets.py exited {proc.returncode}\n{tail}")
    return assets_out


# --- assemble ------------------------------------------------------------

def run_assemble(slug: str) -> Path:
    """Build work/<slug>/rough_cut.mp4 via ffmpeg. Returns the output path."""
    try:
        return assemble.assemble(slug)
    except FileNotFoundError as e:
        raise JobError(str(e)) from e
    except RuntimeError as e:
        # assemble raises RuntimeError for missing ffmpeg / failed ffmpeg calls.
        raise JobError(str(e)) from e
