---
description: Write IG script (mode=script, auto-loads scout research) or prep the publish tray (mode=tray)
argument-hint: "mode=script slug=<slug> topic=\"<topic>\" format=reel|carousel  ·  mode=tray slug=<slug> platform=instagram_reel|instagram_carousel|instagram_story"
---

Use the **instagram-copywriter** subagent.

Arguments: $ARGUMENTS

Required: `mode` — either `script` or `tray`. If `mode` or a required arg for the
chosen mode is missing, ask before proceeding.

### mode=script — write the IG script for a new video
Needs `slug`, `topic`, `format` (`reel`|`carousel`), optional `sources`.

Before writing, **auto-load the scout's research** (do this yourself with
Read/Glob/Bash — the subagent can't glob):
1. Search `work/_planning/topics-*.json`, **newest first**, for the entry whose
   `topic` matches this video's topic (case-insensitive, ignoring punctuation
   and minor truncation). Prefer exact; if ambiguous, list candidates and ask.
2. **Match found** → pass the entry's `hook`, `payoff`, `fact_check_notes`, and
   `sources` to the subagent; the script MUST land that exact payoff and reuse
   those sources (add new ones only if verified).
   **No match** → print verbatim and proceed with the title only:
   `⚠ No scout research found for "<topic>" in work/_planning/topics-*.json — writing from the title alone. Run /curiosity-scout first if you want verified sourcing.`

Writes `work/<slug>/script.md` (same canonical path the youtube-scriptwriter
uses, so the asset-scout can read it). Report whether scout research was loaded.

### mode=tray — prep the publish-ready package after the rough cut exists
Needs `slug`, `platform` (`instagram_reel`|`instagram_carousel`|
`instagram_story`). Reads `work/<slug>/script.md` and `work/<slug>/visuals.json`
(if present), writes `work/<slug>/tray/<platform>.json`. (No scout lookup needed
here — the script already carries the research.)
