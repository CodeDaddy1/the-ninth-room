# -*- coding: utf-8 -*-
"""A beat is named after the shot it shows.

Beat ids are invented free-hand by the LLM inside its session. The only
specification anywhere is the literal example `"id": "BT01"` in
`.claude/agents/story-designer.md`; the engine never mints one. The
shipped hmns plan's id sequence — BT01..BT05, BT70, BT71, BT08, BT09,
BT73, BT06, BT07, BT74, BT10... — is the fossil record of hand surgery,
new ids minted from a high-water mark. Ten artifacts key on a beat id
(review verdicts, captions, the baked captions/BT*.mov files and their
bake hashes, graphics cards, sfx cues, pending conform ops, trash,
proxies, the timeline map, music beds), so regenerating the cut does not
ORPHAN the old ids — it re-points about 76 of 82 of them at different
takes, and no read-time filter can detect it, because BT06 still exists
and still resolves. That is why `_run_editplan` refuses to re-cut, and
why the Studio's "Re-build the cut" button is a door that does not open.
The full trace, and its 2026-08-28 correction (a beat may have no take),
is the Studio repo's `docs/p10-beat-identity-spec.md` — read it before
changing a rule here.

The scheme: a beat's ANCHOR is its `take_id` when it carries one, else
its spine's `clip_id`. `validate_edit_plan` (schemas.py, the spine/take
branch) already guarantees a valid beat has one of the two, and the one
rule covers all four beat kinds — oncamera, vo and desk anchor on their
take, picture beats on their spine clip. Take ids (T\\d+) and b-roll ids
(B\\d+) are disjoint mint spaces, verified across all three live
projects (2026-08-28: 875 takes, 407 clips, zero nonconforming), so an
anchor can never be ambiguous. The id is `B-<anchor>` for an anchor's
first beat and `B-<anchor>-<n>` from the second beat on — and occurrence
is genuinely load-bearing: hmns repeats 11 take ids across beats, T92
five times. NOT the spec's original `T341#2` spelling: `#` is the URL
fragment separator and the engine serves proxies over HTTP, so an id
with `#` in it could never name its own proxy in a URL.

The invariant that kills mis-binding STRUCTURALLY rather than by
convention: every id parses, is unique in its plan, and its anchor part
equals the beat's actual anchor. An id can never point at a different
shot than it names — a regeneration can strand history, loudly, but it
can no longer silently re-home it.

Pure identity functions only. Nothing here reads a file, writes an
artifact, or migrates anything — the runner that will own promotion
(the job-contract cut) is where these get wired, later and separately.
"""
import copy
import re

# derive_ids stamps this; id_errors gates on it. Legacy plans carry no
# marker, so the checker can tell "predates the scheme" from "violates
# it" without guessing from what the ids happen to look like.
ID_SCHEME = "anchor-v1"

# The derived shape. Legacy ids are BT\d+, which this cannot match, so a
# mixed state is detectable rather than plausible. The occurrence suffix
# is emitted only from 2 up (the first beat is bare) — parse_id refuses
# a spelled-out "-1" and format_id cannot emit one, because "B-T92-1"
# would be a second name for the beat "B-T92" already names, and two
# spellings of one identity is the disease this module exists to cure.
ID_RE = re.compile(r"^B-(T\d+|B\d+)(?:-([1-9]\d*))?$")

# What a take id or a b-roll clip id looks like — the two mint spaces,
# disjoint by construction (takes.py mints T01.., broll B001..).
ANCHOR_RE = re.compile(r"^(?:T\d+|B\d+)$")

# Two cuts whose boundaries both moved less than this are the same cut.
# validate_edit_plan already grants trim bounds 0.01s of slack, and
# 0.05s is a frame and a half at 30fps — under anything a verdict could
# have been about. Wider and a real re-trim would smuggle an approval
# onto a cut nobody has watched.
CARRY_TRIM_EPS = 0.05


