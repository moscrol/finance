"""历史折叠（spec 2026-09-07 §3.2 / §6.1）：只折比最近 K 批更早的 tool 消息、索引覆盖每个 E 号、配对不变、幂等。"""

from __future__ import annotations

import json
import re

import pytest

from intelligence.services.agent_research import AgentEvidence
from intelligence.services.episode_history_compaction import (
    COMPACTED_NOTE,
    CompactionReport,
    compact_history,
    history_compaction_enabled,
    history_keep_batches,
)

_HEX = re.compile(r"\b[0-9a-f]{40,64}\b")


def _evidence(n: int, tool: str = "news_search") -> AgentEvidence:
    return AgentEvidence(
        tool=tool,
        title=f"标题{n}" + "很长" * 40,
        detail=f"细节{n}" * 30,
        source=f"source-{n}",
        source_date="2026-09-0" + str(1 + n % 7),
        independent_key=f"k{n}",
        content_hash=f"{n:040x}",
    )


def _tool_message(call_id: str, tool: str, items: list[AgentEvidence], ordinals: dict[str, str], **extra: object) -> dict[str, object]:
    rows = [
        {
            "tool": item.tool, "title": item.title, "detail": item.detail, "source": item.source,
            "source_date": item.source_date, "evidence_tier": "news", "evidence_id": ordinals[item.content_hash],
        }
        for item in items
    ]
    payload: dict[str, object] = {
        "ok": True, "tool": tool, "query": f"{tool} 查询", "observation": "观察叙述" * 50,
        "evidence": rows, "evidence_ids": [r["evidence_id"] for r in rows], "gaps": [f"{tool} 缺口"],
        **extra,
    }
    return {"role": "tool", "tool_call_id": call_id, "content": json.dumps(payload, ensure_ascii=False)}


def _history(batches: int, per_batch: int = 3) -> tuple[list[dict[str, object]], tuple[AgentEvidence, ...]]:
    evidence: list[AgentEvidence] = []
    for b in range(batches):
        for i in range(per_batch):
            evidence.append(_evidence(b * per_batch + i))
    from intelligence.services.episode_protocol import evidence_ordinal_table

    ordinals = evidence_ordinal_table(tuple(evidence))
    messages: list[dict[str, object]] = [
        {"role": "system", "content": "宪法"},
        {"role": "user", "content": "任务"},
    ]
    for b in range(batches):
        calls = [{"id": f"c{b}-{i}", "type": "function", "function": {"name": "news_search", "arguments": "{}"}} for i in range(per_batch)]
        messages.append({"role": "assistant", "content": "", "tool_calls": calls})
        for i in range(per_batch):
            item = evidence[b * per_batch + i]
            extra = {"runtime_budget": {"remaining_tool_calls": 9}} if (b == batches - 1 and i == per_batch - 1) else {}
            messages.append(_tool_message(f"c{b}-{i}", "news_search", [item], ordinals, **extra))
    return messages, tuple(evidence)


def test_only_batches_older_than_the_kept_tail_are_folded_and_pairing_survives() -> None:
    messages, evidence = _history(batches=5)
    before_shape = [(m["role"], m.get("tool_call_id")) for m in messages]
    before_assistants = [m for m in messages if m["role"] == "assistant"]
    originals = {m["tool_call_id"]: m["content"] for m in messages if m["role"] == "tool"}

    report = compact_history(messages, evidence=evidence, keep_batches=2)

    assert isinstance(report, CompactionReport)
    assert (report.batches_total, report.batches_kept) == (5, 2)
    assert sorted(f.call_id for f in report.folded) == sorted(f"c{b}-{i}" for b in range(3) for i in range(3))
    assert report.chars_saved > 0 and all(f.chars_after < f.chars_before for f in report.folded)
    # 配对不变量：条数 / 顺序 / tool_call_id 集合不变；assistant 消息逐字节相同。
    assert [(m["role"], m.get("tool_call_id")) for m in messages] == before_shape
    assert [m for m in messages if m["role"] == "assistant"] == before_assistants
    for m in (m for m in messages if m["role"] == "tool"):
        payload = json.loads(m["content"])
        batch = int(m["tool_call_id"][1])
        if batch < 3:
            assert payload["compacted"] is True and "observation" not in payload and "evidence" not in payload
            assert payload["note"] == COMPACTED_NOTE and payload["gaps"] == ["news_search 缺口"]
        else:
            assert m["content"] == originals[m["tool_call_id"]]  # 最近两批原文
    # runtime_budget 挂在最后一条上，逐字不变。
    last = json.loads(messages[-1]["content"])
    assert last["runtime_budget"] == {"remaining_tool_calls": 9} and "compacted" not in last


