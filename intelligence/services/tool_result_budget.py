"""Budget one tool observation before it enters the model's context.

This is layer 1 of the layered compaction design (see the roadmap's Phase 1
notes): large tool output is persisted in full, and the context keeps a bounded
preview plus a pointer back to the full record.

The precondition already holds here, which is why this layer is cheap for us:
``_EpisodeAccumulator`` hands the same ``public_observation`` to two sinks.

    ledger.add("tool_result", payload)   → continuous-episode.json  (audit)
    messages.append({"role": "tool"})    → the model's context      (budgeted)

So the full observation is already durable.  Only the context copy needs a
bound, and only the *prose* inside it: truncating identifiers would turn
compaction into evidence destruction.

Never truncated, because the roadmap's red line requires 来源 / 时点 / 状态 /
缺口 / 完整性 to survive any compaction:

- ``evidence_hashes`` and each item's ``content_hash`` — the binding gate
  resolves citations against these.  Dropping one does not make the answer
  shorter, it makes the gate unsatisfiable.  (The model itself never sees them:
  ``strip_hashes_for_model`` swaps them for E-numbers one step later, because a
  model transcribing a 16-hex digest gets it wrong.  We preserve them for the
  pipeline, not for the prompt — hence ``context_budget`` names E-numbers.)
- ``source`` / ``source_date`` / ``freshness`` / ``evidence_tier`` — a claim
  without its time and tier is not a shorter claim, it is a different one.
- ``gaps`` — the thing the answer must disclose.
- ``supports`` / ``contradicts`` — dropping a contradiction silently upgrades
  a contested finding into a clean one.

Truncated: the free-text ``observation`` narrative and each evidence item's
``title`` / ``detail``.  Those survive in the ledger, so an *auditor* can
recover them — the model cannot, and this module must not imply otherwise.

Callers must put qualifiers (口径/使用要求/截断提示) **before** the content they
qualify.  This module clips from the head of a string, so a qualifier appended
last is the first thing to go — and it is precisely the part with no second
copy in ``evidence``.  ``episode_tools`` and ``agent_research`` own that
ordering; see the field measurement recorded there.

Deterministic on purpose.  The reduction is a pure function of its input, with
no model call, clock, or randomness, so the same observation always yields the
same bytes.  A provider's prompt cache keys on the exact prefix; a preview that
varied per call would invalidate the cache on every resume and cost more than
the tokens it saved.

Layer 1b（2026-09-07，spec ``2026-09-07-episode-history-compaction-design.md`` §3.1）：
``lean_tool_observation`` 去掉**空值**与 ``independent_key``。上面的红线一条不破——
一条非空的 ``contradicts`` 仍在、非空的 ``freshness`` 仍在；被去掉的是 ``"supports": []``
``"contradicts": []`` ``"evidence_tier": ""`` ``"source_date": "None"`` 这类每条都带、
但不携带任何信息的键，以及只给校验器判来源独立性用的 ``independent_key``（宪法与绑定
都不引用它）。同题 17 个 run 实测：sub_research 那条 5.2 万字的 evidence JSON 里 2/3 是
这种脚手架；红线内可去掉的合计 −21%。缺省关（``ASK_EPISODE_LEAN_OBSERVATION``），A/B 拍板后翻。
"""

from __future__ import annotations

import os
from typing import Any, Mapping

LEAN_OBSERVATION_ENV = "ASK_EPISODE_LEAN_OBSERVATION"
# 顶层这些键在空的时候对模型没有信息量（hash 已由 strip_hashes_for_model 换成 E 号）。
_LEAN_TOP_LEVEL_WHEN_EMPTY = frozenset(
    {"evidence_hashes", "payload_field_names", "payload_sha256", "dataset", "caliber"}
)
# 每条证据里只给校验器用、模型从不引用的键。
_LEAN_EVIDENCE_DROP = frozenset({"independent_key"})
_EMPTY_VALUES: tuple[object, ...] = ("", "None", None)


def lean_observation_enabled() -> bool:
    raw = str(os.environ.get(LEAN_OBSERVATION_ENV) or "").strip().lower()
    return raw in {"on", "1", "true", "yes"}


