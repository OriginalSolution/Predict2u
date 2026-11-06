"""Configurable directories so the pipeline runs on GitHub Actions as well as the box."""
from __future__ import annotations
import os
from pathlib import Path

ENGINE_DIR = Path(os.environ.get("ENGINE_DIR") or Path(__file__).resolve().parent)
REPO_DIR = Path(os.environ.get("REPO_DIR") or ENGINE_DIR.parent)
VENDOR_DIR = Path(os.environ.get("VENDOR_DIR") or ENGINE_DIR / "vendor")
RESEARCH_DIR = Path(os.environ.get("RESEARCH_DIR") or ENGINE_DIR / "data")
FEED_DIR = Path(os.environ.get("FEED_DIR") or ENGINE_DIR)
STATS_CACHE = Path(os.environ.get("STATS_CACHE") or RESEARCH_DIR / "stats-cache")
INBOX_DIR = Path(os.environ.get("INBOX_DIR") or ENGINE_DIR / "inbox")
INBOX_PARENT = Path(os.environ.get("INBOX_PARENT") or INBOX_DIR)
PRIV_DIR = Path(os.environ.get("PRIV_DIR") or ENGINE_DIR / "private")
GATES_DIR = Path(os.environ.get("ENGINE_GATES_DIR") or ENGINE_DIR / "gates")
SBJSON = Path(os.environ.get("SBJSON") or RESEARCH_DIR / "sb.json")


def environ() -> dict[str, str]:
    """Env vars every vendor script understands."""
    env = dict(os.environ)
    env.update({
        "ENGINE_DIR": str(ENGINE_DIR),
        "REPO_DIR": str(REPO_DIR),
        "VENDOR_DIR": str(VENDOR_DIR),
        "RESEARCH_DIR": str(RESEARCH_DIR),
        "FEED_DIR": str(FEED_DIR),
        "STATS_CACHE": str(STATS_CACHE),
        "INBOX_DIR": str(INBOX_DIR),
        "INBOX_PARENT": str(INBOX_PARENT),
        "PRIV_DIR": str(PRIV_DIR),
        "ENGINE_GATES_DIR": str(GATES_DIR),
        "SBJSON": str(SBJSON),
        "P2U_STRICT_GATES": env.get("P2U_STRICT_GATES", "report"),
    })
    py = env.get("PYTHONPATH", "")
    parts = [str(ENGINE_DIR), str(VENDOR_DIR)]
    env["PYTHONPATH"] = os.pathsep.join(parts + ([py] if py else []))
    return env


def ensure_dirs() -> None:
    for p in (RESEARCH_DIR, STATS_CACHE, INBOX_DIR, PRIV_DIR, GATES_DIR):
        p.mkdir(parents=True, exist_ok=True)
