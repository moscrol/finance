# Immutable evidence packet
No reasoning transcript or other-axis results included.
Raw command output is authoritative. Prior-stage prose may contain errors: never promote a proposed correction or unsupported PASS label to an observed result. Missing evidence must remain explicit.


## explore/parsed.json
```text
{
  "claims_examined": [
    "C1",
    "C2",
    "C3",
    "C4",
    "C5",
    "C6",
    "C7"
  ],
  "limits": [
    "No tests or positive control observed yet."
  ],
  "next_stage_command": "OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /Users/a77/finance-workspace-private/.venv-workbench/bin/python -B -m pytest -q /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-13/quality/work/probes/test_seeded_c3.py /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-13/quality/work/probes/test_earlier_fixture_adapter.py /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-13/quality/work/probes/test_production_contract.py --rootdir=/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-13/quality/work -p no:cacheprovider --junitxml=/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-13/quality/work/probe-results-all.xml --basetemp=/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-13/quality/work/tmp/reviewer",
  "probe_files": [
    "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-13/quality/work/probes/test_seeded_c3.py",
    "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-13/quality/work/probes/test_earlier_fixture_adapter.py",
    "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-13/quality/work/probes/test_production_contract.py"
  ],
  "provenance": "All tests supplied. 10 prior-reviewer assertions plus 14 host-authored tests. No execution in explore.",
  "complete": true,
  "stage": "explore",
  "axis": "quality",
  "revision": "f650d9e765e127c7e66a621226cc2d676d70075d",
  "baseline": "79861f07e48573b6b5bd378b28880e484f509905"
}

```


## execute/parsed.json
```text
{
  "claims": [
    {
      "id": "C1",
      "status": "verified",
      "evidence": "Reviewer-executed parent CLI on frozen real-date subset: apply exit 0, verify exit 0 (independent-real-date-observation.json); 37-check acceptance oracle exit 0 with expected revision f650d9e… and source sha256 4c2d1b7e…ca26. Exact 53-INSERT/1-UPDATE split not independently enumerated by reviewer (limit)."
    },
    {
      "id": "C2",
      "status": "verified",
      "evidence": "test_corrupt_authorized_source_refuses_without_publish[missing|null|adjusted] all passed; wrong.parquet CLI refusal observed exit 2 without publish; window boundary enforced by acceptance oracle."
    },
    {
      "id": "C3",
      "status": "verified",
      "evidence": "Seeded mutation oracle: 6 cases in test_seeded_c3 (amount/timestamp/delete/insert/duplicate/other_stock) and 3 in test_earlier_fixture_adapter (earlier_than_window/null_column) all fail correctly; baseline passes. My run: rows=64, technical=39, window=161, acceptance_checks=37."
    },
    {
      "id": "C4",
      "status": "verified",
      "evidence": "In-scope only: CLI parent apply/verify/refuse exits coherent; unsafe-input preflight (existing/under_source/symlink/wal/bad_hash) and low-space refusal before copies all passed; receipt-coherence probes passed. No full security audit performed (per claim scope)."
    },
    {
      "id": "C5",
      "status": "verified",
      "evidence": "My isolated subset rehearsal: apply exit 0, verify exit 0, 37 acceptance checks pass, amount=1e15 negative control exit 2, backup_rollback_match=true; unsafe identity/WAL/symlink/hash rejections pass. Limits: full-copy rehearsal is host-supplied audit-only (inputs/host-rehearsal), not reviewer execution; production read-only/unchanged not independently observed by reviewer."
    },
    {
      "id": "C6",
      "status": "verified",
      "evidence": "Three host-authored regression witnesses passed (fdopen receipt-write-failure cleanup, open permission preflight block, EEXIST race): test_context_regression_witness_rejects_degraded_scope 3/3. Six author test-body invocations (candidate + external scope-mutant × 3) disclosed as running inside witnesses only; no standalone author pytest invocation."
    },
    {
      "id": "C7",
      "status": "verified",
      "evidence": "Observation JSON and passing test_host_full_copy_receipts_are_current_but_not_reviewer_execution bind evidence to revision f650d9e765e127c7e66a621226cc2d676d70075d integrated with main 79861f07e48573b6b5bd378b28880e484f509905. Verdict is code-binding only; engineering gate still running, merge/production approvals remain false."
    }
  ],
  "counts": {
    "executed": 24,
    "errors": 0,
    "failed": 0,
    "passed": 24,
    "skipped": 0
  },
  "evidence": {
    "junit": "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-13/quality/work/probe-results-all.xml",
    "observation": "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-13/quality/work/independent-real-date-observation.json",
    "positive_control": "exit 1, AssertionError: intentional probe_bug control (as required)",
    "report": "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-13/quality/work/EXECUTE.md"
  },
  "limits": [
    "Frozen real-data subset only (302132.SZ verbatim + sentinel 000001.SZ + calendar), not full production copy",
    "53-INSERT/1-UPDATE split and production-unchanged property rest on acceptance oracle and host receipts, not independent row enumeration",
    "Host full-copy rehearsal is external audit-only evidence, not reviewer execution",
    "Engineering readiness gate running separately; C7 verdict covers code binding only"
  ],
  "verdict": "PASS_WITH_LIMITS",
  "complete": true,
  "stage": "execute",
  "axis": "quality",
  "revision": "f650d9e765e127c7e66a621226cc2d676d70075d",
  "baseline": "79861f07e48573b6b5bd378b28880e484f509905"
}

```


## work/EXPLORE.md
MISSING: not delivered by previous stage. No substitute was authored.


## work/EXECUTE.md
```text
# PR813 QC — EXECUTE (reviewer stage)

## Controls
- Positive control: `positive_control.py` exit 1, `AssertionError: intentional probe_bug control` — as required (fresh, intentional).
- Direct pytest (single invocation, exact command): **24 passed, 0 failed, 0 errors, 0 skipped** in 21.69s.
  JUnit authority: probe-results-all.xml → tests=24, failures=0, errors=0, skipped=0.

## Counts (from JUnit)
executed=24, passed=24, failed=0, errors=0, skipped=0.
Breakdown: test_seeded_c3=7, test_earlier_fixture_adapter=3, test_production_contract=14 (incl. 3 regression witnesses embedding 6 author-test body invocations: candidate + external scope-mutant, ×3 tests; no standalone author pytest run).

## Reviewer-executed numeric evidence (independent-real-date-observation.json, generated by the run)
- Frozen subset, not full production (verbatim 302132.SZ + sentinel 000001.SZ + calendar).
- Window rows=64, technical=39, window=161, acceptance_checks=37, backup_rollback_match=true.
- CLI parent: wrong parquet refused exit 2; apply exit 0; verify-only exit 0; acceptance script exit 0; amount=1e15 negative control exit 2.
- Revision bound f650d9e765e127c7e66a621226cc2d676d70075d; source sha256 4c2d1b7e…ca26 consistent across observation and receipts test.

## Claim verdicts
- C1 verified — parent apply/verify and acceptance run executed against frozen source with correct exit codes; contract checked by the 37-check acceptance oracle on the reviewer-executed subset. Exact 53-INSERT/1-UPDATE split was not independently enumerated row-by-row by me (limit, not contradiction).
- C2 verified — test_corrupt_authorized_source_refuses_without_publish[missing|null|adjusted] all pass; wrong-parquet refusal observed exit 2 without publish.
- C3 verified — seeded oracle catches amount/timestamp/delete/insert/duplicate/other-stock mutations (6 cases) + earlier-than-window/null_column (3 cases); baseline passes; window numerics 64/39/161 from my run.
- C4 verified (in scope) — CLI parent apply/verify/refuse, preflight unsafe-state rejections (5 cases), low-space refusal, receipt coherence test all pass. Not a full security audit (out of scope by claim).
- C5 verified with limits — my run covered isolated subset rehearsal: apply/verify/37 checks/rollback match/amount control; unsafe identity/WAL/symlink/bad-hash rejections. Fresh full-copy rehearsal is host-supplied (inputs/host-rehearsal, audit-only) — not my execution; production read-only/unchanged not independently observed by me.
- C6 verified — three regression witnesses (fdopen/open/EEXIST-race) passed; six author-body invocations disclosed; monkeypatch.context confinement asserted by passing witnesses.
- C7 verified — code binding to revision f650d9e… integrated with main 79861f0… observed in run receipts; test_host_full_copy_receipts_are_current_but_not_reviewer_execution passes (explicitly not my execution); full engineering gate still running — not a QC fact, merge/production approvals remain false.

## Limits
1. Reviewer executed on frozen real-data subset only, not a full production copy.
2. 53/1 insert/update split and production-unchanged property rest on the acceptance oracle + host receipts, not independent row enumeration.
3. Host full-copy rehearsal is audit-only external evidence.
4. Engineering readiness gate running separately; C7 verdict is code-binding only.

## Verdict
PASS_WITH_LIMITS

```


