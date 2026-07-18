from __future__ import annotations

import json

from intelligence.api.structured_reports import (
    ask_result_modules,
    complete_report,
    daily_projection_modules,
    moneyflow_module,
    new_structured_report,
    render_daily_review_answer,
    upsert_report_module,
)
from intelligence.services.ask import AskResult
from intelligence.services.market_moneyflow import MoneyflowRow, MoneyflowSnapshot


def test_daily_projection_becomes_bounded_stream_modules(tmp_path) -> None:
    exports = tmp_path / "market_feature_store" / "exports"
    exports.mkdir(parents=True)
    (exports / "2026-07-10-daily-review.md").write_text(
        """# 2026-07-10 每日市场复盘

## 核心看板
| 维度 | 结论 |
|---|---|
| 市场性质 | 普通交易日 / 修复阶段 |
| 指数表现 | 上证上涨 0.8% |
| 量能状态 | 成交额 18000 亿 |
| 题材量能 | 双红主线：算力 |

## 内部 HTML
<script>secret()</script>

## 15. 市场环境总评
> 修复延续，下一交易日验证量能。
""",
        encoding="utf-8",
    )

    report_date, modules, warnings = daily_projection_modules(tmp_path)

    assert report_date == "2026-07-10"
    assert warnings == []
    assert modules[0]["module_id"] == "daily_overview"
    assert modules[0]["table"]["rows"][1] == {
        "dimension": "成交情况",
        "conclusion": "成交额 18000 亿",
    }
    rendered = json.dumps(modules, ensure_ascii=False)
    assert "修复阶段" in rendered
    assert "上涨且成交同步放大的方向：算力" in rendered
    assert "canonical" not in rendered
    assert "fact_market_daily" not in rendered
    assert "<script>" not in rendered


def test_daily_projection_can_select_requested_historical_date(tmp_path) -> None:
    exports = tmp_path / "market_feature_store" / "exports"
    exports.mkdir(parents=True)
    for report_date, index_value in (
        ("2026-07-15", "上证上涨 0.3%"),
        ("2026-07-16", "上证下跌 0.8%"),
    ):
        (exports / f"{report_date}-daily-review.md").write_text(
            f"""# {report_date} 每日市场复盘

## 核心看板
| 维度 | 结论 |
|---|---|
| 指数表现 | {index_value} |
""",
            encoding="utf-8",
        )

    report_date, modules, warnings = daily_projection_modules(
        tmp_path,
        requested_date="2026-07-15",
    )

    assert report_date == "2026-07-15"
    assert warnings == []
    assert modules[0]["metrics"][0]["value"] == "上证上涨 0.3%"


def test_daily_projection_does_not_replace_missing_date_with_latest(
    tmp_path,
) -> None:
    exports = tmp_path / "market_feature_store" / "exports"
    exports.mkdir(parents=True)
    (exports / "2026-07-16-daily-review.md").write_text(
        "# 2026-07-16 每日市场复盘",
        encoding="utf-8",
    )

    report_date, modules, warnings = daily_projection_modules(
        tmp_path,
        requested_date="2026-07-15",
    )

    assert report_date is None
    assert modules == []
    assert warnings == [
        "未找到 2026-07-15 的本地复盘报告；日报基础模块缺失。"
    ]


