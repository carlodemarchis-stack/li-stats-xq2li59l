#!/bin/zsh
# Refresh the LinkedIn store from the clipboard and publish.
#
# 1. In the browser open https://www.linkedin.com/in/carlodemarchis/recent-activity/all/
#    scroll down past the last post you already captured, then Select All + Copy.
# 2. Run ./refresh.sh
set -e
cd "$(dirname "$0")"
DATE=$(date +%Y-%m-%d)
RAW="raw/activity-page-$DATE.html.gz"
mkdir -p raw
if ! osascript -e 'the clipboard as «class HTML»' 2>/dev/null | sed 's/^«data HTML//; s/»$//' | xxd -r -p | gzip -c > "$RAW"; then
  echo "Could not read HTML from the clipboard. Copy the activity page first."; rm -f "$RAW"; exit 1
fi
N=$(gzip -dc "$RAW" | grep -o 'post-summary/urn:li:activity' | wc -l | tr -d ' ')
if [ "$N" -eq 0 ]; then
  echo "The clipboard does not look like the LinkedIn activity page (no posts found)."; rm -f "$RAW"; exit 1
fi
echo "Capture $DATE: $N posts with analytics"
python3 parse_linkedin.py "$RAW"
python3 build_store.py
python3 export_analytics.py
git add -A
git commit -q -m "Refresh $DATE ($N posts in capture)" || { echo "Nothing changed."; exit 0; }
git push -q
echo "Pushed. The page updates in about a minute."
