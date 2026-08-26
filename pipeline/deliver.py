# -*- coding: utf-8 -*-
"""Deliverables (P5): the readiness checklist and the master render.

The checklist is COMPUTED from live state — every row is a fact the desk
can also fix, never a checkbox someone remembers to tick. The master render
drives Resolve's own render queue through the bridge (verified in the S2
spike) as an engine job, landing in ``work/<slug>/deliverables/``.
"""
import glob
import json
import os
import subprocess
import time

from .ingest import work_path


def checklist(slug: str) -> "dict":
    from . import conform as conform_mod, editroom, proxy as proxy_mod
    work = work_path(slug)
    rows = []
    if not (work / "analysis" / "timeline_map.json").exists():
        # a fresh project 500'd here (P5 review F4) — say where it stands
        return {"slug": slug, "ready": False, "masters": [],
                "rows": [{"id": "assembled", "label": "Timeline assembled",
                          "ok": False,
                          "detail": "not assembled yet — ingest, story, "
                                    "then Assemble", "fix": "/studio"}]}

    # the TCC detector (P6, 2026-08-24): the engine tries actually READING
    # one footage file — a revoked Desktop grant makes every mechanical
    # stage fail with "Operation not permitted", and this row says so
    # BEFORE a ship attempt discovers it (the hmns story)
    fdir = work / "footage"
    probe_ok, probe_detail = True, "no footage to probe"
    files = sorted(f for f in fdir.iterdir()
                   if f.is_file() and not f.name.startswith(".")) \
        if fdir.is_dir() else []
    if files:
        # every file, not just the first: hmns mixes local files with
        # Desktop symlinks and only the symlinked ones are TCC-blocked —
        # a first-file probe would lie green
        bad = None
        for f in files:
            try:
                with open(f, "rb") as fh:
                    fh.read(1024)
            except OSError as e:
                bad = (f.name, e.strerror or str(e))
                break
        if bad is None:
            probe_ok, probe_detail = True, ("all %d files readable"
                                            % len(files))
        else:
            probe_ok = False
            probe_detail = ("cannot read %s (%s) — re-grant disk access "
                            "to the engine in System Settings" % bad)
    rows.append({"id": "footage_readable", "label": "Footage readable",
                 "ok": probe_ok, "detail": probe_detail, "fix": None})

    ship_p = work / "ship.json"
    ship = {}
    if ship_p.exists():
        try:
            ship = json.loads(ship_p.read_text())
        except ValueError:
            ship = {}
    rows.append({"id": "backup", "label": "Footage + work backed up",
                 "ok": bool(ship.get("backup_confirmed")),
                 "detail": ("confirmed %s" % time.strftime(
                     "%Y-%m-%d", time.localtime(ship.get("backup_ts", 0)))
                     if ship.get("backup_confirmed")
                     else "62GB of a shot day has no second copy until "
                          "you make one — check this off when it does"),
                 "fix": None, "manual": True})

    # the QC gate's measured rows (P10): rendered when the report covers
    # the CURRENT master; a stale report says so instead of lying green
    qc_p = work / "qc_report.json"
    if qc_p.exists():
        try:
            qc = json.loads(qc_p.read_text())
        except ValueError:
            qc = {}
        masters_now = sorted(m.name for m in
                             (work / "deliverables").glob("*.mp4")
                             if not m.name.startswith("_tmp"))
        current = masters_now[-1] if masters_now else None
        if qc.get("master") == current:
            rows.extend(dict(r, fix=None) for r in qc.get("rows", []))
        elif current:
            rows.append({"id": "qc_stale", "label": "QC the master",
                         "ok": False,
                         "detail": "the report covers %s — re-run QC for "
                                   "%s" % (qc.get("master"), current),
                         "fix": None})

    stale = conform_mod._stale_cards(slug)
    pend = editroom._conform_pending(slug)
    cstate = conform_mod.status(slug).get("state")
    # NOTHING TO CHECK is not the same as CHECKED AND FINE. This row read
    # "all current" over an episode with zero cards, because nothing stale
    # was found in an empty set — one of two ticks on the live checklist
    # that meant "we did not look" (P8 audit, 2026-08-25).
    # graphics_plan.json is the card ledger the Graphics desk reads; a
    # custom card lands in it too, so its length is the honest count.
    n_cards = 0
    gp = work / "graphics_plan.json"
    if gp.exists():
        try:
            n_cards = len(json.loads(gp.read_text()).get("cards", []))
        except ValueError:
            n_cards = 0
    rows.append({"id": "cards", "label": "Cards exported",
                 "ok": not stale,
                 "state": "none" if n_cards == 0 else ("todo" if stale else "ok"),
                 "detail": ("%d stale" % len(stale)) if stale
                 else ("no cards on this episode" if n_cards == 0 else "all current"),
                 "fix": "/studio/overlays/%s" % slug})
    rows.append({"id": "conform", "label": "Timeline conformed",
                 "ok": not pend and cstate != "running",
                 # EFFECTIVE ops, not the raw ledger. The engine collapses
                 # it before executing — an attach then a remove of the
                 # same cover cancels out — so this row said "22 edits
                 # queued" while the Review desk's own button correctly
                 # said 12. One question, one number.
                 "detail": ("conform running" if cstate == "running" else
                            ("%d edits queued" % len(conform_mod._collapse_ops(pend)))
                            if pend else "in sync"),
                 "fix": "/studio/review/%s" % slug})

    review = editroom._normalize_review(slug)
    # Count only beats in the LIVE cut — review.json keeps entries for beat
    # ids a re-assembly dropped, and 14 such ghosts once held this row amber
    # while the Review desk (which renders the cut) was rightly all green.
    # The row must share the desk's predicate exactly, or it points at a
    # queue the desk can't show.
    live_ids = {b["id"] for b in json.loads(
        (work / "edit_plan.json").read_text()).get("beats", [])}
    open_beats = [k for k, e in review.items()
                  if k in live_ids
                  and e.get("status") in ("flagged", "reworked", "edited")]
    n_reviewed = sum(1 for k, e in review.items()
                     if k in live_ids and e.get("status"))
    # CLIPS NOBODY HAS OPENED are the biggest part of "how much reviewing
    # is left", and this row could not see them: it counted only clips
    # SENT BACK, so it read "2 beats open" over an episode with 88
    # untouched — while the Review desk one click away said "90 clips
    # need you" (P8 audit, 2026-08-25). The same blind spot `handoff.ts`
    # had, fixed there in P0 for the desk footer.
    untouched = max(0, len(live_ids) - n_reviewed)
    parts = []
    if untouched:
        parts.append("%d clip%s never opened" % (untouched, "" if untouched == 1 else "s"))
    if open_beats:
        parts.append("%d sent back" % len(open_beats))
    rows.append({"id": "review", "label": "Review",
                 "ok": not open_beats and not untouched,
                 "detail": " · ".join(parts) if parts
                 else ("every clip approved" if n_reviewed else "nothing to review"),
                 "fix": "/studio/review/%s" % slug})

    caps_missing = []
    cap_path = work / "captions.json"
    if cap_path.exists():
        for c in json.loads(cap_path.read_text())["beats"]:
            if (c.get("text") or "").strip() and \
                    not (work / "captions" / ("%s.mov" % c["beat_id"])).exists():
                caps_missing.append(c["beat_id"])
    # Same shape as `cards`: no captions.json means the loop above never
    # ran, so "all baked" was a tick for a question nobody answered.
    rows.append({"id": "captions", "label": "Captions",
                 "ok": not caps_missing,
                 "state": "none" if not cap_path.exists()
                 else ("todo" if caps_missing else "ok"),
                 "detail": ("%d beats unbaked" % len(caps_missing))
                 if caps_missing else
                 ("none written" if not cap_path.exists() else "all baked"),
                 "fix": "/studio/captions/%s" % slug})

    tl, catalog, caps, cards_by_beat, cues_by_beat = proxy_mod._load(slug)
    stale_prox = [b["id"] for b in tl["beats"]
                  if not (work / "proxies" / ("%s.%s.mp4" % (b["id"],
                          proxy_mod._hash_spec(proxy_mod.beat_spec(
                              b, caps.get(b["id"], ""),
                              cards_by_beat.get(b["id"], []),
                              cues_by_beat.get(b["id"], []),
                              slug=slug))))).exists()]
    rows.append({"id": "proxies", "label": "Review proxies current",
                 "ok": not stale_prox,
                 "detail": ("%d stale" % len(stale_prox)) if stale_prox
                 else "all current", "fix": None})

    ep_path = work / "edit_plan.json"
    has_payoff = False
    if ep_path.exists():
        has_payoff = any(b.get("purpose") == "payoff"
                         for b in json.loads(ep_path.read_text())["beats"])
    rows.append({"id": "payoff", "label": "Payoff beat lands the ninth room",
                 "ok": has_payoff,
                 "detail": "payoff beat in the plan" if has_payoff
                 else "no payoff beat — the loop never closes",
                 "fix": None})

    masters = []
    vids = []
    for ext in ("*.mp4", "*.mov", "*.mxf", "*.m4v"):
        vids += [v for v in glob.glob(str(work / "deliverables" / ext))
                 if not os.path.basename(v).startswith("_tmp.")]
    for f in sorted(vids, key=os.path.getmtime, reverse=True)[:8]:
        try:
            dur = float(subprocess.run(
                ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                 "-of", "csv=p=0", f], capture_output=True, text=True,
                timeout=20).stdout.strip() or 0)
        except Exception:
            dur = 0
        st = os.stat(f)
        masters.append({"file": os.path.basename(f), "bytes": st.st_size,
                        "duration": round(dur, 1), "ts": int(st.st_mtime)})
    # Same block the Shots desk gets, so "timeline v14 · 93 clips · 22:41"
    # is one computation rather than two that drift.
    from . import editroom, facts
    try:
        st = editroom._state(slug)
        tlf = st.get("timeline") or {}
    except Exception:
        tlf = {"version": facts.timeline_version(slug),
               "clips": 0, "duration": None}
    return {"slug": slug, "ready": all(r["ok"] for r in rows),
            "rows": rows, "masters": masters, "timeline": tlf}


