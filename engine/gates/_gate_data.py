"""Resolve gate snapshot data without hardcoding /workspace/novDD.

Looks in ENGINE_GATES_DIR, this package dir, then box fallbacks. Missing
files become empty defaults so Actions can still import gate31 / rules31
and apply hard vetoes (DC/NG/women/price) while stats-dependent checks
degrade to STRICT: no stats.
"""
from __future__ import annotations
import json, os, pickle, csv
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent  # engine/


def data_dirs() -> list[Path]:
    dirs: list[Path] = []
    env = os.environ.get("ENGINE_GATES_DIR")
    if env:
        dirs.append(Path(env))
    dirs.append(_HERE)
    # box day folders (newest first) + thresholds at /workspace/rules
    try:
        novs = sorted(Path("/workspace").glob("nov[0-9][0-9]"), reverse=True)
        dirs.extend(novs)
    except Exception:
        pass
    dirs.append(Path("/workspace/rules"))
    dirs.append(_ROOT / "data")
    # de-dupe preserving order
    out, seen = [], set()
    for d in dirs:
        s = str(d)
        if s not in seen:
            seen.add(s)
            out.append(d)
    return out


def find_file(*names: str) -> Path | None:
    for d in data_dirs():
        for n in names:
            p = d / n
            if p.is_file():
                return p
    return None


def load_json(name: str, default=None):
    if default is None:
        default = {}
    p = find_file(name)
    if not p:
        return default
    try:
        return json.loads(p.read_text())
    except Exception:
        return default


def load_pickle(name: str, default=None):
    if default is None:
        default = []
    p = find_file(name)
    if not p:
        return default
    try:
        with open(p, "rb") as f:
            return pickle.load(f)
    except Exception:
        return default


def open_text(name: str):
    p = find_file(name)
    if not p:
        return None
    try:
        return open(p, encoding="utf-8", errors="ignore")
    except Exception:
        return None


def csv_dict_rows(name: str):
    p = find_file(name)
    if not p:
        return []
    try:
        with open(p, newline="", encoding="utf-8", errors="ignore") as f:
            return list(csv.DictReader(f))
    except Exception:
        return []
