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


FIXER_PROMPT = (
    "Run the fixer round for %(slug)s. Read .claude/agents/shot-fixer.md and "
    "act as that agent: work/%(slug)s/review.json holds the flagged beats — "
    "the note on each is the instruction. Make the smallest change that "
    "satisfies each note, re-proxy only the beats you touched, set each "
    "fixed beat's status to 'reworked' with a one-line fixer_note, and obey "
    "every hard rule in the agent doc. Do NOT run conforms, renders, or "
    "touch DaVinci Resolve — the desk's Conform button handles the "
    "timeline. The engine is running on :8765; leave it alone.")


def _run_fixer(slug, log, set_pct):
    """Dispatch the shot-fixer as a HEADLESS Claude Code session (the same
    agent Caleb used to prompt by hand — same subscription, one button).
    Runs in its own process, so the engine's file locks do not cover it:
    the desk should not place sounds/b-roll on the flagged beats while it
    works, same as during a manual fixer round."""
    import subprocess
    review_path = work_path(slug) / "review.json"
    def flagged():
        if not review_path.exists():
            return []
        d = json.loads(review_path.read_text())
        return [k for k, e in d.items() if e.get("status") == "flagged"]
    before = flagged()
    if not before:
        raise RuntimeError("no flagged beats — nothing to send")
    log("[fixer] dispatching %d flagged beat(s): %s"
        % (len(before), " ".join(before)))
    set_pct(5)
    proc = subprocess.Popen(
        ["~/.local/bin/claude", "-p",
         FIXER_PROMPT % {"slug": slug},
         "--dangerously-skip-permissions"],
        cwd=str(PROJECT_ROOT), stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, text=True)
    set_pct(15)
    for line in proc.stdout:
        line = line.rstrip()
        if line:
            log(line)
    rc = proc.wait()
    if rc != 0:
        raise RuntimeError("fixer session exited %d — see the log" % rc)
    after = flagged()
    fixed = [b for b in before if b not in after]
    log("[fixer] done: %d fixed -> re-review, %d still flagged"
        % (len(fixed), len(after)))
    if not fixed:
        raise RuntimeError("fixer finished but no beat left flagged status "
                           "changed — read the log")
    set_pct(100)


STORY_PROMPT = (
    "Pitch stories for %(slug)s. Read .claude/agents/story-designer.md and "
    "act as that agent: read work/%(slug)s/analysis/ (take transcripts and "
    "the b-roll catalog) and the brand docs, and write "
    "work/%(slug)s/stories.json with three distinct directions. If "
    "work/%(slug)s/favorites.json exists, its files are the clips Caleb "
    "STARRED as the story's core material: build every direction around "
    "them first — a big starred set means a wide story, a small one means "
    "a focused story — and treat unstarred footage as supporting. If "
    "work/%(slug)s/story_feedback.json has rounds, the LATEST round's notes "
    "direct this round — honor them. Do NOT write edit_plan.json (that "
    "needs an approving round on the Story desk), do NOT run conforms or "
    "renders, and do NOT touch DaVinci Resolve. The engine is running on "
    ":8765; leave it alone.")


def _run_story(slug, log, set_pct):
    """Dispatch the story-designer as a headless Claude Code session — the
    same agent Caleb used to prompt by hand, now the desk's Pitch button.
    Same pattern as the fixer: the proof of work is the artifact changing,
    not the exit code."""
    import subprocess
    stories_path = work_path(slug) / "stories.json"
    before = stories_path.stat().st_mtime if stories_path.exists() else None
    log("[story] dispatching the story designer%s"
        % (" — fresh round over existing pitches" if before else ""))
    set_pct(5)
    proc = subprocess.Popen(
        ["~/.local/bin/claude", "-p",
         STORY_PROMPT % {"slug": slug},
         "--dangerously-skip-permissions"],
        cwd=str(PROJECT_ROOT), stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, text=True)
    set_pct(15)
    for line in proc.stdout:
        line = line.rstrip()
        if line:
            log(line)
    rc = proc.wait()
    if rc != 0:
        raise RuntimeError("story session exited %d — see the log" % rc)
    after = stories_path.stat().st_mtime if stories_path.exists() else None
    if after is None or after == before:
        raise RuntimeError("session finished but stories.json did not "
                           "change — read the log")
    log("[story] pitches written — pick a direction on the Story desk")
    set_pct(100)


def _run_render(slug, log, set_pct):
    from . import deliver
    deliver.render_master(slug, log=log, set_pct=set_pct)
    set_pct(100)


KINDS = {
    "ingest": ("Ingest — transcribe, takes, b-roll", _run_ingest),
    "assemble": ("Assemble — timeline + proxies", _run_assemble),
    "reproxy": ("Re-proxy changed beats", _run_reproxy),
    "render": ("Render master — Resolve render queue", _run_render),
    "fixer": ("Fixer round — flagged beats to re-review", _run_fixer),
    "story": ("Story pitches — three directions", _run_story),
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
    if kind == "render":
        from . import conform as conform_mod, resolve_api
        if conform_mod.status(slug).get("state") == "running":
            raise JobError("a conform is running — render after it")
        if resolve_api.rendering_in_progress():
            raise JobError("Resolve is already rendering — wait for it")
    if kind == "story":
        if not (work_path(slug) / "analysis" / "catalog.json").exists():
            raise JobError("ingest first — the designer needs transcripts")
        if (work_path(slug) / "edit_plan.json").exists():
            raise JobError("story is locked — an edit plan already exists")
    if kind == "fixer":
        rv = work_path(slug) / "review.json"
        n = 0
        if rv.exists():
            n = sum(1 for e in json.loads(rv.read_text()).values()
                    if e.get("status") == "flagged")
        if not n:
            raise JobError("no flagged beats to send")
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
