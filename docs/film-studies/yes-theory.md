# Film study — Yes Theory, "ABANDONED city in America with NO LAWS"

> **Rules only.** Every line below is something a story-designer, coverage-editor,
> graphics-director, caption-editor or sound-designer could execute tomorrow, with
> the timestamp that proves it. Nothing here is a vibe. Where a rule collides with
> a Ninth Room non-negotiable, the non-negotiable wins — see §5.

---

## The card

- **Video:** *ABANDONED city in America with NO LAWS | Yes Theory*
- **Source:** https://www.youtube.com/watch?v=kUTYSyd3LR0 (uploaded 2017-06-08)
- **Runtime:** 10:18 (618.28 s) · 28.8 M views · 358 K likes · 23 K comments
- **Why this one:** it is the channel's most-viewed video (confirmed on the
  channel itself and in a Nathaniel Drew *No Backup Plan* interview chapter
  titled "The Most Viewed Video Is the Slab City Video"), it sits inside the
  8–20 min window, and — unlike the modern 30–45 min single-narrator era — it is
  the **four-person ensemble** format the brief asked for. It is also the closest
  genre match on the shelf to us: a small group drives to a strange real place,
  meets the people who live there, and finds something that was not on the map.
- **Studied:** 2026-08-24 — six passes: 100 scene-aware frames full-range; a
  30-frame 1 fps hook pass (0:00–0:30); a 28-frame targeted overlay census; a
  17-frame sub-second sweep of the cast cards and the location pin; a 12-frame
  pin of the two name cards and the joke cutaway; and 5 frames probing whether
  local speech is subtitled. Plus per-frame luminance **and saturation** scans of
  the whole runtime.
- **Transcript:** YouTube's **manual** English caption track (161 cues; the
  `subtitles` list in the info JSON confirms `en` is human-authored, not ASR).
  It even carries the profanity mask as `****`. Quotes below are exact.

### Measurement notes and honest caveats

- **Cut detection:** ffmpeg scene detection at **0.30 (194 cuts)**, **0.20 (271)**
  and **0.15 (384)**, matching the five earlier studies so the numbers compare.
  Unless stated, figures are the 0.30 pass. Scene detection under-counts
  same-angle cuts — this film is full of them inside the Wizard interview — and
  over-counts the handheld whip-pans in the car.
- **The download is 480p** (YouTube's higher formats 403'd this session). All
  on-screen type in this film is large and centred, so nothing below rests on
  type I could not read.
- **The file has exactly one keyframe.** Every frame grab was verified against an
  independent measurement before its timestamp was written: the black cards
  against `blackdetect`, the location pin against the scene-cut list, the B&W
  runs against the saturation scan. Where a grab could not be corroborated it is
  marked approximate (there is one — the Leonard Knight card, R4).
- **The saturation scan produces false B&W positives.** The bleached salt-sand at
  the Salton Sea (1:21–1:29, 1:37) reads SATAVG < 6 without being desaturated.
  Only two genuine monochrome treatments are claimed below, both corroborated by
  frame: the archival stills at 4:18 and the flashback stinger at 6:20.
- **Genre distance is real but small.** Four adults, one car, one day, consumer
  cameras, 2017. That is nearly our shooting condition — which is why this study
  yields more directly copyable rules than Rober or Harris did. What does *not*
  translate: this video has a bleeped expletive (5:38, 5:43), a drug-adjacent
  community, and doll-part sculptures shot as bare torsos (4:12). We are
  family-rated. §5 says exactly which parts die at the border.

---

## §1 — The numbers

### Whole video

