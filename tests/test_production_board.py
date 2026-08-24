# -*- coding: utf-8 -*-
"""The production board: one fold, one writer per class, honest brakes.

P1 of the team plan (2026-08-24). The rules Caleb's plan review made
mechanical, pinned:

- one writer per event class — a lead-class event claiming the engine
  writer is refused by validation, not prevented by a lock;
- the stall brakes fire on STRUCTURE (stable line ids), never on note
  strings an LLM rephrases: the stuck 2,2 line fires; the CONVERGING
  1→3 line does not; min+sum non-increasing across 3 rounds fires and
  an improving vector never does;
- scores of 3 and below must quote the artifact line that earned them;
- stale claims reap; the anchoring leak check catches an inlined
  scorecard.

Run: /usr/bin/python3 -m unittest discover -s tests -t .
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline import schemas  # noqa: E402


def ev(etype, by, **kw):
    e = {"type": etype, "by": by, "ts": kw.pop("ts", 1000)}
    e.update(kw)
    return e


def rounds_to_card(*score_rounds):
    """Build a card via the real fold: each dict is one round's scores."""
    events = [ev("assigned", "lead", task_id="T1", craft="coverage",
                 title="cover the cut")]
    for i, scores in enumerate(score_rounds):
        events.append(ev("claimed", "engine", task_id="T1", owner="cov",
                         ts=1000 + i))
        events.append(ev("artifact_submitted", "engine", task_id="T1",
                         artifact="plan.json", ts=1001 + i))
        for line, sc in scores.items():
            events.append(ev("score", "lead", task_id="T1", line_id=line,
                             score=sc, quoted_artifact_line="the line",
                             ts=1002 + i))
    return schemas.fold_production(events)["tasks"]["T1"]


class WriterClasses(unittest.TestCase):
    def test_a_lead_event_from_the_engine_writer_is_refused(self):
        errs = schemas.validate_production({"events": [
            ev("score", "engine", task_id="T1", line_id="R1", score=5)]})
        self.assertTrue(any("lead-written" in e for e in errs))

    def test_an_engine_event_from_the_lead_is_refused(self):
        errs = schemas.validate_production({"events": [
            ev("cost", "lead", task_id="T1")]})
        self.assertTrue(any("engine-written" in e for e in errs))

    def test_a_low_score_must_quote_its_line(self):
        errs = schemas.validate_production({"events": [
            ev("score", "lead", task_id="T1", line_id="R2", score=2)]})
        self.assertTrue(any("must quote" in e for e in errs))

    def test_a_clean_log_validates(self):
        errs = schemas.validate_production({"events": [
            ev("assigned", "lead", task_id="T1", craft="coverage",
               title="t"),
            ev("claimed", "engine", task_id="T1", owner="cov"),
            ev("score", "lead", task_id="T1", line_id="R1", score=5),
            ev("caleb_note", "caleb", task_id="T1", text="looser"),
        ]})
        self.assertEqual(errs, [])


class StallBrakes(unittest.TestCase):
    def test_the_stuck_line_fires(self):
        card = rounds_to_card({"R1": 5, "R3": 2}, {"R1": 5, "R3": 2})
        self.assertIn("R3", schemas.stalled(card) or "")

    def test_the_converging_line_does_not_fire(self):
        """Caleb's rev-3 catch verbatim: R3 going 1 then 3 against a bar
        of 4 is a teammate doing exactly what you want."""
        card = rounds_to_card({"R1": 5, "R3": 1}, {"R1": 5, "R3": 3})
        self.assertIsNone(schemas.stalled(card))

    def test_the_flat_vector_fires_at_three(self):
        card = rounds_to_card({"R1": 4, "R2": 3},
                              {"R1": 4, "R2": 3},
                              {"R1": 3, "R2": 4})  # sum flat, min down
        self.assertIn("vector", schemas.stalled(card) or "")

    def test_an_improving_vector_never_fires(self):
        card = rounds_to_card({"R1": 2, "R2": 2},
                              {"R1": 3, "R2": 3},
                              {"R1": 4, "R2": 4})
        self.assertIsNone(schemas.stalled(card))

    def test_two_rounds_of_nothing_is_no_stall(self):
        card = rounds_to_card({"R1": 5}, {"R1": 5})
        self.assertIsNone(schemas.stalled(card))


class FoldAndReap(unittest.TestCase):
    def test_the_lifecycle_folds(self):
        card = rounds_to_card({"R1": 5})
        self.assertEqual(card["status"], "in_review")
        self.assertEqual(card["rounds"], 1)
        self.assertEqual(card["score_history"], [{"R1": 5}])

    def test_costs_accumulate(self):
        events = [ev("assigned", "lead", task_id="T1", craft="c", title="t"),
                  ev("cost", "engine", task_id="T1", tokens=1000, usd=0.5,
                     ms=2000),
                  ev("cost", "engine", task_id="T1", tokens=500, usd=0.2,
                     ms=1000)]
        card = schemas.fold_production(events)["tasks"]["T1"]
        self.assertEqual(card["cost"]["sessions"], 2)
        self.assertEqual(card["cost"]["tokens"], 1500)
        self.assertAlmostEqual(card["cost"]["usd"], 0.7)

    def test_a_stale_claim_reaps_and_a_fresh_one_does_not(self):
        events = [
            ev("assigned", "lead", task_id="T1", craft="c", title="t"),
            ev("claimed", "engine", task_id="T1", owner="x", ts=1000),
            ev("assigned", "lead", task_id="T2", craft="c", title="t"),
            ev("claimed", "engine", task_id="T2", owner="y", ts=99000),
        ]
        cards = schemas.fold_production(events)
        self.assertEqual(schemas.stale_claims(cards, now=100000), ["T1"])

    def test_a_reclaim_reopens(self):
        events = [ev("assigned", "lead", task_id="T1", craft="c", title="t"),
                  ev("claimed", "engine", task_id="T1", owner="x"),
                  ev("reclaimed", "engine", task_id="T1")]
        card = schemas.fold_production(events)["tasks"]["T1"]
        self.assertEqual(card["status"], "open")
        self.assertIsNone(card["owner"])


class AnchoringLeak(unittest.TestCase):
    def test_an_inlined_scorecard_is_caught(self):
        self.assertTrue(schemas.artifact_has_self_assessment(
            "the plan...\n## Self-critique\nR1: 4 because"))

    def test_a_clean_artifact_passes(self):
        self.assertFalse(schemas.artifact_has_self_assessment(
            '{"beats": [{"id": "BT01", "broll": []}]}'))


if __name__ == "__main__":
    unittest.main()
