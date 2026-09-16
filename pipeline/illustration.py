"""Illustrations: pictures no camera could film, and where they came from.

The vocabulary is CONTEXT.md's; the decisions are
docs/decisions-illustrations.md. This module owns the one fact every rule
about an illustration reads, its PROVENANCE, and the pure helpers around
it. Provenance is derived once, at catalog time, from the Library manifest
(`work/<slug>/assets/assets.json`): a row whose `honesty` names one of the
two values is an illustration, and the footage file it became is matched
by `promoted_as` first (the name `_use_asset` gave it), then by the row's
own file name, then by the `<stem>_still.mp4` a still is baked into.
Absent means camera, everywhere.

What breaks if this is wrong: a plate is graded through the camera LUT
(build_api reads provenance to leave it alone), a re-analyze forgets which
clips are illustrations (catalog_broll derives it fresh each run, so it
cannot), or a rule keyed on provenance goes blind.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from .ingest import work_path
from .schemas import HONESTY  # noqa: F401  (re-exported: the two values)


def provenance_of(assets_dir: Path, name: str) -> Optional[str]:
    """The honesty value of the manifest row `name` came from, or None."""
    man_p = Path(assets_dir) / "assets.json"
    try:
        rows = json.loads(man_p.read_text()).get("assets", [])
    except (OSError, ValueError):
        return None
    for a in rows:
        honesty = a.get("honesty")
        if honesty not in HONESTY:
            continue
        f = str(a.get("file") or "")
        if name in (a.get("promoted_as"), f, Path(f).stem + "_still.mp4"):
            return honesty
    return None


def exempt_files(slug: str) -> "set[str]":
    """Footage file names the colour pipeline must leave alone: every
    catalogued clip carrying a provenance. Pure over analysis/broll.json."""
    p = work_path(slug) / "analysis" / "broll.json"
    try:
        clips = json.loads(p.read_text()).get("clips", [])
    except (OSError, ValueError):
        return set()
    return {c["file"] for c in clips
            if isinstance(c, dict) and c.get("provenance") and c.get("file")}


# --- the gate, the ledger, the cap ---------------------------------------
#
# Decisions 3, 7, 17 and 18 (docs/decisions-illustrations.md). The agent
# PROPOSES a priced round; Caleb approves it on the Library desk and marks
# Seedance or pro where he wants them; the engine GENERATES inside a cap and
# writes one manifest row per spend in the same operation as the file it
# bought (the brand/sfx manifest shape: a file without its row does not
# exist). Everything below is pure or file-local; nothing here dispatches a
# session or calls the network except `cli`, which every Higgsfield call
# goes through so it carries a timeout.

import subprocess
import threading

from . import paths
from .capture import append_to_manifest
from .ingest import IngestError
from .schemas import COVER_WHYS, delivery_shape, why_kind

EPISODE_CREDIT_CAP = 300.0

# The defaults the brief works to (decision 18, measured 2026-09-15).
DEFAULT_PLATE = {"model": "nano_banana_pro", "credits": 2.0}
DEFAULT_VIDEO = {"model": "kling3_0", "credits": 7.5, "duration": 5,
                 "mode": "std", "sound": "off"}
SEEDANCE_MODEL = "seedance_2_5"
TURBO_MODEL = "kling3_0_turbo"             # a model id, not a tier
SOUL_MODELS = ("text2image_soul_v2", "soul_cinema_studio")
# The parameter that carries a model's quality tier at create time, and
# what "pro" means on it. `std` is always the model's own default.
# The Soul models top out at 2k, their own default, so pro on a Soul plate
# changes nothing (live `model get`, 2026-09-16).
TIER_FIELD = {"kling3_0": ("mode", "pro"), "kling3_0_turbo": ("mode", "pro"),
              "seedance_2_5": ("resolution", "1080p"),
              "nano_banana_pro": ("resolution", "4k"),
              "text2image_soul_v2": ("quality", "2k"),
              "soul_cinema_studio": ("quality", "2k")}
TIER_STD = {"kling3_0": ("mode", "std"), "kling3_0_turbo": ("mode", "std"),
            "seedance_2_5": ("resolution", "720p"),
            "nano_banana_pro": ("resolution", "2k"),
            "text2image_soul_v2": ("quality", "2k"),
            "soul_cinema_studio": ("quality", "2k")}
TIERS = ("std", "pro")
TARGETS = ("cover", "run", "thumbnail", "short_cover")
ASPECT_OF = {"landscape": "16:9", "portrait": "9:16"}
PROMPT_MAX_CHARS = 1200

_ILLUSTRATION_LOCK = threading.Lock()
CHANNEL_LEDGER = paths.work_dir() / "_channel" / "higgsfield_ledger.json"
_HEX_RE = None


def _hex_re():
    global _HEX_RE
    if _HEX_RE is None:
        import re
        _HEX_RE = re.compile(r"#[0-9a-fA-F]{6}\b")
    return _HEX_RE


def ledger(slug: str) -> "list[dict]":
    """Every manifest row that cost credits: the episode's ledger IS its
    manifest, one row per spend beside the file it bought."""
    p = work_path(slug) / "assets" / "assets.json"
    try:
        rows = json.loads(p.read_text()).get("assets", [])
    except (OSError, ValueError):
        return []
    return [a for a in rows if isinstance(a, dict)
            and a.get("honesty") in HONESTY and "cost_credits" in a]


def spent(slug: str) -> float:
    return round(sum(float(a.get("cost_credits") or 0.0) for a in ledger(slug)), 3)


def append_row(assets_dir: Path, row: dict) -> dict:
    """The one door a spend's row goes through. Refuses a row that could
    not explain a credit: no cost, no model, no job id, no honesty, no
    status. Under the lock because the engine is a ThreadingHTTPServer
    and two spends may finish together."""
    missing = [k for k in ("cost_credits", "model", "job_id", "honesty", "status")
               if k not in row]
    if missing:
        raise IngestError("ledger row %s is missing %s"
                          % (row.get("id"), ", ".join(missing)))
    if row["honesty"] not in HONESTY:
        raise IngestError("ledger row %s: honesty %r is not one of %s"
                          % (row.get("id"), row["honesty"], "/".join(HONESTY)))
    with _ILLUSTRATION_LOCK:
        return append_to_manifest(Path(assets_dir), row)


def channel_ledger() -> "list[dict]":
    """Spends that belong to the channel, not an episode: Soul training,
    hand runs on the website. One row each, so `illustrate-check` can show
    them beside the episode figure and the balance is explained."""
    try:
        return json.loads(CHANNEL_LEDGER.read_text()).get("rows", [])
    except (OSError, ValueError):
        return []


def channel_spent() -> float:
    return round(sum(float(r.get("credits") or 0.0) for r in channel_ledger()), 3)


def append_channel_row(row: dict) -> None:
    if "credits" not in row or "what" not in row:
        raise IngestError("a channel ledger row needs `what` and `credits`")
    with _ILLUSTRATION_LOCK:
        rows = channel_ledger()
        rows.append(row)
        CHANNEL_LEDGER.parent.mkdir(parents=True, exist_ok=True)
        CHANNEL_LEDGER.write_text(json.dumps({"rows": rows}, indent=1))


def cli(args: "list[str]", timeout: float = 120.0) -> "tuple[int, str, str]":
    """Run the Higgsfield CLI with a timeout. Every call goes through here
    so no runner can hang the lane on a network wait."""
    cmd = [paths.higgsfield_bin()] + list(args)
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise IngestError("higgsfield %s timed out after %ss"
                          % (" ".join(args[:2]), timeout))
    except OSError as e:
        raise IngestError("higgsfield could not run: %s" % e)
    return proc.returncode, proc.stdout, proc.stderr


def _section_index(script: "dict | None") -> "dict[str, dict]":
    out = {}
    for ch in (script or {}).get("chapters", []) or []:
        for sec in (ch or {}).get("sections", []) or []:
            if isinstance(sec, dict) and sec.get("id"):
                out[str(sec["id"])] = sec
    return out


def validate_round(round_: dict, delivery: "str | None",
                   script: "dict | None" = None,
                   plan: "dict | None" = None) -> "list[str]":
    """The shape of an illustration round, as errors. Empty means the
    runner may append it at `proposed` and, once approved, spend it.

    Pure. `delivery` fixes the aspect a cover or run must carry; `script`
    (script lane) or `plan` (footage lane) is the artifact the round's
    section or beat must exist in, and the lane decides two things: a
    `run` is a take-less picture beat and only a footage cut can hold one,
    and a Soul step needs a `vo` section or a take-less beat because the
    host cannot appear inside a picture playing under his own face.
    """
    errors: "list[str]" = []
    rid = str(round_.get("id") or round_.get("section_id") or round_.get("beat_id") or "?")
    where = "round %s" % rid
    if round_.get("kind") != "illustration":
        errors.append("%s: kind must be illustration" % where)
    sid, bid = round_.get("section_id"), round_.get("beat_id")
    if bool(sid) == bool(bid):
        errors.append("%s: exactly one of section_id or beat_id" % where)
    sections = _section_index(script)
    beats = {str(b.get("id")): b for b in (plan or {}).get("beats", []) or []
             if isinstance(b, dict)}
    section = sections.get(str(sid)) if sid else None
    beat = beats.get(str(bid)) if bid else None
    if sid and script is not None and section is None:
        errors.append("%s: no section %s in the script" % (where, sid))
    if bid and plan is not None and beat is None:
        errors.append("%s: no beat %s in the plan" % (where, bid))
    honesty = round_.get("honesty")
    if honesty not in HONESTY:
        errors.append("%s: honesty must be one of %s" % (where, "/".join(HONESTY)))
    target = round_.get("target")
    if target not in TARGETS:
        errors.append("%s: target must be one of %s" % (where, "/".join(TARGETS)))
    if target == "run" and not bid:
        errors.append("%s: a run is a picture beat, which only a footage cut "
                      "can hold — use a cover on the script lane" % where)
    if target in ("cover", "run"):
        want = ASPECT_OF[delivery_shape(delivery)["orientation"]]
        if round_.get("aspect") != want:
            errors.append("%s: aspect must be %s for this delivery, not %r"
                          % (where, want, round_.get("aspect")))
        kind = why_kind(round_.get("why"))
        if kind is None:
            errors.append("%s: why must lead with one of %s" % (
                where, "/".join(w for w in COVER_WHYS if w != "establish")))
        elif kind == "establish":
            errors.append("%s: an illustration cannot establish — the place is "
                          "camera footage" % where)
    marks = round_.get("marks") if isinstance(round_.get("marks"), dict) else {}
    steps = round_.get("steps")
    if not isinstance(steps, list) or not steps:
        errors.append("%s: a round needs at least one priced step" % where)
        steps = []
    seen_stages: "list[str]" = []
    total = 0.0
    for i, st in enumerate(steps):
        sw = "%s.steps[%d]" % (where, i)
        if not isinstance(st, dict):
            errors.append(sw + ": not an object")
            continue
        stage = str(st.get("stage") or "")
        if not stage:
            errors.append(sw + ": no stage name")
        model = str(st.get("model") or "")
        if not model:
            errors.append(sw + ": no model id")
        prompt = str(st.get("prompt") or "")
        if not prompt.strip():
            errors.append(sw + ": no prompt")
        elif len(prompt) > PROMPT_MAX_CHARS:
            errors.append("%s: prompt runs %d characters — keep it under %d"
                          % (sw, len(prompt), PROMPT_MAX_CHARS))
        if _hex_re().search(prompt):
            errors.append("%s: a hex colour in the prompt — the style file "
                          "carries the tokens, the prompt never types one" % sw)
        if "insert" in prompt.lower().split() or " inserts" in prompt.lower():
            errors.append("%s: the word insert is banned (CONTEXT.md)" % sw)
        credits = st.get("credits")
        if not isinstance(credits, (int, float)) or isinstance(credits, bool) or credits < 0:
            errors.append(sw + ": credits must be a number")
        else:
            total += float(credits)
        tier = st.get("tier", "std")
        if tier not in TIERS:
            errors.append("%s: tier must be std or pro" % sw)
        elif tier == "pro":
            if not str(st.get("reason") or "").strip():
                errors.append("%s: a pro step needs a reason" % sw)
            if stage not in (marks.get("pro") or []):
                errors.append("%s: pro only where Caleb marked it on the round" % sw)
        if model == SEEDANCE_MODEL and not marks.get("seedance"):
            errors.append("%s: Seedance only on a round Caleb marked for it" % sw)
        if st.get("soul"):
            if model not in SOUL_MODELS:
                errors.append("%s: a Soul step must use a Soul model (%s); %s takes "
                              "no Soul reference" % (sw, "/".join(SOUL_MODELS), model or "?"))
            if stage != "plate":
                errors.append("%s: a Soul step is a plate; the motion step animates "
                              "it from start_image" % sw)
            if honesty != "reconstruction" and target not in ("thumbnail", "short_cover"):
                errors.append("%s: the host appears only in a reconstruction or a "
                              "thumbnail, never in an illustration" % sw)
            if section is not None and section.get("kind") != "vo":
                errors.append("%s: a Soul step needs a vo section — the host cannot "
                              "sit inside a picture under his own face" % sw)
            if beat is not None and beat.get("take_id"):
                errors.append("%s: a Soul step needs a take-less beat" % sw)
        start = st.get("start_image")
        if start is not None and start not in seen_stages:
            errors.append("%s: start_image %r names no earlier stage" % (sw, start))
        seen_stages.append(stage)
    est = round_.get("estimate_credits")
    if not isinstance(est, (int, float)) or abs(float(est) - total) > 0.01:
        errors.append("%s: estimate_credits must equal the steps' sum (%.2f)"
                      % (where, total))
    if honesty == "reconstruction":
        if not isinstance(round_.get("sources"), list) or not round_.get("sources"):
            errors.append("%s: a reconstruction needs sources" % where)
        if not str(round_.get("disclosure") or "").strip():
            errors.append("%s: a reconstruction needs its disclosure line" % where)
    return errors


def cap_check(slug: str, rounds: "list[dict]") -> None:
    """Spent so far plus every estimate offered must fit the episode cap,
    or the runner refuses before a session or a spend."""
    est = sum(float(r.get("estimate_credits") or 0.0) for r in rounds)
    have = spent(slug)
    if have + est > EPISODE_CREDIT_CAP + 1e-9:
        raise IngestError("%.1f spent plus %.1f proposed is past the %d credit "
                          "episode cap" % (have, est, int(EPISODE_CREDIT_CAP)))


# --- the prompt clause and the round shape ---------------------------------

STAGING = Path("staging") / "illustration_rounds.json"
SHIM_DIR = Path(__file__).resolve().parent / "bridge" / "higgsfield_readonly"
STYLE_FILE = paths.PROJECT_ROOT / "brand" / "illustration" / "plate.md"

ROUND_SHAPE = '''{"rounds": [{
  "kind": "illustration",
  "section_id": "CH2.S3"   (script lane)   |  "beat_id": "shot-T41"   (footage lane),
  "honesty": "illustration" | "reconstruction",
  "target": "cover" | "run" | "thumbnail" | "short_cover",
  "aspect": "16:9" | "9:16",
  "why": "illustrate: <the thing the line names>",
  "note": "<one line: what the library lacked; where beside would have served>",
  "steps": [
    {"stage": "plate", "model": "nano_banana_pro", "prompt": "<style block as handed> Subject: ...",
     "credits": 2.0, "tier": "std"},
    {"stage": "motion", "model": "kling3_0", "start_image": "plate",
     "prompt": "<motion only>", "credits": 7.5, "tier": "std"}
  ],
  "estimate_credits": 9.5,
  "sources": ["<url>", ...]        (reconstruction only),
  "disclosure": "<one line>"       (reconstruction only),
  "marks": {}                      (Caleb's, at approval; leave empty)
}]}'''


def style_block() -> str:
    """brand/illustration/plate.md with every placeholder resolved through
    the design tokens. Pure over the two files; the hexes are read, never
    typed (tests/test_illustration_brief.py, test_illustration_job.py)."""
    from . import design_tokens
    text = STYLE_FILE.read_text()
    tokens = design_tokens.load()
    import re
    def sub(m):
        name = m.group(1).replace("_", "-")
        return design_tokens.resolve(tokens, name, "{{%s}}" % m.group(1))
    return re.sub(r"\{\{([a-z0-9_]+)\}\}", sub, text)


def _j(obj) -> str:
    return json.dumps(obj, ensure_ascii=False)


def prompt_clause(slug: str, balance: "float | None" = None) -> str:
    """Everything the illustration-director consults, in the order the
    story-director reads its own inputs: the brief, research, voice, the
    film studies, the lane block, the visual language, the money, the
    honesty rules, the mechanics. Pure over the slug's files; `balance` is
    read by the runner and passed in so this stays testable offline.

    A beat with only a `note` is NOT a request: only a `visual` block whose
    `from` is `illustration` asks for a picture (decision 10, the
    storyteller asks; the director never guesses over eighty beats).
    """
    from . import cutbar, schemas
    w = work_path(slug)
    def read(name, default=None):
        try:
            return json.loads((w / name).read_text())
        except (OSError, ValueError):
            return default
    brief = read("story_brief.json", {}) or {}
    shape = schemas.delivery_shape(brief.get("delivery"))
    aspect = ASPECT_OF[shape["orientation"]]
    parts = []

    # 1. the brief
    parts.append("THE BRIEF (work/%s/story_brief.json): origin %s; delivery %s, so "
                 "the aspect of a cover or run is %s; target %s minutes; chapters %s; "
                 "vo_share %s; %s."
                 % (slug, brief.get("origin", "footage"), brief.get("delivery", "long"),
                    aspect, brief.get("target_minutes", "?"), brief.get("chapters", "?"),
                    brief.get("vo_share", "?"),
                    "location " + _j(brief.get("location")) if brief.get("location")
                    else "subject " + _j(brief.get("subject", ""))))

    # the lane and its requests
    script = read("script.json")
    plan = read("edit_plan.json", {}) or {}
    requests = read("asset_requests.json", {}) or {}
    live = {str(r.get("section_id") or r.get("beat_id"))
            for r in requests.get("rounds", []) or []
            if isinstance(r, dict) and r.get("kind") == "illustration"
            and r.get("status") in ("proposed", "approved")}
    target_ids = []

    # 2. research
    research = read("research.json", {}) or {}
    facts = [f for f in research.get("facts", []) or [] if isinstance(f, dict)]
    if facts:
        parts.append("RESEARCH (work/%s/research.json), each fact with its source and "
                     "confidence; a `claimed` fact is illustrated as claimed, never as "
                     "settled: %s" % (slug, _j([{"fact": f.get("fact"), "source_url": f.get("source_url"),
                                                "confidence": f.get("confidence")} for f in facts[:40]])))

    # 3. voice
    parts.append("VOICE: brand/voice-and-tone.md and brand/brand-brief.md. Two lines "
                 "that govern you: \"The visit is the episode\" and \"could we source "
                 "it if someone asked?\"")

    # 4. film studies
    parts.append("FILM STUDIES (docs/film-studies/INDEX.md): Harris R13 (we can't fly a "
                 "map; never decoration), Rober D10 (beside: reference and reality share "
                 "the frame) and D16 (prefer a real object over a render), Beau Miles "
                 "(the real thing over the drawn one).")

    # 5. the lane block
    if script is not None:
        sections = []
        loops = {str(lp.get("id")): lp for lp in script.get("loops", []) or [] if isinstance(lp, dict)}
        for ch in script.get("chapters", []) or []:
            for sec in (ch or {}).get("sections", []) or []:
                vis = (sec or {}).get("visual") or {}
                if not (isinstance(vis, dict) and vis.get("from") == "illustration"):
                    continue
                sid = str(sec.get("id"))
                if sid in live:
                    continue
                target_ids.append(sid)
                promise = None
                for lp in loops.values():
                    if lp.get("opens") == sid or sid in (lp.get("opens") or []):
                        promise = lp.get("promise")
                sections.append({"id": sid, "kind": sec.get("kind"), "text": sec.get("text"),
                                 "source": sec.get("source"), "est_s": sec.get("est_s"),
                                 "want": vis.get("want"), "why": vis.get("why"),
                                 "chapter": ch.get("title"), "loop_promise": promise})
        parts.append("THE SCRIPT LANE (work/%s/script.json, locked). These sections ask "
                     "for an illustration and have no live round; each is one round "
                     "keyed by section_id: %s" % (slug, _j(sections)))
    else:
        hook = set(cutbar.hook_beat_ids(plan))
        takes = {t.get("id"): t for t in (read("analysis/takes.json", {}) or {}).get("takes", []) or []
                 if isinstance(t, dict)}
        beats = []
        chapters = {str(c.get("id")): c for c in plan.get("chapters", []) or [] if isinstance(c, dict)}
        for b in plan.get("beats", []) or []:
            vis = (b or {}).get("visual") or {}
            if not (isinstance(vis, dict) and vis.get("from") == "illustration"):
                continue
            bid = str(b.get("id"))
            if bid in live or bid in hook or b.get("peak") is True:
                continue
            target_ids.append(bid)
            take = takes.get(b.get("take_id")) or {}
            beats.append({"id": bid, "purpose": b.get("purpose"), "chapter_id": b.get("chapter_id"),
                          "beat_span": round(schemas.beat_span(b), 2),
                          "transcript": (take.get("transcript") or take.get("text") or "")[:400],
                          "note": b.get("note"), "want": vis.get("want"), "why": vis.get("why"),
                          "take_id": b.get("take_id"),
                          "cover_whys": [c.get("why") for c in (b.get("broll") or []) if isinstance(c, dict)],
                          "chapter_promise": (chapters.get(str(b.get("chapter_id"))) or {}).get("promise")})
        stories = read("stories.json", {}) or {}
        feedback = read("story_feedback.json", {}) or {}
        chosen = None
        rounds = feedback.get("rounds", []) or []
        if rounds and rounds[-1].get("decision") == "approve":
            cid = rounds[-1].get("choice")
            chosen = next((o for o in stories.get("options", []) or [] if o.get("id") == cid), None)
        review = read("review.json", {}) or {}
        notes = {k: v.get("note") for k, v in review.items()
                 if isinstance(v, dict) and v.get("note")}
        parts.append("THE FOOTAGE LANE (work/%s/edit_plan.json). theme %s. These beats "
                     "carry a visual block asking for an illustration, are not in the "
                     "hook and are not peaks, and have no live round; each is one round "
                     "keyed by beat_id (a beat with only a note is not a request): %s. "
                     "The approved direction: %s. Review notes: %s"
                     % (slug, _j(plan.get("theme")), _j(beats),
                        _j({k: chosen.get(k) for k in ("logline", "hook", "tone")}) if chosen else "none",
                        _j(notes) if notes else "none"))

    # 6. the visual language
    parts.append("THE VISUAL LANGUAGE, quoted as handed, hexes already resolved from the "
                 "design tokens (never type one):\n%s\nThe failure case: the plate must "
                 "read at the 480p proxy over the chapter's brightest footage."
                 % style_block())

    # 7. money
    parts.append("MONEY: balance %s credits; this episode has spent %.1f of its %d credit "
                 "cap. Defaults: plate %s at %.1f credits; motion %s at %.1f credits for "
                 "%d seconds, sound off, tier std. Pro (%s) only where Caleb marks it on "
                 "the round at approval, with a reason; Seedance (%s) only on a round he "
                 "marks. This overrides the Higgsfield skill's \"don't pre-estimate cost\": "
                 "price every step with `higgsfield generate cost` and write the number."
                 % ("unknown" if balance is None else ("%g" % balance), spent(slug),
                    int(EPISODE_CREDIT_CAP), DEFAULT_PLATE["model"], DEFAULT_PLATE["credits"],
                    DEFAULT_VIDEO["model"], DEFAULT_VIDEO["credits"], DEFAULT_VIDEO["duration"],
                    ", ".join("%s %s=%s" % (m, f, v) for m, (f, v) in sorted(TIER_FIELD.items())),
                    SEEDANCE_MODEL))

    # 8. honesty and the marker
    parts.append("HONESTY: %s. A reconstruction carries sources and a disclosure and "
                 "gets the kit eyebrow RECONSTRUCTION for its whole length. Never the "
                 "real place as footage; never a real person; never the family; a Soul "
                 "step only as a plate on %s, inside a reconstruction or a thumbnail, on "
                 "a vo section or a take-less beat. Soul id %s."
                 % ("/".join(HONESTY), "/".join(SOUL_MODELS),
                    "is set" if paths.soul_id() else "is NOT set: propose no soul step"))

    # 9. mechanics
    parts.append("MECHANICS: write ONLY work/%s/%s in this shape:\n%s\nThe `higgsfield` "
                 "on your PATH is read-only (account, model, generate cost/get/list); "
                 "pass job ids to media flags, never a local path. Then run "
                 "`/usr/bin/python3 -m pipeline.cli illustrate-check %s --offline` and "
                 "fix what it names. Targets this run: %s."
                 % (slug, STAGING.as_posix(), ROUND_SHAPE, slug, _j(target_ids)))
    return "\n\n".join(parts) + "\n\n"


# --- GENERATE: one spend is one operation ---------------------------------
#
# Decision 3 as Caleb settled it on 2026-09-16: the ENGINE generates, no
# session holds the spending binary. `spend` is the only door a credit goes
# through: it re-prices, creates, writes a `pending` row carrying the job id
# BEFORE the wait, waits, downloads, probes, and finalizes the row `done`.
# A death between create and download leaves a row to finalize on rerun,
# never a stray to re-spend. `reconcile` then matches the run's rows to the
# balance delta and the transaction window, because the log carries no job
# id (window, name and amount are all it offers).

import time as _time
import urllib.request

LICENSE_SHORT = "Higgsfield ToU: output owned, commercial use permitted"
LICENSE_NOTE = ("Generated on Higgsfield under its Terms of Use (effective 2026-08-27): the "
                "account owner owns the output, commercial use including YouTube monetisation "
                "is permitted, no attribution required; Higgsfield may train on content left "
                "hosted on its platform (s.4.4).")
WAIT_TIMEOUT = "20m"
PRICE_TOLERANCE = 0.10


def _rounds_doc(slug: str) -> "tuple[Path, dict]":
    p = work_path(slug) / "asset_requests.json"
    try:
        doc = json.loads(p.read_text())
    except (OSError, ValueError):
        raise IngestError("no asset_requests.json for %s" % slug)
    return p, doc


def _find_round(doc: dict, round_id: str) -> dict:
    for r in doc.get("rounds", []) or []:
        if isinstance(r, dict) and str(r.get("id")) == str(round_id):
            return r
    raise IngestError("no round %s" % round_id)


def step_command(round_: dict, step: dict, plate_jobs: "dict[str, str]",
                 soul_id: "str | None") -> "list[str]":
    """The `generate create` argv for one step, marks applied. Pure.

    A Seedance mark swaps the motion model; a pro mark sets the model's
    tier field to its pro value, else its std value is stated explicitly
    so a changed CLI default can never change what was priced. A
    `start_image` names an earlier stage and is resolved to that stage's
    JOB ID, never a path (a path would upload). A Soul step carries the
    reference only on a Soul model.
    """
    marks = round_.get("marks") if isinstance(round_.get("marks"), dict) else {}
    model = str(step.get("model") or "")
    stage = str(step.get("stage") or "")
    if marks.get("seedance") and model == DEFAULT_VIDEO["model"]:
        model = SEEDANCE_MODEL
    pro = stage in (marks.get("pro") or []) and step.get("tier") == "pro"
    args = ["generate", "create", model, "--prompt", str(step.get("prompt") or "")]
    aspect = round_.get("aspect")
    if aspect:
        args += ["--aspect_ratio", str(aspect)]
    field = TIER_FIELD.get(model)
    if field:
        name, value = field if pro else TIER_STD[model]
        args += ["--" + name, value]
    if model in ("kling3_0", "kling3_0_turbo"):
        args += ["--duration", str(step.get("duration") or DEFAULT_VIDEO["duration"]),
                 "--sound", "off"]
    elif model == SEEDANCE_MODEL:
        args += ["--duration", str(step.get("duration") or DEFAULT_VIDEO["duration"]),
                 "--generate_audio", "false"]
    start = step.get("start_image")
    if start:
        job = plate_jobs.get(str(start))
        if not job:
            raise IngestError("step %s names start_image %r but that stage has no job yet"
                              % (stage, start))
        if model == SEEDANCE_MODEL:
            args += ["--mode", "omni_reference", "--start-image", job]
        else:
            args += ["--start-image", job]
    if step.get("soul"):
        if model not in SOUL_MODELS:
            raise IngestError("step %s asks for the Soul on %s, which takes no reference"
                              % (stage, model))
        if not soul_id:
            raise IngestError("step %s needs the Soul but NINTH_ROOM_SOUL_ID is not set" % stage)
        args += ["--custom_reference_id", soul_id]
    args.append("--json")
    return args


_UUID_RE = None


def _json_out(out: str, what: str) -> dict:
    """The CLI's JSON, whatever shape it took: an object, a list of objects,
    or (as `generate create` without `--wait` returns, found 2026-09-16 at
    the cost of one orphaned job) a bare list of id strings. A lone UUID
    anywhere in the text is the id when nothing else names one."""
    global _UUID_RE
    if _UUID_RE is None:
        import re
        _UUID_RE = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
                              r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
    try:
        d = json.loads(out)
    except ValueError:
        d = None
    if isinstance(d, list):
        d = d[0] if d else {}
    if isinstance(d, str):
        d = {"id": d}
    if not isinstance(d, dict):
        d = {}
    if not d.get("id"):
        ids = _UUID_RE.findall(out or "")
        if len(set(ids)) == 1:
            d["id"] = ids[0]
    if not d and not (out or "").strip():
        raise IngestError("%s returned nothing" % what)
    return d


def download(url: str, dest: Path, log=None) -> Path:
    """Fetch a result to `dest`. Separate so tests never touch the network."""
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    with urllib.request.urlopen(url, timeout=300) as resp, open(tmp, "wb") as fh:
        while True:
            chunk = resp.read(1 << 20)
            if not chunk:
                break
            fh.write(chunk)
    tmp.replace(dest)
    return dest


def probe_media(path: Path, expect_seconds: "float | None" = None) -> dict:
    """Width, height and duration of what arrived, or a refusal. A clip
    shorter than asked is a short clip that would play fine and end early,
    the failure nobody notices until the episode is up."""
    path = Path(path)
    if path.suffix.lower() in (".mp4", ".mov", ".webm"):
        proc = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                               "-show_entries", "stream=width,height,duration",
                               "-of", "csv=p=0", str(path)], capture_output=True, text=True)
        parts = proc.stdout.strip().split(",") if proc.returncode == 0 else []
        if len(parts) < 3:
            raise IngestError("%s does not decode as video" % path.name)
        w, h, d = int(parts[0]), int(parts[1]), float(parts[2])
        if expect_seconds and d < expect_seconds - 0.5:
            raise IngestError("%s runs %.2fs, asked for %.1f" % (path.name, d, expect_seconds))
        return {"width": w, "height": h, "duration": round(d, 3)}
    from PIL import Image
    try:
        im = Image.open(path)
        im.load()
    except Exception as e:
        raise IngestError("%s does not decode as an image: %s" % (path.name, e))
    return {"width": im.size[0], "height": im.size[1]}


def _credits(log=None) -> "float | None":
    try:
        rc, out, err = cli(["account", "status", "--json"], timeout=30)
    except IngestError:
        return None
    if rc != 0:
        return None
    try:
        return float(json.loads(out).get("credits"))
    except (ValueError, TypeError, AttributeError):
        return None


def spend(slug: str, round_id: str, stage: str, log=print) -> dict:
    """Spend ONE approved step and return its finalized ledger row.

    Idempotent by (round_id, stage): a `done` row is returned as is; a
    `pending` row (a death after create) is finalized without a second
    create. Refuses before create when the live price is over the estimate
    by more than PRICE_TOLERANCE or the remaining steps would pass the cap.
    """
    work = work_path(slug)
    adir = work / "assets"
    rq, doc = _rounds_doc(slug)
    round_ = _find_round(doc, round_id)
    if round_.get("status") not in ("approved", "done"):
        raise IngestError("round %s is %s, not approved" % (round_id, round_.get("status")))
    steps = [s for s in (round_.get("steps") or []) if isinstance(s, dict)]
    step = next((s for s in steps if str(s.get("stage")) == str(stage)), None)
    if step is None:
        raise IngestError("round %s has no stage %s" % (round_id, stage))
    row_id = "%s-%s" % (round_id, stage)
    existing = next((a for a in ledger(slug) if a.get("id") == row_id), None)
    if existing and existing.get("status") == "done":
        log("[illustrate] %s already done" % row_id)
        return existing

    brief = {}
    try:
        brief = json.loads((work / "story_brief.json").read_text())
    except (OSError, ValueError):
        pass
    script = plan = None
    try:
        script = json.loads((work / "script.json").read_text())
    except (OSError, ValueError):
        try:
            plan = json.loads((work / "edit_plan.json").read_text())
        except (OSError, ValueError):
            pass
    errors = validate_round(round_, brief.get("delivery"), script=script, plan=plan)
    if errors:
        raise IngestError("round %s is not valid: %s" % (round_id, errors[0]))
    remaining = sum(float(s.get("credits") or 0) for s in steps if not s.get("done"))
    cap_check(slug, [{"estimate_credits": remaining}])

    plate_jobs = {str(s.get("stage")): s.get("job_id") for s in steps if s.get("job_id")}
    cmd = step_command(round_, step, plate_jobs, paths.soul_id())
    model = cmd[2]
    honesty = round_.get("honesty")
    estimate = float(step.get("credits") or 0)

    if existing and existing.get("status") == "pending":
        job_id = existing["job_id"]
        log("[illustrate] %s has a pending job %s; finalizing without a second create"
            % (row_id, job_id))
        display = existing.get("display_name") or model
        balance_before = existing.get("balance_before")
    else:
        # re-price with the exact argv the create will use
        rc, out, err = cli(["generate", "cost"] + cmd[2:], timeout=60)
        if rc != 0:
            raise IngestError("could not price %s: %s" % (row_id, (err or out)[-200:]))
        price = float(_json_out(out, "generate cost").get("credits") or 0)
        if price > estimate * (1 + PRICE_TOLERANCE) + 1e-9:
            raise IngestError("%s now costs %.1f credits against an estimate of %.1f — "
                              "re-propose rather than spend past the estimate"
                              % (row_id, price, estimate))
        balance_before = _credits(log)
        rc, out, err = cli(cmd, timeout=120)
        if rc != 0:
            raise IngestError("create failed for %s: %s" % (row_id, (err or out)[-300:]))
        created = _json_out(out, "generate create")
        job_id = str(created.get("id") or "")
        if not job_id:
            raise IngestError("create returned no job id for %s: %s" % (row_id, out[-200:]))
        display = created.get("display_name") or model
        # the row exists BEFORE the wait: a death from here on leaves a
        # pending row with the job id, never an unexplained credit
        append_row(adir, {
            "id": row_id, "file": "", "kind": "illustration", "honesty": honesty,
            "round_id": round_id, "stage": stage, "model": model, "display_name": display,
            "job_id": job_id, "cost_credits": estimate, "status": "pending",
            "created_at": _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime()),
            "balance_before": balance_before, "prompt": step.get("prompt"),
            "section_id": round_.get("section_id"), "beat_id": round_.get("beat_id"),
            "target": round_.get("target"), "aspect": round_.get("aspect"),
            "note": round_.get("note"), "license": LICENSE_SHORT, "license_note": LICENSE_NOTE,
            "what": "%s: %s" % (stage, (round_.get("why") or "")[:80]),
        })
        step["job_id"] = job_id
        rq.write_text(json.dumps(doc, indent=1, ensure_ascii=False))
        log("[illustrate] %s created job %s on %s" % (row_id, job_id, display))

    rc, out, err = cli(["generate", "wait", job_id, "--timeout", WAIT_TIMEOUT, "--json"],
                       timeout=1300)
    result = _json_out(out, "generate wait") if rc == 0 else {}
    status = str(result.get("status") or "")
    row = next((a for a in ledger(slug) if a.get("id") == row_id), None) or {}
    if status != "completed" or not result.get("result_url"):
        reason = result.get("fail_reason") or (err or out)[-200:] or status or "unknown"
        row.update({"status": "refused", "cost_credits": 0.0, "fail_reason": str(reason)})
        append_row(adir, row)
        raise IngestError("%s was refused by Higgsfield (%s); the row is closed at zero "
                          "credits and the round stays approved" % (row_id, reason))
    url = str(result["result_url"])
    ext = Path(url.split("?")[0]).suffix or (".mp4" if model in ("kling3_0", "kling3_0_turbo", SEEDANCE_MODEL) else ".png")
    dest = adir / (row_id + ext)
    download(url, dest, log=log)
    probe = probe_media(dest, expect_seconds=(float(step.get("duration") or DEFAULT_VIDEO["duration"])
                                             if ext in (".mp4", ".mov", ".webm") else None))
    balance_after = _credits(log)
    cost = estimate
    if balance_before is not None and balance_after is not None:
        delta = float(balance_before) - float(balance_after)
        if 0 < delta <= estimate * 2:
            cost = round(delta, 3)
    # the wait result names the model the way the transaction log does
    # ("Kling v3.0", not kling3_0); the bare-list create never did, and
    # reconcile matches on that name (2026-09-16, the first live run)
    row.update({"file": dest.name, "status": "done", "cost_credits": cost,
                "result_url": url, "bytes": dest.stat().st_size,
                "display_name": result.get("display_name") or row.get("display_name") or model})
    row.update(probe)
    row.pop("balance_before", None)
    append_row(adir, row)
    step["done"] = True
    if all(s.get("done") for s in steps):
        round_["status"] = "done"
    round_.pop("error", None)
    rq.write_text(json.dumps(doc, indent=1, ensure_ascii=False))
    log("[illustrate] %s done: %s, %.1f credits" % (row_id, dest.name, cost))
    return row


def reconcile(rows: "list[dict]", items: "list[dict]", balance_delta: "float | None") -> dict:
    """Match this run's ledger rows to Higgsfield's transaction items by
    name and amount (the log carries no job id), and the balance delta to
    the rows' sum. Pure; the runner fetches both sides and calls this."""
    unmatched_rows = []
    pool = [dict(i) for i in items if str(i.get("action")) == "spend"]
    for r in rows:
        if r.get("status") != "done":
            continue
        want_name = str(r.get("display_name") or "")
        want = float(r.get("cost_credits") or 0)
        hit = next((i for i in pool if str(i.get("display_name")) == want_name
                    and abs(abs(float(i.get("credits") or 0)) - want) < 0.01), None)
        if hit is None:
            unmatched_rows.append(r.get("id"))
        else:
            pool.remove(hit)
    out = {"unmatched_items": pool, "unmatched_rows": unmatched_rows}
    if balance_delta is not None:
        total = sum(float(r.get("cost_credits") or 0) for r in rows if r.get("status") == "done")
        if abs(balance_delta - total) > 0.01 and not pool:
            out["delta_gap"] = round(balance_delta - total, 3)
    return out


