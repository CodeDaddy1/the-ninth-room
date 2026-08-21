# Engagement Playbook — The Ninth Room

The channel's retention strategy in one sentence: **hand the viewer a job.**

A viewer who answered out loud is a viewer who is still there ninety seconds
later. That is the entire reason the kit has thirteen engagement cards instead
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

## The thirteen cards

Every one is an outline; the answer is that outline flooding with yellow. None
of them is a filled box. `kit_type` is the value to put in `graphics_plan.json`.

### Ask-before-the-reveal

| `kit_type` | What it does | Reach for it when |
|---|---|---|
| `quiz` | 3 options, wrong ones dim, the answer floods yellow at 2.5s | There is a genuinely surprising correct answer and two plausible wrong ones |
| `true_false` | The two-option quiz | The fact is a common misconception — *"a cocoon and a chrysalis are the same thing"* |
| `countdown` | Ring plus 3·2·1, then cut on the frame the ring closes | You want the answer said out loud before the reveal. The strongest card in the kit |
| `prediction` | Question, held beat, no options | The answer is a number or an event, not a choice. *"How many will land on Caleb?"* |
| `spot_it` | Empty callout frame, viewer hunts | Something is visibly odd in frame before we point at it |

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
| `rank` | Ordered list, only the top row yellow | Three to five things have a real order — most venomous, oldest, heaviest |
| `scale` | Dimension bracket with a marker | One thing sits on a spectrum. *"How weird is it?"* |
| `verdict` | Lit doors out of five — **never stars** | Closing a room with a rating. The doors are the brand's rating unit |
| `streak` | The nine-square meter at full size | Marking progress as its own beat, usually mid-episode |

---

## Rhythm across an episode

A ten-minute room, roughly:

| Where | Card | Why there |
|---|---|---|
| 0:15 | `countdown` or `prediction` | Buys the first minute. The viewer has committed |
| 2:00 | `vote` | The family disagreeing is the first real character beat |
| 4:00 | `quiz` or `true_false` | The educational centre of the episode |
| 5:30 | `streak` | Structural breath — shows how much is left |
| 7:00 | `rank` or `scale` | Second teaching beat, lighter than the first |
| 9:00 | `verdict` | Closes the room |
| 9:30 | `poll` | Sets up next week, and honours last week |

Adjust freely. The only fixed points are: something in the first 20 seconds,
and nothing in the last 30 (the outro's three beats own that space).

## Shorts

A vertical cut gets **exactly one** card, and it must be answerable in the
first five seconds. `countdown` and `this_that` are the two that survive a
45-second cut. Everything else needs setup a Short doesn't have.

All thirteen cards reposition for 1080×1920 automatically — the renderer uses
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
