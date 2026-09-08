# -*- coding: utf-8 -*-
"""The assembly craft bar — the cut's numbers, and the bar a cut must clear.

The cut is the least-checked artifact in the program (2026-08-28).
_run_script is hard-gated by schemas.script_notes and _run_coverage by
schemas.coverage_notes, but _run_editplan only checks that a file appeared.
What that bought us is the shipped hmns cut: a transcript in shoot order —
82 beats of which 64 (78%) are purpose "build", one hook, one stakes, one
payoff, zero beats marked peak, zero named techniques, 12.6 cuts/min flat
against 18.5 (Mark Rober), 21.6 (Kara & Nate) and 18.8 (Yes Theory) in
docs/film-studies/. This module is where the studies' measured numbers
finally gate something.

It is a NEW MODULE rather than more lines in schemas.py (1,933 lines
already) — the same reason docs/decisions-job-preconditions.md gives for
the predicate registry.

Two entry points, mirroring the coverage_notes/script_notes contract:

  cut_metrics(plan, takes, broll)         -> dict — numbers, NEVER gates
  cut_notes(plan, takes, broll, brief)    -> list — the bar; empty is pass

Both are PURE: parsed dicts in, numbers or sentences out; the caller reads
the files. Every check tolerates a plan mid-surgery — an absent field, an
unknown id or a wrong type is a note or a skip, never a raise.

The realized-pace estimate is APPROXIMATE exactly the way gear_change is.
Visual state changes are counted from the plan — each beat is one change,
each cover two (the cut away and the cut back), plus punch-ins and in-beat
cuts — and silence cuts are added later by pipeline/timeline.py
plan_beats, so the estimate compares the SHAPE of the declared ladder
against the plan, not the truth of the finished timeline.
"""
from __future__ import annotations

import re
from typing import Any

from . import schemas
from .schemas import CLIMAX_AT, COVER_MIN_S
from .takes import quiet_floor, rushed_ceiling, superseded_takes, take_flags

# C1 — the declining ladder. Kara & Nate ran 39.6 -> 14.0 cuts/min over six
# chapters, ratio 0.35, with no reversal in cut rate or median shot length
# (docs/film-studies/). hmns ran 12.6 throughout.
PACE_TOLERANCE = 0.10    # a 10% chapter-to-chapter wobble is not a reversal
PACE_DECLINE_MAX = 0.70  # last <= 0.7 * first. Loose next to K&N's 0.35 on
                         # purpose — the first setting only has to kill a
                         # FLAT series, which is hmns's 12.6-throughout
PACE_REVERSALS_MAX = 1   # CALIBRATED 2026-08-28. Strict monotonicity was
                         # the spec, and all five cuts on disk broke it —
                         # every one re-energizes in the middle (hmns
                         # 28.9/14.6/21.8/19.5/15.9). The rule rests on ONE
                         # measured video, and a museum day changes hall
                         # five times: Caleb's call was that a new room
                         # earns a second wind, but only one. The overall
                         # decline below is what actually holds the shape.
PACE_BAND = 0.35         # realized within +/-35% of declared; the estimate
                         # compares shape, not truth, so the band is wide

# C2 — a chapter owes one real moment beyond its own doors.
#
# THE BUILD-SHARE CAP WAS DROPPED, CALIBRATED 2026-08-28. It read: build
# beats may not exceed 60% of the cut. Measured against the real plans it
# was unreachable and it did not track quality. Unreachable because the
# purpose vocabulary holds only two non-structural roles, so hmns's 82
# beats offer 12 structural slots (5 opens, 5 closes, hook, payoff) against
# the 33 non-build beats a 60% cap demands — the other 21 could only be
# label inflation. Not a quality signal because hmns (0 peaks, 0 loops)
# scores 78% and houston (5 peaks, 3 loops) scores 75%: three points apart,
# and one of them is an arc. A gate a session passes by renaming beats
# changes no frames, so this asks for the thing itself instead.
CHAPTER_TEXTURE = ("stakes", "payoff", "button")   # or a peak beat
LOOPS_MIN = 2            # a long-form cut owes at least two open promises
                         # — Rober opens eight and pays all eight in order
