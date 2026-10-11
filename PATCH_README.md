# LifeTrip 等时圈引擎补丁 — 集成说明（PATCH_README）

「15 分钟生活圈智能体检」：中心点 → 真实路网算 15 分钟步行等时圈 → 六类设施
覆盖分析 → 体检报告 + 服务盲区。对应 OSCC 百度地图命题一（开源 AI 工具赛道）。

本包自包含：不依赖 GitHub 上未拉到的代码，所有对 LifeTrip 现有结构的假设
都在代码里标了 `TODO-ADAPT`，本地集成时按注释对齐即可。

---

## 1. 文件清单与放置位置

```
apps/api/app/isochrone/            # 等时圈核心包（全部新增）
├── __init__.py                    # 对外导出
├── geo.py                         # 球面距离/方位角/凸包/面积/点在多边形（零依赖，不用 shapely）
├── schemas.py                     # Pydantic 模型：请求/响应/GeoJSON/覆盖报告
├── osrm.py                        # 传输层：HttpOsrmTransport（超时/重试/分批/并发）+ OfflineOsrmTransport
├── engine.py                      # 扇形采样 → /table 批量算路 → ring/hull 插值多边形 + 降级
├── coverage.py                    # 六类别覆盖率与盲区判定
└── pois.py                        # POI 源适配：Overpass（在线）/ curated fixtures（离线）
apps/api/app/api/v1/isochrone.py   # POST /v1/isochrone/analyze（L0 只读）
web/src/components/HealthReportPanel.tsx  # 前端：地图叠加 + 体检报告面板（纯 CSS 图表）
content/fixtures/isochrone/
├── osrm_table.json                # 离线合成路网模型（方向绕行系数，确定性）
└── pois.json                      # curated POI 集（34 个，六类别）
content/eval/isochrone_cases.json  # 10 题回归用例 + 期望值（由离线管线实际运行生成）
tests/
├── test_isochrone.py              # 全链路测试（28 项，已在本机跑通）
└── generate_eval_fixtures.py      # fixtures/期望值生成器（可重跑校验确定性）
PATCH_README.md                    # 本文件
```

## 2. 后端集成

### 2.1 挂路由（main.py 或路由注册处）

```python
from app.api.v1.isochrone import router as isochrone_router
app.include_router(isochrone_router, prefix="/v1")
```

TODO-ADAPT：如果现有 /v1/walks、/v1/eval 路由是集中在一个 `app/api/v1/__init__.py`
或 `api.py` 里注册的，把这两行并进去；`prefix="/v1"` 与现有保持一致。

### 2.2 依赖

后端仅用到 LifeTrip 已有的栈：`fastapi`、`pydantic>=2`、`httpx`。
**不新增任何依赖**（不用 shapely/numpy/scipy——几何全是手写）。

### 2.3 配置项（环境变量，均有默认值）

| 变量 | 默认 | 说明 |
|---|---|---|
| `LIFETRIP_OFFLINE` | 空 | `1` 时走离线合成路网 + curated POI（评测/CI 用） |
| `LIFETRIP_OSRM_URL` | `http://127.0.0.1:5000` | OSRM 服务地址 |
| `LIFETRIP_OSRM_PROFILE` | `foot` | OSRM profile，与步行规划模块保持同口径 |
| `LIFETRIP_OSRM_TIMEOUT` | `5` | 单次 OSRM 请求超时秒数 |
| `LIFETRIP_OVERPASS_URL` | overpass-api.de | Overpass 端点 |
| `LIFETRIP_FIXTURES_DIR` | 仓库相对路径 `content/fixtures` | fixtures 根目录 |

TODO-ADAPT：这些读环境变量的地方应换成项目 settings 对象注入。

## 3. 前端集成

```tsx
import HealthReportPanel from './components/HealthReportPanel';

// 在持有 MapLibre 地图实例的页面组件里：
<HealthReportPanel result={analyzeResp} map={mapInstance} onClose={() => setReport(null)} />
```

- `result` 是 `POST /v1/isochrone/analyze` 的响应 JSON（类型定义已内嵌在组件文件里）。
- 组件自己不发请求、不管数据获取，方便接进现有的数据流。
- 覆盖率条形图为纯 CSS 实现，无新增 npm 依赖。
- TODO-ADAPT：`THEME` 常量里的色值换成项目 design tokens；`ltp-` className
  前缀按现有约定改名。

