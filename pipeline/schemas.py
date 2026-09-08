"""Hand-rolled validators for the pipeline's JSON artifacts.

Same pattern as v1: each validate_*(data) returns a list of error strings —
empty list means valid. Stdlib only, no jsonschema dependency. Agents and
Python stages both run these before trusting a file; a failed validation is a
stop-the-line error, never a warning.

What breaks if this is wrong: a malformed artifact flows downstream and the
failure surfaces far from its cause (e.g. a bad take id only exploding in the
FCPXML writer).
"""
from __future__ import annotations

import math
import re
from typing import Any

FILE_KINDS = ("video", "audio")
FILE_CLASSES = ("speech", "broll")


def _req(errors: "list[str]", obj: "dict[str, Any]", key: str, typ: type, where: str) -> bool:
    """Require obj[key] to exist and be of type typ; record an error if not."""
    if key not in obj:
        errors.append("%s: missing '%s'" % (where, key))
        return False
    if not isinstance(obj[key], typ):
        errors.append("%s: '%s' should be %s, got %s"
                      % (where, key, typ.__name__, type(obj[key]).__name__))
        return False
    return True


def validate_catalog(data: "dict[str, Any]") -> "list[str]":
    """analysis/catalog.json — the probe + classification of every raw file."""
    errors: "list[str]" = []
    _req(errors, data, "slug", str, "catalog")
    if not _req(errors, data, "files", list, "catalog"):
        return errors
    if not data["files"]:
        errors.append("catalog: 'files' is empty — no footage found")
    names = set()
    for i, f in enumerate(data["files"]):
        where = "catalog.files[%d]" % i
        if not isinstance(f, dict):
            errors.append(where + ": not an object")
            continue
        _req(errors, f, "name", str, where)
        _req(errors, f, "path", str, where)
        _req(errors, f, "duration", (int, float), where)  # type: ignore[arg-type]
        if _req(errors, f, "kind", str, where) and f["kind"] not in FILE_KINDS:
            errors.append("%s: kind '%s' not in %s" % (where, f["kind"], FILE_KINDS))
        if _req(errors, f, "class", str, where) and f["class"] not in FILE_CLASSES:
            errors.append("%s: class '%s' not in %s" % (where, f["class"], FILE_CLASSES))
        if f.get("class") == "speech":
            if not f.get("words_file"):
                errors.append(where + ": speech file has no words_file")
        if isinstance(f.get("duration"), (int, float)) and f["duration"] <= 0:
            errors.append(where + ": duration must be > 0")
        n = f.get("name")
        if n in names:
            errors.append("%s: duplicate file name '%s'" % (where, n))
        names.add(n)
    return errors


def validate_takes(data: "dict[str, Any]") -> "list[str]":
    """analysis/takes.json — segmented takes + retake groups."""
    errors: "list[str]" = []
    _req(errors, data, "slug", str, "takes")
    if not _req(errors, data, "takes", list, "takes"):
        return errors
    ids = set()
    for i, t in enumerate(data["takes"]):
        where = "takes[%d]" % i
        if not isinstance(t, dict):
            errors.append(where + ": not an object")
            continue
        if _req(errors, t, "id", str, where):
            if t["id"] in ids:
                errors.append("%s: duplicate id '%s'" % (where, t["id"]))
            ids.add(t["id"])
        _req(errors, t, "file", str, where)
        _req(errors, t, "transcript", str, where)
        ok_s = _req(errors, t, "s", (int, float), where)  # type: ignore[arg-type]
        ok_e = _req(errors, t, "e", (int, float), where)  # type: ignore[arg-type]
        if ok_s and ok_e and t["e"] <= t["s"]:
            errors.append(where + ": e must be > s")
        for key in ("fillers", "n_words"):
            _req(errors, t, key, int, where)
        for key in ("restart", "complete"):
            _req(errors, t, key, bool, where)
    if _req(errors, data, "groups", list, "takes"):
        seen = set()
        for i, g in enumerate(data["groups"]):
            where = "groups[%d]" % i
            if not isinstance(g, dict):
                errors.append(where + ": not an object")
                continue
            _req(errors, g, "id", str, where)
            if _req(errors, g, "take_ids", list, where):
                for tid in g["take_ids"]:
                    if tid not in ids:
                        errors.append("%s: unknown take id '%s'" % (where, tid))
                    if tid in seen:
                        errors.append("%s: take '%s' in two groups" % (where, tid))
                    seen.add(tid)
        if seen != ids:
            errors.append("takes: %d takes missing from groups" % len(ids - seen))
    return errors


def validate_broll(data: "dict[str, Any]") -> "list[str]":
    """analysis/broll.json — the b-roll catalog with contact sheets."""
    errors: "list[str]" = []
    _req(errors, data, "slug", str, "broll")
    if not _req(errors, data, "clips", list, "broll"):
        return errors
    ids = set()
    for i, c in enumerate(data["clips"]):
        where = "broll.clips[%d]" % i
        if not isinstance(c, dict):
            errors.append(where + ": not an object")
            continue
        if _req(errors, c, "id", str, where):
            if c["id"] in ids:
                errors.append("%s: duplicate id '%s'" % (where, c["id"]))
            ids.add(c["id"])
        _req(errors, c, "file", str, where)
        _req(errors, c, "duration", (int, float), where)  # type: ignore[arg-type]
        _req(errors, c, "sheet", str, where)
        # `trim` is the Footage desk's usable window, carried beside
        # `duration` and ABSENT for a clip nobody trimmed — which is most
        # of them. Checked only when present, so every catalog written
        # before the field existed validates unchanged.
        if "trim" in c:
            _validate_trim(errors, c["trim"], where)
        # `framing` is written by the story-designer off the contact sheet
        # and carried across re-analysis by broll.catalog_broll. "" is the
        # untagged state the catalog writes for every clip, so it is valid;
        # a value that is neither empty nor a shot size is a typo the bar
        # would otherwise report as "untagged" and the writer would fix by
        # tagging it again (2026-09-08).
        if c.get("framing") not in (None, "") \
                and c.get("framing") not in SHOT_SIZES:
            errors.append("%s: framing '%s' not in %s"
                          % (where, c.get("framing"), SHOT_SIZES))
    return errors


def _validate_trim(errors: "list[str]", trim: "Any", where: str) -> None:
    """A clip's usable window: `{"in": float, "out": float}`, out after in.

    Both bounds are FILE-ABSOLUTE seconds — the same clock as a take's s/e
    and a cover's src_s — so a reader never has to know whether a number
    was measured before or after the trim.
    """
    if not isinstance(trim, dict):
        errors.append("%s: 'trim' should be dict, got %s"
                      % (where, type(trim).__name__))
        return
    for key in ("in", "out"):
        if not isinstance(trim.get(key), (int, float)) or isinstance(trim.get(key), bool):
            errors.append("%s: trim '%s' should be a number, got %s"
                          % (where, key, type(trim.get(key)).__name__))
            return
        # NaN and infinity are floats and would pass every test below:
        # both comparisons against NaN are False, so a NaN window reads as
        # valid and then makes every later `outside the trim` comparison
        # False too — the spine check silently degrades to the plain
        # duration bound and the trim stops meaning anything without
        # anyone being told (2026-08-28).
        if not math.isfinite(float(trim[key])):
            errors.append("%s: trim '%s' is %s — a window needs two real "
                          "seconds" % (where, key, trim[key]))
            return
    if float(trim["out"]) <= float(trim["in"]):
        errors.append("%s: trim out (%.2f) is not after in (%.2f) — a window "
                      "with nothing in it is not a trim, it is a deletion"
                      % (where, float(trim["out"]), float(trim["in"])))
    if float(trim["in"]) < 0:
        errors.append("%s: trim in (%.2f) is before the start of the file"
                      % (where, float(trim["in"])))


BEAT_PURPOSES = ("hook", "stakes", "build", "payoff", "button",
                 "chapter_open", "chapter_close")
FORMATS = ("youtube_short", "instagram_reel", "youtube_long")
TRANSITIONS = ("cut", "dissolve")

# The editor's cut vocabulary (Caleb, 2026-08-23). `transition_in` above stays
# the FRAME-BOUNDARY treatment -- what happens in the seam. `technique` is the
# editorial intent, and most of these need no new timeline construct at all:
#
#   hard          the spine does this by existing -- the default
#   jump          segments of ONE take with time removed between them
#   cutaway       b-roll over continuing audio -- a V2 <video> child (built)
#   cross_cut     alternation between two threads -- BEAT ORDER, not a seam
#   montage       a run of short beats -- a beat group, not a seam
#   match         shapes rhyme across the cut -- a SHOT CHOICE
#   cut_on_action the trim lands inside a movement -- a TRIM CHOICE
#   smash         abrupt tonal jolt, usually carried by a sound not a construct
#   j_cut         audio leads picture -> set audio_lead on THIS beat
#   l_cut         audio trails picture -> set audio_tail on this beat
#
# Only j_cut and l_cut need a construct the writer did not already emit:
# a connected <audio lane="-1"> child, verified against Resolve 21.0.4.5 on
# 2026-08-23 (docs/resolve-findings.md). Recording the technique matters even
# where it changes no XML -- it is how the story-designer's intent survives
# into QC, and how a reviewer can tell a jump cut from a botched splice.
CUT_TECHNIQUES = ("hard", "jump", "cutaway", "cross_cut", "montage", "match",
                  "cut_on_action", "smash", "j_cut", "l_cut")

# A split edit longer than this stops reading as a J/L cut and starts sounding
# like a mistake -- the viewer hunts for the offscreen speaker.
MAX_SPLIT_SEC = 3.0
MAX_HOOK_SEC = 15.0


COVER_MIN_S = 1.8        # below this a cutaway cannot be read
COVER_MAX_RATIO = 0.6    # an on-camera beat stays an on-camera beat
COVER_LANDING = 0.2      # the last fifth belongs to the face
# The lifted ceiling for a beat whose every cover is tag-matched (Caleb,
# 2026-08-28: T11 and T7 both rejected, "allow for extra b-roll if
# relevant by tags"). NOT unbounded: 0.85 is the act-scoped coverage
# ceiling the Rober wiring already names, so the number has a precedent
# rather than being invented here, and it keeps an on-camera beat at
# least a sixth face. The COUNT cap lifts entirely when the tags earn it;
# this ratio is the backstop that stops a beat becoming pure b-roll.
COVER_MAX_RATIO_TAGGED = 0.85

# The b-roll grammar's justifications, in the brief's order. A cover's
# `why` must LEAD with one of these words — the fifth, `process`, came
# from the Beau Miles study (2026-08-24): the first four are all defined
# against a spoken line, so footage of the work advancing had no legal
# reason to exist and R1 obliged an editor to DELETE it.
COVER_WHYS = ("establish", "illustrate", "foretell", "bridge", "process")

# Shot size, for the variety rule. Lives HERE and not in cutbar.py for the
# same reason `kind` lives on the take: a vocabulary with two homes drifts,
# and this one is read by the b-roll catalog, the validator and the bar
# (2026-09-08). `cutbar.SHOT_SIZES` is an alias of this tuple.
SHOT_SIZES = ("wide", "medium", "close", "detail")


def why_kind(why: "Any") -> "str | None":
    """The justification a `why` claims, or None if it names none.

    Pure, and forgiving of format: the briefs' worked examples use a
    colon (`illustrate: the donut awning`) and editors in the field have
    written a dash (`illustrate - the donut awning`). Both are the same
    claim, and a checker that accepted one and not the other would be
    grading punctuation. Only the leading word is read — everything
    after it is the clause a human judges.
    """
    head = str(why or "").strip().lower().split()
    if not head:
        return None
    word = "".join(ch for ch in head[0] if ch.isalpha())
    return word if word in COVER_WHYS else None


# A beat's kind is its TAKE's kind — never re-derived from a filename. A
# beat with no take is `picture`: pure coverage with no line under it, which
# is a real shape (Caleb, 2026-08-28). VO may also be recorded in post, so
# this must be read at the point of use rather than frozen into the plan —
# a beat becomes `vo` the moment its recording lands and it points at one.
BEAT_KIND_PICTURE = "picture"


def _take_index(takes: "dict | None") -> "dict":
    """{id: take} from a takes.json payload, or {} when not supplied."""
    if not takes:
        return {}
    rows = takes.get("takes", takes) if isinstance(takes, dict) else takes
    return {r["id"]: r for r in rows if isinstance(r, dict) and "id" in r}


def take_kind(take: "dict | None") -> str:
    """A take's kind, tolerating takes.json written before the field."""
    if not take:
        return BEAT_KIND_PICTURE
    kind = take.get("kind")
    if kind:
        return kind
    from .takes import kind_of_file          # the one prefix reader
    return kind_of_file(take.get("file"))


def beat_kind(beat: "dict", take_by_id: "dict | None") -> str:
    """What this beat IS. `picture` when it carries no take."""
    tid = (beat or {}).get("take_id")
    if not tid or not take_by_id:
        return BEAT_KIND_PICTURE
    return take_kind(take_by_id.get(tid))


