#!/usr/bin/env python3
"""Predict2u engine health check — runs on its own every day (engine-health.yml).

  python -m engine.health preflight   # 18:00: everything below, incl. dry runs of every strategy for tomorrow
  python -m engine.health post        # 23:15 / 07:30: quick check that the night's / morning's codes published

Checks
  code      compile every engine .py, pyflakes "undefined name" (the run.py-style crash), import engine modules,
            engine.check_rules
  registry  every workflow that runs an engine command is discovered automatically; scheduled workflows must
            be on the on-time ticker and enabled
  strategies (preflight) every engine command found in the workflows runs for TOMORROW in a sandbox that
            blocks all write requests (no booking, no Telegram, no email); crash/timeout/insane output = problem
  site      every page returns 200; every data file parses (JSON / JS) and is fresh
  codes     every published, still-live booking code loads on its bookmaker and still has a match to play;
            dead ones go to dead-codes.json, which the site's code guard hides
  actions   ticker alive, last run of every scheduled workflow succeeded and ran on time
Self-heal (--heal): restart the ticker, re-dispatch failed refresh workflows, dispatch a failed booking
workflow only when its codes for the day are missing (its run-once gate still prevents double booking).
Writes engine/data/health/<date>-<mode>.json and health.json; prints a plain summary.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import datetime as dt
import json
import os
import py_compile
import tempfile
_PYC_TMP = tempfile.mkdtemp(prefix='p2u-pyc-')
import re
import shlex
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

REPO = Path(os.environ.get("REPO_DIR") or Path(__file__).resolve().parents[1])
ENGINE = REPO / "engine"
WF_DIR = REPO / ".github" / "workflows"
SITE = os.environ.get("P2U_SITE", "https://predict2u.com").rstrip("/")
GH_REPO = os.environ.get("GITHUB_REPOSITORY", "riddimbossy-prog/Predict2u")
API = os.environ.get("GITHUB_API_URL", "https://api.github.com")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"
NOW = dt.datetime.now(dt.timezone.utc)
TODAY = NOW.date().isoformat()
TOMORROW = (NOW.date() + dt.timedelta(days=1)).isoformat()
BOOKS = ("sportybet", "footballcom", "msport", "betika", "betpawa")

# Workflows GitHub shows as disabled on purpose (their outside service is gone). Anything else disabled is a problem.
KNOWN_DISABLED = {
    "auto-picks-learning.yml", "fixture-snapshot.yml", "future-fixtures.yml", "live-scores.yml", "news-sync.yml",
    "probe-markets.yml", "probe-sot.yml", "settle-slips.yml", "update-data.yml", "update-scores.yml",
}
# Non-booking workflows the health check may simply re-run when their last run failed.
REFRESH = {"sportybet-odds.yml", "engine-refresh.yml", "engine-settle.yml", "engine-self-heal.yml", "daymasters-guard.yml"}
# Engine commands that are not strategies (or need secrets a dry run must not have).
SKIP_CMD = re.compile(r"engine/tests|engine\.check_rules|self_heal\.py|engine\.premium|engine\.health|daymasters_check|pytest")
# Site data files: (path, timestamp key or JS regex, max age hours)
DATA_FILES = [
    ("home-picks.json", "DATA_UPDATED", 30), ("picks.json", "DATA_UPDATED", 30), ("high_odds.json", "updatedAt", 30),
    ("hot-picks.json", "updatedAt", 30), ("record.json", "DATA_UPDATED", 30), ("news-hub.json", "updatedAt", 4),
    ("live-scores.json", "DATA_UPDATED", 4), ("data-meta.json", "generatedAt", 8), ("staked-codes.json", "updatedAt", 30),
    ("fixtures.js", r'FIXTURE_DATA_UPDATED\s*=\s*"([^"]+)"', 8), ("sportybet-odds.js", r'"generatedAt":"([^"]+)"', 8),
    ("current-data.js", r'"generatedAt":"([^"]+)"', 8),
]
CODE_FILES = ("home-picks.json", "high_odds.json", "hot-picks.json", "picks.json")
YOUTH = re.compile(r"\b(U-?1[5-9]|U-?2[0-3]|youth|junior|women|female|ladies|virtual|e-?soccer|srl|simulated)\b", re.I)


class Report:
    def __init__(self, mode):
        self.mode, self.problems, self.warnings, self.passed, self.healed, self.sections = mode, [], [], [], [], {}

    def bad(self, area, msg):
        self.problems.append({"area": area, "msg": msg}); print(f"PROBLEM [{area}] {msg}", flush=True)

    def warn(self, area, msg):
        self.warnings.append({"area": area, "msg": msg}); print(f"warning [{area}] {msg}", flush=True)

    def ok(self, area, msg):
        self.passed.append({"area": area, "msg": msg}); print(f"ok [{area}] {msg}", flush=True)

    def heal(self, msg):
        self.healed.append(msg); print(f"HEALED {msg}", flush=True)


# ---------------------------------------------------------------- helpers
def http(url, method="GET", body=None, headers=None, timeout=25):
    h = {"User-Agent": UA, "Accept": "application/json, text/plain, */*"}
    h.update(headers or {})
    data = json.dumps(body).encode() if body is not None else None
    if data is not None:
        h["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except Exception as e:
        return 0, str(e).encode()


def gh(path, method="GET", body=None):
    tok = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not tok:
        return None
    st, raw = http(API + path, method, body, {"Authorization": f"Bearer {tok}", "Accept": "application/vnd.github+json",
                                              "X-GitHub-Api-Version": "2022-11-28"})
    if st >= 300 or st == 0:
        raise RuntimeError(f"GitHub API {method} {path}: {st} {raw[:200]!r}")
    return json.loads(raw) if raw else {}


def parse_ts(v):
    try:
        s = str(v).strip().replace("Z", "+00:00")
        t = dt.datetime.fromisoformat(s)
        return t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)
    except Exception:
        return None


def ticker_schedule():
    src = (REPO / ".github" / "scripts" / "p2u_ticker.py").read_text()
    return re.findall(r'\("([\w.-]+\.yml)",\s*"([^"]+)",\s*"([^"]+)",\s*"([^"]+)"\)', src)


def load_workflows():
    try:
        import yaml
    except ImportError:
        yaml = None
    out = {}
    for f in sorted(WF_DIR.glob("*.yml")):
        txt = f.read_text()
        info = {"file": f.name, "scheduled": bool(re.search(r"^\s*schedule:", txt, re.M)), "crons": re.findall(r'cron:\s*"([^"]+)"', txt),
                "commands": [], "name": (re.search(r"^name:\s*(.+)$", txt, re.M) or [None, f.name])[1].strip()}
        runs = []
        if yaml:
            try:
                doc = yaml.safe_load(txt) or {}
                for job in (doc.get("jobs") or {}).values():
                    for st in job.get("steps") or []:
                        if isinstance(st, dict) and st.get("run"):
                            runs.append(st["run"])
            except Exception as e:
                info["yamlError"] = str(e)
        else:
            runs = [txt]
        for blk in runs:
            for line in blk.splitlines():
                for m in re.finditer(r"python3?\s+((?:-m\s+engine[\w.]*|engine/[\w/]+\.py)(?:\s+[^|;&#]*)?)", line):
                    cmd = m.group(1).strip()
                    if "$(" in cmd:
                        continue
                    info["commands"].append(cmd)
        out[f.name] = info
    return out


# ---------------------------------------------------------------- 1. code
def check_code(rep):
    errs = []
    for p in sorted(ENGINE.rglob("*.py")):
        if "__pycache__" in p.parts:
            continue
        try:
            py_compile.compile(str(p), doraise=True, cfile=os.path.join(_PYC_TMP, p.name + 'c'))
        except Exception as e:
            errs.append(f"{p.relative_to(REPO)}: {e}")
    for e in errs:
        rep.bad("code", f"does not compile: {e}")
    try:
        r = subprocess.run([sys.executable, "-m", "pyflakes", str(ENGINE)], capture_output=True, text=True, timeout=300)
        und = [l for l in r.stdout.splitlines() if "undefined name" in l]
        for l in und:
            rep.bad("code", f"undefined name (will crash when reached): {l.replace(str(REPO) + '/', '')}")
        if not und:
            rep.ok("code", "no undefined names in engine/ (pyflakes)")
    except FileNotFoundError:
        rep.warn("code", "pyflakes not installed; undefined-name scan skipped")
    mods = ["engine." + p.stem for p in ENGINE.glob("*.py") if p.stem not in ("__init__", "health", "check_rules", "daymasters_check")]
    env = dict(os.environ, P2U_HEALTH_DRY_RUN="1", PYTHONPATH=os.pathsep.join([str(ENGINE / "health_guard"), str(REPO), str(ENGINE), str(ENGINE / "vendor")]))
    for m in sorted(mods):
        r = subprocess.run([sys.executable, "-c", f"import importlib; importlib.import_module({m!r})"], cwd=REPO, env=env,
                           capture_output=True, text=True, timeout=120)
        if r.returncode:
            rep.bad("code", f"import {m} fails: {(r.stderr.strip().splitlines() or ['?'])[-1]}")
    r = subprocess.run([sys.executable, "-m", "engine.check_rules"], cwd=REPO, env=env, capture_output=True, text=True, timeout=300)
    (rep.ok if r.returncode == 0 else rep.bad)("code", "engine.check_rules " + ("passed" if r.returncode == 0 else "failed: " + (r.stdout + r.stderr)[-300:]))
    if not errs:
        rep.ok("code", f"{sum(1 for _ in ENGINE.rglob('*.py'))} engine files compile; {len(mods)} engine modules checked for import")


# ---------------------------------------------------------------- 2. registry
def check_registry(rep, wfs, states):
    on_ticker = {w for w, *_ in ticker_schedule()}
    for f, w in wfs.items():
        if w.get("yamlError"):
            rep.bad("registry", f"{f}: workflow YAML does not parse: {w['yamlError'][:200]}")
        st = states.get(f)
        if not w["scheduled"] or st in ("disabled_manually", "disabled_inactivity") and f in KNOWN_DISABLED:
            continue
        if st and st != "active":
            rep.bad("registry", f"{f} is {st} on GitHub, so it never runs")
            continue
        if f not in on_ticker and f != "engine-ticker.yml":
            rep.bad("registry", f"{f} is scheduled ({', '.join(w['crons'])}) but not on the on-time ticker "
                                f"(.github/scripts/p2u_ticker.py), so it will start hours late or not at all")
    for f, *_ in ticker_schedule():
        if f not in wfs:
            rep.bad("registry", f"ticker lists {f} but that workflow file does not exist")
    n = sum(1 for w in wfs.values() if w["commands"])
    rep.ok("registry", f"{len(wfs)} workflows read, {n} run engine commands, {len(on_ticker)} on the ticker")


# ---------------------------------------------------------------- 3. strategy dry runs
def sandbox_env():
    env = {k: v for k, v in os.environ.items() if not re.search(r"TOKEN|SECRET|KEY|PASSWORD|MAIL_|TELEGRAM|SUPABASE|RESEND|VAPID", k)}
    guard = str(ENGINE / "health_guard")
    env.update({
        "P2U_HEALTH_DRY_RUN": "1", "P2U_DAY": TOMORROW, "P2U_STRICT_GATES": "report",
        "PATH": guard + os.pathsep + env.get("PATH", ""), "P2U_REAL_CURL": subprocess.run(["bash", "-lc", "command -v curl"], capture_output=True, text=True).stdout.strip() or "/usr/bin/curl",
        "PYTHONPATH": os.pathsep.join([guard] + ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else [])),
        "RESEARCH_DIR": str(ENGINE / "data"), "REPO_DIR": str(REPO), "ENGINE_DIR": str(ENGINE), "GITHUB_WORKSPACE": str(REPO),
    })
    return env


def to_dry(cmd):
    cmd = cmd.replace('"$REPO_DIR"', str(REPO)).replace("$REPO_DIR", str(REPO)).replace("${{ github.workspace }}", str(REPO))
    cmd = cmd.replace('"$GITHUB_WORKSPACE"', str(REPO)).replace("$GITHUB_WORKSPACE", str(REPO))
    parts = shlex.split(cmd)
    if parts[:2] == ["-m", "engine.pipeline"] and len(parts) > 2 and parts[2] not in ("settle",) and "--dry-run" not in parts:
        parts.append("--dry-run")
    if any(p.startswith("$") for p in parts):
        return None
    return parts


def check_output_sanity(rep):
    rf = ENGINE / "data" / f"{TOMORROW}.json"
    if not rf.exists():
        rep.bad("strategies", f"collect wrote no research file for tomorrow ({rf.name})")
        return
    d = json.loads(rf.read_text())
    picks = d.get("picks") or []
    try:
        sb = json.loads((ENGINE / "data" / "sb.json").read_text())
        n_sb = len(sb) if isinstance(sb, (list, dict)) else 0
    except Exception:
        n_sb = 0
    if not picks and n_sb:
        rep.bad("strategies", f"favourites engine produced 0 picks for {TOMORROW} although SportyBet lists {n_sb} events")
    need = ("eventId", "match", "market", "selection", "odds", "date", "ko", "marketId", "outcomeId")
    sys.path[:0] = [str(ENGINE), str(ENGINE / "vendor")]
    try:
        from engine.rules import is_dc_vetoed
    except Exception:
        is_dc_vetoed = lambda p: False  # noqa: E731
    bad_fields = [p.get("match") for p in picks if any(p.get(k) in (None, "") for k in need)]
    bad_odds = [f"{p.get('match')} @{p.get('odds')}" for p in picks if not (1.01 <= float(p.get("odds") or 0) <= 50)]
    dc = [p.get("match") for p in picks if is_dc_vetoed(p)]
    youth = [p.get("match") for p in picks if YOUTH.search(f"{p.get('match','')} {p.get('league','')}")]
    if bad_fields:
        rep.bad("strategies", f"{len(bad_fields)} picks miss required fields (e.g. {bad_fields[:3]})")
    if bad_odds:
        rep.bad("strategies", f"{len(bad_odds)} picks have impossible odds (e.g. {bad_odds[:3]})")
    if dc:
        rep.bad("strategies", f"{len(dc)} double-chance picks slipped past the site veto (e.g. {dc[:3]})")
    if youth:
        rep.warn("strategies", f"{len(youth)} youth/women/virtual picks (e.g. {youth[:3]}) — check this strategy allows them")
    if picks and not (bad_fields or bad_odds or dc):
        rep.ok("strategies", f"{len(picks)} favourites picks for {TOMORROW}: fields, odds and DC veto all fine")
    for f in ("home-picks.json", "high_odds.json", "hot-picks.json", "picks.json"):
        p = REPO / f
        try:
            txt = p.read_text()
            json.loads(txt)
            if f == "high_odds.json" and txt.strip().count("\n"):
                rep.bad("strategies", "high_odds.json is no longer one-line compact JSON after the strategies ran")
        except Exception as e:
            rep.bad("strategies", f"{f} is not valid JSON after the strategies ran: {e}")


def run_strategies(rep, wfs, budget_min):
    env = sandbox_env()
    seen, order, results = set(), [], []
    sched = {w: i for i, (w, *_) in enumerate(ticker_schedule())}
    for f in sorted(wfs, key=lambda f: (sched.get(f, 99), f)):
        for c in wfs[f]["commands"]:
            if SKIP_CMD.search(c):
                continue
            parts = to_dry(c)
            if not parts:
                rep.warn("strategies", f"{f}: cannot dry-run `{c}` (uses shell variables)")
                continue
            # make sure collect happens first so later strategies have tomorrow's research
            key = " ".join(parts)
            if key not in seen:
                seen.add(key)
                order.append((f, parts))
    order.sort(key=lambda x: (0 if x[1][:3] == ["-m", "engine.pipeline", "daily"] else 1))
    deadline = time.time() + budget_min * 60
    for f, parts in order:
        label = f"{f}: python {' '.join(parts)}".replace(str(REPO) + "/", "")
        if time.time() > deadline:
            rep.warn("strategies", f"time budget used up; not run: {label}")
            continue
        t0 = time.time()
        try:
            r = subprocess.run([sys.executable] + parts, cwd=REPO, env=env, capture_output=True, text=True,
                               timeout=int(os.environ.get("P2U_HEALTH_CMD_TIMEOUT", "2700")))
            out, rc = (r.stdout or "") + (r.stderr or ""), r.returncode
        except subprocess.TimeoutExpired:
            out, rc = "timeout", "timeout"
        secs = round(time.time() - t0)
        tb = re.findall(r"^(\w+(?:Error|Exception)[^\n]*)$", out, re.M)
        res = {"workflow": f, "command": " ".join(parts).replace(str(REPO) + "/", ""), "rc": rc, "seconds": secs, "errors": tb[-3:], "tail": out[-1500:]}
        results.append(res)
        if rc == "timeout":
            rep.bad("strategies", f"{label} did not finish in time")
        elif rc != 0:
            rep.bad("strategies", f"{label} crashed (exit {rc}): {(tb or out.strip().splitlines() or ['?'])[-1][:300]}")
        elif tb:
            rep.bad("strategies", f"{label} hit an error but kept going: {tb[-1][:300]}")
        else:
            rep.ok("strategies", f"{label} ran clean in {secs}s")
        if parts[:3] == ["-m", "engine.pipeline", "daily"]:
            check_output_sanity(rep)
    rep.sections["strategies"] = results
    # leave the working tree as the checkout had it (no strategy output gets committed)
    subprocess.run(["git", "checkout", "--", "."], cwd=REPO, capture_output=True)


# ---------------------------------------------------------------- 4. site
def site_pages():
    out = subprocess.run(["git", "ls-files", "*.html", "*/index.html"], cwd=REPO, capture_output=True, text=True).stdout.split()
    pages = [p for p in out if p.count("/") <= 1 and not re.search(r"VAPID|GENERATOR|^admin|404", p, re.I)]
    return ["/"] + ["/" + (p[:-10] if p.endswith("/index.html") else p) for p in pages if p != "index.html"]


def check_site(rep):
    pages = site_pages()
    with cf.ThreadPoolExecutor(8) as ex:
        res = list(ex.map(lambda p: (p, http(SITE + p, timeout=30)[0]), pages))
    bad = [f"{p} ({st})" for p, st in res if st != 200]
    for b in bad:
        rep.bad("site", f"page {b} does not load")
    if not bad:
        rep.ok("site", f"all {len(pages)} pages return 200")
    files = {}
    for f, key, max_h in DATA_FILES:
        st, raw = http(f"{SITE}/{f}?t={int(time.time())}", timeout=40)
        if st != 200:
            rep.bad("site", f"{f} does not load ({st})")
            continue
        txt = raw.decode("utf-8", "replace")
        ts = None
        if f.endswith(".json"):
            try:
                doc = json.loads(txt)
                files[f] = doc
                ts = parse_ts(doc.get(key)) if isinstance(doc, dict) else None
            except Exception as e:
                rep.bad("site", f"{f} is not valid JSON: {e}")
                continue
            if f == "high_odds.json" and txt.strip().count("\n"):
                rep.bad("site", "high_odds.json is not compact one-line JSON")
        else:
            m = re.search(key, txt[:5000])
            ts = parse_ts(m.group(1)) if m else None
            try:
                p = Path("/tmp") / ("health-" + f)
                p.write_text(txt)
                r = subprocess.run(["node", "--check", str(p)], capture_output=True, text=True, timeout=60)
                if r.returncode:
                    rep.bad("site", f"{f} is not valid JavaScript: {r.stderr.strip()[-200:]}")
            except FileNotFoundError:
                pass
        if ts is None:
            rep.warn("site", f"{f}: no timestamp found to check freshness")
            continue
        age = (NOW - ts).total_seconds() / 3600
        if age > max_h:
            rep.bad("site", f"{f} is stale: last updated {ts:%Y-%m-%d %H:%M} GMT ({age:.0f}h ago, limit {max_h}h)")
        else:
            rep.ok("site", f"{f} fresh ({age:.1f}h old)")
    for f in ("p2u-home-v318.js", "p2u-code-guard-v352.js"):
        st, raw = http(f"{SITE}/{f}?t={int(time.time())}")
        if st == 200:
            p = Path("/tmp") / ("health-" + f)
            p.write_bytes(raw)
            try:
                if subprocess.run(["node", "--check", str(p)], capture_output=True, timeout=60).returncode:
                    rep.bad("site", f"{f} has a JavaScript syntax error")
            except FileNotFoundError:
                pass
    return files


# ---------------------------------------------------------------- 5. codes
def walk_codes(node, ctx, out, src):
    if isinstance(node, dict):
        c2 = dict(ctx)
        for k in ("date", "targetDate"):
            if isinstance(node.get(k), str) and re.match(r"\d{4}-\d{2}-\d{2}", node[k]):
                c2["date"] = node[k][:10]
        for k in ("status", "result", "settled"):
            if isinstance(node.get(k), str):
                c2["status"] = node[k].lower()
        if isinstance(node.get("code"), str) and node.get("book") in BOOKS:
            out.append((node["book"], node["code"], c2, src))
        for b in BOOKS:
            v = node.get(b)
            if isinstance(v, str):
                out.append((b, v, c2, src))
            elif isinstance(v, dict) and isinstance(v.get("code"), str):
                out.append((b, v["code"], c2, src))
                for part in v.get("parts") or []:
                    if isinstance(part, dict) and isinstance(part.get("code"), str):
                        out.append((b, part["code"], c2, src))
            elif isinstance(v, list):
                for x in v:
                    if isinstance(x, dict) and isinstance(x.get("code"), str):
                        out.append((b, x["code"], c2, src))
                    elif isinstance(x, str):
                        out.append((b, x, c2, src))
        for k, v in node.items():
            if k not in BOOKS:
                walk_codes(v, c2, out, src)
    elif isinstance(node, list):
        for x in node:
            walk_codes(x, ctx, out, src)


def code_status(book, code):
    """(alive, reason). alive=False when the bookmaker rejects it or every match in it has started."""
    now_ms = time.time() * 1000
    try:
        if book in ("sportybet", "footballcom"):
            host = "www.football.com" if book == "footballcom" else "www.sportybet.com"
            st, raw = http(f"https://{host}/api/gh/orders/share/{code}")
            d = json.loads(raw)
            if d.get("bizCode") != 10000:
                return False, d.get("message") or f"bizCode {d.get('bizCode')}"
            o = (d.get("data") or {}).get("outcomes") or []
            if o and all((x.get("estimateStartTime") or 0) <= now_ms for x in o):
                return False, "every match has started"
            return True, f"{sum(1 for x in o if (x.get('estimateStartTime') or 0) > now_ms)}/{len(o)} to play"
        if book == "msport":
            st, raw = http(f"https://www.msport.com/api/gh/orders/real-sports/order/share/{code}", headers={"operid": "3"})
            d = json.loads(raw)
            if d.get("bizCode") != 10000:
                return False, d.get("message") or "invalid"
            B = (d.get("data") or {}).get("bettableBetSlip") or []
            return (bool(B), f"{len(B)} bettable" if B else "no bettable legs left")
        if book == "betika":
            st, raw = http(f"https://api.betika.com.gh/v2/share/decode?code={urllib.parse.quote(code)}&src=MOBILE_WEB")
            d = json.loads(raw)
            V = [x for x in d.get("data") or [] if str(x.get("valid")) == "1"]
            return (bool(V), f"{len(V)} valid" if V else (d.get("message") or "no valid picks"))
        if book == "betpawa":
            st, raw = http(f"https://www.betpawa.com.gh/api/sportsbook/v3/booking-number/{code}",
                           headers={"x-pawa-brand": "betpawa-ghana", "x-pawa-language": "en", "devicetype": "web"})
            d = json.loads(raw)
            it = d.get("items") or []
            if not it:
                return False, d.get("error") or "not found"
            left = [x for x in it if (parse_ts((x.get("eventInfo") or {}).get("startTime")) or NOW) > NOW]
            return (bool(left), f"{len(left)}/{len(it)} to play" if left else "every match has started")
    except Exception as e:
        return None, f"check failed: {e}"
    return None, "unknown bookmaker"


def check_codes(rep, files, heal):
    found = []
    for f in CODE_FILES:
        if f in files:
            walk_codes(files[f], {}, found, f)
    real = re.compile(r"^[A-Za-z0-9]{4,16}$")
    live = {}
    for book, code, ctx, src in found:
        if not real.match(code or "") or code.upper().startswith("P2ULOCK"):
            continue
        if ctx.get("status") in ("won", "lost", "void", "settled", "cancelled"):
            continue
        if ctx.get("date") and ctx["date"] < TODAY:
            continue
        live.setdefault((book, code), set()).add(src)
    with cf.ThreadPoolExecutor(8) as ex:
        res = dict(zip(live, ex.map(lambda k: code_status(*k), live)))
    dead = {f"{b}:{c}": {"book": b, "code": c, "reason": why, "in": sorted(live[(b, c)])} for (b, c), (ok, why) in res.items() if ok is False}
    unknown = [f"{b} {c}" for (b, c), (ok, _) in res.items() if ok is None]
    rep.sections["codes"] = {"checked": len(res), "dead": list(dead.values()), "uncheckable": unknown}
    if unknown:
        rep.warn("codes", f"{len(unknown)} codes could not be checked (bookmaker API error), e.g. {unknown[:3]}")
    if dead:
        rep.warn("codes", f"{len(dead)} of {len(res)} published live codes no longer load or have no match left; hidden via dead-codes.json: "
                          + ", ".join(f"{v['book']} {v['code']} ({v['reason']})" for v in list(dead.values())[:8]))
    else:
        rep.ok("codes", f"all {len(res)} published live codes load with matches still to play")
    if heal:
        p = REPO / "dead-codes.json"
        old = {}
        try:
            old = json.loads(p.read_text()).get("codes") or {}
        except Exception:
            pass
        # keep earlier dead codes for 3 days (a dead code never comes back)
        cut = (NOW - dt.timedelta(days=3)).isoformat()
        keep = {k: v for k, v in old.items() if (v.get("seen") or "") >= cut and k not in dead}
        for k, v in dead.items():
            keep[k] = dict(v, seen=NOW.isoformat(timespec="seconds"))
        p.write_text(json.dumps({"updatedAt": NOW.strftime("%Y-%m-%dT%H:%M:%SZ"), "codes": keep}, separators=(",", ":")))
        if dead:
            rep.heal(f"hid {len(dead)} dead codes on the site (dead-codes.json)")


# ---------------------------------------------------------------- 6. actions
def due_slots(minute, hour, dow, since):
    """Slot datetimes between `since` and now for a cron-like spec (minute/hour lists or */n)."""
    def ok(spec, v):
        return any(p == "*" or (p.startswith("*/") and v % int(p[2:]) == 0) or (p.isdigit() and int(p) == v) for p in spec.split(","))
    t, out = since.replace(second=0, microsecond=0), []
    while t <= NOW:
        if ok(minute, t.minute) and ok(hour, t.hour) and ok(dow, (t.weekday() + 1) % 7):
            out.append(t)
        t += dt.timedelta(minutes=1)
    return out


def codes_missing(wf, files):
    hp = files.get("home-picks.json") or {}
    if wf == "engine-morning.yml":
        return not (REPO / "engine" / "data" / "sb-morning" / f"{TODAY}.json").exists()
    if wf == "engine-fav-leagues.yml":
        dm = ((hp.get("homeCode") or {}).get("dayMasters") or {}).get(TODAY) or {}
        return not dm.get("codes") and bool(dm.get("picks") or hp.get("picks"))
    if wf == "engine-daily.yml":
        r = subprocess.run([sys.executable, str(ENGINE / "daymasters_check.py"), str(REPO / "home-picks.json")], capture_output=True)
        return r.returncode != 0 or not hp.get("leagues")
    return None  # no reliable "codes missing" test: report only


BOOK_HEAL = True  # --no-book-heal turns off re-dispatching booking workflows


def heal_workflow(rep, wf, last_slot, files):
    """Re-run a refresh workflow; re-dispatch a booking one only when its codes for today are missing."""
    try:
        if wf in REFRESH:
            gh(f"/repos/{GH_REPO}/actions/workflows/{wf}/dispatches", "POST", {"ref": "main"})
            rep.heal(f"re-ran {wf}"); rep.problems[-1]["healed"] = True
            return
        miss = codes_missing(wf, files)
        if miss is True and BOOK_HEAL and NOW - last_slot < dt.timedelta(hours=12):
            gh(f"/repos/{GH_REPO}/actions/workflows/{wf}/dispatches", "POST", {"ref": "main"})
            rep.heal(f"re-dispatched {wf}: its codes for today are missing (its run-once gate still blocks double booking)")
            rep.problems[-1]["healed"] = True
        elif miss is True and not BOOK_HEAL:
            rep.problems[-1]["msg"] += " — its codes are missing; booking re-run not attempted (--no-book-heal)"
        elif miss is False:
            rep.problems[-1]["msg"] += " — its codes are on the site anyway, not re-run"
    except Exception as e:
        rep.warn("actions", f"could not re-dispatch {wf}: {e}")


def check_actions(rep, files, heal):
    try:
        wfl = gh(f"/repos/{GH_REPO}/actions/workflows?per_page=100")
    except Exception as e:
        rep.warn("actions", f"cannot read GitHub Actions ({e})")
        return {}
    if wfl is None:
        rep.warn("actions", "no GH_TOKEN; Actions checks skipped")
        return {}
    states = {Path(w["path"]).name: w["state"] for w in wfl.get("workflows") or []}
    created = {Path(w["path"]).name: parse_ts(w["created_at"]) for w in wfl.get("workflows") or [] if w.get("created_at")}
    try:
        alive = gh(f"/repos/{GH_REPO}/actions/workflows/engine-ticker.yml/runs?status=in_progress&per_page=5")
        if (alive or {}).get("total_count"):
            rep.ok("actions", "on-time ticker is running")
        else:
            rep.bad("actions", "on-time ticker is not running")
            if heal:
                gh(f"/repos/{GH_REPO}/actions/workflows/engine-ticker.yml/dispatches", "POST", {"ref": "main"})
                rep.heal("restarted the on-time ticker")
                rep.problems[-1]["healed"] = True
    except Exception as e:
        rep.warn("actions", f"ticker check failed: {e}")
    since = NOW - dt.timedelta(hours=26)
    grouped = {}
    for wf, m, h, d in ticker_schedule():
        born = created.get(wf)
        grouped.setdefault(wf, []).extend(x for x in due_slots(m, h, d, since) if not born or x > born)
    for wf, slots in grouped.items():
        if not slots or states.get(wf) not in (None, "active"):
            continue
        last_slot = max(s for s in slots if s <= NOW - dt.timedelta(minutes=20)) if any(s <= NOW - dt.timedelta(minutes=20) for s in slots) else None
        if not last_slot:
            continue
        try:
            q = urllib.parse.quote(">=" + last_slot.strftime("%Y-%m-%dT%H:%M:%SZ"))
            runs = (gh(f"/repos/{GH_REPO}/actions/workflows/{wf}/runs?per_page=10&created={q}") or {}).get("workflow_runs") or []
        except Exception as e:
            rep.warn("actions", f"{wf}: cannot list runs ({e})")
            continue
        if not runs:
            rep.bad("actions", f"{wf} did not start for its {last_slot:%H:%M} GMT slot")
            if heal:
                heal_workflow(rep, wf, last_slot, files)
            continue
        first = min(runs, key=lambda r: r["created_at"])
        late = (parse_ts(first["created_at"]) - last_slot).total_seconds() / 60
        if late > 30:
            rep.warn("actions", f"{wf} started {late:.0f} min after its {last_slot:%H:%M} slot")
        done = [r for r in runs if r["status"] == "completed"]
        if not done:
            rep.ok("actions", f"{wf} {last_slot:%H:%M} slot is running")
            continue
        if any(r["conclusion"] == "success" for r in done):
            rep.ok("actions", f"{wf} {last_slot:%H:%M} slot succeeded")
            continue
        url = done[0]["html_url"]
        rep.bad("actions", f"{wf} failed for its {last_slot:%H:%M} GMT slot ({url})")
        if heal:
            heal_workflow(rep, wf, last_slot, files)
    return states


# ---------------------------------------------------------------- 7. report + alerts
def write_report(rep):
    out_dir = ENGINE / "data" / "health"
    out_dir.mkdir(parents=True, exist_ok=True)
    open_problems = [p for p in rep.problems if not p.get("healed")]
    doc = {"checkedAt": NOW.strftime("%Y-%m-%dT%H:%M:%SZ"), "mode": rep.mode, "ok": not open_problems,
           "problems": rep.problems, "warnings": rep.warnings, "healed": rep.healed, "passed": rep.passed, "sections": rep.sections}
    (out_dir / f"{TODAY}-{rep.mode}.json").write_text(json.dumps(doc, indent=1, ensure_ascii=False))
    for old in sorted(out_dir.glob("*.json"))[:-28]:
        old.unlink()
    (REPO / "health.json").write_text(json.dumps({"checkedAt": doc["checkedAt"], "mode": rep.mode, "ok": doc["ok"],
                                                   "problems": len(open_problems), "warnings": len(rep.warnings),
                                                   "healed": len(rep.healed)}, separators=(",", ":")))
    return open_problems


def body_text(rep, open_problems):
    run = os.environ.get("GITHUB_RUN_ID")
    link = f"https://github.com/{GH_REPO}/actions/runs/{run}" if run else ""
    lines = [f"Health check ({rep.mode}) at {NOW:%Y-%m-%d %H:%M} GMT — {len(open_problems)} problem(s), {len(rep.warnings)} warning(s), {len(rep.healed)} fixed automatically.", ""]
    if open_problems:
        lines += ["**Needs attention**"] + [f"- [{p['area']}] {p['msg']}" for p in open_problems] + [""]
    if rep.healed:
        lines += ["**Fixed automatically**"] + [f"- {h}" for h in rep.healed] + [""]
    if rep.warnings:
        lines += ["**Warnings**"] + [f"- [{w['area']}] {w['msg']}" for w in rep.warnings[:30]] + [""]
    lines += [f"Passed checks: {len(rep.passed)}. Full report: engine/data/health/{TODAY}-{rep.mode}.json", link]
    return "\n".join(lines)


def alert(rep, open_problems):
    title_prefix = "Predict2u health check"
    try:
        issues = gh(f"/repos/{GH_REPO}/issues?state=open&per_page=100") or []
        mine = [i for i in issues if i["title"].startswith(title_prefix) and "pull_request" not in i]
        body = body_text(rep, open_problems)
        if open_problems:
            title = f"{title_prefix}: {len(open_problems)} problem{'s' if len(open_problems) != 1 else ''}"
            if mine:
                gh(f"/repos/{GH_REPO}/issues/{mine[0]['number']}", "PATCH", {"title": title, "body": body})
            else:
                gh(f"/repos/{GH_REPO}/issues", "POST", {"title": title, "body": body})
        elif mine:
            gh(f"/repos/{GH_REPO}/issues/{mine[0]['number']}/comments", "POST", {"body": "All clear.\n\n" + body})
            gh(f"/repos/{GH_REPO}/issues/{mine[0]['number']}", "PATCH", {"state": "closed", "title": f"{title_prefix}: all clear"})
    except Exception as e:
        print("issue update failed:", e)
    tok, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_ALERT_CHAT_ID")
    if tok and chat and open_problems:
        txt = f"Predict2u health check ({rep.mode}): {len(open_problems)} problem(s)\n" + "\n".join(f"• {p['msg'][:180]}" for p in open_problems[:10])
        st, raw = http(f"https://api.telegram.org/bot{tok}/sendMessage", "POST", {"chat_id": chat, "text": txt[:3900], "disable_web_page_preview": True})
        print("telegram alert:", st)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=("preflight", "post"))
    ap.add_argument("--heal", action="store_true", help="hide dead codes, restart ticker, re-run failed refresh workflows")
    ap.add_argument("--alert", action="store_true", help="update the rolling GitHub issue / Telegram")
    ap.add_argument("--skip-strategies", action="store_true")
    ap.add_argument("--strategy-budget-min", type=int, default=int(os.environ.get("P2U_HEALTH_BUDGET_MIN", "150")))
    ap.add_argument("--no-book-heal", action="store_true", help="never re-dispatch a booking workflow")
    a = ap.parse_args(argv)
    global BOOK_HEAL
    BOOK_HEAL = not a.no_book_heal and os.environ.get("P2U_HEALTH_NO_BOOK_HEAL") != "1"
    rep = Report(a.mode)
    wfs = load_workflows()
    check_code(rep)
    files = check_site(rep)
    check_codes(rep, files, a.heal)
    states = check_actions(rep, files, a.heal)
    check_registry(rep, wfs, states or {})
    if a.mode == "preflight" and not a.skip_strategies:
        run_strategies(rep, wfs, a.strategy_budget_min)
    open_problems = write_report(rep)
    print("\n" + body_text(rep, open_problems))
    if a.alert:
        alert(rep, open_problems)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
