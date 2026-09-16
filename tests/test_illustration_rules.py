# -*- coding: utf-8 -*-
"""The rules an illustration is held to, and the doors that hold them.

Decision 13 (docs/decisions-illustrations.md): an illustration may cover
a beat as an `illustrate` cutaway when the footage is weak; never as an
`establish`, never in the hook, never on a peak, never past the cover
ceiling, never in the landing. Decision 17: the desk's attach route gains
a `why`, the Library's delete verb gains the footage guard, the thumbnail
never comes from a generated frame, the still door honours the delivery
orientation, and a promoted illustration is resampled to the canvas.

Two lengths used to disagree: `_broll_attach` measured a beat by its
record span and `coverage_notes` by its trim, so the same cover could be
fifty-nine percent on the desk and sixty-two in the coverage job.
`schemas.beat_span` is the one number both read now: the trim minus the
beat's own hard cuts.

Run: /usr/bin/python3 -m unittest discover -s tests -t .
"""
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline import cutbar, editroom, schemas  # noqa: E402
from pipeline.ingest import IngestError  # noqa: E402

BROLL = {"slug": "ep", "clips": [
    {"id": "B001", "file": "hall.mp4", "duration": 30.0, "sheet": "s.jpg"},
    {"id": "B009", "file": "egg.mp4", "duration": 5.0, "sheet": "s.jpg",
     "provenance": "illustration"},
    {"id": "B010", "file": "plaza.mp4", "duration": 8.0, "sheet": "s.jpg",
     "provenance": "reconstruction"},
]}


def _beat(bid, covers, **extra):
    b = {"id": bid, "purpose": "build", "take_id": "T01",
         "trim": {"s": 10.0, "e": 20.0}, "broll": covers}
    b.update(extra)
    return b


class BeatSpan(unittest.TestCase):
    def test_a_trim_without_cuts_is_its_own_length(self):
        self.assertAlmostEqual(schemas.beat_span({"trim": {"s": 10.0, "e": 16.57}}), 6.57)

    def test_hard_cuts_inside_the_trim_come_off(self):
        b = {"trim": {"s": 18.94, "e": 25.51}, "cuts": [{"s": 18.94, "e": 20.45}]}
        self.assertAlmostEqual(schemas.beat_span(b), 5.06)

    def test_cuts_are_clipped_to_the_trim_and_merged(self):
        b = {"trim": {"s": 10.0, "e": 20.0},
             "cuts": [{"s": 5.0, "e": 12.0}, {"s": 11.0, "e": 13.0}, {"s": 19.0, "e": 30.0}]}
        self.assertAlmostEqual(schemas.beat_span(b), 6.0)

    def test_no_trim_is_zero(self):
        self.assertEqual(schemas.beat_span({}), 0.0)

    def test_coverage_notes_reads_the_same_number(self):
        # 3.5 s on a 5.06 s beat is sixty-nine percent: over the ceiling
        # only once the cuts are honoured
        plan = {"beats": [_beat("b", [{"clip_id": "B001", "at": 0.0, "duration": 3.5,
                                       "why": "illustrate: the board"}],
                               trim={"s": 18.94, "e": 25.51},
                               cuts=[{"s": 18.94, "e": 20.45}])]}
        notes = schemas.coverage_notes(plan)
        self.assertTrue(any("covered" in n for n in notes), notes)


class FillGate(unittest.TestCase):
    def test_only_a_portrait_clip_on_a_landscape_project_is_filled(self):
        from pipeline import fill
        self.assertTrue(fill.wanted("landscape", 2160, 3840))
        self.assertFalse(fill.wanted("portrait", 2160, 3840))
        self.assertFalse(fill.wanted("landscape", 3840, 2160))


class HookBeatIds(unittest.TestCase):
    def test_everything_before_the_first_chapter_open(self):
        plan = {"beats": [{"id": "h1", "purpose": "hook"}, {"id": "h2", "purpose": "build"},
                          {"id": "c1", "purpose": "chapter_open"}, {"id": "c2", "purpose": "build"}]}
        self.assertEqual(cutbar.hook_beat_ids(plan), ["h1", "h2"])

    def test_a_short_with_no_chapter_open_has_no_hook_run(self):
        self.assertEqual(cutbar.hook_beat_ids({"beats": [{"id": "a", "purpose": "hook"}]}), [])


