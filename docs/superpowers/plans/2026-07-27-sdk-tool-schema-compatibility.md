# SDK Tool Schema Compatibility Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: execute inline test-first; do not delegate this single-seam repair.

**Goal:** Let the `sdk_gpt` continuous Episode send FinanceQuery tools through the OpenAI-compatible 57244 gateway without weakening the provider-neutral tool contract.

**Architecture:** Add one recursive compatibility projection in `openai_agents_runtime.py` immediately before `FunctionTool` construction. The projection removes only `uniqueItems` for `sdk_gpt`; registry schemas and local argument validation remain unchanged.

**Tech Stack:** Python 3.12, OpenAI Agents SDK, pytest, FastAPI Conversation E2E.

---

### Task 1: Lock the provider-boundary regression

**Files:**
- Modify: `intelligence/tests/test_openai_agents_runtime.py`

- [ ] **Step 1: Write the failing test**

Add a default-runner test that supplies a nested schema containing
`uniqueItems`, captures `agent.tools[0].params_json_schema`, and asserts:

```python
assert "uniqueItems" not in json.dumps(gpt_schema)
assert '"uniqueItems": true' in json.dumps(glm_schema).lower()
assert source_schema == original_schema
```

- [ ] **Step 2: Run the test to verify RED**

Run:

```bash
.venv-workbench/bin/python -m pytest \
  intelligence/tests/test_openai_agents_runtime.py::test_default_sdk_runner_projects_provider_compatible_tool_schema \
  -q
```

Expected: `sdk_gpt` assertion fails because `uniqueItems` is still present.

### Task 2: Add the minimal SDK projection

**Files:**
- Modify: `intelligence/services/openai_agents_runtime.py`

- [ ] **Step 1: Implement a detached recursive projection**

Add a private helper with this behavior:

```python
def _provider_tool_schema(
    schema: Mapping[str, object], *, backend: SdkBackend
) -> dict[str, object]:
    projected = copy_tool_parameters(schema)
    if backend != "sdk_gpt":
        return projected

    def visit(value: object) -> object:
        if isinstance(value, Mapping):
            return {
                str(key): visit(item)
                for key, item in value.items()
                if key != "uniqueItems"
            }
        if isinstance(value, list):
            return [visit(item) for item in value]
        return value

    result = visit(projected)
    if not isinstance(result, dict):
        raise ValueError("tool schema projection must remain an object")
    return result
```

- [ ] **Step 2: Use the projection at `FunctionTool` construction**

Replace the direct `copy_tool_parameters(...)` call with:

```python
params_json_schema=_provider_tool_schema(
    sdk_tool.parameters,
    backend=request.backend,
),
```

- [ ] **Step 3: Run the RED test and related SDK tests**

Run:

```bash
.venv-workbench/bin/python -m pytest \
  intelligence/tests/test_openai_agents_runtime.py \
  intelligence/tests/test_finance_query.py \
  intelligence/tests/test_continuous_turn_adapter.py \
  -q
```

Expected: all selected tests pass.

- [ ] **Step 4: Run style and diff checks**

```bash
.venv-workbench/bin/python -m ruff check \
  intelligence/services/openai_agents_runtime.py \
  intelligence/tests/test_openai_agents_runtime.py
git diff --check
```

- [ ] **Step 5: Commit the focused repair**

```bash
git add intelligence/services/openai_agents_runtime.py \
  intelligence/tests/test_openai_agents_runtime.py
git commit -m "fix: project sdk tool schema for openai gateways"
```

### Task 3: Verify the real product path

**Files:**
- Update after acceptance: `docs/verification/adaptive-runtime-representative-evaluation-2026-07-27.md`
- Update after acceptance: `docs/verification/adaptive-runtime-completion-audit-2026-07-27.md`

- [ ] **Step 1: Restart only candidate 8799**

Use the same explicit finance/KB/snapshot roots. Do not touch 8792 or `main`.

- [ ] **Step 2: Run `current-mainline` through Conversation messages**

Acceptance: no `sdk_upstream_unavailable`, tool calls are non-zero, date is
2026-07-24, and direct assessment/support/risk outputs are fulfilled or carry a
specific evidence gap.

- [ ] **Step 3: Run `weekly-market-cause` through Conversation messages**

Acceptance: the answer addresses the weekly decline cause, distinguishes
observed market structure from external-catalyst gaps, and has bound evidence.

- [ ] **Step 4: Run the frozen five-case set once**

Run only after both targeted cases pass. Do not run the nine-case development
set.

- [ ] **Step 5: Update verification reports and commit**

Record exact revision, dirty state, run IDs, dates, provider/tool counts,
contract coverage, and any honest partials. Do not claim release green unless
the frozen gate passes.
