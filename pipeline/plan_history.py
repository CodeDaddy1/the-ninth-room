# -*- coding: utf-8 -*-
"""Every cut this project has had, kept.

`_write_edit_plan` overwrites. There is no versioning anywhere, and
`work/_archive/` has been empty since it was created — the only history
that exists on disk is a handful of hand-made copies with names like
`edit_plan_v2_rejected.json` and `edit_plan_presnap.json`, which is what
a person does when the system does not do it for them.

That is survivable while the cut is written once. It stops being
survivable the moment a re-cut exists: "rebuild the cut and screen it
against the old one" is the whole point of the benchmark, and it needs
the old one to still be somewhere. The re-cut's verdict carry needs it
too — carrying a verdict means diffing this plan against its predecessor,
and a predecessor that was overwritten cannot be diffed.

NOT git. `work/` is gitignored and holds 81 GB of binaries for hmns
alone; committing edit plans would mean either un-ignoring a tree full of
ProRes or a second repo nobody would remember to use.

Append-only, and the version number is read from the FILES, never from
the manifest. A manifest that fails to parse degrades to "no history"
rather than raising — the same choice `broll.read_manual` makes, for the
same reason: a corrupt sidecar must not take the desk down with it. But
if numbering trusted that empty result it would hand out v1 again and
overwrite the archive it could not read, turning a cosmetic problem into
the exact data loss this module exists to prevent.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import threading
from pathlib import Path

from .ingest import work_path

DIRNAME = "plan_history"
MANIFEST = "manifest.json"

# Why a version was archived. `promote` is the runner replacing a cut it
# just validated; `recut` is the same seam with history to carry;
# `migration` is the beat-id rename; `presnap` is snap_cuts' backup slot;
# `manual` is a person or a script asking on purpose.
REASONS = ("promote", "recut", "migration", "presnap", "manual")

_FILE_RE = re.compile(r"^edit_plan\.v(\d{4,})\.json$")
_LOCK = threading.Lock()


def history_dir(slug: str) -> Path:
    return work_path(slug) / DIRNAME


def _manifest_path(slug: str) -> Path:
    return history_dir(slug) / MANIFEST


def path_of(slug: str, v: int) -> Path:
    return history_dir(slug) / ("edit_plan.v%04d.json" % int(v))


def proxy_dir(slug: str, v: int) -> Path:
    """Where a re-cut parks the proxies of the beats it changed, so the
    old picture is still watchable beside the new one."""
    return history_dir(slug) / ("v%04d_proxies" % int(v))


def _versions_on_disk(slug: str) -> "list[int]":
    d = history_dir(slug)
    if not d.is_dir():
        return []
    out = []
    for f in d.iterdir():
        m = _FILE_RE.match(f.name)
        if m:
            out.append(int(m.group(1)))
    return sorted(out)


def versions(slug: str) -> "list":
    """The manifest rows, oldest first. Degrades to [] on a bad manifest."""
    p = _manifest_path(slug)
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text())
    except (ValueError, OSError):
        return []
    rows = data.get("versions") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        return []
    return [r for r in rows if isinstance(r, dict) and isinstance(r.get("v"), int)]


def latest(slug: str) -> "dict | None":
    rows = versions(slug)
    return rows[-1] if rows else None


def archive(slug: str, reason: str, note: str = "") -> "dict | None":
    """Copy the live `edit_plan.json` into history and record it.

    Returns the manifest row, or None when there is no plan yet — a first
    cut has no predecessor, and asking for one is not an error.
    """
    if reason not in REASONS:
        raise ValueError("reason %r not in %s" % (reason, list(REASONS)))
    work = work_path(slug)
    live = work / "edit_plan.json"
    if not live.exists():
        return None
    with _LOCK:
        d = history_dir(slug)
        d.mkdir(parents=True, exist_ok=True)
        # FROM THE FILES. See the module docstring: trusting a manifest
        # that degraded to empty would re-issue v1 over a real archive.
        v = (max(_versions_on_disk(slug) or [0])) + 1
        dest = path_of(slug, v)
        # copy2 keeps mtime, which is the only record of WHEN this cut was
        # built once the file stops being the live one
        shutil.copy2(str(live), str(dest))
        beats = None
        scheme = None
        try:
            plan = json.loads(dest.read_text())
            beats = len(plan.get("beats") or [])
            scheme = plan.get("id_scheme")
        except (ValueError, OSError):
            pass          # an unreadable plan is still worth keeping
        row = {"v": v, "file": dest.name, "ts": int(os.path.getmtime(dest)),
               "reason": reason, "note": note or "",
               "beats": beats, "id_scheme": scheme}
        rows = versions(slug)
        rows.append(row)
        _write_atomic(_manifest_path(slug), {"slug": slug, "versions": rows})
        return row


def _write_atomic(path: Path, data) -> None:
    """tmp + replace with a per-writer tmp name.

    A fixed `.tmp` sibling is worse than no atomicity — one writer's
    `os.replace` moves the file out from under another's. `facts.py` had
    exactly that and it surfaced as a 500 on an upload that had already
    succeeded.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".%d.%d.tmp" % (os.getpid(), threading.get_ident()))
    try:
        tmp.write_text(json.dumps(data, indent=2))
        os.replace(tmp, path)
    except BaseException:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise
