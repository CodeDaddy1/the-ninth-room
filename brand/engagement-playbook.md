# Engagement Playbook — The Ninth Room

The channel's retention strategy in one sentence: **hand the viewer a job.**

A viewer who answered out loud is a viewer who is still there ninety seconds
later. That is the entire reason the kit has fourteen engagement cards instead
of one. This document says which card to reach for, how often, and what makes
one fail.

The graphics-director agent reads this file. So should you before writing an
`edit_plan.json`.

---

## The four rules

1. **One job every 60–90 seconds.** Long enough that it isn't nagging, short
   enough that a kid never drifts. An episode with no engagement card is a
   lecture with better lighting.
2. **The card must be answerable from what is on screen.** If the viewer
   cannot possibly guess, it isn't engagement — it's a quiz they're going to
   lose, and losing is not fun.
3. **The answer always arrives.** Same as the payoff rule: a question we never
   answer is the fastest way to teach the audience to stop playing.
4. **Real numbers only.** A poll result is last week's actual poll. A vote
   count is what the family actually voted. Inventing a percentage is the one
   thing in this document that is never recoverable.

---

## The fourteen cards

Every one is an outline; the answer is that outline flooding with yellow. None
of them is a filled box. `kit_type` is the value to put in `graphics_plan.json`.

### Ask-before-the-reveal

| `kit_type` | What it does | Reach for it when |
|---|---|---|
| `quiz` | 3 options, wrong ones dim, the answer floods yellow at 2.5s | There is a genuinely surprising correct answer and two plausible wrong ones |
| `true_false` | The two-option quiz | The fact is a common misconception — *"a cocoon and a chrysalis are the same thing"* |
| `countdown` | Ring plus 3·2·1, then cut on the frame the ring closes | You want the answer said out loud before the reveal. The strongest card in the kit |
| `prediction` | Options stay open — outlined, no winner; the video pays them off. With no rows, question + held beat | The viewer should call it before the footage answers. *"How many will land on Caleb?"* |
| `spot_it` | Empty callout frame, viewer hunts | Something is visibly odd in frame before we point at it |
| `caption_this` | A freeze frame and an empty line — the yellow cursor blinks, the comments write the joke | A face or a moment is funnier than anything we could script |

### Take-a-side

| `kit_type` | What it does | Reach for it when |
|---|---|---|
| `vote` | Outlined options with counts; the leader takes the yellow outline, its digit ticks | The family disagrees on camera. This is the family card |
| `this_that` | Two options, neither pre-won | The viewer picks and we walk through their choice next episode |
| `poll` | Last week's real results as 6px rules, loser in slate | Following through on a `this_that` from a previous episode. **Only with real numbers** |
| `scoreboard` | Running tally across the episode | A recurring bit — butterflies landed, things Sofia refused to touch |

### Rate-and-rank

| `kit_type` | What it does | Reach for it when |
|---|---|---|
| `rank` | Cyan `?` slots — the viewer supplies the order; a row with `"rank": N` reveals its number in yellow | Three to five things have a real order and the comments are the scoreboard |
| `scale` | Dimension bracket with a marker | One thing sits on a spectrum. *"How weird is it?"* |
| `verdict` | Lit doors out of five — **never stars** | Closing a visit (or a chapter) with a rating. The doors are the brand's rating unit |
| `streak` | The chapter door meter at full size — one door per chapter, lit as you go | Marking progress as its own beat, usually mid-episode |

### The meme B-roll pack (gag clips, not questions)

Twelve `meme_*` screens ported from the MemeBroll design template. These are
not engagement cards — they hand the viewer a laugh, not a job — but they
live in the same kit and follow the same rules: no filled plates (frames and
washes only), one yellow moment, emoji subjects welcome. Each runs 4–5s over
footage or the navy wash. `meme_reaction` (subject slams in over a line),
`meme_drop` (framed "actual footage"), `meme_rain` (a stat under falling
emoji), `meme_versus` (expectation/reality), `meme_zoom` (slow push on a
subject), `meme_breaking` (news bug + ticker), `meme_loading` (a bar stuck at
99%), `meme_wanted` (poster), `meme_deal` (glasses drop), `meme_certified`
(rubber stamp), `meme_chase` (two emoji, one fleeing), `meme_peek` (eyes from
the frame edge). Subject is `emoji` (or an `image` path — it gets the yellow
frame); `meme_versus` and `meme_chase` take `emoji2` for the second party.
Use at most one or two per episode — a gag repeated is a gag killed.

---

## Rhythm across an episode

A ten-minute episode, roughly:

| Where | Card | Why there |
|---|---|---|
| 0:15 | `countdown` or `prediction` | Buys the first minute. The viewer has committed |
| 2:00 | `vote` | The family disagreeing is the first real character beat |
| 4:00 | `quiz` or `true_false` | The educational centre of the episode |
| 5:30 | `streak` | Structural breath — shows how much is left |
| 7:00 | `rank` or `scale` | Second teaching beat, lighter than the first |
| 9:00 | `verdict` | Closes the visit |
| 9:30 | `poll` | Sets up the next episode, and honours the last one |

Adjust freely. The only fixed points are: something in the first 20 seconds,
and nothing in the last 30 (the outro's three beats own that space).

## Shorts (the discovery engine)

Shorts are how new viewers find the channel — standalone moments recut
vertical, released steadily between episodes. A vertical cut gets **exactly
one** card, and it must be answerable in the first five seconds. `countdown`
and `this_that` are the two that survive a 45-second cut. Everything else
needs setup a Short doesn't have.

All fourteen cards reposition for 1080×1920 automatically — the renderer uses
the vertical insets (180 top, 320 bottom, 64 sides) so nothing lands under the
Shorts UI.

## How these fail

- **The card nobody can answer.** Guessing a specimen's Latin name is not a
  game. Guessing whether it ate leaves or fish is.
- **Two yellows.** A card with a yellow eyebrow *and* a yellow answer has no
  focal point. The renderer marks one term; don't fight it in the copy.
- **A poll with invented numbers.** Unrecoverable. If last week's poll wasn't
  run, don't show a poll.
- **Stacked cards.** Two engagement cards inside thirty seconds reads as a
  game show. Space them.
- **A card the footage contradicts.** The countdown must actually cut on the
  reveal. If the b-roll isn't there, the card can't go there.

## Writing the copy

- Eyebrow is structural, uppercase, 3–5 words: "One of these is true",
  "Guess before we do", "For a million bucks".
- Question is sentence case, under eight words: "What did it eat?"
- Options are under five words each. They must be visibly different at a
  glance — two options starting with the same word is a design bug.
- Second person, and give the instruction: "Say it out loud. We'll wait."
- Emoji are welcome on option labels and questions — one per line at most,
  and never at the cost of the option being readable at a glance. No
  exclamation marks. See `voice-and-tone.md`.
