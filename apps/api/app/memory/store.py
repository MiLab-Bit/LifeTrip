"""SQLite persistence for sessions and walk tasks."""
from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any

from app.contracts import BriefInput, PendingAction, RouteEnvelope, WalkProfile, WalkTask
from app.paths import DATA

DB_PATH = DATA / "lifetrip.db"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_db() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    with _conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                prefs_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS walk_tasks (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                status TEXT NOT NULL,
                brief_json TEXT NOT NULL,
                route_json TEXT NOT NULL,
                current_stop_index INTEGER NOT NULL DEFAULT 0,
                pending_action_json TEXT,
                verify_passed INTEGER,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                completed_at TEXT,
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            );
            CREATE INDEX IF NOT EXISTS idx_walk_tasks_session
                ON walk_tasks(session_id, status);

            -- Sprint 1: WalkDNA
            CREATE TABLE IF NOT EXISTS walk_profiles (
                session_id TEXT PRIMARY KEY,
                profile_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            -- Sprint 5: Route ratings
            CREATE TABLE IF NOT EXISTS route_ratings (
                id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                overall INTEGER NOT NULL,
                poi_ratings_json TEXT NOT NULL DEFAULT '{}',
                comment TEXT NOT NULL DEFAULT '',
                photos_json TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            );
            CREATE INDEX IF NOT EXISTS idx_ratings_session
                ON route_ratings(session_id);

            -- Sprint 5: Community routes
            CREATE TABLE IF NOT EXISTS community_routes (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                route_json TEXT NOT NULL,
                tags_json TEXT NOT NULL DEFAULT '[]',
                rating_sum REAL NOT NULL DEFAULT 0,
                rating_count INTEGER NOT NULL DEFAULT 0,
                walk_count INTEGER NOT NULL DEFAULT 0,
                author_label TEXT NOT NULL DEFAULT '匿名探索者',
                published_at TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            );
            CREATE INDEX IF NOT EXISTS idx_community_published
                ON community_routes(published_at DESC);

            -- v0.6: UGC POI Contributions
            CREATE TABLE IF NOT EXISTS poi_contributions (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                name TEXT NOT NULL,
                vibe TEXT NOT NULL,
                city TEXT NOT NULL,
                district TEXT NOT NULL DEFAULT '',
                lat REAL NOT NULL,
                lng REAL NOT NULL,
                headline TEXT NOT NULL,
                body TEXT NOT NULL,
                tip TEXT NOT NULL DEFAULT '',
                tags_json TEXT NOT NULL DEFAULT '[]',
                indoor INTEGER NOT NULL DEFAULT 1,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_contrib_status
                ON poi_contributions(status, vibe, city);

            -- v1.0: Developer API Keys
            CREATE TABLE IF NOT EXISTS dev_api_keys (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                full_key TEXT NOT NULL UNIQUE,
                key_prefix TEXT NOT NULL,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                last_used TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                rate_limit INTEGER NOT NULL DEFAULT 100
            );
            CREATE INDEX IF NOT EXISTS idx_apikeys_session
                ON dev_api_keys(session_id);
            """
        )


@contextmanager
def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def ensure_session(session_id: str | None) -> str:
    from app.session_auth import SessionInvalid, new_session_id, verify_session_id

    if session_id:
        verify_session_id(session_id)  # 伪造/篡改 → SessionInvalid(403)
        sid = session_id
    else:
        sid = new_session_id()
    with _conn() as conn:
        row = conn.execute("SELECT id FROM sessions WHERE id = ?", (sid,)).fetchone()
        if row:
            conn.execute(
                "UPDATE sessions SET updated_at = ? WHERE id = ?",
                (_now(), sid),
            )
            return sid
        now = _now()
        conn.execute(
            "INSERT INTO sessions (id, prefs_json, created_at, updated_at) VALUES (?, '{}', ?, ?)",
            (sid, now, now),
        )
    return sid


def _row_to_task(row: sqlite3.Row) -> WalkTask:
    return WalkTask(
        id=row["id"],
        session_id=row["session_id"],
        status=row["status"],
        brief=BriefInput.model_validate_json(row["brief_json"]),
        route=RouteEnvelope.model_validate_json(row["route_json"]),
        current_stop_index=row["current_stop_index"],
        pending_action=(
            PendingAction.model_validate(json.loads(row["pending_action_json"]))
            if row["pending_action_json"]
            else None
        ),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        completed_at=row["completed_at"],
        verify_passed=bool(row["verify_passed"]) if row["verify_passed"] is not None else None,
    )


def create_task(session_id: str, brief: BriefInput, route: RouteEnvelope) -> WalkTask:
    task_id = str(uuid.uuid4())
    now = _now()
    with _conn() as conn:
        conn.execute(
            """
            INSERT INTO walk_tasks
            (id, session_id, status, brief_json, route_json, current_stop_index,
             pending_action_json, verify_passed, created_at, updated_at, completed_at)
            VALUES (?, ?, 'planned', ?, ?, 0, NULL, NULL, ?, ?, NULL)
            """,
            (
                task_id,
                session_id,
                brief.model_dump_json(),
                route.model_dump_json(),
                now,
                now,
            ),
        )
    return get_task(task_id)  # type: ignore[return-value]


def get_task(task_id: str) -> WalkTask | None:
    with _conn() as conn:
        row = conn.execute("SELECT * FROM walk_tasks WHERE id = ?", (task_id,)).fetchone()
    return _row_to_task(row) if row else None


def update_task(task_id: str, **fields: Any) -> WalkTask | None:
    task = get_task(task_id)
    if not task:
        return None
    data = task.model_dump()
    data.update(fields)
    updated = WalkTask.model_validate(data)
    pending = (
        json.dumps(updated.pending_action.model_dump())
        if updated.pending_action
        else None
    )
    with _conn() as conn:
        conn.execute(
            """
            UPDATE walk_tasks SET
                status = ?, route_json = ?, current_stop_index = ?,
                pending_action_json = ?, verify_passed = ?,
                updated_at = ?, completed_at = ?
            WHERE id = ?
            """,
            (
                updated.status,
                updated.route.model_dump_json(),
                updated.current_stop_index,
                pending,
                updated.verify_passed,
                _now(),
                updated.completed_at,
                task_id,
            ),
        )
    return get_task(task_id)


def find_resumable(session_id: str) -> WalkTask | None:
    with _conn() as conn:
        row = conn.execute(
            """
            SELECT * FROM walk_tasks
            WHERE session_id = ? AND status IN ('planned', 'walking', 'paused')
            ORDER BY updated_at DESC LIMIT 1
            """,
            (session_id,),
        ).fetchone()
    return _row_to_task(row) if row else None


def list_recent_completed(session_id: str, limit: int = 5) -> list[WalkTask]:
    with _conn() as conn:
        rows = conn.execute(
            """
            SELECT * FROM walk_tasks
            WHERE session_id = ? AND status = 'completed'
            ORDER BY completed_at DESC LIMIT ?
            """,
            (session_id, limit),
        ).fetchall()
    return [_row_to_task(r) for r in rows]


# ── Sprint 1: WalkDNA ──────────────────────────────────────────

def get_profile(session_id: str) -> WalkProfile | None:
    """Load a user's WalkDNA profile."""
    with _conn() as conn:
        row = conn.execute(
            "SELECT profile_json FROM walk_profiles WHERE session_id = ?",
            (session_id,),
        ).fetchone()
    if not row:
        return None
    data = json.loads(row["profile_json"])
    data["session_id"] = session_id
    return WalkProfile.model_validate(data)


def save_profile(profile: WalkProfile) -> WalkProfile:
    """Insert or update a WalkDNA profile."""
    now = _now()
    profile.updated_at = now
    if not profile.created_at:
        profile.created_at = now
    with _conn() as conn:
        conn.execute(
            """
            INSERT INTO walk_profiles (session_id, profile_json, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(session_id) DO UPDATE SET
                profile_json = excluded.profile_json,
                updated_at = excluded.updated_at
            """,
            (profile.session_id, profile.model_dump_json(), profile.created_at, now),
        )
    return profile


def derive_profile(session_id: str) -> WalkProfile:
    """Build/update WalkDNA from all completed walk tasks."""
    from app.contracts import WalkProfile as WP  # local import avoids circular

    existing = get_profile(session_id)
    profile = existing or WP(session_id=session_id, created_at=_now())

    completed = list_recent_completed(session_id, limit=100)

    # Aggregate stats
    vibe_counts: dict[str, int] = {}
    district_counts: dict[str, int] = {}
    time_slots: list[str] = []
    total_min = 0
    total_dist = 0
    total_stops = 0

    for task in completed:
        v = task.brief.vibe
        vibe_counts[v] = vibe_counts.get(v, 0) + 1
        d = task.brief.district_id
        district_counts[d] = district_counts.get(d, 0) + 1
        total_min += task.route.totalMin
        total_dist += task.route.distanceM or 0
        total_stops += len(task.route.stops)
        if task.completed_at:
            time_slots.append(task.completed_at[:13])  # hour precision

    profile.completed_walks = len(completed)
    profile.total_walk_minutes = total_min
    profile.total_distance_m = total_dist
    profile.total_stops_visited = total_stops

    # Vibe weights (normalized)
    if vibe_counts:
        mx = max(vibe_counts.values())
        profile.vibe_weights = {k: round(v / mx, 2) for k, v in vibe_counts.items()}

    # Frequent districts (sorted by count)
    profile.frequent_districts = [
        d for d, _ in sorted(district_counts.items(), key=lambda x: -x[1])
    ][:5]

    # Pace preference (most common)
    paces = {}
    for task in completed:
        p = task.brief.pace
        paces[p] = paces.get(p, 0) + 1
    if paces:
        profile.pace_preference = max(paces, key=paces.get)  # type: ignore[arg-type]

    # Preferred time slots
    if time_slots:
        from collections import Counter
        hour_counts = Counter()
        for ts in time_slots:
            try:
                hour_counts[int(ts[11:13])] += 1
            except (ValueError, IndexError):
                pass
        top_hours = [h for h, _ in hour_counts.most_common(3)]
        profile.preferred_time_slots = [f"{h:02d}:00" for h in top_hours]

    # Last active
    if completed:
        profile.last_active_at = completed[0].completed_at or completed[0].updated_at

    # Badges (computed via explore module)
    from app.explore.badges import compute_badges
    profile.badges = [b.id for b in compute_badges(profile, completed)]

    return save_profile(profile)


# ── Sprint 5: Route Ratings ───────────────────────────────────

def save_rating(rating_id: str, task_id: str, session_id: str, overall: int,
                poi_ratings: dict, comment: str, photos: list[str]) -> None:
    now = _now()
    with _conn() as conn:
        conn.execute(
            """
            INSERT INTO route_ratings
                (id, task_id, session_id, overall, poi_ratings_json, comment,
                 photos_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                rating_id, task_id, session_id, overall,
                json.dumps(poi_ratings), comment,
                json.dumps(photos), now,
            ),
        )


def get_ratings_for_task(task_id: str) -> list[dict[str, Any]]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM route_ratings WHERE task_id = ? ORDER BY created_at DESC",
            (task_id,),
        ).fetchall()
    return [dict(r) for r in rows]


# ── Sprint 5: Community Routes ────────────────────────────────

def publish_community_route(route_id: str, session_id: str, route_json: str,
                             tags: list[str], author_label: str) -> None:
    now = _now()
    with _conn() as conn:
        conn.execute(
            """
            INSERT INTO community_routes
                (id, session_id, route_json, tags_json, published_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (route_id, session_id, route_json, json.dumps(tags), now),
        )


def list_community_routes(limit: int = 20, offset: int = 0) -> list[dict[str, Any]]:
    with _conn() as conn:
        rows = conn.execute(
            """
            SELECT * FROM community_routes
            ORDER BY published_at DESC LIMIT ? OFFSET ?
            """,
            (limit, offset),
        ).fetchall()
    return [dict(r) for r in rows]


def rate_community_route(route_id: str, rating: int) -> dict[str, Any] | None:
    with _conn() as conn:
        row = conn.execute(
            "SELECT rating_sum, rating_count FROM community_routes WHERE id = ?",
            (route_id,),
        ).fetchone()
        if not row:
            return None
        new_sum = row["rating_sum"] + rating
        new_count = row["rating_count"] + 1
        conn.execute(
            """
            UPDATE community_routes
            SET rating_sum = ?, rating_count = ?
            WHERE id = ?
            """,
            (new_sum, new_count, route_id),
        )
    return {"rating_sum": new_sum, "rating_count": new_count}


def increment_walk_count(route_id: str) -> None:
    with _conn() as conn:
        conn.execute(
            "UPDATE community_routes SET walk_count = walk_count + 1 WHERE id = ?",
            (route_id,),
        )


# ── v0.6: UGC POI Contributions ────────────────────────────────

def save_contribution(contrib: dict[str, Any]) -> str:
    now = _now()
    with _conn() as conn:
        conn.execute(
            """
            INSERT INTO poi_contributions
                (id, session_id, name, vibe, city, district, lat, lng,
                 headline, body, tip, tags_json, indoor, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)
            """,
            (
                contrib["id"], contrib["session_id"], contrib["name"],
                contrib["vibe"], contrib["city"], contrib.get("district", ""),
                contrib["lat"], contrib["lng"],
                contrib["headline"], contrib["body"], contrib.get("tip", ""),
                json.dumps(contrib.get("tags", [])),
                contrib.get("indoor", True), now,
            ),
        )
    return contrib["id"]


def list_contributions(limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
    with _conn() as conn:
        rows = conn.execute(
            """
            SELECT * FROM poi_contributions
            ORDER BY created_at DESC LIMIT ? OFFSET ?
            """,
            (limit, offset),
        ).fetchall()
    results = []
    for r in rows:
        d = dict(r)
        d["tags"] = json.loads(d.get("tags_json", "[]"))
        del d["tags_json"]
        results.append(d)
    return results


def list_approved_pois(vibe: str | None = None, city: str | None = None) -> list[dict[str, Any]]:
    query = "SELECT * FROM poi_contributions WHERE status = 'approved'"
    params: list[Any] = []
    if vibe:
        query += " AND vibe = ?"
        params.append(vibe)
    if city:
        query += " AND city = ?"
        params.append(city)
    query += " ORDER BY created_at DESC LIMIT 50"
    with _conn() as conn:
        rows = conn.execute(query, params).fetchall()
    results = []
    for r in rows:
        d = dict(r)
        d["tags"] = json.loads(d.get("tags_json", "[]"))
        del d["tags_json"]
        results.append(d)
    return results


# ── v1.0: Developer API Keys ───────────────────────────────────

def create_api_key(session_id: str, name: str) -> dict[str, str]:
    key_id = str(uuid.uuid4())[:8]
    full_key = f"ltk_{uuid.uuid4().hex}"
    prefix = full_key[:12]
    now = _now()
    with _conn() as conn:
        conn.execute(
            """
            INSERT INTO dev_api_keys (id, session_id, full_key, key_prefix, name, created_at, is_active)
            VALUES (?, ?, ?, ?, ?, ?, 1)
            """,
            (key_id, session_id, full_key, prefix, name, now),
        )
    return {"id": key_id, "key": full_key, "prefix": prefix, "name": name}


def list_api_keys(session_id: str) -> list[dict[str, Any]]:
    with _conn() as conn:
        rows = conn.execute(
            """
            SELECT id, session_id, key_prefix, name, created_at, last_used, is_active, rate_limit
            FROM dev_api_keys WHERE session_id = ?
            ORDER BY created_at DESC
            """,
            (session_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def revoke_api_key(session_id: str, key_id: str) -> bool:
    with _conn() as conn:
        cur = conn.execute(
            "UPDATE dev_api_keys SET is_active = 0 WHERE id = ? AND session_id = ?",
            (key_id, session_id),
        )
    return cur.rowcount > 0
