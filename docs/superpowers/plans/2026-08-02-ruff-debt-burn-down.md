# Ruff Debt Burn-down Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不改变四个已停用 legacy 脚本状态、不切换 8792/8799 的前提下，修复 Ruff 揭示的真实缺陷，把活跃 Python 代码的 Ruff 告警从 144 条降到 0，并建立固定版本的本地与 CI 门禁。

**Architecture:** 先以回归测试修复 F821 与两处被 F841 暴露的行为缺口，再把重复的 DuckDB 可选依赖探针收敛到 `retrieval_cache` 的结构化连接结果；其余告警按目录做行为等价的机械清理。确需调整 `sys.path` 后导入的脚本使用逐行 E402 说明，四个 CLAUDE.md 已声明 broken 的脚本使用精确 exclude，最后以固定 Ruff 版本接入 pre-commit 与 `workbench-check`。

**Tech Stack:** Python 3.12、pytest 8.3.5、Ruff 0.11.13、DuckDB 1.4.3、pre-commit、GitHub Actions。

---

## Scope, invariants, and file map

- 分支固定为 `fix/ruff-debt-burn-down`，基线为 `origin/main@78187ec7`；不 merge、不 push、不部署。
- 运行 Python 与 Ruff 统一使用 `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`。
- 禁止运行 `ruff check . --fix`。自动修复只允许作用于 Task 8/10 列出的显式文件。
- 不修改 `scripts/backtest_sector.py`、`scripts/detect_turning_points.py`、`scripts/sync_to_local.py`、`scripts/render_daily_review_template.py` 的正文；它们仍是 CLAUDE.md 记录的 broken legacy。
- 不触碰知识库正文、DuckDB 文件、飞书真实表、8792/8799 进程。
- correctness 文件：
  - `skills/report-search/scripts/api_client.py`：CLI 环境变量读取。
  - `intelligence/chat/feishu_bot.py`：运行时类型反射。
  - `skills/lib/pdf_ingest_lint.py`：broker annotation gate。
  - `skills/limit-advance/scripts/write.py`：飞书批量写入成功数门禁。
- dependency seam 文件：
  - `intelligence/services/retrieval_cache.py`：DuckDB 连接状态唯一实现。
  - `intelligence/services/ask_blocks.py`、`market_analogs.py`、`market_midterm.py`、`market_moneyflow.py`、`market_timeseries.py`：只消费结构化状态。
- policy/enforcement 文件：`ruff.toml`、`.pre-commit-config.yaml`、`.github/workflows/workbench-check.yml`。

### Task 1: Freeze the branch-local baseline

**Files:**
- Verify: entire tracked Python scope
- Verify: `docs/superpowers/specs/2026-08-02-ruff-debt-burn-down-design.md`

- [ ] **Step 1: Confirm branch and clean worktree**

Run:

```bash
git status --short
git branch --show-current
git rev-parse --short HEAD
```

Expected: no status rows, branch `fix/ruff-debt-burn-down`, HEAD `bf08c51e` before this plan commit.

- [ ] **Step 2: Freeze Ruff counts**

Run:

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m ruff check . --statistics
```

Expected: 171 total findings; after subtracting the four legacy files, 144 active findings. Rule totals are F401=59, F541=31, E402=25, E702=19, F841=18, E741=9, F821=5, E701=3, E401=2.

- [ ] **Step 3: Freeze pytest failure identities**

Run:

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q
```

Expected: `2108 passed, 11 failed, 1 skipped`; the failures are exactly:

```text
intelligence/tests/test_subconscious.py::StartAndBufferTests::test_append_resolves_active_session
intelligence/tests/test_subconscious.py::StartAndBufferTests::test_append_stores_memo_and_question
intelligence/tests/test_subconscious.py::StartAndBufferTests::test_append_without_session_raises
intelligence/tests/test_subconscious.py::ResolveVaultTests::test_default_uses_agent_memory_when_present
intelligence/tests/test_subconscious.py::CommitAndArchiveTests::test_commit_persists_judgments_to_machine_layer
intelligence/tests/test_subconscious.py::CommitAndArchiveTests::test_commit_weight_matches_proposal
intelligence/tests/test_subconscious.py::CommitAndArchiveTests::test_commit_without_memos_writes_no_judgments
intelligence/tests/test_subconscious.py::CommitAndArchiveTests::test_commit_writes_both_layers_then_archive
intelligence/tests/test_userspace.py::UserSpacePathTests::test_default_uses_legacy_memory
intelligence/tests/test_userspace.py::UserSpacePathTests::test_non_default_isolated_paths
intelligence/tests/test_userspace.py::ForesightResolveProfileTests::test_memory_path_resolves_per_user
```

Any later failure outside this set is a new regression and stops that batch.

### Task 2: Fix the report-search no-key CLI crash (Batch A1)

**Files:**
- Modify: `skills/report-search/scripts/api_client.py:8-13`
- Modify: `skills/report-search/scripts/test_basic.py:7-13,210-323`

- [ ] **Step 1: Write the failing subprocess test**

Add `import subprocess` to `test_basic.py` and add this method to `TestAPIClient`:

```python
def test_cli_without_api_key_reports_configuration_error(self):
    env = os.environ.copy()
    env.pop("IWENCAI_API_KEY", None)
    script = Path(__file__).with_name("api_client.py")

    proc = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(script.parent),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    self.assertEqual(proc.returncode, 1, proc.stderr)
    self.assertIn("请设置环境变量 IWENCAI_API_KEY", proc.stdout)
    self.assertNotIn("NameError", proc.stderr)
```

- [ ] **Step 2: Prove the test is red**

Run:

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q skills/report-search/scripts/test_basic.py::TestAPIClient::test_cli_without_api_key_reports_configuration_error
```

Expected: FAIL because `api_client.py` raises `NameError: name 'os' is not defined`.

- [ ] **Step 3: Add the missing runtime import**

Add the standard-library import with the other imports:

```python
import logging
import os
import secrets
import time
```

- [ ] **Step 4: Prove the focused test is green**

Run:

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q skills/report-search/scripts/test_basic.py::TestAPIClient::test_cli_without_api_key_reports_configuration_error
```

Expected: `1 passed`.

### Task 3: Make Feishu Bot annotations runtime-resolvable (Batch A2)

**Files:**
- Modify: `intelligence/chat/feishu_bot.py:46-58`
- Modify: `intelligence/tests/test_feishu_bot.py:3-10`

- [ ] **Step 1: Write a runtime type-hint regression test**

Add `import typing` and this class to `test_feishu_bot.py`:

```python
class RuntimeTypeHintTests(unittest.TestCase):
    def test_ask_result_annotations_resolve_for_all_bot_entrypoints(self) -> None:
        result_parameters = (
            feishu_bot.render_ask_reply,
            feishu_bot.render_ask_card,
            feishu_bot.render_evidence_card,
        )
        for function in result_parameters:
            with self.subTest(function=function.__name__):
                hints = typing.get_type_hints(function)
                self.assertIs(hints["result"], AskResult)

        hints = typing.get_type_hints(feishu_bot._run_ask_workflow)
        self.assertIs(hints["return"], AskResult)
```

- [ ] **Step 2: Prove the test is red**

Run:

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q intelligence/tests/test_feishu_bot.py::RuntimeTypeHintTests
```

Expected: FAIL with `NameError: name 'AskResult' is not defined`.

- [ ] **Step 3: Import only the public type layer at runtime**

Add this import near the other module imports:

```python
from intelligence.services.ask_types import AskResult
```

Keep the existing lazy imports of `SECTION_ORDER`, `SUBHEAD`, and workflow code inside functions. Do not move `AskResult` under `TYPE_CHECKING`, because `typing.get_type_hints()` evaluates annotations at runtime.

- [ ] **Step 4: Prove reflection and the no-DuckDB import contract are green**

Run:

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q intelligence/tests/test_feishu_bot.py::RuntimeTypeHintTests intelligence/tests/test_feishu_bot.py::NoDuckdbImportTests
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m ruff check intelligence/chat/feishu_bot.py intelligence/tests/test_feishu_bot.py --select F821
```

Expected: tests pass and Ruff reports no F821.

### Task 4: Restore the broker-only PDF annotation gate (Batch A3)

**Files:**
- Create: `tests/test_pdf_ingest_lint.py`
- Modify: `skills/lib/pdf_ingest_lint.py:446-458`

- [ ] **Step 1: Write broker/non-broker contrast tests**

Create `tests/test_pdf_ingest_lint.py`:

```python
from pathlib import Path

from skills.lib import pdf_ingest_lint


def _write_entity(root: Path, source_name: str) -> None:
    (root / "测试公司.md").write_text(
        "# 测试公司\n\n"
        "## 高信度研究线索\n\n"
        f"### 测试概念｜{source_name}\n\n"
        "缺少三项 annotation。\n",
        encoding="utf-8",
    )


def _exposure(source_quality: str) -> list[tuple[str, str, dict[str, str]]]:
    return [
        (
            "测试公司",
            "测试概念",
            {
                "update_type": "curated_research",
                "fact_hardness": "review_candidate",
                "source_quality": source_quality,
            },
        )
    ]


def test_broker_curated_research_requires_annotations(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(pdf_ingest_lint, "ENTITIES_DIR", tmp_path)
    pdf_ingest_lint.ISSUES.clear()
    _write_entity(tmp_path, "测试来源")

    pdf_ingest_lint.check_entity_annotation(
        "测试来源", _exposure("broker_research_high")
    )

    messages = [item["message"] for item in pdf_ingest_lint.ISSUES]
    assert len(messages) == 3
    assert any("source_quality" in message for message in messages)
    assert any("fact_hardness" in message for message in messages)
    assert any("evidence_layer" in message for message in messages)


def test_non_broker_curated_research_is_outside_annotation_gate(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(pdf_ingest_lint, "ENTITIES_DIR", tmp_path)
    pdf_ingest_lint.ISSUES.clear()
    _write_entity(tmp_path, "测试来源")

    pdf_ingest_lint.check_entity_annotation(
        "测试来源", _exposure("official_disclosure")
    )

    assert pdf_ingest_lint.ISSUES == []
```

