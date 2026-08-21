---
description: Produce a video from raw footage in checkpointed stages, stopping for Caleb's review at each one
argument-hint: <slug> [--resume <checkpoint>] [--auto]
---

Produce the video for slug `$ARGUMENTS`. Footage must already be in
`work/<slug>/footage/`. All Python runs with `/usr/bin/python3` from the repo
root.

**This workflow stops for review.** Caleb evaluates and gives feedback at each
checkpoint; do not run past one without his go-ahead. `--auto` runs straight
through (use only when he says so); `--resume <checkpoint>` picks up at a
named checkpoint after changes.

## CP0 — Analysis (no review needed)

- `pipeline.cli ingest <slug>` — probe + transcribe (slow on big shoots;
  transcriptions are cached, so a rerun is cheap)
- `pipeline.cli takes <slug>` — segment takes, flag flubs, measure levels
- `pipeline.cli broll <slug>` — contact sheets

Then survey what the footage actually contains: cluster clips by their
embedded timestamps into sections, sample the strongest takes per section,
and report the day's map.

## CP1 — Scope 🛑 REVIEW

Report the footage map and propose: format, runtime, chapters, and anything
that needs a decision (unusable audio, missing coverage). **Stop for Caleb.**

## CP2 — Story 🛑 REVIEW

Use the **story-designer** subagent → `work/<slug>/edit_plan.json` (must
validate). Present the chapter-by-chapter outline, the verbatim hook and
closing line, and what strong material didn't fit. **Stop for Caleb.**

## CP3 — Graphics & captions 🛑 REVIEW

Use **graphics-director** → `graphics_plan.json` and **caption-editor** →
`captions.json`, then **hype-director** for the energy layer (emoji pops,
zoom punches, the playful cards). Every episode wants an engagement card
roughly every 60–90s — `brand/engagement-playbook.md` says which one and why.

Render sample stills/animations (`pipeline.animate`) and show them composited
over real frames — including the BRIGHTEST frame in the episode, which is the
legibility acceptance test. **Stop for Caleb.**

## CP4 — Assembly 🛑 REVIEW

`pipeline.cli produce <slug>` — builds the Resolve timeline, grades, renders.
Send the preview (downscale if over ~25 MB) with the QC numbers: runtime,
audio level, highlight clipping, shadow crush. **Stop for Caleb.**

## CP5 — Finish

Apply his notes, re-render, run the **qc-reviewer** subagent, and deliver the
master path plus a preview.

## Rules

- Use the **post-production** subagent for anything about grading, cuts,
  animation, or Resolve misbehaving.
- Use **sound-designer** after picture lock for the SFX cue sheet; Caleb
  mixes in post, so nothing is rendered into the video.
- Never report a stage done without measuring it (see that agent's checklist).
- If the bridge is down, `pipeline.cli bridge ensure` starts Resolve and the
  bridge; relay the manual step verbatim only if that fails.