class IllustrationNotes(unittest.TestCase):
    def notes(self, beats, takes=None):
        return schemas.illustration_notes({"beats": beats}, BROLL, takes or {"takes": []})

    def test_a_camera_cover_is_never_mentioned(self):
        self.assertEqual(self.notes([_beat("b", [
            {"clip_id": "B001", "at": 0.0, "duration": 8.0}])]), [])

    def test_an_illustration_needs_a_why_that_is_not_establish(self):
        no_why = self.notes([_beat("b", [{"clip_id": "B009", "at": 0.0, "duration": 3.0}])])
        establish = self.notes([_beat("b", [{"clip_id": "B009", "at": 0.0, "duration": 3.0,
                                              "why": "establish: the hall"}])])
        fine = self.notes([_beat("b", [{"clip_id": "B009", "at": 0.0, "duration": 3.0,
                                         "why": "illustrate: the egg on the board"}])])
        self.assertEqual(len(no_why), 1); self.assertIn("why", no_why[0])
        self.assertEqual(len(establish), 1); self.assertIn("establish", establish[0])
        self.assertEqual(fine, [])

    def test_never_in_the_hook_never_on_a_peak(self):
        cover = [{"clip_id": "B009", "at": 0.0, "duration": 3.0, "why": "illustrate: x"}]
        hook = self.notes([_beat("h", cover, purpose="hook"),
                           _beat("c", [], purpose="chapter_open")])
        peak = self.notes([_beat("p", cover, peak=True)])
        self.assertEqual(len(hook), 1); self.assertIn("hook", hook[0])
        self.assertEqual(len(peak), 1); self.assertIn("peak", peak[0])

    def test_the_ceiling_and_the_landing_are_measured_on_beat_span(self):
        over = self.notes([_beat("b", [{"clip_id": "B009", "at": 0.0, "duration": 6.5,
                                        "why": "illustrate: x"}])])
        landing = self.notes([_beat("b", [{"clip_id": "B009", "at": 6.0, "duration": 3.0,
                                           "why": "illustrate: x"}])])
        self.assertTrue(any("%" in n for n in over), over)
        self.assertTrue(any("landing" in n for n in landing), landing)

    def test_a_voice_over_beat_may_be_fully_covered(self):
        takes = {"takes": [{"id": "T01", "file": "vo_read.mp4", "kind": "vo"}]}
        self.assertEqual(self.notes([_beat("b", [
            {"clip_id": "B009", "at": 0.0, "duration": 10.0, "why": "illustrate: x"}])],
            takes), [])

    def test_a_reconstruction_spine_in_the_hook_is_refused(self):
        beats = [{"id": "h", "purpose": "hook", "spine": {"clip_id": "B010", "src_s": 0, "src_e": 4},
                  "broll": []},
                 {"id": "c", "purpose": "chapter_open", "take_id": "T01", "broll": []}]
        notes = self.notes(beats)
        self.assertEqual(len(notes), 1); self.assertIn("hook", notes[0])

    def test_validate_edit_plan_carries_them(self):
        takes = {"takes": [{"id": "T01", "file": "a.mp4", "s": 0.0, "e": 30.0,
                            "transcript": "words"}]}
        plan = {"slug": "ep", "beats": [_beat("b", [
            {"clip_id": "B009", "at": 0.0, "duration": 3.0, "why": "establish: x"}])]}
        errors = schemas.validate_edit_plan(plan, takes, BROLL)
        self.assertTrue(any("establish" in e for e in errors), errors)


if __name__ == "__main__":
    unittest.main()


