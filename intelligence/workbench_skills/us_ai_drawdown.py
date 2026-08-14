from __future__ import annotations

import json
from dataclasses import asdict

from intelligence import userspace
from intelligence.services.us_stock_drawdown import (
    AlpacaMarketDataError,
    DrawdownReport,
    MissingAlpacaCredentials,
    UsStockDrawdownService,
    parse_trading_day_window,
)
from intelligence.workbench_skills.contracts import (
    JsonObject,
    SkillExecutionContext,
    SkillOutput,
    build_module_answer_contract,
    redact_json,
)


class UsAiDrawdownSkill:
    skill_id = "us-ai-drawdown"

    def execute(self, context: SkillExecutionContext) -> SkillOutput:
        window = parse_trading_day_window(context.query)
        user_root = userspace.user_space(context.user_id).root
        service = UsStockDrawdownService(
            watchlist_path=context.repo_root
            / "intelligence"
            / "config"
            / "us_ai_watchlist.json",
            cache_path=user_root
            / "market-cache"
            / "alpaca-us-adjusted-daily-bars.json",
        )
        try:
            report = service.run(window=window)
        except MissingAlpacaCredentials:
            warning = (
                "未配置 Alpaca 行情凭证，且没有可用的本地缓存。"
            )
            return SkillOutput(
                skill_id=self.skill_id,
                modules=[self._error_module(window, warning)],
                citations=[],
                warnings=[warning],
                as_of=None,
                raw_result_ref=None,
            )
        except (AlpacaMarketDataError, OSError, UnicodeError, ValueError):
            warning = (
                "美股历史日线暂时无法读取，本轮没有生成回撤排序。"
            )
            return SkillOutput(
                skill_id=self.skill_id,
                modules=[self._error_module(window, warning)],
                citations=[],
                warnings=[warning],
                as_of=None,
                raw_result_ref=None,
            )

        modules = [self._report_module(report)]
        citations: list[JsonObject] = [
            {
                "source": "https://docs.alpaca.markets/reference/stockbars",
                "title": "Alpaca Historical Stock Bars",
                "evidence_layer": "market_data",
                "as_of": report.as_of,
            }
        ]
        warnings = list(report.warnings)
        payload: JsonObject = {
            "skill_id": self.skill_id,
            "window": report.window,
            "as_of": report.as_of,
            "source": report.source,
            "fetched_at": report.fetched_at,
            "rows": [asdict(row) for row in report.rows],
            "warnings": warnings,
        }
        safe_payload = redact_json(payload)
        if not isinstance(safe_payload, dict):
            raise ValueError("回撤榜产物格式错误")
        artifact = context.run_store.add_artifact(
            context.run_id,
            "us-ai-drawdown-skill-result.json",
            json.dumps(safe_payload, ensure_ascii=False, indent=2) + "\n",
            renderer="json",
            title="美股 AI 阵营最大回撤原始结果",
        )
        return SkillOutput(
            skill_id=self.skill_id,
            modules=modules,
            citations=citations,
            warnings=warnings,
            as_of=report.as_of,
            raw_result_ref=artifact.path,
            answer_contract=build_module_answer_contract(
                skill_id=self.skill_id,
                title="美股 AI 阵营最大回撤",
                modules=modules,
                citations=citations,
                warnings=warnings,
                as_of=report.as_of,
                retrieval_plan=(
                    "读取可配置的美股 AI 标的池",
                    "通过 Alpaca IEX 获取复权日线并保留最近 N 个"
                    "已完成交易日",
                    "使用最新收盘价计算当日、5 日和 10 日涨幅",
                    "使用滚动峰值计算每个标的区间内最大回撤及"
                    "对应峰谷",
                ),
                output_contract=(
                    "按最大回撤幅度从深到浅排序",
                    "同时展示当日、5 日、10 日涨幅，峰值日、峰值价、"
                    "谷底日、谷底价和有效交易日数",
                    "缺数标的必须明确标记，不补造价格",
                ),
            ),
        )

    @staticmethod
    def _report_module(report: DrawdownReport) -> JsonObject:
        ranked = [row for row in report.rows if row.rank is not None]
        complete_count = sum(
            row.trading_days == report.window for row in report.rows
        )
        worst = ranked[0] if ranked else None
        summary = (
            f"最近 {report.window} 个已完成交易日中，"
            f"{worst.ticker} 最大回撤最深，为 {worst.max_drawdown_pct:.2f}%。"
            if worst is not None and worst.max_drawdown_pct is not None
            else (
                f"最近 {report.window} 个已完成交易日没有足够数据"
                "形成排序。"
            )
        )
        table_rows: list[JsonObject] = []
        for row in report.rows:
            table_rows.append(
                {
                    "rank": row.rank,
                    "ticker": row.ticker,
                    "name": row.name,
                    "group": row.group,
                    "max_drawdown": (
                        f"{row.max_drawdown_pct:.2f}%"
                        if row.max_drawdown_pct is not None
                        else None
                    ),
                    "daily_change": (
                        f"{row.daily_change_pct:.2f}%"
                        if row.daily_change_pct is not None
                        else None
                    ),
                    "return_5d": (
                        f"{row.return_5d_pct:.2f}%"
                        if row.return_5d_pct is not None
                        else None
                    ),
                    "return_10d": (
                        f"{row.return_10d_pct:.2f}%"
                        if row.return_10d_pct is not None
                        else None
                    ),
                    "peak_date": row.peak_date,
                    "peak_price": row.peak_price,
                    "trough_date": row.trough_date,
                    "trough_price": row.trough_price,
                    "trading_days": row.trading_days,
                    "status": row.status,
                }
            )
        return {
            "module_id": "us_ai_drawdown_ranking",
            "title": f"美股 AI 阵营 · {report.window} 个交易日最大回撤",
            "kind": "market_data",
            "status": "degraded" if report.warnings else "complete",
            "summary": summary,
            "content": (
                "口径：使用复权收盘价；当日、5 日和 10 日涨幅分别"
                "对比 1、5、10 个交易日前收盘价；最大回撤是区间内"
                "任一时点相对此前滚动最高收盘价的最大跌幅。"
            ),
            "metrics": [
                {
                    "label": "统计窗口",
                    "value": f"{report.window} 个交易日",
                    "context": "只统计已完成的美股交易日",
                },
                {
                    "label": "数据区间",
                    "value": (
                        f"{report.start_date} 至 {report.as_of}"
                        if report.start_date and report.as_of
                        else "有效数据不足"
                    ),
                },
                {
                    "label": "完整覆盖",
                    "value": f"{complete_count}/{len(report.rows)} 个标的",
                },
                {
                    "label": "数据口径",
                    "value": "Alpaca IEX 复权日线",
                },
            ],
            "items": [],
            "table": {
                "columns": [
                    {"key": "rank", "label": "排名"},
                    {"key": "ticker", "label": "标的"},
                    {"key": "name", "label": "公司"},
                    {"key": "group", "label": "阵营"},
                    {"key": "max_drawdown", "label": "最大回撤"},
                    {"key": "daily_change", "label": "当日涨幅"},
                    {"key": "return_5d", "label": "5日涨幅"},
                    {"key": "return_10d", "label": "10日涨幅"},
                    {"key": "peak_date", "label": "峰值日期"},
                    {"key": "peak_price", "label": "峰值价格"},
                    {"key": "trough_date", "label": "谷底日期"},
                    {"key": "trough_price", "label": "谷底价格"},
                    {"key": "trading_days", "label": "交易日"},
                    {"key": "status", "label": "状态"},
                ],
                "rows": table_rows,
            },
            "warnings": list(report.warnings),
            "provenance": {
                "source": report.source,
                "as_of": report.as_of,
                "generated_by": "rolling_peak_drawdown",
            },
        }

    @staticmethod
    def _error_module(window: int, warning: str) -> JsonObject:
        return {
            "module_id": "us_ai_drawdown_ranking",
            "title": f"美股 AI 阵营 · {window} 个交易日最大回撤",
            "kind": "market_data",
            "status": "degraded",
            "summary": None,
            "content": None,
            "metrics": [],
            "items": [],
            "table": None,
            "warnings": [warning],
            "provenance": {
                "source": "Alpaca Market Data",
                "as_of": None,
                "generated_by": "rolling_peak_drawdown",
            },
        }
