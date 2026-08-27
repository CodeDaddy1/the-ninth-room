# Film study — Kara and Nate, "24 HOURS AT THE WORLD'S LARGEST GAS STATION (Buc-ee's)"

> **Rules only.** Every line below is something a story-designer, coverage-editor,
> graphics-director, caption-editor or sound-designer could execute tomorrow, with
> the timestamp that proves it. Nothing here is a vibe. Where a rule collides with
> a Ninth Room non-negotiable, the non-negotiable wins — see §3.

---

## The card

- **Video:** *24 HOURS AT THE WORLD'S LARGEST GAS STATION (Buc-ee's)* | Kara and Nate
- **Source:** https://www.youtube.com/watch?v=80oyG1Vl1Vc (uploaded 2021-03-14)
- **Runtime:** 18:50 (1129.72 s) · 7.84 M views · 105 K likes · 8.2 K comments
- **Shot:** 2021-03-03, New Braunfels, Texas. The description numbers it **vlog 758**.
- **Why this one:** the brief asked for travel-vlog structure and day-arc pacing.
  This is the channel's highest-viewed video that is *both* inside the 8–20 min
  window *and* an actual day arc — the title is the arc. It is also the closest
  genre match on the shelf to us: a small family unit drives to one strange real
  place in America, spends a day in it, and finds the thing that wasn't on the
  map. Its notability is independent of view count — it was picked up by Nerdist,
  Digg and Yahoo as a story in its own right. The channel's four higher-viewed
  videos are all vehicle/hotel tours (no day arc) or over 20 minutes.
- **Studied:** 2026-08-24 — six passes: 100 scene-aware frames full-range at
  768 px; a 26-frame targeted overlay census; a 16-frame counter-and-clock sweep;
  a 19-frame closing sweep; a 12-frame 2 fps hook pass (0:00–0:20); and two
  2-second contact sheets (4:28–6:18, 8:00–9:16) to finish the graphics census.
  Plus per-second luminance, audio `silencedetect`, and word-level caption timing
  across the whole runtime.
- **Transcript:** YouTube **auto-captions only** (`en-orig` + `en`; the info JSON
  shows an empty `subtitles` list, so there is no human-authored track). Word-level
  timings are reliable; proper nouns are not — the ASR renders "Buc-ee's" as
  "bucky's"/"buckies"/"monkeys"/"buffy's" and "Kara and Nate" as "karen nate".
  **Per the agent's own rule, visual analysis is weighted higher than caption text
  here, and quoted lines below are only ever used for structure and timing, never
  as evidence about wording.**

### Measurement notes and honest caveats

- **Cut detection:** ffmpeg scene detection at **0.30 (407 cuts)**, **0.20 (477)**
  and **0.15 (528)**, matching the six earlier studies so the numbers compare.
  Unless stated, figures are the 0.30 pass. Scene detection over-counts the
  handheld whip-pans through the store aisles and under-counts the same-angle
  cuts at the van dinette, which is a locked-off two-shot (R9).
