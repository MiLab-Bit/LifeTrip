"""LifeTrip API — WalkTask agent backend."""
from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.contracts import BriefInput, RouteEnvelope
from app.districts import DISTRICTS, District
from app.eval.harness import run_eval
from app.intent import classify_intent
from app.memory import store
from app.paths import FIXTURES
from app.plan.planner import plan_route
from app.proactive.weather import check_weather_reroute
from app.osm import overpass_status
from app.walk import service as walk_service
from app.api.v1.isochrone import router as isochrone_router

ROOT = Path(__file__).resolve().parents[2]

app = FastAPI(title="LifeTrip API", version="0.4.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(isochrone_router, prefix="/v1")


@app.on_event("startup")
async def startup():
    store.init_db()


class PlanRequest(BaseModel):
    vibe: str = Field(description="neon | coffee | vintage | gallery")
    district_id: str
    duration_min: int = Field(default=90, ge=45, le=180)
    pace: str = Field(default="normal", description="slow | normal | fast")
    intent_text: str | None = None
    session_id: str | None = None


class ConfirmBody(BaseModel):
    confirm: bool = False


class WalkPlanBody(BaseModel):
    vibe: str
    district_id: str
    duration_min: int = 90
    pace: str = "normal"
    intent_text: str | None = None
    session_id: str | None = None


def _district_or_404(district_id: str) -> District:
    district = next((d for d in DISTRICTS if d.id == district_id), None)
    if not district:
        raise HTTPException(404, f"unknown district: {district_id}")
    return district


def _load_fixture(vibe: str, district_id: str) -> dict:
    fixture_path = FIXTURES / f"{vibe}-{district_id}.json"
    if not fixture_path.exists():
        fixture_path = FIXTURES / f"{vibe}-default.json"
    return json.loads(fixture_path.read_text(encoding="utf-8"))


async def _plan_with_fallback(body: PlanRequest) -> RouteEnvelope:
    district = _district_or_404(body.district_id)
    if body.vibe not in ("neon", "coffee", "vintage", "gallery"):
        raise HTTPException(400, f"unknown vibe: {body.vibe}")

    force_offline = os.getenv("LIFETRIP_OFFLINE", "0") == "1"
    try:
        if force_offline:
            raise RuntimeError("offline mode")
        route = await plan_route(
            vibe=body.vibe,
            district=district,
            duration_min=body.duration_min,
            pace=body.pace,
        )
        route.source = "live"
        return route
    except Exception as exc:  # noqa: BLE001
        data = _load_fixture(body.vibe, body.district_id)
        route = RouteEnvelope.model_validate(data)
        route.source = "fixture"
        route.fallback_reason = str(exc)[:200]
        return route


@app.get("/v1/health")
async def health():
    offline = os.getenv("LIFETRIP_OFFLINE", "0") == "1"
    llm_on = os.getenv("LIFETRIP_LLM_POLISH", "0") == "1" and bool(os.getenv("LIFETRIP_LLM_API_KEY"))
    return {
        "ok": True,
        "service": "lifetrip-api",
        "version": "0.4.0",
        "offline_mode": offline,
        "features": ["walk_tasks", "memory", "eval", "proactive", "narrative_polish"],
        "llm_polish": llm_on,
        "data_sources": {
            "poi": "OpenStreetMap Overpass + curated",
            "routing": "OSRM foot",
            "weather": "Open-Meteo",
            "narrative": "editor + local + optional LLM",
            "tiles": "CARTO Dark Matter (client)",
        },
    }


@app.get("/v1/districts")
async def list_districts():
    return {"districts": [d.model_dump() for d in DISTRICTS]}


@app.get("/v1/osm/status")
async def osm_status():
    return await overpass_status()


@app.post("/v1/routes/plan")
async def routes_plan(body: PlanRequest):
    """Legacy plan endpoint — returns route envelope only."""
    return (await _plan_with_fallback(body)).model_dump()


@app.post("/v1/walks/plan")
async def walks_plan(body: WalkPlanBody):
    session_id = store.ensure_session(body.session_id)
    resumable = store.find_resumable(session_id)
    intent = classify_intent(body.intent_text, has_active_task=resumable is not None)
    if intent.kind.value == "question":
        raise HTTPException(
            400,
            detail={"code": "intent_question", "message": intent.message or "问答请使用搜索"},
        )
    if intent.kind.value == "resume_walk" and resumable:
        return {
            "session_id": session_id,
            "intent": intent.model_dump(),
            "resumed": True,
            "task": resumable.model_dump(),
        }

    brief = BriefInput(
        vibe=body.vibe,
        district_id=body.district_id,
        duration_min=body.duration_min,
        pace=body.pace,
        intent_text=body.intent_text,
    )
    try:
        task = await walk_service.plan_walk_task(session_id, brief)
    except Exception as exc:  # noqa: BLE001
        route = await _plan_with_fallback(PlanRequest(**body.model_dump()))
        task = store.create_task(session_id, brief, route)
    return {
        "session_id": session_id,
        "intent": intent.model_dump(),
        "resumed": False,
        "task": task.model_dump(),
    }


@app.get("/v1/walks/resume")
async def walks_resume(session_id: str = Query(...)):
    store.ensure_session(session_id)
    task = store.find_resumable(session_id)
    if not task:
        return {"task": None, "message": "没有进行中的走线任务"}
    return {"task": task.model_dump()}


@app.get("/v1/walks/{task_id}")
async def walks_get(task_id: str):
    task = store.get_task(task_id)
    if not task:
        raise HTTPException(404, "task not found")
    return task.model_dump()


@app.post("/v1/walks/{task_id}/start")
async def walks_start(task_id: str):
    try:
        task = walk_service.start_walk(task_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    return task.model_dump()


@app.post("/v1/walks/{task_id}/advance")
async def walks_advance(task_id: str):
    try:
        task = walk_service.advance_stop(task_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    return task.model_dump()


@app.post("/v1/walks/{task_id}/skip")
async def walks_skip(task_id: str, body: ConfirmBody):
    try:
        task = await walk_service.request_skip(task_id, confirm=body.confirm)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return task.model_dump()


@app.post("/v1/walks/{task_id}/reroll")
async def walks_reroll(task_id: str, body: ConfirmBody):
    try:
        task = await walk_service.request_reroll(task_id, confirm=body.confirm)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return task.model_dump()


@app.post("/v1/walks/{task_id}/complete")
async def walks_complete(task_id: str):
    try:
        task = walk_service.complete_walk(task_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    return task.model_dump()


@app.post("/v1/walks/{task_id}/cancel")
async def walks_cancel(task_id: str):
    try:
        task = walk_service.cancel_walk(task_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    return task.model_dump()


@app.get("/v1/walks/{task_id}/proactive")
async def walks_proactive(task_id: str):
    task = store.get_task(task_id)
    if not task:
        raise HTTPException(404, "task not found")
    proposal = await check_weather_reroute(task)
    if not proposal:
        return {"proposal": None}
    return {"proposal": proposal.model_dump()}


class ApplyRerouteBody(BaseModel):
    confirm: bool = False
    proposal: RouteEnvelope


@app.post("/v1/walks/{task_id}/apply-reroute")
async def walks_apply_reroute(task_id: str, body: ApplyRerouteBody):
    task = store.get_task(task_id)
    if not task:
        raise HTTPException(404, "task not found")
    check = await check_weather_reroute(task)
    message = check.message if check else "应用改线提案"
    try:
        updated = walk_service.apply_reroute(
            task_id, body.proposal, confirm=body.confirm, message=message
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return updated.model_dump()


@app.post("/v1/eval/run")
async def eval_run(tier: str | None = None, limit: int | None = None):
    result = run_eval(tier=tier, limit=limit)
    return result.model_dump()


# ── Sprint 1: WalkDNA ──────────────────────────────────────────

@app.get("/v1/profile/{session_id}")
async def get_profile(session_id: str):
    profile = store.get_profile(session_id)
    if not profile:
        # Auto-derive on first access
        profile = store.derive_profile(session_id)
    return profile.model_dump()


@app.post("/v1/profile/{session_id}/refresh")
async def refresh_profile(session_id: str):
    profile = store.derive_profile(session_id)
    return profile.model_dump()


# ── Sprint 2: Explore ──────────────────────────────────────────

@app.get("/v1/explore/{session_id}")
async def get_explore(session_id: str):
    from app.explore.badges import compute_badges
    from app.explore.collection import compute_collection, compute_stats
    from app.explore.coverage import compute_coverage
    from app.contracts import ExploreStats

    completed = store.list_recent_completed(session_id, limit=100)
    profile = store.get_profile(session_id)

    stats = compute_stats(completed)
    badges = compute_badges(profile, completed) if profile else []
    coverage = compute_coverage(completed)
    collection = compute_collection(completed)

    return ExploreStats(
        session_id=session_id,
        total_walks=stats["total_walks"],
        total_km=stats["total_km"],
        total_stops=stats["total_stops"],
        total_minutes=stats["total_minutes"],
        districts=coverage,
        collected_pois=collection,
        badges=badges,
    ).model_dump()


# ── Sprint 3: Narrative v2 ─────────────────────────────────────

@app.get("/v1/walks/{task_id}/stops/{stop_idx}/narrative")
async def get_stop_narrative(task_id: str, stop_idx: int):
    from app.narrative.layers import generate_layered

    task = store.get_task(task_id)
    if not task:
        raise HTTPException(404, "task not found")
    if stop_idx < 0 or stop_idx >= len(task.route.stops):
        raise HTTPException(400, "stop index out of range")

    stop = task.route.stops[stop_idx]
    narrative = await generate_layered(stop, vibe=task.brief.vibe)
    return narrative.model_dump()


# ── Sprint 4: Walk Card (data endpoint — image generated client-side) ──

@app.get("/v1/walks/{task_id}/card-data")
async def get_card_data(task_id: str):
    task = store.get_task(task_id)
    if not task:
        raise HTTPException(404, "task not found")
    profile = store.get_profile(task.session_id)
    return {
        "task": task.model_dump(),
        "profile": profile.model_dump() if profile else None,
        "card_id": str(__import__("uuid").uuid4())[:8],
    }


# ── Sprint 5: Ratings ─────────────────────────────────────────

class RatingBody(BaseModel):
    overall: int  # 1-5
    poi_ratings: dict[str, int] = {}
    comment: str = ""
    photos: list[str] = []


@app.post("/v1/walks/{task_id}/rate")
async def rate_walk(task_id: str, session_id: str, body: RatingBody):
    from app.community.service import submit_rating
    rating = submit_rating(
        task_id, session_id, body.overall,
        body.poi_ratings, body.comment, body.photos,
    )
    return rating.model_dump()


# ── Sprint 5: Community Routes ─────────────────────────────────

class PublishBody(BaseModel):
    tags: list[str] = []
    author_label: str = "匿名探索者"


@app.get("/v1/community/routes")
async def list_community_routes(limit: int = 20, offset: int = 0):
    from app.community.service import list_routes
    routes = list_routes(limit=limit, offset=offset)
    return {"routes": [r.model_dump() for r in routes], "count": len(routes)}


@app.post("/v1/community/publish/{task_id}")
async def publish_route(task_id: str, session_id: str, body: PublishBody):
    from app.community.service import publish_route as do_publish
    task = store.get_task(task_id)
    if not task:
        raise HTTPException(404, "task not found")
    if task.status != "completed":
        raise HTTPException(400, "can only publish completed routes")
    route = do_publish(session_id, task.route, body.tags, body.author_label)
    return route.model_dump()


@app.post("/v1/community/routes/{route_id}/rate")
async def rate_community_route(route_id: str, rating: int):
    from app.community.service import rate_route
    result = rate_route(route_id, rating)
    if not result:
        raise HTTPException(404, "route not found")
    avg = result["rating_sum"] / result["rating_count"] if result["rating_count"] else 0
    return {"route_id": route_id, "avg_rating": round(avg, 1), "count": result["rating_count"]}


@app.post("/v1/community/routes/{route_id}/walk")
async def community_route_walked(route_id: str):
    store.increment_walk_count(route_id)
    return {"ok": True}
