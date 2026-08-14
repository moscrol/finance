from __future__ import annotations

import json
from dataclasses import asdict
from types import SimpleNamespace

import pytest

from intelligence import cli, userspace
from intelligence.services import run_store as run_store_module
from intelligence.services.run_store import RunStore
from intelligence.services.self_use_maturity import SelfUseEvent, SelfUseLedger

# 与 test_self_use_maturity 一致的 12 个连续 canonical 交易日。
CAL = [
    "2026-06-01",
    "2026-06-02",
    "2026-06-03",
    "2026-06-04",
    "2026-06-05",
    "2026-06-08",
    "2026-06-09",
    "2026-06-10",
    "2026-06-11",
    "2026-06-12",
    "2026-06-15",
    "2026-06-16",
]
TODAY = "2026-07-01"
WORKFLOWS = (
    "daily_market",
    "theme_research",
    "stock_research",
    "news_impact",
    "watchlist",
)


def _make_completed_run(run_root, run_id: str, *, llm_used: bool = True) -> None:
    store = RunStore("tester", root=run_root)
    run_dir = store.run_dir(run_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    payload = run_store_module.Run(
        run_id=run_id,
        user="tester",
        question="q",
        task_type="conversation",
        status=run_store_module.STATUS_COMPLETED,
    )
    (run_dir / "run.json").write_text(json.dumps(asdict(payload)), encoding="utf-8")
    report = {
        "report_id": run_id,
        "status": "completed",
        "as_of": "2026-06-01",
        "llm": {
            "used": llm_used,
            "provider": "zhipu",
            "model": "glm-5.2",
        },
    }
    (run_dir / "report.json").write_text(json.dumps(report), encoding="utf-8")
    store.append_stream_event(
        run_id, event_id="evt-1", event_type="answer", payload={"text": "ok"}
    )
    store.append_stream_event(
        run_id,
        event_id="report-complete",
        event_type="report.complete",
        payload={"report": report},
    )


def _cal_args(*days: str) -> list[str]:
    out: list[str] = []
    for day in days:
        out += ["--trading-day", day]
    out += ["--today", TODAY]
    return out


def _record_args(
    ledger, run_root, *extra: str, run_id: str = "run-1", date: str = "2026-06-01"
) -> list[str]:
    return [
        "self-use",
        "record",
        "--ledger",
        str(ledger),
        "--date",
        date,
        "--workflow",
        "daily_market",
        "--outcome",
        "success",
        "--useful",
        "--run-id",
        run_id,
        "--run-root",
        str(run_root),
        *_cal_args(date),
        *extra,
    ]


def _complete_ledger(path) -> None:
    ledger = SelfUseLedger(path)
    for day in range(10):
        for workflow in WORKFLOWS:
            ledger.record(
                SelfUseEvent(
                    trade_date=CAL[day],
                    workflow=workflow,  # type: ignore[arg-type]
                    outcome="success",
                    manual_rescue=False,
                    severe_fact_error=False,
                    useful=True,
                    run_id=f"run-{day}-{workflow}",
                )
            )


def test_record_then_status_json_with_explicit_ledger(tmp_path, capsys) -> None:
    ledger = tmp_path / "events.jsonl"
    run_root = tmp_path / "runs"
    _make_completed_run(run_root, "run-1")

    assert cli.main(_record_args(ledger, run_root, "--note", "helpful")) == 0
    recorded = json.loads(capsys.readouterr().out)
    assert recorded["run_id"] == "run-1"
    assert recorded["note"] == "helpful"

    assert (
        cli.main(
            ["self-use", "status", "--ledger", str(ledger), "--json", *_cal_args(*CAL)]
        )
        == 1
    )
    result = json.loads(capsys.readouterr().out)
    assert result["metrics"]["event_count"] == 1
    assert result["passed"] is False


def test_record_is_idempotent_for_duplicate_run_date_workflow(tmp_path, capsys) -> None:
    ledger = tmp_path / "events.jsonl"
    run_root = tmp_path / "runs"
    _make_completed_run(run_root, "run-1")

    assert cli.main(_record_args(ledger, run_root)) == 0
    capsys.readouterr()
    assert cli.main(_record_args(ledger, run_root)) == 0
    capsys.readouterr()

    assert len(SelfUseLedger(ledger).load()) == 1


def test_record_rejects_unbound_run(tmp_path, capsys) -> None:
    ledger = tmp_path / "events.jsonl"
    run_root = tmp_path / "runs"  # no run created

    assert cli.main(_record_args(ledger, run_root)) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "self-use record failed" in captured.err
    assert SelfUseLedger(ledger).load() == []


def test_record_rejects_non_trading_day(tmp_path, capsys) -> None:
    ledger = tmp_path / "events.jsonl"
    run_root = tmp_path / "runs"
    _make_completed_run(run_root, "run-1")

    # 2026-06-06 是周六：不在注入的日历里（日历只含合法交易日）。
    args = [
        "self-use", "record", "--ledger", str(ledger),
        "--date", "2026-06-06", "--workflow", "daily_market",
        "--outcome", "success", "--useful",
        "--run-id", "run-1", "--run-root", str(run_root),
        *_cal_args(*CAL),
    ]
    assert cli.main(args) == 2
    captured = capsys.readouterr()
    assert "self-use record failed" in captured.err
    assert SelfUseLedger(ledger).load() == []


def test_record_preserves_manual_severe_and_not_useful_flags(tmp_path, capsys) -> None:
    ledger = tmp_path / "events.jsonl"
    run_root = tmp_path / "runs"
    _make_completed_run(run_root, "run-1")
    args = _record_args(ledger, run_root)
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
    args = _record_args(tmp_path / "events.jsonl", tmp_path / "runs")
    args[args.index("daily_market")] = "freeform"

    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(args)

    assert exc_info.value.code == 2


def test_status_user_approval_cannot_bypass_mechanical_gate(tmp_path, capsys) -> None:
    ledger = tmp_path / "events.jsonl"
    run_root = tmp_path / "runs"
    _make_completed_run(run_root, "run-1")
    assert cli.main(_record_args(ledger, run_root)) == 0
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
                *_cal_args(*CAL),
            ]
        )
        == 1
    )
    result = json.loads(capsys.readouterr().out)
    assert result["user_approved"] is True
    assert result["eligible_for_user_decision"] is False
    assert result["passed"] is False


