"""Repository path helpers."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CONTENT = ROOT / "content"
CURATED = CONTENT / "curated"
CACHE = CONTENT / "cache"
FIXTURES = CONTENT / "fixtures"
EVAL = CONTENT / "eval"
DATA = ROOT / "apps" / "api" / "data"
NARRATIVES = CONTENT / "narratives"
CACHE_NARRATIVES_DIR = CONTENT / "cache" / "narratives"
