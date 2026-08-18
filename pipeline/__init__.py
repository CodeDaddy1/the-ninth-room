"""Curated Curiosities v2 — the DaVinci Resolve auto-editor pipeline.

Raw footage in `work/<slug>/footage/` goes in one end; a finished, rendered
video comes out of `work/<slug>/deliverables/`. Mechanical stages are Python
(this package); creative judgment runs as Claude Code subagents that read and
write the JSON artifacts under `work/<slug>/`.

Modules (built across phases — see ULTRA-PLAN.md):
    resolve_api  — the only door into DaVinci Resolve (in-app Lua bridge)
    ingest       — probe + transcribe raw footage            (Phase 2)
    takes        — take segmentation, metrics                (Phase 3)
    broll        — b-roll catalog + contact sheets           (Phase 3)
    graphics     — design cards: HTML -> PNG -> alpha .mov   (Phase 5)
    captions     — Pillow caption chips                      (Phase 5)
    timeline     — FCPXML writer                             (Phase 6)
    render       — Deliver-page automation + QC              (Phase 7)
    schemas      — validators for the JSON artifacts         (Phases 2-6)

Runs on /usr/bin/python3 (3.9) ONLY — keep code 3.9-compatible: keep the
`from __future__ import annotations` import, no runtime `X | Y` unions, no
`match` statements.
"""
