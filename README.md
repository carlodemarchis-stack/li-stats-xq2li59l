# LinkedIn posts, local data store

One year of Carlo De Marchis's LinkedIn activity, captured from the
"All activity" page (https://www.linkedin.com/in/carlodemarchis/recent-activity/all/)
on 2026-10-16 and parsed into a local store.

## Numbers

| | |
|---|---|
| Items on the page | 290 |
| Authored by me (posts, quotes, own reposts) | 277 |
| Exact date range (from activity URNs) | 2025-12-04 to 2026-10-16 |
| Total impressions (where shown) | 444,753 |
| Total reactions / comments / reposts | 4,698 / 754 / 431 |
| Newsletter article cards | 138 |
| Mentions (people, companies, showcase pages) | 1,496 |
| Hashtags | 526 |

Item kinds:

| kind | n |
|---|---|
| `post` | 252 |
| `quote` | 16 |
| `repost_other` | 13 |
| `quote_own` | 8 |
| `repost_own` | 1 |

- `post`: my own post.
- `quote`: my text with someone else's post embedded (the embedded post is in `quoted_post`).
- `quote_own`: my text with one of my own earlier posts embedded.
- `repost_own`: a plain repost of my own post (LinkedIn lists both; no analytics on the repost).
- `repost_other`: a plain repost of someone else's post. No analytics, so no impressions; the
  date is approximate (`date_is_approx = 1`), taken from the neighbouring items.

## Files

| file | what |
|---|---|
| `raw/activity-page-2026-10-16.html.gz` | the page as copied from the browser (HTML flavour of the clipboard), 22 MB uncompressed |
| `raw/activity-page-2026-10-16.txt` | the same, plain-text flavour |
| `parse_linkedin.py` | parser: one HTML capture -> `captures/<date>.json` |
| `captures/*.json` | one file per capture, the merge input |
| `build_store.py` | merges all captures -> `posts.json` + `posts.sqlite` (with `history`) |
| `refresh.sh` | capture file (or clipboard) -> parse -> merge -> export -> commit -> push |
| `capture-extension/` | private Chrome extension: scrolls the activity page back to a date and saves it to `~/Downloads/activity-page-<today>.html` |
| `posts.json` | one record per item, nested (mentions, hashtags, attachments, quoted post) |
| `posts.sqlite` | the same, normalised into tables |
| `export_analytics.py` | `posts.json` -> `analytics-data.js` (compact rows for the dashboard) |
| `index.html` + `analytics-data.js` | the local analytics dashboard |

Rebuild everything from the raw captures with:

```bash
python3 parse_linkedin.py raw/activity-page-2026-10-16.html.gz   # one capture -> captures/<date>.json
python3 build_store.py                                           # all captures -> posts.json + posts.sqlite
python3 export_analytics.py                                      # posts.json -> analytics-data.js
```

To add a newer capture by hand: run the extension (see Refreshing) or, without it, open the
All activity page, scroll until the oldest post you want is loaded, select all, copy, then save
the clipboard's HTML flavour with

```bash
osascript -e 'the clipboard as «class HTML»' | sed 's/^«data HTML//; s/»$//' | xxd -r -p | gzip -c > raw/activity-page-YYYY-MM-DD.html.gz
```

and run the parser on it. Posts are keyed by `activity_id`, so two captures can be merged
and deduplicated on that column.

## Published page

Live at https://carlodemarchis-stack.github.io/li-stats-xq2li59l/ (public GitHub Pages, unlisted URL, `noindex`; repo `carlodemarchis-stack/li-stats-xq2li59l`).

### Refreshing

1. Open https://www.linkedin.com/in/carlodemarchis/recent-activity/all/ in Chrome and press
   ⌘⇧L (the LinkedIn Activity Capture extension, see below). Pick how far back to scroll and
   click Capture. Keep the popup open: it scrolls the feed until a post at or before the target
   date is loaded, then saves the page as `~/Downloads/activity-page-<today>.html` and reports
   how many posts it got. The choices (the popup reads the published `posts.json` for the two
   store-based ones):
   - **newest post in the store** (default): only what was posted since the last capture, plus
     the first page. The routine refresh.
   - **oldest post in the store**: re-reads every post already in the store, to refresh
     impressions, reactions, comments and reposts across the whole year (~30 scrolls).
   - **this month / last month / this year / one year / 5 weeks**, or **a date…**.
   Older posts are kept from earlier captures whatever the reach.
2. Run:

```bash
./refresh.sh
```

With no argument it takes the newest `activity-page-*.html` in `~/Downloads`; a path can also be
given (`./refresh.sh ~/Downloads/activity-page-2026-11-01.html`). With no file at all it falls
back to the clipboard (scroll, Select All, Copy, as before). The capture is gzipped into
`raw/activity-page-<date>.html.gz` (date from the file name), parsed into `captures/<date>.json`,
every capture is merged into `posts.json` / `posts.sqlite` (`build_store.py`: union of all
captures keyed by `activity_id`, freshest counts win, every capture's counts kept in
`history`), `analytics-data.js` is regenerated, then commit and push. The page updates about a
minute later.

#### Installing the capture extension

Once per Chrome profile: open `chrome://extensions`, turn on Developer mode, click
"Load unpacked" and pick the `capture-extension/` folder of this repo. It is private to this
profile (nothing is published to the Web Store) and asks for no site permissions: it only acts
on the tab it is invoked on. If ⌘⇧L is taken, change it at `chrome://extensions/shortcuts`.
To install it on another machine, clone the repo or zip the folder (`zip -r capture-extension.zip
capture-extension`), unzip there and Load unpacked the same way.

The extension stops scrolling at the target date, after 150 scrolls, or when the page stops
growing (five rounds with no new posts, about 50 s). It expands nothing on the page; the full
post text is already in the markup. The feed loads ten posts per page request and LinkedIn
answers some of those with a 503; the page retries them with a backoff, but only if it is not
scrolled again meanwhile, so the extension waits for each page to arrive and rests between
scrolls (about 3 s per ten posts; a full year is roughly two minutes). If a capture still ends
with "page stopped growing" short of the target, run it again: a page reload starts a fresh
pagination, and build_store.py merges whatever each capture reached.

## Sponsor pages

`pages.json` lists one page per sponsor (id, sponsor name, an unguessable `slug`, title, intro).
`export_analytics.py` rebuilds them on every refresh: `<slug>.html` is `index.html` with a
`window.LI_PAGE` config injected, and `data-<slug>.js` holds only the posts that mention that
sponsor (body or footer), with the other sponsors' flags removed. On those pages the Sponsor filter
becomes a Mention switch (All mentions / About <sponsor> / Footer mention only), the other
sponsors' names and tags are hidden, and the rest of the dashboard is unchanged. Share the slug URL
with the sponsor; nothing links to it from the main page. To add a page, add an entry to
`pages.json` with a fresh random slug and run the export.

## Analytics page

`index.html` is a local dashboard over the store. Open it straight from Finder (double-click;
it loads `analytics-data.js` next to it, no server needed), or serve the folder with
`python3 -m http.server`.

- Search bar above the filters, scoping everything below it and listing the matching posts with the
  matching passage highlighted. Plain words match the post text, quoted post, mentions and hashtags
  (accent-insensitive, all words must match); `"exact phrase"`, `-exclude`, `#tag`, `@name`,
  `has:video|images|article|document|link|boosted`, `about:dolby|cleeng|mercury` (sponsor as subject),
  `kind:post|quote|repost`, `series:10things|retention|dataviz|ytft|episode|untangling`,
  `imp>5000`, `chars<300`, `date:2026-07`. The query is kept in the URL (`?q=`), so a search can be bookmarked.
- Filters (one row, scope everything below): date range, my posts vs. everything incl. reposts,
  series, format (article, native video, images, document, boosted), sponsor (as subject of the post).
- Stat tiles: posts, impressions, reactions, comments, reposts, engagement rate.
- Latest posts: the ten most recent in the current selection, newest first.
- Impressions per week and posts per week; every post as a dot over time: blue with article,
  orange without, green for quote reposts, a gold ring on boosted posts, plain reposts hollow on
  the baseline (click a dot to open the post on LinkedIn); best posts table, sortable by any column.
- Series, sponsors (subject of the post vs. footer only) and "what travels" (average impressions by format).
- Growth between captures: pick two capture dates; stat tiles with what the posts present in both
  gained (impressions, reactions, comments, reposts), a bar per capture with the total impressions of
  the posts present in every capture of the range, and the top movers. `deltas.py` prints the same
  comparison in the terminal. Captures are keyed by date, so one snapshot per day; the totals are
  only comparable for posts present in both captures, which is why a regular full capture (scroll
  back to the oldest post you care about) is what makes the trend meaningful.
- Post length in six segments (under 300 to 2,400+ characters): posts per segment next to average
  impressions per segment, engagement in the tooltip and table. The card has its own With / Without article
  toggle that overrides the main Format filter for that card only.
- Who I tag (people / companies / showcase pages, with my own pages hidden by default), hashtags.
- Day of week and hour of day (Europe/Rome) of publication.
- Links in the text (none, one, two or more external links in the body) and hashtags (none, 1 to 3,
  4 to 6, 7 or more): posts per group next to average impressions, engagement in the tooltip and table.
- People tagged and companies tagged (none, 1 to 2, 3 to 5, 6 or more distinct handles, my own pages
  excluded), same layout.
- Every chart has a Table button with the same numbers; the page follows the OS light/dark
  setting and has a Theme toggle.

After re-running the parser, regenerate the page data with:

```bash
python3 export_analytics.py
```

## Record fields (posts.json / table `posts`)

| field | notes |
|---|---|
| `idx` | position on the page, 0 = newest |
| `activity_id`, `activity_urn`, `post_url` | from the "View analytics" link; absent on plain reposts |
| `content_urn` | `urn:li:ugcPost:...` or `urn:li:share:...`, from the Boost link |
| `posted_at_utc`, `posted_date` | decoded from the activity id (top 41 bits = ms since epoch), exact to the second |
| `date_is_approx` | 1 when the date was borrowed from a neighbour (plain reposts) |
| `age_label`, `edited` | what the page showed ("2w", "1mo") and whether the post was edited |
| `kind`, `author`, `author_url`, `posted_with` | see kinds above; `posted_with` is the page a post was shared with ("A guy with a scarf", "2 others") |
| `text`, `text_chars` | full body, line breaks preserved, link text kept, "... more" expanded |
| `mentions[]` | `{name, type: person/company/showcase/school, url}` for every tagged profile |
| `hashtags[]` | lower case, without `#` |
| `external_links[]`, `lnkd_links[]` | links in the body: decoded `linkedin.com/safety/go` targets, and bare lnkd.in short links |
| `attachments[]` | `article` (newsletter card: title + pulse URL), `link` (external card: title, url, domain), `document` (title + pages) |
| `first_captured`, `last_captured`, `history[]` | which captures contained the post; counts per capture |
| `quoted_post` | `{author, author_url, age_label, url, text}` for quote reposts |
| `reactions`, `comments`, `reposts`, `impressions` | counts shown on the page; impressions null on reposts |
| `boost_label`, `was_boosted` | "Boost" / "Boost again" / "Manage boost"; the last two mean the post was boosted |
| `media_type`, `image_count` | `video` (native video player), `document`, `article`, `images` (feed images, with count), `link`, `text`; first match in that order |
| `series[]` | cheap flags: 10 Things To Consider, Retention Zone, Untangling AI, Episode, YouTube Football Tracker, Dataviz (the interactive sport experiences) |
| `sponsors[]`, `sponsor_subject[]` | `{name, where}` per sponsor (Dolby OptiView, Cleeng, Mercury Intermedia): `body` when named in the post itself, `footer` when only in the disclosure boilerplate; Retention Zone episodes count as Cleeng body. `sponsor_subject` lists the body ones |
| `disclosures[]` | the sponsor names, body or footer (kept for compatibility) |

SQLite side tables: `history`, `mentions`, `hashtags`, `attachments`, `external_links`, `series`,
`sponsors` (name, place), `disclosures`, all keyed by `post_idx`.

## What the page does not give

- Images and videos are not captured (only the text and link cards). Image carousels show up on
  the page as unlabeled bullets.
- Comment text, reaction breakdowns, follower counts per post, and the per-post analytics
  (demographics, members reached) live behind the "View analytics" link and are not here.
- The page truncates nothing in the body, but "... more" on very long quoted posts may have
  been collapsed; `quoted_post.text` is what was rendered.

## Quick queries

```sql
-- best posts by impressions
SELECT posted_date, impressions, reactions, substr(text,1,80) FROM posts
WHERE impressions IS NOT NULL ORDER BY impressions DESC LIMIT 20;

-- posts per month with reach
SELECT substr(posted_date,1,7) m, count(*) n, sum(impressions) imp FROM posts GROUP BY m;

-- who I tag most
SELECT name, count(*) n FROM mentions GROUP BY name ORDER BY n DESC LIMIT 30;

-- engagement rate
SELECT posted_date, impressions, round(100.0*(reactions+comments+reposts)/impressions,2) er,
       substr(text,1,60) FROM posts WHERE impressions > 500 ORDER BY er DESC LIMIT 20;
```
