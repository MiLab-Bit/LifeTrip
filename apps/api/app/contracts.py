"""Shared API contracts (Python mirror of @lifetrip/contracts)."""
from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


SourceLabel = Literal["green", "blue", "gray"]
PermissionLevel = Literal["L0", "L1", "L2", "L3"]
WalkTaskStatus = Literal["planned", "walking", "paused", "completed", "cancelled"]


class GeoGeometry(BaseModel):
    type: Literal["LineString"] = "LineString"
    coordinates: list[list[float]]


class Stop(BaseModel):
    id: str
    code: str
    name: str
    district: str
    lat: float
    lng: float
    tags: list[str] = Field(default_factory=list)
    headline: str
    body: str
    tip: str
    walkMin: int = 0
    sourceLabel: SourceLabel = "blue"
    verifiedAt: str | None = None
    indoor: bool = True
    skipped: bool = False


class RouteEnvelope(BaseModel):
    lineCode: str
    lineName: str
    title: str
    subtitle: str
    totalMin: int
    vibe: str
    districtId: str
    stops: list[Stop]
    geometry: GeoGeometry | None = None
    distanceM: int = 0
    source: Literal["live", "fixture", "cache"] | None = None
    fallback_reason: str | None = None


class BriefInput(BaseModel):
    vibe: str
    district_id: str
    duration_min: int = 90
    pace: str = "normal"
    intent_text: str | None = None


class PendingAction(BaseModel):
    kind: Literal["skip", "reroll", "apply_reroute"]
    level: PermissionLevel = "L2"
    message: str
    payload: dict[str, Any] = Field(default_factory=dict)


class WalkTask(BaseModel):
    id: str
    session_id: str
    status: WalkTaskStatus
    brief: BriefInput
    route: RouteEnvelope
    current_stop_index: int = 0
    pending_action: PendingAction | None = None
    created_at: str
    updated_at: str
    completed_at: str | None = None
    verify_passed: bool | None = None


class IntentKind(str, Enum):
    question = "question"
    plan_walk = "plan_walk"
    resume_walk = "resume_walk"


class IntentResult(BaseModel):
    kind: IntentKind
    confidence: float
    message: str | None = None


class RerouteProposal(BaseModel):
    task_id: str
    trigger: str
    message: str
    affected_stop_indices: list[int]
    proposed_route: RouteEnvelope
    requires_confirm: bool = True


class EvalCaseResult(BaseModel):
    id: str
    tier: Literal["fact", "decision", "emergency"]
    passed: bool
    detail: str


class EvalRunResult(BaseModel):
    total: int
    passed: int
    failed: int
    results: list[EvalCaseResult]