## execute/commands/001-bash/output.log
```text
Traceback (most recent call last):
  File "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-13/quality/work/positive_control.py", line 1, in <module>
    assert 1 == 2, "intentional probe_bug control"
           ^^^^^^
AssertionError: intentional probe_bug control

```


## execute/commands/001-bash/request.json
```text
{"toolCallId":"call_0207b01be0764cc99b39fc2a","params":{"command":"OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /Users/a77/finance-workspace-private/.venv-workbench/bin/python -B /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-13/quality/work/positive_control.py"}}
```


## execute/commands/001-bash/result.json
```text
{"exitCode":1}
```


## execute/commands/002-bash/output.log
```text
........................                                                 [100%]
- generated xml file: /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-13/quality/work/probe-results-all.xml -
24 passed in 21.69s

```


## execute/commands/002-bash/request.json
```text
{"toolCallId":"call_ae928f61540841c88d14bc5e","params":{"command":"OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /Users/a77/finance-workspace-private/.venv-workbench/bin/python -B -m pytest -q /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-13/quality/work/probes/test_seeded_c3.py /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-13/quality/work/probes/test_earlier_fixture_adapter.py /Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-13/quality/work/probes/test_production_contract.py --rootdir=/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-13/quality/work -p no:cacheprovider --junitxml=/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-13/quality/work/probe-results-all.xml --basetemp=/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-13/quality/work/tmp/reviewer","timeout":1200}}
```


## execute/commands/002-bash/result.json
```text
{"exitCode":0}
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

CAND = Path("/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-13/candidate")
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

CAND = Path("/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-13/candidate")
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


## work/probes/test_production_contract.py
```text
"""HOST-SUPPLIED probes, not model-authored assertions or a review verdict.

Runs the real parent and external acceptance against a frozen real-data slice.
C6 embeds three author test bodies inside a new restoration/mutation witness;
those six body invocations are disclosed, not standalone author pytest runs.
"""
import ast
from argparse import Namespace
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from types import SimpleNamespace

import duckdb
import pytest

BATCH = Path(__file__).resolve().parents[3]
TREE = BATCH / 'candidate'
Q = BATCH / 'quality'
INPUTS = Q / 'inputs'
sys.path.insert(0, str(TREE))
from market_feature_store.sync import repair_backfill_stock_history as mod
from market_feature_store.sync.repair_hithink_stock_day import RepairRefused
from scripts.review_probes import rehearse_302132_backfill as rehearsal

REV = json.loads((Q / 'config.json').read_text())['revision']
SOURCE = INPUTS / 'production-slice.duckdb'
PARQUET = INPUTS / 'frozen.parquet'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, obj):
    with path.open('x') as stream:
        json.dump(obj, stream, indent=2, default=str)


def command(argv, cwd=TREE, extra=None):
    env = {k: os.environ[k] for k in ('HOME', 'PATH', 'LANG', 'TMPDIR') if k in os.environ}
    env.update(PYTHONDONTWRITEBYTECODE='1', OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', GIT_OPTIONAL_LOCKS='0')
    env.update(extra or {})
    return subprocess.run(argv, cwd=cwd, env=env, capture_output=True, text=True, timeout=90)


def test_real_date_parent_rehearsal_and_numeric_contract(tmp_path):
    before = sha(SOURCE)
    manifest = json.loads((INPUTS / 'fixture-manifest.json').read_text())
    assert before == manifest['fixture_sha256']
    assert sha(PARQUET) == mod.PARQUET_SHA256
    with duckdb.connect(str(SOURCE), read_only=True) as con:
        assert str(con.execute("SELECT max(trade_date) FROM fact_stock_daily_hithink WHERE stock_ts_code='302132.SZ' AND adjusted='none'").fetchone()[0]) > max(mod.GAP_PARALLEL)
    out = tmp_path / 'real-date-rehearsal'
    argv = [sys.executable, '-B', str(TREE / 'scripts/review_probes/rehearse_302132_backfill.py'),
            '--production', str(SOURCE), '--parquet', str(PARQUET), '--output', str(out)]
    result = command(argv)
    save(tmp_path / 'rehearsal-process.json', {'argv': argv, 'exit': result.returncode, 'stdout': result.stdout, 'stderr': result.stderr})
    assert result.returncode == 0, result.stdout + result.stderr
    summary = json.loads((out / 'summary.json').read_text())
    assert summary['ok'] and summary['production_unchanged']
    assert summary['revision'] == REV and summary['dirty'] is False
    assert summary['rollback_sha256'] == summary['baseline_sha256'] == before
    assert summary['values_before']['rows'] == 11
    assert summary['values_after']['rows'] == 64
    assert summary['values_after']['non_null'] == {'close': 64, 'pct_chg': 64, 'amount': 64}
    assert summary['values_after']['identical_adjacent_values'] == []
    assert summary['failure_did_not_publish']
    acceptance = json.loads((out / 'acceptance.json').read_text())
    assert acceptance['verdict'] == 'PASS' and acceptance['failed'] == []
    checks = {v['name']: v for v in acceptance['checks']}
    assert len(checks) == 37 and all(v['ok'] for v in checks.values())
    assert checks['window_golden_triples']['detail'] == {'actual': 161, 'golden': 161}
    assert checks['technical_exact_set']['detail'] == 39
    assert checks['expected_window_counts_match_golden']['detail']['golden'] == {'5': 59, '10': 54, '20': 44, '60': 4}
    applied = json.loads((out / f"copy.duckdb.repair-backfill-execution.{summary['runs']['apply']}.json").read_text())
    verified = json.loads((out / f"copy.duckdb.repair-backfill-execution.{summary['runs']['verify']}.json").read_text())
    for receipt, mode in ((applied, 'apply'), (verified, 'verify')):
        assert receipt['code_revision'] == REV and receipt['code_dirty'] is False
        assert receipt['child_report']['mode'] == mode
        assert receipt['child_report']['technical_rows'] == 39
        assert receipt['child_report']['window_rows'] == 161
        assert receipt['child_report']['ok'] is True
    assert applied['backup']['backup_sha256'] == before
    assert applied['run_id'] != verified['run_id']
    control = json.loads((out / 'amount-control.json').read_text())
    assert control['failed'] == ['keyset_fullfield_oracle']
    assert sha(SOURCE) == before
    save(Q / 'work/independent-real-date-observation.json', {
        'revision': REV, 'classification': 'reviewer executes host-supplied probes on frozen real-data subset; not full production copy',
        'rows': 64, 'technical': 39, 'window': 161, 'acceptance_checks': 37,
        'rehearsal_directory': str(out), 'backup_rollback_match': True,
        'source_sha256': before, 'commands': summary['commands']})


@pytest.mark.parametrize('mutation', ['missing', 'null', 'adjusted'])
def test_corrupt_authorized_source_refuses_without_publish(tmp_path, mutation):
    target = tmp_path / 'input.duckdb'
    shutil.copyfile(SOURCE, target)
    with duckdb.connect(str(target)) as con:
        where = "stock_ts_code='302132.SZ' AND trade_date='2026-06-17' AND adjusted='none'"
        if mutation == 'missing':
            con.execute('DELETE FROM fact_stock_daily_hithink WHERE ' + where)
        elif mutation == 'null':
            con.execute('UPDATE fact_stock_daily_hithink SET close=NULL WHERE ' + where)
        else:
            con.execute("UPDATE fact_stock_daily_hithink SET adjusted='invalid-review-control' WHERE " + where)
    before = sha(target)
    result = command([sys.executable, '-B', '-m', 'market_feature_store.cli',
                      'repair-backfill-302132', '--parquet', str(PARQUET)],
                     extra={'MARKET_FEATURE_STORE_DB': str(target), 'MARKET_FEATURE_STORE_PRODUCTION_DB': str(SOURCE)})
    save(tmp_path / 'refusal-process.json', {'mutation': mutation, 'exit': result.returncode, 'stdout': result.stdout, 'stderr': result.stderr})
    assert result.returncode == 2, result.stdout + result.stderr
    assert sha(target) == before
    assert not list(tmp_path.glob('*.bak-*'))


class RemoveContext(ast.NodeTransformer):
    def visit_With(self, node):
        if any(isinstance(i.context_expr, ast.Call) and isinstance(i.context_expr.func, ast.Attribute)
               and i.context_expr.func.attr == 'context' for i in node.items):
            return [self.visit(child) for child in node.body]
        return self.generic_visit(node)

    def visit_Name(self, node):
        if node.id == 'patch':
            return ast.copy_location(ast.Name(id='monkeypatch', ctx=node.ctx), node)
        return node


@pytest.mark.parametrize('name,attribute', [
    ('test_refused_receipt_write_failure_cleans_partial', 'fdopen'),
    ('test_cli_parent_preflight_blocks_on_open_permission_error', 'open'),
    ('test_refused_receipt_eexist_race_keeps_other_writers_file', 'open'),
])
def test_context_regression_witness_rejects_degraded_scope(tmp_path, name, attribute):
    source = (TREE / 'tests/test_repair_backfill_stock_history.py').read_text()
    observations = []
    for mutated in (False, True):
        function = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == name)
        function.decorator_list = []
        module = ast.Module(body=[function], type_ignores=[])
        if mutated:
            module = RemoveContext().visit(module)
        ast.fix_missing_locations(module)
        namespace = {'mod': mod, 'pytest': pytest, 'RepairRefused': RepairRefused}
        exec(compile(module, '<external-scope-witness>', 'exec'), namespace)
        folder = tmp_path / ('mutant' if mutated else 'candidate')
        folder.mkdir()
        patch = pytest.MonkeyPatch()
        before = getattr(os, attribute)
        error = None
        try:
            try:
                namespace[name](folder, patch)
            except AssertionError as exc:
                error = repr(exc)
            restored = getattr(os, attribute) is before
        finally:
            patch.undo()
        assert getattr(os, attribute) is before
        observations.append({'mutated': mutated, 'restored_before_fixture_cleanup': restored, 'body_assertion_error': error})
        if mutated:
            assert not restored or error is not None, 'degraded scope escaped the witness'
        else:
            assert restored and error is None
    save(tmp_path / 'scope-witness.json', {'copied_author_body': name, 'standalone_author_pytest_runs': 0, 'body_invocations': 2, 'observations': observations})


