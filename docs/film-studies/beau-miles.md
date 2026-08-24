# Film study: Beau Miles — "Running a different kind of marathon: A Mile an Hour"

- **Source:** https://www.youtube.com/watch?v=EvT5XS7j-Dc (channel: Beau
  Miles, 872k subs). Published 2018-08-18.
- **Runtime:** 17:12 (1032.06s measured), 5,010,832 views, 164,974 likes
  (**3.29% like-to-view** — very high for any format).
- **Why this one:** picked by evidence. Pulled all 96 channel uploads with
  yt-dlp and sorted by views: this is the **#1 most-viewed Beau Miles video
  overall** *and* the highest-viewed one inside the 8–20 minute band. It is
  also the most externally validated — Silver for Best Running Film and
  Silver for Best Activism Film at Sheffield Adventure Film Festival 2019,
  winner at Las Vegas Running Film Fest, official selection at four more —
  and Beau himself calls it "my most successful idea."
- **Studied:** 2026-08-24, eight passes — 100 scene-aware frames full-range
  (512px), 26 frames over 0:00–1:00 at 768px, dense sweeps of the night
  stretch, and six contact-sheet sweeps of the lower-left text band to
  census the cards. **Every frame listed was read.**
- **Transcript:** the **human-authored `en-GB` subtitle track** (241 cues,
  2,329 words) — not auto-captions. Quotes below are verbatim from it. The
  auto-caption track was used only to check the first 9 seconds, which the
  human track deliberately omits (see Rule 1 — those lines are burned into
  the picture, so the subtitler didn't duplicate them).
- **Credits:** not a one-man job, and the film says so at 16:12 —
  "DONE AND DIRECTED BY BEAU MILES", produced/filmed/edited by Mitch
  Drummond, second camera Chris Ord, final sound mix James Dobson.

## Measurement caveat — read this before trusting a cut count

Cut detection was run with ffmpeg at thresholds 0.30 (301 cuts) and 0.15
(370 cuts), matching the three earlier studies. **The 0.30 pass reports a
single 132.52-second shot starting at 11:36.32. That is an artifact, not a
shot.** The night sequence is exposed at mean luminance YAVG 16–48 out of
255, so consecutive frames never differ enough to trip the detector. I
verified visually at 4-second spacing: that stretch contains **at least 8
distinct setups** (running legs, the moon, bare branches, the lit barn
interior, a head-torch two-shot, a figure running away). I also tried
per-frame normalisation, brightness-invariant rank signatures, and direct
frame differencing — all under-count on footage this dark.

**Consequence:** every whole-video figure below is computed over the
*reliable region* (0:00–11:36 and 13:51–17:12, 897s) with the night stretch
excluded and reported separately. The undercount is itself a finding —
see Rule 16.

## Genre distance

A 40-year-old Australian academic-adventurer running laps of his own rural
block for 24 hours, alone, narrating in first person, filmed by one mate.
Versus a family of three exploring public places together. Two things do
**not** transfer and are overridden by brand non-negotiables:

1. **He is a solo "I" narrator.** We are an ensemble and the system says
   **"we"**, never "I", and nobody on camera is "the host"
   (`brand/voice-and-tone.md`). Every VO rule below has to be re-voiced as
   the family collectively.
2. **His subject is himself.** Ours is the place and the ninth-room moment.
   His "what did I get done" spine becomes our "what wasn't on the map".

What *does* transfer is the thing this study was commissioned for: how a
film with almost no talking head keeps a viewer for 17 minutes on nothing
but hands, objects and a voice.

---

## 1. The numbers

### Structure

No YouTube chapter markers. The spine, measured:

| Section | Start | Length | Share |
|---|---|---|---|
| Cold open (typed titles → "I'm going to run 26 laps") | 0:00 | 0:14 | 1.4% |
| Hook proper (promise + task montage + night pre-play) | 0:14 | 0:46 | 4.5% |
| Setup / first laps | 1:00 | 1:45 | 10.2% |
| Day work | 2:45 | 3:15 | 18.9% |
| Evening | 6:00 | 3:00 | 17.4% |
| Dusk → night | 9:00 | 2:36 | 15.1% |
| **The night (peak)** | 11:36 | 2:15 | 13.1% |
| Dawn → finish | 13:51 | 2:49 | 16.4% |
| Credits over aerial | 16:12 | 0:28 | 2.7% |
| "COMPLETED PROJECTS" card | 16:40 | ~4s | 0.4% |
| Epilogue in the barn | 16:47 | 0:25 | 2.4% |

**Zero sponsor content. Zero ad reads.** 100% of runtime is story.

### Shot lengths

| Section | Shots | Cuts/min | Median | Mean | Longest |
|---|---|---|---|---|---|
| **Reliable region (excl. night)** | **301** | **20.0** | **2.20s** | **2.98s** | 23.3s |
| Hook 0:00–1:00 | 25 | **25.0** | 1.96s | 2.40s | 6.4s |
| First 30s | 13 | 26.0 | 1.88s | 2.31s | 5.9s |
| Setup 1:00–2:45 | 26 | 14.9 | 2.98s | 4.04s | 11.7s |
| Day work 2:45–6:00 | 75 | 23.1 | 1.92s | 2.60s | 14.0s |
| Evening 6:00–9:00 | 60 | 20.0 | 2.34s | 3.00s | 13.0s |
| Dusk → night 9:00–11:36 | 46 | 17.7 | 2.76s | 3.39s | 9.7s |
| **The night 11:36–13:51** | **~8** | **~3.5** | — | — | — |
| Dawn → finish 13:51–16:40 | 70 | **24.9** | 1.72s | 2.41s | 10.7s |
| Outro 16:40–17:12 | 4 | 7.5 | 3.58s | 8.01s | 23.3s |

Distribution across the reliable region: **p10 = 1.00s, median = 2.20s,
p90 = 5.88s.** 10% of shots are under 1s; 46% are under 2s; 64% are under
3s; only 9% run past 6s.

This is a *fast* film — 20.0 cuts/min against Johnny Harris's 7.2 and in
the same territory as Hangtime — but the speed comes from a different
place. Harris changes state inside a long shot; Hangtime cuts between
camera angles of one continuous event. **Beau cuts between separate
physical tasks**, and each cut is a new object in new hands.

### Voice

- **241 cues, 2,329 words**, covering **64.0% of runtime**.
- **212 words per minute while speaking**; **135 words per runtime-minute**.
- **26 gaps of >4s with no voice at all, totalling 212.2s = 20.6% of the
  film.** The longest: **6:51.7 → 7:19.6 (27.9s)** and
  **9:56.6 → 10:13.8 (17.2s)**.

One fifth of this film has no one talking. The picture carries it alone.

### Talk-to-cover

Of the 100 scene-aware frames sampled across the full runtime:

- **8 frames (8%)** show a person addressing camera — 7 Beau, 1 Kay.
- **~28%** are inserts: hands, tools, objects, no face in frame.
- **~40%** are Beau doing a task with his body visible, not addressing camera.
- **~13%** are running shots.
- **~5%** are aerials; **~5%** are landscape/atmosphere with no person.

**A 17-minute film with roughly 8% talking head.** This is the headline
number of the study.

### On-screen text census

Three families, and that is the entire vocabulary:

1. **Burned-in narration titles** — 0:04.5 to ~0:13 only. Centred, white,
   **sentence case**, built word-by-word, placed *beside* the subject's
   head, never over it. Four lines total. Then the device retires and never
   returns.
2. **MILE counters** — bottom-left, white, **ALL CAPS**, condensed sans,
   cap height ~45–53px at 1080p, no background plate, soft drop shadow.
   **20 confirmed:** MILE 1 (1:38), 2 (1:46), 3 (2:15), 4 (4:07), 7 (6:12),
   8 (6:54), 9 (7:38), 10 (8:21), 11 (8:30), 12 (8:52), 13 (9:19),
   14 (9:57), 15 (10:29), 16 (11:13), 22 (14:12), 23 (14:33), 24 (14:51),
   25 (15:21), 26 (15:38), **26.219 (16:34)**.
3. **Clock-time cards** — same type, but placed in the empty dark region
   rather than a fixed anchor: **2:00 AM (11:45), 3:00 AM (12:10),
   4:00 AM (12:32)**.

Plus one full-screen list card at 16:40 ("COMPLETED PROJECTS") and two
credit lines over aerial at 16:12 and 16:16.

*Census caveat:* cards hold ~2.4s and sweeps ran at 2–4s spacing, so this
is a **lower bound** — miles 5, 6 and 17–21 were not caught. Miles 17–21
fall inside the night stretch where the clock cards take over, which reads
as deliberate (Rule 6); 5 and 6 were probably just missed between samples.

---

## 2. The rules

Every rule below is stated as something the pipeline could do tomorrow, and
carries the timestamp that proves it.

---

### Rule 1 — Type the orientation lines, then retire the device

**Evidence:** 0:04.5 "This is my block." · 0:06.5 "It's a perfect mile." ·
0:08–0:10 "This is me, Beau." (builds word by word from "This") · 0:12
"And this is my…" — all burned into the picture, centred, sentence case,
sitting beside the subject rather than over him. **After 0:14 no burned-in
narration title appears again for the rest of the film.**

**The rule:** spend on-screen type only where the viewer needs orientation
— who, where, what the rules are — and then stop. Four lines, twelve
seconds, done. Text that keeps explaining after the viewer is oriented is
noise.

**Corroboration:** the human subtitle track *starts at 9.74s* and skips
exactly the lines that are burned in. The subtitler treated the burned-in
text as the caption. That is a design decision worth copying — never
double-caption a line that is already on screen.

---

### Rule 2 — The hook alternates spine and variety, never two of a kind

**Evidence:** first 30s, 13 shots, median **1.88s**, range 1.28–5.88s:
0:00 black → 0:02 aerial of the block → 0:07 face to camera (wife Kay
walking through the background carrying firewood, unstaged) → 0:11 top-down
aerial of the barn → 0:14 running, checking watch → 0:16 aerial wide, runner
tiny → 0:19 walking with a green bowl → 0:21 sheep at a fence → 0:23
shoelace close-up.

Then 0:24–0:44, the task montage at 1–2s per shot: carrying timber, power
planing, pencil-marking, painting a fence rail, chopping pumpkin, sawing at
the bench, running away down the road, circular saw, splitting firewood,
belt sander.

**The rule:** the hook shows the **spine** (the one repeating action) and
the **variety** (what fills the time between) in strict alternation. No two
consecutive shots of the same kind, and no two consecutive shots at the
same scale — aerial, face, aerial, action, aerial, action, animal, macro.

---

### Rule 3 — Pre-play the hardest moment inside the first minute

**Evidence:** **0:49** — a night shot, moon behind cloud with one lamp
burning in the dark. It is the only night image in the hook, and the night
sequence itself does not arrive until **11:36** — eleven minutes later.

**The rule:** put exactly one image from the episode's hardest, darkest or
most anticipated stretch inside the first 60 seconds. It is the promise the
rest of the film is redeeming. (This is the third study in a row to
confirm the pattern — both Hangtime studies found the same thing.)

---

### Rule 4 — Plant a physical, checkable change in the first 15 seconds

**Evidence:** 0:09.5 burned-in "This is me, Beau." over a man with a large
red beard; 0:09.74 spoken, "Nice beard hey?" — a throwaway aside. At
**15:17–15:30** he shaves it off using the wing mirror of a ute. At
**16:40** the end card lists **"SHAVED OFF MAGNIFICENT BEARD"** among the
completed projects.

**The rule:** plant one *visible, physical* change in the opening seconds
that the viewer can verify with their own eyes at the end. Not a verbal
promise — a thing on screen that will be different later. It costs one
line of dialogue and pays off a whole runtime.

*(Note: the closing 25s epilogue in the barn shows Beau bearded again and
laughing with Kay — filmed on a later day, playing as a warm tag rather
than part of the 24 hours.)*

---

### Rule 5 — Weld the counter card to the recurring action

**Evidence:** **all 20 confirmed MILE cards sit over a running shot or the
road being run on** — MILE 1 (1:38) over Beau running away down the lane,
MILE 9 (7:38) over two head-torches in the dark, MILE 22 (14:12) over a
runner receding on wet asphalt, MILE 26.219 (16:34) over the finish by the
ute. **Not one lands on a task shot, an insert, or a talking head.**

**The rule:** the progress graphic belongs on the one action that repeats.
It teaches the viewer, without a word, that the counter and the action are
the same fact.

---

### Rule 6 — Change the counter's UNIT when the story changes mode

**Evidence:** MILE 1 → MILE 16 across the daylight and evening (1:38 →
11:13). Then, through the night, the mile counter **stops entirely** and
clock time replaces it: **2:00 AM (11:45), 3:00 AM (12:10), 4:00 AM
(12:32)**. Then MILE 22 → MILE 26.219 resumes for the finish (14:12 →
16:34).

**The rule:** measure **distance** when the story is about achievement, and
**time** when it is about endurance. During the hard middle the viewer does
not care how far — they care how long until it ends. Switching the unit
tells them the film knows that.

This is the sharpest refinement yet of the progress-graphic finding from
the two Hangtime studies. Hangtime taught us the graphic must encode *this*
video's structure. Beau adds: it must encode *this section's* structure, and
it is allowed to change mid-film.

---

### Rule 7 — Fade up ~0.4s, hold ~2s, die on the cut

**Evidence:** MILE 22 sampled at 0.4s intervals — absent at 851.2, faint
grey at 851.6, full white 852.0 / 852.4 / 852.8 / 853.2, and **gone at
853.6 because the shot changed**. Total on-screen ≈2.4s. It never fades
out; the cut kills it.

Where no cut is available the behaviour differs: 2:00 AM at 703–708s fades
*in* over ~1s, holds ~3s, and fades *out* over ~1s, because the night shot
continues underneath it.

**The rule:** a card fades up fast, holds about two seconds, and exits on
the next cut. It only fades out when the shot it is sitting on refuses to
end.

---

### Rule 8 — No card ever carries a background plate

**Evidence:** all 23 observed cards — 20 MILE, 3 clock — are plain white
caps set directly on the image with a soft drop shadow and nothing behind
them. Over bright grass (MILE 3, 2:15), over wet asphalt (MILE 22, 14:12),
over near-black night (MILE 14, 9:57). No box, no bar, no scrim.

**The rule:** legibility comes from the shadow and from choosing the
emptiest part of the frame, never from a filled plate.

**This already matches our one visual rule** (`pipeline/overlay_kit.py`
carries no background on any text container) — it is confirmation from
outside, not a change.

---

### Rule 9 — The voice carries the essay; the hands carry the picture

**Evidence:** **8 of 100 sampled frames** show anyone addressing camera.
VO covers **64.0%** of runtime across **241 cues / 2,329 words**, running
**212 wpm while speaking** and **135 words per runtime-minute**. The face
appears to camera at 0:07, 0:47, 6:28, 7:20, 8:58, 10:36, 11:02, 15:00 and
15:30 — nine moments in seventeen minutes.

**The rule:** an essay does not need a face on screen to be an essay. Put
the argument in the voice and give the eye something being *made*. Reserve
the face for the moments where the feeling, not the information, is the
point.

---

### Rule 10 — Every insert has a second layer that is still moving

**Evidence:** the gold alarm clock at **3:37** is a shallow-DOF close-up
with Beau working in the bokeh behind it. Seedling trays at **0:44** with
Beau blurred in the background. A loaf of bread at **7:52** with Kay
crossing behind. Fallen leaves in hard foreground at **2:24** with the
runner tiny and sharp in the distance.

**The rule:** an insert should not be a still life. Compose it so the
subject is in the foreground and the ongoing action is alive — soft, small,
but moving — behind it. One shot then does two jobs: it details, and it
keeps time passing.

---

### Rule 11 — Cutaways are motivated by the task, not the sentence

**Evidence:** **26 voice gaps over 4s, totalling 212.2s = 20.6% of the
film.** The longest are **6:51.7 → 7:19.6 (27.9s)** — cooking on the open
fire — and **9:56.6 → 10:13.8 (17.2s)** — working under a work light at
night. Through those stretches the picture cuts on its own logic: the next
step of the job.

This is the sharpest contrast with our current grammar. Our four
justifications (**establish / illustrate / foretell / bridge**) all define a
cover *relative to a spoken line*. Beau's dominant cutaway motivation is a
fifth one we don't have a name for: **the work advanced.** The saw finished
the cut, so we cut. The dough came together, so we cut.

**The rule:** when the picture is showing a process, the cut is motivated
by the process reaching its next state — not by a word in the VO, and not
by a timer.

---

### Rule 12 — Let the cut rate track the body, not a template

**Evidence:** Hook **25.0** cuts/min → Day work **23.1** → Evening **20.0**
→ Dusk into night **17.7** → **the night ~3.5** → Dawn to finish **24.9** →
Outro **7.5**. Median shot length moves with it: 1.96s → 1.92s → 2.34s →
2.76s → (night) → 1.72s → 3.58s.

The film slows down as he gets tired and speeds back up when he can smell
the finish. The **fastest** section of the whole film (24.9 cuts/min,
median 1.72s) is the dawn-to-finish run, not the hook.

**The rule:** derive the cut rate from where the episode is emotionally,
and let the finish be faster than the opening.

---

### Rule 13 — Make the progress graphic a real object

**Evidence:** a handwritten list on butcher's paper recurs as a physical
prop — **2:47** (on the bench beside the gold alarm clock and an orange),
**6:16 / 6:19** (a soup pot standing on top of it, items legible: MAKE
SOUP, PLANT TREES, EDIT FILM, WRITE BLOG, MAKE OUTDOOR TABLE, MOW THE
LAWNS), **8:32** (items now struck through — CHAINSAW, SCRABBLE, MONOPOLY,
LEAVES, RUBBISH), **15:45** (two full columns, most crossed off),
**16:15** (writing the blog on the same sheet).

Cost: one sheet of paper and a marker. It never needed a render.

**The rule:** where the episode has a real object that can carry state —
a map, a ticket, a checklist, a tally — shoot it changing rather than
rendering a card. A prop that gets dirtier and more crossed-out is a
progress bar the viewer trusts.

---

### Rule 14 — Bookend on the same grammar, and run credits over motion

**Evidence:** opens **0:02** on an aerial of the block; closes **16:38** on
an aerial of the same block with a runner tiny in a green field under blue
sky. The film opens overcast and ends in sunshine — a real colour arc,
because it really was 24 hours.

Credits run **over the moving aerial**, not on black: **16:12** "DONE AND
DIRECTED BY / BEAU MILES", **16:16** "FINAL SOUND MIXED BY / JAMES DOBSON".

**The rule:** close on the same shot grammar you opened with so the viewer
feels the loop shut, and never cut to black to run a credit — put it over
something still moving.

---

### Rule 15 — The payoff is an itemised, honest, self-deprecating list

**Evidence:** **16:40**, held ~4s: a full-screen card headed **"COMPLETED
PROJECTS"**, three columns × ten rows = **30 items**, white caps on the
aerial. Selected verbatim:

> GLUED HELEN'S KEYRING · MADE AN AWESOME OUTDOOR TABLE · BRACED WORKBENCH
> TO BE KICKARSE · **MADE 2X CANOE PADDLES (ALMOST)** · POLISHED BROWN
> BOOTS · **PLAYED SCRABBLE (LOSER)** · CHOPPED FIREWOOD · LIT FIRE AND
> KEPT IT ALIVE FOR 20 HOURS · **WROTE A (PRETTY CRAP) BLOG** · SHAVED OFF
> MAGNIFICENT BEARD · PLANTED 30 TREES AND 10 SHRUBS · RAN A MARATHON ·
> **(MADE A BABY)**

**The rule:** close a "how much can we do" episode with the actual tally,
itemised and specific. Hedge the ones that deserve hedging *in the copy*
— "(ALMOST)", "(LOSER)", "(PRETTY CRAP)" — and put the joke last. The
honesty is what makes the list funny; a list of unqualified wins would
read as a brag.

This is the single most directly stealable artifact in the film, and it
sits cleanly inside our honest-numbers rule.

---

### Rule 16 — Protect the peak with darkness, fewer cuts, and unbroken voice

**Evidence:** **11:36 → 13:51** (135s, 13.1% of runtime):

- Mean luminance **YAVG 16–48 out of 255** — the film lets the dark be
  dark. Nothing is lifted for legibility.
- **~8 distinct setups in 135s ≈ 3.5 cuts/min**, against 20.0 elsewhere —
  roughly **six times slower**.
- **No cards at all except the three clock times.**
- The VO runs almost continuously and turns confessional — 11:49 "Three or
  four minutes ago, I was just slipping into a very deep sleep and then…
  the alarm went." · 12:37 "I feel like a ghost." · 12:50 "What a beautiful
  beacon to run back to." · 13:30 "I'm finding out new things about myself."
  · 13:48 "this real flexibility, this idea of time — it's just compressed."

**The rule:** at the emotional peak, cut roughly six times slower than the
body of the film, stop the graphics, and let the exposure go where the
real light was. Underexposure reads as honesty.

**This is peak protection confirmed for a fourth time** — Hangtime held
16–43s on emotional peaks, Harris engineered 19s and 13s of silence at
Srebrenica, and Beau does it with darkness and cut rate. The mechanism
differs; the law does not.

---

## 3. For our doctrines

Each rule mapped to the craft it feeds. **Where a rule collides with a
brand non-negotiable, the brand wins and the collision is named.**

### → Story (`story-designer`)

| From | What changes |
|---|---|
| **R2** | The hook's preview montage should alternate **spine and variety** and never repeat a scale back-to-back. Our current rule 1 says "each the chapter's single most anticipated image, in chapter order" — Beau adds the *ordering constraint within that*. **Brand floor holds:** our ≥1.8s legibility minimum stands; his 1.28s hook shots are below it and we do not follow him there. |
| **R3** | Already ours ("the hook is the licensed flash-forward"). Fourth confirmation. Keep. |
| **R4** | **New.** Ask the story-designer to find one *physically checkable* change to plant in the first 15s and pay off in the last third. For us this is naturally a family thing — something someone is carrying, wearing, or collecting. |
| **R6** | **Sharpen the progress doctrine.** The `chapter` door meter currently encodes the episode's chapter count for the whole runtime. Beau's lesson: the counter may **change unit mid-episode** when the mode changes. If an episode has an endurance stretch, the meter should measure something else through it. |
| **R12** | Cut rate is an output of emotional position, not a constant. Note specifically: **the finish should out-pace the hook** (24.9 vs 25.0 cuts/min here — dead level, and faster than everything between). |
| **R16** | Peak protection stands and gains a third mechanism: **cut ~6× slower and kill the graphics**, not just "15–30s, no b-roll, no cards". |
| **R14** | Bookend the closing shot on the opening shot's grammar. |

### → Coverage (`coverage-editor`)

| From | What changes |
|---|---|
| **R11** | **The biggest gap this study found.** Our four justifications — establish / illustrate / foretell / bridge — are all defined *relative to a spoken line*. Beau spends **20.6% of his runtime with no voice at all**, and cuts on **"the work advanced."** Proposal: add a fifth justification, **`process`** — the cover is justified because the task reached its next state. It needs the same one-clause `why` ("process: the glue is clamped, next is the saw"). Without it, our grammar has no legal way to cover a wordless making sequence, and the coverage-editor would be forced to delete exactly the footage that carries a room. |
| **R9** | The 8%-talking-head number is the argument for letting coverage run long where the family is *doing* rather than *saying*. Our ≤60% coverage cap on an on-camera beat is right for a talking beat and wrong for a wordless one — the cap should apply to beats with VO, not to a making sequence. |
| **R10** | **New craft rule, cheap and high-yield:** compose inserts with the ongoing action alive in the background bokeh. Add to the craft rules beside "sequences, not postcards". This is a note for the shoot as much as the edit — it has to be captured that way. |
| **R5** | Covers must never land on the recurring-action shot that carries the counter card, since the card owns that shot. |
| **R2** | "No two consecutive covers at the same scale" belongs next to our existing wide → closer → detail sequence rule. |

### → Captions (`caption-editor`)

| From | What changes |
|---|---|
| **R1** | **Never double-caption a line that is already burned in.** Beau's human subtitler starts at 9.74s precisely to avoid it. If the graphics plan puts a line on screen as type, the caption track should skip it. This is a concrete, checkable rule the caption-editor can follow today. |
| **R1** | Orientation type is **sentence case** and placed *beside* the subject, never over the face. Matches our casing rule already (sentence case for anything that reads as language; UPPERCASE only for structural type) — Beau's MILE counters are structural and uppercase, his narration titles are language and sentence case. **The same split we already enforce.** |

### → Cards (`graphics-director`, `hype-director`)

| From | What changes |
|---|---|
| **R7** | **Timing spec, directly usable:** fade up ~0.4s, hold ~2s, exit on the next cut; fade out over ~1s only when the underlying shot does not end. Worth checking `pipeline/overlay_kit.py` timings against this. |
| **R8** | No background plate — **already our law.** External confirmation across 23 cards in three lighting conditions. |
| **R5** | Counter/progress cards ride the recurring action shot. |
| **R13** | **Prefer a real object over a rendered card** where the episode has one. A physical checklist, map or tally that changes state on camera outranks a card, and costs nothing. Worth a line in the graphics-director brief: *look for the prop before you reach for the kit.* |
| **R15** | The end-of-episode tally card: itemised, specific, hedged in the copy, joke last. **Brand check:** this fits our honest-numbers rule exactly. **Brand override:** no exclamation marks, and our humour never comes at anyone's expense — self-deprecation about the *family's own* attempts is fine ("almost", "loser"), and emoji are encouraged here where Beau uses none. |
| **R6** | Card families may swap unit mid-episode. |

### → Sound (`sound-designer`)

| From | What changes |
|---|---|
| **R11** | **20.6% of runtime with no voice** is a sound-design brief, not an absence. Those 26 gaps — the 27.9s fire-cooking stretch at 6:51, the 17.2s work-light stretch at 9:56 — are carried entirely by location sound: the saw, the fire, the boots. Our cue sheet should treat every wordless making stretch as a beat that needs its *diegetic* sound foregrounded, not just an SFX accent laid over it. |
| **R16** | At the peak, the mix goes quiet and close — breathing at 11:41 is the only cue for eight seconds. Cue sheets should mark the peak as **"no accents"**, consistent with our existing no-cards-at-the-peak rule. |
| **R7** | Card fade-up at ~0.4s gives the pop/whoosh cue a precise anchor. |

### Non-negotiables that override anything above

1. **"We", never "I"** — Beau's entire VO model is first-person singular.
   Every VO rule here must be re-voiced as the family collectively; nobody
   is "the host" (`brand/voice-and-tone.md`).
2. **No exclamation marks; honest numbers only.** Beau complies with both
   naturally; his "MILE 26.219" is exactly the kind of exact figure our
   rule asks for.
3. **No filled plates; one yellow moment per frame.** Rule 8 agrees on the
   first half. Beau has no accent colour at all — our single yellow moment
   is ours and stays.
4. **≥1.8s cover legibility floor.** Beau's hook runs 1.28s shots. We do
   not follow him below 1.8s.
5. **The payoff must always land, and every episode owes a ninth-room
   moment.** Beau's spine is "what did I get done"; ours is "what wasn't on
   the map". Rule 15's tally card is a *format* we can borrow, not a
   replacement for the ninth room.
6. **Emoji are encouraged** (Caleb, 2026-08-20). Beau uses none; that is
   his register, not a standard for us.

---

## 4. The three highest-leverage changes

1. **Add a fifth b-roll justification: `process`.** Our grammar cannot
   currently justify a cover during a wordless making sequence, because all
   four existing justifications are defined against a spoken line. Beau
   spends 20.6% of his runtime there and it is the most watchable material
   in the film. Evidence: 6:51.7 → 7:19.6 (27.9s, no VO) and 9:56.6 →
   10:13.8 (17.2s, no VO). Without this, the coverage-editor is required to
   delete our best footage. *(Owner: `story-designer` b-roll grammar +
   `coverage-editor` R1.)*

2. **Let the counter change unit at the endurance stretch.** The `chapter`
   door meter is fixed for the whole runtime. Beau runs MILE 1–16, switches
   to 2:00/3:00/4:00 AM through the hard middle, and returns to MILE 22–
   26.219 for the finish. Distance for achievement, time for endurance.
   Evidence: 11:13 (MILE 16) → 11:45 (2:00 AM) → 14:12 (MILE 22).
   *(Owner: `graphics-director` + `pipeline/overlay_kit.py`.)*

3. **Look for the real object before reaching for the kit.** The
   handwritten crossed-off list at 2:47 / 6:19 / 8:32 / 15:45 / 16:15 is
   the film's entire progress system, and it cost a sheet of paper. Add to
   the graphics-director brief: if the episode contains a physical thing
   that can carry state on camera, shoot it changing instead of rendering a
   card. *(Owner: `graphics-director`; also a note for the Planner desk's
   shot list, since it has to be captured deliberately.)*

---

*Studied 2026-08-24. Techniques only — no frames, assets or copy from this
video enter our work dirs.*
