"""选站 + 排序 + 文案（curated 加权 + OSM 补位）."""
from __future__ import annotations

import math
import random
from typing import Any

from app.contracts import RouteEnvelope, Stop
from app.curated import load_curated
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


def _merge_pois(curated: list[dict], osm: list[dict]) -> list[dict]:
    seen: set[str] = set()
    merged: list[dict] = []
    for p in curated:
        seen.add(p["id"])
        merged.append({**p, "weight": float(p.get("weight", 1.5))})
    for p in osm:
        if p["id"] in seen:
            continue
        merged.append(
            {
                **p,
                "weight": 0.8,
                "origin": "osm",
                "sourceLabel": "blue",
                "indoor": p.get("tags", {}).get("indoor") == "yes",
            }
        )
    return merged


def _weighted_pick(pois: list[dict], n: int, seed: int = 42) -> list[dict]:
    if len(pois) <= n:
        return pois
    rng = random.Random(seed)
    pool = sorted(pois, key=lambda p: p.get("weight", 1.0), reverse=True)
    start = pool[0]
    chosen = [start]
    remaining = [p for p in pool if p is not start]
    while len(chosen) < n and remaining:
        def score(p: dict) -> float:
            spread = min(_dist(p, c) for c in chosen)
            return spread * (0.5 + p.get("weight", 1.0))

        nxt = max(remaining, key=score)
        chosen.append(nxt)
        remaining.remove(nxt)
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


def _narrative(vibe: str, poi: dict) -> dict[str, str]:
    if poi.get("headline") and poi.get("body"):
        return {
            "headline": poi["headline"],
            "body": poi["body"],
            "tip": poi.get("tip") or "到门口再看今日是否开放。",
        }
    name = poi["name"]
    tags = poi.get("tags_osm") or poi.get("tags") or {}
    if isinstance(tags, list):
        tags = {}
    cuisine = tags.get("cuisine", "") if isinstance(tags, dict) else ""
    opening = tags.get("opening_hours", "") if isinstance(tags, dict) else ""
    extra = f" {cuisine}" if cuisine else ""
    headlines = {
        "neon": "灯箱亮起来的一站",
        "coffee": "适合外带或坐下来",
        "vintage": "橱窗值得慢看",
        "gallery": "留白墙面也是展品",
    }
    origin = poi.get("origin", "osm")
    src_note = "编辑核实" if origin == "curated" else "OSM 实点"
    return {
        "headline": headlines.get(vibe, "好逛的一站"),
        "body": f"「{name}」— {src_note}，LifeTrip 把它当作当下 city walk 的一站。{extra}".strip(),
        "tip": f"营业参考：{opening}" if opening else "到门口再看今日是否开放。",
    }


def _tags_for_vibe(vibe: str, poi: dict) -> list[str]:
    if isinstance(poi.get("tags"), list) and poi["tags"]:
        return poi["tags"][:4]
    tags = poi.get("tags_osm") or {}
    base = {
        "neon": ["夜行", "Bar", "餐饮"],
        "coffee": ["咖啡", "外带", "坐席"],
        "vintage": ["古着", "选物", "淘街"],
        "gallery": ["画廊", "展览", "艺术"],
    }.get(vibe, ["city walk"])
    if tags.get("outdoor_seating") == "yes":
        base = [*base, "外摆"]
    return base[:4]


def plan_route(
    *,
    vibe: str,
    district: District,
    duration_min: int,
    pace: str,
    exclude_ids: set[str] | None = None,
    prefer_indoor: bool = False,
    seed: int = 42,
) -> RouteEnvelope:
    curated = load_curated(district.id, vibe)
    try:
        osm = fetch_pois(vibe, district)
    except RuntimeError:
        osm = []
    merged = _merge_pois(curated, osm)
    if exclude_ids:
        merged = [p for p in merged if p["id"] not in exclude_ids]
    if prefer_indoor:
        indoor = [p for p in merged if p.get("indoor", True)]
        if len(indoor) >= 3:
            merged = indoor

    if len(merged) < 3:
        raise RuntimeError(f"too few pois: {len(merged)}")

    stop_count = 4 if duration_min >= 75 else 3
    picked = _weighted_pick(merged, stop_count, seed=seed)
    ordered = _order_nearest(picked)

    coords = [(s["lng"], s["lat"]) for s in ordered]
    try:
        osrm = route_foot(coords)
    except Exception:  # noqa: BLE001
        osrm = {
            "geometry": {
                "type": "LineString",
                "coordinates": [[lng, lat] for lng, lat in coords],
            },
            "distance_m": int(sum(_dist(ordered[i], ordered[i + 1]) for i in range(len(ordered) - 1)) * 111000),
            "duration_s": len(ordered) * 600,
        }

    line_code, line_name = LINE_META[vibe]
    pace_f = PACE_FACTOR.get(pace, 1.0)
    walk_min = max(15, int((osrm["duration_s"] / 60) * pace_f))

    curated_n = sum(1 for p in ordered if p.get("origin") == "curated")
    stops: list[Stop] = []
    for i, p in enumerate(ordered):
        code = f"{line_code.split('-')[1]}-{i+1:02d}"
        narr = _narrative(vibe, p)
        stops.append(
            Stop(
                id=p["id"],
                code=code,
                name=p["name"],
                district=district.name,
                lat=p["lat"],
                lng=p["lng"],
                tags=_tags_for_vibe(vibe, p),
                headline=narr["headline"],
                body=narr["body"],
                tip=narr["tip"],
                walkMin=0 if i == 0 else max(5, walk_min // max(1, len(ordered) - 1)),
                sourceLabel=p.get("sourceLabel", "blue"),
                verifiedAt=p.get("verifiedAt"),
                indoor=bool(p.get("indoor", True)),
            )
        )

    subtitle = f"精选 {curated_n} · OSM {len(stops) - curated_n} 站 · 步行约 {walk_min} 分钟"
    return RouteEnvelope(
        lineCode=line_code,
        lineName=line_name,
        title=f"{district.name} · {line_name}",
        subtitle=subtitle,
        totalMin=walk_min,
        vibe=vibe,
        districtId=district.id,
        stops=stops,
        geometry=osrm.get("geometry"),
        distanceM=osrm.get("distance_m", 0),
    )


def find_replacement(
    *,
    vibe: str,
    district: District,
    exclude_ids: set[str],
    prefer_indoor: bool = False,
    seed: int | None = None,
) -> dict[str, Any] | None:
    curated = load_curated(district.id, vibe)
    try:
        osm = fetch_pois(vibe, district)
    except RuntimeError:
        osm = []
    merged = _merge_pois(curated, osm)
    candidates = [p for p in merged if p["id"] not in exclude_ids]
    if prefer_indoor:
        candidates = [p for p in candidates if p.get("indoor", True)] or candidates
    if not candidates:
        return None
    rng = random.Random(seed or random.randint(0, 99999))
    return rng.choice(sorted(candidates, key=lambda p: p.get("weight", 1.0), reverse=True)[:5])
