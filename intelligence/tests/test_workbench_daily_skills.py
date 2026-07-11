from __future__ import annotations

import json
from pathlib import Path

import pytest

from intelligence.services.run_store import RunStore
from intelligence.workbench_skills.contracts import SkillExecutionContext
from intelligence.workbench_skills.daily_agent import DailyAgentSkill
from intelligence.workbench_skills.daily_review import DailyReviewSkill
from intelligence.workbench_skills.registry import SKILL_EXECUTORS, SKILL_REGISTRY


def _context(tmp_path: Path, store: RunStore, run_id: str) -> SkillExecutionContext:
    return SkillExecutionContext(
        query="今天市场怎么样？",
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


def test_daily_review_skill_preserves_canonical_values_and_artifact(tmp_path: Path) -> None:
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
        item["summary"] == "fact_stock_daily：缺目标日"
        for module in output.modules
        for item in module.get("items", [])
    )
    assert output.citations == [
        {
            "source": source.relative_to(tmp_path).as_posix(),
            "title": "Canonical Daily Review",
            "evidence_layer": "canonical",
            "as_of": "2026-07-10",
        }
    ]
    assert output.raw_result_ref == "daily-review-skill-result.json"
    artifact = json.loads(
        (store.run_dir(run.run_id) / output.raw_result_ref).read_text(encoding="utf-8")
    )
    assert artifact["as_of"] == "2026-07-10"
    assert artifact["modules"] == output.modules


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
    assert list(SKILL_REGISTRY) == ["daily-review", "daily-agent"]
    assert list(SKILL_EXECUTORS) == ["daily-review", "daily-agent"]
    assert SKILL_REGISTRY["daily-review"].permissions == ("local_read",)
    assert SKILL_REGISTRY["daily-agent"].permissions == ("local_read",)
    assert SKILL_EXECUTORS["daily-review"].skill_id == "daily-review"
    assert SKILL_EXECUTORS["daily-agent"].skill_id == "daily-agent"
