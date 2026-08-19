# Film study: Hangtime — "I Tried 5 Levels of Waterparks"

- **Source:** https://www.youtube.com/watch?v=dakebYDWN6Q (channel: Hangtime)
- **Runtime:** 22:46 (1366s), 854x480 analysed, native captions (clean)
- **Studied:** 2026-08-19, two passes — 100 scene-aware frames full-range, then
  33 frames at higher resolution over 0:00–1:00. Cut timestamps measured with
  ffmpeg scene detection (threshold 0.3, 361 cuts found). Scene detection
  under-counts cuts between similar shots, so shot lengths below are best read
  as slight over-estimates.
- **Genre distance:** athletic solo creator, GoPro thrill rides, strangers as
  supporting cast, ~1M-sub polish. We are a family museum vlog. Translate:
  ride = exhibit reveal, fear = anticipation (bets/votes), "142 ft drop" =
  "3,500 years old", stranger chorus = family chorus.

## 1. The numbers

**Structure.** Five "levels" (parks), strictly escalating in price/epicness,
each closed with a rating out of 10. Chapter marks, from the transcript:

| Section | Start | Length | Rating (spoken at) |
|---|---|---|---|
| Hook / mission | 0:00 | 24s | — |
| L1 Backyard | 0:24 | 40s | 3.5/10 (at 1:25, retroactively) |
| L2 The Cove | 1:04 | 2:39 | 4/10 (3:41) |
| L3 Waco Surf | 3:43 | 6:43 | 6/10 (10:24) |
| L4 DreamWorks | 10:26 | 6:27 | 9/10 (16:50) |
| L5 Volcano Bay | 16:53 | 5:41 | 8.5/10 (22:36) |
| Outro + button | 22:34 | 12s | winner: DreamWorks |

Time budget follows epicness: levels 1–2 get 3:19 combined; levels 3–5 get
~18:52. The cheap parks are treated as warm-up jokes, on purpose.

**Shot lengths** (362 shots total; median 2.77s, mean 3.77s, 15.9 cuts/min,
range 0.5s–42.7s):

| Section | Shots | Cuts/min | Median | Mean | Max |
|---|---|---|---|---|---|
| Hook (0:00–0:24) | 12 | 30.0 | 1.93s | 2.19s | 4.6s |
| L1 backyard | 21 | 31.5 | 1.47s | 1.82s | 4.3s |
| L2 The Cove | 36 | 13.6 | 3.42s | 4.51s | 24.3s |
| L3 Waco Surf | 118 | 17.6 | 2.55s | 3.41s | 14.3s |
| L4 DreamWorks | 86 | 13.3 | 2.88s | 4.50s | 42.7s |
| L5 Volcano Bay | 87 | 15.3 | 3.17s | 3.90s | 18.0s |

First 15 seconds: 7 cuts, median shot 1.68s. The open runs ~2x the cut rate
of the body.

**The five longest shots are all emotional peaks, not filler:** 42.7s at
16:08 (the scared conversation before the Thrillagascar launch, played nearly
uncut through "3 2 1 launch"), 32.3s at 12:10 (wave pool ride), 24.3s at 2:34
(the SpongeBob kid interview), 18.0s at 20:32 (Honu ride), 16.5s at 14:14
(Sinkhole Slammer raft ride). Cut rate breathes: fast connective tissue,
long uncut peaks.

**Talk/cover ratio:** of the 100 sampled frames, 28 show someone addressing
the lens (talking head, selfie-stick piece, interview), 64 are action
POV/b-roll with VO carrying the narration, 8 are full-screen graphics.
Roughly **30/70 talk-to-cover** — the story is told over footage, not to a
tripod.

**Overlay census** (observed in the ~107 sampled frames; captions persist
2–4s so this is a floor, true totals are higher):

