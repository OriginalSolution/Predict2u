"""Records harvests settled slips from published JSON, not only the box ledger."""
import json, os, sys
from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("build_record", ROOT / "engine" / "vendor" / "build_record.py")
br = importlib.util.module_from_spec(spec); sys.modules["build_record"] = br


def test_harvest_from_high_odds_history(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "engine" / "data").mkdir(parents=True)
    ho = {
        "slips": [],
        "history": [{
            "code": "ABC123", "book": "sportybet", "name": "Test slip", "date": "2026-11-07",
            "odds": 30.5, "status": "lost",
            "legs": [
                {"match": "A v B", "selection": "Over 1.5", "odds": 1.2, "result": "won"},
                {"match": "C v D", "selection": "Over 1.5", "odds": 1.3, "result": "lost"},
            ],
        }],
    }
    (repo / "high_odds.json").write_text(json.dumps(ho))
    (repo / "staked-codes.json").write_text(json.dumps({"codes": {}}))
    (repo / "home-picks.json").write_text(json.dumps({"slips": []}))
    (repo / "picks.json").write_text(json.dumps({"slips": []}))
    (repo / "hot-picks.json").write_text(json.dumps({"slips": []}))
    monkeypatch.setenv("REPO_DIR", str(repo))
    monkeypatch.setenv("ENGINE_DIR", str(repo / "engine"))
    monkeypatch.setenv("RESEARCH_DIR", str(repo / "engine" / "data"))
    monkeypatch.setenv("FEED_DIR", str(repo / "missing-feed"))
    # reload module paths
    import importlib
    spec.loader.exec_module(br)
    br.REPO = repo
    br.ENGINE = repo / "engine"
    br.RESEARCH = repo / "engine" / "data"
    br.FEED = repo / "missing-feed"
    acc = br.harvest_sources()
    assert "sportybet:ABC123" in acc
    assert acc["sportybet:ABC123"]["status"] == "lost"
    br.persist_ledger(acc)
    assert (repo / "engine" / "data" / "code-ledger.json").exists()
