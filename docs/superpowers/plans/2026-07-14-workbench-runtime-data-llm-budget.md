# Workbench Runtime Data, Built-in LLM, and Budget Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every Workbench research path use the canonical DuckDB/data root, give the built-in GLM one bounded synthesis opportunity, and always commit a consistent answer/report before the 60-second deadline.

**Architecture:** Create one immutable runtime-input object at the API boundary and pass it through the orchestrator and Skill context instead of letting services infer paths from source files. Keep `Evidence -> Claim -> AnswerSpec` deterministic, then expose one reusable synthesis function for Base Finance and owner results; use a shared deadline with a five-second finalization reserve and capability-based readiness.

**Tech Stack:** Python 3.12+, FastAPI, DuckDB 1.4.3 read-only queries, dataclasses, pytest, React/TypeScript, Vitest, pnpm, existing `ExecutionBudget` and structured-report/SSE protocols.

---

## File responsibility map

- `intelligence/services/runtime_inputs.py`: resolve code/data/user roots once; probe DuckDB, exports, and snapshot capabilities without mutating data.
- `intelligence/api/app.py`: create and inject runtime inputs; expose capability-based readiness; keep Keychain/provider handling unchanged.
- `intelligence/workbench_skills/contracts.py`: carry runtime inputs through the typed Skill boundary.
- `intelligence/workbench_skills/research_owner.py`: use explicit market DB/exports/wiki paths; return an AnswerSpec without owning final prose.
- `intelligence/services/conversation_orchestrator.py`: reserve finalization/synthesis time, compose owner AnswerSpecs once, and disable expensive retry work after a Skill timeout.
- `intelligence/services/ask.py`: classify derivative freshness, reject stale current candidate facts, synthesize already-built AnswerSpecs, and record model-attempt telemetry.
- `intelligence/api/structured_reports.py`: persist configured/attempted/used/fallback model state.
- `intelligence/webapp/src/types.ts` and `StructuredReportView.tsx`: render the expanded non-sensitive model state.
- Tests remain beside their existing service/API/frontend suites; a focused `test_runtime_inputs.py` owns the new path/probe contract.

### Task 1: Add an explicit runtime research-input contract

**Files:**
- Create: `intelligence/services/runtime_inputs.py`
- Create: `intelligence/tests/test_runtime_inputs.py`

- [ ] **Step 1: Write failing path-isolation and capability-probe tests**

```python
# intelligence/tests/test_runtime_inputs.py
from pathlib import Path

import duckdb

from intelligence.services.runtime_inputs import (
    RuntimeResearchInputs,
    probe_market_inputs,
)


def test_runtime_inputs_keep_code_and_canonical_data_roots_separate(tmp_path: Path) -> None:
    code_root = tmp_path / "code-worktree"
    data_root = tmp_path / "canonical-data"
    users_root = tmp_path / "users"
    wiki_root = tmp_path / "knowledge" / "wiki"
    vector_root = tmp_path / "knowledge" / ".rag_index"

    inputs = RuntimeResearchInputs.from_roots(
        code_root=code_root,
        data_root=data_root,
        users_root=users_root,
        knowledge_wiki=wiki_root,
        vector_index_dir=vector_root,
    )

    assert inputs.code_root == code_root.resolve()
    assert inputs.data_root == data_root.resolve()
    assert inputs.market_db_path == data_root.resolve() / "db/market_feature_store.duckdb"
    assert inputs.exports_dir == data_root.resolve() / "market_feature_store/exports"
    assert inputs.market_snapshot_dir == data_root.resolve() / "market_snapshot"
    assert inputs.users_root == users_root.resolve()
    assert inputs.knowledge_wiki == wiki_root.resolve()
    assert inputs.vector_index_dir == vector_root.resolve()


def test_probe_market_inputs_reports_duckdb_cutoff_and_missing_optional_snapshot(
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "data"
    db_path = data_root / "db/market_feature_store.duckdb"
    db_path.parent.mkdir(parents=True)
    connection = duckdb.connect(str(db_path))
    connection.execute("create table fact_market_daily(trade_date date)")
    connection.execute("insert into fact_market_daily values ('2026-07-13')")
    connection.close()
    exports = data_root / "market_feature_store/exports"
    exports.mkdir(parents=True)
    (exports / "2026-07-10-theme-candidates.json").write_text("{}", encoding="utf-8")

    inputs = RuntimeResearchInputs.from_roots(
        code_root=tmp_path / "code",
        data_root=data_root,
        users_root=tmp_path / "users",
        knowledge_wiki=tmp_path / "wiki",
        vector_index_dir=tmp_path / "index",
    )
    status = probe_market_inputs(inputs)

    assert status.duckdb_available is True
    assert status.duckdb_cutoff == "2026-07-13"
    assert status.latest_export_date == "2026-07-10"
    assert status.export_freshness == "stale"
    assert status.market_snapshot_available is False
    assert status.market_data_available is True


def test_probe_market_inputs_does_not_accept_an_empty_snapshot_directory(
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "data"
    (data_root / "market_snapshot").mkdir(parents=True)
    inputs = RuntimeResearchInputs.from_roots(
        code_root=tmp_path / "code",
        data_root=data_root,
        users_root=tmp_path / "users",
        knowledge_wiki=tmp_path / "wiki",
        vector_index_dir=tmp_path / "index",
    )

    status = probe_market_inputs(inputs)

    assert status.market_snapshot_available is False
    assert status.market_snapshot_date is None
    assert status.market_data_available is False
```

