"""LifeTrip API — 潮流 city walk 规划（OSM + OSRM，无上图 API）."""
from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.districts import DISTRICTS, District
from app.planner import plan_route
from app.osm import overpass_status

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "content" / "fixtures"

app = FastAPI(title="LifeTrip API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class PlanRequest(BaseModel):
    vibe: str = Field(description="neon | coffee | vintage | gallery")
    district_id: str
    duration_min: int = Field(default=90, ge=45, le=180)
    pace: str = Field(default="normal", description="slow | normal | fast")


@app.get("/v1/health")
def health():
    offline = os.getenv("LIFETRIP_OFFLINE", "0") == "1"
    return {
        "ok": True,
        "service": "lifetrip-api",
        "offline_mode": offline,
        "data_sources": {
            "poi": "OpenStreetMap Overpass",
            "routing": "OSRM foot (demo)",
            "tiles": "CARTO Dark Matter (client)",
        },
        "slc_api": False,
    }


@app.get("/v1/districts")
def list_districts():
    return {"districts": [d.model_dump() for d in DISTRICTS]}


@app.get("/v1/osm/status")
def osm_status():
    return overpass_status()


@app.post("/v1/routes/plan")
def routes_plan(body: PlanRequest):
    district = next((d for d in DISTRICTS if d.id == body.district_id), None)
    if not district:
        raise HTTPException(404, f"unknown district: {body.district_id}")
    if body.vibe not in ("neon", "coffee", "vintage", "gallery"):
        raise HTTPException(400, f"unknown vibe: {body.vibe}")

    force_offline = os.getenv("LIFETRIP_OFFLINE", "0") == "1"
    fixture_path = FIXTURES / f"{body.vibe}-{body.district_id}.json"
    if not fixture_path.exists():
        fixture_path = FIXTURES / f"{body.vibe}-default.json"

    try:
        if force_offline:
            raise RuntimeError("offline mode")
        route = plan_route(
            vibe=body.vibe,
            district=district,
            duration_min=body.duration_min,
            pace=body.pace,
        )
        route["source"] = "live"
        return route
    except Exception as exc:  # noqa: BLE001
        if not fixture_path.is_file():
            raise HTTPException(
                503,
                f"planning failed and no fixture: {exc}",
            ) from exc
        data = json.loads(fixture_path.read_text(encoding="utf-8"))
        data["source"] = "fixture"
        data["fallback_reason"] = str(exc)[:200]
        return data
