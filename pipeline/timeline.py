"""Phase 6 — timeline generation: edit_plan.json -> timeline.fcpxml.

This is where the edit becomes real. The story-designer picked WHAT to say
(takes, trims, b-roll moments); this module decides WHERE every frame lands:

  1. Each beat's trimmed take is split into segments by cutting dead space —
     silence gaps longer than MAX_KEEP_GAP_SEC (from the ingest silence map),
     keeping KEEP_PAD_SEC of breathing room on each side of a cut.
  2. Segments are laid onto the record timeline in order: V1 talking head
     (with its audio), V2 b-roll cutaways (video-only!), V3 design cards,
     V4 caption clips. Cross-dissolves appear only between beats that asked
     for them AND have enough source handles; otherwise they degrade to cuts.
  3. Everything is written as FCPXML 1.9 using only constructs the Phase 0
     spike proved survive Resolve's importer (docs/resolve-findings.md).
     Times are frame-exact rationals on the timeline's frame-duration grid.

Also writes analysis/timeline_map.json — the record-time layout — which QC
and the caption baker use.

What breaks if this is wrong: cuts land mid-word, b-roll audio (museum crowd
noise!) leaks over the narration if b-roll is placed as asset-clip instead of
<video>, dissolves without handles pull frozen frames, and off-grid times make
Resolve snap clips a frame off.
"""
from __future__ import annotations

import json
from fractions import Fraction
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

from .ingest import work_path, analysis_dir, IngestError

MAX_KEEP_GAP_SEC = 0.9   # in-take silence longer than this is dead space
KEEP_PAD_SEC = 0.25      # breathing room kept on each side of a dead-space cut
HEAD_PAD_SEC = 0.15      # lead-in kept before a take's first word
TAIL_PAD_SEC = 0.30      # room kept after a take's last word
DISSOLVE_SEC = 1.0
MIN_SEGMENT_SEC = 0.4    # segments shorter than this merge into their neighbor

CANVAS = {"portrait": (1080, 1920), "landscape": (1920, 1080)}


# --- rational time on the frame grid --------------------------------------

class FrameGrid:
    """Snap seconds onto the timeline's exact frame duration (e.g. 1001/24000)."""

    def __init__(self, fps: float):
        if abs(fps - 23.976) < 0.01:
            self.frame = Fraction(1001, 24000)
        elif abs(fps - 29.97) < 0.01:
            self.frame = Fraction(1001, 30000)
        elif abs(fps - 59.94) < 0.01:
            self.frame = Fraction(1001, 60000)
        else:
            self.frame = Fraction(1, int(round(fps)))
        self.fps = fps

    def frames(self, seconds: float) -> int:
        return int(round(Fraction(seconds).limit_denominator(100000) / self.frame))

    def rt(self, seconds: float) -> str:
        """Rational-seconds string snapped to the grid, e.g. '3003/24000s'.

        The denominator is ALWAYS the format's timebase: Fraction would reduce
        685685/24000 to 137137/4800, and Resolve rejects the whole file (import
        returns nil, no error) when times aren't on the declared timebase.
        """
        n = self.frames(seconds)
        return "%d/%ds" % (n * self.frame.numerator, self.frame.denominator)

    def snap(self, seconds: float) -> float:
        return float(self.frames(seconds) * self.frame)


# --- segment planning ------------------------------------------------------

