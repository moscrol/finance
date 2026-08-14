# Headless Tool Correlation Observability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:tdd to implement this plan task-by-task. Execute inline in the current session; no subagent is requested for this task.

**Goal:** 给 headless tool request/result/error 建立稳定相关身份，并让 normalized artifact 按 source kind 正确区分“已配平 0”“悬空 N”和“不适用 null”。

**Architecture:** gateway 在真实执行入口冻结一个 32-hex request id，mailbox 复用文件名、其他 transport 本地生成，并把同一 id 传播到每个终态 event。normalizer 独立保留 event identity 与 correlation identity，按 kind 选择请求/响应词表，有 id 时严格同 id 配对、旧数据无 id 时仅做 case 内 FIFO 弱配对。旧 v2 artifact 只对新增 optional field 做窄兼容。

**Tech Stack:** Python 3.12、pytest、JSON/JSONL normalized artifacts、Codex headless mailbox gateway。

---

### Task 1: Gateway 为一次调用传播稳定 request id

**Files:**
- Modify: `intelligence/tests/test_headless_tool_gateway.py`
- Modify: `intelligence/services/headless_tool_gateway.py`

- [x] **Step 1: 写 direct success/rejection 的公共 snapshot RED 测试**

通过 `HeadlessToolGateway.call()` 后只观察 `snapshot().events`：

```python
def test_gateway_pairs_terminal_events_with_one_stable_request_id() -> None:
    with HeadlessToolGateway(registry=_registry([]), context=_context()) as gateway:
        gateway.call("market_data", "市场")
        events = gateway.snapshot().events

    assert [event.kind for event in events] == ["tool_request", "tool_result"]
    request_id = events[0].payload["request_id"]
    assert re.fullmatch(r"[0-9a-f]{32}", str(request_id))
    assert events[1].payload["request_id"] == request_id
```

另用 unknown tool 或 closed stage 断言 `tool_request/tool_error` 共享 id。不要 mock `_execute_tool`、`_add_event` 或随机数。

- [x] **Step 2: 运行 RED**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_headless_tool_gateway.py \
  -k 'stable_request_id'
```

Expected: request event 缺 `request_id`。

- [x] **Step 3: 在执行入口生成/验证 id，并传播到所有终态**

核心签名：

```python
_REQUEST_ID_RE = re.compile(r"^[0-9a-f]{32}$")

def _execute_tool(
    self,
    name: str,
    raw_query: object,
    *,
    request_id: str | None = None,
) -> dict[str, object]:
    resolved_request_id = request_id or secrets.token_hex(16)
    if not _REQUEST_ID_RE.fullmatch(resolved_request_id):
        raise ValueError("invalid headless tool request id")
```

`tool_request`、reservation rejection、tool exception、root-budget rejection、post-execution cancellation 与 success result 全部写同一 id。`_charge_root_budget()`、`_publish_observation()` 显式接收 id，避免从可变全局状态猜当前请求。

- [x] **Step 4: 运行 GREEN**

重跑 Step 2，并跑整个 gateway 文件：

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_headless_tool_gateway.py
```

- [x] **Step 5: 提交 runtime slice**

```bash
git add intelligence/services/headless_tool_gateway.py \
  intelligence/tests/test_headless_tool_gateway.py
git commit -m "feat(runtime): correlate headless tool terminal events"
```

### Task 2: Mailbox 复用 transport request identity

**Files:**
- Modify: `intelligence/tests/test_headless_tool_gateway.py`
- Modify: `intelligence/services/headless_tool_gateway.py`

- [x] **Step 1: 扩展 mailbox wrapper 公共 RED 测试**

在现有 `test_mailbox_gateway_executes_without_network_or_bearer` 只增加调用方可见断言：

```python
request_id = snapshot.mailbox_exchanges[0].request_id.removesuffix(".json")
tool_events = [event for event in snapshot.events if event.kind.startswith("tool_")]
assert [event.payload["request_id"] for event in tool_events] == [
    request_id,
    request_id,
]
```

- [x] **Step 2: 运行 RED**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_headless_tool_gateway.py::test_mailbox_gateway_executes_without_network_or_bearer
```

Expected: gateway 生成了另一个 id 或事件没有 id。

- [x] **Step 3: mailbox 处理器把 filename stem 传入执行入口**

```python
result = self._execute_tool(
    str(payload.get("tool") or ""),
    payload.get("query"),
    request_id=request_path.stem,
)
```

保留 `HeadlessMailboxExchange.request_id` 的现有 `.json` 外部契约，不做无关 schema 改名。

- [x] **Step 4: 运行 GREEN 并 amend runtime slice**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_headless_tool_gateway.py
git add intelligence/services/headless_tool_gateway.py \
  intelligence/tests/test_headless_tool_gateway.py
git commit --amend --no-edit
```

