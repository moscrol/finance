# Acceptance Completion Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the autonomous 2026-08-01 acceptance handoff items with a cross-run three-axis board, provenance-bound reference comparison, synthesis diagnostics, selector resolution evidence, and one B/C live baseline.

**Architecture:** Keep immutable run artifacts and the sealed case bank as sources of truth. Add focused pure modules for run selection, axis projection, comparison artifacts, and selector metrics; keep `acceptance.py` as CLI/renderer and emit synthesis reasons at the runtime boundary that knows them.

**Tech Stack:** Python 3.12, dataclasses/enums, JSON/SHA-256, argparse, pytest, existing Workbench HTTP/trace APIs, existing `llm_refine` provider seam.

---

## File map

- Create `intelligence/eval/acceptance_runs.py`: validate run artifacts and select each case's newest stored execution.
- Create `intelligence/eval/acceptance_axes.py`: typed delivery/information/credibility projections.
- Create `intelligence/eval/acceptance_comparison.py`: comparison queue, rubric binding, evaluator-result validation, canonical hashes.
- Create `intelligence/eval/selector_resolution.py`: deterministic overlap/rank/coverage metrics and experiment artifact.
- Modify `intelligence/eval/acceptance.py`: CLI wiring, trace capture, source-run and three-axis columns.
- Modify `intelligence/services/ask_types.py`: `SynthesisDiagnostic` and `AskResult` field.
- Modify `intelligence/services/ask_synthesis.py`: assign diagnostic states at synthesis boundaries.
- Modify `intelligence/services/conversation_orchestrator.py`: emit diagnostic in `answer_synthesis` trace.
- Create focused tests under `intelligence/tests/` and final verification/decision documents under `docs/verification/`, `docs/decisions/`, and `docs/handoffs/`.

### Task 1: Cross-run case catalog

**Files:**
- Create: `intelligence/eval/acceptance_runs.py`
- Create: `intelligence/tests/test_acceptance_runs.py`
- Modify: `intelligence/eval/acceptance.py` (`latest_run`, `cmd_board`, observation source selection)

- [ ] **Step 1: Write failing catalog tests**

```python
def test_latest_case_runs_preserve_cases_from_separate_run_files(tmp_path: Path) -> None:
    write_run(tmp_path / "20260801T010000Z.json", "20260801T010000Z", [case("A1-market-overview", "high_freq")])
    write_run(tmp_path / "20260801T020000Z.json", "20260801T020000Z", [case("B1-theme-photoresist", "mid_freq")])

    selected = select_latest_case_runs(
        tmp_path,
        {"A1-market-overview": "high_freq", "B1-theme-photoresist": "mid_freq"},
    )

    assert selected["A1-market-overview"].source_path.name == "20260801T010000Z.json"
    assert selected["B1-theme-photoresist"].source_path.name == "20260801T020000Z.json"


def test_newer_run_replaces_only_cases_it_contains(tmp_path: Path) -> None:
    write_run(tmp_path / "20260801T010000Z.json", "20260801T010000Z", [case("A1-market-overview", "high_freq"), case("A2-next-day-call", "high_freq")])
    write_run(tmp_path / "20260801T020000Z.json", "20260801T020000Z", [case("A1-market-overview", "high_freq")])

    selected = select_latest_case_runs(tmp_path, CASE_TIERS)
    assert selected["A1-market-overview"].generated_at == "20260801T020000Z"
    assert selected["A2-next-day-call"].generated_at == "20260801T010000Z"


@pytest.mark.parametrize("mutation", ["unknown_case", "wrong_tier", "duplicate_case", "bad_json"])
def test_invalid_run_fails_closed(tmp_path: Path, mutation: str) -> None:
    write_mutated_run(tmp_path, mutation)
    with pytest.raises(RunArtifactError):
        select_latest_case_runs(tmp_path, CASE_TIERS)
```

- [ ] **Step 2: Run tests and confirm the missing module fails**

Run:
```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q intelligence/tests/test_acceptance_runs.py
```

Expected: collection error for `intelligence.eval.acceptance_runs`.

- [ ] **Step 3: Implement the catalog**

