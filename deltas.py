#!/usr/bin/env python3
"""Compare two captures: what each post gained in impressions, reactions, comments, reposts.

Usage:
    python3 deltas.py                 # last two captures
    python3 deltas.py 2026-10-16 2026-10-17
Only posts present in both captures are compared.
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
d = json.load(open(os.path.join(HERE, 'posts.json'), encoding='utf-8'))
caps = d['captures']
if len(sys.argv) == 3:
    a, b = sys.argv[1], sys.argv[2]
elif len(caps) >= 2:
    a, b = caps[-2], caps[-1]
else:
    raise SystemExit('need at least two captures')

rows = []
for p in d['posts']:
    h = {x['captured']: x for x in p['history']}
    if a in h and b in h and h[a]['impressions'] is not None and h[b]['impressions'] is not None:
        ha, hb = h[a], h[b]
        rows.append((hb['impressions'] - ha['impressions'], hb['reactions'] - ha['reactions'],
                     hb['comments'] - ha['comments'], hb['reposts'] - ha['reposts'], ha, hb, p))
rows.sort(key=lambda r: -r[0])
print(f'{a} -> {b}: {len(rows)} posts in both captures')
print(f"impressions +{sum(r[0] for r in rows):,}  reactions +{sum(r[1] for r in rows)}  "
      f"comments +{sum(r[2] for r in rows)}  reposts +{sum(r[3] for r in rows)}  "
      f"posts that moved: {sum(1 for r in rows if any(r[:4]))}")
print()
print(f"{'date':10} {'impr before':>11} {'after':>7} {'gain':>6} {'rx':>4} {'cm':>4} {'rp':>4}  post")
for di, dr, dc, dp, ha, hb, p in rows:
    if not any((di, dr, dc, dp)): continue
    first = (p['text'] or '').split('\n')[0][:60]
    print(f"{p['posted_date']:10} {ha['impressions']:>11,} {hb['impressions']:>7,} {di:>+6} {dr:>+4} {dc:>+4} {dp:>+4}  {first}")
