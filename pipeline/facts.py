# -*- coding: utf-8 -*-
"""The numbers the Studio's desk headers state, and the machine's own health.

Every desk in the Studio opens with a line of FACTS rather than a sentence
explaining what the desk is for ("327 files · 758 GB · 4 sources", not
"Drop the shoot anywhere on this page"). That was artboard 23's call and
Caleb adopted it across every desk on 2026-08-26.

A fact the engine cannot source honestly is worse than no fact at all, so
the three things the desks wanted and could not have live here:

  * `health()`      — is the engine up, is Resolve running, how much disk
                      is left. There was no health route at all; Resolve's
                      liveness reached the UI only as a 500 from a failed
                      conform.
  * `sources()`     — which camera card each file came from. Nothing
                      recorded it; filenames were the only trace, and a
                      filename is an inference, not a fact.
  * `timeline()`    — the cut's version and duration. `timeline_map.json`
                      has carried a top-level `duration` all along and
                      `_state` never forwarded it; the version did not
                      exist anywhere.

Sources are a SIDECAR (`work/<slug>/footage_sources.json`), deliberately.
Ingest writes the catalog and the catalog is the analysis's own record —
threading a provenance field through it would mean a migration on every
project and a reason for ingest to fail. A sidecar can be absent, partial
or hand-edited and the worst case is files reading as "unsorted", which is
exactly what an un-labelled file IS.
"""
from __future__ import annotations

import json
import os
import shutil
import time
from pathlib import Path

from .ingest import work_path

# What a file with no recorded source is called on the Footage desk. Not
# "unknown": the file is perfectly known, its provenance is not, and the
# desk's job is to say so in a word an operator would use.
UNSORTED = "unsorted"

# A progress file older than this is a leftover from a run that died — the
# same 300s the project row uses (editroom.py), kept identical on purpose
# so two surfaces never disagree about whether an ingest is live.
PROGRESS_TTL_S = 300


# --------------------------------------------------------------------------
# health
# --------------------------------------------------------------------------
def health(project_root: "Path | None" = None) -> "dict":
    """Liveness, Resolve, and disk — the three things a desk cannot infer.

    Resolve is probed through `resolve_api.resolve_running()`, which has
    existed since the bridge was written and was never exposed over HTTP.
    The Studio's conform button therefore had no way to check before it
    ran, and a quit Resolve arrived as a raw 500 mid-conform.

    Every part degrades independently: a `pgrep` that fails must not take
    the disk reading down with it, because the caller is usually asking
    "can I still work?" and the answer is almost always yes.
    """
    root = Path(project_root) if project_root else Path(__file__).resolve().parent.parent
    resolve = None
    try:
        from . import resolve_api
        resolve = bool(resolve_api.resolve_running())
    except Exception:
        # pgrep missing, not macOS, bridge module unimportable — "we do not
        # know" is a distinct answer from "it is not running", and the UI
        # must not offer to launch Resolve on the strength of a failed probe
        resolve = None
    disk = None
    try:
        du = shutil.disk_usage(str(root))
        disk = {"path": str(root), "total": du.total,
                "free": du.free, "used": du.used}
    except OSError:
        disk = None
    return {"ok": True, "resolve": resolve, "disk": disk,
            "ts": int(time.time())}


# --------------------------------------------------------------------------
# sources — which card a file came from
# --------------------------------------------------------------------------
def _sources_path(slug: str) -> Path:
    return work_path(slug) / "footage_sources.json"


def read_sources(slug: str) -> "dict":
    """filename -> source label. Absent, unreadable or half-written all
    mean the same thing to a caller: nothing is labelled yet."""
    p = _sources_path(slug)
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text())
    except (ValueError, OSError):
        return {}
    files = data.get("files")
    return files if isinstance(files, dict) else {}


def record_source(slug: str, names, source: "str | None") -> None:
    """Tag one or more filenames with the source they arrived from.

    Called from the upload route (the browser sends the dropped folder's
    name) and from `_link_footage` (the linked folder IS the card). A blank
    or missing label is not written at all — an absent entry already means
    `unsorted`, and writing the word would make a guess look like a record.
    """
    label = (source or "").strip()
    if not label:
        return
    if isinstance(names, str):
        names = [names]
    names = [n for n in names if n]
    if not names:
        return
    p = _sources_path(slug)
    p.parent.mkdir(parents=True, exist_ok=True)
    data = {"files": read_sources(slug)}
    for n in names:
        data["files"][n] = label[:120]
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2))
    os.replace(tmp, p)


