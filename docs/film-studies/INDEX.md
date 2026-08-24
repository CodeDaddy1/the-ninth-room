# Film studies index

One line per study: title, source, the single biggest takeaway.

- **Hangtime — "I Tried 5 Levels of Waterparks"** ([study](hangtime-5-levels-of-waterparks.md), [source](https://www.youtube.com/watch?v=dakebYDWN6Q)) — The hook previews every chapter with stamped real footage and pre-plays the finale's scariest moment; then one recurring progress-map card carries chapter state + running scores, and the cut rate breathes: 2.8s median shots for connective tissue, 16–43s uncut holds on the emotional peaks.
- **Hangtime — "I Tested 1-Star vs 5-Star Waterparks"** ([study](hangtime-1-star-vs-5-star-waterparks.md), [source](https://www.youtube.com/watch?v=RzQJc3pRtes)) — Same creator, different format, so the standing rules got tested: peak-protected rhythm and the chapter-preview hook survive (3.0s tissue median, all twelve longest shots are uncut peaks), but the progress-map card does NOT — the recurring chapter-door graphic is whatever encodes the video's structure (here a globe with a "+5455 mi" flight arc), and the biggest new pattern is the dread poll: one loop question asked to five different groups, every answer pointing at the promised finale.
- **Johnny Harris — "The Worst War You Never Learned About, Mapped"** ([study](johnny-harris.md), [source](https://www.youtube.com/watch?v=czQrU0OPIR8)) — The opposite of the Hangtime rhythm and it works: the hook is the SLOWEST-cut section (4.1 cuts/min vs 12.4 in its own sponsor read), the first hard cut lands at 0:14.93, and the two longest shots in the 16-minute video are both maps in the first 2:14 (61.0s and 54.6s). The reconciliation is that the rule was never "cut fast" but "change state fast" — inside that 54.6s shot the board changes ten times, one every ~3s. Peak protection survives a third study, now as engineered silence (19s and 13s of no VO at Srebrenica), and the single most useful artefact is the sourced-quote card at 10:32: the primary source speaks in the silence, subtitled, with a small grey attribution line underneath.

- **Beau Miles — "Running a different kind of marathon: A Mile an Hour"** ([study](beau-miles.md), [source](https://www.youtube.com/watch?v=EvT5XS7j-Dc)) — A 17-minute film with an **8% talking head**: 8 of 100 sampled frames show anyone addressing camera, and 20.6% of the runtime has no voice at all. That gap exposed the hole in our b-roll grammar — all four of our justifications (establish/illustrate/foretell/bridge) are defined against a spoken line, so nothing legally covers a wordless making sequence; the fifth justification is **`process`** ("the work advanced"). Two more directly stealable artifacts: the counter **changes unit** when the mode changes (MILE 1–16 by day → 2:00/3:00/4:00 AM through the night → MILE 22–26.219 for the finish), and the progress graphic is a **real object** — a handwritten list, crossed off on camera at 2:47 / 6:19 / 8:32 / 15:45, which cost one sheet of paper. Peak protection confirmed a fourth time, here as darkness plus a ~6× slower cut rate.

- **Mark Rober — "Backyard Squirrel Maze 1.0 — Ninja Warrior Course"** ([study](mark-rober.md), [source](https://www.youtube.com/watch?v=hFZFjoX2cGg)) — The fastest-cut film on the shelf (**18.5 cuts/min, 2.42s median** over 20:20) and the one aimed hardest at families, which settles the idea that warmth needs slow. Its spine is a **loop ledger**: eight obstacles named between 4:43 and 6:38, all eight paid in the same order between 8:10 and 15:43, with the gap widening monotonically 3:26 -> 9:05 — and the emotional climax landing at 72% of runtime, not last. Two structural findings we were not using: **all 16 direct-address frames fall before 7:35** (the presenter vanishes for the last 62%, so setup and payoff are different films), and **the cast card is made of wood** — hand-lettered name-boards in the yard, Beau Miles' real-object rule confirmed by a creator with a hundred times the budget. Best single artifact: at 17:00.89 a black card reads `300 milliseconds`, then a **5-frame white flash** *is* the demonstration — the graphic's duration is the fact (measured 0.208s, which is also the study's honesty warning).

- **Yes Theory — "ABANDONED city in America with NO LAWS"** ([study](yes-theory.md), [source](https://www.youtube.com/watch?v=kUTYSyd3LR0)) — The channel's most-viewed video (28.8M) and its four-person ensemble era, at **18.8 cuts/min over 10:18** — within 2% of Mark Rober, which kills the idea that cut rate is what separates these films. What separates them is **gear change**: the 19.3% of runtime that is scripted VO carries **35% of all the cuts** (34.2 cuts/min, 1.76s mean shot) while everything else runs at 15.2 — so "median shot length" is meaningless as one number, and our pace target should split in two. The ensemble finding is structural, not tonal: **strangers get as much solo screen time as the whole cast** (20 vs 22 of 100 frames), every interview is a two-shot with the listener in frame, direct-to-lens is ≤4% and confined to the car, and **three of the four longest shots in the film are one uncut take of one local** (19.24s at 4:50.72). The identity system is flat — the man who empties buckets gets the same 1.3s typewriter card as the founders. Two more directly stealable artifacts: the **title card lands at 0:28.88, not 0:00** (2.16s of black, exactly on the first chapter boundary), and the detour is **licensed inside the hook** at 0:23.76, five seconds before it. And they reached our one-yellow-moment rule independently — one coloured emphasis term per card, everything else white, no boxes anywhere.

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

