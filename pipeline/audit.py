"""Splice audit: no whisper word may straddle a segment boundary.

Born from the second HMNS QC review: three splices clipped words mid-syllable
("ecologi-", "terrib-", a doubled "so much"), and every one was findable
without listening — a word whose span crosses a segment's in or out point
will be audibly cut. This check runs over the computed timeline map, so it
sees the REAL boundaries (word-snapped trims, silence cuts, explicit cuts)
rather than the plan's nominal ones.

Run before every build: `/usr/bin/python3 -m pipeline.cli audit <slug>`.

A flagged boundary is not always wrong — whisper stretches some words far
past their audible end (e.g. 'fatalities.' held 1.8s), so a crossing near a
word's tail may be inaudible. The report includes how far into the word the
cut lands; anything past ~35% of the word's span deserves a fix.

What breaks if this is skipped: exactly what got the last cut a FAIL.
"""
from __future__ import annotations

import json

from .ingest import analysis_dir


def audit_splices(slug: str, log=print) -> "list[dict]":
    out = analysis_dir(slug)
    tl = json.loads((out / "timeline_map.json").read_text())
    catalog = json.loads((out / "catalog.json").read_text())
    by_name = {f["name"]: f for f in catalog["files"]}
    wcache: "dict[str, list]" = {}

    def words_for(fname: str) -> "list[dict]":
        if fname not in wcache:
            wf = by_name[fname].get("words_file")
            wcache[fname] = (json.loads((out / wf).read_text())
                             if wf and (out / wf).exists() else [])
        return wcache[fname]

    problems = []
    for beat in tl["beats"]:
        words = words_for(beat["file"])
        n = len(beat["segments"])
        for j, seg in enumerate(beat["segments"]):
            for kind, t, edge_ok in (("in", seg["src_s"], j == 0),
                                     ("out", seg["src_e"], j == n - 1)):
                for w in words:
                    if w["s"] < t < w["e"]:
                        frac = (t - w["s"]) / max(w["e"] - w["s"], 0.001)
                        # An out-point deep into a word is usually fine
                        # (whisper stretches tails); early crossings clip.
                        severe = frac < 0.65 if kind == "out" else frac > 0.35
                        problems.append({
                            "beat": beat["id"], "segment": j, "edge": kind,
                            "t": round(t, 3), "word": w["w"],
                            "word_span": (w["s"], w["e"]),
                            "frac": round(frac, 2), "severe": severe,
                        })
    severe = [p for p in problems if p["severe"]]
    for p in problems:
        log("[audit] %-6s seg%d %-3s %8.2fs cuts %r at %d%%%s"
            % (p["beat"], p["segment"], p["edge"], p["t"], p["word"],
               p["frac"] * 100, "  <-- SEVERE" if p["severe"] else ""))
    log("[audit] %d boundary crossings, %d severe" % (len(problems), len(severe)))
    return problems
