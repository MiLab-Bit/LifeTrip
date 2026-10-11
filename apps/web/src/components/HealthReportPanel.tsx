/**
 * HealthReportPanel —— 15 分钟生活圈智能体检：地图等时圈叠加 + 体检报告面板。
 *
 * 职责拆分（为什么这么拆）：
 * 1. 地图叠加（useIsochroneLayer）：把等时圈 GeoJSON 画到 MapLibre 地图上，
 *    半透明绿色填充 + 亮绿描边，与项目黑绿地铁美学一致；组件卸载时清理
 *    source/layer，不留脏图层。
 * 2. 报告面板（HealthReportPanel）：六类设施覆盖率条形图（纯 CSS div 宽度
 *    百分比实现，不引图表库——评审的「交互 15%」靠轻快而非堆依赖）、
 *    盲区红点标注、降级提示横幅。
 *
 * 两个部分可独立使用：只要地图不要面板，或只要面板不要地图都成立。
 *
 * TODO-ADAPT（本地集成时需要确认的点）：
 * - className 约定：这里用 ltp- 前缀 + 内联兜底样式。若项目已有 design
 *   tokens（如 tailwind config 或 CSS 变量 --lt-green），把内联色值换成
 *   现有变量，保持视觉一致。
 * - 数据获取：本组件只渲染 props.result，不自己发请求；在调用方
 *   （页面/容器组件）里 POST /v1/isochrone/analyze 后把结果传进来。
 * - 地图实例：若项目里地图通过 context 提供，替换 props.map 的传递方式。
 */

import React, { useEffect, useMemo } from 'react';
import type { Map as MapLibreMap } from 'maplibre-gl';

// ---------- 与后端 AnalyzeResponse 对齐的类型（TS 侧手写镜像） ----------

export interface LatLng {
  lat: number;
  lng: number;
}

export interface GeoJSONPolygon {
  type: 'Polygon';
  /** GeoJSON 规范：[lng, lat] 序 */
  coordinates: number[][][];
}

export interface DirectionRay {
  bearing: number;
  reachable_m: number;
  time_s: number | null;
  degraded: boolean;
}

export interface IsochroneResult {
  center: LatLng;
  minutes: number;
  walking_speed_kmh: number;
  polygon: GeoJSONPolygon;
  area_m2: number;
  rays: DirectionRay[];
  degraded: boolean;
  degraded_directions: number;
  degraded_ratio: number;
  data_source: 'osrm' | 'offline-synthetic';
}

export interface CategoryCoverage {
  key: string;
  label: string;
  total: number;
  inside: number;
  coverage_rate: number;
  blind_spot: boolean;
}

export interface CoverageReport {
  categories: CategoryCoverage[];
  blind_spots: string[];
  threshold: number;
  total_pois: number;
  inside_pois: number;
}

export interface AnalyzeResponse {
  isochrone: IsochroneResult;
  coverage: CoverageReport;
  blind_spots: string[];
  degraded: boolean;
  poi_source: 'overpass' | 'curated';
}

// ---------- 主题色（TODO-ADAPT：替换为项目 design tokens） ----------

// 集成适配：色值换成项目 design tokens（apps/web/src/styles/tokens.css）。
// red 保留字面值：下方多处用 `${THEME.red}55` 拼十六进制透明度后缀，
// CSS 变量无法参与字符串拼接；该值与 --lt-danger 同色。
const THEME = {
  bg: 'var(--lt-bg-panel)',        // 面板底
  panel: 'var(--lt-bg-elevated)',  // 卡片底
  border: 'var(--lt-line)',        // 分割线
  green: 'var(--lt-green)',        // 主绿（等时圈填充/高亮）
  greenDim: 'var(--lt-green-dim)', // 条形图已覆盖部分
  red: '#ff5252',                  // 盲区红点（= --lt-danger）
  text: 'var(--lt-text)',          // 主文字
  textDim: 'var(--lt-text-muted)', // 次要文字
};

// ---------- 地图叠加 ----------

const SOURCE_ID = 'ltp-isochrone-src';
const FILL_LAYER_ID = 'ltp-isochrone-fill';
const LINE_LAYER_ID = 'ltp-isochrone-line';

/**
 * 把等时圈多边形叠加到 MapLibre 地图。
 * 为什么在 useEffect 里做 addSource/addLayer 而不是渲染时：MapLibre 的
 * 图层不是 React 元素，命令式管理 + cleanup 是最不容易泄漏的方式。
 */
