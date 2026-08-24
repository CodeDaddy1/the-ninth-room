# -*- coding: utf-8 -*-
"""A dispatched session must say it is still there.

2026-08-24, found live: `claude -p` buffers its entire reply until the
session ends, so every job that dispatches one sat at exactly 15% with an
empty note for its whole run. Caleb, watching a 16-minute edit-plan job:
"still showing 15%". Working and hung were indistinguishable, and the
only way to tell them apart was killing the engine — which then killed
the job.

Pinned here: the bar moves, it NEVER reaches 100 on a heartbeat (only
real completion may say that), and a session that does print is drained
without waiting on the tick.

Run: /usr/bin/python3 -m unittest discover -s tests -t .
"""
import io
import os
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline import jobs  # noqa: E402


class HeartbeatCurve(unittest.TestCase):
    def test_it_starts_at_the_floor_and_climbs(self):
        self.assertEqual(jobs.heartbeat_pct(0), 15)
        self.assertGreater(jobs.heartbeat_pct(120), 15)
        self.assertGreater(jobs.heartbeat_pct(600), jobs.heartbeat_pct(120))

    def test_it_never_claims_the_work_is_done(self):
        """An asymptote, not a countdown: the only honest statement a
        heartbeat can make is 'still working'."""
        for elapsed in (600, 3600, 86400, 10 ** 9):
            self.assertLess(jobs.heartbeat_pct(elapsed), 100)
            self.assertLessEqual(jobs.heartbeat_pct(elapsed),
                                 jobs.HEARTBEAT_CEIL)

    def test_it_is_monotonic(self):
        prev = -1
        for t in range(0, 3600, 60):
            now = jobs.heartbeat_pct(t)
            self.assertGreaterEqual(now, prev)
            prev = now


class FakeProc:
    """A session that prints what it is told, then exits."""

    def __init__(self, lines=(), alive_s=0.0, rc=0):
        self.stdout = io.StringIO("".join(l + "\n" for l in lines))
        self._until = time.time() + alive_s
        self._rc = rc

    def poll(self):
        return None if time.time() < self._until else self._rc

    def wait(self):
        return self._rc


class Drain(unittest.TestCase):
    def setUp(self):
        self._hb = jobs.HEARTBEAT_S
        jobs.HEARTBEAT_S = 0.05          # tick fast for the test

    def tearDown(self):
        jobs.HEARTBEAT_S = self._hb

    def test_a_silent_session_still_ticks(self):
        logged, pcts = [], []
        proc = FakeProc(lines=(), alive_s=0.4)
        rc = jobs._drain_with_heartbeat(proc, logged.append, pcts.append,
                                        "editplan")
        self.assertEqual(rc, 0)
        self.assertTrue(pcts, "the bar never moved")
        self.assertTrue(any("still working" in l for l in logged), logged)
        self.assertTrue(all(p < 100 for p in pcts), pcts)

    def test_a_talking_session_is_drained_verbatim(self):
        logged = []
        proc = FakeProc(lines=["[cut] BT01", "[cut] BT02"], alive_s=0.0)
        jobs._drain_with_heartbeat(proc, logged.append, lambda p: None, "x")
        self.assertIn("[cut] BT01", logged)
        self.assertIn("[cut] BT02", logged)

    def test_the_exit_code_comes_back(self):
        proc = FakeProc(lines=[], alive_s=0.0, rc=3)
        self.assertEqual(
            jobs._drain_with_heartbeat(proc, lambda l: None,
                                       lambda p: None, "x"), 3)


if __name__ == "__main__":
    unittest.main()