LONG_FORM_CHAPTERS = 3   # at or past this many chapters, the cut is
                         # long-form and the montage/loop rules apply

# C3 — peak protection is the finding six of the seven film studies
# independently confirmed: the reaction is the product, and it is delivered
# uncovered. hmns marked zero.
# CALIBRATION GAP, for the ten-minute review: PEAKS_MIN and the
# max(PEAKS_MIN, chapters-1) rule below were measured against five
# LONG-FORM cuts (hmns, houston, allure and the two _compare_ runs, all
# 82-beat museum days). No short was in that set, so a 45-second vertical
# is currently told to protect two moments of 8s or more out of 45s. That
# may well be right — a short is mostly payoff — but it is untested, and
# inventing a short-form threshold here rather than measuring one is the
# mistake the build-share cap already made once (2026-09-08).
PEAKS_MIN = 2
PEAK_LEN_S = (8.0, 45.0)  # the standing rule says 15-30s; the band is
                          # wider so a marked reaction beat does not
                          # false-fail on an honest long laugh

# C4 — the hook previews min(n_chapters, 4) chapters. Past four shots the
# montage stops being a preview and starts being a trailer.
HOOK_COVERS_CAP = 4

# C5 — ships OFF. Every edit plan in existence has ZERO vo beats (they all
# predate the VO-led format, measured 2026-08-27 in schemas.gear_change),
# so a threshold shipped today would be a guess about footage that does
# not exist. cut_metrics reports the ratio; cut_notes says nothing while
# this is None. Arming it is one constant change: set the minimum ratio
# here and the note fires on plans with at least GEAR_MIN_VO_BEATS.
GEAR_RATIO_MIN = None
GEAR_MIN_VO_BEATS = 5    # under this many vo beats the ratio is noise

# C7 — the shot-size vocabulary for broll clip `framing`. Declared here:
# the catalog has never carried the field, and it fills in exactly the
# order it matters — a clip is only asked for a size once a plan uses it.
# One home for the vocabulary: schemas owns it, the catalog and the
# validator read it there too (2026-09-08).
SHOT_SIZES = schemas.SHOT_SIZES

_CH_RE = re.compile(r"CH(\d+)")


# ---------------------------------------------------------------- helpers

def _num(v: "Any") -> "float | None":
    """A real number or None. bool is not a duration."""
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    return float(v)


def _list(v: "Any") -> "list":
    return v if isinstance(v, list) else []


def _sid(v: "Any") -> "str | None":
    """A string id, or None. An id of any other type cannot index — and a
    mid-surgery plan can hold a dict or a list where an id goes, which an
    unguarded dict lookup turns into TypeError: unhashable (found in
    verification, 2026-08-28). A malformed id is validate_edit_plan's
    error; here it is a skip."""
    return v if isinstance(v, str) else None


def _beats(plan: "dict[str, Any]") -> "list[dict]":
    return [b for b in _list(plan.get("beats")) if isinstance(b, dict)]


def _chapters(plan: "dict[str, Any]") -> "list[dict]":
    return [c for c in _list(plan.get("chapters")) if isinstance(c, dict)]


def _covers(b: "dict") -> "list[dict]":
    return [c for c in _list(b.get("broll")) if isinstance(c, dict)]


def _beat_dur(b: "dict") -> float:
    """Planned seconds of one beat: the trim span, else the spine span.

    The spine fallback matters on real data — houston's shipped plan holds
    29 picture beats whose span lives on spine.src_s/src_e and no trim
    (2026-08-28); counting them zero would halve that episode's runtime.
    """
    for src, lo, hi in ((b.get("trim"), "s", "e"),
                       (b.get("spine"), "src_s", "src_e")):
        if isinstance(src, dict):
            s, e = _num(src.get(lo)), _num(src.get(hi))
            if s is not None and e is not None and e > s:
                return e - s
    return 0.0


def _beat_changes(b: "dict") -> int:
    """Visual state changes one beat contributes: itself, two per cover
    (away and back), each punch-in, each in-beat cut."""
    return (1 + 2 * len(_covers(b))
            + len(_list(b.get("punches"))) + len(_list(b.get("cuts"))))


