"""Smoke tests for daily strategy modules (no network)."""
import ast, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[1] / "vendor"

def test_three_strategies_parses():
    ast.parse((ROOT / "three_strategies.py").read_text())

def test_verzzify_banker_parses():
    ast.parse((ROOT / "verzzify_banker.py").read_text())

def test_overlap_priority_constants():
    src = (ROOT / "three_strategies.py").read_text()
    assert "o25-2of3" in src and "bottom3-form-dc" in src and "ASC" in src.upper() or "Ascending" in src

def test_nerdytips_parses():
    ast.parse((ROOT / "nerdytips_strategies.py").read_text())

def test_optional_gates_parses():
    import pathlib
    ast.parse((pathlib.Path(__file__).resolve().parents[1] / "gates" / "optional_gates.py").read_text())
