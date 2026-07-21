"""FastAPI backend for the local Market Intelligence Workbench."""

from __future__ import annotations

import json
import os
import threading
import time
from collections import Counter
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from contextlib import asynccontextmanager, nullcontext
from dataclasses import asdict
from importlib import import_module
from pathlib import Path
from threading import Event, Lock
from typing import Literal

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, SecretStr, field_validator

from intelligence import userspace
from intelligence.paths import default_paths
from intelligence.api.artifacts import ArtifactRegistry
from intelligence.api.daily_reports import (
    project_daily_agent,
    project_daily_review_html,
    project_daily_review_markdown,
)
from intelligence.api.structured_reports import (
    ask_result_modules,
    complete_report,
    daily_projection_modules,
    moneyflow_module,
    new_structured_report,
    upsert_report_module,
)
from intelligence.api.stream_events import PUBLIC_EVENT_TYPES
from intelligence.services import followups as followups_svc
from intelligence.services import kb_rag
from intelligence.services import llm_refine
from intelligence.services import market_moneyflow
from intelligence.services import perspective_lab
from intelligence.services import run_store as rs
from intelligence.services.forecast_learning import (
    approve_reflection,
    learning_feedback_projection,
    reject_reflection,
    set_rule_status,
)
from intelligence.services.conversation_orchestrator import (
    TurnOrchestrator,
    sanitize_user_visible_artifact_text,
)
from intelligence.services.conversation_store import (
    ConversationDataIntegrityError,
    ConversationStore,
)
from intelligence.services.llm_refine import LLMProvider
from intelligence.services.llm_settings import SessionLLMSettings
from intelligence.services.market_snapshot_contract import (
    validate_market_snapshot_root,
)
from intelligence.services.run_store import RunStore
from intelligence.services.runtime_provenance import build_runtime_provenance
from intelligence.services.self_use_maturity import (
    SelfUseApprovalStore,
    SelfUseLedger,
    SelfUseLedgerIntegrityError,
    evaluate_maturity,
    trading_days_from_duckdb,
)
from intelligence.services.workbench_overview import build_workbench_overview
from intelligence.workbench_skills.registry import SKILL_REGISTRY

STATIC_DIR = Path(__file__).resolve().parent / "static"
REPO_ROOT = Path(
    os.environ.get("WORKBENCH_REPO_ROOT", Path(__file__).resolve().parents[2])
)

_SSE_POLL_SECONDS = 0.5
_SSE_MAX_SECONDS = 15 * 60


def _positive_float_env(name: str, default: float) -> float:
    try:
        value = float(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default
_WORKER_COUNT = 2
_RESTART_REASON = "workbench_restarted_before_completion"
_STABLE_MACHINE_FALLBACK_REASONS = frozenset(
    {
        "provider_timeout",
        "provider_unavailable",
        "quality_gate_rejected",
        "budget_exhausted",
    }
)
_PUBLIC_METADATA_STRING_FIELDS = frozenset(
    {
        "schema_version",
        "event_id",
        "event_type",
        "run_id",
        "conversation_id",
        "message_id",
        "step_id",
        "skill_id",
        "module_id",
        "artifact_id",
        "report_id",
        "status",
        "role",
        "task_type",
        "skill_mode",
        "perspective_mode",
        "phase",
        "answer_phase",
        "selection_source",
        "kind",
        "renderer",
        "tag",
    }
)
_PUBLIC_METADATA_STRING_LIST_FIELDS = frozenset(
    {
        "selected_skill_ids",
        "invoked_skill_ids",
        "selected_perspective_ids",
    }
)


def _public_degrades(values: list[str]) -> list[str]:
    return list(
        dict.fromkeys(
            sanitize_user_visible_artifact_text(value)
            for value in values
            if isinstance(value, str) and value.strip()
        )
    )


def _public_run_payload(run: rs.Run) -> dict[str, object]:
    payload = asdict(run)
    payload["degrades"] = _public_degrades(run.degrades)
    if run.error:
        payload["error"] = sanitize_user_visible_artifact_text(run.error)
    return payload


def _is_public_machine_enum(path: tuple[str, ...], value: str) -> bool:
    return (
        len(path) >= 3
        and path[-3:] == ("report", "llm", "fallback_reason")
        and value in _STABLE_MACHINE_FALLBACK_REASONS
    )


def _is_public_metadata_string(path: tuple[str, ...]) -> bool:
    return bool(path) and (
        path[-1] in _PUBLIC_METADATA_STRING_FIELDS
        or (
            len(path) >= 2
            and path[-2] in _PUBLIC_METADATA_STRING_LIST_FIELDS
        )
    )


def _public_value(
    value: object,
    *,
    path: tuple[str, ...] = (),
    preserve_text_paths: frozenset[tuple[str, ...]] = frozenset(),
) -> object:
    if isinstance(value, str):
        if (
            _is_public_machine_enum(path, value)
            or _is_public_metadata_string(path)
            or any(
                len(path) >= len(suffix) and path[-len(suffix) :] == suffix
                for suffix in preserve_text_paths
            )
        ):
            return value
        stripped = value.strip()
        if stripped.startswith(("{", "[")):
            try:
                decoded = json.loads(stripped)
            except json.JSONDecodeError:
                pass
            else:
                if isinstance(decoded, (dict, list)):
                    return json.dumps(
                        _public_value(
                            decoded,
                            path=path,
                            preserve_text_paths=preserve_text_paths,
                        ),
                        ensure_ascii=False,
                    )
        return sanitize_user_visible_artifact_text(value)
    if isinstance(value, list):
        return [
            _public_value(
                item,
                path=(*path, str(index)),
                preserve_text_paths=preserve_text_paths,
            )
            for index, item in enumerate(value)
        ]
    if isinstance(value, dict):
        return {
            str(key): _public_value(
                item,
                path=(*path, str(key)),
                preserve_text_paths=preserve_text_paths,
            )
            for key, item in value.items()
        }
    return value


def _public_trace_step(step: dict[str, object]) -> dict[str, object]:
    projected = _public_value(step)
    return projected if isinstance(projected, dict) else {}


def _public_stream_event(event: dict[str, object]) -> dict[str, object]:
    event_type = event.get("event_type")
    preserve_paths: set[tuple[str, ...]] = {
        ("payload", "message", "content")
    }
    if event_type == "answer.snapshot":
        preserve_paths.add(("payload", "text"))
    elif event_type == "text.delta":
        preserve_paths.add(("payload", "delta"))
    projected = _public_value(
        event,
        preserve_text_paths=frozenset(preserve_paths),
    )
    return projected if isinstance(projected, dict) else {}


def _public_message_payload(message: object) -> dict[str, object]:
    projected = _public_value(
        asdict(message),
        preserve_text_paths=frozenset({("content",)}),
    )
    return projected if isinstance(projected, dict) else {}


class CancellationSignal:
    def __init__(self) -> None:
        self._event = Event()
        self.reason: str | None = None

    def set(self, reason: str) -> None:
        self.reason = reason
        self._event.set()

    def is_set(self) -> bool:
        return self._event.is_set()

    def wait(self, timeout: float) -> bool:
        return self._event.wait(timeout)


class RunSupervisor:
    def __init__(
        self,
        max_workers: int = _WORKER_COUNT,
        timeout_sec: float = _SSE_MAX_SECONDS,
    ) -> None:
        self.max_workers = max_workers
        self.timeout_sec = timeout_sec
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="workbench-run",
        )
        self._futures: dict[tuple[str, str], Future[None]] = {}
        self._timers: dict[tuple[str, str], threading.Timer] = {}
        self._stores: dict[tuple[str, str], RunStore] = {}
        self._signals: dict[tuple[str, str], CancellationSignal] = {}
        self._terminal_handlers: dict[tuple[str, str], Callable[[str], None]] = {}
        self._lock = threading.Lock()

    def submit(self, store: RunStore, run_id: str, req: CreateRunRequest) -> None:
        self._submit(
            store,
            run_id,
            lambda _: _run_ask(store, run_id, req),
        )

    def submit_conversation(
        self,
        store: RunStore,
        run_id: str,
        *,
        repo_root: Path,
        conversation_store: ConversationStore,
        conversation_id: str,
        assistant_message_id: str,
        query: str,
        skill_mode: Literal["manual", "auto", "hybrid"],
        selected_skill_ids: list[str],
        perspective_mode: Literal["neutral", "single", "compare"],
        selected_perspective_ids: list[str],
        event_id_prefix: str = "",
        llm_provider: LLMProvider | None = None,
    ) -> None:
        self._submit(
            store,
            run_id,
            lambda signal: _run_conversation_turn(
                repo_root=repo_root,
                conversation_store=conversation_store,
                run_store=store,
                conversation_id=conversation_id,
                run_id=run_id,
                assistant_message_id=assistant_message_id,
                query=query,
                skill_mode=skill_mode,
                selected_skill_ids=selected_skill_ids,
                perspective_mode=perspective_mode,
                selected_perspective_ids=selected_perspective_ids,
                cancellation_signal=signal,
                event_id_prefix=event_id_prefix,
                llm_provider=llm_provider,
            ),
            on_terminal=lambda reason: _terminalize_pending_message(
                conversation_store,
                store,
                conversation_id,
                assistant_message_id,
                run_id,
                reason,
            ),
        )

    def _submit(
        self,
        store: RunStore,
        run_id: str,
        runner: Callable[[CancellationSignal], None],
        on_terminal: Callable[[str], None] | None = None,
    ) -> None:
        key = (store.user_id, run_id)
        store.mark_running(run_id)
        signal = CancellationSignal()
        timer = threading.Timer(
            self.timeout_sec,
            self._expire,
            args=(store, run_id, key),
        )
        timer.daemon = True
        with self._lock:
            future = self._executor.submit(runner, signal)
            self._futures[key] = future
            self._timers[key] = timer
            self._stores[key] = store
            self._signals[key] = signal
            if on_terminal is not None:
                self._terminal_handlers[key] = on_terminal
        future.add_done_callback(lambda _: self._forget(key))
        timer.start()

    def cancel(self, store: RunStore, run_id: str) -> bool:
        key = (store.user_id, run_id)
        with self._lock:
            future = self._futures.get(key)
            timer = self._timers.get(key)
            active_store = self._stores.get(key, store)
            signal = self._signals.get(key)
            terminal_handler = self._terminal_handlers.get(key)
        if timer is not None:
            timer.cancel()
        if signal is not None:
            signal.set("cancelled_by_user")
        queued_cancelled = future.cancel() if future is not None else False
        run = active_store.finish_run(
            run_id,
            rs.STATUS_CANCELLED,
            error="cancelled_by_user",
        )
        if run.status == rs.STATUS_CANCELLED and terminal_handler is not None:
            terminal_handler("cancelled_by_user")
        return queued_cancelled

    @property
    def cancellation_signals(self) -> dict[tuple[str, str], CancellationSignal]:
        return self._signals

    def active_count(self) -> int:
        with self._lock:
            return sum(not future.done() for future in self._futures.values())

    def shutdown(self) -> None:
        with self._lock:
            timers = list(self._timers.values())
        for timer in timers:
            timer.cancel()
        self._executor.shutdown(wait=False, cancel_futures=True)

    def _forget(self, key: tuple[str, str]) -> None:
        with self._lock:
            self._futures.pop(key, None)
            timer = self._timers.pop(key, None)
            self._stores.pop(key, None)
            self._signals.pop(key, None)
            self._terminal_handlers.pop(key, None)
        if timer is not None:
            timer.cancel()

    def _expire(
        self,
        store: RunStore,
        run_id: str,
        key: tuple[str, str],
    ) -> None:
        with self._lock:
            future = self._futures.get(key)
            signal = self._signals.get(key)
            terminal_handler = self._terminal_handlers.get(key)
        if future is None or future.done():
            return
        if signal is not None:
            signal.set("executor_timeout")
        future.cancel()
        if terminal_handler is not None:
            terminal_handler("executor_timeout")
        store.fail_active_run(
            run_id,
            error="executor_timeout",
            degrade="executor_timeout",
        )


