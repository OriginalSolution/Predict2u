#!/usr/bin/env python3
"""Per-slip 1080x1350 share cards -> <repo>/share/<SPORTYCODE>.png"""
import json, os, sys, datetime as dt, glob, time, html, shutil
try:
    import qrcode
except Exception: qrcode = None
from PIL import Image, ImageDraw, ImageFont, ImageFilter
REPO = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else "/workspace/Predict2u"
OUT = os.path.join(REPO, "share"); os.makedirs(OUT, exist_ok=True)
SDIR = os.path.join(REPO, "s"); os.makedirs(SDIR, exist_ok=True)
PAGES = {"home": "", "bankers": "bankers.html", "hot": "hot-picks.html", "high": "high-odds/"}
def _font_base():
    for cand in (
        ("/usr/share/fonts/truetype/sand-box/google/Poppins/Poppins-", "-Bold.ttf"),
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans", "-Bold.ttf"),
        ("/usr/share/fonts/truetype/liberation/LiberationSans", "-Bold.ttf"),
    ):
        try:
            ImageFont.truetype(cand[0] + cand[1], 20); return cand[0]
        except Exception:
            continue
    return None
FD = _font_base()
def F(w, s):
    if not FD:
        return ImageFont.load_default()
    names = [w, "Bold" if any(x in w for x in ("Bold", "Extra")) else "Regular", "Bold", "Regular"]
    for name in names:
        for path in (f"{FD}-{name}.ttf" if not FD.endswith("-") else f"{FD}{name}.ttf", f"{FD}{name}.ttf", f"{FD}.ttf"):
            try: return ImageFont.truetype(path, s)
            except Exception: continue
    return ImageFont.load_default()
W, H = 1080, 1350
NAVY, NAVY2, GREEN, YEL, WHITE, MUTED = (8, 20, 36), (13, 34, 58), (120, 190, 32), (255, 204, 0), (255, 255, 255), (160, 178, 200)
BOOKS = [("sportybet", "SportyBet", (200, 16, 30), WHITE), ("msport", "MSport", (255, 211, 37), (17, 17, 17)),
         ("betika", "Betika", (0, 129, 63), WHITE), ("footballcom", "football.com", (40, 36, 80), WHITE),
         ("betpawa", "Betpawa", (120, 190, 32), (17, 17, 17)), ("betway", "Betway", (11, 11, 11), WHITE)]
FORCE = "--force" in sys.argv
MARK = Image.open(os.path.join(REPO, "predict2u-mark.png")).convert("RGBA")

def code_of(v):
    if isinstance(v, list): v = v[0] if v else None
    if isinstance(v, dict): v = v.get("code")
    return v
def codes(s):
    c = {k: code_of(v) for k, v in (s.get("codes") or {}).items()}
    if not c.get("sportybet") and s.get("code"): c["sportybet"] = s["code"]
    return {k: v for k, v in c.items() if v}
def category(s, src):
    n = (s.get("name") or s.get("label") or "").lower(); r = (s.get("risk") or "").lower()
    if src == "high": return "High"
    if src == "hot": return "Hot"
    if r == "safe" or "safe" in n: return "Safe"
    if r == "medium" or "medium" in n: return "Medium"
    return "Banker"
def title(s, src):
    n = s.get("name") or s.get("label") or "Slip"
    if src == "hot": return n.replace("Hot by market: ", "Hot: ").replace("Hot team: ", "Hot: ")
    c = category(s, src)
    return {"Safe": "Safe slip", "Medium": "Medium slip"}.get(c, n.split(":")[0] if n.lower().startswith("main banker") else n.split(" (")[0])

def fit(d, text, weight, size, maxw):
    while size > 20 and d.textlength(text, font=F(weight, size)) > maxw: size -= 2
    return F(weight, size)

