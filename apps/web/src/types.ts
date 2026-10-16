export type {
  AppStage,
  Badge,
  BriefInput,
  CommunityRoute,
  CollectedPOI,
  DistrictCoverage,
  ExploreStats,
  GeoGeometry,
  LayeredNarrative,
  PendingAction,
  RerouteProposal,
  RouteEnvelope,
  RouteRating,
  SourceLabel,
  Stop,
  VibeId,
  WalkCardData,
  WalkPlanResponse,
  WalkProfile,
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
