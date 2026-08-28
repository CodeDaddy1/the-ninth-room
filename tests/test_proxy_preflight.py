# -*- coding: utf-8 -*-
"""A master is never built from preview media.

2026-08-27. The Footage desk bakes a 1080p H.264 preview per clip so the
Studio can play footage instantly instead of choking on 4K HEVC. Caleb
asked for those to be linked into Resolve as well, so his hand editing is
as fast as the desk.

Proxy editing is safe only because the software swaps back to the
original at export. Whether the free edition actually does that swap is
UNPROVEN (docs/resolve-findings.md). Until it is proven, a render with
any proxy linked is refused.

The check is on the INPUT, and that is the load-bearing decision: a proxy
and a master are both 1920x1080 H.264 here, so every cheap measurement of
a rendered file agrees and only the pixels differ. There is no reliable
after-the-fact test. Upstream, it is a boolean.

Run: /usr/bin/python3 -m unittest discover -s tests -t .
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline import resolve_api  # noqa: E402
from pipeline.ingest import IngestError  # noqa: E402


class ProxiesLinked(unittest.TestCase):
    def setUp(self):
        self._send = resolve_api.send

    def tearDown(self):
        resolve_api.send = self._send

    def _bridge_says(self, text):
        resolve_api.send = lambda label, lua, **kw: text

    def test_an_untouched_project_reports_nothing(self):
        self._bridge_says("")
        self.assertEqual(resolve_api.proxies_linked(), [])

    def test_it_returns_the_clip_names(self):
        self._bridge_says("A001.MP4\nA002.MP4")
        self.assertEqual(resolve_api.proxies_linked(), ["A001.MP4", "A002.MP4"])

    def test_blank_lines_are_not_clips(self):
        self._bridge_says("\n\nA001.MP4\n\n")
        self.assertEqual(resolve_api.proxies_linked(), ["A001.MP4"])

    def test_it_walks_SUBFOLDERS_too(self):
        """A pool with clips only in the root is not the pool Caleb has."""
        seen = {}

        def spy(label, lua, **kw):
            seen['lua'] = lua
            return ""
        resolve_api.send = spy
        resolve_api.proxies_linked()
        self.assertIn("GetSubFolderList", seen['lua'])

    def test_it_asks_for_the_proxy_path_property(self):
        seen = {}
        resolve_api.send = lambda label, lua, **kw: seen.setdefault('lua', lua) and ""
        resolve_api.proxies_linked()
        self.assertIn("Proxy Media Path", seen['lua'])


class Preflight(unittest.TestCase):
    def setUp(self):
        self._linked = resolve_api.proxies_linked

    def tearDown(self):
        resolve_api.proxies_linked = self._linked

    def _linked_are(self, names):
        resolve_api.proxies_linked = lambda: names

    def test_a_clean_project_passes_silently(self):
        self._linked_are([])
        resolve_api.preflight_no_proxies()   # must not raise

    def test_one_linked_clip_REFUSES(self):
        self._linked_are(["A001.MP4"])
        with self.assertRaises(IngestError) as cm:
            resolve_api.preflight_no_proxies()
        self.assertEqual(cm.exception.code, "proxy_linked")

    def test_the_refusal_NAMES_clips_so_it_can_be_acted_on(self):
        self._linked_are(["A001.MP4", "A002.MP4"])
        with self.assertRaises(IngestError) as cm:
            resolve_api.preflight_no_proxies()
        self.assertIn("A001.MP4", str(cm.exception))

    def test_a_long_list_is_summarised_rather_than_dumped(self):
        self._linked_are(["c%03d.MP4" % i for i in range(200)])
        with self.assertRaises(IngestError) as cm:
            resolve_api.preflight_no_proxies()
        msg = str(cm.exception)
        self.assertIn("200 clips", msg)
        self.assertIn("and 197 more", msg)

    def test_it_says_WHY_not_just_no(self):
        self._linked_are(["A001.MP4"])
        with self.assertRaises(IngestError) as cm:
            resolve_api.preflight_no_proxies()
        self.assertIn("1080p stand-ins", str(cm.exception))

    def test_singular_reads_correctly(self):
        self._linked_are(["A001.MP4"])
        with self.assertRaises(IngestError) as cm:
            resolve_api.preflight_no_proxies()
        self.assertIn("1 clip in Resolve is using", str(cm.exception))

    def test_the_verb_is_named_so_the_message_fits_its_caller(self):
        self._linked_are(["A001.MP4"])
        with self.assertRaises(IngestError) as cm:
            resolve_api.preflight_no_proxies("render the master")
        self.assertIn("before you render the master", str(cm.exception))


class WiredIntoTheRenderPath(unittest.TestCase):
    """A refusal that is not on the path is not a refusal."""

    def test_render_master_calls_it(self):
        import inspect
        from pipeline import deliver
        src = "\n".join(l for l in inspect.getsource(deliver.render_master).splitlines()
                        if not l.strip().startswith(("#", "--")))
        self.assertIn("preflight_no_proxies", src)

    def test_conform_does_NOT_call_it(self):
        """Deliberate. Conform mutates the timeline; it does not bake
        pixels. Blocking it would block the exact hand-editing loop
        proxies exist to enable — link previews to edit, then be unable to
        conform. The guard belongs where the irreversible artifact is
        made, and nowhere else."""
        import inspect
        from pipeline import conform
        self.assertNotIn("preflight_no_proxies", inspect.getsource(conform))
