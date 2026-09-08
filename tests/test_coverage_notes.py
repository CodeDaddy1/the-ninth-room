# -*- coding: utf-8 -*-
"""The b-roll craft rules, mechanized.

2026-08-24: the crooise cut put five 1.1-second postcards over the hook
(one of them a different ship) while the line was about donuts — Caleb:
"supportive of the story, not a bombardment of noise". coverage_notes is
the arithmetic half of the fix: pure, advisory (existing plans must not
brick surgery writes), and the bar the coverage job must leave empty.

Run: /usr/bin/python3 -m unittest discover -s tests -t .
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline import schemas  # noqa: E402


def beat(bid="BT01", dur=10.0, covers=None, **extra):
    b = {"id": bid, "take_id": "T1", "trim": {"s": 0.0, "e": dur}}
    if covers is not None:
        b["broll"] = covers
    b.update(extra)
    return b


def cover(clip="B001", at=1.0, dur=2.5, why="illustrate: the thing"):
    c = {"clip_id": clip, "at": at, "duration": dur}
    if why is not None:
        c["why"] = why
    return c


def takes_where(**id_to_file):
    """A takes.json payload. Kind is derived from the FILE, which is where
    the prefix actually lives."""
    from pipeline.takes import kind_of_file
    return {"takes": [{"id": i, "file": f, "kind": kind_of_file(f)}
                      for i, f in id_to_file.items()]}


class CoverageNotes(unittest.TestCase):
    def notes(self, *beats, takes=None):
        return schemas.coverage_notes({"beats": list(beats)}, takes)

    def test_a_clean_cover_passes_silently(self):
        self.assertEqual(self.notes(beat(covers=[cover()])), [])

    def test_an_uncovered_beat_says_nothing(self):
        self.assertEqual(self.notes(beat()), [])

    def test_sub_legible_covers_are_named(self):
        out = self.notes(beat(covers=[cover(dur=1.1)]))
        self.assertTrue(any("cannot be read" in x for x in out))

    def test_the_bombardment_rule(self):
        covers = [cover(clip="B%02d" % i, at=i * 2.0, dur=1.9)
                  for i in range(4)]
        out = self.notes(beat(dur=20.0, covers=covers))
        self.assertTrue(any("bombardment" in x for x in out))

    def test_the_landing_belongs_to_the_face(self):
        out = self.notes(beat(dur=10.0, covers=[cover(at=8.5, dur=1.9)]))
        self.assertTrue(any("landing" in x for x in out))

    def test_the_coverage_ratio(self):
        out = self.notes(beat(dur=10.0, covers=[
            cover(at=0.5, dur=3.5), cover(clip="B002", at=4.5, dur=3.5)]))
        self.assertTrue(any("stops being one" in x for x in out))

    def test_a_peak_is_never_covered(self):
        out = self.notes(beat(covers=[cover()], peak=True))
        self.assertTrue(any("peak" in x for x in out))

    def test_a_cover_without_a_why_is_named(self):
        out = self.notes(beat(covers=[cover(why=None)]))
        self.assertTrue(any("no why" in x for x in out))

    def test_vo_beats_are_exempt_from_ratio_and_landing(self):
        """A VO beat is a teleprompter recording whose picture must never
        ship, so it owes near-total coverage and the landing rule cannot
        apply. Exemption comes from the TAKE's kind."""
        b = beat(dur=10.0, covers=[cover(at=0.0, dur=9.5)], take_id="T01")
        self.assertEqual(
            self.notes(b, takes=takes_where(T01="vo_CH1-S2_r1_t1.mp4")), [])

    def test_the_exemption_needs_the_takes_to_be_reachable(self):
        """THE REGRESSION. For a year this rule tested
        `take_id.startswith("vo_")` and no take id can start with `vo_` —
        they are minted T01, T02 (takes.py:312) and the prefix is on the
        file. So the exemption never fired: every VO beat was told it
        "covers the landing" and jobs.py:1611 failed the coverage job on
        any entry, blocking VO-led episodes at a gate whose exemption was
        unreachable. Measured on golf-testing: ten notes, all of them on
        its five VO beats (2026-08-28)."""
        b = beat(dur=10.0, covers=[cover(at=0.0, dur=9.5)], take_id="T01")
        self.assertNotEqual(self.notes(b), [],
                            "without takes there is no kind, so no exemption")

    def test_a_desk_beat_is_not_exempt(self):
        """The face IS the shot, so the landing still belongs to it."""
        b = beat(dur=10.0, covers=[cover(at=0.0, dur=9.5)], take_id="T01")
        out = self.notes(b, takes=takes_where(T01="desk_CH1-S2_r1_t1.mp4"))
        self.assertNotEqual(out, [])

    def test_a_beat_with_no_take_is_not_exempt(self):
        """`picture` is pure coverage; it is not voice-over."""
        b = beat(dur=10.0, covers=[cover(at=0.0, dur=9.5)])
        b.pop("take_id", None)
        self.assertNotEqual(self.notes(b, takes=takes_where()), [])


