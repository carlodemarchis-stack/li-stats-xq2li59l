#!/bin/zsh
# Refresh the LinkedIn store from a capture of the "All activity" page (posts) or of the
# "Comments" page and publish.
#
#   ./refresh.sh                                   newest ~/Downloads/activity-page-*.html or
#                                                  comments-page-*.html, or the clipboard if none
#   ./refresh.sh ~/Downloads/activity-page-2026-11-01.html
#   ./refresh.sh ~/Downloads/comments-page-2026-11-01.html
#
# Capture: open https://www.linkedin.com/in/carlodemarchis/recent-activity/all/ (posts) or
# .../recent-activity/comments/ (comments), press ⌘⇧L (LinkedIn Activity Capture extension,
# capture-extension/), pick the date to scroll back to, Capture. The page lands in
# ~/Downloads as activity-page-<today>.html or comments-page-<today>.html. The kind is
# detected from the file name, else from the markup (comments pages carry urn:li:comment:).
# Fallback: scroll down past the last post already captured, Select All + Copy, run with
# no argument and no file in ~/Downloads.
set -e
cd "$(dirname "$0")"
mkdir -p raw

SRC="$1"
if [ -z "$SRC" ]; then
  files=(~/Downloads/(activity|comments)-page-*.html(Nom))     # newest first, either kind
  SRC="${files[1]}"
fi

KIND=""
if [ -n "$SRC" ]; then
  [ -f "$SRC" ] || { echo "No such file: $SRC"; exit 1; }
  DATE=$(basename "$SRC" | grep -oE '[0-9]{4}-[0-9]{2}-[0-9]{2}' | head -1)
  [ -n "$DATE" ] || DATE=$(date +%Y-%m-%d)
  case "$(basename "$SRC")" in
    comments-page-*) KIND=comments ;;
    activity-page-*) KIND=posts ;;
  esac
  [ -n "$KIND" ] || { grep -q 'urn:li:comment:' "$SRC" && KIND=comments || KIND=posts; }
  TMP=$(mktemp)
  gzip -c "$SRC" > "$TMP"
  echo "Using $SRC"
else
  DATE=$(date +%Y-%m-%d)
  TMP=$(mktemp)
  if ! osascript -e 'the clipboard as «class HTML»' 2>/dev/null | sed 's/^«data HTML//; s/»$//' | xxd -r -p | gzip -c > "$TMP"; then
    echo "No activity-page-*.html or comments-page-*.html in ~/Downloads and no HTML on the clipboard. Capture the activity page first."; rm -f "$TMP"; exit 1
  fi
  gzip -dc "$TMP" | grep -q 'urn:li:comment:' && KIND=comments || KIND=posts
fi

if [ "$KIND" = comments ]; then
  RAW="raw/comments-page-$DATE.html.gz"
  mv "$TMP" "$RAW"; chmod 644 "$RAW"
  N=$(gzip -dc "$RAW" | grep -oE 'urn:li:comment:\((activity|ugcPost):[0-9]+,[0-9]+\)' | sort -u | wc -l | tr -d ' ')
  if [ "$N" -eq 0 ]; then
    echo "This does not look like the LinkedIn comments page (no comments found)."; rm -f "$RAW"; exit 1
  fi
  echo "Comments capture $DATE: $N comment URNs (threads included)"
  OUT=$(python3 parse_comments.py "$RAW") || exit 1
  echo "$OUT"
  N=$(echo "$OUT" | grep -oE '^[0-9]+' | head -1)
  MSG="Refresh comments $DATE ($N of my comments in capture)"
else
  RAW="raw/activity-page-$DATE.html.gz"
  mv "$TMP" "$RAW"; chmod 644 "$RAW"
  N=$(gzip -dc "$RAW" | grep -o 'post-summary/urn:li:activity' | wc -l | tr -d ' ')
  if [ "$N" -eq 0 ]; then
    echo "This does not look like the LinkedIn activity page (no posts found)."; rm -f "$RAW"; exit 1
  fi
  echo "Capture $DATE: $N posts with analytics"
  python3 parse_linkedin.py "$RAW"
  MSG="Refresh $DATE ($N posts in capture)"
fi
python3 build_store.py
python3 export_analytics.py
git add -A
git commit -q -m "$MSG" || { echo "Nothing changed."; exit 0; }
git push -q
echo "Pushed. The page updates in about a minute."
