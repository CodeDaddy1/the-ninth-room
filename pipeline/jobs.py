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
import sys
import threading
import time

from .ingest import PROJECT_ROOT, work_path

JOBS_PATH = PROJECT_ROOT / "work" / "_jobs.json"
LOG_DIR = PROJECT_ROOT / "work" / "_jobs"
KEEP = 50

# `_jobs.json` is a RING BUFFER of the last KEEP rows — the Studio's tray
# only ever wants the recent window. That means the engine kept no job
# history at all: every fiftieth run destroyed the evidence of the previous
# fifty. The 2026-08-28 failure analysis had to be frozen by hand into
# docs/baselines/ because writing it up would have overwritten it, and the
# ledger rotated once mid-session even so.
#
# So terminal jobs are ALSO appended here, one JSON object per line, and
# nothing prunes it. Append-only: the hot window stays exactly as it was.
# Seven sites launched this by absolute path; five of them were whole
# copies of _dispatch that had drifted only in their dash. One name now,
# so a moved binary is one edit and not a hunt (2026-08-28).
CLAUDE_BIN = "~/.local/bin/claude"
HISTORY_PATH = PROJECT_ROOT / "work" / "_jobs.log"
# `declined` is terminal too — a job that refused is a measurement.
TERMINAL_STATES = ("done", "failed", "declined")

# What the PREVIOUS run was holding when it died, filled by _restore at
# import. A plain list, populated before any thread starts, so a reader
# needs no lock and causes no side effect — `jobs()` would have reaped
# chains just to answer the question.
INTERRUPTED_AT_BOOT: "list" = []

_LOCK = threading.Lock()
# Two lanes, one worker each (2026-08-24). Measured: 173 minutes of the
# tracked job life was spent QUEUEING against 342 running — 34% — and the
# worst case was `snapcuts` waiting 57 minutes behind a dispatched Claude
# session that was using no local CPU at all. A session job is network-
# bound and idle on this machine; an ffmpeg job is not. Running one of
# each concurrently costs nothing and stops the cheap thing blocking the
# expensive one.
#
# The invariant that matters: AT MOST ONE LOCAL JOB AT A TIME. The point
# is to stop sessions blocking ffmpeg, never to run two encodes at once.
#
# Lane membership is an explicit table, not introspection of a function's
# source — a new kind must be classified deliberately, and
# test_job_lanes.py fails if any kind in KINDS is missing from it.
SESSION_KINDS = {
    "story", "editplan", "recut", "coverage", "graphics", "script", "research",
    "sourcing", "interview",
    "retention", "room", "publish", "scout", "fixer", "hook", "perf",
    "retro", "diagnose",
}
LOCAL_KINDS = {
    # survey is ffmpeg on this machine like the rest of them: it decodes
    # and re-encodes every clip, so it serialises with the heavy work
    # rather than racing an assemble for the same cores
    "survey", "ingest", "assemble", "reproxy", "render", "rendercards",
    "qcgate", "snapcuts",
}


def lane_of(kind: str) -> str:
    """Which lane a kind runs in. An unclassified kind falls to `local`,
    the conservative side: it serialises with the heavy work rather than
    running beside it."""
    return "session" if kind in SESSION_KINDS else "local"


_QUEUES = {"session": queue.Queue(), "local": queue.Queue()}
_WORKERS: "dict" = {"session": None, "local": None}
_jobs = {}
_order = []
# Never decreases. Ids used to be stamped `len(_order) % 1000`, which is
# not unique: `_order` can shrink (a prune, a test purge) and it wraps at
# 1000, so two jobs born in the same second could take the SAME id. The
# second one then overwrote the first's row while both ids sat in the
# queue — one row ran twice and the other job hung at "queued" forever,
# which reads as the lane having died. (2026-08-25, chasing a 1-in-6
# flake in test_job_lanes; the id also names the job's log file, so a
# collision crossed two jobs' logs as well.)
_seq = 0


class JobError(Exception):
    pass


def _persist():
    # `_order` and `_jobs` can drift — a prune that drops a row without
    # its id leaves an orphan, and the KeyError this used to raise came
    # out of EVERY write path, not just the one that pruned. Drop the
    # orphan and carry on (2026-08-25).
    missing = [i for i in _order if i not in _jobs]
    for i in missing:
        _order.remove(i)
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
            INTERRUPTED_AT_BOOT.append(r)
            changed = True
        _jobs[r["id"]] = r
        _order.append(r["id"])
    # NOT persisted on purpose (2026-08-24). _restore runs as an IMPORT
    # side effect, so any side process that imports this module — a test,
    # a CLI verb, an inspection script — would otherwise rewrite the
    # shared store and mark the LIVE engine's running and queued jobs
    # "failed: engine restarted mid-job". Marking them in memory is right
    # for this process's view; writing that view over the engine's is not.
    # The engine persists on its own next _update, which is the only
    # process entitled to say what the queue is doing.
    _ = changed


def _append_history(job):
    """One line per job that reached a terminal state, forever.

    Diagnostic only, and deliberately best-effort: a job must never fail
    because its history line could not be written. Called from inside
    _LOCK, on the transition INTO a terminal state, so a job appears here
    exactly once however many times it is updated afterwards.
    """
    try:
        HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        with HISTORY_PATH.open("a") as fh:
            fh.write(json.dumps(job, sort_keys=True) + "\n")
    except OSError:
        pass


def _update(jid, **fields):
    with _LOCK:
        job = _jobs.get(jid)
        if job is None:
            # the row was pruned while its job was still finishing. Raising
            # here climbed out through log() and killed the worker thread
            # (2026-08-25); a vanished job simply has nothing to update.
            return
        was = job.get("state")
        job.update(fields)
        if job.get("state") in TERMINAL_STATES and was not in TERMINAL_STATES:
            _append_history(job)
        _persist()


# Which job this worker thread is running. Set by the worker, read by the
# dispatcher so a session can stamp its id onto the job WITHOUT threading a
# jid through every _run_* signature. One job per lane on its own thread,
# so a thread-local is exactly the right scope.
_CURRENT = threading.local()


def _current_jid():
    """The job on THIS thread, or None. Read on the worker thread and
    passed down — never read from a drain thread, which has its own empty
    thread-local (caught live 2026-08-25: the id silently never landed
    because the reader ran on a thread the worker had not touched)."""
    return getattr(_CURRENT, "jid", None)


def _note_session(session_id: str, jid=None) -> None:
    """Record the Claude session a job dispatched.

    The id is what makes an agent's work inspectable after the fact: the
    transcript lives at ~/.claude/projects/<escaped-cwd>/<id>.jsonl and
    `claude --resume <id>` picks the conversation back up. Without it a
    finished job is just its log tail, and 'what did it actually read'
    has no answer.

    `jid` is explicit for callers on a helper thread; it falls back to
    this thread's job for ordinary callers.
    """
    jid = jid or _current_jid()
    if jid and session_id and jid in _jobs:
        _update(jid, session_id=session_id)


def _job_log(jid):
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    path = LOG_DIR / ("%s.log" % jid)

    def log(*parts):
        line = " ".join(str(p) for p in parts)
        with open(path, "a") as f:
            f.write(line + "\n")
        _update(jid, note=line[-160:])

    def note(text):
        """Update the row's LIVE note without appending to the log.

        The dock reads `note`; the log is the record. Per-file progress
        belongs in the first and would bury the second — an ingest of 368
        files would push every phase line out of the 120-line tail that
        `/api/job/log` returns.
        """
        _update(jid, note=str(text)[-160:])

    log.note = note
    return log


def _mmss(seconds) -> str:
    """`174` -> "2:54". Empty for nothing worth stating."""
    try:
        n = int(seconds)
    except (TypeError, ValueError):
        return ""
    if n <= 0:
        return ""
    return "%d:%02d" % (n // 60, n % 60)


def _run_survey(slug, log, set_pct):
    """Pass 1: see the shoot. Probe, screen, poster, preview — no whisper.

    Two phases with very different costs, so the job's percentage is
    split to match what is actually happening: posters are the first
    fifth, previews the rest. A bar that spends 80% of its life in its
    first 20% is the hardcoded ladder this replaced.
    """
    from . import ingest as ingest_mod, survey as survey_mod
    note = getattr(log, "note", lambda _t: None)

    def on_progress(f):
        stage = str(f.get("stage") or "")
        try:
            done = int(f.get("done") or 0)
            total = int(f.get("total") or 0)
        except (TypeError, ValueError):
            return
        if total <= 0:
            return
        frac = max(0.0, min(1.0, float(f.get("pct") or 0)))
        cur = str(f.get("current") or "")
        if stage == "survey":
            set_pct(2 + int(18 * frac))
            note("reading %d of %d · %s" % (min(done + 1, total), total, cur))
        elif stage == "previews":
            set_pct(20 + int(79 * frac))
            eta = _mmss(f.get("eta_s"))
            note(" · ".join(x for x in (
                "previews %d of %d" % (min(done + 1, total), total),
                cur, "%s left" % eta if eta else "") if x))

    with ingest_mod.observing(slug, on_progress):
        set_pct(2)
        log("[job] survey: probe + posters + previews")
        survey_mod.survey(slug)
    set_pct(100)


def _run_ingest(slug, log, set_pct):
    from . import ingest as ingest_mod, takes, broll
    note = getattr(log, "note", lambda _t: None)

    def on_progress(f):
        """Forward the engine's own numbers onto the JOB.

        `ingest.write_progress` has recorded byte-weighted progress with
        an ETA since the ingest work, and it reached the project row and
        the Footage desk — never the job. So the Activity dock, whose
        entire purpose is showing what is running, showed a hardcoded 2%
        and "probe + transcribe" for the whole transcription, which is by
        far the longest phase (Caleb, 2026-08-26).

        Best-effort: a progress line must never be able to sink an ingest,
        which is why `write_progress` swallows this callback's errors too.
        """
        stage = str(f.get("stage") or "")
        try:
            done = int(f.get("done") or 0)
            total = int(f.get("total") or 0)
        except (TypeError, ValueError):
            return
        if stage == "transcribe" and total > 0:
            # the byte fraction, not done/total: file size tracks duration
            # closely and a 4K clip is not one 300-file unit of work
            frac = max(0.0, min(1.0, float(f.get("pct") or 0)))
            set_pct(2 + int(56 * frac))
            eta = _mmss(f.get("eta_s"))
            cur = str(f.get("current") or "")
            note(" · ".join(x for x in (
                "reading %d of %d" % (min(done + 1, total), total),
                cur, "%s left" % eta if eta else "") if x))
        elif stage == "broll" and total > 0:
            set_pct(80 + int(19 * max(0.0, min(1.0, done / total))))
            note("contact sheets · %d of %d" % (done, total))

    with ingest_mod.observing(slug, on_progress):
        set_pct(2)
        log("[job] ingest: probe + transcribe")
        ingest_mod.ingest(slug)
        set_pct(60)
        log("[job] ingest: take analysis")
        takes.analyze(slug)
        set_pct(75)
        # takes.analyze rebuilds takes.json from scratch, which would
        # silently un-kill every take Caleb screened out. His verdicts are
        # stored separately for exactly this reason — re-apply them here,
        # or a re-ingest quietly undoes a screening pass (2026-08-24).
        from . import editroom as editroom_mod
        n = editroom_mod._stamp_takes(slug)
        if n:
            log("[job] ingest: re-applied %d take verdict(s)" % n)
        set_pct(80)
        log("[job] ingest: b-roll catalog")
        # inside the observer too — `catalog_broll` reports per sheet, and
        # on a big shoot that phase is minutes of its own
        broll.catalog_broll(slug)
        set_pct(100)


def _run_assemble(slug, log, set_pct):
    from . import produce, proxy
    # GUARD BEFORE THE WORK — the rule `_run_reproxy` below already
    # carries, and for the same reason. Without a cut, `build_timeline`
    # raised a bare FileNotFoundError at 2% and the desk showed
    # "[Errno 2] No such file or directory: .../edit_plan.json" where the
    # honest answer is that there is no cut yet. Found running a real
    # short-form documentary end to end (2026-08-26).
    if not (work_path(slug) / "edit_plan.json").exists():
        raise JobError("no cut yet — build the cut on the Story desk "
                       "first; assemble turns it into a timeline")
    set_pct(2)
    log("[job] assemble: building the timeline")
    produce.build_timeline(slug)
    set_pct(55)
    log("[job] assemble: review proxies")
    proxy.build(slug, log=log)
    set_pct(100)


def _run_reproxy(slug, log, set_pct):
    """Rebuild the review previews. Previews are per-BEAT, so this needs a
    cut: `analysis/timeline_map.json` is assemble's output, and without it
    proxy.build raised a bare FileNotFoundError at 5% (found by the
    workflow shakedown, 2026-08-24) — a stack trace where the honest
    answer is 'there is no cut yet'. Guards refuse BEFORE the work."""
    from . import proxy
    if not (work_path(slug) / "analysis" / "timeline_map.json").exists():
        raise JobError("no cut to rebuild previews for — assemble '%s' "
                       "first" % slug)
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
    _dispatch(FIXER_PROMPT % {"slug": slug}, log, set_pct, "fixer")
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
    "cite 1-3 real catalog filenames that carry the chapter (the desk "
    "plays them as evidence), and target_s is the "
    "chapter's TIME BUDGET. Chapter targets MUST sum to the brief's "
    "target length within 10 percent, and when the on-camera takes cannot "
    "honestly fill a chapter, its text says what the VOICE-OVER covers -- "
    "narration Caleb records later over b-roll is a legitimate lane, not "
    "a failure. "
    "If "
    "work/%(slug)s/story_feedback.json has rounds, the LATEST round's notes "
    "direct this round — honor them. Do NOT write edit_plan.json (that "
    "needs an approving round on the Story desk), do NOT run conforms or "
    "renders, and do NOT touch DaVinci Resolve. The engine is running on "
    ":8765; leave it alone.")


