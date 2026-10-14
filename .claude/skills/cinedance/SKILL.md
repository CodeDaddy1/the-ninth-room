---
name: cinedance
description: CINEDANCE V4, the Seedance prompt director. Use when writing, reviewing or fixing a Seedance shot prompt for a Petty Neighbors skit (shot-director's job), or when a draft came back with drifted identity, lens, gaze, blocking or lighting. Doctrine in doctrine.md; this file is the adapter for this pipeline and wins where they differ.
user-invocable: false
---

# CINEDANCE for Petty Neighbors

Read `doctrine.md` in full before writing a prompt. It is Caleb's pasted system, kept near
verbatim. This file says how it plugs into this studio. Where they disagree, this file wins.

## The adapter

**Model and settings live in the command, never in the prompt.** The engine passes them as CLI
flags, so the doctrine's OUTPUT SETTINGS section is always omitted:

| Setting | Value |
|---|---|
| Model | `seedance_2_5` through the Higgsfield CLI |
| Mode | `omni_reference` (every shot carries references) |
| Aspect | `9:16` |
| Duration | 10 seconds by default; 5 or 15 only when the shot says why |
| Resolution | `720p` for finals; 1080p only on a skit Caleb promotes |
| Audio | `generate_audio` on: dialogue, ambience and foley come from Seedance |
| Draft | every shot is drafted first (`--draft true`); a final reuses the approved draft's job |

Prompt-level settings that DO belong in the prompt: single take or controlled multi-shot, the cut
times, real-time motion, "no subtitles, no music" (music is added in the cut).

**Format mode.** A 10 second generation may hold up to two planned internal HARD CUTs. More than
that is a second shot.

**@TAGs.** A tag is the character or set id in capitals: `@BISCUIT`, `@ALLEY`. Each tag maps to
that character's or set's approved reference images in `shows/petty-neighbors/cast/<id>.md` or
`sets/<id>.md`. In `shots.json` every tag the prompt uses is listed in the shot's `refs` array, in
order; the engine passes those images as `--image-references`. The exact handle Seedance reads
inside the prompt is settled by the phase 3 pilot and written here when known; until then write
`@ID` and let the engine rewrite it.

**Character anchors.** The doctrine's formula ("age + role/body type + current state + anchors")
becomes, for an animal: species and breed + size and build + current state + the two or three look
anchors from the cast file + the action-critical paw, mouth or prop state + "100% matches the
reference". Never re-describe what the sheet already shows.

**Acting.** Every character in frame also gets its Acting System scene paragraph (the
`acting-system` skill), folded into FIRST FRAME AND SPATIAL BLOCKING or ACTION TIMING. A speaking
character's voice prompt goes into AUDIO verbatim.

**Look of the show.** Painterly 3D. Paste the style block from `shows/petty-neighbors/show.md` ("The look") word for word into every prompt's style line, after the spatial, optics, action and lighting locks. Lighting is still a priority lock; painterly is not an excuse for flat front light. Use the doctrine's lens bank exactly; animation does not change optics.

**Humans** appear only as legs, offscreen voices or seen from behind. Never a human face.

**The output** is not printed to chat. shot-director writes each prompt into `shots.json` (shape in
`.claude/agents/shot-director.md`). Every prompt passes the doctrine's silent self-QA first.

## Never

Name The Ninth Room in any prompt, caption or on-screen text. Put model, duration, aspect or
resolution in a prompt. Use a tag with no approved reference behind it.
