"""Schema validators for agent output files.

Hand-rolled, stdlib-only. Each `validate_*` function:

    * Accepts the already-parsed in-memory value (dict / list / scalar).
    * Returns `list[str]` of human-readable error messages.
    * Empty list means valid.

Fail-loud: a partial / shaped-wrong result trips an error rather than being
silently accepted. The worker's file watcher (Phase 4) refuses to advance
state when validation returns errors.

There's also `load_and_validate(path, schema_fn)` which reads JSON from disk
and runs the validator in one call — what `worker/cli.py validate` uses.
"""

from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Callable


# --- vocabularies --------------------------------------------------------

PILLARS = {
    "hidden_in_plain_sight",
    "unsolved",
    "how_it_works",
    "lost_forgotten",
    "scales_of_wonder",
    "human_strange",
}

PLATFORMS = {
    "youtube_long",
    "youtube_short",
    "instagram_reel",
    "instagram_carousel",
    "instagram_story",
}

SOURCE_TYPES = {
    "stock",
    "ai_generated",
    "motion_graphic",
    "archival",
    "custom_shoot",
}

ORIENTATIONS = {"landscape", "portrait"}

VERIFIED = {"Confirmed", "Disputed", "Unsolved"}


# --- helpers -------------------------------------------------------------

def _is_str(v: Any) -> bool:
    return isinstance(v, str) and v.strip() != ""


def _is_str_list(v: Any, *, min_len: int = 0) -> bool:
    if not isinstance(v, list):
        return False
    if len(v) < min_len:
        return False
    return all(isinstance(x, str) and x.strip() for x in v)


def _check_required(obj: dict, fields: list[str], prefix: str) -> list[str]:
    errs = []
    for f in fields:
        if f not in obj:
            errs.append(f"{prefix}: missing '{f}'")
    return errs


# --- curiosity-scout: topics.json ----------------------------------------

def validate_topics(data: Any) -> list[str]:
    """Schema:
    {
      "generated_at": "ISO timestamp",
      "pillar_focus": "<pillar>" | null,
      "topics": [
        {
          "topic": str,
          "pillar": <one of PILLARS>,
          "hook": str,
          "payoff": str,
          "verified": <one of VERIFIED>,
          "fact_check_notes": str,
          "sources": [str, ...],            # at least 1
          "best_format": <one of PLATFORMS>,
          "notes": str (optional),
        }, ...
      ]
    }
    """
    errs: list[str] = []
    if not isinstance(data, dict):
        return ["root must be an object"]
    errs += _check_required(data, ["topics"], "root")
    if data.get("pillar_focus") is not None and data["pillar_focus"] not in PILLARS:
        errs.append(f"pillar_focus '{data['pillar_focus']}' not in PILLARS")
    topics = data.get("topics")
    if not isinstance(topics, list) or len(topics) == 0:
        errs.append("topics must be a non-empty array")
        return errs
    for i, t in enumerate(topics):
        p = f"topics[{i}]"
        if not isinstance(t, dict):
            errs.append(f"{p}: must be an object")
            continue
        for f in ("topic", "hook", "payoff", "fact_check_notes"):
            if not _is_str(t.get(f)):
                errs.append(f"{p}: '{f}' must be a non-empty string")
        if t.get("pillar") not in PILLARS:
            errs.append(f"{p}: pillar '{t.get('pillar')}' not in PILLARS")
        if t.get("verified") not in VERIFIED:
            errs.append(f"{p}: verified '{t.get('verified')}' not in {sorted(VERIFIED)}")
        if t.get("best_format") not in PLATFORMS:
            errs.append(f"{p}: best_format '{t.get('best_format')}' not in PLATFORMS")
        if not _is_str_list(t.get("sources"), min_len=1):
            errs.append(f"{p}: sources must be an array of >=1 non-empty strings")
    return errs


# --- content-strategist: slate.json --------------------------------------

