"""问句日预取 + 双红戳记：离线锁，不打生产库。"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from intelligence.services.asof_prefetch import (
    collect_prefetch_items,
    dual_red_counts,
    is_fermentation_query,
    resolve_prefetch_sector,
    standing_iso_from_query,
)
from intelligence.services.episode_factory import build_episode_context
from intelligence.services.honesty_gates import requested_information_cutoff
from intelligence.services.research_contract import InformationCutoff
from intelligence.services.turn_controller import decide_turn

try:
    import duckdb
except Exception:  # pragma: no cover
    duckdb = None

pytestmark = pytest.mark.skipif(duckdb is None, reason="duckdb 不可用")

LITHIUM_QUERY = "锂矿从7月初发酵到 2026-07-23，逐步涨幅、成交额和环比怎么走"


def _sector_db(path: Path, rows: list[tuple]) -> Path:
    con = duckdb.connect(str(path))
    con.execute(
        "create table fact_sector_daily ("
        "trade_date date, sector_name varchar, "
        "pct_chg double, diff_ratio double, amount double)"
    )
    con.executemany(
        "insert into fact_sector_daily values (?, ?, ?, ?, ?)",
        rows,
    )
    con.close()
    return path


def test_fermentation_query_cutoff_is_requested_as_of_not_current() -> None:
    cutoff = requested_information_cutoff(LITHIUM_QUERY, today="2026-08-20")
    assert cutoff == InformationCutoff(date(2026, 7, 23), "requested")

    decision = decide_turn(LITHIUM_QUERY)
    context = build_episode_context(
        decision.task_frame,
        task_id="lithium-asof",
        today="2026-08-20",
        latest_data_date="2026-08-19",
    )
    assert context.information_cutoff == InformationCutoff(
        date(2026, 7, 23),
        "requested",
    )


def test_date_range_still_does_not_steal_cutoff() -> None:
    query = "2026年7月1日至5日A股下跌的主要原因是什么"
    assert standing_iso_from_query(query) is None
    assert requested_information_cutoff(query, today="2026-07-27") is None


@pytest.mark.parametrize(
    "query",
    [
        # 2026-08-27 四臂对照实测：这一句让 cutoff 落成 2026-07-16（区间起点），
        # 于是 07-17 之后的数据整段取不到，多日演化题结构上答不了。
        "2026-07-16 到 07-22 这几天，成交量和涨停家数的变化说明了什么",
        "2026-07-16到07-22 成交量怎么变的",
        "2026-07-16 ~ 07-22 的量能演化",
        "2026-07-16～2026-07-22 的量能演化",
        "2026-07-16 — 07-22 的量能演化",
        "2026年7月16日到22日 成交量怎么变的",
    ],
)
def test_range_separators_beyond_zhi_do_not_steal_cutoff(query: str) -> None:
    """区间分隔符不只有「至」。

    守卫原本只认「至」，而同文件的 ``_MD_RANGE_RE`` 早就用了完整字符类
    ``[-~—–～至到]+``——一处对、两处漏，是词表不全，不是设计如此
    （``requested_information_cutoff`` 的 docstring 明写「区间题不走这条」）。
    """

    assert standing_iso_from_query(query) is None
    assert requested_information_cutoff(query, today="2026-07-27") is None


def test_single_leading_date_is_not_swallowed_by_the_range_guard() -> None:
    """反向锁：放宽分隔符不能把单日题也一起挡掉。

    没有这条，把守卫写成「见到日期就返回 None」也能让上面那组全绿——
    那是一道假门禁。
    """

    assert standing_iso_from_query("2026-07-22 今天盘面怎么样") == "2026-07-22"
    assert requested_information_cutoff(
        "2026-07-22 今天盘面怎么样", today="2026-08-27"
    ) == InformationCutoff(date(2026, 7, 22), "requested")


def test_leading_iso_becomes_requested_cutoff() -> None:
    query = "2026-07-23 电网设备为什么涨"
    assert standing_iso_from_query(query) == "2026-07-23"
    cutoff = requested_information_cutoff(query, today="2026-08-20")
    assert cutoff == InformationCutoff(date(2026, 7, 23), "requested")


def test_dual_red_counts_distinguish_zero_from_missing(tmp_path: Path) -> None:
    db = _sector_db(
        tmp_path / "dual.duckdb",
        [
            (date(2026, 8, 17), "板块甲", 1.2, 12.0, 600.0),
            (date(2026, 8, 17), "板块乙", 0.8, 11.0, 501.0),
            (date(2026, 8, 17), "板块丙", -1.0, 3.0, 100.0),
            (date(2026, 8, 18), "板块甲", 2.0, 15.0, 800.0),
            (date(2026, 8, 19), "板块甲", 1.0, 5.0, 100.0),
        ],
    )
    con = duckdb.connect(str(db), read_only=True)
    counts = dual_red_counts(
        con,
        (date(2026, 8, 17), date(2026, 8, 18), date(2026, 8, 19), date(2026, 8, 20)),
    )
    con.close()
    assert counts["2026-08-17"] == "2"
    assert counts["2026-08-18"] == "1"
    assert counts["2026-08-19"] == "0"
    assert counts["2026-08-20"] == "缺数"

    items = collect_prefetch_items(
        question="站在 2026-08-19 收盘看明天",
        question_type="market_forecast",
        subject="A股市场",
        as_of=date(2026, 8, 19),
        market_db_path=db,
    )
    assert len(items) == 1
    assert items[0].tool == "market_data"
    assert "2026-08-17=2" in items[0].detail
    assert "2026-08-18=1" in items[0].detail
    assert "2026-08-19=0" in items[0].detail
    assert "缺数" not in items[0].detail


def test_fermentation_prefetch_uses_exact_sector_and_stamps_double_red(
    tmp_path: Path,
) -> None:
    db = _sector_db(
        tmp_path / "lithium.duckdb",
        [
            (date(2026, 7, 23), "锂矿", 4.4, 11.73, 628.5),
            (date(2026, 7, 23), "锂电池", 5.0, 20.0, 300.0),
            (date(2026, 7, 1), "锂矿", 1.1, 12.0, 510.0),
        ],
    )
    items = collect_prefetch_items(
        question=LITHIUM_QUERY,
        question_type="theme_analysis",
        subject="锂矿",
        as_of=date(2026, 7, 23),
        market_db_path=db,
    )
    assert len(items) == 2
    timeline = next(item for item in items if "双红时间轴" in item.title)
    detail = timeline.detail
    assert timeline.tool == "market_data"
    assert "板块=锂矿" in detail
    assert "锂电池" not in detail
    assert "contains" not in detail
    assert "涨跌幅=4.4" in detail
    assert "成交额亿=628.5" in detail
    assert "边际量=11.73" in detail
    assert "双红=是" in detail
    assert "2026-07-23" in detail
    assert any(item.tool == "mainline_context" for item in items)


def test_prefetch_market_data_satisfies_mandatory_without_model_call() -> None:
    from intelligence.services.agent_research import AgentEvidence
    from intelligence.services.agent_runtime import (
        AgentOutcome,
        AgentUsage,
        EpisodeEvent,
        OutputEvidenceBinding,
    )
    from intelligence.services.episode_issues import IssueCode
    from intelligence.services.episode_verifier import verify_episode_outcome
    from intelligence.services.evidence_capabilities import (
        EvidencePlan,
        EvidenceRequirement,
    )
    from intelligence.services.research_contract import (
        RequiredOutput,
        ResearchTaskContract,
    )

    task_hash = "prefetch-mandatory"
    contract = ResearchTaskContract(
        task_id="prefetch-mandatory",
        question=LITHIUM_QUERY,
        subject="锂矿",
        subject_kind="theme",
        question_type="theme_analysis",
        required_outputs=(
            RequiredOutput("direct_assessment", "直接判断", ("market_data",)),
        ),
        allowed_capabilities=("market_data", "mainline_context"),
        evidence_plan=EvidencePlan(
            "current_mainline",
            (
                EvidenceRequirement("MARKET_DAILY", "market_data", True),
                EvidenceRequirement("D4", "mainline_context", True),
            ),
        ),
        task_frame_hash=task_hash,
    )
    market = AgentEvidence(
        tool="market_data",
        title="双红个数序列",
        detail="双红个数（口径 pct_chg>0 且 diff_ratio>10 且 amount>500）：2026-08-19=0",
        source="本地 DuckDB · 问句日预取",
        content_hash="prefetch-market-1",
    )
    outcome = AgentOutcome(
        task_frame_hash=task_hash,
        status="partial",
        draft="基于预取盘面。",
        evidence=(market,),
        traces=(),
        gaps=(),
        stop_reason="model_finish",
        events=(EpisodeEvent(1, "task", {"task_frame_hash": task_hash}),),
        bindings=(
            OutputEvidenceBinding("direct_assessment", (), "预取未写入 binding"),
        ),
        usage=AgentUsage(),
    )
    verified = verify_episode_outcome(contract, outcome)
    codes = {item.code for item in verified.issue_items}
    assert IssueCode.MISSING_MANDATORY_CAPABILITY in codes
    assert any(
        "mainline_context" in item.subject
        for item in verified.issue_items
        if item.code == IssueCode.MISSING_MANDATORY_CAPABILITY
    )
    assert all(
        "market_data" not in item.subject
        for item in verified.issue_items
        if item.code == IssueCode.MISSING_MANDATORY_CAPABILITY
    )


def test_non_fermentation_theme_question_skips_dual_red_window(
    tmp_path: Path,
) -> None:
    db = _sector_db(
        tmp_path / "solid.duckdb",
        [
            (date(2026, 8, 19), "固态电池", 2.0, 15.0, 800.0),
        ],
    )
    query = "固态电池有什么新进展"
    assert not is_fermentation_query(query)
    items = collect_prefetch_items(
        question=query,
        question_type="theme_analysis",
        subject="固态电池",
        as_of=date(2026, 8, 19),
        market_db_path=db,
    )
    assert items == ()


PCB_CONCEPT_QUERY = (
    "PCB概念这波是怎么发酵到 2026-08-07 这个位置的？"
    "把链路回溯一下，每一步给出当天的涨幅、成交额和成交额环比变化"
)


def test_prefetch_prefers_exact_name_in_query_over_short_subject(
    tmp_path: Path,
) -> None:
    """问句写了 PCB概念，decide_turn 却收成 subject=PCB。

    两套口径同日数字差一倍（概念 4.74%/3432 亿 vs 短名 8.71%/1295 亿）。
    短名在表里也有行，修前会直接锚 PCB，把问句点名的长口径挤掉。
    """

    db = _sector_db(
        tmp_path / "pcb.duckdb",
        [
            (date(2026, 8, 7), "PCB", 8.71, 23.06, 1295.16),
            (date(2026, 8, 7), "PCB概念", 4.74, 23.72, 3432.59),
        ],
    )
    con = duckdb.connect(str(db), read_only=True)
    try:
        assert resolve_prefetch_sector(con, PCB_CONCEPT_QUERY, "PCB") == "PCB概念"
    finally:
        con.close()

    items = collect_prefetch_items(
        question=PCB_CONCEPT_QUERY,
        question_type="theme_analysis",
        subject="PCB",
        as_of=date(2026, 8, 7),
        market_db_path=db,
    )
    timeline = next(item for item in items if "双红时间轴" in item.title)
    assert timeline.title == "PCB概念 双红时间轴"
    assert "板块=PCB概念" in timeline.detail
    assert "板块=PCB；" not in timeline.detail
    assert "涨跌幅=4.74" in timeline.detail
    assert "成交额亿=3432.59" in timeline.detail
    assert "涨跌幅=8.71" not in timeline.detail
    assert "成交额亿=1295.16" not in timeline.detail