def transactions_since(since_iso: str, pages: int = 5) -> "list[dict]":
    """Every transaction item newer than `since_iso`, paged by cursor."""
    out, cursor = [], None
    for _ in range(pages):
        args = ["account", "transactions", "--size", "40", "--json"]
        if cursor:
            args += ["--cursor", cursor]
        rc, text, err = cli(args, timeout=60)
        if rc != 0:
            break
        raw = _json_out(text, "transactions") if text.strip().startswith("{") else {"items": json.loads(text or "[]")}
        items = raw.get("items") or raw.get("transactions") or raw.get("data") or []
        for it in items:
            if str(it.get("created_at", "")) >= since_iso:
                out.append(it)
        if not items or str(items[-1].get("created_at", "")) < since_iso:
            break
        cursor = raw.get("cursor") or raw.get("next_cursor")
        if not cursor:
            break
    return out


# --- the marker, the credits, the disclosure --------------------------------

MARK_MAX_S = 15.0        # validate_graphics_plan's card ceiling
MARK_PREFIX = "MARK"


def _bake_cards(slug: str, ids: "list[str]", log=None) -> None:
    """Bake the named cards so the proxy can composite them at once.
    Separate so tests never launch Chrome."""
    if not ids:
        return
    from . import graphics
    try:
        from .editroom import _orientation
        orient = _orientation(slug)
    except Exception:
        orient = None
    graphics.build_cards(slug, orientation=orient, only_ids=list(ids), log=log or (lambda *a: None))


