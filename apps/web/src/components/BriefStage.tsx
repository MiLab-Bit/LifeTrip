import { useEffect, useState } from "react";
import { fetchDistricts } from "../lib/api";
import type { BriefInput, DistrictOption, VibeId } from "../types";

const VIBES = [
  { id: "neon" as const, label: "夜行霓虹", line: "L-N1", hint: "Bar、Late-night 小馆" },
  { id: "coffee" as const, label: "咖啡巡游", line: "L-C2", hint: "独立烘焙、窗口位" },
  { id: "vintage" as const, label: "古着淘街", line: "L-V3", hint: "二手、复古选物" },
  { id: "gallery" as const, label: "画廊串游", line: "L-G4", hint: "小型展、艺术空间" },
];

type BriefStageProps = {
  value: BriefInput;
  onChange: (next: BriefInput) => void;
  onSubmit: () => void;
  loading?: boolean;
  error?: string | null;
};

export function BriefStage({
  value,
  onChange,
  onSubmit,
  loading,
  error,
}: BriefStageProps) {
  const [districts, setDistricts] = useState<DistrictOption[]>([]);
  const selectedVibe = VIBES.find((v) => v.id === value.vibe);

  useEffect(() => {
    fetchDistricts()
      .then(setDistricts)
      .catch(() =>
        setDistricts([
          { id: "anfu-wukang", name: "安福—武康", city: "上海" },
          { id: "yuyuan-js", name: "愚园—江苏路", city: "上海" },
          { id: "jufu-fumin", name: "巨富—富民", city: "上海" },
          { id: "west-bund", name: "西岸—滨江", city: "上海" },
        ]),
      );
  }, []);

  return (
    <section className="metro-panel" aria-labelledby="brief-title">
      <p className="metro-kicker">Line Select · 选线</p>
      <h1 id="brief-title" className="metro-title">
        拼一条当下最好逛的 city walk
      </h1>
      <p className="metro-lead">
        数据来自 OpenStreetMap + OSRM 步行，不用上图 API。谈街面 POI，不谈典籍。
      </p>

      <div className="metro-field">
        <label id="vibe-label">潮流主题</label>
        <div className="metro-chip-row" role="group" aria-labelledby="vibe-label">
          {VIBES.map((vibe) => (
            <button
              key={vibe.id}
              type="button"
              className="metro-chip"
              aria-pressed={value.vibe === vibe.id}
              onClick={() => onChange({ ...value, vibe: vibe.id as VibeId })}
            >
              {vibe.label}
            </button>
          ))}
        </div>
        {selectedVibe ? (
          <p className="metro-lead" style={{ marginTop: 12, marginBottom: 0 }}>
            {selectedVibe.line} · {selectedVibe.hint}
          </p>
        ) : null}
      </div>

      <div className="metro-field">
        <label htmlFor="intent">一句话任务（可选）</label>
        <input
          id="intent"
          className="metro-select"
          type="text"
          placeholder="今晚安福咖啡慢逛 90 分钟"
          value={value.intentText ?? ""}
          onChange={(e) => onChange({ ...value, intentText: e.target.value || undefined })}
        />
      </div>

      <div className="metro-field">
        <label htmlFor="district">片区</label>
        <select
          id="district"
          className="metro-select"
          value={value.districtId}
          onChange={(e) => onChange({ ...value, districtId: e.target.value })}
        >
          {districts.map((d) => (
            <option key={d.id} value={d.id}>
              {d.name}（{d.city}）
            </option>
          ))}
        </select>
      </div>

      <div className="metro-field">
        <label htmlFor="duration">时长 · {value.durationMin} 分钟</label>
        <input
          id="duration"
          className="metro-range"
          type="range"
          min={45}
          max={150}
          step={15}
          value={value.durationMin}
          onChange={(e) =>
            onChange({ ...value, durationMin: Number(e.target.value) })
          }
        />
      </div>

      <div className="metro-field">
        <label id="pace-label">步速</label>
        <div className="metro-chip-row" role="group" aria-labelledby="pace-label">
          {(
            [
              ["slow", "慢逛"],
              ["normal", "标准"],
              ["fast", "赶场"],
            ] as const
          ).map(([pace, label]) => (
            <button
              key={pace}
              type="button"
              className="metro-chip"
              aria-pressed={value.pace === pace}
              onClick={() => onChange({ ...value, pace })}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {error ? <p className="metro-error">{error}</p> : null}

      <div className="metro-actions">
        <button
          type="button"
          className="metro-btn metro-btn--primary"
          onClick={onSubmit}
          disabled={loading}
        >
          {loading ? "规划中…" : "生成线路 · Depart"}
        </button>
      </div>
    </section>
  );
}
