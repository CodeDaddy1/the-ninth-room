# Curated Curiosities — Application Ultra Plan

> Single source of truth for what we're building, in what order, and what
> "done" means at each step. Authored 2026-06-01.
>
> **Revised 2026-06-01** — pivot to $0/mo: removed Railway, removed
> Anthropic-API orchestrator (Claude Code subagents instead), removed TTS
> (Caleb records voiceover by hand). Free-tier Vercel + Supabase retained.

---

## 1. What we're building (one paragraph)

A personal-use content production system for the Curated Curiosities brand,
running at **$0/mo**. A **Next.js dashboard** on Vercel (hobby tier) talks to
**Supabase** (free tier — state + auth + thumb storage) and a **local Python
worker** that runs on your Mac via launchd. The worker drives the existing
`program/` pipeline (`fetch_assets` → assemble), with the seven
`.claude/agents/*.md` invoked as **Claude Code subagents** — no Anthropic API
integration code, no per-token bill; orchestration cost rides on your existing
Claude Code subscription. **Voiceover is Caleb-recorded** (voice on, face off)
— no TTS in the stack. The output is a polished rough cut + a per-platform
"ready tray" (caption, hashtags, thumbnail brief) that syncs to your phone via
iCloud Drive for **manual posting**. After publish, you type the numbers into a
manual entry form; the performance-analyst subagent rolls a weekly debrief
(triggered by a launchd-scheduled `claude -p` headless run) that feeds next
week's scout brief.

---

## 2. Locked architecture decisions

These are **not up for re-litigation** during phase work. Changes require
re-opening this plan.

| Decision | Choice | Why |
|---|---|---|
| Surface | Next.js dashboard + local Python worker | Best ergonomics for in-flight editing; Python stays the engine |
| Hosting | Vercel hobby + Supabase free + local Mac | $0/mo; Mac always-on enough for personal cadence |
| AI orchestrator | **Claude Code subagents** | `.claude/agents/*.md` ARE the runtime; invoked interactively from CLI, headless `claude -p` for cron. Zero marginal cost. |
| Host POV / Voice | Faceless visual + **Caleb-recorded VO** | Voice on, face off. Better quality than TTS, zero cost, distinctive brand voice. |
| Publish layer | Draft + push-to-device (iCloud Drive) | No Meta/YouTube app review tax; zero auto-publish risk |
| Creative additions (v1) | Music auto-duck only | Captions + AI clip-gen explicitly deferred |
| Metrics input | Manual form in dashboard | No platform APIs; honest and 30s/post |
| State store | Supabase free (Postgres + Auth + Realtime + tiny Storage) | Same patterns as other projects; well under free-tier limits |
| Asset storage | **Local disk** for working files + final mp4; Supabase Storage for thumbnails only | Mp4s never touch the cloud (egress = $); thumbs are tiny (~100KB) |
| Worker process | Python script on Mac, launched on-demand + launchd for scheduled jobs | No Railway; no $5/mo |
| Repo | `~/Projects/curated-curiosities`, git, GitHub private | Move out of Downloads in Phase 0 |
| Auth | Supabase Auth, single user (Caleb) | Personal use, but RLS still on |

### Hard requirements that shape design

1. **`.claude/agents/*.md` are the prompt source AND the runtime.** They run as
   Claude Code subagents — interactively when you're in the CLI, or via
   `claude -p "/agent-name ..."` headless from launchd. There is no Python
   code that calls the Anthropic API directly.
2. **Per-video work dirs remain the file-system source of truth.** Supabase
   mirrors state and metadata, not the files themselves. Mp4s never leave
   local disk.
3. **Every stage is idempotent.** Re-run any single stage without redoing
   the others (the `program/` README already commits to this — preserve it).
4. **Voice on, face off.** You record the VO into `voiceover.mp3` in the work
   dir; the existing `voiceover.py` manual mode is the only mode used. No
   ElevenLabs, no OpenAI TTS, no Piper.
5. **No claim ships unsourced.** Curiosity-scout writes a `sources` array per
   topic; scriptwriter must reference it; QC won't approve without it.
6. **$0/mo target is binding.** Adding any paid line item requires re-opening
   this plan with a monetization-trigger justification.

---

## 3. Phase map (v1 = Phases 0–7.5)

