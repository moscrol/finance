"""回答后自动质检：默认对每次 ask/chat 的合成回答跑确定性 rubric 评分并落盘。

这是问答闭环里的「评估」节点：评分走 ``finance_answer_rubric``（纯规则、
不调 LLM、不联网、零成本），每次回答后追加一条记录到
``users/<id>/answer_scores.jsonl`` 台账；低分回答自动沉淀为经验卡候选
（``promotion=candidate`` / ``source=auto-score``），供下次 compose 注入
与人工复核升级。评估失败只降级为警告，绝不影响回答本身。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from intelligence import userspace
from intelligence.eval import finance_answer_rubric as rubric
from intelligence.eval.finance_answer_rubric import FinanceAnswerScore
from intelligence.services import experience_cards

# 低于 C 档下限（65 分）视为低分回答，自动沉淀经验卡候选。
LOW_SCORE_THRESHOLD = 65


@dataclass(frozen=True)
class AutoEvalOutcome:
    score: FinanceAnswerScore
    ledger_path: Path
    card_path: Path | None = None
    warnings: list[str] = field(default_factory=list)


def evaluate_answer(
    question: str,
    answer: str,
    *,
    user: str | None = None,
    local_sources: list[str] | None = None,
    threshold: int = LOW_SCORE_THRESHOLD,
) -> AutoEvalOutcome:
    """给一次回答打分、记台账；低分自动沉淀经验卡候选。"""
    scored = rubric.score_answer(question, answer, local_sources=local_sources or [])
    us = userspace.user_space(user)
    ledger_path = us.answer_scores_path
    warnings: list[str] = []

    record = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "question": question,
        "total_score": scored.total_score,
        "max_score": scored.max_score,
        "grade": scored.grade,
        "failures": list(scored.failures),
    }
    try:
        ledger_path.parent.mkdir(parents=True, exist_ok=True)
        with ledger_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as exc:  # pragma: no cover - defensive
        warnings.append(f"评分台账写入失败：{exc}")

    card_path: Path | None = None
    if scored.total_score < threshold:
        card = experience_cards.build_card_from_score(
            scored,
            answer=answer,
            local_sources=local_sources or [],
            promotion="candidate",
        )
        card["source"] = "auto-score"
        try:
            experience_cards.record_card(us.experience_cards_path, card)
            card_path = us.experience_cards_path
        except Exception as exc:  # pragma: no cover - defensive
            warnings.append(f"经验卡候选写入失败：{exc}")

    return AutoEvalOutcome(score=scored, ledger_path=ledger_path, card_path=card_path, warnings=warnings)


def render_notice(outcome: AutoEvalOutcome) -> str:
    """一行人类可读评分提示（走 stderr，不混入回答正文）。"""
    s = outcome.score
    parts = [f"[answer-score] {s.total_score}/{s.max_score}（{s.grade}）→ {outcome.ledger_path}"]
    if outcome.card_path is not None:
        parts.append(f"低分已沉淀经验卡候选 → {outcome.card_path}")
    if s.failures:
        parts.append(f"主要缺口：{'；'.join(s.failures[:2])}")
    return "；".join(parts)
