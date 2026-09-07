"""Episode 历史折叠：比最近 K 批更早的工具观察折成「E 号 + 标题 + 日期」索引。

spec ``docs/superpowers/specs/2026-09-07-episode-history-compaction-design.md`` §3.2（第二刀）。

为什么是这个形状（§0 / §2）：上下文成本 = 模型轮数 × 历史长度，同题 17 遍里工具消息合计稳定
5–12 万字，每一轮都原样重发；折成索引每条只剩原文 ≈10%，17 遍模拟把重发累计压到现状的 32–58%。
**不调模型做摘要**——我们已经有证据账本，E 号就是无损摘要；**不动 durable 事件**——审计底稿仍是
全量，这里只改模型看见的 ``messages``；**不动绑定校验**——``admit_finish`` 用累计证据表解 E 号，
与消息里写了什么无关，所以折叠消息里只要每个 E 号都在索引里，模型仍能绑到它们。

不变量（§3.3，测试逐条钉）：
- 只折 role=tool 消息的 ``content``；role / tool_call_id / assistant / user / system 一字不动，配对不变。
- 最近 ``keep_batches`` 批原文保留（含挂着 ``runtime_budget`` 的最后一条）。
- 折叠消息的 ``evidence_index`` 覆盖该消息原 ``evidence_ids`` 的每一个 E 号；hash 永不出现。
- 幂等：``compacted: true`` 的不再折；同一份 messages 折两次结果相同。
- 纯函数式的确定性：无模型、无时钟、无随机。

dsh 对照：抄 ``compaction-tool-result-pruner`` 的「不调模型、原件留日志、替换可追溯」和
``compaction-basic`` 的「保留最近尾段、只折整单元、配对处切」；不抄 LLM 摘要与头尾截断。
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from intelligence.services.agent_research import AgentEvidence
from intelligence.services.episode_protocol import evidence_ordinal_table

HISTORY_COMPACTION_ENV = "ASK_EPISODE_HISTORY_COMPACTION"
HISTORY_KEEP_BATCHES_ENV = "ASK_EPISODE_HISTORY_KEEP_BATCHES"
DEFAULT_KEEP_BATCHES = 2
INDEX_TITLE_CHARS = 60
COMPACTED_NOTE = "详情已折叠；这些证据仍在证据表中，可按 E 号绑定；需要原文可再查同一工具"


def history_compaction_enabled() -> bool:
    raw = str(os.environ.get(HISTORY_COMPACTION_ENV) or "").strip().lower()
    return raw in {"on", "1", "true", "yes"}


def history_keep_batches() -> int:
    """保留原文的最近批数；非法值回落默认 2（0 也回落：至少要留最后一批给模型看观察）。"""

    raw = str(os.environ.get(HISTORY_KEEP_BATCHES_ENV) or "").strip()
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_KEEP_BATCHES
    return value if value >= 1 else DEFAULT_KEEP_BATCHES


@dataclass(frozen=True)
class FoldedMessage:
    call_id: str
    tool: str
    chars_before: int
    chars_after: int
    evidence_count: int
    # 替换后模型真看到的正文（运行底座 INV-R1「模型可见即已落账」）：``derive_messages``
    # 按 call_id 把它覆写到派生出的 tool 消息上；对外投影把它剔成 sha256 + 字符数
    # （``MODEL_VISIBLE_TEXT_FIELDS`` 的 ``folded[].model_content``）。
    model_content: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "call_id": self.call_id,
            "tool": self.tool,
            "chars_before": self.chars_before,
            "chars_after": self.chars_after,
            "evidence_count": self.evidence_count,
            "model_content": self.model_content,
        }


@dataclass(frozen=True)
class CompactionReport:
    folded: tuple[FoldedMessage, ...]
    batches_total: int
    batches_kept: int

    @property
    def chars_saved(self) -> int:
        return sum(item.chars_before - item.chars_after for item in self.folded)

    def to_payload(self) -> dict[str, object]:
        return {
            "folded": [item.to_dict() for item in self.folded],
            "folded_messages": len(self.folded),
            "chars_saved": self.chars_saved,
            "batches_total": self.batches_total,
            "batches_kept": self.batches_kept,
        }


def _tool_batches(messages: Sequence[Mapping[str, Any]]) -> list[list[int]]:
    """把 messages 切成工具批：一条带 tool_calls 的 assistant 之后连续的 role=tool 消息是一批。"""

    batches: list[list[int]] = []
    current: list[int] | None = None
    for index, message in enumerate(messages):
        role = message.get("role")
        if role == "assistant" and message.get("tool_calls"):
            current = []
            batches.append(current)
            continue
        if role == "tool":
            if current is None:
                # 没有前导 assistant 的 tool 消息（测试夹具 / 外部拼装）：自成一批，同样按年龄折。
                current = []
                batches.append(current)
            current.append(index)
            continue
        current = None
    return [batch for batch in batches if batch]


def _evidence_index(
    evidence_ids: Sequence[object],
    *,
    by_ordinal: Mapping[str, AgentEvidence],
    fallback_rows: Sequence[Any],
) -> list[dict[str, object]]:
    fallback_by_id: dict[str, Mapping[str, Any]] = {}
    for row in fallback_rows:
        if isinstance(row, Mapping) and isinstance(row.get("evidence_id"), str):
            fallback_by_id[row["evidence_id"]] = row
    index: list[dict[str, object]] = []
    for raw in evidence_ids:
        eid = str(raw or "").strip()
        if not eid:
            continue
        item = by_ordinal.get(eid)
        if item is not None:
            tool, title, date = item.tool, item.title, item.source_date
        else:
            row = fallback_by_id.get(eid, {})
            tool, title, date = row.get("tool"), row.get("title"), row.get("source_date")
        entry: dict[str, object] = {"evidence_id": eid}
        if tool:
            entry["tool"] = str(tool)
        if title:
            entry["title"] = str(title)[:INDEX_TITLE_CHARS]
        if date and str(date) != "None":
            entry["source_date"] = str(date)
        index.append(entry)
    return index


def _fold_content(
    payload: Mapping[str, Any],
    *,
    by_ordinal: Mapping[str, AgentEvidence],
) -> dict[str, Any]:
    if payload.get("ok") is False:
        stub: dict[str, Any] = {"ok": False, "tool": payload.get("tool"), "compacted": True}
        if payload.get("error"):
            stub["error"] = payload["error"]
    else:
        evidence_ids = payload.get("evidence_ids")
        if not isinstance(evidence_ids, list):
            evidence_ids = [
                row.get("evidence_id")
                for row in (payload.get("evidence") or [])
                if isinstance(row, Mapping) and row.get("evidence_id")
            ]
        stub = {
            "ok": payload.get("ok", True),
            "tool": payload.get("tool"),
            "query": payload.get("query"),
            "compacted": True,
            "evidence_index": _evidence_index(
                evidence_ids,
                by_ordinal=by_ordinal,
                fallback_rows=payload.get("evidence") or [],
            ),
            "gaps": list(payload.get("gaps") or []),
            "note": COMPACTED_NOTE,
        }
    if "runtime_budget" in payload:
        # 只会挂在最后一条 tool 消息上，正常永远在保留区；万一在，预算注入不能丢。
        stub["runtime_budget"] = payload["runtime_budget"]
    return stub


def compact_history(
    messages: list[dict[str, Any]],
    *,
    evidence: Sequence[AgentEvidence],
    keep_batches: int = DEFAULT_KEEP_BATCHES,
) -> CompactionReport:
    """就地把比最近 ``keep_batches`` 批更早的 tool 消息折成索引；返回本次折了什么。"""

    keep = max(1, int(keep_batches))
    batches = _tool_batches(messages)
    foldable = batches[:-keep] if len(batches) > keep else []
    ordinals = evidence_ordinal_table(tuple(evidence))
    by_ordinal = {
        ordinal: item
        for item in evidence
        if (ordinal := ordinals.get(item.content_hash)) is not None
    }
    folded: list[FoldedMessage] = []
    for batch in foldable:
        for index in batch:
            message = messages[index]
            content = message.get("content")
            if not isinstance(content, str):
                continue
            try:
                payload = json.loads(content)
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict) or payload.get("compacted") is True:
                continue
            stub = _fold_content(payload, by_ordinal=by_ordinal)
            replacement = json.dumps(stub, ensure_ascii=False)
            message["content"] = replacement
            folded.append(
                FoldedMessage(
                    call_id=str(message.get("tool_call_id") or ""),
                    tool=str(payload.get("tool") or ""),
                    chars_before=len(content),
                    chars_after=len(replacement),
                    evidence_count=len(stub.get("evidence_index") or []),
                    model_content=replacement,
                )
            )
    return CompactionReport(
        folded=tuple(folded),
        batches_total=len(batches),
        batches_kept=min(keep, len(batches)),
    )


__all__ = [
    "COMPACTED_NOTE",
    "DEFAULT_KEEP_BATCHES",
    "HISTORY_COMPACTION_ENV",
    "HISTORY_KEEP_BATCHES_ENV",
    "CompactionReport",
    "FoldedMessage",
    "compact_history",
    "history_compaction_enabled",
    "history_keep_batches",
]
