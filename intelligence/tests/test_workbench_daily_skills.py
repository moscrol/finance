from __future__ import annotations

import json
from pathlib import Path

import pytest

from intelligence.services.query_understanding import (
    market_review_requested_date,
)
from intelligence.services.run_store import RunStore
from intelligence.workbench_skills.contracts import SkillExecutionContext
from intelligence.workbench_skills.daily_agent import DailyAgentSkill
from intelligence.workbench_skills.daily_review import DailyReviewSkill
from intelligence.workbench_skills.registry import SKILL_EXECUTORS, SKILL_REGISTRY


def _context(
    tmp_path: Path,
    store: RunStore,
    run_id: str,
    query: str = "今天市场怎么样？",
) -> SkillExecutionContext:
    return SkillExecutionContext(
        query=query,
        task_type="daily",
        user_id="demo",
        run_id=run_id,
        conversation_id="conversation-1",
        repo_root=tmp_path,
        run_store=store,
    )


def _write_daily_review(root: Path, date: str = "2026-07-10") -> Path:
    exports = root / "market_feature_store" / "exports"
    exports.mkdir(parents=True, exist_ok=True)
    path = exports / f"{date}-daily-review.md"
    path.write_text(
        f"""# {date} 每日市场复盘

## 核心看板
| 维度 | 结论 |
|---|---|
| 市场性质 | 普通交易日 / 修复阶段 |
| 指数表现 | 上证上涨 0.8% |
| 量能状态 | 成交额 18000 亿 |
| 题材量能 | 双红主线：算力 |

## 14. 数据覆盖检查
| 表 | 状态 |
|---|---|
| fact_market_daily | OK |
| fact_stock_daily | 缺目标日 |

## 15. 市场环境总评
> 修复延续，下一交易日验证量能。
""",
        encoding="utf-8",
    )
    return path


