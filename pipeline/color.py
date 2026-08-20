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
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

from . import resolve_api as ra
from .ingest import analysis_dir

DJI_LOG = "DJI D-Gamut/D-Log"     # only for genuinely log footage
REC709 = "Rec.709 Gamma 2.4"

# --- camera LUT (Caleb, 2026-08-19: "color grade after LUT is applied") ----
#
# brand/grade.json names a creative LUT that every camera clip gets before
# its grade. Resolve's free API cannot literally put a grade node after a
# LUT node (see docs/resolve-findings.md §5), so the pipeline achieves the
# same result mathematically: it measures the LUT's gray response, inverts
# it, and back-solves the CDL so the image AFTER the LUT lands on the same
# protected targets as before. Overlays (cards/captions) never get the LUT.
MASTER_LUT_DIR = Path("/Library/Application Support/Blackmagic Design/DaVinci Resolve/LUT")
GRADE_CONFIG = Path(__file__).resolve().parent.parent / "brand" / "grade.json"
# CDL bounds in LUT mode: the S-curve supplies the contrast, so the CDL's
# job flips from adding punch to taming the input into the curve's sweet
# spot — slopes below 1 and mid-lifting powers become legitimate.
LUT_SLOPE_RANGE = (0.70, 1.45)
LUT_POWER_RANGE = (0.65, 1.15)
LUT_SAT_RANGE = (0.75, 1.18)

_CURVES: "dict[str, np.ndarray]" = {}


def camera_lut() -> "str | None":
    """Relative LUT path from brand/grade.json, or None for no LUT."""
    if not GRADE_CONFIG.exists():
        return None
    lut = json.loads(GRADE_CONFIG.read_text()).get("camera_lut")
    if lut and not (MASTER_LUT_DIR / lut).exists():
        raise RuntimeError("grade.json names %s but %s does not exist"
                           % (lut, MASTER_LUT_DIR / lut))
    return lut or None


def highlight_trim() -> float:
    """How far below standard the highlight targets sit, in post-LUT signal
    (0-1). Caleb, 2026-08-20: "highlights need to be brought down just a
    tad" — a standing brand preference, so it lives in grade.json and every
    grade (produce and the live-timeline pass) solves with it."""
    if not GRADE_CONFIG.exists():
        return 0.0
    return float(json.loads(GRADE_CONFIG.read_text()).get("highlight_trim", 0.0))


def _lut_curve(lut_rel: str) -> "np.ndarray":
    """The LUT's gray-axis response, sampled at 256 points via ffmpeg."""
    if lut_rel in _CURVES:
        return _CURVES[lut_rel]
    with tempfile.TemporaryDirectory() as td:
        ramp = Path(td) / "ramp.png"
        out = Path(td) / "ramp_lut.png"
        r = np.tile(np.arange(256, dtype=np.uint8), (8, 1))
        Image.fromarray(np.stack([r, r, r], axis=-1)).save(ramp)
        proc = subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", str(ramp),
             "-vf", "lut3d='%s'" % (MASTER_LUT_DIR / lut_rel), str(out)],
            capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError("could not sample LUT %s: %s"
                               % (lut_rel, proc.stderr[-200:]))
        arr = np.asarray(Image.open(out).convert("RGB"))[4, :, :]
    curve = arr.astype(np.float64).mean(axis=1) / 255.0
    curve = np.maximum.accumulate(curve)   # enforce monotonic for inversion
    _CURVES[lut_rel] = curve
    return curve


def _lut_inv(lut_rel: str, y: float) -> float:
    """The input value the LUT maps to output y (gray axis)."""
    curve = _lut_curve(lut_rel)
    xs = np.arange(256) / 255.0
    return float(np.interp(y, curve, xs))

# 10-bit code values (0-1023). Targets leave headroom: we are correcting, not
# crushing — YouTube compression punishes clipped blacks and whites.
TARGET_LOW = 0.045      # normalized black point after the grade
TARGET_HIGH = 0.82      # where the 95th percentile would ideally land
# The brightest measured pixel must stay below this after grading. Without
# this ceiling the slope that lifts the 95th percentile also shoves every
# specular highlight past white: measured 0.25% -> 6.9% clipped pixels on the
# HMNS grade, which reads as blown-out leaves and windows.
HIGHLIGHT_CEILING = 0.985
SLOPE_RANGE = (0.95, 1.45)
OFFSET_RANGE = (-0.35, 0.06)
# Below 1.0 lifts midtones. Bounded so a dark clip cannot be gamma-boosted
# into a milky, washed-out image.
POWER_RANGE = (0.80, 1.05)
SAT_RANGE = (1.0, 1.18)
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