def _craft_clause(slug) -> str:
    """The craft bar, stated to the writer BEFORE it writes.

    The bar was calibrated against five real cuts and then wired to
    nothing, and the fields it grades — pace_cpm, opens_loop, pays_loop,
    framing, peak — appeared in no brief. A gate that asks for
    declarations nobody was told to make is not a gate, it is a trap: the
    session spends its minutes, the promote refuses, and the notes name
    fields the agent has never heard of.

    EVERY NUMBER IS READ FROM `cutbar`, never retyped. That is what keeps
    the calibration doc's promise that recalibrating means changing one
    constant and re-running the report, rather than hunting for the same
    figure in a prompt string. Pure, so a test can prove the numbers
    actually reach the agent — the same reason `_brief_clause` is pure.
    """
    from . import cutbar
    b = _read_json(work_path(slug) / "story_brief.json", {}) or {}
    chapters = int(b.get("chapters") or 0)
    short = str(b.get("delivery") or "long") == "short"
    peaks = max(cutbar.PEAKS_MIN, chapters - 1) if chapters else cutbar.PEAKS_MIN

    c = ("THE CRAFT BAR (mechanical, checked on promote — run "
         "`/usr/bin/python3 -m pipeline.cli cut-check %s --staged` and "
         "leave it EMPTY before you finish): " % slug)
    # The chapter half of the peak rule is vacuous below two chapters,
    # and saying it anyway teaches a short-form writer to look for a
    # structure its format does not have.
    where = ("" if chapters < 2
             else ", one in every chapter after the intro")
    c += ("Protect %d PEAK beats%s, %g-%gs each, marked `\"peak\": true` — "
          "nothing may cover, card or punch a peak, and the renderer stops "
          "cutting its silence. "
          % (peaks, where, cutbar.PEAK_LEN_S[0], cutbar.PEAK_LEN_S[1]))
    if short:
        c += ("This is a SHORT: one loop, not a ledger, and no chapter "
              "furniture. ")
    else:
        c += ("Declare `pace_cpm` (cuts per minute) on EVERY chapter as a "
              "DECLINING ladder — the last chapter at or under %.0f%% of "
              "the first, at most %d second wind, and the cut you actually "
              "build within %.0f%% of what you declared. "
              % (cutbar.PACE_DECLINE_MAX * 100, cutbar.PACE_REVERSALS_MAX,
                 cutbar.PACE_BAND * 100))
        c += ("Every chapter opens AND closes, and carries one moment "
              "between its doors that LANDS: a peak, or a beat whose "
              "purpose is one of %s. " % "/".join(cutbar.CHAPTER_TEXTURE))
        if chapters >= cutbar.LONG_FORM_CHAPTERS or not chapters:
            c += ("Open at least %d loops (`opens_loop` on the beat that "
                  "promises, `pays_loop` on the beat that pays) and pay "
                  "them IN ORDER, the last one past %.0f%% of the runtime. "
                  % (cutbar.LOOPS_MIN, cutbar.CLIMAX_AT * 100))
        c += ("The hook is a chapter-preview montage: %d covers, each at "
              "least %.1fs, each `why` LEADING with foretell and naming "
              "its chapter id. "
              % (min(chapters, cutbar.HOOK_COVERS_CAP) if chapters
                 else cutbar.HOOK_COVERS_CAP, cutbar.COVER_MIN_S))
    c += ("Tag every b-roll clip you place with `framing` — one of %s — "
          "read off its 9-frame contact sheet under analysis/sheets, and "
          "write it back into analysis/broll.json; consecutive covers in "
          "one beat change framing or move tighter. "
          % "/".join(cutbar.SHOT_SIZES))
    c += ("A beat quoting a flagged or superseded take needs a "
          "`flag_note` saying why that one is right anyway. ")
    c += ("To break chronology, declare a `threads` entry with a `why` and "
          "put its id on at least two beats. ")
    return c


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
    vo = float(b.get("vo_share", 0.60))
    mins = float(b.get("target_minutes", 10))
    # State the SHAPE, do not make the writer infer it from a number. A
    # 0.75-minute brief is a vertical Short with one loop and captions on
    # every line; a 25-minute one is a chaptered 16:9 episode. Inferring
    # that from target_minutes alone is exactly the kind of guess the
    # format fields were added to stop (2026-08-25).
    if str(b.get("delivery") or "long") == "short":
        clause = ("Caleb's brief: a VERTICAL SHORT of about %g minutes "
                  "(9:16, under a minute), with about %.0f%% of it carried "
                  "by VOICE-OVER. One loop, no chapter furniture, and the "
                  "payoff inside the runtime -- a short that saves its "
                  "answer for the end does not get watched to the end. "
                  "Every line is captioned, so write lines that read as "
                  "well as they sound. "
                  % (mins, vo * 100))
    else:
        clause = ("Caleb's brief: a ~%g-minute episode in %d chapters "
                  "(16:9 long-form), with "
                  "about %.0f%% of its running time carried by VOICE-OVER "
                  "rather than on-camera talking -- pitch "
                  "spines that fit that budget, and say so when the footage "
                  "cannot fill it honestly. "
                  % (mins, int(b.get("chapters", 6)), vo * 100))
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


def _editplan_prompt(slug, retry_notes=None) -> str:
    """`retry_notes` turns a second attempt into an EDIT rather than a
    rewrite: the staged file is still on disk and the notes say what is
    wrong with it, so the session fixes those lines instead of spending
    its minutes re-deriving a cut it already wrote."""
    clause = _brief_clause(slug)
    source = (EDITPLAN_SOURCE_SCRIPT if _script_origin(slug) == "script"
              else EDITPLAN_SOURCE_PITCH) % {"slug": slug}
    # a script outranks improvisation: when one exists the cut FOLLOWS it
    if (work_path(slug) / "script.json").exists():
        clause += ("work/%s/script.json is the approved SCRIPT -- the cut "
                   "follows it section by section: oncamera sections use "
                   "their cited take_id; vo sections use the recorded "
                   "vo_<section>_t<n> takes (ordinary speech takes after "
                   "ingest) with b-roll covering their ENTIRE beat -- a "
                   "teleprompter recording on screen is a mistake. Respect "
                   "the one-use-per-b-roll-clip rule. " % slug)
    retry = ""
    if retry_notes:
        retry = ("YOUR LAST ATTEMPT IS STILL AT work/%s/staging/"
                 "edit_plan.json and it did not pass. Fix these IN PLACE "
                 "rather than starting over: %s. "
                 % (slug, "; ".join(retry_notes[:6])))
    return EDITPLAN_PROMPT % {"slug": slug, "brief": clause,
                              "source": source,
                              "craft": _craft_clause(slug),
                              "retry": retry}


def _run_story(slug, log, set_pct):
    """Dispatch the story-designer as a headless Claude Code session — the
    same agent Caleb used to prompt by hand, now the desk's Pitch button.
    Same pattern as the fixer: the proof of work is the artifact changing,
    not the exit code."""
    # The lane guard lives HERE as well as in start(). start() is only the
    # queue's front door: a chain follower, a retry, or a direct call goes
    # straight to the runner and would have dispatched a real session for
    # a format that has no pitch. Found by an ad-hoc script doing exactly
    # that and spawning one (2026-08-25).
    if _script_origin(slug) == "script":
        raise JobError("a documentary has no pitch — the story is settled "
                       "by the interview on the Script desk")
    stories_path = work_path(slug) / "stories.json"
    before = stories_path.stat().st_mtime if stories_path.exists() else None
    log("[story] dispatching the story designer%s"
        % (" — fresh round over existing pitches" if before else ""))
    set_pct(5)
    _dispatch_json(_story_prompt(slug), log, set_pct, "story")
    after = stories_path.stat().st_mtime if stories_path.exists() else None
    if after is None or after == before:
        raise RuntimeError("session finished but stories.json did not "
                           "change — read the log")
    log("[story] pitches written — pick a direction on the Story desk")
    set_pct(100)


EDITPLAN_PROMPT = (
    "Write the edit plan for %(slug)s. %(brief)s"
    "Read .claude/agents/story-designer.md "
    "and act as that agent for the EDIT PLAN stage: %(source)s "
    "Read work/%(slug)s/analysis/ (takes, b-roll, timings) and "
    "write work/%(slug)s/staging/edit_plan.json that satisfies the "
    "agent's plan rules. WRITE TO staging/ — the runner validates what "
    "you leave there and promotes it; writing to "
    "work/%(slug)s/edit_plan.json directly replaces the built cut with "
    "something nothing has checked. Beat ids are MINTED BY THE ENGINE "
    "from the shot each beat shows, so any placeholder id will do and "
    "will be rewritten. %(craft)s%(retry)s"
    "Do NOT run conforms or renders, and do NOT touch DaVinci "
    "Resolve. The engine is running on :8765; leave it alone.")

# The two lanes hand the cut a different source. A visit is cut from the
# APPROVED PITCH; a documentary has no pitch at all — `_run_story` refuses
# to write one — and is cut from its APPROVED SCRIPT. The prompt named the
# pitch unconditionally, so a documentary that got past the precondition
# would have been told to read two files that cannot exist (2026-08-26).
EDITPLAN_SOURCE_PITCH = (
    "the latest round in work/%(slug)s/story_feedback.json is an APPROVING "
    "round — build the plan from its chosen direction in "
    "work/%(slug)s/stories.json, honoring its notes.")
EDITPLAN_SOURCE_SCRIPT = (
    "this is a documentary and has no pitch — work/%(slug)s/script.json is "
    "the APPROVED script and the cut is built from it, in order, section by "
    "section.")


INTERVIEW_PROMPT = (
    "Interview Caleb for The Ninth Room episode %(slug)s before writing "
    "anything. %(brief)sRead .claude/agents/story-director.md and act as "
    "that agent for its INTERVIEW stage. Read the brief, "
    "work/%(slug)s/research.json, and -- in the footage lane -- the "
    "approved direction in work/%(slug)s/stories.json plus the "
    "transcripts in work/%(slug)s/analysis/takes.json. Then write "
    "work/%(slug)s/script_questions.json exactly as your brief specifies, "
    "with \"stage\": \"%(stage)s\". AT MOST %(cap)d questions: ask only "
    "what you genuinely cannot decide from the material, cite the take, "
    "clip or fact behind any question about the material, and give EVERY "
    "question a `default` so skipping it is legal. Mark `required` only "
    "where proceeding on a guess would waste a whole draft. Do NOT write "
    "script.json in this stage. Validate before finishing: "
    "/usr/bin/python3 -c 'import json,sys; sys.path.insert(0,\".\"); "
    "from pipeline import schemas; "
    "print(schemas.validate_script_questions(json.load(open("
    "\"work/%(slug)s/script_questions.json\"))))' and fix every error. "
    "Do NOT touch DaVinci Resolve; the engine on :8765 is not yours.")


