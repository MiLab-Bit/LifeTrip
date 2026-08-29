# LifeTrip 架构

```
apps/web (Vite + React + MapLibre)
    │  POST /v1/routes/plan
    ▼
apps/api (FastAPI)
    ├─ districts.py     片区 bbox
    ├─ osm.py           Overpass POI
    ├─ osrm.py          步行 polyline
    ├─ planner.py       选站 + 排序
    └─ narrative.py     规则文案（无典籍）
content/fixtures/       离线线路
```

## 与 RedTrip 关系

**独立仓库**，不依赖 RedTrip monorepo。仅借鉴「Brief → 加载 → 线路 → 漫步」交互形态。
