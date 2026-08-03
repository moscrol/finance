# Headless Finalization Observability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不改预算与模型行为的前提下，为 Codex headless 的真实 finalization 交接和 finish 终态增加可归一化时间戳。

**Architecture:** 由 `HeadlessToolGateway` 提供单一、幂等的 `begin_finalization` 事件入口；既有 rejection 与 finish-only recovery 从该入口记录真实交接。时间字段放在 payload，normalizer 安全读取 payload timestamp，避免扩散修改 `EpisodeEvent` 公共模型。

**Tech Stack:** Python 3.12、pytest、dataclass event model、UTC ISO-8601、JSON benchmark artifact。

---

### Task 1: 冻结 payload timestamp 的归一化契约

**Files:**
- Modify: `intelligence/tests/test_normalize_harness_trace.py`
- Modify: `intelligence/eval/normalize_harness_trace.py`

- [ ] **Step 1: 写 payload timestamp 的失败测试**

在 `test_normalize_harness_trace.py` 增加 runtime-benchmark 记录，顶层无 timestamp、payload 含 `2026-08-04T12:00:00.000Z`，断言 `NormalizedEvent.timestamp` 等于该值。

- [ ] **Step 2: 运行测试确认 RED**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_normalize_harness_trace.py::test_runtime_benchmark_reads_safe_timestamp_from_event_payload
```

Expected: FAIL，当前 `_event_timestamp` 只读 record 顶层，返回 `None`。

- [ ] **Step 3: 最小实现并确认 GREEN**

让 `_event_timestamp` 在顶层未命中时读取 mapping 类型的 `payload`，两层都复用 `_safe_timestamp`。重跑同一测试，Expected: 1 passed。

### Task 2: 冻结 gateway 的单次真实交接事件

**Files:**
- Modify: `intelligence/tests/test_headless_tool_gateway.py`
- Modify: `intelligence/services/headless_tool_gateway.py`

- [ ] **Step 1: 写 research-stage close 的失败测试**

复用现有 mutable deadline seam：先成功调用一次，再把 remaining 调到 floor 内，连续触发两次拒绝；断言 snapshot 只有一个 `finalization`，reason 为 `research_stage_closed`，`remaining_seconds` 非负，timestamp 可由 ISO-8601 解析。

- [ ] **Step 2: 运行测试确认 RED**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_headless_tool_gateway.py::test_gateway_records_one_timestamped_finalization_transition
```

Expected: FAIL，当前 snapshot 没有 finalization。

- [ ] **Step 3: 实现幂等 `begin_finalization`**

入口只接受 `research_stage_closed`、`tool_budget_exhausted`、`deadline_pressure`、`headless_invalid_finish`、`headless_no_finish`，首次写 `reason/remaining_seconds/timestamp`，同一 gateway 后续不重复。rejection 先记录 `tool_error`，再对前两种原因调用入口；不添加 prompt 或 instruction。

- [ ] **Step 4: 重跑 gateway 文件**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_headless_tool_gateway.py
```

Expected: 全绿，既有预算断言不变。

### Task 3: 冻结 runtime recovery 到 finish 的可测区间

**Files:**
- Modify: `intelligence/tests/test_codex_headless_runtime.py`
- Modify: `intelligence/services/codex_headless_runtime.py`

- [ ] **Step 1: 扩展既有 recovery 测试并确认 RED**

在 `test_headless_runtime_allows_one_finish_only_recovery` 断言事件中恰有一个 `finalization`，reason 为初次 finish issue；finalization 与 finish 都有可解析 timestamp，且 finish 不早于 finalization。

- [ ] **Step 2: 在现有 repair command 前记录真实交接**

仅在当前已允许 recovery 的分支调用 `gateway.begin_finalization(finish_issue)`；finish payload 增加 UTC timestamp。不要把普通成功路径事后标成 explicit finalization。

- [ ] **Step 3: 运行三文件 focused tests**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_headless_tool_gateway.py \
  intelligence/tests/test_codex_headless_runtime.py \
  intelligence/tests/test_normalize_harness_trace.py
```

Expected: 全绿。

### Task 4: 提交干净 T1 revision 并只跑 c_long_capped

**Files:**
- Create: `intelligence/eval/measurements/2026-08-04b-finalization/c-long-capped-t1.json`
- Create: `intelligence/eval/measurements/2026-08-04b-finalization/c-long-capped-t1.normalized.json`

- [ ] **Step 1: 检查没有预算或 prompt 漂移并提交 T1**

```bash
git diff --check
git diff -- intelligence/services/research_contract.py intelligence/eval/runtime_backend_benchmark.py
git status --short
git branch --show-current
```

Expected: 后两个预算相关文件无 diff；分支为 `eval/budget-calibration`。提交代码、测试、spec、plan 与 T0 ledger。

- [ ] **Step 2: 用冻结命令运行同一五题**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python \
  scripts/run_agent_runtime_benchmark.py \
  --backend codex_headless \
  --headless-budget-profile c_long_capped \
  --questions-file /Users/a77/.finance-runtime/evals/adaptive-runtime-five-cases-2026-07-27.json \
  --finance-root /Users/a77/finance-workspace-private \
  --knowledge-wiki /Users/a77/知识库/wiki \
  --output intelligence/eval/measurements/2026-08-04b-finalization/c-long-capped-t1.json
```

Expected: 五题落盘；不重跑其余三臂，不触碰生产 runtime。

- [ ] **Step 3: 归一化并断言 T1 判据**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python \
  -m intelligence.eval.normalize_harness_trace \
  intelligence/eval/measurements/2026-08-04b-finalization/c-long-capped-t1.json \
  --kind runtime-benchmark \
  --output intelligence/eval/measurements/2026-08-04b-finalization/c-long-capped-t1.normalized.json
```

用 `jq` 断言 finalization 数量、timestamp 数、逐 case stop_reason 与 profile 生效值；normalizer 的 `unmapped_count` 必须为 0。若 finalization 为 0，T1 不算完成，先回查真实 transition 是否调用入口。

### Task 5: 根据 T1 产物冻结 T2 enforcement point

**Files:**
- Modify: `docs/superpowers/specs/2026-08-04-headless-finalization-observability-design.md`
- Create: `docs/superpowers/plans/2026-08-04-headless-finalization-handoff.md`

- [ ] **Step 1: 对瑞华泰区分三条互斥路径**

按事件与 timestamp 判定：收到 rejection、in-flight tool 未返回、或已进入 recovery 但收尾超时。不得只凭调用顺序推断。

- [ ] **Step 2: 只为被观测到的路径写 T2**

若是 rejection，补明确 finalization instruction；若是 in-flight tool，设计可取消的 deadline-pressure transition；若是 recovery 太慢，R-09 refuted 并转入合成链。T2 计划必须继续保持三个预算字段不变，并另走 red→green。
