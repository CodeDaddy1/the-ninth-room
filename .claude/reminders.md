# Reminders — things only Caleb can do

Append items here whenever something needs Caleb's own hands (permissions,
console settings, recordings, decisions). Check items off when done.

## Open

- [ ] **Grant Accessibility permission** to the terminal app hosting Claude
  Code (System Settings ▸ Privacy & Security ▸ Accessibility). Until then,
  every Resolve session needs one manual click: Workspace ▸ Scripts ▸
  Ninth Room Bridge. Required for true zero-touch `/produce` runs (Phase 7).
- [ ] **Record real test footage** for pipeline verification: 3–5 takes of the
  same ~30s piece to camera (include at least one flub/restart on purpose)
  plus a few b-roll clips. Drop into `work/<test-slug>/footage/`.
- [ ] **Delete the retired cloud projects** when ready (both unused since the
  2026-08-18 pivot): Supabase project `xnyxdpezsfvltmqnzkme` and Vercel
  project `curated-curiosities`. Note: the next push to `main` may trigger a
  failing Vercel build (the `dashboard/` root dir no longer exists) — deleting
  the Vercel project stops that noise.
- [ ] **Confirm HMNS custom overlay `OV03`.** It was a pure-emoji card —
  text `🦜 = 🦋`, attribution `???` — so there is no wording to check the
  intent against. It is now a proper `emoji` kit card rendering
  🦜 = 🦋 across the frame, which preserves the original exactly; confirm
  that is the gag you meant. `work/hmns/overlays_custom.json`; original at
  `work/hmns/overlays_custom.pre-cyanotype.json`.

- [ ] **Restart the Edit Room.** The instance on port 8765 (PID 49527,
  started 2026-08-20 21:57) has the PRE-rebrand `overlay_kit`, `captions` and
  token modules held in memory, so anything previewed there still shows the
  retired Midnight kit. Stop it and re-run
  `/usr/bin/python3 -m pipeline.cli editroom`.

- [ ] **Decide on one dropped clause in HMNS `CARD46` (Slothzilla).** The
  subtext was "its size and bulk matched that of an average male African bush
  elephant"; the Cyanotype lower third reserves that slot for the specimen
  name in serif italic, so it now reads "Eremotherium, the giant ground
  sloth". The elephant comparison is a good fact with nowhere on that card to
  live — either let it go, or give it its own `stat`/`lower_third` beat.
- [ ] **Custom overlays are never schema-validated.** `overlays_custom.json`
  does not pass through `schemas.validate_graphics_plan` — `_export_overlay`
  goes straight to `graphics.bake_spec`. So an overlay created or edited in
  the Edit Room can carry a bad `kit_type`, a missing `rows`, or a wrong-typed
  field and only fail (or render wrong) at bake time. The one crash this
  actually caused is fixed at the root, but the validation gap itself is open.
  Worth wiring the validator into the Edit Room's save path.

- [ ] **Two latent kit defects, deferred from code review (2026-08-21).**
  Neither is reachable today; fix if the trigger ever appears.
  - `captions.py` — when `_emoji_img` returns `None` (a codepoint Apple Color
    Emoji cannot rasterise) the token takes zero width but the draw loop still
    advances by `width + word_gap`, leaving a visible double space mid-caption.
    Needs a font-coverage failure to manifest; none reproducible today.
  - `overlay_kit.py` — `_fit` and `_arch` don't clamp their size input.
    `_fit("hello", 0)` emits `font-size:0px`; `_arch(8)` yields a zero-width
    figure. Every current call site passes a positive literal, so this only
    matters if either becomes caller-driven or Edit-Room-exposed.

- [ ] **Studio + landing page follow-ups (2026-08-21):**
  - Create the Vercel project for `CodeDaddy1/the-ninth-room-studio` (import
    the repo in the Vercel dashboard; no env vars needed — the Studio routes
    self-disable without `STUDIO=1`). Attach a domain whenever you buy one.
  - On launch day: put the first episode's YouTube video id into
    `the-ninth-room-studio/src/lib/site.config.ts` `EPISODES` and redeploy.
  - Delete the old `curated-curiosities` Vercel project (it will fail-build
    on pushes and is retired).

- [ ] Optional: in Resolve, delete the spike leftovers (project
  `CURATED_SPIKE`, timelines `spike_*`) — harmless if kept.

## Done

- [x] 2026-08-18 — Started the Ninth Room Bridge once so Phase 0 could verify
  the in-app scripting route.
- [x] 2026-08-20 — **Brand POV signed off.** v1's "voice on, face off" is
  retired; `brand/brand-brief.md` now locks **on camera** (Caleb, Alma and
  Sofia appear; Caleb carries the narration) as part of The Ninth Room
  rebrand. No further approval outstanding.

## Added 2026-08-18 (HMNS render)

