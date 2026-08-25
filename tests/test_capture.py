# -*- coding: utf-8 -*-
"""An article screenshot is a CITATION, and must never pass as stock.

2026-08-25, Caleb: "we need to source videos, clips, screenshots of
online articles with their headline." The first two are stock and come
with a reuse licence. The third never will — and that difference is the
whole point of this module, because `asset-sourcer.md` correctly refuses
anything whose page does not state a licence, a rule that would forbid
screenshotting a newspaper if a screenshot were stock.

It is not. It is evidence for a narrated claim, shown briefly with its
source legible in frame — the sourced-quote card the Johnny Harris study
describes. So the row records the headline, the publication and the
capture time, and says in the licence field, in words, what it is.

Run: /usr/bin/python3 -m unittest discover -s tests -t .
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline import capture  # noqa: E402
from pipeline.ingest import IngestError  # noqa: E402


class Slugs(unittest.TestCase):
    def test_a_headline_becomes_a_readable_filename(self):
        self.assertEqual(
            capture.slugify("History of the Houston Museum of Natural Science"),
            "history-of-the-houston-museum-of-natural-science")

    def test_punctuation_and_case_are_flattened(self):
        self.assertEqual(capture.slugify("Why?! The T. rex — Explained"),
                         "why-the-t-rex-explained")

    def test_it_stays_short_enough_to_be_a_filename(self):
        self.assertLessEqual(len(capture.slugify("word " * 60)), 60)

    def test_an_empty_headline_falls_back_rather_than_making_a_dotfile(self):
        self.assertEqual(capture.slugify("", "article"), "article")
        self.assertEqual(capture.slugify("!!!", "article"), "article")


class Guards(unittest.TestCase):
    def test_a_non_url_is_refused_before_chrome_launches(self):
        import tempfile
        from pathlib import Path
        for bad in ("", "not a url", "ftp://x/y", "javascript:alert(1)",
                    "file:///etc/passwd"):
            with self.assertRaises(IngestError, msg=bad):
                capture.capture_article(bad, Path(tempfile.mkdtemp()),
                                        log=lambda *a: None)


class ManifestRows(unittest.TestCase):
    def setUp(self):
        import tempfile
        from pathlib import Path
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_a_capture_row_joins_a_manifest_the_fetch_never_wrote(self):
        row = {"id": "CAP1", "file": "a.png", "kind": "citation"}
        man = capture.append_to_manifest(self.tmp, row)
        self.assertEqual(len(man["assets"]), 1)
        self.assertTrue((self.tmp / "assets.json").exists())

    def test_it_joins_stock_already_on_file_without_disturbing_it(self):
        import json
        (self.tmp / "assets.json").write_text(json.dumps(
            {"assets": [{"id": "A1", "file": "clip.mp4", "license": "Pexels"}]}))
        capture.append_to_manifest(self.tmp, {"id": "CAP1", "file": "a.png",
                                              "kind": "citation"})
        man = json.loads((self.tmp / "assets.json").read_text())
        self.assertEqual([a["id"] for a in man["assets"]], ["A1", "CAP1"])
        self.assertEqual(man["assets"][0]["license"], "Pexels")

    def test_recapturing_replaces_rather_than_duplicates(self):
        import json
        row = {"id": "CAP1", "file": "a.png", "kind": "citation",
               "headline": "first"}
        capture.append_to_manifest(self.tmp, row)
        capture.append_to_manifest(self.tmp, dict(row, headline="second"))
        man = json.loads((self.tmp / "assets.json").read_text())
        self.assertEqual(len(man["assets"]), 1)
        self.assertEqual(man["assets"][0]["headline"], "second")

    def test_a_corrupt_manifest_does_not_lose_the_capture(self):
        (self.tmp / "assets.json").write_text("{ not json")
        man = capture.append_to_manifest(self.tmp, {"id": "CAP1",
                                                    "file": "a.png"})
        self.assertEqual(len(man["assets"]), 1)


if __name__ == "__main__":
    unittest.main()


class HeadlineCard(unittest.TestCase):
    """The card is what goes ON SCREEN; the screenshot is the receipt.

    A full-page capture is faithful and full of the publisher's
    navigation and advertising — the TSHA capture has a "SHOP NOW" banner
    in it. The card carries the article's own words at video size, on the
    channel's ground, with the source small and grey underneath.
    """

    ROW = {"file": "a.png", "headline": "History of the Museum",
           "publication": "Texas State Historical Association",
           "published": "2019-04-01T00:00:00Z",
           "source_url": "https://www.tshaonline.org/handbook/entries/x"}

    def html(self, **over):
        return capture._card_html(dict(self.ROW, **over), "a.png")

    def test_it_shows_the_article_s_own_words(self):
        h = self.html()
        self.assertIn("History of the Museum", h)
        self.assertIn("TEXAS STATE HISTORICAL ASSOCIATION", h)

    def test_the_source_line_drops_the_scheme_and_www(self):
        self.assertIn("tshaonline.org/handbook/entries/x", self.html())
        self.assertNotIn("https://www.", self.html())

    def test_only_the_date_survives_a_full_timestamp(self):
        self.assertIn("2019-04-01", self.html())
        self.assertNotIn("T00:00:00Z", self.html())

    def test_a_long_headline_steps_down_rather_than_clipping(self):
        short = self.html(headline="Short one")
        long = self.html(headline="A headline of considerable length " * 6)
        def size(h):
            import re as _re
            return int(_re.search(r"\.head\{[^}]*font-size:(\d+)px", h).group(1))
        self.assertLess(size(long), size(short))

    def test_a_headline_with_markup_is_escaped_not_rendered(self):
        h = self.html(headline='Museum <script>alert(1)</script> "quoted"')
        self.assertNotIn("<script>", h)
        self.assertIn("&lt;script&gt;", h)
        self.assertIn("&quot;quoted&quot;", h)

    def test_a_missing_date_leaves_no_orphan_separator(self):
        self.assertNotIn("·", self.html(published=""))

    def test_the_screenshot_rides_behind_it(self):
        """So the card still looks like a page, not a typed caption."""
        self.assertIn("url('a.png')", self.html())
        self.assertIn("blur(", self.html())

    def test_a_card_is_never_required_for_the_receipt_to_survive(self):
        import tempfile
        from pathlib import Path
        tmp = Path(tempfile.mkdtemp())
        self.assertIsNone(capture.render_card({"file": "missing.png"}, tmp,
                                              log=lambda *a: None))
