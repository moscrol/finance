# Runtime Benchmark Production-Parity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the production-candidate benchmark exercise the same Adapter-owned repair and verification path as the Workbench product.

**Architecture:** The benchmark composes its frozen runtime/context/registry through `ContinuousTurnAdapter`; a capture wrapper preserves typed semantic results for the existing arm schema. Timeout identity remains separate from invalid protocol actions.

**Tech Stack:** Python 3.12, pytest, immutable EpisodeSession, ContinuousTurnAdapter, frozen benchmark JSON.

---

### Task 1: Prove the benchmark bypasses delivery repair

**Files:**
- Modify: `intelligence/tests/test_run_agent_runtime_benchmark.py`

- [ ] **Step 1: Add a CLI red test**

Use one research case and a fake runtime whose `start()` returns timeout plus
evidence and whose session `resume()` returns a completed bound answer. Assert
the CLI artifact reports completed, contains one repair, and has no protocol
issues.

- [ ] **Step 2: Run red**

```bash
env -u FORESIGHT_USERS_DIR pytest -q \
  intelligence/tests/test_run_agent_runtime_benchmark.py \
  -k production_adapter_delivery_repair
```

Expected: FAIL because the current benchmark calls `runtime.run()` and never
enters `start()/resume()`.

### Task 2: Compose benchmark arms through the product Adapter

**Files:**
- Modify: `scripts/run_agent_runtime_benchmark.py`
- Test: `intelligence/tests/test_run_agent_runtime_benchmark.py`

- [ ] **Step 1: Add a semantic capture wrapper**

The wrapper delegates `verify(...)`, stores the latest typed outcome, and
proxies provider-attempt accounting. It adds no semantic decisions.

- [ ] **Step 2: Replace direct runtime/verifier calls**

Construct `ContinuousTurnAdapter` in `on` mode with frozen factories, deadline,
tier, backend label, and verification reserve. Call `handle()` and build the
arm from the captured final outcome plus the Adapter's public answer.

- [ ] **Step 3: Run green and commit**

```bash
env -u FORESIGHT_USERS_DIR pytest -q \
  intelligence/tests/test_run_agent_runtime_benchmark.py
git add scripts/run_agent_runtime_benchmark.py intelligence/tests/test_run_agent_runtime_benchmark.py
git commit -m "fix: benchmark production arms through continuous adapter"
```

### Task 3: Keep timeout separate from invalid actions

**Files:**
- Modify: `intelligence/services/openai_agents_runtime.py`
- Test: `intelligence/tests/test_openai_agents_runtime.py`

- [ ] **Step 1: Add a failure-identity red test**

Assert a timed-out outcome has `invalid_actions == 0`, while the existing
invalid-finish regression continues to assert `invalid_actions == 1`.

- [ ] **Step 2: Implement typed invalid-action accounting**

Set invalid actions only for invalid finish/protocol stop reasons. Do not change
timeout status, gaps, stop reason, or repair admission.

- [ ] **Step 3: Run green and commit**

```bash
env -u FORESIGHT_USERS_DIR pytest -q \
  intelligence/tests/test_openai_agents_runtime.py
git add intelligence/services/openai_agents_runtime.py intelligence/tests/test_openai_agents_runtime.py
git commit -m "fix: separate sdk deadlines from invalid actions"
```

### Task 4: Verify and run one frozen live gate

**Files:**
- Create: `docs/verification/runtime-benchmark-production-parity-2026-07-28.md`

- [ ] **Step 1: Run focused Adapter/runtime/benchmark tests**
- [ ] **Step 2: Run the executable full intelligence suite**
- [ ] **Step 3: Review for gate relaxation, duplicate repair, and risk files**
- [ ] **Step 4: Freeze a clean revision and run the five-case live gate once**

Do not merge `main` or switch 8792/8799.
