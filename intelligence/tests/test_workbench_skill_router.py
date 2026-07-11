from __future__ import annotations

from dataclasses import fields
from pathlib import Path

import pytest

from intelligence.services.run_store import RunStore
from intelligence.workbench_skills.contracts import (
    SkillDefinition,
    SkillExecutionContext,
    SkillOutput,
)
from intelligence.workbench_skills.registry import (
    SKILL_EXECUTORS,
    SKILL_REGISTRY,
    register_skill,
)
from intelligence.workbench_skills.router import route_skills


def definition(skill_id: str, *triggers: str) -> SkillDefinition:
    return SkillDefinition(
        skill_id=skill_id,
        name=f"Skill {skill_id}",
        description=f"Description for {skill_id}",
        version="1.0.0",
        triggers=triggers,
        input_schema={"type": "object"},
        permissions=("local_read",),
        timeout_seconds=30,
    )


class FakeExecutor:
    def __init__(self, skill_id: str) -> None:
        self.skill_id = skill_id

    def execute(self, context: SkillExecutionContext) -> SkillOutput:
        return SkillOutput(
            skill_id=self.skill_id,
            modules=[{"type": "summary", "query": context.query}],
            citations=[],
            warnings=[],
            as_of=None,
            raw_result_ref=None,
        )


def llm_response(payload: str):
    def complete(messages: list[dict[str, str]]):
        assert messages
        return payload, object(), ""

    return complete


def test_contract_fields_are_exact_and_context_supports_task5(tmp_path: Path) -> None:
    assert [field.name for field in fields(SkillDefinition)] == [
        "skill_id",
        "name",
        "description",
        "version",
        "triggers",
        "input_schema",
        "permissions",
        "timeout_seconds",
    ]
    assert [field.name for field in fields(SkillOutput)] == [
        "skill_id",
        "modules",
        "citations",
        "warnings",
        "as_of",
        "raw_result_ref",
    ]
    store = RunStore(root=tmp_path / "runs")
    context = SkillExecutionContext(
        query="今日复盘",
        task_type="daily_review",
        user_id="u1",
        run_id="run1",
        conversation_id="conv1",
        repo_root=tmp_path,
        run_store=store,
    )
    assert context.repo_root == tmp_path
    assert context.run_store is store
    assert FakeExecutor("daily").execute(context).skill_id == "daily"
    assert SkillExecutionContext(
        query="q",
        task_type="ask",
        user_id="u1",
        run_id="run1",
        conversation_id=None,
        repo_root=tmp_path,
        run_store=store,
    ).conversation_id is None


def test_global_registries_are_independent_dicts() -> None:
    assert isinstance(SKILL_REGISTRY, dict)
    assert isinstance(SKILL_EXECUTORS, dict)
    assert SKILL_REGISTRY is not SKILL_EXECUTORS


def test_register_skill_enforces_identity_duplicates_and_permissions() -> None:
    registry: dict[str, SkillDefinition] = {}
    executors: dict[str, FakeExecutor] = {}
    executor = FakeExecutor("daily")
    register_skill(definition("daily", "复盘"), executor, registry=registry, executors=executors)
    assert registry["daily"].name == "Skill daily"
    assert executors["daily"] is executor

    with pytest.raises(ValueError, match="duplicate"):
        register_skill(definition("daily"), executor, registry=registry, executors=executors)
    with pytest.raises(ValueError, match="mismatch"):
        register_skill(definition("other"), FakeExecutor("wrong"), registry={}, executors={})
    forbidden = definition("web")
    forbidden = SkillDefinition(**{**forbidden.__dict__, "permissions": ("local_read", "network")})
    with pytest.raises(ValueError, match="permission"):
        register_skill(forbidden, FakeExecutor("web"), registry={}, executors={})
    blank_trigger = definition("blank", " ")
    with pytest.raises(ValueError, match="triggers"):
        register_skill(blank_trigger, FakeExecutor("blank"), registry={}, executors={})


def test_unknown_manual_ids_and_more_than_three_distinct_manual_ids_are_rejected() -> None:
    registry = {name: definition(name) for name in ("a", "b", "c", "d")}
    with pytest.raises(ValueError, match="Unknown skill"):
        route_skills("q", "ask", "manual", ["missing"], registry=registry)
    with pytest.raises(ValueError, match="at most 3"):
        route_skills("q", "ask", "manual", ["a", "b", "c", "a", "d"], registry=registry)


def test_manual_mode_deduplicates_and_selects_only_manual_without_llm() -> None:
    registry = {"a": definition("a", "q"), "b": definition("b", "ask")}

    def forbidden_llm(messages: list[dict[str, str]]):
        raise AssertionError("manual mode must not call LLM")

    result = route_skills("q", "ask", "manual", ["b", "b", "a"], registry=registry, llm_complete=forbidden_llm)
    assert [(item.skill_id, item.selection_source) for item in result.selections] == [
        ("b", "manual"),
        ("a", "manual"),
    ]
    assert all(item.reason == "用户手动选择" for item in result.selections)
    assert result.fallback_to_ask is False