def _clip_tags(clip: "dict | None") -> "set":
    """A clip's tags, the agent's and Caleb's together.

    `broll.catalog_broll` keeps them in two fields on purpose — merging
    them into one list would let a description pass silently drop a
    hand-typed keyword — so any reader asking "what is this clip about"
    has to union them.
    """
    out = set()
    for key in ("tags", "manual_tags"):
        for t in (clip or {}).get(key) or []:
            t = str(t).strip().lower()
            if t:
                out.add(t)
    return out


def _tag_matched(cover: "dict", clip: "dict | None") -> bool:
    """True when the cover's `why` NAMES one of its clip's tags.

    "Relevant by tags" has to mean the tag did work. Intersecting a
    clip's tags with words in the beat's transcript would pass on
    coincidence — a clip tagged "butterfly" over any line that happens to
    say butterfly — and coincidence is exactly what a bombardment looks
    like from the inside. Requiring the writer to name the tag in the why
    it was already obliged to write costs an honest cover nothing and
    cannot be hit by accident.
    """
    tags = _clip_tags(clip)
    if not tags:
        return False
    why = str(cover.get("why", "")).lower()
    return any(re.search(r"\b%s\b" % re.escape(t), why) for t in tags)


def coverage_notes(plan: "dict[str, Any]",
                   takes: "dict | None" = None,
                   broll: "dict | None" = None) -> "list[str]":
    """The b-roll craft rules, checked mechanically (2026-08-24 — the
    crooise cut put five 1.1s postcards over the hook). ADVISORY, not part
    of validate_edit_plan: existing plans must not brick surgery writes.
    The coverage job requires this list empty; the desk may show it.

    Checks: sub-COVER_MIN_S covers; beat coverage past COVER_MAX_RATIO;
    a cover inside the landing (last COVER_LANDING of the beat); more
    than 3 covers on one beat; any cover on a `peak` beat; a missing
    `why`, or one naming no justification from COVER_WHYS. VO-covered
    beats (vo_* takes) are exempt from the ratio and landing rules —
    there the b-roll IS the picture.

    `process` earns NO exemption of its own (2026-08-24). Inside a beat
    anchored to a spoken take the landing still belongs to the face, and
    an exemption a cover could grant itself by naming it is not a bar.

    TAGS LIFT TWO OF THESE, and only two (Caleb, 2026-08-28 — taste T11
    and T7 both rejected, in his words "allow for extra b-roll if
    relevant by tags"). When EVERY cover on a beat names one of its
    clip's tags in its why, the three-cover cap lifts entirely and the
    ratio ceiling rises to COVER_MAX_RATIO_TAGGED. Every, not any: one
    unjustified cover in a pile is still what a bombardment is made of.

    Never lifted, whatever the tags say: a `peak` beat stays untouchable
    (the one rule six of the seven film studies converged on), the
    landing still belongs to the face, COVER_MIN_S still applies, and a
    cover still owes a why that leads with a justification.
    """
    notes: "list[str]" = []
    clip_by_id = {c["id"]: c for c in (broll or {}).get("clips", [])
                  if isinstance(c, dict) and isinstance(c.get("id"), str)}
    for b in plan.get("beats", []):
        covers = b.get("broll") or []
        if not covers:
            continue
        # Without a catalog nothing can be tag-matched, so the caps stand
        # exactly as they did — the lift is opt-in on real data, and the
        # two existing callers that pass no broll are unaffected.
        unmatched = [c for c in covers
                     if not _tag_matched(c, clip_by_id.get(c.get("clip_id")))]
        tagged = bool(clip_by_id) and not unmatched
        trim = b.get("trim") or {}
        dur = float(trim.get("e", 0)) - float(trim.get("s", 0))
        # WAS `take_id.startswith("vo_")`, which no take id can satisfy —
        # ids are minted T01, T02 and the prefix lives on `file`. The
        # exemption was unreachable, so every VO beat was told it "covers
        # the landing" and jobs.py failed the job on it (2026-08-28).
        is_vo = beat_kind(b, _take_index(takes)) == "vo"
        if b.get("peak") and covers:
            notes.append("%s: a peak beat is covered — the face delivers"
                         % b["id"])
        if len(covers) > 3 and not is_vo and not tagged:
            note = ("%s: %d covers on one beat — that is a bombardment"
                    % (b["id"], len(covers)))
            # NAME the cover that broke the match. Without this the lift
            # is invisible machinery: a writer who tagged three of four
            # sees the same sentence as one who tagged none, and cannot
            # tell a rule that is working from a rule that is broken.
            if clip_by_id and len(unmatched) < len(covers):
                note += ("; %d of them name a tag, %s do not — say which "
                         "tag each cover is here for and the cap lifts"
                         % (len(covers) - len(unmatched),
                            ", ".join(str(c.get("clip_id"))
                                      for c in unmatched[:3])))
            notes.append(note)
        total = 0.0
        for c in covers:
            d = float(c.get("duration", 0))
            total += d
            if d < COVER_MIN_S:
                notes.append("%s: %s runs %.1fs — under %.1fs a cutaway "
                             "cannot be read"
                             % (b["id"], c.get("clip_id"), d, COVER_MIN_S))
            why = str(c.get("why", "")).strip()
            if not why:
                notes.append("%s: %s has no why — a cover that cannot "
                             "say its purpose has none"
                             % (b["id"], c.get("clip_id")))
            elif why_kind(why) is None:
                # a why that names no justification is a preference with
                # a sentence in front of it; R1 used to be the reviewer's
                # judgment call, and this is the arithmetic half of it
                notes.append("%s: %s says %r — a why must LEAD with one "
                             "of %s"
                             % (b["id"], c.get("clip_id"), why[:40],
                                "/".join(COVER_WHYS)))
            if dur > 0 and not is_vo:
                end = float(c.get("at", 0)) + d
                if end > dur * (1 - COVER_LANDING) + 0.05:
                    notes.append("%s: %s covers the landing — the last "
                                 "fifth belongs to the face"
                                 % (b["id"], c.get("clip_id")))
        ceiling = COVER_MAX_RATIO_TAGGED if tagged else COVER_MAX_RATIO
        if dur > 0 and not is_vo and total / dur > ceiling + 0.01:
            note = ("%s: %.0f%% covered — past %.0f%% an on-camera beat "
                    "stops being one"
                    % (b["id"], 100 * total / dur, 100 * ceiling))
            if clip_by_id and unmatched and len(unmatched) < len(covers):
                note += ("; the ceiling would be %.0f%% if %s named a tag"
                         % (100 * COVER_MAX_RATIO_TAGGED,
                            ", ".join(str(c.get("clip_id"))
                                      for c in unmatched[:3])))
            notes.append(note)
    return notes


# Yes Theory's gear change, measured. That film runs 18.8 cuts/min overall
# -- within 2% of Mark Rober -- which kills cut rate as the thing that
# separates these films. What separates them is TEXTURE: the 19.3% of
# runtime that is scripted VO carries 35% of all the cuts, 34.2 cuts/min
# against 15.2 everywhere else, ~1.8s mean shot against ~4.0s.
GEAR_VO_REF_S = 1.8        # their VO mean shot, for reference only
GEAR_SCENE_REF_S = 4.0     # their scene mean shot, for reference only


def gear_change(plan: "dict[str, Any]",
                takes: "dict | None" = None) -> "dict":
    """Mean shot length on VO beats vs scene beats (2026-08-27).

    S5 says "a chapter that is one texture end to end is a flat chapter"
    and nothing measured it, though the edit plan already holds every
    number needed. A flat episode is visible here as the two means
    collapsing toward each other.

    APPROXIMATE, deliberately. On a VO beat the b-roll IS the picture
    (the teleprompter take can never ship), so its shots are its covers.
    On a scene beat the shots are the face plus each cutaway. That
    under-counts a beat whose covers do not tile it exactly, which is
    most of them -- close enough to compare two textures, not close
    enough to quote as a cuts/min figure.

    Returns {vo_mean_s, scene_mean_s, ratio, vo_beats, scene_beats}.
    `ratio` is scene/vo: high means the gear change is there, near 1.0
    means the episode runs one texture end to end. There is deliberately
    NO threshold here and no note anywhere -- `coverage_notes` is
    required empty by the coverage job, and shipping an unmeasured number
    into a gating list turns a green pipeline red on work that was fine.

    MEASURED ON OUR OWN CUTS, 2026-08-27 -- and the answer was that there
    is nothing to calibrate against yet. All four existing edit plans
    (hmns, allure, and both _compare_ cuts) contain ZERO `vo_` beats:

        hmns             scene 5.62s, 0 VO beats, 82 scene beats
        allure           scene 5.42s, 0 VO beats, 34 scene beats
        _compare_room    scene 7.02s, 0 VO beats
        _compare_oneshot scene 6.50s, 0 VO beats

    They all predate the VO-led format (2026-08-24), so every cut we have
    ever made runs ONE texture end to end -- exactly the flat chapter S5
    warns about, at feature length. Two things follow: our scene beats run
    5.4-7.0s against Yes Theory's 4.0s, and the ratio is undefined rather
    than bad. Set a threshold from the first cut that actually has a VO
    half; until then this reports and gates nothing.
    """
    _idx = _take_index(takes)
    vo_s = vo_n = scene_s = scene_n = 0.0
    vo_beats = scene_beats = 0
    for b in plan.get("beats", []) or []:
        if not isinstance(b, dict):
            continue
        trim = b.get("trim") or {}
        try:
            dur = float(trim.get("e", 0)) - float(trim.get("s", 0))
        except (TypeError, ValueError):
            continue
        if dur <= 0:
            continue
        covers = [c for c in (b.get("broll") or []) if isinstance(c, dict)]
        # Same dead branch as the coverage exemption: no take id can
        # start with `vo_`. The counts above were right only because every
        # project measured is genuinely all-oncamera — they could never
        # have changed once a VO-led cut existed (2026-08-28).
        if beat_kind(b, _idx) == "vo":
            vo_beats += 1
            for c in covers:
                try:
                    d = float(c.get("duration", 0))
                except (TypeError, ValueError):
                    continue
                if d > 0:
                    vo_s += d
                    vo_n += 1
        else:
            scene_beats += 1
            scene_s += dur
            scene_n += 1 + len(covers)
    vo_mean = (vo_s / vo_n) if vo_n else 0.0
    scene_mean = (scene_s / scene_n) if scene_n else 0.0
    return {"vo_mean_s": round(vo_mean, 2),
            "scene_mean_s": round(scene_mean, 2),
            "ratio": round(scene_mean / vo_mean, 2) if vo_mean else 0.0,
            "vo_beats": vo_beats, "scene_beats": scene_beats}


# A beat whose picture is a CLIP rather than a take. Caleb, 2026-08-28: a
# beat may have no take at all — either a stretch of pure picture with no
# line under it, or b-roll carried by its own sound, which is the spine of
# a whole direction when nobody is narrating (six of golf-testing's eleven
# sections were exactly that, and no cut could express them).
#
# `audio` must be opted INTO. A cover is emitted as a picture-only <video>
# precisely because b-roll audio leaking over narration is a known hazard
# (timeline.py's docstring: "museum crowd noise!"), so silence stays the
# default and natural sound is a decision the plan states out loud.
def _validate_spine(errors: "list[str]", spine: "Any", clip_by_id: "dict",
                    where: str) -> None:
    if not isinstance(spine, dict):
        errors.append("%s: 'spine' should be dict, got %s"
                      % (where, type(spine).__name__))
        return
    cid = spine.get("clip_id")
    clip = clip_by_id.get(cid)
    if clip is None:
        errors.append("%s: spine names unknown clip '%s'" % (where, cid))
    try:
        s = float(spine.get("src_s", 0.0))
        e = float(spine.get("src_e", 0.0))
    except (TypeError, ValueError):
        errors.append("%s: spine src_s/src_e must be numbers" % where)
        return
    if e <= s:
        errors.append("%s: spine src_e (%.2f) must be after src_s (%.2f)"
                      % (where, e, s))
    elif clip is not None:
        dur = float(clip.get("duration") or 0.0)
        # A trimmed clip is only usable INSIDE its window. `duration` still
        # names the whole file on disk — every src_s ever written is in
        # that clock (broll.py) — so the window is the tighter bound, not a
        # replacement one, and a clip with no trim is checked exactly as it
        # was before the field existed.
        lo = hi = None
        trim = clip.get("trim")
        if isinstance(trim, dict):
            try:
                lo, hi = float(trim["in"]), float(trim["out"])
            except (KeyError, TypeError, ValueError):
                lo = hi = None
        outside_trim = (lo is not None and hi > lo
                        and (s < lo - 0.001 or e > hi + 0.001))
        if outside_trim:
            errors.append("%s: spine runs %.2f-%.2fs but clip '%s' is trimmed "
                          "to %.2f-%.2fs — move the window inside the trim, or "
                          "widen the trim on the Footage desk"
                          % (where, s, e, cid, lo, hi))
        # Still checked when the trim passed: a hand-edited window can
        # claim more than the file holds, and the file is the truth.
        if not outside_trim and dur and e > dur + 0.001:
            errors.append("%s: spine runs to %.2fs but clip '%s' is %.2fs"
                          % (where, e, cid, dur))
    if "audio" in spine and not isinstance(spine["audio"], bool):
        errors.append("%s: spine 'audio' should be bool, got %s"
                      % (where, type(spine["audio"]).__name__))


