# FinanceQuery and EvidenceSearch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the primary model two honest, flexible read-only tools—typed structured finance querying and closed-loop evidence search—without allowing raw production SQL or breaking one-episode repair continuity.

**Architecture:** `ResearchToolRegistry` becomes the single deep seam for per-tool JSON Schema, argument parsing, canonical deduplication, authorization, cutoff filtering, and public observations. `FinanceQuery` hides DuckDB physical tables behind a semantic dataset registry and compiles model-selected fields into parameterized read-only SQL. `EvidenceSearch` wraps the existing narrow/broad/counter retrieval loop and projects only cutoff-valid, semantically eligible evidence into the model observation. Both tools enter the existing `EpisodeToolBatchSession`, `QueryLedger`, `EvidenceLedger`, root budget, and verifier path; legacy snapshots remain migration adapters with truthful no-argument schemas.

**Tech Stack:** Python dataclasses and typing, DuckDB read-only connections, existing KB hybrid retrieval and semantic evidence judge, pytest, Ruff.

---

## Public seams under test

1. `ResearchToolRegistry.tool_definitions()` and `ResearchToolRegistry.prepare()` / `execute()` expose and enforce the exact schema for each tool.
2. `FinanceQuery.run()` accepts only a `FinanceQuerySpec` plus code-owned cutoff/deadline/cancellation and returns evidence or a typed failure.
3. `EvidenceSearch.search()` returns evidence, coverage, gaps, attempts, and a model-safe observation that excludes discarded and future material.
4. `EpisodeToolBatchSession.execute()` accepts model-generated structured arguments, deduplicates canonical calls, and appends both tools to the same episode state.

Tests must assert behavior through these seams. They must not assert private helper calls or full physical SQL strings.

### Task 1: Make tool arguments schema-owned

**Files:**
- Modify: `intelligence/services/research_tool_registry.py`
- Modify: `intelligence/services/episode_tool_batch.py`
- Modify: `intelligence/services/openai_agents_runtime.py`
- Modify: `intelligence/tests/test_episode_tool_batch.py`
- Modify: `intelligence/tests/test_openai_agents_runtime.py`
- Modify: `intelligence/tests/test_information_cutoff.py`

- [ ] **Step 1: Write failing registry and batch tests**

Add tests proving that a query tool publishes `{query: string}`, a snapshot publishes an empty-object schema, a snapshot rejects a fake `query`, a typed tool receives its complete object, and two objects with the same values but different key order deduplicate.

```python
def test_tool_definitions_use_each_specs_own_json_schema() -> None:
    definitions = registry.tool_definitions()
    assert definitions[0]["function"]["parameters"] == QUERY_PARAMETERS
    assert definitions[1]["function"]["parameters"] == EMPTY_PARAMETERS


def test_no_argument_snapshot_rejects_fake_query() -> None:
    result = session.execute(
        (ModelToolCall("snapshot-1", "market_data", {"query": "ignored"}),),
        registry=registry,
        context=context,
        remaining_slots=1,
    )
    assert result.items[0].status == "rejected"
    assert result.items[0].error == "invalid_arguments"
```

- [ ] **Step 2: Run the new tests and verify RED**

Run:

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/pytest \
  intelligence/tests/test_episode_tool_batch.py \
  intelligence/tests/test_openai_agents_runtime.py \
  intelligence/tests/test_information_cutoff.py -q
```

Expected: failures show that every tool still advertises and requires `query`.

- [ ] **Step 3: Add one prepared-arguments interface**

Implement immutable per-tool schemas and parsers in `research_tool_registry.py`:

```python
ToolInput = object
ToolArgumentParser = Callable[[Mapping[str, object]], ToolInput]


@dataclass(frozen=True)
class PreparedToolArguments:
    raw: Mapping[str, object]
    runner_input: ToolInput
    normalized_key: str
    display_query: str


@dataclass(frozen=True)
class ToolSpec:
    name: str
    capability: str
    description: str
    cost: str
    freshness: str
    runner: Callable[[ToolInput, agent_research.AgentToolContext], ToolRunnerResult]
    query_scope: Literal["query", "episode"] = "query"
    parameters: Mapping[str, object] = field(default_factory=query_parameters)
    parse_arguments: ToolArgumentParser = parse_query_arguments
