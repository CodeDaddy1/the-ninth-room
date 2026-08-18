"""Phase 3 — take analysis: segment speech files into takes, measure them,
and group retakes of the same content.

A "take" is a continuous stretch of speech bounded by silence gaps of
TAKE_SPLIT_GAP_SEC or more. For each take we compute the facts a human editor
would notice in the first second — is it complete, did he flub it, how many
fillers — so the story-designer agent can pick winners by reading
`analysis/takes.json` instead of watching footage.

Grouping: retakes of the same line share their opening words, so we compare
normalized transcripts with difflib and group takes whose similarity clears
GROUP_SIMILARITY. The agent picks ONE take per group (or none).

What breaks if this is wrong: the agent picks between wrongly-split fragments
(mid-sentence cuts) or never sees that two takes are alternatives of the same
line (bad grouping) — the edit plan inherits every mistake made here.
"""
from __future__ import annotations

import difflib
import json
import re
from pathlib import Path

from .ingest import analysis_dir, IngestError

# Silence this long ends a take. Longer than a breath (~0.6s), shorter than
# the deliberate "reset pause" people take between retakes.
TAKE_SPLIT_GAP_SEC = 1.4
# Takes whose normalized transcripts match at least this much are retakes of
# the same content.
GROUP_SIMILARITY = 0.55

FILLER_WORDS = {"um", "uh", "er", "ah", "hmm", "mhm", "uhh", "umm"}
# Spoken evidence the speaker abandoned the take.
RESTART_PATTERNS = (
    "no wait", "wait no", "let me start over", "start over", "start again",
    "let me try that again", "try that again", "take two", "scratch that",
    "hold on", "one more time", "from the top",
)


def _norm_tokens(text: str) -> "list[str]":
    return re.findall(r"[a-z0-9']+", text.lower())


def segment_takes(words: "list[dict]", split_gap: float = TAKE_SPLIT_GAP_SEC) -> "list[list[dict]]":
    """Split a word stream into runs separated by >= split_gap of silence."""
    takes: "list[list[dict]]" = []
    current: "list[dict]" = []
    prev_end = None
    for w in words:
        if prev_end is not None and w["s"] - prev_end >= split_gap:
            if current:
                takes.append(current)
            current = []
        current.append(w)
        prev_end = w["e"]
    if current:
        takes.append(current)
    return takes


def take_metrics(take_words: "list[dict]") -> "dict":
    text = " ".join(w["w"] for w in take_words)
    tokens = _norm_tokens(text)
    fillers = sum(1 for t in tokens if t in FILLER_WORDS)
    lower = " ".join(tokens)
    restart = any(p in lower for p in RESTART_PATTERNS)
    last = take_words[-1]["w"].rstrip()
    complete = last.endswith((".", "!", "?"))
    dur = take_words[-1]["e"] - take_words[0]["s"]
    return {
        "transcript": text,
        "n_words": len(take_words),
        "duration": round(dur, 3),
        "fillers": fillers,
        "restart": restart,
        "complete": complete,
    }


def group_takes(takes: "list[dict]") -> "list[dict]":
    """Group takes by transcript similarity (same content, different attempts).

    Greedy: each take joins the first existing group whose representative it
    matches, else founds a new group. Representative = the group's longest
    transcript so far, so short flubbed fragments still match the full line.
    """
    by_id = {t["id"]: t for t in takes}
    groups: "list[dict]" = []
    for t in takes:
        placed = False
        for g in groups:
            rep = max((by_id[tid]["transcript"] for tid in g["take_ids"]), key=len)
            sim = difflib.SequenceMatcher(
                None, _norm_tokens(rep), _norm_tokens(t["transcript"]), autojunk=False
            ).ratio()
            if sim >= GROUP_SIMILARITY:
                g["take_ids"].append(t["id"])
                placed = True
                break
        if not placed:
            groups.append({"id": "G%02d" % (len(groups) + 1), "take_ids": [t["id"]]})
    return groups


def analyze(slug: str, log=print) -> Path:
    """Read catalog.json, write analysis/takes.json."""
    out = analysis_dir(slug)
    catalog_path = out / "catalog.json"
    if not catalog_path.exists():
        raise IngestError("no catalog.json — run ingest first")
    catalog = json.loads(catalog_path.read_text())

    takes: "list[dict]" = []
    for f in catalog["files"]:
        if f.get("class") != "speech":
            continue
        words = json.loads((out / f["words_file"]).read_text())
        for run in segment_takes(words):
            m = take_metrics(run)
            m.update({
                "id": "T%02d" % (len(takes) + 1),
                "file": f["name"],
                "s": round(run[0]["s"], 3),
                "e": round(run[-1]["e"], 3),
            })
            takes.append(m)
            log("[takes] %s %s %.1f–%.1fs %dw%s%s%s" % (
                m["id"], f["name"], m["s"], m["e"], m["n_words"],
                " RESTART" if m["restart"] else "",
                "" if m["complete"] else " INCOMPLETE",
                (" fillers=%d" % m["fillers"]) if m["fillers"] else ""))

    if not takes:
        raise IngestError("no speech takes found in catalog")

    groups = group_takes(takes)
    for g in groups:
        log("[takes] %s: %s" % (g["id"], ", ".join(g["take_ids"])))

    data = {"slug": slug, "takes": takes, "groups": groups}
    from . import schemas
    errors = schemas.validate_takes(data)
    if errors:
        raise IngestError("takes.json failed validation:\n  " + "\n  ".join(errors))
    path = out / "takes.json"
    path.write_text(json.dumps(data, indent=2))
    log("[takes] wrote %s (%d takes, %d groups)" % (path, len(takes), len(groups)))
    return path
