"""Synthetic offline recovery inputs and a real guarded staging child."""
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import sys

import duckdb
import pytest

from market_feature_store import db
from scripts import recover_local_review as recovery
from scripts.dated_quote_recovery import CONTRACT, SOURCE, load_manifest
from tests.test_audit_dated_quote_capture import DAY, quote


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def event(code="600002.SH", **changes):
    return {"SECUCODE": code, "SECURITY_CODE": code[:6], "SECURITY_TYPE_CODE": "058001001",
            "SUSPEND_START_TIME": "2026-09-21 09:30:00", "SUSPEND_END_TIME": None, **changes}


def fixture_inputs(tmp_path, *, raw=None, captured=None, declared=None, events=None):
    captured = captured or ["600001.SH"]
    directory = tmp_path / "capture"
    directory.mkdir()
    (directory / "batch.raw").write_bytes(quote() if raw is None else raw)
    receipt = {"target_date": str(DAY), "codes": captured, "captured_code_count": len(captured),
               "batches": [{"file": "batch.raw", "sha256": digest(directory / "batch.raw"),
                            "codes": captured, "http_status": 200}]}
    (directory / "receipt.json").write_text(json.dumps(receipt))
    events = [event()] if events is None else events
    reference = tmp_path / "suspensions.json"
    reference.write_text(json.dumps({"success": True, "code": 0,
                                    "result": {"pages": 1, "count": len(events), "data": events}}))
    manifest = {"contract_version": CONTRACT, "days": [{
        "trade_date": str(DAY), "scope_basis": "synthetic declared scope, not official universe",
        "declared_codes": declared or ["600001.SH", "600002.SH"],
        "captures": [{"directory": "capture", "receipt_sha256": digest(directory / "receipt.json")}],
        "suspensions": {"path": "suspensions.json", "sha256": digest(reference)},
    }]}
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest))
    return path


def replace_manifest(path, mutate):
    payload = json.loads(path.read_text())
    mutate(payload)
    path.write_text(json.dumps(payload))


def test_preparation_preserves_scope_source_units_and_nontrading_identities(tmp_path):
    path = fixture_inputs(tmp_path)
    day, = load_manifest(path, digest(path))
    row, = day.rows
    assert row[:9] == (DAY, "600001.SH", "Example", 10, 10, 0, .001, None, SOURCE)
    assert isinstance(row[9], datetime)
    assert row[10:] == (10, 11, 9, 100)
    evidence = day.evidence
    assert evidence["coverage"]["declared_count"] == 2
    assert evidence["coverage"]["nontrading_count"] == 1
    assert evidence["breadth"]["unchanged_traded"] == 1
    assert evidence["breadth"]["nontrading_not_flat"] == 1
    assert evidence["synthetic_rows"] == 0
    assert evidence["turnover_contract"] == 'null_not_zero_not_carried_not_inferred'
    assert evidence["observations"] == [{"stock_ts_code": "600001.SH", "name_source": SOURCE,
                                        "name_observed_at": "20260921150001", "observed_turnover_pct": 1}]
    assert evidence["production_ready"] is False
    assert evidence["coverage"]["official_historical_universe_verified"] is False


def test_share_quotes_become_canonical_hands(tmp_path):
    path = fixture_inputs(tmp_path, raw=quote("sh688001", fields={6: "10001", 35: "10/10001/100010"}),
                          captured=["688001.SH"], declared=["688001.SH"], events=[])
    row = load_manifest(path, digest(path))[0].rows[0]
    assert row[-1] == 100.01 and row[6] == .0010001


def test_zero_quotes_excluded_without_creating_flat_bars(tmp_path):
    zero = quote("sh600002", fields={5: "0", 6: "0", 33: "0", 34: "0", 35: "10/0/0"})
    path = fixture_inputs(tmp_path, raw=quote() + zero, captured=["600001.SH", "600002.SH"])
    assert len(load_manifest(path, digest(path))[0].rows) == 1


@pytest.mark.parametrize("mutation", ["version", "scope", "duplicate_day", "holiday", "basis",
                                      "missing_stop", "extra_stop", "overlap", "receipt_pin"])
