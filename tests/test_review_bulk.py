# -*- coding: utf-8 -*-
"""The chapter sweep: one write, and flags never ride a bulk approve.

P2 of the workflow plan (2026-08-23). A flagged clip was flagged for a
reason — the sweep exists to clear the UNDECIDED remainder of a chapter,
not to erase judgment. reworked/edited count as judgment too (they are
back in the queue for a re-look).

Run: /usr/bin/python3 -m unittest discover -s tests -t .
"""
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline import editroom  # noqa: E402


class BulkReview(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self._wp = editroom.work_path
        editroom.work_path = lambda slug: self.tmp

    def tearDown(self):
        editroom.work_path = self._wp
        shutil.rmtree(self.tmp, ignore_errors=True)

    def read(self):
        return json.loads((self.tmp / "review.json").read_text())

    def test_fresh_clips_sweep_to_approved(self):
        touched = editroom._save_review_bulk("ep", ["BT01", "BT02"], "approved")
        self.assertEqual(touched, 2)
        data = self.read()
        self.assertEqual(data["BT01"]["status"], "approved")
        self.assertEqual(data["BT02"]["status"], "approved")

    def test_flagged_and_reworked_never_ride_the_sweep(self):
        (self.tmp / "review.json").write_text(json.dumps({
            "BT01": {"status": "flagged", "note": "too long"},
            "BT02": {"status": "reworked"},
            "BT03": {"status": "edited"},
        }))
        touched = editroom._save_review_bulk(
            "ep", ["BT01", "BT02", "BT03", "BT04"], "approved")
        self.assertEqual(touched, 1)
        data = self.read()
        self.assertEqual(data["BT01"]["status"], "flagged")
        self.assertEqual(data["BT01"]["note"], "too long")
        self.assertEqual(data["BT02"]["status"], "reworked")
        self.assertEqual(data["BT04"]["status"], "approved")

    def test_an_already_approved_clip_is_a_harmless_retouch(self):
        (self.tmp / "review.json").write_text(json.dumps(
            {"BT01": {"status": "approved"}}))
        touched = editroom._save_review_bulk("ep", ["BT01"], "approved")
        self.assertEqual(touched, 1)

    def test_bad_inputs_refuse(self):
        for ids, status in (([], "approved"), (None, "approved"),
                            (["BT01"], "deleted"), ([1, 2], "approved")):
            with self.assertRaises(Exception, msg=(ids, status)):
                editroom._save_review_bulk("ep", ids, status)


if __name__ == "__main__":
    unittest.main()
