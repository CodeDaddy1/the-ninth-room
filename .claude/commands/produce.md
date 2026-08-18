---
description: Full auto — raw footage in work/<slug>/footage/ becomes a rendered video in work/<slug>/deliverables/
argument-hint: <slug> [--review]
---

Produce the video for slug `$ARGUMENTS` end to end. Footage must already be
in `work/<slug>/footage/`. All Python runs with `/usr/bin/python3` from the
repo root.

1. **Analyze** (skip any step whose output already exists and is newer than
   the footage):
   - `/usr/bin/python3 -m pipeline.cli ingest <slug>`
   - `/usr/bin/python3 -m pipeline.cli takes <slug>`
   - `/usr/bin/python3 -m pipeline.cli broll <slug>`
2. **Story** — use the **story-designer** subagent for `<slug>`. It writes
   `work/<slug>/edit_plan.json` and must report VALID.
3. If `--review` was passed: stop here, show Caleb the plan summary, and wait
   for his go-ahead before continuing.
4. **Graphics** — use the **graphics-director** subagent for `<slug>`.
5. **Captions** — use the **caption-editor** subagent for `<slug>`.
6. **Build + render**:
   - `/usr/bin/python3 -m pipeline.cli produce <slug>`
   - If the bridge is down, this fails with the exact manual step (start
     `Workspace ▸ Scripts ▸ Curated Bridge` in Resolve). Relay it verbatim,
     then retry once the bridge heartbeat is alive.
7. **QC** — use the **qc-reviewer** subagent on the rendered file. On
   `QC: FAIL`, fix what it names (edit plan / cards / captions), re-run step
   6, and re-review — at most two repair loops before reporting to Caleb.

Finish by reporting: the deliverable path, runtime, the three-line story
(hook / build / payoff), and the QC verdict.
