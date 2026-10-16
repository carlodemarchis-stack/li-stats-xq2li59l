#!/usr/bin/env python3
"""Merge every capture in captures/*.json into posts.json and posts.sqlite.

Posts are keyed by activity_id (plain reposts, which have none, by a hash of
author + text). The record comes from the latest capture that contains the
post, so counts are the freshest seen; every capture's counts are kept in
`history` so reach can be tracked over time.
"""
import glob, hashlib, json, os, sqlite3

HERE = os.path.dirname(os.path.abspath(__file__))


def key(p):
    if p.get('activity_id'):
        return str(p['activity_id'])
    h = hashlib.sha1(((p.get('author') or '') + '|' + (p.get('text') or '')[:300]).encode()).hexdigest()[:16]
    return 'x:' + h


def main():
    files = sorted(glob.glob(os.path.join(HERE, 'captures', '*.json')))
    if not files:
        raise SystemExit('no captures/*.json found')
    merged = {}
    for f in files:
        cap = json.load(open(f, encoding='utf-8'))
        day = cap['captured_at']
        for p in cap['posts']:
            k = key(p)
            snap = {'captured': day, 'impressions': p.get('impressions'), 'reactions': p['reactions'],
                    'comments': p['comments'], 'reposts': p['reposts']}
            if k in merged:
                old = merged[k]
                p['first_captured'] = old['first_captured']
                p['history'] = old['history'] + [snap]
                if old.get('date_is_approx') is False and p.get('date_is_approx'):
                    p['posted_date'], p['date_is_approx'] = old['posted_date'], False
            else:
                p['first_captured'] = day
                p['history'] = [snap]
            p['last_captured'] = day
            p['key'] = k
            merged[k] = p
    recs = sorted(merged.values(), key=lambda r: (r.get('posted_at_utc') or r['posted_date'] or ''), reverse=True)
    for i, r in enumerate(recs):
        r['idx'] = i

    with open(os.path.join(HERE, 'posts.json'), 'w', encoding='utf-8') as f:
        json.dump({'captures': [os.path.basename(x)[:-5] for x in files], 'captured_at': recs and max(r['last_captured'] for r in recs),
                   'count': len(recs), 'posts': recs}, f, ensure_ascii=False, indent=1)

    db = os.path.join(HERE, 'posts.sqlite')
    if os.path.exists(db): os.remove(db)
    con = sqlite3.connect(db)
    con.executescript('''
    CREATE TABLE posts(
      idx INTEGER PRIMARY KEY, key TEXT, activity_id INTEGER, activity_urn TEXT, content_urn TEXT,
      post_url TEXT, posted_at_utc TEXT, posted_date TEXT, date_is_approx INTEGER,
      age_label TEXT, edited INTEGER, kind TEXT, author TEXT, posted_with TEXT,
      text TEXT, text_chars INTEGER, reactions INTEGER, comments INTEGER, reposts INTEGER,
      impressions INTEGER, boost_label TEXT, was_boosted INTEGER, has_article INTEGER,
      quoted_author TEXT, quoted_text TEXT, quoted_url TEXT, first_captured TEXT, last_captured TEXT);
    CREATE TABLE history(post_idx INTEGER, captured TEXT, impressions INTEGER, reactions INTEGER, comments INTEGER, reposts INTEGER);
    CREATE TABLE mentions(post_idx INTEGER, name TEXT, type TEXT, url TEXT);
    CREATE TABLE hashtags(post_idx INTEGER, tag TEXT);
    CREATE TABLE attachments(post_idx INTEGER, type TEXT, title TEXT, url TEXT, domain TEXT, pages INTEGER);
    CREATE TABLE external_links(post_idx INTEGER, text TEXT, url TEXT);
    CREATE TABLE series(post_idx INTEGER, series TEXT);
    CREATE TABLE disclosures(post_idx INTEGER, name TEXT);
    ''')
    for r in recs:
        q = r['quoted_post'] or {}
        con.execute('INSERT INTO posts VALUES (' + ','.join('?'*28) + ')', (
            r['idx'], r['key'], r.get('activity_id'), r.get('activity_urn'), r.get('content_urn'),
            r.get('post_url'), r.get('posted_at_utc'), r.get('posted_date'), int(r['date_is_approx']),
            r['age_label'], int(r['edited']), r['kind'], r['author'], r['posted_with'],
            r['text'], r['text_chars'], r['reactions'], r['comments'], r['reposts'],
            r['impressions'], r['boost_label'], int(r['was_boosted']), int(r['has_article']),
            q.get('author'), q.get('text'), q.get('url'), r['first_captured'], r['last_captured']))
        con.executemany('INSERT INTO history VALUES (?,?,?,?,?,?)',
                        [(r['idx'], h['captured'], h['impressions'], h['reactions'], h['comments'], h['reposts']) for h in r['history']])
        con.executemany('INSERT INTO mentions VALUES (?,?,?,?)',
                        [(r['idx'], m['name'], m['type'], m['url']) for m in r['mentions']])
        con.executemany('INSERT INTO hashtags VALUES (?,?)', [(r['idx'], h) for h in r['hashtags']])
        con.executemany('INSERT INTO attachments VALUES (?,?,?,?,?,?)',
                        [(r['idx'], a['type'], a.get('title'), a.get('url'), a.get('domain'), a.get('pages'))
                         for a in r['attachments']])
        con.executemany('INSERT INTO external_links VALUES (?,?,?)',
                        [(r['idx'], e['text'], e['url']) for e in r['external_links']])
        con.executemany('INSERT INTO series VALUES (?,?)', [(r['idx'], s) for s in r['series']])
        con.executemany('INSERT INTO disclosures VALUES (?,?)', [(r['idx'], d) for d in r['disclosures']])
    con.commit(); con.close()
    print(f'{len(recs)} posts from {len(files)} capture(s) -> posts.json, posts.sqlite')


if __name__ == '__main__':
    main()
