"""The only door into DaVinci Resolve: the in-app Lua bridge.

Why a bridge at all: the free edition of Resolve refuses every external
scripting transport (verified 2026-08-18 — see docs/resolve-findings.md).
Scripts started from INSIDE Resolve get full API access, so a small Lua script
("Curated Bridge", in Resolve's Workspace > Scripts menu) loops forever,
executing Lua command files we drop into work/_bridge/inbox/ and writing each
result to work/_bridge/outbox/<name>.result as "OK\n<value>" or
"ERROR\n<message>".

This module is the Python side: it installs/starts the bridge, sends commands,
and wraps the handful of Resolve operations the pipeline needs (import a
generated FCPXML timeline, render it, poll progress).

What breaks if this is wrong: the pipeline can still analyze footage and plan
the edit, but nothing ever reaches a Resolve timeline or the render queue.
"""
from __future__ import annotations

import subprocess
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SPOOL = PROJECT_ROOT / "work" / "_bridge"
BRIDGE_SOURCE = Path(__file__).resolve().parent / "bridge" / "Curated Bridge.lua"
BRIDGE_INSTALL_DIR = (
    Path.home()
    / "Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Scripts/Utility"
)
RESOLVE_APP = "DaVinci Resolve"

# Fresh heartbeats are written every bridge loop (~0.3s); anything older than
# this means the bridge died or Resolve quit.
HEARTBEAT_MAX_AGE_SEC = 10.0


class BridgeError(RuntimeError):
    """The bridge is unreachable or a command failed inside Resolve."""


# --- liveness + lifecycle -------------------------------------------------

def alive() -> bool:
    """True when the bridge heartbeat is fresh."""
    f = SPOOL / "bridge.alive"
    if not f.exists():
        return False
    v = f.read_text().strip()
    if v == "stopped":
        return False
    try:
        return time.time() - float(v) < HEARTBEAT_MAX_AGE_SEC
    except ValueError:
        return False


def install_bridge() -> Path:
    """Copy the repo's bridge script into Resolve's user Scripts menu folder.

    Resolve scans this folder at startup only — restart Resolve after a fresh
    install or the menu item won't exist.
    """
    BRIDGE_INSTALL_DIR.mkdir(parents=True, exist_ok=True)
    dest = BRIDGE_INSTALL_DIR / BRIDGE_SOURCE.name
    dest.write_text(BRIDGE_SOURCE.read_text())
    return dest


def resolve_running() -> bool:
    proc = subprocess.run(["pgrep", "-x", "Resolve"], capture_output=True)
    return proc.returncode == 0


def launch_resolve() -> None:
    subprocess.run(["open", "-a", RESOLVE_APP], check=True)


def click_bridge_menu() -> "tuple[bool, str]":
    """Start the bridge by clicking Workspace > Scripts > Curated Bridge.

    Needs Accessibility permission for the host app (System Settings >
    Privacy & Security > Accessibility). Returns (ok, message) instead of
    raising so callers can fall back to asking the human for one click.
    """
    script = (
        'tell application "DaVinci Resolve" to activate\n'
        "delay 2\n"
        'tell application "System Events" to tell process "Resolve" to '
        'click menu item "Curated Bridge" of menu 1 of menu item "Scripts" '
        'of menu 1 of menu bar item "Workspace" of menu bar 1'
    )
    proc = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    if proc.returncode == 0:
        return True, "clicked"
    return False, (proc.stderr or proc.stdout).strip()


def _handle_is_live() -> bool:
    """A fresh heartbeat is not enough: the bridge is a separate fuscript
    process that survives Resolve quitting, and its `resolve` handle then
    points at a dead session (seen 2026-08-19 — heartbeat current, every API
    call failing). Only an actual API round trip proves the handle."""
    try:
        return send("probe", '''
local ok, pm = pcall(function() return resolve:GetProjectManager() end)
if ok and pm then return "ok" end
return error("stale resolve handle")
''', timeout=15) == "ok"
    except BridgeError:
        return False


def ensure_bridge(boot_timeout: float = 180.0) -> None:
    """Make the bridge reachable, launching Resolve and auto-clicking the menu
    when permissions allow. Raises BridgeError with the exact manual step when
    automation isn't possible."""
    if alive():
        if resolve_running() and _handle_is_live():
            return
        stop_bridge()
        deadline = time.time() + 15
        while time.time() < deadline and alive():
            time.sleep(1)
    install_bridge()
    if not resolve_running():
        launch_resolve()
        deadline = time.time() + boot_timeout
        while time.time() < deadline and not resolve_running():
            time.sleep(3)
        time.sleep(20)  # let the UI finish booting before poking menus
    clicked, why = click_bridge_menu()
    deadline = time.time() + 60
    while time.time() < deadline:
        if alive():
            return
        time.sleep(2)
    hint = (
        "Start it manually in Resolve: Workspace > Scripts > Curated Bridge. "
        "For zero-click runs, grant Accessibility permission to this terminal "
        "app (System Settings > Privacy & Security > Accessibility)."
    )
    raise BridgeError(
        "bridge did not come up"
        + ("" if clicked else " (menu automation failed: %s)" % why)
        + ". " + hint
    )