class CreateRunRequest(BaseModel):
    question: str = Field(min_length=1)
    user: str | None = None
    task_type: str = "ask"
    session_id: str | None = None
    parent_run_id: str | None = None
    compose: bool = True
    repo_root: Path | None = Field(default=None, exclude=True)


def _run_terminal(store: RunStore, run_id: str) -> bool:
    return store.load_run(run_id).status in (
        rs.STATUS_COMPLETED,
        rs.STATUS_FAILED,
        rs.STATUS_CANCELLED,
    )


class CreateConversationRequest(BaseModel):
    title: str = "新对话"
    user: str | None = None

    @field_validator("title")
    @classmethod
    def title_must_not_be_blank(cls, value: str) -> str:
        title = value.strip()
        if not title:
            raise ValueError("title must not be blank")
        return title


class UpdateConversationRequest(BaseModel):
    title: str = Field(min_length=1)
    user: str | None = None

    @field_validator("title")
    @classmethod
    def title_must_not_be_blank(cls, value: str) -> str:
        title = value.strip()
        if not title:
            raise ValueError("title must not be blank")
        return title


class UserRequest(BaseModel):
    user: str | None = None


class CreateMessageRequest(BaseModel):
    content: str = Field(min_length=1)
    skill_mode: Literal["manual", "auto", "hybrid"]
    selected_skill_ids: list[str] = Field(default_factory=list)
    perspective_mode: Literal["neutral", "single", "compare"] = "neutral"
    selected_perspective_ids: list[str] = Field(default_factory=list)
    user: str | None = None

    @field_validator("content")
    @classmethod
    def content_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("content must not be blank")
        return value


class ConfigureLLMRequest(BaseModel):
    provider: Literal["zhipu", "openai", "deepseek", "moonshot", "dashscope"]
    api_key: SecretStr
    model: str | None = Field(
        default=None,
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9._:/-]+$",
    )
    user: str | None = None


class ApproveReflectionRequest(BaseModel):
    hypothesis_ids: list[str] = Field(default_factory=list, max_length=50)


class RuleStatusRequest(BaseModel):
    status: Literal["approved", "rejected"]


def _run_conversation_turn(
    *,
    repo_root: Path,
    conversation_store: ConversationStore,
    run_store: RunStore,
    conversation_id: str,
    run_id: str,
    assistant_message_id: str,
    query: str,
    skill_mode: Literal["manual", "auto", "hybrid"],
    selected_skill_ids: list[str],
    cancellation_signal: CancellationSignal,
    perspective_mode: Literal["neutral", "single", "compare"] = "neutral",
    selected_perspective_ids: list[str] | None = None,
    event_id_prefix: str = "",
    llm_provider: LLMProvider | None = None,
) -> None:
    try:
        test_delay_ms = int(
            os.environ.get("WORKBENCH_TEST_RUN_DELAY_MS", "0")
        )
    except ValueError:
        test_delay_ms = 0
    test_delay_ms = min(5000, max(0, test_delay_ms))
    if test_delay_ms and cancellation_signal.wait(test_delay_ms / 1000):
        return
    provider_context = (
        llm_refine.provider_override(llm_provider)
        if llm_provider is not None
        else nullcontext()
    )
    with provider_context:
        TurnOrchestrator(
            repo_root=repo_root,
            conversation_store=conversation_store,
            run_store=run_store,
            llm_model=llm_provider.model if llm_provider is not None else None,
            is_cancelled=cancellation_signal.is_set,
            cancellation_reason=lambda: cancellation_signal.reason,
            event_id_prefix=event_id_prefix,
        ).run_turn(
            conversation_id=conversation_id,
            run_id=run_id,
            assistant_message_id=assistant_message_id,
            query=query,
            skill_mode=skill_mode,
            selected_skill_ids=selected_skill_ids,
            perspective_mode=perspective_mode,
            selected_perspective_ids=selected_perspective_ids or [],
        )


