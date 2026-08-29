"""POI response cache for Overpass."""
from __future__ import annotations

import json
import time
from typing import Any

from app.paths import CACHE

TTL_SEC = 60 * 60 * 6  # 6 hours


def _cache_path(district_id: str, vibe: str):
    CACHE.mkdir(parents=True, exist_ok=True)
    return CACHE / f"{district_id}-{vibe}.json"


def read_cache(district_id: str, vibe: str) -> list[dict[str, Any]] | None:
    path = _cache_path(district_id, vibe)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if time.time() - float(data.get("cached_at", 0)) > TTL_SEC:
            return None
        return data.get("pois") or None
    except (json.JSONDecodeError, OSError):
        return None


def write_cache(district_id: str, vibe: str, pois: list[dict[str, Any]]) -> None:
    path = _cache_path(district_id, vibe)
    path.write_text(
        json.dumps({"cached_at": time.time(), "pois": pois}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def read_stale_cache(district_id: str, vibe: str) -> list[dict[str, Any]] | None:
    path = _cache_path(district_id, vibe)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("pois") or None
    except (json.JSONDecodeError, OSError):
        return None
