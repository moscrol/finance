# Headless In-Flight Tool Handoff Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 Codex headless 在只读工具卡住时先于 60 秒 wrapper 墙返回一次可配对的收口指令，并隔离工具线程的迟到 evidence、trace、query-ledger 与第二终态。

**Architecture:** `HeadlessToolGateway` 在 request 入场时从 deadline、root ledger、显式 synthesis reserve 和共享 transport 常量冻结唯一 grant；只读工具在携带 `QueryPublishGuard` 的 daemon worker 中执行，gateway 线程按 absolute cutoff 等待并拥有唯一发布权。超时路径先撤销发布权，再记一次 root call、写一个执行层 error 和一个幂等 finalization；正常路径保持现有 wrapper JSON schema。

**Tech Stack:** Python 3.12、stdlib `Future`/`Thread`/`ContextVar`、现有 `QueryPublishGuard`、pytest、Codex mailbox/HTTP wrapper、runtime benchmark normalizer。

---

## File map

- `intelligence/services/headless_tool_gateway.py`：唯一生产改动点；负责 grant、admission、watchdog、root 计费、执行终态和两种 wrapper 的 60 秒共享常量。
- `intelligence/tests/test_headless_tool_gateway.py`：主结构门；覆盖 grant 数学、root ledger、slow worker、迟到发布隔离、外部取消和 transport conflict。
- `intelligence/tests/test_codex_headless_runtime.py`：用 fake Codex process 真实执行生成的 mailbox wrapper，证明模型能在同一 command 收到 instruction 后 `model_finish`。
- `intelligence/tests/test_normalize_harness_trace.py`：锁定 handoff error 可配对，且 mailbox `response_path_conflict` 不被误当第二个执行终态。
- `docs/verification/2026-08-04c-headless-inflight-handoff.md`：记录离线结构门与唯一 live canary 的可证伪结论。
- `docs/prediction-ledger.md`、`docs/trace-profile.md`、`docs/handoffs/2026-08-04b-finalization-handoff.md`：按预注册分支更新 R-10、字段语义和下一层。
- `intelligence/eval/measurements/2026-08-04c-inflight-handoff/`：只保存一次 `ruihuatai-valuation` 的 raw/normalized canary 产物。

### Task 1: 冻结唯一预算视图与 transport-safe grant

**Files:**
- Modify: `intelligence/services/headless_tool_gateway.py:39-54,132-196,498-536,584-682,761-869,877-998`
- Modify: `intelligence/tests/test_headless_tool_gateway.py:16-30,169-194,266-309,484-645`

- [ ] **Step 1: 扩充 request telemetry 的 RED 测试**

把现有 `test_gateway_records_timestamp_and_two_budget_clocks_at_request_entry` 扩成同一快照断言。`FixedDeadline` 给 root=70、research=40、显式 reserve=30，所以 grant 必须是 10 秒，limiter 必须来自 handoff window：

```python
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
    assert request.payload["remaining_root_seconds_at_entry"] == 70.0
    assert request.payload["remaining_research_seconds_at_entry"] == 40.0
    assert request.payload["finalization_handoff_seconds"] == 30.0
    assert request.payload["transport_timeout_seconds"] == 60.0
    assert request.payload["tool_grant_seconds"] == 10.0
    assert request.payload["tool_grant_limiter"] == "handoff_window"
    datetime.fromisoformat(str(request.payload["timestamp"]).replace("Z", "+00:00"))
```

- [ ] **Step 2: 增加长窗口、reserve=0、root calls=0 与 wrapper 常量 RED 测试**

```python
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
    with HeadlessToolGateway(registry=_registry([]), context=context) as gateway:
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


def test_gateway_rejects_zero_root_calls_before_dispatch() -> None:
    calls: list[tuple[str, str]] = []
    base = _context(max_steps=3)
    ledger = InMemoryRootBudgetLedger(
        episode_id=base.contract.task_id,
        initial_calls=0,
        hard_calls_cap=0,
        initial_seconds=30.0,
        hard_seconds_cap=30.0,
    )
    context = replace(base, root_budget=ledger)

    with HeadlessToolGateway(registry=_registry(calls), context=context) as gateway:
        result = gateway.call("market_data", "市场")
        snapshot = gateway.snapshot()

    assert result["error"] == "tool_budget_exhausted"
    assert result["instruction"] == FINALIZATION_INSTRUCTION
    assert result["budget"]["remaining_tool_calls"] == 0
    assert result["budget"]["must_finalize"] is True
    assert snapshot.executed_count == 0
    assert calls == []


def test_generated_wrappers_share_one_transport_timeout(tmp_path: Path) -> None:
    mailbox_dir = tmp_path / "mailbox"
    http_dir = tmp_path / "http"
    with HeadlessToolGateway(
        registry=_registry([]),
        context=_context(),
        run_dir=mailbox_dir,
        transport="mailbox",
    ) as mailbox:
        mailbox_source = mailbox.wrapper_path.read_text(encoding="utf-8")
    with HeadlessToolGateway(
        registry=_registry([]),
        context=_context(),
        run_dir=http_dir,
        transport="http",
    ) as http:
        http_source = http.wrapper_path.read_text(encoding="utf-8")

    assert "deadline = time.monotonic() + 60.0" in mailbox_source
    assert "urlopen(request, timeout=60.0)" in http_source
```

- [ ] **Step 3: 运行 RED**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_headless_tool_gateway.py::test_gateway_records_one_effective_grant_at_request_entry \
  intelligence/tests/test_headless_tool_gateway.py::test_gateway_caps_long_tool_grant_before_wrapper_timeout \
  intelligence/tests/test_headless_tool_gateway.py::test_gateway_zero_reserve_has_no_hidden_handoff_floor \
  intelligence/tests/test_headless_tool_gateway.py::test_gateway_rejects_zero_root_calls_before_dispatch \
  intelligence/tests/test_headless_tool_gateway.py::test_generated_wrappers_share_one_transport_timeout
```

Expected: 前三项缺 grant 字段；root ledger 为 0 的调用仍会错误 dispatch；wrapper timeout 尚有两份 literal authority。

- [ ] **Step 4: 加入冻结预算值类型与共享常量**

在 gateway 模块常量区新增：

```python
TOOL_TRANSPORT_TIMEOUT_SECONDS = 60.0
TOOL_RESPONSE_PUBLISH_MARGIN_SECONDS = 1.0


@dataclass(frozen=True)
class _EffectiveBudget:
    remaining_calls: int
    remaining_root_seconds: float
    remaining_research_seconds: float


@dataclass(frozen=True)
class _ToolGrant:
    seconds: float
    limiter: str