### Task 3: Normalizer 区分 Codex 配对与 Workbench N/A

**Files:**
- Modify: `intelligence/tests/test_normalize_harness_trace.py`
- Modify: `intelligence/eval/normalize_harness_trace.py`

- [x] **Step 1: 写 CLI RED：Codex 悬空为 1，Workbench 为 null**

```python
def test_pairing_metric_is_kind_aware(tmp_path) -> None:
    rollout = tmp_path / "rollout.jsonl"
    rollout.write_text(
        "\n".join(
            json.dumps(event)
            for event in (
                {"type": "function_call", "id": "c1"},
                {"type": "function_call_output", "id": "c1o"},
                {"type": "function_call", "id": "c2"},
                {"type": "turn.failed"},
            )
        ),
        encoding="utf-8",
    )
    codex_target = tmp_path / "codex.json"
    assert main([str(rollout), "--kind", "codex-rollout", "--output", str(codex_target)]) == 0
    assert json.loads(codex_target.read_text())["unpaired_tool_requests"] == 1

    workbench = tmp_path / "workbench.jsonl"
    workbench.write_text('{"step_id":"route","name":"route_skills"}\n')
    workbench_target = tmp_path / "workbench.json"
    assert main([str(workbench), "--kind", "workbench-trace", "--output", str(workbench_target)]) == 0
    assert json.loads(workbench_target.read_text())["unpaired_tool_requests"] is None
```

- [x] **Step 2: 运行 RED**

Expected: Codex 得 `0`，Workbench 也得 `0`。

- [x] **Step 3: 保留 Codex `item.type` 并加入 kind-aware role**

新增受控 source type 选择器；Codex 有 `item.type` 时使用它。配对函数签名改为：

```python
def _count_unpaired_tool_requests(
    events: Sequence[NormalizedEvent],
    *,
    kind: str,
) -> int | None:
```

`runtime-benchmark` 与 Codex 返回整数，`workbench-trace` 返回 `None`。Codex response terms 必须先匹配，避免 `function_call_output` 被算 request。

- [x] **Step 4: 运行 GREEN 与 normalizer 全文件**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_normalize_harness_trace.py
```

- [x] **Step 5: 提交 kind-aware slice**

```bash
git add intelligence/eval/normalize_harness_trace.py \
  intelligence/tests/test_normalize_harness_trace.py
git commit -m "fix(eval): make tool pairing kind aware"
```

### Task 4: Correlation identity 防止跨请求误配并兼容旧 v2

**Files:**
- Modify: `intelligence/tests/test_normalize_harness_trace.py`
- Modify: `intelligence/eval/normalize_harness_trace.py`

- [x] **Step 1: 写 strict-id 与 legacy RED 测试**

通过 normalizer CLI 构造两个 benchmark case：

```python
matched = [
    {"kind": "tool_request", "payload": {"request_id": "a" * 32}},
    {"kind": "tool_result", "payload": {"request_id": "a" * 32}},
]
mismatched = [
    {"kind": "tool_request", "payload": {"request_id": "b" * 32}},
    {"kind": "tool_result", "payload": {"request_id": "c" * 32}},
]
```

断言 matched 为 0、mismatched 为 1，且 normalized events 显式保留对应 `correlation_id`。另从新 artifact 删除每个 event 的 `correlation_id`，保留 v2 marker，断言 reuse 仍可重算 legacy FIFO。

- [x] **Step 2: 运行 RED**

Expected: mismatched 仍被数量/FIFO 配成 0，event 没有 correlation field。

- [x] **Step 3: 新增 optional correlation field 与窄兼容 loader**

```python
@dataclass(frozen=True)
class NormalizedEvent:
    ...
    correlation_id: str | None
    ...
```

raw normalization 对 benchmark 读取 `request_id`，Codex 读取 `call_id/tool_call_id`，普通 `id` 不作为 correlation。artifact loader 仅允许 `correlation_id` 缺失并注入 `None`；其余 missing/unexpected key 仍拒绝。

配对内部按 `(case_id, correlation_id)` 计数；有 id 的 response 只消费同 id，双方均无 id 才进入 legacy FIFO。

- [x] **Step 4: 锁住 frozen artifact 回归**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_normalize_harness_trace.py \
  -k 'pairing or frozen_finalization or reused_artifact'
```

Expected: frozen T1/T2 仍是 `0/1`。

- [x] **Step 5: 提交 correlation slice**

```bash
git add intelligence/eval/normalize_harness_trace.py \
  intelligence/tests/test_normalize_harness_trace.py
git commit -m "feat(eval): preserve tool request correlation ids"
```

