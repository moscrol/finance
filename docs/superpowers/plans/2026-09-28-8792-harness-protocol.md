# 8792 Harness Protocol Implementation Plan

> **For agentic workers:** Use subagent-driven-development for implementation and sequential specification/quality review. The user has authorized execution; continue between tasks without another approval prompt.

**Goal:** Eliminate contradictory Controller reply contracts and prove existing research seams retain their evidence and recovery behavior.

**Architecture:** One pure reply protocol owns canonical fields, validation and the shared shape instruction. Controller retains policy, route and TaskFrame ownership. Research tooling and correction loops are exercised through their existing entry points.

**Tech Stack:** Python 3.12, pytest, Ruff; use the main checkout's .venv-workbench interpreter without modifying shared dependencies.

## Task 1 — Freeze the failure and unify reply reception

Files: create intelligence/services/controller_protocol.py; modify intelligence/services/turn_controller.py and intelligence/tests/test_turn_controller.py.

- [x] Add a decide_turn regression using a fixed valid six-field reply and a read-only QueryResolution stub; assert one completion call, empty llm_failure_reason, needs_retrieval for the research question, and preservation of TaskFrame required_outputs.
- [x] Add a bad-first/good-second case, reject-both case, legacy five/seven-field cases, invalid types/route/extra fields, and a failed-alignment contamination case. Execute before changes and retain the actual failure output.
- [x] Implement one canonical protocol definition and derive first/retry field descriptions and allowed canonical keys from it. Keep legacy compatibility explicit; never allow the compatibility required_outputs to become task authority.
- [x] Apply semantic supplements only from an accepted reply; if the correction succeeds, align that accepted reply. Preserve error classification, bounded retry and evidence floor.
- [x] Run the new cases and the full Controller/TaskFrame related suites. Commit only owned paths with pathspec.

Behavioral core to retain in the test:

```python
reply = {"route_id": "chat", "confidence": 0.91, "reason": "普通交流",
         "user_goal": "判断产业趋势是否成立", "assumptions": [], "ambiguities": []}
calls = []
def complete(messages):
    calls.append(messages)
    return json.dumps(reply, ensure_ascii=False), object(), ""
decision = decide_turn("帮我判断产业趋势", llm_complete=complete)
assert len(calls) == 1
assert decision.llm_failure_reason == ""
assert decision.needs_retrieval is True
```

Run with the prescribed interpreter: `-m pytest -q intelligence/tests/test_turn_controller.py intelligence/tests/test_task_frame.py` (check exact test file availability before execution). Red is a second call or failed alignment on the old implementation; green must preserve the other assertions.

## Task 2 — Verify research input, capability and correction seams

- [x] Run existing theme snapshot/prefetch tests, tool-menu tests, dataset-registration audit, Controller evidence floor, retrieval-stage transmission, and real-Episode typed-query-error recovery tests.
- [x] Read the actual tests and return paths to distinguish registration from model-visible delivery. Record coverage and failures; do not invent a gap from an empty code map.
- [x] If a related behavior fails, freeze the original expected result and fix the producing boundary. Otherwise retain the implementation and report that these behaviors already exist.
- [x] Re-run the original fixed-reply differential on the completed revision; no real model or production writes are necessary for this causal check.

## Task 3 — Review, validate and deliver

- [x] Update docs/agent-product-door.md with protocol ownership and compatibility limits.
- [x] Independent specification review, then independent quality review of the fixed diff; resolve findings before final acceptance.
- [x] Run appropriate targeted suites and Ruff; prepare full merge gates against a clean commit where resources permit, preserving red receipts and no scope narrowing.
- [x] Record the dependency-doctor drift (httpx 0.25.2 vs lock 0.28.1); do not repair the shared environment or call a drifted environment lock-clean.
- [x] Commit/push the branch and create a reviewable PR. No merge or production switch is included in “执行” because repository instructions require explicit merge confirmation.
- [x] Handoff after actions, recording current commit, tests, independent review, remaining natural-quality evidence and deployment boundary. Do not call the old 38-question score a new result.

Execution evidence and remaining acceptance boundaries: `docs/handoffs/2026-09-28-8792-harness-protocol.md`. Final full-gate status is read from the external `acceptance/result.json` named there; checkboxes do not substitute for a completed passing receipt.
