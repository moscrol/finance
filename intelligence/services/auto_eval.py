"""回答后自动质检：默认对每次 ask/chat 的合成回答跑确定性 rubric 并落盘。

规则评分只适合当「挑错助手」：不调 LLM、不联网、零成本，但尚未通过历史
盲测证明能区分预测 hit/miss。因此每次回答只追加到
``users/<id>/answer_scores.jsonl`` 供人工观察；低分仅打标，不自动生成经验卡、
不影响回答、不进入任何硬闸门。经验卡必须由用户反馈或人工复核显式创建。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from intelligence import userspace
from intelligence.eval import finance_answer_rubric as rubric
from intelligence.eval.finance_answer_rubric import FinanceAnswerScore
from intelligence.services.answer_orchestrator import plan_answer_question

# 低于 C 档下限（65 分）只标记为待人工复核，不触发自动动作。
REVIEW_FLAG_THRESHOLD = 65
LOW_SCORE_THRESHOLD = REVIEW_FLAG_THRESHOLD


@dataclass(frozen=True)
class AutoEvalOutcome:
    score: FinanceAnswerScore
    ledger_path: Path
    card_path: Path | None = None
    flagged_for_review: bool = False
    warnings: list[str] = field(default_factory=list)


def evaluate_answer(
    question: str,
    answer: str,
    *,
    user: str | None = None,
    local_sources: list[str] | None = None,
    threshold: int = REVIEW_FLAG_THRESHOLD,
    question_type: str | None = None,
) -> AutoEvalOutcome:
    """给一次回答生成候选审稿意见并记台账；低分只标记人工复核。

    ``question_type`` 未指定时复用 answer_orchestrator 的题型分类，
    使 market_forecast 等题型自动启用专用维度组。"""
    if question_type is None:
        question_type = plan_answer_question(question).question_type
    scored = rubric.score_answer(
        question, answer, local_sources=local_sources or [], question_type=question_type
    )
    us = userspace.user_space(user)
    ledger_path = us.answer_scores_path
    warnings: list[str] = []

    record = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "question": question,
        "question_type": question_type,
        "total_score": scored.total_score,
        "max_score": scored.max_score,
        "grade": scored.grade,
        "failures": list(scored.failures),
        "role": scored.role,
        "calibration_status": scored.calibration_status,
        "decision_eligible": scored.decision_eligible,
        "flagged_for_review": scored.percent < threshold,
    }
    try:
        ledger_path.parent.mkdir(parents=True, exist_ok=True)
        with ledger_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as exc:  # pragma: no cover - defensive
        warnings.append(f"评分台账写入失败：{exc}")

    return AutoEvalOutcome(
        score=scored,
        ledger_path=ledger_path,
        flagged_for_review=scored.percent < threshold,
        warnings=warnings,
    )


def render_notice(outcome: AutoEvalOutcome) -> str:
    """一行人类可读评分提示（走 stderr，不混入回答正文）。"""
    s = outcome.score
    parts = [
        f"[answer-review/advisory] {s.total_score}/{s.max_score}（{s.grade}）→ {outcome.ledger_path}"
    ]
    if outcome.flagged_for_review:
        parts.append("仅标记待人工复核；未自动阻断、未自动回灌")
    if s.failures:
        parts.append(f"主要缺口：{'；'.join(s.failures[:2])}")
    return "；".join(parts)
