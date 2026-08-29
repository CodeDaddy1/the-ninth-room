# Caleb's taste — mined from recorded verdicts

**SIGNED 2026-08-28 by Caleb, statement by statement.** Every statement below carries a `verdict:` line. Only `kept` and `revised` statements may be cited by any agent brief or check; a `rejected` statement stays here with its evidence — it is mined data and deleting it would destroy the trace back to the verdicts — but nothing may reference it.

A revised statement's own heading is unchanged; the revision is Caleb's wording on the verdict line and it OUTRANKS the heading.

Mined 2026-08-24, signed 2026-08-28. Every statement below is derived only
from decisions Caleb actually recorded. Nothing here is inferred from the
brand docs. A statement becomes doctrine when its verdict line says `kept`
or `revised`, and never before.

**Sources**
- `work/hmns/review.json` — 96 beats, 59 carrying a Caleb note across 2 rounds.
- `work/hmns/captions.json` — 80 caption beats; 1 carries a `text_orig` diff.
- `work/hmns/graphics_plan_removed.json` — 22 cards removed from the plan,
  2 removed from the timeline — against 34 cards kept in
  `work/hmns/graphics_plan.json`.
  *(The task named these two files under `work/crooise/`; they do not exist
  there. The real files are under `work/hmns/` and are what was mined.)*
- `work/crooise/story_feedback.json` + `work/crooise/story_brief.json` — 2
  recorded story verdicts, 0 prose notes, 1 brief.
- `.claude/agents/story-designer.md` §"The b-roll grammar" — the one Caleb
  b-roll critique recorded verbatim in an agent file.

Not mined: `work/crooise/review.json`. Its five notes are signed
`"by": "retention-editor"` — they are an agent's flags, not Caleb's verdicts.

---

## Cutting: where a beat starts and stops

### T1. A beat may not end before the last spoken word finishes. When in doubt he extends, never trims.
evidence: 7
verdict: revised 2026-08-28 — can extend or shave

> BT12 — extend this clip by half a second more. The cut is too abrupt on the last word spoken.
> BT18 — the word butterfly is cut off mid speech. Extend clip by a quarter second.
> BT19 — Extend for a 10th of a second.
> BT21 — Ending of the clip keeps clipping the last word in the sentence by a fraction of a second
> BT15 — finish the sentence. Look, there's a butterfly right there on the ground. Make sure this does not cut to the next clip without finishing this sentence.
> BT06 — Make sure the sentence completes and do not cut off before the word harmless.
> BT101 — The last sentence is cut off before the word monopoly, it shouldn't be cut.

### T2. He specifies cut points as quoted lines, not as timecodes — the sentence is the unit of edit, and once the line lands the beat is over.
evidence: 7
verdict: revised 2026-08-28 — We should be able to edit the clip by manually cutting with a scrubber during the footage ranking process. This will eliminate words spoken within the clip that is not needed. We should also be able to mute the clip, effectively turning it into B-roll.

> BT16 — Cut right after the sentence, "That is actually insane". 
> BT06 — "These wingless giants from Madagascar are gentle, slow-moving and harmless." Only keep the clip of the sentence described. Cut everything before that.
> BT57 — Cut the clip to, "this is a turtle" 2 seconds max
> BT67 — Start clip at "We're going to get ready to head home because we're tired."
> BT13 — It should start clean on the sentence starting with "we've been here countless times..."
> BT83 — "Im going to go on top of that pyramid tomorrow is what the caption should say.
> BT73 — Cut down to the 5 second mark.

### T3. A beat must open clean — no audio bleeding in from the previous clip.
evidence: 1
verdict: rejected 2026-08-28 — it can stay as a one-off to be corrected

> BT13 — Start from the 1 second mark at the waterfall scene with not audio clipping from the previous clip. It should start clean on the sentence starting with "we've been here countless times..."

### T4. A misspoken line and its retake must never both survive the cut.
evidence: 1
verdict: rejected 2026-08-28 — superseded by the revision of T2

> BT62 — Make the cut better and do not repeat the misspoken "we had so much fun". remove the part "and we had a blast"

