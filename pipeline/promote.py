# -*- coding: utf-8 -*-
"""The one seam a cut passes through to become the cut.

`_run_editplan` was the only session-written artifact in the program with
no post-condition bar. `_run_script` is gated by `script_notes` and
`_run_coverage` by `validate_edit_plan` + `coverage_notes`, but the cut —
the artifact Caleb actually watches — was checked for one thing: that a
file appeared. What that produced is on record: 82 beats, 78% of them
undifferentiated `build`, one hook, one payoff, zero peaks, zero loops,
one texture end to end.

The shape is staging-then-promote rather than write-then-check, and the
difference is not cosmetic. A session that writes `edit_plan.json`
directly has already replaced the cut by the time anything looks at it,
so a failed check leaves the project holding a plan nobody approved and
the only way back is a backup. Writing to `staging/` means a failure
changes nothing: the live plan is untouched, the staged file stays
exactly where the agent left it, and the notes can be handed back to a
second attempt to fix IN PLACE rather than rewrite from nothing.

ONE FUNCTION, TWO JOBS. `editplan` and `recut` are two callers of
`promote_cut`, not two implementations of it. They differ only in their
preconditions and in whether there is history to carry; everything from
"read the staged file" to "os.replace it into place" is this module. Two
implementations of a promote is how a bug gets fixed in one of them.

`check_cut` has THREE consumers by design — the CLI verb the agent runs
to prove itself clean before ending its session, this module's gate, and
`/api/cut/recheck` for the Studio. One implementation, so the bar the
job enforces and the bar the desk displays cannot drift apart. That is
the two-consumer rule from `docs/decisions-job-preconditions.md`, obeyed
at construction rather than retrofitted.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from .ingest import work_path, analysis_dir, IngestError
from . import beat_identity, cutbar, plan_history, schemas

STAGE_DIRNAME = "staging"
PLAN_NAME = "edit_plan.json"
RECUT_REPORT = "recut_report.json"
REVIEW_ARCHIVE = plan_history.REVIEW_ARCHIVE   # one home, two writers

# THE CRAFT BAR IS NOT ARMED YET, and this constant is the whole switch.
#
# Same idiom as `cutbar.GEAR_RATIO_MIN = None`: the check is built, tested
# and computed on every promote, and it reports rather than refuses until
# a threshold has been through the ten-minute calibration review with
# Caleb. `.claude/reminders.md` carries that as an open box, and the
# plan's own rule is that no gate goes live before he has seen the
# numbers — every one of them is a single constant at the top of
# `pipeline/cutbar.py`.
#
# Flipping this to True is the entire arming step. Nothing else changes.
BAR_ARMED = True


def stage_dir(slug: str) -> Path:
    return work_path(slug) / STAGE_DIRNAME


def staged_plan(slug: str) -> Path:
    return stage_dir(slug) / PLAN_NAME


def live_plan(slug: str) -> Path:
    return work_path(slug) / PLAN_NAME


def _read(p: Path):
    try:
        return json.loads(p.read_text())
    except (OSError, ValueError):
        return None


def _material(slug: str) -> "tuple":
    """takes, broll, brief — each degrading to a safe empty rather than
    raising, because every checker here is written to tolerate them and a
    documentary legitimately has no takes."""
    out = analysis_dir(slug)
    takes = _read(out / "takes.json") or {"takes": []}
    broll = _read(out / "broll.json") or {"clips": []}
    brief = _read(work_path(slug) / "story_brief.json") or {}
    return takes, broll, brief


def check_cut(slug: str, staged: bool = False) -> "dict":
    """Run the cut's own gates against what is on disk right now.

    Reports, never refuses — `ok` says whether it would pass. The job
    turns this into a refusal; the desk renders it; the agent reads it
    mid-session. `metrics` rides along because a surface that shows the
    failures without the numbers cannot tell over-gating from a bad cut.
    """
    p = staged_plan(slug) if staged else live_plan(slug)
    if not p.exists():
        raise IngestError("no %s cut to check" % ("staged" if staged else "built"))
    plan = _read(p)
    if plan is None:
        raise IngestError("%s is not readable JSON" % p.name)
    takes, broll, brief = _material(slug)
    errors = schemas.validate_edit_plan(plan, takes, broll)
    errors += beat_identity.id_errors(plan)
    notes = cutbar.cut_notes(plan, takes, broll, brief)
    return {"slug": slug, "staged": staged, "errors": errors, "notes": notes,
            "metrics": cutbar.cut_metrics(plan, takes, broll),
            "bar_armed": BAR_ARMED,
            "ok": not errors and not notes}


def promote_cut(slug: str, reason: str, note: str = "",
                carry_from: "dict | None" = None, log=print) -> "dict":
    """Validate the staged cut and make it the cut. Nothing on disk
    changes unless every gate passes.

    `carry_from` is the plan being replaced, when there is one — that is
    what turns a promote into a re-cut: verdicts follow the SHOT through
    the id map instead of being thrown away.
    """
    src = staged_plan(slug)
    if not src.exists():
        # This converts "the session ran and wrote nothing" into a named
        # failure at the moment it happens, instead of the old
        # "edit_plan.json was not written" after the money was spent.
        raise RuntimeError(
            "the session finished without writing %s — read the log; "
            "nothing was promoted and the built cut is untouched" % src)
    plan = _read(src)
    if plan is None:
        raise RuntimeError("%s is not readable JSON — the staged file is "
                           "kept for diagnosis" % src)

    takes, broll, brief = _material(slug)

    # 1. MINT THE IDS. The agent no longer names beats; whatever
    #    placeholders it wrote are rewritten from the shot each beat
    #    shows, so a rebuilt cut keeps its history by construction.
    plan = beat_identity.derive_ids(plan)

    # 2. Correctness. These refuse whether or not the craft bar is armed:
    #    a plan that does not validate cannot be rendered at all.
    errs = schemas.validate_edit_plan(plan, takes, broll)
    if errs:
        raise RuntimeError("the cut does not validate: %s%s"
                           % ("; ".join(errs[:4]),
                              " (+%d more)" % (len(errs) - 4)
                              if len(errs) > 4 else ""))
    id_errs = beat_identity.id_errors(plan)
    if id_errs:
        raise RuntimeError("the beat ids do not hold: %s" % id_errs[0])

    # 3. Craft. Reported always, refused only once armed.
    notes = cutbar.cut_notes(plan, takes, broll, brief)
    if notes:
        if BAR_ARMED:
            raise RuntimeError("the cut misses the bar: %s%s"
                               % ("; ".join(notes[:4]),
                                  " (+%d more)" % (len(notes) - 4)
                                  if len(notes) > 4 else ""))
        log("[promote] the craft bar is NOT armed yet — %d note(s) "
            "reported, none of them blocking:" % len(notes))
        for n in notes[:4]:
            log("[promote]   %s" % n)

    # 4. History, and the verdicts that survive it.
    report = {"slug": slug, "reason": reason, "note": note,
              "beats": len(plan.get("beats") or []),
              "notes": notes, "carried": [], "requeued": [],
              "stranded": [], "added": []}
    archived = plan_history.archive(slug, reason=reason, note=note)
    if archived:
        report["archived_v"] = archived["v"]
    if carry_from:
        m = beat_identity.id_map(carry_from, plan)
        review = _read(work_path(slug) / "review.json") or {}
        carried = beat_identity.carry_review(review, m["map"],
                                             carry_from, plan)
        _write(work_path(slug) / "review.json", carried["carried"])
        if carried["stranded"]:
            # APPEND. This wrote the whole file until 2026-09-08, and so
            # did the beat-id migration, so whichever ran second deleted
            # the other's record — including hmns's 14 ghosts, which
            # carry Caleb's notes on beats that no longer exist.
            plan_history.archive_review(
                slug, "re-cut: %s" % (note or reason), carried["stranded"])
        report["carried"] = sorted(carried["carried"])
        report["requeued"] = carried["requeued"]
        report["stranded"] = [s["id"] for s in carried["stranded"]]
        report["added"] = [b["id"] for b in plan.get("beats") or []
                           if b["id"] not in carried["carried"]]
        report["metrics_before"] = cutbar.cut_metrics(carry_from, takes, broll)
        log("[promote] %d verdicts carried, %d back in the queue, %d "
            "archived with nowhere to go"
            % (len(report["carried"]), len(report["requeued"]),
               len(report["stranded"])))

    # 5. THE SWAP, last and atomic. Everything above raises before this
    #    line, so a failed promote leaves the built cut exactly as it was
    #    and the staged file exactly where the agent left it.
    _write(live_plan(slug), plan)
    report["metrics"] = cutbar.cut_metrics(plan, takes, broll)

    # 6. Keep the agent's raw pre-normalisation output, even on success —
    #    it is the only record of what the session actually wrote.
    if archived:
        raw = plan_history.history_dir(slug) / ("staged.v%04d.json"
                                                % archived["v"])
        try:
            os.replace(str(src), str(raw))
        except OSError:
            pass
    else:
        try:
            src.unlink()
        except OSError:
            pass

    if carry_from:
        _write(work_path(slug) / RECUT_REPORT, report)
    return report


def clear_staging(slug: str) -> None:
    """Before a fresh dispatch. NOT called on failure — a failed promote
    keeps its staged file, because that file plus its notes is what makes
    the retry an edit rather than a rewrite."""
    p = staged_plan(slug)
    if p.exists():
        try:
            p.unlink()
        except OSError:
            pass


def _write(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".%d.tmp" % os.getpid())
    try:
        tmp.write_text(json.dumps(data, indent=2))
        os.replace(str(tmp), str(path))
    except BaseException:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise
