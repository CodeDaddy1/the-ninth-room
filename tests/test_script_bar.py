# -*- coding: utf-8 -*-
"""The script's craft bar, and the identity rules that stop silent corruption.

Two halves, split the way validate_edit_plan / coverage_notes already are:

  validate_script  — STRUCTURE AND IDENTITY. The class of mistake that
                     corrupts silently. Kept narrow on purpose so a script
                     written before a rule existed does not become invalid.
  script_notes     — THE CRAFT. Advisory as a function, required-empty by
                     the job that dispatched the writer.

The identity half exists because recordings match to sections by FILENAME
(vo_CH2-S3_r1_t1.webm). Renumber a section and real recordings orphan; reuse
a retired id and an OLD recording reads "recorded" for words the script no
longer says. Both are silent until the cut, which is why they are validated
rather than trusted to a brief.

Run: /usr/bin/python3 -m unittest discover -s tests -t .
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline import schemas  # noqa: E402


VISUAL = {"want": "the vault door, slow push in",
          "why": "illustrate — the door being named",
          "from": "library"}


def sec(**over):
    d = {"id": "CH1.S1", "kind": "vo", "text": "A short line to say.",
         "est_s": 60.0, "rev": 1, "visual": dict(VISUAL)}
    d.update(over)
    return d


def script(sections=None, **over):
    d = {"slug": "ep", "option_id": "S1", "target_minutes": 1.0,
         "chapters": [{"id": "CH1", "title": "One", "target_s": 60,
                       "sections": sections or [sec()]}]}
    d.update(over)
    return d


TAKES = {"takes": [{"id": "T1"}]}


class Identity(unittest.TestCase):
    """validate_script — the half that stops silent corruption."""

    def test_a_sound_script_validates(self):
        self.assertEqual(schemas.validate_script(script(), TAKES), [])

    def test_a_retired_id_may_never_be_reused(self):
        """The whole point. A recording named vo_CH1-S1_r1_t1 survives on
        disk after its section is cut; handing that id to a NEW line makes
        the old take read as this line's take."""
        s = script(retired_ids=["CH1.S1"])
        errs = schemas.validate_script(s, TAKES)
        self.assertTrue(any("retired" in e for e in errs), errs)

    def test_ids_must_look_like_the_filename_they_become(self):
        s = script([sec(id="intro-line")])
        errs = schemas.validate_script(s, TAKES)
        self.assertTrue(any("CH<n>.S<n>" in e for e in errs), errs)

    def test_rev_must_be_a_real_revision_number(self):
        for bad in (0, -1, 1.5, True, "2"):
            errs = schemas.validate_script(script([sec(rev=bad)]), TAKES)
            self.assertTrue(any("rev" in e for e in errs),
                            "rev=%r should be refused" % (bad,))

    def test_a_script_with_no_rev_is_still_valid(self):
        """Every script written before 2026-08-24 is implicitly rev 1.
        Sharpening the bar must not invalidate what is already on disk."""
        s = script([sec()])
        del s["chapters"][0]["sections"][0]["rev"]
        self.assertEqual(schemas.validate_script(s, TAKES), [])

    def test_desk_is_a_real_kind(self):
        s = script([sec(kind="desk", visual=None)])
        del s["chapters"][0]["sections"][0]["visual"]
        self.assertEqual(schemas.validate_script(s, TAKES), [])

    def test_an_unknown_kind_is_refused(self):
        errs = schemas.validate_script(script([sec(kind="voiceover")]), TAKES)
        self.assertTrue(any("kind must be" in e for e in errs), errs)

    def test_the_script_lane_needs_no_pitch_to_reference(self):
        """A script-led episode has no footage, so there was no pitch and
        no option to attribute it to."""
        s = script(origin="script")
        del s["option_id"]
        self.assertEqual(schemas.validate_script(s, TAKES), [])

    def test_the_footage_lane_still_demands_one(self):
        s = script()
        del s["option_id"]
        errs = schemas.validate_script(s, TAKES)
        self.assertTrue(any("option_id" in e for e in errs), errs)


