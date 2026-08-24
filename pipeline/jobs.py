# -*- coding: utf-8 -*-
"""The engine's job queue (P4): mechanical pipeline stages as buttons.

One daemon worker consumes a FIFO queue, so heavy stages never run
concurrently (they would only fight over _BAKE_LOCK/_BUILD_LOCK anyway) and
a desk click can never start the same stage twice. State is mirrored to
``work/_jobs.json`` (last 50) so the Studio's activity tray can poll it and
a mid-job engine restart shows an honest "interrupted" instead of a
forever-running ghost. Per-job logs land in ``work/_jobs/<id>.log``.

Kinds are the *mechanical* stages only — story, edit plan, and the fixer
stay agent work (plan amendment: P4 pipeline buttons):

- ``ingest``   — probe + transcribe, take analysis, b-roll catalog
- ``assemble`` — edit_plan -> captions/cards -> timeline.fcpxml, then proxies
- ``reproxy``  — proxy.build: only beats whose spec hash moved re-render
"""
import json
import os
import queue
import threading
import time

from .ingest import PROJECT_ROOT, work_path

JOBS_PATH = PROJECT_ROOT / "work" / "_jobs.json"
LOG_DIR = PROJECT_ROOT / "work" / "_jobs"
KEEP = 50

_LOCK = threading.Lock()
_QUEUE = queue.Queue()
_WORKER = [None]
_jobs = {}
_order = []


class JobError(Exception):
    pass


def _persist():
    rows = [_jobs[i] for i in _order[-KEEP:]]
    JOBS_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = JOBS_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps({"jobs": rows}, indent=2))
    os.replace(tmp, JOBS_PATH)


def _restore():
    """On import: reload history; anything 'running' at restart was killed
    with the process — say so rather than showing it running forever."""
    if not JOBS_PATH.exists():
        return
    try:
        rows = json.loads(JOBS_PATH.read_text()).get("jobs", [])
    except ValueError:
        return
    changed = False
    for r in rows:
        if r.get("state") in ("running", "queued"):
            r["state"] = "failed"
            r["error"] = "engine restarted mid-job"
            r["ended_ts"] = int(time.time())
            changed = True
        _jobs[r["id"]] = r
        _order.append(r["id"])
    if changed:
        _persist()


def _update(jid, **fields):
    with _LOCK:
        _jobs[jid].update(fields)
        _persist()


def _job_log(jid):
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    path = LOG_DIR / ("%s.log" % jid)

    def log(*parts):
        line = " ".join(str(p) for p in parts)
        with open(path, "a") as f:
            f.write(line + "\n")
        _update(jid, note=line[-160:])
    return log


def _run_ingest(slug, log, set_pct):
    from . import ingest as ingest_mod, takes, broll
    set_pct(2)
    log("[job] ingest: probe + transcribe")
    ingest_mod.ingest(slug)
    set_pct(60)
    log("[job] ingest: take analysis")
    takes.analyze(slug)
    set_pct(80)
    log("[job] ingest: b-roll catalog")
    broll.catalog_broll(slug)
    set_pct(100)


def _run_assemble(slug, log, set_pct):
    from . import produce, proxy
    set_pct(2)
    log("[job] assemble: building the timeline")
    produce.build_timeline(slug)
    set_pct(55)
    log("[job] assemble: review proxies")
    proxy.build(slug, log=log)
    set_pct(100)


def _run_reproxy(slug, log, set_pct):
    from . import proxy
    set_pct(5)
    proxy.build(slug, log=log)
    set_pct(100)


FIXER_PROMPT = (
    "Run the fixer round for %(slug)s. Read .claude/agents/shot-fixer.md and "
    "act as that agent: work/%(slug)s/review.json holds the flagged beats — "
    "the note on each is the instruction. Make the smallest change that "
    "satisfies each note, re-proxy only the beats you touched, set each "
    "fixed beat's status to 'reworked' with a one-line fixer_note, and obey "
    "every hard rule in the agent doc. Do NOT run conforms, renders, or "
    "touch DaVinci Resolve — the desk's Conform button handles the "
    "timeline. The engine is running on :8765; leave it alone.")