```

`ResearchToolRegistry.prepare(name, arguments)` must parse before budget reservation, serialize the raw object with sorted JSON keys for deduplication, and preserve direct-string compatibility only for existing non-model callers by converting it to `{"query": value}`. `execute()` accepts either raw arguments or an already prepared value.

- [ ] **Step 4: Pass prepared arguments through Continuous and SDK adapters**

Replace the hard-coded `set(call.arguments) == {"query"}` and string query handling in `episode_tool_batch.py`. The batch reserves only successfully prepared calls and dispatches `PreparedToolArguments` to the registry. Update `AgentsSdkTool` to carry `parameters` and `invoke: Callable[[Mapping[str, object]], ...]`; `_run_openai_agents_sdk()` must use the per-tool schema unchanged.

Legacy query runners are adapted once by `query_tool_spec()`. The three fixed snapshots use `snapshot_tool_spec()` with:

```python
{
    "type": "object",
    "properties": {},
    "additionalProperties": False,
}
```

- [ ] **Step 5: Run Task 1 tests and commit**

Run the command from Step 2 plus:

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/ruff check \
  intelligence/services/research_tool_registry.py \
  intelligence/services/episode_tool_batch.py \
  intelligence/services/openai_agents_runtime.py
```

Expected: all selected tests pass and Ruff reports no errors.

Commit:

```bash
git add intelligence/services/research_tool_registry.py \
  intelligence/services/episode_tool_batch.py \
  intelligence/services/openai_agents_runtime.py \
  intelligence/tests/test_episode_tool_batch.py \
  intelligence/tests/test_openai_agents_runtime.py \
  intelligence/tests/test_information_cutoff.py
git commit -m "refactor: make research tool arguments schema owned"
```

### Task 2: Compile semantic FinanceQuery specs safely

**Files:**
- Create: `intelligence/services/finance_query.py`
- Create: `intelligence/tests/test_finance_query.py`

- [ ] **Step 1: Write failing semantic-query tests**

Create a temporary DuckDB containing `fact_market_daily`, `fact_stock_daily`, `fact_sector_daily`, `fact_sector_stock_daily`, `fact_mainline_theme_daily`, and `fact_mainline_sector_daily`. Test a worked example:

```python
spec = FinanceQuerySpec.from_arguments(
    {
        "dataset": "market_daily",
        "metrics": ["index_return_pct", "total_amount"],
        "dimensions": ["trade_date", "market_stage"],
        "filters": [{"field": "market_stage", "op": "eq", "value": "反弹阶段"}],
        "time_range": {"start": "2026-07-20", "end": "2026-07-24"},
        "group_by": [],
        "order_by": [{"field": "trade_date", "direction": "asc"}],
        "limit": 20,
    }
)
result = query.run(spec, information_cutoff=cutoff, deadline=deadline)
assert [item.source_date for item in result.evidence] == ["2026-07-21", "2026-07-24"]
```

Also prove unknown datasets, fields, operators, order keys, and model-supplied dates later than the cutoff are rejected before a DuckDB connection executes.

- [ ] **Step 2: Run the test and verify RED**

Run:

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/pytest intelligence/tests/test_finance_query.py -q
```

Expected: import failure because `finance_query.py` does not exist.

- [ ] **Step 3: Implement typed input and a hidden dataset registry**

Define frozen `QueryFilter`, `TimeRange`, `Order`, `FinanceQuerySpec`, `FinanceQueryLimits`, `FinanceQueryAudit`, and `FinanceQueryResult`. `FinanceQuerySpec.from_arguments()` enforces exact top-level keys, non-empty selections, finite limits, and immutable tuples.

The private registry maps semantic names to physical columns. Initial production datasets are:

```python
DATASETS = {
    "market_daily": "fact_market_daily",
    "stock_daily": "fact_stock_daily",
    "sector_daily": "fact_sector_daily",
    "sector_stock_daily": "fact_sector_stock_daily",
    "mainline_theme_daily": "fact_mainline_theme_daily",
    "mainline_sector_daily": "fact_mainline_sector_daily",
}
```

Each definition declares its time dimension, public dimensions, public metrics, value type, aggregation semantics, evidence tier, and source label. Physical names never enter the JSON Schema or model observation.

- [ ] **Step 4: Implement parameterized compilation**

Compile identifiers only from the registry and values only as bound parameters. Always inject `trade_date <= ?`. Reject `time_range.end > information_cutoff.as_of_date`, `time_range.start > cutoff`, and date filters outside `time_range`. `group_by` may contain registered dimensions only; every ordered field must be selected. Clamp `limit` to the hard row cap.

The compiler returns a private plan:

```python
@dataclass(frozen=True)
class _CompiledQuery:
    sql: str
    parameters: tuple[object, ...]
    output_fields: tuple[str, ...]
    source_date_index: int
```

- [ ] **Step 5: Run Task 2 tests and commit**

Run:

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/pytest intelligence/tests/test_finance_query.py -q
/Users/a77/finance-workspace-private/.venv-workbench/bin/ruff check intelligence/services/finance_query.py \
  intelligence/tests/test_finance_query.py
```

