# Frozen Representative Evaluation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Freeze one Adaptive Finance Agent Runtime revision and evaluate five representative long-tail questions exactly once, with enough diagnostics to distinguish model, provider, retrieval, verifier, and product-projection failures.

**Architecture:** Reuse the existing `run_agent_runtime_benchmark.py` and its provider-neutral `RuntimeArmResult` interface. The tracked nine-case suite remains unchanged; a local ignored five-case projection selects only the release-frontier questions, and live credentials are loaded from macOS Keychain without entering argv, logs, artifacts, or Git. Deterministic regression and a dry run must pass before the revision is frozen; no verifier threshold is changed in response to benchmark results.

**Tech Stack:** Python, pytest, macOS Keychain, existing AgentRuntime adapters, JSON benchmark artifacts under `/Users/a77/.finance-runtime/evals/`.

---

## File structure

- Create `docs/superpowers/plans/2026-07-27-frozen-representative-evaluation.md`: this execution plan.
- Create `/Users/a77/.finance-runtime/evals/adaptive-runtime-five-cases-2026-07-27.json`: ignored local input projected from the tracked runtime cases.
- Create `/Users/a77/.finance-runtime/evals/adaptive-runtime-five-cases-2026-07-27-<revision>.json`: ignored live result artifact.
- Create `docs/verification/adaptive-runtime-representative-evaluation-2026-07-27.md`: bounded verification summary containing no raw prompts, secrets, SQL, physical schema, or private evidence payloads.

## Task 1: Freeze the release input and revision

**Files:**
- Read: `intelligence/tests/fixtures/runtime_backend_cases.json`
- Create: `/Users/a77/.finance-runtime/evals/adaptive-runtime-five-cases-2026-07-27.json`

- [ ] **Step 1: Project exactly five representative cases**

Select these existing cases without changing their questions, cutoffs, budgets, or required outputs:

```text
rebound-duration
ruihuatai-valuation
weekly-market-cause
current-mainline
unfamiliar-methodology
```

This set covers prediction, valuation, causal attribution, current-market judgment, and a non-skill methodology question. It intentionally omits the deterministic technical fast path because that path already has a real UI/SSE acceptance run and is not a long-tail Episode quality test.

- [ ] **Step 2: Run the provider-tolerance and benchmark-contract tests**

Run:

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest \
  intelligence/tests/test_market_news.py \
  intelligence/tests/test_evidence_search.py \
  intelligence/tests/test_finance_query.py \
  intelligence/tests/test_runtime_backend_benchmark.py \
  intelligence/tests/test_run_agent_runtime_benchmark.py -q
```

Expected: all pass.

- [ ] **Step 3: Run one dry benchmark plan**

Run the five-case file with `--dry-run --backend sdk_gpt`. Assert `case_count=5`, every `execution_status=planned`, and every `acceptance_contract_gaps` list is empty.

- [ ] **Step 4: Freeze the exact Git revision**

Record `git rev-parse HEAD` and require `git status --short` to be empty. All live artifacts must record this same revision. Do not edit product code after this point without invalidating the live result.

## Task 2: Run the live release frontier once

**Files:**
- Create: `/Users/a77/.finance-runtime/evals/adaptive-runtime-five-cases-2026-07-27-<revision>.json`

- [ ] **Step 1: Load the saved provider safely**

Enable `FORESIGHT_LLM_KEYCHAIN=on` for the benchmark process and pass `--keychain-user linxiaoqi5111`. Do not print the loaded provider object, inspect another process environment, export the key, or write it to a shell file.

- [ ] **Step 2: Execute the five cases exactly once**

Run `sdk_gpt` against the frozen five-case file, the canonical finance data root, and the local knowledge wiki. If Keychain access or the upstream route is unavailable, record an infrastructure blocker and do not substitute another backend silently.

- [ ] **Step 3: Preserve hard gates**

Do not loosen `summarize_runtime_benchmark`, task-fulfillment, citation, cutoff, invalid-action, or semantic grounding rules. A failed arm remains a result to diagnose, not a reason to change the evaluator.

## Task 3: Summarize acceptance evidence

**Files:**
- Create: `docs/verification/adaptive-runtime-representative-evaluation-2026-07-27.md`

- [ ] **Step 1: Compute bounded metrics**

Report per case and aggregate:

```text
status / structural_status / semantic_status
directness and task alignment
missing_outputs
citations and data cutoff
provider traces and future_of_cutoff count
repair events and recovery outcome
input/output tokens
latency, model calls, tool calls, duplicate queries, invalid actions
control-plane leakage scan
```

- [ ] **Step 2: Judge product quality separately from protocol success**

Read only the five public answers. Classify each as `useful`, `honest_partial`, or `unacceptable`; explain whether the result directly addresses the user's ask. A green protocol with a templated or irrelevant answer is not accepted.

- [ ] **Step 3: Write the release conclusion**

State one of:

```text
ready_for_independent_review
needs_product_fix
blocked_by_external_runtime
```

No canonical 8792 switch, `main` merge, or legacy deletion is part of this plan.

## Alignment checks

- Claude `ALIGNMENT.md` remains supplemental to the approved 17-section design; it does not create another runtime or review harness.
- `partial` must retain `missing_outputs`, so a failed verifier can form a concrete same-Episode `RepairGoal`.
- Per-tool ProviderTrace, token usage, cutoff rejection, and repair provenance remain in the private benchmark artifact, while public SSE receives only the safe progress projection.
- The review harness stays frozen. Independent Claude review happens once after this artifact and verification note exist.
