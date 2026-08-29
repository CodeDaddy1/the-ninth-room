# Reminders — things only Caleb can do

Append items here whenever something needs Caleb's own hands (permissions,
console settings, recordings, decisions). Check items off when done.

## Open

- [ ] **Name the desk lane's signatures.** You decided (2026-08-24) that a
  script-led desk episode owes **neither** the ninth-room moment nor the door
  meter, and that its own conventions get defined later. Until you name them,
  the story-director enforces only accuracy, a closed loop and the voice on
  desk episodes — and it is explicitly forbidden from inventing a substitute
  ritual. A visit still owes its ninth room. Decide what a desk episode
  promises the viewer that a generic explainer does not.

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

- [ ] **Get B030 and B100 into `the-pendulum-that-stopped`.** (added 2026-08-25,
  from your Q8 = a on the script round.) Both pendulum clips live in
  `work/houston-museum-of-natural-science/analysis/broll.json`; this slug's
  `analysis/` is empty. `CH1.S2` (18.4s) and `CH1.S7` (12.4s) declare them
  `from: "library"`, but `coverage_budget` only ever reads THIS slug's
  `broll.json` — so until the files and an entry for each exist here, those
  31 seconds read as an uncovered hole and the sourcing stage will try to buy
  pendulum pictures we already own. It needs an ingest pass on this slug, which
  is the engine's job and yours to start, not the script director's.

- [ ] **Brief Claude Design: four new screens for `the-pendulum-that-stopped`**
  (added 2026-08-25, from the sourcing PROPOSE pass). The script declares
  105.2s of its 180s of narration `from: "graphic"`, and the kit can serve
  only 13.6s of it today. Four components do not exist, and rule 6 says they
  are designed there and re-implemented here, not invented in the pipeline:
  (a) **a rotating globe** with a pinned latitude and a chalk arc sweeping
  exactly 180 degrees (CH1.S4, 18.0s) — `flight_path` draws a travelling path
  but across a flat map;
  (b) **a technical cutaway** of the pivot head — collar, coil, contact
  closing at mid-swing, the tug as one arrow — on a loop that holds 21.6s
  (CH3.S2). This one carries the answer the whole episode is built toward;
  (c) and (d) **two illustrative scene plates** (CH2.S7 15.6s, CH2.S8 14.8s):
  the dented original bob in its vitrine, and the Smithsonian's pendulum down
  its stairwell. Design these two together — they cut back to back and should
  read as a pair. Nothing in `RENDERERS` draws a scene at all: `compare` puts
  two *supplied* images side by side, `callout` frames a detail. Both plates
  need the small grey "illustration" label actually shipped, or a drawing of a
  real object reads as a photograph of it.
  All four in Cyanotype's register, and the yellow moment goes on the thing
  the sentence is about — the pin, the tug arrow, the dent, the falling bob.
  Only you can open the Claude Design brief.

- [ ] **Decide where `the-pendulum-that-stopped` spends its `payoff` card.**
  (added 2026-08-25, same pass.) CH3.S6 wants a sourced-quote card and the kit
  already draws one — `quote` is an alias of `payoff` and it does take
  `attribution`, rendering it as a small cyan caps line. But `payoff` is
  documented "Reserved for the takeaway line, once per video," and this
  episode closes on a 34.4s desk section that will almost certainly want it.
  Either the Hemberger quote gets it and the close does without, or the
  dedicated sourced-quote card from the Johnny Harris study (item (a) above,
  still unbuilt) finally gets briefed. Your call, not the graphics-director's.

- [ ] **Approve the two archival rounds for `the-pendulum-that-stopped`, and
  settle the 1851 problem.** (added 2026-08-25, from the sourcing PROPOSE
  re-run.) `CH2.S3` and `CH2.S4` are the only 44s of the episode that can be
  BOUGHT rather than drawn, and both rounds now carry six resolved candidates
  each with real item pages and previews. The `CH2.S3` half is easy — three
  period portraits, take one. `CH2.S4` is not, and it needs you: **no genuine
  1851 depiction of the Pantheon demonstration exists** in Commons, Gallica or
  Wellcome. What is available is a 1902 drawing of the event, a 1902 photo of
  a reconstruction of it, an 1850s engraving of the WRONG demonstration (Baden
  Powell at the Royal Institution in London), and the modern replica on video.
  The episode spends CH2.S5 correcting a placard for confusing London 1851
  with Paris 1851, so running the London engraving under the Pantheon line is
  the exact error we are calling out one beat earlier. Either a date goes on
  screen over whichever picture wins, or the sand bed becomes a fifth kit
  plate and the archival budget drops to 18.8s. Only you can spend the money
  or add the fifth screen to the Design brief above.

