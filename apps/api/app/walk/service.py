"""WalkTask lifecycle — plan, skip, reroll, complete."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.contracts import BriefInput, PendingAction, RouteEnvelope, Stop, WalkTask
from app.districts import DISTRICTS
from app.memory import store
from app.plan.planner import find_replacement, plan_route
from app.verify.verify import verify_completion, verify_route
from app.walk import permissions


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _district(district_id: str):
    return next((d for d in DISTRICTS if d.id == district_id), None)


def plan_walk_task(session_id: str, brief: BriefInput) -> WalkTask:
    district = _district(brief.district_id)
    if not district:
        raise ValueError(f"unknown district: {brief.district_id}")
    route = plan_route(
        vibe=brief.vibe,
        district=district,
        duration_min=brief.duration_min,
        pace=brief.pace,
    )
    ok, _ = verify_route(route)
    route.source = "live" if ok else route.source
    return store.create_task(session_id, brief, route)


def start_walk(task_id: str) -> WalkTask:
    task = store.get_task(task_id)
    if not task:
        raise ValueError("task not found")
    return store.update_task(task_id, status="walking", pending_action=None)  # type: ignore[return-value]


def advance_stop(task_id: str) -> WalkTask:
    task = store.get_task(task_id)
    if not task:
        raise ValueError("task not found")
    nxt = min(task.current_stop_index + 1, len(task.route.stops) - 1)
    return store.update_task(task_id, current_stop_index=nxt, status="walking")  # type: ignore[return-value]


def request_skip(task_id: str, *, confirm: bool = False) -> WalkTask:
    task = store.get_task(task_id)
    if not task:
        raise ValueError("task not found")
    idx = task.current_stop_index
    stop = task.route.stops[idx]
    if not confirm:
        pending = permissions.pending_skip(stop.name, idx)
        return store.update_task(task_id, pending_action=pending)  # type: ignore[return-value]

    stops = list(task.route.stops)
    stops[idx] = stop.model_copy(update={"skipped": True})
    active = [s for s in stops if not s.skipped]
    if len(active) < 2:
        raise ValueError("cannot skip: too few stops remaining")

    district = _district(task.brief.district_id)
    if not district:
        raise ValueError("district missing")
    exclude = {s.id for s in stops}
    route = plan_route(
        vibe=task.brief.vibe,
        district=district,
        duration_min=task.brief.duration_min,
        pace=task.brief.pace,
        exclude_ids=exclude,
        seed=hash(task_id) % 10000,
    )
    # preserve skipped markers on names if possible
    return store.update_task(
        task_id,
        route=route,
        pending_action=None,
        status="walking",
    )  # type: ignore[return-value]


def request_reroll(task_id: str, *, confirm: bool = False, stop_index: int | None = None) -> WalkTask:
    task = store.get_task(task_id)
    if not task:
        raise ValueError("task not found")
    idx = stop_index if stop_index is not None else task.current_stop_index
    stop = task.route.stops[idx]
    district = _district(task.brief.district_id)
    if not district:
        raise ValueError("district missing")
    exclude = {s.id for s in task.route.stops}
    replacement = find_replacement(
        vibe=task.brief.vibe,
        district=district,
        exclude_ids=exclude,
        seed=hash(f"{task_id}-{idx}") % 10000,
    )
    if not replacement:
        raise ValueError("no replacement poi")

    if not confirm:
        pending = permissions.pending_reroll(stop.name, idx, replacement["name"])
        pending.payload["replacement_id"] = replacement["id"]
        return store.update_task(task_id, pending_action=pending)  # type: ignore[return-value]

    from app.plan.planner import _narrative, _tags_for_vibe  # noqa: PLC0415

    narr = _narrative(task.brief.vibe, replacement)
    new_stop = Stop(
        id=replacement["id"],
        code=stop.code,
        name=replacement["name"],
        district=stop.district,
        lat=replacement["lat"],
        lng=replacement["lng"],
        tags=_tags_for_vibe(task.brief.vibe, replacement),
        headline=narr["headline"],
        body=narr["body"],
        tip=narr["tip"],
        walkMin=stop.walkMin,
        sourceLabel=replacement.get("sourceLabel", "blue"),
        verifiedAt=replacement.get("verifiedAt"),
        indoor=bool(replacement.get("indoor", True)),
    )
    stops = list(task.route.stops)
    stops[idx] = new_stop
    route = task.route.model_copy(update={"stops": stops})
    return store.update_task(task_id, route=route, pending_action=None)  # type: ignore[return-value]


def apply_reroute(task_id: str, proposed: RouteEnvelope, *, confirm: bool, message: str) -> WalkTask:
    if not confirm:
        pending = permissions.pending_reroute(message, str(uuid.uuid4()))
        return store.update_task(task_id, pending_action=pending)  # type: ignore[return-value]
    return store.update_task(task_id, route=proposed, pending_action=None, status="walking")  # type: ignore[return-value]


def complete_walk(task_id: str) -> WalkTask:
    task = store.get_task(task_id)
    if not task:
        raise ValueError("task not found")
    task = store.update_task(
        task_id,
        status="completed",
        current_stop_index=len(task.route.stops) - 1,
        completed_at=_now(),
        pending_action=None,
    )
    passed, _ = verify_completion(task)  # type: ignore[arg-type]
    return store.update_task(task_id, verify_passed=passed)  # type: ignore[return-value]


def cancel_walk(task_id: str) -> WalkTask:
    return store.update_task(task_id, status="cancelled", pending_action=None)  # type: ignore[return-value]
