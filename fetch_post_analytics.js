// Pull per-post analytics (video views, watch time, saves, sends) from LinkedIn's post analytics pages.
// Run in the browser console on any linkedin.com page while logged in (Claude in Chrome runs it the same way):
//   1. paste this file, 2. set IDS to the activity ids you want (sqlite: select activity_id from posts where media_type='video'),
//   3. when it finishes it prints compact rows "id:impressions:video_views:watch_s:avg_s:reactions:comments:reposts:saves:sends;..."
//   4. paste the rows into merge_post_analytics.py (see README).
const IDS = [];
const num = s => { const m = /^([\d.,]+)\s*([KM])?$/.exec((s||'').trim()); if (!m) return null; let v = parseFloat(m[1].replace(/,/g,'')); if (m[2]==='K') v*=1000; if (m[2]==='M') v*=1e6; return Math.round(v); };
const dur = s => { if (!s) return null; let t = 0, m, any = false; const re = /(\d+)\s*([hms])/g; while ((m = re.exec(s))) { any = true; t += +m[1] * (m[2]==='h'?3600:m[2]==='m'?60:1); } return any ? t : null; };
const parse = html => {
  const lines = html.replace(/<script[\s\S]*?<\/script>/g,'').replace(/<style[\s\S]*?<\/style>/g,'').replace(/<[^>]+>/g,'\n').split('\n').map(s=>s.trim()).filter(Boolean);
  const before = lab => { const i = lines.indexOf(lab); return i > 0 ? num(lines[i-1]) : null; };
  const after = lab => { const i = lines.indexOf(lab); return i >= 0 ? lines[i+1] : null; };
  return [before('Impressions'), before('Video views'), dur(after('Watch time')), dur(after('Average watch time')), num(after('Reactions')), num(after('Comments')), num(after('Reposts')), num(after('Saves')), num(after('Sends on LinkedIn'))];
};
(async () => {
  const rows = [];
  for (const id of IDS) {
    const r = await fetch(`https://www.linkedin.com/analytics/post-summary/urn:li:activity:${id}/`, {credentials:'include'});
    const t = await r.text();
    if (r.status === 200 && t.includes('Impressions')) rows.push([id, ...parse(t)].map(v => v ?? '').join(':'));
    await new Promise(res => setTimeout(res, 700));
  }
  window.__rows = rows.join(';'); console.log(window.__rows);
})();
