# -*- coding: utf-8 -*-
"""A restart that kills a job must leave a trace worth reading.

The engine log held 72 boot lines reading exactly the same 46 characters,
with no timestamp and no pid. launchd has KeepAlive true, so the process
always comes back and a death leaves nothing else behind. That made "engine
restarted mid-job" undiagnosable after the fact: of the three in the frozen
baseline, two could be pinned to a manual restart only by correlating
against commit times, and the third (2026-08-27 19:47) never was.

What breaks if this is wrong: the next unexplained death is equally
unexplainable, and the boot-time re-queue the job contract calls for has no
record of what it re-queued.

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


class InterruptedAtBoot(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self._path, self._ids, self._order = (
            jobs.JOBS_PATH, dict(jobs._jobs), list(jobs._order))
        self._boot = list(jobs.INTERRUPTED_AT_BOOT)
        jobs.JOBS_PATH = Path(self.tmp) / "_jobs.json"
        jobs._jobs.clear()
        del jobs._order[:]
        del jobs.INTERRUPTED_AT_BOOT[:]

    def tearDown(self):
        jobs.JOBS_PATH = self._path
        jobs._jobs.clear()
        jobs._jobs.update(self._ids)
        del jobs._order[:]
        jobs._order.extend(self._order)
        del jobs.INTERRUPTED_AT_BOOT[:]
        jobs.INTERRUPTED_AT_BOOT.extend(self._boot)

    def write(self, rows):
        jobs.JOBS_PATH.write_text(json.dumps({"jobs": rows}))

    def test_a_job_left_running_is_recorded_not_just_marked(self):
        self.write([{"id": "J1", "kind": "ingest", "slug": "ep",
                     "state": "running"}])
        jobs._restore()
        self.assertEqual(len(jobs.INTERRUPTED_AT_BOOT), 1)
        self.assertEqual(jobs.INTERRUPTED_AT_BOOT[0]["kind"], "ingest")
        self.assertEqual(jobs.INTERRUPTED_AT_BOOT[0]["slug"], "ep")

    def test_a_queued_job_counts_too(self):
        """It never got to run, and that is the same loss."""
        self.write([{"id": "J2", "kind": "editplan", "slug": "golf",
                     "state": "queued"}])
        jobs._restore()
        self.assertEqual(len(jobs.INTERRUPTED_AT_BOOT), 1)

    def test_a_clean_shutdown_records_nothing(self):
        self.write([{"id": "J3", "kind": "survey", "slug": "ep",
                     "state": "done"},
                    {"id": "J4", "kind": "ingest", "slug": "ep",
                     "state": "failed", "error": "no frames"}])
        jobs._restore()
        self.assertEqual(jobs.INTERRUPTED_AT_BOOT, [])

    def test_the_recorded_row_is_the_one_that_was_marked(self):
        """The boot line names kinds and slugs, so it must hold the row
        itself and not a copy that drifts."""
        self.write([{"id": "J5", "kind": "coverage", "slug": "hmns",
                     "state": "running"}])
        jobs._restore()
        row = jobs.INTERRUPTED_AT_BOOT[0]
        self.assertEqual(row["error"], "engine restarted mid-job")
        self.assertIs(row, jobs._jobs["J5"])


if __name__ == "__main__":
    unittest.main()
