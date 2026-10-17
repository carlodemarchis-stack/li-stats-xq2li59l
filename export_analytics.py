#!/usr/bin/env python3
"""Export a compact dataset for analytics.html from posts.json -> analytics-data.js"""
import json, re
d = json.load(open('posts.json', encoding='utf-8'))
out = []
for p in d['posts']:
    text = p['text'] or ''
    first = next((l.strip() for l in text.split('\n') if l.strip()), '')
    art = next((a for a in p['attachments'] if a['type'] == 'article'), None)
    title = (art['title'] if art else first)[:140]
    out.append({
        'i': p['idx'], 'id': p.get('activity_id'), 'url': p.get('post_url'),
        'ts': p.get('posted_at_utc'), 'date': p['posted_date'], 'approx': p['date_is_approx'],
        'kind': p['kind'], 'author': p['author'], 'with': p['posted_with'],
        'title': title, 'snippet': first[:160], 'chars': p['text_chars'],
        'imp': p['impressions'], 'rx': p['reactions'], 'cm': p['comments'], 'rp': p['reposts'],
        'boosted': p['was_boosted'], 'article': p['has_article'], 'edited': p['edited'],
        'attachments': [a['type'] for a in p['attachments']],
        'mentions': [[m['name'], m['type']] for m in p['mentions']],
        'tags': p['hashtags'], 'series': p['series'], 'disc': p['disclosures'],
        'sponsors': p.get('sponsors', []), 'subject': p.get('sponsor_subject', []),
        'media': p.get('media_type'), 'images': p.get('image_count', 0),
        'hist': [[h['captured'], h['impressions'], h['reactions'], h['comments'], h['reposts']] for h in p.get('history', [])],
        'quoted': (p['quoted_post'] or {}).get('author'),
    })
js = 'window.LI_DATA = ' + json.dumps({'captured': d['captured_at'], 'captures': d.get('captures', [d['captured_at']]), 'posts': out}, ensure_ascii=False) + ';\n'
open('analytics-data.js', 'w', encoding='utf-8').write(js)
print(len(out), 'posts ->', 'analytics-data.js', len(js)//1024, 'KB')
