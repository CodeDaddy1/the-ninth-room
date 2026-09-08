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
import os
from fractions import Fraction
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

from .ingest import work_path, analysis_dir, IngestError, words_by_file


def _brief_delivery(slug: str) -> str:
    """This project's delivery, or `long` when it predates the field."""
    p = work_path(slug) / "story_brief.json"
    try:
        return str(json.loads(p.read_text()).get("delivery") or "long")
    except (OSError, ValueError):
        return "long"

MAX_KEEP_GAP_SEC = 0.65  # in-take silence longer than this is dead space
                         # (0.9 read as documentary pacing; YouTube cuts tighter)
KEEP_PAD_SEC = 0.2       # breathing room kept on each side of a dead-space cut
HEAD_PAD_SEC = 0.12      # lead-in kept before a take's first word
TAIL_PAD_SEC = 0.22      # room kept after a take's last word
DISSOLVE_SEC = 1.0
MIN_SEGMENT_SEC = 0.4    # segments shorter than this merge into their neighbor

# 4K is the channel format (Caleb, 2026-08-20) — the Osmo Pocket 3 shoots
# native 3840x2160 and normalization preserves it, so UHD is real detail.
CANVAS = {"portrait": (2160, 3840), "landscape": (3840, 2160)}


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

_TERMINAL = (".", "!", "?", "…", '."', '!"', '?"')


def _sentence_ends_before(words: "list[dict]", t: float) -> bool:
    """True when the last word spoken before time t closes a sentence."""
    prev = None
    for w in words:
        if w["e"] <= t + 0.05:
            prev = w
        else:
            break
    return bool(prev) and prev["w"].rstrip().endswith(_TERMINAL)


