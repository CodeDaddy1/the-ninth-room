#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S1 spike, resolved 2026-08-22: what Caleb's Epidemic key can do.

The key is a SUBSCRIBER key (epidemicsound.com/account/api-keys) — it
authenticates the account MCP service, not the partner REST API (which
401s subscriber keys). This probe exercises the exact calls the desk
uses via pipeline.sfx: sfx search, music search, and a download-URL
fetch. Run it whenever the key is rotated (keys expire after one year).
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pipeline import sfx  # noqa: E402


def main():
    hits = sfx.ep_search("whoosh", "sfx", 3)
    print("sfx search: %d hits | first: %s (%.1fs, preview=%s)"
          % (len(hits), hits[0]["title"], hits[0]["length"],
             "yes" if hits[0].get("preview") else "no"))
    music = sfx.ep_search("adventure", "music", 2)
    print("music search: %d hits | first: %s" % (len(music), music[0]["title"]))
    data = sfx._mcp_call("DownloadSoundEffect",
                         {"id": str(hits[0]["id"]),
                          "options": {"fileType": "MP3"}})
    url = sfx._find_asset_url(data)
    print("download url: %s..." % (url or "-")[:60])
    if not (hits and music and url):
        sys.exit("S1 FAILED")
    print("S1: search + download PASS (both catalogs)")


if __name__ == "__main__":
    main()
