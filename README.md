# Curated Curiosities

A social-media brand that brings **curated content that piques curiosity** —
mainly on **Instagram** and **YouTube**. This repo holds the brand foundation,
the production workflows, and a team of AI subagents that run the content
pipeline.

## What's here

```
curated-curiosities/
├── CLAUDE.md                  ← start here: master context for the whole project
├── README.md                  ← you are here
├── brand/                     ← who the brand is
│   ├── brand-brief.md
│   ├── audience.md
│   ├── content-pillars.md
│   ├── voice-and-tone.md
│   └── visual-identity.md
├── workflows/                 ← how content gets made
│   ├── content-workflow.md
│   ├── posting-cadence.md
│   └── platform-specs.md
└── .claude/
    └── agents/                ← the AI team
        ├── curiosity-scout.md
        ├── content-strategist.md
        ├── youtube-scriptwriter.md
        ├── instagram-copywriter.md
        ├── visual-director.md
        └── performance-analyst.md
```

## How to use the agents

The files in `.claude/agents/` are subagent definitions. Each has a `name`,
a `description` that tells Claude when to reach for it, and a system prompt
that gives it its role and output format.

A typical week:

1. Ask **curiosity-scout** to surface 8–10 fact-checked topic candidates.
2. Hand those to **content-strategist** to build the week's slate across
   pillars and platforms.
3. For each piece, route to **youtube-scriptwriter** and/or
   **instagram-copywriter**, with **visual-director** for thumbnails/carousels.
4. After things publish, give **performance-analyst** the numbers; its
   learnings become the next brief for the scout.

## Getting started from scratch

1. Read `CLAUDE.md`.
2. Fill in any `[BRACKETED]` placeholders in the brand docs — these are the
   decisions only you can make (handles, exact palette, founder POV, etc.).
3. Run the scout for your first batch of topics and start the loop.

The brand docs are written as living documents — update them as the brand's
voice and audience sharpen with real data.
