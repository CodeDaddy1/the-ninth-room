# -*- coding: utf-8 -*-
"""Rename a project's beats onto the current id scheme, reversibly.

A beat id is a free-hand string the session invented, and eight artifacts
key on it. `beat_identity` can derive a stable id from the SHOT a beat
shows, which is the fix — but deriving it is only half the job. The other
half is that every artifact holding the old spelling has to move with it
in the same breath, or the rename silently unbinds Caleb's review
history, his cards, his cue sheet and his conform queue from the beats
they describe.

WHAT THIS IS CAREFUL ABOUT, and why:

  * A DRY RUN CHANGES NOTHING. It is the default. `--apply` is a
    deliberate second run, after reading what the first one printed.
  * IT RUNS MORE THAN ONCE. It was written for one hop, and the second
    one (anchor-v1 -> shot-v1, 2026-09-08) found four places where a
    re-run quietly destroyed the first run's record: the backup
    directory refused to overwrite and so backed up NOTHING while
    logging a count, the id map was replaced rather than extended, the
    caption link pass would have spawned a THIRD name set, and the
    review archive was written whole. Every one of them looked like a
    success in the log.
  * Captions are HARDLINKED to their new names. A name a PERSON wrote
    is never touched: hmns's shipped Resolve timeline holds absolute
    paths to `captions/BT01.mov`, and moving it takes that timeline
    offline until every clip is relinked. A name THIS TOOL minted on an
    earlier run is unlinked once the new one exists, because otherwise
    each migration leaves another 80 names on the same 80 inodes and
    the directory stops being readable. The one case that would break:
    a conform push between two migrations, which would leave Resolve
    holding a minted name. `conform_status.json` is the ledger to check
    when that day comes, and the dry run prints every name it will
    remove.
  * The bake cache is re-keyed, not discarded. `_caption_key` is
    content-only — words, duration, canvas, CAPTIONS_V, no beat id — so
    the same caption under a new key is still a cache HIT, and 9.3 GB of
    ProRes survives a rename that would otherwise re-bake for 84 minutes.
  * Proxies are deleted rather than renamed. Their filename carries a
    spec hash, they are 38 MB, and re-rendering them is a job.
  * A review entry with nowhere to go is ARCHIVED AND NAMED, never
    dropped. hmns carries 96 entries against 82 beats: fourteen ghosts
    that predate some earlier surgery, and they hold Caleb's notes.

Not a bug, despite appearances: `sfx_cues.json` keys on `beat` while
`sfx.cues_by_beat` reads `beat_id`. Those are two different artifacts on
purpose (`sfx.py`) — the sound-designer's advisory prose cue sheet and
the desk's real placements in `sound_cues.json`. Both are remapped, each
under its own key.

Run:
    /usr/bin/python3 -m pipeline.cli migrate-beat-ids <slug>
    /usr/bin/python3 -m pipeline.cli migrate-beat-ids <slug> --apply
"""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

from .ingest import work_path, analysis_dir
from . import beat_identity, plan_history, schemas

BACKUP_DIRNAME = "_premigration"
MAP_FILE = "beat_id_map.json"
REPORT_FILE = "beat_id_migration.json"
ARCHIVE_FILE = plan_history.REVIEW_ARCHIVE


def backup_dir(work: Path) -> Path:
    """The directory THIS run backs up into: `_premigration`, then
    `_premigration.v2`, `.v3`...

    The copy loop refuses to overwrite an existing backup, which is
    right — an older pre-migration state is more valuable than a newer
    one. But with a fixed directory name that made the second migration
    back up nothing at all while still logging "backed up 11
    artifacts", so the only way back from hop two was the APFS clone
    Caleb happened to take by hand.
    """
    d = work / BACKUP_DIRNAME
    if not d.exists():
        return d
    n = 2
    while (work / ("%s.v%d" % (BACKUP_DIRNAME, n))).exists():
        n += 1
    return work / ("%s.v%d" % (BACKUP_DIRNAME, n))


