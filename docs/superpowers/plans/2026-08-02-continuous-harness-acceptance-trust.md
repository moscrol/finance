# Continuous Harness Acceptance Trust Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Continuous Harness acceptance prove the exact runtime, execution path, attempt, TaskFrame, cutoff, and Episode artifact that produced every turn, then run a clean Cockpit-backed baseline without touching production 8792.

**Architecture:** Add a process identity projection and an append-only per-Run attempt ledger, bind the orchestrator's selected execution path to that ledger, and make the acceptance client fail closed against an explicit execution-contract overlay. Reuse the existing `sdk_gpt` Responses adapter for Cockpit, and isolate live execution behind a runner that verifies a clean checkout, unused port, singleton provider chain, and exact health identity before spending model calls.

**Tech Stack:** Python 3.12, FastAPI, OpenAI Agents SDK, OpenAI Responses-compatible Cockpit API, JSON/JSONL, pytest, urllib/subprocess.

---

## File map

- Create `intelligence/services/execution_provenance.py`: stable execution-path types, process identity, attempt event validation, and safe projections.
- Modify `intelligence/services/runtime_provenance.py`: actual Python import root and runtime instance identity.
- Modify `intelligence/services/agent_runtime_factory.py`: non-secret provider protocol/label/endpoint fingerprint and provider-chain count.
- Modify `intelligence/services/run_store.py`: append/read the canonical `attempts.jsonl` ledger.
- Modify `intelligence/services/conversation_orchestrator.py`: bind the observed path, owner, contributors, TaskFrame, and cutoff.
- Modify `intelligence/api/app.py`: compose process identity into workers, finish attempts with artifact receipts, and expose a safe provenance endpoint.
- Create `intelligence/eval/cases/acceptance_execution_contracts.json`: explicit expected path for all 28 frozen cases.
- Modify `intelligence/eval/acceptance.py`: strict structured preflight, exact path/receipt checks, and true multi-turn execution.
- Create `scripts/run_continuous_cockpit_acceptance.py`: secret-safe Cockpit smoke, isolated server lifecycle, canary, and full-suite runner.
- Modify focused tests under `intelligence/tests/` for every new contract.

## Task 1: Process and provider identity

**Files:**

- Modify: `intelligence/services/runtime_provenance.py`
- Modify: `intelligence/services/agent_runtime_factory.py`
- Test: `intelligence/tests/test_runtime_provenance.py`
- Test: `intelligence/tests/test_agent_runtime_factory.py`
- Test: `intelligence/tests/test_workbench_api.py`

- [ ] **Step 1: Write failing import-root and runtime-instance tests**

Add assertions equivalent to:

```python
def test_runtime_provenance_reports_actual_import_root() -> None:
    payload = build_runtime_provenance(Path(__file__).resolve().parents[2])
    import intelligence

    assert payload["import_root"] == str(
        Path(intelligence.__file__).resolve().parents[1]
    )
    assert payload["runtime_instance_id"].startswith("runtime_")


def test_runtime_instance_id_can_be_frozen_for_one_app() -> None:
    payload = build_runtime_provenance(
        Path(__file__).resolve().parents[2],
        runtime_instance_id="runtime-test",
    )
    assert payload["runtime_instance_id"] == "runtime-test"
```

- [ ] **Step 2: Write failing provider identity tests**

Cover `sdk_gpt` with Cockpit-compatible environment metadata:

```python
def test_sdk_gpt_readiness_exposes_non_secret_cockpit_identity(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "never-print")
    monkeypatch.setenv("OPENAI_BASE_URL", "http://127.0.0.1:57244/v1")
    monkeypatch.setenv("OPENAI_AGENT_MODEL", "gpt-5.6-sol")
    monkeypatch.setenv("AGENT_RUNTIME_PROVIDER_LABEL", "cockpit_local")

    readiness = runtime_backend_readiness(
        resolve_runtime_backend("sdk_gpt"),
        provider_chain_size=1,
    )

    assert readiness.provider_label == "cockpit_local"
    assert readiness.provider_protocol == "openai_responses"
    assert readiness.provider_chain_size == 1
    assert len(readiness.endpoint_fingerprint) == 64
    assert "never-print" not in json.dumps(readiness.to_dict())
    assert "57244" not in json.dumps(readiness.to_dict())
```

- [ ] **Step 3: Run the new tests and verify they fail**

Run:

```bash
FINANCE_WS=/Users/a77/finance-workspace-private \
  /Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_runtime_provenance.py \
  intelligence/tests/test_agent_runtime_factory.py \
  intelligence/tests/test_workbench_api.py -k 'runtime_provenance or runtime_instance or cockpit_identity'
```

Expected: failures for missing `import_root`, `runtime_instance_id`, and provider identity fields.

- [ ] **Step 4: Implement process identity**

Change `build_runtime_provenance` to accept a fixed instance ID and derive the import root from the imported package:

```python
from uuid import uuid4
import intelligence


def build_runtime_provenance(
    code_root: str | Path,
    *,
    runtime_instance_id: str | None = None,
) -> dict[str, object]:
    root = Path(code_root).expanduser().resolve()
    import_root = Path(intelligence.__file__).resolve().parents[1]
    revision = _git_output(root, "rev-parse", "HEAD")
    dirty = bool(_git_output(root, "status", "--porcelain"))
    dependencies = _dependency_versions()
    fingerprint_payload = "\n".join(
        f"{name}={version}" for name, version in sorted(dependencies.items())
    ).encode("utf-8")
    return {
        "runtime_instance_id": runtime_instance_id or f"runtime_{uuid4().hex}",
        "source_revision": revision or "unknown",
        "source_dirty": dirty,
        "code_root": str(root),
        "import_root": str(import_root),
        "python_executable": str(Path(sys.executable).resolve()),
        "python_version": platform.python_version(),
        "python_prefix": str(Path(sys.prefix).resolve()),
        "dependency_fingerprint": hashlib.sha256(
            fingerprint_payload
        ).hexdigest(),
        "dependencies": dependencies,
    }
```

- [ ] **Step 5: Implement non-secret provider identity**

Extend `RuntimeBackendReadiness` with:

```python
provider_label: str
provider_protocol: str
endpoint_fingerprint: str
provider_chain_size: int
```

Use a helper that hashes a normalized base URL without returning it:

```python
def endpoint_fingerprint(base_url: str | None) -> str:
    normalized = str(base_url or "").strip().rstrip("/")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
```

For `sdk_gpt`, set protocol to `openai_responses`, label from
`AGENT_RUNTIME_PROVIDER_LABEL` or `openai`, and base URL from
`LLM_BASE_URL`, then `OPENAI_BASE_URL`, then the official OpenAI default. Keep all existing readiness behavior and never include credential values.

- [ ] **Step 6: Make one app instance reuse one identity**

In `create_app`, build the runtime payload once and reuse its
`runtime_instance_id`. Populate `provider_chain_size` from environment-detected providers without forcing a lazy Keychain read; when `/api/llm/config` activates a saved session provider, refresh the readiness projection with a singleton chain.

- [ ] **Step 7: Run focused tests**

Run the command from Step 3 without `-k`. Expected: all selected files pass.

- [ ] **Step 8: Commit Task 1**

```bash
git add intelligence/services/runtime_provenance.py \
  intelligence/services/agent_runtime_factory.py \
  intelligence/tests/test_runtime_provenance.py \
  intelligence/tests/test_agent_runtime_factory.py \
  intelligence/tests/test_workbench_api.py
git commit -m "feat: expose exact continuous runtime identity"
```

## Task 2: Append-only Run attempt ledger

**Files:**

- Create: `intelligence/services/execution_provenance.py`
- Modify: `intelligence/services/run_store.py`
- Test: `intelligence/tests/test_execution_provenance.py`
- Test: `intelligence/tests/test_run_store.py`

- [ ] **Step 1: Write failing model-validation tests**

The new module must expose exactly these paths:

```python
EXECUTION_PATHS = frozenset(
    {
        "continuous_episode",
        "continuous_fast_path",
        "continuous_clarification",
        "legacy_direct",
    }
)
```

Test that blank IDs, unknown paths, booleans used as attempt indexes, and secret-shaped mapping keys fail closed or are redacted before persistence.

- [ ] **Step 2: Write failing RunStore lifecycle tests**

Add a complete lifecycle and replay test:

```python
runtime = RuntimeExecutionIdentity(
    runtime_instance_id="runtime-a",
    source_revision="a" * 40,
    source_dirty=False,
    code_root="/candidate",
    import_root="/candidate",
    python_executable="/python",
    backend="sdk_gpt",
    model="gpt-5.6-sol",
    provider_label="cockpit_local",
    provider_protocol="openai_responses",
    endpoint_fingerprint="b" * 64,
)
first = store.start_execution_attempt(run.run_id, runtime)
store.bind_execution_attempt(
    run.run_id,
    attempt_id=first.attempt_id,
    execution_path="continuous_episode",
    terminal_owner="continuous_turn_adapter",
    contributors=("turn_controller", "sdk_gpt"),
    task_frame_hash="c" * 64,
    cutoff="2026-07-23",
    effective_backend="sdk_gpt",
    effective_model="gpt-5.6-sol",
)
store.finish_execution_attempt(
    run.run_id,
    attempt_id=first.attempt_id,
    status="completed",
    artifact_receipts=({"path": "continuous-episode.json", "sha256": "d" * 64},),
)
second = store.start_execution_attempt(run.run_id, runtime)

assert first.attempt_index == 1
assert second.attempt_index == 2
assert [event["event_type"] for event in store.load_execution_attempts(run.run_id)] == [
    "attempt.started",
    "execution.bound",
    "attempt.finished",
    "attempt.started",
]
```

Also assert a second finish for the same attempt and a bind after finish raise `ValueError`.

- [ ] **Step 3: Run tests and verify they fail**

```bash
FINANCE_WS=/Users/a77/finance-workspace-private \
  /Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_execution_provenance.py \
  intelligence/tests/test_run_store.py -k 'execution_attempt or attempt_ledger'
```

