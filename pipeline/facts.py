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
import math
import os
import shutil
import threading
import time
from pathlib import Path

from . import ingest as _ingest
from .ingest import IngestError


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
_TRIM_LOCK = threading.Lock()


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


# --- footage trims --------------------------------------------------------
#
# The usable RANGE inside one clip: {"in": seconds, "out": seconds}.
#
# Caleb, 2026-08-28: "edit the clip by manually cutting with a scrubber
# during the footage ranking process." Triage had two verbs, stars and
# reject, so a clip with a bad walk-up or a fumbled tail was thrown away
# whole — the good forty seconds in the middle went with the bad four.
#
# The times are FILE-ABSOLUTE seconds, the same clock a take's `s`/`e` and
# a cover's `src_s` are already in. Nothing downstream converts, and a
# trim can be compared with a take boundary directly. An absent entry
# means the whole clip is usable, which is exactly what an untrimmed clip
# IS — so `trim_of` gives the no-trim path the same arithmetic rather than
# a second branch every caller has to remember.
#
# A SIDECAR for the same reason every other one here is: ingest rebuilds
# `catalog.json` from scratch, so a trim written into it is destroyed by
# the next analysis — and a trim is the most expensive judgment on the
# desk to re-make, because it is per-clip and by hand.
#
# What breaks if this is wrong: a take is silently DROPPED or renumbered.
# Take ids are positional — `"T%02d" % (len(takes) + 1)`, takes.py:340,
# assigned in catalog order — and `edit_plan.json` references them BY
# NAME, so dropping one take re-points every later beat at different
# footage. That is the same failure broll.py:218-245 documents for b-roll
# ids, where it had already happened. A take outside the window is
# MARKED, never removed; one straddling the edge is CLAMPED in place,
# keeping its id and its position.

# Under half a second of usable range is a mis-drag, not an edit. The
# Review desk's beat trim has refused this floor since it shipped (the
# Studio's `src/lib/trim-sheet.ts` MIN_CLIP_S = 0.5, "under half a second
# is a flash frame"), and two trim surfaces disagreeing about the
# smallest legal range is how one desk offers a drag the other rejects.
MIN_TRIM_S = 0.5


def _trims_path(slug: str) -> Path:
    return work_path(slug) / "footage_trims.json"


def read_trims(slug: str) -> "dict":
    """filename -> {"in": float, "out": float}. Absent or unreadable both
    mean the same thing to a caller: nothing has been trimmed."""
    p = _trims_path(slug)
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


def set_trim(slug: str, name: str, in_s=None, out_s=None) -> "dict":
    """Mark the usable range inside one clip. `in_s=None` or `out_s=None`
    CLEARS it.

    Returns ONE shape, always: `{"name": basename, "trim": {...} | None}`.
    `trim` is the nullable half because "no trim" is a real answer here and
    a zeroed window is not — `{"in": 0, "out": 0}` would read as a clip
    with nothing usable in it, which is the one thing a cleared trim does
    not mean. The route forwards this dict verbatim, so the wire shape and
    the Python shape cannot drift.

    Locked and atomic for the measured reason `record_source` is: a
    scrubbing pass fires these as fast as the desk can drag, and a
    read-modify-write without a lock loses most of them (12 concurrent
    `record_source` calls once kept 2 of 12).

    A refusal is an `IngestError` with a stable `code`, so the desk gets a
    400 it can explain rather than a 500. `set_verdict` raises a bare
    `ValueError` here and becomes a 500 with `ValueError:` in the message —
    a wart, not a pattern to copy.
    """
    name = os.path.basename(name or "")
    if not name:
        raise IngestError(
            "no clip named — a trim belongs to a file, send its name",
            code="no_clip")
    # A clear is not a write of a blank. An absent entry already means the
    # whole clip is usable, and storing 0/0 would make a cleared trim read
    # as an empty clip to every reader — the same rule verdicts follow when
    # both stars and rejection go away.
    if in_s is None or out_s is None:
        with _TRIM_LOCK:
            files = read_trims(slug)
            if name in files:
                files.pop(name, None)
                _write_atomic(_trims_path(slug), {"files": files})
        return {"name": name, "trim": None}
    try:
        start, end = float(in_s), float(out_s)
        # `math.isfinite` is not a nicety: NaN and Infinity both survive
        # `float()` AND `json.loads`, and NaN compares false against every
        # bound — so it would pass the floor check below and then poison
        # every clamp that reads the sidecar.
        numeric = math.isfinite(start) and math.isfinite(end)
    except (TypeError, ValueError):
        numeric = False
    if not numeric:
        raise IngestError(
            "a trim is two numbers of seconds, got in=%r out=%r — send the "
            "scrubber's positions" % (in_s, out_s), code="bad_trim")
    # Milliseconds, like `_clamp_cover` and every take boundary. A trim is
    # dragged with a mouse; anything past a millisecond is noise that makes
    # the sidecar unreadable and two equal drags compare unequal.
    start = round(max(0.0, start), 3)
    end = round(end, 3)
    # ROUND THE SPAN, NOT JUST THE BOUNDS (2026-08-28). The desk enforces
    # the same floor before it offers the button, and it measures the
    # rounded span — so comparing the raw float here split the two on
    # float representation alone: 721 of 20,001 millisecond in-points
    # over one real clip enabled a control the engine then refused with a
    # 400. A limit the screen and the engine disagree about is a limit
    # that reads as a bug.
    if round(end - start, 3) < MIN_TRIM_S:
        raise IngestError(
            "that leaves %.2fs of clip — under %.1fs is a mis-drag, not an "
            "edit. Drag wider, or clear the trim to keep the whole clip."
            % (max(0.0, end - start), MIN_TRIM_S), code="trim_too_short")
    with _TRIM_LOCK:
        files = read_trims(slug)
        files[name] = {"in": start, "out": end}
        _write_atomic(_trims_path(slug), {"files": files})
    return {"name": name, "trim": {"in": start, "out": end}}