def test_index_covers_every_evidence_id_and_never_leaks_a_hash() -> None:
    messages, evidence = _history(batches=3, per_batch=2)
    originals = {m["tool_call_id"]: json.loads(m["content"]) for m in messages if m["role"] == "tool"}

    compact_history(messages, evidence=evidence, keep_batches=1)

    folded = [m for m in messages if m["role"] == "tool" and json.loads(m["content"]).get("compacted")]
    assert len(folded) == 4
    for m in folded:
        payload = json.loads(m["content"])
        original = originals[m["tool_call_id"]]
        assert [e["evidence_id"] for e in payload["evidence_index"]] == original["evidence_ids"]
        for entry in payload["evidence_index"]:
            assert set(entry) <= {"evidence_id", "tool", "title", "source_date"}
            assert len(entry["title"]) <= 60 and entry["source_date"].startswith("2026-09-")
        assert not _HEX.search(m["content"])


def test_folding_is_idempotent_and_fallbacks_when_evidence_table_lacks_an_ordinal() -> None:
    messages, evidence = _history(batches=3)
    first = compact_history(messages, evidence=evidence, keep_batches=1)
    snapshot = json.dumps(messages, ensure_ascii=False)
    second = compact_history(messages, evidence=evidence, keep_batches=1)
    assert first.folded and second.folded == ()
    assert json.dumps(messages, ensure_ascii=False) == snapshot

    # 累计表里缺这个 E 号（不该发生，但发生时索引仍要覆盖它——从消息自己的行取标题）。
    messages2, evidence2 = _history(batches=2)
    compact_history(messages2, evidence=(), keep_batches=1)
    folded = json.loads(messages2[3]["content"])
    assert folded["compacted"] is True and folded["evidence_index"][0]["evidence_id"] == "E1"
    assert folded["evidence_index"][0]["title"].startswith("标题0")


def test_tool_errors_fold_to_error_stub_and_short_histories_are_untouched() -> None:
    messages, evidence = _history(batches=2)
    err = {"role": "tool", "tool_call_id": "e1", "content": json.dumps({"ok": False, "tool": "web_fetch", "error": "tool_timeout", "detail": "x" * 400})}
    messages.insert(3, err)  # 放进第一批
    report = compact_history(messages, evidence=evidence, keep_batches=1)
    assert json.loads(messages[3]["content"]) == {"ok": False, "tool": "web_fetch", "compacted": True, "error": "tool_timeout"}
    assert any(f.call_id == "e1" for f in report.folded)

    short, ev = _history(batches=2)
    untouched = json.dumps(short, ensure_ascii=False)
    assert compact_history(short, evidence=ev, keep_batches=2).folded == ()
    assert json.dumps(short, ensure_ascii=False) == untouched


def test_switches_default_off_and_keep_batches_floor(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ASK_EPISODE_HISTORY_COMPACTION", raising=False)
    monkeypatch.delenv("ASK_EPISODE_HISTORY_KEEP_BATCHES", raising=False)
    assert history_compaction_enabled() is False and history_keep_batches() == 2
    monkeypatch.setenv("ASK_EPISODE_HISTORY_COMPACTION", "on")
    assert history_compaction_enabled() is True
    for raw, expected in (("1", 1), ("3", 3), ("0", 2), ("-2", 2), ("abc", 2)):
        monkeypatch.setenv("ASK_EPISODE_HISTORY_KEEP_BATCHES", raw)
        assert history_keep_batches() == expected, raw
