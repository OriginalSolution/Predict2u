import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from engine.settle_codes import grade


def ev(h, a, final=True, void=False):
    return {"final": final, "void": void, "score": f"{h}:{a}"}


def test_over_under():
    assert grade("Over 1.5", "A v B", ev(2, 0)) == "won"
    assert grade("Over 2.5", "A v B", ev(1, 1)) == "lost"
    assert grade("Under 3.5", "A v B", ev(1, 1)) == "won"


def test_gg():
    assert grade("Yes", "A v B", ev(1, 1)) == "won"
    assert grade("GG", "A v B", ev(2, 0)) == "lost"
    assert grade("No", "A v B", ev(3, 0)) == "won"


def test_1x2_and_void():
    assert grade("A", "A v B", ev(2, 1)) == "won"
    assert grade("B", "A v B", ev(2, 1)) == "lost"
    assert grade("Draw", "A v B", ev(1, 1)) == "won"
    assert grade("A or Draw", "A v B", ev(0, 0)) == "won"
    assert grade("Yes", "A v B", ev(1, 0, void=True)) == "void"
    assert grade("Yes", "A v B", ev(1, 1, final=False)) == "pending"
