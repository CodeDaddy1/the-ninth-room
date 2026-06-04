"""The local worker daemon (Phase 4).

A single long-running process, started by launchd, that drives videos through
the pipeline. Each tick it:

  1. Scans every in-flight video and ensures its work dir exists.
  2. Advances "watcher" states when the expected file lands on disk
     (agent output or a hand-dropped voiceover.mp3) — no compute, just a
     state bump. Publishing stays a human gate and is never auto-advanced.
  3. Enqueues a job for "worker stage" states (fetch / assemble).
  4. Claims and runs queued jobs, with per-slug file locks, bounded retries,
     and an events feed the dashboard reads over Realtime.

It also exposes a tiny localhost-only HTTP control surface so a locally-run
dashboard can seed a topic or kick a stage without round-tripping Supabase.

State-machine truth lives in `orchestrator/work_dir.py` (WATCHER_STATES /
WORKER_STAGES / NEXT_ACTION), mirrored in dashboard/src/lib/next-action.ts.
"""

from __future__ import annotations

import json
import signal
import sys
import threading
import traceback
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

try:
    import fcntl  # POSIX only; the worker is Mac-local so this is always present.
except ImportError:  # pragma: no cover
    fcntl = None

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
    from worker import config, db, jobs  # noqa: E402
    from worker.jobs import JobError  # noqa: E402
    from worker.orchestrator import work_dir  # noqa: E402
else:
    from .. import config, db, jobs
    from ..jobs import JobError
    from . import work_dir


# Job types the daemon knows how to enqueue/advance but hasn't built yet.
# Listed so they fail with a precise message instead of a generic one.
_DEFERRED_JOB_TYPES = {
    "music_duck": "Phase 6",
    "ready_tray": "Phase 7",
}


def log(msg: str) -> None:
    """Stdout line for the launchd log; flushed so `tail -f` stays live."""
    print(msg, flush=True)