def _takes_index(takes: "dict | None") -> "dict":
    """{id: take}, tolerant of anything: this bar runs on files an agent
    is mid-way through writing."""
    if not isinstance(takes, dict):
        return {}
    rows = takes.get("takes")
    if not isinstance(rows, list):
        return {}
    return {t["id"]: t for t in rows
            if isinstance(t, dict) and isinstance(t.get("id"), str)}


def _ends(beats: "list[dict]") -> "list[float]":
    """Cumulative end time of each beat, in planned seconds."""
    out, at = [], 0.0
    for b in beats:
        at += _beat_dur(b)
        out.append(at)
    return out


# ------------------------------------------------------- C1: the ladder

def _pace_notes(plan: "dict[str, Any]") -> "list[str]":
    notes: "list[str]" = []
    chapters = _chapters(plan)
    if len(chapters) < 2:
        return notes
    declared: "list[tuple]" = []      # (chapter id, pace_cpm or None)
    for i, ch in enumerate(chapters):
        cid = ch.get("id") if isinstance(ch.get("id"), str) else \
            "chapters[%d]" % i
        v = _num(ch.get("pace_cpm"))
        declared.append((cid, v if v is not None and v > 0 else None))
    missing = [cid for cid, v in declared if v is None]
    if len(missing) == len(declared):
        # one note, not five — a plan written before the field existed
        # needs the rule taught once, not per chapter
        notes.append("plan: no chapter declares pace_cpm — without a "
                     "declining ladder the cut runs one speed end to end, "
                     "declare cuts/min on every chapter")
        return notes
    for cid in missing:
        notes.append("%s: no pace_cpm — every chapter declares its speed "
                     "or the ladder cannot be read" % cid)
    stated = [(cid, v) for cid, v in declared if v is not None]
    # One climb is a second wind; two is a ladder with no direction. Only
    # the reversals past the first are named, and the note says how many
    # there were so the count is never hidden behind the allowance.
    reversals = [(pid, pv, cid, cv)
                 for (pid, pv), (cid, cv) in zip(stated, stated[1:])
                 if cv > pv * (1 + PACE_TOLERANCE)]
    for pid, pv, cid, cv in reversals[PACE_REVERSALS_MAX:]:
        notes.append("%s: pace_cpm rises %.1f -> %.1f after %s, and that "
                     "is reversal %d — a new room earns one second wind, "
                     "not %d"
                     % (cid, pv, cv, pid,
                        reversals.index((pid, pv, cid, cv)) + 1,
                        len(reversals)))
    if len(stated) >= 2:
        first, last = stated[0][1], stated[-1][1]
        if last > first * PACE_DECLINE_MAX:
            notes.append("plan: pace_cpm ends at %.1f against a %.1f open "
                         "— Kara & Nate fall to 35%% of their opening "
                         "rate, and the close must sit at or under %.0f%% "
                         "of it" % (last, first, PACE_DECLINE_MAX * 100))
    # realized vs declared — the estimate is shape, not truth (see the
    # module docstring), which is why the band is a third either way
    beats = _beats(plan)
    for cid, v in stated:
        members = [b for b in beats if b.get("chapter_id") == cid]
        minutes = sum(_beat_dur(b) for b in members) / 60.0
        if not members or minutes <= 0:
            continue
        realized = sum(_beat_changes(b) for b in members) / minutes
        if abs(realized - v) > PACE_BAND * v:
            notes.append("%s: the plan realizes %.1f cuts/min against a "
                         "declared %.1f — outside the +/-%.0f%% band the "
                         "declaration is a wish, re-declare or re-cut"
                         % (cid, realized, v, PACE_BAND * 100))
    return notes


# --------------------------------------- C2a/C2b: purposes and chapters

