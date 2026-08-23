---
description: Review, fix, and re-verify in a loop until the codebase is clean or the loop stops making progress
argument-hint: [scope] [--max <n>] [--dry]
---

Run the review→fix→verify loop over `$ARGUMENTS` (default: the whole engine
plus the Studio). All Python runs with `/usr/bin/python3` from the repo root.

`--dry` reviews and reports without applying any fix. `--max <n>` caps the
rounds (default 5).

## The loop

Each round is: **baseline → review → triage → fix → verify**. Repeat until a
stop condition fires. Announce the round number and the open-issue count at
the start of every round so progress is visible.

### 1. Baseline — measure before you touch anything

```
/usr/bin/python3 -m py_compile pipeline/*.py
/usr/bin/python3 -m unittest discover -s tests -t .
```

and, when a slug is in play, `/usr/bin/python3 -m pipeline.cli audit <slug>`.
In the Studio repo: `npx tsc --noEmit`, `npm run lint`, `npm test`.

Record the numbers. This is round 0's issue count, and every later round is
compared against it. **A round that does not reduce the count is a failed
round** — see the stop conditions.

### 2. Review

Dispatch the **code-reviewer** agent over the scope. It is read-only and
returns findings ranked by severity, each labelled Verified or Inferred.

### 3. Triage — decide, do not fix everything

Sort findings into:

- **Fix now** — verified defects with a clear cause and a bounded fix.
- **Needs Caleb** — anything touching his footage, his Resolve project, a
  destructive delete, a naming or product decision, or a behaviour he would
  have an opinion about. **Do not fix these.** Append them to
  `.claude/reminders.md` and carry them forward as open.
- **Won't fix** — inferred findings you could not reproduce, and anything
  out of scope. Say why.

Report the triage before acting on it.

### 4. Fix

Dispatch the **debugger** agent per issue, one issue at a time, highest
severity first. Each fix must arrive with a test in `tests/` that fails
before and passes after, unless the failure genuinely cannot be expressed as
one — in which case say so explicitly.

Do not batch unrelated fixes into one change. When two findings share a root
cause, fix the cause once and note that it closed both.

### 5. Verify

Re-run the full baseline from step 1 — not just the new test. Compare against
the previous round. Report: fixed, still open, newly introduced.

**A fix that breaks something else is not a fix.** Revert it and re-triage.

## Stop conditions

Stop and report when any of these fires:

1. **Clean** — review returns no verified findings and the baseline is green.
2. **No progress** — a round closes zero issues. Do not run the same round
   again hoping for a different result; report what is stuck and why.
3. **Regression** — a round leaves the baseline worse than it started.
   Revert that round's changes and stop.
4. **Round cap** — `--max` reached (default 5).
5. **Needs Caleb** — every remaining issue is in the Needs-Caleb bucket.
   That is a clean finish, not a failure; the loop cannot proceed without him.

Never loop indefinitely, and never lower the bar to reach "clean" — a test
weakened or deleted to make a round pass is a regression, and the loop must
report it as one.

## Final report

- Rounds run, and the issue count at each round.
- What was fixed, with the test that proves each one.
- What is still open, and which bucket it is in.
- Anything appended to `.claude/reminders.md`.
- The final baseline output, pasted, not summarised.

If the loop ends red, say it ends red. An honest red report is the point of
having the loop.