def card(s, src, day):
    c = codes(s); sc = c.get("sportybet") or next(iter(c.values()), None)
    if not sc or str(sc).startswith("P2ULOCK-"): return None  # premium slip: no public card
    p = os.path.join(OUT, f"{sc}.png")
    odds = (s.get("bookOdds") or {}).get("sportybet") or s.get("totalOdds") or s.get("odds") or 0
    page(s, src, sc, c, odds)
    if os.path.exists(p) and not FORCE: os.utime(p); return p
    odds = (s.get("bookOdds") or {}).get("sportybet") or s.get("totalOdds") or s.get("odds") or 0
    legs = s.get("legs"); legs = len(legs) if isinstance(legs, list) else (legs or s.get("picks") or 0)
    legs = (s.get("bookPicks") or {}).get("sportybet") or legs
    im = Image.new("RGB", (W, H), NAVY); d = ImageDraw.Draw(im)
    # gradient
    for y in range(H):
        t = y / H; d.line([(0, y), (W, y)], fill=tuple(int(NAVY2[i] * (1 - t) + NAVY[i] * t) for i in range(3)))
    # diagonal stripes top-right
    st = Image.new("RGBA", (W, H), (0, 0, 0, 0)); sd = ImageDraw.Draw(st)
    for i, (col, a) in enumerate([(GREEN, 70), (YEL, 45), (GREEN, 40), (GREEN, 25), (YEL, 20)]):
        x = 560 + i * 120
        sd.polygon([(x, -50), (x + 60, -50), (x + 60 + 700, 900), (x + 700, 900)], fill=col + (a,))
    st = st.filter(ImageFilter.GaussianBlur(2)); im.paste(st, (0, 0), st); d = ImageDraw.Draw(im)
    M = 60
    d.rounded_rectangle([M - 20, 40, W - M + 20, H - 40], 36, outline=(40, 62, 90), width=2)
    # logo
    lg = MARK.copy(); lg.thumbnail((96, 96)); im.paste(lg, (M + 10, 80), lg)
    d.text((M + 120, 92), "predict2u", font=F("ExtraBold", 50), fill=WHITE)
    d.text((M + 120 + d.textlength("predict2u", font=F("ExtraBold", 50)), 92), ".com", font=F("ExtraBold", 50), fill=GREEN)
    # pill
    pill = "HIGH RISK · STAKE SMALL" if src == "high" else "FREE BOOKING CODE" if src != "hot" else "FREE HOT PICKS CODE"
    pf = F("Bold", 30); pw = d.textlength(pill, font=pf)
    d.rounded_rectangle([M, 210, M + pw + 50, 266], 28, fill=(40, 60, 20), outline=GREEN, width=3)
    d.text((M + 25, 216), pill, font=pf, fill=(200, 240, 140))
    tt = title(s, src); d.text((M, 285), tt, font=fit(d, tt, "ExtraBold", 84, W - 2 * M), fill=WHITE)
    # code box
    y0 = 420
    d.rounded_rectangle([M, y0, W - M, y0 + 225], 30, fill=(6, 14, 26), outline=(50, 74, 104), width=2)
    d.text((M + 40, y0 + 30), "BOOKING CODE · SPORTYBET", font=F("SemiBold", 28), fill=MUTED)
    cf = fit(d, sc, "ExtraBold", 118, W - 2 * M - 80)
    d.text((M + 36, y0 + 62), sc, font=cf, fill=WHITE)
    d.rounded_rectangle([M + 40, y0 + 192, M + 40 + max(260, int(d.textlength(sc, font=cf) * .8)), y0 + 203], 6, fill=YEL)
    # tiles
    when = s.get("date") or day
    dd = None
    try:
        dd = dt.date.fromisoformat(when[:10]); td = dt.date.fromisoformat(day)
        avail = "Today" if dd == td else ("Tomorrow" if (dd - td).days == 1 else dd.strftime("%d %b"))
    except Exception: avail = "Today"
    tiles = [("TOTAL ODDS", f"{float(odds):,.2f}"), ("SELECTIONS", str(legs)), ("CATEGORY", category(s, src)), ("DATE", dd.strftime("%a %d %b") if dd else "Today")]
    tw = (W - 2 * M - 30) // 2
    for i, (k, v) in enumerate(tiles):
        x = M + (i % 2) * (tw + 30); y = 670 + (i // 2) * 130
        d.rounded_rectangle([x, y, x + tw, y + 115], 24, fill=(18, 40, 66), outline=(50, 74, 104), width=2)
        d.text((x + 30, y + 16), k, font=F("SemiBold", 26), fill=MUTED)
        d.text((x + 30, y + 44), v, font=fit(d, v, "Bold", 52, tw - 60), fill=YEL if i == 0 else WHITE)
    # per-book chips
    y = 935; x = M; f = F("Bold", 24)
    for k, nm, bg, fg in BOOKS:
        if k not in c: continue
        t = f"{nm} {c[k]}"; w = d.textlength(t, font=f) + 30
        if x + w > W - M: x = M; y += 52
        d.rounded_rectangle([x, y, x + w, y + 42], 21, fill=bg); d.text((x + 15, y + 5), t, font=f, fill=fg); x += w + 10
    y += 58
    short = f"predict2u.com/s/{sc}"
    if qrcode:
        q = qrcode.QRCode(border=1, box_size=6); q.add_data("https://" + short + "/"); q.make(fit=True)
        qi = q.make_image(fill_color="black", back_color="white").convert("RGB").resize((150, 150), Image.NEAREST)
        im.paste(qi, (W - M - 150, y - 4)); d = ImageDraw.Draw(im)
    d.text((M, y - 4), "Open this slip:", font=F("Regular", 26), fill=MUTED)
    d.text((M, y + 28), short, font=fit(d, short, "ExtraBold", 46, W - 2 * M - 180), fill=YEL)
    d.text((M, y + 92), "Scan or tap the link to copy all codes", font=F("Regular", 24), fill=MUTED)
    fy = H - 165
    d.rounded_rectangle([M, fy, W - M, fy + 110], 26, fill=(30, 52, 22), outline=GREEN, width=3)
    d.text((M + 34, fy + 10), "I found this free on predict2u.com", font=F("Bold", 38), fill=WHITE)
    d.text((M + 34, fy + 60), "Free daily booking codes  •  18+  •  Verify before use", font=F("Medium", 26), fill=(200, 230, 170))
    im.quantize(colors=256, method=Image.Quantize.FASTOCTREE).save(p, optimize=True); return p

def page(s, src, sc, c, odds):
    e = lambda x: html.escape(str(x if x is not None else "")); url = f"https://predict2u.com/s/{sc}/"; img = f"https://predict2u.com/share/{sc}.png"
    t = f"{title(s, src)} @{float(odds or 0):.2f} — Predict2u.com"
    desc = "Free booking code: " + " · ".join(f"{nm} {c[k]}" for k, nm, *_ in BOOKS if k in c) + ". 18+ Bet responsibly."
    tgt = f"/high-odds/#{sc}" if src == "high" else f"/{PAGES.get(src, '')}?code={sc}#slip-{sc}"
    rows = "".join(f'<li><b>{e(nm)}</b> <code>{e(c[k])}</code></li>' for k, nm, *_ in BOOKS if k in c)
    if src == "manual":  # unlisted shared slip: per-book picks + odds, no redirect into site listings
        def _m(k):
            v = (s.get("codes") or {}).get(k); v = v[0] if isinstance(v, list) and v else v
            return v if isinstance(v, dict) else {}
        rows = "".join(f'<li><b>{e(nm)}</b> <code>{e(c[k])}</code> <small>{e(_m(k).get("legs"))} picks · @{e(_m(k).get("totalOdds"))}</small></li>' for k, nm, *_ in BOOKS if k in c)
        tgt = "/"
    P = s.get("parts") or []
    if P:  # >50-leg code: bookmakers take max 50 picks per code -> lead with the parts
        pr = ""
        for i, pt in enumerate(P):
            li = "".join(f'<li><b>{e(nm)}</b> <a href="/s/{e(code_of(pt["codes"][k]))}/"><code>{e(code_of(pt["codes"][k]))}</code></a> <small>{e((pt["codes"][k][0] or {}).get("legs"))} picks · @{e((pt["codes"][k][0] or {}).get("totalOdds"))}</small></li>' for k, nm, *_ in BOOKS if code_of((pt.get("codes") or {}).get(k)))
            if li: pr += f'<h3>Part {i + 1} of {len(P)} · {e(pt.get("legs"))} picks</h3><ul>{li}</ul>'
        rows = f'<p><b style="background:#b91c1c;padding:3px 10px;border-radius:999px">HIGH RISK</b></p><p>Bookmakers take up to 50 picks per code, so this slip is split into {len(P)} parts:</p>{pr}<p><small>Full {e(sc)} code ({e(s.get("legs") if not isinstance(s.get("legs"), list) else len(s["legs"]))} picks):</small></p><ul>{rows}</ul>'
        desc = "HIGH RISK. Split into parts (max 50 picks per code): " + " | ".join(f"Part {i + 1}: " + " · ".join(f"{nm} {code_of(pt['codes'][k])}" for k, nm, *_ in BOOKS if code_of((pt.get('codes') or {}).get(k))) for i, pt in enumerate(P)) + ". 18+ Bet responsibly."
    elif s.get("partOf"):
        rows = f'<p><b style="background:#b91c1c;padding:3px 10px;border-radius:999px">HIGH RISK</b></p><p>{e(s.get("name"))}. Full slip: <a href="/s/{e(s["partOf"])}/">{e(s["partOf"])}</a></p><ul>{rows}</ul>'
    h = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(t)}</title><meta name="description" content="{e(desc)}"><link rel="canonical" href="{url}">
