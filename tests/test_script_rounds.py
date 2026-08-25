# -*- coding: utf-8 -*-
"""The script's collaboration loop: interview, answer, draft, revise, lock.

The script stage was the one artifact Caleb could not argue with — the job
refused to run twice, so the first draft was the last word. This is the
gate that replaces that: the director asks, he answers, it drafts, he sends
direction, and only he can approve.

Three things are pinned hardest, because each is a way a loop stops being
collaborative:

  * a question with a default NEVER blocks — silence runs the default and
    the draft says so. Only a required, default-less question gates.
  * answers ACCUMULATE across rounds. Re-asking a settled question is how a
    loop becomes a chore.
  * approve is idempotent. The Story desk gave no post-approval feedback on
    2026-08-23, Caleb clicked six times, and six identical rounds landed.

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


def q(qid="Q1", **kw):
    d = {"id": qid, "ask": "which angle is the spine?",
         "options": [{"id": "a", "label": "the skin thread"},
                     {"id": "b", "label": "the pendulum"}],
         "default": "a"}
    d.update(kw)
    return d


def qdoc(stage="interview", questions=None):
    return {"slug": "ep", "stage": stage,
            "questions": questions if questions is not None else [q()]}


class Questions(unittest.TestCase):
    def test_a_sound_interview_validates(self):
        self.assertEqual(schemas.validate_script_questions(qdoc()), [])

    def test_the_interview_is_capped(self):
        many = [q("Q%d" % i) for i in range(schemas.MAX_INTERVIEW_Q + 1)]
        errs = schemas.validate_script_questions(qdoc(questions=many))
        self.assertTrue(any("the cap is" in e for e in errs), errs)

    def test_a_draft_round_is_capped_tighter(self):
        many = [q("Q%d" % i) for i in range(schemas.MAX_DRAFT_Q + 1)]
        errs = schemas.validate_script_questions(
            qdoc(stage="draft", questions=many))
        self.assertTrue(any("the cap is" in e for e in errs), errs)
        # the same set is legal as an interview
        self.assertEqual(
            schemas.validate_script_questions(qdoc(questions=many[:-1])), [])

    def test_a_default_must_name_a_real_option(self):
        errs = schemas.validate_script_questions(
            qdoc(questions=[q(default="zzz")]))
        self.assertTrue(any("names no option" in e for e in errs), errs)

    def test_a_required_free_text_question_with_no_default_is_refused(self):
        """There would be no way for it to not block, which defeats the
        point of every question carrying a way past it."""
        errs = schemas.validate_script_questions(
            qdoc(questions=[q(options=[], default=None, required=True)]))
        self.assertTrue(any("no way for this question to not block" in e
                            for e in errs), errs)

    def test_duplicate_question_ids_are_refused(self):
        errs = schemas.validate_script_questions(
            qdoc(questions=[q("Q1"), q("Q1")]))
        self.assertTrue(any("duplicate" in e for e in errs), errs)


class Gating(unittest.TestCase):
    """Which questions actually stop a draft."""

    def test_an_unanswered_question_with_a_default_does_not_block(self):
        self.assertEqual(schemas.blocking_questions(qdoc(), None), [])
        self.assertEqual(schemas.open_questions(qdoc(), None), ["Q1"])

    def test_a_required_default_less_question_blocks(self):
        d = qdoc(questions=[q(options=[], default=None, required=True)])
        self.assertEqual(schemas.blocking_questions(d, None), ["Q1"])

    def test_answering_it_unblocks(self):
        d = qdoc(questions=[q(options=[], default=None, required=True)])
        fb = {"rounds": [{"decision": "answers", "answers": {"Q1": "the skin"}}]}
        self.assertEqual(schemas.blocking_questions(d, fb), [])

    def test_a_blank_answer_is_not_an_answer(self):
        d = qdoc(questions=[q(options=[], default=None, required=True)])
        fb = {"rounds": [{"decision": "answers", "answers": {"Q1": "   "}}]}
        self.assertEqual(schemas.blocking_questions(d, fb), ["Q1"])

    def test_answers_accumulate_across_rounds(self):
        """Settled in round 0 stays settled in round 3."""
        d = qdoc(questions=[q("Q1"), q("Q2")])
        fb = {"rounds": [
            {"decision": "answers", "answers": {"Q1": "a"}},
            {"decision": "direction", "notes": "tighten chapter 4"},
            {"decision": "answers", "answers": {"Q2": "b"}}]}
        self.assertEqual(schemas.open_questions(d, fb), [])


class Loop(unittest.TestCase):
    """The whole thing end to end, through the engine's own functions."""

    def setUp(self):
        self.work = Path(tempfile.mkdtemp())
        (self.work / "analysis").mkdir(parents=True)
        self._wp, self._ad = editroom.work_path, editroom.analysis_dir
        editroom.work_path = lambda slug: self.work
        editroom.analysis_dir = lambda slug: self.work / "analysis"

    def tearDown(self):
        editroom.work_path, editroom.analysis_dir = self._wp, self._ad
        shutil.rmtree(self.work, ignore_errors=True)

    def put(self, name, doc):
        (self.work / name).write_text(json.dumps(doc))

    def script(self, **over):
        d = {"slug": "ep", "option_id": "S1", "round": 1, "locked": False,
             "target_minutes": 1.0,
             "chapters": [{"id": "CH1", "title": "c", "target_s": 60,
                           "sections": [{"id": "CH1.S1", "kind": "vo",
                                         "text": "a line", "est_s": 60.0,
                                         "rev": 1}]}]}
        d.update(over)
        return d

    # --- the interview arrives before any prose ---------------------------

    def test_the_desk_shows_questions_with_no_script_yet(self):
        """Round 0 is the whole point: he is interviewed BEFORE drafting."""
        self.put("script_questions.json", qdoc())
        st = editroom._script_state("ep")
        self.assertIsNone(st["script"])
        self.assertEqual(st["open"], ["Q1"])
        self.assertEqual(st["questions"]["stage"], "interview")

    def test_answering_records_a_round(self):
        self.put("script_questions.json", qdoc())
        fb = editroom._save_script_answers("ep", {"Q1": "a"}, "and keep it wry")
        self.assertEqual(fb["rounds"][-1]["decision"], "answers")
        self.assertEqual(fb["rounds"][-1]["answers"], {"Q1": "a"})
        self.assertEqual(editroom._script_state("ep")["open"], [])

    def test_answering_an_unknown_question_is_refused(self):
        self.put("script_questions.json", qdoc())
        with self.assertRaises(editroom.IngestError):
            editroom._save_script_answers("ep", {"Q9": "a"})

    def test_answering_before_an_interview_is_refused(self):
        with self.assertRaises(editroom.IngestError):
            editroom._save_script_answers("ep", {"Q1": "a"})

    def test_an_empty_send_is_refused(self):
        self.put("script_questions.json", qdoc())
        with self.assertRaises(editroom.IngestError):
            editroom._save_script_answers("ep", {"Q1": "  "}, "")

    def test_a_note_alone_is_a_legitimate_send(self):
        self.put("script_questions.json", qdoc())
        fb = editroom._save_script_answers("ep", {}, "skip them all, go")
        self.assertEqual(fb["rounds"][-1]["notes"], "skip them all, go")

    # --- direction and approval ------------------------------------------

    def test_direction_needs_notes(self):
        self.put("script.json", self.script())
        with self.assertRaises(editroom.IngestError):
            editroom._save_script_feedback("ep", "", "direction")

    def test_direction_records_a_round(self):
        self.put("script.json", self.script())
        fb = editroom._save_script_feedback("ep", "chapter 4 is thin", "direction")
        self.assertEqual(fb["rounds"][-1]["decision"], "direction")

    def test_the_loop_survives_a_script_existing(self):
        """Found by the P6 proof run: the state builder returned only the
        script once one existed, dropping the questions and the rounds at
        exactly the point they matter — every draft carries its own open
        questions, and the approve gate sits beside them."""
        self.put("script.json", self.script())
        self.put("script_questions.json", qdoc(stage="draft"))
        st = editroom._script_state("ep")
        self.assertIsNotNone(st["script"])
        self.assertEqual(st["open"], ["Q1"])
        self.assertIn("feedback", st)
        self.assertIn("answers", st)

    def test_approve_locks_the_script(self):
        self.put("script.json", self.script())
        editroom._save_script_feedback("ep", "", "approve")
        self.assertTrue(editroom._script_state("ep")["script"]["locked"])

    def test_approving_twice_is_one_round(self):
        """The 2026-08-23 six-clicks bug, refused by construction."""
        self.put("script.json", self.script())
        editroom._save_script_feedback("ep", "", "approve")
        for _ in range(5):
            fb = editroom._save_script_feedback("ep", "", "approve")
        self.assertEqual(len([r for r in fb["rounds"]
                              if r["decision"] == "approve"]), 1)

    def test_a_locked_script_refuses_direction(self):
        self.put("script.json", self.script())
        editroom._save_script_feedback("ep", "", "approve")
        with self.assertRaises(editroom.IngestError) as e:
            editroom._save_script_feedback("ep", "one more pass", "direction")
        self.assertIn("unlock", str(e.exception))

    def test_unlocking_reopens_it(self):
        self.put("script.json", self.script())
        editroom._save_script_feedback("ep", "", "approve")
        editroom._unlock_script("ep")
        self.assertFalse(editroom._script_state("ep")["script"]["locked"])
        editroom._save_script_feedback("ep", "one more pass", "direction")

    def test_approving_without_a_script_is_refused(self):
        with self.assertRaises(editroom.IngestError):
            editroom._save_script_feedback("ep", "", "approve")

    def test_an_unknown_decision_is_refused(self):
        self.put("script.json", self.script())
        with self.assertRaises(editroom.IngestError):
            editroom._save_script_feedback("ep", "x", "ship-it")

    # --- what the rail reads ---------------------------------------------

    def test_a_draft_is_not_locked_and_the_row_says_so(self):
        self.put("script.json", self.script())
        self.put("script_questions.json", qdoc(stage="draft"))
        (self.work / "analysis" / "catalog.json").write_text('{"files": []}')
        (self.work / "footage").mkdir(exist_ok=True)
        row = editroom._project_row("ep")
        self.assertFalse(row["script"]["locked"])
        self.assertEqual(row["script"]["open_questions"], 1)

    def test_and_after_approval_it_says_that(self):
        self.put("script.json", self.script())
        (self.work / "analysis" / "catalog.json").write_text('{"files": []}')
        (self.work / "footage").mkdir(exist_ok=True)
        editroom._save_script_feedback("ep", "", "approve")
        self.assertTrue(editroom._project_row("ep")["script"]["locked"])


if __name__ == "__main__":
    unittest.main()
