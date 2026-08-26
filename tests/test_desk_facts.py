# -*- coding: utf-8 -*-
"""The facts the desk headers state, and the health the machine reports.

2026-08-26. Every Studio desk used to open with a sentence explaining what
the desk was for; the Claude Design canvas states NUMBERS instead ("327
files · 758 GB · 4 sources"), and Caleb adopted that across every desk.

A fact the engine cannot source honestly is worse than no fact, so this
file pins the three things that had no source at all: which card a file
came from, what version the timeline is on, and whether Resolve is running.

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

from pipeline import editroom, facts, ingest  # noqa: E402

WORK = Path(__file__).resolve().parent.parent / "work"


class Sandboxed(unittest.TestCase):
    """Same guard as test_footage_state: patch BOTH work_paths, and prove
    on the way out that nothing landed in the real shelf."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.work = self.tmp / "ep"
        (self.work / "footage").mkdir(parents=True)
        self._wp = editroom.work_path, ingest.work_path, facts.work_path
        editroom.work_path = lambda slug: self.work
        ingest.work_path = lambda slug: self.work
        facts.work_path = lambda slug: self.work
        editroom._CATALOG_CACHE.clear()
        self._before = set(p.name for p in WORK.iterdir()) if WORK.is_dir() else set()

    def tearDown(self):
        editroom.work_path, ingest.work_path, facts.work_path = self._wp
        shutil.rmtree(self.tmp, ignore_errors=True)
        after = set(p.name for p in WORK.iterdir()) if WORK.is_dir() else set()
        self.assertEqual(after - self._before, set(),
                         "the test wrote into the REAL work dir")

    def _drop(self, *names, size=1024):
        for n in names:
            (self.work / "footage" / n).write_bytes(b"x" * size)


class Health(unittest.TestCase):
    def test_reports_disk_and_never_raises(self):
        h = facts.health()
        self.assertTrue(h["ok"])
        self.assertIn("resolve", h)
        self.assertIsNotNone(h["disk"])
        self.assertGreater(h["disk"]["total"], 0)
        self.assertGreaterEqual(h["disk"]["free"], 0)

    def test_a_failed_resolve_probe_is_unknown_not_false(self):
        """"We could not ask" and "it is not running" are different answers.

        The Studio offers to LAUNCH Resolve off this field. Reporting a
        broken probe as False would put a launch button in front of someone
        whose Resolve is already open.
        """
        import pipeline.resolve_api as ra
        orig = ra.resolve_running
        ra.resolve_running = lambda: (_ for _ in ()).throw(OSError("no pgrep"))
        try:
            self.assertIsNone(facts.health()["resolve"])
        finally:
            ra.resolve_running = orig

    def test_a_dead_disk_read_does_not_take_the_route_down(self):
        h = facts.health(Path("/nonexistent-volume-for-this-test"))
        self.assertTrue(h["ok"])
        self.assertIsNone(h["disk"])