# A gap this long at a trim boundary is a clean cut on its own, whatever
# the punctuation says. Same number as `ingest.MIN_SILENCE_GAP_SEC`, which
# is what the dead-space cutter calls a silence — quoted rather than
# imported because schemas takes data and never reads a file, and a cycle
# through ingest would be a worse price than a duplicated constant.
CLEAN_PAUSE_SEC = 0.6

# The longest silence a beat may hold on either side of its take's
# words. Measured on hmns (2026-09-08): the whole 82-beat cut holds
# silence on three beats, the largest 1.94s — the reach for the camera
# that ends the episode. Three seconds is comfortably past every real
# one and nowhere near a mis-binding, which misses by minutes.
MAX_HOLD_SEC = 3.0


def take_window(take: "dict", takes: "list") -> "tuple":
    """How far a beat on this take may reach: (earliest, latest).

    A TAKE'S BOUNDS ARE WHERE THE WORDS ARE. They come from whisper, so
    they end on the last syllable — and a beat routinely wants the
    silence on either side of that. hmns holds three of them on purpose,
    each with Caleb's own note attached: the kids stay on camera 1.6s
    after "It's fantastic" (shot-T331), the sign-off starts 0.6s before
    "And" in the gap (shot-T374), and the final beat keeps the 2s reach
    for the camera after the last word (shot-T374-2). The assembler
    delivers all three: it uses the full trim and pads slightly beyond
    it, so those seconds are on screen in the shipped episode.

    The old rule refused every one of them, which made a cut that
    renders correctly, that Caleb reviewed beat by beat, and that has
    already shipped, fail its own validator — and `plan_beats` refuses
    to assemble on a validation error, so hmns could not be rebuilt at
    all until this changed (2026-09-08).

    TWO BOUNDS, and both are needed. The neighbours: a beat owns the
    silence around its take, out to where the next take's words begin
    and back to where the previous one's end, on the same source file.
    It may never contain a word from another take, which is what the
    original rule was really protecting. And MAX_HOLD_SEC, because on
    the first or last take of a file there is no neighbour at all — and
    an unbounded side would have let hmns's shot-T374 pass while naming
    a take on a 4.9-second file and trimming 236.40-240.81 of it. A hold
    is a breath, a reaction or a gesture; past a few seconds the plan
    should be saying so with a wordless picture beat, which the schema
    already has.
    """
    lo = max(0.0, float(take["s"]) - MAX_HOLD_SEC)
    hi = float(take["e"]) + MAX_HOLD_SEC
    for o in takes:
        if o is take or o.get("file") != take.get("file"):
            continue
        if o["e"] <= take["s"] + 0.01:
            lo = max(lo, float(o["e"]))
        elif o["s"] >= take["e"] - 0.01:
            hi = min(hi, float(o["s"]))
    return (lo, hi)