def _signalstats_lut(path: str, at: float, lut_rel: str) -> "dict":
    """signalstats measured through the LUT (for post-LUT saturation)."""
    proc = subprocess.run(
        ["ffmpeg", "-hide_banner", "-ss", "%.2f" % at, "-i", path,
         "-frames:v", "1",
         "-vf", "lut3d='%s',signalstats,metadata=print" % (MASTER_LUT_DIR / lut_rel),
         "-f", "null", "-"],
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


def measure_clip(path: str, duration: float, lut_rel: "str | None" = None) -> "dict":
    """Average signal statistics across a few frames of one clip.

    With a LUT, SATAVG_LUT is also measured through it: the correction must
    know how saturated the image is AFTER the look, not before.
    """
    samples, lut_samples = [], []
    for frac in SAMPLE_TIMES:
        s = _signalstats(path, duration * frac)
        if s.get("YLOW") is not None:
            samples.append(s)
        if lut_rel:
            s2 = _signalstats_lut(path, duration * frac, lut_rel)
            if s2.get("SATAVG") is not None:
                lut_samples.append(s2)
    if not samples:
        return {}
    keys = ("YMIN", "YLOW", "YAVG", "YHIGH", "YMAX", "SATAVG")
    stats = {k: sum(s.get(k, 0.0) for s in samples) / len(samples) for k in keys}
    if lut_samples:
        stats["SATAVG_LUT"] = sum(s["SATAVG"] for s in lut_samples) / len(lut_samples)
    return stats


def compute_cdl(stats: "dict", lut_rel: "str | None" = None) -> "dict":
    """Turn measurements into an ASC CDL that normalizes the clip.

    Slope stretches the measured range onto the target range, offset places
    the black point, saturation compensates for a dull frame. Everything is
    clamped so a strange measurement degrades to "almost no change" rather
    than to a ruined shot.

    With a camera LUT the CDL sits BEFORE the LUT (the API allows nothing
    else), so every target is pulled back through the LUT's inverted gray
    response: the CDL aims for the input values that the LUT maps onto the
    standard targets, and the final image lands exactly where a post-LUT
    grade would put it.
    """
    if not stats:
        return {"slope": 1.0, "offset": 0.0, "power": 1.0, "saturation": 1.0}
    # The trim lowers where highlights LAND (post-LUT signal), so it is
    # subtracted before the targets are pulled back through the LUT.
    trim = highlight_trim()
    if lut_rel:
        t_low = _lut_inv(lut_rel, TARGET_LOW)
        t_high = _lut_inv(lut_rel, TARGET_HIGH - trim)
        ceiling = _lut_inv(lut_rel, HIGHLIGHT_CEILING - trim)
        slope_range, power_range = LUT_SLOPE_RANGE, LUT_POWER_RANGE
    else:
        t_low = TARGET_LOW
        t_high = TARGET_HIGH - trim
        ceiling = HIGHLIGHT_CEILING - trim
        slope_range, power_range = SLOPE_RANGE, POWER_RANGE
    low = stats.get("YLOW", 64.0) / 1023.0
    high = stats.get("YHIGH", 940.0) / 1023.0
    ymax = max(stats.get("YMAX", 1023.0) / 1023.0, high + 0.01)

    # Two candidate slopes: the one that puts the 95th percentile on target,
    # and the one that keeps the brightest pixel under the ceiling.
    # Always take the gentler — protecting highlights outranks hitting the
    # contrast target, because clipped detail cannot be recovered.
    slope_target = (t_high - t_low) / max(high - low, 0.05)
    slope_ceiling = (ceiling - t_low) / max(ymax - low, 0.05)
    slope = min(slope_target, slope_ceiling)
    slope = max(slope_range[0], min(slope_range[1], slope))
    offset = t_low - low * slope
    offset = max(OFFSET_RANGE[0], min(OFFSET_RANGE[1], offset))

    if lut_rel and stats.get("SATAVG_LUT") is not None:
        # The LUT already boosts saturation; correct what comes OUT of it.
        sat_out = max(stats["SATAVG_LUT"], 1.0)
        saturation = SAT_REFERENCE / sat_out
        saturation = max(LUT_SAT_RANGE[0], min(LUT_SAT_RANGE[1], saturation))
    else:
        sat_avg = stats.get("SATAVG", SAT_REFERENCE)
        saturation = 1.0 + max(0.0, (SAT_REFERENCE - sat_avg) / SAT_REFERENCE) * 0.35
        saturation = max(SAT_RANGE[0], min(SAT_RANGE[1], saturation))

    # Dropping the black point on a hazy shot also drags the midtones down —
    # the image ends up correctly contrasty but too dark. Gamma pulls the
    # midtones back toward their target brightness; because CDL applies
    # power last, it lifts mids hard, blacks a little, and highlights almost
    # not at all, which is exactly the shape we want here. In LUT mode the
    # mid target is the input value the LUT maps back to the clip's own
    # average, so overall brightness survives the S-curve.
    yavg = stats.get("YAVG", 0.0) / 1023.0
    mid_target = _lut_inv(lut_rel, yavg) if lut_rel else yavg
    mid_after = yavg * slope + offset
    power = 1.0
    if 0.02 < mid_after < 0.99 and 0.02 < mid_target < 0.99:
        import math
        power = math.log(mid_target) / math.log(mid_after)
        power = max(power_range[0], min(power_range[1], power))
    return {"slope": round(slope, 4), "offset": round(offset, 4),
            "power": round(power, 4), "saturation": round(saturation, 3)}


def plan_grade(slug: str, files: "list[dict]", log=print) -> "dict":
    """Measure every camera clip once and cache the resulting CDL per file.

    The cache is keyed by the active camera LUT — changing brand/grade.json
    invalidates every cached grade, because the whole CDL is solved through
    the LUT's response curve.
    """
    lut = camera_lut()
    trim = highlight_trim()
    if lut:
        log("[color] camera LUT: %s (grade solved through it)" % lut)
    if trim:
        log("[color] highlight trim: -%.3f" % trim)
    cache_path = analysis_dir(slug) / "color.json"
    cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}
    changed = False
    for f in files:
        entry = cache.get(f["name"])
        if entry and entry.get("lut") == lut and entry.get("trim", 0.0) == trim:
            continue
        if entry and entry.get("lut") == lut:
            # same LUT, new trim: the measurement still holds — only the
            # CDL solve changes
            stats = entry["stats"]
        else:
            stats = measure_clip(f["path"], f["duration"], lut_rel=lut)
        cdl = compute_cdl(stats, lut_rel=lut)
        cache[f["name"]] = {"stats": {k: round(v, 1) for k, v in stats.items()},
                            "cdl": cdl, "lut": lut, "trim": trim}
        changed = True
        log("[color] %s  slope %.2f  offset %+.2f  pow %.2f  sat %.2f"
            % (f["name"][-12:], cdl["slope"], cdl["offset"], cdl["power"],
               cdl["saturation"]))
    if changed:
        cache_path.write_text(json.dumps(cache, indent=2))
    return cache


