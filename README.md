# LifeTrip

**潮流 City Walk · 黑绿地铁美学**

仓库：[github.com/MiLab-Bit/LifeTrip](https://github.com/MiLab-Bit/LifeTrip)

把「出门去哪逛」从查攻略、比榜单，压缩成 **选一条线、进一站点、走起来**。数据以 OpenStreetMap 街面 POI + 步行路由为主，谈当下街面，不谈文献馆藏。

完整产品规划（含 KORA Agent 框架映射）见 **[docs/PRODUCT_DESIGN.md](./docs/PRODUCT_DESIGN.md)**。

**竞争单位：** 不是「推荐好不好」，而是 **WalkTask 能不能办完**（规划 → 开走 → 改线 → 终站）。

## 当前版本（v0.2）

| 能力 | 状态 |
|---|---|
| 选线 Brief（主题 / 片区 / 时长 / 步速） | ✅ |
| OSM Overpass POI + OSRM 步行规划 | ✅ |
| MapLibre 暗色线路图 | ✅ |
| 离线 fixture 兜底 | ✅ |

## 数据源

详见 [docs/DATA_SOURCES.md](./docs/DATA_SOURCES.md)

| 用途 | 来源 |
|---|---|
| POI | OSM Overpass |
| 步行线 | OSRM |
| 底图 | CARTO Dark Matter |

## 快速开始

```bash
pnpm install
pip install -r apps/api/requirements.txt

# 终端 1 — API
pnpm dev:api

# 终端 2 — Web
pnpm dev
```

- Web: http://127.0.0.1:43123  
- API: http://127.0.0.1:8800/v1/health  

离线模式：`LIFETRIP_OFFLINE=1 pnpm dev:api`

## 结构

```
apps/web/           前端（Vite + React + MapLibre）
apps/api/           规划 API（FastAPI）
content/fixtures/   离线示范线
docs/               产品 / 数据 / 架构文档
```

## API

- `GET /v1/health`
- `GET /v1/districts`
- `GET /v1/osm/status`
- `POST /v1/routes/plan` — `{ vibe, district_id, duration_min, pace }`
