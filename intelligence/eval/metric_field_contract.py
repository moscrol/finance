"""§9.3 观测指标 ↔ benchmark 产物字段的一一对表（可执行契约）。

起因：2026-08-17 一天之内三次撞同一个形状——**分析做到一半才发现数据不在产物里**。

1. `claims[].source_ids` 全空（是链路不是漏记），据此误判 evidence-bound「算不出来」；
2. `claims` 与 `citations` 在各 `stop_reason` 上几乎互斥；
3. cancel/resume/restart 事件恒 0、tool denied/invalid 无细分。

三次都不是分析方法的问题，是**产物契约没有单一真源**：spec §9.3 列指标，
benchmark 写产物，两边各自演进、中间无对账。本模块就是那次对账，
并且**由测试钉住**——§9.3 加一条指标而这里没登记，测试转红。

口径纪律（都是踩出来的）：

- **顶层没有列 ≠ 抽不出来。** 首轮超时、Trace 条数对账都要从
  ``diagnostics.events`` 里推，不能只看臂级字段。
- **不能用臂级终态算 repair 恢复。** 进入 ``repair_goal`` 的 21 条里，
  14 条修完后臂级 ``stop_reason`` 被诚实闸改写成 ``numeric_lineage_gap``；
  用终态会把恢复率从 8/21 算成 1/21。
- **空事件不是「通过」。** 崩溃臂事件为空时 ``0 == 0 + 0`` 会让条数对账假通过，
  必须先判 `has_events`。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

Status = Literal["top_level", "derived_from_events", "unavailable"]

_REPAIR_RECOVERED_FINISHES = frozenset(
    {"repair_model_finish", "repair_model_stop", "model_finish"}
)


@dataclass(frozen=True)
class MetricField:
    """一条 §9.3 指标的产物落点。"""

    spec_name: str          # §9.3 里的原文，逐字一致，测试按它对表
    block: str              # 领域质量 / Runtime 质量 / 工程成本
    status: Status
    locator: str            # 字段路径或推导说明
    resolver: Callable[[dict], Any] | None
    note: str = ""
    blocks_window: bool = False   # 开 900 之前是否必须先补


def _events(arm: dict) -> list[dict]:
    ev = (arm.get("diagnostics") or {}).get("events") or []
    return [e for e in ev if isinstance(e, dict)]


def _finishes(arm: dict) -> list[dict]:
    return [e for e in _events(arm) if (e.get("kind") or e.get("event")) == "finish"]


# ── 领域质量 ────────────────────────────────────────────────────────────
def _evidence_bound_output_rate(arm: dict) -> float | None:
    """输出级绑定，载体是 ``diagnostics.bindings``，**不是** ``claims[].source_ids``。

    ⚠ 2026-08-17 实测：组内方差恒 0（诚实闸桶恒 1.0、model_finish 桶恒 0.0），
    是阶跃函数不是带噪声的连续量；另有约半数记录 bindings 为空、指标未定义。
    返回 ``None`` 表示未定义——**调用方必须显式决定计 0 还是排除**，
    两种算法给出的数差很远。
    """
    b = [x for x in ((arm.get("diagnostics") or {}).get("bindings") or []) if isinstance(x, dict)]
    if not b:
        return None
    return sum(1 for x in b if x.get("evidence_hashes")) / len(b)


def _published_with_citations(arm: dict) -> float:
    """§9.4 护栏实际在量的东西（2026-08-17 按实测改名后的口径）。"""
    return 1.0 if (arm.get("claims") and arm.get("citations")) else 0.0


def _semantic_status(arm: dict) -> str | None:
    return arm.get("semantic_status")


# ── Runtime 质量 ───────────────────────────────────────────────────────
def _first_turn_timeout(arm: dict) -> bool | None:
    """第一条 finish 是否 ``deadline_exhausted``。无事件返回 None，不算 False。"""
    fs = _finishes(arm)
    if not fs:
        return None
    payload = fs[0].get("payload") or fs[0]
    return payload.get("stop_reason") == "deadline_exhausted"


def _repair_recovery(arm: dict) -> bool | None:
    """进入 repair 的臂是否恢复。**按事件判，不按臂级 stop_reason。**

    未进入 repair 返回 None（不进分母）。
    """
    ev = _events(arm)
    if not any((e.get("kind") or e.get("event")) == "repair_goal" for e in ev):
        return None
    fs = _finishes(arm)
    if not fs:
        return False
    payload = fs[-1].get("payload") or fs[-1]
    return payload.get("stop_reason") in _REPAIR_RECOVERED_FINISHES


def _wall_time(arm: dict) -> float | None:
    v = arm.get("latency_seconds")
    return float(v) if isinstance(v, (int, float)) else None


def _trace_reconciled(arm: dict) -> bool | None:
    """``tool_request`` 条数是否等于 ``tool_result`` + ``tool_error``。

    ⚠ 无事件返回 None：崩溃臂 ``0 == 0 + 0`` 会假通过。
    ⚠ 只对得上**条数**；按 ``call_id`` 逐一配对是另一件事（#68 上 19/45 对不齐）。
    """
    ev = _events(arm)
    if not ev:
        return None
    kinds = [(e.get("kind") or e.get("event")) for e in ev]
    return kinds.count("tool_request") == kinds.count("tool_result") + kinds.count("tool_error")


# 工具错误码——invalid / denied / failed 三类**本来就分得开**，
# 2026-08-17 初版把它记成「分不开」，是只看了事件 kind（都叫 tool_error）
# 没看事件里的 error 码。这是当天第三次同形误判，前两次是「常驻 worker 不存在」
# 与「evidence-bound 算不出来」。**判「有没有 X」要看到值那一层，不是类型那一层。**
TOOL_ERROR_INVALID = frozenset({"invalid_arguments", "duplicate_query", "duplicate_call_id"})
TOOL_ERROR_DENIED = frozenset({"unknown_or_unauthorized_tool"})


def _tool_error_codes(arm: dict) -> tuple[str, ...] | None:
    """该臂出现过的 tool 错误码。空事件返 None，无错误返空元组。

    分类：``TOOL_ERROR_INVALID`` / ``TOOL_ERROR_DENIED`` / 其余算 failed
    （``tool_timeout`` / ``tool_budget_exhausted`` / ``cancelled`` …）。
    """
    ev = _events(arm)
    if not ev:
        return None
    out: list[str] = []
    for e in ev:
        if (e.get("kind") or e.get("event")) != "tool_error":
            continue
        payload = e.get("payload") or e
        code = payload.get("error")
        if code:
            out.append(str(code))
    return tuple(out)


def _stage_durations(arm: dict) -> dict[str, float] | None:
    """分阶段耗时：事件带 ``at``，工具层另有 ``queued_ms`` / ``elapsed_ms``。

    2026-08-17 初版记成「没有字段，只有总 latency」——错。
    ``episode_tool_batch`` 的注释早写明「排队时长与执行时长**分开**记」。
    """
    ev = _events(arm)
    if not ev:
        return None
    queued = 0.0
    elapsed = 0.0
    for e in ev:
        payload = e.get("payload") or e
        if isinstance(payload.get("queued_ms"), (int, float)):
            queued += float(payload["queued_ms"])
        if isinstance(payload.get("elapsed_ms"), (int, float)):
            elapsed += float(payload["elapsed_ms"])
    stamped = sum(1 for e in ev if (e.get("payload") or e).get("at"))
    return {"queued_ms": queued, "elapsed_ms": elapsed, "events_with_at": float(stamped)}


CONTRACT: tuple[MetricField, ...] = (
    # ── 领域质量 ──
    MetricField(
        "task fulfillment", "领域质量", "top_level",
        "arm['structural_status'] / arm['status']", lambda a: a.get("structural_status"),
    ),
    MetricField(
        "evidence-bound output rate", "领域质量", "top_level",
        "arm['diagnostics']['bindings'][*].evidence_hashes", _evidence_bound_output_rate,
        note="输出级；阶跃函数、约半数未定义。护栏用，不配主检验样本量。"
             "另见 §9.4 改名后的实际口径 _published_with_citations。",
    ),
    MetricField(
        "unsupported numeric/date claim count", "领域质量", "unavailable",
        "闸前 claims 未落盘", None,
        note="过闸后 claims 用闸模板重算，material_numeric 全 0；闸前仅在 "
             "protocol_issues 留 C 号。恢复字面含义须做 T-F 选项 5d。",
        blocks_window=False,   # 护栏侧，不阻塞开窗（spec §9.4.2）
    ),
    MetricField(
        "counterpoint/gap honesty", "领域质量", "top_level",
        "arm['diagnostics']['gaps'] / ['missing_outputs']",
        lambda a: (a.get("diagnostics") or {}).get("gaps"),
    ),
    MetricField(
        "semantic verifier pass/repaired/rejected", "领域质量", "top_level",
        "arm['semantic_status']", _semantic_status,
    ),
    # ── Runtime 质量 ──
    MetricField(
        "tool invalid/denied/failed rate", "Runtime 质量", "derived_from_events",
        "events[tool_error].payload.error 的错误码", _tool_error_codes,
        note="三类分得开：invalid=invalid_arguments/duplicate_*；denied="
             "unknown_or_unauthorized_tool；其余算 failed。"
             "⚠ #68 那 45 条只出现过 tool_budget_exhausted(6)/tool_timeout(2)——"
             "**是那批样本没触发，不是分不开**。",
    ),
    MetricField(
        "first model turn timeout rate", "Runtime 质量", "derived_from_events",
        "第一条 finish 的 stop_reason == deadline_exhausted", _first_turn_timeout,
        note="顶层无列但事件里可推。空事件返 None，不得计 False。",
    ),
    MetricField(
        "repair recovery rate", "Runtime 质量", "derived_from_events",
        "进入 repair_goal 的臂，末条 finish 是否在恢复集合内", _repair_recovery,
        note="⚠ 不得用臂级 stop_reason：诚实闸会改写终态，8/21 会被算成 1/21。",
    ),
    MetricField(
        "P50/P95 wall time", "Runtime 质量", "top_level",
        "arm['latency_seconds']", _wall_time,
        note="45/45 完整，连续量，主检验用。",
    ),
    MetricField(
        "input/output token 和每个阶段耗时", "Runtime 质量", "derived_from_events",
        "token：写手侧 arm['input_tokens'] / continuous-episode.json 的 outcome.usage；"
        "判官侧 metrics.judge_usage{calls,input_tokens,output_tokens,usage_source}"
        "（INDEX #23 起写入，usage_source ∈ api/cli/estimated/mixed）；"
        "阶段耗时=events 的 at / queued_ms / elapsed_ms",
        _stage_durations,
        note="阶段耗时**可推**（272/307 事件带 at，queued_ms 57、elapsed_ms 55，"
             "排队与执行本就分开记）。⚠ token 缺口分两层：写手侧 `input_tokens` 仅 29/45，"
             "缺失机制需说明后才可入功效表；判官侧此前**完全没有账**，2026-09-05 起由 "
             "`metrics.judge_usage` 补上（读者 `intelligence/eval/research_cost.py`；"
             "旧 run 无此键，报表计入「判官未记账」不回填不估；估算记录带 `estimated` 标记）。",
    ),
    MetricField(
        "Arm B 的跨语言桥接耗时，单独记录，不并入 Runtime 耗时", "Runtime 质量", "unavailable",
        "Arm B 已降级为静态形状对照（§9.1）", None,
        note="随 Arm B 降级作废，不需要补。",
    ),
    MetricField(
        "cancel、resume、restart 的成功率", "Runtime 质量", "unavailable",
        "事件里 0/45", None,
        note="#68 未做 §9.2 的失败注入。要判必须先注入，否则该项永远无数据。",
        blocks_window=True,
    ),
    MetricField(
        "Trace 与事件对账完整率", "Runtime 质量", "derived_from_events",
        "tool_request 条数 == tool_result + tool_error", _trace_reconciled,
        note="⚠ 空事件返 None。按 call_id 逐一配对是另一件事，#68 上 19/45 对不齐——"
             "但**工具已存在**：`intelligence/eval/normalize_harness_trace.py` 的 "
             "`normalize_records` / `compare_sequences`（含 correlation_id / source_event_id）。"
             "先用它复核那 19 条，再判要不要补记录。",
    ),
    # ── 工程成本（人工统计，不从产物抽）──
    MetricField("Adapter 代码量", "工程成本", "unavailable", "人工统计", None,
                note="随 Arm B 降级，本轮不需要。"),
    MetricField("新增领域工具的接入代码量", "工程成本", "unavailable", "人工统计", None),
    MetricField("TypeScript/Python 双份契约数量", "工程成本", "unavailable", "人工统计", None,
                note="随 Arm B 降级，本轮不需要。"),
    MetricField("部署依赖和冷启动时间", "工程成本", "unavailable", "人工统计", None),
    MetricField("运行时故障定位所需步骤", "工程成本", "unavailable", "人工统计", None),
)


def blocking_gaps() -> tuple[MetricField, ...]:
    """开 900 之前必须先补记录的项。"""
    return tuple(m for m in CONTRACT if m.blocks_window)


def by_spec_name() -> dict[str, MetricField]:
    return {m.spec_name: m for m in CONTRACT}


_STATUS_LABEL = {
    "top_level": "✅ 顶层字段",
    "derived_from_events": "🔧 需从 events 推导",
    "unavailable": "❌ 产物里没有",
}


def render_report(rows: list[dict] | None = None) -> str:
    """把对表渲染成 Markdown。``rows`` 给了就顺带跑一遍 resolver 报覆盖率。

    这是本模块的人类读取面：**表不进 git 就会漂**，所以由代码生成而不是手写
    （BUILD.md「单一真本源且生成」）。
    """

    out = ["| §9.3 指标 | 块 | 状态 | 落点 | 备注 |", "|---|---|---|---|---|"]
    for m in CONTRACT:
        mark = "⛔ " if m.blocks_window else ""
        note = m.note.replace("\n", " ").strip()
        out.append(
            f"| {m.spec_name} | {m.block} | {mark}{_STATUS_LABEL[m.status]} "
            f"| `{m.locator}` | {note} |"
        )
    gaps = blocking_gaps()
    if gaps:
        out.append("")
        out.append(f"**开窗前必须补记录的 {len(gaps)} 项**：")
        out += [f"- {m.spec_name} —— {m.note}" for m in gaps]
    if rows:
        out.append("")
        out.append("| 指标 | 可判/总数 |")
        out.append("|---|---|")
        for m in CONTRACT:
            if m.resolver is None:
                continue
            defined = sum(1 for a in rows if m.resolver(a) is not None)
            out.append(f"| {m.spec_name} | {defined}/{len(rows)} |")
    return "\n".join(out)
