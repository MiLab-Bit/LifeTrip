# LifeTrip 技术架构

> 随产品分层演进，详见 [PRODUCT_DESIGN.md](./PRODUCT_DESIGN.md) 第六节「分层路线图」。

## 现状（Layer 0）

```
apps/web (Vite + React + MapLibre)
    │  POST /v1/routes/plan
    ▼
apps/api (FastAPI)
    ├─ districts.py     片区 bbox
    ├─ osm.py           Overpass POI
    ├─ osrm.py          步行 polyline
    └─ planner.py       选站 + 排序 + 规则文案
content/fixtures/       离线线路
```

## 目标形态（Layer 3 示意）

```
apps/web | apps/mini（可选）
    ▼
packages/contracts      路线 / 站点 / 会话契约
    ▼
apps/api
    ├─ ingest/          POI 聚合（OSM + 高德 + Curated）
    ├─ planner/         三轴评分 + 路径优化
    ├─ narrative/       LLM 润色（只改写，不增事实）
    └─ session/         行中改线、进度
content/
    ├─ fixtures/
    ├─ curated/         编辑精选站点
    └─ cache/           POI 快照
```

原则：**先跑通闭环，再拆 package；先规则，再模型；先单城，再多城。**
