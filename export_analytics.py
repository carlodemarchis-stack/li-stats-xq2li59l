#!/usr/bin/env python3
"""Export a compact dataset for index.html from posts.json (+ comments.json) -> analytics-data.js"""
import json, re, os
d = json.load(open('posts.json', encoding='utf-8'))
cd = json.load(open('comments.json', encoding='utf-8')) if os.path.exists('comments.json') else {'comments': [], 'captures': [], 'captured_at': None}
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
        'pa': ({k: p['post_analytics'].get(k) for k in ('video_views','watch_time_s','avg_watch_s','saves','sends','fetched')} if p.get('post_analytics') else None),
        'hist': [[h['captured'], h['impressions'], h['reactions'], h['comments'], h['reposts']] for h in p.get('history', [])],
        'quoted': (p['quoted_post'] or {}).get('author'),
    })
# ---- comments: one compact row each; sponsor names found in the comment, the commented
# post's snippet or its author, so the sponsor pages can carry the matching comments
SPONSOR_RE = {'Dolby OptiView': re.compile(r'Dolby'), 'Cleeng': re.compile(r'Cleeng'), 'Mercury Intermedia': re.compile(r'Mercury|Quicksilver')}
cout = []
for c in cd['comments']:
    hay = ' '.join([c['text'] or '', c['post_text'] or '', c['post_author'] or ''])
    cout.append({
        'i': c['idx'], 'id': c['comment_id'], 'url': c['comment_url'], 'ts': c['commented_at_utc'], 'date': c['commented_date'],
        'text': c['text'], 'chars': c['text_chars'], 'age': c['age_label'], 'edited': c['edited'],
        'imp': c['impressions'], 'rx': c['reactions'],
        'author': c['post_author'], 'atype': c['post_author_type'], 'aurl': c['post_author_url'], 'mine': c['post_is_mine'],
        'pid': c['post_activity_id'], 'purl': c['post_url'], 'pdate': c['post_posted_date'], 'ptext': (c['post_text'] or '')[:300],
        'prx': c['post_reactions'], 'pcm': c['post_comments'], 'prp': c['post_reposts'],
        'mentions': [[m['name'], m['type']] for m in c['mentions']],
        'sponsors': [name for name, pat in SPONSOR_RE.items() if pat.search(hay)],
        'hist': [[h['captured'], h['impressions'], h['reactions']] for h in c.get('history', [])],
    })
ccaps = cd.get('captures', [])
def bundle(posts, comments):
    return 'window.LI_DATA = ' + json.dumps({'captured': d['captured_at'], 'captures': d.get('captures', [d['captured_at']]), 'posts': posts,
                                            'comments_captured': cd.get('captured_at'), 'comments_captures': ccaps, 'comments': comments}, ensure_ascii=False) + ';\n'
js = bundle(out, cout)
open('analytics-data.js', 'w', encoding='utf-8').write(js)
print(len(out), 'posts +', len(cout), 'comments ->', 'analytics-data.js', len(js)//1024, 'KB')

# ---- sponsor pages: same dashboard, data limited to posts (and comments) that mention the sponsor
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
        csub = [dict(c, sponsors=[S]) for c in cout if S in c['sponsors']]
        open(f"data-{pg['slug']}.js", 'w', encoding='utf-8').write(bundle(sub, csub))
        cfg = {'sponsor': S, 'title': pg['title'], 'intro': pg.get('intro', ''), 'data': f"data-{pg['slug']}.js"}
        html = tpl.replace('<title>LinkedIn Analytics</title>', f"<title>{pg['title']}</title>\n<script>window.LI_PAGE = {json.dumps(cfg, ensure_ascii=False)};</script>", 1)
        assert 'window.LI_PAGE' in html
        open(f"{pg['slug']}.html", 'w', encoding='utf-8').write(html)
        print(f"{len(sub):4} posts, {len(csub)} comments -> {pg['slug']}.html + data-{pg['slug']}.js")
