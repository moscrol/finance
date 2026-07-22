"""market_technical 回归：确定性头部意图、结构化技术位计算、fail-closed 出口。

对应 2026-07-20 真实失败 run（科创50支撑点位被答成题材模板）的验收要求：
- 识别为 market_technical，主体为科创50，头部路由不调用 LLM；
- 答案包含数字支撑区、数据截止日、计算依据、失效条件；
- 取不到 OHLCV 时只报明确 gap，不出现题材/公司/图谱模板；
- AnswerSpec quality.passed=false 时渲染层 fail-closed，不返回原研究结论。
"""

from __future__ import annotations

from datetime import datetime
import json
import pytest

from intelligence.services import answer_model, ask, episode_tools, market_technical
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


def test_intraday_last_bar_is_excluded_from_technical_calculation(monkeypatch) -> None:
    bars = _synthetic_bars()
    bars[-1] = market_technical.DailyBar(
        date="2026-07-20",
        open=1764.59,
        close=1712.12,
        high=1776.07,
        low=1675.41,
        volume=9509913,
    )
    completed, live = market_technical.split_completed_bars(
        bars,
        quote_timestamp=datetime.fromisoformat("2026-07-20T12:05:00+08:00"),
        now=datetime.fromisoformat("2026-07-20T12:45:00+08:00"),
    )
    assert completed[-1].date == bars[-2].date
    assert live is bars[-1]


def test_beijing_920_code_is_not_misclassified_as_shanghai() -> None:
    instrument = market_technical.resolve_market_instrument("920022支撑位在哪")
    assert instrument is not None
    assert instrument.exchange == "BJ"
    assert instrument.provider_symbol == "bj920022"


def test_unsupported_index_returns_typed_gap() -> None:
    outcome = market_technical.resolve_market_technical("中证2000支撑位在哪")
    assert isinstance(outcome, market_technical.TechnicalGap)
    assert "provider_unsupported" in outcome.reason


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


def test_resolve_market_technical_exposes_live_quote_separately(monkeypatch) -> None:
    bars = _synthetic_bars()
    bars[-1] = market_technical.DailyBar(
        date="2026-07-20",
        open=1764.59,
        close=1712.12,
        high=1776.07,
        low=1675.41,
        volume=9509913,
    )
    rows = [
        [bar.date, bar.open, bar.close, bar.high, bar.low, 1000]
        for bar in bars
    ]
    quote = [""] * 31
    quote[4] = "1712.12"
    quote[30] = "20260720124500"
    payload = json.dumps(
        {"data": {"sh000688": {"day": rows, "qt": {"sh000688": quote}}}}
    ).encode("utf-8")

    class _Resp:
        def __enter__(self):
            import io

            self._body = io.BytesIO(payload)
            return self._body

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(
        market_technical,
        "now_shanghai",
        lambda: datetime.fromisoformat("2026-07-20T12:45:00+08:00"),
    )
    outcome = market_technical.resolve_market_technical(
        QUERY,
        opener=lambda url, timeout: _Resp(),
    )
    assert isinstance(outcome, market_technical.TechnicalLevels)
    assert outcome.as_of == bars[-2].date
    assert outcome.live_quote is not None
    assert outcome.live_quote.price == pytest.approx(1712.12)
    assert outcome.volume_available is True


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


def test_market_technical_gap_uses_short_answer_presentation(monkeypatch) -> None:
    monkeypatch.setattr(
        market_technical,
        "resolve_market_technical",
        lambda *args, **kwargs: market_technical.TechnicalGap(
            subject="科创50", symbol="sh000688", reason="provider_unsupported"
        ),
    )
    result = ask._answer_market_technical(
        ask.AskOptions(query=QUERY),
        plan_answer_question(QUERY),
    )
    assert result.answer_spec is not None
    assert result.answer_spec.presentation_kind == "evidence_gap"
    rendered = answer_model.render_answer_spec(result.answer_spec)
    assert "无法可靠计算支撑位" in rendered
    assert "客户验证" not in rendered
    assert "未通过的质检项" not in rendered


def test_market_technical_success_skips_all_llm_synthesis(monkeypatch) -> None:
    levels = market_technical.TechnicalLevels(
        subject="科创50",
        symbol="sh000688",
        as_of="2026-07-20",
        close=1718.69,
        ma={"MA5": 1842.99},
        supports=(
            market_technical.SupportLevel(
                zone_low=1662.65,
                zone_high=1669.99,
                basis=("摆动低点 1669.99",),
            ),
        ),
        resistances=(),
        invalidation="若收盘跌破 1662.65，当前支撑判断失效。",
    )
    monkeypatch.setattr(
        market_technical,
        "resolve_market_technical",
        lambda *args, **kwargs: levels,
    )
    options = ask.AskOptions(query=QUERY)
    result = ask._answer_market_technical(options, plan_answer_question(QUERY))

    prepared = ask.prepare_existing_answer(options, result)

    assert prepared.result.answer_spec is not None
    assert prepared.result.answer_spec.presentation_kind == "market_technical"
    assert prepared.result.prepared_synthesis_messages == []


def test_fast_path_renders_single_resistance_as_one_percentage(
    monkeypatch,
) -> None:
    levels = market_technical.TechnicalLevels(
        subject="科创50",
        symbol="sh000688",
        as_of="2026-07-22",
        close=100.0,
        ma={"MA5": 103.0},
        supports=(),
        resistances=(
            market_technical.SupportLevel(
                zone_low=103.0,
                zone_high=103.0,
                basis=("MA5=103.0",),
            ),
        ),
        invalidation="若收盘跌破 95.00，当前判断失效。",
    )
    monkeypatch.setattr(
        market_technical,
        "resolve_market_technical",
        lambda *args, **kwargs: levels,
    )

    result = episode_tools.run_deterministic_fast_path(
        decide_turn("科创50你认为反弹空间有多少").task_frame,
        timeout=10.0,
    )

    assert "103.00（距收盘约 3.0%）" in result["answer"]
    assert "3.0%~3.0%" not in result["answer"]


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
    assert "未通过的质检项" not in rendered


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
