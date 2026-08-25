"""The Ninth Room ENGINE — API + media server on 127.0.0.1:8765.

The Studio (~/Projects/the-ninth-room-studio) is the one UI; the inline
Edit Room page this module once served was retired in P5 (2026-08-23) and
the root now answers with a pointer. What remains: the /api surface the
desks and agents share, /media with Range support, the review lifecycle,
the overlay/sound/b-roll direct-edit verbs, the conform ledger, and the
job queue. review.json is written atomically and guarded by _REVIEW_LOCK;
graphics_plan by _PLAN_LOCK; the conform ledger by _CONFORM_LOCK.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .ingest import work_path, analysis_dir, IngestError, VIDEO_EXT, PROJECT_ROOT

PORT = 8765
REPO_ROOT = Path(__file__).resolve().parents[1]

# One bake at a time: animate.py already saturates the performance cores per
# card, and two overlapping Chrome fleets would just thrash.
_BAKE_LOCK = threading.Lock()
# review.json is load->mutate->replace from several threads (state GETs
# normalize, /api/review POSTs save); one lock serializes them all
_REVIEW_LOCK = threading.Lock()
# graphics_plan.json has three writers (_new_overlay's beat path,
# _save_overlay, _delete_overlay) all staging to the same .tmp; and the
# conform ledger is appended from sfx places (no lock) and card exports
# (under _BAKE_LOCK) - each file gets one lock, same reasoning as review
_PLAN_LOCK = threading.Lock()
_CONFORM_LOCK = threading.Lock()


def _state(slug: str) -> "dict":
    work = work_path(slug)
    out = analysis_dir(slug)
    if not ((out / "timeline_map.json").exists()
            and (work / "edit_plan.json").exists()):
        # a project that has not been assembled yet — the Shots desk shows
        # the setup panel instead of a timeline
        return {"slug": slug, "chapters": [],
                "counts": {"total": 0, "approved": 0, "flagged": 0}}
    tl = json.loads((out / "timeline_map.json").read_text())
    plan = json.loads((work / "edit_plan.json").read_text())
    caps = {}
    if (work / "captions.json").exists():
        caps = {c["beat_id"]: c["text"]
                for c in json.loads((work / "captions.json").read_text())["beats"]}
    cards_by_beat: "dict[str, list]" = {}
    if (work / "graphics_plan.json").exists():
        for c in json.loads((work / "graphics_plan.json").read_text())["cards"]:
            cards_by_beat.setdefault(c["beat_id"], []).append(
                {"id": c["id"], "kit": c.get("kit_type", c.get("type")),
                 "copy": c.get("text") or c.get("stat") or c.get("kicker") or ""})
    review = _normalize_review(slug)
    proxies = {}
    pdir = work / "proxies"
    if pdir.is_dir():
        for p in pdir.glob("BT*.mp4"):
            # mtime in the URL busts any stale browser-cached copy of a
            # proxy that was later re-rendered under the same name
            proxies[p.name.split(".")[0]] = "%s?v=%d" % (p.name, p.stat().st_mtime)

    plan_by_id = {b["id"]: b for b in plan["beats"]}
    chapters = [{"id": c["id"], "title": c["title"], "beats": []}
                for c in plan.get("chapters", [])]
    ch_index = {c["id"]: c for c in chapters}
    for beat in tl["beats"]:
        pb = plan_by_id.get(beat["id"], {})
        entry = {
            "id": beat["id"],
            "dur": round(beat["record_e"] - beat["record_s"], 1),
            "record_s": round(beat["record_s"], 1),
            "purpose": pb.get("purpose", ""),
            "take": pb.get("take_id", ""),
            "caption": caps.get(beat["id"], ""),
            "cards": cards_by_beat.get(beat["id"], []),
            "broll": [br["clip_id"] for br in pb.get("broll", [])],
            # full placement rows from the TIMELINE beat - the b-roll drawer
            # lists and removes covers by these (record_s is absolute)
            "broll_placed": beat.get("broll", []),
            "proxy": proxies.get(beat["id"]),
            # The ORIGINAL footage this beat was cut from, and where in it
            # (2026-08-25). The drawer had only the rendered proxy, so
            # placing a cover meant guessing a position against a picture
            # that already has the covers burned into it. Scrubbing the
            # source is what Caleb asked for: "fine scrub the original
            # clip and insert the B-Roll at the insertion point".
            # `segments[].src_s` is FILE-absolute, so beat-relative time
            # maps by addition — verified on BT04, whose segment sits at
            # 67.98 inside a take spanning 66.42-88.74.
            "file": beat.get("file"),
            "segments": beat.get("segments", []),
            "fps": tl.get("fps"),
            "review": review.get(beat["id"], {}),
        }
        ch = ch_index.get(pb.get("chapter_id"))
        (ch["beats"] if ch else chapters[0]["beats"] if chapters else []).append(entry)
    total = len(tl["beats"])
    approved = sum(1 for r in review.values() if r.get("status") == "approved")
    flagged = sum(1 for r in review.values() if r.get("status") == "flagged")
    return {"slug": slug, "chapters": chapters,
            "counts": {"total": total, "approved": approved, "flagged": flagged}}


def _close_review_round(entry: "dict") -> bool:
    """Archive the current note/needs/fixer_note into the entry's history.

    A round CLOSES when the fixer has replied (fixer_note present) — that is
    the "fix landed" signal (decision 3 of the 2026-08-22 plan interview).
    Approving with a fresh note must NOT archive it: that is the
    "approve-with-instruction" flow (BT16 pattern) and the note stays live
    until the fixer answers it. A FLAGGED beat never closes either — flagged
    means the conversation is still open (Caleb's instruction awaits a fixer,
    or a fixer's refusal awaits Caleb; shot-fixer.md sets flagged+fixer_note
    for impossible fixes) — archiving it strands the live instruction, which
    is exactly what happened to BT07/BT78 in the first migration run.
    Returns True when something was archived.
    """
    if entry.get("status") == "flagged":
        return False
    if not (entry.get("fixer_note") or "").strip():
        return False
    import time
    hist = entry.setdefault("history", [])
    hist.append({"round": len(hist) + 1,
                 "note": entry.get("note", ""),
                 "needs": entry.get("needs", []),
                 "fixer_note": entry["fixer_note"],
                 "resolved_ts": int(time.time())})
    entry["note"] = ""
    entry.pop("needs", None)
    entry.pop("fixer_note", None)
    return True


def _normalize_review(slug: str) -> "dict":
    with _REVIEW_LOCK:
        return _normalize_review_locked(slug)


def _normalize_review_locked(slug: str) -> "dict":
    """Load review.json, close any rounds whose fix has landed, persist if
    anything moved. Idempotent; called wherever review state is served so a
    fixer run's replies archive themselves on the next desk load."""
    path = work_path(slug) / "review.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text())
    changed = False
    for entry in data.values():
        if isinstance(entry, dict) and _close_review_round(entry):
            changed = True
    if changed:
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2))
        os.replace(tmp, path)
    return data


def _archive_resolved_reviews(slug: str) -> int:
    with _REVIEW_LOCK:
        return _archive_resolved_reviews_locked(slug)


def _archive_resolved_reviews_locked(slug: str) -> int:
    """One-time sweep (decision 4): notes on approved/reworked beats whose
    fixer never replied still archive — they predate the lifecycle and are
    exactly the stale instructions cluttering the desk. Flagged beats keep
    their notes. Returns how many rounds were closed."""
    path = work_path(slug) / "review.json"
    if not path.exists():
        return 0
    import time
    data = json.loads(path.read_text())
    n = 0
    for entry in data.values():
        if not isinstance(entry, dict):
            continue
        if _close_review_round(entry):
            n += 1
        elif entry.get("status") in ("approved", "reworked")                 and (entry.get("note") or "").strip():
            hist = entry.setdefault("history", [])
            hist.append({"round": len(hist) + 1,
                         "note": entry["note"],
                         "needs": entry.get("needs", []),
                         "fixer_note": "",
                         "resolved_ts": int(time.time())})
            entry["note"] = ""
            entry.pop("needs", None)
            n += 1
    if n:
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2))
        os.replace(tmp, path)
    return n


def _conform_append(slug: str, op: str, beat_id: str, payload: "dict") -> None:
    """Every direct edit lands here until 'Conform to Resolve (n)' pushes the
    batch (plan decision 10). P3 builds the executor; the ledger starts now
    so P2 edits are already queued when it arrives."""
    with _CONFORM_LOCK:
        path = work_path(slug) / "pending_conform.json"
        data = json.loads(path.read_text()) if path.exists() else {"ops": []}
        data["ops"].append({"op": op, "beat_id": beat_id, "payload": payload,
                            "ts": int(time.time())})
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2))
        os.replace(tmp, path)


def _conform_pending(slug: str) -> "list":
    path = work_path(slug) / "pending_conform.json"
    if path.exists():
        return json.loads(path.read_text()).get("ops", [])
    return []


def _sfx_place(slug: str, beat_id: str, file: str, at_ms: int,
               gain_db: "float | None", log=print) -> "dict":
    """Place a sound and make the proxy tell the truth about it: the cue is
    written, the beat re-renders WITH the mix, the edit queues for conform,
    and the beat goes back into Caleb's queue as 'edited' (decision 05)."""
    from . import sfx as sfx_mod
    from . import proxy as proxy_mod
    cue = sfx_mod.place(slug, beat_id, file, at_ms,
                        sfx_mod.DEFAULT_GAIN_DB if gain_db is None
                        else float(gain_db))
    proxy_mod.build(slug, only_beats=[beat_id], log=log)
    _conform_append(slug, "sfx_place", beat_id, cue)
    _mark_edited(slug, beat_id)
    return cue


def _sfx_remove(slug: str, cue_id: str, log=print) -> "dict":
    from . import sfx as sfx_mod
    from . import proxy as proxy_mod
    gone = sfx_mod.remove(slug, cue_id)
    proxy_mod.build(slug, only_beats=[gone["beat_id"]], log=log)
    _conform_append(slug, "sfx_remove", gone["beat_id"], gone)
    _mark_edited(slug, gone["beat_id"])
    return gone


_EDITPLAN_LOCK = threading.Lock()


def _take_verdicts_path(slug: str) -> "Path":
    return work_path(slug) / "take_verdicts.json"


def _read_take_verdicts(slug: str) -> "dict":
    p = _take_verdicts_path(slug)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text()).get("verdicts", {})
    except ValueError:
        return {}


def _stamp_takes(slug: str) -> "int":
    """Write the human verdicts onto analysis/takes.json.

    Agents read takes.json and nothing else — so the screening decision
    has to live THERE, not in a second file they would have to be told
    about. The verdict store stays the source of truth (it survives a
    re-ingest, which rebuilds takes.json from scratch); this re-applies
    it. Returns how many takes are currently screened out.
    """
    tk_path = work_path(slug) / "analysis" / "takes.json"
    if not tk_path.exists():
        return 0
    doc = json.loads(tk_path.read_text())
    verdicts = _read_take_verdicts(slug)
    n = 0
    for t in doc.get("takes", []):
        v = verdicts.get(t["id"])
        if v and v.get("verdict") == "kill":
            t["screened_out"] = True
            t["screen_reason"] = v.get("reason") or "screened out"
            n += 1
        else:
            t.pop("screened_out", None)
            t.pop("screen_reason", None)
    _write_json(tk_path, doc)
    return n


def _set_take_verdict(slug: str, take_id: str, verdict: str,
                      reason: str = "", log=print) -> "dict":
    """Keep or kill one take. `undo` clears the verdict entirely.

    One writer: this route. The store is Caleb's, and it OUTRANKS the
    story-designer's own `kill_list` — that one is the designer judging
    its own work after the fact.
    """
    if verdict not in ("keep", "kill", "undo"):
        raise IngestError("verdict must be keep, kill or undo")
    tk_path = work_path(slug) / "analysis" / "takes.json"
    if not tk_path.exists():
        raise IngestError("no takes yet — ingest first")
    known = {t["id"] for t in json.loads(tk_path.read_text()).get("takes", [])}
    if take_id not in known:
        raise IngestError("no take '%s'" % take_id)
    p = _take_verdicts_path(slug)
    doc = {"verdicts": {}}
    if p.exists():
        try:
            doc = json.loads(p.read_text())
        except ValueError:
            pass
    doc.setdefault("verdicts", {})
    if verdict == "undo":
        doc["verdicts"].pop(take_id, None)
    else:
        doc["verdicts"][take_id] = {"verdict": verdict,
                                    "reason": reason[:200],
                                    "ts": int(time.time())}
    _write_json(p, doc)
    n = _stamp_takes(slug)
    log("[takes] %s %s%s — %d screened out"
        % (take_id, verdict, (" (%s)" % reason) if reason else "", n))
    return {"take_id": take_id, "verdict": verdict, "screened_out": n}


def _take_screening(slug: str) -> "dict":
    """Flags + verdicts for the Takes desk, in one payload."""
    from . import takes as takes_mod
    tk_path = work_path(slug) / "analysis" / "takes.json"
    if not tk_path.exists():
        return {"slug": slug, "flags": {}, "verdicts": {}, "floor": None}
    doc = json.loads(tk_path.read_text())
    rows = doc.get("takes", [])
    return {"slug": slug,
            "flags": takes_mod.flag_takes(rows, doc.get("groups", [])),
            "verdicts": _read_take_verdicts(slug),
            "floor": takes_mod.quiet_floor(rows),
            "counts": {"takes": len(rows),
                       "screened_out": sum(1 for t in rows
                                           if t.get("screened_out"))}}


def _takes_state(slug: str) -> "dict":
    """The Takes desk (P7): every transcribed take with its fate.

    376 takes at ~25 words each travel fine as one payload; search runs
    client-side. Fate comes from the edit plan: picked (which beat), killed
    (the designer's reason), or unused — the honest leftovers pile."""
    out = analysis_dir(slug)
    tk_path = out / "takes.json"
    if not tk_path.exists():
        return {"slug": slug, "ingested": False, "takes": []}
    data = json.loads(tk_path.read_text())
    picked, killed = {}, {}
    ep_path = work_path(slug) / "edit_plan.json"
    if ep_path.exists():
        plan = json.loads(ep_path.read_text())
        for b in plan.get("beats", []):
            if b.get("take_id"):
                picked.setdefault(b["take_id"], []).append(b["id"])
        for k in plan.get("kill_list", []):
            killed[k.get("take_id")] = k.get("reason", "")
    takes = []
    for t in data.get("takes", []):
        fate = ("picked" if t["id"] in picked
                else "killed" if t["id"] in killed else "unused")
        takes.append({"id": t["id"], "file": t.get("file"),
                      "s": round(float(t.get("s", 0)), 2),
                      "e": round(float(t.get("e", 0)), 2),
                      "duration": round(float(t.get("duration", 0)), 2),
                      "transcript": t.get("transcript", ""),
                      "complete": bool(t.get("complete", True)),
                      "fillers": int(t.get("fillers", 0)),
                      "fate": fate,
                      "beats": picked.get(t["id"], []),
                      "kill_reason": killed.get(t["id"], "")})
    screening = _take_screening(slug)
    reqs = {"rounds": []}
    rq_path = work_path(slug) / "asset_requests.json"
    if rq_path.exists():
        try:
            reqs = json.loads(rq_path.read_text())
        except ValueError:
            pass
    return {"slug": slug, "ingested": True, "takes": takes,
            "requests": reqs.get("rounds", []),
            "screening": screening}


def _broll_catalog(slug: str) -> "list":
    p = work_path(slug) / "analysis" / "broll.json"
    if not p.exists():
        return []
    return json.loads(p.read_text()).get("clips", [])


def _clamp_cover(beat_len: float, clip_dur: float, at: float,
                 duration: float, src_s: float) -> "tuple":
    """PURE. Where a cover may legally sit, given the beat and the clip.

    Extracted so attach and adjust cannot drift (2026-08-25). They were
    one code path with the rules inline; the moment a second path could
    place a cover, the same arithmetic had to be one function or the two
    would disagree about the edges — and the edges are where a cover
    runs off the end of its source and renders black.

    Order matters: `at` is bounded by the beat, `src_s` by the clip, and
    only then is `duration` bounded by BOTH what remains of the clip
    after src_s and what remains of the beat after at.
    """
    at = max(0.0, min(float(at), beat_len - 0.2))
    src_s = max(0.0, min(float(src_s), clip_dur - 0.2))
    duration = max(0.2, min(float(duration), clip_dur - src_s, beat_len - at))
    return round(at, 3), round(duration, 3), round(src_s, 3)


def _broll_adjust(slug: str, beat_id: str, clip_id: str,
                  at=None, duration=None, src_s=None, record_s=None,
                  log=print) -> "dict":
    """Move a cover that is already placed, without detaching it.

    Caleb, 2026-08-25: "we should be able to go back to the B-Roll and
    adjust where it starts in the clip without having to remove the clip
    and replace." Remove-and-replace worked but cost the cover its place
    in the plan, wrote two conform ops for one intention, and — because
    detach and attach each re-render the beat — paid for the proxy twice.

    Any of the three may be omitted to leave it as it is: `at` (where the
    cover sits in the beat), `src_s` (where the source starts playing)
    and `duration`. The same clamp attach uses keeps it legal.

    `record_s` names WHICH cover when the same clip is used twice on one
    beat — the desk sends the row it drew. Without it the first matching
    clip_id wins, which silently moves the wrong cutaway. Detach already
    disambiguates this way; adjust did not (2026-08-25).
    """
    clips = {c["id"]: c for c in _broll_catalog(slug)}
    if clip_id not in clips:
        raise IngestError("unknown b-roll clip '%s'" % clip_id)
    clip = clips[clip_id]
    with _EDITPLAN_LOCK:
        work = work_path(slug)
        tm_path = work / "analysis" / "timeline_map.json"
        tm = json.loads(tm_path.read_text())
        beats = {b["id"]: b for b in tm["beats"]}
        if beat_id not in beats:
            raise IngestError("beat '%s' not in the timeline" % beat_id)
        beat = beats[beat_id]
        ep_path = work / "edit_plan.json"
        plan = json.loads(ep_path.read_text())
        pb = next((b for b in plan["beats"] if b["id"] == beat_id), None)
        if pb is None:
            raise IngestError("beat '%s' not in the edit plan" % beat_id)
        mine = [c for c in (pb.get("broll") or [])
                if c.get("clip_id") == clip_id]
        if not mine:
            raise IngestError("%s is not on %s — attach it first"
                              % (clip_id, beat_id))
        if record_s is None or len(mine) == 1:
            cur = mine[0]
        else:
            # the caller drew a specific row; match it on position rather
            # than take whichever copy of the clip comes first
            want = float(record_s) - beat["record_s"]
            cur = min(mine, key=lambda c: abs(c.get("at", 0) - want))
        cur_at = cur.get("at", 0)
        beat_len = beat["record_e"] - beat["record_s"]
        new_at, new_dur, new_src = _clamp_cover(
            beat_len, clip["duration"],
            cur.get("at", 0) if at is None else at,
            cur.get("duration", 0) if duration is None else duration,
            cur.get("src_s", 0) if src_s is None else src_s)
        cur.update({"at": new_at, "duration": new_dur, "src_s": new_src})
        tmp = ep_path.with_suffix(".ep.tmp")
        tmp.write_text(json.dumps(plan, indent=2, ensure_ascii=False))
        os.replace(tmp, ep_path)
        # match the timeline row by the position the cover HAD, so the
        # same copy moves in both files
        was_rs = round(beat["record_s"] + cur_at, 3)
        tm_mine = [c for c in (beat.get("broll") or [])
                   if c.get("clip_id") == clip_id]
        entry_map = None
        if tm_mine:
            entry_map = min(tm_mine,
                            key=lambda c: abs(c.get("record_s", 0) - was_rs))
            entry_map.update({"record_s": round(beat["record_s"] + new_at, 3),
                              "duration": new_dur, "src_s": new_src})
        if entry_map is None:
            # the plan had it and the timeline did not: rebuild the row
            # rather than leave the proxy rendering the old placement
            entry_map = {"clip_id": clip_id, "file": clip["file"],
                         "record_s": round(beat["record_s"] + new_at, 3),
                         "duration": new_dur, "src_s": new_src}
            beat.setdefault("broll", []).append(entry_map)
        tmp = tm_path.with_suffix(".tm.tmp")
        tmp.write_text(json.dumps(tm, indent=2))
        os.replace(tmp, tm_path)
    from . import proxy as proxy_mod
    proxy_mod.build(slug, only_beats=[beat_id], log=log)
    _conform_append(slug, "broll_adjust", beat_id, entry_map)
    _mark_edited(slug, beat_id)
    log("[broll] %s on %s -> at %.2fs, %.2fs from %.2fs into the clip"
        % (clip_id, beat_id, new_at, new_dur, new_src))
    return entry_map


def _broll_attach(slug: str, beat_id: str, clip_id: str, at: float,
                  duration: float, src_s: float, log=print) -> "dict":
    """Cover part of a beat with b-roll, everywhere it matters at once:
    edit_plan (so future assembles keep it), timeline_map (so the proxy
    renders it NOW), the conform ledger (so Resolve gets it on push), and
    the review queue (decision 05). Audio always stays with the take."""
    clips = {c["id"]: c for c in _broll_catalog(slug)}
    if clip_id not in clips:
        raise IngestError("unknown b-roll clip '%s'" % clip_id)
    clip = clips[clip_id]
    with _EDITPLAN_LOCK:
        work = work_path(slug)
        tm_path = work / "analysis" / "timeline_map.json"
        tm = json.loads(tm_path.read_text())
        beats = {b["id"]: b for b in tm["beats"]}
        if beat_id not in beats:
            raise IngestError("beat '%s' not in the timeline" % beat_id)
        beat = beats[beat_id]
        beat_len = beat["record_e"] - beat["record_s"]
        at, duration, src_s = _clamp_cover(beat_len, clip["duration"],
                                           at, duration, src_s)
        entry_plan = {"clip_id": clip_id, "at": at,
                      "duration": duration, "src_s": src_s}
        entry_map = {"clip_id": clip_id, "file": clip["file"],
                     "record_s": round(beat["record_s"] + at, 3),
                     "duration": duration, "src_s": src_s}
        ep_path = work / "edit_plan.json"
        plan = json.loads(ep_path.read_text())
        for b in plan["beats"]:
            if b["id"] == beat_id:
                b.setdefault("broll", []).append(entry_plan)
                break
        else:
            raise IngestError("beat '%s' not in the edit plan" % beat_id)
        tmp = ep_path.with_suffix(".ep.tmp")
        tmp.write_text(json.dumps(plan, indent=2, ensure_ascii=False))
        os.replace(tmp, ep_path)
        beat.setdefault("broll", []).append(entry_map)
        tmp = tm_path.with_suffix(".tm.tmp")
        tmp.write_text(json.dumps(tm, indent=2))
        os.replace(tmp, tm_path)
    from . import proxy as proxy_mod
    proxy_mod.build(slug, only_beats=[beat_id], log=log)
    _conform_append(slug, "broll_attach", beat_id, entry_map)
    _mark_edited(slug, beat_id)
    return entry_map


def _broll_detach(slug: str, beat_id: str, clip_id: str, at: float,
                  record_s: "float | None" = None, log=print) -> "dict":
    """Remove one placed cover. The drawer passes the row's EXACT record_s
    (state rounds beat starts to one decimal, so a beat-relative `at`
    computed client-side can be off by up to 0.05 — exactly the old
    tolerance; P3 review finding 17 measured BT63 failing on it)."""
    with _EDITPLAN_LOCK:
        work = work_path(slug)
        tm_path = work / "analysis" / "timeline_map.json"
        tm = json.loads(tm_path.read_text())
        beats = {b["id"]: b for b in tm["beats"]}
        if beat_id not in beats:
            raise IngestError("beat '%s' not in the timeline" % beat_id)
        beat = beats[beat_id]
        rec = (round(float(record_s), 3) if record_s is not None
               else round(beat["record_s"] + float(at), 3))
        tol = 0.02 if record_s is not None else 0.06
        gone = None
        for br in list(beat.get("broll", [])):
            if br.get("clip_id") == clip_id and abs(br["record_s"] - rec) < tol:
                beat["broll"].remove(br)
                gone = br
                break
        if gone is None:
            raise IngestError("no %s cover at %.1fs on %s" % (clip_id, at, beat_id))
        ep_path = work / "edit_plan.json"
        plan = json.loads(ep_path.read_text())
        for b in plan["beats"]:
            if b["id"] == beat_id:
                rel = round(gone["record_s"] - beat["record_s"], 3)
                for br in list(b.get("broll", [])):
                    if br.get("clip_id") == clip_id and abs(float(br.get("at", -1)) - rel) < 0.06:
                        b["broll"].remove(br)
                        break
                break
        tmp = ep_path.with_suffix(".ep.tmp")
        tmp.write_text(json.dumps(plan, indent=2, ensure_ascii=False))
        os.replace(tmp, ep_path)
        tmp = tm_path.with_suffix(".tm.tmp")
        tmp.write_text(json.dumps(tm, indent=2))
        os.replace(tmp, tm_path)
    # trash BEFORE the slow proxy rebuild: an ffmpeg failure must not
    # commit the removal while losing its undo entry (gate F11)
    _trash_add(slug, "broll", {
        "beat_id": beat_id, "clip_id": clip_id,
        "at": round(gone["record_s"] - beat["record_s"], 3),
        "duration": gone.get("duration"), "src_s": gone.get("src_s", 0)})
    from . import proxy as proxy_mod
    proxy_mod.build(slug, only_beats=[beat_id], log=log)
    _conform_append(slug, "broll_remove", beat_id, gone)
    _mark_edited(slug, beat_id)
    return gone


