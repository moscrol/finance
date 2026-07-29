# Same-Fixture Five-Case Headless Control Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce one immutable five-case profile-D Codex-headless baseline from the sealed instruction/PIT fixture with fixed candidate/published answer projections and no external network tools.

**Architecture:** The benchmark loads and validates the sealed fixture receipt before constructing any runtime. A fixture policy reuses the existing `ResearchToolRegistry` and mailbox gateway while disabling network-backed news/web/valuation fetches for both future arms. `RuntimeArmResult` records the raw episode draft separately from the common semantic-publication answer and projects deterministic sentence claims plus exact evidence sources.

**Tech Stack:** Python 3.12, existing Codex headless subprocess/mailbox transport, typed research registry, runtime benchmark dataclasses, semantic verifier, pytest, Ruff.

---

## File map

- Modify `intelligence/services/episode_tools.py`: injectable fixture policy; no network-backed runners in sealed mode.
- Modify `intelligence/services/codex_headless_runtime.py`: require subprocess/mailbox and sanitized child environment for sealed mode.
- Modify `intelligence/eval/runtime_backend_benchmark.py`: candidate/published answers, normalized claims/sources, fixture provenance.
- Modify `scripts/run_agent_runtime_benchmark.py`: `--ceiling-fixture-receipt`, five-case D preconditions, immutable projection hashes.
- Modify tests in `test_headless_tool_gateway.py`, `test_codex_headless_runtime.py`, `test_runtime_backend_benchmark.py`, and `test_run_agent_runtime_benchmark.py`.

### Task 1: Add a fail-closed sealed-fixture tool policy

**Files:**
- Modify: `intelligence/services/episode_tools.py`
- Test: `intelligence/tests/test_episode_tools.py`

- [x] **Step 1: Write a failing no-network registry test**

```python
def test_sealed_fixture_registry_never_builds_network_runners(
    monkeypatch, tmp_path, frame, context
):
    monkeypatch.setattr(web_research, "fetch_web_search", unexpected_call)
    monkeypatch.setattr(market_news, "fetch_eastmoney_news_result", unexpected_call)
    monkeypatch.setattr(valuation_estimate, "fetch_eastmoney_snapshot", unexpected_call)
    registry = build_episode_registry(
        frame,
        context,
        finance_root=tmp_path / "finance",
        knowledge_wiki=tmp_path / "wiki",
        fixture_policy=SealedFixturePolicy(),
    )
    assert "web_search" not in registry.names
    assert "news_search" not in registry.names
```

- [x] **Step 2: Implement `SealedFixturePolicy`**

```python
@dataclass(frozen=True)
class SealedFixturePolicy:
    external_search_enabled: bool = False
    external_valuation_enabled: bool = False
    external_financials_enabled: bool = False
    require_fresh_kb: bool = True
```

`build_episode_registry()` omits network-backed web/news specs and injects local-only valuation/financial fetchers. Missing external causal evidence remains a typed gap; no hidden fallback is allowed.

- [x] **Step 3: Prove the allowed tool surface is stable**

For the five frozen frames, snapshot exact authorized names from the sealed fixture. The manifest records the per-case list and hash; a later App Server broker must reuse it byte-for-byte.

- [x] **Step 4: Run tests and commit**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest intelligence/tests/test_episode_tools.py -q
git add intelligence/services/episode_tools.py intelligence/tests/test_episode_tools.py
git commit -m "feat: add sealed fixture tool policy"
```

### Task 2: Enforce subprocess mailbox and remove child secrets

**Files:**
- Modify: `intelligence/services/codex_headless_runtime.py`
- Modify: `intelligence/services/headless_tool_gateway.py`
- Test: `intelligence/tests/test_codex_headless_runtime.py`
- Test: `intelligence/tests/test_headless_tool_gateway.py`

- [x] **Step 1: Write failing transport/environment tests**

Assert sealed mode rejects `local_exec`, uses gateway transport `mailbox`, passes only `FINANCE_TOOL_MAILBOX` plus explicit non-secret variables to the child shell, excludes `OPENAI_API_KEY` from command-execution environment while keeping it available to the parent Codex process, and configures `sandbox_workspace_write.network_access=false` for every command child.

- [x] **Step 2: Implement a two-scope environment**

```python
@dataclass(frozen=True)
class HeadlessEnvironment:
    parent: Mapping[str, str]
    command_child_allowlist: tuple[str, ...]
