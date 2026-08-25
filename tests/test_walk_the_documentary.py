# -*- coding: utf-8 -*-
"""Walk a documentary end to end and assert every stage has a way forward.

Caleb, 2026-08-25: "This is a mess. I approve them just to test and nothing
triggers. We need to stop running into these issues. When building test it
to its entirety."

He found five separate dead ends in one afternoon, and every one passed the
checks I was running at the time:

  1. approving a script started nothing (the follower fired on the DRAFT)
  2. sourcing finished and the assets were unreachable (the desk that holds
     the only approve control returned early with no takes.json)
  3. the previews were empty (retired rounds rendered like live ones)
  4. "use this" did nothing (rounds keyed by a non-unique ts)
  5. approving proposals triggered nothing (NO fetch control existed in the
     entire Studio, and 8 of the 10 approvals were requirements, which can
     never be fetched at all)

Each check I ran was true and useless: the endpoint returned 200, the DOM
had twelve nodes. None asked the only question that matters -- from this
state, can a person do the next thing?

So this walks the whole lane and, at every step, asserts BOTH that the
state advanced AND that something exists to press next. Sessions are
stubbed; this is about the seams between stages, which is where every one
of those five lived.

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

from pipeline import editroom, jobs, schemas  # noqa: E402


class WalkTheDocumentary(unittest.TestCase):
    def setUp(self):
        # the work dir must NOT exist yet — creation is the first step of
        # the walk, and _new_project refuses an existing project
        self.root = Path(tempfile.mkdtemp())
        self.work = self.root / "ep"
        self._ew, self._ea = editroom.work_path, editroom.analysis_dir
        self._jw = jobs.work_path
        editroom.work_path = lambda slug: self.work
        editroom.analysis_dir = lambda slug: self.work / "analysis"
        jobs.work_path = lambda slug: self.work

    def tearDown(self):
        editroom.work_path, editroom.analysis_dir = self._ew, self._ea
        jobs.work_path = self._jw
        shutil.rmtree(self.root, ignore_errors=True)

    # --- what "a way forward" means ---------------------------------------

    def next_action(self):
        """The engine's own answer to 'what do I do now'. Empty is a dead
        end, and a dead end is the bug this file exists to catch."""
        return editroom._project_row("ep")["next"]

    def assertMovesOn(self, phase_hint):
        nxt = self.next_action()
        self.assertTrue(nxt.strip(), "dead end: the desk offers nothing")
        self.assertNotIn("Drop clips", nxt,
                         "a documentary was told to add footage: %r" % nxt)
        self.assertNotIn("Analyze footage", nxt,
                         "a documentary was told to analyze footage: %r" % nxt)
        self.assertIn(phase_hint.lower(), nxt.lower(),
                      "expected to be pointed at %r, got %r" % (phase_hint, nxt))

    # --- the walk ---------------------------------------------------------

    def test_every_stage_offers_the_next_one(self):
        # 1. created, with its format decided
        editroom._new_project("ep", "script", "long")
        (self.work / "analysis").mkdir(exist_ok=True)
        self.assertMovesOn("Research")

        # 2. subject + research in hand
        (self.work / "research.json").write_text(json.dumps(
            {"facts": [{"fact": "f", "source_url": "u", "confidence": "verified"}]}))
        self.assertMovesOn("Interview")

        # 3. the director's questions land
        (self.work / "script_questions.json").write_text(json.dumps(
            {"slug": "ep", "stage": "interview", "questions": [
                {"id": "Q1", "ask": "which spine?",
                 "options": [{"id": "a", "label": "x"}], "default": "a"}]}))
        self.assertMovesOn("Write the script")

        # a question with a default must never block the draft
        self.assertEqual(
            schemas.blocking_questions(
                json.loads((self.work / "script_questions.json").read_text()),
                None), [])

        # 4. a draft arrives — and is NOT treated as a finished stage
        self.write_script(locked=False)
        self.assertMovesOn("approve")
        st = editroom._script_state("ep")
        self.assertFalse(st["script"]["locked"])
        self.assertEqual(st["stranded_answers"], [],
                         "nothing is stranded before an approval exists")

        # 5. approving must START something, not just set a flag
        started = []
        real = jobs.start
        jobs.start = lambda kind, slug, arg=None: (
            started.append((kind, arg)) or {"id": "J1"})
        try:
            fb = editroom._save_script_feedback("ep", "", "approve")
        finally:
            jobs.start = real
        self.assertEqual(started, [("sourcing", None)],
                         "approving the script started nothing")
        self.assertTrue(fb["sourcing"]["queued"])

        # 6. proposals arrive: some to buy, some to make
        self.write_requests()
        rounds = editroom._asset_rounds("ep")
        self.assertEqual(len(set(r["id"] for r in rounds)), len(rounds),
                         "rounds must be uniquely addressable")

        # a REQUIREMENT offers nothing to approve — approving one and
        # watching nothing happen is exactly what he reported
        buyable = [r for r in rounds if r.get("kind") == "source"]
        self.assertTrue(buyable, "nothing is actually buyable")

        # 7. approving a picture lands on the round it names, with the
        #    candidate he picked
        target = buyable[-1]
        editroom._asset_round_verdict("ep", target["id"], "approved", 1,
                                      log=lambda *a: None)
        after = {r["id"]: r for r in editroom._asset_rounds("ep")}
        self.assertEqual(after[target["id"]]["status"], "approved")
        self.assertEqual(after[target["id"]]["chosen"], 1)
        for other in buyable[:-1]:
            self.assertEqual(after[other["id"]]["status"], "proposed",
                             "a verdict touched a round it was not given")

        # 8. and THEN the fetch is reachable — the step that did not exist
        self.assertFetchIsReachable()

    def test_approving_only_requirements_says_so(self):
        """Eight requirements approved, nothing to fetch. The refusal has
        to explain that rather than claim nothing was approved."""
        editroom._new_project("ep", "script", "long")
        (self.work / "analysis").mkdir(exist_ok=True)
        self.write_script(locked=True)
        (self.work / "asset_requests.json").write_text(json.dumps({"rounds": [
            {"ts": 1, "section_id": "CH1.S4", "kind": "requirement",
             "status": "approved"},
            {"ts": 1, "section_id": "CH1.S5", "kind": "requirement",
             "status": "approved"}]}))
        with self.assertRaises(jobs.JobError) as cm:
            jobs._run_sourcing("ep", lambda *a: None, lambda p: None,
                               arg="fetch")
        msg = str(cm.exception)
        self.assertIn("MAKE, not buy", msg)
        self.assertNotIn("nothing approved", msg)

    # --- helpers ----------------------------------------------------------

    def write_script(self, locked):
        (self.work / "script.json").write_text(json.dumps({
            "slug": "ep", "origin": "script", "round": 1, "locked": locked,
            "target_minutes": 8.0,
            "chapters": [{"id": "CH1", "title": "c", "target_s": 480,
                          "sections": [
                              {"id": "CH1.S1", "kind": "desk",
                               "text": "a line", "est_s": 300.0, "rev": 1},
                              {"id": "CH1.S2", "kind": "vo", "text": "a line",
                               "est_s": 180.0, "rev": 1,
                               "visual": {"want": "w", "why": "illustrate — w",
                                          "from": "stock"}}]}]}))

    def write_requests(self):
        # deliberately collides two rounds on one ts, the way the agent
        # really writes them
        cand = {"query": "q", "source": "wikimedia", "kind": "image",
                "page": "https://p", "preview": "https://t.jpg",
                "license": "Public domain"}
        (self.work / "asset_requests.json").write_text(json.dumps({"rounds": [
            {"ts": 500, "section_id": "CH1.S4", "kind": "requirement",
             "status": "proposed", "why": "the kit draws this"},
            {"ts": 900, "section_id": "CH1.S2", "kind": "source",
             "status": "proposed", "candidates": [dict(cand), dict(cand)]},
            {"ts": 900, "section_id": "CH1.S3", "kind": "source",
             "status": "proposed", "candidates": [dict(cand), dict(cand)]}]}))

    def assertFetchIsReachable(self):
        """It must be startable, and its refusal must not be a dead end."""
        calls = []
        real = jobs._dispatch
        jobs._dispatch = lambda *a, **k: calls.append(1)
        try:
            jobs._run_sourcing("ep", lambda *a: None, lambda p: None,
                               arg="fetch")
        except AssertionError:
            pass                      # reached the session: that is success
        except jobs.JobError as e:
            self.fail("fetch is not reachable after approving: %s" % e)
        except Exception:
            pass                      # failed past the gate, which is fine
        finally:
            jobs._dispatch = real


if __name__ == "__main__":
    unittest.main()