### Task 5: 恢复派生计数 mismatch 的 declared/actual 取证

**Files:**
- Modify: `intelligence/tests/test_normalize_harness_trace.py`
- Modify: `intelligence/eval/normalize_harness_trace.py`

- [x] **Step 1: 写错误文本 RED 测试**

复用现有 tampered artifact，断言：

```python
with pytest.raises(NormalizedArtifactError) as raised:
    main([str(tampered_path), "--compare", str(artifact_path)])
message = str(raised.value)
assert "unpaired_tool_requests=0" in message
assert "recomputed 1" in message
```

- [x] **Step 2: 运行 RED**

Expected: 当前错误缺 declared `=0`。

- [x] **Step 3: 最小修改错误格式**

```python
raise NormalizedArtifactError(
    f"{field}={declared!r} disagrees with recomputed {actual!r}; "
    "the artifact was modified after it was written"
)
```

- [x] **Step 4: 运行 GREEN 并提交**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_normalize_harness_trace.py
git add intelligence/eval/normalize_harness_trace.py \
  intelligence/tests/test_normalize_harness_trace.py
git commit -m "fix(eval): report declared derived counts"
```

### Task 6: 文档口径、验证与分支交付

**Files:**
- Modify: `docs/trace-profile.md`
- Modify: `docs/prediction-ledger.md`
- Modify: `docs/handoffs/2026-08-04b-finalization-handoff.md`
- Modify: `docs/verification/2026-08-04b-finalization.md`
- Modify: `docs/superpowers/plans/2026-08-04-headless-tool-correlation-observability.md`

- [x] **Step 1: 更新观测边界**

明确：

- `unpaired_tool_requests: int | null`；
- benchmark/Codex 的各自词表与 ID/FIFO 强弱语义；
- `0` 不是迟到结果隔离的充分条件；R-10 必须按 request id 分开检查正常
  `tool_result`、handoff 执行层 `tool_error` 与迟到结果；mailbox
  `response_path_conflict` transport 诊断不计入执行终态基数；
- Workbench 无逐工具词表，必须读 `null`；
- R-02 的真 rollout 仍需真实产物结案，本轮 synthetic 只锁行为。

- [x] **Step 2: focused 验证**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_headless_tool_gateway.py \
  intelligence/tests/test_normalize_harness_trace.py \
  intelligence/tests/test_codex_headless_runtime.py \
  intelligence/tests/test_run_agent_runtime_benchmark.py
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m ruff check \
  intelligence/services/headless_tool_gateway.py \
  intelligence/eval/normalize_harness_trace.py \
  intelligence/tests/test_headless_tool_gateway.py \
  intelligence/tests/test_normalize_harness_trace.py
```

- [x] **Step 3: 相关/全量对账**

```bash
env -u FORESIGHT_USERS_DIR -u SUBCONSCIOUS_VAULT -u AGENT_MEMORY_VAULT \
  /Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q
```

若仍有父 revision 已知的两个 `acceptance_board` 确定性失败，记录同名同数；任何新增失败先修复，不把它归为环境噪声。

Result: 最终 clean-host `4211 passed, 3 skipped, 2 failed`；两条失败与父 revision 同名同数。带本机用户目录变量的首轮为 `4199 passed, 3 skipped, 13 failed`，多出的 11 条是既有 userspace/subconscious 环境耦合，不记作产品修复。

- [x] **Step 4: 审计并提交文档**

```bash
git diff --check
git status --short
git diff --name-only HEAD~4..HEAD
git add docs/trace-profile.md docs/prediction-ledger.md \
  docs/handoffs/2026-08-04b-finalization-handoff.md \
  docs/verification/2026-08-04b-finalization.md \
  docs/superpowers/plans/2026-08-04-headless-tool-correlation-observability.md
git commit -m "docs(eval): define correlation-aware pairing contract"
```

- [x] **Step 5: 单独审计 agent-memory 分支**

只读检查 `/Users/a77/agent-memory` 的 branch/upstream、171 个提交的 name/status/stat、危险路径和大文件。代码分支交付不依赖它；没有明确证明安全前不 push 该 memory 分支。

Result: 审计时已变为 `173 ahead / 2 behind`，本地侧 401 个路径、66,378 行新增，并含两个被红线禁止的 `workbench.sqlite3` 与大量完整 run 产物；因此不 push、不设 upstream，也不与本代码分支混合。

- [x] **Step 6: push 当前独立分支**

```bash
git push -u origin fix/headless-tool-correlation-observability
```

不合 main，不跑 live，不开始 R-10。

Result: `fix/headless-tool-correlation-observability` 已设置 upstream 并 push；main、运行服务与 live artifact 均未改动。
