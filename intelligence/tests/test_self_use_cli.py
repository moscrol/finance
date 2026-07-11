from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from intelligence import cli, userspace
from intelligence.services.self_use_maturity import SelfUseEvent, SelfUseLedger


def _record_args(ledger, *extra: str) -> list[str]:
    return [
        "self-use",
        "record",
        "--ledger",
        str(ledger),
        "--date",
        "2026-07-11",
        "--workflow",
        "daily_market",
        "--outcome",
        "success",
        "--useful",
        *extra,
    ]


def _complete_ledger(path) -> None:
    workflows = (
        "daily_market",
        "theme_research",
        "stock_research",
        "news_impact",
        "watchlist",
    )
    ledger = SelfUseLedger(path)
    for day in range(1, 11):
        for workflow in workflows:
            ledger.record(
                SelfUseEvent(
                    trade_date=f"2026-06-{day:02d}",
                    workflow=workflow,  # type: ignore[arg-type]
                    outcome="success",
                    manual_rescue=False,
                    severe_fact_error=False,
                    useful=True,
                )
            )


def test_record_then_status_json_with_explicit_ledger(tmp_path, capsys) -> None:
    ledger = tmp_path / "events.jsonl"

    assert cli.main(_record_args(ledger, "--run-id", "run-1", "--note", "helpful")) == 0
    recorded = json.loads(capsys.readouterr().out)
    assert recorded["run_id"] == "run-1"
    assert recorded["note"] == "helpful"

    assert cli.main(["self-use", "status", "--ledger", str(ledger), "--json"]) == 1
    result = json.loads(capsys.readouterr().out)
    assert result["metrics"]["event_count"] == 1
    assert result["passed"] is False


def test_record_preserves_manual_severe_and_not_useful_flags(tmp_path, capsys) -> None:
    ledger = tmp_path / "events.jsonl"
    args = _record_args(ledger)
    args[args.index("--useful")] = "--not-useful"
    args.extend(["--manual-rescue", "--severe-fact-error"])

    assert cli.main(args) == 0
    capsys.readouterr()

    event = SelfUseLedger(ledger).load()[0]
    assert event.manual_rescue is True
    assert event.severe_fact_error is True
    assert event.useful is False


def test_invalid_workflow_is_rejected_by_argparse(tmp_path) -> None:
    parser = cli.build_parser()
    args = _record_args(tmp_path / "events.jsonl")
    args[args.index("daily_market")] = "freeform"

    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(args)

    assert exc_info.value.code == 2


def test_status_user_approval_cannot_bypass_mechanical_gate(tmp_path, capsys) -> None:
    ledger = tmp_path / "events.jsonl"
    assert cli.main(_record_args(ledger)) == 0
    capsys.readouterr()

    assert (
        cli.main(
            [
                "self-use",
                "status",
                "--ledger",
                str(ledger),
                "--json",
                "--user-approved",
            ]
        )
        == 1
    )
    result = json.loads(capsys.readouterr().out)
    assert result["user_approved"] is True
    assert result["eligible_for_user_decision"] is False
    assert result["passed"] is False


def test_status_passes_only_with_complete_gate_and_explicit_approval(
    tmp_path, capsys
) -> None:
    ledger = tmp_path / "events.jsonl"
    _complete_ledger(ledger)

    assert cli.main(["self-use", "status", "--ledger", str(ledger), "--json"]) == 1
    capsys.readouterr()
    assert (
        cli.main(
            [
                "self-use",
                "status",
                "--ledger",
                str(ledger),
                "--json",
                "--user-approved",
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["passed"] is True


def test_plain_status_reports_required_summary(tmp_path, capsys) -> None:
    ledger = tmp_path / "events.jsonl"
    assert cli.main(_record_args(ledger)) == 0
    capsys.readouterr()

    assert cli.main(["self-use", "status", "--ledger", str(ledger)]) == 1
    output = capsys.readouterr().out
    assert "1/10" in output
    assert "workflow 1/5" in output
    assert "blockers" in output
    assert "passed: false" in output


def test_status_malformed_ledger_returns_two_and_writes_stderr(
    tmp_path, capsys
) -> None:
    ledger = tmp_path / "events.jsonl"
    ledger.write_text('{"workflow": ', encoding="utf-8")

    assert cli.main(["self-use", "status", "--ledger", str(ledger), "--json"]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "invalid self-use ledger" in captured.err


def test_status_os_error_returns_two_and_writes_stderr(
    tmp_path, monkeypatch, capsys
) -> None:
    def fail_load(_self):
        raise OSError("simulated read failure")

    monkeypatch.setattr(SelfUseLedger, "load", fail_load)

    assert (
        cli.main(
            ["self-use", "status", "--ledger", str(tmp_path / "events.jsonl")]
        )
        == 2
    )
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "simulated read failure" in captured.err


def test_default_ledger_uses_user_space_root(tmp_path, monkeypatch, capsys) -> None:
    root = tmp_path / "private-user"
    seen: list[str | None] = []

    def fake_user_space(user: str | None):
        seen.append(user)
        return SimpleNamespace(root=root)

    monkeypatch.setattr(userspace, "user_space", fake_user_space)

    args = _record_args(tmp_path / "unused.jsonl", "--user", "alice")
    ledger_index = args.index("--ledger")
    del args[ledger_index : ledger_index + 2]
    assert cli.main(args) == 0
    capsys.readouterr()

    assert seen == ["alice"]
    assert (root / "self-use" / "events.jsonl").exists()
