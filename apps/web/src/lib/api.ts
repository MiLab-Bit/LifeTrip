import type {
  BriefInput,
  DistrictOption,
  PendingAction,
  RerouteProposal,
  RouteEnvelope,
  WalkPlanResponse,
  WalkTask,
} from "../types";

const API = import.meta.env.VITE_API_BASE ?? "";

const SESSION_KEY = "lifetrip_session_id";

export function getSessionId(): string {
  let id = localStorage.getItem(SESSION_KEY);
  if (!id) {
    id = crypto.randomUUID();
    localStorage.setItem(SESSION_KEY, id);
  }
  return id;
}

export async function fetchDistricts(): Promise<DistrictOption[]> {
  const r = await fetch(`${API}/v1/districts`);
  if (!r.ok) throw new Error("districts failed");
  const data = (await r.json()) as { districts: DistrictOption[] };
  return data.districts;
}

export async function fetchHealth(): Promise<{ ok: boolean; offline_mode?: boolean; version?: string }> {
  const r = await fetch(`${API}/v1/health`);
  if (!r.ok) return { ok: false };
  return r.json();
}

/** Legacy — route only */
export async function planRoute(brief: BriefInput): Promise<RouteEnvelope> {
  const r = await fetch(`${API}/v1/routes/plan`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      vibe: brief.vibe,
      district_id: brief.districtId,
      duration_min: brief.durationMin,
      pace: brief.pace,
      intent_text: brief.intentText,
      session_id: getSessionId(),
    }),
  });
  if (!r.ok) {
    const text = await r.text();
    throw new Error(text || `plan failed ${r.status}`);
  }
  return r.json() as Promise<RouteEnvelope>;
}

export async function planWalk(brief: BriefInput): Promise<WalkPlanResponse> {
  const r = await fetch(`${API}/v1/walks/plan`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      vibe: brief.vibe,
      district_id: brief.districtId,
      duration_min: brief.durationMin,
      pace: brief.pace,
      intent_text: brief.intentText,
      session_id: getSessionId(),
    }),
  });
  if (!r.ok) {
    const text = await r.text();
    throw new Error(text || `walk plan failed ${r.status}`);
  }
  const data = (await r.json()) as WalkPlanResponse;
  localStorage.setItem(SESSION_KEY, data.session_id);
  return data;
}

export async function resumeWalk(): Promise<WalkTask | null> {
  const r = await fetch(`${API}/v1/walks/resume?session_id=${encodeURIComponent(getSessionId())}`);
  if (!r.ok) return null;
  const data = (await r.json()) as { task: WalkTask | null };
  return data.task;
}

export async function startWalk(taskId: string): Promise<WalkTask> {
  const r = await fetch(`${API}/v1/walks/${taskId}/start`, { method: "POST" });
  if (!r.ok) throw new Error("start failed");
  return r.json() as Promise<WalkTask>;
}

export async function advanceWalk(taskId: string): Promise<WalkTask> {
  const r = await fetch(`${API}/v1/walks/${taskId}/advance`, { method: "POST" });
  if (!r.ok) throw new Error("advance failed");
  return r.json() as Promise<WalkTask>;
}

export async function skipWalk(taskId: string, confirm: boolean): Promise<WalkTask> {
  const r = await fetch(`${API}/v1/walks/${taskId}/skip`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ confirm }),
  });
  if (!r.ok) throw new Error("skip failed");
  return r.json() as Promise<WalkTask>;
}

export async function rerollWalk(taskId: string, confirm: boolean): Promise<WalkTask> {
  const r = await fetch(`${API}/v1/walks/${taskId}/reroll`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ confirm }),
  });
  if (!r.ok) throw new Error("reroll failed");
  return r.json() as Promise<WalkTask>;
}

export async function completeWalk(taskId: string): Promise<WalkTask> {
  const r = await fetch(`${API}/v1/walks/${taskId}/complete`, { method: "POST" });
  if (!r.ok) throw new Error("complete failed");
  return r.json() as Promise<WalkTask>;
}

export async function fetchProactive(taskId: string): Promise<RerouteProposal | null> {
  const r = await fetch(`${API}/v1/walks/${taskId}/proactive`);
  if (!r.ok) return null;
  const data = (await r.json()) as { proposal: RerouteProposal | null };
  return data.proposal;
}

export async function applyReroute(
  taskId: string,
  proposal: RouteEnvelope,
  confirm: boolean,
): Promise<WalkTask> {
  const r = await fetch(`${API}/v1/walks/${taskId}/apply-reroute`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ confirm, proposal }),
  });
  if (!r.ok) throw new Error("apply reroute failed");
  return r.json() as Promise<WalkTask>;
}

export function isPendingAction(v: unknown): v is PendingAction {
  return typeof v === "object" && v !== null && "kind" in v && "message" in v;
}