- **The download is 1080p** (`137+140` via the `web_embedded` player client; the
  default client 403'd). All on-screen type was read at full resolution.
- **Card durations were measured, not eyeballed.** Each was timed by thresholding
  near-white pixels inside a cropped lower band at 4 fps and reading the plateau.
  Where a card sat over bright footage the signal is weak and the timing is marked
  approximate.
- **The graphics census is a verified lower bound, not an exhaustive count.**
  It rests on 173 sampled frames plus two 2-second contact sheets. Nine spec
  cards, three clock cards and four pull-quotes are confirmed by frame; there are
  very likely a few more in the un-sheeted stretches. Counts below say "≥".
- **One number in this film is wrong, and the film proves it itself** — see R6.
  That is the single most useful thing in the study for our accuracy doctrine.
- **Genre distance is small, which is why this study yields so much.** Two adults,
  one van, one location, one day, consumer cameras, no crew, 2021. That is very
  nearly our shooting condition. What does *not* translate: it is a two-hander,
  not an ensemble; there is no child on camera; and it is a food-consumption video,
  so its central graphic is a calorie count. §3 says exactly which parts die at
  the border.

---

## §1 — The numbers

### Whole video

| Measure | Threshold 0.30 | Threshold 0.20 | Threshold 0.15 |
|---|---|---|---|
| Cuts | 407 | 477 | 528 |
| Shots | 408 | 478 | 529 |
| **Median shot** | **1.82 s** | 1.63 s | 1.53 s |
| Mean shot | 2.77 s | 2.36 s | 2.14 s |
| **Cuts / min** | **21.6** | 25.3 | 28.0 |
| p25 / p75 | 1.14 s / 2.96 s | — | — |
| p10 / p90 | 0.76 s / 5.96 s | — | — |
| Longest shot | 29.76 s (16:16.74) | 24.12 s | 19.09 s |
| Shortest shot | 0.03 s (1 frame) | 0.03 s | 0.03 s |

**21.6 cuts/min is the fastest film on the shelf** — ahead of Yes Theory (18.8)
and Mark Rober (18.5). A two-person travel vlog with no crew out-cuts a
studio-budget science film. Cut rate is not a budget line.

### Shot-length distribution (0.30)

| Bucket | Shots | Share |
|---|---|---|
| < 1 s | 80 | 19.6% |
| 1–2 s | 139 | 34.1% |
| 2–3 s | 88 | 21.6% |
| 3–5 s | 47 | 11.5% |
| 5–8 s | 31 | 7.6% |
| 8–15 s | 19 | 4.7% |
| **> 15 s** | **4** | **1.0%** |

### The day arc, measured (YouTube's own chapters, from the info JSON)

| # | Chapter | Span | Length | Cuts | **Cuts/min** | **Median shot** | Words/min | Mean luma |
|---|---|---|---|---|---|---|---|---|
| 1 | Intro | 0:00–0:47 | 47.0 s | 31 | **39.6** | **1.27 s** | 150.6 | 115.6 |
| 2 | What is Buc-ee's | 0:47–2:18 | 91.0 s | 47 | **31.0** | **1.33 s** | 160.9 | 119.5 |
| 3 | Live at Buc-ee's | 2:18–6:24 | 246.0 s | 102 | **24.9** | **1.50 s** | 134.9 | 113.8 |
| 4 | Bathroom Tour | 6:24–11:16 | 292.0 s | 115 | **23.6** | **1.87 s** | 149.4 | 109.5 |
| 5 | Dinner | 11:16–13:45 | 149.0 s | 41 | **16.5** | **2.40 s** | 128.9 | 89.4 |
| 6 | Breakfast | 13:45–18:50 | 304.7 s | 71 | **14.0** | **2.70 s** | 103.2 | 101.7 |

**Both columns are monotonic across all six chapters.** Cuts/min falls 39.6 → 14.0
(a **2.83×** deceleration); median shot length rises 1.27 s → 2.70 s without a
single reversal. First half 27.6 cuts/min, second half 15.7 (**1.76×**). This is
the central finding of the study and it is R1.

### Speech and silence

| Measure | Value |
|---|---|
| Timed caption words | 2,486 |
| Words / min (whole film) | 132.0 |
| Gaps ≥ 2 s between words | 79, totalling 340.6 s (**30.1%** of runtime) |
| Longest word-gap | **24.5 s** (14:28.84 → 14:53.36) |
| **Actual audio silence** (≤ −32 dB, ≥ 1.2 s) | **2 runs only** |
| — run 1 | 14:28.43 → 14:32.92 (**4.49 s**) |
| — run 2 | 18:47.09 → end (2.63 s, the outro fade) |

**30.1% of the film has no voice, and 0.6% of it has no sound.** Everything else
is music. There is exactly one engineered silence in the whole film and it lands
on the moment the premise breaks (R7). Compare Johnny Harris, who used 19 s and
13 s of true silence at Srebrenica, and Beau Miles at 20.6% voiceless: Kara and
Nate reach the same *structural* beat with a music bed instead of a hole.

### Where the long shots live

23 shots run ≥ 8 s. Their positions as a share of runtime:
11, 12, 21, 22, 23, 26, 30, 33, 46, 48, 56, 57, 60, 66, 68, 73, 76, 77, 86, 90,
95, 96, 97%. **Ten in the first half, thirteen in the second**, and the five
longest all sit after 73%. The two longest in the film — 29.76 s at 16:16.74 and
22.86 s at 13:45.89 — are both in the final third.

### Graphics census (verified lower bound)

| Kind | Count | Format | Evidence |
|---|---|---|---|
| Spec card | **≥ 9** | 3 rows, bottom-left: `NAME` / `$PRICE` / `N CALORIES` | 4:32, 4:56, 5:18, 8:40, 8:50, 13:26, 16:20, 17:45 (+1) |
| Clock card | **3** | `12:30 PM`, `3:30 PM`, `9 PM`, lower third | 4:04.75 (1.75 s), ≈8:24 (≈2.25 s), 13:46.0 (≈1.5 s) |
| Pull-quote | **≥ 4** | `"IN QUOTES"`, white all-caps, bottom | 3:03, 8:14, 8:34, 15:35 |
| Live counter | 1 | Bottom-left numeral, 1 → 64 | 2:35 → 2:51 |
| Unit-conversion card | 1 | `6,225 m²`, lower third | 1:48.00 → 1:50.25 (2.50 s) |
| Stat card | 1 | `80 DIFFERENT FOUNTAIN DRINKS!` full-width | 7:34 |
| Archival date-stamp | **3** | `PLACE, MONTH YEAR (VLOG #NNN)` | 6:34, 7:42, 17:17 |
| Source screenshot | **4** | Full-frame web page, held | 1:18.50 (2.25 s), 6:08–6:14, 6:43.25 (≈1.75 s), 11:00 |
| Real-object ledger | 4 appearances | Handwritten list on a paper bag | 6:04, 13:20, 17:49, 18:05 |
| End card | 1 | White-on-black over a dissolving live shot | 18:43 → 18:50 |
| **Title card** | **0** | — | **there isn't one** |

---

## §2 — The rules

### R1 — Decelerate monotonically across the day. Never speed back up.
The film opens at **39.6 cuts/min** and ends at **14.0**, falling at every one of
six chapter boundaries with no reversal; median shot rises 1.27 s → 2.70 s over
the same span. The viewer is *hustled* into the premise and then progressively
allowed to sit down in it. Nothing in the back half is cut at front-half speed.

**Executable form:** set a per-chapter cut-rate target that declines across the
episode, and treat any chapter that cuts faster than the one before it as a defect.
A 6-chapter episode should land roughly 40 / 31 / 25 / 24 / 17 / 14 cuts per minute.
*Evidence: the chapter table in §1; first half 27.6 vs second half 15.7.*

### R2 — The cold open is a payoff flash, and the same frame bookends it.
Frame 1 (0:00.00) is the **funniest image in the film** — Nate in a full beaver
onesie under the fuel canopy, which is footage from hour 20 (≈15:05). It holds
**3.14 s**, the longest shot in the first eleven seconds. Then a 6-shot
flash-forward montage at ~1.1 s each: drone establisher (0:03), store interior
(0:04), the two of them on the bed (0:06), beaver chips (0:08), the brisket
sandwich (0:08), fudge pulling apart (0:09) — and at 0:09 it **cuts back to the
same onesie shot** that opened the film. The bookend closes the montage.

**Executable form:** open on the single most absurd true frame from the back half,
hold it ~3 s, flash 5–7 future payoff shots at ~1 s each, then return to the
opening frame to close the loop before the setup starts.
*Evidence: cuts at 3.14, 4.50, 5.77, 7.54, 7.91, 8.51, 9.18, 11.81.*

### R3 — Promise, constraint, question — in that order, inside 10 seconds.
- **0:00.24–0:03** the promise: *24 hours living at the world's largest gas station.*
- **0:06.64–0:08** the constraint: *eating all three meals here.*
- **0:09.20–0:09.92** the question: *seeing what the hype is all about.*

Three separate jobs, three separate sentences, no overlap, done by 0:10. Then a
**6.34 s shot with no voice at all** (11.81 → 18.15, a top-down coffee cup) lets
the question sit before the channel identity block starts at 0:16.48.

**Executable form:** the hook is not one sentence, it is three — what we're doing,
what rule we're bound by, and what we don't know yet. Then shut up for six seconds.
*Evidence: word timings 0.24 / 6.64 / 9.20; the 5.0 s word-gap 9.92 → 14.92.*

### R4 — There is no title card. The title lives in the metadata.
The 6.34 s hold at 0:12 carries **no text**. Nothing in the film's first minute is
a title. Compare Yes Theory, which lands its title card at 0:28.88 on the first
chapter boundary. Kara and Nate spend that screen time on a coffee cup instead and
lose nothing — the thumbnail and the title bar already did that job.

**Executable form:** a title card is optional, and its absence buys ~6 s of held
image at the exact moment the hook needs to breathe.
*Evidence: hook frames at 0:09 and 0:12 carry no type; the graphics census finds
zero title cards in 173 sampled frames.*

### R5 — The day arc is asserted by clock cards, not by photography.
Per-chapter mean luminance never drops below 89 and only **17 seconds of the whole
film** read below YAVG 45. There is a genuine golden-hour-to-night run at
11:15–12:30 and a blue-hour return at ≈14:25, but the store is fluorescent-lit and
the night is compressed to minutes. The 24-hour claim is carried instead by **three
clock cards** — `12:30 PM` (4:04.75, 1.75 s), `3:30 PM` (≈8:24, ≈2.25 s), `9 PM`
(13:46.0, ≈1.5 s) — plus one **diegetic** clock: a cut to an Apple Watch face at
11:20, at golden hour, instead of a fourth card.

Note what they *don't* do: the clock cards **stop after 9 PM**. The morning has
none. Once the night has been shown photographically, the graphic is retired.

**Executable form:** if an episode claims a duration, state the time on screen 3–4
times in ~1.5–2.5 s cards, spaced across the first two thirds; substitute a real
clock in shot where one exists; and stop once the light is doing the job.
*Evidence: luminance scan; card timings measured at 4 fps; watch cut at 11:20.*

### R6 — Put the source on screen, hold it ~2 s, and push in on the sentence.
Four source screenshots, each landing within about a second of the claim being spoken:
- **1:18.50 (2.25 s)** — Buc-ee's own *World Records* page, on the superlative
  "the largest gas station convenience store in the entire world."
- **6:08–6:14 (~6 s, three framings)** — the *Texas Monthly* article, cut on the
  word "interview": full page → **push in on the headline** → body text.
- **6:43.25 (≈1.75 s)** — the Cintas *America's Best Restroom* award page, on
  "won an award for the bathrooms."
- **11:00** — a *Southern Living* headline with **the sentence highlighted in blue**,
  on the snack-reseller story.

**And here is the warning.** The narration says **67,000 sq ft** (1:47); the
on-screen unit card says **6,225 m²** (1:48.00–1:50.25), which is the conversion of
67,000; but the source page they themselves put on screen at 1:18 says **66,335 sq
ft**, and the Cintas page at 6:43 says **68,000**. Three different numbers, two of
them supplied by the film's own evidence. Most of the gap is explained — the Cintas
page is dated 2012 and the store was expanded — but **the film never says so**, so a
viewer who reads the screenshot catches the discrepancy. Showing your source is
only an honesty gain if the source is date-stamped and agrees with you.

**Executable form:** every surprising claim gets its source held full-frame for
~2 s with the operative sentence highlighted or pushed into — *and* the number we
say out loud must be the number on the page, with the source's date on screen.
*Evidence: card timings above; the 66,335 / 67,000 / 68,000 conflict.*

### R7 — When the premise breaks, say so on camera, in the longest uncut hold you own.
At **13:52.88** the plan fails: they cannot sleep in the Buc-ee's lot (no overnight
parking, police check it), so they move to a Walmart. At **14:16.24** they say the
quiet part out loud — *"so this technically isn't 24 hours at Buc-ee's."* The
admission is protected by three things at once:
- the **22.86 s shot** starting at 13:45.89, the second-longest in the film, sitting
  exactly on the Breakfast chapter boundary;
