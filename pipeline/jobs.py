# -*- coding: utf-8 -*-
"""The engine's job queue (P4): mechanical pipeline stages as buttons.

One daemon worker consumes a FIFO queue, so heavy stages never run
concurrently (they would only fight over _BAKE_LOCK/_BUILD_LOCK anyway) and
a desk click can never start the same stage twice. State is mirrored to
``work/_jobs.json`` (last 50) so the Studio's activity tray can poll it and
a mid-job engine restart shows an honest "interrupted" instead of a
forever-running ghost. Per-job logs land in ``work/_jobs/<id>.log``.

Kinds are the *mechanical* stages only — story, edit plan, and the fixer
stay agent work (plan amendment: P4 pipeline buttons):

- ``ingest``   — probe + transcribe, take analysis, b-roll catalog
- ``assemble`` — edit_plan -> captions/cards -> timeline.fcpxml, then proxies
- ``reproxy``  — proxy.build: only beats whose spec hash moved re-render
"""
import json
import os
import queue
import threading
import time

from .ingest import PROJECT_ROOT, work_path

JOBS_PATH = PROJECT_ROOT / "work" / "_jobs.json"
LOG_DIR = PROJECT_ROOT / "work" / "_jobs"
KEEP = 50

_LOCK = threading.Lock()
_QUEUE = queue.Queue()
_WORKER = [None]
_jobs = {}
_order = []


class JobError(Exception):
    pass


def _persist():
    rows = [_jobs[i] for i in _order[-KEEP:]]
    JOBS_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = JOBS_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps({"jobs": rows}, indent=2))
    os.replace(tmp, JOBS_PATH)


def _restore():
    """On import: reload history; anything 'running' at restart was killed
    with the process — say so rather than showing it running forever."""
    if not JOBS_PATH.exists():
        return
    try:
        rows = json.loads(JOBS_PATH.read_text()).get("jobs", [])
    except ValueError:
        return
    changed = False
    for r in rows:
        if r.get("state") in ("running", "queued"):
            r["state"] = "failed"
            r["error"] = "engine restarted mid-job"
            r["ended_ts"] = int(time.time())
            changed = True
        _jobs[r["id"]] = r
        _order.append(r["id"])
    if changed:
        _persist()


def _update(jid, **fields):
    with _LOCK:
        _jobs[jid].update(fields)
        _persist()


def _job_log(jid):
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    path = LOG_DIR / ("%s.log" % jid)

    def log(*parts):
        line = " ".join(str(p) for p in parts)
        with open(path, "a") as f:
            f.write(line + "\n")
        _update(jid, note=line[-160:])
    return log


def _run_ingest(slug, log, set_pct):
    from . import ingest as ingest_mod, takes, broll
    set_pct(2)
    log("[job] ingest: probe + transcribe")
    ingest_mod.ingest(slug)
    set_pct(60)
    log("[job] ingest: take analysis")
    takes.analyze(slug)
    set_pct(80)
    log("[job] ingest: b-roll catalog")
    broll.catalog_broll(slug)
    set_pct(100)


def _run_assemble(slug, log, set_pct):
    from . import produce, proxy
    set_pct(2)
    log("[job] assemble: building the timeline")
    produce.build_timeline(slug)
    set_pct(55)
    log("[job] assemble: review proxies")
    proxy.build(slug, log=log)
    set_pct(100)


def _run_reproxy(slug, log, set_pct):
    from . import proxy
    set_pct(5)
    proxy.build(slug, log=log)
    set_pct(100)


KINDS = {
    "ingest": ("Ingest — transcribe, takes, b-roll", _run_ingest),
    "assemble": ("Assemble — timeline + proxies", _run_assemble),
    "reproxy": ("Re-proxy changed beats", _run_reproxy),
}


def _worker():
    while True:
        jid = _QUEUE.get()
        job = _jobs[jid]
        _update(jid, state="running", started_ts=int(time.time()))
        log = _job_log(jid)
        try:
            _, fn = KINDS[job["kind"]]
            fn(job["slug"], log, lambda p: _update(jid, pct=int(p)))
            _update(jid, state="done", pct=100, ended_ts=int(time.time()))
        except Exception as e:  # the tray must show the failure, never hang
            log("[job] FAILED: %s: %s" % (type(e).__name__, e))
            _update(jid, state="failed", error=str(e)[:300],
                    ended_ts=int(time.time()))


def start(kind: str, slug: str) -> "dict":
    if kind not in KINDS:
        raise JobError("unknown job kind '%s'" % kind)
    if not (work_path(slug)).is_dir():
        raise JobError("no project '%s'" % slug)
    with _LOCK:
        for j in _jobs.values():
            if (j["kind"] == kind and j["slug"] == slug
                    and j["state"] in ("queued", "running")):
                raise JobError("%s is already %s for %s"
                               % (kind, j["state"], slug))
        jid = "J%d%03d" % (int(time.time()), len(_order) % 1000)
        job = {"id": jid, "kind": kind, "slug": slug,
               "label": KINDS[kind][0], "state": "queued", "pct": 0,
               "note": "", "queued_ts": int(time.time())}
        _jobs[jid] = job
        _order.append(jid)
        _persist()
        if _WORKER[0] is None:
            _WORKER[0] = threading.Thread(target=_worker, daemon=True)
            _WORKER[0].start()
    _QUEUE.put(jid)
    return job


def jobs(slug: "str | None" = None) -> "list":
    with _LOCK:
        rows = [_jobs[i] for i in reversed(_order)]
    if slug:
        rows = [r for r in rows if r["slug"] == slug]
    return rows[:KEEP]


def log_tail(jid: str, lines: int = 120) -> str:
    path = LOG_DIR / ("%s.log" % jid)
    if not path.exists():
        return ""
    return "\n".join(path.read_text().splitlines()[-lines:])


_restore()
