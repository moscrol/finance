"""Layer 2 of layered compaction: delete noise, do not summarize.

Layer 1 (``tool_result_budget``) bounds *length*.  This layer bounds *density*:
debug keys and a narrative that already appeared in this episode are removed
outright.  Summarizing noise would spend tokens to keep tokens.

It runs on the model-facing copy only.  The audit ledger keeps the full
observation, same split as layer 1.  The function is pure: same payload plus
the same set of already-seen prose fingerprints always yields the same bytes.

Deletions are declared.  The marker is inserted *before* the remaining fields
so a later length bound cannot drop the qualifier and leave the body
(the 「预算 + 声明式截断」pattern: qualifier precedes the qualified content).

Unknown keys stay.  If a field might carry a claim, it is not on the drop
list — the failure mode of deleting evidence identity is worse than leaving
a few extra tokens.
"""

from __future__ import annotations

from collections.abc import Mapping, Set
from typing import Any

# ---------------------------------------------------------------------------
# 田野调查（episode 投影，2026-08-22）
#
# 模型在两次调用之间真正看到的，是 ``agent_episode`` 组的 public_observation，
# 不是 ToolObservation dataclass 全文（trace 不进模型；telemetry 已在入口 pop）：
#
#   顶层: ok, tool, query, observation, evidence, evidence_hashes,
#         evidence_ids, gaps, dataset, caliber, payload_field_names,
#         payload_sha256
#   证据项 (public_agent_evidence + evidence_id):
#         tool, title, detail, source, source_date, evidence_tier,
#         supports, contradicts, independent_key, freshness,
#         content_hash, evidence_id
#
# payload_* / caliber 来自 tool_payload_meta：显式「Never row values」，
# 给评测归因 retrieve vs synthesize，不是一条主张。
# ---------------------------------------------------------------------------

# 可删：确认不承载证据身份 / 主张。每键一句理由。拿不准的不要进这张表。
DROPPABLE_KEYS: dict[str, str] = {
    "payload_field_names": (
        "评测用列清单，不含单元格，不是一条主张；ledger 已留全文。"
    ),
    "payload_sha256": (
        "列清单哈希，不是 evidence_hashes，模型无法用来绑定引用。"
    ),
    "caliber": (
        "物理表名，给评测归因 retrieve/synthesize，不是盘面事实。"
    ),
    "telemetry": (
        "控制面送达收据；入口已 pop，这里再删一次防止漏网。"
    ),
}

# 必须留：合同红线 + 田野调查里拿不准是否承载证据的键。每键一句理由。
MUST_KEEP_KEYS: dict[str, str] = {
    "ok": "成败状态；模型要区分空结果和工具失败。",
    "tool": "工具名，标识符；绑定和重试都靠它。",
    "query": "本次查询原文，标识「这是哪一次」；不是样板叙述。",
    "observation": "叙述本身；仅在与前次规范化后完全相同时替换为声明标记。",
    "evidence": "证据列表；项内身份字段不得丢。",
    "evidence_hashes": "合同红线：绑定门禁的内容主键。",
    "evidence_ids": "模型绑定用序号 E1..En；丢掉会让 finalize 对不上。",
    "gaps": "合同红线：必须披露的缺口。",
    "dataset": "查了哪张公开表；拿不准是否帮助解读数值，留下。",
    "source": "来源标签，主张的出处。",
    "source_date": "合同红线：时点。没有时点的主张是另一条主张。",
    "evidence_tier": "证据层级；丢掉会把 L1 和 L4 混成同一种东西。",
    "supports": "合同红线：这条证据支持哪些输出。",
    "contradicts": "合同红线：丢掉会把有争议的发现静默升级成干净结论。",
    "independent_key": "独立来源键，标识符。",
    "freshness": "时新性标签，和 source_date 一起构成时点身份。",
    "content_hash": "单条证据内容主键；strip_hashes 之前仍在副本里。",
    "evidence_id": "单条证据序号，标识符。",
    "title": "证据标题；可能是主张的一部分，不当前层可删键。",
    "detail": "证据正文；同上，只截长度（第 1 层），不删键。",
}

COLLAPSED_OBSERVATION_MARK = "噪声剪枝：本段叙述与前次观察重复，已删除。"

_NOISE_PRUNE_INSTRUCTION = (
    "已删除调试字段或重复叙述；标识与证据身份未动。不要因此重查。"
)


def normalize_observation_prose(text: str) -> str:
    """Strip all whitespace so layout-only copies compare equal.

    Exact match after this transform — no edit distance, no embedding.
    """

    return "".join(text.split())


def _fingerprint_observation(payload: Mapping[str, Any]) -> str:
    raw = payload.get("observation")
    if not isinstance(raw, str):
        return ""
    return normalize_observation_prose(raw)


def prune_tool_observation(
    payload: Mapping[str, Any],
    *,
    seen_prose: Set[str] = frozenset(),
) -> tuple[dict[str, Any], frozenset[str]]:
    """Drop debug keys and collapse a duplicate observation narrative.

    Returns a new dict plus the updated fingerprint set.  ``payload`` and
    ``seen_prose`` are never mutated.

    When nothing was dropped the result is a shallow copy that compares
    equal to ``dict(payload)`` and carries no ``noise_prune`` marker, so an
    already-clean observation stays byte-identical for the provider cache.
    """

    dropped_keys = [
        key for key in DROPPABLE_KEYS if key in payload
    ]
    fingerprint = _fingerprint_observation(payload)
    collapse_observation = bool(fingerprint) and fingerprint in seen_prose

    updated = set(seen_prose)
    if fingerprint:
        updated.add(fingerprint)

    if not dropped_keys and not collapse_observation:
        return dict(payload), frozenset(updated)

    # Qualifier first — a later char budget must not keep the body and
    # drop the sentence that says the body is incomplete.
    pruned: dict[str, Any] = {
        "noise_prune": {
            "dropped_keys": dropped_keys,
            "collapsed_prose": collapse_observation,
            "instruction": _NOISE_PRUNE_INSTRUCTION,
        }
    }
    for key, value in payload.items():
        if key in DROPPABLE_KEYS:
            continue
        if key == "observation" and collapse_observation:
            pruned[key] = COLLAPSED_OBSERVATION_MARK
            continue
        pruned[key] = value

    return pruned, frozenset(updated)


__all__ = [
    "COLLAPSED_OBSERVATION_MARK",
    "DROPPABLE_KEYS",
    "MUST_KEEP_KEYS",
    "normalize_observation_prose",
    "prune_tool_observation",
]
