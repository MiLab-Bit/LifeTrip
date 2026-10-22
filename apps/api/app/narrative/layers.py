"""Layered narrative engine — multi-depth storytelling for POI arrival."""
from __future__ import annotations

import json
import logging
import os
import re

from app.contracts import LayeredNarrative, Stop
from app.llm import chat_json
from app.paths import NARRATIVES

# Layer depth presets
LAYER_DEPTH = {
    "quick": {"max_chars": 60, "thinking": "low"},
    "standard": {"max_chars": 200, "thinking": "low"},
    "deep": {"max_chars": 500, "thinking": "medium"},
}


def _build_quick(stop: Stop, vibe: str) -> str:
    """One-sentence quick glance (~15s)."""
    return f"{stop.headline}。{stop.tip}"


def _build_standard(stop: Stop, vibe: str) -> str:
    """3-4 sentence standard narrative (~60s)."""
    parts = [f"「{stop.name}」"]
    if stop.headline:
        parts.append(stop.headline)
    if stop.body:
        parts.append(stop.body)
    if stop.tip:
        parts.append(f"💡 {stop.tip}")
    return " — ".join(parts)


def _build_deep_local(stop: Stop, vibe: str) -> str:
    """Local deep narrative without LLM — adds tag context."""
    tag_str = "、".join(stop.tags[:4]) if stop.tags else "城市漫步"
    base = _build_standard(stop, vibe)
    indoor_note = "室内站" if stop.indoor else "户外站"
    verified_note = ""
    if stop.sourceLabel == "green":
        verified_note = "（编辑核实）"
    elif stop.sourceLabel == "blue":
        verified_note = "（社区标注）"
    else:
        verified_note = "（未核实）"
    return f"{base}\n\n标签：{tag_str} · {indoor_note} {verified_note}"


def _llm_enabled() -> bool:
    return os.getenv("LIFETRIP_LLM_POLISH", "0") == "1" and bool(os.getenv("LIFETRIP_LLM_API_KEY"))


async def _call_llm_deep(stop: Stop, vibe: str) -> str | None:
    """Generate deep cultural narrative via LLM (unmetered — 历史未计量).

    平台 key / base_url / model 统一由 app.llm 解析（env 缺失时回退历史默认）。
    失败返回 None，由调用方走本地兜底。
    """
    model = os.getenv("LIFETRIP_LLM_MODEL") or "qwen3.5-397b-a17b"
    system = (
        "你是 LifeTrip 文化导览编辑。\n\n"
        "任务：为 city walk 站点撰写深度文化叙事。\n\n"
        "规则：\n"
        "1. 只使用提供的信息，不编造历史事件、人物、日期。\n"
        "2. 可补充：建筑风格解读、街区文化背景、在地生活观察。\n"
        "3. 语气：有温度的城市观察者，不是百科全书。\n"
        "4. 控制在 300 字以内。\n\n"
        "返回 JSON：{\"deep\":\"\"}"
    )
    user = json.dumps({
        "name": stop.name,
        "district": stop.district,
        "vibe": vibe,
        "tags": stop.tags,
        "headline": stop.headline,
        "body": stop.body,
        "tip": stop.tip,
        "indoor": stop.indoor,
    }, ensure_ascii=False)

    data = await chat_json(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        model=model,
        temperature=0.4,
        max_tokens=None,
        unmetered=True,
    )
    if not data:
        return None
    result = str(data.get("deep", ""))[:500] or None
    if result:
        logging.info(f"LLM deep generated for {stop.name}: {result[:50]}...")
    return result


def _load_editor_deep(poi_id: str) -> str | None:
    """Check for editor-provided deep narrative."""
    safe_id = re.sub(r"[^\w.-]", "_", poi_id)
    # Try layered format first
    path = NARRATIVES / f"{safe_id}_deep.json"
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data.get("deep")
        except (json.JSONDecodeError, KeyError, OSError):
            pass
    return None


async def generate_layered(stop: Stop, *, vibe: str) -> LayeredNarrative:
    """Generate multi-depth narrative for a POI."""
    quick = _build_quick(stop, vibe)
    standard = _build_standard(stop, vibe)

    # Deep layer: editor > LLM > local fallback
    deep = _load_editor_deep(stop.id)
    if not deep and _llm_enabled():
        deep = await _call_llm_deep(stop, vibe)
    if not deep:
        deep = _build_deep_local(stop, vibe)

    return LayeredNarrative(
        poi_id=stop.id,
        quick=quick,
        standard=standard,
        deep=deep,
        source_label=stop.sourceLabel,
        source_note="编辑核实" if stop.sourceLabel == "green" else (
            "社区标注" if stop.sourceLabel == "blue" else "未核实"
        ),
    )
