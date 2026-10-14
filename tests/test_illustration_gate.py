# -*- coding: utf-8 -*-
"""Nothing generates until a round is valid, priced, capped and ledgered.

Decisions 3, 7, 17 and 18 (docs/decisions-illustrations.md): the agent
proposes a priced round, Caleb approves it and marks Seedance or pro
where he wants them, the engine spends inside a three hundred credit cap,
and every credit lands as a manifest row written in the same operation
as the file it bought (the brand/sfx manifest shape). This file pins the
shape of a round, every refusal `validate_round` makes, the cap, the
ledger row's required fields, and the binary path's precedence.

What breaks if this is wrong: a Soul step on a model that takes no Soul
fails at create after the plate was paid for; a pro tier Caleb never
asked for spends four times the credits; a spend leaves no row and the
balance drop has no explanation.

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

from pipeline import illustration, paths, schemas  # noqa: E402
from pipeline.ingest import IngestError  # noqa: E402


def _round(**over):
    r = {"id": "R1", "kind": "illustration", "section_id": "CH2.S3", "status": "proposed",
         "honesty": "illustration", "target": "cover", "aspect": "16:9",
         "why": "illustrate: the pendulum the line names",
         "steps": [
             {"stage": "plate", "model": "nano_banana_pro",
              "prompt": "cyanotype plate of a pendulum", "credits": 2.0, "tier": "std"},
             {"stage": "motion", "model": "kling3_0", "start_image": "plate",
              "prompt": "the bob swings once, slowly", "credits": 7.5, "tier": "std"}],
         "estimate_credits": 9.5, "marks": {}}
    r.update(over)
    return r


SCRIPT = {"chapters": [{"id": "CH2", "sections": [
    {"id": "CH2.S3", "kind": "vo", "text": "The pendulum ran for decades.",
     "visual": {"want": "the pendulum", "why": "illustrate: the thing named", "from": "illustration"}},
    {"id": "CH2.S4", "kind": "oncamera", "text": "Look at this."}]}]}
PLAN = {"beats": [{"id": "shot-T41", "purpose": "build", "take_id": "T41", "broll": [],
                   "visual": {"want": "the egg", "why": "illustrate: the board", "from": "illustration"}},
                  {"id": "shot-B9", "purpose": "build", "spine": {"clip_id": "B009", "src_s": 0, "src_e": 4}}]}


class ValidateRound(unittest.TestCase):
    def v(self, r, delivery="long", script=SCRIPT, plan=None):
        return illustration.validate_round(r, delivery, script=script, plan=plan)

    def test_a_good_script_lane_round_passes(self):
        self.assertEqual(self.v(_round()), [])

    def test_kind_ids_honesty_target_and_aspect(self):
        self.assertTrue(self.v(_round(kind="source")))
        self.assertTrue(self.v(_round(section_id=None)))
        self.assertTrue(self.v(_round(section_id="CH2.S3", beat_id="shot-T41")))
        self.assertTrue(self.v(_round(section_id="CH9.S9")))
        self.assertTrue(self.v(_round(honesty="generated")))
        self.assertTrue(self.v(_round(target="poster")))
        self.assertTrue(self.v(_round(aspect="9:16")), "a long delivery is 16:9")
        self.assertEqual(self.v(_round(aspect="9:16"), delivery="short"), [])
        self.assertEqual(self.v(_round(target="thumbnail", aspect="1:1")), [],
                         "a thumbnail's aspect is free")

    def test_the_why_may_not_establish(self):
        self.assertTrue(any("establish" in e for e in self.v(_round(why="establish: the hall"))))
        self.assertTrue(self.v(_round(why="looks nice")))

    def test_a_run_needs_the_footage_lane(self):
        self.assertTrue(self.v(_round(target="run")))
        r = _round(target="run", section_id=None, beat_id="shot-T41")
        self.assertEqual(self.v(r, plan=PLAN, script=None), [])

    def test_steps_are_priced_and_the_estimate_is_their_sum(self):
        r = _round(estimate_credits=5.0)
        self.assertTrue(any("estimate" in e for e in self.v(r)))
        r = _round(); r["steps"][0].pop("credits")
        self.assertTrue(self.v(r))
        r = _round(); r["steps"] = []
        self.assertTrue(self.v(r))

    def test_a_prompt_carries_no_hex_and_no_banned_word(self):
        r = _round(); r["steps"][0]["prompt"] = "a plate in #0B2340"
        self.assertTrue(any("hex" in e for e in self.v(r)))
        r = _round(); r["steps"][0]["prompt"] = "an insert of a pendulum"
        self.assertTrue(any("insert" in e for e in self.v(r)))

    def test_pro_needs_a_reason_and_calebs_mark(self):
        r = _round(); r["steps"][1]["tier"] = "pro"
        self.assertTrue(self.v(r))
        r["steps"][1]["reason"] = "hero shot"
        self.assertTrue(self.v(r), "a reason without the mark is still refused")
        r["marks"] = {"pro": ["motion"]}
        self.assertEqual(self.v(r), [])

    def test_seedance_needs_calebs_mark(self):
        r = _round(); r["steps"][1]["model"] = illustration.SEEDANCE_MODEL
        self.assertTrue(self.v(r))
        r["marks"] = {"seedance": True}
        self.assertEqual(self.v(r), [])

    def test_a_soul_step_is_a_plate_on_a_soul_model_in_a_reconstruction(self):
        r = _round(); r["steps"][1]["soul"] = True            # Kling takes no Soul
        self.assertTrue(any("Soul" in e for e in self.v(r)))
        r = _round(honesty="reconstruction", sources=["https://x"], disclosure="d")
        r["steps"][0]["soul"] = True; r["steps"][0]["model"] = "soul_cinema_studio"
        self.assertEqual(self.v(r), [])
        r = _round(); r["steps"][0]["soul"] = True; r["steps"][0]["model"] = "soul_cinema_studio"
        self.assertTrue(self.v(r), "an illustration never carries the host")
        r = _round(target="thumbnail", aspect="16:9")
        r["steps"][0]["soul"] = True; r["steps"][0]["model"] = "text2image_soul_v2"
        self.assertEqual(self.v(r), [])

    def test_a_reconstruction_needs_sources_and_a_disclosure(self):
        r = _round(honesty="reconstruction")
        errs = self.v(r)
        self.assertTrue(any("sources" in e for e in errs) and any("disclosure" in e for e in errs))

    def test_start_image_must_name_an_earlier_stage(self):
        r = _round(); r["steps"][1]["start_image"] = "nope"
        self.assertTrue(self.v(r))


class Ledger(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "assets").mkdir()
        self._wp = illustration.work_path
        illustration.work_path = lambda slug: self.tmp

    def tearDown(self):
        illustration.work_path = self._wp
        shutil.rmtree(self.tmp, ignore_errors=True)

    def row(self, **over):
        r = {"id": "x", "file": "x.mp4", "kind": "illustration", "honesty": "illustration",
             "model": "kling3_0", "job_id": "j1", "cost_credits": 7.5, "status": "done",
             "license": "Higgsfield ToU: output owned, commercial use permitted"}
        r.update(over); return r

    def test_a_row_without_its_cost_or_id_is_refused(self):
        for missing in ("cost_credits", "model", "job_id", "honesty", "status"):
            r = self.row(); r.pop(missing)
            with self.assertRaises(IngestError, msg=missing):
                illustration.append_row(self.tmp / "assets", r)

    def test_rows_land_and_spent_sums_them(self):
        illustration.append_row(self.tmp / "assets", self.row(id="a"))
        illustration.append_row(self.tmp / "assets", self.row(id="b", cost_credits=2.0))
        from pipeline.capture import append_to_manifest
        append_to_manifest(self.tmp / "assets", {"id": "stock", "file": "s.mp4",
                                                 "kind": "video", "license": "CC0"})
        self.assertEqual(len(illustration.ledger("ep")), 2)
        self.assertEqual(illustration.spent("ep"), 9.5)

    def test_the_cap_refuses_at_the_boundary(self):
        illustration.append_row(self.tmp / "assets", self.row(id="a", cost_credits=292.5))
        illustration.cap_check("ep", [_round(estimate_credits=7.5)])
        with self.assertRaises(IngestError):
            illustration.cap_check("ep", [_round(estimate_credits=7.6)])

    def test_the_channel_ledger_is_separate_and_summed(self):
        with mock.patch.object(illustration, "CHANNEL_LEDGER", self.tmp / "ch.json"):
            illustration.append_channel_row({"what": "Soul training", "credits": 25.0,
                                             "ts": "2026-09-16T03:38:00Z"})
            self.assertEqual(illustration.channel_spent(), 25.0)
            with self.assertRaises(IngestError):
                illustration.append_channel_row({"what": "no cost"})


class BinaryPath(unittest.TestCase):
    def test_env_then_dotenv_then_which(self):
        with mock.patch.dict(os.environ, {"NINTH_ROOM_HIGGSFIELD_BIN": "/tmp/x"}):
            self.assertEqual(paths.higgsfield_bin(), "/tmp/x")
        with mock.patch.dict(os.environ, {}, clear=False), \
                mock.patch.object(paths, "_dotenv", lambda k: None), \
                mock.patch.object(paths.shutil, "which", lambda n: "/usr/local/bin/higgsfield"):
            os.environ.pop("NINTH_ROOM_HIGGSFIELD_BIN", None)
            self.assertEqual(paths.higgsfield_bin(), "/usr/local/bin/higgsfield")

    def test_the_soul_id_is_a_setting(self):
        with mock.patch.dict(os.environ, {"NINTH_ROOM_SOUL_ID": "c292"}):
            self.assertEqual(paths.soul_id(), "c292")

    def test_the_cli_wrapper_times_out_as_an_ingest_error(self):
        import subprocess
        def boom(cmd, **kw):
            raise subprocess.TimeoutExpired(cmd, kw.get("timeout"))
        with mock.patch.object(illustration.subprocess, "run", boom):
            with self.assertRaises(IngestError):
                illustration.cli(["account", "status"], timeout=1)


class SchemaHooks(unittest.TestCase):
    def test_illustration_is_a_from_and_is_not_sourced(self):
        self.assertIn("illustration", schemas.VISUAL_FROM)
        self.assertIn("illustration", schemas._NOT_SOURCED)

    def test_a_stale_illustration_round_is_retired_on_both_lanes(self):
        moved = json.loads(json.dumps(SCRIPT))
        moved["chapters"][0]["sections"][0]["visual"]["from"] = "stock"
        reqs = {"rounds": [{"section_id": "CH2.S3", "kind": "illustration", "status": "proposed"}]}
        self.assertEqual(schemas.superseded_requests(moved, reqs), [0])
        self.assertEqual(schemas.superseded_requests(SCRIPT, reqs), [])
        reqs = {"rounds": [{"beat_id": "shot-T99", "kind": "illustration", "status": "proposed"}]}
        self.assertEqual(schemas.superseded_requests({}, reqs, plan=PLAN), [0])
        reqs = {"rounds": [{"beat_id": "shot-T41", "kind": "illustration", "status": "proposed"}]}
        self.assertEqual(schemas.superseded_requests({}, reqs, plan=PLAN), [])

    def test_the_sourcer_can_exclude_illustration_sections(self):
        self.assertEqual(schemas.unproposed_sections(SCRIPT, {}), ["CH2.S3"])
        self.assertEqual(schemas.unproposed_sections(SCRIPT, {}, exclude_from=("illustration",)), [])

    def test_a_footage_lane_beat_may_carry_a_visual_block(self):
        takes = {"takes": [{"id": "T41", "file": "a.mp4", "s": 0.0, "e": 30.0, "transcript": "x"}]}
        broll = {"slug": "ep", "clips": []}
        plan = {"slug": "ep", "beats": [{"id": "b", "purpose": "build", "take_id": "T41",
                                         "trim": {"s": 1.0, "e": 5.0}, "broll": [],
                                         "visual": {"want": "x", "why": "illustrate: x", "from": "illustration"}}]}
        self.assertEqual([e for e in schemas.validate_edit_plan(plan, takes, broll) if "visual" in e], [])
        plan["beats"][0]["visual"]["from"] = "magic"
        self.assertTrue(any("visual" in e for e in schemas.validate_edit_plan(plan, takes, broll)))


if __name__ == "__main__":
    unittest.main()