@pytest.mark.parametrize('case', ['existing', 'under_source', 'symlink', 'wal', 'bad_hash'])
def test_rehearsal_rejects_unsafe_input_before_copy(tmp_path, case):
    data = tmp_path / 'data'
    data.mkdir()
    source = data / 'source.duckdb'
    shutil.copyfile(SOURCE, source)
    parquet = data / 'frozen.parquet'
    shutil.copyfile(PARQUET, parquet)
    output = tmp_path / 'run'
    if case == 'existing':
        output.mkdir()
    elif case == 'under_source':
        output = data / 'run'
    elif case == 'symlink':
        alias = data / 'alias.duckdb'
        alias.symlink_to(source)
        source = alias
    elif case == 'wal':
        Path(str(source) + '.wal').write_bytes(b'WAL witness')
    else:
        parquet.write_bytes(b'bad hash witness')
    before = {p.name: sha(p) for p in data.iterdir() if p.is_file()}
    with pytest.raises(ValueError):
        rehearsal.run(Namespace(production=source, parquet=parquet, output=output))
    assert {p.name: sha(p) for p in data.iterdir() if p.is_file()} == before
    assert not output.exists() or (case == 'existing' and list(output.iterdir()) == [])


def test_low_space_refuses_before_database_copies(tmp_path, monkeypatch):
    out = tmp_path / 'low-space'
    with monkeypatch.context() as patch:
        patch.setattr(rehearsal.shutil, 'disk_usage', lambda _: SimpleNamespace(free=0))
        rc = rehearsal.run(Namespace(production=SOURCE, parquet=PARQUET, output=out))
    assert rc == 2
    result = json.loads((out / 'summary.json').read_text())
    assert 'insufficient physical headroom' in result['error']
    assert not list(out.glob('*.duckdb'))


def test_host_full_copy_receipts_are_current_but_not_reviewer_execution():
    root = INPUTS / 'host-rehearsal'
    summary = json.loads((root / 'summary.json').read_text())
    assert summary['revision'] == REV and summary['dirty'] is False
    assert summary['ok'] and summary['production_unchanged']
    assert summary['production_before']['size'] > SOURCE.stat().st_size
    assert summary['rollback_sha256'] == summary['baseline_sha256']
    manifest = json.loads((root / 'manifest.json').read_text())
    for name, expected in manifest.items():
        path = root / name
        if path.is_file():
            assert sha(path) == expected
    for name, expected in [('refused-parent', 2), ('apply', 0), ('verify', 0), ('acceptance', 0), ('amount-control', 2)]:
        receipt = json.loads((root / f'{name}.command.json').read_text())
        assert receipt['exit_code'] == receipt['expected_exit'] == expected

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


## work/probe-results-all.xml
```text
<?xml version="1.0" encoding="utf-8"?><testsuites><testsuite name="pytest" errors="0" failures="0" skipped="0" tests="24" time="21.684" timestamp="2026-09-25T12:17:31.648868+08:00" hostname="77deMacBook-Air.local"><testcase classname="probes.test_seeded_c3" name="test_outside_window_mutation_fails[amount]" time="1.423" /><testcase classname="probes.test_seeded_c3" name="test_outside_window_mutation_fails[timestamp]" time="1.124" /><testcase classname="probes.test_seeded_c3" name="test_outside_window_mutation_fails[delete]" time="0.985" /><testcase classname="probes.test_seeded_c3" name="test_outside_window_mutation_fails[insert]" time="0.876" /><testcase classname="probes.test_seeded_c3" name="test_outside_window_mutation_fails[duplicate]" time="0.849" /><testcase classname="probes.test_seeded_c3" name="test_outside_window_mutation_fails[other_stock]" time="0.922" /><testcase classname="probes.test_seeded_c3" name="test_baseline_pass" time="0.838" /><testcase classname="probes.test_earlier_fixture_adapter" name="test_new_outside_window_mutations_fail[earlier_than_window]" time="0.968" /><testcase classname="probes.test_earlier_fixture_adapter" name="test_new_outside_window_mutations_fail[null_column]" time="1.235" /><testcase classname="probes.test_earlier_fixture_adapter" name="test_baseline_with_earlier_row_pass" time="1.100" /><testcase classname="probes.test_production_contract" name="test_real_date_parent_rehearsal_and_numeric_contract" time="6.543" /><testcase classname="probes.test_production_contract" name="test_corrupt_authorized_source_refuses_without_publish[missing]" time="1.474" /><testcase classname="probes.test_production_contract" name="test_corrupt_authorized_source_refuses_without_publish[null]" time="1.123" /><testcase classname="probes.test_production_contract" name="test_corrupt_authorized_source_refuses_without_publish[adjusted]" time="1.035" /><testcase classname="probes.test_production_contract" name="test_context_regression_witness_rejects_degraded_scope[test_refused_receipt_write_failure_cleans_partial-fdopen]" time="0.035" /><testcase classname="probes.test_production_contract" name="test_context_regression_witness_rejects_degraded_scope[test_cli_parent_preflight_blocks_on_open_permission_error-open]" time="0.134" /><testcase classname="probes.test_production_contract" name="test_context_regression_witness_rejects_degraded_scope[test_refused_receipt_eexist_race_keeps_other_writers_file-open]" time="0.024" /><testcase classname="probes.test_production_contract" name="test_rehearsal_rejects_unsafe_input_before_copy[existing]" time="0.116" /><testcase classname="probes.test_production_contract" name="test_rehearsal_rejects_unsafe_input_before_copy[under_source]" time="0.106" /><testcase classname="probes.test_production_contract" name="test_rehearsal_rejects_unsafe_input_before_copy[symlink]" time="0.122" /><testcase classname="probes.test_production_contract" name="test_rehearsal_rejects_unsafe_input_before_copy[wal]" time="0.117" /><testcase classname="probes.test_production_contract" name="test_rehearsal_rejects_unsafe_input_before_copy[bad_hash]" time="0.107" /><testcase classname="probes.test_production_contract" name="test_low_space_refuses_before_database_copies" time="0.266" /><testcase classname="probes.test_production_contract" name="test_host_full_copy_receipts_are_current_but_not_reviewer_execution" time="0.008" /></testsuite></testsuites>
```


