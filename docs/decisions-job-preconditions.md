# A job's preconditions are declared data, and the answer rides on project state

**Decided 2026-08-28 by Caleb,** against the job ledger — 50 jobs, of which
**14 failed (28%)**. Frozen to `baselines/jobs-2026-08-28.json`; the live
ledger keeps only the last 50 (`jobs.py:7`) and had already rotated once
during the session that produced this document.

## What the ledger says

| class | what happened | n | wall-clock burned |
|---|---|---|---|
| A | an action was offered that could never have succeeded | 4 | ~0s each |
| B | an agent ran for minutes and wrote nothing | 5 | **1,768s (29.5 min)** |
| C | infrastructure — restart, validation, no frames | 5 | 943s (15.7 min) |

`editplan` ran **6 times and failed 5**, median 309s, worst 1,366s. The most
important creative gate in the pipeline succeeds one time in six.

Class A is the diagnostic one. Those four died in under a second — the
engine's guard was already there and already correct. `_run_editplan` checks
takes, stories, an approving round and an existing plan before it dispatches
anything. The preconditions are not missing. **They are imperative `raise`
statements inside each runner, so they can only answer after the click.**

## The principle was already written down

`jobs.py:1026`, after the oligarchy session on 2026-08-26:

> *"A dispatched session is billed minutes; a gate that a file check can
> answer must answer before the dispatch, not after."*

Correct, and applied at exactly one site. This decision generalises it.

## What was compared

| | A — predicate registry | B — project state machine | C — parallel `can_run()` |
|---|---|---|---|
| shape | each raise becomes a named predicate with its message | engine computes a phase; jobs declare legal phases | keep the raises, add a second answer |
| refactor cost | mechanical, message-preserving | new model, must encode `phasePath()` | lowest |
| handles `origin` variance | yes, per predicate | needs the documentary reordering encoded twice | yes |
| second source of truth | no | no | **yes** |

**A.** B is the more elegant model and the wrong bet — the five phases
already reorder for a documentary (`origin === 'script'`), so a single state
machine would have to duplicate `surfaces.phasePath()` on the engine side.
C was rejected outright: a second copy of a condition is precisely what
produced the `vo_` drift (see `decisions-beat-and-take-kind.md`).

## What this decides

- **Preconditions are declared,** one named predicate per condition, carrying
  its own message and the surface that satisfies it. They live in a new
  module — `jobs.py` is 2,402 lines and adding to it is how it got there.
- **Two consumers, one declaration.** The runner guards on it (behaviour
  unchanged); the Studio renders it (new).
- **The answers ride on the project-state call the desks already make.** No
  new endpoint and no new round trip — a separate readiness fetch would tempt
  desk headers into fetching for themselves, which rule 7 forbids.
- **The runner promotes; the agent no longer publishes.** A session writes
  its artifact to a staging path; the runner validates it against the schema
  and moves it into place. Nothing invalid reaches disk, and "ran and wrote
  nothing" becomes a named failure at the moment it happens rather than a
  post-hoc discovery.
- **Every job declares whether it is retryable.** A job that appends, imports
  into Resolve, or touches the outside world is not, and says so, so the UI
  never offers a retry that would double-apply.

## The obstacle this has to clear

Seven sites launch the `claude` CLI. Only two are the shared helpers —
`_dispatch` (`jobs.py:1238`) and `_dispatch_json` (`jobs.py:1458`). The
other five hand-roll their own `subprocess.Popen`: `fixer` (376),
`research` (731), `scout` (1079), `publish` (1155), `sourcing` (1880).

**Staging-and-promote placed in `_dispatch_json` would silently miss five
runners** — including `sourcing` and `research`, which between them account
for three of the five Class B failures. Consolidating dispatch is therefore
not a tidy-up to do afterwards; it is a prerequisite. This is the same
pathology as the `vo_` drift, one level up: the dispatch mechanism has no
single home either.

## Consequences

- Class A should go to zero: a door that cannot open is drawn closed, with
  the engine's own words on it.
- Class B failures keep their cost but lose their silence — and once retry
  exists, a failed run is one click rather than a re-derivation.
- The retryable classification is a new artifact. Nothing anywhere currently
  records which of the 25 job kinds are safe to run twice.
- Scoreboard: **editplan never again fails after 300 seconds of waiting**,
  checked against dead wall-clock across a comparable ledger. The current
  `work/_jobs.json` is the frozen baseline.