def cut_dead_space(span_s: float, span_e: float, gaps: "list[dict]",
                   hard_cuts: "list[dict] | None" = None,
                   words: "list[dict] | None" = None,
                   audio_path: "str | None" = None,
                   trough_cache: "dict | None" = None) -> "list[tuple]":
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
        if ge - gs <= MAX_KEEP_GAP_SEC:
            continue
        # Never auto-cut a pause mid-sentence (Caleb's rule, 2026-08-19): a
        # splice is only allowed where the preceding word ends the sentence.
        # A long mid-sentence pause stays; if it is genuinely bad it is the
        # editor's call via an explicit per-beat cut, not the machine's.
        if words is not None and not _sentence_ends_before(words, gs):
            continue
        rs, re_ = gs + KEEP_PAD_SEC, ge - KEEP_PAD_SEC
        # Snap this removal's edges to measured troughs (troughs.py): the
        # audit kept finding voice hard against these cuts, because
        # silencedetect's threshold is not where a voice actually stops.
        # Segments may only GROW into the gap, so no word that survived
        # before is lost now. Hard cuts below are deliberately untouched --
        # growing across a flub boundary would re-include the flub.
        if audio_path is not None and trough_cache is not None:
            from . import troughs
            rs, re_ = troughs.snap_removal(audio_path, rs, re_, trough_cache)
        removals.append((rs, re_))
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
    errors = schemas.validate_edit_plan(plan, takes, broll_cat,
                                        words=words_by_file(slug))
    if errors:
        raise IngestError("edit_plan invalid:\n  " + "\n  ".join(errors))

    take_by_id = {t["id"]: t for t in takes["takes"]}
    file_by_name = {f["name"]: f for f in catalog["files"]}
    broll_by_id = {c["id"]: c for c in broll_cat["clips"]}

    # The Footage desk's trims (2026-08-28). EVERY source-time bound below
    # is measured against the clip's usable window rather than against the
    # whole file: a trim exists because the walk-up or the tail is
    # unusable, so a clamp that still read `duration` would put a tail pad,
    # a dissolve handle or a cover's in-point squarely in the footage Caleb
    # cut away — the one place the cut must never reach.
    #
    # Read from the SIDECAR, not from broll.json's `trim`, so a trim set
    # after the last catalog run takes effect on the next assemble. The
    # catalogued copy is what the schema and the agents read; this is what
    # the frames obey.
    from .takes import file_trims, trim_window
    trims = file_trims(slug)

    speech_fps = [f.get("fps") for f in catalog["files"]
                  if f.get("class") == "speech" and f.get("fps")]
    fps = speech_fps[0] if speech_fps else 30.0
    grid = FrameGrid(fps)

    words_cache: "dict[str, list]" = {}
    # trough measurements are cached across runs -- footage is immutable, so
    # every map regeneration after the first costs no ffmpeg
    from . import troughs
    trough_cache = troughs.load_cache(out)
    trough_cache_size = len(trough_cache)

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
        # A beat carries a TAKE (speech) or a SPINE (a clip as the picture).
        # Word snapping, head/tail padding and dead-space cutting are all
        # SPEECH operations — there are no words to snap to on a picture
        # beat, and trimming its silence would delete the shot. So a spine
        # is taken exactly as the plan states it (2026-08-28).
        spine = b.get("spine") if not b.get("take_id") else None
        if spine is not None:
            take = None
            clip = broll_by_id[spine["clip_id"]]
            f = file_by_name[clip["file"]]
            t_in, t_out = trim_window(trims, f["name"], f["duration"])
            src_s = max(t_in, float(spine.get("src_s", 0.0)))
            src_e = min(t_out, float(spine["src_e"]))
            segments = [(src_s, src_e)] if src_e > src_s else []
            if not segments:
                why = ("beat %s: spine window %.2f-%.2f is empty against %s"
                       % (b["id"], src_s, src_e, clip["file"]))
                if f["name"] in trims:
                    why += (" — its trim keeps only %.2f-%.2fs; widen the trim "
                            "on the Footage desk or move the beat's window "
                            "inside it" % (t_in, t_out))
                raise IngestError(why)
        else:
            take = take_by_id[b["take_id"]]
            f = file_by_name[take["file"]]
            t_in, t_out = trim_window(trims, f["name"], f["duration"])
            trim = b.get("trim") or {"s": take["s"], "e": take["e"]}
            snap_s, snap_e = snap_to_words(f, trim["s"], trim["e"])
            # Both pads clamp to the TRIM, not to the file: a head pad
            # reaching before `in` plays the fumble the trim removed, and a
            # tail pad past `out` plays the one at the other end.
            span_s = max(t_in, snap_s - HEAD_PAD_SEC)
            span_e = min(t_out, snap_e + TAIL_PAD_SEC)
            if span_e <= span_s and f["name"] in trims:
                # Only a trim can empty this window — `validate_edit_plan`
                # already refuses a beat whose trim is not s < e. Say so
                # rather than emitting a beat with no segments, which reads
                # downstream as a beat that was simply never built.
                raise IngestError(
                    "beat %s: take %s runs %.2f-%.2fs but %s is trimmed to "
                    "%.2f-%.2fs — nothing of the beat is left to play; widen "
                    "the trim on the Footage desk or pick another take"
                    % (b["id"], b["take_id"], trim["s"], trim["e"],
                       f["name"], t_in, t_out))
            # PEAK PROTECTION, third of three sites (2026-09-08). On a
            # peak the pause IS the moment -- the beat exists to deliver a
            # reaction, and automatic silence removal deletes exactly the
            # thing being protected. Six of the seven film studies found
            # this independently: Johnny Harris as engineered silence,
            # Beau Miles as darkness plus a 6x slower cut rate, Kara &
            # Nate as the film's only true silence, laid on the moment the
            # premise broke.
            #
            # The exemption is the GAPS, not the call. The beat's own
            # `cuts` are the editor's deliberate removals and still apply
            # -- dropping the call outright would silently discard them,
            # which is a different bug wearing this one's clothes.
            segments = cut_dead_space(span_s, span_e,
                                      [] if b.get("peak") is True
                                      else f.get("silence", []),
                                      hard_cuts=b.get("cuts"),
                                      words=file_words(f),
                                      audio_path=f.get("path"),
                                      trough_cache=trough_cache)

        transition = b.get("transition_in", "cut")
        if transition == "dissolve" and beats_out:
            # A centered dissolve needs DISSOLVE_SEC/2 of extra media on both
            # sides of the cut. Degrade to a hard cut when handles are short.
            prev = beats_out[-1]
            prev_file = file_by_name[prev["file"]]
            # A handle is media the dissolve may reach INTO, so it is
            # measured against the usable window at both ends. A trim-out
            # shortens the outgoing tail and a trim-in shortens the
            # incoming head; measured against `duration` the dissolve would
            # be granted a handle made of the frames the trim excluded, and
            # a second of them would be mixed into the cut.
            _p_in, p_out = trim_window(trims, prev_file["name"],
                                       prev_file["duration"])
            prev_tail = p_out - prev["segments"][-1]["src_e"]
            head = segments[0][0] - t_in
            if prev_tail < DISSOLVE_SEC / 2 or head < DISSOLVE_SEC / 2:
                transition = "cut"

        # Zoom punches (hype layer): `punches: [{"at": sec-rel-to-beat,
        # "zoom": 1.12}]` split the containing segment at that point and mark
        # the following piece with a zoom. On screen: the Hangtime jump-cut —
        # same shot, suddenly 12% closer. Resolve applies the scale as a
        # static transform per clip (SetProperty), which the API does support.
        punch_srcs = []
        for p in b.get("punches", []):
            elapsed, target = 0.0, None
            for (s, e) in segments:
                if elapsed + (e - s) > p["at"]:
                    target = s + (p["at"] - elapsed)
                    break
                elapsed += e - s
            if target is not None:
                punch_srcs.append((grid.snap(target), float(p.get("zoom", 1.12))))
        if punch_srcs:
            split: "list[tuple]" = []
            for (s, e) in segments:
                pieces = [(s, e, None)]
                for pt, z in punch_srcs:
                    nxt = []
                    for (ps, pe, pz) in pieces:
                        if ps < pt < pe:
                            nxt.append((ps, pt, pz))
                            nxt.append((pt, pe, z))
                        else:
                            nxt.append((ps, pe, pz))
                    pieces = nxt
                split.extend(pieces)
            segments = [(s, e) for (s, e, _z) in split]
            zoom_of = {(s, e): z for (s, e, z) in split}
        else:
            zoom_of = {}

        beat_rec_start = record
        seg_out = []
        for (s, e) in segments:
            z = zoom_of.get((s, e))  # look up BEFORE snapping rebinds the key
            s, e = grid.snap(s), grid.snap(e)
            if e <= s:
                continue
            seg = {"src_s": s, "src_e": e, "record_s": grid.snap(record)}
            if z:
                seg["zoom"] = z
            seg_out.append(seg)
            record = grid.snap(record + (e - s))

        broll_out = []
        for br in b.get("broll", []):
            clip = broll_by_id[br["clip_id"]]
            c_in, c_out = trim_window(trims, clip["file"], clip["duration"])
            if c_out == float("inf"):
                # `trim_window` answers "no bound" for a clip nothing has
                # probed. The catalog's own number is the only bound there
                # is, and it is what this line used before trims existed —
                # an unbounded in-point would reach `grid.snap(inf)`.
                c_out = float(clip["duration"] or 0.0)
            usable = max(0.0, c_out - c_in)
            at = grid.snap(beat_rec_start + br["at"])
            dur = grid.snap(min(br["duration"], usable, record - at))
            if dur <= 0 or at >= record:
                continue
            # honor a desk-set in-point (the P3 trim strip writes src_s);
            # otherwise sample from 10% in — DJI clips often start with a
            # ramp. Under a trim that 10% is 10% INTO THE USABLE WINDOW:
            # measured from the head of the file it would land in the
            # walk-up the trim was drawn to exclude, which is the one place
            # an auto-chosen cover must not start. The last legal in-point
            # is likewise `out - dur`, not `duration - dur`.
            last_start = max(c_in, c_out - dur)
            if br.get("src_s") is not None:
                src_off = grid.snap(min(max(c_in, float(br["src_s"])),
                                        last_start))
            else:
                src_off = grid.snap(min(c_in + usable * 0.1, last_start))
            broll_out.append({"clip_id": br["clip_id"], "file": clip["file"],
                              "record_s": at, "duration": dur, "src_s": src_off})

        beats_out.append({
            "id": b["id"], "purpose": b["purpose"],
            "take_id": b.get("take_id"),
            # resolved HERE, where the take is already in hand, so readers
            # of the map never touch a filename (2026-08-28). take_kind(None)
            # is `picture`, which is exactly what a spine beat is.
            "kind": schemas.take_kind(take),
            # Natural sound is opted INTO. A cover is picture-only because
            # b-roll audio leaking over narration is a known hazard; the
            # same caution applies when the clip is the spine.
            "natural_sound": bool((spine or {}).get("audio", False)),
            "file": f["name"], "transition_in": transition,
            "record_s": grid.snap(beat_rec_start), "record_e": record,
            "segments": seg_out, "broll": broll_out,
        })

    # The plan states the shape; the BRIEF is the fallback, not a constant.
    # These used to default to portrait/youtube_short from the shorts-first
    # era, so a plan that omitted them silently built a 16:9 episode on a
    # vertical canvas (2026-08-25).
    from . import schemas
    _shape = schemas.delivery_shape(_brief_delivery(slug))
    tl_map = {
        "slug": slug,
        "fps": fps,
        "orientation": plan.get("orientation", _shape["orientation"]),
        "format": plan.get("format", _shape["format"]),
        "duration": record,
        "beats": beats_out,
    }
    if len(trough_cache) != trough_cache_size:
        troughs.save_cache(out, trough_cache)
    # atomic: a conform or proxy build reading mid-write must never see a
    # torn file (P3 gate finding 8)
    _tmp = out / "timeline_map.json.tmp"
    _tmp.write_text(json.dumps(tl_map, indent=2))
    os.replace(_tmp, out / "timeline_map.json")
    return tl_map


