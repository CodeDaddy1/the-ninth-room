<!-- Stamped 2026-09-16. Written from the interrogation of 2026-09-15 (nineteen decisions, Caleb) and two workflows: the subsystem map (wf_5cd9068b-f3a: six readers, a synthesis, a critic; 1.66M tokens) and the judged plan panel (wf_2b6dd5c5-5a7: three drafts, three judges, synthesis, adversarial verify with twenty-six findings, revise; 2.39M tokens). Function and test names spot-checked against the tree the same night. Status: AWAITING CALEB'S REVIEW; nothing below is built. -->

# Plan: Illustrations (Higgsfield + Blender)

Four words: a **ratchet** is a test that only gets stricter; a **gate** is a check before something expensive, refused as `declined`, never `failed`; a **ledger row** records one purchase and its cost; **provenance** is a stored fact about where a picture came from (camera, illustration, reconstruction).

## 1. Context

**The problem.** The pipeline has no lane for a picture no camera can film. The only generated set, nine monarch rows in `work/hmns/assets/assets.json`, came from a hand session outside any job: `kind: "generated"`, the beat smuggled into `query`, no cost, no lock, "insert" in every row.

**What exists today.**
- Sourcing is the only spend gate: `jobs._run_sourcing` (jobs.py 1986) proposes through `_dispatch_json` and writes nothing under `assets/`; Caleb approves per round through `editroom._asset_round_verdict` (4955, status plus an optional candidate index, nothing else); fetch appends rows through `capture.append_to_manifest`, which has no lock and no cost field.
- The library door: `editroom._use_asset` (5131) symlinks a video into `footage/` or bakes a still into a six second landscape clip through `_still_to_clip` (4924); `ingest` (433 to 445) bakes EVERY portrait clip into a landscape fill and redirects the catalog to it, gated on `fill.is_portrait` alone, never on the project's orientation; `broll.catalog_broll` (broll.py 217) carries only `description`, `framing`, `tags`, `manual_tags` across re-analysis.
- Placement: `editroom._broll_attach` (725) writes a cover with no `why`, runs only `_clamp_cover` (592) and measures the beat as `record_e - record_s` from `timeline_map.json` (cuts removed); `schemas.coverage_notes` (333) measures `trim.e - trim.s` (cuts kept), is called at one site (jobs.py 1809, `_run_coverage`) and never at promote: `promote.promote_cut` runs `validate_edit_plan` and `cutbar.cut_notes` only (promote.py 107, 148, 160). `cutbar._hook_notes` (412) returns nothing under `LONG_FORM_CHAPTERS` (three), so it is silent on a short. On `shot-T41` the two lengths are five point three eight seconds and six point five seven seconds.
- Colour: `build_api.py` 149 to 154 grades every spine and cover file through `color.apply_grade` (303), which reports `untouched=`; only overlay roots are skipped; that code runs only from `produce.produce()` (254 to 279, the Resolve build), never from `_run_assemble` (jobs.py 367: `build_timeline` plus `proxy.build`). `_delete_asset` (5113) has no in-cut check; `_delete_footage` (3716) has one via `_footage_uses` (3663). `_bake_thumbnail` (1626) reads the beat proxy, which composites covers. `deliver.checklist` computes `ready = all(r["ok"] for r in rows)` (deliver.py 230).
- Graphics: a `section` card must carry `text` (schemas.py 1207); the graphics session writes the WHOLE `graphics_plan.json` (`GRAPHICS_PROMPT`, jobs.py 1060) and `CHAIN` runs graphics to reproxy, assemble to retention (2166). `overlay_kit.RENDERERS` learns a kit only by a bare import at the file's tail (2136 to 2138). `validate_graphics_plan` (1106) has no overlap check; graphics-director.md line one hundred eleven forbids two cards at once.
- Jobs: twenty-six kinds in `jobs.KINDS` (2124), each in `SESSION_KINDS` or `LOCAL_KINDS`, ONE worker per lane (70 to 89); no `sound` kind exists, so nothing runs the sound-designer brief. Two launch sites (`_dispatch` 1412, `_dispatch_json` 1629) with permissions skipped and the launchd PATH (`/usr/local/bin/higgsfield` on it). A `JobError` from `jobs.start()` (2462) is a 400 from `/api/job/start` (editroom.py 6024) with no row; one from a runner lands `declined` WITH a row.
- Higgsfield CLI 1.1.25: `account transactions` takes `--size` and `--cursor` only and returns `{action, created_at, credits, display_name}` items, no job id; media flags on `generate create` AND `generate cost` accept a UUID or a local path, and a path is auto-uploaded; `kling3_0` takes `aspect_ratio, duration, end_image, mode (std|pro|4k), prompt, sound, start_image` and no Soul reference; `custom_reference_id` exists only on `text2image_soul_v2` and `soul_cinema_studio` (with `quality`). The balance is read live (eight hundred fifty at last read), never quoted; two hand Seedance 2.5 spends tonight (one refunded) sit in no ledger.
- Blender (uncommitted): `blender_title.build_title` (137) takes no canvas (1920x1080 against cards at 3840x2160); no `subprocess.run` timeout; no kit_type, no cache key; twenty-eight point six seconds per card against a fifteen second target.
- Paper: CLAUDE.md line forty-two "$0/mo is binding" and hard rule twenty-one (promote LINKS); README line sixteen and `docs/blender.md` line one hundred eight say "inserts"; CONTEXT.md line seventy-five bans it; `story-director.md` line thirty-six calls `brand/taste.md` unsigned though it is SIGNED 2026-08-28; story-designer.md gives a footage-lane beat no way to ASK for a picture (all eighty-two hmns beats carry a `note`).
- Studio: a new kind needs the `jobStart` union (`engine.ts` 1352), `DESK_OF_KIND` and a `<JobRunButton>`; `VisualFrom` (engine.ts 566) is a closed union; `licence.ts` matches no Higgsfield string, so the nine rows read `attention`.

**The outcome.** One one-shot craft, illustration-director, proposes priced illustrations; Caleb approves per round and marks Seedance or pro where he wants them; the engine generates under a three hundred credit cap with a locked ledger row per spend, reconciled against the balance delta and Higgsfield's transaction window. Provenance survives into `broll.json` and the timeline map and drives every rule below.

## 2. Locked decisions (Caleb, 2026-09-15)

