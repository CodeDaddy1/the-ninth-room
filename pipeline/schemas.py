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
MAX_HOOK_SEC = 15.0


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
        if chapter_ids and b.get("chapter_id") and b["chapter_id"] not in chapter_ids:
            errors.append("%s: unknown chapter '%s'" % (where, b["chapter_id"]))

    # --- editing-quality rules (added after the 4/10 review, 2026-08-19) ---

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
