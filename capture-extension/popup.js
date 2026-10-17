// LinkedIn "All activity" capture, for linkedin-posts/refresh.sh.
//
// On https://www.linkedin.com/in/carlodemarchis/recent-activity/all/ the popup asks
// for a target date, scrolls the feed until a post at or before that date is loaded,
// then saves the whole page as ~/Downloads/activity-page-<today>.html. The parser
// (parse_linkedin.py) needs the full markup: expandable-text-box, the
// Like/Comment/Repost button aria-labels and the "View analytics" links.

const HOST = 'www.linkedin.com';
const PATH = '/recent-activity/';
const DEFAULT_DAYS = 35;
const MAX_SCROLLS = 150;

const urlEl = document.getElementById('url');
const dateEl = document.getElementById('date');
const goEl = document.getElementById('go');
const msgEl = document.getElementById('msg');

function say(text, cls = '') {
  msgEl.textContent = text;
  msgEl.className = cls;
}

// Runs inside the page (chrome.scripting.executeScript). Self-contained: nothing from
// this file's scope is available in there. Returns the page HTML plus a summary; the
// popup saves it with chrome.downloads (a page-side <a download> gets blocked by
// Chrome's scripted-download rules), so the popup has to stay open until it is done.
async function captureActivity(targetDate, maxScrolls) {
  const ITEM = 'div[role=listitem][componentkey^="update-card-focus"]';
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const items = () => document.querySelectorAll(ITEM).length;

  // exact publish date from the activity URN: top 41 bits = ms since the epoch
  const oldest = () => {
    let min = null;
    for (const a of document.querySelectorAll('a[href*="analytics/post-summary/urn:li:activity:"]')) {
      const m = (a.getAttribute('href') || '').match(/activity:(\d+)/);
      if (!m) continue;
      const d = new Date(Number(BigInt(m[1]) >> 22n)).toISOString().slice(0, 10);
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

  let scrolls = 0, stale = 0, lastH = -1, lastN = -1, reason;
  for (;;) {
    const o = oldest();
    if (o && o <= targetDate) { reason = 'reached target date'; break; }
    if (scrolls >= maxScrolls) { reason = 'scroll cap'; break; }
    const sc = scroller();
    sc.scrollTo(0, sc.scrollHeight);
    scrolls++;
    await sleep(1500);
    const h = sc.scrollHeight, n = items();
    if (h === lastH && n === lastN) {
      if (++stale >= 4) { reason = 'page stopped growing'; break; }
    } else {
      stale = 0;
    }
    lastH = h; lastN = n;
  }

  const html = '<!DOCTYPE html>\n' + document.documentElement.outerHTML;
  return { html, posts: items(), oldest: oldest(), scrolls, reason };
}

function todayFilename() {
  const d = new Date();
  const p = (n) => String(n).padStart(2, '0');
  return `activity-page-${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}.html`;
}

async function run(tab) {
  if (!dateEl.value) return say('Pick a date first.', 'err');
  goEl.disabled = dateEl.disabled = true;
  say(`Scrolling to ${dateEl.value}… keep this popup open.`);
  try {
    const [res] = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: captureActivity,
      args: [dateEl.value, MAX_SCROLLS]
    });
    const r = res?.result;
    if (!r) throw new Error('no result from the page');
    const filename = todayFilename();
    const url = URL.createObjectURL(new Blob([r.html], { type: 'text/html' }));
    await chrome.downloads.download({ url, filename, saveAs: false });
    say(`Saved ${filename}: ${r.posts} posts, oldest ${r.oldest || '?'} (${r.reason}, ${r.scrolls} scrolls). ` +
        `Now run refresh.sh`, 'ok');
  } catch (e) {
    say('Capture failed: ' + e.message, 'err');
    goEl.disabled = dateEl.disabled = false;
  }
}

async function init() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab || !tab.url) return say('No active tab.', 'err');
  const u = new URL(tab.url);
  if (u.hostname !== HOST || !u.pathname.includes(PATH)) {
    return say('Open your LinkedIn "All activity" page first (linkedin.com/in/…/recent-activity/all/).', 'err');
  }
  urlEl.textContent = tab.url;
  const d = new Date();
  d.setDate(d.getDate() - DEFAULT_DAYS);
  dateEl.value = d.toISOString().slice(0, 10);
  goEl.disabled = false;
  goEl.focus();
  say('Scrolls back to the date, then saves the page to Downloads.');
  goEl.addEventListener('click', () => run(tab));
  dateEl.addEventListener('keydown', (e) => { if (e.key === 'Enter') run(tab); });
}

init();
