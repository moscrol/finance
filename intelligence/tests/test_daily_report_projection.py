from __future__ import annotations

import json

import pytest

from intelligence.api.daily_reports import (
    project_daily_agent,
    project_daily_review_html,
    project_daily_review_json,
    project_daily_review_markdown,
)


def _daily_review_json_payload() -> dict[str, object]:
    """台账 JSON 真本源的缩样：三节覆盖 note / heading / table / conclusion 四种 block。"""
    return {
        "schema": "daily-review/v1",
        "trade_date": "2026-09-02",
        "generated_at": "2026-09-02 20:40:05",
        "warnings": ["申万一级实时源当日缺数，3/31 行使用聚合代理。"],
        "core_board": [
            {"dimension": "市场性质", "conclusion": "普通交易日 / 底部横盘阶段 第26天"},
            {"dimension": "指数表现", "conclusion": "上证 3941.386，涨幅 -0.97%，偏离度 -0.55%"},
            {"dimension": "情绪状态", "conclusion": "涨家数 1541，MA5 2903.2，涨停 52，跌停 8"},
            {"dimension": "涨停方向", "conclusion": "核心涨停题材：储能(15)、新能源车(15)"},
            {"dimension": "强度状态", "conclusion": "强势，强度加权涨幅 6.72%，强度成交占比 7.00%"},
        ],
        "facts": {"ma5_position": "震荡区间", "price_day": False},
        "sections": [
            {
                "id": "sentiment",
                "index": 2,
                "title": "市场情绪",
                "blocks": [
                    {
                        "kind": "table",
                        "title": None,
                        "columns": ["项目", "今日", "昨日"],
                        "rows": [["涨家数", 1541, 3387], ["涨停", 52, 83]],
                    },
                    {
                        "kind": "table",
                        "title": "涨家数 MA5 波段区间",
                        "columns": ["区间", "日期区间", "状态"],
                        "rows": [["波谷→波峰", "2026-08-19→2026-08-31", "上升"]],
                    },
                    {"kind": "note", "text": "**MA5位置**：当前处于 **震荡区间**，趋势为 **震荡**。"},
                    {"kind": "conclusion", "text": "涨家数 1541，MA5 2903.2；涨停较昨日减少31只。"},
                ],
            },
            {
                "id": "limit_up",
                "index": 10,
                "title": "涨停题材",
                "blocks": [
                    {"kind": "heading", "text": "近15日子板块涨停矩阵"},
                    {"kind": "note", "text": "单元格为当日涨停的去重个股数。"},
                    {"kind": "heading", "text": "电子"},
                    {
                        "kind": "table",
                        "title": None,
                        "columns": ["题材", "09-01", "09-02"],
                        "rows": [["芯片", 5, 11]],
                    },
                    {
                        "kind": "table",
                        "title": "当日涨停题材 Top20",
                        "columns": ["题材", "涨停数"],
                        "rows": [["储能", 15]],
                    },
                    {"kind": "conclusion", "text": "涨停题材核心集中在 储能、新能源车。"},
                ],
            },
            {
                "id": "limit_advance",
                "index": 11,
                "title": "3板及以上个股",
                "blocks": [
                    {
                        "kind": "table",
                        "title": None,
                        "columns": ["股票", "连板数", "首板日期"],
                        "rows": [["国芳集团", 4, "2026-08-28"]],
                    },
                    {"kind": "conclusion", "text": "3板及以上个股 6 只，最高连板 4 板。"},
                ],
            },
            {
                "id": "coverage",
                "index": 14,
                "title": "数据覆盖检查",
                "blocks": [
                    {
                        "kind": "table",
                        "title": None,
                        "columns": ["表", "最新日期", "总行数", "目标日行数", "状态"],
                        "rows": [
                            ["fact_market_daily", "2026-09-02", 413, 1, "OK"],
                            ["fact_stock_daily", "2026-09-01", 100, 0, "缺目标日"],
                        ],
                    }
                ],
            },
        ],
        "assessment": "2026-09-02 市场性质为 **普通交易日**，主线集中在 国防军工 相关方向。",
    }


