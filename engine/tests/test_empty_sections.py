"""Empty strategy sections are never published (HANDOFF §5.11)."""
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "engine"))
import empty_sections as es  # noqa: E402


def test_empty_section_omitted_nonempty_kept():
    slips = [
        {"code": "TTW1", "origin": "strategy-ttw", "name": "Team To Win · HIGH RISK"},
        {"code": "", "origin": "strategy-form80", "name": "80% Form · HIGH RISK"},
        {"origin": "strategy-mo25", "name": "Match Over 2.5 · HIGH RISK", "codes": {}},
        {"code": "AH1A", "origin": "strategy-ah1", "name": "AH -1 Favourite · HIGH RISK"},
    ]
    sections = es.sections_to_publish(slips)
    assert [s["origin"] for s in sections] == ["strategy-ttw", "strategy-ah1"]
    assert [row["code"] for row in sections[0]["slips"]] == ["TTW1"]
    kept = es.drop_empty_strategy_cards(slips)
    assert [s["code"] for s in kept] == ["TTW1", "AH1A"]


def test_all_empty_yields_empty_list():
    slips = [
        {"origin": "strategy-ttw", "name": "Team To Win · HIGH RISK"},
        {"code": "", "origin": "strategy-form80", "codes": {}},
    ]
    assert es.sections_to_publish(slips) == []
    assert es.drop_empty_strategy_cards(slips) == []


def test_history_cards_with_codes_are_kept():
    doc = {
        "slips": [
            {"code": "LIVE", "origin": "strategy-ttw", "name": "Team To Win · HIGH RISK"},
            {"origin": "strategy-form80", "name": "80% Form · HIGH RISK"},
        ],
        "history": [
            {"code": "OLD1", "origin": "strategy-form80", "name": "80% Form · HIGH RISK", "status": "lost"},
            {"origin": "strategy-mo25", "name": "Match Over 2.5 · HIGH RISK", "status": "lost"},
        ],
    }
    out = es.prepare_high_odds_doc(doc)
    assert [s["code"] for s in out["slips"]] == ["LIVE"]
    assert [s["code"] for s in out["history"]] == ["OLD1"]
    assert out["history"][0]["origin"] == "strategy-form80"


def test_preserve_origin_does_not_stomp_specific_keys():
    assert es.preserve_origin({"origin": "strategy-form80", "name": "Team To Win"}) == "strategy-form80"
    assert es.preserve_origin({"origin": "ho-master", "name": "Ascending odds"}) == "ho-master"
    assert es.preserve_origin({"origin": "strategy", "name": "Team To Win 2 · HIGH RISK"}) == "strategy-ttw"
    assert es.preserve_origin({"origin": "strategy", "pipeline": "mp-grp-o25", "name": "Over 2.5 Group · HIGH RISK"}) == "strategy-mp-grp-o25"
    assert es.preserve_origin({"origin": "strategy", "name": "80% Sure · HIGH RISK"}) == "strategy-sure80"
    assert es.preserve_origin({"origin": "strategy", "name": "Reverse U4.5 + Draw · HIGH RISK"}) == "strategy-rev-u45-draw"
    assert es.preserve_origin({"origin": "code-hub", "name": "High Odds Selection"}) == "code-hub"


def test_prepare_repairs_generic_strategy_origin_and_stays_one_line(tmp_path):
    doc = {
        "label": "High Odds — higher risk",
        "slips": [
            {"code": "DLVWTL", "origin": "strategy", "name": "Team To Win 1 · HIGH RISK", "strategyJob": True},
            {"code": "9ES308", "origin": "strategy", "name": "80% Sure · HIGH RISK", "strategyJob": True},
        ],
        "history": [{"code": "OLD", "origin": "strategy", "name": "AH -1 Favourite · HIGH RISK"}],
    }
    path = tmp_path / "high_odds.json"
    written = es.write_high_odds(path, doc)
    raw = path.read_text()
    assert "\n" not in raw.strip()
    assert written["slips"][0]["origin"] == "strategy-ttw"
    assert written["slips"][1]["origin"] == "strategy-sure80"
    assert written["history"][0]["origin"] == "strategy-ah1"
    assert json.loads(raw)["slips"][0]["origin"] == "strategy-ttw"


def test_hot_upsert_still_hides_slips_with_no_codes(tmp_path):
    sys.path.insert(0, str(ROOT / "engine" / "vendor"))
    import publish_hot as PH  # noqa: E402
    doc = PH.upsert_model_slips(tmp_path, [
        {"name": "M1", "strategy": "M1", "codes": {"sportybet": [{"code": "ABCDE", "totalOdds": 2, "legs": 3, "link": "https://x"}]}},
        {"name": "empty", "strategy": "M2", "codes": {}},
    ])
    assert [s["strategy"] for s in doc["modelSlips"]] == ["M1"]
    assert all(es.has_valid_code(s) for s in doc["modelSlips"])
