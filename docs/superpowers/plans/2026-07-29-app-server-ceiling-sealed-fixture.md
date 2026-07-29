# App Server Ceiling Sealed Fixture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a content-addressed, no-gold instruction export and a physical 2026-07-24 finance/Wiki PIT fixture that can be consumed identically by headless and a later App Server experiment.

**Architecture:** Four focused modules own deterministic leakage scanning, Git-object export, physical finance/Wiki snapshotting, and fixture sealing. A thin CLI composes them into a private root under `~/.finance-runtime`; databases, indexes, and review packets never enter Git. The fixture remains unsealed until an independent semantic-leak PASS sidecar is hash-bound to its manifests.

**Tech Stack:** Python 3.12, dataclasses, `hashlib`, `unicodedata`, Git plumbing commands, DuckDB, the existing KB Hybrid RAG CLI, pytest, Ruff.

---

## File map

- Create `intelligence/eval/ceiling_leakage.py`: frozen normalization/tokenization, forbidden corpus, deterministic scan, semantic receipt validation.
- Create `intelligence/eval/ceiling_instruction_export.py`: no-`.git`, regular-file-only export from one Git revision.
- Create `intelligence/eval/ceiling_pit_fixture.py`: filtered DuckDB, cutoff Wiki export, Hybrid index build/audit, manifest seal.
- Create `scripts/build_agent_runtime_ceiling_fixture.py`: orchestration CLI only.
- Create four matching test modules under `intelligence/tests/`.

### Task 1: Freeze deterministic leakage detection

**Files:**
- Create: `intelligence/eval/ceiling_leakage.py`
- Test: `intelligence/tests/test_ceiling_leakage.py`

- [x] **Step 1: Write failing normalization/tokenization tests**

```python
from intelligence.eval.ceiling_leakage import normalize_char_stream, tokenize


def test_normalization_is_nfkc_casefolded_and_punctuation_free() -> None:
    assert normalize_char_stream("Ａ股， Weekly  Cause！") == "a股weeklycause"


def test_tokenization_uses_han_codepoints_and_alnum_runs() -> None:
    assert tokenize("瑞华泰 PB 4.33") == ("瑞", "华", "泰", "pb", "4", "33")
```

- [x] **Step 2: Run RED**