- [ ] **Give DaVinci Resolve permission to read the Desktop.** System Settings ▸
  Privacy & Security ▸ **Files and Folders** ▸ DaVinci Resolve ▸ enable
  "Desktop Folder" (or grant **Full Disk Access** to DaVinci Resolve, which
  covers every future footage location). Verified 2026-08-18: Resolve cannot
  open `~/Desktop/Curated Curiosities/DJI/...` at all (`io.open` → BLOCKED),
  so `ImportMedia`/`ImportTimelineFromFile` return nil for that footage while
  files under `~/Projects/` import fine. **Workaround already in place:** the
  pipeline copies footage into the repo's `work/<slug>/footage/`, which
  Resolve can read — so this grant is optional, but it saves the copy step
  and 62GB of duplication for future shoots.

## Added 2026-08-18 (music)

- [x] Music: Caleb scores in post, so the pipeline does not mix it. If that
  changes, `pipeline/music.py` lays a per-chapter bed ducked under the
  narration. Note the library looks like Epidemic Sound (`ES_` prefixes) —
  that needs an active subscription with the channel connected, or YouTube can
  still issue a claim.

- [ ] **Credit the cocoon photo in every video description that uses it.**
  Required by its licence: `Cecropia moth cocoon photo by Ryan Hodnett,
  CC BY-SA 4.0 (creativecommons.org/licenses/by-sa/4.0), cropped.` The
  share-alike term also means that image and any edit of it stays CC BY-SA 4.0.
  The monarch chrysalis (USFWS) is public domain and needs no credit.

## Added 2026-08-19

- [ ] **Rotate the OpenAI API key.** It was pasted into the Claude chat
  (2026-08-19), so it exists in the conversation transcript. Create a new key
  at platform.openai.com/api-keys, update `~/.config/watch/.env`, revoke the
  old one. Takes two minutes.

## 2026-08-22 — Studio Interactive Suite plan
- Paste `EPIDEMIC_API_KEY=<your key>` into `~/Projects/the-ninth-room/.env`
  (gitignored). The P0 Epidemic probe and the P2 sound picker need it.
- Keep Resolve open when asked during P3 conform and P5 render checks.
- After P2 ships: prune Epidemic pulls you don't like from brand/sfx/;
  manifest.json tracks what's licensed.
- **Epidemic key RESOLVED (2026-08-22).** It is a subscriber key and works
  against the account MCP service (not the partner REST API) — search,
  preview, and pull all live in the desk. One future errand: keys expire
  ONE YEAR after creation; when pulls start failing with 401, mint a new
  key at epidemicsound.com/account/api-keys, paste into `.env`, re-run
  `scripts/epidemic_probe.py`.

## 2026-08-22 — from the hmns fixer round (BT10 / BT78)

- [ ] **Brief `subtext_delay` back into Claude Design.** BT10's note
  ("Subtext should not be delayed") needed a per-card timing override on the
  lower third, so `pipeline/overlay_kit.py` now reads `subtext_delay` (ms) and
  falls back to the canvas's 300/400ms stagger when unset. Only the runtime
  kit knows about it — the Cyanotype canvas in the design system still hard-
  codes the stagger. Rule 6 says the canvas is the source of truth, so it
  should learn the knob (or tell us the stagger is non-negotiable and BT10
  gets a different answer).
- **Delete the orphaned `curated-curiosities` Vercel project.** It is still
  linked to the renamed `the-ninth-room` GitHub repo, so every engine push
  triggers a doomed Next.js build (the failed-deploy emails). Nothing real
  is attached — no custom domains, not live, v1 app long superseded. Run:
  `vercel project rm curated-curiosities` (or, to keep the project shell
  and only stop the builds, disconnect the Git repo in the Vercel dashboard:
  curated-curiosities → Settings → Git → Disconnect). (2026-08-22)

- [ ] **Re-grant Desktop access to the terminal hosting Claude Code.** Sometime
  after ~10:30 on 2026-08-23 macOS revoked it (morning audits decoded the
  Desktop DJI files; by 15:00 even an unsandboxed `ls ~/Desktop` returns
  Operation not permitted). System Settings ▸ Privacy & Security ▸ Files and
  Folders (or Full Disk Access) ▸ your terminal app ▸ Desktop. Until then:
  hmns audio work (trough rescue, speech-edge audit, re-proxy) is blocked —
  its footage symlinks into ~/Desktop/Curated Curiosities. The audit now says
  "N of M edges UNMEASURABLE" instead of silently passing. After granting,
  run: `rebake hmns` then `audit hmns` for the sighted rescue. (2026-08-23)

- [ ] **Back up work/ + the Desktop footage before shipping HMNS.** Neither
  the 62 GB in ~/Desktop/Curated Curiosities nor work/hmns has a second copy
  anywhere (footage/artifacts are gitignored by design). One rsync to an
  external drive before conform/re-cut runs on the episode that matters.
  (2026-08-23)