TRASH_CAP = 7
_TRASH_LOCK = threading.Lock()


def _trash_add(slug: str, kind: str, payload: "dict") -> None:
    """Removals are recoverable: the last few removed covers/cards land in
    trash.json with a Restore verb (P3, 2026-08-23). Capped — this is an
    undo, not an archive. Every entry carries a unique uid: two deletions
    in the same SECOND are ordinary, and a (ts, kind) restore key deleted
    both (P3 gate finding 1, verified data loss)."""
    with _TRASH_LOCK:
        work = work_path(slug)
        path = work / "trash.json"
        data = json.loads(path.read_text()) if path.exists() else {"entries": []}
        uid = "%d-%04d" % (int(time.time()), (data.get("seq", 0) % 10000))
        data["seq"] = data.get("seq", 0) + 1
        data["entries"].append(dict(payload, kind=kind,
                                    ts=int(time.time()), uid=uid))
        data["entries"] = data["entries"][-TRASH_CAP:]
        _write_json(path, data)


def _trash_list(slug: str) -> "list":
    path = work_path(slug) / "trash.json"
    if not path.exists():
        return []
    return json.loads(path.read_text()).get("entries", [])


def _trash_pop(slug: str, uid: str) -> None:
    """Drop exactly ONE entry by identity, re-reading the file so entries
    trashed during a slow restore (an ffmpeg proxy build) survive
    (P3 gate finding 5)."""
    with _TRASH_LOCK:
        path = work_path(slug) / "trash.json"
        data = json.loads(path.read_text()) if path.exists() else {"entries": []}
        data["entries"] = [e for e in data["entries"] if e.get("uid") != uid]
        _write_json(path, data)


def _trash_restore(slug: str, uid: str, kind: str = "") -> "dict":
    """Re-insert ONE trashed entry (by uid — never by second-resolution
    timestamp, P3 gate finding 1) through a VALIDATED write path. The
    b-roll branch validates the whole plan after the attach and rolls it
    back on errors (finding 2: _broll_attach clamps but never validates,
    so a restore could violate one-use-per-clip and brick assemble), and
    refuses when the beat has shrunk so far the clamp would produce a
    different cover than the one removed (finding 3: a 4s cover restored
    as a 0.2s flash frame reported as success)."""
    work = work_path(slug)
    entries = _trash_list(slug)
    entry = next((e for e in entries if e.get("uid") == uid), None)
    if entry is None:
        raise IngestError("that entry is no longer in the trash")
    kind = entry.get("kind", kind)
    if kind == "broll":
        want_at = float(entry.get("at", 0))
        want_dur = float(entry["duration"])
        restored = _broll_attach(slug, entry["beat_id"], entry["clip_id"],
                                 want_at, want_dur,
                                 float(entry.get("src_s", 0)))
        # the attach clamps against the CURRENT beat — if the clip landed
        # meaningfully elsewhere/shorter, the beat changed since removal
        got_at = float(restored.get("record_s", 0))  # absolute; compare dur
        if abs(float(restored.get("duration", 0)) - want_dur) > 0.25:
            _broll_detach(slug, entry["beat_id"], entry["clip_id"], 0,
                          record_s=restored.get("record_s"))
            raise IngestError("the clip has changed since this cover was "
                              "removed — place it again by hand")
        from . import schemas
        plan, takes, broll = _plan_takes_broll(slug)
        errs = schemas.validate_edit_plan(plan, takes, broll)
        if errs:
            _broll_detach(slug, entry["beat_id"], entry["clip_id"], 0,
                          record_s=restored.get("record_s"))
            raise IngestError("restore refused: %s" % errs[0])
    elif kind == "custom_card":
        card = entry["card"]
        with _PLAN_LOCK:  # every other custom writer holds it (gate F6)
            custom = _load_custom(slug)
            if any(c["id"] == card["id"] for c in custom["overlays"]):
                raise IngestError("a card with id %s exists again — restore "
                                  "would collide" % card["id"])
            custom["overlays"].append(card)
            from . import schemas
            errs = schemas.validate_custom_overlays(custom)
            if errs:
                raise IngestError("cannot restore %s: %s"
                                  % (card["id"], errs[0]))
            _write_custom(slug, custom)
        restored = card
    elif kind == "card":
        card = entry["card"]
        with _PLAN_LOCK:
            gp_path = work / "graphics_plan.json"
            if not gp_path.exists():
                raise IngestError("no graphics plan to restore into")
            plan = json.loads(gp_path.read_text())
            if any(c["id"] == card["id"] for c in plan["cards"]):
                raise IngestError("a card with id %s exists again — restore "
                                  "would collide" % card["id"])
            plan["cards"].append(card)
            from . import schemas
            # validate WITH the edit plan (a beat-less call skips the
            # unknown-beat check entirely) and filter by id AND position:
            # "unknown beat" errors name cards[N], never the card id —
            # both gaps found by test_surgery, both restored invalid cards
            ep_path = work / "edit_plan.json"
            ep = json.loads(ep_path.read_text()) if ep_path.exists() else None
            where = "cards[%d]" % (len(plan["cards"]) - 1)
            # beat_lens too: a card whose `at` overruns its re-assembled
            # beat composites into NO proxy while landing mid-next-beat in
            # Resolve (gate F7 — the exact divergence schemas documents)
            errs = [e for e in schemas.validate_graphics_plan(
                        plan, ep, beat_lens=_beat_lens(slug))
                    if card["id"] in e or where in e]
            if errs:
                raise IngestError("cannot restore %s: %s"
                                  % (card["id"], errs[0]))
            tmp = gp_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(plan, indent=2, ensure_ascii=False))
            os.replace(tmp, gp_path)
        restored = card
    else:
        raise IngestError("unknown trash kind '%s'" % kind)
    _trash_pop(slug, uid)
    return restored


def _plan_takes_broll(slug: str) -> "tuple":
    work = work_path(slug)
    plan = json.loads((work / "edit_plan.json").read_text())
    takes = json.loads((work / "analysis" / "takes.json").read_text())
    broll_p = work / "analysis" / "broll.json"
    broll = json.loads(broll_p.read_text()) if broll_p.exists() else {"clips": []}
    return plan, takes, broll


def _beat_alternates(slug: str, beat_id: str) -> "list":
    """The other takes of this moment, ranked by transcript similarity to
    the take the cut currently uses — the swap verb's menu."""
    import difflib
    plan, takes, _ = _plan_takes_broll(slug)
    beat = next((b for b in plan["beats"] if b["id"] == beat_id), None)
    if beat is None:
        raise IngestError("beat '%s' not in the cut" % beat_id)
    by_id = {t["id"]: t for t in takes.get("takes", [])}
    cur = by_id.get(beat.get("take_id"))
    base = (cur or {}).get("transcript", "")
    out = []
    for t in takes.get("takes", []):
        if t["id"] == beat.get("take_id"):
            continue
        ratio = difflib.SequenceMatcher(
            None, (base or "").lower(),
            (t.get("transcript") or "").lower()).ratio()
        out.append({"id": t["id"], "file": t.get("file"),
                    "transcript": t.get("transcript", ""),
                    "duration": t.get("duration"),
                    "s": t.get("s"), "e": t.get("e"),
                    "similarity": round(ratio, 3)})
    out.sort(key=lambda x: -x["similarity"])
    return out[:6]


def _reset_review(slug: str, beat_id: str) -> None:
    """Surgery invalidates the VERDICT: the clip returns to the queue.
    The note survives — a flag's reason is the reviewer's words and may
    still apply to the new take (gate F11: deleting the whole entry
    destroyed irrecoverable text)."""
    with _REVIEW_LOCK:
        path = work_path(slug) / "review.json"
        if not path.exists():
            return
        data = json.loads(path.read_text())
        entry = data.get(beat_id)
        if entry and "status" in entry:
            entry.pop("status", None)
            entry["ts"] = int(time.time())
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, indent=2))
            os.replace(tmp, path)


def _queue_reassemble(slug: str) -> bool:
    """Swap and trim change beat DURATIONS, so the single-beat re-proxy
    the b-roll verbs use is not enough — the timeline must rebuild
    (proxies render from timeline_map; found live when snap-cuts silently
    missed review playback). Assemble is enqueued; P1's notification says
    when it lands.

    A QUEUED assemble will read the fresh plan when it starts — fine. A
    RUNNING one read the plan before this edit and will not contain it
    (P3 gate finding 4: the silent stale-review no-op) — arm a retry
    timer that keeps trying until a fresh assemble queues."""
    from . import jobs as jobs_mod
    try:
        jobs_mod.start("assemble", slug)
        return True
    except jobs_mod.JobError:
        running = any(j.get("kind") == "assemble"
                      and j.get("state") == "running"
                      for j in jobs_mod.jobs(slug))
        if running:
            def _retry(attempt=0):
                try:
                    jobs_mod.start("assemble", slug)
                except jobs_mod.JobError:
                    if attempt < 60:  # give a long assemble ten minutes
                        t = threading.Timer(10.0, _retry, args=(attempt + 1,))
                        t.daemon = True
                        t.start()
            t = threading.Timer(10.0, _retry)
            t.daemon = True
            t.start()
        return False  # queued already, or the retry timer owns it


def _beat_swap(slug: str, beat_id: str, take_id: str) -> "dict":
    """Use a different take for this clip — no auto-fix session for a
    one-take opinion (P3, 2026-08-23). The new take starts at its natural
    span; Tighten cuts can polish the edges after."""
    from . import schemas
    with _EDITPLAN_LOCK:
        plan, takes, broll = _plan_takes_broll(slug)
        by_id = {t["id"]: t for t in takes.get("takes", [])}
        if take_id not in by_id:
            raise IngestError("unknown take '%s'" % take_id)
        beat = next((b for b in plan["beats"] if b["id"] == beat_id), None)
        if beat is None:
            raise IngestError("beat '%s' not in the cut" % beat_id)
        if beat.get("take_id") == take_id:
            raise IngestError("the cut already uses that take")
        take = by_id[take_id]
        old = {k: beat.get(k) for k in ("take_id", "trim", "cuts",
                                        "punches", "broll")}
        beat["take_id"] = take_id
        beat["trim"] = {"s": round(float(take["s"]), 3),
                        "e": round(float(take["e"]), 3)}
        # cuts/punches belong to the OLD performance — stale times over a
        # new take are wrong even when they happen to validate (gate F9)
        beat.pop("cuts", None)
        beat.pop("punches", None)
        # covers past the new take's span would be silently dropped at
        # assemble while still validating as coverage — drop them HERE,
        # loudly, into the trash
        span = float(take["e"]) - float(take["s"])
        kept, dropped = [], []
        for br in beat.get("broll", []) or []:
            if float(br.get("at", 0)) + float(br.get("duration", 0)) <= span + 0.05:
                kept.append(br)
            else:
                dropped.append(br)
        if dropped:
            beat["broll"] = kept
        errs = schemas.validate_edit_plan(plan, takes, broll)
        if errs:
            for k, v in old.items():
                if v is None:
                    beat.pop(k, None)
                else:
                    beat[k] = v
            raise IngestError("swap refused: %s" % errs[0])
        ep_path = work_path(slug) / "edit_plan.json"
        tmp = ep_path.with_suffix(".ep.tmp")
        tmp.write_text(json.dumps(plan, indent=2, ensure_ascii=False))
        os.replace(tmp, ep_path)
    for br in dropped:
        _trash_add(slug, "broll", {"beat_id": beat_id,
                                   "clip_id": br.get("clip_id"),
                                   "at": br.get("at"),
                                   "duration": br.get("duration"),
                                   "src_s": br.get("src_s", 0)})
    _reset_review(slug, beat_id)
    assembling = _queue_reassemble(slug)
    return {"beat_id": beat_id, "take_id": take_id,
            "trim": beat["trim"], "assembling": assembling,
            "covers_dropped": len(dropped)}


def _beat_trim(slug: str, beat_id: str, d_in: float, d_out: float) -> "dict":
    """Nudge this clip's in/out points. Small steps only — a trim is a
    haircut, not a re-edit; anything bigger is a swap or a session."""
    from . import schemas
    d_in, d_out = float(d_in), float(d_out)
    if abs(d_in) > 2.0 or abs(d_out) > 2.0:
        raise IngestError("trim steps are capped at 2.0s per nudge")
    with _EDITPLAN_LOCK:
        plan, takes, broll = _plan_takes_broll(slug)
        beat = next((b for b in plan["beats"] if b["id"] == beat_id), None)
        if beat is None:
            raise IngestError("beat '%s' not in the cut" % beat_id)
        trim = dict(beat.get("trim") or {})
        if "s" not in trim or "e" not in trim:
            raise IngestError("this clip has no trim to nudge")
        new_s = round(trim["s"] + d_in, 3)
        new_e = round(trim["e"] + d_out, 3)
        if new_s < 0:
            raise IngestError("in point cannot go below the file start")
        if new_e - new_s < 0.5:
            raise IngestError("a clip under half a second is a flash frame")
        old = dict(trim)
        beat["trim"] = {"s": new_s, "e": new_e}
        errs = schemas.validate_edit_plan(plan, takes, broll)
        if errs:
            beat["trim"] = old
            raise IngestError("trim refused: %s" % errs[0])
        ep_path = work_path(slug) / "edit_plan.json"
        tmp = ep_path.with_suffix(".ep.tmp")
        tmp.write_text(json.dumps(plan, indent=2, ensure_ascii=False))
        os.replace(tmp, ep_path)
    _reset_review(slug, beat_id)
    assembling = _queue_reassemble(slug)
    return {"beat_id": beat_id, "trim": beat["trim"],
            "assembling": assembling}


def _mark_edited(slug: str, beat_id: str) -> None:
    # Back into the queue as edited (decision 05) - unless the beat is
    # FLAGGED, which is already at the top and must not be demoted (the
    # export path carries the same guard).
    if _normalize_review(slug).get(beat_id, {}).get("status") != "flagged":
        _save_review(slug, beat_id, {"status": "edited"})


def _save_review(slug: str, beat_id: str, payload: "dict") -> None:
    with _REVIEW_LOCK:
        _save_review_locked(slug, beat_id, payload)


def _save_review_bulk(slug: str, beat_ids: "list", status: str) -> int:
    """One write for a chapter sweep (P2, 2026-08-23). Deliberately only
    fresh clips: a flagged clip was flagged for a reason and never rides
    a bulk approve — clear it by hand or run the auto-fix."""
    if status not in ("approved", "flagged"):
        raise IngestError("bulk status must be approved or flagged")
    if not isinstance(beat_ids, list) or not beat_ids             or not all(isinstance(b, str) for b in beat_ids):
        raise IngestError("beat_ids must be a non-empty list of ids")
    with _REVIEW_LOCK:
        work = work_path(slug)
        path = work / "review.json"
        data = json.loads(path.read_text()) if path.exists() else {}
        now = int(time.time())
        touched = 0
        for bid in beat_ids:
            entry = data.get(bid, {})
            if entry.get("status") in ("flagged", "reworked", "edited"):
                continue
            entry["status"] = status
            entry["ts"] = now
            data[bid] = entry
            touched += 1
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2))
        os.replace(tmp, path)
        return touched


def _save_review_locked(slug: str, beat_id: str, payload: "dict") -> None:
    work = work_path(slug)
    path = work / "review.json"
    data = json.loads(path.read_text()) if path.exists() else {}
    entry = data.get(beat_id, {})
    # a note-only autosave sends status:null — that must never erase a
    # decision already on file
    if payload.get("status") in ("approved", "flagged", "reworked", "edited"):
        entry["status"] = payload["status"]
    if "note" in payload:
        entry["note"] = payload["note"]
    if isinstance(payload.get("needs"), list):
        # structured shot needs — the fixer round routes them: broll ->
        # story/b-roll pass, sfx -> sound-designer, cards -> graphics-director
        entry["needs"] = [n for n in payload["needs"]
                          if n in ("broll", "sfx", "cards")]
        if not entry["needs"]:
            entry.pop("needs", None)
    import time
    entry["ts"] = int(time.time())
    data[beat_id] = entry
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2))
    os.replace(tmp, path)


# --- Overlays desk ---------------------------------------------------------
# Cards are edited with a live in-browser preview (the kit is pure CSS, so
# the browser plays the REAL animation — no bake needed to look), and
# "Approve & Export" bakes the ProRes 4444 alpha .mov into
# work/<slug>/exports/overlays/ under a human-readable name for manual
# import onto a Resolve timeline.

# Content fields the editor may change. Identity and placement wiring
# (id, type, kit_type, beat_id, prebaked, animation) stay server-owned.
_EDITABLE = ("kicker", "text", "subtext", "subtext_italic", "emphasis",
             "stat", "attribution", "rows", "entries", "emojis",
             "duration", "at", "size", "speaker", "cta",
             "sides", "travel_ms", "accent", "x", "y",
             # chapter door meter + the Cyanotype engagement screens
             "active", "chapters", "answer", "value", "low", "high",
             "reveal_ms", "style",
             # per-card sizing (Overlays desk sliders)
             "font_scale", "card_scale",
             # meme pack subjects
             "emoji", "emoji2", "image",
             # legibility scrim strength (0-100; 0 removes it)
             "scrim",
             # position nudge in design pixels
             "offset_x", "offset_y")

# Starter copy for a freshly created overlay, per kit screen. Keys must be
# names overlay_kit.RENDERERS knows (the big emoji screen is "emoji").
#
# This dict is what the "+ new overlay" menu offers, and it is NOT the same
# set as RENDERERS: aliases (hook_title/section/quote/end_plate) and the
# worked-example screens (compare/flight_path/contact, which need images)
# are deliberately absent. Everything a person would reach for should be
# here — the engagement cards especially, since handing the viewer a job is
# the channel's retention strategy (brand/engagement-playbook.md).
#
# What breaks if a screen is missing: it renders fine from a graphics_plan
# but cannot be created by hand in the Edit Room, so it quietly never
# gets used.
_KIT_TEMPLATES = {
    "lower_third": {"kicker": "True fact", "text": "Your fact goes here"},
    "hook": {"kicker": "The setup", "text": "A headline that opens the loop"},
    "chapter": {"kicker": "", "text": "Chapter title",
                "active": 1, "chapters": 5},
    "transition": {"kicker": "Next up", "text": "Chapter title"},
    "stat": {"kicker": "By the numbers", "stat": "42",
             "text": "what the number means"},
    "payoff": {"text": "The payoff line, delivered.", "attribution": "Caleb"},
    "vote": {"kicker": "Cast your vote", "text": "Who wins?",
             "rows": [{"label": "Caleb", "value": "0"},
                      {"label": "Alma", "value": "0"},
                      {"label": "Sofia", "value": "0"}]},
    "scoreboard": {"kicker": "Final count",
                   "entries": [{"label": "Sofia", "value": "1", "highlight": True},
                               {"label": "Caleb", "value": "0"}]},
    "stamp": {"text": "Certified weird"},
    "reaction": {"text": "NO WAY.", "attribution": "Sofia"},
    "emoji": {"emojis": [{"char": "😱"}]},
    "watermark": {},
    "outro": {"kicker": "", "text": "", "cta": "",
              "subtext": "Nine rooms. One you can\u2019t find."},

    # --- the rest of the eight overlays ---
    "callout": {"kicker": "Look here", "text": "What to notice",
                "x": 1180, "y": 400, "size": 380},
    "caption_plate": {"speaker": "Caleb", "text": "A single spoken line"},

    # --- the thirteen engagement cards (brand/engagement-playbook.md) ---
    "quiz": {"kicker": "One of these is true", "text": "What did it eat?",
             "rows": [{"label": "The wrong one"},
                      {"label": "The right one", "correct": True},
                      {"label": "The other wrong one"}]},
    "true_false": {"kicker": "True or false", "answer": "false",
                   "text": "A cocoon and a chrysalis are the same thing"},
    "countdown": {"kicker": "Guess before we do", "text": "How old is this?",
                  "subtext": "Say it out loud. We\u2019ll wait."},
    "prediction": {"kicker": "Call it now", "text": "How many will land on Caleb?",
                   "subtext": "We\u2019ll find out in a second."},
    "spot_it": {"kicker": "Spot it", "text": "Find it before we point",
                "x": 900, "y": 380},
    "this_that": {"kicker": "Pick one", "text": "Left door or right?",
                  "sides": [{"label": "Left"}, {"label": "Right"}]},
    "poll": {"kicker": "You picked", "text": "Left door or right?",
             "subtext": "From last week\u2019s poll. Real numbers only.",
             "rows": [{"label": "Left", "value": "68"},
                      {"label": "Right", "value": "32"}]},
    "rank": {"kicker": "In order", "text": "Most venomous",
             "rows": [{"label": "First"}, {"label": "Second"}, {"label": "Third"}]},
    "scale": {"kicker": "How weird is it", "text": "Rate it",
              "value": 70, "low": "Normal", "high": "Very"},
    "verdict": {"kicker": "The verdict", "text": "This room",
                "value": 4, "subtext": "Four doors out of five"},
    "streak": {"kicker": "Where we are", "text": "Halfway",
               "active": 3, "chapters": 5},

    # --- the legibility layer ---
    "glass": {"value": 55},

    # --- meme B-roll pack: subject = emoji, or an image path in `image` ---
    "meme_reaction": {"kicker": "Live reaction", "emoji": "\U0001F631",
                      "text": "We are so cooked"},
    "meme_drop": {"kicker": "Actual footage", "emoji": "\U0001F5BC",
                  "text": "The family at hour seven"},
    "meme_rain": {"emoji": "\U0001F9A5", "stat": "3 tons",
                  "text": "of sloth, apparently"},
    "meme_versus": {"emoji": "\U0001F3DB", "emoji2": "\U0001F9A5",
                    "sides": [{"label": "Expectation"}, {"label": "Reality"}]},
    "meme_zoom": {"kicker": "Meanwhile", "emoji": "\U0001F419",
                  "text": "The security guard watching us"},
    "meme_breaking": {"kicker": "Breaking", "emoji": "\U0001F6A8",
                      "text": "Dad has found a bench"},
    "meme_loading": {"emoji": "\U0001F9CD", "text": "Convincing dad to leave"},
    "meme_wanted": {"kicker": "Wanted", "emoji": "\U0001F47B",
                    "text": "The ninth room"},
    "meme_deal": {"emoji": "\U0001F9A5", "text": "Deal with it"},
    "meme_certified": {"emoji": "\U0001F995", "text": "Certified museum moment"},
    "meme_chase": {"kicker": "Actual speed", "emoji": "\U0001F3C3",
                   "emoji2": "\U0001F996", "text": "Hour nine of nine"},
    "meme_peek": {"kicker": "We saw that", "emoji": "\U0001F440",
                  "text": "You, still not subscribed"},
    "caption_this": {"kicker": "Caption this", "text": "This exact moment",
                     "subtext": "Comment your caption"},

    # --- outro beats one and two (three is "outro", the end plate) ---
    "takeaway": {"kicker": "The takeaway",
                 "text": "The one line this episode was for."},
    "next_room": {"kicker": "Next room", "text": "What is coming",
                  "subtext": "And one thing nobody mentions",
                  "cta": "Subscribe"},
}

# the VFX pack's starter copy + canvas durations ride the same dict the
# picker and hover previews already read
from .vfx_kit import VFX_TEMPLATES as _VFX_TEMPLATES
_KIT_TEMPLATES.update(_VFX_TEMPLATES)
from .checklist_kit import CHECKLIST_TEMPLATES as _CHECKLIST_TEMPLATES
_KIT_TEMPLATES.update(_CHECKLIST_TEMPLATES)


