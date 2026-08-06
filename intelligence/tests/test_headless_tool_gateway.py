from __future__ import annotations

from dataclasses import replace
from datetime import datetime
import json
import os
from pathlib import Path
import re
import stat
import subprocess
from threading import Barrier, Event, Lock, Thread
import urllib.error
import urllib.request

import pytest

from intelligence.services.agent_research import AgentEvidence, AgentToolContext
from intelligence.services.evidence_capabilities import EvidencePlan
from intelligence.runtime.headless_tool_gateway import (
    FINALIZATION_INSTRUCTION,
    HeadlessToolGateway,
)
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.research_contract import (
    InMemoryRootBudgetLedger,
    RequiredOutput,
    ResearchDeadline,
    ResearchPolicy,
    ResearchRunContext,
    ResearchTaskContract,
)
from intelligence.services.research_tool_registry import (
    EMPTY_TOOL_PARAMETERS,
    InvalidResearchToolArguments,
    ResearchToolRegistry,
    ToolSpec,
    parse_snapshot_arguments,
)


def _context(*, max_steps: int = 3) -> ResearchRunContext:
    contract = ResearchTaskContract(
        task_id="headless-gateway-test",
        question="目前市场怎么看",
        subject="A股市场",
        subject_kind="market_pattern",
        question_type="market_forecast",
        required_outputs=(
            RequiredOutput(
                "direct_assessment",
                "直接判断",
                ("market_data",),
                True,
            ),
        ),
        allowed_capabilities=("market_data", "news_search"),
        research_tier="quick",
        freshness="current",
        evidence_plan=EvidencePlan(),
        task_frame_hash="frame-hash",
    )
    return ResearchRunContext(
        contract=contract,
        deadline=ResearchDeadline.from_timeout(30.0),
        policy=ResearchPolicy("quick", max_steps, 30.0, 0.0),
        trace_parent_id="headless-gateway-test",
        today="2026-07-25",
        latest_data_date="2026-07-24",
    )


def _registry(calls: list[tuple[str, str]]) -> ResearchToolRegistry:
    def market_runner(query: str, _context: AgentToolContext):
        calls.append(("market_data", query))
        evidence = AgentEvidence(
            tool="market_data",
            title="A股市场总览",
            detail=f"{query}：上涨家数增加",
            source="本地行情",
            source_date="2026-07-24",
            evidence_tier="L4",
            content_hash="market-hash",
        )
        return (
            [evidence],
            "上涨家数增加",
            ProviderTrace(
                provider="test:market",
                capability="market_data",
                status="success",
                source_trade_date="2026-07-24",
                result_count=1,
            ),
        )

    def news_runner(query: str, _context: AgentToolContext):
        calls.append(("news_search", query))
        return (
            [],
            "没有同窗新闻",
            ProviderTrace(
                provider="test:news",
                capability="news_search",
                status="empty",
                result_count=0,
            ),
        )

    return ResearchToolRegistry(
        (
            ToolSpec(
                name="market_data",
                capability="market_data",
                description="结构化行情",
                cost="local",
                freshness="current",
                runner=market_runner,
                query_scope="episode",
            ),
            ToolSpec(
                name="news_search",
                capability="news_search",
                description="财经新闻",
                cost="external",
                freshness="current",
                runner=news_runner,
            ),
        )
    )


