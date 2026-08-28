# Kind is a stored field on the take, not a prefix on the filename

**Decided 2026-08-28 by Caleb,** in a design interview, against measured
evidence from the engine and the live projects.

## The concept already exists — it just does not travel

`SECTION_KINDS = ("oncamera", "vo", "desk")` (`schemas.py:862`) is a
validated field on a script section. The engine already knows what a line
IS. That knowledge stops at the script: nothing carries it onto the take
that gets recorded, or onto the beat that gets cut. So four independent
rules re-derive it downstream by looking at a filename prefix.

They do not agree.

| | what it tests | correct? |
|---|---|---|
| `captions.vo_beats_of` (`captions.py:58`) | `take_id.startswith("vo_")` | **no** — dead branch |
| `validate_edit_plan` (`schemas.py:479`) | the take's `file` startswith `vo_` | yes |
| coverage exemption (`schemas.py:221`) | `take_id.startswith("vo_")` | **no** — dead branch |
| `gear_change` (`schemas.py:363`) | `take_id.startswith("vo_")` | **no** — dead branch |
| `recut_suggested` (`editroom.py:2858`) | files matching `vo_*`, `desk_*` | yes |

Take ids are minted `"T%02d" % (len(takes) + 1)` (`takes.py:312`) — `T01`,
`T02`, and so on. **No take id can ever start with `vo_`.** The prefix lives
on `file`, which is the sibling field. So two of the four rules test a
condition that is never true, and `captions.py:55` says of itself *"One
definition, used by every caller"* while being one of the dead ones.

Measured consequence, not reasoned: a dry run of the `golf-testing` design
returns `validate_edit_plan` VALID and `coverage_notes` with ten entries —
"covers the landing" and "100% covered" on each of its five VO beats, the
exact two rules a VO beat is supposed to be exempt from. `jobs.py:1611`
fails the coverage job on any entry, so **every VO-led episode is blocked at
that gate.**

## What was compared

| | A — kind on the beat | B — kind on the take | C — one shared helper |
|---|---|---|---|
| where the fact lives | written at plan time | derived at ingest, stored | still the filename |
| who knows it first | the story designer | the ingest that made the file | nobody; re-derived forever |
| duplicates a known fact | yes — the take already knows | no | no |
| survives a beat with no take | yes | yes, as `picture` | yes |
| drift possible | plan vs take can disagree | no second copy | one place, but still parsing |

**B.** A take's nature is knowable the moment it is ingested, and a beat's
nature is a consequence of what it points at. A stores the same fact twice,
which is the mechanism that produced the bug above. C keeps a filename as a
load-bearing data structure.

## What this decides

- **A take carries `kind`,** derived once at ingest from its file and stored
  in `takes.json`. Values are the existing `SECTION_KINDS`.
- **A beat's kind is its take's kind, or `picture` when it has no take.** A
  beat may legitimately have no take (Caleb, 2026-08-28) — a stretch of pure
  picture with no line under it is a real shape, not an edge case.
- **Nothing sniffs a prefix at read time again.** All five sites above read
  the field, enforced by a ratchet (`tests/test_kind_has_one_home.py`).

## What this reverses

`schemas.py:787` records a decision from 2026-08-24: `vo` and `desk` get
different filename prefixes *rather than one flag*, because "four
independent rules key off a `vo_` prefix, and a desk recording landing on
the wrong side of them would be forbidden from ever appearing on screen."

That reasoning was sound and its premise is now gone. It accepted
prefix-sniffing as fixed and worked around it by adding a second prefix. The
bug above is the proof it could not hold: the rules key off `take_id`, the
prefix lives on `file`, and no amount of prefix discipline could reconcile
them. Once kind is a stored field, `desk_` stops being load-bearing and
becomes just a filename.

**Do not re-introduce a prefix check to "make it obvious".** It was obvious.
It was also wrong for an unknown number of episodes.

## Consequences

- `takes.json` gains a field; existing projects need it backfilled. The
  backfill is derivable from `file`, so it is a one-shot pass, not a
  judgement call.
- P10 (beat identity) gains a four-case model to derive against instead of
  the three-case assumption it was written on. Its proposed rule —
  `take_id` + occurrence — cannot stand as written, because `picture` beats
  have no take. See the 2026-08-28 correction appended to
  `the-ninth-room-studio/docs/p10-beat-identity-spec.md`.
- The unreachable branches become reachable. Expect VO-led episodes to
  behave differently at the coverage gate for the first time — that is the
  fix, but it is also the first time those rules will have actually run.

## What the implementation found (2026-08-28)

**There were five sites, not four.** `gear_change` (`schemas.py:363`) was
dead the same way. Its docstring reasons from the broken measurement — "0 VO
beats … every cut we have ever made runs ONE texture end to end" — and
declines to set a threshold because of it. That conclusion happens to be
true (every take in every project is `oncamera` except oligarchy's two, and
oligarchy has no plan), but it could never have changed.

**The tests were dead with the code.** Three asserted the exemption worked
using `take_id="vo_CH1-S1_r1_t1"` — an id that cannot exist, since
`takes.py:312` mints them `T01`, `T02`. The test and the unreachable branch
agreed with each other, which is why a year of green suites never surfaced
it. That is the failure mode to watch for elsewhere: a fixture proving a
rule with data the system never produces.

**Verified against real takes**, not fixtures. A VO beat covered 95% end to
end, pointed at oligarchy's real `T01` (`vo_CH1-S1_r1_t1.mp4`): before, two
notes — "covers the landing" and "95% covered"; after, none. The same beat
pointed at a filmed take still gets both.

**Found here, fixed separately:** "a beat may have no take" turned out to be
*forbidden by the schema* rather than unimplemented — `validate_edit_plan`
required `take_id` to be a str, and `golf-testing` carries `take_id: null`
on all eleven beats. That, and the natural-sound gap beside it, are settled
in `decisions-picture-beats.md`.

What no code change clears: `golf-testing`'s five narrated sections are
unrecorded. That project is being deleted; the shapes it exposed are not.