| Measure | Threshold 0.30 | Threshold 0.20 | Threshold 0.15 |
|---|---|---|---|
| Cuts | 194 | 271 | 384 |
| Shots | 195 | 272 | 385 |
| **Median shot** | **2.08 s** | 1.56 s | 1.00 s |
| Mean shot | 3.17 s | 2.27 s | 1.61 s |
| **Cuts / min** | **18.8** | 26.3 | 37.3 |
| p25 / p75 | 1.28 s / 3.84 s | — | — |
| p10 / p90 | 0.84 s / 7.16 s | — | — |
| Longest shot | 19.24 s | 19.24 s | 17.12 s |
| Shortest shot | 0.04 s (1 frame) | 0.04 s | 0.04 s |

**18.8 cuts/min at 0.30 puts this film within 2% of Mark Rober's 18.5** — a
four-person handheld travel vlog and a studio-budget family science film land on
the same cut rate. The rate is not the differentiator. What it does *with* the
rate is (R6, R7).

### Shot-length distribution (0.30)

| Bucket | Shots | Share |
|---|---|---|
| < 1 s | 24 | 12.3% |
| 1–2 s | 68 | 34.9% |
| 2–3 s | 37 | 19.0% |
| 3–5 s | 35 | 17.9% |
| 5–8 s | 16 | 8.2% |
| 8–15 s | 11 | 5.6% |
| **> 15 s** | **4** | **2.1%** |

### Chapters (YouTube's own, from the info JSON)

| Chapter | Span | Length | Cues | Words | Words/min | Cuts | Cuts/min | Mean shot |
|---|---|---|---|---|---|---|---|---|
| Intro | 0:00–0:28 | 28.0 s | 6 | 92 | 197.1 | 17 | **36.4** | 1.65 s |
| Salton Sea | 0:28–2:10 | 102.0 s | 25 | 250 | 147.1 | 37 | 21.8 | 2.76 s |
| Salvation Mountain | 2:10–4:10 | 120.0 s | 30 | 372 | 186.0 | 41 | 20.5 | 2.93 s |
| Slab City | 4:10–10:18 | 368.3 s | 100 | 961 | 156.6 | 99 | **16.1** | 3.72 s |

### Speech

| Measure | Value |
|---|---|
| Runtime with speech | 485.0 s (**78.4%**) |
| Runtime with no speech | 133.3 s (21.6%) |
| Gaps ≥ 2 s | 18, totalling 82.5 s (13.3%) |
| Longest gap | 11.74 s (10:06.54 → end) |
| **Scripted VO** | **119.5 s — 19.3% of runtime, 24.6% of all speech** |
| **Live / in-scene speech** | **365.5 s — 75.4% of all speech** |

### Who is on screen (100 scene-aware frames, accurate timestamps)

| Category | Frames | Share |
|---|---|---|
| No people (cover, graphic, archival object) | 49 | 49% |
| Crew only | 22 | 22% |
| **Local / stranger only** | **20** | **20%** |
| **Crew + local in the same frame** | **9** | **9%** |
| …of which, crew addressing the lens | ≤ 4 | ≤ 4% |

**Strangers get as much solo screen time as the entire four-person cast
combined** (20 vs 22). Every interview is framed as a two-shot with a crew member
visibly in frame — there is no lone-presenter framing anywhere in the film.

---

## §2 — The rules

### Hook and title

**R1 — The title card is at the END of the hook, not the top.**
`0:00.00–~0:04` a small brand plate reads *"An Experience by Yes Theory"* over a
moving-car shot — footage first, never a static logo. The actual title,
*"The Last Lawless land in America"*, is a **full-black card at 0:28.88–0:31.08
(2.16 s, corroborated by `blackdetect`)**. It lands exactly on the Intro→Salton
Sea chapter boundary (YouTube chapter "Intro" ends at 28 s). The title is the
*door out of the hook*, not the way in.

**R2 — The promise word burns in as text at the instant it is spoken.**
VO cue `0:01.96–0:09.14` ends on *"…rumored to be the last city in America with
no laws."* On screen: *"with"* appears at 0:08, *"with no laws"* completes at
0:09. Not before, not after. The graphic does not announce the promise — it
*arrives with* it.