```python
@dataclass(frozen=True)
class SelectedCaseRun:
    case_id: str
    tier: str
    generated_at: str
    source_path: Path
    source_sha256: str
    run_record: Mapping[str, Any]
    case_run: Mapping[str, Any]


def select_latest_case_runs(
    run_dir: Path,
    case_tiers: Mapping[str, str],
) -> dict[str, SelectedCaseRun]:
    selected: dict[str, SelectedCaseRun] = {}
    for path in sorted(run_dir.glob("*.json")):
        record = load_validated_run(path, case_tiers)
        for case_run in record["cases"]:
            candidate = SelectedCaseRun(
                case_id=case_run["case_id"],
                tier=case_run["tier"],
                generated_at=record["generated_at"],
                source_path=path,
                source_sha256=sha256_file(path),
                run_record=record,
                case_run=case_run,
            )
            previous = selected.get(candidate.case_id)
            if previous is None or (candidate.generated_at, path.name) > (
                previous.generated_at,
                previous.source_path.name,
            ):
                selected[candidate.case_id] = candidate
    return selected
```

`load_validated_run` must reject non-object JSON, missing/invalid `generated_at`, non-list `cases`, duplicate case ids, unknown case ids, and tier mismatches.

- [ ] **Step 4: Wire the board to the catalog and support explicit run output**

Replace single `latest_run()` lookup with `select_latest_case_runs`. Add a `来源` column using `source_path.stem[-7:]`, list contributing run stems in the header, and keep rows without a selected run as `NOT_RUN`. If `--truth-observations` or `--experience-labels` is supplied without `--run`, return a clear error because the current artifact contract is single-run-bound.

Add optional `run --output PATH`. When supplied, write exactly that path and refuse to overwrite an existing file; without it, retain the timestamp default. This gives live receipts stable names without changing historical compatibility.

- [ ] **Step 5: Run focused tests**

Run:
```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q intelligence/tests/test_acceptance_runs.py intelligence/tests/test_acceptance_verdict.py
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add intelligence/eval/acceptance_runs.py intelligence/eval/acceptance.py intelligence/tests/test_acceptance_runs.py
git commit -m "feat: aggregate acceptance cases across runs"
```

### Task 2: Three-axis acceptance projection

**Files:**
- Create: `intelligence/eval/acceptance_axes.py`
- Create: `intelligence/tests/test_acceptance_axes.py`
- Modify: `intelligence/eval/acceptance.py` (`cmd_board` table and summaries)

- [ ] **Step 1: Write failing projection tests**

```python
def test_delivery_does_not_claim_truth() -> None:
    verdict = case_verdict(operational=OperationalState.COMPLETED, truth=VerdictState.FAIL)
    axes = project_axes(verdict)
    assert axes.delivery.state is AxisState.PASS
    assert axes.credibility.state is AxisState.FAIL


def test_degraded_delivery_is_partial() -> None:
    axes = project_axes(case_verdict(operational=OperationalState.DEGRADED, truth=VerdictState.PASS))
    assert axes.delivery.state is AxisState.PARTIAL


def test_missing_information_observation_is_not_evaluated() -> None:
    axes = project_axes(case_verdict(operational=OperationalState.COMPLETED, truth=VerdictState.PASS))
    assert axes.information.state is AxisState.NOT_EVALUATED


def test_unreproducible_truth_remains_unjudgeable() -> None:
    axes = project_axes(case_verdict(operational=OperationalState.COMPLETED, truth=VerdictState.UNJUDGEABLE))
    assert axes.credibility.state is AxisState.UNJUDGEABLE
```

- [ ] **Step 2: Run tests and confirm the missing module fails**

Run:
```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q intelligence/tests/test_acceptance_axes.py
```

Expected: collection error for `acceptance_axes`.

- [ ] **Step 3: Implement typed axes**

```python
class AxisState(str, Enum):
    PASS = "pass"
    PARTIAL = "partial"
    FAIL = "fail"
    UNJUDGEABLE = "unjudgeable"
    NOT_EVALUATED = "not_evaluated"
    NOT_RUN = "not_run"


@dataclass(frozen=True)
class AxisVerdict:
    state: AxisState
    reason: str


@dataclass(frozen=True)
class AcceptanceAxes:
    delivery: AxisVerdict
    information: AxisVerdict
    credibility: AxisVerdict


def project_axes(
    verdict: CaseVerdict,
    information: Mapping[str, Any] | None = None,
) -> AcceptanceAxes:
    return AcceptanceAxes(
        delivery=project_delivery(verdict.operational),
        information=project_information(information),
        credibility=project_credibility(verdict.truth),
    )
```