| # | Decision, one line |
|---|---|
| 1 | Illustrations plus photoreal RECONSTRUCTIONS of unfilmable things, marked on screen. Never the real place as generated footage. Never a fake of a real person. |
| 2 | Higgsfield scope: illustrations (b-roll), thumbnails and Shorts covers, GLBs for Blender turntables. No audio. |
| 3 | The agent PROPOSES with a cost estimate; Caleb approves the round on the Library desk; only then GENERATE. Mirrors sourcing. |
| 4 | Generated files land on the Library desk as `assets.json` rows; Caleb promotes them; today's flow. |
| 5 | A Soul of Caleb only (cinematic, "Caleb", trained tonight); the family never goes to Higgsfield. Uses: host presence inside a marked reconstruction; Shorts covers and thumbnails with motion. Never to fill a missed to-camera line. |
| 6 | The kit eyebrow RECONSTRUCTION for the clip's length plus a YouTube altered-content line at publish. A stylised illustration carries provenance in data only. |
| 7 | Three hundred credits an episode; std by default; pro per item on request; every spend gets a ledger row. |
| 8 | Blender Template one (3D titles) first, as new kit_types BESIDE the CSS cards. |
| 9 | Consult by artifact: one one-shot craft; runner-built prompt; self-critique with stable ids. No relay, no subagents, no room loop. |
| 10 | The storyteller is story-director (script lane) or story-designer (footage lane); the visual director is overlay-designer's design language, borrowed, not called. |
| 11 | Noun "illustration"; craft illustration-director; manifest and round kind `illustration`; "insert" scrubbed from README, docs/blender.md and the nine hmns rows. |
| 12 | The NEXT fresh episode runs the full lane. hmns takes the monarch set through the desk attach route only; no recut. |
| 13 | An illustration MAY depict a filmed thing as an `illustrate` cover when the footage is weak; never `establish`; never in the hook. A machine rule keyed on provenance enforces this. |
| 14 | Beside is LATER. The five cover justifications are reused now; the brief names beside as the preferred future shape; wiring it is the first follow-up. |
| 15 | A Credits section naming the model; a YouTube disclosure line when a reconstruction is in the cut. Export never blocks on a licence. |
| 16 | One placed cue per wordless illustration run, written by the sound-designer, whose brief gains the category. |
| 17 | Engine calls delegated to Claude, flagged **[D17]** below: a locked manifest row per spend with cost (the sfx manifest shape); named preconditions for the new kind in a small new module, existing kinds unchanged; the delivery aspect on the request and honoured by the still door; illustrations exempt from LUT and CDL via a provenance flag in build_api/color; `/api/broll/attach` requires a `why` once illustrations exist; `_delete_asset` gains the delete guard; `broll.json` carries `provenance` derived from the manifest at catalog time; a generated frame is never the automatic thumbnail; CLAUDE.md's binding line amended in the same PR as the gate; story-director.md line thirty-six corrected; the brief overrides the skill's "Don't pre-estimate cost". |
| 18 | Default video Kling 3.0 std, sound off, five seconds (seven and a half credits), upscaled to the delivery frame; Seedance 2.5 only on a round Caleb marks; Kling turbo tested once before adopting. |
| 19 | The sixteen earlier answers stand; the whole list is final. |

One implementation call, flagged and NOT yet Caleb's: GENERATE dispatches no session. An approved round is a complete instruction and mechanical work fires on its own (hard rule five); a session with permissions skipped never holds the CLI while credits move. Decision 3 names the agent as the actor, so this changes the actor, not the order: P4 does not start until the ADR carries Caleb's one-line yes (open item one). If he says no, P4 dispatches the agent for generate behind the P3 shim with `create` unlocked for the approved steps only, and the runner remains the only writer of ledger rows, from the create's JSON.

## 3. The lane in one paragraph

Story-director writes a `vo` section with `visual.from: "illustration"`; story-designer writes the same `visual {want, why, from}` block on a footage-lane beat. Caleb presses Propose illustrations on the Library desk; `jobs.start("illustrate", slug)` runs the `ILLUSTRATE_PROPOSE` predicates in `pipeline/preconditions.py` (a refusal is a 400; `arg == "generate"` selects `ILLUSTRATE_GENERATE`); `_run_illustrate` (session lane) repeats them, reads `higgsfield account status`, builds the prompt with `_illustration_clause` and dispatches ONE session whose PATH leads with a read-only `higgsfield` shim. The agent writes only `work/<slug>/staging/illustration_rounds.json`; the runner validates each round with `illustration.validate_round`, appends them to `asset_requests.json` at `proposed` through `editroom._ensure_round_ids`, and proves the balance and the `assets/` file count unchanged. Caleb approves through `POST /api/asset/round`, marking `seedance` or `pro` there if he wants them. Generate runs `illustration.spend` per approved step (one locked operation: create, a `pending` ledger row with the job id, wait, download, probe, finalize); `illustration.reconcile` matches the balance delta and the transaction window against the ledger. `_use_asset` upscales to the delivery canvas and writes `promoted_as`; `ingest` gives a B-id and `catalog_broll` derives `provenance` from the manifest. A cover is placed through `/api/broll/attach` with a required `why`; `schemas.validate_edit_plan` refuses a `provenance` clip on `establish`, in `cutbar.hook_beat_ids(plan)`, on a peak, over the ratio or in the landing, measured by one `beat_span` helper, at the desk, at coverage and at promote; `timeline.plan_beats` copies `provenance` onto the cover; `build_api` leaves it out of `camera_files`; `illustration.sync_markers` writes RECONSTRUCTION kit cards after every graphics, reproxy and assemble run; publish-writer writes `# Credits` and the disclosure.

## 4. Phases

Engine suite: `/usr/bin/python3 -m unittest discover -s tests -t .` in `~/Projects/the-ninth-room`; Studio: `npm test` in `~/Projects/the-ninth-room-studio`. After any `pipeline/` edit: check `work/_jobs.json` for a running job, then `launchctl kickstart -k gui/$(id -u)/com.ninthroom.engine`.

### P0. Vocabulary and paper

**Goal.** Fix the words before the code inherits them; commit the Blender seam.

**Changes.**
- Commit the uncommitted Blender seam as-is on a branch.
- `CONTEXT.md`: add **Illustration** (a generated picture of a thing no camera filmed, or a stylised cover of a thing it did; avoid: insert), **Reconstruction** (a photoreal illustration, marked on screen and in the description), **Provenance**, **Ledger**.
- `docs/decisions-illustrations.md`: an ADR with the nineteen decisions; the generate-actor question left open for Caleb's line; the upscale choice (an ffmpeg resample now, a listed upscale model later behind the same ledger); the retired v1 briefs read at `16206bf^` (asset-scout's per-platform orientation, visual-director's "show the gap, not the answer"), each rule adopted or rejected by name; a measurements section.
- `CLAUDE.md` line forty-two: "no Anthropic API calls; $0/mo by default" (the per-round approval clause lands in the P4 PR beside the gate). Rule six: a Blender kit_type's HTML stand-in is its canvas. Hard rule twenty-one: promote links, except an illustration, which is resampled to the delivery canvas (ADR).
- `README.md` line sixteen: "illustrations for things no camera could film". `docs/blender.md` line one hundred eight: "first illustrations". `story-director.md` lines thirty-six to thirty-seven: "`brand/taste.md` is SIGNED 2026-08-28; cite only `kept` and `revised` statements."
- `scripts/rewrite_hmns_illustrations.py` (run once, deleted after) rewrites the hmns rows: `kind: "illustration"`, `honesty`, `beat_id: "shot-T41"`, `note` replacing `query`, `license: "Higgsfield ToU: output owned, commercial use permitted"` with the long sentence in `license_note`, `cost_credits`, `model` ids.

**Definition of done.**
- `grep -niE "\binserts?\b" README.md docs/blender.md work/hmns/assets/assets.json`, `grep -n "is binding" CLAUDE.md` and `grep -n "It is unsigned" .claude/agents/story-director.md` all return nothing.
- A one-line python over `work/hmns/assets/assets.json` prints `{'illustration'} 38.0` for the set of kinds and the credit sum.
- The Blender seam is committed; the suite is green.

**Risks and mitigations.** README and CLAUDE.md disagree until this lands: P0 lands first, alone, and promises no gate the code lacks.

**Tests.** Add `tests/test_illustration_vocabulary.py`: the greps above; the nine rows carry `kind`, `honesty`, `beat_id`, `cost_credits`. Do not break `tests/test_paths.py`.

**Who.** `mattpocock-skills:domain-modeling` for CONTEXT.md and the ADR; `mattpocock-skills:writing-for-agents` for the story-director edit; `mattpocock-skills:code-review`.

### P1. Provenance survives and the silent doors close (no credit)

**Goal.** Make `illustration` a first-class kind that survives promotion, ingest and assembly; close every door that would misgrade, dangle, misplace or mis-thumbnail one. Verified on the hmns monarch set, no new spend.

