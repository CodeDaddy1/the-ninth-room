"""Color correction for the Resolve timeline: measure each clip, then grade it.

**Read this before reaching for a log LUT.** The DJI Osmo Pocket 3 names its
files `..._D.MP4` whether or not they are D-Log M, so the suffix proves
nothing. Measure instead. On the HMNS shoot the footage turned out to be a
standard profile shot in a humid, hazy conservatory:

    cave shot   YMIN 122  YLOW 192  YHIGH 605  YMAX 955  SATAVG 24
    dome shot   YMIN 181  YLOW 237  YHIGH 469  YMAX 946  SATAVG 50

Real log would show uniformly low saturation and a much tighter luma range.
Applying Resolve's `DJI D-Gamut/D-Log` transform to it produced neon greens
and clipped highlights — the classic over-correction. So this module does the
honest thing: it measures every clip's own black point, white point and
saturation with ffmpeg, then applies an ASC CDL that puts them where they
belong, per clip. A hazy cave shot and a bright dome shot get different
numbers, which is the whole point.

If a future shoot IS log, tag it: `tag_camera_clips(names, DJI_LOG)` with the
project in managed color. That path is kept below but is off by default.

What breaks if this is wrong: crushed shadows and clipped highlights (slope
too aggressive), or a flat video that looks ungraded (slope too timid). The
caps below exist so one weird measurement cannot wreck a clip.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from . import resolve_api as ra
from .ingest import analysis_dir

DJI_LOG = "DJI D-Gamut/D-Log"     # only for genuinely log footage
REC709 = "Rec.709 Gamma 2.4"

# 10-bit code values (0-1023). Targets leave headroom: we are correcting, not
# crushing — YouTube compression punishes clipped blacks and whites.
TARGET_LOW = 0.055      # normalized black point after the grade
TARGET_HIGH = 0.88      # normalized white point after the grade
SLOPE_RANGE = (0.95, 1.9)
OFFSET_RANGE = (-0.22, 0.06)
SAT_RANGE = (1.0, 1.25)
SAT_REFERENCE = 55.0    # SATAVG a well-saturated Rec.709 frame lands near
SAMPLE_TIMES = (0.25, 0.5, 0.75)   # fractions of the clip to measure


def _signalstats(path: str, at: float) -> "dict":
    proc = subprocess.run(
        ["ffmpeg", "-hide_banner", "-ss", "%.2f" % at, "-i", path,
         "-frames:v", "1", "-vf", "signalstats,metadata=print", "-f", "null", "-"],
        capture_output=True, text=True)
    out = {}
    for line in proc.stderr.splitlines():
        if "lavfi.signalstats." not in line:
            continue
        key, _, val = line.split("lavfi.signalstats.")[1].partition("=")
        try:
            out[key.strip()] = float(val)
        except ValueError:
            pass
    return out


def measure_clip(path: str, duration: float) -> "dict":
    """Average signal statistics across a few frames of one clip."""
    samples = []
    for frac in SAMPLE_TIMES:
        s = _signalstats(path, duration * frac)
        if s.get("YLOW") is not None:
            samples.append(s)
    if not samples:
        return {}
    keys = ("YMIN", "YLOW", "YAVG", "YHIGH", "YMAX", "SATAVG")
    return {k: sum(s.get(k, 0.0) for s in samples) / len(samples) for k in keys}


def compute_cdl(stats: "dict") -> "dict":
    """Turn measurements into an ASC CDL that normalizes the clip.

    Slope stretches the measured range onto the target range, offset places
    the black point, saturation compensates for a dull frame. Everything is
    clamped so a strange measurement degrades to "almost no change" rather
    than to a ruined shot.
    """
    if not stats:
        return {"slope": 1.0, "offset": 0.0, "power": 1.0, "saturation": 1.0}
    low = stats.get("YLOW", 64.0) / 1023.0
    high = stats.get("YHIGH", 940.0) / 1023.0
    span = max(high - low, 0.05)
    slope = (TARGET_HIGH - TARGET_LOW) / span
    slope = max(SLOPE_RANGE[0], min(SLOPE_RANGE[1], slope))
    offset = TARGET_LOW - low * slope
    offset = max(OFFSET_RANGE[0], min(OFFSET_RANGE[1], offset))
    sat_avg = stats.get("SATAVG", SAT_REFERENCE)
    saturation = 1.0 + max(0.0, (SAT_REFERENCE - sat_avg) / SAT_REFERENCE) * 0.35
    saturation = max(SAT_RANGE[0], min(SAT_RANGE[1], saturation))
    # A touch of gamma keeps midtones from flattening once contrast is added.
    power = 1.03 if slope > 1.15 else 1.0
    return {"slope": round(slope, 4), "offset": round(offset, 4),
            "power": power, "saturation": round(saturation, 3)}


def plan_grade(slug: str, files: "list[dict]", log=print) -> "dict":
    """Measure every camera clip once and cache the resulting CDL per file."""
    cache_path = analysis_dir(slug) / "color.json"
    cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}
    changed = False
    for f in files:
        if f["name"] in cache:
            continue
        stats = measure_clip(f["path"], f["duration"])
        cdl = compute_cdl(stats)
        cache[f["name"]] = {"stats": {k: round(v, 1) for k, v in stats.items()},
                            "cdl": cdl}
        changed = True
        log("[color] %s  black %.0f→%.0f  slope %.2f  sat %.2f"
            % (f["name"][-12:], stats.get("YLOW", 0), TARGET_LOW * 1023,
               cdl["slope"], cdl["saturation"]))
    if changed:
        cache_path.write_text(json.dumps(cache, indent=2))
    return cache


def apply_grade(grades: "dict", log=print) -> str:
    """Apply each clip's CDL to its items on V1/V2. Overlay tracks are left
    alone — cards and captions are already brand-exact."""
    entries = ",".join(
        '{n=%s,s=%s,o=%s,p=%s,sat=%s}' % (
            ra.lua_str(name),
            ra.lua_str("%s %s %s" % ((g["cdl"]["slope"],) * 3)),
            ra.lua_str("%s %s %s" % ((g["cdl"]["offset"],) * 3)),
            ra.lua_str("%s %s %s" % ((g["cdl"]["power"],) * 3)),
            ra.lua_str(str(g["cdl"]["saturation"])))
        for name, g in grades.items())
    out = ra.send("apply_cdl", '''
local tl = resolve:GetProjectManager():GetCurrentProject():GetCurrentTimeline()
local byname = {}
for _, e in ipairs({%s}) do byname[e.n] = e end
local graded, skipped = 0, 0
for _, track in ipairs({1, 2}) do
  for _, item in ipairs(tl:GetItemListInTrack("video", track)) do
    local g = byname[item:GetName()]
    if g then
      if item:SetCDL({["NodeIndex"]="1", ["Slope"]=g.s, ["Offset"]=g.o,
                      ["Power"]=g.p, ["Saturation"]=g.sat}) then
        graded = graded + 1
      end
    else
      skipped = skipped + 1
    end
  end
end
return "graded=" .. graded .. " untouched=" .. skipped
''' % entries, timeout=600)
    log("[color] %s" % out)
    return out


def use_standard_color_science(log=print) -> str:
    """Plain DaVinci YRGB — no managed transforms.

    Managed color only helps when the input color space is known and correct;
    with ordinary Rec.709 footage it adds risk (a wrong tag = a wrecked
    image) and buys nothing.
    """
    out = ra.send("std_color", '''
local proj = resolve:GetProjectManager():GetCurrentProject()
proj:SetSetting("colorScienceMode", "davinciYRGB")
return tostring(proj:GetSetting("colorScienceMode"))
''', timeout=300)
    log("[color] science: %s" % out)
    return out


def tag_camera_clips(names: "list[str]", colorspace: str = DJI_LOG, log=print) -> str:
    """Tag clips with an input color space (managed color only). Off by
    default — see the module docstring."""
    lua_names = ",".join(ra.lua_str(n) for n in names)
    out = ra.send("tag_cs", '''
local mp = resolve:GetProjectManager():GetCurrentProject():GetMediaPool()
local want = {}
for _, n in ipairs({%s}) do want[n] = true end
local tagged = 0
local function scan(f)
  for _, c in ipairs(f:GetClipList()) do
    if want[c:GetName()] and c:SetClipProperty("Input Color Space", %s) then
      tagged = tagged + 1
    end
  end
  for _, s in ipairs(f:GetSubFolderList()) do scan(s) end
end
scan(mp:GetRootFolder())
return "tagged=" .. tagged
''' % (lua_names, ra.lua_str(colorspace)), timeout=600)
    log("[color] %s as %s" % (out, colorspace))
    return out
