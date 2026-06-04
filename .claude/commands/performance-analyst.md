---
description: Analyze weekly metrics into guidance → work/_planning/analyst-YYYY-Www.md
argument-hint: "[week=YYYY-Www]"
---

Use the **performance-analyst** subagent.

Arguments (may be empty): $ARGUMENTS

Parse `week=` (ISO year-week; default the current week). Read
`work/_planning/metrics-<week>.json`, then **Write**
`work/_planning/analyst-<week>.md` per the agent's contract — concrete learnings
that feed the next curiosity-scout cycle. Lead the summary with the file path.