class Sources(Sandboxed):
    def test_unlabelled_files_read_as_unsorted(self):
        self._drop("A001.mov", "A002.mov")
        st = editroom._footage_state("ep")
        self.assertEqual([f["source"] for f in st["files"]],
                         [facts.UNSORTED, facts.UNSORTED])
        self.assertEqual([r["name"] for r in st["sources"]], [facts.UNSORTED])

    def test_recorded_sources_group_with_counts_and_bytes(self):
        self._drop("A001.mov", "A002.mov", size=100)
        self._drop("B001.mov", size=300)
        facts.record_source("ep", ["A001.mov", "A002.mov"], "Card A")
        facts.record_source("ep", "B001.mov", "Card B")
        rows = {r["name"]: r for r in editroom._footage_state("ep")["sources"]}
        self.assertEqual(rows["Card A"]["files"], 2)
        self.assertEqual(rows["Card A"]["bytes"], 200)
        self.assertEqual(rows["Card B"]["files"], 1)
        self.assertEqual(rows["Card B"]["bytes"], 300)

    def test_unsorted_sorts_last_even_when_alphabetically_first(self):
        """It is a residue bucket, not a card — sorting it among the real
        ones implies it is one."""
        self._drop("a.mov", "z.mov")
        facts.record_source("ep", "z.mov", "Zoom H6")
        rows = [r["name"] for r in editroom._footage_state("ep")["sources"]]
        self.assertEqual(rows, ["Zoom H6", facts.UNSORTED])

    def test_a_blank_label_writes_nothing(self):
        """An absent entry already means unsorted; writing the word would
        make a guess look like a record."""
        self._drop("A001.mov")
        facts.record_source("ep", "A001.mov", "   ")
        self.assertEqual(facts.read_sources("ep"), {})

    def test_a_corrupt_sidecar_degrades_to_unsorted(self):
        self._drop("A001.mov")
        (self.work / "footage_sources.json").write_text("{ not json")
        self.assertEqual(facts.read_sources("ep"), {})
        st = editroom._footage_state("ep")
        self.assertEqual(st["files"][0]["source"], facts.UNSORTED)

    def test_forgetting_a_deleted_file_drops_its_card(self):
        self._drop("A001.mov")
        facts.record_source("ep", "A001.mov", "Card A")
        facts.forget_source("ep", ["A001.mov"])
        self.assertEqual(facts.read_sources("ep"), {})

    def test_skipped_files_are_counted_against_their_own_card(self):
        """The SOURCES panel's whole job on a bad card is naming WHICH
        card the unreadable files are on."""
        self._drop("A001.mov", "A002.mov")
        facts.record_source("ep", ["A001.mov", "A002.mov"], "Card C")
        rows = facts.group_sources(
            [{"name": "A001.mov", "size": 10}, {"name": "A002.mov", "size": 10}],
            facts.read_sources("ep"), skipped=["A002.mov"])
        self.assertEqual(rows[0]["skipped"], 1)


class LiveProgress(Sandboxed):
    def _write(self, **fields):
        (self.work / "ingest_progress.json").write_text(json.dumps(fields))

    def test_a_live_run_is_forwarded(self):
        import time
        self._write(stage="transcribe", done=118, total=190, pct=0.62,
                    eta_s=860, current="A008_C001.mov", ts=int(time.time()))
        pr = editroom._footage_state("ep")["progress"]
        self.assertEqual(pr["done"], 118)
        self.assertEqual(pr["eta_s"], 860)

    def test_a_finished_run_reports_nothing(self):
        import time
        self._write(stage="done", done=190, total=190, ts=int(time.time()))
        self.assertIsNone(editroom._footage_state("ep")["progress"])

    def test_a_stale_run_reports_nothing(self):
        """A progress file outliving the process that wrote it must not
        leave a bar creeping on the desk forever."""
        self._write(stage="transcribe", done=1, total=2,
                    ts=0)
        self.assertIsNone(editroom._footage_state("ep")["progress"])


class TimelineFacts(Sandboxed):
    def test_version_starts_at_zero_and_only_bumps_explicitly(self):
        self.assertEqual(facts.timeline_version("ep"), 0)
        self.assertEqual(facts.bump_timeline_version("ep"), 1)
        self.assertEqual(facts.bump_timeline_version("ep"), 2)
        self.assertEqual(facts.timeline_version("ep"), 2)

    def test_duration_prefers_the_map_over_a_sum_of_clips(self):
        """A sum silently loses whatever sits between clips."""
        f = facts.timeline_facts("ep", {"duration": 1361.4},
                                 [{"dur": 1.0}, {"dur": 2.0}])
        self.assertEqual(f["duration"], 1361.4)
        self.assertEqual(f["clips"], 2)

    def test_duration_falls_back_to_the_sum_when_the_map_has_none(self):
        f = facts.timeline_facts("ep", {}, [{"dur": 1.5}, {"dur": 2.0}])
        self.assertEqual(f["duration"], 3.5)

    def test_no_beats_and_no_map_reports_no_duration_rather_than_zero(self):
        """Zero is a claim about a cut; None is the absence of one."""
        f = facts.timeline_facts("ep", {}, [])
        self.assertIsNone(f["duration"])
        self.assertEqual(f["clips"], 0)