- [ ] **Step 2: Run the focused tests and verify the module is missing**

Run:

```bash
uv run --with pytest --with 'duckdb==1.4.3' python -m pytest intelligence/tests/test_runtime_inputs.py -q
```

Expected: collection fails with `ModuleNotFoundError: intelligence.services.runtime_inputs`.

- [ ] **Step 3: Implement the immutable contract and read-only probe**

```python
# intelligence/services/runtime_inputs.py
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from intelligence.services.market_snapshot_contract import (
    validate_market_snapshot_root,
)


_EXPORT_DATE = re.compile(r"^(\d{4}-\d{2}-\d{2})-theme-candidates\.json$")


@dataclass(frozen=True)
class RuntimeResearchInputs:
    code_root: Path
    data_root: Path
    users_root: Path
    knowledge_wiki: Path
    vector_index_dir: Path
    market_db_path: Path
    exports_dir: Path
    market_snapshot_dir: Path

    @classmethod
    def from_roots(
        cls,
        *,
        code_root: Path,
        data_root: Path,
        users_root: Path,
        knowledge_wiki: Path,
        vector_index_dir: Path,
        market_snapshot_dir: Path | None = None,
    ) -> "RuntimeResearchInputs":
        code = code_root.expanduser().resolve()
        data = data_root.expanduser().resolve()
        return cls(
            code_root=code,
            data_root=data,
            users_root=users_root.expanduser().resolve(),
            knowledge_wiki=knowledge_wiki.expanduser().resolve(),
            vector_index_dir=vector_index_dir.expanduser().resolve(),
            market_db_path=data / "db/market_feature_store.duckdb",
            exports_dir=data / "market_feature_store/exports",
            market_snapshot_dir=(market_snapshot_dir or data / "market_snapshot")
            .expanduser()
            .resolve(),
        )


@dataclass(frozen=True)
class MarketInputStatus:
    duckdb_available: bool
    duckdb_cutoff: str | None
    latest_export_date: str | None
    export_freshness: str
    market_snapshot_available: bool
    market_snapshot_date: str | None
    market_data_available: bool
    warning: str | None = None


def _duckdb_cutoff(path: Path) -> tuple[str | None, str | None]:
    if not path.is_file():
        return None, "duckdb_missing"
    try:
        import duckdb

        connection = duckdb.connect(str(path), read_only=True)
        try:
            value = connection.execute(
                "select max(trade_date) from fact_market_daily"
            ).fetchone()[0]
        finally:
            connection.close()
    except Exception as exc:  # optional dependency / lock / schema failure
        return None, f"duckdb_unavailable:{type(exc).__name__}"
    return (str(value) if value is not None else None), None


def _latest_export_date(exports_dir: Path) -> str | None:
    if not exports_dir.is_dir():
        return None
    dates = [
        match.group(1)
        for path in exports_dir.iterdir()
        if path.is_file() and (match := _EXPORT_DATE.fullmatch(path.name))
    ]
    return max(dates, default=None)


def probe_market_inputs(inputs: RuntimeResearchInputs) -> MarketInputStatus:
    cutoff, warning = _duckdb_cutoff(inputs.market_db_path)
    export_date = _latest_export_date(inputs.exports_dir)
    if cutoff and export_date:
        freshness = "fresh" if export_date == cutoff else (
            "stale" if export_date < cutoff else "conflict"
        )
    else:
        freshness = "missing"
    snapshot_validation = validate_market_snapshot_root(
        inputs.market_snapshot_dir
    )
    snapshot_available = snapshot_validation["status"] in {"PASS", "WARN"}
    snapshot_date = (
        str(snapshot_validation.get("date") or "") or None
    )
    return MarketInputStatus(
        duckdb_available=cutoff is not None,
        duckdb_cutoff=cutoff,
        latest_export_date=export_date,
        export_freshness=freshness,
        market_snapshot_available=snapshot_available,
        market_snapshot_date=snapshot_date if snapshot_available else None,
        market_data_available=cutoff is not None or snapshot_available,
        warning=warning,
    )
```

- [ ] **Step 4: Run the new tests**

Run the Task 1 command again.

Expected: `3 passed`.

- [ ] **Step 5: Commit Task 1**