def validate_edit_plan(plan: "dict[str, Any]", takes: "dict[str, Any]",
                       broll: "dict[str, Any]",
                       words: "Any | None" = None) -> "list[str]":
    """edit_plan.json — the story-designer's output, cross-checked against
    takes.json and broll.json so the plan can only reference real material.

    `words` is optional and absent-tolerant: a mapping from a take's file
    name to that file's word timings (`ingest.words_by_file(slug)`).
    Given it, the sentence check reads which words are really inside a
    trim; without it, it falls back to interpolating across the take,
    which assumes every word takes the same time and produced must-fix
    errors on correct beats (2026-09-08).

    The storytelling rules enforced here are the brand's non-negotiables:
    the first beat is a hook and stays under MAX_HOOK_SEC; a payoff beat
    exists (the loop the hook opens must close); at most one take per retake
    group is used (never two attempts of the same line).
    """
    errors: "list[str]" = []
    take_by_id = {t["id"]: t for t in takes.get("takes", [])}
    group_of = {}
    for g in takes.get("groups", []):
        for tid in g["take_ids"]:
            group_of[tid] = g["id"]
    broll_ids = {c["id"] for c in broll.get("clips", [])}
    clip_by_id = {c["id"]: c for c in broll.get("clips", [])}

    _req(errors, plan, "slug", str, "plan")
    if _req(errors, plan, "format", str, "plan") and plan["format"] not in FORMATS:
        errors.append("plan: format '%s' not in %s" % (plan["format"], FORMATS))
    if _req(errors, plan, "theme", dict, "plan"):
        for key in ("problem", "promise", "payoff"):
            _req(errors, plan["theme"], key, str, "plan.theme")
    if not _req(errors, plan, "beats", list, "plan") or not plan["beats"]:
        errors.append("plan: no beats")
        return errors

    # Long-form videos are organized into chapters (one per museum hall, say).
    # Chapters are optional so short-form plans stay valid unchanged.
    chapter_ids = set()
    for i, ch in enumerate(plan.get("chapters", [])):
        where = "chapters[%d]" % i
        if not isinstance(ch, dict):
            errors.append(where + ": not an object")
            continue
        if _req(errors, ch, "id", str, where):
            if ch["id"] in chapter_ids:
                errors.append("%s: duplicate chapter id '%s'" % (where, ch["id"]))
            chapter_ids.add(ch["id"])
        _req(errors, ch, "title", str, where)
        # The pace ladder cutbar grades (C1). Absent-tolerant on purpose:
        # every plan written before the field existed must still validate,
        # so the schema only says what a well-formed one looks like and
        # `cutbar.cut_notes` is what asks for it at all (2026-09-08).
        if "pace_cpm" in ch:
            v = ch["pace_cpm"]
            if isinstance(v, bool) or not isinstance(v, (int, float)) \
                    or v <= 0:
                errors.append("%s: pace_cpm must be a positive number of "
                              "cuts per minute" % where)

    # Declared threads (the chronology escape hatch) and the loop ledger.
    # SHAPE ONLY, for the same reason coverage_notes is advisory: whether a
    # thread earns its exception, or a loop pays in order, is craft, and
    # craft lives in cutbar. An undeclared thread id on a beat is therefore
    # NOT an error here -- cutbar reads it and asks for its why.
    for i, t in enumerate(plan.get("threads") or []):
        where = "threads[%d]" % i
        if not isinstance(t, dict):
            errors.append(where + ": not an object")
            continue
        _req(errors, t, "id", str, where)
        _req(errors, t, "why", str, where)
    for i, lp in enumerate(plan.get("loops") or []):
        where = "loops[%d]" % i
        if not isinstance(lp, dict):
            errors.append(where + ": not an object")
            continue
        _req(errors, lp, "id", str, where)

    used_groups: "dict[str, str]" = {}
    # Beats were the ONE id space here without a uniqueness check
    # (chapters, takes, broll, cards and overlays all had one), and
    # ten artifacts key on a beat id — review verdicts, captions,
    # cards, sfx cues, conform ops, trash, proxies. A duplicate does
    # not orphan anything; it silently re-points the second beat's
    # history at the first. Added 2026-08-28.
    beat_ids = set()
    killed = {k.get("take_id") for k in plan.get("kill_list", [])}
    for i, b in enumerate(plan["beats"]):
        where = "beats[%d]" % i
        if not isinstance(b, dict):
            errors.append(where + ": not an object")
            continue
        if _req(errors, b, "id", str, where):
            if b["id"] in beat_ids:
                errors.append("%s: duplicate beat id '%s'"
                              % (where, b["id"]))
            beat_ids.add(b["id"])
        if _req(errors, b, "purpose", str, where) and b["purpose"] not in BEAT_PURPOSES:
            errors.append("%s: purpose '%s' not in %s" % (where, b["purpose"], BEAT_PURPOSES))
        # A beat has a TAKE (speech) or a SPINE (picture). Requiring
        # take_id unconditionally is what made "a beat may have no take"
        # forbidden rather than merely unimplemented (2026-08-28).
        if b.get("spine") is not None and not b.get("take_id"):
            _validate_spine(errors, b["spine"], clip_by_id, where)
        elif _req(errors, b, "take_id", str, where):
            tid = b["take_id"]
            t = take_by_id.get(tid)
            if t is None:
                errors.append("%s: unknown take '%s'" % (where, tid))
            else:
                if tid in killed:
                    errors.append("%s: take '%s' is on the kill list" % (where, tid))
                # screened out on the Takes desk BEFORE the cut existed —
                # the kill_list above is the designer's own judgement, this
                # is Caleb's, and it outranks it (2026-08-24)
                if t.get("screened_out"):
                    errors.append("%s: take '%s' was screened out — %s"
                                  % (where, tid,
                                     t.get("screen_reason")
                                     or "no reason recorded"))
                gid = group_of.get(tid)
                if gid and gid in used_groups and used_groups[gid] != tid:
                    errors.append("%s: group %s already used via take %s — one take per retake group"
                                  % (where, gid, used_groups[gid]))
                if gid:
                    used_groups[gid] = tid
                trim = b.get("trim")
                if trim is not None:
                    if not isinstance(trim, dict) or "s" not in trim or "e" not in trim:
                        errors.append(where + ": trim needs s and e")
                    elif not trim["s"] < trim["e"]:
                        errors.append("%s: trim %.2f-%.2f is empty or backwards"
                                      % (where, trim["s"], trim["e"]))
                    else:
                        # The take's bounds are its WORDS; the beat may hold
                        # the silence around them, out to the neighbouring
                        # takes. See take_window.
                        lo, hi = take_window(t, takes.get("takes", []))
                        if trim["s"] < lo - 0.01 or trim["e"] > hi + 0.01:
                            errors.append(
                                "%s: trim %.2f-%.2f outside take %s's window "
                                "%.2f-%.2f on %s — a beat holds its take's "
                                "words plus the silence around them, never "
                                "another take's"
                                % (where, trim["s"], trim["e"], tid, lo, hi,
                                   t.get("file", "its file")))
        for j, br in enumerate(b.get("broll", [])):
            bw = "%s.broll[%d]" % (where, j)
            if not isinstance(br, dict):
                errors.append(bw + ": not an object")
                continue
            if br.get("clip_id") not in broll_ids:
                errors.append("%s: unknown b-roll clip '%s'" % (bw, br.get("clip_id")))
            for key in ("at", "duration"):
                if not isinstance(br.get(key), (int, float)):
                    errors.append("%s: missing numeric '%s'" % (bw, key))
        tr = b.get("transition_in", "cut")
        if tr not in TRANSITIONS:
            errors.append("%s: transition_in '%s' not in %s" % (where, tr, TRANSITIONS))
        tech = b.get("technique", "hard")
        if tech not in CUT_TECHNIQUES:
            errors.append("%s: technique '%s' not in %s" % (where, tech, CUT_TECHNIQUES))
        # A split edit is a NUMBER of seconds, not a flag: the writer needs to
        # know how far the audio runs past its picture to place the connected
        # <audio> child. Naming the technique without it emits nothing.
        for key, tech_name in (("audio_lead", "j_cut"), ("audio_tail", "l_cut")):
            if key in b:
                v = b[key]
                if isinstance(v, bool) or not isinstance(v, (int, float)) or v <= 0:
                    errors.append("%s: %s must be a positive number of seconds"
                                  % (where, key))
                elif v > MAX_SPLIT_SEC:
                    errors.append("%s: %s of %.1fs exceeds the %.1fs maximum"
                                  % (where, key, v, MAX_SPLIT_SEC))
            elif tech == tech_name:
                errors.append("%s: technique '%s' needs %s (seconds)"
                              % (where, tech_name, key))
        # A technique that names a cut the beat does not actually contain is
        # worse than no technique at all: QC and the reviewer both read this
        # field to tell a deliberate edit from a botched one. Only the two
        # that leave evidence in the plan can be checked here -- match,
        # cut_on_action and smash are judgement, and cross_cut and montage
        # live in the beat ORDER, not in any single beat.
        if tech == "cutaway" and not b.get("broll"):
            errors.append("%s: technique 'cutaway' but the beat has no b-roll"
                          % where)
        if tech == "jump" and not b.get("cuts"):
            errors.append("%s: technique 'jump' but the beat has no cuts — a "
                          "jump cut is time removed from ONE take" % where)
        # --- the craft-bar's beat fields (2026-09-08) ---
        # Shape only, and absent-tolerant. cutbar decides whether a loop
        # pays in order or a flag_note earns its take; this only refuses a
        # field that is present and malformed, because a `pays_loop` of 3
        # or a `peak` of "yes" reads as absent to every grader and the
        # writer never learns why its declaration did nothing.
        for key in ("opens_loop", "pays_loop", "thread", "flag_note"):
            if key in b and not (isinstance(b[key], str) and b[key].strip()):
                errors.append("%s: %s must be a non-empty string"
                              % (where, key))
        if "peak" in b and not isinstance(b["peak"], bool):
            errors.append("%s: peak must be true or false" % where)
        for j, pn in enumerate(b.get("punches") or []):
            pw = "%s.punches[%d]" % (where, j)
            if not isinstance(pn, dict):
                errors.append(pw + ": not an object")
                continue
            for key in ("at", "zoom"):
                v = pn.get(key)
                if isinstance(v, bool) or not isinstance(v, (int, float)):
                    errors.append("%s: missing numeric '%s'" % (pw, key))
        # PEAK PROTECTION, first of three sites. A peak is the moment the
        # cut exists to deliver, and a zoom punch is the editor talking
        # over it. The other two are the card refusal in
        # validate_graphics_plan and the dead-space exemption in
        # timeline.plan_beats -- six of the seven film studies converged
        # on protecting these, which is more evidence than any other rule
        # in the program has behind it.
        if b.get("peak") is True and b.get("punches"):
            errors.append("%s: a peak beat carries %d punch-in(s) — the "
                          "moment plays, the edit does not comment on it"
                          % (where, len(b["punches"])))
        if chapter_ids and b.get("chapter_id") and b["chapter_id"] not in chapter_ids:
            errors.append("%s: unknown chapter '%s'" % (where, b["chapter_id"]))

    # --- editing-quality rules (added after the 4/10 review, 2026-08-19) ---

    # A VO take on screen is a teleprompter recording of Caleb reading --
    # its PICTURE must never ship. Any beat cut from a vo_* file needs
    # b-roll, and enough of it to cover what the beat keeps.
    for b in plan["beats"]:
        t = take_by_id.get(b.get("take_id"))
        if take_kind(t) != "vo":
            continue
        where = "beat %s" % b.get("id")
        if not b.get("broll"):
            errors.append("%s: cut from voice-over take %s with NO b-roll "
                          "-- the teleprompter picture would ship"
                          % (where, b["take_id"]))
            continue
        trim = b.get("trim") or {"s": t["s"], "e": t["e"]}
        kept = max(0.0, float(trim["e"]) - float(trim["s"]))
        covered = sum(float(br.get("duration", 0)) for br in b["broll"])
        if kept > 0 and covered < kept * 0.9:
            errors.append("%s: b-roll covers %.1fs of a %.1fs voice-over "
                          "beat -- the gap shows the teleprompter"
                          % (where, covered, kept))

    # A b-roll clip may appear ONCE in the whole video. Reused cutaways read
    # as filler and viewers notice the second time even when they can't say
    # why. 150 placements over 111 clips meant ~39 repeats.
    seen_clips: "dict[str, str]" = {}
    for b in plan["beats"]:
        for br in b.get("broll", []):
            cid = br.get("clip_id")
            if cid in seen_clips:
                errors.append("beat %s: b-roll %s already used in beat %s — one use per clip"
                              % (b.get("id"), cid, seen_clips[cid]))
            else:
                seen_clips[cid] = b.get("id")

    # The edit runs in shoot order. Museum days have a natural arc, and
    # jumping around reads as random. Exceptions: the intro (everything before
    # the first chapter_open may flash forward) and beats explicitly marked
    # `"foreshadow": true`, which must carry a `foreshadow_note` saying what
    # they set up.
    import re as _re

    def shoot_key(b):
        t = take_by_id.get(b.get("take_id"))
        if not t:
            return None
        m = _re.search(r"DJI_(\d{14})", t["file"])
        return (m.group(1), t["s"]) if m else None

    intro_chapter = plan.get("chapters", [{}])[0].get("id") if plan.get("chapters") else None
    prev_key, prev_id = None, None
    for b in plan["beats"]:
        if b.get("chapter_id") == intro_chapter or b.get("purpose") == "hook":
            continue  # the intro may flash forward freely
        if b.get("foreshadow"):
            if not b.get("foreshadow_note"):
                errors.append("beat %s: foreshadow beats need a foreshadow_note" % b.get("id"))
            continue
        key = shoot_key(b)
        if key and prev_key and key < prev_key:
            errors.append("beat %s: jumps backward in the day (before %s) — keep the edit "
                          "linear, or mark it foreshadow with a note" % (b.get("id"), prev_id))
        if key:
            prev_key, prev_id = key, b.get("id")

    # Explicit in-beat cuts (bad audio, flubs) must stay inside the trim.
    for b in plan["beats"]:
        t = take_by_id.get(b.get("take_id"))
        if not t:
            continue
        trim = b.get("trim") or {"s": t["s"], "e": t["e"]}
        for j, c in enumerate(b.get("cuts", [])):
            if not (isinstance(c, dict) and "s" in c and "e" in c):
                errors.append("beat %s: cuts[%d] needs s and e" % (b.get("id"), j))
            elif not (trim["s"] - 0.01 <= c["s"] < c["e"] <= trim["e"] + 0.01):
                errors.append("beat %s: cuts[%d] %.2f-%.2f outside trim %.2f-%.2f"
                              % (b.get("id"), j, c["s"], c["e"], trim["s"], trim["e"]))

    # No beat may cut mid-sentence (Caleb, 2026-08-19). The take's transcript
    # is checked at both trim boundaries: the last word inside the trim must
    # close a sentence, and the first word must open one (start of take, or
    # preceded by a sentence-closing word). Intentional partial lines —
    # a reaction fragment, an interrupted joke — carry `"fragment": true`.
    _terminal = (".", "!", "?", "…", '."', '!"', '?"', ",”", ".”")

    def _beat_sentence_errors(b) -> "list[str]":
        t = take_by_id.get(b.get("take_id"))
        if not t or b.get("fragment"):
            return []
        trim = b.get("trim") or {"s": t["s"], "e": t["e"]}
        toks = t.get("transcript", "").split()
        if not toks:
            return []
        errs = []

        # THE REAL TIMINGS FIRST. whisper wrote them; `takes.json` keeps
        # only the transcript string, so this check used to interpolate
        # word positions across the take — which assumes a constant
        # speaking rate. On the shipped hmns plan it landed on 'Check'
        # where the real last word is 'before.' and on 'if' where the
        # real first word is 'What', and each wrong guess was a MUST-FIX
        # on a correct beat. A must-fix blocks the assemble, so a
        # rounding error froze an episode.
        rows = words.get(t.get("file")) if words is not None else None
        if rows:
            inside = [r for r in rows
                      if r.get("s", 0) >= trim["s"] - 0.05
                      and r.get("e", 0) <= trim["e"] + 0.05]
            if inside:
                first_i, last_i = rows.index(inside[0]), rows.index(inside[-1])
                # A CUT IS CLEAN IF IT LANDS IN A SILENCE, whatever the
                # punctuation says. whisper writes commas where a speaker
                # simply stopped: hmns's shot-T316 starts after a 5.26
                # SECOND pause and was flagged for starting "mid-sentence"
                # after "Yeah,". Speech has utterance boundaries that
                # punctuation misses, and the rest of the pipeline already
                # reasons in pauses (ingest.MIN_SILENCE_GAP_SEC). Both
                # real findings on the shipped plan have a 0.00s gap, so
                # this removes the noise without softening the signal.
                # Caleb's call, 2026-09-08.
                last = str(inside[-1].get("w", "")).rstrip()
                tail_gap = (rows[last_i + 1].get("s", 0) - inside[-1].get("e", 0)
                            if last_i + 1 < len(rows) else None)
                if (not last.endswith(_terminal)
                        and tail_gap is not None
                        and tail_gap < CLEAN_PAUSE_SEC):
                    errs.append(
                        "beat %s: ends mid-sentence on %r with no pause after "
                        "it — extend the trim to the sentence end or mark "
                        "fragment:true" % (b.get("id"), last))
                if first_i > 0:
                    prev = str(rows[first_i - 1].get("w", "")).rstrip()
                    head_gap = inside[0].get("s", 0) - rows[first_i - 1].get("e", 0)
                    if (not prev.endswith(_terminal)
                            and head_gap < CLEAN_PAUSE_SEC):
                        errs.append(
                            "beat %s: starts mid-sentence on %r, %.2fs after "
                            "%r — pull the trim back to the sentence start or "
                            "mark fragment:true"
                            % (b.get("id"),
                               str(inside[0].get("w", "")).rstrip(),
                               head_gap, prev))
            return errs

        # Approximate word times across the take span to find boundary words.
        span = max(t["e"] - t["s"], 0.001)
        # last word fully inside the trim
        idx_end = min(len(toks) - 1,
                      int((trim["e"] - t["s"]) / span * len(toks)))
        last = toks[max(0, idx_end)].rstrip()
        if not last.endswith(_terminal):
            errs.append("beat %s: ends mid-sentence near %r — extend the trim to the "
                        "sentence end or mark fragment:true" % (b.get("id"), last))
        # CLAMPED AT BOTH ENDS, like idx_end above. `idx_start` only ever
        # had a floor, so a trim starting past its take's end indexed off
        # the transcript and the whole validator raised IndexError instead
        # of returning the errors it had already collected -- including the
        # "trim outside take bounds" error that names the very cause.
        #
        # That is not theoretical: it happens on the shipped hmns plan
        # today (beat BT19 names take T56, 0.00-2.07, and trims 4.14-7.30,
        # which is T57's window). A validator that dies on the input it
        # exists to reject cannot be a gate, and _run_editplan is about to
        # call this on untrusted agent output (2026-09-08).
        idx_start = min(len(toks) - 1,
                        max(0, int((trim["s"] - t["s"]) / span * len(toks))))
        if idx_start > 0 and not toks[idx_start - 1].rstrip().endswith(_terminal):
            errs.append("beat %s: starts mid-sentence near %r — pull the trim back to "
                        "the sentence start or mark fragment:true"
                        % (b.get("id"), toks[idx_start]))
        return errs

    for b in plan["beats"]:
        errors.extend(_beat_sentence_errors(b))

    first = plan["beats"][0]
    if first.get("purpose") != "hook":
        errors.append("plan: first beat must be the hook")
    else:
        t = take_by_id.get(first.get("take_id"))
        if t is not None:
            trim = first.get("trim") or {"s": t["s"], "e": t["e"]}
            if trim["e"] - trim["s"] > MAX_HOOK_SEC:
                errors.append("plan: hook beat runs %.1fs — cap is %.0fs"
                              % (trim["e"] - trim["s"], MAX_HOOK_SEC))
    purposes = [b.get("purpose") for b in plan["beats"]]
    if "payoff" not in purposes:
        errors.append("plan: no payoff beat — the curiosity loop never closes")
    return errors


# "meme" is the story role for the meme B-roll pack (gag clips the
# graphics-director may place between beats); the fine-grained screen is
# still named by kit_type, which is validated against RENDERERS below.
CARD_TYPES = ("hook_title", "section", "stat", "quote", "outro", "meme")
CARD_ANIMATIONS = ("slide_up", "slide_down", "fade")

# Copy fields the audience actually reads. Brand rules are checked on these.
COPY_FIELDS = ("kicker", "text", "subtext", "stat", "attribution", "speaker",
               "cta", "low", "high")


# Engagement screens that are meaningless without their options.
NEEDS_ROWS = {"quiz": "rows", "vote": "rows", "poll": "rows", "rank": "rows",
              "scoreboard": "entries", "this_that": "sides"}


def _brand_copy_errors(card: "dict[str, Any]", where: str) -> "list[str]":
    """The hard rules from brand/voice-and-tone.md, enforced not just written.

    **Emoji are allowed and encouraged anywhere** (Caleb, 2026-08-20) — they
    are the channel's playfulness, and the renderer gives every one its own
    drop-shadow so it sits on footage like the type around it. Nothing here
    checks for them. `brand/visual-identity.md` notes that they read best in
    the language lines rather than in wide-tracked structural caps, but that
    is guidance for a writer, not a gate.

    The exclamation rule stays: it comes from the design system's own voice
    section and Caleb's correction was specifically about emoji.
    """
    out = []
    for field in COPY_FIELDS:
        val = card.get(field)
        if not isinstance(val, str) or not val:
            continue
        if "!" in val:
            out.append("%s: %s contains an exclamation mark — "
                       "brand/voice-and-tone.md forbids them" % (where, field))
    return out