- the film's **only engineered silence**, 14:28.43–14:32.92 (4.49 s of true −32 dB);
- the **longest word-gap in the film**, 24.5 s (14:28.84 → 14:53.36).

The correction costs them the title of their own video and they run it anyway, at
73.7% of runtime — and the payoff still lands 21 points later.

**Executable form:** a broken premise is a beat, not a problem. Name the break in
plain words, give it the longest hold in the episode, and cut the music under it.
*Evidence: shot list; `silencedetect`; caption word-gap analysis.*

### R8 — The progress graphic is a real object, made on camera from a real source.
At **6:04–6:07** Kara hand-writes `BUC-EE'S TOP 10:` on the back of a paper fudge
bag with a Sharpie, in an overhead shot. The list is derived on camera from the
Texas Monthly source shown seconds earlier (R6). It is then **crossed off on camera**
at **13:20** and **17:49**, and **held up to the lens complete** at **18:05**. Four
appearances, one prop, total cost: a bag and a marker.

This is the third independent confirmation of the rule — Beau Miles' handwritten
crossed-off list, Mark Rober's hand-lettered wooden name-boards, and now this. A
creator with a van and a creator with a workshop and a creator with a studio budget
all reached the same answer: **the progress graphic should be a thing you can hold.**

**Executable form:** if the episode has a checklist, make it physical, make it on
camera, derive it from a shown source, and cut back to it at least three times
including once at the end.
*Evidence: frames at 6:04, 6:07, 13:20, 17:49, 18:05.*