def _terminalize_pending_message(
    conversation_store: ConversationStore,
    run_store: RunStore,
    conversation_id: str,
    message_id: str,
    run_id: str,
    reason: str,
) -> None:
    current = next(
        (
            message
            for message in conversation_store.load_messages(conversation_id)
            if message.message_id == message_id
        ),
        None,
    )
    if current is None or current.status in {
        rs.STATUS_COMPLETED,
        rs.STATUS_FAILED,
        rs.STATUS_CANCELLED,
    }:
        return
    status = (
        rs.STATUS_CANCELLED
        if reason == "cancelled_by_user"
        else rs.STATUS_FAILED
    )
    warning = (
        "用户已取消本轮执行"
        if status == rs.STATUS_CANCELLED
        else "本轮执行超时"
    )
    message = conversation_store.revise_message(
        conversation_id,
        message_id,
        content=current.content,
        status=status,
        selected_skill_ids=current.selected_skill_ids,
        invoked_skill_ids=current.invoked_skill_ids,
        citations=current.citations,
        degrades=list(dict.fromkeys([*current.degrades, warning])),
    )
    run_store.append_stream_event(
        run_id,
        event_id=f"supervisor:{status}",
        event_type="message.error",
        payload={"status": status, "message": asdict(message)},
        conversation_id=conversation_id,
        message_id=message_id,
    )


def _run_ask(
    store: RunStore,
    run_id: str,
    req: CreateRunRequest,
) -> None:
    from intelligence.services.ask import AskOptions, answer_query, render_answer
    from intelligence.services.llm_refine import detect_provider

    repo_root = req.repo_root or REPO_ROOT
    report = new_structured_report(
        run_id=run_id,
        question=req.question,
        task_type=req.task_type,
    )
    store.append_stream_event(
        run_id,
        event_id="report:start",
        event_type="report.start",
        payload={"report": report},
    )
    if _run_terminal(store, run_id):
        return

    report_warnings: list[str] = []
    report_date: str | None = None

    def emit_module(module: dict[str, object]) -> None:
        upsert_report_module(report, module)
        store.append_stream_event(
            run_id,
            event_id=f"module:{module['module_id']}",
            event_type="report.module",
            payload={"module": module},
        )

    if req.task_type == "daily":
        try:
            report_date, daily_modules, daily_warnings = daily_projection_modules(repo_root)
            report["as_of"] = report_date
            report_warnings.extend(daily_warnings)
            for module in daily_modules:
                emit_module(module)
            if _run_terminal(store, run_id):
                return
        except Exception as exc:  # noqa: BLE001
            warning = f"日报 canonical 投影失败（{type(exc).__name__}）"
            report_warnings.append(warning)
            store.add_degrade(run_id, warning)

    wants_moneyflow = req.task_type == "daily" or market_moneyflow.parse_moneyflow_intent(
        req.question
    )
    if wants_moneyflow:
        snapshot = market_moneyflow.load_moneyflow_snapshot(
            repo_root / "db" / "market_feature_store.duckdb",
            as_of_date=report_date,
        )
        emit_module(moneyflow_module(snapshot))
        if snapshot.status != "ok":
            for warning in snapshot.warnings:
                store.add_degrade(run_id, warning)
        if _run_terminal(store, run_id):
            return

    started_at = rs._now_iso()
    store.append_step(
        run_id,
        step_id="s01",
        name="ask_retrieve_compose",
        status="running",
        input_summary=req.question,
        started_at=started_at,
    )
    try:
        result = answer_query(
            AskOptions(
                query=req.question,
                date=report_date,
                user=req.user,
                compose=req.compose,
                compose_revise_on_warn=req.task_type != "daily",
                market_db_path=repo_root / "db" / "market_feature_store.duckdb",
                force_moneyflow_block=req.task_type == "daily",
            )
        )
        rag_telemetry = (
            asdict(result.wiki_rag_telemetry)
            if result.wiki_rag_telemetry is not None
            else {}
        )
        store.update_provenance(
            run_id,
            source_date=result.trade_date,
            kb_commit=str(rag_telemetry.get("index_source_revision") or "") or None,
            kb_index_built_at=str(rag_telemetry.get("index_built_at") or "") or None,
            kb_index_freshness=str(rag_telemetry.get("index_freshness") or "") or None,
        )
        if _run_terminal(store, run_id):
            return
    except Exception as exc:  # noqa: BLE001
        if _run_terminal(store, run_id):
            return
        store.append_step(
            run_id,
            step_id="s01",
            name="ask_retrieve_compose",
            status="failed",
            input_summary=req.question,
            started_at=started_at,
            finished_at=rs._now_iso(),
            warnings=[f"{type(exc).__name__}: {exc}"],
        )
        report["status"] = "failed"
        report_warnings.append(f"{type(exc).__name__}: {exc}")
        report["warnings"] = report_warnings
        store.append_stream_event(
            run_id,
            event_id="report:error",
            event_type="report.error",
            payload={"report": report},
        )
        store.finish_run(run_id, rs.STATUS_FAILED, error=f"{type(exc).__name__}: {exc}")
        return

    hits = [
        source
        for source, found in (
            ("market", result.found_market),
            ("graph", result.found_graph),
            ("wiki", result.found_wiki),
        )
        if found
    ]
    citation_counts = dict(Counter(citation.tag[:1] for citation in result.citations if citation.tag))
    store.append_step(
        run_id,
        step_id="s01",
        name="ask_retrieve_compose",
        status="completed",
        input_summary=req.question,
        started_at=started_at,
        finished_at=rs._now_iso(),
        output_summary=(
            f"命中源：{'+'.join(hits) or '无'}；引用 {len(result.citations)} 条"
            f"；模块 {','.join(result.routed_modules) or '—'}"
        ),
        warnings=list(result.warnings),
        retrieval={
            "sources": hits,
            "citation_counts": citation_counts,
            "citations": [asdict(citation) for citation in result.citations],
            "trade_date": result.trade_date,
            "matched_theme": result.matched_theme,
        },
    )
    for warning in result.warnings:
        store.add_degrade(run_id, warning)
    if req.compose and not (result.llm_refined or result.synthesis):
        store.add_degrade(run_id, "llm_unavailable_template_answer")

    for module in ask_result_modules(result):
        emit_module(module)

    render_started_at = rs._now_iso()
    answer_md = render_answer(result)
    store.add_artifact(
        run_id,
        "answer.md",
        answer_md,
        renderer="markdown",
        title=f"研究回答：{req.question[:24]}",
    )
    summary = {
        "trade_date": result.trade_date,
        "matched_theme": result.matched_theme,
        "question_type": result.question_plan.question_type if result.question_plan else None,
        "citations": len(result.citations),
        "citation_counts": citation_counts,
        "citation_records": [asdict(citation) for citation in result.citations],
        "llm_refined": result.llm_refined,
        "llm_composed": bool(result.synthesis),
        "warnings": list(result.warnings),
    }
    store.add_artifact(
        run_id,
        "summary.json",
        json.dumps(summary, ensure_ascii=False, indent=2),
        renderer="json",
        title="结构化摘要",
    )
    provider = detect_provider()
    complete_report(
        report,
        as_of=result.trade_date or report_date,
        warnings=[*report_warnings, *result.warnings],
        llm_provider=result.llm_provider,
        llm_model=provider.model if provider and result.llm_provider else None,
    )
    store.add_artifact(
        run_id,
        "report.json",
        json.dumps(report, ensure_ascii=False, indent=2),
        renderer="structured_report",
        title="结构化流式报告",
    )
    store.append_stream_event(
        run_id,
        event_id="report:complete",
        event_type="report.complete",
        payload={"report": report},
    )
    store.append_step(
        run_id,
        step_id="s02",
        name="render_artifacts",
        status="completed",
        started_at=render_started_at,
        finished_at=rs._now_iso(),
        output_summary="answer.md + summary.json",
    )
    if _run_terminal(store, run_id):
        return

    followup_started_at = rs._now_iso()
    store.append_step(
        run_id,
        step_id="s03",
        name="foresight_followups",
        status="running",
        input_summary=req.question,
        started_at=followup_started_at,
    )
    try:
        followups = followups_svc.generate_followups(
            req.question,
            matched_theme=result.matched_theme,
            answer_excerpt=result.synthesis or answer_md,
            use_llm=req.task_type != "daily",
        )
        store.add_artifact(
            run_id,
            "followups.json",
            followups.to_json(),
            renderer="json",
            title="猜你想问",
        )
        if not followups.llm_used:
            store.add_degrade(run_id, "llm_unavailable_template_followups")
        store.append_step(
            run_id,
            step_id="s03",
            name="foresight_followups",
            status="completed",
            input_summary=req.question,
            started_at=followup_started_at,
            finished_at=rs._now_iso(),
            output_summary=f"追问 {len(followups.followups)} 条（{'LLM' if followups.llm_used else '模板'}）",
            warnings=list(followups.warnings),
        )
    except Exception as exc:  # noqa: BLE001
        store.append_step(
            run_id,
            step_id="s03",
            name="foresight_followups",
            status="failed",
            input_summary=req.question,
            started_at=followup_started_at,
            finished_at=rs._now_iso(),
            warnings=[f"{type(exc).__name__}: {exc}"],
        )

    if _run_terminal(store, run_id):
        return
    store.finish_run(run_id, rs.STATUS_COMPLETED)