def _is_empty(value: object) -> bool:
    if value in _EMPTY_VALUES:
        return True
    return isinstance(value, (list, tuple, dict)) and len(value) == 0


def lean_tool_observation(payload: Mapping[str, Any]) -> dict[str, Any]:
    """去掉模型视图里的空值与 ``independent_key``；非空字段一个不动。

    与 ``budget_tool_observation`` 同样是纯函数、不动输入。红线（来源 / 时点 / 分档 /
    缺口 / 非空的 supports·contradicts·freshness）全部保留：空列表不是「没有矛盾」的
    声明，只是这条证据没有被标注过。
    """

    leaned: dict[str, Any] = {}
    for key, value in payload.items():
        if key in _LEAN_TOP_LEVEL_WHEN_EMPTY and _is_empty(value):
            continue
        leaned[key] = value
    raw_evidence = payload.get("evidence")
    if isinstance(raw_evidence, list):
        items: list[Any] = []
        for item in raw_evidence:
            if not isinstance(item, Mapping):
                items.append(item)
                continue
            items.append(
                {
                    key: value
                    for key, value in item.items()
                    if key not in _LEAN_EVIDENCE_DROP and not _is_empty(value)
                }
            )
        leaned["evidence"] = items
    return leaned

# ``agent_research`` reads the same constant so the two engines bound their
# context the same way.
#
# 2026-10-06 calibration (user decision: lift every bound that limits the
# model).  The old 900 / 240 / 120 clipped 28% of observations and every long
# evidence row; Pi, given the same tools on the same database, saw them whole
# and answered better.  Measured over Pi's 134 tool calls (harness-arms v5):
# observation p95 2210 / max 3000, evidence detail p95 223 / max 619.  The new
# bounds sit above those maxima, so a normal tool result reaches the model
# unclipped; they remain a guard only against pathological outputs.
MAX_OBSERVATION_CHARS = 4000
MAX_EVIDENCE_DETAIL_CHARS = 800
MAX_EVIDENCE_TITLE_CHARS = 300

# Where a reader can recover what was elided.  Named, not a bare "truncated"
# flag: "there was more" without "and here is where it is" is not auditable.
FULL_RECORD_ARTIFACT = "continuous-episode.json"

_ELLIPSIS = "…"


def _clip(value: object, limit: int) -> tuple[object, int]:
    """Return the clipped value and how many characters were dropped.

    A non-``str`` value passes through untouched rather than becoming ``""``.
    Coercing it would delete data while reporting ``omitted_chars == 0``, so no
    ``context_budget`` marker would be attached and the model could not tell the
    field had been emptied — the exact failure this module exists to prevent.
    Same pass-through rule as a non-``Mapping`` evidence item.
    """

    if not isinstance(value, str):
        return value, 0
    text = value
    if len(text) <= limit:
        return text, 0
    # Reserve one character for the marker so the result never exceeds ``limit``
    # and a reader can see the value is partial without consulting metadata.
    kept = max(0, limit - 1)
    return text[:kept] + _ELLIPSIS, len(text) - kept


def _evidence_read_enabled() -> bool:
    # Lazy import: the reader uses this module's shared observation bound.
    from intelligence.services.evidence_read import evidence_read_enabled
    return evidence_read_enabled()