- [ ] **Step 2: Prove the non-broker case is red**

Run:

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q tests/test_pdf_ingest_lint.py
```

Expected: broker test passes; non-broker test fails with three annotation issues.

- [ ] **Step 3: Enforce the source-quality boundary**

Insert the source gate before the update-type and hardness gates:

```python
# This annotation contract is specific to second-hand broker research.
if sq not in BROKER_SOURCES:
    continue
if update_type != "curated_research":
    continue
if hardness != "review_candidate":
    continue
```

- [ ] **Step 4: Prove both routing cases are green**

Run:

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q tests/test_pdf_ingest_lint.py
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m ruff check skills/lib/pdf_ingest_lint.py --select F841
```

Expected: `2 passed`; the F841 at the former `sq` line is gone. Other `pdf_ingest_lint.py` findings remain for Batch C.

### Task 5: Fail closed on partial Feishu batch writes (Batch A4)

**Files:**
- Create: `tests/test_limit_advance_write.py`
- Modify: `skills/limit-advance/scripts/write.py:96-139`

- [ ] **Step 1: Write a script-level partial-update regression**

Create `tests/test_limit_advance_write.py` with a fake `feishu_utils` module so the test never reads real credentials:

```python
from __future__ import annotations

import importlib.util
import io
import json
import sys
import types
from pathlib import Path
from unittest import mock

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "skills/limit-advance/scripts/write.py"


def _load_module(monkeypatch):
    fake = types.ModuleType("feishu_utils")
    fake.load_config = lambda: {"app_token": "test-app"}
    fake.get_token = lambda _cfg: "test-token"
    for name in (
        "api",
        "fetch_all_records",
        "list_fields",
        "create_field",
        "delete_field",
        "get_table_id",
        "batch_update",
        "batch_delete",
    ):
        setattr(fake, name, mock.Mock())
    monkeypatch.setitem(sys.modules, "feishu_utils", fake)
    spec = importlib.util.spec_from_file_location("limit_advance_write_tested", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_partial_existing_record_update_exits_before_reporting_success(
    monkeypatch, capsys
) -> None:
    module = _load_module(monkeypatch)
    payload = {
        "date": "08-01",
        "trading_days": ["08-01"],
        "stocks": [{"name": "测试股", "first_date": "08-01"}],
    }
    monkeypatch.setattr(module.sys, "stdin", io.StringIO(json.dumps(payload)))
    monkeypatch.setattr(module, "get_token", lambda: "token")
    monkeypatch.setattr(module, "get_table_id", lambda *args, **kwargs: "table")
    monkeypatch.setattr(
        module,
        "list_fields",
        lambda *args, **kwargs: [
            {"field_name": "序号", "field_id": "seq"},
            {"field_name": "08-01", "field_id": "date"},
        ],
    )
    monkeypatch.setattr(
        module,
        "fetch_all_records",
        lambda *args, **kwargs: [
            {"record_id": "rec-1", "fields": {"股票简称": "测试股"}}
        ],
    )
    monkeypatch.setattr(module, "batch_delete", lambda *args, **kwargs: None)
    monkeypatch.setattr(module, "batch_update", lambda *args, **kwargs: 0)
    create_api = mock.Mock(return_value={"code": 0, "data": {"records": []}})
    monkeypatch.setattr(module, "api", create_api)

    with pytest.raises(SystemExit) as exc_info:
        module.main()

    assert exc_info.value.code == 1
    assert "请求 1 条，实际成功 0 条" in capsys.readouterr().err
    create_api.assert_not_called()
```

- [ ] **Step 2: Prove the test is red**

Run:

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q tests/test_limit_advance_write.py
```

Expected: FAIL because current `main()` continues after `batch_update()` returns 0.

- [ ] **Step 3: Add one reusable completeness guard and use actual counts**

Add near `get_token()`:

```python
def _require_complete(operation: str, requested: int, completed: int) -> None:
    if completed == requested:
        return
    print(
        f"{operation}部分失败：请求 {requested} 条，实际成功 {completed} 条",
        file=sys.stderr,
    )
    raise SystemExit(1)
```

Use it immediately after each externally visible batch result:

```python
updated = batch_update(token, tid, to_update, app_token=APP_TOKEN, chunk_size=500)
_require_complete("更新", len(to_update), updated)

# existing create loop remains; after it:
_require_complete("新增", len(to_create), created)
print(f"更新 {updated} 条，新增 {created} 条")

reordered = batch_update(token, tid, updates, app_token=APP_TOKEN, chunk_size=500)
_require_complete("序号重排", len(updates), reordered)
print(f"序号已按首板日期重排（{reordered} 条）")
```

- [ ] **Step 4: Prove partial failure and full success semantics**

Run:

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q tests/test_limit_advance_write.py
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m ruff check skills/limit-advance/scripts/write.py --select F841
```

Expected: tests pass and the unused `updated` finding is gone.

### Task 6: Validate and commit Batch A correctness fixes

**Files:**
- Modify: the eight Batch A code/test files from Tasks 2-5

- [ ] **Step 1: Run the Batch A suite**

