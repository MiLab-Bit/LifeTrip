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
def plan_walktask_activity(inp: dict[str, Any]) -> dict[str, Any]:
    """规划一条 WalkTask 路线（选 POI + 排序 + 步行路由）。"""
    _hb("plan:start")
    area = inp.get("area", "unknown")
    vibe = inp.get("vibe", "casual")
    dur = inp.get("duration_min", 90)
    _hb(f"plan:done area={area}")
    return {
        "task_id": inp.get("task_id", "wt-001"),
        "area": area,
        "vibe": vibe,
        "duration_min": dur,
        "stops": [
            {"order": 1, "name": f"{area} 起点咖啡", "lat": 31.220, "lng": 121.460, "minutes": 15},
            {"order": 2, "name": f"{area} 地标建筑", "lat": 31.222, "lng": 121.462, "minutes": 25},
            {"order": 3, "name": f"{area} 隐藏小巷", "lat": 31.224, "lng": 121.464, "minutes": 20},
            {"order": 4, "name": f"{area} 终点甜品店", "lat": 31.226, "lng": 121.466, "minutes": 30},
        ],
        "total_walk_m": 1200,
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
