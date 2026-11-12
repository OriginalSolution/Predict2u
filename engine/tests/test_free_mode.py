"""Free-codes mode (p2u-free-mode.js / P2U_FREE_CODES): nothing is flagged or sealed."""
import json

from engine.premium import flag_slip, free_mode, is_premium_odds, lock_published, unseal_repo


def test_env_overrides_file(monkeypatch, tmp_path):
    (tmp_path / "p2u-free-mode.js").write_text("window.P2U_FREE_CODES = true;\n")
    monkeypatch.delenv("P2U_FREE_CODES", raising=False)
    assert free_mode(str(tmp_path)) is True
    (tmp_path / "p2u-free-mode.js").write_text("window.P2U_FREE_CODES = false;\n")
    assert free_mode(str(tmp_path)) is False
    monkeypatch.setenv("P2U_FREE_CODES", "1")
    assert free_mode(str(tmp_path)) is True


def test_free_mode_never_premium(monkeypatch):
    monkeypatch.setenv("P2U_FREE_CODES", "1")
    assert is_premium_odds(12978.01) is False
    slip = {"name": "Morning master", "totalOdds": 12978.01, "premium": True, "locked": {"id": "hot-20261112"}, "code": "8USGK9"}
    flag_slip(slip)
    assert "premium" not in slip and "locked" not in slip and slip["code"] == "8USGK9"


def test_lock_published_unseals_and_keeps_one_line(monkeypatch, tmp_path):
    monkeypatch.setenv("P2U_FREE_CODES", "1")
    monkeypatch.delenv("P2U_LOCK_KEY", raising=False)
    (tmp_path / "engine" / "data").mkdir(parents=True)
    (tmp_path / "engine" / "data" / "free-restore.json").write_text(json.dumps({"codes": {"hot-20261106": {"sportybet": ["F3PCEP"]}}}))
    doc = {"slips": [{"name": "Master", "totalOdds": 99.0, "premium": True, "locked": {"id": "hot-20261106"},
                      "code": "P2ULOCK-hot-20261106-sportybet", "codes": {"sportybet": {"code": "P2ULOCK-hot-20261106-sportybet"}}},
                     {"name": "Gone", "totalOdds": 30.0, "code": "P2ULOCK-banker-20261108-sportybet"}]}
    (tmp_path / "high_odds.json").write_text(json.dumps(doc, separators=(",", ":")))
    assert lock_published(str(tmp_path)) == 0
    raw = (tmp_path / "high_odds.json").read_text()
    assert "\n" not in raw.strip()
    out = json.loads(raw)
    s = out["slips"][0]
    assert s["code"] == "F3PCEP" and s["codes"]["sportybet"]["code"] == "F3PCEP"
    assert "premium" not in s and "locked" not in s
    # unknown placeholder stays for the site to hide; never guessed
    assert out["slips"][1]["code"] == "P2ULOCK-banker-20261108-sportybet"
    assert unseal_repo(str(tmp_path)) == []