Expected: missing module and methods.

- [ ] **Step 4: Implement immutable event types**

Create frozen `RuntimeExecutionIdentity`, `ExecutionAttempt`, and validation
helpers. Persist only bounded identifiers, dates, hashes, booleans, and stable
enum values. Use `redact_value()` as a second safety boundary before write.

```python
@dataclass(frozen=True)
class RuntimeExecutionIdentity:
    runtime_instance_id: str
    source_revision: str
    source_dirty: bool
    code_root: str
    import_root: str
    python_executable: str
    backend: str
    model: str
    provider_label: str
    provider_protocol: str
    endpoint_fingerprint: str

    @classmethod
    def from_runtime_payload(
        cls,
        payload: Mapping[str, object],
    ) -> "RuntimeExecutionIdentity":
        agent_runtime = payload.get("agent_runtime")
        if not isinstance(agent_runtime, Mapping):
            raise ValueError("runtime payload missing agent_runtime")
        return cls(
            runtime_instance_id=str(payload["runtime_instance_id"]),
            source_revision=str(payload["source_revision"]),
            source_dirty=bool(payload["source_dirty"]),
            code_root=str(payload["code_root"]),
            import_root=str(payload["import_root"]),
            python_executable=str(payload["python_executable"]),
            backend=str(agent_runtime["backend"]),
            model=str(agent_runtime["model"]),
            provider_label=str(agent_runtime["provider_label"]),
            provider_protocol=str(agent_runtime["provider_protocol"]),
            endpoint_fingerprint=str(agent_runtime["endpoint_fingerprint"]),
        )


@dataclass(frozen=True)
class ExecutionAttempt:
    attempt_id: str
    attempt_index: int


def validate_execution_path(value: str) -> str:
    cleaned = str(value or "").strip()
    if cleaned not in EXECUTION_PATHS:
        raise ValueError(f"unsupported execution path: {cleaned}")
    return cleaned
```

- [ ] **Step 5: Implement `RunStore` append/read methods**

Add `attempts_path(run_id)` and the three lifecycle methods. Use the existing per-path lock pattern, refuse a non-newline-terminated ledger, append one JSON object per event, then `flush()` and `os.fsync()`.

Every event includes `schema_version`, `event_type`, `run_id`, `attempt_id`,
`attempt_index`, and `created_at`. Transition checks are reconstructed from the existing file before append; no event is updated in place.

- [ ] **Step 6: Run focused tests**

Run the command from Step 3 without `-k`. Expected: all selected tests pass.

- [ ] **Step 7: Commit Task 2**

```bash
git add intelligence/services/execution_provenance.py \
  intelligence/services/run_store.py \
  intelligence/tests/test_execution_provenance.py \
  intelligence/tests/test_run_store.py
git commit -m "feat: persist append-only run execution attempts"
```

## Task 3: Bind observed execution ownership and Episode receipts

**Files:**

- Modify: `intelligence/services/conversation_orchestrator.py`
- Modify: `intelligence/api/app.py`
- Test: `intelligence/tests/test_conversation_orchestrator.py`
- Test: `intelligence/tests/test_workbench_api.py`

- [ ] **Step 1: Write failing path-binding tests**

Cover one turn of each relevant shape:

```text
research handled by adapter       -> continuous_episode
market technical fast path        -> continuous_fast_path
adapter clarification             -> continuous_clarification
adapter decline + direct lane      -> legacy_direct
```

For each, assert one `execution.bound` event has the expected path, stable
`terminal_owner`, non-empty contributors, TaskFrame hash, and cutoff.

- [ ] **Step 2: Write failing artifact-receipt tests**

For a completed Continuous Episode, assert:

```python
events = run_store.load_execution_attempts(run_id)
bound = next(item for item in events if item["event_type"] == "execution.bound")
finished = next(item for item in events if item["event_type"] == "attempt.finished")
receipt = next(
    item for item in finished["artifact_receipts"]
    if item["path"] == "continuous-episode.json"
)
artifact = next(
    item for item in run_store.load_run(run_id).artifacts
    if item["path"] == "continuous-episode.json"
)

assert receipt["sha256"] == artifact["sha256"]
assert receipt["attempt_id"] == bound["attempt_id"]
assert receipt["task_frame_hash"] == bound["task_frame_hash"]
assert receipt["cutoff"] == bound["cutoff"]
```

Clarification and legacy direct turns must finish their attempt without a fake
`continuous-episode.json` receipt.

- [ ] **Step 3: Run the new tests and verify they fail**

```bash
FINANCE_WS=/Users/a77/finance-workspace-private \
  /Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_conversation_orchestrator.py \
  intelligence/tests/test_workbench_api.py -k 'execution_path or episode_receipt or attempt_finish'
```

- [ ] **Step 4: Start and finish attempts at the worker boundary**

Pass the process runtime identity through `RunSupervisor.submit_conversation()`
to `_run_conversation_turn()`. Start the attempt before orchestration. In a
`finally` block, load the actual Run status and artifacts and append
`attempt.finished`; an exception leaves a truthful failed/incomplete receipt rather than silently reusing the previous attempt.

