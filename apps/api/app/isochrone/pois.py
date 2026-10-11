"""POI 来源适配层：Overpass（在线）与 curated fixtures（离线）。

为什么包一层：eval 的确定性要求离线 fixtures，线上又要真实 OSM 数据，
两者共用同一个 Poi 结构和六类别口径；未来接百度 POI API 时也在这里加
一个 BaiduPoiSource，并统一做 BD-09 → WGS-84 转换（百度坐标偏转约
几百米，不转直接算会把「可达」错判成「不可达」）。
TODO-ADAPT：百度 API 需要AK密钥，key 放 settings，不要硬编码。
"""

from __future__ import annotations

import json
import logging
import os
from typing import List, Optional, Sequence

import httpx

from .schemas import Poi

logger = logging.getLogger(__name__)

# Overpass 标签 → 六类别的映射。左边是 OSM tag 键值（保留英文原样），
# 未命中的 POI 直接丢弃（比归到 other 更干净，报告不出现噪音类别）。
_OVERPASS_CATEGORY_MAP = {
    "medical": [
        ("amenity", "hospital"), ("amenity", "clinic"), ("amenity", "doctors"),
        ("amenity", "pharmacy"), ("amenity", "dentist"),
    ],
    "education": [
        ("amenity", "school"), ("amenity", "kindergarten"), ("amenity", "college"),
        ("amenity", "university"), ("amenity", "library"),
    ],
    "shopping": [
        ("shop", "supermarket"), ("shop", "convenience"), ("shop", "mall"),
        ("shop", "grocery"), ("amenity", "marketplace"),
    ],
    "dining": [
        ("amenity", "restaurant"), ("amenity", "cafe"), ("amenity", "fast_food"),
        ("amenity", "food_court"), ("amenity", "bar"),
    ],
    "green": [
        ("leisure", "park"), ("leisure", "garden"), ("leisure", "pitch"),
        ("landuse", "forest"), ("natural", "wood"),
    ],
    "transit": [
        ("amenity", "bus_station"), ("railway", "station"), ("railway", "halt"),
        ("railway", "tram_stop"), ("amenity", "taxi"), ("highway", "bus_stop"),
    ],
}


def default_fixtures_dir() -> str:
    """fixtures 目录定位：环境变量优先，退回仓库相对路径。

    文件位于 apps/api/app/isochrone/pois.py → 仓库根是第 4 级父目录。
    TODO-ADAPT：LifeTrip 已有 settings/fixtures 路径解析的话，替换本函数。
    """
    env = os.environ.get("LIFETRIP_FIXTURES_DIR")
    if env:
        return env
    # 集成适配：优先复用项目既有路径解析 app/paths.py 的 FIXTURES，
    # 与 plan/walk 等模块指向同一份 content/fixtures，避免两处口径漂移。
    try:
        from app.paths import FIXTURES

        return str(FIXTURES)
    except Exception:  # 包外独立运行时回退仓库相对路径
        pass
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "content", "fixtures"))


