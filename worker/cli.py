"""Curated Curiosities pipeline — command-line entry point.

Usage:
    python worker/cli.py init <slug>
    python worker/cli.py fetch <slug>
    python worker/cli.py voiceover <slug> [--provider elevenlabs|openai|manual]
    python worker/cli.py assemble <slug>
    python worker/cli.py run <slug>
    python worker/cli.py validate <slug>          # validate per-video agent outputs
    python worker/cli.py validate --planning      # validate planning outputs
    python worker/cli.py ping                     # Supabase reachability check
    python worker/cli.py analyst-weekly           # surface the weekly analyst command
    python worker/cli.py daemon [--once] [--interval N] [--no-http]

The work dir for each video lives at work/<slug>/.
"""

from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

# Allow running as `python worker/cli.py` or `python -m worker.cli`
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from worker import config, voiceover, assemble, db, jobs  # noqa: E402
    from worker.orchestrator import schemas, work_dir, daemon  # noqa: E402
else:
    from . import config, voiceover, assemble, db, jobs
    from .orchestrator import schemas, work_dir, daemon


# --- init ----------------------------------------------------------------

INIT_SCRIPT_TEMPLATE = """# Script — <slug>

Drop your finished script here (output of the youtube-scriptwriter or
instagram-copywriter agent). Spoken lines, [VISUAL] cues, timing markers.
"""

INIT_VOICEOVER_TEMPLATE = """\
(Optional) Put the clean narration text here, one line per beat.

If this file doesn't exist, the voiceover stage will auto-derive narration
from the script_line fields in shot_list.json.
"""

INIT_SHOT_LIST_HINT = {
    "_comment": "Replace this with the output of the asset-scout agent.",
    "video_title": "<replace>",
    "platform": "youtube_short",
    "default_orientation": "portrait",
    "shots": [],
}


def cmd_init(args) -> None:
    work = config.work_path(args.slug)
    print(f"[init] {work}")
    files = {
        "script.md": INIT_SCRIPT_TEMPLATE.replace("<slug>", args.slug),
        "voiceover.txt": INIT_VOICEOVER_TEMPLATE,
        "shot_list.json": json.dumps(INIT_SHOT_LIST_HINT, indent=2) + "\n",
    }
    for name, body in files.items():
        p = work / name
        if p.exists():
            print(f"  · {name} exists — leaving alone")
            continue
        p.write_text(body)
        print(f"  + {name}")
    print("\nNext steps:")
    print("  1. Replace script.md and shot_list.json with real agent output")
    print("  2. (Optional) drop a watermark.png into the work dir")
    print(f"  3. Run: python program/cli.py run {args.slug}")


# --- fetch ---------------------------------------------------------------

def cmd_fetch(args) -> None:
    try:
        out = jobs.run_fetch(args.slug, per_shot=args.per_shot)
    except jobs.JobError as e:
        print(f"[fetch] {e}", file=sys.stderr)
        sys.exit(2)
    print(f"[fetch] ✓ {out}")


# --- voiceover -----------------------------------------------------------

def cmd_voiceover(args) -> None:
    voiceover.generate(args.slug, provider=args.provider)


# --- assemble ------------------------------------------------------------

def cmd_assemble(args) -> None:
    assemble.assemble(args.slug)


# --- run (all stages) ----------------------------------------------------

def cmd_run(args) -> None:
    cmd_fetch(args)
    cmd_voiceover(args)
    cmd_assemble(args)
    print(f"\n[run] done. Output: {config.work_path(args.slug) / 'rough_cut.mp4'}")


# --- validate ------------------------------------------------------------

def cmd_validate(args) -> None:
    """Validate every agent-output file present in a work dir.

    For a per-video slug:  scans work/<slug>/ for script.md, shot_list.json,
                            visuals.json, and tray/*.json.
    For a planning slug:    pass --planning to scan work/_planning/.
    """
    paths_to_check: list[Path] = []
    if args.planning:
        for p in work_dir.planning_dir().iterdir():
            if p.is_file():
                paths_to_check.append(p)
    else:
        vd = work_dir.video_dir(args.slug)
        for name in ("shot_list.json", "visuals.json"):
            f = vd / name
            if f.exists():
                paths_to_check.append(f)
        tray = vd / "tray"
        if tray.exists():
            paths_to_check.extend(p for p in tray.iterdir() if p.suffix == ".json")

    if not paths_to_check:
        print(f"[validate] no agent-output files found for '{args.slug}'.")
        return

    any_failed = False
    for path in paths_to_check:
        errs = schemas.load_and_validate(path)
        if errs:
            any_failed = True
            print(f"  ✗ {path.relative_to(config.PROJECT_ROOT)}")
            for e in errs:
                print(f"      - {e}")
        else:
            print(f"  ✓ {path.relative_to(config.PROJECT_ROOT)}")

    if any_failed:
        sys.exit(1)