def forget_source(slug: str, names) -> None:
    """Drop labels for deleted files so the sidecar cannot outlive them and
    keep a phantom card on the desk."""
    if isinstance(names, str):
        names = [names]
    current = read_sources(slug)
    if not current:
        return
    changed = False
    for n in names:
        if n in current:
            del current[n]
            changed = True
    if not changed:
        return
    p = _sources_path(slug)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps({"files": current}, indent=2))
    os.replace(tmp, p)


def group_sources(items, labels: "dict", skipped=()) -> "list":
    """Roll the file list up into the SOURCES panel artboard 23 draws.

    One row per card: how many files, how many bytes, how many of them
    ingest set aside. Sorted by name with `unsorted` forced last — it is a
    residue bucket, not a card, and sorting it among the real ones implies
    it is one.
    """
    skipped = set(skipped or ())
    by: "dict" = {}
    for it in items:
        name = it.get("name")
        label = labels.get(name) or UNSORTED
        row = by.setdefault(label, {"name": label, "files": 0,
                                    "bytes": 0, "skipped": 0})
        row["files"] += 1
        row["bytes"] += int(it.get("size") or 0)
        if name in skipped:
            row["skipped"] += 1
    rows = sorted(by.values(), key=lambda r: (r["name"] == UNSORTED, r["name"]))
    return rows


# --------------------------------------------------------------------------
# live ingest progress, for the desk that is watching it happen
# --------------------------------------------------------------------------
def live_progress(slug: str) -> "dict | None":
    """The byte-weighted progress ingest has always written, forwarded.

    `ingest.write_progress` records `done/total/current/pct/eta_s` per file
    and has since the ETA work — but it only ever reached `/api/projects`,
    so the Footage desk, the one screen actually watching the copy, had to
    make do with `/api/jobs`'s hardcoded 2/60/75/80/100 ladder.

    Returns None for a run that finished or went stale, so a caller can
    treat "no progress" and "not running" as one case.
    """
    p = work_path(slug) / "ingest_progress.json"
    if not p.exists():
        return None
    try:
        pr = json.loads(p.read_text())
    except (ValueError, OSError):
        return None
    if pr.get("stage") == "done":
        return None
    if time.time() - (pr.get("ts") or 0) >= PROGRESS_TTL_S:
        return None
    return pr


# --------------------------------------------------------------------------
# the cut's own facts
# --------------------------------------------------------------------------
def _version_path(slug: str) -> Path:
    return work_path(slug) / "timeline_version.json"


def timeline_version(slug: str) -> int:
    """How many times this cut has been conformed into Resolve.

    Artboard 16 states "timeline v14" and nothing in the engine counted.
    A version that only ever advances on a SUCCESSFUL conform is the
    honest definition: it names what Resolve is actually holding, which is
    the only thing an operator can act on. A failed conform leaves the
    number where it was, because the timeline is where it was.
    """
    p = _version_path(slug)
    if not p.exists():
        return 0
    try:
        return int(json.loads(p.read_text()).get("version") or 0)
    except (ValueError, OSError, TypeError):
        return 0


def bump_timeline_version(slug: str) -> int:
    p = _version_path(slug)
    p.parent.mkdir(parents=True, exist_ok=True)
    n = timeline_version(slug) + 1
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps({"version": n, "ts": int(time.time())}, indent=2))
    os.replace(tmp, p)
    return n


def timeline_facts(slug: str, tl: "dict | None" = None,
                   beats: "list | None" = None) -> "dict":
    """`{version, clips, duration}` — the Export desk's whole top line.

    `duration` prefers timeline_map.json's own top-level value, which the
    assembler writes and `_state` has always read and never forwarded.
    Summing the clips is the fallback, and it is a fallback rather than the
    definition because a sum silently loses whatever sits between clips.
    """
    dur = None
    if tl:
        try:
            dur = float(tl.get("duration"))
        except (TypeError, ValueError):
            dur = None
    if not dur and beats:
        try:
            dur = sum(float(b.get("dur") or 0) for b in beats)
        except (TypeError, ValueError):
            dur = None
    return {"version": timeline_version(slug),
            "clips": len(beats or []),
            "duration": round(dur, 1) if dur else None}
