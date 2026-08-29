"""Intent classification — question vs walk task."""
from __future__ import annotations

import re

from app.contracts import IntentKind, IntentResult

PLAN_PATTERNS = (
    r"帮我(排|规划|走|逛|生成)",
    r"(今晚|今天|明天|周末).*(逛|走|线)",
    r"(walk|line|route)",
    r"^(咖啡|夜行|古着|画廊)",
    r"慢逛",
    r"\d+\s*分钟",
)

QUESTION_PATTERNS = (
    r"(有什么|哪些是|推荐一下)",
    r"^(什么|哪些|有没有|几点|怎么|where|what|how)",
    r"\?$",
    r"开门",
    r"推荐",
)


def classify_intent(text: str | None, *, has_active_task: bool = False) -> IntentResult:
    if has_active_task:
        return IntentResult(
            kind=IntentKind.resume_walk,
            confidence=0.9,
            message="检测到进行中的走线任务",
        )
    if not text or not text.strip():
        return IntentResult(kind=IntentKind.plan_walk, confidence=0.7)

    t = text.strip().lower()
    for pat in QUESTION_PATTERNS:
        if re.search(pat, t, re.I):
            return IntentResult(
                kind=IntentKind.question,
                confidence=0.75,
                message="识别为问答，不进入 WalkTask",
            )
    for pat in PLAN_PATTERNS:
        if re.search(pat, t, re.I):
            return IntentResult(kind=IntentKind.plan_walk, confidence=0.85)
    return IntentResult(kind=IntentKind.plan_walk, confidence=0.6)
