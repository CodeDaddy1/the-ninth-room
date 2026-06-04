---
description: Turn scouted topics into a weekly slate → work/_planning/slate-YYYY-Www.json
argument-hint: "[topics=<topics-file>] [week=YYYY-Www]"
---

Use the **content-strategist** subagent to build the content slate.

Arguments (may be empty): $ARGUMENTS

Parse `topics=` (path to a `topics-*.json`; if omitted, read the most recent one
in `work/_planning/`) and `week=` (ISO year-week like `2026-W23`; if omitted,
infer from today). Follow the agent's contract: assign a url-safe `slug` per
slot, choose format/platform/day, set the `flagship_slug`, route each slot to
`youtube-scriptwriter` or `instagram-copywriter`, and **Write**
`work/_planning/slate-<week>.json`. Lead the summary with the file path.