Information observations accept only `workbench_wins`, `tie`, `knevo_wins`, or `not_evaluated`; unknown values fail closed.

- [ ] **Step 4: Add board columns and separate summaries**

Render `送达`, `信息量`, and `可信度` columns alongside `运行`, `真值`, and `体验`. Summaries count each axis independently. Do not compute an overall numeric product or change `truth_tally`.

- [ ] **Step 5: Run focused tests and board replay**

Run:
```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q intelligence/tests/test_acceptance_axes.py intelligence/tests/test_acceptance_runs.py intelligence/tests/test_acceptance_verdict.py
KNOWLEDGE_WIKI=/Users/a77/knowledge-base-private/wiki /Users/a77/finance-workspace-private/.venv-workbench/bin/python -m intelligence.eval.acceptance board
```

Expected: tests pass; board shows A rows from the latest A run and all unrun B/C rows with three axes.

- [ ] **Step 6: Commit**

```bash
git add intelligence/eval/acceptance_axes.py intelligence/eval/acceptance.py intelligence/tests/test_acceptance_axes.py
git commit -m "feat: expose acceptance delivery information credibility axes"
```

### Task 3: Provenance-bound reference comparison

**Files:**
- Create: `intelligence/eval/acceptance_comparison.py`
- Create: `intelligence/eval/cases/acceptance_information_rubric.md`
- Create: `intelligence/tests/test_acceptance_comparison.py`
- Modify: `intelligence/eval/acceptance.py` (comparison CLI and `--information-comparisons`)

- [ ] **Step 1: Write failing integrity tests**

```python
def test_valid_comparison_result_binds_both_answers(tmp_path: Path) -> None:
    queue = build_comparison_queue(run_path=RUN, agent="knevo")
    result = signed_result_for(queue, case_id="A1-market-overview", winner="tie")
    artifact = load_comparison_result(write_json(tmp_path / "result.json", result), queue)
    assert artifact.case_observations["A1-market-overview"]["state"] == "tie"


@pytest.mark.parametrize(
    "mutation",
    ["run_hash", "cases_hash", "overlay_hash", "rubric_hash", "snapshot_hash", "artifact_hash"],
)
def test_comparison_mutation_fails_closed(tmp_path: Path, mutation: str) -> None:
    path, queue = write_mutated_comparison(tmp_path, mutation)
    with pytest.raises(ComparisonArtifactError):
        load_comparison_result(path, queue)


def test_ineligible_or_missing_snapshot_is_not_queued() -> None:
    queue = build_comparison_queue(run_path=RUN, agent="knevo")
    assert queue.entries["A8-market-stage"].status == "ineligible"
    assert queue.entries["A9-sentiment-contradiction"].status == "missing"
```

- [ ] **Step 2: Run tests and confirm the missing module fails**

Run:
```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q intelligence/tests/test_acceptance_comparison.py
```

Expected: collection error.

- [ ] **Step 3: Implement queue and result models**

```python
@dataclass(frozen=True)
class ComparisonEntry:
    case_id: str
    status: str
    question: str
    workbench_answer: str
    workbench_answer_sha256: str
    reference_agent: str
    reference_answer: str | None
    reference_answer_sha256: str | None
    reference_path: str | None
    reason: str


@dataclass(frozen=True)
class ComparisonQueue:
    run_path: Path
    run_sha256: str
    cases_sha256: str
    overlay_sha256: str
    rubric_sha256: str
    entries: Mapping[str, ComparisonEntry]
```

Use `acceptance_reference_eligibility.json` to exclude missing, aliased, temporally incompatible, or dimension-ineligible snapshots. Canonicalize JSON without the artifact's own hash before computing `artifact_sha256`.

- [ ] **Step 4: Add CLI commands**

Add:

```bash
python -m intelligence.eval.acceptance comparison-pack --run intelligence/eval/runs/20260801T035325Z.json --agent knevo --output /tmp/acceptance-a-knevo-queue.json
python -m intelligence.eval.acceptance validate-comparison /tmp/acceptance-a-knevo-result.json --queue /tmp/acceptance-a-knevo-queue.json
python -m intelligence.eval.acceptance board --information-comparisons /tmp/acceptance-a-knevo-result.json --run intelligence/eval/runs/20260801T035325Z.json
```

