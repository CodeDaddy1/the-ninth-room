# -*- coding: utf-8 -*-
"""Deleting a project is permanent, so the gates are the feature.

2026-08-24. What is pinned here is everything that stands between a
mis-click and 60 GB of unrepeatable footage:

- the typed confirmation must echo the slug exactly;
- a `_`-prefixed directory (_archive, _scout, _scorecards) is not an
  episode and can never be the target;
- a queued or running job for the slug refuses the delete — erasing the
  tree under a live ingest leaves half-written files;
- an archived project deletes from the archive, not from the live root;
- symlinked directories inside the tree are unlinked, NEVER followed:
  the compare sandboxes point their `analysis` at another episode, and
  that episode must survive.

Run: /usr/bin/python3 -m unittest discover -s tests -t .
"""
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline import editroom  # noqa: E402
from pipeline.ingest import IngestError  # noqa: E402


class DeleteGates(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self._wp = editroom.work_path
        editroom.work_path = lambda slug: self.root / slug
        self._jobs = []
        import pipeline.jobs as jobs_mod
        self._real_jobs = jobs_mod.jobs
        jobs_mod.jobs = lambda slug=None: list(self._jobs)
        self.jobs_mod = jobs_mod

    def tearDown(self):
        editroom.work_path = self._wp
        self.jobs_mod.jobs = self._real_jobs
        shutil.rmtree(self.root, ignore_errors=True)

    def make(self, slug, archived=False, mb=1):
        d = (self.root / "_archive" / slug) if archived else (self.root / slug)
        (d / "footage").mkdir(parents=True)
        (d / "footage" / "A001.mov").write_bytes(b"x" * (mb * 1000))
        (d / "edit_plan.json").write_text("{}")
        return d

    def test_the_typed_name_must_match(self):
        self.make("crooise")
        with self.assertRaises(IngestError) as e:
            editroom._delete_project("crooise", "croise", log=lambda *_: None)
        self.assertIn("type the episode", str(e.exception))
        self.assertTrue((self.root / "crooise").is_dir())

    def test_an_empty_confirmation_refuses(self):
        self.make("crooise")
        with self.assertRaises(IngestError):
            editroom._delete_project("crooise", "", log=lambda *_: None)
        self.assertTrue((self.root / "crooise").is_dir())

    def test_a_bookkeeping_directory_is_not_an_episode(self):
        (self.root / "_archive").mkdir(parents=True, exist_ok=True)
        with self.assertRaises(IngestError) as e:
            editroom._delete_project("_archive", "_archive",
                                     log=lambda *_: None)
        self.assertIn("bad slug", str(e.exception))
        self.assertTrue((self.root / "_archive").is_dir())

    def test_a_running_job_refuses_the_delete(self):
        self.make("crooise")
        self._jobs = [{"kind": "ingest", "state": "running", "slug": "crooise"}]
        with self.assertRaises(IngestError) as e:
            editroom._delete_project("crooise", "crooise", log=lambda *_: None)
        self.assertIn("busy", str(e.exception))
        self.assertTrue((self.root / "crooise").is_dir())

    def test_a_finished_job_does_not(self):
        self.make("crooise")
        self._jobs = [{"kind": "ingest", "state": "done", "slug": "crooise"}]
        out = editroom._delete_project("crooise", "crooise",
                                       log=lambda *_: None)
        self.assertEqual(out["files"], 2)
        self.assertFalse((self.root / "crooise").exists())

    def test_it_reports_what_it_freed(self):
        self.make("crooise", mb=3)
        out = editroom._delete_project("crooise", "crooise",
                                       log=lambda *_: None)
        self.assertEqual(out["bytes"], 3000 + 2)  # + edit_plan.json
        self.assertFalse(out["archived"])

    def test_an_archived_project_deletes_from_the_archive(self):
        self.make("dead-one", archived=True)
        out = editroom._delete_project("dead-one", "dead-one",
                                       log=lambda *_: None)
        self.assertTrue(out["archived"])
        self.assertFalse((self.root / "_archive" / "dead-one").exists())

    def test_an_unknown_slug_raises(self):
        with self.assertRaises(IngestError) as e:
            editroom._delete_project("ghost", "ghost", log=lambda *_: None)
        self.assertIn("no project", str(e.exception))

    def test_the_scorecards_go_with_it(self):
        self.make("crooise")
        cards = self.root / "_scorecards" / "crooise"
        cards.mkdir(parents=True)
        (cards / "T1.json").write_text("{}")
        editroom._delete_project("crooise", "crooise", log=lambda *_: None)
        self.assertFalse(cards.exists())

    def test_a_symlinked_directory_is_unlinked_never_followed(self):
        """The compare sandboxes symlink `analysis` at a real episode."""
        self.make("hmns", mb=9)
        sandbox = self.root / "sandbox"
        sandbox.mkdir()
        (sandbox / "edit_plan.json").write_text("{}")
        os.symlink(self.root / "hmns" / "footage", sandbox / "analysis")
        out = editroom._delete_project("sandbox", "sandbox",
                                       log=lambda *_: None)
        # the link counted as one entry, its 9000-byte target was not read
        self.assertEqual(out["bytes"], 2)
        self.assertFalse(sandbox.exists())
        self.assertTrue((self.root / "hmns" / "footage" / "A001.mov").exists())


if __name__ == "__main__":
    unittest.main()