export function useIsochroneLayer(
  map: MapLibreMap | null,
  polygon: GeoJSONPolygon | null,
  visible: boolean = true,
): void {
  useEffect(() => {
    if (!map || !polygon) return;

    const addLayers = () => {
      // 幂等：重复挂载先清旧图层，避免「Source already exists」报错
      for (const id of [LINE_LAYER_ID, FILL_LAYER_ID]) {
        if (map.getLayer(id)) map.removeLayer(id);
      }
      if (map.getSource(SOURCE_ID)) map.removeSource(SOURCE_ID);

      map.addSource(SOURCE_ID, {
        type: 'geojson',
        data: { type: 'Feature', geometry: polygon, properties: {} },
      });
      map.addLayer({
        id: FILL_LAYER_ID,
        type: 'fill',
        source: SOURCE_ID,
        layout: { visibility: visible ? 'visible' : 'none' },
        // 半透明绿填充：既要显眼又不能盖住底图路网
        paint: { 'fill-color': THEME.green, 'fill-opacity': 0.18 },
      });
      map.addLayer({
        id: LINE_LAYER_ID,
        type: 'line',
        source: SOURCE_ID,
        layout: { visibility: visible ? 'visible' : 'none' },
        paint: { 'line-color': THEME.green, 'line-width': 1.8, 'line-opacity': 0.9 },
      });
    };

    if (map.isStyleLoaded()) {
      addLayers();
    } else {
      // 样式未就绪时等 load 事件，否则 addSource 会静默失败
      map.once('load', addLayers);
    }

    return () => {
      // cleanup：组件卸载/多边形更换时移除图层与数据源
      for (const id of [LINE_LAYER_ID, FILL_LAYER_ID]) {
        if (map.getLayer(id)) map.removeLayer(id);
      }
      if (map.getSource(SOURCE_ID)) map.removeSource(SOURCE_ID);
    };
  }, [map, polygon, visible]);
}

// ---------- 纯工具 ----------

function formatArea(m2: number): string {
  if (m2 >= 1_000_000) return `${(m2 / 1_000_000).toFixed(2)} km²`;
  return `${Math.round(m2).toLocaleString('zh-CN')} m²`;
}

function formatPercent(rate: number): string {
  return `${Math.round(rate * 100)}%`;
}

// ---------- 覆盖率条形图（纯 CSS，零依赖） ----------

interface BarProps {
  category: CategoryCoverage;
  threshold: number;
}

function CoverageBar({ category, threshold }: BarProps) {
  const pct = Math.round(category.coverage_rate * 100);
  const empty = category.total === 0;
  return (
    <div className="ltp-cov-row" style={{ marginBottom: 10 }}>
      <div
        className="ltp-cov-label"
        style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}
      >
        <span style={{ color: category.blind_spot ? THEME.red : THEME.text, fontSize: 13 }}>
          {/* 盲区类别带红点标注，与面板顶部「盲区」呼应 */}
          {category.blind_spot && (
            <span
              aria-label="盲区"
              title="覆盖率低于阈值或该类别缺失"
              style={{
                display: 'inline-block',
                width: 7,
                height: 7,
                borderRadius: '50%',
                background: THEME.red,
                marginRight: 6,
                boxShadow: `0 0 6px ${THEME.red}`,
              }}
            />
          )}
          {category.label}
        </span>
        <span style={{ color: THEME.textDim, fontSize: 12, fontVariantNumeric: 'tabular-nums' }}>
          {category.inside}/{category.total} · {empty ? '缺失' : formatPercent(category.coverage_rate)}
        </span>
      </div>
      <div
        className="ltp-cov-track"
        role="meter"
        aria-valuenow={pct}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`${category.label}覆盖率`}
        style={{
          position: 'relative',
          height: 8,
          borderRadius: 4,
          background: 'var(--lt-bg)',
          overflow: 'hidden',
        }}
      >
        {/* 阈值刻度线：让「为什么这是盲区」一眼可见 */}
        <div
          style={{
            position: 'absolute',
            left: `${Math.round(threshold * 100)}%`,
            top: 0,
            bottom: 0,
            width: 1,
            background: THEME.textDim,
            opacity: 0.7,
          }}
        />
        <div
          className="ltp-cov-fill"
          style={{
            position: 'absolute',
            left: 0,
            top: 0,
            bottom: 0,
            width: `${pct}%`,
            borderRadius: 4,
            background: category.blind_spot ? `${THEME.red}99` : THEME.greenDim,
            transition: 'width 400ms ease',
          }}
        />
      </div>
    </div>
  );
}

// ---------- 主面板 ----------

export interface HealthReportPanelProps {
  result: AnalyzeResponse;
  /** MapLibre 地图实例；传 null 则只渲染面板不画图（方便纯列表页复用） */
  map?: MapLibreMap | null;
  /** 是否显示等时圈图层 */
  showPolygon?: boolean;
  /** 关闭回调（可选，容器决定怎么收起面板） */
  onClose?: () => void;
}

