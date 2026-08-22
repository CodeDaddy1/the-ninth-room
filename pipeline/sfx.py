# -*- coding: utf-8 -*-
"""The sound library and its Epidemic Sound tap.

Two truths live here (P2 of the Studio Interactive Suite plan):

- **The library** — ``brand/sfx/<category>/<file>`` plus ``manifest.json``,
  the license ledger. Renders never touch the network: everything the desk
  can place is a file on disk, and every file has a manifest row saying
  where it came from. A pull and its manifest row are ONE operation — a
  sound must never exist in the library without its license row.
- **Placements** — ``work/<slug>/sound_cues.json``: which file plays on
  which beat, when, and how loud. This is deliberately NOT the
  sound-designer's ``sfx_cues.json``, which is a prose cue sheet (advisory
  descriptions, no files); the desk places real audio, the agent suggests.

Epidemic Sound Partner Content API (docs: developers.epidemicsite.com):
bearer = the ``epidemic_live_…`` key from ``.env`` (``EPIDEMIC_API_KEY`` or
``EPIDEMIC_SOUND``). SFX: /sound-effects/search, /sound-effects/{id}/download.
Music: /tracks/search (existence confirmed by 401-not-404 while the key was
still unauthorized), /tracks/{id}/download. Keep this module 3.9-clean.
"""
import json
import os
import re
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from .ingest import PROJECT_ROOT, work_path

SFX_DIR = PROJECT_ROOT / "brand" / "sfx"
MANIFEST = SFX_DIR / "manifest.json"
EP_BASE = "https://partner-content-api.epidemicsound.com/v0"
AUDIO_EXT = (".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac")
# Placement default: sit under the voice, not on top of it (plan decision 06)
DEFAULT_GAIN_DB = -12.0


class SfxError(Exception):
    pass


# One lock for every read-modify-write in this module (manifest and
# sound_cues both): the engine is a ThreadingHTTPServer, and an unlocked
# interleaving loses a cue or replaces a pull's Epidemic license row with
# a re-registered "manual" one (P2 review findings 4 and 6).
_SFX_LOCK = threading.Lock()


# --- the library ----------------------------------------------------------

def _manifest_load() -> "dict":
    if MANIFEST.exists():
        return json.loads(MANIFEST.read_text())
    return {"files": {}}


def _manifest_save(m: "dict") -> None:
    SFX_DIR.mkdir(parents=True, exist_ok=True)
    tmp = MANIFEST.with_suffix(".tmp")
    tmp.write_text(json.dumps(m, indent=2, ensure_ascii=False))
    os.replace(tmp, MANIFEST)


def _probe_len(path) -> float:
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(path)],
            capture_output=True, text=True, timeout=20).stdout.strip()
        return round(float(out), 2)
    except Exception:
        return 0.0


def library() -> "dict":
    with _SFX_LOCK:
        return _library_locked()


def _library_locked() -> "dict":
    """Every sound on disk, by category, joined with its manifest row.

    Lengths are probed once and cached in the manifest — a big library must
    not cost one ffprobe per desk load.
    """
    m = _manifest_load()
    cats = {}
    changed = False
    if SFX_DIR.is_dir():
        for f in sorted(SFX_DIR.rglob("*")):
            if not (f.is_file() and f.suffix.lower() in AUDIO_EXT):
                continue
            rel = str(f.relative_to(SFX_DIR))
            row = m["files"].get(rel)
            if row is None:
                # a hand-dropped file: legal to use (Caleb owns the drop),
                # but the ledger should say it was manual
                row = {"title": f.stem, "source": "manual",
                       "license": "provided by Caleb", "pulled_ts": 0}
                m["files"][rel] = row
                changed = True
            if not row.get("length"):
                row["length"] = _probe_len(f)
                changed = True
            cat = rel.split(os.sep)[0] if os.sep in rel else "uncategorized"
            cats.setdefault(cat, []).append({
                "file": rel, "title": row.get("title", f.stem),
                "length": row.get("length", 0.0),
                "source": row.get("source", "manual"),
                "kind": row.get("kind", "sfx")})
    if changed:
        _manifest_save(m)
    return {"categories": [{"name": k, "sounds": v}
                           for k, v in sorted(cats.items())],
            "dir": str(SFX_DIR)}


# --- Epidemic Sound -------------------------------------------------------

def _ep_key() -> str:
    env = PROJECT_ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            line = line.strip()
            for name in ("EPIDEMIC_API_KEY", "EPIDEMIC_SOUND"):
                if line.startswith(name + "="):
                    key = line.split("=", 1)[1].strip()
                    if key:
                        return key
    raise SfxError("no Epidemic key in .env (EPIDEMIC_API_KEY)")


