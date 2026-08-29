# LifeTrip 技术架构

> 产品五系统见 [PRODUCT_DESIGN.md](./PRODUCT_DESIGN.md) 第六节；分层路线图见第十节。

## 现状（v0.3 · L1–L4 雏形）

```
apps/web
    │  POST /v1/walks/plan · skip · reroll · proactive
    ▼
packages/contracts       RouteEnvelope · WalkTask · Stop
    ▼
apps/api
    ├─ intent/           问题 vs 任务
    ├─ memory/store.py   SQLite 漫步档案
    ├─ plan/planner.py   curated 加权 + OSM 补位 + OSRM
    ├─ walk/service.py   执行 + L0–L2 权限
    ├─ verify/           POI/几何/完成态
    ├─ proactive/weather  Open-Meteo 降雨改线
    └─ eval/harness.py   50 题回归
content/
    ├─ curated/          编辑精选（安福咖啡线）
    ├─ cache/            Overpass 缓存
    ├─ eval/cases.json
    └─ fixtures/         离线 fallback
```

**已有：** WalkTask 闭环、Memory、权限、Eval、主动改线提案  
**待强化：** 真实用户 W4 复盘数据、LLM 润色、小程序

原则：**先 WalkTask 闭环，再拆 package；先规则，再 LLM；先单城，再多城。**

## 权限分级

| 级别 | 操作 | 确认 |
|---|---|---|
| L0 | 查 POI / 天气 / 算路 | 否 |
| L1 | 生成线路草稿 | 否 |
| L2 | skip / reroll / 应用改线 | 一次确认 |
| L3 | 预约 / 支付（v2+） | 强制 |

## 数据流

```
Brief + intent_text
    → Intent（plan_walk | question | resume_walk）
    → Plan（curated 优先 → OSM/cache → OSRM）
    → WalkTask（SQLite）
    → Walk UI（逐站 + skip/reroll）
    → Verify（complete）
    → Proactive（weather reroute）
```
