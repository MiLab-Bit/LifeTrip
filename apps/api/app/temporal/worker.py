"""LifeTrip Temporal Worker（统一到 openclaw_core.temporal.run_worker）。"""
from __future__ import annotations

from openclaw_core.temporal import run_worker

from app.temporal.activities import (
    complete_walktask_activity,
    plan_walktask_activity,
    reroll_stop_activity,
    start_walktask_activity,
)
from app.temporal.workflows.walktask import WalkTaskWorkflow


def run() -> None:
    run_worker(
        [WalkTaskWorkflow],
        [
            plan_walktask_activity,
            start_walktask_activity,
            reroll_stop_activity,
            complete_walktask_activity,
        ],
        task_queue="lifetrip-task-queue",
        namespace="default",
        address="127.0.0.1:7233",
        connect_retries=30,
        activity_workers=10,
    )


if __name__ == "__main__":
    run()