SCRIPT_PROMPT = (
    "Write the timed script for %(slug)s. %(brief)s%(lane)sRead "
    ".claude/agents/story-director.md and act as that agent for its "
    "%(stage)s stage. %(rounds)s"
    "Write work/%(slug)s/script.json with this exact shape: "
    "{\"slug\", \"origin\", \"option_id\" (footage lane only), \"round\", "
    "\"locked\": false, \"target_minutes\", \"retired_ids\": [], "
    "\"defaults_used\": [], \"chapters\": "
    "[{\"id\": \"CH1\", \"title\", \"target_s\", \"sections\": "
    "[{\"id\": \"CH1.S1\", \"kind\": \"oncamera\"|\"vo\"|\"desk\", "
    "\"text\", \"take_id\" (oncamera only), \"est_s\", \"rev\": 1, "
    "\"source\", \"visual\": {\"want\", \"why\", \"from\"}}]}]}. "
    "oncamera sections QUOTE a real take (take_id from "
    "analysis/takes.json, text = what it says, est_s = its trimmed span). "
    "vo sections are narration Caleb records LATER over pictures, and "
    "desk sections are written to be PERFORMED to camera at his desk; "
    "both are est_s = words/150*60. EVERY vo section carries a `visual` "
    "whose `why` leads with one of establish/illustrate/foretell/bridge/"
    "process. A line built on a research.json fact carries that fact's "
    "source_url as \"source\". Section ids are permanent: never renumber, "
    "never reuse a retired id, and bump a section's `rev` when you change "
    "its text -- recordings match by filename and a reused id makes an old "
    "take read as this line's. Then write a FRESH "
    "work/%(slug)s/script_questions.json at \"stage\": \"draft\" with the "
    "real open questions this draft raises (at most %(cap)d), including "
    "any structural change you want to propose. "
    "Before finishing, prove it -- validate_script AND script_notes must "
    "BOTH come back empty: "
    "/usr/bin/python3 -c 'import json,os,sys; sys.path.insert(0,\".\"); "
    "from pipeline import schemas; "
    "L=lambda p: json.load(open(p)) if os.path.exists(p) else None; "
    "W=\"work/%(slug)s/\"; s=L(W+\"script.json\"); "
    "b=L(W+\"story_brief.json\") or {}; "
    "print(schemas.validate_script(s, L(W+\"analysis/takes.json\"))); "
    "print(schemas.script_notes(s, b.get(\"vo_share\"), "
    "origin=b.get(\"origin\",\"footage\")))' "
    "-- fix every error and every note, then run it again until clean. "
    "Do NOT touch DaVinci Resolve; the engine on :8765 is not yours.")


def _script_prompt(slug) -> str:
    """The writer's prompt, carrying the lane and the round it is answering.

    The rounds clause is what makes this a collaboration rather than a
    retry: a revision is told to address exactly what Caleb wrote and to
    leave alone what he did not mention.
    """
    from . import schemas
    work = work_path(slug)
    origin = _script_origin(slug)
    existing = _read_json(work / "script.json")
    fb = _read_json(work / "script_feedback.json") or {}
    rounds = fb.get("rounds", [])
    if origin == "script":
        lane = ("This is a SCRIPT-LED episode: there is no footage and no "
                "pitch. The script IS the backbone -- build it from the "
                "brief and work/%s/research.json. Caleb presents at his "
                "desk, so `desk` sections carry the spine and `vo` lines "
                "connect them. It owes no ninth-room moment and no door "
                "meter. " % slug)
    else:
        lane = ("This is a VISIT: the latest round in "
                "work/%s/story_feedback.json approves a direction in "
                "work/%s/stories.json -- script THAT direction. Caleb "
                "hosts; Alma and Sofia are on camera with him. The "
                "episode owes one ninth-room moment, and the spine is "
                "WRITTEN -- `oncamera` takes support it, they do not "
                "carry it. " % (slug, slug))
    lane += ('Person: "I" is not banned anywhere -- it is Caleb\'s in both '
             'lanes, and "we" is for the family moving as one. On camera '
             'everyone speaks as themselves, so a take that says "I" stays '
             'exactly as it was said. ')
    if existing is not None:
        latest = next((r for r in reversed(rounds)
                       if r.get("decision") in ("direction", "answers")), {})
        parts = []
        if latest.get("notes"):
            parts.append("His direction: %s" % latest["notes"])
        if latest.get("answers"):
            parts.append("His answers: %s" % "; ".join(
                "%s = %s" % (k, v) for k, v in latest["answers"].items()))
        clause = ("You are REVISING work/%s/script.json (round %s). %s "
                  "Address exactly what he named and keep what he did not "
                  "mention; bump `round`. " %
                  (slug, existing.get("round"), " ".join(parts) or
                   "He asked for a revision."))
        stage = "REVISE"
    else:
        given = _script_answers_clause(work)
        clause = ("work/%s/script_questions.json holds your interview and "
                  "work/%s/script_feedback.json holds his answers. %s"
                  "Anything he did not answer runs on YOUR stated default "
                  "-- list those in `defaults_used`. " % (slug, slug, given))
        stage = "DRAFT"
    return SCRIPT_PROMPT % {"slug": slug, "brief": _brief_clause(slug),
                            "lane": lane, "stage": stage, "rounds": clause,
                            "cap": schemas.MAX_DRAFT_Q}


def _script_answers_clause(work) -> str:
    """Caleb's answers, in the prompt. Separate and pure so a test can
    prove they actually reach the writer -- the failure mode an interview
    invites is being politely ignored, exactly as the brief's was."""
    fb = _read_json(work / "script_feedback.json") or {}
    got = {}
    for r in fb.get("rounds", []) or []:
        for qid, val in (r.get("answers") or {}).items():
            if str(val or "").strip():
                got[str(qid)] = val
        if r.get("notes"):
            got.setdefault("_notes", r["notes"])
    if not got:
        return ""
    notes = got.pop("_notes", None)
    out = ""
    if got:
        out += "He answered: %s. " % "; ".join(
            "%s = %s" % (k, v) for k, v in sorted(got.items()))
    if notes:
        out += "His note: %s. " % notes
    return out


