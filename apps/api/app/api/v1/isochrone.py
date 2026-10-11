"""POST /v1/isochrone/analyze —— 15 分钟生活圈智能体检（L0 只读分析）。

权限分级：本端点不写库、不产生副作用、不改用户任务状态，
按项目 L0–L2 分级标注为 L0（登录即可用，不需要任何写权限）。
集成适配：LifeTrip 现有代码用注释式权限标注（见 app/walk/permissions.py 的
L0–L3 常量），没有 Depends 依赖注入层，故本端点保持 L0 注释式标注。

挂载方式（见 PATCH_README.md）：
    from app.api.v1.isochrone import router as isochrone_router
    app.include_router(isochrone_router, prefix="/v1")
"""

from __future__ import annotations

import os

from fastapi import APIRouter

from app.isochrone import (
    IsochroneEngine,
    OfflineOsrmTransport,
    analyze_coverage,
    load_pois_with_status,
)
from app.isochrone.osrm import HttpOsrmTransport
from app.isochrone.pois import default_fixtures_dir
from app.isochrone.schemas import AnalyzeRequest, AnalyzeResponse

router = APIRouter(prefix="/isochrone", tags=["isochrone"])


def _is_offline() -> bool:
    # 集成适配：与 app/main.py 同一口径（主入口同样判断 LIFETRIP_OFFLINE="1"）。
    return os.environ.get("LIFETRIP_OFFLINE", "").strip() in ("1", "true", "True")


def _offline_transport(speed_kmh: float | None = None) -> OfflineOsrmTransport:
    path = os.path.join(default_fixtures_dir(), "isochrone", "osrm_table.json")
    # 透传请求步速：离线模式下 walking_speed_kmh 同样改变等时圈大小
    return OfflineOsrmTransport(path, speed_kmh=speed_kmh)


@router.post(
    "/analyze",
    response_model=AnalyzeResponse,
    summary="15 分钟生活圈智能体检（等时圈 + 设施覆盖 + 盲区）",
    description=(
        "中心点 → 扇形采样 → OSRM /table 真实步行时间 → 环形插值多边形 → "
        "六类设施覆盖率 → 盲区判定。L0 只读。离线模式（LIFETRIP_OFFLINE=1）"
        "使用确定性合成路网与 curated POI fixtures。"
    ),
)
async def analyze(req: AnalyzeRequest) -> AnalyzeResponse:
    # L0 只读：无写操作、无副作用。
    offline = _is_offline()

    # 1. 等时圈多边形
    if offline:
        transport = _offline_transport(speed_kmh=req.walking_speed_kmh)
        data_source = "offline-synthetic"
    else:
        # 集成适配：base_url 由 HttpOsrmTransport 默认解析（见 isochrone/osrm.py，
        # 与 app/osrm.py 共用 LIFETRIP_OSRM_URL / LIFETRIP_OSRM_BASE）；
        # profile / timeout 沿用项目既有的 LIFETRIP_OSRM_PROFILE、LIFETRIP_OSRM_TIMEOUT。
        transport = HttpOsrmTransport(
            profile=os.environ.get("LIFETRIP_OSRM_PROFILE", "foot"),
            timeout=float(os.environ.get("LIFETRIP_OSRM_TIMEOUT", "5")),
        )
        data_source = "osrm"
    engine = IsochroneEngine(transport=transport)
    iso = await engine.compute(
        center=req.center,
        minutes=req.minutes,
        walking_speed_kmh=req.walking_speed_kmh,
        directions=req.directions,
        polygon_mode=req.polygon_mode,
        data_source=data_source,
    )

    # 2. POI 加载（Overpass 在线 / curated 离线；在线失败自动降级 curated）
    radius_m = max(800, int(req.minutes * req.walking_speed_kmh * 1000 / 60 * 1.5))
    poi_status = await load_pois_with_status(
        source=req.poi_source,
        lat=req.center.lat,
        lng=req.center.lng,
        radius_m=radius_m,
        offline=offline,
    )

    # 3. 覆盖分析 + 盲区
    report = analyze_coverage(iso.polygon, poi_status.pois, threshold=req.blind_spot_threshold)

    # degraded 语义：等时圈有降级方向，或 POI 在线源失败回落 curated
    degraded = iso.degraded or poi_status.fallback_used

    return AnalyzeResponse(
        isochrone=iso,
        coverage=report,
        blind_spots=report.blind_spots,
        degraded=degraded,
        poi_source="curated" if offline else req.poi_source,  # type: ignore[arg-type]
    )