def anchor(beat: "dict | None") -> "str | None":
    """The shot this beat shows: its take if present, else its spine
    clip; None when it has neither.

    `validate_edit_plan` guarantees a valid beat carries one of the two
    (schemas.py, the branch above `_validate_spine`: a spine is only
    read when `take_id` is absent, so a beat holding both anchors on
    its take). None therefore means the beat is invalid under the
    schema, not that identity needs a third rule.
    """
    if not isinstance(beat, dict):
        return None
    tid = beat.get("take_id")
    if isinstance(tid, str) and tid:
        return tid
    spine = beat.get("spine")
    if isinstance(spine, dict):
        cid = spine.get("clip_id")
        if isinstance(cid, str) and cid:
            return cid
    return None


def parse_id(bid: "str | None") -> "tuple[str, int] | None":
    """The (anchor, occurrence) a derived id names, or None.

    Occurrence is 1 when the id is bare. A spelled-out "-1" returns
    None even though the intent is guessable: format_id can never emit
    it, so accepting it would let one identity carry two names — which
    is mis-binding with extra steps. Legacy BT ids return None; that is
    how a mixed state stays visible.
    """
    if not isinstance(bid, str):
        return None
    m = ID_RE.match(bid)
    if not m:
        return None
    if m.group(2) is None:
        return (m.group(1), 1)
    n = int(m.group(2))
    if n < 2:
        return None
    return (m.group(1), n)


def format_id(anchor_id: str, occurrence: int = 1) -> str:
    """The one spelling of (anchor, occurrence).

    Raises ValueError rather than emit an id parse_id would refuse — a
    formatter that can produce an unparseable name moves the invariant
    from structure back to hope.
    """
    if not ANCHOR_RE.match(str(anchor_id or "")):
        raise ValueError("anchor %r is neither a take id nor a b-roll "
                         "clip id — a beat is named after a real shot"
                         % (anchor_id,))
    n = int(occurrence)
    if n < 1:
        raise ValueError("occurrence %d — an anchor's first beat is "
                         "occurrence 1" % n)
    if n == 1:
        return "B-%s" % anchor_id
    return "B-%s-%d" % (anchor_id, n)


def derive_ids(plan: "dict") -> "dict":
    """A NEW plan (deep copy) with every beat id rewritten from its
    anchor in beat order — first occurrence bare, then -2, -3 — plus
    the `id_scheme` marker so id_errors knows the plan opted in. Never
    mutates its argument.

    A beat with no anchor keeps whatever id it had: it has no identity
    under this scheme, and id_errors names it out loud. Inventing an id
    here would silently paper over exactly the beat the spec's
    2026-08-28 correction was about.

    RAISES ValueError when a beat's anchor is a non-empty string that is
    neither a take id nor a b-roll clip id. That is deliberate and it is
    the one input this function refuses rather than reports. It runs at
    the promote seam, on a plan a session just wrote: an anchor like
    "X99" means the agent named a shot that does not exist, and the
    honest answer is to fail the job with the anchor in the message
    rather than mint an id that resolves to nothing. validate_edit_plan
    rejects the same plan a moment earlier ("unknown take"), so the
    live path never reaches this — it is the backstop for the day the
    order of those two checks changes. The deep copy is taken first, so
    a raise leaves the caller's plan untouched.
    """
    out = copy.deepcopy(plan) if isinstance(plan, dict) else {}
    seen = {}  # type: dict
    for b in out.get("beats", []) or []:
        if not isinstance(b, dict):
            continue
        a = anchor(b)
        if a is None:
            continue
        seen[a] = seen.get(a, 0) + 1
        b["id"] = format_id(a, seen[a])
    out["id_scheme"] = ID_SCHEME
    return out


def mint_id(anchor_id: str, existing_ids: "list[str] | set | tuple") -> str:
    """The id for ONE later beat of this anchor — a swap, an insert, a
    restore — against the ids already in the plan.

    Lowest unused suffix, because existing beats never renumber: a
    removal leaves a hole and the next mint fills it. Reuse is safe
    HERE and was not under the BT scheme — the hole and its filler name
    the same shot by construction, so an artifact keyed on the reused
    id re-attaches to footage identical to what it described, where a
    reused BT id re-pointed history at a stranger. Legacy BT ids in
    `existing_ids` occupy a disjoint space and are ignored.
    """
    taken = set()
    for bid in existing_ids or ():
        parsed = parse_id(bid)
        if parsed is not None and parsed[0] == anchor_id:
            taken.add(parsed[1])
    n = 1
    while n in taken:
        n += 1
    return format_id(anchor_id, n)