def _daily_agent_payload() -> dict[str, object]:
    candidate = {
        "matched_theme": "氢能源",
        "priority_score": 194.57,
        "strong_stocks": ["金宏气体", "昊华科技"],
        "logic_lifecycle": {
            "生命周期阶段": "旧逻辑唤醒",
            "阶段变化": "旧材料唤醒",
        },
        "research_judgment": {
            "证据状态": "旧逻辑待验证",
            "缺失证据层": ["L2 基线", "L3 官方验证"],
            "建议动作": "查公告、调研纪要和订单验证。",
        },
        "market_validation": {
            "验证结论": "多信号共振，但仍需官方事实确认。",
        },
    }
    return {
        "date": "2026-07-01",
        "generated_at": "2026-07-01T20:28:58+08:00",
        "decision": {
            "old_logic_wakeup": [candidate],
            "new_logic_candidate": [],
            "data_gap": [],
            "noise_or_unconfirmed": [],
        },
        "research_queue": {
            "today_do_ima": [
                {
                    "目标": "风电",
                    "动作": "今日该做 IMA",
                    "理由": "盘面触发但缺少基线材料。",
                    "优先级": 188.62,
                    "生命周期阶段": "升温验证",
                    "证据状态": "盘面触发待解释",
                    "强势股": ["大唐发电"],
                    "建议动作": "补齐题材边界和核心公司。",
                }
            ],
            "today_find_official_evidence": [
                {
                    "目标": "氢能源",
                    "动作": "今日该找公告/调研/订单",
                    "理由": "旧逻辑需要官方事实确认。",
                    "优先级": 194.57,
                    "生命周期阶段": "旧逻辑唤醒",
                    "证据状态": "旧逻辑待验证",
                    "强势股": ["金宏气体"],
                    "建议动作": "查公告、调研纪要和订单。",
                }
            ],
            "today_wait_market_validation": [],
            "today_downgrade_or_watch": [],
            "summary": {
                "today_do_ima": 1,
                "today_find_official_evidence": 1,
                "today_wait_market_validation": 0,
                "today_downgrade_or_watch": 0,
                "total": 2,
            },
        },
        "notes": ["报告为只读研究入口，不自动执行交易。"],
    }


def test_project_daily_agent_translates_internal_schema() -> None:
    projection = project_daily_agent(
        _daily_agent_payload(),
        source_path="market_feature_store/exports/2026-07-01-daily-agent.json",
    )

    assert projection["report_type"] == "daily_agent"
    assert projection["source_mode"] == "canonical_json"
    assert projection["metrics"][0] == {
        "label": "旧逻辑重新活跃",
        "value": "1",
        "tone": "attention",
    }
    assert any("今日研究队列共 2 项" in item for item in projection["plain_summary"])
    assert len(projection["plain_summary"]) <= 3

    focus = next(section for section in projection["sections"] if section["title"] == "值得关注")
    assert focus["items"][0]["title"] == "氢能源"
    assert "旧逻辑唤醒" in focus["items"][0]["badges"]
    assert "旧逻辑待验证" in focus["items"][0]["badges"]

    actions = next(section for section in projection["sections"] if section["title"] == "今天要做什么")
    assert [item["title"] for item in actions["items"]] == ["氢能源", "风电"]
    assert any(item["term"] == "L3" for item in projection["glossary"])
    assert projection["provenance"]["canonical_path"].endswith("2026-07-01-daily-agent.json")
    assert "old_logic_wakeup" not in json.dumps(projection, ensure_ascii=False)
    assert "today_find_official_evidence" not in json.dumps(projection, ensure_ascii=False)


def test_project_daily_agent_rejects_payload_without_report_data() -> None:
    with pytest.raises(ValueError, match="Daily Agent"):
        project_daily_agent({}, source_path="empty.json")


def test_project_daily_review_markdown_extracts_bounded_sections() -> None:
    source = """# 2026-07-01 每日市场复盘

> ⚠️ 数据降级：31/31 行使用复盘会聚合代理，不可等同于申万指数官方口径。

## 核心看板
| 维度 | 结论 |
|---|---|
| 市场性质 | 普通交易日 / 底部横盘阶段 第2天 |
| 指数表现 | 上证 4112.445，涨幅 0.44% |
| 量能状态 | 成交额 36397.84亿，较昨日 11.19% |
| 情绪状态 | 涨家数 4240，涨停 148，跌停 7 |
| 题材量能 | 双红主线：计算机、电力设备 |
| 涨停方向 | 机器人概念、芯片概念 |
| 强度状态 | 沸点 |

## 未知内部诊断
不要公开这段调试信息。

## 14. 数据覆盖检查
| 表 | 状态 |
|---|---|
| fact_market_daily | OK |
| fact_stock_daily | 缺目标日 |

## 15. 市场环境总评
> 市场处于底部横盘阶段，量能回升；下一交易日重点验证主线能否扩散。
"""
    projection = project_daily_review_markdown(
        source,
        source_path="复盘/daily/2026-07-01/2026-07-01-daily-review.md",
        date="2026-07-01",
    )

    assert projection["report_type"] == "daily_review"
    assert projection["source_mode"] == "canonical_markdown"
    assert projection["metrics"][0]["label"] == "指数表现"
    assert any("底部横盘阶段" in item for item in projection["plain_summary"])
    risk = next(section for section in projection["sections"] if section["title"] == "风险与验证")
    assert any(item["title"] == "市场环境判断" for item in risk["items"])
    assert any("缺目标日" in item["summary"] for item in risk["items"])
    assert any(
        "不可等同于申万指数官方口径" in warning
        for warning in projection["provenance"]["warnings"]
    )
    rendered = json.dumps(projection, ensure_ascii=False)
    assert "未知内部诊断" not in rendered
    assert "调试信息" not in rendered


