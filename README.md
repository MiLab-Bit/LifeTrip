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

© LifeTrip · MiLab-Bit