if __name__ == "__main__":
    unittest.main()


class TagsLiftTwoCapsAndOnlyTwo(unittest.TestCase):
    """Caleb, 2026-08-28, rejecting taste T11 and T7 in his own words:
    "allow for extra b-roll if relevant by tags." So "support, not
    density" stopped being his standard, and the three-cover cap and the
    60% ceiling stopped being absolute.

    The lift has to mean the TAG did work. Intersecting a clip's tags
    with words in the line would pass on coincidence — a clip tagged
    "butterfly" over any line that says butterfly — and coincidence is
    what a bombardment looks like from the inside. So the cover names the
    tag in the why it already owed.

    What breaks if this is wrong: too permissive and the cap is
    decoration; too strict and it is the build-share cap all over again,
    a rule nobody can satisfy. Every, not any, is the hinge.
    """

    def catalog(self, **id_to_tags):
        return {"clips": [{"id": i, "tags": t}
                          for i, t in id_to_tags.items()]}

    def notes(self, *beats, takes=None, broll=None):
        return schemas.coverage_notes({"beats": list(beats)}, takes, broll)

    def _four(self, whys):
        return [cover(clip="B%02d" % i, at=i * 2.0, dur=1.9, why=w)
                for i, w in enumerate(whys)]

    def test_four_covers_that_all_name_a_tag_are_allowed(self):
        covers = self._four(["illustrate: the butterfly wing"] * 4)
        out = self.notes(beat(dur=20.0, covers=covers),
                         broll=self.catalog(**{"B%02d" % i: ["butterfly"]
                                               for i in range(4)}))
        self.assertEqual([x for x in out if "bombardment" in x], [], out)

    def test_one_untagged_cover_and_the_cap_still_fires(self):
        """EVERY, not any — one unjustified cover in a pile is still what
        a bombardment is made of."""
        covers = self._four(["illustrate: the butterfly wing"] * 3
                            + ["illustrate: something else"])
        out = self.notes(beat(dur=20.0, covers=covers),
                         broll=self.catalog(**{"B%02d" % i: ["butterfly"]
                                               for i in range(4)}))
        self.assertTrue(any("bombardment" in x for x in out), out)

    def test_the_note_names_the_cover_that_broke_the_match(self):
        """Otherwise the lift is invisible machinery: someone who tagged
        three of four reads the same sentence as someone who tagged none,
        and cannot tell a working rule from a broken one."""
        covers = self._four(["illustrate: the butterfly wing"] * 3
                            + ["illustrate: something else"])
        out = [x for x in self.notes(
            beat(dur=20.0, covers=covers),
            broll=self.catalog(**{"B%02d" % i: ["butterfly"]
                                  for i in range(4)})) if "bombardment" in x]
        self.assertIn("B03", out[0])
        self.assertIn("3 of them name a tag", out[0])

    def test_the_ratio_ceiling_rises_but_does_not_vanish(self):
        """0.85, not unbounded — an on-camera beat stays at least a sixth
        face however well tagged its covers are."""
        covers = [cover(clip="B01", at=0.5, dur=3.5,
                        why="illustrate: the butterfly"),
                  cover(clip="B02", at=4.2, dur=3.5,
                        why="illustrate: the butterfly")]
        cat = self.catalog(B01=["butterfly"], B02=["butterfly"])
        # 70% covered: over the plain 60% ceiling, under the tagged 85%
        self.assertEqual([x for x in self.notes(beat(dur=10.0, covers=covers),
                                                broll=cat)
                          if "stops being one" in x], [])
        # 90% covered: over both
        covers[1]["duration"] = 5.5
        self.assertTrue(any("stops being one" in x
                            for x in self.notes(beat(dur=10.0, covers=covers),
                                                broll=cat)))

    def test_a_peak_stays_untouchable_however_well_tagged(self):
        """The one rule six of the seven film studies converged on. It is
        not on the table and no tag buys it."""
        c = cover(clip="B01", why="illustrate: the butterfly")
        out = self.notes(beat(covers=[c], peak=True),
                         broll=self.catalog(B01=["butterfly"]))
        self.assertTrue(any("peak" in x for x in out), out)

    def test_the_landing_and_the_legibility_floor_are_not_lifted(self):
        out = self.notes(
            beat(dur=10.0, covers=[cover(clip="B01", at=8.5, dur=1.1,
                                         why="illustrate: the butterfly")]),
            broll=self.catalog(B01=["butterfly"]))
        self.assertTrue(any("landing" in x for x in out), out)
        self.assertTrue(any("cannot be read" in x for x in out), out)

    def test_a_tag_must_be_named_not_merely_owned(self):
        """The clip carries the tag; the why never says it. Nothing is
        earned by owning a tag you did not use."""
        covers = self._four(["illustrate: a shot"] * 4)
        out = self.notes(beat(dur=20.0, covers=covers),
                         broll=self.catalog(**{"B%02d" % i: ["butterfly"]
                                               for i in range(4)}))
        self.assertTrue(any("bombardment" in x for x in out), out)

    def test_a_substring_is_not_a_tag_match(self):
        """"butter" inside "butterfly" must not count, or the match is
        decided by spelling accidents."""
        covers = self._four(["illustrate: the butterfly wing"] * 4)
        out = self.notes(beat(dur=20.0, covers=covers),
                         broll=self.catalog(**{"B%02d" % i: ["butter"]
                                               for i in range(4)}))
        self.assertTrue(any("bombardment" in x for x in out), out)

    def test_calebs_own_manual_tags_count_too(self):
        """catalog_broll keeps the agent's tags and his apart on purpose;
        a reader asking what a clip is about has to union them."""
        covers = self._four(["illustrate: the butterfly wing"] * 4)
        cat = {"clips": [{"id": "B%02d" % i, "tags": [],
                          "manual_tags": ["butterfly"]} for i in range(4)]}
        out = self.notes(beat(dur=20.0, covers=covers), broll=cat)
        self.assertEqual([x for x in out if "bombardment" in x], [], out)

    def test_without_a_catalog_the_caps_stand_exactly_as_before(self):
        """The lift is opt-in on real data. Both existing callers passed
        no catalog, and nothing they gate on may have moved."""
        covers = self._four(["illustrate: the butterfly wing"] * 4)
        out = self.notes(beat(dur=20.0, covers=covers))
        self.assertTrue(any("bombardment" in x for x in out), out)