def _purpose_notes(plan: "dict[str, Any]") -> "list[str]":
    notes: "list[str]" = []
    beats = _beats(plan)
    if not beats:
        return notes
    for ch in _chapters(plan):
        cid = ch.get("id")
        if not isinstance(cid, str) or not cid:
            continue
        members = [b for b in beats if b.get("chapter_id") == cid]
        if not members:
            continue     # an empty chapter is validate_edit_plan's problem
        purposes = {b.get("purpose") for b in members}
        if "chapter_open" not in purposes:
            notes.append("%s: no chapter_open in its run — the room is "
                         "entered mid-sentence" % cid)
        if "chapter_close" not in purposes:
            notes.append("%s: no chapter_close in its run — a door left "
                         "open leaks into the next room" % cid)
        # the texture rule that replaced the build-share cap: opening and
        # closing a room is stagecraft, not a story. Something has to
        # HAPPEN between the doors, and it has to be a beat that says so.
        if not (purposes.intersection(CHAPTER_TEXTURE)
                or any(b.get("peak") is True for b in members)):
            notes.append("%s: nothing between its doors but build beats — "
                         "a chapter owes one moment that lands: a peak, a "
                         "payoff, a stakes beat or a button" % cid)
    return notes


# ------------------------------------------------- C2c/C2d: mini-loops

def _declared_loops(plan: "dict[str, Any]") -> "tuple":
    """(opens, pays, order): opens {lid: beat index}, pays {lid: [beat
    indices]}, order = lids by opening position.

    Two declaration shapes are read. Beat-level opens_loop / pays_loop is
    the contract; plan-level `loops` [{id, opens, pays}] naming beat ids
    is ALSO read because houston's shipped plan already declares its
    ledger that way, mirroring the script's `loops` (2026-08-28) — a bar
    that told that plan it declared nothing would be grading the field
    name, not the craft.
    """
    beats = _beats(plan)
    idx_of: "dict" = {}
    for i, b in enumerate(beats):
        bid = b.get("id")
        if isinstance(bid, str) and bid not in idx_of:
            idx_of[bid] = i
    opens: "dict" = {}
    pays: "dict" = {}
    for i, b in enumerate(beats):
        lid = b.get("opens_loop")
        if isinstance(lid, str) and lid and lid not in opens:
            opens[lid] = i
        pid = b.get("pays_loop")
        if isinstance(pid, str) and pid:
            pays.setdefault(pid, []).append(i)
    for lp in _list(plan.get("loops")):
        if not isinstance(lp, dict):
            continue
        lid = lp.get("id")
        if not isinstance(lid, str) or not lid:
            continue
        o = idx_of.get(_sid(lp.get("opens")))
        y = idx_of.get(_sid(lp.get("pays")))
        if o is not None and lid not in opens:
            opens[lid] = o
        if y is not None:
            pays.setdefault(lid, []).append(y)
    order = sorted(opens, key=lambda lid: opens[lid])
    return opens, pays, order


def _loop_notes(plan: "dict[str, Any]") -> "list[str]":
    notes: "list[str]" = []
    beats = _beats(plan)
    opens, pays, order = _declared_loops(plan)
    for lid in pays:
        if lid not in opens:
            notes.append("%s: pays a loop that never opened — the viewer "
                         "cannot cash a promise they were never handed"
                         % lid)
    for lid in order:
        paid = pays.get(lid, [])
        if not paid:
            notes.append("%s: opens and never pays — the curiosity loop "
                         "never closes" % lid)
            continue
        if len(paid) > 1:
            notes.append("%s: paid %d times — a loop pays once, the "
                         "second payment is an echo" % (lid, len(paid)))
        if min(paid) <= opens[lid]:
            notes.append("%s: pays at or before it opens — the viewer "
                         "cannot want an answer they were never asked to "
                         "wait for" % lid)
    settled = [(opens[lid], min(pays[lid]), lid) for lid in order
               if pays.get(lid) and min(pays[lid]) > opens[lid]]
    for (o1, y1, id1), (o2, y2, id2) in zip(settled, settled[1:]):
        if y2 < y1:
            notes.append("%s pays before %s, which opened first — pay "
                         "them in the order they were opened" % (id2, id1))
    ends = _ends(beats)
    total = ends[-1] if ends else 0.0
    if settled and total > 0:
        last = max(y for _, y, _ in settled)
        where = ends[last] / total
        if where < CLIMAX_AT:
            notes.append("plan: the last loop closes %.0f%% of the way in "
                         "— the climax sits at %.0f%% or later (Rober "
                         "lands his at 72%%)"
                         % (where * 100, CLIMAX_AT * 100))
    if len(_chapters(plan)) >= LONG_FORM_CHAPTERS and len(opens) < LOOPS_MIN:
        notes.append("plan: %d loops declared on a %d-chapter cut — a "
                     "long-form episode owes at least %d open promises"
                     % (len(opens), len(_chapters(plan)), LOOPS_MIN))
    return notes


