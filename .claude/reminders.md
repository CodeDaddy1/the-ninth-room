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
  open `~/Footage/Curated Curiosities/DJI/...` at all (`io.open` → BLOCKED),
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
  its footage symlinks into ~/Footage/Curated Curiosities. The audit now says
  "N of M edges UNMEASURABLE" instead of silently passing. After granting,
  run: `rebake hmns` then `audit hmns` for the sighted rescue. (2026-08-23)

- [ ] **Back up work/ + the Desktop footage before shipping HMNS.** Neither
  the 62 GB in ~/Footage/Curated Curiosities nor work/hmns has a second copy
  anywhere (footage/artifacts are gitignored by design). One rsync to an
  external drive before conform/re-cut runs on the episode that matters.
  (2026-08-23)

## 2026-08-23 — from the hmns fixer round (BT01)

- [ ] **Brief the translucent transition plate back into Claude Design.**
  BT01's note ("lower opacity for the title card with background visible
  underneath, apply gradient") needed the house cut to stop covering the
  shot, so `pipeline/overlay_kit.py`'s `transition()` now reads the existing
  per-card `scrim` (0-100): with it set, the full-frame navy plate becomes a
  navy gradient at that strength — deepest under the title on the left,
  fading to nothing — instead of the opaque wall. Opt-in, so a transition
  with no `scrim` renders byte-identical (verified on CARD03/13/17/27/38).
  Only the runtime kit knows about it; the Cyanotype canvas still paints the
  transition solid. Rule 6 says the canvas is the source of truth, so it
  should learn the knob. Same shape of debt as `subtext_delay` above.
- [ ] **BT01 is fixed but unverified — re-proxy it after Desktop access is
  back.** CARD02 is re-baked with the gradient (frame-checked against the
  real shot), but `proxy hmns --beat BT01` cannot read the footage, so the
  Review desk still shows the OLD opaque card and the beat is deliberately
  left flagged. Run `/usr/bin/python3 -m pipeline.cli proxy hmns --beat BT01`,
  look, then approve it on the desk.
- **`scrim` (and `style`) are invisible to the proxy cache.**
  `pipeline/proxy.py:_spec_body` keys a beat's proxy on only
  `id/type/kit_type/at/duration/kicker/text/stat/subtext/emphasis/rows/entries/animation`,
  so dialing `scrim` on the Overlays desk re-bakes the card but leaves the
  beat's proxy a cache hit — the desk keeps showing the old look, which is
  exactly the "74 stale proxies" failure that comment warns about. Same gap
  for `style`, `font_scale`, `card_scale`, `offset_x/y`, `subtext_delay`.
  Not fixed here: adding fields changes every beat's hash and would
  re-render all 34 card-bearing beats, which is outside a fixer round.
  (2026-08-23)

## 2026-08-23 — from the hmns fixer round (BT01, BT04, BT24)

- [ ] **Only you can grant this: Claude Code cannot read `~/Desktop`, so no
  fixer round can re-proxy an hmns beat.** Every source clip in
  `work/hmns/footage/` is a symlink into
  `~/Footage/Curated Curiosities/DJI/05-17-26 - HMNS/`, and ffmpeg run from
  the session gets `Operation not permitted` on all of them — the cards bake
  fine (Chrome + local files), the proxies cannot render. Grant the Claude
  Code app Full Disk Access (System Settings → Privacy & Security → Full Disk
  Access) and this whole class of round finishes itself.
- [ ] **Three beats are fixed but unverified — re-proxy them.** Supersedes
  the BT01-only item above: CARD02 (BT01, your scrim 50), CARD03 (BT04) and
  CARD13 (BT24) are all re-baked as navy gradients and frame-checked against
  the real shots, but their Review proxies are still the OLD opaque cards, so
  all three stay flagged. Run
  `/usr/bin/python3 -m pipeline.cli proxy hmns --beat BT01 --beat BT04 --beat BT24`,
  look, then approve on the desk.
- **Correction to the "`scrim` is invisible to the proxy cache" note above.**
  Measured this round: `beat_spec` also carries `gfx_sig` (each card mov's
  mtime + size), so a re-baked card DOES re-key its beat's proxy — BT01
  9dbac390e124, BT04 eaf37a8f6587 after the bake. The real gap is upstream:
  `/api/overlay/save` writes the plan and never bakes, so dialing `scrim` on
  the Overlays desk leaves the mov stale until something calls
  `build_cards` (Approve & Export, `cli rebake --card`, or a fixer round).
  The desk shows the old look because nothing re-baked, not because the
  proxy cache missed it.
- [ ] **The other transitions still have solid plates.** CARD17, CARD27 and
  CARD38 are the remaining `style: rule` house cuts with no `scrim`. You
  flagged BT01, BT04 and BT24 one at a time and the fix is identical; say the
  word and the next round does all three at once instead of waiting for three
  more flags. (2026-08-23)