**Changes.**
- `pipeline/illustration.py` (new): `HONESTY = ("illustration", "reconstruction")`, `provenance_of(assets_dir, name)` (matches `promoted_as`, then `file`, then `<stem>_still.mp4`), `exempt_files(slug)` (pure over `broll.json`).
- `broll.catalog_broll` (carry block near 310 to 335): `"provenance": provenance_of(...)`, only when set; absent means camera. `schemas.validate_broll` (113): optional `provenance` in `HONESTY`. `timeline.plan_beats` (171): copy `provenance` onto each cover entry and spine beat in `timeline_map.json`.
- `build_api.py` 149 to 154: extract pure `camera_file_names(tl_map, by_name)` skipping any file with `provenance`; log `[color] N illustration file(s) left ungraded`; after `apply_grade` assert the `untouched=` count is at least N, else `IngestError`. `color.grade_live_timeline`: skip `exempt_files(slug)` beside overlay roots. **[D17]**
- `schemas.beat_span(beat)` (new, pure): the record span after `cuts`, the number `_broll_attach` already reads from the timeline map; `coverage_notes` and `_broll_attach` both read it, so the ratio and the landing agree on every beat with cuts. `cutbar.hook_beat_ids(plan)` (new, pure, NOT gated on `LONG_FORM_CHAPTERS`): beats before the first `chapter_open`; `_hook_notes` keeps its gate for the montage prose only.
- `schemas.validate_edit_plan` (already takes `broll`): a cover whose clip carries `provenance` is an error on `establish`, in `hook_beat_ids`, on a `peak` beat, over `COVER_MAX_RATIO` of `beat_span` or landing in the last fifth. It fires at promote (promote.py 107, 148), at coverage (jobs.py 1803) and at the desk. **[D13, D17]**
- `editroom._broll_attach` and route (5874): accept `why`; once the catalog holds any `provenance` clip, require `schemas.why_kind(why)`; run `validate_edit_plan` on the candidate plan and refuse with its first error; write `why` into the entry.
- `editroom._use_asset`: write `promoted_as` (the `_uniquify` result) onto the row; an illustration video is scaled to `timeline.CANVAS[_orientation(slug)]` with ffmpeg rather than symlinked: Kling std returns 1284x716 and there is no `.LRF` sibling. **[D18]** `_still_to_clip` takes `orientation`; a pure `_still_to_clip_args(inp, clip, orientation)` returns the argv so a test pins portrait 2160x3840. **[D17]**
- `ingest` 433 to 445: the landscape fill runs only when the project's delivery orientation (through `schemas.delivery_shape`) is landscape; a portrait project keeps a portrait plate native, so a Short receives the 2160x3840 plate and not the centre of a fill. **[D17]**
- `editroom._delete_asset`: resolve the promoted name, call `_footage_uses`, refuse with the existing `in_the_cut` or `take_in_cut` code, move nothing. **[D17]**
- `editroom._bake_thumbnail`: if the beat's spine or any cover spanning `at` carries `provenance` in `timeline_map.json`, refuse "that frame is an illustration; pick a camera frame". **[D17]**
- `editroom._assets_state` (5018): keep `kind` when `illustration`; add `media_kind` (by suffix, for the player); pass the row's extra fields through. Studio: `SourcedAsset.kind` gains `'illustration'` plus those fields; `licence.ts` CLEAR gains `/higgsfield tou/i`; `sourced-assets.tsx` shows a badge, model and credits; `AttachToClip` (116) and `engine.brollAttach` (1329) gain a required `why`.

**Definition of done.**
- `POST /api/asset/use` on `monarch-1-egg`: `ffprobe` on the footage file prints `3840,2160`; the row carries `promoted_as`; after ingest `broll.json` shows `provenance: "illustration"` and a second ingest keeps it.
- `POST /api/broll/attach` on `shot-T41` (`beat_span` five point three eight seconds) with `why: "illustrate: the egg on the board he is pointing at"` and duration three seconds is placed; `establish`, no `why`, or duration three and a half seconds (over sixty percent) each return 400. `POST /api/asset/delete` for the promoted row returns 400 `in_the_cut`.
- `curl -s 'localhost:8765/api/assets?slug=hmns' | python3 -c "import sys,json; a=json.load(sys.stdin)['assets']; print(sum(x['kind']=='illustration' for x in a), sum(x.get('needsClearing',False) for x in a))"` prints `9 0`; a vitest on `licenceState` returns `clear` for the canonical string.
- `test_camera_file_names` proves the exemption; the render job's log on hmns (`build_api.build` through `produce.produce`) prints `[color] 1 illustration file(s) left ungraded`. Assemble is not the proof (it never grades, and its chain would dispatch a retention session on hmns).
- A portrait temp project ingests a 2160x3840 plate with no `_fill` companion.

**Risks and mitigations.** Provenance dies at a `_uniquify` rename: `promoted_as` is the source of truth, filename the fallback. Every switch on `a.kind` gets a case; `vercel:react-best-practices` after.

**Tests to add.** `tests/test_illustration_provenance.py` (catalog derives and survives re-analysis, `validate_broll`, `plan_beats`, `camera_file_names`, `grade_live_timeline`, the ingest fill gate). `tests/test_illustration_rules.py` (`beat_span` with and without cuts, agreed by both callers; every `validate_edit_plan` provenance error; `hook_beat_ids` on a two-chapter short; every `_broll_attach` refusal; `_delete_asset` guard; `_bake_thumbnail` refusal; `_use_asset` upscale; `_still_to_clip_args` portrait). Studio: `licence.test.ts`.

**Ratchets not to break.** `tests/test_broll_merge.py`, `tests/test_broll_catalog.py`, `tests/test_footage_delete_guard.py` (twenty-one), `tests/test_broll_adjust.py`, `tests/test_coverage_notes.py` (thirty-six), `tests/test_cut_bar.py`, `tests/test_cut_promote.py`, `tests/test_picture_beats.py`, `tests/test_peak_protection.py`, `tests/test_error_codes.py`, `tests/test_beat_glob_ratchet.py`, `tests/test_kind_has_one_home.py`. Studio: `licence.test.ts`, `library.test.ts`, `pipeline.test.ts`.

**Who.** `mattpocock-skills:tdd`, red first on each door; a Studio subagent; `mattpocock-skills:code-review`.

### P2. The gate, the ledger, the cap and the binary path (no credit)

**Goal.** Everything generate needs to refuse, count and lock exists and is tested before the kind is registered.