# --- FCPXML writing --------------------------------------------------------

def _asset_id(name: str, registry: "dict") -> str:
    if name not in registry:
        registry[name] = "a%d" % (len(registry) + 1)
    return registry[name]


def write_fcpxml(slug: str, tl_map: "dict", cards: "list[dict]",
                 caption_clips: "list[dict]", log=print) -> Path:
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
    # Only the split edits below read this: every other window in the XML
    # was already resolved against the trim by `plan_beats`. A J/L-cut is
    # the exception because its source range is derived HERE, from the
    # neighbour beat's segments, and never passed through that clamp.
    from .takes import file_trims, trim_window
    trims = file_trims(slug)

    registry: "dict[str, str]" = {}
    asset_lines = []

    def register(name: str, path: str, duration: float, has_audio: bool) -> str:
        known = name in registry
        aid = _asset_id(name, registry)
        if not known:
            # `duration` here is DELIBERATELY the whole media on disk, never
            # the Footage desk's trim. An <asset> describes the file, and
            # every clip's `start=` is an offset into that file's own clock;
            # declaring the trimmed length would put each in-point past the
            # asset's declared end. Resolve rejects such a file whole —
            # import returns nil with no error (docs/resolve-findings.md),
            # which is the worst failure shape there is. A trim narrows what
            # the cut may USE, and that is enforced in `plan_beats` where
            # the windows are chosen, not here where the media is declared.
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

    # --- split edits: J-cuts and L-cuts ----------------------------------
    # A J-cut's audio is heard BEFORE its own picture, so it cannot hang off
    # its own clip -- it hangs off the PREVIOUS beat's. An L-cut's audio
    # outlives its picture and hangs off the NEXT one. Both are the connected
    # <audio lane="-1"> child verified against Resolve 21.0.4.5 on 2026-08-23
    # (docs/resolve-findings.md): a 1s child landed on A2 one second ahead of
    # its video while the spine stayed put.
    #
    # Keyed by the HOST segment's id so the main loop below picks each child
    # up when it reaches the beat that owns that segment.
    split_children: "dict[int, list]" = {}
    # A J-cut also has to STOP the outgoing voice, or both takes play at once
    # and the viewer hears two people. audioDuration on the host clip does it
    # (verified 21.0.4.5, 2026-08-23). Maps host segment id -> seconds of
    # audio it keeps.
    audio_trim: "dict[int, float]" = {}

    def _window(seg):
        return seg["record_s"], seg["record_s"] + (seg["src_e"] - seg["src_s"])

    def _host_for(beats_slice, rec_t):
        for hb in beats_slice:
            for seg in hb["segments"]:
                lo, hi = _window(seg)
                if lo <= rec_t < hi:
                    return seg
        return None

    def _skip(beat, kind, why):
        """A dropped split edit is a decision the story-designer made and
        nobody would otherwise see -- it just would not be in the cut. Say it
        out loud so the omission is reviewable."""
        log("[timeline] %s on %s skipped: %s" % (kind, beat["id"], why))

    def _split(beat, host, rec_start, src_start, dur, kind):
        """One connected <audio> child, or nothing if it cannot be placed
        safely. A NEGATIVE child offset silently kills the whole import, and
        a source range outside the file pulls silence or a frozen tail --
        both fail quietly, so each is a skip, not a clamp."""
        if dur <= 0:
            return _skip(beat, kind, "no duration")
        if host is None:
            return _skip(beat, kind, "no clip covers the record time "
                                     "(a gap between beats?)")
        f = file_by_name[beat["file"]]
        if not f.get("has_audio", False):
            return _skip(beat, kind, "%s has no audio" % f["name"])
        # Bounded by the usable window, which is the whole file when nothing
        # was trimmed. A J-cut's audio runs BEFORE its own picture, so on a
        # take that starts at the trim's in-point the lead is exactly the
        # excluded seconds — the fumbled walk-up, played under the outgoing
        # shot. Skipped, not clamped, for the reason above: a shortened
        # split edit is a different edit, and the editor asked for this one.
        _t_in, _t_out = trim_window(trims, f["name"], f["duration"])
        if src_start < _t_in or src_start + dur > _t_out:
            return _skip(beat, kind, "reaches outside the %s"
                         % ("clip's trim" if f["name"] in trims else "take"))
        child_off = host["src_s"] + (rec_start - host["record_s"])
        if child_off < 0:
            return _skip(beat, kind, "would need a negative offset")
        if kind == "jcut":
            # the host keeps only the audio BEFORE the incoming voice starts.
            # A trim of zero would silence the whole host segment, which is a
            # worse edit than the overlap -- so drop the J-cut instead.
            keep = rec_start - host["record_s"]
            if keep <= 0:
                return _skip(beat, kind, "would mute the whole previous clip")
            audio_trim[id(host)] = keep
        aid_a = register(f["name"], f["path"], f["duration"], True)
        split_children.setdefault(id(host), []).append(
            '<audio lane="-1" ref="%s" name=%s offset="%s" start="%s" '
            'duration="%s" role="dialogue"/>'
            % (aid_a, quoteattr("%s_%s" % (beat["id"], kind)),
               grid.rt(child_off), grid.rt(src_start), grid.rt(dur)))

    _beats = tl_map["beats"]
    for _i, _b in enumerate(_beats):
        if not _b.get("segments"):
            continue
        lead = _b.get("audio_lead")
        if lead and _i > 0:
            # audio runs from (picture start - lead) up to picture start
            _rec = _b["record_s"] - lead
            _src = _b["segments"][0]["src_s"] - lead
            _split(_b, _host_for(_beats[:_i], _rec), _rec, _src, lead, "jcut")
        tail = _b.get("audio_tail")
        if tail and _i < len(_beats) - 1:
            # audio carries on from where the picture stopped
            _rec = _b["record_e"]
            _src = _b["segments"][-1]["src_e"]
            _split(_b, _host_for(_beats[_i + 1:], _rec), _rec, _src, tail, "lcut")

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
        # split-edit audio belonging to a NEIGHBOUR beat, hosted by this one
        for _seg in beat["segments"]:
            children_by_seg[id(_seg)].extend(split_children.get(id(_seg), []))
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
            # a J-cut on the NEXT beat ends this clip's audio early; its
            # picture is untouched. audioStart mirrors start -- it shifts the
            # source in-point, not the timeline slot.
            audio_attrs = ""
            if id(seg) in audio_trim:
                audio_attrs = ' audioStart="%s" audioDuration="%s"' % (
                    grid.rt(seg["src_s"]), grid.rt(audio_trim[id(seg)]))
            # A picture beat that has NOT opted into natural sound is
            # emitted the way a cover is — <video> carries no audio,
            # whatever the asset declares. <asset-clip> would play the
            # clip's own sound under the cut, which is the exact leak the
            # cover rule exists to prevent (2026-08-28).
            silent_picture = (beat.get("kind") == "picture"
                              and not beat.get("natural_sound"))
            if silent_picture:
                spine_parts.append(
                    '<video ref="%s" name=%s offset="%s" start="%s" '
                    'duration="%s">%s</video>'
                    % (aid, quoteattr("%s_%s" % (beat["id"], j)),
                       grid.rt(seg["record_s"]), grid.rt(seg["src_s"]),
                       grid.rt(dur), body))
            else:
                spine_parts.append(
                    '<asset-clip ref="%s" name=%s offset="%s" start="%s" duration="%s"%s format="r1">%s</asset-clip>'
                    % (aid, quoteattr("%s_%s" % (beat["id"], j)), grid.rt(seg["record_s"]),
                       grid.rt(seg["src_s"]), grid.rt(dur), audio_attrs, body))

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