def _run_fixer(slug, log, set_pct):
    """Dispatch the shot-fixer as a HEADLESS Claude Code session (the same
    agent Caleb used to prompt by hand — same subscription, one button).
    Runs in its own process, so the engine's file locks do not cover it:
    the desk should not place sounds/b-roll on the flagged beats while it
    works, same as during a manual fixer round."""
    import subprocess
    review_path = work_path(slug) / "review.json"
    def flagged():
        if not review_path.exists():
            return []
        d = json.loads(review_path.read_text())
        return [k for k, e in d.items() if e.get("status") == "flagged"]
    before = flagged()
    if not before:
        raise RuntimeError("no flagged beats — nothing to send")
    log("[fixer] dispatching %d flagged beat(s): %s"
        % (len(before), " ".join(before)))
    set_pct(5)
    proc = subprocess.Popen(
        ["~/.local/bin/claude", "-p",
         FIXER_PROMPT % {"slug": slug},
         "--dangerously-skip-permissions"],
        cwd=str(PROJECT_ROOT), stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, text=True)
    set_pct(15)
    for line in proc.stdout:
        line = line.rstrip()
        if line:
            log(line)
    rc = proc.wait()
    if rc != 0:
        raise RuntimeError("fixer session exited %d — see the log" % rc)
    after = flagged()
    fixed = [b for b in before if b not in after]
    log("[fixer] done: %d fixed -> re-review, %d still flagged"
        % (len(fixed), len(after)))
    if not fixed:
        raise RuntimeError("fixer finished but no beat left flagged status "
                           "changed — read the log")
    set_pct(100)


STORY_PROMPT = (
    "Pitch stories for %(slug)s. Read .claude/agents/story-designer.md and "
    "act as that agent: read work/%(slug)s/analysis/ (take transcripts and "
    "the b-roll catalog) and the brand docs, and write "
    "work/%(slug)s/stories.json with three distinct directions. "
    "%(brief)s"
    "Each beats_outline item must be an OBJECT "
    '{"text": "...", "clips": [...], "target_s": <int seconds>} -- clips '
    "cite 1-3 real catalog filenames that carry the chapter (favorites "
    "first; the desk plays them as evidence), and target_s is the "
    "chapter's TIME BUDGET. Chapter targets MUST sum to the brief's "
    "target length within 10 percent, and when the on-camera takes cannot "
    "honestly fill a chapter, its text says what the VOICE-OVER covers -- "
    "narration Caleb records later over b-roll is a legitimate lane, not "
    "a failure. If "
    "work/%(slug)s/favorites.json exists, its files are the clips Caleb "
    "STARRED as the story's core material: build every direction around "
    "them first — a big starred set means a wide story, a small one means "
    "a focused story — and treat unstarred footage as supporting. If "
    "work/%(slug)s/story_feedback.json has rounds, the LATEST round's notes "
    "direct this round — honor them. Do NOT write edit_plan.json (that "
    "needs an approving round on the Story desk), do NOT run conforms or "
    "renders, and do NOT touch DaVinci Resolve. The engine is running on "
    ":8765; leave it alone.")


def _brief_clause(slug) -> str:
    """The questionnaire's voice in the prompt. Pure and separate so a test
    can prove the brief actually reaches the agent -- the failure mode a
    pre-production questionnaire invites is being politely ignored."""
    p = work_path(slug) / "story_brief.json"
    if not p.exists():
        return ""
    try:
        b = json.loads(p.read_text())
    except ValueError:
        return ""
    clause = ("Caleb's brief: a ~%g-minute episode in %d chapters -- pitch "
              "spines that fit that budget, and say so when the footage "
              "cannot fill it honestly. "
              % (float(b.get("target_minutes", 10)),
                 int(b.get("chapters", 6))))
    location = str(b.get("location") or "").strip()
    if location:
        clause += "The place: %s. " % location
    research_p = work_path(slug) / "research.json"
    if research_p.exists():
        clause += (
            "work/%s/research.json holds SOURCED facts about the place -- "
            "read it and RANGE WIDE: a beat the takes cannot support is "
            "legitimate when its text says the voice-over carries it, built "
            "on those facts over b-roll. The footage anchors the story; the "
            "research expands it. " % slug)
    notes = str(b.get("notes") or "").strip()
    if notes:
        clause += "Brief notes: %s " % notes
    return clause


