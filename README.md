# LifeTrip

**潮流 City Walk · 黑绿地铁美学 · 独立仓库**

与 RedTrip 无关：不用上图 API、不做典籍叙事。数据以 **OpenStreetMap POI + OSRM 步行** 为主。

## 数据源（详见 `docs/DATA_SOURCES.md`）

| 用途 | 来源 |
|---|---|
| 咖啡/Bar/古着/画廊 POI | OSM Overpass |
| 步行 polyline | OSRM demo |
| 地图底图 | CARTO Dark Matter |
| 离线兜底 | `content/fixtures/*.json` |

## 快速开始

```bash
pnpm install
pip install -r apps/api/requirements.txt

# 终端 1 — API
pnpm dev:api

# 终端 2 — Web
pnpm dev
```

Web: http://127.0.0.1:43123  
API: http://127.0.0.1:8800/v1/health

强制离线模式（跳过 Overpass/OSRM）：

```bash
LIFETRIP_OFFLINE=1 pnpm dev:api
```

## 结构

```
apps/web/          Vite + React + MapLibre
apps/api/          FastAPI 规划服务
content/fixtures/  离线示范线
docs/              数据源与架构说明
```

## API

- `GET /v1/health`
- `GET /v1/districts`
- `GET /v1/osm/status`
- `POST /v1/routes/plan` — `{ vibe, district_id, duration_min, pace }`

## 与 RedTrip 差异

| | RedTrip | LifeTrip |
|---|---|---|
| 视觉 | 米色书页 | 黑绿地铁 |
| 数据 | 上图馆藏 | OSM 街面 POI |
| 叙事 | 典籍/溯源 | 潮流 city walk |