Run:

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q skills/report-search/scripts/test_basic.py intelligence/tests/test_feishu_bot.py tests/test_pdf_ingest_lint.py tests/test_limit_advance_write.py
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m ruff check skills/report-search/scripts/api_client.py intelligence/chat/feishu_bot.py skills/lib/pdf_ingest_lint.py skills/limit-advance/scripts/write.py --select F821,F841
```

Expected: all selected tests pass; no F821; only unrelated pre-existing F841 lines, if any, remain in `pdf_ingest_lint.py`.

- [ ] **Step 2: Compare the full pytest identity set**

Run:

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q
```

Expected: the 11 baseline failure identities from Task 1 and no new identity; pass count increases by the new tests.

- [ ] **Step 3: Check and commit only Batch A**

Run:

```bash
git diff --check
git add skills/report-search/scripts/api_client.py skills/report-search/scripts/test_basic.py intelligence/chat/feishu_bot.py intelligence/tests/test_feishu_bot.py skills/lib/pdf_ingest_lint.py skills/limit-advance/scripts/write.py tests/test_pdf_ingest_lint.py tests/test_limit_advance_write.py
git diff --cached --check
git commit -m "fix: close Ruff-discovered correctness gaps"
```

Expected: one correctness commit, with no mechanical cleanup mixed in.

### Task 7: Centralize optional DuckDB connection state (Batch B)

**Files:**
- Modify: `intelligence/services/retrieval_cache.py:13-150`
- Modify: `intelligence/tests/test_retrieval_cache_service.py`
- Modify: `intelligence/services/ask_blocks.py`
- Modify: `intelligence/services/market_analogs.py`
- Modify: `intelligence/services/market_midterm.py`
- Modify: `intelligence/services/market_moneyflow.py`
- Modify: `intelligence/services/market_timeseries.py`

- [ ] **Step 1: Write connection-state tests first**

Extend `test_retrieval_cache_service.py` with imports `from types import SimpleNamespace` and `from unittest import mock`, then add:

```python
class DuckDBConnectionResultTests(unittest.TestCase):
    def test_dependency_unavailable_is_structured(self) -> None:
        with mock.patch.object(
            retrieval_cache,
            "_load_duckdb",
            side_effect=ModuleNotFoundError("No module named 'duckdb'"),
        ):
            result = retrieval_cache.try_connect_readonly("missing.duckdb")
        self.assertEqual(result.status, "dependency_unavailable")
        self.assertIsNone(result.connection)
        self.assertEqual(result.error_type, "ModuleNotFoundError")

    def test_open_failure_is_distinct_from_missing_dependency(self) -> None:
        fake_duckdb = SimpleNamespace(
            connect=mock.Mock(side_effect=RuntimeError("cannot open database"))
        )
        with mock.patch.object(retrieval_cache, "_load_duckdb", return_value=fake_duckdb):
            result = retrieval_cache.try_connect_readonly("broken.duckdb")
        self.assertEqual(result.status, "open_failed")
        self.assertIsNone(result.connection)
        self.assertEqual(result.error_type, "RuntimeError")

    def test_success_returns_the_connection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "ok.duckdb"
            import duckdb

            duckdb.connect(str(db_path)).close()
            result = retrieval_cache.try_connect_readonly(db_path)
            self.assertEqual(result.status, "available")
            self.assertIsNotNone(result.connection)
            result.connection.close()
```

- [ ] **Step 2: Prove the new API is red**

Run:

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q intelligence/tests/test_retrieval_cache_service.py::DuckDBConnectionResultTests
```

Expected: FAIL because `_load_duckdb` and `try_connect_readonly` do not exist.

- [ ] **Step 3: Implement the structured seam**

Add these imports and definitions to `retrieval_cache.py`:

```python
from dataclasses import dataclass
from importlib import import_module
from typing import Any, Iterator, Literal

DuckDBConnectionStatus = Literal[
    "available", "dependency_unavailable", "open_failed"
]


@dataclass(frozen=True)
class DuckDBConnectionResult:
    status: DuckDBConnectionStatus
    connection: Any | None = None
    error_type: str | None = None

    @property
    def available(self) -> bool:
        return self.status == "available" and self.connection is not None


def _load_duckdb() -> Any:
    return import_module("duckdb")
```

Replace both direct imports inside `_DuckDBPool.borrow()` and `connect_readonly()` with `duckdb = _load_duckdb()`, then add:

```python
def try_connect_readonly(db_path: str | Path) -> DuckDBConnectionResult:
    try:
        connection = connect_readonly(db_path)
    except (ImportError, ModuleNotFoundError) as exc:
        return DuckDBConnectionResult(
            "dependency_unavailable", error_type=type(exc).__name__
        )
    except Exception as exc:
        return DuckDBConnectionResult("open_failed", error_type=type(exc).__name__)
    return DuckDBConnectionResult("available", connection=connection)
```

- [ ] **Step 4: Migrate every duplicate dependency probe**

In the five consumers, replace each local `try: import duckdb` plus connection `try` pair with one result lookup. Silent/fallback callers use:

```python
db_result = retrieval_cache.try_connect_readonly(db_path)
if not db_result.available:
    return fallback_value
