"""Narrative polish — editor baseline + optional LLM (POI-bound, async)."""
from __future__ import annotations

import json
import os
import re

import httpx

from app.contracts import Stop
from app.paths import CACHE_NARRATIVES_DIR, NARRATIVES

VIBE_TONE = {
    "coffee": "独立杂志感，短句，强调当下逛法",
    "neon": "夜行霓虹，略快，强调气氛和灯光",
    "vintage": "淘街感，强调橱窗和选物",
    "gallery": "留白、安静，强调看展节奏",
}


def _safe_id(poi_id: str) -> str:
    return re.sub(r"[^\w.-]", "_", poi_id)


def _load_editor_narrative(poi_id: str) -> dict[str, str] | None:
    path = NARRATIVES / f"{_safe_id(poi_id)}.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return {
            "headline": data["headline"],
            "body": data["body"],
            "tip": data.get("tip", "到门口再看今日是否开放。"),
            "source": data.get("source", "editor"),
        }
    except (json.JSONDecodeError, KeyError, OSError):
        return None


def _load_llm_cache(poi_id: str, vibe: str) -> dict[str, str] | None:
    CACHE_NARRATIVES_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_NARRATIVES_DIR / f"{_safe_id(poi_id)}_{vibe}.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return {
            "headline": data["headline"],
            "body": data["body"],
            "tip": data.get("tip", ""),
            "source": "llm_cache",
        }
    except (json.JSONDecodeError, KeyError, OSError):
        return None


def _save_llm_cache(poi_id: str, vibe: str, narr: dict[str, str]) -> None:
    CACHE_NARRATIVES_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_NARRATIVES_DIR / f"{_safe_id(poi_id)}_{vibe}.json"
    path.write_text(json.dumps({**narr, "poiId": poi_id, "vibe": vibe}, ensure_ascii=False, indent=2), encoding="utf-8")


def _local_polish(stop: Stop, vibe: str, index: int, total: int) -> dict[str, str]:
    """Rule-based polish when LLM unavailable — still POI-bound."""
    role = ["起点", "中段", "高潮", "收束"][min(index, 3)]
    tone = VIBE_TONE.get(vibe, "city walk")
    headline = stop.headline
    if index == 0 and vibe == "coffee":
        headline = "第一杯：启动这条线"
    elif index == total - 1:
        headline = f"终站 · {stop.headline[:12]}"
    body = stop.body
    if len(body) < 40:
        body = f"「{stop.name}」— {role}。{body}（{tone}）"
    return {"headline": headline, "body": body, "tip": stop.tip, "source": "local"}


def _llm_enabled() -> bool:
    return os.getenv("LIFETRIP_LLM_POLISH", "0") == "1" and bool(os.getenv("LIFETRIP_LLM_API_KEY"))


async def _call_llm(*, stop: Stop, vibe: str, district: str, index: int, total: int) -> dict[str, str] | None:
    api_key = os.getenv("LIFETRIP_LLM_API_KEY", "")
    base = os.getenv("LIFETRIP_LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = os.getenv("LIFETRIP_LLM_MODEL", "gpt-4o-mini")
    url = f"{base}/chat/completions"

    system = (
        "你是 LifeTrip city walk 文案编辑。\n"
        "\n"
        "【最高优先级】只润色语气，不新增事实。找不到依据就保留原文，绝不编造。\n"
        "\n"
        "规则（按重要性排序）：\n"
        "1. POI 名称必须原样保留，不可改写。\n"
        "2. 不可添加未提供的地址/价格/营业时间/电话等具体信息。\n"
        "3. 润色限于语气和节奏（更生动/更紧凑），不改事实。\n"
        "4. 如果原文信息太少，headline 保持简洁就好，不要凑字。\n"
        "\n"
        "返回 JSON：{\"headline\":\"\",\"body\":\"\",\"tip\":\"\"}，不要 markdown。"
    )
    user = json.dumps(
        {
            "poiId": stop.id,
            "name": stop.name,
            "district": district,
            "vibe": vibe,
            "stationIndex": index + 1,
            "totalStations": total,
            "tags": stop.tags,
            "draftHeadline": stop.headline,
            "draftBody": stop.body,
            "draftTip": stop.tip,
            "tone": VIBE_TONE.get(vibe, ""),
        },
        ensure_ascii=False,
    )

    try:
        async with httpx.AsyncClient(timeout=float(os.getenv("LIFETRIP_LLM_TIMEOUT", "25"))) as client:
            r = await client.post(
                url,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": model,
                    "temperature": 0.3,
                    "response_format": {"type": "json_object"},
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                },
            )
            r.raise_for_status()
            content = r.json()["choices"][0]["message"]["content"]
            data = json.loads(content)
    except Exception:  # noqa: BLE001
        return None

    if stop.name not in (data.get("body") or "") and stop.name not in (data.get("headline") or ""):
        data["body"] = f"「{stop.name}」— {data.get('body', stop.body)}"
    return {
        "headline": str(data.get("headline") or stop.headline)[:80],
        "body": (lambda b: b[:280].rsplit("\u3002", 1)[0] + "\u3002" if len(b) > 280 and "\u3002" in b[:280] else b[:280])(str(data.get("body") or stop.body)),
        "tip": str(data.get("tip") or stop.tip)[:120],
        "source": "llm",
    }


async def polish_stop(
    stop: Stop,
    *,
    vibe: str,
    district: str,
    index: int,
    total: int,
) -> Stop:
    editor = _load_editor_narrative(stop.id)
    if editor:
        return stop.model_copy(update={"headline": editor["headline"], "body": editor["body"], "tip": editor["tip"]})

    cached = _load_llm_cache(stop.id, vibe)
    if cached:
        return stop.model_copy(update={"headline": cached["headline"], "body": cached["body"], "tip": cached["tip"]})

    narr: dict[str, str] | None = None
    if _llm_enabled() and stop.sourceLabel != "green":
        narr = await _call_llm(stop=stop, vibe=vibe, district=district, index=index, total=total)
        if narr:
            _save_llm_cache(stop.id, vibe, narr)

    if not narr:
        narr = _local_polish(stop, vibe, index, total)

    return stop.model_copy(update={"headline": narr["headline"], "body": narr["body"], "tip": narr["tip"]})


async def polish_stops(stops: list[Stop], *, vibe: str, district: str) -> list[Stop]:
    """并发润色所有站点 — async 允许未来用 asyncio.gather 并行 LLM 调用。"""
    import asyncio
    total = len(stops)
    tasks = [polish_stop(s, vibe=vibe, district=district, index=i, total=total) for i, s in enumerate(stops)]
    return await asyncio.gather(*tasks)
