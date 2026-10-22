"""LifeTrip 核心逻辑黄金测试 —— 仅覆盖「不调 LLM / 不联网」的确定性环节。

覆盖：
  - contracts: Stop / RouteEnvelope（pydantic 契约）字段默认值与序列化往返
  - intent: classify_intent 加权打分（规划/问答/续走/空输入）
  - session_auth: session_id HMAC 防篡改（签发/验签/篡改拒签/空值拒签/遗留未签名放行）

运行（仓库根）：
    pytest tests/test_core_golden.py -q
"""
from __future__ import annotations

import os
import sys

import pytest

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(REPO, "apps", "api"))
sys.path.insert(0, os.getenv("OPENCLAW_SHARED_DIR", "/opt/shared"))

_SESSION_SECRET = "lifetrip-golden-test-secret"


# ----------------------------------------------------------------------
# contracts: Stop / RouteEnvelope
# ----------------------------------------------------------------------
def test_stop_defaults_and_roundtrip():
    from app.contracts import Stop

    s = Stop(id="p1", code="C1", name="和平饭店", district="外滩", lat=31.24, lng=121.49,
             headline="h", body="b", tip="t")
    assert s.tags == []
    assert s.walkMin == 0
    assert s.sourceLabel == "blue"
    assert s.indoor is True
    assert s.skipped is False
    # 序列化往返
    d = s.model_dump()
    s2 = Stop.model_validate(d)
    assert s2 == s


def test_route_envelope_construction():
    from app.contracts import RouteEnvelope, Stop

    stop = Stop(id="p1", code="C1", name="X", district="外滩", lat=31.24, lng=121.49,
                headline="h", body="b", tip="t")
    env = RouteEnvelope(lineCode="L1", lineName="外滩线", title="t", subtitle="s",
                        totalMin=60, vibe="文艺", districtId="d1", stops=[stop])
    assert env.distanceM == 0
    assert env.source is None
    assert len(env.stops) == 1
    assert env.stops[0].name == "X"


# ----------------------------------------------------------------------
# intent: classify_intent
# ----------------------------------------------------------------------
def test_classify_intent_plan_walk():
    from app.contracts import IntentKind
    from app.intent import classify_intent

    r = classify_intent("帮我规划一条今晚的citywalk线路")
    assert r.kind == IntentKind.plan_walk


def test_classify_intent_question():
    from app.contracts import IntentKind
    from app.intent import classify_intent

    r = classify_intent("徐汇有哪些咖啡馆推荐一下？")
    assert r.kind == IntentKind.question


def test_classify_intent_empty_defaults_to_plan():
    from app.contracts import IntentKind
    from app.intent import classify_intent

    r = classify_intent("")
    assert r.kind == IntentKind.plan_walk
    assert r.confidence == 0.7


def test_classify_intent_resume_when_active():
    from app.contracts import IntentKind
    from app.intent import classify_intent

    r = classify_intent("随便逛逛", has_active_task=True)
    assert r.kind == IntentKind.resume_walk
    assert r.confidence == 0.9


# ----------------------------------------------------------------------
# session_auth: HMAC 防篡改
# ----------------------------------------------------------------------
def test_session_new_and_verify(monkeypatch):
    from app.session_auth import is_signed, new_session_id, verify_session_id

    monkeypatch.setenv("LIFETRIP_SESSION_SECRET", _SESSION_SECRET)
    sid = new_session_id()
    assert is_signed(sid)
    assert verify_session_id(sid) == sid


def test_session_tampered_signature_rejected(monkeypatch):
    from app.session_auth import SessionInvalid, new_session_id, verify_session_id

    monkeypatch.setenv("LIFETRIP_SESSION_SECRET", _SESSION_SECRET)
    sid = new_session_id()
    body, sig = sid.split(".", 1)
    bad = f"{body}.{'0' * len(sig)}"
    with pytest.raises(SessionInvalid):
        verify_session_id(bad)


def test_session_empty_rejected(monkeypatch):
    from app.session_auth import SessionInvalid, verify_session_id

    monkeypatch.setenv("LIFETRIP_SESSION_SECRET", _SESSION_SECRET)
    with pytest.raises(SessionInvalid):
        verify_session_id("")


def test_session_legacy_unsigned_allowed(monkeypatch):
    from app.session_auth import verify_session_id

    monkeypatch.delenv("LIFETRIP_SESSION_SECRET", raising=False)
    monkeypatch.setenv("LIFETRIP_ALLOW_LEGACY_SESSIONS", "true")
    assert verify_session_id("legacy-unsigned-id") == "legacy-unsigned-id"
