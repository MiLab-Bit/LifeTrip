"""等时圈引擎：扇形采样 → OSRM /table 批量算路 → 环形/凸包插值成多边形。

算法（为什么这么做）：
1. 扇形采样：把 360° 均分为 N 个方向，每方向在半径上取 M 个候选点
   （距离按比例分布）。真实步行时间不是直线距离能算的（过河、断头路），
   所以候选点的「直线距离 → 实际时间」映射必须交给路网（OSRM）。
2. 一次 /table 批量取回所有候选点的真实步行时间（见 osrm.py 的分批并发）。
3. 每方向在「距离-时间」序列上找预算时间（minutes*60 秒）的穿越点，
   线性插值出精确可达距离。凹形路网（如前方是江）会让某几个方向
   可达距离骤减，这正是环形多边形（ring 模式）能表达、凸包会抹平的形态。
4. 降级：OSRM 某方向全部候选点失败时，退回直线距离 = 预算时间 × 步速，
   并在结果里标注 degraded —— 宁可给一个保守但可解释的圈，也不报错。

输出：GeoJSON Polygon + 每方向可达明细 + degraded 标记，供
coverage.py / 前端 / eval 消费。
"""

from __future__ import annotations

import asyncio
from typing import List, Optional, Sequence, Tuple

from . import geo
from .osrm import OsrmTransport
from .schemas import DirectionRay, GeoJSONPolygon, IsochroneResult, LatLng

Point = Tuple[float, float]

# 每条射线上候选距离占最大半径的比例。
# 为什么不是均匀分布：可达边界大概率落在 0.5-1.0 区间（绕行系数 1~2），
# 中后段加密、起点保留一个近点做零点校准，插值误差最小。
RAY_FRACTIONS = (0.25, 0.45, 0.6, 0.75, 0.9, 1.0)

# 最大半径外扩系数：真实步行可达距离 ≤ 直线最大距离 × 绕行系数上限。
# 2.0 覆盖了绝大多数城市路网（曼哈顿格网 1.41，绕河可达 1.8+）。
MAX_RADIUS_FACTOR = 2.0