# ------------------------------------------------------------ C3: peaks

def _peak_notes(plan: "dict[str, Any]") -> "list[str]":
    notes: "list[str]" = []
    beats = _beats(plan)
    if not beats:
        return notes
    chapters = _chapters(plan)
    peaks = [b for b in beats if b.get("peak") is True]
    need = max(PEAKS_MIN, len(chapters) - 1)
    if len(peaks) < need:
        notes.append("plan: %d peak beats — protect at least %d, the "
                     "reaction is the product and six of seven studies "
                     "converged on exactly this" % (len(peaks), need))
    for ch in chapters[1:]:
        cid = ch.get("id")
        if not isinstance(cid, str) or not cid:
            continue
        members = [b for b in beats if b.get("chapter_id") == cid]
        if members and not any(b.get("peak") is True for b in members):
            notes.append("%s: no peak beat — every chapter after the "
                         "intro protects at least one moment" % cid)
    for b in peaks:
        dur = _beat_dur(b)
        if dur > 0 and not PEAK_LEN_S[0] <= dur <= PEAK_LEN_S[1]:
            notes.append("%s: a peak runs %.1fs — a protected moment "
                         "holds between %.0fs and %.0fs"
                         % (b.get("id"), dur, PEAK_LEN_S[0], PEAK_LEN_S[1]))
    return notes


# ------------------------------------------------- C4: the hook montage

def _hook_notes(plan: "dict[str, Any]") -> "list[str]":
    notes: "list[str]" = []
    chapters = _chapters(plan)
    if len(chapters) < LONG_FORM_CHAPTERS:
        return notes
    beats = _beats(plan)
    first_open = next((i for i, b in enumerate(beats)
                       if b.get("purpose") == "chapter_open"), None)
    if first_open is None:
        return notes     # C2 already names the missing opens
    covers = [c for b in beats[:first_open] for c in _covers(b)]
    need = min(len(chapters), HOOK_COVERS_CAP)
    if len(covers) < need:
        notes.append("the hook carries %d cover%s — the hook is a chapter "
                     "preview montage: one shot per chapter, in order, "
                     "each at least %.1fs, the line landing on the face"
                     % (len(covers), "" if len(covers) == 1 else "s",
                        COVER_MIN_S))
    named: "list[int]" = []
    for c in covers:
        cid = c.get("clip_id")
        d = _num(c.get("duration")) or 0.0
        if d < COVER_MIN_S:
            notes.append("hook cover %s runs %.1fs — under %.1fs a "
                         "preview cannot be read" % (cid, d, COVER_MIN_S))
        if schemas.why_kind(c.get("why")) != "foretell":
            notes.append("hook cover %s does not foretell — a hook cover "
                         "is a promise, lead its why with 'foretell'" % cid)
        m = _CH_RE.search(str(c.get("why") or ""))
        if m:
            named.append(int(m.group(1)))
    if covers and not named:
        # covers do not carry a chapter reference today, so the ordering
        # half reads the why. ONE note when none names a chapter — asking
        # per cover would be N copies of the same request.
        notes.append("no hook cover names a chapter — write the chapter "
                     "id (CH1, CH2...) into each cover's why so the "
                     "preview order can be read")
    elif any(b < a for a, b in zip(named, named[1:])):
        notes.append("the hook previews chapters out of order — the "
                     "montage runs CH1 to the end, the way the day will")
    return notes


# ------------------------------------------- C5: gear change (ships OFF)

