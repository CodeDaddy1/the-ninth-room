# -*- coding: utf-8 -*-
"""The beat-proxy naming convention has exactly one home.

Seven readers globbed `BT*.mp4` by hand: the Review desk's payload, the
poster frame, clean-stale, the Overlays desk, the project row, the
Captions desk, and the retention job's precondition.

That is fine until beats are renamed. The anchor scheme spells a beat
`B-T362`, so every one of those seven finds NOTHING — and not one of them
raises. The Review desk reads zero clips, `_state` drops the project back
to the assembly phase, and retention refuses with "no previews yet". A
migration can be byte-perfect and the project still looks destroyed, with
nothing anywhere naming the cause. It is the worst kind of bug: silent,
total, and blamed on the migration that was actually correct.

So the pattern lives in `beat_identity.PROXY_GLOBS`, the directory read
lives in `beat_identity.beat_proxies`, and this test stops the seventh
hand-rolled copy from coming back.

Run: /usr/bin/python3 -m unittest discover -s tests -t .
"""
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline import beat_identity as bi  # noqa: E402

PIPELINE = Path(__file__).resolve().parent.parent / "pipeline"
# a glob on a literal beat-id prefix, however it is quoted
HAND_ROLLED = re.compile(r"""glob\(\s*['"]BT""")


class OneHomeForTheProxyGlob(unittest.TestCase):

    def test_no_module_globs_beat_proxies_by_hand(self):
        offenders = []
        for f in sorted(PIPELINE.glob("*.py")):
            if f.name == "beat_identity.py":
                continue
            for n, line in enumerate(f.read_text().splitlines(), 1):
                if HAND_ROLLED.search(line):
                    offenders.append("%s:%d %s" % (f.name, n, line.strip()))
        self.assertEqual(offenders, [], "use beat_identity.beat_proxies:\n"
                         + "\n".join(offenders))

    def test_the_ratchet_would_catch_a_regression(self):
        """A ratchet that cannot fail is decoration. Prove the pattern
        matches the exact line the seven sites used to carry."""
        self.assertTrue(HAND_ROLLED.search('for p in pdir.glob("BT*.mp4"):'))
        self.assertTrue(HAND_ROLLED.search("sorted(d.glob('BT*.mp4'))"))


class BothIdErasAreFound(unittest.TestCase):
    """There is no moment when only one spelling is correct: a migration
    renames the beats and the proxies are re-rendered afterwards, so
    every reader in between sees a mixed directory."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def _touch(self, *names):
        for n in names:
            (self.tmp / n).write_bytes(b"x")

    def test_legacy_and_anchor_names_both_come_back(self):
        self._touch("BT01.abc123def456.mp4", "B-T362.abc123def456.mp4",
                    "B-T04-2.abc123def456.mp4")
        self.assertEqual(len(bi.beat_proxies(self.tmp)), 3)

    def test_a_mixed_directory_is_not_deduped_away(self):
        """The two patterns must not both match one file and drop it."""
        self._touch("BT01.a.mp4", "BT02.b.mp4")
        names = [p.name for p in bi.beat_proxies(self.tmp)]
        self.assertEqual(names, ["BT01.a.mp4", "BT02.b.mp4"])

    def test_a_directory_that_does_not_exist_is_empty_not_an_error(self):
        """Every caller was writing this check by hand; the helper owns
        it now, so a project with no proxies dir must not raise."""
        self.assertEqual(bi.beat_proxies(self.tmp / "nope"), [])

    def test_the_temp_file_a_render_is_writing_is_invisible(self):
        """`render_beat` publishes by atomic rename precisely so a
        browser never fetches a half-encoded proxy — that is how BT103
        broke. The glob must not see `_tmp.` either."""
        self._touch("BT01.abc.mp4", "_tmp.BT02.abc.mp4")
        names = [p.name for p in bi.beat_proxies(self.tmp)]
        self.assertEqual(names, ["BT01.abc.mp4"])

    def test_the_beat_id_is_read_off_either_spelling(self):
        self.assertEqual(bi.beat_of_proxy("BT01.abc123.mp4"), "BT01")
        self.assertEqual(bi.beat_of_proxy("B-T362.abc123.mp4"), "B-T362")
        self.assertEqual(bi.beat_of_proxy("B-T04-2.abc123.mp4"), "B-T04-2")

    def test_beat_of_proxy_takes_a_path_or_a_name(self):
        self._touch("B-T99.abc.mp4")
        p = bi.beat_proxies(self.tmp)[0]
        self.assertEqual(bi.beat_of_proxy(p), "B-T99")
        self.assertEqual(bi.beat_of_proxy(p.name), "B-T99")


class ARenameIsNotAReRender(unittest.TestCase):
    """The proxy hash names the PIXELS; the filename names the beat.
    Carrying the id in both meant a pure rename re-rendered every beat it
    touched."""

    def test_the_cache_key_ignores_the_beat_id(self):
        from pipeline import proxy
        beat = {"id": "BT01", "record_s": 4.0, "record_e": 9.0,
                "segments": [{"src_s": 0.0, "src_e": 5.0, "record_s": 4.0}],
                "broll": []}
        renamed = dict(beat, id="B-T362")
        self.assertEqual(proxy._relative_beat(beat),
                         proxy._relative_beat(renamed))

    def test_it_still_notices_a_real_change(self):
        """A key that ignores everything is not a key."""
        from pipeline import proxy
        beat = {"id": "BT01", "record_s": 4.0, "record_e": 9.0,
                "segments": [{"src_s": 0.0, "src_e": 5.0, "record_s": 4.0}],
                "broll": []}
        trimmed = {"id": "BT01", "record_s": 4.0, "record_e": 8.0,
                   "segments": [{"src_s": 0.0, "src_e": 4.0,
                                 "record_s": 4.0}], "broll": []}
        self.assertNotEqual(proxy._relative_beat(beat),
                            proxy._relative_beat(trimmed))


if __name__ == "__main__":
    unittest.main()