def resolve_id(doc: "dict | None", bid: str) -> str:
    """The name a beat carries TODAY, given any name it has ever had.

    This is why the map file keeps every generation instead of the last
    one. `BT01` is not a historical curiosity: it is what the shipped
    Resolve timeline speaks, what the baked `captions/BT01.mov` is
    called, and what Caleb types when he goes looking for a clip. After
    two hops a single-generation map cannot answer him at all — it only
    knows `B-T362 -> shot-T362`, and `BT01` looks like a stranger.

    An id that is already current, or that no generation mentions,
    comes back unchanged.
    """
    cur = str(bid)
    for gen in generations(doc):
        m = gen.get("map") or {}
        if cur in m:
            cur = m[cur]
    return cur


def generations(doc: "dict | None") -> "list":
    """Every hop the map records, oldest first. A map written before
    generations existed is folded in as hop one, read off its own
    `scheme`/`map` — the file is the audit trail, so it has to be able
    to describe its own past."""
    if not isinstance(doc, dict):
        return []
    gens = [g for g in (doc.get("generations") or []) if isinstance(g, dict)]
    if gens:
        return gens
    if isinstance(doc.get("map"), dict) and doc["map"]:
        return [{"scheme": doc.get("scheme"), "map": doc["map"]}]
    return []

# (path relative to work/, how the beat id is stored). `where` is
# "keys" for a dict keyed by beat id, otherwise (list field, id field).
ARTIFACTS = (
    ("review.json", "keys", None),
    ("captions.json", "beats", "beat_id"),
    ("graphics_plan.json", "cards", "beat_id"),
    ("analysis/timeline_map.json", "beats", "id"),
    ("sfx_cues.json", "cues", "beat"),          # the agent's prose sheet
    ("sound_cues.json", "cues", "beat_id"),     # the desk's placements
    ("trash.json", "entries", "beat_id"),
    ("pending_conform.json", "ops", "beat_id"),
    # The conform LEDGER, not a snapshot: the Studio reads it to show what
    # the last push to Resolve did, per beat. Found by the sandbox run.
    ("conform_status.json", "ops", "beat_id"),
)


class MigrationError(Exception):
    pass


def _read(p: Path):
    try:
        return json.loads(p.read_text())
    except (OSError, ValueError):
        return None


def _counts(work: Path, mapping: "dict") -> "list":
    """What each artifact would have rewritten, without touching one."""
    rows = []
    for rel, field, key in ARTIFACTS:
        p = work / rel
        if not p.exists():
            rows.append({"artifact": rel, "present": False,
                         "rows": 0, "remapped": 0, "stranded": 0})
            continue
        doc = _read(p)
        if doc is None:
            rows.append({"artifact": rel, "present": True, "unreadable": True,
                         "rows": 0, "remapped": 0, "stranded": 0})
            continue
        if field == "keys":
            ids = list(doc) if isinstance(doc, dict) else []
        else:
            ids = [r.get(key) for r in (doc.get(field) or [])
                   if isinstance(r, dict)]
        hit = [i for i in ids if i in mapping]
        rows.append({"artifact": rel, "present": True, "rows": len(ids),
                     "remapped": len(hit),
                     "stranded": len([i for i in ids if i not in mapping])})
    return rows


def _map_doc(prev: "dict | None", slug: str, mapping: "dict") -> "dict":
    """The map file after this hop: every generation kept, newest last.

    Written whole until 2026-09-08, which made `BT01 -> B-T362 ->
    shot-T362` unreconstructable after the second hop — and `BT01` is
    the name the shipped Resolve timeline and the baked caption movs
    still carry. `map` stays the LATEST hop so existing readers see what
    they always saw.
    """
    gens = list(generations(prev))
    gens.append({"scheme": beat_identity.ID_SCHEME, "map": mapping})
    return {"slug": slug, "scheme": beat_identity.ID_SCHEME,
            "map": mapping, "generations": gens}


def _plan_paths(slug: str) -> "tuple":
    work = work_path(slug)
    return work, work / "edit_plan.json"


