#!/usr/bin/env python3
"""Parse a LinkedIn "Comments" activity page (saved by the capture extension from
https://www.linkedin.com/in/carlodemarchis/recent-activity/comments/) into one
record per comment of mine.

Usage:
    python3 parse_comments.py raw/comments-page-2026-10-27.html.gz
Writes captures-comments/<date>.json (one capture); build_store.py merges all
captures into comments.json and the `comments` tables of posts.sqlite.

Each card on the page is the commented post (author, text, counts) followed by
the comment thread: my comment, with the one it answers and my further replies
when there are any (text, age, reactions, impressions each). Every comment block
is a div id="replaceableComment_urn:li:comment:(activity:<post>,<comment>)" (or
(ugcPost:<post>,<comment>) for video, document and some image posts); both ids
encode their time as id >> 22 ms since the epoch, so the dates are exact.
"""
import json, re, sys, datetime, os, urllib.parse
from bs4 import BeautifulSoup
from parse_linkedin import ME, load_html, text_of, link_type, parse_age, author_of

URN_RE = re.compile(r'urn:li:comment:\((activity|ugcPost):(\d+),(\d+)\)')
REACT_RE = re.compile(r'(\d[\d,]*)\s+reactions?\b', re.I)
IMPR_RE = re.compile(r'(\d[\d,]*)\s+impressions?\b', re.I)
CDIV_ID = re.compile(r'^replaceableComment_')


def ts_of(li_id):
    t = datetime.datetime.fromtimestamp((li_id >> 22) / 1000, tz=datetime.timezone.utc)
    return t.isoformat(timespec='seconds'), t.date().isoformat()


def comment_div_of(el):
    """The comment block (div id=replaceableComment_<urn>) an element belongs to, or None
    when it is part of the post itself."""
    return el.find_parent('div', id=CDIV_ID)


def top_boxes(node):
    return [tb for tb in node.select('[data-testid=expandable-text-box]')
            if not any(p.get('data-testid') == 'expandable-text-box' for p in tb.parents)]


def links_in(box):
    mentions, hashtags = [], []
    for a in box.find_all('a'):
        href = a.get('href', '')
        lt = link_type(href)
        txt = a.get_text(' ', strip=True)
        if lt in ('person', 'company', 'showcase', 'school'):
            mentions.append({'name': txt, 'type': lt, 'url': href.split('?')[0]})
        elif lt == 'hashtag':
            hashtags.append(txt.lstrip('#').lower())
    return mentions, hashtags


def parse_post(item):
    """The commented post at the top of a card: author, text snippet, counts, ids."""
    post = {}
    pboxes = [b for b in top_boxes(item) if comment_div_of(b) is None]
    pbox = pboxes[0] if pboxes else None
    if pbox is not None:
        name, url, posted_with, age, edited = author_of(pbox, item)
        post['post_text'] = text_of(pbox)[:400]
    else:
        # a post with no text (image / video only): the author is the first profile link
        name = url = None
        for a in item.find_all('a'):
            if comment_div_of(a) is not None: break
            al = a.get('aria-label') or ''
            if al.startswith('View company: '): name, url = al[len('View company: '):], a.get('href'); break
            if al.startswith('View ') and al.endswith(' profile'): name, url = al[5:-len(' profile')].rstrip('’\'s'), a.get('href'); break
        post['post_text'] = ''
    if name and '’' in name: name = name.split('’')[0]
    u = url or ''
    post['post_author'], post['post_author_url'] = name, u.split('?')[0] or None
    lt = link_type(u) if u else None
    post['post_author_type'] = lt if lt in ('person', 'company', 'showcase', 'school') else ('person' if name else None)
    post['post_is_mine'] = name == ME or '/in/carlodemarchis' in u

    def count(label_prefix):
        for b in item.find_all('button'):
            if comment_div_of(b) is not None: continue
            if (b.get('aria-label') or '').startswith(label_prefix):
                t = b.get_text('', strip=True).replace(',', '')
                return int(t) if t.isdigit() else 0
        return 0
    post['post_reactions'] = count('Reaction button')
    post['post_comments'] = count('Comment')
    post['post_reposts'] = count('Repost')
    raw = urllib.parse.unquote(str(item))
    m = re.search(r'urn:li:activity:(\d+)', raw)
    post['post_activity_id'] = int(m.group(1)) if m else None
    return post