def reconstruction_spans(slug: str) -> "list[dict]":
    """Every stretch of the cut that shows a reconstruction, in beat time:
    a cover with provenance reconstruction, or a spine beat carrying it.
    Long stretches are split under the card ceiling."""
    p = work_path(slug) / "analysis" / "timeline_map.json"
    try:
        beats = json.loads(p.read_text()).get("beats", [])
    except (OSError, ValueError):
        return []
    spans = []
    for b in beats:
        rec0 = float(b.get("record_s", 0.0))
        if b.get("provenance") == "reconstruction":
            spans.append((b["id"], 0.0, float(b.get("record_e", rec0)) - rec0))
        for c in b.get("broll") or []:
            if c.get("provenance") == "reconstruction":
                spans.append((b["id"], round(float(c.get("record_s", rec0)) - rec0, 3),
                              float(c.get("duration", 0.0))))
    out = []
    for bid, at, dur in spans:
        while dur > 0:
            piece = min(dur, MARK_MAX_S)
            out.append({"beat_id": bid, "at": round(at, 3), "duration": round(piece, 3)})
            at += piece
            dur -= piece
    return out


def _mark_card(n: int, span: dict) -> dict:
    return {"id": "%s%02d" % (MARK_PREFIX, n), "type": "section", "kit_type": "provenance",
            "text": "RECONSTRUCTION", "kicker": "RECONSTRUCTION", "beat_id": span["beat_id"],
            "at": span["at"], "duration": max(1.0, span["duration"]), "engine": "illustration"}


