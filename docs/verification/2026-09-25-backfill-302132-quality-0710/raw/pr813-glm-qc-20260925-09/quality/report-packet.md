# Immutable evidence packet
No reasoning transcript or other-axis results included.
Raw command output is authoritative. Prior-stage prose may contain errors: never promote a proposed correction or unsupported PASS label to an observed result. Missing evidence must remain explicit.


## explore/parsed.json
```text
{
  "claims_examined": [
    {
      "claim": "C3: _data_checks enforces clone-vs-baseline bidirectional zero-diff for other stocks (fact_stock_daily), target outside-window rows, retained in-window rows (full columns incl updated_at), and the two hithink source tables read entirely from the immutable production baseline (prod. schema), so oracle inputs are independent of the clone result",
      "state": "verified",
      "evidence": "candidate/scripts/verify_302132_backfill_acceptance.py::_data_checks lines ~502-540: xa() builds fwd/rev EXCEPT ALL counts against prod.{table}; checks fact_other_stocks_allcols, retained_rows_full_column_identical (SELECT * equality plus expected_total_rows - |write_keys| count), target_outside_window_allcols, hithink_source_untouched, hithink_adjustment_untouched; oracle reads use prod.fact_stock_daily_hithink and prod.fact_market_daily"
    },
    {
      "claim": "C3: authorized keyset full-field oracle recomputes values from baseline hithink source plus frozen parquet and validates window/technical protected slices, golden triples, pinned values, and market_daily immutability; any data-check exception is captured as a structured FAIL (rc=2) and data checks are skipped when preflight/args/receipt schema fail (fail-closed)",
      "state": "verified",
      "evidence": "keyset_fullfield_oracle compares fact_stock_daily rows for write_keys (gap_parallel|gap_parquet|shell_date) against src built from prod. + read_parquet('{pq}'); technical_protected_allcols/window_protected_allcols use xa(); window_golden_triples, expected_window_counts_match_golden, technical_exact_set (cal64[25:]), pinned_technical_target_day, pinned_windows_target_day, market_daily_untouched; main() wraps _data_checks in try/except -> check('data_checks_error', False, ...) and emits data_checks_executed=False when spec_ok is False; rc 0 only on PASS"
    },
    {
      "claim": "inputs/claims.md and inputs/source-map.md exist under quality/work/inputs/ as stated stage inputs",
      "state": "not_verified",
      "evidence": "reads of /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-09/quality/work/inputs/claims.md and source-map.md both raised FileNotFoundError; bash listing prohibited in this stage so no alternative location could be confirmed"
    }
  ],
  "limits": [
    "inputs/claims.md and inputs/source-map.md were not found at the given paths; claims examined were reconstructed from the task brief and the candidate source itself",
    "No bash, no test execution, no file writes, no new assertions in this stage (per contract); one incidental partial read of probes/test_seeded_c3.py header (50 lines) occurred while locating missing inputs - it was not used to form any explore claim and its contents remain execute-stage evidence",
    "Production-shaped 64/39/161 counts and duplicate-case clone-only PK removal disclosures remain a separate limitation unless directly observed in execute",
    "No production, network, or vendor access; synthetic DuckDB only in execute stage"
  ],
  "next_stage_commands": [
    {
      "command": "OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /Users/a77/finance-workspace-private/.venv-workbench/bin/python -B /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-09/quality/work/positive_control.py",
      "purpose": "mandatory first bash call in execute; must exit 1 with intentional probe_bug text"
    },
    {
      "command": "/Users/a77/finance-workspace-private/.venv-workbench/bin/python -B /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-09/quality/work/probes/test_seeded_c3.py",
      "purpose": "seven prior C3 assertions with receipt-path/OTHER-date fixture repair, using actual external acceptance entry"
    },
    {
      "command": "/Users/a77/finance-workspace-private/.venv-workbench/bin/python -B /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-09/quality/work/probes/test_earlier_fixture_adapter.py",
      "purpose": "three prior new assertions with host-only pre-window-row fixture repair added to both baseline and clone"
    }
  ],
  "no_tests_ran": true,
  "probe_files": [
    "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-09/quality/work/probes/test_seeded_c3.py",
    "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-09/quality/work/probes/test_earlier_fixture_adapter.py"
  ],
  "probe_provenance": "Both suites are supplied prior-reviewer assertions plus host fixture repairs (receipt-path rebind and a real pre-window row added to both baseline and clone with receipt hashes rebound), not prior verdicts; they invoke the actual external acceptance entry scripts/verify_302132_backfill_acceptance.py, not only a helper. They must be executed fresh in the execute stage with provenance recorded. Neither probe file was intentionally read in this explore stage.",
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
    "author_tests_run": 0,
    "failed": 0,
    "passed": 0,
    "suite": "none — author tests not run per contract"
  },
  "claims": [
    {
      "claim": "C3: candidate acceptance oracle scripts/verify_302132_backfill_acceptance.py::_data_checks correctly FAILs outside-window clone mutations and PASSes an unmutated baseline with outside-window rows (as asserted by the supplied probe suites)",
      "state": "not_verified"
    }
  ],
  "findings": [
    {
      "detail": "Both supplied suites hardcode CAND=/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-06/candidate (a prior review's directory). This session's sandbox denies reads outside the -09 review root (verified: ls of the -06 candidate returns 'Operation not permitted'), so module import of the author test fixture helper raises PermissionError at collection. 0 of 10 supplied test items executed.",
      "severity": "info",
      "title": "Supplied probes unexecutable: stale candidate path outside sandbox"
    }
  ],
  "limits": [
    "Supplied probe suites (test_seeded_c3.py: 7 cases; test_earlier_fixture_adapter.py: 3 cases) could not be executed; C3 remains unverified this session.",
    "Reviewer probe counts contain collection errors; PASS/PASS_WITH_LIMITS delivery is blocked by contract.",
    "The production-shaped 64/39/161 counts remain a separate unobserved limitation.",
    "No author tests, production access, or candidate reads in this session; candidate code itself was not inspected during execute."
  ],
  "positive_control": {
    "evidence": "execute/001-bash/request.json, result.json, output.log show the exact command, exit code 1, and 'intentional probe_bug control'",
    "observed": true
  },
  "probe_provenance": "Supplied files test_seeded_c3.py (7 cases: prior C3 assertions amount/timestamp/delete/insert/duplicate/other_stock/baseline-pass, with host receipt-path and OTHER-date fixture repairs) and test_earlier_fixture_adapter.py (3 cases: prior earlier-than-window/null-column assertions plus a host-only pre-window-row fixture repair rebinding receipt hashes to both baseline and clone). Per instructions these are prior reviewer assertions plus host fixture repairs, executed fresh this session; both use the external acceptance entry point scripts/verify_302132_backfill_acceptance.py, not only a helper. Syntax-checked via py_compile (clean). Not modified.",
  "reviewer_probe_counts": {
    "errors": 2,
    "failed": 0,
    "passed": 0,
    "source": "probe-results-supplied.xml plus raw pytest output (exit 2, 2 collection errors, 0 tests run)"
  },
  "supplied_probe_counts": {
    "collected_and_run": 0,
    "collection_errors": 2,
    "expected_cases": 10
  },
  "supplied_probe_results": {
    "basetemp": ".../quality/work/tmp/supplied",
    "exit_code": 2,
    "junitxml": ".../quality/work/probe-results-supplied.xml",
    "outcome": "2 collection errors, 0 tests run",
    "reason": "PermissionError reading /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-06/candidate/tests/test_repair_backfill_stock_history.py — hardcoded stale candidate path outside this session's sandbox",
    "syntax_check": "py_compile clean on both supplied test files"
  },
  "supplied_xml": "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-09/quality/work/probe-results-supplied.xml",
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
# EXECUTE log — PR #813 C3 bounded QC (revision 3c5b3c9a6f0c1fe9401c424bc5ac396cf46fbc59)

## Positive control (first bash)
Command (exact):
`OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /Users/a77/finance-workspace-private/.venv-workbench/bin/python -B /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-09/quality/work/positive_control.py`
Result: exit code 1, traceback ending `AssertionError: intentional probe_bug control`. Raw files: execute/001-bash/*.

## Syntax check
`python -B -m py_compile` on both supplied test files: clean, no output.

## Supplied pytest run (direct, single command, exact required args)
- pytest 8.3.5, rootdir=.../quality/work, both supplied test paths, --junitxml=.../probe-results-supplied.xml, --basetemp=.../tmp/supplied
- Outcome: **collected 0 items / 2 collection ERRORS**, exit code 2, session interrupted.
- Both errors are `PermissionError: [Errno 1] Operation not permitted: '/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-06/candidate/tests/test_repair_backfill_stock_history.py'`.
- Cause: both supplied suites (probe_c3_acceptance_v2.py via test_seeded_c3.py, and test_new_c3_v1.py via test_earlier_fixture_adapter.py) hardcode `CAND = .../pr813-glm-qc-20260925-06/candidate`, a prior review's directory. This session's sandbox permits reads only under the `-09` review root (confirmed separately: `ls .../pr813-glm-qc-20260925-06/candidate/scripts` → "Operation not permitted").
- Per contract, supplied files were not modified; no helper files or wrapper scripts were created; no author tests run.

## Counts observed from this run
- Supplied suites: 0 passed, 0 failed, 2 collection errors (10 test items never executed: 7 seeded + 3 adapter).
- Author tests: 0 run by reviewer.

```


