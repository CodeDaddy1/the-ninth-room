# Film studies index

One line per study: title, source, the single biggest takeaway.

- **Hangtime — "I Tried 5 Levels of Waterparks"** ([study](hangtime-5-levels-of-waterparks.md), [source](https://www.youtube.com/watch?v=dakebYDWN6Q)) — The hook previews every chapter with stamped real footage and pre-plays the finale's scariest moment; then one recurring progress-map card carries chapter state + running scores, and the cut rate breathes: 2.8s median shots for connective tissue, 16–43s uncut holds on the emotional peaks.
- **Hangtime — "I Tested 1-Star vs 5-Star Waterparks"** ([study](hangtime-1-star-vs-5-star-waterparks.md), [source](https://www.youtube.com/watch?v=RzQJc3pRtes)) — Same creator, different format, so the standing rules got tested: peak-protected rhythm and the chapter-preview hook survive (3.0s tissue median, all twelve longest shots are uncut peaks), but the progress-map card does NOT — the recurring chapter-door graphic is whatever encodes the video's structure (here a globe with a "+5455 mi" flight arc), and the biggest new pattern is the dread poll: one loop question asked to five different groups, every answer pointing at the promised finale.
- **Johnny Harris — "The Worst War You Never Learned About, Mapped"** ([study](johnny-harris.md), [source](https://www.youtube.com/watch?v=czQrU0OPIR8)) — The opposite of the Hangtime rhythm and it works: the hook is the SLOWEST-cut section (4.1 cuts/min vs 12.4 in its own sponsor read), the first hard cut lands at 0:14.93, and the two longest shots in the 16-minute video are both maps in the first 2:14 (61.0s and 54.6s). The reconciliation is that the rule was never "cut fast" but "change state fast" — inside that 54.6s shot the board changes ten times, one every ~3s. Peak protection survives a third study, now as engineered silence (19s and 13s of no VO at Srebrenica), and the single most useful artefact is the sourced-quote card at 10:32: the primary source speaks in the silence, subtitled, with a small grey attribution line underneath.

- **Beau Miles — "Running a different kind of marathon: A Mile an Hour"** ([study](beau-miles.md), [source](https://www.youtube.com/watch?v=EvT5XS7j-Dc)) — A 17-minute film with an **8% talking head**: 8 of 100 sampled frames show anyone addressing camera, and 20.6% of the runtime has no voice at all. That gap exposed the hole in our b-roll grammar — all four of our justifications (establish/illustrate/foretell/bridge) are defined against a spoken line, so nothing legally covers a wordless making sequence; the fifth justification is **`process`** ("the work advanced"). Two more directly stealable artifacts: the counter **changes unit** when the mode changes (MILE 1–16 by day → 2:00/3:00/4:00 AM through the night → MILE 22–26.219 for the finish), and the progress graphic is a **real object** — a handwritten list, crossed off on camera at 2:47 / 6:19 / 8:32 / 15:45, which cost one sheet of paper. Peak protection confirmed a fourth time, here as darkness plus a ~6× slower cut rate.

## What these studies became

The progress-map finding from both Hangtime studies is now **built in**, not a
per-video decision: the `chapter` card carries a door meter — one small arch
per chapter (`chapters` = the episode's real total, `active` = doors lit) —
which is the channel's own structural graphic and changes state at every
chapter turn. This honours the second study's warning directly: the graphic
encodes THIS video's structure, not a fixed nine. See
`brand/engagement-playbook.md` and the `chapter` / `streak` screens in
`pipeline/overlay_kit.py`.

The Beau Miles finding is **half built** (2026-08-24). `process` is now the
fifth justification in the b-roll grammar (`.claude/agents/story-designer.md`)
and in the coverage-editor's R1, and `schemas.COVER_WHYS` / `why_kind()` check
the leading word mechanically — R1 used to be the reviewer's judgment, and a
`why` naming no justification at all now fails the bar. What is NOT built is
the structure Beau actually cuts from: a beat with no spoken take, where
b-roll is the whole picture. Our edit plan cannot express it — every beat is
anchored to a speech take, and there are zero wordless takes among hmns's 376
— so it stays an open engine feature rather than a word quietly redefined.

The second study's warning still stands — the progress graphic has to encode
*this* video's structure. For The Ninth Room it always does, because the
format is literally nine rooms.