def _story_prompt(slug) -> str:
    return STORY_PROMPT % {"slug": slug, "brief": _brief_clause(slug)}


def _editplan_prompt(slug) -> str:
    clause = _brief_clause(slug)
    # a script outranks improvisation: when one exists the cut FOLLOWS it
    if (work_path(slug) / "script.json").exists():
        clause += ("work/%s/script.json is the approved SCRIPT -- the cut "
                   "follows it section by section: oncamera sections use "
                   "their cited take_id; vo sections use the recorded "
                   "vo_<section>_t<n> takes (ordinary speech takes after "
                   "ingest) with b-roll covering their ENTIRE beat -- a "
                   "teleprompter recording on screen is a mistake. Respect "
                   "the one-use-per-b-roll-clip rule. " % slug)
    return EDITPLAN_PROMPT % {"slug": slug, "brief": clause}


def _run_story(slug, log, set_pct):
    """Dispatch the story-designer as a headless Claude Code session — the
    same agent Caleb used to prompt by hand, now the desk's Pitch button.
    Same pattern as the fixer: the proof of work is the artifact changing,
    not the exit code."""
    import subprocess
    stories_path = work_path(slug) / "stories.json"
    before = stories_path.stat().st_mtime if stories_path.exists() else None
    log("[story] dispatching the story designer%s"
        % (" — fresh round over existing pitches" if before else ""))
    set_pct(5)
    proc = subprocess.Popen(
        ["~/.local/bin/claude", "-p",
         _story_prompt(slug),
         "--dangerously-skip-permissions"],
        cwd=str(PROJECT_ROOT), stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, text=True)
    set_pct(15)
    for line in proc.stdout:
        line = line.rstrip()
        if line:
            log(line)
    rc = proc.wait()
    if rc != 0:
        raise RuntimeError("story session exited %d — see the log" % rc)
    after = stories_path.stat().st_mtime if stories_path.exists() else None
    if after is None or after == before:
        raise RuntimeError("session finished but stories.json did not "
                           "change — read the log")
    log("[story] pitches written — pick a direction on the Story desk")
    set_pct(100)


EDITPLAN_PROMPT = (
    "Write the edit plan for %(slug)s. %(brief)s"
    "Read .claude/agents/story-designer.md "
    "and act as that agent for the EDIT PLAN stage: the latest round in "
    "work/%(slug)s/story_feedback.json is an APPROVING round — build the "
    "plan from its chosen direction in work/%(slug)s/stories.json, honoring "
    "its notes. Read work/%(slug)s/analysis/ (takes, b-roll, timings) and "
    "write work/%(slug)s/edit_plan.json that satisfies the agent's plan "
    "rules. Do NOT run conforms or renders, and do NOT touch DaVinci "
    "Resolve. The engine is running on :8765; leave it alone.")


SCRIPT_PROMPT = (
    "Write the timed script for %(slug)s. %(brief)sRead "
    ".claude/agents/story-designer.md and act as that agent for the SCRIPT "
    "stage: the latest round in work/%(slug)s/story_feedback.json approves "
    "a direction in work/%(slug)s/stories.json -- script THAT direction, "
    "chapter by chapter, into work/%(slug)s/script.json with this exact "
    "shape: {\"slug\", \"option_id\", \"target_minutes\", \"chapters\": "
    "[{\"id\": \"CH1\", \"title\", \"target_s\", \"sections\": "
    "[{\"id\": \"CH1.S1\", \"kind\": \"oncamera\"|\"vo\", \"text\", "
    "\"take_id\" (oncamera only), \"est_s\"}]}]}. oncamera sections QUOTE "
    "a real take (take_id from analysis/takes.json, text = what it says, "
    "est_s = its trimmed span). vo sections are lines Caleb records LATER "
    "over b-roll, in his voice, est_s = words/150*60 -- this is the lane "
    "that fills a brief the day's takes cannot. A vo line built on a "
    "research.json fact carries that fact's source_url as \"source\" so "
    "QC can trace the claim. Each chapter's est_s sum "
    "must land within 25 percent of its target_s. Run "
    "/usr/bin/python3 -c 'from pipeline import schemas; import json; "
    "print(schemas.validate_script(json.load(open(\"work/%(slug)s/"
    "script.json\")), json.load(open(\"work/%(slug)s/analysis/"
    "takes.json\"))))' from the repo root and fix every error it prints. "
    "Do NOT touch DaVinci Resolve; the engine on :8765 is not yours.")


