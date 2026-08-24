# Film study — Mark Rober, "Backyard Squirrel Maze 1.0 — Ninja Warrior Course"

> **Rules only.** Every line below is something a story-designer, coverage-editor,
> graphics-director, caption-editor or sound-designer could execute tomorrow, with
> the timestamp that proves it. Nothing here is a vibe. Where a rule collides with
> a Ninth Room non-negotiable, the non-negotiable wins — see §5.

---

## The card

- **Video:** *Backyard Squirrel Maze 1.0 — Ninja Warrior Course*
- **Source:** https://www.youtube.com/watch?v=hFZFjoX2cGg (uploaded 2020-05-24)
- **Runtime:** 20:20 (1220.1 s) · 146.9 M views · 2.76 M likes · 93 K comments
- **Why this one:** the most-watched long-form video on the channel by a wide
  margin, family-audience, and its entire spine is promise-and-payoff — which is
  the brief. The glitter-bomb videos are more famous as *stunts*; this one is the
  better teacher of *structure*.
- **Studied:** 2026-08-24 — five passes: 100 scene-aware frames full-range, a
  9-frame hook pass at shot midpoints, an 18-frame pass across the rewind bridge
  at 8 fps, a 14-frame direct-address sweep of the back half, and 8 frames across
  the reveal sequence. Plus per-frame luminance scans of every black run.
- **Transcript:** YouTube's own English caption track (562 cues, human-quality —
  it carries sound-effect cues like `(record scratches)`, so it is a real
  subtitle file, not auto-ASR slop). Quotes below are exact.

### Measurement notes and honest caveats

- **Cut detection:** ffmpeg scene detection at thresholds **0.30 (376 cuts)** and
  **0.15 (434 cuts)**, matching the four earlier studies so the numbers compare.
  Unless stated, figures are the 0.30 pass. Scene detection under-counts
  match-cuts and same-angle cuts and over-counts inside the VHS-rewind montage;
  both are flagged where they matter.
- **The download is 360p** (YouTube blocked every higher format for this session).
  Composition, cut rhythm, luminance and large on-screen type all read fine; small
  type would not, so no claim below rests on small type I could not read.
- **The file has a 79 s tail** of silent, unrelated workshop footage past the real
  20:20 end (video stream 1299 s, audio stream 1220.1 s). All measurement was done
  on a trimmed 0–1220.14 s copy. Frame-to-caption alignment was verified at eight
  points across the runtime before any timestamp below was written.
- **Genre distance is large and matters.** One presenter with a workshop, a
  month of shooting, a build collaborator, six camera systems including 24/7
  streaming cams and night IR, and a subject that performs on demand for free.
  We have a family, a trip, and a day. Every rule below is stated in a form that
  survives that translation; where it does not survive, it says so.

---

## §1 — The numbers

### Whole video

| Measure | Threshold 0.30 | Threshold 0.15 |
|---|---|---|
| Cuts | 376 | 434 |
| Shots | 377 | 435 |
| **Median shot** | **2.42 s** | 2.17 s |
| Mean shot | 3.24 s | 2.80 s |
| **Cuts / min** | **18.5** | 21.3 |
| p25 / p75 | 1.50 s / 3.84 s | 1.21 s / 3.46 s |
| p90 | 6.21 s | 5.59 s |
| Shots under 2 s | 37.7 % | 45.3 % |
| Shots under 1 s | 12.5 % | 19.8 % |
| Shots over 10 s | 11 | 9 |
| Longest shot | 32.03 s (17:40) | 28.70 s (15:34) |

For scale against the shelf: Hangtime's waterpark videos ran 2.8–3.0 s medians;
Johnny Harris ran 4.1 cuts/min in his hook. **This is the fastest-cut video in
the collection** — 18.5 cuts/min sustained across twenty minutes — and it is
also the one aimed hardest at a family audience. Speed and warmth are not in
tension here.

### Section table