```

构造函数只从 enforcement point 的显式 reserve 派生 handoff；保留原 floor 公式不动：

```python
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
```

新增两个只读 helper；ledger 只钳制可执行 research 秒数，不改 deadline root clock 的观测语义：

```python
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
```

- [ ] **Step 5: 让 request、admission、finalization 与 budget payload 读取同一视图**

在 `_execute_tool()` 的锁内先算后写：

```python
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
            budget.remaining_root_seconds, 3
        ),
        "remaining_research_seconds_at_entry": round(
            budget.remaining_research_seconds, 3
        ),
        "finalization_handoff_seconds": round(
            self._finalization_handoff_seconds, 3
        ),
        "transport_timeout_seconds": TOOL_TRANSPORT_TIMEOUT_SECONDS,
        "tool_grant_seconds": round(grant.seconds, 3),
        "tool_grant_limiter": grant.limiter,
    },
)
```

把 `_reservation_error()` 替换为：

```python
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
        and budget.remaining_research_seconds <= self._finalization_floor_seconds
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
```

调用处传入冻结值：

```python
rejected = self._reservation_error(
    spec,
    prepared,
    budget=budget,
    grant=grant,
)
```

`_pending_finalization_reason()` 与 `_budget_payload()` 接收可选 view，未传时各自只计算一次：

```python
def _pending_finalization_reason(
    self,
    budget: _EffectiveBudget | None = None,
) -> str | None:
    if self._finalization_event is not None:
        return str(self._finalization_event.payload["reason"])
    effective = budget if budget is not None else self._effective_budget()
    if effective.remaining_calls <= 0:
        return "tool_budget_exhausted"
    if effective.remaining_research_seconds <= self._finalization_handoff_seconds:
        return "deadline_pressure"
    if (
        self._executed_count > 0
        and effective.remaining_research_seconds <= self._finalization_floor_seconds
    ):
        return "research_stage_closed"
    return None


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
            effective.remaining_research_seconds, 3
        ),
        "must_finalize": self._pending_finalization_reason(effective) is not None,
    }
```

对 admission rejection 先写 error/finalization，再用同一 view 生成 response budget；替换现有
`if rejected is not None` block 为：

```python
if rejected is not None:
    self._add_event(
        "tool_error",
        {
            "request_id": resolved_request_id,
            "tool": name,
            "error": rejected,
            "retryable": rejected == "invalid_arguments" and spec is not None,
        },
    )
    if rejected in {"research_stage_closed", "tool_budget_exhausted"}:
        self._begin_finalization_locked(rejected)
    rejection: dict[str, object] = {
        "status": "rejected",
        "tool": name,
        "error": rejected,
        "budget": self._budget_payload(),
    }
    if rejected == "invalid_arguments" and spec is not None:
        rejection.update(
            {
                "retryable": True,
                "expected_parameters": copy_tool_parameters(spec.parameters),
                "retry_hint": (
                    "retry this tool with one single-line JSON object "
                    "matching expected_parameters"
                ),
            }
        )
    if rejected in {"research_stage_closed", "tool_budget_exhausted"}:
        rejection["instruction"] = FINALIZATION_INSTRUCTION
    return rejection
```

这保证 root calls=0 时 `must_finalize=true`，同时保留 `invalid_arguments` 的 retry contract。

- [ ] **Step 6: 两种 wrapper 从同一常量渲染 timeout**

不要把外层模板改成 f-string，以免误展开 wrapper 自己的 `uuid` 表达式。增加一个严格只替换一次的 renderer：

```python
_TRANSPORT_TIMEOUT_TOKEN = "__TOOL_TIMEOUT__"


def _render_wrapper_timeout(source: str) -> str:
    if source.count(_TRANSPORT_TIMEOUT_TOKEN) != 1:
        raise RuntimeError("headless wrapper must contain one timeout token")
    return source.replace(
        _TRANSPORT_TIMEOUT_TOKEN,
        repr(TOOL_TRANSPORT_TIMEOUT_SECONDS),
    )
```

然后对现有两段 wrapper source 做以下精确替换，并把各自的完整 triple-quoted source 传给
`_render_wrapper_timeout()` 后再交给 `write_text()`：

```diff
-deadline = time.monotonic() + 60.0
+deadline = time.monotonic() + __TOOL_TIMEOUT__

-with urllib.request.urlopen(request, timeout=60.0) as response:
+with urllib.request.urlopen(request, timeout=__TOOL_TIMEOUT__) as response:
```

把旧的 deadline-closed 测试改成：

```python
def test_gateway_hands_off_before_tool_when_research_deadline_is_closed() -> None:
    calls: list[tuple[str, str]] = []
    context = replace(_context(), deadline=ResearchDeadline.from_timeout(0.0))

    with HeadlessToolGateway(
        registry=_registry(calls),
        context=context,
    ) as gateway:
        rejected = gateway.call("market_data", "市场")

    assert rejected["error"] == "research_stage_closed"
    assert rejected["instruction"] == FINALIZATION_INSTRUCTION
    assert rejected["budget"]["must_finalize"] is True
    assert calls == []
```

把依赖隐藏 20% reserve 的旧测试完整替换为显式 reserve admission 测试：

```python
def test_gateway_rejects_at_visible_handoff_window() -> None:
    class MutableDeadline:
        synthesis_reserve = 30.0

        def __init__(self) -> None:
            self.seconds = 150.0

        def remaining(self) -> float:
            return self.seconds

        def stage_timeout(self, configured_limit: float) -> float:
            return min(float(configured_limit), self.seconds)

        @property
        def expired(self) -> bool:
            return self.seconds <= 0.0

    calls: list[tuple[str, str]] = []
    deadline = MutableDeadline()
    context = replace(_context(max_steps=3), deadline=deadline)
    with HeadlessToolGateway(
        registry=_registry(calls),
        context=context,
        finalization_floor_ratio=0.0,
    ) as gateway:
        first = gateway.call("market_data", "市场")
        deadline.seconds = 30.0
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
```

- [ ] **Step 7: 运行 GREEN 与 gateway 全文件**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_headless_tool_gateway.py
```

Expected: 全绿；新增 4 个 test，旧 floor_ratio=0 测试证明 floor 与 handoff 仍是两条控制线。

- [ ] **Step 8: 提交预算视图片段**

```bash
git add intelligence/services/headless_tool_gateway.py \
  intelligence/tests/test_headless_tool_gateway.py
git commit -m "refactor(runtime): unify headless tool grant budget"
```

### Task 2: 让每个真实 dispatch 恰好计费一次

**Files:**
- Modify: `intelligence/services/headless_tool_gateway.py:492-515,688-759`
- Modify: `intelligence/tests/test_headless_tool_gateway.py:225-246,311-338`

- [ ] **Step 1: 把 exception 计费与 charge race 写成 RED**

给现有 exception 测试装 root ledger，并增加 race 测试：