- [ ] **Only you can confirm the five orchestra names in the crooise script
  (CH5).** `script.json` CH5.S5–S10 quote takes T265–T270 — the Boardwalk
  orchestra roll call, the beat that answers your "who lives aboard" brief
  note. Whisper transcribed those names through applause and heavy accents,
  and every one of them is a guess: "Nicholas" (Ecuador), "Juan Pedro
  Saksapol-Raim" (United States), "Juan Agazaksozco" (Colombia), "Hatter"
  (Canada), "Montromont Francisco" (Puerto Rico), and the musical director
  "Piori". The script currently ships the plausible fragments and drops the
  unrecoverable ones. Listen to `IMG_7188.mov` 0:00–0:37 and write down what
  you actually hear before any of these reaches a caption or a card —
  misspelling a musician's name on screen is the exact failure this channel
  cannot afford. Same take carries a headcount ("34 musicians") that is
  equally garbled; the script deliberately does not use it. (2026-08-23)

- **Iterate the Punchline Captions canvas** (added 2026-08-24): the seed
  canvas "The Ninth Room - Punchline Captions.dc.html" is in the design
  system project with three directions (A bigger word-pop · B the slam ·
  C spoken underline). Pick/iterate in Claude Design; the winner gets
  ported into pipeline/captions.py as the punchline style. Until then,
  punchline episodes bake selected-only at the current look.

- [ ] **Only you can settle which crooise story the publish package describes**
  (added 2026-08-24). `work/crooise/publish.md` is written from
  `edit_plan.json` — the scorecard spine (S2, "First Impressions, Out of
  Five"), which is what the beats, the graphics plan and `thumbnail_v1.png`
  all actually build. But `story_feedback.json`'s latest round (round 3,
  2026-08-23 18:18) approves **S8, "But the Floor Is Moving"** — the
  engineering angle off `research.json`. The edit plan flags the same conflict
  in `notes.which_story_this_follows` and follows the script because S8 is
  three-quarters voice-over that has not been recorded. If round 3 was meant
  to supersede the script, then the script, the plan, the thumbnail *and* all
  three titles are the wrong episode and this package has to be rewritten from
  S8. One word from you either way.
- [ ] **Mark the winning crooise title after upload day.** `work/_channel/titles.json`
  now holds the three options with `chosen: null`. Set the winner to `true`
  once it is live — that ledger is the only record of which title *kind*
  (gap / noun / question) actually earns clicks on this channel, and future
  publish packages read it. It is empty of history until you start marking.
- [ ] **The HMNS coelacanth card asserts a fact your footage never states**
  (added 2026-08-24). `graphics_plan.json` CARD38 (BT73, kit `lower_third`)
  reads "Called extinct, then caught alive in 1938 · *Latimeria chalumnae*".
  That is the reveal S1's hook promises, and `edit_plan.json`'s notes flag it
  as VO section CH8.S10 — written in `script.json`, **not recorded, and with
  no `research.json` behind it**. The card is on solid ground historically,
  but accuracy is the brand: run the research job before this bakes, or pull
  CARD38 and let BT73's on-camera line ("a very prehistoric fish that still
  exists today") carry the beat alone. Recording CH8.S10 closes the hook's
  loop properly and makes the card redundant either way.

- **Sign off brand/taste.md** (added 2026-08-24): 20+ taste statements
  mined from your recorded verdicts, marked UNSIGNED DRAFT. Read it,
  strike or amend statements, then replace the header line with
  "Signed off by Caleb <date>" — no doctrine or showrunner review may
  cite it until then.

- [ ] **Roatan CH2 and CH5 have no establishing footage, and no edit can fix it**
  (added 2026-08-24). The coverage pass on `testing` audited all 90 clips in
  `work/testing/analysis/broll.json`: exactly **five** are Roatan-on-land and
  long enough to cut (B013 macaws, B014 bridge POV, B015 bridge wide, B067
  island road, B069 jungle trail). Everything else is the ship, Galveston,
  food or a later port. So "Welcome to Roatan" (CH2) and "The Heist Crew"
  (CH5) open with nothing but a face, and **the heist crew itself — the
  monkeys the episode is named for — has no footage at all**, nor do the
  kinkajou, parrots, coati, mangoes or chili, all of which are named on the
  word. Staying on the face is the right call for the cut we have, but only
  you can decide whether that is the episode you want to ship or whether this
  needs a relink (is there Roatan card footage that never got ingested?) or a
  reshoot. Check the footage folder against what you remember filming before
  you answer — a missing-import is the cheaper explanation.

