import { useEffect, useState } from "react";
import type { CommunityRoute } from "../types";
import { fetchCommunityRoutes, rateCommunityRoute } from "../lib/api";

export function CommunityFeed() {
  const [routes, setRoutes] = useState<CommunityRoute[]>([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<string | null>(null);

  useEffect(() => {
    fetchCommunityRoutes()
      .then(setRoutes)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <section className="metro-panel">
        <p className="metro-kicker">社区线路</p>
        <p className="metro-lead">加载中…</p>
      </section>
    );
  }

  if (routes.length === 0) {
    return (
      <section className="metro-panel">
        <p className="metro-kicker">社区线路</p>
        <h2 className="metro-title">还没有社区线路</h2>
        <p className="metro-lead">
          完成一次漫步后，点击「发布到社区」分享给其他探索者。
          第一条社区线路就在你手里。
        </p>
      </section>
    );
  }

  const handleRate = async (routeId: string, rating: number) => {
    try {
      await rateCommunityRoute(routeId, rating);
      setRoutes((prev) =>
        prev.map((r) =>
          r.id === routeId
            ? { ...r, rating_count: r.rating_count + 1 }
            : r,
        ),
      );
    } catch {
      /* ignore */
    }
  };

  return (
    <section className="metro-panel community-feed">
      <p className="metro-kicker">社区线路 · {routes.length} 条</p>
      <div className="community-list">
        {routes.map((route) => (
          <div key={route.id} className="community-card">
            <div className="community-header">
              <span className="community-line-code">{route.route.lineCode}</span>
              <span className="community-author">{route.author_label}</span>
              <span className="community-rating">
                ⭐ {route.rating.toFixed(1)} ({route.rating_count})
              </span>
            </div>
            <h3 className="community-title">{route.route.lineName}</h3>
            <p className="community-subtitle">{route.route.title}</p>
            <div className="community-meta">
              <span>{route.route.stops.length} 站</span>
              <span>{route.route.totalMin} 分钟</span>
              <span>👤 {route.walk_count} 人走过</span>
            </div>
            {route.tags.length > 0 && (
              <div className="community-tags">
                {route.tags.map((t) => (
                  <span key={t} className="community-tag">#{t}</span>
                ))}
              </div>
            )}
            {expanded === route.id && (
              <div className="community-stops">
                {route.route.stops.map((stop) => (
                  <div key={stop.id} className="community-stop">
                    <span className="stop-code">{stop.code}</span>
                    <span className="stop-name">{stop.name}</span>
                  </div>
                ))}
              </div>
            )}
            <div className="community-actions">
              <button
                type="button"
                className="community-btn"
                onClick={() =>
                  setExpanded(expanded === route.id ? null : route.id)
                }
              >
                {expanded === route.id ? "收起站点" : "查看站点"}
              </button>
              <div className="star-rating">
                {[1, 2, 3, 4, 5].map((star) => (
                  <button
                    key={star}
                    type="button"
                    className="star-btn"
                    onClick={() => handleRate(route.id, star)}
                    title={`${star} 星`}
                  >
                    ⭐
                  </button>
                ))}
              </div>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
