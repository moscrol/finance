"""A dated withdrawal must reach the judge; date recognition does not approve it."""

from dataclasses import replace

import pytest

from intelligence.services.episode_semantic_verifier import (
    SemanticEpisodeVerifier,
    numeric_condition_unsupported,
)
from intelligence.services.research_contract import ResearchDeadline
from intelligence.tests.test_episode_semantic_verifier import _judge, _structural


LIVE_WITHDRAWAL = (
    "- “9-11 是出逃式交易/兑现压力放大”：总量数据无逐笔卖单与资金方向，"
    "原倾向性措辞撤回，降级为候选解释之一。"
)


def _dated_structure(text, source_date="2026-09-11"):
    frame, verified = _structural(text)
    evidence = replace(verified.outcome.evidence[0], source_date=source_date)
    return frame, replace(verified, outcome=replace(verified.outcome, evidence=(evidence,)))


@pytest.mark.parametrize("text", [
    LIVE_WITHDRAWAL,
    "- 9-11：原先的出逃判断降级为待验证假说。",
    "**9-11**：原先的出逃判断降级为待验证假说。",
    "「9-11是出逃」的原判断应降级为假说。",
])
def test_bound_short_date_reaches_semantic_review(text):
    frame, verified = _dated_structure(text)
    assert not numeric_condition_unsupported(verified)
    judge = _judge(True)
    result = SemanticEpisodeVerifier(judge_fn=judge).verify(
        frame=frame, structurally_verified=verified,
        deadline=ResearchDeadline.from_timeout(5),
    )
    assert any(text in str(call["sentences"]) for call in judge.calls)
    assert text in result.public_answer


@pytest.mark.parametrize("text", [
    "若市盈率跌破9-11倍则降级。",
    "9-11倍是降级的支撑区间。",
    "9-11亿元是需要守住的支撑。",
    "9-11元是需要守住的支撑。",
    "9-11万元是需要守住的支撑。",
    "9-11手是降级的触发阈值。",
    "9-11个交易日内至少需要完成修复。",
    "9-11点是指数的支撑。",
    "9-11.5倍是降级的支撑区间。",
    "**9-11**倍是降级的支撑区间。",
    "若价格落到9-11则降级。",
    "9-11：若指数跌破3870点则降级。",
    "9-11：若上涨家数低于4000家则降级。",
])
def test_short_date_does_not_hide_numeric_conditions(text):
    _, verified = _dated_structure(text)
    assert numeric_condition_unsupported(verified)


@pytest.mark.parametrize("source_date", [None, "not-a-date", "2026-09-12"])
def test_short_date_requires_a_matching_bound_calendar_date(source_date):
    _, verified = _dated_structure(LIVE_WITHDRAWAL, source_date)
    assert numeric_condition_unsupported(verified)


def test_unbound_source_date_cannot_exempt_numeric_condition():
    _, verified = _dated_structure(LIVE_WITHDRAWAL, "2026-09-12")
    unbound = replace(
        verified.outcome.evidence[0], source_date="2026-09-11", content_hash="unbound-date"
    )
    verified = replace(
        verified, outcome=replace(verified.outcome, evidence=(*verified.outcome.evidence, unbound))
    )
    assert numeric_condition_unsupported(verified)


def test_bound_date_does_not_override_semantic_rejection():
    frame, verified = _dated_structure(LIVE_WITHDRAWAL)
    judge = _judge(False, rejected=(1,), issues=("第1句：语义仍需审核",))
    result = SemanticEpisodeVerifier(judge_fn=judge).verify(
        frame=frame, structurally_verified=verified,
        deadline=ResearchDeadline.from_timeout(5),
    )
    assert judge.calls
    assert result.judge_status != "passed"
    assert any("语义仍需审核" in issue for issue in result.issues)
