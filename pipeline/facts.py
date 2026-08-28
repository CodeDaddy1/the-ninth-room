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
import threading
import time
from pathlib import Path

from . import ingest as _ingest


def work_path(slug: str) -> Path:
    """Resolved through the ingest MODULE, not bound by value.

    `from .ingest import work_path` binds the function object at import
    time, so a test that patches `ingest.work_path` — which is how every
    sandboxed test in this repo isolates itself — does not reach this
    module. `_link_footage` calls `record_source`, so
    tests/test_footage_linking.py wrote a real `work/ep/` into the live
    shelf, where it showed up as a phantom project on the Studio's board
    (found 2026-08-26).

    Re-exported under the same name so this module's own tests can patch
    `facts.work_path` directly as well.
    """
    return _ingest.work_path(slug)

# Every other multi-writer file in this engine has a lock (review.json,
# graphics_plan.json, the conform ledger, trash.json, edit_plan.json) and
# these two did not. `ThreadingHTTPServer` handles uploads in parallel and
# a browser folder-drop fires several at once, so a read-modify-write here
# is a real race, not a theoretical one — measured 2026-08-26: 12
# concurrent `record_source` calls kept 2 labels and raised 9 times.
_SOURCES_LOCK = threading.Lock()
_VERSION_LOCK = threading.Lock()
_VERDICT_LOCK = threading.Lock()
_SESSION_LOCK = threading.Lock()


