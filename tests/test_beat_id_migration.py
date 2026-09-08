# -*- coding: utf-8 -*-
"""Renaming a project's beats, without unbinding anything from them.

`beat_identity` can derive a stable id from the shot a beat shows. That
is half the job. The other half is that eight artifacts key on the old
spelling, and if they do not move in the same breath the rename silently
unbinds Caleb's review history, his cards, his cue sheet and his conform
queue from the beats they describe — which is the exact failure the
anchor scheme exists to end, reproduced one level up.

Two of these tests exist because the sandbox run on a copy of hmns found
real bugs that fixture tests had not:

  * `derive_ids` renamed `beats[].id` and nothing else, so the plan's own
    `fun[].beat_id` references pointed at ids that no longer existed.
  * `conform_status.json` — the ledger the Studio reads to show what the
    last push to Resolve did — was not in the artifact list at all.

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

from pipeline import (beat_identity as bi, ingest, migrate_ids as mi,  # noqa
                      plan_history as ph)


def _plan():
    """Two beats on one take (so occurrence is exercised) and one on
    another, plus the plan's own reference into `fun`."""
    return {
        "slug": "ep", "format": "youtube_long", "orientation": "landscape",
        "theme": {"problem": "p", "promise": "q", "payoff": "r"},
        "beats": [
            {"id": "BT01", "purpose": "hook", "take_id": "T04",
             "trim": {"s": 0.0, "e": 5.0}},
            {"id": "BT07", "purpose": "build", "take_id": "T04",
             "trim": {"s": 6.0, "e": 9.0}},
            {"id": "BT09", "purpose": "payoff", "take_id": "T12",
             "trim": {"s": 0.0, "e": 4.0}},
        ],
        "fun": [{"beat_id": "BT07", "at": 1.0, "kind": "vote", "note": "n"}],
    }


