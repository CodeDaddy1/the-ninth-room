# A beat carries a take or a spine, and natural sound is opted into

**Decided 2026-08-28 by Caleb.** "A beat may have no take" was settled in the
design interview; this is what it took to be true.

## It was forbidden, not merely unimplemented

`validate_edit_plan` required `take_id` to be a `str` (`schemas.py:455`), so
a beat without one failed twice over — missing key, wrong type. Downstream,
`timeline.plan_beats` indexed `take_by_id[b["take_id"]]` directly.

`golf-testing` is the case that proved it. All eleven of its beats carry
`take_id: null` and it could not be validated at all, so the design was
written to `edit_plan.blocked.json` rather than to the real filename — the
previous agent's own note explains that `edit_plan.json` "flips the Studio to
'the cut is written', makes jobs.py refuse to ever re-run the editplan job,
and hands the assemble job beats whose takes do not exist."

Two distinct shapes need it:

- **pure picture** — a stretch with no line under it at all;
- **natural sound** — b-roll carried by its OWN audio. Six of golf-testing's
  eleven sections were off-camera voices over b-roll ("Okay, there we go.",
  "Nice, babe.", "No way."), and those voices were the spine of the whole
  direction. A cover is emitted as a picture-only `<video>`, so every one of
  those lines was inaudible in any cut the engine could build.

## What was compared

| | A — `spine` on the beat | B — promote a cover | C — a second beat type |
|---|---|---|---|
| shape | beat has `take_id` **or** `spine` | mark one `broll` entry as the spine | `beats` plus a parallel list |
| readers that change | validator, `plan_beats`, emitter | every cover reader | almost all of them |
| already invented by an agent | **yes** — golf-testing's design | no | no |
| natural sound expressible | yes, explicitly | tangled with cover rules | yes |

**A.** It is the shape the story designer reached for unprompted when it had
no takes to point at, which is decent evidence it is the natural one. B
overloads a structure whose entire contract is "picture only, never audio".

## What this decides

- **A beat carries a take or a spine.** `spine` is
  `{clip_id, src_s, src_e, audio}`, validated against the b-roll catalog:
  the clip must exist, the window must be non-empty and inside the clip.
- **A beat with neither is still an error.** Relaxing the rule did not
  remove it.
- **A take wins when both are present.** A beat that has a take IS its take.
- **`audio` is opted INTO, defaulting to silent.** A cover is picture-only
  because b-roll audio leaking over narration is a known hazard —
  `timeline.py`'s docstring names it: "museum crowd noise!". A spine is the
  same clip in a more dangerous position, so silence stays the default and
  natural sound is a decision the plan states out loud.
- **Speech operations do not run on a picture beat.** Word snapping,
  head/tail padding and dead-space cutting are all defined against a
  transcript; a picture beat is taken exactly as stated. Trimming its
  silence would delete the shot.
- **Emission follows the audio decision, not the asset.** Natural sound is an
  `<asset-clip>` (which carries the asset's audio); silent picture is a
  `<video>` (which never does), the same element and the same reason as a
  cover. The asset still declares `hasAudio` honestly either way, so a later
  cover of the same clip does not inherit a lie.

## Consequences

- `kind` is `picture` for both shapes. Natural sound is a property of the
  spine, not a fifth kind — a natural-sound beat has no take, no transcript
  and no face to cut back to, which is what the speech rules care about.
- The craft rules are unchanged for picture beats. They iterate covers, and
  the two that name the face ("the landing belongs to the face", "past 60%
  an on-camera beat stops being one") are worth revisiting if picture beats
  start carrying covers in practice. Not changed here on speculation.
- `snap_cuts` skips take-less beats; there is no speech to snap to.
- The Studio needed no change — `take_id` was already optional in
  `engine.ts`, and `ScriptView` already guarded on it.
- **golf-testing is now expressible but still not shippable**: its five
  narrated sections remain unrecorded, which no code change clears. That
  project is being deleted; the two shapes it exposed are not.
