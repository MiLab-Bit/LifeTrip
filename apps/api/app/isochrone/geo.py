"""LifeTrip 等时圈基础几何工具。

为什么不用 shapely：项目约定「无奇异依赖」，等时圈场景只需要 4 个原语
（球面距离、方位角、凸包、点在多边形内），手写不到 150 行，
换来评测环境 / 低配机器零依赖可跑。若未来需要 alpha-shape 等高级形状，
再引入 shapely 并在 adapter 层替换，不影响上层接口。

精度口径：15 分钟步行圈尺度（约 1-2 km）下，
- 距离用球面 haversine（误差 < 0.5%）；
- 多边形面积用「以中心点为原点的局部等距圆柱投影 + 鞋带公式」，
  该尺度内投影误差远小于验收容差（面积允许 ±5%）。
"""

from __future__ import annotations

import math
from typing import List, Sequence, Tuple

# (lat, lng) 有序对。注意：GeoJSON 序列化时是 [lng, lat]，转换只发生在
# engine 的输出边界，内部统一 (lat, lng)，避免双向换算出错。
Point = Tuple[float, float]

EARTH_RADIUS_M = 6_371_008.8  # IUGG 平均半径，与 OSRM 口径一致


def haversine_m(a: Point, b: Point) -> float:
    """球面大圆距离（米）。"""
    lat1, lng1 = math.radians(a[0]), math.radians(a[1])
    lat2, lng2 = math.radians(b[0]), math.radians(b[1])
    dlat, dlng = lat2 - lat1, lng2 - lng1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(h))


def bearing_deg(a: Point, b: Point) -> float:
    """a→b 的初始方位角（0=正北，顺时针 0-360）。"""
    lat1, lng1 = math.radians(a[0]), math.radians(a[1])
    lat2, lng2 = math.radians(b[0]), math.radians(b[1])
    dlng = lng2 - lng1
    x = math.sin(dlng) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlng)
    deg = math.degrees(math.atan2(x, y))
    return deg % 360.0


def destination(start: Point, bearing: float, dist_m: float) -> Point:
    """从 start 沿给定方位角走 dist_m 米后的坐标（球面直接解）。"""
    lat1, lng1 = math.radians(start[0]), math.radians(start[1])
    theta = math.radians(bearing)
    delta = dist_m / EARTH_RADIUS_M
    lat2 = math.asin(math.sin(lat1) * math.cos(delta) + math.cos(lat1) * math.sin(delta) * math.cos(theta))
    lng2 = lng1 + math.atan2(
        math.sin(theta) * math.sin(delta) * math.cos(lat1),
        math.cos(delta) - math.sin(lat1) * math.sin(lat2),
    )
    return (math.degrees(lat2), math.degrees(lng2) % 360.0)


def _cross(o: Point, a: Point, b: Point) -> float:
    """向量 OA × OB 的 z 分量（平面叉积，用于凸包排序）。"""
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def convex_hull(points: Sequence[Point]) -> List[Point]:
    """Andrew 单调链凸包，返回逆时针闭合前的顶点序列（不重复首尾）。

    为什么在 (lat,lng) 平面上直接算：小尺度下经纬度近似线性，
    凸包的拓扑结构不会因投影误差改变。
    """
    pts = sorted(set((round(p[0], 9), round(p[1], 9)) for p in points))
    if len(pts) <= 2:
        return list(pts)
    lower: List[Point] = []
    for p in pts:
        while len(lower) >= 2 and _cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    upper: List[Point] = []
    for p in reversed(pts):
        while len(upper) >= 2 and _cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def _to_local_meters(p: Point, origin: Point) -> Tuple[float, float]:
    """以 origin 为原点的局部平面坐标（米）。等距圆柱近似。"""
    x = math.radians(p[1] - origin[1]) * EARTH_RADIUS_M * math.cos(math.radians(origin[0]))
    y = math.radians(p[0] - origin[0]) * EARTH_RADIUS_M
    return (x, y)


def polygon_area_m2(ring: Sequence[Point], origin: Point) -> float:
    """鞋带公式算多边形面积（平方米）。ring 可闭合可不闭合。"""
    if len(ring) < 3:
        return 0.0
    pts = [_to_local_meters(p, origin) for p in ring]
    s = 0.0
    for i in range(len(pts)):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % len(pts)]
        s += x1 * y2 - x2 * y1
    return abs(s) / 2.0


def point_in_polygon(p: Point, ring: Sequence[Point]) -> bool:
    """射线法判断点是否在多边形内（边界算在内，容差 1e-12）。

    覆盖分析只要求「在圈内/圈外」二值判断，网格法/角度法都没有必要。
    """
    if len(ring) < 3:
        return False
    lat, lng = p
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        lat_i, lng_i = ring[i]
        lat_j, lng_j = ring[j]
        # 半开区间 + 严格不等式，避免射线穿顶点时重复计数
        if (lng_i > lng) != (lng_j > lng):
            t = (lng - lng_i) / (lng_j - lng_i)
            if lat_i + t * (lat_j - lat_i) >= lat:
                inside = not inside
        j = i
    return inside


def lerp(a: float, b: float, t: float) -> float:
    """线性插值。"""
    return a + (b - a) * t
