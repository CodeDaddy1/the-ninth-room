# -*- coding: utf-8 -*-
"""Sourcing proposes; Caleb approves; only then does anything download.

2026-08-24, as the format moved VO-led. Every VO second is a second with
nobody on camera to cut to, so a VO-led cut needs covering footage of
roughly its narration time — and the library is finite. Measured on
HMNS: 186 clips, 28.0 minutes, which is 1.87x a 60% VO cut and only
1.25x a 90% one, before the coverage editor rejects anything.

The gate is the point. The agent that judges what the library lacks does
not also decide what gets downloaded: a licence is a commitment.

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

from pipeline import schemas, jobs, editroom  # noqa: E402
from pipeline.ingest import IngestError  # noqa: E402


def script(vo_s=600.0, oncam_s=400.0):
    return {"chapters": [{"id": "CH1", "title": "c", "sections": [
        {"id": "CH1.S1", "kind": "vo", "text": "narrated", "est_s": vo_s},
        {"id": "CH1.S2", "kind": "oncamera", "text": "face", "est_s": oncam_s},
    ]}]}


def library(n=10, each=30.0):
    return {"clips": [{"id": "B%03d" % i, "duration": each} for i in range(n)]}


class Budget(unittest.TestCase):
    def test_it_counts_only_narration_against_the_library(self):
        b = schemas.coverage_budget(script(600, 400), library(10, 30))
        self.assertEqual(b["vo_seconds"], 600.0)
        self.assertEqual(b["library_seconds"], 300.0)
        self.assertEqual(b["shortfall_seconds"], 300.0)
        self.assertEqual(b["ratio"], 0.5)

    def test_a_comfortable_library_reports_no_shortfall(self):
        b = schemas.coverage_budget(script(300, 700), library(20, 30))
        self.assertEqual(b["shortfall_seconds"], 0.0)
        self.assertGreater(b["ratio"], 1.0)

    def test_clips_already_used_do_not_count_as_available(self):
        """One clip, one use — a library already spent is not in hand."""
        used = frozenset("B%03d" % i for i in range(8))
        b = schemas.coverage_budget(script(600, 400), library(10, 30), used)
        self.assertEqual(b["library_clips"], 2)
        self.assertEqual(b["library_seconds"], 60.0)

    def test_a_script_with_no_narration_has_no_budget(self):
        b = schemas.coverage_budget(script(0, 1000), library())
        self.assertEqual(b["vo_seconds"], 0.0)
        self.assertIsNone(b["ratio"])


class TheGate(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "analysis").mkdir(parents=True)
        self._wp_e, self._wp_j = editroom.work_path, jobs.work_path
        editroom.work_path = lambda slug: self.tmp
        jobs.work_path = lambda slug: self.tmp
        (self.tmp / "script.json").write_text(json.dumps(script()))
        (self.tmp / "analysis" / "broll.json").write_text(json.dumps(library()))
        (self.tmp / "asset_requests.json").write_text(json.dumps({"rounds": [
            {"ts": 111, "section_id": "CH1.S1", "line": "l", "why": "w",
             "candidates": [], "status": "proposed"}]}))

    def tearDown(self):
        editroom.work_path, jobs.work_path = self._wp_e, self._wp_j
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _rounds(self):
        return json.loads((self.tmp / "asset_requests.json").read_text())["rounds"]

    def test_approving_marks_only_that_round(self):
        out = editroom._asset_round_verdict("x", 111, "approved",
                                            log=lambda *a: None)
        self.assertEqual(out["approved"], 1)
        self.assertEqual(self._rounds()[0]["status"], "approved")

    def test_skipping_is_recorded_not_deleted(self):
        editroom._asset_round_verdict("x", 111, "skipped", log=lambda *a: None)
        self.assertEqual(self._rounds()[0]["status"], "skipped")
        self.assertEqual(len(self._rounds()), 1)

    def test_a_fetched_round_may_be_re_opened_but_not_undone(self):
        """Changed 2026-08-25: re-sourcing a gap is normal when the
        rules change (video first). Sliding it back to skipped is not —
        that would orphan the asset already on disk."""
        doc = {"rounds": [{"ts": 111, "status": "done"}]}
        (self.tmp / "asset_requests.json").write_text(json.dumps(doc))
        out = editroom._asset_round_verdict("x", 111, "approved",
                                            log=lambda *a: None)
        self.assertEqual(out["status"], "approved")
        (self.tmp / "asset_requests.json").write_text(json.dumps(doc))
        with self.assertRaises(IngestError):
            editroom._asset_round_verdict("x", 111, "skipped",
                                          log=lambda *a: None)

    def test_an_unknown_round_is_refused(self):
        with self.assertRaises(IngestError):
            editroom._asset_round_verdict("x", 999, "approved",
                                          log=lambda *a: None)

    def test_fetch_refuses_while_nothing_is_approved(self):
        """The gate, from the job's side: proposing does not authorise
        downloading."""
        with self.assertRaises(jobs.JobError) as e:
            jobs._run_sourcing("x", lambda *a: None, lambda p: None,
                               arg="fetch")
        self.assertIn("nothing approved", str(e.exception))

    def test_sourcing_refuses_without_a_script(self):
        (self.tmp / "script.json").unlink()
        with self.assertRaises(jobs.JobError) as e:
            jobs._run_sourcing("x", lambda *a: None, lambda p: None)
        self.assertIn("no script", str(e.exception))

    def test_the_budget_clause_quotes_real_arithmetic(self):
        clause = jobs._sourcing_budget_clause("x")
        self.assertIn("minutes of narration", clause)
        self.assertIn("ratio", clause)


class Wiring(unittest.TestCase):
    def test_sourcing_runs_on_the_session_lane(self):
        self.assertEqual(jobs.lane_of("sourcing"), "session")

    def test_the_script_job_does_NOT_hand_off_to_it(self):
        """It used to, and the trigger was wrong: the script job finishing
        means a DRAFT was written, not that the words are settled. Sourcing
        went out and priced pictures for lines about to be rewritten, and
        once the script lane began refusing an unapproved draft it was
        declined every time. The handoff moved to the APPROVAL
        (editroom._save_script_feedback, 2026-08-25)."""
        self.assertIsNone(jobs.CHAIN.get("script"))

    def test_and_sourcing_stops_at_the_gate(self):
        self.assertIsNone(jobs.CHAIN.get("sourcing"))


if __name__ == "__main__":
    unittest.main()


class ReopeningAFetchedRound(unittest.TestCase):
    """The rules changed (video first, 2026-08-25), so re-sourcing a gap
    that was already fetched is a normal thing to want — but a fetched
    round must not slide back to proposed or skipped, which would orphan
    the asset already on disk."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self._wp = editroom.work_path
        editroom.work_path = lambda slug: self.tmp
        (self.tmp / "asset_requests.json").write_text(json.dumps({"rounds": [
            {"ts": 1, "status": "done", "line": "a line"}]}))

    def tearDown(self):
        editroom.work_path = self._wp
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _status(self):
        return json.loads((self.tmp / "asset_requests.json").read_text())["rounds"][0]["status"]

    def test_approving_a_done_round_re_opens_it(self):
        out = editroom._asset_round_verdict("x", 1, "approved",
                                            log=lambda *a: None)
        self.assertEqual(out["status"], "approved")
        self.assertEqual(self._status(), "approved")

    def test_it_cannot_slide_back_to_skipped(self):
        with self.assertRaises(IngestError):
            editroom._asset_round_verdict("x", 1, "skipped",
                                          log=lambda *a: None)
        self.assertEqual(self._status(), "done")

    def test_nor_back_to_proposed(self):
        with self.assertRaises(IngestError):
            editroom._asset_round_verdict("x", 1, "proposed",
                                          log=lambda *a: None)
        self.assertEqual(self._status(), "done")


