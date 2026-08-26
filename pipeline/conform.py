# -*- coding: utf-8 -*-
"""Conform: push the desk's batched edits into the Resolve timeline.

Two stages (plan decision 10 + the Complete Suite Audit's G1 amendment):

1. **Export the stale set.** Every card whose bake key moved since its last
   export re-bakes; each fresh export appends its own card_place /
   card_replace op to the ledger (editroom._export_overlay does that).
2. **Execute the ledger** through the bridge, one op at a time, additive
   inserts and clip replacements ONLY — restructures stay agent territory:
   - card_replace: find the placed item at its synced record position on
     its synced track, ReplaceClip to the new export file.
   - card_place / sfx_place / broll_attach: AppendToTimeline at the exact
     record frame (S3 spike: works in free Resolve, audio via mediaType 2).
   - sfx_remove / broll_remove: find the item by position + basename,
     DeleteClips.

Runs as a background thread with a polled status file — a conform can take
many minutes (33 stale exports at UHD) and one long POST would trip the
proxy's timeout and the ECONNRESET race (P2 review finding 14). Successful
ops leave the ledger; failed ops stay with their error so nothing is
silently dropped. Ends with a timeline re-sync and a project save.
"""
import json
import os
import threading
import time

from .ingest import work_path

_RUN_LOCK = threading.Lock()
_running = {}


def _lua_safe(text):
    """Strings are %-interpolated into single-quoted Lua and the bridge
    forbids backslash escapes — a quote or newline cannot be escaped, only
    refused (finding 11: an apostrophe in a renamed project would turn
    every op into a Lua syntax error)."""
    t = str(text)
    if "'" in t or "\n" in t or "\\" in t:
        raise RuntimeError("name not usable over the bridge (quote/backslash): %r" % t)
    return t


class ConformBusy(Exception):
    pass


def _status_path(slug):
    return work_path(slug) / "conform_status.json"


def _write_status(slug, st):
    p = _status_path(slug)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(st, indent=2))
    os.replace(tmp, p)


def status(slug: str) -> "dict":
    p = _status_path(slug)
    if not p.exists():
        return {"state": "idle"}
    st = json.loads(p.read_text())
    # an engine restart kills the conform thread but not its status file —
    # a ghost "running" would block re-runs forever (same guard jobs.py
    # carries; bitten live 2026-08-23)
    if st.get("state") == "running" and not _running.get(slug):
        st.update({"state": "failed",
                   "error": "engine restarted mid-conform — run it again"})
        _write_status(slug, st)
    return st


def start(slug: str) -> None:
    """Kick off a conform in a background thread; one per slug at a time.
    Refused while a render job runs — conform ops would edit the very
    timeline Resolve is rendering (P5 review F10)."""
    from . import jobs as jobs_mod, resolve_api
    if any(j["kind"] == "render" and j["state"] in ("queued", "running")
           for j in jobs_mod.jobs()):
        raise ConformBusy("a master render is running — conform after it")
    # the ledger forgets across an engine restart; Resolve does not (F1)
    if resolve_api.rendering_in_progress():
        raise ConformBusy("Resolve is rendering — conform after it finishes")
    with _RUN_LOCK:
        if _running.get(slug):
            raise ConformBusy("a conform is already running for %s" % slug)
        _running[slug] = True
    t = threading.Thread(target=_run_guarded, args=(slug,), daemon=True)
    t.start()


def _run_guarded(slug):
    try:
        _run(slug)
    except Exception as e:  # status must reflect a crash, never hang
        st = status(slug)
        st.update({"state": "failed", "error": "%s: %s" % (type(e).__name__, e)})
        _write_status(slug, st)
    finally:
        with _RUN_LOCK:
            _running[slug] = False