def stop_bridge() -> None:
    (SPOOL / "stop").write_text("")


# --- command transport ----------------------------------------------------

_seq = [int(time.time()) % 100000]


def send(label: str, lua: str, timeout: float = 120.0) -> str:
    """Run a Lua chunk inside Resolve; return its string result.

    The chunk sees the global `resolve` object and must `return` a string.
    Raises BridgeError on ERROR results or timeout.
    """
    if not alive():
        raise BridgeError("bridge is not running — call ensure_bridge() first")
    _seq[0] += 1
    name = "%06d_%s.lua" % (_seq[0], label)
    result = SPOOL / "outbox" / (name + ".result")
    (SPOOL / "inbox").mkdir(parents=True, exist_ok=True)
    (SPOOL / "inbox" / name).write_text(lua)
    deadline = time.time() + timeout
    while time.time() < deadline:
        if result.exists():
            time.sleep(0.2)  # let the bridge finish writing
            text = result.read_text()
            head, _, body = text.partition("\n")
            if head == "OK":
                return body.strip()
            raise BridgeError("%s failed in Resolve: %s" % (label, body.strip()))
        time.sleep(0.3)
    raise BridgeError("timeout after %.0fs waiting for %s" % (timeout, name))


def lua_str(value: str) -> str:
    """Quote a Python string as a Lua string literal."""
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


# --- Resolve operations the pipeline uses ---------------------------------

def open_project(name: str) -> str:
    return send("open_project", '''
local pm = resolve:GetProjectManager()
local proj = pm:LoadProject(%s)
if not proj then proj = pm:CreateProject(%s) end
if not proj then return error("could not load or create project") end
return proj:GetName()
''' % (lua_str(name), lua_str(name)))


def import_timeline(fcpxml_path: Path, timeline_name: str) -> str:
    """Import a generated FCPXML as a new timeline and make it current."""
    return send("import_timeline", '''
local pm = resolve:GetProjectManager()
local proj = pm:GetCurrentProject()
local mp = proj:GetMediaPool()
local tl = mp:ImportTimelineFromFile(%s, {
  ["timelineName"] = %s,
  ["importSourceClips"] = true,
})
if not tl then return error("ImportTimelineFromFile returned nil") end
proj:SetCurrentTimeline(tl)
return tl:GetName() .. "|tracks=" .. tl:GetTrackCount("video")
''' % (lua_str(str(fcpxml_path)), lua_str(timeline_name)), timeout=300)


def start_render(target_dir: Path, custom_name: str) -> str:
    """Queue and start an H.264 mp4 render of the current timeline.

    SelectAllFrames is essential: without it Resolve renders only the current
    in/out range, which on a freshly built timeline is a single frame (seen
    2026-08-18 — a 108s edit rendered as 0.11s).
    """
    return send("start_render", '''
local pm = resolve:GetProjectManager()
local proj = pm:GetCurrentProject()
proj:DeleteAllRenderJobs()
if not proj:SetCurrentRenderFormatAndCodec("mp4", "H264") then
  return error("SetCurrentRenderFormatAndCodec(mp4, H264) failed")
end
proj:SetRenderSettings({
  ["SelectAllFrames"] = true,
  ["TargetDir"] = %s,
  ["CustomName"] = %s,
})
local job = proj:AddRenderJob()
if not job then return error("AddRenderJob failed") end
if not proj:StartRendering(job) then return error("StartRendering failed") end
return job
''' % (lua_str(str(target_dir)), lua_str(custom_name)), timeout=300)


def rendering_in_progress(timeout: float = 300.0) -> bool:
    out = send("render_poll", '''
local pm = resolve:GetProjectManager()
return tostring(pm:GetCurrentProject():IsRenderingInProgress())
''', timeout=timeout)
    return out == "true"


def wait_for_render(timeout: float = 7200.0, poll_sec: float = 10.0) -> None:
    """Poll until the render queue drains.

    A rendering Resolve answers the bridge slowly, so a slow poll means "still
    busy", not "broken" — swallow those and keep waiting until the overall
    deadline. Two consecutive idle answers confirm completion (the queue
    reports idle for a moment between queued jobs).
    """
    deadline = time.time() + timeout
    idle_streak = 0
    while time.time() < deadline:
        try:
            busy = rendering_in_progress()
        except BridgeError:
            time.sleep(poll_sec)
            continue
        idle_streak = 0 if busy else idle_streak + 1
        if idle_streak >= 2:
            return
        time.sleep(poll_sec)
    raise BridgeError("render did not finish within %.0fs" % timeout)
