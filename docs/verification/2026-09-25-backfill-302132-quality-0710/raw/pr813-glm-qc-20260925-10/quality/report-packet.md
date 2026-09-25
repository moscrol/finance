# Immutable evidence packet
No reasoning transcript or other-axis results included.
Raw command output is authoritative. Prior-stage prose may contain errors: never promote a proposed correction or unsupported PASS label to an observed result. Missing evidence must remain explicit.


## explore/parsed.json
```text
{
  "claims_examined": [
    "C3: Acceptance oracle evaluates retained rows (row count = expected_total_rows - authorized keyset count) inside the authorized window with full-column equality via SELECT * ORDER BY trade_date comparison; target rows outside the window and other stocks retain ALL columns via bidirectional EXCEPT ALL (xa fwd/rev) multiset semantics on the full column list derived from PRAGMA table_info — lines 540-728 of scripts/verify_302132_backfill_acceptance.py",
    "C3: Mutation detection beyond row counts — amount is checked in the keyset full-field oracle (abs(r[8]-amt)<1e-9 with Decimal re-derivation from frozen parquet/baseline source), deletion/insertion asymmetry is caught by bidirectional EXCEPT ALL multiset diffs, timestamps by protected-slice all-column comparisons including calculated_at and updated_at (retained rows via SELECT *); keyset_fullfield_oracle additionally requires len(rows)==len(write_keys)",
    "C3 window-after-apply counts (64 rows; close/pct_chg/amount each 64 nonnull; technical 39; window 161): the script checks window_golden_triples, technical_exact_set (cal64[25:] = technical 39 if calendar in-window has 64 dates), expected_window_counts/expected_technical_count binding, and pinned 09-11 values; the 64/39/161 production-shaped counts are NOT hardcoded in the script — they derive from spec and the baseline market calendar, so their direct observation is deferred to the supplied probes/artifacts and remains a stated limitation",
    "C1, C2, C4, C5, C6, C7: out_of_scope for this C3-only axis"
  ],
  "limits": [
    "No bash execution, no file writes, no new assertions, and no test runs occurred in this explore stage",
    "The supplied probe files were intentionally NOT read in this stage; their paths and provenance are fixed inputs carried forward to execute",
    "The production-shaped 64/39/161 counts were not directly observed here; they remain a separate limitation unless observed during execute",
    "Positive control gate requires the exact first execute command (OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .../python -B .../positive_control.py) with exit code 1 and probe_bug text; not yet performed",
    "All claims except C3 are out_of_scope per axis isolation"
  ],
  "next_stage_commands": [
    {
      "bash": "OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /Users/a77/finance-workspace-private/.venv-workbench/bin/python -B /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-10/quality/work/positive_control.py",
      "purpose": "mandatory first execute command; must exit 1 with probe_bug text"
    },
    {
      "bash": "/Users/a77/finance-workspace-private/.venv-workbench/bin/python -B -m pytest -q /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-10/quality/work/probes/test_seeded_c3.py /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-10/quality/work/probes/test_earlier_fixture_adapter.py",
      "purpose": "execute the ten supplied probe cases (7 seeded C3 + 3 earlier fixture-adapter) against the external acceptance entry in a fresh synthetic DuckDB work root; do not modify supplied files"
    }
  ],
  "positive_control": "planned and not yet executed; mandatory exact first command for execute stage per controller contract",
  "probe_files": [
    "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-10/quality/work/probes/test_seeded_c3.py",
    "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-10/quality/work/probes/test_earlier_fixture_adapter.py"
  ],
  "probe_provenance": "test_seeded_c3.py: seven prior-reviewer C3 assertions with receipt-path/OTHER-date host fixture repairs. test_earlier_fixture_adapter.py: three prior new assertions with a host-only fixture repair adding a real pre-window row to both baseline and clone and rebinding receipt hashes. Both suites invoke the actual external acceptance entry (candidate scripts/verify_302132_backfill_acceptance.py), not merely a helper; duplicate cases disclose clone-only PK removal. Supplied probes are prior reviewer assertions plus host fixture repairs, not prior verdicts; they must be executed fresh in this session with provenance kept explicit. Supplied files must not be modified.",
  "statement": "Explore only: read claims.md, source-map.md, and the candidate's precise _data_checks implementation; no tests ran in this stage",
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
    "collected": 0,
    "errors": 0,
    "failed": 0,
    "passed": 0,
    "skipped": 0
  },
  "claims": [
    {
      "claim": "Candidate's external acceptance entry (verify_302132_backfill_acceptance.py) rejects all six outside-window mutation classes (amount, timestamp, delete, insert, duplicate with clone-only PK removal, other_stock)",
      "evidence": "test_seeded_c3.py 6/6 mutation cases passed against the actual external entry",
      "state": "verified"
    },
    {
      "claim": "Acceptance passes on unmodified baseline",
      "evidence": "test_baseline_pass passed",
      "state": "verified"
    },
    {
      "claim": "New assertions with host-only pre-window fixture adapter (real pre-window row in baseline and clone, rebound receipt hashes): earlier_than_window and null_column mutations are rejected",
      "evidence": "test_earlier_fixture_adapter.py 2/2 mutation cases passed",
      "state": "verified"
    },
    {
      "claim": "Baseline including the added earlier row still passes acceptance",
      "evidence": "test_baseline_with_earlier_row_pass passed",
      "state": "verified"
    },
    {
      "claim": "Production-shaped 64/39/161 counts match production",
      "evidence": "not directly observed in this bounded review",
      "state": "out_of_scope"
    }
  ],
  "findings": [
    "All 7 prior C3 assertions verified against the actual external acceptance entry, not just the helper.",
    "All 3 supplied new assertions with the host-only pre-window fixture repair verified; earlier-row baseline still passes.",
    "Duplicate case discloses clone-only PK removal; not treated as a hidden baseline property.",
    "No regressions observed in the supplied probe suite: 10 passed / 0 failed / 0 errors."
  ],
  "limits": [
    "Production-shaped 64/39/161 counts remain a separate limitation; not directly observed.",
    "No author tests executed (contract); author_test_counts all zero.",
    "Synthetic DuckDB inside work only; no production, vendor, network, or credential access.",
    "Supplied probes are prior reviewer assertions plus host fixture repairs re-executed fresh; they are evidence, not prior verdicts."
  ],
  "positive_control": {
    "command": "OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /Users/a77/finance-workspace-private/.venv-workbench/bin/python -B /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-10/quality/work/positive_control.py",
    "evidence": "execute/001-bash/request.json, result.json, output.log show exact command, exit code 1, traceback text 'intentional probe_bug control'",
    "observed": true
  },
  "probe_provenance": {
    "fixture_repairs": [
      "test_seeded_c3.py: receipt-path/OTHER-date fixture repair",
      "test_earlier_fixture_adapter.py: host-only adapter adding a real pre-window row to both baseline and clone and rebinding receipt hashes"
    ],
    "supplied_by": "prior reviewer assertions plus host fixture repairs supplied by controller; not prior verdicts",
    "test_entry": "candidate scripts/verify_302132_backfill_acceptance.py actual external acceptance entry (not only helper)"
  },
  "reviewer_probe_counts": {
    "collected": 10,
    "errors": 0,
    "failed": 0,
    "passed": 10,
    "skipped": 0
  },
  "supplied_probe_counts": {
    "test_earlier_fixture_adapter.py": {
      "passed": 3
    },
    "test_seeded_c3.py": {
      "passed": 7
    },
    "total": 10
  },
  "supplied_probe_results": {
    "basetemp": "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-10/quality/work/tmp/supplied",
    "command": "direct pytest with both supplied test paths, --rootdir=work, --junitxml=work/probe-results-supplied.xml, --basetemp=work/tmp/supplied",
    "duration_s": 16.94,
    "failed": 0,
    "passed": 10,
    "syntax_check": "py_compile of both supplied files OK"
  },
  "supplied_xml": "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-10/quality/work/probe-results-supplied.xml",
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
# EXECUTE — C3 quality review (PR #813, rev 3c5b3c9a, baseline 4cc15e70)

## Positive control
First bash call (raw logs in execute/001-bash/): exact command
`OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /Users/a77/finance-workspace-private/.venv-workbench/bin/python -B .../quality/work/positive_control.py`
exit code 1, traceback text `intentional probe_bug control`. Control observed.

## Supplied probes
- Syntax check: py_compile of both supplied test files — OK (no output).
- Direct pytest run (no wrapper, both supplied paths, required rootdir/junitxml/basetemp):
  10 passed, 0 failed, 0 errors in 16.94s.
  - test_seeded_c3.py: 7/7 passed (6 outside-window mutation cases + baseline_pass)
  - test_earlier_fixture_adapter.py: 3/3 passed (earlier_than_window, null_column, baseline_with_earlier_row_pass)
- XML: work/probe-results-supplied.xml (preserved).

## Findings
- All 7 prior C3 assertions verified: the actual external acceptance entry
  (candidate verify_302132_backfill_acceptance.py, not only the helper) rejects amount,
  timestamp, delete, insert, duplicate (clone-only PK removal disclosed), and other_stock
  mutations outside the window, and passes on the unmodified baseline.
- All 3 new assertions with the host-only pre-window fixture adapter verified, including
  a real pre-window row added to both baseline and clone with rebound receipt hashes;
  baseline with the earlier row still passes. Clone-only PK removal disclosed in duplicate case.

## Limits
- No author tests executed (author_test_counts all zero by contract).
- Production-shaped 64/39/161 counts remain a separate limitation; not directly observed here.
- Synthetic DuckDB inside work only; no production/vendor/network access.
- Supplied probes are prior reviewer assertions plus host fixture repairs; provenance is
  prior-reviewer assertions, re-executed fresh in this session — not prior verdicts.

```