class TheVoice(unittest.TestCase):
    """S1 — brand/voice-and-tone.md, checked rather than trusted."""

    def notes(self, text, origin="footage", kind="vo"):
        return schemas.script_notes(
            script([sec(kind=kind, text=text, source="u")]),
            target=1.0, origin=origin)

    def test_exclamation_marks_are_refused(self):
        self.assertTrue(any("exclamation" in n
                            for n in self.notes("What a place!")))

    def test_the_banned_tics_are_refused(self):
        for word in ("insane", "literally", "mind-blowing"):
            self.assertTrue(
                any("banned" in n for n in self.notes("This is %s." % word)),
                "%r should be refused" % word)

    def test_guys_is_no_longer_an_address_error(self):
        """The prohibition went with the person rule (Caleb, 2026-08-27)."""
        self.assertEqual(self.notes("Hey guys, look."), [])

    def test_I_passes_in_every_shape(self):
        """The whole point of the 2026-08-27 change: NOTHING checks person,
        in either lane, for any speaker. Caleb hosts and says "I"; on camera
        Alma and Sofia say it too. A checker that reached a take would be
        asking a real sentence somebody really said to rewrite itself."""
        line = "I went looking for it."
        person = lambda n: '"I"' in n or "person" in n or "ensemble" in n
        for origin in ("footage", "script"):
            for kind in ("vo", "desk"):
                # a `desk` section trips the VO dial, which is a different
                # rule -- assert on person, not on emptiness
                got = self.notes(line, origin=origin, kind=kind)
                self.assertFalse([n for n in got if person(n)],
                                 "%s/%s flagged person: %s"
                                 % (origin, kind, got))
        self.assertEqual(self.notes(line), [])   # the vo case is fully clean
        # and in a quote, where it is not even our sentence
        s = script([sec(kind="oncamera", take_id="T1", text=line)])
        del s["chapters"][0]["sections"][0]["visual"]
        self.assertEqual(schemas.script_notes(s, target=0.0), [])

    def test_a_quoted_take_is_not_held_to_a_writing_standard(self):
        """oncamera text is a transcript. Marking a real person's real
        sentence as too long would ask the past to rewrite itself."""
        s = script([sec(kind="oncamera", take_id="T1",
                        text="I literally can't believe it!", visual=None)])
        del s["chapters"][0]["sections"][0]["visual"]
        self.assertEqual(schemas.script_notes(s, target=0.0), [])


class EngineeredSilence(unittest.TestCase):
    """A wordless `vo` section (Caleb, 2026-08-27).

    S7 had told the writer for a while that "a `visual` and no words is a
    legitimate section, and it is often the best one in the episode", and
    validate_script rejected every one of them — so peak protection, the
    finding that has survived six studies, was unwritable. Johnny Harris
    runs 19 wordless seconds at Srebrenica.
    """

    def silent(self, **over):
        d = {"id": "CH1.S1", "kind": "vo", "text": "", "est_s": 15.0,
             "rev": 1, "visual": dict(VISUAL)}
        d.update(over)
        return d

    def test_a_wordless_vo_with_a_picture_is_legal(self):
        s = script([self.silent()])
        s["chapters"][0]["target_s"] = 15
        self.assertEqual(schemas.validate_script(s, TAKES), [])

    def test_a_wordless_vo_with_no_picture_is_still_a_hole(self):
        """The `visual` is the whole difference between silence and a gap
        — there has to be something to look at."""
        s = self.silent()
        del s["visual"]
        self.assertTrue(any("hole" in e for e in
                            schemas.validate_script(script([s]), TAKES)))

    def test_a_wordless_desk_piece_is_nothing(self):
        self.assertTrue(any("hole" in e for e in schemas.validate_script(
            script([self.silent(kind="desk")]), TAKES)))

    def test_a_wordless_quote_is_not_a_quote(self):
        self.assertTrue(any("hole" in e for e in schemas.validate_script(
            script([self.silent(kind="oncamera", take_id="T1")]), TAKES)))

    def test_silence_is_running_time_but_not_narration(self):
        """The dial would otherwise read a 15s held picture as 15s of
        voice-over and push the writer to cut real narration to get back
        under it — lying in the exact direction that destroys the beat."""
        s = script([sec(est_s=15.0), self.silent(id="CH1.S2")])
        self.assertAlmostEqual(schemas.vo_share(s), 0.5)


