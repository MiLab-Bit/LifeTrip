"""等时圈引擎全链路测试（本地 fixtures + OSRM mock，无网络依赖）。

覆盖面：
1. geo 原语（haversine/凸包/面积/点在多边形）
2. OSRM HTTP 传输：URL 组装、分批合并、5xx 重试、null duration、整批失败降级
3. 引擎：离线确定性、直线降级（传输整体异常）、ring/hull、步速参数
4. 覆盖分析：六类别覆盖率、盲区判定、类别缺失
5. API 路由：LIFETRIP_OFFLINE=1 走 fixtures，响应结构完整
6. eval 回归：content/eval/isochrone_cases.json 的 10 题期望值逐项断言

运行（仓库根）：
    pytest tests/test_isochrone.py -v
"""

from __future__ import annotations

import asyncio
import json
import math
import os
import sys

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(REPO, "apps", "api"))

from app.isochrone import (  # noqa: E402
    CuratedPoiSource,
    IsochroneEngine,
    OfflineOsrmTransport,
    analyze_coverage,
    geo,  # noqa: E402
    load_pois,
)
from app.isochrone.osrm import HttpOsrmTransport  # noqa: E402
from app.isochrone.schemas import LatLng, Poi  # noqa: E402

FIX_DIR = os.path.join(REPO, "content", "fixtures", "isochrone")
EVAL_PATH = os.path.join(REPO, "content", "eval", "isochrone_cases.json")

CENTER = LatLng(lat=31.2304, lng=121.4737)


def run(coro):
    """engine 是 async 的；不引 pytest-asyncio，统一 asyncio.run 驱动。"""
    return asyncio.run(coro)


# ---------------------------------------------------------------- geo 原语

class TestGeo:
    def test_haversine_known_distance(self):
        # 上海人民广场 → 东方明珠 直线约 2.7km（量级校验，容差 8%）
        d = geo.haversine_m((31.2304, 121.4737), (31.2397, 121.4998))
        assert 2500 < d < 2900, d

    def test_destination_roundtrip(self):
        # 走 800 米再算距离，应回读出 ~800 米（球面直接解自洽）
        p = geo.destination((31.2304, 121.4737), 63.0, 800)
        assert abs(geo.haversine_m((31.2304, 121.4737), p) - 800) < 1.0

    def test_bearing_wraps(self):
        assert abs(geo.bearing_deg((31.0, 121.0), (32.0, 121.0))) < 1e-6   # 正北
        # 同纬度向东：球面大圆初始方位角略小于 90°（收敛经线效应）
        be = geo.bearing_deg((31.0, 121.0), (31.0, 122.0))
        assert 89 < be < 90.5, be
        b = geo.bearing_deg((31.0, 121.0), (30.5, 120.5))
        assert 180 < b < 270  # 西南象限

    def test_convex_hull_drops_inner_points(self):
        square = [(0, 0), (0, 1), (1, 1), (1, 0)]
        with_inner = square + [(0.5, 0.5), (0.2, 0.3)]
        hull = geo.convex_hull(with_inner)
        assert len(hull) == 4
        assert set(hull) == set(square)

    def test_polygon_area_square(self):
        # 0.01° 经度在 31°N 约 952m，纬度 0.01° 约 1111m；用投影后面积校验量级
        ring = [(31.0, 121.0), (31.0, 121.01), (31.01, 121.01), (31.01, 121.0)]
        area = geo.polygon_area_m2(ring, (31.0, 121.0))
        expected = 1111.9 * 952.1
        assert abs(area - expected) / expected < 0.02, (area, expected)

    def test_point_in_polygon(self):
        ring = [(31.0, 121.0), (31.0, 121.02), (31.02, 121.02), (31.02, 121.0)]
        assert geo.point_in_polygon((31.01, 121.01), ring)
        assert not geo.point_in_polygon((31.05, 121.01), ring)
        assert not geo.point_in_polygon((30.99, 121.01), ring)


# ---------------------------------------------------- OSRM HTTP 传输（mock）