RESEARCH_PROMPT = (
    "Research %(location)s for The Ninth Room episode %(slug)s. It may be "
    "a PLACE we are visiting or a TOPIC the episode is about -- research "
    "whichever it is. Search the "
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
    work = work_path(slug)
    brief_p = work / "story_brief.json"
    # A visit names a place; a script-led episode names a topic. Either is
    # a legitimate thing to research, and an episode may carry both.
    location = ""
    if brief_p.exists():
        try:
            b = json.loads(brief_p.read_text())
            location = " -- ".join(
                p for p in (str(b.get("location") or "").strip(),
                            str(b.get("subject") or "").strip()) if p)
        except ValueError:
            pass
    if not location:
        raise RuntimeError("the brief has no subject -- name the place, "
                           "event or topic on the Story desk first")
    out_p = work / "research.json"
    before = out_p.stat().st_mtime if out_p.exists() else None
    log("[research] dispatching the researcher for %s" % location)
    _dispatch(RESEARCH_PROMPT % {"slug": slug, "location": location},
              log, set_pct, "research")
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


def _read_json(path, default=None):
    """Read a JSON artifact, or the default when it is absent or corrupt.
    Guards exist because the script lane has legitimately empty projects --
    an unguarded read of takes.json is what made a footage-free episode
    impossible to start at all (jobs.py, before 2026-08-24)."""
    import json
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return default


def _script_origin(slug) -> str:
    """Which lane this episode is in. `footage` = a visit, shot first.
    `script` = written first from a subject, with no footage yet."""
    b = _read_json(work_path(slug) / "story_brief.json", {}) or {}
    return "script" if str(b.get("origin") or "") == "script" else "footage"


def _run_interview(slug, log, set_pct):
    """Round 0: the director asks before it writes (Caleb, 2026-08-24 --
    "I need to be prompted interactively to collaborate with the agent
    before a script is finalized").

    This exists as its own job because the questions have to reach Caleb
    and come back before a single line is drafted. A writer that asked and
    answered itself would be the old one-shot wearing a costume.
    """
    from . import schemas
    work = work_path(slug)
    if not (work / "story_brief.json").exists():
        raise RuntimeError("no brief yet -- answer the brief on the Story "
                           "desk first: the director needs the budget and "
                           "the subject before it can ask anything useful")
    script_path = work / "script.json"
    if _read_json(script_path, {}).get("locked"):
        raise RuntimeError("the script is approved -- unlock it on the "
                           "Script desk before reopening the interview")
    origin = _script_origin(slug)
    if origin == "footage":
        rounds = (_read_json(work / "story_feedback.json", {}) or {}).get(
            "rounds", [])
        if not rounds or rounds[-1].get("decision") != "approve":
            raise RuntimeError("no approving round -- approve a direction on "
                               "the Story desk first")
    elif not (work / "research.json").exists():
        # The script lane has no footage, so research is the ONLY material
        # the director has. Interviewing without it would be asking Caleb
        # to supply what the pipeline is meant to fetch.
        # names the button as the SCRIPT lane labels it — this branch is
        # only reachable there, and "Research the place" is what the
        # filmed lane calls it
        raise RuntimeError("no research yet -- run Research the topic on "
                           "the Story desk; with no footage it is the only "
                           "material the director has")
    out = work / "script_questions.json"
    before = out.stat().st_mtime if out.exists() else None
    log("[interview] dispatching the story director for its questions")
    _dispatch_json(INTERVIEW_PROMPT % {"slug": slug,
                                       "brief": _brief_clause(slug),
                                       "stage": "interview",
                                       "cap": schemas.MAX_INTERVIEW_Q},
                   log, set_pct, "interview")
    after = out.stat().st_mtime if out.exists() else None
    if after is None or after == before:
        raise RuntimeError("session finished but script_questions.json did "
                           "not change -- read the log")
    doc = _read_json(out, {}) or {}
    errs = schemas.validate_script_questions(
        doc, _read_json(work / "script_feedback.json"))
    if errs:
        raise RuntimeError("the interview is malformed: " + "; ".join(errs[:4]))
    n = len(doc.get("questions", []))
    log("[interview] %d question(s) waiting on the Script desk -- answer "
        "what you have a view on, skip the rest and the defaults run" % n)
    set_pct(100)


def _run_script(slug, log, set_pct):
    """The Script desk's writer (Caleb, 2026-08-23): the timed script
    between an approved direction and the cut. Dispatch-and-verify like its
    siblings -- but here the proof is not just that script.json changed; it
    must also VALIDATE, because a script whose chapter sums ignore their
    targets is the budget fiction this whole feature exists to prevent.

    As of 2026-08-24 it is also REVISABLE. It used to refuse outright once
    script.json existed, which made the first draft the last word; now a
    rewrite is legal exactly when Caleb has asked for one, and refused once
    he has approved.
    """
    from . import schemas
    work = work_path(slug)
    origin = _script_origin(slug)
    script_path = work / "script.json"
    existing = _read_json(script_path)
    if origin == "footage":
        rounds = (_read_json(work / "story_feedback.json", {}) or {}).get(
            "rounds", [])
        if not rounds or rounds[-1].get("decision") != "approve":
            raise RuntimeError("no approving round -- approve a direction on "
                               "the Story desk first")
    questions = _read_json(work / "script_questions.json")
    feedback = _read_json(work / "script_feedback.json")
    if existing is not None:
        # A revision needs an instruction. Without this the button would
        # silently rewrite a script Caleb was happy with.
        if existing.get("locked"):
            raise RuntimeError("the script is approved -- unlock it on the "
                               "Script desk to revise it")
        rounds = (feedback or {}).get("rounds", [])
        if not any(r.get("decision") in ("direction", "answers")
                   for r in rounds):
            raise RuntimeError("nothing to revise from -- send direction or "
                               "answer the open questions on the Script desk")
    else:
        blocking = schemas.blocking_questions(questions, feedback)
        if blocking:
            raise RuntimeError(
                "waiting on you: %s. Answer on the Script desk (everything "
                "else runs on its default)" % ", ".join(blocking))
        if questions is None:
            raise RuntimeError("no interview yet -- run Interview me on the "
                               "Script desk so the director asks before it "
                               "writes")
    before = script_path.stat().st_mtime if script_path.exists() else None
    log("[script] dispatching the story director (%s lane%s)"
        % (origin, ", revising" if existing is not None else ""))
    _dispatch_json(_script_prompt(slug), log, set_pct, "script")
    if not script_path.exists():
        raise RuntimeError("session finished but script.json was not "
                           "written -- read the log")
    after = script_path.stat().st_mtime
    if before is not None and after == before:
        raise RuntimeError("session finished but script.json did not change "
                           "-- read the log")
    # The script lane has no takes, and that is legal: an unguarded read
    # here is what made a footage-free episode impossible to start.
    takes = _read_json(work / "analysis" / "takes.json")
    script_doc = _read_json(script_path, {})
    errs = schemas.validate_script(script_doc, takes)
    if errs:
        raise RuntimeError("script.json failed validation: " +
                           "; ".join(errs[:4]))
    # the VO dial, enforced against THIS episode's target rather than a
    # constant — the same shape the coverage job uses for coverage_notes
    brief_p = work / "story_brief.json"
    target = schemas.VO_TARGET_DEFAULT
    if brief_p.exists():
        try:
            target = float(json.loads(brief_p.read_text())
                           .get("vo_share", target))
        except (ValueError, TypeError):
            pass
    notes = schemas.script_notes(script_doc, target, origin=origin)
    if notes:
        raise RuntimeError("script.json misses the bar: " +
                           "; ".join(notes[:4]))
    log("[script] %.0f%% voice-over against a %.0f%% target"
        % (schemas.vo_share(script_doc) * 100, target * 100))
    budget = schemas.coverage_budget(
        script_doc, _read_json(work / "analysis" / "broll.json", {}))
    if budget.get("to_source_seconds"):
        log("[script] %.0f min of pictures to source -- %s"
            % (budget["to_source_seconds"] / 60.0,
               ", ".join("%s %.0fs" % (k, v) for k, v in
                         sorted(budget["declared_seconds"].items())
                         if k != "library")))
    still = schemas.open_questions(
        _read_json(work / "script_questions.json"),
        _read_json(work / "script_feedback.json"))
    if still:
        log("[script] the director left %d question(s) on this draft -- "
            "answer or approve on the Script desk" % len(still))
    log("[script] draft %s written -- read it on the Script desk, then "
        "approve it or send direction" % (script_doc.get("round") or 1))
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
    _dispatch_json(GRAPHICS_PROMPT % {"slug": slug}, log, set_pct, "graphics")
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
    work = work_path(slug)
    # WHICH APPROVAL GATES THE CUT DEPENDS ON THE LANE.
    #
    # A visit is cut from an approved pitch. A documentary has no pitch —
    # `_run_story` refuses to write one for this lane — so demanding
    # stories.json here made the cut UNREACHABLE: the script could be
    # written, interviewed over and approved, and "Build the cut" would
    # answer "no story pitches yet — pitch stories first" forever. A real
    # short-form documentary hit that dead end (2026-08-26).
    #
    # Its approval is the approved SCRIPT, which is the artifact the cut
    # is actually built from on this lane.
    if _script_origin(slug) == "script":
        script = _read_json(work / "script.json", None)
        if not script:
            raise RuntimeError("no script yet — interview and write it on "
                               "the Script desk first")
        if not script.get("locked"):
            raise RuntimeError("the script is not approved — approve it on "
                               "the Script desk; the cut is built from it")
        # AND THE LINES HAVE TO EXIST. The cut references recorded takes
        # by id, so without an ingest there is nothing to reference — the
        # designer reads `analysis/takes.json`, finds no file, and stops.
        #
        # It cost a full session to learn that: the agent ran, wrote a
        # careful account of what it could not do, and the job failed with
        # "session finished but edit_plan.json was not written" (measured
        # on the oligarchy short, 2026-08-26). A dispatched session is
        # billed minutes; a gate that a file check can answer must answer
        # before the dispatch, not after.
        if not (work / "analysis" / "takes.json").exists():
            raise RuntimeError(
                "the lines are not recorded yet — record them on the "
                "Script desk and let the analysis run; the cut is built "
                "from the takes, so there is nothing to cut from until "
                "then")
    else:
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
    # A LEFTOVER STAGED CUT IS A RETRY, NOT RUBBISH. A promote that
    # refused left the file exactly where the session put it, precisely so
    # the next attempt can be handed its own notes and fix them in place
    # instead of spending a second session re-deriving the same cut.
    from . import promote
    retry_notes = None
    if promote.staged_plan(slug).exists():
        try:
            chk = promote.check_cut(slug, staged=True)
            retry_notes = (chk["errors"] + chk["notes"]) or None
        except Exception:
            retry_notes = None
        if retry_notes:
            log("[editplan] a staged cut from a previous attempt is still "
                "here with %d finding(s) — handing them back rather than "
                "starting over" % len(retry_notes))
        else:
            promote.clear_staging(slug)
    log("[editplan] dispatching the story designer for the cut")
    set_pct(5)
    _dispatch_json(_editplan_prompt(slug, retry_notes), log, set_pct,
                   "editplan")
    # The runner promotes; the agent no longer publishes. Everything
    # promote_cut checks raises BEFORE the swap, so a refusal leaves the
    # built cut untouched and the staged file on disk to diagnose.
    r = promote.promote_cut(slug, reason="promote", log=log)
    log("[editplan] cut promoted — %d beats, ids minted by the engine; "
        "assemble builds the timeline next" % r["beats"])
    set_pct(100)


def _run_recut(slug, log, set_pct, arg=None):
    """Rebuild a cut that already exists, carrying what still applies.

    `_run_editplan` refuses when a plan exists, and that refusal stays
    honest — overwriting a cut the desks and reviews hang off is a
    decision, not a button press. THIS is the sanctioned door, and it
    differs from editplan in exactly two ways: it requires a plan rather
    than refusing one, and it hands `promote_cut` the plan being replaced
    so verdicts follow the SHOT through the id map instead of being
    thrown away.

    `arg` is Caleb's one line saying what this re-cut should improve.
    It is required, and that is pre-registration in miniature: a re-cut
    with no stated intent cannot be judged against anything afterwards.
    The guard is repeated here as well as in `start()` because a chain
    follower, a retry or a direct call goes straight to the runner — the
    lesson `_run_story` records at its own guard.
    """
    from . import promote
    work = work_path(slug)
    plan_path = work / "edit_plan.json"
    if not plan_path.exists():
        raise RuntimeError("there is no cut to re-cut — build one first")
    reason = str(arg or "").strip()
    if not reason:
        raise RuntimeError("say in one line what this re-cut should "
                           "improve — a re-cut with no stated intent "
                           "cannot be judged against the one it replaces")
    before = _read_json(plan_path, None)
    if before is None:
        raise RuntimeError("the built cut is not readable JSON")

    retry_notes = None
    if promote.staged_plan(slug).exists():
        try:
            chk = promote.check_cut(slug, staged=True)
            retry_notes = (chk["errors"] + chk["notes"]) or None
        except Exception:
            retry_notes = None
        if not retry_notes:
            promote.clear_staging(slug)

    log("[recut] rebuilding the cut — %s" % reason)
    set_pct(5)
    _dispatch_json(_editplan_prompt(slug, retry_notes) +
                   ("THIS IS A RE-CUT of an existing plan. What it must "
                    "improve: %s. The current cut is at "
                    "work/%s/edit_plan.json — read it, then write the NEW "
                    "one to staging/. " % (reason, slug)),
                   log, set_pct, "recut")
    r = promote.promote_cut(slug, reason="recut", note=reason,
                            carry_from=before, log=log)
    log("[recut] %d beats — %d verdicts carried, %d back in the queue, "
        "%d archived. Screening only what changed."
        % (r["beats"], len(r["carried"]), len(r["requeued"]),
           len(r["stranded"])))
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
    ideas_path = work_path("_scout") / "ideas.json"
    before = ideas_path.stat().st_mtime if ideas_path.exists() else None
    log("[scout] dispatching the idea scout")
    _dispatch(SCOUT_PROMPT, log, set_pct, "scout")
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


def _run_snapcuts(slug, log, set_pct):
    """Tighten cuts: move speech-clipping edges to acoustic troughs. The
    CLI verb, promoted to a job so the Review desk can reach it — and so
    the CHAIN can enforce the order this session got wrong once: proxies
    render from the ASSEMBLED timeline, so a snap that is not followed by
    assemble never reaches review playback (found live, 2026-08-23)."""
    if not (work_path(slug) / "edit_plan.json").exists():
        raise RuntimeError("no cut yet -- Build the cut first")
    from . import snap_cuts
    set_pct(10)
    snap_cuts.snap(slug, log=log)
    set_pct(100)


def _run_rendercards(slug, log, set_pct):
    """Approve & render every card that isn't current — one job instead of
    23 clicks (P4, 2026-08-23). _export_overlay is idempotent (an unchanged
    card reuses its file), so re-running after a partial failure only pays
    for what's missing."""
    from . import editroom
    state = editroom._overlays_state(slug)
    todo = [it["id"] for it in state["overlays"]
            if it["export"]["status"] != "current" and not it.get("prebaked")]
    if not todo:
        raise RuntimeError("every card is already rendered")
    log("[cards] %d to render" % len(todo))
    for i, cid in enumerate(todo):
        log("[cards] %s (%d/%d)" % (cid, i + 1, len(todo)))
        editroom._export_overlay(slug, cid, log=log)
        set_pct(int(5 + 90.0 * (i + 1) / len(todo)))
    set_pct(100)


PUBLISH_PROMPT = (
    "Write the publish package for The Ninth Room episode %(slug)s. Read "
    ".claude/agents/publish-writer.md and act as that agent: read the "
    "episode's script/story and the brand voice docs, write "
    "work/%(slug)s/publish.md exactly in the format the brief specifies "
    "(title options with honest scores, description, tags), and append "
    "the options to work/_channel/titles.json. Do NOT touch DaVinci "
    "Resolve or the engine on :8765.")


def _run_publish(slug, log, set_pct):
    """Upload-day package as a job (P9, 2026-08-24). Dispatch-and-verify:
    the proof is publish.md existing with all three sections."""
    work = work_path(slug)
    if not ((work / "edit_plan.json").exists()
            or (work / "script.json").exists()):
        raise RuntimeError("nothing to publish yet -- build the cut first")
    log("[publish] dispatching the publish writer")
    _dispatch(PUBLISH_PROMPT % {"slug": slug}, log, set_pct, "publish")
    md_path = work / "publish.md"
    if not md_path.exists():
        raise RuntimeError("session finished but publish.md was not "
                           "written -- read the log")
    md = md_path.read_text()
    for section in ("# Title options", "# Description", "# Tags"):
        if section not in md:
            raise RuntimeError("publish.md is missing '%s' -- the package "
                               "is incomplete" % section)
    log("[publish] package written -- copy it from the Export desk")
    set_pct(100)


HEARTBEAT_S = 30      # how often a silent session says it is still there
HEARTBEAT_CEIL = 90   # a heartbeat never claims the work is finished


def heartbeat_pct(elapsed_s: float, floor: int = 15,
                  ceil: int = HEARTBEAT_CEIL, half_life_s: float = 420.0):
    """PURE: where the bar sits after `elapsed_s` of a session we cannot
    measure. Asymptotic — it approaches `ceil` and never arrives, because
    the only honest statement is "still working", and a bar that reached
    100 would be a lie told by arithmetic."""
    import math
    span = ceil - floor
    return int(floor + span * (1 - math.exp(-elapsed_s / half_life_s)))


def _drain_with_heartbeat(proc, log, set_pct, what):
    """Stream a dispatched session's output, and tick while it is silent.

    `claude -p` buffers its whole reply until the session ends, so a job
    that dispatches one sat at exactly 15% with no note for its entire
    run — twenty minutes of looking identical to a hang. Caleb, watching
    a live edit-plan job: "still showing 15%" (2026-08-24).

    The drain moves to a thread so the tick is never blocked by a session
    that says nothing for ten minutes. What breaks if this is wrong: the
    tray goes back to lying by omission, and a wedged session gets
    diagnosed by killing the engine.
    """
    import threading
    import time
    t0 = time.time()
    last = [t0]

    def drain():
        for line in proc.stdout:
            line = line.rstrip()
            if line:
                log(line)
                last[0] = time.time()

    t = threading.Thread(target=drain, daemon=True)
    t.start()
    while proc.poll() is None:
        time.sleep(1)
        now = time.time()
        if now - last[0] >= HEARTBEAT_S:
            mins = (now - t0) / 60.0
            set_pct(heartbeat_pct(now - t0))
            log("[%s] still working — %.0fm elapsed, session silent"
                % (what, mins))
            last[0] = now
    t.join(timeout=5)
    return proc.wait()


def _dispatch(prompt, log, set_pct, what):
    """One headless session, streamed to the job log — the shared tail
    every agent job used to copy by hand."""
    import subprocess
    set_pct(5)
    proc = subprocess.Popen(
        [CLAUDE_BIN, "-p", prompt,
         "--dangerously-skip-permissions"],
        cwd=str(PROJECT_ROOT), stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, text=True)
    set_pct(15)
    rc = _drain_with_heartbeat(proc, log, set_pct, what)
    if rc != 0:
        raise RuntimeError("%s session exited %d -- see the log"
                           % (what, rc))


def _run_retention(slug, log, set_pct):
    """The first pass (P10): pacing flags waiting in the queue before
    Caleb opens it. Auto-chained after assemble, so the guards keep it
    cheap and polite: no cut or no proxies -> refuse; ANY human verdict
    already on file -> refuse (first pass only — after that, re-review
    is human territory and a session would be noise)."""
    import json
    work = work_path(slug)
    if not (work / "edit_plan.json").exists():
        raise RuntimeError("no cut yet")
    from . import beat_identity
    if not beat_identity.beat_proxies(work / "proxies"):
        raise RuntimeError("no previews yet -- assemble first")
    rv = work / "review.json"
    if rv.exists():
        entries = json.loads(rv.read_text())
        if any(e.get("status") and e.get("by") != "retention-editor"
               for e in entries.values()):
            raise RuntimeError("humans are already reviewing -- the first "
                               "pass only runs on a fresh cut")
    log("[retention] dispatching the retention editor")
    _dispatch(
        "Run the retention pass on The Ninth Room episode %s. Read "
        ".claude/agents/retention-editor.md and act as that agent (the "
        "job-kind-retention section): read the cut and file pacing flags "
        "into work/%s/review.json exactly in the desk's shape, never "
        "touching an entry a human wrote. Do NOT touch DaVinci Resolve "
        "or the engine on :8765." % (slug, slug),
        log, set_pct, "retention")
    set_pct(100)


def _run_hook(slug, log, set_pct):
    if not (work_path(slug) / "edit_plan.json").exists():
        raise RuntimeError("no cut yet")
    log("[hook] dispatching the hook doctor")
    _dispatch(
        "Doctor the hook of The Ninth Room episode %s. Read "
        ".claude/agents/retention-editor.md and act as that agent's hook "
        "doctor: score the cold open, pitch two alternates from existing "
        "takes (cite take ids), write it as BT01's review note. Do NOT "
        "touch DaVinci Resolve or the engine on :8765." % slug,
        log, set_pct, "hook")
    set_pct(100)


def _run_qcgate(slug, log, set_pct):
    """Mechanical ship gate (P10): MEASURED checks on the newest master —
    no session, no vibes. Writes work/<slug>/qc_report.json; the Export
    checklist renders the rows."""
    import json
    import re as re_mod
    import subprocess
    work = work_path(slug)
    masters = sorted((work / "deliverables").glob("*.mp4")) \
        if (work / "deliverables").is_dir() else []
    masters = [m for m in masters if not m.name.startswith("_tmp")]
    if not masters:
        raise RuntimeError("no master yet -- render first")
    m = masters[-1]
    rows = []
    set_pct(10)
    # duration vs the assembled timeline
    tl_p = work / "analysis" / "timeline_map.json"
    probe = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json",
         "-show_format", "-show_streams", str(m)],
        capture_output=True, text=True, timeout=120)
    info = json.loads(probe.stdout or "{}")
    dur = float(info.get("format", {}).get("duration", 0) or 0)
    vstream = next((st for st in info.get("streams", [])
                    if st.get("codec_type") == "video"), {})
    if tl_p.exists():
        tl = json.loads(tl_p.read_text())
        want = max((b["record_e"] for b in tl.get("beats", [])), default=0)
        ok = abs(dur - want) < 2.0
        rows.append({"id": "qc_duration", "label": "Master length matches "
                     "the cut", "ok": ok,
                     "detail": "%.1fs vs %.1fs planned" % (dur, want)})
    # Against the TIMELINE's canvas, not a 1920 floor.
    #
    # `width >= 1920` passes a 1080p master rendered from a 4K timeline —
    # which is exactly what was happening, because the render never pinned
    # its output size and took whatever preset was selected in Resolve
    # (2026-08-27). A floor answers "is this big enough for YouTube"; the
    # question worth asking is "is this what we cut".
    want = None
    if tl_p.exists():
        try:
            from .timeline import CANVAS
            want = CANVAS[json.loads(tl_p.read_text())["orientation"]]
        except (ValueError, KeyError, ImportError):
            want = None
    got = (int(vstream.get("width", 0) or 0), int(vstream.get("height", 0) or 0))
    rows.append({"id": "qc_resolution", "label": "Resolution",
                 "ok": (got == tuple(want)) if want else got[0] >= 1920,
                 "detail": ("%dx%d" % got) if not want or got == tuple(want)
                 else "%dx%d — the cut is %dx%d" % (got[0], got[1], want[0], want[1])})
    set_pct(40)
    # loudness: broadcast-ish window for YouTube (-16 +/- 3 LUFS)
    loud = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", str(m), "-map", "a",
         "-af", "ebur128", "-f", "null", "-"],
        capture_output=True, text=True, timeout=1800)
    mI = re_mod.findall(r"I:\s+(-?[\d.]+) LUFS", loud.stderr)
    if mI:
        lufs = float(mI[-1])
        rows.append({"id": "qc_loudness", "label": "Loudness",
                     "ok": -19.0 <= lufs <= -13.0,
                     "detail": "%.1f LUFS (target -16 +/- 3)" % lufs})
    set_pct(80)
    # dead air / black at the head (a broken conform's classic tell)
    black = subprocess.run(
        ["ffmpeg", "-hide_banner", "-t", "5", "-i", str(m),
         "-vf", "blackdetect=d=1.0", "-an", "-f", "null", "-"],
        capture_output=True, text=True, timeout=300)
    rows.append({"id": "qc_head", "label": "No black at the head",
                 "ok": "black_start:0" not in black.stderr,
                 "detail": ("opens on black" if "black_start:0"
                            in black.stderr else "picture from frame one")})
    report = {"master": m.name, "ts": int(time.time()), "rows": rows}
    _write = work / "qc_report.json"
    tmp = _write.with_suffix(".tmp")
    tmp.write_text(json.dumps(report, indent=2))
    os.replace(tmp, _write)
    bad = [r for r in rows if not r["ok"]]
    log("[qc] %d checks, %d failing" % (len(rows), len(bad)))
    set_pct(100)