def parse_comment(cdiv, post):
    """One comment block of mine inside a card."""
    urn = urllib.parse.unquote(cdiv['id'][len('replaceableComment_'):])
    m = URN_RE.match(urn)
    if not m: return None
    kind, container_id, comment_id = m.group(1), int(m.group(2)), int(m.group(3))
    rec = {'comment_id': comment_id, 'comment_urn': urn}
    rec.update(post)
    # the URN names the post as an activity, or as the ugcPost behind it (video, document
    # and some image posts); the activity id is then taken from the card when it has one
    if kind == 'activity':
        rec['post_activity_id'] = container_id
        rec['post_content_urn'] = None
    else:
        rec['post_content_urn'] = f'urn:li:ugcPost:{container_id}'
    pid = rec['post_activity_id']
    rec['post_url'] = (f'https://www.linkedin.com/feed/update/urn:li:activity:{pid}/' if pid
                       else f'https://www.linkedin.com/feed/update/{rec["post_content_urn"]}/')
    rec['comment_url'] = rec['post_url'] + '?commentUrn=' + urllib.parse.quote(urn, safe='')
    rec['commented_at_utc'], rec['commented_date'] = ts_of(comment_id)
    rec['post_posted_at_utc'], rec['post_posted_date'] = ts_of(container_id)

    own = lambda el: comment_div_of(el) is cdiv          # not part of a nested reply block
    boxes = [b for b in top_boxes(cdiv) if own(b)]
    if boxes:
        rec['text'] = text_of(boxes[0])
        rec['mentions'], rec['hashtags'] = links_in(boxes[0])
    else:
        rec['text'] = ''
        rec['mentions'], rec['hashtags'] = [], []
    rec['text_chars'] = len(rec['text'])
    texts = [t.get_text(' ', strip=True) for t in cdiv.find_all(['span', 'p']) if own(t)]
    age, edited = parse_age(texts)
    if not age:                                      # edited comments read "(edited) 3d"
        m = next((re.match(r'\(edited\)\s*(\d+\s*(?:h|d|w|mo|yr))$', t) for t in texts if t.startswith('(edited)')), None)
        if m: age, edited = m.group(1).replace(' ', ''), True
    rec['age_label'] = age
    rec['edited'] = edited or any(re.search(r'\(edited\)|•\s*Edited', t) for t in texts)
    own_text = ' '.join(texts)
    m = REACT_RE.search(own_text)
    rec['reactions'] = int(m.group(1).replace(',', '')) if m else 0
    m = IMPR_RE.search(own_text)
    rec['impressions'] = int(m.group(1).replace(',', '')) if m else None
    rec['on_own_post'] = rec['post_is_mine']
    return rec


def parse_item(item):
    """Every comment of mine in a card. A card is one post plus the comment thread
    LinkedIn shows for it: my comment, sometimes the comment it replies to and my
    further replies. Two of my comments in one thread give two cards, each showing
    the whole thread, so the caller de-duplicates by comment_id."""
    post = parse_post(item)
    out = []
    for cdiv in item.select('div[id^="replaceableComment_"]'):
        a = next((a for a in cdiv.find_all('a', href=True) if comment_div_of(a) is cdiv and ('/in/' in a['href'] or '/company/' in a['href'])), None)
        if a is None or '/in/carlodemarchis' not in a['href']:
            continue                                   # someone else's comment in the thread
        rec = parse_comment(cdiv, post)
        if rec: out.append(rec)
    return out


def main(path):
    html = load_html(path)
    soup = BeautifulSoup(html, 'lxml')
    items = soup.select('div[role=listitem][componentkey^=update-card-focus]')
    recs, seen = [], set()
    for it in items:
        for r in parse_item(it):
            if r['comment_id'] in seen: continue      # the same thread shown on another card
            seen.add(r['comment_id'])
            recs.append(r)
    recs.sort(key=lambda r: r['comment_id'], reverse=True)
    for i, r in enumerate(recs): r['idx'] = i

    m = re.search(r'(\d{4}-\d{2}-\d{2})', os.path.basename(path))
    captured = m.group(1) if m else datetime.date.today().isoformat()
    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'captures-comments')
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, captured + '.json')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump({'source': os.path.basename(path), 'captured_at': captured,
                   'count': len(recs), 'comments': recs}, f, ensure_ascii=False, indent=1)
    print(f'{len(recs)} comments ({len(items)} cards) -> {out}')


if __name__ == '__main__':
    main(sys.argv[1])