def validate_graphics_plan(plan: "dict[str, Any]",
                           edit_plan: "dict[str, Any] | None" = None,
                           beat_lens: "dict | None" = None) -> "list[str]":
    """graphics_plan.json — the graphics-director's card list. When edit_plan
    is given, beat references are cross-checked too."""
    errors: "list[str]" = []
    _req(errors, plan, "slug", str, "graphics")
    if not _req(errors, plan, "cards", list, "graphics"):
        return errors
    beat_ids = {b["id"] for b in (edit_plan or {}).get("beats", [])}
    # PEAK PROTECTION, second of three sites (2026-09-08). Only knowable
    # when the cut is passed in, which is why it lives beside beat_ids.
    peak_beats = {b["id"] for b in (edit_plan or {}).get("beats", [])
                  if b.get("peak") is True}
    ids = set()
    for i, c in enumerate(plan["cards"]):
        where = "cards[%d]" % i
        if not isinstance(c, dict):
            errors.append(where + ": not an object")
            continue
        if _req(errors, c, "id", str, where):
            if c["id"] in ids:
                errors.append("%s: duplicate id '%s'" % (where, c["id"]))
            ids.add(c["id"])
        if _req(errors, c, "type", str, where) and c["type"] not in CARD_TYPES:
            errors.append("%s: type '%s' not in %s" % (where, c["type"], CARD_TYPES))
        _req(errors, c, "beat_id", str, where)
        # a card whose `at` overruns its beat is composited into NO proxy
        # (invisible in Review) while landing mid-NEXT-beat in Resolve —
        # the exact divergence proxies exist to prevent (review finding 11)
        if beat_lens and isinstance(c.get("at"), (int, float)):
            blen = beat_lens.get(c.get("beat_id"))
            if blen is not None and c["at"] > blen - 0.05:
                errors.append("%s: at %.2fs is past the end of %s (%.2fs) - "
                              "re-home the card to the beat it overlays"
                              % (where, c["at"], c.get("beat_id"), blen))
        if beat_ids and c.get("beat_id") not in beat_ids:
            errors.append("%s: unknown beat '%s'" % (where, c.get("beat_id")))
        if c.get("beat_id") in peak_beats:
            errors.append("%s: a card on peak beat %s — the reaction is "
                          "the product, and nothing shares the frame with "
                          "it" % (where, c.get("beat_id")))
        for key in ("at", "duration"):
            if not isinstance(c.get(key), (int, float)):
                errors.append("%s: missing numeric '%s'" % (where, key))
        if isinstance(c.get("duration"), (int, float)) and not 1.0 <= c["duration"] <= 15.0:
            errors.append("%s: duration %.1fs outside 1-15s" % (where, c["duration"]))
        # Chapter turns must be readable: >= 2.5s (Caleb, 2026-08-19). A
        # transition SWEEP gets a lower floor — it reveals and moves on
        # rather than holding a title, and the SemiFinal timeline trims
        # them to ~2.4s; syncing plan durations FROM the timeline must not
        # fail validation against the timeline's own cut.
        if not c.get("prebaked") and isinstance(c.get("duration"), (int, float)):
            kit = c.get("kit_type")
            if (kit == "chapter" or c.get("type") == "chapter") and c["duration"] < 2.5:
                errors.append("%s: chapter card '%s' holds %.1fs — minimum is 2.5s"
                              % (where, c.get("id"), c["duration"]))
            elif kit == "transition" and c["duration"] < 2.0:
                errors.append("%s: transition '%s' runs %.1fs — minimum is 2.0s"
                              % (where, c.get("id"), c["duration"]))
        if c.get("animation", "slide_up") not in CARD_ANIMATIONS:
            errors.append("%s: animation '%s' not in %s" % (where, c.get("animation"), CARD_ANIMATIONS))

        # kit_type must name a real screen. Previously unchecked, so a typo
        # survived validation and only blew up mid-bake, minutes later.
        kit = c.get("kit_type")
        if kit is not None:
            from .overlay_kit import RENDERERS
            if kit not in RENDERERS:
                errors.append("%s: kit_type '%s' is not a kit screen (%s)"
                              % (where, kit, ", ".join(sorted(RENDERERS))))
            elif kit in NEEDS_ROWS and not c.get(NEEDS_ROWS[kit]):
                errors.append("%s: kit_type '%s' needs a non-empty '%s'"
                              % (where, kit, NEEDS_ROWS[kit]))
        errors.extend(_brand_copy_errors(c, where))

        # Sizing multipliers: numeric and sane, or named. The renderer also
        # clamps, but a plan carrying "font_scale": "big" should fail HERE,
        # not render silently at 1.0.
        for fld in ("offset_x", "offset_y"):
            if fld in c:
                v = c[fld]
                if not isinstance(v, (int, float)) or not -600 <= v <= 600:
                    errors.append("%s: %s must be a number between -600 and "
                                  "600" % (where, fld))
        if "scrim" in c:
            v = c["scrim"]
            if not isinstance(v, (int, float)) or not 0 <= v <= 100:
                errors.append("%s: scrim must be a number between 0 and 100"
                              % where)
        for fld in ("font_scale", "card_scale"):
            if fld in c:
                v = c[fld]
                if not isinstance(v, (int, float)) or not 0.5 <= v <= 2.0:
                    errors.append("%s: %s must be a number between 0.5 and 2.0"
                                  % (where, fld))

        ctype = c.get("type")
        if ctype == "stat":
            _req(errors, c, "stat", str, where)
            _req(errors, c, "text", str, where)
        elif ctype in ("hook_title", "section", "outro", "quote"):
            _req(errors, c, "text", str, where)
        if ctype == "hook_title" and isinstance(c.get("text"), str) and len(c["text"].split()) > 9:
            errors.append(where + ": hook card text over 9 words — unreadable in a second")
    return errors


def validate_custom_overlays(data: "dict[str, Any]") -> "list[str]":
    """overlays_custom.json — the Overlays desk's own cards.

    Deliberately NOT validate_graphics_plan. A custom overlay is addressed by
    `kit_type` (a key of overlay_kit.RENDERERS) and carries no `type` and no
    `beat_id`, so the plan validator rejects every one of them — wiring that
    one in here would refuse every save instead of closing the gap.

    What actually fails at bake time is a kit_type the kit cannot render, so
    that is what this checks, against RENDERERS itself rather than a copy of
    its key list (CLAUDE.md: read the dict, don't trust a count in prose).
    """
    errors: "list[str]" = []
    if not _req(errors, data, "overlays", list, "custom"):
        return errors
    from .overlay_kit import RENDERERS
    ids = set()
    for i, o in enumerate(data["overlays"]):
        where = "overlays[%d]" % i
        if not isinstance(o, dict):
            errors.append(where + ": not an object")
            continue
        if _req(errors, o, "id", str, where):
            if o["id"] in ids:
                errors.append("%s: duplicate id '%s'" % (where, o["id"]))
            ids.add(o["id"])
        if _req(errors, o, "kit_type", str, where) \
                and o["kit_type"] not in RENDERERS:
            errors.append("%s: kit_type '%s' is not in the kit"
                          % (where, o["kit_type"]))
        # bool is an int subclass — a JSON `true` must not pass as a number
        for key, floor in (("duration", 0), ("at", -1)):
            if key in o:
                v = o[key]
                if isinstance(v, bool) or not isinstance(v, (int, float)) \
                        or v <= floor:
                    errors.append("%s: %s must be a number greater than %d"
                                  % (where, key, floor))
        if "beat_id" in o and not isinstance(o["beat_id"], str):
            errors.append("%s: beat_id should be str" % where)
    return errors


SPEAKING_WPM = 150  # est_s for a VO line = words / SPEAKING_WPM * 60

# The three kinds of script section (2026-08-24). `oncamera` QUOTES a take
# that already exists — its text is a transcript and editing it would lie.
# `vo` and `desk` are both WRITTEN to be performed later, and the difference
# between them is whether the picture ships:
#
#   vo   -> a teleprompter recording of Caleb reading. validate_edit_plan
#           HARD-BLOCKS its picture (>=90% b-roll required, "the teleprompter
#           picture would ship"), so every vo line owes a `visual`.
#   desk -> a real-camera performance at his desk. The face IS the shot, so
#           it must NOT inherit any of the vo_ exemptions. This is why the
#           two get different filename prefixes rather than one flag: four
#           independent rules key off a `vo_` prefix, and a desk recording
#           landing on the wrong side of them would be forbidden from ever
#           appearing on screen.
# --- the two axes a project is created on (2026-08-25) --------------------
#
# ORIGIN is how the video is MADE: `footage` is a day out, shot first and
# scripted from what the day gave us; `script` is documentary/educational,
# written first from a subject and performed later.
#
# DELIVERY is where it SHIPS, and it is one choice rather than separate
# length and orientation dials because those two never actually vary
# independently here: long-form is 16:9 and shorts are vertical. A 16:9
# short or a long vertical would be two more workflows to design and test
# for videos Caleb does not make.
#
# Both were previously GUESSED, and late: orientation came from
# analysis/timeline_map.json, which only exists after assemble, so captions,
# card baking, the Resolve canvas and the review proxies all learned the
# shape of the video two-thirds of the way through making it.
ORIGINS = ("footage", "script")
DELIVERIES = ("long", "short")
SHORTS_SOURCES = ("standalone", "derived")

# What each delivery implies. `instagram_reel` is deliberately absent: a Reel
# is the same vertical master with different copy, so the Reel/Short split
# belongs to the publish stage, not to the canvas.
DELIVERY_SHAPE = {
    "long":  {"orientation": "landscape", "format": "youtube_long",
              "target_minutes": 8.0, "chapters": 3},
    "short": {"orientation": "portrait", "format": "youtube_short",
              "target_minutes": 0.75, "chapters": 1},
}

# The narration dial's starting point per combination. A DIAL, not a
# doctrine — Caleb sets it per episode; these are only what a fresh project
# opens on. A desk documentary is carried by narration and to-camera; a
# short cut from a day out is carried by the moment itself.
VO_SHARE_DEFAULT = {
    ("footage", "long"): 0.60,
    ("footage", "short"): 0.25,
    ("script", "long"): 0.35,
    ("script", "short"): 0.85,
}


def delivery_shape(delivery: "str | None") -> "dict":
    """Orientation, edit-plan format and opening budget for a delivery.
    Unknown or absent reads as `long` — every project that predates this
    field is a 16:9 episode."""
    return dict(DELIVERY_SHAPE.get(str(delivery or "long"),
                                   DELIVERY_SHAPE["long"]))


def format_defaults(origin: "str | None", delivery: "str | None") -> "dict":
    """The whole opening brief implied by the two choices at creation, so a
    project is never formatless — nothing downstream has to guess a shape
    from an artifact that does not exist yet."""
    o = str(origin or "footage")
    d = str(delivery or "long")
    shape = delivery_shape(d)
    shape["vo_share"] = VO_SHARE_DEFAULT.get((o, d), 0.60)
    return shape


SECTION_KINDS = ("oncamera", "vo", "desk")

# Where a `visual` comes from. The sourcing stage buys against this, so a
# wrong guess costs Caleb money and an hour — prefer `library` whenever the
# footage we already have honestly covers the line.
VISUAL_FROM = ("library", "stock", "archival", "graphic", "shoot")

# Section ids look like CH2.S3 — chapter, section. They are IDENTITY, not
# ordering: recordings match to sections by FILENAME (vo_CH2-S3_r1_t1.webm),
# so renumbering orphans real recordings and REUSING a retired id makes an
# old take read "recorded" for words the script no longer says. Both fail
# silently until the cut, which is why reuse is validated rather than
# trusted.
_SECTION_ID_RE = re.compile(r"^CH\d+\.S\d+$")


def _kill_reason(takes: "dict[str, Any] | None", tid: str) -> str:
    for t in (takes or {}).get("takes", []):
        if t.get("id") == tid:
            return str(t.get("screen_reason") or "no reason recorded")
    return "no reason recorded"


