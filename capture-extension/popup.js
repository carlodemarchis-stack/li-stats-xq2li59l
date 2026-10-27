// LinkedIn "All activity" and "Comments" capture, for linkedin-posts/refresh.sh.
//
// On https://www.linkedin.com/in/carlodemarchis/recent-activity/all/ the popup asks
// for a target date, scrolls the feed until a post at or before that date is loaded,
// then saves the whole page as ~/Downloads/activity-page-<today>.html. The parser
// (parse_linkedin.py) needs the full markup: expandable-text-box, the
// Like/Comment/Repost button aria-labels and the "View analytics" links.
// On .../recent-activity/comments/ the same capture scrolls until a comment at or
// before the date is loaded (date from the comment URN) and saves
// comments-page-<today>.html for parse_comments.py.

const HOST = 'www.linkedin.com';
const PATH = '/recent-activity/';
const STORE_BASE = 'https://carlodemarchis-stack.github.io/li-stats-xq2li59l/';
const DEFAULT_DAYS = 35;
const MAX_SCROLLS = 150;

const urlEl = document.getElementById('url');
const rangeEl = document.getElementById('range');
const dateRowEl = document.getElementById('date-row');
const dateEl = document.getElementById('date');
const hintEl = document.getElementById('hint');
const goEl = document.getElementById('go');
const msgEl = document.getElementById('msg');

let store = null;   // { newest, oldest, captured } from the published posts.json / comments.json
let mode = 'posts'; // 'posts' on the All activity page, 'comments' on the Comments page

function say(text, cls = '') {
  msgEl.textContent = text;
  msgEl.className = cls;
}

// Runs inside the page (chrome.scripting.executeScript). Self-contained: nothing from
// this file's scope is available in there. Returns the page HTML plus a summary; the
// popup saves it with chrome.downloads (a page-side <a download> gets blocked by
// Chrome's scripted-download rules), so the popup has to stay open until it is done.
async function captureActivity(targetDate, maxScrolls, mode) {
  const ITEM = 'div[role=listitem][componentkey^="update-card-focus"]';
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const items = () => document.querySelectorAll(ITEM).length;

  // exact date from the URN: top 41 bits of the id = ms since the epoch. Posts: the
  // activity id in the "View analytics" links; comments: the comment id in
  // urn:li:comment:(activity:<post>,<comment>), which only appears in the markup, so
  // only the last few cards are scanned (the feed is newest first; serialising the
  // whole page on every round froze the tab past ~250 cards).
  const oldest = () => {
    let min = null;
    const ids = [];
    if (mode === 'comments') {
      const re = /urn:li:comment:\(activity:\d+,(\d+)\)/g;
      const cards = document.querySelectorAll(ITEM);
      for (const card of [...cards].slice(-3)) {
        let m; const html = card.outerHTML;
        while ((m = re.exec(html))) ids.push(m[1]);
      }
    } else {
      for (const a of document.querySelectorAll('a[href*="analytics/post-summary/urn:li:activity:"]')) {
        const m = (a.getAttribute('href') || '').match(/activity:(\d+)/);
        if (m) ids.push(m[1]);
      }
    }
    for (const id of ids) {
      const d = new Date(Number(BigInt(id) >> 22n)).toISOString().slice(0, 10);
      if (min === null || d < min) min = d;
    }
    return min;
  };

  // the feed scrolls inside <main>, not the window; find whichever ancestor scrolls
  const scroller = () => {
    let el = document.querySelector(ITEM);
    while (el && el !== document.body) {
      const cs = getComputedStyle(el);
      if (/(auto|scroll)/.test(cs.overflowY) && el.scrollHeight > el.clientHeight) return el;
      el = el.parentElement;
    }
    return document.scrollingElement || document.documentElement;
  };

  // The feed loads 10 posts per page request. Those requests 503 now and then and
  // the page retries them with a backoff, but only if it is not hammered: scrolling
  // every 1.5 s stalled for good at 140-240 posts, waiting for each page and resting
  // between scrolls went past 360. So: scroll, wait for growth (up to 8 s), rest
  // 2.5 s; on no growth, nudge (up and back down) and give it five more rounds.
  let scrolls = 0, stale = 0, reason;
  for (;;) {
    const o = oldest();
    if (o && o <= targetDate) { reason = 'reached target date'; break; }
    if (scrolls >= maxScrolls) { reason = 'scroll cap'; break; }
    const sc = scroller();
    const n = items();
    if (stale) { sc.scrollTo(0, sc.scrollHeight - 800); await sleep(300); }
    sc.scrollTo(0, sc.scrollHeight);
    scrolls++;
    let waited = 0;
    while (items() === n && waited < 8000) { await sleep(500); waited += 500; }
    if (items() === n) {
      if (++stale >= 5) { reason = 'page stopped growing'; break; }
    } else {
      stale = 0;
    }
    await sleep(2500);
  }

  const html = '<!DOCTYPE html>\n' + document.documentElement.outerHTML;
  return { html, posts: items(), oldest: oldest(), scrolls, reason };
}

