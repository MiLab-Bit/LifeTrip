"""LifeTrip LLM 每日配额测试 — 不调 LLM，只验证配额门、scope 隔离与降级。

运行（仓库根）：
    pytest tests/test_llm_quota.py -v
"""
from __future__ import annotations

import asyncio
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(REPO, "apps", "api"))
sys.path.insert(0, os.getenv("OPENCLAW_SHARED_DIR", "/opt/shared"))

from app.contracts import Stop  # noqa: E402
from app.narrative import polish  # noqa: E402
import llm_quota  # noqa: E402

HTTP_CALLS: list = []


class _StubClient:
    """配额门生效时 HTTP 永远不应发生 — 发生了就记账并炸。"""

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, *args, **kwargs):
        HTTP_CALLS.append(args)
        raise AssertionError("LLM HTTP must not be called when quota exhausted")


class _OkClient(_StubClient):
    async def post(self, *args, **kwargs):
        HTTP_CALLS.append(args)

        class _Resp:
            def raise_for_status(self):
                pass

            def json(self):
                return {
                    "choices": [
                        {
                            "message": {
                                "content": '{"headline":"润色标题","body":"测试POI0 润色正文","tip":"润色提示"}'
                            }
                        }
                    ]
                }

        return _Resp()


def _stop(i: int = 0, body: str = "短正文") -> Stop:
    return Stop(
        id=f"poi-{i}",
        code=f"C{i}",
        name="测试POI0",
        district="安福-五原",
        lat=31.21,
        lng=121.44,
        headline="原标题",
        body=body,
        tip="原提示",
    )


@pytest.fixture()
def quota_env(tmp_path, monkeypatch):
    HTTP_CALLS.clear()
    db = str(tmp_path / "lifetrip.db")
    monkeypatch.setenv("LIFETRIP_QUOTA_DB", db)
    monkeypatch.setenv("LIFETRIP_LLM_POLISH", "1")
    monkeypatch.setenv("LIFETRIP_LLM_API_KEY", "test-key")
    monkeypatch.setenv("LIFETRIP_LLM_BASE_URL", "http://127.0.0.1:9/v1")
    return db


def _exhaust(db: str, scope: str, limit: int = 3) -> None:
    for _ in range(limit):
        assert llm_quota.allow(db, scope, limit=limit)


def _call(stop: Stop, *, session_id: str = "", index: int = 0, total: int = 4):
    return asyncio.run(
        polish._call_llm(
            stop=stop,
            vibe="coffee",
            district="安福-五原",
            index=index,
            total=total,
            session_id=session_id,
        )
    )


def test_quota_exhausted_skips_llm_http(quota_env, monkeypatch):
    monkeypatch.setattr("httpx.AsyncClient", _StubClient)
    _exhaust(quota_env, "sess-a")
    out = _call(_stop(), session_id="sess-a")
    assert out is None
    assert HTTP_CALLS == []  # 关键：配额门拦在 HTTP 之前


def test_within_quota_calls_llm(quota_env, monkeypatch):
    monkeypatch.setattr("httpx.AsyncClient", _OkClient)
    out = _call(_stop(), session_id="sess-b")
    assert out is not None and out["headline"] == "润色标题"
    assert len(HTTP_CALLS) == 1


def test_sessions_have_independent_quota(quota_env, monkeypatch):
    monkeypatch.setattr("httpx.AsyncClient", _OkClient)
    _exhaust(quota_env, "sess-a")
    blocked = _call(_stop(), session_id="sess-a")
    allowed = _call(_stop(), session_id="sess-b")
    assert blocked is None
    assert allowed is not None


def test_quota_exhausted_polish_stop_falls_back_local(quota_env, monkeypatch):
    monkeypatch.setattr("httpx.AsyncClient", _StubClient)
    _exhaust(quota_env, "sess-c")
    stop = asyncio.run(
        polish.polish_stop(
            _stop(), vibe="coffee", district="安福-五原", index=0, total=4, session_id="sess-c"
        )
    )
    assert "「测试POI0」" in stop.body  # 本地兜底包裹句式
    assert HTTP_CALLS == []


def test_anon_scope_when_no_session(quota_env, monkeypatch):
    monkeypatch.setattr("httpx.AsyncClient", _StubClient)
    _exhaust(quota_env, "anon")
    out = _call(_stop())
    assert out is None
    assert HTTP_CALLS == []


def test_quota_env_unlimited(quota_env, monkeypatch):
    monkeypatch.setenv("LLM_QUOTA_LIMIT", "0")
    monkeypatch.setattr("httpx.AsyncClient", _OkClient)
    for i in range(5):
        out = _call(_stop(i), session_id="sess-d", index=i, total=5)
        assert out is not None
    assert len(HTTP_CALLS) == 5
