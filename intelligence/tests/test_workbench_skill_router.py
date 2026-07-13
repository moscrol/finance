from __future__ import annotations

import json
from dataclasses import fields
from pathlib import Path

import pytest

from intelligence.services.ask import AskOptions
from intelligence.services.execution_budget import ExecutionBudget
from intelligence.services.query_understanding import understand_query
from intelligence.services.run_store import RunStore
from intelligence.workbench_skills.contracts import (
    SkillDefinition,
    SkillExecutionContext,
    SkillOutput,
    build_module_answer_contract,
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
        "answer_contract",
    ]
    assert [field.name for field in fields(SkillExecutionContext)] == [
        "query",
        "task_type",
        "user_id",
        "run_id",
        "conversation_id",
        "repo_root",
        "run_store",
        "conversation_context",
        "execution_budget",
    ]
    store = RunStore(root=tmp_path / "runs")
    budget = ExecutionBudget(started_at=10.0, deadline_at=20.0)
    context = SkillExecutionContext(
        query="今日复盘",
        task_type="daily_review",
        user_id="u1",
        run_id="run1",
        conversation_id="conv1",
        repo_root=tmp_path,
        run_store=store,
        execution_budget=budget,
    )
    assert context.repo_root == tmp_path
    assert context.run_store is store
    assert context.execution_budget is budget
    other_budget = ExecutionBudget(started_at=30.0, deadline_at=40.0)
    equivalent_context = SkillExecutionContext(
        query="今日复盘",
        task_type="daily_review",
        user_id="u1",
        run_id="run1",
        conversation_id="conv1",
        repo_root=tmp_path,
        run_store=store,
        execution_budget=other_budget,
    )
    assert context == equivalent_context
    assert "execution_budget" not in repr(context)
    assert "10.0" not in repr(context)
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
    ask_options = AskOptions(query="q", execution_budget=budget)
    assert ask_options.execution_budget is budget
    assert ask_options == AskOptions(query="q", execution_budget=other_budget)
    assert "execution_budget" not in repr(ask_options)
    assert "10.0" not in repr(ask_options)


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
    assert result.base_finance_fallback is False


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
    assert result.base_finance_fallback is False


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
        '{"skill_ids":["a"],"reasons":[]}',
        '{"skill_ids":["a"],"reasons":{}}',
        '{"skill_ids":["a"],"reasons":{"a":1}}',
        '{"skill_ids":["a"],"reasons":{"a":"x"},"extra":true}',
    ],
)
def test_malformed_or_unknown_llm_result_invalidates_whole_result_and_keeps_rules(
    payload: str,
) -> None:
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
    assert result.fallback_to_ask is False
    assert result.base_finance_fallback is True


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


def test_no_rule_candidates_still_routes_semantically_against_full_registry() -> None:
    result = route_skills(
        "整理今天的正式日报",
        "ask",
        "hybrid",
        [],
        registry={
            "daily": definition("daily", "复盘"),
            "agent": definition("agent", "研究队列"),
        },
        llm_complete=llm_response(
            '{"skill_ids":["daily"],"reasons":{"daily":"语义上需要正式日报"}}'
        ),
    )
    assert [item.skill_id for item in result.selections] == ["daily"]
    assert result.selections[0].selection_source == "llm"
    assert result.fallback_to_ask is False
    assert result.base_finance_fallback is False


def test_llm_can_select_registered_skill_without_trigger_match() -> None:
    registry = {
        "matched": definition("matched", "复盘"),
        "semantic": definition("semantic", "研究队列"),
    }
    result = route_skills(
        "请做复盘并安排后续研究",
        "ask",
        "auto",
        [],
        registry=registry,
        llm_complete=llm_response(
            '{"skill_ids":["semantic"],"reasons":{"semantic":"需要安排研究任务"}}'
        ),
    )
    assert [item.skill_id for item in result.selections] == ["semantic"]
    assert result.selections[0].selection_source == "llm"


def test_no_semantic_selection_enters_base_finance_chain() -> None:
    result = route_skills(
        "无关问题",
        "ask",
        "hybrid",
        [],
        registry={"daily": definition("daily", "复盘")},
        llm_complete=llm_response('{"skill_ids":[],"reasons":{}}'),
    )
    assert result.selections == ()
    assert result.fallback_to_ask is False
    assert result.base_finance_fallback is True


def test_auto_market_pattern_excludes_theme_research_from_rules_and_llm() -> None:
    query = (
        "如果一个A股题材连续上涨，但板块成交占比开始下降，我应该怎么判断"
        "它是健康分歧还是行情高潮？"
    )
    envelope = understand_query(query)
    captured_candidates: list[str] = []

    def select_forbidden_theme(messages: list[dict[str, str]]):
        payload = json.loads(messages[1]["content"])
        captured_candidates.extend(
            candidate["skill_id"] for candidate in payload["candidates"]
        )
        return (
            '{"skill_ids":["theme-research"],'
            '"reasons":{"theme-research":"规则和语义都像题材研究"}}',
            object(),
            "",
        )

    result = route_skills(
        query,
        "ask",
        "auto",
        [],
        registry={
            "theme-research": definition("theme-research", "连续上涨"),
            "daily-review": definition("daily-review", "今日复盘"),
        },
        llm_complete=select_forbidden_theme,
        query_envelope=envelope,
    )

    assert captured_candidates == ["daily-review"]
    assert result.selections == ()
    assert result.base_finance_fallback is True


def test_manual_market_pattern_preserves_user_selected_theme_research() -> None:
    query = "指数上涨但涨停家数减少，是否背离？"
    envelope = understand_query(query)

    result = route_skills(
        query,
        "ask",
        "manual",
        ["theme-research"],
        registry={"theme-research": definition("theme-research", "指数上涨")},
        llm_complete=lambda _: pytest.fail("manual mode must not call LLM"),
        query_envelope=envelope,
    )

    assert [selection.skill_id for selection in result.selections] == [
        "theme-research"
    ]
    assert result.selections[0].selection_source == "manual"
    assert result.base_finance_fallback is False