| Section | Span | Length | Cuts | c/min | Median | Max |
|---|---|---|---|---|---|---|
| Hook (cold open) | 0:00.00–0:21.56 | 21.6 s | 8 | 22.3 | 1.96 s | 6.34 s |
| Blackout + rewind bridge | 0:21.56–0:28.41 | 6.9 s | 18 | **157.7** | **0.08 s** | 2.50 s |
| The problem: four feeders beaten | 0:28.41–3:08.98 | 160.6 s | 51 | 19.1 | 2.40 s | 12.47 s |
| Glitter-bomb thesis callback | 3:08.98–3:28.38 | 19.4 s | 9 | 27.8 | 1.88 s | 4.25 s |
| Build montage | 3:28.38–3:45.42 | 17.0 s | 14 | 49.3 | 1.00 s | 2.09 s |
| Course tour (8 obstacles) | 3:45.42–7:56.12 | 250.7 s | 92 | 22.0 | 2.34 s | 9.63 s |
| Trials (cast + obstacle results) | 7:56.12–14:45.48 | 409.4 s | 104 | 15.2 | 3.21 s | 14.97 s |
| Jackpot payoff | 14:45.48–15:40.56 | 55.1 s | 20 | 21.8 | 2.25 s | 7.04 s |
| Squirrel-pult + physics | 15:40.56–18:19.29 | 158.7 s | 23 | **8.7** | 3.57 s | **32.03 s** |
| Wind-down / picnic table | 18:19.29–19:07.53 | 48.2 s | 12 | 14.9 | 2.17 s | 13.64 s |
| Takeaway | 19:07.53–20:14.06 | 66.5 s | 24 | 21.6 | 1.71 s | 7.42 s |
| Outro card | 20:14.06–20:20.14 | 6.1 s | 1 | — | — | — |

The shape: fast everywhere (15–28 cuts/min), **one deliberate slow zone** at the
physics finale (8.7 cuts/min, and the three longest shots in the whole video sit
inside it at 15:33, 16:35 and 17:40), and **one deliberate strobe** in the
seven-second bridge out of the hook.

### Voice, silence, density

| Measure | Value |
|---|---|
| VO coverage | **1077.7 s = 88.3 %** of runtime |
| Wordless | 142.5 s = 11.7 % |
| Words | 3,865 |
| Rate over runtime | **190.1 wpm** |
| Rate while speaking | **215.2 wpm** |
| Silences ≥ 1.5 s | 19 |
| Longest silence | 13.12 s (8:13.25–8:26.37) |
| "you" (direct address) | 31 |
| Question marks in VO | 7 |

Compare Beau Miles: 20.6 % wordless, 8 % talking head. Rober is the opposite
pole — near-continuous narration at 215 wpm — and both hold an audience. The
variable that matters is not talk density, it is **rate of new information**.

### Who is on screen

Of the 100 scene-aware frames sampled across the full runtime:

- **16 frames show direct address to camera.** All sixteen fall between **0:00
  and 7:35.**
- 15 more show a human not addressing camera (building, installing, or inside a
  clip borrowed from another video).
- **69 frames have no human in them at all.**
- A separate 14-frame sweep evenly spaced from 8:20 to 20:00 found **zero**
  pieces to camera. The only human in that sweep is at 18:30, at distance,
  taking the course down.

**The presenter is gone for the last 62 % of the runtime.** Everything after the
course opens is subject footage under voiceover.

### On-screen graphics census

Nine designed full-frame graphic events in twenty minutes — one every ~2.3
minutes — and **five of the nine are black cards**:

| # | t | Duration | What |
|---|---|---|---|
| 1 | 0:22.77 | 0.96 s | Small bottom-line joke card on black: *"(after 9 years of making videos I suppose you probably aren't)"* |
| 2 | 0:23.77 | 2.01 s | `REWIND ◀◀` label over a VHS-degraded reverse montage |
| 3 | 3:25.58 | 2.79 s | Pure-black curtain, no type, ahead of the build montage |
| 4 | 13:02 | ~3 frames | White flash on a camera-shutter SFX (the Tourist Trap photo op) |
| 5 | 13:26–13:35 | ~9 s | Full "CSI zoom-enhance" HUD, then three 0.50 s step-zoom cuts |
| 6 | 13:35.82 | 3.21 s | A real Google search bar typing out *"Do boy squirrels have nippl…"* |
| 7 | 13:39.03 | 4.05 s | SMPTE colour bars, `PLEASE STAND BY` |
| 8 | 13:43.07 | **3.30 s** | Pure black — the reveal is spoken over it |
| 9 | 17:00.89 | 1.59 s + 0.21 s + 2.00 s | Black card `300 milliseconds`, then black, then a **5-frame white flash**, then black |
| — | 20:17.55 | 2.63 s | `please consider subscribing`, monospace, black |

**There is no burned-in subtitle track.** There is exactly one editorial caption
in everything sampled — *"no, seriously"* at 13:46.4 — and it says something the
voiceover does **not** say. On-screen type in this video is only ever a **joke**
or a **number**. It is never a transcription.

**Five graphics are physical objects, not renders:** the seven-nut buffet with
chalk labels (4:04, again full-frame at 9:16); the four cast name-boards with
hanging weight tags (9:30, delivered as a 2×2 quad-split); the re-lettered
`Phat Gus / charming / slovenly` board (13:51); the `manual override` Sharpie
block held to camera (16:05). Cost: some scrap ply and a chalk marker. This is
Beau Miles' "the progress graphic is a real object" finding confirmed a second
time by a completely different creator at a hundred times the budget.

