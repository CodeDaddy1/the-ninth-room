# Phase 0 — DaVinci Resolve control findings (verified 2026-08-18)

Everything below was tested live against DaVinci Resolve **21.0.4.5, free
edition**, on this Mac. These findings are the ground rules the whole pipeline
is built on. Re-test only if Resolve is upgraded to Studio or a new major
version.

## 1. How we control Resolve: the in-app bridge (only working route)

**External scripting is fully blocked in the free edition.** All three
transports were tried while Resolve was running and all returned nothing:

| Route | Result |
|---|---|
| `fusionscript.so` from `/usr/bin/python3` (`dvr.scriptapp("Resolve")`) | `None` |
| Bundled `fuscript -l lua` (`bmd.scriptapp("Resolve")`, plain and `"127.0.0.1"`) | `nil` |
| Script-server port 1144 | not listening (checked with `lsof`) |

Also: `fuscript -l py3` fails with "Language 'py3' is not available" — Resolve
finds no framework Python to load. Irrelevant for us: the bridge is Lua, which
is built in.

**What works: scripts started from inside Resolve.** Our bridge
(`pipeline/bridge/Ninth Room Bridge.lua`, installed to
`~/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Scripts/Utility/`)
runs from **Workspace ▸ Scripts ▸ Ninth Room Bridge** and then executes Lua
command files the outside pipeline drops into `work/_bridge/inbox/`, writing
results to `outbox/`. A heartbeat file (`bridge.alive`) proves liveness.

Two facts about getting it started:
- Resolve scans the Scripts folder **at startup only** — install the script,
  then (re)start Resolve, or the menu item won't exist.
- Clicking the menu item can be automated with AppleScript UI scripting, but
  the host app needs **Accessibility permission** (System Settings ▸ Privacy &
  Security ▸ Accessibility). Until granted: one manual click per Resolve
  session. This is the only human action "full auto" still needs.

## 2. What survives FCPXML import (the timeline mechanism)

`MediaPool:ImportTimelineFromFile(path, {timelineName=..., importSourceClips=true})`
with hand-generated FCPXML 1.9 (stdlib string/XML — no OTIO dependency needed):

| Construct | Survives? | Evidence |
|---|---|---|
| Cuts with source in/out points (`asset-clip start/duration/offset`) | ✅ | item list matches frame-exactly |
| **Cross-dissolve** (`<transition>` + `filter-video "Cross Dissolve"`) | ✅ | rendered mp4 shows an exact 50/50 color blend mid-cut; round-trip export keeps the transition |
| Connected clips on `lane="1"` → V2 | ✅ | items land on V2 at the right frames (offset is relative to the **parent's source time**, mind the parent's `start`) |
| ProRes 4444 clip with straight alpha on V2 | ✅ | card composites over V1 in the render; Resolve reads it as Alpha mode "Straight" |
| **Split-edit audio** (connected `<audio lane="-1">` child) | ✅ | **verified 2026-08-23.** A 1s `<audio>` child of clip A referencing clip B's asset landed on **A2 at frames 60–90** while B's video stayed at 90 — audio one second ahead of its picture. This is the J-cut / L-cut mechanism; the child's `offset` is in the PARENT clip's source time, same rule as connected `<video>`. Resolve made the second audio track itself. |
| **`audioDuration` shorter than `duration`** (asset-clip) | ✅ | **verified 2026-08-23.** V1 ran 0–90 while A1 stopped at 60: the clip's audio ends before its picture. This is the OUTGOING half of a J-cut — the connected `<audio>` child alone only adds the incoming voice, it cannot stop the previous one. `audioStart` mirrors `start`; it shifts the source in-point, NOT the timeline slot, so it cannot delay audio without desyncing it. |
| **`audioDuration="0/1s"`** (silence a clip entirely) | ✅ | **verified 2026-08-23.** Splitting one clip into two contiguous spine entries and zeroing the head's audio gave V1 continuous 0–150 with A1 only 45–150 — picture seamless, audio starting late. This is the INCOMING half of an L-cut. Not yet implemented: it restructures the spine, so overlay children must be re-homed across the split. |
| **`adjust-transform` keyframes** (position/scale animation) | ❌ **dropped** | round-trip export shows static `scale="1 1" position="0 0"` |
| Static `adjust-transform` values | untested (assumed OK, but we don't need them) | |

**Consequence (locked design decision): all graphics animation is baked into
the asset.** Design cards are rendered by ffmpeg into short **ProRes 4444
`.mov` clips with alpha** (slide/fade/scale via `overlay` expressions +
`fade=...:alpha=1`), and the timeline simply places the clip. Verified
end-to-end: the baked slide-up plays in Resolve's own render (card top edge
y=1054 mid-slide → y=1000 at rest).

