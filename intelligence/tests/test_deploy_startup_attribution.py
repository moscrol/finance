"""Port attribution must preserve events and fail closed on changed evidence."""

from __future__ import annotations

import hashlib
import json

import pytest

from intelligence.runtime import deploy_ledger as ledger
from scripts import audit_deploy_ledger as cli


@pytest.fixture
def case(tmp_path):
    path = tmp_path / "ledger.jsonl"
    production = ledger.build_row(action="switch", rev="a" * 40, port=8792, unix=1000)
    startup = ledger.build_row(
        action="startup",
        rev="b" * 40,
        port=None,
        pid=42,
        snapshot_path="/example/intelligence",
        unix=1100,
        argv=["capture-sidecar.py", "8817"],
    )
    ledger.append_row(path, production)
    ledger.append_row(path, startup)
    log = tmp_path / "sidecar.log"
    log.write_text(
        "INFO:     Started server process [42]\n"
        "INFO:     Uvicorn running on http://127.0.0.1:8817 (Press CTRL+C to quit)\n"
    )
    health = tmp_path / "health.json"
    health.write_text(
        json.dumps(
            {
                "status": "healthy",
                "timestamp": ledger.utc_now_iso(1101),
                "runtime": {
                    "source_revision": "b" * 40,
                    "loaded_code_root": "/example/intelligence",
                },
            }
        )
    )
    return path, startup, log, health


def options(case):
    path, startup, log, health = case
    return dict(
        ledger_path=path,
        target_sha256=ledger.startup_row_sha256(startup),
        port=8817,
        server_log={
            "path": str(log),
            "sha256": hashlib.sha256(log.read_bytes()).hexdigest(),
        },
        health_snapshot={
            "path": str(health),
            "sha256": hashlib.sha256(health.read_bytes()).hexdigest(),
        },
        reason="Bound PID, listening port, revision, root and capture time",
    )


def test_append_only_dry_run_apply_and_idempotency(case):
    path, startup, _, _ = case
    original = path.read_bytes()
    report = ledger.attribute_startup_port(**options(case), apply=False)
    assert report["applied"] is False
    assert path.read_bytes() == original
    assert not ledger.check_against_health(
        path, {"runtime": {"source_revision": "a" * 40}}, port=8792
    )["ok"]
    assert ledger.attribute_startup_port(**options(case), apply=True)["applied"] is True
    after = path.read_bytes()
    assert after.startswith(original)
    assert len(after.splitlines()) == 3
    assert ledger.read_rows(path)[1] == startup
    assert ledger.last_relevant_row(path, port=8792)["rev"] == "a" * 40
    attributed = ledger.last_relevant_row(path, port=8817)
    assert attributed["rev"] == "b" * 40
    assert attributed["recorded_port"] is None
    assert attributed["port_attribution_sha256"]
    assert (
        ledger.attribute_startup_port(**options(case), apply=True)["already_recorded"]
        is True
    )
    assert path.read_bytes() == after
    assert ledger.last_relevant_row(path)["rev"] == "b" * 40


@pytest.mark.parametrize("changed", ["log", "health", "missing"])
def test_changed_or_missing_evidence_restores_ambiguity(case, changed):
    path, _, log, health = case
    ledger.attribute_startup_port(**options(case), apply=True)
    if changed == "missing":
        log.unlink()
    else:
        (log if changed == "log" else health).write_text("changed")
    result = ledger.check_against_health(
        path, {"runtime": {"source_revision": "a" * 40}}, port=8792
    )
    assert result["ok"] is False
    assert result["reason"] == "rev_mismatch"
    assert ledger.last_relevant_row(path, port=8792)["port"] is None


@pytest.mark.parametrize(
    "bad",
    [
        "hash",
        "pid",
        "port",
        "multi_process",
        "multi_bind",
        "rev",
        "root",
        "time",
        "naive_time",
        "reason",
        "bool_port",
        "zero_port",
        "big_port",
        "target",
        "known_port",
        "switch",
        "duplicate",
    ],
)
def test_invalid_proof_never_writes(case, bad):
    path, startup, log, health = case
    payload = json.loads(health.read_text())
    if bad == "pid":
        log.write_text(log.read_text().replace("[42]", "[43]"))
    if bad == "port":
        log.write_text(log.read_text().replace(":8817", ":8818"))
    if bad == "multi_process":
        log.write_text(log.read_text() + "INFO:     Started server process [43]\n")
    if bad == "multi_bind":
        log.write_text(
            log.read_text()
            + "INFO:     Uvicorn running on http://127.0.0.1:8792 (Press CTRL+C to quit)\n"
        )
    if bad == "rev":
        payload["runtime"]["source_revision"] = "c" * 40
    if bad == "root":
        payload["runtime"]["loaded_code_root"] = "/other/intelligence"
    if bad == "time":
        payload["timestamp"] = ledger.utc_now_iso(1500)
    if bad == "naive_time":
        payload["timestamp"] = "1970-01-01T00:18:21"
    health.write_text(json.dumps(payload))
    if bad in {"known_port", "switch"}:
        startup["port" if bad == "known_port" else "action"] = (
            8792 if bad == "known_port" else "switch"
        )
        path.write_text(json.dumps(startup) + "\n")
    if bad == "duplicate":
        ledger.append_row(path, startup)
    args = options(case)
    if bad == "hash":
        args["server_log"]["sha256"] = "0" * 64
    if bad == "reason":
        args["reason"] = " "
    if bad in {"bool_port", "zero_port", "big_port"}:
        args["port"] = {"bool_port": True, "zero_port": 0, "big_port": 65536}[bad]
    if bad == "target":
        args["target_sha256"] = "0" * 64
    before = path.read_bytes()
    with pytest.raises(ValueError):
        ledger.attribute_startup_port(**args, apply=True)
    assert path.read_bytes() == before