### R9 — One locked-off two-shot is the film's home base; return to it every meal.
The van dinette is a fixed wide framing that recurs at **4:32, 4:56, 5:18, 5:38,
8:40, 8:50, 9:15, 9:57, 13:00, 17:27, 17:42, 18:18** and more. Both people are in
frame, neither is favoured, nobody is "the host." The camera does not move.
Every tasting beat comes home to it, so the fast store footage always has somewhere
to land. The peak moment — a high-five across the table at **11:36** — is shot in
this same wide, uncut.

**Executable form:** designate one fixed multi-person framing per episode, shoot
every reaction beat in it, and let it be the resting shot the fast coverage cuts back to.
*Evidence: recurring identical framing across 12+ sampled frames.*

### R10 — Every consumable gets an identical three-line spec card with two honest numbers.
≥ 9 cards, all bottom-left, all three rows, all the same grammar:

| Time | Card |
|---|---|
| 4:32 | `BRISKET SANDWICH` / `$5.99` / `790 CALORIES` |
| 4:56 | `BEAVER CHIPS` / `$1.29` / `190 CALORIES` |
| 5:18 | `HOMEMADE FUDGE` / `$3.49` / `400 CALORIES` |
| 8:40 | `BEAVER NUGGETS` / `$3.99` / `140 CALORIES` |
| 8:50 | `GARLIC JERKY` / `$6.99` / `60 CALORIES` |
| 13:26 | `BANANA PUDDING` / `$2.59` / `288 CALORIES` |
| 16:20 | `BREAKFAST TACO` / `$2.49` / `480 CALORIES` |
| 17:45 | `SAUSAGE KOLACHES` / `$2.29` / `470 CALORIES` |

