# Immutable evidence packet
No reasoning transcript or other-axis results included.
Raw command output is authoritative. Prior-stage prose may contain errors: never promote a proposed correction or unsupported PASS label to an observed result. Missing evidence must remain explicit.


## explore/parsed.json
```text
{
  "claims_examined": {
    "absent_claims_map": "candidate/claims/source-map (and .md) not found; C3 verification scope taken directly from _data_checks implementation and its docstring claims",
    "c3_data_contract_checks": [
      "fact_other_stocks_allcols (bidirectional EXCEPT ALL, all columns)",
      "retained_rows_full_column_identical (in-window non-key rows incl. updated_at, count == expected_total_rows - |write_keys|)",
      "target_outside_window_allcols",
      "hithink_source_untouched / hithink_adjustment_untouched (whole-table bidirectional)",
      "parallel_source_md5_binding (recomputed from prod. baseline, bound to both receipts' child reports)",
      "keyset_fullfield_oracle (parallel rows read from prod. baseline, parquet rows from frozen file; OHLC/pre_close/pct_chg/amount/turnover==None/volume/source-label recomputed with Decimal quantization; expected_retained == spec.expected_total_rows - len(write_keys))",
      "technical_protected_allcols / window_protected_allcols",
      "window_golden_triples + expected_window_counts_match_golden",
      "technical_exact_set (cal64[25:]) + expected_technical_count_matches_calendar",
      "pinned_technical_target_day / pinned_windows_target_day",
      "market_daily_untouched"
    ]
  },
  "gating": "data checks only run when preflight_ok and args_ok and schema_ok and spec is dict; exceptions funnel into data_checks_error structured FAIL (rc=2); final verdict rc 0/2; production sha checked before and after (TOCTOU)",
  "notes_on_prior_c3_focus": "retained-row definition (write_keys = gap_parallel | gap_parquet | shell_date) is the central C3 lever; pre-window rows (before window_start) are covered only by target_outside_window_allcols; oracle reads source rows from prod. baseline (input-independence discipline)",
  "file": "candidate/scripts/verify_302132_backfill_acceptance.py, _data_checks (lines ~567-732), read in full alongside main() and _validate_receipt",
  "imprecision_risks": [
    "cal bounded below by hardcoded '2026-06-01' in market-calendar query — limits golden-triple derivation if window_start predates that bound",
    "src dict uses first-wins on duplicate trade_date (UNION ALL collision between parallel and parquet sources silently favors parallel rows)",
    "pre_close/pct oracle tolerance 1e-9 on floats after Decimal quantize; turnover hard-required None in keyset rows"
  ],
  "target_checks_location": "candidate/scripts/verify_302132_backfill_acceptance.py::_data_checks; gate at main() spec_ok branch",
  "tests_ran": false,
  "limits": [
    "claims/source-map absent at both attempted paths; claim list reconstructed from code docstring and implementation, not an author-supplied map",
    "No execution this stage: no bash, no probes run, no fixtures built; nothing verified empirically",
    "Files beyond the acceptance script not enumerated/read (stage restricted to _data_checks and claims map)",
    "Only C3 in scope; the production-shaped 64/39/161 counts remain a separate limitation unless directly observed"
  ],
  "next_stage_commands": [
    {
      "cmd": "OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /Users/a77/finance-workspace-private/.venv-workbench/bin/python -B /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-06/quality/work/positive_control.py",
      "note": "mandatory first bash call in execute stage; expected exit 1 with probe_bug text",
      "seq": 1
    },
    {
      "cmd": "OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /Users/a77/finance-workspace-private/.venv-workbench/bin/python -B -m pytest --junitxml=<work>/execute/xml/test_seeded_c3.xml <work>/probes/test_seeded_c3.py",
      "note": "seven prior C3 assertions with receipt-path/OTHER-date fixture repair; uses actual external acceptance entry",
      "seq": 2
    },
    {
      "cmd": "OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /Users/a77/finance-workspace-private/.venv-workbench/bin/python -B -m pytest --junitxml=<work>/execute/xml/test_earlier_fixture_adapter.xml <work>/probes/test_earlier_fixture_adapter.py",
      "note": "three prior new assertions; host-only fixture repair adds real pre-window row to baseline and clone and rebinds receipt hashes; supplied evidence, not new authoring",
      "seq": 3
    }
  ],
  "probe_files": [
    {
      "path": "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-06/quality/work/probes/test_seeded_c3.py",
      "provenance": "prior reviewer C3 assertions + host fixture repair (receipt-path/OTHER-date); 7 cases; drives the actual external acceptance entry (scripts/verify_302132_backfill_acceptance.py), not only helpers; duplicate cases disclose clone-only PK removal"
    },
    {
      "path": "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-06/quality/work/probes/test_earlier_fixture_adapter.py",
      "provenance": "prior new assertions + host-only fixture repair adding a real pre-window row to both baseline and clone and rebinding receipt hashes; 3 cases; supplied evidence, not new authoring; also uses actual external acceptance entry"
    }
  ],
  "stage_scope": "C3 only; revision 3c5b3c9a6f0c1fe9401c424bc5ac396cf46fbc59 vs baseline 4cc15e703f81bce8abadee00f68caacdb0c72b4d; current main d21707ca6c71e4e39194b01ef9549bc893595d3f not integrated",
  "complete": true,
  "stage": "explore",
  "axis": "quality",
  "revision": "3c5b3c9a6f0c1fe9401c424bc5ac396cf46fbc59",
  "baseline": "4cc15e703f81bce8abadee00f68caacdb0c72b4d"
}

```