## work/independent-real-date-observation.json
```text
{
  "revision": "f650d9e765e127c7e66a621226cc2d676d70075d",
  "classification": "reviewer executes host-supplied probes on frozen real-data subset; not full production copy",
  "rows": 64,
  "technical": 39,
  "window": 161,
  "acceptance_checks": 37,
  "rehearsal_directory": "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-13/quality/work/tmp/reviewer/test_real_date_parent_rehearsa0/real-date-rehearsal",
  "backup_rollback_match": true,
  "source_sha256": "4c2d1b7e53770e9daead4af503e466a815d371294c22b3b4b6909fdd4da2ca26",
  "commands": [
    {
      "label": "refused-parent",
      "argv": [
        "/Users/a77/finance-workspace-private/.venv-workbench/bin/python",
        "-m",
        "market_feature_store.cli",
        "repair-backfill-302132",
        "--parquet",
        "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-13/quality/work/tmp/reviewer/test_real_date_parent_rehearsa0/real-date-rehearsal/wrong.parquet"
      ],
      "expected_exit": 2,
      "exit_code": 2,
      "seconds": 0.65
    },
    {
      "label": "apply",
      "argv": [
        "/Users/a77/finance-workspace-private/.venv-workbench/bin/python",
        "-m",
        "market_feature_store.cli",
        "repair-backfill-302132",
        "--parquet",
        "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-13/quality/work/tmp/reviewer/test_real_date_parent_rehearsa0/real-date-rehearsal/frozen.parquet"
      ],
      "expected_exit": 0,
      "exit_code": 0,
      "seconds": 1.861
    },
    {
      "label": "verify",
      "argv": [
        "/Users/a77/finance-workspace-private/.venv-workbench/bin/python",
        "-m",
        "market_feature_store.cli",
        "repair-backfill-302132",
        "--parquet",
        "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-13/quality/work/tmp/reviewer/test_real_date_parent_rehearsa0/real-date-rehearsal/frozen.parquet"
      ],
      "expected_exit": 0,
      "exit_code": 0,
      "seconds": 1.454
    },
    {
      "label": "acceptance",
      "argv": [
        "/Users/a77/finance-workspace-private/.venv-workbench/bin/python",
        "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-13/candidate/scripts/verify_302132_backfill_acceptance.py",
        "--production",
        "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-13/quality/work/tmp/reviewer/test_real_date_parent_rehearsa0/real-date-rehearsal/baseline.duckdb",
        "--clone",
        "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-13/quality/work/tmp/reviewer/test_real_date_parent_rehearsa0/real-date-rehearsal/copy.duckdb",
        "--parquet",
        "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-13/quality/work/tmp/reviewer/test_real_date_parent_rehearsa0/real-date-rehearsal/frozen.parquet",
        "--run-apply",
        "9bee09824f80",
        "--run-verify",
        "207d080f1b09",
        "--expected-revision",
        "f650d9e765e127c7e66a621226cc2d676d70075d",
        "--expected-production-sha256",
        "4c2d1b7e53770e9daead4af503e466a815d371294c22b3b4b6909fdd4da2ca26",
        "--output",
        "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-13/quality/work/tmp/reviewer/test_real_date_parent_rehearsa0/real-date-rehearsal/acceptance.json"
      ],
      "expected_exit": 0,
      "exit_code": 0,
      "seconds": 0.628
    },
    {
      "label": "amount-control",
      "argv": [
        "/Users/a77/finance-workspace-private/.venv-workbench/bin/python",
        "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-13/candidate/scripts/verify_302132_backfill_acceptance.py",
        "--production",
        "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-13/quality/work/tmp/reviewer/test_real_date_parent_rehearsa0/real-date-rehearsal/baseline.duckdb",
        "--clone",
        "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-13/quality/work/tmp/reviewer/test_real_date_parent_rehearsa0/real-date-rehearsal/copy.duckdb",
        "--parquet",
        "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-13/quality/work/tmp/reviewer/test_real_date_parent_rehearsa0/real-date-rehearsal/frozen.parquet",
        "--run-apply",
        "9bee09824f80",
        "--run-verify",
        "207d080f1b09",
        "--expected-revision",
        "f650d9e765e127c7e66a621226cc2d676d70075d",
        "--expected-production-sha256",
        "4c2d1b7e53770e9daead4af503e466a815d371294c22b3b4b6909fdd4da2ca26",
        "--output",
        "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-13/quality/work/tmp/reviewer/test_real_date_parent_rehearsa0/real-date-rehearsal/amount-control.json"
      ],
      "expected_exit": 2,
      "exit_code": 2,
      "seconds": 0.819
    }
  ]
}
```


