# Film study: Hangtime — "I Tested 1-Star vs 5-Star Waterparks"

- **Source:** https://www.youtube.com/watch?v=RzQJc3pRtes (channel: Hangtime)
- **Runtime:** 25:16 (1516s), 640x360 analysed, native captions (clean)
- **Studied:** 2026-08-19, three passes — 100 scene-aware frames full-range,
  25 frames at 1024px over 0:00–1:00, plus 9 targeted cue frames (globe
  transition, subscriber cards, ambiguous overlays). Cut timestamps measured
  with ffmpeg scene detection (threshold 0.3, 329 cuts found — same method as
  study #1, so numbers are directly comparable; scene detection under-counts
  cuts between similar shots, so shot lengths are slight over-estimates).
- **Why this one matters:** same creator as study #1 ("5 Levels of
  Waterparks") in a different format — 2 chapters instead of 5, comparison
  instead of ladder, no rating system. Whatever survives the format change is
  channel grammar; whatever didn't is format-specific. That's exactly the
  test the three standing rules needed.
- **Genre distance:** unchanged from study #1 — athletic solo creator, GoPro
  thrill rides, strangers as chorus. Translate: ride = exhibit reveal, dread
  = anticipation, stranger chorus = family chorus, "world's scariest slide" =
  "the one thing everyone came to see."

## 1. The numbers

**Structure.** Two parks, worst-rated vs best-rated, with one explicit open
loop (the Tower of Power, "world's scariest water slide") promised in the
hook and deliberately saved for the final minutes:

| Section | Start | Length |
|---|---|---|
| Hook (both parks intercut) | 0:00 | 21s |
| Globe: leaving Dallas | 0:21 | 10s |
| Park 1 — Hurricane Harbor Phoenix (1-star) | 0:31 | 8:10 |
| Globe: flight arc "+5455 mi" → Siam Park | 8:41 | ~9s |
| Park 2 — Siam Park Tenerife (5-star) | 8:50 | 16:14 |
| — Tower of Power finale (loop close) | 22:46 | 2:18 |
| Outro CTA | 25:05 | 11s |

