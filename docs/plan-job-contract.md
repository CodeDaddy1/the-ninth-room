# Plan — the job contract

One structural cut, decided 2026-08-28. The decisions it rests on are in
`decisions-job-preconditions.md` and `decisions-beat-and-take-kind.md`; this
document is the work.

Branch `job-contract` in both repos.

## Order

**0. Prerequisite — consolidate dispatch.** Five runners hand-roll their own
`subprocess.Popen` to the `claude` CLI (`fixer` 376, `research` 731, `scout`
1079, `publish` 1155, `sourcing` 1880) instead of using `_dispatch` (1238) or
`_dispatch_json` (1458). Staging-and-promote must live in one place or it
misses five runners, two of which account for three Class B failures.

**1. The failing six first** — `editplan`, `sourcing`, `ingest`, `retention`,
`research`, `assemble`. All fourteen ledger failures are theirs. Convert,
measure against the scoreboard, then do the remaining nineteen.

**2. Free fix, independent of everything** — `validate_edit_plan` gains the
duplicate-id check every other id space in `schemas.py` already has
(chapters at 381; takes, broll, cards and overlays likewise). Beats are the
only id space without one.

**3. Kind onto the take** — derived at ingest from `file`, stored in
`takes.json`, backfilled for existing projects. Then the four prefix-sniffing
sites read the field.

**4. The Studio half** — doors drawn closed with the engine's reason; retry
on failed jobs; the `sfx_cues.json` key fix (it writes `beat` while
`sfx.cues_by_beat` reads `beat_id`, and no validator covers it).

## Retryable — PROPOSED, NOT VERIFIED

Inferred from docstrings and runner bodies on 2026-08-28. **Verifying each
row is the first task of step 1, not an assumption to build on.** Nothing
in the engine currently records this, which is why the table exists at all.

| kind | session? | retryable | why |
|---|---|---|---|
| survey | — | yes | re-derives from footage |
| ingest | — | yes | derived outputs overwrite |
| assemble | — | **no** | imports into Resolve |
| reproxy | — | yes | previews overwrite per beat |
| fixer | hand-rolled | **no** | mutates a built cut |
| story | `_dispatch_json` | yes | overwrites `stories.json` |
| research | hand-rolled | yes | overwrites `research.json` |
| interview | `_dispatch_json` | yes | overwrites `script_questions.json` |
| script | `_dispatch_json` | **caution** | rewrites lines; recordings key off `rev` |
| graphics | `_dispatch_json` | yes | overwrites `graphics_plan.json` |
| editplan | `_dispatch_json` | **no, by design** | refuses when a plan exists; P10 unblocks |
| scout | hand-rolled | yes | honours existing verdicts |
| render | — | **no** | expensive, external, via Resolve |
| snapcuts | — | **no** | a second run re-snaps snapped cuts |
| rendercards | — | yes | self-limiting to cards not current |
| publish | hand-rolled | **no** | outside world |
| retention | `_dispatch` | yes | guarded — refuses once review started |
| hook | `_dispatch` | yes | analysis only |
| qcgate | — | yes | measured checks, read-only |
| perf | `_dispatch` | yes | channel-level analysis |
| retro | `_dispatch` | yes | analysis |
| diagnose | both | yes | reads a failed job's log |
| room | `_dispatch_json` | **no** | reaps claims; stateful |
| coverage | `_dispatch_json` | **no** | a second run attaches more covers |
| sourcing | hand-rolled | **no** | appends rounds |

15 proposed retryable, 1 caution, 9 not. 25 kinds.

## Durability

launchd already restores the engine — `KeepAlive` true, 5s throttle, and
there are no crash reports. All three "engine restarted mid-job" failures
were manual restarts during development (two land minutes before a commit;
the engine has no auto-reloader). One, 2026-08-27 19:47, is unexplained.

So durability reduces to a **boot-time sweep**: find jobs left `running`,
re-queue the retryable ones, fail the rest with a clear reason. No new
supervision.

## Done when

- **`editplan` never again fails after 300 seconds of waiting.** Headline.
- Dead wall-clock across a comparable ledger approaches zero for Class A and
  Class B. `work/_jobs.json` as of 2026-08-28 is the frozen baseline: 50
  jobs, 14 failed (28%), 45.1 minutes burned — Class A 4, Class B 5
  (29.5 min), Class C 5 (15.7 min).

  **The ledger keeps only the last 50 jobs** (`jobs.py:7`), so running this
  work would have overwritten the baseline it is measured against. Frozen
  to `docs/baselines/jobs-2026-08-28.json` before any change.
- No job is offered that the engine would refuse in under a second.
- Every job kind declares retryable, and the UI offers retry only where true.
- Two beats cannot share an id.

## Verify

```
/usr/bin/python3 -m pytest tests/          # engine
npm run lint && npm test && npx tsc --noEmit && npm run build   # studio
```

Then, per `AGENTS.md`: load the desks in a browser against a real project.
A green suite is not a working feature — three defects in the footage
rebuild passed every test and were obvious on sight.

## Not in this

- **P10, beat identity.** Deliberately deferred; reasoning recorded in the
  2026-08-28 correction appended to
  `the-ninth-room-studio/docs/p10-beat-identity-spec.md`.
- **Cost preview before dispatch.** A consolation prize for a wait this cut
  removes.
- **Surfacing `recut_suggested`** (`editroom.py:2849`, computed and consumed
  by nothing). It belongs to P10 — a re-cut suggestion you cannot act on is
  worse than none.

---

## Done so far (2026-08-28)

Committed on `job-contract`, 917 engine tests green:

| | |
|---|---|
| beat ids | duplicate check `validate_edit_plan` never had |
| job history | append-only `work/_jobs.log`; the ring buffer was destroying its own evidence |
| dispatch | five hand-rolled `claude` launches collapsed onto `_dispatch`; `CLAUDE_BIN`; ratcheted |
| boot | timestamped, with pid, naming what the last run was holding |
| kind | stored on the take, 1,628 backfilled; revived **five** dead rules |
| picture beats | a beat may carry a spine instead of a take; b-roll can carry its own sound |

**Not started:** the predicate registry itself — steps 0 and 1 above. The
prerequisite (consolidate dispatch) is done, so step 1 is unblocked.
