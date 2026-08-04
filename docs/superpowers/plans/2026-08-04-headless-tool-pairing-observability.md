# Headless Tool Pairing Observability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 normalized artifact 自动报告未配对 tool request，并让 gateway 原生 request 事件暴露可审计的时间与 root/research 入口余量。

**Architecture:** normalizer 只基于安全的 normalized event identity 按 case 顺序配对 request/result/error，派生一个可重算顶层计数；gateway 在请求进入锁内时冻结一次 deadline 读数并写入事件 payload。两处都只加 telemetry，不改变预算、工具执行或 finalization 控制流。

**Tech Stack:** Python 3.12、pytest、JSON runtime-benchmark artifact、Codex headless mailbox gateway。

---

### Task 1: 单输入 artifact 报告未配对请求

**Files:**
- Modify: `intelligence/tests/test_normalize_harness_trace.py`
- Modify: `intelligence/eval/normalize_harness_trace.py`

- [x] **Step 1: 写 public CLI RED 测试**

在一个 synthetic benchmark 中放三条 case：第一条只有 request，第二条 request→result，第三条 request→error。只断言最终用户可见字段为 1。

```python
def test_runtime_benchmark_artifact_counts_unpaired_tool_requests(tmp_path) -> None:
    source = tmp_path / "runtime-benchmark.json"
    source.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "cases": [
                    {
                        "id": "missing-response",
                        "arms": [{"diagnostics": {"events": [
                            {"sequence": 1, "kind": "tool_request"},
                        ]}}],
                    },
                    {
                        "id": "completed-response",
                        "arms": [{"diagnostics": {"events": [
                            {"sequence": 1, "kind": "tool_request"},
                            {"sequence": 2, "kind": "tool_result"},
                        ]}}],
                    },
                    {
                        "id": "rejected-response",
                        "arms": [{"diagnostics": {"events": [
                            {"sequence": 1, "kind": "tool_request"},
                            {"sequence": 2, "kind": "tool_error"},
                        ]}}],
                    },
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
    assert artifact["unpaired_tool_requests"] == 1
```

- [x] **Step 2: 运行 RED**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_normalize_harness_trace.py::test_runtime_benchmark_artifact_counts_unpaired_tool_requests
```

Expected: `KeyError: 'unpaired_tool_requests'`。

- [x] **Step 3: 写最小配对器并接入 raw build**

在 `normalize_harness_trace.py` 增加纯函数；同 case 的额外 response 不得让 pending 变负。

```python
def _count_unpaired_tool_requests(events: Sequence[NormalizedEvent]) -> int:
    pending_by_case: dict[str | None, int] = {}
    for event in events:
        case_id = event.case_id
        if event.source_event_type == "tool_request":
            pending_by_case[case_id] = pending_by_case.get(case_id, 0) + 1
        elif event.source_event_type in {"tool_result", "tool_error"}:
            pending = pending_by_case.get(case_id, 0)
            if pending > 0:
                pending_by_case[case_id] = pending - 1
    return sum(pending_by_case.values())
```

并在 `_build_side()` 的 payload 写：

```python
"unpaired_tool_requests": _count_unpaired_tool_requests(events),
```

- [x] **Step 4: 运行 GREEN**

重跑 Step 2，Expected: `1 passed`。

- [x] **Step 5: 提交第一片**

```bash
git add intelligence/eval/normalize_harness_trace.py \
  intelligence/tests/test_normalize_harness_trace.py
git commit -m "feat(eval): count unpaired tool requests"
```

### Task 2: Artifact reuse 保持可再入且拒绝伪计数

**Files:**
- Modify: `intelligence/tests/test_normalize_harness_trace.py`
- Modify: `intelligence/eval/normalize_harness_trace.py`

- [x] **Step 1: 写 reuse RED 测试**

旧 v2 artifact 缺字段时必须从 events 重算；已声明但与 events 不同必须 fail loudly。

```python
def test_reused_artifact_recomputes_or_validates_tool_pairing_count(tmp_path) -> None:
    source = tmp_path / "benchmark.json"
    source.write_text(
        json.dumps({
            "schema_version": 1,
            "cases": [{
                "id": "case-1",
                "arms": [{"diagnostics": {"events": [
                    {"sequence": 1, "kind": "tool_request"},
                ]}}],
            }],
        }),
        encoding="utf-8",
    )
    artifact_path = tmp_path / "normalized.json"
    assert main([
        str(source), "--kind", "runtime-benchmark",
        "--output", str(artifact_path),
    ]) == 0
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))

    legacy = dict(artifact)
    legacy.pop("unpaired_tool_requests")
    legacy_path = tmp_path / "legacy.json"
    legacy_path.write_text(json.dumps(legacy), encoding="utf-8")
    compared = tmp_path / "compared.json"
    assert main([
        str(legacy_path), "--compare", str(legacy_path),
        "--output", str(compared),
    ]) == 0
    output = json.loads(compared.read_text(encoding="utf-8"))
    assert output["left"]["unpaired_tool_requests"] == 1

    tampered = dict(artifact, unpaired_tool_requests=0)
    tampered_path = tmp_path / "tampered.json"
    tampered_path.write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(NormalizedArtifactError, match="unpaired_tool_requests"):
        main([str(tampered_path), "--compare", str(artifact_path)])
