"""沙箱财务助手 ``sandbox_fincalc`` 的行为夹具（工单 04）。

直接在宿主进程 import 它、把证据列表当参数传——这个模块必须在没有 evidence.json 的地方也能
用，否则它在沙箱里的可用性就没法在单测里钉住。反向验证的五类错（累计 / 单季混用、
亿 / 万混用、零分母、缺季度、修订值）每类一条。
"""

from __future__ import annotations

from intelligence.services import sandbox_fincalc as fc

_EVIDENCE = [
    {
        "ref": "E1",
        "hash": "a" * 16,
        "tool": "financial_data",
        "as_of": "2026-08-15",
        "observations": [
            {"subject": "600519.SH", "as_of": "2025-03-31", "metric": "revenue_cum_yi", "value": 514.43},
            {"subject": "600519.SH", "as_of": "2025-06-30", "metric": "revenue_cum_yi", "value": 910.94},
            {"subject": "600519.SH", "as_of": "2025-12-31", "metric": "revenue_cum_yi", "value": 1720.54},
            {"subject": "600519.SH", "as_of": "2026-03-31", "metric": "revenue_cum_yi", "value": 547.03},
            {"subject": "600519.SH", "as_of": "2026-06-30", "metric": "revenue_cum_yi", "value": 922.78},
            {"subject": "600519.SH", "as_of": "2025-06-30", "metric": "ocf_cum_yi", "value": 131.19},
            {"subject": "600519.SH", "as_of": "2026-06-30", "metric": "ocf_cum_yi", "value": 706.91},
            {"subject": "600519.SH", "as_of": "2025-06-30", "metric": "net_profit_cum_yi", "value": 454.03},
            {"subject": "600519.SH", "as_of": "2026-06-30", "metric": "net_profit_cum_yi", "value": 445.17},
        ],
    },
    {
        # 同一期同一指标的修订值：来源日期更新，应取代旧值并留痕。
        "ref": "E2",
        "hash": "b" * 16,
        "tool": "web_fetch",
        "as_of": "2026-09-01",
        "observations": [
            {"subject": "600519.SH", "as_of": "2026-06-30", "metric": "revenue_cum_yi", "value": 922.80},
        ],
    },
]


def test_single_quarter_from_cumulative_marks_missing_prior_period() -> None:
    points = fc.series("600519.SH", "revenue_cum_yi", _EVIDENCE)
    rows = {row["period"]: row for row in fc.to_single_quarter(points)}

    assert rows["2025Q1"]["value"] == 514.43 and "Q1 累计" in rows["2025Q1"]["method"]
    assert rows["2025Q2"]["value"] == 396.51
    # 2025Q3 累计缺 → Q4 不可还原，写 note、不填 0、不外推。
    assert rows["2025Q4"]["value"] is None
    assert "缺上一期累计（2025-09-30）" in rows["2025Q4"]["note"]
    assert rows["2026Q2"]["value"] == round(922.80 - 547.03, 4)


def test_series_prefers_latest_evidence_and_records_revision() -> None:
    points = fc.series("600519.SH", "revenue_cum_yi", _EVIDENCE)
    latest = next(point for point in points if point["as_of"] == "2026-06-30")

    assert latest["value"] == 922.80 and latest["ref"] == "E2"
    assert latest["revised_from"] == [{"value": 922.78, "ref": "E1"}]
    assert [point["as_of"] for point in points] == sorted(point["as_of"] for point in points)
    assert fc.value_at("600519.SH", "revenue_cum_yi", "2025-03-31", _EVIDENCE) == 514.43
    assert fc.subjects(_EVIDENCE) == ["600519.SH"]
    assert "ocf_cum_yi" in fc.metrics(_EVIDENCE, subject="600519.SH")


def test_zero_denominator_and_missing_values_come_back_as_none() -> None:
    assert fc.safe_div(1.0, 0.0) is None
    assert fc.safe_div(None, 2.0) is None
    assert fc.pct(1.0, 4.0) == 25.0
    assert fc.pct_change(110.0, 100.0) == 10.0
    assert fc.pct_change(110.0, 0.0) is None
    assert fc.pct_change(-50.0, -100.0) == 50.0


def test_unit_conversion_only_accepts_known_units() -> None:
    assert fc.to_yi(12345.0, "万元") == 1.2345
    assert fc.to_yi(3.5, "亿") == 3.5
    assert fc.to_yi(2_500_000_000, "元") == 25.0
    assert fc.to_yi(1.0, "克") is None


def test_yoy_and_ratio_series_align_on_period() -> None:
    profit = fc.series("600519.SH", "net_profit_cum_yi", _EVIDENCE)
    yoy = {row["as_of"]: row for row in fc.yoy(profit)}
    assert yoy["2026-06-30"]["prior_as_of"] == "2025-06-30"
    assert yoy["2026-06-30"]["yoy_pct"] == round((445.17 - 454.03) / 454.03 * 100, 2)
    assert yoy["2025-06-30"]["yoy_pct"] is None

    ratio = {row["as_of"]: row for row in fc.ratio_series(fc.series("600519.SH", "ocf_cum_yi", _EVIDENCE), profit)}
    assert ratio["2026-06-30"]["ratio"] == round(706.91 / 445.17, 2)
    assert ratio["2026-06-30"]["period"] == "2026Q2"


def test_scenario_and_sensitivity_tables_follow_the_result_protocol() -> None:
    scenarios = fc.scenario_table(1720.54, {"悲观": -3.0, "中性": 0.0, "乐观": 5.0}, name="2026 收入情景")
    assert scenarios["columns"][0] == "情景"
    values = {row[0]: row[2] for row in scenarios["rows"]}
    assert values["乐观"] == round(1720.54 * 1.05, 2)
    assert values["悲观"] == round(1720.54 * 0.97, 2)

    grid = fc.sensitivity_grid(
        [48, 50, 52],
        [-3, 0, 3],
        lambda margin, growth: 1720.54 * (1 + growth / 100) * margin / 100,
        name="净利润敏感性",
        row_name="净利率%",
        col_name="营收增速%",
        unit="亿元",
    )
    assert grid["columns"] == ["净利率%\\营收增速%", "-3.00", "0.00", "3.00"]
    assert grid["rows"][1][2] == round(1720.54 * 0.50, 2)

    result = fc.build_result(summary={"base": 1720.54}, tables=[scenarios, grid], formulas=["推演值 = 基期 × (1 + 增速)"])
    assert result["schema"] == fc.SCHEMA
    assert [table["name"] for table in result["tables"]] == ["2026 收入情景", "净利润敏感性"]
    assert result["params"] == {}


def test_growth_path_stops_propagating_after_a_missing_rate() -> None:
    path = fc.growth_path(100.0, [10.0, None, 5.0], labels=["2026", "2027", "2028"])
    assert [row["value"] for row in path] == [110.0, None, None]


def test_host_process_without_sandbox_files_sees_empty_inputs() -> None:
    fc._STATE["evidence"] = None
    fc._STATE["params"] = None
    assert fc.evidence() == []
    assert fc.params() == {}
    assert fc.observations() == []
