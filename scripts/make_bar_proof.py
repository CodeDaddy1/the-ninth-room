"""Build a cut that PASSES the craft bar, from hmns's real material.

Calibration had no positive control: every plan on disk is the same
museum episode with no arc, so a threshold could be tuned until hmns
failed less and nothing would show whether it still passed good work.
This is the other side of that comparison.

It is a FIXTURE, not an episode. The beats are chosen to satisfy the
eight checks, not to tell a story — nobody should watch it. What it
proves is that the bar is satisfiable at all, and it gives a
threshold change something to move against in two directions.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
SRC = ROOT / "work" / "hmns" / "analysis"
DST = ROOT / "work" / "bar-proof"

takes = json.loads((SRC / "takes.json").read_text())
broll = json.loads((SRC / "broll.json").read_text())
group_of = {}
for g in takes.get("groups", []):
    for tid in g["take_ids"]:
        group_of[tid] = g["id"]


def shoot_key(t):
    m = re.search(r"DJI_(\d{14})", t["file"])
    return (m.group(1), t["s"]) if m else None


def sentence_ok(t, s, e):
    """The trim must open and close a sentence, or the beat needs
    fragment:true. Same interpolation validate_edit_plan uses."""
    toks = (t.get("transcript") or "").split()
    if not toks:
        return False
    span = max(t["e"] - t["s"], 0.001)
    term = (".", "!", "?", "…", '."', '!"', '?"', ",”", ".”")
    i_end = min(len(toks) - 1, int((e - t["s"]) / span * len(toks)))
    if not toks[max(0, i_end)].rstrip().endswith(term):
        return False
    i_start = min(len(toks) - 1, max(0, int((s - t["s"]) / span * len(toks))))
    if i_start > 0 and not toks[i_start - 1].rstrip().endswith(term):
        return False
    return True


# usable, in shoot order, one per retake group, whole-take trims so the
# sentence check passes on the take's own boundaries
seen_groups = set()
pool = []
for t in sorted((t for t in takes["takes"] if shoot_key(t)), key=shoot_key):
    if not t.get("complete") or t.get("screened_out"):
        continue
    dur = t["e"] - t["s"]
    if not 6.0 <= dur <= 46.0:
        continue
    g = group_of.get(t["id"])
    if g and g in seen_groups:
        continue
    if not sentence_ok(t, t["s"], t["e"]):
        continue
    if g:
        seen_groups.add(g)
    pool.append(t)

print("usable takes in shoot order: %d" % len(pool))

clips = [c for c in broll["clips"] if c.get("duration", 0) >= 3.0]
print("usable b-roll clips: %d" % len(clips))

SIZES = ("wide", "medium", "close", "detail")
clip_i = 0


def take_clip():
    global clip_i
    c = clips[clip_i]
    clip_i += 1
    return c


# ---- the shape -----------------------------------------------------
# CH1 is the intro: hook, open, one build, close.
# CH2..CH5 each: open, build, PEAK, close.
# Covers thin out chapter by chapter so realized pace declines.
CHAPTERS = [
    {"id": "CH1", "title": "We're Here", "promise": "what this place is"},
    {"id": "CH2", "title": "The Butterflies", "promise": "the dome"},
    {"id": "CH3", "title": "The Bones", "promise": "the hall of fossils"},
    {"id": "CH4", "title": "The Gems", "promise": "the vault"},
    {"id": "CH5", "title": "The Ninth Room", "promise": "the thing off the map"},
]
COVERS_PER_BUILD = {"CH1": 3, "CH2": 3, "CH3": 2, "CH4": 1, "CH5": 0}

beats = []
ti = 0


def nxt():
    global ti
    t = pool[ti]
    ti += 1
    return t


def beat(purpose, chapter, n_covers=0, peak=False, **extra):
    t = nxt()
    b = {"id": "PLACEHOLDER", "purpose": purpose, "chapter_id": chapter,
         "take_id": t["id"], "trim": {"s": t["s"], "e": t["e"]},
         "transition_in": "cut"}
    dur = t["e"] - t["s"]
    if peak:
        b["peak"] = True
    else:
        at = 0.6
        for _ in range(n_covers):
            c = take_clip()
            d = min(2.4, max(1.9, c["duration"] - 0.2))
            # nothing in the last fifth, and it must fit
            if at + d > dur * 0.8 - 0.1:
                break
            b.setdefault("broll", []).append({
                "clip_id": c["id"], "at": round(at, 2),
                "duration": round(d, 2),
                "why": "illustrate: %s" % (c["file"].split(".")[0][:28])})
            at += d + 0.8
    b.update(extra)
    return b


# hook — 4 covers previewing CH2..CH5, each foretell, in order.
# It must ALREADY be under MAX_HOOK_SEC: clamping a longer take to 14s
# lands the trim mid-sentence, which validate_edit_plan then refuses.
hi = next(i for i, t in enumerate(pool) if 9.0 <= t["e"] - t["s"] <= 14.5)
h = pool.pop(hi)
hook = {"id": "PLACEHOLDER", "purpose": "hook", "chapter_id": "CH1",
        "take_id": h["id"], "transition_in": "cut",
        "trim": {"s": h["s"], "e": h["e"]},
        "broll": []}
at = 0.4
for n, ch in enumerate(["CH2", "CH3", "CH4", "CH5"]):
    c = take_clip()
    hook["broll"].append({"clip_id": c["id"], "at": round(at, 2),
                          "duration": 1.9,
                          "why": "foretell: %s, what waits in %s"
                                 % (ch, CHAPTERS[n + 1]["title"])})
    at += 2.3
beats.append(hook)

for ch in CHAPTERS:
    cid = ch["id"]
    beats.append(beat("chapter_open", cid, 1))
    if cid == "CH1":
        beats.append(beat("stakes", cid, COVERS_PER_BUILD[cid],
                          opens_loop="L1"))
    else:
        beats.append(beat("build", cid, COVERS_PER_BUILD[cid]))
        # the peak: uncovered, uncarded, 8-45s
        p = beat("build", cid, 0, peak=True)
        while not 8.0 <= (p["trim"]["e"] - p["trim"]["s"]) <= 45.0:
            p = beat("build", cid, 0, peak=True)
        beats.append(p)
    if cid == "CH2":
        beats.append(beat("build", cid, 1, opens_loop="L2"))
    if cid == "CH4":
        beats.append(beat("payoff", cid, 1, pays_loop="L1"))
    if cid == "CH5":
        beats.append(beat("payoff", cid, 0, pays_loop="L2"))
    beats.append(beat("chapter_close", cid, 0))

# every used clip gets a framing tag, alternating so adjacent covers differ
used = {}
for b in beats:
    for i, c in enumerate(b.get("broll", [])):
        used[c["clip_id"]] = SIZES[(len(used) + i) % len(SIZES)]
by_id = {c["id"]: c for c in broll["clips"]}
for cid, f in used.items():
    by_id[cid]["framing"] = f

from pipeline import beat_identity, cutbar

plan = {"slug": "bar-proof", "format": "youtube_long",
        "orientation": "landscape",
        "theme": {"problem": "a museum is too big to see",
                  "promise": "nine rooms, one you cannot find on the map",
                  "payoff": "the ninth room is a door in the fossil hall"},
        "chapters": [{"id": c["id"], "title": c["title"]} for c in CHAPTERS],
        "beats": beats,
        "loops": [{"id": "L1"}, {"id": "L2"}]}

# The engine mints beat ids at promote; a fixture written by hand has to
# do the same or it carries 23 PLACEHOLDERs.
plan = beat_identity.derive_ids(plan)

# DECLARE WHAT THE CUT ACTUALLY DOES.  counts one per beat
# plus two per cover, over the chapter's planned minutes — so the ladder
# is a consequence of thinning the covers, not a number typed on top.
for ch in plan["chapters"]:
    members = [b for b in plan["beats"] if b.get("chapter_id") == ch["id"]]
    minutes = sum(cutbar._beat_dur(b) for b in members) / 60.0
    if minutes > 0:
        ch["pace_cpm"] = round(
            sum(cutbar._beat_changes(b) for b in members) / minutes, 1)

DST.mkdir(parents=True, exist_ok=True)
(DST / "analysis").mkdir(exist_ok=True)
(DST / "analysis" / "takes.json").write_text(json.dumps(takes))
(DST / "analysis" / "broll.json").write_text(json.dumps(broll))
(DST / "story_brief.json").write_text(json.dumps(
    {"target_minutes": 9, "chapters": 5, "vo_share": 0.4,
     "origin": "footage", "delivery": "long"}))
(DST / "edit_plan.json").write_text(json.dumps(plan, indent=2))
print("ladder:", [ (c["id"], c.get("pace_cpm")) for c in plan["chapters"] ])
print("beats: %d  covers: %d  peaks: %d"
      % (len(beats), sum(len(b.get("broll", [])) for b in beats),
         sum(1 for b in beats if b.get("peak"))))
