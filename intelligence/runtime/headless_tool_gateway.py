"""Run-scoped loopback gateway for Codex headless finance tools."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from contextvars import Context, copy_context
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import secrets
import stat
import tempfile
import time
from threading import Event, Lock, Thread
from types import TracebackType
import urllib.error
import urllib.parse
import urllib.request

from intelligence.services.agent_research import AgentEvidence
from intelligence.services.agent_runtime import EpisodeEvent, public_agent_evidence
from intelligence.services.episode_scope import EpisodeScope
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.research_contract import ResearchRunContext
from intelligence.services.research_tool_registry import (
    copy_tool_parameters,
    InvalidResearchToolArguments,
    PreparedToolArguments,
    ResearchToolRegistry,
    ToolObservation,
    ToolSpec,
)


_MAX_REQUEST_BYTES = 65_536
_WRAPPER_NAME = "finance-tool"
_MAILBOX_NAME = ".finance-tool-mailbox"
_REQUEST_ID_RE = re.compile(r"^[0-9a-f]{32}$")
_MAILBOX_REQUEST_RE = re.compile(r"^[0-9a-f]{32}\.json$")
_MAX_RESPONSE_BYTES = 1_048_576
TOOL_TRANSPORT_TIMEOUT_SECONDS = 60.0
TOOL_RESPONSE_PUBLISH_MARGIN_SECONDS = 1.0
FINALIZATION_INSTRUCTION = "研究取证阶段已结束，请使用已有信息完成终止回答。"
_FINALIZATION_REASONS = frozenset(
    {
        "research_stage_closed",
        "tool_budget_exhausted",
        "deadline_pressure",
        "headless_invalid_finish",
        "headless_no_finish",
    }
)
_FINALIZATION_REASON_BY_REJECTION = {
    "research_stage_closed": "research_stage_closed",
    "tool_budget_exhausted": "tool_budget_exhausted",
    "root_budget_exhausted": "tool_budget_exhausted",
}
_ROOT_BUDGET_CALL_RESERVATION_SECONDS = 1e-9
_TRANSPORT_TIMEOUT_TOKEN = "__TOOL_TIMEOUT__"


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace(
        "+00:00", "Z"
    )


def _render_wrapper_timeout(source: str) -> str:
    if source.count(_TRANSPORT_TIMEOUT_TOKEN) != 1:
        raise RuntimeError("headless wrapper must contain one timeout token")
    return source.replace(
        _TRANSPORT_TIMEOUT_TOKEN,
        repr(TOOL_TRANSPORT_TIMEOUT_SECONDS),
    )


def _is_snapshot_tool(spec: ToolSpec) -> bool:
    properties = spec.parameters.get("properties")
    return isinstance(properties, Mapping) and not properties


def _transport_arguments(spec: ToolSpec, query: str) -> object:
    if _is_snapshot_tool(spec):
        return {}
    properties = spec.parameters.get("properties")
    if isinstance(properties, Mapping) and set(properties) == {"query"}:
        return query
    try:
        value = json.loads(query)
    except json.JSONDecodeError as exc:
        raise InvalidResearchToolArguments(
            "structured tool input must be a JSON object"
        ) from exc
    if not isinstance(value, dict):
        raise InvalidResearchToolArguments(
            "structured tool input must be a JSON object"
        )
    return value


@dataclass(frozen=True)
class _EffectiveBudget:
    remaining_calls: int
    remaining_root_seconds: float
    remaining_research_seconds: float


@dataclass(frozen=True)
class _ToolGrant:
    seconds: float
    limiter: str


@dataclass(frozen=True)
class HeadlessMailboxExchange:
    request_id: str
    request_sha256: str
    response_sha256: str

    def __post_init__(self) -> None:
        if not _MAILBOX_REQUEST_RE.fullmatch(self.request_id):
            raise ValueError("invalid mailbox request id")
        for value in (self.request_sha256, self.response_sha256):
            if not re.fullmatch(r"[0-9a-f]{64}", value):
                raise ValueError("invalid mailbox exchange hash")

    def to_dict(self) -> dict[str, str]:
        return {
            "request_id": self.request_id,
            "request_sha256": self.request_sha256,
            "response_sha256": self.response_sha256,
        }


@dataclass(frozen=True)
class HeadlessGatewaySnapshot:
    evidence: tuple[AgentEvidence, ...]
    traces: tuple[ProviderTrace, ...]
    events: tuple[EpisodeEvent, ...]
    gaps: tuple[str, ...]
    executed_count: int
    duplicate_queries: int
    mailbox_exchanges: tuple[HeadlessMailboxExchange, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "evidence": [public_agent_evidence(item) for item in self.evidence],
            "traces": [item.to_dict() for item in self.traces],
            "events": [item.to_dict() for item in self.events],
            "gaps": list(self.gaps),
            "executed_count": self.executed_count,
            "duplicate_queries": self.duplicate_queries,
            "mailbox_exchanges": [
                item.to_dict() for item in self.mailbox_exchanges
            ],
        }


class HeadlessToolGateway:
    """Expose one canonical registry through an ephemeral loopback endpoint."""

    def __init__(
        self,
        *,
        registry: ResearchToolRegistry,
        context: ResearchRunContext,
        is_cancelled: Callable[[], bool] | None = None,
        run_dir: Path | None = None,
        transport: str = "http",
        finalization_floor_ratio: float = 0.65,
        scope: EpisodeScope | None = None,
    ) -> None:
        selected_transport = str(transport or "").strip().lower()
        if selected_transport not in {"http", "mailbox"}:
            raise ValueError("unsupported headless tool transport")
        floor_ratio = float(finalization_floor_ratio)
        if not 0.0 <= floor_ratio <= 1.0:
            raise ValueError("headless finalization floor ratio must be between 0 and 1")
        self._registry = registry
        self._context = context
        initial_research_seconds = context.deadline.stage_timeout(
            context.deadline.remaining()
        )
        self._finalization_floor_seconds = min(
            45.0,
            max(5.0, initial_research_seconds * floor_ratio),
        )
        self._finalization_handoff_seconds = min(
            initial_research_seconds,
            max(0.0, float(context.deadline.synthesis_reserve)),
        )
        self._is_cancelled = is_cancelled or (lambda: False)
        self._authorized = {
            spec.name: spec
            for spec in registry.authorized_specs(
                context.contract.allowed_capabilities
            )
        }
        if scope is not None:
            if scope.episode_id != context.contract.task_id:
                raise ValueError("gateway scope episode_id mismatch")
            if scope.task_frame_hash != context.contract.task_frame_hash:
                raise ValueError("gateway scope task_frame_hash mismatch")
        self._scope = scope
        self._requested_run_dir = run_dir
        self._transport = selected_transport
        self._temporary_directory: tempfile.TemporaryDirectory[str] | None = None
        self._run_dir: Path | None = None
        self._wrapper_path: Path | None = None
        self._server: ThreadingHTTPServer | None = None
        self._thread: Thread | None = None
        self._mailbox_dir: Path | None = None
        self._mailbox_stop = Event()
        self._endpoint = ""
        self._bearer = secrets.token_urlsafe(32)
        self._lock = Lock()
        self._contextvars: Context = copy_context()
        self._seen_queries: set[tuple[str, str]] = set()
        self._successful_episode_tools: set[str] = set()
        self._evidence: list[AgentEvidence] = []
        self._evidence_hashes: set[str] = set()
        self._traces: list[ProviderTrace] = []
        self._events: list[EpisodeEvent] = []
        self._gaps: list[str] = []
        self._executed_count = 0
        self._duplicate_queries = 0
        self._mailbox_exchanges: list[HeadlessMailboxExchange] = []
        self._finalization_event: EpisodeEvent | None = None
        self._next_sequence = 2
        self._closed = False

    def __enter__(self) -> HeadlessToolGateway:
        return self.start()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type, exc, traceback
        self.close()

    @property
    def endpoint(self) -> str:
        if not self._endpoint:
            raise RuntimeError("headless tool gateway has not started")
        return self._endpoint

    @property
    def wrapper_path(self) -> Path:
        if self._wrapper_path is None:
            raise RuntimeError("headless tool gateway has not started")
        return self._wrapper_path

    @property
    def scope_attached(self) -> bool:
        """spec §8.2：窄协议是否带上了 EpisodeScope。缺省 False，行为与接线前一致。"""

        return self._scope is not None

    def start(self) -> HeadlessToolGateway:
        if self._server is not None:
            return self
        if self._closed:
            raise RuntimeError("closed headless tool gateway cannot restart")
        if self._requested_run_dir is None:
            self._temporary_directory = tempfile.TemporaryDirectory(
                prefix="finance-headless-tools-"
            )
            self._run_dir = Path(self._temporary_directory.name)
        else:
            self._run_dir = self._requested_run_dir.resolve()
            self._run_dir.mkdir(parents=True, exist_ok=True)
        self._wrapper_path = self._write_wrapper(self._run_dir)

        if self._transport == "mailbox":
            self._mailbox_dir = self._run_dir / _MAILBOX_NAME
            self._ensure_private_mailbox_directory(self._mailbox_dir)
            self._ensure_private_mailbox_directory(
                self._mailbox_dir / "requests"
            )
            self._ensure_private_mailbox_directory(
                self._mailbox_dir / "responses"
            )
            self._thread = Thread(
                target=self._serve_mailbox,
                name="headless-finance-mailbox",
                daemon=True,
            )
            self._thread.start()
            return self

        gateway = self

        class Handler(BaseHTTPRequestHandler):
            server_version = "FinanceToolGateway/1"

            def log_message(self, _format: str, *args: object) -> None:
                del args

            def do_POST(self) -> None:  # noqa: N802 - stdlib handler contract
                gateway._serve_request(self)

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        server.daemon_threads = True
        host, port = server.server_address[:2]
        if host != "127.0.0.1":
            server.server_close()
            raise RuntimeError("headless tool gateway must bind to loopback")
        self._server = server
        self._endpoint = f"http://127.0.0.1:{port}"
        self._thread = Thread(
            target=server.serve_forever,
            name="headless-finance-tools",
            daemon=True,
        )
        self._thread.start()
        return self

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._mailbox_stop.set()
        server, thread = self._server, self._thread
        self._server = None
        self._thread = None
        if server is not None:
            server.shutdown()
            server.server_close()
        if thread is not None:
            thread.join(timeout=2.0)
        if self._temporary_directory is not None:
            self._temporary_directory.cleanup()
            self._temporary_directory = None

    def subprocess_environment(self) -> dict[str, str]:
        if self._transport == "mailbox":
            if self._mailbox_dir is None:
                raise RuntimeError("headless tool gateway has not started")
            return {"FINANCE_TOOL_MAILBOX": str(self._mailbox_dir)}
        return {
            "FINANCE_TOOL_GATEWAY_URL": self.endpoint,
            "FINANCE_TOOL_GATEWAY_TOKEN": self._bearer,
        }

    def call(self, tool: str, query: str, *, timeout: float = 5.0) -> dict[str, object]:
        """Use the same HTTP surface as the headless child process."""

        if self._transport == "mailbox":
            del timeout
            return self._execute_tool(tool, query)

        name = urllib.parse.quote(str(tool), safe="")
        request = urllib.request.Request(
            f"{self.endpoint}/tool/{name}",
            data=json.dumps({"query": query}, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self._bearer}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            value = json.loads(response.read().decode("utf-8"))
        if not isinstance(value, dict):
            raise RuntimeError("headless tool gateway returned a non-object")
        return value

    def _serve_mailbox(self) -> None:
        mailbox = self._mailbox_dir
        if mailbox is None:
            return
        requests_dir = mailbox / "requests"
        responses_dir = mailbox / "responses"
        while not self._mailbox_stop.wait(0.01):
            try:
                requests = tuple(requests_dir.iterdir())
            except OSError:
                continue
            for request_path in requests:
                if not _MAILBOX_REQUEST_RE.fullmatch(request_path.name):
                    continue
                response_path = responses_dir / request_path.name
                self._process_mailbox_request(request_path, response_path)

    def _process_mailbox_request(
        self,
        request_path: Path,
        response_path: Path,
    ) -> None:
        request_sha256 = hashlib.sha256(b"").hexdigest()
        try:
            raw = self._read_mailbox_request(request_path)
            request_sha256 = hashlib.sha256(raw).hexdigest()
            payload = json.loads(raw.decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("request must be an object")
            result = self._execute_tool(
                str(payload.get("tool") or ""),
                payload.get("query"),
                request_id=request_path.stem,
            )
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
            result = {"status": "rejected", "error": "invalid_request"}
        finally:
            try:
                request_path.unlink(missing_ok=True)
            except OSError:
                pass
        try:
            response_sha256 = self._write_mailbox_response(
                response_path,
                result,
                request_sha256=request_sha256,
            )
        except OSError:
            with self._lock:
                if "mailbox_response_path_conflict" not in self._gaps:
                    self._gaps.append("mailbox_response_path_conflict")
                self._add_event(
                    "tool_error",
                    {
                        "request_id": request_path.stem,
                        "tool": "mailbox",
                        "error": "response_path_conflict",
                    },
                )
            return
        with self._lock:
            self._mailbox_exchanges.append(
                HeadlessMailboxExchange(
                    request_id=request_path.name,
                    request_sha256=request_sha256,
                    response_sha256=response_sha256,
                )
            )

    @staticmethod
    def _read_mailbox_request(path: Path) -> bytes:
        flags = os.O_RDONLY
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(path, flags)
        try:
            metadata = os.fstat(descriptor)
            if not stat.S_ISREG(metadata.st_mode):
                raise ValueError("request must be a regular file")
            if metadata.st_size < 1 or metadata.st_size > _MAX_REQUEST_BYTES:
                raise ValueError("request size is invalid")
            chunks: list[bytes] = []
            remaining = metadata.st_size
            while remaining > 0:
                chunk = os.read(descriptor, remaining)
                if not chunk:
                    break
                chunks.append(chunk)
                remaining -= len(chunk)
            value = b"".join(chunks)
            if len(value) != metadata.st_size:
                raise ValueError("request read was incomplete")
            return value
        finally:
            os.close(descriptor)

    @staticmethod
    def _write_mailbox_response(
        path: Path,
        payload: dict[str, object],
        *,
        request_sha256: str,
    ) -> str:
        envelope = dict(payload)
        envelope["mailbox_request_sha256"] = request_sha256
        encoded = json.dumps(
            envelope,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        HeadlessToolGateway._publish_exclusive(path, encoded)
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def _publish_exclusive(path: Path, encoded: bytes) -> None:
        temporary = path.with_name(f".{path.name}.{secrets.token_hex(8)}.tmp")
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(temporary, flags, 0o600)
        try:
            offset = 0
            while offset < len(encoded):
                offset += os.write(descriptor, encoded[offset:])
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        try:
            os.link(temporary, path, follow_symlinks=False)
        finally:
            temporary.unlink(missing_ok=True)

    @staticmethod
    def _ensure_private_mailbox_directory(path: Path) -> None:
        try:
            metadata = path.lstat()
        except FileNotFoundError:
            path.mkdir(mode=0o700)
            metadata = path.lstat()
        if stat.S_ISLNK(metadata.st_mode):
            raise ValueError("mailbox directory must not be a symlink")
        if not stat.S_ISDIR(metadata.st_mode):
            raise ValueError("mailbox path must be a directory")
        if metadata.st_uid != os.getuid():
            raise ValueError("mailbox directory owner mismatch")
        if stat.S_IMODE(metadata.st_mode) != 0o700:
            raise ValueError("mailbox directory mode must be 0700")

    def snapshot(self) -> HeadlessGatewaySnapshot:
        with self._lock:
            return HeadlessGatewaySnapshot(
                evidence=tuple(self._evidence),
                traces=tuple(self._traces),
                events=tuple(self._events),
                gaps=tuple(self._gaps),
                executed_count=self._executed_count,
                duplicate_queries=self._duplicate_queries,
                mailbox_exchanges=tuple(self._mailbox_exchanges),
            )

    def begin_finalization(self, reason: str) -> EpisodeEvent:
        """Record one real control-plane transition into answer finalization."""

        with self._lock:
            return self._begin_finalization_locked(reason)

    def _begin_finalization_locked(self, reason: str) -> EpisodeEvent:
        if reason not in _FINALIZATION_REASONS:
            raise ValueError("unsupported headless finalization reason")
        if self._finalization_event is not None:
            return self._finalization_event
        remaining_seconds = self._context.deadline.stage_timeout(
            self._context.deadline.remaining()
        )
        event = self._add_event(
            "finalization",
            {
                "reason": reason,
                "remaining_seconds": round(remaining_seconds, 3),
                "timestamp": _utc_timestamp(),
            },
        )
        self._finalization_event = event
        return event

    def _effective_budget(self) -> _EffectiveBudget:
        remaining_root_seconds = max(
            0.0,
            float(self._context.deadline.remaining()),
        )
        remaining_research_seconds = self._context.deadline.stage_timeout(
            remaining_root_seconds
        )
        remaining_calls = max(
            0,
            int(self._context.policy.max_steps) - self._executed_count,
        )
        ledger = getattr(self._context, "root_budget", None)
        ledger_calls = getattr(ledger, "remaining_calls", None)
        if isinstance(ledger_calls, int) and not isinstance(ledger_calls, bool):
            remaining_calls = min(remaining_calls, max(0, ledger_calls))
        ledger_seconds = getattr(ledger, "remaining_seconds", None)
        if isinstance(ledger_seconds, (int, float)) and not isinstance(
            ledger_seconds, bool
        ):
            remaining_research_seconds = min(
                remaining_research_seconds,
                max(0.0, float(ledger_seconds)),
            )
        return _EffectiveBudget(
            remaining_calls=remaining_calls,
            remaining_root_seconds=remaining_root_seconds,
            remaining_research_seconds=remaining_research_seconds,
        )

    def _tool_grant(self, budget: _EffectiveBudget) -> _ToolGrant:
        deadline_safe_seconds = max(
            0.0,
            budget.remaining_research_seconds - self._finalization_handoff_seconds,
        )
        transport_safe_seconds = max(
            0.0,
            TOOL_TRANSPORT_TIMEOUT_SECONDS - TOOL_RESPONSE_PUBLISH_MARGIN_SECONDS,
        )
        if deadline_safe_seconds <= transport_safe_seconds:
            return _ToolGrant(deadline_safe_seconds, "handoff_window")
        return _ToolGrant(transport_safe_seconds, "transport_timeout")

    def _pending_finalization_reason(
        self,
        budget: _EffectiveBudget | None = None,
    ) -> str | None:
        if self._finalization_event is not None:
            return str(self._finalization_event.payload["reason"])
        effective = budget if budget is not None else self._effective_budget()
        if effective.remaining_calls <= 0:
            return "tool_budget_exhausted"
        if (
            effective.remaining_research_seconds
            <= self._finalization_handoff_seconds
        ):
            return "deadline_pressure"
        if (
            self._executed_count > 0
            and effective.remaining_research_seconds
            <= self._finalization_floor_seconds
        ):
            return "research_stage_closed"
        return None

    def _serve_request(self, handler: BaseHTTPRequestHandler) -> None:
        if handler.headers.get("Authorization") != f"Bearer {self._bearer}":
            self._send(handler, 401, {"status": "rejected", "error": "unauthorized"})
            return
        parsed = urllib.parse.urlparse(handler.path)
        parts = parsed.path.strip("/").split("/")
        if len(parts) != 2 or parts[0] != "tool":
            self._send(handler, 404, {"status": "rejected", "error": "not_found"})
            return
        try:
            content_length = int(handler.headers.get("Content-Length") or "0")
        except ValueError:
            content_length = -1
        if content_length < 0 or content_length > _MAX_REQUEST_BYTES:
            self._send(
                handler,
                413,
                {"status": "rejected", "error": "request_too_large"},
            )
            return
        try:
            payload = json.loads(handler.rfile.read(content_length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._send(
                handler,
                400,
                {"status": "rejected", "error": "invalid_json"},
            )
            return
        query = payload.get("query") if isinstance(payload, dict) else None
        result = self._execute_tool(urllib.parse.unquote(parts[1]), query)
        self._send(handler, 200, result)

    @staticmethod
    def _send(
        handler: BaseHTTPRequestHandler,
        status: int,
        payload: dict[str, object],
    ) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        handler.send_response(status)
        handler.send_header("Content-Type", "application/json; charset=utf-8")
        handler.send_header("Content-Length", str(len(data)))
        handler.end_headers()
        handler.wfile.write(data)

    def _execute_tool(
        self,
        name: str,
        raw_query: object,
        *,
        request_id: str | None = None,
    ) -> dict[str, object]:
        resolved_request_id = (
            secrets.token_hex(16) if request_id is None else request_id
        )
        if not _REQUEST_ID_RE.fullmatch(resolved_request_id):
            raise ValueError("invalid headless tool request id")
        with self._lock:
            budget = self._effective_budget()
            grant = self._tool_grant(budget)
            request_event = self._add_event(
                "tool_request",
                {
                    "request_id": resolved_request_id,
                    "tool": name,
                    "query": str(raw_query or ""),
                    "timestamp": _utc_timestamp(),
                    "remaining_root_seconds_at_entry": round(
                        budget.remaining_root_seconds,
                        3,
                    ),
                    "remaining_research_seconds_at_entry": round(
                        budget.remaining_research_seconds,
                        3,
                    ),
                    "finalization_handoff_seconds": round(
                        self._finalization_handoff_seconds,
                        3,
                    ),
                    "transport_timeout_seconds": TOOL_TRANSPORT_TIMEOUT_SECONDS,
                    "tool_grant_seconds": round(grant.seconds, 3),
                    "tool_grant_limiter": grant.limiter,
                },
            )
            step_id = (
                f"{self._context.trace_parent_id}:headless:tool:"
                f"{request_event.sequence - 1}"
            )
            spec = self._authorized.get(name)
            if self._scope is not None and not self._scope.authorize(name).allowed:
                spec = None
            if spec is None:
                rejected = "unknown_or_unauthorized_tool"
                prepared = None
            elif not isinstance(raw_query, str) or not raw_query.strip():
                rejected = "invalid_query"
                prepared = None
            else:
                try:
                    prepared = self._registry.prepare(
                        name,
                        _transport_arguments(spec, raw_query.strip()),
                    )
                except InvalidResearchToolArguments as exc:
                    rejected = exc.code
                    prepared = None
                else:
                    rejected = self._reservation_error(
                        spec,
                        prepared,
                        budget=budget,
                        grant=grant,
                    )
                    if rejected is None and not self._reserve_root_call_locked():
                        rejected = "root_budget_exhausted"
            if rejected is not None:
                finalization_reason = _FINALIZATION_REASON_BY_REJECTION.get(rejected)
                self._add_event(
                    "tool_error",
                    {
                        "request_id": resolved_request_id,
                        "tool": name,
                        "error": rejected,
                        "retryable": (
                            rejected == "invalid_arguments" and spec is not None
                        ),
                    },
                )
                if finalization_reason is not None:
                    self._begin_finalization_locked(finalization_reason)
                rejection: dict[str, object] = {
                    "status": "rejected",
                    "tool": name,
                    "error": rejected,
                    "budget": self._budget_payload(budget),
                }
                if rejected == "invalid_arguments" and spec is not None:
                    rejection.update(
                        {
                            "retryable": True,
                            "expected_parameters": copy_tool_parameters(
                                spec.parameters
                            ),
                            "retry_hint": (
                                "retry this tool with one single-line JSON object "
                                "matching expected_parameters"
                            ),
                        }
                    )
                if finalization_reason is not None:
                    rejection["instruction"] = FINALIZATION_INSTRUCTION
                return rejection
            if spec is None or prepared is None:
                raise RuntimeError("prepared headless tool request missing")
            self._seen_queries.add((name, prepared.normalized_key))
            self._executed_count += 1

        started_at = time.monotonic()
        try:
            observation = self._contextvars.copy().run(
                self._registry.execute,
                name,
                prepared,
                context=self._context,
                step_id=step_id,
                is_cancelled=self._is_cancelled,
            )
        except Exception:
            trace = ProviderTrace(
                provider=f"headless:{name}",
                capability=name,
                status="request_error",
                detail="tool_exception",
                parent_id=self._context.trace_parent_id,
                step_id=step_id,
            )
            with self._lock:
                self._traces.append(trace)
                self._add_event(
                    "tool_error",
                    {
                        "request_id": resolved_request_id,
                        "tool": name,
                        "error": "tool_exception",
                    },
                )
            self._settle_root_seconds(
                time.monotonic() - started_at,
                request_id=resolved_request_id,
            )
            return {"status": "error", "tool": name, "error": "tool_exception"}

        if self._scope is not None:
            self._scope.record_invocation(name)

        self._settle_root_seconds(
            time.monotonic() - started_at,
            request_id=resolved_request_id,
        )

        return self._publish_observation(
            spec.query_scope,
            observation,
            request_id=resolved_request_id,
        )

    def _reserve_root_call_locked(self) -> bool:
        """Claim one root call slot atomically before the tool runs at all."""

        ledger = getattr(self._context, "root_budget", None)
        consume_call = getattr(ledger, "consume_call", None)
        if not callable(consume_call):
            return True
        try:
            consume_call(seconds=_ROOT_BUDGET_CALL_RESERVATION_SECONDS)
        except (TypeError, ValueError):
            return False
        return True

    def _settle_root_seconds(
        self,
        elapsed_seconds: float,
        *,
        request_id: str,
    ) -> None:
        """Debit real tool wall time, clamping rather than rejecting finished work."""

        ledger = getattr(self._context, "root_budget", None)
        try:
            requested = max(0.001, float(elapsed_seconds))
        except (TypeError, ValueError):
            return

        settle_seconds = getattr(ledger, "settle_seconds", None)
        if callable(settle_seconds):
            # Preferred path: the ledger clamps and debits under its own lock, so
            # concurrent settling cannot lose a debit to a check-then-act race.
            try:
                settled = float(settle_seconds(seconds=requested))
            except (TypeError, ValueError) as exc:
                self._record_settlement_failure(
                    request_id=request_id,
                    requested=requested,
                    error=type(exc).__name__,
                )
                return
        else:
            settled = self._settle_root_seconds_legacy(
                ledger,
                requested=requested,
                request_id=request_id,
            )
            if settled is None:
                return

        overdraft = requested - settled
        if overdraft <= 0.0:
            return
        with self._lock:
            self._add_event(
                "root_budget_overdraft",
                {
                    "request_id": request_id,
                    "requested_seconds": round(requested, 3),
                    "settled_seconds": round(settled, 3),
                    "overdraft_seconds": round(overdraft, 3),
                },
            )

    def _settle_root_seconds_legacy(
        self,
        ledger: object,
        *,
        requested: float,
        request_id: str,
    ) -> float | None:
        """Settle against ledgers predating ``settle_seconds`` (third-party/test stubs).

        This path keeps the old read-then-debit shape and is therefore racy; it
        exists only for backward compatibility. Unlike the original code it never
        fails silently -- a rejected debit is surfaced as telemetry.
        """

        consume_seconds = getattr(ledger, "consume_seconds", None)
        if not callable(consume_seconds):
            return None
        remaining = getattr(ledger, "remaining_seconds", None)
        if isinstance(remaining, (int, float)) and not isinstance(remaining, bool):
            settled = min(requested, max(0.0, float(remaining)))
        else:
            settled = requested
        try:
            consume_seconds(seconds=settled)
        except (TypeError, ValueError) as exc:
            self._record_settlement_failure(
                request_id=request_id,
                requested=requested,
                error=type(exc).__name__,
            )
            return None
        return settled

    def _record_settlement_failure(
        self,
        *,
        request_id: str,
        requested: float,
        error: str,
    ) -> None:
        """Surface a dropped seconds debit instead of swallowing it."""

        with self._lock:
            self._add_event(
                "root_budget_overdraft",
                {
                    "request_id": request_id,
                    "requested_seconds": round(requested, 3),
                    "settled_seconds": 0.0,
                    "overdraft_seconds": round(requested, 3),
                    "settlement_failed": True,
                    "error": error,
                },
            )

    def _reservation_error(
        self,
        spec: ToolSpec,
        prepared: PreparedToolArguments,
        *,
        budget: _EffectiveBudget,
        grant: _ToolGrant,
    ) -> str | None:
        if self._closed or self._is_cancelled():
            return "cancelled"
        if self._finalization_event is not None:
            return "research_stage_closed"
        if budget.remaining_calls <= 0:
            return "tool_budget_exhausted"
        if budget.remaining_root_seconds <= 0.0 or grant.seconds <= 0.0:
            return "research_stage_closed"
        if (
            self._executed_count > 0
            and budget.remaining_research_seconds
            <= self._finalization_floor_seconds
        ):
            return "research_stage_closed"
        key = (spec.name, prepared.normalized_key)
        if (
            spec.query_scope == "episode"
            and spec.name in self._successful_episode_tools
        ):
            return "episode_snapshot_already_collected"
        if key in self._seen_queries:
            self._duplicate_queries += 1
            return "duplicate_query"
        return None

    def _publish_observation(
        self,
        query_scope: str,
        observation: ToolObservation,
        *,
        request_id: str,
    ) -> dict[str, object]:
        with self._lock:
            if self._closed or self._is_cancelled():
                self._add_event(
                    "tool_error",
                    {
                        "request_id": request_id,
                        "tool": observation.tool,
                        "error": "cancelled",
                    },
                )
                return {
                    "status": "rejected",
                    "tool": observation.tool,
                    "error": "cancelled",
                }
            self._traces.append(observation.trace)
            for gap in observation.gaps:
                cleaned = gap.strip()
                if cleaned and cleaned not in self._gaps:
                    self._gaps.append(cleaned)
            for item in observation.evidence:
                if item.content_hash in self._evidence_hashes:
                    continue
                self._evidence_hashes.add(item.content_hash)
                self._evidence.append(item)
            if query_scope == "episode" and observation.evidence:
                self._successful_episode_tools.add(observation.tool)
            status = "success" if observation.evidence else "empty"
            budget = self._effective_budget()
            payload: dict[str, object] = {
                "status": status,
                "tool": observation.tool,
                "query": observation.query,
                "observation": observation.observation,
                "evidence": [
                    public_agent_evidence(item) for item in observation.evidence
                ],
                "evidence_hashes": list(observation.evidence_hashes),
                "gaps": list(observation.gaps),
                "budget": self._budget_payload(budget),
            }
            finalization_reason = self._pending_finalization_reason(budget)
            if finalization_reason is not None:
                payload["instruction"] = FINALIZATION_INSTRUCTION
            self._add_event(
                "tool_result",
                {**payload, "request_id": request_id},
            )
            if finalization_reason is not None:
                self._begin_finalization_locked(finalization_reason)
            return payload

    def _budget_payload(
        self,
        budget: _EffectiveBudget | None = None,
    ) -> dict[str, object]:
        effective = budget if budget is not None else self._effective_budget()
        return {
            "max_tool_calls": int(self._context.policy.max_steps),
            "executed_tool_calls": self._executed_count,
            "remaining_tool_calls": effective.remaining_calls,
            "remaining_research_seconds": round(
                effective.remaining_research_seconds,
                3,
            ),
            "must_finalize": self._pending_finalization_reason(effective) is not None,
        }

    def _add_event(self, kind: str, payload: dict[str, object]) -> EpisodeEvent:
        event = EpisodeEvent(self._next_sequence, kind, payload)
        self._next_sequence += 1
        self._events.append(event)
        return event

    def _write_wrapper(self, run_dir: Path) -> Path:
        wrapper = run_dir / _WRAPPER_NAME
        if self._transport == "mailbox":
            wrapper.write_text(
                _render_wrapper_timeout("""#!/usr/bin/env python3
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import time
import uuid