**At least eight split-screen or picture-in-picture moments** in the 100-frame
sample (4:04, 5:04, 9:04, 11:03, 11:14, 12:30, 17:50, 18:46) — a floor, not a
count, since the sample is sparse.

---

## §2 — The rules

### A. Hook anatomy

**R1 — The first image is the finished thing, and the first cut lands at 1.54 s.**
Shot 1 (0:00.00–1:53) is a medium of the presenter standing beside the payoff
object — the jackpot bird feeder that the whole video is about reaching. No logo
sting, no channel intro, no "hey what's up guys." First words: *"This is a bird
feeder."* Nine shots in 21.56 s, median 1.96 s.

**R2 — Spend the hook's longest shot on the promise, and make it one unbroken
move.** Shot 4 is 6.34 s (0:04.96–0:11.30), a single continuous camera move down
the length of the course, carrying the line *"they will first need to pass
through what is basically an eight-part 'Ninja Warrior' obstacle course for
squirrels"* (0:06.48–0:11.46). The promise is a **countable number** — eight —
delivered while the eight things are physically on screen. Every other hook shot
is 1.25–2.84 s.

**R3 — Close the hook by admitting you lose.** Shots 5–9 (0:11.30–0:21.56) are
five escalating proofs, each 1.25–2.84 s, and every one of them shows a squirrel
*beating* something. The line under them:

> *"This course is extremely challenging. It is not for the timid of heart. But
> out of the gate, I will admit that in hindsight that I completely
> underestimated my adversary."* (0:11.46–0:21.63)

The gap is not "watch me win." It is **"I lost and you have to see how."** The
antagonist is named as an adversary in the hook's last word.

**R4 — Zero on-screen text in the hook.** No title, no name, no stat card, from
0:00.00 to 21.56. The first type in the video is a self-deprecating joke, and it
arrives on a black frame *after* the hook is over.

### B. The bridge out of the hook

**R5 — Blackout for ~2 s to change time, and hide a joke in the second half of
it.** 0:21.563–0:23.732, 2.169 s of black. Pure black (YAVG 16.0) for the first
1.17 s; then at 0:22.773 a small line of type appears at the bottom of the frame
for **0.96 s**:

> *"(after 9 years of making videos I suppose you probably aren't)"*

It is answering his own spoken line *"Now if you're wondering why I would go
through all this trouble"* (0:21.63–0:23.88). The narration never stops. The
blackout is not a pause — it is a **surface for the aside the voice can't make.**

**R6 — Rewind the story, don't dissolve it.** 0:23.774–0:25.78, **2.01 s**, 16
cuts, median shot **0.08 s** (two frames), one `REWIND ◀◀` label top-left and a
VHS tracking-noise treatment on everything. Sampled at 8 fps, the montage runs
in **reverse chronological order**: finale → obstacles → cowboy board → jackpot
underside → **him building the course** (25.55) → **him sitting bored on the
living-room couch** (25.80). It lands on the origin image and holds it 2.50 s
while the VO catches up: *"when I found myself stuck at home and very bored"*
(0:25.74–0:28.41).

The whole device is: **2 seconds, one label, reverse order, land on the origin
and let the voice name it.** It costs one text label and clips you already have.

**R7 — Announce a montage, then cut to black before it.** 3:25.580–3:28.333,
**2.79 s of pure black with no type**, under the line *"we put it all together
in this 20-second build montage"* (3:25.68–3:28.49). Then 17.04 s of montage, 14
cuts, **median shot 1.00 s**. The black is a curtain: it tells the eye a
different kind of thing is about to happen.

### C. Promise-and-payoff architecture

**R8 — Open every loop in one contiguous block, close them in the same order.**
The tour (3:45–7:56, 250.7 s) names eight obstacles at an average of one every
**22.1 s**. The trials (7:56 onward) deliver all eight in the identical order:

| # | Obstacle | Promised | Paid | Gap |
|---|---|---|---|---|
| 1 | Bridge of Instability | 4:43.47 | 8:09.75 | 3:26 |
| 2 | Maze of a Thousand Corridors | 5:05.97 | 10:07.74 | 5:02 |
| 3 | Pitchfork Tumblers of Treachery | 5:10.94 | 10:19.26 | 5:08 |
| 4 | The Homewrecker | 5:27.81 | 11:15.27 | 5:47 |
| 5 | Slinky Bridge of Deception | 5:56.04 | 12:32.58 | 6:37 |
| 6 | Tourist Trap | 6:05.49 | 12:57.45 | 6:52 |
| 7 | Quad Steps of Great Elevation | 6:20.70 | 13:57.33 | 7:36 |
| — | **The jackpot** | 7:42.75 | **14:45.48** | 7:03 |
| 8 | Orbital Assist Platform ("squirrel-pult") | 6:38.46 | **15:42.93** | **9:05** |

