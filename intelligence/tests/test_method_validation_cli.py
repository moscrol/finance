"""分析师入口验收：真实最小主库→现有标签构建→新实验 CLI，不调用模型或生产写入。"""

from __future__ import annotations

import importlib.util
import json
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import duckdb
import pytest

from intelligence.services.methodology_backtest.labels import build_labels
from intelligence.services.methodology_backtest.outcomes import build_outcomes
from market_feature_store.db import init_db

REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("method_validation_cli", REPO / "scripts/method_validation.py")
cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli)
DATES = [date(2026, 2, 2) + timedelta(days=i) for i in range(12) if (date(2026, 2, 2) + timedelta(days=i)).weekday() < 5]
REGISTERED_AT = datetime(2026, 2, 3, 9, tzinfo=timezone.utc)
CAPTURED_AT = datetime(2026, 2, 4, 9, tzinfo=timezone.utc)


def _extend_source(source, days):
    with duckdb.connect(str(source)) as con:
        init_db(con)
        for day in days:
            con.execute("INSERT INTO fact_market_daily (trade_date, market_stage, total_amount) VALUES (?, '主升阶段', 10000)", [day])
            for code, pct in (("A.TI", 1.0), ("B.TI", 0.2), ("C.TI", -1.0)):
                diff = 20 if code == "A.TI" or (code == "B.TI" and day == DATES[2]) else -5
                con.execute(
                    "INSERT INTO fact_sector_daily_generation "
                    "(trade_date, sector_universe_snapshot_id, sector_ts_code, sector_name, pct_chg, amount, diff_ratio) "
                    "VALUES (?, 'legacy', ?, ?, ?, 800, ?)",
                    [day, code, code, pct, diff],
                )


@pytest.fixture
def example(tmp_path, monkeypatch, capsys):
    source, labels = tmp_path / "source.duckdb", tmp_path / "labels.duckdb"
    _extend_source(source, DATES[:3])
    build_labels(source, labels, now=CAPTURED_AT)
    monkeypatch.setattr(cli, "current_time", lambda: REGISTERED_AT)
    args = [
        "register", "--history-start", str(DATES[0]), "--history-end", str(DATES[1]),
        "--forward-start", str(DATES[2]), "--root", str(tmp_path / "research"),
    ]
    assert cli.main(args) == 0
    result = json.loads(capsys.readouterr().out)
    return {"source": source, "labels": labels, "study": Path(result["study_dir"]), "register_args": args}


def _run(command, example, capsys, *extra):
    args = [command, "--study-dir", str(example["study"]), "--labels-db", str(example["labels"]), *extra]
    code = cli.main(args)
    captured = capsys.readouterr()
    return code, json.loads(captured.out) if captured.out else {}, captured.err


