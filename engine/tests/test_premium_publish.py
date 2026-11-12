"""Publish paths for morning, model slips, ho-masters and Verzzify go through the lock."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load_lock_codes():
    spec = importlib.util.spec_from_file_location("lock_codes", ROOT / "engine" / "vendor" / "lock_codes.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_prune():
    spec = importlib.util.spec_from_file_location("prune_live_premium", ROOT / "engine" / "vendor" / "prune_live.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_seal_public_strips_side_copies_and_keeps_high_odds_one_line(tmp_path):
    ho = {
        "label": "High Odds",
        "slips": [{
            "code": "HODAY",
            "name": "Ascending odds · first 25 · HIGH RISK",
            "date": "2026-11-12",
            "odds": 33,
            "origin": "ho-master",
            "legs": [{"match": "Up v Down", "selection": "Over 1.5", "odds": 1.3, "date": "2026-11-12"}],
            "codes": {"sportybet": {"code": "HODAY", "legs": 1, "odds": 33, "link": "https://www.sportybet.com/gh/?shareCode=HODAY"}},
        }],
    }
    (tmp_path / "high_odds.json").write_text(json.dumps(ho, separators=(",", ":")))
    morning = tmp_path / "engine" / "data" / "sb-morning"
    morning.mkdir(parents=True)
    (morning / "2026-11-12.json").write_text(json.dumps({
        "date": "2026-11-12",
        "picks": [{"match": "Dawn v Dusk", "selection": "Over 1.5"}],
        "slips": [{"name": "SportyBet Stats · Master", "totalOdds": 30, "legs": 1, "codes": {"sportybet": "MORNING"}}],
    }))
    verz = tmp_path / "engine" / "data" / "verzzify-banker-2026-11-12.json"
    verz.write_text(json.dumps({
        "name": "Verzzify Edge Banker",
        "strategy": "verzzify-edge-banker",
        "date": "2026-11-12",
        "totalOdds": 28,
        "verzzify": True,
        "code": "VERZ1",
        "legs": [{"match": "Edge v Bank", "selection": "Home", "odds": 1.25, "date": "2026-11-12"}],
        "codes": {"sportybet": {"code": "VERZ1", "odds": 28, "legs": 1, "link": "https://www.sportybet.com/gh/?shareCode=VERZ1"}},
    }))
    store = {}
    changed = _load_lock_codes()._seal_public(str(tmp_path), store)
    assert any(name.endswith("high_odds.json") for name in changed)
    assert any("sb-morning" in name for name in changed)
    assert any("verzzify-banker" in name for name in changed)
    text = (tmp_path / "high_odds.json").read_text()
    assert "\n" not in text and text.startswith("{") and "HODAY" not in text and "Up v Down" not in text
    report = json.loads((morning / "2026-11-12.json").read_text())
    assert report["picks"] == [] and "MORNING" not in json.dumps(report)
    verz_doc = json.loads(verz.read_text())
    assert "VERZ1" not in json.dumps(verz_doc) and "Edge v Bank" not in json.dumps(verz_doc)
    assert store["hot-20261112"]["codes"]["sportybet"][0]["code"] == "HODAY"
    assert store["banker-20261112"]["codes"]["sportybet"][0]["code"] == "VERZ1"


def test_prune_keeps_a_sealed_model_slip_for_its_day():
    pl = _load_prune()
    doc = {"modelSlips": [
        {"name": "Safest market", "strategy": "safe50", "date": "2099-01-02", "premium": True,
         "totalOdds": 40, "legs": 3, "picks": 3, "codes": {"sportybet": [{"code": "P2ULOCK-hot-20990102-sportybet0"}]}},
        {"name": "Old safest", "strategy": "safe50", "date": "2020-01-01", "premium": True,
         "totalOdds": 40, "legs": 3, "picks": 3},
    ], "picks": []}
    out, removed = pl.prune_hot(doc)
    assert [s["name"] for s in out["modelSlips"]] == ["Safest market"]
    assert any(row[2] == "2020-01-01" for row in removed)


def test_jobs_lock_on_publish_and_the_ticker_starts_them():
    ticker = (ROOT / ".github" / "scripts" / "p2u_ticker.py").read_text()
    assert '("engine-fav-leagues.yml", "0", "6", "*")' in ticker
    assert '("engine-m1m2.yml", "45", "21", "*")' in ticker
    assert '("engine-strategies.yml", "30", "22", "*")' in ticker
    morning = (ROOT / ".github" / "workflows" / "engine-morning.yml").read_text()
    models = (ROOT / ".github" / "workflows" / "engine-m1m2.yml").read_text()
    strategies = (ROOT / ".github" / "workflows" / "engine-strategies.yml").read_text()
    pipe = (ROOT / "engine" / "pipeline.py").read_text()
    assert "p2u_gate.py --at 07:00 --job morning" in morning
    assert "p2u_gate.py --at 21:45 --job m1m2" in models
    assert "p2u_gate.py --at 22:30 --job strategies" in strategies
    for text in (morning, models, strategies):
        assert "p2u_push.sh main" in text
        assert "P2U_LOCK_KEY" in text
        assert "locked.enc.json" in text
    assert "python -m engine.premium --lock" in models
    assert "python -m engine.premium --lock" in strategies
    assert 'args.command == "morning"' in pipe and "_lock_premium" in pipe
    assert "save(OUT, doc, pretty=False)" in (ROOT / "engine" / "vendor" / "high_odds.py").read_text()
    hot = (ROOT / "p2u-hot-v309.js").read_text()
    assert "modelSlips" in hot and "if(models.length)" in hot and "P2UPremium.is(s)" in hot