def _stale_cards(slug):
    from . import editroom
    exp = editroom._export_state(slug)
    orient = editroom._orientation(slug)
    out = []
    for card, _src in editroom._all_overlays(slug):
        prev = exp.get(card["id"])
        if not prev or prev.get("key") != editroom._current_key(slug, card, orient):
            out.append(card["id"])
    return out


def _stem(name):
    """BT56_stamp_x_v5.mov -> stamp_x — the family that survives BOTH a
    version bump and a re-home (the beat prefix changes when a card moves
    beats, and the old clip in Resolve wears the old beat's name)."""
    import re
    n = re.sub(r"(_v\d+)?\.mov$", "", name)
    return re.sub(r"^(BT\d+|custom)_", "", n)


def _pair_key(o):
    p = o["payload"]
    if o["op"].startswith("sfx_"):
        return ("sfx", p.get("id"))
    return ("broll", p.get("file"), round(float(p.get("record_s", -1)), 2),
            round(float(p.get("src_s", 0)), 2), round(float(p.get("duration", 0)), 2))


def _op_detail(o):
    """One human label for a queued op, used by BOTH the pending preview and
    the running status panel — the desk must never describe the same op two
    different ways. Card ops carry no beat_id (a card is addressed by
    card_id), which is why a bare "card place" told Caleb nothing.
    """
    p = o.get("payload") or {}
    bits = []
    if p.get("card_id"):
        bits.append(str(p["card_id"]))
    if p.get("file"):
        bits.append(os.path.basename(str(p["file"])))
    return " \u00b7 ".join(bits) or o.get("beat_id", "")


def _collapse_ops(ops):
    """A place later removed cancels (sfx by cue id, b-roll by file +
    record position); repeated card exports keep only the last."""
    out = []
    removes = {_pair_key(o) for o in ops
               if o["op"] in ("sfx_remove", "broll_remove")}
    places = {_pair_key(o) for o in ops
              if o["op"] in ("sfx_place", "broll_attach")}
    latest_card = {}
    for o in ops:
        if o["op"] in ("card_place", "card_replace"):
            latest_card[o["payload"]["card_id"]] = o
    seen_cards = set()
    for o in ops:
        op = o["op"]
        if op in ("sfx_place", "broll_attach") and _pair_key(o) in removes:
            continue
        if op in ("sfx_remove", "broll_remove") and _pair_key(o) in places:
            continue  # its counterpart place was dropped above
        if op in ("card_place", "card_replace"):
            cid = o["payload"]["card_id"]
            if cid in seen_cards or latest_card[cid] is not o:
                continue
            seen_cards.add(cid)
        out.append(o)
    return out


def _beat_starts(slug):
    tm = json.loads((work_path(slug) / "analysis" /
                     "timeline_map.json").read_text())
    return {b["id"]: b["record_s"] for b in tm["beats"]}


