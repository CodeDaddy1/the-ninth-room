# The cut bar, calibrated against the real cuts

Decided 2026-08-28 by Caleb, after `scripts/cut_report.py` graded all five
edit plans on disk. The bar (`pipeline/cutbar.py`) was written from the film
studies' measured numbers; this is what changed once it met the footage.

Two of the four decisions changed the code the same day. One is deferred to
the hmns benchmark on purpose. One is owed to `coverage_notes` in Phase 2.

---

## 1. The build-share cap is gone

**Was:** build beats may not exceed 60% of the cut.
**Now:** no share cap. Each chapter must instead carry one beat between its
open and its close that is a `peak`, a `payoff`, a `stakes` or a `button`.

Two measurements killed it.

**Unreachable.** `BEAT_PURPOSES` holds seven roles and five of them are
structural singletons, so an 82-beat episode with five chapters offers 12
non-build slots (5 opens, 5 closes, a hook, a payoff) against the 33 a 60%
cap demands. The remaining 21 could only be label inflation — a twelve-minute
museum visit does not contain twenty-one one-line kickers.

**Not a quality signal.** The two cuts furthest apart in structure sit three
points apart on this number:

| cut | build share | peaks | loops |
|---|---|---|---|
| hmns | 78% | 0 | 0 |
| houston | 75% | 5 | 3 |

A gate a session passes by renaming beats changes no frames. The replacement
asks for the thing itself, and it separates the two cuts the way a viewer
would: hmns is flagged on CH2, CH3 and CH4; houston is flagged on none.

## 2. The pace ladder allows one reversal

**Was:** each chapter's declared `pace_cpm` must be at or under the one
before it (within a 10% wobble).
**Now:** `PACE_REVERSALS_MAX = 1`. The overall decline is unchanged — the
last chapter still sits at or under 0.7 of the first.

All five cuts on disk break strict monotonicity; every one re-energizes in
the middle (hmns realizes 28.9 / 14.6 / 21.8 / 19.5 / 15.9). The rule rests
on a single measured video — Kara & Nate's 39.6 → 14.0 with no reversal —
and a museum day changes hall five times. Caleb's call: a new room earns one
second wind, not two. The note names the reversal and states the total count,
so the allowance never hides how many there were.

## 3. The landing rule — OPEN, deferred to the hmns benchmark

The sign-off produced a real contradiction and it is deliberately unresolved.

- `taste.md` **T28 kept** — a beat should end on a chosen outgoing image.
- `taste.md` **T10 rejected** — "the face delivers" is not his standard.
- `decisions-agent-topology.md` decision 2 (BT94) has him choosing the
  landing gate over T28, refusing any escape hatch: *"a rule a cover can
  escape by declaring the rule inapplicable is not a rule."*

Signed taste and a recorded decision now point opposite ways. Caleb declined
to settle it in the abstract: it gets judged on frames at the hmns benchmark
re-screen, with the shipped cut and the re-cut side by side. Until then
`COVER_LANDING = 0.2` stands as written and nothing cites T28.

## 4. Tags lift the coverage caps — owed to Phase 2

`taste.md` **T11 rejected**, in his words: *"allow for extra b-roll if
relevant by tags."* **T7 rejected** with it, so "support, not density" is no
longer his standard either.

`coverage_notes` currently caps a beat at three covers and at 60% covered
(`COVER_MAX_RATIO`). Decided: a cover whose tags genuinely match its line may
exceed both, and a `peak` beat stays untouchable regardless — the one rule
six of the seven film studies converged on. Not yet implemented; it lands
when Phase 2 opens `pipeline/schemas.py`. The tag quality this leans on is
the same `framing` and tag work the bar's C7 already demands per episode.

---

## What the bar says today

| cut | notes | what it names |
|---|---|---|
| hmns | 26 | no pace ladder, three chapters with nothing between their doors, 0 peaks in 5 chapters, a 2-cover hook |
| houston | 9 | no pace ladder, a 4.4s peak, a hook that does not foretell |
| allure | 11 | no pace ladder, CH1 has no landing moment, no loops, a 2-cover hook |
| _compare_oneshot | 25 | as hmns |
| _compare_room | 24 | as hmns |

Every threshold remains a single constant at the top of `pipeline/cutbar.py`,
each carrying the measurement behind it. Recalibration means changing a
number there and re-running the report — not editing a rule.
