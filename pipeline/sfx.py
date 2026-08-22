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
# Caleb's key is a SUBSCRIBER key (epidemicsound.com/account/api-keys), which
# authenticates the account MCP service - NOT the partner REST API (that one
# 401s subscriber keys; discovered 2026-08-22). The MCP server is Apollo
# (GraphQL as tools) at /a/mcp-service/mcp: initialize once per process,
# then tools/call SearchSoundEffects / SearchRecordings / DownloadSoundEffect
# / DownloadRecording. Search hits carry a low-quality preview mp3 URL, so
# the desk can audition BEFORE pulling.

EP_MCP = "https://www.epidemicsound.com/a/mcp-service/mcp"
_MCP_LOCK = threading.Lock()
_mcp_session = {"id": None}


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


def _mcp_post(payload: "dict", session: "str | None") -> "tuple":
    """One JSON-RPC POST; returns (parsed data line or None, session id)."""
    headers = {"Authorization": "Bearer " + _ep_key(),
               "Content-Type": "application/json",
               "Accept": "application/json, text/event-stream"}
    if session:
        headers["mcp-session-id"] = session
    req = urllib.request.Request(EP_MCP, json.dumps(payload).encode(), headers)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            sid = r.headers.get("mcp-session-id") or session
            body = r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        if e.code == 401:
            raise SfxError("Epidemic rejected the key (401) - check "
                           "epidemicsound.com/account/api-keys (keys expire "
                           "after one year)")
        raise SfxError("Epidemic MCP HTTP %d" % e.code)
    data = None
    for line in body.splitlines():
        if line.startswith("data: {"):
            data = json.loads(line[6:])
    if data is None and body.strip().startswith("{"):
        data = json.loads(body)
    return data, sid


def _mcp_call(tool: str, arguments: "dict") -> "dict":
    """tools/call with session management; returns the GraphQL data dict."""
    with _MCP_LOCK:
        if not _mcp_session["id"]:
            d, sid = _mcp_post({"jsonrpc": "2.0", "id": 1,
                                "method": "initialize",
                                "params": {"protocolVersion": "2025-03-26",
                                           "capabilities": {},
                                           "clientInfo": {"name": "ninth-room-studio",
                                                          "version": "1.0"}}}, None)
            if not sid:
                raise SfxError("Epidemic MCP gave no session")
            _mcp_session["id"] = sid
            _mcp_post({"jsonrpc": "2.0",
                       "method": "notifications/initialized"}, sid)
        session = _mcp_session["id"]
    d, _ = _mcp_post({"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                      "params": {"name": tool, "arguments": arguments}},
                     session)
    if d is None:
        # session likely expired server-side: re-init once and retry
        with _MCP_LOCK:
            _mcp_session["id"] = None
        return _mcp_call(tool, arguments)
    if "error" in d:
        raise SfxError("Epidemic MCP: %s" % d["error"].get("message", d["error"]))
    content = (d.get("result") or {}).get("content") or []
    if not content:
        raise SfxError("Epidemic MCP returned no content")
    body = json.loads(content[0].get("text") or "{}")
    if body.get("errors"):
        raise SfxError("Epidemic: %s" % body["errors"][0].get("message"))
    return body.get("data") or {}


def ep_search(term: str, kind: str = "sfx", limit: int = 20) -> "list":
    """Search Epidemic; returns [{id, title, length, kind, preview}]."""
    out = []
    if kind == "music":
        data = _mcp_call("SearchRecordings",
                         {"query": {"term": term}, "first": int(limit)})
        for n in (data.get("recordings") or {}).get("nodes") or []:
            r = n.get("recording") or {}
            credits = r.get("credits") or []
            artist = ""
            if credits:
                artist = (credits[0].get("artist") or {}).get("name", "")
            af = r.get("audioFile") or {}
            out.append({"id": r.get("id"),
                        "title": (r.get("title", "") +
                                  (" - " + artist if artist else "")),
                        "length": (af.get("durationInMilliseconds") or 0) / 1000.0,
                        "kind": "music", "preview": af.get("lqmp3Url")})
    else:
        data = _mcp_call("SearchSoundEffects",
                         {"query": {"term": term}, "first": int(limit)})
        for n in (data.get("soundEffects") or {}).get("nodes") or []:
            r = n.get("soundEffect") or {}
            af = r.get("audioFile") or {}
            out.append({"id": r.get("id"), "title": r.get("title", ""),
                        "length": (af.get("durationInMilliseconds") or 0) / 1000.0,
                        "kind": "sfx", "preview": af.get("lqmp3Url")})
    return out


def _find_asset_url(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in ("assetUrl", "url", "downloadUrl") and isinstance(v, str):
                return v
            r = _find_asset_url(v)
            if r:
                return r
    if isinstance(obj, list):
        for it in obj:
            r = _find_asset_url(it)
            if r:
                return r
    return None


def _safe_name(title: str) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "-", title).strip("-").lower()
    return (s[:60] or "sound")


def ep_pull(kind: str, item_id: str, title: str, category: str) -> "dict":
    """Download one Epidemic sound into the library WITH its license row."""
    with _SFX_LOCK:
        return _ep_pull_locked(kind, item_id, title, category)


def _ep_pull_locked(kind, item_id, title, category):
    if kind == "music":
        data = _mcp_call("DownloadRecording",
                         {"id": str(item_id),
                          "options": {"fileType": "MP3", "stemType": "FULL"}})
    else:
        data = _mcp_call("DownloadSoundEffect",
                         {"id": str(item_id), "options": {"fileType": "MP3"}})
    url = _find_asset_url(data)
    if not url:
        raise SfxError("Epidemic returned no download url")
    cat = re.sub(r"[^a-z0-9_-]+", "-", (category or kind).lower()) or kind
    rel = os.path.join(cat, _safe_name(title) + ".mp3")
    dest = SFX_DIR / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=180) as f:
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
