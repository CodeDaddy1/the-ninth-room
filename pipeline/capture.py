# -*- coding: utf-8 -*-
"""Screenshots of the articles a narrated claim rests on.

A VO line that asserts a fact needs something on screen while it is
said, and the honest picture for "a newspaper reported X" is the report
itself — headline, masthead, date. The Johnny Harris study called this
the sourced-quote card: the primary source speaks, subtitled, with a
small attribution line underneath (docs/film-studies/johnny-harris.md).

**A capture is a CITATION, not stock.** Every other asset in this
pipeline arrives with a licence that permits reuse, and
`asset-sourcer.md` refuses anything whose page does not state one — a
rule that would forbid screenshotting a news site, correctly, if a
screenshot were stock. It is not. It is evidence for a claim, shown
briefly, with its source legible in the frame. So captures get their
own kind, are never described as our footage, and record exactly what
was captured and when so a claim can be traced back years later.

What breaks if this is wrong: a fact on screen that nobody can check,
which is the one thing a curiosity channel cannot afford.
"""
from __future__ import annotations

import json
import re
import subprocess
import time
from pathlib import Path

from .graphics import CHROME
from .ingest import IngestError

SHOT_W, SHOT_H = 1600, 1200      # a readable page, not a phone column
CAPTURE_TIMEOUT = 60


def slugify(text: str, fallback: str = "capture") -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return (s[:60] or fallback)


def _read_meta(url: str) -> "dict":
    """Headline, publication and date, straight from the page's own
    metadata. Open Graph first — it is what the publisher chose to be
    quoted as — then the <title>, then nothing rather than a guess.
    """
    js = """
    (() => {
      const m = (p, a) => document.querySelector(`meta[${p}="${a}"]`)?.content || '';
      return JSON.stringify({
        headline: m('property','og:title') || document.title || '',
        publication: m('property','og:site_name') || location.hostname,
        published: m('property','article:published_time') || m('name','date') || '',
        url: location.href,
      });
    })()
    """
    proc = subprocess.run(
        [CHROME, "--headless=new", "--disable-gpu", "--no-sandbox",
         "--virtual-time-budget=8000", "--dump-dom", url],
        capture_output=True, text=True, timeout=CAPTURE_TIMEOUT)
    dom = proc.stdout or ""
    def meta(pattern):
        m = re.search(pattern, dom, re.I)
        return (m.group(1).strip() if m else "")
    headline = (meta(r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)')
                or meta(r"<title[^>]*>([^<]+)</title>"))
    site = (meta(r'<meta[^>]+property=["\']og:site_name["\'][^>]+content=["\']([^"\']+)')
            or re.sub(r"^www\.", "", (re.search(r"https?://([^/]+)", url).group(1)
                                      if re.search(r"https?://([^/]+)", url) else "")))
    published = meta(r'<meta[^>]+property=["\']article:published_time["\'][^>]+content=["\']([^"\']+)')
    _ = js  # the DOM dump is the portable path; the eval form is kept for reference
    return {"headline": headline, "publication": site, "published": published}


def capture_article(url: str, dest_dir: "Path", log=print) -> "dict":
    """Screenshot one article and record what it is.

    Returns a manifest row with `kind: "citation"` — deliberately not
    "image", so nothing downstream can mistake a newspaper for b-roll we
    are free to cut with.
    """
    if not re.match(r"^https?://", url or ""):
        raise IngestError("a capture needs an http(s) URL")
    dest_dir.mkdir(parents=True, exist_ok=True)
    meta = _read_meta(url)
    name = "%s.png" % slugify(meta.get("headline") or url, "article")
    shot = dest_dir / name
    cmd = [CHROME, "--headless=new", "--disable-gpu", "--no-sandbox",
           "--hide-scrollbars", "--force-device-scale-factor=2",
           "--window-size=%d,%d" % (SHOT_W, SHOT_H),
           "--virtual-time-budget=8000",
           "--screenshot=" + str(shot), url]
    err = ""
    for attempt in range(2):
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True,
                                  timeout=CAPTURE_TIMEOUT)
            err = (proc.stderr or "")[-200:]
            if shot.exists() and shot.stat().st_size > 0:
                break
        except subprocess.TimeoutExpired:
            err = "chrome timed out"
    if not shot.exists() or shot.stat().st_size == 0:
        raise IngestError("could not capture %s: %s" % (url, err or "no image"))
    row = {
        "id": "CAP%d" % int(time.time() * 1000 % 10 ** 9),
        "file": name,
        "kind": "citation",
        "what": meta.get("headline") or url,
        "headline": meta.get("headline") or "",
        "publication": meta.get("publication") or "",
        "published": meta.get("published") or "",
        "source_url": url,
        "captured_ts": int(time.time()),
        # NOT a licence. Said plainly so nobody later reads a blank
        # licence field as "unchecked" and goes looking for one.
        "license": "citation — shown as evidence, source visible on screen",
        "attribution": " · ".join(x for x in (meta.get("publication"),
                                              meta.get("headline")) if x),
    }
    log("[capture] %s — %s" % (row["publication"] or "?", row["headline"][:60]))
    return row


def append_to_manifest(assets_dir: "Path", row: "dict") -> "dict":
    """Add a capture to the episode's asset manifest, creating it if the
    fetch phase has not run yet."""
    man_p = assets_dir / "assets.json"
    man = {"assets": []}
    if man_p.exists():
        try:
            man = json.loads(man_p.read_text())
        except ValueError:
            pass
    man.setdefault("assets", [])
    man["assets"] = [a for a in man["assets"] if a.get("id") != row["id"]]
    man["assets"].append(row)
    man_p.write_text(json.dumps(man, indent=1, ensure_ascii=False))
    return man