**R3 — Every person on the trip is carded in 5.4 seconds, one card each,
~1.3 s each, typewriter type-on, no box.**
Justin Escolona type-on begins 0:16.2 and completes 0:16.8; Marissa ~0:18.0–0:19.4;
Nick ~0:19.2; the collaborating channel *Playthegamefilms* 0:19.8–0:21.2 over a
four-person rooftop hero shot. Each card sits in the **empty half of the frame,
beside the person** — bottom-left for Justin, bottom-right for Marissa,
bottom-centre for Nick, top-left for the channel. Never centred over a face.

**R4 — Strangers get the identical card. No visual hierarchy.**
*"Wizard"* appears bottom-left at ~4:52–4:55 (present at 292.0 s and 294.0 s,
absent at 290.0 s and 296.0 s — same typeface, same size, same position language
as the cast cards). *"Leonard Knight"* is carded on the archival shot in the
Salvation Mountain chapter, VO naming him at 2:17.69 (*approximate: this one card
is the single claim I could not pin to a tight in/out, so treat its timestamp as
~2:18–2:40, not measured*). The system says: on this trip, the person who lives
here is cast.

### Rhythm

**R5 — The longest holds in the film go to the stranger, not the cast.**
The four shots over 15 s, in order of length:

| Length | In | What it is |
|---|---|---|
| **19.24 s** | 4:50.72 | Wizard's opening monologue — *"I am certified insane, and really, no, I have Papers… this place is a power vortex"* |
| **17.24 s** | 9:09.76 | The crew handing over cold beer; the cheers |
| **17.12 s** | 5:56.44 | Wizard answering the video's central question — *"no, not lawless it's very courteous"* |
| **15.32 s** | 5:36.56 | Wizard's comedy monologue — the two-jobs bit |

**Three of the four longest shots in a 10-minute film are one uncut take of one
stranger.** Peak protection — now confirmed in a sixth study — but the peak
belongs to the person we met, not to us.

**R6 — Narration is cut 2.3× faster than the scene. The film changes gear, not
speed.**

| | Runtime | Cuts | Cuts/min | Mean shot |
|---|---|---|---|---|
| Scripted VO blocks | 119.5 s (19.3%) | 68 | **34.2** | 1.76 s |
| Everything else | 498.8 s (80.7%) | 126 | **15.2** | 3.96 s |

19.3% of the runtime carries **35% of all the cuts**. When someone real is
talking, the camera stops moving; when the narrator explains, it sprints.

**R7 — Cut rate decelerates chapter over chapter, and the destination is the
slowest.**
36.4 → 21.8 → 20.5 → **16.1** cuts/min. The Slab City chapter is 60% of the
runtime and the calmest thing in the film. The film opens at a sprint to buy the
right to slow down.

**R8 — Scripted VO is the minority voice.** 119.5 s of narration against 365.5 s
of live, in-scene speech — **24.6% / 75.4%**. The explaining is a service to the
scene, not the spine of it.

### On-screen text

**R9 — Narration text is one phrase at a time, alternating a black card with the
footage that proves it.**
The Salton Sea death sequence, 1:11–1:19, is the whole grammar in eight seconds:

| Time | Screen |
|---|---|
| 1:11.20–1:11.92 (0.72 s) | *"Survived"* — full black |
| 1:13 | *"the water turned toxic"* — over toxic mud |
| 1:14.5 | *"left"* — beside a real sign with a left arrow |
| 1:15.44–1:17.12 (1.68 s) | *"and the millions of fish…"* — full black |
| 1:17 | *"dead"* — over the shore of dead fish |

Six near-black text cards in the film, **7.24 s total — 1.2% of runtime**. Black
is the pause between phrases, not a background.

