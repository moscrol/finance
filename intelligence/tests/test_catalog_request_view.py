import copy
from dataclasses import replace
import json

import pytest

from intelligence.eval.catalog_request_view import Entry, full_catalog, project_catalog


@pytest.fixture
def case():
    entries = (
        Entry(
            "document_search",
            "document_read",
            "low",
            "source_dated",
            "检索当前已授权的文档，返回可回查的来源片段、原始日期和页码信息。",
            "命中摘要不代表全文；未见内容不得推断为已证实，来源日期不等于事件发生日期。",
        ),
        Entry(
            "table_query",
            "table_read",
            "low",
            "snapshot",
            "按已授权的表结构查询只读快照；字段含义和单位以返回的来源元数据为准。",
            "空结果不证明对象不存在；不得把行数或缺失值直接解释为业务事实。",
        ),
    )
    tools = [
        {
            "type": "function",
            "function": {
                "name": e.name,
                "description": e.description + "\n" + e.contract,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "保留完整参数含义，不缩写这段说明",
                        }
                    },
                    "required": ["query"],
                    "additionalProperties": False,
                },
            },
        }
        for e in entries
    ]
    entries = tuple(
        replace(e, parameters=copy.deepcopy(t["function"]["parameters"]))
        for e, t in zip(entries, tools)
    )
    payload = {
        "available_tools": full_catalog(entries),
        "question": "信息已经足够时直接回答即可。",
        "permissions": ["document_read", "table_read"],
        "budget": {"steps": 6},
        "source_identity": {"snapshot": "fixed-snapshot"},
    }
    return payload, entries, tools


def test_disabled_is_identity(case):
    payload, entries, tools = case
    result = project_catalog(payload, entries, tools)
    assert result.payload is payload
    assert not result.applied


def test_compact_only_duplicate_catalog_value(case):
    payload, entries, tools = case
    original_payload, original_tools = copy.deepcopy(payload), copy.deepcopy(tools)
    result = project_catalog(payload, entries, tools, enabled=True)
    assert result.applied
    assert result.payload is not payload
    assert {k: v for k, v in result.payload.items() if k != "available_tools"} == {
        k: v for k, v in payload.items() if k != "available_tools"
    }
    for e in entries:
        for text in (e.name, e.capability, e.cost, e.freshness):
            assert text in result.payload["available_tools"]
        assert e.description not in result.payload["available_tools"]
        assert e.contract in next(
            t["function"]["description"]
            for t in tools
            if t["function"]["name"] == e.name
        )
    assert payload == original_payload
    assert tools == original_tools


def test_reported_bytes_are_real_utf8_difference_not_tokens(case):
    payload, entries, tools = case
    result = project_catalog(payload, entries, tools, enabled=True)
    assert result.catalog_bytes_saved == len(payload["available_tools"].encode()) - len(
        result.payload["available_tools"].encode()
    )
    assert result.catalog_bytes_saved > 0


@pytest.mark.parametrize(
    "problem",
    [
        "closed",
        "hidden",
        "extra",
        "duplicate",
        "missing_params",
        "wrong_description",
        "wrong_contract",
        "bad_function",
        "bad_type",
    ],
)
def test_no_compaction_without_exact_full_definitions(case, problem):
    payload, entries, tools = case
    if problem == "closed":
        tools = []
    elif problem == "hidden":
        tools = tools[:1]
    elif problem == "extra":
        tools += [{"type": "function", "function": {"name": "other"}}]
    elif problem == "duplicate":
        tools += [copy.deepcopy(tools[0])]
    elif problem == "missing_params":
        del tools[0]["function"]["parameters"]
    elif problem == "wrong_description":
        tools[0]["function"]["description"] = "短介绍，不含完整限制"
    elif problem == "wrong_contract":
        tools[0]["function"]["description"] = entries[0].description
    elif problem == "bad_function":
        tools[0]["function"] = []
    elif problem == "bad_type":
        tools[0]["type"] = "not-function"
    result = project_catalog(payload, entries, tools, enabled=True)
    assert result.payload is payload
    assert not result.applied
    assert result.catalog_bytes_saved == 0


def test_finalization_restores_original_instead_of_persisting_compact_history(case):
    payload, entries, tools = case
    first = project_catalog(payload, entries, tools, enabled=True)
    assert first.applied
    final = project_catalog(payload, entries, [], enabled=True)
    assert final.payload["available_tools"] == full_catalog(entries)
    assert not final.applied
    assert payload["available_tools"] == full_catalog(entries)


def test_stale_or_altered_catalog_is_untouched(case):
    payload, entries, tools = case
    payload["available_tools"] += "\n另有必须保留的使用限制"
    assert project_catalog(payload, entries, tools, enabled=True).payload is payload


def test_already_shortened_payload_is_not_silently_reused(case):
    payload, entries, tools = case
    first = project_catalog(payload, entries, tools, enabled=True)
    assert first.applied
    second = project_catalog(first.payload, entries, tools, enabled=True)
    assert not second.applied
    assert second.reason == "catalog_mismatch"


def test_api_order_does_not_affect_projection(case):
    payload, entries, tools = case
    result = project_catalog(payload, entries, tools, enabled=True)
    assert result.applied
    assert (
        project_catalog(payload, entries, list(reversed(tools)), enabled=True) == result
    )


@pytest.mark.parametrize("profile", ["economy", "standard", "frontier", "expanded"])
def test_profile_and_model_identity_have_no_presentation_authority(
    case, monkeypatch, profile
):
    payload, entries, tools = case
    before = project_catalog(payload, entries, tools, enabled=True)
    assert before.applied
    monkeypatch.setenv("FWP_MODEL_PROFILE", profile)
    monkeypatch.setenv("LLM_MODEL", "arbitrary-unranked-model")
    assert project_catalog(payload, entries, tools, enabled=True) == before


def test_zero_saving_does_not_expand_prompt():
    entries = (Entry("x", "r", "l", "s", "", parameters={"type": "object"}),)
    payload = {"available_tools": full_catalog(entries)}
    tools = [
        {
            "type": "function",
            "function": {
                "name": "x",
                "description": "",
                "parameters": {"type": "object"},
            },
        }
    ]
    result = project_catalog(payload, entries, tools, enabled=True)
    assert not result.applied
    assert result.payload is payload


def test_serialized_tool_schemas_remain_identical(case):
    payload, entries, tools = case
    before = json.dumps(tools, ensure_ascii=False, sort_keys=True)
    result = project_catalog(payload, entries, tools, enabled=True)
    assert result.applied
    assert json.dumps(tools, ensure_ascii=False, sort_keys=True) == before


def test_same_name_different_contract_fails_open_to_full_view(case):
    payload, entries, tools = case
    changed = (replace(entries[0], contract="不同限制"), entries[1])
    assert project_catalog(payload, changed, tools, enabled=True).payload is payload


@pytest.mark.parametrize("change", ["required", "property", "numeric_boolean"])
def test_parameters_must_match_authoritative_registry(case, change):
    payload, entries, tools = case
    if change == "required":
        tools[0]["function"]["parameters"]["required"] = []
    elif change == "property":
        tools[0]["function"]["parameters"]["properties"]["query"]["description"] = (
            "不同参数说明"
        )
    else:
        entries = (
            replace(entries[0], parameters={"type": "object", "minProperties": 1}),
            entries[1],
        )
        tools[0]["function"]["parameters"] = {"type": "object", "minProperties": True}
    result = project_catalog(payload, entries, tools, enabled=True)
    assert not result.applied
    assert result.reason == "parameters_mismatch"
    assert result.payload is payload