class JustifiedWhys(unittest.TestCase):
    """R1, mechanized (2026-08-24, from the Beau Miles study).

    The rubric line "every cover names exactly one of the justifications"
    was the reviewer's judgment until now; a why that names none is a
    preference with a sentence in front of it. And the fifth
    justification exists because the first four are all defined against
    a spoken line — footage of the work advancing had no legal reason to
    exist, so R1 obliged an editor to delete exactly the coverage Beau
    Miles builds 20% of a film from.
    """

    def notes(self, why):
        return schemas.coverage_notes(
            {"beats": [beat(covers=[cover(why=why)])]})

    def test_every_justification_is_accepted(self):
        for kind in schemas.COVER_WHYS:
            self.assertEqual(self.notes("%s: the reason" % kind), [],
                             "%s should be legal" % kind)

    def test_process_is_one_of_them(self):
        self.assertIn("process", schemas.COVER_WHYS)
        self.assertEqual(self.notes("process: hands opening the case"), [])

    def test_a_dash_reads_the_same_as_a_colon(self):
        """Both formats appear in real editor output — a checker that
        graded punctuation would fail half of them for nothing."""
        self.assertEqual(self.notes("illustrate - the donut awning"), [])
        self.assertEqual(self.notes("illustrate: the donut awning"), [])

    def test_a_why_that_names_no_justification_is_flagged(self):
        notes = self.notes("it looked nice here")
        self.assertEqual(len(notes), 1)
        self.assertIn("must LEAD with one of", notes[0])
        self.assertIn("process", notes[0])  # the vocabulary is quoted

    def test_the_justification_must_LEAD(self):
        """A cover that buries the word mid-sentence has not claimed it."""
        self.assertEqual(len(self.notes("a nice wide that helps establish "
                                        "the hall")), 1)

    def test_a_missing_why_still_reads_as_missing_not_unknown(self):
        notes = schemas.coverage_notes(
            {"beats": [beat(covers=[cover(why=None)])]})
        self.assertEqual(len(notes), 1)
        self.assertIn("has no why", notes[0])

    def test_process_grants_itself_no_exemption(self):
        """The premise of the VO exemption is that there is no face to
        cut back to. A cover cannot create that condition by naming it."""
        covers = [cover(clip="B1", at=0.0, dur=3.0, why="process: the walk"),
                  cover(clip="B2", at=4.5, dur=4.5, why="process: the work")]
        notes = schemas.coverage_notes({"beats": [beat(dur=10.0,
                                                       covers=covers)]})
        self.assertTrue(any("covered" in n for n in notes),
                        "the 60%% ratio still applies: %r" % notes)
        self.assertTrue(any("landing" in n for n in notes),
                        "the landing still belongs to the face: %r" % notes)

    def test_why_kind_is_pure_and_says_none_for_nonsense(self):
        self.assertEqual(schemas.why_kind("Establish — the plaza"), "establish")
        self.assertEqual(schemas.why_kind("  bridge, hides the jump"), "bridge")
        self.assertIsNone(schemas.why_kind(""))
        self.assertIsNone(schemas.why_kind(None))
        self.assertIsNone(schemas.why_kind("vibes"))


