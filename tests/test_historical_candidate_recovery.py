"""Fixed historical gap preparation: synthetic inputs and guarded child writes."""
from dataclasses import replace
from datetime import datetime
import hashlib
import json
from pathlib import Path

import duckdb
import pytest

from market_feature_store import db
from market_feature_store.hithink_recovery_candidate import RecoverySpec, build_candidate, scope_fingerprint
from market_feature_store.sync.sync_mootdx_stock_daily import COLS
from scripts import historical_candidate_recovery as candidate
from scripts import recover_local_review as recovery
from tests.test_hithink_recovery_candidate import CODE, PREV, RESUME, TD, add_resumption, bar, quote


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def prepared(tmp_path, monkeypatch):
    inputs = {"spec": RecoverySpec(TD, scope_fingerprint(TD, [CODE]), (), (), ()),
              "stock_codes": [CODE], "bars": [bar(day=PREV, close=10.), bar()],
              "actions": [], "quotes": {CODE: quote()}, "suspensions": [], "historical_witnesses": []}
    add_resumption(inputs)
    spec = inputs.pop("spec")
    result = build_candidate(spec, **inputs)
    monkeypatch.setattr(candidate, "CANDIDATE_20260921", spec)
    monkeypatch.setattr(candidate, "FIXED_INPUT_FINGERPRINT", result["input_fingerprint"])
    monkeypatch.setattr(candidate, "FIXED_CANDIDATE_FINGERPRINT", result["candidate_fingerprint"])
    data = tmp_path / "inputs.json"
    data.write_text(json.dumps(inputs, default=str))
    row = {**result["rows"][0], "trade_date": TD, "stock_name": "Existing Name",
           "turnover": 7.5, "source": "original-source", "updated_at": datetime(2026, 9, 22)}
    existing = [tuple(row[column] for column in COLS)]
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"contract_version": candidate.CONTRACT, "trade_date": str(TD),
        "inputs": {"path": "inputs.json", "sha256": digest(data)}, "missing_codes": [RESUME],
        "existing_rows_sha256": candidate.rows_fingerprint(existing)}))
    return manifest, candidate.load_manifest(manifest, digest(manifest)), existing


def test_rebuilds_fixed_candidate_and_preserves_existing_metadata(prepared):
    _, day, existing = prepared
    additions = candidate.plan_missing_rows(day, existing)
    assert len(additions) == 1 and additions[0][1] == RESUME
    assert additions[0][COLS.index("turnover")] is None
    assert additions[0][COLS.index("source")] == "hithink:daily-k-10d"
    assert day.evidence["production_ready"] is False
    assert day.evidence["coverage"]["declared_count"] == 2
    assert day.evidence["coverage"]["official_historical_universe_verified"] is False
    assert existing[0][COLS.index("stock_name")] == "Existing Name"
    assert existing[0][COLS.index("turnover")] == 7.5


@pytest.mark.parametrize("field", COLS)
def test_preimage_pins_every_existing_column(prepared, field):
    _, day, existing = prepared
    row = list(existing[0])
    row[COLS.index(field)] = "changed"
    with pytest.raises(ValueError, match="preimage changed"):
        candidate.plan_missing_rows(day, [tuple(row)])


@pytest.mark.parametrize("field", candidate.NUMERIC_FIELDS)
def test_repinning_existing_numbers_does_not_make_conflicts_acceptable(prepared, field):
    _, day, existing = prepared
    row = list(existing[0])
    row[COLS.index(field)] += .01
    changed = [tuple(row)]
    day = replace(day, existing_sha256=candidate.rows_fingerprint(changed))
    with pytest.raises(ValueError, match="numeric value differs"):
        candidate.plan_missing_rows(day, changed)


@pytest.mark.parametrize("case", ["extra", "duplicate", "already_present", "empty", "wrong_day"])
def test_missing_identity_and_day_are_exact_not_a_count(prepared, case):
    _, day, existing = prepared
    if case == "extra":
        row = list(existing[0])
        row[1] = "600999.SH"
        changed = [*existing, tuple(row)]
    elif case == "duplicate":
        changed = existing * 2
    elif case == "already_present":
        changed = list(day.rows)
    elif case == "wrong_day":
        row = list(existing[0])
        row[0] = TD.replace(day=22)
        changed = [tuple(row)]
    else:
        changed = []
    day = replace(day, existing_sha256=candidate.rows_fingerprint(changed))
    with pytest.raises(ValueError, match="historical row|fixed gaps"):
        candidate.plan_missing_rows(day, changed)


