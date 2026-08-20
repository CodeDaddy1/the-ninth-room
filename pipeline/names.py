"""Proper-noun corrections for whisper transcripts.

Whisper hears names phonetically: Caleb's daughter Sofia came out "Sophia" in
every transcript on the HMNS shoot, and the wrong spelling flowed through
takes.json into captions and onto rendered cards before anyone caught it
(2026-08-19). The fix belongs at the source: `brand/names.json` maps wrong
spellings to right ones, and `correct_words` runs on every fresh
transcription in `pipeline/ingest.py`.

Corrections are whole-word only (regex word boundaries), so punctuation
survives ("Sophia." -> "Sofia.") and substrings are untouched ("Sophias"
stays as-is — if that ever appears, add it to the map explicitly).

What breaks if this is wrong: a family member's name is misspelled on a
scoreboard in the finished video.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

NAMES_PATH = Path(__file__).resolve().parent.parent / "brand" / "names.json"


def load_corrections() -> "dict[str, str]":
    if not NAMES_PATH.exists():
        return {}
    data = json.loads(NAMES_PATH.read_text())
    return data.get("transcript_corrections", {})


def _pattern(corrections: "dict[str, str]"):
    if not corrections:
        return None
    alts = "|".join(re.escape(k) for k in sorted(corrections, key=len, reverse=True))
    return re.compile(r"\b(%s)\b" % alts)


def correct_text(text: str, corrections: "dict[str, str] | None" = None) -> str:
    """Apply the corrections map to free text, whole words only."""
    if corrections is None:
        corrections = load_corrections()
    pat = _pattern(corrections)
    if not pat:
        return text
    return pat.sub(lambda m: corrections[m.group(1)], text)


def correct_words(words: "list[dict]",
                  corrections: "dict[str, str] | None" = None) -> int:
    """Correct the "w" field of whisper word dicts IN PLACE. Returns the
    number of words changed."""
    if corrections is None:
        corrections = load_corrections()
    pat = _pattern(corrections)
    if not pat:
        return 0
    changed = 0
    for wd in words:
        fixed = pat.sub(lambda m: corrections[m.group(1)], wd["w"])
        if fixed != wd["w"]:
            wd["w"] = fixed
            changed += 1
    return changed


def apply_to_slug(slug: str, log=print) -> int:
    """Re-apply corrections to an existing slug's words files and takes.json
    (for footage transcribed before a correction was added)."""
    from .ingest import analysis_dir
    out = analysis_dir(slug)
    corrections = load_corrections()
    total = 0
    for wp in sorted(out.glob("*.words.json")):
        words = json.loads(wp.read_text())
        n = correct_words(words, corrections)
        if n:
            wp.write_text(json.dumps(words))
            log("[names] %s: %d words corrected" % (wp.name, n))
        total += n
    takes_path = out / "takes.json"
    if takes_path.exists():
        raw = takes_path.read_text()
        fixed = correct_text(raw, corrections)
        if fixed != raw:
            takes_path.write_text(fixed)
            log("[names] takes.json transcripts corrected")
    log("[names] %d transcript words corrected" % total)
    return total
