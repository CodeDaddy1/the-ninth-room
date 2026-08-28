# -*- coding: utf-8 -*-
"""Only one function may read a recording's filename prefix.

What a take IS was re-derived from its filename at FIVE sites, and three of
them tested `take_id.startswith("vo_")` — which no take id can satisfy,
because ids are minted "T%02d" (takes.py:312) and the prefix lives on
`file`. The coverage exemption and the caption marker were both dead, so
every VO beat was told it "covers the landing" and jobs.py:1611 failed the
job on any entry: VO-led episodes were blocked at a gate whose exemption
could not fire. `gear_change` was dead the same way and would have reported
"no VO beats" on a cut that was entirely VO.

The tests were dead with it. Three of them asserted the exemption worked
using `take_id="vo_CH1-S1_r1_t1"` — an id that cannot exist — so the test
and the unreachable branch agreed with each other for a year.

Kind is now derived once, at ingest, from the file, and STORED on the take
(docs/decisions-beat-and-take-kind.md). This is a ratchet. It only falls.

Run: /usr/bin/python3 -m unittest discover -s tests -t .
"""
import ast
import os
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PIPELINE = Path(__file__).resolve().parent.parent / "pipeline"

# The one function entitled to look at a prefix, and the module it lives in.
OWNER_MODULE = "takes.py"
OWNER_FUNC = "kind_of_file"

PREFIX_READ = re.compile(r'startswith\(\s*["\'](?:vo_|desk_)')


def _code_lines(path):
    """Source lines with comments and docstrings removed, so the incident
    can be written down without tripping the rule it describes."""
    src = path.read_text()
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return []
    doc_lines = set()
    for node in ast.walk(tree):
        if (isinstance(node, ast.Expr)
                and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)):
            doc_lines.update(range(node.lineno, (node.end_lineno or 0) + 1))
    out = []
    for i, line in enumerate(src.splitlines(), 1):
        if i in doc_lines:
            continue
        out.append((i, line.split("#", 1)[0]))
    return out


class KindHasOneHome(unittest.TestCase):

    def test_no_module_reads_a_prefix_except_the_owner(self):
        offenders = []
        for path in sorted(PIPELINE.glob("*.py")):
            for lineno, line in _code_lines(path):
                if PREFIX_READ.search(line):
                    offenders.append("%s:%d" % (path.name, lineno))
        self.assertEqual(
            offenders, [],
            "read the take's `kind` instead — see takes.kind_of_file")

    def test_the_owner_still_exists_and_works(self):
        """A ratchet that passes because the rule was deleted is worthless."""
        from pipeline.takes import kind_of_file
        self.assertEqual(kind_of_file("vo_CH1-S1_r1_t1.mp4"), "vo")
        self.assertEqual(kind_of_file("desk_CH1-S1_r1_t1.mp4"), "desk")
        self.assertEqual(kind_of_file("IMG_6371.mov"), "oncamera")
        self.assertEqual(kind_of_file(None), "oncamera")

    def test_ingest_stamps_kind_onto_every_take(self):
        """If this stops happening, every reader silently falls back to
        deriving it, and the decision has been undone without a diff."""
        src = (PIPELINE / "takes.py").read_text()
        self.assertIn('"kind": kind_of_file(f["name"])', src)

    def test_a_beat_with_no_take_is_picture_not_oncamera(self):
        """Caleb, 2026-08-28: a beat may have no take at all. Defaulting
        it to `oncamera` would apply the face rules to pure picture."""
        from pipeline import schemas
        self.assertEqual(schemas.beat_kind({}, {}), "picture")
        self.assertEqual(schemas.beat_kind({"take_id": None}, {}), "picture")
        self.assertEqual(
            schemas.beat_kind({"take_id": "T01"},
                              {"T01": {"id": "T01", "kind": "vo"}}), "vo")

    def test_kind_is_read_at_use_not_frozen_into_the_plan(self):
        """VO can be recorded in post (Caleb, 2026-08-28), so a beat
        becomes `vo` the moment its recording lands. A `kind` stored on the
        beat would have to be rewritten every time one arrives."""
        from pipeline import schemas
        beat = {"take_id": "T01"}
        self.assertEqual(schemas.beat_kind(beat, {}), "picture")
        self.assertEqual(
            schemas.beat_kind(beat, {"T01": {"id": "T01",
                                             "file": "vo_CH1-S1_r1_t1.mp4"}}),
            "vo")


if __name__ == "__main__":
    unittest.main()
