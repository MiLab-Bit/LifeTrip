export type VibeId = "neon" | "coffee" | "vintage" | "gallery";

export type Vibe = {
  id: VibeId;
  label: string;
  line: string;
  hint: string;
};

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
};

export type LifeRoute = {
  lineCode: string;
  lineName: string;
  title: string;
  subtitle: string;
  totalMin: number;
  vibe: VibeId;
  districtId?: string;
  stops: Stop[];
  geometry?: GeoGeometry | null;
  distanceM?: number;
  source?: "live" | "fixture";
  fallback_reason?: string;
};

export type DistrictOption = {
  id: string;
  name: string;
  city: string;
};

export type BriefInput = {
  vibe: VibeId;
  districtId: string;
  durationMin: number;
  pace: "slow" | "normal" | "fast";
};

export type AppStage = "brief" | "loading" | "route" | "walk" | "done";