```

- [x] **Step 2: 运行 RED**

Expected: reused side 缺新字段，或 tampered artifact 未被拒绝。

- [x] **Step 3: 在 loader 复算并验证派生计数**

在 `_load_normalized_artifact()` 完成 event validation 后：

```python
unpaired_tool_requests = _count_unpaired_tool_requests(events)
declared_unpaired = value.get("unpaired_tool_requests")
if declared_unpaired is not None:
    if (
        isinstance(declared_unpaired, bool)
        or not isinstance(declared_unpaired, int)
        or declared_unpaired != unpaired_tool_requests
    ):
        raise NormalizedArtifactError(
            "unpaired_tool_requests disagrees with the normalized events present"
        )
```

reused payload 同样写：

```python
"unpaired_tool_requests": unpaired_tool_requests,
```

- [x] **Step 4: 运行 GREEN 与 normalizer 全文件**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_normalize_harness_trace.py
```

Expected: 全绿。

- [x] **Step 5: 提交第二片**

```bash
git add intelligence/eval/normalize_harness_trace.py \
  intelligence/tests/test_normalize_harness_trace.py
git commit -m "test(eval): validate tool pairing count on reuse"
```

### Task 3: 冻结产物回归与 gateway 请求入口遥测

**Files:**
- Modify: `intelligence/tests/test_normalize_harness_trace.py`
- Modify: `intelligence/tests/test_headless_tool_gateway.py`
- Modify: `intelligence/services/headless_tool_gateway.py`

- [x] **Step 1: 写 T1/T3 frozen artifact RED 测试**

```python
def test_frozen_finalization_artifacts_expose_the_pairing_gap(tmp_path) -> None:
    repo = Path(__file__).resolve().parents[2]
    measurement = repo / "intelligence/eval/measurements/2026-08-04b-finalization"
    observed: list[int] = []
    for name in ("c-long-capped-t1.json", "c-long-capped-t2.json"):
        target = tmp_path / f"{name}.normalized.json"
        assert main([
            str(measurement / name),
            "--kind", "runtime-benchmark",
            "--output", str(target),
        ]) == 0
        artifact = json.loads(target.read_text(encoding="utf-8"))
        observed.append(artifact["unpaired_tool_requests"])
    assert observed == [0, 1]
```

Expected RED: Task 1/2 未覆盖真实 nested benchmark 形状时失败；若已自然转绿，保留为真实回归锁。

- [x] **Step 2: 写 gateway snapshot RED 测试**

```python
def test_gateway_request_records_root_and_research_entry_budget() -> None:
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
    with HeadlessToolGateway(registry=_registry([]), context=context) as gateway:
        gateway.call("market_data", "市场")
        request = gateway.snapshot().events[0]

    assert request.kind == "tool_request"
    assert request.payload["remaining_root_seconds_at_entry"] == 70.0
    assert request.payload["remaining_research_seconds_at_entry"] == 40.0
    datetime.fromisoformat(
        str(request.payload["timestamp"]).replace("Z", "+00:00")
    )
```

- [x] **Step 3: 运行 gateway RED**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_headless_tool_gateway.py::test_gateway_request_records_root_and_research_entry_budget
```

Expected: request payload 缺三个新字段。

- [x] **Step 4: 在真实 request event 构造点冻结遥测**

```python
remaining_root_seconds = max(0.0, self._context.deadline.remaining())
remaining_research_seconds = self._context.deadline.stage_timeout(
    remaining_root_seconds
)
request_event = self._add_event(
    "tool_request",
    {
        "tool": name,
        "query": str(raw_query or ""),
        "timestamp": _utc_timestamp(),
        "remaining_root_seconds_at_entry": round(remaining_root_seconds, 3),
        "remaining_research_seconds_at_entry": round(
            remaining_research_seconds, 3
        ),
    },
)
```

- [x] **Step 5: 运行 GREEN 与两文件回归**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_headless_tool_gateway.py \
  intelligence/tests/test_normalize_harness_trace.py
```