## execute/parsed.json
```text
{
  "author_test_counts": {
    "errors": 0,
    "failed": 0,
    "passed": 0,
    "note": "no author tests run per instruction"
  },
  "claims": [
    {
      "claim": "Outside-window mutations (amount, timestamp, delete, insert, duplicate, other_stock) are rejected by the candidate acceptance entry",
      "state": "verified"
    },
    {
      "claim": "Baseline passes acceptance",
      "state": "verified"
    },
    {
      "claim": "Earlier-than-window and null-column mutations are rejected with a real pre-window row in both baseline and clone",
      "state": "verified"
    },
    {
      "claim": "Production-shaped 64/39/161 counts correctness",
      "state": "out_of_scope"
    }
  ],
  "findings": [
    "All 10 supplied probes passed; both suites exercise the actual external acceptance entry scripts/verify_302132_backfill_acceptance.py, not only a helper",
    "Duplicate cases disclose clone-only PK removal",
    "Host fixture adapter (real pre-window row added to both baseline and clone, receipt hashes rebound) confirms candidate rejects pre-window mutations and passes baseline"
  ],
  "limits": [
    "Production-shaped 64/39/161 counts remain a separate limitation unless directly observed; not observed here",
    "No git/network/live vendors/credentials/production DB; synthetic DuckDB inside work only; no candidate writes"
  ],
  "positive_control": {
    "command": "OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /Users/a77/finance-workspace-private/.venv-workbench/bin/python -B /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-06/quality/work/positive_control.py",
    "exit_code": 1,
    "message": "AssertionError: intentional probe_bug control",
    "observed": true,
    "raw_files": [
      "execute/001-bash/request.json",
      "execute/001-bash/result.json",
      "execute/001-bash/output.log"
    ]
  },
  "probe_provenance": "Supplied probes are prior reviewer assertions plus host fixture repairs (receipt-path/OTHER-date repair in test_seeded_c3.py; host-only adapter adding a real pre-window row to both baseline and clone and rebinding receipt hashes in test_earlier_fixture_adapter.py). Executed fresh in this session against the actual external acceptance entry; supplied evidence, not new authoring. Supplied files unmodified.",
  "reviewer_probe_counts": {
    "errors": 0,
    "failed": 0,
    "passed": 10,
    "total": 10
  },
  "supplied_probe_counts": {
    "cases": 10,
    "errors": 0,
    "failed": 0,
    "files": 2,
    "passed": 10
  },
  "supplied_probe_results": {
    "basetemp": "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-06/quality/work/tmp/supplied",
    "command": "pytest probes/test_seeded_c3.py probes/test_earlier_fixture_adapter.py --rootdir=work --junitxml=work/probe-results-supplied.xml -p no:cacheprovider --basetemp=work/tmp/supplied",
    "detail": {
      "probes/test_earlier_fixture_adapter.py": {
        "passed": [
          "test_new_outside_window_mutations_fail[earlier_than_window]",
          "test_new_outside_window_mutations_fail[null_column]",
          "test_baseline_with_earlier_row_pass"
        ]
      },
      "probes/test_seeded_c3.py": {
        "passed": [
          "test_outside_window_mutation_fails[amount]",
          "test_outside_window_mutation_fails[timestamp]",
          "test_outside_window_mutation_fails[delete]",
          "test_outside_window_mutation_fails[insert]",
          "test_outside_window_mutation_fails[duplicate]",
          "test_outside_window_mutation_fails[other_stock]",
          "test_baseline_pass"
        ]
      }
    },
    "exit_code": 0,
    "syntax_check": "ast.parse OK on both supplied files",
    "xml": "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-06/quality/work/probe-results-supplied.xml"
  },
  "complete": true,
  "stage": "execute",
  "axis": "quality",
  "revision": "3c5b3c9a6f0c1fe9401c424bc5ac396cf46fbc59",
  "baseline": "4cc15e703f81bce8abadee00f68caacdb0c72b4d"
}

```


