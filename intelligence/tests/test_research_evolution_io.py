"""受控本地入口的验收（spec 06 §5.1 / §5.2 → I13 / I15）。

两条纪律逐条钉住：默认不落盘；登记时钟归服务端，输入包回填不了。
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from intelligence.services.research_evolution import pilot_io, study_io
from intelligence.tests import research_evolution_fixtures as fx

SH = timezone(timedelta(hours=8))
NOW = datetime(2026, 9, 14, 16, 0, 0, tzinfo=SH)
OWNER = "default"


@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    return fx.install_env(monkeypatch, tmp_path)


def _run(module, argv: list[str], capsys: pytest.CaptureFixture[str], *, now: datetime = NOW) -> tuple[int, dict]:
    code = module.main(argv, now=now)
    out = capsys.readouterr().out.strip()
    return code, json.loads(out) if out else {}


def _protocol_file(tmp_path: Path) -> Path:
    import yaml

    raw = yaml.safe_load((fx.FIXTURE_DIR.parent / "05" / "protocol.yaml").read_text(encoding="utf-8"))
    path = tmp_path / "protocol.json"
    path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    return path


# --------------------------------------------------------------------------- #
# pilot_io
# --------------------------------------------------------------------------- #
def test_pilot_register_is_dry_run_by_default(env: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = _protocol_file(tmp_path)
    code, body = _run(pilot_io, ["--owner", OWNER, "register", "--kind", "protocol", "--input", str(path)], capsys)
    assert code == 0 and body["dry_run"] is True
    assert not (env / OWNER / "research_evolution" / "protocols").exists(), "dry-run 不得落盘"

    code, body = _run(pilot_io, ["--owner", OWNER, "--apply", "register", "--kind", "protocol", "--input", str(path)], capsys)
    assert code == 0 and body["created"] is True
    stored = list((env / OWNER / "research_evolution" / "protocols").glob("*.json"))
    assert len(stored) == 1


def test_pilot_register_is_idempotent_on_identical_content(env: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = _protocol_file(tmp_path)
    args = ["--owner", OWNER, "--apply", "register", "--kind", "protocol", "--input", str(path)]
    first = _run(pilot_io, args, capsys)[1]
    second = _run(pilot_io, args, capsys)[1]
    assert first["protocol_hash"] == second["protocol_hash"]
    assert first["created"] is True and second["created"] is False
    assert len(list((env / OWNER / "research_evolution" / "protocols").glob("*.json"))) == 1


def test_pilot_import_refuses_the_whole_batch_when_one_event_is_invalid(
    env: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    good = json.loads((fx.FIXTURE_DIR.parent / "05" / "complete_pair" / "events.jsonl").read_text(encoding="utf-8").splitlines()[0])
    bad = {**good, "event_id": "e-bad", "event_type": "not_a_real_type"}
    path = tmp_path / "events.jsonl"
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in (good, bad)), encoding="utf-8")

    code, body = _run(pilot_io, ["--owner", OWNER, "--apply", "import-events", "--events", str(path)], capsys)
    assert code == 2
    assert body["ok"] is False
    assert body["rejected"], "拒收项要逐条回给调用者"
    assert not (env / OWNER / "research_evolution" / "product_value_events.jsonl").exists(), "整批失败不留半批"


def test_pilot_import_stamps_the_channel_and_ignores_what_the_file_claims(
    env: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    row = json.loads((fx.FIXTURE_DIR.parent / "05" / "complete_pair" / "events.jsonl").read_text(encoding="utf-8").splitlines()[0])
    row["source_channel"] = "server"  # 文件自称服务端事实
    path = tmp_path / "events.jsonl"
    path.write_text(json.dumps(row, ensure_ascii=False), encoding="utf-8")

    code, _ = _run(pilot_io, ["--owner", OWNER, "--apply", "import-events", "--events", str(path)], capsys)
    assert code == 0
    stored = [
        json.loads(line)
        for line in (env / OWNER / "research_evolution" / "product_value_events.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(stored) == 1
    assert stored[0]["source_channel"] == "manual_import", "来源渠道由接收入口决定，不采信文件自报"
    assert stored[0]["owner_user_id"] == OWNER


def test_pilot_import_is_idempotent_across_reruns(env: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    row = json.loads((fx.FIXTURE_DIR.parent / "05" / "complete_pair" / "events.jsonl").read_text(encoding="utf-8").splitlines()[0])
    path = tmp_path / "events.jsonl"
    path.write_text(json.dumps(row, ensure_ascii=False), encoding="utf-8")
    args = ["--owner", OWNER, "--apply", "import-events", "--events", str(path)]
    first = _run(pilot_io, args, capsys)[1]
    second = _run(pilot_io, args, capsys)[1]
    assert first["written"] == 1
    assert second["written"] == 0 and second["already_present"] == 1
    lines = (env / OWNER / "research_evolution" / "product_value_events.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1


def test_pilot_import_refuses_server_facts_arriving_through_the_manual_door(
    env: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """``run_started`` 这类服务端事实走人工导入口会被拒：M 渠道必须带导入者与凭据。

    这不是夹具坏了——它正是那条边界：谁收的事件谁盖章，人工口不能替服务端作证。
    """
    rows = [json.loads(line) for line in (fx.FIXTURE_DIR.parent / "05" / "complete_pair" / "events.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    server_rows = [r for r in rows if r.get("event_type") in {"run_started", "run_finished"}]
    assert server_rows, "夹具里应当有服务端事实事件"
    path = tmp_path / "server.jsonl"
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in server_rows), encoding="utf-8")

    code, body = _run(pilot_io, ["--owner", OWNER, "--apply", "import-events", "--events", str(path)], capsys)
    assert code == 2
    codes = {issue["code"] for item in body["rejected"] for issue in item["issues"]}
    # 两道各自独立的关都咬住了：类型白名单不允许 M 渠道，凭据也缺。
    assert codes == {"source_not_allowed", "manual_import_missing_evidence"}
    assert not (env / OWNER / "research_evolution" / "product_value_events.jsonl").exists()


def _seed_server_events(env: Path, rows: list[dict]) -> None:
    """服务端事实由服务端写：测试里直接经同一个 writer 落盘，模拟 Workbench 观察 run 生命周期。"""
    from intelligence.services.research_evolution.contracts import digest
    from intelligence.services.research_evolution.store import EvolutionStore

    store = EvolutionStore(env / OWNER / "research_evolution", OWNER)
    with store.transaction() as txn:
        for row in rows:
            txn.append_product_value_event({**row, "owner_user_id": OWNER}, content_hash=digest(row))


def test_pilot_rebuild_is_reproducible_and_never_upgrades_synthetic_to_real(
    env: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    protocol_path = _protocol_file(tmp_path)
    registered = _run(pilot_io, ["--owner", OWNER, "--apply", "register", "--kind", "protocol", "--input", str(protocol_path)], capsys)[1]
    rows = [json.loads(line) for line in (fx.FIXTURE_DIR.parent / "05" / "complete_pair" / "events.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    manual = [r for r in rows if r.get("source_channel") == "manual_import"]
    server = [r for r in rows if r.get("source_channel") != "manual_import"]
    _seed_server_events(env, server)
    manual_path = tmp_path / "manual.jsonl"
    manual_path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in manual), encoding="utf-8")
    imported = _run(pilot_io, ["--owner", OWNER, "--apply", "import-events", "--events", str(manual_path)], capsys)[1]
    assert imported["ok"] is True

    args = ["--owner", OWNER, "--apply", "rebuild", "--protocol-hash", registered["protocol_hash"]]
    first = _run(pilot_io, args, capsys)[1]
    second = _run(pilot_io, args, capsys)[1]
    assert first["ok"] and second["ok"]
    # 同输入同内容 id：重启后对账靠的就是这个。
    assert first["summary_id"] == second["summary_id"]
    assert second["summary_created"] is False
    assert second["receipts_written"] == 0
    # 夹具事件是 synthetic：真人效果与付费状态不得被它升级。
    assert first["field_status"] in {"pending", "collecting", "inconclusive"}
    assert first["commercial_status"] == "unstarted"


def test_pilot_show_reports_state_without_writing(env: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code, body = _run(pilot_io, ["--owner", OWNER, "show"], capsys)
    assert code == 0
    assert body == {
        "owner": OWNER,
        "events": 0,
        "process_receipts": 0,
        "protocols": [],
        "receipts": [],
        "summaries": [],
        "registrations": [],
    }
    assert not (env / OWNER / "research_evolution").exists()


# --------------------------------------------------------------------------- #
# study_io
# --------------------------------------------------------------------------- #
def _forward_protocol(tmp_path: Path) -> Path:
    from intelligence.services.research_validation.contracts import Calendar  # noqa: F401 - 只为确认 03 可用

    body = json.loads((fx.FIXTURE_DIR.parent / "03" / "forward_protocol_synthetic.json").read_text(encoding="utf-8"))
    body.pop("_comment", None)
    calendar = [f"2026-09-{day:02d}" for day in (1, 2, 3, 4, 7, 8, 9, 10, 11, 14, 15, 16, 17, 18)]
    body["calendar"] = calendar
    body["forward_start"] = "2026-09-15"
    body["evaluation_end"] = "2026-09-18"
    path = tmp_path / "forward.json"
    path.write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")
    return path


def test_study_io_refuses_input_packs_that_try_to_backfill_the_clock(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "p.json"
    path.write_text(json.dumps({"mode": "forward", "now": "2026-01-01T00:00:00+08:00"}), encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        study_io.main(["--owner", OWNER, "freeze", "--protocol", str(path)], now=NOW)
    assert "不得包含" in str(exc.value)


def test_study_io_freeze_is_dry_run_by_default(env: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = _forward_protocol(tmp_path)
    code, body = _run(study_io, ["--owner", OWNER, "freeze", "--protocol", str(path)], capsys)
    assert code == 0 and body["dry_run"] is True
    assert not (env / OWNER / "research_validation").exists()


def test_study_io_settle_without_an_authorised_outcome_source_fails_closed(
    env: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code, body = _run(study_io, ["--owner", OWNER, "--apply", "settle", "--study-id", "s1"], capsys)
    assert code == 2
    assert body["ok"] is False
    assert "结果源" in body["error"]


def test_study_io_show_is_empty_before_any_study_is_frozen(env: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code, body = _run(study_io, ["--owner", OWNER, "show"], capsys)
    assert code == 0
    assert body == {"owner": OWNER, "studies": [], "exposures": 0}
