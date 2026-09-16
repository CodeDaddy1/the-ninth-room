# -*- coding: utf-8 -*-
"""The words landed before the code: "illustration", never "insert".

2026-09-15: nine Higgsfield rows reached work/hmns/assets/assets.json from a
hand session with `kind: "generated"`, the beat smuggled into `query`, no
cost, and "insert" in every row, a word CONTEXT.md bans under Cover. The
README, docs/blender.md and CLAUDE.md's "$0/mo is binding" line disagreed
with each other the same night. docs/decisions-illustrations.md settled the
vocabulary; this test keeps the paper and the one rewritten manifest saying
the same thing.

What breaks if this is wrong: a brief inherits "insert" and a validator
refuses it; an agent reads "$0/mo is binding" while the engine spends;
the storyteller refuses to cite a taste file that is signed.

Run: /usr/bin/python3 -m unittest discover -s tests -t .
"""
import json
import os
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ROOT = Path(__file__).resolve().parents[1]
HMNS_MANIFEST = ROOT / "work" / "hmns" / "assets" / "assets.json"
INSERT = re.compile(r"\binserts?\b", re.I)


class Paper(unittest.TestCase):
    def test_the_banned_word_is_gone_from_the_readme_and_the_blender_doc(self):
        for rel in ("README.md", "docs/blender.md"):
            text = (ROOT / rel).read_text()
            hits = [ln for ln in text.splitlines() if INSERT.search(ln)]
            self.assertEqual(hits, [], rel)

    def test_the_glossary_carries_the_four_terms_and_still_bans_insert(self):
        ctx = (ROOT / "CONTEXT.md").read_text()
        for term in ("**Illustration**", "**Reconstruction**", "**Provenance**", "**Ledger**"):
            self.assertIn(term, ctx)
        cover = ctx[ctx.index("**Cover**"):ctx.index("**Illustration**")]
        self.assertIn("insert", cover.split("_Avoid_:")[1])

    def test_zero_dollars_is_by_default_not_binding(self):
        claude = (ROOT / "CLAUDE.md").read_text()
        self.assertIn("$0/mo by default", claude)
        self.assertNotIn("is binding", claude)

    def test_the_storyteller_knows_taste_is_signed(self):
        brief = (ROOT / ".claude" / "agents" / "story-director.md").read_text()
        self.assertNotIn("It is unsigned", brief)
        self.assertIn("SIGNED 2026-08-28", brief)
        self.assertIn("SIGNED 2026-08-28", (ROOT / "brand" / "taste.md").read_text())

    def test_the_decision_record_exists_with_every_decision(self):
        adr = (ROOT / "docs" / "decisions-illustrations.md").read_text()
        rows = [ln for ln in adr.splitlines() if ln.startswith("| ")]
        numbers = [ln.split("|")[1].strip() for ln in rows]
        for n in range(1, 20):
            self.assertIn(str(n), numbers, "decision %d missing" % n)


@unittest.skipUnless(HMNS_MANIFEST.exists(), "hmns work folder is not on this machine")
class HmnsRows(unittest.TestCase):
    def setUp(self):
        self.rows = [a for a in json.loads(HMNS_MANIFEST.read_text())["assets"]
                     if a.get("kind") == "illustration"]

    def test_nine_rows_carry_the_illustration_shape(self):
        self.assertEqual(len(self.rows), 9)
        for a in self.rows:
            for field in ("honesty", "beat_id", "cost_credits", "model", "status", "license"):
                self.assertIn(field, a, a["id"])
            self.assertEqual(a["honesty"], "illustration")
            self.assertEqual(a["beat_id"], "shot-T41")
            self.assertNotIn("query", a)

    def test_the_credits_sum_to_the_set_that_was_bought(self):
        self.assertEqual(sum(a["cost_credits"] for a in self.rows), 38.0)

    def test_no_row_says_insert(self):
        for a in self.rows:
            for v in a.values():
                if isinstance(v, str):
                    self.assertIsNone(INSERT.search(v), a["id"])


if __name__ == "__main__":
    unittest.main()
