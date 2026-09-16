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
