import json
"""Fully settled slips leave live lists; partials stay; history kept."""
import importlib.util, pathlib, sys
ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("prune_live", ROOT / "vendor" / "prune_live.py")
pl = importlib.util.module_from_spec(spec); sys.modules["prune_live"] = pl; spec.loader.exec_module(pl)

def test_fully_settled_slip_not_live():
    s = {"date": "2099-01-01", "legs": [
        {"result": "won", "kickoff": "2099-01-01T12:00:00Z"},
        {"result": "lost", "kickoff": "2099-01-01T15:00:00Z"},
    ]}
    assert pl.live_slip(s) is False

def test_partial_settled_slip_stays_live():
    s = {"date": "2099-01-01", "legs": [
        {"result": "won", "kickoff": "2099-01-01T12:00:00Z"},
        {"result": "pending", "kickoff": "2099-01-01T20:00:00Z"},
    ]}
    assert pl.live_slip(s) is True

def test_prune_high_odds_moves_settled_to_history():
    doc = {"slips": [
        {"code": "AAA", "status": "pending", "legs": [{"result": "pending", "kickoff": "2099-01-01T20:00:00Z"}]},
        {"code": "BBB", "status": "lost", "legs": [{"result": "lost"}, {"result": "won"}], "date": "2026-11-07"},
    ], "history": []}
    out, rem = pl.prune_high_odds(doc)
    codes = {s["code"] for s in out["slips"]}
    hist = {s["code"] for s in out["history"]}
    assert "AAA" in codes and "BBB" not in codes
    assert "BBB" in hist
    assert any(r[1] == "BBB" for r in rem)

def test_settled_pick_not_live():
    assert pl.live_pick({"result": "won", "date": "2099-01-01", "kickoff": "2099-01-01T12:00:00Z"}) is False
    assert pl.live_pick({"result": "pending", "date": "2099-01-01", "kickoff": "2099-01-01T20:00:00Z"}) is True


def test_prune_home_archives_settled(tmp_path, monkeypatch):
    repo = tmp_path
    (repo / "engine" / "data").mkdir(parents=True)
    monkeypatch.setattr(pl, "REPO", repo)
    doc = {"slips": [{
        "name": "Old slip", "date": "2026-11-01",
        "codes": {"sportybet": "ZZZZ99"},
        "legs": [
            {"result": "won", "kickoff": "2026-11-01T12:00:00Z", "match": "A v B", "selection": "Over 1.5", "odds": 1.2},
            {"result": "lost", "kickoff": "2026-11-01T15:00:00Z", "match": "C v D", "selection": "Over 1.5", "odds": 1.3},
        ],
    }], "picks": []}
    out, rem = pl.prune_home(doc)
    assert out["slips"] == []
    ledger = json.loads((repo / "engine" / "data" / "code-ledger.json").read_text())
    assert "sportybet:ZZZZ99" in ledger
    assert ledger["sportybet:ZZZZ99"]["status"] == "lost"
