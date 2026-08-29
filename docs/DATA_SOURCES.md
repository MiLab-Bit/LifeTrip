# LifeTrip 数据源规划

> 目标：潮流 city walk，**不用上图 API / 典籍 / 馆藏**。数据以「当下可逛的街面 POI + 步行几何」为主。

## 选型结论（v1 已接入）

| 层级 | 数据源 | 用途 | 密钥 | 状态 |
|---|---|---|---|---|
| **POI** | [OpenStreetMap Overpass](https://wiki.openstreetmap.org/wiki/Overpass_API) | 咖啡、Bar、古着、画廊等可逛点 | 无 | ✅ 主源 |
| **步行几何** | [OSRM Demo](https://router.project-osrm.org/) | 站间 polyline、距离、时长 | 无 | ✅ 主源 |
| **底图** | [CARTO Dark Matter](https://carto.com/basemaps/) | 黑绿地铁感地图底图 | 无 | ✅ Web |
| **离线兜底** | `content/fixtures/*.json` | Overpass/OSRM 不可达时 | — | ✅ |

## 不采用（及原因）

| 数据源 | 原因 |
|---|---|
| 上海图书馆 / SLC API | 典籍与馆藏叙事，与 LifeTrip 定位冲突 |
| CBDB / 古籍新生 | 典籍人物链，用户明确不要 |
| 纯 LLM 编造 POI | 无法保证「真店真坐标」，易幻觉 |
| 小红书 / 大众点评爬虫 | 无稳定官方 API，合规与维护成本高 |
| Foursquare / Google Places | 国内覆盖与访问不稳定 |

## 可选扩展（v2+）

| 数据源 | 场景 | 备注 |
|---|---|---|
| **高德 POI + 步行** | 国内店名/新店更全 | 需 `AMAP_KEY`，作 OSM 补全而非替代 |
| **Wikidata SPARQL** | 公共艺术、地标一句话 | 只取坐标+标签，不做典籍叙事 |
| **OpenTripMap** | 旅游类 POI 补充 | 与 OSM 去重后合并 |
| **自研 curated 清单** | 安福/愚园等「编辑精选」 | JSON 维护网红店，Overpass 作底 |

## Vibe → OSM 标签映射

| LifeTrip 主题 | Overpass 筛选（优先） |
|---|---|
| `neon` 夜行霓虹 | `amenity=bar`, `amenity=pub`, `amenity=nightclub`, `amenity=restaurant` + `outdoor_seating` |
| `coffee` 咖啡巡游 | `amenity=cafe`, `shop=coffee` |
| `vintage` 古着淘街 | `shop=clothes`, `shop=second_hand`, `shop=charity`, `shop=variety_store` |
| `gallery` 画廊串游 | `tourism=gallery`, `tourism=museum`, `amenity=arts_centre` |

## 片区 → 搜索框（bbox）

预置上海 city walk 热区 bbox（WGS84），见 `apps/api/app/districts.py`。

## 管线

```
Brief(vibe, district, duration)
  → Overpass 拉 POI
  → 按 vibe 过滤 + 去重
  → 选 3–5 站（spread + 时长约束）
  → OSRM foot 排序 + polyline
  → 模板化潮流文案（v1 规则；v2 可接 LLM 只改写不增事实）
  → Web MapLibre 展示
```

## 运维注意

- Overpass 公共实例有速率限制；失败自动换 mirror + 回落 fixture
- OSRM demo 仅供开发/demo，生产应自建或使用商业路由
- 国内访问 Overpass/OSRM 可能慢，`.env` 可设 `LIFETRIP_OFFLINE=1` 强制 fixture
