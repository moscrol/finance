from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from intelligence.services.forecast_learning import (
    approve_reflection,
    render_learning_prompt,
    set_rule_status,
    sync_reflections,
    sync_rule_candidates,
)


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _ledger(tmp_path: Path) -> tuple[Path, Path]:
    ledger = tmp_path / "forecast-review-ledger"
    learning = tmp_path / "forecast-lessons"
    _write(
        ledger / "2026-07-01.answer.codex.json",
        {
            "date": "2026-07-01",
            "agent": "codex",
            "source": "duckdb",
            "stage": "轮动",
            "main_judgment": "半导体扩散",
            "direction_ranking": ["半导体", "机器人"],
            "thresholds": {"direction": "半导体强于机器人"},
            "hypotheses": [
                {
                    "id": "direction:semi",
                    "category": "direction",
                    "claim": "半导体强于机器人",
                    "evidence_refs": ["M1"],
                }
            ],
            "evidence_catalog": {"M1": {"field": "diff", "value": 5}},
        },
    )
    _write(
        ledger / "2026-07-01.verdict.json",
        {
            "date": "2026-07-01",
            "verdicts": [
                {
                    "id": "direction:semi",
                    "agent": "codex",
                    "stream": "盘面",
                    "horizon": "T+1",
                    "verdict": "miss",
                    "actual": "机器人强于半导体",
                    "failure_mode": "机判待人工归因",
                }
            ],
        },
    )
    return ledger, learning


def test_reflection_sync_is_idempotent_and_degrades_without_llm(tmp_path: Path) -> None:
    ledger, learning = _ledger(tmp_path)
    first = sync_reflections(ledger, learning, use_llm=False)
    second = sync_reflections(ledger, learning, use_llm=False)

    assert first["created"] == 1
    assert first["pending"] == 1
    assert first["orphaned"] == []
    assert second["skipped"] == 1
    payload = json.loads(
        next((learning / "reflections").glob("*.json")).read_text(encoding="utf-8")
    )
    assert payload["status"] == "pending_llm"
    assert payload["reflections"][0]["category"] == "direction"
    assert payload["reflections"][0]["actual"] == "机器人强于半导体"


def test_llm_reflection_requires_approval_before_prompt_injection(tmp_path: Path) -> None:
    ledger, learning = _ledger(tmp_path)

    def fake_complete(*_args, **_kwargs):
        return (
            json.dumps(
                {
                    "reflections": [
                        {
                            "id": "direction:semi",
                            "failure_mode": "A5 场景错位",
                            "diagnosis": "轮动环境误当扩散",
                            "missed_signal": "机器人相对强度反转",
                            "ranking_error": "方向排序失真",
                            "correction": "先检查相对强度",
                            "reusable_lesson": "轮动期先比较方向相对强度再排序。",
                            "proposed_rule": "方向排序前必须列出同日相对强度。",
                        }
                    ]
                },
                ensure_ascii=False,
            ),
            SimpleNamespace(name="mock", model="mock-1"),
            "",
        )

    result = sync_reflections(ledger, learning, llm_complete=fake_complete)
    reflection = next((learning / "reflections").glob("*.json"))
    lessons = learning / "lessons.jsonl"
    rules = learning / "rule_candidates.jsonl"

    assert result["created"] == 1
    assert "轮动期" not in render_learning_prompt(lessons, rules)
    assert approve_reflection(reflection, lessons) == {"approved": 1, "skipped": 0}
    assert approve_reflection(reflection, lessons) == {"approved": 0, "skipped": 1}
    prompt = render_learning_prompt(lessons, rules)
    assert "轮动期先比较方向相对强度" in prompt
    assert "direction:semi" in prompt


def test_pending_llm_reflection_retries_when_provider_becomes_available(
    tmp_path: Path,
) -> None:
    ledger, learning = _ledger(tmp_path)
    sync_reflections(ledger, learning, use_llm=False)

    def fake_complete(*_args, **_kwargs):
        return (
            '{"reflections":[{"id":"direction:semi",'
            '"failure_mode":"A2 信息集不全",'
            '"reusable_lesson":"补相对强度。","proposed_rule":"先横比。"}]}',
            SimpleNamespace(name="mock", model="mock-1"),
            "",
        )

    result = sync_reflections(ledger, learning, llm_complete=fake_complete)
    payload = json.loads(
        next((learning / "reflections").glob("*.json")).read_text(encoding="utf-8")
    )
    assert result["updated"] == 1
    assert payload["status"] == "pending_review"
    assert payload["reflections"][0]["reusable_lesson"] == "补相对强度。"


def test_cross_stream_verdict_reuses_answer_that_contains_hypothesis(
    tmp_path: Path,
) -> None:
    ledger, learning = _ledger(tmp_path)
    verdict_path = ledger / "2026-07-01.verdict.json"
    verdict = json.loads(verdict_path.read_text(encoding="utf-8"))
    verdict["verdicts"][0]["stream"] = "晨汇"
    verdict_path.write_text(json.dumps(verdict, ensure_ascii=False), encoding="utf-8")

    result = sync_reflections(ledger, learning, use_llm=False)

    assert result["errors"] == []
    reflection = next((learning / "reflections").glob("*.briefing.json"))
    payload = json.loads(reflection.read_text(encoding="utf-8"))
    assert payload["source"] == "briefing"
    assert payload["answer_ref"].endswith("2026-07-01.answer.codex.json")


def test_empty_reflection_cannot_be_approved(tmp_path: Path) -> None:
    ledger, learning = _ledger(tmp_path)
    sync_reflections(ledger, learning, use_llm=False)
    reflection = next((learning / "reflections").glob("*.json"))
    with pytest.raises(ValueError, match="尚无 reusable_lesson"):
        approve_reflection(reflection, learning / "lessons.jsonl")


def test_annotation_rules_are_pending_until_human_approval(tmp_path: Path) -> None:
    ledger = tmp_path / "forecast-review-ledger"
    ledger.mkdir()
    (ledger / "2026-07-02.md").write_text(
        """# 台账

## 8. 用户批注区

### 批注 1

- 问题：忽略相对强度
- 应该改成：先横向比较
- 下次硬规则：方向排序前必须比较至少三个候选的相对强度。

### 批注 2

- 问题：
- 应该改成：
- 下次硬规则：

<!-- BEGIN AUTO dual-blind-verdict -->
""",
        encoding="utf-8",
    )
    rules = tmp_path / "forecast-lessons" / "rule_candidates.jsonl"

    first = sync_rule_candidates(ledger, rules)
    second = sync_rule_candidates(ledger, rules)
    candidate = json.loads(rules.read_text(encoding="utf-8").splitlines()[0])

    assert first == {"created": 1, "skipped": 0}
    assert second == {"created": 0, "skipped": 1}
    assert "相对强度" not in render_learning_prompt(tmp_path / "none", rules)
    set_rule_status(rules, candidate["id"], "approved")
    line_count = len(rules.read_text(encoding="utf-8").splitlines())
    set_rule_status(rules, candidate["id"], "approved")
    assert len(rules.read_text(encoding="utf-8").splitlines()) == line_count
    assert "方向排序前必须比较至少三个候选" in render_learning_prompt(
        tmp_path / "none", rules
    )