def _pending_review_count(repo_root: Path) -> int:
    ledger = repo_root / "docs" / "learning" / "forecast-review-ledger"
    return sum(
        1
        for manifest in ledger.glob("20??-??-??.manifest.json")
        if not manifest.with_name(manifest.name.replace(".manifest.json", ".verdict.json")).is_file()
    )


def _run_context(store: RunStore, run_id: str) -> dict[str, object]:
    run = store.load_run(run_id)
    trace = store.load_trace(run_id)
    source_labels = {
        "market": "盘面快照",
        "graph": "知识图谱",
        "wiki": "知识库检索",
    }
    citation_labels = {
        "S": "盘面证据",
        "G": "图谱证据",
        "R": "事实证据",
        "W": "语义检索",
        "L": "公告与互动证据",
        "M": "用户记忆",
        "V": "历史回检",
    }
    evidence: list[dict[str, object]] = []
    citation_counts: Counter[str] = Counter()
    seen_sources: set[str] = set()
    warnings: list[str] = []
    for step in trace:
        warnings.extend(str(warning) for warning in step.get("warnings", []))
        retrieval = step.get("retrieval")
        if not isinstance(retrieval, dict):
            continue
        for source in retrieval.get("sources", []):
            source_name = str(source)
            if source_name in seen_sources:
                continue
            seen_sources.add(source_name)
            evidence.append(
                {
                    "id": f"source:{source_name}",
                    "label": source_labels.get(source_name, source_name),
                    "kind": "source",
                    "classification": "fact_source",
                    "detail": "本次检索已命中",
                    "status": "hit",
                }
            )
        citation_records = retrieval.get("citations", [])
        if isinstance(citation_records, list):
            for citation in citation_records:
                if not isinstance(citation, dict):
                    continue
                tag = str(citation.get("tag") or "")
                source = str(citation.get("source") or "")
                if not tag or not source:
                    continue
                binding = [
                    f"chunk={citation.get('chunk_id')}" if citation.get("chunk_id") else "",
                    f"hash={str(citation.get('content_hash'))[:12]}"
                    if citation.get("content_hash")
                    else "",
                    f"index={str(citation.get('index_source_revision'))[:12]}"
                    if citation.get("index_source_revision")
                    else "",
                    f"freshness={citation.get('index_freshness')}"
                    if citation.get("index_freshness")
                    else "",
                ]
                evidence.append(
                    {
                        "id": f"citation-record:{tag}",
                        "label": f"[{tag}] {source}",
                        "kind": "citation_record",
                        "classification": "bound_evidence",
                        "detail": " · ".join(item for item in binding if item)
                        or str(citation.get("detail") or "已记录引用"),
                        "status": "hit",
                    }
                )
        counts = retrieval.get("citation_counts", {})
        if isinstance(counts, dict):
            citation_counts.update(
                {
                    str(tag): int(count)
                    for tag, count in counts.items()
                    if str(count).isdigit() or isinstance(count, int)
                }
            )
    for tag, count in sorted(citation_counts.items()):
        if tag in {"M", "V"}:
            continue
        evidence.append(
            {
                "id": f"citation:{tag}",
                "label": citation_labels.get(tag, f"{tag} 类证据"),
                "kind": "citation",
                "classification": "fact_or_context",
                "detail": f"{count} 条引用",
                "status": "hit",
            }
        )

    memory = []
    if citation_counts.get("M"):
        memory.append(
            {
                "label": "用户记忆命中",
                "detail": f"{citation_counts['M']} 条 M 类引用参与本次回答",
                "source": "run trace",
            }
        )
    review = []
    if citation_counts.get("V"):
        review.append(
            {
                "label": "历史回检命中",
                "detail": f"{citation_counts['V']} 条 V 类引用参与本次回答",
                "source": run.manifest_ref or "run trace",
            }
        )
    gaps = list(dict.fromkeys([*run.degrades, *warnings]))
    return {
        "evidence": evidence,
        "memory": memory,
        "review": review,
        "gaps": gaps,
        "warnings": list(dict.fromkeys(warnings)),
        "metadata": {
            "source_date": run.source_date,
            "duckdb_cutoff": run.duckdb_cutoff,
            "kb_commit": run.kb_commit,
            "kb_index_built_at": run.kb_index_built_at,
            "kb_index_freshness": run.kb_index_freshness,
            "manifest_ref": run.manifest_ref,
        },
    }


def _resume_conversation_run(
    supervisor: RunSupervisor,
    store: RunStore,
    run: rs.Run,
    repo_root: Path,
) -> bool:
    if run.session_id is None:
        return False
    conversation_store = ConversationStore(user_id=store.user_id)
    messages = conversation_store.load_messages(run.session_id)
    user_message = next(
        (
            message
            for message in messages
            if message.run_id == run.run_id and message.role == "user"
        ),
        None,
    )
    assistant_message = next(
        (
            message
            for message in messages
            if message.run_id == run.run_id and message.role == "assistant"
        ),
        None,
    )
    if user_message is None or assistant_message is None:
        return False
    event_id_prefix = f"recovery:{len(store.load_stream_events(run.run_id)) + 1}:"
    supervisor.submit_conversation(
        store,
        run.run_id,
        repo_root=repo_root,
        conversation_store=conversation_store,
        conversation_id=run.session_id,
        assistant_message_id=assistant_message.message_id,
        query=user_message.content,
        skill_mode=user_message.skill_mode,
        selected_skill_ids=list(user_message.selected_skill_ids),
        perspective_mode=user_message.perspective_mode,
        selected_perspective_ids=list(user_message.selected_perspective_ids),
        event_id_prefix=event_id_prefix,
    )
    return True


