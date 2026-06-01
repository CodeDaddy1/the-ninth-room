# Curated Curiosities — Project Context

This is the master context file. Read it first. It tells you what the brand is,
where everything lives, and the rules every agent follows.

## The brand in one line

**Curated Curiosities** surfaces the fascinating, overlooked, and surprising —
curated so the audience gets the wonder without the digging.

## Platforms

- **Instagram** — Reels, carousels, and Stories. Discovery + daily habit.
- **YouTube** — long-form (6–12 min) and Shorts. Depth + search longevity.

Instagram is the top of the funnel; YouTube is where curiosity goes deep.

## The core mechanic: the curiosity gap

Every piece of content opens a loop the viewer *needs* closed. The hook creates
the gap; the content delivers the payoff. The non-negotiable rule:

> **The payoff must always land.** We open curiosity gaps honestly and we close
> them completely. No bait-and-switch, no withheld answer for engagement, no
> "the truth will shock you" that resolves into nothing. Clickbait that doesn't
> deliver is the fastest way to kill a curiosity brand.

## Where things live

| File | What it's for |
|---|---|
| `brand/brand-brief.md` | Mission, positioning, the curiosity thesis |
| `brand/audience.md` | Who we're making this for |
| `brand/content-pillars.md` | The recurring themes all content fits into |
| `brand/voice-and-tone.md` | How the brand sounds and writes |
| `brand/visual-identity.md` | Look, color, typography, thumbnail rules |
| `workflows/content-workflow.md` | Idea → publish pipeline |
| `workflows/posting-cadence.md` | What posts when, on which platform |
| `workflows/platform-specs.md` | Format, dimension, and length cheat sheet |

## The agent team and how they hand off

The agents live in `.claude/agents/` and run as a pipeline:

1. **curiosity-scout** — finds and fact-checks curiosity-worthy topics
2. **content-strategist** — turns raw topics into a planned content slate
3. **youtube-scriptwriter** — writes long-form and Shorts scripts
4. **instagram-copywriter** — writes Reels hooks, captions, carousels, hashtags
5. **visual-director** — thumbnail and carousel concepts, on-screen text
6. **performance-analyst** — reads the numbers and feeds learnings back to step 1

Scout → Strategist → (Scriptwriter + Copywriter + Visual-director) → publish →
Analyst → back to Scout. It's a loop, not a line.

## Rules every agent follows

1. **Accuracy is the brand.** A curiosity brand that gets facts wrong loses
   trust permanently. Every surprising claim must be verifiable. Cite sources.
   If something can't be confirmed, frame it as "claimed/disputed," never as
   settled fact.
2. **Curiosity, not sensationalism.** We pique interest with genuine substance,
   not manufactured drama or fear.
3. **Respect the payoff.** See the core mechanic above.
4. **Stay on-pillar.** If a topic doesn't fit a content pillar, flag it rather
   than forcing it.
5. **One voice.** Everything reads like it came from the same curious, warm,
   smart narrator. See `brand/voice-and-tone.md`.
6. **Platform-native.** Don't post a YouTube script to Instagram verbatim.
   Adapt to each platform's specs and behavior.