- [ ] **Two overlay screens need a Claude Design brief before any code**
  (added 2026-08-24, from `docs/film-studies/johnny-harris.md`). The study
  produced exactly two techniques we have no screen for, and
  `CLAUDE.md` rule 6 says the design system decides first, not the
  pipeline:
  (a) **the sourced-quote card** — a quote in brand type with a smaller
  attribution line beneath naming the source and how we know it. This is
  the visual form of "accuracy is the brand" that we currently do not
  have; it would let a plaque, a guide or a sign be quoted with its
  receipts on screen. Evidence: 10:32 in the studied video.
  (b) **a persistent-actor rail** — Caleb, Alma and Sofia resident at the
  frame edge carrying live state (who's ahead on a bet, who guessed what),
  the way that video parks faction badges for its whole runtime. We have
  `scoreboard`, `streak` and `vote` but nothing that *stays*.
  Both must be designed in the *The Ninth Room Design System* project and
  re-implemented here from what comes back — and both must obey "no filled
  plates, one yellow moment per frame," which the studied video does not.
  Only you can open the Claude Design brief.
- [ ] **Make the cast name-boards — this is a physical build, not a render**
  (added 2026-08-24, from the Mark Rober film study). The strongest single
  steal in `docs/film-studies/mark-rober.md` for an ensemble family channel:
  he introduces his four characters at 9:30 with **hand-lettered wooden
  boards standing in the actual yard**, one per character, each with a real
  measured number on a small hanging tag — delivered as a 2x2 quad-split. Not
  a lower third. The same trick carries his labelled nut-buffet (4:04, 9:16),
  the re-lettered correction board (13:51) and a Sharpie "manual override"
  block held to camera (16:05). This is Beau Miles' "the progress graphic is a
  real object" rule confirmed by a creator with a hundred times the budget,
  and it means the cast graphic is lit by the same sun as the family.
  For us: three boards — **Caleb, Alma, Sofia** — in chalk on ply or slate, in
  Cyanotype's register (navy ground, chalk type, one yellow accent, no filled
  plate), plus a couple of blanks for per-episode labels. Then they travel in
  the kit bag to every location. The kit's `lower_third` stays for when there
  is no board. Only you can build them, and only you can decide whether they
  get the Archway on them — if they do, that artwork comes from
  `brand/design-system/channel-assets/`, not a redraw.

- [ ] **Brief Claude Design: the `hold` screen and a `hold_is_the_number` stat
  mode** (added 2026-08-24, from the Mark Rober film study). Two kit
  behaviours the study earns and we cannot invent here (CLAUDE.md rule 6).
  (a) **`hold`** — a bare navy ground used as punctuation, in three measured
  durations: a ~2.2s *hinge* to change time with a small chalk aside entering
  at ~55% of it (evidence 0:21.56, aside at 0:22.77 for 0.96s), a ~2.8s
  type-free *curtain* before a montage (3:25.58), and a ~3.3s *reveal* hold
  under the single most important sentence of the episode (13:43.07 — he
  delivers the biggest fact in the film on pure black with nothing on it).
  (b) **`hold_is_the_number`** — a `stat` mode where the yellow moment lasts
  *exactly* the interval being claimed. At 17:00.89 a card reads "300
  milliseconds", then a flash **is** the demonstration. Note the honesty catch
  that makes this ours to get right: his flash measures **0.208s**, not 0.300.
  If we ship it, it is frame-accurate or the claim changes.
  Only you can open the Claude Design brief.

- [ ] **`workflow-shakedown` has no `story_brief.json` and no `research.json`**
  (added 2026-08-24, from the round-1 story pitch). The three directions each
  had to declare their own target length because no brief assigned one — S1
  85s, S2 135s, S3 110s — so approving a pitch also silently approves a
  runtime nobody set. Only you can fill the Planner questionnaire. The
  research gap is the harder one: every VO chapter that would carry a fact is
  currently marked "needs sourcing", including the actual reason a glasswing's
  wings read as transparent — S1 budgets a whole 12s chapter to it. Nothing
  can be scripted into a claim until that file exists.

- [ ] **Shoot a ninth-room line on the next visit.** All 139 seconds of HMNS footage in
  `workflow-shakedown` — eight clips — contain no on-camera moment where
  anyone names the thing that wasn't on the map. The three candidates the pitch found
  — the airlock between the doors, the specimen drawers you may open yourself,
  and the lobby amethyst everyone walks past — are all carried by picture plus
  voice-over, which is honest but leaves the brand promise resting on
  narration. One sentence said out loud, in the room, fixes it. Only you can
  shoot it.

- [ ] **Shoot one plant shot for the ending, on the way in.** (added 2026-08-24,
  from the `workflow-shakedown` edit plan.) The b-roll library for this shoot is
  four clips and all four are the same thing: arriving at the butterfly center.
  So the cut can `establish` (once, over the hook) and it can `process`, but it
  has no honest `foretell` — nothing in the library plants what the ending pays
  off, and the plan ships with one cover rather than a why invented to make the
  count. The fix costs about ten seconds at the door: once you know what the
  episode is likely to land on, grab a wide of it on the way IN, before anyone
  reacts to it. Only you can shoot it.