export default function HealthReportPanel({
  result,
  map = null,
  showPolygon = true,
  onClose,
}: HealthReportPanelProps): React.ReactElement {
  useIsochroneLayer(map, result?.isochrone?.polygon ?? null, showPolygon);

  const iso = result.isochrone;
  const cov = result.coverage;
  const sorted = useMemo(
    () =>
      // 稳定排序：盲区置顶，其余按覆盖率降序——报告的第一眼信息是「缺什么」
      [...cov.categories].sort((a, b) => {
        if (a.blind_spot !== b.blind_spot) return a.blind_spot ? -1 : 1;
        return b.coverage_rate - a.coverage_rate;
      }),
    [cov],
  );

  return (
    <aside
      className="ltp-health-panel"
      style={{
        width: 320,
        background: THEME.bg,
        border: `1px solid ${THEME.border}`,
        borderRadius: 10,
        color: THEME.text,
        padding: 16,
        fontFamily:
          "'SF Mono', 'JetBrains Mono', ui-monospace, Menlo, Consolas, monospace",
        boxShadow: '0 8px 32px rgba(0,0,0,0.5)',
      }}
    >
      {/* 标题区 */}
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <h2 style={{ margin: 0, fontSize: 15, fontWeight: 700, letterSpacing: 0.5 }}>
          {Math.round(iso.minutes)} 分钟生活圈体检
        </h2>
        {onClose && (
          <button
            onClick={onClose}
            aria-label="关闭体检报告"
            style={{
              background: 'transparent',
              border: 'none',
              color: THEME.textDim,
              cursor: 'pointer',
              fontSize: 16,
              lineHeight: 1,
            }}
          >
            ✕
          </button>
        )}
      </header>

      {/* 降级提示：诚实展示数据质量，不用假数据冒充 */}
      {(result.degraded || iso.data_source === 'offline-synthetic') && (
        <div
          className="ltp-degraded-banner"
          style={{
            background: 'rgba(255, 213, 79, 0.10)',
            border: '1px solid rgba(255, 213, 79, 0.35)',
            color: 'var(--lt-warning)',
            borderRadius: 6,
            padding: '6px 10px',
            fontSize: 12,
            marginBottom: 10,
          }}
        >
          {iso.data_source === 'offline-synthetic'
            ? '离线合成路网数据（评测模式）'
            : `部分方向降级估算（${iso.degraded_directions}/${iso.rays.length}）`}
        </div>
      )}

      {/* 概览卡片 */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 14 }}>
        <div style={{ background: THEME.panel, borderRadius: 8, padding: '8px 10px' }}>
          <div style={{ fontSize: 11, color: THEME.textDim }}>等时圈面积</div>
          <div style={{ fontSize: 15, fontWeight: 700, color: THEME.green }}>
            {formatArea(iso.area_m2)}
          </div>
        </div>
        <div style={{ background: THEME.panel, borderRadius: 8, padding: '8px 10px' }}>
          <div style={{ fontSize: 11, color: THEME.textDim }}>设施覆盖</div>
          <div style={{ fontSize: 15, fontWeight: 700 }}>
            {cov.inside_pois}/{cov.total_pois} 个 POI
          </div>
        </div>
      </div>

      {/* 盲区摘要：红点 + 类别名，扫一眼知道缺什么 */}
      {cov.blind_spots.length > 0 ? (
        <div
          className="ltp-blindspots"
          style={{
            border: `1px solid ${THEME.red}55`,
            background: `${THEME.red}0d`,
            borderRadius: 8,
            padding: '8px 10px',
            marginBottom: 12,
          }}
        >
          <div style={{ fontSize: 12, color: THEME.red, marginBottom: 4 }}>
            ⚠ 服务盲区（覆盖率 &lt; {formatPercent(cov.threshold)}）
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {cov.blind_spots.map((key) => {
              const cat = cov.categories.find((c) => c.key === key);
              return (
                <span
                  key={key}
                  style={{
                    fontSize: 12,
                    padding: '2px 8px',
                    borderRadius: 999,
                    background: `${THEME.red}1a`,
                    color: THEME.red,
                    border: `1px solid ${THEME.red}44`,
                  }}
                >
                  ● {cat?.label ?? key}
                </span>
              );
            })}
          </div>
        </div>
      ) : (
        <div
          style={{
            border: `1px solid ${THEME.green}44`,
            background: `${THEME.green}0d`,
            borderRadius: 8,
            padding: '8px 10px',
            marginBottom: 12,
            fontSize: 12,
            color: THEME.green,
          }}
        >
          ✓ 六类设施均无盲区
        </div>
      )}

      {/* 类别覆盖率条形图 */}
      <section aria-label="分类覆盖率">
        {sorted.map((c) => (
          <CoverageBar key={c.key} category={c} threshold={cov.threshold} />
        ))}
      </section>

      {/* 脚注：数据口径 */}
      <footer
        style={{
          marginTop: 12,
          paddingTop: 10,
          borderTop: `1px solid ${THEME.border}`,
          fontSize: 11,
          color: THEME.textDim,
          lineHeight: 1.6,
        }}
      >
        中心 ({iso.center.lat.toFixed(4)}, {iso.center.lng.toFixed(4)}) · 步速{' '}
        {iso.walking_speed_kmh} km/h · POI 来源 {result.poi_source}
        <br />
        覆盖率 = 圈内同类设施数 ÷ 周边同类设施总数
      </footer>
    </aside>
  );
}