```
Phase 0  Foundation & infra        — repo, git, Vercel hobby + Supabase free; local launchd plist
Phase 1  Supabase schema           — videos, shots, assets, ready_tray, metrics, music_tracks, briefs
Phase 2  Subagent invocation shim  — work-dir conventions; dashboard surfaces the next /slash command;
                                       optional `claude -p` headless for the analyst weekly run
Phase 3  Dashboard MVP (read-only) — auth, video list, drill-down, "new video" form
Phase 4  Local worker + file watcher — Python process that watches work dirs + Supabase queue,
                                       runs fetch/assemble stages on demand or from launchd
Phase 5  Dashboard editing         — script/shot-list editors, asset picker, rough-cut preview
Phase 6  Music auto-duck           — licensed-track picker + ffmpeg sidechain
Phase 7  Ready tray + push-to-device — per-platform copy, thumbnail brief, iCloud sync
Phase 7.5 Metrics + analyst loop   — manual entry, weekly headless analyst run → next scout brief
─── v1 ships here ───
Phase 8  Captions (DEFERRED)       — Whisper → styled SRT → ffmpeg burn-in (first $/mo line if added)
Phase 9  AI clip-gen (DEFERRED)    — fal.ai aggregator (also paid; gated on monetization)
```

---

## 4. Per-phase detail

### Phase 0 — Foundation & infra

