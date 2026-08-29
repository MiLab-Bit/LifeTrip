import { RouteMap } from "./RouteMap";
import { SourceBadge } from "./SourceBadge";
import type { RouteEnvelope } from "../types";

type RouteStageProps = {
  route: RouteEnvelope;
  activeStopIndex: number;
  onSelectStop: (index: number) => void;
  onStartWalk: () => void;
  startLoading?: boolean;
};

export function RouteStage({
  route,
  activeStopIndex,
  onSelectStop,
  onStartWalk,
  startLoading,
}: RouteStageProps) {
  return (
    <section className="metro-panel route-stage" aria-labelledby="route-title">
      <p className="metro-kicker">
        {route.lineCode} · {route.lineName}
        {route.source === "fixture" ? " · 离线" : route.source === "live" ? " · OSM" : ""}
      </p>
      <h2 id="route-title" className="metro-title">
        {route.title}
      </h2>
      <p className="metro-lead">{route.subtitle}</p>
      {route.fallback_reason ? (
        <p className="metro-note">Live 规划不可用，已回落示范线。</p>
      ) : null}

      <RouteMap
        route={route}
        activeStopIndex={activeStopIndex}
        onSelectStop={onSelectStop}
      />

      <div className="route-map" role="list">
        {route.stops.map((stop, index) => (
          <button
            key={stop.id}
            type="button"
            className="route-stop route-stop--btn"
            role="listitem"
            onClick={() => onSelectStop(index)}
          >
            <span
              className={`route-stop__dot${index === activeStopIndex ? " route-stop__dot--active" : ""}`}
              aria-hidden="true"
            />
            <div className="route-stop__code">{stop.code}</div>
            <div className="route-stop__name">
              {stop.name} <SourceBadge label={stop.sourceLabel} />
            </div>
            <div className="route-stop__meta">
              {stop.district}
              {stop.walkMin > 0 ? ` · 步行 ${stop.walkMin} 分` : " · 起点站"}
            </div>
          </button>
        ))}
      </div>

      <div className="metro-actions">
        <button type="button" className="metro-btn metro-btn--primary" onClick={onStartWalk} disabled={startLoading}>
          {startLoading ? "准备中…" : "开始漫步 · Enter"}
        </button>
      </div>
    </section>
  );
}