**R10 — One emphasis term per card, coloured; every other word stays white.**
*"the water turned **toxic**"* — `toxic` in red, 1:13. *"But after the war ended,
it was **taken down**"* — `taken down` in yellow, 4:20.5. Never two coloured terms
in one frame. **This is our one-yellow-moment rule, arrived at independently.**

**R11 — The word lands on the image that proves it.** `dead` (1:17) sits on the
dead-fish shore. `left` (1:14.5) sits beside a left-arrow sign. *"no running
water or electricity"* (4:33) sits over the wide of the camp. The graphic never
asks you to take its word for it.

**R12 — Archival is signed, not smuggled, and then located.**
A period *"Greetings from Salton Sea"* postcard at 1:04. Two B&W US Marine Corps
stills at **4:18.04–4:22.72 (4.68 s, corroborated by the saturation scan)**, both
wearing a film-frame vignette so they read as *not us*. Immediately after, at
4:22.5, a **satellite map with a red arrow and the label "Slab City"** puts the
place on Earth. Sign it, then locate it.

**R13 — The location pin lives exactly one shot and never survives a cut.**
📍 *Salton Sea*, top-left, in on the cut at **0:40.64**, out on the cut at
**0:44.28** — 3.64 s, one shot, to the frame.

**R14 — A distance card keeps the loop alive mid-journey.**
*"20 minutes from Slab City"* at 1:41, over a passing freight train. The viewer is
102 seconds into a detour; the card is the reassurance that the promise is still
running.

**R15 — Only the money quote gets burned in.**
*"I am certified insane"* is subtitled on screen at ~4:56. Checked at 5:00, 5:21
and 5:56 — **no subtitles on ordinary local speech.** It is a punchline burn-in,
not a captioning system. The same line is spoken three times (4:50.80, 4:59.04,
6:19.98): the burn-in marks a running gag, and the repeats are left bare.

### Structure and comedy

**R16 — The joke cutaway lands ~6 s after its setup line, on the action, and runs
~2 s.**
Setup at 7:01.27: *"Dude, there's a putter! I'll be Tiger Woods back in High
school."* The ball is rolling at 7:06, the archival Tiger Woods clip is on screen
at 7:07.5, and we are back in the yard by 7:09. The joke is not illustrated when
it is *said* — it is illustrated when it **works**.

**R17 — A time-jump is a 2.2 s desaturated stinger with the offset written on it.**
*"2 minutes earlier"* over B&W, **6:20.60–6:22.80** (saturation scan; colour
returns immediately at 6:22.80). Two seconds of monochrome buys a
non-chronological cut without confusing anyone.

**R18 — Bookend the film with the same words, inverted.**
Open: *"An Experience by Yes Theory"* — white type over moving footage, 0:00.
Close: *"A Film by Yes Theory"* — **black type on white**, 10:04. Same signature,
flipped, 10 minutes apart.

**R19 — The payoff is an act, not a line.**
The film's promise is *"the last city in America with no laws."* The answer is
delivered by the Wizard at 5:56 (*"not lawless — very courteous"*), and then
**proved by the crew's own behaviour**: at 9:01 they explain they bought cold beer
on the way because refrigeration is hard here, and the **longest shot of the
entire back half (17.24 s at 9:09.76)** is them giving it away. The closing VO at
9:48 states what the act already showed: *"people that live there are pretty much
surrounded and immersed in love."*

**R20 — The detour is promised before it is taken.**
At 0:23.76 — five seconds before the title card — the VO says *"But before we
explored slab city there was a fascinating place, we simply couldn't avoid."*
102 seconds of Salton Sea and 120 seconds of Salvation Mountain follow. The
audience never wonders why they are not at the destination yet, because the
detour was **licensed inside the hook**.

---

## §3 — Hook anatomy, second by second

24 cuts in the first 60 s (24.0/min); 17 of them in the first 28 s (36.4/min).
First cut at **2.32 s**.

