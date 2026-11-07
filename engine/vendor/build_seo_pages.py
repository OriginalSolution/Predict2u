#!/usr/bin/env python3
"""Build crawlable match + league SEO pages and sitemap from home-picks.json."""
from __future__ import annotations
import json, os, re, sys, html, datetime as dt
from pathlib import Path
from collections import defaultdict

REPO = Path(sys.argv[1] if len(sys.argv) > 1 else "/workspace/Predict2u")
BASE = "https://predict2u.com"
OG = f"{BASE}/og-card.png?v=1"

def esc(s):
    return html.escape("" if s is None else str(s), quote=True)

def slug(s: str, maxlen=72) -> str:
    s = (s or "").lower().replace("&", " and ")
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return (s[:maxlen] or "item").strip("-")

def split_match(m: str):
    for sep in (" v ", " vs ", " vs. ", " - "):
        if sep in (m or ""):
            a, b = m.split(sep, 1)
            return a.strip(), b.strip()
    return m or "Home", "Away"

def rate(x):
    try:
        v = float(x)
        if v <= 1: v *= 100
        return f"{v:.0f}%"
    except Exception:
        return "—"

def odds(x):
    try:
        return f"{float(x):.2f}"
    except Exception:
        return "—"

CSS = """
:root{--bg:#070b12;--card:#0f1724;--card2:#131e2e;--line:rgba(255,255,255,.08);--tx:#e8eef7;--mut:#8b98ab;--acc:#22c55e;--gold:#fbbf24}
*{box-sizing:border-box}html,body{margin:0;background:var(--bg);color:var(--tx);font:15px/1.45 Inter,system-ui,sans-serif}
a{color:var(--acc);text-decoration:none}a:hover{text-decoration:underline}
.wrap{max-width:720px;margin:0 auto;padding:14px 14px 96px}
.hero{background:radial-gradient(120% 140% at 0% 0%,rgba(34,197,94,.16),transparent 55%),linear-gradient(160deg,#0f1a2a,#0a111c);border:1px solid var(--line);border-radius:18px;padding:16px;margin:6px 0 12px}
.kicker{display:inline-block;font-size:.7rem;font-weight:800;letter-spacing:.14em;color:var(--acc);background:rgba(34,197,94,.12);padding:5px 10px;border-radius:999px}
h1{font-size:clamp(1.35rem,5.5vw,1.9rem);margin:10px 0 6px;letter-spacing:-.02em;line-height:1.15}
.lead,.meta{color:var(--mut);font-size:.9rem;margin:0 0 8px}
.crumb{font-size:.78rem;color:var(--mut);margin:0 0 10px;display:flex;flex-wrap:wrap;gap:6px;align-items:center}
.crumb a{color:#c7d2e1}
.card{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:14px;margin:10px 0}
.sel{display:flex;justify-content:space-between;gap:10px;padding:10px 12px;background:var(--card2);border-radius:12px;font-weight:800;margin:8px 0}
.sel b{color:var(--gold)}
.stats{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin:10px 0 0;font-size:.82rem}
.stats dt{color:var(--mut);font-size:.68rem;text-transform:uppercase;letter-spacing:.06em;font-weight:700}
.stats dd{margin:2px 0 0;font-weight:800}
.case{margin:10px 0 0;font-size:.85rem;line-height:1.5;color:#c7d2e1;border-left:3px solid var(--acc);padding-left:10px}
.list{display:grid;gap:8px;margin:10px 0}
.row{display:block;background:var(--card);border:1px solid var(--line);border-radius:14px;padding:12px;color:var(--tx)}
.row:hover{border-color:rgba(34,197,94,.45)}
.row b{display:block;font-size:.95rem}.row small{color:var(--mut)}
.pill{display:inline-block;font-size:.68rem;font-weight:900;letter-spacing:.04em;text-transform:uppercase;padding:2px 8px;border-radius:999px;background:#1f2a3a;color:#c3d0e2}
.pill-won{background:#0f3d2a;color:#7ff0b8}.pill-lost{background:#3a1520;color:#ffb0c0}
.links{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px}
.links a{min-height:40px;display:inline-flex;align-items:center;padding:0 12px;border-radius:999px;border:1px solid var(--line);background:#16233a;color:var(--tx);font-weight:700;font-size:.85rem}
.note{font-size:.78rem;color:var(--mut);margin-top:14px}
"""