def _run_perf(slug, log, set_pct):
    """Channel-level (slug ignored like scout): the analyst reads the
    stats drop and writes insights.json for the Ideas desk."""
    stats = work_path("_channel") / "stats"
    if not stats.is_dir() or not any(stats.glob("*.csv")):
        raise RuntimeError("no stats yet -- export CSVs from YouTube "
                           "Studio into work/_channel/stats/")
    log("[perf] dispatching the performance analyst")
    _dispatch(
        "Analyze the channel stats for The Ninth Room. Read "
        ".claude/agents/performance-analyst.md and act as that agent "
        "(the YouTube export drop contract): read work/_channel/stats/, "
        "write work/_channel/insights.json in the specified shape. Do "
        "NOT touch DaVinci Resolve or the engine on :8765.",
        log, set_pct, "perf")
    if not (work_path("_channel") / "insights.json").exists():
        raise RuntimeError("session finished but insights.json was not "
                           "written -- read the log")
    set_pct(100)


def _run_retro(slug, log, set_pct):
    work = work_path(slug)
    masters = sorted((work / "deliverables").glob("*.mp4")) \
        if (work / "deliverables").is_dir() else []
    if not masters:
        raise RuntimeError("nothing shipped yet -- the retro follows the "
                           "publish")
    stats = work_path("_channel") / "stats"
    if not stats.is_dir() or not any(stats.glob("*.csv")):
        raise RuntimeError("no stats yet -- export CSVs from YouTube "
                           "Studio into work/_channel/stats/")
    log("[retro] dispatching the episode retro")
    _dispatch(
        "Run the retro for The Ninth Room episode %s. Read "
        ".claude/agents/episode-retro.md and act as that agent. Do NOT "
        "touch DaVinci Resolve or the engine on :8765." % slug,
        log, set_pct, "retro")
    set_pct(100)


def _run_diagnose(slug, log, set_pct, arg=None):
    """The pipeline doctor: reads a FAILED job's log and writes the
    one-sentence cause. `arg` is the failed job's id."""
    jid = arg or ""
    target = _jobs.get(jid)
    if target is None or target.get("state") != "failed":
        raise RuntimeError("diagnose wants a FAILED job id")
    log_path = LOG_DIR / ("%s.log" % jid)
    if not log_path.exists():
        raise RuntimeError("that job left no log")
    log("[doctor] dispatching on %s (%s)" % (jid, target.get("kind")))
    _dispatch(
        "A Ninth Room engine job failed. Read "
        ".claude/agents/pipeline-doctor.md and act as that agent. The "
        "job: kind=%s slug=%s. Its log: %s. Write "
        "work/%s/diagnosis.md with the one-sentence cause on line 1. "
        "Fix only what the brief calls safely fixable."
        % (target.get("kind"), slug, log_path, slug),
        log, set_pct, "diagnose")
    d = work_path(slug) / "diagnosis.md"
    if d.exists():
        first = d.read_text().strip().splitlines()
        if first:
            _update(jid, error=(target.get("error", "") or "")[:120]
                    + " · doctor: " + first[0][:150])
            _notify("Diagnosis", first[0][:160])
    set_pct(100)


def _dispatch_json(prompt, log, set_pct, what):
    """A headless session via stream-json: assistant text is teed to the
    job log LIVE, and the final result event's usage comes back — the
    token/cost numbers the board's cost events need (probed 2026-08-24:
    input/output/cache tokens, total_cost_usd, durations all present)."""
    import json as _json
    import subprocess
    set_pct(5)
    proc = subprocess.Popen(
        [CLAUDE_BIN, "-p", prompt,
         "--output-format", "stream-json", "--verbose",
         "--dangerously-skip-permissions"],
        cwd=str(PROJECT_ROOT), stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, text=True)
    set_pct(15)
    usage = {}
    seen_session = [False]
    t0 = time.time()
    last = [t0]
    # How many tool steps the session has taken. The heartbeat used to say
    # "session silent" whatever was happening, which is only half true: a
    # session reading files is working hard and saying nothing, and that
    # reads very differently from one that is genuinely stuck.
    steps = [0]
    # Captured HERE, on the worker thread, and closed over. The drain runs
    # on its own thread with its own empty thread-local, so reading the
    # current job from inside it finds nothing and the id never lands.
    jid = _current_jid()

    def drain():
        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue
            # NOT here. The timer must measure how long it has been since
            # anything was SAID, and most lines on this stream are tool
            # events that say nothing. Resetting on every one of them meant
            # a session reading ninety-four takes files kept the heartbeat
            # permanently fresh while the log sat frozen on its last
            # sentence and the bar sat on heartbeat_pct's 15% floor — the
            # exact "still showing 15%" symptom the heartbeat was written
            # to end, returning whenever the session is BUSY rather than
            # idle (Caleb, 2026-08-26, 13.5 minutes into a live script
            # job). The plain dispatcher never had this: every line it
            # reads is a line it logs.
            try:
                ev = _json.loads(line)
            except ValueError:
                log(line)
                last[0] = time.time()
                continue
            # Every event carries it; the first one is enough. Stamped as
            # soon as it arrives rather than at the end, so a session that
            # hangs or crashes is still inspectable afterwards.
            if not seen_session[0] and ev.get("session_id"):
                seen_session[0] = True
                _note_session(str(ev["session_id"]), jid)
            etype = ev.get("type")
            if etype == "assistant":
                for block in (ev.get("message") or {}).get("content", []):
                    if block.get("type") == "tool_use":
                        steps[0] += 1
                    if block.get("type") == "text" and block.get("text"):
                        for tl in block["text"].splitlines():
                            if tl.strip():
                                log(tl)
                                # said something: the clock starts again
                                last[0] = time.time()
            elif etype == "result":
                u = ev.get("usage") or {}
                usage.update({
                    "tokens": (u.get("input_tokens", 0)
                               + u.get("output_tokens", 0)
                               + u.get("cache_read_input_tokens", 0)
                               + u.get("cache_creation_input_tokens", 0)),
                    "usd": ev.get("total_cost_usd", 0),
                    "ms": ev.get("duration_ms", 0)})

    # Same heartbeat the plain dispatcher has. Reading the stream on THIS
    # thread would put the tick behind a session that says nothing for ten
    # minutes, which is the "still showing 15%" bug all over again.
    t = threading.Thread(target=drain, daemon=True)
    t.start()
    while proc.poll() is None:
        time.sleep(1)
        now = time.time()
        if now - last[0] >= HEARTBEAT_S:
            set_pct(heartbeat_pct(now - t0))
            log("[%s] still working — %.0fm elapsed, %s"
                % (what, (now - t0) / 60.0,
                   ("%d steps so far" % steps[0]) if steps[0]
                   else "session silent"))
            last[0] = now
    t.join(timeout=5)
    rc = proc.wait()
    if rc != 0:
        raise RuntimeError("%s session exited %d -- see the log"
                           % (what, rc))
    return usage