def _unauthorized_call(gateway: HeadlessToolGateway) -> urllib.error.HTTPError:
    request = urllib.request.Request(
        f"{gateway.endpoint}/tool/market_data",
        data=json.dumps({"query": "A股"}).encode("utf-8"),
        headers={
            "Authorization": "Bearer wrong-token",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with pytest.raises(urllib.error.HTTPError) as raised:
        urllib.request.urlopen(request, timeout=2.0)
    return raised.value


def test_gateway_executes_authorized_registry_tool() -> None:
    calls: list[tuple[str, str]] = []

    with HeadlessToolGateway(
        registry=_registry(calls),
        context=_context(),
    ) as gateway:
        result = gateway.call("market_data", "A股最近五日")
        snapshot = gateway.snapshot()

    assert result["status"] == "success"
    assert result["evidence_hashes"] == ["market-hash"]
    assert result["budget"]["remaining_tool_calls"] == 2
    assert result["budget"]["must_finalize"] is False
    assert calls == [("market_data", "A股最近五日")]
    assert snapshot.evidence[0].content_hash == "market-hash"
    assert snapshot.executed_count == 1
    assert [event.kind for event in snapshot.events] == [
        "tool_request",
        "tool_result",
    ]


def test_gateway_freezes_post_tool_budget_for_success_handoff() -> None:
    class ScriptedDeadline:
        synthesis_reserve = 30.0

        def __init__(self) -> None:
            self._remaining = iter((100.0, 100.0, 31.0, 29.0))
            self._last = 29.0

        def remaining(self) -> float:
            self._last = next(self._remaining, self._last)
            return self._last

        def stage_timeout(self, configured_limit: float) -> float:
            return float(configured_limit)

        @property
        def expired(self) -> bool:
            return self._last <= 0.0

    context = replace(_context(), deadline=ScriptedDeadline())
    with HeadlessToolGateway(
        registry=_registry([]),
        context=context,
        finalization_floor_ratio=0.0,
        transport="mailbox",
    ) as gateway:
        result = gateway.call("market_data", "市场")
        snapshot = gateway.snapshot()

    assert result["status"] == "success"
    assert result["budget"]["remaining_research_seconds"] == 31.0
    assert result["budget"]["must_finalize"] is False
    assert "instruction" not in result
    assert [event.kind for event in snapshot.events] == [
        "tool_request",
        "tool_result",
    ]


def test_gateway_records_one_effective_grant_at_request_entry() -> None:
    class FixedDeadline:
        synthesis_reserve = 30.0

        def remaining(self) -> float:
            return 70.0

        def stage_timeout(self, configured_limit: float) -> float:
            return min(float(configured_limit), 40.0)

        @property
        def expired(self) -> bool:
            return False

    context = replace(_context(), deadline=FixedDeadline())
    with HeadlessToolGateway(
        registry=_registry([]),
        context=context,
    ) as gateway:
        gateway.call("market_data", "市场")
        request = gateway.snapshot().events[0]

    assert request.kind == "tool_request"
    assert request.payload["timestamp"]
    assert request.payload["remaining_root_seconds_at_entry"] == 70.0
    assert request.payload["remaining_research_seconds_at_entry"] == 40.0
    assert request.payload["finalization_handoff_seconds"] == 30.0
    assert request.payload["transport_timeout_seconds"] == 60.0
    assert request.payload["tool_grant_seconds"] == 10.0
    assert request.payload["tool_grant_limiter"] == "handoff_window"
    datetime.fromisoformat(str(request.payload["timestamp"]).replace("Z", "+00:00"))


def test_gateway_caps_long_tool_grant_before_wrapper_timeout() -> None:
    class FixedDeadline:
        synthesis_reserve = 30.0

        def remaining(self) -> float:
            return 180.0

        def stage_timeout(self, configured_limit: float) -> float:
            return min(float(configured_limit), 150.0)

        @property
        def expired(self) -> bool:
            return False

    context = replace(_context(), deadline=FixedDeadline())
    with HeadlessToolGateway(
        registry=_registry([]),
        context=context,
    ) as gateway:
        gateway.call("market_data", "市场")
        request = gateway.snapshot().events[0]

    assert request.payload["tool_grant_seconds"] == 59.0
    assert request.payload["tool_grant_limiter"] == "transport_timeout"


def test_gateway_zero_reserve_has_no_hidden_handoff_floor() -> None:
    class FixedDeadline:
        synthesis_reserve = 0.0

        def remaining(self) -> float:
            return 40.0

        def stage_timeout(self, configured_limit: float) -> float:
            return min(float(configured_limit), 40.0)

        @property
        def expired(self) -> bool:
            return False

    context = replace(_context(), deadline=FixedDeadline())
    with HeadlessToolGateway(
        registry=_registry([]),
        context=context,
        finalization_floor_ratio=0.0,
    ) as gateway:
        gateway.call("market_data", "市场")
        request = gateway.snapshot().events[0]

    assert request.payload["finalization_handoff_seconds"] == 0.0
    assert request.payload["tool_grant_seconds"] == 40.0
    assert request.payload["tool_grant_limiter"] == "handoff_window"


def test_gateway_rejects_zero_root_calls_before_dispatch() -> None:
    calls: list[tuple[str, str]] = []
    base = _context()
    ledger = InMemoryRootBudgetLedger(
        episode_id=base.contract.task_id,
        initial_calls=0,
        hard_calls_cap=0,
        initial_seconds=30.0,
        hard_seconds_cap=30.0,
    )
    context = replace(base, root_budget=ledger)

    with HeadlessToolGateway(
        registry=_registry(calls),
        context=context,
    ) as gateway:
        rejected = gateway.call("market_data", "市场")
        snapshot = gateway.snapshot()

    assert rejected["error"] == "tool_budget_exhausted"
    assert rejected["instruction"] == FINALIZATION_INSTRUCTION
    assert rejected["budget"]["remaining_tool_calls"] == 0
    assert rejected["budget"]["must_finalize"] is True
    assert snapshot.executed_count == 0
    assert calls == []


def test_gateway_rejects_when_atomic_root_call_reservation_loses_race() -> None:
    class RejectingLedger:
        remaining_calls = 1
        remaining_seconds = 10.0

        def consume_call(self, *, seconds: float) -> None:
            assert seconds > 0.0
            self.remaining_calls = 0
            self.remaining_seconds = 0.0
            raise ValueError("simulated root reservation race")

    calls: list[tuple[str, str]] = []
    context = replace(_context(), root_budget=RejectingLedger())

    with HeadlessToolGateway(
        registry=_registry(calls),
        context=context,
        finalization_floor_ratio=0.0,
    ) as gateway:
        result = gateway.call("market_data", "市场")
        snapshot = gateway.snapshot()

    assert result["status"] == "rejected"
    assert result["error"] == "root_budget_exhausted"
    assert result["instruction"] == FINALIZATION_INSTRUCTION
    assert calls == []
    assert snapshot.executed_count == 0
    terminals = [
        event
        for event in snapshot.events
        if event.kind in {"tool_result", "tool_error"}
    ]
    assert len(terminals) == 1
    assert terminals[0].kind == "tool_error"
    assert terminals[0].payload["error"] == "root_budget_exhausted"
    transitions = [event for event in snapshot.events if event.kind == "finalization"]
    assert len(transitions) == 1
    assert transitions[0].payload["reason"] == "tool_budget_exhausted"


def test_gateway_success_events_share_one_stable_request_id() -> None:
    with HeadlessToolGateway(
        registry=_registry([]),
        context=_context(),
    ) as gateway:
        gateway.call("market_data", "市场")
        events = gateway.snapshot().events

    assert [event.kind for event in events] == ["tool_request", "tool_result"]
    request_id = events[0].payload["request_id"]
    assert re.fullmatch(r"[0-9a-f]{32}", str(request_id))
    assert events[1].payload["request_id"] == request_id


def test_gateway_rejection_events_share_one_stable_request_id() -> None:
    with HeadlessToolGateway(
        registry=_registry([]),
        context=_context(),
    ) as gateway:
        gateway.call("not_authorized", "市场")
        events = gateway.snapshot().events

    assert [event.kind for event in events] == ["tool_request", "tool_error"]
    request_id = events[0].payload["request_id"]
    assert re.fullmatch(r"[0-9a-f]{32}", str(request_id))
    assert events[1].payload["request_id"] == request_id


def test_gateway_debits_root_budget_with_real_tool_elapsed_time() -> None:
    calls: list[tuple[str, str]] = []
    base = _context()
    ledger = InMemoryRootBudgetLedger(
        episode_id=base.contract.task_id,
        initial_calls=2,
        hard_calls_cap=2,
        initial_seconds=10.0,
        hard_seconds_cap=10.0,
    )
    context = replace(base, root_budget=ledger)

    with HeadlessToolGateway(
        registry=_registry(calls),
        context=context,
    ) as gateway:
        result = gateway.call("market_data", "市场")

    assert result["status"] == "success"
    assert ledger.remaining_calls == 1
    assert 0.0 < ledger.remaining_seconds < 10.0


def test_gateway_settles_concurrent_seconds_without_losing_a_debit() -> None:
    """Two settlements racing for the last of the budget must both be accounted for.

    The pre-fix code read ``remaining_seconds`` and then called
    ``consume_seconds`` in two steps, so the loser of the race raised
    ``ValueError`` and was swallowed by a bare ``except`` -- the seconds were
    never debited and the overdraft never surfaced.
    """

    base = _context()
    ledger = InMemoryRootBudgetLedger(
        episode_id=base.contract.task_id,
        initial_calls=2,
        hard_calls_cap=2,
        initial_seconds=1.0,
        hard_seconds_cap=1.0,
    )
    context = replace(base, root_budget=ledger)
    # Each runner claims nearly the whole budget, so exactly one can be paid in
    # full and the other must be clamped.
    requested_each = 0.9
    start = Barrier(2, timeout=10.0)
    errors: list[BaseException] = []

    with HeadlessToolGateway(registry=_registry([]), context=context) as gateway:
        def settle(request_id: str) -> None:
            try:
                start.wait()
                gateway._settle_root_seconds(requested_each, request_id=request_id)
            except BaseException as exc:  # pragma: no cover - surfaced via assert
                errors.append(exc)

        threads = [Thread(target=settle, args=(f"req-{i}",)) for i in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=15.0)
            assert not thread.is_alive()
        snapshot = gateway.snapshot()

    assert errors == []
    # Invariant: the ledger can never pay out more than it started with.
    total_settled = ledger.initial_seconds - ledger.remaining_seconds
    assert total_settled <= ledger.initial_seconds + 1e-9
    assert ledger.remaining_seconds == pytest.approx(0.0, abs=1e-9)

    overdrafts = [
        event for event in snapshot.events if event.kind == "root_budget_overdraft"
    ]
    # The clamped settlement must be visible, not silently dropped.
    assert len(overdrafts) == 1
    payload = overdrafts[0].payload
    assert payload["requested_seconds"] == pytest.approx(requested_each)
    assert float(payload["overdraft_seconds"]) > 0.0
    # Nothing may fail silently: no settlement-failure telemetry either.
    assert not any(
        event.payload.get("settlement_failed") for event in overdrafts
    )
    # Both settlements together account for the full initial budget.
    assert float(payload["settled_seconds"]) + requested_each == pytest.approx(
        ledger.initial_seconds
    )


@pytest.mark.parametrize("transport", ("http", "mailbox"))
def test_gateway_reserves_one_root_call_before_concurrent_dispatch(
    transport: str,
) -> None:
    runner_entered = Event()
    release_runner = Event()
    runner_lock = Lock()
    runner_calls: list[str] = []

    def blocking_runner(query: str, _context: AgentToolContext):
        with runner_lock:
            runner_calls.append(query)
            is_first = len(runner_calls) == 1
        if is_first:
            runner_entered.set()
            assert release_runner.wait(timeout=10.0)
        return (
            [],
            "没有同窗新闻",
            ProviderTrace(
                provider="test:news",
                capability="news_search",
                status="empty",
                result_count=0,
            ),
        )

    registry = ResearchToolRegistry(
        (
            ToolSpec(
                name="news_search",
                capability="news_search",
                description="财经新闻",
                cost="external",
                freshness="current",
                runner=blocking_runner,
            ),
        )
    )
    base = _context()
    ledger = InMemoryRootBudgetLedger(
        episode_id=base.contract.task_id,
        initial_calls=1,
        hard_calls_cap=1,
        initial_seconds=10.0,
        hard_seconds_cap=10.0,
    )
    context = replace(base, root_budget=ledger)
    first_results: list[dict[str, object]] = []
    first_errors: list[BaseException] = []

    with HeadlessToolGateway(
        registry=registry,
        context=context,
        transport=transport,
        finalization_floor_ratio=0.0,
    ) as gateway:
        def call_first() -> None:
            try:
                first_results.append(
                    gateway.call("news_search", "第一次查询", timeout=15.0)
                )
            except BaseException as exc:
                first_errors.append(exc)

        first = Thread(target=call_first)
        first.start()
        assert runner_entered.wait(timeout=5.0)
        try:
            second = gateway.call("news_search", "第二次查询", timeout=15.0)
        finally:
            release_runner.set()
        first.join(timeout=15.0)
        assert not first.is_alive()
        snapshot = gateway.snapshot()

    assert first_errors == []
    assert first_results[0]["status"] == "empty"
    assert second["status"] == "rejected"
    assert second["error"] == "tool_budget_exhausted"
    assert second["instruction"] == FINALIZATION_INSTRUCTION
    assert runner_calls == ["第一次查询"]
    assert ledger.remaining_calls == 0

    second_request = next(
        event
        for event in snapshot.events
        if event.kind == "tool_request" and event.payload["query"] == "第二次查询"
    )
    second_terminals = [
        event
        for event in snapshot.events
        if event.kind in {"tool_result", "tool_error"}
        and event.payload.get("request_id") == second_request.payload["request_id"]
    ]
    assert len(second_terminals) == 1
    assert second_terminals[0].kind == "tool_error"
    assert second_terminals[0].payload["error"] == "tool_budget_exhausted"
    transitions = [event for event in snapshot.events if event.kind == "finalization"]
    assert len(transitions) == 1
    assert transitions[0].payload["reason"] == "tool_budget_exhausted"


def test_gateway_rejects_duplicate_query_without_second_execution() -> None:
    calls: list[tuple[str, str]] = []

    with HeadlessToolGateway(
        registry=_registry(calls),
        context=_context(max_steps=3),
    ) as gateway:
        gateway.call("news_search", "A股 本周 新闻")
        duplicate = gateway.call("news_search", "  a股   本周 新闻  ")
        snapshot = gateway.snapshot()

    assert duplicate["status"] == "rejected"
    assert duplicate["error"] == "duplicate_query"
    assert calls == [("news_search", "A股 本周 新闻")]
    assert snapshot.executed_count == 1
    assert snapshot.duplicate_queries == 1


def test_gateway_rejects_after_finance_tool_budget() -> None:
    calls: list[tuple[str, str]] = []

    with HeadlessToolGateway(
        registry=_registry(calls),
        context=_context(max_steps=1),
    ) as gateway:
        result = gateway.call("market_data", "市场")
        rejected = gateway.call("news_search", "市场新闻")

    assert result["instruction"] == FINALIZATION_INSTRUCTION
    assert rejected["status"] == "rejected"
    assert rejected["error"] == "research_stage_closed"
    assert rejected["instruction"] == FINALIZATION_INSTRUCTION
    assert calls == [("market_data", "市场")]


def test_gateway_rejects_second_successful_episode_snapshot() -> None:
    calls: list[tuple[str, str]] = []

    with HeadlessToolGateway(
        registry=_registry(calls),
        context=_context(max_steps=3),
    ) as gateway:
        gateway.call("market_data", "市场近五日")
        rejected = gateway.call("market_data", "市场近十日")

    assert rejected["error"] == "episode_snapshot_already_collected"
    assert calls == [("market_data", "市场近五日")]


def test_gateway_rejects_before_tool_when_deadline_is_closed() -> None:
    calls: list[tuple[str, str]] = []
    context = replace(_context(), deadline=ResearchDeadline.from_timeout(0.0))

    with HeadlessToolGateway(
        registry=_registry(calls),
        context=context,
    ) as gateway:
        rejected = gateway.call("market_data", "市场")
        snapshot = gateway.snapshot()

    assert rejected["error"] == "research_stage_closed"
    assert rejected["instruction"] == FINALIZATION_INSTRUCTION
    assert rejected["budget"]["must_finalize"] is True
    assert snapshot.executed_count == 0
    assert calls == []


def _failing_tool_registry() -> ResearchToolRegistry:
    def failing_runner(_query: str, _context: AgentToolContext):
        raise RuntimeError("PRIVATE_TOOL_EXCEPTION_SENTINEL")

    return ResearchToolRegistry(
        (
            ToolSpec(
                name="market_data",
                capability="market_data",
                description="结构化行情",
                cost="local",
                freshness="current",
                runner=failing_runner,
            ),
        )
    )


def test_gateway_charges_root_budget_for_tool_exception() -> None:
    base = _context()
    ledger = InMemoryRootBudgetLedger(
        episode_id=base.contract.task_id,
        initial_calls=1,
        hard_calls_cap=1,
        initial_seconds=10.0,
        hard_seconds_cap=10.0,
    )
    context = replace(base, root_budget=ledger)

    with HeadlessToolGateway(
        registry=_failing_tool_registry(),
        context=context,
    ) as gateway:
        result = gateway.call("market_data", "市场")

    assert result == {
        "status": "error",
        "tool": "market_data",
        "error": "tool_exception",
    }
    assert ledger.remaining_calls == 0


def test_gateway_redacts_tool_exception_detail() -> None:
    with HeadlessToolGateway(
        registry=_failing_tool_registry(),
        context=_context(),
    ) as gateway:
        gateway.call("market_data", "市场")
        snapshot = gateway.snapshot()

    assert "PRIVATE_TOOL_EXCEPTION_SENTINEL" not in str(snapshot.to_dict())


def test_gateway_requires_ephemeral_bearer_and_never_writes_it_to_wrapper() -> None:
    calls: list[tuple[str, str]] = []

    with HeadlessToolGateway(
        registry=_registry(calls),
        context=_context(),
    ) as gateway:
        error = _unauthorized_call(gateway)
        wrapper_text = Path(gateway.wrapper_path).read_text(encoding="utf-8")
        environment = gateway.subprocess_environment()
        snapshot_text = json.dumps(
            gateway.snapshot().to_dict(),
            ensure_ascii=False,
        )

        assert error.code == 401
        assert environment["FINANCE_TOOL_GATEWAY_TOKEN"] not in wrapper_text
        assert environment["FINANCE_TOOL_GATEWAY_TOKEN"] not in snapshot_text
        assert "FINANCE_TOOL_GATEWAY_TOKEN" in wrapper_text
        assert gateway.endpoint.startswith("http://127.0.0.1:")


def test_mailbox_gateway_executes_without_network_or_bearer() -> None:
    calls: list[tuple[str, str]] = []

    with HeadlessToolGateway(
        registry=_registry(calls),
        context=_context(),
        transport="mailbox",
    ) as gateway:
        environment = {**os.environ, **gateway.subprocess_environment()}
        completed = subprocess.run(
            [str(gateway.wrapper_path), "market_data", "A股最近五日"],
            env=environment,
            check=True,
            capture_output=True,
            text=True,
            timeout=5.0,
        )
        result = json.loads(completed.stdout)
        snapshot = gateway.snapshot()
        wrapper = gateway.wrapper_path.read_text(encoding="utf-8")

    assert result["status"] == "success"
    assert result["evidence_hashes"] == ["market-hash"]
    assert calls == [("market_data", "A股最近五日")]
    assert snapshot.executed_count == 1
    assert len(snapshot.mailbox_exchanges) == 1
    exchange = snapshot.mailbox_exchanges[0]
    assert len(exchange.request_sha256) == 64
    assert len(exchange.response_sha256) == 64
    request_id = exchange.request_id.removesuffix(".json")
    tool_events = [
        event for event in snapshot.events if event.kind.startswith("tool_")
    ]
    assert [event.payload["request_id"] for event in tool_events] == [
        request_id,
        request_id,
    ]
    assert set(gateway.subprocess_environment()) == {"FINANCE_TOOL_MAILBOX"}
    assert "urllib" not in wrapper
    assert "FINANCE_TOOL_GATEWAY_TOKEN" not in wrapper
    assert "os.O_EXCL" in wrapper
    assert "os.O_NOFOLLOW" in wrapper


def test_generated_wrappers_share_one_transport_timeout(tmp_path: Path) -> None:
    with HeadlessToolGateway(
        registry=_registry([]),
        context=_context(),
        run_dir=tmp_path / "mailbox",
        transport="mailbox",
    ) as gateway:
        mailbox_source = gateway.wrapper_path.read_text(encoding="utf-8")

    with HeadlessToolGateway(
        registry=_registry([]),
        context=_context(),
        run_dir=tmp_path / "http",
    ) as gateway:
        http_source = gateway.wrapper_path.read_text(encoding="utf-8")

    assert "deadline = time.monotonic() + 60.0" in mailbox_source
    assert "urlopen(request, timeout=60.0)" in http_source


def test_mailbox_directories_are_private_and_owned() -> None:
    calls: list[tuple[str, str]] = []

    with HeadlessToolGateway(
        registry=_registry(calls),
        context=_context(),
        transport="mailbox",
    ) as gateway:
        mailbox = Path(gateway.subprocess_environment()["FINANCE_TOOL_MAILBOX"])
        for path in (mailbox, mailbox / "requests", mailbox / "responses"):
            metadata = path.lstat()
            assert stat.S_ISDIR(metadata.st_mode)
            assert stat.S_IMODE(metadata.st_mode) == 0o700
            assert metadata.st_uid == os.getuid()


def test_mailbox_gateway_rejects_symlink_root(tmp_path: Path) -> None:
    target = tmp_path / "outside"
    target.mkdir()
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / ".finance-tool-mailbox").symlink_to(
        target,
        target_is_directory=True,
    )

    gateway = HeadlessToolGateway(
        registry=_registry([]),
        context=_context(),
        run_dir=run_dir,
        transport="mailbox",
    )
    with pytest.raises(ValueError, match="mailbox directory must not be a symlink"):
        gateway.start()


def test_mailbox_gateway_rejects_wrong_owner(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    monkeypatch.setattr(os, "getuid", lambda: 2**31 - 1)

    gateway = HeadlessToolGateway(
        registry=_registry([]),
        context=_context(),
        run_dir=run_dir,
        transport="mailbox",
    )
    with pytest.raises(ValueError, match="mailbox directory owner mismatch"):
        gateway.start()


def test_mailbox_response_creation_never_overwrites_existing_path(
    tmp_path: Path,
) -> None:
    response = tmp_path / ("a" * 32 + ".json")
    response.write_text("attacker", encoding="utf-8")

    with pytest.raises(FileExistsError):
        HeadlessToolGateway._write_mailbox_response(
            response,
            {"status": "success"},
            request_sha256="b" * 64,
        )

    assert response.read_text(encoding="utf-8") == "attacker"


def test_mailbox_rejects_oversized_request(tmp_path: Path) -> None:
    request = tmp_path / ("a" * 32 + ".json")
    request.write_bytes(b"x" * 65_537)

    with pytest.raises(ValueError, match="request size is invalid"):
        HeadlessToolGateway._read_mailbox_request(request)


def test_gateway_closes_research_stage_before_finalization_budget() -> None:
    calls: list[tuple[str, str]] = []
    base = _context(max_steps=3)
    context = replace(
        base,
        deadline=ResearchDeadline.from_timeout(5.0),
        policy=ResearchPolicy("quick", 3, 5.0, 0.0),
    )

    with HeadlessToolGateway(
        registry=_registry(calls),
        context=context,
    ) as gateway:
        first = gateway.call("market_data", "市场")
        rejected = gateway.call("news_search", "再查一次")
        snapshot = gateway.snapshot()

    assert first["status"] == "success"
    assert first["budget"]["must_finalize"] is True
    assert rejected["error"] == "research_stage_closed"
    assert rejected["budget"]["must_finalize"] is True
    assert snapshot.executed_count == 1
    assert calls == [("market_data", "市场")]


def test_gateway_records_one_timestamped_finalization_transition() -> None:
    calls: list[tuple[str, str]] = []
    base = _context(max_steps=3)
    context = replace(
        base,
        deadline=ResearchDeadline.from_timeout(5.0),
        policy=ResearchPolicy("quick", 3, 5.0, 0.0),
    )

    with HeadlessToolGateway(
        registry=_registry(calls),
        context=context,
    ) as gateway:
        gateway.call("market_data", "市场")
        first_rejection = gateway.call("news_search", "第一次补查")
        second_rejection = gateway.call("news_search", "第二次补查")
        snapshot = gateway.snapshot()

    transitions = [
        event for event in snapshot.events if event.kind == "finalization"
    ]
    assert first_rejection["error"] == "research_stage_closed"
    assert second_rejection["error"] == "research_stage_closed"
    assert len(transitions) == 1
    assert transitions[0].payload["reason"] == "research_stage_closed"
    assert float(transitions[0].payload["remaining_seconds"]) >= 0.0
    datetime.fromisoformat(str(transitions[0].payload["timestamp"]).replace("Z", "+00:00"))


def test_gateway_rejects_at_visible_handoff_window() -> None:
    class MutableDeadline:
        synthesis_reserve = 30.0

        def __init__(self) -> None:
            self.seconds = 180.0

        def remaining(self) -> float:
            return self.seconds

        def stage_timeout(self, configured_limit: float) -> float:
            return min(
                float(configured_limit),
                max(0.0, self.seconds - self.synthesis_reserve),
            )

        @property
        def expired(self) -> bool:
            return self.seconds <= 0.0

    deadline = MutableDeadline()
    context = replace(_context(max_steps=3), deadline=deadline)
    with HeadlessToolGateway(
        registry=_registry(calls := []),
        context=context,
        finalization_floor_ratio=0.0,
    ) as gateway:
        first = gateway.call("market_data", "市场")
        deadline.seconds = 60.0
        rejected = gateway.call("news_search", "补充消息")
        snapshot = gateway.snapshot()

    assert first["status"] == "success"
    assert rejected["error"] == "research_stage_closed"
    assert rejected["instruction"] == FINALIZATION_INSTRUCTION
    assert calls == [("market_data", "市场")]
    transitions = [
        event for event in snapshot.events if event.kind == "finalization"
    ]
    assert len(transitions) == 1
    assert transitions[0].payload["reason"] == "research_stage_closed"


def test_gateway_hands_off_when_last_tool_slot_is_consumed() -> None:
    with HeadlessToolGateway(
        registry=_registry([]),
        context=_context(max_steps=1),
        finalization_floor_ratio=0.0,
    ) as gateway:
        result = gateway.call("market_data", "市场")
        rejected = gateway.call("news_search", "继续补查")
        snapshot = gateway.snapshot()

    assert result["instruction"] == FINALIZATION_INSTRUCTION
    assert rejected["error"] == "research_stage_closed"
    assert rejected["instruction"] == FINALIZATION_INSTRUCTION
    transitions = [
        event for event in snapshot.events if event.kind == "finalization"
    ]
    assert len(transitions) == 1
    assert transitions[0].payload["reason"] == "tool_budget_exhausted"


def test_gateway_floor_ratio_can_be_disabled_without_changing_default() -> None:
    class MutableDeadline:
        synthesis_reserve = 0.0

        def __init__(self) -> None:
            self.seconds = 30.0

        def remaining(self) -> float:
            return self.seconds

        def stage_timeout(self, configured_limit: float) -> float:
            return min(float(configured_limit), self.seconds)

        @property
        def expired(self) -> bool:
            return self.seconds <= 0.0

    default_calls: list[tuple[str, str]] = []
    default_deadline = MutableDeadline()
    default_context = replace(_context(), deadline=default_deadline)
    with HeadlessToolGateway(
        registry=_registry(default_calls),
        context=default_context,
    ) as gateway:
        gateway.call("market_data", "市场")
        default_deadline.seconds = 10.0
        default_result = gateway.call("news_search", "再查一次")

    ablated_calls: list[tuple[str, str]] = []
    ablated_deadline = MutableDeadline()
    ablated_context = replace(_context(), deadline=ablated_deadline)
    with HeadlessToolGateway(
        registry=_registry(ablated_calls),
        context=ablated_context,
        finalization_floor_ratio=0.0,
    ) as gateway:
        gateway.call("market_data", "市场")
        ablated_deadline.seconds = 10.0
        ablated_result = gateway.call("news_search", "再查一次")

    assert default_result["error"] == "research_stage_closed"
    assert default_calls == [("market_data", "市场")]
    assert ablated_result["status"] == "empty"
    assert ablated_calls == [
        ("market_data", "市场"),
        ("news_search", "再查一次"),
    ]


def test_gateway_adapts_model_query_to_snapshot_arguments() -> None:
    runner_inputs: list[str] = []

    def snapshot_runner(value: str, _context: AgentToolContext):
        runner_inputs.append(value)
        return (
            [
                AgentEvidence(
                    tool="market_data",
                    title="A股市场快照",
                    detail="截至2026-07-24，上证收盘数据可用。",
                    source="本地行情",
                    source_date="2026-07-24",
                    content_hash="snapshot-hash",
                )
            ],
            "A股市场快照可用",
            ProviderTrace(
                provider="test:snapshot",
                capability="market_data",
                status="success",
                result_count=1,
            ),
        )

    registry = ResearchToolRegistry(
        (
            ToolSpec(
                name="market_data",
                capability="market_data",
                description="完整市场快照",
                cost="local",
                freshness="current",
                runner=snapshot_runner,
                query_scope="episode",
                parameters=EMPTY_TOOL_PARAMETERS,
                parse_arguments=parse_snapshot_arguments,
            ),
        )
    )

    with HeadlessToolGateway(registry=registry, context=_context()) as gateway:
        result = gateway.call(
            "market_data",
            "请返回最近五日指数、成交额和市场宽度",
        )
        second = gateway.call("market_data", "换一个措辞再查一次")

    assert result["status"] == "success"
    assert result["query"] == "snapshot"
    assert runner_inputs == [""]
    assert second["error"] == "episode_snapshot_already_collected"


def test_gateway_decodes_structured_json_without_charging_invalid_attempt() -> None:
    runner_inputs: list[dict[str, object]] = []

    def parse_arguments(arguments):
        if set(arguments) != {"dataset"}:
            raise InvalidResearchToolArguments("dataset is required")
        return dict(arguments), str(arguments["dataset"])

    def runner(value: dict[str, object], _context: AgentToolContext):
        runner_inputs.append(value)
        return (
            [
                AgentEvidence(
                    tool="finance_query",
                    title="市场日线查询",
                    detail="market_daily 返回一行数据。",
                    source="本地行情",
                    source_date="2026-07-24",
                    content_hash="finance-query-hash",
                )
            ],
            "market_daily 返回一行数据",
            ProviderTrace(
                provider="test:finance-query",
                capability="finance_query",
                status="success",
                result_count=1,
            ),
        )

    registry = ResearchToolRegistry(
        (
            ToolSpec(
                name="finance_query",
                capability="finance_query",
                description="语义金融查询",
                cost="local",
                freshness="current",
                runner=runner,
                parameters={
                    "type": "object",
                    "properties": {"dataset": {"type": "string"}},
                    "required": ["dataset"],
                    "additionalProperties": False,
                },
                parse_arguments=parse_arguments,
            ),
        )
    )
    context = replace(
        _context(),
        contract=replace(
            _context().contract,
            allowed_capabilities=("finance_query",),
        ),
    )

    with HeadlessToolGateway(registry=registry, context=context) as gateway:
        invalid = gateway.call("finance_query", "dataset=market_daily")
        valid = gateway.call(
            "finance_query",
            '{"dataset":"market_daily"}',
        )
        snapshot = gateway.snapshot()

    assert invalid["error"] == "invalid_arguments"
    assert invalid["retryable"] is True
    assert invalid["expected_parameters"]["required"] == ["dataset"]
    assert invalid["expected_parameters"]["properties"]["dataset"]["type"] == "string"
    assert invalid["budget"]["remaining_tool_calls"] == 3
    assert valid["status"] == "success"
    assert runner_inputs == [{"dataset": "market_daily"}]
    assert snapshot.executed_count == 1