Expected: 全绿；不跑 live。

- [x] **Step 6: 提交第三片**

```bash
git add intelligence/services/headless_tool_gateway.py \
  intelligence/tests/test_headless_tool_gateway.py \
  intelligence/tests/test_normalize_harness_trace.py
git commit -m "feat(runtime): timestamp headless tool request entry"
```

### Task 4: 修正文档口径并冻结 R-10 主门

**Files:**
- Modify: `docs/trace-profile.md`
- Modify: `docs/verification/2026-08-04b-finalization.md`
- Modify: `docs/handoffs/2026-08-04b-finalization-handoff.md`
- Modify: `docs/prediction-ledger.md`
- Modify: `docs/superpowers/plans/2026-08-04-headless-tool-pairing-observability.md`

- [x] **Step 1: 删除 §8 陈旧的 1/3 结论**

保留 `configure → intent → plan = 3/3`；从缺口表删除 codex configure/plan 两行，并把底部验收状态改成 3/3 已达标。不得保留新旧两套数字。

- [x] **Step 2: 加入单次 live 方差字段陷阱**

记录同 profile 的 `59da8acf → 84c1eb73`：weekly 从 `headless_protocol_rejected / 144.7s / 4 calls` 翻为 `model_finish / 74.1s / 6 calls`。明确 `finalization=0`、request/response 配对属于结构读数；单次 stop/latency 不能叫无回归。

- [x] **Step 3: 修正 acceptance 两红分类**

把“宿主环境基线”改为“父 revision 已存在的确定性 CLI contract/test drift”；保留“不是本轮回归”，但不再归为环境噪声。handoff 的 13 红拆成 11 个 userspace/subconscious 环境耦合 + 2 个 acceptance contract drift。

- [x] **Step 4: 更新 R-10**

主判据改为离线 deterministic slow-tool：配对 count=0、阈值处 finalization、late result 不入 episode。单次 live 只作最后确认，不能单独 confirmed。

- [x] **Step 5: 提交文档纠错**

```bash
git add docs/trace-profile.md \
  docs/verification/2026-08-04b-finalization.md \
  docs/handoffs/2026-08-04b-finalization-handoff.md \
  docs/prediction-ledger.md \
  docs/superpowers/plans/2026-08-04-headless-tool-pairing-observability.md
git commit -m "docs(eval): correct finalization observability contracts"
```

### Task 5: 验证、风险扫描与 push

**Files:**
- Verify only; no additional production files.

执行前发现 `eval/budget-calibration` 并发前进到 `9dd30c2e`；本分支已重放到该基线，
保留其 normalized artifact 逐字段/脱敏硬化，并把新配对计数纳入同一派生字段校验。

- [x] **Step 1: 运行 focused suite 与 Ruff**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_normalize_harness_trace.py \
  intelligence/tests/test_headless_tool_gateway.py \
  intelligence/tests/test_codex_headless_runtime.py \
  intelligence/tests/test_run_agent_runtime_benchmark.py

/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m ruff check \
  intelligence/eval/normalize_harness_trace.py \
  intelligence/services/headless_tool_gateway.py \
  intelligence/tests/test_normalize_harness_trace.py \
  intelligence/tests/test_headless_tool_gateway.py
```

Expected: 新增四测试后约 `101 passed / 1 skipped`，以实际收集数为准；Ruff 0。

Observed（重放 `9dd30c2e` 后）：`104 passed, 1 skipped`；Ruff 0。

- [x] **Step 2: 运行全量并分账**

```bash
env -u FORESIGHT_USERS_DIR \
  /Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests
```

Expected: 两个已知 `test_acceptance_board` deterministic failures 仍可能存在；它们不是宿主环境红，也不是本轮回归。任何新增失败先归因。

Observed：`2 failed, 3711 passed, 2 skipped`；失败名称与父 revision 基线完全一致，
没有本轮新增红。

- [x] **Step 3: 风险扫描**

```bash
git diff --check
git diff 7b87d900 -- \
  intelligence/services/research_contract.py \
  intelligence/eval/runtime_backend_benchmark.py
git status --short
git branch --show-current
```

Expected: 预算/profile 文件零 diff；分支 `fix/headless-tool-pairing-observability`；无 `.env*`、密钥、数据库、PDF、压缩包或缓存。

- [x] **Step 4: push 独立分支**

```bash
git push -u origin fix/headless-tool-pairing-observability
```

不合并 main，不运行 live canary。
