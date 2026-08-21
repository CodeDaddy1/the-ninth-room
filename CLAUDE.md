# The Ninth Room — Project Context

This is the master context file. Read it first. It tells you what the channel
is, what the program does, and the rules every agent follows.

> **Repo path note.** The directory is `~/Projects/the-ninth-room`. A
> compatibility **symlink** at the old `~/Projects/curated-curiosities` path
> is deliberate and must stay: DaVinci Resolve stores absolute media paths,
> and the shipped HMNS timeline still points at the old location. Deleting
> the symlink takes that timeline offline until every clip is relinked.

## The channel in one line

**The Ninth Room** — a family explores the world's most interesting places —
museums, parks, ships, anywhere worth wondering about — and every episode
finds the one thing that wasn't on the map.

Fun first, educational second, on purpose. The laugh and the fact are the same
moment. Full brief: `brand/brand-brief.md`.

## What this repo is (v2, 2026-08-18 pivot)

A **fully local DaVinci Resolve auto-editor**. Caleb shoots raw footage —
talking-head takes of himself and the family (with flubs and retakes) plus
b-roll — drops it in `work/<slug>/footage/`, and runs `/produce <slug>`. The
pipeline transcribes everything, picks the best takes, cuts dead space,
designs the story, renders brand design cards, builds the timeline in DaVinci
Resolve (cuts, transitions, graphics, captions), and renders the finished
video to `work/<slug>/deliverables/` — automatically, end to end.

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

## The Studio (canonical UI) and the Edit Room (legacy)

**The Ninth Room Studio** (`~/Projects/the-ninth-room-studio`, Next.js) is
the canonical UI over this pipeline: channel landing page at `/`, and the
desks — Ideas, Planner, Overlays, Captions, Review — at `/studio` (local,
`STUDIO=1`). It talks to this repo's engine over HTTP and reads/writes the
same JSON artifacts the agents use. Read that repo's CLAUDE.md before
changing any `/api/*` shape here — the Studio's `src/lib/engine.ts` mirrors
them.

The Planner desk writes `work/<slug>/plan.json` (pre-shoot: chapters, shot
lists, card ideas, ninth-room candidates, derived checklist). The engine
validates it in `_validate_plan` and stamps identity; the story-designer
may read it for intent when present.

The inline-HTML UI served by `editroom.py` itself is **frozen legacy** —
kept working, gets no new features; new surfaces go in the Studio.

## The Edit Room production hub

`/usr/bin/python3 -m pipeline.cli editroom` serves every project at
http://127.0.0.1:8765 — a project picker, phase strip, and four desks
(Story / Shots / Overlays / Captions). Caleb starts a project and drops raw
clips/photos straight onto the page (photos become 6s b-roll clips); the
phase strip tells him what to tell Claude next. The agents run HERE in the
Claude session and read what the hub writes:

- **Story loop**: "pitch stories for <slug>" → story-designer writes
  `stories.json` (3 directions) → Caleb approves/redirects on the Story tab
  (`story_feedback.json`) → "write the edit plan for <slug>" once approved.
- **Assemble**: "assemble <slug>" = build-timeline + assets + proxies so the
  Shots desk can review the cut in story order.
- **Shot needs**: review.json entries may carry `"needs": ["broll","sfx",
  "cards"]` — route them in the fixer round: broll → story/b-roll pass,
  sfx → sound-designer, cards → graphics-director.
- **Ideas (channel-level)**: "scout ideas" → the scout agent writes
  `work/_scout/ideas.json`; Caleb saves/develops/dismisses on the Ideas tab.
- **Assets**: Caleb files requests on the Assets tab; "source assets for
  <slug>" → the asset-sourcer downloads licensed stock with a manifest.

## The agent team

1. **story-designer** — reads take transcripts + b-roll catalog + brand docs,
   writes `edit_plan.json`: the theme/problem the episode solves, the hook,
   beat order, take picks and kill list, b-roll placement, transition policy.
2. **graphics-director** — decides which moments get cards and writes their
   copy (`graphics_plan.json`). Reads `brand/engagement-playbook.md`.
3. **caption-editor** — turns the chosen takes' transcript into clean caption
   lines (text from the cleaned script, timing from whisper — never caption
   raw transcript).
4. **qc-reviewer** — checks the rendered output against the edit plan.
5. **post-production** — editing, colour grading, motion-graphics specialist.
   Use it when a render looks wrong, when cards/captions/animation need
   fixing, or when Resolve misbehaves. It measures and looks at frames rather
   than trusting settings.

Dormant survivors from v1: `instagram-copywriter`, `performance-analyst`.

## The brand system

**Source of truth is Claude Design**, not this repo. The *The Ninth Room
Design System* project (`4b8bb4a4-b234-45ed-aa84-b35ce761648b`) owns the
identity; `brand/design-system/` is a synced copy.

| Path | What it holds |
|---|---|
| `brand/design-system/tokens/*.css` | The five token files. `pipeline/design_tokens.py` reads them |
| `brand/design-system/canvases/*.dc.html` | The ground-truth canvases, including the Cyanotype kit |
| `brand/design-system/channel-assets/` | 153 production files — SVG masters, PNG, JPG, every YouTube slot at exact size |

