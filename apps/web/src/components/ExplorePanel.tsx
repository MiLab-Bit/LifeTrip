import { useEffect, useState } from "react";
import type { ExploreStats, WalkProfile } from "../types";
import { fetchExplore, fetchProfile } from "../lib/api";

export function ExplorePanel() {
  const [stats, setStats] = useState<ExploreStats | null>(null);
  const [profile, setProfile] = useState<WalkProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<"badges" | "map" | "collection">("badges");

  useEffect(() => {
    Promise.all([fetchExplore(), fetchProfile()])
      .then(([s, p]) => {
        setStats(s);
        setProfile(p);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <section className="metro-panel">
        <p className="metro-kicker">探索图谱</p>
        <p className="metro-lead">加载中…</p>
      </section>
    );
  }

  if (!stats || stats.total_walks === 0) {
    return (
      <section className="metro-panel">
        <p className="metro-kicker">探索图谱</p>
        <h2 className="metro-title">还没有探索记录</h2>
        <p className="metro-lead">完成第一次漫步后，你的探索图谱会在这里亮起来。</p>
        <div className="badge-wall" style={{ opacity: 0.3 }}>
          {DEFAULT_BADGE_ICONS.map((icon) => (
            <span key={icon} className="badge-chip badge-chip--locked">{icon}</span>
          ))}
        </div>
      </section>
    );
  }

  const earned = stats.badges.filter((b) => b.earned);
  const locked = stats.badges.filter((b) => !b.earned);

  return (
    <section className="metro-panel explore-panel">
      <p className="metro-kicker">探索图谱</p>

      {/* Stats strip */}
      <div className="explore-stats-strip">
        <div className="stat-item">
          <span className="stat-value">{stats.total_walks}</span>
          <span className="stat-label">完成线路</span>
        </div>
        <div className="stat-item">
          <span className="stat-value">{stats.total_km.toFixed(1)}</span>
          <span className="stat-label">公里</span>
        </div>
        <div className="stat-item">
          <span className="stat-value">{stats.total_stops}</span>
          <span className="stat-label">站点</span>
        </div>
        <div className="stat-item">
          <span className="stat-value">{stats.total_minutes}</span>
          <span className="stat-label">分钟</span>
        </div>
        <div className="stat-item">
          <span className="stat-value">{earned.length}</span>
          <span className="stat-label">徽章</span>
        </div>
      </div>

      {/* WalkDNA quick view */}
      {profile && profile.completed_walks > 0 && (
        <div className="walkdna-chip">
          <span className="walkdna-label">WalkDNA</span>
          <span className="walkdna-prefs">
            {Object.entries(profile.vibe_weights).map(([vibe, w]) => (
              <span key={vibe} className="vibe-bar" style={{ opacity: 0.4 + w * 0.6 }}>
                {VIBE_LABELS[vibe] ?? vibe}
              </span>
            ))}
          </span>
          <span className="walkdna-pace">配速 · {PACE_LABELS[profile.pace_preference] ?? profile.pace_preference}</span>
        </div>
      )}

      {/* Tabs */}
      <div className="explore-tabs">
        <button
          className={`explore-tab ${tab === "badges" ? "active" : ""}`}
          onClick={() => setTab("badges")}
        >徽章墙</button>
        <button
          className={`explore-tab ${tab === "map" ? "active" : ""}`}
          onClick={() => setTab("map")}
        >街区覆盖</button>
        <button
          className={`explore-tab ${tab === "collection" ? "active" : ""}`}
          onClick={() => setTab("collection")}
        >收藏站 ({stats.collected_pois.length})</button>
      </div>

      {/* Tab content */}
      {tab === "badges" && (
        <div className="badge-wall">
          {earned.map((b) => (
            <span key={b.id} className="badge-chip badge-chip--earned" title={b.description}>
              <span className="badge-icon">{b.icon}</span>
              <span className="badge-name">{b.name}</span>
            </span>
          ))}
          {locked.map((b) => (
            <span key={b.id} className="badge-chip badge-chip--locked" title={b.description}>
              <span className="badge-icon">{b.icon}</span>
              <span className="badge-name">{b.name}</span>
            </span>
          ))}
        </div>
      )}

      {tab === "map" && (
        <div className="district-coverage">
          {stats.districts.map((d) => (
            <div key={d.district_id} className={`district-card ${d.lit ? "lit" : ""}`}>
              <span className="district-name">{d.district_name}</span>
              {d.lit ? (
                <span className="district-count">{d.walks_completed} 次漫步 ✅</span>
              ) : (
                <span className="district-count">未探索</span>
              )}
            </div>
          ))}
        </div>
      )}

      {tab === "collection" && (
        <div className="poi-collection">
          {stats.collected_pois.length === 0 ? (
            <p className="metro-note">还没有收藏的站点</p>
          ) : (
            stats.collected_pois.map((poi) => (
              <div key={poi.id} className="poi-chip">
                <span className="poi-name">{poi.name}</span>
                <span className="poi-district">{poi.district}</span>
                {poi.tags.slice(0, 2).map((t) => (
                  <span key={t} className="poi-tag">{t}</span>
                ))}
              </div>
            ))
          )}
        </div>
      )}
    </section>
  );
}

const DEFAULT_BADGE_ICONS = ["🚶", "☕", "🌙", "🧥", "🖼️", "⭐", "🔥", "🗺️", "🏃", "📮", "🏆"];

const VIBE_LABELS: Record<string, string> = {
  coffee: "咖啡",
  neon: "夜行",
  vintage: "古着",
  gallery: "画廊",
};

const PACE_LABELS: Record<string, string> = {
  slow: "慢逛",
  normal: "正常",
  fast: "高效",
};