con = db_result.connection
```

Callers that expose distinct degrade reasons map the status explicitly:

```python
if db_result.status == "dependency_unavailable":
    return dependency_unavailable_value
if db_result.status == "open_failed":
    return open_failed_value
con = db_result.connection
```

Apply this at all current probe locations:

```text
ask_blocks.py: _mainline_context_block_for_llm, _market_review_mainline_context_block_for_llm,
  _second_derivative_queue_block_for_llm, _daily_market_overview_block_for_llm,
  _market_data_asof, _attach_market_index_comparison,
  _market_value_block_for_llm, _valuation_block_for_llm,
  _financials_block_for_llm
market_analogs.py: build_historical_analogs, analog_block_for_llm
market_midterm.py: build_midterm_trend
market_moneyflow.py: build_moneyflow_snapshot, moneyflow_block_for_llm
market_timeseries.py: fetch_timeseries
```

For `fetch_timeseries`, render `dependency_unavailable` as `duckdb 库不可用` and `open_failed` as `DuckDB 连接失败（<error_type>）`; do not expose a traceback or filesystem exception text.

- [ ] **Step 5: Run dependency-focused tests and Ruff**

Run:

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q intelligence/tests/test_retrieval_cache_service.py intelligence/tests/test_ask_compose.py intelligence/tests/test_market_analogs.py intelligence/tests/test_market_midterm.py intelligence/tests/test_market_moneyflow.py intelligence/tests/test_market_timeseries.py intelligence/tests/test_structured_reports.py intelligence/tests/test_valuation_estimate.py intelligence/tests/test_workbench_research_owner_skills.py
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m ruff check intelligence/services/retrieval_cache.py intelligence/services/ask_blocks.py intelligence/services/market_analogs.py intelligence/services/market_midterm.py intelligence/services/market_moneyflow.py intelligence/services/market_timeseries.py --select F401,F821,F841
```

Expected: selected tests pass; the 15 active-service DuckDB F401 findings are gone; optional dependency, open failure, and available states remain distinct. The separate module-level finding in deprecated `scripts/fast_daily_sync.py` remains for Task 8.

- [ ] **Step 6: Compare the full suite and commit Batch B**

Run:

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q
git diff --check
git add intelligence/services/retrieval_cache.py intelligence/tests/test_retrieval_cache_service.py intelligence/services/ask_blocks.py intelligence/services/market_analogs.py intelligence/services/market_midterm.py intelligence/services/market_moneyflow.py intelligence/services/market_timeseries.py
git diff --cached --check
git commit -m "refactor: centralize optional DuckDB connection state"
```

Expected: only the 11 baseline failure identities; one dependency-seam commit.

### Task 8: Apply audited safe fixes to active non-skill code (Batch C1)

**Files:**
- Modify only the explicit files in the command below

- [ ] **Step 1: Preview Ruff safe fixes without editing**

Run:

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m ruff check \
  docs/learning/forecast-review-ledger/build_calendar.py \
  evolution/strategy1.py \
  intelligence/dream/kb_candidates.py \
  intelligence/services/agent.py \
  intelligence/services/entity_anchor.py \
  intelligence/services/interactions.py \
  intelligence/services/question_router.py \
  intelligence/tests/test_ask_compose.py \
  intelligence/tests/test_skill_tools.py \
  intelligence/tests/test_subconscious.py \
  market_feature_store/sync/sync_daily_full.py \
  research/market-hypothesis/_scripts/e001c_reflow_alignment.py \
  research/market-hypothesis/_scripts/strategy1_limit_ma5_impact.py \
  scripts/fast_daily_sync.py \
  scripts/render_strategy4_dual_engine_matrix.py \
  --select F401,F541 --fix --diff
```

Expected: the diff only removes unused imports or the `f` prefix from strings with no placeholders. If it changes string contents or removes a module used for an availability probe, remove that file from this automatic group and apply the one-line edit manually.

- [ ] **Step 2: Apply exactly the previewed safe fixes**

Run the same command with `--fix` and without `--diff`.

- [ ] **Step 3: Split the two multi-import lines**

In `scripts/db_delta_export.py` replace its combined import with:

```python
import argparse
import datetime
import hashlib
import json
import os
import re
import sys
import zipfile
```

In `skills/daily-full-review/scripts/export_increment.py` replace its combined import with:

```python
import argparse
import datetime as dt
import json
import sys
import tarfile
import tempfile
```

- [ ] **Step 4: Verify this sub-batch**

