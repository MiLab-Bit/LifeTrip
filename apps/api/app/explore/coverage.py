"""District coverage — which districts has the user walked."""
from __future__ import annotations

from app.contracts import DistrictCoverage, WalkTask
from app.districts import DISTRICTS


def compute_coverage(completed: list[WalkTask]) -> list[DistrictCoverage]:
    """Compute district coverage from completed walks."""
    counts: dict[str, int] = {}
    for task in completed:
        d = task.brief.district_id
        counts[d] = counts.get(d, 0) + 1

    result: list[DistrictCoverage] = []
    for d in DISTRICTS:
        result.append(DistrictCoverage(
            district_id=d.id,
            district_name=d.name,
            walks_completed=counts.get(d.id, 0),
            lit=counts.get(d.id, 0) > 0,
        ))
    return result