The worker must pass the `ExecutionAttempt` handle into `TurnOrchestrator`.

- [ ] **Step 5: Bind execution immediately after control ownership is known**

Add a single internal helper in `TurnOrchestrator`:

```python
def _bind_execution(
    self,
    *,
    run_id: str,
    execution_path: str,
    terminal_owner: str,
    contributors: Sequence[str],
    task_frame: TaskFrame,
    cutoff: str | None,
) -> None:
    if self.execution_attempt is None:
        return
    self.run_store.bind_execution_attempt(
        run_id,
        attempt_id=self.execution_attempt.attempt_id,
        execution_path=execution_path,
        terminal_owner=terminal_owner,
        contributors=tuple(dict.fromkeys(contributors)),
        task_frame_hash=task_frame.task_frame_hash,
        cutoff=cutoff or task_frame.timeframe,
        effective_backend=self.runtime_identity.backend,
        effective_model=self.llm_model or self.runtime_identity.model,
    )
```

Classification is code-owned:

```python
if continuous_result.handled:
    if continuous_control.terminal_kind == "clarification":
        path = "continuous_clarification"
    elif task_frame.question_type in CONTINUOUS_FAST_PATH_TYPES:
        path = "continuous_fast_path"
    else:
        path = "continuous_episode"
else:
    path = "legacy_direct"
```

For Episode results, extract the effective cutoff from
`private_artifact.research_context.information_cutoff.as_of_date`; fall back to
the frozen TaskFrame timeframe only when the adapter produced no research context.

- [ ] **Step 6: Bind the internal Episode artifact to the attempt**

Before serializing `continuous-episode.json`, add a private execution receipt with
`run_id`, `attempt_id`, `runtime_instance_id`, `task_frame_hash`, and cutoff.
After `add_artifact()` returns its SHA-256 metadata, the worker's
`attempt.finished` event records the matching public-safe receipt.

- [ ] **Step 7: Run focused tests**

Run the command from Step 3 without `-k`. Expected: all selected tests pass.

- [ ] **Step 8: Commit Task 3**

```bash
git add intelligence/services/conversation_orchestrator.py \
  intelligence/api/app.py \
  intelligence/tests/test_conversation_orchestrator.py \
  intelligence/tests/test_workbench_api.py
git commit -m "feat: bind run attempts to observed execution paths"
```

## Task 4: Safe provenance API

**Files:**

- Modify: `intelligence/api/app.py`
- Test: `intelligence/tests/test_workbench_api.py`

- [ ] **Step 1: Write failing API tests**

Add tests for:

```text
GET /api/runs/{run_id}/provenance
```

The response must include the attempt events and Episode receipt hash, but must
not contain the API key, raw provider URL, prompts, private Episode content, or
provider continuation. Unknown runs return 404.

- [ ] **Step 2: Run the tests and verify they fail**

```bash
FINANCE_WS=/Users/a77/finance-workspace-private \
  /Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_workbench_api.py -k 'run_provenance'
```

- [ ] **Step 3: Implement the endpoint**

Use only `RunStore.load_execution_attempts()` and `redact_value()`:

```python
@app.get("/api/runs/{run_id}/provenance")
def get_run_provenance(run_id: str, user: str | None = None) -> dict[str, object]:
    store = store_for(user)
    try:
        store.load_run(run_id)
        events = store.load_execution_attempts(run_id)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(404, f"run 不存在：{run_id}") from exc
    return {"run_id": run_id, "attempts": redact_value(events)}
```

Do not expose a route for downloading `attempts.jsonl` or
`continuous-episode.json`.

- [ ] **Step 4: Run focused tests**

Run the command from Step 2. Expected: all selected tests pass.

- [ ] **Step 5: Commit Task 4**

```bash
git add intelligence/api/app.py intelligence/tests/test_workbench_api.py
git commit -m "feat: expose redacted run execution provenance"
```

## Task 5: Explicit execution contracts and strict preflight

**Files:**

- Create: `intelligence/eval/cases/acceptance_execution_contracts.json`
- Modify: `intelligence/eval/acceptance.py`
- Modify: `intelligence/tests/test_acceptance_board.py`

- [ ] **Step 1: Add the full execution-contract overlay**

Use an explicit entry for every frozen case so adding or renaming a case fails
closed:

```json
{
  "schema_version": 1,
  "cases": {
    "A1-market-overview": "continuous_episode",
    "A2-next-day-call": "continuous_episode",
    "A3-stock-deep-dive": "continuous_episode",
    "A4-dual-red": "continuous_episode",
    "A5-limit-heat": "continuous_episode",
    "A6-limit-advance-ladder": "continuous_episode",
    "A7-mainline": "continuous_episode",
    "A8-market-stage": "continuous_episode",
    "A9-sentiment-contradiction": "continuous_episode",
    "A10-new-high-structure": "continuous_episode",
    "B1-theme-photoresist": "continuous_episode",
    "B2-theme-liquid-cooling": "continuous_episode",
    "B3-theme-solid-state-battery": "continuous_episode",
    "B4-fermentation-trace": "continuous_episode",
    "B5-cross-table-intersection": "continuous_episode",
    "B6-sellside-distillation": "continuous_clarification",
    "B7-volume-sentiment-evolution": "continuous_episode",
    "B8-valuation-band": "continuous_episode",
    "C1-future-date-no-data": "continuous_episode",
    "C2-non-trading-day": "continuous_episode",
    "C3-empty-table": "continuous_episode",
    "C4-unit-anomaly": "continuous_episode",
    "C5-data-contradiction": "continuous_episode",
    "C6-strict-definition": "continuous_episode",
    "C7-temporal-leakage": "continuous_episode",
    "C8-nonexistent-table": "legacy_direct",
    "C9-citation-integrity": "continuous_episode",
    "C10-multi-turn-consistency": "continuous_episode"
  }
}
```

- [ ] **Step 2: Write failing overlay and strict-preflight tests**

Tests must reject missing/extra case IDs, invalid paths, mode off, dirty source,
short or wrong revision, code/import root mismatch, backend/model mismatch,
provider-chain size other than one, provider label/protocol mismatch, and a
runtime instance missing from health.

The healthy fixture must contain the full exact identity and produce a stable
`receipt_hash` over canonical JSON.

- [ ] **Step 3: Run tests and verify they fail**

```bash
FINANCE_WS=/Users/a77/finance-workspace-private \
  /Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_acceptance_board.py
```

- [ ] **Step 4: Implement structured preflight**

Add:

```python
@dataclass(frozen=True)
class ExpectedRuntime:
    mode: str
    backend: str
    model: str
    revision: str
    code_root: str
    provider_label: str
    provider_protocol: str = "openai_responses"


@dataclass(frozen=True)
class PreflightReport:
    acceptance_eligible: bool
    failures: tuple[str, ...]
    expected: dict[str, object]
    observed: dict[str, object]
    receipt_hash: str
```

`preflight(base, expected)` returns the report, not a truthy tuple. Canonicalize
the non-secret expected/observed payload with sorted compact JSON before hashing.
Keep `/api/llm/config` readiness, but make health identity the authoritative
source for mode/backend/model/revision/import root.

- [ ] **Step 5: Make CLI expectations explicit**

The `run` command requires the following concrete invocation fields:

```text
--expected-revision "$(git rev-parse HEAD)"
--expected-code-root /Users/a77/finance-workspace-private/tmp/agent-runtime-seam-fix-69f9cf17
--expected-mode on
--expected-backend sdk_gpt
--expected-model gpt-5.6-sol
--expected-provider-label cockpit_local
--expected-provider-protocol openai_responses
```

`--force` may execute diagnostic turns, but the output keeps
`acceptance_eligible=false`; `board` must never count such a file as formal
Continuous acceptance.

- [ ] **Step 6: Run focused tests**

Run the command from Step 3. Expected: all tests pass.

- [ ] **Step 7: Commit Task 5**

```bash
git add intelligence/eval/cases/acceptance_execution_contracts.json \
  intelligence/eval/acceptance.py \
  intelligence/tests/test_acceptance_board.py
git commit -m "feat: fail closed on continuous acceptance identity"
```

## Task 6: Exact Run binding and true C10 multi-turn execution

**Files:**

- Modify: `intelligence/eval/acceptance.py`
- Modify: `intelligence/tests/test_acceptance_board.py`
- Modify: `intelligence/tests/test_acceptance_runs.py`

- [ ] **Step 1: Write failing exact-message polling tests**

Simulate a conversation containing an older completed assistant message and the
new pending message. Assert the client waits for the exact
`assistant_message_id` returned by POST and rejects a message whose `run_id`
does not match the POST response.

- [ ] **Step 2: Write failing C10 reuse tests**

Stub one conversation creation and three turn submissions. Assert:

```python
assert create_conversation.call_count == 1
assert [turn.conversation_id for turn in case.turns] == ["conv-1"] * 3
assert len({turn.run_id for turn in case.turns}) == 3
assert len({turn.assistant_message_id for turn in case.turns}) == 3
```

Also assert observed execution paths match the overlay and all three C10 turns
carry the same PIT cutoff.

- [ ] **Step 3: Run the new tests and verify they fail**

```bash
FINANCE_WS=/Users/a77/finance-workspace-private \
  /Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_acceptance_board.py \
  intelligence/tests/test_acceptance_runs.py -k 'exact_message or multi_turn or execution_contract'
```

- [ ] **Step 4: Split conversation creation from turn submission**

Implement these boundaries:

```python
def create_conversation(base: str, user: str, title: str) -> str:
    payload = _post(
        f"{base}/api/conversations",
        {"title": title, "user": user},
    )
    conversation_id = str(
        payload.get("conversation_id") or payload.get("id") or ""
    ).strip()
    if not conversation_id:
        raise ValueError("create conversation response missing conversation_id")
    return conversation_id


def ask_turn(
    base: str,
    user: str,
    conversation_id: str,
    question: str,
    timeout: float,
    *,
    expected_path: str,
    preflight_receipt_hash: str,
) -> TurnTrace:
    trace = TurnTrace(
        question=question,
        conversation_id=conversation_id,
        expected_execution_path=expected_path,
        preflight_receipt_hash=preflight_receipt_hash,
    )
    started = time.monotonic()
    submission = _post(
        f"{base}/api/conversations/{conversation_id}/messages",
        {"content": question, "skill_mode": "auto", "user": user},
    )
    trace.user_message_id = str(submission["user_message_id"])
    trace.assistant_message_id = str(submission["assistant_message_id"])
    trace.run_id = str(submission["run_id"])
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        time.sleep(2.0)
        payload = _get(
            f"{base}/api/conversations/{conversation_id}/messages?user={user}"
        )
        messages = payload if isinstance(payload, list) else payload.get("messages", [])
        assistant = next(
            (
                item
                for item in messages
                if item.get("message_id") == trace.assistant_message_id
            ),
            None,
        )
        if assistant is None or assistant.get("status") in {None, "pending", "running"}:
            continue
        if assistant.get("run_id") != trace.run_id:
            raise ValueError("assistant message run_id differs from submission")
        _fill_terminal_trace(base, user, trace, assistant)
        break
    else:
        trace.status = "timeout"
        trace.error = f"超过 {timeout}s 未返回终态"
    trace.elapsed_s = round(time.monotonic() - started, 1)
    return trace
```

Extend `TurnTrace` with `conversation_id`, `user_message_id`,
`assistant_message_id`, `parent_run_id`, `execution_path`, `terminal_owner`,
`attempt_id`, `attempt_index`, `runtime_instance_id`, `task_frame_hash`,
`cutoff`, `expected_execution_path`, `artifact_receipt_valid`, and
`preflight_receipt_hash`.

Implement the helper called by `ask_turn` with explicit fail-closed selection:

```python
def _fill_terminal_trace(
    base: str,
    user: str,
    trace: TurnTrace,
    assistant: dict[str, Any],
) -> None:
    trace.answer = assistant.get("content")
    trace.status = str(assistant.get("status") or "unknown")
    trace.invoked_skill_ids = list(assistant.get("invoked_skill_ids") or [])
    trace.citations = list(assistant.get("citations") or [])
    trace.degrades = list(assistant.get("degrades") or [])
    run = _get(f"{base}/api/runs/{trace.run_id}?user={user}")
    trace.parent_run_id = run.get("parent_run_id")
    provenance = _get(
        f"{base}/api/runs/{trace.run_id}/provenance?user={user}"
    )
    events = provenance.get("attempts") if isinstance(provenance, dict) else None
    if not isinstance(events, list):
        trace.error = "execution_provenance_missing"
        return
    finished = next(
        (
            item
            for item in reversed(events)
            if item.get("event_type") == "attempt.finished"
        ),
        None,
    )
    if not isinstance(finished, dict):
        trace.error = "attempt_finished_missing"
        return
    attempt_id = str(finished.get("attempt_id") or "")
    bound = next(
        (
            item
            for item in reversed(events)
            if item.get("event_type") == "execution.bound"
            and item.get("attempt_id") == attempt_id
        ),
        None,
    )
    started = next(
        (
            item
            for item in reversed(events)
            if item.get("event_type") == "attempt.started"
            and item.get("attempt_id") == attempt_id
        ),
        None,
    )
    if not isinstance(bound, dict) or not isinstance(started, dict):
        trace.error = "attempt_binding_missing"
        return
    trace.attempt_id = attempt_id
    trace.attempt_index = int(started["attempt_index"])
    trace.runtime_instance_id = str(started["runtime_instance_id"])
    trace.execution_path = str(bound["execution_path"])
    trace.terminal_owner = str(bound["terminal_owner"])
    trace.task_frame_hash = str(bound["task_frame_hash"])
    trace.cutoff = str(bound.get("cutoff") or "") or None
    if trace.execution_path != trace.expected_execution_path:
        trace.error = "execution_path_mismatch"
        return
    receipts = finished.get("artifact_receipts") or []
    episode = next(
        (
            item
            for item in receipts
            if isinstance(item, dict)
            and item.get("path") == "continuous-episode.json"
        ),
        None,
    )
    if trace.execution_path == "continuous_episode":
        trace.artifact_receipt_valid = bool(
            isinstance(episode, dict)
            and episode.get("run_id") == trace.run_id
            and episode.get("attempt_id") == trace.attempt_id
            and episode.get("task_frame_hash") == trace.task_frame_hash
            and episode.get("cutoff") == trace.cutoff
            and re.fullmatch(r"[0-9a-f]{64}", str(episode.get("sha256") or ""))
        )
        if not trace.artifact_receipt_valid:
            trace.error = "continuous_episode_receipt_mismatch"
            return
    else:
        trace.artifact_receipt_valid = episode is None
    _fill_run_detail(base, trace, user=user)
```

- [ ] **Step 5: Validate provenance rather than infer it**