## execute/commands/001-bash/output.log
```text
Traceback (most recent call last):
  File "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-09/quality/work/positive_control.py", line 1, in <module>
    assert 1 == 2, "intentional probe_bug control"
           ^^^^^^
AssertionError: intentional probe_bug control

```


## execute/commands/001-bash/request.json
```text
{"toolCallId":"call_9e29ccdf48724be2bf5c137c","params":{"command":"OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /Users/a77/finance-workspace-private/.venv-workbench/bin/python -B /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-09/quality/work/positive_control.py"}}
```


## execute/commands/001-bash/result.json
```text
{"exitCode":1}
```


## execute/commands/002-bash/output.log
```text

```


## execute/commands/002-bash/request.json
```text
{"toolCallId":"call_526818161e2947ecabcb43da","params":{"command":"/Users/a77/finance-workspace-private/.venv-workbench/bin/python -B -m py_compile /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-09/quality/work/probes/test_seeded_c3.py /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-09/quality/work/probes/test_earlier_fixture_adapter.py"}}
```


## execute/commands/002-bash/result.json
```text
{"exitCode":0}
```


## execute/commands/003-bash/output.log
```text
============================= test session starts ==============================
platform darwin -- Python 3.12.13, pytest-8.3.5, pluggy-1.6.0 -- /Users/a77/finance-workspace-private/.venv-workbench/bin/python
cachedir: .pytest_cache
rootdir: /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-09/quality/work
plugins: anyio-4.14.1
collecting ... collected 0 items / 2 errors

==================================== ERRORS ====================================
__________________ ERROR collecting probes/test_seeded_c3.py ___________________
../quality/work/probes/test_seeded_c3.py:14: in <module>
    spec.loader.exec_module(review)
<frozen importlib._bootstrap_external>:999: in exec_module
    ???
<frozen importlib._bootstrap>:488: in _call_with_frames_removed
    ???
../quality/work/probes/probe_c3_acceptance_v2.py:32: in <module>
    spec.loader.exec_module(t)
<frozen importlib._bootstrap_external>:995: in exec_module
    ???
<frozen importlib._bootstrap_external>:1132: in get_code
    ???
<frozen importlib._bootstrap_external>:1190: in get_data
    ???
E   PermissionError: [Errno 1] Operation not permitted: '/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-06/candidate/tests/test_repair_backfill_stock_history.py'
___________ ERROR collecting probes/test_earlier_fixture_adapter.py ____________
../quality/work/probes/test_earlier_fixture_adapter.py:15: in <module>
    loader.loader.exec_module(review)
<frozen importlib._bootstrap_external>:999: in exec_module
    ???
<frozen importlib._bootstrap>:488: in _call_with_frames_removed
    ???
../quality/work/probes/test_new_c3_v1.py:36: in <module>
    spec.loader.exec_module(t)
<frozen importlib._bootstrap_external>:995: in exec_module
    ???
<frozen importlib._bootstrap_external>:1132: in get_code
    ???
<frozen importlib._bootstrap_external>:1190: in get_data
    ???
E   PermissionError: [Errno 1] Operation not permitted: '/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-06/candidate/tests/test_repair_backfill_stock_history.py'
- generated xml file: /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-09/quality/work/probe-results-supplied.xml -
=========================== short test summary info ============================
ERROR ../quality/work/probes/test_seeded_c3.py - PermissionError: [Errno 1] O...
ERROR ../quality/work/probes/test_earlier_fixture_adapter.py - PermissionErro...
!!!!!!!!!!!!!!!!!!! Interrupted: 2 errors during collection !!!!!!!!!!!!!!!!!!!!
============================== 2 errors in 0.32s ===============================

```