def _bake_thumbnail(slug: str, beat_id: str, at: float,
                    title: str, kicker: str = "",
                    log=print) -> "dict":
    """The YouTube thumbnail, composed in the Studio and baked here
    (P9, 2026-08-24): a real frame from the chosen clip, the Cyanotype
    scrim, the arch, display type with ONE yellow line. 1280x720 exactly.
    Versioned like every deliverable — thumbnails are iterated, and the
    uploaded one must never be silently replaced."""
    from .graphics import CHROME
    from . import overlay_kit as kit
    work = work_path(slug)
    title = (title or "").strip()
    if not title:
        raise IngestError("a thumbnail needs its title line")
    prox = sorted((work / "proxies").glob("%s.*.mp4" % beat_id)) \
        if (work / "proxies").is_dir() else []
    if not prox:
        raise IngestError("no preview for %s -- assemble first" % beat_id)
    deliver = work / "deliverables"
    deliver.mkdir(exist_ok=True)
    tmp = work / "captions" / "tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    frame = tmp / "thumb_frame.jpg"
    r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error",
                        "-ss", str(max(0.0, float(at))), "-i", str(prox[0]),
                        "-frames:v", "1", str(frame)],
                       capture_output=True, timeout=60)
    if r.returncode != 0 or not frame.exists():
        raise IngestError("could not pull the frame: %s"
                          % r.stderr.decode()[:120])
    import base64
    b64 = base64.b64encode(frame.read_bytes()).decode()
    lines = [ln.strip() for ln in title.split("\n") if ln.strip()][:2]
    # the LAST line carries the yellow — the thing to look at
    spans = []
    for i, ln in enumerate(lines):
        color = kit.YELLOW if i == len(lines) - 1 and len(lines) > 1 \
            else kit.CHALK
        spans.append('<div style="color:%s">%s</div>' % (color, kit._e(ln)))
    if len(lines) == 1:
        spans = ['<div style="color:%s">%s</div>'
                 % (kit.CHALK, kit._e(lines[0]))]
    eyebrow = ""
    if kicker.strip():
        eyebrow = ('<div style="display:flex;align-items:center;gap:12px;'
                   'margin-bottom:18px"><div style="width:56px;height:4px;'
                   'background:%s"></div><span style="font-family:%s;'
                   'font-size:30px;font-weight:800;letter-spacing:.2em;'
                   'text-transform:uppercase;color:%s">%s</span></div>'
                   % (kit.CYAN, kit.FONT_DISPLAY, kit.CYAN,
                      kit._e(kicker.strip())))
    html = (
        '<!DOCTYPE html><html><head><meta charset="utf-8"><style>'
        'html,body{margin:0;width:1280px;height:720px;overflow:hidden}'
        '</style></head><body>'
        '<div style="position:relative;width:1280px;height:720px;'
        'background:#0B2340">'
        '<img src="data:image/jpeg;base64,%(b64)s" style="position:absolute;'
        'inset:0;width:100%%;height:100%%;object-fit:cover">'
        '<div style="position:absolute;inset:0;background:'
        'linear-gradient(90deg, rgba(11,35,64,.92) 0%%,'
        'rgba(11,35,64,.55) 42%%, rgba(11,35,64,0) 75%%)"></div>'
        '<div style="position:absolute;left:64px;top:0;bottom:0;'
        'display:flex;flex-direction:column;justify-content:center;'
        'max-width:640px">%(eyebrow)s'
        '<div style="font-family:%(font)s;font-size:88px;line-height:1.02;'
        'font-weight:800;letter-spacing:-.03em;'
        'text-shadow:0 0 6px rgba(4,16,32,.9),0 6px 28px rgba(4,16,32,.85)">'
        '%(spans)s</div></div>'
        '</div></body></html>'
        % {"b64": b64, "eyebrow": eyebrow, "font": kit.FONT_DISPLAY,
           "spans": "".join(spans)})
    page = tmp / "thumb.html"
    page.write_text(html)
    v = 1
    while (deliver / ("thumbnail_v%d.png" % v)).exists():
        v += 1
    out = deliver / ("thumbnail_v%d.png" % v)
    r = subprocess.run([CHROME, "--headless=new", "--disable-gpu",
                        "--force-device-scale-factor=1",
                        "--window-size=1280,720", "--hide-scrollbars",
                        "--screenshot=" + str(out), "file://" + str(page)],
                       capture_output=True, timeout=60)
    if r.returncode != 0 or not out.exists():
        raise IngestError("thumbnail bake failed: %s"
                          % r.stderr.decode()[:120])
    log("[thumb] %s -> %s" % (slug, out.name))
    return {"file": out.name}


def _project_title(slug: str) -> str:
    """The episode's human name (P6, 2026-08-24). Precedence: Caleb's
    override (title.txt) -> the approved story option's title -> the
    title-cased folder name. stories.json is overwritten per round, so an
    approved id may not resolve — fall through, never guess."""
    work = work_path(slug)
    t = work / "title.txt"
    if t.exists():
        txt = t.read_text().strip()
        if txt:
            return txt[:120]
    try:
        fb = json.loads((work / "story_feedback.json").read_text())
        rounds = fb.get("rounds", [])
        choice = next((r.get("choice") for r in reversed(rounds)
                       if r.get("decision") == "approve"), None)
        if choice:
            st = json.loads((work / "stories.json").read_text())
            for o in st.get("options", []):
                if o.get("id") == choice and o.get("title"):
                    return str(o["title"])[:120]
    except (OSError, ValueError):
        pass
    return slug.replace("-", " ").title()


def _project_poster(slug: str) -> "str | None":
    """poster.jpg beside the work files: the mid-frame of the first beat's
    preview, generated once and reused (media-served, cache-busted by
    mtime). Missing proxies mean no poster — never a placeholder file."""
    work = work_path(slug)
    poster = work / "poster.jpg"
    if poster.exists():
        return "poster.jpg?v=%d" % poster.stat().st_mtime
    pdir = work / "proxies"
    if not pdir.is_dir():
        return None
    prox = sorted(pdir.glob("BT*.mp4"))
    if not prox:
        return None
    try:
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error",
                        "-ss", "1.0", "-i", str(prox[0]),
                        "-frames:v", "1", "-vf", "scale=640:-2",
                        str(poster)], timeout=30, capture_output=True)
    except (OSError, subprocess.SubprocessError):
        return None
    if poster.exists():
        return "poster.jpg?v=%d" % poster.stat().st_mtime
    return None


def _dir_bytes(d: Path) -> int:
    total = 0
    if d.is_dir():
        for f in d.rglob("*"):
            try:
                if f.is_file():
                    total += f.stat().st_size
            except OSError:
                continue
    return total


def _project_storage(slug: str) -> "dict":
    work = work_path(slug)
    return {"footage": _dir_bytes(work / "footage"),
            "previews": (_dir_bytes(work / "proxies")
                         + _dir_bytes(work / "captions")),
            "renders": (_dir_bytes(work / "deliverables")
                        + _dir_bytes(work / "exports"))}


def _clean_stale_candidates(files_by_beat: "dict", live_ids: "set") -> "list":
    """PURE selection for the clean verb (testable without a filesystem):
    per live beat keep only the NEWEST preview file (the current one is
    always the newest — proxy names change with the spec hash and the old
    hash lingers); every file of a beat no longer in the cut goes."""
    doomed = []
    for bid, files in files_by_beat.items():
        ordered = sorted(files, key=lambda f: f[1])  # (name, mtime)
        if bid not in live_ids:
            doomed.extend(name for name, _ in ordered)
        else:
            doomed.extend(name for name, _ in ordered[:-1])
    return doomed


def _clean_stale(slug: str, log=print) -> "dict":
    """Delete superseded preview files. Exports are NOT touched: they are
    immutable because Resolve may reference any of them (the Media Offline
    rule) — preview files are ours alone."""
    work = work_path(slug)
    live = set()
    tm = work / "analysis" / "timeline_map.json"
    if tm.exists():
        live = {b["id"] for b in json.loads(tm.read_text()).get("beats", [])}
    pdir = work / "proxies"
    by_beat: "dict" = {}
    if pdir.is_dir():
        for f in pdir.glob("BT*.mp4"):
            bid = f.name.split(".")[0]
            by_beat.setdefault(bid, []).append((f.name, f.stat().st_mtime))
    doomed = _clean_stale_candidates(by_beat, live)
    freed = 0
    for name in doomed:
        f = pdir / name
        try:
            freed += f.stat().st_size
            f.unlink()
        except OSError:
            continue
    # caption scratch dirs are re-creatable by construction
    tmpdir = work / "captions" / "tmp"
    if tmpdir.is_dir():
        freed += _dir_bytes(tmpdir)
        shutil.rmtree(tmpdir, ignore_errors=True)
    log("[clean] %s: %d files, %.1f MB freed"
        % (slug, len(doomed), freed / 1e6))
    return {"files": len(doomed), "bytes": freed}


def _orientation(slug: str) -> str:
    """The shape this project is being built in.

    Precedence is deliberate and in this order:

    1. `timeline_map.json` — what was ACTUALLY built. Once a cut exists its
       cards and captions are baked to that canvas, so a brief edited
       afterwards must not re-shape it underneath them.
    2. the brief's `delivery` — the intent, and the only answer available
       before assemble. This is the whole point of asking at creation:
       everything upstream of the timeline used to guess, and guessed
       landscape, so a vertical project baked 16:9 cards until its first
       assemble corrected it.
    3. landscape — every project that predates the field is an episode.
    """
    p = analysis_dir(slug) / "timeline_map.json"
    if p.exists():
        try:
            return json.loads(p.read_text()).get("orientation", "landscape")
        except ValueError:
            pass
    b = work_path(slug) / "story_brief.json"
    if b.exists():
        try:
            brief = json.loads(b.read_text())
        except ValueError:
            return "landscape"
        if brief.get("orientation") in ("portrait", "landscape"):
            return brief["orientation"]
        from . import schemas
        if brief.get("delivery"):
            return schemas.delivery_shape(brief["delivery"])["orientation"]
    return "landscape"


def _write_json(path: Path, data) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    os.replace(tmp, path)


def _custom_path(slug: str) -> Path:
    return work_path(slug) / "overlays_custom.json"


def _write_custom(slug: str, custom: "dict") -> None:
    """The ONE writer for overlays_custom.json.

    Every desk edit lands here so a bad kit_type is refused at SAVE rather
    than discovered at bake time -- four call sites wrote the file directly
    and none of them validated, which is how an overlay could carry a
    kit_type the kit cannot render all the way to a render.

    Only rows that are NEW OR CHANGED are checked. Validating the survivors
    instead locks the desk: with one bad row already on disk you could no
    longer delete a DIFFERENT overlay, because the bad one is still in the
    list -- the guard would refuse every repair except the single delete that
    happens to remove it. Refuse what is being written, not what is being
    kept. Duplicate ids stay a whole-list check; they are an invariant of the
    file, not of a row.
    """
    from . import schemas
    rows = custom.get("overlays")
    if not isinstance(rows, list):
        raise IngestError("overlay rejected: 'overlays' must be a list")
    prior = _load_custom(slug).get("overlays", [])
    fresh = [o for o in rows if o not in prior]
    errs = schemas.validate_custom_overlays({"overlays": fresh})
    seen = set()
    for o in rows:
        if isinstance(o, dict) and o.get("id") in seen:
            errs.append("duplicate id '%s'" % o["id"])
        elif isinstance(o, dict):
            seen.add(o.get("id"))
    if errs:
        raise IngestError("overlay rejected: " + "; ".join(errs[:4]))
    _write_json(_custom_path(slug), custom)


def _load_custom(slug: str) -> "dict":
    p = _custom_path(slug)
    return json.loads(p.read_text()) if p.exists() else {"overlays": []}


def _all_overlays(slug: str) -> "list":
    """Every (card, source) — timeline plan cards first, then customs."""
    out = []
    gp = work_path(slug) / "graphics_plan.json"
    if gp.exists():
        for c in json.loads(gp.read_text())["cards"]:
            out.append((c, "plan"))
    for c in _load_custom(slug)["overlays"]:
        out.append((c, "custom"))
    return out


def _exports_dir(slug: str) -> Path:
    d = work_path(slug) / "exports" / "overlays"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _export_state(slug: str) -> "dict":
    p = work_path(slug) / "exports" / "overlays" / ".export_hashes.json"
    return json.loads(p.read_text()) if p.exists() else {}


def _slugify(text: str, n: int = 36) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return s[:n].rstrip("-") or "overlay"


def _export_name(card: "dict") -> str:
    """BT04_transition_the-cockrell-butterfly-center.mov — beat first so the
    file sorts into timeline order in Finder, then what it is, then what it
    says."""
    from . import graphics
    spec, _ = graphics.bake_spec(card)
    copy = card.get("text") or card.get("stat") or card.get("kicker") or ""
    if not copy and card.get("emojis"):
        copy = "emoji"
    who = card.get("beat_id") or "custom"
    return "%s_%s_%s.mov" % (who, spec.get("kit_type", "card"), _slugify(copy))


def _current_key(slug: str, card: "dict", orient: str) -> str:
    """What must match the export sidecar for the .mov to be 'current'.
    Prebaked effect clips have no kit spec — track the mov file itself."""
    from . import graphics
    if card.get("prebaked"):
        mov = work_path(slug) / "graphics" / (card["id"] + ".mov")
        if not mov.exists():
            return "pre:missing"
        st = mov.stat()
        return "pre:%d:%d" % (int(st.st_mtime), st.st_size)
    return graphics.bake_key(card, orient)


def _overlays_state(slug: str) -> "dict":
    from . import graphics
    orient = _orientation(slug)
    exp = _export_state(slug)
    d = _exports_dir(slug)
    items = []
    for card, source in _all_overlays(slug):
        spec, _ = graphics.bake_spec(card)
        e = exp.get(card["id"]) or {}
        f = e.get("file")
        if f and (d / f).exists():
            status = ("current" if e.get("key") == _current_key(slug, card, orient)
                      else "stale")
        else:
            f, status = None, "none"
        items.append({"id": card["id"], "source": source,
                      "beat": card.get("beat_id"),
                      "kit": "effect" if card.get("prebaked")
                             else spec.get("kit_type"),
                      "prebaked": bool(card.get("prebaked")),
                      "export": {"status": status, "file": f},
                      "card": card})
    # Timeline placements, when a dump exists (work/<slug>/timeline_cards.json,
    # written from a bridge dump of the live Resolve timeline). The desk uses
    # it to show which cards are actually IN the cut and where — the plan
    # alone cannot know what a hand edit kept.
    tc_path = work_path(slug) / "timeline_cards.json"
    placements = {}
    if tc_path.exists():
        try:
            placements = json.loads(tc_path.read_text()).get("cards", {})
        except ValueError:
            placements = {}
    for it in items:
        it["placed"] = placements.get(it["id"])
    # Clip context for the editor preview: which proxy plays under this card,
    # and how far in. A plan card knows its beat; a custom card is located by
    # its PLACED record position (OV03 has no beat_id but sits at a known
    # time). With this, "does the scrim read over THIS footage" is answered
    # in the editor, before approving — not after a bake (Caleb, 2026-08-22).
    tm_path = work_path(slug) / "analysis" / "timeline_map.json"
    beats = []
    if tm_path.exists():
        try:
            beats = json.loads(tm_path.read_text())["beats"]
        except (ValueError, KeyError):
            beats = []
    pdir = work_path(slug) / "proxies"
    proxy_by_beat = {}
    if pdir.is_dir():
        for f in pdir.glob("BT*.mp4"):
            proxy_by_beat[f.name.split(".")[0]] = "%s?v=%d" % (f.name,
                                                               f.stat().st_mtime)
    by_id = {b["id"]: b for b in beats}
    for it in items:
        ctx = None
        card = it["card"]
        bid = card.get("beat_id")
        if bid and bid in by_id:
            ctx = {"proxy": proxy_by_beat.get(bid),
                   "offset": float(card.get("at", 0) or 0)}
        elif it.get("placed"):
            rec = it["placed"].get("record_s")
            for b in beats:
                if rec is not None and b["record_s"] <= rec < b["record_e"]:
                    ctx = {"proxy": proxy_by_beat.get(b["id"]),
                           "offset": round(rec - b["record_s"], 2)}
                    break
        if ctx and not ctx["proxy"]:
            ctx = None
        it["context"] = ctx
    placed_meta = None
    if tc_path.exists():
        try:
            _tc = json.loads(tc_path.read_text())
            placed_meta = {"project": _tc.get("project"),
                           "timeline": _tc.get("timeline"),
                           "synced_ts": _tc.get("synced_ts")}
        except ValueError:
            pass

    return {"slug": slug, "orientation": orient, "placed_meta": placed_meta,
            # the live preview renders at the kit's design size — bakes and
            # exports use graphics.CANVAS (UHD) with the same layout at 2x
            "canvas": list(graphics.KIT_DESIGN[orient]),
            "export_dir": str(d), "kits": sorted(_KIT_TEMPLATES),
            # starter copy per screen — the desk's New-card picker renders
            # hover previews from these through /api/overlay/html
            "kit_templates": _KIT_TEMPLATES,
            # picker grouping lives HERE, next to the templates themselves —
            # the Studio renders whatever this says and never keeps its own
            # kit taxonomy (the capability-lookalike lesson)
            "kit_groups": _kit_groups(),
            "overlays": items}


def _kit_groups() -> "list":
    """Picker sections, in display order. Membership is derived from the
    template dict so a kit added there can never silently vanish from the
    picker — anything unclaimed lands in the first (Overlays) group."""
    named = {
        "Engagement": ["quiz", "true_false", "prediction", "countdown",
                       "scale", "poll", "vote", "this_that", "rank",
                       "spot_it", "caption_this", "streak", "verdict",
                       "scoreboard"],
        "Memes": [k for k in _KIT_TEMPLATES if k.startswith("meme_")],
        "Outro": ["takeaway", "next_room", "outro"],
    }
    from .vfx_kit import VFX_GROUPS
    from .checklist_kit import CHECKLIST_GROUPS
    for g in VFX_GROUPS + CHECKLIST_GROUPS:
        named[g["title"]] = g["kits"]
    claimed = {k for ks in named.values() for k in ks}
    groups = [{"title": "Overlays",
               "kits": [k for k in _KIT_TEMPLATES if k not in claimed]}]
    for title in ("Engagement", "Checklist & map", "Memes", "Effects",
                  "Transitions", "Cut furniture", "Outro"):
        kits = [k for k in named[title] if k in _KIT_TEMPLATES]
        if kits:
            groups.append({"title": title, "kits": kits})
    return groups


def _preview_html(card: "dict", w: int, h: int) -> str:
    from . import graphics, overlay_kit
    spec, _ = graphics.bake_spec(card)
    page = overlay_kit.overlay_html(spec, w, h)
    # file:// images (compare / flight_path) are blocked inside an http page;
    # route them through /file so the preview still shows them
    return re.sub(r'file://(/[^"\']+)',
                  lambda m: "/file?p=" + urllib.parse.quote(m.group(1)), page)


def _merge_edits(card: "dict", updates: "dict") -> "dict":
    """Editable fields only. An emptied value never ADDS a key, and never
    DELETES one the card already had — it empties it in place, in the key's
    own type. Renderers treat "" and absent identically (falsy-skip), but
    the plan schema does not: a stat-typed vote card carries "stat": "" and
    "text": "" purely to satisfy it, and dropping those keys made Caleb's
    first real edit un-saveable (2026-08-20)."""
    out = dict(card)
    for k in _EDITABLE:
        if k not in updates:
            continue
        v = updates[k]
        if v in ("", None) or v == []:
            if k in ("duration", "at"):
                continue  # numbers: an empty input is a no-op, not a zero
            if k in out:
                out[k] = [] if isinstance(out[k], list) else ""
        else:
            out[k] = v
    # a zero offset means "no nudge" — storing it re-keys the bake against
    # the absent-key original forever (P7 gate finding 4)
    for fld in ("offset_x", "offset_y"):
        if out.get(fld) in (0, 0.0):
            out.pop(fld, None)
    return out


def _save_overlay(slug: str, card_id: str, updates: "dict") -> "dict":
    with _PLAN_LOCK:
        return _save_overlay_locked(slug, card_id, updates)


def _beat_lens(slug: str) -> "dict":
    p = work_path(slug) / "analysis" / "timeline_map.json"
    if not p.exists():
        return {}
    return {b["id"]: round(b["record_e"] - b["record_s"], 3)
            for b in json.loads(p.read_text()).get("beats", [])}


def _save_overlay_locked(slug, card_id, updates):
    """Persist edits; a timeline card re-validates the WHOLE plan (the 2.5s
    chapter rule etc. gate edits exactly like they gate the pipeline)."""
    from . import schemas
    work = work_path(slug)
    gp = work / "graphics_plan.json"
    if gp.exists():
        plan = json.loads(gp.read_text())
        for i, c in enumerate(plan["cards"]):
            if c["id"] == card_id:
                merged = _merge_edits(c, updates)
                plan["cards"][i] = merged
                errors = schemas.validate_graphics_plan(
                    plan, beat_lens=_beat_lens(slug))
                if errors:
                    raise IngestError("; ".join(errors))
                _write_json(gp, plan)
                return merged
    custom = _load_custom(slug)
    for i, c in enumerate(custom["overlays"]):
        if c["id"] == card_id:
            merged = _merge_edits(c, updates)
            dur = merged.get("duration")
            if not isinstance(dur, (int, float)) or not 1.0 <= dur <= 15.0:
                raise IngestError("duration must be 1-15s")
            if merged.get("kit_type") in ("chapter", "transition") and dur < 2.5:
                raise IngestError("chapter cards hold at least 2.5s")
            custom["overlays"][i] = merged
            _write_custom(slug, custom)
            return merged
    raise IngestError("no overlay '%s'" % card_id)


_KIT_ROLE = {"hook": "hook_title", "payoff": "quote", "reaction": "quote",
             "outro": "outro", "takeaway": "outro", "next_room": "outro",
             "stat": "stat", "vote": "stat", "scoreboard": "stat",
             "quiz": "stat", "poll": "stat", "true_false": "stat"}


def _new_overlay(slug: str, kit_type: str, beat_id: "str | None" = None,
                 at: float = 0.0) -> "dict":
    if kit_type not in _KIT_TEMPLATES:
        raise IngestError("unknown kit type '%s'" % kit_type)
    if beat_id:
        with _PLAN_LOCK:
            # Review-desk creation: a PLAN card, because only plan cards are
            # composited into the beat's proxy — a custom would preview true in
            # the editor and then vanish from the review truth.
            gp_path = work_path(slug) / "graphics_plan.json"
            if not gp_path.exists():
                raise IngestError("no graphics plan to add a beat card to")
            plan = json.loads(gp_path.read_text())
            taken = {c["id"] for c in plan["cards"]}
            n = 1
            while "CARD%02d" % n in taken:
                n += 1
            role = ("meme" if kit_type.startswith("meme_")
                    else _KIT_ROLE.get(kit_type, "section"))
            card = {"id": "CARD%02d" % n, "type": role, "kit_type": kit_type,
                    "beat_id": beat_id, "at": float(at),
                    "duration": 2.5 if kit_type in ("chapter", "transition") else 3.0,
                    "animation": "slide_up"}
            card.update(json.loads(json.dumps(_KIT_TEMPLATES[kit_type])))
            # The validator requires copy fields by ROLE (stat needs stat+text,
            # text roles need text) that several templates legitimately lack.
            # Fill neutral defaults, then validate the WHOLE plan before
            # writing: a rejected card must never reach the file, or every
            # later save/export of ANY card 400s until it is deleted (P2
            # review finding 9 - eight kits poisoned the plan this way).
            if role == "stat":
                card.setdefault("stat", "0")
            if role in ("stat", "hook_title", "section", "outro", "quote"):
                card.setdefault("text", "")
            plan["cards"].append(card)
            from . import schemas
            errs = [e for e in schemas.validate_graphics_plan(plan)
                    if card["id"] in e]
            if errs:
                raise IngestError("cannot add %s here: %s" % (kit_type, errs[0]))
            tmp = gp_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(plan, indent=2, ensure_ascii=False))
            os.replace(tmp, gp_path)
            return card
    custom = _load_custom(slug)
    taken = {c["id"] for c, _ in _all_overlays(slug)}
    n = 1
    while "OV%02d" % n in taken:
        n += 1
    card = {"id": "OV%02d" % n, "kit_type": kit_type,
            "duration": 2.5 if kit_type in ("chapter", "transition") else 3.0}
    card.update(json.loads(json.dumps(_KIT_TEMPLATES[kit_type])))
    custom["overlays"].append(card)
    _write_custom(slug, custom)
    return card


def _delete_overlay(slug: str, card_id: str) -> "dict":
    with _PLAN_LOCK:
        return _delete_overlay_locked(slug, card_id)


def _delete_overlay_locked(slug, card_id):
    """Delete a custom draft, or remove a plan card from graphics_plan.json.

    Plan cards were undeletable from the desk ("belongs to the edit plan"),
    which left no way to kill a card short of editing JSON by hand (Caleb,
    2026-08-21). A removed plan card is appended to graphics_plan_removed.json
    so the decision is reversible by hand; NOTHING here touches Resolve — a
    clip already placed on the timeline stays there until it is removed in
    Resolve or the next conform, and the caller is told which case it got.
    """
    custom = _load_custom(slug)
    keep = [c for c in custom["overlays"] if c["id"] != card_id]
    if len(keep) != len(custom["overlays"]):
        gone_c = [c for c in custom["overlays"] if c["id"] == card_id]
        custom["overlays"] = keep
        _write_custom(slug, custom)
        if gone_c:
            _trash_add(slug, "custom_card", {"card": gone_c[0]})
        source = "custom"
    else:
        gp_path = work_path(slug) / "graphics_plan.json"
        plan = json.loads(gp_path.read_text()) if gp_path.exists() else None
        cards = (plan or {}).get("cards", [])
        keep = [c for c in cards if c.get("id") != card_id]
        if plan is None or len(keep) == len(cards):
            raise IngestError("no overlay '%s' in this project" % card_id)
        gone = [c for c in cards if c.get("id") == card_id]
        plan["cards"] = keep
        _write_json(gp_path, plan)
        rm_path = work_path(slug) / "graphics_plan_removed.json"
        removed = json.loads(rm_path.read_text()) if rm_path.exists() else {}
        removed.setdefault("removed_from_plan", []).extend(
            dict(c, removed_ts=int(time.time())) for c in gone)
        _write_json(rm_path, removed)
        if gone:
            _trash_add(slug, "card", {"card": gone[0]})
        source = "plan"
    with _BAKE_LOCK:
        # same lock as _export_overlay's sidecar writes — two different
        # locks on one read-modify-write file is no lock at all (finding 6)
        exp = _export_state(slug)
        exp.pop(card_id, None)
        # exported files stay on disk — Resolve may reference them
        # (immutability rule above); Caleb trashes unwanted versions himself
        _write_json(_exports_dir(slug) / ".export_hashes.json", exp)
    return {"source": source}


def _duplicate_overlay(slug: str, card_id: str) -> "dict":
    """Copy any card — plan or custom — into a new custom DRAFT.

    This is the replacement workflow: duplicate the card you want to redo,
    edit the draft until the preview is right, export it, and swap it in.
    The copy keeps beat_id so its export still names itself by the beat, and
    remembers what it replaces so the desk can say so.
    """
    cards = {c["id"]: c for c, _src in _all_overlays(slug)}
    if card_id not in cards:
        raise IngestError("no overlay '%s' in this project" % card_id)
    custom = _load_custom(slug)
    taken = set(cards)
    n = 1
    while "OV%02d" % n in taken:
        n += 1
    card = json.loads(json.dumps(cards[card_id]))
    card["id"] = "OV%02d" % n
    card["replaces"] = card_id
    custom["overlays"].append(card)
    _write_custom(slug, custom)
    return card