def apply_grade(grades: "dict", log=print) -> str:
    """Apply the camera LUT (if configured) + each clip's CDL to its items on
    V1/V2. Overlay tracks are left alone — cards and captions are already
    brand-exact and must never inherit the footage look."""
    lut = camera_lut()
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
local lut = %s
local byname = {}
for _, e in ipairs({%s}) do byname[e.n] = e end
local graded, lutted, skipped = 0, 0, 0
for _, track in ipairs({1, 2}) do
  for _, item in ipairs(tl:GetItemListInTrack("video", track)) do
    local g = byname[item:GetName()]
    if g then
      if lut ~= "" and item:SetLUT(1, lut) then lutted = lutted + 1 end
      if item:SetCDL({["NodeIndex"]="1", ["Slope"]=g.s, ["Offset"]=g.o,
                      ["Power"]=g.p, ["Saturation"]=g.sat}) then
        graded = graded + 1
      end
    else
      skipped = skipped + 1
    end
  end
end
return "graded=" .. graded .. " lut=" .. lutted .. " untouched=" .. skipped
''' % (ra.lua_str(lut or ""), entries), timeout=600)
    log("[color] %s" % out)
    if lut:
        want = out.split("graded=")[-1].split(" ")[0]
        got = out.split("lut=")[-1].split(" ")[0]
        if want != got:
            raise RuntimeError("camera LUT applied to %s of %s graded clips"
                               % (got, want))
    return out


def grade_live_timeline(slug: str, log=print) -> str:
    """Grade whatever timeline is CURRENTLY OPEN in Resolve, uniformly.

    Unlike apply_grade (which matches the auto-built timeline's clips by
    name on V1/V2), this walks EVERY video track of the live timeline —
    including clips Caleb placed by hand — and grades each item from its
    actual media file. Overlays (anything under this slug's graphics/,
    captions/, or exports/) are skipped: they are brand-exact and never
    take the footage look. Every footage file is measured once (cached in
    analysis/color.json) and solved through the camera LUT with the
    standing highlight trim, so hand-placed clips land on exactly the same
    targets as the pipeline's own.
    """
    from .ingest import work_path
    lut = camera_lut()
    trim = highlight_trim()
    log("[color] LUT: %s  trim: -%.3f" % (lut or "none", trim))
    work = str(work_path(slug).resolve())
    overlay_roots = tuple(work + "/" + d for d in
                          ("graphics", "captions", "exports"))

    listing = ra.send("list_items", '''
