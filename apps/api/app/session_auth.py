"""Session ID 防篡改：HMAC-SHA256 签名（2026-10 修复）。

背景：session_id 由客户端随请求提交（body/query/path），服务端
ensure_session 对任意 ID upsert——任何知悉（或经 URL/日志/Referer
泄露、或穷举）他人 session_id 的客户端，都可读写其 walk 任务、
画像、探索数据、社区发布。uuid4 不可穷举，但无防伪造、无泄露缓解。

方案（账号体系之外的最小加固，前端零改动）：
- 新签发 sid = <uuid4hex>.<hmac_sha256(secret, uuid4hex)[:24]>
- 每次使用验签，签名不符 → SessionInvalid（HTTP 403），无法伪造
- 存量未签名 ID（老用户 localStorage）走 grace period：
  LIFETRIP_ALLOW_LEGACY_SESSIONS 默认 true 放行并记警告日志，
  前端全量迁移后可置 false 彻底关闭。
密钥：LIFETRIP_SESSION_SECRET（unit EnvironmentFile 注入，vault 另存）。
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
import uuid

log = logging.getLogger("lifetrip.session_auth")

SEP = "."
_SIG_LEN = 24


class SessionInvalid(Exception):
    """session_id 为空、未签名(grace 关闭时)或签名不符。"""


def _secret() -> str:
    s = os.environ.get("LIFETRIP_SESSION_SECRET", "").strip()
    if not s:
        raise RuntimeError("LIFETRIP_SESSION_SECRET 未配置")
    return s


def _sig(secret: str, sid_body: str) -> str:
    return hmac.new(secret.encode("utf-8"), sid_body.encode("utf-8"), hashlib.sha256).hexdigest()[:_SIG_LEN]


def new_session_id() -> str:
    body = uuid.uuid4().hex
    return f"{body}{SEP}{_sig(_secret(), body)}"


def is_signed(sid: str) -> bool:
    return SEP in sid and len(sid.split(SEP, 1)[1]) == _SIG_LEN


def verify_session_id(sid: str) -> str:
    """验签并原样返回；不合法抛 SessionInvalid。"""
    if not sid:
        raise SessionInvalid("empty session id")
    if not is_signed(sid):
        if str(os.environ.get("LIFETRIP_ALLOW_LEGACY_SESSIONS", "true")).lower() == "false":
            raise SessionInvalid("legacy unsigned session id rejected")
        log.warning("[session] legacy unsigned id in use: %s...", sid[:8])
        return sid
    body, sig = sid.split(SEP, 1)
    if not hmac.compare_digest(_sig(_secret(), body), sig):
        raise SessionInvalid("bad session signature")
    return sid
