#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The assembly craft bar, run over every cut in work/ — the calibration
report Caleb reviews before any gate goes live.

For each project holding an edit_plan.json: the episode's numbers from
cutbar.cut_metrics, then its notes as plain sentences. Nothing here
gates anything; this is the evidence for setting the constants.

Run: /usr/bin/python3 scripts/cut_report.py [slug ...]
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.cutbar import cut_metrics, cut_notes  # noqa: E402

WIDTH = 74


def _load(path):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


def _mmss(seconds):
    s = int(round(seconds or 0))
    return "%d:%02d" % (s // 60, s % 60)


def _pace_row(values):
    if not values or all(v is None for v in values):
        return "none declared"
    return ", ".join("-" if v is None else "%.1f" % v for v in values)


def report(project):
    plan = _load(project / "edit_plan.json")
    takes = _load(project / "analysis" / "takes.json")
    broll = _load(project / "analysis" / "broll.json")
    brief = _load(project / "story_brief.json")
    m = cut_metrics(plan, takes, broll)
    notes = cut_notes(plan, takes, broll, brief)

    print("=" * WIDTH)
    print(project.name)
    print("=" * WIDTH)
    print("  beats %-5d chapters %-3d runtime %-7s build share %.0f%%"
          "   peaks %d"
          % (m["beats"], m["chapters"], _mmss(m["runtime_s"]),
             m["build_share"] * 100, m["peaks"]))
    print("  overall %.1f cuts/min   median shot %.1fs   covers %d   "
          "loops %d"
          % (m["overall_cpm"], m["median_shot_s"], m["covers"], m["loops"]))
    print("  pace declared: %s" % _pace_row(m["pace_declared"]))
    print("  pace realized: %s" % _pace_row(m["pace_realized"]))
    g = m["gear"]
    print("  gear: %d vo beats, %d scene beats (vo mean %.1fs, scene "
          "mean %.1fs)"
          % (g.get("vo_beats", 0), g.get("scene_beats", 0),
             g.get("vo_mean_s", 0.0), g.get("scene_mean_s", 0.0)))
    if not notes:
        print("  BAR: PASS — no notes")
        print()
        return
    print("  BAR: FAIL — %d notes" % len(notes))
    for i, n in enumerate(notes, 1):
        print("  %3d. %s" % (i, n))
    print()


def main(argv):
    root = Path(__file__).resolve().parent.parent / "work"
    wanted = set(argv)
    projects = sorted(p for p in root.iterdir()
                      if p.is_dir() and (p / "edit_plan.json").exists())
    if wanted:
        projects = [p for p in projects if p.name in wanted]
    if not projects:
        print("no project under work/ has an edit_plan.json"
              if not wanted else
              "no edit_plan.json in: %s" % ", ".join(sorted(wanted)))
        return 1
    for p in projects:
        report(p)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