def forget_trims(slug: str, names) -> None:
    """Drop trims for files that are gone.

    Same hazard `forget_verdicts` closes, and sharper: `_uniquify` only
    guards names CURRENTLY present, so deleting a clip and re-dropping the
    card gives the same filename back — and the new file would inherit a
    window dragged against footage it never was. A stale trim is worse
    than a stale rating: a rating changes what gets analyzed, a window
    changes which seconds of a clip the cut is allowed to use.
    """
    if isinstance(names, str):
        names = [names]
    names = [os.path.basename(n) for n in (names or []) if n]
    if not names:
        return
    with _TRIM_LOCK:
        files = read_trims(slug)
        if not any(n in files for n in names):
            return
        for n in names:
            files.pop(n, None)
        _write_atomic(_trims_path(slug), {"files": files})


def clear_trims(slug: str) -> None:
    """The shelf is empty, so there is nothing left to have trimmed."""
    with _TRIM_LOCK:
        try:
            _trims_path(slug).unlink()
        except OSError:
            pass


def trim_of(trims: "dict", name: str, duration) -> "tuple":
    """PURE. One file's usable window, resolved against its real duration.

    `(in_s, out_s)`, file-absolute seconds. No entry returns
    `(0.0, duration)` — the whole clip — so every downstream site calls
    this and the no-trim path is the SAME code path. A caller that
    branched on `if name in trims` would have two implementations of
    "usable range" and only one of them would get fixed.

    TOTAL by design: it is called from the assemble path and from take
    marking, where raising is not an option a caller can recover from.
    An unknown name, a junk entry, a non-numeric bound, an `out` past the
    real end of the file, an `in` past the `out` — every one of them
    degrades to a sane window rather than an exception. The file on disk
    is the truth; the sidecar is a note about it.

    The window is clamped to [0, duration]. When clamping would collapse
    it — a hand-edited entry, or a file replaced by a shorter one under
    the same name — the answer is the whole clip, never an empty window:
    an empty window would put every take outside the trim, and marking
    all of them is the failure this whole feature must not cause.
    """
    try:
        dur = float(duration)
    except (TypeError, ValueError):
        dur = 0.0
    if not (math.isfinite(dur) and dur > 0):
        # 0.0 is what `_footage_state` reports for a clip nothing has
        # probed yet. There is no length to clamp against, so a stored
        # window is passed through as-is rather than clamped to nothing.
        dur = 0.0
    whole = (0.0, dur)
    if not isinstance(trims, dict):
        return whole
    entry = trims.get(os.path.basename(name or ""))
    if not isinstance(entry, dict):
        return whole
    try:
        start, end = float(entry.get("in")), float(entry.get("out"))
    except (TypeError, ValueError):
        return whole
    if not (math.isfinite(start) and math.isfinite(end)):
        return whole
    start = max(0.0, start)
    end = max(0.0, end)
    if dur:
        start, end = min(start, dur), min(end, dur)
    # ROUND FIRST, then test. Rounding after the test is how an empty
    # window gets out of here: a legal stored trim of `in` 59.9 / `out`
    # 60.4 against a file that probes at 59.9004s clamps to
    # (59.9, 59.9004) — which passes `end > start` — and only then rounds
    # to (59.9, 59.9). Measured 2026-08-28, reachable with no hand-editing
    # at all: it is the "file replaced by a shorter one" case this
    # docstring already promises to degrade, whenever the new length lands
    # inside a millisecond of the in point.
    start, end = round(start, 3), round(end, 3)
    if end <= start:
        return whole
    return start, end
