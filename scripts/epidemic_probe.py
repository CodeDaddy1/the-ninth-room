#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S1 spike: what can Caleb's Epidemic key actually do?

Probes the Partner Content API (bearer = the epidemic_live_ key from .env):
sound-effect search -> download URL -> actual file, plus the music-side
search/download. Prints one line per capability; exits non-zero if the
core pair (search + download) fails. Never prints the key.
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = "https://partner-content-api.epidemicsound.com/v0"


def _key():
    for line in open(os.path.join(ROOT, ".env")):
        line = line.strip()
        for name in ("EPIDEMIC_API_KEY", "EPIDEMIC_SOUND"):
            if line.startswith(name + "="):
                return line.split("=", 1)[1].strip()
    sys.exit("no EPIDEMIC_API_KEY / EPIDEMIC_SOUND in .env")


def call(path, key):
    req = urllib.request.Request(BASE + path, headers={
        "Authorization": "Bearer " + key, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def main():
    key = _key()
    ok = {}

    # --- sound effects: search ---
    try:
        r = call("/sound-effects/search?" + urllib.parse.urlencode(
            {"term": "whoosh", "limit": 3, "sort": "best-match",
             "order": "desc"}), key)
        hits = (r.get("soundEffects") or r.get("tracks")
                or r.get("results") or r.get("items") or [])
        ok["sfx_search"] = hits
        print("sfx search: %d hits | first: %s" % (
            len(hits), json.dumps(hits[0], ensure_ascii=False)[:160] if hits else "-"))
    except urllib.error.HTTPError as e:
        print("sfx search FAILED: HTTP %d %s" % (e.code, e.read()[:120]))
        ok["sfx_search"] = None

    # --- sound effects: download url + real file ---
    if ok.get("sfx_search"):
        sid = ok["sfx_search"][0].get("id")
        try:
            r = call("/sound-effects/%s/download" % sid, key)
            url = r.get("url") or r.get("downloadUrl")
            print("sfx download url: %s… expires=%s" % (
                (url or "-")[:60], r.get("expires", "?")))
            if url:
                with urllib.request.urlopen(url, timeout=60) as f:
                    blob = f.read()
                out = "/tmp/epidemic_probe_sfx"
                open(out, "wb").write(blob)
                print("sfx file: %d bytes -> %s" % (len(blob), out))
                ok["sfx_download"] = True
        except urllib.error.HTTPError as e:
            print("sfx download FAILED: HTTP %d %s" % (e.code, e.read()[:120]))

    # --- sfx categories (the picker's browse tab) ---
    try:
        r = call("/sound-effects/categories", key)
        cats = r.get("categories") or r.get("results") or []
        print("sfx categories: %d | e.g. %s" % (
            len(cats), ", ".join(str(c.get("name", c)) for c in cats[:5])))
    except urllib.error.HTTPError as e:
        print("sfx categories FAILED: HTTP %d" % e.code)

    # --- music: search endpoint shape is undocumented in the guide index;
    #     try the obvious candidates and report which answers ---
    music_hit = None
    for path in ("/search?", "/tracks/search?", "/track-search?"):
        try:
            r = call(path + urllib.parse.urlencode(
                {"term": "adventure", "limit": 2}), key)
            music_hit = (path, r)
            break
        except urllib.error.HTTPError as e:
            if e.code != 404:
                print("music %s -> HTTP %d" % (path, e.code))
    if music_hit:
        path, r = music_hit
        tracks = r.get("tracks") or r.get("results") or []
        print("music search via %s: %d hits | first: %s" % (
            path, len(tracks),
            json.dumps(tracks[0], ensure_ascii=False)[:160] if tracks else "-"))
        if tracks:
            tid = tracks[0].get("id")
            try:
                r = call("/tracks/%s/download?format=mp3&quality=high" % tid, key)
                print("music download url: %s…" % (r.get("url") or "-")[:60])
                ok["music"] = True
            except urllib.error.HTTPError as e:
                print("music download FAILED: HTTP %d %s" % (e.code, e.read()[:120]))
    else:
        print("music search: no candidate endpoint answered (fallback: collections)")
        try:
            r = call("/collections?limit=2&excludeFields=tracks", key)
            print("collections: %s" % json.dumps(r, ensure_ascii=False)[:160])
            ok["music"] = "collections"
        except urllib.error.HTTPError as e:
            print("collections FAILED: HTTP %d" % e.code)

    if not (ok.get("sfx_search") and ok.get("sfx_download")):
        sys.exit("CORE PAIR FAILED — picker needs the manual-pull fallback")
    print("S1: core pair (search+download) PASSES")


if __name__ == "__main__":
    main()
