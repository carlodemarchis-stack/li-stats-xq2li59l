#!/usr/bin/env python3
"""Parse a LinkedIn "All activity" page (HTML copied from the browser) into
structured post records.

Usage:
    python3 parse_linkedin.py raw/activity-page-2026-10-16.html.gz
Writes captures/<date>.json (one capture); build_store.py merges all captures
into posts.json and posts.sqlite.

The exact publish time comes from the activity URN: the top 41 bits of the
activity id are milliseconds since the Unix epoch (id >> 22).
"""
import gzip, json, re, sqlite3, sys, datetime, os, urllib.parse
from bs4 import BeautifulSoup

ME = "Carlo De Marchis"
AGE_RE = re.compile(r'(?:^|•\s*)(\d+\s*(?:h|d|w|mo|yr))\s*(•\s*Edited)?\s*$')
AGE_UNITS = {'h': 1/24, 'd': 1, 'w': 7, 'mo': 30.4, 'yr': 365}


def load_html(path):
    opener = gzip.open if path.endswith('.gz') else open
    with opener(path, 'rt', encoding='utf-8') as f:
        h = f.read()
    # drop styling noise before parsing: 22MB -> ~5MB
    h = re.sub(r' style="[^"]*"', '', h)
    h = re.sub(r' class="[^"]*"', '', h)
    h = re.sub(r'<svg.*?</svg>', '<svg/>', h, flags=re.S)
    return h


def text_of(node):
    """Text of a node with <br> as newlines and whitespace preserved."""
    for br in node.find_all('br'):
        br.replace_with('\n')
    for b in node.find_all('button'):      # "… more" / "see less" buttons
        b.decompose()
    t = node.get_text('')
    t = re.sub(r'[ \t]+\n', '\n', t)
    t = re.sub(r'\n{3,}', '\n\n', t)
    return t.strip()


def link_type(href):
    if '/in/' in href: return 'person'
    if '/company/' in href: return 'company'
    if '/showcase/' in href: return 'showcase'
    if '/school/' in href: return 'school'
    if 'keywords=%23' in href: return 'hashtag'
    if 'safety/go/' in href or 'lnkd.in' in href: return 'external'
    return 'other'


def decode_external(href):
    if 'safety/go/' in href:
        q = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
        if 'url' in q:
            return q['url'][0]
    return href


def parse_age(p_texts):
    for t in p_texts:
        m = AGE_RE.search(t)
        if m:
            return m.group(1).replace(' ', ''), bool(m.group(2))
    return None, False


def age_days(label):
    if not label: return None
    m = re.match(r'(\d+)(h|d|w|mo|yr)', label)
    return int(m.group(1)) * AGE_UNITS[m.group(2)]


def author_of(textbox, item):
    """Walk backwards from a text box to the header of its card and return
    (author_name, author_url, posted_with, age_label, edited)."""
    name = url = posted_with = None
    p_texts = []
    for prev in textbox.find_all_previous(['p', 'a', 'div']):
        if prev is item: break
        if prev.name == 'div' and prev.get('aria-label', '').startswith('Posted with '):
            posted_with = posted_with or prev['aria-label'][len('Posted with '):]
        if prev.name == 'p':
            t = prev.get_text(' ', strip=True)
            p_texts.append(t)
            if 'reposted this' in t:
                break
        if prev.name == 'a' and name is None:
            href = prev.get('href', '')
            al = prev.get('aria-label', '') or ''
            txt = prev.get_text(' ', strip=True)
            par = prev.find_parent('p')
            if par is not None and par.get_text(' ', strip=True).startswith('with '):
                # "with <Page> • 1d": the page the post was shared with, not the author
                posted_with = posted_with or txt
                continue
            if al.startswith('View company: '):
                name, url = al[len('View company: '):], href
            elif al.endswith(' profile') and al.startswith('View '):
                name, url = al[5:-len(' profile')].rstrip('’\'s'), href
            elif ME in al and '/in/carlodemarchis' in href:
                name, url = ME, href
            elif txt and ('/in/' in href or '/company/' in href or '/showcase/' in href) \
                    and 'recent-activity' not in href and 'View my services' not in txt:
                name, url = re.sub(r'\s*•\s*(You|1st|2nd|3rd|Following)\s*$', '', txt), href
        if name and p_texts and parse_age(p_texts)[0]:
            break
    age, edited = parse_age(p_texts)
    if name and '’' in name: name = name.split('’')[0]
    return name, url, posted_with, age, edited


