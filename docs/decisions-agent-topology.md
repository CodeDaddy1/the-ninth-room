# The room lost the blind A/B — refinement-only from here

**Decided 2026-08-24 by Caleb, blind.** Pre-registered as P2's exit
criterion in the Agent Team plan before either half ran.

## What was compared

The same bombardment-era hmns cut (82 beats, 56 covers, 72 craft
violations) re-covered twice, identical input, identical bar:

| | A — the room | B — one-shot |
|---|---|---|
| process | coverage-editor + showrunner scoring R1–R6, notes back, looped | one refined agent, one pass |
| covers | 30 | 39 |
| craft violations | 0 | 0 |
| hook reading | two `foretell` shots — chapter preview | one `establish` wide on the museum's name |
| cost | $12.34, 37,303 tokens | one session |
| finished clean | no — stopped at the BT94 human gate | yes |

Caleb picked **B, the one-shot**, judging frames and whys with the
labels sealed. The key opened after the pick.

## What this decides

**The refinement was the win; the topology was not.** Both halves
cleared the bar, so the brief work — the b-roll grammar, the mechanical
`coverage_notes` bar, the rubric written into the craft's own brief —
is what took a bombardment down to a clean cut. The lead-and-loop cost
about 4x per run and produced no quality difference a human could see.

Therefore, per the plan's own branch:

- **P3–P6 collapse to the refinement-only path.** Remaining agents get
  the same treatment — doctrine, mechanical bar, worked examples,
  self-critique, stable rubric ids — and run as ONE-SHOT jobs.
- **No lead loop.** Do not wire new crafts through the showrunner.
- **The board stays, as a visibility surface only.** `production.json`,
  `fold_production`, the desk and the brakes are built, tested and
  cheap; they show what happened. They no longer drive the work.
- The `room` job kind and `showrunner.md` stay on disk, dormant. They
  cost nothing unused, and re-deciding this later should require new
  evidence, not archaeology.

## What this does NOT decide

One episode, one craft, one judge. It says the room did not beat a
refined one-shot at b-roll coverage on this material. It does not say a
review loop is worthless for a craft with a fuzzier bar — but reopening
it needs a fresh comparison of the same shape, pre-registered the same
way, not an argument.

---

# BT94: the gate wins, and no exception mechanism gets built

**Decided 2026-08-24 by Caleb: "remove bt94".**

The open question was whether a cover may end a beat. Caleb's round-2
verdict had moved B136 — the low-angle push-in on the rearing giant
ground sloth — to BT94's tail so the beat ENDS on it, cutting into the
reveal at the same mount. `coverage_notes` flags exactly that as
covering the landing, and the coverage job hard-fails while the finding
stands, so the shot sat out of the plan in `work/_compare_room/`.

Three ways out were on the table: (a) his verdict wins via a per-beat
exception, (b) the gate wins and BT94 ends on faces, (c) the shot moves
to the head of BT58/BT59. **He chose (b).**

So: **the landing rule holds with no escape hatch.** No `allow_landing`
flag, no `beat_close` justification, no human-only exceptions file. The
last fifth of a beat belongs to the face, full stop, and a cover that
wants it loses.

This is the second time today the same principle decided a design: a
rule a cover can escape by declaring the rule inapplicable is not a
rule. `process` earns no relaxation of the craft rules for the same
reason.

B136 remains in `work/_compare_room/trash.json` against BT94 @6.1/2.21,
so a restore would put it back exactly where it was — but nothing is
waiting on that, and hmns's shipped cut is untouched.
