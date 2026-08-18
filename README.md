# Curated Curiosities

A social-media brand that brings **curated content that piques curiosity** —
and the fully local program that edits its videos automatically.

Caleb shoots raw footage (talking-head takes + b-roll), drops it in
`work/<slug>/footage/`, and runs `/produce <slug>` in Claude Code. The
pipeline transcribes, picks best takes, cuts dead space, designs the story,
builds the timeline in DaVinci Resolve — cuts, transitions, brand design
cards, captions — and renders the finished video. No cloud, no paid APIs.

- Start here: `CLAUDE.md` (context) → `ULTRA-PLAN.md` (build plan) →
  `docs/resolve-findings.md` (Resolve ground rules)
- Stack: Python 3.9 (`/usr/bin/python3` only) + ffmpeg + faster-whisper +
  Pillow + headless Chrome + DaVinci Resolve (free) via the in-app Lua bridge
- AI judgment: Claude Code subagents in `.claude/agents/` — no API calls

v1 (stock-footage pipeline + Supabase dashboard + worker daemon) was retired
on 2026-08-18; its proven rendering techniques live on in
`docs/reference-renderers/`.