def id_errors(plan: "dict") -> "list[str]":
    """The invariant, checked: on a plan marked `anchor-v1`, every beat
    id parses, is unique, and names the beat's actual anchor. Empty on
    a conforming plan.

    Returns [] immediately when the marker is absent or different — the
    same reasoning that keeps coverage_notes advisory: every plan
    shipped before the scheme is legacy by definition, and a checker
    that bricked hmns's surgery writes over ids it was never given
    would punish the archive for predating the rule. The gate is the
    MARKER, not what the ids look like, because a mixed state inside a
    marked plan (one BT survivor after a bad merge) is exactly what
    this must catch.

    Occurrence gaps are legal: B-T92-3 without B-T92-2 is the trace of
    a removal, and renumbering survivors is the disease, not the cure.
    """
    if not isinstance(plan, dict) or plan.get("id_scheme") != ID_SCHEME:
        return []
    errors = []  # type: list
    seen = set()  # type: set
    for i, b in enumerate(plan.get("beats", []) or []):
        where = "beats[%d]" % i
        if not isinstance(b, dict):
            errors.append("%s: not an object — nothing to name" % where)
            continue
        bid = b.get("id")
        a = anchor(b)
        parsed = parse_id(bid)
        if parsed is None:
            errors.append("%s: id %r does not parse — a marked plan "
                          "names every beat B-<shot>" % (where, bid))
        elif a is not None and parsed[0] != a:
            errors.append("%s: id '%s' names %s but the beat shows %s "
                          "— an id may never point at a different shot "
                          "than it names" % (where, bid, parsed[0], a))
        if a is None:
            errors.append("%s: no take and no spine — a beat with no "
                          "shot has no identity" % where)
        if isinstance(bid, str):
            if bid in seen:
                errors.append("%s: duplicate id '%s' — two beats "
                              "cannot share a name" % (where, bid))
            seen.add(bid)
    return errors


def _keyed(plan: "dict") -> "tuple[dict, list]":
    """{(anchor, positional occurrence): beat id} plus the walk order.
    Positional means the Nth beat SHOWING a shot, counted in beat
    order — computed the same way on both sides of a mapping, so it
    works whether a plan's ids are legacy BT or derived."""
    seen = {}  # type: dict
    keys = {}  # type: dict
    order = []  # type: list
    # `plan or {}` passed a truthy non-dict straight to .get and crashed
    # (verification fuzz, 2026-08-28) — guard like every public sibling.
    beats = plan.get("beats", []) if isinstance(plan, dict) else []
    for b in beats or []:
        if not isinstance(b, dict):
            continue
        bid = b.get("id")
        if not isinstance(bid, str):
            continue
        a = anchor(b)
        if a is None:
            order.append((None, bid))
            continue
        seen[a] = seen.get(a, 0) + 1
        keys[(a, seen[a])] = bid
        order.append(((a, seen[a]), bid))
    return keys, order


def id_map(old_plan: "dict", new_plan: "dict") -> "dict":
    """{old beat id: new beat id} across a regeneration, matched by
    (anchor, occurrence) so a beat that kept its shot keeps its
    history. Returns {"map", "unmatched_old", "unmatched_new"} — the
    unmatched are NAMED on both sides, never dropped: an unmatched old
    id is a beat the new cut dropped (its review entry will strand),
    an unmatched new id is a beat with no history to inherit.

    Occurrence is positional on BOTH plans — the Nth beat showing a
    shot matches the Nth beat showing it — rather than parsed out of
    the ids, because a legacy plan's ids encode nothing and the whole
    point is that history follows the SHOT, not the slot.
    """
    old_keys, old_order = _keyed(old_plan)
    new_keys, new_order = _keyed(new_plan)
    mapping = {}  # type: dict
    unmatched_old = []  # type: list
    for key, bid in old_order:
        if key is not None and key in new_keys:
            mapping[bid] = new_keys[key]
        else:
            unmatched_old.append(bid)
    matched_new = set(mapping.values())
    unmatched_new = [bid for _key, bid in new_order
                     if bid not in matched_new]
    return {"map": mapping,
            "unmatched_old": unmatched_old,
            "unmatched_new": unmatched_new}