class _ProjectOnDisk(object):
    """One project's artifacts in a temp dir, with `work_path` pointed at
    it. A mixin rather than a base TestCase so the second-hop class can
    reuse the fixture without re-running every test in the first."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "analysis").mkdir(parents=True)
        (self.tmp / "captions").mkdir()
        (self.tmp / "proxies").mkdir()
        self._wp, self._ad = ingest.work_path, ingest.analysis_dir
        ingest.work_path = lambda slug: self.tmp
        ingest.analysis_dir = lambda slug: self.tmp / "analysis"
        for mod in (mi, ph):
            mod.work_path = ingest.work_path
        mi.analysis_dir = ingest.analysis_dir
        self.write("edit_plan.json", _plan())
        # 4 review entries against 3 beats: BT99 is a ghost with a note
        self.write("review.json", {
            "BT01": {"status": "approved", "note": "keep"},
            "BT07": {"status": "approved", "note": "the vote lands"},
            "BT09": {"status": "flagged", "note": "fix the tail"},
            "BT99": {"status": "approved", "note": "a beat that is gone"}})
        self.write("captions.json", {"slug": "ep", "beats": [
            {"beat_id": "BT01", "text": "one"},
            {"beat_id": "BT07", "text": "two"}]})
        self.write("graphics_plan.json", {"slug": "ep", "cards": [
            {"id": "CARD01", "beat_id": "BT09", "at": 1.0, "duration": 3.0}]})
        self.write("analysis/timeline_map.json", {"slug": "ep", "beats": [
            {"id": "BT01"}, {"id": "BT07"}, {"id": "BT09"}]})
        self.write("sfx_cues.json", {"slug": "ep", "cues": [
            {"beat": "BT01", "sound": "whoosh"}]})
        self.write("trash.json", {"entries": [{"beat_id": "BT07",
                                               "kind": "broll"}], "seq": 1})
        self.write("pending_conform.json", {"ops": [{"op": "x",
                                                     "beat_id": "BT09"}]})
        self.write("conform_status.json", {"state": "done", "ops": [
            {"op": "card_place", "beat_id": "BT09", "result": "ok"},
            {"op": "card_place", "beat_id": "", "result": "skipped"}]})
        for bid in ("BT01", "BT07"):
            (self.tmp / "captions" / ("%s.mov" % bid)).write_bytes(b"prores")
        self.write("captions/.bake_hashes.json", {"BT01": "aaa", "BT07": "bbb"})
        for bid in ("BT01", "BT07", "BT09"):
            (self.tmp / "proxies" / ("%s.deadbeef.mp4" % bid)).write_bytes(b"m")

    def tearDown(self):
        ingest.work_path, ingest.analysis_dir = self._wp, self._ad
        for mod in (mi, ph):
            mod.work_path = self._wp
        mi.analysis_dir = self._ad
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write(self, rel, doc):
        p = self.tmp / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(doc, indent=2))

    def read(self, rel):
        return json.loads((self.tmp / rel).read_text())

    def _tree(self):
        """Content hash of everything, for the dry-run inertness proof."""
        import hashlib
        return {str(p.relative_to(self.tmp)):
                hashlib.sha1(p.read_bytes()).hexdigest()
                for p in sorted(self.tmp.rglob("*")) if p.is_file()}


class MigrateBeatIds(_ProjectOnDisk, unittest.TestCase):

    # ---- the dry run -------------------------------------------------

    def test_the_survey_changes_nothing_at_all(self):
        """THE DEFAULT IS SAFE. Run it three times and the tree is
        byte-identical, because `--apply` is a second deliberate run
        made after reading what the first one printed."""
        before = self._tree()
        for _ in range(3):
            mi.survey("ep")
        self.assertEqual(self._tree(), before)

    def test_the_survey_counts_what_apply_would_rewrite(self):
        s = mi.survey("ep")
        rows = {r["artifact"]: r for r in s["artifacts"]}
        self.assertEqual(rows["review.json"]["rows"], 4)
        self.assertEqual(rows["review.json"]["remapped"], 3)
        self.assertEqual(rows["review.json"]["stranded"], 1)
        self.assertEqual(rows["conform_status.json"]["remapped"], 1)

    # ---- identity ----------------------------------------------------

    def test_the_ids_come_from_the_shot_and_occurrence_is_kept(self):
        mi.apply("ep", log=lambda *a: None)
        ids = [b["id"] for b in self.read("edit_plan.json")["beats"]]
        self.assertEqual(ids, ["shot-T04", "shot-T04-2", "shot-T12"])

    def test_the_migrated_plan_passes_its_own_invariant(self):
        mi.apply("ep", log=lambda *a: None)
        self.assertEqual(bi.id_errors(self.read("edit_plan.json")), [])

    def test_the_map_is_written_and_is_a_bijection(self):
        mi.apply("ep", log=lambda *a: None)
        m = self.read(mi.MAP_FILE)["map"]
        self.assertEqual(m, {"BT01": "shot-T04", "BT07": "shot-T04-2",
                             "BT09": "shot-T12"})

    # ---- the two the sandbox found -----------------------------------

    def test_the_plans_own_references_move_with_it(self):
        """`fun[].beat_id` pointed at a beat that no longer existed. The
        rename must not strand the plan's references to itself."""
        mi.apply("ep", log=lambda *a: None)
        plan = self.read("edit_plan.json")
        ids = {b["id"] for b in plan["beats"]}
        self.assertEqual(plan["fun"][0]["beat_id"], "shot-T04-2")
        self.assertIn(plan["fun"][0]["beat_id"], ids)

    def test_the_conform_ledger_moves_too(self):
        """The Studio reads it to show what the last push to Resolve did,
        per beat. An op naming a dead beat is a lie on that surface."""
        mi.apply("ep", log=lambda *a: None)
        ops = self.read("conform_status.json")["ops"]
        self.assertEqual(ops[0]["beat_id"], "shot-T12")
        self.assertEqual(ops[1]["beat_id"], "", "an empty id is left alone")

    def test_a_rename_never_edits_prose(self):
        """The reference fields are LISTED, not discovered by walking. A
        blind walk would rewrite a note that happens to say BT07."""
        self.write("edit_plan.json", dict(_plan(), notes="see BT07 for the gag"))
        mi.apply("ep", log=lambda *a: None)
        self.assertEqual(self.read("edit_plan.json")["notes"],
                         "see BT07 for the gag")

    # ---- the artifacts -----------------------------------------------

    def test_every_keyed_artifact_follows(self):
        mi.apply("ep", log=lambda *a: None)
        self.assertEqual([b["beat_id"] for b in self.read("captions.json")["beats"]],
                         ["shot-T04", "shot-T04-2"])
        self.assertEqual(self.read("graphics_plan.json")["cards"][0]["beat_id"], "shot-T12")
        self.assertEqual([b["id"] for b in self.read("analysis/timeline_map.json")["beats"]],
                         ["shot-T04", "shot-T04-2", "shot-T12"])
        self.assertEqual(self.read("sfx_cues.json")["cues"][0]["beat"], "shot-T04")
        self.assertEqual(self.read("trash.json")["entries"][0]["beat_id"], "shot-T04-2")
        self.assertEqual(self.read("pending_conform.json")["ops"][0]["beat_id"], "shot-T12")

    def test_a_ghost_verdict_is_archived_with_its_note_not_dropped(self):
        """hmns carries fourteen of these and they hold Caleb's words."""
        mi.apply("ep", log=lambda *a: None)
        rv = self.read("review.json")
        ar = self.read(mi.ARCHIVE_FILE)["entries"]
        self.assertEqual(sorted(rv), ["shot-T04", "shot-T04-2", "shot-T12"])
        self.assertEqual([e["id"] for e in ar], ["BT99"])
        self.assertEqual(ar[0]["entry"]["note"], "a beat that is gone")

    def test_carried_verdicts_are_byte_identical(self):
        mi.apply("ep", log=lambda *a: None)
        self.assertEqual(self.read("review.json")["shot-T04-2"],
                         {"status": "approved", "note": "the vote lands"})

    # ---- the media -----------------------------------------------------

    def test_captions_are_hardlinked_and_the_old_names_survive(self):
        """hmns's shipped Resolve timeline holds absolute paths to the old
        names; moving one takes that timeline offline."""
        mi.apply("ep", log=lambda *a: None)
        caps = self.tmp / "captions"
        for old, new in (("BT01", "shot-T04"), ("BT07", "shot-T04-2")):
            self.assertTrue((caps / ("%s.mov" % old)).exists(), old)
            self.assertTrue((caps / ("%s.mov" % new)).exists(), new)
            self.assertEqual(os.stat(caps / ("%s.mov" % old)).st_ino,
                             os.stat(caps / ("%s.mov" % new)).st_ino)

    def test_the_bake_cache_is_rekeyed_so_the_prores_survives(self):
        """`_caption_key` is content-only, so the same caption under a new
        key is still a cache HIT — 9.3 GB on hmns."""
        mi.apply("ep", log=lambda *a: None)
        self.assertEqual(self.read("captions/.bake_hashes.json"),
                         {"shot-T04": "aaa", "shot-T04-2": "bbb"})

    def test_proxies_are_deleted_because_their_name_holds_a_spec_hash(self):
        mi.apply("ep", log=lambda *a: None)
        self.assertEqual(bi.beat_proxies(self.tmp / "proxies"), [])

    # ---- the way back ---------------------------------------------------

    def test_the_previous_state_is_backed_up_verbatim(self):
        mi.apply("ep", log=lambda *a: None)
        b = self.tmp / mi.BACKUP_DIRNAME          # the first hop's
        self.assertEqual(json.loads((b / "edit_plan.json").read_text()),
                         _plan())
        self.assertIn("BT99", json.loads((b / "review.json").read_text()))

    def test_the_cut_is_archived_into_plan_history(self):
        mi.apply("ep", log=lambda *a: None)
        rows = ph.versions("ep")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["reason"], "migration")

    def test_a_second_apply_refuses_instead_of_renaming_again(self):
        mi.apply("ep", log=lambda *a: None)
        with self.assertRaises(mi.MigrationError) as cm:
            mi.survey("ep")
        self.assertIn("already on", str(cm.exception))

    def test_a_project_with_no_cut_is_refused_by_name(self):
        (self.tmp / "edit_plan.json").unlink()
        with self.assertRaises(mi.MigrationError):
            mi.survey("ep")