def create_app(
    *,
    repo_root: Path | None = None,
    run_timeout_sec: float = _SSE_MAX_SECONDS,
    self_use_require_consecutive_trading_days: bool = False,
) -> FastAPI:
    root = (repo_root or REPO_ROOT).resolve()
    runtime_provenance = build_runtime_provenance(root)
    runtime_paths = default_paths()
    supervisor = RunSupervisor(timeout_sec=run_timeout_sec)
    llm_settings = SessionLLMSettings()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        if kb_rag.rag_worker.enabled():
            try:
                kb_rag.prewarm(
                    runtime_paths.knowledge_wiki,
                    timeout=_positive_float_env(
                        "RAG_WORKER_PREWARM_TIMEOUT",
                        90.0,
                    ),
                )
            except Exception as exc:  # noqa: BLE001 - fail closed at readiness
                kb_rag.rag_worker.record_startup_failure(exc)
        try:
            yield
        finally:
            kb_rag.rag_worker.close_all()
            llm_settings.clear_all()
            supervisor.shutdown()

    app = FastAPI(title="Market Intelligence Workbench API", lifespan=lifespan)
    app.state.repo_root = root
    registries: dict[str, ArtifactRegistry] = {}
    recovered_runs: list[str] = []
    conversation_locks: dict[tuple[str, str], Lock] = {}
    conversation_locks_guard = Lock()

    user_ids = {userspace.DEFAULT_USER}
    users_root = userspace.users_dir()
    if users_root.is_dir():
        user_ids.update(
            path.name
            for path in users_root.iterdir()
            if path.is_dir() and (path / "runs").is_dir()
        )
    for user_id in sorted(user_ids):
        try:
            store = RunStore(user_id=user_id)
            for run in store.requeue_incomplete_runs(reason=_RESTART_REASON):
                recovered_runs.append(run.run_id)
                try:
                    if _resume_conversation_run(supervisor, store, run, root):
                        continue
                except (
                    FileNotFoundError,
                    ValueError,
                    json.JSONDecodeError,
                    ConversationDataIntegrityError,
                ):
                    pass
                supervisor.submit(
                    store,
                    run.run_id,
                    CreateRunRequest(
                        question=run.question,
                        user=run.user,
                        task_type=run.task_type,
                        session_id=run.session_id,
                        parent_run_id=run.parent_run_id,
                        repo_root=root,
                    ),
                )
        except (OSError, ValueError, json.JSONDecodeError):
            continue
    app.state.supervisor = supervisor
    app.state.recovered_runs = recovered_runs
    app.state.cancellation_registry = supervisor.cancellation_signals
    app.state.conversation_locks = conversation_locks
    app.state.conversation_locks_guard = conversation_locks_guard
    app.state.llm_settings = llm_settings

    def store_for(user: str | None) -> RunStore:
        return RunStore(user_id=user)

    def conversation_store_for(user: str | None) -> ConversationStore:
        return ConversationStore(user_id=store_for(user).user_id)

    def self_use_projection(user: str | None) -> dict[str, object]:
        conversation_store = conversation_store_for(user)
        self_use_dir = conversation_store.root.parent / "self-use"
        ledger = SelfUseLedger(self_use_dir / "events.jsonl")
        trading_days = trading_days_from_duckdb(
            root / "db" / "market_feature_store.duckdb"
        )
        try:
            result = evaluate_maturity(
                ledger.load(),
                trading_days=trading_days,
                require_consecutive_trading_days=(
                    self_use_require_consecutive_trading_days
                ),
            )
        except (OSError, SelfUseLedgerIntegrityError) as exc:
            raise HTTPException(500, "自用成熟度台账不可读") from exc
        # passed 由持久化审批驱动：审批指纹须与当前裁决快照一致，否则失效。
        approvals = SelfUseApprovalStore(self_use_dir / "approval.json")
        passed = bool(result.eligible_for_user_decision and approvals.is_approved_for(result))
        return {
            "distinct_trade_dates": result.metrics["distinct_trade_dates"],
            "success_rate": result.metrics["core_success_rate"],
            "useful_rate": result.metrics["useful_rate"],
            "manual_rescue_rate": result.metrics["manual_rescue_rate"],
            "covered_workflows": result.metrics["covered_workflows"],
            "blockers": list(result.blockers),
            "eligible_for_user_decision": result.eligible_for_user_decision,
            "passed": passed,
        }

    def conversation_lock_for(user: str | None, conversation_id: str) -> Lock:
        resolved_user_id = store_for(user).user_id
        key = (resolved_user_id, conversation_id)
        with conversation_locks_guard:
            lock = conversation_locks.get(key)
            if lock is None:
                lock = Lock()
                conversation_locks[key] = lock
            return lock

    def conversation_or_404(user: str | None, conversation_id: str):
        try:
            return conversation_store_for(user).load_conversation(conversation_id)
        except (FileNotFoundError, ValueError):
            raise HTTPException(404, "conversation 不存在") from None

    def registry_for(user: str | None) -> ArtifactRegistry:
        store = store_for(user)
        registry = registries.get(store.user_id)
        if registry is None:
            registry = ArtifactRegistry(repo_root=root, run_store=store)
            registries[store.user_id] = registry
        return registry

    def dependency_checks() -> dict[str, bool]:
        return {
            "repo_root": root.is_dir(),
            "knowledge_wiki": runtime_paths.knowledge_wiki.is_dir(),
            "relations": (runtime_paths.knowledge_wiki / "relations").is_dir(),
            "vector_index": runtime_paths.vector_index_dir.is_dir(),
            "market_snapshot": runtime_paths.market_snapshot_dir.is_dir(),
            "frontend_built": (STATIC_DIR / "index.html").is_file(),
        }

    @app.get("/api/health")
    @app.get("/api/health/live")
    def health_live() -> dict[str, object]:
        checks = dependency_checks()
        return {
            "status": "healthy",
            "timestamp": rs._now_iso(),
            "dependencies": checks,
            "runtime": runtime_provenance,
        }

    @app.get("/api/readiness")
    @app.get("/api/health/ready")
    def health_ready(user: str | None = None) -> JSONResponse:
        store = store_for(user)
        rag_probe = kb_rag.probe_rag_cli(runtime_paths.knowledge_wiki)
        worker_status = kb_rag.rag_worker.status()
        snapshot_contract = validate_market_snapshot_root(
            runtime_paths.market_snapshot_dir
        )
        run_root_ready = False
        try:
            store.root.mkdir(parents=True, exist_ok=True)
            run_root_ready = store.root.is_dir() and os.access(store.root, os.W_OK)
        except OSError:
            pass
        checks = {
            **dependency_checks(),
            "rag_query_protocol": rag_probe.query_protocol_compatible,
            "rag_worker": (
                not worker_status["enabled"]
                or (
                    worker_status["state"] == "ready"
                    and int(worker_status["active"]) >= 1
                )
            ),
            "run_store_writable": run_root_ready,
            "market_snapshot_contract": bool(snapshot_contract["ready"]),
        }
        critical = {
            "repo_root": checks["repo_root"],
            "run_store_writable": checks["run_store_writable"],
            "knowledge_wiki": checks["knowledge_wiki"],
            "relations": checks["relations"],
            "vector_index": checks["vector_index"],
            "rag_query_protocol": checks["rag_query_protocol"],
            "rag_worker": checks["rag_worker"],
            "market_snapshot": checks["market_snapshot_contract"],
        }
        ready = all(critical.values())
        payload = {
            "status": "ready" if ready else "not_ready",
            "timestamp": rs._now_iso(),
            "checks": checks,
            "critical": critical,
            "missing_critical": [
                name for name, available in critical.items() if not available
            ],
            "rag": rag_probe.to_dict(),
            "market_snapshot": {
                "status": snapshot_contract["status"],
                "ready": snapshot_contract["ready"],
                "date": snapshot_contract["summary"].get(
                    "served_trade_date"
                )
                or snapshot_contract["date"],
                "requested_date": snapshot_contract["summary"].get(
                    "requested_trade_date"
                ),
                "provider": snapshot_contract["summary"].get("provider"),
                "source": snapshot_contract["summary"].get("source"),
                "summary": snapshot_contract["summary"],
                "errors": snapshot_contract["errors"],
                "warnings": snapshot_contract["warnings"],
            },
            "workers": {
                "active": supervisor.active_count(),
                "capacity": supervisor.max_workers,
                "timeout_sec": supervisor.timeout_sec,
                "rag": worker_status,
            },
            "recovered_runs": len(recovered_runs),
        }
        return JSONResponse(payload, status_code=200 if ready else 503)

    @app.post("/api/runs")
    def create_run(req: CreateRunRequest) -> dict[str, object]:
        req.repo_root = root
        store = store_for(req.user)
        run = store.create_run(
            req.question,
            req.task_type,
            session_id=req.session_id,
            parent_run_id=req.parent_run_id,
        )
        supervisor.submit(store, run.run_id, req)
        return {"run_id": run.run_id, "status": run.status}

    @app.post("/api/runs/{run_id}/cancel")
    def cancel_run(run_id: str, user: str | None = None) -> dict[str, object]:
        store = store_for(user)
        try:
            run = store.load_run(run_id)
        except (FileNotFoundError, ValueError) as exc:
            raise HTTPException(404, f"run 不存在：{run_id}") from exc
        if run.status not in (rs.STATUS_COMPLETED, rs.STATUS_FAILED, rs.STATUS_CANCELLED):
            supervisor.cancel(store, run_id)
            run = store.load_run(run_id)
        return {
            "run_id": run.run_id,
            "status": run.status,
            "cancel_requested": True,
        }

    @app.post("/api/conversations")
    def create_conversation(req: CreateConversationRequest) -> dict[str, object]:
        try:
            return asdict(conversation_store_for(req.user).create_conversation(req.title))
        except ValueError as exc:
            raise HTTPException(422, "invalid user") from exc

    @app.get("/api/conversations")
    def list_conversations(user: str | None = None) -> list[dict[str, object]]:
        try:
            return [asdict(item) for item in conversation_store_for(user).list_conversations()]
        except ValueError as exc:
            raise HTTPException(422, "invalid user") from exc

    @app.get("/api/conversations/{conversation_id}")
    def get_conversation(conversation_id: str, user: str | None = None) -> dict[str, object]:
        return asdict(conversation_or_404(user, conversation_id))

    @app.patch("/api/conversations/{conversation_id}")
    def update_conversation(
        conversation_id: str, req: UpdateConversationRequest
    ) -> dict[str, object]:
        with conversation_lock_for(req.user, conversation_id):
            conversation_or_404(req.user, conversation_id)
            return asdict(
                conversation_store_for(req.user).rename_conversation(
                    conversation_id, req.title
                )
            )

    @app.post("/api/conversations/{conversation_id}/archive")
    def archive_conversation(conversation_id: str, req: UserRequest) -> dict[str, object]:
        with conversation_lock_for(req.user, conversation_id):
            conversation_or_404(req.user, conversation_id)
            return asdict(
                conversation_store_for(req.user).archive_conversation(conversation_id)
            )

    @app.get("/api/conversations/{conversation_id}/messages")
    def list_messages(conversation_id: str, user: str | None = None) -> list[dict[str, object]]:
        conversation_or_404(user, conversation_id)
        return [
            _public_message_payload(item)
            for item in conversation_store_for(user).load_messages(conversation_id)
        ]

    @app.get("/api/llm/config")
    def get_llm_config(user: str | None = None) -> dict[str, object]:
        user_id = store_for(user).user_id
        return llm_settings.describe(user_id)

    @app.put("/api/llm/config")
    def configure_llm(req: ConfigureLLMRequest) -> dict[str, object]:
        user_id = store_for(req.user).user_id
        api_key = req.api_key.get_secret_value().strip()
        if not 8 <= len(api_key) <= 4096:
            raise HTTPException(422, "invalid api key")
        llm_settings.configure_byok(
            user_id,
            provider_id=req.provider,
            api_key=api_key,
            model=req.model,
        )
        return llm_settings.describe(user_id)

    @app.delete("/api/llm/config")
    def use_built_in_llm(user: str | None = None) -> dict[str, object]:
        user_id = store_for(user).user_id
        llm_settings.clear_byok(user_id)
        return llm_settings.describe(user_id)

    @app.post("/api/conversations/{conversation_id}/messages", status_code=202)
    def create_message(
        conversation_id: str, req: CreateMessageRequest
    ) -> dict[str, str]:
        with conversation_lock_for(req.user, conversation_id):
            conversation = conversation_or_404(req.user, conversation_id)
            unknown_skills = [
                skill_id
                for skill_id in dict.fromkeys(req.selected_skill_ids)
                if skill_id not in SKILL_REGISTRY
            ]
            if unknown_skills:
                raise HTTPException(422, "unknown product skill")
            if len(dict.fromkeys(req.selected_skill_ids)) > 3:
                raise HTTPException(422, "at most 3 product skills may be selected")
            try:
                selected_perspective_ids = perspective_lab.validate_runtime_selection(
                    userspace.user_space(conversation.user_id),
                    req.perspective_mode,
                    req.selected_perspective_ids,
                )
            except (ValueError, FileNotFoundError) as exc:
                raise HTTPException(422, str(exc)) from exc
            parent_run_id = conversation.last_run_id
            run_store = store_for(req.user)
            run = run_store.create_run(
                req.content,
                "ask",
                session_id=conversation_id,
                parent_run_id=parent_run_id,
            )
            try:
                store = conversation_store_for(req.user)
                user_message = store.append_message(
                    conversation_id,
                    "user",
                    req.content,
                    run_id=run.run_id,
                    skill_mode=req.skill_mode,
                    selected_skill_ids=req.selected_skill_ids,
                    perspective_mode=req.perspective_mode,
                    selected_perspective_ids=list(selected_perspective_ids),
                )
                assistant_message = store.append_message(
                    conversation_id,
                    "assistant",
                    "",
                    status="pending",
                    run_id=run.run_id,
                    perspective_mode=req.perspective_mode,
                    selected_perspective_ids=list(selected_perspective_ids),
                )
                current = store.load_conversation(conversation_id)
                store.update_summary(
                    conversation_id, current.summary, last_run_id=run.run_id
                )
                supervisor.submit_conversation(
                    run_store,
                    run.run_id,
                    repo_root=root,
                    conversation_store=store,
                    conversation_id=conversation_id,
                    assistant_message_id=assistant_message.message_id,
                    query=req.content,
                    skill_mode=req.skill_mode,
                    selected_skill_ids=list(req.selected_skill_ids),
                    perspective_mode=req.perspective_mode,
                    selected_perspective_ids=list(selected_perspective_ids),
                    llm_provider=llm_settings.provider_for(run_store.user_id),
                )
            except Exception:
                try:
                    run_store.finish_run(
                        run.run_id,
                        rs.STATUS_FAILED,
                        error="message persistence or submission failed",
                    )
                except Exception as compensation_exc:
                    raise RuntimeError(
                        "failed to persist run failure state"
                    ) from compensation_exc
                raise
            return {
                "conversation_id": conversation_id,
                "user_message_id": user_message.message_id,
                "assistant_message_id": assistant_message.message_id,
                "run_id": run.run_id,
            }

    @app.get("/api/skills")
    def list_skills() -> list[dict[str, object]]:
        try:
            registry = import_module("intelligence.workbench_skills.registry")
        except ModuleNotFoundError as exc:
            if exc.name in {
                "intelligence.workbench_skills",
                "intelligence.workbench_skills.registry",
            }:
                return []
            raise
        return [asdict(skill) for skill in registry.SKILL_REGISTRY.values()]

    @app.get("/api/perspectives")
    def list_perspectives(user: str | None = None) -> list[dict[str, object]]:
        user_id = store_for(user).user_id
        return perspective_lab.list_profiles(userspace.user_space(user_id))

    @app.get("/api/runs")
    def list_runs(user: str | None = None) -> list[dict[str, object]]:
        return [
            _public_run_payload(run)
            for run in reversed(store_for(user).list_runs())
        ]

    @app.get("/api/runs/{run_id}")
    def get_run(run_id: str, user: str | None = None) -> dict[str, object]:
        try:
            return _public_run_payload(store_for(user).load_run(run_id))
        except (FileNotFoundError, ValueError) as exc:
            raise HTTPException(404, f"run 不存在：{run_id}") from exc

    @app.get("/api/runs/{run_id}/trace")
    def get_trace(run_id: str, user: str | None = None) -> list[dict[str, object]]:
        store = store_for(user)
        try:
            if not store.run_path(run_id).exists():
                raise HTTPException(404, f"run 不存在：{run_id}")
            return [_public_trace_step(step) for step in store.load_trace(run_id)]
        except ValueError as exc:
            raise HTTPException(404, f"run 不存在：{run_id}") from exc

    @app.get("/api/runs/{run_id}/context")
    def get_run_context(run_id: str, user: str | None = None) -> dict[str, object]:
        store = store_for(user)
        try:
            return _run_context(store, run_id)
        except (FileNotFoundError, ValueError) as exc:
            raise HTTPException(404, f"run 不存在：{run_id}") from exc

    @app.get("/api/runs/{run_id}/followups")
    def get_followups(run_id: str, user: str | None = None) -> dict[str, object]:
        store = store_for(user)
        try:
            path = store.run_dir(run_id) / "followups.json"
        except ValueError as exc:
            raise HTTPException(404, f"run 不存在：{run_id}") from exc
        if not path.is_file():
            return {"followups": []}
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {"followups": []}

    @app.get("/api/runs/{run_id}/events")
    def run_events(
        run_id: str,
        request: Request,
        user: str | None = None,
        after: int = Query(default=0, ge=0),
    ) -> StreamingResponse:
        store = store_for(user)
        try:
            if not store.run_path(run_id).exists():
                raise HTTPException(404, f"run 不存在：{run_id}")
        except ValueError as exc:
            raise HTTPException(404, f"run 不存在：{run_id}") from exc

        last_event_id = request.headers.get("last-event-id", "")
        cursor = after
        if cursor == 0 and last_event_id:
            if last_event_id.isdigit():
                cursor = int(last_event_id)
            else:
                cursor = next(
                    (event["seq"] for event in store.load_stream_events(run_id) if event["event_id"] == last_event_id),
                    0,
                )

        def stream():
            current_cursor = cursor
            deadline = time.monotonic() + _SSE_MAX_SECONDS
            terminal_event_deadline: float | None = None
            while True:
                report_events = store.load_stream_events(run_id, after=current_cursor)
                for event in report_events:
                    current_cursor = event["seq"]
                    if event["event_type"] not in PUBLIC_EVENT_TYPES:
                        continue
                    public_event = _public_stream_event(event)
                    data = json.dumps(public_event, ensure_ascii=False)
                    yield (
                        f"id: {public_event['event_id']}\n"
                        f"event: {public_event['event_type']}\n"
                        f"data: {data}\n\n"
                    )
                run = store.load_run(run_id)
                if run.status in (rs.STATUS_COMPLETED, rs.STATUS_FAILED, rs.STATUS_CANCELLED):
                    terminal_message_missing = run.session_id and not any(
                        event["event_type"] in {"message.complete", "message.error"}
                        for event in store.load_stream_events(run_id)
                    )
                    if terminal_message_missing:
                        terminal_event_deadline = (
                            terminal_event_deadline
                            or time.monotonic() + 2 * _SSE_POLL_SECONDS
                        )
                    if (
                        terminal_message_missing
                        and time.monotonic() < terminal_event_deadline
                    ):
                        time.sleep(_SSE_POLL_SECONDS)
                        continue
                    yield (
                        "event: run\n"
                        f"data: {json.dumps(_public_run_payload(run), ensure_ascii=False)}\n\n"
                    )
                    return
                if time.monotonic() > deadline:
                    yield "event: timeout\ndata: {}\n\n"
                    return
                time.sleep(_SSE_POLL_SECONDS)

        return StreamingResponse(stream(), media_type="text/event-stream")

    @app.get("/api/runs/{run_id}/report")
    def get_run_report(run_id: str, user: str | None = None) -> dict[str, object] | None:
        store = store_for(user)
        try:
            run_dir = store.run_dir(run_id)
            if not store.run_path(run_id).exists():
                raise HTTPException(404, f"run 不存在：{run_id}")
        except ValueError as exc:
            raise HTTPException(404, f"run 不存在：{run_id}") from exc
        report_path = run_dir / "report.json"
        if report_path.is_file():
            payload = json.loads(report_path.read_text(encoding="utf-8"))
            return payload if isinstance(payload, dict) else None
        report: dict[str, object] | None = None
        for event in store.load_stream_events(run_id):
            payload = event.get("payload", {})
            if event.get("event_type") in {"report.start", "report.complete", "report.error"}:
                candidate = payload.get("report") if isinstance(payload, dict) else None
                if isinstance(candidate, dict):
                    report = candidate
            elif event.get("event_type") == "report.module" and report is not None:
                module = payload.get("module") if isinstance(payload, dict) else None
                if isinstance(module, dict):
                    upsert_report_module(report, module)
        return report

    @app.get("/api/runs/{run_id}/artifacts/{name:path}")
    def get_run_artifact(run_id: str, name: str, user: str | None = None) -> FileResponse:
        store = store_for(user)
        try:
            run_dir = store.run_dir(run_id).resolve()
        except ValueError as exc:
            raise HTTPException(404, f"run 不存在：{run_id}") from exc
        path = (run_dir / name).resolve()
        try:
            path.relative_to(run_dir)
        except ValueError as exc:
            raise HTTPException(404, f"产物不存在：{name}") from exc
        if not path.is_file():
            raise HTTPException(404, f"产物不存在：{name}")
        return FileResponse(path)

    @app.get("/api/artifacts")
    def list_artifacts(
        category: str | None = None,
        date: str | None = None,
        status: str | None = None,
        query: str | None = Query(default=None, alias="q"),
        user: str | None = None,
    ) -> list[dict[str, object]]:
        return [
            descriptor.public_dict()
            for descriptor in registry_for(user).list(
                category=category,
                date=date,
                status=status,
                query=query,
            )
        ]

    @app.get("/api/artifacts/{artifact_id}/content")
    def get_artifact_content(artifact_id: str, user: str | None = None) -> FileResponse:
        try:
            descriptor, path = registry_for(user).content_path(artifact_id)
        except KeyError as exc:
            raise HTTPException(404, f"产物未注册：{artifact_id}") from exc
        except FileNotFoundError as exc:
            raise HTTPException(404, f"产物文件不存在：{artifact_id}") from exc
        except PermissionError as exc:
            raise HTTPException(403, "产物路径不在允许目录") from exc
        headers = {}
        if descriptor.viewer == "legacy_html":
            headers["Content-Security-Policy"] = (
                "sandbox allow-scripts; default-src 'self' data: blob: https:; "
                "style-src 'self' 'unsafe-inline' https:; "
                "script-src 'self' 'unsafe-inline' https:; img-src 'self' data: blob: https:"
            )
        return FileResponse(path, headers=headers)

    @app.get("/api/artifacts/{artifact_id}/projection")
    def get_artifact_projection(
        artifact_id: str, user: str | None = None
    ) -> dict[str, object]:
        registry = registry_for(user)
        descriptor = registry.get(artifact_id)
        if descriptor is None:
            raise HTTPException(404, f"产物未注册：{artifact_id}")
        if descriptor.category not in {"daily_agent", "daily_review"}:
            raise HTTPException(404, "该产物不支持原生投影")
        if (
            descriptor.category == "daily_review"
            and not Path(descriptor.source_path).name.endswith(
                ("-daily-review.html", "-daily-review.md")
            )
        ):
            raise HTTPException(404, "该产物不支持原生投影")

        original = next(
            (
                item
                for item in registry.list(
                    category=descriptor.category,
                    date=descriptor.date,
                )
                if item.viewer == "legacy_html" and item.status != "missing"
            ),
            None,
        )
        try:
            if descriptor.category == "daily_agent":
                _, source = registry.canonical_path(artifact_id)
                payload = json.loads(source.read_text(encoding="utf-8"))
                if not isinstance(payload, dict):
                    raise ValueError("Daily Agent canonical JSON 必须是对象")
                projection = project_daily_agent(
                    payload,
                    source_path=source.relative_to(root).as_posix(),
                )
            else:
                try:
                    _, source = registry.canonical_path(artifact_id)
                except FileNotFoundError:
                    _, source = registry.content_path(artifact_id)
                source_path = source.relative_to(root).as_posix()
                if source.suffix.lower() == ".md":
                    projection = project_daily_review_markdown(
                        source.read_text(encoding="utf-8"),
                        source_path=source_path,
                        date=descriptor.date,
                    )
                elif source.suffix.lower() == ".html":
                    projection = project_daily_review_html(
                        source.read_text(encoding="utf-8"),
                        source_path=source_path,
                        date=descriptor.date,
                    )
                else:
                    raise ValueError("Daily Review 需要 canonical Markdown 或历史 HTML")
        except KeyError as exc:
            raise HTTPException(404, f"产物未注册：{artifact_id}") from exc
        except FileNotFoundError as exc:
            raise HTTPException(404, "原生投影来源不存在") from exc
        except PermissionError as exc:
            raise HTTPException(403, "投影来源路径不在允许目录") from exc
        except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as exc:
            raise HTTPException(422, f"无法生成原生投影：{exc}") from exc

        provenance = projection.get("provenance")
        if isinstance(provenance, dict) and original is not None:
            provenance["rendered_path"] = original.source_path
            provenance["original_report_available"] = True
            provenance["original_artifact_id"] = original.artifact_id
        return projection

    @app.get("/api/artifacts/{artifact_id}")
    def get_artifact_descriptor(artifact_id: str, user: str | None = None) -> dict[str, object]:
        descriptor = registry_for(user).get(artifact_id)
        if descriptor is None:
            raise HTTPException(404, f"产物未注册：{artifact_id}")
        return descriptor.public_dict()

    @app.get("/api/artifacts/{artifact_id}/{asset_path:path}")
    def get_artifact_asset(
        artifact_id: str, asset_path: str, user: str | None = None
    ) -> FileResponse:
        try:
            _, path = registry_for(user).asset_path(artifact_id, asset_path)
        except KeyError as exc:
            raise HTTPException(404, f"产物未注册：{artifact_id}") from exc
        except FileNotFoundError as exc:
            raise HTTPException(404, f"配套资源不存在：{asset_path}") from exc
        except PermissionError as exc:
            raise HTTPException(403, "配套资源路径不在产物目录内") from exc
        return FileResponse(path)

    @app.get("/api/workbench/bootstrap")
    def workbench_bootstrap(user: str | None = None) -> dict[str, object]:
        store = store_for(user)
        runs = list(reversed(store.list_runs()))[:20]
        artifacts = registry_for(user).list()
        latest_daily = next(
            (
                artifact
                for artifact in artifacts
                if artifact.category in {"daily_review", "daily_agent", "theme_candidates"}
                and artifact.status != "missing"
            ),
            None,
        )
        data_cutoff = latest_daily.date if latest_daily else next(
            (run.source_date for run in runs if run.source_date),
            None,
        )
        workflows = [
            {
                "id": "daily",
                "title": "今日复盘",
                "description": "调用 GLM 综合证据，并流式生成日报与 L2 资金流模块",
                "task_type": "daily",
                "artifact_id": latest_daily.artifact_id if latest_daily else None,
                "prompt": "基于最新收盘数据，总结今日盘面、主线、反证和下一交易日验证点。",
            },
            {
                "id": "theme",
                "title": "题材深挖",
                "description": "从产业链、证据与盘面阶段拆解题材",
                "task_type": "theme",
                "artifact_id": None,
                "prompt": "请深挖这个题材的产业链、核心矛盾、证据分层、反证和后续验证信号：",
            },
            {
                "id": "stock_research",
                "title": "个股研究",
                "description": "核对公司角色、兑现路径与风险",
                "task_type": "stock_research",
                "artifact_id": None,
                "prompt": "请研究这只股票的业务角色、受益链条、当前证据、反证和可验证节点：",
            },
        ]
        return {
            "user": store.user_id,
            "workflows": workflows,
            "recent_runs": [_public_run_payload(run) for run in runs],
            "latest_artifacts": [artifact.public_dict() for artifact in artifacts[:10]],
            "latest_daily_artifact": latest_daily.public_dict() if latest_daily else None,
            "pending_review_count": _pending_review_count(root),
            "needs_human_action": sum(
                1 for artifact in artifacts if artifact.status in {"warn", "missing"}
            ),
            "data_cutoff": data_cutoff,
            "self_use_maturity": self_use_projection(user),
        }

    @app.get("/api/workbench/overview")
    def workbench_overview() -> dict[str, object]:
        return build_workbench_overview(root, runtime_paths.knowledge_wiki)

    learning_root = root / "docs" / "learning" / "forecast-lessons"

    @app.get("/api/workbench/learning-feedback")
    def workbench_learning_feedback() -> dict[str, object]:
        return learning_feedback_projection(learning_root)

    @app.post("/api/workbench/learning-feedback/reflections/{filename}/approve")
    def approve_learning_reflection(
        filename: str,
        req: ApproveReflectionRequest,
    ) -> dict[str, object]:
        if Path(filename).name != filename or not filename.endswith(".json"):
            raise HTTPException(400, "invalid reflection filename")
        reflection = learning_root / "reflections" / filename
        if not reflection.is_file():
            raise HTTPException(404, "reflection not found")
        try:
            approve_reflection(
                reflection,
                learning_root / "lessons.jsonl",
                hypothesis_ids=req.hypothesis_ids,
            )
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        return learning_feedback_projection(learning_root)

    @app.post("/api/workbench/learning-feedback/reflections/{filename}/reject")
    def reject_learning_reflection(
        filename: str,
        req: ApproveReflectionRequest,
    ) -> dict[str, object]:
        if Path(filename).name != filename or not filename.endswith(".json"):
            raise HTTPException(400, "invalid reflection filename")
        reflection = learning_root / "reflections" / filename
        if not reflection.is_file():
            raise HTTPException(404, "reflection not found")
        try:
            reject_reflection(reflection, hypothesis_ids=req.hypothesis_ids)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        return learning_feedback_projection(learning_root)

    @app.post("/api/workbench/learning-feedback/rules/{candidate_id}/status")
    def update_learning_rule(
        candidate_id: str,
        req: RuleStatusRequest,
    ) -> dict[str, object]:
        try:
            set_rule_status(
                learning_root / "rule_candidates.jsonl",
                candidate_id,
                req.status,
            )
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from exc
        return learning_feedback_projection(learning_root)

    assets_dir = STATIC_DIR / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/")
    def index() -> FileResponse:
        if not (STATIC_DIR / "index.html").is_file():
            raise HTTPException(503, "Workbench 前端尚未构建")
        return FileResponse(STATIC_DIR / "index.html")

    return app


app = create_app()