Two things are engineered here, and both are copyable:

- **The gap widens monotonically**, 3:26 → 7:36, as the viewer's investment
  grows. Early loops close fast to teach the audience that loops close at all.
- **The emotional climax is not last.** The jackpot lands at 14:45 (72.5 % of
  runtime); the eighth obstacle — the one whose payoff was *weakest*, because the
  squirrels mostly refused to trigger it — is held back and re-purposed as the
  **intellectual** finale.

**R9 — Name the loop the viewer is still holding, out loud, before you close
it.** *"And while we're watching, you might be wondering what happened to the
squirrel-pult"* (15:40.56–15:42.93), immediately followed by the honest answer:
*"Unfortunately, they didn't really fall for my illusion much, but I'm about to
show you the two times they did."* The weakest result in the video is not
buried; it is announced, admitted, and then converted into the best segment.

**R10 — Pay the most charming promise twice, and make the second payment the
last image.** The Tourist Trap is promised at 6:05.49 as a photo op. It pays at
12:57–13:20. It pays **again at 20:10** — a real squirrel's head through the
hand-painted cowboy board — and that is the final picture before the outro card
at 20:17.55. The last shot of the video is not a new thing; it is a promise
being kept one more time.

### D. Cut motivation

**R11 — Every cut in the tour is motivated by the presenter physically moving to
the next object.** The tour is 92 cuts over 250.7 s (22.0 c/min, median 2.34 s)
and there is no cutaway grammar in it at all: he stands *beside* each obstacle
and the cut goes to him standing beside the next one (4:24, 4:36, 4:48, 4:59,
5:28, 5:50, 5:58, 6:35, 6:51). The set is the graphic.

**R12 — Interrupt your own sentence with a 3-clip montage, and finish the
sentence on the far side.** At 7:13.62 he starts *"I know I seem to have this
reputation of —"*, then 6.26 s of clips from his own earlier videos punctuated
only by SFX cues in the caption track — `(fire sizzling)` 7:16.03, `(glass
shattering)` 7:17.94, `(people screaming)` 7:19.11 — and then the sentence lands:
*"— improvised high-speed projectiles"* (7:22.29). The grammar reads instantly
because the sentence is **incomplete** across the gap.

**R13 — Put the reference and the reality on screen at the same time.** Every
pop-culture or evidence callout is a split or a PIP, never a full-frame cutaway:
the seven-nut buffet beside the talking head at 4:04; a red vertical wipe into
his own carnival-games video at 5:04; a Spider-Man clip beside the live squirrel
at 9:04; stock camo-photographer footage beside his own set-up at 11:03; a `Nest`
camera PIP against the main angle at 11:14, 12:30 and 18:46; Destin's cat-flip
footage beside his own launch at 17:50. **The joke never costs the viewer the
picture.** He also leaves the `Nest` on-screen watermark visible rather than
cropping it — the camera brand is the authenticity marker.

**R14 — Protect the peak with a 6× slower cut rate, not with music.** The physics
finale (15:40.56–18:19.29) runs **8.7 cuts/min against a 18.5 whole-video
average**, and contains the three longest shots in the video: 28.7 s at 15:33,
25.5 s at 16:35, 32.0 s at 17:40. All three are slow-motion analyses of a single
half-second event. This is peak protection confirmed for the **fifth** time
across five studies, in its most extreme form yet.

**R15 — Shut up for 7 seconds after a setup line.** Nineteen silences ≥ 1.5 s.
The load-bearing ones are all punchline pauses:

| t | Length | Set up by | Resolved by |
|---|---|---|---|
| 8:13.25 | **13.12 s** | `(bright electronic music)` | *"That didn't exactly go as planned"* |
| 13:05.39 | 8.29 s | `(playful music)` | *"Now here comes Phat Gus."* |
| 11:24.29 | 7.33 s | *"His buddy Marty, on the other hand…"* | *"She is a cruel mistress."* |
| 16:42.85 | 1.97 s | *"Did you catch it?"* | *"The first critical moment is right here."* |

The 11:24 one is the model: **name the setup, stop talking for seven seconds,
land the punchline.** The 16:42 one is the model for engagement: **pose, show,
pause for two seconds, answer.**

### E. Cast

**R16 — Introduce the cast *after* the first attempt fails, not before.** The
course opens at 7:56. The first contender attempts and fails at 8:09–8:26. Only
then — at 8:26 — does the roster arrive, and it is introduced *out of* that
failure: *"That didn't exactly go as planned, so Rick decides to regroup.
Speaking of which, that's Rick."* The cast card is a consequence of an event the
viewer already cares about.

**R17 — Give each character one number, one adjective, and one flaw, in under
12 seconds.** 8:26–9:30, 64 s for four characters:

- *Rick — 500 g — "very clever… but he also gets spooked easily."*
- *Marty — "basically indistinguishable from Rick"; "Rick and Marty are inseparable."*
- *Frank — 500 g — "He's very gutsy. He's also kinda dumb."*
- *Phat Gus — 800 g — "really charming… will strike a pose if he sees a camera."*

The number is real (a custom scale is shown at 8:38). The flaw is what makes each
one legible in a two-second shot 200 seconds later.

**R18 — Close the cast block with a recap card, then say the next name.** At 9:30
a 2×2 quad-split shows all four wooden name-boards at once; the VO under it is
*"So now that you know our four contenders, let's get back to Rick"* (9:29.49).
The card exists to hand the viewer a lookup table and then immediately use it.

### F. The reveal — the "ninth room" of this video

The single most transferable sequence in the film. Measured to the frame:

| t | Duration | What is on screen | What the voice says |
|---|---|---|---|
| 13:26.0 | 4.8 s | Full sci-fi HUD, footage inset, `ZOOM PERCENT 50.00%` | *"…he looks at the camera, wait a second. Play that back, and freeze."* |
| 13:34.19 / 13:34.69 / 13:35.19 | 0.50 s each | **Three step-zoom cuts**, HUD stripping away | *"Zoom, enhance."* + `(record scratches) (eerie music)` |
| 13:35.82 | **3.21 s** | A real Google search bar typing `Do boy squirrels have nippl…` | `(air whooshes) (keyboard clacking)` — **no words** |
| 13:39.03 | **4.05 s** | SMPTE colour bars, `PLEASE STAND BY` | `(lighthearted music)` — **no words** |
| 13:43.07 | **3.30 s** | **Pure black** | *"Well, turns out Phat Gus is not a dude and he's pregnant, which meant I was suddenly feeling real uncomfortable about all those weight comments."* |
| 13:46.37 | — | Footage returns, caption *"no, seriously"* | *"So after a bit of a pivot to smooth things over…"* |
| 13:51 | — | The name-board, **re-lettered**: `Phat Gus / charming / slovenly` | — |

**R19 — Deliver the biggest fact of the video on pure black.** 3.30 s, the
longest engineered blackout in the film, with nothing on it. Nothing competes
with the sentence.

**R20 — Show the actual research query.** 3.21 s of a real search bar, typed
live. It is simultaneously the funniest shot in the video and the *proof* that
the claim was checked. Honesty and comedy in the same frame.

**R21 — Admit the rupture with a card instead of hiding the seam.** 4.05 s of
`PLEASE STAND BY` says *the video is about to change its mind*. It buys the
audience four seconds to expect a reversal.

**R22 — When you learn you were wrong about someone, correct the on-screen
record, and retire the joke.** The physical name-board is re-lettered on camera
at 13:51. And the name change is total: **"Phat Gus" appears 9 times, the last
of them inside the reveal line at 13:43.11; "Phantastic Gus" appears 8 times,
the first at 14:18.93, and it is the only form used for the remaining 6 minutes,
through the final line at 20:05.82.** The replacement joke flatters instead of
mocking: *"when you sit like that, you don't look an ounce over 700 grams"*
(15:24.30).

### G. Numbers on screen

**R23 — Make the graphic's *duration* be the fact.** 17:00.89: a black card reads
`300 milliseconds` and holds 1.585 s under the spoken number. Then 0.96 s of
plain black under *"That's exactly this long"* (17:02.64). Then a **single white
flash of exactly 5 frames — 0.208 s at 23.976 fps** (17:03.523–17:03.689). Then
2.00 s of black under *"Literally less than the blink of an eye."*

The demonstration is not a diagram. It is a flash whose *length* is the claim.
(Measured honestly: the delivered flash is ~0.21 s, not the 0.300 s stated — see
§5, this is exactly the gap our voice doc forbids.)

**R24 — Every number in the video is one the presenter measured.** 500 g and
800 g come off a custom scale shown on camera (8:38). "Walnuts" is justified by a
seven-nut buffet run four times: *"over the course of a week, I put out a buffet
of seven different nuts and seeds. And all four times I repeated the experiment,
walnuts were always the one they ate first"* (4:04.35–4:14.01) — and the buffet
board is on screen in split while he says it. The launch force is stated as
*"40 % full power… about half a g, which is 10 times less than a typical
rollercoaster"* (15:49.98–15:57.81). "Less than 40 seconds" for a full run
(15:37.89) is a stopwatch claim, not a feeling.

### H. The ending

**R25 — Do not slow down for the moral. Speed up, and make every cut a new
proof.** The takeaway (19:07.53–20:14.06, 66.5 s) runs **21.6 cuts/min, median
1.71 s** — faster than the video average — and every shot is *new evidence the
viewer has not seen*: vines spiralling for a grip, a spider's leap, night-IR
animals using the fence as a highway, the dog and a squirrel nose to nose. The
thesis rides on top:

> *"It's also made me realize that even amongst the structures and pavement and
> power lines, how interesting nature can be in a single suburban backyard if you
> just really stop to look."* (19:14.79–19:24.18)

The lesson is proven by footage, not asserted over a slow shot.

**R26 — End on a small, specific, forward-looking image, then one flat card.**
Final line: *"…squirrels can live to be 20 years old, and so I like to think that
someday, Phantastic Gus will bring his grand-squirrels to the fence and regale
them with tales of cowboys and courage and legendary walnut piles"*
(20:04.20–20:14.06) — over the cowboy-board payoff. Then 2.63 s of monospace on
black: `please consider subscribing`. The ask is **six words, once, at the very
end, with no animation.**

---

## §3 — Where this contradicts our current defaults

| Our default | What this video does | Verdict |
|---|---|---|
| Coverage ≤ 60 %, b-roll justified against a spoken line | 69 % of sampled frames have no human at all; the last 62 % of runtime has no direct address whatsoever | **Our ceiling is too low for a payoff act.** See D1 |
| Cards every 60–90 s (`engagement-playbook.md` rule 1) | Nine designed graphics in 20:20 — one per 2.3 min | **Both can be true**, because his engagement lives in the *structure* (an eight-loop ledger), not in cards. See D2 |
| Median shot target inherited from Hangtime (~2.8–3.0 s) | 2.42 s at the same threshold, and 22 c/min in an explainer section | Faster is available to us without losing warmth |
| The `chapter` door meter carries structural state | The structural graphic here is a **wooden sign** and a **spoken ordinal list** | Our door meter is better; keep it. But the *cast* graphic should be physical |
| Peak protection = hold the shot | Confirmed, fifth study — and here it is a 6× cut-rate drop plus slow motion | No change; stronger evidence |
| Hook = preview the chapters (Hangtime finding) | Hook = state one countable promise, then admit defeat | **Both work.** Ours should carry the admission too |

Things this video does that we already do and should keep doing: the loop
ledger, the physical progress object, engineered silence at the punchline,
honest sourcing of every number, and one flat unanimated ask at the end.

---

## §4 — For our doctrines

Each rule mapped to the craft it feeds and the file or agent that owns it.

### Story — `story-designer`, `edit_plan.json`

- **D1 — The presenter act and the payoff act are different films.** All 16
  direct-address frames land in the first 38 % of runtime (R-set B/C). Rule for
  the story-designer: **all pieces-to-camera belong before the payoff act
  opens.** Once the promise is made and the trials begin, the family stops
  addressing camera and the voiceover carries it. Concretely, the plan should
  mark a `payoff_opens_at` beat; after it, no beat's primary take may be a
  piece-to-camera.
- **D2 — Write the loop ledger before writing beats.** R8. Every promise made in
  the setup gets an explicit paid-at beat, in the same order, with a widening
  gap. If a promise has no paid-at beat, either cut the promise or find the
  footage. This is a validation we can literally run.
- **D3 — Hold back the weakest result and convert it.** R9. The obstacle that
  didn't work became the best segment because it was *named as unresolved* and
  then answered with something better. When a chapter under-delivers, the plan
  should say so on camera and re-purpose it, never bury it.