@pytest.mark.parametrize("file", ["manifest.json", "inputs.json"])
def test_bound_bytes_cannot_change(prepared, file):
    manifest, _, _ = prepared
    pin = digest(manifest)
    with (manifest.parent / file).open("ab") as stream:
        stream.write(b"\n")
    with pytest.raises(ValueError, match="hash changed"):
        candidate.load_manifest(manifest, pin)


@pytest.mark.parametrize("mutation", ["date", "contract", "gaps", "fingerprint", "schema"])
def test_manifest_cannot_generalize_the_fixed_proposal(prepared, mutation):
    path, _, _ = prepared
    manifest = json.loads(path.read_text())
    if mutation == "date":
        manifest["trade_date"] = "2026-09-22"
    elif mutation == "contract":
        manifest["contract_version"] = "other"
    elif mutation == "gaps":
        manifest["missing_codes"] = [CODE]
    else:
        data = path.parent / "inputs.json"
        payload = json.loads(data.read_text())
        if mutation == "schema":
            payload["unexpected"] = True
        else:
            payload["bars"][0]["updated_at"] = "2026-09-23 00:00:00"
        data.write_text(json.dumps(payload))
        manifest["inputs"]["sha256"] = digest(data)
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        candidate.load_manifest(path, digest(path))


def test_real_child_preserves_every_existing_field_and_never_signs_publication(prepared, tmp_path, monkeypatch):
    manifest, day, existing = prepared
    output = tmp_path / "isolated"
    output.mkdir()
    target = output / "source.duckdb.staging"
    with duckdb.connect(str(target)) as con:
        db.init_db(con)
        con.execute(f'INSERT INTO fact_stock_daily ({", ".join(COLS)}) '
                    f'VALUES ({", ".join("?" for _ in COLS)})', existing[0])
    monkeypatch.setattr(db, "DB_PATH", target)
    monkeypatch.setenv("MARKET_FEATURE_STORE_RUN_ID", "synthetic-run")
    monkeypatch.setenv("MARKET_FEATURE_STORE_DB", str(target))
    args = recovery.argparse.Namespace(prepare_dir=output, candidate_manifest=manifest,
        candidate_manifest_sha256=digest(manifest))
    assert recovery.child(args) == 2
    status = json.loads(Path(str(target) + ".status.json").read_text())
    assert status["run_id"] == "synthetic-run" and status["ok"] is False
    assert status["input_prepared"] is True and status["quality_gates_attempted"] is False
    assert status["publication_attempted"] is False
    assert status["steps"][0]["written_rows"] == status["steps"][0]["preserved_rows"] == 1
    with duckdb.connect(str(target), read_only=True) as con:
        rows = con.execute(f'SELECT {", ".join(COLS)} FROM fact_stock_daily ORDER BY stock_ts_code').fetchall()
        assert rows[0] == existing[0]
        assert rows[1][1] == RESUME and rows[1][COLS.index("turnover")] is None
        assert con.execute("SELECT count(*) FROM fact_market_daily").fetchone()[0] == 0
    before = candidate.rows_fingerprint(rows)
    with pytest.raises(ValueError, match="preimage changed"):
        recovery.child(args)
    with duckdb.connect(str(target), read_only=True) as con:
        assert candidate.rows_fingerprint(con.execute(
            f'SELECT {", ".join(COLS)} FROM fact_stock_daily').fetchall()) == before


@pytest.mark.parametrize("extra", [[], ["--prepare-dir", "unused", "--quote-manifest", "other"],
                                    ["--prepare-dir", "unused", "--history-day", "2026-09-21"]])
def test_parent_requires_explicit_prepare_only_and_no_mixed_modes(tmp_path, extra):
    with pytest.raises(SystemExit) as exc:
        recovery.main(["--candidate-manifest", "unused", "--candidate-manifest-sha256", "0" * 64,
                       "--receipt", str(tmp_path / "receipt.json"), *extra])
    assert exc.value.code == 2
    assert list(tmp_path.iterdir()) == []
