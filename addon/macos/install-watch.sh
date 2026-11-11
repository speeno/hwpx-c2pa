#!/bin/zsh
# macOS: Hangul for Mac has no add-in or automation interface, so signing runs
# outside the app. This installs a launchd agent that watches a folder and
# re-signs every .hwpx saved there.
#   ./install-watch.sh ~/Documents/Signed          install and start
#   ./install-watch.sh --remove                    stop and remove
# Signer settings are read from ~/.config/hwpx-c2pa/config.json:
#   {"cert": "/path/chain.pem", "key": "/path/signer.key", "tsa": "http://..."}
set -e
LABEL=io.github.speeno.hwpx-c2pa.watch
PLIST=~/Library/LaunchAgents/$LABEL.plist

if [[ "$1" == "--remove" ]]; then
  launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
  rm -f "$PLIST"; echo "removed"; exit 0
fi
FOLDER="${1:?folder to watch}"; mkdir -p "$FOLDER"; FOLDER="$(cd "$FOLDER" && pwd)"
CLI="$(command -v hwpx-c2pa)" || { echo "hwpx-c2pa not found on PATH"; exit 1; }
mkdir -p ~/Library/LaunchAgents ~/Library/Logs
cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key><array>
    <string>$CLI</string><string>watch</string><string>$FOLDER</string>
  </array>
  <key>RunAtLoad</key><true/><key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>$HOME/Library/Logs/hwpx-c2pa-watch.log</string>
  <key>StandardErrorPath</key><string>$HOME/Library/Logs/hwpx-c2pa-watch.log</string>
</dict></plist>
EOF
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
echo "watching $FOLDER (log: ~/Library/Logs/hwpx-c2pa-watch.log)"
