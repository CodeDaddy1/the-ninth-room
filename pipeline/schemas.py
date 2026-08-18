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


BEAT_PURPOSES = ("hook", "stakes", "build", "payoff", "button")
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


CARD_TYPES = ("hook_title", "section", "stat", "quote", "outro")
CARD_ANIMATIONS = ("slide_up", "slide_down", "fade")


def validate_graphics_plan(plan: "dict[str, Any]",
                           edit_plan: "dict[str, Any] | None" = None) -> "list[str]":
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
        if beat_ids and c.get("beat_id") not in beat_ids:
            errors.append("%s: unknown beat '%s'" % (where, c.get("beat_id")))
        for key in ("at", "duration"):
            if not isinstance(c.get(key), (int, float)):
                errors.append("%s: missing numeric '%s'" % (where, key))
        if isinstance(c.get("duration"), (int, float)) and not 1.0 <= c["duration"] <= 15.0:
            errors.append("%s: duration %.1fs outside 1-15s" % (where, c["duration"]))
        if c.get("animation", "slide_up") not in CARD_ANIMATIONS:
            errors.append("%s: animation '%s' not in %s" % (where, c.get("animation"), CARD_ANIMATIONS))
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
