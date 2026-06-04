---
description: Write a YouTube script, auto-loading the scout's research → work/<slug>/script.md
argument-hint: "slug=<slug> topic=\"<topic>\" [format=long|short]"
---

Write the YouTube script for Curated Curiosities, automatically pulling in the
curiosity-scout's verified research so the script matches the topic that was
actually researched — not a fresh take on the bare title.

Arguments: $ARGUMENTS
Required: `slug` and `topic`. Optional: `format` (default `long`).
If `slug` or `topic` is missing, ask — do not invent one.

Do these steps **in order**. Do not skip straight to the subagent.

**Step 1 — Resolve the scout research yourself** (use your own Read/Glob/Bash
tools; the subagent can't glob):
1. If any slate exists, read the most recent `work/_planning/slate-*.json` and
   find the slot whose `slug` equals this slug. Note its `topic` and
   `hook_angle` — this confirms the canonical topic string.
2. Search `work/_planning/topics-*.json`, **newest file first**, for the entry
   whose `topic` matches this video's topic — case-insensitive, ignoring
   punctuation and minor truncation. Prefer an exact match; if several plausibly
   match, pick the closest; if it's genuinely ambiguous, list the candidates and
   ask which one.
3. From the matched entry, extract: `hook`, `payoff`, `verified`,
   `fact_check_notes`, `sources`, `best_format`.

**Step 2 — Branch on what you found:**
- **Match found** → invoke the **youtube-scriptwriter** subagent and pass the
  resolved research inline: the verified `hook`, the `payoff` (the script MUST
  land this exact payoff), the `fact_check_notes` (keep every claim aligned),
  and the `sources` (reuse these; only add new ones if you verify them). Also
  give it the path of the topics file so it can re-read if needed.
- **No match found** → print this warning verbatim, then proceed with the title
  only:
  `⚠ No scout research found for "<topic>" in work/_planning/topics-*.json — writing from the title alone. Run /curiosity-scout first if you want verified sourcing.`

**Step 3 —** Have the subagent follow its full contract and **Write**
`work/<slug>/script.md` using the required literal headings (the watcher and
asset-scout both depend on them). Post a 2–3 sentence summary: topic, format,
runtime estimate, the file path, and **whether scout research was loaded** (and
from which file) or not.