```

The parent receives `OPENAI_API_KEY`; the generated Codex config sets shell environment inheritance to the explicit allowlist, omits the key, and sets command-child `networkAccess=false`. The finance wrapper uses mailbox files, not TCP/Unix sockets.

- [x] **Step 3: Add network and IPC negative controls**

Run command children that attempt a public TCP connection, `127.0.0.1`, and a non-allowlisted Unix socket. All must receive a sandbox denial. If the denial cannot be observed, sealed mode returns `isolation_unproven` before the benchmark case.

- [x] **Step 4: Add mailbox permission and tamper tests**

Require the mailbox root and `requests/`/`responses/` directories to be owned by the current uid, non-symlinks, and mode `0700`. Both wrapper request creation and gateway response creation use atomic `O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW` semantics; a pre-existing request or response path fails closed. Also reject oversized requests and paths outside the per-case mailbox. Record request/result hashes for fixture provenance.

- [x] **Step 5: Run tests and commit**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest intelligence/tests/test_codex_headless_runtime.py intelligence/tests/test_headless_tool_gateway.py -q
git add intelligence/services/codex_headless_runtime.py intelligence/services/headless_tool_gateway.py intelligence/tests/test_codex_headless_runtime.py intelligence/tests/test_headless_tool_gateway.py
git commit -m "feat: isolate sealed headless mailbox"
```

### Task 3: Separate candidate and published projections

**Files:**
- Modify: `intelligence/eval/runtime_backend_benchmark.py`
- Modify: `scripts/run_agent_runtime_benchmark.py`
- Test: `intelligence/tests/test_runtime_backend_benchmark.py`
- Test: `intelligence/tests/test_run_agent_runtime_benchmark.py`

- [x] **Step 1: Write failing round-trip tests**

```python
arm = replace(
    _arm(),
    candidate_answer="原始研究草稿。",
    published_answer="语义门后的公开答案。",
    claims=(RuntimeClaim("C1", 0, 10, "语义门后的公开答案。", False, ("E1",)),),
    sources=(RuntimeSource("E1", "market_data", "hash", "2026-07-24"),),
)
assert RuntimeArmResult.from_dict(arm.to_dict()) == arm
```

- [x] **Step 2: Add frozen `RuntimeClaim` and `RuntimeSource` dataclasses**

Validate Unicode code-point spans against `published_answer`, unique IDs, existing source IDs, 64-hex hashes, cutoff dates, and no absolute paths.

- [x] **Step 3: Populate both answers from the existing semantic seam**

Use `final_outcome.draft` as `candidate_answer` and `semantic.public_answer` as `published_answer`. Keep legacy `answer` as an alias of `published_answer` for backward compatibility and reject divergence.

- [x] **Step 4: Project claims/sources deterministically**

Sources come from `final_outcome.evidence` and exact content hashes. Claims are sentence spans over the published answer; source IDs are the union of evidence hashes from fulfilled output bindings, and a material numeric sentence with no joined source fails the arm.

- [x] **Step 5: Run tests and commit**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest intelligence/tests/test_runtime_backend_benchmark.py intelligence/tests/test_run_agent_runtime_benchmark.py -q
git add intelligence/eval/runtime_backend_benchmark.py scripts/run_agent_runtime_benchmark.py intelligence/tests/test_runtime_backend_benchmark.py intelligence/tests/test_run_agent_runtime_benchmark.py
git commit -m "feat: seal benchmark answer projections"
```

### Task 4: Bind the benchmark to the sealed fixture

**Files:**
- Modify: `scripts/run_agent_runtime_benchmark.py`
- Test: `intelligence/tests/test_run_agent_runtime_benchmark.py`

- [ ] **Step 1: Write fail-closed fixture tests**

Reject missing receipt, self-hash mismatch, unsealed status, changed instruction/PIT hashes, wrong cutoff, non-subprocess transport, a case subset other than all five, a profile other than D, and source-dirty execution.

- [ ] **Step 2: Add `--ceiling-fixture-receipt`**

The runner reads `/Users/a77/.finance-runtime/app-server-ceiling/2026-07-24/sealed-fixture.json`, resolves the relative fixture directory, revalidates the target manifest, and uses only its finance/Wiki/index/instruction paths.

- [ ] **Step 3: Pin five-case execution and projection hashes**

Require exactly `rebound-duration`, `ruihuatai-valuation`, `weekly-market-cause`, `current-mainline`, and `unfamiliar-methodology`; profile `d_long_expanded`; 180 seconds; model `gpt-5.6-sol`; reasoning medium; external tools disabled. Every case stores the JSON pointer and SHA-256 of its blind `published_answer/claims/sources` projection.

- [ ] **Step 4: Add fixture/tool/projection provenance to the top-level artifact**

Record fixture manifest hash, instruction export hash, finance DB hash, Wiki/index hash, tool-surface hash, parent/child environment policy hash, and no-live-root assertion. Never record the API key.

- [ ] **Step 5: Run tests and commit**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest intelligence/tests/test_run_agent_runtime_benchmark.py intelligence/tests/test_runtime_backend_benchmark.py -q
git add scripts/run_agent_runtime_benchmark.py intelligence/tests/test_run_agent_runtime_benchmark.py
git commit -m "feat: bind headless control to sealed fixture"
```