def _gear_notes(plan: "dict[str, Any]",
                takes: "dict | None") -> "list[str]":
    if GEAR_RATIO_MIN is None:
        return []
    try:
        g = schemas.gear_change(plan, takes)
    except (TypeError, ValueError, KeyError, AttributeError):
        return []
    if g.get("vo_beats", 0) < GEAR_MIN_VO_BEATS:
        return []
    ratio = g.get("ratio", 0.0)
    if ratio < GEAR_RATIO_MIN:
        return ["plan: gear ratio %.2f across %d vo beats — the VO "
                "texture must cut faster than the scenes (Yes Theory "
                "runs 34.2 against 15.2)" % (ratio, g.get("vo_beats", 0))]
    return []


# ---------------------------------------------------------- C6: threads

def _thread_notes(plan: "dict[str, Any]") -> "list[str]":
    """Shape only. The chronology exemption a thread grants lands in
    schemas.validate_edit_plan in a later step, not here."""
    notes: "list[str]" = []
    declared: "dict" = {}
    for t in _list(plan.get("threads")):
        if isinstance(t, dict) and isinstance(t.get("id"), str) and t["id"]:
            declared.setdefault(t["id"], t)
    members: "dict" = {}
    order: "list[str]" = list(declared)
    for b in _beats(plan):
        tid = b.get("thread")
        if isinstance(tid, str) and tid:
            members[tid] = members.get(tid, 0) + 1
            if tid not in declared and tid not in order:
                order.append(tid)
    for tid in order:
        why = str((declared.get(tid) or {}).get("why") or "").strip()
        if not why:
            notes.append("%s: a thread with no why — a chronology "
                         "exception must say what it buys" % tid)
        if members.get(tid, 0) < 2:
            notes.append("%s: %d member beats — one beat is a jump "
                         "wearing a lanyard, a thread binds at least two"
                         % (tid, members.get(tid, 0)))
    return notes


# ----------------------------------------------------- C7: shot variety

def _clip_index(broll: "dict | None") -> "dict":
    if not isinstance(broll, dict):
        return {}
    return {c["id"]: c for c in _list(broll.get("clips"))
            if isinstance(c, dict) and isinstance(c.get("id"), str)}


def _variety_notes(plan: "dict[str, Any]", takes: "dict | None",
                   broll: "dict | None") -> "list[str]":
    notes: "list[str]" = []
    clips = _clip_index(broll)
    beats = _beats(plan)
    # (a) a used clip with no framing, one note per clip in first-use
    # order — self-enforcing: the catalog fills in exactly the order it
    # matters, because a clip is only asked for a size once a plan uses it
    used: "list[str]" = []
    for b in beats:
        refs = [c.get("clip_id") for c in _covers(b)]
        spine = b.get("spine")
        if isinstance(spine, dict):
            refs.append(spine.get("clip_id"))
        for cid in refs:
            if isinstance(cid, str) and cid not in used:
                used.append(cid)
    # ONE note for the whole tagging chore, not one per clip. The first
    # run against the shipped cuts returned 52 identical lines out of 85
    # (2026-08-28): the story findings were still first in the list, but
    # a human reading the report scrolled past them, and the desk would
    # have rendered 52 rows of the same sentence. The count and every id
    # stay in the note — a roll-up that hides what it rolled up is worse
    # than the flood.
    untagged = [cid for cid in used
                if cid in clips and clips[cid].get("framing") is None]
    mistagged = [cid for cid in used
                 if cid in clips
                 and clips[cid].get("framing") is not None
                 and clips[cid].get("framing") not in SHOT_SIZES]
    if len(untagged) == 1:
        notes.append("%s: no framing — read its contact sheet under "
                     "analysis/sheets and tag it one of %s"
                     % (untagged[0], "/".join(SHOT_SIZES)))
    elif untagged:
        notes.append("%d used clips carry no framing — read each contact "
                     "sheet under analysis/sheets and tag it one of %s: %s"
                     % (len(untagged), "/".join(SHOT_SIZES),
                        ", ".join(untagged)))
    if mistagged:
        notes.append("%s: framing is not a shot size — use one of %s"
                     % (", ".join(mistagged), "/".join(SHOT_SIZES)))

    def _framed(cover: "dict") -> "str | None":
        clip = clips.get(_sid(cover.get("clip_id")))
        f = (clip or {}).get("framing")
        return f if f in SHOT_SIZES else None

    # (b) inside one beat: consecutive covers must change framing — the
    # canonical progression steps tighter, wide toward detail — unless
    # the later cover's why says it is a match cut, which repeats a
    # shape on purpose. Any change satisfies the rule; only holding one
    # size twice is the violation, and one note per beat is enough
    # because the fix is the same for every pair in it.
    for b in beats:
        prev = None
        for c in _covers(b):
            f = _framed(c)
            if f is None:
                continue
            if prev is not None and f == prev \
                    and "match" not in str(c.get("why") or "").lower():
                notes.append("%s: consecutive covers hold %s — change "
                             "the framing, or step tighter wide to "
                             "detail" % (b.get("id"), f))
                break
            prev = f
    # (c) three of a size in a row across a run of VO beats — there the
    # covers ARE the picture, and three alike is a slideshow
    idx = _takes_index(takes)
    run: "list[tuple]" = []      # (framing, beat id) across consecutive vo
    for b in beats:
        # beat_kind indexes on the beat's take_id raw, so hand it a
        # sanitized one — the same unhashable-id skip _sid exists for
        if schemas.beat_kind({"take_id": _sid(b.get("take_id"))},
                             idx) != "vo":
            run = []
            continue
        for c in _covers(b):
            f = _framed(c)
            if f is None:
                continue
            run.append((f, b.get("id")))
            if len(run) >= 3 and run[-1][0] == run[-2][0] == run[-3][0]:
                notes.append("%s: three covers in a row run %s — a "
                             "slideshow, vary the shot size"
                             % (b.get("id"), f))
                run = []
                break
    return notes


