"""Private self-use event ledger for the Workbench maturity gate."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import tempfile
from collections.abc import Sequence
from dataclasses import asdict, dataclass, replace
from datetime import date, datetime
from pathlib import Path
from typing import Literal, cast

from intelligence.services.run_store import STATUS_COMPLETED, RunStore, redact


Workflow = Literal[
    "daily_market",
    "theme_research",
    "stock_research",
    "news_impact",
    "watchlist",
]
Outcome = Literal["success", "degraded", "failed"]

WORKFLOWS: frozenset[str] = frozenset(
    {
        "daily_market",
        "theme_research",
        "stock_research",
        "news_impact",
        "watchlist",
    }
)
OUTCOMES: frozenset[str] = frozenset({"success", "degraded", "failed"})
MINIMUM_TRADE_DATES = 10
SELF_USE_LLM_PROVIDER = "zhipu"
SELF_USE_LLM_MODEL = "glm-5.2"

# 一个 run 判定为「模型未参与 / 回退到模板」的降级标记（见
# conversation_orchestrator：LLM 不可用时写入 run.degrades）。绑定校验拒绝它。
LLM_FALLBACK_DEGRADE = "llm_unavailable_template_answer"

# 阻塞项的稳定合同顺序：数据真实性（日历/绑定）在前，成熟度阈值在后。
BLOCKER_ORDER: tuple[str, ...] = (
    "trading_calendar_unavailable",
    "non_trading_day",
    "future_trade_date",
    "non_contiguous_streak",
    "minimum_trade_dates",
    "missing_workflows",
    "success_rate",
    "severe_fact_error",
    "manual_rescue_rate",
    "useful_rate",
)


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _coerce_today(today: date | str | None) -> date:
    if today is None:
        return date.today()
    if isinstance(today, date):
        return today
    return date.fromisoformat(str(today).strip())


def trading_days_from_duckdb(db_path: str | Path) -> list[str]:
    """从本地 DuckDB 读取 canonical A 股交易日历（distinct fact_stock_daily.trade_date）。

    复用 evolution.validate.trading_calendar，作为唯一交易日来源。数据库不存在或
    表缺失时返回空列表——上层据此 fail-closed（标记 trading_calendar_unavailable）。
    """
    path = Path(db_path)
    if not path.exists():
        return []
    import duckdb  # 局部导入：避免给不碰 DuckDB 的调用方增加依赖
    from evolution.validate import trading_calendar

    con = duckdb.connect(str(path), read_only=True)
    try:
        return list(trading_calendar(con))
    except Exception:
        return []
    finally:
        con.close()


@dataclass(frozen=True)
class SelfUseEvent:
    trade_date: str
    workflow: Workflow
    outcome: Outcome
    manual_rescue: bool
    severe_fact_error: bool
    useful: bool
    note: str = ""
    run_id: str | None = None
    recorded_at: str | None = None
    schema_version: int = 1

    def validated(self, *, generate_recorded_at: bool = True) -> SelfUseEvent:
        if type(self.schema_version) is not int or self.schema_version != 1:
            raise ValueError(f"invalid schema_version: {self.schema_version!r}")
        if not isinstance(self.trade_date, str):
            raise ValueError("trade_date must be an ISO date string")
        trade_date = self.trade_date.strip()
        try:
            parsed_trade_date = date.fromisoformat(trade_date)
        except ValueError as exc:
            raise ValueError(f"invalid trade_date: {self.trade_date!r}") from exc
        if parsed_trade_date.isoformat() != trade_date:
            raise ValueError(f"invalid trade_date: {self.trade_date!r}")
        if not isinstance(self.workflow, str):
            raise ValueError("workflow must be a string")
        workflow = self.workflow.strip()
        if workflow not in WORKFLOWS:
            raise ValueError(f"invalid workflow: {self.workflow!r}")
        if not isinstance(self.outcome, str):
            raise ValueError("outcome must be a string")
        outcome = self.outcome.strip()
        if outcome not in OUTCOMES:
            raise ValueError(f"invalid outcome: {self.outcome!r}")
        for field_name in ("manual_rescue", "severe_fact_error", "useful"):
            if type(getattr(self, field_name)) is not bool:
                raise ValueError(f"{field_name} must be a boolean")
        if not isinstance(self.note, str):
            raise ValueError("note must be a string")
        if self.run_id is not None and not isinstance(self.run_id, str):
            raise ValueError("run_id must be a string or None")

        note = redact(self.note.strip())[:1000]
        run_id = redact(self.run_id.strip()) if self.run_id is not None else None
        if run_id == "":
            run_id = None

        if self.recorded_at is not None and not isinstance(self.recorded_at, str):
            raise ValueError("recorded_at must be an ISO datetime string or None")
        if self.recorded_at is None and not generate_recorded_at:
            raise ValueError("recorded_at is required when loading a persisted event")
        recorded_at = self.recorded_at.strip() if self.recorded_at is not None else _now_iso()
        try:
            parsed_recorded_at = datetime.fromisoformat(recorded_at)
        except ValueError as exc:
            raise ValueError(f"invalid recorded_at: {self.recorded_at!r}") from exc
        if parsed_recorded_at.tzinfo is None or parsed_recorded_at.utcoffset() is None:
            raise ValueError("recorded_at must include a timezone offset")

        return replace(
            self,
            trade_date=trade_date,
            workflow=cast(Workflow, workflow),
            outcome=cast(Outcome, outcome),
            note=note,
            run_id=run_id,
            recorded_at=recorded_at,
        )


@dataclass(frozen=True)
class MaturityResult:
    metrics: dict[str, float | int | list[str]]
    blockers: tuple[str, ...]
    eligible_for_user_decision: bool
    user_approved: bool
    passed: bool
    fingerprint: str = ""


def dedupe_events(events: Sequence[SelfUseEvent]) -> list[SelfUseEvent]:
    """幂等去重：同一个 (run_id, trade_date, workflow) 只计一次。

    重复摄入同一个 run/日期/工作流不得稀释成功率/有用率（gap 3）。已绑定的事件都带
    唯一 run_id；缺 run_id 的历史/探索事件退化为按 (trade_date, workflow) 去重。
    保留首次出现，保持顺序稳定。
    """
    result: list[SelfUseEvent] = []
    seen: set[tuple[str | None, str, str]] = set()
    for event in events:
        key = (event.run_id, event.trade_date, event.workflow)
        if key in seen:
            continue
        seen.add(key)
        result.append(event)
    return result


def _calendar_blockers(
    trade_dates: set[str],
    *,
    trading_days: Sequence[str] | None,
    today: date,
    require_consecutive_trading_days: bool,
) -> list[str]:
    """校验去重后的交易日：canonical 交易日、非未来，以及可选的连续性政策。"""
    blockers: list[str] = []
    if trading_days is None or len(trading_days) == 0:
        # 无法拿到 canonical 日历 → fail-closed，不冒充已校验。
        blockers.append("trading_calendar_unavailable")
        return blockers

    index = {day: position for position, day in enumerate(trading_days)}
    if any(day not in index for day in trade_dates):
        blockers.append("non_trading_day")
    if any(date.fromisoformat(day) > today for day in trade_dates):
        blockers.append("future_trade_date")

    canonical = sorted(day for day in trade_dates if day in index)
    if require_consecutive_trading_days and len(canonical) >= 2:
        positions = [index[day] for day in canonical]
        if positions[-1] - positions[0] + 1 != len(positions):
            blockers.append("non_contiguous_streak")
    return blockers


def eligibility_fingerprint(result: MaturityResult) -> str:
    """对裁决相关快照做 canonical 指纹（sha256）。

    审批记录绑定到该指纹；台账一旦变化（指标/阻塞项/裁决态改变），旧审批的指纹将
    对不上，从而失效——避免「批一次、永久通过」。
    """
    snapshot = {
        "metrics": result.metrics,
        "blockers": list(result.blockers),
        "eligible_for_user_decision": result.eligible_for_user_decision,
    }
    canonical = json.dumps(snapshot, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def evaluate_maturity(
    events: Sequence[SelfUseEvent],
    *,
    trading_days: Sequence[str] | None,
    today: date | str | None = None,
    user_approved: bool = False,
    require_consecutive_trading_days: bool = False,
) -> MaturityResult:
    """Evaluate deterministic self-use maturity without mutating the ledger.

    ``trading_days`` 是 canonical A 股交易日历（升序）；``None``/空表示不可用，据此
    fail-closed。事件先去重（幂等），再按去重后集合计算指标与阈值。
    """

    if type(user_approved) is not bool:
        raise TypeError("user_approved must be a boolean")
    if type(require_consecutive_trading_days) is not bool:
        raise TypeError("require_consecutive_trading_days must be a boolean")
    resolved_today = _coerce_today(today)
    validated_events = dedupe_events([event.validated() for event in events])
    event_count = len(validated_events)
    trade_dates = {event.trade_date for event in validated_events}
    covered_workflows = sorted({event.workflow for event in validated_events})
    success_count = sum(event.outcome == "success" for event in validated_events)
    useful_count = sum(event.useful for event in validated_events)
    manual_rescue_count = sum(event.manual_rescue for event in validated_events)
    severe_fact_errors = sum(event.severe_fact_error for event in validated_events)

    def rate(numerator: int) -> float:
        return round(numerator / event_count, 6) if event_count else 0.0

    metrics: dict[str, float | int | list[str]] = {
        "distinct_trade_dates": len(trade_dates),
        "covered_workflows": covered_workflows,
        "core_success_rate": rate(success_count),
        "useful_rate": rate(useful_count),
        "manual_rescue_rate": rate(manual_rescue_count),
        "severe_fact_errors": severe_fact_errors,
        "event_count": event_count,
    }

    blockers: set[str] = set(
        _calendar_blockers(
            trade_dates,
            trading_days=trading_days,
            today=resolved_today,
            require_consecutive_trading_days=require_consecutive_trading_days,
        )
    )
    if len(trade_dates) < MINIMUM_TRADE_DATES:
        blockers.add("minimum_trade_dates")
    if set(covered_workflows) != WORKFLOWS:
        blockers.add("missing_workflows")
    if not event_count or success_count * 100 < event_count * 95:
        blockers.add("success_rate")
    if severe_fact_errors:
        blockers.add("severe_fact_error")
    if event_count and manual_rescue_count * 100 > event_count * 5:
        blockers.add("manual_rescue_rate")
    if not event_count or useful_count * 100 < event_count * 80:
        blockers.add("useful_rate")

    blocker_tuple = tuple(name for name in BLOCKER_ORDER if name in blockers)
    eligible_for_user_decision = not blocker_tuple
    result = MaturityResult(
        metrics=metrics,
        blockers=blocker_tuple,
        eligible_for_user_decision=eligible_for_user_decision,
        user_approved=user_approved,
        passed=eligible_for_user_decision and user_approved,
    )
    return replace(result, fingerprint=eligibility_fingerprint(result))


class SelfUseLedgerIntegrityError(ValueError):
    """A JSONL row cannot be decoded into a valid persisted event."""


def _atomic_replace(path: Path, data: bytes) -> None:
    """临时文件 + fsync + os.replace 原子落盘（调用方须已持有文件锁）。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
        directory_fd = os.open(
            path.parent,
            os.O_RDONLY | getattr(os, "O_DIRECTORY", 0),
        )
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