class RevisionsRetireStaleProposals(unittest.TestCase):
    """A proposal offers to BUY something. A revision can decide we are not
    buying it after all — and the proposal made against the old line stays
    at `proposed`, indistinguishable from a live one.

    Observed on the-pendulum-that-stopped (2026-08-25): CH2.S7 and CH2.S8
    were proposed as archival, Caleb answered "redraw those two in the
    overlay kit", and both proposals sat there. Approving them would have
    spent money on the exact thing he decided not to buy.
    """

    def script(self, **frm):
        return {"chapters": [{"id": "CH1", "sections": [
            {"id": sid, "kind": "vo", "visual": {"want": "x", "why": "y",
                                                 "from": f}}
            for sid, f in frm.items()]}]}

    def reqs(self, *rows):
        return {"rounds": [dict(r) for r in rows]}

    def test_a_source_the_kit_now_draws_is_retired(self):
        s = self.script(CH2_S7="graphic")
        s["chapters"][0]["sections"][0]["id"] = "CH2.S7"
        r = self.reqs({"section_id": "CH2.S7", "kind": "source",
                       "status": "proposed"})
        self.assertEqual(schemas.superseded_requests(s, r), [0])

    def test_a_source_still_wanted_is_left_alone(self):
        s = self.script(x="archival")
        s["chapters"][0]["sections"][0]["id"] = "CH2.S3"
        r = self.reqs({"section_id": "CH2.S3", "kind": "source",
                       "status": "proposed"})
        self.assertEqual(schemas.superseded_requests(s, r), [])

    def test_a_requirement_is_never_retired_this_way(self):
        """It names work still owed whatever the section now says."""
        s = self.script(x="graphic")
        s["chapters"][0]["sections"][0]["id"] = "CH1.S4"
        r = self.reqs({"section_id": "CH1.S4", "kind": "requirement",
                       "status": "proposed"})
        self.assertEqual(schemas.superseded_requests(s, r), [])

    def test_a_section_that_no_longer_exists_is_retired(self):
        r = self.reqs({"section_id": "CH9.S9", "kind": "source",
                       "status": "proposed"})
        self.assertEqual(schemas.superseded_requests(self.script(), r), [0])

    def test_already_decided_rounds_are_untouched(self):
        """Approved and done rounds are history, not open offers."""
        s = self.script()
        for st in ("approved", "done", "skipped", "superseded"):
            r = self.reqs({"section_id": "CH9.S9", "kind": "source",
                           "status": st})
            self.assertEqual(schemas.superseded_requests(s, r), [], st)

    def test_shoot_and_library_also_mean_not_buying(self):
        for f in ("shoot", "library"):
            s = self.script(x=f)
            s["chapters"][0]["sections"][0]["id"] = "CH1.S1"
            r = self.reqs({"section_id": "CH1.S1", "kind": "source",
                           "status": "proposed"})
            self.assertEqual(schemas.superseded_requests(s, r), [0], f)