def _export_overlay(slug: str, card_id: str, log=print) -> "dict":
    """Approve: bake (cached when unchanged) and place the named .mov in
    work/<slug>/exports/overlays/. A timeline card also re-proxies its beat
    so the Shots desk keeps showing what will actually ship."""
    with _BAKE_LOCK:
        from . import graphics
        from . import animate as animate_mod
        from . import proxy as proxy_mod
        cards = {c["id"]: (c, src) for c, src in _all_overlays(slug)}
        if card_id not in cards:
            raise IngestError("no overlay '%s'" % card_id)
        card, source = cards[card_id]
        orient = _orientation(slug)
        w, h = graphics.CANVAS[orient]
        work = work_path(slug)
        d = _exports_dir(slug)
        exp = _export_state(slug)

        # Exported files are IMMUTABLE: Resolve may have any of them imported,
        # and replacing or deleting media under an NLE is exactly what makes
        # clips flicker "Media Offline" (Caleb, 2026-08-20). An unchanged card
        # reuses its latest file; a changed one gets a fresh _v2/_v3 name and
        # every older version stays on disk untouched.
        cur_key = _current_key(slug, card, orient)
        prev = exp.get(card_id, {})
        if prev.get("key") == cur_key and prev.get("file") \
                and (d / prev["file"]).exists():
            log("[export] %s (already current: %s)" % (card_id, prev["file"]))
            exp[card_id] = dict(prev, ts=int(time.time()))
            _write_json(d / ".export_hashes.json", exp)
            return {"file": prev["file"], "path": str(d / prev["file"]),
                    "reproxied": False, "review_reset": False}

        base = _export_name(card)
        name, n = base, 2
        while (d / name).exists():
            name = "%s_v%d.mov" % (base[:-4], n)
            n += 1
        target = d / name

        if source == "plan":
            mov = work / "graphics" / (card_id + ".mov")
            if card.get("prebaked"):
                if not mov.exists():
                    raise IngestError("prebaked card %s has no %s"
                                      % (card_id, mov.name))
            else:
                graphics.build_cards(slug, orientation=orient,
                                     only_ids=[card_id], log=log)
            tmp = d / ("_tmp.%s" % name)
            shutil.copy2(mov, tmp)
            os.replace(tmp, target)
        else:
            spec, preset = graphics.bake_spec(card)
            tmp = d / ("_tmp.%s" % name)
            # scratch frames go in graphics/tmp, NOT the exports folder — a
            # wholesale folder import must never sweep up a mutating PNG
            # sequence alongside the movs
            animate_mod.render_animation(spec, tmp, float(card["duration"]),
                                         w, h, work / "graphics" / "tmp",
                                         preset=preset, log=log)
            os.replace(tmp, target)

        exp[card_id] = {"file": name, "key": _current_key(slug, card, orient),
                        "ts": int(time.time())}
        _write_json(d / ".export_hashes.json", exp)
        log("[export] %s -> %s" % (card_id, target))

        result = {"file": name, "path": str(target),
                  "reproxied": False, "review_reset": False}
        if source == "plan" and card.get("beat_id") and not card.get("prebaked"):
            bid = card["beat_id"]
            pdir = work / "proxies"
            before = {p.name: p.stat().st_mtime
                      for p in pdir.glob(bid + ".*.mp4")}
            proxy_mod.build(slug, only_beats=[bid], log=log)
            after = {p.name: p.stat().st_mtime
                     for p in pdir.glob(bid + ".*.mp4")}
            # only an actually-changed proxy invalidates an approval — an
            # export with no edits must not disturb the review
            if before != after:
                result["reproxied"] = True
                rv = work / "review.json"
                if rv.exists():
                    data = json.loads(rv.read_text())
                    st = data.get(bid, {}).get("status")
                    if st == "approved":
                        _save_review(slug, bid, {"status": "reworked"})
                        result["review_reset"] = True
                    elif st != "flagged":
                        # a changed card puts the beat back in the queue as
                        # "edited — check the result" (decision 05); a
                        # flagged beat is already at the top and stays put
                        _save_review(slug, bid, {"status": "edited"})
        # queue the Resolve-side work (decision 10) for EVERY fresh export —
        # custom cards (OV01-04) and prebaked ones are placed in the live
        # timeline too, and gating this on source=='plan' let their edits
        # silently never reach Resolve (P3 review finding 3). A new card
        # with no beat can't be auto-placed; its op fails with a clear
        # place-it-by-hand reason instead of vanishing.
        tc_path = work / "timeline_cards.json"
        placed_ids = []
        if tc_path.exists():
            try:
                placed_ids = json.loads(tc_path.read_text()).get("cards", [])
            except ValueError:
                pass
        _conform_append(slug,
                        "card_replace" if card_id in placed_ids
                        else "card_place",
                        card.get("beat_id") or "",
                        {"card_id": card_id, "file": name})
        return result


# --- Projects, phases, uploads, story loop ---------------------------------
# The Edit Room houses every project: pick one in the header, or create one
# and drop raw clips/photos straight onto the page. Phases are DERIVED from
# what exists on disk (footage -> ingest -> story -> assembly -> review ->
# master), and each phase's next step is spelled out — including exactly
# what to tell Claude, since the agents run in the Claude session, not here.

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
# the upload gate accepts exactly what ingest can see — one list, owned by
# ingest.py (a private copy here drifted the day .webm arrived: the upload
# said yes, ingest said "no media files")
_VIDEO_UP = VIDEO_EXT
_IMAGE_UP = (".jpg", ".jpeg", ".png", ".heic", ".webp")


def _valid_slug(slug: str) -> bool:
    return bool(slug and _SLUG_RE.match(slug) and work_path(slug).is_dir())


def _new_project(name: str, origin: str = "footage",
                 delivery: str = "long",
                 shorts_source: "str | None" = None) -> str:
    """Create a project WITH its format already decided (Caleb, 2026-08-25:
    "it should prompt me which direction we are taking").

    Both axes used to be inferred far downstream — orientation from
    analysis/timeline_map.json, which only exists after assemble — so every
    stage before that guessed, and guessed landscape. Writing the opening
    brief here means a project is never formatless: the desk knows on the
    first screen whether this is a day out or a documentary, and whether it
    is 16:9 or vertical.
    """
    from . import schemas
    slug = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")
    if not slug:
        raise IngestError("give the project a name")
    origin = str(origin or "footage")
    delivery = str(delivery or "long")
    if origin not in schemas.ORIGINS:
        raise IngestError("origin must be one of %s"
                          % ", ".join(schemas.ORIGINS))
    if delivery not in schemas.DELIVERIES:
        raise IngestError("delivery must be one of %s"
                          % ", ".join(schemas.DELIVERIES))
    if shorts_source and shorts_source not in schemas.SHORTS_SOURCES:
        raise IngestError("shorts_source must be one of %s"
                          % ", ".join(schemas.SHORTS_SOURCES))
    work = work_path(slug)
    if work.exists():
        raise IngestError("project '%s' already exists" % slug)
    (work / "footage").mkdir(parents=True)
    d = schemas.format_defaults(origin, delivery)
    brief = {"target_minutes": d["target_minutes"], "chapters": d["chapters"],
             "vo_share": d["vo_share"], "location": "", "subject": "",
             "origin": origin, "delivery": delivery,
             "orientation": d["orientation"], "format": d["format"],
             "notes": "", "ts": int(time.time())}
    if delivery == "short":
        brief["shorts_source"] = shorts_source or "standalone"
    _write_json(work / "story_brief.json", brief)
    return slug


def _project_row(slug: str) -> "dict":
    work = work_path(slug)
    out = work / "analysis"
    fdir = work / "footage"
    footage = ([p.name for p in sorted(fdir.iterdir())
                if p.suffix.lower() in _VIDEO_UP and not p.name.startswith((".", "_tmp"))]
               if fdir.is_dir() else [])
    ingested = (out / "catalog.json").exists() and (out / "takes.json").exists()
    stories = None
    if (work / "stories.json").exists():
        stories = json.loads((work / "stories.json").read_text())
    fb = {"rounds": []}
    if (work / "story_feedback.json").exists():
        fb = json.loads((work / "story_feedback.json").read_text())
    approved = any(r.get("decision") == "approve" for r in fb.get("rounds", []))
    plan = (work / "edit_plan.json").exists()
    graphics = (work / "graphics_plan.json").exists()
    tl = (out / "timeline_map.json").exists()
    prox = (len(list((work / "proxies").glob("BT*.mp4")))
            if (work / "proxies").is_dir() else 0)
    masters = (sorted(m for m in (work / "deliverables").glob("*.mp4")
                      if not m.name.startswith("_tmp."))
               if (work / "deliverables").is_dir() else [])
    review = {}
    if (work / "review.json").exists():
        review = json.loads((work / "review.json").read_text())
    n_appr = sum(1 for e in review.values() if e.get("status") == "approved")
    n_flag = sum(1 for e in review.values() if e.get("status") == "flagged")
    # reworked + edited both mean "back in Caleb's queue for a re-look";
    # the retired needs tags no longer drive anything (round-2 audit A3)
    n_queue = sum(1 for e in review.values()
                  if e.get("status") in ("flagged", "reworked", "edited"))

    # the Script stage's rail/first-run facts. Recorded counts honor
    # ingest's speech classing (a silent upload must not read as done);
    # the catalog only loads when a script exists, so the common listing
    # stays cheap. Computed BEFORE the phase decision, which reads it.
    script_status = None
    sp = work / "script.json"
    if sp.exists():
        try:
            sc = json.loads(sp.read_text())
            speech = set()
            cat_p = out / "catalog.json"
            if cat_p.exists():
                speech = {f["name"] for f in
                          json.loads(cat_p.read_text()).get("files", [])
                          if f.get("class") == "speech"}
            # Both performed kinds count toward "is this script recorded".
            # A desk episode's lines are the SPINE — counting only vo would
            # call a script-led episode fully recorded before Caleb has sat
            # down in front of the camera once.
            vo_total = vo_rec = 0
            for ch in sc.get("chapters", []):
                for sec in ch.get("sections", []):
                    kind = sec.get("kind")
                    if kind not in ("vo", "desk"):
                        continue
                    vo_total += 1
                    prefixes = _section_file_prefixes(
                        kind, str(sec.get("id", "")), _sec_rev(sec))
                    if any(n.startswith(prefixes) for n in speech):
                        vo_rec += 1
            script_status = {"exists": True, "vo_total": vo_total,
                             "vo_recorded": vo_rec,
                             "locked": bool(sc.get("locked")),
                             "round": sc.get("round"),
                             "open_questions": _open_q_count(work)}
        except ValueError:
            script_status = {"exists": True, "vo_total": 0, "vo_recorded": 0,
                             "locked": False, "round": None,
                             "open_questions": 0}

    # A script-led episode STARTS with no footage, and that is not a state
    # to be nudged out of -- the script comes first and the pictures are
    # sourced or performed to it. Pinning it at "footage" made a
    # footage-free video impossible to begin from the desk.
    brief_doc = {}
    if (work / "story_brief.json").exists():
        try:
            brief_doc = json.loads((work / "story_brief.json").read_text())
        except ValueError:
            brief_doc = {}
    script_led = str(brief_doc.get("origin") or "") == "script"
    script_locked = bool((script_status or {}).get("locked"))

    if script_led and not plan:
        if not (work / "research.json").exists():
            phase, nxt = "story", ("Name the subject on the Story desk, "
                                   "then Research it — with no footage, "
                                   "the research is the material.")
        elif not (work / "script_questions.json").exists():
            phase, nxt = "script", ("Interview me on the Script desk — the "
                                    "director asks before it writes.")
        elif not (script_status or {}).get("exists"):
            phase, nxt = "script", ("Answer what you have a view on, then "
                                    "Write the script. Anything you skip "
                                    "runs on the director's default.")
        elif not script_locked:
            phase, nxt = "script", ("Read the draft on the Script desk — "
                                    "approve it, or send direction for a "
                                    "revision.")
        elif (script_status or {}).get("vo_recorded", 0) < \
                (script_status or {}).get("vo_total", 0):
            phase, nxt = "script", ("Approved. Record the desk and "
                                    "voice-over lines, then Build the cut.")
        else:
            phase, nxt = "script", ("Every line is recorded. Build the cut "
                                    "on the Script desk.")
    elif not footage:
        phase, nxt = "footage", ("Drop clips and photos anywhere on this "
                                 "page, or open the footage folder and copy "
                                 "them in.")
    elif not ingested:
        phase, nxt = "ingest", ("Footage is in (%d clips). Analysis starts "
                                "on its own when the batch settles — or "
                                "press Analyze footage." % len(footage))
    elif not plan and not stories:
        phase, nxt = "story", ("Answer the brief on the Story desk, then "
                               "Pitch stories — three directions arrive "
                               "for your review.")
    elif not plan and not approved:
        phase, nxt = "story", ("Story pitches are on the Story desk — "
                               "approve one, or send direction for a "
                               "fresh round.")
    elif not plan:
        phase, nxt = "story", ("Approved. Build the cut on the Story desk "
                               "— assembly follows on its own.")
    elif not (tl and prox):
        phase, nxt = "assembly", ("The cut is written. Assemble builds the "
                                  "timeline and review previews (it chains "
                                  "automatically after Build the cut).")
    elif prox and (n_appr + n_flag) < prox:
        phase, nxt = "review", ("Work the Review queue — approve what "
                                "ships; b-roll, sound and graphics edit "
                                "each clip directly.")
    elif n_queue:
        phase, nxt = "review", ("%d clip(s) still in the queue. Clear "
                                "them, then Conform to Resolve pushes "
                                "every edit and stale card." % n_queue)
    elif not masters:
        phase, nxt = "master", ("Every clip approved. Render the master "
                                "from the Export desk.")
    else:
        phase, nxt = "master", ("Master rendered: %s. A later change "
                                "re-renders from the Export desk."
                                % masters[-1].name)
    progress = None
    prog_p = work / "ingest_progress.json"
    if prog_p.exists():
        try:
            pr = json.loads(prog_p.read_text())
            # fresh + unfinished = the chain is running right now
            if pr.get("stage") != "done" and time.time() - pr.get("ts", 0) < 300:
                progress = pr
        except ValueError:
            pass
    if progress:
        phase = "ingest"
        nxt = "Ingesting…"
    # the re-cut prompt: every scripted VO line is recorded and the cut
    # predates the newest recording — the plan can't contain what didn't
    # exist when it was written (P4, 2026-08-23)
    recut = False
    if plan and script_status and script_status.get("vo_total", 0) > 0 \
            and script_status.get("vo_recorded") == script_status.get("vo_total"):
        try:
            plan_ts = (work / "edit_plan.json").stat().st_mtime
            # desk takes postdate the plan exactly the way vo takes do —
            # a cut written before Caleb performed a line cannot contain it
            fdir = work / "footage"
            vo_ts = max((f.stat().st_mtime
                         for pat in ("vo_*", "desk_*")
                         for f in fdir.glob(pat)), default=0)
            recut = vo_ts > plan_ts
        except OSError:
            recut = False
    return {"slug": slug, "phase": phase, "next": nxt,
            "title": _project_title(slug),
            "poster": _project_poster(slug),
            "storage": _project_storage(slug),
            "footage": len(footage), "ingested": ingested,
            "stories": bool(stories), "approved": approved,
            "recut_suggested": recut,
            "plan": plan, "graphics": graphics, "proxies": prox,
            "master": masters[-1].name if masters else None,
            "progress": progress, "script": script_status,
            # The format, on every row: the rail and the guided path shape
            # themselves from this rather than assuming a day out.
            "origin": brief_doc.get("origin") or "footage",
            "delivery": brief_doc.get("delivery") or "long",
            "orientation": _orientation(slug),
            "shorts_source": brief_doc.get("shorts_source"),
            # The script lane's own progress facts. A documentary has no
            # footage to count, so the guided path needs these instead:
            # what it is about, whether the material has been gathered, and
            # whether its pictures have been sourced.
            "briefed": bool(str(brief_doc.get("subject") or "").strip()
                            or str(brief_doc.get("location") or "").strip()),
            "research": (work / "research.json").exists(),
            "assets": _asset_count(work),
            "review": {"approved": n_appr, "flagged": n_flag,
                       "queue": n_queue}}


def _archive_project(slug: str) -> None:
    """Move a dead project under work/_archive/ (quick win, round-2 audit
    G7). NOT a delete — footage survives — but Resolve's absolute media
    paths into the project break until it is restored to the same name."""
    src = work_path(slug)
    if not src.is_dir():
        raise IngestError("no project '%s'" % slug)
    dest_root = src.parent / "_archive"
    dest_root.mkdir(exist_ok=True)
    dest = dest_root / slug
    if dest.exists():
        raise IngestError("'%s' already archived" % slug)
    os.replace(src, dest)


def _restore_project(slug: str) -> None:
    src = work_path(slug).parent / "_archive" / slug
    if not src.is_dir():
        raise IngestError("'%s' is not archived" % slug)
    dest = work_path(slug)
    if dest.exists():
        raise IngestError("'%s' already exists live" % slug)
    os.replace(src, dest)


def _tree_stats(d: "Path") -> "tuple":
    """(files, bytes) under d. Symlinks are COUNTED as one entry and never
    followed — a sandbox whose `analysis` points at another episode must not
    report (or later delete) that episode's footage."""
    files = 0
    total = 0
    for root, dirs, names in os.walk(d, followlinks=False):
        dirs[:] = [x for x in dirs if not os.path.islink(os.path.join(root, x))]
        for n in names:
            files += 1
            fp = os.path.join(root, n)
            if os.path.islink(fp):
                continue
            try:
                total += os.stat(fp).st_size
            except OSError:
                continue
    return files, total


def _project_dir(slug: str) -> "tuple":
    """Where a project lives right now: (path, archived). Either root is a
    legitimate delete target — the archive is where dead episodes wait."""
    live = work_path(slug)
    if live.is_dir():
        return live, False
    arch = live.parent / "_archive" / slug
    if arch.is_dir():
        return arch, True
    raise IngestError("no project '%s'" % slug)


def _delete_project(slug: str, confirm: str, log=print) -> "dict":
    """PERMANENT. Erases the project tree — footage, previews, renders, the
    edit plan, everything — from the live root or the archive.

    There is no undo, so three gates stand in front of it:
      1. the slug is a real project slug and not a `_`-prefixed bookkeeping
         directory (_archive, _scout, _scorecards are not episodes);
      2. the caller echoes the slug back in `confirm` — the desk makes a
         human type the name, so a mis-click cannot reach here;
      3. no job is queued or running for it — deleting the tree out from
         under a running ingest or render leaves half-written files and a
         worker raising into the log.
    What breaks if this is wrong: 60+ GB of unrepeatable footage, gone.
    """
    if not _SLUG_RE.match(slug or "") or slug.startswith("_"):
        raise IngestError("bad slug")
    if (confirm or "").strip() != slug:
        raise IngestError("type the episode's name to confirm the delete")
    from . import jobs as jobs_mod
    busy = [j for j in jobs_mod.jobs(slug)
            if j.get("state") in ("queued", "running")]
    if busy:
        raise IngestError("'%s' is busy — %s is %s; wait for it to finish"
                          % (slug, busy[0].get("kind"), busy[0].get("state")))
    target, archived = _project_dir(slug)
    files, size = _tree_stats(target)
    shutil.rmtree(target)
    # the teammate scorecards live outside the episode tree by design
    # (they are the teammate's, not the board's) — they die with it
    cards = work_path("_scorecards") / slug
    if cards.is_dir():
        shutil.rmtree(cards, ignore_errors=True)
    log("[delete] %s (%s): %d files, %.1f GB freed"
        % (slug, "archived" if archived else "live", files, size / 1e9))
    return {"slug": slug, "files": files, "bytes": size, "archived": archived}


def _archived_slugs() -> "list":
    root = work_path("x").parent / "_archive"
    if not root.is_dir():
        return []
    return sorted(p.name for p in root.iterdir()
                  if p.is_dir() and _SLUG_RE.match(p.name))


def _start_project_from_idea(idea_id: str) -> "dict":
    """Idea -> project (quick win, round-2 audit G8): create the project and
    seed the planner with the idea's own words, so starting an episode is a
    click instead of retyping."""
    scout = work_path("_scout") / "ideas.json"
    if not scout.exists():
        raise IngestError("no scouted ideas on file")
    ideas = json.loads(scout.read_text()).get("ideas", [])
    idea = next((i for i in ideas if i.get("id") == idea_id), None)
    if idea is None:
        raise IngestError("no idea '%s'" % idea_id)
    slug = re.sub(r"[^a-z0-9]+", "-", idea.get("title", "").lower()).strip("-")[:32]
    slug = slug or ("idea-%s" % idea_id)
    if work_path(slug).exists():
        raise IngestError("project '%s' already exists" % slug)
    if (work_path(slug).parent / "_archive" / slug).exists():
        raise IngestError("'%s' exists in the archive — restore it instead"
                          % slug)
    work_path(slug).mkdir(parents=True)
    (work_path(slug) / "footage").mkdir()
    plan = {"place": idea.get("title", ""), "visit_date": "",
            "chapters": [],
            "ninth_room_candidates": [],
            "checklist": [],
            "notes": "From the scout: %s\n\nAngle: %s\nWhy now: %s" % (
                idea.get("title", ""), idea.get("angle", ""),
                idea.get("why_now", ""))}
    _write_json(_plan_path(slug), plan)
    try:
        _save_idea_state(idea_id, "develop", "started as project '%s'" % slug)
    except Exception:
        pass  # the project exists either way; the verdict is bookkeeping
    return {"slug": slug}


FOOTAGE_LIBRARY = Path.home() / "Footage"


def _library_index(root: "Path") -> "dict":
    """name -> [paths] for every video under a library root.

    Names, not contents: the index is cheap to build over tens of
    thousands of files, and `_relink_footage` verifies a candidate by
    size + content signature before it replaces anything.
    """
    index: "dict" = {}
    if not root.is_dir():
        return index
    for p in root.rglob("*"):
        if p.is_file() and p.suffix.lower() in VIDEO_EXT:
            index.setdefault(p.name, []).append(p)
    return index


def _swap_to_link(dest: "Path", target: "Path") -> None:
    """Point `dest` at `target` atomically — temp link, then replace, so
    an interrupted swap can never leave the project without its media.
    Same shape as the pass that re-pointed hmns's 358 links."""
    tmp = dest.with_name(dest.name + ".relink")
    if tmp.exists() or tmp.is_symlink():
        tmp.unlink()
    os.symlink(target, tmp)
    os.replace(tmp, dest)


def _link_footage(slug: str, folder: str, log=print) -> "dict":
    """Symlink every video in `folder` into the project's footage dir.

    Linking rather than copying is what keeps the `.LRF` fast path alive:
    `broll._prefer_proxy` resolves the link and finds the camera's 720p
    proxy sitting beside the original, which builds a contact sheet ~17x
    faster than decoding 4K HEVC (measured 0.5s vs 8.8s, 2026-08-24). It
    also saves the project's whole footage weight on disk and removes the
    copy wait before ingest can start.
    """
    src = Path(folder).expanduser()
    if not src.is_dir():
        raise IngestError("no folder '%s'" % folder)
    fdir = work_path(slug) / "footage"
    fdir.mkdir(parents=True, exist_ok=True)
    linked, skipped = [], []
    for p in sorted(src.iterdir()):
        if not p.is_file() or p.suffix.lower() not in VIDEO_EXT:
            continue
        dest = fdir / p.name
        if dest.exists() or dest.is_symlink():
            skipped.append(p.name)      # never overwrite what is already there
            continue
        os.symlink(p.resolve(), dest)
        linked.append(p.name)
    log("[link] %s: linked %d, skipped %d already present"
        % (slug, len(linked), len(skipped)))
    return {"linked": len(linked), "skipped": len(skipped),
            "names": linked[:20]}


def _relink_footage(slug: str, folder: "str | None" = None,
                    log=print) -> "dict":
    """Replace COPIED footage with links to the identical library file.

    The repair for a project that was filled by copy: every real file is
    matched to a library file by name, then verified by size AND the
    first/last-MB content signature before the copy is swapped for a
    link. A file that cannot be matched and verified is left exactly as
    it is — a repair that guesses is worse than one that stops.
    """
    fdir = work_path(slug) / "footage"
    if not fdir.is_dir():
        raise IngestError("no footage in '%s'" % slug)
    root = Path(folder).expanduser() if folder else FOOTAGE_LIBRARY
    index = _library_index(root)
    if not index:
        raise IngestError("no videos under '%s' to link against" % root)
    relinked, freed, unmatched = 0, 0, []
    for p in sorted(fdir.iterdir()):
        if p.is_symlink() or not p.is_file():
            continue                     # already a link, or not media
        if p.suffix.lower() not in VIDEO_EXT:
            continue
        size = p.stat().st_size
        want = _content_sig(p, size)
        match = None
        for cand in index.get(p.name, []):
            try:
                if cand.stat().st_size == size and _content_sig(cand, size) == want:
                    match = cand
                    break
            except OSError:
                continue
        if match is None:
            unmatched.append(p.name)
            continue
        _swap_to_link(p, match.resolve())
        relinked += 1
        freed += size
    log("[relink] %s: %d relinked, %.1f GB reclaimed, %d left as copies"
        % (slug, relinked, freed / 1e9, len(unmatched)))
    return {"relinked": relinked, "bytes": freed,
            "unmatched": len(unmatched), "unmatched_names": unmatched[:10],
            "library": str(root)}


