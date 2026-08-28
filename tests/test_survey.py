# -*- coding: utf-8 -*-
"""Pass 1 must be cheap, resumable, and honest about what it could not read.

2026-08-27. Ingest was one pass: it transcribed every clip with audio
before a human had seen anything, and the desk's thumbnails were a side
effect of a GET that shelled ffprobe and ffmpeg while the browser waited.
The expensive work had the progress bar; the work that would let Caleb
decide anything was hidden inside a page load.

Survey is the cheap half on its own. It writes analysis/survey.json and
nothing downstream reads it but the desk and pass 2, so it can be re-run
or abandoned without the cut noticing.

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

from pipeline import ingest, survey  # noqa: E402
from pipeline.ingest import IngestError  # noqa: E402


class SurveyBasics(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "footage").mkdir(parents=True)
        self._wp, self._swp = ingest.work_path, survey.work_path
        ingest.work_path = lambda slug: self.tmp
        survey.work_path = lambda slug: self.tmp

    def tearDown(self):
        ingest.work_path = self._wp
        survey.work_path = self._swp
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _clip(self, name, body=b"not a video"):
        (self.tmp / "footage" / name).write_bytes(body)

    # ---- refusals ----

    def test_no_footage_dir_is_no_media(self):
        shutil.rmtree(self.tmp / "footage")
        with self.assertRaises(IngestError) as cm:
            survey.survey("ep", log=lambda *_: None)
        self.assertEqual(cm.exception.code, "no_media")

    def test_an_empty_shelf_is_no_media(self):
        with self.assertRaises(IngestError) as cm:
            survey.survey("ep", log=lambda *_: None)
        self.assertEqual(cm.exception.code, "no_media")

    # ---- one bad clip must not sink the run ----

    def test_an_unreadable_clip_is_set_aside_not_raised(self):
        self._clip("broken.mp4")
        survey.survey("ep", log=lambda *_: None)
        d = json.loads((self.tmp / "analysis" / "survey.json").read_text())
        self.assertEqual(d["files"], [])
        self.assertEqual(len(d["skipped"]), 1)
        self.assertEqual(d["skipped"][0]["name"], "broken.mp4")
        self.assertEqual(d["skipped"][0]["code"], "bad_file")

    def test_it_names_the_file_it_could_not_read(self):
        self._clip("A001.MP4")
        survey.survey("ep", log=lambda *_: None)
        d = json.loads((self.tmp / "analysis" / "survey.json").read_text())
        self.assertIn("A001.MP4", d["skipped"][0]["why"])

    # ---- what it walks ----

    def test_it_ignores_hidden_files_and_uploads_in_flight(self):
        self._clip(".DS_Store")
        self._clip("_tmp.A002.MP4")
        (self.tmp / "footage" / "notes.txt").write_text("hi")
        with self.assertRaises(IngestError) as cm:
            survey.survey("ep", log=lambda *_: None)
        self.assertEqual(cm.exception.code, "no_media")

    def test_audio_is_media_too(self):
        """Ingest has always analysed AUDIO_EXT; survey must see it as well
        or a .wav is transcribed and shown on no screen."""
        self._clip("interview.wav")
        survey.survey("ep", log=lambda *_: None)
        d = json.loads((self.tmp / "analysis" / "survey.json").read_text())
        # unreadable stub, but it was WALKED — it reached the skip list
        self.assertEqual(d["skipped"][0]["name"], "interview.wav")

    # ---- the file it writes ----

    def test_a_half_written_survey_reads_as_no_survey(self):
        (self.tmp / "analysis").mkdir(parents=True, exist_ok=True)
        survey.survey_path("ep").write_text('{"slug": "ep", "files": [{"na')
        self.assertIsNone(survey.read_survey("ep"))

    def test_a_survey_without_a_files_list_is_not_a_survey(self):
        (self.tmp / "analysis").mkdir(parents=True, exist_ok=True)
        survey.survey_path("ep").write_text('{"slug": "ep"}')
        self.assertIsNone(survey.read_survey("ep"))

    def test_no_survey_at_all_is_None_not_an_error(self):
        self.assertIsNone(survey.read_survey("ep"))

    def test_the_write_is_atomic(self):
        """A fixed .tmp sibling is the multi-writer hazard facts.py
        documents; the name must carry pid and thread."""
        self._clip("broken.mp4")
        survey.survey("ep", log=lambda *_: None)
        leftovers = list((self.tmp / "analysis").glob("*.tmp"))
        self.assertEqual(leftovers, [])
        self.assertTrue(survey.survey_path("ep").exists())


class SurveyResume(unittest.TestCase):
    """A survey killed at clip 90 of 148 must not redo the first 89."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "footage").mkdir(parents=True)
        (self.tmp / "analysis").mkdir(parents=True)
        self._wp, self._swp = ingest.work_path, survey.work_path
        ingest.work_path = lambda slug: self.tmp
        survey.work_path = lambda slug: self.tmp
        self.probed = []
        self._probe = survey.probe_file

        def counting(path):
            self.probed.append(path.name)
            return {"name": path.name, "path": str(path), "kind": "video",
                    "duration": 4.0, "has_audio": False,
                    "width": 1920, "height": 1080, "fps": 25.0,
                    "vcodec": "h264"}
        survey.probe_file = counting
        survey._poster = lambda src, dest, dur: (dest.write_bytes(b"jpg"), True)[1]
        survey._proxy = lambda src, dest: (dest.write_bytes(b"mp4"), True)[1]
        # DIFFERENT bytes per clip: identical content is a duplicate, and
        # screen.py sets duplicates aside — which is correct, and would
        # quietly halve every count in this class if the fixture ignored it.
        for i, n in enumerate(("A.mp4", "B.mp4")):
            (self.tmp / "footage" / n).write_bytes(bytes([65 + i]) * 64)

    def tearDown(self):
        ingest.work_path = self._wp
        survey.work_path = self._swp
        survey.probe_file = self._probe
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_a_second_run_reprobes_nothing(self):
        survey.survey("ep", log=lambda *_: None)
        self.assertEqual(sorted(self.probed), ["A.mp4", "B.mp4"])
        self.probed[:] = []
        survey.survey("ep", log=lambda *_: None)
        self.assertEqual(self.probed, [])

    def test_a_CHANGED_file_is_re_read(self):
        survey.survey("ep", log=lambda *_: None)
        self.probed[:] = []
        p = self.tmp / "footage" / "A.mp4"
        p.write_bytes(b"Z" * 128)          # different size
        survey.survey("ep", log=lambda *_: None)
        self.assertEqual(self.probed, ["A.mp4"])

    def test_a_DELETED_poster_is_remade(self):
        survey.survey("ep", log=lambda *_: None)
        (self.tmp / "footage" / ".thumbs" / "A.mp4.jpg").unlink()
        self.probed[:] = []
        survey.survey("ep", log=lambda *_: None)
        self.assertEqual(self.probed, ["A.mp4"])

    def test_force_redoes_everything(self):
        survey.survey("ep", log=lambda *_: None)
        self.probed[:] = []
        survey.survey("ep", log=lambda *_: None, force=True)
        self.assertEqual(sorted(self.probed), ["A.mp4", "B.mp4"])

    def test_posters_are_written_BEFORE_any_preview(self):
        """Phase A must land on disk first, or the desk shows placeholders
        for the length of a full transcode and the split bought nothing."""
        order = []
        survey._poster = lambda src, dest, dur: (
            order.append("poster"), dest.write_bytes(b"jpg"), True)[2]
        survey._proxy = lambda src, dest: (
            order.append("proxy"), dest.write_bytes(b"mp4"), True)[2]
        survey.survey("ep", log=lambda *_: None)
        self.assertEqual(order, ["poster", "poster", "proxy", "proxy"])

    def test_a_screened_out_clip_gets_no_preview(self):
        """An encode of footage already set aside is spent for nothing."""
        made = []
        survey._proxy = lambda src, dest: (made.append(dest.name), True)[1]
        real_screen = survey.screen_mod.screen
        survey.screen_mod.screen = lambda e, seen, **kw: dict(
            e, screened_out=True, screen_reason="too short to cut")
        try:
            survey.survey("ep", log=lambda *_: None)
        finally:
            survey.screen_mod.screen = real_screen
        self.assertEqual(made, [])