class ProposalsAreLookedAtNotGuessed(unittest.TestCase):
    """A candidate used to be a SEARCH TERM. You cannot look at a search
    term, so approving one approved a guess — and its licence line was a
    prediction about what the search might turn up, not a fact about a
    file. Caleb asked to see the picture first (2026-08-25).

    The preview urls are REMOTE and rendered by the browser, so nothing
    reaches disk before approval — the gate the propose/fetch split exists
    to protect is untouched.
    """

    def cand(self, **over):
        c = {"query": "Foucault portrait 1850s", "source": "wikimedia",
             "kind": "image", "page": "https://commons.example/File:x",
             "preview": "https://commons.example/thumb/x.jpg",
             "license": "PD-US, stated on the file page"}
        c.update(over)
        return c

    def round_(self, *cands, **over):
        r = {"kind": "source", "section_id": "CH2.S3",
             "candidates": [dict(c) for c in cands]}
        r.update(over)
        return r

    def test_a_resolved_candidate_passes(self):
        self.assertEqual(schemas.validate_candidates(
            self.round_(self.cand())), [])

    def test_a_bare_search_term_is_refused(self):
        errs = schemas.validate_candidates(self.round_(
            {"query": "x", "source": "wikimedia", "license": "PD", "note": "n"}))
        self.assertTrue(any("nothing to preview" in e for e in errs), errs)

    def test_no_page_means_the_licence_is_unverifiable(self):
        errs = schemas.validate_candidates(self.round_(self.cand(page="")))
        self.assertTrue(any("no page url" in e for e in errs), errs)

    def test_a_predicted_licence_is_still_required_to_be_stated(self):
        errs = schemas.validate_candidates(self.round_(self.cand(license="")))
        self.assertTrue(any("read it off the page" in e for e in errs), errs)

    def test_a_video_candidate_needs_something_playable(self):
        errs = schemas.validate_candidates(self.round_(
            self.cand(kind="video")))
        self.assertTrue(any("playable url" in e for e in errs), errs)
        self.assertEqual(schemas.validate_candidates(self.round_(
            self.cand(kind="video", video="https://ex/v.mp4"))), [])

    def test_a_requirement_offers_nothing_to_look_at(self):
        """It names work Caleb or the kit must do — there is no picture."""
        self.assertEqual(schemas.validate_candidates(
            {"kind": "requirement", "section_id": "CH1.S4"}), [])

    def test_a_source_with_no_candidates_at_all_is_refused(self):
        errs = schemas.validate_candidates(self.round_())
        self.assertTrue(any("no candidates" in e for e in errs), errs)

    def test_previewable_reads_either_url(self):
        self.assertTrue(schemas.candidate_previewable({"preview": "u"}))
        self.assertTrue(schemas.candidate_previewable({"video": "u"}))
        self.assertFalse(schemas.candidate_previewable({"query": "x"}))
        self.assertFalse(schemas.candidate_previewable(None))


