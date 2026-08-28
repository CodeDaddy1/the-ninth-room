# -*- coding: utf-8 -*-
"""Terminal jobs are kept forever, not for fifty runs.

`_jobs.json` is a ring buffer of the last KEEP rows — right for the
Studio's activity tray, and the reason the engine had no job history at
all. The 2026-08-28 failure analysis (50 jobs, 14 failed, 45 minutes
burned) had to be frozen into docs/baselines/ by hand, because the work it
was measuring would have overwritten the measurement. It rotated once
mid-session even so, dropping a Class A failure.

What breaks if this is wrong: the scoreboard becomes unmeasurable. "Is it
actually better?" needs a before, and the before deletes itself.

Run: /usr/bin/python3 -m unittest discover -s tests -t .
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline import jobs  # noqa: E402


class History(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self._real = jobs.HISTORY_PATH
        jobs.HISTORY_PATH = Path(self.tmp) / "_jobs.log"
        self.jid = "JTEST%d" % id(self)
        with jobs._LOCK:
            jobs._jobs[self.jid] = {"id": self.jid, "kind": "ingest",
                                    "slug": "ep", "state": "queued"}
            jobs._order.append(self.jid)

    def tearDown(self):
        jobs.HISTORY_PATH = self._real
        with jobs._LOCK:
            jobs._jobs.pop(self.jid, None)
            if self.jid in jobs._order:
                jobs._order.remove(self.jid)

    def lines(self):
        if not jobs.HISTORY_PATH.exists():
            return []
        return [json.loads(l) for l in
                jobs.HISTORY_PATH.read_text().splitlines() if l.strip()]

    def test_a_finished_job_is_written_once(self):
        jobs._update(self.jid, state="running")
        self.assertEqual(self.lines(), [])
        jobs._update(self.jid, state="done", pct=100)
        rows = self.lines()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], self.jid)
        self.assertEqual(rows[0]["state"], "done")

    def test_updates_after_the_transition_do_not_write_again(self):
        """A job that is touched after it finishes is still one job."""
        jobs._update(self.jid, state="failed", error="boom")
        jobs._update(self.jid, note="read the log")
        jobs._update(self.jid, pct=0)
        self.assertEqual(len(self.lines()), 1)

    def test_a_declined_job_is_history_too(self):
        """A refusal is a measurement — it says a door was open that
        should not have been."""
        jobs._update(self.jid, state="declined", error="already reviewing")
        self.assertEqual(len(self.lines()), 1)

    def test_progress_ticks_write_nothing(self):
        for pct in (5, 15, 40, 90):
            jobs._update(self.jid, state="running", pct=pct)
        self.assertEqual(self.lines(), [])

    def test_history_never_fails_a_job(self):
        """Diagnostic only. An unwritable path must not raise out of
        _update and kill the worker thread."""
        jobs.HISTORY_PATH = Path(self.tmp) / "no" / "such" / "dir" / "x.log"
        os.chmod(self.tmp, 0o500)
        try:
            jobs._update(self.jid, state="done")
        finally:
            os.chmod(self.tmp, 0o700)


if __name__ == "__main__":
    unittest.main()
