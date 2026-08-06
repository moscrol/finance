# Headless Active Finalization Handoff Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 Codex headless 在真实 deadline-pressure / tool-cap / rejection 边界收到一次明确收口指令，并用同一 `c_long_capped` 五题可证伪验收。

**Architecture:** `HeadlessToolGateway` 冻结内部 handoff window，所有 activation 复用幂等 `begin_finalization`。指令随真实 tool result/rejection 返回到同一模型上下文，既有 runtime finish 协议和 recovery 保持不变。

**Tech Stack:** Python 3.12、pytest、mailbox/HTTP gateway、Codex CLI、JSON benchmark artifact。

---

## Execution status (2026-08-04)

- T2 code: `3dd867e9`；预算 profile 零 diff。
- Focused: 97 passed / 1 skipped；全量：2 known baseline failed / 3704 passed / 2 skipped。
- 唯一 T3 live 已执行并归一化：54 events / 0 unmapped / 0 finalization。
- 瑞华泰：事件级 `headless_protocol_rejected` / 135.555s；5 requests / 4 mailbox exchanges。
- R-09 已 refuted；下一层登记为 R-10（in-flight tool deadline handoff），没有追加 live run。

### Task 1: Deadline-pressure result 主动交接

**Files:**
- Modify: `intelligence/tests/test_headless_tool_gateway.py`
- Modify: `intelligence/services/headless_tool_gateway.py`

- [x] **Step 1: 写失败测试**

使用 mutable deadline + `floor_ratio=0.0`：初始 150s，成功执行首个工具后把 remaining 调到 25s，再执行第二个工具。断言第二个成功 result 含固定 `instruction`，snapshot 只有一个 `finalization(reason=deadline_pressure)`，第三个工具请求被 `research_stage_closed` 拒绝且仍含 instruction。

```python
def test_gateway_hands_off_after_result_enters_deadline_pressure() -> None:
    class MutableDeadline:
        synthesis_reserve = 0.0

        def __init__(self) -> None:
            self.seconds = 150.0

        def remaining(self) -> float:
            return self.seconds

        def stage_timeout(self, configured_limit: float) -> float:
            return min(float(configured_limit), self.seconds)

        @property
        def expired(self) -> bool:
            return self.seconds <= 0.0

    deadline = MutableDeadline()
    context = replace(_context(max_steps=3), deadline=deadline)
    with HeadlessToolGateway(
        registry=_registry([]),
        context=context,
        finalization_floor_ratio=0.0,
    ) as gateway:
        gateway.call("market_data", "市场")
        deadline.seconds = 25.0
        result = gateway.call("news_search", "补充消息")
        rejected = gateway.call("news_search", "继续补查")
        snapshot = gateway.snapshot()

    assert result["instruction"] == FINALIZATION_INSTRUCTION
    assert rejected["error"] == "research_stage_closed"
    assert rejected["instruction"] == FINALIZATION_INSTRUCTION
    finalization = [event for event in snapshot.events if event.kind == "finalization"]
    assert len(finalization) == 1
    assert finalization[0].payload["reason"] == "deadline_pressure"
```

- [x] **Step 2: 运行 RED**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_headless_tool_gateway.py::test_gateway_hands_off_after_result_enters_deadline_pressure
```

Expected: 当前 result 无 instruction、无 deadline-pressure finalization。

- [x] **Step 3: 最小实现**

冻结 handoff window；让 `_budget_payload.must_finalize` 纳入 deadline pressure 与已开始的 transition；`_publish_observation` 先写 result，再发 finalization；`_reservation_error` 在 transition 后 fail-closed。

```python
_FINALIZATION_INSTRUCTION = "研究取证阶段已结束，请使用已有信息完成终止回答。"

self._finalization_handoff_seconds = min(
    30.0,
    max(5.0, initial_research_seconds * 0.20),
)

def _pending_finalization_reason(self) -> str | None:
    if self._finalization_event is not None:
        return str(self._finalization_event.payload["reason"])
    remaining_calls = max(0, self._context.policy.max_steps - self._executed_count)
    remaining_seconds = self._context.deadline.stage_timeout(
        self._context.deadline.remaining()
    )
    if remaining_calls <= 0:
        return "tool_budget_exhausted"
    if remaining_seconds <= self._finalization_handoff_seconds:
        return "deadline_pressure"
    if self._executed_count > 0 and remaining_seconds <= self._finalization_floor_seconds:
        return "research_stage_closed"
    return None
```

- [x] **Step 4: 运行 GREEN**

重跑同一测试，Expected: 1 passed。

### Task 2: Tool cap 与 rejection 共享指令

**Files:**
- Modify: `intelligence/tests/test_headless_tool_gateway.py`
- Modify: `intelligence/services/headless_tool_gateway.py`

- [x] **Step 1: 写 max_steps=1 的失败测试**

首个成功 result 应含 instruction，finalization reason=`tool_budget_exhausted`；随后任意工具请求返回 `research_stage_closed` + instruction，同 episode 不新增第二个 finalization。

```python
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
    finalization = [event for event in snapshot.events if event.kind == "finalization"]
    assert len(finalization) == 1
    assert finalization[0].payload["reason"] == "tool_budget_exhausted"
```

- [x] **Step 2: RED → 最小实现 → GREEN**

只在三个冻结 activation path 加固定 instruction，不改变 invalid-arguments 的 `retry_hint`。运行完整 gateway 测试文件，Expected: 全绿。

```python
reason = self._pending_finalization_reason()
if reason is not None:
    payload["instruction"] = _FINALIZATION_INSTRUCTION
self._add_event("tool_result", payload)
if reason is not None:
    self._begin_finalization_locked(reason)