ffmpeg gotcha that cost an hour: a still-image input used in a bake **must**
use `-loop 1 -t <dur> -r <fps>`; without `-loop 1` the fade filter sees a
single frame at t=0 and the whole overlay renders transparent.

## 3. Direct API calls that work (through the bridge)

- `ProjectManager`: `CreateProject` / `LoadProject` / `GetCurrentProject`
- `Project:SetSetting` — `timelineFrameRate`, `timelineResolutionWidth/Height`
  (vertical 1080×1920 works)
- `MediaPool:ImportMedia({paths})`, `CreateEmptyTimeline`, `AddTrack("video")`
- `MediaPool:AppendToTimeline({{mediaPoolItem, startFrame, endFrame,
  trackIndex, recordFrame}})` — fallback timeline builder (hard cuts only)
- `TimelineItem:SetProperty("ZoomX", 1.5)` — static transforms
- `Timeline:GetItemListInTrack`, `Timeline:Export(path,
  resolve.EXPORT_FCPXML_1_9, resolve.EXPORT_NONE)` — used for verification
- Render: `SetCurrentRenderFormatAndCodec("mp4", "H264")`,
  `SetRenderSettings({TargetDir=..., CustomName=...})`, `AddRenderJob`,
  `StartRendering(jobId)`, `IsRenderingInProgress()` polling — produced a
  playable H.264 mp4.

## 4. Leftovers in Resolve from the spike

Projects `CURATED_SPIKE`, and inside it timelines `spike_append`,
`spike_fcpxml`, `spike_render`, `spike_render2` — safe to delete anytime.

## 5. Color: LUTs through the API (verified 2026-08-19)

- `MediaPoolItem:SetClipProperty("Input LUT", …)` is READ-ONLY through the
  API — every value form returns false. A media-pool input LUT cannot be
  assigned by script.
- `TimelineItem:SetLUT(1, "DJI/DJI_X7_DLOG2Rec709.cube")` works (relative to
  the master LUT folder `/Library/Application Support/Blackmagic Design/
  DaVinci Resolve/LUT/`). Within one node, the LUT is applied AFTER that
  node's CDL, and there is no API to add a second node — so "grade after
  LUT" cannot be built literally. `pipeline/color.py` achieves it
  mathematically instead: it inverts the LUT's measured gray response and
  back-solves the CDL so the post-LUT image lands on the standard targets.

## Render queue via bridge (S2 spike, 2026-08-22)

The FREE edition's render queue is fully scriptable through the in-app
bridge: `SetRenderSettings{SelectAllFrames=false, MarkIn/MarkOut, TargetDir,
CustomName}` → `AddRenderJob()` (returns a job id) → `StartRendering(id)`
(async, returns immediately) → poll `GetRenderJobStatus(id)`
(`JobStatus`/`CompletionPercentage`, "Rendering" → "Complete") →
`DeleteRenderJob(id)`. A 48-frame probe of hmns_210023 rendered to mp4 in
~5s with no watermark. StartRendering flips Resolve to the Deliver page —
harmless, but don't drive it while Caleb is mid-edit.

## Conform primitives (S3 spike, 2026-08-22)

All three conform operations work in the FREE edition through the bridge:
`AppendToTimeline({{mediaPoolItem, startFrame, endFrame, trackIndex,
recordFrame}})` lands a VIDEO clip at the exact record frame on the named
track; adding `mediaType = 2` does the same for AUDIO onto an audio track
(verified: items report GetStart() == recordFrame); and
`Timeline:DeleteClips({item})` removes a timeline item. recordFrame is
relative to frame 0 — offset by `Timeline:GetStartFrame()` when the
timeline starts at 01:00:00:00.