## work/EXPLORE.md
MISSING: not delivered by previous stage. No substitute was authored.


## work/EXECUTE.md
```text
# EXECUTE — PR #813 C3 (rev 3c5b3c9a6f0c1fe9401c424bc5ac396cf46fbc59, baseline 4cc15e703f81bce8abadee00f68caacdb0c72b4d)

## Positive control (first bash, controller-enforced)
Command: `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /Users/a77/finance-workspace-private/.venv-workbench/bin/python -B .../quality/work/positive_control.py`
Result: exit code 1, `AssertionError: intentional probe_bug control` — observed in session output and raw execute/001-bash logs.

## Syntax check
`ast.parse` OK on both supplied probe files (test_seeded_c3.py, test_earlier_fixture_adapter.py).

## Supplied probe run
Single pytest command, both supplied files, rootdir=work, fresh XML `probe-results-supplied.xml`, basetemp `work/tmp/supplied`.
Result: **10 passed, 0 failed, 0 errors** in 13.56s.
- test_seeded_c3.py: 7 passed (outside-window mutations amount/timestamp/delete/insert/duplicate/other_stock fail acceptance; baseline passes)
- test_earlier_fixture_adapter.py: 3 passed (earlier-than-window and null-column mutations fail; baseline with real pre-window row passes)

Both suites drive the actual external acceptance entry (scripts/verify_302132_backfill_acceptance.py), not only a helper. Duplicate cases disclose clone-only PK removal.

## Probe provenance
Probes are prior reviewer assertions plus host fixture repairs (receipt-path/OTHER-date repair in test_seeded_c3.py; host-only fixture repair adding a real pre-window row to both baseline and clone and rebinding receipt hashes in test_earlier_fixture_adapter.py). Executed fresh in this session; supplied evidence, not new authoring.

## Counts
- reviewer_probe_counts: passed=10, failed=0, errors=0
- author_test_counts: passed=0, failed=0, errors=0 (none run, per instruction)
- supplied_probe_counts: files=2, cases=10, all passed

## Findings
- All outside-window mutation probes are correctly rejected by the candidate's acceptance verification; baseline passes.
- Pre-window row adapter confirms candidate behavior with realistic earlier data.

## Limits
- Production-shaped 64/39/161 counts remain a separate limitation unless directly observed; not observed here.
- No git/network/live vendors/production DB; synthetic DuckDB in work only.

```


## execute/commands/001-bash/output.log
```text
Traceback (most recent call last):
  File "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-06/quality/work/positive_control.py", line 1, in <module>
    assert 1 == 2, "intentional probe_bug control"
           ^^^^^^
AssertionError: intentional probe_bug control

```


## execute/commands/001-bash/request.json
```text
{"toolCallId":"call_63a1e9a9b9a94f73880ed3f9","params":{"command":"OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /Users/a77/finance-workspace-private/.venv-workbench/bin/python -B /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-06/quality/work/positive_control.py"}}
```


## execute/commands/001-bash/result.json
```text
{"exitCode":1}
```


## execute/commands/002-bash/output.log
```text
/opt/homebrew/Cellar/python@3.12/3.12.13_2/Frameworks/Python.framework/Versions/3.12/Resources/Python.app/Contents/MacOS/Python: can't open file '/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-06/quality/work/ast_check.py': [Errno 2] No such file or directory

```


