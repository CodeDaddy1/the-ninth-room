# -*- coding: utf-8 -*-
"""Two lanes: a network-bound session must not block local compute.

2026-08-24, measured across 35 real jobs: 173 minutes waiting against
342 running — 34% of job life was queueing — and `snapcuts` waited 57
minutes behind a dispatched Claude session that used no local CPU at
all. Sessions are network-bound and idle on this machine; ffmpeg is not.

Pinned here: every registered kind is classified deliberately, the
lanes really are independent, and the invariant that protects the
machine — AT MOST ONE LOCAL JOB AT A TIME — still holds.

Run: /usr/bin/python3 -m unittest discover -s tests -t .
"""
import os
import shutil
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline import jobs  # noqa: E402


class LaneTable(unittest.TestCase):
    def test_every_registered_kind_has_a_lane(self):
        """A new kind must be classified on purpose. Falling through to
        the default silently is how a session ends up blocking ffmpeg."""
        unclassified = [k for k in jobs.KINDS
                        if k not in jobs.SESSION_KINDS and k not in jobs.LOCAL_KINDS]
        self.assertEqual(unclassified, [],
                         "add these to SESSION_KINDS or LOCAL_KINDS")

    def test_no_kind_is_in_both_lanes(self):
        self.assertEqual(jobs.SESSION_KINDS & jobs.LOCAL_KINDS, set())

    def test_the_dispatching_kinds_are_the_session_lane(self):
        for k in ("story", "editplan", "coverage", "script", "graphics"):
            self.assertEqual(jobs.lane_of(k), "session", k)

    def test_the_ffmpeg_kinds_are_the_local_lane(self):
        for k in ("ingest", "assemble", "reproxy", "render"):
            self.assertEqual(jobs.lane_of(k), "local", k)

    def test_an_unknown_kind_falls_to_the_conservative_lane(self):
        self.assertEqual(jobs.lane_of("something-new"), "local")


class LanesRunIndependently(unittest.TestCase):
    """Through the REAL queue and workers, not helpers."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "x").mkdir()
        self._wp = jobs.work_path
        jobs.work_path = lambda slug: self.tmp / "x"
        self._jobs_path = jobs.JOBS_PATH
        jobs.JOBS_PATH = self.tmp / "_jobs.json"
        self._added = []
        os.environ["NINTH_NOTIFY"] = "0"

    def tearDown(self):
        # drain before restoring JOBS_PATH — see test_exception_policy
        deadline = time.time() + 10
        while time.time() < deadline:
            live = [j for j in jobs._jobs.values()
                    if j["kind"] in self._added
                    and j["state"] in ("queued", "running")]
            if not live:
                break
            time.sleep(0.05)
        # Purge this test's jobs from the MODULE store before the real
        # JOBS_PATH comes back. Draining only waits for them to finish —
        # they stay in jobs._jobs, and _persist() writes the whole store,
        # so the next persist after this line would flush test rows into
        # Caleb's real job history. (Observed 2026-08-24: 33 t_* rows in
        # work/_jobs.json.)
        for jid in [i for i, j in jobs._jobs.items()
                    if j.get("kind") in self._added]:
            jobs._jobs.pop(jid, None)
            if jid in jobs._order:
                jobs._order.remove(jid)
        for k in self._added:
            jobs.KINDS.pop(k, None)
            jobs.SESSION_KINDS.discard(k)
            jobs.LOCAL_KINDS.discard(k)
        jobs.JOBS_PATH = self._jobs_path
        jobs.work_path = self._wp
        del os.environ["NINTH_NOTIFY"]
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _kind(self, name, fn, lane):
        jobs.KINDS[name] = (name, fn)
        (jobs.SESSION_KINDS if lane == "session" else jobs.LOCAL_KINDS).add(name)
        self._added.append(name)

    def test_a_session_and_a_local_job_run_at_the_same_time(self):
        both = threading.Barrier(2, timeout=10)

        def hold(slug, log, set_pct):
            both.wait()          # only passes if the other lane is running too

        self._kind("t_sess", hold, "session")
        self._kind("t_loc", hold, "local")
        a = jobs.start("t_sess", "x")
        b = jobs.start("t_loc", "x")
        for j in (a, b):
            self._wait(j["id"])
        self.assertEqual(jobs._jobs[a["id"]]["state"], "done")
        self.assertEqual(jobs._jobs[b["id"]]["state"], "done")

    def test_two_local_jobs_still_serialise(self):
        """The invariant: never two encodes at once."""
        live = []
        peak = []

        def busy(slug, log, set_pct):
            live.append(1)
            peak.append(len(live))
            time.sleep(0.25)
            live.pop()

        self._kind("t_loc1", busy, "local")
        self._kind("t_loc2", busy, "local")
        a = jobs.start("t_loc1", "x")
        b = jobs.start("t_loc2", "x")
        for j in (a, b):
            self._wait(j["id"])
        self.assertEqual(max(peak), 1, "two local jobs ran concurrently")

    def test_a_queued_job_is_numbered_within_its_own_lane(self):
        def hold(slug, log, set_pct):
            time.sleep(0.4)
        self._kind("t_s", hold, "session")
        self._kind("t_l1", hold, "local")
        self._kind("t_l2", hold, "local")
        mine = [jobs.start("t_s", "x")["id"], jobs.start("t_l1", "x")["id"]]
        third = jobs.start("t_l2", "x")
        mine.append(third["id"])
        time.sleep(0.05)
        rows = {r["id"]: r for r in jobs.jobs()}
        row = rows[third["id"]]
        if row["state"] == "queued":
            # 1st in the LOCAL lane — the session job cannot block it
            self.assertEqual(row["lane"], "local")
            self.assertLessEqual(row["queue_pos"], 1)
        # only the jobs THIS test started: jobs.jobs() also returns rows
        # _restore() loaded from the real store at import time
        for j in mine:
            self._wait(j, timeout=6)

    def _wait(self, jid, states=("done", "failed", "declined"), timeout=10.0):
        t0 = time.time()
        while time.time() - t0 < timeout:
            j = jobs._jobs.get(jid)
            if j and j["state"] in states:
                return j
            time.sleep(0.02)
        raise AssertionError("job %s never settled: %r" % (jid, jobs._jobs.get(jid)))


if __name__ == "__main__":
    unittest.main()
