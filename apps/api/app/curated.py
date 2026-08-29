"""Load editor-curated POI lists."""
from __future__ import annotations

import json
from typing import Any

from app.paths import CURATED


def load_curated(district_id: str, vibe: str) -> list[dict[str, Any]]:
    for name in (f"{district_id}-{vibe}.json", f"{district_id}.json"):
        path = CURATED / name
        if not path.is_file():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        stops = data.get("stops") or []
        out: list[dict[str, Any]] = []
        for s in stops:
            if data.get("vibe") and data["vibe"] != vibe:
                continue
            out.append(
                {
                    "id": s["id"],
                    "name": s["name"],
                    "lat": float(s["lat"]),
                    "lng": float(s["lng"]),
                    "weight": float(s.get("weight", 1.5)),
                    "indoor": bool(s.get("indoor", True)),
                    "tags": s.get("tags") or [],
                    "headline": s.get("headline"),
                    "body": s.get("body"),
                    "tip": s.get("tip"),
                    "sourceLabel": s.get("sourceLabel", "green"),
                    "verifiedAt": s.get("verifiedAt"),
                    "tags_osm": {},
                    "origin": "curated",
                }
            )
        if out:
            return out
    return []
