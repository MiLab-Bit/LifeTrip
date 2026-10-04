"""WalkTaskWorkflow — LifeTrip 步行任务生命周期（Temporal 底座）。

plan -> start -> [skip/reroll]* -> complete
"""
from __future__ import annotations
from datetime import timedelta
from typing import Any
from temporalio import workflow
from temporalio.common import RetryPolicy

_ACT_TIMEOUT = timedelta(seconds=30)
_ACT_RETRY = RetryPolicy(maximum_attempts=3)


@workflow.defn(name="WalkTaskWorkflow")
class WalkTaskWorkflow:
    """WalkTask 生命周期工作流（状态机模式，人在回路）。"""

    def __init__(self) -> None:
        self.task_id: str = ""
        self.status: str = "planning"
        self.plan: dict[str, Any] = {}
        self.current_stop: int = 0
        self.history: list[dict[str, Any]] = []

    def _emit(self, event: str, data: dict[str, Any] | None = None) -> None:
        self.history.append({"event": event, "status": self.status, **(data or {})})

    @workflow.run
    async def run(self, inp: Any) -> dict[str, Any]:
        self.task_id = inp.task_id
        self._emit("init")

        # 1) plan
        self.plan = await workflow.execute_activity(
            "plan_walktask",
            {"task_id": inp.task_id, "area": inp.area, "vibe": inp.vibe, "duration_min": inp.duration_min},
            start_to_close_timeout=_ACT_TIMEOUT, retry_policy=_ACT_RETRY,
        )
        self.status = "planned"
        self._emit("planned", {"stops": len(self.plan.get("stops", []))})

        # 2) start
        await workflow.execute_activity(
            "start_walktask", {"task_id": self.task_id},
            start_to_close_timeout=_ACT_TIMEOUT, retry_policy=_ACT_RETRY,
        )
        self.status = "walking"
        self._emit("started")

        # 3) 等待完成信号
        await workflow.wait_condition(lambda: self.status == "completing")
        result = await workflow.execute_activity(
            "complete_walktask",
            {"task_id": self.task_id, "stops_visited": self.current_stop},
            start_to_close_timeout=_ACT_TIMEOUT, retry_policy=_ACT_RETRY,
        )
        self.status = "completed"
        self._emit("completed")
        return self._snapshot()

    @workflow.update
    async def skip_stop(self, stop_order: int) -> dict[str, Any]:
        self.current_stop = max(self.current_stop, stop_order + 1)
        self._emit("skip", {"stop": stop_order})
        return {"skipped": stop_order, "current": self.current_stop}

    @workflow.update
    async def reroll_stop(self, stop_order: int) -> dict[str, Any]:
        result = await workflow.execute_activity(
            "reroll_stop", {"stop_order": stop_order},
            start_to_close_timeout=_ACT_TIMEOUT, retry_policy=_ACT_RETRY,
        )
        self._emit("reroll", {"stop": stop_order, "new": result.get("new_name")})
        return result

    @workflow.update
    async def complete(self) -> None:
        self.status = "completing"

    @workflow.query
    def get_status(self) -> str:
        return self.status

    @workflow.query
    def get_plan(self) -> dict[str, Any]:
        return self.plan

    @workflow.query
    def get_snapshot(self) -> dict[str, Any]:
        return self._snapshot()

    def _snapshot(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "status": self.status,
            "plan": self.plan,
            "current_stop": self.current_stop,
            "history": self.history,
        }