The format never varies, so the viewer stops reading it as a graphic and starts
reading it as data. The numbers are checkable, unrounded (`288`, not "about 300")
and unflattering — a 790-calorie sandwich is stated as 790.

**Executable form:** pick one repeating card grammar per episode, give it exactly
two verifiable numbers, never round them, and never vary the layout.
*Evidence: the eight cards above, verified by frame.*

### R11 — Count the absurd thing live, on screen, while someone walks past it.
From **2:35 to 2:51** a large numeral runs in the bottom-left, counting ice-freezer
doors as Kara walks the length of them: **1** (2:35), **3** (2:36), **7** (2:38),
**34** (2:40), **56** (2:44), **63** (2:45–2:46), **64** (2:48–2:51). It drops out
on the intercut shots and returns on the freezer shots. Sixteen seconds, one
number, no narration needed — the joke is the arithmetic.

**Executable form:** when a location's absurdity is quantitative, don't say the
number, *run* it against a tracking shot and let it settle.
*Evidence: eleven sampled values across 2:35–2:51.*

### R12 — Date-stamp your own archive; the stamp names the vlog number.
Three cutaways to their own back catalogue, each stamped:
- **6:34** — `OCTOBER 2019 (VLOG #668)`
- **7:42** — `SUMMER 2016`
- **17:17** — `LVIV, UKRAINE, AUGUST 2019 (VLOG #657)`

