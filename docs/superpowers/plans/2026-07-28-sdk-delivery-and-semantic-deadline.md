# SDK Delivery and Semantic Deadline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve model autonomy while guaranteeing time to deliver an answer once mandatory finance evidence is available, and keep semantic verification inside one bounded retry window.

**Architecture:** `_AgentsRunState` owns model-visible evidence progress and an absolute tool-stage close time; `OpenAIAgentsRuntime` still owns the single SDK request timeout. `EpisodeSemanticVerifier` allocates attempts from one shared deadline and keeps all existing semantic predicates.

**Tech Stack:** Python 3.12, pytest, OpenAI Agents SDK adapter, immutable research contracts, fake-clock boundary tests.

---

### Task 1: Publish mandatory evidence completion through the SDK seam

**Files:**
- Modify: `intelligence/services/openai_agents_runtime.py`
- Test: `intelligence/tests/test_openai_agents_runtime.py`

- [ ] **Step 1: Write the failing public-seam test**

Build a contract with mandatory `market_data` and `financial_data` requirements.
The scripted SDK runner invokes both public tools and independently asserts:

```python
assert first["mandatory_missing_capabilities"] == ["financial_data"]
assert "mandatory_evidence_complete" not in first
assert second["mandatory_missing_capabilities"] == []
assert second["mandatory_evidence_complete"] is True
assert "绑定" in second["finish_hint"]
```

Return terminal JSON binding evidence from both observations, then assert the
public `AgentOutcome` is completed.

- [ ] **Step 2: Run the red test**

```bash
env -u FORESIGHT_USERS_DIR pytest -q intelligence/tests/test_openai_agents_runtime.py -k mandatory_evidence_completion
```

Expected: FAIL because tool results do not publish evidence-plan progress.

- [ ] **Step 3: Implement the minimal progress ledger**

Track successful `ToolSpec.capability` values only when new evidence was
published. Add the exact missing mandatory list to every evidence-bearing tool
result, and add the boolean plus finish hint only when the list becomes empty.
Do not modify `episode_verifier.py`.

- [ ] **Step 4: Run the focused test green and commit**

```bash
env -u FORESIGHT_USERS_DIR pytest -q intelligence/tests/test_openai_agents_runtime.py -k mandatory_evidence_completion
git add intelligence/services/openai_agents_runtime.py intelligence/tests/test_openai_agents_runtime.py
git commit -m "fix: expose mandatory evidence completion to sdk episodes"
```

### Task 2: Reserve the tail of one SDK episode for delivery

**Files:**
- Modify: `intelligence/services/openai_agents_runtime.py`
- Test: `intelligence/tests/test_openai_agents_runtime.py`

- [ ] **Step 1: Write a fake-clock red test through `run()`**

The scripted runner obtains mandatory evidence, advances the boundary clock
past the tool-stage close time, invokes one optional tool, and then returns
valid terminal JSON. Assert:

```python
assert optional["status"] == "closed"
assert optional["error"] == "research_stage_closed"
assert outcome.status == "completed"
assert "research_stage_closed" not in outcome.gaps
```

- [ ] **Step 2: Run red**

```bash
env -u FORESIGHT_USERS_DIR pytest -q intelligence/tests/test_openai_agents_runtime.py -k delivery_reserve_closes_optional_tools
```

Expected: FAIL because tools remain open until the full SDK/root deadline.

- [ ] **Step 3: Implement an absolute SDK tool-stage deadline**

Compute a bounded reserve from the already-bounded SDK timeout:

```python
reserve = min(20.0, max(5.0, runtime_timeout * 0.25), runtime_timeout * 0.5)
tool_seconds = max(0.0, runtime_timeout - reserve)
```

Pass an absolute close time into `_AgentsRunState`. `_reservation_error()`
returns `research_stage_closed` at or after that time. Repair continuations keep
their existing independently bounded delivery behavior.

- [ ] **Step 4: Run all SDK runtime tests and commit**

```bash
env -u FORESIGHT_USERS_DIR pytest -q intelligence/tests/test_openai_agents_runtime.py
git add intelligence/services/openai_agents_runtime.py intelligence/tests/test_openai_agents_runtime.py
git commit -m "fix: reserve sdk episode tail for answer delivery"
```

### Task 3: Bound semantic retries by the shared verifier window

**Files:**
- Modify: `intelligence/services/episode_semantic_verifier.py`
- Test: `intelligence/tests/test_episode_semantic_verifier.py`

- [ ] **Step 1: Add a deadline-allocation red test**

Use a boundary provider that records timeouts, fails first with a typed
transient, and succeeds second. Under a 30-second fake deadline assert there are
at most two attempts, the first does not claim the entire window, the second
has a positive bounded slice, and the final semantic status is passed.

- [ ] **Step 2: Add a repeated-transient red test**

Return typed transient failures repeatedly and assert the verifier stops after
two attempts with the current fail-closed/unavailable classification rather
than requesting a third full timeout.

- [ ] **Step 3: Run red**

```bash
env -u FORESIGHT_USERS_DIR pytest -q intelligence/tests/test_episode_semantic_verifier.py -k shared_semantic_deadline
```

- [ ] **Step 4: Implement one attempt allocator**

Calculate each attempt from `deadline.remaining()` with a minimum retry slice.
Only typed release-safe transient failures admit the second attempt. Keep all
existing malformed/authentication/contract predicates and optional-rejudge
release rules unchanged.

- [ ] **Step 5: Run semantic tests and commit**

```bash
env -u FORESIGHT_USERS_DIR pytest -q intelligence/tests/test_episode_semantic_verifier.py
git add intelligence/services/episode_semantic_verifier.py intelligence/tests/test_episode_semantic_verifier.py
git commit -m "fix: bound semantic retries to shared deadline"
```

### Task 4: Verify once, then freeze a release candidate

**Files:**
- Create: `docs/verification/sdk-delivery-and-semantic-deadline-2026-07-28.md`
- Modify: `.agent-memory/20_projects/finance-workspace-private.md`

- [ ] **Step 1: Run focused and composition suites**

```bash
env -u FORESIGHT_USERS_DIR pytest -q \
  intelligence/tests/test_run_agent_runtime_benchmark.py \
  intelligence/tests/test_episode_protocol.py \
  intelligence/tests/test_episode_tools.py \
  intelligence/tests/test_ask_compose.py \
  intelligence/tests/test_keychain_credentials.py \
  intelligence/tests/test_workbench_api.py
env -u FORESIGHT_USERS_DIR pytest -q intelligence/tests/test_continuous_turn_adapter.py intelligence/tests/test_orchestrator.py
```

- [ ] **Step 2: Run the executable full suite**

```bash
env -u FORESIGHT_USERS_DIR pytest -q intelligence/tests
```

Record sandbox-only socket-bind exclusions separately; do not weaken tests.

- [ ] **Step 3: Review the diff and freeze the revision**

Confirm no secret/database/cache files, no verifier predicate relaxation, and
no question-specific routing. Commit the verification document.

- [ ] **Step 4: Run one live five-case hard gate**

Run the frozen SDK-GPT benchmark exactly once. Only 5/5 completed, useful,
cutoff-correct results authorize proposing a fast-forward of the formal
candidate. Do not merge `main` or switch 8792/8799.