class _RecordingHandler:
    """记录请求并返回合成 OSRM table 响应；可注入 5xx 次数与 null 单元。"""

    def __init__(self, fail_first=0, null_positions=None, per_batch_fail=False):
        self.requests: list[httpx.Request] = []
        self.fail_first = fail_first
        self.null_positions = null_positions or set()
        self.per_batch_fail = per_batch_fail
        self.served = 0

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        self.served += 1
        if self.served <= self.fail_first:
            return httpx.Response(500, text="boom")
        # 解析 URL 里的坐标串：/table/v1/foot/lng,lat;lng,lat...?sources=0&destinations=...
        dest_idx = [int(x) for x in request.url.params["destinations"].split(";")]
        n_dst = len(dest_idx)
        # 合成模型：时间 = 索引距离基准（保持与坐标顺序无关的确定性即可测分批合并）
        durations: list = []
        for _ in range(1):  # sources=0 → 单行
            row = []
            for j in range(n_dst):
                if (self.served, j) in self.null_positions:
                    row.append(None)
                else:
                    row.append(300.0 + 50.0 * j)
            durations.append(row)
        if self.per_batch_fail and self.served >= 2:
            # 第二批起永久 500：验证「单批失败 → None 行 → 引擎降级」路径
            return httpx.Response(500, text="permanent fail")
        return httpx.Response(200, json={"code": "Ok", "durations": durations})


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


class TestHttpOsrmTransport:
    def test_url_shape_and_single_batch(self):
        h = _RecordingHandler()
        t = HttpOsrmTransport(base_url="http://osrm.test", client=_client(h), batch_size=64)
        res = run(t.table([(31.0, 121.0)], [(31.001, 121.001), (31.002, 121.002)]))
        url = h.requests[0].url
        assert "/table/v1/foot/" in url.path
        # 坐标序是 lng,lat（GeoJSON/OSRM 规范）
        assert "121.000000,31.000000" in url.path
        assert url.params["sources"] == "0"
        assert url.params["destinations"] == "1;2"
        assert res.durations[0] == [300.0, 350.0]

    def test_batch_split_and_merge(self):
        # 5 个目的地、batch_size=2 → 3 批；时间应按「批内序号」连续拼接
        h = _RecordingHandler()
        t = HttpOsrmTransport(base_url="http://osrm.test", client=_client(h), batch_size=2)
        dests = [(31.001 * (i + 1) / 10, 121.0) for i in range(5)]
        res = run(t.table([(31.0, 121.0)], dests))
        assert len(h.requests) == 3
        # 每批 j 从 0 重新计数：0,50 / 0,50 / 0 —— 验证合并保序
        assert res.durations[0] == [300.0, 350.0, 300.0, 350.0, 300.0]

    def test_retry_on_500_then_success(self):
        h = _RecordingHandler(fail_first=2)
        t = HttpOsrmTransport(
            base_url="http://osrm.test", client=_client(h), retries=3, backoff=0.0
        )
        res = run(t.table([(31.0, 121.0)], [(31.001, 121.001)]))
        assert len(h.requests) == 3  # 失败 2 次 + 成功 1 次
        assert res.durations[0][0] == 300.0

    def test_retry_exhausted_degrades_to_none(self):
        h = _RecordingHandler(fail_first=99)
        t = HttpOsrmTransport(
            base_url="http://osrm.test", client=_client(h), retries=1, backoff=0.0
        )
        res = run(t.table([(31.0, 121.0)], [(31.001, 121.001), (31.002, 121.002)]))
        assert res.durations[0] == [None, None]  # 引擎按 None 降级

    def test_partial_batch_failure_fills_none_rows(self):
        # 第一批成功、后续批永久失败：成功批的数据保留，失败批为 None
        h = _RecordingHandler(per_batch_fail=True)
        t = HttpOsrmTransport(
            base_url="http://osrm.test", client=_client(h), batch_size=2, retries=1, backoff=0.0
        )
        dests = [(31.001 * (i + 1) / 10, 121.0) for i in range(5)]
        res = run(t.table([(31.0, 121.0)], dests))
        assert res.durations[0][:2] == [300.0, 350.0]
        assert res.durations[0][2:] == [None, None, None]

    def test_null_duration_passthrough(self):
        h = _RecordingHandler(null_positions={(1, 1)})
        t = HttpOsrmTransport(base_url="http://osrm.test", client=_client(h))
        res = run(t.table([(31.0, 121.0)], [(31.001, 121.001), (31.002, 121.002)]))
        assert res.durations[0] == [300.0, None]