```bash
git add intelligence/services/runtime_inputs.py intelligence/tests/test_runtime_inputs.py
git commit -m "feat: define canonical workbench runtime inputs"
```

### Task 2: Propagate the canonical data root and reject stale derivatives

**Files:**
- Modify: `intelligence/api/app.py`
- Modify: `intelligence/services/conversation_orchestrator.py`
- Modify: `intelligence/workbench_skills/contracts.py`
- Modify: `intelligence/workbench_skills/research_owner.py`
- Modify: `intelligence/services/ask.py`
- Modify: `intelligence/tests/test_conversation_orchestrator.py`
- Modify: `intelligence/tests/test_workbench_research_owner_skills.py`
- Modify: `intelligence/tests/test_answer_orchestrator.py`

- [ ] **Step 1: Write failing propagation tests**

Add assertions to the existing base-Ask capture test in `test_conversation_orchestrator.py`:

```python
assert options.market_db_path == runtime_inputs.market_db_path
assert options.exports_dir == runtime_inputs.exports_dir
assert options.kb_wiki == runtime_inputs.knowledge_wiki
assert options.wiki_rag_index_dir == runtime_inputs.vector_index_dir
```

Extend the `_context(...)` fixture in `test_workbench_research_owner_skills.py` to accept `runtime_inputs`, then add:

```python
def test_research_owner_uses_explicit_runtime_data_paths(tmp_path: Path) -> None:
    captured: list[AskOptions] = []
    inputs = _runtime_inputs(tmp_path)
    store = RunStore(user_id="demo", root=tmp_path / "runs")
    run = store.create_run("深挖英维克", "ask")

    ResearchOwnerSkill(
        STOCK_DEEP_DIVE,
        answer_query_fn=lambda options: captured.append(options)
        or _result(options.query, STOCK_DEEP_DIVE.question_type, evidence_id="R1"),
    ).execute(
        _context(
            tmp_path / "code-worktree",
            store,
            run.run_id,
            "深挖英维克",
            runtime_inputs=inputs,
        )
    )

    assert captured[0].market_db_path == inputs.market_db_path
    assert captured[0].exports_dir == inputs.exports_dir
    assert captured[0].kb_wiki == inputs.knowledge_wiki
    assert captured[0].wiki_rag_index_dir == inputs.vector_index_dir
```

- [ ] **Step 2: Write a failing stale-export fact-boundary test**

```python
def test_stale_theme_export_cannot_become_current_candidate_fact(self) -> None:
    duckdb = __import__("duckdb")
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        wiki = root / "wiki"
        exports = root / "exports"
        (wiki / "relations").mkdir(parents=True)
        exports.mkdir()
        (exports / "2026-07-01-theme-candidates.json").write_text(
            json.dumps(
                {
                    "trade_date": "2026-07-01",
                    "candidates": [
                        {"canonical_concept": "液冷", "candidate_tier": "A"}
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        db_path = root / "market.duckdb"
        connection = duckdb.connect(str(db_path))
        connection.execute("create table fact_market_daily(trade_date date)")
        connection.execute("insert into fact_market_daily values ('2026-07-13')")
        connection.close()

        result = answer_query(
            AskOptions(
                query="液冷现在是不是主线",
                exports_dir=exports,
                kb_wiki=wiki,
                market_db_path=db_path,
                compose=False,
                use_modules=False,
                use_wiki_rag=False,
            )
        )

    assert result.trade_date == "2026-07-13"
    assert result.snapshot_date == "2026-07-01"
    assert result.snapshot_freshness == "stale"
    assert result.found_market is False
    assert result.candidate_tier is None
    assert any("stale_derivative" in warning for warning in result.warnings)
```

- [ ] **Step 3: Run the focused tests and verify the new assertions fail**

```bash
uv run --with pytest --with fastapi --with httpx --with pydantic --with 'duckdb==1.4.3' python -m pytest \
  intelligence/tests/test_conversation_orchestrator.py \
  intelligence/tests/test_workbench_research_owner_skills.py \
  intelligence/tests/test_answer_orchestrator.py -q
```

Expected: failures show missing `runtime_inputs`, implicit exports/wiki paths, and missing `snapshot_freshness`.

- [ ] **Step 4: Create runtime inputs once in `create_app` and inject them**

Use the source file location for `code_root`, the `create_app(repo_root=...)` value for `data_root`, and existing environment-aware knowledge paths:

```python
project_paths = default_paths()
runtime_inputs = RuntimeResearchInputs.from_roots(
    code_root=Path(__file__).resolve().parents[2],
    data_root=root,
    users_root=userspace.users_dir(),
    knowledge_wiki=project_paths.knowledge_wiki,
    vector_index_dir=project_paths.vector_index_dir,
    market_snapshot_dir=project_paths.market_snapshot_dir,
)
app.state.runtime_inputs = runtime_inputs
```

