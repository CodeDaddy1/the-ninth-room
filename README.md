# The Ninth Room

A YouTube channel — a family walks a museum end to end, one room a week, and
the premise is in the name: **nine rooms, and one of them isn't on the map** —
and the fully local program that edits its videos automatically.

Caleb shoots raw footage (talking-head takes + b-roll), drops it in
`work/<slug>/footage/`, and runs `/produce <slug>` in Claude Code. The
pipeline transcribes, picks best takes, cuts dead space, designs the story,
builds the timeline in DaVinci Resolve — cuts, transitions, brand design
cards, captions — and renders the finished episode. No cloud, no paid APIs.

- Start here: `CLAUDE.md` (context) → `ULTRA-PLAN.md` (build plan) →
  `docs/resolve-findings.md` (Resolve ground rules)
- Brand: `brand/brand-brief.md` → `brand/visual-identity.md` →
  `brand/engagement-playbook.md`
- Stack: Python 3.9 (`/usr/bin/python3` only) + ffmpeg + faster-whisper +
  Pillow + headless Chrome + DaVinci Resolve (free) via the in-app Lua bridge
- AI judgment: Claude Code subagents in `.claude/agents/` — no API calls

The look is **Cyanotype**: navy ground, chalk type, one yellow moment per
frame, cyan for anything structural, and the Archway mark. It is synced from
the *The Ninth Room Design System* project on claude.ai/design, which is the
source of truth — this repo holds a copy in `brand/design-system/`.

## History

- **v1** (stock-footage pipeline + Supabase dashboard + worker daemon) was
  retired 2026-08-18; its proven rendering techniques live on in
  `docs/reference-renderers/`.
- The channel was **Curated Curiosities** until 2026-08-20. The rebrand to The
  Ninth Room changed the name, the identity, and the format (one room a week,
  family on camera). The old brand is kept for reference in
  `brand/_retired-curated-curiosities/`.
- The **directory name is legacy.** It stays `curated-curiosities` because
  moving it would break the Resolve bridge path and relink every media
  reference in the shipped HMNS timeline.