- **D4 — The hook states one countable promise and then admits the loss.** R2 +
  R3. `hook` beat rule: one number the viewer can hold ("nine rooms", "four
  floors, one door that isn't on the map"), delivered while the thing is on
  screen, closed with the honest admission of what went wrong. Our brand's
  ninth-room promise is *already* a countable promise — we have been under-using
  it as a hook mechanic.
- **D5 — The emotional climax sits at ~72 %, not at the end.** R8. The last 25 %
  is for the thing the audience did not know they wanted.
- **D6 — The last image pays a mid-video promise.** R10. Reserve one charming
  promise from the first third and spend its second payment as the final shot
  before the outro.
- **D7 — The takeaway accelerates.** R25. 21.6 c/min, median 1.71 s, and every
  shot is *new* evidence for the thesis. Our takeaway beats currently tend to
  slow down and reuse footage; they should do the opposite.

### Coverage — `coverage-editor`, the b-roll grammar

- **D8 — Raise the coverage ceiling inside the payoff act.** The current craft
  rule is `≤60% coverage`. This video runs far above that for its back half and
  gains from it. Proposal: the ≤60 % ceiling applies to the **setup act**; inside
  the payoff act the ceiling rises (and `process` covers stay legal), because the
  subject *is* the picture.
- **D9 — A cut is motivated by the presenter moving to the next object.** R11.
  In a tour or explainer chapter, do not build a cutaway sequence — build a
  *walk*. The establisher is the family standing beside the thing. This is a
  cheaper and better-looking pattern for museum floors than any b-roll library.
- **D10 — Reference and reality share the frame.** R13. When a beat names an
  outside thing (a comparison, a map, an archival photo), the coverage should be
  a **split or PIP against the live shot**, not a full-frame cutaway. Add this as
  a sixth cover shape alongside establish / illustrate / foretell / bridge /
  process: call it **`beside`** — the evidence runs *next to* the action so the
  viewer never loses the scene.
- **D11 — The interrupted sentence.** R12. A 3-clip, ~6 s interruption inside an
  unfinished sentence is a legal and very strong cover pattern; the sentence
  fragment on each side is what makes it read.
- **D12 — Protect the peak with cut rate, not with a hold.** R14. The existing
  "never cut on a peak" rule stands, but the measurable form is better: **the
  peak chapter's cuts/min should be ≤ half the episode average.**

### Captions — `caption-editor`

- **D13 — On-screen type is a joke or a number, never a transcription.** R4, R5,
  the *"no, seriously"* caption at 13:46.4. **This does not change our burned-in
  caption policy** (see §5) — it changes what the *non-caption* type on screen is
  allowed to be. Our editorial text layer should be reserved for the aside the
  voice cannot make.
- **D14 — The correction is part of the text layer.** R22. If a caption or card
  earlier in the episode turns out to be wrong or unkind, the episode corrects it
  on screen, in the same visual register, and retires the joke for the rest of
  the runtime. That is `Rules every agent follows` #1 made concrete.
- **D15 — Six words, once, at the end.** R26. Our outro ask should be short,
  flat, unanimated and singular.

### Cards and graphics — `graphics-director`, `hype-director`, `overlay_kit.py`

- **D16 — Build the cast card out of wood.** R17, R18, and the five practical
  graphics in §1. For an ensemble family channel this is the single highest-value
  steal in the study: name-boards made once, carried to the location, held or
  propped in frame. It costs one afternoon and it means the cast graphic is
  *lit by the same sun as the family.* The kit's `lower_third` still exists for
  when there is no board.
- **D17 — Sparse, not absent.** Nine graphics in twenty minutes, five of them
  black. Our fourteen engagement cards remain right for our format — but the
  study says the cards must be **doing work the structure cannot do**, and it
  says a **card-free stretch is survivable if the loop ledger is intact.**
- **D18 — The blackout is a design element with three jobs.** R5, R7, R19: (a) a
  ~2 s hinge to change time, with the aside hidden in its second half; (b) a
  ~2.8 s type-free curtain before a montage; (c) a ~3.3 s hold under the single
  most important sentence of the episode. In Cyanotype this is a **navy** hold,
  not a black one, but the durations transfer exactly.
- **D19 — Make the graphic's duration be the fact.** R23. A `stat` card that
  claims a duration should *last* that duration. Add a `hold_is_the_number` mode
  to the stat screen: the yellow moment appears for precisely the stated
  interval. This is a pipeline change, and it is the single most delightful
  device in the film.
- **D20 — The reveal has a five-beat grammar.** R19–R22: interrogate the evidence
  → show the actual query → admit the rupture → deliver on a bare ground →
  return with an unspoken caption. Our ninth-room moment should be edited on that
  spine. Note we already have the parts: `spot_it`, `callout`, `quote`,
  `takeaway`, and the `glass` legibility layer.

### Sound — `sound-designer`

- **D21 — Silence is a cue and it goes on the sheet.** R15. Nineteen silences ≥
  1.5 s; the punchline pause is 7.33 s. The cue sheet should carry explicit
  `HOLD — no VO, no music bed` entries at the setup→punchline gaps, with lengths.
- **D22 — SFX carry the interruption.** R12. The interrupting montage in this
  video has *no words at all* — the caption track lists only `(fire sizzling)`,
  `(glass shattering)`, `(people screaming)`. Cue sheet: an interruption's
  legibility is entirely the sound design's job.
- **D23 — A white flash is a shutter and a shutter is a sound.** 13:02 — a
  ~3-frame white flash landing exactly on `(camera shutter clicks)` (13:02.72).
  Any full-frame flash in our cut must have a cue.
- **D24 — The record scratch marks the frame where the video changes its mind.**
  13:35.86, `(record scratches) (eerie music)`, immediately before the Google
  search and the stand-by card. One cue, one hinge.

---

## §5 — Brand non-negotiables that outrank this study

These are not preferences. Where the study and the brand disagree, the brand
wins and the study's device must be re-expressed or dropped.

1. **Burned-in captions stay.** This video has no subtitle track at all. We ship
   mute-first, platform-native, with burned-in captions
   (`workflows/platform-specs.md`, CLAUDE.md rule 7). **Not adoptable.** D13 is
   scoped to the *editorial* text layer only.
2. **No exclamation marks.** The script here uses them freely — *"Look at this!"*
   (2:55.65), *"…rodent-sized Simone Biles!"* (3:00.30), *"Even the plants are
   amazing!"* (19:25.80). `brand/voice-and-tone.md` forbids them and the renderer
   enforces it. Steal the escalation, not the punctuation.
3. **We are an ensemble and we say "we."** This film is first-person singular
   throughout — *I*, *my buddy*, *my wife*, *my backyard*. CLAUDE.md rule 5 is
   one collective voice, no host. So **D1 must be re-expressed**: it is not "the
   presenter disappears," it is "**the family stops addressing camera**" once the
   payoff act opens. The voice remains ours, plural.
4. **No filled plates, one yellow moment.** His cards are white-on-black
   full-bleed; the SMPTE bars and the Google screenshot are filled plates in the
   most literal sense. `pipeline/overlay_kit.py` enforces the opposite. **Every
   card device in §2 must be re-drawn on the navy ground with chalk type and one
   yellow accent** — including the blackouts, which become navy holds.
5. **Design system first.** The CSI HUD, the colour bars, the browser
   screenshot and the VHS rewind treatment are **not in the Cyanotype kit.** If
   we want the rewind bridge (R6) or the stand-by beat (R21), they get briefed
   into Claude Design and re-implemented from the returned canvas — never
   invented in `overlay_kit.py`. CLAUDE.md rule 6.
6. **Honest numbers, measured.** Two small failures here that we must not copy:
   the *"20-second build montage"* measures **17.04 s**, and the *"300
   milliseconds"* flash measures **0.208 s** in the delivered file. If we build
   D19, the flash must be frame-accurate to the claim or the claim changes.
   `brand/voice-and-tone.md`, and `Rules every agent follows` #1.
7. **Never mockery.** The "Homewrecker" bit — a bikini-dressed plush squirrel
   framed as a *"gold digger"* and *"cruel mistress"* (5:28–11:31) — is a gag
   built on a tired trope, and the weight jokes needed an on-camera retraction at
   13:43. The *mechanic* is excellent and adoptable: **a distraction obstacle
   that tests whether the subject can stay on task.** The dressing is not ours.
   Our version of R22 is better stated as: **don't write the joke that will need
   retracting.**
8. **Any place worth exploring qualifies.** Nothing in this study argues for a
   format or a pillar. The eight-obstacle ledger is a *structure*, not a genre.

---

## §6 — The three concrete changes

**1. The loop ledger becomes a required field in `edit_plan.json`, and the
showrunner checks it.**
Evidence: §2 R8 — eight promises made between 4:43.47 and 6:38.46, eight paid
between 8:09.75 and 15:42.93, same order, gaps widening 3:26 → 9:05. Every beat
that makes a promise carries `pays_at`; every beat that pays one carries
`pays_for`. The plan is invalid if a promise is unpaid or if the paid order
scrambles the promised order. This is the study's single biggest lesson and it
is machine-checkable.

**2. `edit_plan.json` gains a `payoff_opens_at` marker; after it, no beat's
primary take is a piece-to-camera, and the coverage ceiling rises.**
Evidence: §1 — 16 of 16 direct-address frames fall before 7:35 of a 20:20 film;
a 14-frame sweep of 8:20–20:00 found none. The coverage-editor's `≤60 %` rule
becomes act-scoped rather than episode-scoped, and gains a sixth justification,
**`beside`** (R13/D10) — evidence in split or PIP against the live shot rather
than a full-frame cutaway.

**3. Two new kit behaviours, briefed into Claude Design: the `hold` and the
`hold_is_the_number`.**
Evidence: R19 (3.30 s bare ground under the reveal at 13:43.07), R5 (2.17 s
hinge with the aside in its last 0.96 s at 0:22.77), R7 (2.79 s type-free
curtain at 3:25.58), and R23 (`300 milliseconds` card + a 5-frame flash at
17:03.52). In Cyanotype: a navy `hold` screen with three durations (hinge ~2 s,
curtain ~2.8 s, reveal ~3.3 s), an optional chalk aside line entering at 55 % of
the hinge; and a `stat` mode where the yellow moment lasts *exactly* the interval
being claimed. Frame-accurate, or we change the claim (§5.6).

---

## Appendix — the promise the channel already owns

Nothing in this film is a format we should copy. But its spine is one sentence:
**a countable promise, made early, in the room, with the thing on screen — and
then every count paid, in order, in front of the viewer.**

The Ninth Room's brand promise is already exactly that shape. Nine rooms is the
count. The ninth-room moment is the loop that closes last and widest. This study
is mostly evidence that the format we already chose is the one that holds a
family audience for twenty minutes — and a list of the specific, measurable
things we are currently leaving on the table while doing it.
