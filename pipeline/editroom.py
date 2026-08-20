"""The Edit Room — a local review UI for grading the cut shot by shot.

`/usr/bin/python3 -m pipeline.cli editroom <slug>` starts a localhost server
and prints the URL. The page is a review desk: a sidebar lists every shot
with its status dot, the main pane plays ONE shot at a time — approve or
flag it and the desk auto-advances to the next unreviewed shot, so a full
pass never requires scrolling a wall of cards. Decisions land in
work/<slug>/review.json, which the shot-fixer agent consumes: it patches
exactly the flagged beats, re-proxies them, and resets their status to
"reworked" for re-review. Approved beats are never touched.

Saving: every decision POSTs immediately; notes autosave ~1s after typing
stops and flush on blur/navigate/close (sendBeacon). The header shows the
live save state plus a Save button that flushes anything pending — the
button is reassurance, the autosave is the mechanism.

Serving video correctly matters: the proxy endpoint honors HTTP Range
requests (206) — browsers require ranges to seek, and Safari refuses to
play without them — and sends Cache-Control: no-store so a proxy fetched
mid-render (the BT103 incident) can never stick in the browser cache.

The Overlays desk (second tab, or /#overlays) edits cards with a LIVE
animated preview — the kit is pure CSS, so an <iframe srcdoc> plays the real
animation while you type, no bake needed to look. "Approve & Export" bakes
the ProRes 4444 alpha .mov (cached when unchanged) into
work/<slug>/exports/overlays/ under a human-readable name
(BT04_transition_the-cockrell-butterfly-center.mov) for manual import onto a
Resolve timeline, with Download and Reveal-in-Finder buttons. Editing a
timeline card writes graphics_plan.json through the schema validator (the
2.5s chapter rule gates the form exactly like it gates the pipeline), and
exporting one re-proxies its beat so the Shots desk keeps showing what will
ship — flipping an approved beat back to re-review only when the pixels
actually changed. Custom overlays (not on the timeline) live in
overlays_custom.json and never touch the produce pipeline.

Everything is local and $0: stdlib http.server, no build step, no cloud.
The page is written fresh on every start, so UI changes ship by restarting.

What breaks if this is wrong: review decisions get lost (the one file that
matters is review.json — it is written atomically via replace) or the page
shows stale proxies (the state endpoint re-reads the proxy dir every call,
so a re-render shows up on refresh).
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .ingest import work_path, analysis_dir, IngestError

PORT = 8765
REPO_ROOT = Path(__file__).resolve().parents[1]

# One bake at a time: animate.py already saturates the performance cores per
# card, and two overlapping Chrome fleets would just thrash.
_BAKE_LOCK = threading.Lock()


def _state(slug: str) -> "dict":
    work = work_path(slug)
    out = analysis_dir(slug)
    tl = json.loads((out / "timeline_map.json").read_text())
    plan = json.loads((work / "edit_plan.json").read_text())
    caps = {}
    if (work / "captions.json").exists():
        caps = {c["beat_id"]: c["text"]
                for c in json.loads((work / "captions.json").read_text())["beats"]}
    cards_by_beat: "dict[str, list]" = {}
    if (work / "graphics_plan.json").exists():
        for c in json.loads((work / "graphics_plan.json").read_text())["cards"]:
            cards_by_beat.setdefault(c["beat_id"], []).append(
                {"id": c["id"], "kit": c.get("kit_type", c.get("type")),
                 "copy": c.get("text") or c.get("stat") or c.get("kicker") or ""})
    review = {}
    if (work / "review.json").exists():
        review = json.loads((work / "review.json").read_text())
    proxies = {}
    pdir = work / "proxies"
    if pdir.is_dir():
        for p in pdir.glob("BT*.mp4"):
            # mtime in the URL busts any stale browser-cached copy of a
            # proxy that was later re-rendered under the same name
            proxies[p.name.split(".")[0]] = "%s?v=%d" % (p.name, p.stat().st_mtime)

    plan_by_id = {b["id"]: b for b in plan["beats"]}
    chapters = [{"id": c["id"], "title": c["title"], "beats": []}
                for c in plan.get("chapters", [])]
    ch_index = {c["id"]: c for c in chapters}
    for beat in tl["beats"]:
        pb = plan_by_id.get(beat["id"], {})
        entry = {
            "id": beat["id"],
            "dur": round(beat["record_e"] - beat["record_s"], 1),
            "record_s": round(beat["record_s"], 1),
            "purpose": pb.get("purpose", ""),
            "take": pb.get("take_id", ""),
            "caption": caps.get(beat["id"], ""),
            "cards": cards_by_beat.get(beat["id"], []),
            "broll": [br["clip_id"] for br in pb.get("broll", [])],
            "proxy": proxies.get(beat["id"]),
            "review": review.get(beat["id"], {}),
        }
        ch = ch_index.get(pb.get("chapter_id"))
        (ch["beats"] if ch else chapters[0]["beats"] if chapters else []).append(entry)
    total = len(tl["beats"])
    approved = sum(1 for r in review.values() if r.get("status") == "approved")
    flagged = sum(1 for r in review.values() if r.get("status") == "flagged")
    return {"slug": slug, "chapters": chapters,
            "counts": {"total": total, "approved": approved, "flagged": flagged}}


def _save_review(slug: str, beat_id: str, payload: "dict") -> None:
    work = work_path(slug)
    path = work / "review.json"
    data = json.loads(path.read_text()) if path.exists() else {}
    entry = data.get(beat_id, {})
    # a note-only autosave sends status:null — that must never erase a
    # decision already on file
    if payload.get("status") in ("approved", "flagged", "reworked"):
        entry["status"] = payload["status"]
    if "note" in payload:
        entry["note"] = payload["note"]
    import time
    entry["ts"] = int(time.time())
    data[beat_id] = entry
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2))
    os.replace(tmp, path)


# --- Overlays desk ---------------------------------------------------------
# Cards are edited with a live in-browser preview (the kit is pure CSS, so
# the browser plays the REAL animation — no bake needed to look), and
# "Approve & Export" bakes the ProRes 4444 alpha .mov into
# work/<slug>/exports/overlays/ under a human-readable name for manual
# import onto a Resolve timeline.

# Content fields the editor may change. Identity and placement wiring
# (id, type, kit_type, beat_id, prebaked, animation) stay server-owned.
_EDITABLE = ("kicker", "text", "subtext", "subtext_italic", "emphasis",
             "stat", "attribution", "rows", "entries", "emojis",
             "duration", "at", "size", "speaker",
             "sides", "travel_ms", "accent", "x", "y")

# Starter copy for a freshly created overlay, per kit screen. Keys must be
# names overlay_kit.RENDERERS knows (the big emoji screen is "emoji").
_KIT_TEMPLATES = {
    "lower_third": {"kicker": "True fact", "text": "Your fact goes here"},
    "hook": {"kicker": "The setup", "text": "A headline that opens the loop"},
    "chapter": {"kicker": "Chapter", "text": "Chapter title"},
    "transition": {"kicker": "Next up", "text": "Chapter title"},
    "stat": {"kicker": "By the numbers", "stat": "42",
             "text": "what the number means"},
    "payoff": {"text": "The payoff line, delivered.", "attribution": "Caleb"},
    "vote": {"kicker": "Cast your vote", "text": "Who wins?",
             "rows": [{"label": "Caleb", "value": "0"},
                      {"label": "Alma", "value": "0"},
                      {"label": "Sofia", "value": "0"}]},
    "scoreboard": {"kicker": "Final count",
                   "entries": [{"label": "Sofia", "value": "1", "highlight": True},
                               {"label": "Caleb", "value": "0"}]},
    "stamp": {"text": "Certified weird"},
    "reaction": {"text": "NO WAY.", "attribution": "Sofia"},
    "emoji": {"emojis": [{"char": "😱"}]},
    "watermark": {},
}


def _orientation(slug: str) -> str:
    p = analysis_dir(slug) / "timeline_map.json"
    if p.exists():
        return json.loads(p.read_text()).get("orientation", "landscape")
    return "landscape"


def _write_json(path: Path, data) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    os.replace(tmp, path)


def _custom_path(slug: str) -> Path:
    return work_path(slug) / "overlays_custom.json"


def _load_custom(slug: str) -> "dict":
    p = _custom_path(slug)
    return json.loads(p.read_text()) if p.exists() else {"overlays": []}


def _all_overlays(slug: str) -> "list":
    """Every (card, source) — timeline plan cards first, then customs."""
    out = []
    gp = work_path(slug) / "graphics_plan.json"
    if gp.exists():
        for c in json.loads(gp.read_text())["cards"]:
            out.append((c, "plan"))
    for c in _load_custom(slug)["overlays"]:
        out.append((c, "custom"))
    return out


def _exports_dir(slug: str) -> Path:
    d = work_path(slug) / "exports" / "overlays"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _export_state(slug: str) -> "dict":
    p = work_path(slug) / "exports" / "overlays" / ".export_hashes.json"
    return json.loads(p.read_text()) if p.exists() else {}


def _slugify(text: str, n: int = 36) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return s[:n].rstrip("-") or "overlay"


def _export_name(card: "dict") -> str:
    """BT04_transition_the-cockrell-butterfly-center.mov — beat first so the
    file sorts into timeline order in Finder, then what it is, then what it
    says."""
    from . import graphics
    spec, _ = graphics.bake_spec(card)
    copy = card.get("text") or card.get("stat") or card.get("kicker") or ""
    if not copy and card.get("emojis"):
        copy = "emoji"
    who = card.get("beat_id") or "custom"
    return "%s_%s_%s.mov" % (who, spec.get("kit_type", "card"), _slugify(copy))


def _current_key(slug: str, card: "dict", orient: str) -> str:
    """What must match the export sidecar for the .mov to be 'current'.
    Prebaked effect clips have no kit spec — track the mov file itself."""
    from . import graphics
    if card.get("prebaked"):
        mov = work_path(slug) / "graphics" / (card["id"] + ".mov")
        if not mov.exists():
            return "pre:missing"
        st = mov.stat()
        return "pre:%d:%d" % (int(st.st_mtime), st.st_size)
    return graphics.bake_key(card, orient)


def _overlays_state(slug: str) -> "dict":
    from . import graphics
    orient = _orientation(slug)
    exp = _export_state(slug)
    d = _exports_dir(slug)
    items = []
    for card, source in _all_overlays(slug):
        spec, _ = graphics.bake_spec(card)
        e = exp.get(card["id"]) or {}
        f = e.get("file")
        if f and (d / f).exists():
            status = ("current" if e.get("key") == _current_key(slug, card, orient)
                      else "stale")
        else:
            f, status = None, "none"
        items.append({"id": card["id"], "source": source,
                      "beat": card.get("beat_id"),
                      "kit": "effect" if card.get("prebaked")
                             else spec.get("kit_type"),
                      "prebaked": bool(card.get("prebaked")),
                      "export": {"status": status, "file": f},
                      "card": card})
    return {"slug": slug, "orientation": orient,
            "canvas": list(graphics.CANVAS[orient]),
            "export_dir": str(d), "kits": sorted(_KIT_TEMPLATES),
            "overlays": items}


def _preview_html(card: "dict", w: int, h: int) -> str:
    from . import graphics, overlay_kit
    spec, _ = graphics.bake_spec(card)
    page = overlay_kit.overlay_html(spec, w, h)
    # file:// images (compare / flight_path) are blocked inside an http page;
    # route them through /file so the preview still shows them
    return re.sub(r'file://(/[^"\']+)',
                  lambda m: "/file?p=" + urllib.parse.quote(m.group(1)), page)


def _merge_edits(card: "dict", updates: "dict") -> "dict":
    """Editable fields only; an emptied value removes the key so renderers
    skip the element (a blank subtext must not render an empty chip)."""
    out = dict(card)
    for k in _EDITABLE:
        if k not in updates:
            continue
        v = updates[k]
        if v in ("", None) or v == []:
            if k not in ("duration", "at"):
                out.pop(k, None)
        else:
            out[k] = v
    return out


def _save_overlay(slug: str, card_id: str, updates: "dict") -> "dict":
    """Persist edits; a timeline card re-validates the WHOLE plan (the 2.5s
    chapter rule etc. gate edits exactly like they gate the pipeline)."""
    from . import schemas
    work = work_path(slug)
    gp = work / "graphics_plan.json"
    if gp.exists():
        plan = json.loads(gp.read_text())
        for i, c in enumerate(plan["cards"]):
            if c["id"] == card_id:
                merged = _merge_edits(c, updates)
                plan["cards"][i] = merged
                errors = schemas.validate_graphics_plan(plan)
                if errors:
                    raise IngestError("; ".join(errors))
                _write_json(gp, plan)
                return merged
    custom = _load_custom(slug)
    for i, c in enumerate(custom["overlays"]):
        if c["id"] == card_id:
            merged = _merge_edits(c, updates)
            dur = merged.get("duration")
            if not isinstance(dur, (int, float)) or not 1.0 <= dur <= 15.0:
                raise IngestError("duration must be 1-15s")
            if merged.get("kit_type") in ("chapter", "transition") and dur < 2.5:
                raise IngestError("chapter cards hold at least 2.5s")
            custom["overlays"][i] = merged
            _write_json(_custom_path(slug), custom)
            return merged
    raise IngestError("no overlay '%s'" % card_id)


def _new_overlay(slug: str, kit_type: str) -> "dict":
    if kit_type not in _KIT_TEMPLATES:
        raise IngestError("unknown kit type '%s'" % kit_type)
    custom = _load_custom(slug)
    taken = {c["id"] for c, _ in _all_overlays(slug)}
    n = 1
    while "OV%02d" % n in taken:
        n += 1
    card = {"id": "OV%02d" % n, "kit_type": kit_type,
            "duration": 2.5 if kit_type in ("chapter", "transition") else 3.0}
    card.update(json.loads(json.dumps(_KIT_TEMPLATES[kit_type])))
    custom["overlays"].append(card)
    _write_json(_custom_path(slug), custom)
    return card


def _delete_overlay(slug: str, card_id: str) -> None:
    """Custom overlays only — timeline cards belong to the edit plan."""
    custom = _load_custom(slug)
    keep = [c for c in custom["overlays"] if c["id"] != card_id]
    if len(keep) == len(custom["overlays"]):
        raise IngestError("'%s' is not a custom overlay" % card_id)
    custom["overlays"] = keep
    _write_json(_custom_path(slug), custom)
    exp = _export_state(slug)
    e = exp.pop(card_id, None)
    if e and e.get("file"):
        f = _exports_dir(slug) / e["file"]
        if f.exists():
            f.unlink()
    _write_json(_exports_dir(slug) / ".export_hashes.json", exp)


def _export_overlay(slug: str, card_id: str, log=print) -> "dict":
    """Approve: bake (cached when unchanged) and place the named .mov in
    work/<slug>/exports/overlays/. A timeline card also re-proxies its beat
    so the Shots desk keeps showing what will actually ship."""
    with _BAKE_LOCK:
        from . import graphics
        from . import animate as animate_mod
        from . import proxy as proxy_mod
        cards = {c["id"]: (c, src) for c, src in _all_overlays(slug)}
        if card_id not in cards:
            raise IngestError("no overlay '%s'" % card_id)
        card, source = cards[card_id]
        orient = _orientation(slug)
        w, h = graphics.CANVAS[orient]
        work = work_path(slug)
        d = _exports_dir(slug)
        exp = _export_state(slug)

        name = _export_name(card)
        for oid, e in exp.items():  # two cards can share beat+kit+copy
            if oid != card_id and e.get("file") == name:
                name = "%s_%s" % (card_id, name)
                break
        target = d / name

        if source == "plan":
            mov = work / "graphics" / (card_id + ".mov")
            if card.get("prebaked"):
                if not mov.exists():
                    raise IngestError("prebaked card %s has no %s"
                                      % (card_id, mov.name))
            else:
                graphics.build_cards(slug, orientation=orient,
                                     only_ids=[card_id], log=log)
            tmp = d / ("_tmp.%s" % name)
            shutil.copy2(mov, tmp)
            os.replace(tmp, target)
        else:
            key = _current_key(slug, card, orient)
            if exp.get(card_id, {}).get("key") == key and target.exists():
                log("[export] %s (cached)" % name)
            else:
                spec, preset = graphics.bake_spec(card)
                tmp = d / ("_tmp.%s" % name)
                animate_mod.render_animation(spec, tmp, float(card["duration"]),
                                             w, h, d / "tmp", preset=preset,
                                             log=log)
                os.replace(tmp, target)

        old = exp.get(card_id, {}).get("file")
        if old and old != name and (d / old).exists():
            (d / old).unlink()  # renamed by a copy edit — keep one per card
        exp[card_id] = {"file": name, "key": _current_key(slug, card, orient),
                        "ts": int(time.time())}
        _write_json(d / ".export_hashes.json", exp)
        log("[export] %s -> %s" % (card_id, target))

        result = {"file": name, "path": str(target),
                  "reproxied": False, "review_reset": False}
        if source == "plan" and card.get("beat_id") and not card.get("prebaked"):
            bid = card["beat_id"]
            pdir = work / "proxies"
            before = {p.name: p.stat().st_mtime
                      for p in pdir.glob(bid + ".*.mp4")}
            proxy_mod.build(slug, only_beats=[bid], log=log)
            after = {p.name: p.stat().st_mtime
                     for p in pdir.glob(bid + ".*.mp4")}
            # only an actually-changed proxy invalidates an approval — an
            # export with no edits must not disturb the review
            if before != after:
                result["reproxied"] = True
                rv = work / "review.json"
                if rv.exists():
                    data = json.loads(rv.read_text())
                    if data.get(bid, {}).get("status") == "approved":
                        _save_review(slug, bid, {"status": "reworked"})
                        result["review_reset"] = True
        return result


def serve(slug: str, port: int = PORT, log=print) -> None:
    work = work_path(slug)
    page = PAGE.replace("__SLUG__", slug)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):  # quiet
            pass

        def _send(self, code, body, ctype="application/json"):
            data = body if isinstance(body, bytes) else json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def _send_video(self, p: Path):
            size = p.stat().st_size
            start, end, partial = 0, size - 1, False
            rng = self.headers.get("Range", "")
            if rng.startswith("bytes="):
                spec = rng[6:].split(",")[0].strip()
                s, _, e = spec.partition("-")
                try:
                    if s:
                        start = int(s)
                        if e:
                            end = int(e)
                    elif e:  # suffix form: the last N bytes
                        start = max(size - int(e), 0)
                    partial = True
                except ValueError:
                    start, end, partial = 0, size - 1, False
                end = min(end, size - 1)
            if start > end or start >= size:
                self.send_response(416)
                self.send_header("Content-Range", "bytes */%d" % size)
                self.end_headers()
                return
            with open(p, "rb") as fh:
                fh.seek(start)
                data = fh.read(end - start + 1)
            self.send_response(206 if partial else 200)
            if partial:
                self.send_header("Content-Range",
                                 "bytes %d-%d/%d" % (start, end, size))
            self.send_header("Content-Type", "video/mp4")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            try:
                self.wfile.write(data)
            except (BrokenPipeError, ConnectionResetError):
                pass  # the player aborts range reads constantly; that's normal

        def do_GET(self):
            if self.path in ("/", "/index.html"):
                self._send(200, page.encode(), "text/html; charset=utf-8")
            elif self.path == "/api/state":
                self._send(200, _state(slug))
            elif self.path == "/api/overlays":
                self._send(200, _overlays_state(slug))
            elif self.path.startswith("/proxies/"):
                name = os.path.basename(self.path.split("?")[0])
                p = (work / "proxies" / name).resolve()
                if p.exists() and p.suffix == ".mp4":
                    self._send_video(p)
                else:
                    self._send(404, {"error": "no proxy"})
            elif self.path.startswith("/exports/"):
                name = os.path.basename(self.path.split("?")[0])
                p = work / "exports" / "overlays" / name
                if p.exists() and p.suffix == ".mov":
                    data = p.read_bytes()
                    self.send_response(200)
                    self.send_header("Content-Type", "video/quicktime")
                    self.send_header("Content-Disposition",
                                     'attachment; filename="%s"' % name)
                    self.send_header("Content-Length", str(len(data)))
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                    self.wfile.write(data)
                else:
                    self._send(404, {"error": "no export"})
            elif self.path.startswith("/file?"):
                # preview images only, and only from inside the repo or the
                # slug's work dir — this server is localhost, but stay tight
                qs = urllib.parse.parse_qs(self.path.split("?", 1)[1])
                p = Path(qs.get("p", [""])[0]).resolve()
                allowed = any(str(p).startswith(str(root) + os.sep)
                              for root in (REPO_ROOT, work_path(slug).resolve()))
                if allowed and p.is_file() and p.suffix.lower() in (
                        ".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"):
                    ctype = {"svg": "image/svg+xml"}.get(
                        p.suffix[1:].lower(), "image/" + p.suffix[1:].lower())
                    self._send(200, p.read_bytes(), ctype)
                else:
                    self._send(404, {"error": "not found"})
            else:
                self._send(404, {"error": "not found"})

        def _body(self):
            n = int(self.headers.get("Content-Length") or 0)
            return json.loads(self.rfile.read(n) or b"{}")

        def do_POST(self):
            try:
                self._post()
            except IngestError as e:
                self._send(400, {"error": str(e)})
            except Exception as e:  # a bake crash must reach the UI, not die
                self._send(500, {"error": "%s: %s" % (type(e).__name__, e)})

        def _post(self):
            if self.path == "/api/review":
                body = self._body()
                if not body.get("beat_id"):
                    self._send(400, {"error": "beat_id required"})
                    return
                _save_review(slug, body["beat_id"], body)
                self._send(200, {"ok": True})
            elif self.path == "/api/overlay/html":
                body = self._body()
                html = _preview_html(body["card"],
                                     int(body.get("w", 1920)),
                                     int(body.get("h", 1080)))
                self._send(200, {"html": html})
            elif self.path == "/api/overlay/save":
                body = self._body()
                card = _save_overlay(slug, body["id"], body.get("updates", {}))
                self._send(200, {"ok": True, "card": card})
            elif self.path == "/api/overlay/new":
                body = self._body()
                card = _new_overlay(slug, body.get("kit_type", "lower_third"))
                self._send(200, {"ok": True, "card": card})
            elif self.path == "/api/overlay/delete":
                _delete_overlay(slug, self._body()["id"])
                self._send(200, {"ok": True})
            elif self.path == "/api/overlay/export":
                result = _export_overlay(slug, self._body()["id"], log=log)
                self._send(200, dict(result, ok=True))
            elif self.path == "/api/reveal":
                body = self._body()
                d = _exports_dir(slug)
                p = d / os.path.basename(body["file"]) if body.get("file") else d
                if not p.exists():
                    p = d
                subprocess.run(["open", "-R", str(p)] if p.is_file()
                               else ["open", str(p)])
                self._send(200, {"ok": True})
            else:
                self._send(404, {"error": "not found"})

    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    log("[editroom] http://127.0.0.1:%d  (Ctrl-C to stop)" % port)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


PAGE = r"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Edit Room — __SLUG__</title>
<style>
:root{--accent:#12B76A;--ink:#09090B;--panel:#141416;--panel2:#1C1C1F;
--text:#FCFCFA;--muted:#9A9A94;--hair:#26262A;--flag:#E5484D;--rework:#E8A33D}
*{box-sizing:border-box;margin:0}
html,body{height:100%}
body{background:var(--ink);color:var(--text);display:flex;flex-direction:column;
font-family:Manrope,'Helvetica Neue',sans-serif;font-size:15px;line-height:1.5;
overflow:hidden}
header{background:var(--ink);border-bottom:1px solid var(--hair);
padding:12px 20px;display:flex;align-items:center;gap:16px;flex:none}
h1{font-family:Gabarito,sans-serif;font-size:19px;letter-spacing:-.02em}
.tally{margin-left:auto;display:flex;gap:14px;font-size:13px;color:var(--muted);
white-space:nowrap}
.tally b{color:var(--text);font-variant-numeric:tabular-nums}
.tally .ok b{color:var(--accent)} .tally .fl b{color:var(--flag)}
.save{display:flex;align-items:center;gap:10px}
#saveState{font-size:12.5px;color:var(--muted);white-space:nowrap}
#saveState.err{color:var(--flag)} #saveState.busy{color:var(--rework)}
#saveBtn{font:inherit;font-size:13px;font-weight:700;padding:7px 16px;
border-radius:7px;border:1px solid var(--hair);background:var(--panel2);
color:var(--text);cursor:pointer}
#saveBtn:hover{border-color:var(--accent)}
.bar{height:4px;background:var(--panel2);flex:none}
.bar i{display:block;height:100%;background:var(--accent);transition:width .3s}
.wrap{flex:1;display:grid;grid-template-columns:290px 1fr;min-height:0}
aside{overflow-y:auto;border-right:1px solid var(--hair);padding-bottom:30px}
.chh{position:sticky;top:0;background:var(--ink);z-index:2;
font-family:Gabarito,sans-serif;font-size:12px;letter-spacing:.07em;
text-transform:uppercase;color:var(--muted);padding:12px 14px 6px;
border-bottom:1px solid var(--hair)}
.brow{display:grid;grid-template-columns:12px 50px 1fr auto;gap:9px;
align-items:center;padding:6px 14px 6px 11px;cursor:pointer;
border-left:3px solid transparent;font-size:13px}
.brow:hover{background:var(--panel)}
.brow.cur{background:var(--panel2);border-left-color:var(--accent)}
.dot{width:9px;height:9px;border-radius:50%;border:1.5px solid var(--hair)}
.dot.approved{background:var(--accent);border-color:var(--accent)}
.dot.flagged{background:var(--flag);border-color:var(--flag)}
.dot.reworked{background:var(--rework);border-color:var(--rework)}
.brow .bid{font-family:Gabarito,sans-serif;font-weight:800}
.brow .pu{color:var(--muted);overflow:hidden;text-overflow:ellipsis;
white-space:nowrap;font-size:12px}
.brow .du{color:var(--muted);font-size:11.5px;font-variant-numeric:tabular-nums}
.stage{overflow-y:auto;padding:20px 26px 60px}
.focus{max-width:940px;margin:0 auto;display:flex;flex-direction:column;gap:12px}
.crumb{font-size:13px;color:var(--muted)}
.crumb b{color:var(--text);font-family:Gabarito,sans-serif}
video{width:100%;aspect-ratio:16/9;background:#000;border-radius:12px;
display:block;outline:none}
.noproxy{display:flex;align-items:center;justify-content:center;
aspect-ratio:16/9;background:#000;border-radius:12px;color:var(--muted);
font-size:13px;text-align:center;padding:20px}
.row{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.chip{font-size:11px;letter-spacing:.08em;text-transform:uppercase;
background:var(--panel2);border-radius:4px;padding:3px 8px;color:var(--muted)}
.chip.acc{color:var(--accent)}
.cap{font-size:14px;color:var(--muted);border-left:2px solid var(--hair);
padding-left:12px}
.note{width:100%;background:var(--panel);border:1px solid var(--hair);
border-radius:9px;color:var(--text);padding:10px 12px;font:inherit;
font-size:14px;resize:vertical;min-height:64px}
.note:focus{border-color:var(--accent);outline:none}
.acts{display:flex;gap:10px}
.acts button{flex:1;font:inherit;font-size:15px;font-weight:800;padding:13px 0;
border-radius:9px;border:1px solid var(--hair);background:var(--panel2);
color:var(--text);cursor:pointer;font-family:Gabarito,sans-serif}
.acts button kbd{font-family:inherit;font-size:11px;opacity:.55;font-weight:400;
border:1px solid currentColor;border-radius:4px;padding:0 5px;margin-left:8px}
.acts .ok.on{background:var(--accent);border-color:var(--accent);color:#06110B}
.acts .fl.on{background:var(--flag);border-color:var(--flag)}
.nav{display:flex;gap:10px;align-items:center}
.nav button{font:inherit;font-size:13px;font-weight:700;padding:9px 16px;
border-radius:7px;border:1px solid var(--hair);background:transparent;
color:var(--muted);cursor:pointer}
.nav button:hover{color:var(--text);border-color:var(--muted)}
.nav .nu{margin-left:auto;color:var(--accent);border-color:rgba(18,183,106,.4)}
.nav .nu:hover{border-color:var(--accent);color:var(--accent)}
.done{background:var(--panel);border:1px solid rgba(18,183,106,.5);
border-radius:12px;padding:26px;text-align:center;
font-family:Gabarito,sans-serif;font-size:17px}
.hint{font-size:12px;color:var(--muted);text-align:center}
.hint kbd{border:1px solid var(--hair);border-radius:4px;padding:0 5px;
font-family:inherit}
.tabs{display:flex;gap:4px;background:var(--panel);border:1px solid var(--hair);
border-radius:9px;padding:3px}
.tabs button{font:inherit;font-size:13px;font-weight:700;padding:6px 14px;
border-radius:7px;border:0;background:transparent;color:var(--muted);
cursor:pointer;font-family:Gabarito,sans-serif}
.tabs button.on{background:var(--panel2);color:var(--text)}
.ovnew{margin:12px 14px 4px;display:block;width:calc(100% - 28px);font:inherit;
font-size:13px;font-weight:700;padding:9px 0;border-radius:8px;
border:1px dashed var(--hair);background:transparent;color:var(--muted);
cursor:pointer;font-family:Gabarito,sans-serif}
.ovnew:hover{color:var(--accent);border-color:var(--accent)}
.kitmenu{display:none;flex-wrap:wrap;gap:6px;padding:8px 14px}
.kitmenu.open{display:flex}
.kitmenu button{font:inherit;font-size:12px;padding:5px 10px;border-radius:6px;
border:1px solid var(--hair);background:var(--panel);color:var(--text);
cursor:pointer}
.kitmenu button:hover{border-color:var(--accent)}
.orow{display:grid;grid-template-columns:12px 60px 1fr;gap:9px;
align-items:center;padding:6px 14px 6px 11px;cursor:pointer;
border-left:3px solid transparent;font-size:13px}
.orow:hover{background:var(--panel)}
.orow.cur{background:var(--panel2);border-left-color:var(--accent)}
.orow .oid{font-family:Gabarito,sans-serif;font-weight:800}
.orow .osub{color:var(--muted);overflow:hidden;text-overflow:ellipsis;
white-space:nowrap;font-size:12px}
.dot.current{background:var(--accent);border-color:var(--accent)}
.dot.stale{background:var(--rework);border-color:var(--rework)}
.pvwrap{display:flex;justify-content:center;border-radius:12px;
background:repeating-conic-gradient(#141416 0% 25%,#1d1d21 0% 50%) 0 0/28px 28px}
.pvbox{position:relative;overflow:hidden}
.pvbox iframe{border:0;transform-origin:top left;pointer-events:none;
display:block}
.pvbar{display:flex;gap:10px;align-items:center;font-size:12.5px;
color:var(--muted)}
.pvbar button{font:inherit;font-size:13px;font-weight:700;padding:7px 14px;
border-radius:7px;border:1px solid var(--hair);background:var(--panel2);
color:var(--text);cursor:pointer}
.pvbar button:hover{border-color:var(--accent)}
.fields{display:grid;grid-template-columns:110px 1fr;gap:10px 12px;
align-items:start}
.fields label{font-size:11.5px;letter-spacing:.06em;text-transform:uppercase;
color:var(--muted);font-family:Gabarito,sans-serif;padding-top:10px}
.fields input[type=text],.fields textarea,.fields input[type=number]{
width:100%;background:var(--panel);border:1px solid var(--hair);
border-radius:8px;color:var(--text);padding:8px 10px;font:inherit;font-size:14px}
.fields textarea{resize:vertical;min-height:54px}
.fields textarea.raw{font-family:ui-monospace,Menlo,monospace;font-size:12.5px;
min-height:200px}
.fields textarea.bad{border-color:var(--flag)}
.fields input:focus,.fields textarea:focus{border-color:var(--accent);
outline:none}
.fields .fhint{grid-column:2;font-size:11.5px;color:var(--muted);margin-top:-6px}
.rowed{display:flex;flex-direction:column;gap:6px}
.rowed .rr{display:grid;grid-template-columns:1fr 110px 52px 26px;gap:6px;
align-items:center}
.rowed .rr .win{display:flex;align-items:center;gap:4px;font-size:11px;
color:var(--muted)}
.rowed .rr button{border:1px solid var(--hair);background:transparent;
color:var(--muted);border-radius:6px;cursor:pointer;font-size:14px;padding:4px 0}
.addrow{align-self:flex-start;font:inherit;font-size:12px;
border:1px dashed var(--hair);background:transparent;color:var(--muted);
border-radius:6px;padding:4px 10px;cursor:pointer}
.acts .ex.busy{opacity:.6;pointer-events:none}
.exrow{display:flex;gap:12px;align-items:center;flex-wrap:wrap;font-size:13px;
color:var(--muted)}
.exrow a,.exrow button{font:inherit;font-size:13px;font-weight:700;
padding:7px 14px;border-radius:7px;border:1px solid var(--hair);
background:var(--panel2);color:var(--text);cursor:pointer;text-decoration:none}
.exrow a:hover,.exrow button:hover{border-color:var(--accent)}
.exrow .cur{color:var(--accent)} .exrow .stl{color:var(--rework)}
.badge{font-size:11px;letter-spacing:.07em;text-transform:uppercase;
border-radius:4px;padding:2px 8px;background:var(--panel2);color:var(--rework)}
.del{margin-left:auto;color:var(--flag);background:none;border:none;
cursor:pointer;font:inherit;font-size:12.5px}
#ovmsg{font-size:13px;min-height:18px}
#ovmsg.err{color:var(--flag)} #ovmsg.ok{color:var(--accent)}
</style></head><body>
<header><h1>Edit Room · __SLUG__</h1>
<nav class="tabs"><button id="tabShots" class="on">Shots</button>
<button id="tabOv">Overlays</button></nav>
<div class="tally"><span class="ok">approved <b id="tA">0</b></span>
<span class="fl">flagged <b id="tF">0</b></span>
<span>left <b id="tL">0</b></span></div>
<div class="save"><span id="saveState">All changes saved</span>
<button id="saveBtn">Save</button></div></header>
<div class="bar"><i id="prog" style="width:0"></i></div>
<div class="wrap" id="wrapShots"><aside id="side"></aside>
<section class="stage"><div class="focus" id="focus">loading…</div></section></div>
<div class="wrap" id="wrapOv" style="display:none"><aside id="ovside"></aside>
<section class="stage"><div class="focus" id="ovfocus">loading…</div></section></div>
<script>
const SLUG='__SLUG__', LS='editroom.'+SLUG+'.current';
let S=null, order=[], rows={}, idx=0, dirty={}, timers={};

function esc(s){return (s||'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));}
function fmt(s){return Math.floor(s/60)+':'+String(Math.floor(s%60)).padStart(2,'0');}
function cur(){return order[idx];}
function needsReview(b){const st=b.review.status;return !st||st==='reworked';}

async function boot(){
  S=await (await fetch('/api/state')).json();
  order=[];
  for(const ch of S.chapters)for(const b of ch.beats){b.chapter=ch.title;order.push(b);}
  buildSide();
  const remembered=localStorage.getItem(LS);
  let start=order.findIndex(b=>b.id===remembered);
  if(start<0)start=order.findIndex(needsReview);
  if(start<0)start=0;
  select(start,true);
  counts();
}

function buildSide(){
  const side=document.getElementById('side');side.innerHTML='';
  let i=0;
  for(const ch of S.chapters){
    const h=document.createElement('div');h.className='chh';
    h.textContent=ch.title;side.appendChild(h);
    for(const b of ch.beats){
      const j=i++;
      const r=document.createElement('div');r.className='brow';
      r.innerHTML='<span class="dot"></span><span class="bid">'+b.id+'</span>'+
        '<span class="pu">'+esc(b.purpose)+'</span>'+
        '<span class="du">'+b.dur+'s</span>';
      r.onclick=()=>select(j);
      rows[b.id]=r;side.appendChild(r);patchRow(b);
    }
  }
}

function patchRow(b){
  const d=rows[b.id].querySelector('.dot');
  d.className='dot '+(b.review.status||'');
}

function select(i,first){
  if(!first)flushNote(cur().id);
  idx=i;localStorage.setItem(LS,cur().id);
  renderFocus();
  for(const id in rows)rows[id].classList.toggle('cur',id===cur().id);
  rows[cur().id].scrollIntoView({block:'nearest'});
}

function renderFocus(){
  const b=cur(), f=document.getElementById('focus');
  const st=b.review.status||'';
  const pos=idx+1, T=order.length;
  const vid=b.proxy
    ?'<video id="vid" controls autoplay playsinline src="/proxies/'+b.proxy+'"></video>'
    :'<div class="noproxy">no proxy yet — run:<br>pipeline.cli proxy '+SLUG+' --beat '+b.id+'</div>';
  const cards=b.cards.map(c=>'<span class="chip acc">'+esc(c.kit)+': '+esc(String(c.copy).slice(0,26))+'</span>').join('');
  f.innerHTML=
    '<div class="crumb"><b>'+b.id+'</b> · '+esc(b.chapter)+' · shot '+pos+' of '+T+'</div>'+
    vid+
    '<div class="row"><span class="chip">'+esc(b.purpose)+'</span>'+
    '<span class="chip">'+b.dur+'s @ '+fmt(b.record_s)+'</span>'+
    (b.take?'<span class="chip">'+esc(b.take)+'</span>':'')+
    (b.broll.length?'<span class="chip">b-roll ×'+b.broll.length+'</span>':'')+
    cards+'</div>'+
    (b.caption?'<div class="cap">'+esc(b.caption)+'</div>':'')+
    '<textarea class="note" id="note" placeholder="note for the shot-fixer…">'+
      esc(dirty[b.id]!==undefined?dirty[b.id]:(b.review.note||''))+'</textarea>'+
    '<div class="acts">'+
    '<button class="ok '+(st==='approved'?'on':'')+'" id="bOk">Approve<kbd>A</kbd></button>'+
    '<button class="fl '+(st==='flagged'?'on':'')+'" id="bFl">Flag<kbd>F</kbd></button></div>'+
    '<div class="nav"><button id="bPrev">‹ Prev</button>'+
    '<button id="bNext">Next ›</button>'+
    '<button class="nu" id="bNu">Next unreviewed ↵</button></div>'+
    '<div class="hint"><kbd>A</kbd> approve · <kbd>F</kbd> flag · '+
    '<kbd>←</kbd><kbd>→</kbd> prev/next · <kbd>↵</kbd> next unreviewed · '+
    '<kbd>space</kbd> play/pause</div>';
  const note=document.getElementById('note');
  note.addEventListener('input',()=>queueNote(b.id,note.value));
  note.addEventListener('blur',()=>flushNote(b.id));
  document.getElementById('bOk').onclick=()=>decide('approved');
  document.getElementById('bFl').onclick=()=>decide('flagged');
  document.getElementById('bPrev').onclick=()=>select((idx-1+order.length)%order.length);
  document.getElementById('bNext').onclick=()=>select((idx+1)%order.length);
  document.getElementById('bNu').onclick=gotoUnreviewed;
}

function gotoUnreviewed(){
  const T=order.length;
  for(let k=1;k<=T;k++){
    const j=(idx+k)%T;
    if(needsReview(order[j])){select(j);return;}
  }
  const f=document.getElementById('focus');
  const d=document.createElement('div');d.className='done';
  d.textContent='Every shot is reviewed. Tell Claude to run the shot-fixer on the flags.';
  f.prepend(d);
}

function counts(){
  let A=0,F=0;
  for(const b of order){
    if(b.review.status==='approved')A++;
    else if(b.review.status==='flagged')F++;
  }
  const T=order.length;
  document.getElementById('tA').textContent=A;
  document.getElementById('tF').textContent=F;
  document.getElementById('tL').textContent=T-A-F;
  document.getElementById('prog').style.width=(T?100*(A+F)/T:0)+'%';
}

function setState(txt,cls){
  const el=document.getElementById('saveState');
  el.textContent=txt;el.className=cls||'';
}

async function post(body){
  const r=await fetch('/api/review',{method:'POST',
    headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  if(!r.ok)throw new Error('save failed');
}

function queueNote(id,val){
  dirty[id]=val;
  setState('Unsaved changes…','busy');
  clearTimeout(timers[id]);
  timers[id]=setTimeout(()=>flushNote(id),900);
}

async function flushNote(id){
  if(dirty[id]===undefined)return;
  const b=order.find(x=>x.id===id), note=dirty[id];
  clearTimeout(timers[id]);
  try{
    await post({beat_id:id,status:b.review.status||null,note:note});
    b.review.note=note;
    if(dirty[id]===note)delete dirty[id];
    if(!Object.keys(dirty).length)setSaved();
  }catch(e){
    setState('Save failed — retrying…','err');
    timers[id]=setTimeout(()=>flushNote(id),3000);
  }
}

function setSaved(){
  const t=new Date().toLocaleTimeString([],{hour:'numeric',minute:'2-digit'});
  setState('All changes saved · '+t);
}

async function decide(status){
  const b=cur(), note=document.getElementById('note').value;
  clearTimeout(timers[b.id]);delete dirty[b.id];
  setState('Saving…','busy');
  try{
    await post({beat_id:b.id,status:status,note:note});
    b.review={status:status,note:note};
    patchRow(b);counts();setSaved();
    setTimeout(gotoUnreviewed,150);
  }catch(e){setState('Save failed — click Save to retry','err');}
}

document.getElementById('saveBtn').onclick=async()=>{
  const ids=Object.keys(dirty);
  if(!ids.length){setSaved();return;}
  setState('Saving…','busy');
  for(const id of ids)await flushNote(id);
};

document.addEventListener('keydown',e=>{
  const tag=(e.target.tagName||'').toLowerCase();
  if(tag==='textarea'||tag==='input'){
    if(e.key==='Escape')e.target.blur();
    return;
  }
  if(document.getElementById('wrapOv').style.display!=='none')return;
  if(e.key==='a'||e.key==='A')decide('approved');
  else if(e.key==='f'||e.key==='F')decide('flagged');
  else if(e.key==='ArrowLeft')select((idx-1+order.length)%order.length);
  else if(e.key==='ArrowRight')select((idx+1)%order.length);
  else if(e.key==='Enter')gotoUnreviewed();
  else if(e.key===' '){
    e.preventDefault();
    const v=document.getElementById('vid');
    if(v)v.paused?v.play():v.pause();
  }
});

window.addEventListener('beforeunload',()=>{
  for(const id in dirty){
    const b=order.find(x=>x.id===id);
    navigator.sendBeacon('/api/review',
      JSON.stringify({beat_id:id,status:(b&&b.review.status)||null,note:dirty[id]}));
  }
});

/* ---------------- Overlays desk ---------------- */
let OV=null, ovRows={}, ovId=null, ovWork=null, pvTimer=null, pvHtml='';

// field editors per kit screen: [key, widget]
const KIT_FIELDS={
  hook:[['kicker','text'],['text','area'],['emphasis','emph']],
  chapter:[['kicker','text'],['text','area'],['subtext','text']],
  transition:[['kicker','text'],['text','area']],
  lower_third:[['kicker','text'],['text','area'],['subtext','text'],
               ['subtext_italic','check'],['emphasis','emph']],
  stat:[['kicker','text'],['stat','text'],['text','area']],
  payoff:[['text','area'],['attribution','text'],['emphasis','emph']],
  vote:[['kicker','text'],['text','text'],['rows','rows']],
  scoreboard:[['kicker','text'],['entries','rows']],
  stamp:[['text','text']],
  reaction:[['text','area'],['attribution','text']],
  emoji:[['emojis','emojis']],
  watermark:[],
  caption_plate:[['speaker','text'],['text','area']]
};
const FIELD_HINTS={emphasis:'comma-separated exact phrases to turn amber',
  emojis:'emoji separated by spaces, e.g. 🦕 😱'};

function tab(which){
  const ov=which==='ov';
  document.getElementById('wrapShots').style.display=ov?'none':'';
  document.getElementById('wrapOv').style.display=ov?'':'none';
  document.getElementById('tabShots').classList.toggle('on',!ov);
  document.getElementById('tabOv').classList.toggle('on',ov);
  history.replaceState(null,'',ov?'#overlays':'#');
  if(ov&&!OV)bootOv();
}
if(location.hash==='#overlays')tab('ov');
document.getElementById('tabShots').onclick=()=>tab('shots');
document.getElementById('tabOv').onclick=()=>tab('ov');

function ovItem(id){return OV.overlays.find(o=>o.id===id);}
function ovKit(o){return o.kit||'';}
function ovMsg(txt,cls){const el=document.getElementById('ovmsg');
  if(el){el.textContent=txt||'';el.className=cls||'';}}

async function bootOv(keep){
  OV=await(await fetch('/api/overlays')).json();
  buildOvSide();
  const want=keep||ovId;
  if(want&&ovItem(want))selectOv(want);
  else if(OV.overlays.length)selectOv(OV.overlays[0].id);
  else document.getElementById('ovfocus').innerHTML=
    '<div class="done">No overlays yet — create one with ＋ New overlay.</div>';
}

function buildOvSide(){
  const side=document.getElementById('ovside');side.innerHTML='';ovRows={};
  const nb=document.createElement('button');nb.className='ovnew';
  nb.textContent='＋ New overlay';side.appendChild(nb);
  const menu=document.createElement('div');menu.className='kitmenu';
  for(const k of OV.kits){
    const b=document.createElement('button');b.textContent=k;
    b.onclick=()=>newOverlay(k);menu.appendChild(b);
  }
  side.appendChild(menu);
  nb.onclick=()=>menu.classList.toggle('open');
  const groups=[['On the timeline',OV.overlays.filter(o=>o.source==='plan')],
                ['Custom',OV.overlays.filter(o=>o.source==='custom')]];
  for(const [title,list] of groups){
    if(!list.length)continue;
    const h=document.createElement('div');h.className='chh';
    h.textContent=title;side.appendChild(h);
    for(const o of list){
      const r=document.createElement('div');r.className='orow';
      const copy=o.card.text||o.card.stat||o.card.kicker||'';
      r.innerHTML='<span class="dot"></span><span class="oid">'+o.id+'</span>'+
        '<span class="osub">'+esc((o.beat?o.beat+' · ':'')+ovKit(o)+
        (copy?' · '+String(copy).replace(/\n/g,' ').slice(0,30):''))+'</span>';
      r.onclick=()=>selectOv(o.id);
      ovRows[o.id]=r;side.appendChild(r);patchOvRow(o);
    }
  }
}

function patchOvRow(o){
  const d=ovRows[o.id].querySelector('.dot');
  d.className='dot '+(o.export.status==='current'?'current':
                     o.export.status==='stale'?'stale':'');
}

function selectOv(id){
  ovId=id;
  const o=ovItem(id);
  ovWork=JSON.parse(JSON.stringify(o.card));
  for(const k in ovRows)ovRows[k].classList.toggle('cur',k===id);
  if(ovRows[id])ovRows[id].scrollIntoView({block:'nearest'});
  renderOvFocus();
  if(!o.prebaked)refreshPreview();
}

function ovInput(key,widget){
  const v=ovWork[key];
  if(widget==='area')return '<textarea data-k="'+key+'" data-w="area">'+
    esc(v||'')+'</textarea>';
  if(widget==='check')return '<input type="checkbox" data-k="'+key+
    '" data-w="check"'+((v===undefined||v)?' checked':'')+'>';
  if(widget==='emph')return '<input type="text" data-k="'+key+'" data-w="emph" value="'+
    esc((v||[]).join(', '))+'">';
  if(widget==='emojis')return '<input type="text" data-k="'+key+'" data-w="emojis" value="'+
    esc((v||[]).map(e=>e.char).join(' '))+'">';
  return '<input type="text" data-k="'+key+'" data-w="text" value="'+esc(v||'')+'">';
}

function rowsEditorHtml(key){
  const list=ovWork[key]||[];
  let out='<div class="rowed" id="rowed_'+key+'">';
  list.forEach((r,i)=>{
    out+='<div class="rr">'+
      '<input type="text" data-rk="'+key+'" data-ri="'+i+'" data-rf="label" value="'+esc(r.label||'')+'">'+
      '<input type="text" data-rk="'+key+'" data-ri="'+i+'" data-rf="value" value="'+esc(r.value||'')+'">'+
      '<span class="win"><input type="checkbox" data-rk="'+key+'" data-ri="'+i+
        '" data-rf="highlight"'+(r.highlight?' checked':'')+'>win</span>'+
      '<button data-rdel="'+key+'" data-ri="'+i+'" title="remove">×</button></div>';
  });
  out+='<button class="addrow" data-radd="'+key+'">＋ row</button></div>';
  return out;
}

function renderOvFocus(){
  const o=ovItem(ovId), f=document.getElementById('ovfocus');
  const kit=ovKit(o);
  const crumb='<div class="crumb"><b>'+o.id+'</b> · '+
    (o.beat?esc(o.beat):'custom — not on the timeline')+' · '+esc(kit)+
    (o.prebaked?' <span class="badge">prebaked</span>':'')+'</div>';
  const ex=o.export;
  const exrow='<div class="exrow" id="exrow">'+
    (ex.file
      ?('<span class="'+(ex.status==='current'?'cur':'stl')+'">'+
        (ex.status==='current'?'✓ exported':'⚠ export is stale — re-export')+
        '</span><a href="/exports/'+encodeURIComponent(ex.file)+
        '" download>Download</a>'+
        '<button id="bReveal">Reveal in Finder</button>'+
        '<span>'+esc(ex.file)+'</span>')
      :'<span>not exported yet</span><button id="bFolder">Open export folder</button>')+
    '</div>';
  if(o.prebaked){
    f.innerHTML=crumb+
      '<div class="noproxy">Prebaked effect clip — its pixels are baked footage, '+
      'so there is nothing to edit here. Approve &amp; Export copies the clip '+
      'out under a proper name. Preview it on the Shots desk.</div>'+
      '<div class="acts"><button class="ok ex" id="bExport">Approve &amp; Export .mov</button></div>'+
      exrow+'<div id="ovmsg"></div>';
    wireOvActions(o);return;
  }
  const W=OV.canvas[0],H=OV.canvas[1];
  const scale=Math.min(870/W,500/H);
  const pw=Math.round(W*scale),ph=Math.round(H*scale);
  const fields=KIT_FIELDS[kit];
  let form='';
  if(fields===undefined){
    form='<label>raw json</label><textarea class="raw" id="rawjson">'+
      esc(JSON.stringify(ovWork,null,2))+'</textarea>';
  }else{
    for(const [key,widget] of fields){
      form+='<label>'+esc(key.replace(/_/g,' '))+'</label>'+
        (widget==='rows'?rowsEditorHtml(key):ovInput(key,widget));
      if(FIELD_HINTS[key])form+='<div class="fhint">'+FIELD_HINTS[key]+'</div>';
    }
  }
  form+='<label>duration s</label><input type="number" step="0.1" min="1" max="15" '+
    'data-k="duration" data-w="num" value="'+(ovWork.duration||3)+'">';
  if(o.beat)form+='<label>at s (in beat)</label><input type="number" step="0.1" min="0" '+
    'data-k="at" data-w="num" value="'+(ovWork.at||0)+'">';
  f.innerHTML=crumb+
    '<div class="pvwrap"><div class="pvbox" style="width:'+pw+'px;height:'+ph+'px">'+
    '<iframe id="pvframe" width="'+W+'" height="'+H+
    '" style="transform:scale('+scale+')"></iframe></div></div>'+
    '<div class="pvbar"><button id="bReplay">↺ Replay animation</button>'+
    '<span>live preview — the checkerboard is transparency; edits render as you type</span></div>'+
    '<div class="fields" id="ovform">'+form+'</div>'+
    '<div class="acts"><button id="bSaveOv">Save changes</button>'+
    '<button class="ok ex" id="bExport">Approve &amp; Export .mov</button>'+
    (o.source==='custom'?'<button class="del" id="bDelOv">Delete overlay</button>':'')+
    '</div>'+exrow+'<div id="ovmsg"></div>';
  wireOvForm(o);wireOvActions(o);
}

function wireOvForm(o){
  const form=document.getElementById('ovform');
  if(!form)return;
  const raw=document.getElementById('rawjson');
  if(raw){
    raw.addEventListener('input',()=>{
      try{const j=JSON.parse(raw.value);j.id=o.id;ovWork=j;
        raw.classList.remove('bad');schedulePreview();}
      catch(e){raw.classList.add('bad');}
    });
  }
  form.querySelectorAll('[data-k]').forEach(el=>{
    el.addEventListener('input',()=>{
      const k=el.dataset.k,w=el.dataset.w;
      if(w==='check')ovWork[k]=el.checked;
      else if(w==='num'){const n=parseFloat(el.value);
        if(!isNaN(n))ovWork[k]=n;}
      else if(w==='emph'){
        const list=el.value.split(',').map(s=>s.trim()).filter(Boolean);
        if(list.length)ovWork[k]=list;else delete ovWork[k];}
      else if(w==='emojis'){
        const old=ovWork[k]||[];
        const chars=el.value.split(/\s+/).filter(Boolean);
        ovWork[k]=chars.map((ch,i)=>Object.assign({},old[i]||{},{char:ch}));}
      else{if(el.value==='')delete ovWork[k];else ovWork[k]=el.value;}
      schedulePreview();
    });
  });
  form.querySelectorAll('[data-rk]').forEach(el=>{
    el.addEventListener('input',()=>{
      const k=el.dataset.rk,i=+el.dataset.ri,fld=el.dataset.rf;
      const list=ovWork[k]||(ovWork[k]=[]);
      if(!list[i])list[i]={};
      if(fld==='highlight'){
        if(el.checked)list[i].highlight=true;else delete list[i].highlight;}
      else list[i][fld]=el.value;
      schedulePreview();
    });
  });
  form.querySelectorAll('[data-radd]').forEach(el=>{
    el.onclick=()=>{const k=el.dataset.radd;
      (ovWork[k]||(ovWork[k]=[])).push({label:'',value:'0'});
      redrawRows(k,o);schedulePreview();};
  });
  form.querySelectorAll('[data-rdel]').forEach(el=>{
    el.onclick=()=>{const k=el.dataset.rdel;
      ovWork[k].splice(+el.dataset.ri,1);
      redrawRows(k,o);schedulePreview();};
  });
}

function redrawRows(key,o){
  const holder=document.getElementById('rowed_'+key);
  if(!holder)return;
  holder.outerHTML=rowsEditorHtml(key);
  wireOvForm(o);
}

function wireOvActions(o){
  const rp=document.getElementById('bReplay');
  if(rp)rp.onclick=()=>{const f=document.getElementById('pvframe');
    if(f&&pvHtml)f.srcdoc=pvHtml;};
  const sv=document.getElementById('bSaveOv');
  if(sv)sv.onclick=()=>saveOv(o);
  const exb=document.getElementById('bExport');
  if(exb)exb.onclick=()=>exportOv(o);
  const del=document.getElementById('bDelOv');
  if(del)del.onclick=async()=>{
    if(!confirm('Delete '+o.id+' and its export?'))return;
    await ovPost('/api/overlay/delete',{id:o.id});
    ovId=null;bootOv();
  };
  const rv=document.getElementById('bReveal');
  if(rv)rv.onclick=()=>ovPost('/api/reveal',{file:o.export.file});
  const fo=document.getElementById('bFolder');
  if(fo)fo.onclick=()=>ovPost('/api/reveal',{});
}

async function ovPost(url,body){
  const r=await fetch(url,{method:'POST',
    headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  const j=await r.json();
  if(!r.ok)throw new Error(j.error||'request failed');
  return j;
}

function schedulePreview(){
  clearTimeout(pvTimer);
  pvTimer=setTimeout(refreshPreview,350);
  ovMsg('unsaved edits — Save to keep them, Approve & Export to ship them','');
}

async function refreshPreview(){
  const o=ovItem(ovId);
  if(!o||o.prebaked)return;
  try{
    const j=await ovPost('/api/overlay/html',
      {card:ovWork,w:OV.canvas[0],h:OV.canvas[1]});
    pvHtml=j.html;
    const f=document.getElementById('pvframe');
    if(f)f.srcdoc=pvHtml;
  }catch(e){ovMsg('preview failed: '+e.message,'err');}
}

function ovUpdates(){
  const KEYS=['kicker','text','subtext','subtext_italic','emphasis','stat',
    'attribution','rows','entries','emojis','duration','at','size','speaker',
    'sides','travel_ms','accent','x','y'];
  const u={};
  for(const k of KEYS){
    if(k in ovWork)u[k]=ovWork[k];
    else u[k]='';
  }
  return u;
}

async function saveOv(o,quiet){
  try{
    const j=await ovPost('/api/overlay/save',{id:o.id,updates:ovUpdates()});
    o.card=j.card;ovWork=JSON.parse(JSON.stringify(j.card));
    if(!quiet){ovMsg('saved','ok');bootOv(o.id);}
    return true;
  }catch(e){ovMsg(e.message,'err');return false;}
}

async function exportOv(o){
  const btn=document.getElementById('bExport');
  if(!o.prebaked&&!(await saveOv(o,true)))return;
  btn.classList.add('busy');
  btn.textContent='Baking… (instant if unchanged, ~a minute fresh)';
  ovMsg('rendering the ProRes 4444 alpha .mov…','');
  try{
    const j=await ovPost('/api/overlay/export',{id:o.id});
    let msg='exported '+j.file;
    if(j.reproxied)msg+=' · the '+o.beat+' proxy was refreshed';
    if(j.review_reset)msg+=' and reset to re-review on the Shots desk';
    ovMsg(msg,'ok');
    await bootOv(o.id);
    if(j.reproxied)boot();
  }catch(e){
    ovMsg('export failed: '+e.message,'err');
    btn.classList.remove('busy');
    btn.textContent='Approve & Export .mov';
  }
}

async function newOverlay(kit){
  try{
    const j=await ovPost('/api/overlay/new',{kit_type:kit});
    await bootOv(j.card.id);
  }catch(e){ovMsg(e.message,'err');}
}

boot();
</script></body></html>
"""
