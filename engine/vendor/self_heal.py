#!/usr/bin/env python3
"""Auto-fix common Site Quality / publish failures without a bot.

Fixes (idempotent):
  1. BUILD_VERSION.txt vs sw.js VERSION / CACHE_VERSION mismatch → sync to max
  2. HTML ?v=N cache params behind BUILD_VERSION → bump to current
  3. Missing /s/<code>/ pages for live slips → rebuild share_cards
  4. Broken p2u-code-guard script hrefs → point at existing guard file
  5. Invalid live JSON (home-picks, high_odds, hot-picks, picks) → restore from git HEAD
Exits 0 if clean or fixed; prints JSON summary. Does not push (workflow commits).
"""
from __future__ import annotations
import json, os, re, subprocess, sys
from pathlib import Path

REPO = Path(sys.argv[1] if len(sys.argv) > 1 else os.environ.get("REPO_DIR", ".")).resolve()
os.chdir(REPO)
report = {"fixed": [], "ok": [], "failed": []}


def sh(*args, check=False):
    return subprocess.run(args, capture_output=True, text=True, cwd=REPO)


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="replace") if p.exists() else ""


def write(p: Path, text: str):
    p.write_text(text, encoding="utf-8")


def ver_num(v: str) -> int:
    m = re.search(r"v(\d+)", v or "")
    return int(m.group(1)) if m else 0


# --- 1. BUILD_VERSION ↔ sw.js ---
bv_path = REPO / "BUILD_VERSION.txt"
sw_path = REPO / "sw.js"
bv = (read(bv_path).strip() or "v0")
sw = read(sw_path)
sw_ver = re.search(r"VERSION=['\"](v\d+)['\"]", sw)
sw_v = sw_ver.group(1) if sw_ver else "v0"
target = f"v{max(ver_num(bv), ver_num(sw_v), 360)}"
if bv != target or sw_v != target or f"predict2u-{target}" not in sw:
    write(bv_path, target + "\n")
    sw2 = sw
    sw2 = re.sub(r"VERSION=['\"]v\d+['\"]", f"VERSION='{target}'", sw2)
    sw2 = re.sub(r"predict2u-v\d+", f"predict2u-{target}", sw2)
    sw2 = re.sub(r"service worker v\d+", f"service worker {target}", sw2, count=1)
    sw2 = re.sub(r"predict2u-runtime-v\d+", f"predict2u-runtime-{target}", sw2)
    write(sw_path, sw2)
    report["fixed"].append(f"version→{target} (was BUILD={bv} sw={sw_v})")
else:
    report["ok"].append(f"version {target}")

# --- 2. HTML ?v= params ---
n = ver_num(target)
html_fixed = 0
for html in list(REPO.glob("*.html")) + list((REPO / "high-odds").glob("*.html") if (REPO / "high-odds").exists() else []):
    t = read(html)
    t2 = re.sub(r"(\?v=)(\d+)", lambda m: m.group(1) + str(n) if int(m.group(2)) < n else m.group(0), t)
    # also bare v359 in script query without catching unrelated
    if t2 != t:
        write(html, t2); html_fixed += 1
if html_fixed:
    report["fixed"].append(f"html ?v= bumped in {html_fixed} files")
else:
    report["ok"].append("html cache params")

# --- 3. code-guard script refs ---
guards = sorted(REPO.glob("p2u-code-guard-v*.js"))
guard = guards[-1].name if guards else None
if guard:
    gfix = 0
    for html in list(REPO.glob("*.html")) + list((REPO / "high-odds").glob("*.html") if (REPO / "high-odds").exists() else []):
        t = read(html)
        t2 = re.sub(r"p2u-code-guard-v\d+\.js", guard, t)
        if t2 != t:
            write(html, t2); gfix += 1
    if gfix:
        report["fixed"].append(f"code-guard → {guard} in {gfix} files")
    else:
        report["ok"].append(f"code-guard {guard}")
else:
    report["failed"].append("no p2u-code-guard-v*.js found")

# --- 4. Live JSON validity ---
LIVE = ["home-picks.json", "high_odds.json", "hot-picks.json", "picks.json", "record.json"]
for name in LIVE:
    path = REPO / name
    if not path.exists():
        continue
    try:
        json.loads(read(path))
        report["ok"].append(f"json:{name}")
    except Exception as e:
        r = sh("git", "show", f"HEAD:{name}")
        if r.returncode == 0 and r.stdout.strip():
            try:
                json.loads(r.stdout)
                write(path, r.stdout)
                report["fixed"].append(f"restored {name} from git HEAD ({e})")
            except Exception as e2:
                report["failed"].append(f"{name} invalid and HEAD bad: {e2}")
        else:
            report["failed"].append(f"{name} invalid: {e}")

# --- 5. Missing /s/ pages for live SportyBet codes ---
codes = set()
for name in ("high_odds.json", "home-picks.json", "hot-picks.json", "picks.json"):
    try:
        d = json.loads(read(REPO / name))
    except Exception:
        continue
    slips = list(d.get("slips") or [])
    if name == "high_odds.json":
        slips += list(d.get("history") or [])[:30]
    for s in slips:
        c = s.get("code") or (s.get("codes") or {}).get("sportybet")
        if isinstance(c, list):
            c = (c[0].get("code") if c and isinstance(c[0], dict) else c[0]) if c else None
        if isinstance(c, dict):
            c = c.get("code")
        if c and re.fullmatch(r"[A-Za-z0-9]{4,16}", str(c)):
            codes.add(str(c))
missing = [c for c in sorted(codes) if not (REPO / "s" / c / "index.html").exists()]
if missing:
    r = sh(sys.executable, str(REPO / "engine" / "vendor" / "share_cards.py"), str(REPO))
    still = [c for c in missing if not (REPO / "s" / c / "index.html").exists()]
    if len(still) < len(missing):
        report["fixed"].append(f"share_cards rebuilt; still missing {still[:8]}")
    else:
        report["failed"].append(f"share_cards did not create {still[:8]} (exit {r.returncode}): {(r.stderr or r.stdout)[:200]}")
else:
    report["ok"].append(f"share pages for {len(codes)} codes")

print(json.dumps(report, indent=2))
sys.exit(1 if report["failed"] and not report["fixed"] else 0)