def test_manifest_contract_refuses_ambiguous_inputs(tmp_path, mutation):
    path = fixture_inputs(tmp_path)

    def mutate(manifest):
        day = manifest["days"][0]
        if mutation == "version":
            manifest["contract_version"] = "other"
        elif mutation == "scope":
            day["declared_codes"].append("200016.SZ")
        elif mutation == "duplicate_day":
            manifest["days"].append(day.copy())
        elif mutation == "holiday":
            day["trade_date"] = "2026-09-20"
        elif mutation == "basis":
            day["scope_basis"] = " "
        elif mutation == "missing_stop":
            day["declared_codes"].append("600003.SH")
        elif mutation == "extra_stop":
            day["declared_codes"].remove("600002.SH")
        elif mutation == "overlap":
            day["captures"] *= 2
        else:
            day["captures"][0]["receipt_sha256"] = "0" * 64
    replace_manifest(path, mutate)
    with pytest.raises(ValueError):
        load_manifest(path, digest(path))


@pytest.mark.parametrize("file", ["manifest.json", "suspensions.json", "capture/receipt.json", "capture/batch.raw"])
def test_each_bound_input_refuses_changed_bytes(tmp_path, file):
    path = fixture_inputs(tmp_path)
    pin = digest(path)
    with (tmp_path / file).open("ab") as handle:
        handle.write(b"\n")
    with pytest.raises(ValueError, match="hash changed"):
        load_manifest(path, pin)


@pytest.mark.parametrize("changes", [{32: "0.01"}, {1: "bad\x00name"}, {3: "10.001", 35: "10.001/100/100000"}])
def test_price_percentage_and_name_contracts(tmp_path, changes):
    path = fixture_inputs(tmp_path, raw=quote(fields=changes))
    with pytest.raises(ValueError):
        load_manifest(path, digest(path))


@pytest.mark.parametrize("changes", [{"SUSPEND_START_TIME": "2026-09-22 09:30:00"},
                                     {"SUSPEND_END_TIME": "2026-09-20 15:00:00"},
                                     {"SUSPEND_END_TIME": "2026-09-21 12:00:00"},
                                     {"SECURITY_CODE": "600003"},
                                     {"SECURITY_TYPE_CODE": "unknown"},
                                     {"SUSPEND_START_TIME": "2026-09-21T09:30:00+08:00"}])
def test_inapplicable_or_invalid_suspension_cannot_explain_a_missing_bar(tmp_path, changes):
    path = fixture_inputs(tmp_path, events=[event(**changes)])
    with pytest.raises(ValueError):
        load_manifest(path, digest(path))


def test_directory_excludes_b_shares_future_and_ended_events(tmp_path):
    events = [event(), event("200016.SZ", SECURITY_TYPE_CODE="058001002"),
              event("600003.SH", SUSPEND_START_TIME="2026-09-22 09:30:00"),
              event("600004.SH", SUSPEND_START_TIME="2026-09-18 09:30:00",
                    SUSPEND_END_TIME="2026-09-18 15:00:00")]
    path = fixture_inputs(tmp_path, events=events)
    evidence = load_manifest(path, digest(path))[0].evidence
    assert evidence["suspensions"]["applicable_codes"] == ["600002.SH"]
    assert evidence["suspensions"]["excluded_codes"] == ["200016.SZ", "600003.SH", "600004.SH"]


@pytest.mark.parametrize("changes", [{"success": False}, {"code": 9501},
                                     {"result": {"pages": 2, "data": [], "count": 0}}])
def test_http_200_or_partial_page_is_not_valid_suspension_evidence(tmp_path, changes):
    path = fixture_inputs(tmp_path)
    reference = tmp_path / "suspensions.json"
    payload = json.loads(reference.read_text())
    payload.update(changes)
    reference.write_text(json.dumps(payload))
    replace_manifest(path, lambda m: m["days"][0]["suspensions"].update(sha256=digest(reference)))
    with pytest.raises(ValueError, match="successful complete"):
        load_manifest(path, digest(path))


