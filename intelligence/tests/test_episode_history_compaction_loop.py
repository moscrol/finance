"""历史折叠接进 Episode loop（spec 2026-09-07 §6.1 第 2 / 4 / 6 / 8 / 10 条）。

四批工具、K=2：第 4 轮模型看到第 1 批已折，第 5 轮（收尾）看到第 1、2 批已折、第 3、4 批原文；
收尾绑一个**只出现在已折叠消息里**的 E 号仍被 admit_finish 接受（校验靠累计证据表不靠消息）；
durable tool_result 全量不变；开关关时逐字节同前。
"""

from __future__ import annotations

import json

import pytest

from intelligence.runtime.agent_episode import ContinuousAgentEpisode
from intelligence.services.agent_research import AgentEvidence, AgentToolContext
from intelligence.services.agent_runtime import ModelToolCall, ModelTurn
from intelligence.services.provider_observability import ProviderTrace
from intelligence.tests.test_agent_episode import (  # noqa: E402  复用既有脚本模型与夹具
    ScriptedModel,
    _context,
    _frame,
    _market_registry,
)


def _runner(query: str, _context: AgentToolContext):
    digest = f"hash-{query}"
    evidence = AgentEvidence(
        tool="market_data",
        title=f"{query} 总览",
        detail=f"{query}：上涨家数增加，成交保持活跃" * 8,
        source="本地行情",
        source_date="2026-07-21",
        evidence_tier="L4",
        content_hash=digest,
    )
    return (
        [evidence],
        "raw market observation " + "叙述" * 200,
        ProviderTrace(provider="test:market", capability="market_data", status="success", result_count=1),
    )


def _tool_turn(index: int) -> ModelTurn:
    return ModelTurn("", (ModelToolCall(f"call-{index}", "market_data", {"query": f"查询{index}"}),), "scripted", "")


def _finish_binding(evidence_ref: str) -> ModelTurn:
    return ModelTurn(
        json.dumps(
            {
                "status": "completed",
                "draft": "当前更接近条件化修复，持续性取决于量能。",
                "gaps": [],
                "bindings": [{"output_id": "direct_assessment", "evidence_hashes": [evidence_ref], "gap": ""}],
            },
            ensure_ascii=False,
        ),
        (),
        "scripted",
        "",
    )


def _run(monkeypatch: pytest.MonkeyPatch, *, enabled: bool) -> tuple[ScriptedModel, object]:
    if enabled:
        monkeypatch.setenv("ASK_EPISODE_HISTORY_COMPACTION", "on")
        monkeypatch.setenv("ASK_EPISODE_HISTORY_KEEP_BATCHES", "2")
    else:
        monkeypatch.delenv("ASK_EPISODE_HISTORY_COMPACTION", raising=False)
    model = ScriptedModel([_tool_turn(1), _tool_turn(2), _tool_turn(3), _tool_turn(4), _finish_binding("E1")])
    frame = _frame()
    outcome = ContinuousAgentEpisode(model).run(
        task_frame=frame,
        context=_context(frame, max_steps=8),
        registry=_market_registry(_runner),
    )
    return model, outcome


def _tool_messages(call: dict[str, object]) -> list[dict[str, object]]:
    return [m for m in call["messages"] if m.get("role") == "tool"]


def test_older_batches_fold_before_the_model_call_and_a_folded_evidence_still_binds(monkeypatch) -> None:
    model, outcome = _run(monkeypatch, enabled=True)

    assert outcome.status == "completed", outcome.stop_reason
    assert len(model.calls) == 5
    # 第 4 轮：3 批在场，K=2 → 第 1 批折、第 2、3 批原文。
    turn4 = [json.loads(m["content"]) for m in _tool_messages(model.calls[3])]
    assert [p.get("compacted", False) for p in turn4] == [True, False, False]
    assert turn4[0]["evidence_index"] == [{"evidence_id": "E1", "tool": "market_data", "title": "查询1 总览", "source_date": "2026-07-21"}]
    assert "observation" not in turn4[0] and "evidence" not in turn4[0]
    # 第 5 轮（收尾）：4 批在场 → 第 1、2 批折；最后一条仍挂 runtime_budget。
    turn5 = [json.loads(m["content"]) for m in _tool_messages(model.calls[4])]
    assert [p.get("compacted", False) for p in turn5] == [True, True, False, False]
    assert "runtime_budget" in turn5[-1] and "compacted" not in turn5[-1]
    # 绑到只在折叠消息里的 E1 → 通过，且解回原 hash。
    assert [b.output_id for b in outcome.bindings] == ["direct_assessment"]
    assert outcome.bindings[0].evidence_hashes == ("hash-查询1",)
    # durable tool_result 全量不变：四条都还带原始 observation。
    results = [e for e in outcome.events if e.kind == "tool_result"]
    assert len(results) == 4 and all(str(e.payload["observation"]).startswith("raw market observation") for e in results)
    # 折叠账：两条 history_compacted（第 4 轮前折 1 条、第 5 轮前再折 1 条），finish 带汇总。
    folds = [e for e in outcome.events if e.kind == "history_compacted"]
    assert [e.payload["folded_messages"] for e in folds] == [1, 1]
    assert [e.payload["llm_calls_before"] for e in folds] == [3, 4]
    assert all(e.payload["chars_saved"] > 0 for e in folds)
    finish = next(e for e in outcome.events if e.kind == "finish")
    summary = finish.payload["history_compaction"]
    assert summary["enabled"] is True and summary["folded_messages"] == 2
    assert summary["chars_saved"] == sum(e.payload["chars_saved"] for e in folds)
    # 折叠只发生在 tool 消息上：assistant 消息条数与 tool_call_id 集合和关闭时一致（见下一条对照）。


def test_switch_off_is_byte_identical_to_before(monkeypatch) -> None:
    model_off, outcome_off = _run(monkeypatch, enabled=False)
    assert outcome_off.status == "completed"
    assert not [e for e in outcome_off.events if e.kind == "history_compacted"]
    finish = next(e for e in outcome_off.events if e.kind == "finish")
    assert finish.payload["history_compaction"] == {"enabled": False, "folded_messages": 0, "chars_saved": 0}
    for call in model_off.calls:
        assert all("compacted" not in json.loads(m["content"]) for m in _tool_messages(call))

    model_on, _ = _run(monkeypatch, enabled=True)
    # 配对不变量：开与关，每一轮 tool 消息的条数、顺序、tool_call_id 完全相同，只差 content。
    for off_call, on_call in zip(model_off.calls, model_on.calls, strict=True):
        assert [m.get("tool_call_id") for m in _tool_messages(off_call)] == [m.get("tool_call_id") for m in _tool_messages(on_call)]
        assert [m for m in off_call["messages"] if m.get("role") == "assistant"] == [m for m in on_call["messages"] if m.get("role") == "assistant"]
