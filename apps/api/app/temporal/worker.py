"""LifeTrip Temporal Worker."""
from __future__ import annotations
import asyncio, concurrent.futures, logging, os, time
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
    namespace = os.getenv("TEMPORAL_NAMESPACE", "default")
    task_queue = os.getenv("TEMPORAL_TASK_QUEUE", "lifetrip-task-queue")
    
    # Retry loop for connection
    max_retries = 30
    for attempt in range(max_retries):
        try:
            log.info("connecting to Temporal | tq=%s ns=%s addr=%s (attempt %d/%d)", 
                     task_queue, namespace, address, attempt+1, max_retries)
            client = await Client.connect(address, namespace=namespace)
            log.info("✅ Connected to Temporal")
            break
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            log.warning("Temporal connection failed, retrying in 2s: %s", e)
            await asyncio.sleep(2)
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
        worker = Worker(
            client, task_queue=task_queue,
            workflows=[WalkTaskWorkflow],
            activities=[
                plan_walktask_activity, start_walktask_activity,
                reroll_stop_activity, complete_walktask_activity,
            ],
            activity_executor=pool,
        )
        log.info("🚀 LifeTrip worker running on task queue: %s", task_queue)
        await worker.run()


def run() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(_run())


if __name__ == "__main__":
    run()