```

### Task 3: 证明 instruction 穿过真实 subprocess seam

**Files:**
- Modify: `intelligence/tests/test_codex_headless_runtime.py`

- [x] **Step 1: 写 fake Codex 集成失败测试**

context 的 `max_steps=1`。fake runner 调用真实 `finance-tool` wrapper，只有当 JSON result 含固定 instruction 才返回合法 finish；断言 runtime 事件顺序含 `tool_result → finalization → finish`，终态 `model_finish`。

```python
def test_headless_runtime_delivers_tool_cap_finalization_instruction() -> None:
    frame = _frame()

    def finalizing_runner(command: HeadlessCommand) -> HeadlessProcessResult:
        wrapper = command.cwd / "finance-tool"
        tool_command = [str(wrapper), "mainline_context", "A股 当前主线"]
        completed = subprocess.run(
            tool_command,
            cwd=command.cwd,
            env=command.env,
            check=True,
            capture_output=True,
            text=True,
            timeout=5.0,
        )
        result = json.loads(completed.stdout)
        assert result["instruction"] == FINALIZATION_INSTRUCTION
        finish = {
            "status": "completed",
            "draft": "截至2026-07-24，医药是韧性核心。",
            "gaps": [],
            "bindings": [{
                "output_id": "direct_assessment",
                "evidence_hashes": result["evidence_hashes"],
                "gap": "",
            }],
        }
        return HeadlessProcessResult(
            _jsonl(wrapper_command=shlex.join(tool_command), finish=finish),
            "",
            0,
            False,
        )

    context = replace(_context(frame), policy=ResearchPolicy("quick", 1, 30.0, 0.0))
    outcome = CodexHeadlessRuntime(command_runner=finalizing_runner).run(
        task_frame=frame,
        context=context,
        registry=_registry([]),
    )
    assert outcome.stop_reason == "model_finish"
    kinds = [event.kind for event in outcome.events]
    assert kinds.index("tool_result") < kinds.index("finalization") < kinds.index("finish")
```

- [x] **Step 2: 运行 RED/GREEN 与 focused suite**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_headless_tool_gateway.py \
  intelligence/tests/test_codex_headless_runtime.py \
  intelligence/tests/test_normalize_harness_trace.py \
  intelligence/tests/test_run_agent_runtime_benchmark.py
```

Expected: 全绿；normalizer 外部未提交改动若独立失败，必须与本轮 tests 分账，不得混入 commit。

### Task 4: 提交干净 revision 并执行唯一 T3 run

**Files:**
- Create: `intelligence/eval/measurements/2026-08-04b-finalization/c-long-capped-t2.json`
- Create: `intelligence/eval/measurements/2026-08-04b-finalization/c-long-capped-t2.normalized.json`

- [x] **Step 1: 确认预算零 diff并提交**

```bash
git diff -- intelligence/services/research_contract.py intelligence/eval/runtime_backend_benchmark.py
git diff --check
git status --short
git branch --show-current
```

Expected: 两个预算文件无 diff；分支为 `eval/budget-calibration`。并发外部改动按 hunk 排除。

- [x] **Step 2: 从提交后的 detached clean worktree 跑同一 c profile 五题**

命令与 T1 完全相同，只把输出改为 `c-long-capped-t2.json`。不跑 a/b/d，不碰生产 runtime。

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python \
  scripts/run_agent_runtime_benchmark.py \
  --backend codex_headless \
  --headless-budget-profile c_long_capped \
  --questions-file /Users/a77/.finance-runtime/evals/adaptive-runtime-five-cases-2026-07-27.json \
  --finance-root /Users/a77/finance-workspace-private \
  --knowledge-wiki /Users/a77/知识库/wiki \
  --output /Users/a77/finance-workspace-private-synthesis-release/intelligence/eval/measurements/2026-08-04b-finalization/c-long-capped-t2.json
```

- [x] **Step 3: 归一化并按三结局记账**

断言 `source_dirty=false`、profile 四字段与 T1 相同、`unmapped_count=0`；提取逐题 event stop_reason、latency、finalization reason/remaining/duration。只按 design 的三种结局更新 R-09。

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python \
  -m intelligence.eval.normalize_harness_trace \
  intelligence/eval/measurements/2026-08-04b-finalization/c-long-capped-t2.json \
  --kind runtime-benchmark \
  --output intelligence/eval/measurements/2026-08-04b-finalization/c-long-capped-t2.normalized.json
```

### Task 5: 收尾文档、测试与推送

**Files:**
- Create: `docs/verification/2026-08-04b-finalization.md`
- Modify: `docs/prediction-ledger.md`
- Modify: `docs/trace-profile.md`
- Modify: `docs/handoffs/2026-08-04b-finalization-handoff.md`

- [x] **Step 1: 写 T1/T2 单变量对照与字段语义**

明确 T1 finalization duration 是截断下界；T2 只比较同 profile、不同 finalization behavior，不把模型采样差异冒充全部因果。

- [x] **Step 2: 更新 ledger/profile/handoff**

R-09 只能 confirmed 或 refuted，不保留 pending；profile 记录 payload timestamp、raw benchmark schema 与 normalized schema 的区分。

- [x] **Step 3: 运行 focused + 全量基线**

focused 使用 Task 3 命令。全量用项目 canonical 路径，预期仍为 13 个同名宿主环境红；若数量或名称变化，先归因再提交。

```bash
env -u FORESIGHT_USERS_DIR \
  /Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q intelligence/tests
```

- [x] **Step 4: 风险扫描、提交、push 分支**

不提交任何 `.env*`、密钥、数据库、PDF、压缩包、缓存或外部并发改动；push `eval/budget-calibration`，不合并 main。
