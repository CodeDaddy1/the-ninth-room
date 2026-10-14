# -*- coding: utf-8 -*-
"""The brief says what the engine enforces, in the same words.

A brief that names a rule the engine does not check is a trap; one that
omits a rule the engine refuses on sends a session out to fail. This
file pins the illustration-director's brief to the validator's vocabulary
(the rubric ids, the honesty values, the Soul models by name, the read-
only shim's refusals) and pins the style file to its contract: no hex,
and every placeholder resolves through the design tokens.

Run: /usr/bin/python3 -m unittest discover -s tests -t .
"""
import os
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline import design_tokens, illustration  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
BRIEF = ROOT / ".claude" / "agents" / "illustration-director.md"
PLATE = ROOT / "brand" / "illustration" / "plate.md"


class Brief(unittest.TestCase):
    def setUp(self):
        self.text = BRIEF.read_text()

    def test_frontmatter_names_the_tools_and_the_job(self):
        head = self.text.split("---")[1]
        self.assertIn("name: illustration-director", head)
        self.assertIn("tools: Read, Write, Bash, Glob", head)
        self.assertIn("illustrate", head)

    def test_the_rubric_ids_are_stable(self):
        for n in range(1, 11):
            self.assertRegex(self.text, r"\*\*I%d " % n, "I%d missing" % n)

    def test_it_speaks_the_validators_vocabulary(self):
        for phrase in ("illustrate-check", "illustration", "reconstruction", "RECONSTRUCTION",
                       "never type a colour", "beside", "staging/illustration_rounds.json",
                       "estimate_credits", "start_image", "don't pre-estimate cost"):
            self.assertIn(phrase, self.text, phrase)
        for model in illustration.SOUL_MODELS:
            self.assertIn(model, self.text, model)

    def test_the_never_list_matches_the_shim(self):
        never = self.text[self.text.index("## Never"):]
        for phrase in ("generate create", "workflow", "upload", "soul-id", "local path",
                       "Download"):
            self.assertIn(phrase, never, phrase)

    def test_the_banned_word_appears_only_as_a_ban(self):
        hits = [m.start() for m in re.finditer(r"\binserts?\b", self.text)]
        for h in hits:
            window = self.text[max(0, h - 60):h + 40]
            self.assertIn("ban", window, "insert used, not banned: %r" % window)


class StyleFile(unittest.TestCase):
    def test_no_hex_is_typed_and_every_placeholder_resolves(self):
        text = PLATE.read_text()
        self.assertIsNone(re.search(r"#[0-9a-fA-F]{6}\b", text))
        tokens = design_tokens.load()
        names = set(re.findall(r"\{\{([a-z0-9_]+)\}\}", text))
        self.assertTrue(names)
        for n in names:
            self.assertNotEqual(design_tokens.resolve(tokens, n.replace("_", "-"), ""), "",
                                "%s resolves to nothing" % n)

    def test_both_blocks_and_the_shared_refusals_exist(self):
        text = PLATE.read_text()
        for h in ("## Plate (honesty: illustration)", "## Reconstruction (honesty: reconstruction)",
                  "## What both refuse"):
            self.assertIn(h, text)


if __name__ == "__main__":
    unittest.main()