### T5. Deleting a whole beat is routine, not a last resort — he cut 14 of 96.
evidence: 14
verdict: rejected 2026-08-28 — footage edit/trim will make clips more useful during review desk and story building

> BT69 — Omit from video
> BT72 — Omit from video
> BT17 — remove clip
> BT20 — remove this clip.
> BT37 — remove clip
> BT41 — remove clip
> BT44 — remove clip
> BT85 — remove clip
> BT86 — remove
> BT87 — remove
> BT88 — remove
> BT90 — remove
> BT92 — remove
> BT53 — remove

### T6. When a beat carries information the story still needs, he names a replacement take instead of deleting it.
evidence: 1
verdict: rejected 2026-08-28 — can stay as a one-off

> BT47 — remove and replace with the same clip but where Caleb says that their feeling a bit peckish and will grab a bite to eat. As well as how there's still more of the museum left to see.

---

## B-roll: the default verdict is remove

### T7. He never once asked for more b-roll. Of the 9 beats where he ruled on coverage, 8 were removals and 1 was a swap. His stated standard is support, not density.
evidence: 10
verdict: rejected 2026-08-28

> BT08 — Remove B roll from 3 second mark of the butterfly. Not relevant to the shot.
> BT74 — remove b roll. Though relevant, this b roll comes from the butterfly dome, which we have not entered yet.
> BT11 — Remove the second B roll.
> BT59 — remove b roll starting at 3 second mark. Have more talking head shot.
> BT60 — remove b roll
> BT61 — remove B roll. Reaction animation, "Caleb sizing up Slothzilla"
> BT67 — remove b roll.
> BT101 — Remove both b rolls. Do not cut the speaker.
> BT29 — Use another b roll clip
> story-designer.md §"The b-roll grammar" heading — Caleb's note, 2026-08-24: "supportive of the story, not a bombardment of noise"

### T8. A cutaway must be of the thing the line is naming. Relevance to the subject is not enough — it must be relevant to the shot.
evidence: 2
verdict: kept 2026-08-28

> BT08 — Remove B roll from 3 second mark of the butterfly. Not relevant to the shot.
> story-designer.md — The crooise cut placed five 1.1-second postcards over the hook — one of them a DIFFERENT SHIP — while the line was about donuts. Never again.

### T9. Coverage may not run ahead of where the story has physically arrived.
evidence: 1
verdict: kept 2026-08-28

> BT74 — remove b roll. Though relevant, this b roll comes from the butterfly dome, which we have not entered yet.

### T10. The face delivers. Cutting away from the speaker mid-thought is a defect.
evidence: 2
verdict: rejected 2026-08-28

> BT101 — Remove both b rolls. Do not cut the speaker.
> BT59 — remove b roll starting at 3 second mark. Have more talking head shot.

### T11. When a beat carries two or more covers, the extra ones are the ones that go.
evidence: 3
verdict: rejected 2026-08-28 — allow for extra b-roll if relevant by tags

> BT11 — Remove the second B roll.
> BT101 — Remove both b rolls.
> story-designer.md — Sequences, not postcards: two or more covers inside one beat must be a SEQUENCE — wide → closer → detail of the same subject, or a match chain — never unrelated inserts.

---

## Cards: what survives and what dies

### T12. A card must let the footage read through it, and take less of the frame. Opacity was his single most repeated graphics note.
evidence: 5
verdict: kept 2026-08-28

> BT01 — Should have lower opacity for the title card with background visible underneath, apply gradient. Door
> BT04 — Lower opacity to see clip underneath.
> BT24 — Should have lower opacity to see underneath
> BT14 — Maybe a bit opaque without sacrificing visibility of text.
> BT14 — Make the vote box slightly smaller and perhaps centered?

### T13. Placeholder copy is an automatic delete. 18 of the 22 removed cards still carried kit default text.
evidence: 6 (representative; 18 total removals carry default copy)
verdict: kept 2026-08-28