class SelfUseLedger:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.lock_path = self.path.with_name(f".{self.path.name}.lock")

    def record(self, event: SelfUseEvent) -> SelfUseEvent:
        validated = event.validated()
        line = json.dumps(asdict(validated), ensure_ascii=False) + "\n"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock_path.open("a+b") as lock_handle:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
            existing = self.path.read_bytes() if self.path.exists() else b""
            separator = b"\n" if existing and not existing.endswith(b"\n") else b""
            _atomic_replace(self.path, existing + separator + line.encode("utf-8"))
        return validated

    def _load_bytes(self, raw: bytes) -> list[SelfUseEvent]:
        if not raw:
            return []
        events: list[SelfUseEvent] = []
        for line_number, line in enumerate(raw.decode("utf-8").splitlines(), start=1):
            try:
                payload = json.loads(line)
                if not isinstance(payload, dict):
                    raise TypeError("event row must be a JSON object")
                event = SelfUseEvent(**payload).validated(generate_recorded_at=False)
            except Exception as exc:
                raise SelfUseLedgerIntegrityError(
                    f"invalid self-use ledger {self.path} at JSONL line {line_number}"
                ) from exc
            events.append(event)
        return events

    def record_once(self, event: SelfUseEvent) -> SelfUseEvent:
        validated = event.validated()
        identity = (validated.run_id, validated.trade_date, validated.workflow)
        line = json.dumps(asdict(validated), ensure_ascii=False) + "\n"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock_path.open("a+b") as lock_handle:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
            existing = self.path.read_bytes() if self.path.exists() else b""
            for persisted in self._load_bytes(existing):
                if (persisted.run_id, persisted.trade_date, persisted.workflow) == identity:
                    return persisted
            separator = b"\n" if existing and not existing.endswith(b"\n") else b""
            _atomic_replace(self.path, existing + separator + line.encode("utf-8"))
        return validated

    def load(self) -> list[SelfUseEvent]:
        raw = self.path.read_bytes() if self.path.exists() else b""
        return self._load_bytes(raw)