After the exact assistant message reaches terminal state:

1. fetch `/api/runs/{run_id}` and `/api/runs/{run_id}/provenance`;
2. select the attempt referenced by the terminal receipt;
3. compare observed path with the overlay;
4. for `continuous_episode`, require a matching
   `continuous-episode.json` receipt with run/attempt/TaskFrame/cutoff/hash;
5. record a seam error when any field is missing or mismatched.

- [ ] **Step 6: Reuse one conversation per case**

Move `create_conversation()` outside the question loop in `cmd_run`. All
follow-ups for a case use that ID; the next case receives a fresh conversation.
Preserve existing stop-on-error behavior and business-quality evaluation.

- [ ] **Step 7: Persist Layer 1 separately from Layer 2**

The run artifact records:

```json
{
  "acceptance_eligible": true,
  "execution_summary": {
    "total_turns": 30,
    "path_matches": 30,
    "continuous_episode_turns": 28,
    "valid_episode_receipts": 28
  }
}
```

These are measured counts, not hard-coded output. Existing answer verdicts stay
separate and may fail without rewriting execution validity.

- [ ] **Step 8: Run focused tests**

Run the command from Step 3 without `-k`. Expected: all selected tests pass.

- [ ] **Step 9: Commit Task 6**

```bash
git add intelligence/eval/acceptance.py \
  intelligence/tests/test_acceptance_board.py \
  intelligence/tests/test_acceptance_runs.py
git commit -m "fix: run acceptance followups in one conversation"
```

## Task 7: Secret-safe Cockpit acceptance runner

**Files:**

- Create: `scripts/run_continuous_cockpit_acceptance.py`
- Create: `intelligence/tests/test_continuous_cockpit_acceptance_runner.py`

- [ ] **Step 1: Write failing runner safety tests**

Test with a temporary Cockpit config and stub subprocess/HTTP layer. Cover:

- missing config or empty `api-keys` fails before server start;
- dirty Git checkout fails;
- occupied port fails instead of probing the old process;
- generated child environment removes GLM, generic, and other provider keys;
- child environment contains the Cockpit key, but command/log/receipt do not;
- `/models` must contain `gpt-5.6-sol`;
- `/responses` must return `status=completed` and output `OK`;
- canary selects one research case plus B6, C8, and C10;
- full suite runs its gate canary first inside the same child server process and
  proceeds only while revision and runtime identity remain unchanged.

- [ ] **Step 2: Run tests and verify they fail**

```bash
FINANCE_WS=/Users/a77/finance-workspace-private \
  /Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_continuous_cockpit_acceptance_runner.py
```

- [ ] **Step 3: Implement config loading and provider isolation**

Read JSON with the standard library; accept only a non-empty string at
`api-keys[0]`. Build the child environment from a copy, remove these inherited
keys, then add only the Cockpit OpenAI-compatible settings:

```python
PROVIDER_SECRET_ENV = {
    "LLM_API_KEY",
    "FORESIGHT_BUILTIN_LLM_API_KEY",
    "ZHIPU_API_KEY",
    "GLM_API_KEY",
    "DEEPSEEK_API_KEY",
    "MOONSHOT_API_KEY",
    "KIMI_API_KEY",
    "DASHSCOPE_API_KEY",
    "QWEN_API_KEY",
    "OPENAI_API_KEY",
}
```

Then set `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `LLM_MODEL`,
`OPENAI_AGENT_MODEL`, `AGENT_RUNTIME_PROVIDER_LABEL`,
`AGENT_RUNTIME_BACKEND=sdk_gpt`, `ASK_CONTINUOUS_RUNTIME=on`,
`WORKBENCH_REPO_ROOT`, `FINANCE_WS`, and an isolated `FORESIGHT_USERS_DIR`.

- [ ] **Step 4: Implement direct Cockpit protocol smoke**

Use `urllib.request` with an Authorization header in memory. Probe `/models`,
then send this exact bounded Responses request:

```json
{
  "model": "gpt-5.6-sol",
  "input": "Reply exactly OK.",
  "max_output_tokens": 16,
  "store": false
}
```

Return only status, model ID, response status, and a boolean `output_ok`; never
return headers or raw config.

- [ ] **Step 5: Implement isolated server lifecycle**

Before start, require a clean checkout and an unused port. Launch with
`cwd=code_root` and the exact workspace Python:

```python
[python, "-m", "uvicorn", "intelligence.api.app:app", "--host", "127.0.0.1", "--port", str(port)]
```

Poll `/api/health`, then compare its revision, code root, import root, mode,
backend, model, provider label, protocol, provider-chain size, and runtime
instance against expectations. On every exit path terminate only the child PID
started by this runner; never touch 8792 or launchd.

- [ ] **Step 6: Implement canary/full suite selection**

Default `--suite canary` passes these exact case IDs to the acceptance CLI:

```text
A4-dual-red
B6-sellside-distillation
C8-nonexistent-table
C10-multi-turn-consistency
```

`--suite full` first executes the four-case canary in the same child server
process and requires the same full revision, runtime instance identity,
provider/model, and `acceptance_eligible=true`. It then invokes the 28-case
command without `--case` filters. This prevents a receipt from a different
process from unlocking the full run.

- [ ] **Step 7: Run focused tests**

Run the command from Step 2. Expected: all tests pass.

- [ ] **Step 8: Commit Task 7**

```bash
git add scripts/run_continuous_cockpit_acceptance.py \
  intelligence/tests/test_continuous_cockpit_acceptance_runner.py
