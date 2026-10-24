"""LifeTrip LLM 每日配额测试 — 不调 LLM（打桩 Gateway 客户端）。

polish._call_llm 现经 app.llm.chat_json → hermes_core.gateway.Gateway；
本测试只替换 Gateway 的客户端构造与配额存储，验证配额门、scope 隔离与降级
（真实网关逻辑在 hermes_core 黄金测试中覆盖）。

运行（仓库根）：venv/bin/python -m pytest tests/test_llm_quota.py -v
"""
from __future__ import annotations

import asyncio
import os
import sys
from types import SimpleNamespace

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(REPO, "apps", "api"))
sys.path.insert(0, os.getenv("OPENCLAW_SHARED_DIR", "/opt/shared"))

from app import llm as lifetrip_llm  # noqa: E402
from app.contracts import Stop  # noqa: E402
from app.narrative import polish  # noqa: E402
from hermes_core.quota import QuotaGate  # noqa: E402

# 供应商调用记账：配额门生效时供应商永远不应被调用
SUPPLIER_CALLS: list = []


class _Resp:
    def __init__(self, content: str):
        self.choices = [SimpleNamespace(message=SimpleNamespace(content=content))]


class _Completions:
    def __init__(self, fc):
        self.fc = fc

    async def create(self, **kw):
        self.fc.calls.append(kw)
        content = '{"headline":"润色标题","body":"测试POI0 润色正文","tip":"润色提示"}'
        return _Resp(content)


class _Chat:
    def __init__(self, fc):
        self.completions = _Completions(fc)


class _FakeClient:
    def __init__(self):
        self.calls = SUPPLIER_CALLS

    chat = property(lambda self: _Chat(self))


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
    SUPPLIER_CALLS.clear()
    db = str(tmp_path / "lifetrip.db")
    gate = QuotaGate(db, limit=3)
    lifetrip_llm._gateway._quota = gate
    lifetrip_llm._gateway._cache = None  # 测试关闭缓存，保证每次真实走配额门
    fc = _FakeClient()
    monkeypatch.setattr(lifetrip_llm._gateway, "_client", lambda b, k: fc)
    monkeypatch.setenv("LIFETRIP_QUOTA_DB", db)
    monkeypatch.setenv("LIFETRIP_LLM_POLISH", "1")
    monkeypatch.setenv("LIFETRIP_LLM_API_KEY", "test-key")
    monkeypatch.setenv("LIFETRIP_LLM_BASE_URL", "http://127.0.0.1:9/v1")
    return db, gate


def _exhaust(gate, scope: str, limit: int = 3) -> None:
    for _ in range(limit):
        assert gate.allow(scope)


def _call(stop, *, session_id="", index=0, total=4):
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
    _, gate = quota_env
    _exhaust(gate, "sess-a")
    out = _call(_stop(), session_id="sess-a")
    assert out is None
    assert SUPPLIER_CALLS == []  # 关键：配额门拦在供应商调用之前


def test_within_quota_calls_llm(quota_env, monkeypatch):
    out = _call(_stop(), session_id="sess-b")
    assert out is not None and out["headline"] == "润色标题"
    assert len(SUPPLIER_CALLS) == 1


def test_sessions_have_independent_quota(quota_env, monkeypatch):
    _, gate = quota_env
    _exhaust(gate, "sess-a")
    blocked = _call(_stop(), session_id="sess-a")
    allowed = _call(_stop(), session_id="sess-b")
    assert blocked is None
    assert allowed is not None


def test_quota_exhausted_polish_stop_falls_back_local(quota_env, monkeypatch):
    _, gate = quota_env
    _exhaust(gate, "sess-c")
    stop = asyncio.run(
        polish.polish_stop(
            _stop(), vibe="coffee", district="安福-五原", index=0, total=4, session_id="sess-c"
        )
    )
    assert "「测试POI0」" in stop.body  # 本地兜底包裹句式
    assert SUPPLIER_CALLS == []


def test_anon_scope_when_no_session(quota_env, monkeypatch):
    _, gate = quota_env
    _exhaust(gate, "anon")
    out = _call(_stop())
    assert out is None
    assert SUPPLIER_CALLS == []


def test_quota_env_unlimited(quota_env, monkeypatch, tmp_path):
    _, gate = quota_env
    lifetrip_llm._gateway._quota = QuotaGate(str(tmp_path / "unlim.db"), limit=None)
    for i in range(5):
        out = _call(_stop(i), session_id="sess-d", index=i, total=5)
        assert out is not None
    assert len(SUPPLIER_CALLS) == 5
