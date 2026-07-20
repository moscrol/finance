"""market_technical 回归：确定性头部意图、结构化技术位计算、fail-closed 出口。

对应 2026-07-20 真实失败 run（科创50支撑点位被答成题材模板）的验收要求：
- 识别为 market_technical，主体为科创50，头部路由不调用 LLM；
- 答案包含数字支撑区、数据截止日、计算依据、失效条件；
- 取不到 OHLCV 时只报明确 gap，不出现题材/公司/图谱模板；
- AnswerSpec quality.passed=false 时渲染层 fail-closed，不返回原研究结论。
"""

from __future__ import annotations

import pytest

from intelligence.services import answer_model, market_technical
from intelligence.services.answer_orchestrator import plan_answer_question
from intelligence.services.query_understanding import (
    is_market_technical_query,
    match_index_subject,
    understand_query,
)
from intelligence.services.research_contract import ResearchDeadline
from intelligence.services.route_table import route_by_id
from intelligence.services.turn_controller import decide_turn

QUERY = "科创50的支撑点位在哪"


def _llm_must_not_be_called(_messages: list[dict[str, str]]):
    raise AssertionError("market_technical 头部意图不得调用 LLM controller")


# ---------- 意图识别 ----------


def test_market_technical_query_detected() -> None:
    assert is_market_technical_query(QUERY)
    assert is_market_technical_query("沪深300压力位在哪里")
    assert is_market_technical_query("上证指数回踩到哪有支撑")
    assert not is_market_technical_query("科创50怎么看")
    assert not is_market_technical_query("固态电池的支撑逻辑是什么")


def test_index_alias_maps_to_canonical_code() -> None:
    assert match_index_subject(QUERY) == ("科创50", "000688.SH")
    assert match_index_subject("沪深300压力位") == ("沪深300", "000300.SH")


def test_understand_query_returns_market_technical_envelope() -> None:
    envelope = understand_query(QUERY)
    assert envelope.question_type == "market_technical"
    assert envelope.subject == "科创50"
    assert envelope.subject_kind == "index"
    assert envelope.confidence >= 0.9


def test_route_table_has_market_technical_row() -> None:
    row = route_by_id("market_technical")
    assert row is not None
    assert row.lane == "research"
    assert row.question_type == "market_technical"


# ---------- Controller：确定性路由、不调 LLM、单一事实源 ----------


def test_controller_routes_market_technical_without_llm() -> None:
    decision = decide_turn(QUERY, llm_complete=_llm_must_not_be_called)
    assert decision.lane == "research"
    assert decision.question_type == "market_technical"
    assert decision.subject == "科创50"
    assert decision.turn_intent is not None
    # 单一事实源：intent 与 decision 不允许分叉
    assert decision.turn_intent.question_type == "market_technical"


def test_question_plan_skips_wiki_rag_for_market_technical() -> None:
    plan = plan_answer_question(QUERY)
    assert plan.question_type == "market_technical"
    joined = "\n".join(plan.retrieval_plan)
    assert "OHLCV" in joined
    assert "Wiki RAG" in joined and "跳过" in joined


# ---------- 技术位计算 ----------


def _synthetic_bars(n: int = 80) -> list[market_technical.DailyBar]:
    bars: list[market_technical.DailyBar] = []
    price = 1000.0
    for i in range(n):
        # 缓涨带回踩：第 40 天挖一个明显低点
        drift = 1.5 if i != 40 else -30.0
        price = max(900.0, price + drift)
        bars.append(
            market_technical.DailyBar(
                date=f"2026-{(i // 28) + 1:02d}-{(i % 28) + 1:02d}",
                open=price - 2,
                close=price,
                high=price + 5,
                low=price - 5,
            )
        )
    return bars