def _same_span(card: dict, span: dict) -> bool:
    return (card.get("beat_id") == span["beat_id"]
            and abs(float(card.get("at", -1)) - span["at"]) < 0.05
            and abs(float(card.get("duration", -1)) - max(1.0, span["duration"])) < 0.05)


def sync_markers(slug: str, bake: bool = True, log=None) -> dict:
    """Make graphics_plan.json carry exactly one MARK card per reconstruction
    span: keep the ones that still match, drop the orphans, add the rest,
    and bake what changed so the very next proxy shows the eyebrow. Writes
    nothing when there is nothing to mark and no marker to remove."""
    work = work_path(slug)
    spans = reconstruction_spans(slug)
    gp = work / "graphics_plan.json"
    try:
        plan = json.loads(gp.read_text())
    except (OSError, ValueError):
        plan = None
    cards = list((plan or {}).get("cards", []) or [])
    marks = [c for c in cards if str(c.get("id", "")).startswith(MARK_PREFIX)]
    if not spans and not marks:
        return {"added": [], "removed": [], "kept": []}
    kept, removed, wanted = [], [], list(spans)
    for c in marks:
        hit = next((sp for sp in wanted if _same_span(c, sp)), None)
        if hit is None:
            removed.append(c["id"])
        else:
            kept.append(c["id"])
            wanted.remove(hit)
    others = [c for c in cards if not str(c.get("id", "")).startswith(MARK_PREFIX)]
    survivors = [c for c in marks if c["id"] in kept]
    used = {int(c["id"][len(MARK_PREFIX):]) for c in survivors if c["id"][len(MARK_PREFIX):].isdigit()}
    added = []
    n = 1
    for sp in wanted:
        while n in used:
            n += 1
        used.add(n)
        card = _mark_card(n, sp)
        survivors.append(card)
        added.append(card["id"])
    if plan is None:
        plan = {"slug": slug, "cards": []}
    plan["cards"] = others + sorted(survivors, key=lambda c: c["id"])
    gp.write_text(json.dumps(plan, indent=1, ensure_ascii=False))
    for rid in removed:
        mov = work / "graphics" / (rid + ".mov")
        if mov.exists():
            mov.unlink()
    if bake and added and (work / "analysis" / "timeline_map.json").exists():
        _bake_cards(slug, added, log=log)
    return {"added": added, "removed": removed, "kept": kept}