## execute/commands/002-bash/request.json
```text
{"toolCallId":"call_08fdcbde9fbe4f91bb028850","params":{"command":"/Users/a77/finance-workspace-private/.venv-workbench/bin/python -B /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-06/quality/work/ast_check.py"}}
```


## execute/commands/002-bash/result.json
```text
{"exitCode":2}
```


## execute/commands/004-bash/output.log
```text
SYNTAX OK test_seeded_c3.py
SYNTAX OK test_earlier_fixture_adapter.py

```


## execute/commands/004-bash/request.json
```text
{"toolCallId":"call_c26fd003171f445c998430aa","params":{"command":"/Users/a77/finance-workspace-private/.venv-workbench/bin/python -B /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-06/quality/work/ast_check.py"}}
```


## execute/commands/004-bash/result.json
```text
{"exitCode":0}
```


## execute/commands/005-bash/output.log
```text
============================= test session starts ==============================
platform darwin -- Python 3.12.13, pytest-8.3.5, pluggy-1.6.0 -- /Users/a77/finance-workspace-private/.venv-workbench/bin/python
rootdir: /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-06/quality/work
plugins: anyio-4.14.1
collecting ... collected 10 items

../quality/work/probes/test_seeded_c3.py::test_outside_window_mutation_fails[amount] PASSED [ 10%]
../quality/work/probes/test_seeded_c3.py::test_outside_window_mutation_fails[timestamp] PASSED [ 20%]
../quality/work/probes/test_seeded_c3.py::test_outside_window_mutation_fails[delete] PASSED [ 30%]
../quality/work/probes/test_seeded_c3.py::test_outside_window_mutation_fails[insert] PASSED [ 40%]
../quality/work/probes/test_seeded_c3.py::test_outside_window_mutation_fails[duplicate] PASSED [ 50%]
../quality/work/probes/test_seeded_c3.py::test_outside_window_mutation_fails[other_stock] PASSED [ 60%]
../quality/work/probes/test_seeded_c3.py::test_baseline_pass PASSED      [ 70%]
../quality/work/probes/test_earlier_fixture_adapter.py::test_new_outside_window_mutations_fail[earlier_than_window] PASSED [ 80%]
../quality/work/probes/test_earlier_fixture_adapter.py::test_new_outside_window_mutations_fail[null_column] PASSED [ 90%]
../quality/work/probes/test_earlier_fixture_adapter.py::test_baseline_with_earlier_row_pass PASSED [100%]

- generated xml file: /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-06/quality/work/probe-results-supplied.xml -
============================= 10 passed in 13.56s ==============================

```


## execute/commands/005-bash/request.json
```text
{"toolCallId":"call_e25c6fd1b4da4b2699efbaa1","params":{"command":"OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /Users/a77/finance-workspace-private/.venv-workbench/bin/python -B -m pytest /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-06/quality/work/probes/test_seeded_c3.py /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-06/quality/work/probes/test_earlier_fixture_adapter.py --rootdir=/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-06/quality/work --junitxml=/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-06/quality/work/probe-results-supplied.xml -p no:cacheprovider --basetemp=/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-06/quality/work/tmp/supplied -v","timeout":300}}
```


## execute/commands/005-bash/result.json
```text
{"exitCode":0}
```


## work/probes/check_seed_syntax.py
```text
import ast
from pathlib import Path
for path in sorted(Path(__file__).parent.glob("*.py")):
    if path.name != "check_seed_syntax.py":
        ast.parse(path.read_text())
print("seed syntax ok")

```


