# -*- coding: utf-8 -*-
"""A failure the desk can explain needs a STABLE code, not prose.

2026-08-25. Two `ingest` jobs sat in the live list reading "no speech
takes found in catalog" — engine vocabulary, and the Footage desk showed
nothing at all, because `useEngineJob` only resumes jobs that are still
running. Giving the desk a door means matching the failure, and matching
on the MESSAGE means a reworded error silently turns that door into a
dead end.

So `IngestError` may carry a `code`, the worker copies it onto the job
row as `error_code`, and the Studio matches on that. Deliberately only
three raises carry one — the ones the Footage desk can actually do
something about. Everything else keeps showing its message verbatim and
gets no door; that is the bargain, and this file pins both halves of it.

Run: /usr/bin/python3 -m unittest discover -s tests -t .
"""
import os
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline import jobs  # noqa: E402
from pipeline.ingest import IngestError  # noqa: E402


class TheErrorItself(unittest.TestCase):
    def test_a_code_is_optional_and_never_changes_the_message(self):
        plain = IngestError("catalog failed validation")
        coded = IngestError("no speech takes found in catalog", code="no_speech")
        self.assertIsNone(plain.code)
        self.assertEqual(coded.code, "no_speech")
        # the message is what a human reads in a log; adding a code must
        # not smuggle anything into it
        self.assertEqual(str(coded), "no speech takes found in catalog")

    def test_every_coded_raise_the_desk_explains_is_reachable(self):
        """A code nobody raises is a door that never opens.

        These are the exact sites the Studio has words for; the mirror of
        this list lives in `src/lib/job-failure.test.ts` as
        EXPLAINED_CODES, and the two must not drift.

        `proxy_linked` joined on 2026-08-27 — a master render refuses
        while Resolve is editing against 1080p previews. It is raised from
        `resolve_api`, which is why this reads three files now.
        """
        root = Path(__file__).resolve().parent.parent / "pipeline"
        src = ((root / "ingest.py").read_text()
               + (root / "takes.py").read_text()
               + (root / "resolve_api.py").read_text())
        for code in ("no_speech", "no_media", "bad_file", "proxy_linked"):
            self.assertIn('code="%s"' % code, src,
                          "%s is claimed by the desk but never raised" % code)

    def test_the_proxy_refusal_is_on_the_RENDER_path(self):
        """The guard is only a guard if the thing it guards calls it.

        Deliberately NOT on conform: conform mutates the timeline, it does
        not bake pixels, and blocking it would block the exact hand-editing
        loop previews exist to enable.
        """
        root = Path(__file__).resolve().parent.parent / "pipeline"
        deliver_src = (root / "deliver.py").read_text()
        self.assertIn("preflight_no_proxies", deliver_src)
        self.assertNotIn("preflight_no_proxies",
                         (root / "conform.py").read_text())


class OntoTheJobRow(unittest.TestCase):
    """Through the REAL worker — the copy happens in `_run_one`'s except
    branch, which is exactly the place a unit test of the error class
    cannot reach."""

    @classmethod
    def setUpClass(cls):
        cls._path = jobs.JOBS_PATH
        cls._tmp = Path(tempfile.mkdtemp())
        jobs.JOBS_PATH = cls._tmp / "_jobs.json"

    @classmethod
    def tearDownClass(cls):
        time.sleep(0.2)
        jobs.JOBS_PATH = cls._path
        shutil.rmtree(cls._tmp, ignore_errors=True)

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "x").mkdir()
        self._wp = jobs.work_path
        jobs.work_path = lambda slug: self.tmp / "x"
        os.environ["NINTH_NOTIFY"] = "0"
        self._added = []

    def tearDown(self):
        deadline = time.time() + 10
        while time.time() < deadline:
            if not [j for j in jobs._jobs.values()
                    if j.get("kind") in self._added
                    and j["state"] in ("queued", "running")]:
                break
            time.sleep(0.05)
        for jid in [i for i, j in jobs._jobs.items()
                    if j.get("kind") in self._added]:
            jobs._jobs.pop(jid, None)
            if jid in jobs._order:
                jobs._order.remove(jid)
        for k in self._added:
            jobs.KINDS.pop(k, None)
            jobs.SESSION_KINDS.discard(k)
            jobs.LOCAL_KINDS.discard(k)
        jobs.work_path = self._wp
        del os.environ["NINTH_NOTIFY"]
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _kind(self, name, fn):
        jobs.KINDS[name] = (name, fn)
        jobs.LOCAL_KINDS.add(name)
        self._added.append(name)

    def _wait(self, jid, timeout=10.0):
        t0 = time.time()
        while time.time() - t0 < timeout:
            j = jobs._jobs.get(jid)
            if j and j["state"] in ("done", "failed", "declined"):
                return j
            time.sleep(0.02)
        self.fail("job %s never settled: %r" % (jid, jobs._jobs.get(jid)))

    def _raiser(self, exc):
        def go(slug, log, set_pct):
            raise exc
        return go

    def test_a_coded_failure_reaches_the_row_as_error_code(self):
        self._kind("t_code1", self._raiser(
            IngestError("no speech takes found in catalog", code="no_speech")))
        row = self._wait(jobs.start("t_code1", "x")["id"])
        self.assertEqual(row["state"], "failed")
        self.assertEqual(row.get("error_code"), "no_speech")
        self.assertEqual(row["error"], "no speech takes found in catalog")

    def test_an_uncoded_failure_leaves_the_field_ABSENT(self):
        """Not empty-string — absent. The desk asks "is there a code?" and
        an empty string that is present would send it looking for a door
        it does not have."""
        self._kind("t_code2", self._raiser(IngestError("catalog failed validation")))
        row = self._wait(jobs.start("t_code2", "x")["id"])
        self.assertEqual(row["state"], "failed")
        self.assertNotIn("error_code", row)
        self.assertEqual(row["error"], "catalog failed validation")

    def test_an_exception_that_is_not_an_IngestError_is_unaffected(self):
        self._kind("t_code3", self._raiser(ValueError("something else entirely")))
        row = self._wait(jobs.start("t_code3", "x")["id"])
        self.assertEqual(row["state"], "failed")
        self.assertNotIn("error_code", row)

    def test_a_non_string_code_is_ignored_rather_than_serialized(self):
        """The row is JSON on disk. `code` is a public attribute of an
        exception class anyone can raise, so a stray object must not be
        able to make the whole job store unwritable."""
        boom = IngestError("odd", code=object())
        self._kind("t_code4", self._raiser(boom))
        row = self._wait(jobs.start("t_code4", "x")["id"])
        self.assertEqual(row["state"], "failed")
        self.assertNotIn("error_code", row)


if __name__ == "__main__":
    unittest.main()