def _projects_state() -> "dict":
    root = work_path("x").parent
    slugs = sorted(p.name for p in root.iterdir()
                   if p.is_dir() and _SLUG_RE.match(p.name)
                   and not p.name.startswith("_")
                   and ((p / "footage").is_dir() or (p / "analysis").is_dir()
                        or (p / "edit_plan.json").exists()))
    return {"projects": [_project_row(s) for s in slugs],
            "archived": _archived_slugs()}


def _content_sig(path: Path, size: int) -> str:
    """Delegates to screen.content_sig — one definition, used by the
    pre-screen's duplicate check and by upload dedupe alike."""
    from .screen import content_sig
    return content_sig(path, size)


def _find_duplicate(tmp: Path, size: int, *dirs: Path) -> "str | None":
    """Name of an existing file with identical size + content, if any."""
    sig = None
    for d in dirs:
        if not d.is_dir():
            continue
        for p in d.iterdir():
            if not p.is_file() or p.name.startswith((".", "_tmp")):
                continue
            if p.stat().st_size != size:
                continue
            if sig is None:
                sig = _content_sig(tmp, size)
            if _content_sig(p, p.stat().st_size) == sig:
                return p.name
    return None


def _uniquify(d: Path, name: str) -> str:
    """name, name-2, name-3… — same NAME but different CONTENT means a
    second camera card reused the counter; both recordings must survive."""
    if not (d / name).exists():
        return name
    stem, ext = Path(name).stem, Path(name).suffix
    n = 2
    while (d / ("%s-%d%s" % (stem, n, ext))).exists():
        n += 1
    return "%s-%d%s" % (stem, n, ext)


def _trash_dest(trash: Path, name: str) -> Path:
    d = trash / name
    if d.exists():  # same name trashed twice — keep both
        d = trash / ("%s.%d%s" % (Path(name).stem, int(time.time()),
                                  Path(name).suffix))
    return d


def _save_upload(slug: str, name: str, rfile, length: int) -> "dict":
    """One uploaded file, streamed to footage/. Photos are kept in
    footage/stills/ and ALSO converted to a 6s UHD clip so the b-roll
    pipeline can place them like any other cutaway. A file whose size and
    content match something already in the project is dropped silently as
    a duplicate (re-dropping a whole card folder must be safe)."""
    name = os.path.basename(name)
    ext = Path(name).suffix.lower()
    if ext not in _VIDEO_UP + _IMAGE_UP:
        raise IngestError("unsupported file type '%s'" % ext)
    fdir = work_path(slug) / "footage"
    fdir.mkdir(parents=True, exist_ok=True)
    tmp = fdir / ("_tmp.%s" % name)
    remaining = length
    with open(tmp, "wb") as fh:
        while remaining > 0:
            chunk = rfile.read(min(1 << 20, remaining))
            if not chunk:
                break
            fh.write(chunk)
            remaining -= len(chunk)
    if remaining:
        tmp.unlink()
        raise IngestError("upload of %s was truncated" % name)
    dup = _find_duplicate(tmp, length, fdir, fdir / "stills")
    if dup:
        tmp.unlink()
        return {"stored": name, "duplicate": dup, "still": ext in _IMAGE_UP}
    if ext in _IMAGE_UP:
        stills = fdir / "stills"
        stills.mkdir(exist_ok=True)
        name = _uniquify(stills, name)
        src = stills / name
        os.replace(tmp, src)
        inp = src
        if ext == ".heic":  # ffmpeg has no HEIC decoder; sips ships with macOS
            conv = stills / (Path(name).stem + ".png")
            subprocess.run(["sips", "-s", "format", "png", str(src),
                            "--out", str(conv)], capture_output=True)
            if conv.exists():
                inp = conv
        clip = fdir / (Path(name).stem + "_still.mp4")
        _still_to_clip(inp, clip)
        return {"stored": name, "as": clip.name, "still": True}
    name = _uniquify(fdir, name)
    os.replace(tmp, fdir / name)
    return {"stored": name, "still": False}


def _save_asset_upload(slug: str, name: str, rfile, length: int,
                       log=print) -> "dict":
    """One uploaded file, streamed to assets/ and filed beside sourced
    material.

    Uploads land on the SAME shelf as anything the sourcer fetched
    (Caleb, 2026-08-25: "I should be able to upload materials in addition
    to the sourcer... through the library"). The Footage desk stays the
    place to dump a camera card; the Library is where supporting material
    lives, whoever found it, with the same verbs and the same provenance
    row.

    Its licence line says plainly where it came from. "Uploaded" is a
    provenance, not a permission — a file Caleb dropped might be his own
    footage or something he grabbed, and only he knows which, so the row
    says so rather than implying a clearance nobody granted.
    """
    name = os.path.basename(name)
    ext = Path(name).suffix.lower()
    if ext not in _VIDEO_UP + _IMAGE_UP:
        raise IngestError("unsupported file type '%s'" % ext)
    adir = work_path(slug) / "assets"
    adir.mkdir(parents=True, exist_ok=True)
    tmp = adir / ("_tmp%s" % ext)
    remaining = length
    with open(tmp, "wb") as fh:
        while remaining > 0:
            chunk = rfile.read(min(1 << 20, remaining))
            if not chunk:
                break
            fh.write(chunk)
            remaining -= len(chunk)
    if remaining:
        tmp.unlink(missing_ok=True)
        raise IngestError("upload of %s was truncated" % name)
    dup = _find_duplicate(tmp, length, adir)
    if dup:
        tmp.unlink(missing_ok=True)
        log("[upload] %s already on the shelf as %s" % (name, dup))
        return {"stored": dup, "duplicate": dup}
    name = _uniquify(adir, name)
    os.replace(tmp, adir / name)
    row = {
        "id": "UP%d" % int(time.time() * 1000 % 10 ** 9),
        "file": name,
        "kind": "video" if ext in _VIDEO_UP else "image",
        "what": Path(name).stem.replace("-", " ").replace("_", " "),
        "query": "uploaded by hand",
        # provenance, NOT permission — see the docstring
        "license": "uploaded — provenance yours to confirm",
        "attribution": "",
        "uploaded_ts": int(time.time()),
    }
    from . import capture as capture_mod
    capture_mod.append_to_manifest(adir, row)
    log("[upload] %s -> assets/%s" % (slug, name))
    return dict(row, stored=name)


_FAV_LOCK = threading.Lock()


def _broll_suggest(slug: str, beat_id: str, limit: int = 8) -> "list":
    """Covers ranked for THIS clip (2026-08-24): the catalog scored by
    description-vs-transcript similarity, minus every clip the plan
    already uses anywhere (the once-only rule means a used clip is not
    actually available). The drawer shows these above the raw search —
    the fluid path to a cover that illustrates the line."""
    import difflib
    work = work_path(slug)
    plan = json.loads((work / "edit_plan.json").read_text()) \
        if (work / "edit_plan.json").exists() else {"beats": []}
    beat = next((b for b in plan.get("beats", []) if b["id"] == beat_id),
                None)
    if beat is None:
        raise IngestError("beat '%s' not in the cut" % beat_id)
    takes = {}
    tp = work / "analysis" / "takes.json"
    if tp.exists():
        takes = {t["id"]: t for t in
                 json.loads(tp.read_text()).get("takes", [])}
    text = (takes.get(beat.get("take_id"), {}).get("transcript") or "").lower()
    used = {c.get("clip_id") for b in plan.get("beats", [])
            for c in (b.get("broll") or [])}
    out = []
    for c in _broll_catalog(slug):
        if c["id"] in used:
            continue
        desc = (c.get("description") or "").lower()
        score = difflib.SequenceMatcher(None, text, desc).ratio()
        # token overlap matters more than sequence for description prose
        tw = set(w for w in text.split() if len(w) > 3)
        dw = set(w for w in desc.split() if len(w) > 3)
        overlap = len(tw & dw) / max(len(tw | dw), 1)
        out.append(dict(c, score=round(0.4 * score + 0.6 * overlap, 3)))
    out.sort(key=lambda x: -x["score"])
    return out[:limit]


def _search_all(q: str, limit: int = 40) -> "list":
    """Cross-episode transcript + b-roll search (P7, 2026-08-24): "that
    time Sofia said the thing about the octopus" -> the exact take,
    playable. Case-insensitive substring over every live project's
    analysis — the corpus is small enough that honesty beats indexing."""
    q = (q or "").strip().lower()
    if len(q) < 2:
        raise IngestError("search needs at least two characters")
    hits = []
    for d in sorted(work_path("x").parent.iterdir()):
        if not d.is_dir() or d.name.startswith("_"):
            continue
        slug = d.name
        title = _project_title(slug)
        tk = d / "analysis" / "takes.json"
        if tk.exists():
            try:
                takes = json.loads(tk.read_text()).get("takes", [])
            except ValueError:
                takes = []
            for t in takes:
                txt = (t.get("transcript") or "")
                if q in txt.lower():
                    hits.append({"slug": slug, "title": title,
                                 "kind": "take", "id": t.get("id"),
                                 "file": t.get("file"),
                                 "s": t.get("s"), "e": t.get("e"),
                                 "text": txt[:220]})
                    if len(hits) >= limit:
                        return hits
        br = d / "analysis" / "broll.json"
        if br.exists():
            try:
                clips = json.loads(br.read_text()).get("clips", [])
            except ValueError:
                clips = []
            for c in clips:
                desc = (c.get("description") or "")
                if q in desc.lower():
                    hits.append({"slug": slug, "title": title,
                                 "kind": "broll", "id": c.get("id"),
                                 "file": c.get("file"),
                                 "s": 0, "e": c.get("duration"),
                                 "text": desc[:220]})
                    if len(hits) >= limit:
                        return hits
    return hits


def _favorites(slug: str) -> "list":
    f = work_path(slug) / "favorites.json"
    if not f.exists():
        return []
    return json.loads(f.read_text()).get("files", [])


def _toggle_favorite(slug: str, name: str, on: bool) -> "list":
    """Star/unstar one clip. The starred set is the story bucket: the
    story-designer treats it as the episode's core material, so what is
    starred here directly widens or narrows the pitched scope."""
    if not name:
        raise IngestError("no file name")
    with _FAV_LOCK:
        favs = _favorites(slug)
        if on and name not in favs:
            favs.append(name)
        if not on and name in favs:
            favs.remove(name)
        _write_json(work_path(slug) / "favorites.json", {"files": favs})
    return favs


def _footage_state(slug: str) -> "dict":
    """Inventory of what's been dropped in: per-clip thumbnail, duration,
    size — thumbnails and probes cached in footage/.thumbs keyed by
    (size, mtime) so the panel stays instant with a card full of 4K."""
    fdir = work_path(slug) / "footage"
    items = []
    if fdir.is_dir():
        thumbs = fdir / ".thumbs"
        thumbs.mkdir(exist_ok=True)
        meta_path = thumbs / "meta.json"
        meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
        changed = False
        for p in sorted(fdir.iterdir()):
            if not p.is_file() or p.name.startswith((".", "_tmp")) \
                    or p.suffix.lower() not in _VIDEO_UP:
                continue
            st = p.stat()
            key = [st.st_size, int(st.st_mtime)]
            m = meta.get(p.name)
            if not m or m[:2] != key:
                pr = subprocess.run(
                    ["ffprobe", "-v", "error", "-select_streams", "v:0",
                     "-show_entries", "stream=width,height:format=duration",
                     "-of", "json", str(p)], capture_output=True, text=True)
                try:
                    d = json.loads(pr.stdout)
                    dur = float(d["format"]["duration"])
                    w0 = d["streams"][0]["width"]
                    h0 = d["streams"][0]["height"]
                except Exception:
                    dur, w0, h0 = 0.0, 0, 0
                m = key + [round(dur, 1), w0, h0]
                meta[p.name] = m
                changed = True
            th = thumbs / (p.name + ".jpg")
            if not th.exists() or th.stat().st_mtime < st.st_mtime:
                at = min(1.0, max(m[2] / 2.0, 0.0))
                subprocess.run(
                    ["ffmpeg", "-y", "-loglevel", "error", "-ss", "%.2f" % at,
                     "-i", str(p), "-frames:v", "1", "-vf", "scale=320:-2",
                     str(th)], capture_output=True)
            still_src, src_size = None, None
            if p.stem.endswith("_still"):
                for s in (fdir / "stills").glob(p.stem[:-6] + ".*"):
                    still_src, src_size = s.name, s.stat().st_size
                    break
            items.append({"name": p.name, "size": st.st_size,
                          "dur": m[2], "w": m[3], "h": m[4],
                          "still": p.stem.endswith("_still"),
                          "still_src": still_src, "src_size": src_size,
                          "thumb": str(th) if th.exists() else None})
        if changed:
            _write_json(meta_path, meta)
    ingested = (work_path(slug) / "analysis" / "catalog.json").exists()
    return {"slug": slug, "files": items, "ingested": ingested,
            "favorites": _favorites(slug)}


def _footage_uses(slug: str, name: str) -> "dict":
    """What the cut would lose if this file went.

    Two ways a footage file is load-bearing, and only the first has ever
    bitten: it may be a b-roll CLIP some beat covers with, or it may hold
    the SPEECH TAKE a beat is built on. Deleting either used to succeed
    silently and surface at assemble — Caleb deleted four garage clips,
    one of them B184 covering BT93, and the cut failed validation with
    "unknown b-roll clip 'B184'" hours later (2026-08-25).
    """
    work = work_path(slug)
    name = os.path.basename(name)
    covers, beats = [], []
    clip_ids = set()
    bp = work / "analysis" / "broll.json"
    if bp.exists():
        try:
            for c in json.loads(bp.read_text()).get("clips", []):
                if c.get("file") == name:
                    clip_ids.add(c.get("id"))
        except ValueError:
            pass
    take_ids = set()
    tp = work / "analysis" / "takes.json"
    if tp.exists():
        try:
            for t in json.loads(tp.read_text()).get("takes", []):
                if t.get("file") == name:
                    take_ids.add(t.get("id"))
        except ValueError:
            pass
    ep = work / "edit_plan.json"
    if ep.exists() and (clip_ids or take_ids):
        try:
            plan = json.loads(ep.read_text())
        except ValueError:
            plan = {"beats": []}
        for b in plan.get("beats", []):
            for c in (b.get("broll") or []):
                if c.get("clip_id") in clip_ids:
                    # `at` travels with it: _broll_detach matches on
                    # POSITION as well as clip id, so a cover cannot be
                    # removed without saying where it sits
                    covers.append({"beat_id": b["id"],
                                   "clip_id": c.get("clip_id"),
                                   "at": float(c.get("at") or 0.0),
                                   "why": (c.get("why") or "")[:120]})
            if b.get("take_id") in take_ids:
                beats.append({"beat_id": b["id"], "take_id": b.get("take_id"),
                              "purpose": b.get("purpose", "")})
    return {"covers": covers, "beats": beats}


def _delete_footage(slug: str, name: str, force: bool = False,
                    log=print) -> "dict":
    """Remove one dropped clip — into footage/.trash, never gone for good.
    Removing a converted photo clip takes its source photo along.

    REFUSES when the cut is using the file (2026-08-25). Forcing removes
    the covers too, through `_broll_detach`, so the plan, timeline map,
    conform ledger, review queue and cover trash all stay in step and the
    cut is never knowingly left invalid. A beat built on a take from this
    file refuses even under force: losing a beat's take is a re-cut
    decision, not a cleanup, and nothing here is entitled to make it.
    """
    fdir = work_path(slug) / "footage"
    name = os.path.basename(name)
    p = fdir / name
    if not (p.is_file() or p.is_symlink()):
        raise IngestError("no clip named '%s'" % name)
    uses = _footage_uses(slug, name)
    if uses["beats"]:
        raise IngestError(
            "%s carries the take %s is built on — re-cut that beat first"
            % (name, ", ".join(b["beat_id"] for b in uses["beats"])))
    if uses["covers"] and not force:
        raise IngestError(
            "%s is in the cut: %s. Delete it and those covers go too."
            % (name, "; ".join("%s covers %s" % (c["clip_id"], c["beat_id"])
                               for c in uses["covers"])))
    detached = []
    for c in uses["covers"]:
        # detach FIRST: it trashes the cover before its proxy rebuild, so
        # an interrupted delete leaves an undo entry rather than a plan
        # pointing at a file that is already in the bin
        _broll_detach(slug, c["beat_id"], c["clip_id"], c["at"], log=log)
        detached.append(c)
    trash = fdir / ".trash"
    trash.mkdir(exist_ok=True)
    os.replace(p, _trash_dest(trash, p.name))
    removed = [name]
    if p.stem.endswith("_still"):
        for s in (fdir / "stills").glob(p.stem[:-6] + ".*"):
            os.replace(s, _trash_dest(trash, s.name))
            removed.append("stills/" + s.name)
    th = fdir / ".thumbs" / (name + ".jpg")
    if th.exists():
        th.unlink()
    return {"removed": removed, "detached": detached,
            "reingest": (work_path(slug) / "analysis" / "catalog.json").exists()}


def _clear_footage(slug: str) -> "dict":
    """Everything out — into .trash, recoverable like single removals."""
    fdir = work_path(slug) / "footage"
    if not fdir.is_dir():
        return {"removed": 0, "reingest": False}
    trash = fdir / ".trash"
    trash.mkdir(exist_ok=True)
    moved = 0
    for p in list(fdir.iterdir()):
        if p.is_file() and not p.name.startswith((".", "_tmp")):
            os.replace(p, _trash_dest(trash, p.name))
            moved += 1
    stills = fdir / "stills"
    if stills.is_dir():
        for p in list(stills.iterdir()):
            if p.is_file() and not p.name.startswith("."):
                os.replace(p, _trash_dest(trash, p.name))
                moved += 1
    thumbs = fdir / ".thumbs"
    if thumbs.is_dir():
        shutil.rmtree(thumbs)
    return {"removed": moved,
            "reingest": (work_path(slug) / "analysis" / "catalog.json").exists()}


def _save_story_brief(slug: str, target_minutes, chapters,
                      notes: str = "", location: str = "",
                      vo_share=None, subject: str = "",
                      origin: str = "footage",
                      delivery: "str | None" = None,
                      shorts_source: "str | None" = None) -> "dict":
    """The pre-production questionnaire (Caleb, 2026-08-23): target length
    and chapter count, briefed to the story-designer instead of left to its
    judgment. Bounds are the system's own: 12 chapters is the kit's chapter
    cap, and an hour is not an episode.

    It also records the FORMAT (2026-08-25): `origin` is how the video is
    made, `delivery` is where it ships, and orientation and edit-plan format
    are derived from delivery rather than decided by an agent halfway
    through.
    """
    from . import schemas
    try:
        mins = float(target_minutes)
        chaps = int(chapters)
    except (TypeError, ValueError):
        raise IngestError("brief needs numbers: target_minutes, chapters")
    # 15 seconds, not one minute. The old floor was written when every
    # episode was a visit, and it refused every short outright -- a 45
    # second Reel is 0.75 (Caleb, 2026-08-25).
    if not (0.25 <= mins <= 60):
        raise IngestError("target_minutes must be 0.25-60")
    if not (1 <= chaps <= 12):
        raise IngestError("chapters must be 1-12 (the kit's chapter cap)")
    # How much of the episode is narration rather than on camera. A DIAL,
    # not a doctrine: 0.6 is the default and 0.9 is a legitimate choice —
    # "my vision is fluid, 90% narrating voice for a few videos won't
    # hurt the content" (Caleb, 2026-08-24). Every VO second is a second
    # needing coverage, which is why the sourcing stage reads this too.
    try:
        vo = 0.60 if vo_share is None else float(vo_share)
    except (TypeError, ValueError):
        raise IngestError("vo_share must be a number between 0 and 1")
    if not (0.0 <= vo <= 1.0):
        raise IngestError("vo_share must be between 0 and 1")
    location = str(location or "").strip()
    if len(location) > 200:
        raise IngestError("location: keep it under 200 characters")
    # A visit names a PLACE; a script-led episode names a TOPIC ("why the
    # Foucault pendulum stopped"). Both fields survive because an episode
    # can carry both -- a topic anchored at a place -- and research reads
    # whichever it is given.
    subject = str(subject or "").strip()
    if len(subject) > 200:
        raise IngestError("subject: keep it under 200 characters")
    # The lane is stated, never sniffed from an empty footage folder: that
    # would make "I have not uploaded yet" and "there will never be
    # footage" the same state, and they lead to opposite pipelines.
    origin = str(origin or "footage").strip() or "footage"
    if origin not in schemas.ORIGINS:
        raise IngestError("origin must be 'footage' or 'script'")
    if origin == "script" and not subject and not location:
        raise IngestError("a script-led episode needs a subject -- with no "
                          "footage it is the only thing to research")
    # Delivery is sticky: editing the brief on the Story desk must not
    # silently re-shape a project back to 16:9 because the form did not
    # send the field. Creation decided it; absence means "unchanged".
    prev = {}
    bp = work_path(slug) / "story_brief.json"
    if bp.exists():
        try:
            prev = json.loads(bp.read_text())
        except ValueError:
            prev = {}
    delivery = str(delivery or prev.get("delivery") or "long").strip()
    if delivery not in schemas.DELIVERIES:
        raise IngestError("delivery must be 'long' or 'short'")
    shape = schemas.delivery_shape(delivery)
    brief = {"target_minutes": mins, "chapters": chaps, "vo_share": vo,
             "location": location, "subject": subject, "origin": origin,
             "delivery": delivery,
             # Derived, never asked for twice: one answer, one shape.
             "orientation": shape["orientation"], "format": shape["format"],
             "notes": str(notes or "").strip(), "ts": int(time.time())}
    if delivery == "short":
        src = shorts_source or prev.get("shorts_source") or "standalone"
        if src not in schemas.SHORTS_SOURCES:
            raise IngestError("shorts_source must be 'standalone' or 'derived'")
        brief["shorts_source"] = src
        if prev.get("derived_from"):
            brief["derived_from"] = prev["derived_from"]
    _write_json(bp, brief)
    return brief


def _section_file_prefix(kind: str, section_id: str, rev: int = 1) -> str:
    """The name a NEW recording of this section gets.

    vo_CH1-S2_r2_t3.webm <- section CH1.S2 at revision 2, take 3. Dots swap
    to dashes so the section id never fights the extension.

    Two things ride in this name on purpose:

    `kind` — `vo` recordings are a webcam capture of Caleb reading, and
    `schemas.validate_edit_plan` HARD-BLOCKS their picture from shipping
    (>=90% b-roll required). A `desk` recording is a real-camera
    performance whose face IS the shot. Four separate rules key off a
    `vo_` prefix, so a desk take carrying that prefix would be forbidden
    from ever appearing on screen — hence a different prefix, not a flag.

    `rev` — recordings match to sections by NAME. Without a revision in
    the name, rewriting a line leaves its old take matching the new words:
    the desk shows "recorded" and the wrong audio reaches the cut, silently.
    With it, a rewrite simply stops matching and reads "not recorded",
    which is the truth.
    """
    return "%s_%s_r%d_t" % ("desk" if kind == "desk" else "vo",
                            section_id.replace(".", "-"), int(rev or 1))


def _section_file_prefixes(kind: str, section_id: str,
                           rev: int = 1) -> "tuple":
    """Every name that counts as a recording OF this section at this rev.

    Revision 1 also answers to the pre-2026-08-24 name, which carried no
    `_r` segment at all -- hmns's recordings are on disk under it, and a
    sharpening that orphaned real files would be the exact bug this
    function exists to prevent.
    """
    canonical = _section_file_prefix(kind, section_id, rev)
    if int(rev or 1) == 1 and kind != "desk":
        return (canonical, "vo_%s_t" % section_id.replace(".", "-"))
    return (canonical,)


def _sec_rev(sec: "dict") -> int:
    """A section with no `rev` is revision 1 -- every script written before
    2026-08-24 is."""
    try:
        r = int(sec.get("rev") or 1)
    except (TypeError, ValueError):
        return 1
    return r if r >= 1 else 1


def _vo_file_prefix(section_id: str) -> str:
    """Back-compat shim: the legacy rev-less VO name. Still the answer for
    'what did we call these before revisions existed'."""
    return "vo_%s_t" % section_id.replace(".", "-")


_SESSION_RE = re.compile(r"^[0-9a-f-]{16,64}$")
SESSION_STEP_CAP = 400          # a long pass, not an unbounded transcript
SESSION_LINE_CAP = 512 * 1024   # past this a line is a tool result, not a step


def _session_dir() -> Path:
    """Where the CLI keeps this repo's transcripts: the project root with
    every separator turned into a dash."""
    return (Path.home() / ".claude" / "projects"
            / str(PROJECT_ROOT).replace("/", "-"))