def _span(beat: "dict | None") -> "tuple | None":
    """The cut a beat shows: its trim, else its spine's src window —
    the same fact in a take beat's and a picture beat's spelling
    (houston's 29 spine beats carry src_s/src_e and no trim)."""
    if not isinstance(beat, dict):
        return None
    trim = beat.get("trim")
    if isinstance(trim, dict) and "s" in trim and "e" in trim:
        try:
            return (float(trim["s"]), float(trim["e"]))
        except (TypeError, ValueError):
            return None
    spine = beat.get("spine")
    if isinstance(spine, dict):
        try:
            return (float(spine.get("src_s", 0.0)),
                    float(spine.get("src_e", 0.0)))
        except (TypeError, ValueError):
            return None
    return None


def _spans(plan: "dict") -> "dict":
    """{beat id: span} for every identifiable beat in a plan."""
    out = {}  # type: dict
    beats = plan.get("beats", []) if isinstance(plan, dict) else []
    for b in beats or []:
        if isinstance(b, dict) and isinstance(b.get("id"), str):
            out[b["id"]] = _span(b)
    return out


def _same_cut(a: "tuple | None", b: "tuple | None") -> bool:
    """Both boundaries moved less than CARRY_TRIM_EPS. Two absent
    spans are the same cut (an untrimmed beat regenerated untrimmed);
    an absent span against a present one is a change — the cut gained
    or lost a boundary nobody reviewed."""
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    return (abs(a[0] - b[0]) <= CARRY_TRIM_EPS
            and abs(a[1] - b[1]) <= CARRY_TRIM_EPS)


def carry_review(old_review: "dict", mapping: "dict",
                 old_plan: "dict", new_plan: "dict") -> "dict":
    """Where each review entry lands after a regeneration. Pure: takes
    dicts, returns dicts, writes nothing — the runner that owns
    promotion applies the result.

    Three fates, none silent:

      carried  — the beat kept its shot and its cut moved less than
                 CARRY_TRIM_EPS: verdict and note carry unchanged,
                 keyed by the new id.
      requeued — the beat kept its shot but the cut moved: the NOTE
                 carries (the reviewer's words may still apply — gate
                 F11 found deleting them destroyed irrecoverable text)
                 and the status is cleared, back in the queue —
                 exactly what _reset_review does when _beat_swap
                 changes what a verdict was looking at. Listed only
                 when a status was actually cleared; an entry that was
                 already queued just carries.
      stranded — the old id maps to nothing: the entry is returned
                 whole, under its old id, text intact. hmns's
                 review.json already holds 14 ghosts against 82 live
                 beats; the rule is that a strand is always NAMED.

    `mapping` is id_map's return value, or a bare {old: new} dict.
    Timestamps are left alone — this function takes no clock, and a
    carried entry's `ts` is the review's own history, not this run's.
    """
    pairs = mapping.get("map", mapping) if isinstance(mapping, dict) else {}
    old_spans = _spans(old_plan)
    new_spans = _spans(new_plan)
    carried = {}  # type: dict
    requeued = []  # type: list
    stranded = []  # type: list
    for old_id, entry in (old_review or {}).items():
        new_id = pairs.get(old_id)
        if new_id is None:
            stranded.append({"id": old_id,
                             "entry": copy.deepcopy(entry)})
            continue
        kept = copy.deepcopy(entry)
        if _same_cut(old_spans.get(old_id), new_spans.get(new_id)):
            carried[new_id] = kept
            continue
        had_status = isinstance(kept, dict) and "status" in kept
        if isinstance(kept, dict):
            kept.pop("status", None)
        carried[new_id] = kept
        if had_status:
            requeued.append(new_id)
    return {"carried": carried, "requeued": requeued,
            "stranded": stranded}
