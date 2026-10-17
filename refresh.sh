#!/bin/zsh
# Refresh the LinkedIn store from a capture of the "All activity" page and publish.
#
#   ./refresh.sh                                   newest ~/Downloads/activity-page-*.html,
#                                                  or the clipboard if there is none
#   ./refresh.sh ~/Downloads/activity-page-2026-11-01.html
#
# Capture: open https://www.linkedin.com/in/carlodemarchis/recent-activity/all/, press
# ⌘⇧L (LinkedIn Activity Capture extension, capture-extension/), pick the date to scroll
# back to, Capture. The page lands in ~/Downloads as activity-page-<today>.html.
# Fallback: scroll down past the last post already captured, Select All + Copy, run with
# no argument and no file in ~/Downloads.
set -e
cd "$(dirname "$0")"
mkdir -p raw

SRC="$1"
if [ -z "$SRC" ]; then
  files=(~/Downloads/activity-page-*.html(Nom))     # newest first
  SRC="${files[1]}"
fi

if [ -n "$SRC" ]; then
  [ -f "$SRC" ] || { echo "No such file: $SRC"; exit 1; }
  DATE=$(basename "$SRC" | grep -oE '[0-9]{4}-[0-9]{2}-[0-9]{2}' | head -1)
  [ -n "$DATE" ] || DATE=$(date +%Y-%m-%d)
  RAW="raw/activity-page-$DATE.html.gz"
  echo "Using $SRC"
  gzip -c "$SRC" > "$RAW"
else
  DATE=$(date +%Y-%m-%d)
  RAW="raw/activity-page-$DATE.html.gz"
  if ! osascript -e 'the clipboard as «class HTML»' 2>/dev/null | sed 's/^«data HTML//; s/»$//' | xxd -r -p | gzip -c > "$RAW"; then
    echo "No activity-page-*.html in ~/Downloads and no HTML on the clipboard. Capture the activity page first."; rm -f "$RAW"; exit 1
  fi
fi

N=$(gzip -dc "$RAW" | grep -o 'post-summary/urn:li:activity' | wc -l | tr -d ' ')
if [ "$N" -eq 0 ]; then
  echo "This does not look like the LinkedIn activity page (no posts found)."; rm -f "$RAW"; exit 1
fi
echo "Capture $DATE: $N posts with analytics"
python3 parse_linkedin.py "$RAW"
python3 build_store.py
python3 export_analytics.py
git add -A
git commit -q -m "Refresh $DATE ($N posts in capture)" || { echo "Nothing changed."; exit 0; }
git push -q
echo "Pushed. The page updates in about a minute."