def _write_atomic(path: Path, data) -> None:
    """tmp + replace, with a tmp name NOBODY ELSE CAN BE USING.

    A fixed `.tmp` sibling is worse than no atomicity: thread A's
    `os.replace` moves the file out from under thread B, and B's replace
    raises FileNotFoundError. That surfaced as a 500 on an upload that had
    already succeeded — the file on disk, the upload stamp never set, and
    the Studio told it failed.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".%d.%d.tmp" % (os.getpid(), threading.get_ident()))
    try:
        tmp.write_text(json.dumps(data, indent=2))
        os.replace(tmp, path)
    except BaseException:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise

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
    if not isinstance(data, dict):
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
    with _SOURCES_LOCK:
        data = {"files": read_sources(slug)}
        for n in names:
            # basename only: the label is user-supplied and the key is a
            # filename, and neither has any business carrying a path
            data["files"][os.path.basename(n)] = label[:120]
        _write_atomic(_sources_path(slug), data)


def forget_source(slug: str, names) -> None:
    """Drop labels for deleted files so the sidecar cannot outlive them and
    keep a phantom card on the desk."""
    if isinstance(names, str):
        names = [names]
    with _SOURCES_LOCK:
        current = read_sources(slug)
        if not current:
            return
        changed = False
        for n in names:
            key = os.path.basename(n)
            if key in current:
                del current[key]
                changed = True
        if not changed:
            return
        _write_atomic(_sources_path(slug), {"files": current})


def clear_sources(slug: str) -> None:
    """Forget every label — the shelf is empty, so nothing is attributable."""
    with _SOURCES_LOCK:
        p = _sources_path(slug)
        try:
            p.unlink()
        except OSError:
            pass


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
    # same shape guard as timeline_version — this one reaches /api/footage
    if not isinstance(pr, dict):
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
        data = json.loads(p.read_text())
        # a JSON array, a bare number, a string — every shape a hand-edited
        # or half-written file can take. `.get` on any of them is an
        # AttributeError, and this is read by `_state`, so an uncaught one
        # takes the whole Shots desk down with a 500.
        if not isinstance(data, dict):
            return 0
        return int(data.get("version") or 0)
    except (ValueError, OSError, TypeError):
        return 0


def bump_timeline_version(slug: str) -> int:
    with _VERSION_LOCK:
        n = timeline_version(slug) + 1
        _write_atomic(_version_path(slug),
                      {"version": n, "ts": int(time.time())})
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
    # the same shape guard `timeline_version`, `live_progress` and
    # `read_sources` carry — a non-dict `tl` is an AttributeError, and
    # this is read by `_state`
    if isinstance(tl, dict):
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


# --- triage verdicts ------------------------------------------------------
#
# What Caleb thought of each clip, in a SIDECAR — never in the catalog.
#
# Ingest rebuilds `catalog.json` from scratch on every run, so anything
# hand-authored inside it is destroyed by the next analysis. That is why
# sources, b-roll tags, promotions and take verdicts all live beside it,
# and footage verdicts are no different: a rating survives a re-ingest
# because ingest never writes this file.
#
# What breaks if this is wrong: a triage pass over 148 clips is silently
# undone by the analysis it was meant to shape.

STAR_MAX = 5
REJECTED = "rejected"


def _verdicts_path(slug: str) -> Path:
    return work_path(slug) / "footage_verdicts.json"


def read_verdicts(slug: str) -> "dict":
    """filename -> {"stars": int, "rejected": bool}. Absent or unreadable
    both mean the same thing to a caller: nothing has been triaged."""
    p = _verdicts_path(slug)
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text())
    except (ValueError, OSError):
        return {}
    if not isinstance(data, dict):
        return {}
    files = data.get("files")
    return files if isinstance(files, dict) else {}


def read_rejected(slug: str) -> "set":
    """Just the names ingest must skip."""
    return {n for n, v in read_verdicts(slug).items()
            if isinstance(v, dict) and v.get("rejected")}


def set_verdict(slug: str, name: str, stars=None, rejected=None) -> "dict":
    """Rate or reject one clip. Returns the clip's whole verdict.

    Locked and atomic for the same measured reason `record_source` is: a
    keyboard triage pass fires these faster than a browser folder-drop
    fires uploads, and a read-modify-write without a lock loses most of
    them. `stars=0` clears the rating; passing neither argument is a
    no-op that still returns the current state.
    """
    name = os.path.basename(name or "")
    if not name:
        raise ValueError("no clip named")
    with _VERDICT_LOCK:
        files = read_verdicts(slug)
        cur = files.get(name)
        cur = dict(cur) if isinstance(cur, dict) else {}
        if stars is not None:
            try:
                n = int(stars)
            except (TypeError, ValueError):
                n = 0
            cur["stars"] = max(0, min(STAR_MAX, n))
            # Rating a clip un-rejects it: they are one judgment, and a
            # 4-star reject is a state nothing downstream could act on.
            if cur["stars"]:
                cur["rejected"] = False
        if rejected is not None:
            cur["rejected"] = bool(rejected)
            if cur["rejected"]:
                cur["stars"] = 0
        if not cur.get("stars") and not cur.get("rejected"):
            files.pop(name, None)   # back to untriaged; do not store a blank
        else:
            files[name] = cur
        _write_atomic(_verdicts_path(slug), {"files": files})
        # ONE shape, always. Returning {} for a cleared clip and a dict for
        # a set one makes every caller re-derive the default, and the desk
        # would have to guess whether a missing key means 0 or unknown.
        return {"stars": int(cur.get("stars") or 0),
                "rejected": bool(cur.get("rejected"))}


def forget_verdicts(slug: str, names) -> None:
    """Drop verdicts for files that are gone.

    Same hazard `forget_source` closes: `_uniquify` only guards names
    CURRENTLY present, so re-dropping a card gives the same filename back
    — and it would inherit the rejection of a clip it never was.
    """
    if isinstance(names, str):
        names = [names]
    names = [os.path.basename(n) for n in (names or []) if n]
    if not names:
        return
    with _VERDICT_LOCK:
        files = read_verdicts(slug)
        if not any(n in files for n in names):
            return
        for n in names:
            files.pop(n, None)
        _write_atomic(_verdicts_path(slug), {"files": files})


def clear_verdicts(slug: str) -> None:
    """The shelf is empty, so there is nothing left to have an opinion about."""
    with _VERDICT_LOCK:
        try:
            _verdicts_path(slug).unlink()
        except OSError:
            pass


# --- session labels -------------------------------------------------------
#
# What Caleb called each stretch of the visit.
#
# Stored PER CLIP, like the card labels above, and for a sharper reason: a
# session is a cluster of capture times, and a cluster is not a stable
# thing to key a name to. Drop one more clip into the middle of a shoot
# and every boundary can move, so a name keyed to "session 3" would drift
# onto footage it was never about. Keyed to the clips, the name stays
# where it was put, and two stretches given the SAME name merge — which
# is the whole of the merge feature (2026-08-27).


def _sessions_path(slug: str) -> Path:
    return work_path(slug) / "footage_sessions.json"


def read_session_labels(slug: str) -> "dict":
    """filename -> session label. Absent or unreadable both mean unnamed."""
    p = _sessions_path(slug)
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text())
    except (ValueError, OSError):
        return {}
    if not isinstance(data, dict):
        return {}
    files = data.get("files")
    return files if isinstance(files, dict) else {}


def name_session(slug: str, names, label: "str | None") -> "dict":
    """Name a stretch of the visit — every clip in it at once.

    An empty label CLEARS, rather than writing a blank: an absent entry
    already means "still a proposal", and storing the empty string would
    make an unnamed session look deliberately named to every reader.
    """
    if isinstance(names, str):
        names = [names]
    names = [os.path.basename(n) for n in (names or []) if n]
    if not names:
        raise ValueError("no clips given")
    text = (label or "").strip()[:120]
    with _SESSION_LOCK:
        files = read_session_labels(slug)
        for n in names:
            if text:
                files[n] = text
            else:
                files.pop(n, None)
        _write_atomic(_sessions_path(slug), {"files": files})
        return files


def forget_session_labels(slug: str, names) -> None:
    """Drop labels for files that are gone — see `forget_verdicts`."""
    if isinstance(names, str):
        names = [names]
    names = [os.path.basename(n) for n in (names or []) if n]
    if not names:
        return
    with _SESSION_LOCK:
        files = read_session_labels(slug)
        if not any(n in files for n in names):
            return
        for n in names:
            files.pop(n, None)
        _write_atomic(_sessions_path(slug), {"files": files})


def clear_session_labels(slug: str) -> None:
    with _SESSION_LOCK:
        try:
            _sessions_path(slug).unlink()
        except OSError:
            pass