**Changes.**
- `pipeline/paths.py`: `higgsfield_bin()` = `NINTH_ROOM_HIGGSFIELD_BIN` env, then `.env`, then `shutil.which("higgsfield")`, the `claude_bin()` shape; `soul_id()` = `setting("NINTH_ROOM_SOUL_ID")`.
- `pipeline/illustration.py`: `EPISODE_CREDIT_CAP = 300`; `DEFAULT_VIDEO` (`kling3_0`, `mode: std`, five seconds, sound off, seven and a half credits); `DEFAULT_PLATE` (`nano_banana_pro`, `2k`, two credits); `SOUL_MODELS = ("text2image_soul_v2", "soul_cinema_studio")`; `SEEDANCE_MODEL`; `TURBO_MODEL = "kling3_0_turbo"` (a model id, not a tier); `TIER_FIELD = {"kling3_0": "mode", ...: "quality"}`; `_ILLUSTRATION_LOCK`; `ledger(slug)`, `spent(slug)`, `channel_ledger()` (`work/_channel/higgsfield_ledger.json`, one row per hand spend: the Soul training, tonight's two Seedance runs); `append_row(assets_dir, row)` = `capture.append_to_manifest` under the lock, refusing a row without `cost_credits`, `model`, `job_id`, `honesty`, `status` **[D17]**; `cli(args, timeout)` wrapping every Higgsfield call with a timeout; `validate_round(round_, delivery, script=None, plan=None)`: kind `illustration`; exactly one of `section_id`/`beat_id` naming a real one; `honesty` in `HONESTY`; `target` in cover, run, thumbnail, short_cover, where `run` is accepted only on the footage lane (it enters the cut as a story-designer picture beat, `BEAT_KIND_PICTURE`, never through the desk); `aspect` equals the delivery shape except for the last two; `why` leads with a `COVER_WHYS` word other than `establish`; each step has `stage`, `model`, `prompt` (short, no `#` hex, no "insert"), `credits`, the model's tier field defaulting to `std`; a non-std tier needs a `reason` AND the round's `marks.pro` naming the stage; a Seedance step needs `marks.seedance` **[D7, D18]**; `estimate_credits` equals the sum; `sources` and `disclosure` required on a reconstruction; `soul: true` only on a plate stage whose `model` is in `SOUL_MODELS` (Kling takes no Soul; the host enters a reconstruction as a Soul plate the motion step animates through `start_image`), only with honesty `reconstruction` or a thumbnail/short_cover target, and only on a `vo` section or a take-less beat **[D5]**; `note` may record where beside would have served **[D14]**; `cap_check(slug, rounds)` raising when `spent + estimates > 300`.
- `pipeline/schemas.py`: `VISUAL_FROM` (1339) gains `"illustration"`; `_NOT_SOURCED` (1882) gains it in the SAME commit; `superseded_requests` (1942) also retires an `illustration` round whose section moved on or whose `beat_id` left the plan; `unproposed_sections` (1976) gains `exclude_from=("illustration",)` for the sourcer. `validate_edit_plan` accepts an optional `visual {want, why, from}` block on a beat.
- `pipeline/preconditions.py` (new): `Predicate(id, message, surface, check)`; `ILLUSTRATE_PROPOSE` = `project_exists`, `has_story` (script lane: `script.json` `locked`; footage lane: `edit_plan.json` and `analysis/broll.json`), `has_targets` (both lanes: a section or beat with `from: illustration` and no live round), `higgsfield_cli_present`, `cap_headroom`; `ILLUSTRATE_GENERATE` adds `rounds_approved`, `cap_fits`, `soul_available`, `marks_consistent`. `RETRYABLE = {("illustrate", None): True, ("illustrate", "generate"): False}`. No import of `jobs`; existing kinds untouched. **[D17]**
- `pipeline/cli.py`: `illustrate-check <slug>` prints round validation, `spent`, the channel ledger total, the cap and the balance. `asset-sourcer.md` and `jobs.SOURCING_SCRIPT_LANE` (1949): "illustration: do NOT propose stock". `story-director.md`: `illustration` as a sixth `from` with the honesty rule. `story-designer.md`: one line, a beat may carry `visual {want, why, from: "illustration"}` when the footage is weak or the thing was never filmed.
- Studio: `VisualFrom` (engine.ts 566) gains `'illustration'`; the Script desk's section renderer shows it; a test.

**Definition of done.**
- `NINTH_ROOM_HIGGSFIELD_BIN=/tmp/x` makes `paths.higgsfield_bin()` print `/tmp/x`; unset, `/usr/local/bin/higgsfield`.
- `python3 -m pipeline.cli illustrate-check hmns` prints nine ledger rows, `spent 38.0 of 300`, and the channel ledger beside it.
- A locked script with `from: illustration` passes `schemas.script_notes`; `unproposed_sections` with the exclusion reports nothing for it; a footage plan with the `visual` block passes `validate_edit_plan`.

**Risks and mitigations.** If `VISUAL_FROM` gains `illustration` before `_NOT_SOURCED` does, a stale stock round for a section that moved to `illustration` stays live and a fetch buys stock: one commit, pinned both ways.

**Tests to add.** `tests/test_illustration_gate.py`: every `validate_round` refusal by name (Soul on Kling, pro without a mark, Seedance without a mark, `run` on the script lane); `cap_check` at two hundred ninety-nine and a half plus seven and a half; `append_row` refuses a row without cost and holds the lock; `superseded_requests` both lanes; `unproposed_sections` exclusion; `higgsfield_bin` precedence; `cli` timeout; `channel_ledger` totals. `tests/test_preconditions.py`: every predicate refuses on a bare temp dir, `has_targets` both lanes, `RETRYABLE` has both entries, `test_existing_kinds_are_untouched`. Studio: a `VisualFrom` test.

**Ratchets not to break.** `tests/test_sourcing.py`, `tests/test_script_lanes.py`, `tests/test_documentary_lane.py`, `tests/test_capture.py`, `tests/test_paths.py`, `tests/test_script_bar.py`, `tests/test_picture_beats.py`.

**Who.** `mattpocock-skills:tdd`; `mattpocock-skills:writing-for-agents` for the brief lines.

### P3. The kind, the runner, the clause, the brief, the shim, the style file, the Studio mirror: PROPOSE only

**Goal.** Register `illustrate` and prove a propose session CANNOT spend or upload. The `generate` arg is coded but declines until P4 flips it.

**Gates before a dispatch.** In `jobs.start()`: the existing checks, then every `ILLUSTRATE_PROPOSE` predicate as `JobError` (a 400, no row), or every `ILLUSTRATE_GENERATE` predicate when `arg == "generate"`. In `_run_illustrate`, repeated (landing `declined`), plus the one network check: `higgsfield account status --json` returns credits (an expired session is `declined`).

**The shim.** `bin/higgsfield-readonly` (a python script named `higgsfield`, in its own directory prepended to PATH by `_dispatch_json` for this kind only): forwards `account`, `model` and `generate cost` to `paths.higgsfield_bin()` when every media flag is a UUID; exits non-zero with a one-line reason on `create`, `workflow`, `upload`, `soul-id`, or any argument that resolves to a local path. Detection after the fact is not a gate; the shim is.

**Changes.**
- `pipeline/jobs.py`: `KINDS["illustrate"] = ("Illustrate: pictures no camera can film", _run_illustrate)` four-space indented, no em dash; `SESSION_KINDS` gains it; `CHAIN` gains nothing; `start()` selects the predicate set by `arg`; `_run_illustrate(slug, log, set_pct, arg=None)` in the `_run_sourcing` shape: predicates, balance, `before = (assets file count, credits)`, `_dispatch_json` with the shim PATH, read the staging file, `validate_round` each, `cap_check`, append to `asset_requests.json` at `proposed` through `_ensure_round_ids`, then post-checks: `assets/` count and credits unchanged; a no-op fails only when `has_targets` still finds an unillustrated section or beat.
- `brand/illustration/plate.md`: the signed style contract, two blocks (Plate, Reconstruction) with `{{navy_900}}`, `{{chalk}}`, `{{slate_300}}` placeholders resolved by the runner through `design_tokens.load()` and `resolve()`; no `#` hex in the file; signed by Caleb statement by statement.
- `.claude/agents/illustration-director.md` (section five), `tools: Read, Write, Bash, Glob`; `_illustration_clause(slug)` pure beside `_sourcing_prompt` (section six).
- Studio: `jobStart` union gains `'illustrate'`; `DESK_OF_KIND.illustrate = '/studio/takes'`; `TakesView.tsx` beside the sourcing fetch button (1012): `<JobRunButton kind="illustrate">` labelled "Propose illustrations" and a second with `arg="generate"` labelled "Generate N approved (about M credits)", enabled in P4; `SourcingRounds` (955) renders an `illustration` round with Approve, Skip, a Seedance toggle and a per-stage Pro toggle that post `marks` through `POST /api/asset/round` (`_asset_round_verdict` gains `marks`); `AssetRound.kind` gains `'illustration'`.

**Definition of done.**
- `grep -nE '^\s{4}"illustrate":' pipeline/jobs.py` matches once; `npm test` passes `job-kinds.test.ts` both directions.
- Kickstart; `curl -s -X POST localhost:8765/api/job/start -d '{"kind":"illustrate","slug":"<unlocked>"}'` returns 400 whose `error` names the Script desk; with `"arg":"generate"` and nothing approved, 400 naming the round; `work/_jobs.json` gains no row either way.
- On a temp script-lane project with one `from: illustration` section: the propose job ends `done`, one `illustration` round appears with an estimate, `assets/` count and credits are identical before and after (the log prints both); the shim's log shows every call it forwarded and none it refused.

**Risks and mitigations.** The session tries to spend or upload during propose: the shim refuses before the network; the credits-unchanged post-check is the second net. An unclassified kind falls to local: `test_every_registered_kind_has_a_lane`. A Higgsfield auth failure stays uncoded (`EXPLAINED_CODES` is pinned in `tests/test_error_codes.py`).

**Tests to add.** `tests/test_illustration_job.py`: kind in `KINDS` and `SESSION_KINDS`; `lane_of("illustrate") == "session"`; `CHAIN.get("illustrate") is None`; each predicate of both sets refuses before enqueue with no dispatch; the runner repeats the guards and lands `declined`; every propose post-check both ways; the shim is first on the dispatched PATH; the shim forwards `generate cost` with a UUID, refuses it with a local path, refuses `create`, `workflow`, `upload`, `soul-id`; `test_the_story_reaches_the_illustrator` and `test_the_cut_reaches_the_illustrator` (section six). `tests/test_illustration_brief.py`: the brief names I1 to I10, `illustrate-check`, both honesty words, `RECONSTRUCTION`, "never call `higgsfield generate create`", "never pass a local path to any Higgsfield flag", the override sentence, `beside`, `SOUL_MODELS` by name, never "insert"; `plate.md` has no `#` hex and every placeholder resolves.

**Ratchets not to break.** `tests/test_job_lanes.py`, `tests/test_dispatch_is_shared.py`, `tests/test_exception_policy.py`, `tests/test_job_history.py`, `tests/test_walk_the_documentary.py`, `tests/test_recut_job.py`; Studio `job-kinds.test.ts`, `desk-of-job.test.ts`, `vocabulary.test.ts`.

**Who.** `mattpocock-skills:tdd`; `mattpocock-skills:writing-for-agents` for the brief and style file; a Studio subagent; `mattpocock-skills:code-review`.

### P4. GENERATE: the first engine credit, on the worker thread, reconciled

**Goal.** Spend through one door, ledger every credit as the same operation, reconcile against the balance and Higgsfield's transaction window after every run. Starts only with Caleb's yes in the ADR.

**Changes.**
- `pipeline/illustration.py`: `spend(slug, round_id, stage, log)`: skip a step already `done` (idempotent by `round_id + stage`, which is why the job need not be retryable); `cap_check`; apply the round's `marks` (a Seedance mark swaps the video model, a pro mark sets the tier field); re-run `higgsfield generate cost` and refuse if it exceeds the estimate by more than ten percent; resolve `start_image` to the plate's `job_id` (never a local path); read the balance; run `higgsfield generate create <model> ... --json` WITHOUT `--wait` through `paths.higgsfield_bin()` (`--soul-id paths.soul_id()` only on a `SOUL_MODELS` step); `append_row` a `pending` row at once with the create's `job_id`, the model and the `generate cost` figure; then `higgsfield generate wait <job_id> --wait-timeout 20m --json`; download into `assets/<round>-<stage>.<ext>`; probe (refuse a short clip); read the balance again and set `cost_credits` to the delta when it differs from the estimate; finalize the row `done` under the lock; mark the step, then the round, `done`. A death between create and download leaves a `pending` row to finalize on rerun, never a stray to re-spend. `reconcile(slug, window_start)`: page `higgsfield account transactions --json` by `--cursor` back to `window_start`; match each item by `(display_name, credits, created_at within the window)` to a ledger row of that run; the balance delta must equal the run's ledger sum; return unmatched items and unmatched rows.
- `jobs._run_illustrate` with `arg == "generate"`: `ILLUSTRATE_GENERATE` predicates; `window_start = time.time()`; no dispatch; loop `spend` over approved rounds, `set_pct` per step; a step failure records `error` on the round, keeps it `approved`, fails the job naming the step; post-checks: every new row has `job_id`, `cost_credits`, `honesty`, `status: done` (a `pending` row fails the job naming it); `spent(slug) <= 300`; `reconcile` returns nothing, else `RuntimeError("N credit(s) unaccounted")`. `illustrate-spend <slug> <round_id> <stage>` joins `cli.py` for a hand rerun. Enable the P3 button. Generate holds the session lane's single worker for up to twenty minutes a step; stated and accepted for the pilot (a `spend` lane is a follow-up, section eight).
- `CLAUDE.md` line forty-two, this PR: "three opt-in paid paths, each behind a per-round approval on the Library desk". **[D17]**
- Kling turbo: one hand test by Caleb (`kling3_0_turbo`, ten credits) against a std clip of the same plate, recorded in the ADR and the channel ledger. **[D18]**

**Definition of done.**
- Real: approve one round on the P3 project (a plate and a Kling std clip, nine and a half credits): the job ends `done`; `illustrate-check` prints two `done` rows summing to nine and a half and no `pending`; `higgsfield account status --json` before minus after equals nine and a half; `higgsfield account transactions --size 5 --json` holds two items in the window whose `display_name` and `credits` match the rows; a second click returns 400 before any row.
- With the CLI stubbed to die after create: one `pending` row; `illustrate-spend` finalizes it without a second create.

**Risks and mitigations.** `nsfw` or `ip_detected`: `spend` raises, writes no file, and the `pending` row is finalized `refused` at zero credits (Higgsfield refunds) so the ledger still explains the transaction. Network death mid-step: the rerun finalizes `pending` and skips `done`.

**Tests to add.** `tests/test_illustration_spend.py` with a stubbed CLI: one row per spend, `pending` before wait, idempotent stage, marks applied, cap at the boundary, the ten percent refusal, local path refused, Soul id only on Soul models, short download refused, `reconcile` on a matched window, on a stray item and on a stray row, the runner's post-checks.

**Ratchets not to break.** `tests/test_dispatch_is_shared.py`, `tests/test_paths.py`, `tests/test_capture.py`, `tests/test_job_lanes.py`, `tests/test_production_board.py`.

**Who.** `mattpocock-skills:tdd`; Caleb presses the button; `mattpocock-skills:code-review`.

### P5. Ship gates: the marker, the sound category, the credits, the disclosure, the checklist row

**Goal.** A reconstruction cannot reach a master unmarked or uncredited; export never blocks on a licence.

**Changes.**
- `pipeline/marker_kit.py` registers `"provenance"` into `overlay_kit.RENDERERS` and is imported at overlay_kit's tail beside `vfx_kit` and `checklist_kit` (2136 to 2138), plus a template into `editroom._KIT_TEMPLATES` (1526): the existing `_eyebrow` primitive, CYAN, kicker "RECONSTRUCTION", inside the safe inset, both orientations. `illustration.sync_markers(slug)`: for every cover or spine with `provenance == "reconstruction"` ensure cards `{id: "MARK<n>", type: "section", kit_type: "provenance", text: "RECONSTRUCTION", beat_id, at, duration}` in `graphics_plan.json` (the `section` type requires `text`, schemas.py 1207), split under the fifteen second ceiling `validate_graphics_plan` (1106) enforces; remove orphans. Called AFTER validation in `_run_graphics` (the session rewrites the whole file, so the runner re-syncs), in `_run_reproxy`, from `_broll_attach`, `_broll_detach`, `promote.promote_cut` and `_run_assemble` (367). `marker_notes(slug)` names an unmarked reconstruction and any other card overlapping a MARK span (graphics-director.md line one hundred eleven: never two cards at once); `_run_assemble` and `proxy.build` refuse on it, so a reproxy after graphics cannot reach the desk unmarked. `graphics-director.md`: `MARK*` cards are engine-owned; preserve them; never place a card across one. **[D6]**
- `sound-designer.md` "The grammar": category **Illustration runs**: a wordless run gets ONE cue row, quiet, never on a peak; the chapter bed continues. No job runs this brief (no `sound` kind); the sound-designer's hand session writes the row in `sfx_cues.json` with the picture beat's id, and Caleb places it on the Sound desk through today's `_sfx_place` (editroom.py 302). **[D16]** `retention-editor.md`: a `provenance` beat with a placed cue is not a dead stretch. `coverage-editor.md` R1 (Justified): an illustration never establishes and never sits in the hook. One line each in `hype-director.md` (never an illustration frame in the hook montage), `caption-editor.md` (a reconstruction's caption names it as such), `shot-fixer.md` (never replace a take with an illustration), `post-production.md` (illustrations are ungraded by design), `graphics-director.md` (above).
- `publish-writer.md`: a fourth heading `# Credits` ("Illustrations generated with <model ids> via Higgsfield; N reconstruction(s) marked on screen", plus the CC attribution rows from `brand/design-system/overlay-assets/assets.json`), and in `# Description` the YouTube altered-content line when a reconstruction is in the cut. `jobs._credits_clause(slug)` (pure, from `illustration.in_cut(slug)`) joins `PUBLISH_PROMPT`; `_run_publish` demands `# Credits` with the model ids, and the disclosure when a reconstruction is in the cut. **[D15]**
- `deliver.checklist` (18): a row `{"id": "credits", "ok": <publish.md carries Credits, or nothing is in the cut>, "fix": "/studio/deliver/<slug>", "blocking": False}`; `ready` becomes `all(r["ok"] for r in rows if r.get("blocking", True))` (deliver.py 230). **[D15]**