def test_project_daily_review_markdown_does_not_leak_wide_table_headers() -> None:
    """五列覆盖表的表头此前漏成一条「表：状态」覆盖提醒——按分隔行识别表头。"""
    source = """# 2026-09-02 每日市场复盘

## 核心看板
| 维度 | 结论 |
|---|---|
| 市场性质 | 普通交易日 |

## 14. 数据覆盖检查
| 表 | 最新日期 | 总行数 | 目标日行数 | 状态 |
|---|---|---|---|---|
| fact_market_daily | 2026-09-02 | 413 | 1 | OK |
"""
    projection = project_daily_review_markdown(
        source, source_path="exports/2026-09-02-daily-review.md", date="2026-09-02"
    )

    risk = next(section for section in projection["sections"] if section["title"] == "风险与验证")
    assert all(item["title"] != "数据覆盖提醒" for item in risk["items"])
    assert "表：状态" not in json.dumps(projection, ensure_ascii=False)


def test_project_daily_review_json_keeps_core_board_and_carries_every_table() -> None:
    payload = _daily_review_json_payload()

    projection = project_daily_review_json(
        payload,
        source_path="market_feature_store/exports/2026-09-02-daily-review.json",
        date="2026-09-02",
    )

    assert projection["source_mode"] == "canonical_json"
    assert projection["date"] == "2026-09-02"
    assert projection["provenance"]["generated_at"] == "2026-09-02 20:40:05"
    # 核心看板那一层与 md 路径同形：老前端/聊天答案不用改就能读。
    assert [metric["label"] for metric in projection["metrics"]] == [
        "指数表现",
        "情绪状态",
        "强度状态",
    ]
    titles = [section["title"] for section in projection["sections"]]
    assert titles[:3] == ["主要方向", "风险与验证", "专业数据"]
    assert titles[3:] == ["情绪层", "板块双坐标", "个股载体", "数据覆盖"]

    sentiment = next(s for s in projection["sections"] if s["title"] == "情绪层")
    assert [table["title"] for table in sentiment["tables"]] == [
        "市场情绪",
        "市场情绪 · 涨家数 MA5 波段区间",
    ]
    assert sentiment["tables"][0]["rows"][0] == ["涨家数", 1541, 3387]
    (item,) = sentiment["items"]
    assert item["badges"] == ["§2"]
    assert item["summary"] == "涨家数 1541，MA5 2903.2；涨停较昨日减少31只。"
    assert item["details"] == ["MA5位置：当前处于 震荡区间，趋势为 震荡。"]

    sector = next(s for s in projection["sections"] if s["title"] == "板块双坐标")
    # 矩阵表没有自己的标题，用紧挨着的 ### 小标题（申万一级名）命名。
    assert [table["title"] for table in sector["tables"]] == [
        "涨停题材 · 电子",
        "涨停题材 · 当日涨停题材 Top20",
    ]

    stock = next(s for s in projection["sections"] if s["title"] == "个股载体")
    assert stock["tables"][0]["columns"] == ["股票", "连板数", "首板日期"]
    assert stock["items"][0]["summary"] == "3板及以上个股 6 只，最高连板 4 板。"

    coverage = next(s for s in projection["sections"] if s["title"] == "数据覆盖")
    assert coverage["items"] == []
    assert len(coverage["tables"]) == 1

    risk = next(s for s in projection["sections"] if s["title"] == "风险与验证")
    assert any("fact_stock_daily：缺目标日" in item["summary"] for item in risk["items"])
    assert any(
        "3/31 行使用聚合代理" in warning for warning in projection["provenance"]["warnings"]
    )


def test_project_daily_review_json_rejects_payload_without_report_data() -> None:
    with pytest.raises(ValueError, match="Daily Review JSON"):
        project_daily_review_json({"schema": "daily-review/v1"}, source_path="x.json", date=None)


def test_project_daily_review_html_extracts_only_known_sections() -> None:
    source = """<!doctype html><html><body>
<h2 id="核心看板">核心看板</h2>
<table><tr><th>维度</th><th>结论</th></tr>
<tr><td>市场性质</td><td>普通交易日 / 上升阶段</td></tr>
<tr><td>指数表现</td><td>上证上涨 1.2%</td></tr>
<tr><td>涨停方向</td><td>机器人、算力</td></tr></table>
<h2>秘密调试章节</h2><p>unknown-secret</p>
<h2 id="15-市场环境总评">15. 市场环境总评</h2>
<blockquote><p>市场强度回升，但成交集中度仍需验证。</p></blockquote>
<script>window.secret = "script-secret";</script>
</body></html>"""
    projection = project_daily_review_html(
        source,
        source_path="复盘/daily/2026-07-01/2026-07-01-daily-review.html",
        date="2026-07-01",
    )

    assert projection["source_mode"] == "legacy_html_projection"
    assert projection["metrics"][0]["value"] == "上证上涨 1.2%"
    assert any("兼容投影" in warning for warning in projection["provenance"]["warnings"])
    assert projection["provenance"]["rendered_path"].endswith("daily-review.html")
    rendered = json.dumps(projection, ensure_ascii=False)
    assert "成交集中度仍需验证" in rendered
    assert "unknown-secret" not in rendered
    assert "script-secret" not in rendered
