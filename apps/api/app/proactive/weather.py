"""Proactive triggers — weather-based reroute proposals (async)."""
from __future__ import annotations

import os
from typing import Any

import httpx

from app.contracts import RerouteProposal, RouteEnvelope, WalkTask
from app.districts import DISTRICTS
from app.plan.planner import plan_route

# Open-Meteo — no API key required
METEO_URL = "https://api.open-meteo.com/v1/forecast"


def _district(district_id: str):
    return next((d for d in DISTRICTS if d.id == district_id), None)


async def fetch_rain_hours(lat: float, lng: float) -> list[dict[str, Any]]:
    if os.getenv("LIFETRIP_OFFLINE", "0") == "1":
        return [{"hour": 15, "precip_mm": 4.2}, {"hour": 16, "precip_mm": 3.1}]
    params = {
        "latitude": lat,
        "longitude": lng,
        "hourly": "precipitation",
        "forecast_days": 1,
        "timezone": "Asia/Shanghai",
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(METEO_URL, params=params)
        r.raise_for_status()
        data = r.json()
    hours = data.get("hourly") or {}
    times = hours.get("time") or []
    precips = hours.get("precipitation") or []
    out = []
    for t, p in zip(times, precips):
        if "T" in t:
            h = int(t.split("T")[1][:2])
            out.append({"hour": h, "precip_mm": float(p or 0)})
    return out


async def check_weather_reroute(task: WalkTask) -> RerouteProposal | None:
    district = _district(task.brief.district_id)
    if not district:
        return None

    lat = (district.south + district.north) / 2
    lng = (district.west + district.east) / 2
    hours = await fetch_rain_hours(lat, lng)
    heavy = [h for h in hours if h["precip_mm"] >= 2.0]
    if not heavy:
        return None

    outdoor_indices = [
        i
        for i, s in enumerate(task.route.stops)
        if not s.skipped and not s.indoor and i >= task.current_stop_index
    ]
    if not outdoor_indices:
        return None

    hour_range = f"{min(h['hour'] for h in heavy):02d}:00\u2013{max(h['hour'] for h in heavy):02d}:00"
    proposed = plan_route(
        vibe=task.brief.vibe,
        district=district,
        duration_min=task.brief.duration_min,
        pace=task.brief.pace,
        prefer_indoor=True,
        seed=hash(task.id) % 10000,
    )
    proposed.source = "live"
    names = ", ".join(task.route.stops[i].name for i in outdoor_indices[:2])
    message = (
        f"预计 {hour_range} 有降雨，「{names}」等户外站可能受影响。"
        f"已生成室内优先替代线，需要我调整吗？"
    )
    return RerouteProposal(
        task_id=task.id,
        trigger="rain_forecast",
        message=message,
        affected_stop_indices=outdoor_indices,
        proposed_route=proposed,
        requires_confirm=True,
    )