Expected: all FinanceQuery parsing and compilation tests pass.

Commit:

```bash
git add intelligence/services/finance_query.py intelligence/tests/test_finance_query.py
git commit -m "feat: add typed semantic finance query"
```

### Task 3: Enforce FinanceQuery execution limits and evidence lineage

**Files:**
- Modify: `intelligence/services/finance_query.py`
- Modify: `intelligence/tests/test_finance_query.py`

- [ ] **Step 1: Write failing execution-boundary tests**

Test `read_only=True`, timeout interruption, cancellation before and during execution, hard row clamping, byte-cap failure, missing table failure, and evidence lineage. A result row must become one `AgentEvidence` with `tool="finance_query"`, a real `source_date`, semantic source label, `independent_key`, `internal_locator` fingerprint, and non-empty `content_hash`.

- [ ] **Step 2: Run the new cases and verify RED**

Run:

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/pytest intelligence/tests/test_finance_query.py -q
```

Expected: resource-boundary and lineage cases fail while Task 2 cases remain green.

- [ ] **Step 3: Add bounded read-only execution**

`FinanceQuery.run()` opens `duckdb.connect(path, read_only=True)`, starts a deadline timer that calls `connection.interrupt()`, polls cancellation with a stop event, fetches in bounded chunks, and closes all resources in `finally`. It rejects rows once serialized UTF-8 output exceeds `max_bytes`. It stores physical SQL only in `FinanceQueryAudit`; public evidence uses semantic fields and source labels.

- [ ] **Step 4: Run Task 3 tests and commit**

Run the Task 2 commands. Expected: all tests pass, including interruption and lineage.

Commit:

```bash
git add intelligence/services/finance_query.py intelligence/tests/test_finance_query.py
git commit -m "feat: bound finance query execution and lineage"
```

### Task 4: Adapt closed-loop retrieval as EvidenceSearch

**Files:**
- Create: `intelligence/services/evidence_search.py`
- Create: `intelligence/tests/test_evidence_search.py`
- Modify: `intelligence/services/closed_loop_retrieval.py`
- Modify: `intelligence/tests/test_closed_loop_retrieval.py`

- [ ] **Step 1: Write failing search-interface tests**

Use scripted `WikiRagResult` responses to prove:

- narrow, broad, and counter attempts are retained in order;
- conclusion, clue, counter-clue, and discarded counts are exposed;
- duplicate chunks become one evidence item;
- empty search yields a question-specific gap;
- a high-scoring future document is recorded as discarded but never appears in `evidence` or `observation`;
- a semantic judge rejection moves the hit to discarded before projection.

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/pytest \
  intelligence/tests/test_evidence_search.py \
  intelligence/tests/test_closed_loop_retrieval.py -q
```

Expected: import failure for the new adapter.

- [ ] **Step 3: Implement one deep search interface**

Add:

```python
@dataclass(frozen=True)
class EvidenceSearchCoverage:
    conclusion_count: int
    clue_count: int
    counter_count: int
    discarded_count: int
    apertures_attempted: tuple[str, ...]


@dataclass(frozen=True)
class EvidenceSearchResult:
    evidence: tuple[AgentEvidence, ...]
    observation: str
    coverage: EvidenceSearchCoverage
    gaps: tuple[str, ...]
    attempts: tuple[RetrievalAttempt, ...]
    trace: ProviderTrace
```

`EvidenceSearch.search()` receives the immutable cutoff and deadline, calls `retrieve_closed_loop()` with the remaining stage budget, applies the existing semantic judge through an injected judge adapter, deduplicates by content hash/source chunk, and projects only eligible conclusion/counter evidence. The discarded bucket stays inspector-only.

- [ ] **Step 4: Run Task 4 tests and commit**

Run the Task 4 tests plus Ruff for both modules. Expected: all pass.

Commit:

```bash
git add intelligence/services/evidence_search.py \
  intelligence/services/closed_loop_retrieval.py \
  intelligence/tests/test_evidence_search.py \
  intelligence/tests/test_closed_loop_retrieval.py
git commit -m "feat: expose closed loop evidence search"
```

### Task 5: Register both tools in one continuous Episode

**Files:**
- Modify: `intelligence/services/research_tool_registry.py`
- Modify: `intelligence/services/episode_tools.py`
- Modify: `intelligence/services/episode_factory.py`
- Modify: `intelligence/services/episode_protocol.py`
- Modify: `intelligence/tests/test_episode_tools.py`
- Modify: `intelligence/tests/test_episode_factory.py`
- Modify: `intelligence/tests/test_agent_episode.py`
- Modify: `intelligence/tests/test_openai_agents_runtime.py`