The strongest form carries **place, month, year and a findable episode number**.
The viewer can go check. Note the asymmetry against R6: they date-stamp their own
footage rigorously and their *sources* not at all — which is exactly where the
number error got in.

**Executable form:** any cutaway to footage not shot for this episode carries a
stamp with place, date and the episode it came from.
*Evidence: three frames above.*

### R13 — The on-screen quote is for the joke, not the information.
Four pull-quotes, all in quotation marks, all white all-caps on the lower band:
- **3:03** `"WE DON'T HAVE ENOUGH ROOM IN THE VAN"`
- **8:14** `"WHERE FROM, WHERE TO?"` — the cashier's line, not theirs
- **8:34** `"TOO MANY BEAVER BAGS"`
- **15:35** `"BREAKFAST"` — one ironic word, over a man in a beaver onesie

None of them carry information. Every one is a punchline, an eye-roll, or a
stranger's line worth preserving. The film is **not** continuously captioned —
these four are the only quoted text, so each one reads as a deliberate aside.

**Executable form:** the quote card is a comedy instrument. Reserve it for lines
that are funny, self-deprecating, or spoken by someone we met — never for a fact.
*Evidence: four frames above; no continuous burned-in captions anywhere in 173
sampled frames.*

### R14 — Both hosts stay on the lens the whole way through.
Direct-to-lens address appears in ~16 of the 100 scene-aware frames and is spread
across the **entire** runtime — 0:00, 0:58, 1:05, 1:17, 2:35, 3:30, 5:22, 6:01,
11:31, 12:18, 13:26, 14:55, 15:53, 16:05. This is the opposite of Mark Rober
(all 16 direct-address frames before 7:35, then the presenter vanishes for 62%)
and of Yes Theory (≤4%, confined to the car).

**Executable form:** for a family day-trip format, the presenter never hands the
film over to disembodied narration. Setup and payoff are the *same* film, with the
same faces in it.
*Evidence: frame classification across the full runtime.*

### R15 — Close both loops in one sentence, at 94% of runtime, then coda.
At **17:45.92** — 94.4% in — one line closes the hook's question *and* the ledger
opened at 6:11 (32.8%): the top ten and all three meals are done, and the verdict
on the hype is given. Then ~65 s of coda: the aftermath, the oversized mug, the
couch. The film does not end on the payoff; it ends on the comedown.

**Executable form:** the sentence that closes the curiosity gap should also close
the episode's checklist, land at ~90–95% of runtime, and be followed by a soft
minute that resolves the day rather than the question.
*Evidence: the ledger at 6:11 → 18:05; payoff line at 17:45.92.*

---

## §3 — Where these rules die at our border

Brand non-negotiables outrank everything observed above.