`comparison-pack` performs no model call. A validated result must record evaluator id/kind/model/independence and one of `workbench_wins|tie|knevo_wins|not_evaluated` per queued case.

- [ ] **Step 5: Run focused tests and export an A comparison pack**

Run:
```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q intelligence/tests/test_acceptance_comparison.py intelligence/tests/test_acceptance_axes.py
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m intelligence.eval.acceptance comparison-pack --run intelligence/eval/runs/20260801T035325Z.json --agent knevo --output /tmp/acceptance-a-knevo-queue.json
```

Expected: tests pass; queue contains only cases with a valid Workbench answer and eligible Knevo snapshot, and explicitly lists missing/ineligible cases.

- [ ] **Step 6: Commit**

```bash
git add intelligence/eval/acceptance_comparison.py intelligence/eval/cases/acceptance_information_rubric.md intelligence/eval/acceptance.py intelligence/tests/test_acceptance_comparison.py
git commit -m "feat: add provenance-bound acceptance comparisons"
```

### Task 4: Structured synthesis diagnostics

**Files:**
- Modify: `intelligence/services/ask_types.py`
- Modify: `intelligence/services/ask_synthesis.py`
- Modify: `intelligence/services/conversation_orchestrator.py`
- Modify: `intelligence/eval/acceptance.py` (`TurnTrace`, `_fill_run_detail`)
- Modify: `intelligence/tests/test_conversation_orchestrator.py`
- Modify: `intelligence/tests/test_acceptance_verdict.py` or create `intelligence/tests/test_acceptance_trace_capture.py`

- [ ] **Step 1: Write failing runtime and capture tests**

```python
def test_synthesis_without_messages_records_not_prepared() -> None:
    result = AskResult(query="q", trade_date=None, matched_theme=None, candidate_tier=None, priority_score=None)
    prepared = PreparedAnswer(options=AskOptions(query="q"), result=result)
    synthesize_prepared_answer(prepared)
    assert result.synthesis_diagnostic.state == "not_prepared"
    assert result.synthesis_diagnostic.reason_code == "no_prepared_messages"


def test_orchestrator_trace_emits_structured_synthesis_diagnostic() -> None:
    payload = run_orchestrator_fixture_with_rejected_grounded_answer()
    event = next(e for e in payload.trace if e["name"] == "answer_synthesis")
    assert event["payload"]["diagnostic"]["state"] == "rejected"
    assert "prepared_messages" not in json.dumps(event, ensure_ascii=False)


def test_acceptance_capture_reads_answer_synthesis_diagnostic(monkeypatch) -> None:
    monkeypatch.setattr(acceptance, "_get", fake_trace_with_synthesis_diagnostic)
    trace = TurnTrace(question="q", run_id="run-1")
    acceptance._fill_run_detail("http://base", trace)
    assert trace.synthesis_diagnostic["reason_code"] == "claim_binding_failed"
```

- [ ] **Step 2: Run tests and verify failure**

Run:
```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q intelligence/tests/test_conversation_orchestrator.py -k synthesis_diagnostic intelligence/tests/test_acceptance_trace_capture.py
```

Expected: failures because `SynthesisDiagnostic` and capture fields do not exist.

- [ ] **Step 3: Implement the typed diagnostic**

```python
@dataclass(frozen=True)
class SynthesisDiagnostic:
    state: str = "not_requested"
    reason_code: str = "not_requested"
    detail: str = "synthesis was not requested"
    prepared_message_count: int = 0
    candidate_claim_count: int = 0
    bound_claim_count: int = 0
```

Add `synthesis_diagnostic: SynthesisDiagnostic` to `AskResult`. At each synthesis boundary replace the diagnostic with a specific immutable value: `not_prepared/no_prepared_messages`, `rejected/grounded_required_fallback`, `failed/provider_unavailable`, or `accepted/validated`. Sanitize and cap detail to 200 characters.

- [ ] **Step 4: Emit and capture the trace**

In `conversation_orchestrator.py`, emit `diagnostic=asdict(result.synthesis_diagnostic)` under `answer_synthesis`. In `_fill_run_detail`, retain both step names and the bounded diagnostic payload from that event. Old trace formats yield `{}`.

