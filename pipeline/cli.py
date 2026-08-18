"""Command-line entry points for the pipeline.

Run with the system Python from the repo root:

    /usr/bin/python3 -m pipeline.cli <command> [args]

Commands are added phase by phase; `/produce` (Phase 7) orchestrates them.
"""
from __future__ import annotations

import argparse
import sys


def cmd_ingest(args) -> int:
    from . import ingest
    try:
        ingest.ingest(args.slug)
    except ingest.IngestError as e:
        print("error: %s" % e, file=sys.stderr)
        return 1
    return 0


def cmd_takes(args) -> int:
    from . import takes
    from .ingest import IngestError
    try:
        takes.analyze(args.slug)
    except IngestError as e:
        print("error: %s" % e, file=sys.stderr)
        return 1
    return 0


def cmd_broll(args) -> int:
    from . import broll
    from .ingest import IngestError
    try:
        broll.catalog_broll(args.slug)
    except IngestError as e:
        print("error: %s" % e, file=sys.stderr)
        return 1
    return 0


def cmd_build_timeline(args) -> int:
    from . import produce
    from .ingest import IngestError
    try:
        produce.build_timeline(args.slug)
    except IngestError as e:
        print("error: %s" % e, file=sys.stderr)
        return 1
    return 0


def cmd_produce(args) -> int:
    from . import produce
    from .ingest import IngestError
    from .resolve_api import BridgeError
    try:
        produce.produce(args.slug)
    except (IngestError, BridgeError) as e:
        print("error: %s" % e, file=sys.stderr)
        return 1
    return 0


def cmd_bridge(args) -> int:
    from . import resolve_api as ra
    if args.action == "install":
        dest = ra.install_bridge()
        print("installed: %s (restart Resolve to pick it up)" % dest)
    elif args.action == "ensure":
        ra.ensure_bridge()
        print("bridge is up")
    elif args.action == "stop":
        ra.stop_bridge()
        print("stop requested")
    elif args.action == "status":
        print("alive" if ra.alive() else "down")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="pipeline")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("ingest", help="probe + transcribe work/<slug>/footage/")
    p.add_argument("slug")
    p.set_defaults(fn=cmd_ingest)

    p = sub.add_parser("takes", help="segment speech into takes, group retakes")
    p.add_argument("slug")
    p.set_defaults(fn=cmd_takes)

    p = sub.add_parser("broll", help="catalog b-roll + contact sheets")
    p.add_argument("slug")
    p.set_defaults(fn=cmd_broll)

    p = sub.add_parser("build-timeline", help="edit_plan -> captions/cards -> timeline.fcpxml")
    p.add_argument("slug")
    p.set_defaults(fn=cmd_build_timeline)

    p = sub.add_parser("produce", help="full auto: timeline -> Resolve -> rendered mp4")
    p.add_argument("slug")
    p.set_defaults(fn=cmd_produce)

    p = sub.add_parser("bridge", help="manage the in-app Resolve bridge")
    p.add_argument("action", choices=["install", "ensure", "stop", "status"])
    p.set_defaults(fn=cmd_bridge)

    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