class LoopLedger(unittest.TestCase):
    """S6 written down (Caleb, 2026-08-27). "The payoff must always land"
    is the brand's one non-negotiable and was the only rule with nothing
    behind it — validate_edit_plan checks that *a* payoff beat exists and
    nothing checked that the hook's actual promises were kept."""

    def two_chapters(self, **over):
        d = {"slug": "ep", "option_id": "S1", "target_minutes": 1.0,
             "chapters": [
                 {"id": "CH1", "title": "One", "target_s": 120,
                  "sections": [sec(id="CH1.S1"), sec(id="CH1.S2")]},
                 {"id": "CH2", "title": "Two", "target_s": 120,
                  "sections": [sec(id="CH2.S1"), sec(id="CH2.S2")]}]}
        d.update(over)
        return d

    def notes(self, doc):
        return schemas.script_notes(doc, target=1.0)

    # --- structure: an error, because a dangling ref means nothing ---

    def test_a_ledger_pointing_at_a_missing_section_is_an_error(self):
        d = self.two_chapters(loops=[{"id": "L1", "opens": "CH1.S1",
                                      "pays": "CH9.S9"}])
        self.assertTrue(any("not a section" in e
                            for e in schemas.validate_script(d, TAKES)))

    def test_duplicate_loop_ids_are_refused(self):
        d = self.two_chapters(loops=[
            {"id": "L1", "opens": "CH1.S1", "pays": "CH2.S2"},
            {"id": "L1", "opens": "CH1.S2", "pays": "CH2.S2"}])
        self.assertTrue(any("duplicate loop id" in e
                            for e in schemas.validate_script(d, TAKES)))

    def test_an_absent_ledger_never_invalidates_an_existing_script(self):
        """The house rule: an existing script must not become invalid when
        the bar gets sharper. Absence is a NOTE, never an error."""
        self.assertEqual(schemas.validate_script(self.two_chapters(),
                                                 TAKES), [])

    # --- the bar: advisory ---

    def test_a_missing_ledger_is_noted(self):
        self.assertTrue(any("no loop ledger" in n
                            for n in self.notes(self.two_chapters())))

    def test_a_short_owes_no_ledger(self):
        """One loop, not a ledger — a single chapter is exempt."""
        self.assertEqual(
            [n for n in schemas.script_notes(script(), target=1.0)
             if "ledger" in n], [])

    def test_a_loop_paid_before_it_opens_is_noted(self):
        d = self.two_chapters(loops=[{"id": "L1", "opens": "CH2.S2",
                                      "pays": "CH1.S1"}])
        self.assertTrue(any("before it opens" in n for n in self.notes(d)))

    def test_loops_paid_out_of_order_are_noted(self):
        """Rober opens eight and pays all eight in the SAME order."""
        d = self.two_chapters(loops=[
            {"id": "L1", "opens": "CH1.S1", "pays": "CH2.S2"},
            {"id": "L2", "opens": "CH1.S2", "pays": "CH2.S1"}])
        self.assertTrue(any("in the order they were opened" in n
                            for n in self.notes(d)))

    def test_a_climax_that_lands_early_is_noted(self):
        d = self.two_chapters(loops=[{"id": "L1", "opens": "CH1.S1",
                                      "pays": "CH1.S2"}])
        self.assertTrue(any("climax should sit late" in n
                            for n in self.notes(d)))

    def test_a_sound_ledger_is_silent(self):
        d = self.two_chapters(loops=[
            {"id": "L1", "opens": "CH1.S1", "pays": "CH2.S1"},
            {"id": "L2", "opens": "CH1.S2", "pays": "CH2.S2"}])
        self.assertEqual([n for n in self.notes(d) if "loop" in n
                          or "climax" in n], [])


class SentenceShape(unittest.TestCase):
    """S3 — short declaratives, a fragment to land it."""

    def test_a_sentence_past_the_cap_is_refused(self):
        long = " ".join(["word"] * (schemas.MAX_SENTENCE_W + 1)) + "."
        notes = schemas.script_notes(script([sec(text=long)]), target=1.0)
        self.assertTrue(any("stops being speech" in n for n in notes), notes)

    def test_a_long_median_is_refused_even_when_each_sentence_passes(self):
        """Every sentence under the hard cap, all of them heavy. The cap
        alone would call this clean."""
        mid = " ".join(["word"] * (schemas.MEDIAN_SENTENCE_W + 6)) + "."
        notes = schemas.script_notes(
            script([sec(text=mid), sec(id="CH1.S2", text=mid)]), target=1.0)
        self.assertTrue(any("median sentence" in n for n in notes), notes)

    def test_the_house_shape_passes(self):
        notes = schemas.script_notes(
            script([sec(text="About 13 feet tall and 3 tons. "
                             "Wrong continent entirely.", source="u")]),
            target=1.0)
        self.assertEqual(notes, [])


