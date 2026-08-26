# -*- coding: utf-8 -*-
"""The episode poster has to be reachable.

`_poster` writes poster.jpg BESIDE the work files — not in a
subdirectory — and the project row has advertised it since the Home board
learned to show poster tiles. The media route required exactly five path
parts (/media/<slug>/<kind>/<name>), and a root-level file has four, so
every card on the board rendered a broken image. Found 2026-08-25, on the
first screen of the app, because the graphite ground made the broken-image
glyph obvious where the light one had hidden it.

The fix is one allow-listed name, and that is the part worth pinning: the
root of a work dir holds edit_plan.json, review.json and a SYMLINK to the
footage library. It must never become browsable.

Run: /usr/bin/python3 -m unittest discover -s tests -t .
"""
import inspect
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline import editroom  # noqa: E402


def _route_source() -> str:
    """The media branch, read from the file.

    The request handler is a class defined INSIDE `serve()`, so it is not a
    module attribute and reflection cannot reach it. Reading the source is
    the honest way in — and it means this test fails if the branch is
    deleted, which is the point.
    """
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "pipeline", "editroom.py")
    src = open(path).read()
    start = src.index('elif self.path.startswith("/media/")')
    return src[start:start + 6000]


class PosterRoute(unittest.TestCase):
    def setUp(self):
        self.src = _route_source()

    def test_a_root_level_poster_is_served(self):
        self.assertIn('== "poster.jpg"', self.src)

    def test_it_is_the_ONLY_root_level_name(self):
        """The allow-list is the whole safety of this branch.

        A four-part media path that accepted any basename would serve
        edit_plan.json, review.json, story_feedback.json and anything else
        sitting in a work directory — including through the footage
        symlink, which points outside the project entirely.
        """
        # find the len(parts) == 4 branch and prove it compares a literal
        four = re.search(r"len\(parts\) == 4(.{0,400})", self.src, re.S)
        self.assertIsNotNone(four, "the four-part branch must exist")
        body = four.group(1)
        self.assertIn('"poster.jpg"', body)
        # no wildcard suffix check standing in for a name check
        self.assertNotIn("suffix", body.split("self._send(200")[0])

    def test_it_cannot_escape_the_work_directory(self):
        """`..` in a slug is already refused by _valid_slug, but the parent
        check is what stops a resolved symlink landing elsewhere."""
        four = re.search(r"len\(parts\) == 4(.{0,400})", self.src, re.S)
        self.assertIn("_valid_slug", four.group(1))
        self.assertIn("parent ==", four.group(1))

    def test_the_row_and_the_route_agree_on_the_filename(self):
        """The bug was a disagreement, not a missing file: the row said
        poster.jpg and the route could not serve it."""
        poster_fn = inspect.getsource(editroom._project_poster)
        self.assertIn("poster.jpg", poster_fn)
        self.assertIn('"poster.jpg"', self.src)


if __name__ == "__main__":
    unittest.main()