def test_auto_mode_ignores_manual_selection_and_uses_stable_rules_without_llm() -> None:
    registry = {
        "z": definition("z", "复盘"),
        "a": definition("a", "daily_review"),
        "n": definition("n", "unmatched"),
    }
    result = route_skills(
        "请做今日复盘",
        "daily_review",
        "auto",
        ["n"],
        registry=registry,
        llm_complete=lambda messages: (None, None, "no key"),
    )
    assert [(item.skill_id, item.selection_source) for item in result.selections] == [
        ("a", "rule"),
        ("z", "rule"),
    ]
    assert all("匹配" in item.reason for item in result.selections)
    assert result.fallback_to_ask is False


def test_hybrid_preserves_manual_then_supplements_and_caps_total_at_three() -> None:
    registry = {name: definition(name, "命中") for name in ("a", "b", "c", "d")}
    result = route_skills(
        "全部命中",
        "ask",
        "hybrid",
        ["d", "d"],
        registry=registry,
        llm_complete=llm_response('{"skill_ids":["c","a","b"],"reasons":{"c":"x","a":"y","b":"z"}}'),
    )
    assert [(item.skill_id, item.selection_source) for item in result.selections] == [
        ("d", "manual"),
        ("c", "llm"),
        ("a", "llm"),
    ]


def test_three_manual_skills_skip_unnecessary_llm_call() -> None:
    registry = {name: definition(name, "命中") for name in ("a", "b", "c", "d")}

    def forbidden_llm(messages: list[dict[str, str]]):
        raise AssertionError("full manual selection must not call LLM")

    result = route_skills(
        "命中",
        "ask",
        "hybrid",
        ["a", "b", "c"],
        registry=registry,
        llm_complete=forbidden_llm,
    )
    assert [item.skill_id for item in result.selections] == ["a", "b", "c"]


@pytest.mark.parametrize(
    "payload",
    [
        "not json",
        "[]",
        '{"skill_ids":"a","reasons":{}}',
        '{"skill_ids":[1],"reasons":{}}',
        '{"skill_ids":["invented"],"reasons":{"invented":"x"}}',
        '{"skill_ids":["registered_not_candidate"],"reasons":{"registered_not_candidate":"x"}}',
        '{"skill_ids":["a"],"reasons":[]}',
        '{"skill_ids":["a"],"reasons":{}}',
        '{"skill_ids":["a"],"reasons":{"a":1}}',
        '{"skill_ids":["a"],"reasons":{"a":"x"},"extra":true}',
    ],
)
def test_malformed_or_disallowed_llm_result_invalidates_whole_result_and_keeps_rules(payload: str) -> None:
    registry = {
        "a": definition("a", "命中"),
        "b": definition("b", "命中"),
        "registered_not_candidate": definition("registered_not_candidate", "别的"),
    }
    result = route_skills("命中", "ask", "auto", [], registry=registry, llm_complete=llm_response(payload))
    assert [(item.skill_id, item.selection_source) for item in result.selections] == [
        ("a", "rule"),
        ("b", "rule"),
    ]


def test_llm_call_failure_keeps_deterministic_rule_selection() -> None:
    def broken(messages: list[dict[str, str]]):
        raise RuntimeError("network must degrade")

    result = route_skills("复盘", "ask", "auto", [], registry={"daily": definition("daily", "复盘")}, llm_complete=broken)
    assert result.selections[0].skill_id == "daily"
    assert result.selections[0].selection_source == "rule"
    assert result.fallback_to_ask is False


def test_valid_empty_llm_selection_means_no_automatic_selection_and_fallback() -> None:
    result = route_skills(
        "复盘",
        "ask",
        "auto",
        [],
        registry={"daily": definition("daily", "复盘")},
        llm_complete=llm_response('{"skill_ids":[],"reasons":{}}'),
    )
    assert result.selections == ()
    assert result.fallback_to_ask is True


def test_llm_reason_is_redacted_before_becoming_visible() -> None:
    result = route_skills(
        "复盘",
        "ask",
        "auto",
        [],
        registry={"daily": definition("daily", "复盘")},
        llm_complete=llm_response(
            '{"skill_ids":["daily"],"reasons":{"daily":"use sk-abcdef1234567890 for routing"}}'
        ),
    )
    reason = result.selections[0].reason
    assert result.selections[0].selection_source == "llm"
    assert "sk-abcdef1234567890" not in reason
    assert "[REDACTED]" in reason


def test_no_candidates_falls_back_without_calling_llm() -> None:
    def forbidden_llm(messages: list[dict[str, str]]):
        raise AssertionError("empty allowlist must not call LLM")

    result = route_skills("无关问题", "ask", "hybrid", [], registry={"daily": definition("daily", "复盘")}, llm_complete=forbidden_llm)
    assert result.selections == ()
    assert result.fallback_to_ask is True