def _script_prompt(slug) -> str:
    return SCRIPT_PROMPT % {"slug": slug, "brief": _brief_clause(slug)}


RESEARCH_PROMPT = (
    "Research %(location)s for The Ninth Room episode %(slug)s. Search the "
    "web broadly -- history, numbers, engineering, oddities, the stories "
    "locals and enthusiasts tell -- and write work/%(slug)s/research.json: "
    '{"location": "...", "facts": [{"fact": "one verifiable sentence", '
    '"source_url": "...", "confidence": "verified"|"claimed"}], '
    '"angles": ["story angle this research opens", ...], "ts": <epoch int>}. '
    "10-25 facts, every one SOURCED -- accuracy is the brand and a parent "
    "is fact-checking this in front of their kid; mark disputed or "
    "single-source claims \"claimed\", never settled. The facts feed "
    "voice-over lines Caleb records over b-roll, so favor what makes "
    "someone say 'wait, really?' out loud. Do NOT touch DaVinci Resolve "
    "or the engine on :8765.")


def _run_research(slug, log, set_pct):
    """The web's half of the story (Caleb, 2026-08-23): the footage knows
    what happened on the day; research.json knows the place. Story pitches
    and VO scripts read it, which is what lets them range wider than what
    was said on camera. Same dispatch-and-verify shape as the scout."""
    import json
    import subprocess
    work = work_path(slug)
    brief_p = work / "story_brief.json"
    location = ""
    if brief_p.exists():
        try:
            location = str(json.loads(brief_p.read_text())
                           .get("location") or "").strip()
        except ValueError:
            pass
    if not location:
        raise RuntimeError("the brief has no location -- name the place or "
                           "event on the Story desk first")
    out_p = work / "research.json"
    before = out_p.stat().st_mtime if out_p.exists() else None
    log("[research] dispatching the researcher for %s" % location)
    set_pct(5)
    proc = subprocess.Popen(
        ["~/.local/bin/claude", "-p",
         RESEARCH_PROMPT % {"slug": slug, "location": location},
         "--dangerously-skip-permissions"],
        cwd=str(PROJECT_ROOT), stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, text=True)
    set_pct(15)
    for line in proc.stdout:
        line = line.rstrip()
        if line:
            log(line)
    rc = proc.wait()
    if rc != 0:
        raise RuntimeError("research session exited %d -- see the log" % rc)
    after = out_p.stat().st_mtime if out_p.exists() else None
    if after is None or after == before:
        raise RuntimeError("session finished but research.json did not "
                           "change -- read the log")
    facts = json.loads(out_p.read_text()).get("facts", [])
    unsourced = [f for f in facts if not str(f.get("source_url") or "").strip()]
    if not facts or unsourced:
        raise RuntimeError(
            "research.json has %d facts, %d unsourced -- every fact needs a "
            "source; accuracy is the brand" % (len(facts), len(unsourced)))
    log("[research] %d sourced facts in -- pitch a round and they widen it"
        % len(facts))
    set_pct(100)


