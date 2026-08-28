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
import subprocess
from pathlib import Path

from .ingest import analysis_dir, IngestError, _write_atomic

# Silence this long ends a take. Longer than a breath (~0.6s), shorter than
# the deliberate "reset pause" people take between retakes.
TAKE_SPLIT_GAP_SEC = 1.4

# THE ONE PLACE A PREFIX IS READ (2026-08-28).
#
# What a take IS was re-derived from its filename at four sites, and two of
# them tested `take_id.startswith("vo_")` — which can never be true, because
# ids are minted "T%02d" below and the prefix lives on `file`. The coverage
# gate therefore claimed "100% covered" on every VO beat, the exact rule a
# VO beat is exempt from, and jobs.py failed the job on any entry: VO-led
# episodes were blocked at a gate whose exemption was unreachable.
#
# So kind is derived ONCE, here, where the file is in hand, and stored on
# the take. `vo` is a teleprompter recording whose picture must never ship;
# `desk` is a real-camera performance where the face IS the shot and none of
# the vo exemptions apply. Everything else is speech filmed on the day.
# See docs/decisions-beat-and-take-kind.md.
TAKE_KIND_PREFIXES = (("vo_", "vo"), ("desk_", "desk"))
DEFAULT_TAKE_KIND = "oncamera"
# For callers that must match FILES on disk rather than takes — the only
# legitimate reason left to care about a prefix.
RECORDED_GLOBS = tuple("%s*" % p for p, _ in TAKE_KIND_PREFIXES)


def kind_of_file(name: str) -> str:
    """What a speech file is, from its name. The only prefix read anywhere."""
    for prefix, kind in TAKE_KIND_PREFIXES:
        if str(name or "").startswith(prefix):
            return kind
    return DEFAULT_TAKE_KIND
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


def span_volume_db(path: str, s: float, e: float) -> "float | None":
    """Mean volume of one take's audio span. Close-mic'd narration sits far
    above background crowd chatter — the strongest cheap separator between a
    real take and transcribed passers-by."""
    proc = subprocess.run(
        ["ffmpeg", "-ss", "%.3f" % s, "-t", "%.3f" % max(e - s, 0.1),
         "-i", path, "-vn", "-af", "volumedetect", "-f", "null", "-"],
        capture_output=True, text=True)
    for line in proc.stderr.splitlines():
        if "mean_volume" in line:
            try:
                return float(line.split("mean_volume:")[1].split("dB")[0])
            except (IndexError, ValueError):
                return None
    return None


FILLER_RATE_MAX = 0.12       # fillers as a share of words
WPM_MAX = 260.0              # the floor under the relative ceiling
WPM_RELATIVE = 1.75          # ...times this episode's own median pace
WPM_MIN_WORDS = 8            # below this, wpm is arithmetic noise
WPM_MIN_S = 1.5
QUIET_BELOW_MEDIAN_DB = 8.0  # quiet is RELATIVE to this episode's own mic