def validate_script(script: "dict[str, Any]",
                    takes: "dict[str, Any] | None" = None) -> "list[str]":
    """script.json — the timed script between an approved direction and the
    cut (Caleb, 2026-08-23). Three kinds of section: `oncamera` quotes a real
    take; `vo` is a line Caleb records LATER over b-roll — the lane that
    lets a thin shoot fill a long brief; `desk` is written to be PERFORMED to
    camera later, the spine of a script-led episode (2026-08-24). The
    chapter's est sum must land near its target or the budget the pitch
    promised is fiction.

    This function is STRUCTURE AND IDENTITY only. The craft rules live in
    `script_notes` — same split as `validate_edit_plan` / `coverage_notes`,
    and for the same reason: an existing script must not become invalid
    when the bar gets sharper. What is enforced HERE is the class of
    mistake that corrupts silently rather than reading badly.
    """
    errors: "list[str]" = []
    _req(errors, script, "slug", str, "script")
    # A script-led episode has no pitch to reference — there was no footage
    # to pitch from. option_id stays required in the footage lane, where an
    # unattributed script means nobody can tell which approved direction it
    # claims to be.
    if str(script.get("origin") or "footage") != "script":
        _req(errors, script, "option_id", str, "script")
    if not _req(errors, script, "chapters", list, "script"):
        return errors
    origin = str(script.get("origin") or "footage")
    if origin not in ("footage", "script"):
        errors.append("script: origin must be 'footage' or 'script'")
    # Ids are permanent. A retired id handed back out makes an old recording
    # read "recorded" for words that no longer exist — silent until the cut.
    retired = script.get("retired_ids") or []
    if not isinstance(retired, list):
        errors.append("script: retired_ids must be a list")
        retired = []
    retired_set = {str(r) for r in retired}
    take_ids = {t["id"] for t in (takes or {}).get("takes", [])}
    # A take Caleb screened out must not be quotable. The Takes desk's
    # kill is the decision; this is what makes it BITE — a brief can be
    # ignored, a validator cannot (2026-08-24).
    killed = {t["id"] for t in (takes or {}).get("takes", [])
              if t.get("screened_out")}
    seen_sections = set()
    for i, ch in enumerate(script["chapters"]):
        cw = "chapters[%d]" % i
        if not isinstance(ch, dict):
            errors.append(cw + ": not an object")
            continue
        _req(errors, ch, "id", str, cw)
        _req(errors, ch, "title", str, cw)
        has_target = _req(errors, ch, "target_s", (int, float), cw)
        if not _req(errors, ch, "sections", list, cw):
            continue
        est_sum = 0.0
        for j, sec in enumerate(ch["sections"]):
            sw = "%s.sections[%d]" % (cw, j)
            if not isinstance(sec, dict):
                errors.append(sw + ": not an object")
                continue
            if _req(errors, sec, "id", str, sw):
                if sec["id"] in seen_sections:
                    errors.append("%s: duplicate section id '%s'" % (sw, sec["id"]))
                seen_sections.add(sec["id"])
                if sec["id"] in retired_set:
                    errors.append(
                        "%s: id '%s' is retired and was reused — a recording "
                        "named for it would read as this line's take"
                        % (sw, sec["id"]))
                if not _SECTION_ID_RE.match(str(sec["id"])):
                    errors.append(
                        "%s: id '%s' is not CH<n>.S<n> — the recording "
                        "filename is built from it" % (sw, sec["id"]))
            kind = sec.get("kind")
            if kind not in SECTION_KINDS:
                errors.append("%s: kind must be one of %s"
                              % (sw, ", ".join(SECTION_KINDS)))
            # rev bumps whenever the text changes, and rides in the recording
            # filename so a rewritten line reads "not recorded" instead of
            # showing a green tick for words it no longer says. Absent means
            # rev 1 — every script written before 2026-08-24 is rev 1.
            if "rev" in sec:
                rev = sec.get("rev")
                if isinstance(rev, bool) or not isinstance(rev, int) or rev < 1:
                    errors.append("%s: rev must be an integer of 1 or more"
                                  % sw)
            # Engineered silence is a real section (Caleb, 2026-08-27).
            # S7 has told the writer for a while that "a `visual` and no
            # words is a legitimate section", and this line refused to let
            # them write one -- peak protection survived six studies and
            # the format would not hold it. A wordless `vo` with a picture
            # is the shape; anything else with no words is still a hole.
            # A `desk` piece with no words is nothing, and a quote with no
            # words is not a quote.
            if not str(sec.get("text") or "").strip():
                if kind == "vo" and isinstance(sec.get("visual"), dict):
                    pass
                else:
                    errors.append("%s: empty text — a section with nothing "
                                  "to say is a hole in the episode. Silence "
                                  "is legal as a `vo` section WITH a "
                                  "`visual`: there has to be something to "
                                  "look at" % sw)
            est = sec.get("est_s")
            if isinstance(est, bool) or not isinstance(est, (int, float)) or est <= 0:
                errors.append("%s: est_s must be a positive number" % sw)
            else:
                est_sum += float(est)
            if kind == "oncamera":
                tid = sec.get("take_id")
                if take_ids and tid not in take_ids:
                    errors.append("%s: unknown take '%s'" % (sw, tid))
                elif tid in killed:
                    errors.append("%s: take '%s' was screened out — %s"
                                  % (sw, tid, _kill_reason(takes, tid)))
        # the pitch promised target_s; the script must land near it
        if has_target and est_sum > 0:
            target = float(ch["target_s"])
            if target > 0 and abs(est_sum - target) / target > 0.25:
                errors.append(
                    "%s: sections estimate %.0fs against a %.0fs target — "
                    "off by more than 25%%; rebudget the chapter or the "
                    "script" % (cw, est_sum, target))
    errors.extend(_loop_ledger_errors(script, seen_sections))
    return errors


def _loop_ledger_errors(script: "dict[str, Any]",
                        section_ids: "set") -> "list[str]":
    """`loops[]` — the hook's promises, written down (2026-08-27).

    STRUCTURE ONLY, and only when the field is there. An absent ledger is
    silent here and picked up as a NOTE by `script_notes`, because the
    house rule is that an existing script must not become invalid when the
    bar gets sharper. What IS an error is a ledger that points at a
    section id which does not exist: that is the same silent-corruption
    class as a reused section id -- it reads fine and means nothing, and
    nobody finds out until the loop goes unpaid in the cut.
    """
    errors: "list[str]" = []
    loops = script.get("loops")
    if loops is None:
        return errors
    if not isinstance(loops, list):
        return ["script: loops must be a list"]
    seen: "set" = set()
    for i, lp in enumerate(loops):
        lw = "loops[%d]" % i
        if not isinstance(lp, dict):
            errors.append(lw + ": not an object")
            continue
        lid = lp.get("id")
        if not isinstance(lid, str) or not lid.strip():
            errors.append(lw + ": id must be a non-empty string")
        elif lid in seen:
            errors.append("%s: duplicate loop id '%s'" % (lw, lid))
        else:
            seen.add(lid)
        for field in ("opens", "pays"):
            ref = lp.get(field)
            if not isinstance(ref, str) or not ref.strip():
                errors.append("%s: %s must name a section" % (lw, field))
            elif section_ids and ref not in section_ids:
                errors.append("%s: %s names '%s', which is not a section in "
                              "this script" % (lw, field, ref))
    return errors


VO_TARGET_DEFAULT = 0.60   # the dial's default; per-episode in story_brief
VO_TOLERANCE = 0.10        # how far the script may drift from the target


def vo_share(script: "dict[str, Any]") -> float:
    """Share of the script's estimated RUNNING TIME carried by voice-over.

    Time, not section count: three one-line VO sections beside one long
    on-camera answer is not a VO-led episode, and counting sections would
    say it was.

    A WORDLESS `vo` section -- engineered silence -- counts toward the
    running time and NOT toward the voice-over (2026-08-27). Fifteen
    seconds of held picture is not fifteen seconds of narration, and
    counting it as such would read the episode as VO-heavy and push the
    writer to cut real narration to get back under the dial. The dial
    would be lying in the exact direction that destroys the beat it was
    protecting.
    """
    vo = total = 0.0
    for ch in script.get("chapters", []):
        for sec in (ch or {}).get("sections", []) or []:
            try:
                est = float(sec.get("est_s") or 0)
            except (TypeError, ValueError):
                continue
            if est <= 0:
                continue
            total += est
            if sec.get("kind") == "vo" and str(sec.get("text") or "").strip():
                vo += est
    return (vo / total) if total else 0.0


# S1's banned vocabulary, straight out of brand/voice-and-tone.md's "Words
# and tics to avoid". Checked here rather than trusted to the brief because
# a document nobody reads is not a standard — the brand doc says so itself.
SCRIPT_BANNED = ("insane", "mind-blowing", "mind blowing", "literally",
                 "you won't believe", "you wont believe")
MAX_SENTENCE_W = 32        # S3: past this, Caleb has to breathe mid-clause
MEDIAN_SENTENCE_W = 18     # S3: the house shape is short declaratives


def _sentences(text: str) -> "list[str]":
    """Split spoken prose into sentences. Deliberately crude — this counts
    length, it does not parse grammar, and an abbreviation splitting early
    costs nothing here."""
    out, cur = [], []
    for tok in str(text or "").replace("\n", " ").split():
        cur.append(tok)
        if tok.endswith((".", "!", "?", "…")):
            out.append(" ".join(cur))
            cur = []
    if cur:
        out.append(" ".join(cur))
    return [s for s in out if s.strip()]


def _spoken_sections(script: "dict[str, Any]") -> "list[dict]":
    """Sections whose words we WROTE — vo and desk. `oncamera` is a quote of
    what was actually said on the day, so holding it to a writing standard
    would be grading a transcript."""
    return [sec for ch in script.get("chapters", [])
            for sec in (ch or {}).get("sections", []) or []
            if sec.get("kind") in ("vo", "desk")]