- [ ] **Step 5: Run focused runtime tests**

Run:
```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q intelligence/tests/test_conversation_orchestrator.py -k 'synthesis or fallback' intelligence/tests/test_acceptance_trace_capture.py intelligence/tests/test_grounded_presenter_general.py
```

Expected: all selected tests pass.

- [ ] **Step 6: Commit**

```bash
git add intelligence/services/ask_types.py intelligence/services/ask_synthesis.py intelligence/services/conversation_orchestrator.py intelligence/eval/acceptance.py intelligence/tests/test_conversation_orchestrator.py intelligence/tests/test_acceptance_trace_capture.py
git commit -m "fix: expose synthesis degradation diagnostics"
```

### Task 5: Selector resolution experiment

**Files:**
- Create: `intelligence/eval/selector_resolution.py`
- Create: `intelligence/tests/test_selector_resolution.py`
- Modify: `intelligence/eval/acceptance.py` only if wiring the CLI here; otherwise give the module its own `main()`.

- [ ] **Step 1: Write failing metric and artifact tests**

```python
def test_pairwise_jaccard_and_rank_overlap() -> None:
    report = analyze_selector_results(
        {
            "beneficiary": selection(["宁德时代", "赣锋锂业", "当升科技"]),
            "expansion": selection(["当升科技", "宁德时代", "亿纬锂能"]),
        }
    )
    pair = report.pairs[0]
    assert pair.jaccard == pytest.approx(0.5)
    assert pair.top3_changed == 3


def test_all_identical_lists_are_not_discriminative() -> None:
    report = analyze_selector_results({"a": selection(["甲", "乙"]), "b": selection(["甲", "乙"])})
    assert report.outcome == "indistinguishable"


def test_provider_fallback_is_inconclusive() -> None:
    report = analyze_selector_results({"a": fallback_selection(), "b": selection(["甲"])})
    assert report.outcome == "unjudgeable"


def test_hallucinated_name_invalidates_experiment() -> None:
    report = analyze_selector_results({"a": selection(["候选外"], hallucinated=1), "b": selection(["甲"])})
    assert report.outcome == "unjudgeable"
```

- [ ] **Step 2: Run tests and confirm missing module failure**

Run:
```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q intelligence/tests/test_selector_resolution.py
```

Expected: collection error.

- [ ] **Step 3: Implement deterministic metrics**

```python
@dataclass(frozen=True)
class PairwiseResolution:
    left: str
    right: str
    jaccard: float
    top3_changed: int
    rank_overlap: float


@dataclass(frozen=True)
class SelectorResolutionReport:
    outcome: str
    pairs: tuple[PairwiseResolution, ...]
    unique_ordered_lists: int
    union_size: int
    reason: str
```

Use deterministic set Jaccard and rank-biased overlap with persistence `p=0.9`. Mark fallback or hallucination `unjudgeable`, one unique ordered list `indistinguishable`, and otherwise `discriminative`.

- [ ] **Step 4: Add controlled live probe**

Expose a command that freezes the concept candidate pool once, runs the four predeclared intents through `select_exposures`, and writes one JSON artifact containing candidate-pool SHA256, questions, results, model/provider, code revision, and the deterministic report. Do not change production ranking or candidate fields.

- [ ] **Step 5: Run focused tests and an offline fake probe**

Run:
```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q intelligence/tests/test_selector_resolution.py intelligence/tests/test_exposure_selector.py intelligence/tests/test_exposure_ranking.py
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add intelligence/eval/selector_resolution.py intelligence/tests/test_selector_resolution.py
git commit -m "test: measure exposure selector intent resolution"
```

### Task 6: Live baseline, comparison receipt, and decision handoff

**Files:**
- Create: `docs/verification/2026-08-01-b-c-acceptance-baseline.md`
- Create: `docs/verification/2026-08-01-exposure-selector-resolution.md`
- Create: `docs/decisions/2026-08-01-acceptance-open-decisions.md`
- Create: `docs/handoffs/2026-08-01e-acceptance-completion-loop.md`
- Add generated run JSON and comparison artifacts under their existing repository locations only after secret/size review.

- [ ] **Step 1: Run pre-live regression and seal checks**