def validate_slate(data: Any) -> list[str]:
    """Schema:
    {
      "week": "YYYY-Www",
      "flagship_slug": str,
      "slots": [
        {
          "slug": str,                       # url-safe
          "topic": str,
          "pillar": <one of PILLARS>,
          "platform": <one of PLATFORMS>,
          "scheduled_day": "Mon|Tue|...",
          "hook_angle": str,
          "cross_promo_slug": str | null,
          "agent": "youtube-scriptwriter | instagram-copywriter",
          "notes": str (optional)
        }, ...
      ],
      "gaps": [str, ...]                     # optional
    }
    """
    errs: list[str] = []
    if not isinstance(data, dict):
        return ["root must be an object"]
    errs += _check_required(data, ["week", "flagship_slug", "slots"], "root")
    if not _is_str(data.get("week")) or "-W" not in str(data.get("week")):
        errs.append("week must be ISO week format 'YYYY-Www' (e.g. '2026-W23')")
    slots = data.get("slots")
    if not isinstance(slots, list) or len(slots) == 0:
        errs.append("slots must be a non-empty array")
        return errs

    seen_slugs = set()
    flagship = data.get("flagship_slug")
    for i, s in enumerate(slots):
        p = f"slots[{i}]"
        if not isinstance(s, dict):
            errs.append(f"{p}: must be an object")
            continue
        slug = s.get("slug")
        if not _is_str(slug) or not all(c.isalnum() or c in "-_" for c in slug):
            errs.append(f"{p}: slug must be url-safe (alnum, '-', '_')")
        elif slug in seen_slugs:
            errs.append(f"{p}: slug '{slug}' duplicated")
        else:
            seen_slugs.add(slug)
        if s.get("pillar") not in PILLARS:
            errs.append(f"{p}: pillar '{s.get('pillar')}' not in PILLARS")
        if s.get("platform") not in PLATFORMS:
            errs.append(f"{p}: platform '{s.get('platform')}' not in PLATFORMS")
        if s.get("agent") not in {"youtube-scriptwriter", "instagram-copywriter"}:
            errs.append(f"{p}: agent must be 'youtube-scriptwriter' or 'instagram-copywriter'")
        for f in ("topic", "hook_angle"):
            if not _is_str(s.get(f)):
                errs.append(f"{p}: '{f}' must be a non-empty string")

    if flagship not in seen_slugs:
        errs.append(f"flagship_slug '{flagship}' must match one of the slot slugs")
    return errs


# --- asset-scout: shot_list.json ----------------------------------------

def validate_shot_list(data: Any) -> list[str]:
    """Schema:
    {
      "video_title": str,
      "platform": <one of PLATFORMS>,
      "default_orientation": <one of ORIENTATIONS>,
      "shots": [
        {
          "shot_id": "S\\d+",
          "timecode": str,                   # "M:SS-M:SS"
          "script_line": str,
          "visual": str,
          "source_type": <one of SOURCE_TYPES>,
          "queries": [str, ...],             # >=1 for source_type=stock
          "ai_prompt": str (required when ai_generated),
          "orientation": <one of ORIENTATIONS> (optional),
          "duration_sec": number > 0,
          "license_requirement": str,
          "fallback": str,
          "needs_rights_check": bool,
          "notes": str (optional)
        }, ...
      ]
    }
    """
    errs: list[str] = []
    if not isinstance(data, dict):
        return ["root must be an object"]
    errs += _check_required(data, ["video_title", "platform", "default_orientation", "shots"], "root")
    if data.get("platform") not in PLATFORMS:
        errs.append(f"platform '{data.get('platform')}' not in PLATFORMS")
    if data.get("default_orientation") not in ORIENTATIONS:
        errs.append(f"default_orientation '{data.get('default_orientation')}' not in ORIENTATIONS")
    shots = data.get("shots")
    if not isinstance(shots, list) or len(shots) == 0:
        errs.append("shots must be a non-empty array")
        return errs

    seen_ids = set()
    for i, s in enumerate(shots):
        p = f"shots[{i}]"
        if not isinstance(s, dict):
            errs.append(f"{p}: must be an object")
            continue
        sid = s.get("shot_id")
        if not (_is_str(sid) and sid[0] == "S" and sid[1:].isdigit()):
            errs.append(f"{p}: shot_id must match 'S\\d+' (got {sid!r})")
        elif sid in seen_ids:
            errs.append(f"{p}: shot_id '{sid}' duplicated")
        else:
            seen_ids.add(sid)
        for f in ("timecode", "script_line", "visual", "license_requirement", "fallback"):
            if not _is_str(s.get(f)):
                errs.append(f"{p}: '{f}' must be a non-empty string")
        if s.get("source_type") not in SOURCE_TYPES:
            errs.append(f"{p}: source_type '{s.get('source_type')}' not in SOURCE_TYPES")
        if s.get("source_type") == "stock" and not _is_str_list(s.get("queries"), min_len=1):
            errs.append(f"{p}: queries must be a non-empty string array for stock shots")
        if s.get("source_type") == "ai_generated" and not _is_str(s.get("ai_prompt")):
            errs.append(f"{p}: ai_prompt required for ai_generated shots")
        dur = s.get("duration_sec")
        if not (isinstance(dur, (int, float)) and dur > 0):
            errs.append(f"{p}: duration_sec must be a positive number")
        if "orientation" in s and s["orientation"] not in ORIENTATIONS:
            errs.append(f"{p}: orientation '{s['orientation']}' not in ORIENTATIONS")
        if not isinstance(s.get("needs_rights_check"), bool):
            errs.append(f"{p}: needs_rights_check must be a bool")
    return errs