def _session_transcript(session_id: str) -> "dict":
    """What an agent actually DID, read back from its transcript.

    The job log only carries the assistant's prose -- it says what the
    director concluded, never what it read to get there. The transcript
    has the tool calls, so "did it actually open research.json" stops
    being a matter of trust.

    Streamed and summarised rather than parsed whole: these files reach
    78 MB in this repo, and a desk that tried to load one would hang the
    engine. Only the shape of each step is kept, capped at
    SESSION_STEP_CAP.
    """
    if not _SESSION_RE.match(str(session_id or "")):
        raise IngestError("that is not a session id")
    path = _session_dir() / ("%s.jsonl" % session_id)
    if not path.exists():
        raise IngestError(
            "no transcript on disk for that session -- headless sessions "
            "are kept per project, and this one ran somewhere else")
    steps: "list[dict]" = []
    prompt = ""
    truncated = False
    with open(path) as f:
        for line in f:
            if len(steps) >= SESSION_STEP_CAP:
                truncated = True
                break
            # Most of the bulk is tool RESULTS, which this never renders:
            # 773 lines carrying 78 MB in the largest transcript here, so
            # a single line can be megabytes. Skip those before json.loads
            # rather than materialising one to learn its type.
            if len(line) > SESSION_LINE_CAP:
                continue
            try:
                ev = json.loads(line)
            except ValueError:
                continue
            etype = ev.get("type")
            if etype == "queue-operation" and not prompt:
                prompt = str(ev.get("content") or "")[:2000]
                continue
            if etype != "assistant":
                continue
            for block in ((ev.get("message") or {}).get("content") or []):
                btype = block.get("type")
                if btype == "text" and str(block.get("text") or "").strip():
                    steps.append({"kind": "said",
                                  "text": block["text"].strip()[:1200]})
                elif btype == "tool_use":
                    steps.append({"kind": "did",
                                  "tool": block.get("name") or "?",
                                  "target": _tool_target(block.get("input"))})
    return {"session_id": session_id, "prompt": prompt, "steps": steps,
            "truncated": truncated,
            "resume": "claude --resume %s" % session_id,
            "cwd": str(PROJECT_ROOT)}


def _tool_target(inp: "Any") -> str:
    """The one thing a tool call was AIMED at, for a one-line summary.
    Whole inputs are unbounded (a Write carries the entire file); this is
    the part a human scans."""
    if not isinstance(inp, dict):
        return ""
    for key in ("file_path", "path", "command", "pattern", "url", "query",
                "prompt", "skill"):
        v = inp.get(key)
        if isinstance(v, str) and v.strip():
            v = v.strip().replace(str(PROJECT_ROOT) + "/", "")
            return v[:160]
    return ""


def _asset_count(work: "Path") -> int:
    """Sourced files on disk. Cheap enough for the project row — it reads
    one small manifest, not the directory."""
    p = work / "assets" / "assets.json"
    if not p.exists():
        return 0
    try:
        return len(json.loads(p.read_text()).get("assets", []) or [])
    except ValueError:
        return 0


def _open_q_count(work: "Path") -> int:
    """How many of the director's questions still wait on Caleb. Cheap
    enough for the project row, which every desk polls."""
    from . import schemas
    def _load(name):
        p = work / name
        if not p.exists():
            return None
        try:
            return json.loads(p.read_text())
        except ValueError:
            return None
    return len(schemas.open_questions(_load("script_questions.json"),
                                      _load("script_feedback.json")))


def _script_answers(fb: "dict | None") -> "dict":
    """Every answer Caleb has ever given, flattened newest-wins.

    Answers ACCUMULATE across rounds rather than belonging to one: a
    question he settled in round 0 stays settled in round 3. Re-asking it
    is how a collaboration loop turns into a chore.
    """
    out: "dict" = {}
    for r in (fb or {}).get("rounds", []) or []:
        for qid, val in ((r or {}).get("answers") or {}).items():
            if str(val or "").strip():
                out[str(qid)] = val
    return out


def _save_script_answers(slug: str, answers: "dict",
                         notes: str = "") -> "dict":
    """Caleb answers the director's open questions. A round in its own
    right -- the writer's next pass reads it and says which defaults it
    fell back on for anything still blank."""
    from . import schemas
    if not isinstance(answers, dict):
        raise IngestError("answers must be an object of question id -> answer")
    work = work_path(slug)
    qp = work / "script_questions.json"
    if not qp.exists():
        raise IngestError("no open questions -- run the interview first")
    known = {str(q.get("id")) for q in
             json.loads(qp.read_text()).get("questions", [])
             if isinstance(q, dict)}
    unknown = [k for k in answers if str(k) not in known]
    if unknown:
        raise IngestError("no such question: %s" % ", ".join(sorted(unknown)))
    clean = {str(k): v for k, v in answers.items() if str(v or "").strip()}
    if not clean and not str(notes or "").strip():
        raise IngestError("nothing to send -- answer a question or write a note")
    path = work / "script_feedback.json"
    fb = json.loads(path.read_text()) if path.exists() else {"rounds": []}
    fb["rounds"].append({"ts": int(time.time()),
                         "decision": "answers",
                         "answers": clean,
                         "notes": str(notes or "").strip()})
    _write_json(path, fb)
    return fb


def _save_script_feedback(slug: str, notes: str, decision: str) -> "dict":
    """Caleb's verdict on a draft. 'direction' asks for a revision steered
    by the notes; 'approve' LOCKS the script.

    Locking is a POST, not a job: it costs no session and spawns nothing.
    And re-approving an already-locked script is a NO-OP rather than a new
    round -- the desk gave no post-approval feedback on the Story loop
    2026-08-23, Caleb clicked approve six times, and six identical rounds
    landed in the file. That bug does not get rebuilt here.
    """
    from . import schemas
    if decision not in ("direction", "approve"):
        raise IngestError("decision must be 'direction' or 'approve'")
    work = work_path(slug)
    sp = work / "script.json"
    if not sp.exists():
        raise IngestError("no script yet -- write a draft first")
    if decision == "direction" and not str(notes or "").strip():
        raise IngestError("write the direction you want the revision to take")
    script = json.loads(sp.read_text())
    path = work / "script_feedback.json"
    fb = json.loads(path.read_text()) if path.exists() else {"rounds": []}
    if decision == "approve" and script.get("locked"):
        return fb                                   # idempotent
    if decision == "direction" and script.get("locked"):
        raise IngestError("the script is approved -- unlock it to revise")
    fb["rounds"].append({"ts": int(time.time()),
                         "round": script.get("round"),
                         "decision": decision,
                         "notes": str(notes or "").strip()})
    _write_json(path, fb)
    if decision == "approve":
        script["locked"] = True
        script["approved_ts"] = int(time.time())
        _write_json(sp, script)
        # Approval is what "the words are settled" MEANS, so it is the
        # honest trigger for the one stage that spends money against them.
        # This was chained off the script JOB finishing, which fires when a
        # draft lands -- pricing pictures for lines about to be rewritten,
        # and, once the script lane began refusing an unapproved draft,
        # being declined every time.
        #
        # It proposes and STOPS: approving a download is a licence decision
        # and Caleb's alone. A guard that refuses (not ingested yet, no
        # pictures needed) declines politely, which is the system working.
        # Reported, never swallowed: the approve itself must still succeed
        # if the follower cannot start, but a silent miss here looks exactly
        # like a stage that ran and found nothing. `fb` is already on disk
        # by this point, so this key rides back in the response only.
        try:
            from . import jobs as _jobs_auto
            job = _jobs_auto.start("sourcing", slug)
            fb["sourcing"] = {"queued": True, "job": job.get("id")}
        except Exception as e:
            fb["sourcing"] = {"queued": False, "why": str(e)[:200]}
    return fb


def _recheck_script(slug: str) -> "dict":
    """Run the script's own gates against whatever is on disk RIGHT NOW.

    The job validates what it wrote, which is enough while the job is the
    only writer. A resumed session is not the job: it edits the same
    files with the same authority and answers to nothing, so a script
    could reach the cut having never passed the bar. This is the way
    back -- it re-runs exactly what the job runs, and reports rather
    than refusing, because by this point the words are already on disk.
    """
    from . import schemas
    work = work_path(slug)
    p = work / "script.json"
    if not p.exists():
        raise IngestError("no script yet")
    script = json.loads(p.read_text())
    takes = None
    tp = analysis_dir(slug) / "takes.json"
    if tp.exists():
        try:
            takes = json.loads(tp.read_text())
        except ValueError:
            takes = None
    brief = {}
    bp = work / "story_brief.json"
    if bp.exists():
        try:
            brief = json.loads(bp.read_text())
        except ValueError:
            brief = {}
    errors = schemas.validate_script(script, takes)
    notes = schemas.script_notes(script, brief.get("vo_share"),
                                 origin=brief.get("origin", "footage"))
    return {"slug": slug, "errors": errors, "notes": notes,
            "ok": not errors and not notes,
            "vo_share": round(schemas.vo_share(script), 3),
            "target": brief.get("vo_share"),
            "locked": bool(script.get("locked"))}


def _unlock_script(slug: str) -> "dict":
    """Reopen an approved script. Deliberately its own verb: approving is
    what tells every later stage the words are final, so undoing it should
    be a decision Caleb takes on purpose, not a side effect of typing."""
    work = work_path(slug)
    sp = work / "script.json"
    if not sp.exists():
        raise IngestError("no script yet")
    script = json.loads(sp.read_text())
    script["locked"] = False
    script.pop("approved_ts", None)
    _write_json(sp, script)
    return script


def _script_state(slug: str) -> "dict":
    """script.json plus per-vo-section recording status. A section is
    recorded when the catalog holds a SPEECH file named for it -- matching
    is by NAME, deterministically: the teleprompter names its uploads, so
    there is no transcript fuzz to argue with."""
    from . import schemas
    work = work_path(slug)
    p = work / "script.json"
    questions = fb = None
    if (work / "script_questions.json").exists():
        try:
            questions = json.loads((work / "script_questions.json").read_text())
        except ValueError:
            questions = None
    if (work / "script_feedback.json").exists():
        try:
            fb = json.loads((work / "script_feedback.json").read_text())
        except ValueError:
            fb = None
    # The desk needs these whether or not a script exists yet: the interview
    # arrives BEFORE any prose, and that is the whole point of round 0.
    loop = {"questions": questions,
            "feedback": fb,
            "open": schemas.open_questions(questions, fb),
            "blocking": schemas.blocking_questions(questions, fb),
            "answers": _script_answers(fb)}
    if not p.exists():
        return dict(loop, slug=slug, script=None)
    script = json.loads(p.read_text())
    cat_p = analysis_dir(slug) / "catalog.json"
    files = (json.loads(cat_p.read_text()).get("files", [])
             if cat_p.exists() else [])
    by_prefix = {}
    for f in files:
        by_prefix.setdefault(f["name"], f)
    for ch in script.get("chapters", []):
        for sec in ch.get("sections", []):
            kind = sec.get("kind")
            # `oncamera` quotes a take that already exists; there is nothing
            # to record. `vo` and `desk` are both performed later.
            if kind not in ("vo", "desk"):
                continue
            sid = str(sec.get("id", ""))
            rev = _sec_rev(sec)
            sec["rev"] = rev
            sec["file_prefix"] = _section_file_prefix(kind, sid, rev)
            prefixes = _section_file_prefixes(kind, sid, rev)
            recs = [f for name, f in by_prefix.items()
                    if name.startswith(prefixes)]
            sec["recordings"] = sorted(f["name"] for f in recs)
            sec["recorded"] = any(f.get("class") == "speech" for f in recs)
            # ingest's real duration outranks the 150wpm estimate
            spoken = [f for f in recs if f.get("class") == "speech"]
            if spoken:
                sec["recorded_s"] = round(
                    max(f.get("duration", 0) for f in spoken), 1)
            # A recording of an EARLIER revision is not this line. It stays
            # on disk as history, and the desk says "the line changed" --
            # never "missing", which would read as an error the writer made
            # rather than a consequence of the rewrite Caleb asked for.
            if not sec["recorded"] and rev > 1:
                earlier = tuple(p for r in range(1, rev)
                                for p in _section_file_prefixes(kind, sid, r))
                older = [n for n in by_prefix if n.startswith(earlier)]
                sec["stale_recordings"] = sorted(older)
                sec["stale"] = bool(older)
    # Carry the loop through. Returning only the script here dropped the
    # questions and the rounds the moment a draft existed -- which is
    # exactly when they matter, since every draft ships with its own open
    # questions and the approve gate lives beside them.
    return dict(loop, slug=slug, script=script)


def _save_script_section(slug: str, section_id: str, text: str) -> "dict":
    """Caleb rewrites a VO line in his own voice; est_s re-estimates from
    the new word count. oncamera text is a QUOTE of a take -- editing the
    quote would not change the take, so it is refused rather than lied
    about."""
    from . import schemas
    work = work_path(slug)
    p = work / "script.json"
    if not p.exists():
        raise IngestError("no script yet")
    script = json.loads(p.read_text())
    text = str(text or "").strip()
    if not text:
        raise IngestError("a section cannot be empty")
    for ch in script.get("chapters", []):
        for sec in ch.get("sections", []):
            if str(sec.get("id")) == section_id:
                if sec.get("kind") not in ("vo", "desk"):
                    raise IngestError(
                        "only written sections are editable -- an oncamera "
                        "section quotes its take; re-pick the take instead")
                if text == str(sec.get("text") or ""):
                    return sec          # no edit, no revision
                sec["text"] = text
                words = len(text.split())
                sec["est_s"] = round(words / schemas.SPEAKING_WPM * 60, 1)
                # The words changed, so any recording of the OLD words is no
                # longer this line. Bumping the revision is what makes the
                # desk say so -- without it the old take keeps matching by
                # name and ships under words nobody ever said.
                sec["rev"] = _sec_rev(sec) + 1
                _write_json(p, script)
                return sec
    raise IngestError("unknown section '%s'" % section_id)


def _story_state(slug: str) -> "dict":
    work = work_path(slug)
    stories = fb = plan_summary = brief = research = None
    if (work / "story_brief.json").exists():
        brief = json.loads((work / "story_brief.json").read_text())
    if (work / "research.json").exists():
        try:
            r = json.loads((work / "research.json").read_text())
            research = {"facts": len(r.get("facts", [])),
                        "location": r.get("location", ""),
                        "ts": r.get("ts")}
        except ValueError:
            research = {"facts": 0, "location": "", "ts": None}
    if (work / "stories.json").exists():
        stories = json.loads((work / "stories.json").read_text())
    if (work / "story_feedback.json").exists():
        fb = json.loads((work / "story_feedback.json").read_text())
    if (work / "edit_plan.json").exists():
        plan = json.loads((work / "edit_plan.json").read_text())
        plan_summary = {"beats": len(plan.get("beats", [])),
                        "chapters": [c.get("title", "")
                                     for c in plan.get("chapters", [])]}
    return {"slug": slug, "stories": stories, "brief": brief,
            "research": research,
            "feedback": fb or {"rounds": []}, "plan": plan_summary}


def _save_story_feedback(slug: str, choice: "str | None", notes: str,
                         decision: str) -> "dict":
    """Caleb's verdict on a pitch round — the story designer's next input.
    'direction' asks for a fresh round steered by the notes; 'approve'
    green-lights the chosen option (notes still travel with it)."""
    if decision not in ("direction", "approve"):
        raise IngestError("decision must be 'direction' or 'approve'")
    work = work_path(slug)
    stories = None
    if (work / "stories.json").exists():
        stories = json.loads((work / "stories.json").read_text())
    if decision == "approve":
        ids = {o.get("id") for o in (stories or {}).get("options", [])}
        if choice not in ids:
            raise IngestError("pick one of the pitched options to approve")
    path = work / "story_feedback.json"
    fb = json.loads(path.read_text()) if path.exists() else {"rounds": []}
    # Idempotent approve: re-approving the already-approved option is a
    # no-op, not a new round. Found live 2026-08-23 — the desk gave no
    # post-approval state, Caleb clicked six times, and six identical
    # rounds landed in the file.
    last = fb["rounds"][-1] if fb["rounds"] else None
    if (decision == "approve" and last
            and last.get("decision") == "approve"
            and last.get("choice") == choice
            and not (notes or "").strip()):
        return fb
    fb["rounds"].append({"ts": int(time.time()),
                         "round": (stories or {}).get("round"),
                         "choice": choice, "notes": (notes or "").strip(),
                         "decision": decision})
    _write_json(path, fb)
    return fb


# --- Ideas (scout) + Assets (sourcer) desks --------------------------------
# Both follow the story-loop pattern: the desk collects Caleb's requests and
# verdicts into JSON, the agents run in the Claude session and write their
# results back, the desk renders them. Ideas are CHANNEL-level (work/_scout,
# underscore keeps it out of the project list); assets are per-project.


def _scout_dir() -> Path:
    d = work_path("_scout")
    d.mkdir(parents=True, exist_ok=True)
    return d


def _ideas_state() -> "dict":
    d = _scout_dir()
    ideas = None
    if (d / "ideas.json").exists():
        ideas = json.loads((d / "ideas.json").read_text())
    state = {}
    if (d / "ideas_state.json").exists():
        state = json.loads((d / "ideas_state.json").read_text())
    return {"ideas": ideas, "state": state}


def _save_idea_state(idea_id: str, status: str, notes: str) -> None:
    if status not in ("saved", "dismissed", "develop"):
        raise IngestError("status must be saved, dismissed, or develop")
    d = _scout_dir()
    p = d / "ideas_state.json"
    state = json.loads(p.read_text()) if p.exists() else {}
    state[idea_id] = {"status": status, "notes": (notes or "").strip(),
                      "ts": int(time.time())}
    _write_json(p, state)


# --- the episode plan (pre-shoot planning, Studio Planner desk) -----------
# work/<slug>/plan.json is an agent-readable artifact like edit_plan.json:
# the story-designer may read it for intent, and Caleb prints it as the
# shoot-day sheet. The server owns nothing here except shape validation —
# identity comes from the slug, and the whole document is client-editable
# because unlike a card there is no baked artifact downstream to protect.

_PLAN_CHECKLIST_SOURCES = ("card", "brand", "custom")


# --- timeline sync (the Overlays desk's "Sync from Resolve" button) --------

def _sync_timeline_cards(slug: str) -> "dict":
    """Dump the live Resolve timeline over the bridge and rewrite
    work/<slug>/timeline_cards.json — the placements the Overlays desk
    mirrors. Non-destructive on purpose: this refreshes WHERE cards sit in
    the cut and which are in it; it never rewrites graphics_plan.json.

    Needs Resolve running with the project open. ensure_bridge() auto-starts
    the in-app bridge (one AppleScript menu click; Accessibility granted).

    What breaks if this is wrong: the desk confidently shows a stale cut —
    worse than showing none, which is why the sidecar carries project,
    timeline and a timestamp the desk displays.
    """
    from . import resolve_api as ra
    import re as _re, time as _time
    ra.ensure_bridge()
    # No escape sequences in Lua the Python layer could collapse: newline is
    # string.char(10), fields join on "|" (the bridge-escaping incident).
    lua = chr(10).join([
        'local function S(v) if v == nil then return "-" end return tostring(v) end',
        'local pm = resolve:GetProjectManager()',
        'local proj = pm:GetCurrentProject()',
        'if not proj then return error("no project open in Resolve") end',
        'local tl = proj:GetCurrentTimeline()',
        'if not tl then return error("no timeline open in Resolve") end',
        'local out = {"PROJECT|" .. proj:GetName(), "TIMELINE|" .. tl:GetName(),',
        '  "FPS|" .. S(tl:GetSetting("timelineFrameRate")),',
        '  "STARTFRAME|" .. S(tl:GetStartFrame())}',
        'for t = 1, tl:GetTrackCount("video") do',
        '  for _, it in ipairs(tl:GetItemListInTrack("video", t) or {}) do',
        '    local ok, mpi = pcall(function() return it:GetMediaPoolItem() end)',
        '    local fp = "-"',
        '    if ok and mpi then fp = S(mpi:GetClipProperty("File Path")) end',
        '    out[#out+1] = "ITEM|V" .. t .. "|" .. S(it:GetStart()) .. "|" ..',
        '      S(it:GetEnd()) .. "|" .. fp',
        '  end',
        'end',
        'return table.concat(out, string.char(10))',
    ])
    raw = ra.send("timeline_sync", lua, timeout=180)

    meta = {"project": "?", "timeline": "?", "fps": 24.0, "start": 0}
    rows = []
    for line in raw.splitlines():
        parts = line.split("|")
        if parts[0] == "PROJECT":
            meta["project"] = parts[1]
        elif parts[0] == "TIMELINE":
            meta["timeline"] = parts[1]
        elif parts[0] == "FPS":
            try:
                meta["fps"] = float(parts[1])
            except ValueError:
                pass
        elif parts[0] == "STARTFRAME":
            try:
                meta["start"] = int(parts[1])
            except ValueError:
                pass
        elif parts[0] == "ITEM" and len(parts) >= 5:
            rows.append(parts)

    # Map a referenced file to a card id: graphics/CARDxx directly; exports
    # by version-stripped basename against the sidecar, so an item still on
    # an older _vN resolves to its card rather than vanishing.
    sidecar_path = work_path(slug) / "exports" / "overlays" / ".export_hashes.json"
    sidecar = json.loads(sidecar_path.read_text()) if sidecar_path.exists() else {}
    strip = lambda n: _re.sub(r"_v\d+(?=[.]mov$)", "", n)
    by_base = {strip(e["file"]): cid for cid, e in sidecar.items()}

    fps, start = meta["fps"] or 24.0, meta["start"]
    cards = {}
    for _tag, track, s_f, e_f, fp in rows:
        base = fp.rsplit("/", 1)[-1]
        cid = None
        if "/graphics/" in fp and base.startswith("CARD"):
            cid = base.split(".")[0]
        elif "/exports/overlays/" in fp:
            cid = by_base.get(strip(base))
        if not cid:
            continue
        try:
            s_i, e_i = int(s_f), int(e_f)
        except ValueError:
            continue
        cards[cid] = {"record_s": round((s_i - start) / fps, 2),
                      "duration_s": round((e_i - s_i) / fps, 2),
                      "track": track}

    out = {"project": meta["project"], "timeline": meta["timeline"],
           "synced_ts": int(_time.time()), "cards": cards}
    _write_json(work_path(slug) / "timeline_cards.json", out)
    return {"ok": True, "project": meta["project"],
            "timeline": meta["timeline"], "placed": len(cards)}


def _plan_path(slug: str) -> Path:
    return work_path(slug) / "plan.json"


def _plan_state(slug: str) -> "dict":
    p = _plan_path(slug)
    if not p.exists():
        return {"slug": slug, "exists": False, "plan": None}
    return {"slug": slug, "exists": True,
            "plan": json.loads(p.read_text())}


def _chapter_title(text: str) -> str:
    """'CH2 · The park — Central Park at dusk…' -> 'The park'. Tolerant:
    freeform text falls back to its first clause, trimmed to title length."""
    import re as _re
    t = str(text or "").strip()
    m = _re.match(r"^CH\s?\d{1,2}\s*[·:.]\s*(.*)$", t, _re.I)
    if m:
        t = m.group(1)
    head = t.split(" — ")[0].strip()
    return (head[:60] + "…") if len(head) > 60 else (head or "Chapter")


def _seed_plan(slug: str) -> "dict":
    """Prefill the shoot plan from the APPROVED story (Caleb, 2026-08-23):
    the plan stops being pre-shoot guesswork and becomes the capture list
    the chosen direction actually needs. Chapters come from the approved
    option's outline (title + its rough-cut text as the first shot to
    cover); research angles land as ninth-room candidates; the brief's
    location fills the place. Refuses to clobber: a plan that already has
    chapters is someone's work, not a seed target.
    """
    work = work_path(slug)
    fb_p = work / "story_feedback.json"
    rounds = (json.loads(fb_p.read_text()).get("rounds", [])
              if fb_p.exists() else [])
    if not rounds or rounds[-1].get("decision") != "approve":
        raise IngestError("no approved story yet — approve a direction on "
                          "the Story desk first")
    choice = rounds[-1].get("choice")

    plan_p = work / "plan.json"
    plan = json.loads(plan_p.read_text()) if plan_p.exists() else {}
    if plan.get("chapters"):
        raise IngestError("the shoot plan already has chapters — seeding "
                          "would clobber them; clear them first if you "
                          "really want the story's")

    chapters = []
    script_p = work / "script.json"
    if script_p.exists():
        # The SCRIPT is the approved artifact and it survives rounds —
        # stories.json is overwritten per round, so the approved option can
        # vanish from it (found live: approval said S2, stories.json held
        # round 2's S4-S6). It is also the richer seed: real chapter titles,
        # and each VO line names exactly the b-roll that must cover it.
        script = json.loads(script_p.read_text())
        for ch in script.get("chapters", [])[:12]:
            shots = [{"desc": "Cover with b-roll: %s" % sec.get("text", "").strip()}
                     for sec in ch.get("sections", [])
                     if sec.get("kind") == "vo" and sec.get("text", "").strip()][:6]
            if not shots:
                first = next((sec.get("text", "").strip()
                              for sec in ch.get("sections", [])
                              if sec.get("text", "").strip()), "")
                if first:
                    shots = [{"desc": "Story: %s" % first}]
            chapters.append({"title": str(ch.get("title") or "Chapter"),
                             "shots": shots, "card_ideas": []})
    else:
        stories = json.loads((work / "stories.json").read_text()) \
            if (work / "stories.json").exists() else {}
        option = next((o for o in stories.get("options", [])
                       if o.get("id") == choice), None)
        if option is None:
            raise IngestError(
                "approved option '%s' is not in the current stories.json "
                "round and no script exists — Write the script first, or "
                "re-approve a current pitch" % choice)
        for item in (option.get("beats_outline") or [])[:12]:
            text = item.get("text", "") if isinstance(item, dict) else str(item)
            chapters.append({
                "title": _chapter_title(text),
                # the rough cut IS the first thing to cover
                "shots": [{"desc": "Story: %s" % text.strip()}]
                         if text.strip() else [],
                "card_ideas": [],
            })

    angles = []
    r_p = work / "research.json"
    if r_p.exists():
        try:
            angles = [str(a).strip() for a in
                      json.loads(r_p.read_text()).get("angles", []) if a][:12]
        except ValueError:
            pass

    brief_p = work / "story_brief.json"
    location = ""
    if brief_p.exists():
        try:
            location = str(json.loads(brief_p.read_text())
                           .get("location") or "").strip()
        except ValueError:
            pass

    plan.setdefault("place", "")
    if location and not plan["place"]:
        plan["place"] = location
    plan.setdefault("visit_date", "")
    plan["chapters"] = chapters
    existing = plan.get("ninth_room_candidates") or []
    plan["ninth_room_candidates"] = existing + [a for a in angles
                                                if a not in existing]
    plan.setdefault("checklist", [])
    plan.setdefault("notes", "")
    plan["slug"] = slug
    plan["updated"] = int(time.time())
    errs = _validate_plan(plan)
    if errs:
        raise IngestError("seeded plan invalid: " + "; ".join(errs[:3]))
    _write_json(plan_p, plan)
    return plan


