# LifeTrip

**潮流 City Walk · 黑绿地铁美学**

仓库：[github.com/MiLab-Bit/LifeTrip](https://github.com/MiLab-Bit/LifeTrip)

把「出门去哪逛」从查攻略、比榜单，压缩成 **选一条线、进一站点、走起来**。数据以 OpenStreetMap 街面 POI + 步行路由为主，谈当下街面，不谈文献馆藏。

完整产品规划见 **[docs/PRODUCT_DESIGN.md](./docs/PRODUCT_DESIGN.md)**。

**竞争单位：** 不是「推荐好不好」，而是 **WalkTask 能不能办完**（规划 → 开走 → 改线 → 终站）。

## 当前版本（v0.4 · WalkTask Agent + Narrative）

| 能力 | 状态 |
|---|---|
| WalkTask 全生命周期（plan / start / skip / reroll / complete） | ✅ |
| **curated 多片区**（安福 / 愚园 / 巨富 / 西岸 × 多 vibe） | ✅ |
| **文案润色**（editor 基准 + local + 可选 LLM） | ✅ |
| 任务 Memory + 跨会话 resume | ✅ |
| L0–L2 权限确认 | ✅ |
| Eval Harness（50 题回归） | ✅ |
| 主动推进（降雨改线提案） | ✅ |
| PWA manifest | ✅ |
| OSM Overpass + OSRM 步行规划 | ✅ |
| MapLibre 暗色线路图 | ✅ |

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
apps/web/              前端（Vite + React + MapLibre + PWA）
apps/api/              WalkTask API（FastAPI + SQLite Memory）
packages/contracts/    共享类型（RouteEnvelope · WalkTask · Stop）
content/curated/       编辑精选 POI（9 条线 × 4 片区）
content/narratives/    润色基准文案（editor / LLM）
content/eval/          回归题库
content/fixtures/      离线示范线
docs/                  产品 / 数据 / 架构文档
```

## 主要 API

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/v1/walks/plan` | 理解意图 + 创建 WalkTask |
| GET | `/v1/walks/resume` | 恢复未完成任务 |
| POST | `/v1/walks/{id}/start` | 开始漫步 |
| POST | `/v1/walks/{id}/skip` | 跳过站（L2 确认） |
| POST | `/v1/walks/{id}/reroll` | 换站（L2 确认） |
| POST | `/v1/walks/{id}/complete` | 完成 + 验证 |
| GET | `/v1/walks/{id}/proactive` | 降雨改线提案 |
| POST | `/v1/eval/run` | 跑回归题库 |

Legacy：`POST /v1/routes/plan` 仍可用（仅返回线路，不创建任务）。

## Eval

```bash
pnpm eval   # API 需已启动
```

## LLM 文案润色（可选）

```bash
# .env 中设置 LIFETRIP_LLM_POLISH=1 和 LIFETRIP_LLM_API_KEY
python3 scripts/polish_curated.py   # 批量润色 curated 站
```

- **绿标 curated**：优先 `content/narratives/` 编辑器基准
- **蓝标 OSM**：local 规则润色；开启 LLM 后实时润色并 cache
- 润色严格绑定 POI ID / 名称，不编造地址或价格

## curated 覆盖

| 片区 | 线路 |
|---|---|
| 安福—武康 | 咖啡 · 夜行 · 古着 |
| 愚园—江苏路 | 咖啡 · 夜行 · 画廊 |
| 巨富—富民 | 古着 · 咖啡 |
| 西岸—滨江 | 画廊 |

---

## Temporal 编排接入（2026-10）

LifeTrip 的 WalkTask 生命周期已接入 **Temporal Server v1.27**，实现任务持久化、人在回路审批和断点恢复。

### WalkTask 生命周期

```
plan_walktask → start_walktask
     ├──→ skip_stop (Update, 人在回路)
     ├──→ reroll_stop (Update, 人在回路)
     └──→ complete_walktask
```

### 代码结构

```
apps/api/app/temporal/
├── common.py        # WalkTaskInput dataclass
├── activities.py    # 4 个同步 Activity（plan/start/reroll/complete）
├── worker.py        # Worker 启动器（ThreadPoolExecutor）
└── workflows/
    └── walktask.py  # WalkTaskWorkflow（带人在回路 Update）
```

### 配置

```bash
TEMPORAL_ADDRESS=127.0.0.1:7233
TEMPORAL_NAMESPACE=lifetrip
TEMPORAL_TASK_QUEUE=lifetrip-task-queue
```
