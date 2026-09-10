"""研究进展账（06 号单）：底座按批记「这一轮有没有带来新东西」，递给模型，停滞到底时收口。

为什么要有它：连续 Episode 里模型每轮只看到本批工具的原始观察和 ``runtime_budget``
（剩几次、剩几秒）。「刚才那次检索有没有新证据」「同一个查询已经试了几遍」「哪个工具
连续空手」这些事实底座都知道，但此前一句都没告诉模型——2026-09-07 D5 那题 20 轮 19 次
调用、同题七遍工具消息稳定 8–12 万字，变量就是模型在原地重复。

只递事实与建议码，不写领域规则：新证据按 ``content_hash`` 相对已有证据去重算，重复查询按
「同工具 + 归一化查询」算，空手按工具连续计。建议码（``switch_query`` / ``switch_tool`` /
``stalled`` / ``follow_up_divergences``）由这些计数确定性推出；模型仍自己决定下一步——
这是 steering，不是授权，也不改预算。唯一的硬动作是「连续 N 批零新证据且已有证据」时
关研究阶段（``finalization.reason = research_stalled``），N 由
``WORKBENCH_RESEARCH_STALL_FINALIZE_BATCHES`` 控。**缺省 0 = 只提醒不收口**：既有 loop
测试用固定 hash 的假工具跑满预算（每批都是 duplicate），默认收口会把「预算 6 次」改成
4 次；收口该不该开、开几批，等候选臂 live 读数（06 号单 progress/06.md）再定。

注入通道复用 ``runtime_budget``（叠在最后一条 tool 消息上、由 ``tool_budget_state`` 事件
承载）：不新增事件种类、不改派生规则，INV-R1 对账逐字节照旧。
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
import json
import os
import re
from threading import RLock

PROGRESS_ENV = "WORKBENCH_RESEARCH_PROGRESS"
STALL_FINALIZE_ENV = "WORKBENCH_RESEARCH_STALL_FINALIZE_BATCHES"
DEFAULT_STALL_FINALIZE_BATCHES = 0
# 连续几批零新证据开始把 ``stalled`` 写进建议（先提醒、再收口）。
STALL_STEER_BATCHES = 2
# 同一「工具 + 查询」第几次仍无新证据算重复。
REPEAT_QUERY_THRESHOLD = 2
# 一个工具连续几次空手 / 重复算「该换工具」。
TOOL_EMPTY_STREAK_THRESHOLD = 2
_MAX_QUERY_CHARS = 120
_MAX_LAST_BATCH_ROWS = 8
_MAX_ALTERNATIVES = 4

CallStatus = str  # "new" | "duplicate" | "empty" | "error" | "timeout" | "rejected"
_NO_PROGRESS_STATUSES = frozenset({"duplicate", "empty", "error", "timeout", "rejected"})


def progress_enabled() -> bool:
    return os.environ.get(PROGRESS_ENV, "on").strip().lower() not in {"0", "false", "off"}


def stall_finalize_batches() -> int:
    raw = os.environ.get(STALL_FINALIZE_ENV, "").strip()
    if not raw:
        return DEFAULT_STALL_FINALIZE_BATCHES
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_STALL_FINALIZE_BATCHES
    return max(0, value)


def normalize_query(value: object) -> str:
    """归一化查询键：压空白、小写、截长。只用于比较，不回灌给模型。"""

    if isinstance(value, Mapping):
        query = value.get("query")
        if isinstance(query, str) and query.strip():
            value = query
        else:
            goals = value.get("goals")
            if isinstance(goals, (list, tuple)) and goals:
                value = " | ".join(str(item) for item in goals)
            else:
                value = json.dumps(value, ensure_ascii=False, sort_keys=True) if value else ""
    text = re.sub(r"\s+", " ", str(value or "")).strip().lower()
    return text[:_MAX_QUERY_CHARS]


@dataclass(frozen=True)
class ToolCallDigest:
    """一次工具调用相对「此前已有证据」的结果形状。"""

    tool: str
    query: str
    status: CallStatus
    new_evidence: int = 0
    total_evidence: int = 0

    def __post_init__(self) -> None:
        if self.status not in {"new", *_NO_PROGRESS_STATUSES}:
            raise ValueError(f"unknown call digest status: {self.status!r}")
        object.__setattr__(self, "tool", str(self.tool or "").strip())
        object.__setattr__(self, "query", normalize_query(self.query))
        object.__setattr__(self, "new_evidence", max(0, int(self.new_evidence)))
        object.__setattr__(self, "total_evidence", max(0, int(self.total_evidence)))

    @property
    def result_label(self) -> str:
        if self.status == "new":
            return f"new:{self.new_evidence}"
        return self.status


@dataclass(frozen=True)
class BatchDigest:
    index: int
    calls: tuple[ToolCallDigest, ...]

    @property
    def new_evidence(self) -> int:
        return sum(call.new_evidence for call in self.calls)

    @property
    def executed(self) -> int:
        return sum(1 for call in self.calls if call.status != "rejected")


@dataclass(frozen=True)
class BranchDigest:
    branch_id: str
    goal: str
    status: str
    evidence: int
    gaps: int
    error: str = ""


@dataclass
class _QueryAttempts:
    attempts: int = 0
    last_new_evidence: int = 0


class ResearchProgressTracker:
    """按批累计的进展账。线程安全：分支回调在批执行器工作线程里记。"""

    def __init__(self, *, stall_finalize_batches: int | None = None) -> None:
        self._lock = RLock()
        self._pending: list[ToolCallDigest] = []
        self.batches: list[BatchDigest] = []
        self.branches: list[BranchDigest] = []
        self._branches_since_last_view = False
        self._refused_reason = ""
        self._query_attempts: dict[tuple[str, str], _QueryAttempts] = {}
        self._tool_empty_streak: dict[str, int] = {}
        self.stalled_batches = 0
        self.evidence_total = 0
        self._finalize_after = (
            stall_finalize_batches
            if stall_finalize_batches is not None
            else stall_finalize_batches_default()
        )

    # ── 记账 ──────────────────────────────────────────────────────────────

    def record_call(self, digest: ToolCallDigest) -> None:
        with self._lock:
            self._pending.append(digest)

    def close_batch(self) -> BatchDigest | None:
        """把本轮所有调用（含空池回退那一发）合成一批。没有调用就不记批。"""

        with self._lock:
            if not self._pending:
                return None
            batch = BatchDigest(index=len(self.batches) + 1, calls=tuple(self._pending))
            self._pending = []
            self.batches.append(batch)
            for call in batch.calls:
                key = (call.tool, call.query)
                attempts = self._query_attempts.setdefault(key, _QueryAttempts())
                attempts.attempts += 1
                attempts.last_new_evidence = call.new_evidence
                if call.new_evidence > 0:
                    self._tool_empty_streak[call.tool] = 0
                elif call.status in _NO_PROGRESS_STATUSES:
                    self._tool_empty_streak[call.tool] = (
                        self._tool_empty_streak.get(call.tool, 0) + 1
                    )
            self.evidence_total += batch.new_evidence
            if batch.new_evidence > 0:
                self.stalled_batches = 0
            else:
                self.stalled_batches += 1
            return batch

    def record_branches(
        self,
        branches: Iterable[object],
        *,
        refused_reason: str = "",
    ) -> None:
        digests: list[BranchDigest] = []
        for branch in branches:
            digests.append(
                BranchDigest(
                    branch_id=str(getattr(branch, "branch_id", "") or ""),
                    goal=str(getattr(branch, "goal", "") or "")[:_MAX_QUERY_CHARS],
                    status=str(getattr(branch, "status", "") or ""),
                    evidence=len(tuple(getattr(branch, "evidence", ()) or ())),
                    gaps=len(tuple(getattr(branch, "gaps", ()) or ())),
                    error=str(getattr(branch, "error", "") or "")[:200],
                )
            )
        with self._lock:
            self.branches.extend(digests)
            self._branches_since_last_view = True
            self._refused_reason = str(refused_reason or "")

    def note_external_input(self) -> None:
        """用户改方向（收件箱认领）后从零计停滞：新方向的第一批不该被记成原地踏步。"""

        with self._lock:
            self.stalled_batches = 0

    # ── 读数 ──────────────────────────────────────────────────────────────

    @property
    def last_batch(self) -> BatchDigest | None:
        with self._lock:
            return self.batches[-1] if self.batches else None

    def repeated_queries(self) -> tuple[dict[str, object], ...]:
        with self._lock:
            rows = [
                {"tool": tool, "query": query, "attempts": item.attempts}
                for (tool, query), item in self._query_attempts.items()
                if item.attempts >= REPEAT_QUERY_THRESHOLD and item.last_new_evidence == 0
            ]
        rows.sort(key=lambda row: (-int(row["attempts"]), str(row["tool"]), str(row["query"])))
        return tuple(rows[:_MAX_LAST_BATCH_ROWS])

    def empty_tools(self) -> tuple[tuple[str, int], ...]:
        with self._lock:
            return tuple(
                sorted(
                    (
                        (tool, streak)
                        for tool, streak in self._tool_empty_streak.items()
                        if streak >= TOOL_EMPTY_STREAK_THRESHOLD
                    ),
                    key=lambda item: (-item[1], item[0]),
                )
            )

    def should_finalize(self) -> bool:
        """连续 N 批零新证据且已有证据在手 → 关研究阶段。零证据不收口（没东西可写）。"""

        with self._lock:
            return (
                self._finalize_after > 0
                and self.evidence_total > 0
                and self.stalled_batches >= self._finalize_after
            )

    def suggestions(self, *, available_tools: Sequence[str] = ()) -> tuple[str, ...]:
        codes: list[str] = []
        if self.repeated_queries():
            codes.append("switch_query")
        exhausted = self.empty_tools()
        if exhausted:
            stale = {tool for tool, _ in exhausted}
            alternatives = [
                name
                for name in available_tools
                if name not in stale and name != "sub_research"
            ][:_MAX_ALTERNATIVES]
            for tool, _streak in exhausted[:3]:
                suffix = f"→{','.join(alternatives)}" if alternatives else ""
                codes.append(f"switch_tool:{tool}{suffix}")
        with self._lock:
            stalled = self.stalled_batches
            branches_pending = self._branches_since_last_view
            failed_branches = [
                item.branch_id
                for item in self.branches
                if item.status not in {"completed", "partial"}
            ]
        if stalled >= STALL_STEER_BATCHES:
            codes.append("stalled")
        if branches_pending:
            codes.append("follow_up_divergences")
            for branch_id in failed_branches:
                codes.append(f"branch_failed:{branch_id}")
        return tuple(dict.fromkeys(codes))

    def model_view(
        self,
        *,
        available_tools: Sequence[str] = (),
        tools_short_of_window: Sequence[str] = (),
    ) -> dict[str, object]:
        """给模型看的进展块。字段都是事实或确定性推出的建议码；``instruction`` 是短句。"""

        # 建议码先算：它要读「分支摘要是否还没给模型看过」这个标记，下面才把它清掉。
        codes = self.suggestions(available_tools=available_tools)
        with self._lock:
            batch = self.batches[-1] if self.batches else None
            stalled = self.stalled_batches
            evidence_total = self.evidence_total
            branches = tuple(self.branches) if self._branches_since_last_view else ()
            refused = self._refused_reason if self._branches_since_last_view else ""
            self._branches_since_last_view = False
            finalize_after = self._finalize_after
        view: dict[str, object] = {
            "batch": batch.index if batch is not None else 0,
            "new_evidence": batch.new_evidence if batch is not None else 0,
            "evidence_total": evidence_total,
            "stalled_batches": stalled,
        }
        if batch is not None:
            view["last_batch"] = [
                {"tool": call.tool, "query": call.query, "result": call.result_label}
                for call in batch.calls[:_MAX_LAST_BATCH_ROWS]
            ]
        repeated = self.repeated_queries()
        if repeated:
            view["repeated_queries"] = list(repeated)
        if branches:
            view["branches"] = [
                {
                    "branch_id": item.branch_id,
                    "goal": item.goal,
                    "status": item.status,
                    "evidence": item.evidence,
                    "gaps": item.gaps,
                    **({"error": item.error} if item.error else {}),
                }
                for item in branches
            ]
            if refused:
                view["branches_refused"] = refused
        short = [str(name) for name in tools_short_of_window if str(name).strip()]
        if short:
            view["tools_short_of_window"] = short
        if codes:
            view["suggestion"] = list(codes)
        view["instruction"] = self._instruction(
            codes,
            stalled=stalled,
            finalize_after=finalize_after,
            short_tools=short,
        )
        return view

    @staticmethod
    def _instruction(
        codes: Sequence[str],
        *,
        stalled: int,
        finalize_after: int,
        short_tools: Sequence[str],
    ) -> str:
        parts = [
            "research_progress 是底座按批记的事实：new_evidence 是本轮相对已有证据的新增条数，"
            "repeated_queries 是同一工具同一查询重复且没有新证据的记录。"
        ]
        if "switch_query" in codes:
            parts.append(
                "重复同一查询不会带来新证据：下一轮改写查询词（换实体名、别名、时间窗或更具体的事实），"
                "或换一个工具查同一缺口。"
            )
        switch_tools = [code for code in codes if code.startswith("switch_tool:")]
        if switch_tools:
            described = "；".join(
                code.removeprefix("switch_tool:").replace("→", " 连续空手，可换 ")
                for code in switch_tools
            )
            parts.append(f"{described}；换不到证据就把该缺口写成 gap，不要再点同一个工具。")
        if "stalled" in codes:
            parts.append(
                f"已连续 {stalled} 批没有新证据：只针对仍未覆盖的必需输出再补查一次；"
                "已经够回答的部分直接写进结论，补不到的写明确 gap。"
            )
            if finalize_after > 0 and stalled >= finalize_after - 1:
                parts.append("再一批没有新证据，研究阶段将自动关闭并进入收口。")
        if "follow_up_divergences" in codes:
            parts.append(
                "分支已回证据：只对分支之间不一致、互相矛盾或空手的子问题补查，"
                "不重复分支已完成的取证；失败的分支是没研究过，不是没有答案。"
            )
        if short_tools:
            parts.append(
                f"{'、'.join(short_tools)} 在剩余时间窗里装不下（会超时白烧一轮），下一轮不要点它们。"
            )
        return "".join(parts)


def stall_finalize_batches_default() -> int:
    return stall_finalize_batches()


__all__ = [
    "BatchDigest",
    "BranchDigest",
    "DEFAULT_STALL_FINALIZE_BATCHES",
    "PROGRESS_ENV",
    "REPEAT_QUERY_THRESHOLD",
    "STALL_FINALIZE_ENV",
    "STALL_STEER_BATCHES",
    "TOOL_EMPTY_STREAK_THRESHOLD",
    "ResearchProgressTracker",
    "ToolCallDigest",
    "normalize_query",
    "progress_enabled",
    "stall_finalize_batches",
]
