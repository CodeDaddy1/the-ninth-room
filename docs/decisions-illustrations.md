# Illustrations: pictures no camera could film, gated, ledgered, marked

**Decided 2026-09-15 by Caleb**, over four rounds of questions with pros and
cons shown, after a six-reader map of the engine and a critic pass on the
map. The build plan is `docs/plan-illustrations.md`. Vocabulary is in
`CONTEXT.md` (Illustration, Reconstruction, Provenance, Ledger).

## What was true before

Nine Higgsfield rows sat in `work/hmns/assets/assets.json`, written by a hand
session outside any job: `kind: "generated"`, the beat smuggled into `query`,
no cost, no lock, "insert" in every row (a word `CONTEXT.md` bans). Nothing
in `pipeline/` read those fields; the Library desk rewrote the kind to
`video` or `image` and badged the licence `attention` with no way to clear
it. The Blender seam (`pipeline/blender_render.py`, `pipeline/blender_title.py`)
existed uncommitted, with no kit type and no cache key. `CLAUDE.md` said
"$0/mo is binding" while the README named three opt-in paid paths.

## The decisions

| # | Decision |
|---|---|
| 1 | Honesty: illustrations, plus photoreal reconstructions of unfilmable things marked on screen. Never the real place as generated footage. Never a fake of a real person saying or doing anything. |
| 2 | Higgsfield scope: illustrations (b-roll), thumbnails and Shorts covers, GLBs for Blender turntables. No audio generation. |
| 3 | The agent PROPOSES with a cost estimate; Caleb approves the round on the Library desk; only then GENERATE. This mirrors the sourcing gate (propose, approve, fetch). |
| 4 | Generated files land on the Library desk as `assets.json` rows; Caleb promotes them into footage. Today's flow, no auto-placement. |
| 5 | A Soul of Caleb only (cinematic variant, name "Caleb"); the family never goes to Higgsfield. Uses: host presence inside a marked reconstruction; Shorts covers and thumbnails with motion. Never to fill a missed to-camera line. |
| 6 | Marker: the kit eyebrow RECONSTRUCTION for the clip's whole length, plus YouTube's altered-content disclosure line at publish. A stylised illustration carries provenance in data only; the look does the on-screen work. |
| 7 | Credits: proposals capped at three hundred an episode; std quality by default; pro per item on request; every spend gets a ledger row. |
| 8 | Blender: Template one (3D titles) first, as new kit types BESIDE the CSS cards, never replacing them. |
| 9 | Topology: consult by artifact. One new one-shot craft; the runner builds its prompt from the story artifacts and the visual language; the agent self-critiques against a rubric with stable ids. No relay, no in-session subagents, no room loop (the 2026-08-24 one-shot decision stands). |
| 10 | Names: the "storyteller" is story-director on a script-lane episode and story-designer on a footage-lane cut. The "visual director" is overlay-designer's design language, borrowed into the new brief, not called. |
| 11 | Noun: "illustration". Craft: illustration-director. Manifest and round kind: `illustration`. "Insert" is scrubbed from the README, `docs/blender.md` and the nine hmns rows. |
| 12 | Pilot: the next fresh episode runs the full lane. hmns keeps the monarch set through the desk attach route only; its approved cut is not recut. |
| 13 | An illustration MAY depict a thing the camera filmed, as an `illustrate` cover when the footage is weak; never as `establish`; never in the hook montage. A machine rule keyed on provenance enforces this. |
| 14 | The "beside" shape (split or inset while the family stays on screen): later. The five cover justifications are reused now; the brief names beside as the preferred future shape; wiring it is the first follow-up plan. |
| 15 | Ship: a Credits section in the publish package naming the model, and a YouTube disclosure line when a reconstruction is in the cut. Export never blocks on a licence. |
| 16 | Sound under a wordless illustration run: one placed cue per run, written by the sound-designer, whose brief gains the category. |
| 17 | Engine calls delegated to Claude and locked: a locked manifest row per spend with its cost (the `brand/sfx/manifest.json` shape); named preconditions for the new kind in a small new module, existing kinds unchanged; the delivery aspect on the request and honoured by the still door; illustrations exempt from the camera LUT and CDL through a provenance flag that reaches `build_api`/`color`; `/api/broll/attach` requires a `why` once illustrations exist; `_delete_asset` gains the footage delete guard; `broll.json` keeps a `provenance` field derived from the manifest at catalog time; a generated frame is never the automatic thumbnail; the `$0/mo` line amended; `story-director.md`'s stale "unsigned" line corrected; the new brief overrides the Higgsfield skill's "don't pre-estimate cost". |
| 18 | Default video model: Kling 3.0 std, sound off, five seconds (seven and a half credits), upscaled to the delivery frame. Seedance 2.5 only on a round Caleb marks. Kling turbo 1080p tested once before adopting. |
| 19 | The list above is final; the plan does not re-litigate it. |