def quiet_floor(takes: "list") -> "float | None":
    """The dB below which a take is quiet FOR THIS EPISODE.

    An absolute floor does not survive contact with real footage. Measured
    on HMNS (2026-08-24): the median take sits at -36 dB because the
    camera mic runs quiet in a big room, and a fixed -40 dB floor flagged
    26% of the shoot as "barely audible" — which is not a defect, it is
    the rig. The floor therefore comes from the episode's own
    distribution.
    """
    vols = [float(t["mean_volume_db"]) for t in takes
            if t.get("mean_volume_db") is not None]
    if len(vols) < 8:
        return None          # too few to know what normal sounds like
    vols.sort()
    median = vols[len(vols) // 2]
    return median - QUIET_BELOW_MEDIAN_DB


def rushed_ceiling(takes: "list") -> float:
    """The wpm above which a line is rushed FOR THIS EPISODE.

    Same reasoning as `quiet_floor`, and the same trap avoided: an
    absolute ceiling is a statement about a presenter, not about a take.
    HMNS measured a median of 153 wpm with p90 at 268, so 260 happened to
    flag a sane 11% — but on a fast talker the same number would flag
    half the shoot. Never falls below WPM_MAX, so a very slow episode
    cannot make ordinary speech look rushed.
    """
    rows = [t for t in takes
            if int(t.get("n_words") or 0) >= WPM_MIN_WORDS
            and float(t.get("duration") or 0) >= WPM_MIN_S]
    if len(rows) < 8:
        return WPM_MAX
    paces = sorted(int(t["n_words"]) / float(t["duration"]) * 60.0
                   for t in rows)
    median = paces[len(paces) // 2]
    return max(WPM_MAX, median * WPM_RELATIVE)


def take_flags(take: "dict", floor: "float | None" = None,
               ceiling: "float | None" = None) -> "list":
    """PURE. Mechanical reasons a take is a poor candidate to QUOTE.

    Every field read here has been computed since the takes stage was
    written and never used as a filter — the story-designer sees all 355
    takes and is trusted to avoid the fumbles by reading them. It usually
    does; "usually" is how a false start reaches a published cut.

    These are FLAGS, not verdicts. A flagged take stays selectable —
    Caleb keeps or kills it on the Takes desk, and only a kill is
    enforced. A restart can be the best line in the episode when the
    restart IS the joke.
    """
    flags = []
    if take.get("restart"):
        flags.append("false start")
    if not take.get("complete", True):
        flags.append("unfinished sentence")
    n = int(take.get("n_words") or 0)
    fillers = int(take.get("fillers") or 0)
    if n and fillers / n > FILLER_RATE_MAX:
        flags.append("%d fillers in %d words" % (fillers, n))
    dur = float(take.get("duration") or 0)
    # wpm is meaningless on a fragment: "Yeah." at 0.02s reads as 3000 wpm
    if n >= WPM_MIN_WORDS and dur >= WPM_MIN_S:
        wpm = n / dur * 60.0
        if wpm > (WPM_MAX if ceiling is None else ceiling):
            flags.append("%.0f wpm — rushed" % wpm)
    vol = take.get("mean_volume_db")
    if floor is not None and vol is not None and float(vol) < floor:
        flags.append("%.0f dB — quiet for this shoot" % float(vol))
    return flags


def superseded_takes(takes: "list", groups: "list") -> "dict":
    """take_id -> the take that supersedes it, within a retake cluster.

    `group_takes` already clusters attempts at the same line. Inside a
    cluster the KEEPER is the last complete take with the most words —
    the one the crew settled on — and everything before it is a discarded
    attempt. This is the flag that matters most in practice: 355 takes
    hide a lot of "let me say that again".

    A cluster of one supersedes nothing. Returns only the losers.
    """
    by_id = {t["id"]: t for t in takes}
    out: "dict" = {}
    for g in groups:
        ids = [i for i in g.get("take_ids", []) if i in by_id]
        if len(ids) < 2:
            continue
        complete = [i for i in ids if by_id[i].get("complete", True)]
        pool = complete or ids
        keeper = max(pool, key=lambda i: (int(by_id[i].get("n_words") or 0),
                                          ids.index(i)))
        for i in ids:
            if i != keeper:
                out[i] = keeper
    return out


def flag_takes(takes: "list", groups: "list" = ()) -> "dict":
    """take_id -> flags, with the episode's own quiet floor and its
    retake clusters applied. One call so no caller has to remember that
    the floor is relative."""
    floor = quiet_floor(takes)
    ceiling = rushed_ceiling(takes)
    sup = superseded_takes(takes, groups or [])
    out = {}
    for t in takes:
        f = take_flags(t, floor, ceiling)
        if t["id"] in sup:
            f = f + ["superseded by %s" % sup[t["id"]]]
        if f:
            out[t["id"]] = f
    return out


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


def take_thumb(path: str, s: float, e: float, dest: Path) -> bool:
    """One frame from INSIDE this take, cached on disk.

    Caleb, 2026-08-26: "All clips in the library should have previews
    regardless of class." Every file already has a thumbnail — the Footage
    desk makes one per file, 371 of them — but a take is a SEGMENT, and on
    this episode 249 of 375 takes share their file with another. One file
    holds sixteen. Reusing the file's thumbnail would have given two thirds
    of the library a picture of a different moment, which is worse than no
    picture: a wrong frame is read as this take's frame.

    Grabbed a beat INTO the take rather than on its first frame, which is
    often mid-blink on the cut from the previous one.
    """
    if dest.exists():
        return True
    at = s + min(0.5, max((e - s) / 3.0, 0.0))
    dest.parent.mkdir(parents=True, exist_ok=True)
    from .broll import _prefer_proxy
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-ss", "%.2f" % at,
         "-i", str(_prefer_proxy(Path(path))), "-frames:v", "1",
         "-vf", "scale=320:-2", str(dest)],
        capture_output=True)
    return dest.exists()


