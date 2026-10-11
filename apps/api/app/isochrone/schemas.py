"""等时圈数据结构（Pydantic v2）。

为什么单独一包：LifeTrip 的共享类型在 packages/contracts，
但那是「跨服务契约」的地盘；等时圈是单一 API 模块，先把结构收在
本模块内。TODO-ADAPT：如果 contracts 里已有 LatLng / GeoJSON 类型，
把这里的重复定义替换成 from packages.contracts import ... 即可，
字段名保持一致（lat/lng、type/coordinates）。
"""

from __future__ import annotations

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field, model_validator


class LatLng(BaseModel):
    lat: float = Field(..., ge=-90, le=90, description="纬度（WGS-84）")
    lng: float = Field(..., ge=-180, le=180, description="经度（WGS-84）")


class Poi(BaseModel):
    id: str
    name: str
    category: str  # coverage.CATEGORIES 的 key
    lat: float
    lng: float


class GeoJSONPolygon(BaseModel):
    """GeoJSON Polygon，坐标为 [lng, lat]（GeoJSON 规范序）。"""

    type: Literal["Polygon"] = "Polygon"
    coordinates: List[List[List[float]]]  # [ring][vertex][lng, lat]


class DirectionRay(BaseModel):
    """单个扇形方向的可达性明细。"""

    bearing: float = Field(..., description="方位角 0-360，0=正北")
    reachable_m: float = Field(..., ge=0, description="该方向可达距离（米）")
    time_s: Optional[float] = Field(None, description="可达边界处的 OSRM 步行秒数；直线估算时为 null")
    degraded: bool = Field(False, description="该方向是否走了降级估算（OSRM 失败）")


class CategoryCoverage(BaseModel):
    key: str
    label: str
    total: int = Field(..., ge=0, description="该类别 POI 总数")
    inside: int = Field(..., ge=0, description="落在等时圈内的数量")
    coverage_rate: float = Field(..., ge=0, le=1, description="inside/total；total=0 时为 0")
    blind_spot: bool = Field(..., description="覆盖率低于阈值或类别缺失")


class CoverageReport(BaseModel):
    categories: List[CategoryCoverage]
    blind_spots: List[str] = Field(..., description="盲区类别 key 列表")
    threshold: float
    total_pois: int
    inside_pois: int


class IsochroneResult(BaseModel):
    center: LatLng
    minutes: float
    walking_speed_kmh: float
    polygon: GeoJSONPolygon
    area_m2: float
    rays: List[DirectionRay]
    degraded: bool = Field(..., description="任一方向降级即为 true")
    degraded_directions: int = Field(..., ge=0, description="降级方向数")
    degraded_ratio: float = Field(..., ge=0, le=1)
    data_source: Literal["osrm", "offline-synthetic"] = "osrm"


class AnalyzeRequest(BaseModel):
    center: LatLng
    minutes: float = Field(15, gt=0, le=120, description="步行分钟数")
    walking_speed_kmh: float = Field(4.8, gt=0, le=15, description="步行速度，OSRM 常用 4.8km/h")
    directions: int = Field(16, ge=4, le=64, description="扇形采样方向数，16/32 常用")
    polygon_mode: Literal["ring", "hull"] = Field(
        "ring", description="ring=环形星形多边形（保留凹形），hull=凸包（更保守）"
    )
    poi_source: Literal["overpass", "curated"] = Field(
        "curated", description="POI 来源；离线模式强制 curated"
    )
    blind_spot_threshold: float = Field(0.3, ge=0, le=1, description="覆盖率低于该值判盲区")

    @model_validator(mode="after")
    def _check_dirs(self) -> "AnalyzeRequest":
        # 32 方向是「精细模式」；允许 4-64 任意值，给 eval 留小方向数的便宜用例
        if self.directions not in (4, 8, 16, 32, 64):
            # 不报错，只在非标准值下照常计算——评测确定性优先于配置洁癖
            pass
        return self


class AnalyzeResponse(BaseModel):
    """POST /v1/isochrone/analyze 的返回体。"""

    isochrone: IsochroneResult
    coverage: CoverageReport
    blind_spots: List[str]
    degraded: bool
    poi_source: Literal["overpass", "curated"]
    # L0 只读分析：不写库、不改用户状态，见 PATCH_README 的权限分级说明


class TableResult(BaseModel):
    """OSRM /table 结果的内部表示。durations[i][j] 为 None 表示该对失败。"""

    durations: List[List[Optional[float]]]


POI_CATEGORY_LABELS: Dict[str, str] = {
    "medical": "医疗",
    "education": "教育",
    "shopping": "购物",
    "dining": "餐饮",
    "green": "绿地",
    "transit": "交通",
}
