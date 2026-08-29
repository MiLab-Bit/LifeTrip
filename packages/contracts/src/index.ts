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

export type AppStage = "brief" | "loading" | "route" | "walk" | "done" | "confirm";
