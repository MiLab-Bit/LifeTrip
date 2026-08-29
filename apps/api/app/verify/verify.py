"""Route verification."""
from __future__ import annotations

from app.contracts import RouteEnvelope, WalkTask


def verify_route(route: RouteEnvelope) -> tuple[bool, list[str]]:
    issues: list[str] = []
    if len(route.stops) < 2:
        issues.append("too_few_stops")
    active = [s for s in route.stops if not s.skipped]
    if len(active) < 2:
        issues.append("too_few_active_stops")
    if route.geometry is None or not route.geometry.coordinates:
        issues.append("missing_geometry")
    elif len(route.geometry.coordinates) < 2:
        issues.append("degenerate_geometry")
    for s in route.stops:
        if s.sourceLabel == "gray":
            issues.append(f"unverified_stop:{s.id}")
    return len(issues) == 0, issues


def verify_completion(task: WalkTask) -> tuple[bool, list[str]]:
    ok, issues = verify_route(task.route)
    if task.current_stop_index < len(task.route.stops) - 1:
        last = task.route.stops[-1]
        if not last.skipped and task.status != "completed":
            issues.append("not_at_terminal")
            ok = False
    return ok, issues
