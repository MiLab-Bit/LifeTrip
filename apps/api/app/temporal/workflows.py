"""LifeTrip Temporal Workflows - City Walk planning with LLM."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from temporalio import activity, workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    pass


@dataclass
class PlanRouteInput:
    vibe: str
    district: dict
    duration_min: int
    pace: str


@dataclass
class PolishStopsInput:
    route: dict
    vibe: str
    session_id: str = ""


@activity.defn
async def plan_route_activity(input: PlanRouteInput) -> dict:
    """Activity: Plan route with OSRM + curated POIs."""
    from app.districts import District
    from app.plan.planner import plan_route

    district = District(**input.district)
    route = await plan_route(
        vibe=input.vibe,
        district=district,
        duration_min=input.duration_min,
        pace=input.pace,
    )
    return route.model_dump()


@activity.defn
async def polish_stops_activity(input: PolishStopsInput) -> list[dict]:
    """Activity: Polish stops with LLM narratives."""
    from app.contracts import Stop
    from app.narrative.polish import polish_stops

    stops = [Stop(**s) for s in input.route.get('stops', [])]
    district_id = input.route.get('districtId', '')

    # Polish with LLM
    polished = await polish_stops(
        stops=stops,
        vibe=input.vibe,
        district=district_id,
        session_id=input.session_id,
    )

    return [s.model_dump() for s in polished]


@activity.defn
async def create_task_activity(
    session_id: str,
    brief: dict,
    route: dict,
) -> dict:
    """Activity: Create WalkTask in memory store."""
    from app.contracts import BriefInput, RouteEnvelope
    from app.memory import store

    brief_input = BriefInput(**brief)
    route_envelope = RouteEnvelope(**route)

    task = store.create_task(session_id, brief_input, route_envelope)
    return task.model_dump()


@workflow.defn
class WalkPlanWorkflow:
    """Main workflow: Plan a city walk with LLM-polished narratives."""

    @workflow.run
    async def run(self, session_id: str, brief: dict, district: dict) -> dict:
        # Step 1: Plan route
        route_input = PlanRouteInput(
            vibe=brief['vibe'],
            district=district,
            duration_min=brief['duration_min'],
            pace=brief.get('pace', 'normal'),
        )

        route = await workflow.execute_activity(
            plan_route_activity,
            route_input,
            start_to_close_timeout=timedelta(seconds=60),
            retry_policy=RetryPolicy(
                initial_interval=timedelta(seconds=2),
                maximum_interval=timedelta(seconds=10),
                maximum_attempts=3,
            ),
        )

        # Step 2: Polish stops with LLM
        polish_input = PolishStopsInput(route=route, vibe=brief['vibe'], session_id=session_id)

        polished_stops = await workflow.execute_activity(
            polish_stops_activity,
            polish_input,
            start_to_close_timeout=timedelta(seconds=300),  # LLM can be slow
            retry_policy=RetryPolicy(
                initial_interval=timedelta(seconds=5),
                maximum_interval=timedelta(seconds=30),
                maximum_attempts=2,
            ),
        )

        # Update route with polished stops
        route['stops'] = polished_stops

        # Step 3: Create task
        task = await workflow.execute_activity(
            create_task_activity,
            session_id,
            brief,
            route,
            start_to_close_timeout=timedelta(seconds=10),
        )

        return task