```python
def test_gateway_charges_root_budget_for_tool_exception() -> None:
    def failing_runner(_query: str, _context: AgentToolContext):
        raise RuntimeError("PRIVATE_TOOL_EXCEPTION_SENTINEL")

    registry = ResearchToolRegistry(
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
    base = _context()
    ledger = InMemoryRootBudgetLedger(
        episode_id=base.contract.task_id,
        initial_calls=1,
        hard_calls_cap=1,
        initial_seconds=10.0,
        hard_seconds_cap=10.0,
    )
    context = replace(base, root_budget=ledger)

    with HeadlessToolGateway(registry=registry, context=context) as gateway:
        result = gateway.call("market_data", "市场")
        snapshot = gateway.snapshot()

    assert result == {
        "status": "error",
        "tool": "market_data",
        "error": "tool_exception",
    }
    assert ledger.remaining_calls == 0
    assert "PRIVATE_TOOL_EXCEPTION_SENTINEL" not in str(snapshot.to_dict())


def test_gateway_root_charge_race_emits_one_execution_terminal() -> None:
    class RejectingLedger:
        remaining_calls = 1
        remaining_seconds = 10.0

        def consume_call(self, *, seconds: float) -> None:
            assert seconds > 0.0
            self.remaining_calls = 0
            self.remaining_seconds = 0.0
            raise ValueError("simulated root charge race")

    context = replace(_context(), root_budget=RejectingLedger())
    with HeadlessToolGateway(registry=_registry([]), context=context) as gateway:
        result = gateway.call("market_data", "市场")
        events = gateway.snapshot().events

    terminals = [
        event
        for event in events
        if event.kind in {"tool_result", "tool_error"}
    ]
    assert result["error"] == "root_budget_exhausted"
    assert result["instruction"] == FINALIZATION_INSTRUCTION
    assert len(terminals) == 1
    assert terminals[0].kind == "tool_error"
    assert terminals[0].payload["error"] == "root_budget_exhausted"
    transitions = [event for event in events if event.kind == "finalization"]
    assert len(transitions) == 1
    assert transitions[0].payload["reason"] == "tool_budget_exhausted"
```

- [ ] **Step 2: 运行 RED**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_headless_tool_gateway.py::test_gateway_charges_root_budget_for_tool_exception \
  intelligence/tests/test_headless_tool_gateway.py::test_gateway_root_charge_race_emits_one_execution_terminal
```

Expected: exception 未扣 root call；race 会由 `_charge_root_budget()` 自己写 error，使调用路径难以保证唯一终态与 instruction。

- [ ] **Step 3: 把 charge helper 改成无 event 的结果函数**

```python
def _charge_root_budget(self, elapsed_seconds: float) -> bool:
    ledger = getattr(self._context, "root_budget", None)
    consume_call = getattr(ledger, "consume_call", None)
    if not callable(consume_call):
        return True
    try:
        consume_call(seconds=max(0.001, float(elapsed_seconds)))
    except (TypeError, ValueError):
        return False
    return True
```

新增唯一 root rejection 构造器；finalization 可以带触发 request id，但不改 wrapper response schema：

```python
def _root_budget_rejection(
    self,
    *,
    request_id: str,
    tool: str,
) -> dict[str, object]:
    with self._lock:
        self._add_event(
            "tool_error",
            {
                "request_id": request_id,
                "tool": tool,
                "error": "root_budget_exhausted",
            },
        )
        self._begin_finalization_locked(
            "tool_budget_exhausted",
            request_id=request_id,
        )
        return {
            "status": "rejected",
            "tool": tool,
            "error": "root_budget_exhausted",
            "instruction": FINALIZATION_INSTRUCTION,
            "budget": self._budget_payload(),
        }
```

扩展 finalization 的可选 correlation，不影响既有调用：

```python
def _begin_finalization_locked(
    self,
    reason: str,
    *,
    request_id: str | None = None,
) -> EpisodeEvent:
    if reason not in _FINALIZATION_REASONS:
        raise ValueError("unsupported headless finalization reason")
    if self._finalization_event is not None:
        return self._finalization_event
    budget = self._effective_budget()
    payload: dict[str, object] = {
        "reason": reason,
        "remaining_seconds": round(budget.remaining_research_seconds, 3),
        "timestamp": _utc_timestamp(),
    }
    if request_id is not None:
        payload["request_id"] = request_id
    event = self._add_event("finalization", payload)
    self._finalization_event = event
    return event
```

- [ ] **Step 4: 所有 dispatch 终态先计费、再选择唯一 event**

把 `started_at` 放到执行前。正常 observation、empty、tool exception 都调用一次 `_charge_root_budget()`；失败时只走 `_root_budget_rejection()`，不先写 result/exception error：

```python
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
    elapsed_seconds = time.monotonic() - started_at
    if not self._charge_root_budget(elapsed_seconds):
        return self._root_budget_rejection(
            request_id=resolved_request_id,
            tool=name,
        )
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
    return {"status": "error", "tool": name, "error": "tool_exception"}

if not self._charge_root_budget(time.monotonic() - started_at):
    return self._root_budget_rejection(
        request_id=resolved_request_id,
        tool=name,
    )
return self._publish_observation(
    spec.query_scope,
    observation,
    request_id=resolved_request_id,
)
```

- [ ] **Step 5: 运行 GREEN 与计费回归**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_headless_tool_gateway.py
```

Expected: 全绿；invalid/duplicate/admission rejection 仍为 0 call，正常/empty/exception 为 1 call，同 id 只有一个执行层终态。

- [ ] **Step 6: 提交计费片段**

```bash
git add intelligence/services/headless_tool_gateway.py \
  intelligence/tests/test_headless_tool_gateway.py
git commit -m "fix(runtime): align headless root budget accounting"
```

### Task 3: 加入 watchdog、迟到发布隔离和真实 wrapper 门

**Files:**
- Modify: `intelligence/services/headless_tool_gateway.py:5-36,46-54,132-196,584-849`
- Modify: `intelligence/tests/test_headless_tool_gateway.py`
- Modify: `intelligence/tests/test_codex_headless_runtime.py:1-40,247-335`
- Modify: `intelligence/tests/test_normalize_harness_trace.py:284-458`

- [ ] **Step 1: 增加 fake clock/barrier 的主 RED 测试**

测试 import 增加：

```python
from concurrent.futures import Future, TimeoutError as FutureTimeoutError
from threading import Event

from intelligence.eval.normalize_harness_trace import main as normalize_trace
from intelligence.services import query_ledger
```

增加确定性时钟和 slow registry；runner 内部再写一层 QueryLedger，证明迟到 cache publication 也被撤销：