# ----------------------------------------------------- C8: take quality

def _quality_notes(plan: "dict[str, Any]",
                   takes: "dict | None") -> "list[str]":
    notes: "list[str]" = []
    if not isinstance(takes, dict):
        return notes
    rows = [t for t in _list(takes.get("takes"))
            if isinstance(t, dict) and isinstance(t.get("id"), str)]
    if not rows:
        return notes
    by_id = {t["id"]: t for t in rows}
    # the same floor and ceiling the Takes desk shows — a bar that flagged
    # takes the desk calls clean would send the agent chasing ghosts
    try:
        floor = quiet_floor(rows)
        ceiling = rushed_ceiling(rows)
    except (TypeError, ValueError):
        floor, ceiling = None, None
    try:
        sup = superseded_takes(rows, [g for g in _list(takes.get("groups"))
                                      if isinstance(g, dict)])
    except (TypeError, ValueError, KeyError):
        sup = {}
    # Grouped BY TAKE, not by beat. One fumbled take often carries three
    # or four beats (T333 carries three of hmns's), and four sentences
    # naming the same take read as four problems when they are one
    # decision the designer owes a reason for.
    flagged: "dict[str, list]" = {}
    superseded: "dict[str, list]" = {}
    reason: "dict[str, str]" = {}
    for b in _beats(plan):
        t = by_id.get(_sid(b.get("take_id")))
        if t is None or str(b.get("flag_note") or "").strip():
            continue
        try:
            flags = take_flags(t, floor, ceiling)
        except (TypeError, ValueError):
            flags = []
        if flags:
            flagged.setdefault(t["id"], []).append(b.get("id"))
            reason[t["id"]] = "; ".join(flags)
        if t["id"] in sup:
            superseded.setdefault(t["id"], []).append(b.get("id"))
    # the note demands a reason, not a different take — a restart can be
    # the best line in the episode when the restart IS the joke
    for tid, bids in flagged.items():
        notes.append("take %s draws flags (%s) and is quoted by %s with "
                     "no flag_note — a flawed take can be the right one, "
                     "say why this one is"
                     % (tid, reason[tid], ", ".join(str(x) for x in bids)))
    for tid, bids in superseded.items():
        notes.append("take %s is superseded by %s and is quoted by %s "
                     "with no flag_note — the crew settled on the later "
                     "take, say why the earlier one wins here"
                     % (tid, sup[tid], ", ".join(str(x) for x in bids)))
    return notes


# -------------------------------------------------------- the public API