class RoundsAreAddressedUniquely(unittest.TestCase):
    """`ts` was the round's identity, and it is not unique — the agent
    writes several in the same second. CH2.S3 and CH2.S4 both landed on
    1787692563 (2026-08-25).

    Two failures came out of that. The desk keyed cards by ts, so React
    saw duplicates and stopped re-rendering — which read as "clicking use
    this does nothing". And far worse, the verdict looked rounds up by ts
    and took the FIRST match, so approving a picture on one line could
    mark a DIFFERENT line approved, carrying a candidate index from a list
    it never belonged to.
    """

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self._wp = editroom.work_path
        editroom.work_path = lambda slug: self.tmp

    def tearDown(self):
        editroom.work_path = self._wp
        shutil.rmtree(self.tmp, ignore_errors=True)

    def put(self, *rounds):
        (self.tmp / "asset_requests.json").write_text(
            json.dumps({"rounds": [dict(r) for r in rounds]}))

    def collide(self):
        self.put({"ts": 100, "section_id": "CH2.S3", "kind": "source",
                  "status": "proposed", "candidates": [{"query": "a"}, {"query": "b"}]},
                 {"ts": 100, "section_id": "CH2.S4", "kind": "source",
                  "status": "proposed", "candidates": [{"query": "c"}]})

    def test_colliding_rounds_get_distinct_ids(self):
        self.collide()
        ids = [r["id"] for r in editroom._asset_rounds("ep")]
        self.assertEqual(len(ids), len(set(ids)))

    def test_ids_are_stable_across_reads(self):
        self.collide()
        first = [r["id"] for r in editroom._asset_rounds("ep")]
        self.assertEqual([r["id"] for r in editroom._asset_rounds("ep")], first)

    def test_a_verdict_lands_on_the_round_it_names(self):
        """The corruption: approving CH2.S4 used to mark CH2.S3."""
        self.collide()
        rounds = editroom._asset_rounds("ep")
        target = next(r for r in rounds if r["section_id"] == "CH2.S4")
        editroom._asset_round_verdict("ep", target["id"], "approved",
                                      log=lambda *a: None)
        by = {r["section_id"]: r for r in editroom._asset_rounds("ep")}
        self.assertEqual(by["CH2.S4"]["status"], "approved")
        self.assertEqual(by["CH2.S3"]["status"], "proposed")

    def test_an_ambiguous_ts_is_refused_rather_than_guessed(self):
        self.collide()
        with self.assertRaises(editroom.IngestError) as cm:
            editroom._asset_round_verdict("ep", 100, "approved",
                                          log=lambda *a: None)
        self.assertIn("names 2 proposals", str(cm.exception))

    def test_an_unambiguous_ts_still_works(self):
        """Anything written before ids existed stays addressable."""
        self.put({"ts": 7, "section_id": "CH1.S1", "kind": "source",
                  "status": "proposed", "candidates": [{"query": "a"}]})
        editroom._asset_round_verdict("ep", 7, "skipped", log=lambda *a: None)
        self.assertEqual(editroom._asset_rounds("ep")[0]["status"], "skipped")

    def test_the_chosen_candidate_must_exist_on_that_round(self):
        self.collide()
        rounds = editroom._asset_rounds("ep")
        target = next(r for r in rounds if r["section_id"] == "CH2.S4")
        with self.assertRaises(editroom.IngestError):
            # CH2.S4 has ONE candidate; index 1 belongs to CH2.S3's list
            editroom._asset_round_verdict("ep", target["id"], "approved", 1,
                                          log=lambda *a: None)