```python
class _FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += max(0.0, float(seconds))


class _ClockDeadline:
    def __init__(
        self,
        clock: _FakeClock,
        *,
        total_seconds: float,
        synthesis_reserve: float,
    ) -> None:
        self._clock = clock
        self._expires_at = float(total_seconds)
        self.synthesis_reserve = float(synthesis_reserve)

    def remaining(self) -> float:
        return max(0.0, self._expires_at - self._clock())

    def stage_timeout(self, configured_limit: float) -> float:
        return max(
            0.0,
            min(float(configured_limit), self.remaining() - self.synthesis_reserve),
        )

    @property
    def expired(self) -> bool:
        return self.remaining() <= 0.0


def _slow_registry(
    *,
    started: Event,
    release: Event,
    finished: Event,
) -> ResearchToolRegistry:
    def runner(query: str, _context: AgentToolContext):
        def fetch() -> str:
            started.set()
            release.wait(timeout=2.0)
            return "late-result"

        detail = query_ledger.executed("nested:slow", query, fetch)
        finished.set()
        return (
            [
                AgentEvidence(
                    tool="market_data",
                    title="迟到结果",
                    detail=detail,
                    source="test",
                    source_date="2026-07-24",
                    content_hash="late-hash",
                )
            ],
            detail,
            ProviderTrace(
                provider="test:slow",
                capability="market_data",
                status="success",
                result_count=1,
            ),
        )

    return ResearchToolRegistry(
        (
            ToolSpec(
                name="market_data",
                capability="market_data",
                description="慢只读工具",
                cost="local",
                freshness="current",
                runner=runner,
            ),
        )
    )
```

主测试参数化 handoff 与 transport 两种先到的 cutoff；两组都复用同一个慢工具且都必须在
wrapper 60 秒墙以前返回：

```python
@pytest.mark.parametrize(
    ("total_seconds", "reserve_seconds", "expected_grant", "expected_limiter"),
    (
        (3.0, 1.0, 1.0, "handoff_window"),
        (180.0, 30.0, 59.0, "transport_timeout"),
    ),
)
def test_gateway_handoff_suppresses_late_tool_publication(
    tmp_path: Path,
    total_seconds: float,
    reserve_seconds: float,
    expected_grant: float,
    expected_limiter: str,
) -> None:
    clock = _FakeClock()
    started = Event()
    release = Event()
    finished = Event()
    base = _context(max_steps=2)
    ledger = InMemoryRootBudgetLedger(
        episode_id=base.contract.task_id,
        initial_calls=2,
        hard_calls_cap=2,
        initial_seconds=total_seconds,
        hard_seconds_cap=total_seconds,
    )
    context = replace(
        base,
        deadline=_ClockDeadline(
            clock,
            total_seconds=total_seconds,
            synthesis_reserve=reserve_seconds,
        ),
        policy=ResearchPolicy(
            "quick",
            2,
            total_seconds,
            reserve_seconds,
        ),
        root_budget=ledger,
    )

    def future_waiter(
        _future: Future,
        timeout: float,
    ):
        assert started.wait(timeout=1.0)
        assert timeout > 0.0
        clock.advance(expected_grant)
        raise FutureTimeoutError

    with query_ledger.query_ledger_scope() as query_book:
        with HeadlessToolGateway(
            registry=_slow_registry(
                started=started,
                release=release,
                finished=finished,
            ),
            context=context,
            transport="mailbox",
            finalization_floor_ratio=0.0,
            monotonic=clock,
            future_waiter=future_waiter,
        ) as gateway:
            result = gateway.call("market_data", "市场")
            at_handoff = gateway.snapshot()
            release.set()
            assert finished.wait(timeout=1.0)
            after_late_finish = gateway.snapshot()

    assert result["status"] == "rejected"
    assert result["error"] == "research_stage_closed"
    assert result["instruction"] == FINALIZATION_INSTRUCTION
    assert result["budget"]["must_finalize"] is True
    assert [event.kind for event in at_handoff.events] == [
        "tool_request",
        "tool_error",
        "finalization",
    ]
    request_id = at_handoff.events[0].payload["request_id"]
    assert at_handoff.events[1].payload["request_id"] == request_id
    assert at_handoff.events[1].payload["reason"] == "inflight_tool_timeout"
    assert at_handoff.events[1].payload["tool_grant_seconds"] == expected_grant
    assert at_handoff.events[1].payload["tool_grant_limiter"] == expected_limiter
    assert at_handoff.events[2].payload["request_id"] == request_id
    assert at_handoff.events[2].payload["reason"] == "inflight_tool_timeout"
    assert after_late_finish == at_handoff
    assert query_book.summary()["executed_count"] == 0
    assert ledger.remaining_calls == 1
    assert ledger.remaining_seconds == pytest.approx(
        total_seconds - expected_grant
    )

    source = tmp_path / f"{expected_limiter}.json"
    target = tmp_path / f"{expected_limiter}.normalized.json"
    source.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "cases": [
                    {
                        "id": expected_limiter,
                        "arms": [
                            {
                                "diagnostics": {
                                    "events": [
                                        event.to_dict()
                                        for event in at_handoff.events
                                    ]
                                }
                            }
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    assert normalize_trace(
        [str(source), "--kind", "runtime-benchmark", "--output", str(target)]
    ) == 0
    artifact = json.loads(target.read_text(encoding="utf-8"))
    assert artifact["unpaired_tool_requests"] == 0
```

- [ ] **Step 2: 增加 external cancellation RED 测试**

```python
def test_gateway_external_cancellation_suppresses_late_publication() -> None:
    clock = _FakeClock()
    started = Event()
    release = Event()
    finished = Event()
    cancelled = Event()
    base = _context()
    ledger = InMemoryRootBudgetLedger(
        episode_id=base.contract.task_id,
        initial_calls=1,
        hard_calls_cap=1,
        initial_seconds=3.0,
        hard_seconds_cap=3.0,
    )
    context = replace(
        base,
        deadline=_ClockDeadline(
            clock,
            total_seconds=3.0,
            synthesis_reserve=1.0,
        ),
        root_budget=ledger,
    )

    def future_waiter(_future: Future, timeout: float):
        assert started.wait(timeout=1.0)
        clock.advance(timeout)
        cancelled.set()
        raise FutureTimeoutError

    with query_ledger.query_ledger_scope() as query_book:
        with HeadlessToolGateway(
            registry=_slow_registry(
                started=started,
                release=release,
                finished=finished,
            ),
            context=context,
            is_cancelled=cancelled.is_set,
            transport="mailbox",
            finalization_floor_ratio=0.0,
            monotonic=clock,
            future_waiter=future_waiter,
        ) as gateway:
            result = gateway.call("market_data", "市场")
            before_release = gateway.snapshot()
            release.set()
            assert finished.wait(timeout=1.0)
            after_release = gateway.snapshot()

    assert result == {
        "status": "rejected",
        "tool": "market_data",
        "error": "cancelled",
    }
    assert [event.kind for event in before_release.events] == [
        "tool_request",
        "tool_error",
    ]
    assert after_release == before_release
    assert query_book.summary()["executed_count"] == 0
    assert ledger.remaining_calls == 0
    assert ledger.remaining_seconds < 3.0
```