| Time | Picture | Text | Sound/VO |
|---|---|---|---|
| 0:00.00 | moving-car b-roll | *An Experience by Yes Theory* | — |
| 0:01.96 | " | " | VO in: *"We've only heard stories about the city we're heading to…"* |
| 0:02.32 | **first cut** | | |
| 0:03.80 / 0:04.40 | 1.48 s then **0.60 s** shots | plate fades | |
| 0:08 → 0:09 | freeway, mountains | *with* → **with no laws** | VO lands *"…with no laws"* |
| 0:10.12 | windmills | — | *"So I'm going to try to give you my take…"* |
| 0:12 | **aerial of the destination** | *Desert of* | first sight of Slab City |
| 0:14.64–0:15.60 | **full black (0.96 s)** | *really is* | |
| 0:16.2–0:17.2 | Justin + Marissa | *Justin Escolona* (type-on) | *"And our friends Justin Escolona…"* |
| 0:17.9–0:19.4 | Marissa | *Marissa* | |
| ~0:19.2 | Nick | *Nick* | *"…and his best friend Nick"* |
| 0:19.8–0:21.2 | four-shot, LA rooftop, night | *Playthegamefilms* | *"…were too curious not to tag along"* |
| 0:17.32–0:18.32 | **three cuts in 1.00 s** (0.64 / 0.20 / 0.16 s) | | the fastest burst in the film |
| 0:23.76 | walking three-shot | — | **the detour promise** (R20) |
| **0:28.88–0:31.08** | **full black (2.16 s)** | **The Last Lawless land in America** | title |

Read the shape: **promise (0:02) → promise word on screen (0:09) → destination
glimpsed (0:12) → cast (0:16–0:21) → detour licensed (0:24) → title (0:29).**
Six moves in 31 seconds, and the destination is *shown* 12 seconds in but not
*arrived at* for another 3 minutes 58.

---

## §4 — Ensemble mechanics (the brief)

Four measured facts, no vibes:

1. **No lone-presenter framing exists in the film.** All 9 interview frames in
   the 100-frame sample are crew + local two-shots (3:14, 5:22, 6:14, 6:23, 6:40,
   6:51, 6:54, 8:39, 9:31). The listener is always in shot.
2. **Direct-to-lens address is ≤ 4% of sampled frames** and is confined to two
   functions: setting up the arrival (4:07, in the car) and signing off (9:47, in
   the car), plus a walking piece-to-camera at 9:02 explaining the beer.
   Everything else is people talking to *each other*.
3. **Strangers out-hold the cast.** 20 solo-local frames vs 22 solo-crew frames,
   and three of the four longest shots are one local talking (R5).
4. **The identity system is flat** (R3/R4): the same card, the same face, the
   same 1.3 s, for a founder and for a man who empties buckets in the desert.

The ensemble reads as an ensemble because **no one is positioned as the answer**.
The crew asks; the place answers. The 17.12 s shot at 5:56 is the video's thesis
statement and a crew member is not speaking during it.

---

## §5 — Where this collides with our non-negotiables

**The brand wins. These do not cross the border:**

| Observed | Why it dies here |
|---|---|
| Red emphasis (`toxic`, 1:13) | Our palette is Cyanotype: navy ground, chalk type, **one yellow moment**, cyan structural. Red is not in it. Take R10's *structure* (one term, coloured, rest chalk) — `emphasize()` already enforces exactly this. Never the hue. |
| Distressed typewriter face | Ours is Bricolage + Newsreader, from `brand/fonts/`. Same geometry, our type. |
| Full-black narration cards | Closest legal equivalent is the kit's own screens over a **gradient scrim** — and note their cards carry **no box** either, which is already our one visual rule. Black-out is a transition, and we have `transition` in the kit; do not invent a new full-bleed black plate. |
| Bleeped expletive (5:38, 5:43) | Family-rated, no exceptions. If a subject swears, the take does not ship — we do not bleep our way into a laugh. |
| Doll-torso sculptures shot bare (4:12) | Family-rated. Same place, different framing. |
| *"hit that subscribe button"* (10:05) | `brand/voice-and-tone.md` — we do not beg, and we do not use exclamation marks. The kit's `outro` beats already carry our version. |
| *"the last city in America with no laws"* as a settled claim | Rule 1: accuracy is the brand. Note that this film **does the right thing** — it opens with *"it's **rumored** to be"* (0:01.96) and then lets a resident **contradict the title** at 5:56 (*"no, not lawless"*). Frame the unconfirmed as claimed, then let the place correct you on camera. That part we keep, gladly. |