class GearChange(unittest.TestCase):
    """S5, measured (2026-08-27).

    Yes Theory runs 18.8 cuts/min overall — within 2% of Mark Rober — so
    cut rate is not what separates these films. TEXTURE is: their scripted
    VO carries 35% of all cuts at ~1.8s mean shot while everything else
    runs ~4.0s. This reports the two numbers and gates nothing, because
    `coverage_notes` is required empty by the coverage job and a threshold
    nobody has calibrated would fail a real cut.
    """

    def test_an_empty_plan_reports_zeros_rather_than_dividing_by_zero(self):
        g = schemas.gear_change({"beats": []})
        self.assertEqual(g["ratio"], 0.0)
        self.assertEqual(g["vo_beats"], 0)

    def test_a_vo_beat_is_measured_by_its_covers(self):
        """On a VO beat the b-roll IS the picture — the teleprompter take
        can never ship, so the covers are the shots."""
        g = schemas.gear_change({"beats": [
            beat("BT01", dur=12.0, take_id="T01",
                 covers=[cover(dur=2.0), cover(dur=2.0), cover(dur=2.0)])]},
            takes_where(T01="vo_CH1-S1_r1_t1.mp4"))
        self.assertEqual(g["vo_mean_s"], 2.0)
        self.assertEqual(g["vo_beats"], 1)
        self.assertEqual(g["scene_beats"], 0)

    def test_a_scene_beat_is_the_face_plus_each_cutaway(self):
        g = schemas.gear_change({"beats": [
            beat("BT01", dur=12.0, covers=[cover(), cover()])]})
        self.assertEqual(g["scene_mean_s"], 4.0)      # 12s over 3 shots
        self.assertEqual(g["scene_beats"], 1)

    def test_the_ratio_is_what_makes_a_flat_episode_visible(self):
        """Two textures that have collapsed into one read as ratio ~1.0;
        a real gear change reads high. This is the number to watch."""
        flat = schemas.gear_change({"beats": [
            beat("BT01", dur=8.0, take_id="T01",
                 covers=[cover(dur=4.0), cover(dur=4.0)]),
            beat("BT02", dur=8.0, take_id="T02", covers=[cover()])]},
            takes_where(T01="vo_CH1-S1_r1_t1.mp4", T02="IMG_1.mov"))
        self.assertAlmostEqual(flat["ratio"], 1.0)

    def test_a_vo_beat_without_takes_is_invisible_to_the_ratio(self):
        """The fifth dead site, found 2026-08-28 while ratcheting the
        other four. gear_change tested `take_id.startswith("vo_")` too,
        so a fully VO-led cut would have reported "no VO beats" and the
        ratio would have stayed undefined forever."""
        plan = {"beats": [beat("BT01", dur=8.0, take_id="T01",
                               covers=[cover(dur=4.0)])]}
        self.assertEqual(schemas.gear_change(plan)["vo_beats"], 0)
        self.assertEqual(
            schemas.gear_change(
                plan, takes_where(T01="vo_CH1-S1_r1_t1.mp4"))["vo_beats"], 1)

    def test_our_own_cuts_have_no_vo_half_at_all(self):
        """Measured 2026-08-27: every existing edit plan predates the
        VO-led format and contains zero `vo_` beats, so the ratio is
        undefined rather than bad. Pinned so the day that changes is
        visible in a diff rather than in a shrug.

        Re-checked 2026-08-28 and the conclusion survives, but note how it
        was reached: the detector it was measured with was dead, so it
        would have said "zero" whatever the cuts contained. It was right
        by luck — every take in every project is `oncamera` except
        oligarchy's two, and oligarchy has no plan. The measurement is
        only trustworthy from here."""
        g = schemas.gear_change({"beats": [beat("BT01", dur=10.0)]})
        self.assertEqual(g["vo_beats"], 0)
        self.assertEqual(g["ratio"], 0.0)
        self.assertGreater(g["scene_mean_s"], 0)
