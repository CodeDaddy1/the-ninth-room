# Curated Curiosities — Project Context

This is the master context file. Read it first. It tells you what the brand is,
what the program does, and the rules every agent follows.

## The brand in one line

**Curated Curiosities** surfaces the fascinating, overlooked, and surprising —
curated so the audience gets the wonder without the digging.

## What this repo is (v2, 2026-08-18 pivot)

A **fully local DaVinci Resolve auto-editor**. Caleb shoots raw footage —
talking-head takes of himself (with flubs and retakes) plus b-roll — drops it
in `work/<slug>/footage/`, and runs `/produce <slug>`. The pipeline
transcribes everything, picks the best takes, cuts dead space, designs the
story, renders brand design cards, builds the timeline in DaVinci Resolve
(cuts, transitions, graphics, captions), and renders the finished video to
`work/<slug>/deliverables/` — automatically, end to end.

The build plan (phases, DoD, risks) lives in `ULTRA-PLAN.md`. The verified
Resolve ground rules live in `docs/resolve-findings.md` — read it before
touching anything Resolve-adjacent; the free edition's constraints shaped the
whole architecture.

## Architecture in one paragraph

Mechanical work is Python 3.9 (`pipeline/` — **only** `/usr/bin/python3`,
keep code 3.9-compatible) using ffmpeg, faster-whisper, Pillow, and headless
Chrome. Creative judgment runs as **Claude Code subagents** (`.claude/agents/`)
that read and write JSON artifacts under `work/<slug>/` — there are no
Anthropic API calls and no paid services (**$0/mo is binding**). Resolve is
controlled through the in-app Lua bridge (`pipeline/resolve_api.py` +
`pipeline/bridge/Curated Bridge.lua`) because the free edition blocks external
scripting. Timelines are generated as FCPXML and imported; transitions survive
import, transform keyframes do not — so all graphics animation is **baked into
ProRes 4444 alpha clips** with ffmpeg before they reach the timeline.

## The agent team (v2)

1. **story-designer** — reads take transcripts + b-roll catalog + brand docs,
   writes `edit_plan.json`: the theme/problem the video solves, the hook,
   beat order, take picks and kill list, b-roll placement, transition policy.
2. **graphics-director** — decides which moments get design cards and writes
   their copy (`graphics_plan.json`).
3. **caption-editor** — turns the chosen takes' transcript into clean caption
   lines (text from the cleaned script, timing from whisper — never caption
   raw transcript).
4. **qc-reviewer** — checks the rendered output against the edit plan.
5. **post-production** — editing, color grading, and motion-graphics
   specialist. Use it when a render looks wrong (blown highlights, muddy
   shadows, bad cuts), when cards/captions/animation need designing or
   fixing, or when Resolve misbehaves. It measures and looks at frames
   rather than trusting settings.

## Brand tokens come from the design system

`brand/design-system/tokens/*.css` is synced from the "Curated Curiosities
Design System" project on claude.ai/design. `pipeline/design_tokens.py` reads
it, so cards use the same navy/amber/cream, Playfair Display, and Work Sans
as the thumbnails, site, and social kits. Re-pull the tokens after changing
the design system; don't hardcode brand values in the pipeline.

Dormant survivors from v1: `instagram-copywriter` (post copy, reactivate
later), `performance-analyst` (metrics loop, deferred).

## The core mechanic: the curiosity gap

Every video opens a loop the viewer *needs* closed. The hook creates the gap;
the content delivers the payoff. The non-negotiable rule:

> **The payoff must always land.** We open curiosity gaps honestly and we
> close them completely. No bait-and-switch, no withheld answer for
> engagement. Clickbait that doesn't deliver is the fastest way to kill a
> curiosity brand.

## Where things live

| Path | What it's for |
|---|---|
| `brand/*.md` | Mission, audience, pillars, voice, visual identity |
| `workflows/*.md` | Cadence + platform specs (safe zones, lengths) |
| `pipeline/` | The Python pipeline (see `pipeline/__init__.py` for the module map) |
| `docs/resolve-findings.md` | Verified Resolve API ground rules |
| `docs/reference-renderers/` | Proven whisper/Pillow/ffmpeg techniques from v1 |
| `work/<slug>/` | Per-video working dir (gitignored): footage in, deliverables out |
| `.claude/reminders.md` | Things only Caleb can do — append, don't just mention in chat |

## Rules every agent follows

1. **Accuracy is the brand.** Surprising claims must be verifiable; frame the
   unconfirmed as "claimed/disputed," never settled fact.
2. **Curiosity, not sensationalism.**
3. **Respect the payoff.** See above.
4. **Stay on-pillar** (`brand/content-pillars.md`); flag misfits.
5. **One voice** (`brand/voice-and-tone.md`) — Caleb's, since he's on camera.
6. **Platform-native** (`workflows/platform-specs.md`): safe zones, lengths,
   burned-in captions for mute-first viewing.
