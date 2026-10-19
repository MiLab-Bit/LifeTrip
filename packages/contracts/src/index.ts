export type SourceLabel = "green" | "blue" | "gray";
export type PermissionLevel = "L0" | "L1" | "L2" | "L3";
export type WalkTaskStatus = "planned" | "walking" | "paused" | "completed" | "cancelled";

export type GeoGeometry = {
  type: "LineString";
  coordinates: [number, number][];
};

export type Stop = {
  id: string;
  code: string;
  name: string;
  district: string;
  lat: number;
  lng: number;
  tags: string[];
  headline: string;
  body: string;
  tip: string;
  walkMin: number;
  sourceLabel?: SourceLabel;
  verifiedAt?: string | null;
  indoor?: boolean;
  skipped?: boolean;
};

export type RouteEnvelope = {
  lineCode: string;
  lineName: string;
  title: string;
  subtitle: string;
  totalMin: number;
  vibe: string;
  districtId: string;
  stops: Stop[];
  geometry?: GeoGeometry | null;
  distanceM?: number;
  source?: "live" | "fixture" | "cache";
  fallback_reason?: string;
};

export type BriefInput = {
  vibe: string;
  districtId: string;
  durationMin: number;
  pace: "slow" | "normal" | "fast";
  intentText?: string;
};

export type PendingAction = {
  kind: "skip" | "reroll" | "apply_reroute";
  level: PermissionLevel;
  message: string;
  payload: Record<string, unknown>;
};

export type WalkTask = {
  id: string;
  session_id: string;
  status: WalkTaskStatus;
  brief: {
    vibe: string;
    district_id: string;
    duration_min: number;
    pace: string;
    intent_text?: string | null;
  };
  route: RouteEnvelope;
  current_stop_index: number;
  pending_action?: PendingAction | null;
  created_at: string;
  updated_at: string;
  completed_at?: string | null;
  verify_passed?: boolean | null;
};

export type RerouteProposal = {
  task_id: string;
  trigger: string;
  message: string;
  affected_stop_indices: number[];
  proposed_route: RouteEnvelope;
  requires_confirm: boolean;
};

export type WalkPlanResponse = {
  session_id: string;
  intent: { kind: string; confidence: number; message?: string };
  resumed: boolean;
  task: WalkTask;
};

export type VibeId = "neon" | "coffee" | "vintage" | "gallery";

export type AppStage = "brief" | "loading" | "route" | "walk" | "done" | "confirm" | "explore" | "community";

// ── Sprint 1: WalkDNA ──────────────────────────────────────────

export type WalkProfile = {
  session_id: string;
  vibe_weights: Record<string, number>;
  pace_preference: string;
  frequent_districts: string[];
  preferred_time_slots: string[];
  completed_walks: number;
  total_walk_minutes: number;
  total_distance_m: number;
  total_stops_visited: number;
  badges: string[];
  last_active_at?: string | null;
  created_at: string;
  updated_at: string;
};

// ── Sprint 2: Explore ──────────────────────────────────────────

export type Badge = {
  id: string;
  name: string;
  description: string;
  icon: string;
  earned: boolean;
  earned_at?: string | null;
};

export type DistrictCoverage = {
  district_id: string;
  district_name: string;
  walks_completed: number;
  lit: boolean;
};

export type CollectedPOI = {
  id: string;
  name: string;
  district: string;
  tags: string[];
  source_label?: string;
  lat: number;
  lng: number;
};

export type ExploreStats = {
  session_id: string;
  total_walks: number;
  total_km: number;
  total_stops: number;
  total_minutes: number;
  districts: DistrictCoverage[];
  collected_pois: CollectedPOI[];
  badges: Badge[];
};

// ── Sprint 3: Narrative v2 ─────────────────────────────────────

export type LayeredNarrative = {
  poi_id: string;
  quick: string;
  standard: string;
  deep: string;
  source_label: SourceLabel;
  source_note: string;
};

// ── Sprint 5: Community ────────────────────────────────────────

export type RouteRating = {
  task_id: string;
  session_id: string;
  overall: number;
  poi_ratings: Record<string, number>;
  comment: string;
  photos: string[];
  created_at: string;
};

export type CommunityRoute = {
  id: string;
  session_id: string;
  route: RouteEnvelope;
  rating: number;
  rating_count: number;
  walk_count: number;
  tags: string[];
  published_at: string;
  author_label: string;
};

// ── Sprint 4: Walk Card ────────────────────────────────────────

export type WalkCardData = {
  task: WalkTask;
  profile: WalkProfile | null;
  card_id: string;
};
