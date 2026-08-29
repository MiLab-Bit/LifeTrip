"""SQLite persistence for sessions and walk tasks."""
from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any

from app.contracts import BriefInput, PendingAction, RouteEnvelope, WalkTask
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
    sid = session_id or str(uuid.uuid4())
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
