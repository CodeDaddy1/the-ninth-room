# -*- coding: utf-8 -*-
"""The master must be the size the cut is, and the pipeline must say so.

2026-08-27. Caleb asked why anything was 1080p when the Osmo Pocket 3
shoots 4K. It found a live bug: `deliver.render_master` set the render's
format, codec, target and frame range and NOTHING about size, so the
output resolution came from whichever of Resolve's 24 render presets
happened to be selected in its UI.

Measured at the time: source 4K HEVC, timeline 3840x2160, and three
masters on disk at 1920x1080 with a fourth at 4K — the signature of a
dropdown changing between runs. Nothing objected, because the only
resolution check on the live path asked `width >= 1920`, which 1920
satisfies exactly.

Two halves, and both are needed: PIN the size so the preset cannot
decide it, and MEASURE the result so a master that is wrong anyway
cannot be mistaken for one that is right.

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

from pipeline import deliver  # noqa: E402


class RenderIsPinned(unittest.TestCase):
    """The Lua that queues the render must set the output size.

    These read the source with COMMENTS STRIPPED. The first version did
    not, and every one of them passed with the fix deleted — because the
    comment explaining the fix still contained the word `FormatWidth`.
    A test that greps a file will happily match the prose about the code.
    """

    def _code(self):
        import inspect
        out = []
        for line in inspect.getsource(deliver.render_master).splitlines():
            t = line.strip()
            if t.startswith("--") or t.startswith("#"):
                continue
            out.append(line)
        return "\n".join(out)

    def test_it_sets_FormatWidth_and_FormatHeight(self):
        code = self._code()
        self.assertIn("FormatWidth = rw", code)
        self.assertIn("FormatHeight = rh", code)

    def test_the_size_comes_from_the_TIMELINE_not_a_constant(self):
        """A hardcoded 3840 would be wrong the day a portrait short is cut."""
        code = self._code()
        self.assertIn("tl:GetSetting('timelineResolutionWidth')", code)
        self.assertIn("tl:GetSetting('timelineResolutionHeight')", code)

    def test_it_refuses_rather_than_guessing_when_it_cannot_read_the_size(self):
        self.assertIn("could not read the timeline resolution", self._code())

    def test_it_reports_what_it_pinned(self):
        """So a mismatch can tell 'we asked wrong' from 'Resolve ignored us'."""
        self.assertIn("'JOB|' .. job .. '|'", self._code())

    def test_the_master_is_actually_MEASURED_on_this_path(self):
        """The helper existing is not the same as it being called. Deleting
        the call left every other test in this file green."""
        self.assertIn("_assert_master_matches_timeline(slug, final, pinned",
                      self._code())


class MasterIsMeasured(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.logged = []
        self._run = deliver.subprocess.run

    def tearDown(self):
        deliver.subprocess.run = self._run
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _probe_returns(self, w, h):
        class R(object):
            returncode = 0
            stdout = json.dumps({"streams": [{"width": w, "height": h}]})
            stderr = ""
        deliver.subprocess.run = lambda *a, **k: R()

    def test_a_matching_master_passes_quietly(self):
        self._probe_returns(3840, 2160)
        deliver._assert_master_matches_timeline(
            "ep", str(self.tmp / "m.mp4"), "3840x2160", log=self.logged.append)
        self.assertTrue(any("3840x2160" in x for x in self.logged))

    def test_a_1080p_master_from_a_4K_timeline_RAISES(self):
        """The actual bug. It used to ship."""
        self._probe_returns(1920, 1080)
        with self.assertRaises(RuntimeError) as cm:
            deliver._assert_master_matches_timeline(
                "ep", str(self.tmp / "m.mp4"), "3840x2160", log=lambda *_: None)
        msg = str(cm.exception)
        self.assertIn("1920x1080", msg)
        self.assertIn("3840x2160", msg)
        self.assertIn("render preset", msg)

    def test_the_failure_NAMES_the_file_rather_than_hiding_it(self):
        self._probe_returns(1920, 1080)
        with self.assertRaises(RuntimeError) as cm:
            deliver._assert_master_matches_timeline(
                "ep", str(self.tmp / "hmns_master_0827.mp4"), "3840x2160",
                log=lambda *_: None)
        self.assertIn("hmns_master_0827.mp4", str(cm.exception))

    def test_a_portrait_cut_is_judged_against_ITS_canvas(self):
        self._probe_returns(2160, 3840)
        deliver._assert_master_matches_timeline(
            "ep", str(self.tmp / "m.mp4"), "2160x3840", log=self.logged.append)
        self.assertTrue(self.logged)

    def test_an_unmeasurable_file_is_an_error_not_a_pass(self):
        class R(object):
            returncode = 1
            stdout = ""
            stderr = "moov atom not found"
        deliver.subprocess.run = lambda *a, **k: R()
        with self.assertRaises(RuntimeError):
            deliver._assert_master_matches_timeline(
                "ep", str(self.tmp / "m.mp4"), "3840x2160", log=lambda *_: None)

    def test_an_unreported_pin_logs_the_measurement_instead_of_crashing(self):
        """An older engine answering 'JOB|123' with no size must not blow up
        a render that already succeeded."""
        self._probe_returns(3840, 2160)
        deliver._assert_master_matches_timeline(
            "ep", str(self.tmp / "m.mp4"), "?", log=self.logged.append)
        self.assertTrue(any("3840x2160" in x for x in self.logged))
