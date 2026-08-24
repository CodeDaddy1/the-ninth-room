#!/bin/bash
# Install the engine as a launchd agent: starts at login, restarts if it
# dies — the Studio never sees "engine offline" again (P1, 2026-08-23).
#
#   bash scripts/install-launchd.sh            install + start
#   bash scripts/install-launchd.sh uninstall  stop + remove
#
# Logs: ~/Library/Logs/ninth-room-engine.log
set -euo pipefail

LABEL="com.ninthroom.engine"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
REPO="$(cd "$(dirname "$0")/.." && pwd)"
LOG="$HOME/Library/Logs/ninth-room-engine.log"

if [ "${1:-}" = "uninstall" ]; then
  launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
  rm -f "$PLIST"
  echo "engine launchd agent removed — start it by hand again with:"
  echo "  /usr/bin/python3 -m pipeline.cli editroom"
  exit 0
fi

# a hand-started engine would fight the agent over the port — stop it first
if pgrep -f "pipeline.cli editroom" > /dev/null; then
  echo "stopping the hand-started engine first…"
  pkill -f "pipeline.cli editroom" || true
  sleep 1
fi

mkdir -p "$(dirname "$PLIST")" "$(dirname "$LOG")"
cat > "$PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/bin/python3</string>
    <string>-m</string>
    <string>pipeline.cli</string>
    <string>editroom</string>
  </array>
  <key>WorkingDirectory</key><string>$REPO</string>
  <!-- launchd agents do not inherit the shell PATH; without this the
       engine cannot find ffmpeg and every mechanical job fails -->
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key>
    <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$HOME/.local/bin</string>
  </dict>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>ThrottleInterval</key><integer>5</integer>
  <key>StandardOutPath</key><string>$LOG</string>
  <key>StandardErrorPath</key><string>$LOG</string>
</dict>
</plist>
PLIST

launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
sleep 2
if curl -s -o /dev/null http://127.0.0.1:8765/api/projects; then
  echo "engine is up at http://127.0.0.1:8765 and will restart itself."
  echo "log: $LOG"
else
  echo "agent installed but the engine is not answering yet — check $LOG"
  exit 1
fi
