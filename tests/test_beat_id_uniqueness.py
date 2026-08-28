"""Two beats may not share an id.

Beats were the one id space in `validate_edit_plan` without a uniqueness
check — chapters, takes, broll, cards and overlays all had one. Ten
artifacts key on a beat id (review verdicts, captions, cards, sfx cues,
conform ops, trash, proxies, and the baked caption movs named for it), so a
duplicate does not orphan anything: it silently re-points the second beat's
history at the first, and no read-time filter can see it because the id
still resolves.

What breaks if this is wrong: a hand-edited or re-generated plan can carry
Caleb's notes from one shot onto a different one, with nothing anywhere
reporting it.
"""
import unittest

from pipeline import schemas


def _plan(beat_ids):
    """A minimal valid landscape plan, one beat per id given."""
    takes = {"takes": [{"id": "T%d" % (i + 1), "file": "T%d.mp4" % (i + 1),
                        "s": 0.0, "e": 10.0, "transcript": "line %d" % i,
                        "duration": 10.0}
                       for i in range(len(beat_ids))]}
    plan = {"slug": "ep", "format": "youtube_long", "orientation": "landscape",
            "theme": {"problem": "p", "promise": "q", "payoff": "r"},
            "hook": {"take_id": "T1", "why": "w"},
            "beats": [{"id": bid, "purpose": "hook" if i == 0 else "explain",
                       "take_id": "T%d" % (i + 1),
                       "trim": {"s": 0.0, "e": 10.0},
                       "transition_in": "cut"}
                      for i, bid in enumerate(beat_ids)]}
    return plan, takes


class BeatIdsAreUnique(unittest.TestCase):

    def test_a_duplicate_beat_id_is_an_error(self):
        plan, takes = _plan(["BT01", "BT01"])
        errs = schemas.validate_edit_plan(plan, takes, {"clips": []})
        self.assertTrue(any("duplicate beat id" in e for e in errs), errs)

    def test_the_error_names_the_id_and_where(self):
        """A plan with 82 beats needs to say which one."""
        plan, takes = _plan(["BT01", "BT02", "BT01"])
        errs = schemas.validate_edit_plan(plan, takes, {"clips": []})
        dupes = [e for e in errs if "duplicate beat id" in e]
        self.assertEqual(len(dupes), 1, errs)
        self.assertIn("BT01", dupes[0])
        self.assertIn("beats[2]", dupes[0])

    def test_distinct_ids_raise_nothing(self):
        plan, takes = _plan(["BT01", "BT02"])
        errs = schemas.validate_edit_plan(plan, takes, {"clips": []})
        self.assertFalse(any("duplicate beat id" in e for e in errs), errs)


if __name__ == "__main__":
    unittest.main()
