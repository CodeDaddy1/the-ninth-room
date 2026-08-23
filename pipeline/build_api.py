"""Build the Resolve timeline through the scripting API (AppendToTimeline).

Why this exists alongside timeline.py's FCPXML writer: Resolve's FCPXML
importer will not link 4K HEVC DJI assets — a hand-written file imports with
every clip OFFLINE (verified 2026-08-18; synthetic H.264 assets link fine, so
it is a codec/asset-matching limitation, not a syntax error). `ImportMedia`
handles the same files without complaint, and `AppendToTimeline` places pool
items frame-exactly, so this path trades one feature for reliability:

  FCPXML path : cuts + CROSS-DISSOLVES + lanes, but offline media on DJI
  API path    : cuts + lanes, media guaranteed linked, NO transitions

The API has no transition call in any edition, so dissolves degrade to hard
cuts here and are reported. Both paths share the same timeline_map, so
switching back is a one-line change once FCPXML linking is solved.

What breaks if this is wrong: clips land on the wrong frame (source vs record
frame confusion) or b-roll brings its own audio and buries the narration.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from . import resolve_api as ra
from .ingest import analysis_dir, work_path, IngestError

# Resolve's AppendToTimeline mediaType flags.
VIDEO_ONLY = 1


def _f(seconds: float, fps: float) -> int:
    return int(round(seconds * fps))


def _clip_frames(path: str) -> int:
    """Frame count of an overlay .mov, from the file itself.

    startFrame/endFrame are indices into the CLIP's own frames, and the
    overlay movs are baked at 24/30fps while the timeline runs 23.976 —
    computing endFrame with the timeline rate silently trimmed every 30fps
    caption clip to ~80% of its length (found 2026-08-19: 'cockroaches 🪳'
    never appeared in the master). The plan's overlay durations equal the mov
    durations by construction, so the correct request is simply every frame
    the file has.
    """
    proc = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=nb_frames", "-of", "csv=p=0", path],
        capture_output=True, text=True, timeout=30)
    out = (proc.stdout or "").strip()
    if proc.returncode != 0 or not out.isdigit() or int(out) < 1:
        raise IngestError("could not read frame count of %s: %s"
                          % (path, (proc.stderr or out)[-200:]))
    return int(out)


def build(slug: str, cards: "list[dict]", caption_clips: "list[dict]", log=print) -> str:
    """Create the timeline in Resolve from timeline_map.json. Returns its name."""
    tl_map = json.loads((analysis_dir(slug) / "timeline_map.json").read_text())
    catalog = json.loads((analysis_dir(slug) / "catalog.json").read_text())
    by_name = {f["name"]: f for f in catalog["files"]}
    fps = tl_map["fps"]

    # 0. Level the narration first — Resolve has no clip-gain API, so quiet
    #    chapters must be fixed on the media (see pipeline/audio.py). A
    #    normalized file substitutes for the original everywhere below, under
    #    its own name so the media pool never has two clips with one name.
    from . import audio as audio_mod
    speech_files = [by_name[b["file"]] for b in tl_map["beats"]]
    norm = audio_mod.normalize_files(slug, list({f["name"]: f for f in speech_files}.values()),
                                     log=log)
    for original, leveled in norm.items():
        entry = dict(by_name[original])
        entry["path"] = leveled
        entry["name"] = Path(leveled).name
        by_name[original + "::norm"] = entry

    def source_for(name: str) -> "dict":
        """The file to actually use for a clip: leveled if one was made."""
        return by_name.get(name + "::norm", by_name[name])

    # 1. Collect every media file this edit needs, import it, and map
    #    file path -> media pool item (by name, which Resolve preserves).
    paths = []
    for b in tl_map["beats"]:
        paths.append(source_for(b["file"])["path"])
        for br in b["broll"]:
            paths.append(by_name[br["file"]]["path"])
    for item in list(cards) + list(caption_clips):
        paths.append(item["path"])
    uniq = sorted({str(Path(p).resolve()) for p in paths})
    # Overlays are imported SEPARATELY so they can be filed in their own bin
    # (resolve_api.BIN_OVERLAYS) — a card must land in the same place whether
    # this build imported it or a later conform did. Camera originals and
    # b-roll keep going to the pool's current folder: they are long-lived and
    # may already be organised by hand, so this does not move them.
    overlay_paths = sorted({str(Path(item["path"]).resolve())
                            for item in list(cards) + list(caption_clips)})
    media_paths = [p for p in uniq if p not in set(overlay_paths)]
    lua_list = ",".join(ra.lua_str(p) for p in media_paths)
    lua_ovlist = ",".join(ra.lua_str(p) for p in overlay_paths)
    # Overlay movs are REGENERATED at the same path every build, but a reused
    # project keeps the old pool items — after a few builds the pool held four
    # BT05.movs of different lengths and the name scan picked one at random
    # (found 2026-08-19). Purge same-name overlay items before importing so
    # exactly one, current copy exists. Camera originals never change, so
    # they are left alone.
    overlay_names = sorted({Path(item["path"]).name
                            for item in list(cards) + list(caption_clips)})
    lua_overlays = ",".join(ra.lua_str(n) for n in overlay_names)
    got = ra.send("preload_media", '''%(binhelper)s
local mp = resolve:GetProjectManager():GetCurrentProject():GetMediaPool()
local purge_names = {}
for _, n in ipairs({%(purge)s}) do purge_names[n] = true end
local stale = {}
local function sweep(folder)
  for _, c in ipairs(folder:GetClipList()) do
    if purge_names[c:GetName()] then stale[#stale+1] = c end
  end
  for _, sub in ipairs(folder:GetSubFolderList()) do sweep(sub) end
end
sweep(mp:GetRootFolder())
if #stale > 0 then mp:DeleteClips(stale) end
local items = mp:ImportMedia({%(media)s}) or {}
local ovpaths = {%(overlays)s}
if #ovpaths > 0 then
  for _, it in ipairs(_nr_import(mp, '%(bin)s', ovpaths) or {}) do items[#items+1] = it end
end
-- Stash THIS build's imports by name. Rebuilds regenerate overlay .movs at
-- the same paths, and the pool can hold stale same-name items from earlier
-- builds whose files were replaced or missing; a name-only scan could pick
-- an offline one. Bridge globals persist within a session, so later append
-- commands prefer these fresh handles.
_nr_imported = _nr_imported or {}
for _, it in ipairs(items or {}) do _nr_imported[it:GetName()] = it end
return tostring(items and #items or 0)
''' % {"binhelper": ra.LUA_BIN_IMPORT, "purge": lua_overlays,
        "media": lua_list, "overlays": lua_ovlist,
        "bin": ra.BIN_OVERLAYS}, timeout=900)
    log("[build] media pool: %s/%d clips" % (got, len(uniq)))

    # Measure every camera clip now so its grade is ready to apply once the
    # timeline exists. We measure rather than assume a log profile — see the
    # pipeline/color.py docstring for why the filename suffix lies.
    from . import color as color_mod
    color_mod.use_standard_color_science(log=log)
    camera_files = {}
    for b in tl_map["beats"]:
        camera_files[source_for(b["file"])["name"]] = source_for(b["file"])
        for br in b["broll"]:
            camera_files[by_name[br["file"]]["name"]] = by_name[br["file"]]
    grades = color_mod.plan_grade(slug, list(camera_files.values()), log=log)

    # 2. Fresh empty timeline at the right rate/resolution.
    from .timeline import CANVAS
    w, h = CANVAS[tl_map["orientation"]]
    import time as _time
    tl_name = "%s_%s" % (slug, _time.strftime("%H%M%S"))
    fps_str = ("%.3f" % fps).rstrip("0").rstrip(".")
    out = ra.send("new_timeline", '''
local proj = resolve:GetProjectManager():GetCurrentProject()
local mp = proj:GetMediaPool()
proj:SetSetting("timelineFrameRate", %s)
proj:SetSetting("timelineResolutionWidth", "%d")
proj:SetSetting("timelineResolutionHeight", "%d")
local got = tostring(proj:GetSetting("timelineFrameRate"))
local tl = mp:CreateEmptyTimeline(%s)
if not tl then return error("CreateEmptyTimeline failed") end
proj:SetCurrentTimeline(tl)
while tl:GetTrackCount("video") < 4 do tl:AddTrack("video") end
return tl:GetName() .. " tracks=" .. tl:GetTrackCount("video") .. " fps=" .. got
''' % (ra.lua_str(fps_str), w, h, ra.lua_str(tl_name)), timeout=300)
    log("[build] timeline %s @ %dx%d (%s)" % (tl_name, w, h, out))

    # A project's frame rate LOCKS once it contains a timeline; a mismatch
    # makes Resolve conform every clip (23.976 into a 29.97 project stretches
    # each clip by 1.25x and the edit drifts). Fail loudly rather than render
    # a wrong-length video.
    got_fps = out.split("fps=")[-1].strip()
    if abs(float(got_fps) - fps) > 0.01:
        raise IngestError(
            "project frame rate is %s but the footage is %.3f — Resolve locks the "
            "rate to the project's first timeline. Use a fresh project for this "
            "slug (see render.project_for_slug)." % (got_fps, fps))

    # 3a. V1 first, appended IN ORDER with no recordFrame. The talking-head
    #     segments are contiguous by construction, so a plain sequential
    #     append lands them exactly — and it avoids recordFrame, which
    #     Resolve honours unreliably when one batch spans several tracks.
    dissolves_lost = sum(1 for b in tl_map["beats"] if b["transition_in"] == "dissolve")
    v1 = []
    for beat in tl_map["beats"]:
        src = source_for(beat["file"])
        for seg in beat["segments"]:
            # endFrame is EXCLUSIVE: a clip from s to e runs e-s frames, not
            # e-s+1. Subtracting one here cost exactly one frame per segment,
            # which is invisible on a single cut and 3.4s across 83 of them
            # (measured 2026-08-18: 734.51s rendered vs 737.90s planned).
            v1.append('{n=%s,s=%d,e=%d}' % (ra.lua_str(src["name"]),
                                            _f(seg["src_s"], fps),
                                            _f(seg["src_e"], fps)))
    out = ra.send("append_v1", '''
local proj = resolve:GetProjectManager():GetCurrentProject()
local mp = proj:GetMediaPool()
local tl = proj:GetCurrentTimeline()
local byname = {}
local function scan(f)
  for _, c in ipairs(f:GetClipList()) do byname[c:GetName()] = c end
  for _, s in ipairs(f:GetSubFolderList()) do scan(s) end
end
scan(mp:GetRootFolder())
for n, it in pairs(_nr_imported or {}) do byname[n] = it end
local infos = {}
for _, e in ipairs({%s}) do
  local item = byname[e.n]
  if not item then return error("missing pool item: " .. e.n) end
  infos[#infos+1] = {["mediaPoolItem"]=item, ["startFrame"]=e.s, ["endFrame"]=e.e}
end
local res = mp:AppendToTimeline(infos)
if not res or #res == 0 then return error("V1 append failed") end
-- Report where each segment actually landed; the overlays are positioned
-- against these real frames rather than the planned ones.
local base = tl:GetStartFrame()
local out = tostring(#res)
for _, it in ipairs(tl:GetItemListInTrack("video", 1)) do
  out = out .. "|" .. tostring(it:GetStart() - base) .. ":" .. tostring(it:GetDuration())
end
return out
''' % ",".join(v1), timeout=900)
    parts = out.split("|")
    log("[build] V1: %s/%d segments placed" % (parts[0], len(v1)))
    actual = [(int(p.split(":")[0]), int(p.split(":")[1])) for p in parts[1:]]
    if len(actual) != len(v1):
        raise IngestError("V1 placement mismatch: %d of %d segments" % (len(actual), len(v1)))

    # Zoom punches: static per-clip transforms on the marked segments (the
    # API supports SetProperty ZoomX/Y; animated keyframes it does not).
    zoom_specs = []
    seg_idx = 0
    for beat in tl_map["beats"]:
        for seg in beat["segments"]:
            seg_idx += 1
            if seg.get("zoom"):
                zoom_specs.append((seg_idx, float(seg["zoom"])))
    if zoom_specs:
        lua_z = ",".join("{i=%d,z=%.3f}" % s for s in zoom_specs)
        zout = ra.send("apply_zooms", '''
local tl = resolve:GetProjectManager():GetCurrentProject():GetCurrentTimeline()
local items = tl:GetItemListInTrack("video", 1)
local done = 0
for _, e in ipairs({%s}) do
  local it = items[e.i]
  if it and it:SetProperty("ZoomX", e.z) and it:SetProperty("ZoomY", e.z) then
    done = done + 1
  end
end
return "zoomed=" .. done
''' % lua_z, timeout=300)
        log("[build] %s of %d punch segments" % (zout, len(zoom_specs)))

    # 3b. Map each beat to the real record frame of its first segment, then
    #     place overlays relative to that.
    beat_start_frame = {}
    idx = 0
    for beat in tl_map["beats"]:
        beat_start_frame[beat["id"]] = actual[idx][0]
        idx += len(beat["segments"])

    def rec_frame(beat_id: str, offset_sec: float) -> int:
        return beat_start_frame[beat_id] + _f(offset_sec, fps)

    entries = []
    for beat in tl_map["beats"]:
        for br in beat["broll"]:
            bsrc = by_name[br["file"]]
            entries.append({
                "name": bsrc["name"],
                "start": _f(br["src_s"], fps),
                "end": _f(br["src_s"] + br["duration"], fps) - 1,
                "track": 2,
                "record": rec_frame(beat["id"], br["record_s"] - beat["record_s"]),
                "video_only": True,
            })
    beat_of_record = {b["id"]: b["record_s"] for b in tl_map["beats"]}

    def owning_beat(record_s: float) -> str:
        best = tl_map["beats"][0]["id"]
        for b in tl_map["beats"]:
            if b["record_s"] <= record_s:
                best = b["id"]
        return best

    for card in cards:
        bid = owning_beat(card["record_s"])
        entries.append({"name": Path(card["path"]).name, "start": 0,
                        "end": _clip_frames(card["path"]) - 1, "track": 3,
                        "record": rec_frame(bid, card["record_s"] - beat_of_record[bid]),
                        "video_only": True})
    for cap in caption_clips:
        bid = owning_beat(cap["record_s"])
        entries.append({"name": Path(cap["path"]).name, "start": 0,
                        "end": _clip_frames(cap["path"]) - 1, "track": 4,
                        "record": rec_frame(bid, cap["record_s"] - beat_of_record[bid]),
                        "video_only": True})

    lua_entries = ",\n".join(
        '{name=%s, s=%d, e=%d, track=%d, rec=%d, vo=%s}'
        % (ra.lua_str(e["name"]), e["start"], e["end"], e["track"], e["record"],
           "true" if e["video_only"] else "false")
        for e in entries)

    out = ra.send("append_overlays", '''
local proj = resolve:GetProjectManager():GetCurrentProject()
local mp = proj:GetMediaPool()
local tl = proj:GetCurrentTimeline()
local byname = {}
local function scan(folder)
  for _, c in ipairs(folder:GetClipList()) do byname[c:GetName()] = c end
  for _, sub in ipairs(folder:GetSubFolderList()) do scan(sub) end
end
scan(mp:GetRootFolder())
-- Same fresh-handle preference append_v1 has: this build's imports win.
for n, it in pairs(_nr_imported or {}) do byname[n] = it end

-- recordFrame is ABSOLUTE timeline frames, and a Resolve timeline starts at
-- the hour mark (01:00:00:00), not zero. Placing at 0 puts every clip before
-- the timeline start: appends "succeed" but the render comes out empty
-- (verified 2026-08-18 — a 108s edit rendered as 0.11s).
local base = tl:GetStartFrame()

local entries = {%s}
-- Overlays go one call PER CLIP: batching positioned clips across tracks made
-- Resolve drop some and mistime others (2026-08-18). One call each is slower
-- but lands every clip on its exact frame.
local placed, missing, failed = 0, {}, {}
for _, e in ipairs(entries) do
  local item = byname[e.name]
  if not item then
    missing[#missing+1] = e.name
  else
    local info = {
      ["mediaPoolItem"] = item,
      ["startFrame"] = e.s,
      ["endFrame"] = e.e,
      ["trackIndex"] = e.track,
      ["recordFrame"] = e.rec + base,
    }
    if e.vo then info["mediaType"] = %d end
    local res = mp:AppendToTimeline({info})
    if res and #res > 0 then placed = placed + 1
    else failed[#failed+1] = e.name .. "@V" .. e.track end
  end
end
local msg = "placed=" .. placed .. "/" .. #entries
if #missing > 0 then msg = msg .. " MISSING=" .. table.concat(missing, ",", 1, math.min(#missing, 4)) end
if #failed > 0 then msg = msg .. " FAILED=" .. table.concat(failed, ",", 1, math.min(#failed, 4)) end
return msg
''' % (lua_entries, VIDEO_ONLY), timeout=900)
    log("[build] %s" % out)
    if dissolves_lost:
        log("[build] note: %d dissolve(s) became hard cuts (no transition API)"
            % dissolves_lost)
    if "MISSING=" in out or "FAILED=" in out:
        raise IngestError("timeline build incomplete: %s" % out)

    color_mod.apply_grade({k: v for k, v in grades.items() if k in camera_files},
                          log=log)
    return tl_name
