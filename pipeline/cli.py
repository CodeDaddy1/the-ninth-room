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
        ingest.ingest(args.slug, use_api=getattr(args, "api", False))
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


def cmd_audit(args) -> int:
    from . import audit
    problems = audit.audit_splices(args.slug)
    audit.audit_speech_edges(args.slug)
    return 1 if any(p["severe"] for p in problems) else 0


def cmd_snap_cuts(args) -> int:
    from . import snap_cuts
    snap_cuts.snap(args.slug)
    return 0


def cmd_proxy(args) -> int:
    from . import proxy
    from .ingest import IngestError
    try:
        proxy.build(args.slug, only_beats=args.beat or None)
    except IngestError as e:
        print("error: %s" % e, file=sys.stderr)
        return 1
    return 0


def cmd_rebake(args) -> int:
    from . import produce
    from .ingest import IngestError
    try:
        produce.rebake(args.slug, beat_ids=args.beat or None,
                       card_ids=args.card or None)
    except IngestError as e:
        print("error: %s" % e, file=sys.stderr)
        return 1
    return 0


def cmd_qcframes(args) -> int:
    from . import qc_frames
    from .ingest import work_path, IngestError
    master = args.master
    if not master:
        deliver = work_path(args.slug) / "deliverables"
        movs = sorted(deliver.glob("*.mp4"), key=lambda p: p.stat().st_mtime)
        if not movs:
            print("error: no mp4 in %s" % deliver, file=sys.stderr)
            return 1
        master = str(movs[-1])
    try:
        flags = qc_frames.compare(args.slug, master)
    except IngestError as e:
        print("error: %s" % e, file=sys.stderr)
        return 1
    return 1 if flags else 0


def cmd_names(args) -> int:
    from . import names
    names.apply_to_slug(args.slug)
    return 0


def cmd_reencode(args) -> int:
    """Re-encode a slug's overlay/caption .movs with Apple's ProRes encoder.

    Heals files baked with ffmpeg's prores_ks, whose bitstream Resolve's
    realtime hardware decoder intermittently rejects (flickering "Media
    Offline" during playback; renders were always fine). Run with Resolve
    CLOSED — files are replaced in place under their existing names so the
    project relinks itself on reopen. Idempotent: healed files are recorded
    in work/<slug>/.vt_healed.json and skipped next time.
    """
    import json
    import os
    import subprocess
    from .ingest import work_path
    from .graphics import prores_encode_args

    enc = prores_encode_args()
    if "prores_videotoolbox" not in enc:
        print("VideoToolbox encoder unavailable — nothing to heal")
        return 1
    work = work_path(args.slug)
    marker_path = work / ".vt_healed.json"
    healed = json.loads(marker_path.read_text()) if marker_path.exists() else {}

    def frames(path) -> str:
        pr = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-count_packets", "-show_entries", "stream=nb_read_packets",
             "-of", "csv=p=0", str(path)], capture_output=True, text=True)
        return pr.stdout.strip()

    todo = []
    for d in (work / "graphics", work / "captions",
              work / "exports" / "overlays"):
        if d.is_dir():
            todo += sorted(p for p in d.glob("*.mov")
                           if not p.name.startswith("_tmp."))
    done = skipped = failed = 0
    for p in todo:
        rel = str(p.relative_to(work))
        st = p.stat()
        if healed.get(rel) == [st.st_size, int(st.st_mtime)]:
            skipped += 1
            continue
        n0 = frames(p)
        tmp = p.parent / ("_tmp.%s" % p.name)
        pr = subprocess.run(["ffmpeg", "-y", "-loglevel", "error",
                             "-i", str(p)] + enc + [str(tmp)],
                            capture_output=True, text=True)
        if pr.returncode != 0:
            if tmp.exists():
                tmp.unlink()
            print("FAILED %s: %s" % (rel, pr.stderr[-200:]))
            failed += 1
            continue
        n1 = frames(tmp)
        if not n0 or n0 != n1:  # never swap in a clip of a different length
            tmp.unlink()
            print("FRAME MISMATCH %s: %s -> %s (original kept)" % (rel, n0, n1))
            failed += 1
            continue
        os.replace(tmp, p)
        st = p.stat()
        healed[rel] = [st.st_size, int(st.st_mtime)]
        marker_path.write_text(json.dumps(healed))
        done += 1
        print("healed %s (%s frames)" % (rel, n1))

    # prebaked cards' export status keys are mtime/size-based — refresh them
    from . import editroom
    sc = work / "exports" / "overlays" / ".export_hashes.json"
    if sc.exists():
        exp = json.loads(sc.read_text())
        cards = {c["id"]: c for c, _ in editroom._all_overlays(args.slug)}
        orient = editroom._orientation(args.slug)
        for cid in list(exp):
            if cid in cards:
                exp[cid]["key"] = editroom._current_key(
                    args.slug, cards[cid], orient)
        editroom._write_json(sc, exp)
    print("re-encoded %d, already healed %d, failed %d, total %d"
          % (done, skipped, failed, len(todo)))
    return 1 if failed else 0


def cmd_editroom(args) -> int:
    from . import editroom
    editroom.serve(args.slug, port=args.port)
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
    p.add_argument("--api", action="store_true",
                   help="transcribe via OpenAI Whisper (better names; costs cents)")
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

    p = sub.add_parser("audit", help="flag words straddling splice points")
    p.add_argument("slug")
    p.set_defaults(fn=cmd_audit)

    p = sub.add_parser("snap-cuts", help="snap explicit cut edges to acoustic silence")
    p.add_argument("slug")
    p.set_defaults(fn=cmd_snap_cuts)

    p = sub.add_parser("proxy", help="render per-beat 480p proxies (cached)")
    p.add_argument("slug")
    p.add_argument("--beat", action="append", help="only these beat ids")
    p.set_defaults(fn=cmd_proxy)

    p = sub.add_parser("rebake", help="regen timeline map + re-bake only named captions/cards")
    p.add_argument("slug")
    p.add_argument("--beat", action="append", help="re-bake captions for these beat ids")
    p.add_argument("--card", action="append", help="re-render these card ids")
    p.set_defaults(fn=cmd_rebake)

    p = sub.add_parser("qcframes", help="diff the rendered master against the approved proxies")
    p.add_argument("slug")
    p.add_argument("--master", help="mp4 to check (default: newest in deliverables/)")
    p.set_defaults(fn=cmd_qcframes)

    p = sub.add_parser("names", help="re-apply brand/names.json corrections to a slug's transcripts")
    p.add_argument("slug")
    p.set_defaults(fn=cmd_names)

    p = sub.add_parser("reencode", help="re-encode overlay/caption movs with "
                       "Apple's ProRes encoder (fixes Resolve playback "
                       "Media Offline; run with Resolve closed)")
    p.add_argument("slug")
    p.set_defaults(fn=cmd_reencode)

    p = sub.add_parser("editroom", help="serve the shot-review UI on localhost")
    p.add_argument("slug")
    p.add_argument("--port", type=int, default=8765)
    p.set_defaults(fn=cmd_editroom)

    p = sub.add_parser("bridge", help="manage the in-app Resolve bridge")
    p.add_argument("action", choices=["install", "ensure", "stop", "status"])
    p.set_defaults(fn=cmd_bridge)

    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