def _write_daily_agent(root: Path, date: str = "2026-07-10") -> Path:
    exports = root / "market_feature_store" / "exports"
    exports.mkdir(parents=True, exist_ok=True)
    path = exports / f"{date}-daily-agent.json"
    path.write_text(
        json.dumps(
            {
                "date": date,
                "generated_at": f"{date}T20:00:00+08:00",
                "decision": {
                    "old_logic_wakeup": [
                        {
                            "matched_theme": "氢能源",
                            "priority_score": 194.57,
                            "strong_stocks": ["金宏气体"],
                            "logic_lifecycle": {
                                "生命周期阶段": "旧逻辑唤醒",
                                "阶段变化": "旧材料唤醒",
                            },
                            "research_judgment": {
                                "证据状态": "旧逻辑待验证",
                                "缺失证据层": ["L3 官方验证"],
                                "建议动作": "查公告和订单。",
                            },
                            "market_validation": {
                                "验证结论": "盘面共振，但仍需官方事实确认。"
                            },
                        }
                    ],
                    "new_logic_candidate": [],
                    "data_gap": [],
                    "noise_or_unconfirmed": [],
                },
                "research_queue": {
                    "today_do_ima": [],
                    "today_find_official_evidence": [
                        {
                            "目标": "氢能源",
                            "理由": "旧逻辑需要官方事实确认。",
                            "优先级": 194.57,
                            "生命周期阶段": "旧逻辑唤醒",
                            "证据状态": "旧逻辑待验证",
                            "强势股": ["金宏气体"],
                            "建议动作": "查公告和订单。",
                        }
                    ],
                    "today_wait_market_validation": [],
                    "today_downgrade_or_watch": [],
                    "summary": {
                        "today_do_ima": 0,
                        "today_find_official_evidence": 1,
                        "today_wait_market_validation": 0,
                        "today_downgrade_or_watch": 0,
                        "total": 1,
                    },
                },
                "notes": ["只读研究入口，不自动交易。"],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return path


def test_daily_review_skill_preserves_canonical_values_and_artifact(
    tmp_path: Path,
    monkeypatch,
) -> None:
    # 把盘面库钉在不存在的路径上。这个用例断言的是 fixture 日报的逐字保真，而知识库
    # 那条腿走 default_market_db_path()，不钉住就会在设了 FINANCE_WS 的服务配置下
    # 读到真实生产库、多出一条引用——本地跑绿、服务配置跑红。
    monkeypatch.setenv("MARKET_FEATURE_STORE_DB", str(tmp_path / "absent.duckdb"))
    source = _write_daily_review(tmp_path)
    store = RunStore(user_id="demo", root=tmp_path / "runs")
    run = store.create_run("今天市场怎么样？", "daily")

    output = DailyReviewSkill().execute(_context(tmp_path, store, run.run_id))

    assert output.skill_id == "daily-review"
    assert output.as_of == "2026-07-10"
    assert output.warnings == []
    assert output.modules[0]["metrics"][0] == {
        "label": "指数表现",
        "value": "上证上涨 0.8%",
    }
    assert any(
        item["summary"] == "个股日行情数据：缺目标日"
        for module in output.modules
        for item in module.get("items", [])
    )
    assert output.citations == [
        {
            "source": source.relative_to(tmp_path).as_posix(),
            "title": "本地正式日报",
            "evidence_layer": "canonical",
            "as_of": "2026-07-10",
        }
    ]
    assert output.raw_result_ref == "daily-review-skill-result.json"
    assert output.answer_contract is not None
    assert output.answer_contract.retrieval_plan == (
        "读取最新 canonical 正式日报",
    )
    artifact = json.loads(
        (store.run_dir(run.run_id) / output.raw_result_ref).read_text(encoding="utf-8")
    )
    assert artifact["as_of"] == "2026-07-10"
    assert artifact["modules"] == output.modules


def test_daily_review_skill_reads_the_date_requested_by_user(tmp_path: Path) -> None:
    _write_daily_review(tmp_path, "2026-07-15")
    requested = _write_daily_review(tmp_path, "2026-07-16")
    store = RunStore(user_id="demo", root=tmp_path / "runs")
    run = store.create_run("总结一下 2026年7月16日 的行情", "daily")

    output = DailyReviewSkill().execute(
        _context(
            tmp_path,
            store,
            run.run_id,
            query="总结一下 2026年7月16日 的行情",
        )
    )

    assert output.as_of == "2026-07-16"
    assert output.citations[0]["source"] == requested.relative_to(tmp_path).as_posix()
    assert output.answer_contract is not None
    assert output.answer_contract.retrieval_plan == (
        "读取 2026-07-16 的 canonical 正式日报",
    )


def test_daily_review_skill_normalizes_yearless_requested_date(tmp_path: Path) -> None:
    query = "总结一下7.16的行情"
    requested_iso = market_review_requested_date(query)
    assert requested_iso is not None
    _write_daily_review(tmp_path, requested_iso)
    store = RunStore(user_id="demo", root=tmp_path / "runs")
    run = store.create_run(query, "daily")

    output = DailyReviewSkill().execute(
        _context(tmp_path, store, run.run_id, query=query)
    )

    assert output.as_of == requested_iso
    assert output.answer_contract is not None
    assert output.answer_contract.retrieval_plan == (
        f"读取 {requested_iso} 的 canonical 正式日报",
    )


def test_daily_review_skill_fails_closed_when_yearless_date_report_missing(
    tmp_path: Path,
) -> None:
    _write_daily_review(tmp_path, "2020-01-02")
    store = RunStore(user_id="demo", root=tmp_path / "runs")
    query = "总结一下7.16的行情"
    run = store.create_run(query, "daily")

    output = DailyReviewSkill().execute(
        _context(tmp_path, store, run.run_id, query=query)
    )

    assert output.as_of is None
    assert output.citations == []
    assert any("未找到" in warning for warning in output.warnings)


def test_daily_agent_skill_projects_summary_actions_evidence_and_provenance(
    tmp_path: Path,
) -> None:
    source = _write_daily_agent(tmp_path)
    store = RunStore(user_id="demo", root=tmp_path / "runs")
    run = store.create_run("今天研究什么？", "ask")

    output = DailyAgentSkill().execute(_context(tmp_path, store, run.run_id))

    assert output.skill_id == "daily-agent"
    assert output.as_of == "2026-07-10"
    assert output.warnings == ["只读研究入口，不自动交易。"]
    assert [module["kind"] for module in output.modules] == [
        "summary",
        "list",
        "actions",
        "evidence",
    ]
    assert output.modules[0]["metrics"][0] == {
        "label": "旧逻辑重新活跃",
        "value": "1",
        "tone": "attention",
    }
    assert output.modules[1]["items"][0]["title"] == "氢能源"
    assert output.modules[2]["items"][0]["next_action"] == "查公告和订单。"
    assert "L3 官方验证" in output.modules[3]["items"][0]["summary"]
    assert output.citations[0]["source"] == source.relative_to(tmp_path).as_posix()
    assert output.raw_result_ref == "daily-agent-skill-result.json"
    assert output.answer_contract is not None
    assert output.answer_contract.output_contract == (
        "先裁决研究优先级，再给证据缺口和可执行核验动作",
    )
    artifact = json.loads(
        (store.run_dir(run.run_id) / output.raw_result_ref).read_text(encoding="utf-8")
    )
    assert artifact["projection"]["date"] == "2026-07-10"
    assert artifact["projection"]["metrics"][0]["value"] == "1"


@pytest.mark.parametrize(
    ("executor", "suffix"),
    [
        (DailyReviewSkill(), "daily-review.html"),
        (DailyAgentSkill(), "daily-agent.html"),
    ],
)
def test_daily_skills_do_not_fallback_to_html(
    tmp_path: Path, executor: DailyReviewSkill | DailyAgentSkill, suffix: str
) -> None:
    daily_dir = tmp_path / "复盘" / "daily" / "2026-07-10"
    daily_dir.mkdir(parents=True)
    (daily_dir / f"2026-07-10-{suffix}").write_text(
        "<h1>must not migrate</h1>", encoding="utf-8"
    )
    store = RunStore(user_id="demo", root=tmp_path / "runs")
    run = store.create_run("q", "ask")

    output = executor.execute(_context(tmp_path, store, run.run_id))

    assert output.modules == []
    assert output.citations == []
    assert output.raw_result_ref is None
    assert output.as_of is None
    assert output.warnings
    assert "HTML" not in json.dumps(output.modules, ensure_ascii=False)


def test_daily_agent_invalid_json_degrades_without_artifact(tmp_path: Path) -> None:
    exports = tmp_path / "market_feature_store" / "exports"
    exports.mkdir(parents=True)
    (exports / "2026-07-10-daily-agent.json").write_text("{", encoding="utf-8")
    store = RunStore(user_id="demo", root=tmp_path / "runs")
    run = store.create_run("q", "ask")

    output = DailyAgentSkill().execute(_context(tmp_path, store, run.run_id))

    assert output.modules == []
    assert output.raw_result_ref is None
    assert output.warnings == ["canonical Daily Agent JSON 无法读取。"]


def test_skill_artifacts_and_visible_values_are_redacted(tmp_path: Path) -> None:
    source = _write_daily_agent(tmp_path)
    payload = json.loads(source.read_text(encoding="utf-8"))
    payload["notes"] = ["token=super-secret-value"]
    source.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    store = RunStore(user_id="demo", root=tmp_path / "runs")
    run = store.create_run("q", "ask")

    output = DailyAgentSkill().execute(_context(tmp_path, store, run.run_id))
    persisted = (store.run_dir(run.run_id) / output.raw_result_ref).read_text(
        encoding="utf-8"
    )

    assert output.warnings == ["[REDACTED]"]
    assert "super-secret-value" not in persisted
    assert "[REDACTED]" in persisted


def test_daily_skills_are_registered_as_local_read_executors() -> None:
    expected = [
        "daily-review",
        "daily-agent",
        "us-ai-drawdown",
        "stock-deep-dive",
        "theme-research",
        "news-impact",
        "financial-analysis",
    ]
    assert list(SKILL_REGISTRY) == expected
    assert list(SKILL_EXECUTORS) == expected
    for skill_id in expected:
        assert SKILL_EXECUTORS[skill_id].skill_id == skill_id
    assert SKILL_REGISTRY["us-ai-drawdown"].permissions == (
        "local_read",
        "network_read",
    )
    for skill_id in set(expected) - {"us-ai-drawdown"}:
        assert SKILL_REGISTRY[skill_id].permissions == ("local_read",)


# --- 按问题意图选章节（2026-08-01 A 组基线，任务 #12）------------------------
#
# A 组实测：路由修好之后 A6「连板梯队什么情况，有没有断层」确实走到了 daily-review、
# 也取到了 2026-07-23 的数据，但吐的是通用「每日市场复盘」模板——涨停方向、强势股
# 那几段，一个字没碰连板。
# 根因不在 output_contract，在更上游：daily_projection_modules 把 43,481 字的正式
# 日报压成 3,609 字的四个固定模块，「连板」「断层」「立新能源」在模块里出现 0 次。
# 而正式日报的「## 11. 3板及以上个股」里，立新能源 6 连板、梯队 6→4→3（缺 5 板，
# 断层肉眼可见）全都在。信息在系统里，又一次没送到。
#
# daily_projection_modules 被工作台 UI（api/app.py）共用，不动它；这里加一条
# 按问题意图选章节的附加腿。

_LADDER_MD = """## 11. 3板及以上个股
| 股票 | 代码 | 连板数 | 首板日期 | 题材 | 涨幅 |
|---|---|---|---|---|---|
| 立新能源 | 001258.SZ | 6 | 2026-07-16 | 电站 | 9.99% |
| 美利云 | 000815.SZ | 4 | 2026-07-20 | 算力租赁 | 9.98% |

> **结论**：3板及以上个股 6 只，最高连板 6 板。
"""

_STRENGTH_MD = """## 12. 市场强度
| 指标 | 值 |
|---|---|
| 强度状态 | 沸点 |
| 边际变化 | -66.3% |
"""


def _write_rich_review(root: Path, date: str = "2026-07-10") -> Path:
    exports = root / "market_feature_store" / "exports"
    exports.mkdir(parents=True, exist_ok=True)
    path = exports / f"{date}-daily-review.md"
    path.write_text(
        f"# {date} 每日市场复盘\n\n"
        "## 核心看板\n| 维度 | 结论 |\n|---|---|\n| 指数表现 | 上证上涨 0.8% |\n\n"
        f"{_LADDER_MD}\n{_STRENGTH_MD}\n"
        "## 15. 市场环境总评\n> 修复延续。\n",
        encoding="utf-8",
    )
    return path


def test_ladder_question_selects_the_ladder_section() -> None:
    from intelligence.workbench_skills.daily_review import select_review_sections

    markdown = f"# 日报\n\n{_LADDER_MD}\n{_STRENGTH_MD}\n"
    sections, warnings = select_review_sections(
        markdown, "2026-07-23 连板梯队什么情况，有没有断层"
    )

    joined = "\n".join(s["body"] for s in sections)
    assert "立新能源" in joined, f"连板题没选到连板章节：{[s['heading'] for s in sections]}"
    assert "6" in joined
    assert warnings == []


def test_strength_question_selects_the_strength_section() -> None:
    from intelligence.workbench_skills.daily_review import select_review_sections

    markdown = f"# 日报\n\n{_LADDER_MD}\n{_STRENGTH_MD}\n"
    sections, _ = select_review_sections(markdown, "2026-07-23 的市场情绪怎么解读")

    joined = "\n".join(s["body"] for s in sections)
    assert "沸点" in joined and "-66.3" in joined


def test_generic_market_question_selects_nothing_extra() -> None:
    """泛问「今天市场怎么样」不该拖章节进来——通用模板本来就够，多拖是浪费预算。"""
    from intelligence.workbench_skills.daily_review import select_review_sections

    markdown = f"# 日报\n\n{_LADDER_MD}\n{_STRENGTH_MD}\n"
    sections, _ = select_review_sections(markdown, "今天市场怎么样")

    assert sections == []


def test_oversized_section_is_truncated_with_disclosure() -> None:
    """章节超预算要截断，且必须留证——截断留证是本项目反复钉的纪律。"""
    from intelligence.workbench_skills.daily_review import select_review_sections

    big = "## 11. 3板及以上个股\n" + ("| 立新能源 | 6 |\n" * 4000)
    sections, warnings = select_review_sections(big, "连板梯队怎么样", budget=500)

    assert sections and len(sections[0]["body"]) <= 600
    assert warnings, "截断了却一句不说"
    assert any("截断" in w for w in warnings)


def test_subtopic_sections_reach_the_skill_output_and_contract(tmp_path: Path) -> None:
    """只测组件不测送达 = 没测：章节要真进 skill 的 modules，且 contract 要求回答它。"""
    _write_rich_review(tmp_path, "2026-07-10")
    store = RunStore(user_id="demo", root=tmp_path / "runs")
    run = store.create_run("连板", "daily")

    output = DailyReviewSkill().execute(
        _context(
            tmp_path,
            store,
            run.run_id,
            query="2026-07-10 连板梯队什么情况，有没有断层",
        )
    )

    # 断言点必须是**模型真正看到的那份文本**，不是 modules 的原始 JSON。
    # 第一版这里断言 json.dumps(output.modules)，绿了——但正文塞在 items[].content，
    # 而序列化器只读 items[].title/summary，模型收到的只有标题。线上实测答案原话：
    # 「知道日报里有这张表、但看不到表里任何一行数据」。
    # 又一次「只测组件不测送达」，这次是自己踩的。
    assert output.answer_contract is not None
    delivered = "\n".join(
        claim.text for claim in output.answer_contract.answer_spec.verified_facts
    )
    assert "立新能源" in delivered, (
        f"连板章节正文没送到模型上下文——模型看不到就答不出。实际={delivered[:400]}"
    )
    assert output.answer_contract is not None
    contract_text = " ".join(output.answer_contract.output_contract)
    assert "连板" in contract_text or "问题" in contract_text, (
        f"output_contract 没要求回答用户问的那件事：{contract_text}"
    )
