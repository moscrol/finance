"""能力 frontier 向量：把一次 run 的落盘工件投影成七个轴，不把「能力 max」当一个数看。

来源：2026-09-07 对 #615–#618「先探能力 max，再按越线加约束」路线的六层巡检，第 4 条建议
「建立能力 frontier 向量，不把 max 当单一数字：工具发现、证据产出、上下文效率、修复恢复、
验证完整性、墙钟、分支健康度」。同日候选口四遍 + 8792 一遍同题重跑证明：`completed / judge repaired`
只说明终局链闭合——第 2 遍父臂墙钟剩 396s 却因账本口径 `deadline_exhausted`，第 1、3 遍分支 6/6 收尾被
`unknown_output` 拒而证据照旧回流；这些都在同一个 `completed` 标签底下。七个轴把它们拆开。

只读现有字段（`continuous-episode.json` / `report.json` / `run.json`），确定性、无副作用、不调模型。
字段缺席就是 ``None``，不写 0 把「没测到」伪装成读数——与 ``runtime/sub_research.BranchBatch`` 同一条纪律。
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

SUB_RESEARCH_TOOL = "sub_research"
_ACCEPTED_FINISH_STOP_REASONS = frozenset({"model_finish", "repair_model_finish"})


@dataclass(frozen=True)
class ToolDiscovery:
    offered: int | None
    used_distinct: int
    parent_used: tuple[str, ...]
    branch_used: tuple[str, ...]

    @property
    def used_ratio(self) -> float | None:
        if not self.offered:
            return None
        return round(self.used_distinct / self.offered, 3)


@dataclass(frozen=True)
class EvidenceYield:
    parent_evidence: int | None
    branch_evidence: int
    bound_hashes: int | None


@dataclass(frozen=True)
class ContextEfficiency:
    input_tokens: int | None
    output_tokens: int | None
    llm_calls: int | None

    @property
    def input_tokens_per_llm_call(self) -> float | None:
        if self.input_tokens is None or not self.llm_calls:
            return None
        return round(self.input_tokens / self.llm_calls, 1)


@dataclass(frozen=True)
class RepairRecovery:
    status: str | None
    stop_reason: str | None
    repair_attempts: int | None
    repair_cycles: int | None

    @property
    def finish_accepted(self) -> bool | None:
        if self.stop_reason is None:
            return None
        return self.stop_reason in _ACCEPTED_FINISH_STOP_REASONS


@dataclass(frozen=True)
class Verification:
    verified_status: str | None
    judge_status: str | None
    judge_unavailable_count: int | None
    content_degraded_count: int | None


@dataclass(frozen=True)
class WallClock:
    episode_seconds: float | None
    sub_research_seconds: float | None
    ledger_remaining_seconds_at_finish: float | None
    root_seconds_before_branches: float | None
    root_seconds_after_branches: float | None

    @property
    def branches_charged_parent_seconds(self) -> float | None:
        """分支让父账本少了多少秒；口径 C（秒 = 墙钟、分支只扣次数）下应为 0。"""

        if self.root_seconds_before_branches is None or self.root_seconds_after_branches is None:
            return None
        return round(self.root_seconds_before_branches - self.root_seconds_after_branches, 3)


@dataclass(frozen=True)
class BranchHealth:
    count: int
    completed: int
    partial: int
    failed: int
    finish_accepted: int | None
    invalid_actions: int | None
    requested: int | None
    rejected_by_cap: int | None
    timed_out: int | None
    allocated_calls: int | None
    consumed_calls: int | None
    remaining_seconds: tuple[float, ...] = ()
    stop_reasons: tuple[str, ...] = ()
    invalid_action_codes: tuple[str, ...] = ()


@dataclass(frozen=True)
class FrontierVector:
    run_id: str
    revision: str | None
    tool_discovery: ToolDiscovery
    evidence_yield: EvidenceYield
    context_efficiency: ContextEfficiency
    repair_recovery: RepairRecovery
    verification: Verification
    wall_clock: WallClock
    branch_health: BranchHealth
    notes: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["tool_discovery"]["used_ratio"] = self.tool_discovery.used_ratio
        payload["context_efficiency"]["input_tokens_per_llm_call"] = (
            self.context_efficiency.input_tokens_per_llm_call
        )
        payload["repair_recovery"]["finish_accepted"] = self.repair_recovery.finish_accepted
        payload["wall_clock"]["branches_charged_parent_seconds"] = (
            self.wall_clock.branches_charged_parent_seconds
        )
        return payload


def _read_json_object(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _int_or_none(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return int(value)


def _float_or_none(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _parse_at(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _events(episode: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    raw = episode.get("events")
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict) and isinstance(item.get("payload"), dict)]


def _branch_terminals(events: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return [
        event["payload"]
        for event in events
        if event.get("kind") in {"branch_completed", "branch_failed"}
    ]


def _sub_research_result(events: Sequence[Mapping[str, Any]]) -> Mapping[str, Any] | None:
    for event in events:
        payload = event["payload"]
        if event.get("kind") == "tool_result" and payload.get("tool") == SUB_RESEARCH_TOOL:
            return payload
    return None


def _gate_receipt(report: Mapping[str, Any], episode: Mapping[str, Any]) -> Verification:
    receipt = report.get("gate_receipt") if isinstance(report.get("gate_receipt"), dict) else {}
    structural = episode.get("structural_verifier") if isinstance(episode.get("structural_verifier"), dict) else {}
    semantic = episode.get("semantic_verifier") if isinstance(episode.get("semantic_verifier"), dict) else {}
    verified = receipt.get("verified_status") or structural.get("verified_status")
    judge = receipt.get("judge_status") or semantic.get("judge_status")
    return Verification(
        verified_status=str(verified) if verified is not None else None,
        judge_status=str(judge) if judge is not None else None,
        judge_unavailable_count=_int_or_none(receipt.get("judge_unavailable_count")),
        content_degraded_count=_int_or_none(receipt.get("content_degraded_count")),
    )


def _branch_health(terminals: Sequence[Mapping[str, Any]]) -> BranchHealth:
    statuses = [str(item.get("status") or "") for item in terminals]
    stop_reasons = tuple(str(item.get("stop_reason") or "") for item in terminals)
    measured_finish = [reason for reason in stop_reasons if reason]
    invalid_lists = [item.get("invalid_actions") for item in terminals if "invalid_actions" in item]
    batches = [
        batch
        for item in terminals
        for batch in (item.get("batches") or [])
        if isinstance(batch, dict)
    ]
    budgets = [item.get("budget") for item in terminals if isinstance(item.get("budget"), dict)]
    has_trace = any("stop_reason" in item for item in terminals)
    codes = tuple(
        str(action.get("code") or "")
        for actions in invalid_lists
        if isinstance(actions, list)
        for action in actions
        if isinstance(action, dict) and action.get("code")
    )
    return BranchHealth(
        count=len(terminals),
        completed=statuses.count("completed"),
        partial=statuses.count("partial"),
        failed=statuses.count("failed"),
        finish_accepted=(
            sum(1 for reason in measured_finish if reason in _ACCEPTED_FINISH_STOP_REASONS)
            if has_trace
            else None
        ),
        # 摘要是 2026-09-07 才落盘的：旧 run 的 branch_completed 没有这些键，留 None 不写 0。
        invalid_actions=(
            sum(len(actions) for actions in invalid_lists if isinstance(actions, list))
            if has_trace
            else None
        ),
        requested=sum(_int_or_none(b.get("requested")) or 0 for b in batches) if batches else None,
        rejected_by_cap=sum(_int_or_none(b.get("rejected_by_cap")) or 0 for b in batches) if batches else None,
        timed_out=sum(_int_or_none(b.get("timed_out")) or 0 for b in batches) if batches else None,
        allocated_calls=sum(_int_or_none(b.get("allocated_calls")) or 0 for b in budgets) if budgets else None,
        consumed_calls=sum(_int_or_none(b.get("consumed_calls")) or 0 for b in budgets) if budgets else None,
        remaining_seconds=tuple(
            round(value, 1)
            for value in (_float_or_none(b.get("remaining_seconds")) for b in budgets)
            if value is not None
        ),
        stop_reasons=stop_reasons,
        invalid_action_codes=codes,
    )


def frontier_vector(run_dir: Path) -> FrontierVector:
    """把一个 run 目录投影成 frontier 向量。缺件不抛：能读到什么就投影什么。"""

    run_dir = Path(run_dir)
    episode = _read_json_object(run_dir / "continuous-episode.json")
    report = _read_json_object(run_dir / "report.json")
    run = _read_json_object(run_dir / "run.json")
    events = _events(episode)
    outcome = episode.get("outcome") if isinstance(episode.get("outcome"), dict) else {}
    usage = outcome.get("usage") if isinstance(outcome.get("usage"), dict) else {}
    contract = episode.get("contract") if isinstance(episode.get("contract"), dict) else {}
    terminals = _branch_terminals(events)
    sub_research = _sub_research_result(events)
    notes: list[str] = []

    offered_raw = contract.get("allowed_capabilities")
    offered = len(offered_raw) if isinstance(offered_raw, list) else None
    parent_used = tuple(
        dict.fromkeys(
            str(event["payload"].get("name") or "")
            for event in events
            if event.get("kind") == "tool_request" and event["payload"].get("name")
        )
    )
    branch_used = tuple(
        dict.fromkeys(
            str(tool)
            for item in terminals
            for batch in (item.get("batches") or [])
            if isinstance(batch, dict)
            for tool in (batch.get("tools") or [])
        )
    )
    used_distinct = len(set(parent_used) | set(branch_used))

    bindings = outcome.get("bindings")
    bound_hashes: int | None = None
    if isinstance(bindings, list):
        bound_hashes = len(
            {
                str(digest)
                for binding in bindings
                if isinstance(binding, dict)
                for digest in (binding.get("evidence_hashes") or [])
            }
        )
    evidence = outcome.get("evidence")
    parent_evidence = len(evidence) if isinstance(evidence, list) else None
    branch_evidence = sum(_int_or_none(item.get("evidence_count")) or 0 for item in terminals)

    stamps = [_parse_at(event["payload"].get("at")) for event in events]
    stamps = [stamp for stamp in stamps if stamp is not None]
    episode_seconds = (
        round((max(stamps) - min(stamps)).total_seconds(), 1) if len(stamps) >= 2 else None
    )
    sub_research_seconds = None
    root_before = root_after = None
    if sub_research is not None:
        elapsed_ms = _float_or_none(sub_research.get("elapsed_ms"))
        sub_research_seconds = round(elapsed_ms / 1000.0, 1) if elapsed_ms is not None else None
        telemetry = sub_research.get("telemetry") if isinstance(sub_research.get("telemetry"), dict) else {}
        root_budget = telemetry.get("root_budget") if isinstance(telemetry.get("root_budget"), dict) else {}
        before = root_budget.get("before") if isinstance(root_budget.get("before"), dict) else {}
        after = root_budget.get("after_branches") if isinstance(root_budget.get("after_branches"), dict) else {}
        root_before = _float_or_none(before.get("remaining_seconds"))
        root_after = _float_or_none(after.get("remaining_seconds"))
        if telemetry.get("refused_reason"):
            notes.append(f"sub_research refused: {telemetry.get('refused_reason')}")
    transitions = (episode.get("phase_trace") or {}).get("transitions") if isinstance(episode.get("phase_trace"), dict) else None
    ledger_remaining = None
    if isinstance(transitions, list) and transitions and isinstance(transitions[-1], dict):
        ledger_remaining = _float_or_none(transitions[-1].get("remaining_seconds"))
        if ledger_remaining is not None:
            ledger_remaining = round(ledger_remaining, 1)

    wall = WallClock(
        episode_seconds=episode_seconds,
        sub_research_seconds=sub_research_seconds,
        ledger_remaining_seconds_at_finish=ledger_remaining,
        root_seconds_before_branches=root_before,
        root_seconds_after_branches=root_after,
    )
    if (
        wall.ledger_remaining_seconds_at_finish is not None
        and wall.ledger_remaining_seconds_at_finish <= 0.0
        and str(outcome.get("stop_reason") or "") == "deadline_exhausted"
    ):
        notes.append("ledger seconds exhausted (stop_reason=deadline_exhausted): check wall clock vs ledger")
    health = _branch_health(terminals)
    if health.invalid_action_codes:
        notes.append("branch finish rejected: " + ",".join(sorted(set(health.invalid_action_codes))))
    unaccepted = sorted(
        {reason for reason in health.stop_reasons if reason and reason not in _ACCEPTED_FINISH_STOP_REASONS}
    )
    if unaccepted:
        notes.append("branch stop_reasons not accepted: " + ",".join(unaccepted))

    revision = None
    receipt = report.get("gate_receipt") if isinstance(report.get("gate_receipt"), dict) else {}
    if isinstance(receipt.get("rev"), str) and receipt.get("rev"):
        revision = str(receipt["rev"])[:12]

    return FrontierVector(
        run_id=str(run.get("run_id") or run_dir.name),
        revision=revision,
        tool_discovery=ToolDiscovery(
            offered=offered,
            used_distinct=used_distinct,
            parent_used=parent_used,
            branch_used=branch_used,
        ),
        evidence_yield=EvidenceYield(
            parent_evidence=parent_evidence,
            branch_evidence=branch_evidence,
            bound_hashes=bound_hashes,
        ),
        context_efficiency=ContextEfficiency(
            input_tokens=_int_or_none(usage.get("input_tokens")),
            output_tokens=_int_or_none(usage.get("output_tokens")),
            llm_calls=_int_or_none(usage.get("llm_calls")),
        ),
        repair_recovery=RepairRecovery(
            status=str(outcome.get("status")) if outcome.get("status") is not None else None,
            stop_reason=str(outcome.get("stop_reason")) if outcome.get("stop_reason") is not None else None,
            repair_attempts=_int_or_none(episode.get("repair_attempts")),
            repair_cycles=_int_or_none(episode.get("repair_cycles")),
        ),
        verification=_gate_receipt(report, episode),
        wall_clock=wall,
        branch_health=health,
        notes=tuple(notes),
    )


_MD_COLUMNS: tuple[tuple[str, str], ...] = (
    ("run", "run_id"),
    ("rev", "revision"),
    ("status/stop", "status_stop"),
    ("judge", "judge"),
    ("tools used/offered", "tools"),
    ("evidence parent+branch/bound", "evidence"),
    ("input tok / llm", "context"),
    ("repair", "repair"),
    ("episode s / sub_research s / ledger left", "clock"),
    ("branches ok/partial/fail · accepted · invalid · cap rej/req", "branches"),
    ("branch→parent s", "charged"),
)


def _md_cells(vector: FrontierVector) -> dict[str, str]:
    td, ey, ce, rr, ve, wc, bh = (
        vector.tool_discovery,
        vector.evidence_yield,
        vector.context_efficiency,
        vector.repair_recovery,
        vector.verification,
        vector.wall_clock,
        vector.branch_health,
    )

    def show(value: Any) -> str:
        return "—" if value is None else str(value)

    return {
        "run_id": vector.run_id,
        "revision": show(vector.revision),
        "status_stop": f"{show(rr.status)} / {show(rr.stop_reason)}",
        "judge": f"{show(ve.judge_status)} (unavail {show(ve.judge_unavailable_count)}, degraded {show(ve.content_degraded_count)})",
        "tools": (
            f"{td.used_distinct}/{show(td.offered)} "
            f"(父 {len(td.parent_used)} · 支 {len(td.branch_used)})"
        ),
        "evidence": f"{show(ey.parent_evidence)}+{ey.branch_evidence}/{show(ey.bound_hashes)}",
        "context": f"{show(ce.input_tokens)} / {show(ce.llm_calls)}",
        "repair": f"{show(rr.repair_attempts)} attempt(s)",
        "clock": f"{show(wc.episode_seconds)} / {show(wc.sub_research_seconds)} / {show(wc.ledger_remaining_seconds_at_finish)}",
        "branches": (
            f"{bh.completed}/{bh.partial}/{bh.failed} · {show(bh.finish_accepted)} · {show(bh.invalid_actions)} · "
            f"{show(bh.rejected_by_cap)}/{show(bh.requested)}"
        ),
        "charged": show(wc.branches_charged_parent_seconds),
    }


def render_markdown(vectors: Sequence[FrontierVector]) -> str:
    header = "| " + " | ".join(label for label, _ in _MD_COLUMNS) + " |"
    rule = "|" + "|".join("---" for _ in _MD_COLUMNS) + "|"
    rows = []
    for vector in vectors:
        cells = _md_cells(vector)
        rows.append("| " + " | ".join(cells[key] for _, key in _MD_COLUMNS) + " |")
    lines = [header, rule, *rows]
    notes = [f"- {vector.run_id}: {note}" for vector in vectors for note in vector.notes]
    if notes:
        lines.extend(["", *notes])
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="把 workbench run 目录投影成能力 frontier 向量（只读工件，不调模型）。",
    )
    parser.add_argument("run_dirs", nargs="+", type=Path)
    parser.add_argument("--format", choices=("json", "md"), default="md")
    args = parser.parse_args(argv)
    vectors = [frontier_vector(path) for path in args.run_dirs]
    if args.format == "json":
        print(json.dumps([vector.to_dict() for vector in vectors], ensure_ascii=False, indent=2))
    else:
        print(render_markdown(vectors))
    return 0


__all__ = [
    "BranchHealth",
    "ContextEfficiency",
    "EvidenceYield",
    "FrontierVector",
    "RepairRecovery",
    "ToolDiscovery",
    "Verification",
    "WallClock",
    "frontier_vector",
    "render_markdown",
    "main",
]


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