def _validate_plan(plan: "dict") -> "list":
    """Same posture as pipeline.schemas: name every problem, reject on any.

    What breaks if this is loose: the Studio writes a malformed plan, the
    story-designer agent reads it mid-produce, and the failure surfaces two
    stages later as a nonsense edit plan instead of here as a 400.
    """
    errors = []
    if not isinstance(plan, dict):
        return ["plan: not an object"]
    for key in ("place", "notes"):
        if key in plan and not isinstance(plan[key], str):
            errors.append("plan: '%s' must be a string" % key)
    if "visit_date" in plan and plan["visit_date"]:
        import re as _re
        if not _re.match(r"^\d{4}-\d{2}-\d{2}$", str(plan["visit_date"])):
            errors.append("plan: visit_date must be YYYY-MM-DD")
    chapters = plan.get("chapters", [])
    if not isinstance(chapters, list):
        errors.append("plan: 'chapters' must be a list")
        chapters = []
    if len(chapters) > 12:
        errors.append("plan: %d chapters — the door meter caps at 12"
                      % len(chapters))
    for i, ch in enumerate(chapters):
        where = "chapters[%d]" % i
        if not isinstance(ch, dict):
            errors.append(where + ": not an object"); continue
        if not isinstance(ch.get("title", ""), str):
            errors.append(where + ": 'title' must be a string")
        for lk, fields in (("shots", ("desc",)), ("card_ideas", ("kit_type",))):
            items = ch.get(lk, [])
            if not isinstance(items, list):
                errors.append("%s: '%s' must be a list" % (where, lk)); continue
            for j, it in enumerate(items):
                if not isinstance(it, dict):
                    errors.append("%s.%s[%d]: not an object" % (where, lk, j))
                    continue
                for f in fields:
                    if not isinstance(it.get(f, ""), str):
                        errors.append("%s.%s[%d]: '%s' must be a string"
                                      % (where, lk, j, f))
        # card_ideas must name real kit screens, same check the graphics
        # validator gained — a typo here otherwise survives to bake time.
        from .overlay_kit import RENDERERS
        for j, it in enumerate(ch.get("card_ideas", []) or []):
            if isinstance(it, dict) and it.get("kit_type") and \
                    it["kit_type"] not in RENDERERS:
                errors.append("%s.card_ideas[%d]: kit_type '%s' is not a "
                              "kit screen" % (where, j, it["kit_type"]))
    for lk in ("ninth_room_candidates", "checklist"):
        items = plan.get(lk, [])
        if not isinstance(items, list):
            errors.append("plan: '%s' must be a list" % lk)
    for j, it in enumerate(plan.get("checklist", []) or []):
        if isinstance(it, dict) and it.get("source") and \
                it["source"] not in _PLAN_CHECKLIST_SOURCES:
            errors.append("checklist[%d]: source '%s' not in %s"
                          % (j, it["source"], _PLAN_CHECKLIST_SOURCES))
    return errors


def _save_plan(slug: str, plan: "dict") -> "dict":
    errors = _validate_plan(plan)
    if errors:
        raise IngestError("plan failed validation:\n  " + "\n  ".join(errors))
    plan = dict(plan)
    plan["slug"] = slug          # identity is the server's, not the client's
    plan["updated"] = int(time.time())
    _write_json(_plan_path(slug), plan)
    return _plan_state(slug)


def _still_to_clip(inp: Path, clip: Path) -> None:
    """A still image becomes a 6s UHD clip the b-roll pipeline can place."""
    from . import graphics as graphics_mod
    proc = subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-t", "6",
         "-i", str(inp),
         "-vf", "scale=3840:2160:force_original_aspect_ratio=increase,"
                "crop=3840:2160,fps=24,format=yuv420p",
         *graphics_mod.h264_encode_args(3840, crf=18),
         "-movflags", "+faststart", str(clip)],
        capture_output=True, text=True)
    if proc.returncode != 0:
        raise IngestError("still conversion failed for %s: %s"
                          % (inp.name, proc.stderr[-200:]))


def _capture_article(slug: str, url: str, log=print) -> "dict":
    """Screenshot an article and file it as a CITATION.

    Not stock: it carries no reuse licence and never will. It is shown
    as evidence for a narrated claim with its source legible in frame,
    which is why the row records the headline, publication and capture
    time rather than a licence it does not have.
    """
    from . import capture as capture_mod
    adir = work_path(slug) / "assets"
    row = capture_mod.capture_article(url, adir, log=log)
    capture_mod.append_to_manifest(adir, row)
    return row


def _asset_round_verdict(slug: str, ts, status: str,
                         log=print) -> "dict":
    """Approve or skip one sourcing proposal.

    The human gate between proposing and fetching. The agent that judges
    what the library lacks does not also get to decide what is
    downloaded — a licence is a commitment, and a file on disk before
    this call is that commitment made on Caleb's behalf (2026-08-24).
    """
    if status not in ("approved", "skipped", "proposed"):
        raise IngestError("status must be approved, skipped or proposed")
    p = work_path(slug) / "asset_requests.json"
    if not p.exists():
        raise IngestError("no proposals on file")
    doc = json.loads(p.read_text())
    rounds = doc.get("rounds", [])
    hit = next((r for r in rounds if str(r.get("ts")) == str(ts)), None)
    if hit is None:
        raise IngestError("no proposal '%s'" % ts)
    if hit.get("status") == "done" and status != "approved":
        # a fetched round may be RE-OPENED for another pass — the rules
        # changed on 2026-08-25 (video first) and re-sourcing a gap is a
        # normal thing to want. It may not go back to proposed or
        # skipped, which would orphan the asset already on disk.
        raise IngestError("that round is already fetched — approve it "
                          "again to re-source, or leave it")
    refetch = hit.get("status") == "done" and status == "approved"
    hit["status"] = status
    _write_json(p, doc)
    n = sum(1 for r in rounds if r.get("status") == "approved")
    log("[sourcing] round %s -> %s%s (%d approved and waiting)"
        % (ts, status, " (RE-SOURCE)" if refetch else "", n))
    return {"ts": hit.get("ts"), "status": status, "approved": n}


def _assets_state(slug: str) -> "dict":
    work = work_path(slug)
    adir = work / "assets"
    man = {"assets": []}
    if (adir / "assets.json").exists():
        man = json.loads((adir / "assets.json").read_text())
    reqs = {"rounds": []}
    if (work / "asset_requests.json").exists():
        reqs = json.loads((work / "asset_requests.json").read_text())
    thumbs = adir / ".thumbs"
    items = []
    for a in man.get("assets", []):
        p = adir / a.get("file", "")
        if not p.is_file():
            continue
        # a citation stays a citation: nothing downstream may treat a
        # screenshotted newspaper as footage we are free to cut with
        kind = (a.get("kind") if a.get("kind") == "citation"
                else ("video" if p.suffix.lower() in _VIDEO_UP else "image"))
        thumb = None
        if kind == "citation":
            thumb = str(p)          # the screenshot IS its own thumbnail
        elif kind == "video":
            thumbs.mkdir(exist_ok=True)
            th = thumbs / (p.name + ".jpg")
            if not th.exists() or th.stat().st_mtime < p.stat().st_mtime:
                subprocess.run(
                    ["ffmpeg", "-y", "-loglevel", "error", "-ss", "0.5",
                     "-i", str(p), "-frames:v", "1", "-vf", "scale=320:-2",
                     str(th)], capture_output=True)
            thumb = str(th) if th.exists() else None
        else:
            thumb = str(p)
        # servable, slug-relative paths — `thumb` is an absolute filesystem
        # path the browser cannot load, and the desk reaches media through
        # the /pymedia rewrite (non-negotiable #4)
        rel = "assets/%s" % a.get("file", "")
        thumb_rel = rel if kind in ("image", "citation") else (
            "assets/.thumbs/%s.jpg" % p.name if thumb else None)
        items.append(dict(a, kind=kind, thumb=thumb, media=rel,
                          thumb_rel=thumb_rel, size=p.stat().st_size))
    # Which catalogued b-roll clip each promoted asset became, so the
    # Library can attach it to a beat without the desk having to guess at
    # filenames (Caleb, 2026-08-25: "associate the uploaded material to a
    # clip or beat"). An asset with no clip_id has not been promoted and
    # analysed yet, and the desk says so rather than offering a dead verb.
    by_file = {}
    bp = work / "analysis" / "broll.json"
    if bp.exists():
        try:
            for c in json.loads(bp.read_text()).get("clips", []):
                by_file[c.get("file")] = c.get("id")
        except ValueError:
            pass
    used = set()
    ep = work / "edit_plan.json"
    beats = []
    if ep.exists():
        try:
            plan = json.loads(ep.read_text())
            for b in plan.get("beats", []):
                for c in (b.get("broll") or []):
                    used.add(c.get("clip_id"))
            takes = {}
            tk = work / "analysis" / "takes.json"
            if tk.exists():
                takes = {t["id"]: (t.get("transcript") or "")
                         for t in json.loads(tk.read_text()).get("takes", [])}
            for b in plan.get("beats", []):
                beats.append({"id": b["id"], "purpose": b.get("purpose", ""),
                              "says": takes.get(b.get("take_id"), "")[:90],
                              "covers": len(b.get("broll") or [])})
        except ValueError:
            pass
    for it in items:
        stem = Path(it.get("file", "")).stem
        cid = by_file.get(it.get("file")) or by_file.get(stem + "_still.mp4")
        it["clip_id"] = cid
        it["in_cut"] = bool(cid and cid in used)
    return {"slug": slug, "assets": items, "requests": reqs, "beats": beats}


def _request_assets(slug: str, text: str) -> "dict":
    text = (text or "").strip()
    if not text:
        raise IngestError("describe what you need")
    work = work_path(slug)
    p = work / "asset_requests.json"
    reqs = json.loads(p.read_text()) if p.exists() else {"rounds": []}
    reqs["rounds"].append({"ts": int(time.time()), "text": text,
                           "status": "open"})
    _write_json(p, reqs)
    return reqs


def _delete_asset(slug: str, aid: str) -> None:
    adir = work_path(slug) / "assets"
    man_p = adir / "assets.json"
    if not man_p.exists():
        raise IngestError("no assets manifest")
    man = json.loads(man_p.read_text())
    row = next((a for a in man.get("assets", []) if a.get("id") == aid), None)
    if row is None:
        raise IngestError("no asset '%s'" % aid)
    p = adir / row.get("file", "")
    if p.is_file():
        trash = adir / ".trash"
        trash.mkdir(exist_ok=True)
        os.replace(p, _trash_dest(trash, p.name))
    man["assets"] = [a for a in man["assets"] if a.get("id") != aid]
    _write_json(man_p, man)


def _use_asset(slug: str, aid: str) -> "dict":
    """Copy an asset into footage/ so it rides the b-roll pipeline; images
    go through the same 6s-clip conversion as dropped photos."""
    work = work_path(slug)
    adir = work / "assets"
    man = json.loads((adir / "assets.json").read_text())
    row = next((a for a in man.get("assets", []) if a.get("id") == aid), None)
    if row is None:
        raise IngestError("no asset '%s'" % aid)
    src = adir / row["file"]
    if not src.is_file():
        raise IngestError("asset file missing: %s" % row["file"])
    fdir = work / "footage"
    fdir.mkdir(parents=True, exist_ok=True)
    if src.suffix.lower() in _VIDEO_UP:
        name = _uniquify(fdir, src.name)
        # LINK, don't copy: a copy leaves the camera's sibling .LRF proxy
        # behind, and broll._prefer_proxy then decodes 4K HEVC for every
        # contact sheet — measured 8.8s against 0.5s (2026-08-24). The
        # link also saves the footage's whole weight on disk.
        os.symlink(src.resolve(), fdir / name)
    else:
        stills = fdir / "stills"
        stills.mkdir(exist_ok=True)
        sname = _uniquify(stills, src.name)
        shutil.copy2(src, stills / sname)
        name = Path(sname).stem + "_still.mp4"
        _still_to_clip(stills / sname, fdir / name)
    # Arm the auto-analysis, exactly as a footage drop does. Promoting an
    # asset used to leave the shelf and the catalogue out of step until
    # someone remembered to re-analyze by hand (Caleb, 2026-08-25: "are we
    # able to auto analyze the uploaded assets?"). The debounce means a
    # run of promotions costs ONE analysis, not one each — and a cached
    # re-analysis of a 367-file project is ~21s and, since the catalogue
    # merges rather than rebuilds, destroys nothing.
    reingest = (work / "analysis" / "catalog.json").exists()
    if reingest:
        from . import jobs as _jobs_auto
        _jobs_auto.note_upload(slug)
    return {"as": name, "reingest": reingest, "analyzing": reingest}


# --- Captions desk ---------------------------------------------------------
# Safeguard editor for caption text. The text is the source of truth
# (captions.json); timing always comes from whisper via align_words, so an
# edit here re-aligns, re-bakes the beat's caption clip, and re-proxies the
# beat — the exact code produce runs, nothing can drift.


def _captions_state(slug: str) -> "dict":
    work = work_path(slug)
    out = analysis_dir(slug)
    if not ((out / "timeline_map.json").exists()
            and (work / "edit_plan.json").exists()):
        return {"slug": slug, "beats": []}
    tl = json.loads((out / "timeline_map.json").read_text())
    plan = json.loads((work / "edit_plan.json").read_text())
    plan_by_id = {b["id"]: b for b in plan["beats"]}
    ch_title = {c["id"]: c["title"] for c in plan.get("chapters", [])}
    caps = {}
    if (work / "captions.json").exists():
        caps = {c["beat_id"]: c for c in
                json.loads((work / "captions.json").read_text()).get("beats", [])}
    review = _normalize_review(slug)
    proxies = {}
    pdir = work / "proxies"
    if pdir.is_dir():
        for p in pdir.glob("BT*.mp4"):
            proxies[p.name.split(".")[0]] = "%s?v=%d" % (p.name,
                                                         p.stat().st_mtime)
    style = "classic"
    if (work / "captions.json").exists():
        try:
            style = json.loads((work / "captions.json").read_text()) \
                .get("style") or "classic"
        except ValueError:
            style = "classic"
    beats = []
    for beat in tl["beats"]:
        c = caps.get(beat["id"])
        if not c:
            continue
        pb = plan_by_id.get(beat["id"], {})
        beats.append({"id": beat["id"],
                      "chapter": ch_title.get(pb.get("chapter_id"), ""),
                      "dur": round(beat["record_e"] - beat["record_s"], 1),
                      "text": c.get("text", ""),
                      "edited": "text_orig" in c,
                      # classic captions every line; punchline captions the
                      # picks — the desk's toggle writes this flag
                      "selected": (bool(c.get("selected"))
                                   if style == "punchline" else True),
                      "why": c.get("why", ""),
                      "proxy": proxies.get(beat["id"]),
                      "review": review.get(beat["id"], {}).get("status", "")})
    return {"slug": slug, "style": style, "beats": beats}


def _select_caption(slug: str, beat_id: str, selected: bool,
                    log=print) -> "dict":
    """Punchline toggle: this line bakes / this line doesn't. Only
    meaningful under the punchline style — flipping it re-bakes and
    re-proxies the one beat so review playback tells the truth."""
    work = work_path(slug)
    path = work / "captions.json"
    if not path.exists():
        raise IngestError("no captions yet")
    data = json.loads(path.read_text())
    if data.get("style") != "punchline":
        raise IngestError("selection is a punchline-style control; classic "
                          "episodes caption every line")
    entry = next((c for c in data.get("beats", [])
                  if c["beat_id"] == beat_id), None)
    if entry is None:
        raise IngestError("no caption entry for %s" % beat_id)
    entry["selected"] = bool(selected)
    if selected:
        entry.setdefault("why", "hand-picked")
    _write_json(path, data)
    from . import produce as produce_mod
    from . import proxy as proxy_mod
    produce_mod.rebake_beat_caption(slug, beat_id, log=log)
    proxy_mod.build(slug, only_beats=[beat_id], log=log)
    return {"beat_id": beat_id, "selected": bool(selected)}


def _save_caption(slug: str, beat_id: str, text: "str | None",
                  revert: bool = False, log=print) -> "dict":
    """Persist a caption text edit, then re-bake + re-proxy the beat.

    text_orig stashes the caption-editor's original on first edit so
    Revert always works; saving text identical to the original clears the
    stash. Blank text removes the caption from the beat (produce and the
    proxy both skip captions by text)."""
    with _BAKE_LOCK:
        work = work_path(slug)
        path = work / "captions.json"
        if not path.exists():
            raise IngestError("no captions.json for this slug")
        data = json.loads(path.read_text())
        entry = next((c for c in data.get("beats", [])
                      if c["beat_id"] == beat_id), None)
        if entry is None:
            raise IngestError("no caption entry for %s" % beat_id)
        if revert:
            if "text_orig" not in entry:
                raise IngestError("this caption was never edited")
            entry["text"] = entry.pop("text_orig")
        else:
            text = (text or "").strip()
            orig = entry.get("text_orig", entry.get("text", ""))
            if text == orig:
                entry.pop("text_orig", None)
            elif "text_orig" not in entry:
                entry["text_orig"] = entry.get("text", "")
            entry["text"] = text
        _write_json(path, data)

        from . import produce as produce_mod
        from . import proxy as proxy_mod
        info = produce_mod.rebake_beat_caption(slug, beat_id, log=log)
        pdir = work / "proxies"
        before = {p.name: p.stat().st_mtime
                  for p in pdir.glob(beat_id + ".*.mp4")}
        proxy_mod.build(slug, only_beats=[beat_id], log=log)
        after = {p.name: p.stat().st_mtime
                 for p in pdir.glob(beat_id + ".*.mp4")}
        reproxied = before != after
        review_reset = False
        if reproxied:
            rv = work / "review.json"
            if rv.exists():
                d = json.loads(rv.read_text())
                if d.get(beat_id, {}).get("status") == "approved":
                    _save_review(slug, beat_id, {"status": "reworked"})
                    review_reset = True
        return dict(info, text=entry["text"], edited="text_orig" in entry,
                    reproxied=reproxied, review_reset=review_reset)