**Definition of done.**
- On the P4 project mark a round `honesty: reconstruction`, generate, promote, attach: `graphics_plan.json` holds `MARK01` with `text`, the cover's `at` and `duration`; `ffmpeg -ss <at + 0.2> -i <proxy> -frames:v 1` at three offsets (start, middle, end of the span) piped to a pixel probe of the eyebrow region reports CYAN, and the frame after the span does not; a twenty second spine run yields `MARK01` and `MARK02`. Run the graphics job: `MARK01` survives. Delete the cover and re-assemble: `MARK01` gone. Place a chapter card across the span: assemble returns `declined` naming both cards.
- Publish: `publish.md` has four headings and the disclosure; with no reconstruction the disclosure is not demanded.
- `curl -s 'localhost:8765/api/deliver/checklist?slug=<slug>'` shows the `credits` row; with `publish.md` deleted it reads not ok and `ready` is unchanged.

**Risks and mitigations.** Illustrations on the shelf but none in the cut: `in_cut` reads `promoted_as` against `broll.json` and the plan. Resolve's behaviour on overlapping connected clips is untested: the overlap refusal keeps it untested on purpose.

**Tests to add.** `tests/test_illustration_ship.py`: `sync_markers` one card per reconstruction cover, none for an illustration, every card passes `validate_graphics_plan`, splits past fifteen seconds, removes an orphan, survives a rewritten graphics plan, idempotent; `marker_notes` on an unmarked span and on an overlap; `provenance` in `RENDERERS` after a bare `import overlay_kit`; publish post-check both branches; `_credits_clause` lists only rows in the cut; the checklist row never blocks.