def og_block(title, desc, url):
    return f'''  <!-- p2u-og -->
  <meta property="og:type" content="website"/>
  <meta property="og:site_name" content="Predict2u.com"/>
  <meta property="og:title" content="{esc(title)}"/>
  <meta property="og:description" content="{esc(desc)}"/>
  <meta property="og:url" content="{esc(url)}"/>
  <meta property="og:image" content="{OG}"/>
  <meta property="og:image:secure_url" content="{OG}"/>
  <meta property="og:image:type" content="image/png"/>
  <meta property="og:image:width" content="1200"/>
  <meta property="og:image:height" content="630"/>
  <meta property="og:image:alt" content="Predict2u.com — Daily booking codes"/>
  <meta name="twitter:card" content="summary_large_image"/>
  <meta name="twitter:title" content="{esc(title)}"/>
  <meta name="twitter:description" content="{esc(desc)}"/>
  <meta name="twitter:image" content="{OG}"/>
  <!-- /p2u-og -->'''

def page(title, desc, url, body, jsonld=None):
    ld = ""
    if jsonld:
        ld = f'<script type="application/ld+json">{json.dumps(jsonld, ensure_ascii=False)}</script>\n'
    return f'''<!doctype html>
<html lang="en">
<head>
{og_block(title, desc, url)}
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"/>
  <title>{esc(title)}</title>
  <meta name="description" content="{esc(desc)}"/>
  <meta name="theme-color" content="#07111d"/>
  <link rel="canonical" href="{esc(url)}"/>
  <link rel="icon" href="../favicon-32x32.png"/>
  <link rel="manifest" href="../manifest.webmanifest"/>
  <style>{CSS}</style>
  {ld}</head>
<body>
<script src="../p2u-rg-v322.js?v=322" defer></script>
<script src="../p2u-live-track-v335.js?v=335" defer></script>
<main class="wrap">
{body}
<p class="note">Free daily football picks and booking codes on SportyBet, MSport, Betika, football.com and Betpawa. 18+ · Gamble responsibly.</p>
</main>
</body>
</html>
'''

def hub_page(title, desc, url, body):
    # hubs live at repo root — fix relative asset paths
    html_doc = page(title, desc, url, body)
    return html_doc.replace('href="../favicon', 'href="favicon').replace('href="../manifest', 'href="manifest').replace('src="../p2u-rg', 'src="p2u-rg').replace('src="../p2u-live', 'src="p2u-live')