const todayFilename = () => `${mode === 'comments' ? 'comments' : 'activity'}-page-${iso(new Date())}.html`;
const noun = () => mode === 'comments' ? 'comment' : 'post';

// local calendar date, not UTC: toISOString() would roll back a day in the evening
const iso = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;

// the date the capture scrolls back to, for the selected range; null when unknown
function targetDate() {
  const d = new Date();
  switch (rangeEl.value) {
    case 'store-newest': return store && store.newest;
    case 'store-oldest': return store && store.oldest;
    case 'this-month': d.setDate(1); return iso(d);
    case 'last-month': d.setDate(1); d.setMonth(d.getMonth() - 1); return iso(d);
    case 'this-year': return `${d.getFullYear()}-01-01`;
    case 'one-year': d.setFullYear(d.getFullYear() - 1); return iso(d);
    case 'weeks': d.setDate(d.getDate() - DEFAULT_DAYS); return iso(d);
    case 'date': return dateEl.value || null;
  }
  return null;
}

function describe() {
  dateRowEl.hidden = rangeEl.value !== 'date';
  const t = targetDate();
  const what = {
    'store-newest': `only ${noun()}s newer than the store, plus the first page`,
    'store-oldest': `every ${noun()} already in the store, to refresh impressions and reactions`
  }[rangeEl.value] || `${noun()}s from that date on`;
  if (!t) {
    hintEl.textContent = rangeEl.value.startsWith('store') ? 'store not loaded' : 'pick a date';
  } else {
    hintEl.textContent = `until a ${noun()} from ${t} or earlier is loaded: ${what}`;
  }
  goEl.disabled = !t;
}

// newest / oldest post (or comment) dates in the published store
async function loadStore() {
  const file = mode === 'comments' ? 'comments.json' : 'posts.json';
  const res = await fetch(`${STORE_BASE}${file}?t=${Date.now()}`, { cache: 'no-store' });
  if (!res.ok) throw new Error(`store returned ${res.status}`);
  const data = await res.json();
  const dates = (mode === 'comments' ? data.comments.map((c) => c.commented_date) : data.posts.map((p) => p.posted_date)).filter(Boolean).sort();
  if (!dates.length) throw new Error(`store has no dated ${noun()}s`);
  return { newest: dates[dates.length - 1], oldest: dates[0], captured: data.captured_at };
}

async function run(tab) {
  const target = targetDate();
  if (!target) return say('Pick a date first.', 'err');
  goEl.disabled = rangeEl.disabled = dateEl.disabled = true;
  say(`Scrolling to ${target}… keep this popup open.`);
  try {
    const [res] = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: captureActivity,
      args: [target, MAX_SCROLLS, mode]
    });
    const r = res?.result;
    if (!r) throw new Error('no result from the page');
    const filename = todayFilename();
    const url = URL.createObjectURL(new Blob([r.html], { type: 'text/html' }));
    await chrome.downloads.download({ url, filename, saveAs: false });
    say(`Saved ${filename}: ${r.posts} ${noun()}s, oldest ${r.oldest || '?'} (${r.reason}, ${r.scrolls} scrolls). ` +
        `Now run refresh.sh`, 'ok');
  } catch (e) {
    say('Capture failed: ' + e.message, 'err');
    goEl.disabled = rangeEl.disabled = dateEl.disabled = false;
  }
}

async function init() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab || !tab.url) return say('No active tab.', 'err');
  const u = new URL(tab.url);
  if (u.hostname !== HOST || !u.pathname.includes(PATH)) {
    return say('Open your LinkedIn "All activity" or "Comments" page first (linkedin.com/in/…/recent-activity/all/ or …/comments/).', 'err');
  }
  mode = /\/recent-activity\/comments\/?/.test(u.pathname) ? 'comments' : 'posts';
  urlEl.textContent = tab.url;
  const d = new Date();
  d.setDate(d.getDate() - DEFAULT_DAYS);
  dateEl.value = iso(d);
  rangeEl.addEventListener('change', describe);
  dateEl.addEventListener('change', describe);
  goEl.addEventListener('click', () => run(tab));
  dateEl.addEventListener('keydown', (e) => { if (e.key === 'Enter') run(tab); });

  say('Loading the store…');
  try {
    store = await loadStore();
    rangeEl.options[0].textContent = `newest ${noun()} in the store (${store.newest})`;
    rangeEl.options[1].textContent = `oldest ${noun()} in the store (${store.oldest})`;
    say(`Store captured ${store.captured}. Scrolls back, then saves the page to Downloads.`);
  } catch (e) {
    rangeEl.value = 'weeks';
    say(`Store unreachable (${e.message}); store options are off.`, 'err');
  }
  describe();
  goEl.focus();
}

init();
