"""WalkTaskWorkflow — LifeTrip 步行任务生命周期（Temporal 底座）。

plan -> start -> [skip/reroll]* -> complete
"""
from __future__ import annotations

from datetime import timedelta
from typing import Any

from temporalio import workflow
from temporalio.common import RetryPolicy

_ACT_TIMEOUT = timedelta(seconds=120)  # LLM can be slow
_ACT_RETRY = RetryPolicy(maximum_attempts=3)


def _get(inp: dict | Any, key: str, default=None):
    """Helper to access dict or object fields."""
    if isinstance(inp, dict):
        return inp.get(key, default)
    return getattr(inp, key, default)


@workflow.defn(name="WalkTaskWorkflow")
class WalkTaskWorkflow:
    """WalkTask 生命周期工作流（状态机模式，人在回路）。"""

    def __init__(self) -> None:
        self.task_id: str = ""
        self.status: str = "planning"
        self.plan: dict[str, Any] = {}
        self.route: dict[str, Any] = {}  # Keep route separately
        self.current_stop: int = 0
        self.history: list[dict[str, Any]] = []

    def _emit(self, event: str, data: dict[str, Any] | None = None) -> None:
        self.history.append({"event": event, "status": self.status, **(data or {})})

    @workflow.run
    async def run(self, inp: dict | Any) -> dict[str, Any]:
        self.task_id = _get(inp, "task_id")
        self._emit("init")

        # 1) plan - returns route
        plan_result = await workflow.execute_activity(
            "plan_walktask",
            {
                "task_id": self.task_id,
                "session_id": _get(inp, "session_id", ""),
                "area": _get(inp, "area", "anfu-wukang"),
                "vibe": _get(inp, "vibe", "coffee"),
                "district_id": _get(inp, "district_id", "anfu-wukang"),
                "duration_min": _get(inp, "duration_min", 90),
            },
            start_to_close_timeout=_ACT_TIMEOUT,
            retry_policy=_ACT_RETRY,
        )
        self.route = plan_result.get("route", {})
        self.status = "planned"
        self._emit("planned", {"stops": len(self.route.get("stops", []))})

        # 2) start (mark as active)
        await workflow.execute_activity(
            "start_walktask",
            {"task_id": self.task_id, "route": self.route},
            start_to_close_timeout=_ACT_TIMEOUT,
            retry_policy=_ACT_RETRY,
        )
        self.status = "active"
        self._emit("started")

        # 3) complete (for now, auto-complete)
        complete_result = await workflow.execute_activity(
            "complete_walktask",
            {
                "task_id": self.task_id,
                "route": self.route,
                "stops_visited": len(self.route.get("stops", [])),
            },
            start_to_close_timeout=_ACT_TIMEOUT,
            retry_policy=_ACT_RETRY,
        )
        self.status = "completed"
        self._emit("completed")

        return {
            "task_id": self.task_id,
            "status": self.status,
            "route": self.route,
            "history": self.history,
            **complete_result,
        }
