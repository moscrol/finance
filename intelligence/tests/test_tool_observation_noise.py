"""Layer 2 (no-model noise prune) — 可删/必须留表 + 夹具。

本文件不包含「缺 as_of 拒执行」夹具，也不触及 authorize。
截止日由合同注入，不由模型参数硬拒（设计合同 §6 / §11.3）。
"""

from __future__ import annotations

import json

from intelligence.runtime.agent_episode import ContinuousAgentEpisode
from intelligence.services.agent_research import AgentEvidence, AgentToolContext
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.research_tool_registry import ResearchToolRegistry, ToolSpec
from intelligence.services.tool_observation_noise import (
    COLLAPSED_OBSERVATION_MARK,
    DROPPABLE_KEYS,
    MUST_KEEP_KEYS,
    normalize_observation_prose,
    prune_tool_observation,
)
from intelligence.tests.test_agent_episode import (
    ScriptedModel,
    _context,
    _finish_turn,
    _frame,
    _tool_turn,
)

# 真实 observation 上反复出现的截断套话（finance_query.truncation_notice 形状）。
_BOILERPLATE = (
    "查询结果已按 Agent 上下文预算截断至 25 条；"
    "未覆盖的日期请收窄 time_range 再查，不要靠调大 limit；"
    "实际覆盖 2026-07-01..2026-07-21；请求窗口 2026-06-01..2026-07-21"
)


def _payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "ok": True,
        "tool": "finance_query",
        "query": "sector_daily 成交额前10",
        "observation": "PCB概念涨4.74%，成交3432亿。",
        "evidence": [
            {
                "tool": "finance_query",
                "title": "PCB概念",
                "detail": "pct_chg=4.74 amount=3432.59",
                "source": "fact_sector_daily",
                "source_date": "2026-08-07",
                "evidence_tier": "A",
                "supports": ["current_baseline"],
                "contradicts": ["duration_assessment"],
                "independent_key": "pcb:2026-08-07",
                "freshness": "same_day",
                "content_hash": "abc123def456",
                "evidence_id": "E1",
            }
        ],
        "evidence_hashes": ["abc123def456"],
        "evidence_ids": ["E1"],
        "gaps": ["缺少成因证据"],
        "dataset": "sector_daily",
        "caliber": "fact_sector_daily",
        "payload_field_names": ["trade_date", "pct_chg", "amount"],
        "payload_sha256": "f" * 64,
    }
    payload.update(overrides)
    return payload


def _assert_evidence_identity_intact(pruned: dict[str, object]) -> None:
    item = pruned["evidence"][0]
    assert isinstance(item, dict)
    assert item["content_hash"] == "abc123def456"
    assert pruned["evidence_hashes"] == ["abc123def456"]
    assert item["source_date"] == "2026-08-07"
    assert item["supports"] == ["current_baseline"]
    assert item["contradicts"] == ["duration_assessment"]
    assert pruned["gaps"] == ["缺少成因证据"]
    assert item["independent_key"] == "pcb:2026-08-07"
    assert item["source"] == "fact_sector_daily"


def test_keep_and_drop_tables_are_explicit_with_reasons() -> None:
    assert DROPPABLE_KEYS
    assert MUST_KEEP_KEYS
    for key, reason in {**DROPPABLE_KEYS, **MUST_KEEP_KEYS}.items():
        assert isinstance(key, str) and key
        assert isinstance(reason, str) and reason
    for required in (
        "evidence_hashes",
        "source_date",
        "gaps",
        "supports",
        "contradicts",
    ):
        assert required in MUST_KEEP_KEYS
        assert required not in DROPPABLE_KEYS
    overlap = set(DROPPABLE_KEYS) & set(MUST_KEEP_KEYS)
    assert not overlap


def test_clean_payload_without_debug_keys_is_byte_identical() -> None:
    payload = _payload()
    for key in DROPPABLE_KEYS:
        payload.pop(key, None)

    pruned, _seen = prune_tool_observation(payload)

    assert pruned == payload
    assert "noise_prune" not in pruned


def test_debug_keys_are_dropped_and_declared_not_evidence_identity() -> None:
    payload = _payload()

    pruned, _seen = prune_tool_observation(payload)

    for key in ("payload_field_names", "payload_sha256", "caliber"):
        assert key not in pruned
    assert pruned["dataset"] == "sector_daily"
    _assert_evidence_identity_intact(pruned)
    marker = pruned["noise_prune"]
    assert list(pruned)[0] == "noise_prune"
    assert marker["dropped_keys"] == [
        "payload_field_names",
        "payload_sha256",
        "caliber",
    ]
    assert marker["collapsed_prose"] is False
    assert "已删除" in marker["instruction"]


def test_duplicate_prose_is_collapsed_after_whitespace_normalize() -> None:
    first = _payload(
        observation=f"  {_BOILERPLATE}  ",
        query="第一次查询",
    )
    second = _payload(
        observation=f"{_BOILERPLATE}\n",
        query="第二次查询",
        evidence_hashes=["def789aaa000"],
        evidence=[
            {
                **_payload()["evidence"][0],
                "content_hash": "def789aaa000",
                "evidence_id": "E2",
                "source_date": "2026-08-08",
            }
        ],
    )
    assert normalize_observation_prose(str(first["observation"])) == (
        normalize_observation_prose(str(second["observation"]))
    )

    kept, seen = prune_tool_observation(first)
    collapsed, _seen = prune_tool_observation(second, seen_prose=seen)

    assert kept["observation"] == first["observation"]
    assert collapsed["observation"] == COLLAPSED_OBSERVATION_MARK
    assert collapsed["noise_prune"]["collapsed_prose"] is True
    assert collapsed["query"] == "第二次查询"
    item = collapsed["evidence"][0]
    assert isinstance(item, dict)
    assert item["content_hash"] == "def789aaa000"
    assert collapsed["evidence_hashes"] == ["def789aaa000"]
    assert item["source_date"] == "2026-08-08"
    assert item["supports"] == ["current_baseline"]
    assert item["contradicts"] == ["duration_assessment"]
    assert collapsed["gaps"] == ["缺少成因证据"]


