"""选站 + 排序 + 文案."""
from __future__ import annotations

import math
import random
from typing import Any

from app.districts import District
from app.osm import fetch_pois
from app.osrm import route_foot

LINE_META = {
    "neon": ("L-N1", "夜行线"),
    "coffee": ("L-C2", "咖啡线"),
    "vintage": ("L-V3", "古着线"),
    "gallery": ("L-G4", "艺术线"),
}

PACE_FACTOR = {"slow": 1.25, "normal": 1.0, "fast": 0.85}


def _dist(a: dict, b: dict) -> float:
    return math.hypot(a["lat"] - b["lat"], a["lng"] - b["lng"])


def _pick_spread(pois: list[dict], n: int, seed: int = 42) -> list[dict]:
    if len(pois) <= n:
        return pois
    rng = random.Random(seed)
    start = rng.choice(pois)
    chosen = [start]
    pool = [p for p in pois if p is not start]
    while len(chosen) < n and pool:
        nxt = max(pool, key=lambda p: min(_dist(p, c) for c in chosen))
        chosen.append(nxt)
        pool.remove(nxt)
    return chosen


def _order_nearest(stops: list[dict]) -> list[dict]:
    if len(stops) <= 1:
        return stops
    remaining = stops[1:]
    ordered = [stops[0]]
    while remaining:
        last = ordered[-1]
        nxt = min(remaining, key=lambda p: _dist(last, p))
        ordered.append(nxt)
        remaining.remove(nxt)
    return ordered


def _narrative(vibe: str, name: str, tags: dict) -> dict[str, str]:
    cuisine = tags.get("cuisine", "")
    opening = tags.get("opening_hours", "")
    extra = f" {cuisine}" if cuisine else ""
    headlines = {
        "neon": "灯箱亮起来的一站",
        "coffee": "适合外带或坐下来",
        "vintage": "橱窗值得慢看",
        "gallery": "留白墙面也是展品",
    }
    return {
        "headline": headlines.get(vibe, "好逛的一站"),
        "body": f"「{name}」在 OSM 有记录{extra}——LifeTrip 把它当作当下 city walk 的一站，不是典籍条目，而是今天值得拐进去的真实街面。",
        "tip": f"营业参考：{opening}" if opening else "到门口再看今日是否开放。",
    }


def plan_route(
    *,
    vibe: str,
    district: District,
    duration_min: int,
    pace: str,
) -> dict[str, Any]:
    pois = fetch_pois(vibe, district)
    if len(pois) < 3:
        raise RuntimeError(f"too few pois: {len(pois)}")

    stop_count = 4 if duration_min >= 75 else 3
    picked = _pick_spread(pois, stop_count)
    ordered = _order_nearest(picked)

    coords = [(s["lng"], s["lat"]) for s in ordered]
    osrm = route_foot(coords)

    line_code, line_name = LINE_META[vibe]
    pace_f = PACE_FACTOR.get(pace, 1.0)
    walk_min = max(15, int((osrm["duration_s"] / 60) * pace_f))

    stops: list[dict[str, Any]] = []
    for i, p in enumerate(ordered):
        code = f"{line_code.split('-')[1]}-{i+1:02d}"
        narr = _narrative(vibe, p["name"], p.get("tags") or {})
        stops.append(
            {
                "id": p["id"],
                "code": code,
                "name": p["name"],
                "district": district.name,
                "lat": p["lat"],
                "lng": p["lng"],
                "tags": _tags_for_vibe(vibe, p.get("tags") or {}),
                "headline": narr["headline"],
                "body": narr["body"],
                "tip": narr["tip"],
                "walkMin": 0 if i == 0 else max(5, walk_min // max(1, len(ordered) - 1)),
            }
        )

    return {
        "lineCode": line_code,
        "lineName": line_name,
        "title": f"{district.name} · {line_name}",
        "subtitle": f"OSM 实点 {len(stops)} 站 · 步行约 {walk_min} 分钟",
        "totalMin": walk_min,
        "vibe": vibe,
        "districtId": district.id,
        "stops": stops,
        "geometry": osrm.get("geometry"),
        "distanceM": osrm.get("distance_m", 0),
    }


def _tags_for_vibe(vibe: str, tags: dict) -> list[str]:
    base = {
        "neon": ["夜行", "Bar", "餐饮"],
        "coffee": ["咖啡", "外带", "坐席"],
        "vintage": ["古着", "选物", "淘街"],
        "gallery": ["画廊", "展览", "艺术"],
    }.get(vibe, ["city walk"])
    if tags.get("outdoor_seating") == "yes":
        base = [*base, "外摆"]
    return base[:4]