- [ ] **Step 1: Write failing integration tests**

Prove that an evidence-grounded long-tail context authorizes `finance_query` and `evidence_search` without a new question route; methodology/user-premise tasks still expose no current-world tools. Prove the model can call both tools with distinct structured arguments, receive both observations in model order, bind their hashes, and reuse the same `episode_id` during a verifier-triggered repair.

- [ ] **Step 2: Run integration tests and verify RED**

Run:

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/pytest \
  intelligence/tests/test_episode_tools.py \
  intelligence/tests/test_episode_factory.py \
  intelligence/tests/test_agent_episode.py \
  intelligence/tests/test_openai_agents_runtime.py -q
```

Expected: the new capabilities are absent from the registry/context.

- [ ] **Step 3: Compose production adapters**

In `build_episode_registry()` construct `FinanceQuery` over the canonical private DuckDB path and `EvidenceSearch` over the existing KB `retrieve()` function plus deterministic entity anchor resolution. Register typed specs with their own schemas. Keep `market_data`, `financial_data`, and `mainline_context` only as migration snapshots and change them to no-argument schemas.

For evidence-grounded long-tail tasks, `episode_factory` adds the two broad read-only capabilities to the authorization ceiling. This is a permission set, not a route plan: the model still decides whether, when, and how to call them. The episode prompt lists their real schemas/capabilities but does not prescribe order.

- [ ] **Step 4: Feed empty/coverage results into existing RepairGoal state**

Map `EvidenceSearchResult.gaps` and FinanceQuery typed failures into `ToolObservation.gaps`; let the existing `EvidenceLedger`, coverage delta, `RepairCoordinator`, root budget, and `EpisodeSession.resume()` handle them. Do not add a second retry counter or template fallback.

- [ ] **Step 5: Run integration tests and commit**

Run the Task 5 command plus:

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/pytest \
  intelligence/tests/test_episode_tool_batch.py \
  intelligence/tests/test_information_cutoff.py -q
```

Expected: all selected tests pass.

Commit:

```bash
git add intelligence/services/research_tool_registry.py \
  intelligence/services/episode_tools.py \
  intelligence/services/episode_factory.py \
  intelligence/services/episode_protocol.py \
  intelligence/tests/test_episode_tools.py \
  intelligence/tests/test_episode_factory.py \
  intelligence/tests/test_agent_episode.py \
  intelligence/tests/test_openai_agents_runtime.py
git commit -m "feat: give episodes structured query and evidence search"
```

### Task 6: Milestone verification and documentation

**Files:**
- Create: `docs/verification/finance-query-evidence-search-2026-07-27.md`
- Modify: `docs/superpowers/plans/2026-07-27-finance-query-evidence-search.md`

- [ ] **Step 1: Run focused milestone suites**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/pytest \
  intelligence/tests/test_finance_query.py \
  intelligence/tests/test_evidence_search.py \
  intelligence/tests/test_episode_tool_batch.py \
  intelligence/tests/test_episode_tools.py \
  intelligence/tests/test_episode_factory.py \
  intelligence/tests/test_agent_episode.py \
  intelligence/tests/test_openai_agents_runtime.py \
  intelligence/tests/test_information_cutoff.py -q
```

- [ ] **Step 2: Run the full deterministic suite once**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/pytest intelligence/tests -q
```

Do not run the nine-case frozen live benchmark and do not touch canonical 8792.

- [ ] **Step 3: Run static checks**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/ruff check intelligence/services intelligence/tests
git diff --check
git status --short
```

- [ ] **Step 4: Write the verification receipt**

Record exact revision, focused/full counts, cutoff negative case, schema behavior, FinanceQuery dataset surface, resource caps, EvidenceSearch bucket counts, same-episode repair assertion, Ruff result, and explicit non-actions (`no live benchmark`, `no 8792`, `no main merge`). Mark completed plan checkboxes from actual evidence only.

- [ ] **Step 5: Commit the milestone receipt**

```bash
git add docs/verification/finance-query-evidence-search-2026-07-27.md \
  docs/superpowers/plans/2026-07-27-finance-query-evidence-search.md
git commit -m "docs: verify finance query evidence search milestone"
```

## Deferred by design

- `ModeGovernor`, asynchronous deep mode, and sub-research branches start only after this tool milestone is green.
- `MemoryGate` starts only after adaptive mode has stable validated outcomes.
- Unrestricted SQL remains benchmark-only and is not registered here.
- Legacy long-tail route/contract deletion waits for the canary trigger in the approved design.
- The frozen nine-case live benchmark and Claude architecture review run only after the product milestone is frozen.