Pass `runtime_inputs` into `_run_conversation_turn(...)` and `TurnOrchestrator(...)` rather than reconstructing it inside a worker.

- [ ] **Step 5: Extend the orchestrator and Skill context**

```python
# contracts.py
runtime_inputs: RuntimeResearchInputs | None = field(
    default=None,
    repr=False,
    compare=False,
)
```

Add a required `runtime_inputs` constructor parameter to production `TurnOrchestrator`; retain a test-compatible default built from `repo_root` only inside the constructor. Populate `SkillExecutionContext.runtime_inputs` for every selected Skill.

For the base Ask call, pass all four explicit consumers:

```python
market_db_path=self.runtime_inputs.market_db_path,
exports_dir=self.runtime_inputs.exports_dir,
kb_wiki=self.runtime_inputs.knowledge_wiki,
wiki_rag_index_dir=self.runtime_inputs.vector_index_dir,
```

Apply the same values in `ResearchOwnerSkill.execute()` from `context.runtime_inputs`; fall back to `context.repo_root` only for direct unit callers that did not provide the new optional field.

- [ ] **Step 6: Add derivative freshness to `AskResult` and fail closed**

```python
snapshot_freshness: str = "missing"
```

Classify `fresh`, `stale`, `conflict`, or `missing` after reading DuckDB cutoff. When no explicit historical `options.date` is requested, only call `match_candidate()` for a `fresh` export. Preserve the old export date in telemetry and add `stale_derivative`/`conflicting_derivative` warnings; do not populate `found_market`, candidate tier, or current claims from it.

- [ ] **Step 7: Run focused and adjacent tests**

Run the Task 2 command, then:

```bash
uv run --with pytest --with fastapi --with httpx --with pydantic --with 'duckdb==1.4.3' python -m pytest \
  intelligence/tests/test_workbench_skill_router.py \
  intelligence/tests/test_workbench_api.py -q
```

Expected: all selected tests pass.

- [ ] **Step 8: Commit Task 2**

```bash
git add intelligence/api/app.py intelligence/services/conversation_orchestrator.py \
  intelligence/workbench_skills/contracts.py intelligence/workbench_skills/research_owner.py \
  intelligence/services/ask.py intelligence/tests/test_conversation_orchestrator.py \
  intelligence/tests/test_workbench_research_owner_skills.py \
  intelligence/tests/test_answer_orchestrator.py
git commit -m "fix: route workbench research through canonical data inputs"
```

### Task 3: Make readiness report market capabilities instead of one snapshot gate

**Files:**
- Modify: `intelligence/api/app.py`
- Modify: `intelligence/tests/test_workbench_api.py`

- [ ] **Step 1: Replace the snapshot-only readiness test with capability tests**

```python
def test_readiness_accepts_healthy_duckdb_without_optional_snapshot(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("FORESIGHT_USERS_DIR", str(tmp_path / "users"))
    knowledge_wiki = tmp_path / "wiki"
    (knowledge_wiki / "relations").mkdir(parents=True)
    monkeypatch.setenv("KB_VAULT", str(knowledge_wiki))
    monkeypatch.setenv("MARKET_SNAPSHOT_DIR", str(tmp_path / "missing-snapshot"))
    repo_root = tmp_path / "repo"
    db_path = repo_root / "db/market_feature_store.duckdb"
    db_path.parent.mkdir(parents=True)
    connection = __import__("duckdb").connect(str(db_path))
    connection.execute("create table fact_market_daily(trade_date date)")
    connection.execute("insert into fact_market_daily values ('2026-07-13')")
    connection.close()

    response = TestClient(app_module.create_app(repo_root=repo_root)).get(
        "/api/health/ready"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert payload["critical"]["market_data"] is True
    assert payload["capabilities"]["market_data"]["cutoff"] == "2026-07-13"
    assert payload["capabilities"]["market_snapshot"]["available"] is False
    assert payload["checks"]["market_snapshot"] is False
    assert payload["missing_critical"] == []


def test_readiness_fails_when_duckdb_and_snapshot_are_both_unavailable(
    tmp_path, monkeypatch
) -> None:
    # Build valid repo/wiki/user roots but no DB and no snapshot.
    response = _readiness_client_without_market_inputs(tmp_path, monkeypatch).get(
        "/api/health/ready"
    )
    assert response.status_code == 503
    payload = response.json()
    assert payload["critical"]["market_data"] is False
    assert payload["missing_critical"] == ["market_data"]
```

- [ ] **Step 2: Run the two tests and verify the old contract fails**

```bash
uv run --with pytest --with fastapi --with httpx --with pydantic --with 'duckdb==1.4.3' python -m pytest \
  intelligence/tests/test_workbench_api.py -k 'readiness' -q
```

Expected: the healthy-DuckDB test receives `503`, and `capabilities` is absent.

- [ ] **Step 3: Build readiness from `probe_market_inputs`**

Keep the old boolean fields for compatibility, but make `market_data` the critical aggregate:

```python
market = probe_market_inputs(runtime_inputs)
checks = {
    **dependency_checks(),
    "market_data": market.market_data_available,
    "run_store_writable": run_root_ready,
}
critical = {
    "repo_root": checks["repo_root"],
    "run_store_writable": checks["run_store_writable"],
    "knowledge_wiki": checks["knowledge_wiki"],
    "relations": checks["relations"],
    "market_data": checks["market_data"],
}
payload["capabilities"] = {
    "market_data": {
        "available": market.market_data_available,
        "source": "duckdb" if market.duckdb_available else "snapshot",
        "cutoff": market.duckdb_cutoff,
    },
    "market_exports": {
        "available": market.latest_export_date is not None,
        "as_of": market.latest_export_date,
        "freshness": market.export_freshness,
    },
    "market_snapshot": {
        "available": market.market_snapshot_available,
        "as_of": market.market_snapshot_date,
    },
}
```

Do not print filesystem paths or DB exceptions in the public payload; expose a bounded warning label only.

- [ ] **Step 4: Run all API tests**

```bash
uv run --with pytest --with fastapi --with httpx --with pydantic --with 'duckdb==1.4.3' python -m pytest intelligence/tests/test_workbench_api.py -q
```

Expected: all tests pass; existing health fields remain available.

- [ ] **Step 5: Commit Task 3**

```bash
git add intelligence/api/app.py intelligence/tests/test_workbench_api.py
git commit -m "fix: make workbench readiness capability aware"
```

### Task 4: Give every AnswerSpec one bounded built-in GLM synthesis opportunity

**Files:**
- Modify: `intelligence/services/ask.py`
- Modify: `intelligence/services/conversation_orchestrator.py`
- Modify: `intelligence/api/structured_reports.py`
- Modify: `intelligence/tests/test_answer_orchestrator.py`
- Modify: `intelligence/tests/test_conversation_orchestrator.py`
- Modify: `intelligence/tests/test_structured_reports.py`

- [ ] **Step 1: Add failing Base Finance synthesis and fallback-telemetry tests**

```python
def test_market_pattern_attempts_answer_spec_synthesis_when_compose_enabled(self) -> None:
    composed_answer = "结构性上涨仍需下一交易日确认。（非投资建议）"
    with mock.patch(
        "intelligence.services.ask.llm_refine.synthesize_messages",
        return_value=(
            llm_refine.SynthesisResult(composed_answer, "zhipu", "glm-5.2"),
            "",
        ),
    ), mock.patch(
        "intelligence.services.ask.answer_model.validate_llm_answer",
        return_value=[],
    ):
        result = answer_query(
            AskOptions(
                query="指数上涨但涨停家数下降、成交额放大，怎么理解？",
                compose=True,
                use_modules=False,
                use_wiki_rag=False,
            )
        )

    assert result.llm_attempted is True
    assert result.llm_provider == "zhipu"
    assert result.llm_fallback_reason is None
    assert result.synthesis == composed_answer


def test_market_pattern_records_model_fallback_without_losing_answer_spec(self) -> None:
    with mock.patch(
        "intelligence.services.ask.llm_refine.synthesize_messages",
        return_value=(None, "LLM 调用失败（TimeoutError），已降级为模板"),
    ):
        result = answer_query(
            AskOptions(
                query="指数上涨但涨停家数下降，是否背离？",
                compose=True,
                use_modules=False,
                use_wiki_rag=False,
            )
        )

    assert result.llm_attempted is True
    assert result.llm_provider is None
    assert result.llm_fallback_reason == "provider_timeout"
    assert result.answer_spec is not None
```

- [ ] **Step 2: Add a failing owner-AnswerSpec synthesis test**

Build a `SkillOutput` with a verified `answer_contract`, route it as the owner, and patch the new synthesis wrapper. Assert the wrapper is called exactly once after `_skill_owner_result`, the final report has `attempted=true`, and no second retrieval call occurs.

```python
assert answer_query_calls == 0
assert synthesis_calls == 1
assert report["llm"] == {
    "configured": True,
    "attempted": True,
    "used": True,
    "provider": "zhipu",
    "model": "glm-5.2",
    "fallback_reason": None,
}
```

- [ ] **Step 3: Run the focused tests and observe both early-return gaps**

```bash
uv run --with pytest --with fastapi --with httpx --with pydantic python -m pytest \
  intelligence/tests/test_answer_orchestrator.py \
  intelligence/tests/test_conversation_orchestrator.py \
  intelligence/tests/test_structured_reports.py -q
```

Expected: market-pattern synthesis is never called; owner results render deterministically; the report lacks configured/attempted/fallback fields.

- [ ] **Step 4: Add model-attempt state and a reusable synthesis wrapper**

Extend `AskResult`:

```python
llm_attempted: bool = False
llm_fallback_reason: str | None = None
```

