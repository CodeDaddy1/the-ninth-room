---
description: Turn an approved script into a shot list → work/<slug>/shot_list.json
argument-hint: "slug=<slug>"
---

Use the **asset-scout** subagent to build the shot list.

Arguments: $ARGUMENTS

Required: `slug`. If missing, ask first. Read `work/<slug>/script.md`, pull every
`[B-ROLL]` / `[ON-SCREEN]` / `[GRAPHIC]` cue, and **Write**
`work/<slug>/shot_list.json` per the agent's schema — ready-to-run stock search
queries, AI-generation prompts where stock won't work, and the brand licensing
rules. Lead the summary with the file path.