class ASecondHop(_ProjectOnDisk, unittest.TestCase):
    """hmns was renamed TWICE on 2026-09-08: `BT01` to `B-T362` in the
    morning, then to `shot-T362` in the afternoon, because the anchor
    spelling is one hyphen away from the name it replaced and Caleb
    could not find his own clip.

    The tool was written for one hop, and every one of its four
    "careful" behaviours inverted on the second: the backup directory
    refused to overwrite and therefore saved NOTHING, the id map was
    replaced so `BT01` became unresolvable, captions would have grown a
    third name set on the same 80 inodes, and the review archive was
    written whole over the fourteen ghosts it had just preserved. Each
    one logged success.

    Hop one is run with the anchor-v1 constants patched in, because that
    is literally what shipped and what hmns is sitting on right now.
    """

    def _hop_one(self):
        import re
        keep = (bi.ID_SCHEME, bi.ID_RE, bi.format_id)
        bi.ID_SCHEME = "anchor-v1"
        bi.ID_RE = re.compile(r"^B-(T\d+|B\d+)(?:-([1-9]\d*))?$")
        bi.format_id = lambda a, n=1: ("B-%s" % a if int(n) == 1
                                       else "B-%s-%d" % (a, int(n)))
        try:
            mi.apply("ep", log=lambda *a: None)
        finally:
            bi.ID_SCHEME, bi.ID_RE, bi.format_id = keep

    def _both_hops(self):
        self._hop_one()
        # a verdict on a beat the second cut will not have — hop one
        # stranded BT99, and hop two has to strand this one WITHOUT
        # taking BT99's record with it
        rv = self.read("review.json")
        rv["B-T99"] = {"status": "flagged", "note": "the second ghost"}
        self.write("review.json", rv)
        mi.apply("ep", log=lambda *a: None)

    def test_a_plan_on_the_previous_scheme_may_be_migrated_again(self):
        """The already-migrated guard compares against the CURRENT
        scheme, so a plan on a superseded one goes through. That is the
        one thing about the tool that was already right."""
        self._hop_one()
        self.assertEqual(self.read("edit_plan.json")["id_scheme"],
                         "anchor-v1")
        mi.apply("ep", log=lambda *a: None)
        plan = self.read("edit_plan.json")
        self.assertEqual(plan["id_scheme"], "shot-v1")
        self.assertEqual([b["id"] for b in plan["beats"]],
                         ["shot-T04", "shot-T04-2", "shot-T12"])

    def test_each_hop_backs_up_the_state_it_replaced(self):
        """`_premigration/` holds the BT plan and `_premigration.v2/`
        the anchor one. With a fixed directory name the second run
        copied nothing and said it had copied eleven artifacts."""
        self._both_hops()
        first = self.tmp / mi.BACKUP_DIRNAME
        second = self.tmp / (mi.BACKUP_DIRNAME + ".v2")
        self.assertEqual([b["id"] for b in
                          json.loads((first / "edit_plan.json").read_text())
                          ["beats"]], ["BT01", "BT07", "BT09"])
        self.assertEqual([b["id"] for b in
                          json.loads((second / "edit_plan.json").read_text())
                          ["beats"]], ["B-T04", "B-T04-2", "B-T12"])

    def test_the_map_still_answers_for_the_original_name(self):
        """`BT01` is what the shipped Resolve timeline speaks and what
        the baked `captions/BT01.mov` is called. A map holding only the
        latest hop cannot resolve it at all."""
        self._both_hops()
        doc = self.read(mi.MAP_FILE)
        self.assertEqual([g["scheme"] for g in mi.generations(doc)],
                         ["anchor-v1", "shot-v1"])
        self.assertEqual(mi.resolve_id(doc, "BT01"), "shot-T04")
        self.assertEqual(mi.resolve_id(doc, "BT07"), "shot-T04-2")
        self.assertEqual(mi.resolve_id(doc, "B-T12"), "shot-T12")
        self.assertEqual(mi.resolve_id(doc, "shot-T12"), "shot-T12")
        self.assertEqual(mi.resolve_id(doc, "BT99"), "BT99")

    def test_the_captions_gain_no_third_name_set(self):
        """Two name sets on two inodes: the hand-written names Resolve
        holds, and the current ones. The middle generation was minted by
        this tool and nothing outside `work/` ever saw it."""
        self._both_hops()
        caps = self.tmp / "captions"
        names = sorted(p.name for p in caps.glob("*.mov"))
        self.assertEqual(names, ["BT01.mov", "BT07.mov",
                                 "shot-T04-2.mov", "shot-T04.mov"])
        self.assertEqual(len({os.stat(p).st_ino for p in caps.glob("*.mov")}),
                         2)
        self.assertEqual(os.stat(caps / "BT01.mov").st_ino,
                         os.stat(caps / "shot-T04.mov").st_ino)

    def test_the_first_hops_archived_ghost_survives_the_second(self):
        """The file whose entire job is "nothing is dropped" was the
        thing dropping it."""
        self._both_hops()
        ids = [e["id"] for e in self.read(mi.ARCHIVE_FILE)["entries"]]
        self.assertEqual(sorted(ids), ["B-T99", "BT99"])
        notes = {e["id"]: e["entry"]["note"]
                 for e in self.read(mi.ARCHIVE_FILE)["entries"]}
        self.assertEqual(notes["BT99"], "a beat that is gone")

    def test_the_bake_cache_survives_both_hops(self):
        self._both_hops()
        self.assertEqual(self.read("captions/.bake_hashes.json"),
                         {"shot-T04": "aaa", "shot-T04-2": "bbb"})

    def test_a_third_apply_still_refuses(self):
        self._both_hops()
        with self.assertRaises(mi.MigrationError):
            mi.survey("ep")


class TheMapReadsItsOwnPast(unittest.TestCase):
    """`generations` has to understand a file written before it existed,
    or the audit trail starts at hop two."""

    def test_a_single_generation_file_is_folded_in(self):
        doc = {"slug": "ep", "scheme": "anchor-v1",
               "map": {"BT01": "B-T04"}}
        self.assertEqual(mi.generations(doc),
                         [{"scheme": "anchor-v1", "map": {"BT01": "B-T04"}}])
        self.assertEqual(mi.resolve_id(doc, "BT01"), "B-T04")

    def test_junk_resolves_to_itself_rather_than_raising(self):
        for doc in (None, {}, {"map": None}, {"generations": "no"}):
            self.assertEqual(mi.resolve_id(doc, "BT01"), "BT01")

    def test_a_backup_directory_is_chosen_per_generation(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            self.assertEqual(mi.backup_dir(tmp).name, "_premigration")
            (tmp / "_premigration").mkdir()
            self.assertEqual(mi.backup_dir(tmp).name, "_premigration.v2")
            (tmp / "_premigration.v2").mkdir()
            self.assertEqual(mi.backup_dir(tmp).name, "_premigration.v3")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