class Origin(Sandboxed):
    def test_flips_between_the_two_lanes(self):
        editroom._write_json(self.work / "story_brief.json",
                             {"origin": "footage", "delivery": "long",
                              "subject": "the sealed room"})
        out = editroom._set_project_origin("ep", "script")
        self.assertTrue(out["changed"])
        brief = json.loads((self.work / "story_brief.json").read_text())
        self.assertEqual(brief["origin"], "script")
        # and the "nothing else here can change" half of artboard 28
        self.assertEqual(brief["delivery"], "long")

    def test_setting_the_same_lane_is_a_no_op(self):
        editroom._write_json(self.work / "story_brief.json", {"origin": "script"})
        self.assertFalse(editroom._set_project_origin("ep", "script")["changed"])

    def test_a_BRAND_NEW_project_can_still_flip(self):
        """A subject gate briefly lived here, and broke the promise the
        create form makes three lines above the swap button.

        `_new_project` writes `subject: ""` and accepts `origin="script"`,
        so a gate here refused a state the app creates on purpose —
        nothing could be flipped until someone had already written a
        subject. `_save_story_brief` is the enforcement point: it asks
        when you SAVE a brief, which is when the subject is being written.
        """
        editroom._write_json(self.work / "story_brief.json",
                             {"origin": "footage", "subject": "", "location": ""})
        self.assertTrue(editroom._set_project_origin("ep", "script")["changed"])

    def test_a_project_born_in_the_script_lane_can_flip_back_and_forth(self):
        editroom._write_json(self.work / "story_brief.json", {"origin": "script"})
        self.assertTrue(editroom._set_project_origin("ep", "footage")["changed"])
        self.assertTrue(editroom._set_project_origin("ep", "script")["changed"])

    def test_a_corrupt_brief_is_a_400_not_a_500(self):
        (self.work / "story_brief.json").write_text("{ not json")
        with self.assertRaises(ingest.IngestError):
            editroom._set_project_origin("ep", "footage")

    def test_a_non_object_brief_is_a_400_not_a_500(self):
        (self.work / "story_brief.json").write_text("[]")
        with self.assertRaises(ingest.IngestError):
            editroom._set_project_origin("ep", "footage")

    def test_an_unknown_lane_is_refused(self):
        with self.assertRaises(ingest.IngestError):
            editroom._set_project_origin("ep", "documentary")


class IngestRetry(Sandboxed):
    def _catalog(self, skipped):
        d = self.work / "analysis"
        d.mkdir(parents=True, exist_ok=True)
        editroom._write_json(d / "catalog.json",
                             {"files": [], "skipped": list(skipped)})

    def test_nothing_skipped_is_not_an_error(self):
        self._catalog([])
        out = editroom._ingest_retry("ep")
        self.assertEqual(out["retried"], 0)
        self.assertIsNone(out["job"])

    def test_a_file_that_still_fails_is_named_back(self):
        self._catalog(["bad.mov"])
        self._drop("bad.mov")          # not real media; ffprobe refuses it
        out = editroom._ingest_retry("ep")
        self.assertEqual(out["still_failing"], ["bad.mov"])
        self.assertEqual(out["recovered"], [])
        self.assertIsNone(out["job"])
        # and the skip list is untouched, so the desk keeps offering retry
        cat = json.loads((self.work / "analysis" / "catalog.json").read_text())
        self.assertEqual(cat["skipped"], ["bad.mov"])

    def test_a_deleted_file_leaves_the_skip_list_WITHOUT_queueing_a_job(self):
        """It is not failing any more, it is gone — and leaving it on the
        list keeps offering a retry for a file that cannot be retried.

        But sweeping a name is not analysing a file. Counting it as a
        recovery queued a full ingest over nothing (review, 2026-08-26).
        """
        self._catalog(["gone.mov"])
        started = []
        import pipeline.jobs as jobs_mod
        orig = jobs_mod.start
        jobs_mod.start = lambda k, s, a=None: started.append((k, s)) or {"id": "j1"}
        try:
            out = editroom._ingest_retry("ep")
        finally:
            jobs_mod.start = orig
        self.assertEqual(out["swept"], ["gone.mov"])
        self.assertEqual(out["recovered"], [])
        cat = json.loads((self.work / "analysis" / "catalog.json").read_text())
        self.assertEqual(cat["skipped"], [], "the dead name is off the list")
        self.assertEqual(started, [], "nothing was queued over a deleted file")

    def test_an_unexpected_probe_error_does_not_sink_the_batch(self):
        """`probe_file` also raises FileNotFoundError when ffprobe is off
        PATH, and JSONDecodeError on an empty ffprobe. Either propagated as
        a 500, losing every result already gathered."""
        self._catalog(["a.mov", "b.mov"])
        self._drop("a.mov", "b.mov")
        import pipeline.ingest as ingest_mod
        orig = ingest_mod.probe_file
        ingest_mod.probe_file = lambda f: (_ for _ in ()).throw(
            FileNotFoundError(2, "No such file or directory: 'ffprobe'"))
        try:
            out = editroom._ingest_retry("ep")
        finally:
            ingest_mod.probe_file = orig
        self.assertEqual(sorted(out["still_failing"]), ["a.mov", "b.mov"])

    def test_no_catalog_at_all_is_refused_by_name(self):
        with self.assertRaises(ingest.IngestError):
            editroom._ingest_retry("ep")



