# -*- coding: utf-8 -*-
"""What a Footage-desk trim does to everything downstream of it.

Caleb, 2026-08-28: "edit the clip by manually cutting with a scrubber
during the footage ranking process." `facts` owns the sidecar; this file
is about the four stages that have to OBEY it — take analysis, the b-roll
catalog, the timeline, and the plan validator.

THE RULE THESE TESTS EXIST FOR: a trim may never cause a take to be
dropped or renumbered. Take ids are positional (`"T%02d" % (len(takes) +
1)`, takes.py, assigned in catalog order) and `edit_plan.json` references
them BY NAME, so a single dropped take shifts every later id and silently
re-points built beats at different footage. broll.py:218-245 documents the
same failure for b-roll ids, where it had already happened. So the first
class below asserts the id SEQUENCE, not just that ids exist.

The second thing under test is that an untrimmed project is byte-for-byte
what it was before trims existed — every trimmed path resolves to
`(0, duration)`, which is the same arithmetic, not a second branch.

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

from PIL import Image  # noqa: E402

from pipeline import broll, facts, ingest, schemas, takes, timeline  # noqa: E402
from pipeline.ingest import IngestError  # noqa: E402

WORK = Path(__file__).resolve().parent.parent / "work"

# One speech file, three runs of words separated by more than
# TAKE_SPLIT_GAP_SEC. Chosen so a window can be drawn that excludes the
# first and the last outright and clips the middle one at either edge.
WORDS = [
    {"s": 1.0, "e": 1.4, "w": "Hello"},
    {"s": 1.5, "e": 2.0, "w": "world."},

    {"s": 10.0, "e": 10.4, "w": "This"},
    {"s": 10.5, "e": 11.0, "w": "is"},
    {"s": 11.1, "e": 12.0, "w": "fine."},

    {"s": 20.0, "e": 20.5, "w": "Bad"},
    {"s": 20.6, "e": 21.0, "w": "walk"},
    {"s": 21.1, "e": 21.6, "w": "up."},
]


class Sandbox(unittest.TestCase):
    """Every stage resolves work_path through the ingest MODULE, and so
    does `facts` — patching it there is what keeps a test out of the real
    shelf (facts.work_path's docstring: a test once wrote a phantom
    project onto the Studio's board)."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.analysis = self.tmp / "analysis"
        self.analysis.mkdir(parents=True)
        self._iwp = ingest.work_path
        self._saved = {
            "takes.analysis_dir": takes.analysis_dir,
            "broll.analysis_dir": broll.analysis_dir,
            "broll.work_path": broll.work_path,
            "timeline.work_path": timeline.work_path,
            "timeline.analysis_dir": timeline.analysis_dir,
            "takes.span_volume_db": takes.span_volume_db,
            "takes.take_thumb": takes.take_thumb,
        }
        ingest.work_path = lambda slug: self.tmp
        takes.analysis_dir = lambda slug: self.analysis
        broll.analysis_dir = lambda slug: self.analysis
        broll.work_path = lambda slug: self.tmp
        timeline.work_path = lambda slug: self.tmp
        timeline.analysis_dir = lambda slug: self.analysis
        # no ffmpeg in a unit test: both of these shell out per take
        takes.span_volume_db = lambda *a, **k: None
        takes.take_thumb = lambda *a, **k: False
        self._before = set(p.name for p in WORK.iterdir()) if WORK.is_dir() else set()

    def tearDown(self):
        ingest.work_path = self._iwp
        takes.analysis_dir = self._saved["takes.analysis_dir"]
        broll.analysis_dir = self._saved["broll.analysis_dir"]
        broll.work_path = self._saved["broll.work_path"]
        timeline.work_path = self._saved["timeline.work_path"]
        timeline.analysis_dir = self._saved["timeline.analysis_dir"]
        takes.span_volume_db = self._saved["takes.span_volume_db"]
        takes.take_thumb = self._saved["takes.take_thumb"]
        shutil.rmtree(self.tmp, ignore_errors=True)
        after = set(p.name for p in WORK.iterdir()) if WORK.is_dir() else set()
        self.assertEqual(after - self._before, set(),
                         "the test wrote into the REAL work dir")

    # --- fixtures ----------------------------------------------------

    def speech_file(self, name="a.mov", duration=30.0, words=None):
        (self.analysis / (name + ".words.json")).write_text(
            json.dumps(WORDS if words is None else words))
        return {"name": name, "path": str(self.tmp / name), "kind": "video",
                "class": "speech", "duration": duration, "fps": 30.0,
                "has_audio": True, "words_file": name + ".words.json",
                "silence": []}

    def broll_file(self, name="clip.mov", duration=100.0):
        p = self.tmp / name
        if not p.exists():
            p.write_bytes(b"\x00")
        return {"name": name, "path": str(p), "kind": "video",
                "class": "broll", "duration": duration, "fps": 30.0,
                "width": 1920, "height": 1080}

    def catalog(self, *files):
        (self.analysis / "catalog.json").write_text(
            json.dumps({"slug": "ep", "files": list(files), "skipped": []}))

    def analyze(self):
        takes.analyze("ep", log=lambda *a: None)
        return json.loads((self.analysis / "takes.json").read_text())


class ATrimNeverCostsATakeItsId(Sandbox):
    """THE REGRESSION THAT MATTERS MOST."""

    def setUp(self):
        Sandbox.setUp(self)
        self.catalog(self.speech_file())

    def test_the_id_sequence_is_identical_with_and_without_a_trim(self):
        before = [t["id"] for t in self.analyze()["takes"]]
        # a window that excludes the first take and the last one entirely
        facts.set_trim("ep", "a.mov", 9.0, 13.0)
        after = self.analyze()["takes"]
        self.assertEqual([t["id"] for t in after], before)
        self.assertEqual(before, ["T01", "T02", "T03"])
        self.assertEqual([t["file"] for t in after], ["a.mov"] * 3)

    def test_a_take_outside_the_window_is_marked_not_removed(self):
        facts.set_trim("ep", "a.mov", 9.0, 13.0)
        by_id = {t["id"]: t for t in self.analyze()["takes"]}
        for tid in ("T01", "T03"):
            self.assertTrue(by_id[tid]["screened_out"], tid)
            self.assertEqual(by_id[tid]["screen_reason"],
                             "outside the clip's trim")
        self.assertNotIn("screened_out", by_id["T02"],
                         "a take inside the window is untouched")

    def test_a_marked_take_keeps_its_own_words_and_bounds(self):
        """It describes real footage; it is excluded, not rewritten. The
        Takes desk still shows what was said there."""
        facts.set_trim("ep", "a.mov", 9.0, 13.0)
        t = {x["id"]: x for x in self.analyze()["takes"]}["T01"]
        self.assertEqual(t["transcript"], "Hello world.")
        self.assertEqual((t["s"], t["e"]), (1.0, 2.0))

    def test_the_plan_validator_already_refuses_the_marked_take(self):
        """No new field: `screened_out` is the one schemas.py enforces and
        the Takes desk renders. This is why the mark is worth anything."""
        facts.set_trim("ep", "a.mov", 9.0, 13.0)
        tk = self.analyze()
        plan = {"slug": "ep", "format": "youtube_short",
                "theme": {"problem": "p", "promise": "q", "payoff": "r"},
                "beats": [{"id": "BT01", "purpose": "hook", "take_id": "T01"}]}
        errs = schemas.validate_edit_plan(plan, tk, {"clips": []})
        self.assertTrue(
            any("was screened out — outside the clip's trim" in e for e in errs),
            errs)

    def test_a_window_that_excludes_everything_still_emits_every_take(self):
        """The worst input: nothing survives. All three takes must still be
        there, in order — a trim is never allowed to shorten the list."""
        facts.set_trim("ep", "a.mov", 25.0, 29.0)
        out = self.analyze()["takes"]
        self.assertEqual([t["id"] for t in out], ["T01", "T02", "T03"])
        self.assertTrue(all(t["screened_out"] for t in out))

    def test_a_zero_length_word_inside_the_window_is_still_kept(self):
        """A point is CONTAINED by a window, not overlapping it — the
        clause `_word_in` carries for whisper's 0.000-0.000 stamps, doing
        its job at a real trim boundary rather than at zero."""
        self.catalog(self.speech_file(words=[
            {"s": 1.0, "e": 1.4, "w": "Before"},
            {"s": 12.0, "e": 12.0, "w": "Point."},
        ]))
        facts.set_trim("ep", "a.mov", 10.0, 15.0)
        out = self.analyze()["takes"]
        self.assertEqual([t["id"] for t in out], ["T01", "T02"])
        self.assertEqual(out[1]["transcript"], "Point.")
        self.assertNotIn("screened_out", out[1])

    def test_a_zero_length_word_at_the_trim_edge_is_not_dropped(self):
        """The zero-length guard is the one path that CAN drop a take, and
        a trim must never be the reason it fires. Whisper stamped
        'literally.' at 29.98-29.98 on a real clip's last frame."""
        self.catalog(self.speech_file(words=[
            {"s": 1.0, "e": 1.4, "w": "Hello"},
            {"s": 11.98, "e": 11.98, "w": "literally."},
        ]))
        before = [t["id"] for t in self.analyze()["takes"]]
        facts.set_trim("ep", "a.mov", 5.0, 12.0)
        after = self.analyze()["takes"]
        self.assertEqual([t["id"] for t in after], before)
        self.assertEqual(len(after), 2)
        self.assertGreater(after[1]["e"], after[1]["s"])


class AStraddlingTakeIsClamped(Sandbox):

    def setUp(self):
        Sandbox.setUp(self)
        self.catalog(self.speech_file())

    def take(self, tid="T02"):
        return {t["id"]: t for t in self.analyze()["takes"]}[tid]

    def test_the_head_is_clamped_and_the_transcript_loses_the_lost_words(self):
        """`take_metrics` derives transcript, n_words, fillers and
        `complete` from the WORD LIST. Clamping s/e without filtering the
        words would leave a take claiming words that no longer play."""
        facts.set_trim("ep", "a.mov", 10.7, 30.0)
        t = self.take()
        self.assertEqual(t["s"], 10.7, "clamped to the trim, not to a word")
        self.assertEqual(t["e"], 12.0)
        self.assertEqual(t["transcript"], "is fine.")
        self.assertEqual(t["n_words"], 2)
        self.assertEqual(t["duration"], 1.3, "what actually plays")

    def test_the_tail_is_clamped_and_complete_stops_lying(self):
        """`complete` is the field that lies first: the sentence-closing
        word is exactly what a fumbled tail takes away."""
        self.assertTrue(self.take()["complete"], "the untrimmed take is whole")
        facts.set_trim("ep", "a.mov", 0.5, 11.05)
        t = self.take()
        self.assertEqual(t["transcript"], "This is")
        self.assertFalse(t["complete"])
        self.assertEqual(t["e"], 11.0, "no frame past the trim may play")

    def test_a_word_straddling_the_edge_keeps_the_take_inside_the_window(self):
        """The word runs past `out`; the take may not."""
        facts.set_trim("ep", "a.mov", 9.0, 11.5)
        t = self.take()
        self.assertEqual(t["e"], 11.5)
        self.assertIn("fine.", t["transcript"],
                      "the word overlaps the window, so it is still spoken")
        self.assertEqual(t["duration"], round(11.5 - 10.0, 3))


class AnUntrimmedProjectIsUnchanged(Sandbox):
    """Byte-identity, field by field, against what the code did before
    trims existed: s/e are the run's own rounded bounds and every metric
    comes from the whole run."""

    def setUp(self):
        Sandbox.setUp(self)
        self.catalog(self.speech_file())

    def expected(self):
        out = []
        for run in takes.segment_takes(WORDS):
            m = takes.take_metrics(run)
            m.update({"s": round(run[0]["s"], 3), "e": round(run[-1]["e"], 3)})
            out.append(m)
        return out

    def test_every_field_matches_the_pre_trim_computation(self):
        got = self.analyze()["takes"]
        self.assertEqual(len(got), 3)
        for g, want in zip(got, self.expected()):
            for key, value in want.items():
                self.assertEqual(g[key], value, "%s.%s" % (g["id"], key))
            self.assertNotIn("screened_out", g)
            self.assertNotIn("screen_reason", g)

    def test_an_empty_sidecar_reads_the_same_as_no_sidecar(self):
        first = (self.analysis / "takes.json")
        self.analyze()
        without = first.read_text()
        (self.tmp / "footage_trims.json").write_text('{"files": {}}')
        self.analyze()
        self.assertEqual(first.read_text(), without)

    def test_zero_length_words_on_the_first_frame_survive(self):
        """FOUND ON REAL DATA (2026-08-28). Whisper stamps clusters of
        words at 0.000-0.000 on a clip's first frame — 4 of hmns' 375
        takes open with one, T205 with five in a row. A plain overlap test
        (`w["e"] > t_in`) drops every one of them at t_in = 0, so an
        UNTRIMMED episode would quietly lose words from its transcripts,
        its word counts and its `complete` flag."""
        self.catalog(self.speech_file(words=[
            {"s": 0.0, "e": 0.0, "w": "I'm"},
            {"s": 0.0, "e": 0.0, "w": "trying"},
            {"s": 0.0, "e": 0.1, "w": "with"},
            {"s": 0.1, "e": 0.1, "w": "you."},
        ]))
        t = self.analyze()["takes"][0]
        self.assertEqual(t["transcript"], "I'm trying with you.")
        self.assertEqual(t["n_words"], 4)
        self.assertEqual(t["s"], 0.0)

    def test_a_damaged_sidecar_cannot_stop_the_analysis(self):
        """Triage data must never be able to stop an analysis from running
        (ingest.py:131-143). Absent, unreadable and half-written all mean
        'nothing is trimmed', which is what an untrimmed shoot IS."""
        self.analyze()
        without = (self.analysis / "takes.json").read_text()
        for junk in ("not json at all", "[]", '{"files": 3}',
                     '{"files": {"a.mov": "yesterday"}}'):
            (self.tmp / "footage_trims.json").write_text(junk)
            self.assertEqual(self.analyze() and
                             (self.analysis / "takes.json").read_text(),
                             without, junk)


class TheBrollTrimRidesTheSidecar(Sandbox):

    def presheet(self, *names):
        d = self.analysis / "sheets"
        d.mkdir(parents=True, exist_ok=True)
        for n in names:
            (d / (n + ".sheet.jpg")).write_bytes(b"\xff\xd8jpeg")

    def catalog_broll(self):
        broll.catalog_broll("ep", log=lambda *a: None)
        return json.loads((self.analysis / "broll.json").read_text())

    def test_an_untrimmed_clip_carries_no_trim_key_at_all(self):
        self.catalog(self.broll_file())
        self.presheet("clip.mov")
        self.assertNotIn("trim", self.catalog_broll()["clips"][0])

    def test_the_trim_survives_a_re_catalog_that_never_saw_it(self):
        """The whole reason it is a sidecar: ingest rebuilds catalog.json
        from probe and `catalog_broll` rebuilds broll.json from that."""
        self.catalog(self.broll_file())
        self.presheet("clip.mov")
        facts.set_trim("ep", "clip.mov", 12.0, 40.0)
        first = self.catalog_broll()["clips"][0]
        self.assertEqual(first["trim"], {"in": 12.0, "out": 40.0})
        self.catalog(self.broll_file())          # rebuilt from probe
        second = self.catalog_broll()["clips"][0]
        self.assertEqual(second["trim"], {"in": 12.0, "out": 40.0})
        self.assertEqual(second["id"], first["id"], "ids must not move")

    def test_duration_still_names_the_whole_file(self):
        """`duration` is the source-time bound `_clamp_cover` and
        `_validate_spine` measure every src_s against, and every built plan
        states its covers in that clock. The trim is additive beside it."""
        self.catalog(self.broll_file())
        self.presheet("clip.mov")
        facts.set_trim("ep", "clip.mov", 12.0, 40.0)
        self.assertEqual(self.catalog_broll()["clips"][0]["duration"], 100.0)

    def test_a_window_past_the_end_of_the_file_is_recorded_clamped(self):
        """`trim_of` resolves against the real duration; the catalog must
        not record a window the file cannot honour."""
        self.catalog(self.broll_file(duration=30.0))
        self.presheet("clip.mov")
        facts.set_trim("ep", "clip.mov", 5.0, 900.0)
        self.assertEqual(self.catalog_broll()["clips"][0]["trim"],
                         {"in": 5.0, "out": 30.0})

    def test_the_catalogued_trim_passes_its_own_validator(self):
        self.catalog(self.broll_file())
        self.presheet("clip.mov")
        facts.set_trim("ep", "clip.mov", 12.0, 40.0)
        self.assertEqual(schemas.validate_broll(self.catalog_broll()), [])


class TheContactSheetSamplesTheUsableWindow(Sandbox):
    """The agents choose and tag shots by reading these sheets, so a sheet
    spread across the whole file offers frames from the seconds Caleb cut
    away — and a shot chosen there cannot be cut."""

    def setUp(self):
        Sandbox.setUp(self)
        self.seeks = []
        self._run = broll.subprocess.run

        class _Proc(object):
            returncode = 0
            stdout = stderr = ""

        def fake(cmd, **kw):
            self.seeks.append(float(cmd[cmd.index("-ss") + 1]))
            Image.new("RGB", (8, 8)).save(cmd[-1])
            return _Proc()

        broll.subprocess.run = fake

    def tearDown(self):
        broll.subprocess.run = self._run
        Sandbox.tearDown(self)

    def sheet(self, **kw):
        src = self.tmp / "clip.mov"
        src.write_bytes(b"\x00")
        broll.contact_sheet(src, 90.0, self.tmp / "s.jpg", self.tmp / "f", **kw)
        return self.seeks

    def test_the_whole_clip_is_sampled_when_nothing_is_trimmed(self):
        n = broll.GRID * broll.GRID
        self.assertEqual(self.sheet(),
                         [90.0 * (i + 0.5) / n for i in range(n)])

    def test_every_frame_comes_from_inside_the_trim(self):
        n = broll.GRID * broll.GRID
        got = self.sheet(in_s=30.0, out_s=48.0)
        self.assertEqual(got, [30.0 + 18.0 * (i + 0.5) / n for i in range(n)])
        self.assertTrue(all(30.0 <= t <= 48.0 for t in got), got)

    def test_an_unusable_window_falls_back_to_the_whole_clip(self):
        """A sheet is better than an exception, and a window we cannot
        sample is not a window."""
        n = broll.GRID * broll.GRID
        self.assertEqual(self.sheet(in_s=60.0, out_s=10.0),
                         [90.0 * (i + 0.5) / n for i in range(n)])


class TheTimelineObeysTheTrim(Sandbox):
    """plan_beats is the densest bite site: every source-time bound in the
    cut is chosen here."""

    def setUp(self):
        Sandbox.setUp(self)
        self.catalog(self.speech_file("a.mov", 60.0),
                     self.speech_file("b.mov", 60.0),
                     self.broll_file("clip.mov", 100.0))
        (self.analysis / "takes.json").write_text(json.dumps({"takes": [
            {"id": "T01", "file": "a.mov", "s": 1.0, "e": 5.0,
             "kind": "oncamera", "transcript": "one.", "duration": 4.0},
            {"id": "T02", "file": "b.mov", "s": 10.0, "e": 14.0,
             "kind": "oncamera", "transcript": "two.", "duration": 4.0},
        ], "groups": []}))
        (self.analysis / "broll.json").write_text(json.dumps(
            {"clips": [{"id": "B001", "file": "clip.mov", "duration": 100.0,
                        "sheet": "sheets/clip.mov.sheet.jpg"}]}))
        # the storytelling rules are validate_edit_plan's own tests; these
        # are about the arithmetic downstream of them
        self._validate = schemas.validate_edit_plan
        schemas.validate_edit_plan = lambda *a, **k: []

    def tearDown(self):
        schemas.validate_edit_plan = self._validate
        Sandbox.tearDown(self)

    def plan(self, *beats):
        (self.tmp / "edit_plan.json").write_text(json.dumps(
            {"slug": "ep", "format": "youtube_long", "orientation": "landscape",
             "beats": list(beats)}))
        return timeline.plan_beats("ep")

    def take_beat(self, bid="BT01", tid="T01", **kw):
        b = {"id": bid, "purpose": "hook", "take_id": tid,
             "transition_in": "cut"}
        b.update(kw)
        return b

    # --- covers -------------------------------------------------------

    def cover(self, at=0.5, duration=3.0, **kw):
        br = {"clip_id": "B001", "at": at, "duration": duration}
        br.update(kw)
        return self.take_beat(broll=[br])

    def test_the_ten_percent_default_lands_inside_the_window(self):
        """DJI clips open on a ramp, so an auto-placed cover starts 10% in
        — measured from the head of the FILE that is the walk-up the trim
        was drawn to exclude."""
        untrimmed = self.plan(self.cover())["beats"][0]["broll"][0]
        self.assertAlmostEqual(untrimmed["src_s"], 10.0, places=2)

        facts.set_trim("ep", "clip.mov", 40.0, 60.0)
        got = self.plan(self.cover())["beats"][0]["broll"][0]
        self.assertAlmostEqual(got["src_s"], 42.0, places=2,
                               msg="10% INTO the usable window")
        self.assertGreaterEqual(got["src_s"], 40.0)
        self.assertLessEqual(got["src_s"] + got["duration"], 60.0)

    def test_a_desk_set_in_point_before_the_trim_is_pulled_inside_it(self):
        facts.set_trim("ep", "clip.mov", 40.0, 60.0)
        got = self.plan(self.cover(src_s=2.0))["beats"][0]["broll"][0]
        self.assertGreaterEqual(got["src_s"], 40.0)

    def test_a_cover_longer_than_the_window_is_cut_to_it(self):
        facts.set_trim("ep", "clip.mov", 40.0, 42.0)
        got = self.plan(self.cover(duration=9.0))["beats"][0]["broll"][0]
        self.assertLessEqual(got["duration"], 2.0)
        self.assertLessEqual(got["src_s"] + got["duration"], 42.0 + 1e-6)

    # --- the take's own window ----------------------------------------

    def test_the_head_and_tail_pads_stay_inside_the_trim(self):
        """HEAD_PAD_SEC before the first word and TAIL_PAD_SEC after the
        last are exactly the seconds a trim is usually drawn to remove."""
        facts.set_trim("ep", "a.mov", 2.0, 4.5)
        segs = self.plan(self.take_beat())["beats"][0]["segments"]
        self.assertTrue(segs)
        self.assertGreaterEqual(segs[0]["src_s"], 2.0)
        self.assertLessEqual(segs[-1]["src_e"], 4.5)

    def test_a_take_window_emptied_by_a_trim_raises_and_names_it(self):
        facts.set_trim("ep", "a.mov", 10.0, 50.0)
        with self.assertRaises(IngestError) as cm:
            self.plan(self.take_beat())
        msg = str(cm.exception)
        self.assertIn("trimmed to 10.00-50.00s", msg)
        self.assertIn("widen the trim", msg)

    # --- spines --------------------------------------------------------

    def spine_beat(self, s=5.0, e=20.0):
        return {"id": "BT01", "purpose": "hook", "transition_in": "cut",
                "spine": {"clip_id": "B001", "src_s": s, "src_e": e}}

    def test_a_spine_window_clamped_empty_by_a_trim_names_the_trim(self):
        facts.set_trim("ep", "clip.mov", 40.0, 60.0)
        with self.assertRaises(IngestError) as cm:
            self.plan(self.spine_beat())
        msg = str(cm.exception)
        self.assertIn("is empty against clip.mov", msg)
        self.assertIn("its trim keeps only 40.00-60.00s", msg)

    def test_an_untrimmed_empty_spine_window_still_reads_as_it_did(self):
        """The old message is the whole message when no trim is involved —
        naming a trim that does not exist would send Caleb to the wrong
        desk."""
        with self.assertRaises(IngestError) as cm:
            self.plan(self.spine_beat(s=20.0, e=5.0))
        self.assertNotIn("trim", str(cm.exception))

    def test_a_spine_is_clamped_into_the_window_when_it_overlaps(self):
        facts.set_trim("ep", "clip.mov", 10.0, 18.0)
        segs = self.plan(self.spine_beat(s=5.0, e=20.0))["beats"][0]["segments"]
        self.assertEqual((segs[0]["src_s"], segs[0]["src_e"]), (10.0, 18.0))

    # --- the dissolve handle -------------------------------------------

    def dissolve_pair(self):
        return (self.take_beat("BT01", "T01"),
                self.take_beat("BT02", "T02", transition_in="dissolve"))

    def test_a_dissolve_survives_when_the_handles_are_really_there(self):
        beats = self.plan(*self.dissolve_pair())["beats"]
        self.assertEqual(beats[1]["transition_in"], "dissolve")

    def test_a_trim_out_shortens_the_handle_and_degrades_to_a_cut(self):
        """A centred dissolve reaches DISSOLVE_SEC/2 past the outgoing
        clip's last frame. Measured against `duration` it would be granted
        a handle made of the footage the trim excluded, and half a second
        of it would be mixed into the cut."""
        facts.set_trim("ep", "a.mov", 0.5, 5.4)
        beats = self.plan(*self.dissolve_pair())["beats"]
        self.assertEqual(beats[1]["transition_in"], "cut")

    def test_a_trim_in_shortens_the_incoming_head_too(self):
        facts.set_trim("ep", "b.mov", 9.6, 40.0)
        beats = self.plan(*self.dissolve_pair())["beats"]
        self.assertEqual(beats[1]["transition_in"], "cut")

    # --- the map as a whole --------------------------------------------

    def test_an_untrimmed_map_is_unchanged_by_an_empty_sidecar(self):
        before = json.dumps(self.plan(self.cover(), self.take_beat("BT02", "T02")))
        facts.set_trim("ep", "clip.mov", 40.0, 60.0)
        facts.set_trim("ep", "clip.mov", None, None)      # cleared again
        after = json.dumps(self.plan(self.cover(), self.take_beat("BT02", "T02")))
        self.assertEqual(after, before)

    def test_the_fcpxml_asset_still_declares_the_whole_file(self):
        """DELIBERATE. An <asset> describes the media on disk and every
        clip's start= is an offset into that file's clock; declaring the
        trimmed length would put each in-point past the asset's end, and
        Resolve rejects such a file whole with no error."""
        facts.set_trim("ep", "a.mov", 2.0, 4.5)
        tl = self.plan(self.take_beat())
        xml = timeline.write_fcpxml("ep", tl, [], [], log=lambda *a: None).read_text()
        self.assertIn('duration="1800/30s"', xml)   # 60.0s at 30fps


class TheSpineValidatorReadsTheTrim(unittest.TestCase):
    """`_validate_spine` has no slug in hand, so it reads the trim the
    catalog carries — which is why `catalog_broll` writes it there."""

    def errs(self, spine, clip):
        out = []
        schemas._validate_spine(out, spine, {"B001": clip}, "beats[0]")
        return out

    def test_a_clip_with_no_trim_validates_exactly_as_before(self):
        clip = {"id": "B001", "duration": 30.0}
        self.assertEqual(self.errs({"clip_id": "B001", "src_s": 0.0,
                                    "src_e": 20.0}, clip), [])
        out = self.errs({"clip_id": "B001", "src_s": 0.0, "src_e": 90.0}, clip)
        self.assertTrue(any("is 30.00s" in e for e in out), out)

    def test_a_window_outside_the_trim_names_the_trim(self):
        clip = {"id": "B001", "duration": 30.0,
                "trim": {"in": 10.0, "out": 20.0}}
        out = self.errs({"clip_id": "B001", "src_s": 2.0, "src_e": 18.0}, clip)
        self.assertTrue(any("trimmed to 10.00-20.00s" in e for e in out), out)
        self.assertTrue(any("widen the trim" in e for e in out), out)

    def test_a_window_inside_the_trim_is_accepted(self):
        clip = {"id": "B001", "duration": 30.0,
                "trim": {"in": 10.0, "out": 20.0}}
        self.assertEqual(self.errs({"clip_id": "B001", "src_s": 10.0,
                                    "src_e": 20.0}, clip), [])

    def test_a_junk_trim_falls_back_to_the_file_length(self):
        """The file on disk is the truth; the sidecar is a note about it."""
        clip = {"id": "B001", "duration": 30.0, "trim": "from 10 to 20"}
        out = self.errs({"clip_id": "B001", "src_s": 0.0, "src_e": 90.0}, clip)
        self.assertTrue(any("is 30.00s" in e for e in out), out)

    def test_a_trim_that_claims_more_than_the_file_still_hits_the_length(self):
        clip = {"id": "B001", "duration": 30.0,
                "trim": {"in": 0.0, "out": 900.0}}
        out = self.errs({"clip_id": "B001", "src_s": 0.0, "src_e": 90.0}, clip)
        self.assertTrue(any("is 30.00s" in e for e in out), out)


class TheCatalogValidatorChecksTheTrimShape(unittest.TestCase):

    def clips(self, trim):
        c = {"id": "B001", "file": "a.mov", "duration": 30.0, "sheet": "s.jpg"}
        if trim is not None:
            c["trim"] = trim
        return {"slug": "ep", "clips": [c]}

    def test_absent_is_valid_and_is_what_most_clips_are(self):
        self.assertEqual(schemas.validate_broll(self.clips(None)), [])

    def test_a_real_window_is_valid(self):
        self.assertEqual(
            schemas.validate_broll(self.clips({"in": 1.0, "out": 2.0})), [])

    def test_an_empty_window_is_named(self):
        out = schemas.validate_broll(self.clips({"in": 5.0, "out": 5.0}))
        self.assertTrue(any("is not after in" in e for e in out), out)

    def test_a_non_numeric_bound_is_named(self):
        out = schemas.validate_broll(self.clips({"in": "1", "out": 2.0}))
        self.assertTrue(any("should be a number" in e for e in out), out)

    def test_a_negative_in_point_is_named(self):
        out = schemas.validate_broll(self.clips({"in": -3.0, "out": 2.0}))
        self.assertTrue(any("before the start of the file" in e for e in out), out)


if __name__ == "__main__":
    unittest.main()


class TheMarkSurvivesTheJobThatFollowsIt(Sandbox):
    """The feature was dead on arrival and the unit tests could not see it.

    `takes.analyze` writes the mark; `editroom._stamp_takes` runs one call
    later in the SAME job (`jobs.py:335-344`) re-applying Caleb's screening
    store, and its `else` branch popped `screened_out` from every take that
    store had no `kill` verdict for. So every trim mark was made and then
    erased before anything downstream could read it — measured on a real
    project 2026-08-28, `MARK SURVIVES: False`.

    This asserts across the seam, because each side alone was green.
    """

    def setUp(self):
        Sandbox.setUp(self)
        self.catalog(self.speech_file())
        from pipeline import editroom as editroom_mod
        self.editroom = editroom_mod
        self._ewp = editroom_mod.work_path
        editroom_mod.work_path = lambda slug: self.tmp

    def tearDown(self):
        self.editroom.work_path = self._ewp
        Sandbox.tearDown(self)

    def test_stamp_takes_does_not_erase_a_trim_mark(self):
        facts.set_trim("ep", "a.mov", 9.0, 13.0)
        self.analyze()
        self.editroom._stamp_takes("ep")
        by_id = {t["id"]: t
                 for t in json.loads(
                     (self.analysis / "takes.json").read_text())["takes"]}
        for tid in ("T01", "T03"):
            self.assertTrue(by_id[tid].get("screened_out"),
                            "%s lost its trim mark to _stamp_takes" % tid)
            self.assertEqual(by_id[tid]["screen_reason"],
                             takes.TRIM_SCREEN_REASON)
        self.assertNotIn("screened_out", by_id["T02"])

    def test_stamp_takes_still_clears_a_mark_it_owns(self):
        """The `else` exists for a real reason — a verdict Caleb undid must
        still lose its mark. Preserving the trim mark may not blunt that."""
        self.analyze()
        self.editroom._set_take_verdict("ep", "T01", "kill", "fumbled",
                                        log=lambda *a: None)
        self.editroom._stamp_takes("ep")
        killed = json.loads(
            (self.analysis / "takes.json").read_text())["takes"][0]
        self.assertTrue(killed["screened_out"])
        self.editroom._set_take_verdict("ep", "T01", "undo",
                                        log=lambda *a: None)
        self.editroom._stamp_takes("ep")
        cleared = json.loads(
            (self.analysis / "takes.json").read_text())["takes"][0]
        self.assertNotIn("screened_out", cleared)

    def test_the_screened_count_includes_takes_a_trim_put_outside(self):
        facts.set_trim("ep", "a.mov", 9.0, 13.0)
        self.analyze()
        self.assertEqual(self.editroom._stamp_takes("ep"), 2)