class ClaimsAndPictures(unittest.TestCase):
    """S2 and S4 — every claim traces, every narrated line has a picture."""

    def test_a_narrated_number_needs_a_source(self):
        notes = schemas.script_notes(
            script([sec(text="It opened in 1909.")]), target=1.0)
        self.assertTrue(any("cannot trace" in n for n in notes), notes)

    def test_a_voice_over_line_owes_a_picture(self):
        """The teleprompter picture is hard-blocked from shipping, so a VO
        line with nothing to look at is a hole in the episode."""
        s = script([sec()])
        del s["chapters"][0]["sections"][0]["visual"]
        notes = schemas.script_notes(s, target=1.0)
        self.assertTrue(any("no `visual`" in n for n in notes), notes)

    def test_a_visual_must_name_a_justification(self):
        v = dict(VISUAL, why="a nice shot of the door")
        notes = schemas.script_notes(script([sec(visual=v)]), target=1.0)
        self.assertTrue(any("no justification" in n for n in notes), notes)

    def test_every_justification_the_b_roll_grammar_allows_is_accepted(self):
        """One definition of the five, shared with coverage_notes via
        why_kind — the two bars cannot drift apart."""
        for w in schemas.COVER_WHYS:
            v = dict(VISUAL, why="%s — the thing" % w)
            notes = schemas.script_notes(script([sec(visual=v)]), target=1.0)
            self.assertFalse(any("justification" in n for n in notes),
                             "%r should be accepted" % w)

    def test_a_visual_must_say_where_it_comes_from(self):
        notes = schemas.script_notes(
            script([sec(visual=dict(VISUAL, **{"from": "somewhere"}))]),
            target=1.0)
        self.assertTrue(any("visual.from" in n for n in notes), notes)

    def test_a_desk_line_owes_no_picture(self):
        """His face IS the shot there — a cutaway is optional."""
        s = script([sec(kind="desk", text="A short line to say.")])
        del s["chapters"][0]["sections"][0]["visual"]
        self.assertEqual(schemas.script_notes(s, target=0.0), [])


class Budget(unittest.TestCase):
    """coverage_budget — what the script declared it needs."""

    def test_the_script_declares_what_must_be_sourced(self):
        """A script-led episode has no library, so a shortfall against one
        says 'everything is missing' — true and useless. The visual.from on
        each line is what sourcing can actually propose against."""
        s = script([
            sec(id="CH1.S1", est_s=10.0),                       # from: library
            sec(id="CH1.S2", est_s=20.0,
                visual=dict(VISUAL, **{"from": "stock"})),
            sec(id="CH1.S3", est_s=5.0,
                visual=dict(VISUAL, **{"from": "archival"})),
        ])
        b = schemas.coverage_budget(s, {"clips": []})
        self.assertEqual(b["declared_seconds"].get("library"), 10.0)
        self.assertEqual(b["declared_seconds"].get("stock"), 20.0)
        self.assertEqual(b["to_source_seconds"], 25.0)

    def test_an_empty_library_does_not_crash(self):
        b = schemas.coverage_budget(script(), None)
        self.assertEqual(b["library_seconds"], 0.0)


class RealScript(unittest.TestCase):
    """The bar is measured against the one real script on disk, because a
    bar nobody could pass is not a bar (verification #2 of the plan)."""

    def test_the_shipped_hmns_script_still_validates(self):
        """Identity rules must not invalidate what already exists — the
        partial-migration lesson, applied to a validator."""
        import json
        from pathlib import Path
        p = (Path(__file__).resolve().parent.parent / "work"
             / "houston-museum-of-natural-science" / "script.json")
        if not p.exists():
            self.skipTest("hmns script not on this machine")
        t = json.loads((p.parent / "analysis" / "takes.json").read_text())
        self.assertEqual(schemas.validate_script(json.loads(p.read_text()), t),
                         [])


if __name__ == "__main__":
    unittest.main()