## work/probes/probe_c3_acceptance_v2.py
```text
"""Reviewer QC probe C3 v2 (PR #813): acceptance oracle for outside-window rows.

Challenges candidate/scripts/verify_302132_backfill_acceptance.py (main ->
_data_checks). Fixture helper reused from author tests; ALL assertions are the
reviewer's own. Synthetic DuckDB inside quality/work only. No production run.

v2 fix: sys.path setup before importing the author test module (v1 import of
market_feature_store would fail without candidate root on sys.path); removed the
intentional-control test (positive control is the separate standalone script).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

CAND = Path("/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-06/candidate")
TESTS = CAND / "tests" / "test_repair_backfill_stock_history.py"
ACCEPT = CAND / "scripts" / "verify_302132_backfill_acceptance.py"

import importlib.util

sys.path.insert(0, str(CAND))
spec = importlib.util.spec_from_file_location("t302132", TESTS)
t = importlib.util.module_from_spec(spec)
sys.modules["t302132"] = t
spec.loader.exec_module(t)

OTHER = "000001.SZ"
LATER = "2026-09-22"
LATER2 = "2026-09-23"


def _subprocess_env() -> dict[str, str]:
    return {
        "HOME": os.environ.get("HOME", str(Path.home())),
        "PATH": os.environ.get("PATH", os.defpath),
        "LANG": "C.UTF-8",
        "TMPDIR": os.environ.get("TMPDIR", "/tmp"),
        "FWP_TEST_RECEIPT": "0",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONPATH": str(CAND),
    }


def _run(clone: Path, art: dict, out: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(ACCEPT), "--production", str(art["baseline"]),
         "--clone", str(clone), "--parquet", str(art["pq"]),
         "--run-apply", t.APPLY_RUN, "--run-verify", t.VERIFY_RUN,
         "--expected-revision", t.E2E_REV,
         "--expected-production-sha256", art["base_sha"],
         "--output", str(out)],
        capture_output=True, text=True, timeout=110, env=_subprocess_env())


def _base(tmp_path: Path) -> dict:
    """Author fixture + a later (outside-window) row in BOTH baseline & clone,
    receipts' backup sha rebound to the modified baseline."""
    import duckdb
    art = t._build_e2e_artifacts(tmp_path)
    for p in (art["baseline"], art["clone"]):
        with duckdb.connect(str(p)) as con:
            con.execute(
                "INSERT INTO fact_stock_daily SELECT * REPLACE "
                "(DATE '" + LATER + "' AS trade_date) FROM fact_stock_daily "
                "WHERE stock_ts_code=? AND trade_date=?",
                [art["spec"].code, art["spec"].window_end])
    art["base_sha"] = t.mod._sha256(art["baseline"])
    for rid in (t.APPLY_RUN, t.VERIFY_RUN):
        p = Path(str(art["clone"]) + f".repair-backfill-execution.{rid}.json")
        rec = json.loads(p.read_text())
        rec["backup"]["backup_sha256"] = art["base_sha"]
        p.write_text(json.dumps(rec))
    return art


def _mutated_clone(tmp_path: Path, art: dict, mutation: str) -> Path:
    import duckdb
    clone = tmp_path / "clone_mut.duckdb"
    shutil.copy(str(art["clone"]), str(clone))
    with duckdb.connect(str(clone)) as con:
        if mutation == "none":
            pass
        elif mutation == "amount":
            con.execute("UPDATE fact_stock_daily SET amount=amount+1 "
                        "WHERE stock_ts_code=? AND trade_date=DATE '" + LATER + "'",
                        [art["spec"].code])
        elif mutation == "timestamp":
            con.execute("UPDATE fact_stock_daily SET updated_at="
                        "TIMESTAMP '2026-09-23 12:00:00' WHERE stock_ts_code=? "
                        "AND trade_date=DATE '" + LATER + "'", [art["spec"].code])
        elif mutation == "delete":
            con.execute("DELETE FROM fact_stock_daily WHERE stock_ts_code=? "
                        "AND trade_date=DATE '" + LATER + "'", [art["spec"].code])
        elif mutation == "insert":
            con.execute("INSERT INTO fact_stock_daily SELECT * REPLACE "
                        "(DATE '" + LATER2 + "' AS trade_date) FROM "
                        "fact_stock_daily WHERE stock_ts_code=? AND "
                        "trade_date=DATE '" + LATER + "'", [art["spec"].code])
        elif mutation == "duplicate":
            # DISCLOSURE: clone-only CTAS rebuild removes the PK constraint so
            # an exact duplicate row can exist; adversarial multiset-oracle
            # probe only — real PK would itself block duplicates.
            con.execute("BEGIN")
            con.execute("CREATE TABLE fsd_nopk AS SELECT * FROM fact_stock_daily")
            con.execute("DROP TABLE fact_stock_daily")
            con.execute("ALTER TABLE fsd_nopk RENAME TO fact_stock_daily")
            con.execute("INSERT INTO fact_stock_daily SELECT * FROM "
                        "fact_stock_daily WHERE stock_ts_code=? AND "
                        "trade_date=DATE '" + LATER + "'", [art["spec"].code])
            con.execute("COMMIT")
        elif mutation == "other_stock":
            con.execute("UPDATE fact_stock_daily SET amount=amount+1 "
                        "WHERE stock_ts_code=? AND trade_date=DATE '" + LATER + "'",
                        [OTHER])
        else:
            raise ValueError(mutation)
    return clone


def _fail_check(res, out: Path, must_fail: str) -> dict:
    __tracebackhide__ = True
    assert res.returncode == 2, (res.returncode, res.stdout, res.stderr)
    assert out.exists()
    v = json.loads(out.read_text())
    assert v["verdict"] == "FAIL", v
    assert must_fail in v["failed"], (must_fail, v["failed"])
    return v


MUTS = ["amount", "timestamp", "delete", "insert", "duplicate", "other_stock"]
EXPECT_CHECK = {"other_stock": "fact_other_stocks_allcols",
                "insert": "target_outside_window_allcols"}


@pytest.mark.parametrize("mutation", MUTS)
def test_outside_window_mutation_fails(tmp_path, mutation):
    art = _base(tmp_path)
    clone = _mutated_clone(tmp_path, art, mutation)
    out = tmp_path / "out.json"
    res = _run(clone, art, out)
    _fail_check(res, out, EXPECT_CHECK.get(
        mutation, "target_outside_window_allcols"))


def test_baseline_pass(tmp_path):
    art = _base(tmp_path)
    clone = _mutated_clone(tmp_path, art, "none")
    out = tmp_path / "out.json"
    res = _run(clone, art, out)
    assert res.returncode == 0, (res.stdout, res.stderr)
    v = json.loads(out.read_text())
    assert v["verdict"] == "PASS" and v["failed"] == [], v

```