## execute/commands/001-bash/output.log
```text
Traceback (most recent call last):
  File "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-10/quality/work/positive_control.py", line 1, in <module>
    assert 1 == 2, "intentional probe_bug control"
           ^^^^^^
AssertionError: intentional probe_bug control

```


## execute/commands/001-bash/request.json
```text
{"toolCallId":"call_cbbd2a737aa34d45b57d81b0","params":{"command":"OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /Users/a77/finance-workspace-private/.venv-workbench/bin/python -B /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-10/quality/work/positive_control.py"}}
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
{"toolCallId":"call_3c736bc6291440db90da7daf","params":{"command":"/Users/a77/finance-workspace-private/.venv-workbench/bin/python -B -m py_compile /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-10/quality/work/probes/test_seeded_c3.py /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-10/quality/work/probes/test_earlier_fixture_adapter.py"}}
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
rootdir: /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-10/quality/work
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

- generated xml file: /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-10/quality/work/probe-results-supplied.xml -
============================= 10 passed in 16.94s ==============================

```


## execute/commands/003-bash/request.json
```text
{"toolCallId":"call_59c60a8b90d94e13a013d906","params":{"command":"OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /Users/a77/finance-workspace-private/.venv-workbench/bin/python -B -m pytest /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-10/quality/work/probes/test_seeded_c3.py /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-10/quality/work/probes/test_earlier_fixture_adapter.py --rootdir=/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-10/quality/work --junitxml=/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-10/quality/work/probe-results-supplied.xml --basetemp=/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-10/quality/work/tmp/supplied -v"}}
```


