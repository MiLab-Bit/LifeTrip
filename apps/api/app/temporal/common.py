"""LifeTrip Temporal 跨边界数据类。"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


@dataclass
class WalkTaskInput:
    """WalkTask 工作流输入。"""
    task_id: str = ""
    area: str = ""
    vibe: str = ""
    duration_min: int = 90
    options: dict[str, Any] = field(default_factory=dict)