def _ep_call(path: str) -> "dict":
    req = urllib.request.Request(EP_BASE + path, headers={
        "Authorization": "Bearer " + _ep_key(),
        "Accept": "application/json",
        "x-partner-user-id": "ninth-room-studio"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 401:
            raise SfxError(
                "Epidemic rejected the key (401) — check it in the "
                "Developer Portal, then re-run scripts/epidemic_probe.py")
        raise SfxError("Epidemic HTTP %d on %s" % (e.code, path.split("?")[0]))


def ep_search(term: str, kind: str = "sfx", limit: int = 20) -> "list":
    """Search Epidemic; returns [{id, title, length, kind}]."""
    q = urllib.parse.urlencode({"term": term, "limit": limit,
                                "sort": "best-match", "order": "desc"})
    if kind == "music":
        r = _ep_call("/tracks/search?" + q)
        rows = r.get("tracks") or r.get("results") or []
    else:
        r = _ep_call("/sound-effects/search?" + q)
        rows = (r.get("soundEffects") or r.get("tracks")
                or r.get("results") or [])
    return [{"id": t.get("id"), "title": t.get("title", ""),
             "length": t.get("length", 0), "kind": kind} for t in rows]


def _safe_name(title: str) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "-", title).strip("-").lower()
    return (s[:60] or "sound")


def ep_pull(kind: str, item_id: str, title: str, category: str) -> "dict":
    """Download one Epidemic sound into the library WITH its license row."""
    with _SFX_LOCK:
        return _ep_pull_locked(kind, item_id, title, category)


def _ep_pull_locked(kind, item_id, title, category):
    if kind == "music":
        r = _ep_call("/tracks/%s/download?format=mp3&quality=high"
                     % urllib.parse.quote(str(item_id)))
    else:
        r = _ep_call("/sound-effects/%s/download"
                     % urllib.parse.quote(str(item_id)))
    url = r.get("url") or r.get("downloadUrl")
    if not url:
        raise SfxError("Epidemic returned no download url")
    cat = re.sub(r"[^a-z0-9_-]+", "-", (category or kind).lower()) or kind
    rel = os.path.join(cat, _safe_name(title) + ".mp3")
    dest = SFX_DIR / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=120) as f:
        blob = f.read()
    tmp = dest.with_suffix(".tmp")
    tmp.write_bytes(blob)
    os.replace(tmp, dest)
    m = _manifest_load()
    m["files"][rel] = {
        "title": title, "source": "epidemic", "source_id": str(item_id),
        "kind": kind, "license": "Epidemic Sound subscription",
        "pulled_ts": int(time.time()), "length": _probe_len(dest)}
    _manifest_save(m)
    return {"file": rel, "bytes": len(blob)}


# --- placements -----------------------------------------------------------

def _cues_path(slug: str):
    return work_path(slug) / "sound_cues.json"


def cues(slug: str) -> "list":
    p = _cues_path(slug)
    if p.exists():
        return json.loads(p.read_text()).get("cues", [])
    return []


def _cues_save(slug: str, rows: "list") -> None:
    p = _cues_path(slug)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps({"cues": rows}, indent=2, ensure_ascii=False))
    os.replace(tmp, p)


def place(slug: str, beat_id: str, file: str, at_ms: int,
          gain_db: float = DEFAULT_GAIN_DB) -> "dict":
    """Place a library sound on a beat. at_ms is beat-relative."""
    with _SFX_LOCK:
        return _place_locked(slug, beat_id, file, at_ms, gain_db)


def _place_locked(slug, beat_id, file, at_ms, gain_db):
    src = SFX_DIR / file
    if not (src.is_file() and src.suffix.lower() in AUDIO_EXT):
        raise SfxError("'%s' is not a library sound" % file)
    rows = cues(slug)
    n = 1
    taken = {c["id"] for c in rows}
    while "SC%03d" % n in taken:
        n += 1
    cue = {"id": "SC%03d" % n, "beat_id": beat_id, "file": file,
           "at_ms": int(at_ms), "gain_db": float(gain_db)}
    rows.append(cue)
    _cues_save(slug, rows)
    return cue


def remove(slug: str, cue_id: str) -> "dict":
    with _SFX_LOCK:
        return _remove_locked(slug, cue_id)


def _remove_locked(slug, cue_id):
    rows = cues(slug)
    keep = [c for c in rows if c["id"] != cue_id]
    if len(keep) == len(rows):
        raise SfxError("no cue '%s'" % cue_id)
    gone = [c for c in rows if c["id"] == cue_id][0]
    _cues_save(slug, keep)
    return gone


def cues_by_beat(slug: str) -> "dict":
    out = {}
    for c in cues(slug):
        out.setdefault(c["beat_id"], []).append(c)
    return out