def script_notes(script: "dict[str, Any]",
                 target: "float | None" = None,
                 origin: "str | None" = None) -> "list[str]":
    """The script's craft bar, shaped like `coverage_notes`: ADVISORY as a
    function, required-empty by the job that dispatched the writer.

    The format is VO-led as of 2026-08-24, and the share is a per-episode
    dial rather than a doctrine — so this checks the script against THAT
    episode's target, not against a constant.

    **Nothing here checks person** (Caleb, 2026-08-27). "I" is not banned
    in either lane — Caleb hosts, and on camera Alma and Sofia speak in the
    first person too. `origin` stays in the signature because the lane still
    decides the ninth room and the door meter, and every caller passes it.

    Only `vo` and `desk` text is judged. An `oncamera` section is a QUOTE,
    and marking a real person's real sentence as too long would be asking
    the past to rewrite itself.
    """
    notes: "list[str]" = []
    want = VO_TARGET_DEFAULT if target is None else float(target)
    got = vo_share(script)
    if abs(got - want) > VO_TOLERANCE:
        notes.append("script is %.0f%% voice-over against a %.0f%% target — "
                     "%s" % (got * 100, want * 100,
                             "write more narration" if got < want
                             else "give the ensemble more of the screen"))
    all_lens: "list[int]" = []
    for sec in _spoken_sections(script):
        sid = sec.get("id", "?")
        text = str(sec.get("text") or "")
        low = text.lower()
        # --- S2: a claim the audience cannot check and QC cannot trace ---
        if any(c.isdigit() for c in text) and not sec.get("source"):
            notes.append("%s: a narrated fact with no source — QC "
                         "cannot trace the claim" % sid)
        # --- S1: the voice, exactly ---
        if "!" in text:
            notes.append("%s: exclamation mark — the brand has no "
                         "exclamation marks" % sid)
        for word in SCRIPT_BANNED:
            if word in low:
                notes.append("%s: \"%s\" is on the banned list — label the "
                             "wonder less, show it more" % (sid, word))
        # NOTHING here checks person, in either lane, for any speaker
        # (Caleb, 2026-08-27). "I" is his in both written lanes, and on
        # camera Caleb, Alma and Sofia each say it when they give a take.
        # A check that reached a quote would be asking a real sentence
        # somebody really said to rewrite itself. "guys" went with it.
        # --- S3: sentence shape ---
        for s in _sentences(text):
            n = len(s.split())
            all_lens.append(n)
            if n > MAX_SENTENCE_W:
                notes.append("%s: a %d-word sentence — over %d words it "
                             "stops being speech" % (sid, n, MAX_SENTENCE_W))
        # --- S4: every vo line owes a picture ---
        if sec.get("kind") == "vo":
            vis = sec.get("visual")
            if not isinstance(vis, dict):
                notes.append("%s: a voice-over line with no `visual` — the "
                             "teleprompter picture cannot ship, so a line "
                             "with nothing to look at is a hole" % sid)
            else:
                if not str(vis.get("want") or "").strip():
                    notes.append("%s: visual.want is empty — name what the "
                                 "viewer is looking at" % sid)
                if why_kind(vis.get("why")) is None:
                    notes.append("%s: visual.why names no justification — "
                                 "lead with one of %s"
                                 % (sid, "/".join(COVER_WHYS)))
                if str(vis.get("from") or "") not in VISUAL_FROM:
                    notes.append("%s: visual.from must be one of %s — the "
                                 "sourcing stage buys against it"
                                 % (sid, "/".join(VISUAL_FROM)))
    if all_lens:
        mid = sorted(all_lens)[len(all_lens) // 2]
        if mid > MEDIAN_SENTENCE_W:
            notes.append("median sentence is %d words against a %d-word "
                         "house shape — short declaratives, a fragment to "
                         "land it" % (mid, MEDIAN_SENTENCE_W))
    notes.extend(loop_ledger_notes(script))
    return notes


# S6's ledger, checked. Mark Rober opens eight loops between 4:43 and 6:38
# and pays all eight IN THE SAME ORDER between 8:10 and 15:43, landing the
# climax at 72% of runtime rather than at the end.
LEDGER_MIN_CHAPTERS = 2    # a short has one loop, not a ledger
CLIMAX_AT = 0.70           # the last payment should not land before this


def loop_ledger_notes(script: "dict[str, Any]") -> "list[str]":
    """S6 as far as a machine can take it (2026-08-27).

    ADVISORY, like everything else in `script_notes`: "the payoff must
    always land" is the brand's one non-negotiable and until now it was
    the only rule with nothing behind it at all -- `validate_edit_plan`
    checks that *a* payoff beat exists and nothing checks that the
    promises the hook actually made were kept.

    What is NOT checked: the widening gap between opening and payment.
    That is taste, it stays in S6, and a number would only make it worse.
    """
    notes: "list[str]" = []
    chapters = script.get("chapters") or []
    order: "list[str]" = [str(sec.get("id"))
                          for ch in chapters
                          for sec in (ch or {}).get("sections", []) or []]
    at = {sid: i for i, sid in enumerate(order)}
    loops = script.get("loops")
    if not isinstance(loops, list) or not loops:
        if len(chapters) >= LEDGER_MIN_CHAPTERS:
            notes.append("no loop ledger — the promises the hook makes are "
                         "not written down, so nothing can tell whether they "
                         "were paid. Declare `loops` (S6)")
        return notes
    paid: "list[tuple]" = []
    for lp in loops:
        if not isinstance(lp, dict):
            continue
        lid = str(lp.get("id") or "?")
        o, y = at.get(str(lp.get("opens"))), at.get(str(lp.get("pays")))
        if o is None or y is None:
            continue        # a dangling ref is validate_script's error
        if y <= o:
            notes.append("%s: paid at or before it opens — the viewer cannot "
                         "remember a loop that had not been opened yet" % lid)
            continue
        paid.append((o, y, lid))
    paid.sort()
    for (o1, y1, id1), (o2, y2, id2) in zip(paid, paid[1:]):
        if y2 < y1:
            notes.append("%s pays before %s, which opened first — pay them "
                         "in the order they were opened (S6)" % (id2, id1))
    if paid and order:
        last = max(y for _, y, _ in paid)
        where = (last + 1) / float(len(order))
        if where < CLIMAX_AT:
            notes.append("the last loop closes %.0f%% of the way in — the "
                         "climax should sit late (Rober lands his at 72%%), "
                         "and the run after it has nothing left to pay"
                         % (where * 100))
    return notes


# The script's collaboration loop (2026-08-24). Same vocabulary as the pitch
# loop's story_feedback.json, because it is the same shape of decision:
#   answers   — Caleb answered the open questions; write/revise from them
#   direction — a fresh pass steered by his notes
#   approve   — LOCK it; no further draft may overwrite
SCRIPT_DECISIONS = ("answers", "direction", "approve")
MAX_INTERVIEW_Q = 8   # round 0. More than this spends the scarcest thing here
MAX_DRAFT_Q = 6       # every draft after


def validate_script_questions(doc: "dict[str, Any]",
                              feedback: "dict[str, Any] | None" = None) -> "list[str]":
    """script_questions.json — the director's open interview.

    The cap is the point. Attention is the scarcest resource in this
    pipeline, and a writer that asks twenty questions has moved its own
    job onto Caleb. Every question also carries a DEFAULT, so skipping is
    legal and silence never blocks a draft.
    """
    errors: "list[str]" = []
    _req(errors, doc, "slug", str, "questions")
    stage = doc.get("stage")
    if stage not in ("interview", "draft"):
        errors.append("questions: stage must be 'interview' or 'draft'")
    if not _req(errors, doc, "questions", list, "questions"):
        return errors
    qs = doc["questions"]
    cap = MAX_INTERVIEW_Q if stage == "interview" else MAX_DRAFT_Q
    if len(qs) > cap:
        errors.append("questions: %d questions at stage '%s' — the cap is "
                      "%d; ask what you cannot decide yourself"
                      % (len(qs), stage, cap))
    # A question id that was ALREADY answered must not come back attached
    # to a different question. Answers accumulate by id across rounds, and
    # each draft writes a fresh questions file — so reusing "Q1" for a new
    # question makes it read as already answered, with an answer given to
    # something else entirely. Same class as the retired-section-id bug,
    # and silent in the same way. (The director numbers Q7.. on its own;
    # this is the rule stated rather than trusted.)
    answered = set()
    for r in (feedback or {}).get("rounds", []) or []:
        for qid, val in ((r or {}).get("answers") or {}).items():
            if str(val or "").strip():
                answered.add(str(qid))
    seen = set()
    for i, q in enumerate(qs):
        where = "questions[%d]" % i
        if not isinstance(q, dict):
            errors.append(where + ": not an object")
            continue
        if _req(errors, q, "id", str, where):
            if q["id"] in seen:
                errors.append("%s: duplicate question id '%s'"
                              % (where, q["id"]))
            if q["id"] in answered:
                errors.append(
                    "%s: id '%s' was already answered in an earlier round — "
                    "keep numbering upward so an old answer cannot attach "
                    "to a new question" % (where, q["id"]))
            seen.add(q["id"])
        if not str(q.get("ask") or "").strip():
            errors.append(where + ": empty ask")
        opts = q.get("options") or []
        if not isinstance(opts, list):
            errors.append(where + ": options must be a list")
            opts = []
        ids = set()
        for k, o in enumerate(opts):
            if not isinstance(o, dict):
                errors.append("%s.options[%d]: not an object" % (where, k))
                continue
            if _req(errors, o, "id", str, "%s.options[%d]" % (where, k)):
                ids.add(o["id"])
            if not str(o.get("label") or "").strip():
                errors.append("%s.options[%d]: empty label" % (where, k))
        # A default that names no option cannot run, so "skip it" would
        # silently become "block on it" — the one thing the cap exists to
        # prevent.
        dflt = q.get("default")
        if opts and dflt is not None and str(dflt) not in ids:
            errors.append("%s: default '%s' names no option" % (where, dflt))
        if not opts and q.get("required") and dflt is None:
            errors.append("%s: required, free-text, and no default — there "
                          "is no way for this question to not block" % where)
    return errors


def validate_script_feedback(doc: "dict[str, Any]") -> "list[str]":
    """script_feedback.json — Caleb's rounds. Mirrors story_feedback."""
    errors: "list[str]" = []
    if not _req(errors, doc, "rounds", list, "feedback"):
        return errors
    for i, r in enumerate(doc["rounds"]):
        where = "rounds[%d]" % i
        if not isinstance(r, dict):
            errors.append(where + ": not an object")
            continue
        if r.get("decision") not in SCRIPT_DECISIONS:
            errors.append("%s: decision must be one of %s"
                          % (where, ", ".join(SCRIPT_DECISIONS)))
        if "answers" in r and not isinstance(r["answers"], dict):
            errors.append(where + ": answers must be an object of qid -> answer")
    return errors


def open_questions(questions: "dict[str, Any] | None",
                   feedback: "dict[str, Any] | None") -> "list[str]":
    """Question ids still unanswered — REQUIRED ones are what gate a draft.

    Pure, so the desk and the job quote the same number. An answered
    question stays answered across later rounds: the answers dict
    accumulates, because re-asking something Caleb already settled is how
    a collaboration loop becomes a chore.
    """
    qs = (questions or {}).get("questions", []) or []
    answered: "set" = set()
    for r in (feedback or {}).get("rounds", []) or []:
        for qid, val in ((r or {}).get("answers") or {}).items():
            if str(val or "").strip():
                answered.add(str(qid))
    return [str(q.get("id")) for q in qs
            if isinstance(q, dict) and str(q.get("id")) not in answered]


def blocking_questions(questions: "dict[str, Any] | None",
                       feedback: "dict[str, Any] | None") -> "list[str]":
    """Unanswered questions that carry no default and are marked required.

    Only these stop a draft. Everything else runs on its default and the
    draft reports which defaults it used — the writer never idles waiting
    for an answer Caleb did not think was worth giving.
    """
    still = set(open_questions(questions, feedback))
    out = []
    for q in (questions or {}).get("questions", []) or []:
        if not isinstance(q, dict) or str(q.get("id")) not in still:
            continue
        if q.get("required") and q.get("default") is None:
            out.append(str(q.get("id")))
    return out


# A proposal offers to BUY something. These are the answers that mean we
# are no longer buying it — the overlay kit draws it, Caleb shoots it, or
# the library already holds it.
_NOT_SOURCED = ("graphic", "shoot", "library")


# A candidate used to be a SEARCH TERM: {query, source, license, note}.
# You cannot look at a search term, so approving one approved a guess --
# and its licence line was a prediction about what the search might turn
# up ("PD-US expected -- verify on the file page"), not a fact about a
# file. Caleb asked to see the picture first (2026-08-25), which only
# works if propose RESOLVES each candidate to a real item.
#
# `preview` and `video` are REMOTE urls, rendered by the browser straight
# from the source. Nothing is written to disk before approval, so the gate
# the propose/fetch split exists to protect is untouched: looking at a
# public thumbnail is browsing, not acquiring.
CANDIDATE_KINDS = ("image", "video")


def candidate_previewable(c: "dict[str, Any] | None") -> bool:
    """Whether the desk can show this candidate rather than describe it."""
    if not isinstance(c, dict):
        return False
    return bool(str(c.get("preview") or "").strip()
                or str(c.get("video") or "").strip())


def validate_candidates(round_: "dict[str, Any]") -> "list[str]":
    """A resolved proposal: every candidate names a real item.

    Kept advisory (the propose job requires it empty) rather than part of
    a hard validator, because rounds written before 2026-08-25 carry bare
    queries and must not become invalid.
    """
    errors: "list[str]" = []
    if round_.get("kind") != "source":
        return errors            # a requirement offers nothing to look at
    cands = round_.get("candidates") or []
    if not isinstance(cands, list) or not cands:
        return ["%s: a source proposal with no candidates"
                % round_.get("section_id", "?")]
    for i, c in enumerate(cands):
        where = "%s.candidates[%d]" % (round_.get("section_id", "?"), i)
        if not isinstance(c, dict):
            errors.append(where + ": not an object")
            continue
        if c.get("kind") not in CANDIDATE_KINDS:
            errors.append("%s: kind must be image or video" % where)
        if not str(c.get("page") or "").strip():
            errors.append("%s: no page url — the licence is stated there, "
                          "and it is what makes the claim checkable" % where)
        if not candidate_previewable(c):
            errors.append("%s: nothing to preview — resolve the search to a "
                          "real item and record its preview url" % where)
        if c.get("kind") == "video" and not str(c.get("video") or "").strip():
            errors.append("%s: a video candidate needs a playable url" % where)
        if not str(c.get("license") or "").strip():
            errors.append("%s: no licence — read it off the page rather "
                          "than predicting it" % where)
    return errors


def superseded_requests(script: "dict[str, Any]",
                        requests: "dict[str, Any] | None") -> "list[int]":
    """Indices of open proposals the script has since moved past.

    A revision can turn "find me archival footage of this" into "draw it in
    the kit", and the proposal made against the OLD line stays sitting at
    `proposed`, indistinguishable from a live one. Approving it then spends
    money on the exact thing Caleb decided not to buy — which is what
    happened to CH2.S7 and CH2.S8 on the-pendulum-that-stopped
    (2026-08-25).

    Only `source` proposals can go stale this way: a `requirement` names
    work still owed whatever the section now says. Nothing is deleted —
    the caller re-labels, so the record of what was proposed survives.
    """
    want = {}
    for ch in (script or {}).get("chapters", []):
        for sec in (ch or {}).get("sections", []) or []:
            vis = sec.get("visual")
            want[str(sec.get("id"))] = (
                str((vis or {}).get("from") or "") if isinstance(vis, dict)
                else None)
    out = []
    for i, r in enumerate((requests or {}).get("rounds", []) or []):
        if not isinstance(r, dict) or r.get("status") != "proposed":
            continue
        if r.get("kind") != "source":
            continue
        sid = str(r.get("section_id") or "")
        if sid not in want or want[sid] in _NOT_SOURCED or not want[sid]:
            out.append(i)
    return out


def unproposed_sections(script: "dict[str, Any]",
                        requests: "dict[str, Any] | None") -> "list[str]":
    """Section ids that ask for a picture and have no live row.

    The inverse of `superseded_requests`, and the test for whether a
    sourcing run that wrote NOTHING was a correct no-op or a miss.

    The sourcer sits behind a human gate: rounds wait at `proposed` until
    they are approved, and it is built not to duplicate work already
    waiting on a verdict. So "the file did not change" is a legitimate
    outcome — but only when every section that wants a picture already has
    one. This is what tells the two apart.

    KIND IS IRRELEVANT HERE. A `desk` section is performed to camera, and
    people assume its face IS the shot — but it can still declare a
    cutaway, and one did: CH1.S2 on the oligarchy short wanted stock and
    no round ever proposed it, while all seven `vo` lines were covered
    (2026-08-26). What decides is `visual.from`, not the section's kind.

    A `superseded` row does not cover anything: it names a purchase the
    script has since moved past.
    """
    covered = set()
    for r in (requests or {}).get("rounds", []) or []:
        if not isinstance(r, dict):
            continue
        if r.get("status") == "superseded":
            continue
        sid = str(r.get("section_id") or "")
        if sid:
            covered.add(sid)
    out = []
    for ch in (script or {}).get("chapters", []) or []:
        for sec in (ch or {}).get("sections", []) or []:
            if not isinstance(sec, dict):
                continue
            vis = sec.get("visual")
            if not isinstance(vis, dict) or not str(vis.get("from") or "").strip():
                continue
            sid = str(sec.get("id") or "")
            if sid and sid not in covered:
                out.append(sid)
    return out


def coverage_budget(script: "dict[str, Any]",
                    broll: "dict[str, Any] | None" = None,
                    used_clip_ids: "set | frozenset | None" = None) -> "dict":
    """How many seconds of narration need covering, and what is in hand.

    Every VO second is a second with nobody on camera to cut to, so a
    VO-led cut needs covering footage of roughly its VO running time.
    Measured on HMNS (2026-08-24): 186 clips totalling 28.0 minutes —
    enough for about 28 minutes of narration under the once-per-clip
    rule, and no more. When a library is only just big enough the
    coverage editor cannot afford to delete anything, and "fewer,
    righter" dies by arithmetic rather than by choice.

    PURE, so the sourcing stage and the desk quote the same number.
    """
    vo_s = 0.0
    for ch in script.get("chapters", []):
        for sec in (ch or {}).get("sections", []) or []:
            if sec.get("kind") != "vo":
                continue
            try:
                vo_s += max(0.0, float(sec.get("est_s") or 0))
            except (TypeError, ValueError):
                continue
    used = used_clip_ids or frozenset()
    clips = (broll or {}).get("clips", []) or []
    avail = [c for c in clips if c.get("id") not in used]
    lib_s = 0.0
    for c in avail:
        try:
            lib_s += max(0.0, float(c.get("duration") or 0))
        except (TypeError, ValueError):
            continue
    # What the SCRIPT itself declared it needs (2026-08-24). A script-led
    # episode has no library to measure a shortfall against — dividing into
    # a library of zero says "everything is missing", which is true and
    # useless. The `visual.from` on each section says where its picture is
    # meant to come from, so the sourcing stage can propose against a brief
    # instead of against an absence.
    #
    # EVERY SECTION THAT DECLARES ONE, not just the vo lines. `vo_seconds`
    # above is rightly vo-only — it measures narration with nobody on
    # camera to cut to. This is a different question: what did the script
    # ASK FOR. A desk line is performed to camera and usually needs
    # nothing, but it can still declare a cutaway of its own, and one did:
    # CH1.S2 on the oligarchy short wanted stock, was invisible to this
    # total, and so was never proposed while all seven vo lines were
    # covered (2026-08-26). The sourcer proposes against this arithmetic,
    # so a picture missing from it is a picture nobody buys.
    declared: "dict[str, float]" = {k: 0.0 for k in VISUAL_FROM}
    for ch in script.get("chapters", []):
        for sec in (ch or {}).get("sections", []) or []:
            vis = sec.get("visual")
            if not isinstance(vis, dict):
                continue
            src = str(vis.get("from") or "")
            if src not in declared:
                continue
            try:
                declared[src] += max(0.0, float(sec.get("est_s") or 0))
            except (TypeError, ValueError):
                continue
    declared = {k: round(v, 1) for k, v in declared.items() if v > 0}
    return {"vo_seconds": round(vo_s, 1),
            "library_seconds": round(lib_s, 1),
            "library_clips": len(avail),
            "shortfall_seconds": round(max(0.0, vo_s - lib_s), 1),
            "ratio": round(lib_s / vo_s, 2) if vo_s else None,
            "declared_seconds": declared,
            "to_source_seconds": round(
                sum(v for k, v in declared.items() if k != "library"), 1)}


def validate_words(data: "list[Any]") -> "list[str]":
    """<file>.words.json — whisper word timings: [{"w","s","e"}, ...]."""
    errors: "list[str]" = []
    if not isinstance(data, list):
        return ["words: not a list"]
    prev_end = 0.0
    for i, w in enumerate(data):
        where = "words[%d]" % i
        if not isinstance(w, dict):
            errors.append(where + ": not an object")
            continue
        _req(errors, w, "w", str, where)
        ok_s = _req(errors, w, "s", (int, float), where)  # type: ignore[arg-type]
        ok_e = _req(errors, w, "e", (int, float), where)  # type: ignore[arg-type]
        if ok_s and ok_e:
            if w["e"] < w["s"]:
                errors.append(where + ": end before start")
            if w["s"] < prev_end - 0.5:  # whisper can jitter slightly; big regressions are real errors
                errors.append(where + ": starts %.2fs before previous word ends" % (prev_end - w["s"]))
            prev_end = max(prev_end, float(w["e"]))
    return errors


# --- the production board (team plan P1, 2026-08-24) ------------------------
# Append-only event log per episode (work/<slug>/production.json), ONE
# writer per event class: the ENGINE appends cost/checker_result/brake/
# reclaimed, the LEAD appends assigned/score/note/done/blocked, Caleb's
# reply box appends caleb_note, and TEAMMATE lifecycle events (claimed/
# artifact_submitted) are appended by the engine on the teammate's behalf
# — teammates never touch the file. Cards are fold_production(events):
# one pure function shared by the engine routes and the Studio desk.

RUBRIC_BAR = 4          # a line at or above this is clean
STALL_LINE_ROUNDS = 2   # same line below bar AND non-increasing
STALL_VECTOR_ROUNDS = 3  # min AND sum both non-increasing (noisier signal,
                         # looser window — Caleb's review, rev 3)
CLAIM_REAP_MIN = 30

EVENT_CLASS = {
    # engine-written: the outer dispatcher (cost, reclaimed) and the
    # engine's OWN checker/brake code invoked as a CLI verb — the lead
    # calls the verb but never authors these events
    "cost": "engine", "checker_result": "engine", "brake": "engine",
    "reclaimed": "engine", "calibration": "engine",
    # lead-written: the lead session is its teammates' only observer, so
    # lifecycle events are its to append — one writer, no contention
    "assigned": "lead", "score": "lead", "note": "lead",
    "done": "lead", "blocked": "lead", "stage": "lead",
    "claimed": "lead", "artifact_submitted": "lead",
    # Caleb's reply box (appended by the engine on his behalf)
    "caleb_note": "caleb",
}


def validate_production(doc: "dict[str, Any]") -> "list[str]":
    """Event shapes + the one-writer-per-class rule. A lead-class event
    claiming the engine writer (or vice versa) is refused — contention is
    prevented by construction, not by locks."""
    errors: "list[str]" = []
    if not isinstance(doc, dict) or not isinstance(doc.get("events"), list):
        return ["production: not an event document"]
    for i, e in enumerate(doc["events"]):
        where = "events[%d]" % i
        if not isinstance(e, dict):
            errors.append(where + ": not an object")
            continue
        etype = e.get("type")
        if etype not in EVENT_CLASS:
            errors.append("%s: unknown type %r" % (where, etype))
            continue
        if e.get("by") != EVENT_CLASS[etype]:
            errors.append("%s: %s events are %s-written, got by=%r"
                          % (where, etype, EVENT_CLASS[etype], e.get("by")))
        if not isinstance(e.get("ts"), (int, float)):
            errors.append(where + ": missing ts")
        if etype != "stage" and not e.get("task_id"):
            errors.append("%s: %s needs a task_id" % (where, etype))
        if etype == "score":
            if not e.get("line_id"):
                errors.append(where + ": score needs its rubric line_id")
            sc = e.get("score")
            if not isinstance(sc, (int, float)) or not 1 <= sc <= 5:
                errors.append(where + ": score must be 1-5")
            elif sc <= 3 and not str(e.get("quoted_artifact_line",
                                           "")).strip():
                errors.append("%s: a score of %d must quote the artifact "
                              "line that earned it" % (where, sc))
        if etype == "assigned" and not (e.get("craft") and e.get("title")):
            errors.append(where + ": assigned needs craft and title")
    return errors


def fold_production(events: "list") -> "dict":
    """events -> cards. THE view: engine routes and the Studio desk both
    render this fold, so they can never disagree about a card."""
    tasks: "dict[str, dict]" = {}
    stage = None
    for e in events:
        etype = e.get("type")
        if etype == "stage":
            stage = e.get("name")
            continue
        tid = e.get("task_id")
        if not tid:
            continue
        card = tasks.setdefault(tid, {
            "id": tid, "stage": stage, "craft": None, "title": None,
            "status": "open", "owner": None, "rounds": 0,
            "notes": [], "score_history": [], "cost": {
                "sessions": 0, "tokens": 0, "usd": 0.0, "ms": 0},
            "claimed_ts": None, "artifact": None,
            "brake": None, "checker": None,
        })
        if etype == "assigned":
            card.update(craft=e.get("craft"), title=e.get("title"),
                        stage=e.get("stage", stage), status="open")
        elif etype == "claimed":
            card.update(status="claimed", owner=e.get("owner"),
                        claimed_ts=e.get("ts"))
        elif etype == "reclaimed":
            card.update(status="open", owner=None, claimed_ts=None)
        elif etype == "artifact_submitted":
            card.update(status="in_review", artifact=e.get("artifact"))
            card["rounds"] += 1
        elif etype == "score":
            # scores land per round: the round index is rounds-1
            while len(card["score_history"]) < card["rounds"]:
                card["score_history"].append({})
            if card["rounds"] > 0:
                card["score_history"][card["rounds"] - 1][e["line_id"]] = \
                    e.get("score")
        elif etype in ("note", "caleb_note"):
            card["notes"].append({"from": e.get("by"),
                                  "text": e.get("text", ""),
                                  "taste_override": e.get("taste_override"),
                                  "ts": e.get("ts")})
            if etype == "note":
                card["status"] = "revising"
        elif etype == "done":
            card["status"] = "done"
        elif etype == "blocked":
            card["status"] = "blocked"
        elif etype == "brake":
            card.update(status="blocked", brake=e.get("reason"))
        elif etype == "checker_result":
            card["checker"] = {"name": e.get("name"),
                               "notes": e.get("notes", [])}
        elif etype == "cost":
            c = card["cost"]
            c["sessions"] += 1
            c["tokens"] += int(e.get("tokens", 0) or 0)
            c["usd"] += float(e.get("usd", 0) or 0)
            c["ms"] += int(e.get("ms", 0) or 0)
    return {"stage": stage, "tasks": tasks}


def stalled(card: "dict") -> "str | None":
    """The two structural brakes, exactly as locked in the plan:

    - same line_id below bar AND non-increasing across
      STALL_LINE_ROUNDS consecutive rounds (a converging line — 1 then 3
      — must NOT trip; the stuck 2,2 fires);
    - the score VECTOR non-improving across STALL_VECTOR_ROUNDS
      consecutive rounds, where non-improving is testable: min AND sum
      both non-increasing round over round.
    """
    hist = [h for h in card.get("score_history", []) if h]
    if len(hist) >= STALL_LINE_ROUNDS:
        window = hist[-STALL_LINE_ROUNDS:]
        for line in window[0]:
            scores = [h.get(line) for h in window]
            if any(s is None for s in scores):
                continue
            below = all(s < RUBRIC_BAR for s in scores)
            rising = any(b > a for a, b in zip(scores, scores[1:]))
            if below and not rising:
                return ("line %s below bar and not improving across %d "
                        "rounds" % (line, STALL_LINE_ROUNDS))
    if len(hist) >= STALL_VECTOR_ROUNDS:
        window = hist[-STALL_VECTOR_ROUNDS:]
        mins = [min(h.values()) for h in window]
        sums = [sum(h.values()) for h in window]
        min_flat = all(b <= a for a, b in zip(mins, mins[1:]))
        sum_flat = all(b <= a for a, b in zip(sums, sums[1:]))
        if min_flat and sum_flat:
            return ("score vector not improving across %d rounds"
                    % STALL_VECTOR_ROUNDS)
    return None


def stale_claims(cards: "dict", now: float,
                 reap_min: int = CLAIM_REAP_MIN) -> "list[str]":
    """Task ids whose claim outlived its teammate (a dead session) —
    the room re-opens each with a `reclaimed` event."""
    out = []
    for tid, card in cards.get("tasks", {}).items():
        if card.get("status") == "claimed" and card.get("claimed_ts") \
                and now - card["claimed_ts"] > reap_min * 60:
            out.append(tid)
    return sorted(out)


def artifact_has_self_assessment(text: str) -> bool:
    """The anchoring leak check (rev 3): a teammate inlining its critique
    into the artifact would hand the lead the scorecard through the front
    door. Pure, deliberately blunt — headers or key phrases."""
    low = (text or "").lower()
    return any(marker in low for marker in (
        "self-critique", "self critique", "scorecard", "self-assessment",
        "self assessment", "my score", "i score myself", "rubric r"))
