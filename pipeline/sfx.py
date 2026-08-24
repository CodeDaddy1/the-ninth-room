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
    # preserve the never-recycle id counter across removals
    nxt = 1
    if p.exists():
        nxt = int(json.loads(p.read_text()).get("next", 1))
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps({"cues": rows, "next": nxt},
                              indent=2, ensure_ascii=False))
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
    p = _cues_path(slug)
    data = json.loads(p.read_text()) if p.exists() else {"cues": []}
    rows = data.get("cues", [])
    # ids NEVER recycle: conform cancels place/remove pairs by cue id, and
    # a reused id pairs a new placement with an old removal (P3 review
    # finding 5) — the counter survives deletions
    n = max([int(data.get("next", 1))] +
            [int(c["id"][2:]) + 1 for c in rows if c["id"].startswith("SC")])
    cue = {"id": "SC%03d" % n, "beat_id": beat_id, "file": file,
           "at_ms": int(at_ms), "gain_db": float(gain_db)}
    rows.append(cue)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps({"cues": rows, "next": n + 1},
                              indent=2, ensure_ascii=False))
    os.replace(tmp, p)
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


# --- music beds (P9, 2026-08-24) -------------------------------------------
# A bed is per CHAPTER: one licensed track under a whole chapter's beats,
# ducked under speech by a deterministic envelope computed from whisper's
# word times — no sidechain guesswork, fully reproducible. Storage:
# work/<slug>/sound.json {"beds": [{"chapter_id", "file", "gain_db"}]}.
# The bed rides the SAME per-beat cue mixer sfx uses, with two extensions
# the renderer understands: src_ms (seek into the track so the music
# continues seamlessly across cuts) and vol_expr (the duck envelope).

BED_DUCK_DB = -18.0   # under speech
BED_UP_DB = -10.0     # in the gaps
BED_RAMP_S = 0.3
BED_GAP_MIN_S = 1.0   # a pause shorter than this never lifts the bed


def _sound_path(slug: str):
    return work_path(slug) / "sound.json"


def beds(slug: str) -> "list":
    p = _sound_path(slug)
    if p.exists():
        return json.loads(p.read_text()).get("beds", [])
    return []


def save_bed(slug: str, chapter_id: str, file: "str | None",
             gain_db: float = 0.0) -> "list":
    """Set or clear one chapter's bed. `file` is brand/sfx-relative and
    must exist (renders never touch the network); None clears."""
    if file is not None and not (SFX_DIR / file).exists():
        raise SfxError("no such track in the library: %s" % file)
    with _SFX_LOCK:
        rows = [b for b in beds(slug) if b.get("chapter_id") != chapter_id]
        if file is not None:
            rows.append({"chapter_id": chapter_id, "file": file,
                         "gain_db": float(gain_db)})
        p = _sound_path(slug)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps({"beds": rows}, indent=2,
                                  ensure_ascii=False))
        os.replace(tmp, p)
        return rows


def duck_expr(gaps: "list", duck_db: float = BED_DUCK_DB,
              up_db: float = BED_UP_DB, ramp: float = BED_RAMP_S) -> str:
    """The ffmpeg volume expression for one beat's duck envelope.

    PURE so the arithmetic is testable: level = duck + (up-duck) *
    coverage(t), where each speech GAP (a, b) contributes a trapezoid
    that ramps over `ramp` seconds and the sum is clamped at 1. With the
    usual 0-3 gaps per beat the expression stays short; a beat with no
    gaps ducks flat and needs no expression at all (caller uses plain
    volume then).
    """
    duck = 10.0 ** (duck_db / 20.0)
    up = 10.0 ** (up_db / 20.0)
    if not gaps:
        return "%.6f" % duck
    terms = []
    for a, b in gaps:
        terms.append("min(1,max(0,(t-%.3f)/%.3f))*min(1,max(0,(%.3f-t)/%.3f))"
                     % (a, ramp, b, ramp))
    coverage = "min(1,%s)" % "+".join(terms)
    return "%.6f+%.6f*%s" % (duck, up - duck, coverage)


def speech_gaps(rel_words: "list", beat_dur: float,
                gap_min: float = BED_GAP_MIN_S) -> "list":
    """PURE: the silences of one beat, in beat-relative seconds, from its
    word times [(s, e), ...] sorted. Head and tail count as gaps too."""
    gaps = []
    cursor = 0.0
    for ws, we in rel_words:
        if ws - cursor >= gap_min:
            gaps.append((cursor, ws))
        cursor = max(cursor, we)
    if beat_dur - cursor >= gap_min:
        gaps.append((cursor, beat_dur))
    return gaps


def bed_cues_by_beat(slug: str) -> "dict":
    """Expand chapter beds into per-beat mixer cues: each beat of a bedded
    chapter gets the track seeked to the beat's offset WITHIN the chapter
    (the music flows across cuts) with its own duck envelope."""
    rows = beds(slug)
    if not rows:
        return {}
    work = work_path(slug)
    out_dir = work / "analysis"
    try:
        tl = json.loads((out_dir / "timeline_map.json").read_text())
        plan = json.loads((work / "edit_plan.json").read_text())
        catalog = json.loads((out_dir / "catalog.json").read_text())
    except (OSError, ValueError):
        return {}
    file_by_name = {f["name"]: f for f in catalog.get("files", [])}
    chapter_of = {b["id"]: b.get("chapter_id") for b in plan.get("beats", [])}
    bed_by_chapter = {b["chapter_id"]: b for b in rows}
    words_cache: "dict" = {}
    out: "dict" = {}
    chapter_clock: "dict" = {}
    for beat in tl.get("beats", []):
        ch = chapter_of.get(beat["id"])
        bed = bed_by_chapter.get(ch)
        dur = beat["record_e"] - beat["record_s"]
        if bed is None:
            continue
        offset = chapter_clock.get(ch, 0.0)
        chapter_clock[ch] = offset + dur
        # beat-relative word spans, mapped through the kept segments
        rel = []
        f = file_by_name.get(beat.get("file"))
        if f and f.get("words_file"):
            wf = f["words_file"]
            if wf not in words_cache:
                try:
                    words_cache[wf] = json.loads(
                        (out_dir / wf).read_text())
                except (OSError, ValueError):
                    words_cache[wf] = []
            acc = 0.0
            for seg in beat.get("segments", []):
                for wd in words_cache[wf]:
                    if seg["src_s"] - 0.05 <= wd["s"] <= seg["src_e"] + 0.05:
                        rel.append((acc + wd["s"] - seg["src_s"],
                                    acc + wd["e"] - seg["src_s"]))
                acc += seg["src_e"] - seg["src_s"]
        gaps = speech_gaps(sorted(rel), dur)
        out.setdefault(beat["id"], []).append({
            "id": "bed-%s" % beat["id"], "beat_id": beat["id"],
            "file": bed["file"], "at_ms": 0,
            "src_ms": int(offset * 1000),
            "dur_ms": int(dur * 1000),
            "gain_db": float(bed.get("gain_db", 0.0)),
            "vol_expr": duck_expr(gaps),
            "kind": "bed",
        })
    return out