**Build:**
- Move `~/Downloads/curated-curiosities` → `~/Projects/curated-curiosities`. Verify nothing in Downloads relies on it.
- `git init`, `.gitignore` (work/, .env, *.mp3, *.mp4, *.wav, .DS_Store, node_modules), initial commit, push to `codedaddy1` GitHub private repo.
- Create Supabase **free-tier** project `curated-curiosities` (separate from LumaIQ/RevStor/Trip Theory). Save ref + URL + keys to memory.
- Create Vercel **hobby-tier** project linked to GitHub repo. Default subdomain is fine.
- Scaffold dirs: `dashboard/` (Next.js 16 App Router), `worker/` (move existing `program/` here, renamed), keep `brand/`, `workflows/`, `.claude/agents/` at repo root.
- `.env.example` listing every key (PEXELS_API_KEY, PIXABAY_API_KEY, SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_KEY, WORK_DIR). Sync to Vercel via `vercel env`.
- `scripts/apply-migration.mjs` copied from Trip Theory pattern (MCP can't always reach a fresh project).
- **launchd plists** in `infra/launchd/`:
  - `curated.worker.plist` — runs `python worker/cli.py daemon` on login, restarts on crash.
  - `curated.analyst.plist` — runs `python worker/cli.py analyst-weekly` every Monday 09:00 (calls `claude -p "/performance-analyst weekly"` headless).
  - Installed via `make install-launchd` to `~/Library/LaunchAgents/`.

**DoD:**
- [ ] Repo at `~/Projects/curated-curiosities`, pushed, CI green (or skipped — no CI required for personal).
- [ ] Vercel preview deploy of empty dashboard works at a real URL.
- [ ] Supabase project responds to `select 1` via `apply-migration.mjs`.
- [ ] All env keys present in Vercel + local `.env`.
- [ ] Worker launchd plist loaded; `launchctl list | grep curated.worker` shows it; killing the process auto-restarts.

**Risks:**
- Author email — must pass `--author "Caleb Pham <codedaddy1@outlook.com>"` per commit (memory: `feedback_git_author`).
- Supabase free tier **pauses projects after ~7 days of inactivity**. First request unpauses but adds ~30s latency. Acceptable for personal cadence; document so we don't chase it as a bug.
- launchd plist syntax is finicky — verify with `plutil -lint` and `launchctl bootstrap gui/$(id -u) <plist>` rather than the deprecated `load`.

**Subagent:** general-purpose for the file/dir work; vercel:bootstrap to sanity-check Vercel link.

---

### Phase 1 — Supabase schema

**Tables (singular schema, no multi-tenant):**

```
videos
  id              uuid pk
  slug            text unique
  topic           text                  -- the seed idea
  pillar          text                  -- one of the six
  platform_targets text[]               -- ['youtube_long','instagram_reel',...]
  state           text                  -- queued|scripting|shots|fetching|vo|assembling|ready|published
  script_md       text                  -- mirror of script.md
  shot_list_json  jsonb                 -- mirror of shot_list.json
  selections_json jsonb                 -- which candidate per shot
  rough_cut_url   text                  -- Supabase Storage signed URL
  created_at, updated_at timestamptz

video_assets       -- per-shot candidate metadata; files live on Railway disk
  id, video_id fk, shot_id text, candidate_idx int, provider text,
  file_path text, license text, source_page text, picked bool

ready_tray         -- one row per (video, platform)
  id, video_id fk, platform text, caption text, hashtags text[],
  thumbnail_brief text, exported_at, pushed_at, posted_at

metrics            -- manual entries
  id, video_id fk, platform text, window text ('48h','7d','28d'),
  views int, likes int, comments int, saves int, shares int,
  watch_time_seconds int, retention_pct numeric, captured_at

music_tracks       -- your licensed library, registered on the worker
  id, label text, file_path text, license_source text, bpm int, mood text

analyst_briefs     -- weekly debriefs
  id, week_start date, summary_md text, scout_brief_md text, created_at

events             -- worker telemetry, for debugging
  id, video_id fk, stage text, level text, payload jsonb, created_at
```

**Migrations:** versioned in `supabase/migrations/`, applied via
`scripts/apply-migration.mjs`. RLS on; single-user policy keyed to Caleb's
auth.uid().

**DoD:**
- [ ] All migrations apply cleanly to a fresh Supabase project.
- [ ] RLS verified: anon role can't read; authenticated Caleb can CRUD.
- [ ] `select` from each table from the worker (service role) works.
- [ ] `generate_typescript_types` produces a `dashboard/lib/db.types.ts` that compiles.

**Risks:**
- `feedback_partial_migrations` memory — never use `create table if not exists` for migrations; they hide column drift. Use raw `create table` per migration file.
- `feedback_rls_restrictive_for_role_blocks` — if we add any block-role policies later, mark them `AS RESTRICTIVE`.

**Subagent:** supabase skill for schema design; general-purpose to run migrations.

---

### Phase 2 — Subagent invocation shim (no Anthropic API code)

**Build:**
- **Verify the seven `.claude/agents/*.md` files work as Claude Code subagents.** Run each one manually in the CLI against a real work dir and confirm:
  - It produces the structured output described below.
  - It writes its output to the correct file in the work dir (or returns it for the main session to write).
  - Polish prompts where needed so output is reliably parseable.
- **Work-dir output conventions** — each agent reads/writes specific files; the dashboard advances state by watching for them:
  - `curiosity-scout` → writes `topics.json` (array of `{topic, hook, payoff, sources[], pillar, fact_check_notes}`).
  - `content-strategist` → writes `slate.json` (`{week_start, slots[{video_slug, topic, pillar, platform, format}]}`).
  - `youtube-scriptwriter` / `instagram-copywriter` → writes `script.md`.
  - `asset-scout` → writes `shot_list.json` (validated against `scripts/shot_list.example.json` shape).
  - `visual-director` → writes `visuals.json` (`{thumbnail_brief, carousel_layout, on_screen_text[]}`).
  - `performance-analyst` → writes `analyst_brief_<week>.md`.
- **Dashboard "next action" surface** — for each video, the drill-down view shows the exact slash command for the current stage with the work dir path baked in. You click "copy", paste into Claude Code, run. The file watcher (Phase 4) auto-detects the output and advances state.
- **Headless analyst** — `worker/cli.py analyst-weekly` shells out to `claude -p "/performance-analyst weekly --work-dir <path>"` and parses the output file. Used by the launchd Monday-morning job.
- **Schema validation** — `worker/orchestrator/schemas.py` has Python validators for `topics.json`, `slate.json`, `shot_list.json`, `visuals.json`. Any agent output that fails validation is flagged in the dashboard with the error, not silently advanced.

**DoD:**
- [ ] Manually running `/curiosity-scout` in Claude Code with a pillar focus produces a valid `topics.json` in the right location.
- [ ] Same for the other six agents on a single end-to-end test video.
- [ ] All seven outputs round-trip cleanly through the schema validators.
- [ ] `claude -p "/performance-analyst weekly"` runs headless and produces a brief without interactive prompts.
- [ ] Total marginal cost from this phase: **$0** — confirmed by the Anthropic console showing only Claude Code subscription usage, no API spend.

**Risks:**
- **Headless `claude -p` auth/behavior** — verify it inherits your Claude Code login and respects the subagent definitions in `.claude/agents/`. If headless mode doesn't see project subagents, fallback is: launch the weekly analyst as an interactive run on Monday morning (you click a notification).
- Agent prompts may need iteration to produce reliable structured output. Budget a real evening for prompt-tuning each one.
- If Claude Code's subagent invocation syntax changes, the shim breaks. Pin the workflow to a known-good CLI version.

**Subagent:** claude-code-guide for current subagent + headless CLI behavior; general-purpose for the shim + validators.

---

### Phase 3 — Dashboard MVP (read-only)

**Build:**
- Next.js 16 App Router, Cache Components on by default. shadcn/ui for primitives.
- Tailwind theme uses brand tokens: `--navy: #0E1B2C; --amber: #E8A33D; --cream: #F4EFE6; --slate: #6B7C93`.
- Supabase Auth via `@supabase/ssr`, single allow-list of Caleb's email; everyone else bounces.
- Routes:
  - `/` — videos table (slug, state, pillar, platforms, updated_at)
  - `/videos/[slug]` — drill-down: script preview, shot list (read-only), asset thumbnails, rough-cut player when ready, ready tray; **"Next action" card with a copy-to-clipboard slash command** for the current stage.
  - `/videos/new` — form: topic + pillar + platform targets → creates a `videos` row + scaffolds the work dir on disk via the local worker.
  - `/queue` — live worker status (Realtime channel on `events`)
  - `/analyst` — list of weekly briefs
- **Worker exposes a small FastAPI surface on `http://localhost:8787`** (NOT public): `POST /jobs/topic`, `POST /jobs/run/{slug}`, `GET /health`. The Vercel-hosted dashboard talks to it via a Cloudflare Tunnel or **(simpler)** by running the dashboard on `localhost:3000` too. Decision deferred to Phase 4; for v1 read-only, the dashboard doesn't need the worker yet — it reads from Supabase only.

**DoD:**
- [ ] Login works; non-Caleb email is denied.
- [ ] "New video" form creates a `videos` row.
- [ ] Drill-down renders script Markdown (when present), shot list as a table, and any persisted state.
- [ ] "Next action" card shows the correct slash command per stage with the work dir path embedded.
- [ ] Realtime `events` stream surfaces stage transitions in `/queue` without polling.

**Risks:**
- Cache Components + Realtime subscriptions need a client boundary — don't accidentally cache the live feed (`vercel:next-cache-components` skill).
- The dashboard background must use `bg-[var(--card)]` for overlay panels — `--surface-*` tokens are translucent (memory: `feedback_lumaiq_drawer_bg`).
- **Vercel-hosted dashboard ↔ localhost worker bridge.** If we want the Vercel URL to trigger local jobs, we need a tunnel. Simplest is: also run the dashboard locally (`pnpm dev`) when triggering, and keep the Vercel deploy as read-only-ish. Pick a path in Phase 4.

**Subagent:** vercel:nextjs for App Router + Cache Components; vercel:shadcn for components; vercel:auth for the SSR pattern.

---

### Phase 4 — Local worker + file watcher

**Build:**
- `jobs` table in Supabase: `id, type, payload jsonb, status, video_id, started_at, ended_at, error`.
- **Local Python worker daemon** (`worker/cli.py daemon`) — long-running process started by launchd:
  - Polls `jobs` table every 5s via Supabase service-role key.
  - Watches each in-flight video's work dir for the file outputs Phase 2 defined; transitions state when they appear.
  - Runs `fetch_assets`, `assemble`, and the future music-duck stage as job types.
  - **No `voiceover` job** — that stage just waits for you to record `voiceover.mp3` into the work dir, then the watcher advances state.
  - **No subagent jobs in v1** — the dashboard surfaces the slash command, you run it in Claude Code, the watcher picks up the output. (The Monday analyst is the one exception, via `claude -p`.)
- Worker also runs a tiny FastAPI server on `localhost:8787` so the dashboard (when running locally) can trigger jobs without round-tripping through Supabase.
- Per-video work dir lives at `~/Projects/curated-curiosities/work/<slug>/` — gitignored but mounted in the runtime.

**DoD:**
- [ ] launchd starts the worker on login; killing it via `kill -9` triggers auto-restart.
- [ ] Submitting a `topic` from the dashboard creates the work dir + first slash-command CTA.
- [ ] After you run `/curiosity-scout` in Claude Code, the watcher detects `topics.json` and advances state to `scripting`.
- [ ] After you drop a recorded `voiceover.mp3` in the work dir, the watcher advances state to `ready_to_assemble`.
- [ ] Clicking "Assemble" enqueues the job; rough_cut.mp4 appears in <5 min for a typical 60s video.
- [ ] Two videos can be in flight concurrently without colliding (per-slug file lock).

**Risks:**
- Pexels/Pixabay rate limits — back off and retry with one alt query, then fall back to slate.
- Concurrent assemble on the same slug — file lock per work dir.
- Mac sleep — when the laptop sleeps the worker pauses. Acceptable for personal cadence; document. The Monday analyst job will fire when the Mac wakes if it missed its window (launchd `StartCalendarInterval` honors this).
- Free-tier Supabase Realtime quota — if we use Realtime for live status, watch the 200 concurrent connections / 2M messages per month cap. Polling is cheaper for personal use; default to polling.

**Subagent:** general-purpose.

---

### Phase 5 — Dashboard editing

**Build:**
- Script editor: Markdown with syntax highlight (CodeMirror or Lexical). Save writes to Supabase + the work dir's `script.md`.
- Shot-list editor: a table view of shots with inline edit on `script_line`, `duration_sec`, `queries`. "Refetch" button per shot re-runs `fetch_assets.py` for that shot only.
- Asset picker: thumbnails for each shot's candidates; click to set in `selections.json` (and `selections_json` in DB).
- Rough-cut preview: HTML `<video>` against a Supabase Storage signed URL once `state >= ready`.
- "Approve → assemble" CTA: enqueues an `assemble` job; "Approve → ready tray" CTA when assembled.

**DoD:**
- [ ] Editing a script line and saving writes both to DB and disk; refresh shows the change.
- [ ] Refetching one shot replaces only that shot's `assets/<sid>_*` folder.
- [ ] Picking a different candidate then re-assembling produces the new rough cut.
- [ ] Editing while a job runs on the same video is blocked with a clear message.

**Risks:**
- Dashboard ↔ disk drift — DB is the canonical write target; the worker re-derives disk files from DB at job start.

**Subagent:** vercel:nextjs + vercel:shadcn + vercel:react-best-practices.

---

### Phase 6 — Music auto-duck

**Build:**
- `music_tracks` table populated by a one-time `worker/cli.py register-music <dir>` that scans your Epidemic/Artlist downloads on the mounted volume and inserts metadata.
- Shot-list / video gets a `music_track_id` field (optional). UI: dropdown of registered tracks with mood/bpm.
- `assemble.py` extended: if a music track is selected, layer it under the VO with `sidechaincompress` keyed off the VO so it auto-ducks. Loop or trim to video duration. Fade out last 1.5s.
- License source recorded per track; ready tray shows the credit line for use in the YT description.

**DoD:**
- [ ] Registering a directory inserts N tracks with metadata.
- [ ] Picking a track and re-assembling produces a rough cut with ducked music under the VO.
- [ ] No track selected → assemble works as before (silent music bed).
- [ ] License credit string appears in the ready tray's YouTube description.

**Risks:**
- BPM/mood from file metadata is unreliable — leave editable fields in the UI.
- Sidechain compress parameters need a tasteful preset; tune on one real video before committing defaults.

**Subagent:** general-purpose (ffmpeg).

---

### Phase 7 — Ready tray + push-to-device

**Build:**
- After assemble, orchestrator runs `instagram-copywriter` (caption + hashtags), `youtube-scriptwriter` (title + description + timestamps), `visual-director` (thumbnail brief) — one `ready_tray` row per platform target.
- Dashboard `/videos/[slug]/tray` view: per-platform card showing copy + hashtags + thumbnail brief + a download button.
- "Push to device" button copies the final mp4 + a `<slug>-<platform>.md` (the copy) into a configurable iCloud Drive path on the worker volume that's synced via `rclone` to your iCloud account. (Or simpler: a Supabase Storage signed URL you download on your phone — pick at build time.)
- "I posted it" button on each card → sets `ready_tray.posted_at`, transitions the video to `published`.

**DoD:**
- [ ] Every published video has at least one `ready_tray` row per target platform.
- [ ] Caption + hashtags pass the voice gut-check (matches `brand/voice-and-tone.md` rules — no "you won't believe", payoff doesn't bait-and-switch).
- [ ] Push-to-device delivers a playable mp4 + copy onto your phone within 60s.
- [ ] "I posted it" updates state visible immediately in the dashboard.

**Risks:**
- iCloud Drive via rclone on Linux is finicky — the simpler path is "Supabase Storage signed URL + you download on phone." Start there; revisit only if friction is real.
- The copywriter must respect platform caps (IG caption < 2200 chars; YT title < 100). Validate before persisting.

**Subagent:** vercel:nextjs for the tray UI; general-purpose for the push logic.

---

### Phase 7.5 — Metrics + analyst loop

**Build:**
- After "I posted it", schedule reminders (rows in a `reminders` table the worker polls) to capture metrics at 48h (IG) and 7d/28d (YT).
- Reminder fires → dashboard shows a "metrics needed" badge → form: views, likes, comments, saves, shares, watch time, retention. Save → `metrics` row.
- **Weekly analyst job runs via launchd Monday 09:00**, executing `claude -p "/performance-analyst weekly --metrics-since=<7d_ago>"` headless. Output (`analyst_brief_<week>.md`) is parsed and stored as an `analyst_briefs` row.
- "Run scout from latest brief" button on `/analyst` produces a copy-to-clipboard slash command pre-loaded with the brief as context — you paste into Claude Code, the scout writes `topics.json` for next week.

**DoD:**
- [ ] Posting a video creates the right reminders.
- [ ] Filling the metrics form persists and clears the badge.
- [ ] Monday launchd run produces a brief that explicitly references the metric patterns.
- [ ] The next scout call uses that brief as input.

**Risks:**
- **Headless `claude -p` may not see project subagents** — verify in Phase 2. Fallback: dashboard pushes a macOS notification on Monday "click to run analyst" and you run it interactively. Same outcome, manual click.
- Cold start — first week has no data; the analyst should gracefully say "insufficient data, use pillar rotation" rather than hallucinate trends.

**Subagent:** general-purpose; claude-code-guide for headless behavior verification.

---

### Phase 8 (DEFERRED) — Captions

**Sketch (don't build):**
- `captions.py`: Whisper API on `voiceover.mp3` → word-level timestamps → SRT/ASS in brand styling (cream body, amber emphasis on hook words, safe zones per platform spec).
- `assemble.py` learns a final burn-in step.

### Phase 9 (DEFERRED) — AI clip-gen

**Sketch (don't build):**
- `aigen.py`: fal.ai aggregator (Veo / Kling / Runway) keyed on `source_type=aigen` in the shot list.
- Cost guardrail per video.
- `assemble.py` already handles non-stock as slates — replace slates with generated clips when source is `aigen` and a clip is on disk.

---

## 5. Subagent map (which agent type drives which phase)

| Phase | Primary | Secondary |
|---|---|---|
| 0 Foundation | general-purpose | vercel:bootstrap (sanity-check Vercel link) |
| 1 Schema | supabase skill | general-purpose (run migrations) |
| 2 Subagent shim | claude-code-guide | general-purpose |
| 3 Dashboard MVP | vercel:nextjs | vercel:shadcn, vercel:auth |
| 4 Local worker | general-purpose | — |
| 5 Dashboard editing | vercel:nextjs | vercel:react-best-practices |
| 6 Music duck | general-purpose | — |
| 7 Ready tray + push | vercel:nextjs | general-purpose (push logic) |
| 7.5 Metrics + analyst | general-purpose | claude-code-guide (headless verification) |

---

## 6. Verification matrix

Every phase ships with **three checks**, in this order:

1. **Smoke test (golden path).** A single command or click sequence that proves the happy path works on a real video. Recorded in the phase's DoD.
2. **Failure-mode probe.** One deliberate break per phase — kill the worker mid-assemble, return zero stock results, exceed a token budget — and confirm the error surfaces cleanly in the dashboard.
3. **Cost + budget read.** After the smoke test, read the spend dashboards (Claude, ElevenLabs, Supabase egress, Railway compute) and confirm it's within the budget below. Halt the phase if any line is >2× projection.

**Projected per-video budget (steady state): $0.**
- Claude Code subagents: $0 marginal (your existing subscription).
- Voiceover: $0 (you record).
- Music: $0 marginal (your existing licensed library).
- Pexels / Pixabay: free.
- Supabase free + Vercel hobby: $0/mo at our scale (well under all limits).
- Local Mac: sunk cost, no incremental electricity worth tracking.

**Total target: $0/mo.** If any line shows a charge, halt and investigate.
The first paid line item we'd accept (when we monetize) is **ElevenLabs** for
voiceover at scale, then **Whisper** for captions, then **fal.ai** for AI
clip-gen. Document the trigger ($X channel revenue) before turning each on.

---

## 7. Risk register (cross-cutting)

| Risk | Likelihood | Mitigation |
|---|---|---|
| Claude Code subagent / headless CLI behavior changes | Medium | Pin a known-good CLI version; use `claude-code-guide` agent before relying on a new feature |
| Headless `claude -p` doesn't see project subagents | Medium | Verify in Phase 2; fallback is interactive analyst run on Monday morning |
| Mac sleeps during scheduled work | High | Acceptable — launchd retries on wake; weekly cadence tolerates a few hours of slip |
| Supabase free tier project pauses after 7d inactivity | Medium | First request unpauses; document the ~30s latency so we don't chase it |
| Supabase free DB / storage / egress limits | Low | We stay tiny: only metadata + thumbnails in Postgres/Storage. Mp4s never leave local disk. |
| Vercel hobby tier non-commercial clause | Low | This is personal; if it ever becomes commercial, upgrade is $20/mo |
| iCloud sync flakiness on push-to-device | Medium | Default to download-on-phone via signed URL; rclone only if asked |
| Brand voice drift in copywriter / scriptwriter subagents | Medium | Voice gut-check in the QC checklist; weekly analyst flags drift |
| `--author` not set per commit | High | One-time git config or shell alias; doc'd in CLAUDE.md |
| Partial migration drift | Medium | No `if not exists`; one `create table` per migration |

---

## 8. What this plan deliberately does NOT do

- **No paid services.** Target $0/mo. ElevenLabs / Whisper / fal.ai are unlocked by monetization, not by convenience.
- **No Anthropic API code.** Claude Code subagents only. Switching to API-direct is a Phase 10 ($) consideration once we have always-on cloud infra.
- **No TTS.** You record the voiceover. Voice quality and brand voice are stronger than any v1-tier TTS.
- **No auto-publish** to IG/YT. No Meta app review. No OAuth refresh circus.
- **No always-on cloud worker.** Mac at home + launchd is enough for personal cadence.
- **No captions burned in** (you finish in CapCut for v1).
- **No AI clip-gen** (placeholder slates remain in v1).
- **No multi-user / multi-tenant.** Single user is Caleb.
- **No mobile app.** Dashboard is desktop-first; tray-on-phone is a sync flow, not a native app.
- **No automated music selection.** You pick from your licensed library.
- **No analytics integrations.** Manual entry only in v1.

These are intentional cuts to keep v1 ship-able in ~1–2 weeks of focused work
at zero cost.

## 8.5. Monetization triggers (when we'd reopen the plan)

The first paid lines we'd accept, in order:

1. **ElevenLabs Starter ($5/mo)** when posting >3x/week and the manual VO record becomes the bottleneck. Switches Phase 7 ready-tray to optionally regenerate VO from a script edit.
2. **OpenAI Whisper API (~$0.006/min)** for burned-in captions (Phase 8). ~$1/mo at our volume.
3. **Anthropic API direct (~$0.50/video)** if we ever want truly autonomous overnight pipeline runs without your Mac being on. Lets the worker move to Fly/Railway/Render.
4. **fal.ai (~$0.10–$0.50/clip)** for AI clip-gen on non-stock shots (Phase 9). Only when stylized B-roll is the gating quality issue.

Each unlock has an explicit revenue trigger (e.g. "first $50/mo from
sponsors") — set those when we get closer.

---

## 9. Working order (the first three things)

When we kick off execution, the path is:

1. **Phase 0 in one session.** Move repo, git init, push, create Supabase free + Vercel hobby projects, save IDs to memory, scaffold dirs, install launchd plists, push a working empty deploy.
2. **Phase 1 in one session.** Write the schema migration, apply, generate types, smoke-test from the local worker.
3. **Phase 2 in one session.** Verify all seven subagents produce valid structured output against a real topic. Write the schema validators. Confirm headless `claude -p` behavior.

After Phase 2 we have the "agents actually work" milestone. Phases 3–7.5 then
go in order with the dashboard becoming useful midway through Phase 3.

---

*End of plan. Edits to this file should bump a date stamp at the top and call
out the decision being changed.*