Run:

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest intelligence/tests/test_ceiling_leakage.py -q
```

Expected: collection fails because the module does not exist.

- [x] **Step 3: Implement the exact v3 algorithms**

```python
def normalize_char_stream(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    return "".join(
        char for char in normalized
        if not char.isspace() and not unicodedata.category(char).startswith("P")
    )
```

`tokenize()` treats each Han code point as one token and each maximal case-folded alphanumeric run as one token. `scan_export()` fails on a full normalized string, 12-character n-gram, 6-token n-gram, or token-set Jaccard `>= 0.80` for a forbidden sentence with at least 8 tokens.

- [x] **Step 4: Build `ForbiddenCorpus` from frozen evaluator sources**

Include raw questions, conversation context, required outputs, direct targets, reference answers, expected facts, pass rules, prior candidate/published answers, and post-cutoff handoff/result prose. No exception may suppress a full question, reference sentence, required-output ID, or post-cutoff result fragment.

- [x] **Step 5: Add deterministic and semantic-positive fixtures**

```python
@pytest.mark.parametrize(
    "leak",
    [
        "昨天 的 反弹，能持续多久？",
        "scenario_ range",
        "先按3至5个交易日的短周期修复看",
        "截至2026-07-27的后续验收结果",
    ],
)
def test_scan_rejects_known_leaks(tmp_path: Path, leak: str) -> None:
    export = tmp_path / "export"
    export.mkdir()
    (export / "leak.md").write_text(leak, encoding="utf-8")
    assert scan_export(export, frozen_corpus()).status == "rejected"
```

The semantic review packet also includes a paraphrase that deliberately shares no deterministic n-gram: `这周下跌主要是风险偏好收缩和高位筹码松动共同导致`.

- [x] **Step 6: Implement hash-bound semantic receipt validation**

```python
@dataclass(frozen=True)
class SemanticLeakReceipt:
    export_manifest_sha256: str
    deterministic_scan_sha256: str
    model: str
    prompt_sha256: str
    reviewer: str
    verdict: Literal["pass", "fail"]
    receipt_sha256: str
```

Reject hash mismatch, self-authored reviewer, model other than `gpt-5.6-sol`, bad self hash, or non-PASS verdict.

- [x] **Step 7: Run GREEN and commit**

Run:

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest intelligence/tests/test_ceiling_leakage.py -q
git add intelligence/eval/ceiling_leakage.py intelligence/tests/test_ceiling_leakage.py
git commit -m "feat: freeze ceiling fixture leakage scan"
```

Expected: all leakage tests pass.

### Task 2: Export the sealed instruction tree

**Files:**
- Create: `intelligence/eval/ceiling_instruction_export.py`
- Test: `intelligence/tests/test_ceiling_instruction_export.py`

- [ ] **Step 1: Write a failing safety test**

Create a temporary Git repo containing a regular production file, a symlink, `docs/verification/result.md`, and `intelligence/tests/gold.json`. Assert that only the regular allowlisted file can enter the export.

- [ ] **Step 2: Implement explicit scope**

```python
INCLUDE_PREFIXES = (
    "intelligence/services/",
    "intelligence/workbench_skills/",
    "intelligence/README.md",
    "skills/",
    "UBIQUITOUS_LANGUAGE.md",
)
EXCLUDE_PREFIXES = (
    ".git/", ".agent-memory/", "tmp/", "docs/",
    "intelligence/eval/", "intelligence/tests/",
)
```

Generate a neutral root `AGENTS.md` containing only read-only finance research rules, PIT cutoff discipline, `finance-tool` discovery, and no benchmark/rubric language.

- [ ] **Step 3: Export directly from Git objects**

Use `git ls-tree -r -z source_revision` for mode/type/path and `git cat-file blob source_revision:relative_path` for bytes. Reject symlink/submodule modes. Write to a temporary sibling with create-if-absent semantics, chmod files `0444` and directories `0555`, then atomically rename to the content-addressed destination.

- [ ] **Step 4: Seal `instruction-export.manifest.json`**

Record source revision, allow/exclude lists, neutral instruction hash, file count, and for every file: relative path, Git mode, byte count, SHA-256. Bind the deterministic leak-scan hash.

- [ ] **Step 5: Test link/mutation/overwrite failures**

Prove no `.git`, all entries are regular files, every file has `st_nlink == 1`, mutation invalidates audit, and a different manifest cannot overwrite an existing destination.

- [ ] **Step 6: Run GREEN and commit**

Run:

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest intelligence/tests/test_ceiling_instruction_export.py -q
git add intelligence/eval/ceiling_instruction_export.py intelligence/tests/test_ceiling_instruction_export.py
git commit -m "feat: build sealed instruction export"
```

Expected: export safety and audit tests pass.

### Task 3: Build the physical finance PIT DuckDB

**Files:**
- Create: `intelligence/eval/ceiling_pit_fixture.py`
- Test: `intelligence/tests/test_ceiling_pit_fixture.py`

- [ ] **Step 1: Write a failing future-row/unknown-column test**

The source DB contains rows on 2026-07-24 and 2026-07-25 plus a table with `mystery_effective_when`. The builder must exclude the future row and reject the unknown temporal schema.

- [ ] **Step 2: Implement the conservative temporal policy**

Recognize `trade_date`, `date`, `source_date`, `report_date`, `ann_date`, `announcement_date`, `end_date`, `report_period`, `source_update_time`, `updated_at`, `created_at`, and `published_at`. Any other column whose name contains `date`, `time`, `year`, `period`, or `when` blocks that table as `unclassified_temporal_column`.

- [ ] **Step 3: Implement `build_filtered_duckdb()`**

Open the source read-only. Copy each base table into a new DB with all recognized non-null temporal values `<= 2026-07-24T23:59:59+08:00`; materialize views after dependencies. Record source/target rows and maxima. Never byte-copy the source DB.

Core predicate construction:

```python
predicates = [
    f"({quote_ident(column)} IS NULL OR {normalized_sql(column)} <= ?::TIMESTAMP)"
    for column in temporal_columns
]
```

- [ ] **Step 4: Implement post-build audit**

Reopen the target read-only, verify every maximum, check path/mode/hash, confirm no external attached DB remains, and seal the target SHA-256. Chmod the DB and final fixture root read-only only after all components pass.

- [ ] **Step 5: Cover SQL DATE, `YYYYMMDD`, timestamps, nulls, malformed values, empty tables, and views**

Malformed date-bearing values fail closed; they are not copied as opaque strings.

- [ ] **Step 6: Run GREEN and commit**

Run:

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest intelligence/tests/test_ceiling_pit_fixture.py -q
git add intelligence/eval/ceiling_pit_fixture.py intelligence/tests/test_ceiling_pit_fixture.py
git commit -m "feat: build physical finance pit fixture"
```

### Task 4: Export cutoff Wiki and build a fresh true-Hybrid index

**Files:**
- Modify: `intelligence/eval/ceiling_pit_fixture.py`
- Modify: `intelligence/tests/test_ceiling_pit_fixture.py`

- [ ] **Step 1: Test cutoff revision selection**

With one pre-cutoff and one post-cutoff commit, `select_revision_at_cutoff()` must choose the pre-cutoff SHA and omit the post-cutoff file.

- [ ] **Step 2: Export `wiki/` regular blobs from the selected revision**

Select with `git rev-list -1 --before=2026-07-24T23:59:59+08:00 HEAD`. Strip the leading `wiki/`, reject symlinks/submodules, and hash every file. For the real repo this must resolve to `883815c9b43658339b6308a6494536d2e71b9ad7`.

- [ ] **Step 3: Invoke the isolated 9053b0c4 RAG builder**

Pass argv/environment arrays equivalent to:

```bash
KB_VAULT=/private/fixture/wiki RAG_INDEX_DIR=/private/fixture/index KB_RAG_PYTHON=/Users/a77/knowledge-base-private/.rag_venv/bin/python3 /Users/a77/knowledge-base-private/.rag_venv/bin/python3 /Users/a77/finance-workspace-private/tmp/knowledge-base-phase-c-freshness/scripts/rag_index.py build --model bge-m3
```

- [ ] **Step 4: Validate content identity and one true-Hybrid probe**

Require the 9053b0c4 freshness code, runtime `fresh`, exact index hashes, source-file count, Python version/path, one bounded Hybrid query, and no use of `/Users/a77/知识库` as data or interpreter.

- [ ] **Step 5: Add link/mutation/future-date tests, run GREEN, commit**

Run:

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest intelligence/tests/test_ceiling_pit_fixture.py -q
git add intelligence/eval/ceiling_pit_fixture.py intelligence/tests/test_ceiling_pit_fixture.py
git commit -m "feat: build cutoff wiki hybrid fixture"
```

### Task 5: Compose the private fixture CLI

**Files:**
- Create: `scripts/build_agent_runtime_ceiling_fixture.py`
- Test: `intelligence/tests/test_build_agent_runtime_ceiling_fixture.py`

- [ ] **Step 1: Test dry-run and fail-closed ordering**

Dry-run writes nothing. A deterministic leak blocks before DB/index work. A missing semantic receipt ends `semantic_review_pending`. A mismatched receipt cannot seal.

- [ ] **Step 2: Implement deterministic order**

Resolve revisions → build forbidden corpus → export instructions → deterministic scan → build finance DB → export Wiki → build/validate index → write semantic request → validate receipt → final audit/seal.

- [ ] **Step 3: Use the stable private root**

```text
/Users/a77/.finance-runtime/app-server-ceiling/2026-07-24/{manifest_input_sha256[:16]}/
```

Write `fixture.manifest.json`, `instruction-export.manifest.json`, `deterministic-leak-scan.json`, `semantic-leak-review-request.json`, and the external `semantic-leak-review-receipt.json`. Databases, Wiki, index, and model files remain private.

After sealing, atomically write `/Users/a77/.finance-runtime/app-server-ceiling/2026-07-24/sealed-fixture.json` with only the sealed relative directory name, manifest SHA-256, and self hash. It is a receipt, not a symlink, and the consumer must revalidate the target manifest.

- [ ] **Step 4: Run focused tests and Ruff**

Run:

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest intelligence/tests/test_ceiling_leakage.py intelligence/tests/test_ceiling_instruction_export.py intelligence/tests/test_ceiling_pit_fixture.py intelligence/tests/test_build_agent_runtime_ceiling_fixture.py -q
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m ruff check intelligence/eval/ceiling_leakage.py intelligence/eval/ceiling_instruction_export.py intelligence/eval/ceiling_pit_fixture.py scripts/build_agent_runtime_ceiling_fixture.py
```

- [ ] **Step 5: Commit**

Run:

```bash
git add scripts/build_agent_runtime_ceiling_fixture.py intelligence/tests/test_build_agent_runtime_ceiling_fixture.py
git commit -m "feat: seal app server ceiling fixture"
```

### Task 6: Build, independently review, and seal the real fixture

**Files:**
- Private: `/Users/a77/.finance-runtime/app-server-ceiling/2026-07-24/`
- Create: `docs/verification/app-server-ceiling-fixture-2026-07-29.md`

- [ ] **Step 1: Build through `semantic_review_pending`**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 /Users/a77/finance-workspace-private/.venv-workbench/bin/python scripts/build_agent_runtime_ceiling_fixture.py --source-revision "$(git rev-parse HEAD)" --finance-db /Users/a77/finance-workspace-private/db/market_feature_store.duckdb --kb-source-repo /Users/a77/knowledge-base-private --kb-code-root /Users/a77/finance-workspace-private/tmp/knowledge-base-phase-c-freshness --kb-code-revision 9053b0c4137428e9ad9d8b4be3ba475b7377b435 --kb-rag-python /Users/a77/knowledge-base-private/.rag_venv/bin/python3 --question-file /Users/a77/.finance-runtime/evals/adaptive-runtime-five-cases-2026-07-27.json --reference-file intelligence/tests/fixtures/capability_monotonicity_cases.json --as-of 2026-07-24 --output-root /Users/a77/.finance-runtime/app-server-ceiling/2026-07-24
```

Expected: exit 3 plus a hash-bound review request; fixture status is not sealed.

- [ ] **Step 2: Run one independent read-only `gpt-5.6-sol` semantic-leak review**

The reviewer receives only the request packet/candidate snippets, cannot modify the fixture/repo, and writes a strict receipt.

- [ ] **Step 3: Seal with the receipt and re-audit**

Rerun the same command with `--semantic-receipt /private/tmp/app-server-ceiling-semantic-leak-receipt.json --seal`. Expected: deterministic/semantic scans, date/link/hash audits, and true-Hybrid probe all PASS.

- [ ] **Step 4: Commit a bounded verification receipt**

Record manifest SHA-256, source revisions, maximum dates, file/table counts, index hash, true-Hybrid status, leak receipts, and unchanged live repositories. Do not commit private data/index/model files.

Run:

```bash
git add docs/verification/app-server-ceiling-fixture-2026-07-29.md
git commit -m "docs: verify sealed app server ceiling fixture"
```

### Task 7: Proportional regression and plan completion

- [ ] **Step 1: Run focused and existing PIT/RAG tests**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest intelligence/tests/test_ceiling_leakage.py intelligence/tests/test_ceiling_instruction_export.py intelligence/tests/test_ceiling_pit_fixture.py intelligence/tests/test_build_agent_runtime_ceiling_fixture.py intelligence/tests/test_pit_snapshot.py intelligence/tests/test_kb_rag.py -q
```

- [ ] **Step 2: Run downstream tests and diff audit**

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest intelligence/tests/test_run_agent_runtime_benchmark.py intelligence/tests/test_headless_tool_gateway.py intelligence/tests/test_codex_headless_runtime.py -q
git diff --check
```

- [ ] **Step 3: Mark this plan complete and commit**

```bash
git add docs/superpowers/plans/2026-07-29-app-server-ceiling-sealed-fixture.md
git commit -m "docs: complete sealed fixture implementation plan"
```
