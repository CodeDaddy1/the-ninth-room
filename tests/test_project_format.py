# -*- coding: utf-8 -*-
"""A project knows its shape from the moment it is created.

Caleb, 2026-08-25: "When creating a project, it should prompt me which
direction we are taking." Before this, creating a project asked for a name
and nothing else, and the two things that decide every downstream stage were
inferred far later:

  * ORIENTATION came from analysis/timeline_map.json, which only exists
    AFTER assemble — so captions, card baking, the Resolve canvas and the
    review proxies all learned the shape of the video two-thirds of the way
    through making it, defaulting to landscape until then.
  * FORMAT was a default in the timeline builder.

And a short could not be briefed at all: the bound was 1-60 minutes, so a
45-second Reel (0.75) was refused outright.

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

from pipeline import editroom, schemas  # noqa: E402
from pipeline.ingest import IngestError  # noqa: E402


class TheModel(unittest.TestCase):
    """Pure: one answer, one shape."""

    def test_long_is_sixteen_by_nine(self):
        s = schemas.delivery_shape("long")
        self.assertEqual(s["orientation"], "landscape")
        self.assertEqual(s["format"], "youtube_long")

    def test_short_is_vertical(self):
        s = schemas.delivery_shape("short")
        self.assertEqual(s["orientation"], "portrait")
        self.assertEqual(s["format"], "youtube_short")

    def test_a_short_opens_under_a_minute(self):
        """The length that the old brief bound made impossible."""
        self.assertLess(schemas.delivery_shape("short")["target_minutes"], 1)

    def test_an_unknown_delivery_reads_as_long(self):
        """Every project that predates the field is a 16:9 episode."""
        for v in (None, "", "widescreen"):
            self.assertEqual(schemas.delivery_shape(v)["orientation"],
                             "landscape")

    def test_the_narration_dial_differs_per_combination(self):
        """Note which way round this goes, because it is counter-intuitive:
        a desk documentary opens LOWER on voice-over than a visit does.

        vo_share counts `vo` seconds against the whole, and `desk` sections
        are not vo — they are Caleb performing to camera. Caleb chose the
        desk as the SPINE of that format, so most of its runtime is a face,
        and narration is the connective tissue. A visit is the opposite: the
        day gave what it gave, and narration fills what it did not.
        """
        doc = schemas.format_defaults("script", "long")["vo_share"]
        visit = schemas.format_defaults("footage", "long")["vo_share"]
        self.assertLess(doc, visit)

    def test_a_short_leans_harder_on_narration_than_its_long_form(self):
        """Sixty seconds has no room to build a desk spine or to let a
        moment breathe — the voice carries it either way."""
        for origin in ("script", "footage"):
            long_ = schemas.format_defaults(origin, "long")["vo_share"]
            short = schemas.format_defaults(origin, "short")["vo_share"]
            if origin == "script":
                self.assertGreater(short, long_)
            else:
                # a short cut from a day out is the moment itself
                self.assertLess(short, long_)

    def test_reel_is_not_a_third_shape(self):
        """A Reel is the same vertical master with different copy — the
        split belongs to the publish stage, not the canvas."""
        self.assertNotIn("instagram_reel",
                         [s["format"] for s in schemas.DELIVERY_SHAPE.values()])


class Creation(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self._wp = editroom.work_path
        editroom.work_path = lambda slug: self.root / slug

    def tearDown(self):
        editroom.work_path = self._wp
        shutil.rmtree(self.root, ignore_errors=True)

    def brief(self, slug):
        return json.loads((self.root / slug / "story_brief.json").read_text())

    def test_a_project_is_never_formatless(self):
        editroom._new_project("Pendulum", "script", "long")
        b = self.brief("pendulum")
        self.assertEqual(b["origin"], "script")
        self.assertEqual(b["delivery"], "long")
        self.assertEqual(b["orientation"], "landscape")
        self.assertEqual(b["format"], "youtube_long")

    def test_a_vertical_short_is_vertical_from_the_first_screen(self):
        editroom._new_project("Quick one", "script", "short")
        b = self.brief("quick-one")
        self.assertEqual(b["orientation"], "portrait")
        self.assertLess(b["target_minutes"], 1)
        self.assertEqual(b["chapters"], 1)

    def test_shorts_record_where_they_come_from(self):
        editroom._new_project("Cut down", "footage", "short", "derived")
        self.assertEqual(self.brief("cut-down")["shorts_source"], "derived")

    def test_a_short_defaults_to_standalone(self):
        editroom._new_project("Solo", "footage", "short")
        self.assertEqual(self.brief("solo")["shorts_source"], "standalone")

    def test_a_long_project_carries_no_shorts_source(self):
        editroom._new_project("Episode", "footage", "long")
        self.assertNotIn("shorts_source", self.brief("episode"))

    def test_the_default_is_the_day_out(self):
        editroom._new_project("Plain")
        b = self.brief("plain")
        self.assertEqual(b["origin"], "footage")
        self.assertEqual(b["delivery"], "long")

    def test_junk_axes_are_refused(self):
        for kw in ({"origin": "hybrid"},
                   {"delivery": "medium"},
                   {"delivery": "short", "shorts_source": "borrowed"}):
            with self.assertRaises(editroom.IngestError):
                editroom._new_project("X", **kw)

    def test_a_nameless_project_is_still_refused(self):
        with self.assertRaises(editroom.IngestError):
            editroom._new_project("   ")


class Bounds(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self._wp = editroom.work_path
        editroom.work_path = lambda slug: self.tmp

    def tearDown(self):
        editroom.work_path = self._wp
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_a_forty_five_second_short_can_be_briefed(self):
        """The bug: the old floor of one minute refused every short."""
        b = editroom._save_story_brief("ep", 0.75, 1, "", "", 0.85,
                                       "the pendulum", "script", "short")
        self.assertEqual(b["target_minutes"], 0.75)
        self.assertEqual(b["orientation"], "portrait")

    def test_fifteen_seconds_is_the_floor(self):
        editroom._save_story_brief("ep", 0.25, 1, "", "x", 0.5)
        with self.assertRaises(editroom.IngestError):
            editroom._save_story_brief("ep", 0.1, 1, "", "x", 0.5)

    def test_an_hour_is_still_not_an_episode(self):
        with self.assertRaises(editroom.IngestError):
            editroom._save_story_brief("ep", 61, 3, "", "x", 0.5)

    def test_delivery_is_sticky_across_edits(self):
        """Editing the brief on the Story desk must not silently re-shape a
        vertical project back to 16:9 because the form omitted the field."""
        editroom._save_story_brief("ep", 0.75, 1, "", "", 0.85, "topic",
                                   "script", "short")
        again = editroom._save_story_brief("ep", 0.9, 1, "", "", 0.85,
                                           "topic", "script")
        self.assertEqual(again["delivery"], "short")
        self.assertEqual(again["orientation"], "portrait")

    def test_a_junk_delivery_is_refused(self):
        with self.assertRaises(editroom.IngestError):
            editroom._save_story_brief("ep", 5, 2, "", "x", 0.5, "", "footage",
                                       "medium")


class Orientation(unittest.TestCase):
    """Precedence: what was BUILT outranks what was intended."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "analysis").mkdir()
        self._wp, self._ad = editroom.work_path, editroom.analysis_dir
        editroom.work_path = lambda slug: self.tmp
        editroom.analysis_dir = lambda slug: self.tmp / "analysis"

    def tearDown(self):
        editroom.work_path, editroom.analysis_dir = self._wp, self._ad
        shutil.rmtree(self.tmp, ignore_errors=True)

    def brief(self, **kw):
        (self.tmp / "story_brief.json").write_text(json.dumps(kw))

    def timeline(self, orientation):
        (self.tmp / "analysis" / "timeline_map.json").write_text(
            json.dumps({"orientation": orientation}))

    def test_the_brief_answers_before_any_cut_exists(self):
        """The whole point: everything upstream of assemble used to guess,
        and guessed landscape — so a vertical project baked 16:9 cards."""
        self.brief(delivery="short", orientation="portrait")
        self.assertEqual(editroom._orientation("ep"), "portrait")

    def test_delivery_alone_is_enough(self):
        self.brief(delivery="short")
        self.assertEqual(editroom._orientation("ep"), "portrait")

    def test_a_built_timeline_outranks_a_later_brief_edit(self):
        """Its cards and captions are baked to that canvas; re-shaping
        underneath them would break a finished episode."""
        self.timeline("landscape")
        self.brief(delivery="short", orientation="portrait")
        self.assertEqual(editroom._orientation("ep"), "landscape")

    def test_a_project_with_neither_is_an_episode(self):
        self.assertEqual(editroom._orientation("ep"), "landscape")

    def test_corrupt_files_do_not_crash_the_desk(self):
        (self.tmp / "story_brief.json").write_text("{not json")
        self.assertEqual(editroom._orientation("ep"), "landscape")
        self.timeline("portrait")
        (self.tmp / "analysis" / "timeline_map.json").write_text("{nope")
        self.assertEqual(editroom._orientation("ep"), "landscape")


