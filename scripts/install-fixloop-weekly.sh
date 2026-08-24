#!/bin/bash
# The weekly fixloop (P10, 2026-08-24): every Monday 09:00 a headless
# session runs the existing /fixloop against both repos, commits GREEN
# fixes to a fixloop/ branch (never main), and notifies with the summary.
#
#   bash scripts/install-fixloop-weekly.sh            install
#   bash scripts/install-fixloop-weekly.sh uninstall  remove
set -euo pipefail

LABEL="com.ninthroom.fixloop"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
REPO="$(cd "$(dirname "$0")/.." && pwd)"
RUNNER="$REPO/scripts/fixloop-weekly.sh"
LOG="$HOME/Library/Logs/ninth-room-fixloop.log"

if [ "${1:-}" = "uninstall" ]; then
  launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
  rm -f "$PLIST"
  echo "weekly fixloop removed"
  exit 0
fi

cat > "$RUNNER" <<'RUN'
#!/bin/bash
set -uo pipefail
for repo in "$HOME/Projects/the-ninth-room" "$HOME/Projects/the-ninth-room-studio"; do
  cd "$repo"
  branch="fixloop/$(date +%Y-%m-%d)"
  git checkout -B "$branch" main
  "$HOME/.local/bin/claude" -p "Run /fixloop on this repository: find and \
fix what the test suite, lint, and type checks catch. Commit each green \
fix on the CURRENT branch (never switch to main) with author \
'CodeDaddy1 <codedaddy1@outlook.com>'. File anything unfixable in \
.claude/reminders.md. Do not push. Do not touch DaVinci Resolve or the \
engine on :8765." --dangerously-skip-permissions
  n=$(git rev-list --count main.."$branch")
  git checkout main
  osascript -e "display notification \"$repo: $n fix(es) on $branch\" with title \"Weekly fixloop\"" || true
done
RUN
chmod +x "$RUNNER"

cat > "$PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array><string>/bin/bash</string><string>$RUNNER</string></array>
  <key>StartCalendarInterval</key>
  <dict><key>Weekday</key><integer>1</integer>
        <key>Hour</key><integer>9</integer>
        <key>Minute</key><integer>0</integer></dict>
  <key>EnvironmentVariables</key>
  <dict><key>PATH</key>
    <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$HOME/.local/bin</string></dict>
  <key>StandardOutPath</key><string>$LOG</string>
  <key>StandardErrorPath</key><string>$LOG</string>
</dict>
</plist>
PLIST

launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
for i in 1 2 3; do
  launchctl bootstrap "gui/$(id -u)" "$PLIST" 2>/dev/null && break
  sleep 1
done
echo "weekly fixloop installed — Mondays 09:00, log: $LOG"
