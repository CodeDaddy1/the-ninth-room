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
TIER_FIELD = {"kling3_0": ("mode", "pro"), "kling3_0_turbo": ("mode", "pro"),
              "seedance_2_5": ("resolution", "1080p"),
              "nano_banana_pro": ("resolution", "4k"),
              "text2image_soul_v2": ("quality", "4k"),
              "soul_cinema_studio": ("quality", "4k")}
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
