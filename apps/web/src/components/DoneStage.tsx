import { useEffect, useState } from "react";
import type { WalkCardData } from "../types";
import { fetchCardData } from "../lib/api";
import { WalkCard } from "./WalkCard";
import { RatingForm } from "./RatingForm";

type DoneStageProps = {
  taskId?: string;
  lineCode: string;
  title: string;
  verified?: boolean;
  onRestart: () => void;
  onExplore?: () => void;
};

export function DoneStage({ taskId, lineCode, title, verified, onRestart, onExplore }: DoneStageProps) {
  const [cardData, setCardData] = useState<WalkCardData | null>(null);
  const [showCard, setShowCard] = useState(false);
  const [showRating, setShowRating] = useState(false);

  useEffect(() => {
    if (taskId && showCard) {
      fetchCardData(taskId)
        .then(setCardData)
        .catch(() => {});
    }
  }, [taskId, showCard]);

  return (
    <section className="metro-panel done-stage">
      <p className="metro-kicker">{lineCode} · 终到站</p>
      <h2 className="metro-title">今日线路已走完</h2>
      <p className="metro-lead">
        「{title}」——潮流 city walk 不在清单里打勾，在街角多停的那一分钟。
      </p>
      {verified !== undefined ? (
        <p className="metro-note">{verified ? "✓ WalkTask 验证通过" : "部分站点未完全核实"}</p>
      ) : null}

      {/* Action buttons */}
      <div className="done-actions">
        <button type="button" className="metro-btn metro-btn--primary" onClick={onRestart}>
          再选一条线 · Transfer
        </button>
        {taskId && (
          <>
            <button
              type="button"
              className="metro-btn"
              onClick={() => setShowCard(!showCard)}
            >
              🎴 {showCard ? "收起" : "漫步卡片"}
            </button>
            <button
              type="button"
              className="metro-btn"
              onClick={() => setShowRating(!showRating)}
            >
              ⭐ {showRating ? "收起" : "评价"}
            </button>
            {onExplore && (
              <button type="button" className="metro-btn" onClick={onExplore}>
                🗺️ 我的探索图谱
              </button>
            )}
          </>
        )}
      </div>

      {/* Walk Card */}
      {showCard && cardData && <WalkCard cardData={cardData} />}
      {showCard && !cardData && <p className="metro-note">卡片加载中…</p>}

      {/* Rating */}
      {showRating && taskId && <RatingForm taskId={taskId} />}
    </section>
  );
}