## work/tmp/reviewer/test_real_date_parent_rehearsa0/real-date-rehearsal/summary.json
```text
{
  "revision": "f650d9e765e127c7e66a621226cc2d676d70075d",
  "dirty": false,
  "commands": [
    {
      "label": "refused-parent",
      "argv": [
        "/Users/a77/finance-workspace-private/.venv-workbench/bin/python",
        "-m",
        "market_feature_store.cli",
        "repair-backfill-302132",
        "--parquet",
        "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-13/quality/work/tmp/reviewer/test_real_date_parent_rehearsa0/real-date-rehearsal/wrong.parquet"
      ],
      "expected_exit": 2,
      "exit_code": 2,
      "seconds": 0.65
    },
    {
      "label": "apply",
      "argv": [
        "/Users/a77/finance-workspace-private/.venv-workbench/bin/python",
        "-m",
        "market_feature_store.cli",
        "repair-backfill-302132",
        "--parquet",
        "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-13/quality/work/tmp/reviewer/test_real_date_parent_rehearsa0/real-date-rehearsal/frozen.parquet"
      ],
      "expected_exit": 0,
      "exit_code": 0,
      "seconds": 1.861
    },
    {
      "label": "verify",
      "argv": [
        "/Users/a77/finance-workspace-private/.venv-workbench/bin/python",
        "-m",
        "market_feature_store.cli",
        "repair-backfill-302132",
        "--parquet",
        "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-13/quality/work/tmp/reviewer/test_real_date_parent_rehearsa0/real-date-rehearsal/frozen.parquet"
      ],
      "expected_exit": 0,
      "exit_code": 0,
      "seconds": 1.454
    },
    {
      "label": "acceptance",
      "argv": [
        "/Users/a77/finance-workspace-private/.venv-workbench/bin/python",
        "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-13/candidate/scripts/verify_302132_backfill_acceptance.py",
        "--production",
        "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-13/quality/work/tmp/reviewer/test_real_date_parent_rehearsa0/real-date-rehearsal/baseline.duckdb",
        "--clone",
        "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-13/quality/work/tmp/reviewer/test_real_date_parent_rehearsa0/real-date-rehearsal/copy.duckdb",
        "--parquet",
        "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-13/quality/work/tmp/reviewer/test_real_date_parent_rehearsa0/real-date-rehearsal/frozen.parquet",
        "--run-apply",
        "9bee09824f80",
        "--run-verify",
        "207d080f1b09",
        "--expected-revision",
        "f650d9e765e127c7e66a621226cc2d676d70075d",
        "--expected-production-sha256",
        "4c2d1b7e53770e9daead4af503e466a815d371294c22b3b4b6909fdd4da2ca26",
        "--output",
        "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-13/quality/work/tmp/reviewer/test_real_date_parent_rehearsa0/real-date-rehearsal/acceptance.json"
      ],
      "expected_exit": 0,
      "exit_code": 0,
      "seconds": 0.628
    },
    {
      "label": "amount-control",
      "argv": [
        "/Users/a77/finance-workspace-private/.venv-workbench/bin/python",
        "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-13/candidate/scripts/verify_302132_backfill_acceptance.py",
        "--production",
        "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-13/quality/work/tmp/reviewer/test_real_date_parent_rehearsa0/real-date-rehearsal/baseline.duckdb",
        "--clone",
        "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-13/quality/work/tmp/reviewer/test_real_date_parent_rehearsa0/real-date-rehearsal/copy.duckdb",
        "--parquet",
        "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-13/quality/work/tmp/reviewer/test_real_date_parent_rehearsa0/real-date-rehearsal/frozen.parquet",
        "--run-apply",
        "9bee09824f80",
        "--run-verify",
        "207d080f1b09",
        "--expected-revision",
        "f650d9e765e127c7e66a621226cc2d676d70075d",
        "--expected-production-sha256",
        "4c2d1b7e53770e9daead4af503e466a815d371294c22b3b4b6909fdd4da2ca26",
        "--output",
        "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-13/quality/work/tmp/reviewer/test_real_date_parent_rehearsa0/real-date-rehearsal/amount-control.json"
      ],
      "expected_exit": 2,
      "exit_code": 2,
      "seconds": 0.819
    }
  ],
  "ok": true,
  "production_before": {
    "path": "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-13/quality/inputs/production-slice.duckdb",
    "size": 10235904,
    "mtime_ns": 1790309614153952499,
    "inode": 267640071,
    "freshness": {
      "fact_auction_hithink": "None",
      "fact_auction_stock_daily": "None",
      "fact_core_leader_daily": "None",
      "fact_core_stock_daily": "None",
      "fact_dragon_hot_money_hithink": "None",
      "fact_dragon_seat_daily": "None",
      "fact_dragon_summary_daily": "None",
      "fact_dragon_tiger_daily": "None",
      "fact_dragon_tiger_hithink": "None",
      "fact_global_index_daily": "None",
      "fact_global_stock_daily": "None",
      "fact_hot_stock_rank_hithink": "None",
      "fact_leader_height_daily": "None",
      "fact_limit_advance_daily": "None",
      "fact_limit_advance_presence": "None",
      "fact_limit_pool_hithink": "None",
      "fact_mainline_sector_daily": "None",
      "fact_mainline_stock_daily": "None",
      "fact_mainline_theme_daily": "None",
      "fact_market_daily": "2026-09-22",
      "fact_polymarket_macro_odds_daily": "None",
      "fact_sector_daily": "None",
      "fact_sector_daily_generation": "None",
      "fact_sector_kline_daily": "None",
      "fact_sector_period_rank_daily": "None",
      "fact_sector_stock_daily": "2026-09-18",
      "fact_sector_stock_daily_generation": "2026-09-18",
      "fact_sector_universe_daily": "None",
      "fact_stock_daily": "2026-09-22",
      "fact_stock_daily_hithink": "2026-09-22",
      "fact_stock_high_daily": "None",
      "fact_stock_technical_snapshot": "None",
      "fact_sw_l1_daily": "None",
      "fact_theme_flow_daily": "None",
      "fact_theme_limit_heat_daily": "None",
      "fact_theme_limit_stock_daily": "None"
    }
  },
  "free_bytes_before": 57809543168,
  "baseline_copy": {
    "method": "clonefile",
    "seconds": 0.006,
    "bytes": 10235904
  },
  "baseline_sha256": "4c2d1b7e53770e9daead4af503e466a815d371294c22b3b4b6909fdd4da2ca26",
  "parquet_sha256": "51f9ee9cba1ceb4a6ff50c4c4dce8267cb39f78add28d6a33699cbf90bf28d17",
  "target_copy": {
    "method": "clonefile",
    "seconds": 0.004,
    "bytes": 10235904
  },
  "values_before": {
    "rows": 11,
    "non_null": {
      "close": 10,
      "pct_chg": 10,
      "amount": 10
    },
    "identical_adjacent_values": [],
    "values": [
      [
        "2026-06-15",
        61.35,
        -3.86,
        8.92
      ],
      [
        "2026-06-16",
        60.9,
        -0.1,
        4.39
      ],
      [
        "2026-06-18",
        59.33,
        -1.4452,
        4.1855
      ],
      [
        "2026-06-22",
        60.25,
        1.55,
        4.97
      ],
      [
        "2026-06-23",
        null,
        null,
        null
      ],
      [
        "2026-06-25",
        57.9,
        -0.09,
        4.06
      ],
      [
        "2026-06-26",
        57.08,
        -1.42,
        4.4
      ],
      [
        "2026-07-01",
        58.5,
        0.31,
        5.65
      ],
      [
        "2026-07-07",
        56.69,
        -0.74,
        3.29
      ],
      [
        "2026-07-09",
        55.81,
        0.5,
        3.52
      ],
      [
        "2026-09-11",
        63.42,
        -1.45,
        5.9863
      ]
    ]
  },
  "failure_did_not_publish": true,
  "runs": {
    "apply": "9bee09824f80",
    "verify": "207d080f1b09"
  },
  "values_after": {
    "rows": 64,
    "non_null": {
      "close": 64,
      "pct_chg": 64,
      "amount": 64
    },
    "identical_adjacent_values": [],
    "values": [
      [
        "2026-06-15",
        61.35,
        -3.86,
        8.92
      ],
      [
        "2026-06-16",
        60.9,
        -0.1,
        4.39
      ],
      [
        "2026-06-17",
        60.2,
        -1.15,
        4.8761
      ],
      [
        "2026-06-18",
        59.33,
        -1.4452,
        4.1855
      ],
      [
        "2026-06-22",
        60.25,
        1.55,
        4.97
      ],
      [
        "2026-06-23",
        58.41,
        -3.05,
        4.0741
      ],
      [
        "2026-06-24",
        57.95,
        -0.79,
        3.3992
      ],
      [
        "2026-06-25",
        57.9,
        -0.09,
        4.06
      ],
      [
        "2026-06-26",
        57.08,
        -1.42,
        4.4
      ],
      [
        "2026-06-29",
        57.34,
        0.46,
        3.802
      ],
      [
        "2026-06-30",
        58.32,
        1.71,
        4.5924
      ],
      [
        "2026-07-01",
        58.5,
        0.31,
        5.65
      ],
      [
        "2026-07-02",
        56.85,
        -2.82,
        5.1207
      ],
      [
        "2026-07-03",
        58.71,
        3.27,
        6.1253
      ],
      [
        "2026-07-06",
        57.11,
        -2.73,
        4.1294
      ],
      [
        "2026-07-07",
        56.69,
        -0.74,
        3.29
      ],
      [
        "2026-07-08",
        55.53,
        -2.05,
        3.1527
      ],
      [
        "2026-07-09",
        55.81,
        0.5,
        3.52
      ],
      [
        "2026-07-10",
        57.1,
        2.31,
        6.4238
      ],
      [
        "2026-07-13",
        54.16,
        -5.15,
        4.6114
      ],
      [
        "2026-07-14",
        52.52,
        -3.03,
        3.9136
      ],
      [
        "2026-07-15",
        53.23,
        1.35,
        2.8962
      ],
      [
        "2026-07-16",
        53.37,
        0.26,
        3.6165
      ],
      [
        "2026-07-17",
        52.91,
        -0.86,
        3.8339
      ],
      [
        "2026-07-20",
        55.23,
        4.38,
        5.7983
      ],
      [
        "2026-07-21",
        55.1,
        -0.24,
        4.7251
      ],
      [
        "2026-07-22",
        56.34,
        2.25,
        5.0247
      ],
      [
        "2026-07-23",
        57.69,
        2.4,
        4.9183
      ],
      [
        "2026-07-24",
        55.69,
        -3.47,
        6.586
      ],
      [
        "2026-07-27",
        56.91,
        2.19,
        5.108
      ],
      [
        "2026-07-28",
        56.94,
        0.05,
        4.0027
      ],
      [
        "2026-07-29",
        58.43,
        2.62,
        5.0001
      ],
      [
        "2026-07-30",
        58.74,
        0.53,
        4.9278
      ],
      [
        "2026-07-31",
        58.52,
        -0.37,
        5.0936
      ],
      [
        "2026-08-03",
        57.9,
        -1.06,
        3.144
      ],
      [
        "2026-08-04",
        57.99,
        0.16,
        3.0924
      ],
      [
        "2026-08-05",
        57.97,
        -0.03,
        3.1683
      ],
      [
        "2026-08-06",
        57.85,
        -0.21,
        2.9537
      ],
      [
        "2026-08-07",
        56.96,
        -1.54,
        3.8938
      ],
      [
        "2026-08-10",
        59.78,
        4.95,
        6.7946
      ],
      [
        "2026-08-11",
        58.16,
        -2.71,
        4.8347
      ],
      [
        "2026-08-12",
        57.89,
        -0.46,
        2.4302
      ],
      [
        "2026-08-13",
        57.48,
        -0.71,
        3.9343
      ],
      [
        "2026-08-14",
        58.0,
        0.9,
        5.916
      ],
      [
        "2026-08-17",
        59.4,
        2.41,
        6.801
      ],
      [
        "2026-08-18",
        60.06,
        1.11,
        5.4282
      ],
      [
        "2026-08-19",
        57.02,
        -5.06,
        5.6508
      ],
      [
        "2026-08-20",
        57.09,
        0.12,
        2.54
      ],
      [
        "2026-08-21",
        56.84,
        -0.44,
        2.5404
      ],
      [
        "2026-08-24",
        56.7,
        -0.25,
        3.3667
      ],
      [
        "2026-08-25",
        56.08,
        -1.09,
        2.4168
      ],
      [
        "2026-08-26",
        57.67,
        2.84,
        4.4896
      ],
      [
        "2026-08-27",
        59.71,
        3.54,
        6.6239
      ],
      [
        "2026-08-28",
        60.0,
        0.49,
        4.751
      ],
      [
        "2026-08-31",
        59.7,
        -0.5,
        3.9912
      ],
      [
        "2026-09-01",
        60.76,
        1.78,
        5.9595
      ],
      [
        "2026-09-02",
        63.4,
        4.34,
        17.741
      ],
      [
        "2026-09-03",
        63.75,
        0.55,
        9.6373
      ],
      [
        "2026-09-04",
        63.3,
        -0.71,
        7.3896
      ],
      [
        "2026-09-07",
        61.33,
        -3.11,
        6.2797
      ],
      [
        "2026-09-08",
        62.21,
        1.43,
        5.0617
      ],
      [
        "2026-09-09",
        65.15,
        4.73,
        10.9634
      ],
      [
        "2026-09-10",
        64.35,
        -1.23,
        6.3409
      ],
      [
        "2026-09-11",
        63.42,
        -1.45,
        5.9863
      ]
    ]
  },
  "rollback_copy": {
    "method": "clonefile",
    "seconds": 0.006,
    "bytes": 10235904
  },
  "rollback_sha256": "4c2d1b7e53770e9daead4af503e466a815d371294c22b3b4b6909fdd4da2ca26",
  "production_after": {
    "path": "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-13/quality/inputs/production-slice.duckdb",
    "size": 10235904,
    "mtime_ns": 1790309614153952499,
    "inode": 267640071,
    "freshness": {
      "fact_auction_hithink": "None",
      "fact_auction_stock_daily": "None",
      "fact_core_leader_daily": "None",
      "fact_core_stock_daily": "None",
      "fact_dragon_hot_money_hithink": "None",
      "fact_dragon_seat_daily": "None",
      "fact_dragon_summary_daily": "None",
      "fact_dragon_tiger_daily": "None",
      "fact_dragon_tiger_hithink": "None",
      "fact_global_index_daily": "None",
      "fact_global_stock_daily": "None",
      "fact_hot_stock_rank_hithink": "None",
      "fact_leader_height_daily": "None",
      "fact_limit_advance_daily": "None",
      "fact_limit_advance_presence": "None",
      "fact_limit_pool_hithink": "None",
      "fact_mainline_sector_daily": "None",
      "fact_mainline_stock_daily": "None",
      "fact_mainline_theme_daily": "None",
      "fact_market_daily": "2026-09-22",
      "fact_polymarket_macro_odds_daily": "None",
      "fact_sector_daily": "None",
      "fact_sector_daily_generation": "None",
      "fact_sector_kline_daily": "None",
      "fact_sector_period_rank_daily": "None",
      "fact_sector_stock_daily": "2026-09-18",
      "fact_sector_stock_daily_generation": "2026-09-18",
      "fact_sector_universe_daily": "None",
      "fact_stock_daily": "2026-09-22",
      "fact_stock_daily_hithink": "2026-09-22",
      "fact_stock_high_daily": "None",
      "fact_stock_technical_snapshot": "None",
      "fact_sw_l1_daily": "None",
      "fact_theme_flow_daily": "None",
      "fact_theme_limit_heat_daily": "None",
      "fact_theme_limit_stock_daily": "None"
    }
  },
  "production_unchanged": true,
  "production_sha256_after": "4c2d1b7e53770e9daead4af503e466a815d371294c22b3b4b6909fdd4da2ca26",
  "code_identity_after": [
    "f650d9e765e127c7e66a621226cc2d676d70075d",
    false
  ],
  "removed_rehearsal_copies": [
    {
      "name": "baseline.duckdb",
      "sha256": "4c2d1b7e53770e9daead4af503e466a815d371294c22b3b4b6909fdd4da2ca26",
      "bytes": 10235904
    },
    {
      "name": "copy.duckdb",
      "sha256": "4c2d1b7e53770e9daead4af503e466a815d371294c22b3b4b6909fdd4da2ca26",
      "bytes": 10235904
    },
    {
      "name": "copy.duckdb.bak-20260925T121745-9bee09824f80",
      "sha256": "4c2d1b7e53770e9daead4af503e466a815d371294c22b3b4b6909fdd4da2ca26",
      "bytes": 10235904
    },
    {
      "name": "copy.duckdb.bak-20260925T121746-207d080f1b09",
      "sha256": "449596bedc9062ad31cc1a315664b6c1995951f694999ffc1ae796c95ad79f02",
      "bytes": 14954496
    }
  ],
  "free_bytes_after": 57803091968
}

```


