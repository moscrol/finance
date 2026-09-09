"""P0a / P0b 验收（spec ``2026-09-02-capability-amplification-output-gate-design.md`` §5）。

P0a：``company_financial_evidence`` 的运行时地板补 ``web_search``——20 条策略里唯一
被排除 web 的公司类策略（§1.3 第一层）。断言走合成函数 ``runtime_capabilities_for_frame``，
不断言字面量；不含 web 的策略写成名单，新增策略漏授权会红。

P0b：``financial_data`` 读报告期。2026-09-02 站立日往前数 6 期是 2026 中报 → 2025 一季报，
2024 年报是第 7 期，刚好在默认窗外——两臂拿到的都是 2025 年报 1720.54 与同比 -1.2，
倒推出 1741（§1.3 第二层）。live 探针（2026-09-03，F10 600519 pageSize=8）确认：第 7 行
``2024年报 REPORT_DATE=2024-12-31 NOTICE_DATE=2025-04-03 TOTALOPERATEREVE=1741.44 亿``。
下面的 fixture 逐字复刻这 8 行。

变异验证（§5 第 2 / 6 条）不写成测试，写在收据里：去掉 ``"web_search"`` 那一行 →
``test_p0a_*`` 红；去掉 runner 读报告期那段 → ``test_p0b_maotai_*`` 红。
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from intelligence.services import market_financials
from intelligence.services.agent_research import block_lines_to_evidence
from intelligence.services.episode_factory import build_episode_context
from intelligence.services.episode_tools import build_episode_registry
from intelligence.services.evidence_capabilities import (
    _RUNTIME_CAPABILITY_FLOOR,
    runtime_capabilities_for_frame,
)
from intelligence.services.market_financials import (
    FinancialsFetchResult,
    QuarterFinancials,
    build_financials_block,
    periods_for_financial_query,
    periods_to_cover,
    target_report_end_from_query,
)
from intelligence.services.research_tool_registry import (
    FINANCIAL_DATA_PARAMETERS,
    InvalidResearchToolArguments,
    default_registry,
    parse_financial_data_arguments,
)
from intelligence.services.task_frame import TaskFrame, task_frame_requires_retrieval

MAOTAI_QUESTION = "2024年贵州茅台营业总收入是多少亿元？"
STANDING_DAY = date(2026, 9, 2)


def _maotai_frame(question: str = MAOTAI_QUESTION) -> TaskFrame:
    return TaskFrame(
        raw_question=question,
        user_goal="查证某公司某期财报数字",
        question_type="financial_analysis",
        subject="贵州茅台",
        subject_kind="company",
        market_scope="A股",
        timeframe="2024年报",
        required_outputs=("financial_assessment", "metric_evidence"),
        assumptions=(),
        ambiguities=(),
        clarification_question=None,
        evidence_policy="company_financial_evidence",
        confidence=0.95,
    )


# ---------------------------------------------------------------------------
# P0a（§5 第 1 条）
# ---------------------------------------------------------------------------


def test_p0a_maotai_frame_is_authorized_web_search_through_the_synthesis_function() -> None:
    frame = _maotai_frame()
    assert task_frame_requires_retrieval(frame) is True
    capabilities = runtime_capabilities_for_frame(frame)
    assert "web_search" in capabilities
    # 原有五项一项不少——P0a 是加一项，不是换菜单。
    assert {
        "market_data",
        "financial_data",
        "kb_search",
        "evidence_lookup",
        "l3_lookup",
    }.issubset(set(capabilities))


def test_p0a_only_local_market_strategies_lack_web_search() -> None:
    """名单断言：不含 web 的恰为 4 条本地盘面 / 技术面策略。

    新增一条公司类策略却漏了 web_search，这里会红；这正是 §1.3 那一行漏掉两个月
    没人发现的原因——之前没有任何东西在数这个名单。
    """

    missing = {
        name for name, floor in _RUNTIME_CAPABILITY_FLOOR.items() if "web_search" not in floor
    }
    assert missing == {
        "current_a_share_market",
        "dated_a_share_market",
        "current_market_scenarios",
        "structured_market_technical",
    }


# ---------------------------------------------------------------------------
# P0b：解析（年份 + 期别 → 季末日）
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (MAOTAI_QUESTION, date(2024, 12, 31)),
        ("2024年报", date(2024, 12, 31)),
        ("2024", date(2024, 12, 31)),
        ("2024年", date(2024, 12, 31)),
        ("2025三季报", date(2025, 9, 30)),
        ("2025Q1", date(2025, 3, 31)),
        ("2025年中报净利润", date(2025, 6, 30)),
        ("FY2024 revenue", date(2024, 12, 31)),
        ("贵州茅台2023年度归母净利润", date(2023, 12, 31)),
    ],
)
def test_p0b_target_report_end_parses_year_and_period(text: str, expected: date) -> None:
    assert target_report_end_from_query(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "",
        "贵州茅台最近业绩怎么样",
        "最近一期财报",
        # 证券代码里的 2024 不是年份：前面紧挨着数字。
        "002024 营收",
        "600519 营收",
        # 有年份但既无期别词也不在问财务数字：不猜。
        "2024年上市的公司有哪些",
    ],
)
def test_p0b_target_report_end_returns_none_without_an_explicit_period(text: str) -> None:
    assert target_report_end_from_query(text) is None


def test_p0b_chinese_year_is_not_a_word_boundary() -> None:
    """``\\b(20\\d{2})\\b`` 在「2024年」上不命中（Python ``\\w`` 含 CJK）——上一版就栽在这里。"""

    import re

    assert re.search(r"\b(20\d{2})\b", MAOTAI_QUESTION) is None
    assert target_report_end_from_query(MAOTAI_QUESTION) == date(2024, 12, 31)


# ---------------------------------------------------------------------------
# P0b：窗口（季末日 → 要取几期）
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("target_end", "expected"),
    [
        (date(2024, 12, 31), 7),  # 茅台题：第 7 期，默认 6 期窗外
        (date(2024, 9, 30), 8),
        (date(2025, 12, 31), 6),  # 距离 3，不收窄到 3
        (date(2026, 6, 30), 6),
        (date(2026, 12, 31), 6),  # 目标在未来：默认
    ],
)
def test_p0b_periods_to_cover_counts_quarters_back_from_the_standing_day(
    target_end: date,
    expected: int,
) -> None:
    assert periods_to_cover(target_end, as_of=STANDING_DAY) == expected


def test_p0b_periods_to_cover_caps_the_lookback() -> None:
    assert periods_to_cover(date(2010, 12, 31), as_of=STANDING_DAY) == market_financials.DEFAULT_PERIODS


def test_p0b_periods_for_financial_query_end_to_end() -> None:
    assert periods_for_financial_query(MAOTAI_QUESTION, as_of=STANDING_DAY) == 7
    assert periods_for_financial_query("贵州茅台最近业绩", as_of=STANDING_DAY) == 6


# ---------------------------------------------------------------------------
# P0b：块渲染——每行带日期，证据 as_of 取披露日
# ---------------------------------------------------------------------------


def _annual_2024(notice_date: str | None) -> QuarterFinancials:
    return QuarterFinancials(
        "2024年报",
        "2024-12-31",
        revenue_yi=1741.44,
        revenue_yoy=15.66,
        netprofit_yi=862.28,
        netprofit_yoy=15.38,
        gross_margin=91.93,
        net_margin=52.27,
        notice_date=notice_date,
    )


def test_p0b_block_rows_carry_disclosure_date_and_period_end() -> None:
    block = build_financials_block("贵州茅台", "600519.SH", [_annual_2024("2025-04-03")])
    assert "| 2024年报（2024-12-31） | 2025-04-03 | 1741.44 |" in block
    evidence, _observation = block_lines_to_evidence(
        "financial_data", block, "D7", limit=12, detail_chars=1000
    )
    row = next(item for item in evidence if "1741.44" in item.detail)
    assert row.source_date == "2025-04-03"


def test_p0b_block_falls_back_to_period_end_when_disclosure_date_missing() -> None:
    """新浪 / AKShare 不给披露日：写「缺」，as_of 退到报告期截止日，绝不是取数日。"""

    result = FinancialsFetchResult(
        rows=(_annual_2024(None),),
        provider=market_financials.SINA_PROVIDER,
        status="degraded",
        as_of="2026-09-02",
        attempted=(market_financials.PRIMARY_PROVIDER, market_financials.SINA_PROVIDER),
    )
    block = build_financials_block(
        "贵州茅台", "600519.SH", list(result.rows), fetch_result=result
    )
    assert "| 2024年报（2024-12-31） | 缺 | 1741.44 |" in block
    evidence, _observation = block_lines_to_evidence(
        "financial_data", block, "D7", limit=12, detail_chars=1000
    )
    row = next(item for item in evidence if "1741.44" in item.detail)
    assert row.source_date == "2024-12-31"
    assert row.source_date != "2026-09-02"


# ---------------------------------------------------------------------------
# P0b：参数面——report_period 真被读（§3.6 第三条契约）
# ---------------------------------------------------------------------------


def test_p0b_parser_keeps_bare_snapshot_and_accepts_only_report_period() -> None:
    assert parse_financial_data_arguments({}) == ("", "snapshot")
    assert parse_financial_data_arguments({"report_period": " 2024年报 "}) == (
        "2024年报",
        "2024年报",
    )
    with pytest.raises(InvalidResearchToolArguments, match="report_period"):
        parse_financial_data_arguments({"query": "2024年报"})
    with pytest.raises(InvalidResearchToolArguments, match="report_period"):
        parse_financial_data_arguments({"report_period": "2024年报", "extra": 1})
    with pytest.raises(InvalidResearchToolArguments) as excinfo:
        parse_financial_data_arguments({"report_period": "   "})
    assert excinfo.value.code == "invalid_query"


def test_p0b_default_registry_exposes_report_period_to_the_model() -> None:
    registry = default_registry({"financial_data": lambda *a, **k: None})
    spec = registry.resolve("financial_data")
    assert spec.query_scope == "episode"
    # P0b 只加了 report_period；工单 04 又加了可选 subjects（多公司一次取）。两者都可选，
    # 空参仍是裸快照——这里钉「report_period 在、没有必填项」，不钉参数集恰好等于一个。
    assert "report_period" in spec.parameters["properties"]
    assert set(spec.parameters["properties"]) == {"report_period", "subjects"}
    assert "required" not in spec.parameters
    definition = registry.tool_definitions(("financial_data",))[0]["function"]
    assert definition["parameters"] == FINANCIAL_DATA_PARAMETERS
    assert "report_period" in definition["description"]
    prepared = registry.prepare("financial_data", {"report_period": "2024年报"})
    assert prepared.runner_input == "2024年报"
    assert registry.prepare("financial_data", {}).runner_input == ""


# ---------------------------------------------------------------------------
# P0b（§5 第 5 条）：runner 端到端——2024 年报那一行、1741.44、D7 来源、披露日 as_of
# ---------------------------------------------------------------------------

# 逐字复刻 2026-09-03 live 探针（F10 600519.SH pageSize=8，REPORT_DATE 倒序）。
_F10_ROWS_LIVE_20260903: tuple[QuarterFinancials, ...] = (
    QuarterFinancials("2026中报", "2026-06-30", 922.78, 1.30, notice_date="2026-08-15"),
    QuarterFinancials("2026一季报", "2026-03-31", 547.03, 6.34, notice_date="2026-04-25"),
    QuarterFinancials("2025年报", "2025-12-31", 1720.54, -1.20, notice_date="2026-04-17"),
    QuarterFinancials("2025三季报", "2025-09-30", 1309.04, 6.32, notice_date="2025-10-30"),
    QuarterFinancials("2025中报", "2025-06-30", 910.94, 9.16, notice_date="2025-08-13"),
    QuarterFinancials("2025一季报", "2025-03-31", 514.43, 10.67, notice_date="2025-04-30"),
    QuarterFinancials("2024年报", "2024-12-31", 1741.44, 15.66, notice_date="2025-04-03"),
    QuarterFinancials("2024三季报", "2024-09-30", 1231.23, 16.91, notice_date="2024-10-26"),
)


def _install_fake_d7_chain(monkeypatch, captured: dict[str, object]) -> None:
    """F10 语义：按报告期倒序取前 ``periods`` 行。含金量补全的三次外呼一律短路。"""

    def fake_chain(ts_code, name="", periods=market_financials.DEFAULT_PERIODS, timeout=8.0):
        captured["ts_code"] = ts_code
        captured["periods"] = periods
        return FinancialsFetchResult(
            rows=_F10_ROWS_LIVE_20260903[: max(1, int(periods))],
            provider=market_financials.PRIMARY_PROVIDER,
            status="ok",
            as_of=STANDING_DAY.isoformat(),
            attempted=(market_financials.PRIMARY_PROVIDER,),
        )

    monkeypatch.setattr(market_financials, "fetch_quarterly_financials_chain", fake_chain)
    monkeypatch.setattr(
        market_financials,
        "enrich_quality_fields",
        lambda _ts_code, rows, **_kwargs: rows,
    )


def _maotai_registry(tmp_path: Path, frame: TaskFrame):
    wiki = tmp_path / "wiki"
    relations = wiki / "relations"
    relations.mkdir(parents=True)
    (relations / "entity_exposures.json").write_text(
        '{"entities":{"贵州茅台":{"codes":["600519"],"concepts":{"白酒":{}}}}}',
        encoding="utf-8",
    )
    context = build_episode_context(
        frame,
        task_id=f"p0b-{abs(hash(frame.raw_question))}",
        capabilities=("financial_data",),
        timeout=30.0,
        today=STANDING_DAY.isoformat(),
    )
    registry = build_episode_registry(
        frame,
        context,
        finance_root=tmp_path / "finance",
        knowledge_wiki=wiki,
        l3_runner=None,
    )
    return registry, context


def _revenue_row(observation, report_name: str):
    return next(
        (
            item
            for item in observation.evidence
            if item.detail.startswith(f"| {report_name}（")
            and "1741.44" in item.detail
        ),
        None,
    )


def test_p0b_maotai_question_widens_the_window_to_the_2024_annual_report(
    tmp_path: Path,
    monkeypatch,
) -> None:
    captured: dict[str, object] = {}
    _install_fake_d7_chain(monkeypatch, captured)
    registry, context = _maotai_registry(tmp_path, _maotai_frame())

    observation = registry.execute(
        "financial_data",
        {},
        context=context,
        step_id="p0b-maotai:financials",
    )

    assert captured["ts_code"] == "600519"
    assert captured["periods"] == 7
    row = _revenue_row(observation, "2024年报")
    assert row is not None, [item.detail[:60] for item in observation.evidence]
    assert "2024-12-31" in row.detail
    assert row.source_date == "2025-04-03"  # 披露日，不是取数日 2026-09-02
    assert market_financials.PRIMARY_PROVIDER in row.source or "D7" in row.source
    assert row.evidence_tier == "L2_structured"
    assert observation.trace.status == "success"
    assert "periods=7" in observation.trace.detail
    assert "window=question" in observation.trace.detail
    assert "target_report_end=2024-12-31" in observation.trace.detail


def test_p0b_model_report_period_argument_is_read_and_wins_over_the_question(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """模型显式传 report_period 时以它为准：问句没提年份也能拿到 2024 年报那一行。"""

    captured: dict[str, object] = {}
    _install_fake_d7_chain(monkeypatch, captured)
    registry, context = _maotai_registry(tmp_path, _maotai_frame("贵州茅台营业总收入"))

    observation = registry.execute(
        "financial_data",
        {"report_period": "2024年报"},
        context=context,
        step_id="p0b-maotai:explicit",
    )

    assert captured["periods"] == 7
    assert _revenue_row(observation, "2024年报") is not None
    assert observation.query == "2024年报"
    assert "window=report_period" in observation.trace.detail


def test_p0b_unparseable_report_period_is_reported_not_silently_dropped(
    tmp_path: Path,
    monkeypatch,
) -> None:
    captured: dict[str, object] = {}
    _install_fake_d7_chain(monkeypatch, captured)
    registry, context = _maotai_registry(tmp_path, _maotai_frame("贵州茅台营业总收入"))

    observation = registry.execute(
        "financial_data",
        {"report_period": "最近一期"},
        context=context,
        step_id="p0b-maotai:unparseable",
    )

    assert captured["periods"] == market_financials.DEFAULT_PERIODS
    assert "report_period「最近一期」未能解析为报告期" in observation.observation
    assert "window=default" in observation.trace.detail


def test_p0b_without_a_period_the_default_window_stops_at_the_2025_annual_report(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """对照：问句不带年份时仍是 6 期——2024 年报不在返回里。这就是 09-02 两臂看到的世界。"""

    captured: dict[str, object] = {}
    _install_fake_d7_chain(monkeypatch, captured)
    registry, context = _maotai_registry(tmp_path, _maotai_frame("贵州茅台最近业绩怎么样"))

    observation = registry.execute(
        "financial_data",
        {},
        context=context,
        step_id="p0b-maotai:default",
    )

    assert captured["periods"] == market_financials.DEFAULT_PERIODS
    assert _revenue_row(observation, "2024年报") is None
    assert any("2025年报（2025-12-31）" in item.detail for item in observation.evidence)
    assert "window=default" in observation.trace.detail
