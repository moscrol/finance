# Dual-Lane Agent Review Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a machine-enforced Codex Producer + Claude external Reviewer loop that keeps development moving through bounded reviewer outages without allowing self-review to seal or release code.

**Architecture:** Versioned Python commands own contracts, provenance validation, request submission, and Producer authority; the shell worker only performs process orchestration. Mutable requests, claims, verdicts, backoff, and locks remain outside Git under one configurable runtime root. External and provisional verdicts are separate authorities, and every decision is recomputed from immutable Git ancestry plus request hashes.

**Tech Stack:** Python 3.11 standard library, Git CLI, pytest, POSIX/zsh worker wrapper, Claude Code headless reviewer, Codex headless fallback reviewer.

---

## File Map

- `scripts/agent_review/contract.py`: schema-2 values, JSON loading, Git ancestry, request hashing, legacy classification, and artifact-test discovery.
- `scripts/agent_review/submit.py`: the only schema-2 request writer; recomputes mechanical fields and writes request plus claim hash atomically.
- `scripts/agent_review/validate_verdict.py`: validates external/provisional verdict identity, commit, hash, ancestry, checks, and authority.
- `scripts/agent_review/gate.py`: reduces all requests/verdicts into one machine-readable Producer decision and release decision.
- `scripts/agent_review/worker.py`: selects the valid frontier, owns lock/backoff/claim/worktree lifecycle, and invokes a configured reviewer executable.
- `scripts/agent_review/reviewer_worker.sh`: small source-of-truth wrapper around `worker.py`.
- `scripts/agent_review/producer_fallback.py`: runs the same review manifest in a detached worktree and writes only provisional verdicts.
- `intelligence/tests/test_agent_review_contract.py`: schema, discovery, hash, hygiene, and legacy tests.
- `intelligence/tests/test_agent_review_gate.py`: authority, speculative depth, taint, and release tests.
- `intelligence/tests/test_agent_review_worker.py`: lock, backoff, fake-reviewer, claim mutation, and fallback integration tests.

Mutable state is configurable with `AGENT_REVIEW_ROOT` and defaults to
`/Users/a77/.finance-runtime/agent-review-loop`. Tests always use `tmp_path`.

---

### Task 1: Add strict schema-2 contracts and legacy classification

**Files:**
- Create: `scripts/agent_review/__init__.py`
- Create: `scripts/agent_review/contract.py`
- Create: `intelligence/tests/test_agent_review_contract.py`

- [ ] **Step 1: Write failing contract tests**

```python
def test_schema2_request_rejects_unknown_identity_and_missing_mapping(repo):
    raw = request_dict(
        producer="codex:subagent",
        artifacts=["intelligence/services/evidence_ledger.py"],
        artifact_tests={},
    )
    result = validate_request(raw, repo=repo)
    assert "producer_identity" in result.errors
    assert "artifact_test_coverage" in result.errors


def test_legacy_verdicts_are_classified_without_mutation(repo, state_root):
    before = sha256_file(state_root / "verdicts/ARL-0001.json")
    classification = classify_legacy_records(state_root, repo=repo)
    assert classification["ARL-0001"].state == "LEGACY_SELF_REVIEW"
    assert sha256_file(state_root / "verdicts/ARL-0001.json") == before
```

Also cover malformed JSON, path traversal, forbidden artifacts, invalid review
IDs, duplicate artifacts/tests, unsupported intensity, a missing commit, and a
request commit that is not a descendant of `parent_commit`.

- [ ] **Step 2: Run the tests and verify RED**

Run:

```bash
env -u FORESIGHT_USERS_DIR -u FORESIGHT_USER -u SUBCONSCIOUS_VAULT \
  -u AGENT_MEMORY_VAULT \
  /Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_agent_review_contract.py
```

Expected: import failure for `scripts.agent_review.contract`.

- [ ] **Step 3: Implement frozen values and deterministic validators**

```python
class GateState(str, Enum):
    WAITING_EXTERNAL = "WAITING_EXTERNAL"
    EXTERNAL_PASS = "EXTERNAL_PASS"
    CHANGES_REQUIRED = "CHANGES_REQUIRED"
    PROVISIONAL_PASS = "PROVISIONAL_PASS"
    BLOCKED = "BLOCKED"
    INVALID = "INVALID"


@dataclass(frozen=True)
class ReviewRequest:
    schema_version: int
    review_id: str
    commit: str
    parent_commit: str
    branch: str
    producer: str
    scope: str
    artifacts: tuple[str, ...]
    artifact_tests: Mapping[str, tuple[str, ...]]
    required_checks: tuple[str, ...]
    depends_on: tuple[str, ...]
    supersedes: str | None
    intensity: str
    created_at: str
    status: str


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    errors: tuple[str, ...]
```

