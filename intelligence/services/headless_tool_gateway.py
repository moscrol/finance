"""Run-scoped loopback gateway for Codex headless finance tools."""

from __future__ import annotations

from collections.abc import Callable
from contextvars import Context, copy_context
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import tempfile
from threading import Lock, Thread
from types import TracebackType
from typing import cast
import urllib.error
import urllib.parse
import urllib.request

from intelligence.services import query_ledger
from intelligence.services.agent_research import AgentEvidence
from intelligence.services.agent_runtime import EpisodeEvent, public_agent_evidence
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.research_contract import ResearchRunContext
from intelligence.services.research_tool_registry import (
    ResearchToolRegistry,
    ToolObservation,
)


_MAX_REQUEST_BYTES = 65_536
_WRAPPER_NAME = "finance-tool"


@dataclass(frozen=True)
class HeadlessGatewaySnapshot:
    evidence: tuple[AgentEvidence, ...]
    traces: tuple[ProviderTrace, ...]
    events: tuple[EpisodeEvent, ...]
    gaps: tuple[str, ...]
    executed_count: int
    duplicate_queries: int

    def to_dict(self) -> dict[str, object]:
        return {
            "evidence": [public_agent_evidence(item) for item in self.evidence],
            "traces": [item.to_dict() for item in self.traces],
            "events": [item.to_dict() for item in self.events],
            "gaps": list(self.gaps),
            "executed_count": self.executed_count,
            "duplicate_queries": self.duplicate_queries,
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
    ) -> None:
        self._registry = registry
        self._context = context
        self._is_cancelled = is_cancelled or (lambda: False)
        self._authorized = {
            spec.name: spec
            for spec in registry.authorized_specs(
                context.contract.allowed_capabilities
            )
        }
        self._requested_run_dir = run_dir
        self._temporary_directory: tempfile.TemporaryDirectory[str] | None = None
        self._run_dir: Path | None = None
        self._wrapper_path: Path | None = None
        self._server: ThreadingHTTPServer | None = None
        self._thread: Thread | None = None
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
        return {
            "FINANCE_TOOL_GATEWAY_URL": self.endpoint,
            "FINANCE_TOOL_GATEWAY_TOKEN": self._bearer,
        }

    def call(self, tool: str, query: str, *, timeout: float = 5.0) -> dict[str, object]:
        """Use the same HTTP surface as the headless child process."""

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

    def snapshot(self) -> HeadlessGatewaySnapshot:
        with self._lock:
            return HeadlessGatewaySnapshot(
                evidence=tuple(self._evidence),
                traces=tuple(self._traces),
                events=tuple(self._events),
                gaps=tuple(self._gaps),
                executed_count=self._executed_count,
                duplicate_queries=self._duplicate_queries,
            )

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

    def _execute_tool(self, name: str, raw_query: object) -> dict[str, object]:
        with self._lock:
            request_event = self._add_event(
                "tool_request",
                {"tool": name, "query": str(raw_query or "")},
            )
            step_id = (
                f"{self._context.trace_parent_id}:headless:tool:"
                f"{request_event.sequence - 1}"
            )
            rejected = self._reservation_error(name, raw_query)
            if rejected is not None:
                self._add_event(
                    "tool_error",
                    {"tool": name, "error": rejected},
                )
                return {"status": "rejected", "tool": name, "error": rejected}
            query = cast(str, raw_query).strip()
            spec = self._authorized[name]
            normalized = query_ledger.normalize_query(query)
            self._seen_queries.add((name, normalized))
            self._executed_count += 1

        try:
            observation = self._contextvars.copy().run(
                self._registry.execute,
                name,
                query,
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
                    {"tool": name, "error": "tool_exception"},
                )
            return {"status": "error", "tool": name, "error": "tool_exception"}

        return self._publish_observation(spec.query_scope, observation)

    def _reservation_error(self, name: str, raw_query: object) -> str | None:
        if self._closed or self._is_cancelled():
            return "cancelled"
        if self._context.deadline.expired:
            return "deadline_exhausted"
        spec = self._authorized.get(name)
        if spec is None:
            return "unknown_or_unauthorized_tool"
        if not isinstance(raw_query, str) or not raw_query.strip():
            return "invalid_query"
        normalized = query_ledger.normalize_query(raw_query)
        key = (name, normalized)
        if key in self._seen_queries:
            self._duplicate_queries += 1
            return "duplicate_query"
        if (
            spec.query_scope == "episode"
            and name in self._successful_episode_tools
        ):
            return "episode_snapshot_already_collected"
        if self._executed_count >= self._context.policy.max_steps:
            return "tool_budget_exhausted"
        return None

    def _publish_observation(
        self,
        query_scope: str,
        observation: ToolObservation,
    ) -> dict[str, object]:
        with self._lock:
            if self._closed or self._is_cancelled():
                self._add_event(
                    "tool_error",
                    {"tool": observation.tool, "error": "cancelled"},
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
            }
            self._add_event("tool_result", payload)
            return payload

    def _add_event(self, kind: str, payload: dict[str, object]) -> EpisodeEvent:
        event = EpisodeEvent(self._next_sequence, kind, payload)
        self._next_sequence += 1
        self._events.append(event)
        return event

    @staticmethod
    def _write_wrapper(run_dir: Path) -> Path:
        wrapper = run_dir / _WRAPPER_NAME
        wrapper.write_text(
            """#!/usr/bin/env python3
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
with urllib.request.urlopen(request, timeout=60.0) as response:
    sys.stdout.write(response.read().decode("utf-8"))
""",
            encoding="utf-8",
        )
        wrapper.chmod(0o700)
        return wrapper


__all__ = ["HeadlessGatewaySnapshot", "HeadlessToolGateway"]