## work/probes/test_earlier_fixture_adapter.py
```text
"""Host-only fixture repair, retaining the reviewer's two mutation assertions."""
from datetime import date, timedelta
import importlib.util
import json
from pathlib import Path
import sys

import duckdb

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / 'quality/work/probes/test_new_c3_v1.py'
loader = importlib.util.spec_from_file_location('reviewer_earlier_original', SOURCE)
review = importlib.util.module_from_spec(loader)
sys.modules[loader.name] = review
loader.loader.exec_module(review)
original_base = review._base


def corrected_base(tmp_path):
    art = original_base(tmp_path)
    earlier = date.fromisoformat(art['spec'].window_start) - timedelta(days=1)
    for path in (art['baseline'], art['clone']):
        with duckdb.connect(str(path)) as con:
            rows = con.execute(
                'INSERT INTO fact_stock_daily SELECT * REPLACE (? AS trade_date) '
                'FROM fact_stock_daily WHERE stock_ts_code=? AND trade_date=? RETURNING trade_date',
                [earlier, art['spec'].code, art['spec'].window_end],
            ).fetchall()
            assert rows == [(earlier,)]
    art['base_sha'] = review.t.mod._sha256(art['baseline'])
    for run in (review.t.APPLY_RUN, review.t.VERIFY_RUN):
        path = Path(str(art['clone']) + f'.repair-backfill-execution.{run}.json')
        receipt = json.loads(path.read_text())
        receipt['backup']['backup_sha256'] = art['base_sha']
        path.write_text(json.dumps(receipt))
    return art


review._base = corrected_base
test_new_outside_window_mutations_fail = review.test_new_outside_window_mutations_fail


def test_baseline_with_earlier_row_pass(tmp_path):
    art = corrected_base(tmp_path)
    clone = review._clone_with_receipts(tmp_path, art)
    out = tmp_path / 'out.json'
    result = review._run(clone, art, out)
    assert result.returncode == 0, (result.stdout, result.stderr)
    verdict = json.loads(out.read_text())
    assert verdict['verdict'] == 'PASS' and not verdict['failed']

```