Use exact allowlists: producer `codex:producer`, external reviewer
`claude:independent-reviewer`, intensities `light|milestone|release`, and
statuses defined by the design. Resolve every path under the repository before
reading it. `classify_legacy_records()` returns derived classifications and
never modifies old JSON.

- [ ] **Step 4: Run tests and commit**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_agent_review_contract.py
git add scripts/agent_review/__init__.py scripts/agent_review/contract.py \
  intelligence/tests/test_agent_review_contract.py
git commit -m "feat: define agent review contracts"
```

Expected: all contract tests pass.

---

### Task 2: Make request submission mechanical and immutable

**Files:**
- Modify: `scripts/agent_review/contract.py`
- Create: `scripts/agent_review/submit.py`
- Modify: `intelligence/tests/test_agent_review_contract.py`

- [ ] **Step 1: Write failing discovery and submission tests**

```python
def test_submit_discovers_all_existing_direct_tests(repo, state_root):
    request = submit_request(
        repo=repo,
        state_root=state_root,
        scope="evidence ledger slice",
        artifacts=("intelligence/services/evidence_ledger.py",),
        required_checks=("run focused tests",),
        intensity="light",
    )
    assert request.artifact_tests["intelligence/services/evidence_ledger.py"] == (
        "intelligence/tests/test_evidence_ledger.py",
    )
    claim = json.loads((state_root / "claims" / f"{request.review_id}.json").read_text())
    assert claim["request_sha256"] == sha256_file(
        state_root / "requests" / f"{request.review_id}.json"
    )
```

Add fixtures for conventional `test_X.py`, exact import hits, tests changed in
`parent..commit`, concurrent IDs, atomic rename, and a forbidden waiver for a
gate/verifier/budget/session artifact.

- [ ] **Step 2: Run the targeted tests and verify RED**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_agent_review_contract.py -k 'discover or submit or claim'
```

Expected: missing `discover_artifact_tests` and `submit_request`.

- [ ] **Step 3: Implement discovery and the only writer**

`discover_artifact_tests(repo, artifacts, parent_commit, commit)` searches:

```python
candidate_paths = {
    Path("intelligence/tests") / f"test_{artifact.stem}.py",
    artifact.parent / "tests" / f"test_{artifact.stem}.py",
}
```

Then it adds exact import hits and changed test files from
`git diff --name-only parent..commit`. `submit_request()` takes the repository
lock, allocates the next ID, reads the exact current branch/tip/parent, validates
dependencies, serializes sorted JSON to a temporary file, atomically renames
it, and writes a separate claim containing the request SHA-256. The CLI accepts
repeatable `--artifact` and `--required-check`; callers cannot provide
`artifact_tests`, commit, producer, hash, or branch.

- [ ] **Step 4: Verify CLI output and commit**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_agent_review_contract.py
/Users/a77/finance-workspace-private/.venv-workbench/bin/python \
  -m scripts.agent_review.submit --help
git add scripts/agent_review/contract.py scripts/agent_review/submit.py \
  intelligence/tests/test_agent_review_contract.py
git commit -m "feat: submit immutable review requests"
```

Expected: tests pass and help exits zero without writing state.

---

### Task 3: Validate verdict provenance and authority

**Files:**
- Create: `scripts/agent_review/validate_verdict.py`
- Modify: `intelligence/tests/test_agent_review_contract.py`

- [ ] **Step 1: Write failing falsification tests**

```python
@pytest.mark.parametrize("reviewer", ["codex:producer", "codex:subagent", "claude"])
def test_non_whitelisted_pass_never_grants_external_authority(review_case, reviewer):
    verdict = verdict_dict(reviewer=reviewer, status="PASS")
    result = validate_verdict(verdict, request=review_case.request, authority="external")
    assert not result.valid
    assert "reviewer_identity" in result.errors


def test_mutated_request_invalidates_verdict(review_case):
    review_case.request_path.write_text(review_case.request_path.read_text() + "\n")
    result = validate_verdict_file(review_case.verdict_path, context=review_case.context)
    assert "request_hash_mismatch" in result.errors
