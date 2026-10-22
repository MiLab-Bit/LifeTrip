#!/usr/bin/env python3
"""生成等时圈 eval fixtures 与期望值（确定性，可重跑校验）。

产出：
1. content/fixtures/isochrone/pois.json   curated POI 集（由下方布局表生成）
2. content/eval/isochrone_cases.json      10 题回归用例 + 期望输出

期望值不是手填的——是「离线管线实际跑出来的结果」序列化，
所以 eval 断言的语义是「任何人重跑管线都应得到完全相同的输出」
（回归保护，防算法改动悄悄漂移）。

用法（在仓库根）：
    python tests/generate_eval_fixtures.py
重跑后 git diff 为空 = 确定性成立。
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "api"))

import asyncio  # noqa: E402

from app.isochrone import (  # noqa: E402
    IsochroneEngine,
    OfflineOsrmTransport,
    analyze_coverage,
    geo,  # noqa: E402
)
from app.isochrone.schemas import LatLng  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
FIX_DIR = os.path.join(HERE, "..", "content", "fixtures", "isochrone")
EVAL_DIR = os.path.join(HERE, "..", "content", "eval")

CENTER = (31.2304, 121.4737)

# curated POI 布局表：(name, category, bearing, distance_m)
# 布局设计意图（对照 osrm_table.json 的绕行规则）：
# - 15min@4.8km/h：普通方向可达 ~1040m，东北(20-110°) ~630m，西南(200-260°) ~800m
# - dining/shopping：近程密布 → 高覆盖率
# - education/medical：医疗故意放远（东北阻隔方向 + 远距离）→ 典型盲区
# - green/transit：中距离混合，随 minutes 参数变化敏感（考察不同用例的区分度）
LAYOUT = [
    # 餐饮：近程 8 个，全部在圈内（15min）
    ("兰州拉面", "dining", 5, 250), ("便利店咖啡", "dining", 40, 300),
    ("沙县小吃", "dining", 75, 350), ("社区食堂", "dining", 120, 280),
    ("麻辣烫", "dining", 160, 400), ("面包房", "dining", 195, 450),
    ("火锅店", "dining", 240, 500), ("早点铺", "dining", 300, 350),
    ("江景餐厅", "dining", 65, 900), ("深夜食堂", "dining", 335, 1100),
    # 购物：中近程 7 个
    ("联华超市", "shopping", 10, 400), ("全家便利店", "shopping", 55, 520),
    ("菜市场", "shopping", 95, 600), ("百货商店", "shopping", 140, 700),
    ("社区生鲜", "shopping", 185, 550), ("购物中心", "shopping", 230, 950),
    ("杂货店", "shopping", 280, 800),
    # 医疗：故意稀缺且偏远 → 15min 基准下应为盲区
    ("社区卫生服务站", "medical", 350, 550), ("三甲医院", "medical", 60, 1400),
    ("药店", "medical", 15, 750),
    # 教育：混合距离
    ("实验小学", "education", 25, 500), ("幼儿园", "education", 80, 650),
    ("老年大学", "education", 130, 850), ("区图书馆", "education", 210, 1000),
    # 绿地：中远距离，minutes 变化时敏感
    ("街角公园", "green", 45, 700), ("滨江绿道", "green", 85, 1100),
    ("社区花园", "green", 150, 600), ("体育公园", "green", 245, 1300),
    ("植物园", "green", 320, 1600),
    # 交通：近远混合
    ("公交枢纽站", "transit", 0, 600), ("地铁站A口", "transit", 30, 800),
    ("地铁站B口", "transit", 190, 750), ("长途客运站", "transit", 100, 1500),
    ("共享单车点", "transit", 265, 400),
]

# 10 道回归题。request 字段即 POST /v1/isochrone/analyze 的请求体。
CASES = [
    {"id": "iso-001", "title": "基准：15 分钟 16 方向 ring",
     "request": {"center": {"lat": CENTER[0], "lng": CENTER[1]}, "minutes": 15}},
    {"id": "iso-002", "title": "方向加密到 32：弦长近似误差减小，面积应略增（与 16 方向差 <15%）",
     "request": {"center": {"lat": CENTER[0], "lng": CENTER[1]}, "minutes": 15, "directions": 32}},
    {"id": "iso-003", "title": "凸包模式：面积应不小于 ring 模式（凹形被抹平）",
     "request": {"center": {"lat": CENTER[0], "lng": CENTER[1]}, "minutes": 15, "polygon_mode": "hull"}},
    {"id": "iso-004", "title": "缩短到 10 分钟：面积缩小、盲区增多",
     "request": {"center": {"lat": CENTER[0], "lng": CENTER[1]}, "minutes": 10}},
    {"id": "iso-005", "title": "放宽到 25 分钟：面积扩大、盲区减少",
     "request": {"center": {"lat": CENTER[0], "lng": CENTER[1]}, "minutes": 25}},
    {"id": "iso-006", "title": "阈值收紧到 0.6：盲区类别应多于基准",
     "request": {"center": {"lat": CENTER[0], "lng": CENTER[1]}, "minutes": 15, "blind_spot_threshold": 0.6}},
    {"id": "iso-007", "title": "中心点北移 ~670m：合成路网平移不变，面积相同但覆盖结构改变",
     "request": {"center": {"lat": CENTER[0] + 0.006, "lng": CENTER[1]}, "minutes": 15}},
    {"id": "iso-008", "title": "快走 6 km/h：面积应大于基准",
     "request": {"center": {"lat": CENTER[0], "lng": CENTER[1]}, "minutes": 15, "walking_speed_kmh": 6.0}},
    {"id": "iso-009", "title": "阈值放宽到 0.1：盲区应只剩类别缺失项",
     "request": {"center": {"lat": CENTER[0], "lng": CENTER[1]}, "minutes": 15, "blind_spot_threshold": 0.1}},
    {"id": "iso-010", "title": "5 分钟小圈：绝大多数类别应判盲区",
     "request": {"center": {"lat": CENTER[0], "lng": CENTER[1]}, "minutes": 5}},
]


def build_pois() -> list:
    pois = []
    for i, (name, cat, bearing, dist) in enumerate(LAYOUT):
        lat, lng = geo.destination(CENTER, bearing, dist)
        pois.append({
            "id": f"curated-{i:03d}",
            "name": name,
            "category": cat,
            "lat": round(lat, 7),
            "lng": round(lng, 7),
        })
    return pois


async def run_case(pois, case: dict) -> dict:
    req = case["request"]
    # 离线传输按请求步速构造：walking_speed_kmh 在离线模式同样改变结果
    transport = OfflineOsrmTransport(
        os.path.join(FIX_DIR, "osrm_table.json"),
        speed_kmh=req.get("walking_speed_kmh"),
    )
    engine = IsochroneEngine(transport=transport)
    iso = await engine.compute(
        center=LatLng(**req["center"]),
        minutes=req.get("minutes", 15),
        walking_speed_kmh=req.get("walking_speed_kmh", 4.8),
        directions=req.get("directions", 16),
        polygon_mode=req.get("polygon_mode", "ring"),
        data_source="offline-synthetic",
    )
    cov = analyze_coverage(iso.polygon, pois, threshold=req.get("blind_spot_threshold", 0.3))
    return {
        "area_m2": round(iso.area_m2, 1),
        "vertex_count": len(iso.polygon.coordinates[0]) - 1,  # 减去闭合点
        "degraded": iso.degraded,
        "degraded_directions": iso.degraded_directions,
        "coverage": {
            c.key: {"total": c.total, "inside": c.inside, "coverage_rate": round(c.coverage_rate, 6)}
            for c in cov.categories
        },
        "blind_spots": cov.blind_spots,
    }


async def main() -> None:
    os.makedirs(FIX_DIR, exist_ok=True)
    os.makedirs(EVAL_DIR, exist_ok=True)

    pois_raw = build_pois()
    with open(os.path.join(FIX_DIR, "pois.json"), "w", encoding="utf-8") as f:
        json.dump({
            "comment": "curated POI 集：由 tests/generate_eval_fixtures.py 从 LAYOUT 布局表确定性生成。中心点 31.2304,121.4737。",
            "pois": pois_raw,
        }, f, ensure_ascii=False, indent=2)

    from app.isochrone.schemas import Poi
    pois = [Poi(**p) for p in pois_raw]

    cases_out = []
    for case in CASES:
        expected = await run_case(pois, case)
        cases_out.append({
            "id": case["id"],
            "title": case["title"],
            "request": case["request"],
            "expect": expected,
        })

    doc = {
        "suite": "isochrone-regression",
        "version": 1,
        "comment": (
            "LifeTrip 等时圈 10 题回归集。期望值由离线管线（OfflineOsrmTransport + "
            "curated POI）实际运行生成，断言口径见 tests/test_isochrone.py::test_eval_regression。"
            "TODO-ADAPT：若 /v1/eval/run 有既有的题目 schema（如 packages/contracts 里的 EvalCase），"
            "把本文件的字段映射过去；回归断言逻辑可复用 tests 里的实现。"
        ),
        "tolerance": {"area_rel": 0.02, "coverage_abs": 1e-6},
        "cases": cases_out,
    }
    with open(os.path.join(EVAL_DIR, "isochrone_cases.json"), "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)

    print(f"pois: {len(pois_raw)} 生成于 content/fixtures/isochrone/pois.json")
    for c in cases_out:
        print(f"{c['id']}: area={c['expect']['area_m2']}m2 blind={c['expect']['blind_spots']}")


if __name__ == "__main__":
    asyncio.run(main())