class IsochroneEngine:
    def __init__(
        self,
        transport: OsrmTransport,
        ray_fractions: Sequence[float] = RAY_FRACTIONS,
        max_radius_factor: float = MAX_RADIUS_FACTOR,
    ) -> None:
        self.transport = transport
        self.ray_fractions = tuple(ray_fractions)
        self.max_radius_factor = max_radius_factor

    async def compute(
        self,
        center: LatLng,
        minutes: float,
        walking_speed_kmh: float = 4.8,
        directions: int = 16,
        polygon_mode: str = "ring",
        data_source: str = "osrm",
    ) -> IsochroneResult:
        budget_s = minutes * 60.0
        speed_mps = walking_speed_kmh / 3.6
        # 直线最大距离：预算时间 × 步速（路网绕行只会更短，外扩系数给采样余量）
        straight_max_m = budget_s * speed_mps
        max_radius_m = straight_max_m * self.max_radius_factor

        bearings = [360.0 * i / directions for i in range(directions)]
        # 展平全部候选点：一次 table 请求批量取时间
        cand_points: List[Point] = []
        for b in bearings:
            for frac in self.ray_fractions:
                cand_points.append(geo.destination((center.lat, center.lng), b, max_radius_m * frac))

        try:
            result = await self.transport.table([(center.lat, center.lng)], cand_points)
            times: List[Optional[float]] = list(result.durations[0]) if result.durations and result.durations[0] else [None] * len(cand_points)
        except Exception:  # 传输层整体失败：全部方向走直线降级
            times = [None] * len(cand_points)

        rays: List[DirectionRay] = []
        m = len(self.ray_fractions)
        for di, b in enumerate(bearings):
            ray_times = times[di * m : (di + 1) * m]
            ray, _ = self._ray_from_times(
                b, ray_times, max_radius_m, budget_s, speed_mps
            )
            rays.append(ray)

        polygon, area = self._build_polygon((center.lat, center.lng), rays, polygon_mode)
        degraded_n = sum(1 for r in rays if r.degraded)
        return IsochroneResult(
            center=center,
            minutes=minutes,
            walking_speed_kmh=walking_speed_kmh,
            polygon=polygon,
            area_m2=area,
            rays=rays,
            degraded=degraded_n > 0,
            degraded_directions=degraded_n,
            degraded_ratio=degraded_n / max(1, len(rays)),
            data_source=data_source,  # type: ignore[arg-type]
        )

    def _ray_from_times(
        self,
        bearing: float,
        ray_times: Sequence[Optional[float]],
        max_radius_m: float,
        budget_s: float,
        speed_mps: float,
    ) -> Tuple[DirectionRay, float]:
        """单方向可达距离：线性插值穿越预算时间。返回 (ray, 可达米数)。"""
        dists = [max_radius_m * f for f in self.ray_fractions]
        valid = [(d, t) for d, t in zip(dists, ray_times) if t is not None and t > 0]
        if not valid:
            # 全方向失败 → 直线降级：距离=预算×步速，time 置空并标 degraded
            d = budget_s * speed_mps
            return DirectionRay(bearing=bearing, reachable_m=d, time_s=None, degraded=True), d

        # 找最后一个可达采样点 + 第一个不可达采样点，之间线性插值
        reachable = [(d, t) for d, t in valid if t <= budget_s]
        if not reachable:
            # 最近的采样点都超预算：从中心(0,0)到第一个采样点插值
            d0, t0 = valid[0]
            d = d0 * budget_s / t0
            degraded = len(valid) < len(dists)
            return (
                DirectionRay(bearing=bearing, reachable_m=d, time_s=budget_s, degraded=degraded),
                d,
            )
        d_last, t_last = reachable[-1]
        # 下一采样点（无论 None 与否）取有效值里第一个超过 d_last 的
        nxt = next(((d, t) for d, t in valid if d > d_last), None)
        if nxt is None:
            # 所有有效点都可达：取最大有效距离，标注是否因缺失采样而不确定
            d = d_last
            t = t_last
        else:
            d_next, t_next = nxt
            # 分母可能为 0（相邻采样时间相同）：退化为取近端
            if t_next > t_last:
                d = d_last + (budget_s - t_last) * (d_next - d_last) / (t_next - t_last)
            else:
                d = d_last
            t = budget_s
        degraded = len(valid) < len(dists)
        return DirectionRay(bearing=bearing, reachable_m=min(d, max_radius_m), time_s=t, degraded=degraded), d

    def _build_polygon(
        self, center: Point, rays: Sequence[DirectionRay], mode: str
    ) -> Tuple[GeoJSONPolygon, float]:
        """ring：星形环（保凹形）；hull：凸包（保守、必凸）。"""
        if mode == "hull":
            pts = [geo.destination(center, r.bearing, r.reachable_m) for r in rays]
            hull = geo.convex_hull(pts)
            ring = hull
        else:
            # 环形插值：相邻方向之间插入中点方位（距离取均值），
            # 让 16 方向也能画出光滑边界；凹形（某方向距离骤减）被保留
            pts: List[Point] = []
            n = len(rays)
            for i in range(n):
                r = rays[i]
                pts.append(geo.destination(center, r.bearing, r.reachable_m))
                r_next = rays[(i + 1) % n]
                mid_b = (r.bearing + r_next.bearing) / 2.0
                mid_d = (r.reachable_m + r_next.reachable_m) / 2.0
                pts.append(geo.destination(center, mid_b, mid_d))
            ring = pts
        # GeoJSON 坐标序 [lng, lat]，并闭合环
        coords = [[round(p[1], 7), round(p[0], 7)] for p in ring]
        if coords and coords[0] != coords[-1]:
            coords.append(coords[0])
        area = geo.polygon_area_m2(ring, center)
        return GeoJSONPolygon(type="Polygon", coordinates=[coords]), area