Time budget again follows epicness: the 1-star park gets 8:10, the 5-star
park 16:23 — a 1:2 split (study #1 split 3:19 vs 18:52). No ratings out of
10 anywhere; verdicts are verbal and comparative ("I don't think Hurricane
Harbor deserves as much hate as it's gotten… however, it absolutely pales in
comparison," 8:38).

**Shot lengths** (330 shots; whole-video median 3.00s, mean 4.59s, 13.1
cuts/min):

| Section | Shots | Cuts/min | Median | Mean | Max |
|---|---|---|---|---|---|
| Hook (0:00–0:21) | 11 | 31.4 | 1.70s | 1.97s | 4.2s |
| Park 1 (0:31–8:41) | 120 | 14.7 | 2.65s | 4.16s | 28.7s |
| Park 2 (8:41–25:04) | 194 | 11.8 | 3.20s | 5.03s | 23.0s |
| First 15s | 9 | 36.0 | 1.70s | 1.76s | 2.5s |

The hook cuts at ~2.4x the body rate — study #1's hook was ~2x. Same shape.

**The twelve longest shots are all peaks, zero filler:** 28.7s at 8:05
(Bahama Blaster: lifeguard's "BOTH HANDS" through the ride, uncut), 23.0s at
17:52 (Canari, "I'M BACKWARDS" through the screams), 22.2s at 1:59 (first
ride of the video, run whole), 22.2s at 14:08 (Saifa), 20.3s at 18:15 ("wait,
is there another drop?" — played out), 19.8s at 11:10 (the Dragon), 18.9s at
15:19 (Volcano + surprise light show), 18.4s at 20:16 (lazy-river drop),
17.7s at 14:30, 16.8s at 12:25, 15.4s at 9:57 (the "I'm not by myself"
friend-reveal, held through both introductions), 14.4s at 2:24. Every ride
gets one protected take; peaks here cap ~29s vs 42.7s in study #1.

**Talk/cover ratio:** of the 100 full-range frames, ~26 show someone
addressing the lens (talking head or interview), ~5 are full-screen
graphics, ~69 are action POV/b-roll under VO. **~26/74 talk-to-cover** —
study #1 measured 30/70. Stable channel trait.

**Overlay census** (floor, from ~134 sampled frames):

- 14+ quote captions — other people's or his own shouted words, chunky white,
  low-center: "c'mon we gotta get a table" (1:03), "uh it's fun" (2:45),
  "we got one!" (5:37), "it's bright as crap" (5:50), "when I send you guys
  down" (8:05 — the lifeguard), "Dan was this ride named after you?" (12:17),
  "Institut Mediterrània in El Vendrell" (12:58), "you can't breathe?! 😨"
  (13:13), "Texas!" (15:16), "why?" (17:51), "you think you're gonna beat
  me?" (22:10), "bro that was a draw!" (22:42), "where are you from?"
  (24:08). Calm VO narration is never captioned.
- 6 status/joke captions, 2–3 words + emoji: "Opening Day 🤩" (0:34, held
  across a drone pan), "SUBSCRIBERS 😎" (2:22, held ~4s over a high-five
  run), "not even joking please fix this hurrican harbor 💀" + red arrow
  (4:19), "pulling camera out of my pocket 😅" (4:47), "Racing Time 🏎️"
  (21:28), "Grown Man btw" + red arrow (0:16).
- 2 emoji-only stamps: giant 💀 hovering over the Tower of Power drop-in as a
  rider launches (0:20), floating 😔 over the friend who lost the race
  (21:40).
- 3 sightings of one recurring **globe travel card**: "Dallas — United States
  of America" (0:25), "Hurricane Harbor Phoenix" (8:41), then a drawn flight
  arc with a live "+5455 mi" mileage counter landing on "Siam Park — Spain"
  (8:47). The only chapter-transition graphic in the video.
- 2 YouTube-native subscriber cards introducing the friends: "Dantic ·
  3.05M subscribers" (10:13), "Michael Chanin · 113K subscribers" (10:15).
- Receipts, three registers: (a) **stacked** — five overlapping 1-star Google
  review cards filling the frame at 0:51 while VO says "thousands upon
  thousands of terrible reviews"; (b) **zoomed + red underline** — a single
  review phrase, "were 'out of bottled water'", underlined in red (2:38);
  (c) **artifact-as-shot** — the park's own website ride list with thrill
  levels (1:44), the pass-pricing page $65/$85/$125 (2:51), the physical park
  map filmed full-frame as the wayfinding graphic (12:06, pointed at again
  13:34), the safety sign's weight-limit icon pointed at on camera (14:06),
  and "look at this screenshot" replaying his own 360 footage as evidence
  (18:40).
- 2 red-arrow annotations beyond the caption ones (4:19 rust, 23:28 pointing
  at the tower looming behind an interviewee).
- B&W grade marking "not now," twice: flash-forward to the Tower of Power
  launch tub at 10:26 (while VO says "we'll go on that last"), flashback
  replaying an earlier interview at 23:02 (while VO says "literally every
  interview, people said this was the scariest ride").
- Park 2 entrance gets a themed animated title lettering (8:50).
- **Zero** lower thirds, zero branded motion kit, zero scoreboard — every
  overlay is someone's words, an artifact, an emoji, or the globe.

**Hook anatomy (0:00–0:21, transcribed exactly):** "I'm testing the worst
one-star water park in America versus the best five-star water park in the
entire world. I'll be testing the most thrilling rides, the most common
complaints, and the amenities at each park in order to find out just how big
of a difference is a one-star versus five-star water park experience. And as
a grown man, I was genuinely terrified to ride the world's scariest water
slide, which you'll see later in this video."
Visually: 0:00 crowd surging into Park 1 mid-motion (no logo, no greeting);
0:01 Park 1 slide splash; **0:03 cut to Park 2 exactly on "versus"** — the
comparison is made visible before it finishes being said; 0:05 Tower of
Power establishing; 0:06–0:13 alternating P1/P2 footage matched to each
spoken test ("thrilling rides" over the tube shot, "amenities" over the Siam
lagoon); 0:11 first graphic (yellow typed mission text over footage); 0:16
first joke ("Grown Man btw" + red arrow); 0:20 💀 stamped over the Tower as
a rider drops; 0:22 the pre-played future moment — him lying in the launch
tub, lifeguard adjusting his arms — under "which you'll see later in this
video." Eleven shots in 21 seconds; both chapters appear before either is
named, and the loop the whole video walks toward is shown, stamped, and
explicitly promised.

## 2. The grammar — named patterns

1. **Versus cut** (0:00–0:13). The two-chapter structure is taught by
   intercutting: worst-park shot, best-park shot, cut landing on the word
   "versus," then each spoken test criterion paired with footage from
   alternating parks. The hook montage IS the format. (Study #1 did the same
   job with stamped numerals for a 5-rung ladder — the stamp form follows the
   structure.)
2. **Promised-peak loop with emoji seal** (0:16–0:22 → 24:28). One future
   moment — the Tower of Power — is shown, skull-stamped, pre-played (the
   launch tub), and verbally promised ("you'll see later in this video").
   The next 24 minutes walk toward it; it closes on schedule at 24:28–25:04.
   Unlike study #1 there's no verbatim-audio replay — the visual pre-play +
   explicit promise carries the loop honestly.
3. **The dread poll** (10:19, 13:04, 16:03, 19:17, 23:19). The same question
   — "what's the scariest ride here?" — is asked to five separate groups
   (a friend, school kids, wave-pool swimmers, grandparents, a couple) and
   every answer is "Tower of Power." Each interview re-opens the hook loop
   and escalates it; he says it out loud: "all these interviews kept adding
   to my anxiety" (19:33). The chorus is the escalation mechanism, and it's
   also social proof that the promised peak is real.
4. **Claims tested on camera** (0:51 → 5:51, 2:38 → 2:26, 6:30). Park 1's
   whole chapter is structured as the internet's complaints (dirty,
   overpriced, long lines — shown as stacked review receipts at 0:51) tested
   one by one against reality: "It looks very clean though. I don't know why
   the reviews said dirty" (5:51), water-stock check against the underlined
   "out of bottled water" review (2:26–2:43), "was the food expensive? Yes"
   (6:30). Each verdict lands next to its receipt. The chapter is a checklist
   the viewer can score along with.
5. **Receipts in three registers** (0:51, 2:38, 12:06/14:06). Magnitude =
   stack five review cards; precision = zoom one phrase and underline it in
   red; ground truth = film the actual sign/map/menu and point at it. The
   artifact always looks like the artifact — a Google card, a browser page, a
   weathered park sign — never like a designed graphic.
6. **Globe owns the doors** (0:25, 8:41–8:47). Every act boundary is the same
   3D globe card: leaving Dallas, naming Park 1, then a drawn flight arc with
   a live "+5455 mi" counter landing on Park 2. The transition graphic
   encodes the video's structure — distance traveled — and the outgoing
   chapter's verdict is spoken over the approach to it (8:38–8:49). No
   scoreboard exists anywhere in this video.
7. **Cast reveal as mini-loop** (9:57–10:15). "I have a confession to make…
   I'm not by myself" — a held 15.4s single take reveals the two friends, each
   tagged with a YouTube-native subscriber card (3.05M / 113K). Companions
   are introduced as a payoff, not listed in the intro.
8. **Peaks run long, tissue runs short — every ride, not once a chapter.**
   Median shot 3.0s, hook at 31 cuts/min, yet all twelve longest shots
   (14.4–28.7s) are ride peaks or the friend reveal, held straight through
   the screams. Roughly one protected take per ride, ~10 across the video;
   caps ~29s here vs 42.7s in study #1.
9. **Status stamps with emoji** (0:34, 2:22, 21:28). Two-to-three-word
   white captions + one emoji mark mode changes and gags — "Opening Day 🤩,"
   "SUBSCRIBERS 😎," "Racing Time 🏎️" — a caption register distinct from
   quotes: it stamps *what this moment is*, not what anyone said.
10. **Honest limitation as content, again** (4:47, 5:57, 20:29, 21:16).
    "pulling camera out of my pocket 😅," "this was not a good idea to try
    to get this shot," "I SCREWED MY PHONE" mid-ride, and a straight-faced
    apology for a jump-scare (21:16). Production flaws are captioned and kept;
    same pattern as study #1, now confirmed as channel grammar.

Smaller notes: B&W grade means "not now" in both directions — flash-forward
(10:26) *and* flashback (23:02); exposition still arrives only when useful
(the park's own 1–5 thrill scale is introduced mid-first-ride at 1:37, and
"only one level five… naturally we'll do that last" states the save-the-best
ordering rule in passing); the outro is 11s, CTA over the endscreen with the
final drop as the background (25:05).

## 3. Verdict on the three standing rules

Same creator, different format — the cleanest possible second data point.

**Rule 1 — chapter-stamped hook montage: CONFIRMED, with a refinement.**
The hook is again a montage of real footage from every chapter at ~2.4x the
body cut rate, ending on the video's single most anticipated future moment,
explicitly promised and later closed (0:00–0:22 → 24:28). But there are no
numerals: with two chapters the stamp is a *versus cut* plus an emoji seal on
the loop moment. And the pre-played peak here is visual + verbal promise, not
a verbatim-audio replay. **Refined rule:** the hook must show one real shot
from every chapter and end on the pre-played most-anticipated moment; *how*
each shot is marked follows the structure (numerals for a ladder, alternation
for a comparison), and the loop needs an honest promise, not necessarily the
moment's own audio. Also note his hooks run 15–21s; our ≤15s cap is tighter
than the pattern requires but not contradicted.

**Rule 2 — stateful progress-map card owns chapter transitions:
CONTRADICTED in form, REFINED in substance.** This video has no progress
map, no numbered thumbnails, no running tally — no rating system at all.
Two data points now say the map card was the *5-levels format's* device,
not channel grammar. What survives across both videos: **one recurring
transition graphic that encodes the video's structural metaphor and carries
state** — the ladder video used a map card with levels lit; the journey
video uses a globe with a flight arc and mileage counter (0:25, 8:41, 8:47)
— and the finished chapter's verdict is spoken over the transition (8:38).
**Rewritten rule:** every chapter door is owned by the same recurring
graphic; the graphic's form matches the video's structure (ladder → lit
levels, journey → route map, museum day → floor-plan with visited halls
lit); it must visibly change state each time; the chapter verdict is spoken
over it. A scoreboard only belongs on it when the format actually keeps
score.

**Rule 3 — peak-protected cut rhythm: CONFIRMED, with two refinements.**
The strongest confirmation in this study: tissue at 3.0s median / 13.1
cuts/min, hook at 31.4 cuts/min, and every one of the twelve longest shots
(14.4–28.7s) is a peak held uncut through the screams. Refinements: (a)
protection applies to **every payoff moment**, not one per chapter — this
video protects ~10 ride peaks across 2 chapters; (b) the uncut window here
is **15–30s**, not 15–45s — the 42.7s hold in study #1 was that video's
singular emotional climax, an outlier, not the norm. **Refined rule:** every
beat tagged `payoff`/`reveal` gets peak protection (no b-roll, no silence
cut, no transition) for 15–30s; one *chapter climax* per video may run
longer.

## 4. What we already do / don't do

Mapped against our pipeline: 14.5-min chaptered family museum vlog, hook
≤15s enforced, silence cuts >0.65s at sentence boundaries only, overlay kit
(hook, lower_third, stat, vote, scoreboard, stamp, reaction, payoff,
transition glass sweep, flight_path, compare), captions in 4-word phrase
groups with green active word, b-roll no-repeat rule, linear shoot order,
96 beats across 5 chapters.

| Pattern | Us today | Gap |
|---|---|---|
| Versus cut hook | ✘ hook is one take + inserts | Confirms study #1's change #1; refines it — stamp form follows structure, versus-alternation is the tool when a video compares two things. |
| Promised-peak loop | Partial — hook opens a question | We never pre-play a specific future moment. New license: visual pre-play + spoken "you'll see later" is enough; no need to engineer an audio replay. |
| Dread poll | ✘ no recurring-question concept | `vote` overlay exists but is a one-off graphic. The pattern is *shot-planning*: same question to different family members across the day, answers cut in as recurring beats. |
| Claims tested on camera | ✘ not a structure we use | Story-designer material: "the internet says this exhibit is X" → test on camera → verdict beside the receipt. Fits the curiosity-gap mechanic exactly — the review IS the open loop. |
| Receipts, three registers | Partial — `stat` is a designed card | A designed card is the opposite register: his receipts look like the artifact (Google card, browser, physical sign). We lack a screenshot-receipt overlay (stack + red-underline variants) entirely. |
| Globe owns the doors | Partial — kit has `flight_path` + `transition` | Our glass sweep is stateless and our flight_path is unused for structure. The museum equivalent is a floor-plan route card with visited halls lit. |
| Cast reveal + subscriber cards | ✘ | Low relevance (family is the standing cast), but the *held reveal* beat (15.4s, no cuts) is usable for a surprise guest or exhibit. |
| Peaks protected per payoff | ✘ silence cuts apply uniformly | Confirms study #1's change #3 at larger scale; refine cap to 15–30s and apply per payoff beat, not per chapter. |
| Status stamps with emoji | ✘ captions are one uniform register | Our caption spec has no second register. A 2–3-word status stamp + emoji is cheap and platform-native. Emoji-only stamps (💀 over the tower) map to our `stamp`/`reaction` types. |
| Honest limitation as content | ✘ flubs go to the kill list | Second video, same pattern — this is now twice-confirmed channel grammar, not a one-off. |
| B&W = "not now" | ✘ no flashback/forward grade | Now seen in both directions (forward 10:26, back 23:02). One ffmpeg grade away. |
| Quote captions, VO never captioned | Partial | We caption everything (mute-first spec — keep), but we still lack the *quote register* that elevates family lines. |
| B-roll no-repeat | ✔ | Match again. |

## 5. Three concrete changes

**1. Plan a loop question and cut it as a recurring chorus.** Rule for the
shoot brief and story-designer: pick one question tied to the hook's open
loop ("what's the one thing you can't wait to see?" / "what's going to be
the weirdest thing here?"), ask it to each family member — and a stranger or
docent if natural — at different points in the day, and place 3–5 of the
answers as recurring beats that all point at the finale chapter. Every
answer must name the same thing the hook promised; the finale closes it.
*Evidence: the same "scariest ride?" question at 10:19, 13:04, 16:03, 19:17,
23:19 — five groups, one answer, loop closed at 24:28; he narrates the
mechanism himself at 19:33 ("all these interviews kept adding to my
anxiety").*

**2. Add a receipt overlay family — and use the artifact's own face.**
Graphics-director rule: any claim sourced from outside the footage ("this is
rated the #1 dinosaur hall," "reviews call this room overwhelming," "the
sign says 3,500 years old") gets its artifact on screen within ~1s of the
spoken claim, in one of three registers: a **stack** of review/article cards
for magnitude, a **zoom + red underline** on the single load-bearing phrase,
or the **physical sign/map filmed and pointed at**. The overlay renders as
the artifact (browser chrome, review card, photo) — never restyled into a
brand card; our `stat` card remains for numbers we generate ourselves.
*Evidence: five stacked 1-star Google reviews at 0:51; "out of bottled
water" red-underlined at 2:38; the weight-limit sign pointed at on camera at
14:06; park map as the wayfinding graphic at 12:06.*

**3. Rebuild the chapter transition as a stateful route card (amends
standing rule 2).** Replace the stateless glass sweep + title at chapter
boundaries with one recurring card whose form matches the video's structure
— for a museum day: the floor plan, visited halls lit in colour, current
hall highlighted, route line drawn, remaining halls dimmed. It must visibly
change state at every appearance, the finished chapter's one-line verdict is
spoken over it, and a tally rides on it only when the video actually keeps
score (bets/votes) — otherwise the geography IS the state. Our `flight_path`
renderer is the nearest existing code. *Evidence: globe at 0:25 / 8:41 /
8:47 with flight arc and live "+5455 mi" counter as the only chapter
graphic in a video with no scoreboard — versus study #1's lit-levels map
card; the invariant is the recurring stateful door, not the scoreboard.*

Runner-up (cheap, do when touching captions): a second caption register —
2–3-word **status stamps + emoji** for mode changes ("Dino Hall time 🦖",
"Opening Day 🤩" at 0:34, "Racing Time 🏎️" at 21:28) and floating
emoji-only reactions (💀 0:20, 😔 21:40) — distinct from the standing
speaker-attributed quote-caption runner-up of study #1.
