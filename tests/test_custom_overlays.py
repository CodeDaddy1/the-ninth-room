# -*- coding: utf-8 -*-
"""The Overlays desk's save guard.

Why this file exists: `overlays_custom.json` had FOUR direct writers and none
of them validated, so an overlay could carry a kit_type the kit cannot render
all the way to bake time. The plan validator could not be reused — a custom
overlay has no `type` and no `beat_id`, so `validate_graphics_plan` rejects
every legitimate one. These tests pin both halves: the real shapes stay
accepted, and the failure that actually reached a render is refused.

Run: /usr/bin/python3 -m unittest discover -s tests -t .
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline import schemas  # noqa: E402
from pipeline.overlay_kit import RENDERERS  # noqa: E402


def wrap(*overlays):
    return {"overlays": list(overlays)}


class AcceptsRealOverlays(unittest.TestCase):
    """These five shapes are live on hmns. If this class ever fails, the
    guard has started refusing work Caleb already has on disk."""

    def test_every_kit_type_in_use_is_a_real_renderer(self):
        for kt in ("next_room", "stamp", "emoji", "lower_third", "glass"):
            self.assertIn(kt, RENDERERS)

    def test_a_full_lower_third_validates(self):
        self.assertEqual(schemas.validate_custom_overlays(wrap({
            "id": "OV04", "kit_type": "lower_third", "duration": 3,
            "kicker": "Foucault pendulum", "text": "It proves the earth is turning",
            "emphasis": ["the earth is turning"], "style_v": 2,
        })), [])

    def test_a_minimal_overlay_validates(self):
        self.assertEqual(schemas.validate_custom_overlays(
            wrap({"id": "OV05", "kit_type": "glass", "duration": 3.0, "value": 55})), [])

    def test_an_overlay_with_no_duration_validates(self):
        """duration is optional — the kit has its own default."""
        self.assertEqual(schemas.validate_custom_overlays(
            wrap({"id": "OV09", "kit_type": "stamp"})), [])

    def test_an_empty_overlay_list_validates(self):
        self.assertEqual(schemas.validate_custom_overlays(wrap()), [])


class RefusesBadOverlays(unittest.TestCase):
    def test_unknown_kit_type_is_refused(self):
        """The gap this guard was built to close."""
        errs = schemas.validate_custom_overlays(
            wrap({"id": "OV01", "kit_type": "not_a_real_kit", "duration": 2}))
        self.assertTrue(any("not_a_real_kit" in e for e in errs))

    def test_missing_kit_type_is_refused(self):
        errs = schemas.validate_custom_overlays(wrap({"id": "OV01", "duration": 2}))
        self.assertTrue(any("kit_type" in e for e in errs))

    def test_missing_id_is_refused(self):
        errs = schemas.validate_custom_overlays(wrap({"kit_type": "stamp"}))
        self.assertTrue(any("id" in e for e in errs))

    def test_duplicate_ids_are_refused(self):
        errs = schemas.validate_custom_overlays(
            wrap({"id": "OV01", "kit_type": "stamp"},
                 {"id": "OV01", "kit_type": "glass"}))
        self.assertTrue(any("duplicate" in e for e in errs))

    def test_zero_duration_is_refused(self):
        errs = schemas.validate_custom_overlays(
            wrap({"id": "OV01", "kit_type": "stamp", "duration": 0}))
        self.assertTrue(any("duration" in e for e in errs))

    def test_boolean_duration_is_refused(self):
        """bool subclasses int in Python — a JSON `true` must not slip through
        an isinstance(v, (int, float)) check and reach ffmpeg as a length."""
        errs = schemas.validate_custom_overlays(
            wrap({"id": "OV01", "kit_type": "stamp", "duration": True}))
        self.assertTrue(any("duration" in e for e in errs))

    def test_negative_at_is_refused(self):
        errs = schemas.validate_custom_overlays(
            wrap({"id": "OV01", "kit_type": "stamp", "at": -4}))
        self.assertTrue(any("at" in e for e in errs))

    def test_non_string_beat_id_is_refused(self):
        errs = schemas.validate_custom_overlays(
            wrap({"id": "OV01", "kit_type": "stamp", "beat_id": 12}))
        self.assertTrue(any("beat_id" in e for e in errs))

    def test_a_non_object_entry_is_refused_without_crashing(self):
        errs = schemas.validate_custom_overlays(wrap("just a string"))
        self.assertTrue(errs)

    def test_a_missing_overlays_key_is_refused(self):
        self.assertTrue(schemas.validate_custom_overlays({}))


class SaveGuardWithLegacyBadData(unittest.TestCase):
    """The guard must refuse what is being WRITTEN, not what is being kept.

    Validating the survivors instead locked the desk: with one bad row already
    on disk, deleting a DIFFERENT overlay failed, because the bad row was
    still in the remaining list. The guard blocked every repair except the one
    exact delete that removed it. Caught by review 2026-08-23.
    """

    def setUp(self):
        import json, tempfile
        from pathlib import Path
        from pipeline import editroom
        self.editroom = editroom
        self.tmp = Path(tempfile.mkdtemp())
        self.legacy = {"overlays": [
            {"id": "OV01", "kit_type": "stamp", "duration": 2},
            {"id": "OV02", "kit_type": "not_a_real_kit", "duration": 2},
        ]}
        (self.tmp / "overlays_custom.json").write_text(json.dumps(self.legacy))
        self._wp = editroom.work_path
        editroom.work_path = lambda slug: self.tmp

    def tearDown(self):
        import shutil
        self.editroom.work_path = self._wp
        shutil.rmtree(self.tmp, ignore_errors=True)

    def keep(self, *ids):
        return {"overlays": [o for o in self.legacy["overlays"] if o["id"] in ids]}

    def test_deleting_a_good_row_still_works_with_a_bad_row_present(self):
        self.editroom._write_custom("x", self.keep("OV02"))

    def test_deleting_the_bad_row_works(self):
        self.editroom._write_custom("x", self.keep("OV01"))

    def test_a_NEW_bad_row_is_still_refused(self):
        bad = dict(self.legacy)
        bad = {"overlays": self.legacy["overlays"] + [
            {"id": "OV03", "kit_type": "still_not_real"}]}
        with self.assertRaises(Exception):
            self.editroom._write_custom("x", bad)

    def test_a_duplicate_id_is_refused_even_between_old_and_new_rows(self):
        dup = {"overlays": self.legacy["overlays"] + [
            {"id": "OV01", "kit_type": "glass", "duration": 1}]}
        with self.assertRaises(Exception):
            self.editroom._write_custom("x", dup)


class SaveGuard(unittest.TestCase):
    """_write_custom is the one writer; it must refuse before touching disk."""

    def test_bad_overlay_never_reaches_the_file(self):
        from pipeline import editroom
        wrote = []
        real = editroom._write_json
        editroom._write_json = lambda p, d: wrote.append(p)
        try:
            with self.assertRaises(Exception):
                editroom._write_custom("hmns", wrap(
                    {"id": "OV01", "kit_type": "not_a_real_kit"}))
        finally:
            editroom._write_json = real
        self.assertEqual(wrote, [], "a rejected overlay still hit the disk")


if __name__ == "__main__":
    unittest.main()
