"""Eval harness — regression over fact / decision / emergency cases."""
from __future__ import annotations

import json
from typing import Any

from app.contracts import EvalCaseResult, EvalRunResult
from app.curated import load_curated
from app.districts import DISTRICTS
from app.intent import classify_intent
from app.paths import EVAL
from app.plan.planner import plan_route
from app.verify.verify import verify_route


def _load_cases() -> list[dict[str, Any]]:
    path = EVAL / "cases.json"
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("cases") or []


def _run_fact(case: dict[str, Any]) -> EvalCaseResult:
    cid = case["id"]
    district_id = case.get("districtId", "anfu-wukang")
    vibe = case.get("vibe", "coffee")
    curated = load_curated(district_id, vibe)
    expect_id = case.get("expectPoiId")
    if expect_id:
        found = any(p["id"] == expect_id for p in curated)
        return EvalCaseResult(
            id=cid,
            tier="fact",
            passed=found,
            detail="curated poi present" if found else f"missing {expect_id}",
        )
    expect_min = int(case.get("expectMinCurated", 1))
    n = len(curated)
    return EvalCaseResult(
        id=cid,
        tier="fact",
        passed=n >= expect_min,
        detail=f"curated count={n}, need>={expect_min}",
    )


def _run_decision(case: dict[str, Any]) -> EvalCaseResult:
    cid = case["id"]
    text = case.get("input", "")
    kind = case.get("expectIntent", "plan_walk")
    result = classify_intent(text)
    passed = result.kind.value == kind
    return EvalCaseResult(
        id=cid,
        tier="decision",
        passed=passed,
        detail=f"got {result.kind.value}, want {kind}",
    )


def _run_emergency(case: dict[str, Any]) -> EvalCaseResult:
    cid = case["id"]
    district = next((d for d in DISTRICTS if d.id == case.get("districtId", "anfu-wukang")), None)
    if not district:
        return EvalCaseResult(id=cid, tier="emergency", passed=False, detail="district missing")
    try:
        route = plan_route(
            vibe=case.get("vibe", "coffee"),
            district=district,
            duration_min=int(case.get("durationMin", 90)),
            pace="normal",
            prefer_indoor=bool(case.get("preferIndoor")),
            seed=int(case.get("seed", 7)),
        )
        ok, issues = verify_route(route)
        if case.get("expectIndoor"):
            indoor_n = sum(1 for s in route.stops if s.indoor)
            ok = ok and indoor_n >= int(case.get("expectMinIndoor", 2))
            detail = f"indoor={indoor_n}, issues={issues}"
        else:
            detail = f"issues={issues}"
        return EvalCaseResult(id=cid, tier="emergency", passed=ok, detail=detail)
    except Exception as exc:  # noqa: BLE001
        return EvalCaseResult(id=cid, tier="emergency", passed=False, detail=str(exc)[:120])


def run_eval(*, tier: str | None = None, limit: int | None = None) -> EvalRunResult:
    cases = _load_cases()
    if tier:
        cases = [c for c in cases if c.get("tier") == tier]
    if limit:
        cases = cases[:limit]

    results: list[EvalCaseResult] = []
    runners = {
        "fact": _run_fact,
        "decision": _run_decision,
        "emergency": _run_emergency,
    }
    for case in cases:
        fn = runners.get(case.get("tier", "fact"), _run_fact)
        results.append(fn(case))

    passed = sum(1 for r in results if r.passed)
    return EvalRunResult(
        total=len(results),
        passed=passed,
        failed=len(results) - passed,
        results=results,
    )
