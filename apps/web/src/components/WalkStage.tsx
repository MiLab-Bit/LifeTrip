import { RouteMap } from "./RouteMap";
import type { LifeRoute } from "../types";

type WalkStageProps = {
  route: LifeRoute;
  stopIndex: number;
  onPrev: () => void;
  onNext: () => void;
  onFinish: () => void;
};

export function WalkStage({
  route,
  stopIndex,
  onPrev,
  onNext,
  onFinish,
}: WalkStageProps) {
  const stop = route.stops[stopIndex];
  const total = route.stops.length;
  const progress = ((stopIndex + 1) / total) * 100;
  const isLast = stopIndex === total - 1;

  return (
    <section className="metro-panel walk-stage" aria-labelledby="walk-title">
      <RouteMap route={route} activeStopIndex={stopIndex} compact />

      <div className="walk-progress">
        <span>
          STATION {stopIndex + 1}/{total}
        </span>
        <div className="walk-progress__bar" aria-hidden="true">
          <div className="walk-progress__fill" style={{ width: `${progress}%` }} />
        </div>
        <span>{stop.code}</span>
      </div>

      <p className="metro-kicker">{route.lineCode}</p>
      <h2 id="walk-title" className="metro-title">
        {stop.name}
      </h2>
      <p className="metro-lead">
        {stop.district}
        {stop.walkMin > 0 ? ` · 已步行约 ${stop.walkMin} 分钟到此` : " · 起点"}
      </p>

      <div style={{ marginBottom: 14 }}>
        {stop.tags.map((tag) => (
          <span key={tag} className="metro-tag">
            {tag}
          </span>
        ))}
      </div>

      <h3 className="walk-headline">{stop.headline}</h3>
      <p className="walk-body">{stop.body}</p>
      <p className="walk-tip">
        <strong>TIP</strong>
        {stop.tip}
      </p>

      <div className="metro-actions">
        <button
          type="button"
          className="metro-btn metro-btn--ghost"
          onClick={onPrev}
          disabled={stopIndex === 0}
        >
          上一站
        </button>
        {isLast ? (
          <button type="button" className="metro-btn metro-btn--primary" onClick={onFinish}>
            到达终点 · Exit
          </button>
        ) : (
          <button type="button" className="metro-btn metro-btn--primary" onClick={onNext}>
            下一站 · Next
          </button>
        )}
      </div>
    </section>
  );
}