def test_observed_bar_and_full_day_suspension_cannot_overlap(tmp_path):
    path = fixture_inputs(tmp_path, events=[event(), event("600001.SH")])
    with pytest.raises(ValueError, match="partition"):
        load_manifest(path, digest(path))


@pytest.fixture
def preparation(tmp_path, monkeypatch):
    path = fixture_inputs(tmp_path)
    target = tmp_path / "source.duckdb"
    with duckdb.connect(str(target)) as con:
        db.init_db(con)
        con.execute("INSERT INTO fact_stock_daily (trade_date, stock_ts_code, close, source) "
                    "VALUES ('2026-09-18', '600001.SH', 9, 'original')")
    monkeypatch.setenv("FINANCE_WS", str(tmp_path))
    monkeypatch.setenv("FINANCE_LOCK_DIR", str(tmp_path / "locks"))
    monkeypatch.setenv("MARKET_FEATURE_STORE_DB", str(target))
    monkeypatch.setattr(db, "DB_PATH", target)
    monkeypatch.setattr(db, "DB_DIR", tmp_path)
    output, receipt = tmp_path / "prepared", tmp_path / "result.json"
    argv = ["--quote-manifest", str(path), "--quote-manifest-sha256", digest(path),
            "--prepare-dir", str(output), "--receipt", str(receipt)]
    return path, target, output, receipt, argv


def add_second_day(path):
    directory = path.parent / 'second-day'
    directory.mkdir()
    second = fixture_inputs(directory, raw=quote(fields={30: '20260922150001'}))
    receipt = directory / 'capture/receipt.json'
    payload = json.loads(receipt.read_text())
    payload['target_date'] = '2026-09-22'
    receipt.write_text(json.dumps(payload))
    day = json.loads(second.read_text())['days'][0]
    day['trade_date'] = '2026-09-22'
    day['captures'][0] = {'directory': str(receipt.parent), 'receipt_sha256': digest(receipt)}
    day['suspensions']['path'] = str(directory / 'suspensions.json')
    replace_manifest(path, lambda manifest: manifest['days'].append(day))


def test_real_child_prepares_rows_but_parent_never_publishes(preparation):
    _, target, output, receipt, argv = preparation
    before = digest(target)
    assert recovery.main(argv) == 2
    result = json.loads(receipt.read_text())
    assert result["swapped"] is False and result["backup"] is None
    assert result["input_prepared"] is True and result["child_returncode"] == 2
    assert result["status"]["ok"] is False
    assert result["status"]["quality_gates_attempted"] is False
    assert digest(target) == before
    with duckdb.connect(str(output / (target.name + ".staging")), read_only=True) as con:
        assert con.execute("SELECT close, source FROM fact_stock_daily ORDER BY trade_date").fetchall() == [
            (9, "original"), (10, SOURCE)]
        assert con.execute("SELECT count(*) FROM fact_market_daily").fetchone()[0] == 0
    assert not Path(str(target) + ".staging").exists()
    assert not Path(os.environ["FINANCE_LOCK_DIR"], "daily-full-review.lock").exists()


def test_multi_day_preparation_is_one_transaction_and_refuses_any_occupied_day(preparation):
    path, target, output, receipt, argv = preparation
    add_second_day(path)
    argv[argv.index('--quote-manifest-sha256') + 1] = digest(path)
    with duckdb.connect(str(target)) as con:
        con.execute("INSERT INTO fact_stock_daily (trade_date, stock_ts_code, close, source) "
                    "VALUES ('2026-09-22', '600003.SH', 8, 'original')")
    assert recovery.main(argv) == 2
    with duckdb.connect(str(output / (target.name + '.staging')), read_only=True) as con:
        assert con.execute("SELECT count(*) FROM fact_stock_daily WHERE source=?", [SOURCE]).fetchone()[0] == 0
    assert json.loads(receipt.read_text())['swapped'] is False


