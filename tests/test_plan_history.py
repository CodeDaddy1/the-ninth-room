# -*- coding: utf-8 -*-
"""A cut that is replaced is kept.

`_write_edit_plan` overwrites, `work/_archive/` has been empty since it
was created, and the only history on disk anywhere is a few hand-made
copies — `edit_plan_v2_rejected.json`, `edit_plan_presnap.json` — which
is what a person does when the system will not do it for them.

The benchmark needs the old cut ("screen the re-cut against the shipped
one"), and so does the verdict carry: carrying a verdict means diffing a
plan against its predecessor, and a predecessor that was overwritten
cannot be diffed.

The sharp edge is the version number. A manifest that fails to parse
degrades to "no history" rather than raising, which is right — a corrupt
sidecar must not take the desk down. But numbering that TRUSTED that
empty answer would hand out v1 again and overwrite the archive it could
not read, turning a cosmetic problem into the exact data loss this module
exists to prevent. So numbering reads the files.

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

from pipeline import ingest, plan_history as ph  # noqa: E402


class PlanHistory(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self._wp = ingest.work_path
        ingest.work_path = lambda slug: self.tmp
        ph.work_path = ingest.work_path

    def tearDown(self):
        ingest.work_path = self._wp
        ph.work_path = self._wp
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _plan(self, n_beats=3, scheme=None):
        p = {"slug": "ep", "beats": [{"id": "BT%02d" % i}
                                     for i in range(n_beats)]}
        if scheme:
            p["id_scheme"] = scheme
        (self.tmp / "edit_plan.json").write_text(json.dumps(p))
        return p

    # ---- the basics -------------------------------------------------

    def test_the_first_archive_is_v1(self):
        self._plan()
        row = ph.archive("ep", reason="promote")
        self.assertEqual(row["v"], 1)
        self.assertEqual(row["file"], "edit_plan.v0001.json")
        self.assertTrue(ph.path_of("ep", 1).exists())

    def test_no_plan_yet_is_not_an_error(self):
        """A first cut has no predecessor; asking for one is a no-op, so
        the promote seam can call this unconditionally."""
        self.assertIsNone(ph.archive("ep", reason="promote"))

    def test_the_archived_copy_is_the_plan_that_was_live(self):
        self._plan(n_beats=5)
        ph.archive("ep", reason="promote")
        self._plan(n_beats=2)          # the cut moves on
        kept = json.loads(ph.path_of("ep", 1).read_text())
        self.assertEqual(len(kept["beats"]), 5)

    def test_the_manifest_records_what_it_is_and_why(self):
        self._plan(n_beats=4, scheme="shot-v1")
        row = ph.archive("ep", reason="migration", note="beat ids")
        self.assertEqual(row["reason"], "migration")
        self.assertEqual(row["note"], "beat ids")
        self.assertEqual(row["beats"], 4)
        self.assertEqual(row["id_scheme"], "shot-v1")

    def test_an_unknown_reason_is_refused(self):
        """The reasons are a closed vocabulary because they are what the
        history is READ by. A free-text reason is a comment."""
        self._plan()
        with self.assertRaises(ValueError):
            ph.archive("ep", reason="because")

    # ---- append-only ------------------------------------------------

    def test_five_archives_are_five_versions_in_order(self):
        for i in range(5):
            self._plan(n_beats=i + 1)
            ph.archive("ep", reason="manual")
        rows = ph.versions("ep")
        self.assertEqual([r["v"] for r in rows], [1, 2, 3, 4, 5])
        self.assertEqual([r["beats"] for r in rows], [1, 2, 3, 4, 5])
        self.assertEqual(ph.latest("ep")["v"], 5)

    def test_nothing_is_ever_overwritten(self):
        for i in range(3):
            self._plan(n_beats=i + 1)
            ph.archive("ep", reason="manual")
        for v in (1, 2, 3):
            kept = json.loads(ph.path_of("ep", v).read_text())
            self.assertEqual(len(kept["beats"]), v)

    # ---- the sharp edge ---------------------------------------------

    def test_a_corrupt_manifest_reads_as_no_history(self):
        self._plan()
        ph.archive("ep", reason="manual")
        (ph.history_dir("ep") / ph.MANIFEST).write_text("{not json")
        self.assertEqual(ph.versions("ep"), [])
        self.assertIsNone(ph.latest("ep"))

    def test_a_corrupt_manifest_does_NOT_let_v1_be_reissued(self):
        """THE ONE THAT MATTERS. Degrading to [] is right for reading and
        catastrophic for numbering: v1 would be handed out again and the
        archived plan overwritten by the one replacing it."""
        self._plan(n_beats=7)
        ph.archive("ep", reason="manual")
        (ph.history_dir("ep") / ph.MANIFEST).write_text("{not json")
        self._plan(n_beats=1)
        row = ph.archive("ep", reason="manual")
        self.assertEqual(row["v"], 2)
        self.assertEqual(len(json.loads(
            ph.path_of("ep", 1).read_text())["beats"]), 7)

    def test_a_missing_manifest_is_rebuilt_without_losing_the_number(self):
        self._plan()
        ph.archive("ep", reason="manual")
        (ph.history_dir("ep") / ph.MANIFEST).unlink()
        self._plan()
        self.assertEqual(ph.archive("ep", reason="manual")["v"], 2)

    def test_an_unreadable_plan_is_still_archived(self):
        """Keeping a corrupt cut is the whole point — it is the evidence
        for what went wrong. It just cannot report its beat count."""
        (self.tmp / "edit_plan.json").write_text("{truncated")
        row = ph.archive("ep", reason="promote")
        self.assertEqual(row["v"], 1)
        self.assertIsNone(row["beats"])
        self.assertTrue(ph.path_of("ep", 1).exists())

    def test_the_proxy_dir_is_named_for_its_version(self):
        self.assertTrue(str(ph.proxy_dir("ep", 2)).endswith("v0002_proxies"))


class SnapCutsUsesTheHistory(unittest.TestCase):
    """snap_cuts backed up to ONE fixed filename, so a second snap
    overwrote the backup taken before the first — the only run you could
    undo was the most recent one."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self._wp = ingest.work_path
        ingest.work_path = lambda slug: self.tmp
        ph.work_path = ingest.work_path

    def tearDown(self):
        ingest.work_path = self._wp
        ph.work_path = self._wp
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_two_snaps_keep_two_backups(self):
        from pipeline import snap_cuts
        self.assertIn("plan_history",
                      Path(snap_cuts.__file__).read_text())
        (self.tmp / "edit_plan.json").write_text(
            json.dumps({"slug": "ep", "beats": [{"id": "BT01"}]}))
        ph.archive("ep", reason="presnap")
        (self.tmp / "edit_plan.json").write_text(
            json.dumps({"slug": "ep", "beats": [{"id": "BT01"},
                                                {"id": "BT02"}]}))
        ph.archive("ep", reason="presnap")
        self.assertEqual([r["beats"] for r in ph.versions("ep")], [1, 2])


if __name__ == "__main__":
    unittest.main()
