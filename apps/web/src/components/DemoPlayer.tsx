/**
 * DemoPlayer — 外滩全流程自播放演示
 * 数据来源：POST /v1/walks/plan (district_id=the-bund, vibe=coffee)
 * 真实 API 数据嵌入，演示时无需后端
 */
import { useEffect, useRef, useState } from "react";

// ── 真实 API 数据（POST /v1/walks/plan → the-bund, coffee）──
const DEMO_ROUTE = {
  title: "外滩 · 咖啡线",
  subtitle: "精选 4 · OSM 0 站 · 步行约 42 分钟",
  totalMin: 42,
  distanceM: 3532,
  stops: [
    {
      name: "外滩源·圆明园路",
      code: "C2-01",
      headline: "第一杯：启动这条线",
      body: "圆明园路保留了外滩最原始的石板路和殖民时期建筑群。清晨几乎没有游客，协和教堂的红砖墙和穹顶在晨光中格外好看。从这里一路往南走，就是经典的外滩万国建筑博览。",
      tip: "早上 8 点前到，光最好也最安静。圆明园路口的咖啡车 7:30 就开了。",
      tags: ["历史建筑", "拍照", "步行"],
      lat: 31.2397,
      lng: 121.4905,
      walkMin: 0,
      indoor: false,
    },
    {
      name: "外滩观景台·陈毅广场段",
      code: "C2-02",
      headline: "外滩经典机位：左手万国建筑，右手陆家嘴三件套",
      body: "陈毅广场前的观景平台是整个外滩最佳的拍照点。往浦东看是东方明珠、上海中心、环球金融中心组成的「三件套」天际线；背后是从汇丰银行到海关大楼的万国建筑群。傍晚 5-6 点来这里，能同时拍到日落和亮灯。",
      tip: "想避开人群可以走到北侧的外白渡桥，那边人少很多，也是《情深深雨濛濛》的取景地。",
      tags: ["观景", "拍照", "必到"],
      lat: 31.239,
      lng: 121.4908,
      walkMin: 14,
      indoor: false,
    },
    {
      name: "和平饭店·北楼",
      code: "C2-03",
      headline: "走进和平饭店大堂，感受 1929 年的 Art Deco 奢华",
      body: "和平饭店（原名沙逊大厦）是外滩最具标志性的建筑之一。大堂的八角形穹顶和铜艺吊灯保存完好，无需消费即可参观一楼公共区域。如果时间充裕，顶楼的华懋阁露台可以俯瞰浦东天际线。",
      tip: "大堂免费参观，但拍照请勿使用三脚架。东侧的旋转门是原物。",
      tags: ["历史建筑", "咖啡", "拍照"],
      lat: 31.2415,
      lng: 121.4905,
      walkMin: 14,
      indoor: true,
    },
    {
      name: "十六铺码头·滨江步道",
      code: "C2-04",
      headline: "终站 · 一路走到十六铺，老码头的滨江日落",
      body: "从陈毅广场沿江往南约 800 米就是十六铺码头。这里经过改造后成了开放的滨江公园，有木质栈道和亲水平台。比起北段的外滩，这里人少很多，可以坐下来面对黄浦江发呆。如果走到这里累了，旁边的 BFC 外滩金融中心有大量餐饮选择。",
      tip: "十六铺的地下商业街「BFC」有干净的卫生间和空调，适合休息后再走。",
      tags: ["江景", "休闲", "日落"],
      lat: 31.2305,
      lng: 121.4905,
      walkMin: 14,
      indoor: false,
    },
  ],
};

type DemoPhase = "brief" | "route" | `walk-${number}` | "done";

const PHASE_DURATIONS: Record<string, number> = {
  brief: 3500,
  route: 4000,
  "walk-0": 6000,
  "walk-1": 6000,
  "walk-2": 6000,
  "walk-3": 6000,
  done: 4000,
};