def test_daily_review_fallback_is_plain_chinese_and_keeps_key_numbers(
    tmp_path,
) -> None:
    exports = tmp_path / "market_feature_store" / "exports"
    exports.mkdir(parents=True)
    (exports / "2026-07-10-daily-review.md").write_text(
        """# 2026-07-10 每日市场复盘

## 核心看板
| 维度 | 结论 |
|---|---|
| 市场性质 | 普通交易日 / 底部横盘阶段第9天 |
| 指数表现 | 上证 3996.162，涨幅 -1.00%，偏离度 0.28% |
| 量能状态 | 成交额 33883.62亿，较昨日 16.30%，相对20日均量 104.35% |
| 情绪状态 | 涨家数 3774，MA5 2084.4，涨停 92，跌停 4 |
| 成交集中 | 前三行业 51.00%，较昨日 -0.30pct |
| 强度状态 | 沸点，强度加权涨幅 9.62%，强度成交占比 6.99% |
| 题材量能 | 双红 59 个，单红 70 个；双红主线：计算机(16)、国防军工(9) |
| 新高方向 | 120日新高 78 只；前三申万：电子(33)、计算机(8) |
| 涨停方向 | 核心涨停题材：商业航天(31)、军工(24)、人工智能(23) |

## 14. 数据覆盖检查
| 表 | 状态 |
|---|---|
| fact_sw_l1_daily | OK（降级 31/31：复盘会聚合代理） |

## 15. 市场环境总评
> 2026-07-10 市场性质为普通交易日，市场阶段为底部横盘阶段。
""",
        encoding="utf-8",
    )

    report_date, modules, warnings = daily_projection_modules(tmp_path)
    answer = render_daily_review_answer(
        date_text=report_date,
        modules=modules,
        warnings=warnings,
    )

    assert "7月10日复盘" in answer
    assert "上证收于 3996.16 点" in answer
    assert "上涨 3774 只" in answer
    assert "涨停 92 只，跌停 4 只" in answer
    assert "33883.62 亿元" in answer
    assert "主要放量上涨方向" in answer
    assert "下一交易日重点看" in answer
    for internal_term in (
        "图谱命中",
        "状态机",
        "L3",
        "graph_only",
        "检索骨架",
        "确定性结构化结果",
        "双红",
        "偏离度",
        "沸点",
        "fact_sw_l1_daily",
        "canonical",
    ):
        assert internal_term not in answer


def test_moneyflow_module_is_structured_and_declares_coverage() -> None:
    snapshot = MoneyflowSnapshot(
        status="stale",
        target_date="2026-07-10",
        trade_date="2026-07-08",
        coverage={"limitup": 12, "top100": 100},
        leaders=(
            MoneyflowRow(
                stock_code="300454",
                stock_name="深信服",
                scan_type="limitup",
                main_buy_net_wan=12000,
                total_buy_net_wan=15000,
                score=0.55,
                rank=1,
                pct_change=9.9,
            ),
        ),
        quant_orders=(),
        warnings=("L2 最新扫描日早于报告日。", "仅覆盖涨停股和成交额前100。"),
    )

    module = moneyflow_module(snapshot)

    assert module["module_id"] == "l2_moneyflow"
    assert module["status"] == "degraded"
    assert module["metrics"][1]["value"] == "112"
    assert module["table"]["rows"][0]["stock"] == "深信服"
    assert module["provenance"]["generated_by"] == "deterministic_duckdb_query"


def test_llm_and_deterministic_sections_share_one_report_contract() -> None:
    result = AskResult(
        query="今日复盘",
        trade_date="2026-07-10",
        matched_theme="算力",
        candidate_tier="watch",
        priority_score=80,
    )
    result.synthesis = "量能修复，但须核对 L2 扫描时效。[D9]"
    result.llm_provider = "glm"
    result.sections = {
        "结论": ["市场修复延续。"],
        "分歧反证": ["L2 数据滞后。"],
        "后续验证点": ["验证量能是否延续。"],
    }
    report = new_structured_report(
        run_id="run_demo",
        question="今日复盘",
        task_type="daily",
    )
    for module in ask_result_modules(result):
        upsert_report_module(report, module)
    complete_report(
        report,
        as_of=result.trade_date,
        warnings=[],
        llm_provider="glm",
        llm_model="glm-5.2",
    )

    assert report["status"] == "completed"
    assert report["llm"] == {"used": True, "provider": "glm", "model": "glm-5.2"}
    assert report["modules"][0]["module_id"] == "llm_synthesis"
    assert report["modules"][1]["kind"] == "summary"
    assert "html" not in json.dumps(report, ensure_ascii=False).lower()


def test_ask_warnings_mark_user_facing_modules_degraded() -> None:
    result = AskResult(
        query="今日复盘",
        trade_date="2026-07-10",
        matched_theme="算力",
        candidate_tier="watch",
        priority_score=80,
    )
    result.synthesis = "保留初稿。"
    result.warnings = ["wiki-rag 索引新鲜度=stale，结果按降级证据处理"]
    result.sections = {"结论": ["需要刷新索引后复核。"]}

    modules = ask_result_modules(result)

    assert modules[0]["status"] == "degraded"
    assert modules[0]["warnings"] == result.warnings
    assert modules[1]["status"] == "degraded"
