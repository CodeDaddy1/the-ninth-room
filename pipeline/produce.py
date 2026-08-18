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


def _beat_caption_clips(slug: str, tl_map: "dict", log=print) -> "list[dict]":
    """Bake one word-pop caption clip per beat from captions.json (if present)."""
    work = work_path(slug)
    cap_path = work / "captions.json"
    if not cap_path.exists():
        log("[produce] no captions.json — skipping captions")
        return []
    caps = json.loads(cap_path.read_text())
    by_beat = {c["beat_id"]: c for c in caps.get("beats", [])}

    out = analysis_dir(slug)
    catalog = json.loads((out / "catalog.json").read_text())
    file_by_name = {f["name"]: f for f in catalog["files"]}
    w, h = timeline_mod.CANVAS[tl_map["orientation"]]

    cap_dir = work / "captions"
    cap_dir.mkdir(exist_ok=True)
    clips = []
    for beat in tl_map["beats"]:
        spec = by_beat.get(beat["id"])
        if not spec or not spec.get("text"):
            continue
        f = file_by_name[beat["file"]]
        words = json.loads((out / f["words_file"]).read_text())
        lo = beat["segments"][0]["src_s"]
        hi = beat["segments"][-1]["src_e"]
        beat_words = [wd for wd in words if lo - 0.2 <= wd["s"] <= hi + 0.2]
        timed = captions_mod.align_words(spec["text"], beat_words)
        rel = []
        for tw in timed:
            rec = retime(tw["t"], beat["segments"])
            if rec is None:
                continue
            rel.append({"disp": tw["disp"], "t": round(rec - beat["record_s"], 3)})
        if not rel:
            continue
        dur = beat["record_e"] - beat["record_s"]
        mov = cap_dir / ("%s.mov" % beat["id"])
        captions_mod.bake_caption_clip(rel, dur, mov, w, h, tl_map["orientation"],
                                       cap_dir / "tmp")
        clips.append({"id": "cap_" + beat["id"], "path": str(mov),
                      "record_s": beat["record_s"], "duration": dur})
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
    caps = _beat_caption_clips(slug, tl_map, log)
    path = timeline_mod.write_fcpxml(slug, tl_map, cards, caps)
    log("[produce] wrote %s" % path)
    return path


def build_assets(slug: str, log=print) -> "tuple":
    """Plan the layout and bake overlays without writing FCPXML.
    Returns (timeline_map, cards, caption_clips)."""
    tl_map = timeline_mod.plan_beats(slug)
    log("[produce] %d beats, %.1fs total @ %sfps %s"
        % (len(tl_map["beats"]), tl_map["duration"], tl_map["fps"], tl_map["orientation"]))
    cards = _card_clips(slug, tl_map, log)
    caps = _beat_caption_clips(slug, tl_map, log)
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

    ra.ensure_bridge()
    render_mod.project_for_slug(slug, tl_map["fps"], log=log)
    tl_name = build_api.build(slug, cards, caps, log=log)
    return render_mod.render_current(slug, tl_name, log=log)