def test_capture_pending_then_mature_keeps_original_members(example, monkeypatch, capsys):
    monkeypatch.setattr(cli, "current_time", lambda: CAPTURED_AT)
    # capture 在没有 history_outcomes 构建的旁路库上也必须能成功，证明选样不依赖未来结果。
    code, captured, error = _run("capture", example, capsys)
    assert code == 0, error
    observation = Path(captured["observation"])
    original_bytes = observation.read_bytes()
    original = cli.read_record(observation)
    assert "outcomes" not in original["payload"]
    assert "comparison" not in original["payload"]
    assert datetime.fromisoformat(original["payload"]["captured_at"]) == CAPTURED_AT
    assert [r["entity_id"] for r in original["payload"]["features"]["rows"] if "streak3" in r["arms"]] == ["A.TI"]

    build_outcomes(example["source"], example["labels"], now=CAPTURED_AT)
    code, pending, error = _run("recheck", example, capsys, "--observation", str(observation))
    assert code == 0, error
    assert pending["summary"]["paired_dates"] == 0

    _extend_source(example["source"], DATES[3:8])
    with duckdb.connect(str(example["source"])) as con:
        con.execute("UPDATE fact_sector_daily_generation SET diff_ratio=-5 WHERE trade_date=?", [DATES[2]])
    later = datetime(2026, 2, 11, 9, tzinfo=timezone.utc)
    build_labels(example["source"], example["labels"], now=later)
    build_outcomes(example["source"], example["labels"], now=later)
    monkeypatch.setattr(cli, "current_time", lambda: later)
    code, checked, error = _run("recheck", example, capsys, "--observation", str(observation))
    assert code == 0, error
    result = cli.read_record(Path(checked["record"]))
    assert checked["summary"]["paired_dates"] == 1
    assert checked["summary"]["means"]["streak3"] == pytest.approx((1.01**5 - 1) * 100)
    assert result["payload"]["features"] == original["payload"]["features"]
    assert result["payload"]["observation_sha256"] == original["content_sha256"]
    assert observation.read_bytes() == original_bytes
    assert Path(pending["record"]).is_file()  # pending 留证不被后来结果覆盖
    assert cli.main(["report", "--record", checked["record"]]) == 0
    report = capsys.readouterr().out
    assert "共同可评估日期：**1**" in report
    assert "尚不具备决策或方法晋升资格" in report


def test_history_and_report_are_repeatable_and_readonly(example, monkeypatch, capsys):
    monkeypatch.setattr(cli, "current_time", lambda: CAPTURED_AT)
    build_outcomes(example["source"], example["labels"], now=CAPTURED_AT)
    source_before = example["source"].read_bytes()
    labels_before = example["labels"].read_bytes()
    code, first, error = _run("history", example, capsys)
    assert code == 0, error
    code, second, error = _run("history", example, capsys)
    assert code == 0, error
    assert first["record"] == second["record"]
    assert example["source"].read_bytes() == source_before
    assert example["labels"].read_bytes() == labels_before
    assert cli.main(["report", "--record", first["record"]]) == 0
    assert "历史重建" in capsys.readouterr().out


def test_recheck_cannot_settle_future_dated_source_on_capture_day(example, monkeypatch, capsys):
    monkeypatch.setattr(cli, "current_time", lambda: CAPTURED_AT)
    code, captured, error = _run("capture", example, capsys)
    assert code == 0, error
    _extend_source(example["source"], DATES[3:8])
    future = datetime(2026, 2, 11, 9, tzinfo=timezone.utc)
    build_labels(example["source"], example["labels"], now=future)
    build_outcomes(example["source"], example["labels"], now=future)
    code, _, error = _run("recheck", example, capsys, "--observation", captured["observation"])
    assert code == 2 and error
    assert not list((example["study"] / "recheck").rglob("*.json"))


def test_same_day_capture_returns_original_without_resampling(example, monkeypatch, capsys):
    monkeypatch.setattr(cli, "current_time", lambda: CAPTURED_AT)
    code, first, error = _run("capture", example, capsys)
    assert code == 0, error

    def no_resample(*args, **kwargs):
        pytest.fail("同日重跑不应重选样本")

    monkeypatch.setattr(cli, "read_features", no_resample)
    code, second, error = _run("capture", example, capsys)
    assert code == 0, error
    assert second["status"] == "already_captured"
    assert second["observation"] == first["observation"]


