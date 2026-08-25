"""The end-to-end assembly: plan -> captions -> cards -> FCPXML (-> Resolve).

`build_timeline(slug)` is the Phase 6 entry point: it runs the segment math,
bakes caption clips and design cards, and writes timeline.fcpxml. Phase 7's
`produce(slug)` adds the Resolve import + render + QC on top.

Source-to-record retiming: dead-space cuts remove chunks of the source, so a
whisper word at source second 41.2 may land at record second 12.7. The
segment map from plan_beats() is the single source of that truth —
`retime()` here is the only code that walks it.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from . import captions as captions_mod
from . import graphics as graphics_mod
from . import timeline as timeline_mod
from .ingest import work_path, analysis_dir, IngestError


def retime(t: float, segments: "list[dict]") -> "float | None":
    """Map a source-time to record-time through a beat's segments.

    A time inside a removed gap snaps to the next segment's start; a time
    after the last segment returns None (the word was cut away entirely).
    """
    for seg in segments:
        if t < seg["src_s"]:
            return seg["record_s"]
        if seg["src_s"] <= t <= seg["src_e"]:
            return seg["record_s"] + (t - seg["src_s"])
    return None


def _caption_key(rel: "list", dur: float, w: int, h: int,
                 orientation: str) -> str:
    """The caption bake-cache key. One function so the Edit Room's caption
    desk and produce can never disagree about what 'unchanged' means."""
    return hashlib.sha1(json.dumps(
        {"words": rel, "dur": round(dur, 3), "w": w, "h": h,
         "orientation": orientation,
         "v": captions_mod.CAPTIONS_V}, sort_keys=True).encode()).hexdigest()[:12]


def caption_rel_words(slug: str, beat: "dict", text: str,
                      file_by_name: "dict", words_cache: "dict"):
    """Timed display words for one beat: TEXT from the (possibly edited)
    caption script, TIMING from whisper, retimed into the beat's kept
    segments. Returns (rel, dropped) — dropped counts script words whose
    aligned time falls in trimmed audio and therefore never displays."""
    out = analysis_dir(slug)
    f = file_by_name[beat["file"]]
    if f["words_file"] not in words_cache:
        words_cache[f["words_file"]] = json.loads(
            (out / f["words_file"]).read_text())
    words = words_cache[f["words_file"]]
    lo = beat["segments"][0]["src_s"]
    hi = beat["segments"][-1]["src_e"]
    beat_words = [wd for wd in words if lo - 0.2 <= wd["s"] <= hi + 0.2]
    timed = captions_mod.align_words(text, beat_words)
    rel, dropped = [], 0
    for tw in timed:
        rec = retime(tw["t"], beat["segments"])
        if rec is None:
            dropped += 1
            continue
        rel.append({"disp": tw["disp"], "t": round(rec - beat["record_s"], 3)})
    return rel, dropped


def rebake_beat_caption(slug: str, beat_id: str, log=print) -> "dict":
    """Re-derive and re-bake ONE beat's caption clip from captions.json.

    The Edit Room's caption desk calls this after a text edit: alignment,
    cache key, and bake are the same code produce runs, so the desk's
    result is exactly what the next produce would ship. The mov keeps its
    name (captions/<beat>.mov) — the FCPXML timeline references it by path.
    """
    work = work_path(slug)
    out = analysis_dir(slug)
    tl_map = json.loads((out / "timeline_map.json").read_text())
    caps = json.loads((work / "captions.json").read_text())
    effective = captions_mod.effective_captions(
        caps, tl_map.get("orientation", "landscape"),
        captions_mod.vo_beats_of(tl_map))
    entry = next((c for c in caps.get("beats", [])
                  if c["beat_id"] == beat_id
                  and c["beat_id"] in effective), None)
    beat = next((b for b in tl_map["beats"] if b["id"] == beat_id), None)
    if beat is None:
        raise IngestError("no beat '%s'" % beat_id)
    cap_dir = work / "captions"
    hash_path = cap_dir / ".bake_hashes.json"
    hashes = json.loads(hash_path.read_text()) if hash_path.exists() else {}
    if entry is None or not entry.get("text"):
        # caption blanked: the proxy and produce both skip it by text, so
        # just forget the cache entry; the old mov stays (Resolve may
        # reference it) and a restored text re-bakes over it
        if hashes.pop(beat_id, None) is not None:
            hash_path.write_text(json.dumps(hashes, indent=1))
        return {"words": 0, "dropped": 0, "baked": False}
    catalog = json.loads((out / "catalog.json").read_text())
    file_by_name = {f["name"]: f for f in catalog["files"]}
    rel, dropped = caption_rel_words(slug, beat, entry["text"],
                                     file_by_name, {})
    if not rel:
        return {"words": 0, "dropped": dropped, "baked": False}
    w, h = timeline_mod.CANVAS[tl_map["orientation"]]
    dur = beat["record_e"] - beat["record_s"]
    key = _caption_key(rel, dur, w, h, tl_map["orientation"])
    mov = cap_dir / ("%s.mov" % beat_id)
    baked = False
    if hashes.get(beat_id) != key or not mov.exists():
        # Per-beat scratch: frames are named cap_NNN.png with no beat prefix,
        # so two concurrent bakes sharing one tmp dir overwrite each other's
        # frames mid-encode (Edit Room desk + produce, or a parallel rebake).
        captions_mod.bake_caption_clip(rel, dur, mov, w, h,
                                       tl_map["orientation"],
                                       cap_dir / "tmp" / beat_id)
        hashes[beat_id] = key
        hash_path.write_text(json.dumps(hashes, indent=1))
        baked = True
        log("[captions] %s re-baked: %d words" % (beat_id, len(rel)))
    return {"words": len(rel), "dropped": dropped, "baked": baked}


def _beat_caption_clips(slug: str, tl_map: "dict",
                        only_beats: "list | None" = None, log=print) -> "list[dict]":
    """Bake one word-pop caption clip per beat from captions.json (if present).

    only_beats: bake just these beat ids (the shot-fixer's surgical path).
    """
    work = work_path(slug)
    cap_path = work / "captions.json"
    if not cap_path.exists():
        log("[produce] no captions.json — skipping captions")
        return []
    caps = json.loads(cap_path.read_text())
    effective = captions_mod.effective_captions(
        caps, tl_map.get("orientation", "landscape"),
        captions_mod.vo_beats_of(tl_map))
    by_beat = {c["beat_id"]: c for c in caps.get("beats", [])
               if c["beat_id"] in effective}

    out = analysis_dir(slug)
    catalog = json.loads((out / "catalog.json").read_text())
    file_by_name = {f["name"]: f for f in catalog["files"]}
    w, h = timeline_mod.CANVAS[tl_map["orientation"]]

    cap_dir = work / "captions"
    cap_dir.mkdir(exist_ok=True)
    # Bake cache (same idea as pipeline/proxy.py): a beat whose timed words
    # have not changed keeps its baked mov. Four produce runs in one day
    # re-baked every caption identically (~15 min each, 2026-08-19).
    hash_path = cap_dir / ".bake_hashes.json"
    hashes = json.loads(hash_path.read_text()) if hash_path.exists() else {}
    clips = []
    words_cache: "dict" = {}
    for beat in tl_map["beats"]:
        if only_beats and beat["id"] not in only_beats:
            continue
        spec = by_beat.get(beat["id"])
        if not spec or not spec.get("text"):
            continue
        rel, _dropped = caption_rel_words(slug, beat, spec["text"],
                                          file_by_name, words_cache)
        if not rel:
            continue
        dur = beat["record_e"] - beat["record_s"]
        mov = cap_dir / ("%s.mov" % beat["id"])
        key = _caption_key(rel, dur, w, h, tl_map["orientation"])
        if hashes.get(beat["id"]) == key and mov.exists():
            clips.append({"id": "cap_" + beat["id"], "path": str(mov),
                          "record_s": beat["record_s"], "duration": dur})
            log("[produce] captions %s (cached)" % beat["id"])
            continue
        captions_mod.bake_caption_clip(rel, dur, mov, w, h, tl_map["orientation"],
                                       cap_dir / "tmp")
        clips.append({"id": "cap_" + beat["id"], "path": str(mov),
                      "record_s": beat["record_s"], "duration": dur})
        hashes[beat["id"]] = key
        hash_path.write_text(json.dumps(hashes, indent=1))
        log("[produce] captions %s: %d words, %.1fs" % (beat["id"], len(rel), dur))
    return clips


def _card_clips(slug: str, tl_map: "dict", log=print) -> "list[dict]":
    """Bake design cards from graphics_plan.json (if present) and place them."""
    work = work_path(slug)
    plan_path = work / "graphics_plan.json"
    if not plan_path.exists():
        log("[produce] no graphics_plan.json — skipping cards")
        return []
    graphics_mod.build_cards(slug, orientation=tl_map["orientation"], log=log)
    plan = json.loads(plan_path.read_text())
    beat_by_id = {b["id"]: b for b in tl_map["beats"]}
    clips = []
    for card in plan["cards"]:
        beat = beat_by_id.get(card["beat_id"])
        if beat is None:
            raise IngestError("graphics_plan card %s references unknown beat %s"
                              % (card["id"], card["beat_id"]))
        rec = beat["record_s"] + card["at"]
        rec = min(rec, beat["record_e"] - 0.5)
        dur = min(card["duration"], tl_map["duration"] - rec)
        clips.append({"id": card["id"],
                      "path": str(work / "graphics" / (card["id"] + ".mov")),
                      "record_s": rec, "duration": dur})
    return clips


def build_timeline(slug: str, log=print) -> Path:
    """Phase 6: everything up to (but not including) Resolve."""
    tl_map = timeline_mod.plan_beats(slug)
    log("[produce] %d beats, %.1fs total @ %sfps %s"
        % (len(tl_map["beats"]), tl_map["duration"], tl_map["fps"], tl_map["orientation"]))
    cards = _card_clips(slug, tl_map, log)
    caps = _beat_caption_clips(slug, tl_map, log=log)
    path = timeline_mod.write_fcpxml(slug, tl_map, cards, caps)
    log("[produce] wrote %s" % path)
    return path


def rebake(slug: str, beat_ids: "list | None" = None,
           card_ids: "list | None" = None, log=print) -> "dict":
    """The shot-fixer's surgical rebuild: regenerate the timeline map from
    the (edited) plan, then re-bake ONLY the named caption beats and card
    ids. Nothing else is touched — no Resolve, no renders, no full bakes.
    """
    tl_map = timeline_mod.plan_beats(slug)
    log("[rebake] %d beats, %.1fs total" % (len(tl_map["beats"]), tl_map["duration"]))
    if card_ids:
        graphics_mod.build_cards(slug, orientation=tl_map["orientation"],
                                 only_ids=card_ids, log=log)
    if beat_ids:
        _beat_caption_clips(slug, tl_map, only_beats=beat_ids, log=log)
    return tl_map


def build_assets(slug: str, log=print) -> "tuple":
    """Plan the layout and bake overlays without writing FCPXML.
    Returns (timeline_map, cards, caption_clips)."""
    tl_map = timeline_mod.plan_beats(slug)
    log("[produce] %d beats, %.1fs total @ %sfps %s"
        % (len(tl_map["beats"]), tl_map["duration"], tl_map["fps"], tl_map["orientation"]))
    cards = _card_clips(slug, tl_map, log)
    caps = _beat_caption_clips(slug, tl_map, log=log)
    return tl_map, cards, caps


def produce(slug: str, log=print) -> Path:
    """Phase 7: full auto — timeline into Resolve, render, verify.

    Timelines are built through the scripting API rather than by importing
    the FCPXML: Resolve's importer leaves 4K HEVC (DJI) clips offline. The
    FCPXML is still written for reference/debugging and for NLEs that read it.
    """
    from . import build_api
    from . import render as render_mod
    from . import resolve_api as ra

    tl_map, cards, caps = build_assets(slug, log)
    fcpxml = timeline_mod.write_fcpxml(slug, tl_map, cards, caps)
    log("[produce] wrote %s (reference)" % fcpxml)

    # Report (never block on) cuts that interrupt a measured voice — the
    # check that would have caught the clipped "Monopoly." (2026-08-19).
    from . import audit as audit_mod
    edge_flags = audit_mod.audit_speech_edges(slug, log=log)
    if edge_flags:
        log("[produce] WARNING: %d cut(s) land while a voice is audible — "
            "review before publishing" % len(edge_flags))

    ra.ensure_bridge()
    render_mod.project_for_slug(slug, tl_map["fps"], log=log)
    tl_name = build_api.build(slug, cards, caps, log=log)
    # Music is deliberately NOT mixed here — Caleb scores in post (2026-08-18).
    # `pipeline/music.py` still works if that changes: it lays a per-chapter
    # bed and side-chain ducks it under the narration. Call it explicitly.
    output = render_mod.render_current(slug, tl_name, log=log)

    # The approved proxies ARE the picture; the master must show what they
    # show. Reports (never blocks) — see pipeline/qc_frames.py.
    from . import qc_frames
    frame_flags = qc_frames.compare(slug, output, log=log)
    if frame_flags:
        log("[produce] WARNING: %d beat(s) differ from their approved "
            "proxies — inspect before publishing" % len(frame_flags))
    return output