> BT33 round 2 — remove default chapter title card
> removed — `lower_third` / "True fact" / "Your fact goes here"
> removed ×2 — `chapter` / "Chapter title" (BT33, BT01)
> removed ×3 — `poll` / "You picked" / "Left door or right?" (BT07, BT80, BT14)
> removed ×2 — `quiz` / "One of these is true" / "What did it eat?" (BT07, BT78)
> removed ×2 — `vote` / "Cast your vote" / "Who wins?" / Caleb 0, Alma 0, Sofia 0 (BT07, BT10)

### T14. It is the copy that is judged, not the card type. The same type is deleted with default text and kept with written text.
evidence: 2
verdict: kept 2026-08-28

> removed (BT14) — `prediction` / "Call it now" / "How many will land on Caleb?"
> kept (BT14, CARD18) — `prediction` / "Call it now" / "How many 🦋 will land on Sofia?"

### T15. Eleven of the kit's card types were tried and none survived: chapter, countdown, quiz, poll, true_false, emoji, watermark, glass, meme_zoom, meme_drop, meme_rain.
evidence: 15 (summarised below; 15 removals, 0 survivors)
verdict: revised 2026-08-28 — No type is banned. Placeholder copy is dead on arrival, and an untried card type needs written copy before judgment.

> removed kit_types with zero kept instances — chapter ×2, poll ×3, quiz ×2, countdown ×1, true_false ×1, emoji ×1, watermark ×1, glass ×1, meme_zoom ×1, meme_drop ×1, meme_rain ×1
> kept kit_types — hook, lower_third, payoff, prediction, reaction, scoreboard, section, stamp, stat, transition, vote

### T16. The meme pack was tried three different ways on one beat and rejected all three times.
evidence: 4
verdict: rejected 2026-08-28 — no longer needed

> BT78 — Remove this card
> removed (BT78) — `meme_zoom` / "Sofia" / "🦜=🦋"
> removed (BT78) — `meme_drop` / "Sofia" / "Math ain't Mathin"
> removed (BT78) — `meme_rain` / "🦥" / "3 tons" / "of sloth, apparently"

### T17. The lower-third fact card is the workhorse — 9 kept, the most of any type, and no written one was ever removed.
evidence: 3
verdict: rejected 2026-08-28 — observing

> BT58 — Add the lower third Eremotherium animation with a fun fact about Slothzilla.
> BT36 — remove the vote and insert a fact of botulism
> kept — 9 `lower_third` cards; the only `lower_third` ever removed was the "Your fact goes here" placeholder

### T18. When a fact and an engagement prompt compete for the same moment, the fact wins.
evidence: 2
verdict: revised 2026-08-28 — Must fit context of clip the most.

> BT36 — remove the vote and insert a fact of botulism
> kept (BT36, CARD20) — `lower_third` / "Botulism" / "It shuts your nerves down, top to bottom"

### T19. A tally card must show the real count from the footage. He corrects the numbers rather than removing the card.
evidence: 3
verdict: kept 2026-08-28

> BT80 — Update No.Just No to 2 and keep has to be deep fried as 1
> removed (BT80, CARD11) — "Has to be deep fried 🍤" 1 / "No. Just no. 🤢" 1
> kept (BT80, CARD31) — "Has to be deep fried 🍤" 1 / "No. Just No. 🤢" 2

### T20. A card belongs on the frame where the line is spoken, not near it.
evidence: 3
verdict: kept 2026-08-28

> BT56 — Fried Fish Skin Card is on BT94, needs to be on BT56 when the punchline is being delivered.
> BT94 round 2 — The fried fish skin card needs to be removed from this clip
> kept — CARD36 `stamp` "🐟 Fried fish skin, anyone? 🐟" now sits on BT56 at 3.06s

### T21. A card reads all at once. Staggered subtext is a defect, and he filed it twice.
evidence: 2
verdict: kept 2026-08-28

> BT10 — Subtext should not be delayed.
> BT32 — sub text should not be delayed.

### T22. On-screen names are given names. "Mom" is a defect he filed twice, on two different cards.
evidence: 2
verdict: kept 2026-08-28

> BT14 — Mom should be replaced with Alma.
> BT22 — Mom on the scoreboard should be replaced with "Alma"

---

## Captions

### T23. Captions carry the words that were actually said, including the ungrammatical form.
evidence: 3
verdict: kept 2026-08-28

