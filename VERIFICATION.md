# Phase 2 — Subagent verification

Manual smoke test for the seven `.claude/agents/*.md` subagents. Run these in
Claude Code with this project's directory open. Marginal cost = **$0** (your
existing subscription). Total time end-to-end: **~30 min**.

## Pre-flight

1. Open Claude Code in `~/Projects/curated-curiosities`.
2. Confirm subagents are visible: type `/` and you should see
   `/curiosity-scout`, `/content-strategist`, `/youtube-scriptwriter`,
   `/instagram-copywriter`, `/asset-scout`, `/visual-director`,
   `/performance-analyst`.

If any are missing, the project's `.claude/agents/` files haven't loaded —
restart Claude Code from the project directory.

## Smoke matrix

After each step, run the validator and confirm green:

```
python worker/cli.py validate <slug>           # per-video
python worker/cli.py validate --planning       # planning files
```

### 1. curiosity-scout
**Run:** `/curiosity-scout pillar=human_strange`
**Expect:** `work/_planning/topics-YYYY-MM-DD.json` written; 8–10 topics; every
topic has at least one `sources` URL; conversational table in chat.
**Validate:** `python worker/cli.py validate --planning` → ✓ for `topics-*.json`.

### 2. content-strategist
**Run:** `/content-strategist topics_file=work/_planning/topics-YYYY-MM-DD.json week=2026-W23`
**Expect:** `work/_planning/slate-2026-W23.json` written; 5–8 slots; flagship
slug identified; pillar rotation hits ≥4 different pillars.
**Validate:** `python worker/cli.py validate --planning` → ✓ for `slate-*.json`.

### 3. youtube-scriptwriter
**Run:** `/youtube-scriptwriter slug=wow-signal-explained topic="The 1977 Wow! signal" format=long`
**Expect:** `work/wow-signal-explained/script.md` written with `## Title options`,
`## Script` (with `[M:SS]` timecodes), `## Description`, `## Thumbnail concept`.
**Validate:** open the file; confirm timecoded structure. (No JSON to validate.)

### 4. asset-scout
**Run:** `/asset-scout slug=wow-signal-explained`
**Expect:** `work/wow-signal-explained/shot_list.json` written; one shot per
script beat; queries for stock shots; fallbacks everywhere.
**Validate:** `python worker/cli.py validate wow-signal-explained` → ✓ for `shot_list.json`.

### 5. visual-director
**Run:** `/visual-director slug=wow-signal-explained`
**Expect:** `work/wow-signal-explained/visuals.json` with thumbnail, on-screen
text, consistency check all true.
**Validate:** `python worker/cli.py validate wow-signal-explained` → ✓ for `visuals.json`.

### 6. instagram-copywriter — script mode
**Run:** `/instagram-copywriter slug=wow-signal-reel topic="The 1977 Wow! signal" format=reel mode=script`
**Expect:** `work/wow-signal-reel/script.md` with `## Hook options`, `## Script`,
`## Caption (draft)`, `## Hashtags (draft)`, `## Thumbnail concept`.

### 7. instagram-copywriter — tray mode
**Pre:** assume `rough_cut.mp4` exists for `wow-signal-reel` (real or stub).
**Run:** `/instagram-copywriter slug=wow-signal-reel platform=instagram_reel mode=tray`
**Expect:** `work/wow-signal-reel/tray/instagram_reel.json` written; caption ≤ 2200
chars; hashtags array; thumbnail_brief.
**Validate:** `python worker/cli.py validate wow-signal-reel` → ✓ for `tray/instagram_reel.json`.

### 8. performance-analyst (cold start)
**Run:** `python worker/cli.py analyst-weekly` — this stages an empty metrics
file and prints the slash command. Then run it:
```
/performance-analyst week=YYYY-Www
```
**Expect:** `work/_planning/analyst-YYYY-Www.md` with the five required H2
sections; "insufficient data" path (cold start).
**Validate:** `python worker/cli.py validate --planning` → ✓ for `analyst-*.md`.

## Headless verification

The Monday-morning launchd job will call:
```bash
claude -p "/performance-analyst week=YYYY-Www"
```
from `~/Projects/curated-curiosities`. To confirm headless mode can see the
project subagents:
```bash
cd ~/Projects/curated-curiosities
claude -p "/curiosity-scout pillar=human_strange count=3"
```
This should produce a `work/_planning/topics-YYYY-MM-DD.json` file with 3
entries and exit cleanly. If headless mode can't see the subagents, fall back
to clicking a Monday-morning macOS notification that triggers an interactive
run (Phase 7.5 will wire this).

## Pass criteria

Phase 2 is **done** when:
- Each of the seven agents writes its canonical file on the first try.
- The validator returns ✓ on every output.
- `claude -p` headless produces a valid file for at least one agent (the
  analyst, since that's the one with a scheduled headless run).
- Cost shows **$0** on the Anthropic API console — only Claude Code
  subscription usage.

## Common fixes

| Symptom | Fix |
|---|---|
| Agent writes to wrong path | Re-read the agent .md — pin the canonical path in the call args |
| JSON validation fails on enum | Check the schema's allowed values list in `worker/orchestrator/schemas.py` |
| Subagent not visible at `/` | Restart Claude Code from `~/Projects/curated-curiosities` so it picks up `.claude/agents/` |
| `claude -p` headless errors | Verify `~/.claude/.credentials.json` exists and you're logged in interactively first |
