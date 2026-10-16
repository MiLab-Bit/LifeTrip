# 🚇 LifeTrip

**潮流 City Walk · 黑绿地铁美学**

> 🏆 **上海开源大赛参赛作品**

🔗 **在线体验：[lifetrip.sy-realm.ltd](https://lifetrip.sy-realm.ltd)**

---

把「出门去哪逛」从查攻略、比榜单，压缩成 **选一条线、进一站点、走起来**。

LifeTrip 是一个面向年轻城市探索者的 City Walk 智能规划工具——选个主题和时长，AI 帮你拼一条当下最好逛的步行线路，每站配一句够味儿的文案，走完还能生成漫步卡片分享给朋友。

完整产品规划见 **[docs/PRODUCT_DESIGN.md](./docs/PRODUCT_DESIGN.md)**。

## ✨ 核心功能

### WalkTask 全生命周期

一次完整的漫步从规划到终站，全程陪伴：

```
选线（Brief） → 确认（Confirm） → 漫步中（Walk） → 终到站（Done）
```

- 🗺️ **智能选线**：选主题 + 时长，自动拼站点序列
- 🔄 **实时改线**：走到一半想换站？跳过 / 换站 / 降雨改线，随时调整
- 🏆 **终到站验收**：走完验证，生成漫步卡片

### v0.5 新功能（本次升级）

| 功能 | 说明 |
|---|---|
| 🧬 **WalkDNA 画像** | 自动学习你的偏好（节奏 / 主题 / 价位），推荐越来越准 |
| 🏅 **探索图谱** | 11 枚成就徽章 + 街区覆盖度 + POI 收藏，留住探索者 |
| 📖 **分层叙事** | 每站文案支持 quick / standard / deep 三档深度切换 |
| 🎴 **漫步卡片** | Canvas 实时生成可分享的线路图，一键保存到相册 |
| 👥 **社区线路** | 发布你的路线到社区，浏览他人路线，互相评分 |

### 竞争单位

不是「推荐好不好」，而是 **WalkTask 能不能办完**（规划 → 开走 → 改线 → 终站）。

## 🚀 快速开始

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

## 🏗️ 项目结构

```
apps/web/              前端（Vite + React + MapLibre + PWA）
apps/api/              WalkTask API（FastAPI + SQLite Memory）
├── app/explore/       探索图谱（徽章 / 覆盖度 / POI 采集）
├── app/community/     社区线路（发布 / 评分 / 列表）
├── app/narrative/     分层叙事引擎（quick / standard / deep）
└── app/memory/        任务 Memory + WalkDNA 画像存储
packages/contracts/    共享类型（前后端契约）
content/curated/       编辑精选 POI
content/narratives/    润色基准文案
docs/                  产品 / 架构 / 升级文档
```

## 📡 API 概览

### WalkTask 生命周期

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/v1/walks/plan` | 理解意图 + 创建 WalkTask |
| GET | `/v1/walks/resume` | 恢复未完成任务 |
| POST | `/v1/walks/{id}/start` | 开始漫步 |
| POST | `/v1/walks/{id}/skip` | 跳过站（L2 确认） |
| POST | `/v1/walks/{id}/reroll` | 换站（L2 确认） |
| POST | `/v1/walks/{id}/complete` | 完成 + 验证 |

### v0.5 新增

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/v1/profile/{session_id}` | WalkDNA 画像 |
| POST | `/v1/profile/{session_id}/refresh` | 刷新画像 |
| GET | `/v1/explore/{session_id}` | 探索图谱（徽章 / 覆盖 / 收藏） |
| GET | `/v1/narrative/{task_id}/{stop}/layered` | 分层叙事 |
| GET | `/v1/walk-card/{task_id}` | 漫步卡片数据 |
| POST | `/v1/rate/{task_id}` | 评分 |
| GET | `/v1/community/routes` | 社区线路列表 |
| POST | `/v1/community/publish/{task_id}` | 发布线路到社区 |
| POST | `/v1/community/{route_id}/rate` | 给社区线路打分 |

完整 API 文档：启动后访问 `/docs`（Swagger UI）。

## 🌐 在线部署

| 环境 | 地址 |
|---|---|
| 📱 **Web App** | **[https://lifetrip.sy-realm.ltd](https://lifetrip.sy-realm.ltd)** |
| API 服务 | https://lifetrip.sy-realm.ltd/v1/health |
| Swagger 文档 | https://lifetrip.sy-realm.ltd/docs |

## 🎨 设计语言

**黑绿地铁美学**：深色底 + 翠绿 accent + 地铁线路色编码。每个片区对应一条「虚拟地铁线」，站点序号像地铁站台编号。文案风格短、狠、有态度——不啰嗦，不端着。

## 📦 curated 覆盖

| 片区 | 线路 |
|---|---|
| 安福—武康 | 咖啡 · 夜行 · 古着 |
| 愚园—江苏路 | 咖啡 · 夜行 · 画廊 |
| 巨富—富民 | 古着 · 咖啡 |
| 西岸—滨江 | 画廊 |

## 🛠️ 技术栈

| 层 | 选型 |
|---|---|
| 前端 | React + TypeScript + Vite + MapLibre GL + PWA |
| 后端 | Python FastAPI + SQLite + Temporal |
| 数据 | OpenStreetMap + OSRM 步行路由 |
| 共享契约 | TypeScript contracts 包（前后端类型同步） |
| 部署 | 阿里云 ECS + Nginx + Cloudflare DNS |

## 📄 License

MIT

---

<p align="center">
  🏆 上海开源大赛参赛作品
  <br>
  <a href="https://lifetrip.sy-realm.ltd">lifetrip.sy-realm.ltd</a>
</p>
