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

    stale = conform_mod._stale_cards(slug)
    pend = editroom._conform_pending(slug)
    cstate = conform_mod.status(slug).get("state")
    rows.append({"id": "cards", "label": "Cards exported and current",
                 "ok": not stale, "detail": ("%d stale" % len(stale)) if stale
                 else "all current", "fix": "/studio/overlays/%s" % slug})
    rows.append({"id": "conform", "label": "Timeline conformed",
                 "ok": not pend and cstate != "running",
                 "detail": ("conform running" if cstate == "running" else
                            ("%d edits queued" % len(pend)) if pend else "in sync"),
                 "fix": "/studio/review/%s" % slug})

    review = editroom._normalize_review(slug)
    open_beats = [k for k, e in review.items()
                  if e.get("status") in ("flagged", "reworked", "edited")]
    n_reviewed = sum(1 for e in review.values() if e.get("status"))
    rows.append({"id": "review", "label": "Review queue empty",
                 "ok": not open_beats,
                 "detail": ("%d beats open" % len(open_beats)) if open_beats
                 else ("every shot approved" if n_reviewed
                       else "nothing reviewed yet"),
                 "fix": "/studio/review/%s" % slug})

    caps_missing = []
    cap_path = work / "captions.json"
    if cap_path.exists():
        for c in json.loads(cap_path.read_text())["beats"]:
            if (c.get("text") or "").strip() and \
                    not (work / "captions" / ("%s.mov" % c["beat_id"])).exists():
                caps_missing.append(c["beat_id"])
    rows.append({"id": "captions", "label": "Captions baked",
                 "ok": not caps_missing,
                 "detail": ("%d beats unbaked" % len(caps_missing))
                 if caps_missing else "all baked",
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
        vids += glob.glob(str(work / "deliverables" / ext))
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
    return {"slug": slug, "ready": all(r["ok"] for r in rows),
            "rows": rows, "masters": masters}


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
    resolve_api.ensure_bridge()
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
  TargetDir = '%(dir)s', CustomName = '%(name)s' })
if ok == false then return 'ERR|SetRenderSettings rejected' end
local job = proj:AddRenderJob()
if job == nil then return 'ERR|AddRenderJob failed' end
local started = proj:StartRendering(job)
if started == false then return 'ERR|StartRendering refused' end
return 'JOB|' .. job
""" % {"proj": proj_name, "tl": tl_name, "dir": str(out_dir), "name": name},
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
    if state != "Complete":
        raise RuntimeError("render %s" % state.lower())
    hits = glob.glob(str(out_dir / (name + "*")))
    if not hits:
        raise RuntimeError("render finished but no file matched %s*" % name)
    log("[deliver] %s" % os.path.basename(hits[0]))
    return os.path.basename(hits[0])