<meta property="og:type" content="website"><meta property="og:site_name" content="Predict2u.com"><meta property="og:url" content="{url}">
<meta property="og:title" content="{e(t)}"><meta property="og:description" content="{e(desc)}">
<meta property="og:image" content="{img}"><meta property="og:image:secure_url" content="{img}"><meta property="og:image:type" content="image/png"><meta property="og:image:width" content="1080"><meta property="og:image:height" content="1350">
<meta name="twitter:card" content="summary_large_image"><meta name="twitter:image" content="{img}"><meta name="robots" content="noindex,follow">
<style>body{{margin:0;background:#081424;color:#fff;font-family:system-ui,sans-serif;text-align:center;padding:16px}}img{{max-width:100%;width:420px;border-radius:16px}}a.b{{display:inline-block;margin:14px 0;padding:12px 22px;border-radius:999px;background:#78be20;color:#081424;font-weight:800;text-decoration:none}}ul{{list-style:none;padding:0}}code{{color:#ffcc00;font-size:1.1em}}</style></head>
<body><a class="b" href="{e(tgt)}">Open this slip on Predict2u.com</a><ul>{rows}</ul><img src="/share/{sc}.png" alt="{e(t)}"><p><small>18+ Bet responsibly.</small></p>
<script src="/p2u-live-track-v336.js?v=336" defer></script>{'' if src == 'manual' else '<script>setTimeout(function(){location.replace(' + json.dumps(tgt) + ')},2500)</script>'}</body></html>"""
    d = os.path.join(SDIR, sc); os.makedirs(d, exist_ok=True)
    open(os.path.join(d, "index.html"), "w").write(h)

def main():
    day = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d"); made = []
    def load(n):
        try: return json.load(open(os.path.join(REPO, n)))
        except Exception: return {}
    seen = set()
    for src, n in (("home", "home-picks.json"), ("bankers", "picks.json")):
        for s in load(n).get("slips") or []:
            k = codes(s).get("sportybet")
            if k in seen: continue  # home-picks keeps original code case
            seen.add(k); made.append(card(s, src, day))
    h = load("hot-picks.json")
    for k in ("slips", "byMarket", "byTeam"):
        for s in h.get(k) or []: made.append(card(s, "hot", day))
    h = load("high_odds.json")
    for k in ("slips", "history"):
        for s in h.get(k) or []:
            sc = codes(s).get("sportybet")
            if sc in seen: continue
            seen.add(sc); made.append(card(s, "high", day))
    def parts_of(s, src):
        for i, pt in enumerate(s.get("parts") or []):
            pc = {k: v for k, v in (pt.get("codes") or {}).items() if code_of(v)}
            if not pc: continue
            first = pc.get("sportybet") or next(iter(pc.values()))
            ps = dict(name=f"{title(s, src)} · Part {i + 1}/{len(s['parts'])} · HIGH RISK", codes=pc, totalOdds=(first[0] or {}).get("totalOdds"),
                      legs=(first[0] or {}).get("legs"), partOf=codes(s).get("sportybet"), highRisk=True)
            made.append(card(ps, src, day))
            for k, v in pc.items():  # every bookmaker's part code gets its own /s/ link
                sc2 = code_of(v)
                if sc2 and sc2 != code_of(first):
                    made.append(card(dict(ps, codes={k: v}), src, day))
    for n, src in (("home-picks.json", "home"), ("hot-picks.json", "hot"), ("high_odds.json", "high")):
        d = load(n)
        for k in ("slips", "history"):
            for s in d.get(k) or []:
                if s.get("parts"): parts_of(s, src)
    for s in (load(os.path.join("engine", "data", "manual_shares.json")).get("slips") or []):
        made.append(card(s, "manual", day))  # persisted unlisted share pages (never pruned)
    made = {p for p in made if p}
    for p in glob.glob(os.path.join(OUT, "*.png")):  # prune old unreferenced cards
        if p not in made: os.remove(p)
    keep = {os.path.basename(p)[:-4] for p in made}
    for d in glob.glob(os.path.join(SDIR, "*")):
        if os.path.basename(d) not in keep: shutil.rmtree(d, ignore_errors=True)
    print("share cards", len(made))
main()
