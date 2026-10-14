# -*- coding: utf-8 -*-
"""One spend is one operation: create, a pending row, wait, download,
probe, finalize. Nothing else may move a credit.

Decision 7 (every spend gets a ledger row) and the sfx precedent (a file
and its row are one operation) meet Higgsfield's shape: `generate create`
returns a job id at once, the wait can take twenty minutes, and the
transaction log carries no job id. So the row is written `pending` with
the job id BEFORE the wait, a death between create and download leaves a
row to finalize instead of a stray to re-spend, and the run is reconciled
against the balance delta and the transaction window afterwards.

Every Higgsfield call in these tests is a stub: the CLI is never run.

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

from pipeline import editroom, illustration as il, ingest, jobs, paths  # noqa: E402
from pipeline import preconditions as pre  # noqa: E402
from pipeline.ingest import IngestError  # noqa: E402

JOB_PLATE = "11111111-1111-1111-1111-111111111111"
JOB_MOTION = "22222222-2222-2222-2222-222222222222"


def _round(**over):
    r = {"id": "R1", "kind": "illustration", "section_id": "CH1.S2", "status": "approved",
         "honesty": "illustration", "target": "cover", "aspect": "9:16",
         "why": "illustrate: the pendulum", "note": "n", "ts": 1,
         "steps": [{"stage": "plate", "model": "nano_banana_pro", "prompt": "a plate",
                    "credits": 2.0, "tier": "std"},
                   {"stage": "motion", "model": "kling3_0", "start_image": "plate",
                    "prompt": "it swings", "credits": 7.5, "tier": "std"}],
         "estimate_credits": 9.5, "marks": {}}
    r.update(over)
    return r


class FakeHiggsfield(object):
    """Answers illustration.cli the way the real CLI does, and records
    every call. `balance` drops by the create's cost when the job is
    waited on, like the account."""

    def __init__(self, balance=850.0, cost=None, die_after_create=False, refuse=None):
        self.calls, self.balance = [], balance
        self.cost = cost or {"nano_banana_pro": 2.0, "kling3_0": 7.5, "seedance_2_5": 45.0}
        self.die_after_create, self.refuse = die_after_create, refuse
        self.created = {}
        self.transactions = []

    @staticmethod
    def name(model):
        return {"nano_banana_pro": "Nano Banana Pro", "kling3_0": "Kling v3.0",
                "seedance_2_5": "Seedance 2.5"}.get(model, model)

    def __call__(self, args, timeout=120.0):
        self.calls.append(list(args))
        verb = tuple(args[:2])
        if verb == ("account", "status"):
            return 0, json.dumps({"credits": self.balance}), ""
        if verb == ("generate", "cost"):
            return 0, json.dumps({"credits": self.cost[args[2]]}), ""
        if verb == ("generate", "create"):
            model = args[2]
            jid = JOB_PLATE if model == "nano_banana_pro" else JOB_MOTION
            self.created[jid] = model
            # the REAL shape without --wait: a bare list of id strings, no
            # display name (2026-09-16)
            return 0, json.dumps([jid]), ""
        if verb == ("generate", "wait"):
            jid = args[2]
            if self.die_after_create:
                self.die_after_create = False
                raise RuntimeError("engine died after create, before the wait")
            model = self.created.get(jid) or ("nano_banana_pro" if jid == JOB_PLATE else "kling3_0")
            if self.refuse:
                return 0, json.dumps({"id": jid, "status": "failed", "fail_reason": self.refuse}), ""
            self.balance -= self.cost[model]
            self.transactions.insert(0, {"display_name": self.name(model), "credits": -self.cost[model],
                                         "action": "spend", "created_at": "2099-01-01T00:00:00Z"})
            ext = "png" if model == "nano_banana_pro" else "mp4"
            return 0, json.dumps({"id": jid, "job_type": model, "display_name": self.name(model),
                                  "status": "completed", "result_url": "https://x/%s.%s" % (jid, ext)}), ""
        if verb == ("account", "transactions"):
            return 0, json.dumps({"items": list(self.transactions)}), ""
        return 1, "", "unknown"


class _Project(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self._wp = ingest.work_path
        ingest.work_path = lambda slug: self.tmp
        for mod in (jobs, il, pre, editroom):
            mod.work_path = ingest.work_path
        (self.tmp / "assets").mkdir()
        (self.tmp / "assets" / "assets.json").write_text('{"assets": []}')
        (self.tmp / "story_brief.json").write_text(json.dumps({"origin": "script", "delivery": "short"}))
        (self.tmp / "script.json").write_text(json.dumps({"locked": True, "chapters": [{"id": "CH1", "sections": [
            {"id": "CH1.S2", "kind": "vo", "text": "x", "visual": {"want": "w", "why": "illustrate: w", "from": "illustration"}}]}]}))
        (self.tmp / "asset_requests.json").write_text(json.dumps({"rounds": [_round()]}))
        self.hf = FakeHiggsfield()
        self._cli = il.cli
        il.cli = self.hf
        self._dl = il.download
        il.download = lambda url, dest, log=None: (Path(dest).write_bytes(b"media"), dest)[1]
        self._probe = il.probe_media
        il.probe_media = lambda p, expect_seconds=None: {"width": 1284, "height": 716, "duration": 5.04}
        self._bin = paths.higgsfield_bin
        paths.higgsfield_bin = lambda: sys.executable

    def tearDown(self):
        ingest.work_path = self._wp
        for mod in (jobs, il, pre, editroom):
            mod.work_path = self._wp
        il.cli, il.download, il.probe_media = self._cli, self._dl, self._probe
        paths.higgsfield_bin = self._bin
        shutil.rmtree(self.tmp, ignore_errors=True)

    def rows(self):
        return json.loads((self.tmp / "assets" / "assets.json").read_text())["assets"]

    def rounds(self):
        return json.loads((self.tmp / "asset_requests.json").read_text())["rounds"]


class SpendStep(_Project):
    def test_one_spend_is_one_row_pending_before_wait_then_done(self):
        states = []
        real_cli = self.hf
        def spy(args, timeout=120.0):
            if tuple(args[:2]) == ("generate", "wait"):
                states.append([r["status"] for r in self.rows()])
            return real_cli(args, timeout)
        il.cli = spy
        row = il.spend("ep", "R1", "plate", log=lambda *a: None)
        self.assertEqual(states, [["pending"]], "the row exists before the wait")
        self.assertEqual(row["status"], "done")
        self.assertEqual(row["job_id"], JOB_PLATE)
        self.assertEqual(row["cost_credits"], 2.0)
        self.assertEqual(row["honesty"], "illustration")
        self.assertEqual(row["file"], "R1-plate.png")
        self.assertTrue((self.tmp / "assets" / "R1-plate.png").exists())
        self.assertEqual(row["kind"], "illustration")
        self.assertTrue(row["license"].startswith("Higgsfield ToU"))

    def test_the_motion_step_resolves_start_image_to_the_plates_job_id(self):
        il.spend("ep", "R1", "plate", log=lambda *a: None)
        il.spend("ep", "R1", "motion", log=lambda *a: None)
        create = [c for c in self.hf.calls if c[:2] == ["generate", "create"] and c[2] == "kling3_0"][0]
        self.assertIn(JOB_PLATE, create)
        self.assertNotIn("R1-plate.png", " ".join(create), "never a local path")
        self.assertEqual([r["status"] for r in self.rounds()], ["done"], "every step done closes the round")

    def test_a_done_step_is_skipped_and_a_pending_one_finalized_without_a_second_create(self):
        il.spend("ep", "R1", "plate", log=lambda *a: None)
        n = len([c for c in self.hf.calls if c[:2] == ["generate", "create"]])
        il.spend("ep", "R1", "plate", log=lambda *a: None)
        self.assertEqual(len([c for c in self.hf.calls if c[:2] == ["generate", "create"]]), n)
        # a death after create: the pending row survives, the rerun finalizes it
        self.hf.die_after_create = True
        with self.assertRaises(RuntimeError):
            il.spend("ep", "R1", "motion", log=lambda *a: None)
        self.assertEqual([r["status"] for r in self.rows() if r["id"] == "R1-motion"], ["pending"])
        row = il.spend("ep", "R1", "motion", log=lambda *a: None)
        self.assertEqual(row["status"], "done")
        creates = [c for c in self.hf.calls if c[:2] == ["generate", "create"] and c[2] == "kling3_0"]
        self.assertEqual(len(creates), 1)

    def test_marks_swap_the_model_and_set_the_tier(self):
        r = _round(marks={"seedance": True, "pro": ["plate"]})
        r["steps"][0]["tier"] = "pro"; r["steps"][0]["reason"] = "hero"
        r["steps"][1]["model"] = il.SEEDANCE_MODEL; r["steps"][1]["credits"] = 45.0
        r["estimate_credits"] = 47.0
        (self.tmp / "asset_requests.json").write_text(json.dumps({"rounds": [r]}))
        self.hf.created[JOB_MOTION] = "seedance_2_5"
        il.spend("ep", "R1", "plate", log=lambda *a: None)
        plate = [c for c in self.hf.calls if c[:2] == ["generate", "create"]][0]
        self.assertIn("4k", plate)
        cmd = il.step_command(r, r["steps"][1], {"plate": JOB_PLATE}, None)
        self.assertEqual(cmd[2], il.SEEDANCE_MODEL)
        self.assertIn("omni_reference", cmd)

    def test_a_price_over_the_estimate_by_ten_percent_is_refused_before_create(self):
        self.hf.cost["nano_banana_pro"] = 2.3
        with self.assertRaises(IngestError) as cm:
            il.spend("ep", "R1", "plate", log=lambda *a: None)
        self.assertIn("estimate", str(cm.exception))
        self.assertFalse(any(c[:2] == ["generate", "create"] for c in self.hf.calls))

    def test_the_cap_is_checked_on_the_remaining_steps(self):
        from pipeline.capture import append_to_manifest
        append_to_manifest(self.tmp / "assets", {"id": "old", "file": "o.mp4", "kind": "illustration",
                                                 "honesty": "illustration", "model": "kling3_0",
                                                 "job_id": "j", "cost_credits": 295.0, "status": "done"})
        with self.assertRaises(IngestError):
            il.spend("ep", "R1", "motion", log=lambda *a: None)

    def test_a_refused_job_finalizes_at_zero_and_raises(self):
        self.hf.refuse = "nsfw"
        with self.assertRaises(IngestError) as cm:
            il.spend("ep", "R1", "plate", log=lambda *a: None)
        self.assertIn("nsfw", str(cm.exception))
        row = [r for r in self.rows() if r["id"] == "R1-plate"][0]
        self.assertEqual((row["status"], row["cost_credits"]), ("refused", 0.0))

    def test_a_soul_step_carries_the_reference_only_on_a_soul_model(self):
        cmd = il.step_command(_round(honesty="reconstruction"),
                              {"stage": "plate", "model": "soul_cinema_studio", "soul": True,
                               "prompt": "p", "credits": 2.0, "tier": "std"}, {}, "c292")
        self.assertIn("--custom_reference_id", cmd); self.assertIn("c292", cmd)
        with self.assertRaises(IngestError):
            il.step_command(_round(), {"stage": "plate", "model": "kling3_0", "soul": True,
                                       "prompt": "p", "credits": 2.0}, {}, "c292")


class CliShapes(unittest.TestCase):
    def test_every_shape_the_cli_returns_yields_the_job_id(self):
        jid = "35284981-d738-4472-932d-7a3ccb28cdde"
        self.assertEqual(il._json_out(json.dumps({"id": jid}), "x")["id"], jid)
        self.assertEqual(il._json_out(json.dumps([{"id": jid}]), "x")["id"], jid)
        self.assertEqual(il._json_out(json.dumps([jid]), "x")["id"], jid)
        self.assertEqual(il._json_out("created " + jid + "\n", "x")["id"], jid)


class Reconcile(_Project):
    def test_a_matched_window_is_clean_and_a_stray_is_named(self):
        rows = [{"id": "R1-plate", "display_name": "Nano Banana Pro", "cost_credits": 2.0,
                 "status": "done", "created_at": "2026-09-16T10:00:05Z"}]
        items = [{"display_name": "Nano Banana Pro", "credits": -2, "action": "spend",
                  "created_at": "2026-09-16T10:00:07Z"}]
        self.assertEqual(il.reconcile(rows, items, balance_delta=2.0), {"unmatched_items": [], "unmatched_rows": []})
        stray = items + [{"display_name": "Seedance 2.5", "credits": -270, "action": "spend",
                          "created_at": "2026-09-16T10:00:09Z"}]
        out = il.reconcile(rows, stray, balance_delta=272.0)
        self.assertEqual(len(out["unmatched_items"]), 1)
        out = il.reconcile(rows + [{"id": "R1-motion", "display_name": "Kling v3.0", "cost_credits": 7.5,
                                    "status": "done", "created_at": "z"}], items, balance_delta=2.0)
        self.assertEqual(len(out["unmatched_rows"]), 1)


class GenerateRun(_Project):
    def test_the_runner_spends_every_approved_step_and_reconciles(self):
        with mock.patch.object(jobs, "_dispatch_json") as d:
            jobs._run_illustrate("ep", lambda *a: None, lambda p: None, arg="generate")
        d.assert_not_called()
        self.assertEqual(sorted(r["status"] for r in self.rows()), ["done", "done"])
        self.assertEqual(self.rounds()[0]["status"], "done")
        self.assertEqual(il.spent("ep"), 9.5)

    def test_a_failing_step_keeps_the_round_approved_and_names_it(self):
        self.hf.cost["kling3_0"] = 9.0     # over the estimate: the motion step refuses
        with self.assertRaises(Exception) as cm:
            jobs._run_illustrate("ep", lambda *a: None, lambda p: None, arg="generate")
        self.assertIn("motion", str(cm.exception))
        r = self.rounds()[0]
        self.assertEqual(r["status"], "approved")
        self.assertTrue(r["steps"][0].get("done"))
        self.assertIn("motion", r.get("error", ""))

    def test_a_second_click_with_nothing_approved_is_refused_before_enqueue(self):
        with mock.patch.object(jobs, "_dispatch_json"), mock.patch.object(jobs, "_persist"):
            jobs._run_illustrate("ep", lambda *a: None, lambda p: None, arg="generate")
            with self.assertRaises(jobs.JobError):
                jobs.start("illustrate", "ep", arg="generate")


if __name__ == "__main__":
    unittest.main()