# ---------------------------------------------------------------- 引擎

class _StaticTransport:
    """完全可控的桩传输：直接给定 durations 行，或抛异常。"""

    def __init__(self, durations=None, raise_exc=None):
        self.durations = durations
        self.raise_exc = raise_exc

    async def table(self, sources, destinations):
        if self.raise_exc:
            raise self.raise_exc
        return type("R", (), {"durations": [self.durations]})()


class TestEngine:
    def _offline_engine(self, speed_kmh=None) -> IsochroneEngine:
        t = OfflineOsrmTransport(os.path.join(FIX_DIR, "osrm_table.json"), speed_kmh=speed_kmh)
        return IsochroneEngine(transport=t)

    def test_offline_baseline_shape(self):
        res = run(self._offline_engine().compute(CENTER, 15))
        ring = res.polygon.coordinates[0]
        # 闭合环 + 16 方向 × (1 实点 + 1 插值点) = 33 顶点
        assert len(ring) == 33
        assert ring[0] == ring[-1]
        assert not res.degraded
        # 东北阻隔扇区（bearing 45°）可达距离应显著小于普通方向（315°）
        r_ne = next(r for r in res.rays if abs(r.bearing - 45) < 1)
        r_sw = next(r for r in res.rays if abs(r.bearing - 315) < 1)
        assert r_ne.reachable_m < r_sw.reachable_m * 0.75

    def test_transport_exception_full_degradation(self):
        # 传输层整体抛异常 → 全部方向直线降级，结果仍可解释
        engine = IsochroneEngine(transport=_StaticTransport(raise_exc=httpx.ConnectError("down")))
        res = run(engine.compute(CENTER, 15, walking_speed_kmh=4.8))
        assert res.degraded and res.degraded_directions == 16
        budget_m = 15 * 60 * (4.8 / 3.6)  # 900s × 1.333m/s = 1200m
        for r in res.rays:
            assert r.time_s is None
            assert abs(r.reachable_m - budget_m) < 1e-6

    def test_partial_null_marks_degraded_but_computes(self):
        # 6 个采样点里 2 个 None：方向仍给出插值结果，但标 degraded
        # 16 方向 × 6 采样 = 96 个候选点；每方向塞进 2 个 None
        per_ray = [600.0, None, 700.0, 800.0, None, 900.0]
        times = per_ray * 16
        engine = IsochroneEngine(transport=_StaticTransport(durations=times))
        res = run(engine.compute(CENTER, 15))
        assert res.degraded
        assert res.degraded_directions == 16
        # 部分失败但仍有有效采样：给出插值时间而非直线降级
        assert all(r.time_s is not None for r in res.rays)
        assert all(r.reachable_m > 0 for r in res.rays)

    def test_hull_mode_area_geq_ring(self):
        ring_res = run(self._offline_engine().compute(CENTER, 15, polygon_mode="ring"))
        hull_res = run(self._offline_engine().compute(CENTER, 15, polygon_mode="hull"))
        assert hull_res.area_m2 >= ring_res.area_m2
        # 凸包顶点数 ≤ 方向数（16）
        assert len(hull_res.polygon.coordinates[0]) - 1 <= 16

    def test_walking_speed_scales_offline_result(self):
        base = run(self._offline_engine().compute(CENTER, 15))
        fast = run(self._offline_engine(speed_kmh=6.0).compute(CENTER, 15, walking_speed_kmh=6.0))
        assert fast.area_m2 > base.area_m2 * 1.3

    def test_minutes_monotonic_area(self):
        e = self._offline_engine()
        a10 = run(e.compute(CENTER, 10)).area_m2
        a15 = run(e.compute(CENTER, 15)).area_m2
        a25 = run(e.compute(CENTER, 25)).area_m2
        assert a10 < a15 < a25

    def test_area_close_to_sector_model(self):
        # 解析校验：按绕行系数算各扇区可达半径 → 扇形面积和，多边形面积应在 ±12%
        res = run(self._offline_engine().compute(CENTER, 15, directions=32))
        budget_s, speed = 900.0, 4.8 / 3.6
        straight = budget_s * speed
        def factor(b):
            if 20 <= b <= 110:
                return 1.9
            if 200 <= b <= 260:
                return 1.5
            return 1.15
        analytic = sum(
            (360 / 32) / 360 * math.pi * (straight / factor(360 * i / 32)) ** 2
            for i in range(32)
        )
        rel = abs(res.area_m2 - analytic) / analytic
        assert rel < 0.12, (res.area_m2, analytic, rel)


