"""LifeTrip 等时圈包：15 分钟生活圈智能体检的引擎与覆盖分析。

对外入口：
- IsochroneEngine        扇形采样 + OSRM 批量算路 + 插值成 GeoJSON 多边形
- analyze_coverage       等时圈 × POI → 分类覆盖率与盲区
- 路由层见 apps/api/app/api/v1/isochrone.py（POST /v1/isochrone/analyze）
"""

from .coverage import CATEGORIES, analyze_coverage
from .engine import IsochroneEngine
from .osrm import HttpOsrmTransport, OfflineOsrmTransport
from .pois import CuratedPoiSource, OverpassPoiSource, load_pois, load_pois_with_status
from .schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    CategoryCoverage,
    CoverageReport,
    DirectionRay,
    GeoJSONPolygon,
    IsochroneResult,
    LatLng,
    Poi,
)

__all__ = [
    "CATEGORIES",
    "IsochroneEngine",
    "HttpOsrmTransport",
    "OfflineOsrmTransport",
    "CuratedPoiSource",
    "OverpassPoiSource",
    "load_pois",
    "load_pois_with_status",
    "analyze_coverage",
    "AnalyzeRequest",
    "AnalyzeResponse",
    "CategoryCoverage",
    "CoverageReport",
    "DirectionRay",
    "GeoJSONPolygon",
    "IsochroneResult",
    "LatLng",
    "Poi",
]
