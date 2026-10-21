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
        'title': title, 'snippet': first[:160], 'chars': p['text_chars'], 'text': text,
        'qtext': ((p['quoted_post'] or {}).get('text') or '')[:600],
        'imp': p['impressions'], 'rx': p['reactions'], 'cm': p['comments'], 'rp': p['reposts'],
        'boosted': p['was_boosted'], 'article': p['has_article'], 'edited': p['edited'],
        'attachments': [a['type'] for a in p['attachments']],
        'mentions': [[m['name'], m['type']] for m in p['mentions']],
        'tags': p['hashtags'], 'series': p['series'], 'disc': p['disclosures'],
        'sponsors': p.get('sponsors', []), 'subject': p.get('sponsor_subject', []),
        'media': p.get('media_type'), 'images': p.get('image_count', 0),
        'links': len(p.get('external_links', [])),
        'hist': [[h['captured'], h['impressions'], h['reactions'], h['comments'], h['reposts']] for h in p.get('history', [])],
        'quoted': (p['quoted_post'] or {}).get('author'),
    })
js = 'window.LI_DATA = ' + json.dumps({'captured': d['captured_at'], 'captures': d.get('captures', [d['captured_at']]), 'posts': out}, ensure_ascii=False) + ';\n'
open('analytics-data.js', 'w', encoding='utf-8').write(js)
print(len(out), 'posts ->', 'analytics-data.js', len(js)//1024, 'KB')

# ---- sponsor pages: same dashboard, data limited to posts that mention the sponsor
import os
if os.path.exists('pages.json'):
    tpl = open('index.html', encoding='utf-8').read()
    for pg in json.load(open('pages.json', encoding='utf-8')):
        S = pg['sponsor']
        sub = []
        for p in out:
            if not any(x['name'] == S for x in p['sponsors']): continue
            q = dict(p)   # keep only this sponsor's flags in the shared file
            q['sponsors'] = [x for x in p['sponsors'] if x['name'] == S]
            q['subject'] = [s for s in p['subject'] if s == S]
            q['disc'] = [s for s in p['disc'] if s == S]
            sub.append(q)
        data = 'window.LI_DATA = ' + json.dumps({'captured': d['captured_at'], 'captures': d.get('captures', [d['captured_at']]), 'posts': sub}, ensure_ascii=False) + ';\n'
        open(f"data-{pg['slug']}.js", 'w', encoding='utf-8').write(data)
        cfg = {'sponsor': S, 'title': pg['title'], 'intro': pg.get('intro', ''), 'data': f"data-{pg['slug']}.js"}
        html = tpl.replace('<title>LinkedIn Analytics</title>', f"<title>{pg['title']}</title>\n<script>window.LI_PAGE = {json.dumps(cfg, ensure_ascii=False)};</script>", 1)
        assert 'window.LI_PAGE' in html
        open(f"{pg['slug']}.html", 'w', encoding='utf-8').write(html)
        print(f"{len(sub):4} posts -> {pg['slug']}.html + data-{pg['slug']}.js")
