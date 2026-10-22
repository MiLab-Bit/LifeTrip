"""设施覆盖分析：等时圈多边形 × POI 列表 → 体检报告。

口径定义（为什么这样定，写进报告口径避免评审争议）：
- 覆盖率 coverage_rate = 该类别落在等时圈内的 POI 数 / 该类别 POI 总数。
  分母是「这个中心点周边检索到的全部同类设施」，分子是「15 分钟步行
  真能走到的」。它回答的问题是：这个居住点对某类服务的可达比例。
- 盲区 blind_spot = coverage_rate < threshold（默认 0.3）或该类别
  POI 总数为 0（周边根本没有这类设施，是最硬的盲区）。
"""

from __future__ import annotations

from typing import Dict, List, Sequence

from . import geo
from .schemas import POI_CATEGORY_LABELS, CategoryCoverage, CoverageReport, GeoJSONPolygon, Poi

# 六大类别固定顺序输出，前端条形图按这个顺序渲染
CATEGORIES: Sequence[str] = ("medical", "education", "shopping", "dining", "green", "transit")

UNKNOWN_CATEGORY = "other"


def _ring_from_geojson(polygon: GeoJSONPolygon) -> List[geo.Point]:
    # GeoJSON 外环（第一环），坐标 [lng, lat] → 内部 (lat, lng)
    ring = [(v[1], v[0]) for v in polygon.coordinates[0]]
    if len(ring) > 1 and ring[0] == ring[-1]:
        ring = ring[:-1]
    return ring


def analyze_coverage(
    polygon: GeoJSONPolygon,
    pois: Sequence[Poi],
    threshold: float = 0.3,
) -> CoverageReport:
    ring = _ring_from_geojson(polygon)

    # 类别缺失也算盲区：curated/Overpass 检索范围内一个医疗点都没有，
    # 对「生活圈体检」来说比覆盖率 10% 更值得红点标注
    by_cat: Dict[str, List[bool]] = {k: [] for k in CATEGORIES}
    for poi in pois:
        key = poi.category if poi.category in by_cat else UNKNOWN_CATEGORY
        by_cat.setdefault(key, []).append(geo.point_in_polygon((poi.lat, poi.lng), ring))

    categories: List[CategoryCoverage] = []
    blind: List[str] = []
    for key in CATEGORIES:
        flags = by_cat.get(key, [])
        total = len(flags)
        inside = sum(1 for f in flags if f)
        rate = (inside / total) if total else 0.0
        is_blind = (total == 0) or (rate < threshold)
        if is_blind:
            blind.append(key)
        categories.append(
            CategoryCoverage(
                key=key,
                label=POI_CATEGORY_LABELS.get(key, key),
                total=total,
                inside=inside,
                coverage_rate=rate,
                blind_spot=is_blind,
            )
        )

    return CoverageReport(
        categories=categories,
        blind_spots=blind,
        threshold=threshold,
        total_pois=len(pois),
        inside_pois=sum(c.inside for c in categories),
    )
