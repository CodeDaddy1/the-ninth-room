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
    return errors


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

# The b-roll grammar's justifications, in the brief's order. A cover's
# `why` must LEAD with one of these words — the fifth, `process`, came
# from the Beau Miles study (2026-08-24): the first four are all defined
# against a spoken line, so footage of the work advancing had no legal
# reason to exist and R1 obliged an editor to DELETE it.
COVER_WHYS = ("establish", "illustrate", "foretell", "bridge", "process")


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


def coverage_notes(plan: "dict[str, Any]") -> "list[str]":
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
    """
    notes: "list[str]" = []
    for b in plan.get("beats", []):
        covers = b.get("broll") or []
        if not covers:
            continue
        trim = b.get("trim") or {}
        dur = float(trim.get("e", 0)) - float(trim.get("s", 0))
        is_vo = str(b.get("take_id", "")).startswith("vo_")
        if b.get("peak") and covers:
            notes.append("%s: a peak beat is covered — the face delivers"
                         % b["id"])
        if len(covers) > 3 and not is_vo:
            notes.append("%s: %d covers on one beat — that is a "
                         "bombardment" % (b["id"], len(covers)))
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
        if dur > 0 and not is_vo and total / dur > COVER_MAX_RATIO + 0.01:
            notes.append("%s: %.0f%% covered — past %.0f%% an on-camera "
                         "beat stops being one"
                         % (b["id"], 100 * total / dur,
                            100 * COVER_MAX_RATIO))
    return notes


def validate_edit_plan(plan: "dict[str, Any]", takes: "dict[str, Any]",
                       broll: "dict[str, Any]") -> "list[str]":
    """edit_plan.json — the story-designer's output, cross-checked against
    takes.json and broll.json so the plan can only reference real material.

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

    used_groups: "dict[str, str]" = {}
    killed = {k.get("take_id") for k in plan.get("kill_list", [])}
    for i, b in enumerate(plan["beats"]):
        where = "beats[%d]" % i
        if not isinstance(b, dict):
            errors.append(where + ": not an object")
            continue
        _req(errors, b, "id", str, where)
        if _req(errors, b, "purpose", str, where) and b["purpose"] not in BEAT_PURPOSES:
            errors.append("%s: purpose '%s' not in %s" % (where, b["purpose"], BEAT_PURPOSES))
        if _req(errors, b, "take_id", str, where):
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
                    elif not (t["s"] - 0.01 <= trim["s"] < trim["e"] <= t["e"] + 0.01):
                        errors.append("%s: trim %.2f-%.2f outside take %s bounds %.2f-%.2f"
                                      % (where, trim["s"], trim["e"], tid, t["s"], t["e"]))
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
        if chapter_ids and b.get("chapter_id") and b["chapter_id"] not in chapter_ids:
            errors.append("%s: unknown chapter '%s'" % (where, b["chapter_id"]))

    # --- editing-quality rules (added after the 4/10 review, 2026-08-19) ---

    # A VO take on screen is a teleprompter recording of Caleb reading --
    # its PICTURE must never ship. Any beat cut from a vo_* file needs
    # b-roll, and enough of it to cover what the beat keeps.
    for b in plan["beats"]:
        t = take_by_id.get(b.get("take_id"))
        if not t or not str(t.get("file", "")).startswith("vo_"):
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
        # Approximate word times across the take span to find boundary words.
        span = max(t["e"] - t["s"], 0.001)
        errs = []
        # last word fully inside the trim
        idx_end = min(len(toks) - 1,
                      int((trim["e"] - t["s"]) / span * len(toks)))
        last = toks[max(0, idx_end)].rstrip()
        if not last.endswith(_terminal):
            errs.append("beat %s: ends mid-sentence near %r — extend the trim to the "
                        "sentence end or mark fragment:true" % (b.get("id"), last))
        idx_start = max(0, int((trim["s"] - t["s"]) / span * len(toks)))
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


def _kill_reason(takes: "dict[str, Any] | None", tid: str) -> str:
    for t in (takes or {}).get("takes", []):
        if t.get("id") == tid:
            return str(t.get("screen_reason") or "no reason recorded")
    return "no reason recorded"


def validate_script(script: "dict[str, Any]",
                    takes: "dict[str, Any] | None" = None) -> "list[str]":
    """script.json — the timed script between an approved direction and the
    cut (Caleb, 2026-08-23). Two kinds of section: `oncamera` quotes a real
    take; `vo` is a line Caleb records LATER over b-roll — the lane that
    lets a thin shoot fill a long brief. The chapter's est sum must land
    near its target or the budget the pitch promised is fiction.
    """
    errors: "list[str]" = []
    _req(errors, script, "slug", str, "script")
    _req(errors, script, "option_id", str, "script")
    if not _req(errors, script, "chapters", list, "script"):
        return errors
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
            kind = sec.get("kind")
            if kind not in ("oncamera", "vo"):
                errors.append("%s: kind must be oncamera or vo" % sw)
            if not str(sec.get("text") or "").strip():
                errors.append("%s: empty text — a section with nothing to "
                              "say is a hole in the episode" % sw)
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
    return errors


VO_TARGET_DEFAULT = 0.60   # the dial's default; per-episode in story_brief
VO_TOLERANCE = 0.10        # how far the script may drift from the target


def vo_share(script: "dict[str, Any]") -> float:
    """Share of the script's estimated RUNNING TIME carried by voice-over.

    Time, not section count: three one-line VO sections beside one long
    on-camera answer is not a VO-led episode, and counting sections would
    say it was.
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
            if sec.get("kind") == "vo":
                vo += est
    return (vo / total) if total else 0.0


def script_notes(script: "dict[str, Any]",
                 target: "float | None" = None) -> "list[str]":
    """The script's craft bar, shaped like `coverage_notes`: ADVISORY as a
    function, required-empty by the job that dispatched the writer.

    The format is VO-led as of 2026-08-24, and the share is a per-episode
    dial rather than a doctrine — so this checks the script against THAT
    episode's target, not against a constant.
    """
    notes: "list[str]" = []
    want = VO_TARGET_DEFAULT if target is None else float(target)
    got = vo_share(script)
    if abs(got - want) > VO_TOLERANCE:
        notes.append("script is %.0f%% voice-over against a %.0f%% target — "
                     "%s" % (got * 100, want * 100,
                             "write more narration" if got < want
                             else "give the ensemble more of the screen"))
    for ch in script.get("chapters", []):
        for sec in (ch or {}).get("sections", []) or []:
            if sec.get("kind") != "vo":
                continue
            text = str(sec.get("text") or "")
            # a narrated claim carrying a number or a date is an assertion
            # the audience cannot check and QC cannot trace without a source
            if any(c.isdigit() for c in text) and not sec.get("source"):
                notes.append("%s: a narrated fact with no source — QC "
                             "cannot trace the claim" % sec.get("id", "?"))
    return notes


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
    return {"vo_seconds": round(vo_s, 1),
            "library_seconds": round(lib_s, 1),
            "library_clips": len(avail),
            "shortfall_seconds": round(max(0.0, vo_s - lib_s), 1),
            "ratio": round(lib_s / vo_s, 2) if vo_s else None}


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