Run:

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m ruff check docs evolution intelligence market_feature_store research/market-hypothesis/_scripts scripts/db_delta_export.py scripts/fast_daily_sync.py scripts/render_strategy4_dual_engine_matrix.py skills/daily-full-review/scripts/export_increment.py --select F401,F541,E401
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q intelligence/tests/test_ask_compose.py intelligence/tests/test_skill_tools.py intelligence/tests/test_kb_candidates.py tests/test_db_delta.py tests/test_pipeline_p0.py
```

Expected: no selected-rule findings in the listed files and all non-baseline selected tests pass.

### Task 9: Remove active dead assignments and ambiguous names (Batch C2)

**Files:**
- Modify: `evolution/strategy4.py`
- Modify: `intelligence/services/refresh_profile.py`
- Modify: `market_feature_store/reports/daily_review.py`
- Modify: `scripts/build_registry.py`
- Modify: `scripts/evolve.py`
- Modify: `scripts/headtohead_ledger.py`
- Modify: `scripts/moneyflow/moneyflow.py`
- Modify: `skills/daily-full-review/scripts/run_review_sync.py`
- Modify: `skills/lib/pdf_ingest_lint.py`
- Modify: `skills/opinion-cross/scripts/winrate_rank.py`
- Modify: `skills/report-search/scripts/cli.py`
- Modify: `skills/stock-deep-dive/scripts/deepdive_gap_list.py`
- Modify: `skills/theme-radar/scripts/radar.py`
- Modify: `skills/up-line/scripts/update.py`

- [ ] **Step 1: Delete only proven-dead assignments**

Apply these exact deletions; retain the expressions that have side effects:

```text
evolution/strategy4.py: delete `wanted = set(dates)`.
intelligence/services/refresh_profile.py: delete `kb_index = ...`.
market_feature_store/reports/daily_review.py: delete the `amount_delta` initialization and calculation block.
scripts/moneyflow/moneyflow.py: delete `empty_retry = []`.
skills/daily-full-review/scripts/run_review_sync.py: call `run_step(...)` without assigning its return to `res` inside `sync_sector_stocks`; the call itself remains.
skills/lib/pdf_ingest_lint.py: delete unused `chain_layer = ...` in `check_role_quality` and `skipped_concepts = set()` in the contradiction check.
skills/report-search/scripts/cli.py: delete `error_type = ...`; `result["error"]` remains the source of truth.
skills/theme-radar/scripts/radar.py: delete `has_def`, `strength`, `total` in `deep_dive_quality_gate_section`, `context` in `map_gap_section`, and `graph` in `map_appendix_section`.
```

- [ ] **Step 2: Replace ambiguous one-letter names without changing values**

Use these names consistently in their local comprehensions/parsers:

```text
scripts/build_registry.py: `l` -> `location` for location dicts; `l` -> `line` for Markdown rows.
scripts/evolve.py: `l` -> `log_parser`.
scripts/headtohead_ledger.py: `l` -> `label` in the KPI comprehension.
skills/opinion-cross/scripts/winrate_rank.py: `l` -> `line` in JSONL loading.
skills/stock-deep-dive/scripts/deepdive_gap_list.py: `l` -> `common_length` in overlap filtering.
skills/up-line/scripts/update.py: `l` -> `table_label` in the table-name lookup.
```

- [ ] **Step 3: Split active same-line statements**

Make each assignment/branch its own indented line in:

```text
market_feature_store/query.py: eight E702 statements around lines 692-704.
scripts/db_delta_export.py: two E702 statements around lines 94-96.
scripts/evolve.py: one E702 statement around line 425.
skills/top-gainers/scripts/query_sectors.py: three E701 branches around lines 95-97.
```

Do not edit the eight E702 statements in excluded `scripts/backtest_sector.py`.

- [ ] **Step 4: Verify manual mechanics**

Run:

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m ruff check evolution intelligence market_feature_store scripts skills --select F841,E741,E701,E702
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q intelligence/tests/test_evolve_suggest.py intelligence/tests/test_evolve_validate.py intelligence/tests/test_headtohead_selections.py intelligence/tests/test_structured_reports.py tests/test_db_delta.py tests/test_moneyflow_ch_preflight.py tests/test_moneyflow_server_aggregation.py tests/test_question_router.py tests/test_theme_radar_lineage.py
/Users/a77/finance-workspace-private/.venv-workbench/bin/python scripts/build_registry.py check-parseability
/Users/a77/finance-workspace-private/.venv-workbench/bin/python scripts/build_registry.py check
```

Expected: only the four legacy files can still appear for the selected Ruff rules; tests and registry checks pass.

### Task 10: Apply audited safe fixes to skill scripts (Batch C3)

**Files:**
- Modify only the explicit skill files in the command below

- [ ] **Step 1: Preview then apply safe fixes**

Run first with `--fix --diff`, inspect, then repeat with `--fix`:

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m ruff check \
  skills/advancers-chart/scripts/feishu_chart.py \
  skills/advancers-chart/scripts/sync.py \
  skills/daily-full-review/scripts/export_increment.py \
  skills/dispatcher/scripts/route.py \
  skills/hithink-market-query/scripts/cli.py \
  skills/lib/pdf_ingest_lint.py \
  skills/limit-advance/scripts/check_coverage.py \
  skills/limit-advance/scripts/dedup_fields.py \
  skills/limit-advance/scripts/scrape.py \
  skills/market-overview/scripts/check_coverage.py \
  skills/market-overview/scripts/verify_and_patch.py \
  skills/opinion-cross/scripts/winrate_rank.py \
  skills/report-search/scripts/api_client.py \
  skills/report-search/scripts/cli.py \
  skills/report-search/scripts/data_processor.py \
  skills/report-search/scripts/example_usage.py \
  skills/report-search/scripts/setup.py \
  skills/report-search/scripts/test_basic.py \
  skills/theme-radar/scripts/radar.py \
  skills/top-gainers-feishu/scripts/query_ma.py \
  --select F401,F541 --fix --diff