**And one thing we should notice we already do better:** their engagement layer is
nearly absent — one distance card (R14) in 10 minutes. Our thirteen engagement
cards and the 60–90 s job cadence in `brand/engagement-playbook.md` are a real
advantage over this reference, not a deficit to correct against it.

---

## §6 — For our doctrines

Each rule mapped to the craft it feeds and the artefact it changes.

### Story — `story-designer`, `edit_plan.json`

| Rule | What it becomes |
|---|---|
| **R1** | Put the episode title beat at the **end** of the cold open, on the first chapter boundary — not at 0:00. Budget it ~2 s. |
| **R20** | If the episode detours before the promised room, **license the detour inside the hook**. A beat that says "but first" before the title costs 4 s and buys 3 minutes. |
| **R7** | Plan the cut rate to **decelerate** across chapters. The ninth room should be the calmest chapter, not the fastest. Target a ~2.2× spread from open to destination (36.4 → 16.1). |
| **R6** | Any beat anchored to a VO take gets a **different rhythm target** from a beat anchored to a face: ~1.8 s mean shot for VO, ~4.0 s for scene. This is a per-beat property, not one global pace. |
| **R8** | Cap scripted narration at roughly **a quarter of total speech**. If the plan's VO takes exceed that, the episode is being explained instead of shown. |
| **R5** | The peak beats — where `coverage_notes` already forbids covers — should be **the family's or a stranger's uncut reaction**, and they should be the longest shots in the episode. Confirms peak protection a sixth time. |
| **R19** | The payoff beat should be **an act on camera**, with the takeaway line placed *after* it. Our ninth-room moment lands better as something done than something narrated. |

### Coverage — `coverage-editor`, R1, `schemas.COVER_WHYS`

| Rule | What it becomes |
|---|---|
| **R11** | Sharpens **`illustrate`**: the cover must contain the *evidence* for the word, not a mood equivalent. `dead` over dead fish, `left` over a left-arrow sign. A `why` reading `illustrate — the desert` where the line said "dead" fails. |
| **R13** | New coverage discipline: **a location graphic is scoped to one shot.** It enters on a cut and leaves on the next cut. Nothing brand-side currently says this; it should. |
| **R12** | Archival/asset covers must be **visually signed** (vignette, border, period grade) so a viewer never mistakes borrowed footage for ours — then followed by a locating shot. Feeds `asset-sourcer` too. |
| **R16** | The comedy cutaway is placed on **the action that proves the joke, ~6 s after the setup line** — not on the line. Currently our `illustrate` window is "within about a second of the word", which would place this cutaway wrong. Worth an explicit exception. |
| **R6** | The 60% coverage ceiling is right for scene beats and **too tight for VO beats** — this film runs its VO blocks at 34.2 cuts/min, which is almost all cover. Our existing `vo_*` exemption is doing the correct thing; this is corroboration. |

### Captions — `caption-editor`, `captions.json`