class Daemon:
    def __init__(self, interval: float | None = None, http: bool = True) -> None:
        self.interval = config.POLL_INTERVAL_SEC if interval is None else interval
        self.http_enabled = http
        self._stop = threading.Event()
        self._httpd: ThreadingHTTPServer | None = None

    # --- lifecycle -------------------------------------------------------

    def run(self) -> None:
        """Block forever, ticking every `interval` seconds until signalled."""
        self._install_signal_handlers()
        if self.http_enabled:
            self._start_http()
        log(f"[daemon] up — polling every {self.interval}s, work_dir={config.WORK_DIR}")
        self.emit_event(stage="daemon", message="worker daemon started")
        try:
            while not self._stop.is_set():
                self.tick()
                self._stop.wait(self.interval)
        finally:
            self._shutdown()

    def run_once(self) -> None:
        """A single tick — used by `daemon --once` and tests."""
        self.tick()

    def _shutdown(self) -> None:
        log("[daemon] shutting down")
        self.emit_event(stage="daemon", message="worker daemon stopped")
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()

    def _install_signal_handlers(self) -> None:
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, lambda *_: self._stop.set())

    # --- one tick --------------------------------------------------------

    def tick(self) -> None:
        """One full pass. Network errors are swallowed so launchd doesn't
        crash-loop while Supabase is paused/unreachable — we just retry."""
        try:
            self._scan_videos()
            self._run_queued_jobs()
        except Exception as e:  # noqa: BLE001 — resilience over correctness here
            log(f"[daemon] tick error: {e}")
            log(traceback.format_exc().rstrip())

    def _scan_videos(self) -> None:
        states = ",".join(work_dir.ACTIVE_STATES)
        videos = db.select(
            "videos",
            columns="id,slug,topic,state,platform_targets",
            filters={"state": f"in.({states})"},
            order="updated_at.asc",
        )
        for v in videos:
            slug = v["slug"]
            # DoD: a submitted topic gets its work dir created here.
            config.work_path(slug)
            state = v["state"]
            if state in work_dir.WORKER_STAGES:
                job_type, _success_state = work_dir.WORKER_STAGES[state]
                self._ensure_job(v["id"], slug, job_type)
            elif state in work_dir.WATCHER_STATES:
                self._watch(v)

    def _watch(self, v: dict) -> None:
        """Advance a watcher state if its expected file has appeared."""
        state = v["state"]
        expect = work_dir.expect_file_for(state)
        nxt = work_dir.advances_to(state)
        if not expect or not nxt:
            return
        target = config.work_path(v["slug"]) / expect
        if target.exists():
            self._advance(v, nxt, reason=f"{expect} present")

    def _advance(self, v: dict, new_state: str, *, reason: str) -> None:
        db.update("videos", {"id": f"eq.{v['id']}"}, {"state": new_state})
        msg = f"{v['slug']}: {v['state']} → {new_state} ({reason})"
        log(f"[watch] {msg}")
        self.emit_event(stage=new_state, message=msg, video_id=v["id"])

    # --- job queue -------------------------------------------------------

    def _ensure_job(self, video_id: str, slug: str, job_type: str) -> dict | None:
        """Enqueue a job for this video/type unless one is already pending."""
        existing = db.select(
            "jobs",
            columns="id,status",
            filters={
                "video_id": f"eq.{video_id}",
                "type": f"eq.{job_type}",
                "status": "in.(queued,running)",
            },
            limit=1,
        )
        if existing:
            return existing[0]
        row = db.insert("jobs", {
            "type": job_type,
            "video_id": video_id,
            "status": "queued",
            "payload": {"slug": slug},
        })[0]
        log(f"[queue] {slug}: enqueued {job_type} ({row['id']})")
        self.emit_event(stage=job_type, message=f"{slug}: enqueued {job_type}", video_id=video_id)
        return row

    def _run_queued_jobs(self) -> None:
        queued = db.select(
            "jobs",
            columns="id,type,video_id,payload,status,attempts",
            filters={"status": "eq.queued"},
            order="created_at.asc",
        )
        for job in queued:
            if self._stop.is_set():
                break
            claimed = db.claim_job(job)
            if claimed is None:
                continue  # another worker / loop already grabbed it
            self._run_job(claimed)

    def _run_job(self, job: dict) -> None:
        jtype = job["type"]
        video_id = job.get("video_id")
        payload = job.get("payload") or {}
        slug = payload.get("slug") or (self._slug_for(video_id) if video_id else None)

        log(f"[job] {slug or '-'}: {jtype} (attempt {job.get('attempts')})")
        self.emit_event(stage=jtype, message=f"{slug or '-'}: {jtype} started", video_id=video_id)

        handler = self.HANDLERS.get(jtype)
        if handler is None:
            why = _DEFERRED_JOB_TYPES.get(jtype)
            reason = f"job type '{jtype}' not implemented" + (f" (deferred to {why})" if why else "")
            self._finish_fail(job, slug, reason, terminal=True)
            return

        try:
            with self._slug_lock(slug):
                success_state = handler(self, job, slug)
            self._finish_success(job, slug, success_state)
        except JobError as e:
            self._finish_fail(job, slug, str(e))
        except Exception as e:  # noqa: BLE001
            self._finish_fail(job, slug, f"{type(e).__name__}: {e}")

    def _finish_success(self, job: dict, slug: str | None, success_state: str | None) -> None:
        db.update("jobs", {"id": f"eq.{job['id']}"},
                  {"status": "succeeded", "ended_at": db.now_iso(), "error": None})
        if success_state and job.get("video_id"):
            db.update("videos", {"id": f"eq.{job['video_id']}"}, {"state": success_state})
        suffix = f" → {success_state}" if success_state else ""
        log(f"[job] {slug or '-'}: {job['type']} succeeded{suffix}")
        self.emit_event(stage=job["type"],
                        message=f"{slug or '-'}: {job['type']} succeeded{suffix}",
                        video_id=job.get("video_id"))

    def _finish_fail(self, job: dict, slug: str | None, err: str, *, terminal: bool = False) -> None:
        attempts = int(job.get("attempts", 0))  # already bumped at claim time
        err = err[:2000]
        retryable = (not terminal) and attempts < config.JOB_MAX_ATTEMPTS
        if retryable:
            db.update("jobs", {"id": f"eq.{job['id']}"}, {"status": "queued", "error": err})
            log(f"[job] {slug or '-'}: {job['type']} failed (attempt {attempts}/{config.JOB_MAX_ATTEMPTS}) — will retry")
            self.emit_event(stage=job["type"], level="warn",
                            message=f"{slug or '-'}: {job['type']} failed, retrying — {err.splitlines()[0] if err else ''}",
                            video_id=job.get("video_id"))
            return
        db.update("jobs", {"id": f"eq.{job['id']}"},
                  {"status": "failed", "ended_at": db.now_iso(), "error": err})
        fail_state = work_dir.JOB_FAILURE_STATE.get(job["type"])
        if fail_state and job.get("video_id"):
            db.update("videos", {"id": f"eq.{job['video_id']}"}, {"state": fail_state})
        log(f"[job] {slug or '-'}: {job['type']} FAILED permanently — {err.splitlines()[0] if err else ''}")
        self.emit_event(stage=job["type"], level="error",
                        message=f"{slug or '-'}: {job['type']} failed: {err}",
                        video_id=job.get("video_id"),
                        payload={"error": err})

    # --- job handlers ----------------------------------------------------
    # Each takes (self, job, slug) and returns the video state to advance to
    # on success, or None to leave the video state untouched.

    def _h_fetch(self, job: dict, slug: str) -> str | None:
        per_shot = int((job.get("payload") or {}).get("per_shot", 3))
        jobs.run_fetch(slug, per_shot=per_shot)
        return work_dir.WORKER_STAGES["shots"][1]  # -> "fetching"

    def _h_assemble(self, job: dict, slug: str) -> str | None:
        jobs.run_assemble(slug)
        return work_dir.WORKER_STAGES["assembling"][1]  # -> "ready"

    def _h_register_music(self, job: dict, slug: str | None) -> str | None:
        track = (job.get("payload") or {}).get("track")
        if not track:
            raise JobError("register_music job needs payload.track")
        db.insert("music_tracks", track)
        return None

    def _h_analyst_weekly(self, job: dict, slug: str | None) -> str | None:
        """Stage the week's metrics file so the analyst can run cold.

        Headless `claude -p` subagent visibility is unverified (see project
        land-mines), so v1 stages inputs and nudges Caleb to run
        /performance-analyst interactively rather than executing it blind.
        """
        week = (job.get("payload") or {}).get("week") or _current_iso_week()
        metrics_path = work_dir.metrics_path(week)
        if not metrics_path.exists():
            monday, sunday = work_dir.parse_iso_week(week)
            metrics_path.write_text(json.dumps({
                "week": week, "since": monday.isoformat(),
                "until": sunday.isoformat(), "rows": [],
            }, indent=2) + "\n")
        self.emit_event(stage="analyst_weekly",
                        message=f"metrics staged for {week} — run /performance-analyst week={week}")
        return None

    HANDLERS = {
        "fetch": _h_fetch,
        "assemble": _h_assemble,
        "register_music": _h_register_music,
        "analyst_weekly": _h_analyst_weekly,
    }

    # --- helpers ---------------------------------------------------------

    def _slug_for(self, video_id: str) -> str | None:
        rows = db.select("videos", columns="slug", filters={"id": f"eq.{video_id}"}, limit=1)
        return rows[0]["slug"] if rows else None

    @contextmanager
    def _slug_lock(self, slug: str | None):
        """Exclusive per-slug lock so the same video is never processed twice
        concurrently (e.g. two daemons). Non-blocking: a contended slug fails
        the job, which then retries on a later tick once the lock frees."""
        if not slug or fcntl is None:
            yield
            return
        lock_path = config.work_path(slug) / ".lock"
        f = open(lock_path, "w")
        try:
            try:
                fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as e:
                raise JobError(f"work dir for '{slug}' is locked by another job") from e
            try:
                yield
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)
        finally:
            f.close()

    def emit_event(self, *, stage: str, message: str | None = None, level: str = "info",
                   video_id: str | None = None, payload: dict | None = None) -> None:
        """Best-effort telemetry. Never let a logging failure crash the loop."""
        try:
            db.insert("events", {
                "stage": stage, "level": level, "message": message,
                "video_id": video_id, "payload": payload,
            })
        except Exception as e:  # noqa: BLE001
            log(f"[event] failed to record ({level}/{stage}): {e}")

    # --- HTTP control surface -------------------------------------------

    def _start_http(self) -> None:
        daemon = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_a):  # silence default per-request stderr spam
                pass

            def _send(self, code: int, body: dict) -> None:
                data = json.dumps(body).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def _authed(self) -> bool:
                if not config.WORKER_SECRET:
                    return True  # localhost-only bind; secret optional
                return self.headers.get("X-Worker-Secret") == config.WORKER_SECRET

            def _read_json(self) -> dict:
                n = int(self.headers.get("Content-Length") or 0)
                if not n:
                    return {}
                return json.loads(self.rfile.read(n) or b"{}")

            def do_GET(self):
                if self.path == "/health":
                    self._send(200, {"ok": True, "interval": daemon.interval})
                else:
                    self._send(404, {"error": "not found"})

            def do_POST(self):
                if not self._authed():
                    self._send(401, {"error": "bad or missing X-Worker-Secret"})
                    return
                try:
                    if self.path == "/jobs/topic":
                        self._send(200, daemon._http_create_topic(self._read_json()))
                    elif self.path.startswith("/jobs/run/"):
                        slug = self.path[len("/jobs/run/"):]
                        self._send(200, daemon._http_run(slug, self._read_json()))
                    else:
                        self._send(404, {"error": "not found"})
                except (ValueError, JobError) as e:
                    self._send(400, {"error": str(e)})
                except Exception as e:  # noqa: BLE001
                    self._send(500, {"error": f"{type(e).__name__}: {e}"})

        self._httpd = ThreadingHTTPServer((config.WORKER_HOST, config.WORKER_PORT), Handler)
        t = threading.Thread(target=self._httpd.serve_forever, name="worker-http", daemon=True)
        t.start()
        log(f"[http] control surface on http://{config.WORKER_HOST}:{config.WORKER_PORT}"
            + ("" if config.WORKER_SECRET else "  (no WORKER_SECRET set — localhost only)"))

    def _http_create_topic(self, body: dict) -> dict:
        topic = (body.get("topic") or "").strip()
        if not topic:
            raise ValueError("topic is required")
        slug = (body.get("slug") or _slugify(topic)).strip()
        if not slug:
            raise ValueError("could not derive a slug from topic")
        row = db.insert("videos", {
            "slug": slug,
            "topic": topic,
            "pillar": body.get("pillar"),
            "platform_targets": body.get("platform_targets") or [],
            "state": "queued",
            "notes": body.get("notes"),
        })[0]
        config.work_path(slug)
        self.emit_event(stage="queued", message=f"{slug}: created via control surface", video_id=row["id"])
        return {"video": row}

    def _http_run(self, slug: str, body: dict) -> dict:
        rows = db.select("videos", columns="id,slug,state", filters={"slug": f"eq.{slug}"}, limit=1)
        if not rows:
            raise ValueError(f"no video with slug '{slug}'")
        v = rows[0]
        job_type = body.get("type")
        if not job_type:
            stage = work_dir.WORKER_STAGES.get(v["state"])
            if not stage:
                raise ValueError(f"video '{slug}' is in '{v['state']}', not a worker stage — pass an explicit type")
            job_type = stage[0]
        job = self._ensure_job(v["id"], slug, job_type)
        return {"job": job}


# --- module helpers ------------------------------------------------------

def _slugify(s: str) -> str:
    import re
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:60]


def _current_iso_week() -> str:
    from datetime import date
    iso = date.today().isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def run(interval: float | None = None, http: bool = True, once: bool = False) -> None:
    """Entry point used by `worker/cli.py daemon`."""
    d = Daemon(interval=interval, http=http)
    if once:
        d.run_once()
    else:
        d.run()