| Observed | Our rule | Verdict |
|---|---|---|
| `80 DIFFERENT FOUNTAIN DRINKS!` (7:34); `THANKS FOR WATCHING!` (18:43) | `brand/voice-and-tone.md`: **no exclamation marks**, enforced in the renderer | **Dies.** Copy the full-width stat card; strip the punctuation. |
| Spec cards sit on translucent tinted bars — the price row is a mauve plate | **"No filled plates, and one yellow moment per frame"**, enforced in `pipeline/overlay_kit.py` (no text container carries a background) | **Dies as drawn, survives as structure.** Keep three rows, `NAME` / number / number, one emphasis term. Legibility comes from the `glass` scrim or the chalk double-shadow — never a box. |
| Selective captioning: only 4 quoted lines in 18:50 | `workflows/platform-specs.md`: **burned-in captions for mute-first viewing** | **Dies as a replacement, survives as a layer.** We caption everything. R13's quote card becomes an *extra* graphic on top of full captions, not a substitute for them. |
| 67,000 vs the 66,335 on their own source page (R6) | **Rule 1: accuracy is the brand.** A parent is fact-checking this in front of their kid | **Dies, and is the study's cautionary example.** If we show the source, our spoken number matches it and the source carries its date. |
| Two-hander with a lot of "I"; one person drives most beats | **Rule 5, rewritten 2026-08-27:** Caleb hosts and narrates; "I" is not banned anywhere | **Survives, having previously died.** One person driving most beats is now what we do — the original verdict was written under "nobody is the host". R9's locked two-shot still becomes a locked *three*-shot, because that is about who is in frame, not who narrates. R14's direct address is Caleb's. |
| Zero emoji (one `:)` in the end card) | `brand/voice-and-tone.md`: **emoji are encouraged**; the `hype-director` places them | **Inverted.** Our version of R2's flash montage and R11's counter should carry emoji reactions where they earn them. |
| The spec card as a novel graphic | **Rule 6: design system first** | **Process constraint.** The three-line spec card must be briefed into Claude Design and re-implemented from the returned canvas — not invented in `overlay_kit.py`. Nearest existing keys: `stat`, `scale`, `compare`. |
| Premise broken and admitted, title now inaccurate (R7) | **"The payoff must always land."** We open gaps honestly and close them completely | **Survives and is reinforced.** Their admission is *why* the payoff still lands. Our equivalent: if we didn't find a ninth room, we say so and let the takeaway carry it. |

---

## §4 — For our doctrines

Each rule mapped to the craft it feeds.

### Story — `story-designer`, `edit_plan.json`
- **R1** is the biggest single change available to us. Our edit plan has no
  per-chapter pace target at all; this film says it should, and that the target
  should **decline monotonically**. Concretely: add a per-beat or per-chapter
  `pace` intent to `edit_plan.json` and have the retention-editor flag any chapter
  that cuts faster than its predecessor.
- **R3** gives the hook a three-part checklist — promise / constraint / question —
  that the story-designer can be graded against, and **R4** says a title card is
  optional, which frees ~6 s of held image.
- **R2** is a cold-open recipe we can execute from existing takes: the funniest
  true frame, held ~3 s, then 5–7 one-second flashes, then the bookend.
- **R7** and **R15** together are the shape of an honest episode: name the break at
  ~74%, close both loops at ~94%, coda to the end. This is directly compatible with
  the ninth-room promise — and R7 is the strongest external evidence we have that
  admitting a miss on camera *strengthens* the payoff rather than spending it.
- **R5** matters for any episode that claims a duration. It also answers a question
  we have not had to face: how to carry a time arc when the location is
  evenly lit, which is every museum we will ever shoot.

### Coverage — `coverage-editor`, the b-roll grammar
- **R6**'s source screenshots and **R8**'s ledger are both `process` covers under
  our fifth justification — the work advancing, hands writing, a page being read.
  This film is a strong second data point for `process` being the right addition,
  and it shows the justification carrying *narrative* weight, not just filling
  wordless space.
- **R6** also sharpens `illustrate`: the Texas Monthly page cuts in on the word
  "interview," within about a second, exactly as our grammar demands.
- **R9** gives the coverage-editor its landing shot. Our rule already says the
  landing belongs to the face; this film says there should be **one designated
  framing** that is the face, fixed, and used every time. That is a shootable
  instruction for the Planner desk, not just an editing one.
- **R12** is a coverage *hygiene* rule we do not currently enforce: any cover not
  shot for this episode must be stamped with place, date and origin.

### Captions — `caption-editor`, `captions.json`
- **R13** is the useful one, and it is additive rather than corrective. Our
  burned-in captions are non-negotiable (§3), so the pull-quote becomes a second
  layer reserved for jokes, self-deprecation, and lines from people we met.
  The distinguishing marks are cheap: quotation marks, all-caps, bottom band.
- **R14** confirms our caption source rule from the other direction — because both
  hosts stay on the lens for the whole runtime, there is always a cleaned script
  line to caption from. We should keep refusing to caption raw transcript.

### Cards — `graphics-director`, `graphics_plan.json`, `overlay_kit.py`
- **R10** is the most directly stealable artifact in the study: **one repeating
  card grammar per episode, exactly two verifiable numbers, never rounded, layout
  never varied.** For us that is a museum-object card, not a calorie card — but the
  discipline is identical, and it lands on our `stat` / `scale` / `compare` keys.
  Brief it to Claude Design first (§3).
- **R11** — the live count-up against a tracking shot — is a genuinely new screen
  for us. Nothing in the 49 `RENDERERS` keys does a running numeral tied to camera
  motion. `streak` and `countdown` are the closest and neither is this.
- **R5**'s clock card is a small, obvious addition; **R12**'s date-stamp should be
  a standing requirement on archival covers rather than a card someone remembers.
- **R8** is the anti-card finding, and it is now confirmed three times across three
  budgets: when the episode has a checklist, **the checklist should be a physical
  object shot on camera**, not a rendered overlay. Our `chapter` door-meter stays —
  it encodes structure — but a per-episode list should be paper.

### Sound — `sound-designer`, the cue sheet
- **R7** is the sound rule: the film's only true silence is 4.49 s long and sits on
  the admission that the premise broke. Everything else in 18:50 has a music bed,
  including all 79 speech gaps and all 30.1% of voiceless runtime. That is a
  precise, imitable policy — **the bed never drops except once, on the beat that
  costs us something.** The cue sheet should mark exactly one such drop per episode
  and defend it.
- **R2** and **R11** are both cue-dense: a 6-shot one-second flash montage and a
  16-second count-up both want per-beat accents, and the counter's settle on 64
  wants a stop cue.
- **R15**'s coda implies a music change, not just an ending — the last ~65 s
  resolve the day after the question is already answered.

---

## The three changes worth making first

1. **Give the edit plan a declining pace target.** Add a per-chapter cut-rate
   intent that must fall monotonically, and have the retention-editor flag
   reversals. *Evidence: 39.6 → 31.0 → 24.9 → 23.6 → 16.5 → 14.0 cuts/min across
   six chapters, with median shot rising 1.27 s → 2.70 s and no reversal in either.*

2. **Adopt the repeating two-number card, and brief it to Claude Design.** One
   grammar per episode, three rows, exactly two checkable unrounded numbers, layout
   frozen — rendered with a `glass` scrim or chalk shadow, never a plate.
   *Evidence: ≥ 9 identical cards at 4:32, 4:56, 5:18, 8:40, 8:50, 13:26, 16:20,
   17:45; `288 CALORIES`, not "about 300".*

3. **Make the source rule two-sided.** We already want claims sourced; this film
   shows the failure mode — its own on-screen page says 66,335 sq ft while the
   narration says 67,000 and a second source says 68,000. So: hold the source
   ~2 s with the sentence pushed into *or* highlighted, **and** put the source's
   date on screen, **and** make the spoken number match the page.
   *Evidence: 1:18.50 (2.25 s), 1:48.00–1:50.25, 6:43.25.*

**File:** `docs/film-studies/kara-and-nate.md`
