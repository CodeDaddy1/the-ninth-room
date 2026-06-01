"""Path conventions for agent outputs.

Layout under `work/` (gitignored, on the local Mac):

    work/
    ├── _planning/                       # weekly slate cadence, no per-video tie
    │   ├── topics-YYYY-MM-DD.json       # curiosity-scout
    │   ├── slate-YYYY-WW.json           # content-strategist
    │   ├── metrics-YYYY-WW.json         # staged by the worker for analyst input
    │   └── analyst-YYYY-WW.md           # performance-analyst
    │
    └── <slug>/                          # per-video
        ├── script.md                    # youtube-scriptwriter / instagram-copywriter
        ├── shot_list.json               # asset-scout
        ├── visuals.json                 # visual-director
        ├── voiceover.mp3                # Caleb records, drops in
        ├── selections.json              # which asset candidate per shot
        ├── music.json                   # picked music_tracks.id + duck level
        ├── assets/                      # written by scripts/fetch_assets.py
        ├── tmp/                         # scratch for ffmpeg passes
        ├── rough_cut.mp4
        └── tray/
            ├── youtube_long.json        # instagram-copywriter / youtube-scriptwriter
            ├── youtube_short.json       # output per platform target
            ├── instagram_reel.json
            ├── instagram_carousel.json
            └── instagram_story.json

`work/_planning/` filenames are date-anchored so reruns don't clobber history.
`work/<slug>/` lives one video, one slug.
"""

from __future__ import annotations
from datetime import date, datetime
from pathlib import Path

from .. import config


# --- root ----------------------------------------------------------------

def work_root() -> Path:
    """The on-disk root for all work dirs."""
    root = config.WORK_DIR
    root.mkdir(parents=True, exist_ok=True)
    return root


def planning_dir() -> Path:
    p = work_root() / "_planning"
    p.mkdir(parents=True, exist_ok=True)
    return p


def video_dir(slug: str) -> Path:
    """Per-video work dir, created on demand."""
    p = work_root() / slug
    p.mkdir(parents=True, exist_ok=True)
    return p


# --- planning filenames --------------------------------------------------

def topics_path(today: date | None = None) -> Path:
    d = today or date.today()
    return planning_dir() / f"topics-{d.isoformat()}.json"


def slate_path(week: str | None = None) -> Path:
    """`week` is ISO-year-week, e.g. '2026-W23'. Defaults to current week."""
    w = week or _iso_week(date.today())
    return planning_dir() / f"slate-{w}.json"


def metrics_path(week: str | None = None) -> Path:
    w = week or _iso_week(date.today())
    return planning_dir() / f"metrics-{w}.json"


def analyst_brief_path(week: str | None = None) -> Path:
    w = week or _iso_week(date.today())
    return planning_dir() / f"analyst-{w}.md"


# --- per-video filenames -------------------------------------------------

def script_path(slug: str) -> Path:
    return video_dir(slug) / "script.md"


def shot_list_path(slug: str) -> Path:
    return video_dir(slug) / "shot_list.json"


def visuals_path(slug: str) -> Path:
    return video_dir(slug) / "visuals.json"


def voiceover_path(slug: str) -> Path:
    return video_dir(slug) / "voiceover.mp3"


def selections_path(slug: str) -> Path:
    return video_dir(slug) / "selections.json"


def music_path(slug: str) -> Path:
    return video_dir(slug) / "music.json"


def rough_cut_path(slug: str) -> Path:
    return video_dir(slug) / "rough_cut.mp4"


def tray_path(slug: str, platform: str) -> Path:
    d = video_dir(slug) / "tray"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{platform}.json"


# --- next-action map -----------------------------------------------------
# Given a video.state, what slash command should the dashboard surface and
# which file does it expect on disk to advance? Used by the dashboard's
# "Next action" card (Phase 3) and the worker's watcher (Phase 4).

NEXT_ACTION: dict[str, dict[str, str]] = {
    "queued": {
        "kind": "agent",
        "slash": "/youtube-scriptwriter slug={slug} topic=\"{topic}\"",
        "expect_file": "script.md",
        "advances_to": "scripting",
    },
    "scripting": {
        "kind": "agent",
        "slash": "/asset-scout slug={slug}",
        "expect_file": "shot_list.json",
        "advances_to": "shots",
    },
    "shots": {
        "kind": "worker_job",
        "job_type": "fetch",
        "expect_file": "assets/",
        "advances_to": "fetching",
    },
    "fetching": {
        "kind": "manual",
        "instruction": "Worker is fetching stock candidates. No action.",
        "expect_file": "assets/",
        "advances_to": "awaiting_vo",
    },
    "awaiting_vo": {
        "kind": "manual",
        "instruction": "Record voiceover and save as voiceover.mp3 in the work dir.",
        "expect_file": "voiceover.mp3",
        "advances_to": "assembling",
    },
    "assembling": {
        "kind": "worker_job",
        "job_type": "assemble",
        "expect_file": "rough_cut.mp4",
        "advances_to": "ready",
    },
    "ready": {
        "kind": "agent",
        "slash": "/visual-director slug={slug}",
        "expect_file": "visuals.json",
        "advances_to": "tray",
    },
    "tray": {
        "kind": "manual",
        "instruction": "Ready tray populated. Approve → push to device.",
        "expect_file": "tray/",
        "advances_to": "pushed",
    },
}


# --- helpers -------------------------------------------------------------

def _iso_week(d: date) -> str:
    iso = d.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def parse_iso_week(week: str) -> tuple[date, date]:
    """Returns (monday, sunday) of the given ISO week."""
    year, w = week.split("-W")
    monday = datetime.fromisocalendar(int(year), int(w), 1).date()
    sunday = datetime.fromisocalendar(int(year), int(w), 7).date()
    return monday, sunday
