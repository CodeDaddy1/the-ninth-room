"""Declared preconditions: what a job needs true BEFORE it is billed.

docs/decisions-job-preconditions.md (2026-08-28) asked for this module and
nothing built it until a paid kind needed a gate that answers before the
click. It starts with the illustration kind only (decision 17); existing
kinds keep their imperative guards in jobs.py and are not touched here.

A Predicate is a name, the sentence the desk shows when it refuses, the
surface that sentence points at, and a pure check over the slug's files.
`jobs.start()` runs the set for the kind and its arg and raises before
enqueue; the runner runs the same set again and lands `declined`. The
two answers cannot drift because they are the same list.

This module must never import jobs (tests/test_preconditions.py pins it):
jobs imports it, not the other way.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable, Optional

from . import illustration, paths
from .ingest import work_path


class Predicate(object):
    def __init__(self, id: str, message: str, surface: str,
                 check: "Callable[[str], bool]"):
        self.id, self.message, self.surface, self.check = id, message, surface, check

    def __repr__(self):
        return "Predicate(%s)" % self.id


def refused(predicates: "list[Predicate]", slug: str) -> "list[Predicate]":
    """Every predicate in the list that is NOT satisfied, in order."""
    return [p for p in predicates if not p.check(slug)]


def _read(p: Path) -> Optional[dict]:
    try:
        return json.loads(p.read_text())
    except (OSError, ValueError):
        return None


def _lane(slug: str) -> str:
    return "script" if (work_path(slug) / "script.json").exists() else "footage"


def _rounds(slug: str) -> "list[dict]":
    doc = _read(work_path(slug) / "asset_requests.json") or {}
    return [r for r in doc.get("rounds", []) or [] if isinstance(r, dict)]


def _live_ids(slug: str) -> "set[str]":
    return {str(r.get("section_id") or r.get("beat_id"))
            for r in _rounds(slug)
            if r.get("kind") == "illustration" and r.get("status") in ("proposed", "approved")}


def _targets(slug: str) -> "list[str]":
    """Sections or beats asking for an illustration with no live round."""
    live = _live_ids(slug)
    out = []
    if _lane(slug) == "script":
        for ch in (_read(work_path(slug) / "script.json") or {}).get("chapters", []) or []:
            for sec in (ch or {}).get("sections", []) or []:
                vis = (sec or {}).get("visual") or {}
                if isinstance(vis, dict) and vis.get("from") == "illustration" \
                        and str(sec.get("id")) not in live:
                    out.append(str(sec.get("id")))
    else:
        for b in (_read(work_path(slug) / "edit_plan.json") or {}).get("beats", []) or []:
            vis = (b or {}).get("visual") or {}
            if isinstance(vis, dict) and vis.get("from") == "illustration" \
                    and str(b.get("id")) not in live:
                out.append(str(b.get("id")))
    return out


def _has_story(slug: str) -> bool:
    w = work_path(slug)
    if _lane(slug) == "script":
        return bool((_read(w / "script.json") or {}).get("locked"))
    return (w / "edit_plan.json").exists() and (w / "analysis" / "broll.json").exists()


def _approved(slug: str) -> "list[dict]":
    return [r for r in _rounds(slug)
            if r.get("kind") == "illustration" and r.get("status") == "approved"]


def _cap_fits(slug: str) -> bool:
    try:
        illustration.cap_check(slug, _approved(slug))
    except Exception:
        return False
    return True


def _soul_available(slug: str) -> bool:
    needs = any(st.get("soul") for r in _approved(slug)
                for st in (r.get("steps") or []) if isinstance(st, dict))
    return (not needs) or bool(paths.soul_id())


def _marks_consistent(slug: str) -> bool:
    w = work_path(slug)
    brief = _read(w / "story_brief.json") or {}
    script = _read(w / "script.json")
    plan = _read(w / "edit_plan.json") if script is None else None
    for r in _approved(slug):
        if illustration.validate_round(r, brief.get("delivery"), script=script, plan=plan):
            return False
    return True


PROJECT_EXISTS = Predicate(
    "project_exists", "no such project", "/studio",
    lambda slug: work_path(slug).is_dir())
HAS_STORY = Predicate(
    "has_story",
    "the story is not ready: lock the script on the Script desk, or build the "
    "cut on the Story desk and analyze the footage first",
    "/studio/script", _has_story)
HAS_TARGETS = Predicate(
    "has_targets",
    "nothing asks for an illustration yet: a section or beat needs "
    "`visual.from: illustration` with no round already waiting",
    "/studio/script", lambda slug: bool(_targets(slug)))
HIGGSFIELD_CLI_PRESENT = Predicate(
    "higgsfield_cli_present", "the Higgsfield CLI is not installed on this machine",
    "/studio/takes", lambda slug: Path(paths.higgsfield_bin()).exists())
CAP_HEADROOM = Predicate(
    "cap_headroom",
    "this episode has spent its %d illustration credits" % int(illustration.EPISODE_CREDIT_CAP),
    "/studio/takes", lambda slug: illustration.spent(slug) < illustration.EPISODE_CREDIT_CAP)
ROUNDS_APPROVED = Predicate(
    "rounds_approved", "no illustration round is approved on the Library desk",
    "/studio/takes", lambda slug: bool(_approved(slug)))
CAP_FITS = Predicate(
    "cap_fits", "the approved rounds would pass the episode's credit cap",
    "/studio/takes", _cap_fits)
SOUL_AVAILABLE = Predicate(
    "soul_available",
    "an approved round puts the host in a picture but NINTH_ROOM_SOUL_ID is not set",
    "/studio/takes", _soul_available)
MARKS_CONSISTENT = Predicate(
    "marks_consistent",
    "an approved round asks for a tier or a model Caleb has not marked on it",
    "/studio/takes", _marks_consistent)

ILLUSTRATE_PROPOSE = [PROJECT_EXISTS, HAS_STORY, HAS_TARGETS,
                      HIGGSFIELD_CLI_PRESENT, CAP_HEADROOM]
ILLUSTRATE_GENERATE = [PROJECT_EXISTS, HAS_STORY, HIGGSFIELD_CLI_PRESENT,
                       ROUNDS_APPROVED, CAP_FITS, SOUL_AVAILABLE, MARKS_CONSISTENT]

# Whether a failed run may simply be pressed again. Propose writes nothing
# paid; generate is idempotent per step but a re-press is a human decision.
RETRYABLE = {("illustrate", None): True, ("illustrate", "generate"): False}