local tl = resolve:GetProjectManager():GetCurrentProject():GetCurrentTimeline()
if not tl then return "ERROR: no current timeline" end
local lines = {"TL\\t" .. tl:GetName()}
for t = 1, tl:GetTrackCount("video") do
  local items = tl:GetItemListInTrack("video", t) or {}
  for i, item in ipairs(items) do
    local mp = item:GetMediaPoolItem()
    local path = (mp and mp:GetClipProperty("File Path")) or ""
    lines[#lines+1] = t .. "\\t" .. i .. "\\t" .. path
  end
end
return table.concat(lines, "\\n")
''', timeout=300)
    lines = listing.splitlines()
    tl_name = lines[0].split("\t", 1)[1] if lines else "?"
    log("[color] timeline: %s" % tl_name)

    # one measurement per distinct footage file
    cache_path = analysis_dir(slug) / "color.json"
    cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}
    todo, skipped = [], 0
    for line in lines[1:]:
        t, i, path = line.split("\t", 2)
        if not path or path.startswith(overlay_roots):
            skipped += 1
            continue
        todo.append((int(t), int(i), path))
    changed = False
    for path in sorted({p for _, _, p in todo}):
        name = Path(path).name
        entry = cache.get(name)
        if entry and entry.get("lut") == lut and entry.get("trim", 0.0) == trim:
            continue
        if entry and entry.get("lut") == lut:
            stats = entry["stats"]
        else:
            probe = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "csv=p=0", path], capture_output=True, text=True)
            duration = float(probe.stdout.strip() or 10.0)
            log("[color] measuring %s (%.0fs)" % (name, duration))
            stats = measure_clip(path, duration, lut_rel=lut)
        cdl = compute_cdl(stats, lut_rel=lut)
        cache[name] = {"stats": {k: round(v, 1) for k, v in stats.items()},
                       "cdl": cdl, "lut": lut, "trim": trim}
        changed = True
        log("[color] %s  slope %.2f  offset %+.2f  pow %.2f  sat %.2f"
            % (name[-16:], cdl["slope"], cdl["offset"], cdl["power"],
               cdl["saturation"]))
    if changed:
        cache_path.write_text(json.dumps(cache, indent=2))

    entries = ",".join(
        '{t=%d,i=%d,s=%s,o=%s,p=%s,sat=%s}' % (
            t, i,
            ra.lua_str("%s %s %s" % ((cache[Path(p).name]["cdl"]["slope"],) * 3)),
            ra.lua_str("%s %s %s" % ((cache[Path(p).name]["cdl"]["offset"],) * 3)),
            ra.lua_str("%s %s %s" % ((cache[Path(p).name]["cdl"]["power"],) * 3)),
            ra.lua_str(str(cache[Path(p).name]["cdl"]["saturation"])))
        for t, i, p in todo)
    out = ra.send("grade_live", '''
local tl = resolve:GetProjectManager():GetCurrentProject():GetCurrentTimeline()
local lut = %s
local bytrack = {}
for t = 1, tl:GetTrackCount("video") do
  bytrack[t] = tl:GetItemListInTrack("video", t) or {}
end
local graded, lutted, failed = 0, 0, 0
for _, e in ipairs({%s}) do
  local item = bytrack[e.t] and bytrack[e.t][e.i]
  if item then
    if lut ~= "" and item:SetLUT(1, lut) then lutted = lutted + 1 end
    if item:SetCDL({["NodeIndex"]="1", ["Slope"]=e.s, ["Offset"]=e.o,
                    ["Power"]=e.p, ["Saturation"]=e.sat}) then
      graded = graded + 1
    else
      failed = failed + 1
    end
  else
    failed = failed + 1
  end
end
return "graded=" .. graded .. " lut=" .. lutted .. " failed=" .. failed ..
       " on " .. tl:GetName()
''' % (ra.lua_str(lut or ""), entries), timeout=600)
    log("[color] %s (overlays untouched: %d)" % (out, skipped))
    if "failed=0" not in out:
        raise RuntimeError("some items did not take the grade: %s" % out)
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
