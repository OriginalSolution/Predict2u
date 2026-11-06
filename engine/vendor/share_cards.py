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
FD = "/usr/share/fonts/truetype/sand-box/google/Poppins/Poppins-"
def F(w, s): return ImageFont.truetype(FD + w + ".ttf", s)
W, H = 1080, 1350
NAVY, NAVY2, GREEN, YEL, WHITE, MUTED = (8, 20, 36), (13, 34, 58), (120, 190, 32), (255, 204, 0), (255, 255, 255), (160, 178, 200)
BOOKS = [("sportybet", "SportyBet", (226, 0, 26), WHITE), ("msport", "MSport", (255, 204, 0), (20, 20, 20)),
         ("betika", "Betika", (0, 160, 70), WHITE), ("footballcom", "football.com", (40, 36, 80), WHITE),
         ("betpawa", "Betpawa", (120, 190, 32), (10, 20, 10)), ("betway", "Betway", (10, 10, 10), WHITE)]
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
    e = html.escape; url = f"https://predict2u.com/s/{sc}/"; img = f"https://predict2u.com/share/{sc}.png"
    t = f"{title(s, src)} @{float(odds or 0):.2f} — Predict2u.com"
    desc = "Free booking code: " + " · ".join(f"{nm} {c[k]}" for k, nm, *_ in BOOKS if k in c) + ". 18+ Bet responsibly."
    tgt = f"/high-odds/#{sc}" if src == "high" else f"/{PAGES.get(src, '')}?code={sc}#slip-{sc}"
    rows = "".join(f'<li><b>{e(nm)}</b> <code>{e(c[k])}</code></li>' for k, nm, *_ in BOOKS if k in c)
    h = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(t)}</title><meta name="description" content="{e(desc)}"><link rel="canonical" href="{url}">
<meta property="og:type" content="website"><meta property="og:site_name" content="Predict2u.com"><meta property="og:url" content="{url}">
<meta property="og:title" content="{e(t)}"><meta property="og:description" content="{e(desc)}">
<meta property="og:image" content="{img}"><meta property="og:image:secure_url" content="{img}"><meta property="og:image:type" content="image/png"><meta property="og:image:width" content="1080"><meta property="og:image:height" content="1350">
<meta name="twitter:card" content="summary_large_image"><meta name="twitter:image" content="{img}"><meta name="robots" content="noindex,follow">
<style>body{{margin:0;background:#081424;color:#fff;font-family:system-ui,sans-serif;text-align:center;padding:16px}}img{{max-width:100%;width:420px;border-radius:16px}}a.b{{display:inline-block;margin:14px 0;padding:12px 22px;border-radius:999px;background:#78be20;color:#081424;font-weight:800;text-decoration:none}}ul{{list-style:none;padding:0}}code{{color:#ffcc00;font-size:1.1em}}</style></head>
<body><a class="b" href="{e(tgt)}">Open this slip on Predict2u.com</a><ul>{rows}</ul><img src="/share/{sc}.png" alt="{e(t)}"><p><small>18+ Bet responsibly.</small></p>
<script src="/p2u-live-track-v335.js?v=335" defer></script><script>setTimeout(function(){{location.replace({json.dumps(tgt)})}},2500)</script></body></html>"""
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
    made = {p for p in made if p}
    for p in glob.glob(os.path.join(OUT, "*.png")):  # prune old unreferenced cards
        if p not in made: os.remove(p)
    keep = {os.path.basename(p)[:-4] for p in made}
    for d in glob.glob(os.path.join(SDIR, "*")):
        if os.path.basename(d) not in keep: shutil.rmtree(d, ignore_errors=True)
    print("share cards", len(made))
main()