## work/tmp/reviewer/test_real_date_parent_rehearsa0/real-date-rehearsal/acceptance.json
```text
{
  "verdict": "PASS",
  "expected_revision": "f650d9e765e127c7e66a621226cc2d676d70075d",
  "runs": {
    "apply": "9bee09824f80",
    "verify": "207d080f1b09"
  },
  "checks": [
    {
      "name": "args_expected_revision_format",
      "ok": true,
      "detail": "f650d9e765e127c7e66a621226cc2d676d70075d"
    },
    {
      "name": "args_expected_production_sha256_format",
      "ok": true,
      "detail": ""
    },
    {
      "name": "args_run_ids_distinct_nonempty",
      "ok": true,
      "detail": {
        "apply": "9bee09824f80",
        "verify": "207d080f1b09"
      }
    },
    {
      "name": "inputs_regular_files",
      "ok": true,
      "detail": []
    },
    {
      "name": "clone_is_not_production_alias",
      "ok": true,
      "detail": {
        "production": "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-13/quality/work/tmp/reviewer/test_real_date_parent_rehearsa0/real-date-rehearsal/baseline.duckdb",
        "clone": "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-13/quality/work/tmp/reviewer/test_real_date_parent_rehearsa0/real-date-rehearsal/copy.duckdb"
      }
    },
    {
      "name": "production_sha256_before",
      "ok": true,
      "detail": {
        "expected": "4c2d1b7e53770e9d",
        "actual": "4c2d1b7e53770e9d"
      }
    },
    {
      "name": "receipt_apply_readable",
      "ok": true,
      "detail": ""
    },
    {
      "name": "receipt_verify_readable",
      "ok": true,
      "detail": ""
    },
    {
      "name": "receipts_apply_verify_present",
      "ok": true,
      "detail": [
        "apply",
        "verify"
      ]
    },
    {
      "name": "receipt_apply_schema",
      "ok": true,
      "detail": []
    },
    {
      "name": "receipt_verify_schema",
      "ok": true,
      "detail": []
    },
    {
      "name": "receipt_apply_child_report_file",
      "ok": true,
      "detail": "与父收据嵌入子报告深比较"
    },
    {
      "name": "receipt_verify_child_report_file",
      "ok": true,
      "detail": "与父收据嵌入子报告深比较"
    },
    {
      "name": "backup_apply_identity",
      "ok": true,
      "detail": {
        "expected": "4c2d1b7e53770e9d",
        "actual": "4c2d1b7e53770e9d"
      }
    },
    {
      "name": "backup_verify_identity",
      "ok": true,
      "detail": {
        "expected": "449596bedc9062ad",
        "actual": "449596bedc9062ad"
      }
    },
    {
      "name": "backup_apply_matches_baseline",
      "ok": true,
      "detail": "apply 备份 sha == 基线 sha（换库前生产身份）"
    },
    {
      "name": "spec_alignment_apply_verify",
      "ok": true,
      "detail": "apply/verify 授权 spec 深比较（同输入同合同前提）"
    },
    {
      "name": "parquet_readable",
      "ok": true,
      "detail": "51f9ee9cba1ceb4a"
    },
    {
      "name": "parquet_identity_apply",
      "ok": true,
      "detail": {
        "spec": "51f9ee9cba1ceb4a",
        "actual": "51f9ee9cba1ceb4a"
      }
    },
    {
      "name": "parquet_identity_verify",
      "ok": true,
      "detail": {
        "spec": "51f9ee9cba1ceb4a",
        "actual": "51f9ee9cba1ceb4a"
      }
    },
    {
      "name": "fact_other_stocks_allcols",
      "ok": true,
      "detail": ""
    },
    {
      "name": "retained_rows_full_column_identical",
      "ok": true,
      "detail": {
        "rows": 10,
        "expected": 10
      }
    },
    {
      "name": "target_outside_window_allcols",
      "ok": true,
      "detail": [
        0,
        0
      ]
    },
    {
      "name": "hithink_source_untouched",
      "ok": true,
      "detail": ""
    },
    {
      "name": "hithink_adjustment_untouched",
      "ok": true,
      "detail": ""
    },
    {
      "name": "parallel_source_md5_binding",
      "ok": true,
      "detail": {
        "recomputed": "2ddb4224900b3b8e30a85ac0c9b89ffc",
        "rows": 62,
        "apply": "2ddb4224900b3b8e30a85ac0c9b89ffc",
        "verify": "2ddb4224900b3b8e30a85ac0c9b89ffc"
      }
    },
    {
      "name": "keyset_fullfield_oracle",
      "ok": true,
      "detail": {
        "rows": 54,
        "keys": 54,
        "bad": []
      }
    },
    {
      "name": "technical_protected_allcols",
      "ok": true,
      "detail": ""
    },
    {
      "name": "window_protected_allcols",
      "ok": true,
      "detail": ""
    },
    {
      "name": "window_golden_triples",
      "ok": true,
      "detail": {
        "actual": 161,
        "golden": 161
      }
    },
    {
      "name": "expected_window_counts_match_golden",
      "ok": true,
      "detail": {
        "golden": {
          "5": 59,
          "10": 54,
          "20": 44,
          "60": 4
        },
        "spec": {
          "5": 59,
          "10": 54,
          "20": 44,
          "60": 4
        }
      }
    },
    {
      "name": "technical_exact_set",
      "ok": true,
      "detail": 39
    },
    {
      "name": "expected_technical_count_matches_calendar",
      "ok": true,
      "detail": {
        "spec": 39,
        "calendar": 39
      }
    },
    {
      "name": "pinned_technical_target_day",
      "ok": true,
      "detail": [
        59.8542,
        2.6845,
        61.9052,
        2.45
      ]
    },
    {
      "name": "pinned_windows_target_day",
      "ok": true,
      "detail": ""
    },
    {
      "name": "market_daily_untouched",
      "ok": true,
      "detail": ""
    },
    {
      "name": "production_sha256_after",
      "ok": true,
      "detail": {
        "expected": "4c2d1b7e53770e9d",
        "actual": "4c2d1b7e53770e9d"
      }
    }
  ],
  "failed": []
}

```