- [ ] **Two CC-BY credit lines owe the description on upload day for
  `the-pendulum-that-stopped`.** (added 2026-08-25, from the sourcing FETCH
  run.) Both approved archival picks are Creative Commons **Attribution**, not
  public domain — Commons' own licensing block says `AttributionRequired:
  true` on each — so the credit is a condition of use, not a courtesy, and it
  has to be in the published description. Paste verbatim:
  `Fondo Antiguo de la Biblioteca de la Universidad de Sevilla, CC BY 2.0, via
  Wikimedia Commons` (the 1882 engraving on CH2.S3) and `Zátonyi Sándor,
  (ifj.) Fizped, CC BY 4.0, via Wikimedia Commons` (the Panthéon video on
  CH2.S4). Both strings also live in `work/the-pendulum-that-stopped/assets/
  assets.json`. Only you can edit the description at upload.

- [ ] **Put a date on screen over the Panthéon video, and decide the CH2.S3
  cellar.** (added 2026-08-25, same run.) The fetched CH2.S4 clip is the
  **modern replica** swinging under the dome — it carries the room, the drop
  and the scale of a 67 m wire, and it must not run under the 1851 sentences
  as if it were the demonstration; that is the same London-1851/Paris-1851
  error CH2.S5 calls out. And the CH2.S3 pick covers only the apparatus half:
  no period image of the rue de Vaugirard cellar was found in Commons, Gallica
  or Wellcome, so the lamplit cellar the line describes is still either a kit
  plate or nothing. Your call on both, before the cut locks.

- [ ] **`oligarchy` has an approved, locked script and zero frames of footage
  — the cut cannot be built until you record it.** (added 2026-08-26, from the
  edit-plan run.) All ten performed sections are unrecorded, so the engine's
  own next step reads "Approved. Record the desk and voice-over lines, then
  Build the cut." Recordings match sections by FILENAME, so use exactly these
  prefixes (Studio teleprompter emits them; `<n>` is the take number):
  `vo_CH1-S1_r1_t<n>`, `desk_CH1-S2_r1_t<n>`, `vo_CH1-S3_r1_t<n>`,
  `vo_CH1-S4_r1_t<n>`, `desk_CH1-S5_r1_t<n>`, `vo_CH1-S6_r1_t<n>`,
  `vo_CH1-S7_r1_t<n>`, `vo_CH1-S8_r1_t<n>`, `vo_CH1-S9_r1_t<n>`,
  `desk_CH1-S10_r1_t<n>`. The three `desk_` names are deliberate and not
  interchangeable with `vo_`: four rules hard-block a `vo_` picture from ever
  reaching the screen, and S2, S5 and S10 are the ones where your face IS the
  shot. Only you can perform these.

- [ ] **`oligarchy` needs 28.8s of covering picture bought or shot, and all
  seven asset requests are still `proposed`.** (added 2026-08-26, same run.)
  Every voice-over second is a second with no face to cut to, and the library
  is empty: 20.0s must come from stock, 4.4s is a kit graphic (the corrected
  market-share stat on CH1.S6), and 4.4s **only you can shoot** — CH1.S1 is
  the macro on the maker's name stamped inside your own glasses, and the
  sourcer was right that no stock pair can stand in, because the whole short
  turns on the viewer reading the name in YOUR glasses. Note the sourcer's own
  finding on CH1.S3: no stock clip it found has a legible designer name on the
  temple arm, so "Chanel. Prada. Armani. Versace." has no picture that proves
  it yet. Only you can approve the candidates and spend the money.

- [ ] **`golf-testing`'s approved direction S2 cannot be cut by the engine —
  two blockers, and only one of them is yours.** (added 2026-08-27, from the
  edit-plan run.) You approved S2, "The Person Holding the Phone", whose own
  pitch says "this is the only direction where the b-roll audio IS the
  script". That is the problem: **a b-roll cover is emitted as an FCPXML
  `<video>` element on lane 1 — picture, never audio** (`pipeline/timeline.py`
  :533, and :20 says suppressing b-roll audio is deliberate; `broll.py`'s
  `promote()` says "It plays SILENT"). So "Nice, babe.", "No way." and "See
  you next time." — the three lines the whole direction rests on — are
  inaudible in any cut this engine can build today. **Only you can decide**
  which way out: (a) re-approve a direction that does not need b-roll audio,
  (b) commission the engine change (b-roll audio on the timeline, or the
  wordless-run beat `.claude/agents/story-designer.md` already names as "a
  separate, larger piece of work"), or (c) shoot the lines as real takes.
  The second blocker is ordinary and yours too: the short is 24.4% VO and
  **none of it is recorded**, so there are no `vo_*` takes to anchor its
  beats to (`analysis/takes.json` holds exactly one take, T01, 3.32s — the
  entire project has 3.32 seconds of audio this engine can put on a
  timeline). The finished design, validated clean on everything except the
  missing material, is in `work/golf-testing/edit_plan.blocked.json`;
  `edit_plan.json` was deliberately NOT written, because its existence flips
  the Studio to "the cut is written" and the assemble job would hard-fail.

- [ ] **Decide whether `golf-testing` should be rebuilt vertical, and who is
  holding the phone.** (added 2026-08-27, same run.) Two things the story
  side cannot answer. First, ingest baked six of the eleven clips
  (IMG_6283, IMG_6323, IMG_6419, IMG_6429, IMG_6587, IMG_6603 — all natively
  720x1280) into 3840x2160 blurred-ground companions and pointed
  `catalog.json` at them, so a 9:16 short assembled through the catalog as it
  stands picks up letterboxed landscape for most of its shots. `survey.json`
  still holds the true native sizes. Second, the off-camera voices are
  **unattributed** — the pipeline cannot tell you whether it is one person
  across the year — so no VO line in the design names or genders them, and
  the line "they start rolling before I am ready" assumes you are the golfer,
  which the brief does not say. Confirm both before any VO is recorded.

- [ ] **`golf-testing`: the locked script asserts four things the footage does
  not contain — and two of them are yours to settle before a word is
  recorded.** (added 2026-08-27, from the second edit-plan run, which read the
  approved `script.json` rather than the pitch.) I checked every claim on real
  frames, not on the nine-frame contact sheets. **CH1.S7 and CH1.S8 are built
  on "the frame he has already walked out of, held on empty winter grass" —
  that frame does not exist.** In `IMG_6419` he is still at address at 6.4s,
  does not begin leaving until ~11.4s, and at 12.1s his shoulder and the club
  are still in shot; the nearest empty frame is the last ~0.23s. No clip in
  the library holds an empty frame for two seconds. S8 also comes up 1.7s
  short because of it. **CH1.S4 says "One winter." over `IMG_5639`, which is
  deep summer** — full green canopy, between two bare-tree winter beats. Both
  need either a new line or a new picture, and the script is locked, so only
  you can reopen it. Two smaller ones I absorbed into the design and you
  should know about: S10's "about ten seconds after the strike" is really
  ~7.2s (strike ~3.9s, "No way." at 11.14s) — honest numbers, so nothing may
  ever say ten; and S3 and S6 both say "from the top", where a window from
  0.0s contains no swing at all, so both trims moved later by their own
  duration. The full section-by-section design is in
  `work/golf-testing/edit_plan.blocked.json`, which now carries four blockers
  rather than two, and supersedes the 24.4%-VO figure in the entry above (the
  approved script is 27.8% VO across 46.1s).

- [ ] **The coverage gate can never pass a voice-over-led cut — decide
  whether to commission the one-line fix.** (added 2026-08-27, found while
  dry-running `golf-testing`'s design.) `schemas.coverage_notes`,
  `schemas.gear_change` and `captions.vo_beats_of` all decide "is this a VO
  beat" with `beat["take_id"].startswith("vo_")`, but `takes.py:312` names
  every take `T01`, `T02`, … — **so no take id can ever start with `vo_`, and
  the VO exemption is unreachable.** `validate_edit_plan:479` gets it right by
  testing the take's FILE instead, which is where the prefix actually lives;
  the two have drifted apart despite `captions.py`'s docstring promising they
  cannot. Measured, not reasoned: a dry run of the `golf-testing` design
  returns `validate_edit_plan` VALID and `coverage_notes` with ten entries —
  "covers the landing" and "100% covered" on each of its five VO beats, the
  exact two rules a VO beat is supposed to be exempt from. `jobs.py:1611`
  fails the coverage job on any entry, so **every VO-led episode is blocked at
  that gate, not just this short.** It also means `gear_change` will report
  "no VO beats" on a cut that is all VO, and in landscape the caption pass
  will treat VO beats as ordinary ones. I did not touch it — changing a
  validator every project runs through is your call, not a side effect of
  writing one edit plan.

## Resolve proxy linking — SETTLED, nothing owed (2026-08-27)

**Closed the same day. No action needed; kept as the record.**

Tested on a throwaway project, `CC_hmns_SemiFinal` never opened. The same
4K timeline rendered twice — once from originals, once with previews
linked — came out **pixel-identical** (`psnr: inf`, `mse_avg: 0.00`, all
68 frames). Resolve's free edition does swap back to the original at
render, so proxy editing is safe.

Shipped: `POST /api/resolve/proxies` links or unlinks; a master render
refuses while any preview is attached (`preflight_no_proxies`, code
`proxy_linked`) and names the way out. The guard stays even though the
swap-back works — a Resolve update could change it, and the failure is
invisible in the output.

Test project deleted, previews unlinked, your project reopened and
verified: 237 clips, 0 proxies, 0 leftover PROXYTEST_* projects.

**One thing worth knowing:** your masters had been rendering at 1920x1080
from 4K source, because the render never pinned its output size and took
whichever of 24 presets was selected in Resolve's UI. Fixed — the render
now pins to the timeline's own resolution and measures the result. Full
write-up in `docs/resolve-findings.md`.

---

## `oligarchy`'s narration dial is wrong on disk (2026-08-28)

`work/oligarchy/story_brief.json` holds `"vo_share": 0.6`. For a
script-led Short the engine's own default is **0.85**
(`schemas.VO_SHARE_DEFAULT[("script","short")]`), and the 0.6 is not a
choice you made — it is damage. The old Story brief form never sent
`vo_share`, and `_save_story_brief` defaults what the caller omits, so
every save of that brief overwrote the dial with 0.60.

The form now sends it and the Story desk shows it, so it will not drift
again. What it cannot do is know what you meant: `script_notes` fails a
draft whose VO share is more than 10% off this number, so a documentary
short briefed at 0.6 is being told to put 40% of a 45-second film on
camera it does not have.

**Your call:** open `/studio/story/oligarchy`, press edit on the brief,
and set Narrated to 85 (or whatever you actually want). One click, and
it only matters before the next `script` run.

Same question, quietly, for any other project created before today: the
value on disk is only trustworthy if the brief was never saved from the
Studio.

## The re-cut question is spec'd and waiting (2026-08-28)

`the-ninth-room-studio/docs/p10-beat-identity-spec.md`. Short version: a
built cut cannot be rebuilt today, and the reason is that beat ids are
free-form strings the `editplan` agent invents on each run — no
derivation, and the one id space in `schemas.py` with no uniqueness
check. A second run would land ~76 of hmns's 82 ids on a *different*
take, and `review.json` (your note history), `graphics_plan.json`,
`sfx_cues.json`, 81 baked captions and 82 proxies all key on that string.

Nothing is broken today. It only bites the day you want to re-cut, and
the spec says what it would take. Read it when you want to decide; there
is nothing to do until then.

## The hmns script needs the Narrated dial moved (2026-08-28)

Your Q8 = c answer took the two `desk` sections out of
`work/houston-museum-of-natural-science/script.json` — the hook and the
confession, 54 seconds of written performance — and made them
voice-over. That is a good call for the shoot and a bad one for the dial:
`story_brief.json` still says `vo_share` 0.20, and `script_notes` fails
any draft more than 10 points off it.

Round 2 passes at 29.0% only because I put two more quoted takes on
screen and compressed eight narration lines to get there. One point of
margin is left. The next narrated sentence anyone writes breaks the bar.

**Your call:** open `/studio/story/houston-museum-of-natural-science`,
press edit on the brief, and set Narrated to 30. It is Q14 in
`script_questions.json` with the alternatives, if you would rather cut
narration than move the number.

Second thing, same script, from Q9 = b: T112 now says on camera that the
tomb was built for a queen, and `research.json` has nothing behind it.
You said that blocks the lock. It is Q15 on the desk.

## Two coverage decisions the sourcer cannot make (2026-08-28)

Six rounds are waiting on the Assets desk for
`houston-museum-of-natural-science`. Two of them carry a decision that is
yours, not the sourcer's.

**1. The falling peg does not exist to buy.** CH3.S9 promises "it knocks
them over by itself" and that is the episode's payoff. I searched Pexels,
Pixabay and Wikimedia Commons: every free-licensed image of a Foucault
pendulum shows the ring with the pegs STANDING. Nobody has published a
reusable shot of one going over. The five candidates on that round are
all rings at rest. If the peg has to be seen falling, that is a return
trip to the Grand Hall with a camera — the pendulum is in the building
and takes just over seven seconds a swing.

**2. Approving the HMNS pendulum photo breaks CH3.S12.** Candidate 5 on
the CH3.S8 round is a Commons photo of *our* pendulum, in the Grand Hall,
CC BY-SA 4.0. It is the best-matching picture in the whole set. But
CH3.S12 says "everything you just watched swing was somebody else's
pendulum" — approve that candidate and the line stops being true and
needs a rewrite on the Script desk. Every other candidate on that round
is somebody else's pendulum and leaves the line alone.

## The edit plan is written and cannot be conformed yet (2026-08-28)

`work/houston-museum-of-natural-science/edit_plan.json` is written and
valid — 56 beats, all 40 script sections, 9m18s. It is a **picture edit
with silence where the narration goes**, because there are no `vo_*` files
in `footage/` and all 351 takes are `oncamera`.

**Twelve VO takes are yours to record** — one per VO section, at the names
the Script desk expects:

    vo_CH1-S2_r2   vo_CH1-S6_r1   vo_CH1-S10_r2  vo_CH1-S13_r2
    vo_CH2-S2_r2   vo_CH2-S6_r2   vo_CH3-S5_r2   vo_CH3-S8_r1
    vo_CH3-S9_r1   vo_CH3-S10_r2  vo_CH3-S11_r2  vo_CH3-S12_r2

CH3.S13 needs none — it is a deliberate 14-second wordless hold.

Until those land, each VO section sits in the plan as picture beats
carrying `spine` and `vo_pending`. When a recording ingests, its beats
take the take id and a trim; the shot choices stand.

Related, already on this list: the narrated share lands at **31%**, not the
brief's 20% (Q14), and the six sourcing rounds above are still unapproved —
so CH1.S10, CH1.S13, CH2.S6 and CH3.S8–S10 are covered from our own footage
and the plan's `why` lines say plainly what they do not claim to be.

## The storytelling overhaul — what needs your hands (2026-08-28)

The plan is approved and Phase 1 is built. These are the points where the
work stops and waits for you. Nothing here is urgent today; the order is
the order the phases need them.

- [ ] **The taste sign-off sitting (~30 minutes).** `brand/taste.md` holds 30
  statements mined from your own review verdicts, and its header bars every
  agent from citing any of them until you sign. Until that happens the craft
  rules get written from the film studies alone and your recorded taste stays
  locked out. The cards are prepared: read
  `docs/taste-signoff-cards.md` — one card per statement, in plain words,
  with its evidence and its catch. Answer keep / reject; "revise" only if you
  want different wording. Two need a real decision rather than a reflex:
  **T15** (eleven of the fourteen engagement card types died in your review)
  against `brand/engagement-playbook.md`, which still tells the
  graphics-director a card every 60–90 seconds is the whole retention
  strategy — and the confound is that the dead cards were only ever tried
  carrying placeholder text; and **T30**, whose source files were deleted
  with the crooise project and survive only in a job log.

- [ ] **Review the cut-bar calibration** (~10 minutes, before any gate goes
  live). Run `/usr/bin/python3 scripts/cut_report.py` in the engine repo. It
  grades every cut on disk against the new assembly bar. hmns comes back with
  24 findings and they are the four things you named: 78% of the episode is
  undifferentiated "build", the hook carries 2 covers instead of a chapter
  preview, no chapter declares a pace, and nothing is marked as a protected
  peak. Say whether any threshold is too strict before it starts failing
  jobs — every one is a single constant at the top of `pipeline/cutbar.py`.

- [ ] **Keep your own copy of `work/hmns/`** before the beat-id migration
  runs. It is the only shipped episode and its `review.json` is the evidence
  behind taste.md. The migration backs itself up and hardlinks the caption
  bakes rather than renaming them, so the shipped Resolve timeline stays
  linked — but a second copy costs you one command and removes the question.

- [ ] **The hmns benchmark re-screen** — the point of all of it. Once the
  re-cut job exists, hmns gets rebuilt under the new rules and you screen it
  against the version you shipped, clip by clip, same footage, old brain vs
  new brain. Your verdicts on the unchanged shots carry over, so you only
  judge what actually changed.

- [ ] **Drop 2–3 film-study links** on the new Film Studies desk once it
  exists (`/studio/studies`). Videos whose editing you admire. Each one gets
  broken down shot by shot and every finding lands as a row in the adoption
  ledger, so nothing agreed can quietly go unwired again — which is what
  happened to four findings already on the shelf.

## Two things the taste sign-off left open (2026-08-28)

The sitting is done — `brand/taste.md` is signed, 15 kept, 11 rejected, 4
revised, and every statement carries a dated verdict line. Agents may now
cite the kept and revised ones and nothing else. Two answers need a second
pass from you.

- [ ] **The landing rule — you asked to see it before deciding.** You kept
  T28 (a beat should end on a chosen outgoing image) and rejected T10 (the
  face delivers). Both point away from the BT94 decision, where you chose
  the "last fifth belongs to the face" gate and refused an escape hatch.
  Judge it at the hmns benchmark re-screen with both versions in front of
  you. Until then the gate stands as written and nothing cites T28.
  Recorded in `docs/decisions-cut-bar-calibration.md`.

- [ ] **You asked for a tool, not a taste rule, and it is not built.** Your
  answers to T2 and T5 asked to trim a clip with a scrubber during footage
  ranking, and to mute a clip so it becomes B-roll. Neither exists: today
  trimming only happens after the cut is built (a ±2s nudge on the Review
  desk), and there is no mute anywhere. Half of the second half already
  works under another name — promoting a take to the b-roll catalog makes it
  a cover, and covers carry no audio on the timeline. Say whether you want
  clip-range trimming added to the Footage desk; it is real new scope and it
  changes the review plan, because your reason for rejecting T5 was that
  trimming would stop you having to delete whole beats.

## Clip trimming is built and owes you a browser pass (2026-08-28)

You asked for it after the taste sign-off: trim a clip to its usable range
with a scrubber during footage ranking, so a clip with a bad walk-up or a
fumbled tail stops being all-or-nothing. It is built end to end — sidecar,
route, and the trimmer inside the Screener where the clip plays big.

- [x] ~~Engine restarted 2026-08-28 so the route exists at all~~ — the
  first attempt failed with "Range could not be saved" because the engine
  had been running for 5h46m and was serving code from before the feature.
  The route 404'd, which is why retrying could not help. Now documented in
  CLAUDE.md: editing `pipeline/` changes nothing until the service
  restarts.

- [ ] **Open the Footage desk against a real project and use it.** A green
  test suite is not a working feature and this repo's own rule says so.
  Press `s` to screen, then `i` to set the in point at the playhead, `o` for
  the out, `[` and `]` to nudge a frame, `\` to reset, then commit. Check
  the range survives a reload, then run an analysis and confirm the takes
  outside the range come back marked rather than missing.

Two things worth knowing about how it behaves:

**A trim never deletes a take.** Take ids are positional, so dropping one
would renumber every later take and silently re-point your built cuts at
different footage — the same class of bug the b-roll ids already suffered
once. So a take outside the range is marked unusable and keeps its id, and a
take straddling the edge is clipped in place with its transcript re-derived
from the words that survive.

**Trimming a clip an existing cut already uses is safe but loud.** The plan
validator will name any beat whose take the trim just put out of bounds
rather than letting it ship. Trim during ranking, before the cut, and the
question never comes up.

Still not built, and you may not need it: the "mute a clip so it becomes
B-roll" half of your T2 answer. Promoting a take to the b-roll catalog
already gets you most of it, because covers carry no audio on the timeline.
Say the word if you want an explicit mute anyway.
