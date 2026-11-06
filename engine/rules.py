"""Public rule surface used by tests and the pipeline (implementation lives in vendor/matchup_rules.py)."""
from __future__ import annotations
import sys
from pathlib import Path

_VENDOR = Path(__file__).resolve().parent / "vendor"
if str(_VENDOR) not in sys.path:
    sys.path.insert(0, str(_VENDOR))

from matchup_rules import (  # noqa: E402
    ALLOW,
    apply_all,
    check,
    classify,
    filter_picks,
    is_double_chance,
)