**Never hardcode a brand value in the pipeline.** Change it in the design
system, re-pull the tokens, re-bake.

The identity is **Cyanotype**: navy ground, chalk type, one yellow moment,
cyan for anything structural. The mark is the **Archway**. Full spec:
`brand/visual-identity.md`.

### The one visual rule

> **No filled plates, and one yellow moment per frame.**

Both halves are enforced in `pipeline/overlay_kit.py`: no text container in
the kit carries a background, and `emphasize()` marks only the first emphasis
term. When bright footage threatens legibility the answer is a gradient scrim
or the chalk double-shadow — **never a box.**

### Overlays come from the design system

`pipeline/overlay_kit.py` is the runtime version of the Cyanotype kit canvas —
same geometry, same keyframes, same delays, copy parameterised. Its
`RENDERERS` dict is the authoritative list — **49 keys, 45 distinct screens**
(the overlays incl. the glass legibility layer, fourteen engagement cards,
four transitions in one component, the twelve-clip meme B-roll pack, the
three outro beats, three worked examples) plus four aliases:
`hook_title`→`hook`, `section`→`lower_third`, `quote`→`payoff`,
`end_plate`→`outro`. Read the dict, don't trust a count in prose. `pipeline/animate.py`
renders them by pausing every CSS animation and seeking `currentTime` frame by
frame in headless Chrome, so what ships is what the canvas shows.

To evolve the look: design it in Claude Design first, then re-implement the
returned canvas here. Never the other way round.

## The channel's personality

**Fun first, funny while learning, family-friendly in rating.** The audience
is general curious viewers of any age — not kids specifically, though kids
can watch everything. The humour comes from how genuinely strange the real
world is, and from the family's real reactions on camera — never from
mockery, profanity, or shock. An episode should teach something true and
make someone laugh on the way.

On-screen family — an **ensemble, no single host**: Caleb, **Alma** (his
wife) and **Sofia** (Alma's little sister, *not* Caleb's daughter). Everyone
gets bits, votes, and camera time. Never "Mom" on a card. Whisper mishears
Sofia as "Sophia"; `brand/names.json` corrects it automatically.

See `brand/voice-and-tone.md` — and note its hard rules, which the renderer
enforces: no exclamation marks and honest numbers only. **Emoji are
encouraged** — see `voice-and-tone.md` and the `hype-director` agent. (The
design system readme's "no emoji" line is overridden; Caleb, 2026-08-20.)

## The core mechanic: the curiosity gap

Every episode opens a loop the viewer *needs* closed. The hook creates the
gap; the room delivers the payoff.

> **The payoff must always land.** We open curiosity gaps honestly and close
> them completely. No bait-and-switch, no withheld answer for engagement.

And the channel's own promise on top of that: every episode owes the viewer
one **ninth-room moment** — the thing that wasn't on the map. It cannot be
manufactured. If we didn't find one, say so and let the takeaway carry it.

## Engagement is the retention strategy

Hand the viewer a job every 60–90 seconds. Thirteen engagement cards exist for
exactly this. Which card, how often, and how they fail:
`brand/engagement-playbook.md`. The graphics-director reads it; so should you.

## Where things live

| Path | What it's for |
|---|---|
| `brand/*.md` | Brief, audience, voice, visual identity, engagement playbook |
| `brand/design-system/` | Synced from Claude Design — tokens, canvases, channel assets |
| `brand/names.json` | Proper-noun corrections applied to every transcript |
| `brand/fonts/` | Bricolage + Newsreader, for Pillow (captions) |
| `brand/_retired-curated-curiosities/` | The old brand. Reference only |
| `workflows/*.md` | Cadence + platform specs (safe zones, lengths) |
| `pipeline/` | The Python pipeline (see `pipeline/__init__.py` for the module map) |
| `docs/resolve-findings.md` | Verified Resolve API ground rules |
| `docs/reference-renderers/` | Proven whisper/Pillow/ffmpeg techniques from v1 |
| `work/<slug>/` | Per-episode working dir (gitignored): footage in, deliverables out |
| `.claude/reminders.md` | Things only Caleb can do — append, don't just mention in chat |

## Rules every agent follows

1. **Accuracy is the brand.** Surprising claims must be verifiable; frame the
   unconfirmed as "claimed/disputed," never settled fact. A parent is
   fact-checking this in front of their kid.
2. **Curiosity, not sensationalism.**
3. **Respect the payoff**, and deliver a ninth room.
4. **Any place worth exploring qualifies** — there is no pillar taxonomy.
   The bar is the brand promise, not a category: something true, something
   funny, and a ninth-room moment.
5. **One voice** (`brand/voice-and-tone.md`) — the family's, collectively.
   The system says "we", never "I"; nobody on camera is "the host".
6. **Design system first.** If it isn't in the Cyanotype kit, don't invent it
   here — brief it into Claude Design and re-implement what comes back.
7. **Platform-native** (`workflows/platform-specs.md`): safe zones, lengths,
   burned-in captions for mute-first viewing.
