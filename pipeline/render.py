"""Phase 7 — render + QC: the generated timeline goes through Resolve's
Deliver page and the output is verified before we call it done.

QC here is mechanical (ffprobe facts vs. the timeline map); the qc-reviewer
agent does the editorial pass on top. A render that finishes but fails QC
raises — a wrong-duration or silent deliverable must never look like success.
"""
from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

from . import resolve_api as ra
from .ingest import work_path, analysis_dir, IngestError

# The DaVinci Resolve project name. `open_project` tries PROJECT_NAME first,
# then LEGACY_PROJECT_NAME, and only creates a project if neither exists — so
# this rename is safe whether or not the project has been renamed inside
# Resolve. The legacy project still holds the shipped HMNS timeline and every
# media link in it; without the fallback, LoadProject would miss it and
# CreateProject would make a second, EMPTY project while the real one sat
# orphaned. Once the project is renamed in Resolve's project manager, the
# legacy name can be dropped.
PROJECT_NAME = "The Ninth Room"
LEGACY_PROJECT_NAME = "Curated Curiosities"
DURATION_TOLERANCE_SEC = 0.75


def project_for_slug(slug: str, fps: float, log=print) -> str:
    """Create a FRESH Resolve project for this produce run.

    Resolve locks a project's timeline frame rate as soon as the project holds
    a timeline, and silently conforms mismatched clips (23.976 footage in a
    29.97 project stretches every clip by 1.25x). A fresh project can never be
    locked to a wrong rate — and, decisive since 2026-08-19, it can never hold
    stale media-pool imports: a reused project accumulated four same-name
    copies of every overlay and shipped an old one's pixels. Older CC_<slug>*
    projects are swept after the new one is current, so the library holds
    exactly one project per slug.
    """
    name = "CC_%s_%s" % (slug, time.strftime("%Y%m%d_%H%M%S"))
    prefix = "CC_%s_" % slug
    fps_str = ("%.3f" % fps).rstrip("0").rstrip(".")
    out = ra.send("project_for_slug", '''
local pm = resolve:GetProjectManager()
local proj = pm:CreateProject(%s)
if not proj then return error("could not create project") end
proj:SetSetting("timelineFrameRate", %s)
local swept = 0
for _, old in ipairs(pm:GetProjectListInCurrentFolder() or {}) do
  if old ~= %s and (old:sub(1, #%s) == %s or old == "CC_" .. %s) then
    if pm:DeleteProject(old) then swept = swept + 1 end
  end
end
return proj:GetName() .. " fps=" .. tostring(proj:GetSetting("timelineFrameRate"))
       .. " swept=" .. swept
''' % (ra.lua_str(name), ra.lua_str(fps_str), ra.lua_str(name),
       ra.lua_str(prefix), ra.lua_str(prefix), ra.lua_str(slug)),
        timeout=300)
    log("[render] project %s" % out)
    return name


def render_timeline(slug: str, fcpxml: Path, log=print) -> Path:
    """Import a generated FCPXML, then render it. Kept for assets Resolve's
    importer links correctly; the DJI/HEVC path uses render_current instead."""
    ra.ensure_bridge()
    ra.open_project(PROJECT_NAME, LEGACY_PROJECT_NAME)
    # Timeline names must be unique per import or Resolve silently numbers
    # them; a timestamp suffix keeps reruns unambiguous.
    tl_name = "%s_%s" % (slug, time.strftime("%H%M%S"))
    info = ra.import_timeline(fcpxml, tl_name)
    log("[render] imported: %s" % info)
    return render_current(slug, tl_name, log=log)


def render_current(slug: str, tl_name: str, log=print) -> Path:
    """Render whatever timeline is currently open in Resolve."""
    deliver = work_path(slug) / "deliverables"
    deliver.mkdir(exist_ok=True)
    job = ra.start_render(deliver, tl_name)
    log("[render] job %s rendering..." % job)
    ra.wait_for_render()

    output = deliver / (tl_name + ".mp4")
    if not output.exists():
        candidates = sorted(deliver.glob("*.mp4"), key=lambda p: p.stat().st_mtime)
        if not candidates:
            raise IngestError("render finished but no mp4 in %s" % deliver)
        output = candidates[-1]
    qc_probe(slug, output, log=log)
    log("[render] ✓ %s" % output)
    return output


def qc_probe(slug: str, output: Path, log=print) -> "dict":
    """Mechanical QC: duration, resolution, audio presence + loudness."""
    tl_map = json.loads((analysis_dir(slug) / "timeline_map.json").read_text())
    proc = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json",
         "-show_streams", "-show_format", str(output)],
        capture_output=True, text=True)
    if proc.returncode != 0:
        raise IngestError("qc: ffprobe failed on %s" % output.name)
    info = json.loads(proc.stdout)
    v = next((s for s in info["streams"] if s["codec_type"] == "video"), None)
    a = next((s for s in info["streams"] if s["codec_type"] == "audio"), None)
    duration = float(info["format"]["duration"])

    problems = []
    if v is None:
        problems.append("no video stream")
    if a is None:
        problems.append("no audio stream")
    if abs(duration - tl_map["duration"]) > DURATION_TOLERANCE_SEC:
        problems.append("duration %.2fs vs planned %.2fs"
                        % (duration, tl_map["duration"]))
    from .timeline import CANVAS
    w, h = CANVAS[tl_map["orientation"]]
    if v is not None and (v["width"], v["height"]) != (w, h):
        problems.append("resolution %sx%s vs planned %dx%d"
                        % (v["width"], v["height"], w, h))

    mean_volume = None
    if a is not None:
        vol = subprocess.run(
            ["ffmpeg", "-i", str(output), "-af", "volumedetect", "-f", "null", "-"],
            capture_output=True, text=True)
        for line in vol.stderr.splitlines():
            if "mean_volume" in line:
                mean_volume = float(line.split("mean_volume:")[1].split("dB")[0])
        if mean_volume is not None and mean_volume < -45.0:
            problems.append("audio nearly silent (mean %.1f dB)" % mean_volume)

    report = {"file": str(output), "duration": duration,
              "mean_volume_db": mean_volume, "problems": problems}
    (work_path(slug) / "deliverables" / "qc.json").write_text(json.dumps(report, indent=2))
    if problems:
        raise IngestError("qc failed for %s:\n  %s" % (output.name, "\n  ".join(problems)))
    log("[qc] duration %.2fs, mean volume %s dB — OK"
        % (duration, mean_volume))
    return report
