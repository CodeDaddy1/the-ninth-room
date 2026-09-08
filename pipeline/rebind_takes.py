# -*- coding: utf-8 -*-
"""Point a beat at the take it actually shows.

A beat names a take and carries a trim. On hmns, nine beats name the
WRONG take while carrying the right trim — the fossil record of hand
surgery on a plan across two sessions, the same surgery whose take ids
drifted by one in one run and by one the other way in another.

Nothing on screen is wrong. The assembler reads the trim, the proxies
render the right seconds, and Caleb reviewed and approved all 82 beats
of the episode that shipped. It is the LABEL that lies, and the label
is what the id scheme derives identity from, so every one of those
beats is named after a shot it does not show.

WHAT IT COSTS TO LEAVE: `validate_edit_plan` refuses the plan, and
`plan_beats` refuses to assemble on a validation error. hmns could not
be re-assembled, re-cut, tightened or conformed at all — the episode was
frozen, and the reason was nine wrong strings.

THE EVIDENCE IS THE WORDS, not the numbers. For each broken beat this
ranks every take whose window could hold the trim by how much of the
beat's own caption that take actually says. It proposes a re-bind only
when one take says effectively all of it and no other comes close.
Anything ambiguous is reported and left alone: a wrong re-bind is worse
than a beat that still fails, because a failure is visible and a wrong
label is not — which is the whole lesson of this file existing.

The rename that follows is the beat-id migration's job, reused whole:
new ids derive from the corrected anchors, verdicts carry by cut span
(the trims do not move, so every verdict carries with its status), and
the ten keyed artifacts follow. The id map gains a generation, so the
name a beat had this morning still resolves.

Run:
    /usr/bin/python3 -m pipeline.cli rebind-takes <slug>
    /usr/bin/python3 -m pipeline.cli rebind-takes <slug> --apply
"""
from __future__ import annotations

import copy
import json
import re
import shutil
from pathlib import Path

from .ingest import work_path, words_by_file
from . import beat_identity, migrate_ids, plan_history, schemas

# A candidate must say this much of the beat's caption, and beat the
# runner-up by this margin. Measured on hmns (2026-09-08): every one of
# the nine has a take saying 95 to 100 percent of the caption, and the
# next best says 73 percent or less. Well clear of both numbers.
MIN_SHARE = 0.9
MIN_MARGIN = 0.2


class RebindError(Exception):
    pass


def _words(s) -> "set":
    return set(x for x in re.sub(r"[^a-z0-9 ]", " ", str(s or "").lower()).split())


def _share(caption, transcript) -> float:
    """How much of the caption this take actually says."""
    cap = _words(caption)
    return len(cap & _words(transcript)) / len(cap) if cap else 0.0


def _read(p: Path):
    try:
        return json.loads(p.read_text())
    except (OSError, ValueError):
        return None


def survey(slug: str) -> "dict":
    """Every beat whose trim lies outside its take's window, and the take
    that says its words. Writes nothing."""
    work = work_path(slug)
    plan = _read(work / "edit_plan.json")
    takes_doc = _read(work / "analysis" / "takes.json") or {}
    if plan is None:
        raise RebindError("%s has no readable edit_plan.json" % slug)
    rows = takes_doc.get("takes") or []
    if not rows:
        raise RebindError("%s has no takes.json — nothing to bind to" % slug)
    by_id = {t["id"]: t for t in rows}
    caps = {c.get("beat_id"): c.get("text") or ""
            for c in ((_read(work / "captions.json") or {}).get("beats") or [])}

    proposals, ambiguous, unbound = [], [], []
    for i, b in enumerate(plan.get("beats") or []):
        tid, trim = b.get("take_id"), b.get("trim")
        t = by_id.get(tid)
        if not t or not isinstance(trim, dict):
            continue
        lo, hi = schemas.take_window(t, rows)
        if lo - 0.01 <= trim["s"] and trim["e"] <= hi + 0.01:
            continue                      # this beat is bound correctly
        cap = caps.get(b.get("id")) or ""
        # every take that COULD hold this trim, best-said first
        fits = []
        for o in rows:
            olo, ohi = schemas.take_window(o, rows)
            if olo - 0.01 <= trim["s"] and trim["e"] <= ohi + 0.01:
                fits.append((_share(cap, o.get("transcript")), o["id"]))
        fits.sort(reverse=True)
        row = {"index": i, "beat_id": b.get("id"), "was": tid,
               "trim": [trim["s"], trim["e"]], "caption": cap[:70],
               "candidates": [{"take": c[1], "says": round(c[0], 2)}
                              for c in fits[:3]]}
        if not fits:
            unbound.append(row)
        elif not cap:
            row["why"] = "no caption to match against"
            ambiguous.append(row)
        elif fits[0][0] < MIN_SHARE:
            row["why"] = ("best candidate says only %.0f%% of the caption"
                          % (100 * fits[0][0]))
            ambiguous.append(row)
        elif len(fits) > 1 and fits[0][0] - fits[1][0] < MIN_MARGIN:
            row["why"] = ("%s and %s are too close to call"
                          % (fits[0][1], fits[1][1]))
            ambiguous.append(row)
        else:
            row["to"] = fits[0][1]
            row["says"] = round(fits[0][0], 2)
            proposals.append(row)
    return {"slug": slug, "beats": len(plan.get("beats") or []),
            "proposals": proposals, "ambiguous": ambiguous,
            "unbound": unbound, "plan": plan}


