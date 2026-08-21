# The Ninth Room v2 — DaVinci Resolve Auto-Editor

> Rebranded 2026-08-20. This plan was written as *Curated Curiosities*; the
> program is unchanged, the channel is now **The Ninth Room**. The identity
> that the graphics phases build against is the Cyanotype system in
> `brand/visual-identity.md`, not whatever a phase below calls the look.

## Context

Caleb is pivoting the channel from a stock-footage assembly pipeline (Supabase dashboard + worker daemon + ffmpeg) to a **fully local program that edits his own raw footage into finished videos inside DaVinci Resolve, automatically, end to end**. He now shoots the footage himself: talking-head takes of him on camera (with flubs and retakes) plus b-roll he films. The program must transcribe everything, pick the best takes, cut dead space, design the story (theme/problem → hook → escalating beats → payoff, per the brand's curiosity-gap rules), place brand-designed animated graphics, build the timeline in Resolve with good cuts and transitions, and render the final mp4 — no human touch after kickoff.

Locked decisions (Caleb, 2026-08-18): **full teardown** of dashboard/Supabase/daemon/stock-fetcher; footage = on-camera takes + self-shot b-roll; graphics = HTML design cards → PNG → animated in Resolve; **full auto through final render**. Cost stays **$0/mo**: all AI judgment runs as Claude Code subagents (no API), all mechanical work is Python 3.9 + ffmpeg + faster-whisper + Pillow + headless Chrome — all verified installed.

## Verified environment facts (design constraints)

- **Resolve 21.0.0, free edition** (no "Studio"), scripting API present. Free edition historically restricts *external* scripting; scripts run from inside Resolve (Workspace ▸ Scripts) always work. **Phase 0 resolves this empirically.**
- API verified in the local README: `ImportTimelineFromFile` (accepts **FCPXML/OTIO/EDL/AAF/DRT**), `AppendToTimeline([{mediaPoolItem, startFrame, endFrame, trackIndex, recordFrame}])`, `LoadRenderPreset` / `SetRenderSettings` / `AddRenderJob` / `StartRendering`, `TimelineItem.SetProperty("ZoomX", …)` (static transforms only — animated keyframes must come from the imported timeline file or Fusion).
- There is **no transition-adding API** in any Resolve edition → transitions must be declared in a generated timeline file and imported. This makes **"generate FCPXML → ImportTimelineFromFile"** the primary mechanism and `AppendToTimeline` (hard cuts only) the fallback.
- `/usr/bin/python3` (3.9.6) is the only Python. faster-whisper 1.2.1 (base.en cached), Pillow 11.3.0, numpy, requests installed. ffmpeg 8.1.1 **without drawtext** → all text is Pillow-rendered PNG (proven pattern). Chrome present for HTML→PNG. No OTIO lib (not needed — FCPXML via stdlib `xml.etree`).
- Proven $0 techniques to promote from `work/houston-no-zoning/_build_synced.py` + `_transcribe.py`: whisper word timestamps; difflib anchor-alignment + interpolation; Pillow caption chips above platform safe zones.

## Architecture (locked)

```
work/<slug>/
├── footage/            ← Caleb drops raw clips here (the only manual step)
├── analysis/
│   ├── catalog.json    probe results: every file, fps/res/duration/audio
│   ├── <file>.words.json   whisper word timings per speech file
│   ├── takes.json      segmented takes: transcript, timings, disfluency metrics
│   ├── broll.json      b-roll catalog: tags/description per clip
│   └── sheets/<clip>.jpg   3×3 contact sheets the agents view
├── edit_plan.json      story-designer agent output (the edit's single source of truth)
├── graphics_plan.json  graphics-director agent output
├── graphics/*.png      rendered design cards (2×, brand tokens)
├── captions/*.png      Pillow caption chips
├── timeline.fcpxml     generated timeline (cuts, transitions, 4 tracks, keyframes)
└── deliverables/       final render + thumbnail
```

- New Python package **`pipeline/`** (3.9-compatible, stdlib + installed deps only): `ingest.py`, `takes.py`, `broll.py`, `graphics.py`, `captions.py`, `timeline.py` (FCPXML writer), `resolve_api.py` (connection + import + render), `schemas.py` (hand-rolled validators, same pattern as today's `worker/orchestrator/schemas.py`), `cli.py`.
- **Track layout:** V1 talking head · V2 b-roll cutaways · V3 design cards (keyframed scale/position/opacity) · V4 caption chips. A1 program audio.
- **New agent roster** (`.claude/agents/`): `story-designer` (reads takes.json + broll.json + contact sheets + brand docs → `edit_plan.json`: theme/problem, hook take, beat order, take picks + kill list, b-roll placement, transition policy), `graphics-director` (→ `graphics_plan.json`: card moments, type, copy), `caption-editor` (cleans chosen-take transcript into caption lines; text from cleaned script, timing from whisper — never caption raw transcript), `qc-reviewer` (reviews rendered output's probe stats + final timeline vs edit_plan). Old agents retired except `instagram-copywriter` (kept dormant for post copy) and `performance-analyst` (deferred).
- **Invocation:** `/produce <slug>` slash command orchestrates: python stages → subagents → FCPXML → Resolve import → render → QC. `--review` flag inserts a pause after `edit_plan.json` for cheap insurance; default is full auto.
- **Music: deferred to v2** (ffmpeg sidechain ducking pre-render exists as a known path; Fairlight isn't scriptable).
- Format targets per video config: vertical 1080×1920 (reels/shorts) or 1920×1080 long-form; timeline fps = dominant source fps.

## Phases

### Phase 0 — Resolve control spike (everything hangs on this)
Test with Resolve running: (a) external API connection from `/usr/bin/python3` (`fusionscript.so` env vars); (b) if blocked (free-edition limit), the in-app fallback: our launcher script in `~/Library/.../Fusion/Scripts/Utility/` driving the same code from Workspace ▸ Scripts; (c) `ImportTimelineFromFile` smoke test with a hand-built minimal FCPXML: two clips, one cross-dissolve, one PNG still on V2 with position/scale keyframes; (d) `AppendToTimeline` + `SetProperty` smoke; (e) `AddRenderJob`/`StartRendering` round trip.
**DoD:** `pipeline/resolve_api.py` connects via whichever route works; `docs/resolve-findings.md` records exactly what survives FCPXML import (dissolves? keyframes? both?).
**Risks:** external scripting blocked → in-app launcher (designed in, not a rewrite); FCPXML keyframes dropped on import → cards animate via static `SetProperty` + per-card zoompan baked by ffmpeg into the PNG→mp4 instead (documented switch).
**What breaks if wrong:** everything downstream — which is why it's Phase 0.

### Phase 1 — Teardown + restructure
`make uninstall-launchd`; delete `dashboard/`, `worker/` daemon+db, `supabase/`, `infra/`, `scripts/fetch_assets.py`, old agents/commands; keep `brand/`, `workflows/` (update platform-specs references), promote `_build_synced.py` techniques into `pipeline/`. Rewrite `CLAUDE.md` and replace `ULTRA-PLAN.md` with this plan. Reminders file entry: Caleb may delete the Supabase + Vercel projects (his hands).
**DoD:** repo contains only v2 surface; `git log` clean commit; launchd empty; `/usr/bin/python3 -m py_compile` green on `pipeline/`.

### Phase 2 — Ingest & transcription
`pipeline/ingest.py`: probe every file in `footage/` (ffprobe → catalog.json), detect speech vs b-roll (audio presence + whisper), transcribe speech files with word timestamps, silence map (word-gap analysis + ffmpeg `silencedetect` cross-check).
**DoD:** real footage folder → `catalog.json` + `*.words.json` correct on spot-check.
**What breaks if wrong:** cuts land mid-word everywhere downstream.

### Phase 3 — Take analysis + b-roll catalog
`takes.py`: segment talking-head files into takes (silence gaps ≥ ~1.5s, restart-phrase detection via repeated-shingle similarity with difflib), compute per-take metrics (duration, filler count, completeness, restarts). `broll.py`: 3×3 contact sheet per clip (ffmpeg frame grabs + Pillow grid) for agent viewing.
**DoD:** `takes.json` groups retakes of the same content and metrics match a human spot-check; `broll.json` + sheets exist for every non-speech clip.

### Phase 4 — Story-designer agent + edit_plan contract
Agent + `validate_edit_plan` (only real take/clip IDs, monotonic timeline math, hook ≤15s, payoff present, kill-list justified). Command does the glob/pre-work (pattern from existing commands).
**DoD:** on real footage the agent emits a valid `edit_plan.json` whose story reads well; validator green.
**What breaks if wrong:** the video is mechanically fine but boring — this file IS the storytelling.

### Phase 5 — Design cards + captions
`graphics.py`: brand HTML templates (hook title, beat/section, stat/fact, quote, outro/CTA) → headless Chrome `--screenshot` at 2×; `graphics-director` agent fills `graphics_plan.json`. `captions.py`: caption-editor agent cleans lines; Pillow chips with whisper timing, safe-zone anchored.
**DoD:** PNGs pixel-checked against brand tokens (colors sampled, not assumed); caption timing aligns with audio in a scrub test.

### Phase 6 — Timeline generation + Resolve import
`timeline.py`: stdlib FCPXML writer — V1 picked takes with dead-space trims (± breathing-room padding), V2 b-roll cutaways, V3 keyframed cards, V4 captions, transitions per edit_plan policy (hard cut default; dissolve on act boundaries). `resolve_api.py` imports it, relinks media.
**DoD:** imported timeline in Resolve plays the designed video: right takes, no dead air, b-roll where planned, cards animate, captions synced. Matches `edit_plan.json` frame math.
**Risk:** FCPXML edge cases per Phase-0 findings; the writer only uses constructs the spike proved.

### Phase 7 — Render, QC, `/produce` end to end
`render.py`: render preset per format, `AddRenderJob` → `StartRendering`, poll to completion. QC: ffprobe checks (duration vs plan, audio levels, resolution) + `qc-reviewer` agent. `/produce` command wires all stages with resumable stage markers.
**DoD:** one command, real footage in → verified mp4 in `deliverables/`; a second run resumes/reproduces.

## Subagent map (build-time)
- Python pipeline stages: built directly (general-purpose review pass after Phases 3 and 6).
- Card HTML templates: frontend-engineer review for the brand-token CSS.
- No supabase/devops agents — that world is being deleted.

## Verification matrix
| Phase | Check |
|---|---|
| 0 | spike scripts run against live Resolve; findings doc committed |
| 1 | `launchctl list \| grep curated` empty; repo tree diff reviewed; py_compile green |
| 2–3 | run on Caleb's real footage; human spot-check of takes.json vs actual flubs |
| 4–5 | schema validators green; sampled PNG pixels = brand hex; caption scrub test |
| 6 | Resolve timeline visually matches edit_plan; frame math asserted in tests |
| 7 | `/produce` full run → ffprobe assertions + qc-reviewer pass on the mp4 |

## Caleb's-hands items (logged to reminders in Phase 1)
- Record real test footage (a few takes + b-roll) for Phases 2–7 verification.
- Resolve Preferences ▸ System ▸ General: set "External scripting using: Local" if present (Phase 0 will say).
- Optionally delete the Supabase project (`xnyxdpezsfvltmqnzkme`) and Vercel `curated-curiosities` project once teardown ships; brand brief POV line ("voice on, face off") needs his sign-off to change to on-camera.
