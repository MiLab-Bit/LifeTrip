"""Overpass API — 潮流 POI 检索 + 本地 cache."""
from __future__ import annotations

import os
from typing import Any

import httpx

from app.cache import read_cache, read_stale_cache, write_cache

OVERPASS_URLS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
)

VIBE_FILTERS: dict[str, list[str]] = {
    "neon": [
        'node["amenity"~"^(bar|pub|nightclub|restaurant)$"]',
        'way["amenity"~"^(bar|pub|nightclub|restaurant)$"]',
    ],
    "coffee": [
        'node["amenity"="cafe"]',
        'way["amenity"="cafe"]',
        'node["shop"="coffee"]',
    ],
    "vintage": [
        'node["shop"~"^(clothes|second_hand|charity|variety_store)$"]',
        'way["shop"~"^(clothes|second_hand|charity|variety_store)$"]',
    ],
    "gallery": [
        'node["tourism"~"^(gallery|museum)$"]',
        'way["tourism"~"^(gallery|museum)$"]',
        'node["amenity"="arts_centre"]',
        'way["amenity"="arts_centre"]',
    ],
}

UA = "LifeTrip/0.1 (city-walk demo; +https://github.com)"


def _bbox_clause(d) -> str:
    return f"{d.south},{d.west},{d.north},{d.east}"


def build_query(vibe: str, district) -> str:
    bbox = _bbox_clause(district)
    parts = VIBE_FILTERS.get(vibe, VIBE_FILTERS["coffee"])
    inner = "\n  ".join(f"{p}({bbox});" for p in parts)
    return f"""
[out:json][timeout:25];
(
  {inner}
);
out center 40;
""".strip()


def _parse_elements(raw: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for el in raw.get("elements") or []:
        tags = el.get("tags") or {}
        lat = el.get("lat")
        lng = el.get("lon")
        if lat is None or lng is None:
            c = el.get("center") or {}
            lat, lng = c.get("lat"), c.get("lon")
        if lat is None or lng is None:
            continue
        name = tags.get("name:zh") or tags.get("name") or tags.get("brand") or "未命名"
        out.append(
            {
                "id": f"osm/{el.get('type')}/{el.get('id')}",
                "name": name,
                "lat": float(lat),
                "lng": float(lng),
                "tags": tags,
                "tags_osm": tags,
                "origin": "osm",
            }
        )
    return out


def fetch_pois(vibe: str, district) -> list[dict[str, Any]]:
    cached = read_cache(district.id, vibe)
    if cached:
        return cached

    query = build_query(vibe, district)
    timeout = float(os.getenv("LIFETRIP_OVERPASS_TIMEOUT", "20"))
    last_err = "overpass failed"
    with httpx.Client(timeout=timeout, headers={"User-Agent": UA}) as client:
        for url in OVERPASS_URLS:
            try:
                r = client.post(url, data={"data": query})
                if r.status_code != 200:
                    last_err = f"{url} HTTP {r.status_code}"
                    continue
                pois = _parse_elements(r.json())
                if pois:
                    write_cache(district.id, vibe, pois)
                    return pois
                last_err = "empty result"
            except Exception as exc:  # noqa: BLE001
                last_err = str(exc)

    stale = read_stale_cache(district.id, vibe)
    if stale:
        return stale
    raise RuntimeError(last_err)


def overpass_status() -> dict[str, Any]:
    try:
        with httpx.Client(timeout=8.0, headers={"User-Agent": UA}) as client:
            r = client.get(f"{OVERPASS_URLS[0]}?data=[out:json];node(1);out;")
            return {"ok": r.status_code == 200, "status_code": r.status_code}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}