- [ ] **Step 3: 增加真实 mailbox wrapper + fake Codex process RED 测试**

在 `test_codex_headless_runtime.py` 把 threading import 改为：

```python
from threading import Event, Thread
```

```python
def test_headless_runtime_finishes_after_inflight_tool_handoff() -> None:
    frame = _frame()
    started = Event()
    release = Event()

    def slow_runner(_query: str, _context: AgentToolContext):
        started.set()
        release.wait(timeout=5.0)
        return (
            [],
            "late",
            ProviderTrace(
                provider="test:slow",
                capability="mainline_context",
                status="empty",
                result_count=0,
            ),
        )

    registry = ResearchToolRegistry(
        (
            ToolSpec(
                name="mainline_context",
                capability="mainline_context",
                description="慢只读工具",
                cost="local",
                freshness="current",
                runner=slow_runner,
            ),
        )
    )

    def finishing_runner(command: HeadlessCommand) -> HeadlessProcessResult:
        wrapper = command.cwd / "finance-tool"
        tool_command = [str(wrapper), "mainline_context", "A股 当前主线"]
        completed = subprocess.run(
            tool_command,
            cwd=command.cwd,
            env=command.env,
            check=True,
            capture_output=True,
            text=True,
            timeout=3.0,
        )
        result = json.loads(completed.stdout)
        assert started.is_set()
        assert result["error"] == "research_stage_closed"
        assert result["instruction"] == FINALIZATION_INSTRUCTION
        finish = {
            "status": "partial",
            "draft": "现有证据不足，研究窗口已关闭。",
            "gaps": ["inflight_tool_timeout"],
            "bindings": [
                {
                    "output_id": "direct_assessment",
                    "evidence_hashes": [],
                    "gap": "研究工具未在安全窗口内返回",
                }
            ],
        }
        return HeadlessProcessResult(
            _jsonl(wrapper_command=shlex.join(tool_command), finish=finish),
            "",
            0,
            False,
        )

    base = _context(frame)
    context = replace(
        base,
        deadline=ResearchDeadline.from_timeout(3.0, synthesis_reserve=1.0),
        policy=ResearchPolicy("quick", 2, 3.0, 1.0),
    )
    try:
        outcome = CodexHeadlessRuntime(
            command_runner=finishing_runner,
            finalization_floor_ratio=0.0,
        ).run(
            task_frame=frame,
            context=context,
            registry=registry,
        )
    finally:
        release.set()

    assert outcome.stop_reason == "model_finish"
    assert outcome.status == "partial"
    kinds = [event.kind for event in outcome.events]
    assert kinds.index("tool_error") < kinds.index("finalization") < kinds.index(
        "finish"
    )
    runtime_event = next(
        event for event in outcome.events if event.kind == "runtime_result"
    )
    assert len(runtime_event.payload["mailbox_exchanges"]) == 1
```

- [ ] **Step 4: 增加 transport conflict 分账回归**

在 gateway test 直接调用现有 mailbox processor 制造独占写冲突，避免等待 wrapper 60 秒：

```python
def test_mailbox_conflict_is_not_a_second_execution_terminal(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    requests_dir = tmp_path / "requests"
    responses_dir = tmp_path / "responses"
    requests_dir.mkdir()
    responses_dir.mkdir()
    gateway = HeadlessToolGateway(
        registry=_registry([]),
        context=_context(),
        transport="mailbox",
    )
    try:
        request_id = "a" * 32
        request_path = requests_dir / f"{request_id}.json"
        response_path = responses_dir / f"{request_id}.json"
        request_path.write_text(
            json.dumps({"tool": "market_data", "query": "市场"}),
            encoding="utf-8",
        )
        monkeypatch.setattr(
            gateway,
            "_write_mailbox_response",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(
                FileExistsError("simulated response conflict")
            ),
        )
        gateway._process_mailbox_request(request_path, response_path)
        events = gateway.snapshot().events
    finally:
        gateway.close()

    execution_terminals = [
        event
        for event in events
        if event.kind in {"tool_result", "tool_error"}
        and not (
            event.kind == "tool_error"
            and event.payload.get("tool") == "mailbox"
            and event.payload.get("error") == "response_path_conflict"
        )
    ]
    transport_errors = [
        event
        for event in events
        if event.kind == "tool_error"
        and event.payload.get("error") == "response_path_conflict"
    ]
    assert len(execution_terminals) == 1
    assert execution_terminals[0].kind == "tool_result"
    assert len(transport_errors) == 1
    assert transport_errors[0].payload["request_id"] == request_id
```

在 normalizer test 锁定额外 transport response 不会制造 pending，也不会抵消另一 id：

```python
def test_runtime_benchmark_transport_conflict_does_not_unpair_request(
    tmp_path,
) -> None:
    request_id = "a" * 32
    source = tmp_path / "benchmark.json"
    source.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "cases": [
                    {
                        "id": "conflict",
                        "arms": [
                            {
                                "diagnostics": {
                                    "events": [
                                        {
                                            "kind": "tool_request",
                                            "payload": {"request_id": request_id},
                                        },
                                        {
                                            "kind": "tool_result",
                                            "payload": {"request_id": request_id},
                                        },
                                        {
                                            "kind": "tool_error",
                                            "payload": {
                                                "request_id": request_id,
                                                "tool": "mailbox",
                                                "error": "response_path_conflict",
                                            },
                                        },
                                    ]
                                }
                            }
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    target = tmp_path / "normalized.json"

    assert main(
        [str(source), "--kind", "runtime-benchmark", "--output", str(target)]
    ) == 0
    artifact = json.loads(target.read_text(encoding="utf-8"))
    assert artifact["unpaired_tool_requests"] == 0
```

- [ ] **Step 5: 运行 RED**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_headless_tool_gateway.py::test_gateway_handoff_suppresses_late_tool_publication \
  intelligence/tests/test_headless_tool_gateway.py::test_gateway_external_cancellation_suppresses_late_publication \
  intelligence/tests/test_codex_headless_runtime.py::test_headless_runtime_finishes_after_inflight_tool_handoff \
  intelligence/tests/test_headless_tool_gateway.py::test_mailbox_conflict_is_not_a_second_execution_terminal \
  intelligence/tests/test_normalize_harness_trace.py::test_runtime_benchmark_transport_conflict_does_not_unpair_request
```

Expected: 前三项失败，因为 gateway 仍同步等待 runner 且构造函数没有 clock/wait seam；两个 transport 测试是现有语义的 characterization lock，可以先绿。

- [ ] **Step 6: 加入 worker、Future waiter 与 publish guard**

生产 import：

```python
from concurrent.futures import Future, TimeoutError as FutureTimeoutError
from contextvars import Context, copy_context
from threading import Event, Lock, Thread