def _run_script(slug, log, set_pct):
    """The Script desk's writer (Caleb, 2026-08-23): the timed script
    between an approved direction and the cut. Dispatch-and-verify like its
    siblings -- but here the proof is not just that script.json changed; it
    must also VALIDATE, because a script whose chapter sums ignore their
    targets is the budget fiction this whole feature exists to prevent."""
    import json
    import subprocess
    from . import schemas
    work = work_path(slug)
    fb = work / "story_feedback.json"
    rounds = (json.loads(fb.read_text()).get("rounds", [])
              if fb.exists() else [])
    if not rounds or rounds[-1].get("decision") != "approve":
        raise RuntimeError("no approving round -- approve a direction on "
                           "the Story desk first")
    script_path = work / "script.json"
    if script_path.exists():
        raise RuntimeError("script.json already exists -- edit sections on "
                           "the Script desk; a rewrite is a session decision")
    log("[script] dispatching the story designer for the script")
    set_pct(5)
    proc = subprocess.Popen(
        ["~/.local/bin/claude", "-p", _script_prompt(slug),
         "--dangerously-skip-permissions"],
        cwd=str(PROJECT_ROOT), stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, text=True)
    set_pct(15)
    for line in proc.stdout:
        line = line.rstrip()
        if line:
            log(line)
    rc = proc.wait()
    if rc != 0:
        raise RuntimeError("script session exited %d -- see the log" % rc)
    if not script_path.exists():
        raise RuntimeError("session finished but script.json was not "
                           "written -- read the log")
    takes = json.loads((work / "analysis" / "takes.json").read_text())
    errs = schemas.validate_script(json.loads(script_path.read_text()), takes)
    if errs:
        raise RuntimeError("script.json failed validation: " +
                           "; ".join(errs[:4]))
    log("[script] script written -- read it on the Script desk, record the "
        "vo sections, then Build the cut")
    set_pct(100)


GRAPHICS_PROMPT = (
    "Direct the graphics for The Ninth Room episode %(slug)s. Read "
    ".claude/agents/graphics-director.md and act as that agent: read "
    "work/%(slug)s/edit_plan.json, the transcripts in "
    "work/%(slug)s/analysis/takes.json, and brand/engagement-playbook.md, "
    "then write work/%(slug)s/graphics_plan.json as "
    '{"slug": "%(slug)s", "cards": [...]}. Every card carries id '
    '("CARD01"...), type, kit_type, beat_id naming a beat in the edit '
    "plan, at (seconds INTO that beat -- it must land inside the beat), "
    "duration, animation, and its copy fields. Recommend a card wherever "
    "one earns its place -- the hook, chapter turns, verified facts, one "
    "engagement moment every 60-90 seconds, the outro run -- and nowhere "
    "else; a bare stretch is a choice, not a gap. Before finishing, "
    "validate: /usr/bin/python3 -c \"import json,sys; sys.path.insert(0,'.'); "
    "from pipeline import schemas; ep=json.load(open('work/%(slug)s/edit_plan.json')); "
    "gp=json.load(open('work/%(slug)s/graphics_plan.json')); "
    "errs=schemas.validate_graphics_plan(gp, ep); "
    "print(errs); sys.exit(1 if errs else 0)\" and fix every error it "
    "prints. Do NOT touch DaVinci Resolve or the engine on :8765.")


def _run_graphics(slug, log, set_pct):
    """The Review desk's card recommender (Caleb, 2026-08-23: assembly
    shipped bare -- "it should recommend cards for the clips"). The
    graphics-director was the one creative stage never converted to a job
    when the Edit Room retired, so no cut ever got cards without a manual
    session. Dispatch-and-verify; the proof is a graphics_plan.json that
    VALIDATES against the edit plan, because a card homed to a missing
    beat is composited into no proxy and reviews as nothing."""
    import json
    import subprocess
    from . import schemas
    work = work_path(slug)
    plan_path = work / "edit_plan.json"
    if not plan_path.exists():
        raise RuntimeError("no cut yet -- Build the cut first")
    gp_path = work / "graphics_plan.json"
    if gp_path.exists():
        raise RuntimeError("graphics already planned -- edit cards on the "
                           "Graphics desk (delete graphics_plan.json to "
                           "start over)")
    log("[graphics] dispatching the graphics director")
    set_pct(5)
    proc = subprocess.Popen(
        ["~/.local/bin/claude", "-p",
         GRAPHICS_PROMPT % {"slug": slug},
         "--dangerously-skip-permissions"],
        cwd=str(PROJECT_ROOT), stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, text=True)
    set_pct(15)
    for line in proc.stdout:
        line = line.rstrip()
        if line:
            log(line)
    rc = proc.wait()
    if rc != 0:
        raise RuntimeError("graphics session exited %d -- see the log" % rc)
    if not gp_path.exists():
        raise RuntimeError("session finished but graphics_plan.json was "
                           "not written -- read the log")
    ep = json.loads(plan_path.read_text())
    gp = json.loads(gp_path.read_text())
    errs = schemas.validate_graphics_plan(gp, ep)
    if errs:
        raise RuntimeError("graphics_plan.json failed validation: " +
                           "; ".join(errs[:4]))
    log("[graphics] %d cards proposed -- review them per clip on the "
        "Review desk; Rebuild previews burns them into the playback"
        % len(gp.get("cards", [])))
    set_pct(100)