### Task 5: Preregister and run the five-case profile-D control

**Files:**
- Create: `docs/verification/headless-five-case-same-fixture-preregistration-2026-07-29.md`
- Create: `docs/verification/headless-five-case-same-fixture-result-2026-07-29.md`
- Private artifact: `/Users/a77/.finance-runtime/evals/headless-five-case-same-fixture-d-2026-07-29.json`

- [ ] **Step 1: Commit preregistration before execution**

Pin source revision, clean tree, question hash, sealed fixture receipt/hash, tool-surface hash, subprocess/mailbox transport, environment-only API-key auth, model, reasoning, profile D, output path, five JSON pointers, and validity rule `max_observed_tool_calls >= 7`.

- [ ] **Step 2: Run one dry-run and inspect only contract/provenance**

```bash
OPENAI_API_KEY="${OPENAI_API_KEY:?missing}" PYTHONDONTWRITEBYTECODE=1 /Users/a77/finance-workspace-private/.venv-workbench/bin/python scripts/run_agent_runtime_benchmark.py --dry-run --backend codex_headless --headless-budget-profile d_long_expanded --case rebound-duration --case ruihuatai-valuation --case weekly-market-cause --case current-mainline --case unfamiliar-methodology --questions-file /Users/a77/.finance-runtime/evals/adaptive-runtime-five-cases-2026-07-27.json --ceiling-fixture-receipt /Users/a77/.finance-runtime/app-server-ceiling/2026-07-24/sealed-fixture.json --output /Users/a77/.finance-runtime/evals/headless-five-case-same-fixture-d-dry-run-2026-07-29.json
```

- [ ] **Step 3: Run the live five cases once**

Use the same command without `--dry-run` and write `/Users/a77/.finance-runtime/evals/headless-five-case-same-fixture-d-2026-07-29.json`. Do not inspect answers between cases.

- [ ] **Step 4: Validate and publish the bounded result receipt**

Require five cases exactly once, source clean, all hashes unchanged, no future dates, no external tool calls, all blind projection hashes valid, and at least one case with seven calls. Record truth/operational status without claiming App Server eligibility.

- [ ] **Step 5: Commit**

```bash
git add docs/verification/headless-five-case-same-fixture-preregistration-2026-07-29.md docs/verification/headless-five-case-same-fixture-result-2026-07-29.md
git commit -m "docs: seal five-case headless control"
```

### Task 6: Regression and boundary audit

- [ ] **Step 1: Run focused runtime tests and Ruff**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest intelligence/tests/test_episode_tools.py intelligence/tests/test_headless_tool_gateway.py intelligence/tests/test_codex_headless_runtime.py intelligence/tests/test_runtime_backend_benchmark.py intelligence/tests/test_run_agent_runtime_benchmark.py -q
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m ruff check intelligence/services/episode_tools.py intelligence/services/headless_tool_gateway.py intelligence/services/codex_headless_runtime.py intelligence/eval/runtime_backend_benchmark.py scripts/run_agent_runtime_benchmark.py
git diff --check
```

- [ ] **Step 2: Run proportional full regression**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest intelligence/tests -q
```

Classify only reproduced environment-baseline failures; do not relabel new failures.

- [ ] **Step 3: Update canonical handoff and complete this plan**

Record the sealed fixture/control hashes, valid/invalid result, current App Server identity blocker, and unchanged `main`/8792/KB boundaries. Then mark every checkbox complete and commit.