Run:
```bash
find . -name __pycache__ -type d -exec rm -rf {} +
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q intelligence/tests/test_acceptance_verdict.py intelligence/tests/test_acceptance_runs.py intelligence/tests/test_acceptance_axes.py intelligence/tests/test_acceptance_comparison.py intelligence/tests/test_acceptance_trace_capture.py intelligence/tests/test_selector_resolution.py
shasum -a 256 intelligence/eval/cases/acceptance_cases.json
```

Expected: focused tests pass; SHA256 is `a25c68253a92be536b94d2403ffa010b6cd15a20b7eea581450159cb6444a1c6`.

- [ ] **Step 2: Restart and verify canary 8793**

Use the existing `/tmp/start-canary-8793.sh`, then verify:

```bash
PID=$(lsof -ti tcp:8793 -sTCP:LISTEN | head -1)
grep -c 'address already in use' /tmp/canary-8793.log
ps eww "$PID" | tr ' ' '\n' | grep '^PYTHONPATH='
lsof -a -p "$PID" -d cwd -Fn
ps eww "$PID" | tr ' ' '\n' | grep -cE '^(RAG_|KB_RAG)'
```

Expected: no bind error, cwd and PYTHONPATH equal this work clone, four RAG variables.

- [ ] **Step 3: Run A2 diagnostic, B, and C exactly once**

```bash
PY=/Users/a77/finance-workspace-private/.venv-workbench/bin/python
$PY -m intelligence.eval.acceptance run --case A2-next-day-call --base http://127.0.0.1:8793 --user default --output intelligence/eval/runs/20260801-a2-diagnostic.json
$PY -m intelligence.eval.acceptance run --tier mid_freq --base http://127.0.0.1:8793 --user default --output intelligence/eval/runs/20260801-b-midfreq.json
$PY -m intelligence.eval.acceptance run --tier long_tail --base http://127.0.0.1:8793 --user default --output intelligence/eval/runs/20260801-c-longtail.json
```

Expected: each preflight passes; three new run artifacts are written. C6 truth is unjudgeable.

- [ ] **Step 4: Render the aggregate board and comparison queue**

```bash
KNOWLEDGE_WIKI=/Users/a77/knowledge-base-private/wiki $PY -m intelligence.eval.acceptance board
$PY -m intelligence.eval.acceptance comparison-pack --run intelligence/eval/runs/20260801-b-midfreq.json --agent knevo --output /tmp/acceptance-b-knevo-queue.json
$PY -m intelligence.eval.acceptance comparison-pack --run intelligence/eval/runs/20260801-c-longtail.json --agent knevo --output /tmp/acceptance-c-knevo-queue.json
```

Expected: board has all 28 cases with A/B/C source runs; queue includes only eligible frozen comparisons and names missing Codex/Knevo references.

- [ ] **Step 5: Run the selector live experiment once**

```bash
$PY -m intelligence.eval.selector_resolution probe --concept 固态电池 --output docs/verification/2026-08-01-exposure-selector-resolution.json
```

Expected: artifact reports `discriminative`, `indistinguishable`, or `unjudgeable` with zero hidden fallback.

- [ ] **Step 6: Write receipts and decision packages**

The B/C receipt must include run hashes, source revision/backend, operational/truth/axis tallies, C6 exclusion, and A2 diagnostic. The decision document must give options, consequences, recommendation, exact files, tests, and commands for K, A8/C6, Codex authentication, and J without implementing them.

- [ ] **Step 7: Run full regression and risk scan**

```bash
find . -name __pycache__ -type d -exec rm -rf {} +
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m ruff check .
git diff --check
git status --short
```

Expected: new tests pass; existing failures and Ruff findings are identical or fewer by exact identity; no forbidden files are staged.

- [ ] **Step 8: Commit final receipts**

```bash
git add docs/verification/2026-08-01-b-c-acceptance-baseline.md docs/verification/2026-08-01-exposure-selector-resolution.md docs/decisions/2026-08-01-acceptance-open-decisions.md docs/handoffs/2026-08-01e-acceptance-completion-loop.md intelligence/eval/runs/20260801-a2-diagnostic.json intelligence/eval/runs/20260801-b-midfreq.json intelligence/eval/runs/20260801-c-longtail.json
git commit -m "docs: record acceptance completion loop evidence"
```

Do not push and do not merge `main`.