def _renamed_plan(plan: "dict", proposals: "list") -> "tuple":
    """The corrected plan and {old id: new id}, POSITIONALLY.

    Positionally because a rebind CHANGES a beat's anchor, and
    `beat_identity.id_map` matches beats by (anchor, occurrence) — the
    one assumption that does not hold here. Nothing is added, removed or
    reordered, so index i is index i on both sides and the mapping is
    exact rather than inferred.
    """
    out = copy.deepcopy(plan)
    for p in proposals:
        out["beats"][p["index"]]["take_id"] = p["to"]
    new = beat_identity.derive_ids(out)
    renamed, every = {}, {}
    for old_b, new_b in zip(plan.get("beats") or [], new.get("beats") or []):
        o, n = old_b.get("id"), new_b.get("id")
        if not (o and n):
            continue
        every[o] = n              # INCLUDING the ones that did not move
        if o != n:
            renamed[o] = n
    return new, renamed, every


# `every` exists because `carry_review` reads a mapping as the whole
# story: a verdict whose beat id is absent from it has nowhere to go and
# is archived. Handing it only the renames archived 72 of hmns's 82
# verdicts in the sandbox run — the beats that were CORRECT lost their
# history, which is the exact damage this file exists to prevent, caused
# by the tool preventing it. The map file still records only the moves;
# identity entries there would be noise.


def apply(slug: str, log=print) -> "dict":
    """Correct the labels, rename what they name, carry everything."""
    s = survey(slug)
    if not s["proposals"]:
        raise RebindError("%s: nothing to rebind" % slug)
    work = work_path(slug)
    plan = s["plan"]
    new, mapping, every = _renamed_plan(plan, s["proposals"])

    errs = schemas.validate_edit_plan(
        new, _read(work / "analysis" / "takes.json") or {},
        _read(work / "analysis" / "broll.json") or {"clips": []},
        words=words_by_file(slug))
    bounds = [e for e in errs if "outside take" in e]
    if bounds:
        raise RebindError("the rebound plan still fails its bounds: %s"
                          % bounds[0])
    id_errs = beat_identity.id_errors(new)
    if id_errs:
        raise RebindError("the rebound plan breaks the id invariant: %s"
                          % id_errs[0])

    row = plan_history.archive(slug, reason="manual",
                               note="rebind %d beats onto the take they show"
                                    % len(s["proposals"]))
    log("[rebind] archived the current cut as v%d" % (row or {}).get("v", 0))

    bdir = migrate_ids.backup_dir(work)
    bdir.mkdir(parents=True, exist_ok=True)
    for rel, _f, _k in migrate_ids.ARTIFACTS + (("edit_plan.json", None, None),):
        src = work / rel
        if src.exists():
            shutil.copy2(str(src), str(bdir / rel.replace("/", "__")))
    log("[rebind] backed up %d artifacts to %s/"
        % (len(list(bdir.iterdir())), bdir.name))

    migrate_ids._write(work / "edit_plan.json", new)
    for p in s["proposals"]:
        log("[rebind] %-13s %s -> %s   (says %.0f%% of its caption)"
            % (p["beat_id"], p["was"], p["to"], 100 * p["says"]))

    if mapping:
        migrate_ids._write(work / migrate_ids.MAP_FILE,
                           migrate_ids._map_doc(
                               _read(work / migrate_ids.MAP_FILE), slug, mapping))
        review = _read(work / "review.json") or {}
        carried = beat_identity.carry_review(review, every, plan, new)
        if (work / "review.json").exists():
            migrate_ids._write(work / "review.json", carried["carried"])
            if carried["stranded"]:
                plan_history.archive_review(slug, "rebind", carried["stranded"])
        log("[rebind] %d beats renamed, %d verdicts carried, %d requeued, "
            "%d archived" % (len(mapping), len(carried["carried"]),
                             len(carried["requeued"]), len(carried["stranded"])))
        for rel, field, key in migrate_ids.ARTIFACTS:
            if rel == "review.json":
                continue
            p = work / rel
            doc = _read(p) if p.exists() else None
            if doc is None:
                continue
            doc, n, strand = migrate_ids._remap_doc(doc, field, key, every)
            migrate_ids._write(p, doc)
            if n:
                log("[rebind] %-28s %d remapped" % (rel, n))
    return {"slug": slug, "rebound": len(s["proposals"]),
            "renamed": len(mapping), "backup_dir": bdir.name,
            "ambiguous": len(s["ambiguous"]), "unbound": len(s["unbound"])}


def print_survey(s: "dict", log=print) -> None:
    log("")
    log("  %s — %d beats" % (s["slug"], s["beats"]))
    if not (s["proposals"] or s["ambiguous"] or s["unbound"]):
        log("  every beat names the take it shows.\n")
        return
    for p in s["proposals"]:
        log("  %-13s %-5s -> %-5s  trim %.2f-%.2f  says %.0f%% of: %s"
            % (p["beat_id"], p["was"], p["to"], p["trim"][0], p["trim"][1],
               100 * p["says"], p["caption"][:44]))
    for p in s["ambiguous"] + s["unbound"]:
        log("  %-13s %-5s -> ?      %s  [%s]"
            % (p["beat_id"], p["was"], p.get("why", "no take can hold this trim"),
               ", ".join("%s %.0f%%" % (c["take"], 100 * c["says"])
                         for c in p["candidates"]) or "no candidates"))
    log("")