```

Also test exact commit mismatch, review ID mismatch, non-ancestor commit, missing
artifact test in `checks`, invalid finding shape, provisional output placed in
the official directory, and an official verdict placed in provisional state.

- [ ] **Step 2: Verify RED and implement**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_agent_review_contract.py -k 'verdict or whitelist or mutated'
```

`validate_verdict()` must return authority explicitly:

```python
@dataclass(frozen=True)
class VerdictValidation:
    valid: bool
    authority: Literal["external", "provisional", "none"]
    errors: tuple[str, ...]
    status: str
```

It recomputes request hash, verifies commit existence and ancestry against the
current branch tip, and requires all discovered artifact tests plus requested
checks in the verdict's run manifest. A producer fallback verdict may be valid
only with provisional authority and never with external authority.

- [ ] **Step 3: Run contract tests and commit**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_agent_review_contract.py
git add scripts/agent_review/validate_verdict.py \
  intelligence/tests/test_agent_review_contract.py
git commit -m "feat: validate review verdict provenance"
```

---

### Task 4: Enforce Producer progression and release gates

**Files:**
- Create: `scripts/agent_review/gate.py`
- Create: `intelligence/tests/test_agent_review_gate.py`

- [ ] **Step 1: Write the state-machine tests**

```python
def test_two_provisional_slices_allowed_but_third_denied(case):
    case.external_pass("ARL-0020")
    case.provisional_pass("ARL-0021")
    assert case.decision_at("ARL-0021").allowed_next_action == "IMPLEMENT_NEXT"
    case.provisional_pass("ARL-0022")
    decision = case.decision_at("ARL-0022")
    assert decision.provisional_depth == 2
    assert decision.allowed_next_action == "WAIT"


def test_external_finding_taints_provisional_descendants(case):
    case.provisional_pass("ARL-0021")
    case.provisional_pass("ARL-0022")
    case.external_changes_required("ARL-0021")
    decision = case.decision_at("ARL-0022")
    assert decision.allowed_next_action == "FIX"
    assert decision.tainted_review_ids == ("ARL-0022",)


def test_release_denied_until_provisional_debt_is_zero(case):
    case.provisional_pass("ARL-0021", intensity="milestone")
    assert not case.decision_at("ARL-0021", release=True).release_allowed
```

Cover `WAITING_EXTERNAL`, external PASS, `CHANGES_REQUIRED`, invalid
provenance, abandoned commit, dependency mismatch, SLA eligibility for light
and milestone, no fallback for release, duplicate architecture conflicts, and
full-regression/live-benchmark release prerequisites.

- [ ] **Step 2: Run and verify RED**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_agent_review_gate.py
```

- [ ] **Step 3: Implement one reducer and JSON CLI**

```python
@dataclass(frozen=True)
class GateDecision:
    branch: str
    tip: str
    gate_state: str
    latest_external_sealed_commit: str | None
    pending_review_id: str | None
    provisional_depth: int
    tainted_review_ids: tuple[str, ...]
    allowed_next_action: Literal["WAIT", "FIX", "IMPLEMENT_NEXT", "RELEASE_CHECK"]
    release_allowed: bool
    reasons: tuple[str, ...]
    invalid_records: tuple[str, ...]
```

`compute_gate()` consumes only validated records. It derives debt from Git
ancestry after the latest externally sealed commit; external PASS clears the
matching provisional item, while an ancestor finding taints descendants. The
CLI prints only sorted JSON to stdout and uses nonzero exit codes for
`WAIT|FIX|INVALID`, enabling Producer and workers to share the same authority.

- [ ] **Step 4: Run tests and commit**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_agent_review_contract.py \
  intelligence/tests/test_agent_review_gate.py
git add scripts/agent_review/gate.py intelligence/tests/test_agent_review_gate.py
git commit -m "feat: enforce producer review gates"
```

---

### Task 5: Replace the retrying shell loop with a locked, backoff-aware worker

**Files:**
- Create: `scripts/agent_review/worker.py`
- Create: `scripts/agent_review/reviewer_worker.sh`
- Create: `intelligence/tests/test_agent_review_worker.py`

- [ ] **Step 1: Write fake-reviewer worker tests**

```python
def test_duplicate_worker_cannot_claim_same_request(worker_case):
    first = worker_case.start_fake_reviewer(block=True)
    second = worker_case.run_once()
    assert second.status == "LOCKED"
    first.release()


def test_budget_failure_sets_backoff_and_does_not_retry(worker_case):
    worker_case.fake_reviewer(exit_code=1, stderr="Exceeded USD budget")
    first = worker_case.run_once(now=1000)
    second = worker_case.run_once(now=1001)
    assert first.status == "REVIEWER_INACTIVE"
    assert second.status == "BACKOFF"
    assert worker_case.invocations == 1