def survey(slug: str) -> "dict":
    """Everything `apply` would do, computed and nothing written."""
    work, plan_path = _plan_paths(slug)
    if not plan_path.exists():
        raise MigrationError("%s has no edit_plan.json — nothing to migrate"
                             % slug)
    old = _read(plan_path)
    if old is None:
        raise MigrationError("%s: edit_plan.json is unreadable" % slug)
    if old.get("id_scheme") == beat_identity.ID_SCHEME:
        raise MigrationError(
            "%s is already on %s — migrating twice would rename beats that "
            "are already named after their shot"
            % (slug, beat_identity.ID_SCHEME))

    new = beat_identity.derive_ids(old)
    errs = beat_identity.id_errors(new)
    if errs:
        raise MigrationError("the derived ids do not hold: %s" % errs[0])

    m = beat_identity.id_map(old, new)
    mapping = m["map"]

    review = _read(work / "review.json") or {}
    carried = beat_identity.carry_review(review, mapping, old, new)

    cap_dir = work / "captions"
    caps = sorted(cap_dir.glob("*.mov")) if cap_dir.is_dir() else []
    cap_moves = [(f.name, "%s.mov" % mapping[f.stem])
                 for f in caps if f.stem in mapping]
    # WHICH OLD NAMES MAY GO. A name this tool minted on an earlier hop
    # is ours to remove once the new one exists; a name a session wrote
    # by hand is not, because that is what the shipped Resolve timeline
    # holds. The plan's `id_scheme` marker is exactly that distinction:
    # `derive_ids` is the only thing that sets it. Without this, hop two
    # leaves 240 names on 80 inodes and hop three leaves 320.
    minted = bool(old.get("id_scheme"))
    cap_unlink = [o for o, _n in cap_moves] if minted else []

    proxies = beat_identity.beat_proxies(work / "proxies")

    return {
        "slug": slug,
        "beats": len(new.get("beats") or []),
        "mapping": mapping,
        "unmatched_old": m.get("unmatched_old") or [],
        "unmatched_new": m.get("unmatched_new") or [],
        "artifacts": _counts(work, mapping),
        "review": {"entries": len(review),
                   "carried": len(carried["carried"]),
                   "requeued": len(carried["requeued"]),
                   "stranded": [s["id"] for s in carried["stranded"]]},
        "captions": {"movs": len(caps), "hardlinks": len(cap_moves),
                     "unlink": len(cap_unlink)},
        "from_scheme": old.get("id_scheme"),
        "to_scheme": beat_identity.ID_SCHEME,
        "proxies_to_delete": len(proxies),
        "new_plan": new,
        "old_plan": old,
        "carried_review": carried,
        "caption_moves": cap_moves,
        "caption_unlink": cap_unlink,
    }


def _remap_doc(doc, field, key, mapping):
    """Returns (doc, remapped, stranded). Never drops an unmapped row."""
    remapped = stranded = 0
    if field == "keys":
        if not isinstance(doc, dict):
            return doc, 0, 0
        out = {}
        for k, v in doc.items():
            if k in mapping:
                out[mapping[k]] = v
                remapped += 1
            else:
                out[k] = v
                stranded += 1
        return out, remapped, stranded
    for row in (doc.get(field) or []):
        if not isinstance(row, dict):
            continue
        cur = row.get(key)
        if cur in mapping:
            row[key] = mapping[cur]
            remapped += 1
        elif cur is not None:
            stranded += 1
    return doc, remapped, stranded