# --- visual-director: visuals.json --------------------------------------

def validate_visuals(data: Any) -> list[str]:
    """Schema:
    {
      "thumbnail": {
        "concept": str,
        "subject": str,
        "text": str,                         # 3-5 words
        "accent_word": str,
        "composition": str,
        "logo_position": str (optional),
      },
      "cover": {                              # for reel/short, optional
        "concept": str,
        "first_frame_text": str
      } | null,
      "carousel_slides": [                    # for carousel, optional
        { "slide": int, "role": str, "title": str, "body": str (optional) }, ...
      ] | null,
      "on_screen_text": [                     # for reel/short bodies
        { "timecode": str, "text": str, "emphasis_words": [str, ...] }, ...
      ],
      "consistency_check": {
        "palette_ok": bool,
        "fonts_ok": bool,
        "logo_placement_ok": bool,
        "thumbnail_legible_small": bool,
        "matches_recent_posts": bool
      }
    }
    """
    errs: list[str] = []
    if not isinstance(data, dict):
        return ["root must be an object"]
    errs += _check_required(data, ["thumbnail", "on_screen_text", "consistency_check"], "root")

    thumb = data.get("thumbnail")
    if not isinstance(thumb, dict):
        errs.append("thumbnail must be an object")
    else:
        for f in ("concept", "subject", "text", "accent_word", "composition"):
            if not _is_str(thumb.get(f)):
                errs.append(f"thumbnail.{f} must be a non-empty string")
        if isinstance(thumb.get("text"), str):
            wc = len(thumb["text"].split())
            if wc < 1 or wc > 6:
                errs.append(f"thumbnail.text should be 1-6 words (got {wc})")

    osts = data.get("on_screen_text")
    if not isinstance(osts, list):
        errs.append("on_screen_text must be an array")
    else:
        for i, ost in enumerate(osts):
            if not isinstance(ost, dict):
                errs.append(f"on_screen_text[{i}]: must be an object")
                continue
            if not _is_str(ost.get("timecode")) or not _is_str(ost.get("text")):
                errs.append(f"on_screen_text[{i}]: 'timecode' and 'text' required")
            if not isinstance(ost.get("emphasis_words", []), list):
                errs.append(f"on_screen_text[{i}]: emphasis_words must be an array")

    check = data.get("consistency_check")
    if not isinstance(check, dict):
        errs.append("consistency_check must be an object")
    else:
        for f in ("palette_ok", "fonts_ok", "logo_placement_ok", "thumbnail_legible_small", "matches_recent_posts"):
            if not isinstance(check.get(f), bool):
                errs.append(f"consistency_check.{f} must be a bool")
    return errs


