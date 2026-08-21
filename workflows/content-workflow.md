# Content Workflow — The Ninth Room

How a room becomes an episode. Every stage maps to something real: an agent in
`.claude/agents/`, a desk in the Edit Room, or a pipeline command.

> This replaced the v1 workflow (curiosity-scout → content-strategist →
> youtube-scriptwriter → visual-director), which described a stock-footage
> assembly line that no longer exists. None of those agents remain.

```
  scout ──▶ shoot ──▶ ingest ──▶ story loop ──▶ assemble ──▶ review ──▶ master
   ideas    footage   takes +     3 pitches      timeline     shots +    render
   tab      dropped   transcript  → approval     + cards      captions   + grade
     ▲                                                           │
     └────────────────── what performed ◀───────────────────────┘
```

Everything below is slug-scoped: one visit, one `work/<slug>/`.

## Stage 0 — Scout (channel level)
**Command:** "scout ideas"
**Agent:** `scout`
**Out:** `work/_scout/ideas.json` — candidate rooms with the surprising hook,
the honest payoff, a fact-check note, and sources.
**Where Caleb works:** the Ideas tab. Save / develop / dismiss; the next round
honours those verdicts.
**Gate:** anything unverifiable is cut or clearly labelled disputed/unsolved.
A room with no candidate ninth-room moment is a weak episode — flag it.

## Stage 1 — Shoot
Caleb shoots the room: talking-head takes (flubs and retakes are fine and
expected), plus b-roll of the cases, the labels, and the family reacting.

**Shoot for the cards.** The engagement plan is not something to bolt on
later — a `countdown` card needs a reveal to cut to, a `vote` needs the
family actually disagreeing on camera. See `brand/engagement-playbook.md`
before the visit, not after.

## Stage 2 — Ingest
**Command:** `/usr/bin/python3 -m pipeline.cli ingest <slug>` (or drop files
straight onto the Edit Room page — photos become 6s b-roll clips).
**Out:** normalized clips, whisper transcripts with word timing, a take
analysis, and a b-roll catalog.
Proper nouns are corrected against `brand/names.json` immediately after
whisper runs — Sofia, not Sophia.

## Stage 3 — Story loop
**Command:** "pitch stories for <slug>" → `story-designer` writes
`stories.json` with **three** directions.
**Where Caleb works:** the Story tab — approve or redirect
(`story_feedback.json`).
**Then:** "write the edit plan for <slug>".
**Gate (enforced):** no `edit_plan.json` without an approving round. The agent
contract forbids skipping the pitch.

**Out:** `edit_plan.json` — theme, hook, beat order, take picks and kill list,
b-roll placement, transition policy.

## Stage 4 — Graphics + captions
**Agents:** `graphics-director` → `graphics_plan.json`,
`caption-editor` → `captions.json`.

The graphics-director reads `brand/engagement-playbook.md` and places a card
every 60–90 seconds. Copy follows `brand/voice-and-tone.md` — emoji
encouraged, no exclamation marks, honest numbers, one yellow moment per card.

The caption-editor takes text from the *cleaned script* and timing from
whisper. **Never caption the raw transcript.**

## Stage 5 — Assemble
**Command:** "assemble <slug>" — build-timeline + assets + proxies.
Cards bake to ProRes 4444 alpha .movs; the FCPXML is generated and imported
into Resolve through the Lua bridge.

## Stage 6 — Review
**Where Caleb works:** the Shots desk, in story order. Entries may carry
`"needs": ["broll","sfx","cards"]`; route them in the fixer round —
broll → story/b-roll pass, sfx → `sound-designer`, cards →
`graphics-director`.

The **Overlays** and **Captions** desks edit card copy and caption text live.
Exported overlay .movs are **immutable** — a change writes `_v2`, never
replaces the file, because mutating imported media makes Resolve show Media
Offline.

## Stage 7 — Grade + master
**Command:** `cli grade <slug>` grades the live Resolve timeline, then render.
**Out:** `work/<slug>/deliverables/`.

## Pre-publish checklist

- [ ] Hook opens a real curiosity gap, and the payoff lands
- [ ] The episode delivers a **ninth-room moment** — or honestly says it didn't
- [ ] Every surprising claim is sourced; disputed things are labelled
- [ ] At least one engagement card, spaced 60–90s, all answerable on screen
- [ ] Exactly one takeaway, serif italic, no accent word
- [ ] Emoji vocabulary small and consistent; no exclamation marks; no invented numbers
- [ ] One yellow moment per frame, no filled plates
- [ ] Names correct — Alma, Sofia; never "Mom"
- [ ] Burned captions legible over the brightest footage in the episode
- [ ] Platform specs met (`platform-specs.md`)

## Stage 8 — Learn
`performance-analyst` (dormant) reads retention and comments. The signal that
matters most for this channel is **comment composition**: how many answered
the engagement card versus only praised the video.

## Batching
Shoot a room, then post-produce it in one block. Two rooms in the pipe at once
is fine; three means the story loop starts blurring between them.