Before the provider call in `_synthesize_answer_spec`, set `llm_attempted=True`. Map bounded failure strings to stable labels (`provider_timeout`, `provider_unavailable`, `quality_gate_rejected`, `budget_exhausted`) while preserving the detailed warning separately.

Expose a public wrapper that composes an already-built AnswerSpec without rerunning retrieval:

```python
def synthesize_existing_answer_spec(options: AskOptions, result: AskResult) -> AskResult:
    if result.answer_spec is None or not options.compose:
        return result
    question_plan = result.question_plan or plan_answer_question(options.query)
    quality_context = answer_quality.build_quality_context(
        evidence_lines=[claim.text for claim in result.answer_spec.verified_facts],
        market_lines=[claim.text for claim in result.answer_spec.triggers],
        gap_lines=[claim.text for claim in result.answer_spec.gaps],
    )
    _synthesize_answer_spec(
        options=options,
        result=result,
        question_plan=question_plan,
        theme=result.answer_spec.research_spec.theme,
        citations=result.citations,
        quality_context=quality_context,
        is_market_review=question_plan.question_type == QUESTION_MARKET_REVIEW,
    )
    return result
```

Call this wrapper in the market-pattern/unknown early-return branch after `_answer_general_finance()` builds the AnswerSpec.

- [ ] **Step 5: Compose owner output in the orchestrator, not inside the Skill**

After `_skill_owner_result(...)`, calculate a synthesis allowance with a five-second commit reserve and call `synthesize_existing_answer_spec()` once. Keep ResearchOwner on `synthesize=False`; it owns retrieval and the AnswerSpec, while the orchestrator owns final prose.

```python
synthesis_allowance = execution_budget.child_timeout(20, reserve=5)
if synthesis_allowance >= 4:
    result = synthesize_existing_answer_spec(
        AskOptions(
            query=contextual_query,
            user=self.run_store.user_id,
            compose=True,
            synthesize=True,
            use_modules=False,
            use_wiki_rag=False,
            conversation_context=context.to_prompt_block(),
            include_memory_block=True,
            perspective_mode=perspective_mode,
            perspective_ids=tuple(selected_perspective_ids),
            llm_timeout=max(1, int(synthesis_allowance - 2)),
            stream_text_delta=emit_text_delta,
        ),
        result,
    )
else:
    result.llm_fallback_reason = "budget_exhausted"
```

- [ ] **Step 6: Expand the structured-report model contract**

Change `new_structured_report()` and `complete_report()` to produce:

```python
"llm": {
    "configured": llm_configured,
    "attempted": result.llm_attempted,
    "used": result.llm_provider is not None,
    "provider": result.llm_provider,
    "model": llm_model if result.llm_provider else None,
    "fallback_reason": result.llm_fallback_reason,
}
```

Pass `llm_configured=llm_provider is not None` from `_run_conversation_turn` into `TurnOrchestrator`; do not infer configured state from `used`.

- [ ] **Step 7: Run the focused suite and commit**

Run the Task 4 command. Expected: all tests pass.

```bash
git add intelligence/services/ask.py intelligence/services/conversation_orchestrator.py \
  intelligence/api/structured_reports.py intelligence/tests/test_answer_orchestrator.py \
  intelligence/tests/test_conversation_orchestrator.py intelligence/tests/test_structured_reports.py
git commit -m "feat: synthesize every workbench answer spec with built-in llm"
```

### Task 5: Reserve finalization time and make Skill timeout fallback cheap

**Files:**
- Modify: `intelligence/api/app.py`
- Modify: `intelligence/services/conversation_orchestrator.py`
- Modify: `intelligence/workbench_skills/research_owner.py`
- Modify: `intelligence/tests/test_conversation_orchestrator.py`
- Modify: `intelligence/tests/test_workbench_api.py`
- Modify: `intelligence/tests/test_workbench_research_owner_skills.py`

- [ ] **Step 1: Write a failing internal-deadline reserve test**

```python
def test_turn_work_seconds_reserves_terminalization_time() -> None:
    assert _turn_work_seconds(60) == 55
    assert _turn_work_seconds(3) == 1
```

- [ ] **Step 2: Extend the existing timed-out Skill test**

Capture the fallback `AskOptions` after a Skill timeout and assert expensive work is disabled while synthesis remains available:

```python
assert fallback_options.use_modules is False
assert fallback_options.use_wiki_rag is False
assert fallback_options.compose is True
assert fallback_options.synthesize is True
assert result.status == "completed"
assert run_store.load_run(run_id).status == "completed"
assert json.loads((run_store.run_dir(run_id) / "report.json").read_text())["status"] == "completed"
```

- [ ] **Step 3: Add a failing API integration test for the prior real failure**

Use a fake owner that blocks until its allowance expires and a fast deterministic fallback. Start the API with `answer_deadline_seconds=0.20` through a new test-only `create_app` argument or injected supervisor. Assert the run completes before the supervisor's `+5` hard timer, the report is completed, and `executor_timeout` is absent.

