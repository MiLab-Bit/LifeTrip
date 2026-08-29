"""L0–L3 permission checks."""
from __future__ import annotations

from app.contracts import PendingAction, PermissionLevel


def requires_confirm(level: PermissionLevel) -> bool:
    return level in ("L2", "L3")


def pending_skip(stop_name: str, stop_index: int) -> PendingAction:
    return PendingAction(
        kind="skip",
        level="L2",
        message=f"跳过第 {stop_index + 1} 站「{stop_name}」？系统将重新规划剩余路线。",
        payload={"stop_index": stop_index},
    )


def pending_reroll(stop_name: str, stop_index: int, replacement: str) -> PendingAction:
    return PendingAction(
        kind="reroll",
        level="L2",
        message=f"将第 {stop_index + 1} 站「{stop_name}」替换为「{replacement}」？",
        payload={"stop_index": stop_index, "replacement": replacement},
    )


def pending_reroute(message: str, proposal_id: str) -> PendingAction:
    return PendingAction(
        kind="apply_reroute",
        level="L2",
        message=message,
        payload={"proposal_id": proposal_id},
    )