class CuratedPoiSource:
    """读 content/fixtures/isochrone/pois.json 的精选 POI 集（离线/评测用）。"""

    def __init__(self, fixture_path: Optional[str] = None) -> None:
        self.path = fixture_path or os.path.join(default_fixtures_dir(), "isochrone", "pois.json")

    def load(self) -> List[Poi]:
        with open(self.path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        return [Poi(**item) for item in raw["pois"]]


class OverpassPoiSource:
    """在线 Overpass 查询：around 半径内的六类别 POI。

    容错：超时/网络错误重试一次，仍失败则抛 POISourceError，
    由路由层决定返回 502 还是降级 curated（当前路由选择降级 + degraded 标记，
    与等时圈引擎的降级哲学一致：能给出可解释的部分结果就给）。
    """

    def __init__(
        self,
        endpoint: str = "https://overpass-api.de/api/interpreter",
        timeout: float = 15.0,
        retries: int = 1,
        client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        self.endpoint = os.environ.get("LIFETRIP_OVERPASS_URL", endpoint)
        self.timeout = timeout
        self.retries = retries
        self._client = client

    def _query(self, lat: float, lng: float, radius_m: int) -> str:
        # 为什么手拼 QL 而不是库：overpass 库是非必要依赖，QL 字符串可控可测
        selectors = []
        for pairs in _OVERPASS_CATEGORY_MAP.values():
            for k, v in pairs:
                selectors.append(f'node["{k}"="{v}"](around:{radius_m},{lat},{lng});')
        body = "\n  ".join(selectors)
        return f"[out:json][timeout:25];\n({body}\n);\nout center;"

    async def fetch(self, lat: float, lng: float, radius_m: int) -> List[Poi]:
        client = self._client or httpx.AsyncClient(timeout=self.timeout)
        try:
            last_exc: Optional[Exception] = None
            data = None
            for attempt in range(self.retries + 1):
                try:
                    resp = await client.post(self.endpoint, data={"data": self._query(lat, lng, radius_m)})
                    resp.raise_for_status()
                    data = resp.json()
                    break
                except (httpx.TimeoutException, httpx.TransportError, httpx.HTTPStatusError) as exc:
                    last_exc = exc
            if data is None:
                raise POISourceError(f"overpass unreachable: {last_exc}")
            return self._parse(data)
        finally:
            if self._client is None:
                await client.aclose()

    def _parse(self, data: dict) -> List[Poi]:
        tag_map = {pair: cat for cat, pairs in _OVERPASS_CATEGORY_MAP.items() for pair in pairs}
        pois: List[Poi] = []
        for el in data.get("elements", []):
            tags = el.get("tags", {})
            for (k, v), cat in tag_map.items():
                if tags.get(k) == v:
                    lat = el.get("lat") or (el.get("center") or {}).get("lat")
                    lng = el.get("lon") or (el.get("center") or {}).get("lon")
                    if lat is None or lng is None:
                        continue
                    pois.append(
                        Poi(
                            id=f"osm-{el.get('type','n')}-{el.get('id','?')}",
                            name=tags.get("name", f"OSM {el.get('id')}"),
                            category=cat,
                            lat=float(lat),
                            lng=float(lng),
                        )
                    )
                    break
        return pois


class POISourceError(RuntimeError):
    pass


async def load_pois(
    source: str,
    lat: float,
    lng: float,
    radius_m: int = 1500,
    offline: bool = False,
    curated: Optional[CuratedPoiSource] = None,
    overpass: Optional[OverpassPoiSource] = None,
) -> List[Poi]:
    """统一入口：source=overpass/curated；离线模式强制 curated（确定性优先）。"""
    if source == "curated" or offline:
        return (curated or CuratedPoiSource()).load()
    try:
        return await (overpass or OverpassPoiSource()).fetch(lat, lng, radius_m)
    except POISourceError:
        # 在线源失败：降级 curated 并让调用方通过 degraded 标记告知用户
        logger.warning("overpass failed, fallback to curated fixtures")
        return (curated or CuratedPoiSource()).load()


class PoiLoadStatus:
    """带降级标志的加载结果：routes 层需要知道「在线源是否失败回落」，
    以便在响应里如实标 degraded，而不是让用户以为拿到了真实 OSM 数据。"""

    def __init__(self, pois: List[Poi], fallback_used: bool, source_used: str) -> None:
        self.pois = pois
        self.fallback_used = fallback_used
        self.source_used = source_used


async def load_pois_with_status(
    source: str,
    lat: float,
    lng: float,
    radius_m: int = 1500,
    offline: bool = False,
    curated: Optional[CuratedPoiSource] = None,
    overpass: Optional[OverpassPoiSource] = None,
) -> PoiLoadStatus:
    if source == "curated" or offline:
        return PoiLoadStatus((curated or CuratedPoiSource()).load(), False, "curated")
    try:
        pois = await (overpass or OverpassPoiSource()).fetch(lat, lng, radius_m)
        return PoiLoadStatus(pois, False, "overpass")
    except POISourceError:
        logger.warning("overpass failed, fallback to curated fixtures")
        return PoiLoadStatus((curated or CuratedPoiSource()).load(), True, "curated")