def _run_room(slug, log, set_pct):
    """One stage of the production room (team plan P1): reap dead claims,
    dispatch the showrunner as Team Lead, bill the run onto the board,
    and refuse to accept an invalid event log back."""
    import json as _json
    from . import board
    if not (work_path(slug) / "footage").is_dir() \
            and not (work_path(slug) / "edit_plan.json").exists():
        raise RuntimeError("nothing to produce yet -- add footage first")
    reaped = board.reap(slug, log=log)
    if reaped:
        log("[room] %d task(s) re-opened before convening" % len(reaped))
    log("[room] dispatching the showrunner")
    usage = _dispatch_json(
        "Run the current stage of The Ninth Room episode %s as its "
        "showrunner. Read .claude/agents/showrunner.md and act as that "
        "agent: the board is work/%s/production.json; the arithmetic "
        "checker verb is `/usr/bin/python3 -m pipeline.cli board-check "
        "%s <task_id> <craft>`; teammate scorecards go to the path "
        "`/usr/bin/python3 -m pipeline.cli scorecard-path %s <task_id>` "
        "prints. Stop at the stage boundary or a human gate. Do NOT "
        "touch DaVinci Resolve or the engine on :8765."
        % (slug, slug, slug, slug),
        log, set_pct, "room")
    board.append(slug, [{"type": "cost", "by": "engine",
                         "task_id": "_room",
                         "tokens": usage.get("tokens", 0),
                         "usd": usage.get("usd", 0),
                         "ms": usage.get("ms", 0)}], expect_by="engine")
    from . import schemas
    errs = schemas.validate_production(board.read(slug))
    if errs:
        raise RuntimeError("the room left an invalid board: %s" % errs[0])
    tasks = board.fold(slug).get("tasks", {})
    states = {}
    for tid, card in tasks.items():
        if tid.startswith("_"):
            continue  # cost pseudo-tasks are bookkeeping, not work
        states[card["status"]] = states.get(card["status"], 0) + 1
    log("[room] board: %s · %.2f USD this run"
        % (", ".join("%d %s" % (v, k) for k, v in sorted(states.items()))
           or "empty", usage.get("usd", 0)))
    set_pct(100)


def _run_coverage(slug, log, set_pct):
    """The b-roll pass (2026-08-24, Caleb: "supportive of the story, not
    a bombardment of noise"). Dispatch-and-verify with a MECHANICAL bar:
    the session must leave validate_edit_plan AND coverage_notes empty,
    or the job fails — craft is checked, not trusted. Beats whose covers
    changed get their verdicts reset (notes survive); assemble chains."""
    import json
    work = work_path(slug)
    plan_path = work / "edit_plan.json"
    if not plan_path.exists():
        raise RuntimeError("no cut yet -- Build the cut first")
    if not (work / "analysis" / "broll.json").exists():
        raise RuntimeError("no b-roll catalog -- analyze footage first")
    before = {b["id"]: json.dumps(b.get("broll") or [], sort_keys=True)
              for b in json.loads(plan_path.read_text()).get("beats", [])}
    log("[coverage] dispatching the coverage editor")
    _dispatch_json(
        "Run the b-roll pass on The Ninth Room episode %s. Read "
        ".claude/agents/coverage-editor.md and act as that agent: re-edit "
        "every cover in work/%s/edit_plan.json against the b-roll grammar "
        "(the four justifications, required why), prove both checkers "
        "empty before finishing. Do NOT touch DaVinci Resolve or the "
        "engine on :8765." % (slug, slug),
        log, set_pct, "coverage")
    from . import schemas
    plan = json.loads(plan_path.read_text())
    takes = json.loads((work / "analysis" / "takes.json").read_text())
    broll = json.loads((work / "analysis" / "broll.json").read_text())
    errs = schemas.validate_edit_plan(plan, takes, broll)
    if errs:
        raise RuntimeError("the pass broke the plan: %s" % errs[0])
    # broll is passed so the tag lift can fire — without the catalog
    # nothing can be tag-matched and the caps stay where they were
    notes = schemas.coverage_notes(plan, takes, broll)
    if notes:
        raise RuntimeError("the pass left craft violations: %s (+%d more)"
                           % (notes[0], len(notes) - 1))
    changed = [b["id"] for b in plan.get("beats", [])
               if json.dumps(b.get("broll") or [], sort_keys=True)
               != before.get(b["id"], "[]")]
    from . import editroom
    for bid in changed:
        editroom._reset_review(slug, bid)
    log("[coverage] %d beats re-covered -- their verdicts reset (notes "
        "kept); assembling next" % len(changed))
    # S5's gear change, reported and NOT gated (2026-08-27). coverage_notes
    # is required empty by this job, so a threshold in there would fail a
    # real cut on a number nobody has calibrated. Watch it first.
    g = schemas.gear_change(plan, takes)
    if g["vo_beats"]:
        log("[coverage] gear change: VO %.1fs mean shot vs scene %.1fs "
            "(ratio %.2f) -- Yes Theory ran 1.8 / 4.0, ratio 2.22"
            % (g["vo_mean_s"], g["scene_mean_s"], g["ratio"]))
    else:
        log("[coverage] gear change: no VO beats in this cut, so there is "
            "one texture end to end -- scene mean shot %.1fs"
            % g["scene_mean_s"])
    set_pct(100)


# Labels are user-facing (tray, notifications): desk vocabulary — clip,
# preview, render — never internal jargon (P1 copy pass, 2026-08-23).
SOURCING_PROMPT = (
    "Propose supporting coverage for %(slug)s. Read "
    ".claude/agents/asset-sourcer.md and act as that agent in its PROPOSE "
    "phase. %(budget)s"
    "Read work/%(slug)s/script.json (the approved script), "
    "work/%(slug)s/analysis/broll.json (the library we already shot -- "
    "descriptions and durations) and the B-roll grammar section of "
    ".claude/agents/story-designer.md. For EVERY section with "
    "\"kind\": \"vo\", decide whether the library can honestly cover that "
    "line: an establisher for the place it names, the thing it names, or "
    "the work it describes. Where it cannot, append a round to "
    "work/%(slug)s/asset_requests.json with this shape: "
    "{\"ts\", \"section_id\", \"line\" (the VO text), \"why\" (one clause "
    "on what the library lacks), \"candidates\": [...], "
    "\"status\": \"proposed\"}. Three to six candidates per gap. "
    "RESOLVE every candidate to a REAL ITEM -- actually search, open the "
    "file's own page, and record what is there. Caleb reviews these as "
    "pictures, not as search terms, and approves the one he wants. Each "
    "candidate is {\"query\" (what you searched), \"source\", "
    "\"kind\": \"image\"|\"video\", \"page\" (the item's own page, where "
    "the licence is stated), \"preview\" (a direct thumbnail/still URL "
    "that renders in an img tag), \"video\" (a direct playable mp4 URL, "
    "video candidates only), \"license\" (READ OFF THE PAGE, not "
    "predicted), \"attribution\" (the exact string if the licence needs "
    "one), \"note\"}. A candidate with no `preview` cannot be looked at "
    "and does not count -- drop it and find one that can. Do not "
    "hotlink-guess a URL: open the page and take the real one. "
    "DOWNLOAD NOTHING and write no files under assets/ -- Caleb approves "
    "each round first, and a file on disk before that decision is a "
    "licence choice made on his behalf. Prefer the library over a "
    "proposal: a gap you invent costs him money and an hour. "
    "Do NOT touch DaVinci Resolve or the engine on :8765.")

SOURCING_FETCH_PROMPT = (
    "Fetch the APPROVED coverage for %(slug)s. Read "
    ".claude/agents/asset-sourcer.md and act as that agent in its FETCH "
    "phase: work/%(slug)s/asset_requests.json holds rounds; work ONLY "
    "those with \"status\": \"approved\" AND \"kind\": \"source\". A round "
    "whose kind is \"requirement\" is work Caleb or the overlay kit must "
    "do -- there is nothing to buy, and sourcing one anyway buys the "
    "picture he asked to have drawn. Ignore every other round. "
    "IF THE ROUND CARRIES \"chosen\": <n>, that is the candidate Caleb "
    "LOOKED AT and picked -- fetch THAT item from its `page`/`video` url "
    "and do not search for something better. He approved a picture, not "
    "a search, and arriving with a different file than the one he "
    "approved is the whole failure this replaced. Only when a round has "
    "no `chosen` do you pick the best match yourself. "
    "NEVER refuse a gap over its licence (changed 2026-08-25): "
    "fetch the best match every time and RECORD what the licence "
    "actually is -- the real terms when the page states them, plain "
    "words when it does not (\"page states none -- unverified\", "
    "\"editorial use only per source\", \"watermarked preview\"). "
    "Never blank, never a guess, never round unclear up to fine; Caleb "
    "clears the doubtful ones on the desk. "
    "PREFER MOVING PICTURE: the format is voice-over led, so a "
    "still holds the screen for six seconds while a clip holds it for as "
    "long as the line runs. Search VIDEO first on every gap (Pexels and "
    "Pixabay both host it) and fall back to a still only when no clip of "
    "the subject exists -- the first real run returned five stills for "
    "five gaps without trying video once. Download into "
    "work/%(slug)s/assets/, "
    "append a row to work/%(slug)s/assets/assets.json carrying its "
    "licence and attribution plus \"query\" and \"what\", and set that "
    "round's status to \"done\". A candidate whose page states no licence is still sourced -- "
    "recorded as unverified, not skipped. "
    "Do NOT touch DaVinci Resolve or the engine on :8765.")


def _sourcing_budget_clause(slug) -> str:
    """The arithmetic, in the prompt, so the proposals are sized to a real
    shortfall instead of an appetite.

    The two lanes need opposite framings. A VISIT has a library and a
    shortfall against it. A SCRIPT-LED episode has no library at all, so a
    shortfall would read "everything is missing" -- true, useless, and an
    invitation to propose the whole film. There the SCRIPT is the brief:
    every vo line already named the picture it wants and where it should
    come from, so the budget is that declaration, totalled.
    """
    work = work_path(slug)
    script = _read_json(work / "script.json")
    if script is None:
        return ""
    from . import schemas as schemas_mod
    broll = _read_json(work / "analysis" / "broll.json") or {}
    b = schemas_mod.coverage_budget(script, broll)
    if _script_origin(slug) == "script":
        declared = b.get("declared_seconds") or {}
        parts = ", ".join("%s %.0fs" % (k, v)
                          for k, v in sorted(declared.items())) or "nothing"
        return ("Budget: %.0f minutes of narration, and this episode has NO "
                "footage of its own -- the script is the brief. EVERY "
                "section carrying a `visual` block declares where its "
                "picture comes from, desk sections included: a desk line "
                "is performed to camera and usually needs nothing, but "
                "when it names a cutaway that cutaway is owed like any "
                "other. Totalled: %s. About %.0f minutes of that has to be "
                "sourced or made. Work to those declarations rather than "
                "inventing needs, and leave nothing that declares a "
                "picture without one. "
                % (b["vo_seconds"] / 60.0, parts,
                   b.get("to_source_seconds", 0) / 60.0))
    return ("Budget: %.0f minutes of narration to cover, %.0f minutes of "
            "library in hand across %d clips (ratio %s). Each clip may be "
            "used ONCE, so a ratio near 1 means the cut cannot afford to "
            "reject anything -- propose accordingly, and propose nothing "
            "when the library is comfortable. "
            % (b["vo_seconds"] / 60.0, b["library_seconds"] / 60.0,
               b["library_clips"], b["ratio"]))


SOURCING_SCRIPT_LANE = (
    "This episode is SCRIPT-LED: there is no footage and no b-roll "
    "catalog, and that is normal -- the pictures do not exist yet, which "
    "is why you are here. Read work/%(slug)s/script.json and treat each "
    "section's `visual` block as the brief: `want` is what must be on "
    "screen, `why` is the justification it has to serve, and `from` is "
    "where it should come from. Honour `from`:\n"
    "  stock / archival -- propose candidates as usual.\n"
    "  graphic -- do NOT propose stock. Write a requirement saying what "
    "the overlay kit must draw (a map, a diagram, a stat card), because "
    "buying a picture of a thing we would rather draw is money wasted.\n"
    "  shoot -- do NOT propose stock. Write a requirement telling Caleb "
    "what HE has to film: the shot, the framing, and why nothing bought "
    "will do.\n"
    "  library -- there is no library here; treat it as an error and say "
    "so rather than silently sourcing it.\n"
    "Every entry gets \"kind\": \"source\" (something to fetch) or "
    "\"requirement\" (something Caleb or the kit must make), so the desk "
    "can separate what it can buy from what he still owes the episode. A "
    "requirement carries no candidates. ")