if len(sys.argv) != 3:
    raise SystemExit("usage: finance-tool TOOL QUERY")
mailbox = Path(os.environ["FINANCE_TOOL_MAILBOX"])
for directory in (mailbox, mailbox / "requests", mailbox / "responses"):
    metadata = directory.lstat()
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
        raise SystemExit("finance tool mailbox directory is invalid")
    if metadata.st_uid != os.getuid() or stat.S_IMODE(metadata.st_mode) != 0o700:
        raise SystemExit("finance tool mailbox permissions are invalid")
request_id = f"{uuid.uuid4().hex}.json"
request_path = mailbox / "requests" / request_id
response_path = mailbox / "responses" / request_id
try:
    response_path.lstat()
except FileNotFoundError:
    pass
else:
    raise SystemExit("finance tool mailbox response path already exists")
encoded = json.dumps(
    {"tool": sys.argv[1], "query": sys.argv[2]},
    ensure_ascii=False,
    separators=(",", ":"),
    sort_keys=True,
).encode("utf-8")
request_sha256 = hashlib.sha256(encoded).hexdigest()
temporary = request_path.with_name(f".{request_id}.{os.getpid()}.tmp")
flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
if hasattr(os, "O_NOFOLLOW"):
    flags |= os.O_NOFOLLOW
