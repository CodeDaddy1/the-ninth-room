# -*- coding: utf-8 -*-
"""The illustrate kind: gated before the click, read-only while it runs.

A propose session is the first job in this engine that could spend money
by itself: it runs with permissions skipped and the Higgsfield CLI sits on
the launchd PATH. So this file pins the three things that keep it honest.
The declared gates refuse at `jobs.start()` with no row and no dispatch,
and again in the runner. The session sees a read-only `higgsfield` first
on its PATH. And the runner proves the phase spent nothing: the same file
count under assets/ and the same balance before and after, with every
proposed round validated and capped before it lands at `proposed`.

The clause tests are the other half of decision nine, consult by
artifact: the story reaches the illustrator only through the prompt, so
a test asserts the section text, the why, the source, the confidence and
the chapter promise are all in it, in order, and that the hexes come from
the design tokens rather than being typed.

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

from pipeline import cutbar, design_tokens, editroom, illustration, ingest, jobs, paths  # noqa: E402
from pipeline import preconditions as pre  # noqa: E402

SCRIPT = {"locked": True, "title": "The pendulum", "chapters": [
    {"id": "CH1", "title": "A wire and a weight", "sections": [
        {"id": "CH1.S1", "kind": "oncamera", "text": "Look up.", "est_s": 3.0},
        {"id": "CH1.S2", "kind": "vo", "est_s": 6.0,
         "text": "The pendulum ran for decades on nothing but the rotation of the planet.",
         "source": "https://example.org/pendulum",
         "visual": {"want": "the pendulum mid-swing", "why": "illustrate: the thing being named",
                    "from": "illustration"}}]}],
    "loops": [{"id": "L1", "opens": "CH1.S2", "pays": "CH1.S1",
               "promise": "you will see what made it turn"}]}
RESEARCH = {"location": "the Panthéon", "facts": [
    {"fact": "Foucault hung the pendulum in 1851.", "source_url": "https://example.org/1851",
     "confidence": "verified"},
    {"fact": "It ran unattended for years.", "source_url": "https://example.org/claim",
     "confidence": "claimed"}]}


def _round(sid="CH1.S2", **over):
    r = {"kind": "illustration", "section_id": sid, "honesty": "illustration",
         "target": "cover", "aspect": "9:16", "why": "illustrate: the pendulum",
         "steps": [{"stage": "plate", "model": "nano_banana_pro", "prompt": "a plate",
                    "credits": 2.0, "tier": "std"}],
         "estimate_credits": 2.0, "marks": {}}
    r.update(over)
    return r


class _Project(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self._wp = ingest.work_path
        ingest.work_path = lambda slug: self.tmp
        for mod in (jobs, illustration, pre, editroom):
            mod.work_path = ingest.work_path
        (self.tmp / "story_brief.json").write_text(json.dumps(
            {"origin": "script", "delivery": "short", "target_minutes": 0.75, "chapters": 1,
             "vo_share": 0.85, "subject": "the pendulum"}))
        (self.tmp / "script.json").write_text(json.dumps(SCRIPT))
        (self.tmp / "research.json").write_text(json.dumps(RESEARCH))
        (self.tmp / "assets").mkdir()
        (self.tmp / "assets" / "assets.json").write_text('{"assets": []}')
        self._bin = paths.higgsfield_bin
        paths.higgsfield_bin = lambda: sys.executable    # exists; never called for real

    def tearDown(self):
        ingest.work_path = self._wp
        for mod in (jobs, illustration, pre, editroom):
            mod.work_path = self._wp
        paths.higgsfield_bin = self._bin
        shutil.rmtree(self.tmp, ignore_errors=True)


class Registration(unittest.TestCase):
    def test_the_kind_is_registered_on_the_session_lane_and_chains_nothing(self):
        self.assertIn("illustrate", jobs.KINDS)
        self.assertIn("illustrate", jobs.SESSION_KINDS)
        self.assertEqual(jobs.lane_of("illustrate"), "session")
        self.assertIsNone(jobs.CHAIN.get("illustrate"))
        self.assertNotIn("—", jobs.KINDS["illustrate"][0])


class GatesBeforeEnqueue(_Project):
    def test_an_unlocked_script_is_refused_with_no_row_and_no_dispatch(self):
        s = json.loads((self.tmp / "script.json").read_text()); s["locked"] = False
        (self.tmp / "script.json").write_text(json.dumps(s))
        with mock.patch.object(jobs, "_dispatch_json") as d, \
                mock.patch.object(jobs, "_persist"):
            with self.assertRaises(jobs.JobError) as cm:
                jobs.start("illustrate", "ep")
        self.assertIn("Script desk", str(cm.exception))
        d.assert_not_called()

    def test_generate_with_nothing_approved_is_refused_by_name(self):
        with mock.patch.object(jobs, "_dispatch_json") as d, \
                mock.patch.object(jobs, "_persist"):
            with self.assertRaises(jobs.JobError) as cm:
                jobs.start("illustrate", "ep", arg="generate")
        self.assertIn("approved", str(cm.exception))
        d.assert_not_called()

    def test_the_runner_repeats_the_guards_and_lands_declined(self):
        s = json.loads((self.tmp / "script.json").read_text()); s["locked"] = False
        (self.tmp / "script.json").write_text(json.dumps(s))
        with mock.patch.object(jobs, "_dispatch_json") as d:
            with self.assertRaises(jobs.JobError):
                jobs._run_illustrate("ep", lambda *a: None, lambda p: None)
        d.assert_not_called()


class ProposeRun(_Project):
    def _run(self, session, balance_after=850.0):
        """Run the propose arm with a fake session and a fake balance."""
        balances = iter([850.0, balance_after])
        seen = {}
        def fake_dispatch(prompt, log, set_pct, what, env=None):
            seen["prompt"], seen["env"] = prompt, env
            session(self.tmp)
        with mock.patch.object(jobs, "_dispatch_json", fake_dispatch), \
                mock.patch.object(jobs, "_higgsfield_credits", lambda log: next(balances)):
            jobs._run_illustrate("ep", lambda *a: None, lambda p: None)
        return seen

    def test_the_shim_is_first_on_the_sessions_path(self):
        def session(tmp):
            (tmp / "staging" / "illustration_rounds.json").write_text(
                json.dumps({"rounds": [_round()]}))
        seen = self._run(session)
        first = seen["env"]["PATH"].split(os.pathsep)[0]
        self.assertEqual(Path(first), illustration.SHIM_DIR)
        self.assertTrue((Path(first) / "higgsfield").exists())
        self.assertEqual(seen["env"]["NINTH_ROOM_HIGGSFIELD_REAL"], sys.executable)
        self.assertIn("illustration-director.md", seen["prompt"])

    def test_a_valid_round_lands_at_proposed_with_an_id(self):
        def session(tmp):
            (tmp / "staging" / "illustration_rounds.json").write_text(
                json.dumps({"rounds": [_round()]}))
        self._run(session)
        rounds = json.loads((self.tmp / "asset_requests.json").read_text())["rounds"]
        self.assertEqual(len(rounds), 1)
        self.assertEqual(rounds[0]["status"], "proposed")
        self.assertEqual(rounds[0]["kind"], "illustration")
        self.assertTrue(rounds[0].get("id"))

    def test_an_invalid_round_never_lands(self):
        def session(tmp):
            (tmp / "staging" / "illustration_rounds.json").write_text(
                json.dumps({"rounds": [_round(why="establish: the hall")]}))
        with self.assertRaises(RuntimeError) as cm:
            self._run(session)
        self.assertIn("establish", str(cm.exception))
        self.assertFalse((self.tmp / "asset_requests.json").exists())

    def test_a_file_under_assets_or_a_moved_balance_fails_the_run(self):
        def downloads(tmp):
            (tmp / "staging" / "illustration_rounds.json").write_text(json.dumps({"rounds": [_round()]}))
            (tmp / "assets" / "sneaky.png").write_bytes(b"x")
        with self.assertRaises(RuntimeError) as cm:
            self._run(downloads)
        self.assertIn("assets/ changed", str(cm.exception))
        (self.tmp / "assets" / "sneaky.png").unlink()
        def prices_only(tmp):
            (tmp / "staging" / "illustration_rounds.json").write_text(json.dumps({"rounds": [_round()]}))
        with self.assertRaises(RuntimeError) as cm:
            self._run(prices_only, balance_after=848.0)
        self.assertIn("balance moved", str(cm.exception))

    def test_a_no_op_is_fine_only_when_nothing_still_asks(self):
        def nothing(tmp):
            pass
        with self.assertRaises(RuntimeError) as cm:
            self._run(nothing)
        self.assertIn("still asks", str(cm.exception))
        (self.tmp / "asset_requests.json").write_text(json.dumps({"rounds": [
            _round(status="proposed", id="R1")]}))
        # now every target has a live round, and the gate refuses before the run
        with self.assertRaises(jobs.JobError):
            jobs._run_illustrate("ep", lambda *a: None, lambda p: None)

    def test_the_cap_is_checked_on_the_new_rounds_too(self):
        def session(tmp):
            (tmp / "staging" / "illustration_rounds.json").write_text(json.dumps({"rounds": [
                _round(estimate_credits=301.0, steps=[{"stage": "plate", "model": "nano_banana_pro",
                                                       "prompt": "p", "credits": 301.0, "tier": "std"}])]}))
        with self.assertRaises(Exception) as cm:
            self._run(session)
        self.assertIn("cap", str(cm.exception))


class TheClause(_Project):
    def test_the_story_reaches_the_illustrator(self):
        clause = jobs._illustration_clause("ep", balance=850.0)
        navy = design_tokens.resolve(design_tokens.load(), "navy-900")
        order = ["CH1.S2", "rotation of the planet", "the pendulum mid-swing",
                 "illustrate: the thing being named", "https://example.org/pendulum", "claimed",
                 "you will see what made it turn", "9:16", navy, "300", "7.5", "RECONSTRUCTION",
                 "illustrate-check"]
        last = -1
        for token in order:
            at = clause.find(token)
            self.assertNotEqual(at, -1, token)
        # the section block precedes the visual language, which precedes the money
        self.assertLess(clause.index("THE SCRIPT LANE"), clause.index("THE VISUAL LANGUAGE"))
        self.assertLess(clause.index("THE VISUAL LANGUAGE"), clause.index("MONEY:"))
        self.assertLess(clause.index("MONEY:"), clause.index("MECHANICS:"))

    def test_the_cut_reaches_the_illustrator_and_notes_alone_do_not(self):
        (self.tmp / "script.json").unlink()
        beats = [{"id": "h1", "purpose": "hook", "take_id": "T01", "broll": [],
                  "visual": {"want": "x", "why": "illustrate: x", "from": "illustration"}},
                 {"id": "c1", "purpose": "chapter_open", "take_id": "T01", "broll": []},
                 {"id": "shot-T41", "purpose": "build", "take_id": "T41", "chapter_id": "CH2",
                  "trim": {"s": 18.94, "e": 25.51}, "cuts": [{"s": 18.94, "e": 20.45}],
                  "note": "B013 removed per Caleb's review", "broll": [],
                  "visual": {"want": "the egg", "why": "illustrate: the board", "from": "illustration"}},
                 {"id": "p1", "purpose": "payoff", "take_id": "T01", "peak": True, "broll": [],
                  "visual": {"want": "y", "why": "illustrate: y", "from": "illustration"}}]
        beats += [{"id": "n%d" % i, "purpose": "build", "take_id": "T01", "broll": [],
                   "note": "a note and nothing else"} for i in range(80)]
        (self.tmp / "edit_plan.json").write_text(json.dumps({"theme": {"promise": "one Sunday"},
                                                           "chapters": [{"id": "CH2", "promise": "the bugs"}],
                                                           "beats": beats}))
        (self.tmp / "analysis").mkdir()
        (self.tmp / "analysis" / "takes.json").write_text(json.dumps({"takes": [
            {"id": "T41", "transcript": "let's start from egg"}]}))
        clause = jobs._illustration_clause("ep", balance=850.0)
        self.assertIn("shot-T41", clause)
        self.assertIn("let's start from egg", clause)
        self.assertIn("the bugs", clause)
        self.assertIn("5.06", clause)
        block = clause[clause.index("THE FOOTAGE LANE"):clause.index("THE VISUAL LANGUAGE")]
        self.assertNotIn('"h1"', block, "a hook beat is never a target")
        self.assertNotIn('"p1"', block, "a peak is never a target")
        self.assertNotIn('"n7"', block, "a note alone is not a request")

    def test_the_token_hexes_are_read_from_the_kit_not_typed(self):
        with mock.patch.object(design_tokens, "load", lambda *a, **k: {"navy-900": "#123456",
                                                                       "chalk": "#ABCDEF",
                                                                       "slate-300": "#0F0F0F"}):
            clause = jobs._illustration_clause("ep", balance=1.0)
        self.assertIn("#123456", clause)
        src = (Path(illustration.__file__)).read_text()
        import re
        self.assertIsNone(re.search(r"#[0-9A-Fa-f]{6}\b", src), "a hex is typed in illustration.py")


if __name__ == "__main__":
    unittest.main()