## execute/commands/003-bash/request.json
```text
{"toolCallId":"call_55ae02f356364b6d980f3879","params":{"command":"OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /Users/a77/finance-workspace-private/.venv-workbench/bin/python -B -m pytest /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-09/quality/work/probes/test_seeded_c3.py /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-09/quality/work/probes/test_earlier_fixture_adapter.py --rootdir=/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-09/quality/work --junitxml=/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-09/quality/work/probe-results-supplied.xml --basetemp=/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-09/quality/work/tmp/supplied -v","timeout":580}}
```


## execute/commands/003-bash/result.json
```text
{"exitCode":2}
```


## execute/commands/008-bash/output.log
```text
total 56
drwxr-xr-x@  8 a77  staff   256 Sep 25 09:54 .
drwxr-xr-x@ 14 a77  staff   448 Sep 25 09:54 ..
drwxr-xr-x@  4 a77  staff   128 Sep 25 09:54 __pycache__
-rw-r--r--@  1 a77  staff   196 Sep 25 09:51 check_seed_syntax.py
-rw-r--r--@  1 a77  staff  6570 Sep 25 09:51 probe_c3_acceptance_v2.py
-rw-r--r--@  1 a77  staff  2004 Sep 25 09:51 test_earlier_fixture_adapter.py
-rw-r--r--@  1 a77  staff  5245 Sep 25 09:51 test_new_c3_v1.py
-rw-r--r--@  1 a77  staff  1674 Sep 25 09:51 test_seeded_c3.py

```