def render_master(slug: str, log=print, set_pct=lambda p: None) -> str:
    """Render the full timeline through Resolve's queue (S2 primitives).

    Uses the project's own render format settings; SelectAllFrames covers
    the whole timeline. Needs the synced project/timeline names — the same
    requirement conform has."""
    from . import resolve_api
    from .conform import _lua_safe
    work = work_path(slug)
    tc_path = work / "timeline_cards.json"
    if not tc_path.exists():
        raise RuntimeError("no timeline sync on file — Sync from Resolve first")
    tc = json.loads(tc_path.read_text())
    proj_name = _lua_safe(tc.get("project"))
    tl_name = _lua_safe(tc.get("timeline"))
    out_dir = work / "deliverables"
    out_dir.mkdir(exist_ok=True)
    name = "%s_master_%s" % (slug, time.strftime("%m%d_%H%M"))
    # Render under a _tmp. name and rename only on Complete (the footage
    # uploads' trick): a cancelled render must never leave a master-shaped
    # file for the desk to list (audit F1). Stale temps from a crash are
    # swept here — only one render runs at a time.
    tmp_name = "_tmp." + name
    for stale in glob.glob(str(out_dir / "_tmp.*")):
        os.unlink(stale)
    resolve_api.ensure_bridge()
    if resolve_api.rendering_in_progress():
        raise RuntimeError("Resolve is already rendering — wait for it")
    set_pct(3)
    out = resolve_api.send("deliver-start", """
local pm = resolve:GetProjectManager()
local proj = pm:GetCurrentProject()
if proj == nil or proj:GetName() ~= '%(proj)s' then proj = pm:LoadProject('%(proj)s') end
if proj == nil then return 'ERR|cannot load %(proj)s' end
local tl = proj:GetCurrentTimeline()
if tl == nil or tl:GetName() ~= '%(tl)s' then
  for i = 1, proj:GetTimelineCount() do
    local t = proj:GetTimelineByIndex(i)
    if t:GetName() == '%(tl)s' then proj:SetCurrentTimeline(t); tl = t; break end
  end
end
if tl == nil or tl:GetName() ~= '%(tl)s' then return 'ERR|timeline %(tl)s not found' end
-- The S2 spike and a verification render PERSISTED a 48/72-frame
-- MarkIn/MarkOut into this project (P5 review F6). Belt and braces: set
-- SelectAllFrames AND an explicit full-timeline range, and refuse to
-- queue if Resolve rejects the settings.
local ok = proj:SetRenderSettings({ SelectAllFrames = true,
  MarkIn = tl:GetStartFrame(), MarkOut = tl:GetEndFrame() - 1,
  TargetDir = '%(dir)s', CustomName = '%(tmp)s' })
if ok == false then return 'ERR|SetRenderSettings rejected' end
local job = proj:AddRenderJob()
if job == nil then return 'ERR|AddRenderJob failed' end
local started = proj:StartRendering(job)
if started == false then return 'ERR|StartRendering refused' end
return 'JOB|' .. job
""" % {"proj": proj_name, "tl": tl_name, "dir": str(out_dir),
       "tmp": tmp_name},
        timeout=180)
    if out.startswith("ERR|"):
        raise RuntimeError(out[4:])
    job = out.split("|")[1]
    log("[deliver] render job %s started" % job)
    deadline = time.time() + 3 * 3600
    nil_polls = 0
    while True:
        if time.time() > deadline:
            raise RuntimeError("render exceeded 3 hours — gave up polling")
        st = resolve_api.send("deliver-poll", """
local proj = resolve:GetProjectManager():GetCurrentProject()
local s = proj:GetRenderJobStatus('%s')
if s == nil then return 'nil|0' end
return tostring(s.JobStatus) .. '|' .. tostring(s.CompletionPercentage or 0)
""" % job, timeout=60)
        state, _, pct = st.partition("|")
        if state == "nil":
            # job status unavailable: the project changed under the poll or
            # the job vanished — twelve strikes and it is a failure, not a
            # wedged-forever worker (P5 review F8)
            nil_polls += 1
            if nil_polls >= 12:
                raise RuntimeError("render job lost its status — did the "
                                   "current project change mid-render?")
            time.sleep(5)
            continue
        nil_polls = 0
        try:
            set_pct(max(5, min(99, int(float(pct or 0)))))
        except ValueError:
            pass
        if state in ("Complete", "Failed", "Cancelled"):
            break
        time.sleep(5)
    resolve_api.send("deliver-clean",
                     "resolve:GetProjectManager():GetCurrentProject()"
                     ":DeleteRenderJob('%s') return 'ok'" % job, timeout=60)
    hits = glob.glob(str(out_dir / (tmp_name + "*")))
    if state != "Complete":
        for h in hits:  # the partial is junk, not a master
            os.unlink(h)
        raise RuntimeError("render %s" % state.lower())
    if not hits:
        raise RuntimeError("render finished but no file matched %s*" % tmp_name)
    final = str(out_dir / os.path.basename(hits[0])[len("_tmp."):])
    os.replace(hits[0], final)
    log("[deliver] %s" % os.path.basename(final))
    return os.path.basename(final)