class ConcurrentSources(Sandboxed):
    """`ThreadingHTTPServer` handles uploads in parallel and a browser
    folder-drop fires several at once.

    Before the lock (measured 2026-08-26): 12 concurrent calls kept 2
    labels and raised 9 times — and the raise was a FileNotFoundError from
    a SHARED tmp path, which `do_POST` turns into a 500 on an upload that
    had already stored its file.
    """

    def test_every_concurrent_label_survives(self):
        import threading
        n = 24
        start = threading.Barrier(n)
        errors = []

        def one(i):
            try:
                start.wait(timeout=5)
                facts.record_source("ep", "F%02d.mov" % i, "Card %d" % (i % 3))
            except Exception as e:      # noqa: BLE001 - the point is to see it
                errors.append(e)

        threads = [threading.Thread(target=one, args=(i,)) for i in range(n)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        self.assertEqual(errors, [], "a concurrent write raised")
        self.assertEqual(len(facts.read_sources("ep")), n,
                         "a concurrent write was lost")

    def test_a_label_cannot_carry_a_path(self):
        """The key is a filename and the label is user-supplied; neither
        has any business escaping the project."""
        facts.record_source("ep", "../../../etc/passwd", "Card A")
        self.assertEqual(list(facts.read_sources("ep")), ["passwd"])

    def test_no_tmp_file_is_left_behind(self):
        facts.record_source("ep", "A.mov", "Card A")
        leftovers = [p.name for p in self.work.iterdir() if p.name.endswith(".tmp")]
        self.assertEqual(leftovers, [])


class CorruptFilesDegrade(Sandboxed):
    """Every one of these promises in a docstring that it degrades. Each
    was a 500 through /api/state or /api/footage."""

    def test_a_non_dict_version_file_reads_as_zero(self):
        (self.work / "timeline_version.json").write_text("[1, 2, 3]")
        self.assertEqual(facts.timeline_version("ep"), 0)

    def test_a_bare_number_version_file_reads_as_zero(self):
        (self.work / "timeline_version.json").write_text("14")
        self.assertEqual(facts.timeline_version("ep"), 0)

    def test_a_non_dict_progress_file_reports_nothing(self):
        (self.work / "ingest_progress.json").write_text('"running"')
        self.assertIsNone(facts.live_progress("ep"))

    def test_a_non_dict_sidecar_reads_as_empty(self):
        (self.work / "footage_sources.json").write_text("[]")
        self.assertEqual(facts.read_sources("ep"), {})

if __name__ == "__main__":
    unittest.main()
