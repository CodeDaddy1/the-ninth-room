"""The Edit Room — a local review UI for grading the cut shot by shot.

`/usr/bin/python3 -m pipeline.cli editroom <slug>` starts a localhost server
and prints the URL. The page is a review desk: a sidebar lists every shot
with its status dot, the main pane plays ONE shot at a time — approve or
flag it and the desk auto-advances to the next unreviewed shot, so a full
pass never requires scrolling a wall of cards. Decisions land in
work/<slug>/review.json, which the shot-fixer agent consumes: it patches
exactly the flagged beats, re-proxies them, and resets their status to
"reworked" for re-review. Approved beats are never touched.

Saving: every decision POSTs immediately; notes autosave ~1s after typing
stops and flush on blur/navigate/close (sendBeacon). The header shows the
live save state plus a Save button that flushes anything pending — the
button is reassurance, the autosave is the mechanism.

Serving video correctly matters: the proxy endpoint honors HTTP Range
requests (206) — browsers require ranges to seek, and Safari refuses to
play without them — and sends Cache-Control: no-store so a proxy fetched
mid-render (the BT103 incident) can never stick in the browser cache.

The Overlays desk (second tab, or /#overlays) edits cards with a LIVE
animated preview — the kit is pure CSS, so an <iframe srcdoc> plays the real
animation while you type, no bake needed to look. "Approve & Export" bakes
the ProRes 4444 alpha .mov (cached when unchanged) into
work/<slug>/exports/overlays/ under a human-readable name
(BT04_transition_the-cockrell-butterfly-center.mov) for manual import onto a
Resolve timeline, with Download and Reveal-in-Finder buttons. Exports are
IMMUTABLE: a changed card gets a fresh _v2/_v3 filename and older versions
are never touched — replacing or deleting media an NLE has imported is what
makes clips flicker "Media Offline". Editing a
timeline card writes graphics_plan.json through the schema validator (the
2.5s chapter rule gates the form exactly like it gates the pipeline), and
exporting one re-proxies its beat so the Shots desk keeps showing what will
ship — flipping an approved beat back to re-review only when the pixels
actually changed. Custom overlays (not on the timeline) live in
overlays_custom.json and never touch the produce pipeline.

Everything is local and $0: stdlib http.server, no build step, no cloud.
The page is written fresh on every start, so UI changes ship by restarting.

What breaks if this is wrong: review decisions get lost (the one file that
matters is review.json — it is written atomically via replace) or the page
shows stale proxies (the state endpoint re-reads the proxy dir every call,
so a re-render shows up on refresh).
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

from .ingest import work_path, analysis_dir, IngestError

PORT = 8765
REPO_ROOT = Path(__file__).resolve().parents[1]

# One bake at a time: animate.py already saturates the performance cores per
# card, and two overlapping Chrome fleets would just thrash.
_BAKE_LOCK = threading.Lock()


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
    review = {}
    if (work / "review.json").exists():
        review = json.loads((work / "review.json").read_text())
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
            "proxy": proxies.get(beat["id"]),
            "review": review.get(beat["id"], {}),
        }
        ch = ch_index.get(pb.get("chapter_id"))
        (ch["beats"] if ch else chapters[0]["beats"] if chapters else []).append(entry)
    total = len(tl["beats"])
    approved = sum(1 for r in review.values() if r.get("status") == "approved")
    flagged = sum(1 for r in review.values() if r.get("status") == "flagged")
    return {"slug": slug, "chapters": chapters,
            "counts": {"total": total, "approved": approved, "flagged": flagged}}


def _save_review(slug: str, beat_id: str, payload: "dict") -> None:
    work = work_path(slug)
    path = work / "review.json"
    data = json.loads(path.read_text()) if path.exists() else {}
    entry = data.get(beat_id, {})
    # a note-only autosave sends status:null — that must never erase a
    # decision already on file
    if payload.get("status") in ("approved", "flagged", "reworked"):
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
             "sides", "travel_ms", "accent", "x", "y")

# Starter copy for a freshly created overlay, per kit screen. Keys must be
# names overlay_kit.RENDERERS knows (the big emoji screen is "emoji").
_KIT_TEMPLATES = {
    "lower_third": {"kicker": "True fact", "text": "Your fact goes here"},
    "hook": {"kicker": "The setup", "text": "A headline that opens the loop"},
    "chapter": {"kicker": "Chapter", "text": "Chapter title"},
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
    "outro": {"kicker": "Thanks for watching",
              "text": "See you in the next room.",
              "subtext": "New rooms every week",
              "cta": "Subscribe"},
}


def _orientation(slug: str) -> str:
    p = analysis_dir(slug) / "timeline_map.json"
    if p.exists():
        return json.loads(p.read_text()).get("orientation", "landscape")
    return "landscape"


def _write_json(path: Path, data) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    os.replace(tmp, path)


def _custom_path(slug: str) -> Path:
    return work_path(slug) / "overlays_custom.json"


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
    return {"slug": slug, "orientation": orient,
            # the live preview renders at the kit's design size — bakes and
            # exports use graphics.CANVAS (UHD) with the same layout at 2x
            "canvas": list(graphics.KIT_DESIGN[orient]),
            "export_dir": str(d), "kits": sorted(_KIT_TEMPLATES),
            "overlays": items}


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
    return out


def _save_overlay(slug: str, card_id: str, updates: "dict") -> "dict":
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
                errors = schemas.validate_graphics_plan(plan)
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
            _write_json(_custom_path(slug), custom)
            return merged
    raise IngestError("no overlay '%s'" % card_id)


def _new_overlay(slug: str, kit_type: str) -> "dict":
    if kit_type not in _KIT_TEMPLATES:
        raise IngestError("unknown kit type '%s'" % kit_type)
    custom = _load_custom(slug)
    taken = {c["id"] for c, _ in _all_overlays(slug)}
    n = 1
    while "OV%02d" % n in taken:
        n += 1
    card = {"id": "OV%02d" % n, "kit_type": kit_type,
            "duration": 2.5 if kit_type in ("chapter", "transition") else 3.0}
    card.update(json.loads(json.dumps(_KIT_TEMPLATES[kit_type])))
    custom["overlays"].append(card)
    _write_json(_custom_path(slug), custom)
    return card


def _delete_overlay(slug: str, card_id: str) -> None:
    """Custom overlays only — timeline cards belong to the edit plan."""
    custom = _load_custom(slug)
    keep = [c for c in custom["overlays"] if c["id"] != card_id]
    if len(keep) == len(custom["overlays"]):
        raise IngestError("'%s' is not a custom overlay" % card_id)
    custom["overlays"] = keep
    _write_json(_custom_path(slug), custom)
    exp = _export_state(slug)
    exp.pop(card_id, None)
    # exported files stay on disk — Resolve may reference them (immutability
    # rule above); Caleb trashes unwanted versions from Finder himself
    _write_json(_exports_dir(slug) / ".export_hashes.json", exp)


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
                    if data.get(bid, {}).get("status") == "approved":
                        _save_review(slug, bid, {"status": "reworked"})
                        result["review_reset"] = True
        return result


# --- Projects, phases, uploads, story loop ---------------------------------
# The Edit Room houses every project: pick one in the header, or create one
# and drop raw clips/photos straight onto the page. Phases are DERIVED from
# what exists on disk (footage -> ingest -> story -> assembly -> review ->
# master), and each phase's next step is spelled out — including exactly
# what to tell Claude, since the agents run in the Claude session, not here.

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
_VIDEO_UP = (".mp4", ".mov", ".m4v", ".mts", ".avi", ".mkv")
_IMAGE_UP = (".jpg", ".jpeg", ".png", ".heic", ".webp")


def _valid_slug(slug: str) -> bool:
    return bool(slug and _SLUG_RE.match(slug) and work_path(slug).is_dir())


def _new_project(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")
    if not slug:
        raise IngestError("give the project a name")
    work = work_path(slug)
    if work.exists():
        raise IngestError("project '%s' already exists" % slug)
    (work / "footage").mkdir(parents=True)
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
    tl = (out / "timeline_map.json").exists()
    prox = (len(list((work / "proxies").glob("BT*.mp4")))
            if (work / "proxies").is_dir() else 0)
    masters = (sorted((work / "deliverables").glob("*.mp4"))
               if (work / "deliverables").is_dir() else [])
    review = {}
    if (work / "review.json").exists():
        review = json.loads((work / "review.json").read_text())
    n_appr = sum(1 for e in review.values() if e.get("status") == "approved")
    n_flag = sum(1 for e in review.values() if e.get("status") == "flagged")
    n_needs = sum(1 for e in review.values() if e.get("needs"))

    if not footage:
        phase, nxt = "footage", ("Drop clips and photos anywhere on this "
                                 "page, or open the footage folder and copy "
                                 "them in.")
    elif not ingested:
        phase, nxt = "ingest", ('Footage is in (%d clips). Tell Claude: '
                                '“ingest %s” — transcription, '
                                'take analysis, b-roll catalog.'
                                % (len(footage), slug))
    elif not plan and not stories:
        phase, nxt = "story", ('Tell Claude: “pitch stories for %s” '
                               '— the story designer writes three '
                               'directions to the Story tab.' % slug)
    elif not plan and not approved:
        phase, nxt = "story", ("Story pitches are on the Story tab — "
                               "approve one, or send direction notes for a "
                               "fresh round.")
    elif not plan:
        phase, nxt = "story", ('Direction approved. Tell Claude: '
                               '“write the edit plan for %s”.' % slug)
    elif not (tl and prox):
        phase, nxt = "assembly", ('Tell Claude: “assemble %s” '
                                  '— timeline and review proxies in '
                                  'story order.' % slug)
    elif prox and (n_appr + n_flag) < prox:
        phase, nxt = "review", ("Review the shots — approve or flag "
                                "each, and mark b-roll / SFX / card needs.")
    elif n_flag or n_needs:
        phase, nxt = "review", ('%d flag(s) and %d shot(s) with needs. Tell '
                                'Claude: “run the fixer on %s”.'
                                % (n_flag, n_needs, slug))
    elif not masters:
        phase, nxt = "master", ('Every shot approved. Tell Claude: '
                                '“produce the master for %s”.' % slug)
    else:
        phase, nxt = "master", ("Master rendered: %s. Any later change: "
                                "tell Claude to re-produce." % masters[-1].name)
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
    return {"slug": slug, "phase": phase, "next": nxt,
            "footage": len(footage), "ingested": ingested,
            "stories": bool(stories), "plan": plan, "proxies": prox,
            "master": masters[-1].name if masters else None,
            "progress": progress,
            "review": {"approved": n_appr, "flagged": n_flag,
                       "needs": n_needs}}


def _projects_state() -> "dict":
    root = work_path("x").parent
    slugs = sorted(p.name for p in root.iterdir()
                   if p.is_dir() and _SLUG_RE.match(p.name)
                   and not p.name.startswith("_")
                   and ((p / "footage").is_dir() or (p / "analysis").is_dir()
                        or (p / "edit_plan.json").exists()))
    return {"projects": [_project_row(s) for s in slugs]}


def _content_sig(path: Path, size: int) -> str:
    """Cheap content signature: sha1 of the first+last MB. Two multi-GB
    camera files agreeing on size AND both ends are the same recording."""
    with open(path, "rb") as fh:
        head = fh.read(1 << 20)
        tail = b""
        if size > (1 << 20):
            fh.seek(max(size - (1 << 20), 0))
            tail = fh.read(1 << 20)
    return hashlib.sha1(head + tail).hexdigest()[:16]


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
        proc = subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-t", "6",
             "-i", str(inp),
             "-vf", "scale=3840:2160:force_original_aspect_ratio=increase,"
                    "crop=3840:2160,fps=24,format=yuv420p",
             "-c:v", "libx264", "-preset", "fast", "-crf", "18",
             "-movflags", "+faststart", str(clip)],
            capture_output=True, text=True)
        if proc.returncode != 0:
            raise IngestError("still conversion failed for %s: %s"
                              % (name, proc.stderr[-200:]))
        return {"stored": name, "as": clip.name, "still": True}
    name = _uniquify(fdir, name)
    os.replace(tmp, fdir / name)
    return {"stored": name, "still": False}


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
    return {"slug": slug, "files": items, "ingested": ingested}


def _delete_footage(slug: str, name: str) -> "dict":
    """Remove one dropped clip — into footage/.trash, never gone for good.
    Removing a converted photo clip takes its source photo along."""
    fdir = work_path(slug) / "footage"
    name = os.path.basename(name)
    p = fdir / name
    if not p.is_file():
        raise IngestError("no clip named '%s'" % name)
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
    return {"removed": removed,
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


def _story_state(slug: str) -> "dict":
    work = work_path(slug)
    stories = fb = plan_summary = None
    if (work / "stories.json").exists():
        stories = json.loads((work / "stories.json").read_text())
    if (work / "story_feedback.json").exists():
        fb = json.loads((work / "story_feedback.json").read_text())
    if (work / "edit_plan.json").exists():
        plan = json.loads((work / "edit_plan.json").read_text())
        plan_summary = {"beats": len(plan.get("beats", [])),
                        "chapters": [c.get("title", "")
                                     for c in plan.get("chapters", [])]}
    return {"slug": slug, "stories": stories,
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
    fb["rounds"].append({"ts": int(time.time()),
                         "round": (stories or {}).get("round"),
                         "choice": choice, "notes": (notes or "").strip(),
                         "decision": decision})
    _write_json(path, fb)
    return fb


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
    review = {}
    if (work / "review.json").exists():
        review = json.loads((work / "review.json").read_text())
    proxies = {}
    pdir = work / "proxies"
    if pdir.is_dir():
        for p in pdir.glob("BT*.mp4"):
            proxies[p.name.split(".")[0]] = "%s?v=%d" % (p.name,
                                                         p.stat().st_mtime)
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
                      "proxy": proxies.get(beat["id"]),
                      "review": review.get(beat["id"], {}).get("status", "")})
    return {"slug": slug, "beats": beats}


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
    page = PAGE.replace("__INITIAL__", slug or "")

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
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def _send_video(self, p: Path):
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
            self.send_header("Content-Type", "video/mp4")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            try:
                self.wfile.write(data)
            except (BrokenPipeError, ConnectionResetError):
                pass  # the player aborts range reads constantly; that's normal

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
            elif self.path.startswith("/api/captions"):
                self._send(200, _captions_state(self._slug_q()))
            elif self.path.startswith("/api/story"):
                self._send(200, _story_state(self._slug_q()))
            elif self.path.startswith("/api/footage"):
                self._send(200, _footage_state(self._slug_q()))
            elif self.path.startswith("/media/"):
                parts = self.path.split("?")[0].split("/")
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
                result = _save_upload(uslug, name, self.rfile, n)
                log("[upload] %s <- %s%s%s"
                    % (uslug, result["stored"],
                       " (still -> %s)" % result["as"] if result.get("as") else "",
                       " duplicate of %s" % result["duplicate"]
                       if result.get("duplicate") else ""))
                self._send(200, dict(result, ok=True))
                return
            if self.path == "/api/project/new":
                new = _new_project(self._body().get("name", ""))
                log("[project] created %s" % new)
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
                                    body.get("kit_type", "lower_third"))
                self._send(200, {"ok": True, "card": card})
            elif self.path == "/api/overlay/delete":
                _delete_overlay(self._slug_b(body), body["id"])
                self._send(200, {"ok": True})
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
                result = _delete_footage(self._slug_b(body), body.get("name", ""))
                log("[footage] %s removed %s" % (body.get("slug"),
                                                 result["removed"]))
                self._send(200, dict(result, ok=True))
            elif self.path == "/api/footage/clear":
                result = _clear_footage(self._slug_b(body))
                log("[footage] %s cleared (%d files to .trash)"
                    % (body.get("slug"), result["removed"]))
                self._send(200, dict(result, ok=True))
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


PAGE = r"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Edit Room</title>
<style>
:root{--accent:#12B76A;--ink:#09090B;--panel:#141416;--panel2:#1C1C1F;
--text:#FCFCFA;--muted:#9A9A94;--hair:#26262A;--flag:#E5484D;--rework:#E8A33D}
*{box-sizing:border-box;margin:0}
html,body{height:100%}
body{background:var(--ink);color:var(--text);display:flex;flex-direction:column;
font-family:Manrope,'Helvetica Neue',sans-serif;font-size:15px;line-height:1.5;
overflow:hidden}
header{background:var(--ink);border-bottom:1px solid var(--hair);
padding:12px 20px;display:flex;align-items:center;gap:16px;flex:none}
h1{font-family:Gabarito,sans-serif;font-size:19px;letter-spacing:-.02em}
.tally{margin-left:auto;display:flex;gap:14px;font-size:13px;color:var(--muted);
white-space:nowrap}
.tally b{color:var(--text);font-variant-numeric:tabular-nums}
.tally .ok b{color:var(--accent)} .tally .fl b{color:var(--flag)}
.save{display:flex;align-items:center;gap:10px}
#saveState{font-size:12.5px;color:var(--muted);white-space:nowrap}
#saveState.err{color:var(--flag)} #saveState.busy{color:var(--rework)}
#saveBtn{font:inherit;font-size:13px;font-weight:700;padding:7px 16px;
border-radius:7px;border:1px solid var(--hair);background:var(--panel2);
color:var(--text);cursor:pointer}
#saveBtn:hover{border-color:var(--accent)}
.bar{height:4px;background:var(--panel2);flex:none}
.bar i{display:block;height:100%;background:var(--accent);transition:width .3s}
.wrap{flex:1;display:grid;grid-template-columns:290px 1fr;min-height:0}
aside{overflow-y:auto;border-right:1px solid var(--hair);padding-bottom:30px}
.chh{position:sticky;top:0;background:var(--ink);z-index:2;
font-family:Gabarito,sans-serif;font-size:12px;letter-spacing:.07em;
text-transform:uppercase;color:var(--muted);padding:12px 14px 6px;
border-bottom:1px solid var(--hair)}
.brow{display:grid;grid-template-columns:12px 50px 1fr auto;gap:9px;
align-items:center;padding:6px 14px 6px 11px;cursor:pointer;
border-left:3px solid transparent;font-size:13px}
.brow:hover{background:var(--panel)}
.brow.cur{background:var(--panel2);border-left-color:var(--accent)}
.dot{width:9px;height:9px;border-radius:50%;border:1.5px solid var(--hair)}
.dot.approved{background:var(--accent);border-color:var(--accent)}
.dot.flagged{background:var(--flag);border-color:var(--flag)}
.dot.reworked{background:var(--rework);border-color:var(--rework)}
.brow .bid{font-family:Gabarito,sans-serif;font-weight:800}
.brow .pu{color:var(--muted);overflow:hidden;text-overflow:ellipsis;
white-space:nowrap;font-size:12px}
.brow .du{color:var(--muted);font-size:11.5px;font-variant-numeric:tabular-nums}
.stage{overflow-y:auto;padding:20px 26px 60px}
.focus{max-width:940px;margin:0 auto;display:flex;flex-direction:column;gap:12px}
.crumb{font-size:13px;color:var(--muted)}
.crumb b{color:var(--text);font-family:Gabarito,sans-serif}
video{width:100%;aspect-ratio:16/9;background:#000;border-radius:12px;
display:block;outline:none}
.noproxy{display:flex;align-items:center;justify-content:center;
aspect-ratio:16/9;background:#000;border-radius:12px;color:var(--muted);
font-size:13px;text-align:center;padding:20px}
.row{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.chip{font-size:11px;letter-spacing:.08em;text-transform:uppercase;
background:var(--panel2);border-radius:4px;padding:3px 8px;color:var(--muted)}
.chip.acc{color:var(--accent)}
.cap{font-size:14px;color:var(--muted);border-left:2px solid var(--hair);
padding-left:12px}
.note{width:100%;background:var(--panel);border:1px solid var(--hair);
border-radius:9px;color:var(--text);padding:10px 12px;font:inherit;
font-size:14px;resize:vertical;min-height:64px}
.note:focus{border-color:var(--accent);outline:none}
.acts{display:flex;gap:10px}
.acts button{flex:1;font:inherit;font-size:15px;font-weight:800;padding:13px 0;
border-radius:9px;border:1px solid var(--hair);background:var(--panel2);
color:var(--text);cursor:pointer;font-family:Gabarito,sans-serif}
.acts button kbd{font-family:inherit;font-size:11px;opacity:.55;font-weight:400;
border:1px solid currentColor;border-radius:4px;padding:0 5px;margin-left:8px}
.acts .ok.on{background:var(--accent);border-color:var(--accent);color:#06110B}
.acts .fl.on{background:var(--flag);border-color:var(--flag)}
.nav{display:flex;gap:10px;align-items:center}
.nav button{font:inherit;font-size:13px;font-weight:700;padding:9px 16px;
border-radius:7px;border:1px solid var(--hair);background:transparent;
color:var(--muted);cursor:pointer}
.nav button:hover{color:var(--text);border-color:var(--muted)}
.nav .nu{margin-left:auto;color:var(--accent);border-color:rgba(18,183,106,.4)}
.nav .nu:hover{border-color:var(--accent);color:var(--accent)}
.done{background:var(--panel);border:1px solid rgba(18,183,106,.5);
border-radius:12px;padding:26px;text-align:center;
font-family:Gabarito,sans-serif;font-size:17px}
.hint{font-size:12px;color:var(--muted);text-align:center}
.hint kbd{border:1px solid var(--hair);border-radius:4px;padding:0 5px;
font-family:inherit}
.tabs{display:flex;gap:4px;background:var(--panel);border:1px solid var(--hair);
border-radius:9px;padding:3px}
.tabs button{font:inherit;font-size:13px;font-weight:700;padding:6px 14px;
border-radius:7px;border:0;background:transparent;color:var(--muted);
cursor:pointer;font-family:Gabarito,sans-serif}
.tabs button.on{background:var(--panel2);color:var(--text)}
.ovnew{margin:12px 14px 4px;display:block;width:calc(100% - 28px);font:inherit;
font-size:13px;font-weight:700;padding:9px 0;border-radius:8px;
border:1px dashed var(--hair);background:transparent;color:var(--muted);
cursor:pointer;font-family:Gabarito,sans-serif}
.ovnew:hover{color:var(--accent);border-color:var(--accent)}
.kitmenu{display:none;flex-wrap:wrap;gap:6px;padding:8px 14px}
.kitmenu.open{display:flex}
.kitmenu button{font:inherit;font-size:12px;padding:5px 10px;border-radius:6px;
border:1px solid var(--hair);background:var(--panel);color:var(--text);
cursor:pointer}
.kitmenu button:hover{border-color:var(--accent)}
.orow{display:grid;grid-template-columns:12px 60px 1fr;gap:9px;
align-items:center;padding:6px 14px 6px 11px;cursor:pointer;
border-left:3px solid transparent;font-size:13px}
.orow:hover{background:var(--panel)}
.orow.cur{background:var(--panel2);border-left-color:var(--accent)}
.orow .oid{font-family:Gabarito,sans-serif;font-weight:800}
.orow .osub{color:var(--muted);overflow:hidden;text-overflow:ellipsis;
white-space:nowrap;font-size:12px}
.dot.current{background:var(--accent);border-color:var(--accent)}
.dot.stale{background:var(--rework);border-color:var(--rework)}
.pvwrap{display:flex;justify-content:center;border-radius:12px;
background:repeating-conic-gradient(#141416 0% 25%,#1d1d21 0% 50%) 0 0/28px 28px}
.pvbox{position:relative;overflow:hidden}
.pvbox iframe{border:0;transform-origin:top left;pointer-events:none;
display:block}
.pvbar{display:flex;gap:10px;align-items:center;font-size:12.5px;
color:var(--muted)}
.pvbar button{font:inherit;font-size:13px;font-weight:700;padding:7px 14px;
border-radius:7px;border:1px solid var(--hair);background:var(--panel2);
color:var(--text);cursor:pointer}
.pvbar button:hover{border-color:var(--accent)}
.fields{display:grid;grid-template-columns:110px 1fr;gap:10px 12px;
align-items:start}
.fields label{font-size:11.5px;letter-spacing:.06em;text-transform:uppercase;
color:var(--muted);font-family:Gabarito,sans-serif;padding-top:10px}
.fields input[type=text],.fields textarea,.fields input[type=number]{
width:100%;background:var(--panel);border:1px solid var(--hair);
border-radius:8px;color:var(--text);padding:8px 10px;font:inherit;font-size:14px}
.fields textarea{resize:vertical;min-height:54px}
.fields textarea.raw{font-family:ui-monospace,Menlo,monospace;font-size:12.5px;
min-height:200px}
.fields textarea.bad{border-color:var(--flag)}
.fields input:focus,.fields textarea:focus{border-color:var(--accent);
outline:none}
.fields .fhint{grid-column:2;font-size:11.5px;color:var(--muted);margin-top:-6px}
.rowed{display:flex;flex-direction:column;gap:6px}
.rowed .rr{display:grid;grid-template-columns:1fr 110px 52px 26px;gap:6px;
align-items:center}
.rowed .rr .win{display:flex;align-items:center;gap:4px;font-size:11px;
color:var(--muted)}
.rowed .rr button{border:1px solid var(--hair);background:transparent;
color:var(--muted);border-radius:6px;cursor:pointer;font-size:14px;padding:4px 0}
.addrow{align-self:flex-start;font:inherit;font-size:12px;
border:1px dashed var(--hair);background:transparent;color:var(--muted);
border-radius:6px;padding:4px 10px;cursor:pointer}
.acts .ex.busy{opacity:.6;pointer-events:none}
.exrow{display:flex;gap:12px;align-items:center;flex-wrap:wrap;font-size:13px;
color:var(--muted)}
.exrow a,.exrow button{font:inherit;font-size:13px;font-weight:700;
padding:7px 14px;border-radius:7px;border:1px solid var(--hair);
background:var(--panel2);color:var(--text);cursor:pointer;text-decoration:none}
.exrow a:hover,.exrow button:hover{border-color:var(--accent)}
.exrow .cur{color:var(--accent)} .exrow .stl{color:var(--rework)}
.badge{font-size:11px;letter-spacing:.07em;text-transform:uppercase;
border-radius:4px;padding:2px 8px;background:var(--panel2);color:var(--rework)}
.del{margin-left:auto;color:var(--flag);background:none;border:none;
cursor:pointer;font:inherit;font-size:12.5px}
.proj{display:flex;gap:6px;align-items:center}
.proj select{font:inherit;font-size:13px;font-weight:700;padding:6px 10px;
border-radius:7px;border:1px solid var(--hair);background:var(--panel2);
color:var(--text);font-family:Gabarito,sans-serif}
.proj button{font:inherit;font-size:15px;font-weight:700;width:32px;height:32px;
border-radius:7px;border:1px dashed var(--hair);background:transparent;
color:var(--muted);cursor:pointer}
.proj button:hover{color:var(--accent);border-color:var(--accent)}
.phasebar{display:flex;gap:14px;align-items:center;padding:8px 20px;
border-bottom:1px solid var(--hair);font-size:12.5px;flex:none;
background:var(--panel)}
.phasebar .ph{display:flex;gap:5px;align-items:center;color:var(--muted);
letter-spacing:.05em;text-transform:uppercase;font-size:11px;
font-family:Gabarito,sans-serif;white-space:nowrap}
.phasebar .ph i{width:8px;height:8px;border-radius:50%;
border:1.5px solid var(--hair);display:block}
.phasebar .ph.done i{background:var(--accent);border-color:var(--accent)}
.phasebar .ph.cur{color:var(--text)}
.phasebar .ph.cur i{border-color:var(--rework);background:var(--rework)}
.phasebar .nx{margin-left:auto;color:var(--text);font-size:13px;
overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.phasebar .pwrap{margin-left:auto;display:flex;gap:12px;align-items:center;
min-width:0;flex:1;justify-content:flex-end}
.phasebar .ptxt{color:var(--text);font-size:13px;white-space:nowrap;
overflow:hidden;text-overflow:ellipsis}
.phasebar .pbar{width:220px;height:6px;background:var(--panel2);
border-radius:3px;flex:none;overflow:hidden}
.phasebar .pbar i{display:block;height:100%;background:var(--rework);
transition:width .5s}
.setup{border:2px dashed var(--hair);border-radius:14px;padding:44px 30px;
text-align:center;color:var(--muted);font-size:14.5px}
.setup.hot{border-color:var(--accent);color:var(--text);
background:rgba(18,183,106,.06)}
.setup b{color:var(--text);font-family:Gabarito,sans-serif;font-size:17px;
display:block;margin-bottom:8px}
.setup .row2{display:flex;gap:10px;justify-content:center;margin-top:18px}
.setup button{font:inherit;font-size:13px;font-weight:700;padding:8px 16px;
border-radius:7px;border:1px solid var(--hair);background:var(--panel2);
color:var(--text);cursor:pointer}
.setup button:hover{border-color:var(--accent)}
.uplist{display:flex;flex-direction:column;gap:5px;margin-top:16px;
font-size:12.5px;text-align:left}
.uplist .u{display:grid;grid-template-columns:1fr 90px;gap:10px;
color:var(--muted)}
.uplist .u.ok{color:var(--accent)} .uplist .u.err{color:var(--flag)}
.fgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(190px,1fr));
gap:12px;margin-top:22px;text-align:left}
.fcard{position:relative;background:var(--panel);border:1px solid var(--hair);
border-radius:10px;overflow:hidden}
.fcard img,.fcard video{display:block;width:100%;aspect-ratio:16/9;
object-fit:cover;background:#000;cursor:pointer}
.fcard .fn{font-size:12px;color:var(--text);padding:7px 9px 2px;
overflow:hidden;text-overflow:ellipsis;white-space:nowrap;
font-family:Gabarito,sans-serif}
.fcard .fm{font-size:11px;color:var(--muted);padding:0 9px 8px}
.fcard .fdel{position:absolute;top:6px;right:6px;width:24px;height:24px;
border-radius:6px;border:none;background:rgba(11,11,12,.75);
color:var(--flag);font-size:15px;cursor:pointer;line-height:1}
.fcard .fdel:hover{background:var(--flag);color:#fff}
.fcard .fbadge{position:absolute;top:6px;left:6px;font-size:10px;
letter-spacing:.07em;text-transform:uppercase;background:rgba(11,11,12,.75);
color:var(--rework);border-radius:4px;padding:2px 7px}
.scard{background:var(--panel);border:1px solid var(--hair);border-radius:12px;
padding:18px 20px;cursor:pointer;display:flex;flex-direction:column;gap:8px}
.scard:hover{border-color:var(--muted)}
.scard.pick{border-color:var(--accent);background:rgba(18,183,106,.05)}
.scard h3{font-family:Gabarito,sans-serif;font-size:17px}
.scard .lg{font-size:14px;color:var(--text)}
.scard .hk{font-size:13px;color:var(--rework)}
.scard ul{margin:4px 0 0 18px;font-size:13px;color:var(--muted)}
.scard .tone{font-size:11.5px;letter-spacing:.07em;text-transform:uppercase;
color:var(--muted)}
.srounds{font-size:12.5px;color:var(--muted);border-left:2px solid var(--hair);
padding-left:12px;display:flex;flex-direction:column;gap:6px}
.needs{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.needs span{font-size:11px;letter-spacing:.06em;text-transform:uppercase;
color:var(--muted)}
.needs button{font:inherit;font-size:12px;font-weight:700;padding:5px 12px;
border-radius:999px;border:1px solid var(--hair);background:transparent;
color:var(--muted);cursor:pointer}
.needs button.on{border-color:var(--rework);color:var(--rework);
background:rgba(232,163,61,.08)}
#ovmsg,#capmsg{font-size:13px;min-height:18px}
#ovmsg.err,#capmsg.err{color:var(--flag)}
#ovmsg.ok,#capmsg.ok{color:var(--accent)}
#capmsg.busy{color:var(--rework)}
</style></head><body>
<header><h1>Edit Room</h1>
<div class="proj"><select id="projSel"></select>
<button id="projNew" title="new project">＋</button></div>
<nav class="tabs"><button id="tabStory">Story</button>
<button id="tabShots" class="on">Shots</button>
<button id="tabOv">Overlays</button>
<button id="tabCap">Captions</button></nav>
<div class="tally"><span class="ok">approved <b id="tA">0</b></span>
<span class="fl">flagged <b id="tF">0</b></span>
<span>left <b id="tL">0</b></span></div>
<div class="save"><span id="saveState">All changes saved</span>
<button id="saveBtn">Save</button></div></header>
<div class="bar"><i id="prog" style="width:0"></i></div>
<div class="phasebar" id="phasebar"></div>
<div class="wrap" id="wrapShots"><aside id="side"></aside>
<section class="stage"><div class="focus" id="focus">loading…</div></section></div>
<div class="wrap" id="wrapOv" style="display:none"><aside id="ovside"></aside>
<section class="stage"><div class="focus" id="ovfocus">loading…</div></section></div>
<div class="wrap" id="wrapCap" style="display:none"><aside id="capside"></aside>
<section class="stage"><div class="focus" id="capfocus">loading…</div></section></div>
<div class="wrap" id="wrapStory" style="display:none;grid-template-columns:1fr">
<section class="stage"><div class="focus" id="storyfocus">loading…</div></section></div>
<script>
let SLUG='__INITIAL__'||localStorage.getItem('editroom.project')||'';
let PROJECTS=[], S=null, order=[], rows={}, idx=0, dirty={}, timers={};

function ls(){return 'editroom.'+SLUG+'.current';}
function api(p){return p+(p.includes('?')?'&':'?')+'slug='+encodeURIComponent(SLUG);}

function esc(s){return (s||'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));}

async function bootProjects(){
  const d=await(await fetch('/api/projects')).json();
  PROJECTS=d.projects;
  if(!PROJECTS.find(p=>p.slug===SLUG))
    SLUG=PROJECTS.length?PROJECTS[0].slug:'';
  localStorage.setItem('editroom.project',SLUG);
  const sel=document.getElementById('projSel');
  sel.innerHTML=PROJECTS.map(p=>'<option value="'+p.slug+'"'+
    (p.slug===SLUG?' selected':'')+'>'+p.slug+'</option>').join('');
  renderPhasebar();
}

function proj(){return PROJECTS.find(p=>p.slug===SLUG);}

function fmtEta(s){
  if(s==null)return 'estimating…';
  if(s<60)return '~'+Math.max(s,1)+'s left';
  return '~'+Math.round(s/60)+'m left';
}

function renderPhasebar(){
  const p=proj(), bar=document.getElementById('phasebar');
  if(!p){bar.innerHTML='<span class="nx">No projects yet — click ＋ to start one.</span>';return;}
  const PH=[['footage','Footage'],['ingest','Ingest'],['story','Story'],
            ['assembly','Assembly'],['review','Review'],['master','Master']];
  const ci=PH.findIndex(x=>x[0]===p.phase);
  let right;
  const pr=p.progress;
  if(pr){
    const STAGE={transcribe:'Transcribing',takes:'Analyzing takes',
                 broll:'Cataloging b-roll'};
    const pct=Math.round((pr.pct||0)*100);
    right='<span class="pwrap"><span class="ptxt">'+
      (STAGE[pr.stage]||pr.stage)+' '+(pr.done!=null?pr.done+'/'+pr.total:'')+
      (pr.current?' · '+esc(pr.current):'')+' · '+fmtEta(pr.eta_s)+
      '</span><span class="pbar"><i style="width:'+pct+'%"></i></span></span>';
  }else{
    right='<span class="nx" title="'+esc(p.next)+'">'+esc(p.next)+'</span>';
  }
  bar.innerHTML=PH.map((x,i)=>'<span class="ph '+(i<ci?'done':i===ci?'cur':'')+
    '"><i></i>'+x[1]+'</span>').join('')+right;
}

// live phase/progress: cheap poll; the select only rebuilds when the
// project list itself changes so an open dropdown never snaps shut
setInterval(async()=>{
  try{
    const d=await(await fetch('/api/projects')).json();
    const same=JSON.stringify(d.projects.map(p=>p.slug))===
               JSON.stringify(PROJECTS.map(p=>p.slug));
    PROJECTS=d.projects;
    if(!same)await bootProjects();
    else renderPhasebar();
  }catch(e){}
},5000);

async function switchProject(s){
  SLUG=s;localStorage.setItem('editroom.project',s);
  S=null;OV=null;CAP=null;STY=null;ovId=null;capId=null;idx=0;dirty={};
  await bootProjects();
  boot();
  const cur=document.querySelector('.tabs .on').id;
  if(cur==='tabOv')bootOv();else if(cur==='tabCap')bootCap();
  else if(cur==='tabStory')bootStory();
}
document.getElementById('projSel').onchange=e=>switchProject(e.target.value);
document.getElementById('projNew').onclick=async()=>{
  const name=prompt('New project name (folder under work/):');
  if(!name)return;
  try{
    const r=await fetch('/api/project/new',{method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({name:name})});
    const j=await r.json();
    if(!r.ok)throw new Error(j.error||'failed');
    await switchProject(j.slug);
  }catch(e){alert(e.message);}
};
function fmt(s){return Math.floor(s/60)+':'+String(Math.floor(s%60)).padStart(2,'0');}
function cur(){return order[idx];}
function needsReview(b){const st=b.review.status;return !st||st==='reworked';}

async function boot(){
  if(!SLUG){document.getElementById('side').innerHTML='';
    document.getElementById('focus').innerHTML=
      '<div class="done">Create a project with the ＋ button to begin.</div>';
    return;}
  S=await (await fetch(api('/api/state'))).json();
  order=[];
  for(const ch of S.chapters)for(const b of ch.beats){b.chapter=ch.title;order.push(b);}
  buildSide();
  if(!order.length){renderSetup();counts();return;}
  const remembered=localStorage.getItem(ls());
  let start=order.findIndex(b=>b.id===remembered);
  if(start<0)start=order.findIndex(needsReview);
  if(start<0)start=0;
  select(start,true);
  counts();
}

function renderSetup(){
  const p=proj()||{footage:0,next:''};
  document.getElementById('focus').innerHTML=
    '<div class="setup" id="dropzone"><b>'+esc(SLUG)+' — drop footage here</b>'+
    'Drag clips and photos (or whole folders) anywhere onto this box.<br>'+
    'Photos become 6-second b-roll clips automatically.'+
    '<div class="row2"><button id="bPickFiles">Choose files…</button>'+
    '<button id="bOpenFootage">Open footage folder in Finder</button>'+
    (p.footage?'<button id="bClearAll" style="color:var(--flag)">Remove all</button>':'')+
    '</div>'+
    '<div class="uplist" id="uplist"></div>'+
    '<div class="fgrid" id="fgrid"></div>'+
    '<div style="margin-top:18px;font-size:13px;color:var(--text)">'+
    (p.footage?p.footage+' clip(s) in. ':'')+esc(p.next)+'</div></div>'+
    '<input type="file" id="fileInput" multiple style="display:none" '+
    'accept="video/*,image/*">';
  const dz=document.getElementById('dropzone');
  const fi=document.getElementById('fileInput');
  document.getElementById('bPickFiles').onclick=e=>{e.stopPropagation();fi.click();};
  document.getElementById('bOpenFootage').onclick=e=>{e.stopPropagation();
    ovPost('/api/reveal',{footage:true});};
  const clr=document.getElementById('bClearAll');
  if(clr)clr.onclick=async e=>{
    e.stopPropagation();
    if(!confirm('Remove ALL footage from '+SLUG+'?\n(Everything moves to '+
      'footage/.trash — recoverable in Finder.)'))return;
    try{
      const r=await ovPost('/api/footage/clear',{});
      await bootProjects();
      renderSetup();
      if(r.reingest)alert('Cleared. This project was already ingested — '+
        'tell Claude to re-ingest '+SLUG+' if you rebuild it.');
    }catch(err){alert(err.message);}
  };
  fi.addEventListener('click',e=>e.stopPropagation());
  fi.onchange=()=>uploadFiles([...fi.files]);
  ['dragenter','dragover'].forEach(ev=>dz.addEventListener(ev,e=>{
    e.preventDefault();dz.classList.add('hot');}));
  ['dragleave','drop'].forEach(ev=>dz.addEventListener(ev,e=>{
    e.preventDefault();dz.classList.remove('hot');}));
  loadFootage();
  dz.addEventListener('drop',async e=>{
    // DataTransfer items die at the end of the drop tick — snapshot every
    // entry SYNCHRONOUSLY before the first await, then walk at leisure.
    const entries=[];
    for(const it of e.dataTransfer.items){
      const en=it.webkitGetAsEntry&&it.webkitGetAsEntry();
      if(en)entries.push(en);
    }
    const files=entries.length?[]:[...e.dataTransfer.files];
    const collect=async entry=>{
      if(entry.isFile){
        await new Promise(res=>entry.file(f=>{files.push(f);res();},
                                          ()=>res()));
      }else if(entry.isDirectory){
        const reader=entry.createReader();
        for(;;){ // readEntries hands back at most ~100 per call
          const batch=await new Promise(res=>
            reader.readEntries(res,()=>res([])));
          if(!batch||!batch.length)break;
          for(const s of batch)await collect(s);
        }
      }
    };
    for(const en of entries)await collect(en);
    uploadFiles(files);
  });
}

function fmtSize(b){
  return b>=1e9?(b/1e9).toFixed(2)+' GB':b>=1e6?(b/1e6).toFixed(1)+' MB':
    Math.round(b/1e3)+' KB';
}

async function loadFootage(){
  const grid=document.getElementById('fgrid');
  if(!grid)return;
  const d=await(await fetch(api('/api/footage'))).json();
  grid.innerHTML=(d.ingested&&d.files.length
    ?'<div style="grid-column:1/-1;color:var(--rework);font-size:12.5px">'+
     'this project is already ingested — after removing clips, tell Claude '+
     'to re-ingest</div>':'')+
    d.files.map(f=>{
    const label=f.still&&f.still_src?f.still_src:f.name;
    return '<div class="fcard" data-f="'+esc(f.name)+'">'+
      (f.thumb?'<img src="/file?p='+encodeURIComponent(f.thumb)+
        '" title="click to play">':'<img title="click to play">')+
      (f.still?'<span class="fbadge">photo</span>':'')+
      '<button class="fdel" title="remove">×</button>'+
      '<div class="fn">'+esc(label)+'</div>'+
      '<div class="fm">'+(f.dur?f.dur+'s · ':'')+
      (f.w?f.w+'×'+f.h+' · ':'')+fmtSize(f.size)+'</div></div>';
  }).join('');
  grid.querySelectorAll('.fcard').forEach(card=>{
    const name=card.dataset.f;
    card.querySelector('img').onclick=e=>{
      e.stopPropagation();
      const v=document.createElement('video');
      v.controls=true;v.autoplay=true;v.playsinline=true;
      v.src='/media/'+SLUG+'/footage/'+encodeURIComponent(name);
      card.querySelector('img').replaceWith(v);
    };
    card.querySelector('.fdel').onclick=async e=>{
      e.stopPropagation();
      if(!confirm('Remove '+name+' from this project?\n(It moves to '+
        'footage/.trash, recoverable in Finder.)'))return;
      try{
        const r=await ovPost('/api/footage/delete',{name:name});
        await bootProjects();
        await loadFootage();
        if(r.reingest)alert('Removed. This project was already ingested — '+
          'tell Claude to re-ingest '+SLUG+' so the analysis matches.');
      }catch(err){alert(err.message);}
    };
  });
}

// A drop that misses the zone must NEVER navigate the app away — the
// browser's default for a dropped folder is to OPEN it, replacing the Edit
// Room with a file:// listing (Caleb hit this, 2026-08-20).
['dragover','drop'].forEach(ev=>document.addEventListener(ev,e=>{
  e.preventDefault();}));

async function uploadFiles(files){
  const ok=/\.(mp4|mov|m4v|mts|avi|mkv|jpg|jpeg|png|heic|webp)$/i;
  const list=document.getElementById('uplist');
  if(!list)return;
  const usable=files.filter(f=>ok.test(f.name));
  if(!usable.length&&files.length){
    const row=document.createElement('div');row.className='u err';
    row.textContent='nothing uploadable in that drop (videos and photos only)';
    list.appendChild(row);return;
  }
  // duplicates never even upload: name+size against the current inventory
  // (the server re-checks by content, so this is only the fast path)
  const have=new Set();
  try{
    const inv=await(await fetch(api('/api/footage'))).json();
    for(const f of inv.files){
      have.add(f.name+'|'+f.size);
      if(f.still_src)have.add(f.still_src+'|'+f.src_size);
    }
  }catch(e){}
  for(const f of usable){
    const row=document.createElement('div');row.className='u';
    row.innerHTML='<span>'+esc(f.name)+'</span><span class="pc">0%</span>';
    list.appendChild(row);
    if(have.has(f.name+'|'+f.size)){
      row.className='u';row.style.color='var(--rework)';
      row.querySelector('.pc').textContent='duplicate — skipped';
      continue;
    }
    await new Promise(res=>{
      const xhr=new XMLHttpRequest();
      xhr.open('POST','/api/upload?slug='+encodeURIComponent(SLUG)+
        '&name='+encodeURIComponent(f.name));
      xhr.upload.onprogress=e=>{if(e.lengthComputable)
        row.querySelector('.pc').textContent=Math.round(100*e.loaded/e.total)+'%';};
      xhr.onload=()=>{
        if(xhr.status===200){
          let dup=null;
          try{dup=JSON.parse(xhr.response).duplicate;}catch(e2){}
          if(dup){row.style.color='var(--rework)';
            row.querySelector('.pc').textContent='duplicate of '+dup+' — skipped';}
          else{row.className='u ok';
            row.querySelector('.pc').textContent='✓';}}
        else{row.className='u err';
          try{row.querySelector('.pc').textContent=JSON.parse(xhr.response).error;}
          catch(e2){row.querySelector('.pc').textContent='failed';}}
        res();};
      xhr.onerror=()=>{row.className='u err';
        row.querySelector('.pc').textContent='failed';res();};
      xhr.send(f);
    });
  }
  await bootProjects();
  await loadFootage();
  const p=proj();
  const note=document.querySelector('#dropzone > div:last-of-type');
  if(note&&p)note.textContent=p.footage+' clip(s) in. '+p.next;
}

function buildSide(){
  const side=document.getElementById('side');side.innerHTML='';
  let i=0;
  for(const ch of S.chapters){
    const h=document.createElement('div');h.className='chh';
    h.textContent=ch.title;side.appendChild(h);
    for(const b of ch.beats){
      const j=i++;
      const r=document.createElement('div');r.className='brow';
      r.innerHTML='<span class="dot"></span><span class="bid">'+b.id+'</span>'+
        '<span class="pu">'+esc(b.purpose)+'</span>'+
        '<span class="du">'+b.dur+'s</span>';
      r.onclick=()=>select(j);
      rows[b.id]=r;side.appendChild(r);patchRow(b);
    }
  }
}

function patchRow(b){
  const d=rows[b.id].querySelector('.dot');
  d.className='dot '+(b.review.status||'');
}

function select(i,first){
  if(!first)flushNote(cur().id);
  idx=i;localStorage.setItem(ls(),cur().id);
  renderFocus();
  for(const id in rows)rows[id].classList.toggle('cur',id===cur().id);
  rows[cur().id].scrollIntoView({block:'nearest'});
}

function renderFocus(){
  const b=cur(), f=document.getElementById('focus');
  const st=b.review.status||'';
  const pos=idx+1, T=order.length;
  const vid=b.proxy
    ?'<video id="vid" controls autoplay playsinline src="/media/'+SLUG+'/proxies/'+b.proxy+'"></video>'
    :'<div class="noproxy">no proxy yet — run:<br>pipeline.cli proxy '+SLUG+' --beat '+b.id+'</div>';
  const nd=b.review.needs||[];
  const needsRow='<div class="needs"><span>this shot needs:</span>'+
    [['broll','＋ b-roll'],['sfx','＋ SFX'],['cards','＋ cards']].map(x=>
      '<button data-need="'+x[0]+'" class="'+(nd.includes(x[0])?'on':'')+'">'+
      x[1]+'</button>').join('')+'</div>';
  const cards=b.cards.map(c=>'<span class="chip acc">'+esc(c.kit)+': '+esc(String(c.copy).slice(0,26))+'</span>').join('');
  f.innerHTML=
    '<div class="crumb"><b>'+b.id+'</b> · '+esc(b.chapter)+' · shot '+pos+' of '+T+'</div>'+
    vid+
    '<div class="row"><span class="chip">'+esc(b.purpose)+'</span>'+
    '<span class="chip">'+b.dur+'s @ '+fmt(b.record_s)+'</span>'+
    (b.take?'<span class="chip">'+esc(b.take)+'</span>':'')+
    (b.broll.length?'<span class="chip">b-roll ×'+b.broll.length+'</span>':'')+
    cards+'</div>'+
    (b.caption?'<div class="cap">'+esc(b.caption)+'</div>':'')+
    needsRow+
    '<textarea class="note" id="note" placeholder="note for the shot-fixer…">'+
      esc(dirty[b.id]!==undefined?dirty[b.id]:(b.review.note||''))+'</textarea>'+
    '<div class="acts">'+
    '<button class="ok '+(st==='approved'?'on':'')+'" id="bOk">Approve<kbd>A</kbd></button>'+
    '<button class="fl '+(st==='flagged'?'on':'')+'" id="bFl">Flag<kbd>F</kbd></button></div>'+
    '<div class="nav"><button id="bPrev">‹ Prev</button>'+
    '<button id="bNext">Next ›</button>'+
    '<button class="nu" id="bNu">Next unreviewed ↵</button></div>'+
    '<div class="hint"><kbd>A</kbd> approve · <kbd>F</kbd> flag · '+
    '<kbd>←</kbd><kbd>→</kbd> prev/next · <kbd>↵</kbd> next unreviewed · '+
    '<kbd>space</kbd> play/pause</div>';
  const note=document.getElementById('note');
  note.addEventListener('input',()=>queueNote(b.id,note.value));
  note.addEventListener('blur',()=>flushNote(b.id));
  f.querySelectorAll('[data-need]').forEach(el=>{
    el.onclick=async()=>{
      el.classList.toggle('on');
      const needs=[...f.querySelectorAll('[data-need].on')].map(x=>x.dataset.need);
      b.review.needs=needs;
      try{await post({beat_id:b.id,status:b.review.status||null,needs:needs});
        setSaved();}
      catch(e){setState('Save failed — retrying…','err');}
    };
  });
  document.getElementById('bOk').onclick=()=>decide('approved');
  document.getElementById('bFl').onclick=()=>decide('flagged');
  document.getElementById('bPrev').onclick=()=>select((idx-1+order.length)%order.length);
  document.getElementById('bNext').onclick=()=>select((idx+1)%order.length);
  document.getElementById('bNu').onclick=gotoUnreviewed;
}

function gotoUnreviewed(){
  const T=order.length;
  for(let k=1;k<=T;k++){
    const j=(idx+k)%T;
    if(needsReview(order[j])){select(j);return;}
  }
  const f=document.getElementById('focus');
  const d=document.createElement('div');d.className='done';
  d.textContent='Every shot is reviewed. Tell Claude to run the shot-fixer on the flags.';
  f.prepend(d);
}

function counts(){
  let A=0,F=0;
  for(const b of order){
    if(b.review.status==='approved')A++;
    else if(b.review.status==='flagged')F++;
  }
  const T=order.length;
  document.getElementById('tA').textContent=A;
  document.getElementById('tF').textContent=F;
  document.getElementById('tL').textContent=T-A-F;
  document.getElementById('prog').style.width=(T?100*(A+F)/T:0)+'%';
}

function setState(txt,cls){
  const el=document.getElementById('saveState');
  el.textContent=txt;el.className=cls||'';
}

async function post(body){
  body=Object.assign({slug:SLUG},body);
  const r=await fetch('/api/review',{method:'POST',
    headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  if(!r.ok)throw new Error('save failed');
}

function queueNote(id,val){
  dirty[id]=val;
  setState('Unsaved changes…','busy');
  clearTimeout(timers[id]);
  timers[id]=setTimeout(()=>flushNote(id),900);
}

async function flushNote(id){
  if(dirty[id]===undefined)return;
  const b=order.find(x=>x.id===id), note=dirty[id];
  clearTimeout(timers[id]);
  try{
    await post({beat_id:id,status:b.review.status||null,note:note});
    b.review.note=note;
    if(dirty[id]===note)delete dirty[id];
    if(!Object.keys(dirty).length)setSaved();
  }catch(e){
    setState('Save failed — retrying…','err');
    timers[id]=setTimeout(()=>flushNote(id),3000);
  }
}

function setSaved(){
  const t=new Date().toLocaleTimeString([],{hour:'numeric',minute:'2-digit'});
  setState('All changes saved · '+t);
}

async function decide(status){
  const b=cur(), note=document.getElementById('note').value;
  clearTimeout(timers[b.id]);delete dirty[b.id];
  setState('Saving…','busy');
  try{
    await post({beat_id:b.id,status:status,note:note});
    b.review={status:status,note:note};
    patchRow(b);counts();setSaved();
    setTimeout(gotoUnreviewed,150);
  }catch(e){setState('Save failed — click Save to retry','err');}
}

document.getElementById('saveBtn').onclick=async()=>{
  const ids=Object.keys(dirty);
  if(!ids.length){setSaved();return;}
  setState('Saving…','busy');
  for(const id of ids)await flushNote(id);
};

document.addEventListener('keydown',e=>{
  const tag=(e.target.tagName||'').toLowerCase();
  if(tag==='textarea'||tag==='input'){
    if(e.key==='Escape')e.target.blur();
    return;
  }
  if(document.getElementById('wrapShots').style.display==='none')return;
  if(e.key==='a'||e.key==='A')decide('approved');
  else if(e.key==='f'||e.key==='F')decide('flagged');
  else if(e.key==='ArrowLeft')select((idx-1+order.length)%order.length);
  else if(e.key==='ArrowRight')select((idx+1)%order.length);
  else if(e.key==='Enter')gotoUnreviewed();
  else if(e.key===' '){
    e.preventDefault();
    const v=document.getElementById('vid');
    if(v)v.paused?v.play():v.pause();
  }
});

window.addEventListener('beforeunload',()=>{
  for(const id in dirty){
    const b=order.find(x=>x.id===id);
    navigator.sendBeacon('/api/review',
      JSON.stringify({slug:SLUG,beat_id:id,status:(b&&b.review.status)||null,note:dirty[id]}));
  }
});

/* ---------------- Overlays desk ---------------- */
let OV=null, ovRows={}, ovId=null, ovWork=null, pvTimer=null, pvHtml='';

// field editors per kit screen: [key, widget]
const KIT_FIELDS={
  hook:[['kicker','text'],['text','area'],['emphasis','emph']],
  chapter:[['kicker','text'],['text','area'],['subtext','text']],
  transition:[['kicker','text'],['text','area']],
  lower_third:[['kicker','text'],['text','area'],['subtext','text'],
               ['subtext_italic','check'],['emphasis','emph']],
  stat:[['kicker','text'],['stat','text'],['text','area']],
  payoff:[['text','area'],['attribution','text'],['emphasis','emph']],
  vote:[['kicker','text'],['text','text'],['rows','rows']],
  scoreboard:[['kicker','text'],['entries','rows']],
  stamp:[['text','text']],
  reaction:[['text','area'],['attribution','text']],
  emoji:[['emojis','emojis']],
  watermark:[],
  caption_plate:[['speaker','text'],['text','area']],
  outro:[['kicker','text'],['text','area'],['subtext','text'],
         ['cta','text'],['emphasis','emph']]
};
const FIELD_HINTS={emphasis:'comma-separated exact phrases to turn amber',
  emojis:'emoji separated by spaces, e.g. 🦕 😱'};

function tab(which){
  const wraps={shots:'wrapShots',ov:'wrapOv',cap:'wrapCap',story:'wrapStory'};
  const tabs={shots:'tabShots',ov:'tabOv',cap:'tabCap',story:'tabStory'};
  for(const k in wraps){
    const el=document.getElementById(wraps[k]);
    if(k==='story')el.style.display=(k===which)?'grid':'none';
    else el.style.display=(k===which)?'':'none';
    document.getElementById(tabs[k]).classList.toggle('on',k===which);
  }
  history.replaceState(null,'',
    which==='ov'?'#overlays':which==='cap'?'#captions':
    which==='story'?'#story':'#');
  if(which==='ov'&&!OV)bootOv();
  if(which==='cap'&&!CAP)bootCap();
  if(which==='story'&&!STY)bootStory();
}
document.getElementById('tabShots').onclick=()=>tab('shots');
document.getElementById('tabOv').onclick=()=>tab('ov');
document.getElementById('tabCap').onclick=()=>tab('cap');
document.getElementById('tabStory').onclick=()=>tab('story');

function ovItem(id){return OV.overlays.find(o=>o.id===id);}
function ovKit(o){return o.kit||'';}
function ovMsg(txt,cls){const el=document.getElementById('ovmsg');
  if(el){el.textContent=txt||'';el.className=cls||'';}}

async function bootOv(keep){
  OV=await(await fetch(api('/api/overlays'))).json();
  buildOvSide();
  const want=keep||ovId;
  if(want&&ovItem(want))selectOv(want);
  else if(OV.overlays.length)selectOv(OV.overlays[0].id);
  else document.getElementById('ovfocus').innerHTML=
    '<div class="done">No overlays yet — create one with ＋ New overlay.</div>';
}

function buildOvSide(){
  const side=document.getElementById('ovside');side.innerHTML='';ovRows={};
  const nb=document.createElement('button');nb.className='ovnew';
  nb.textContent='＋ New overlay';side.appendChild(nb);
  const menu=document.createElement('div');menu.className='kitmenu';
  for(const k of OV.kits){
    const b=document.createElement('button');b.textContent=k;
    b.onclick=()=>newOverlay(k);menu.appendChild(b);
  }
  side.appendChild(menu);
  nb.onclick=()=>menu.classList.toggle('open');
  const groups=[['On the timeline',OV.overlays.filter(o=>o.source==='plan')],
                ['Custom',OV.overlays.filter(o=>o.source==='custom')]];
  for(const [title,list] of groups){
    if(!list.length)continue;
    const h=document.createElement('div');h.className='chh';
    h.textContent=title;side.appendChild(h);
    for(const o of list){
      const r=document.createElement('div');r.className='orow';
      const copy=o.card.text||o.card.stat||o.card.kicker||'';
      r.innerHTML='<span class="dot"></span><span class="oid">'+o.id+'</span>'+
        '<span class="osub">'+esc((o.beat?o.beat+' · ':'')+ovKit(o)+
        (copy?' · '+String(copy).replace(/\n/g,' ').slice(0,30):''))+'</span>';
      r.onclick=()=>selectOv(o.id);
      ovRows[o.id]=r;side.appendChild(r);patchOvRow(o);
    }
  }
}

function patchOvRow(o){
  const d=ovRows[o.id].querySelector('.dot');
  d.className='dot '+(o.export.status==='current'?'current':
                     o.export.status==='stale'?'stale':'');
}

function selectOv(id){
  ovId=id;
  const o=ovItem(id);
  ovWork=JSON.parse(JSON.stringify(o.card));
  for(const k in ovRows)ovRows[k].classList.toggle('cur',k===id);
  if(ovRows[id])ovRows[id].scrollIntoView({block:'nearest'});
  renderOvFocus();
  if(!o.prebaked)refreshPreview();
}

function ovInput(key,widget){
  const v=ovWork[key];
  if(widget==='area')return '<textarea data-k="'+key+'" data-w="area">'+
    esc(v||'')+'</textarea>';
  if(widget==='check')return '<input type="checkbox" data-k="'+key+
    '" data-w="check"'+((v===undefined||v)?' checked':'')+'>';
  if(widget==='emph')return '<input type="text" data-k="'+key+'" data-w="emph" value="'+
    esc((v||[]).join(', '))+'">';
  if(widget==='emojis')return '<input type="text" data-k="'+key+'" data-w="emojis" value="'+
    esc((v||[]).map(e=>e.char).join(' '))+'">';
  return '<input type="text" data-k="'+key+'" data-w="text" value="'+esc(v||'')+'">';
}

function rowsEditorHtml(key){
  const list=ovWork[key]||[];
  let out='<div class="rowed" id="rowed_'+key+'">';
  list.forEach((r,i)=>{
    out+='<div class="rr">'+
      '<input type="text" data-rk="'+key+'" data-ri="'+i+'" data-rf="label" value="'+esc(r.label||'')+'">'+
      '<input type="text" data-rk="'+key+'" data-ri="'+i+'" data-rf="value" value="'+esc(r.value||'')+'">'+
      '<span class="win"><input type="checkbox" data-rk="'+key+'" data-ri="'+i+
        '" data-rf="highlight"'+(r.highlight?' checked':'')+'>win</span>'+
      '<button data-rdel="'+key+'" data-ri="'+i+'" title="remove">×</button></div>';
  });
  out+='<button class="addrow" data-radd="'+key+'">＋ row</button></div>';
  return out;
}

function renderOvFocus(){
  const o=ovItem(ovId), f=document.getElementById('ovfocus');
  const kit=ovKit(o);
  const crumb='<div class="crumb"><b>'+o.id+'</b> · '+
    (o.beat?esc(o.beat):'custom — not on the timeline')+' · '+esc(kit)+
    (o.prebaked?' <span class="badge">prebaked</span>':'')+'</div>';
  const ex=o.export;
  const exrow='<div class="exrow" id="exrow">'+
    (ex.file
      ?('<span class="'+(ex.status==='current'?'cur':'stl')+'">'+
        (ex.status==='current'?'✓ exported':'⚠ export is stale — re-export')+
        '</span><a href="/media/'+SLUG+'/exports/'+encodeURIComponent(ex.file)+
        '" download>Download</a>'+
        '<button id="bReveal">Reveal in Finder</button>'+
        '<span>'+esc(ex.file)+'</span>')
      :'<span>not exported yet</span><button id="bFolder">Open export folder</button>')+
    '</div>';
  if(o.prebaked){
    f.innerHTML=crumb+
      '<div class="noproxy">Prebaked effect clip — its pixels are baked footage, '+
      'so there is nothing to edit here. Approve &amp; Export copies the clip '+
      'out under a proper name. Preview it on the Shots desk.</div>'+
      '<div class="acts"><button class="ok ex" id="bExport">Approve &amp; Export .mov</button></div>'+
      exrow+'<div id="ovmsg"></div>';
    wireOvActions(o);return;
  }
  const W=OV.canvas[0],H=OV.canvas[1];
  const scale=Math.min(870/W,500/H);
  const pw=Math.round(W*scale),ph=Math.round(H*scale);
  const fields=KIT_FIELDS[kit];
  let form='';
  if(fields===undefined){
    form='<label>raw json</label><textarea class="raw" id="rawjson">'+
      esc(JSON.stringify(ovWork,null,2))+'</textarea>';
  }else{
    for(const [key,widget] of fields){
      form+='<label>'+esc(key.replace(/_/g,' '))+'</label>'+
        (widget==='rows'?rowsEditorHtml(key):ovInput(key,widget));
      if(FIELD_HINTS[key])form+='<div class="fhint">'+FIELD_HINTS[key]+'</div>';
    }
  }
  form+='<label>duration s</label><input type="number" step="0.1" min="1" max="15" '+
    'data-k="duration" data-w="num" value="'+(ovWork.duration||3)+'">';
  if(o.beat)form+='<label>at s (in beat)</label><input type="number" step="0.1" min="0" '+
    'data-k="at" data-w="num" value="'+(ovWork.at||0)+'">';
  f.innerHTML=crumb+
    '<div class="pvwrap"><div class="pvbox" style="width:'+pw+'px;height:'+ph+'px">'+
    '<iframe id="pvframe" width="'+W+'" height="'+H+
    '" style="transform:scale('+scale+')"></iframe></div></div>'+
    '<div class="pvbar"><button id="bReplay">↺ Replay animation</button>'+
    '<span>live preview — the checkerboard is transparency; edits render as you type</span></div>'+
    '<div class="fields" id="ovform">'+form+'</div>'+
    '<div class="acts"><button id="bSaveOv">Save changes</button>'+
    '<button class="ok ex" id="bExport">Approve &amp; Export .mov</button>'+
    (o.source==='custom'?'<button class="del" id="bDelOv">Delete overlay</button>':'')+
    '</div>'+exrow+'<div id="ovmsg"></div>';
  wireOvForm(o);wireOvActions(o);
}

function wireOvForm(o){
  const form=document.getElementById('ovform');
  if(!form)return;
  const raw=document.getElementById('rawjson');
  if(raw){
    raw.addEventListener('input',()=>{
      try{const j=JSON.parse(raw.value);j.id=o.id;ovWork=j;
        raw.classList.remove('bad');schedulePreview();}
      catch(e){raw.classList.add('bad');}
    });
  }
  form.querySelectorAll('[data-k]').forEach(el=>{
    el.addEventListener('input',()=>{
      const k=el.dataset.k,w=el.dataset.w;
      if(w==='check')ovWork[k]=el.checked;
      else if(w==='num'){const n=parseFloat(el.value);
        if(!isNaN(n))ovWork[k]=n;}
      else if(w==='emph'){
        const list=el.value.split(',').map(s=>s.trim()).filter(Boolean);
        if(list.length)ovWork[k]=list;else delete ovWork[k];}
      else if(w==='emojis'){
        const old=ovWork[k]||[];
        const chars=el.value.split(/\s+/).filter(Boolean);
        ovWork[k]=chars.map((ch,i)=>Object.assign({},old[i]||{},{char:ch}));}
      else{if(el.value==='')delete ovWork[k];else ovWork[k]=el.value;}
      schedulePreview();
    });
  });
  form.querySelectorAll('[data-rk]').forEach(el=>{
    el.addEventListener('input',()=>{
      const k=el.dataset.rk,i=+el.dataset.ri,fld=el.dataset.rf;
      const list=ovWork[k]||(ovWork[k]=[]);
      if(!list[i])list[i]={};
      if(fld==='highlight'){
        if(el.checked)list[i].highlight=true;else delete list[i].highlight;}
      else list[i][fld]=el.value;
      schedulePreview();
    });
  });
  form.querySelectorAll('[data-radd]').forEach(el=>{
    el.onclick=()=>{const k=el.dataset.radd;
      (ovWork[k]||(ovWork[k]=[])).push({label:'',value:'0'});
      redrawRows(k,o);schedulePreview();};
  });
  form.querySelectorAll('[data-rdel]').forEach(el=>{
    el.onclick=()=>{const k=el.dataset.rdel;
      ovWork[k].splice(+el.dataset.ri,1);
      redrawRows(k,o);schedulePreview();};
  });
}

function redrawRows(key,o){
  const holder=document.getElementById('rowed_'+key);
  if(!holder)return;
  holder.outerHTML=rowsEditorHtml(key);
  wireOvForm(o);
}

function wireOvActions(o){
  const rp=document.getElementById('bReplay');
  if(rp)rp.onclick=()=>{const f=document.getElementById('pvframe');
    if(f&&pvHtml)f.srcdoc=pvHtml;};
  const sv=document.getElementById('bSaveOv');
  if(sv)sv.onclick=()=>saveOv(o);
  const exb=document.getElementById('bExport');
  if(exb)exb.onclick=()=>exportOv(o);
  const del=document.getElementById('bDelOv');
  if(del)del.onclick=async()=>{
    if(!confirm('Delete '+o.id+' and its export?'))return;
    await ovPost('/api/overlay/delete',{id:o.id});
    ovId=null;bootOv();
  };
  const rv=document.getElementById('bReveal');
  if(rv)rv.onclick=()=>ovPost('/api/reveal',{file:o.export.file});
  const fo=document.getElementById('bFolder');
  if(fo)fo.onclick=()=>ovPost('/api/reveal',{});
}

async function ovPost(url,body){
  body=Object.assign({slug:SLUG},body);
  const r=await fetch(url,{method:'POST',
    headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  const j=await r.json();
  if(!r.ok)throw new Error(j.error||'request failed');
  return j;
}

function schedulePreview(){
  clearTimeout(pvTimer);
  pvTimer=setTimeout(refreshPreview,350);
  ovMsg('unsaved edits — Save to keep them, Approve & Export to ship them','');
}

async function refreshPreview(){
  const o=ovItem(ovId);
  if(!o||o.prebaked)return;
  try{
    const j=await ovPost('/api/overlay/html',
      {card:ovWork,w:OV.canvas[0],h:OV.canvas[1]});
    pvHtml=j.html;
    const f=document.getElementById('pvframe');
    if(f)f.srcdoc=pvHtml;
  }catch(e){ovMsg('preview failed: '+e.message,'err');}
}

function ovUpdates(){
  const KEYS=['kicker','text','subtext','subtext_italic','emphasis','stat',
    'attribution','rows','entries','emojis','duration','at','size','speaker',
    'cta','sides','travel_ms','accent','x','y'];
  const u={};
  for(const k of KEYS){
    if(k in ovWork)u[k]=ovWork[k];
    else u[k]='';
  }
  return u;
}

async function saveOv(o,quiet){
  try{
    const j=await ovPost('/api/overlay/save',{id:o.id,updates:ovUpdates()});
    o.card=j.card;ovWork=JSON.parse(JSON.stringify(j.card));
    if(!quiet){ovMsg('saved','ok');bootOv(o.id);}
    return true;
  }catch(e){ovMsg(e.message,'err');return false;}
}

async function exportOv(o){
  const btn=document.getElementById('bExport');
  if(!o.prebaked&&!(await saveOv(o,true)))return;
  btn.classList.add('busy');
  btn.textContent='Baking… (instant if unchanged, ~a minute fresh)';
  ovMsg('rendering the ProRes 4444 alpha .mov…','');
  try{
    const j=await ovPost('/api/overlay/export',{id:o.id});
    let msg='exported '+j.file;
    if(j.reproxied)msg+=' · the '+o.beat+' proxy was refreshed';
    if(j.review_reset)msg+=' and reset to re-review on the Shots desk';
    ovMsg(msg,'ok');
    await bootOv(o.id);
    if(j.reproxied)boot();
  }catch(e){
    ovMsg('export failed: '+e.message,'err');
    btn.classList.remove('busy');
    btn.textContent='Approve & Export .mov';
  }
}

async function newOverlay(kit){
  try{
    const j=await ovPost('/api/overlay/new',{kit_type:kit});
    await bootOv(j.card.id);
  }catch(e){ovMsg(e.message,'err');}
}

/* ---------------- Captions desk ---------------- */
let CAP=null, capRows={}, capId=null;

function capMsg(txt,cls){const el=document.getElementById('capmsg');
  if(el){el.textContent=txt||'';el.className=cls||'';}}

async function bootCap(keep){
  CAP=await(await fetch(api('/api/captions'))).json();
  buildCapSide();
  const want=keep||capId;
  if(want&&CAP.beats.find(b=>b.id===want))selectCap(want);
  else if(CAP.beats.length)selectCap(CAP.beats[0].id);
  else document.getElementById('capfocus').innerHTML=
    '<div class="done">This edit has no captions.</div>';
}

function buildCapSide(){
  const side=document.getElementById('capside');side.innerHTML='';capRows={};
  let ch=null;
  for(const b of CAP.beats){
    if(b.chapter!==ch){
      ch=b.chapter;
      const h=document.createElement('div');h.className='chh';
      h.textContent=ch||'Captions';side.appendChild(h);
    }
    const r=document.createElement('div');r.className='orow';
    r.innerHTML='<span class="dot"></span><span class="oid">'+b.id+'</span>'+
      '<span class="osub">'+esc(String(b.text).slice(0,34))+'</span>';
    r.onclick=()=>selectCap(b.id);
    capRows[b.id]=r;side.appendChild(r);patchCapRow(b);
  }
}

function patchCapRow(b){
  const d=capRows[b.id].querySelector('.dot');
  d.className='dot '+(b.edited?'stale':'');
}

function capItem(id){return CAP.beats.find(b=>b.id===id);}

function selectCap(id){
  capId=id;
  const b=capItem(id), f=document.getElementById('capfocus');
  for(const k in capRows)capRows[k].classList.toggle('cur',k===id);
  if(capRows[id])capRows[id].scrollIntoView({block:'nearest'});
  const vid=b.proxy
    ?'<video id="capvid" controls playsinline src="/media/'+SLUG+'/proxies/'+b.proxy+'"></video>'
    :'<div class="noproxy">no proxy for this beat yet</div>';
  f.innerHTML=
    '<div class="crumb"><b>'+b.id+'</b> · '+esc(b.chapter)+' · '+b.dur+'s'+
    (b.edited?' <span class="badge">edited</span>':'')+'</div>'+
    vid+
    '<textarea class="note" id="captext" rows="4" style="min-height:96px">'+
    esc(b.text)+'</textarea>'+
    '<div class="hint" style="text-align:left">Text is the script; timing '+
    'stays locked to the spoken words. Emoji ride along inside a word '+
    '("cockroaches 🪳"). Blank the box to remove this beat\'s captions.</div>'+
    '<div class="acts"><button id="bCapSave">Save &amp; Re-bake</button>'+
    (b.edited?'<button id="bCapRevert">Revert to original</button>':'')+
    '</div><div id="capmsg"></div>';
  document.getElementById('bCapSave').onclick=()=>saveCap(false);
  const rv=document.getElementById('bCapRevert');
  if(rv)rv.onclick=()=>saveCap(true);
  document.getElementById('captext').addEventListener('input',
    ()=>capMsg('unsaved — Save & Re-bake to apply',''));
}

async function saveCap(revert){
  const b=capItem(capId);
  const text=document.getElementById('captext').value;
  if(!revert&&!text.trim()&&b.text.trim()&&
     !confirm('Remove all captions from '+b.id+'?'))return;
  capMsg('re-aligning, re-baking the caption clip, re-rendering the proxy…','busy');
  try{
    const j=await ovPost('/api/caption/save',
      revert?{beat_id:b.id,revert:true}:{beat_id:b.id,text:text});
    let m=(revert?'reverted':'saved')+' — '+j.words+' words';
    if(j.dropped)m+=' ('+j.dropped+' fall in trimmed audio and won’t show)';
    if(j.reproxied)m+=' · proxy refreshed';
    if(j.review_reset)m+=' · beat set to re-review on the Shots desk';
    m+='. If this beat’s caption clip is on an open Resolve timeline, re-import it there.';
    await bootCap(b.id);
    boot();
    capMsg(m,'ok');
  }catch(e){capMsg(e.message,'err');}
}

/* ---------------- Story desk ---------------- */
let STY=null, styPick=null;

async function bootStory(){
  STY=await(await fetch(api('/api/story'))).json();
  renderStory();
}

function renderStory(){
  const f=document.getElementById('storyfocus');
  const rounds=(STY.feedback.rounds||[]);
  const approved=rounds.filter(r=>r.decision==='approve').slice(-1)[0];
  let html='<div class="crumb"><b>Story</b> · '+esc(SLUG)+'</div>';
  if(STY.plan){
    html+='<div class="done">Story locked — the edit plan has '+
      STY.plan.beats+' beats across '+STY.plan.chapters.length+' chapters:'+
      '<div style="font-size:14px;margin-top:8px;color:var(--muted)">'+
      STY.plan.chapters.map(esc).join(' · ')+'</div></div>';
  }
  if(!STY.stories){
    html+='<div class="setup" style="cursor:default"><b>No story pitches yet</b>'+
      (STY.plan?'This project was planned before the pitch flow existed.'
       :'Tell Claude: “pitch stories for '+esc(SLUG)+'” — the story designer '+
        'will write three directions here for you to choose from.')+'</div>';
  }else{
    const opts=STY.stories.options||[];
    html+='<div class="crumb">Round '+(STY.stories.round||1)+' — pick a direction, '+
      'or send notes for a fresh round.</div>'+
      '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(270px,1fr));gap:12px">'+
      opts.map(o=>'<div class="scard'+(styPick===o.id?' pick':'')+
        '" data-opt="'+esc(o.id)+'">'+
        '<h3>'+esc(o.title)+'</h3>'+
        (o.tone?'<div class="tone">'+esc(o.tone)+'</div>':'')+
        '<div class="lg">'+esc(o.logline||'')+'</div>'+
        (o.hook?'<div class="hk">Hook: '+esc(o.hook)+'</div>':'')+
        ((o.beats_outline&&o.beats_outline.length)
          ?'<ul>'+o.beats_outline.map(b=>'<li>'+esc(b)+'</li>').join('')+'</ul>':'')+
        '</div>').join('')+'</div>'+
      '<textarea class="note" id="storynotes" placeholder="direction for the '+
      'story designer — what to keep, drop, lean into…"></textarea>'+
      '<div class="acts">'+
      '<button id="bStoryDir">Send direction (new round)</button>'+
      '<button class="ok ex" id="bStoryOk">Approve selected story</button></div>'+
      '<div id="storymsg" style="font-size:13px;min-height:18px"></div>';
  }
  if(rounds.length){
    html+='<div class="srounds">'+rounds.map(r=>
      '<div><b style="color:var(--text)">'+
      (r.decision==='approve'?'✓ approved '+esc(r.choice||''):'↻ direction')+
      '</b>'+(r.notes?' — '+esc(r.notes):'')+'</div>').join('')+'</div>';
  }
  f.innerHTML=html;
  f.querySelectorAll('[data-opt]').forEach(el=>{
    el.onclick=()=>{styPick=el.dataset.opt;renderStory();};
  });
  const dir=document.getElementById('bStoryDir');
  if(dir)dir.onclick=()=>sendStory('direction');
  const ok=document.getElementById('bStoryOk');
  if(ok)ok.onclick=()=>sendStory('approve');
}

async function sendStory(decision){
  const msg=document.getElementById('storymsg');
  const notes=(document.getElementById('storynotes')||{}).value||'';
  if(decision==='approve'&&!styPick){
    msg.textContent='click a story card first, then approve';
    msg.style.color='var(--flag)';return;}
  if(decision==='direction'&&!notes.trim()){
    msg.textContent='write the direction you want the next round to take';
    msg.style.color='var(--flag)';return;}
  try{
    await ovPost('/api/story/feedback',
      {choice:styPick,notes:notes,decision:decision});
    await bootProjects();await bootStory();
    const m=document.getElementById('storymsg');
    if(m){m.style.color='var(--accent)';
      m.textContent=decision==='approve'
        ?'approved — tell Claude: “write the edit plan for '+SLUG+'”'
        :'sent — tell Claude: “pitch stories for '+SLUG+'” to run the next round';}
  }catch(e){msg.textContent=e.message;msg.style.color='var(--flag)';}
}

(async()=>{
  await bootProjects();
  boot();
  if(location.hash==='#overlays')tab('ov');
  else if(location.hash==='#captions')tab('cap');
  else if(location.hash==='#story')tab('story');
})();
</script></body></html>
"""