# --------------------------------------------------------------------------
# gap 2：把台账事件绑定到真实、终态成功、模型确有参与、且留有 SSE/报告证据的 run。
# --------------------------------------------------------------------------


class RunBindingError(ValueError):
    """A self-use event does not bind to a valid, terminal-success, LLM-backed run."""


@dataclass(frozen=True)
class RunEvidence:
    run_id: str
    status: str
    llm_used: bool
    llm_provider: str
    llm_model: str
    report_as_of: str
    stream_event_count: int


def verify_run_binding(
    run_store: RunStore,
    run_id: str | None,
    *,
    expected_provider: str = SELF_USE_LLM_PROVIDER,
    expected_model: str = SELF_USE_LLM_MODEL,
) -> RunEvidence:
    """校验 ``run_id`` 绑定到一个真实、终态成功、llm.used=true 且留证据的 Workbench run。

    拒绝：缺失/伪造 run_id、非终态或非成功 run、模型未参与/回退（llm.used!=true 或
    命中回退降级标记）、以及缺 SSE/报告证据的 run。任一不满足抛 ``RunBindingError``。
    """
    if not isinstance(run_id, str) or not run_id.strip():
        raise RunBindingError("self-use event must bind to a Workbench run_id")
    run_id = run_id.strip()

    try:
        run = run_store.load_run(run_id)
    except FileNotFoundError as exc:
        raise RunBindingError(f"run not found: {run_id}") from exc
    except (ValueError, OSError, json.JSONDecodeError, TypeError) as exc:
        raise RunBindingError(f"run not loadable: {run_id}") from exc

    if run.status != STATUS_COMPLETED:
        raise RunBindingError(
            f"run {run_id} is not terminal-successful (status={run.status})"
        )
    if LLM_FALLBACK_DEGRADE in run.degrades:
        raise RunBindingError(f"run {run_id} degraded to a template answer (model unused)")

    report_path = run_store.run_dir(run_id) / "report.json"
    if not report_path.exists():
        raise RunBindingError(f"run {run_id} has no report.json evidence")
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RunBindingError(f"run {run_id} report.json unreadable") from exc
    if not isinstance(report, dict):
        raise RunBindingError(f"run {run_id} report.json must be an object")
    if report.get("report_id") != run_id:
        raise RunBindingError(f"run {run_id} report_id is not bound to the run")
    if report.get("status") != STATUS_COMPLETED:
        raise RunBindingError(f"run {run_id} report is not completed")
    report_as_of = report.get("as_of")
    if not isinstance(report_as_of, str):
        raise RunBindingError(f"run {run_id} report as_of is not an ISO date")
    try:
        parsed_as_of = date.fromisoformat(report_as_of)
    except ValueError as exc:
        raise RunBindingError(f"run {run_id} report as_of is not an ISO date") from exc
    if parsed_as_of.isoformat() != report_as_of:
        raise RunBindingError(f"run {run_id} report as_of is not an ISO date")

    llm_meta = report.get("llm")
    llm_used = bool(isinstance(llm_meta, dict) and llm_meta.get("used") is True)
    if not llm_used:
        raise RunBindingError(f"run {run_id} report metadata does not assert llm.used=true")
    provider = str(llm_meta.get("provider") or "")
    model = str(llm_meta.get("model") or "")
    if provider != expected_provider or model != expected_model:
        raise RunBindingError(
            f"run {run_id} model binding mismatch "
            f"(expected {expected_provider}/{expected_model}, got {provider or '-'}/{model or '-'})"
        )

    try:
        stream_events = run_store.load_stream_events(run_id)
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        raise RunBindingError(f"run {run_id} stream evidence unreadable") from exc
    if not stream_events:
        raise RunBindingError(f"run {run_id} has no SSE/stream evidence")
    report_events = [
        event for event in stream_events if event.get("event_type") == "report.complete"
    ]
    if not report_events:
        raise RunBindingError(f"run {run_id} has no report.complete stream evidence")
    streamed_report = report_events[-1].get("payload", {}).get("report")
    if not isinstance(streamed_report, dict) or streamed_report.get("report_id") != run_id:
        raise RunBindingError(f"run {run_id} streamed report is not bound to the run")
    if streamed_report.get("status") != STATUS_COMPLETED:
        raise RunBindingError(f"run {run_id} streamed report is not completed")
    if any(
        streamed_report.get(field) != report.get(field)
        for field in ("report_id", "status", "as_of", "llm")
    ):
        raise RunBindingError(f"run {run_id} streamed report does not match report.json")

    return RunEvidence(
        run_id=run_id,
        status=run.status,
        llm_used=llm_used,
        llm_provider=provider,
        llm_model=model,
        report_as_of=report_as_of,
        stream_event_count=len(stream_events),
    )


