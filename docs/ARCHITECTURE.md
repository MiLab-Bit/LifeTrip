# LifeTrip 技术架构

> 产品五系统见 [PRODUCT_DESIGN.md](./PRODUCT_DESIGN.md) 第六节；分层路线图见第十节。

## 现状（Layer 0 · Wedge 雏形）

```
apps/web
    │  POST /v1/routes/plan
    ▼
apps/api
    ├─ districts / osm / osrm
    └─ planner          ← 将演进为 plan/ + walk/ + memory/
content/fixtures/
```

**已有：** 规划 + 地图（Execute 之 L1 草稿）  
**未有：** WalkTask 会话、Memory、Verify、Proactive、Eval

## 目标形态（Layer 2–3）

```
apps/web
    ▼
packages/contracts       RouteEnvelope · WalkTask · Stop
    ▼
apps/api
    ├─ intent/           问题 vs 任务
    ├─ memory/           漫步档案（任务级）
    ├─ plan/             三轴 + 冲突检测
    ├─ walk/             执行 + L0–L2 权限
    ├─ verify/           POI/几何/完成态
    ├─ proactive/        天气、resume 提醒
    └─ eval/             回归题库（L3）
content/
    ├─ curated/
    ├─ cache/
    └─ eval/cases.json
```

原则：**先 WalkTask 闭环，再拆 package；先规则，再 LLM；先单城，再多城。**