descriptor = os.open(temporary, flags, 0o600)
try:
    offset = 0
    while offset < len(encoded):
        offset += os.write(descriptor, encoded[offset:])
    os.fsync(descriptor)
finally:
    os.close(descriptor)
try:
    os.link(temporary, request_path, follow_symlinks=False)
finally:
    temporary.unlink(missing_ok=True)
deadline = time.monotonic() + __TOOL_TIMEOUT__
while time.monotonic() < deadline:
    try:
        read_flags = os.O_RDONLY
        if hasattr(os, "O_NOFOLLOW"):
            read_flags |= os.O_NOFOLLOW
        descriptor = os.open(response_path, read_flags)
    except FileNotFoundError:
        time.sleep(0.02)
        continue
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or not 1 <= metadata.st_size <= 1048576:
            raise SystemExit("finance tool mailbox response is invalid")
        payload = b""
        while len(payload) < metadata.st_size:
            chunk = os.read(descriptor, metadata.st_size - len(payload))
            if not chunk:
                break
            payload += chunk
    finally:
        os.close(descriptor)
    if len(payload) != metadata.st_size:
        raise SystemExit("finance tool mailbox response is incomplete")
    value = json.loads(payload.decode("utf-8"))
    if not isinstance(value, dict):
        raise SystemExit("finance tool mailbox response is invalid")
    if value.pop("mailbox_request_sha256", "") != request_sha256:
        raise SystemExit("finance tool mailbox response hash mismatch")
    response_path.unlink(missing_ok=True)
    sys.stdout.write(json.dumps(value, ensure_ascii=False))
    raise SystemExit(0)
raise SystemExit("finance tool mailbox timed out")
"""),
                encoding="utf-8",
            )
            wrapper.chmod(0o700)
            return wrapper
        wrapper.write_text(
            _render_wrapper_timeout("""#!/usr/bin/env python3
import json
import os
import sys
import urllib.parse
import urllib.request

if len(sys.argv) != 3:
    raise SystemExit("usage: finance-tool TOOL QUERY")
endpoint = os.environ["FINANCE_TOOL_GATEWAY_URL"].rstrip("/")
token = os.environ["FINANCE_TOOL_GATEWAY_TOKEN"]
tool = urllib.parse.quote(sys.argv[1], safe="")
request = urllib.request.Request(
    f"{endpoint}/tool/{tool}",
    data=json.dumps({"query": sys.argv[2]}, ensure_ascii=False).encode("utf-8"),
    headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    },
    method="POST",
)
with urllib.request.urlopen(request, timeout=__TOOL_TIMEOUT__) as response:
    sys.stdout.write(response.read().decode("utf-8"))
"""),
            encoding="utf-8",
        )
        wrapper.chmod(0o700)
        return wrapper


__all__ = [
    "HeadlessGatewaySnapshot",
    "HeadlessMailboxExchange",
    "HeadlessToolGateway",
]