def cut_dead_space(span_s: float, span_e: float, gaps: "list[dict]",
                   hard_cuts: "list[dict] | None" = None) -> "list[tuple]":
    """Split [span_s, span_e] wherever a silence gap exceeds MAX_KEEP_GAP_SEC,
    and remove every `hard_cuts` span outright.

    Silence cuts keep KEEP_PAD_SEC of breathing room on each side. Hard cuts
    (flubs, cross-talk, bad audio, marked per-beat in the edit plan as
    `cuts: [{s,e}]`) are removed exactly as given — the editor already chose
    the boundary, usually on a word edge.
    """
    removals = []
    for g in gaps:
        gs, ge = max(g["s"], span_s), min(g["e"], span_e)
        if ge - gs > MAX_KEEP_GAP_SEC:
            removals.append((gs + KEEP_PAD_SEC, ge - KEEP_PAD_SEC))
    for c in hard_cuts or []:
        cs, ce = max(c["s"], span_s), min(c["e"], span_e)
        if ce > cs:
            removals.append((cs, ce))
    removals.sort()
    merged_removals: "list[list]" = []
    for s, e in removals:
        if merged_removals and s <= merged_removals[-1][1]:
            merged_removals[-1][1] = max(merged_removals[-1][1], e)
        else:
            merged_removals.append([s, e])

    segments = []
    cur = span_s
    for s, e in merged_removals:
        if s > cur:
            segments.append((cur, s))
        cur = max(cur, e)
    if span_e > cur:
        segments.append((cur, span_e))
    # merge slivers into the previous segment's tail
    merged: "list[tuple]" = []
    for s, e in segments:
        if merged and e - s < MIN_SEGMENT_SEC:
            merged[-1] = (merged[-1][0], merged[-1][1])
            continue
        merged.append((s, e))
    return merged or [(span_s, span_e)]


def plan_beats(slug: str) -> "dict":
    """Resolve the edit plan into record-time beats + segments (seconds).

    Returns the timeline map: {"fps", "orientation", "beats": [{id, purpose,
    file, transition_in, record_s, record_e, segments: [{src_s, src_e,
    record_s}], broll: [...], }], "duration"}.
    """
    work = work_path(slug)
    out = analysis_dir(slug)
    plan = json.loads((work / "edit_plan.json").read_text())
    takes = json.loads((out / "takes.json").read_text())
    catalog = json.loads((out / "catalog.json").read_text())
    broll_cat = json.loads((out / "broll.json").read_text()) if (out / "broll.json").exists() \
        else {"clips": []}

    from . import schemas
    errors = schemas.validate_edit_plan(plan, takes, broll_cat)
    if errors:
        raise IngestError("edit_plan invalid:\n  " + "\n  ".join(errors))

    take_by_id = {t["id"]: t for t in takes["takes"]}
    file_by_name = {f["name"]: f for f in catalog["files"]}
    broll_by_id = {c["id"]: c for c in broll_cat["clips"]}

    speech_fps = [f.get("fps") for f in catalog["files"]
                  if f.get("class") == "speech" and f.get("fps")]
    fps = speech_fps[0] if speech_fps else 30.0
    grid = FrameGrid(fps)

    words_cache: "dict[str, list]" = {}

    def file_words(f: "dict") -> "list[dict]":
        if f["name"] not in words_cache:
            wf = f.get("words_file")
            words_cache[f["name"]] = (
                json.loads((out / wf).read_text()) if wf and (out / wf).exists() else [])
        return words_cache[f["name"]]

    def snap_to_words(f: "dict", s: float, e: float) -> "tuple":
        """Editors (human or agent) hand us approximate trims; cutting
        mid-word sounds broken, so pull s back to the start of the word it
        lands in (or forward to the next word) and push e to the end of the
        word it lands in. No word within reach leaves the value alone."""
        words = file_words(f)
        if not words:
            return s, e
        starts = [w["s"] for w in words]
        new_s = s
        inside = [w for w in words if w["s"] - 0.05 <= s < w["e"]]
        if inside:
            new_s = inside[0]["s"]
        else:
            nxt = [t for t in starts if t >= s]
            if nxt and nxt[0] - s <= 1.5:
                new_s = nxt[0]
        new_e = e
        inside_e = [w for w in words if w["s"] < e <= w["e"] + 0.05]
        if inside_e:
            new_e = inside_e[0]["e"]
        else:
            prev = [w["e"] for w in words if w["e"] <= e]
            if prev and e - prev[-1] <= 1.5:
                new_e = prev[-1]
        return (new_s, new_e) if new_e > new_s else (s, e)

    beats_out = []
    record = 0.0
    for b in plan["beats"]:
        take = take_by_id[b["take_id"]]
        f = file_by_name[take["file"]]
        trim = b.get("trim") or {"s": take["s"], "e": take["e"]}
        snap_s, snap_e = snap_to_words(f, trim["s"], trim["e"])
        span_s = max(0.0, snap_s - HEAD_PAD_SEC)
        span_e = min(f["duration"], snap_e + TAIL_PAD_SEC)
        segments = cut_dead_space(span_s, span_e, f.get("silence", []),
                                  hard_cuts=b.get("cuts"))

        transition = b.get("transition_in", "cut")
        if transition == "dissolve" and beats_out:
            # A centered dissolve needs DISSOLVE_SEC/2 of extra media on both
            # sides of the cut. Degrade to a hard cut when handles are short.
            prev = beats_out[-1]
            prev_file = file_by_name[prev["file"]]
            prev_tail = prev_file["duration"] - prev["segments"][-1]["src_e"]
            head = segments[0][0]
            if prev_tail < DISSOLVE_SEC / 2 or head < DISSOLVE_SEC / 2:
                transition = "cut"

        beat_rec_start = record
        seg_out = []
        for (s, e) in segments:
            s, e = grid.snap(s), grid.snap(e)
            if e <= s:
                continue
            seg_out.append({"src_s": s, "src_e": e, "record_s": grid.snap(record)})
            record = grid.snap(record + (e - s))

        broll_out = []
        for br in b.get("broll", []):
            clip = broll_by_id[br["clip_id"]]
            at = grid.snap(beat_rec_start + br["at"])
            dur = grid.snap(min(br["duration"], clip["duration"], record - at))
            if dur <= 0 or at >= record:
                continue
            # sample the clip from 10% in — DJI clips often start with a ramp
            src_off = grid.snap(min(clip["duration"] * 0.1,
                                    max(0.0, clip["duration"] - dur)))
            broll_out.append({"clip_id": br["clip_id"], "file": clip["file"],
                              "record_s": at, "duration": dur, "src_s": src_off})

        beats_out.append({
            "id": b["id"], "purpose": b["purpose"], "take_id": b["take_id"],
            "file": take["file"], "transition_in": transition,
            "record_s": grid.snap(beat_rec_start), "record_e": record,
            "segments": seg_out, "broll": broll_out,
        })

    tl_map = {
        "slug": slug,
        "fps": fps,
        "orientation": plan.get("orientation", "portrait"),
        "format": plan.get("format", "youtube_short"),
        "duration": record,
        "beats": beats_out,
    }
    (out / "timeline_map.json").write_text(json.dumps(tl_map, indent=2))
    return tl_map


