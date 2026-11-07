#!/usr/bin/env python3
"""Daily SEO landing pages: /<bookmaker>-booking-codes-today/ from home-picks.json. Free (unlocked) slips only."""
import json, sys, datetime as dt, re
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from build_seo_pages import page, esc, odds, BASE
import prune_live as _pl
REPO = Path(sys.argv[1] if len(sys.argv) > 1 else "/workspace/Predict2u")
BOOKS = [("sportybet","SportyBet","sportybet-codes-today"),("betway","Betway","betway-booking-codes-today"),
         ("msport","MSport","msport-booking-codes-today"),("betika","Betika","betika-booking-codes-today"),
         ("betpawa","Betpawa","betpawa-booking-codes-today"),("footballcom","football.com","football-com-booking-codes-today")]
def main():
    d = json.loads((REPO/"home-picks.json").read_text())
    day = d.get("date") or dt.date.today().isoformat()
    nice = dt.date.fromisoformat(day).strftime("%A %d %B %Y")
    slips = [s for s in d.get("slips", []) if _pl.live_slip(s)]
    paths = []
    high = json.loads((REPO/"high_odds.json").read_text()) if (REPO/"high_odds.json").exists() else {"slips":[]}
    for hs in high.get("slips") or []:
        converted = dict(name="HIGH RISK · "+str(hs.get("name") or "High Odds"), totalOdds=hs.get("odds"), legs=hs.get("legs") or [], highRisk=True, highCode=hs.get("code"), codes={}, bookOdds={})
        for bk, c in (hs.get("codes") or {}).items():
            if c.get("code"):
                converted["codes"][bk] = c["code"]
                converted["bookOdds"][bk] = c.get("odds")
                converted.setdefault("bookPicks", {})[bk] = c.get("legs")
        slips.append(converted)
    for key, name, sl in BOOKS:
        url = f"{BASE}/{sl}/"
        cards, items = [], []
        for s in slips:
            code = (s.get("codes") or {}).get(key)
            if not code: continue
            locked = bool(s.get("locked"))
            legs = s.get("legs") or []
            bo = (s.get("bookOdds") or {}).get(key) or s.get("totalOdds")
            nlegs = (s.get("bookPicks") or {}).get(key) or len(legs)
            sname = re.sub(r"\s*\(.*?\)", "", s.get("name",""))
            if locked:
                codehtml = f'<a href="../index.html">🔒 Unlock this code on Predict2u</a>'
            else:
                codehtml = f'<b style="font-size:1.25rem;letter-spacing:.08em">{esc(code)}</b>'
                items.append(code)
            rows = "".join(f'<li>{esc(l.get("match"))} — {esc(l.get("selection"))} @ {odds(l.get("odds"))}</li>' for l in legs[:40])
            cards.append(f'<section class="card"><h2 style="margin:0 0 6px;font-size:1.05rem">{esc(sname)}</h2>'
                         f'<div class="sel"><span>{codehtml}</span><b>{odds(bo)} odds · {nlegs} picks</b></div>'
                         f'<details><summary>See all picks</summary><ul>{rows}</ul></details>'
                         + (f'<p><b>⚠ HIGH RISK — stake small.</b> <a href="../high-odds/#{esc(s.get("highCode"))}">Live progress, all bookmaker codes and sharing →</a></p>' if s.get("highRisk") else '') + '</section>')
        # Publish an explicit empty state rather than leaving yesterday's codes live.
        pending = not cards
        title = f"{name} Booking Codes Today ({dt.date.fromisoformat(day).strftime('%d %b %Y')}) — Predict2u"
        desc = f"Today's free {name} booking codes for {nice}: banker slip, safe and medium slips, with every pick, odds and kick-off. Updated three times daily."
        others = " · ".join(f'<a href="../{o}/">{n}</a>' for k,n,o in BOOKS if o != sl)
        body = (f'<nav class="crumb"><a href="../index.html">Home</a> › {esc(name)} codes today</nav>'
                f'<header class="hero"><span class="kicker">UPDATED {esc(day)}</span><h1>{esc(name)} booking codes today</h1>'
                f'<p class="lead">Free {esc(name)} booking codes for {esc(nice)}. Load a code in the {esc(name)} betslip to get every pick at once.</p></header>'
                + ("".join(cards) if cards else f'<section class="card"><h2 style="margin:0 0 6px;font-size:1.05rem">No current {esc(name)} codes</h2><p>Pending rebooking. Previous codes are no longer published because they are not on the current DC-free card.</p></section>') +
                f'<section class="card"><h2 style="margin:0 0 6px;font-size:1rem">Codes on other bookmakers</h2><p>{others}</p>'
                f'<p><a href="../bankers.html">Today\'s bankers</a> · <a href="../hot-picks.html">Hot Picks</a> · <a href="../matches.html">All matches</a></p></section>')
        ld = {"@context":"https://schema.org","@graph":[
            {"@type":"WebPage","name":title,"url":url,"description":desc,"dateModified":d.get("DATA_UPDATED") or day,"inLanguage":"en"},
            {"@type":"BreadcrumbList","itemListElement":[{"@type":"ListItem","position":1,"name":"Home","item":BASE+"/"},{"@type":"ListItem","position":2,"name":f"{name} codes today","item":url}]}]}
        out = REPO/sl; out.mkdir(exist_ok=True)
        (out/"index.html").write_text(page(title, desc[:160], url, body, ld), encoding="utf-8")
        paths.append(f"/{sl}/")
    sm = REPO/"sitemap.xml"
    if sm.exists():
        x = sm.read_text()
        add = "".join(f"<url><loc>{BASE}{p}</loc><lastmod>{day}</lastmod><changefreq>hourly</changefreq><priority>0.95</priority></url>\n"
                      for p in paths if f"<loc>{BASE}{p}</loc>" not in x)
        sm.write_text(x.replace("</urlset>", add + "</urlset>"))
    print("code pages", paths)
if __name__ == "__main__": main()
