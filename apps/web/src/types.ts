export type {
  AppStage,
  BriefInput,
  GeoGeometry,
  PendingAction,
  RerouteProposal,
  RouteEnvelope,
  SourceLabel,
  Stop,
  VibeId,
  WalkPlanResponse,
  WalkTask,
} from "@lifetrip/contracts";

/** @deprecated use RouteEnvelope */
export type LifeRoute = import("@lifetrip/contracts").RouteEnvelope;

export type DistrictOption = {
  id: string;
  name: string;
  city: string;
};

export type Vibe = {
  id: import("@lifetrip/contracts").VibeId;
  label: string;
  line: string;
  hint: string;
};
