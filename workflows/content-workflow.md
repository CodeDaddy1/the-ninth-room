# Content Workflow

The pipeline from raw curiosity to published post. Each stage maps to an agent
in `.claude/agents/`. It's a loop: what gets published feeds what gets made next.

```
  curiosity-scout  →  content-strategist  →  ┌ youtube-scriptwriter ┐
   (find + verify)     (plan the slate)       │ instagram-copywriter │
        ▲                                      └ visual-director ─────┘
        │                                                  │
        │                                       asset-scout + fetch_assets.py
        │                                        (shot list → auto-pull b-roll)
        │                                                  │  → assemble → publish
        │                                                  ▼
        └──────────────── performance-analyst ◀───────── (the numbers)
```

## Stage 1 — Discover (curiosity-scout)
**In:** a pillar focus, recent performance learnings, or "find me topics."
**Out:** 8–10 topic candidates, each with the surprising hook, the honest
payoff, a fact-check note, and source links.
**Gate:** anything that can't be verified is cut or clearly labeled as
disputed/unsolved.

## Stage 2 — Plan (content-strategist)
**In:** the scout's candidates.
**Out:** the week's slate — which topics become what (Reel / carousel / Short /
long-form), which platform, which pillar, and the rough sequence.
**Gate:** the mix respects pillar rotation and the cadence in
`posting-cadence.md`.

## Stage 3 — Produce (parallel)
- **youtube-scriptwriter** → long-form scripts and Shorts scripts.
- **instagram-copywriter** → Reel hooks + scripts, carousel copy, captions,
  hashtags.
- **visual-director** → thumbnail concepts, carousel layout, on-screen text
  callouts.

These run in parallel off the same approved topic so every format shares one
spine but is native to its platform.

## Stage 3.5 — Source assets (asset-scout + fetch script)
Once the script is locked, **asset-scout** reads it and emits a machine-readable
shot list (`scripts/shot_list.example.json` shows the shape): every beat with its
visual, source type, search queries, AI-gen prompts, and license flags.

Then `scripts/fetch_assets.py` runs the stock shots automatically — pulling
candidate clips from Pexels/Pixabay into one folder per shot, plus a
`manifest.csv` of sources and licenses. The editor picks from the curated
candidates; AI-gen and motion-graphic shots come through as actionable TODOs.

**Gate:** any shot flagged `needs_rights_check` (recognizable people, logos,
brands, artworks) gets human license review before it goes in the cut. Every
asset must be commercial royalty-free.

## Stage 4 — Auto-assemble (`program/`)
The pipeline program turns the approved script + shot list into a **rough
cut**: TTS voiceover, normalized clips, watermark overlay. One command:
`python program/cli.py run <slug>`. See `program/README.md` for the stages.

Non-stock shots come through as brand-navy placeholder slates so timing/pacing
are right; you swap them for AI-gen or custom shots in your NLE.

## Stage 5 — Polish & QC
Bring script + copy + visuals together. Run the pre-publish checklist:
- [ ] Hook opens a real curiosity gap
- [ ] Payoff fully lands (or the mystery is honestly framed)
- [ ] Every surprising claim is sourced/verified
- [ ] On-brand voice and visuals
- [ ] Correct platform specs (`platform-specs.md`)
- [ ] Caption, hashtags, CTA present
- [ ] Title/thumbnail legible at small size

## Stage 5 — Publish
Post per the cadence and platform specs. Cross-promote: tease the YouTube
deep-dive in the IG version of the same topic.

## Stage 6 — Learn (performance-analyst)
**In:** post metrics after a set window (e.g. 48h for IG, 7–28 days for YouTube).
**Out:** what worked, what didn't, and concrete guidance for the next scout
brief — winning hook patterns, top pillars per platform, retention drop-off
points.
**Loop:** those learnings become the input to Stage 1.

## Batching
Work in weekly batches: scout and plan once, produce in a block, schedule the
week, then review. Batching keeps the voice consistent and the cadence reliable.