> BT28 — "he had signs of inbred..." the caption should show inbred not inbreeding
> BT83 — "Im going to go on top of that pyramid tomorrow is what the caption should say.
> BT79 `text_orig` diff — was: Those look like water bugs. Yeah. Let's go. Freaky. I found your favorite one. → now: Those look like water bugs. Yeah. That's freaky. I found your favorite one.

### T24. Captions are not owed to every beat. When the shot carries itself, they come off.
evidence: 3
verdict: kept 2026-08-28

> BT09 — Remove captions "Right in front of your nose. See, it's wiggling?"
> BT33 — Remove captions
> BT94 — remove captions and lower third animation. This clip should end on the slothzilla shot leading into the next clip.

### T25. An emoji in a caption is a punchline marker, not decoration — he asked for it twice, and only 3 of 80 caption beats carry one.
evidence: 4
verdict: rejected 2026-08-28

> BT05 — "You like looking at cockroaches?" Have the emoji in the captions.
> BT93 — Perfect opportunity to make funnier and capitalize on the comedic value. Have the emoji in the caption.
> kept caption BT05 — I like looking at cockroaches. 🪳
> kept caption BT93 — This is the garfish, and I'm pretty sure it tastes good too. 🍴

---

## Register

### T26. A flat beat gets a layer added, not a trim. His fix for "boring" is always additive.
evidence: 5
verdict: kept 2026-08-28

> BT39 — Make funnier
> BT66 — Make it comedic and fun
> BT93 — Perfect opportunity to make funnier and capitalize on the comedic value. Have the emoji in the caption.
> BT19 — add a visual comedic element to this statement since this is not the actual name of the butterfly.
> BT84 — Make this more intense or dramatic

### T27. When the family overstates a fact on camera, the correction goes on screen as the joke.
evidence: 2
verdict: kept 2026-08-28

> BT19 — add a visual comedic element to this statement since this is not the actual name of the butterfly.
> kept (BT19, CARD45) — `stamp` / "Not its real name 🤷‍♂️"

### T28. A beat should end on a chosen outgoing image, not simply when the audio runs out.
evidence: 2
verdict: kept 2026-08-28

> BT94 — This clip should end on the slothzilla shot leading into the next clip.
> BT68 — Allow for the shot to extend Caleb's hand towards the camera with a speed ramp up into a closing channel clip.

### T29. Image quality registers with him. In 96 beats of notes, the one unprompted compliment was about sharpness.
evidence: 1
verdict: rejected 2026-08-28

> BT76 — This is so high-def. That's cool.

---

## Story selection

### T30. He steers the story with a structured brief and picks a direction — he does not write notes on the pitches.
evidence: 3
verdict: kept 2026-08-28

> `story_feedback.json` round 1 — choice "S2", decision "approve", notes ""
> `story_feedback.json` round 3 — choice "S8", decision "approve", notes ""
> `story_brief.json` — target_minutes 12.0, chapters 6, "the ship is a city — lean into who lives aboard"

---

## Open questions for the sign-off pass — ANSWERED 2026-08-28

All four were put to Caleb at the sitting and each carries its answer on the
statement's own verdict line. For the record: the thin five split — T9 was
kept, T3, T4, T6 and T29 were all rejected; T15 was revised rather than kept,
which resolves it in the engagement playbook's favour (no card type is banned;
placeholder copy is what dies); T30 was kept despite being thin AND despite
its source files no longer existing on disk (they were deleted with the
crooise project and survive only in `work/_jobs/J1787520864021.log`).

- **T3, T4, T6, T9, T29** rest on a single note each. Sign or drop.
- **T15** is inferred from survival rates on one episode. It may be an artefact
  of hmns's subject matter rather than a standing preference — the quiz, poll
  and countdown cards were only ever inserted with placeholder copy, so T13
  may fully explain their deaths.
- **T30** is thin: two approvals with empty notes. It may describe a UI habit
  rather than a taste.
- Nothing here was mined from a crooise picture verdict — crooise has not been
  through a Caleb review round yet. Every cutting and card statement is
  single-episode.