- 11 quote/dialog captions — always someone's *actual words*, lowercase,
  chunky white or yellow, mid-low center: "dude idk if I wanna do it
  actually" (0:15), "who's ready to go on the slip & slide?" (0:29), "meeee"
  (0:31, the kid's answer), "hahaha" (0:47), "why are you wearing Patrick
  sqa—" (2:34), "what's the best ride here?" (3:07), "should i do it?"
  (6:23), "Grace: go big or go home" (6:48 — **speaker-attributed**), "I
  wanna go again" (8:04), "Paul are you scared?" (18:13), "*intense caugh*"
  (19:19 — asterisk action caption, typo and all). His own VO is never
  captioned.
- 4+ sightings of one recurring **progress-map card**: five numbered circles
  with park photos on a dark water background — all locked at 0:26, partially
  built at 1:19, levels 1–2 lit at 3:44, 1–3 lit at 10:27. Chapter card and
  scoreboard fused into a single stateful graphic.
- 2 stat labels: "142 ft drop" stamped in yellow over both launch capsules
  (0:14).
- 3 research-receipt screenshots: world's-longest-lazy-river article (5:26),
  DreamWorks top-3-rides doc with bolded superlatives (11:18), Volcano Bay
  top-3 doc — "125-ft vertical drop", "trapdoor free-fall", "60 feet per
  second" (17:13–17:23).
- Misc: giant "5" numeral stamped on hook b-roll (0:01), animated neon
  chevron pointing up the slide (0:04), "LAUNCH 🙂" action caption (0:17),
  "Goals:" typed in yellow over dimmed footage (0:19–0:22), red arrow
  annotations (3:58, 22:39), B&W grade marking a flash-forward (0:58), white
  flash transition (22:08), meme zoom face freeze (22:18).
- **Zero** lower thirds, zero branded motion graphics, zero animated kits.
  Every overlay is either someone's words, a number, or the map.

**Hook anatomy (0:00–0:24, transcribed exactly):** "In this video, I'm trying
five levels of water parks. The levels increase based on price and overall
epicness. And as a grown man, I had the time of my life making this video.
It's important to know that each park has one super unique slide that of
course I'll be testing. — Dude, I don't know if I want to do it actually. —
My goal: find the best water park in America and see whether price really
makes a difference. Starting with level one, the backyard water park."
Visually: 0:00 mid-scream ride POV (no logo, no greeting); 0:01 first
graphic (giant "5" on Volcano Bay b-roll); 0:04 chevron arrow; 0:14 first
stat ("142 ft drop"); 0:15 first joke and the pre-played fear moment; 0:19
mission card; 0:23 level one begins. Eleven shots in fifteen seconds, and
every level of the video appears in the montage before it's named.

## 2. The grammar — named patterns

1. **Scream-first cold open** (0:00–0:01). Frame one is the emotional peak of
   the whole video mid-ride, face filling a GoPro. The thesis VO starts *over*
   it at 0:02. No intro, no branding, no "hey guys."
2. **Level-stamp montage as table of contents** (0:01–0:10). The hook montage
   shows real footage from the later chapters with giant numerals stamped on
   it ("5" at 0:01). The viewer sees the whole ladder before level one starts
   — the montage is the contract.
3. **Pre-played fear loop** (0:10–0:17 ↔ 16:19). The hook replays his single
   most vulnerable future moment — the launch capsule, real audio, "dude idk
   if I wanna do it actually," "LAUNCH 🙂" — then the video spends 16 minutes
   walking back to it. The same line recurs verbatim at 16:19. One honest
   open loop, closed completely. The "each park has one super unique slide"
   rule (0:08) additionally opens five mini-loops, one per chapter.
4. **Goals card on dimmed footage** (0:19–0:22). The mission gets three
   dedicated seconds: footage dims, "Goals:" types on in yellow, the goal is
   spoken and shown simultaneously. You can't miss what the video is for.
5. **One progress map owns every chapter door** (0:26, 1:19, 3:44, 10:27).
   The same five-circle card returns at each transition with state: finished
   levels in full colour, the future greyed out. The rating for the finished
   park is spoken over it. Chapter card, scoreboard, and "how much is left"
   in one recurring graphic.
6. **Rules invented mid-game** (1:16–1:32). The 10-point rating system and
   the top-3-rides-per-park constraint are introduced *during level two*,
   then applied retroactively ("the backyard park got a 3.5"). The constraint
   is framed as a viewer favour: "if I showed everything, this video would be
   5 hours long." Exposition arrives exactly when it becomes useful, never
   sooner.
7. **Receipts on screen** (5:26, 11:18, 17:13–17:23). Every superlative claim
   is backed by a visible screenshot with the key phrase bolded, landing
   within ~1s of the spoken claim — "longest lazy river in the entire world"
   (5:27) over the article that says so. Facts are shown, not just asserted.
8. **Peaks run long, connective tissue runs short.** Median shot 2.77s, but
   the five longest shots (16.5–42.7s) are precisely the fear conversation,
   the rides, and the best interview. He cuts fast to *get to* a moment and
   then refuses to cut *inside* it. The 42.7s shot at 16:08 is the emotional
   climax of the entire video.
9. **The stranger chorus, quoted on screen** (2:03, 3:04, 6:21, 9:27, 13:49,
   18:12). Quick interviews with people at each park — kids, a banana-suited
   guy, Paul — whose real words become the captions, sometimes
   name-attributed ("Grace: go big or go home", 6:48). Other voices carry
   the humor and the social proof; the captions elevate *their* lines, not
   his narration.
10. **Honest limitation as content** (12:48, 13:44, 21:33–22:13). No
    cameraman → a bit about hiring one. Mic died → comedic voice-over
    re-enactment, flagged on screen. Not allowed to film the last slide →
    negotiates with the lifeguard on camera, then licenses the gap with "shout
    out to this legend for sneaking it on 7 years ago," using a 2013-era
    vertical clip as the payoff. Production failures become jokes instead of
    silent cuts — and the payoff still lands.

Smaller notes worth keeping: flash-forward b-roll is graded **black-and-white**
so "later" can't be mistaken for "now" (0:56–0:58); after the outro CTA there
is one final 7-second gag (the People Dryer + red arrow + "What are you doing
in my swamp?" callback, 22:39) so the video ends on a laugh, not a plea.

## 3. What we already do / don't do

Grounded against `work/hmns/edit_plan.json` (96 beats, 874s, chapters
30/250/112/224/258s, 13 `fun` overlay moments, transitions = 83 cut / 13
dissolve), `pipeline/overlay_kit.py` (hook, lower_third/section,
chapter/outro, scoreboard, stat, payoff/quote, stamp, caption_plate, compare,
flight_path, contact, reaction, vote, transition glass sweep), and
`pipeline/timeline.py` (MAX_KEEP_GAP_SEC=0.65, KEEP_PAD_SEC=0.2,
DISSOLVE_SEC=1.0, MIN_SEGMENT_SEC=0.4).

| Pattern | Us today | Gap |
|---|---|---|
| Scream-first cold open | ✔ BT01 is a 10.6s flash-forward, "first 2s stay on his face" | Match. Keep. |
| Level-stamp montage TOC | ✘ Our hook is one take + 2 b-roll inserts (~4 shots in 10.6s) | His hook: 11 shots/15s, one from *each* chapter, numeral-stamped. Our hook previews the day, not the chapters. |
| Pre-played fear loop | Partial — hook opens the "what was worth it?" question | We never pre-play a *specific* future moment with its real audio. Note: edit plan v3 enforces "zero foreshadow beats" — the licensed exception is the hook itself. |
| Goals card | ✘ Mission is spoken in BT02–BT03, never shown | We have `hook`/`stamp` renderers that could do this tomorrow. |
| Stateful progress map | ✘ `chapter` card + glass sweep is stateless; `scoreboard` appears 2x, disconnected | His single recurring card carries chapter state + running scores. Contradicts our default chapter grammar. |
| Rules invented mid-game | ✘ Our exposition front-loads in CH1 (30s) | His CH1-equivalent is 24s *because* rules wait until level two. |
| Receipts on screen | Partial — `stat` card exists | Our stats are designed text; his land within ~1s of the claim and every superlative gets one. Placement discipline, not new renderer. |
| Peaks long / tissue short | ✘ Silence cuts (>0.65s) apply uniformly; no "don't cut here" concept | Nothing in the plan marks a peak; b-roll can land on top of the day's best reaction. |
| 30/70 talk-to-cover | ✘ We are talk-forward; 71 b-roll placements over 96 beats but cover is partial | His VO narrates over action; our takes narrate to the lens. Partly genre — but our museum b-roll could carry more. |
| Stranger/family chorus captions | Partial — `vote`/`reaction`/`stamp` are host-centric; captions are uniform 4-word green-word groups | No speaker attribution, no asterisk action captions. Sophia's lines deserve the "Grace:" treatment. |
| Honest limitation as content | ✘ Not a pipeline concept | Story-designer brief material: flubs and rule-collisions can be beats, not kill-list entries. |
| Burned captions everywhere | We caption everything (mute-first spec) — he captions only quotes | Keep ours; platform norm for us. |
| B-roll no-repeat rule | ✔ 71 placements, 71 distinct clips | Match — he also almost never reuses a shot outside the map card. |

## 4. Three concrete changes

**1. The hook must preview every chapter, stamped.** Rule for story-designer
and graphics-director: inside the enforced ≤15s hook, after ~2s on the
cold-open face, cut one shot from *each* chapter in order, each carrying its
chapter numeral (a numeral variant of `stamp`), and end the montage on the
video's single most anticipated future moment with its real audio — that
moment is the loop the finale closes. Foreshadow stays banned in the body;
the hook is the one licensed flash-forward, and montage inserts get a
distinct grade (his B&W trick, 0:56) so "later" reads as later.
*Evidence: 0:01–0:17 — five stamped levels, "142 ft drop", pre-played "dude
idk if I wanna do it actually"; hook median shot 1.68s vs our ~4-shot hook.*

**2. One stateful progress-map card owns every chapter transition.** Replace
the stateless glass sweep + title with a single recurring `scoreboard`-family
card that shows all chapters as numbered thumbnails — done in colour,
current highlighted, future dimmed — and carries the running tally (votes,
butterfly count, whatever the video's score is). The verdict line for the
chapter just finished is spoken over this card. Same card, new state, every
time: it teaches the viewer how much is left and makes the through-line
visible. *Evidence: 0:26 (all locked), 3:44 (1–2 lit), 10:27 (1–3 lit);
ratings ladder 3.5 → 4 → 6 → 9 → 8.5 is the video's spine.*

**3. Cut rate must breathe: mark peaks, protect them, speed up the tissue.**
Story-designer marks one `peak` beat per chapter. Rules: inside a peak beat,
no b-roll insert, no silence cut, no transition — let it run 15–45s raw.
Outside peaks, a beat must produce a visual change (cut or b-roll placement)
at least every ~4s; a non-peak beat running >8s on one static framing gets a
placement or a split. *Evidence: whole-video median 2.77s (15.9 cuts/min),
yet the five longest shots — 42.7s fear talk at 16:08, 32.3s at 12:10, 24.3s
interview at 2:34, 18.0s at 20:32, 16.5s at 14:14 — are exactly the emotional
peaks, held uncut.*

Runner-up (cheap, do when touching captions): speaker-attributed and
asterisk-action caption variants for family lines — "Sophia: ..." and
"*gasp*" — per 6:48 and 19:19.