def test_different_prose_is_not_collapsed() -> None:
    first, seen = prune_tool_observation(_payload(observation="指数收于3421点。"))
    second, _seen = prune_tool_observation(
        _payload(observation="板块放量上涨。"),
        seen_prose=seen,
    )

    assert first["observation"] == "指数收于3421点。"
    assert second["observation"] == "板块放量上涨。"
    assert second["noise_prune"]["collapsed_prose"] is False


def test_pruning_never_mutates_the_input_or_seen_set() -> None:
    payload = _payload()
    seen = frozenset({"already"})

    prune_tool_observation(payload, seen_prose=seen)

    assert "payload_sha256" in payload
    assert "noise_prune" not in payload
    assert seen == frozenset({"already"})


def test_unknown_keys_are_kept() -> None:
    payload = _payload(extra_claim_field="可能是主张")
    pruned, _seen = prune_tool_observation(payload)
    assert pruned["extra_claim_field"] == "可能是主张"


def test_prune_is_deterministic() -> None:
    payload = _payload(observation=_BOILERPLATE)
    first, seen_a = prune_tool_observation(payload)
    second, seen_b = prune_tool_observation(payload)
    assert first == second
    assert seen_a == seen_b
    again_a, _ = prune_tool_observation(payload, seen_prose=seen_a)
    again_b, _ = prune_tool_observation(payload, seen_prose=seen_b)
    assert again_a == again_b


def test_realistic_pair_saves_debug_keys_and_duplicate_narrative() -> None:
    first = _payload(observation=_BOILERPLATE, query="查询甲")
    second = _payload(observation=_BOILERPLATE, query="查询乙")
    kept, seen = prune_tool_observation(first)
    collapsed, _ = prune_tool_observation(second, seen_prose=seen)
    before = len(json.dumps([first, second], ensure_ascii=False))
    after = len(json.dumps([kept, collapsed], ensure_ascii=False))
    assert after < before
    assert collapsed["observation"] == COLLAPSED_OBSERVATION_MARK
    # 给最终报告用的粗估：字符差；token 按 ~2 汉字/token 约。
    assert before - after >= len(_BOILERPLATE) // 2


def test_duplicate_observation_is_collapsed_between_model_turns() -> None:
    """发生在两次模型调用之间：第二轮看到的是剪枝后的 tool 消息，system 不变。"""

    boilerplate = _BOILERPLATE

    def runner(query: str, _context: AgentToolContext):
        digest = f"hash-{query}"
        evidence = AgentEvidence(
            tool="market_data",
            title="样板块",
            detail=query,
            source="本地行情",
            source_date="2026-07-21",
            evidence_tier="L4",
            supports=("current_baseline",),
            contradicts=("duration_assessment",),
            content_hash=digest,
        )
        return (
            [evidence],
            boilerplate,
            ProviderTrace(
                provider="test:market",
                capability="market_data",
                status="success",
                source_trade_date="2026-07-21",
                result_count=1,
            ),
        )

    frame = _frame()
    model = ScriptedModel(
        [
            _tool_turn("查询甲", call_id="call-a"),
            _tool_turn("查询乙", call_id="call-b"),
            _finish_turn(hashes=("hash-查询甲", "hash-查询乙")),
        ]
    )
    registry = ResearchToolRegistry(
        (
            ToolSpec(
                name="market_data",
                capability="market_data",
                description="结构化行情",
                cost="local",
                freshness="current",
                runner=runner,
            ),
        )
    )

    outcome = ContinuousAgentEpisode(model).run(
        task_frame=frame,
        context=_context(frame, max_steps=3),
        registry=registry,
    )

    first_system = model.calls[0]["messages"][0]["content"]
    second_system = model.calls[1]["messages"][0]["content"]
    third_system = model.calls[2]["messages"][0]["content"]
    assert first_system == second_system == third_system

    first_tool = json.loads(
        next(
            item["content"]
            for item in model.calls[1]["messages"]
            if item["role"] == "tool"
        )
    )
    second_tools = [
        json.loads(item["content"])
        for item in model.calls[2]["messages"]
        if item["role"] == "tool"
    ]
    assert first_tool["observation"] == boilerplate
    assert second_tools[0]["observation"] == boilerplate
    assert second_tools[1]["observation"] == COLLAPSED_OBSERVATION_MARK
    assert "payload_sha256" not in first_tool
    assert "payload_field_names" not in first_tool
    assert "caliber" not in first_tool
    assert first_tool["evidence"][0]["source_date"] == "2026-07-21"
    assert first_tool["evidence"][0]["supports"] == ["current_baseline"]
    assert first_tool["evidence"][0]["contradicts"] == ["duration_assessment"]
    assert second_tools[1]["evidence"][0]["source_date"] == "2026-07-21"
    assert "gaps" in second_tools[1]

    ledger_rows = [
        event.payload
        for event in outcome.events
        if event.kind == "tool_result"
    ]
    assert len(ledger_rows) == 2
    assert all(row.get("payload_sha256") for row in ledger_rows)
    assert all(row["observation"] == boilerplate for row in ledger_rows)


def test_error_payload_without_debug_keys_passes_through() -> None:
    payload = {"ok": False, "tool": "market_data", "error": "tool_timeout"}
    pruned, _seen = prune_tool_observation(payload)
    assert pruned == payload