# ---------------------------------------------------------------- 覆盖分析

class TestCoverage:
    def _pois(self) -> list[Poi]:
        return CuratedPoiSource(os.path.join(FIX_DIR, "pois.json")).load()

    def test_six_categories_present(self):
        report = analyze_coverage(_square_polygon(), self._pois(), threshold=0.3)
        keys = [c.key for c in report.categories]
        assert keys == ["medical", "education", "shopping", "dining", "green", "transit"]

    def test_coverage_counts_and_blind_spot_logic(self):
        res = run(IsochroneEngine(transport=OfflineOsrmTransport(
            os.path.join(FIX_DIR, "osrm_table.json"))).compute(CENTER, 15))
        report = analyze_coverage(res.polygon, self._pois(), threshold=0.3)
        for c in report.categories:
            assert c.inside <= c.total
            if c.total > 0:
                assert abs(c.coverage_rate - c.inside / c.total) < 1e-9
            else:
                assert c.blind_spot
            assert c.blind_spot == (c.total == 0 or c.coverage_rate < 0.3)
        assert set(report.blind_spots) == {c.key for c in report.categories if c.blind_spot}

    def test_threshold_changes_blind_spots(self):
        res = run(IsochroneEngine(transport=OfflineOsrmTransport(
            os.path.join(FIX_DIR, "osrm_table.json"))).compute(CENTER, 15))
        strict = analyze_coverage(res.polygon, self._pois(), threshold=0.9)
        loose = analyze_coverage(res.polygon, self._pois(), threshold=0.0)
        assert len(strict.blind_spots) >= len(loose.blind_spots)
        # 阈值 0 时盲区只剩「类别缺失」——curated 集六类都有，应为空
        assert loose.blind_spots == []


def _square_polygon():
    from app.isochrone.schemas import GeoJSONPolygon
    # 大正方形把全部 POI 装进去 → 覆盖率全 1
    return GeoJSONPolygon(
        type="Polygon",
        coordinates=[[[121.44, 31.215], [121.44, 31.245], [121.50, 31.245],
                       [121.50, 31.215], [121.44, 31.215]]],
    )


# ---------------------------------------------------------------- POI 源

class TestPoiSources:
    def test_curated_load(self):
        pois = run(load_pois("curated", 31.23, 121.47))
        assert len(pois) >= 30
        cats = {p.category for p in pois}
        assert cats == {"medical", "education", "shopping", "dining", "green", "transit"}

    def test_offline_forces_curated(self):
        # 离线模式即使请求 overpass 也强制 curated（确定性优先）
        pois = run(load_pois("overpass", 31.23, 121.47, offline=True))
        assert pois and pois[0].id.startswith("curated-")


# ---------------------------------------------------------------- API 路由

class TestApiRoute:
    def _app(self) -> FastAPI:
        from app.api.v1.isochrone import router
        app = FastAPI()
        app.include_router(router, prefix="/v1")
        return app

    def test_analyze_offline_full_response(self, monkeypatch):
        monkeypatch.setenv("LIFETRIP_OFFLINE", "1")
        monkeypatch.setenv("LIFETRIP_FIXTURES_DIR", os.path.join(REPO, "content", "fixtures"))
        client = TestClient(self._app())
        resp = client.post("/v1/isochrone/analyze", json={
            "center": {"lat": 31.2304, "lng": 121.4737},
            "minutes": 15,
            "directions": 16,
        })
        assert resp.status_code == 200, resp.text
        body = resp.json()
        iso = body["isochrone"]
        assert iso["data_source"] == "offline-synthetic"
        assert iso["polygon"]["type"] == "Polygon"
        assert len(iso["polygon"]["coordinates"][0]) >= 8
        assert iso["area_m2"] > 100_000
        assert isinstance(iso["rays"], list) and len(iso["rays"]) == 16
        cov = body["coverage"]
        assert len(cov["categories"]) == 6
        assert set(body["blind_spots"]) == set(cov["blind_spots"])
        assert body["poi_source"] == "curated"
        assert body["degraded"] is False

    def test_analyze_validation_error(self, monkeypatch):
        monkeypatch.setenv("LIFETRIP_OFFLINE", "1")
        monkeypatch.setenv("LIFETRIP_FIXTURES_DIR", os.path.join(REPO, "content", "fixtures"))
        client = TestClient(self._app())
        # 纬度越界 / minutes 为负 → 422
        assert client.post("/v1/isochrone/analyze", json={
            "center": {"lat": 999, "lng": 0}, "minutes": 15}).status_code == 422
        assert client.post("/v1/isochrone/analyze", json={
            "center": {"lat": 31.0, "lng": 121.0}, "minutes": -1}).status_code == 422