```

Expected: only unused imports and redundant `f` prefixes change; no exception path, output text, source-quality gate, or theme-radar ranking expression changes.

- [ ] **Step 2: Run skill-specific regressions**

Run:

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q skills/report-search/scripts/test_basic.py skills/opinion-cross/tests/test_check_opinion_review.py tests/test_pdf_ingest_lint.py tests/test_limit_advance_write.py tests/test_theme_radar_lineage.py
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m ruff check skills --select F401,F541,E401,E701,E702,E741,F841
```

Expected: the listed mechanical rules are zero in active skills; E402 remains for Batch D.

- [ ] **Step 3: Compare full pytest and commit Batch C**

Run:

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q
git diff --check
git add docs evolution intelligence market_feature_store research scripts skills tests
git diff --cached --check
git commit -m "style: clear active Ruff mechanical debt"
```

Expected: only the 11 baseline failure identities; one mechanical-cleanup commit. Confirm `git diff --cached --name-only` contains none of the four legacy files before committing.

### Task 11: Document intentional import order and isolate legacy scripts (Batch D)

**Files:**
- Create: `ruff.toml`
- Modify: 18 active direct-execution scripts with E402 listed below

- [ ] **Step 1: Add exact legacy exclusions and freeze the lint contract**

Create `ruff.toml`:

```toml
target-version = "py39"
force-exclude = true
extend-exclude = [
  # CLAUDE.md marks these old market.duckdb/table consumers as broken pending migration.
  "scripts/backtest_sector.py",
  "scripts/detect_turning_points.py",
  "scripts/sync_to_local.py",
  "scripts/render_daily_review_template.py",
]

[lint]
select = ["E4", "E7", "E9", "F"]
```

- [ ] **Step 2: Add reasoned line-level E402 suppressions**

For every import below, retain its preceding path/bootstrap statement, add a one-line reason comment, and append `# noqa: E402` to the import itself:

```text
research/market-hypothesis/_scripts/double_red_anchor_stock_study.py: market_feature_store.db import after PROJECT_DIR insertion.
research/market-hypothesis/_scripts/strategy1_drawdown_risk.py: market_feature_store.db/query imports after PROJECT_DIR insertion.
research/market-hypothesis/_scripts/strategy1_limit_ma5_impact.py: market_feature_store.db/query imports after PROJECT_DIR insertion.
scripts/build_daily_ops_ledger.py: intelligence.paths import after ROOT insertion.
scripts/build_evidence_hunter_report.py: research_queue import after ROOT insertion.
scripts/build_market_triggered_theme_brief.py: market_feature_store.db import after ROOT insertion.
scripts/build_theme_evidence_readiness.py: sibling scripts import after scripts path insertion.
scripts/check_daily_review_data.py: project package import after ROOT insertion.
scripts/export_finhot_evidence_to_obsidian.py: project package import after ROOT insertion.
scripts/fast_daily_sync.py: market_feature_store.db import after PROJECT_DIR insertion; the unused direct duckdb import has already been removed.
scripts/fidelity_replay_eval.py: intelligence.eval import block after ROOT insertion.
scripts/fidelity_runtime_status.py: runtime_status import after ROOT insertion.
scripts/loop_health_report.py: intelligence.userspace import after ROOT insertion.
scripts/render_sw_l1_theme_matrix_html.py: market_feature_store.db import after PROJECT_DIR insertion.
scripts/research_judge.py: research_judge import after ROOT insertion.
scripts/validate_strategy_matrix_forward_returns.py: market_feature_store.db import after ROOT insertion.
skills/theme-radar/scripts/radar.py: sibling `theme_radar_quality_rules` import after PROJECT_SCRIPTS insertion.
skills/up-line/scripts/update.py: shared `feishu_utils` import after PROJECT_DIR/shared insertion.
```

Use this exact shape at each site:

```python
# Direct execution needs the repository root on sys.path before project imports.
from market_feature_store.db import connect  # noqa: E402
```

For sibling/shared imports, change “repository root” to “scripts directory” or “shared helper directory” so the explanation is truthful.

- [ ] **Step 3: Prove active scope is zero and legacy remains explicit**

Run:

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m ruff check .
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m ruff check scripts/backtest_sector.py scripts/detect_turning_points.py scripts/sync_to_local.py scripts/render_daily_review_template.py --no-force-exclude --statistics
```

Expected: first command exits 0; second command still reports 27 legacy findings, proving exclude did not “fix” or silently erase their documented broken state.

- [ ] **Step 4: Run import-order regressions and commit policy**

Run:

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q tests/test_daily_ops_ledger.py tests/test_evidence_hunter.py tests/test_fidelity_runtime.py tests/test_research_judge.py tests/test_theme_radar_lineage.py
/Users/a77/finance-workspace-private/.venv-workbench/bin/python scripts/build_registry.py check
git diff --check
git add ruff.toml research/market-hypothesis/_scripts scripts skills/theme-radar/scripts/radar.py skills/up-line/scripts/update.py
git diff --cached --check
git commit -m "chore: document Ruff import-order and legacy policy"
```