```

Also test frontier selection, exact detached commit, request mutation after
claim, invalid produced JSON quarantine, atomic verdict publication, worktree
cleanup after failure, and runtime-source checksum logging.

- [ ] **Step 2: Verify RED and implement worker lifecycle**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_agent_review_worker.py -k 'lock or backoff or mutation'
```

`worker.py --once` acquires `locks/external-review.lock` with `fcntl.flock`,
asks the contract layer for the oldest valid frontier, freezes its request
hash, creates a detached worktree, builds a run manifest, invokes the configured
reviewer command, validates the output before `os.replace`, and always removes
the worktree. Backoff state stores `failure_kind`, `attempt`, `next_retry_at`,
and exponential delays capped at one hour. The wrapper contains only:

```zsh
#!/bin/zsh
set -euo pipefail
exec /Users/a77/finance-workspace-private/.venv-workbench/bin/python \
  -m scripts.agent_review.worker --poll-seconds "${1:-20}"
```

- [ ] **Step 3: Run tests and commit**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_agent_review_worker.py
git add scripts/agent_review/worker.py scripts/agent_review/reviewer_worker.sh \
  intelligence/tests/test_agent_review_worker.py
git commit -m "feat: run independent reviews with bounded backoff"
```

---

### Task 6: Add bounded Producer fallback without release authority

**Files:**
- Create: `scripts/agent_review/producer_fallback.py`
- Modify: `scripts/agent_review/worker.py`
- Modify: `intelligence/tests/test_agent_review_worker.py`
- Modify: `intelligence/tests/test_agent_review_gate.py`

- [ ] **Step 1: Write failing fallback tests**

```python
def test_inactive_external_worker_can_create_provisional_only(worker_case):
    worker_case.mark_external_inactive("budget")
    result = worker_case.run_fallback_once()
    assert result.authority == "provisional"
    assert not (worker_case.state_root / "verdicts" / f"{result.review_id}.json").exists()


def test_fallback_refuses_release_and_third_speculative_slice(worker_case):
    worker_case.add_two_provisional_slices()
    assert worker_case.run_fallback_once().status == "WAIT"
    worker_case.pending.intensity = "release"
    assert worker_case.run_fallback_once().status == "WAIT_EXTERNAL"
```

Ensure the fake Codex reviewer runs the exact mechanical test manifest and that
a failing test produces `CHANGES_REQUIRED` provisional evidence, not a pass.

- [ ] **Step 2: Implement fallback lane**

`producer_fallback.py --once` first consumes `compute_gate()`. It is eligible
only after observable external inactivity/SLA expiry, creates its own detached
worktree, runs every mechanical check, optionally calls the configured Codex
review command for falsification, and writes to `provisional-verdicts/` with:

```json
{
  "reviewer": "codex:producer-fallback",
  "reviewer_class": "producer_fallback",
  "authority": "provisional"
}
```

It cannot write official verdicts, cannot handle release intensity, and cannot
override external `CHANGES_REQUIRED`.

- [ ] **Step 3: Verify combined state machine and commit**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_agent_review_contract.py \
  intelligence/tests/test_agent_review_gate.py \
  intelligence/tests/test_agent_review_worker.py
git add scripts/agent_review/producer_fallback.py scripts/agent_review/worker.py \
  intelligence/tests/test_agent_review_worker.py \
  intelligence/tests/test_agent_review_gate.py
git commit -m "feat: bound provisional review fallback"
```

---

### Task 7: Prove the loop end to end and activate it

**Files:**
- Modify: `scripts/agent_review/REVIEWER_PROMPT.md`
- Create: `scripts/agent_review/bootstrap_runtime.sh`
- Create: `docs/verification/dual-lane-agent-review-loop-2026-07-26.md`
- Modify: `intelligence/tests/test_agent_review_worker.py`

- [ ] **Step 1: Add the deterministic fake-reviewer acceptance scenario**

One test must create three commits in a temporary Git repository and prove this
event sequence without a live model:

```text
submit A -> fake Claude budget failure -> provisional PASS A
submit B -> provisional PASS B -> submit C denied
external CHANGES_REQUIRED A -> B tainted -> FIX
repair D -> external PASS D -> debt zero -> IMPLEMENT_NEXT
release request -> external PASS + full regression manifest -> RELEASE_CHECK
```

