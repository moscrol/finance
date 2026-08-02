# Runtime Budget and Cutoff Seam Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore useful continuous-agent finance answers by fixing shared budget, cutoff, as-of retrieval, historical authorization, and Keychain seams without adding question-specific routes.

**Architecture:** Keep `ResearchRunContext.information_cutoff` as the single truth source. Composition roots choose backend-specific reserve policy, structured providers select data at or before the cutoff, and `TaskFrame` alone authorizes historical retrieval. Keychain stays behind its existing backend interface but uses native Security.framework reads.

**Tech Stack:** Python 3.12, pytest, DuckDB, ctypes/CoreFoundation/Security.framework, OpenAI Agents runtime adapters.

---

### Task 1: Separate SDK and GLM reserve policies

**Files:**
- Modify: `scripts/run_agent_runtime_benchmark.py`
- Modify: `intelligence/api/app.py`
- Test: `intelligence/tests/test_run_agent_runtime_benchmark.py`
- Test: `intelligence/tests/test_workbench_api.py`

- [ ] **Step 1: Write the failing benchmark test**

Add a test that builds a standard `sdk_gpt` context and independently asserts
`deadline.synthesis_reserve == 30.0`, `deadline.stage_timeout(90) > 59`, and
`root_budget.initial_seconds == 60.0`. Keep the existing continuous-GLM test.

- [ ] **Step 2: Run the red test**

Run:

```bash
pytest -q intelligence/tests/test_run_agent_runtime_benchmark.py -k 'sdk_gpt and reserve'
```

Expected: FAIL because the SDK ledger has only 30 seconds.

- [ ] **Step 3: Implement the backend reserve selector**

Use one helper in the benchmark:

```python
def _backend_synthesis_reserve(*, backend: str, case, control) -> float:
    if backend == "continuous_glm":
        return GLMAgentRuntime.synthesis_reserve_for_task(
            tier=case.tier,
            question_type=control.task_frame.question_type,
        )
    policy = ResearchPolicy.for_tier(case.tier)
    return min(policy.total_seconds * 0.4, max(policy.synthesis_reserve, 30.0))
```

At the API composition root pass the GLM callback only when
`selection.name == "continuous_glm"`; pass an explicit zero inner-reserve
callback for SDK/headless runtimes because the Adapter already holds the outer
semantic-verifier reserve.

- [ ] **Step 4: Run focused tests and commit**

```bash
pytest -q intelligence/tests/test_run_agent_runtime_benchmark.py intelligence/tests/test_workbench_api.py -k 'reserve or production_adapter'
git add scripts/run_agent_runtime_benchmark.py intelligence/api/app.py intelligence/tests/test_run_agent_runtime_benchmark.py intelligence/tests/test_workbench_api.py
git commit -m "fix: separate sdk and glm runtime reserves"
```

### Task 2: Serialize the immutable cutoff

**Files:**
- Modify: `intelligence/services/episode_protocol.py`
- Test: `intelligence/tests/test_episode_protocol.py`

- [ ] **Step 1: Extend the protocol test**

Assert:

```python
assert task_input["information_cutoff"] == context.information_cutoff.to_dict()
assert "information_cutoff" in task_input["date_rule"]
```

- [ ] **Step 2: Run red, implement, and run green**

Add `information_cutoff` to the JSON object and state that it is the hard upper
bound for every query and citation.

```bash
pytest -q intelligence/tests/test_episode_protocol.py::test_protocol_builds_task_bound_instructions_and_input
git add intelligence/services/episode_protocol.py intelligence/tests/test_episode_protocol.py
git commit -m "fix: expose immutable cutoff to agent episodes"
```

### Task 3: Select structured data at or before cutoff

**Files:**
- Modify: `intelligence/services/ask_blocks.py`
- Modify: `intelligence/services/episode_tools.py`
- Test: `intelligence/tests/test_ask_compose.py`
- Test: `intelligence/tests/test_episode_tools.py`

- [ ] **Step 1: Add frozen two-date fixtures**

Create temporary DuckDB fixtures containing 2026-07-24 and 2026-07-27 rows.
Assert optional `as_of="2026-07-24"` returns blocks and evidence dated 7/24 for
market overview, cause window, and mainline context.

- [ ] **Step 2: Run the red tests**

```bash
pytest -q intelligence/tests/test_ask_compose.py intelligence/tests/test_episode_tools.py -k 'cutoff or as_of or frozen'
```

Expected: the builders select 7/27 and the episode filter removes them.

- [ ] **Step 3: Implement optional as-of selection**

Add optional keyword-only `as_of` parameters. Resolve the selected date with
parameterized SQL equivalent to:

```sql
select max(trade_date)
from fact_market_daily
where (? is null or trade_date <= ?)
```

Use that selected date in every market/theme/sector query. In
`build_episode_registry`, compute `structured_source_date` using the freshness
floor and pass it into `_market_block` and the mainline builder.

- [ ] **Step 4: Add valuation cutoff fallback**

When a fetched valuation snapshot has `source_date > as_of`, discard it. Build
a local target anchor from the latest `fact_sector_stock_daily` row at or
before `as_of`, using `total_mcap_yi`, `price`, and the real trade date. Keep
PE/PB missing rather than relabeling the future snapshot.

- [ ] **Step 5: Run green and commit**

```bash
pytest -q intelligence/tests/test_ask_compose.py intelligence/tests/test_episode_tools.py intelligence/tests/test_valuation_estimate.py
git add intelligence/services/ask_blocks.py intelligence/services/episode_tools.py intelligence/tests/test_ask_compose.py intelligence/tests/test_episode_tools.py
git commit -m "fix: query structured evidence at information cutoff"
```

### Task 4: Let only the user task authorize history

**Files:**
- Modify: `intelligence/services/episode_tools.py`
- Test: `intelligence/tests/test_episode_tools.py`
- Modify: `docs/superpowers/specs/2026-07-27-current-market-freshness-contract-design.md`

- [ ] **Step 1: Replace the obsolete acceptance test**

For `_market_forecast_frame()`, a model `time_range` ending 2025-06-30 must
return no evidence and trace detail `historical_window_not_authorized_by_task`.
For `_historical_market_cause_frame()`, the same typed query remains successful.

- [ ] **Step 2: Run red**

```bash
pytest -q intelligence/tests/test_episode_tools.py -k 'historical_finance_query'
```

- [ ] **Step 3: Implement task-owned authorization**

Add a pure helper that authorizes history only when the frame contains an
explicit historical date/window or dated-review intent. Before calling
`FinanceQuery.run`, reject an earlier model range on current tasks and return a
retryable tool result pointing to the immutable floor.

- [ ] **Step 4: Amend the freshness design and commit**

Replace “the model explicitly requested” with “the user task explicitly
authorized”. Then run the complete `test_episode_tools.py` file and commit.

### Task 5: Read Keychain through Security.framework

**Files:**
- Modify: `intelligence/services/keychain_credentials.py`
- Test: `intelligence/tests/test_keychain_credentials.py`

- [ ] **Step 1: Replace the subprocess timeout test**

Use fake CoreFoundation/Security adapters to make `SecItemCopyMatching` return a
known `CFData` payload. Assert `load()` returns the exact bytes, missing item
returns `None`, refs are released, and `subprocess.run` is never called.

- [ ] **Step 2: Run red**

```bash
pytest -q intelligence/tests/test_keychain_credentials.py
```

- [ ] **Step 3: Implement native load**

Build a query with class/service/account, `kSecReturnData=true`, and
`kSecMatchLimitOne`; call `SecItemCopyMatching`, copy bytes with
`CFDataGetLength`/`CFDataGetBytePtr`, append the result ref to the release list,
and preserve sanitized errors.

- [ ] **Step 4: Run green and commit**

```bash
pytest -q intelligence/tests/test_keychain_credentials.py intelligence/tests/test_llm_settings.py
git add intelligence/services/keychain_credentials.py intelligence/tests/test_keychain_credentials.py
git commit -m "fix: load saved provider with native keychain api"
```

### Task 6: Verify without repeated live evaluation

**Files:**
- Modify: `docs/handoffs/2026-07-27-runtime-seam-hardening-v2.md`

- [ ] **Step 1: Run deterministic replay and focused suites**

```bash
pytest -q intelligence/tests/test_run_agent_runtime_benchmark.py intelligence/tests/test_episode_protocol.py intelligence/tests/test_episode_tools.py intelligence/tests/test_ask_compose.py intelligence/tests/test_keychain_credentials.py intelligence/tests/test_workbench_api.py
```

- [ ] **Step 2: Run adapter/orchestrator and full suites**

```bash
pytest -q intelligence/tests/test_continuous_turn_adapter.py intelligence/tests/test_orchestrator.py
pytest -q intelligence/tests
```

- [ ] **Step 3: Freeze a clean revision and prepare review**

Record revision, dirty state, exact commands, known baseline failures, and the
five fixed invariants in the handoff. Run an independent two-axis review.

- [ ] **Step 4: Run one live benchmark only after all offline gates pass**

Use the frozen five-case input and SDK-GPT backend. Do not switch 8799/8792 or
merge `main` unless the hard gate and all five useful-answer checks pass.
