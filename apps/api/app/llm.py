"""LifeTrip 统一 LLM 网关 — 委托 openclaw_core.gateway.Gateway。

取代 narrative/polish.py 与 narrative/layers.py 各自重复的 httpx 客户端 +
llm_quota 配额打点 + 手工 JSON 解析。两处调用点改为调用本模块的 async 封装，
对外语义不变：平台 LLM 调用失败（含配额超限 / 上游错误）一律返回 None，
由调用方走本地兜底。

配置统一读取 LIFETRIP_LLM_* 环境变量；API key 仅从 env 读取，
不再内置兜底密钥（历史兜底 key 已按泄露处置）。env 缺失时网关
优雅降级，由调用方走本地兜底。
"""
from __future__ import annotations

import os

from openclaw_core.gateway import Gateway, extract_json

from app.paths import DATA

_TIMEOUT = float(os.getenv("LIFETRIP_LLM_TIMEOUT", "120"))



def _platform_base_url() -> str:
    return os.getenv("LIFETRIP_LLM_BASE_URL") or "https://www.abc-ai.cn/v1"


def _platform_api_key() -> str | None:
    return os.getenv("LIFETRIP_LLM_API_KEY")


def _platform_model() -> str:
    return os.getenv("LIFETRIP_LLM_MODEL") or "qwen3.5-397b-a17b"


def _quota_db() -> str:
    return os.getenv("LIFETRIP_QUOTA_DB") or str(DATA / "lifetrip.db")


def _cache_db() -> str:
    return os.getenv("LIFETRIP_LLM_CACHE_DB") or str(DATA / "lifetrip_llm_cache.db")


def _build_gateway(*, unmetered: bool = False) -> Gateway:
    kw = dict(
        platform_base_url=_platform_base_url(),
        platform_api_key=_platform_api_key(),
        default_model=_platform_model(),
        base_url_env="LIFETRIP_LLM_BASE_URL",
        key_env="LIFETRIP_LLM_API_KEY",
        model_env="LIFETRIP_LLM_MODEL",
        quota_db=_quota_db(),
        max_concurrency=5,
        max_retries=3,
        timeout=_TIMEOUT,
        cache_db=_cache_db(),
    )
    if unmetered:
        # layers（深度文化叙事）历史未计量，保持不计量
        kw["quota_limit"] = None
    return Gateway(**kw)


# polish（站点润色）受每日平台配额约束，scope=session_id（与历史一致）；
# layers（深度文化叙事）历史未计量 —— 两者共用同一套客户端/重试/JSON 逻辑。
_gateway = _build_gateway()
_gateway_unmetered = _build_gateway(unmetered=True)


async def chat_json(
    messages: list[dict],
    *,
    model: str | None = None,
    temperature: float = 0.3,
    max_tokens: int | None = None,
    scope: str = "anon",
    unmetered: bool = False,
) -> dict | None:
    """调用平台 LLM 并解析 JSON 响应；任何失败（含配额超限）返回 None。

    response_format=json_object 由 extra_body 传递（OpenAI 兼容网关）。
    unmetered=True 时走不计量网关（layers 深度叙事，历史未计量）。
    """
    gw = _gateway_unmetered if unmetered else _gateway
    try:
        text = await gw.chat(
            messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=False,
            provider=None,
            scope=scope,
            extra_body={"response_format": {"type": "json_object"}},
        )
    except Exception:
        return None
    return extract_json(text)
