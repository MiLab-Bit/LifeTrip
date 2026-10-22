"""Badge system — milestone achievements for exploration."""
from __future__ import annotations

from datetime import datetime

from app.contracts import Badge, WalkProfile, WalkTask


def _now() -> str:
    return datetime.utcnow().isoformat()


# Badge definitions (id -> metadata)
BADGE_DEFS: list[dict[str, str]] = [
    {"id": "first_walk", "name": "初探者", "description": "完成第一次漫步", "icon": "🚶"},
    {"id": "coffee_lover", "name": "咖啡达人", "description": "走完 3 条咖啡线", "icon": "☕"},
    {"id": "night_walker", "name": "夜行人", "description": "走完 1 条夜行线", "icon": "🌙"},
    {"id": "vintage_hunter", "name": "淘街客", "description": "走完 1 条古着线", "icon": "🧥"},
    {"id": "gallery_goer", "name": "看展人", "description": "走完 1 条画廊线", "icon": "🖼️"},
    {"id": "all_round", "name": "全能漫步", "description": "每种 vibe 各走 1 条", "icon": "⭐"},
    {"id": "streak_4", "name": "全勤", "description": "连续 4 周都有走线", "icon": "🔥"},
    {"id": "explorer_3", "name": "街区探索者", "description": "走过 3 个不同片区", "icon": "🗺️"},
    {"id": "marathon_5km", "name": "五公里", "description": "累计步行 5 公里", "icon": "🏃"},
    {"id": "collector_20", "name": "收藏家", "description": "走过 20 个不同站点", "icon": "📮"},
    {"id": "regular_10", "name": "常客", "description": "完成 10 次漫步", "icon": "🏆"},
]


def compute_badges(profile: WalkProfile, completed: list[WalkTask]) -> list[Badge]:
    """Compute which badges are earned based on completed walks + profile."""
    # Gather stats from tasks
    vibe_counts: dict[str, int] = {}
    districts_visited: set[str] = set()
    unique_pois: set[str] = set()
    total_km = 0.0
    walk_dates: list[str] = []
    vibes_covered: set[str] = set()

    for task in completed:
        vibe_counts[task.brief.vibe] = vibe_counts.get(task.brief.vibe, 0) + 1
        vibes_covered.add(task.brief.vibe)
        districts_visited.add(task.brief.district_id)
        for s in task.route.stops:
            if not s.skipped:
                unique_pois.add(s.id)
        total_km += (task.route.distanceM or 0) / 1000.0
        if task.completed_at:
            walk_dates.append(task.completed_at[:10])  # YYYY-MM-DD

    earned_map: dict[str, str] = {}

    # first_walk
    if len(completed) >= 1:
        earned_map["first_walk"] = completed[0].completed_at or _now()

    # vibe-specific badges
    if vibe_counts.get("coffee", 0) >= 3:
        earned_map["coffee_lover"] = _now()
    if vibe_counts.get("neon", 0) >= 1:
        earned_map["night_walker"] = _now()
    if vibe_counts.get("vintage", 0) >= 1:
        earned_map["vintage_hunter"] = _now()
    if vibe_counts.get("gallery", 0) >= 1:
        earned_map["gallery_goer"] = _now()

    # all_round — all 4 vibes
    if len(vibes_covered & {"coffee", "neon", "vintage", "gallery"}) >= 4:
        earned_map["all_round"] = _now()

    # streak_4 — 4 consecutive weeks with at least one walk
    if walk_dates:
        unique_weeks: set[str] = set()
        for d in walk_dates:
            dt = datetime.fromisoformat(d)
            iso_week = f"{dt.isocalendar()[0]}-{dt.isocalendar()[1]}"
            unique_weeks.add(iso_week)
        if len(unique_weeks) >= 4:
            earned_map["streak_4"] = _now()

    # explorer_3
    if len(districts_visited) >= 3:
        earned_map["explorer_3"] = _now()

    # marathon_5km
    if total_km >= 5.0:
        earned_map["marathon_5km"] = _now()

    # collector_20
    if len(unique_pois) >= 20:
        earned_map["collector_20"] = _now()

    # regular_10
    if len(completed) >= 10:
        earned_map["regular_10"] = _now()

    # Build result
    badges: list[Badge] = []
    for defn in BADGE_DEFS:
        bid = defn["id"]
        badges.append(Badge(
            id=bid,
            name=defn["name"],
            description=defn["description"],
            icon=defn["icon"],
            earned=bid in earned_map,
            earned_at=earned_map.get(bid),
        ))
    return badges