def test_persistent_approval_drives_status_pass(tmp_path, capsys) -> None:
    ledger = tmp_path / "events.jsonl"
    _complete_ledger(ledger)

    # 无审批：eligible 但未 pass。
    assert (
        cli.main(["self-use", "status", "--ledger", str(ledger), "--json", *_cal_args(*CAL)])
        == 1
    )
    before = json.loads(capsys.readouterr().out)
    assert before["eligible_for_user_decision"] is True
    assert before["passed"] is False

    # 持久化审批。
    assert (
        cli.main(
            ["self-use", "approve", "--ledger", str(ledger), "--by", "a77", *_cal_args(*CAL)]
        )
        == 0
    )
    record = json.loads(capsys.readouterr().out)
    assert record["approved_by"] == "a77"
    assert record["approved_at"]
    assert record["eligibility_fingerprint"]

    # 审批后 status 无需 --user-approved 也 pass。
    assert (
        cli.main(["self-use", "status", "--ledger", str(ledger), "--json", *_cal_args(*CAL)])
        == 0
    )
    after = json.loads(capsys.readouterr().out)
    assert after["passed"] is True
    assert after["persisted_approval"] is True


def test_approval_invalidated_after_ledger_change(tmp_path, capsys) -> None:
    ledger = tmp_path / "events.jsonl"
    _complete_ledger(ledger)
    assert (
        cli.main(
            ["self-use", "approve", "--ledger", str(ledger), "--by", "a77", *_cal_args(*CAL)]
        )
        == 0
    )
    capsys.readouterr()

    # 台账再追加一条 → 指纹变化 → 旧审批失效。
    SelfUseLedger(ledger).record(
        SelfUseEvent(
            trade_date=CAL[10],
            workflow="daily_market",
            outcome="success",
            manual_rescue=False,
            severe_fact_error=False,
            useful=True,
            run_id="extra",
        )
    )
    assert (
        cli.main(["self-use", "status", "--ledger", str(ledger), "--json", *_cal_args(*CAL)])
        == 1
    )
    after = json.loads(capsys.readouterr().out)
    assert after["passed"] is False
    assert after["persisted_approval"] is False


def test_approve_rejects_ineligible_ledger(tmp_path, capsys) -> None:
    ledger = tmp_path / "events.jsonl"
    run_root = tmp_path / "runs"
    _make_completed_run(run_root, "run-1")
    assert cli.main(_record_args(ledger, run_root)) == 0
    capsys.readouterr()

    assert (
        cli.main(
            ["self-use", "approve", "--ledger", str(ledger), "--by", "a77", *_cal_args(*CAL)]
        )
        == 2
    )
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "not eligible_for_user_decision" in captured.err


def test_plain_status_reports_required_summary(tmp_path, capsys) -> None:
    ledger = tmp_path / "events.jsonl"
    run_root = tmp_path / "runs"
    _make_completed_run(run_root, "run-1")
    assert cli.main(_record_args(ledger, run_root)) == 0
    capsys.readouterr()

    assert cli.main(["self-use", "status", "--ledger", str(ledger), *_cal_args(*CAL)]) == 1
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


def test_record_invalid_date_returns_two_and_writes_stderr(tmp_path, capsys) -> None:
    args = _record_args(tmp_path / "events.jsonl", tmp_path / "runs")
    args[args.index("2026-06-01")] = "not-a-date"

    assert cli.main(args) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "self-use record failed: invalid trade_date" in captured.err


def test_explicit_ledger_expands_user_home(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    run_root = tmp_path / "runs"
    _make_completed_run(run_root, "run-1")

    assert cli.main(_record_args("~/self-use/events.jsonl", run_root)) == 0
    capsys.readouterr()

    assert (tmp_path / "self-use" / "events.jsonl").exists()


def test_default_ledger_uses_user_space_root(tmp_path, monkeypatch, capsys) -> None:
    root = tmp_path / "private-user"
    run_root = tmp_path / "runs"
    _make_completed_run(run_root, "run-1")
    seen: list[str | None] = []

    def fake_user_space(user: str | None):
        seen.append(user)
        return SimpleNamespace(root=root, user_id=user or "default")

    monkeypatch.setattr(userspace, "user_space", fake_user_space)

    args = _record_args(tmp_path / "unused.jsonl", run_root, "--user", "alice")
    ledger_index = args.index("--ledger")
    del args[ledger_index : ledger_index + 2]
    assert cli.main(args) == 0
    capsys.readouterr()

    assert "alice" in seen
    assert (root / "self-use" / "events.jsonl").exists()
