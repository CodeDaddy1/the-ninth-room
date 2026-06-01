"""Curated Curiosities pipeline — command-line entry point.

Usage:
    python program/cli.py init <slug>
    python program/cli.py fetch <slug>
    python program/cli.py voiceover <slug> [--provider elevenlabs|openai|manual]
    python program/cli.py assemble <slug>
    python program/cli.py run <slug>

The work dir for each video lives at program/work/<slug>/.
"""

from __future__ import annotations
import argparse
import json
import subprocess
import sys
from pathlib import Path

# Allow running as `python program/cli.py` or `python -m program.cli`
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from program import config, voiceover, assemble  # noqa: E402
else:
    from . import config, voiceover, assemble


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
    work = config.work_path(args.slug)
    shot_list = work / "shot_list.json"
    if not shot_list.exists():
        print(f"[fetch] missing {shot_list}", file=sys.stderr)
        sys.exit(2)
    assets_out = work / "assets"
    assets_out.mkdir(exist_ok=True)
    cmd = [
        sys.executable, str(config.FETCH_SCRIPT), str(shot_list),
        "--out", str(assets_out), "--per-shot", str(args.per_shot),
    ]
    print(f"[fetch] {' '.join(cmd)}")
    subprocess.run(cmd, check=True)


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

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
