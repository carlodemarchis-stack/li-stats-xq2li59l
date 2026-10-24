#!/usr/bin/env python3
"""Merge rows printed by fetch_post_analytics.js into post_analytics.json, then rebuild.
Usage: python3 merge_post_analytics.py "id:imp:views:watch:avg:rx:cm:rp:saves:sends;..." [YYYY-MM-DD]
"""
import json, os, sys, datetime, subprocess
raw, fetched = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else datetime.date.today().isoformat())
keys = ['impressions','video_views','watch_time_s','avg_watch_s','reactions','comments','reposts','saves','sends']
here = os.path.dirname(os.path.abspath(__file__)); path = os.path.join(here, 'post_analytics.json')
store = json.load(open(path)) if os.path.exists(path) else {'posts': {}}
n = 0
for row in raw.strip().strip(';').split(';'):
    parts = row.split(':'); aid = parts[0]
    snap = {'fetched': fetched, **{k: (int(v) if v != '' else None) for k, v in zip(keys, parts[1:])}}
    e = store['posts'].setdefault(aid, {'history': []})
    e['history'] = [h for h in e['history'] if h['fetched'] != fetched] + [snap]; e['latest'] = snap; n += 1
store['last_fetched'] = fetched
json.dump(store, open(path, 'w'), indent=1); print(n, 'posts merged into post_analytics.json')
subprocess.run([sys.executable, os.path.join(here, 'build_store.py')], check=True)
subprocess.run([sys.executable, os.path.join(here, 'export_analytics.py')], check=True)