def serve(slug: "str | None" = None, port: int = PORT, log=print) -> None:
    import sys
    try:  # export/bake lines must reach editroom.log as they happen, not
        sys.stdout.reconfigure(line_buffering=True)  # when the server exits
    except Exception:
        pass
    # The inline Edit Room UI is retired (P5, 2026-08-23) — the Studio is
    # the one UI. The root answers with a pointer instead of a corpse.
    page = ("<!doctype html><meta charset='utf-8'>"
            "<title>The Ninth Room engine</title>"
            "<body style='font:16px/1.6 system-ui;padding:48px;max-width:520px'>"
            "<h1 style='font-size:22px'>This is the engine</h1>"
            "<p>The editing suite lives in <b>The Ninth Room Studio</b>: "
            "<a href='http://127.0.0.1:3000/studio'>127.0.0.1:3000/studio</a>."
            "</p><p style='color:#666'>This server keeps serving the API and "
            "media the Studio talks to.</p>")

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):  # quiet
            pass

        def _qs(self):
            if "?" not in self.path:
                return {}
            return urllib.parse.parse_qs(self.path.split("?", 1)[1])

        def _slug_q(self):
            s = self._qs().get("slug", [""])[0]
            if not _valid_slug(s):
                raise IngestError("unknown project '%s'" % s)
            return s

        def _slug_b(self, body):
            s = body.get("slug", "")
            if not _valid_slug(s):
                raise IngestError("unknown project '%s'" % s)
            return s

        def _send(self, code, body, ctype="application/json"):
            data = body if isinstance(body, bytes) else json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def _send_video(self, p: Path, ctype: str = "video/mp4"):
            size = p.stat().st_size
            start, end, partial = 0, size - 1, False
            rng = self.headers.get("Range", "")
            if rng.startswith("bytes="):
                spec = rng[6:].split(",")[0].strip()
                s, _, e = spec.partition("-")
                try:
                    if s:
                        start = int(s)
                        if e:
                            end = int(e)
                    elif e:  # suffix form: the last N bytes
                        start = max(size - int(e), 0)
                    partial = True
                except ValueError:
                    start, end, partial = 0, size - 1, False
                end = min(end, size - 1)
            if start > end or start >= size:
                self.send_response(416)
                self.send_header("Content-Range", "bytes */%d" % size)
                self.end_headers()
                return
            with open(p, "rb") as fh:
                fh.seek(start)
                data = fh.read(end - start + 1)
            self.send_response(206 if partial else 200)
            if partial:
                self.send_header("Content-Range",
                                 "bytes %d-%d/%d" % (start, end, size))
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            try:
                self.wfile.write(data)
            except (BrokenPipeError, ConnectionResetError):
                pass  # the player aborts range reads constantly; that's normal

        def do_OPTIONS(self):
            # preflight for the desk's direct-to-engine uploads (the Next
            # dev proxy hangs on large POST bodies; 60MB: 1s direct vs
            # 120s timeout proxied, 2026-08-23). Loopback server - a
            # wildcard origin is fine.
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Access-Control-Max-Age", "86400")
            self.end_headers()

        def do_GET(self):
            try:
                self._get()
            except IngestError as e:
                self._send(400, {"error": str(e)})
            except Exception as e:
                self._send(500, {"error": "%s: %s" % (type(e).__name__, e)})

        def _get(self):
            if self.path in ("/", "/index.html") or self.path.startswith("/#"):
                self._send(200, page.encode(), "text/html; charset=utf-8")
            elif self.path == "/api/projects":
                self._send(200, _projects_state())
            elif self.path.startswith("/api/state"):
                self._send(200, _state(self._slug_q()))
            elif self.path.startswith("/api/overlays"):
                self._send(200, _overlays_state(self._slug_q()))
            elif self.path.startswith("/api/broll/suggest"):
                qs = self._qs()
                self._send(200, {"suggestions": _broll_suggest(
                    self._slug_q(), qs.get("beat_id", [""])[0])})
            elif self.path.startswith("/api/beat/alternates"):
                qs = self._qs()
                self._send(200, {"alternates": _beat_alternates(
                    self._slug_q(), qs.get("beat_id", [""])[0])})
            elif self.path.startswith("/api/trash"):
                self._send(200, {"entries": _trash_list(self._slug_q())})
            elif self.path.startswith("/api/sound/beds"):
                from . import sfx as sfx_mod
                bslug = self._slug_q()
                lib = sorted(str(f.relative_to(sfx_mod.SFX_DIR))
                             for f in sfx_mod.SFX_DIR.rglob("*")
                             if f.is_file() and f.suffix.lower()
                             in (".mp3", ".wav", ".m4a", ".aac", ".ogg"))
                self._send(200, {"beds": sfx_mod.beds(bslug),
                                 "library": lib})
            elif self.path.startswith("/api/board"):
                from . import board as board_mod
                bslug = self._slug_q()
                doc = board_mod.read(bslug)
                self._send(200, {"events": doc.get("events", []),
                                 "cards": board_mod.fold(bslug)})
            elif self.path.startswith("/api/insights"):
                ip = work_path("_channel") / "insights.json"
                data = None
                if ip.exists():
                    try:
                        data = json.loads(ip.read_text())
                    except ValueError:
                        data = None
                sdir = work_path("_channel") / "stats"
                n_stats = len(list(sdir.glob("*.csv"))) if sdir.is_dir() else 0
                self._send(200, {"insights": data, "stats_files": n_stats})
            elif self.path.startswith("/api/publish"):
                pslug = self._slug_q()
                pp = work_path(pslug) / "publish.md"
                self._send(200, {"exists": pp.exists(),
                                 "md": pp.read_text() if pp.exists() else ""})
            elif self.path.startswith("/api/search"):
                qs = self._qs()
                self._send(200, {"hits": _search_all(
                    qs.get("q", [""])[0])})
            elif self.path.startswith("/api/captions"):
                self._send(200, _captions_state(self._slug_q()))
            elif self.path.startswith("/api/story"):
                self._send(200, _story_state(self._slug_q()))
            elif self.path.startswith("/api/session"):
                # keyed by session id, NOT by slug — a session belongs to
                # the job that ran it, and one project has many
                from urllib.parse import parse_qs, urlparse
                q = parse_qs(urlparse(self.path).query)
                self._send(200, _session_transcript(
                    (q.get("id") or [""])[0]))
            elif self.path.startswith("/api/script"):
                self._send(200, _script_state(self._slug_q()))
            elif self.path.startswith("/api/footage"):
                self._send(200, _footage_state(self._slug_q()))
            elif self.path.startswith("/api/ideas"):
                self._send(200, _ideas_state())
            elif self.path.startswith("/api/plan"):
                self._send(200, _plan_state(self._slug_q()))
            elif self.path.startswith("/api/assets"):
                self._send(200, _assets_state(self._slug_q()))
            elif self.path.startswith("/api/sfx/library"):
                from . import sfx as sfx_mod
                qs = self._qs()
                lib = sfx_mod.library()
                lslug = qs.get("slug", [""])[0]
                if lslug and _valid_slug(lslug):
                    lib["cues"] = sfx_mod.cues(lslug)
                self._send(200, lib)
            elif self.path.startswith("/api/takes"):
                self._send(200, _takes_state(self._slug_q()))
            elif self.path.startswith("/api/broll/catalog"):
                qs = self._qs()
                bslug = qs.get("slug", [""])[0]
                if not _valid_slug(bslug):
                    self._send(400, {"error": "bad slug"})
                    return
                self._send(200, {"clips": _broll_catalog(bslug)})
            elif self.path.startswith("/api/deliver/checklist"):
                from . import deliver as deliver_mod
                qs = self._qs()
                dslug = qs.get("slug", [""])[0]
                if not _valid_slug(dslug):
                    self._send(400, {"error": "bad slug"})
                    return
                self._send(200, deliver_mod.checklist(dslug))
            elif self.path.startswith("/api/jobs"):
                from . import jobs as jobs_mod
                qs = self._qs()
                jslug = qs.get("slug", [""])[0] or None
                self._send(200, {"jobs": jobs_mod.jobs(jslug)})
            elif self.path.startswith("/api/job/log"):
                from . import jobs as jobs_mod
                qs = self._qs()
                jid = qs.get("id", [""])[0]
                body = jobs_mod.log_tail(jid).encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            elif self.path.startswith("/api/conform/status"):
                from . import conform as conform_mod
                qs = self._qs()
                cslug = qs.get("slug", [""])[0]
                if not _valid_slug(cslug):
                    self._send(400, {"error": "bad slug"})
                    return
                self._send(200, conform_mod.status(cslug))
            elif self.path.startswith("/api/conform/pending"):
                qs = self._qs()
                cslug = qs.get("slug", [""])[0]
                if not _valid_slug(cslug):
                    self._send(400, {"error": "bad slug"})
                    return
                from . import conform as conform_mod
                stale_ids = conform_mod._stale_cards(cslug)
                # The preview must describe the run that will ACTUALLY
                # happen. A conform collapses the ledger before executing
                # (repeated card exports keep only the last; a place later
                # removed cancels), so the raw ledger overstates the work --
                # three edits to one card read as three placements when the
                # run pushes one. Tag each op with the REAL rule rather than
                # letting the desk re-derive it: that duplication is how a
                # preview comes to promise what the executor won't do.
                raw = _conform_pending(cslug)
                kept = set(id(o) for o in conform_mod._collapse_ops(raw))
                ops = []
                for o in raw:
                    d = dict(o)
                    d["superseded"] = id(o) not in kept
                    d["detail"] = conform_mod._op_detail(o)
                    ops.append(d)
                self._send(200, {"ops": ops,
                                 "effective": len(kept),
                                 "stale": len(stale_ids),
                                 "stale_ids": stale_ids})
            elif self.path.startswith("/media/"):
                parts = self.path.split("?")[0].split("/")
                # /media/<slug>/sfxlib/<category>/<file> — the sound library
                # is global (brand/sfx), slug kept for the rewrite's shape
                if len(parts) == 6 and parts[3] == "sfxlib":
                    from . import sfx as sfx_mod
                    rel = os.path.join(urllib.parse.unquote(parts[4]),
                                       os.path.basename(urllib.parse.unquote(parts[5])))
                    sp = (sfx_mod.SFX_DIR / rel).resolve()
                    if str(sp).startswith(str(sfx_mod.SFX_DIR.resolve()) + os.sep) \
                            and sp.is_file() \
                            and sp.suffix.lower() in sfx_mod.AUDIO_EXT:
                        ctype = {".mp3": "audio/mpeg", ".wav": "audio/wav",
                                 ".m4a": "audio/mp4", ".aac": "audio/aac",
                                 ".ogg": "audio/ogg", ".flac": "audio/flac"}[sp.suffix.lower()]
                        self._send_video(sp, ctype)
                        return
                    self._send(404, {"error": "not found"})
                    return
                # /media/<slug>/assets/.thumbs/<name> — the poster frames
                # _assets_state generates for sourced video (2026-08-24).
                # Six parts, so it cannot ride the branch below.
                if (len(parts) == 6 and parts[3] == "assets"
                        and parts[4] == ".thumbs" and _valid_slug(parts[2])):
                    th = (work_path(parts[2]) / "assets" / ".thumbs" /
                          os.path.basename(urllib.parse.unquote(parts[5]))).resolve()
                    root = (work_path(parts[2]) / "assets").resolve()
                    if (str(th).startswith(str(root) + os.sep)
                            and th.is_file() and th.suffix.lower() == ".jpg"):
                        self._send(200, th.read_bytes(), "image/jpeg")
                        return
                    self._send(404, {"error": "not found"})
                    return
                # /media/<slug>/<proxies|exports>/<name>
                if len(parts) != 5 or not _valid_slug(parts[2]):
                    self._send(404, {"error": "not found"})
                    return
                mslug, kind, name = parts[2], parts[3], os.path.basename(parts[4])
                name = urllib.parse.unquote(name)
                if kind == "proxies":
                    p = (work_path(mslug) / "proxies" / name).resolve()
                    if p.exists() and p.suffix == ".mp4":
                        self._send_video(p)
                        return
                elif kind == "footage":
                    p = (work_path(mslug) / "footage" / name).resolve()
                    if p.is_file() and p.suffix.lower() in _VIDEO_UP:
                        self._send_video(p)
                        return
                elif kind == "deliverables":
                    # the Studio's Export desk plays the newest master in
                    # place -- "ready to ship" answered by watching, not by
                    # reading a row (UX overhaul, 2026-08-23)
                    p = (work_path(mslug) / "deliverables" / name).resolve()
                    if p.is_file() and p.suffix.lower() == ".mp4":
                        self._send_video(p)
                        return
                elif kind == "assets":
                    p = (work_path(mslug) / "assets" / name).resolve()
                    if p.is_file() and p.suffix.lower() in _VIDEO_UP:
                        self._send_video(p)
                        return
                    # a sourced still is media as much as a sourced clip;
                    # this branch served only video, so every image asset
                    # 404'd and the desk showed an empty frame (2026-08-24)
                    if p.is_file() and p.suffix.lower() in _IMAGE_UP:
                        ctype = {".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                                 ".png": "image/png", ".webp": "image/webp",
                                 ".heic": "image/heic"}[p.suffix.lower()]
                        self._send(200, p.read_bytes(), ctype)
                        return
                elif kind == "exports":
                    p = work_path(mslug) / "exports" / "overlays" / name
                    if p.exists() and p.suffix == ".mov":
                        data = p.read_bytes()
                        self.send_response(200)
                        self.send_header("Content-Type", "video/quicktime")
                        self.send_header("Content-Disposition",
                                         'attachment; filename="%s"' % name)
                        self.send_header("Content-Length", str(len(data)))
                        self.send_header("Cache-Control", "no-store")
                        self.end_headers()
                        self.wfile.write(data)
                        return
                self._send(404, {"error": "not found"})
            elif self.path.startswith("/file?"):
                # preview images only, and only from inside the repo (work/
                # lives under it) — this server is localhost, but stay tight
                qs = self._qs()
                p = Path(qs.get("p", [""])[0]).resolve()
                if str(p).startswith(str(REPO_ROOT) + os.sep) and p.is_file() \
                        and p.suffix.lower() in (
                        ".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"):
                    ctype = {"svg": "image/svg+xml"}.get(
                        p.suffix[1:].lower(), "image/" + p.suffix[1:].lower())
                    self._send(200, p.read_bytes(), ctype)
                else:
                    self._send(404, {"error": "not found"})
            else:
                self._send(404, {"error": "not found"})

        def _body(self):
            n = int(self.headers.get("Content-Length") or 0)
            return json.loads(self.rfile.read(n) or b"{}")

        def do_POST(self):
            try:
                self._post()
            except IngestError as e:
                self._send(400, {"error": str(e)})
            except Exception as e:  # a bake crash must reach the UI, not die
                self._send(500, {"error": "%s: %s" % (type(e).__name__, e)})

        def _post(self):
            if self.path.startswith("/api/upload"):
                qs = self._qs()
                uslug = qs.get("slug", [""])[0]
                if not _valid_slug(uslug):
                    raise IngestError("unknown project '%s'" % uslug)
                name = qs.get("name", [""])[0]
                n = int(self.headers.get("Content-Length") or 0)
                if qs.get("to", [""])[0] == "assets":
                    # the Library shelf: supporting material, not the shoot
                    out = _save_asset_upload(uslug, name, self.rfile, n,
                                             log=log)
                    self._send(200, dict(out, ok=True))
                    return
                result = _save_upload(uslug, name, self.rfile, n)
                # local import: jobs_mod is imported LATER in this same
                # function scope for the job routes, so the bare name here
                # is an unassigned local (found live: every upload 500'd)
                from . import jobs as _jobs_auto
                # a re-dropped duplicate stores nothing — it must not stamp
                # the batch and trigger a pointless re-analysis (review F5)
                if not result.get("duplicate"):
                    _jobs_auto.note_upload(uslug)
                log("[upload] %s <- %s%s%s"
                    % (uslug, result["stored"],
                       " (still -> %s)" % result["as"] if result.get("as") else "",
                       " duplicate of %s" % result["duplicate"]
                       if result.get("duplicate") else ""))
                self._send(200, dict(result, ok=True))
                return
            if self.path == "/api/project/new":
                nb = self._body()
                new = _new_project(nb.get("name", ""),
                                   nb.get("origin", "footage"),
                                   nb.get("delivery", "long"),
                                   nb.get("shorts_source"))
                log("[project] created %s (%s, %s)"
                    % (new, nb.get("origin", "footage"),
                       nb.get("delivery", "long")))
                self._send(200, {"ok": True, "slug": new})
                return
            body = self._body()
            if self.path == "/api/review":
                bslug = self._slug_b(body)
                if not body.get("beat_id"):
                    self._send(400, {"error": "beat_id required"})
                    return
                _save_review(bslug, body["beat_id"], body)
                self._send(200, {"ok": True})
            elif self.path == "/api/review/bulk":
                touched = _save_review_bulk(self._slug_b(body),
                                            body.get("beat_ids"),
                                            body.get("status", ""))
                self._send(200, {"ok": True, "touched": touched})
            elif self.path == "/api/overlay/html":
                html = _preview_html(body["card"],
                                     int(body.get("w", 1920)),
                                     int(body.get("h", 1080)))
                self._send(200, {"html": html})
            elif self.path == "/api/overlay/save":
                card = _save_overlay(self._slug_b(body), body["id"],
                                     body.get("updates", {}))
                self._send(200, {"ok": True, "card": card})
            elif self.path == "/api/overlay/new":
                card = _new_overlay(self._slug_b(body),
                                    body.get("kit_type", "lower_third"),
                                    beat_id=body.get("beat_id"),
                                    at=float(body.get("at", 0.0)))
                self._send(200, {"ok": True, "card": card})
            elif self.path == "/api/overlay/delete":
                result = _delete_overlay(self._slug_b(body), body["id"])
                self._send(200, dict(result, ok=True))
            elif self.path == "/api/sfx/search":
                from . import sfx as sfx_mod
                try:
                    rows = sfx_mod.ep_search(body.get("term", ""),
                                             body.get("kind", "sfx"),
                                             int(body.get("limit", 20)))
                    self._send(200, {"ok": True, "results": rows})
                except sfx_mod.SfxError as e:
                    self._send(400, {"error": str(e)})
            elif self.path == "/api/sfx/pull":
                from . import sfx as sfx_mod
                try:
                    r = sfx_mod.ep_pull(body.get("kind", "sfx"),
                                        str(body["id"]), body.get("title", ""),
                                        body.get("category", ""))
                    self._send(200, dict(r, ok=True))
                except sfx_mod.SfxError as e:
                    self._send(400, {"error": str(e)})
            elif self.path == "/api/sfx/place":
                from . import sfx as sfx_mod
                try:
                    cue = _sfx_place(self._slug_b(body), body["beat_id"],
                                     body["file"], int(body.get("at_ms", 0)),
                                     body.get("gain_db"), log=log)
                    self._send(200, {"ok": True, "cue": cue})
                except sfx_mod.SfxError as e:
                    self._send(400, {"error": str(e)})
            elif self.path == "/api/sfx/remove":
                from . import sfx as sfx_mod
                try:
                    gone = _sfx_remove(self._slug_b(body), body["cue_id"], log=log)
                    self._send(200, {"ok": True, "removed": gone})
                except sfx_mod.SfxError as e:
                    self._send(400, {"error": str(e)})
            elif self.path == "/api/broll/attach":
                entry = _broll_attach(self._slug_b(body), body["beat_id"],
                                      body["clip_id"], float(body.get("at", 0)),
                                      float(body.get("duration", 4)),
                                      float(body.get("src_s", 0)), log=log)
                self._send(200, {"ok": True, "placed": entry})
            elif self.path == "/api/sound/bed":
                from . import sfx as sfx_mod
                from . import jobs as jobs_mod2
                bslug = self._slug_b(body)
                rows = sfx_mod.save_bed(bslug, str(body.get("chapter_id", "")),
                                        body.get("file"),
                                        float(body.get("gain_db", 0) or 0))
                # the bed re-keys its chapter's beats; previews rebuild as a
                # job (many beats — never inline in a request)
                try:
                    jobs_mod2.start("reproxy", bslug)
                except jobs_mod2.JobError:
                    pass
                self._send(200, {"ok": True, "beds": rows})
            elif self.path == "/api/thumbnail":
                out = _bake_thumbnail(self._slug_b(body),
                                      body.get("beat_id", ""),
                                      float(body.get("at", 0) or 0),
                                      str(body.get("title", "")),
                                      str(body.get("kicker", "")), log=log)
                self._send(200, dict(out, ok=True))
            elif self.path == "/api/project/title":
                tslug = self._slug_b(body)
                txt = str(body.get("title", "")).strip()[:120]
                tp = work_path(tslug) / "title.txt"
                if txt:
                    tp.write_text(txt)
                else:
                    # empty reverts to the derived title
                    tp.unlink(missing_ok=True)
                log("[title] %s -> %r" % (tslug, txt or "(derived)"))
                self._send(200, {"ok": True,
                                 "title": _project_title(tslug)})
            elif self.path == "/api/board/reply":
                from . import board as board_mod
                bslug = self._slug_b(body)
                evd = {"type": "caleb_note", "by": "caleb",
                       "task_id": str(body.get("task_id", "")),
                       "text": str(body.get("text", ""))[:2000]}
                # rev 3: the taste tap is human-labeled, never inferred
                if body.get("taste_override"):
                    evd["taste_override"] = str(body["taste_override"])[:120]
                board_mod.append(bslug, [evd], expect_by="caleb")
                self._send(200, {"ok": True})
            elif self.path == "/api/deliver/check":
                cslug = self._slug_b(body)
                sp = work_path(cslug) / "ship.json"
                data = json.loads(sp.read_text()) if sp.exists() else {}
                data["backup_confirmed"] = bool(body.get("ok"))
                data["backup_ts"] = int(time.time())
                _write_json(sp, data)
                self._send(200, {"ok": True})
            elif self.path == "/api/project/clean":
                out = _clean_stale(self._slug_b(body), log=log)
                self._send(200, dict(out, ok=True))
            elif self.path == "/api/caption/select":
                out = _select_caption(self._slug_b(body),
                                      body.get("beat_id", ""),
                                      bool(body.get("selected")))
                self._send(200, dict(out, ok=True))
            elif self.path == "/api/beat/swap":
                out = _beat_swap(self._slug_b(body), body.get("beat_id", ""),
                                 body.get("take_id", ""))
                self._send(200, dict(out, ok=True))
            elif self.path == "/api/beat/trim":
                out = _beat_trim(self._slug_b(body), body.get("beat_id", ""),
                                 body.get("d_in", 0), body.get("d_out", 0))
                self._send(200, dict(out, ok=True))
            elif self.path == "/api/trash/restore":
                restored = _trash_restore(self._slug_b(body),
                                          str(body.get("uid", "")))
                self._send(200, {"ok": True, "restored": restored})
            elif self.path == "/api/broll/adjust":
                out = _broll_adjust(self._slug_b(body),
                                    body.get("beat_id", ""),
                                    body.get("clip_id", ""),
                                    at=body.get("at"),
                                    duration=body.get("duration"),
                                    src_s=body.get("src_s"),
                                    record_s=body.get("record_s"), log=log)
                self._send(200, {"ok": True, "placed": out})
            elif self.path == "/api/broll/remove":
                rs = body.get("record_s")
                gone = _broll_detach(self._slug_b(body), body["beat_id"],
                                     body["clip_id"], float(body.get("at", 0)),
                                     record_s=(float(rs) if rs is not None else None),
                                     log=log)
                self._send(200, {"ok": True, "removed": gone})
            elif self.path == "/api/project/archive":
                _archive_project(self._slug_b(body))
                self._send(200, {"ok": True})
            elif self.path == "/api/asset/capture":
                out = _capture_article(self._slug_b(body),
                                       str(body.get("url", "")), log=log)
                self._send(200, dict(out, ok=True))
            elif self.path == "/api/asset/round":
                out = _asset_round_verdict(self._slug_b(body),
                                           body.get("ts"),
                                           str(body.get("status", "")),
                                           log=log)
                self._send(200, dict(out, ok=True))
            elif self.path == "/api/take/verdict":
                out = _set_take_verdict(self._slug_b(body),
                                        str(body.get("take_id", "")),
                                        str(body.get("verdict", "")),
                                        str(body.get("reason", "")), log=log)
                self._send(200, dict(out, ok=True))
            elif self.path == "/api/footage/link":
                out = _link_footage(self._slug_b(body),
                                    str(body.get("folder", "")), log=log)
                self._send(200, dict(out, ok=True))
            elif self.path == "/api/footage/relink":
                out = _relink_footage(self._slug_b(body),
                                      body.get("folder") or None, log=log)
                self._send(200, dict(out, ok=True))
            elif self.path == "/api/project/delete":
                # a live OR archived slug — _delete_project validates the
                # shape itself (_slug_b only knows about live projects) and
                # demands the typed confirmation before anything is erased
                out = _delete_project(str(body.get("slug", "")),
                                      str(body.get("confirm", "")), log=log)
                self._send(200, dict(out, ok=True))
            elif self.path == "/api/project/restore":
                rslug = str(body.get("slug", ""))
                # _slug_b validates against LIVE projects — the archived one
                # is by definition not there (P7 gate finding 2: restore was
                # a one-way door). Regex-check only; _restore_project's own
                # is_dir gate does the rest.
                if not _SLUG_RE.match(rslug):
                    self._send(400, {"error": "bad slug"})
                    return
                _restore_project(rslug)
                self._send(200, {"ok": True})
            elif self.path == "/api/idea/start":
                r = _start_project_from_idea(str(body.get("id", "")))
                self._send(200, dict(r, ok=True))
            elif self.path == "/api/job/rechain":
                from . import jobs as jobs_mod
                try:
                    job = jobs_mod.rechain(str(body.get("id", "")))
                    self._send(200, {"ok": True, "job": job})
                except jobs_mod.JobError as e:
                    self._send(400, {"error": str(e)})
            elif self.path == "/api/job/start":
                from . import jobs as jobs_mod
                try:
                    # scout is channel-level: its workspace is work/_scout,
                    # which the slug regex rejects (leading underscore is
                    # reserved) -- so the kind names its own workspace
                    job = jobs_mod.start(
                        body.get("kind", ""),
                        "_scout" if body.get("kind") == "scout"
                        else "_channel" if body.get("kind") == "perf"
                        else self._slug_b(body),
                        arg=(str(body["arg"]) if body.get("arg") else None))
                    self._send(200, {"ok": True, "job": job})
                except jobs_mod.JobError as e:
                    self._send(400, {"error": str(e)})
            elif self.path == "/api/conform/start":
                from . import conform as conform_mod
                try:
                    conform_mod.start(self._slug_b(body))
                    self._send(200, {"ok": True})
                except conform_mod.ConformBusy as e:
                    self._send(400, {"error": str(e)})
            elif self.path == "/api/review/archive_resolved":
                n = _archive_resolved_reviews(self._slug_b(body))
                self._send(200, {"ok": True, "closed": n})
            elif self.path == "/api/overlay/duplicate":
                card = _duplicate_overlay(self._slug_b(body), body["id"])
                self._send(200, {"ok": True, "card": card})
            elif self.path == "/api/overlay/export":
                result = _export_overlay(self._slug_b(body), body["id"],
                                         log=log)
                self._send(200, dict(result, ok=True))
            elif self.path == "/api/caption/save":
                result = _save_caption(self._slug_b(body), body["beat_id"],
                                       body.get("text"),
                                       revert=bool(body.get("revert")),
                                       log=log)
                self._send(200, dict(result, ok=True))
            elif self.path == "/api/footage/delete":
                result = _delete_footage(self._slug_b(body),
                                         body.get("name", ""),
                                         force=bool(body.get("force")),
                                         log=log)
                log("[footage] %s removed %s" % (body.get("slug"),
                                                 result["removed"]))
                self._send(200, dict(result, ok=True))
            elif self.path == "/api/footage/favorite":
                favs = _toggle_favorite(self._slug_b(body),
                                        body.get("name", ""),
                                        bool(body.get("on")))
                self._send(200, {"ok": True, "favorites": favs})
            elif self.path == "/api/footage/clear":
                result = _clear_footage(self._slug_b(body))
                log("[footage] %s cleared (%d files to .trash)"
                    % (body.get("slug"), result["removed"]))
                self._send(200, dict(result, ok=True))
            elif self.path == "/api/timeline/sync":
                tslug = self._slug_b(body)
                self._send(200, _sync_timeline_cards(tslug))
            elif self.path == "/api/plan/save":
                # `body` was already read at the top of _post — reading the
                # socket again blocks forever on a drained stream.
                pslug = body.get("slug", "")
                if not _valid_slug(pslug):
                    raise IngestError("unknown project '%s'" % pslug)
                self._send(200, _save_plan(pslug, body.get("plan") or {}))
            elif self.path == "/api/idea/state":
                _save_idea_state(body.get("id", ""), body.get("status", ""),
                                 body.get("notes", ""))
                self._send(200, {"ok": True})
            elif self.path == "/api/asset/request":
                reqs = _request_assets(self._slug_b(body), body.get("text", ""))
                self._send(200, {"ok": True, "requests": reqs})
            elif self.path == "/api/asset/delete":
                _delete_asset(self._slug_b(body), body.get("id", ""))
                self._send(200, {"ok": True})
            elif self.path == "/api/asset/use":
                result = _use_asset(self._slug_b(body), body.get("id", ""))
                self._send(200, dict(result, ok=True))
            elif self.path == "/api/plan/seed":
                plan = _seed_plan(self._slug_b(body))
                self._send(200, {"ok": True, "plan": plan})
            elif self.path == "/api/script/section":
                sec = _save_script_section(self._slug_b(body),
                                           str(body.get("section_id", "")),
                                           body.get("text", ""))
                self._send(200, {"ok": True, "section": sec})
            elif self.path == "/api/script/answers":
                fb = _save_script_answers(self._slug_b(body),
                                          body.get("answers") or {},
                                          body.get("notes", ""))
                self._send(200, {"ok": True, "feedback": fb})
            elif self.path == "/api/script/feedback":
                fb = _save_script_feedback(self._slug_b(body),
                                           body.get("notes", ""),
                                           body.get("decision", "direction"))
                self._send(200, {"ok": True, "feedback": fb})
            elif self.path == "/api/script/recheck":
                self._send(200, dict(_recheck_script(self._slug_b(body)),
                                     ok=True))
            elif self.path == "/api/script/unlock":
                sc = _unlock_script(self._slug_b(body))
                self._send(200, {"ok": True, "locked": sc.get("locked", False)})
            elif self.path == "/api/story/brief":
                brief = _save_story_brief(self._slug_b(body),
                                          body.get("target_minutes"),
                                          body.get("chapters"),
                                          body.get("notes", ""),
                                          body.get("location", ""),
                                          body.get("vo_share"),
                                          body.get("subject", ""),
                                          body.get("origin", "footage"),
                                          body.get("delivery"),
                                          body.get("shorts_source"))
                self._send(200, {"ok": True, "brief": brief})
            elif self.path == "/api/story/feedback":
                fb = _save_story_feedback(self._slug_b(body),
                                          body.get("choice"),
                                          body.get("notes", ""),
                                          body.get("decision", "direction"))
                self._send(200, {"ok": True, "feedback": fb})
            elif self.path == "/api/reveal":
                bslug = self._slug_b(body)
                if body.get("footage"):
                    d = work_path(bslug) / "footage"
                    d.mkdir(parents=True, exist_ok=True)
                else:
                    d = _exports_dir(bslug)
                p = d / os.path.basename(body["file"]) if body.get("file") else d
                if not p.exists():
                    p = d
                subprocess.run(["open", "-R", str(p)] if p.is_file()
                               else ["open", str(p)])
                self._send(200, {"ok": True})
            else:
                self._send(404, {"error": "not found"})

    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    log("[editroom] http://127.0.0.1:%d  (Ctrl-C to stop)" % port)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