from intelligence.services import query_ledger
```

模块 helper：

```python
_CANCELLATION_POLL_SECONDS = 0.05
_FutureWaiter = Callable[[Future[ToolObservation], float], ToolObservation]


def _default_future_waiter(
    future: Future[ToolObservation],
    timeout: float,
) -> ToolObservation:
    return future.result(timeout=timeout)


def _run_tool_worker(
    future: Future[ToolObservation],
    *,
    worker_context: Context,
    publish_guard: query_ledger.QueryPublishGuard,
    registry: ResearchToolRegistry,
    name: str,
    prepared: PreparedToolArguments,
    context: ResearchRunContext,
    step_id: str,
    is_cancelled: Callable[[], bool],
) -> None:
    def execute() -> ToolObservation:
        with query_ledger.query_publish_guard_scope(publish_guard):
            return registry.execute(
                name,
                prepared,
                context=context,
                step_id=step_id,
                is_cancelled=is_cancelled,
            )

    try:
        observation = worker_context.run(execute)
    except BaseException as exc:
        future.set_exception(exc)
    else:
        future.set_result(observation)
```

构造函数追加两个测试 seam；默认生产行为不变。精确修改 signature，并在现有
`self._closed = False` 后保存依赖：

```diff
 def __init__(
     self,
     *,
     registry: ResearchToolRegistry,
     context: ResearchRunContext,
     is_cancelled: Callable[[], bool] | None = None,
     run_dir: Path | None = None,
     transport: str = "http",
     finalization_floor_ratio: float = 0.65,
+    monotonic: Callable[[], float] | None = None,
+    future_waiter: _FutureWaiter | None = None,
 ) -> None:

     self._closed = False
+    self._monotonic = monotonic if monotonic is not None else time.monotonic
+    self._future_waiter = (
+        future_waiter if future_waiter is not None else _default_future_waiter
+    )
```

等待循环：

```python
def _await_tool_future(
    self,
    future: Future[ToolObservation],
    *,
    cutoff: float,
) -> tuple[str, ToolObservation | None]:
    while True:
        if self._is_cancelled():
            return "cancelled", None
        remaining = max(0.0, cutoff - self._monotonic())
        if remaining <= 0.0:
            return "timeout", None
        try:
            observation = self._future_waiter(
                future,
                min(_CANCELLATION_POLL_SECONDS, remaining),
            )
        except FutureTimeoutError:
            continue
        return "completed", observation
```

- [ ] **Step 7: 用 watchdog 替换同步执行块**

在锁内 admission 成功后保留本次 `grant`，然后替换原同步 `registry.execute()`：

```python
request_cancelled = Event()

def request_is_cancelled() -> bool:
    return self._is_cancelled() or request_cancelled.is_set()

started_at = self._monotonic()
cutoff = started_at + grant.seconds
publish_guard = query_ledger.QueryPublishGuard(
    publish_cutoff=cutoff,
    monotonic=self._monotonic,
    is_cancelled=request_is_cancelled,
)
future: Future[ToolObservation] = Future()
worker = Thread(
    target=_run_tool_worker,
    kwargs={
        "future": future,
        "worker_context": self._contextvars.copy(),
        "publish_guard": publish_guard,
        "registry": self._registry,
        "name": name,
        "prepared": prepared,
        "context": self._context,
        "step_id": step_id,
        "is_cancelled": request_is_cancelled,
    },
    name=f"headless-tool-{resolved_request_id[:8]}",
    daemon=True,
)
worker.start()

try:
    wait_status, observation = self._await_tool_future(future, cutoff=cutoff)
except Exception:
    request_cancelled.set()
    publish_guard.close(rollback=True)
    return self._complete_dispatched_error(
        request_id=resolved_request_id,
        tool=name,
        error="tool_exception",
        elapsed_seconds=self._monotonic() - started_at,
        grant=grant,
        step_id=step_id,
    )

if wait_status != "completed" or observation is None:
    request_cancelled.set()
    publish_guard.close(rollback=True)
    return self._complete_dispatched_error(
        request_id=resolved_request_id,
        tool=name,
        error=(
            "cancelled" if wait_status == "cancelled" else "research_stage_closed"
        ),
        elapsed_seconds=self._monotonic() - started_at,
        grant=grant,
        step_id=step_id,
    )

if self._is_cancelled():
    request_cancelled.set()
    publish_guard.close(rollback=True)
    return self._complete_dispatched_error(
        request_id=resolved_request_id,
        tool=name,
        error="cancelled",
        elapsed_seconds=self._monotonic() - started_at,
        grant=grant,
        step_id=step_id,
    )

if not self._charge_root_budget(self._monotonic() - started_at):
    publish_guard.close(rollback=True)
    return self._root_budget_rejection(
        request_id=resolved_request_id,
        tool=name,
    )

publish_guard.close()
return self._publish_observation(
    spec.query_scope,
    observation,
    request_id=resolved_request_id,
)
```

增加统一 dispatched error 构造器；`inflight_tool_timeout` 同时加入 `_FINALIZATION_REASONS`：

```python
def _complete_dispatched_error(
    self,
    *,
    request_id: str,
    tool: str,
    error: str,
    elapsed_seconds: float,
    grant: _ToolGrant,
    step_id: str,
) -> dict[str, object]:
    if not self._charge_root_budget(elapsed_seconds):
        return self._root_budget_rejection(request_id=request_id, tool=tool)

    with self._lock:
        if error == "research_stage_closed":
            exit_budget = self._effective_budget()
            self._add_event(
                "tool_error",
                {
                    "request_id": request_id,
                    "tool": tool,
                    "error": "research_stage_closed",
                    "reason": "inflight_tool_timeout",
                    "tool_grant_seconds": round(grant.seconds, 3),
                    "tool_grant_limiter": grant.limiter,
                    "remaining_root_seconds": round(
                        exit_budget.remaining_root_seconds, 3
                    ),
                    "remaining_research_seconds": round(
                        exit_budget.remaining_research_seconds, 3
                    ),
                },
            )
            self._begin_finalization_locked(
                "inflight_tool_timeout",
                request_id=request_id,
            )
            return {
                "status": "rejected",
                "tool": tool,
                "error": "research_stage_closed",
                "instruction": FINALIZATION_INSTRUCTION,
                "budget": self._budget_payload(),
            }

        if error == "cancelled":
            self._add_event(
                "tool_error",
                {"request_id": request_id, "tool": tool, "error": "cancelled"},
            )
            return {"status": "rejected", "tool": tool, "error": "cancelled"}

        trace = ProviderTrace(
            provider=f"headless:{tool}",
            capability=tool,
            status="request_error",
            detail="tool_exception",
            parent_id=self._context.trace_parent_id,
            step_id=step_id,
        )
        self._traces.append(trace)
        self._add_event(
            "tool_error",
            {"request_id": request_id, "tool": tool, "error": "tool_exception"},
        )
        return {"status": "error", "tool": tool, "error": "tool_exception"}