def test_conflicting_or_malformed_attribution_does_not_hide_unknown_startup(case):
    path, _, _, _ = case
    ledger.attribute_startup_port(**options(case), apply=True)
    bad = ledger.read_rows(path)[-1]
    bad["port"] = 8818
    ledger.append_row(path, bad)
    assert ledger.last_relevant_row(path, port=8792)["port"] is None
    with pytest.raises(ValueError):
        ledger.attribute_startup_port(**options(case), apply=True)


@pytest.mark.parametrize(
    "damage",
    [
        "early_claim",
        "duplicate_target",
        "bad_schema",
        "missing_reference",
        "malformed_health",
    ],
)
def test_reader_rejects_invalid_attribution(case, damage):
    path, startup, _, health = case
    ledger.attribute_startup_port(**options(case), apply=True)
    rows = ledger.read_rows(path)
    if damage == "early_claim":
        rows = [rows[-1], *rows[:-1]]
    elif damage == "duplicate_target":
        rows.append(startup)
    elif damage == "bad_schema":
        rows[-1]["schema_version"] = "unknown/v2"
    elif damage == "missing_reference":
        rows[-1].pop("server_log")
    else:
        health.write_text("[]")
        rows[-1]["health_snapshot"]["sha256"] = hashlib.sha256(
            health.read_bytes()
        ).hexdigest()
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))
    assert ledger.last_relevant_row(path, port=8792)["port"] is None


def test_attribution_survives_ledger_migration_without_new_event_authority(
    case, tmp_path
):
    path, _, _, _ = case
    ledger.attribute_startup_port(**options(case), apply=True)
    new = tmp_path / "new-ledger.jsonl"
    ledger.merge_ledgers([path], new, apply=True)
    assert ledger.last_relevant_row(new, port=8792)["rev"] == "a" * 40
    assert ledger.last_relevant_row(new, port=8817)["rev"] == "b" * 40


@pytest.mark.parametrize(
    "capture_time,valid",
    [(1100, True), (1099, False), (1100.2, False), (1400.6, True), (1400.7, False)],
)
def test_health_seconds_precision_and_window_edges(case, capture_time, valid):
    path, startup, _, health = case
    startup["ts"] = ledger.utc_now_iso(1100.6)
    startup["unix"] = 1100.6
    path.write_text(json.dumps(startup) + "\n")
    payload = json.loads(health.read_text())
    payload["timestamp"] = ledger.utc_now_iso(capture_time)
    health.write_text(json.dumps(payload))
    if valid:
        assert ledger.attribute_startup_port(**options(case), apply=True)["applied"]
    else:
        with pytest.raises(ValueError):
            ledger.attribute_startup_port(**options(case), apply=True)


def test_later_production_startup_keeps_chronological_authority(case):
    path, _, _, _ = case
    ledger.append_row(
        path, ledger.build_row(action="startup", rev="c" * 40, port=8792, unix=1200)
    )
    ledger.attribute_startup_port(**options(case), apply=True)
    assert ledger.last_relevant_row(path, port=8792)["rev"] == "c" * 40
    assert ledger.last_relevant_row(path)["rev"] == "c" * 40


def test_unattributed_startup_and_switch_still_block(case):
    path, _, _, _ = case
    ledger.attribute_startup_port(**options(case), apply=True)
    for action in ("startup", "switch"):
        ledger.append_row(
            path, ledger.build_row(action=action, rev="d" * 40, port=None, unix=1200)
        )
        assert ledger.last_relevant_row(path, port=8792)["rev"] == "d" * 40


def test_cli_and_homes_use_same_resolved_rows(case, monkeypatch, capsys):
    path, _, log, health = case
    opts = options(case)
    args = [
        "attribute-startup",
        "--ledger",
        str(path),
        "--target-sha256",
        opts["target_sha256"],
        "--port",
        "8817",
        "--server-log",
        str(log),
        "--server-log-sha256",
        opts["server_log"]["sha256"],
        "--health-snapshot",
        str(health),
        "--health-sha256",
        opts["health_snapshot"]["sha256"],
        "--reason",
        "verified preserved sidecar evidence",
    ]
    assert cli.main(args) == 0
    assert len(ledger.read_rows(path)) == 2
    assert cli.main([*args, "--apply"]) == 0
    monkeypatch.setattr(
        cli, "fetch_health", lambda url: {"runtime": {"source_revision": "a" * 40}}
    )
    assert cli.main(["check", "--ledger", str(path)]) == 0
    assert cli._summarize(path, 8792)["last_startup"] is None
    assert cli._summarize(path, 8817)["last_startup"]["rev"] == "b" * 12
    assert cli._summarize(path, 8792)["rows"] == 3
    assert "traceback" not in capsys.readouterr().out.lower()