def parse_item(item, idx):
    rec = {'idx': idx}
    full_text = item.get_text(' ', strip=True)

    # ---- analytics / boost / ids
    a_an = item.find('a', href=re.compile(r'analytics/post-summary/urn:li:activity:(\d+)'))
    if a_an:
        aid = int(re.search(r'activity:(\d+)', a_an['href']).group(1))
        rec['activity_id'] = aid
        rec['activity_urn'] = f'urn:li:activity:{aid}'
        rec['post_url'] = f'https://www.linkedin.com/feed/update/urn:li:activity:{aid}/'
        ts = datetime.datetime.fromtimestamp((aid >> 22) / 1000, tz=datetime.timezone.utc)
        rec['posted_at_utc'] = ts.isoformat(timespec='seconds')
        rec['posted_date'] = ts.date().isoformat()
    a_boost = item.find('a', href=re.compile(r'campaignmanager/boost'))
    rec['boost_label'] = a_boost.get_text(' ', strip=True) if a_boost else None
    rec['was_boosted'] = rec['boost_label'] in ('Boost again', 'Manage boost')
    if a_boost:
        m = re.search(r'content=(urn[^&]+)', a_boost['href'])
        if m: rec['content_urn'] = urllib.parse.unquote(m.group(1))
    m = re.search(r'([\d,]+) impressions', full_text)
    rec['impressions'] = int(m.group(1).replace(',', '')) if m else None

    # ---- counts
    def count(label_prefix):
        for b in item.find_all('button'):
            if (b.get('aria-label') or '').startswith(label_prefix):
                t = b.get_text('', strip=True).replace(',', '')
                return int(t) if t.isdigit() else 0
        return 0
    rec['reactions'] = count('Reaction button')
    rec['comments'] = count('Comment')
    rec['reposts'] = count('Repost')

    # ---- repost header
    hdr = item.find('p', string=None)
    rec['reposted_by_me'] = bool(re.search(rf'{ME}\s+reposted this', full_text))

    # ---- text boxes: first = main, second = quoted post
    boxes = [tb for tb in item.select('[data-testid=expandable-text-box]')
             if not any(p.get('data-testid') == 'expandable-text-box' for p in tb.parents)]
    main = boxes[0] if boxes else None
    quoted = boxes[1] if len(boxes) > 1 else None

    if main is not None:
        name, url, posted_with, age, edited = author_of(main, item)
        rec['author'] = name
        rec['author_url'] = url
        rec['posted_with'] = posted_with
        rec['age_label'] = age
        rec['edited'] = edited
        # links inside the body
        mentions, hashtags, externals = [], [], []
        for a in main.find_all('a'):
            href = a.get('href', '')
            lt = link_type(href)
            txt = a.get_text(' ', strip=True)
            if lt in ('person', 'company', 'showcase', 'school'):
                mentions.append({'name': txt, 'type': lt, 'url': href.split('?')[0]})
            elif lt == 'hashtag':
                hashtags.append(txt.lstrip('#').lower())
            elif lt == 'external':
                externals.append({'text': txt, 'url': decode_external(href)})
        rec['mentions'] = mentions
        rec['hashtags'] = hashtags
        rec['external_links'] = externals
        rec['text'] = text_of(main)
        rec['text_chars'] = len(rec['text'])
        # bare lnkd.in links typed in the text
        rec['lnkd_links'] = re.findall(r'https://lnkd\.in/\S+', rec['text'])
    else:
        rec['author'] = rec['author_url'] = rec['posted_with'] = rec['age_label'] = None
        rec['edited'] = False
        rec['mentions'] = []; rec['hashtags'] = []; rec['external_links'] = []
        rec['text'] = ''; rec['text_chars'] = 0; rec['lnkd_links'] = []

    if quoted is not None:
        qname, qurl, qwith, qage, qedited = author_of(quoted, item)
        a_feed = item.find('a', href=re.compile(r'feed/update/urn:li:'))
        rec['quoted_post'] = {
            'author': qname, 'author_url': qurl, 'age_label': qage,
            'url': a_feed['href'] if a_feed else None,
            'text': text_of(quoted),
        }
    else:
        rec['quoted_post'] = None

    # ---- kind
    if rec['author'] and rec['author'] != ME:
        rec['kind'] = 'repost_other'       # I reposted someone else's post as-is
    elif rec['reposted_by_me']:
        rec['kind'] = 'repost_own'         # my own repost of my own post
    elif quoted is not None and rec['quoted_post']['author'] == ME:
        rec['kind'] = 'quote_own'          # my text + my own earlier post embedded
    elif quoted is not None:
        rec['kind'] = 'quote'              # my text + someone else's post embedded
    else:
        rec['kind'] = 'post'

    # ---- attachments (outside the text boxes)
    atts = []
    seen = set()
    for a in item.find_all('a'):
        if any(p.get('data-testid') == 'expandable-text-box' for p in a.parents):
            continue
        href = a.get('href', '')
        txt = a.get_text(' ', strip=True)
        if '/pulse/' in href and href not in seen and txt:
            seen.add(href)
            title = re.sub(r'^A guy with a scarf\s*', '', txt)
            title = re.sub(r'\s*Carlo De Marchis$', '', title)
            atts.append({'type': 'article', 'title': title, 'url': href})
        elif 'safety/go/' in href and href not in seen and txt and 'linkedin.com' not in decode_external(href):
            seen.add(href)
            u = decode_external(href)
            atts.append({'type': 'link', 'title': txt, 'url': u,
                         'domain': urllib.parse.urlparse(u).netloc})
    # de-dup link cards: LinkedIn renders title and domain as two anchors
    merged = []
    for at in atts:
        if at['type'] == 'link' and merged and merged[-1].get('url') == at['url']:
            if at['title'] == at['domain']:
                continue
        merged.append(at)
    m = re.search(r'([^·]{3,80}?)\s*·\s*(\d+) pages', full_text)
    if m:
        merged.append({'type': 'document', 'title': m.group(1).strip(), 'pages': int(m.group(2))})
    if item.find('video') or 'video' in (item.get_text(' ', strip=True)[:0]):
        merged.append({'type': 'video'})
    rec['attachments'] = merged
    rec['has_article'] = any(a['type'] == 'article' for a in merged)

    # ---- disclosures / series (cheap flags for later analysis)
    t = rec['text']
    rec['series'] = []
    if re.search(r'10 things to consider', t, re.I): rec['series'].append('10 Things To Consider')
    if 'Retention Zone' in t: rec['series'].append('Retention Zone')
    if 'Untangling AI' in t: rec['series'].append('Untangling AI')
    if re.search(r'\bEp\.?\s*\d+', t): rec['series'].append('Episode')
    if 'YouTube Football Tracker' in t or 'YTFT' in t: rec['series'].append('YouTube Football Tracker')
    rec['disclosures'] = []
    if 'Dolby OptiView' in t: rec['disclosures'].append('Dolby OptiView')
    if 'Cleeng' in t: rec['disclosures'].append('Cleeng')
    if 'Mercury' in t: rec['disclosures'].append('Mercury Intermedia')
    return rec


def main(path):
    html = load_html(path)
    soup = BeautifulSoup(html, 'lxml')
    items = soup.select('div[role=listitem][componentkey^=update-card-focus]')
    recs = [parse_item(it, i) for i, it in enumerate(items)]

    # approximate dates for items without a URN (reposts of others): use the
    # neighbours' exact dates, since the page is in reverse chronological order
    for i, r in enumerate(recs):
        if 'posted_date' in r: continue
        before = next((x for x in recs[i::-1] if 'posted_date' in x), None)   # newer
        after = next((x for x in recs[i:] if 'posted_date' in x), None)       # older
        ref = after or before
        r['posted_date'] = ref['posted_date'] if ref else None
        r['date_is_approx'] = True
    for r in recs:
        r.setdefault('date_is_approx', False)

    m = re.search(r'(\d{4}-\d{2}-\d{2})', os.path.basename(path))
    captured = m.group(1) if m else datetime.date.today().isoformat()
    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'captures')
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, captured + '.json')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump({'source': os.path.basename(path), 'captured_at': captured,
                   'count': len(recs), 'posts': recs}, f, ensure_ascii=False, indent=1)
    print(f'{len(recs)} items -> {out}')


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'raw/activity-page-2026-10-16.html.gz')
