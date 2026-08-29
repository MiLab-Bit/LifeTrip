import type { BriefInput, DistrictOption, LifeRoute } from "../types";

const API = import.meta.env.VITE_API_BASE ?? "";

export async function fetchDistricts(): Promise<DistrictOption[]> {
  const r = await fetch(`${API}/v1/districts`);
  if (!r.ok) throw new Error("districts failed");
  const data = (await r.json()) as { districts: DistrictOption[] };
  return data.districts;
}

export async function planRoute(brief: BriefInput): Promise<LifeRoute> {
  const r = await fetch(`${API}/v1/routes/plan`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      vibe: brief.vibe,
      district_id: brief.districtId,
      duration_min: brief.durationMin,
      pace: brief.pace,
    }),
  });
  if (!r.ok) {
    const text = await r.text();
    throw new Error(text || `plan failed ${r.status}`);
  }
  return r.json() as Promise<LifeRoute>;
}

export async function fetchHealth(): Promise<{ ok: boolean; offline_mode?: boolean }> {
  const r = await fetch(`${API}/v1/health`);
  if (!r.ok) return { ok: false };
  return r.json();
}