## execute/commands/003-bash/result.json
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

CAND = Path("/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-10/candidate")
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

CAND = Path("/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-10/candidate")
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
<?xml version="1.0" encoding="utf-8"?><testsuites><testsuite name="pytest" errors="0" failures="0" skipped="0" tests="10" time="16.917" timestamp="2026-09-25T09:58:56.656747+08:00" hostname="77deMacBook-Air.local"><testcase classname="probes.test_seeded_c3" name="test_outside_window_mutation_fails[amount]" time="2.358" /><testcase classname="probes.test_seeded_c3" name="test_outside_window_mutation_fails[timestamp]" time="1.578" /><testcase classname="probes.test_seeded_c3" name="test_outside_window_mutation_fails[delete]" time="1.435" /><testcase classname="probes.test_seeded_c3" name="test_outside_window_mutation_fails[insert]" time="1.486" /><testcase classname="probes.test_seeded_c3" name="test_outside_window_mutation_fails[duplicate]" time="1.324" /><testcase classname="probes.test_seeded_c3" name="test_outside_window_mutation_fails[other_stock]" time="1.668" /><testcase classname="probes.test_seeded_c3" name="test_baseline_pass" time="1.525" /><testcase classname="probes.test_earlier_fixture_adapter" name="test_new_outside_window_mutations_fail[earlier_than_window]" time="1.801" /><testcase classname="probes.test_earlier_fixture_adapter" name="test_new_outside_window_mutations_fail[null_column]" time="1.812" /><testcase classname="probes.test_earlier_fixture_adapter" name="test_baseline_with_earlier_row_pass" time="1.692" /></testsuite></testsuites>
```
