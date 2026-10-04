"""LifeTrip Temporal Worker."""
from __future__ import annotations
import asyncio, concurrent.futures, logging, os
from temporalio.client import Client
from temporalio.worker import Worker
from app.temporal.activities import (
    plan_walktask_activity, start_walktask_activity,
    reroll_stop_activity, complete_walktask_activity,
)
from app.temporal.workflows.walktask import WalkTaskWorkflow

log = logging.getLogger("lifetrip.temporal.worker")


async def _run() -> None:
    address = os.getenv("TEMPORAL_ADDRESS", "127.0.0.1:7233")
    namespace = os.getenv("TEMPORAL_NAMESPACE", "lifetrip")
    task_queue = os.getenv("TEMPORAL_TASK_QUEUE", "lifetrip-task-queue")
    log.info("starting LifeTrip worker | tq=%s ns=%s addr=%s", task_queue, namespace, address)
    client = await Client.connect(address, namespace=namespace)
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
        worker = Worker(
            client, task_queue=task_queue,
            workflows=[WalkTaskWorkflow],
            activities=[plan_walktask_activity, start_walktask_activity, reroll_stop_activity, complete_walktask_activity],
            activity_executor=pool,
        )
        await worker.run()


def run() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(_run())


if __name__ == "__main__":
    run()