def budget_tool_observation(
    payload: Mapping[str, Any],
    *,
    max_observation_chars: int = MAX_OBSERVATION_CHARS,
    max_detail_chars: int = MAX_EVIDENCE_DETAIL_CHARS,
    max_title_chars: int = MAX_EVIDENCE_TITLE_CHARS,
) -> dict[str, Any]:
    """Bound the prose in one tool observation, preserving every identifier.

    Returns a new dict; the input is never mutated, so the caller can keep
    handing the untouched payload to its audit sink.

    When nothing exceeded its bound the result carries no completeness
    metadata, so an unbudgeted observation stays byte-identical to what the
    model saw before this layer existed.
    """

    budgeted = dict(payload)
    omitted_chars = 0

    observation, dropped = _clip(payload.get("observation"), max_observation_chars)
    omitted_chars += dropped
    if "observation" in payload:
        budgeted["observation"] = observation

    raw_evidence = payload.get("evidence")
    if isinstance(raw_evidence, list):
        items: list[Any] = []
        for item in raw_evidence:
            if not isinstance(item, Mapping):
                items.append(item)
                continue
            projected = dict(item)
            title, title_dropped = _clip(item.get("title"), max_title_chars)
            detail, detail_dropped = _clip(item.get("detail"), max_detail_chars)
            omitted_chars += title_dropped + detail_dropped
            if "title" in item:
                projected["title"] = title
            if "detail" in item:
                projected["detail"] = detail
            items.append(projected)
        budgeted["evidence"] = items

    if omitted_chars:
        # Tell the model it is reading a preview and that the elision was prose
        # only.  Without this it cannot distinguish "the tool found little" from
        # "the harness showed me little", and may re-run the same query.
        #
        # ``preserved`` and ``instruction`` are **model-facing**: this dict only
        # ever rides the model copy (``agent_episode`` hands the untouched
        # payload to the ledger before budgeting).  So they must describe what
        # the model still holds after the *whole* pipeline, not what this
        # function alone declined to clip.  ``strip_hashes_for_model`` runs
        # immediately after us and removes ``evidence_hashes`` /
        # ``content_hash`` on purpose — a model copying a 16-hex digest gets it
        # wrong, which is why bindings use the E-numbers instead.  Naming the
        # hashes here pointed the model at fields it does not have, and at a
        # recovery path that does not exist: no tool in the registry accepts a
        # hash or an evidence id as an argument.  Keep this list in sync with
        # ``episode_protocol.strip_hashes_for_model``; the pairing is pinned by
        # ``test_context_budget_names_only_model_visible_fields``.
        #
        # 2026-09-11: 「取不回来」只对「按证据编号 / 哈希取」成立。cap02 落地后存在一条
        # 真实的节级重读路径：``agent_research.deep_read_evidence`` 把命中页整节按
        # ``kb_rag.DEEP_READ_ITEM_CHARS``（与本文件 detail 上限同值）切成段级证据，并在
        # 观察值里给出「同页其余章节」目录。指令里只说「取不回」会教模型放弃一条
        # 存在的动作，所以这里把那条路径写明（blocked/02 B-1 建议②）。
        budgeted["context_budget"] = {
            "truncated": True,
            "omitted_chars": omitted_chars,
            # Where an auditor — not the model — recovers the elided prose.
            "full_record_in": FULL_RECORD_ARTIFACT,
            "preserved": [
                "evidence_id",
                "source",
                "source_date",
                "evidence_tier",
                "freshness",
                "supports",
                "contradicts",
                "gaps",
            ],
            "instruction": (
                "叙述已按上下文预算截断，被截的只有自由文本；"
                "证据编号、来源、时点、分级与缺口都完整。"
                "不要因为叙述变短而重复同一次查询——重查得到的是同一份预览。"
                "引用时用证据编号（E1、E2…），不要誊抄哈希。"
                + (
                    "若本轮菜单提供 evidence_read，可自选按 E 编号分页补读原始标题或正文；"
                    "它不新增来源或事实日期，仍计工具预算。工具 observation 叙述不在该补读范围。"
                    "没有该菜单项时不能按编号补读；不等于源里没有。"
                    if _evidence_read_enabled() else
                    "被截掉的原文没有工具能按证据编号取回，但不等于没有返回："
                )
                +
                "kb_search 命中页的整节会另以「深读《章节名》N/M」段落送来（每段完整不截），"
                "观察值里还有「同页其余章节」目录——缺哪一节就用 kb_search 检索「页名 章节名」"
                "把那节读出来。还不够再换更窄的查询，或把它写成缺口。"
            ),
        }

    return budgeted


__all__ = [
    "FULL_RECORD_ARTIFACT",
    "MAX_EVIDENCE_DETAIL_CHARS",
    "MAX_EVIDENCE_TITLE_CHARS",
    "MAX_OBSERVATION_CHARS",
    "budget_tool_observation",
]
