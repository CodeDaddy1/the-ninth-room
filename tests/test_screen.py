# -*- coding: utf-8 -*-
"""The pre-screen sets footage aside; it never moves or deletes it.

2026-08-24. Ingest ran at 0.84x real time over 368 files, and a lens-cap
take costs exactly what a good one costs. The screen pays the cheap
checks first so the expensive stages — whisper, contact sheets — are
never spent on a clip that cannot be cut.

Two invariants are the whole reason this can run unattended:
  * nothing is moved or deleted, only flagged with a reason;
  * nothing judges CONTENT — only mechanically useless: no video, too
    short, all black, or a byte-identical duplicate.

Run: /usr/bin/python3 -m unittest discover -s tests -t .
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline import screen  # noqa: E402

FFMPEG = shutil.which("ffmpeg") or "/opt/homebrew/bin/ffmpeg"
HAVE_FFMPEG = os.path.exists(FFMPEG)


def entry(name="A.MP4", **kw):
    e = {"name": name, "path": "/f/" + name, "kind": "video",
         "duration": 12.0, "width": 3840, "height": 2160, "has_audio": True}
    e.update(kw)
    return e


class Flags(unittest.TestCase):
    def test_a_good_clip_has_no_flags(self):
        self.assertEqual(screen.screen_flags(entry(), {}), [])

    def test_a_fragment_is_too_short_to_cut(self):
        f = screen.screen_flags(entry(duration=0.4), {})
        self.assertTrue(any("too short" in x for x in f))

    def test_a_clip_at_the_floor_survives(self):
        self.assertEqual(screen.screen_flags(entry(duration=1.2), {}), [])

    def test_a_video_entry_with_no_stream_is_flagged(self):
        f = screen.screen_flags(entry(width=0), {})
        self.assertTrue(any("no video stream" in x for x in f))

    def test_the_second_copy_names_the_first(self):
        seen = {}
        a = entry("A.MP4", sig="deadbeef")
        b = entry("B.MP4", sig="deadbeef")
        self.assertEqual(screen.screen_flags(a, seen), [])
        f = screen.screen_flags(b, seen)
        self.assertEqual(f, ["identical to A.MP4"])

    def test_the_first_copy_is_never_the_one_set_aside(self):
        """Order matters: whoever arrives first is the keeper."""
        seen = {}
        screen.screen_flags(entry("A.MP4", sig="s"), seen)
        screen.screen_flags(entry("B.MP4", sig="s"), seen)
        self.assertEqual(seen["s"], "A.MP4")

    def test_re_screening_the_same_file_does_not_flag_itself(self):
        seen = {}
        e = entry("A.MP4", sig="s")
        screen.screen_flags(e, seen)
        self.assertEqual(screen.screen_flags(e, seen), [])


class Stamping(unittest.TestCase):
    def test_a_flagged_entry_is_stamped_not_mutated(self):
        e = entry(duration=0.2)
        out = screen.screen(e, {}, check_black=False)
        self.assertTrue(out["screened_out"])
        self.assertIn("too short", out["screen_reason"])
        self.assertNotIn("screened_out", e)   # the original is untouched

    def test_a_clean_entry_is_returned_unchanged(self):
        e = entry()
        self.assertIs(screen.screen(e, {}, check_black=False), e)

    def test_the_tally_reads_like_a_sentence(self):
        rows = [entry("A.MP4"),
                {"name": "B.MP4", "screened_out": True,
                 "screen_reason": "identical to A.MP4"},
                {"name": "C.MP4", "screened_out": True,
                 "screen_reason": "identical to A.MP4"},
                {"name": "D.MP4", "screened_out": True,
                 "screen_reason": "all black"}]
        self.assertEqual(screen.tally(rows),
                         "set aside 3 of 4 — 2 duplicate, 1 all black")

    def test_a_clean_batch_says_so(self):
        self.assertEqual(screen.tally([entry(), entry("B.MP4")]),
                         "set aside 0 of 2")


@unittest.skipUnless(HAVE_FFMPEG, "ffmpeg not available")
class BlackDetection(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _clip(self, name, src):
        p = self.tmp / name
        subprocess.run([FFMPEG, "-nostdin", "-loglevel", "error", "-y",
                        "-f", "lavfi", "-i", src, "-t", "3",
                        "-c:v", "libx264", "-crf", "24", "-pix_fmt",
                        "yuv420p", str(p)], check=True)
        return p

    def test_a_black_clip_is_found(self):
        p = self._clip("black.mp4", "color=c=black:s=320x240:r=12")
        self.assertTrue(screen.is_black(p, 3.0))

    def test_a_real_picture_is_not(self):
        p = self._clip("bars.mp4", "testsrc2=s=320x240:r=12")
        self.assertFalse(screen.is_black(p, 3.0))

    def test_a_clip_that_merely_fades_from_black_survives(self):
        """Fades live at the ENDS; the sample is taken from the middle,
        so a normal fade-in must not cost a clip its ingest."""
        p = self.tmp / "fade.mp4"
        subprocess.run([FFMPEG, "-nostdin", "-loglevel", "error", "-y",
                        "-f", "lavfi", "-i", "testsrc2=s=320x240:r=12",
                        "-t", "3", "-vf", "fade=in:0:12",
                        "-c:v", "libx264", "-crf", "24", "-pix_fmt",
                        "yuv420p", str(p)], check=True)
        self.assertFalse(screen.is_black(p, 3.0))

    def test_content_sig_agrees_with_itself_and_differs_across_files(self):
        a = self._clip("a.mp4", "testsrc2=s=320x240:r=12")
        b = self._clip("b.mp4", "color=c=red:s=320x240:r=12")
        sa = screen.content_sig(a, a.stat().st_size)
        self.assertEqual(sa, screen.content_sig(a, a.stat().st_size))
        self.assertNotEqual(sa, screen.content_sig(b, b.stat().st_size))


if __name__ == "__main__":
    unittest.main()


class ScreenedEntriesSurviveTheCatalog(unittest.TestCase):
    """The seam between screen.py and schemas.py, which nothing tested.

    Both modules were correct on their own. `screen()` stamps an entry
    with `screened_out` and a reason and — per its own contract — leaves
    it in the catalog so undoing a wrong call is editing one field rather
    than restoring a file. `validate_catalog()` requires `class` on every
    file. Ingest's screened-out branch `continue`d past both places that
    assign one.

    The result: the first mechanically-useless clip in a shoot failed the
    ENTIRE ingest at validation — "catalog.files[91]: missing 'class'" —
    and no catalog was written at all. A half-second fumbled record
    button took down a 368-file run (2026-08-26).

    These tests assert the contract across the seam, not inside either
    module, because that is where it broke.
    """

    def _entry(self, **over):
        e = {"name": "DJI_0091.MP4", "path": "/tmp/DJI_0091.MP4",
             "duration": 12.0, "kind": "video", "has_audio": False,
             "width": 3840, "height": 2160, "fps": 24}
        e.update(over)
        return e

    def test_a_screened_out_entry_is_a_valid_catalog_file(self):
        from pipeline import schemas
        # too short to cut — the cheapest screen, and the one that bit
        entry = screen.screen(self._entry(duration=0.4), {}, check_black=False)
        self.assertTrue(entry.get("screened_out"), "the fixture must screen out")
        entry["class"] = "broll"          # what ingest now stamps
        errors = schemas.validate_catalog(
            {"slug": "x", "files": [entry], "skipped": []})
        self.assertEqual(errors, [], "a set-aside clip must not fail the catalog")

    def test_ingest_stamps_the_class_itself(self):
        """The real guard: ingest's own branch, not a value re-typed here."""
        import re
        src = Path(__file__).resolve().parent.parent / "pipeline" / "ingest.py"
        body = src.read_text()
        # `continue` as a STATEMENT — matching the bare word stops inside
        # the branch's own comment, which says "continues past both places"
        m = re.search(r'if entry\.get\("screened_out"\):(.*?)\n\s+continue\n',
                      body, re.S)
        self.assertIsNotNone(m, "the screened-out branch moved — re-point this test")
        self.assertIn('entry["class"]', m.group(1),
                      "the screened-out branch must set a class before appending, "
                      "or the catalog fails validation on the first set-aside clip")

    def test_a_screened_out_clip_never_claims_to_be_speech(self):
        """Whisper never ran on it, so it carries no words_file — and
        validate_catalog rejects a speech file without one."""
        from pipeline import schemas
        entry = screen.screen(self._entry(duration=0.4), {}, check_black=False)
        entry["class"] = "speech"
        errors = schemas.validate_catalog(
            {"slug": "x", "files": [entry], "skipped": []})
        self.assertTrue(any("words_file" in e for e in errors),
                        "speech without a transcript must still be rejected")