```

timeout/cancellation 后不得 `join()` worker、不得加 done callback。worker 只持 registry/context/future/guard，不得拿 gateway 的 evidence/traces/events 容器。

- [ ] **Step 8: 运行 GREEN 与相关隔离套件**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_headless_tool_gateway.py \
  intelligence/tests/test_codex_headless_runtime.py \
  intelligence/tests/test_normalize_harness_trace.py \
  intelligence/tests/test_p1b_runtime.py \
  intelligence/tests/test_episode_tool_batch.py
```

Expected: 全绿；新增函数对应 6 个 collected test（slow-tool 的 handoff/transport 两个参数各算一个）。slow-tool snapshot 在释放 worker 前后逐值相同，wrapper exit code=0，normalizer 的 `unpaired_tool_requests=0`。

- [ ] **Step 9: Ruff 与第三次提交**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m ruff check \
  intelligence/services/headless_tool_gateway.py \
  intelligence/tests/test_headless_tool_gateway.py \
  intelligence/tests/test_codex_headless_runtime.py \
  intelligence/tests/test_normalize_harness_trace.py

git add intelligence/services/headless_tool_gateway.py \
  intelligence/tests/test_headless_tool_gateway.py \
  intelligence/tests/test_codex_headless_runtime.py \
  intelligence/tests/test_normalize_harness_trace.py
git commit -m "fix(runtime): hand off stalled headless tools"
```

### Task 4: 执行离线 release gate 并冻结 clean revision

**Files:**
- Verify only; no new production file.

- [ ] **Step 1: 运行 focused runtime/benchmark suite**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_headless_tool_gateway.py \
  intelligence/tests/test_codex_headless_runtime.py \
  intelligence/tests/test_normalize_harness_trace.py \
  intelligence/tests/test_runtime_backend_benchmark.py \
  intelligence/tests/test_run_agent_runtime_benchmark.py \
  intelligence/tests/test_p1b_runtime.py \
  intelligence/tests/test_episode_tool_batch.py
```

Expected: 全绿；若现有平台 skip 仍存在，逐名报告，不把 skip 记成 pass。

- [ ] **Step 2: 声明两个 collected scope 并跑 clean-host 全量**

```bash
env -u FORESIGHT_USERS_DIR -u SUBCONSCIOUS_VAULT \
  /Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest \
  --collect-only -q

env -u FORESIGHT_USERS_DIR -u SUBCONSCIOUS_VAULT \
  /Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest \
  --collect-only -q intelligence/tests

env -u FORESIGHT_USERS_DIR -u SUBCONSCIOUS_VAULT \
  /Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q

env -u FORESIGHT_USERS_DIR -u SUBCONSCIOUS_VAULT \
  /Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests
```

Expected: 两个 collected 数都比父 revision 各增加本计划的 11 个测试；已知两条 `test_acceptance_board` CLI contract drift 若仍红，名称与父 revision完全一致。任何新增失败都阻止 live，不能只按总数对齐。

- [ ] **Step 3: 检查预算/profile/prompt 零变化与风险文件**

```bash
git diff a21b0539 -- \
  intelligence/services/research_contract.py \
  intelligence/eval/runtime_backend_benchmark.py \
  scripts/run_agent_runtime_benchmark.py \
  intelligence/services/codex_headless_runtime.py

git diff --check
git status --short
git branch --show-current
```

Expected: 上述四个生产文件零 diff；分支为 `fix/headless-tool-correlation-observability`；工作树干净。不得出现 `.env*`、密钥、数据库、PDF、压缩包、缓存或虚拟环境。

- [ ] **Step 4: 若全量出现新红，用父 revision 同名复跑归因**

只在 Step 2 出现新失败时执行，使用临时 detached worktree 跑父 revision 的完整
`intelligence/tests` scope，再按 pytest node id 对账；不改当前分支：

```bash
git worktree add --detach /tmp/headless-r10-parent a21b0539
env -u FORESIGHT_USERS_DIR -u SUBCONSCIOUS_VAULT \
  /Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  --rootdir /tmp/headless-r10-parent \
  /tmp/headless-r10-parent/intelligence/tests
git worktree remove /tmp/headless-r10-parent
```

没有新红时不得创建这个 worktree。父 revision 全量只是归因工具，不改变当前 revision 的
release gate。

### Task 5: 执行唯一瑞华泰 canary

**Files:**
- Create: `intelligence/eval/measurements/2026-08-04c-inflight-handoff/ruihuatai-c-long-capped-r10.json`
- Create: `intelligence/eval/measurements/2026-08-04c-inflight-handoff/ruihuatai-c-long-capped-r10.normalized.json`

- [ ] **Step 1: 确认 live 前置门**

只有 Task 4 全部满足才继续：

```bash
git status --short
git rev-parse HEAD
git branch --show-current
```

Expected: 工作树干净；HEAD 是包含 watchdog 的已提交 revision；分支不变。禁止为 canary 调整 `total_seconds`、`gateway_floor_ratio`、`max_tool_calls`、模型、provider 或 prompt。

- [ ] **Step 2: 只跑 `c_long_capped/ruihuatai-valuation`**

```bash
mkdir -p intelligence/eval/measurements/2026-08-04c-inflight-handoff

/Users/a77/finance-workspace-private/.venv-workbench/bin/python \
  scripts/run_agent_runtime_benchmark.py \
  --backend codex_headless \
  --headless-budget-profile c_long_capped \
  --case ruihuatai-valuation \
  --questions-file /Users/a77/.finance-runtime/evals/adaptive-runtime-five-cases-2026-07-27.json \
  --finance-root /Users/a77/finance-workspace-private \
  --knowledge-wiki /Users/a77/知识库/wiki \
  --output intelligence/eval/measurements/2026-08-04c-inflight-handoff/ruihuatai-c-long-capped-r10.json
```

Expected: `case_count=1`。不得重跑另外四题，也不得重跑 a/b/d 四臂。

- [ ] **Step 3: 归一化并提取可证伪字段**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python \
  -m intelligence.eval.normalize_harness_trace \
  intelligence/eval/measurements/2026-08-04c-inflight-handoff/ruihuatai-c-long-capped-r10.json \
  --kind runtime-benchmark \
  --output intelligence/eval/measurements/2026-08-04c-inflight-handoff/ruihuatai-c-long-capped-r10.normalized.json

jq '{
  source_revision,
  source_dirty,
  headless_budget_profile,
  case_count,
  case: (.cases[0].arms[0] | {
    latency_seconds,
    tool_calls,
    event_stop_reason: ([.diagnostics.events[] | select(.kind == "finish") | .payload.stop_reason] | first),
    handoff: [.diagnostics.events[] | select(
      .kind == "tool_request" or
      .kind == "tool_error" or
      .kind == "finalization"
    ) | {kind, payload}]
  })
}' intelligence/eval/measurements/2026-08-04c-inflight-handoff/ruihuatai-c-long-capped-r10.json

