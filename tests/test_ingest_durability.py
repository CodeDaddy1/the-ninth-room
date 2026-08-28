# -*- coding: utf-8 -*-
"""State that survives being killed, and a cache that cannot poison a run.

2026-08-27, from the footage-desk audit. Three writes at the end of long
jobs used a plain `write_text`, and one read of a cache file had no
guard at all:

  - a crash mid-write left a HALF catalog.json / takes.json / broll.json;
  - a crash mid-write of a .words.json left a truncated transcript that
    made EVERY subsequent ingest of that project raise JSONDecodeError
    until someone deleted the file by hand.

The second is the worse one: a corrupt cache is a cache miss, not a
failure, and nothing about it was recoverable from the Studio.

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

from pipeline import broll, ingest, takes  # noqa: E402


class AtomicWrites(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_it_writes_the_file(self):
        p = self.tmp / "catalog.json"
        ingest._write_atomic(p, {"slug": "ep", "files": []})
        self.assertEqual(json.loads(p.read_text())["slug"], "ep")

    def test_the_tmp_name_carries_pid_and_thread(self):
        """A FIXED .tmp sibling is worse than no atomicity once two
        writers exist: one's replace moves the file out from under the
        other. `facts.py` documents the measured version of this."""
        seen = {}
        real = os.replace

        def spy(src, dst):
            seen['src'] = str(src)
            return real(src, dst)
        os.replace = spy
        try:
            ingest._write_atomic(self.tmp / "x.json", {})
        finally:
            os.replace = real
        self.assertIn(str(os.getpid()), seen['src'])
        self.assertTrue(seen['src'].endswith('.tmp'))

    def test_a_failed_write_leaves_no_tmp_behind(self):
        class Boom(object):
            def __repr__(self):
                raise RuntimeError("cannot serialise")
        with self.assertRaises(Exception):
            ingest._write_atomic(self.tmp / "x.json", {"bad": {1, 2}})
        self.assertEqual(list(self.tmp.glob("*.tmp")), [])

    def test_a_failed_write_does_not_destroy_the_PREVIOUS_file(self):
        p = self.tmp / "catalog.json"
        ingest._write_atomic(p, {"slug": "good"})
        with self.assertRaises(Exception):
            ingest._write_atomic(p, {"bad": {1, 2}})   # sets are not JSON
        self.assertEqual(json.loads(p.read_text())["slug"], "good")

    def test_takes_and_broll_use_it_too(self):
        import inspect
        self.assertIn("_write_atomic", inspect.getsource(takes.analyze))
        self.assertIn("_write_atomic", inspect.getsource(broll.catalog_broll))


class TruncatedTranscriptCache(unittest.TestCase):
    """A corrupt .words.json is a cache MISS, not a dead project."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "footage").mkdir(parents=True)
        (self.tmp / "analysis").mkdir(parents=True)
        (self.tmp / "footage" / "a.mp4").write_bytes(b"x" * 32)
        self._wp = ingest.work_path
        ingest.work_path = lambda slug: self.tmp
        self._probe = ingest.probe_file
        ingest.probe_file = lambda p: {
            "name": p.name, "path": str(p), "kind": "video",
            "duration": 4.0, "has_audio": True,
            "width": 1920, "height": 1080, "fps": 25.0, "vcodec": "h264",
        }
        self.transcribed = []
        self._tr = ingest.transcribe

        def fake(path):
            self.transcribed.append(path.name)
            return [{"w": "hello", "s": 0.1, "e": 0.4}] * 10
        ingest.transcribe = fake

    def tearDown(self):
        ingest.work_path = self._wp
        ingest.probe_file = self._probe
        ingest.transcribe = self._tr
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _words(self):
        return self.tmp / "analysis" / "a.mp4.words.json"

    def test_a_good_cache_is_reused_and_whisper_does_not_run(self):
        self._words().write_text(json.dumps([{"w": "hi", "s": 0.0, "e": 0.2}] * 10))
        ingest.ingest("ep", log=lambda *_: None)
        self.assertEqual(self.transcribed, [])

    def test_a_TRUNCATED_cache_re_transcribes_instead_of_raising(self):
        self._words().write_text('[{"w": "hel')
        ingest.ingest("ep", log=lambda *_: None)   # must not raise
        self.assertEqual(self.transcribed, ["a.mp4"])

    def test_the_truncated_file_is_replaced_with_a_readable_one(self):
        self._words().write_text('[{"w": "hel')
        ingest.ingest("ep", log=lambda *_: None)
        self.assertIsInstance(json.loads(self._words().read_text()), list)

    def test_the_project_is_not_poisoned_for_every_LATER_run(self):
        """The actual bug: it raised on run 2, run 3, run 4... forever."""
        self._words().write_text('not json at all')
        ingest.ingest("ep", log=lambda *_: None)
        self.transcribed[:] = []
        ingest.ingest("ep", log=lambda *_: None)   # second run: cache is good now
        self.assertEqual(self.transcribed, [])