# --- copywriters: tray/<platform>.json ----------------------------------

def validate_tray_entry(data: Any) -> list[str]:
    """Schema (per platform — written by instagram-copywriter or
    youtube-scriptwriter at publish prep time):
    {
      "platform": <one of PLATFORMS>,
      "title": str (required for YouTube),
      "caption": str,
      "hashtags": [str, ...],
      "description": str (YouTube),
      "timestamps": str (YouTube long-form, optional),
      "thumbnail_brief": str,
      "on_screen_text": [str, ...] (optional),
      "music_credit": str (optional),
      "cross_promo_note": str (optional)
    }
    """
    errs: list[str] = []
    if not isinstance(data, dict):
        return ["root must be an object"]
    if data.get("platform") not in PLATFORMS:
        errs.append(f"platform '{data.get('platform')}' not in PLATFORMS")
    if not _is_str(data.get("caption")):
        errs.append("caption must be a non-empty string")
    if not _is_str_list(data.get("hashtags"), min_len=1):
        errs.append("hashtags must be a non-empty string array")
    if not _is_str(data.get("thumbnail_brief")):
        errs.append("thumbnail_brief must be a non-empty string")
    plat = data.get("platform")
    if plat in {"youtube_long", "youtube_short"}:
        if not _is_str(data.get("title")):
            errs.append(f"title required for {plat}")
        if not _is_str(data.get("description")):
            errs.append(f"description required for {plat}")
    # Platform-specific cap checks (informational — caps drift).
    if plat == "instagram_reel" and isinstance(data.get("caption"), str) and len(data["caption"]) > 2200:
        errs.append("caption exceeds Instagram's 2200-char cap")
    if plat in {"youtube_long", "youtube_short"} and isinstance(data.get("title"), str) and len(data["title"]) > 100:
        errs.append("title exceeds YouTube's 100-char cap")
    return errs


# --- performance-analyst: analyst-YYYY-WW.md ----------------------------

def validate_analyst_brief(text: str) -> list[str]:
    """Markdown, not JSON. We just check it contains the required H2 sections
    so downstream rendering and the scout hand-off don't break."""
    errs: list[str] = []
    if not isinstance(text, str) or not text.strip():
        return ["analyst brief must be a non-empty string"]
    required_sections = [
        "## Scorecard",
        "## What worked",
        "## What didn't",
        "## Next-batch brief",
    ]
    for s in required_sections:
        if s not in text:
            errs.append(f"missing required section heading: {s!r}")
    return errs


# --- dispatcher ----------------------------------------------------------

SCHEMA_BY_FILE: dict[str, Callable[[Any], list[str]]] = {
    "topics.json": validate_topics,
    "slate.json": validate_slate,
    "shot_list.json": validate_shot_list,
    "visuals.json": validate_visuals,
    # tray files dispatch separately because the filename varies by platform.
}


def load_and_validate(path: Path) -> list[str]:
    """Load `path` and run the right validator. Returns error list."""
    if not path.exists():
        return [f"file not found: {path}"]
    name = path.name
    text = path.read_text()

    # tray/<platform>.json
    if path.parent.name == "tray" and name.endswith(".json"):
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            return [f"invalid JSON: {e}"]
        return validate_tray_entry(data)

    # planning markdown
    if name.startswith("analyst-") and name.endswith(".md"):
        return validate_analyst_brief(text)

    # planning JSON (topics-*.json, slate-*.json, metrics-*.json)
    if name.startswith("topics-"):
        return _parse_then(text, validate_topics)
    if name.startswith("slate-"):
        return _parse_then(text, validate_slate)
    if name.startswith("metrics-"):
        return []  # metrics-*.json is staged by the worker, schema-trusted.

    # per-video files
    schema = SCHEMA_BY_FILE.get(name)
    if schema is None:
        return [f"no schema registered for filename '{name}'"]
    return _parse_then(text, schema)


def _parse_then(text: str, schema_fn: Callable[[Any], list[str]]) -> list[str]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        return [f"invalid JSON: {e}"]
    return schema_fn(data)