git commit -m "feat: add isolated cockpit acceptance runner"
```

## Task 8: Offline regression, clean revision, live canary, and full acceptance

**Files:**

- Verify only; live JSON receipts go to the existing gitignored/private acceptance state path.
- Update after measured results: `.agent-memory/20_projects/finance-workspace-private.md`

- [ ] **Step 1: Run formatting and focused regression**

```bash
git diff --check
FINANCE_WS=/Users/a77/finance-workspace-private \
  /Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_runtime_provenance.py \
  intelligence/tests/test_agent_runtime_factory.py \
  intelligence/tests/test_execution_provenance.py \
  intelligence/tests/test_run_store.py \
  intelligence/tests/test_continuous_turn_adapter.py \
  intelligence/tests/test_conversation_orchestrator.py \
  intelligence/tests/test_workbench_api.py \
  intelligence/tests/test_acceptance_board.py \
  intelligence/tests/test_acceptance_runs.py \
  intelligence/tests/test_continuous_cockpit_acceptance_runner.py
```

Expected: no new failing test names. If the known repository-wide environment
failures are encountered outside this focused set, report them separately and
do not relabel them as this branch's regression.

- [ ] **Step 2: Commit any final test-only corrections**

```bash
git status --short
git diff --check
git add intelligence/services/runtime_provenance.py \
  intelligence/services/agent_runtime_factory.py \
  intelligence/services/execution_provenance.py \
  intelligence/services/run_store.py \
  intelligence/services/conversation_orchestrator.py \
  intelligence/api/app.py \
  intelligence/eval/cases/acceptance_execution_contracts.json \
  intelligence/eval/acceptance.py \
  scripts/run_continuous_cockpit_acceptance.py \
  intelligence/tests/test_runtime_provenance.py \
  intelligence/tests/test_agent_runtime_factory.py \
  intelligence/tests/test_execution_provenance.py \
  intelligence/tests/test_run_store.py \
  intelligence/tests/test_conversation_orchestrator.py \
  intelligence/tests/test_workbench_api.py \
  intelligence/tests/test_acceptance_board.py \
  intelligence/tests/test_acceptance_runs.py \
  intelligence/tests/test_continuous_cockpit_acceptance_runner.py
git commit -m "test: close continuous acceptance trust regressions"
```

Skip this commit when Step 1 requires no correction; do not create an empty commit.

- [ ] **Step 3: Require a clean revision before live work**

```bash
git status --short
git rev-parse HEAD
```

Expected: empty status and one 40-character revision. A dirty checkout blocks
the runner by design.

- [ ] **Step 4: Run the gated Cockpit full command**

```bash
FINANCE_WS=/Users/a77/finance-workspace-private \
  /Users/a77/finance-workspace-private/.venv-workbench/bin/python \
  scripts/run_continuous_cockpit_acceptance.py \
  --suite full \
  --code-root /Users/a77/finance-workspace-private/tmp/agent-runtime-seam-fix-69f9cf17 \
  --data-root /Users/a77/finance-workspace-private \
  --port 8801
```

The runner first executes a six-turn gate—four Continuous Episode turns (A4
plus three C10 turns), one Continuous clarification, and one legacy direct
turn. Only a green gate starts the 30-turn full run on the same server instance.

- [ ] **Step 5: Inspect the measured gate receipt**

Verify `acceptance_eligible=true`, exact clean revision/import root, singleton
Cockpit provider, stable runtime instance across all turns, C10's single
conversation ID, and zero receipt mismatch. If any Layer 1 field fails, stop;
the runner must have stopped before the full suite. Do not patch around a
business-answer failure.

- [ ] **Step 6: Inspect the full 28-case receipt when the gate passed**

Expected Layer 1 target: 30/30 path matches, 28/28 valid Continuous Episode
receipts, one clarification, one legacy direct turn, and zero identity drift.
Layer 2 answer-quality failures remain visible and do not invalidate a truthful
Layer 1 result.

- [ ] **Step 7: Persist the project-level handoff**

Append only the measured architecture/result summary to
`.agent-memory/20_projects/finance-workspace-private.md`: branch and revision,
Cockpit model/protocol, canary/full Layer 1 counts, Layer 2 count, artifact
locations, and any blocker. Do not copy conversation transcript or secrets.

- [ ] **Step 8: Final safety audit**

```bash
git status --short
git log --oneline -8
git diff main...HEAD -- . ':!intelligence/eval/runs/**'
```

Confirm no `.env*`, key, PDF, archive, database, cache, virtual environment, or
private acceptance artifact is staged or committed. Do not merge `main`, push,
or restart 8792 without separate user authorization.