def _sourcing_prompt(slug) -> str:
    """The propose prompt, with the lane's own framing folded in.

    The two halves have to AGREE about what owes a picture. They did not:
    the lane framing said "each section's `visual` block" while the budget
    clause said "its lines" over a total that counted only `vo`. The agent
    worked to the arithmetic, covered all seven vo lines, and never saw
    CH1.S2 -- a desk section declaring a stock cutaway (2026-08-26).
    """
    lane = (SOURCING_SCRIPT_LANE % {"slug": slug}
            if _script_origin(slug) == "script" else "")
    return SOURCING_PROMPT % {"slug": slug,
                              "budget": _sourcing_budget_clause(slug) + lane}


def _run_sourcing(slug, log, set_pct, arg=None):
    """Propose supporting coverage, or fetch what Caleb approved.

    Two phases with a HUMAN GATE between them (Caleb, 2026-08-24):
    proposing costs a session, fetching costs licences and disk. The
    agent that judges what is missing is not allowed to also decide what
    gets downloaded.
    """
    work = work_path(slug)
    script = _read_json(work / "script.json")
    if script is None:
        raise JobError("no script yet — sourcing reads the approved script")
    origin = _script_origin(slug)
    # The script lane has no footage and therefore no b-roll catalog, and
    # that is its normal state rather than a missing step: the pictures do
    # not exist yet, which is the entire reason this stage runs. Demanding
    # the catalog made format B unable to reach sourcing at all — the same
    # shape of bug as the unguarded takes.json read (Caleb, 2026-08-25).
    if origin != "script" and not (work / "analysis" / "broll.json").exists():
        raise JobError("no b-roll catalog yet — ingest first")
    # And in that lane the script IS the brief for what to buy, so buying
    # against a draft he has not approved spends real money on words that
    # are about to change. The footage lane keeps its old behaviour: its
    # scripts predate the approve gate.
    if origin == "script" and not script.get("locked"):
        raise JobError("the script is not approved yet — approve it on the "
                       "Script desk first; sourcing buys against the words")
    fetch = str(arg or "").lower() == "fetch"
    rq = work / "asset_requests.json"
    if fetch:
        rounds = []
        if rq.exists():
            try:
                rounds = json.loads(rq.read_text()).get("rounds", [])
            except ValueError:
                rounds = []
        # A requirement cannot be fetched: it is work Caleb or the kit must
        # do. Counting one as "approved and ready" sends the fetcher out to
        # buy the picture he asked to have drawn -- and refusing with
        # "nothing approved" after he approved eight of them is exactly as
        # confusing (2026-08-25).
        buyable = [r for r in rounds
                   if r.get("status") == "approved"
                   and r.get("kind", "source") == "source"]
        if not buyable:
            waiting = sum(1 for r in rounds if r.get("status") == "approved")
            if waiting:
                raise JobError(
                    "the %d approved round(s) are all things to MAKE, not "
                    "buy — the overlay kit draws them or you film them; "
                    "there is nothing to fetch" % waiting)
            raise JobError("nothing approved — approve a proposal first")
    # Retire proposals the script has moved past, BEFORE proposing more.
    # A revision can turn "find archival of this" into "the kit draws it",
    # and the old proposal stays at `proposed` looking exactly like a live
    # one -- approve it and the fetch buys the thing Caleb decided not to.
    if not fetch:
        from . import schemas
        reqs = _read_json(rq) or {}
        stale = schemas.superseded_requests(
            _read_json(work / "script.json") or {}, reqs)
        if stale:
            for i in stale:
                reqs["rounds"][i]["status"] = "superseded"
                reqs["rounds"][i]["superseded_ts"] = int(time.time())
            rq.write_text(json.dumps(reqs, indent=1))
            log("[sourcing] %d earlier proposal(s) retired -- the script no "
                "longer asks to buy those" % len(stale))
    before = rq.stat().st_mtime if rq.exists() else None
    started_ts = time.time()
    prompt = ((SOURCING_FETCH_PROMPT % {"slug": slug}) if fetch
              else _sourcing_prompt(slug))
    log("[sourcing] dispatching the asset sourcer to %s"
        % ("fetch approved rounds" if fetch else "propose gaps"))
    _dispatch(prompt, log, set_pct, "sourcing")
    after = rq.stat().st_mtime if rq.exists() else None
    if after is None or after == before:
        # A NO-OP IS NOT AUTOMATICALLY A FAILURE HERE, and this is the one
        # stage where that distinction is real.
        #
        # Proposing sits behind a HUMAN GATE: rounds wait at `proposed`
        # until they are approved, and the sourcer is built not to
        # duplicate work already awaiting a verdict — a second identical
        # round would put the same decisions on the desk twice. The mtime
        # proof cannot tell "did nothing because nothing was needed" from
        # "did nothing because it broke", so it called a correct refusal a
        # failure and told Caleb to read the log (2026-08-26, the
        # oligarchy short: seven live proposals, agent declined to
        # re-propose, job FAILED).
        #
        # `unproposed_sections` is what tells them apart, and when the
        # answer is "it missed some" it can NAME them — which the old
        # message never did. On that same run it did miss one: CH1.S2, a
        # desk line that declares a stock cutaway, while all seven vo
        # lines were covered.
        from . import schemas as _sc
        gaps = (_sc.unproposed_sections(_read_json(work / "script.json") or {},
                                        _read_json(rq) or {})
                if not fetch else [])
        if not fetch and not gaps and rq.exists():
            log("[sourcing] nothing new to propose — every line that wants a "
                "picture already has one waiting on your verdict")
            set_pct(100)
            return
        if gaps:
            raise RuntimeError(
                "session finished and proposed nothing, but %s still %s no "
                "picture — read the log"
                % (", ".join(gaps[:4]) + (" (+%d more)" % (len(gaps) - 4)
                                          if len(gaps) > 4 else ""),
                   "have" if len(gaps) > 1 else "has"))
        raise RuntimeError("session finished but asset_requests.json did not "
                           "change — read the log")
    if not fetch:
        # Every NEW proposal must be lookable-at. Checked only on rounds
        # this run wrote: rounds from before 2026-08-25 carry bare search
        # terms and are not retroactively wrong, just not previewable.
        from . import schemas as _sc
        fresh = [r for r in (_read_json(rq) or {}).get("rounds", [])
                 if r.get("status") == "proposed"
                 and int(r.get("ts", 0)) >= int(started_ts)]
        bad = [e for r in fresh for e in _sc.validate_candidates(r)]
        if bad:
            raise RuntimeError(
                "proposals are not reviewable: %s%s"
                % ("; ".join(bad[:3]),
                   " (+%d more)" % (len(bad) - 3) if len(bad) > 3 else ""))
        # the gate: proposing must never leave media on disk
        adir = work / "assets"
        n = len(list(adir.iterdir())) if adir.is_dir() else 0
        log("[sourcing] proposals written — approve them on the desk "
            "(assets/ holds %d file(s), unchanged by this phase)" % n)
    else:
        log("[sourcing] approved rounds fetched — promote them to footage, "
            "then re-ingest so they catalogue as b-roll")
    set_pct(100)


KINDS = {
    # Pass 1 and pass 2. Survey is cheap and safe to re-run; ingest is the
    # expensive half and now skips what survey set aside.
    "survey": ("Read the shoot — previews you can watch", _run_survey),
    "ingest": ("Analyze footage — transcripts, takes, b-roll", _run_ingest),
    "assemble": ("Assemble — timeline + review previews", _run_assemble),
    "reproxy": ("Rebuild previews", _run_reproxy),
    "render": ("Render master", _run_render),
    "fixer": ("Auto-fix — rework the flagged clips", _run_fixer),
    "story": ("Pitch stories — three directions", _run_story),
    "editplan": ("Build the cut", _run_editplan),
    "recut": ("Re-cut — rebuild it, carry what still applies", _run_recut),
    "interview": ("Interview me — the director's questions", _run_interview),
    "script": ("Write the script", _run_script),
    "sourcing": ("Source supporting coverage", _run_sourcing),
    # "the place" is filmed-lane wording, and `_run_research` has always
    # accepted a topic as readily as a location — a documentary named one
    # and the Activity dock still called it a place (2026-08-26)
    "research": ("Research — sourced facts", _run_research),
    "graphics": ("Suggest graphics — cards for the clips", _run_graphics),
    "scout": ("Scout ideas", _run_scout),
    "snapcuts": ("Tighten cuts — edges onto clean audio", _run_snapcuts),
    "rendercards": ("Render all cards", _run_rendercards),
    "publish": ("Publish package — titles, description, tags",
                _run_publish),
    "retention": ("Retention pass — pacing flags before you review",
                  _run_retention),
    "hook": ("Hook doctor — score the cold open, pitch alternates",
             _run_hook),
    "qcgate": ("QC the master — measured ship checks", _run_qcgate),
    "perf": ("Analyze channel stats", _run_perf),
    "retro": ("Episode retro — lessons into Ideas", _run_retro),
    "diagnose": ("Diagnose a failed job", _run_diagnose),
    "coverage": ("B-roll pass — covers that serve the story",
                 _run_coverage),
    "room": ("Run the room — the showrunner convenes the stage",
             _run_room),
}

# Mechanical followers. A creative decision stays a button; everything
# mechanical that must follow it fires on its own (Caleb, 2026-08-23).
# Only DONE jobs chain — a failure stops the line and says so.
CHAIN = {
    "editplan": "assemble",
    # a re-cut is only watchable once the timeline and proxies follow it
    "recut": "assemble",
    # `script -> sourcing` USED to live here and has moved to the approval
    # (editroom._save_script_feedback, 2026-08-25). The intent is unchanged
    # — sourcing finds what can show the narration, then STOPS at the human
    # gate — but the trigger was wrong: the script job finishing means a
    # DRAFT was written, not that the words are settled. Chained there it
    # went out and priced pictures for lines Caleb was about to rewrite,
    # and once the script lane started refusing an unapproved draft it was
    # declined every single time (observed on the-pendulum-that-stopped).
    "graphics": "reproxy",
    "snapcuts": "assemble",
    # the one auto-dispatched session, by explicit P10 decision: the
    # retention pass runs on a FRESH cut only — its own guards refuse
    # (politely, as a logged chain skip) once any human verdict exists
    "assemble": "retention",
    "coverage": "assemble",
    # a room that changed the cut needs the timeline rebuilt; one that
    # didn't costs a fully-cached assemble — cheap either way
    "room": "assemble",
}


AUTOINGEST_DELAY = 20.0     # seconds of upload silence = the batch settled
# What a settled drop starts on its own.
#
# `ingest` until 2026-08-27, which meant a dropped card was TRANSCRIBED
# before anyone had looked at a frame of it — the desk could not show the
# footage until the expensive stage it should have informed was already
# paid for. Pass 1 is what a drop earns automatically; pass 2 is a human
# gate, because the point of triage is that it happens in between.
AUTOINGEST_KIND = "survey"
_UPLOAD_TS: "dict" = {}     # slug -> epoch of that slug's newest upload


def autoingest_decision(stamp: float, latest: float,
                        slug_jobs: "list", kind: str = AUTOINGEST_KIND) -> str:
    """Pure verdict for one debounce timer firing: 'start', 'rearm', or
    'skip'. Extracted so the race rules are testable without threads.

    - a NEWER upload superseded this timer -> skip (its own timer runs);
    - a run of `kind` already queued/running -> rearm (it may miss this
      batch's newest file, so check again later rather than double-queue);
    - a run that STARTED after the batch's last upload has already covered
      it (the teleprompter fires one explicitly) -> skip;
    - otherwise -> start.

    `kind` is a parameter because what a drop should trigger CHANGED: it
    used to fire the analysis, which transcribed every clip before anyone
    had looked at one. See AUTOINGEST_KIND.
    """
    if latest > stamp:
        return "skip"
    for j in slug_jobs:
        if j.get("kind") != kind:
            continue
        if j.get("state") in ("queued", "running"):
            return "rearm"
        if (j.get("state") == "done"
                and (j.get("started_ts") or 0) >= stamp):
            return "skip"
    return "start"


def _autoingest_fire(slug: str, stamp: float) -> None:
    verdict = autoingest_decision(stamp, _UPLOAD_TS.get(slug, stamp),
                                  jobs(slug), AUTOINGEST_KIND)
    if verdict == "start":
        try:
            start(AUTOINGEST_KIND, slug)
        except JobError:
            pass
    elif verdict == "rearm":
        t = threading.Timer(30.0, _autoingest_fire,
                            args=(slug, _UPLOAD_TS.get(slug, stamp)))
        t.daemon = True
        t.start()