Expected: selected tests pass and the commit contains only `ruff.toml` plus reasoned E402 annotations; excluded legacy bodies remain unchanged.

### Task 12: Add the fixed-version local and CI ratchet (Batch E)

**Files:**
- Modify: `.pre-commit-config.yaml`
- Modify: `.github/workflows/workbench-check.yml`

- [ ] **Step 1: Add staged-file Ruff to pre-commit**

Add this repository before the existing `local` repository:

```yaml
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.11.13
    hooks:
      - id: ruff-check
        args: ["--config=ruff.toml"]
```

The hook receives only staged filenames in normal commits; `ruff.toml` still excludes the four exact legacy paths.
`force-exclude = true` is required because pre-commit passes those filenames explicitly; without it, Ruff would lint an excluded legacy file whenever it was staged.

- [ ] **Step 2: Install the same Ruff version in CI and run it before pytest**

In `.github/workflows/workbench-check.yml`, append `ruff==0.11.13` to the Python dependency install command and insert:

```yaml
      - name: Lint Python with Ruff
        run: python -m ruff check .
```

Place the lint step immediately before `Test Python packages` so cheap static failures stop the job before the full suite.

- [ ] **Step 3: Validate hook and workflow syntax locally**

Run:

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m ruff check .
pre-commit validate-config
pre-commit run ruff-check --all-files
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -c "import yaml; yaml.safe_load(open('.github/workflows/workbench-check.yml', encoding='utf-8'))"
```

Expected: all commands exit 0.

- [ ] **Step 4: Commit enforcement separately**

Run:

```bash
git diff --check
git add .pre-commit-config.yaml .github/workflows/workbench-check.yml
git diff --cached --check
git commit -m "ci: enforce fixed-version Ruff checks"
```

Expected: one enforcement-only commit.

### Task 13: Final verification, risk scan, and handoff

**Files:**
- Modify after successful validation: `/Users/a77/agent-memory/20_projects/finance-workspace-private.md`
- Verify: all commits since `78187ec7`

- [ ] **Step 1: Run the final static and test gates**

Run:

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m ruff check .
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q
pre-commit run --all-files
git diff --check 78187ec7..HEAD
```

Expected: Ruff 0; pytest has only the 11 Task 1 baseline failure identities and a larger pass count; pre-commit and diff checks pass.

- [ ] **Step 2: Verify the legacy and risk boundaries**

Run:

```bash
git diff --name-only 78187ec7..HEAD
git diff --name-only 78187ec7..HEAD | rg '(^|/)(\.env($|\.)|mcp_config\.json$|feishu_config\.json$|.*\.(pdf|zip|duckdb|db|sqlite|sqlite3|pptx)$|\.DS_Store$|__MACOSX/|\._|__pycache__/|\.venv/|venv/)'
git diff --exit-code 78187ec7..HEAD -- scripts/backtest_sector.py scripts/detect_turning_points.py scripts/sync_to_local.py scripts/render_daily_review_template.py
git status --short
```

Expected: risk scan has no matches, legacy body diff exits 0, worktree is clean.

- [ ] **Step 3: Write project-level memory**

Append one concise dated handoff record to `/Users/a77/agent-memory/20_projects/finance-workspace-private.md` containing:

```text
Ruff 0 means active scope zero plus four exact documented legacy excludes; it does not mean those legacy scripts run.
Correctness fixes: report-search no-key CLI, Feishu runtime type hints, broker-only PDF annotations, fail-closed Feishu batch counts.
Architecture decision: optional DuckDB dependency/open/available states are centralized in retrieval_cache.
Enforcement: Ruff 0.11.13 is pinned in pre-commit and workbench CI.
Verification: final pytest totals and the unchanged 11 baseline failure identities.
```

Do not copy chat history or individual lint-line details into memory.

- [ ] **Step 4: Report without expanding authority**

Report exact commits, Ruff before/after counts, pytest before/after totals, the four excluded legacy paths, and the fixed-version gates. State explicitly that the branch was not pushed, merged, deployed, or loaded by 8792/8799; wait for the user before any of those actions.

## Plan self-review

- [ ] **Spec coverage:** map design Batch A/B/C/D/E to Tasks 2-6 / 7 / 8-10 / 11 / 12, and verify final acceptance in Task 13.
- [ ] **Placeholder scan:** run the following command and require no output:

```bash
rg -n 'T''BD|TO''DO|implement ''later|fill ''in details|similar ''to Task' docs/superpowers/plans/2026-08-02-ruff-debt-burn-down.md
```

- [ ] **Type consistency:** verify `DuckDBConnectionResult.status`, `.connection`, `.error_type`, and `.available` use the same names in tests, implementation, and every migrated consumer.
- [ ] **Boundary consistency:** verify the four paths in `ruff.toml`, the explicit legacy Ruff command, the legacy body diff command, and the final report are identical.