## execute/commands/008-bash/request.json
```text
{"toolCallId":"call_14d966273ece47aaa6b0d209","params":{"command":"ls -la /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-09/quality/work/probes"}}
```


## execute/commands/008-bash/result.json
```text
{"exitCode":0}
```


## execute/commands/010-bash/output.log
```text
ls: /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-06/candidate/scripts: Operation not permitted

```


## execute/commands/010-bash/request.json
```text
{"toolCallId":"call_4039187f58214ba195c7cb60","params":{"command":"ls /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-06/candidate/scripts"}}
```


## execute/commands/010-bash/result.json
```text
{"exitCode":1}
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
<?xml version="1.0" encoding="utf-8"?><testsuites><testsuite name="pytest" errors="2" failures="0" skipped="0" tests="2" time="0.318" timestamp="2026-09-25T09:54:28.289020+08:00" hostname="77deMacBook-Air.local"><testcase classname="" name="probes.test_seeded_c3" time="0.000"><error message="collection failure">../quality/work/probes/test_seeded_c3.py:14: in &lt;module&gt;
    spec.loader.exec_module(review)
&lt;frozen importlib._bootstrap_external&gt;:999: in exec_module
    ???
&lt;frozen importlib._bootstrap&gt;:488: in _call_with_frames_removed
    ???
../quality/work/probes/probe_c3_acceptance_v2.py:32: in &lt;module&gt;
    spec.loader.exec_module(t)
&lt;frozen importlib._bootstrap_external&gt;:995: in exec_module
    ???
&lt;frozen importlib._bootstrap_external&gt;:1132: in get_code
    ???
&lt;frozen importlib._bootstrap_external&gt;:1190: in get_data
    ???
E   PermissionError: [Errno 1] Operation not permitted: '/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-06/candidate/tests/test_repair_backfill_stock_history.py'</error></testcase><testcase classname="" name="probes.test_earlier_fixture_adapter" time="0.000"><error message="collection failure">../quality/work/probes/test_earlier_fixture_adapter.py:15: in &lt;module&gt;
    loader.loader.exec_module(review)
&lt;frozen importlib._bootstrap_external&gt;:999: in exec_module
    ???
&lt;frozen importlib._bootstrap&gt;:488: in _call_with_frames_removed
    ???
../quality/work/probes/test_new_c3_v1.py:36: in &lt;module&gt;
    spec.loader.exec_module(t)
&lt;frozen importlib._bootstrap_external&gt;:995: in exec_module
    ???
&lt;frozen importlib._bootstrap_external&gt;:1132: in get_code
    ???
&lt;frozen importlib._bootstrap_external&gt;:1190: in get_data
    ???
E   PermissionError: [Errno 1] Operation not permitted: '/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-06/candidate/tests/test_repair_backfill_stock_history.py'</error></testcase></testsuite></testsuites>
```