def marker_notes(slug: str) -> "list[str]":
    """What is wrong with the markers, as sentences: a reconstruction span
    with no MARK card over it, and any other card overlapping a MARK span
    on its beat (never two cards on screen at once)."""
    work = work_path(slug)
    spans = reconstruction_spans(slug)
    try:
        cards = json.loads((work / "graphics_plan.json").read_text()).get("cards", []) or []
    except (OSError, ValueError):
        cards = []
    marks = [c for c in cards if str(c.get("id", "")).startswith(MARK_PREFIX)]
    notes = []
    for sp in spans:
        if not any(_same_span(c, sp) for c in marks):
            notes.append("%s: a reconstruction runs %.1fs at %.1fs unmarked — "
                         "assemble re-syncs the markers" % (sp["beat_id"], sp["duration"], sp["at"]))
    for c in cards:
        if str(c.get("id", "")).startswith(MARK_PREFIX):
            continue
        for m in marks:
            if m.get("beat_id") != c.get("beat_id"):
                continue
            a0, a1 = float(c.get("at", 0)), float(c.get("at", 0)) + float(c.get("duration", 0))
            m0, m1 = float(m.get("at", 0)), float(m.get("at", 0)) + float(m.get("duration", 0))
            if a0 < m1 - 0.05 and m0 < a1 - 0.05:
                notes.append("%s: card %s overlaps marker %s — never two cards on "
                             "screen at once; move the card off the reconstruction"
                             % (c.get("beat_id"), c.get("id"), m.get("id")))
    return notes


def in_cut(slug: str) -> "list[dict]":
    """The illustration rows whose promoted clip the plan uses as a cover
    or a spine, in row order. What the credits name."""
    work = work_path(slug)
    try:
        plan = json.loads((work / "edit_plan.json").read_text())
        clips = json.loads((work / "analysis" / "broll.json").read_text()).get("clips", [])
    except (OSError, ValueError):
        return []
    used = set()
    for b in plan.get("beats", []) or []:
        for c in b.get("broll") or []:
            used.add(c.get("clip_id"))
        if isinstance(b.get("spine"), dict):
            used.add(b["spine"].get("clip_id"))
    files = {c.get("file") for c in clips if c.get("id") in used and c.get("provenance")}
    out = []
    for a in ledger(slug):
        name = a.get("promoted_as") or a.get("file")
        stem_still = Path(str(a.get("file") or "")).stem + "_still.mp4"
        if name in files or stem_still in files:
            out.append(a)
    return out