# --- FCPXML writing --------------------------------------------------------

def _asset_id(name: str, registry: "dict") -> str:
    if name not in registry:
        registry[name] = "a%d" % (len(registry) + 1)
    return registry[name]


def write_fcpxml(slug: str, tl_map: "dict", cards: "list[dict]",
                 caption_clips: "list[dict]") -> Path:
    """Emit timeline.fcpxml from the planned layout.

    cards: [{"id", "path", "record_s", "duration"}] (already-baked movs)
    caption_clips: same shape, baked per beat.
    Only spike-proven constructs: asset-clip spine with start/duration/offset,
    <transition> + Cross Dissolve filter, connected <video> children on lanes.
    """
    work = work_path(slug)
    grid = FrameGrid(tl_map["fps"])
    w, h = CANVAS[tl_map["orientation"]]
    file_by_name = {f["name"]: f
                    for f in json.loads((analysis_dir(slug) / "catalog.json").read_text())["files"]}

    registry: "dict[str, str]" = {}
    asset_lines = []

    def register(name: str, path: str, duration: float, has_audio: bool) -> str:
        known = name in registry
        aid = _asset_id(name, registry)
        if not known:
            asset_lines.append(
                '<asset id="%s" name=%s start="0/1s" duration="%s" hasVideo="1"%s format="r1">'
                '<media-rep kind="original-media" src=%s /></asset>'
                % (aid, quoteattr(name), grid.rt(duration),
                   ' hasAudio="1"' if has_audio else "",
                   quoteattr("file://" + str(Path(path).resolve()))))
        return aid

    # overlays grouped by which beat's record window they start in
    def overlays_in(rec_s: float, rec_e: float, items: "list[dict]") -> "list[dict]":
        return [x for x in items if rec_s <= x["record_s"] < rec_e]

    spine_parts = []
    for i, beat in enumerate(tl_map["beats"]):
        f = file_by_name[beat["file"]]
        aid = register(f["name"], f["path"], f["duration"], f.get("has_audio", False))

        # Every overlay attaches to the segment whose record window CONTAINS
        # its start — attaching elsewhere makes the child offset negative,
        # which silently kills the whole import (found on the first
        # multi-segment beat). A connected clip may extend past its parent's
        # end; FCPXML allows that.
        seg_windows = []
        for seg in beat["segments"]:
            seg_windows.append((seg, seg["record_s"],
                                seg["record_s"] + (seg["src_e"] - seg["src_s"])))

        def containing_segment(rec_t: float):
            for seg, lo, hi in seg_windows:
                if lo <= rec_t < hi:
                    return seg
            return seg_windows[0][0] if rec_t < seg_windows[0][1] else seg_windows[-1][0]

        children_by_seg: "dict[int, list]" = {id(seg): [] for seg in beat["segments"]}
        beat_overlays = (
            [(1, "broll", item) for item in beat["broll"]] +
            [(2, "card", item) for item in overlays_in(beat["record_s"], beat["record_e"], cards)] +
            [(3, "cap", item) for item in overlays_in(beat["record_s"], beat["record_e"], caption_clips)]
        )
        for lane, kind, item in beat_overlays:
            if kind == "broll":
                bf = file_by_name[item["file"]]
                cid = register(bf["name"], bf["path"], bf["duration"], bf.get("has_audio", False))
                src_start = item.get("src_s", 0.0)
            else:
                cid = register(Path(item["path"]).name, item["path"],
                               item["duration"], False)
                src_start = 0.0
            seg = containing_segment(item["record_s"])
            rec_t = max(item["record_s"], seg["record_s"])
            # child offset is in the PARENT'S source-time coordinates
            child_off = seg["src_s"] + (rec_t - seg["record_s"])
            children_by_seg[id(seg)].append(
                '<video lane="%d" ref="%s" name=%s offset="%s" start="%s" duration="%s"/>'
                % (lane, cid, quoteattr(kind + "_" + str(item.get("clip_id") or item.get("id"))),
                   grid.rt(child_off), grid.rt(src_start), grid.rt(item["duration"])))

        for j, seg in enumerate(beat["segments"]):
            dur = seg["src_e"] - seg["src_s"]
            children = children_by_seg[id(seg)]
            if j == 0 and beat["transition_in"] == "dissolve" and spine_parts:
                spine_parts.append(
                    '<transition name="Cross Dissolve" offset="%s" duration="%s">'
                    '<filter-video ref="fxD" name="Cross Dissolve"/></transition>'
                    % (grid.rt(max(0.0, seg["record_s"] - DISSOLVE_SEC / 2)),
                       grid.rt(DISSOLVE_SEC)))
            body = "".join(children)
            spine_parts.append(
                '<asset-clip ref="%s" name=%s offset="%s" start="%s" duration="%s" format="r1">%s</asset-clip>'
                % (aid, quoteattr("%s_%s" % (beat["id"], j)), grid.rt(seg["record_s"]),
                   grid.rt(seg["src_s"]), grid.rt(dur), body))

    frame = grid.frame
    fcpxml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE fcpxml>\n'
        '<fcpxml version="1.9"><resources>'
        '<format id="r1" name="FFVideoFormatRateUndefined" frameDuration="%d/%ds" width="%d" height="%d"/>'
        '<effect id="fxD" name="Cross Dissolve" uid="FxPlug:4731E73A-8DAC-4113-9A30-AE85B1761265"/>'
        "%s</resources><library><event name=%s><project name=%s>"
        '<sequence format="r1" duration="%s" tcStart="0/1s"><spine>%s</spine></sequence>'
        "</project></event></library></fcpxml>"
        % (frame.numerator, frame.denominator, w, h,
           "".join(asset_lines), quoteattr(slug), quoteattr(slug),
           grid.rt(tl_map["duration"]), "".join(spine_parts))
    )
    path = work / "timeline.fcpxml"
    path.write_text(fcpxml)
    return path
