"""OSRM 步行路由 (async)."""
from __future__ import annotations

import os
from typing import Any

import httpx

OSRM_BASE = os.getenv(
    "LIFETRIP_OSRM_BASE",
    "https://router.project-osrm.org/route/v1/foot",
)


async def route_foot(coords: list[tuple[float, float]]) -> dict[str, Any]:
    """coords: [(lng, lat), ...]"""
    if len(coords) < 2:
        return {"geometry": None, "distance_m": 0, "duration_s": 0}
    path = ";".join(f"{lng},{lat}" for lng, lat in coords)
    url = f"{OSRM_BASE}/{path}"
    params = {"overview": "full", "geometries": "geojson", "steps": "false"}
    async with httpx.AsyncClient(timeout=float(os.getenv("LIFETRIP_OSRM_TIMEOUT", "15"))) as client:
        r = await client.get(url, params=params)
        r.raise_for_status()
        data = r.json()
    if data.get("code") != "Ok" or not data.get("routes"):
        raise RuntimeError(data.get("message", "osrm failed"))
    route = data["routes"][0]
    return {
        "geometry": route.get("geometry"),
        "distance_m": int(route.get("distance", 0)),
        "duration_s": int(route.get("duration", 0)),
    }
