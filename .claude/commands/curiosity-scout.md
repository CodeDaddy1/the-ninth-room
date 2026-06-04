---
description: Find & fact-check curiosity topics → work/_planning/topics-YYYY-MM-DD.json
argument-hint: "[pillar=<pillar>] [count=<n>] [brief=<analyst-file>]"
---

Use the **curiosity-scout** subagent to scout topics for Curated Curiosities.

Arguments (may be empty): $ARGUMENTS

Parse any `pillar=`, `count=`, and `brief=` hints from the arguments. Follow the
agent's contract exactly: fact-check every surprising claim with a source, map
each topic to one of the six content pillars, and **Write** the result to
`work/_planning/topics-YYYY-MM-DD.json` (today's date). Produce 8–10 topics
unless `count=` says otherwise. Then post the short scannable summary in chat,
leading with the file path you wrote to.