## work/tmp/reviewer/test_real_date_parent_rehearsa0/real-date-rehearsal/amount-control.json
```text
{
  "verdict": "FAIL",
  "expected_revision": "f650d9e765e127c7e66a621226cc2d676d70075d",
  "runs": {
    "apply": "9bee09824f80",
    "verify": "207d080f1b09"
  },
  "checks": [
    {
      "name": "args_expected_revision_format",
      "ok": true,
      "detail": "f650d9e765e127c7e66a621226cc2d676d70075d"
    },
    {
      "name": "args_expected_production_sha256_format",
      "ok": true,
      "detail": ""
    },
    {
      "name": "args_run_ids_distinct_nonempty",
      "ok": true,
      "detail": {
        "apply": "9bee09824f80",
        "verify": "207d080f1b09"
      }
    },
    {
      "name": "inputs_regular_files",
      "ok": true,
      "detail": []
    },
    {
      "name": "clone_is_not_production_alias",
      "ok": true,
      "detail": {
        "production": "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-13/quality/work/tmp/reviewer/test_real_date_parent_rehearsa0/real-date-rehearsal/baseline.duckdb",
        "clone": "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-13/quality/work/tmp/reviewer/test_real_date_parent_rehearsa0/real-date-rehearsal/copy.duckdb"
      }
    },
    {
      "name": "production_sha256_before",
      "ok": true,
      "detail": {
        "expected": "4c2d1b7e53770e9d",
        "actual": "4c2d1b7e53770e9d"
      }
    },
    {
      "name": "receipt_apply_readable",
      "ok": true,
      "detail": ""
    },
    {
      "name": "receipt_verify_readable",
      "ok": true,
      "detail": ""
    },
    {
      "name": "receipts_apply_verify_present",
      "ok": true,
      "detail": [
        "apply",
        "verify"
      ]
    },
    {
      "name": "receipt_apply_schema",
      "ok": true,
      "detail": []
    },
    {
      "name": "receipt_verify_schema",
      "ok": true,
      "detail": []
    },
    {
      "name": "receipt_apply_child_report_file",
      "ok": true,
      "detail": "与父收据嵌入子报告深比较"
    },
    {
      "name": "receipt_verify_child_report_file",
      "ok": true,
      "detail": "与父收据嵌入子报告深比较"
    },
    {
      "name": "backup_apply_identity",
      "ok": true,
      "detail": {
        "expected": "4c2d1b7e53770e9d",
        "actual": "4c2d1b7e53770e9d"
      }
    },
    {
      "name": "backup_verify_identity",
      "ok": true,
      "detail": {
        "expected": "449596bedc9062ad",
        "actual": "449596bedc9062ad"
      }
    },
    {
      "name": "backup_apply_matches_baseline",
      "ok": true,
      "detail": "apply 备份 sha == 基线 sha（换库前生产身份）"
    },
    {
      "name": "spec_alignment_apply_verify",
      "ok": true,
      "detail": "apply/verify 授权 spec 深比较（同输入同合同前提）"
    },
    {
      "name": "parquet_readable",
      "ok": true,
      "detail": "51f9ee9cba1ceb4a"
    },
    {
      "name": "parquet_identity_apply",
      "ok": true,
      "detail": {
        "spec": "51f9ee9cba1ceb4a",
        "actual": "51f9ee9cba1ceb4a"
      }
    },
    {
      "name": "parquet_identity_verify",
      "ok": true,
      "detail": {
        "spec": "51f9ee9cba1ceb4a",
        "actual": "51f9ee9cba1ceb4a"
      }
    },
    {
      "name": "fact_other_stocks_allcols",
      "ok": true,
      "detail": ""
    },
    {
      "name": "retained_rows_full_column_identical",
      "ok": true,
      "detail": {
        "rows": 10,
        "expected": 10
      }
    },
    {
      "name": "target_outside_window_allcols",
      "ok": true,
      "detail": [
        0,
        0
      ]
    },
    {
      "name": "hithink_source_untouched",
      "ok": true,
      "detail": ""
    },
    {
      "name": "hithink_adjustment_untouched",
      "ok": true,
      "detail": ""
    },
    {
      "name": "parallel_source_md5_binding",
      "ok": true,
      "detail": {
        "recomputed": "2ddb4224900b3b8e30a85ac0c9b89ffc",
        "rows": 62,
        "apply": "2ddb4224900b3b8e30a85ac0c9b89ffc",
        "verify": "2ddb4224900b3b8e30a85ac0c9b89ffc"
      }
    },
    {
      "name": "keyset_fullfield_oracle",
      "ok": false,
      "detail": {
        "rows": 54,
        "keys": 54,
        "bad": [
          "2026-06-17"
        ]
      }
    },
    {
      "name": "technical_protected_allcols",
      "ok": true,
      "detail": ""
    },
    {
      "name": "window_protected_allcols",
      "ok": true,
      "detail": ""
    },
    {
      "name": "window_golden_triples",
      "ok": true,
      "detail": {
        "actual": 161,
        "golden": 161
      }
    },
    {
      "name": "expected_window_counts_match_golden",
      "ok": true,
      "detail": {
        "golden": {
          "5": 59,
          "10": 54,
          "20": 44,
          "60": 4
        },
        "spec": {
          "5": 59,
          "10": 54,
          "20": 44,
          "60": 4
        }
      }
    },
    {
      "name": "technical_exact_set",
      "ok": true,
      "detail": 39
    },
    {
      "name": "expected_technical_count_matches_calendar",
      "ok": true,
      "detail": {
        "spec": 39,
        "calendar": 39
      }
    },
    {
      "name": "pinned_technical_target_day",
      "ok": true,
      "detail": [
        59.8542,
        2.6845,
        61.9052,
        2.45
      ]
    },
    {
      "name": "pinned_windows_target_day",
      "ok": true,
      "detail": ""
    },
    {
      "name": "market_daily_untouched",
      "ok": true,
      "detail": ""
    },
    {
      "name": "production_sha256_after",
      "ok": true,
      "detail": {
        "expected": "4c2d1b7e53770e9d",
        "actual": "4c2d1b7e53770e9d"
      }
    }
  ],
  "failed": [
    "keyset_fullfield_oracle"
  ]
}

```


