from __future__ import annotations

import json

import pytest

from intelligence.api.daily_reports import (
    project_daily_agent,
    project_daily_review_html,
    project_daily_review_markdown,
)


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