def ingest_self_use_event(
    ledger: SelfUseLedger,
    event: SelfUseEvent,
    *,
    run_store: RunStore,
    trading_days: Sequence[str] | None,
    today: date | str | None = None,
) -> SelfUseEvent:
    """校验并幂等写入一条自用事件。

    - gap 1：``trade_date`` 必须是 canonical A 股交易日且非未来；
    - gap 2：``run_id`` 必须绑定真实、终态成功、模型参与、留证据的 run；
    - gap 3：同一 (run_id, trade_date, workflow) 已入库则跳过，不重复计数。
    """
    validated = event.validated()

    resolved_today = _coerce_today(today)
    if trading_days is None or len(trading_days) == 0:
        raise ValueError("trading calendar unavailable; cannot validate trade_date")
    if validated.trade_date not in set(trading_days):
        raise ValueError(f"trade_date is not a canonical trading day: {validated.trade_date}")
    if date.fromisoformat(validated.trade_date) > resolved_today:
        raise ValueError(f"trade_date is in the future: {validated.trade_date}")

    evidence = verify_run_binding(run_store, validated.run_id)
    if evidence.report_as_of != validated.trade_date:
        raise RunBindingError(
            f"run {evidence.run_id} report as_of {evidence.report_as_of} "
            f"does not match trade_date {validated.trade_date}"
        )
    return ledger.record_once(validated)