if __name__ == "__main__":
    unittest.main()


class WhatReachesTheWriter(unittest.TestCase):
    """The failure mode a questionnaire invites is being politely ignored —
    the same reason _brief_clause was made pure and separately testable."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        from pipeline import jobs
        self.jobs = jobs
        self._wp = jobs.work_path
        jobs.work_path = lambda slug: self.tmp

    def tearDown(self):
        self.jobs.work_path = self._wp
        shutil.rmtree(self.tmp, ignore_errors=True)

    def brief(self, **kw):
        d = {"target_minutes": 8, "chapters": 3, "vo_share": 0.35,
             "origin": "script", "delivery": "long"}
        d.update(kw)
        (self.tmp / "story_brief.json").write_text(json.dumps(d))

    def test_a_short_is_told_it_is_a_short(self):
        """Not left to infer the shape from target_minutes."""
        self.brief(delivery="short", target_minutes=0.75, chapters=1)
        c = self.jobs._brief_clause("ep")
        self.assertIn("VERTICAL SHORT", c)
        self.assertIn("One loop", c)
        self.assertIn("captioned", c)

    def test_a_short_is_not_told_about_chapters(self):
        self.brief(delivery="short", target_minutes=0.75, chapters=1)
        self.assertNotIn("chapters", self.jobs._brief_clause("ep"))

    def test_long_form_still_gets_its_chapter_budget(self):
        self.brief()
        c = self.jobs._brief_clause("ep")
        self.assertIn("3 chapters", c)
        self.assertIn("16:9", c)

    def test_a_brief_with_no_delivery_reads_as_long(self):
        self.brief()
        b = json.loads((self.tmp / "story_brief.json").read_text())
        del b["delivery"]
        (self.tmp / "story_brief.json").write_text(json.dumps(b))
        self.assertIn("chapters", self.jobs._brief_clause("ep"))

    def test_no_brief_is_not_a_crash(self):
        self.assertEqual(self.jobs._brief_clause("ep"), "")


class BriefStickiness(unittest.TestCase):
    """Absence means UNCHANGED, for every field the form may not send.

    `delivery` had this rule and named the reason. `origin` sat three
    lines away with a "footage" default, and the Studio's brief form has
    never sent it — so pressing Save brief on a documentary silently
    converted it to the filmed lane. Verified live on `oligarchy`
    (2026-08-26) before the fix: origin went script -> footage on a save
    that touched neither field.
    """

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self._wp = editroom.work_path
        editroom.work_path = lambda slug: self.tmp
        import pipeline.ingest as ingest_mod
        self._iwp = ingest_mod.work_path
        ingest_mod.work_path = lambda slug: self.tmp

    def tearDown(self):
        import pipeline.ingest as ingest_mod
        editroom.work_path = self._wp
        ingest_mod.work_path = self._iwp
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _seed(self, **over):
        base = {"target_minutes": 0.75, "chapters": 1, "vo_share": 0.6,
                "location": "", "subject": "how ownership concentrates",
                "origin": "script", "delivery": "short",
                "orientation": "portrait", "format": "youtube_short"}
        base.update(over)
        editroom._write_json(self.tmp / "story_brief.json", base)

    def test_a_save_that_omits_origin_does_not_flip_the_lane(self):
        self._seed()
        # exactly what the Studio's form sends
        b = editroom._save_story_brief("ep", 0.75, 1, "")
        self.assertEqual(b["origin"], "script")

    def test_a_save_that_omits_subject_does_not_erase_it(self):
        self._seed()
        b = editroom._save_story_brief("ep", 0.75, 1, "")
        self.assertEqual(b["subject"], "how ownership concentrates")

    def test_a_save_that_omits_location_does_not_erase_it(self):
        self._seed(location="Houston", subject="")
        b = editroom._save_story_brief("ep", 10, 3, "")
        self.assertEqual(b["location"], "Houston")

    def test_an_EMPTY_STRING_still_clears_the_field(self):
        # absent and cleared are different edits, and the form must keep
        # being able to make the second one
        self._seed(location="Houston")
        b = editroom._save_story_brief("ep", 10, 3, "", "")
        self.assertEqual(b["location"], "")
        # and clearing the location does not take the subject with it
        self.assertEqual(b["subject"], "how ownership concentrates")

    def test_the_lane_can_still_be_stated_explicitly(self):
        self._seed()
        b = editroom._save_story_brief("ep", 0.75, 1, "", None, None, None, "footage")
        self.assertEqual(b["origin"], "footage")

    def test_a_script_lane_save_that_would_erase_its_only_subject_is_refused(self):
        # the gate still bites when the subject is genuinely cleared
        self._seed()
        with self.assertRaises(IngestError):
            editroom._save_story_brief("ep", 0.75, 1, "", "", 0.6, "")

    def test_a_brand_new_project_still_defaults_to_footage(self):
        b = editroom._save_story_brief("ep", 10, 3, "", "Houston")
        self.assertEqual(b["origin"], "footage")
        self.assertEqual(b["delivery"], "long")