## work/probes/test_new_c3_v1.py
```text
"""New QC-authored C3 tests (independent of supplied suite assertions).

Provenance: fixture/_base/copy logic ADAPTED from supplied probe_c3_acceptance_v2.py
(whose setup derives from author _build_e2e_artifacts); assertions below are newly
authored this session. Targets candidate scripts/verify_302132_backfill_acceptance.py
main -> _data_checks "target_outside_window_allcols".

New cases (not covered by the supplied suite's amount/timestamp/delete/insert/
duplicate/other_stock on the later date):
  1. earlier_than_window: mutate an inside-code row strictly BEFORE window_start
     (trade_date < 2026-06-15), assert acceptance FAILs target_outside_window_allcols.
  2. null_column: set a NULL-able column (stock_name) to NULL on the outside-window
     later row; NULL-vs-nonNULL must be caught by EXCEPT ALL multiset semantics.
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import duckdb
import pytest

CAND = Path("/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-06/candidate")
TESTS = CAND / "tests" / "test_repair_backfill_stock_history.py"
ACCEPT = CAND / "scripts" / "verify_302132_backfill_acceptance.py"

sys.path.insert(0, str(CAND))
spec = importlib.util.spec_from_file_location("t302132_new", TESTS)
t = importlib.util.module_from_spec(spec)
sys.modules["t302132_new"] = t
spec.loader.exec_module(t)

OTHER = "000001.SZ"
LATER = "2026-09-22"


def _env() -> dict[str, str]:
    return {
        "HOME": os.environ.get("HOME", str(Path.home())),
        "PATH": os.environ.get("PATH", os.defpath),
        "LANG": "C.UTF-8",
        "TMPDIR": os.environ.get("TMPDIR", "/tmp"),
        "FWP_TEST_RECEIPT": "0",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONPATH": str(CAND),
    }


def _base(tmp_path: Path) -> dict:
    art = t._build_e2e_artifacts(tmp_path)
    for p in (art["baseline"], art["clone"]):
        with duckdb.connect(str(p)) as con:
            con.execute(
                "INSERT INTO fact_stock_daily SELECT * REPLACE "
                "(DATE '" + LATER + "' AS trade_date) FROM fact_stock_daily "
                "WHERE stock_ts_code=? AND trade_date=?",
                [art["spec"].code, art["spec"].window_end])
    art["base_sha"] = t.mod._sha256(art["baseline"])
    for rid in (t.APPLY_RUN, t.VERIFY_RUN):
        p = Path(str(art["clone"]) + f".repair-backfill-execution.{rid}.json")
        rec = json.loads(p.read_text())
        rec["backup"]["backup_sha256"] = art["base_sha"]
        p.write_text(json.dumps(rec))
    # receipts resolved relative to clone path (host correction, same as supplied)
    clone = Path(art["clone"])
    return art


def _clone_with_receipts(tmp_path: Path, art: dict) -> Path:
    clone = tmp_path / "clone_new.duckdb"
    shutil.copy(str(art["clone"]), str(clone))
    for rid in (t.APPLY_RUN, t.VERIFY_RUN):
        src = Path(str(art["clone"]) + f".repair-backfill-execution.{rid}.json")
        dst = Path(str(clone) + f".repair-backfill-execution.{rid}.json")
        shutil.copyfile(src, dst)
    return clone


def _run(clone: Path, art: dict, out: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(ACCEPT), "--production", str(art["baseline"]),
         "--clone", str(clone), "--parquet", str(art["pq"]),
         "--run-apply", t.APPLY_RUN, "--run-verify", t.VERIFY_RUN,
         "--expected-revision", t.E2E_REV,
         "--expected-production-sha256", art["base_sha"],
         "--output", str(out)],
        capture_output=True, text=True, timeout=110, env=_env())


@pytest.mark.parametrize("mutation", ["earlier_than_window", "null_column"])
def test_new_outside_window_mutations_fail(tmp_path, mutation):
    art = _base(tmp_path)
    clone = _clone_with_receipts(tmp_path, art)
    with duckdb.connect(str(clone)) as con:
        if mutation == "earlier_than_window":
            code = art["spec"].code
            d0 = art["spec"].window_start
            rows = con.execute(
                "SELECT trade_date FROM fact_stock_daily WHERE stock_ts_code=? "
                "AND trade_date < ? ORDER BY trade_date DESC LIMIT 1",
                [code, d0]).fetchall()
            assert rows, "fixture lacks a pre-window row for target code"
            earlier = rows[0][0]
            changed = con.execute(
                "UPDATE fact_stock_daily SET amount=amount+1 WHERE "
                "stock_ts_code=? AND trade_date=? RETURNING amount",
                [code, earlier]).fetchall()
            assert len(changed) == 1, (changed, earlier)
        elif mutation == "null_column":
            changed = con.execute(
                "UPDATE fact_stock_daily SET stock_name=NULL WHERE "
                "stock_ts_code=? AND trade_date=DATE '" + LATER + "' "
                "RETURNING 1", [art["spec"].code]).fetchall()
            assert len(changed) == 1, changed
    out = tmp_path / "out.json"
    res = _run(clone, art, out)
    assert res.returncode == 2, (res.returncode, res.stdout, res.stderr)
    assert out.exists()
    v = json.loads(out.read_text())
    assert v["verdict"] == "FAIL", v
    assert "target_outside_window_allcols" in v["failed"], v["failed"]

```