def test_compute_technical_levels_supports_below_close() -> None:
    bars = _synthetic_bars()
    levels = market_technical.compute_technical_levels("测试指数", "shTEST", bars)
    assert levels.as_of == bars[-1].date
    assert levels.close == bars[-1].close
    assert levels.supports, "必须给出至少一个支撑区"
    for level in levels.supports:
        assert level.zone_high <= levels.close
        assert level.basis, "每个支撑区必须带计算依据"
    assert "跌破" in levels.invalidation


def test_resolve_market_technical_success_with_stub_opener() -> None:
    import io
    import json as _json

    rows = [
        [bar.date, bar.open, bar.close, bar.high, bar.low, 1000]
        for bar in _synthetic_bars()
    ]
    payload = _json.dumps(
        {"data": {"sh000688": {"day": rows}}}
    ).encode("utf-8")

    class _Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    outcome = market_technical.resolve_market_technical(
        QUERY, opener=lambda url, timeout: _Resp(payload)
    )
    assert isinstance(outcome, market_technical.TechnicalLevels)
    assert outcome.subject == "科创50"
    assert outcome.symbol == "sh000688"
    assert outcome.supports


def test_resolve_market_technical_gap_is_fail_closed() -> None:
    def _broken(url, timeout):  # noqa: ANN001
        raise OSError("network down")

    outcome = market_technical.resolve_market_technical(QUERY, opener=_broken)
    assert isinstance(outcome, market_technical.TechnicalGap)
    text = market_technical.gap_answer_text(outcome)
    assert "无法可靠计算支撑位" in text
    assert "科创50" in text
    # 禁止无关模板
    for banned in ("主线题材", "公司公告", "客户验证", "知识图谱"):
        assert banned not in text


# ---------- AnswerSpec fail-closed 出口 ----------


def _failing_spec() -> answer_model.AnswerSpec:
    spec = answer_model.AnswerSpec(
        research_spec=answer_model.resolve_theme_research_spec(QUERY, None),
        summary=(
            answer_model.Claim(
                claim_id="c1",
                text="主题科创50：但基本面证据不足，偏盘",
                claim_type="inference",
                theme="其他题材",
                status=answer_model.ClaimStatus.INFERRED,
            ),
        ),
        verified_facts=(),
        company_table=(),
        counter_evidence=(),
        gaps=(
            answer_model.Claim(
                claim_id="g1",
                text="缺少科创50近期 OHLCV 日线",
                claim_type="gap",
                theme=QUERY,
                status=answer_model.ClaimStatus.MISSING,
            ),
        ),
        triggers=(),
        next_actions=(),
        sources=(),
        system_notices=(),
    )
    return answer_model.finalize_answer_spec(spec)


def test_failed_quality_spec_renders_evidence_gap_not_research_answer() -> None:
    spec = _failing_spec()
    assert not spec.quality.passed
    rendered = answer_model.render_answer_spec(spec)
    assert "缺少科创50近期 OHLCV 日线" in rendered
    # 不得渲染原研究模板段落
    for banned in ("核心判断", "题材怎么理解", "公司证据"):
        assert banned not in rendered


def test_passed_quality_spec_still_renders_normally() -> None:
    spec = _failing_spec()
    spec = answer_model.AnswerSpec(
        **{
            **{
                field: getattr(spec, field)
                for field in spec.__dataclass_fields__
            },
            "summary": (),
            "quality": answer_model.AnswerQualityReport(),
        }
    )
    # quality.passed=True 时正常走原渲染路径（此处只验证不触发缺口短答开头）
    rendered = answer_model.render_answer_spec(spec)
    assert "未通过的质检项" not in rendered


# ---------- 合成预算硬保留 ----------


def test_research_deadline_reserves_synthesis_budget() -> None:
    deadline = ResearchDeadline.from_timeout(30.0, synthesis_reserve=20.0)
    assert deadline.stage_timeout(60.0) == pytest.approx(10.0, abs=0.5)
    assert deadline.synthesis_timeout(60.0) == pytest.approx(30.0, abs=0.5)