# --------------------------------------------------------------------------
# gap 5：把用户审批持久化为可审计记录（approved_at/approved_by + 裁决快照指纹）。
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ApprovalRecord:
    approved_at: str
    approved_by: str
    eligibility_fingerprint: str
    snapshot: dict[str, object]
    schema_version: int = 1


class SelfUseApprovalStore:
    """持久化审批：原子写 + 文件锁；审批绑定到裁决快照指纹，台账变更即失效。"""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.lock_path = self.path.with_name(f".{self.path.name}.lock")

    def load(self) -> ApprovalRecord | None:
        if not self.path.exists():
            return None
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("approval record must be a JSON object")
        return ApprovalRecord(
            approved_at=str(payload["approved_at"]),
            approved_by=str(payload["approved_by"]),
            eligibility_fingerprint=str(payload["eligibility_fingerprint"]),
            snapshot=dict(payload.get("snapshot") or {}),
            schema_version=int(payload.get("schema_version", 1)),
        )

    def approve(self, result: MaturityResult, *, approved_by: str) -> ApprovalRecord:
        if not result.eligible_for_user_decision:
            raise ValueError("cannot approve a result that is not eligible_for_user_decision")
        approver = redact(str(approved_by).strip())
        if not approver:
            raise ValueError("approved_by must not be blank")
        record = ApprovalRecord(
            approved_at=_now_iso(),
            approved_by=approver,
            eligibility_fingerprint=result.fingerprint or eligibility_fingerprint(result),
            snapshot={
                "metrics": result.metrics,
                "blockers": list(result.blockers),
                "eligible_for_user_decision": result.eligible_for_user_decision,
            },
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock_path.open("a+b") as lock_handle:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
            data = json.dumps(asdict(record), ensure_ascii=False, indent=2).encode("utf-8")
            _atomic_replace(self.path, data)
        return record

    def is_approved_for(self, result: MaturityResult) -> bool:
        """当且仅当存在指纹与当前裁决快照一致的持久化审批时返回 True。"""
        record = self.load()
        if record is None:
            return False
        current = result.fingerprint or eligibility_fingerprint(result)
        return bool(result.eligible_for_user_decision and record.eligibility_fingerprint == current)
