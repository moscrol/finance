from __future__ import annotations

import json

from intelligence.api.structured_reports import (
    ask_result_modules,
    complete_report,
    daily_projection_modules,
    moneyflow_module,
    new_structured_report,
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
    rendered = json.dumps(modules, ensure_ascii=False)
    assert "修复阶段" in rendered
    assert "<script>" not in rendered


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