def apply(slug: str, log=print) -> "dict":
    """Do it. Ordered so nothing is destroyed before it is copied."""
    s = survey(slug)
    work, plan_path = _plan_paths(slug)
    mapping = s["mapping"]

    # 1. history first — the archive is the way back
    row = plan_history.archive(slug, reason="migration",
                               note="beat ids -> %s" % beat_identity.ID_SCHEME)
    log("[migrate] archived the current cut as v%d" % (row or {}).get("v", 0))

    # 2. verbatim backups of every artifact this touches
    bdir = backup_dir(work)
    bdir.mkdir(parents=True, exist_ok=True)
    for rel, _f, _k in ARTIFACTS + (("edit_plan.json", None, None),):
        src = work / rel
        if src.exists():
            dest = bdir / rel.replace("/", "__")
            if not dest.exists():          # never overwrite an older backup
                shutil.copy2(str(src), str(dest))
    log("[migrate] backed up %d artifacts to %s/"
        % (len(list(bdir.iterdir())), bdir.name))

    # 3. the plan itself
    _write(plan_path, s["new_plan"])
    _write(work / MAP_FILE,
           _map_doc(_read(work / MAP_FILE), slug, mapping))
    log("[migrate] %d beats renamed" % len(mapping))

    # 4. review: carried entries replace the file, ghosts are archived
    carried = s["carried_review"]
    if (work / "review.json").exists():
        _write(work / "review.json", carried["carried"])
        if carried["stranded"]:
            plan_history.archive_review(
                slug, "beat-id migration -> %s" % beat_identity.ID_SCHEME,
                carried["stranded"])
            log("[migrate] %d review entries had no beat left and were "
                "archived: %s" % (len(carried["stranded"]),
                                  ", ".join(x["id"]
                                            for x in carried["stranded"])))

    # 5. the rest of the artifacts
    for rel, field, key in ARTIFACTS:
        if rel == "review.json":
            continue                        # handled above, with its ghosts
        p = work / rel
        doc = _read(p) if p.exists() else None
        if doc is None:
            continue
        doc, n, strand = _remap_doc(doc, field, key, mapping)
        _write(p, doc)
        log("[migrate] %-28s %d remapped%s"
            % (rel, n, ", %d left alone" % strand if strand else ""))

    # 6. captions: HARDLINK to the new name. A hand-written name stays
    #    (Resolve holds absolute paths to it); a name an earlier hop of
    #    this tool minted goes, once its replacement exists, so the
    #    directory does not gain a whole name set per migration.
    remove = set(s["caption_unlink"])
    linked = unlinked = 0
    for old_name, new_name in s["caption_moves"]:
        src, dest = work / "captions" / old_name, work / "captions" / new_name
        if src.exists() and not dest.exists():
            os.link(str(src), str(dest))
            linked += 1
        # ORDER MATTERS: the new name has to exist before the old one
        # goes, and `dest.exists()` is checked again rather than
        # assumed, because a link that failed must not take the file.
        if old_name in remove and src.exists() and dest.exists():
            src.unlink()
            unlinked += 1
    hp = work / "captions" / ".bake_hashes.json"
    hashes = _read(hp)
    if isinstance(hashes, dict):
        _write(hp, {mapping.get(k, k): v for k, v in hashes.items()})
    log("[migrate] %d caption movs hardlinked to their new names%s"
        % (linked, ", %d minted names removed" % unlinked if unlinked
           else " (the old names stay — Resolve holds absolute paths)"))

    # 7. proxies: delete, re-render as a job
    gone = 0
    for f in beat_identity.beat_proxies(work / "proxies"):
        f.unlink()
        gone += 1
    log("[migrate] %d proxies deleted — re-render with `proxy %s`"
        % (gone, slug))

    report = {k: v for k, v in s.items()
              if k not in ("new_plan", "old_plan", "carried_review")}
    report["applied"] = True
    report["backup_dir"] = bdir.name
    report["captions_linked"] = linked
    report["captions_unlinked"] = unlinked
    report["proxies_deleted"] = gone
    _write(work / REPORT_FILE, report)
    return report


def _write(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".%d.tmp" % os.getpid())
    try:
        tmp.write_text(json.dumps(data, indent=2))
        os.replace(str(tmp), str(path))
    except BaseException:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise


def print_survey(s: "dict", log=print) -> None:
    log("")
    log("  %s — %d beats" % (s["slug"], s["beats"]))
    log("  %-28s %s" % ("artifact", "rows  remapped  left alone"))
    for r in s["artifacts"]:
        if not r["present"]:
            log("  %-28s (absent)" % r["artifact"])
            continue
        log("  %-28s %4d  %8d  %10d"
            % (r["artifact"], r["rows"], r["remapped"], r["stranded"]))
    rv = s["review"]
    log("  review: %d entries -> %d carried, %d requeued, %d stranded"
        % (rv["entries"], rv["carried"], rv["requeued"], len(rv["stranded"])))
    if rv["stranded"]:
        log("    stranded (archived, not dropped): %s"
            % ", ".join(rv["stranded"]))
    log("  captions: %d movs, %d hardlinks to add, %d old names removed"
        % (s["captions"]["movs"], s["captions"]["hardlinks"],
           s["captions"]["unlink"]))
    if s.get("caption_unlink"):
        log("    removed (this tool minted them on an earlier hop): %s"
            % ", ".join(s["caption_unlink"][:6])
            + (" ..." if len(s["caption_unlink"]) > 6 else ""))
    log("  proxies to delete: %d" % s["proxies_to_delete"])
    if s["unmatched_old"]:
        log("  beats the new plan has no home for: %s"
            % ", ".join(s["unmatched_old"]))
    log("")