**Ratchets not to break.** `tests/test_overlay_kit.py`, `tests/test_custom_overlays.py`, `tests/test_peak_protection.py`, `tests/test_deliver_checklist.py` (ten), `tests/test_cut_promote.py`, Studio `vocabulary.test.ts`.

**Who.** `mattpocock-skills:tdd`; `mattpocock-skills:writing-for-agents` for the nine brief edits; `mattpocock-skills:code-review`.

### P6. Blender Template one as kit types beside the CSS cards

**Goal.** `chapter_3d` and `hook_3d` are real `kit_type`s the graphics-director can pick; the cache key sees the Blender inputs; nothing downstream knows which tool drew the pixels.

**Changes.**
- `brand/blender/` with `README.md`; Template one builds its `.blend` per card from the spec, so the bridge scripts are the template.
- `pipeline/blender_kit.py`: `BLENDER_KITS = {"chapter_3d": "chapter", "hook_3d": "hook"}`; HTML stand-ins registered into `overlay_kit.RENDERERS` (tail import, as P5); templates into `_KIT_TEMPLATES`; group "3D titles" in `_kit_groups` (2086); `template_sha()` = sha1 of the two bridge scripts, `blender_title.BLENDER_TEXT_SCALE` and any `.blend`.
- `graphics.bake_key` (272): fold `template_sha()` for Blender kits only (`build_cards` and `editroom._current_key` (1979) both call it). `build_cards`: route a Blender kit to `blender_title.build_title(text, mov, kicker, fps, seconds, w=w, h=h)`; `editroom._export_overlay` (2336) custom branch gets the same switch. **[D8]**
- `blender_title.build_title` (137): gains `w, h` passed to `title_spec` (93), which already takes them; `subprocess.run` in `build_title` and `blender_render.render_blend` gain `timeout=600`. `schemas.validate_graphics_plan`: the two and a half second chapter floor covers `chapter_3d`.
- Line fit: measure the Bricolage advance in Blender and set `_fit` from it. `graphics-director.md` kit table: two rows (episode title and chapter opens may go 3D; lower thirds flat; never on a peak). `docs/blender.md` records the measured time and the stand-in carve-out.

**Definition of done.**
- `overlay_kit.RENDERERS` holds `chapter_3d` and `hook_3d`; `validate_graphics_plan` accepts `chapter_3d`.
- On hmns switch one chapter card to `chapter_3d` and render: `ffprobe -show_streams` reports prores `yuva444p` at 3840x2160; `curl` of the card state route the Graphics desk polls (the one computing `current` at editroom.py 2003) reads `current`; bump `BLENDER_TEXT_SCALE` by one thousandth and `curl` again: `stale` (a `touch` changes nothing, the key is a content hash); restore it; a flat card's key is unchanged.
- `scripts/card_bbox.py` (ffmpeg first frame, alpha threshold, ink bounding box) over the flat `chapter` render and the `chapter_3d` render at the same canvas: left edge and cap height within six pixels, line count identical. Per-card time logged; fifteen seconds is the target, not a gate.

**Risks and mitigations.** A 4K Eevee bake inside `_BAKE_LOCK` on the single local lane: the timeout, the samples cut, the measured figure. The stand-in shows no depth: the desk badge says so.

