# LifeTrip · 潮流 City Walk 助手

> **把「出门去哪逛」从查攻略、比榜单，压缩成 选一条线、进一站点、走起来。**
> 黑绿地铁美学，谈当下街面，不谈文献馆藏。

**▶ 立即体验：[https://lifetrip.sy-realm.ltd](https://lifetrip.sy-realm.ltd)**

---

## 使用方式

1. 打开 **[lifetrip.sy-realm.ltd](https://lifetrip.sy-realm.ltd)**
2. **选一条线**：从编辑精选的City Walk 线路中挑一条（安福 / 愚园 / 巨富 / 西岸 × 咖啡、夜行、古着、画廊多种 vibe），或描述你想要的感觉
3. **进一站点**：线路以「任务卡」形式展开——每一站做什么、看什么，走起来就有
4. **走起来**：途中随时可以**跳过**（skip）、**重抽**（reroll）、**完成**（complete），也可以让 App 主动改线
5. 下雨了？App 会主动提议改线——不是等你发现淋成落汤鸡

任务进度跨会话保留：走到一半退出，下次打开接着走。

> 可安装为 PWA：添加到主屏幕后全屏运行，通勤地铁里也能翻线路。

---

## 品牌与产品能力

LifeTrip 的竞争单位不是「推荐好不好」，而是 **WalkTask 能不能办完**——规划 → 开走 → 改线 → 终站，一条线走到底才算数。

| 能力 | 状态 |
| --- | --- |
| WalkTask 全生命周期（plan / start / skip / reroll / complete） | ✅ |
| curated 多片区（安福 / 愚园 / 巨富 / 西岸 × 多 vibe） | ✅ |
| 文案润色（editor 基准 + local + 可选 LLM） | ✅ |
| 任务 Memory + 跨会话 resume | ✅ |
| L0–L2 权限确认 | ✅ |
| Eval Harness（50 题回归） | ✅ |
| 主动推进（降雨改线提案） | ✅ |
| PWA manifest | ✅ |
| OSM Overpass + OSRM 步行规划 | ✅ |
| MapLibre 暗色线路图 | ✅ |

---

## 技术与特色

| 层 | 选型 |
| --- | --- |
| 前端 | React 19 · Vite 8 · TypeScript 5.9 · MapLibre GL 6 · PWA |
| 地图与数据 | OpenStreetMap（Overpass POI）+ OSRM 步行路由 + Carto 暗色底图 |
| 后端 | FastAPI + SQLite Memory（任务状态机 + 跨会话记忆） |
| 工程 | pnpm monorepo（apps/web + apps/api + packages/contracts 共享类型）· Eval Harness 50 题回归 |

**工程特色**：

- **开放数据零成本**：POI 走 OSM Overpass、路由走 OSRM——不绑任何地图厂商的付费配额，街面数据谈「当下」而不是陈年文库
- **WalkTask 是状态机不是聊天**：任务生命周期显式建模（人在回路的 skip/reroll 都要确认），进度可恢复、可回归测试
- **契约先行**：web 与 api 共享 `packages/contracts` 类型（RouteEnvelope · WalkTask · Stop），前后端改契约同一处
- **暗色地图即产品**：MapLibre 自定义暗色样式，线路图是美学主体也是功能主体

---

## 业务建模：把城市漫步变成可恢复的任务

LifeTrip 将一次出行明确表示为 `WalkTask`：它持有 `BriefInput`（偏好与约束）、`RouteEnvelope`（路线与站点）、`current_stop_index`（当前进度）、`PendingAction`（待确认动作）和 `WalkTaskStatus`（planned / walking / paused / completed / cancelled）。`Stop` 是可操作的任务节点，而不是只有名称的地点卡片。

**为什么这样设计：** 用户真正完成的是一个不断受天气、路线、时间及主观兴趣影响的连续任务，而不是一次性的 POI 推荐。任务状态独立于聊天上下文并由 SQLite 保存，支持重新打开后续走；“跳过 / 重抽 / 改线”的意图可以先生成提案，再由用户确认执行。

**源码入口：** [业务契约](apps/api/app/contracts.py) · [任务服务](apps/api/app/walk/service.py) · [权限动作](apps/api/app/walk/permissions.py) · [持久化](apps/api/app/memory/store.py)。

## 工程完成度与验证边界

- **已在仓库中实现：** 路线、任务、权限动作的 Pydantic 契约；SQLite 的会话与任务持久化；路线规划、OSM/OSRM 数据接入及前端地图；`apps/api/app/eval/harness.py` 与 `tests/` 中的离线门禁和空间/烟测。
- **可复核的工程配置：** [CI](.github/workflows/ci.yml) 与 [Release 工作流](.github/workflows/release.yml)。README 中的 50 题 Eval Harness 是项目设计/样本规模，不代表 50 个真实道路场景已验证成功。
- **待加强的业务不变量：** `walk/service.py` 的 `confirm=True` 分支目前没有在服务层强制核对待确认动作的 ID/版本；`memory/store.py` 更新时没有乐观锁版本检查。这里属于可识别的后续工程任务，不能简单等同“已具备强授权与并发安全”。


---

© LifeTrip · MiLab-Bit