## Open: who runs the generate step

Decision 3 says "the agent proposes, Caleb approves, then it generates". The
plan has the engine run the generate step mechanically (an approved round is
a complete instruction; a session with permissions skipped never holds the
CLI while credits move; hard rule five, mechanical followers fire on their
own). That changes the actor, not the order, and it is not yet Caleb's call.

**Caleb's line (fill in before P4):** _____

If the answer is no, P4 dispatches the agent for the generate step behind the
read-only shim with `create` unlocked for the approved steps only, and the
runner remains the only writer of ledger rows, from the create's JSON.

## Two engine choices this plan makes

**Upscale.** Kling std returns 1284x716. Promotion resamples an illustration
to the delivery canvas with ffmpeg (Lanczos) instead of symlinking it, which
is the one exception to "promote links, never copies" (`editroom._use_asset`;
there is no `.LRF` sibling to preserve, which was the reason for linking). A
listed upscale model (`video_upscale`, Kling `mode: 4k`) can replace the
resample later behind the same ledger; the ADR is updated when it does.

**The stand-in canvas.** Rule six says the kit is designed in Claude Design
first. A Blender kit type has no HTML; its flat stand-in screen IS its canvas,
and the 3D render must match the stand-in (left edge, cap height, line
count), not the other way round. `CLAUDE.md` rule six carries the carve-out.

## The retired v1 briefs, read at `16206bf^`

The 2026-08-18 teardown deleted `visual-director.md`, `asset-scout.md` and
`youtube-scriptwriter.md`. They were read for this plan; each rule was
adopted or rejected by name so the shape is not revived by accident.

- visual-director, "legible in under a second at thumbnail size; one focal
  subject; five words or fewer of text": **adopted** for the `thumbnail` and
  `short_cover` round targets.
- visual-director, "show the gap, not the answer": **adopted**; a thumbnail
  teases the curiosity and never spoils the payoff, and it is why a generated
  frame is never the automatic thumbnail source.
- visual-director as a craft of its own: **rejected**; thumbnails ride the
  illustration round kind, not a second brief.
- asset-scout, `ai_generated` as a source type with a prompt: the idea is
  **adopted** as `from: illustration` on the story artifact; the shot-list
  artifact it lived in is **rejected** (the pivot removed shot lists on
  purpose, `workflows/content-workflow.md`).
- asset-scout, orientation per platform (16:9 long-form, 9:16 Shorts):
  **adopted** as `aspect` on the round, equal to the delivery shape except for
  the thumbnail and short-cover targets.
- asset-scout, "a fallback for every stock shot: AI-generate with prompt X":
  **rejected**. The library comes first; a wrong illustration is worse than
  the face (taste T8, the coverage grammar).
- asset-scout, "note the tool's commercial terms and any watermark":
  **adopted** as the `license` and `license_note` fields on every row.
- youtube-scriptwriter, the "plain-spoken storyteller": **not applicable**;
  story-director owns the script lane and is the storyteller decision ten
  names.

## Measurements (2026-09-15 to 2026-09-16, this machine and account)

- Monarch set for `shot-T41`: four Nano Banana Pro plates at two credits, four
  Kling 3.0 std sound-off clips at seven and a half; thirty-eight credits.
- Kling 3.0 std returns 1284x716 at twenty-four frames a second; `pro` is the
  1080p path. Seedance 2.5 at 1080p is forty-five credits per five seconds.
- Soul training: fourteen images, twenty-five credits, a few minutes;
  id `c292ab05-956c-4365-a6d1-991cae6d9f5c`, type `soul_cinematic`.
- Neither Seedance 2.5, Kling 3.0 nor Nano Banana Pro exposes a seed or a
  negative prompt; consistency comes from chaining by `job_id` (plate as
  `start_image`), proved on the four matching plates.
- `higgsfield account transactions` returns `{action, created_at, credits,
  display_name}` per item, no job id; reconciliation is by window, name and
  amount against the balance delta.
- Blender Template one: twenty-eight point six seconds per seventy-two frame
  1080p card including Blender's start; text scale one point four zero by cap
  height; the 3D line runs about a quarter wider than the flat card.
- The account showed website spends of two hundred seventy credits per
  Seedance run the same nights, none from the CLI. Always read the
  transaction log before attributing a balance drop to a job.