def test_register_after_forward_start_returns_original_and_new_backdated_study_fails(example, monkeypatch, capsys):
    path = example["study"] / "protocol.json"
    original = path.read_bytes()
    monkeypatch.setattr(cli, "current_time", lambda: CAPTURED_AT)
    assert cli.main(example["register_args"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert Path(result["study_dir"]) == example["study"]
    assert path.read_bytes() == original
    args = example["register_args"].copy()
    args[args.index("--history-start") + 1] = str(DATES[1])
    assert cli.main(args) == 2
    assert capsys.readouterr().err


def test_capture_crosses_midnight_during_read_is_rejected(example, monkeypatch, capsys):
    before = datetime(2026, 2, 4, 15, 59, 59, tzinfo=timezone.utc)
    after = datetime(2026, 2, 4, 16, 0, 1, tzinfo=timezone.utc)
    moments = iter([before, after])
    monkeypatch.setattr(cli, "current_time", lambda: next(moments))
    code, _, error = _run("capture", example, capsys)
    assert code == 2 and error
    assert not list((example["study"] / "capture").rglob("*.json"))


def test_capture_rechecks_clock_after_lock_and_does_not_wait_on_lock(example, monkeypatch, capsys):
    moment = [CAPTURED_AT]
    monkeypatch.setattr(cli, "current_time", lambda: moment[0])
    original_lock = cli._capture_lock

    @contextmanager
    def delayed_lock(study_dir):
        moment[0] = datetime(2026, 2, 4, 16, 0, 1, tzinfo=timezone.utc)
        yield

    with monkeypatch.context() as patch:
        patch.setattr(cli, "_capture_lock", delayed_lock)
        code, _, error = _run("capture", example, capsys)
        assert code == 2 and error
    moment[0] = CAPTURED_AT
    with original_lock(example["study"]):
        code, _, error = _run("capture", example, capsys)
    assert code == 2 and "正在登记" in error
    assert not list((example["study"] / "capture").rglob("*.json"))


def test_no_historical_capture_or_clock_override(example, monkeypatch, capsys):
    monkeypatch.setattr(cli, "current_time", lambda: datetime(2026, 2, 5, 9, tzinfo=timezone.utc))
    code, _, error = _run("capture", example, capsys)
    assert code == 2 and error
    assert not list((example["study"] / "capture").rglob("*.json"))
    with pytest.raises(SystemExit) as exc:
        cli.main(["capture", "--study-dir", str(example["study"]), "--labels-db", str(example["labels"]), "--now", str(CAPTURED_AT)])
    assert exc.value.code == 2


def test_tampered_record_refuses_report(example, monkeypatch, capsys):
    monkeypatch.setattr(cli, "current_time", lambda: CAPTURED_AT)
    code, output, error = _run("capture", example, capsys)
    assert code == 0, error
    path = Path(output["observation"])
    doc = json.loads(path.read_text())
    doc["payload"]["features"]["rows"][0]["dual_red_streak"] = 999
    path.write_text(json.dumps(doc))
    assert cli.main(["report", "--record", str(path)]) == 2
    assert capsys.readouterr().err


def test_cross_study_observation_rejected(example, monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(cli, "current_time", lambda: CAPTURED_AT)
    code, captured, error = _run("capture", example, capsys)
    assert code == 0, error
    monkeypatch.setattr(cli, "current_time", lambda: REGISTERED_AT)
    args = example["register_args"].copy()
    args[args.index("--history-start") + 1] = str(DATES[1])
    assert cli.main(args) == 0
    second = Path(json.loads(capsys.readouterr().out)["study_dir"])
    assert second != example["study"]
    example["study"] = second
    code, _, error = _run("recheck", example, capsys, "--observation", captured["observation"])
    assert code == 2 and error


def test_user_namespaces_use_existing_userspace(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("FORESIGHT_USERS_DIR", str(tmp_path / "users"))
    monkeypatch.setattr(cli, "current_time", lambda: REGISTERED_AT)
    common = ["register", "--history-start", "2026-02-02", "--history-end", "2026-02-03", "--forward-start", "2026-02-04"]
    outputs = []
    for user in ("alice", "bob"):
        assert cli.main([*common, "--user", user]) == 0
        outputs.append(json.loads(capsys.readouterr().out))
        Path(outputs[-1]["study_dir"]).relative_to(tmp_path / "users" / user / "method_validation")
    assert outputs[0]["study_dir"] != outputs[1]["study_dir"]
    assert cli.main([*common, "--user", "../alice"]) == 2