jq '{source_kind, unmapped_count, unpaired_tool_requests}' \
  intelligence/eval/measurements/2026-08-04c-inflight-handoff/ruihuatai-c-long-capped-r10.normalized.json
```

Required structural facts: `source_dirty=false`、profile=`180/6/30/0.0`、`unmapped_count=0`、`unpaired_tool_requests=0`。若没有 `inflight_tool_timeout`，必须按生效 grant 判断是本次工具自然完成，还是 watchdog 没激活；不能把“事件没出现”自动判成实现失败。

- [ ] **Step 4: 按预注册条件裁决 R-10**

1. 事件级 `model_finish` 且 latency `<150`：`R-20260804-10 confirmed`；缺 in-flight handoff 是该冻结失败层的 PRIMARY。
2. 仍非 `model_finish`（包括 timeout 或 protocol rejection），且 `finish.timestamp - finalization.timestamp` 大于 finalization 入场剩余：`R-20260804-10 refuted`；新开“finalization 自身自然耗时超过交接余量”，不调预算掩盖。
3. 仍非 `model_finish`，但实测 finalization 用时小于入场剩余：`R-20260804-10 refuted`；handoff 已激活但不足以完成，转查 finalization 输出/协议，不调预算。
4. 失败且没有 handoff，而 request grant/limiter 表明 watchdog 应触发：R-10 保持 `pending`，回查生效 revision/profile 和 activation path；这是实现未生效，不是机制反证。

若 limiter=`transport_timeout`，报告 transport 先到的事实；它不能冒充 root handoff 直接证据。分析异常 run 时加载 `agent-run-triage`，仍按 Evidence→Finding→Path 与执行层/transport 层分账。

无论结果属于哪一分支，都不得追加第二次 live 调试 run。

### Task 6: 写验证结论、更新账本并交付分支

**Files:**
- Create: `docs/verification/2026-08-04c-headless-inflight-handoff.md`
- Modify: `docs/prediction-ledger.md`
- Modify: `docs/trace-profile.md`
- Modify: `docs/handoffs/2026-08-04b-finalization-handoff.md`
- Modify: `/Users/a77/agent-memory-answer-spec/20_projects/finance-workspace-private.md`

- [ ] **Step 1: 写离线结构门与唯一 canary 的证据链**

验证文档固定包含：

- code revision、raw/normalized SHA-256、`source_dirty` 与 profile 四字段；
- 两个 pytest scope 的 collected/pass/fail/skip，以及父 revision 同名失败对账；
- direct slow-tool 的 `request → error → finalization`、同 request id、late snapshot 恒等、QueryLedger 0、root call 1；
- real wrapper 的 exit code 0、mailbox exchange 1、`model_finish`；
- live 的事件级 stop reason、latency、grant、limiter、finalization 入场余量与实测时差；
- Task 5 的唯一一个预注册裁决，不混入第二假设。

所有数值从 Step 3 的 raw artifact 或 pytest 输出逐字抄录；不得用 arm 级 stop reason 替代事件级 finish，也不得把 `elapsed<=180` 当验收。

- [ ] **Step 2: 更新 prediction ledger、trace profile 与 handoff**

`docs/prediction-ledger.md` 的 R-10 只能写 Task 5 四项条件中的一个 outcome；`docs/trace-profile.md` 增加以下稳定语义：

```markdown
- `tool_grant_seconds` 是 request 入场冻结的执行权，不是工具自然耗时。
- `tool_grant_limiter=transport_timeout` 表示 60 秒 wrapper 协议先于 research handoff；
  `handoff_window` 表示 deadline/root 的安全窗口先到。
- `tool=mailbox,error=response_path_conflict` 是 transport 诊断，不计入同 request id 的执行层终态基数。
- timeout 后 daemon worker 的自然完成时间不计入 episode 可用预算，也不得发布 evidence、trace 或 QueryLedger record。
```

handoff 顶部补 R-10 最终状态、唯一 canary 证据和下一步；保留“不移墙、不重跑四臂”的禁令。

- [ ] **Step 3: 回写安全 memory worktree**

只把稳定项目决策追加到 `/Users/a77/agent-memory-answer-spec/20_projects/finance-workspace-private.md`：gateway-local watchdog、显式 reserve authority、迟到发布隔离、唯一 canary 裁决。不要写聊天流水，不要触碰 `/Users/a77/agent-memory` 的危险未推分支。

```bash
git -C /Users/a77/agent-memory-answer-spec status --short
git -C /Users/a77/agent-memory-answer-spec branch --show-current
git -C /Users/a77/agent-memory-answer-spec pull --ff-only
git -C /Users/a77/agent-memory-answer-spec add \
  20_projects/finance-workspace-private.md
git -C /Users/a77/agent-memory-answer-spec diff --cached --check
git -C /Users/a77/agent-memory-answer-spec commit -m \
  "docs(memory): record headless inflight handoff"
git -C /Users/a77/agent-memory-answer-spec push
```

Expected: 分支为 `main`、开工时 clean；只提交一个项目记忆文件。若开工时不 clean，先停止
memory 回写并报告，不能把他人改动带入本轮 commit。

- [ ] **Step 4: 最终格式、风险与回归检查**

```bash
git diff --check
git status --short
git branch --show-current

/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m ruff check \
  intelligence/services/headless_tool_gateway.py \
  intelligence/tests/test_headless_tool_gateway.py \
  intelligence/tests/test_codex_headless_runtime.py \
  intelligence/tests/test_normalize_harness_trace.py

/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_headless_tool_gateway.py \
  intelligence/tests/test_codex_headless_runtime.py \
  intelligence/tests/test_normalize_harness_trace.py \
  intelligence/tests/test_runtime_backend_benchmark.py \
  intelligence/tests/test_run_agent_runtime_benchmark.py
```

Expected: Ruff 0；focused 全绿；风险扫描不含 `.env*`、密钥、数据库、PDF、压缩包、缓存或虚拟环境。

- [ ] **Step 5: 提交验证产物与文档**

```bash
git add \
  intelligence/eval/measurements/2026-08-04c-inflight-handoff/ruihuatai-c-long-capped-r10.json \
  intelligence/eval/measurements/2026-08-04c-inflight-handoff/ruihuatai-c-long-capped-r10.normalized.json \
  docs/verification/2026-08-04c-headless-inflight-handoff.md \
  docs/prediction-ledger.md \
  docs/trace-profile.md \
  docs/handoffs/2026-08-04b-finalization-handoff.md
git commit -m "docs(eval): verify headless in-flight handoff"
git push
```

memory worktree 单独提交并 push；代码分支不合并 main、不强推。