def test_multi_day_preparation_loads_both_dates_independently(preparation):
    path, target, output, receipt, argv = preparation
    add_second_day(path)
    argv[argv.index('--quote-manifest-sha256') + 1] = digest(path)
    before = digest(target)
    assert recovery.main(argv) == 2
    assert digest(target) == before
    result = json.loads(receipt.read_text())
    assert result['input_prepared'] is True and result['status']['steps'][0]['written_rows'] == 2
    with duckdb.connect(str(output / (target.name + '.staging')), read_only=True) as con:
        assert con.execute('SELECT trade_date::VARCHAR FROM fact_stock_daily WHERE source=? '
                           'ORDER BY trade_date', [SOURCE]).fetchall() == [('2026-09-21',), ('2026-09-22',)]


@pytest.mark.parametrize('alias', ['symlink', 'hardlink'])
def test_child_rejects_canonical_database_aliases_before_loading_inputs(preparation, monkeypatch, alias):
    path, target, output, receipt, argv = preparation
    output.mkdir()
    staging = output / 'aliased.duckdb.staging'
    if alias == 'symlink':
        staging.symlink_to(target)
    else:
        os.link(target, staging)
    monkeypatch.setenv('MARKET_FEATURE_STORE_PRODUCTION_DB', str(target))
    monkeypatch.setenv('MARKET_FEATURE_STORE_RUN_ID', 'synthetic-current-run')
    monkeypatch.setenv('MARKET_FEATURE_STORE_DB', str(staging))
    monkeypatch.setattr(db, 'DB_PATH', staging)
    before = digest(target)
    path.write_text('{}')
    with pytest.raises(RuntimeError, match='not a direct write'):
        recovery.main(argv + ['--child'])
    assert digest(target) == before and not receipt.exists()


def test_ordinary_publisher_cannot_promote_a_miswired_input_preparation_child(preparation):
    from market_feature_store.sync.sync_daily_full import run_daily_full_staged

    _, target, _, _, argv = preparation
    # Simulate a caller that forgot the publisher's prepare_dir keyword.
    argv[argv.index('--prepare-dir') + 1] = str(target.parent)
    command = [sys.executable, str(Path(recovery.__file__).resolve()), *argv, '--child']
    before = digest(target)
    result = run_daily_full_staged(child_argv=command)
    assert result['swapped'] is False
    assert result['rc'] == 2 and result['child_returncode'] == 2
    assert result['status']['input_prepared'] is True and result['status']['ok'] is False
    assert digest(target) == before


def test_bad_input_prevents_even_clone_or_lock(preparation):
    path, target, output, receipt, argv = preparation
    path.write_text("{}")
    before = digest(target)
    with pytest.raises(ValueError, match="hash changed"):
        recovery.main(argv)
    assert not output.exists() and not receipt.exists()
    assert digest(target) == before
    assert not Path(os.environ["FINANCE_LOCK_DIR"]).exists()


def test_existing_evidence_receipt_is_not_overwritten(preparation):
    _, target, output, receipt, argv = preparation
    receipt.write_text("old receipt")
    before = digest(target)
    with pytest.raises(FileExistsError):
        recovery.main(argv)
    assert receipt.read_text() == "old receipt" and not output.exists()
    assert digest(target) == before


def test_existing_target_day_refuses_before_any_insert(preparation):
    _, target, output, receipt, argv = preparation
    with duckdb.connect(str(target)) as con:
        con.execute("INSERT INTO fact_stock_daily (trade_date, stock_ts_code, close, source) "
                    "VALUES ('2026-09-21', '600003.SH', 8, 'original')")
    before = digest(target)
    assert recovery.main(argv) == 2
    assert digest(target) == before
    result = json.loads(receipt.read_text())
    assert result["swapped"] is False and result["child_returncode"] != 0
    with duckdb.connect(str(output / (target.name + ".staging")), read_only=True) as con:
        assert con.execute("SELECT count(*) FROM fact_stock_daily").fetchone()[0] == 2
        assert con.execute("SELECT count(*) FROM fact_stock_daily WHERE source=?", [SOURCE]).fetchone()[0] == 0


@pytest.mark.parametrize("extra", [["--snapshot-day", "2026-09-24"], ["--history", "unread"]])
def test_legacy_and_quote_options_cannot_mix(preparation, extra):
    _, _, output, receipt, argv = preparation
    with pytest.raises(SystemExit) as error:
        recovery.main(argv + extra)
    assert error.value.code == 2 and not output.exists() and not receipt.exists()