## work/tmp/reviewer/test_real_date_parent_rehearsa0/real-date-rehearsal/acceptance.command.json
```text
{
  "label": "acceptance",
  "argv": [
    "/Users/a77/finance-workspace-private/.venv-workbench/bin/python",
    "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-13/candidate/scripts/verify_302132_backfill_acceptance.py",
    "--production",
    "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-13/quality/work/tmp/reviewer/test_real_date_parent_rehearsa0/real-date-rehearsal/baseline.duckdb",
    "--clone",
    "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-13/quality/work/tmp/reviewer/test_real_date_parent_rehearsa0/real-date-rehearsal/copy.duckdb",
    "--parquet",
    "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-13/quality/work/tmp/reviewer/test_real_date_parent_rehearsa0/real-date-rehearsal/frozen.parquet",
    "--run-apply",
    "9bee09824f80",
    "--run-verify",
    "207d080f1b09",
    "--expected-revision",
    "f650d9e765e127c7e66a621226cc2d676d70075d",
    "--expected-production-sha256",
    "4c2d1b7e53770e9daead4af503e466a815d371294c22b3b4b6909fdd4da2ca26",
    "--output",
    "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-13/quality/work/tmp/reviewer/test_real_date_parent_rehearsa0/real-date-rehearsal/acceptance.json"
  ],
  "expected_exit": 0,
  "exit_code": 0,
  "seconds": 0.628
}

```


## work/tmp/reviewer/test_real_date_parent_rehearsa0/real-date-rehearsal/amount-control.command.json
```text
{
  "label": "amount-control",
  "argv": [
    "/Users/a77/finance-workspace-private/.venv-workbench/bin/python",
    "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-13/candidate/scripts/verify_302132_backfill_acceptance.py",
    "--production",
    "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-13/quality/work/tmp/reviewer/test_real_date_parent_rehearsa0/real-date-rehearsal/baseline.duckdb",
    "--clone",
    "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-13/quality/work/tmp/reviewer/test_real_date_parent_rehearsa0/real-date-rehearsal/copy.duckdb",
    "--parquet",
    "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-13/quality/work/tmp/reviewer/test_real_date_parent_rehearsa0/real-date-rehearsal/frozen.parquet",
    "--run-apply",
    "9bee09824f80",
    "--run-verify",
    "207d080f1b09",
    "--expected-revision",
    "f650d9e765e127c7e66a621226cc2d676d70075d",
    "--expected-production-sha256",
    "4c2d1b7e53770e9daead4af503e466a815d371294c22b3b4b6909fdd4da2ca26",
    "--output",
    "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-13/quality/work/tmp/reviewer/test_real_date_parent_rehearsa0/real-date-rehearsal/amount-control.json"
  ],
  "expected_exit": 2,
  "exit_code": 2,
  "seconds": 0.819
}

```


## work/tmp/reviewer/test_real_date_parent_rehearsa0/real-date-rehearsal/apply.command.json
```text
{
  "label": "apply",
  "argv": [
    "/Users/a77/finance-workspace-private/.venv-workbench/bin/python",
    "-m",
    "market_feature_store.cli",
    "repair-backfill-302132",
    "--parquet",
    "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-13/quality/work/tmp/reviewer/test_real_date_parent_rehearsa0/real-date-rehearsal/frozen.parquet"
  ],
  "expected_exit": 0,
  "exit_code": 0,
  "seconds": 1.861
}

```


## work/tmp/reviewer/test_real_date_parent_rehearsa0/real-date-rehearsal/refused-parent.command.json
```text
{
  "label": "refused-parent",
  "argv": [
    "/Users/a77/finance-workspace-private/.venv-workbench/bin/python",
    "-m",
    "market_feature_store.cli",
    "repair-backfill-302132",
    "--parquet",
    "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-13/quality/work/tmp/reviewer/test_real_date_parent_rehearsa0/real-date-rehearsal/wrong.parquet"
  ],
  "expected_exit": 2,
  "exit_code": 2,
  "seconds": 0.65
}

```


## work/tmp/reviewer/test_real_date_parent_rehearsa0/real-date-rehearsal/verify.command.json
```text
{
  "label": "verify",
  "argv": [
    "/Users/a77/finance-workspace-private/.venv-workbench/bin/python",
    "-m",
    "market_feature_store.cli",
    "repair-backfill-302132",
    "--parquet",
    "/Users/a77/.finance-runtime/reviews/pr813-glm-qc-20260925-13/quality/work/tmp/reviewer/test_real_date_parent_rehearsa0/real-date-rehearsal/frozen.parquet"
  ],
  "expected_exit": 0,
  "exit_code": 0,
  "seconds": 1.454
}

```