The same test asserts no self-signed output appears under `verdicts/`, no
request is mutated, and the second worker never acquires the lock.

- [ ] **Step 2: Run deterministic acceptance and full clean regression**

```bash
env -u FORESIGHT_USERS_DIR -u FORESIGHT_USER -u SUBCONSCIOUS_VAULT \
  -u AGENT_MEMORY_VAULT \
  /Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_agent_review_contract.py \
  intelligence/tests/test_agent_review_gate.py \
  intelligence/tests/test_agent_review_worker.py

env -u FORESIGHT_USERS_DIR -u FORESIGHT_USER -u SUBCONSCIOUS_VAULT \
  -u AGENT_MEMORY_VAULT \
  /Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q \
  intelligence/tests
```

Expected: both suites pass; no live Claude/Codex call or live benchmark runs.

- [ ] **Step 3: Bootstrap mutable state without rewriting legacy files**

`bootstrap_runtime.sh` creates missing state directories, copies the versioned
prompt/worker with source commit and checksum metadata, classifies legacy
records into a derived report, and leaves old requests/verdicts byte-identical.
Run it against `/Users/a77/.finance-runtime/agent-review-loop` and verify the
classification includes Codex self-reviews, abandoned commits, ARL-0014 as the
first external review, and ARL-0015 as bootstrap provisional.

- [ ] **Step 4: Submit the schema-2 milestone request and run a fake smoke**

Use `submit.py` for the exact implementation commit. First run `worker.py
--once` with a fake reviewer executable that writes a valid external PASS; then
delete only the fake verdict for the new request, preserving its smoke log.
Confirm `gate.py` returns `IMPLEMENT_NEXT` for the fake scenario and never
returns `RELEASE_CHECK` from provisional state.

- [ ] **Step 5: Start the real worker and record health**

```bash
tmux new-session -d -s finance-agent-review \
  'cd /Users/a77/.finance-runtime/agent-runtime-backends-c4673667 && \
   scripts/agent_review/reviewer_worker.sh 20'
```

Record PID/session, versioned source checksum, current request ID, gate JSON,
and no-canonical-impact proof in the verification document. Do not wait for
human relay; if Claude is inactive, the bounded fallback may authorize at most
two later development slices.

- [ ] **Step 6: Commit documentation and request external milestone review**

```bash
git add scripts/agent_review/REVIEWER_PROMPT.md \
  scripts/agent_review/bootstrap_runtime.sh \
  docs/verification/dual-lane-agent-review-loop-2026-07-26.md \
  intelligence/tests/test_agent_review_worker.py
git commit -m "test: verify dual lane agent review loop"
```

The request intensity is `milestone`. Release remains blocked until the exact
tip receives a valid external PASS and provisional debt is zero.

---

## Post-Loop Runtime Sequence

Once the loop gate returns `IMPLEMENT_NEXT`, continue the approved Adaptive
Runtime plan in these independently reviewed slices:

1. Wire `runtime.start -> verify -> RepairGoal -> same EpisodeSession.resume ->
   new model-owned action -> reverify` without constructing a second history,
   QueryLedger, EvidenceLedger, or RootBudgetLedger.
2. Add typed `FinanceQuery + EvidenceSearch`; unrestricted SQL remains a
   benchmark-only capability.
3. Add `ModeGovernor` and dynamic budgets derived from unresolved answer and
   evidence gaps.
4. Add separability-gated deep branches; no default subagent fan-out.
5. Integrate UI/SSE progress from runtime events without exposing control-plane
   prompts, repair goals, or internal traces as answer prose.
6. Run deterministic full regression, then one frozen live benchmark only at
   release intensity.

Each slice must call `gate.py` before editing, use `submit.py` after committing,
and stop at provisional depth two. No step may merge `main`, switch canonical
8792, or publish a release without explicit user authorization.

---

## Plan Self-Review

- Every design requirement has an implementation task: provenance and schema
  (Tasks 1-3), Producer authority and bounded debt (Task 4), lock/backoff
  (Task 5), fallback (Task 6), deterministic/live operational proof (Task 7).
- Release authority is never inferred from a file's presence and is never
  granted by Codex self-review.
- Mechanical artifact tests are independently recomputed by submitter,
  validator, and worker.
- Runtime files are isolated from Git; tests use temporary roots and fake
  reviewers, so the suite has no model cost.
- The plan contains no unrestricted SQL, default subagent spawning, relaxed
  verifier thresholds, live benchmark loops, or canonical runtime mutation.