## 4. 验收命令

```bash
# 1. 单元/回归测试（离线，无网络）
pytest tests/test_isochrone.py -v

# 2. fixtures 确定性自检（重跑生成器，git diff 应为空）
python tests/generate_eval_fixtures.py && git diff --stat content/

# 3. 起服务后 curl 冒烟（离线模式）
LIFETRIP_OFFLINE=1 uvicorn app.main:app --reload   # 按项目实际入口
curl -s -X POST http://127.0.0.1:8000/v1/isochrone/analyze \
  -H 'Content-Type: application/json' \
  -d '{"center":{"lat":31.2304,"lng":121.4737},"minutes":15}' | python -m json.tool

# 4. 在线模式（需要本地 OSRM foot profile 在跑）
curl -s -X POST http://127.0.0.1:8000/v1/isochrone/analyze \
  -H 'Content-Type: application/json' \
  -d '{"center":{"lat":31.2304,"lng":121.4737},"minutes":15,"poi_source":"overpass"}'
```

eval 接入：`content/eval/isochrone_cases.json` 是标准回归集。
TODO-ADAPT：若 `/v1/eval/run` 有既定的题目 schema（比如在 packages/contracts），
把 `id/title/request/expect` 字段映射过去；断言逻辑可直接复用
`tests/test_isochrone.py::TestEvalRegression` 的实现。

## 5. 坐标系注意（BD-09 / WGS-84 / GCJ-02）

- 本包全链路 **WGS-84**：OSRM、Overpass、GeoJSON 都是 WGS-84，前后端无歧义。
- **百度系（BD-09）不能直接混入**：百度地图 API 的输入输出都是 BD-09，
  相对 WGS-84 偏移几百米——对「15 分钟步行圈」这种 1km 尺度的判断，
  不转换会把可达错判成不可达。GCJ-02（高德/腾讯）同理偏移约几百米。
- **改造铁律**：若未来接百度地图 API（算路或 POI），坐标转换只做在
  adapter 层——即 `osrm.py` 的 `HttpOsrmTransport`（换成百度算路时）和
  `pois.py` 的 POI 源（换百度 POI 时）的出参处统一 BD-09→WGS-84。
  `engine.py` / `coverage.py` / 前端永远只处理 WGS-84，不需要知道百度存在。

## 6. 需要本地确认/适配的点（TODO-ADAPT 汇总）

| 位置 | 事项 |
|---|---|
| `isochrone.py` 路由 | L0 权限标注换成项目真实的权限依赖（若用 Depends(require_level=0)） |
| `isochrone.py` 路由 | 环境变量读配置换成 settings 注入 |
| `osrm.py` | OSRM base_url/profile 与步行规划模块共用配置 |
| `pois.py` | fixtures 目录解析换成项目 settings（若已有） |
| `schemas.py` | 若 packages/contracts 已有 LatLng/GeoJSON 类型则复用 |
| `HealthReportPanel.tsx` | 主题色换 design tokens；className 前缀对齐 |
| `isochrone_cases.json` | eval schema 字段映射到 /v1/eval/run 的题目格式 |
| `tests/` | sys.path 注入方式若项目有 conftest.py 可简化 |

## 7. 已验证 / 未验证（诚实清单）

**已在本机验证（sandbox，Python 3.11）**：
- `pytest tests/test_isochrone.py`：28 项全部通过（含 OSRM mock 的重试/分批/
  部分失败降级、引擎插值、API 路由、10 题 eval 回归）。
- fixtures 生成器重跑两次输出 byte 级一致（确定性成立）。
- `HealthReportPanel.tsx` 通过 `tsc --strict`（react18 + maplibre-gl 4 类型）零错误。

**未执行，需本地验证**：
- 真实 OSRM 服务（在线模式）下的等时圈效果——mock 只验证协议与容错。
- Overpass 真实查询（同上）。
- 浏览器里的组件渲染效果与 MapLibre 图层视觉（需要本地 `npm run dev`）。
- 与 LifeTrip 仓库真实代码的合并（本包按任务说明的架构约定编写，未经真实仓库编译）。