def cut_metrics(plan: "dict[str, Any]", takes: "dict | None",
                broll: "dict | None") -> "dict":
    """The cut's numbers. NEVER gates, never raises — this is the number
    surface a desk renders, and a malformed plan mid-surgery must render
    as zeros, not as a stack trace.

    median_shot_s is approximate the same way gear_change is: a beat's
    shots are its covers plus the face remainder, which under-counts a
    beat whose covers do not tile it — close enough to compare cuts,
    not close enough to quote.
    """
    plan = plan if isinstance(plan, dict) else {}
    beats = _beats(plan)
    chapters = _chapters(plan)
    durs = [_beat_dur(b) for b in beats]
    runtime = sum(durs)
    builds = sum(1 for b in beats if b.get("purpose") == "build")
    covers_n = sum(len(_covers(b)) for b in beats)
    changes = sum(_beat_changes(b) for b in beats)

    pace_declared: "list" = []
    pace_realized: "list" = []
    for ch in chapters:
        v = _num(ch.get("pace_cpm"))
        pace_declared.append(v if v is not None and v > 0 else None)
        members = [b for b in beats if b.get("chapter_id") == ch.get("id")]
        minutes = sum(_beat_dur(b) for b in members) / 60.0
        pace_realized.append(
            round(sum(_beat_changes(b) for b in members) / minutes, 1)
            if members and minutes > 0 else None)

    shots: "list[float]" = []
    for b, d in zip(beats, durs):
        if d <= 0:
            continue
        cds = [x for x in (_num(c.get("duration")) for c in _covers(b))
               if x is not None and x > 0]
        shots.extend(cds)
        face = d - sum(cds)
        if face > 0:
            shots.append(face)
    shots.sort()
    opens, _pays, _order = _declared_loops(plan)
    # gear_change indexes the beats' raw take_ids, so an unhashable id in
    # a mid-surgery plan raises inside it (2026-08-28) — and this surface
    # promised zeros, never a stack trace
    try:
        gear = schemas.gear_change(
            plan, takes if isinstance(takes, dict) else None)
    except (TypeError, ValueError, KeyError, AttributeError):
        gear = {"vo_mean_s": 0.0, "scene_mean_s": 0.0, "ratio": 0.0,
                "vo_beats": 0, "scene_beats": 0}
    return {
        "beats": len(beats),
        "chapters": len(chapters),
        "build_share": round(builds / float(len(beats)), 3) if beats else 0.0,
        "peaks": sum(1 for b in beats if b.get("peak") is True),
        "runtime_s": round(runtime, 1),
        "pace_declared": pace_declared,
        "pace_realized": pace_realized,
        "overall_cpm": round(changes / (runtime / 60.0), 1)
        if runtime > 0 else 0.0,
        "median_shot_s": round(shots[len(shots) // 2], 2) if shots else 0.0,
        "loops": len(opens),
        "covers": covers_n,
        "gear": gear,
    }


def cut_notes(plan: "dict[str, Any]", takes: "dict | None",
              broll: "dict | None",
              brief: "dict | None" = None) -> "list[str]":
    """The assembly bar, shaped like coverage_notes: ADVISORY as a
    function, required-empty by the job that dispatched the cut. Empty
    means pass.

    `brief` is story_brief.json's contents, or None. Nothing reads it
    today; it stays in the signature for the same reason script_notes
    keeps `origin` — the lane will bear on this bar (a documentary cut
    has no hook montage to preview) and every caller already holds the
    file, so the contract is set before the first rule needs it.
    """
    if not isinstance(plan, dict):
        return ["plan: not an object — nothing to grade"]
    takes = takes if isinstance(takes, dict) else None
    broll = broll if isinstance(broll, dict) else None
    notes: "list[str]" = []
    notes.extend(_pace_notes(plan))                 # C1
    notes.extend(_purpose_notes(plan))              # C2 a-b
    notes.extend(_loop_notes(plan))                 # C2 c-d
    notes.extend(_peak_notes(plan))                 # C3
    notes.extend(_hook_notes(plan))                 # C4
    notes.extend(_gear_notes(plan, takes))          # C5 — OFF until armed
    notes.extend(_thread_notes(plan))               # C6
    notes.extend(_variety_notes(plan, takes, broll))  # C7
    notes.extend(_quality_notes(plan, takes))       # C8
    return notes