class PosterFrame(unittest.TestCase):
    """The poster must not come from frame 0, and the seek must be cheap.

    2026-08-27: the first cut of `_run_ffmpeg` dropped `-ss` entirely, so
    every poster was frame 0 — routinely a fade-in, a lens still racking,
    or the operator's hand. The one frame that cannot tell you whether a
    clip is worth keeping, on the desk whose whole job is that judgment.
    No existing test could see it: the file was written, so the survey
    reported success.

    `-ss` BEFORE `-i` is the other half. After `-i` it is an output
    option and ffmpeg decodes from the start to reach the seek point,
    which on 4K HEVC costs the entire decode.
    """

    def setUp(self):
        self.cmds = []
        self._run = survey.subprocess.run

        class R(object):
            returncode = 0

        def spy(cmd, **kw):
            self.cmds.append(cmd)
            # pretend ffmpeg wrote the file it was asked for
            Path(cmd[-1]).write_bytes(b"x")
            return R()
        survey.subprocess.run = spy

    def tearDown(self):
        survey.subprocess.run = self._run

    def test_the_poster_seeks_into_the_clip(self):
        survey._poster(Path("/x/a.mp4"), Path(tempfile.mkdtemp()) / "a.jpg", 10.0)
        cmd = self.cmds[0]
        self.assertIn("-ss", cmd)
        self.assertNotEqual(cmd[cmd.index("-ss") + 1], "0.00")

    def test_the_seek_comes_BEFORE_the_input(self):
        survey._poster(Path("/x/a.mp4"), Path(tempfile.mkdtemp()) / "a.jpg", 10.0)
        cmd = self.cmds[0]
        self.assertLess(cmd.index("-ss"), cmd.index("-i"))

    def test_a_zero_duration_clip_still_seeks_to_a_valid_point(self):
        survey._poster(Path("/x/a.mp4"), Path(tempfile.mkdtemp()) / "a.jpg", 0.0)
        cmd = self.cmds[0]
        self.assertEqual(cmd[cmd.index("-ss") + 1], "0.00")

    def test_hardware_decode_is_tried_first(self):
        survey._poster(Path("/x/a.mp4"), Path(tempfile.mkdtemp()) / "a.jpg", 10.0)
        self.assertIn("-hwaccel", self.cmds[0])

    def test_a_hwaccel_failure_retries_in_software(self):
        class Fail(object):
            returncode = 1
        calls = []

        def flaky(cmd, **kw):
            calls.append(cmd)
            if "-hwaccel" in cmd:
                return Fail()
            Path(cmd[-1]).write_bytes(b"x")

            class Ok(object):
                returncode = 0
            return Ok()
        survey.subprocess.run = flaky
        out = Path(tempfile.mkdtemp()) / "a.jpg"
        self.assertTrue(survey._poster(Path("/x/a.mp4"), out, 10.0))
        self.assertEqual(len(calls), 2)
        self.assertNotIn("-hwaccel", calls[1])