# ---------------------------------------------------------------- eval 回归

class TestEvalRegression:
    """10 题回归：用离线管线重算，与 content/eval/isochrone_cases.json 的
    期望值逐项断言。期望值由 tests/generate_eval_fixtures.py 生成。"""

    def test_all_ten_cases_match_expectations(self):
        with open(EVAL_PATH, "r", encoding="utf-8") as f:
            doc = json.load(f)
        cases = doc["cases"]
        assert len(cases) == 10
        pois = CuratedPoiSource(os.path.join(FIX_DIR, "pois.json")).load()

        for case in cases:
            req = case["request"]
            expect = case["expect"]
            transport = OfflineOsrmTransport(
                os.path.join(FIX_DIR, "osrm_table.json"),
                speed_kmh=req.get("walking_speed_kmh"),
            )
            res = run(IsochroneEngine(transport=transport).compute(
                LatLng(**req["center"]),
                minutes=req.get("minutes", 15),
                walking_speed_kmh=req.get("walking_speed_kmh", 4.8),
                directions=req.get("directions", 16),
                polygon_mode=req.get("polygon_mode", "ring"),
                data_source="offline-synthetic",
            ))
            report = analyze_coverage(res.polygon, pois, threshold=req.get("blind_spot_threshold", 0.3))

            # 面积：容差 2%（浮点平台差异余量；本体是确定性的）
            assert abs(res.area_m2 - expect["area_m2"]) / expect["area_m2"] < 0.02, (
                case["id"], res.area_m2, expect["area_m2"])
            assert len(res.polygon.coordinates[0]) - 1 == expect["vertex_count"], case["id"]
            # 覆盖率：允许 1e-6 舍入差
            for c in report.categories:
                exp = expect["coverage"][c.key]
                assert c.total == exp["total"], (case["id"], c.key)
                assert c.inside == exp["inside"], (case["id"], c.key)
                assert abs(c.coverage_rate - exp["coverage_rate"]) < 1e-6, (case["id"], c.key)
            assert sorted(report.blind_spots) == sorted(expect["blind_spots"]), case["id"]

    def test_direction_count_and_hull_relationships(self):
        """题间的结构性关系（面积单调性、凸包≥环形）也是回归保护点。"""
        with open(EVAL_PATH, "r", encoding="utf-8") as f:
            doc = json.load(f)
        by_id = {c["id"]: c for c in doc["cases"]}
        # 10 分钟 < 15 分钟 < 25 分钟
        assert by_id["iso-004"]["expect"]["area_m2"] < by_id["iso-001"]["expect"]["area_m2"]
        assert by_id["iso-001"]["expect"]["area_m2"] < by_id["iso-005"]["expect"]["area_m2"]
        # 凸包 ≥ 环形
        assert by_id["iso-003"]["expect"]["area_m2"] >= by_id["iso-001"]["expect"]["area_m2"]
        # 32 方向比 16 方向面积大（弦近似误差减小）
        assert by_id["iso-002"]["expect"]["area_m2"] > by_id["iso-001"]["expect"]["area_m2"]
        # 5 分钟小圈盲区最多
        assert len(by_id["iso-010"]["expect"]["blind_spots"]) >= len(
            by_id["iso-004"]["expect"]["blind_spots"])