| Rule | What it becomes |
|---|---|
| **R15** | Direct support for the ~30% punchline budget, from a different direction: this film captions **one line in ten minutes**. Our budget is generous by comparison. When in doubt, cut a caption. |
| **R15** | New selection criterion worth adding: **a line that will repeat** (a running gag's first utterance) earns the caption; the repeats do not. |
| **R2** | Caption timing on the hook's promise line should land **on the word, not before it**. A promise caption that pre-empts the VO spoils its own reveal. |
| **R9** | For narration, break the caption into **one phrase per screen** rather than a full sentence. The pause is the punctuation. |

### Cards — `graphics-director`, `hype-director`, `graphics_plan.json`, `overlay_kit.py`

| Rule | What it becomes |
|---|---|
| **R3 / R4** | The kit has `lower_third` (aliased from `section`). This film argues for using it as a **cast card at ~1.3 s, positioned in the empty half of frame beside the person** — and for spending it on the **people we meet on the day**, on identical terms to Caleb, Alma and Sofia. That is the channel's ensemble promise expressed as a graphic. |
| **R10** | **Already built and already correct.** `emphasize()` marks only the first emphasis term, and no kit container carries a background. Two independent creators converged on the same rule; stop treating it as a house preference and treat it as craft. |
| **R14** | A `countdown`- or `chapter`-shaped **distance/time-to-destination** card during a travel stretch. The door meter already encodes structure; this encodes *remaining journey*, which is a different loop. |
| **R12** | The satellite-map-with-arrow at 4:22.5 is a `callout` we do not currently generate. Worth a brief into Claude Design — locate-the-place is a recurring need for an exploration channel. |
| **R17** | A **2.2 s desaturated stinger with the offset written on it** is the cheapest legal time-jump we could ship, and `transition` is the component it belongs in. |
| **R18** | Bookend `hook`'s brand plate with an inverted `outro` plate. Same words, flipped ground. |
| **R1** | `hook_title` should be authored to land at the chapter boundary, ~2 s, over the transition — not as the opening frame. |

### Sound — `sound-designer`, `brand/sfx/`

| Rule | What it becomes |
|---|---|
| **R9** | Every black card is a **cue point**. Six of them in this film, 0.72–2.16 s. The pause between phrases wants a mark — that is exactly what our stamp/whoosh library is for. |
| **R6** | The gear change between VO (34.2 cuts/min) and scene (15.2) is carried by **music, not just picture**. The cue sheet should mark the VO blocks as their own music state and hand the scene back to nat sound. |
| **R8** | 21.6% of runtime has no speech; 18 gaps ≥ 2 s. Those are nat-sound holds, and they are where the place gets to sound like itself. Cue them as *deliberate*, not as gaps to fill. |
| **R16** | The joke cutaway wants an accent on the **action**, not the setup line — same 6 s offset. |

---

## §7 — The three changes to make first

1. **Move the title card to the end of the cold open, and license any detour
   inside the hook.** (R1, R20 — evidence 0:23.76 and 0:28.88–0:31.08.) The
   story-designer currently has no rule about *where* the title beat sits. This
   costs one line in the brief and restructures every cold open we ship.

2. **Give the people we meet the same name card as the family, and give them the
   episode's longest uncut shot.** (R3/R4/R5 — evidence *Wizard* at 4:52–4:55 and
   the 19.24 s hold at 4:50.72, 17.12 s at 5:56.44, 15.32 s at 5:36.56.) The
   graphics-director should treat a `lower_third` on a stranger as *required*
   when we interview one, and the story-designer should mark that stranger's best
   answer as a `peak` beat. This is the single most transferable thing in the
   film and it is what makes an ensemble read as an ensemble.

3. **Split the pace target in two: VO beats ~1.8 s mean shot, scene beats ~4.0 s.**
   (R6 — evidence 68 cuts / 119.5 s vs 126 cuts / 498.8 s.) We currently reason
   about one median shot length for a whole episode. This film shows the number is
   meaningless as a single value: 19.3% of its runtime carries 35% of its cuts,
   and that asymmetry *is* the craft. The coverage-editor already exempts `vo_*`
   beats from the ratio rule — this extends the same idea to rhythm.

**File:** `docs/film-studies/yes-theory.md`
