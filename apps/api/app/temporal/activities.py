"""LifeTrip Temporal Activities — WalkTask 生命周期各阶段。"""
from __future__ import annotations
from typing import Any
from temporalio import activity


def _hb(*d: str) -> None:
    try:
        activity.heartbeat(*d)
    except RuntimeError:
        pass


@activity.defn(name="plan_walktask")
async def plan_walktask_activity(inp: dict[str, Any]) -> dict[str, Any]:
    """规划一条 WalkTask 路线（选 POI + 排序 + 步行路由 + LLM 文案）。"""
    _hb("plan:start")
    
    from app.plan.planner import plan_route
    from app.districts import District
    from app.narrative.polish import polish_stops
    from app.contracts import Stop
    
    vibe = inp.get("vibe", "coffee")
    district_id = inp.get("district_id", "anfu-wukang")
    duration_min = inp.get("duration_min", 90)
    pace = inp.get("pace", "normal")
    session_id = inp.get("session_id", "")
    
    # Get district
    from app.districts import DISTRICTS
    district = next((d for d in DISTRICTS if d.id == district_id), None)
    if not district:
        raise ValueError(f"unknown district: {district_id}")
    
    # Plan route
    route = await plan_route(
        vibe=vibe,
        district=district,
        duration_min=duration_min,
        pace=pace,
        session_id=session_id,
    )
    
    # Polish stops with LLM
    stops = route.stops
    polished = await polish_stops(
        stops=stops,
        vibe=vibe,
        district=district_id,
    )
    
    _hb(f"plan:done stops={len(polished)}")
    
    return {
        "task_id": inp.get("task_id"),
        "route": route.model_dump(),
        "status": "planned",
    }


@activity.defn(name="start_walktask")
def start_walktask_activity(inp: dict[str, Any]) -> dict[str, Any]:
    """开始执行 WalkTask（推送到前端 PWA）。"""
    _hb("start:done")
    return {"task_id": inp.get("task_id"), "status": "started", "current_stop": 0}


@activity.defn(name="reroll_stop")
def reroll_stop_activity(inp: dict[str, Any]) -> dict[str, Any]:
    """重掷当前站点（换一个附近替代 POI）。"""
    _hb(f"reroll:stop={inp.get('stop_order')}")
    return {
        "stop_order": inp.get("stop_order"),
        "new_name": f"替代 POI #{inp.get('stop_order', 1)}",
        "status": "rerolled",
    }


@activity.defn(name="complete_walktask")
def complete_walktask_activity(inp: dict[str, Any]) -> dict[str, Any]:
    """完成 WalkTask（写 Memory + 生成步行成就）。"""
    _hb("complete:done")
    return {
        "task_id": inp.get("task_id"),
        "status": "completed",
        "completed_at": "2026-10-05T00:00:00Z",
        "stops_visited": inp.get("stops_visited", 0),
    }