def analyze(slug: str, log=print) -> Path:
    """Read catalog.json, write analysis/takes.json."""
    out = analysis_dir(slug)
    catalog_path = out / "catalog.json"
    if not catalog_path.exists():
        raise IngestError("no catalog.json — run ingest first")
    catalog = json.loads(catalog_path.read_text())
    from .ingest import write_progress
    write_progress(slug, stage="takes", done=0, total=1, pct=None, eta_s=None)

    takes: "list[dict]" = []
    for f in catalog["files"]:
        if f.get("class") != "speech":
            continue
        words = json.loads((out / f["words_file"]).read_text())
        for run in segment_takes(words):
            s = round(run[0]["s"], 3)
            e = round(run[-1]["e"], 3)
            if e <= s:
                # whisper sometimes stamps a word zero-length (seen:
                # "literally." at 29.98-29.98 on a clip's last frame). A
                # spoken word has a real footprint — floor it, clamped to
                # the clip; a sliver that can't fit is dropped.
                e = round(s + 0.24, 3)
                if f.get("duration"):
                    e = min(e, round(f["duration"], 3))
                if e <= s:
                    log("[takes] SKIP zero-length take at %.2fs in %s"
                        % (s, f["name"]))
                    continue
            m = take_metrics(run)
            m.update({
                "id": "T%02d" % (len(takes) + 1),
                "file": f["name"],
                "kind": kind_of_file(f["name"]),
                "s": s,
                "e": e,
            })
            vol = span_volume_db(f["path"], m["s"], m["e"])
            if vol is not None:
                m["mean_volume_db"] = vol
            takes.append(m)
            log("[takes] %s %s %.1f–%.1fs %dw%s%s%s" % (
                m["id"], f["name"], m["s"], m["e"], m["n_words"],
                " RESTART" if m["restart"] else "",
                "" if m["complete"] else " INCOMPLETE",
                (" fillers=%d" % m["fillers"]) if m["fillers"] else ""))

    if not takes:
        raise IngestError("no speech takes found in catalog", code="no_speech")

    # The previews. Cheap next to what has already run — one frame each
    # against whisper's pass over the same audio — and cached, so a
    # re-analyze pays only for takes that are new.
    thumbs_dir = out / "take_thumbs"
    made = 0
    by_file = {f["name"]: f for f in catalog["files"]}
    for t in takes:
        src = by_file.get(t["file"], {}).get("path")
        if not src:
            continue
        if take_thumb(src, t["s"], t["e"], thumbs_dir / (t["id"] + ".jpg")):
            made += 1
    log("[takes] %d of %d takes have a preview" % (made, len(takes)))

    groups = group_takes(takes)
    for g in groups:
        log("[takes] %s: %s" % (g["id"], ", ".join(g["take_ids"])))

    data = {"slug": slug, "takes": takes, "groups": groups}
    from . import schemas
    errors = schemas.validate_takes(data)
    if errors:
        raise IngestError("takes.json failed validation:\n  " + "\n  ".join(errors))
    path = out / "takes.json"
    # Atomic: a half-written takes.json is a parse error for every reader,
    # and this is written at the end of a long job that can be killed
    # (2026-08-27). Same rule as the catalog and the sidecars.
    _write_atomic(path, data)
    log("[takes] wrote %s (%d takes, %d groups)" % (path, len(takes), len(groups)))
    return path