def _run_editplan(slug, log, set_pct):
    """The Story desk's approved-state button (UX overhaul, 2026-08-23).
    Approving a direction used to end with the desk saying "tell Claude:
    write the edit plan" — a hand-off to a session a customer doesn't have.
    Same dispatch-and-verify shape as _run_story: the proof of work is
    edit_plan.json changing, not the exit code."""
    import json
    import subprocess
    work = work_path(slug)
    fb = work / "story_feedback.json"
    if not (work / "stories.json").exists():
        raise RuntimeError("no story pitches yet — pitch stories first")
    rounds = (json.loads(fb.read_text()).get("rounds", [])
              if fb.exists() else [])
    if not rounds or rounds[-1].get("decision") != "approve":
        raise RuntimeError("no approving round — approve a direction on "
                           "the Story desk first")
    plan_path = work / "edit_plan.json"
    if plan_path.exists():
        # overwriting a cut that desks and reviews hang off is a decision,
        # not a button press
        raise RuntimeError("edit_plan.json already exists — the cut is "
                           "built; re-cutting is a session decision")
    log("[editplan] dispatching the story designer for the cut")
    set_pct(5)
    proc = subprocess.Popen(
        ["~/.local/bin/claude", "-p",
         _editplan_prompt(slug),
         "--dangerously-skip-permissions"],
        cwd=str(PROJECT_ROOT), stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, text=True)
    set_pct(15)
    for line in proc.stdout:
        line = line.rstrip()
        if line:
            log(line)
    rc = proc.wait()
    if rc != 0:
        raise RuntimeError("edit-plan session exited %d — see the log" % rc)
    if not plan_path.exists():
        raise RuntimeError("session finished but edit_plan.json was not "
                           "written — read the log")
    log("[editplan] cut written — assemble builds the timeline next")
    set_pct(100)


SCOUT_PROMPT = (
    "Scout ideas for The Ninth Room. Read .claude/agents/scout.md and act "
    "as that agent: search the web for episode-worthy places and hooks, "
    "and write/update work/_scout/ideas.json with sourced candidates. "
    "Channel-level -- no per-project work, no conforms, no renders, no "
    "DaVinci Resolve. The engine is running on :8765; leave it alone.")


def _run_scout(slug, log, set_pct):
    """The Ideas desk's Scout button (UX overhaul, 2026-08-23). Channel-
    level: `slug` is the _scout workspace, not a project. Proof of work is
    ideas.json changing, same as every other dispatched agent."""
    import subprocess
    ideas_path = work_path("_scout") / "ideas.json"
    before = ideas_path.stat().st_mtime if ideas_path.exists() else None
    log("[scout] dispatching the idea scout")
    set_pct(5)
    proc = subprocess.Popen(
        ["~/.local/bin/claude", "-p", SCOUT_PROMPT,
         "--dangerously-skip-permissions"],
        cwd=str(PROJECT_ROOT), stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, text=True)
    set_pct(15)
    for line in proc.stdout:
        line = line.rstrip()
        if line:
            log(line)
    rc = proc.wait()
    if rc != 0:
        raise RuntimeError("scout session exited %d -- see the log" % rc)
    after = ideas_path.stat().st_mtime if ideas_path.exists() else None
    if after is None or after == before:
        raise RuntimeError("session finished but ideas.json did not "
                           "change -- read the log")
    log("[scout] new ideas on the Ideas desk")
    set_pct(100)


