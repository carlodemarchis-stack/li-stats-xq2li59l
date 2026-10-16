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
| `parse_linkedin.py` | parser: HTML -> `posts.json` + `posts.sqlite` |
| `posts.json` | one record per item, nested (mentions, hashtags, attachments, quoted post) |
| `posts.sqlite` | the same, normalised into tables |
| `export_analytics.py` | `posts.json` -> `analytics-data.js` (compact rows for the dashboard) |
| `index.html` + `analytics-data.js` | the local analytics dashboard |

Rebuild everything with:

```bash
python3 parse_linkedin.py raw/activity-page-2026-10-16.html.gz
```

To add a newer capture: open the All activity page, scroll until the oldest post you want is
loaded, select all, copy, then save the clipboard's HTML flavour with

```bash
osascript -e 'the clipboard as «class HTML»' | sed 's/^«data HTML//; s/»$//' | xxd -r -p | gzip -c > raw/activity-page-YYYY-MM-DD.html.gz
```

and run the parser on it. Posts are keyed by `activity_id`, so two captures can be merged
and deduplicated on that column.

## Analytics page

`index.html` is a local dashboard over the store. Open it straight from Finder (double-click;
it loads `analytics-data.js` next to it, no server needed), or serve the folder with
`python3 -m http.server`.

- Filters (one row, scope everything below): date range, my posts vs. everything incl. reposts,
  series, format (with/without article, boosted).
- Stat tiles: posts, impressions, reactions, comments, reposts, engagement rate.
- Impressions per week and posts per week; every post as a dot over time (click a dot to open
  the post on LinkedIn); best posts table, sortable by any column.
- Series, disclosures and "what travels" (average impressions by format).
- Who I tag (people / companies / showcase pages, with my own pages hidden by default), hashtags.
- Day of week and hour of day (Europe/Rome) of publication.
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
| `quoted_post` | `{author, author_url, age_label, url, text}` for quote reposts |
| `reactions`, `comments`, `reposts`, `impressions` | counts shown on the page; impressions null on reposts |
| `boost_label`, `was_boosted` | "Boost" / "Boost again" / "Manage boost"; the last two mean the post was boosted |
| `series[]` | cheap flags: 10 Things To Consider, Retention Zone, Untangling AI, Episode, YouTube Football Tracker |
| `disclosures[]` | cheap flags: Dolby OptiView, Cleeng, Mercury Intermedia named in the text |

SQLite side tables: `mentions`, `hashtags`, `attachments`, `external_links`, `series`,
`disclosures`, all keyed by `post_idx`.

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