export function DemoPlayer({ onClose }: { onClose: () => void }) {
  const [phase, setPhase] = useState<DemoPhase>("brief");
  const [playing, setPlaying] = useState(true);
  const [progress, setProgress] = useState(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const totalStops = DEMO_ROUTE.stops.length;
  const phases: DemoPhase[] = [
    "brief",
    "route",
    ...Array.from({ length: totalStops }, (_, i) => `walk-${i}` as DemoPhase),
    "done",
  ];
  const currentPhaseIndex = phases.indexOf(phase);

  // Auto-advance logic
  useEffect(() => {
    if (!playing) return;
    const duration = PHASE_DURATIONS[phase] ?? 5000;

    // Progress bar animation
    const startTime = Date.now();
    timerRef.current = setInterval(() => {
      const elapsed = Date.now() - startTime;
      const pct = Math.min(elapsed / duration, 1);
      setProgress(pct * 100);
      if (pct >= 1) {
        if (timerRef.current) clearInterval(timerRef.current);
        setProgress(0);
        const nextIndex = currentPhaseIndex + 1;
        if (nextIndex < phases.length) {
          setPhase(phases[nextIndex]);
        } else {
          setPlaying(false);
        }
      }
    }, 50);

    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [phase, playing, currentPhaseIndex, phases]);

  const handleRestart = () => {
    setPhase("brief");
    setPlaying(true);
    setProgress(0);
  };

  const handleTogglePlay = () => {
    setPlaying((p) => !p);
  };

  const handleSkip = () => {
    const nextIndex = currentPhaseIndex + 1;
    if (nextIndex < phases.length) {
      setProgress(0);
      setPhase(phases[nextIndex]);
    }
  };

  // ── Render current phase ──

  if (phase === "brief") {
    return (
      <DemoShell progress={progress} phase={phase} phases={phases} currentPhaseIndex={currentPhaseIndex}
        onToggle={handleTogglePlay} onSkip={handleSkip} onRestart={handleRestart} onClose={onClose} playing={playing}>
        <div className="demo-brief">
          <p className="demo-kicker">LifeTrip · AI 城市漫步引擎</p>
          <h2 className="demo-title-big">规划一条漫步</h2>
          <div className="demo-brief-form">
            <div className="demo-field">
              <span className="demo-field-label">城市</span>
              <span className="demo-chip demo-chip--active">上海</span>
            </div>
            <div className="demo-field">
              <span className="demo-field-label">片区</span>
              <span className="demo-chip demo-chip--active">外滩</span>
            </div>
            <div className="demo-field">
              <span className="demo-field-label">主题</span>
              <span className="demo-chip demo-chip--active">☕ 咖啡巡游</span>
            </div>
            <div className="demo-field">
              <span className="demo-field-label">时长</span>
              <span className="demo-chip demo-chip--active">120 分钟</span>
            </div>
          </div>
          <button className="demo-plan-btn demo-plan-btn--auto">
            ✨ 规划线路
          </button>
        </div>
      </DemoShell>
    );
  }

  if (phase === "route") {
    return (
      <DemoShell progress={progress} phase={phase} phases={phases} currentPhaseIndex={currentPhaseIndex}
        onToggle={handleTogglePlay} onSkip={handleSkip} onRestart={handleRestart} onClose={onClose} playing={playing}>
        <div className="demo-route">
          <p className="demo-kicker">线路规划完成</p>
          <h2 className="demo-title-big">{DEMO_ROUTE.title}</h2>
          <p className="demo-subtitle">{DEMO_ROUTE.subtitle}</p>
          <div className="demo-route-stats">
            <div className="demo-stat">
              <span className="demo-stat-val">{DEMO_ROUTE.stops.length}</span>
              <span className="demo-stat-lbl">站点</span>
            </div>
            <div className="demo-stat">
              <span className="demo-stat-val">{DEMO_ROUTE.totalMin}</span>
              <span className="demo-stat-lbl">分钟</span>
            </div>
            <div className="demo-stat">
              <span className="demo-stat-val">{(DEMO_ROUTE.distanceM / 1000).toFixed(1)}</span>
              <span className="demo-stat-lbl">公里</span>
            </div>
          </div>
          <div className="demo-route-stops">
            {DEMO_ROUTE.stops.map((s, i) => (
              <div key={i} className="demo-route-stop" style={{ animationDelay: `${i * 0.3}s` }}>
                <span className="demo-stop-dot">{i + 1}</span>
                <div className="demo-stop-mini">
                  <span className="demo-stop-name">{s.name}</span>
                  <span className="demo-stop-tags">{s.tags.slice(0, 2).join(" · ")}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </DemoShell>
    );
  }

  if (phase.startsWith("walk-")) {
    const idx = parseInt(phase.split("-")[1]);
    const stop = DEMO_ROUTE.stops[idx];
    const isLast = idx === totalStops - 1;

    return (
      <DemoShell progress={progress} phase={phase} phases={phases} currentPhaseIndex={currentPhaseIndex}
        onToggle={handleTogglePlay} onSkip={handleSkip} onRestart={handleRestart} onClose={onClose} playing={playing}>
        <div className="demo-walk">
          {/* Progress rail */}
          <div className="demo-walk-progress">
            {DEMO_ROUTE.stops.map((_, i) => (
              <div key={i} className={`demo-rail-dot ${i < idx ? "done" : i === idx ? "active" : ""}`} />
            ))}
          </div>

          {/* Stop content */}
          <div key={idx} className="demo-stop-card demo-stop-card--enter">
            <div className="demo-stop-header">
              <span className="demo-stop-code">{stop.code}</span>
              <span className="demo-stop-walkmin">
                {stop.walkMin > 0 ? `步行 ${stop.walkMin} 分钟` : "起点"}
              </span>
            </div>
            <h2 className="demo-stop-title">{stop.name}</h2>
            <p className="demo-stop-headline">{stop.headline}</p>
            <p className="demo-stop-body">{stop.body}</p>

            <div className="demo-stop-tags">
              {stop.tags.map((t, i) => (
                <span key={i} className="demo-tag">{t}</span>
              ))}
            </div>

            <div className="demo-stop-tip">
              <span className="demo-tip-icon">💡</span>
              <span>{stop.tip}</span>
            </div>

            {isLast && (
              <div className="demo-complete-banner">
                ✅ 漫步完成！WalkDNA 已更新
              </div>
            )}
          </div>
        </div>
      </DemoShell>
    );
  }

  // done
  return (
    <DemoShell progress={progress} phase={phase} phases={phases} currentPhaseIndex={currentPhaseIndex}
      onToggle={handleTogglePlay} onSkip={handleSkip} onRestart={handleRestart} onClose={onClose} playing={playing}>
      <div className="demo-done">
        <p className="demo-kicker">漫步完成</p>
        <h2 className="demo-title-big">{DEMO_ROUTE.title}</h2>
        <p className="demo-done-stats">
          {totalStops} 站 · {DEMO_ROUTE.totalMin} 分钟 · {(DEMO_ROUTE.distanceM / 1000).toFixed(1)} 公里
        </p>
        <div className="demo-walkdna-card">
          <p className="demo-walkdna-label">你的 WalkDNA</p>
          <div className="demo-dna-bars">
            <div className="demo-dna-bar">
              <span className="dna-label">探索度</span>
              <div className="dna-track"><div className="dna-fill" style={{ width: "72%" }} /></div>
            </div>
            <div className="demo-dna-bar">
              <span className="dna-label">文艺偏好</span>
              <div className="dna-track"><div className="dna-fill" style={{ width: "85%" }} /></div>
            </div>
            <div className="demo-dna-bar">
              <span className="dna-label">步行耐力</span>
              <div className="dna-track"><div className="dna-fill" style={{ width: "60%" }} /></div>
            </div>
          </div>
          <div className="demo-badges">
            <span className="demo-badge">🏅 外滩漫步者</span>
            <span className="demo-badge">📸 摄影达人</span>
            <span className="demo-badge">☕ 咖啡猎人</span>
          </div>
        </div>
        <button className="demo-plan-btn" onClick={handleRestart}>
          ↻ 再看一遍
        </button>
      </div>
    </DemoShell>
  );
}

// ── Shell wrapper with controls ──
function DemoShell({
  progress,
  currentPhaseIndex,
  phases,
  onToggle,
  onSkip,
  onRestart,
  onClose,
  playing,
  children,
}: {
  progress: number;
  phase: DemoPhase;
  currentPhaseIndex: number;
  phases: DemoPhase[];
  onToggle: () => void;
  onSkip: () => void;
  onRestart: () => void;
  onClose: () => void;
  playing: boolean;
  children: React.ReactNode;
}) {
  return (
    <div className="demo-shell">
      <div className="demo-content">{children}</div>

      {/* Bottom control bar */}
      <div className="demo-controls">
        <div className="demo-phase-dots">
          {phases.map((_, i) => (
            <div key={i} className={`demo-phase-dot ${i === currentPhaseIndex ? "active" : i < currentPhaseIndex ? "done" : ""}`} />
          ))}
        </div>
        <div className="demo-btns">
          <button type="button" className="demo-ctrl-btn" onClick={onToggle}>
            {playing ? "⏸" : "▶"}
          </button>
          <button type="button" className="demo-ctrl-btn" onClick={onSkip}>
            ⏭
          </button>
          <button type="button" className="demo-ctrl-btn" onClick={onRestart}>
            ↻
          </button>
          <button type="button" className="demo-ctrl-btn demo-ctrl-btn--close" onClick={onClose}>
            ✕
          </button>
        </div>
      </div>

      {/* Progress bar */}
      <div className="demo-progress-bar">
        <div className="demo-progress-fill" style={{ width: `${progress}%` }} />
      </div>
    </div>
  );
}