def _run_render(slug, log, set_pct):
    from . import deliver
    deliver.render_master(slug, log=log, set_pct=set_pct)
    set_pct(100)


KINDS = {
    "ingest": ("Ingest — transcribe, takes, b-roll", _run_ingest),
    "assemble": ("Assemble — timeline + proxies", _run_assemble),
    "reproxy": ("Re-proxy changed beats", _run_reproxy),
    "render": ("Render master — Resolve render queue", _run_render),
    "fixer": ("Fixer round — flagged beats to re-review", _run_fixer),
    "story": ("Story pitches — three directions", _run_story),
    "editplan": ("Build the cut — plan from the approved direction",
                 _run_editplan),
    "script": ("Write the script — timed sections from the approved "
               "direction", _run_script),
    "research": ("Research — sourced facts about the place", _run_research),
    "graphics": ("Suggest graphics — cards recommended per clip",
                 _run_graphics),
    "scout": ("Scout — episode ideas with sources", _run_scout),
}


def _worker():
    while True:
        jid = _QUEUE.get()
        job = _jobs[jid]
        _update(jid, state="running", started_ts=int(time.time()))
        log = _job_log(jid)
        try:
            _, fn = KINDS[job["kind"]]
            fn(job["slug"], log, lambda p: _update(jid, pct=int(p)))
            _update(jid, state="done", pct=100, ended_ts=int(time.time()))
        except Exception as e:  # the tray must show the failure, never hang
            log("[job] FAILED: %s: %s" % (type(e).__name__, e))
            _update(jid, state="failed", error=str(e)[:300],
                    ended_ts=int(time.time()))


def start(kind: str, slug: str) -> "dict":
    if kind not in KINDS:
        raise JobError("unknown job kind '%s'" % kind)
    if not (work_path(slug)).is_dir():
        raise JobError("no project '%s'" % slug)
    if kind == "render":
        from . import conform as conform_mod, resolve_api
        if conform_mod.status(slug).get("state") == "running":
            raise JobError("a conform is running — render after it")
        if resolve_api.rendering_in_progress():
            raise JobError("Resolve is already rendering — wait for it")
    if kind == "story":
        if not (work_path(slug) / "analysis" / "catalog.json").exists():
            raise JobError("ingest first — the designer needs transcripts")
        if (work_path(slug) / "edit_plan.json").exists():
            raise JobError("story is locked — an edit plan already exists")
    if kind == "fixer":
        rv = work_path(slug) / "review.json"
        n = 0
        if rv.exists():
            n = sum(1 for e in json.loads(rv.read_text()).values()
                    if e.get("status") == "flagged")
        if not n:
            raise JobError("no flagged beats to send")
    with _LOCK:
        for j in _jobs.values():
            if (j["kind"] == kind and j["slug"] == slug
                    and j["state"] in ("queued", "running")):
                raise JobError("%s is already %s for %s"
                               % (kind, j["state"], slug))
        jid = "J%d%03d" % (int(time.time()), len(_order) % 1000)
        job = {"id": jid, "kind": kind, "slug": slug,
               "label": KINDS[kind][0], "state": "queued", "pct": 0,
               "note": "", "queued_ts": int(time.time())}
        _jobs[jid] = job
        _order.append(jid)
        _persist()
        if _WORKER[0] is None:
            _WORKER[0] = threading.Thread(target=_worker, daemon=True)
            _WORKER[0].start()
    _QUEUE.put(jid)
    return job


def jobs(slug: "str | None" = None) -> "list":
    with _LOCK:
        rows = [_jobs[i] for i in reversed(_order)]
    if slug:
        rows = [r for r in rows if r["slug"] == slug]
    return rows[:KEEP]


def log_tail(jid: str, lines: int = 120) -> str:
    path = LOG_DIR / ("%s.log" % jid)
    if not path.exists():
        return ""
    return "\n".join(path.read_text().splitlines()[-lines:])


_restore()