- [ ] **Step 4: Run the budget/timeout tests and verify current behavior fails**

```bash
uv run --with pytest --with fastapi --with httpx --with pydantic python -m pytest \
  intelligence/tests/test_conversation_orchestrator.py \
  intelligence/tests/test_workbench_api.py \
  intelligence/tests/test_workbench_research_owner_skills.py -k 'budget or timeout or deadline' -q
```

- [ ] **Step 5: Introduce explicit reserves**

Add named constants in `conversation_orchestrator.py`:

```python
FINALIZATION_RESERVE_SECONDS = 5.0
SYNTHESIS_RESERVE_SECONDS = 20.0
SKILL_RESERVE_SECONDS = FINALIZATION_RESERVE_SECONDS + SYNTHESIS_RESERVE_SECONDS


def _turn_work_seconds(answer_deadline_seconds: float) -> float:
    return max(1.0, answer_deadline_seconds - FINALIZATION_RESERVE_SECONDS)
```

Start the internal budget with:

```python
execution_budget = ExecutionBudget.start(
    _turn_work_seconds(self.answer_deadline_seconds)
)
```

Cap each Skill with `reserve=SKILL_RESERVE_SECONDS`. Track `skill_timed_out=True` on `FuturesTimeoutError`. If no owner contract is available after that timeout, call base Ask with `use_modules=False` and `use_wiki_rag=False`; do not repeat the expensive research plan.

- [ ] **Step 6: Simplify ResearchOwner budgeting**

ResearchOwner remains retrieval/AnswerSpec-only. Remove the “halve synthesis allowance” calculation and pass a bounded non-model timeout only where Ask's data blocks require it. Update the existing owner budget test to assert:

```python
assert captured[0].execution_budget is budget
assert captured[0].synthesize is False
assert captured[0].market_db_path == inputs.market_db_path
```

- [ ] **Step 7: Preserve the supervisor hard-failure safety net**

Do not change `test_executor_timeout_marks_run_failed` for an arbitrary worker that never cooperates. The supervisor remains the last-resort circuit breaker. The new guarantee is that normal conversation workers receive a shorter internal deadline and produce a safe answer/report before that breaker fires.

- [ ] **Step 8: Run focused tests and commit**

Run the Task 5 command. Expected: all selected tests pass and the arbitrary blocked-worker test still expects `failed/executor_timeout`.

```bash
git add intelligence/api/app.py intelligence/services/conversation_orchestrator.py \
  intelligence/workbench_skills/research_owner.py \
  intelligence/tests/test_conversation_orchestrator.py \
  intelligence/tests/test_workbench_api.py \
  intelligence/tests/test_workbench_research_owner_skills.py
git commit -m "fix: reserve workbench synthesis and terminalization time"
```

### Task 6: Render model state, run all gates, and repeat real built-in smoke

**Files:**
- Modify: `intelligence/webapp/src/types.ts`
- Modify: `intelligence/webapp/src/components/StructuredReportView.tsx`
- Modify: `intelligence/webapp/src/components/components.test.tsx`
- Modify: `scripts/smoke_workbench_self_use.py`
- Modify: `intelligence/tests/test_workbench_conversation_integration.py`
- Regenerate: `intelligence/api/static/index.html`
- Regenerate: `intelligence/api/static/assets/index-*.js`
- Regenerate only if changed by build: `intelligence/api/static/assets/index-*.css`

- [ ] **Step 1: Add failing frontend model-state tests**

```tsx
expect(screen.getByText("已使用 zhipu · glm-5.2")).toBeVisible();
expect(screen.getByText("内置模型已尝试 · 已回退：provider_timeout")).toBeVisible();
expect(screen.getByText("内置模型可用 · 本轮未调用")).toBeVisible();
```

Cover three reports: `used=true`, `configured+attempted+fallback`, and `configured but not attempted`.

- [ ] **Step 2: Expand TypeScript types and render bounded labels**

```ts
llm: {
  configured: boolean;
  attempted: boolean;
  used: boolean;
  provider: string | null;
  model: string | null;
  fallback_reason: string | null;
};
```

Map stable fallback labels to Chinese display text. Do not show provider error bodies or prompts.

- [ ] **Step 3: Extend smoke summary with non-sensitive model and cutoff assertions**

The redacted summary already records `model.used`; add safe fields for `configured`, `attempted`, `fallback_reason`, report `as_of`, and run `duckdb_cutoff`. Validate all labels with existing safe-label rules and never include a path, prompt, key, response header, or raw model error.

- [ ] **Step 4: Run frontend and smoke tests**

```bash
cd intelligence/webapp
pnpm test -- --run
pnpm typecheck
pnpm lint
pnpm build
cd ../..
uv run --with pytest --with fastapi --with httpx --with pydantic python -m pytest \
  intelligence/tests/test_workbench_conversation_integration.py \
  intelligence/tests/test_workbench_api.py -q
```