# --- ping ---------------------------------------------------------------

def cmd_ping(args) -> None:
    """Verify Supabase reachability."""
    ok = db.ping()
    print(f"supabase {'OK' if ok else 'UNREACHABLE'}: {config.SUPABASE_URL}")
    sys.exit(0 if ok else 1)


# --- daemon (placeholder, Phase 4) -------------------------------------

def cmd_daemon(args) -> None:
    """Run the worker loop: poll jobs, watch work dirs, advance state.

    --once       run a single tick and exit (testing / cron-style use)
    --interval   override the poll cadence in seconds
    --no-http    don't bind the localhost control surface
    """
    daemon.run(interval=args.interval, http=not args.no_http, once=args.once)


# --- analyst-weekly (headless brief) -----------------------------------

def cmd_analyst_weekly(args) -> None:
    """Stage metrics and shell out to `claude -p` to run the analyst subagent.

    Wired by launchd Monday 09:00 (see infra/launchd/curated.analyst.plist).
    For Phase 2 this command stages the metrics file and prints the slash
    command to run; Phase 4 will execute it headlessly and parse the output.
    """
    week = args.week or _current_iso_week()
    metrics_path = work_dir.metrics_path(week)
    brief_path = work_dir.analyst_brief_path(week)

    # Stage an empty metrics file if none exists so the analyst can run
    # cold-start without erroring.
    if not metrics_path.exists():
        monday, sunday = work_dir.parse_iso_week(week)
        metrics_path.write_text(json.dumps({
            "week": week,
            "since": monday.isoformat(),
            "until": sunday.isoformat(),
            "rows": [],
        }, indent=2) + "\n")
        print(f"[analyst] staged empty metrics: {metrics_path}")
    else:
        print(f"[analyst] using existing metrics: {metrics_path}")

    slash = f'/performance-analyst week={week}'
    print(f"\nRun this in Claude Code from {config.PROJECT_ROOT}:")
    print(f"  {slash}")
    print(f"\nExpected output: {brief_path}")
    print("\nOnce written, validate with:")
    print(f"  python worker/cli.py validate --planning {week}")


def _current_iso_week() -> str:
    from datetime import date
    iso = date.today().isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


# --- main ----------------------------------------------------------------

def main() -> None:
    p = argparse.ArgumentParser(prog="ccp", description="Curated Curiosities pipeline")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("init", help="scaffold a new video work dir")
    s.add_argument("slug")
    s.set_defaults(func=cmd_init)

    s = sub.add_parser("fetch", help="download stock candidates per shot")
    s.add_argument("slug")
    s.add_argument("--per-shot", type=int, default=3)
    s.set_defaults(func=cmd_fetch)

    s = sub.add_parser("voiceover", help="generate voiceover.mp3 via TTS")
    s.add_argument("slug")
    s.add_argument("--provider", choices=["auto", "elevenlabs", "openai", "manual"], default="auto")
    s.set_defaults(func=cmd_voiceover)

    s = sub.add_parser("assemble", help="build rough_cut.mp4 via ffmpeg")
    s.add_argument("slug")
    s.set_defaults(func=cmd_assemble)

    s = sub.add_parser("run", help="fetch + voiceover + assemble")
    s.add_argument("slug")
    s.add_argument("--per-shot", type=int, default=3)
    s.add_argument("--provider", choices=["auto", "elevenlabs", "openai", "manual"], default="auto")
    s.set_defaults(func=cmd_run)

    s = sub.add_parser("validate", help="validate agent-output files in a work dir")
    s.add_argument("slug", nargs="?", default="")
    s.add_argument("--planning", action="store_true", help="scan work/_planning/ instead of a video work dir")
    s.set_defaults(func=cmd_validate)

    s = sub.add_parser("ping", help="check Supabase reachability")
    s.set_defaults(func=cmd_ping)

    s = sub.add_parser("daemon", help="run the worker loop (poll jobs + watch work dirs)")
    s.add_argument("--once", action="store_true", help="run a single tick and exit")
    s.add_argument("--interval", type=float, default=None, help="poll cadence in seconds")
    s.add_argument("--no-http", action="store_true", help="don't bind the localhost control surface")
    s.set_defaults(func=cmd_daemon)

    s = sub.add_parser("analyst-weekly", help="stage metrics and surface the analyst slash command")
    s.add_argument("--week", help="ISO week 'YYYY-Www'; defaults to current")
    s.set_defaults(func=cmd_analyst_weekly)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