**Tests to add.** `tests/test_blender_kit.py`: both kits in `RENDERERS`; `bake_key` for `chapter_3d` changes with the bridge sha and `chapter`'s does not; `build_cards` takes the branch with `build_title` stubbed, recording the key `_current_key` computes; `_export_overlay` takes it; the canvas reaches `title_spec`; a timeout is an `IngestError`.

**Ratchets not to break.** `tests/test_blender_title.py` (ten), `tests/test_blender_render.py`, `tests/test_overlay_kit.py`, `tests/test_custom_overlays.py`, `tests/test_paths.py`.

**Who.** A general subagent with `docs/blender.md` and `tests/test_blender_title.py` as the bar; `mattpocock-skills:code-review`.

### P7. Pilot and the Soul targets

**Goal.** hmns carries the monarch set through the desk route only; the next fresh episode runs the whole lane; thumbnails and Shorts covers go through the same round kind.

**Changes.**
- hmns: promote the remaining clips and plates; Caleb ingests; attach through the desk with a `why` per cover on beats he names (`shot-T41`: at most three point two seconds, before the last fifth); no `recut`, no coverage job; the beat count stays eighty-two.
- Round targets `thumbnail` (a still, `aspect` free) and `short_cover` (a Soul plate plus an optional Kling motion step at `9:16`, the "with motion" of decision 5): `spend` writes them like any row; the Export desk (`DeliverView.tsx`) gains "Use an illustration as the thumbnail", listing those rows and copying the chosen file into `deliverables/` with `_bake_thumbnail`'s versioning; `_bake_thumbnail` stays camera-only. **[D5]**
- The Soul was trained 2026-09-16 (03:38 UTC) from this session per `work/_soul/STAGING.md`: id `c292ab05-956c-4365-a6d1-991cae6d9f5c`, `soul_cinematic`, fourteen images, twenty-five credits on the transaction log. P2 puts the id into `.env` as `NINTH_ROOM_SOUL_ID`; the training and the website Seedance runs of the same night get rows in `channel_ledger()`, not against any episode. **[D7]**
- Pilot credit estimate: two single illustrations (nineteen), one four-plate run (thirty-eight), the turbo test (ten), a thumbnail and a Shorts cover with motion (about twenty-two): about eighty-nine of the three hundred cap.

**Definition of done.** Every command in section seven's twenty rows passes on the fresh episode; `python3 -c` over `work/hmns/edit_plan.json` prints eighty-two beats with unchanged ids and the monarch covers carry `why`; `work/_jobs.json` holds no hmns `recut` row.

**Risks and mitigations.** hmns's coverage job fails if pressed: the desk route is its door (decision 12). Soul id missing: `soul_available` refuses before dispatch.

**Tests.** `tests/test_illustration_ship.py` gains the thumbnail copy (versioned, never overwrites) and the `short_cover` motion step validation. Do not break `tests/test_media_poster.py`.

**Who.** Caleb on the desks; a Studio subagent for the Export desk verb; `mattpocock-skills:code-review`.

## 5. The illustration-director brief, outlined

`.claude/agents/illustration-director.md`, `tools: Read, Write, Bash, Glob`. Sections in order:

1. **Doctrine.** "You draw what the camera could not film, and you say so." The visit is the episode; the real place is footage or nothing. Two honesty values: `illustration` (stylised cyanotype plate; provenance in data) and `reconstruction` (photoreal; eyebrow on screen, disclosure in the description). Consult by artifact: story-director's `visual` block and section text; story-designer's `visual` block, `theme`, chapter promises and beat notes; `research.json` facts with `confidence`; `brand/taste.md` kept statements T8, T9, T12, T13. The visual language is overlay-designer's, handed through `brand/illustration/plate.md` with hexes injected; never type one. Beside is the preferred future shape; today a cover is a full-frame `illustrate` cutaway. Prefer the library (T8).
2. **Mechanical bar.** Write only `work/<slug>/staging/illustration_rounds.json` with the fields `validate_round` checks; price every step with `higgsfield generate cost` using job ids only; download nothing; write nothing under `assets/`; never call `higgsfield generate create`; the `higgsfield` on your PATH refuses all of these. Credits on every step and round, `std` by default, a higher tier only with a `reason` and only where Caleb marks it, three hundred an episode including the ledger; this overrides the Higgsfield skill's "Don't pre-estimate cost". Plate one defines the treatment and later plates reference it by `job_id`; a motion prompt describes motion only; a Soul step is a plate on a Soul model, animated by Kling from that plate. Prove it: `illustrate-check <slug>` lists no refusal.
3. **Worked examples.** (a) Script lane, story-director's own `CH2.S3` ("The pendulum ran for decades on nothing but the rotation of the planet", `why: "illustrate: the thing being named"`): a plate step (`nano_banana_pro`, two credits) and a motion step (`kling3_0` std, seven and a half credits, `start_image: plate`), aspect `16:9`, estimate nine and a half. (b) Footage lane, hmns `shot-T41` (note "B013 removed per Caleb's review (shot inside the dome, which we have not entered yet)", transcript "let's start from egg ... egg to grow and caterpillar", `beat_span` five point three eight seconds): ONE plate and clip of the egg, `why: "illustrate: the egg on the life-cycle board the line names"`, three seconds (under the sixty percent ceiling and the last fifth); the four-plate lifecycle as a second `target: "run"` round noted "needs a story-designer picture beat on a fresh episode". The lesson is T9: a butterfly plate would run ahead of a beat that ends on "caterpillar". (c) Reconstruction: the 1851 Panthéon demonstration no camera filmed; `honesty: reconstruction`, `sources` and `disclosure` filled, `soul: true` only on the `soul_cinema_studio` plate, only if the host stands in it and only on a `vo` section.
4. **Self-critique rubric, stable ids.** Score one to five before finishing; a three or under quotes the line that earned it. **I1 Honest subject**: never the real place as footage, never a real person, never the family. **I2 Serves the line**: the picture shows the thing named (T8); never runs ahead (T9). **I3 Never an establisher, the hook or a peak.** **I4 Grammar fits**: `COVER_MIN_S`, the sixty percent ceiling of `beat_span`, the landing, one clip once; a longer run is a picture beat. **I5 Style contract**: the plate block quoted as handed; no hex typed; no yellow or cyan inside the plate. **I6 Consistency by job id**: plate one defines treatment. **I7 Money stated**: every step and round priced; `std` unless marked; the total fits three hundred. **I8 Marked when photoreal**: `honesty: reconstruction`, `sources`, `disclosure`; a Soul step only on a Soul model's plate, only on a `vo` section or a take-less beat. **I9 Aspect matches delivery**, except thumbnail and short_cover targets. **I10 Fewer, righter**: nothing the library covers; a wrong illustration is worse than the face.
5. **Never.** Fill a missed to-camera line. A face other than the Soul; never the family. Download. Run `generate create`, `workflow`, `upload` or `soul-id`. Pass a local path to any Higgsfield flag (it uploads). Write under `assets/`, `footage/`, `analysis/` or the live `asset_requests.json`. Say "insert". Quote `brand/taste.md` statements other than `kept` or `revised`. Generate audio.

## 6. The prompt clause

`jobs._illustration_clause(slug)` is pure and injects, in the order story-director reads its own inputs ("Read first", items one to five):