def _run(slug):
    from . import editroom, resolve_api, sfx as sfx_mod
    work = work_path(slug)
    st = {"state": "running", "stage": "export", "started_ts": int(time.time()),
          "exported": 0, "export_total": 0, "ops": []}
    _write_status(slug, st)

    # --- stage 1: export everything stale --------------------------------
    stale = _stale_cards(slug)
    st["export_total"] = len(stale)
    _write_status(slug, st)
    st["export_failures"] = []
    for cid in stale:
        try:
            editroom._export_overlay(slug, cid, log=lambda *a: None)
        except Exception as e:
            st["export_failures"].append({"card": cid, "error": str(e)[:200]})
        st["exported"] += 1
        _write_status(slug, st)

    # --- stage 2: the ledger via the bridge ------------------------------
    st["stage"] = "push"
    _write_status(slug, st)
    raw_ops = editroom._conform_pending(slug)
    ops = _collapse_ops(raw_ops)
    if not ops:
        # the version is HELD, not omitted. This is the commonest outcome —
        # everything collapsed away — and a missing key made
        # `status.version` read `undefined` on exactly the run where the
        # existing value is the right answer (review, 2026-08-26).
        from . import facts as facts_mod
        st.update({"state": "done", "stage": "done",
                   "version": facts_mod.timeline_version(slug)})
        _write_status(slug, st)
        return

    tc_path = work / "timeline_cards.json"
    tc = json.loads(tc_path.read_text()) if tc_path.exists() else {}
    meta_project = tc.get("project")
    meta_timeline = tc.get("timeline")
    if not (meta_project and meta_timeline):
        raise RuntimeError("no timeline sync on file — run Sync from Resolve once first")
    placed = tc.get("cards", {})
    beat_start = _beat_starts(slug)
    exports_dir = str(work / "exports" / "overlays")
    footage_dir = str(work / "footage")

    resolve_api.ensure_bridge()
    # authoritative re-check now the handle is live: the passive guard in
    # start() cannot see past a stale handle, and mutating a rendering
    # timeline cancels the render (audit F1)
    if resolve_api.rendering_in_progress():
        raise RuntimeError("Resolve is rendering — conform after it finishes")
    # one prelude: right project + timeline, remember start frame; a fresh
    # audio track hosts this run's sfx placements
    prelude = resolve_api.send("conform-pre", """
local pm = resolve:GetProjectManager()
local proj = pm:GetCurrentProject()
if proj == nil or proj:GetName() ~= '%(proj)s' then proj = pm:LoadProject('%(proj)s') end
if proj == nil then return 'ERR|cannot load %(proj)s' end
local tl = proj:GetCurrentTimeline()
if tl == nil or tl:GetName() ~= '%(tl)s' then
  local mp = proj:GetMediaPool()
  for i = 1, proj:GetTimelineCount() do
    local t = proj:GetTimelineByIndex(i)
    if t:GetName() == '%(tl)s' then proj:SetCurrentTimeline(t); tl = t; break end
  end
end
if tl == nil or tl:GetName() ~= '%(tl)s' then return 'ERR|timeline %(tl)s not found' end
return 'OK|' .. tostring(tl:GetStartFrame()) .. '|' .. tostring(proj:GetSetting('timelineFrameRate')) .. '|' .. tostring(tl:GetTrackCount('audio'))
""" % {"proj": _lua_safe(meta_project), "tl": _lua_safe(meta_timeline)}, timeout=180)
    if prelude.startswith("ERR|"):
        raise RuntimeError(prelude[4:])
    # RE-SYNC before trusting any placed position: card_replace probes the
    # timeline at the SYNCED record_s, and a sync from yesterday targets
    # wherever clips used to be (round-2 audit — the file was 21.6h old on
    # the first real run's eve). The right project/timeline is current now,
    # so this reads the truth of this minute.
    st["stage"] = "sync"
    _write_status(slug, st)
    editroom._sync_timeline_cards(slug)
    tc = json.loads(tc_path.read_text())
    placed = tc.get("cards", {})
    st["stage"] = "push"
    _write_status(slug, st)
    _, tl_start_s, fps_s, _n_audio = prelude.split("|")
    tl_start = int(float(tl_start_s))
    # the REAL timeline rate (23.976 on hmns) — a hardcoded 24 drifted
    # placements ~18 frames by the episode's end (P3 review finding 1)
    fps = float(fps_s) or 24.0
    sfx_track = [None]  # created lazily on first sfx_place

    def frame(sec):
        return tl_start + int(round(float(sec) * fps))

    for i, o in enumerate(ops):
        op, payload, bid = o["op"], o["payload"], o.get("beat_id", "")
        entry = {"op": op, "beat_id": bid, "result": "pending",
                 "detail": _op_detail(o)}
        st["ops"].append(entry)
        _write_status(slug, st)
        try:
            if op in ("card_place", "card_replace"):
                all_cards = {c["id"] for c, _s in editroom._all_overlays(slug)}
                if payload.get("card_id") not in all_cards:
                    # the card was deleted after this op queued (the BT80
                    # test-card cleanup) — a ghost op must clear, not
                    # re-queue as a failure forever
                    entry["result"] = "skipped"
                    entry["note"] = "card deleted — op dropped"
                    _write_status(slug, st)
                    continue
            if op == "card_place" and payload.get("card_id") in placed:
                # placed by hand (and synced) since the export queued this —
                # a second copy on V3 would be worse than a swap
                op = "card_replace"
            if op == "card_replace":
                cid = payload["card_id"]
                info = placed.get(cid)
                if not info:
                    # the sync maps clips by export basename; a re-homed or
                    # renamed card's old-named clip drops out of the sync
                    # (2026-08-23: three re-homed cards). Fall back to the
                    # card's KNOWN position — after ReplaceClip the next
                    # sync re-learns the new name, so this self-heals.
                    card = {c["id"]: c for c, _s in
                            editroom._all_overlays(slug)}.get(cid, {})
                    if card.get("beat_id") and card["beat_id"] in beat_start:
                        info = {"record_s": beat_start[card["beat_id"]]
                                + float(card.get("at", 0)),
                                "track": None}
                    else:
                        raise RuntimeError(
                            "card %s not in the timeline sync and has no "
                            "beat position to fall back to" % cid)
                track_idx = (int(str(info["track"]).lstrip("V") or 3)
                             if info.get("track") else None)
                target_frame = frame(info["record_s"])
                if track_idx is not None:
                    track_expr = "{%d}" % track_idx
                else:
                    # position fallback: probe every video track, but only
                    # accept an item whose media is one of OURS (a card
                    # export or a kit bake) — never replace footage
                    track_expr = ("(function() local ts = {} for t = 1, "
                                  "tl:GetTrackCount('video') do ts[#ts+1] = t "
                                  "end return ts end)()")
                out = resolve_api.send("conform-op%d" % i, """%(binhelper)s
local tl = resolve:GetProjectManager():GetCurrentProject():GetCurrentTimeline()
local mp = resolve:GetProjectManager():GetCurrentProject():GetMediaPool()
for _, t in ipairs(%(tracks)s) do
  for _, it in ipairs(tl:GetItemListInTrack('video', t) or {}) do
    if it:GetStart() <= %(f)d and it:GetEnd() > %(f)d then
      local mpi = it:GetMediaPoolItem()
      if mpi ~= nil then
        local fp = mpi:GetClipProperty('File Path') or ''
        if string.find(fp, '/exports/overlays/', 1, true) or string.find(fp, '/graphics/', 1, true) then
          local ok = mpi:ReplaceClip('%(path)s')
          return 'OK|replaced=' .. tostring(ok) .. ' on V' .. tostring(t)
        end
      end
    end
  end
end
-- not at its position: the card was re-homed. Find its clip ANYWHERE by the
-- version-stripped name family and MOVE it here; nowhere at all -> insert.
local stem = '%(stem)s'
for t = 1, tl:GetTrackCount('video') do
  for _, it in ipairs(tl:GetItemListInTrack('video', t) or {}) do
    local mpi = it:GetMediaPoolItem()
    if mpi ~= nil then
      local fp = mpi:GetClipProperty('File Path') or ''
      if string.find(fp, '/exports/overlays/', 1, true) and string.find(fp, stem, 1, true) then
        local dur = it:GetEnd() - it:GetStart()
        tl:DeleteClips({it})
        -- swap the media on the SAME pool item, then re-place it: no
        -- import ambiguity, and every other timeline use follows too
        mpi:ReplaceClip('%(path)s')
        local placed2 = mp:AppendToTimeline({{mediaPoolItem = mpi, startFrame = 0, endFrame = dur - 1, trackIndex = t, recordFrame = %(f0)d}})
        if placed2 == nil or #placed2 == 0 then return 'ERR|move: reinsert failed' end
        return 'OK|moved from V' .. tostring(t) .. ' to frame %(f0)d'
      end
    end
  end
end
local imported = _nr_import(mp, '%(bin)s', {'%(path)s'})
if imported == nil or #imported == 0 then return 'ERR|insert: import failed' end
local placed3 = mp:AppendToTimeline({{mediaPoolItem = imported[1], startFrame = 0, endFrame = %(durf)d, trackIndex = 3, recordFrame = %(f0)d}})
if placed3 == nil or #placed3 == 0 then return 'ERR|insert failed' end
return 'OK|inserted at frame %(f0)d on V3'
""" % {"tracks": track_expr, "f": target_frame + 1, "f0": target_frame,
       "stem": _lua_safe(_stem(payload["file"])),
       "durf": max(1, int(round(float(
           ({c["id"]: c for c, _s in editroom._all_overlays(slug)}
            .get(payload["card_id"], {}).get("duration", 3))) * fps)) - 1),
       "binhelper": resolve_api.LUA_BIN_IMPORT,
       "bin": _lua_safe(resolve_api.BIN_OVERLAYS),
       "path": _lua_safe(exports_dir + "/" + payload["file"])}, timeout=180)
            elif op in ("card_place", "sfx_place", "broll_attach"):
                if op == "card_place":
                    cid = payload["card_id"]
                    card = {c["id"]: c for c, _s in editroom._all_overlays(slug)}[cid]
                    if not card.get("beat_id"):
                        raise RuntimeError("card %s has no beat — place it in Resolve by hand" % cid)
                    abs_s = beat_start[card["beat_id"]] + float(card.get("at", 0))
                    dur_frames = int(round(float(card["duration"]) * fps))
                    path = exports_dir + "/" + payload["file"]
                    track_expr = "3"
                    media_type = ""
                elif op == "sfx_place":
                    abs_s = beat_start[bid] + payload["at_ms"] / 1000.0
                    row = sfx_mod._manifest_load()["files"].get(payload["file"], {})
                    path = str(sfx_mod.SFX_DIR / payload["file"])
                    length_s = float(row.get("length") or 0) or sfx_mod._probe_len(path) or 1.0
                    dur_frames = max(1, int(round(length_s * fps)))
                    track_expr = "SFXTRACK"
                    media_type = ", mediaType = 2"
                else:  # broll_attach
                    abs_s = float(payload["record_s"])
                    dur_frames = int(round(float(payload["duration"]) * fps))
                    path = footage_dir + "/" + payload["file"]
                    track_expr = "2"
                    media_type = ""
                start_frame = 0 if op != "broll_attach" else int(round(float(payload.get("src_s", 0)) * fps))
                mk_track = ""
                if track_expr == "SFXTRACK":
                    if sfx_track[0] is None:
                        mk_track = "tl:AddTrack('audio')\n"
                        sfx_track[0] = "made"
                    track_expr = "tl:GetTrackCount('audio')"
                # a card belongs with the cards, a sound with the sounds --
                # the destination follows the op, not the pool selection
                bin_name = (resolve_api.BIN_OVERLAYS if op == "card_place"
                            else resolve_api.BIN_SFX if op == "sfx_place"
                            else resolve_api.BIN_BROLL)
                out = resolve_api.send("conform-op%d" % i, """%(binhelper)s
local proj = resolve:GetProjectManager():GetCurrentProject()
local mp = proj:GetMediaPool()
local tl = proj:GetCurrentTimeline()
%(mk_track)slocal clip = nil
local base = '%(base)s'
local function scan(folder)
  for _, c in ipairs(folder:GetClipList() or {}) do
    local p = c:GetClipProperty('File Path') or ''
    if string.sub(p, -string.len(base)) == base then return c end
  end
  for _, sub in ipairs(folder:GetSubFolderList() or {}) do
    local r = scan(sub)
    if r then return r end
  end
  return nil
end
clip = scan(mp:GetRootFolder())
if clip == nil then
  local imported = _nr_import(mp, '%(bin)s', {'%(path)s'})
  if imported == nil or #imported == 0 then return 'ERR|import failed' end
  clip = imported[1]
end
local items = mp:AppendToTimeline({{mediaPoolItem = clip, startFrame = %(sf)d, endFrame = %(ef)d, trackIndex = %(track)s, recordFrame = %(rf)d%(mt)s}})
if items == nil or #items == 0 then return 'ERR|append failed' end
return 'OK|placed@' .. tostring(items[1]:GetStart())
""" % {"mk_track": mk_track, "base": _lua_safe(os.path.basename(path)),
       "path": _lua_safe(path),
       "binhelper": resolve_api.LUA_BIN_IMPORT,
       "bin": _lua_safe(bin_name),
       "sf": start_frame, "ef": start_frame + dur_frames - 1,
       "track": track_expr, "rf": frame(abs_s), "mt": media_type},
                    timeout=180)
            elif op in ("sfx_remove", "broll_remove"):
                if op == "sfx_remove":
                    abs_s = beat_start.get(bid, 0) + payload["at_ms"] / 1000.0
                    kind, base = "audio", os.path.basename(payload["file"])
                else:
                    abs_s = float(payload["record_s"])
                    kind, base = "video", os.path.basename(payload["file"])
                out = resolve_api.send("conform-op%d" % i, """
local tl = resolve:GetProjectManager():GetCurrentProject():GetCurrentTimeline()
for t = 1, tl:GetTrackCount('%(kind)s') do
  for _, it in ipairs(tl:GetItemListInTrack('%(kind)s', t) or {}) do
    if it:GetStart() <= %(f)d and it:GetEnd() > %(f)d and string.find(it:GetName(), '%(base)s', 1, true) then
      local ok = tl:DeleteClips({it})
      return 'OK|deleted=' .. tostring(ok)
    end
  end
end
return 'ERR|no %(kind)s item named %(base)s at frame %(f)d'
""" % {"kind": kind, "f": frame(abs_s) + 1, "base": _lua_safe(base)}, timeout=120)
            else:
                raise RuntimeError("unknown op %s" % op)
            if out.startswith("ERR|"):
                raise RuntimeError(out[4:])
            entry["result"] = "done"
            entry["note"] = out[3:]
        except Exception as e:
            entry["result"] = "failed"
            entry["note"] = str(e)[:200]
        _write_status(slug, st)

    # --- wrap up: save, re-sync, clear the executed ops ------------------
    resolve_api.send("conform-save", """
resolve:GetProjectManager():SaveProject()
return 'saved'
""", timeout=120)
    try:
        editroom._sync_timeline_cards(slug)
    except Exception:
        pass
    failed_ops = [o for o, e in zip(ops, st["ops"]) if e["result"] == "failed"]
    with editroom._CONFORM_LOCK:
        # everything read at stage-2 start clears — executed, failed (they
        # re-queue below), and collapsed-away pairs alike (finding 2: those
        # never cleared and the count could never reach zero again)
        fresh = editroom._conform_pending(slug)
        remaining = [o for o in fresh if o not in raw_ops] + failed_ops
        path = work / "pending_conform.json"
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"ops": remaining}, indent=2))
        os.replace(tmp, path)
    failed_n = sum(1 for e in st["ops"] if e["result"] == "failed")
    # The timeline version names what RESOLVE is holding, so it advances
    # only when something actually landed there. A conform that executed
    # nothing (every op collapsed away) leaves the version alone — the
    # timeline is where it was, and a bumped number would tell an operator
    # to re-check a cut that did not move.
    from . import facts
    executed = sum(1 for e in st["ops"] if e["result"] == "done")
    version = facts.timeline_version(slug)
    if executed:
        version = facts.bump_timeline_version(slug)
    st.update({"state": "done", "stage": "done",
               "failed": failed_n, "version": version})
    _write_status(slug, st)
