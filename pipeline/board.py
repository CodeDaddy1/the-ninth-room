# -*- coding: utf-8 -*-
"""The production board's I/O — append-only, validated at the door.

The board itself is an event log (see schemas.EVENT_CLASS /
fold_production); this module is the only code that touches the file.
Appends are validated per event — an event whose `by` doesn't match its
type's writer class is refused here, before it ever lands, so the
one-writer-per-class rule holds mechanically for every caller: the
engine's own code, the CLI verbs the lead invokes, and the reply route.
"""
from __future__ import annotations

import json
import os
import threading
import time

from . import schemas
from .ingest import IngestError, work_path

_LOCK = threading.Lock()


def path(slug: str):
    return work_path(slug) / "production.json"


def read(slug: str) -> "dict":
    p = path(slug)
    if not p.exists():
        return {"events": []}
    try:
        return json.loads(p.read_text())
    except ValueError:
        raise IngestError("production.json is corrupt — the board is "
                          "append-only; restore it from git or start over")


def append(slug: str, events: "list", expect_by: "str | None" = None) -> "dict":
    """Append events (each stamped with ts if missing). `expect_by`
    asserts every event claims that writer — the caller declares who it
    is and cannot smuggle another class's event through."""
    now = int(time.time())
    for e in events:
        e.setdefault("ts", now)
        if expect_by is not None and e.get("by") != expect_by:
            raise IngestError("this writer appends %r events only, got %r"
                              % (expect_by, e.get("by")))
    errs = schemas.validate_production({"events": events})
    if errs:
        raise IngestError("board append refused: %s" % errs[0])
    with _LOCK:
        doc = read(slug)
        doc["events"].extend(events)
        p = path(slug)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(doc, indent=1, ensure_ascii=False))
        os.replace(tmp, p)
        return doc


def fold(slug: str) -> "dict":
    return schemas.fold_production(read(slug).get("events", []))


def reap(slug: str, log=print) -> "list[str]":
    """Re-open claims whose teammate died (engine-class events)."""
    stale = schemas.stale_claims(fold(slug), now=time.time())
    if stale:
        append(slug, [{"type": "reclaimed", "by": "engine", "task_id": t}
                      for t in stale], expect_by="engine")
        log("[board] reaped %d stale claim(s): %s"
            % (len(stale), ", ".join(stale)))
    return stale


# craft -> (checker fn over the artifact json, artifact loader hint)
def run_checker(slug: str, task_id: str, craft: str, log=print) -> "list[str]":
    """The engine's own arithmetic, invoked as a verb by the lead: run
    the craft's bar against the episode's live artifact, append the
    checker_result event, then evaluate the stall brakes on the fold and
    append a brake event if one trips. Returns the checker notes."""
    work = work_path(slug)
    notes: "list[str]" = []
    if craft == "coverage":
        plan = json.loads((work / "edit_plan.json").read_text())
        # takes carry `kind`, and the VO exemption is read from it
        tp = work / "analysis" / "takes.json"
        takes = json.loads(tp.read_text()) if tp.exists() else None
        # the catalog carries the tags the cover caps lift on
        bp = work / "analysis" / "broll.json"
        broll = json.loads(bp.read_text()) if bp.exists() else None
        notes = schemas.coverage_notes(plan, takes, broll)
    # future crafts land here beside their *_notes bars (team plan P3)
    append(slug, [{"type": "checker_result", "by": "engine",
                   "task_id": task_id, "name": craft, "notes": notes}],
           expect_by="engine")
    card = fold(slug).get("tasks", {}).get(task_id)
    if card:
        reason = schemas.stalled(card)
        if reason:
            append(slug, [{"type": "brake", "by": "engine",
                           "task_id": task_id, "reason": reason}],
                   expect_by="engine")
            log("[board] brake: %s — %s" % (task_id, reason))
    return notes


def scorecard_path(slug: str, task_id: str):
    """Scorecards live OUTSIDE the episode tree (rev 3): they are the
    teammate's own, never the board's, and the lead has no path to
    guess inside the project it reads."""
    d = work_path("_scorecards") / slug
    d.mkdir(parents=True, exist_ok=True)
    return d / ("%s.json" % task_id)
