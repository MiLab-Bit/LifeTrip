"""Intent classification — question vs walk task (hardened v2).

Improvements over v0.4:
- Weighted scoring instead of first-match-wins
- More patterns for both plan and question intents
- Hesitation detection (decision fatigue)
- Profile-aware suggestions (WalkDNA)
"""
from __future__ import annotations

import re

from app.contracts import IntentKind, IntentResult

# Pattern → weight. Higher weight wins.
PLAN_PATTERNS: list[tuple[str, float]] = [
    (r"帮我(排|规划|走|逛|生成|安排)", 3.0),
    (r"(今晚|今天|明天|周末).{0,6}(逛|走|线|出发)", 3.0),
    (r"(walk|line|route|stroll)", 2.0),
    (r"^(咖啡|夜行|古着|画廊|展览|文艺)", 2.5),
    (r"慢逛|漫步|citywalk|city walk", 3.0),
    (r"\d+\s*分钟", 1.5),
    (r"(轻松|高级|高密度|低密度)", 1.0),
    (r"(徐汇|静安|长宁|浦东).{0,4}(走|逛)", 2.0),
    (r"(随便|你来定|帮我选)", 1.5),  # decision fatigue → plan
]

QUESTION_PATTERNS: list[tuple[str, float]] = [
    (r"(有什么|哪些是|推荐一下)", 2.0),
    (r"^(什么|哪些|有没有|几点|怎么|where|what|how)", 2.0),
    (r"\?$", 1.5),
    (r"开门|营业|几点", 2.0),
    (r"推荐(一下|几个)", 1.5),
    (r"(怎么样|好不好|值得吗)", 1.0),
    (r"(停车|地铁|公交|怎么去)", 2.0),
]

# Hesitation / fatigue signals → suggest walking (low pressure)
HESITATION_PATTERNS = [
    (r"(随便|你来定|帮我选|不知道)", 0.8),
    (r"(纠结|选择困难|犹豫)", 0.8),
]


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

    # Weighted scoring
    question_score = sum(w for pat, w in QUESTION_PATTERNS if re.search(pat, t, re.I))
    plan_score = sum(w for pat, w in PLAN_PATTERNS if re.search(pat, t, re.I))
    hesitation_score = sum(w for pat, w in HESITATION_PATTERNS if re.search(pat, t, re.I))

    # Hesitation nudges toward plan_walk (suggest something easy)
    plan_score += hesitation_score

    if question_score > plan_score and question_score >= 2.0:
        return IntentResult(
            kind=IntentKind.question,
            confidence=min(0.95, question_score / (question_score + plan_score + 0.1)),
            message="识别为问答，不进入 WalkTask",
        )

    confidence = min(0.95, 0.6 + plan_score * 0.1)

    # If hesitation detected, add a gentle message
    if hesitation_score > 0:
        return IntentResult(
            kind=IntentKind.plan_walk,
            confidence=confidence,
            message="检测到犹豫，推荐一条轻松线",
        )

    return IntentResult(kind=IntentKind.plan_walk, confidence=confidence)