def note_upload(slug: str) -> None:
    """Called by the upload endpoint after each stored file. When the
    batch settles (no new file for AUTOINGEST_DELAY), analysis starts on
    its own -- drop footage, walk away (P1, 2026-08-23). NINTH_AUTOINGEST=0
    disables."""
    if os.environ.get("NINTH_AUTOINGEST") == "0":
        return
    ts = time.time()
    _UPLOAD_TS[slug] = ts
    t = threading.Timer(AUTOINGEST_DELAY, _autoingest_fire, args=(slug, ts))
    t.daemon = True
    t.start()


def _notify(title: str, body: str) -> None:
    """A real macOS notification from the engine — it works with the
    browser closed, which a tab-bound notification cannot. Gated to
    darwin and NINTH_NOTIFY != "0" (the SaaS path keeps this off).
    Never raises: a broken osascript must not fail a finished job."""
    import subprocess
    import sys
    if sys.platform != "darwin" or os.environ.get("NINTH_NOTIFY") == "0":
        return
    try:
        script = 'display notification "%s" with title "%s"' % (
            body.replace('\\', '').replace('"', "'")[:180],
            title.replace('\\', '').replace('"', "'")[:60])
        subprocess.run(["osascript", "-e", script], capture_output=True,
                       timeout=10)
    except Exception:
        pass


def _set_chain(job: "dict", follower: str, state: str,
               error: "str | None" = None) -> None:
    """Per-follower chain state on the finished job's record (P0 of the
    team plan): pending -> ok | failed, visible in the tray and
    re-runnable — the crooise assemble that silently never ran."""
    jid = job.get("id")
    if jid not in _jobs:
        return  # unit tests drive _after_done with bare dicts
    with _LOCK:
        chain = dict(_jobs[jid].get("chain") or {})
        chain[follower] = state
        _jobs[jid]["chain"] = chain
        if error:
            _jobs[jid]["chain_error"] = error[:300]
        _persist()


def _after_done(job: "dict", log) -> None:
    """Enqueue the finished job's mechanical follower, if it has one,
    tracking per-follower state. An already-queued/running follower
    satisfies the chain's INTENT (ok); any other refusal or raise is
    chain_failed — visible, notified, and re-runnable from the tray."""
    follower = CHAIN.get(job["kind"])
    if not follower:
        return
    _set_chain(job, follower, "pending")
    try:
        start(follower, job["slug"])
        _set_chain(job, follower, "ok")
        log("[chain] %s done -> %s queued" % (job["kind"], follower))
    except JobError as e:
        if "already" in str(e):
            _set_chain(job, follower, "ok")
            log("[chain] %s follower already in flight: %s"
                % (job["kind"], e))
        else:
            _set_chain(job, follower, "failed", str(e))
            log("[chain] %s -> %s FAILED: %s" % (job["kind"], follower, e))
            _notify("Chain failed", "%s -> %s: %s"
                    % (job["kind"], follower, str(e)[:100]))
    except Exception as e:
        _set_chain(job, follower, "failed", "%s: %s" % (type(e).__name__, e))
        log("[chain] %s -> %s BROKE: %s" % (job["kind"], follower, e))
        _notify("Chain failed", "%s -> %s: %s"
                % (job["kind"], follower, str(e)[:100]))


def rechain(jid: str) -> "dict":
    """Re-run a job's failed chain followers. Idempotent by construction:
    ok followers are skipped, and start()'s duplicate guard turns an
    in-flight follower into ok rather than a double-queue — safe to click
    on a bad day."""
    job = _jobs.get(jid)
    if job is None:
        raise JobError("no job '%s'" % jid)
    chain = dict(job.get("chain") or {})
    if not chain:
        raise JobError("that job has no chain")
    for follower, state in chain.items():
        if state == "ok":
            continue
        _set_chain(job, follower, "pending")
        try:
            start(follower, job["slug"])
            _set_chain(job, follower, "ok")
        except JobError as e:
            if "already" in str(e):
                _set_chain(job, follower, "ok")
            else:
                _set_chain(job, follower, "failed", str(e))
    return _jobs[jid]


CHAIN_REAP_S = 900


def _reap_chains() -> None:
    """A process death between chain_pending and its resolution orphans
    the state forever — the same hole the claim reaper closes. Old
    pending -> failed with a reaped note, still re-runnable."""
    now = time.time()
    with _LOCK:
        dirty = False
        for job in _jobs.values():
            chain = job.get("chain") or {}
            for follower, state in list(chain.items()):
                if state == "pending" \
                        and now - (job.get("ended_ts") or now) > CHAIN_REAP_S:
                    chain[follower] = "failed"
                    job["chain"] = chain
                    job["chain_error"] = ("reaped: the engine died before "
                                          "the chain resolved")
                    dirty = True
        if dirty:
            _persist()


def _job_name(job: "dict") -> str:
    """The human label, from the ROW rather than the registry. `KINDS` can
    lose a kind while a job of it is still running, and a KeyError raised
    on the way to a notification killed the lane's worker."""
    label = job.get("label") or KINDS.get(job.get("kind"), (job.get("kind", "job"),))[0]
    return str(label).split(" — ")[0]


def _worker(lane: str = "local"):
    while True:
        jid = _QUEUES[lane].get()
        try:
            _run_one(lane, jid)
        except BaseException as e:      # noqa: BLE001 — see below
            # NOTHING may end this loop. A lane has exactly one worker, and
            # `start()` only spawns one if the slot is empty, so a thread
            # that dies here takes the lane with it: every later job of
            # that lane sits at "queued" forever and the desk shows a hang
            # with no error anywhere. Whatever escaped `_run_one` has
            # already been handled or is unhandleable; say so and take the
            # next job. (2026-08-25.)
            try:
                sys.stderr.write("[jobs] %s worker survived %s: %s\n"
                                 % (lane, type(e).__name__, e))
            except Exception:
                pass


def _run_one(lane: str, jid: str) -> None:
        job = _jobs.get(jid)
        if job is None:
            # An id in the queue with no row behind it used to raise
            # KeyError HERE, outside the try — which killed the lane's
            # only worker thread for the life of the process. Every later
            # job in that lane then sat at "queued" forever, looking
            # exactly like a hang. (Found 2026-08-25 as a 1-in-6 flake in
            # test_job_lanes; the same hole would swallow the local lane
            # in the engine after any prune of the job store.)
            return
        # float on purpose: an ingest starting in the same second as the
        # upload it covers must still compare AFTER it (review F4)
        _update(jid, state="running", started_ts=time.time())
        log = _job_log(jid)
        _CURRENT.jid = jid
        try:
            _, fn = KINDS[job["kind"]]
            if job.get("arg"):
                fn(job["slug"], log, lambda p: _update(jid, pct=int(p)),
                   arg=job["arg"])
            else:
                fn(job["slug"], log, lambda p: _update(jid, pct=int(p)))
            _update(jid, state="done", pct=100, ended_ts=int(time.time()))
            _notify("%s — done" % _job_name(job), job["slug"])
            try:
                _after_done(job, log)
            except Exception as chain_err:  # review F1: a persist error in
                # the follower's enqueue must never flip THIS job to failed
                log("[chain] follower enqueue broke: %s" % chain_err)
        except JobError as e:
            # A GUARD refusing is not a failure. The retention pass
            # declining because humans are already reviewing, reproxy
            # declining because there is no cut — these are the system
            # working, and painting them red teaches Caleb to ignore red
            # (2026-08-24: every re-assemble of a reviewed episode left a
            # scarlet row behind). No traceback: there is no stack worth
            # reading when nothing broke.
            log("[job] declined: %s" % e)
            _update(jid, state="declined", error=str(e)[:300],
                    ended_ts=int(time.time()))
        except Exception as e:  # the tray must show the failure, never hang
            import traceback as _tb
            log("[job] FAILED: %s: %s" % (type(e).__name__, e))
            # A STABLE CODE when the raise carried one, so the desk can
            # explain the failure and offer a door without matching on
            # prose. Absent for the ~180 raises that carry none — those
            # keep showing their message verbatim, which is the bargain.
            code = getattr(e, "code", None)
            _update(jid, state="failed", error=str(e)[:300],
                    traceback=_tb.format_exc()[-2000:],
                    ended_ts=int(time.time()),
                    **({"error_code": code} if isinstance(code, str) and code else {}))
            _notify("%s — failed" % _job_name(job),
                    "%s: %s" % (job["slug"], str(e)[:140]))


def start(kind: str, slug: str, arg: "str | None" = None) -> "dict":
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
    if kind == "assemble":
        # a running conform reads timeline_map + the card ledger; an
        # assemble rewriting them mid-push tears it (P3 gate finding 8).
        # Surgery's retry timer re-queues once the conform lands.
        from . import conform as conform_mod
        if conform_mod.status(slug).get("state") == "running":
            raise JobError("a conform is running — assemble after it")
    if kind == "story":
        # A documentary has no pitch: there is no day's footage to choose
        # a direction from, so the interview IS the story stage. Saying
        # "ingest first" to a format that will never ingest sends Caleb to
        # a desk that cannot help him (2026-08-25).
        if _script_origin(slug) == "script":
            raise JobError("a documentary has no pitch — the story is "
                           "settled by the interview on the Script desk")
        if not (work_path(slug) / "analysis" / "catalog.json").exists():
            raise JobError("ingest first — the designer needs transcripts")
        if (work_path(slug) / "edit_plan.json").exists():
            raise JobError("story is locked — an edit plan already exists")
    if kind == "recut":
        # Both of these are answerable before the click, which is the
        # whole point of the job contract: a session that dispatches and
        # then discovers it had nothing to do costs billed minutes to
        # learn what a file check knows for free.
        if not (work_path(slug) / "edit_plan.json").exists():
            raise JobError("there is no cut to re-cut — build one first")
        if not str(arg or "").strip():
            raise JobError("say in one line what this re-cut should "
                           "improve — a re-cut with no stated intent "
                           "cannot be judged against the one it replaces")
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
        global _seq
        _seq += 1
        jid = "J%d%03d" % (int(time.time()), _seq % 1000)
        while jid in _jobs:          # belt and braces across a restart
            _seq += 1
            jid = "J%d%03d" % (int(time.time()), _seq % 1000)
        job = {"id": jid, "kind": kind, "slug": slug,
               "label": KINDS[kind][0], "state": "queued", "pct": 0,
               "note": "", "queued_ts": int(time.time())}
        if arg:
            job["arg"] = str(arg)
        _jobs[jid] = job
        _order.append(jid)
        _persist()
        lane = lane_of(kind)
        job["lane"] = lane
        w = _WORKERS.get(lane)
        # `is_alive()`, not just `is None`: a dead thread in the slot is
        # how a lane goes quiet forever. The loop is armoured now, but a
        # lane with no live worker must still be able to come back.
        if w is None or not w.is_alive():
            _WORKERS[lane] = threading.Thread(target=_worker, args=(lane,),
                                              daemon=True)
            _WORKERS[lane].start()
    _QUEUES[lane].put(jid)
    return job


def jobs(slug: "str | None" = None) -> "list":
    """The tray's whole truth. Rows carry `queue_pos` (1 = next to run)
    and `next_kind` (what this job will chain into) so the desk can say
    WHY something is waiting and WHAT it will trigger, instead of showing
    a flat list where a queued job looks stuck (Caleb, 2026-08-24: "I
    need transparency on tasks and how they are queued").

    One worker runs one job: position is simply arrival order among the
    queued, which is exactly what the desk needs to render "3rd in line,
    behind Build the cut".
    """
    _reap_chains()
    with _LOCK:
        rows = [dict(_jobs[i]) for i in reversed(_order)]
    if slug:
        rows = [r for r in rows if r["slug"] == slug]
    rows = rows[:KEEP]
    # positions are PER LANE: with a session and a local worker running
    # side by side, a single global ranking would tell a local job it is
    # "3rd in line" when two of the three ahead of it are on the other
    # lane and cannot block it
    for lane in ("session", "local"):
        waiting = sorted((r for r in rows if r["state"] == "queued"
                          and (r.get("lane") or lane_of(r["kind"])) == lane),
                         key=lambda r: r.get("queued_ts") or 0)
        for pos, r in enumerate(waiting, start=1):
            r["queue_pos"] = pos
            r["lane"] = lane
    for r in rows:
        r.setdefault("lane", lane_of(r["kind"]))
        nxt = CHAIN.get(r["kind"])
        if nxt:
            r["next_kind"] = nxt
            r["next_label"] = KINDS[nxt][0] if nxt in KINDS else nxt
    return rows


def log_tail(jid: str, lines: int = 120) -> str:
    path = LOG_DIR / ("%s.log" % jid)
    if not path.exists():
        return ""
    return "\n".join(path.read_text().splitlines()[-lines:])


_restore()