class _Doors(unittest.TestCase):
    """A temp project with one camera clip, one illustration on the shelf
    promoted as egg.mp4, and one beat; the desk verbs run against it."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        for d in ("analysis", "assets", "footage", "proxies"):
            (self.tmp / d).mkdir()
        (self.tmp / "assets" / "egg.mp4").write_bytes(b"v" * 16)
        (self.tmp / "assets" / "plate.png").write_bytes(b"p" * 16)
        (self.tmp / "assets" / "stock.mp4").write_bytes(b"s" * 16)
        (self.tmp / "footage" / "egg.mp4").write_bytes(b"v" * 16)
        (self.tmp / "assets" / "assets.json").write_text(json.dumps({"assets": [
            {"id": "egg", "file": "egg.mp4", "kind": "illustration", "honesty": "illustration",
             "promoted_as": "egg.mp4", "model": "kling3_0", "cost_credits": 7.5,
             "license": "Higgsfield ToU: output owned, commercial use permitted"},
            {"id": "plate", "file": "plate.png", "kind": "illustration",
             "honesty": "reconstruction", "model": "nano_banana_pro", "cost_credits": 2.0,
             "license": "Higgsfield ToU: output owned, commercial use permitted"},
            {"id": "stock", "file": "stock.mp4", "kind": "video", "license": "CC0"}]}))
        (self.tmp / "analysis" / "broll.json").write_text(json.dumps({"slug": "ep", "clips": [
            {"id": "B001", "file": "hall.mp4", "duration": 30.0, "sheet": "s.jpg"},
            {"id": "B009", "file": "egg.mp4", "duration": 5.0, "sheet": "s.jpg",
             "provenance": "illustration"}]}))
        (self.tmp / "analysis" / "takes.json").write_text(json.dumps({"takes": [
            {"id": "T01", "file": "a.mp4", "s": 0.0, "e": 30.0, "transcript": "x"}]}))
        (self.tmp / "analysis" / "timeline_map.json").write_text(json.dumps({"beats": [
            {"id": "BT01", "record_s": 100.0, "record_e": 105.38, "broll": []},
            {"id": "BT02", "record_s": 105.38, "record_e": 110.0, "broll": [
                {"clip_id": "B009", "file": "egg.mp4", "record_s": 106.0,
                 "duration": 3.0, "src_s": 0.0, "provenance": "illustration"}]}]}))
        (self.tmp / "edit_plan.json").write_text(json.dumps({"slug": "ep", "beats": [
            {"id": "BT01", "purpose": "build", "take_id": "T01",
             "trim": {"s": 18.94, "e": 25.51}, "cuts": [{"s": 18.94, "e": 20.45}], "broll": []},
            {"id": "BT02", "purpose": "build", "take_id": "T01",
             "trim": {"s": 30.0, "e": 35.0}, "broll": [
                 {"clip_id": "B009", "at": 0.5, "duration": 2.5, "src_s": 0.0,
                  "why": "illustrate: the egg"}]}]}))
        self._wp = editroom.work_path
        editroom.work_path = lambda slug: self.tmp
        self._cat = editroom._broll_catalog
        editroom._broll_catalog = lambda slug: json.loads(
            (self.tmp / "analysis" / "broll.json").read_text())["clips"]
        self._conf, self._mark = editroom._conform_append, editroom._mark_edited
        editroom._conform_append = lambda *a, **k: None
        editroom._mark_edited = lambda *a, **k: None
        from pipeline import proxy as proxy_mod
        self.proxy_mod, self._proxy = proxy_mod, proxy_mod.build
        proxy_mod.build = lambda *a, **k: None

    def tearDown(self):
        editroom.work_path = self._wp
        editroom._broll_catalog = self._cat
        editroom._conform_append, editroom._mark_edited = self._conf, self._mark
        self.proxy_mod.build = self._proxy
        shutil.rmtree(self.tmp, ignore_errors=True)

    def attach(self, clip_id, at, duration, why=None, beat="BT01"):
        return editroom._broll_attach("ep", beat, clip_id, at, duration, 0.0,
                                      why=why, log=lambda *a: None)


class AttachDoor(_Doors):
    def test_an_illustrate_cover_under_the_ceiling_is_placed_with_its_why(self):
        self.attach("B009", 0.0, 3.0, why="illustrate: the egg on the board")
        plan = json.loads((self.tmp / "edit_plan.json").read_text())
        cover = plan["beats"][0]["broll"][0]
        self.assertEqual(cover["why"], "illustrate: the egg on the board")

    def test_no_why_is_refused_once_the_catalog_holds_an_illustration(self):
        with self.assertRaises(IngestError):
            self.attach("B001", 0.0, 3.0)

    def test_establish_and_the_ceiling_are_refused_at_the_desk(self):
        with self.assertRaises(IngestError) as cm:
            self.attach("B009", 0.0, 3.0, why="establish: the hall")
        self.assertIn("establish", str(cm.exception))
        with self.assertRaises(IngestError) as cm:
            self.attach("B009", 0.0, 3.5, why="illustrate: the egg")
        self.assertIn("%", str(cm.exception))
        plan = json.loads((self.tmp / "edit_plan.json").read_text())
        self.assertEqual(plan["beats"][0]["broll"], [], "a refusal must write nothing")


class DeleteDoor(_Doors):
    def test_a_promoted_illustration_in_the_cut_cannot_be_deleted(self):
        with self.assertRaises(IngestError) as cm:
            editroom._delete_asset("ep", "egg")
        self.assertEqual(cm.exception.code, "in_the_cut")
        self.assertTrue((self.tmp / "assets" / "egg.mp4").is_file())

    def test_an_asset_not_in_the_cut_still_goes(self):
        editroom._delete_asset("ep", "stock")
        self.assertFalse((self.tmp / "assets" / "stock.mp4").exists())


class ThumbnailDoor(_Doors):
    def test_a_frame_under_an_illustration_cover_is_refused(self):
        (self.tmp / "proxies" / "BT02.0.mp4").write_bytes(b"m")
        with self.assertRaises(IngestError) as cm:
            editroom._bake_thumbnail("ep", "BT02", 1.0, "Title", log=lambda *a: None)
        self.assertIn("illustration", str(cm.exception))


class UseDoor(_Doors):
    def test_the_pure_argvs_carry_the_orientation(self):
        args = editroom._still_to_clip_args(Path("/a/p.png"), Path("/f/p_still.mp4"), "portrait")
        self.assertIn("scale=2160:3840:force_original_aspect_ratio=increase,crop=2160:3840,fps=24,format=yuv420p", " ".join(args))
        args = editroom._resample_args(Path("/a/egg.mp4"), Path("/f/egg.mp4"), (3840, 2160))
        joined = " ".join(args)
        self.assertIn("scale=3840:2160", joined)
        self.assertIn("lanczos", joined)

    def test_promoting_an_illustration_resamples_and_records_the_name(self):
        (self.tmp / "footage" / "egg.mp4").unlink()
        calls = []
        def fake_run(cmd, **kw):
            calls.append(cmd)
            # only the resample writes its output; the encoder probe
            # (`ffmpeg -encoders`) must not leave a file in the cwd
            if any("scale=" in str(a) for a in cmd):
                Path(cmd[-1]).write_bytes(b"out")
            return mock.Mock(returncode=0, stderr="", stdout="")
        with mock.patch.object(editroom.subprocess, "run", fake_run), \
                mock.patch.object(editroom, "_orientation", lambda slug: "landscape"), \
                mock.patch("pipeline.jobs.note_upload", lambda slug: None):
            out = editroom._use_asset("ep", "egg")
        self.assertEqual(out["as"], "egg.mp4")
        self.assertFalse((self.tmp / "footage" / "egg.mp4").is_symlink(), "resampled, not linked")
        self.assertTrue(any("scale=3840:2160" in " ".join(c) for c in calls))
        row = [a for a in json.loads((self.tmp / "assets" / "assets.json").read_text())["assets"]
               if a["id"] == "egg"][0]
        self.assertEqual(row["promoted_as"], "egg.mp4")

    def test_a_stock_video_is_still_linked(self):
        with mock.patch("pipeline.jobs.note_upload", lambda slug: None):
            out = editroom._use_asset("ep", "stock")
        self.assertTrue((self.tmp / "footage" / out["as"]).is_symlink())


class AssetsState(_Doors):
    def test_illustration_rows_keep_their_kind_and_gain_a_media_kind(self):
        with mock.patch.object(editroom.subprocess, "run",
                               lambda *a, **k: mock.Mock(returncode=0)):
            state = editroom._assets_state("ep")
        by_id = {a["id"]: a for a in state["assets"]}
        self.assertEqual(by_id["egg"]["kind"], "illustration")
        self.assertEqual(by_id["egg"]["media_kind"], "video")
        self.assertEqual(by_id["plate"]["media_kind"], "image")
        self.assertEqual(by_id["egg"]["model"], "kling3_0")
        self.assertEqual(by_id["stock"]["kind"], "video")
        self.assertEqual(by_id["egg"]["clip_id"], "B009")
