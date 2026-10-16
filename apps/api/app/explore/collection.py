"""POI collection — which POIs has the user visited."""
from __future__ import annotations

from typing import Any

from app.contracts import WalkTask


def compute_collection(completed: list[WalkTask]) -> list[dict[str, Any]]:
    """Build a list of collected POIs (unique, non-skipped)."""
    seen: dict[str, dict[str, Any]] = {}
    for task in completed:
        for s in task.route.stops:
            if s.skipped:
                continue
            if s.id not in seen:
                seen[s.id] = {
                    "id": s.id,
                    "name": s.name,
                    "district": s.district,
                    "tags": s.tags[:3],
                    "source_label": s.sourceLabel,
                    "lat": s.lat,
                    "lng": s.lng,
                }
    return list(seen.values())


def compute_stats(completed: list[WalkTask]) -> dict[str, Any]:
    """Aggregate numeric stats."""
    total_km = sum((t.route.distanceM or 0) for t in completed) / 1000.0
    total_stops = sum(len(t.route.stops) for t in completed)
    total_min = sum(t.route.totalMin for t in completed)
    return {
        "total_walks": len(completed),
        "total_km": round(total_km, 2),
        "total_stops": total_stops,
        "total_minutes": total_min,
    }
