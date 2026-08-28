#!/usr/bin/env python3
"""Backfill `kind` onto takes written before 2026-08-28.

Kind is derived at ingest from the take's file and stored on the take
(docs/decisions-beat-and-take-kind.md). Takes analysed before that carry no
`kind`, and while `schemas.take_kind` falls back to deriving one, the point
of the decision is that the fact is STORED. This writes it.

Derivation is the same single function ingest uses, so a backfilled take and
a freshly analysed one cannot disagree.

    /usr/bin/python3 scripts/backfill_take_kind.py [--write]

Without --write it reports and changes nothing.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pipeline.takes import kind_of_file  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent / "work"


def main(write: bool) -> int:
    total = changed = 0
    for path in sorted(ROOT.glob("*/analysis/takes.json")):
        data = json.loads(path.read_text())
        rows = data.get("takes", data) if isinstance(data, dict) else data
        hits = {}
        for take in rows:
            if not isinstance(take, dict) or "file" not in take:
                continue
            total += 1
            want = kind_of_file(take["file"])
            if take.get("kind") == want:
                continue
            take["kind"] = want
            changed += 1
            hits[want] = hits.get(want, 0) + 1
        if hits:
            print("%-56s %s" % (path.parent.parent.name,
                                ", ".join("%s=%d" % kv
                                          for kv in sorted(hits.items()))))
            if write:
                tmp = path.with_suffix(".tmp")
                tmp.write_text(json.dumps(data, indent=2))
                tmp.replace(path)
    print("\n%d takes seen, %d %s" %
          (total, changed, "written" if write else "would change"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main("--write" in sys.argv))
