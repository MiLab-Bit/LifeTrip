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


# ── Sprint 1: WalkDNA ──────────────────────────────────────────

class WalkProfile(BaseModel):
    """User's accumulated walk preferences and stats (WalkDNA)."""
    session_id: str
    vibe_weights: dict[str, float] = Field(default_factory=dict)
    pace_preference: str = "normal"
    frequent_districts: list[str] = Field(default_factory=list)
    preferred_time_slots: list[str] = Field(default_factory=list)
    completed_walks: int = 0
    total_walk_minutes: int = 0
    total_distance_m: int = 0
    total_stops_visited: int = 0
    badges: list[str] = Field(default_factory=list)
    last_active_at: str | None = None
    created_at: str = ""
    updated_at: str = ""


# ── Sprint 2: Explore ──────────────────────────────────────────

class Badge(BaseModel):
    id: str
    name: str
    description: str
    icon: str = "🏅"
    earned: bool = False
    earned_at: str | None = None


class DistrictCoverage(BaseModel):
    district_id: str
    district_name: str
    walks_completed: int = 0
    lit: bool = False  # walked at least once


class ExploreStats(BaseModel):
    """Aggregated exploration data for the explore map / badge wall."""
    session_id: str
    total_walks: int = 0
    total_km: float = 0.0
    total_stops: int = 0
    total_minutes: int = 0
    districts: list[DistrictCoverage] = Field(default_factory=list)
    collected_pois: list[dict[str, Any]] = Field(default_factory=list)
    badges: list[Badge] = Field(default_factory=list)


# ── Sprint 3: Narrative v2 ─────────────────────────────────────

class LayeredNarrative(BaseModel):
    """Multi-depth narrative for a single POI arrival."""
    poi_id: str
    quick: str  # 1-sentence, ~15s glance
    standard: str  # 3-4 sentences, ~60s, default
    deep: str  # cultural/historical/architectural deep dive
    source_label: SourceLabel = "blue"
    source_note: str = ""


# ── Sprint 5: Community ────────────────────────────────────────

class RouteRating(BaseModel):
    task_id: str
    session_id: str
    overall: int  # 1-5
    poi_ratings: dict[str, int] = Field(default_factory=dict)  # poi_id -> 1-5
    comment: str = ""
    photos: list[str] = Field(default_factory=list)
    created_at: str = ""


class CommunityRoute(BaseModel):
    id: str
    session_id: str  # publisher
    route: RouteEnvelope
    rating: float = 0.0
    rating_count: int = 0
    walk_count: int = 0  # how many people walked it
    tags: list[str] = Field(default_factory=list)
    published_at: str = ""
    author_label: str = "匿名探索者"