1. **The brief** (`story_brief.json`): `origin`, `delivery` and its aspect from `schemas.delivery_shape`, `target_minutes`, `chapters`, `vo_share`, `location` or `subject`.
2. **Research** (`research.json`): each target section's facts as `fact`, `source_url`, `confidence`; a `claimed` fact is illustrated as claimed.
3. **Voice**: `brand/voice-and-tone.md` and `brand/brand-brief.md` by path, plus "The visit is the episode" and "could we source it if someone asked?".
4. **Film studies** (`docs/film-studies/INDEX.md`): Harris R13, Rober D10 and D16, Beau Miles.
5. **The lane block.** Script lane: every section with `visual.from == "illustration"` and no live round: `id`, `kind`, `text`, `source`, `est_s`, `visual.want`, `visual.why`, its chapter `title` and `loops[].promise`. Footage lane: `theme`, `chapters[].promise`, every beat with `visual.from == "illustration"` and no live round, not in `hook_beat_ids` and not `peak` (`id`, `purpose`, `chapter_id`, `beat_span`, transcript, `note`, `visual.want`, `visual.why`, `broll[].why`), the approved `stories.json` round's `logline`, `hook`, `tone`, and `review.json` notes. A beat with only a `note` is not a request.
6. **Visual language**: the two blocks of `brand/illustration/plate.md` with `{{navy_900}}`, `{{chalk}}`, `{{slate_300}}` replaced through `design_tokens.load()` and `resolve()` (the tokens `overlay_kit.NAVY`, `CHALK`, `SLATE_300` read); the failure case: the plate must read at the `480p` proxy over the chapter's brightest footage.
7. **Money**: the balance from `higgsfield account status`, `spent(slug)`, the three hundred cap, the defaults and tier fields, the override sentence, that marks are Caleb's.
8. **Honesty and marker**: the two honesty values, the never-list, `SOUL_MODELS`, whether `paths.soul_id()` is set (absent means no `soul: true`).
9. **Mechanics**: the round shape, the staging path, the read-only shim, `illustrate-check`.

**The tests.** `tests/test_illustration_job.py::test_the_story_reaches_the_illustrator` builds a temp project (a locked script whose `CH1.S2` has `from: illustration`, one `claimed` fact, a `short` brief) and asserts the clause contains, in order, `CH1.S2`, the section text, the `want`, the `why`, the `source_url`, `claimed`, the chapter promise, `9:16`, the navy hex read from `design_tokens.load()` at test time, `300`, `7.5`, `RECONSTRUCTION`, `illustrate-check`. `test_the_cut_reaches_the_illustrator` does the footage twin (two beats with `visual`, eighty with a bare `note`) and asserts the two are present, the hook beats, a `peak: true` beat and the eighty are absent. `test_the_token_hexes_are_read_from_the_kit_not_typed` monkeypatches `design_tokens.load` and asserts the clause changes and no `#` hex appears in the clause source.

## 7. Verification matrix (a fresh script-lane episode, then the footage twin)

| # | Step | Check |
|---|---|---|
| 1 | story-director writes `from: illustration` on a `vo` section | `schemas.script_notes` empty |
| 2 | Caleb locks the script | `locked: true`; sourcing propose names no gap for it |
| 3 | Propose | one `illustration` round with `estimate_credits`; balance and `assets/` count unchanged; the shim log shows no refusal |
| 4 | Click with an unlocked script, or generate with nothing approved | `/api/job/start` returns 400; no row in `work/_jobs.json` |
| 5 | Approve, mark nothing | `POST /api/asset/round` returns `approved: 1`, `marks` empty |
| 6 | Generate | two `done` rows with `job_id`, `cost_credits`; balance delta equals their sum; the transaction window matches by `display_name` and `credits`; no `session_id`; a second click is 400 |
| 7 | Library desk | the `/api/assets` count prints two illustration rows and zero `needsClearing`; `licenceState` vitest `clear` |
| 8 | Use | footage file at the delivery canvas, `promoted_as` on the row, `survey` queued; on a portrait project no `_fill` file |
| 9 | Ingest | `broll.json` clip has `provenance`; re-ingest keeps it |
| 10 | Attach with `why: illustrate ...` | placed; `establish`, a hook beat, no why, or over sixty percent of `beat_span` each return 400; the same plan edited by hand fails `promote_cut` |
| 11 | Render (`produce.produce`) | `timeline_map.json` cover carries `provenance`; log `[color] 1 illustration file(s) left ungraded` |
| 12 | Proxy | `ffmpeg -frames:v 1` at the cover offset: the frame's mean colour within a tolerance of the approved plate's mean |
| 13 | Reconstruction round, then a graphics run | `MARK01` in `graphics_plan.json` after graphics; the eyebrow pixel probe passes at three offsets and fails after the span |
| 14 | Delete the promoted asset | 400 `in_the_cut`; file still under `assets/` |
| 15 | Thumbnail at the cover offset | 400; the Export desk picker uses a `thumbnail` row |
| 16 | Publish | `# Credits` with the model ids; the disclosure only with a reconstruction |
| 17 | Export checklist | `credits` row `blocking: false`; `ready` unaffected |
| 18 | Sound | the sound-designer's hand session writes one illustration-run row in `sfx_cues.json`; Caleb places it on the Sound desk; `sound_cues.json` holds it on the picture beat |
| 19 | Blender | a `chapter_3d` card bakes at 3840x2160; the state route reads `current`, `stale` after a one-byte bridge edit |
| 20 | Suites and hmns | both suites green (ten new engine test files); hmns covers attached through the desk with `why`; beat count eighty-two; no `recut` row |

## 8. Out of scope and follow-ups

- **Beside** (split or inset, Rober D10, Harris R10): the first follow-up plan; touches `COVER_WHYS`, `timeline.py` and the coverage arithmetic; the round `note` collects the evidence.
- **A `spend` lane**: generate holds the session worker for a render wait; a third lane in `_QUEUES` follows once the pilot shows it hurts.
- **A listed upscale model** (`video_upscale`, Kling `mode: 4k`) behind the same ledger; the ffmpeg resample stands until then (ADR).
- **Blender Templates two to four**: Template two waits on the CLI (`multi_image_to_3d` cost fails on 1.1.25); Template four (parallax over a real still) is the free rescue; Template three (flyover) needs a written rule.
- **The room loop** and **audio generation**: excluded by decisions nine and two.
- **The predicate registry for the twenty-six existing kinds**: `preconditions.py` starts with the new kind only.
- **The compare-card still door** (`overlay_kit.compare` images under `brand/design-system/overlay-assets/`): a second shelf with kit colour; not used here.
- **`Project.assets` counting illustration rows as done pictures** (`_asset_count`, editroom.py 4150), and **the desk route's peak and ratio rules for camera covers**: follow-ups.
- **Gap nine remainder**: composing the eyebrow into a co-timed kit card instead of refusing the overlap; deferred because Resolve's overlap behaviour is unmeasured.
- **"inserts" in `story-designer.md` 216 and 362 and `taste.md` 138**: the signed grammar sentence; left as written.
- **`.claude/commands/produce.md`**: stale; an illustration checkpoint joins its rewrite.

## 9. Open items for Caleb

1. **The generate actor.** Decision 3 names the agent; the plan makes the engine generate. One line in the ADR, yes or no, before P4 starts; no is honoured (section two).
2. **Sign `brand/illustration/plate.md`** after P3 lands: the Plate block restates the monarch look; the Reconstruction block is new prose and needs your eye.
3. **hmns beats.** Only `shot-T41` is named for the monarch set. Name the beats for the other clips, or leave them on the shelf.
4. **The Soul id** is known (`c292ab05-956c-4365-a6d1-991cae6d9f5c`). Say the word and it goes into `.env` as `NINTH_ROOM_SOUL_ID`, with the training and the website Seedance runs as the first channel ledger rows.
5. **Marks are yours.** Seedance and pro exist only as toggles on the round at approval; nothing proposes them.

Verifier disputes: none. Every finding was reopened against the files and the CLI this session and held.