## work/probes/test_seeded_c3.py
```text
"""HOST fixture correction; assertions originate in reviewer source, NOT a QC verdict."""
import importlib.util
from pathlib import Path
import shutil
import sys

import duckdb

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / 'quality/work/probes/probe_c3_acceptance_v2.py'
spec = importlib.util.spec_from_file_location('reviewer_original_for_host_diagnosis', SOURCE)
review = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = review
spec.loader.exec_module(review)
original_mutation = review._mutated_clone


def corrected_fixture(tmp_path, art, mutation):
    clone = original_mutation(tmp_path, art, mutation)
    # The CLI resolves receipts relative to the requested clone, not the fixture's old filename.
    for run in (review.t.APPLY_RUN, review.t.VERIFY_RUN):
        source = Path(str(art['clone']) + f'.repair-backfill-execution.{run}.json')
        destination = Path(str(clone) + f'.repair-backfill-execution.{run}.json')
        assert source.is_file() and not destination.exists()
        shutil.copyfile(source, destination)
    if mutation == 'other_stock':
        # The original fixture has OTHER only on CAL dates, never on LATER.
        with duckdb.connect(str(clone)) as con:
            changed = con.execute(
                'UPDATE fact_stock_daily SET amount=amount+1 WHERE stock_ts_code=? AND trade_date=? RETURNING amount',
                [review.OTHER, review.t.CAL[0]],
            ).fetchall()
            assert len(changed) == 1
    return clone


review._mutated_clone = corrected_fixture
test_outside_window_mutation_fails = review.test_outside_window_mutation_fails
test_baseline_pass = review.test_baseline_pass

```


## work/probe-results-supplied.xml
```text
<?xml version="1.0" encoding="utf-8"?><testsuites><testsuite name="pytest" errors="0" failures="0" skipped="0" tests="10" time="13.563" timestamp="2026-09-25T09:11:54.284406+08:00" hostname="77deMacBook-Air.local"><testcase classname="probes.test_seeded_c3" name="test_outside_window_mutation_fails[amount]" time="1.822" /><testcase classname="probes.test_seeded_c3" name="test_outside_window_mutation_fails[timestamp]" time="1.389" /><testcase classname="probes.test_seeded_c3" name="test_outside_window_mutation_fails[delete]" time="1.221" /><testcase classname="probes.test_seeded_c3" name="test_outside_window_mutation_fails[insert]" time="1.341" /><testcase classname="probes.test_seeded_c3" name="test_outside_window_mutation_fails[duplicate]" time="1.326" /><testcase classname="probes.test_seeded_c3" name="test_outside_window_mutation_fails[other_stock]" time="1.318" /><testcase classname="probes.test_seeded_c3" name="test_baseline_pass" time="1.070" /><testcase classname="probes.test_earlier_fixture_adapter" name="test_new_outside_window_mutations_fail[earlier_than_window]" time="1.193" /><testcase classname="probes.test_earlier_fixture_adapter" name="test_new_outside_window_mutations_fail[null_column]" time="1.233" /><testcase classname="probes.test_earlier_fixture_adapter" name="test_baseline_with_earlier_row_pass" time="1.518" /></testsuite></testsuites>
```