def main():
    hp_path = REPO / "home-picks.json"
    hp = json.load(open(hp_path)) if hp_path.exists() else {"picks": [], "leagues": [], "date": ""}
    picks = [p for p in (hp.get("picks") or []) if p.get("match")]
    day = hp.get("date") or dt.date.today().isoformat()
    updated = hp.get("DATA_UPDATED") or hp.get("sourceUpdatedAt") or ""

    # Dedupe matches by eventId else match+date
    by_match = {}
    for p in picks:
        key = p.get("eventId") or f"{p.get('match')}|{p.get('date')}"
        by_match.setdefault(key, []).append(p)

    by_league = defaultdict(list)
    for p in picks:
        lg = p.get("league") or "Other"
        by_league[lg].append(p)

    match_dir = REPO / "match"
    league_dir = REPO / "league"
    match_dir.mkdir(exist_ok=True)
    league_dir.mkdir(exist_ok=True)

    # Clear old generated pages (keep dirs)
    for d in (match_dir, league_dir):
        for f in d.glob("*.html"):
            f.unlink()

    match_urls = []
    league_urls = []
    match_index_rows = []

    for key, group in sorted(by_match.items(), key=lambda kv: (kv[1][0].get("ko") or "", kv[1][0].get("match") or "")):
        p0 = group[0]
        match = p0.get("match") or "Match"
        home, away = split_match(match)
        league = p0.get("league") or ""
        eid = p0.get("eventId") or ""
        sl = slug(match)
        if eid:
            # keep stable unique slug
            short = re.sub(r"\D", "", eid)[-8:] or slug(eid, 16)
            sl = f"{sl}-{short}" if short not in sl else sl
        path = f"match/{sl}.html"
        url = f"{BASE}/{path}"
        ko = " ".join(filter(None, [p0.get("date") or day, p0.get("ko")]))
        desc = f"{match} prediction and booking pick"
        if league:
            desc += f" · {league}"
        if p0.get("selection"):
            desc += f" — {p0.get('market') or 'Pick'}: {p0.get('selection')}"
            if p0.get("odds"):
                desc += f" @{odds(p0.get('odds'))}"
        desc += ". Free on Predict2u."
        title = f"{match} prediction · Predict2u"

        picks_html = []
        for p in group:
            res = (p.get("result") or "pending").lower()
            pill = f'<span class="pill pill-{esc(res)}">{esc(res)}</span>'
            picks_html.append(
                f'<div class="card"><div class="sel"><span>{esc(p.get("selection") or "—")}<small style="display:block;font-weight:600;color:var(--mut)">{esc(p.get("market") or "")}</small></span><b>@{esc(odds(p.get("odds")))}</b></div>'
                f'<dl class="stats"><div><dt>Confidence</dt><dd>{esc(rate(p.get("confidence")))}</dd></div>'
                f'<div><dt>League fav. rate</dt><dd>{esc(rate(p.get("leagueFavRate")))}</dd></div>'
                f'<div><dt>Sample</dt><dd>{esc(p.get("sample") if p.get("sample") is not None else "—")}</dd></div>'
                f'<div><dt>Result</dt><dd>{pill}</dd></div></dl>'
                + (f'<p class="case">{esc(p.get("case"))}</p>' if p.get("case") else "")
                + "</div>"
            )

        lg_sl = slug(league) if league else ""
        lg_link = f'<a href="../league/{esc(lg_sl)}.html">{esc(league)}</a>' if league else "—"
        body = f'''
  <nav class="crumb"><a href="../index.html">Home</a> · <a href="../matches.html">Matches</a> · {lg_link}</nav>
  <section class="hero">
    <span class="kicker">MATCH PICK</span>
    <h1>{esc(match)}</h1>
    <p class="lead">{esc(league)} · Kick-off {esc(ko or "TBD")}</p>
    <p class="meta">Updated {esc(updated or day)}</p>
    <div class="links">
      <a href="../index.html">← Today’s picks</a>
      <a href="../bankers.html">Booking codes</a>
      {"<a href=\"../league/"+esc(lg_sl)+".html\">League page</a>" if league else ""}
    </div>
  </section>
  <h2 style="font-size:1rem;margin:14px 0 6px">Our pick{"s" if len(group)>1 else ""}</h2>
  {''.join(picks_html)}
'''
        jsonld = {
            "@context": "https://schema.org",
            "@type": "SportsEvent",
            "name": match,
            "startDate": f"{p0.get('date') or day}T{(p0.get('ko') or '00:00')}:00Z" if (p0.get("date") or day) else None,
            "homeTeam": {"@type": "SportsTeam", "name": home},
            "awayTeam": {"@type": "SportsTeam", "name": away},
            "location": {"@type": "VirtualLocation", "url": url},
            "organizer": {"@type": "Organization", "name": "Predict2u", "url": BASE},
            "url": url,
            "description": desc,
        }
        if league:
            jsonld["sport"] = "Soccer"
            jsonld["superEvent"] = {"@type": "SportsOrganization", "name": league}

        (match_dir / f"{sl}.html").write_text(page(title, desc[:160], url, body, jsonld), encoding="utf-8")
        match_urls.append((path, day))
        match_index_rows.append((ko or "", match, league, path, p0.get("selection"), p0.get("odds")))

    for league, group in sorted(by_league.items(), key=lambda kv: kv[0].lower()):
        sl = slug(league)
        path = f"league/{sl}.html"
        url = f"{BASE}/{path}"
        # unique matches in league
        seen = set()
        rows = []
        for p in sorted(group, key=lambda x: (x.get("ko") or "", x.get("match") or "")):
            m = p.get("match") or ""
            if m in seen:
                continue
            seen.add(m)
            # find match page slug
            eid = p.get("eventId") or ""
            msl = slug(m)
            if eid:
                short = re.sub(r"\D", "", eid)[-8:] or slug(eid, 16)
                msl = f"{msl}-{short}" if short not in msl else msl
            rows.append(
                f'<a class="row" href="../match/{esc(msl)}.html"><b>{esc(m)}</b>'
                f'<small>{esc(p.get("date") or day)} {esc(p.get("ko") or "")} · {esc(p.get("selection") or "pick")} @{esc(odds(p.get("odds")))}</small></a>'
            )
        # league stats from first pick / leagues blob
        fav = next((p.get("leagueFavRate") for p in group if p.get("leagueFavRate") is not None), None)
        sample = next((p.get("sample") for p in group if p.get("sample") is not None), None)
        title = f"{league} predictions · Predict2u"
        desc = f"Today’s Predict2u picks in {league}: {len(seen)} match{'es' if len(seen)!=1 else ''}"
        if fav is not None:
            desc += f". League favourite rate {rate(fav)}"
            if sample is not None:
                desc += f" over {sample} games"
        desc += ". Free booking codes."
        body = f'''
  <nav class="crumb"><a href="../index.html">Home</a> · <a href="../leagues.html">Leagues</a> · <span>{esc(league)}</span></nav>
  <section class="hero">
    <span class="kicker">LEAGUE</span>
    <h1>{esc(league)}</h1>
    <p class="lead">{esc(len(seen))} match{"es" if len(seen)!=1 else ""} on the card · {esc(day)}</p>
    <dl class="stats" style="margin-top:12px">
      <div><dt>Favourite rate</dt><dd>{esc(rate(fav))}</dd></div>
      <div><dt>Sample</dt><dd>{esc(sample if sample is not None else "—")}</dd></div>
      <div><dt>Picks today</dt><dd>{esc(len(group))}</dd></div>
      <div><dt>Updated</dt><dd>{esc((updated or day)[:16])}</dd></div>
    </dl>
    <div class="links">
      <a href="../index.html">← Today’s picks</a>
      <a href="../matches.html">All matches</a>
      <a href="../bankers.html">Booking codes</a>
    </div>
  </section>
  <h2 style="font-size:1rem;margin:14px 0 6px">Matches</h2>
  <div class="list">{''.join(rows) or '<p class="meta">No matches listed.</p>'}</div>
'''
        jsonld = {
            "@context": "https://schema.org",
            "@type": "CollectionPage",
            "name": title,
            "description": desc,
            "url": url,
            "isPartOf": {"@type": "WebSite", "name": "Predict2u", "url": BASE},
        }
        (league_dir / f"{sl}.html").write_text(page(title, desc[:160], url, body, jsonld), encoding="utf-8")
        league_urls.append((path, day))

    # Hub: matches.html
    rows_h = []
    for ko, match, league, path, sel, od in sorted(match_index_rows, key=lambda r: (r[0], r[1])):
        rows_h.append(
            f'<a class="row" href="{esc(path)}"><b>{esc(match)}</b>'
            f'<small>{esc(ko)} · {esc(league)} · {esc(sel or "pick")} @{esc(odds(od))}</small></a>'
        )
    matches_body = f'''
  <nav class="crumb"><a href="index.html">Home</a> · <span>Matches</span></nav>
  <section class="hero">
    <span class="kicker">SEO · MATCHES</span>
    <h1>Today’s match picks</h1>
    <p class="lead">{esc(len(match_urls))} matches on {esc(day)}. Open a match for the full pick, odds and rationale.</p>
    <div class="links"><a href="index.html">← Home</a><a href="leagues.html">Leagues</a><a href="bankers.html">Codes</a></div>
  </section>
  <div class="list">{''.join(rows_h)}</div>
'''
    (REPO / "matches.html").write_text(
        hub_page("Today’s match predictions · Predict2u",
                 f"All {len(match_urls)} Predict2u match picks for {day}, with odds and booking codes.",
                 f"{BASE}/matches.html", matches_body),
        encoding="utf-8",
    )

    # Hub: leagues.html
    lg_rows = []
    for league in sorted(by_league.keys(), key=str.lower):
        sl = slug(league)
        n = len({p.get("match") for p in by_league[league]})
        lg_rows.append(
            f'<a class="row" href="league/{esc(sl)}.html"><b>{esc(league)}</b><small>{n} match{"es" if n!=1 else ""} today</small></a>'
        )
    leagues_body = f'''
  <nav class="crumb"><a href="index.html">Home</a> · <span>Leagues</span></nav>
  <section class="hero">
    <span class="kicker">SEO · LEAGUES</span>
    <h1>Leagues on today’s card</h1>
    <p class="lead">{esc(len(league_urls))} competitions with Predict2u picks for {esc(day)}.</p>
    <div class="links"><a href="index.html">← Home</a><a href="matches.html">Matches</a><a href="bankers.html">Codes</a></div>
  </section>
  <div class="list">{''.join(lg_rows)}</div>
'''
    (REPO / "leagues.html").write_text(
        hub_page("Football league predictions · Predict2u",
                 f"Browse {len(league_urls)} leagues with today’s Predict2u picks and booking codes.",
                 f"{BASE}/leagues.html", leagues_body),
        encoding="utf-8",
    )

    # Sitemap
    static = [
        ("", "1.0", "hourly"),
        ("index.html", "1.0", "hourly"),
        ("bankers.html", "0.9", "hourly"),
        ("hot-picks.html", "0.9", "hourly"),
        ("record.html", "0.8", "daily"),
        ("staked.html", "0.7", "daily"),
        ("news.html", "0.9", "hourly"),
        ("matches.html", "0.9", "hourly"),
        ("leagues.html", "0.9", "hourly"),
        ("engines.html", "0.5", "weekly"),
        ("proof.html", "0.5", "weekly"),
        ("scorecards.html", "0.5", "weekly"),
        ("league-dna.html", "0.5", "weekly"),
        ("community.html", "0.4", "weekly"),
        ("high-odds/", "0.7", "daily"),
        ("trust.html", "0.4", "monthly"),
        ("responsible-gambling.html", "0.6", "monthly"),
        ("terms.html", "0.3", "monthly"),
        ("privacy.html", "0.3", "monthly"),
        ("disclaimer.html", "0.3", "monthly"),
    ]
    today = dt.date.today().isoformat()
    urls_xml = []
    seen_loc = set()
    def add(loc_path, lastmod, freq, pri):
        loc = f"{BASE}/{loc_path}" if loc_path else f"{BASE}/"
        if loc in seen_loc:
            return
        seen_loc.add(loc)
        urls_xml.append(
            f"  <url><loc>{esc(loc)}</loc><lastmod>{esc(lastmod)}</lastmod>"
            f"<changefreq>{esc(freq)}</changefreq><priority>{esc(pri)}</priority></url>"
        )
    for path, pri, freq in static:
        add(path, today, freq, pri)
    for path, d in match_urls:
        add(path, d or today, "daily", "0.8")
    for path, d in league_urls:
        add(path, d or today, "daily", "0.7")

    (REPO / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(urls_xml)
        + "\n</urlset>\n",
        encoding="utf-8",
    )

    # robots — ensure sitemap line
    robots = REPO / "robots.txt"
    txt = robots.read_text() if robots.exists() else "User-agent: *\nAllow: /\n"
    if "Sitemap:" not in txt:
        txt = txt.rstrip() + f"\n\nSitemap: {BASE}/sitemap.xml\n"
    robots.write_text(txt, encoding="utf-8")

    # SEO index for clients / debugging
    index = {
        "DATA_UPDATED": updated or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "date": day,
        "matches": len(match_urls),
        "leagues": len(league_urls),
        "matchPages": [u[0] for u in match_urls],
        "leaguePages": [u[0] for u in league_urls],
    }
    (REPO / "seo-pages.json").write_text(json.dumps(index, separators=(",", ":")), encoding="utf-8")
    print(f"seo pages: {len(match_urls)} matches, {len(league_urls)} leagues, sitemap={len(urls_xml)} urls")

if __name__ == "__main__":
    main()
