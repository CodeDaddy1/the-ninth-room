# -*- coding: utf-8 -*-
"""A finished agent job can be read back, and continued.

The job log only tees the assistant's prose: it says what the director
CONCLUDED and never what it read to get there. Capturing the session id
makes the work inspectable — the transcript on disk holds the tool calls,
and `claude --resume <id>` picks the conversation back up.

There is no web link to build here: a headless local session is not a
cloud session and has no claude.ai URL. The id addresses a file.

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

from pipeline import editroom, jobs  # noqa: E402


class Capture(unittest.TestCase):
    """The id reaches the job record without threading a jid through every
    _run_* signature."""

    def setUp(self):
        self.jid = "JTEST1"
        jobs._jobs[self.jid] = {"id": self.jid, "kind": "script", "slug": "x",
                                "state": "running"}
        jobs._order.append(self.jid)
        self._persist = jobs._persist
        jobs._persist = lambda: None

    def tearDown(self):
        jobs._persist = self._persist
        jobs._jobs.pop(self.jid, None)
        if self.jid in jobs._order:
            jobs._order.remove(self.jid)
        jobs._CURRENT.jid = None

    def test_the_running_job_gets_stamped(self):
        jobs._CURRENT.jid = self.jid
        jobs._note_session("abc-123")
        self.assertEqual(jobs._jobs[self.jid]["session_id"], "abc-123")

    def test_no_current_job_is_not_a_crash(self):
        """Dispatchers are also called from scripts and one-offs."""
        jobs._CURRENT.jid = None
        jobs._note_session("abc-123")   # must not raise

    def test_an_empty_id_is_ignored(self):
        jobs._CURRENT.jid = self.jid
        jobs._note_session("")
        self.assertNotIn("session_id", jobs._jobs[self.jid])

    def test_it_stamps_from_a_DIFFERENT_thread(self):
        """The one that matters, and the one the first version got wrong.

        _dispatch_json reads the session's output on a helper thread so a
        silent session cannot block the heartbeat. Thread-locals do not
        cross that boundary: the reader thread has its own empty _CURRENT,
        so looking up the job from inside it finds nothing and the id
        silently never lands. Caught live on a real job, not here — hence
        this test.
        """
        import threading
        jobs._CURRENT.jid = self.jid
        captured = _current_from_worker = jobs._current_jid()
        done = threading.Event()

        def reader():
            # exactly what the drain thread does: no _CURRENT of its own
            self.assertIsNone(jobs._current_jid())
            jobs._note_session("from-a-thread", captured)
            done.set()

        t = threading.Thread(target=reader)
        t.start()
        done.wait(timeout=5)
        t.join(timeout=5)
        self.assertEqual(_current_from_worker, self.jid)
        self.assertEqual(jobs._jobs[self.jid]["session_id"], "from-a-thread")

    def test_a_stale_jid_is_ignored(self):
        """A job reaped while its session was still talking."""
        jobs._note_session("abc", "JGONE")   # must not raise


class CreativeKindsCarryIt(unittest.TestCase):
    """Which buttons get a session door. Caleb chose the creative ones —
    the stages where an agent makes a judgement call worth auditing —
    and not the mechanical fetchers."""

    CREATIVE = ("interview", "script", "story", "editplan", "coverage",
                "graphics")

    def test_every_creative_kind_dispatches_through_the_capturing_path(self):
        import inspect
        src = inspect.getsource(jobs)
        for kind in self.CREATIVE:
            fn = jobs.KINDS[kind][1]
            body = inspect.getsource(fn)
            self.assertIn(
                "_dispatch_json", body,
                "%s must dispatch through _dispatch_json or its session is "
                "never captured and the desk has nothing to link to" % kind)
        self.assertTrue(src)


class Transcript(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self._dir = editroom._session_dir
        editroom._session_dir = lambda: self.tmp

    def tearDown(self):
        editroom._session_dir = self._dir
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write(self, sid, lines):
        (self.tmp / ("%s.jsonl" % sid)).write_text(
            "\n".join(json.dumps(x) for x in lines))

    def test_it_reads_prose_and_tool_calls(self):
        sid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        self.write(sid, [
            {"type": "queue-operation", "content": "write the script"},
            {"type": "assistant", "message": {"content": [
                {"type": "text", "text": "Reading the brief."},
                {"type": "tool_use", "name": "Read",
                 "input": {"file_path": "work/ep/research.json"}}]}},
        ])
        d = editroom._session_transcript(sid)
        self.assertEqual(d["prompt"], "write the script")
        self.assertEqual(d["steps"][0], {"kind": "said", "text": "Reading the brief."})
        self.assertEqual(d["steps"][1]["tool"], "Read")
        self.assertIn("research.json", d["steps"][1]["target"])

    def test_it_hands_back_the_resume_command(self):
        sid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        self.write(sid, [{"type": "assistant", "message": {"content": []}}])
        self.assertEqual(editroom._session_transcript(sid)["resume"],
                         "claude --resume %s" % sid)

    def test_tool_results_are_never_rendered(self):
        """They are the bulk — 773 lines carrying 78 MB in the largest
        transcript here — and none of it is a step."""
        sid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        self.write(sid, [
            {"type": "user", "message": {"content": [
                {"type": "tool_result", "content": "x" * 5000}]}},
            {"type": "assistant", "message": {"content": [
                {"type": "text", "text": "done"}]}},
        ])
        d = editroom._session_transcript(sid)
        self.assertEqual(len(d["steps"]), 1)

    def test_a_huge_line_is_skipped_before_it_is_parsed(self):
        sid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        (self.tmp / ("%s.jsonl" % sid)).write_text(
            json.dumps({"type": "assistant", "message": {"content": [
                {"type": "text", "text": "y" * (editroom.SESSION_LINE_CAP + 10)}]}})
            + "\n" + json.dumps({"type": "assistant", "message": {"content": [
                {"type": "text", "text": "small"}]}}))
        d = editroom._session_transcript(sid)
        self.assertEqual([s["text"] for s in d["steps"]], ["small"])

    def test_it_stops_at_the_cap(self):
        sid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        self.write(sid, [{"type": "assistant", "message": {"content": [
            {"type": "text", "text": "line %d" % i}]}}
            for i in range(editroom.SESSION_STEP_CAP + 50)])
        d = editroom._session_transcript(sid)
        self.assertEqual(len(d["steps"]), editroom.SESSION_STEP_CAP)
        self.assertTrue(d["truncated"])

    def test_a_path_is_not_a_session_id(self):
        for bad in ("../../etc/passwd", "a/b", "", "not a uuid!"):
            with self.assertRaises(editroom.IngestError):
                editroom._session_transcript(bad)

    def test_a_missing_transcript_says_so(self):
        with self.assertRaises(editroom.IngestError) as e:
            editroom._session_transcript("dddddddd-dddd-dddd-dddd-dddddddddddd")
        self.assertIn("no transcript", str(e.exception))


class Recheck(unittest.TestCase):
    """The way back after a resumed session writes outside the job."""

    def setUp(self):
        self.work = Path(tempfile.mkdtemp())
        (self.work / "analysis").mkdir()
        self._wp, self._ad = editroom.work_path, editroom.analysis_dir
        editroom.work_path = lambda slug: self.work
        editroom.analysis_dir = lambda slug: self.work / "analysis"

    def tearDown(self):
        editroom.work_path, editroom.analysis_dir = self._wp, self._ad
        shutil.rmtree(self.work, ignore_errors=True)

    def script(self, text="a line to say", **secover):
        sec = {"id": "CH1.S1", "kind": "vo", "text": text, "est_s": 60.0,
               "rev": 1, "visual": {"want": "the thing", "from": "library",
                                    "why": "illustrate — the thing"}}
        sec.update(secover)
        (self.work / "script.json").write_text(json.dumps(
            {"slug": "ep", "option_id": "S1", "target_minutes": 1.0,
             "chapters": [{"id": "CH1", "title": "c", "target_s": 60,
                           "sections": [sec]}]}))
        (self.work / "story_brief.json").write_text(json.dumps(
            {"target_minutes": 1, "chapters": 1, "vo_share": 1.0}))

    def test_a_clean_script_comes_back_clean(self):
        self.script()
        r = editroom._recheck_script("ep")
        self.assertTrue(r["ok"])
        self.assertEqual(r["errors"], [])
        self.assertEqual(r["notes"], [])

    def test_it_catches_what_a_resumed_session_broke(self):
        """The whole point: a resumed session edits with the job's
        authority and none of its validation."""
        self.script(text="This is insane, you won't believe it!")
        r = editroom._recheck_script("ep")
        self.assertFalse(r["ok"])
        self.assertTrue(any("banned" in n for n in r["notes"]), r["notes"])
        self.assertTrue(any("exclamation" in n for n in r["notes"]), r["notes"])

    def test_it_reports_rather_than_refusing(self):
        """By this point the words are already on disk — raising would
        leave Caleb with a broken script and no reading of it."""
        self.script(text="It opened in 1909.")   # a number, no source
        r = editroom._recheck_script("ep")       # must not raise
        self.assertFalse(r["ok"])

    def test_no_script_is_refused(self):
        with self.assertRaises(editroom.IngestError):
            editroom._recheck_script("ep")


if __name__ == "__main__":
    unittest.main()