Expected: Vitest `45+ passed`; typecheck, lint, build, and Python tests pass.

- [ ] **Step 5: Run the full backend regression gate**

```bash
uv run --with pytest --with fastapi --with httpx --with pydantic --with 'duckdb==1.4.3' python -m pytest \
  intelligence/tests/test_query_understanding.py \
  intelligence/tests/test_execution_budget.py \
  intelligence/tests/test_answer_model.py \
  intelligence/tests/test_answer_orchestrator.py \
  intelligence/tests/test_closed_loop_retrieval.py \
  intelligence/tests/test_kb_rag.py \
  intelligence/tests/test_workbench_skill_router.py \
  intelligence/tests/test_workbench_research_owner_skills.py \
  intelligence/tests/test_conversation_orchestrator.py \
  intelligence/tests/test_workbench_conversation_integration.py \
  intelligence/tests/test_workbench_api.py -q
```

Expected: all tests pass; the existing Starlette/httpx deprecation warning may remain but no assertion fails.

- [ ] **Step 6: Start the isolated branch with canonical data and built-in GLM securely**

Use the existing Keychain lookup only inside command substitution; never echo it:

```bash
export PYTHONPATH=/Users/a77/.codex/worktrees/workbench-query-retrieval-latency
export WORKBENCH_REPO_ROOT=/Users/a77/finance-workspace-private
export FINANCE_WS=/Users/a77/finance-workspace-private
export FORESIGHT_USERS_DIR=/tmp/workbench-runtime-data-llm-users
export FORESIGHT_BUILTIN_LLM_API_KEY="$(security find-generic-password -a a77 -s finance-workbench-glm -w)"
export FORESIGHT_BUILTIN_LLM_MODEL=glm-5.2
export FORESIGHT_BUILTIN_LLM_BASE_URL=https://open.bigmodel.cn/api/coding/paas/v4
export WORKBENCH_ANSWER_DEADLINE_SECONDS=60
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m uvicorn \
  intelligence.api.app:app --host 127.0.0.1 --port 8795
```

Expected: `/api/llm/config` says built-in ready; readiness says market data available from DuckDB with cutoff `2026-07-13` (or the later runtime cutoff), while missing snapshot is only a capability warning.

- [ ] **Step 7: Run two real smokes and inspect route/report evidence**

Questions:

```text
A股里，指数上涨但涨停家数下降、成交额放大，这种背离应该怎么理解？请直接给出判断、最关键的证据、可能的反证和下一步验证，不要写成检查清单。
```

```text
深挖英维克，它在液冷产业链的位置如何？请给出直接判断、最强证据、反证和下一步验证。
```

Acceptance:

- both runs reach completed/degraded terminal state and report `status=completed` within 60 seconds;
- market question keeps `subject_kind=market_pattern`;
- company question keeps subject/title/claims anchored to `英维克`;
- `llm.attempted=true`; use the GLM output if it passes the AnswerSpec gate, otherwise record one safe fallback reason;
- cutoff/as-of uses `2026-07-13` or later canonical data, never the worktree's `2026-07-01` export;
- no `executor_timeout`, no streaming report residue, no unrelated citations, no secret-scan hit.

- [ ] **Step 8: Perform real UI verification and capture screenshots**

Use the Browser skill against `http://127.0.0.1:8795/`. Submit both questions, inspect the visible five-stage progress/Inspector, final model label, data cutoff, neutral no-evidence wording, and complete answer. Save screenshots under `/tmp/workbench-runtime-data-llm-evidence/`; do not add them to Git.

- [ ] **Step 9: Stop the temporary server and commit Task 6**

```bash
git status --short
git diff --check
git add intelligence/webapp/src/types.ts \
  intelligence/webapp/src/components/StructuredReportView.tsx \
  intelligence/webapp/src/components/components.test.tsx \
  scripts/smoke_workbench_self_use.py \
  intelligence/tests/test_workbench_conversation_integration.py \
  intelligence/api/static/index.html intelligence/api/static/assets/
git commit -m "test: verify canonical data and built-in llm workbench flow"
```

Before committing, inspect staged names and abort if any `.env*`, key, database, PDF, archive, user run, cache, virtual environment, or screenshot is present.

## Final review checklist

- [ ] `git diff origin/main...HEAD --check` passes.
- [ ] A final independent reviewer checks spec coverage, path isolation, deadline arithmetic, secret handling, and no duplicate retrieval.
- [ ] The worktree is clean.
- [ ] The branch is not pushed, merged, or installed as canonical runtime without explicit user approval.
- [ ] Project memory records the stable decision: product capability must be distinguished from temporary runtime wiring; DuckDB is the structured market source, built-in GLM is the bounded expression layer, and snapshot-only capability is not global readiness.
