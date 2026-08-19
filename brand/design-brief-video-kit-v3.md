# Curated Curiosities Video Kit v3 — brief for Claude Design

## Context

Curated Curiosities is a family YouTube channel: Caleb on camera with his wife
Alma and daughter Sofia, exploring museums and curiosities. Family friendly,
funny while learning — the humor comes from real reactions, never mockery.
Kids co-watch with parents, and much of the audience watches muted, so
burned-in captions and overlays carry the story.

This is not a one-video request. You are designing the channel's **standing
overlay and effects system**. An automated pipeline re-renders these
components from parameterized HTML/CSS for every future video, so what you
design here becomes the channel's permanent visual language. Design for
reuse: every screen must work with different copy, names, and numbers.

## Design language (refine, don't replace)

The current kit (v2) established: accent green `#12B76A` on near-black ink
`#09090B`, white text, 1px low-alpha hairline borders. Type is **Gabarito**
(display, 700–800) with **Manrope** (body, labels); kickers are uppercase
with wide tracking. Motion is a quick pop-in with slight overshoot
(~350–500ms cubic-bezier), a calm hold, and a quick exit — playful, never
frantic.

Two hard-won rules to keep:
- Any panel over footage uses **≥ 0.90 alpha ink** — translucent panels
  drown in bright, busy footage.
- Big emoji sit on a **dark radial disc** so they can't ghost into the frame.

The master brand (site, thumbnails) uses navy/amber/cream with Playfair
Display + Work Sans. The video kit deliberately runs its own green/ink
language. Keep them distinct, but state the relationship in one sentence so
the contrast reads as a decision, not drift.

## Deliverables — one screen per component

For each: exact layout in px on a 1920×1080 stage, all states, motion
sequence (property, duration, delay, easing), and the legibility treatment
that keeps it readable over bright footage.

1. **Hook / title card** — opens the curiosity gap. Example copy: kicker
   "OPEN TO CLOSE", title "One Family vs. an Entire Museum".
2. **Chapter card** — section turn, ~2–3s hold.
3. **Lower third** — a verified fact or label. Example: "SLOTHZILLA,
   OFFICIALLY / About 13 feet tall and 3 tons / Eremotherium, the giant
   ground sloth". Must clear a person standing frame-right and the caption
   band.
4. **Stat card** — one big number with a label.
5. **Quote / payoff card** — Example: "You're done. You're cooked for
   life." — CALEB, SIZING UP SLOTHZILLA.
6. **Vote card** — a question kicker with 2–3 name/count rows. Example:
   "FOR A MILLION BUCKS" → Eat the cockroach 0 / Absolutely not 0. State for
   a count updating.
7. **Scoreboard / final tally** — names and scores with a winner highlight.
   Example: Sofia 1 (winner) / Caleb 0 / Alma 0.
8. **Stamp** — rubber-stamp slam for comedy verdicts. Example: "NOT ITS
   REAL NAME".
9. **Reaction pop** — a single word blown up big for one beat. Example:
   "GANGLIA".
10. **Big emoji moment** — one emoji at ~260px, front and center on the ink
    disc, for beats with no caption on screen. Pop + subtle wobble.
11. **Caption style spec** — the bottom-band word-pop captions: face,
    weight, size, stroke/shadow, the active word in accent green, emoji
    riding in-line at 1.2× the type size. (Rendered by a separate system —
    spec the look so everything matches.)
12. **Effect treatments** — motion recipes the pipeline reproduces in
    ffmpeg, so specify timing curves and any dressing (frame, vignette,
    grain) that brands them: the zoom punch (1.1–1.15× snap on a word), the
    "wasted"-style desaturate push-in, the speed-ramp-to-black outro, and
    the winner's-rosette pop-in.

## Quality bar — the point of this package

- Safe zones: bottom 220px belongs to captions; keep the top-right clear
  for platform UI. Nothing may cover a face by default placement.
- Minimum holds: a card must be fully readable twice at a comfortable pace
  before it exits.
- Every screen must pass over the worst case: bright greenhouse footage
  with dense foliage AND a dark cave exhibit. Specify the scrim/plate/
  stroke that guarantees it.
- Names and numbers are variables. Show each screen with realistic content,
  and note where text can grow (a long museum name, a three-digit count).
- One portrait note per screen: what changes at 1080×1920.

## Constraints (the design must be implementable as-is)

- Pure HTML/CSS. No JS-driven motion, no canvas, no WebGL, no video. CSS
  `@keyframes` on transform, opacity, filter, and clip-path are the motion
  vocabulary.
- Transparent stage — the overlay composites over footage; never assume a
  background exists.
- Every animation seekable: explicit durations and delays (frames are
  captured by seeking `currentTime`).
- Fonts: Google Fonts only, named explicitly (Gabarito, Manrope, Playfair
  Display, and Work Sans are already in use).
- Raster assets under ~190 KB each; prefer CSS shapes and SVG.

## Out of scope

Thumbnails, end screens, and the website — the master brand system covers
those. Music and SFX — a separate cue-sheet system handles sound.
