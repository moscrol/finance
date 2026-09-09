"""工单 #44：部署账本只有一个家。

写入（``deploy_ledger.record_event``）/ 读取（``worktree_board.resolve_ledger_path``）/ 审计
（``audit_deploy_ledger.py check``）三处对同一环境解析同一路径，不管 ``FINANCE_WS`` 有没有、
``repo_root`` 传没传；``homes`` 报旧家并当门；``migrate-homes`` 并入幂等、目标被并发改动时放弃。
"""

from __future__ import annotations

from datetime import datetime, timezone
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from intelligence.runtime import deploy_ledger

_ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, _ROOT / relative)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


board = _load("worktree_board_homes_under_test", "scripts/worktree_board.py")
audit = _load("audit_deploy_ledger_homes_under_test", "scripts/audit_deploy_ledger.py")


def _write(path: Path, rows: list[dict]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    return path


def _rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _last_json(capsys: pytest.CaptureFixture[str]) -> dict:
    out = capsys.readouterr().out.strip().splitlines()
    return json.loads(out[-1])


@pytest.fixture
def sealed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    """密封宿主：家目录、主检出树、FINANCE_WS 都指向 tmp，真账本碰不到。"""

    home = tmp_path / "home"
    main = tmp_path / "main"
    main.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    monkeypatch.delenv("FINANCE_DEPLOY_LEDGER", raising=False)
    monkeypatch.delenv("FINANCE_WS", raising=False)
    monkeypatch.setattr(audit, "_git_common_dir_parent", lambda root: main)
    monkeypatch.setattr(board, "_git", lambda args, *, cwd, timeout: (0, str(main / ".git")))
    return SimpleNamespace(
        home=home / ".finance-runtime" / "deploy-ledger.jsonl",
        main_ledger=main / "state" / "deploy-ledger.jsonl",
        ws=tmp_path / "ws",
        repo=tmp_path / "repo",
    )


@pytest.mark.parametrize("finance_ws", [False, True])
def test_writer_reader_and_auditor_resolve_the_same_file(
    sealed: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], finance_ws: bool
) -> None:
    if finance_ws:
        monkeypatch.setenv("FINANCE_WS", str(sealed.ws))

    # 写入侧：repo_root 传了也不看
    written = deploy_ledger.record_event(
        action="switch", rev="0060da5c1a08", port=8792, repo_root=sealed.repo
    )
    assert written == sealed.home
    assert not (sealed.ws / "state").exists() and not (sealed.repo / "state").exists()
    # 读取侧（SessionStart 那条 8792 行）
    assert board.resolve_ledger_path(sealed.repo) == sealed.home
    assert board.last_switch_for_port(sealed.home)["rev"] == "0060da5c1a08"
    # 审计侧：check 读的也是这一份
    monkeypatch.setattr(
        audit, "fetch_health", lambda url, timeout=5.0: {"runtime": {"source_revision": "0060da5c1a08"}}
    )
    assert audit.main(["check", "--url", "http://127.0.0.1:8792/api/health"]) == 0
    report = _last_json(capsys)
    assert report["ok"] and report["ledger_path"] == str(sealed.home) and report["port"] == 8792


def test_record_and_check_ignore_repo_root_but_say_so(
    sealed: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    assert (
        audit.main(
            ["record", "--action", "switch", "--rev", "abcdef1234567", "--port", "8792", "--repo-root", str(sealed.repo)]
        )
        == 0
    )
    captured = capsys.readouterr()
    assert "--repo-root" in captured.err and "已忽略" in captured.err
    assert _rows(sealed.home)[-1]["rev"] == "abcdef1234567"
    assert not (sealed.repo / "state").exists()


def test_homes_reports_legacy_files_and_gates_until_migrated(
    sealed: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("FINANCE_WS", str(sealed.ws))
    _write(sealed.home, [{"action": "switch", "rev": "0060da5c1a08", "port": 8792, "unix": 3.0, "ts": "t3"}])
    _write(
        sealed.main_ledger,
        [
            {"action": "startup", "rev": "b594a5e7f8ae", "port": 8792, "unix": 1.0, "ts": "t1"},
            {"action": "switch", "rev": "b594a5e7f8ae", "port": 8792, "unix": 2.0, "ts": "t2"},
            {"action": "switch", "rev": "0060da5c1a08", "port": 8792, "unix": 3.0, "ts": "t3"},  # 与唯一家重复
        ],
    )
    ws_ledger = _write(
        sealed.ws / "state" / "deploy-ledger.jsonl",
        [{"action": "startup", "rev": "2431da494ad4", "port": 8799, "unix": 2.5, "ts": "t2.5"}],
    )

    assert audit.main(["homes"]) == 1
    report = _last_json(capsys)
    assert report["ok"] is False and report["legacy_present"] is True
    assert report["home"]["rows"] == 1 and report["home"]["last_switch"]["rev"] == "0060da5c1a08"
    by_path = {entry["path"]: entry for entry in report["legacy"]}
    assert by_path[str(sealed.main_ledger)]["rows"] == 3
    assert by_path[str(sealed.main_ledger)]["last_switch"]["rev"] == "0060da5c1a08"
    assert by_path[str(sealed.main_ledger)]["last_startup"]["rev"] == "b594a5e7f8ae"
    assert by_path[str(ws_ledger)]["rows"] == 1 and by_path[str(ws_ledger)]["last_switch"] is None

    # 计划：不动文件
    assert audit.main(["migrate-homes"]) == 0
    plan = _last_json(capsys)
    assert plan["mode"] == "dry_run" and plan["applied"] is False
    assert plan["target_rows_before"] == 1 and plan["target_rows_after"] == 4
    assert {entry["path"]: (entry["added"], entry["duplicates"]) for entry in plan["sources"]} == {
        str(sealed.main_ledger): (2, 1),
        str(ws_ledger): (1, 0),
    }
    assert len(_rows(sealed.home)) == 1 and sealed.main_ledger.is_file() and ws_ledger.is_file()

    # 真并入：并集去重、按时刻排序、旧文件改名保留
    assert audit.main(["migrate-homes", "--apply"]) == 0
    applied = _last_json(capsys)
    assert applied["applied"] is True and len(applied["renamed"]) == 2
    merged = _rows(sealed.home)
    assert [row["unix"] for row in merged] == [1.0, 2.0, 2.5, 3.0]
    assert deploy_ledger.last_relevant_row(sealed.home, port=8792)["rev"] == "0060da5c1a08"
    assert not sealed.main_ledger.is_file() and not ws_ledger.is_file()
    migrated = sorted(sealed.main_ledger.parent.glob("deploy-ledger.jsonl.migrated-*"))
    assert len(migrated) == 1 and len(_rows(migrated[0])) == 3

    # 门变绿；再跑一次是空操作
    assert audit.main(["homes"]) == 0
    assert _last_json(capsys)["legacy_present"] is False
    assert audit.main(["migrate-homes", "--apply"]) == 0
    again = _last_json(capsys)
    assert again["applied"] is True and again["renamed"] == [] and again["target_rows_after"] == 4
    assert [row["unix"] for row in _rows(sealed.home)] == [1.0, 2.0, 2.5, 3.0]


def test_migrate_puts_undated_legacy_rows_first_and_keeps_file_order_chronological(
    sealed: SimpleNamespace,
) -> None:
    later = datetime(2026, 9, 7, 0, 0, 5, tzinfo=timezone.utc).timestamp()
    _write(sealed.home, [{"action": "startup", "rev": "ffffffffffff", "port": 8792, "unix": later}])
    old_format = {"action": "switch", "rev": "000000000000"}  # 2026-08 老格式：无 unix / ts
    _write(
        sealed.main_ledger,
        # 只有 ts 没有 unix 的行按 ts 排：比 later 早一秒
        [old_format, {"action": "switch", "rev": "444444444444", "port": 8792, "ts": "2026-09-07T00:00:04Z"}],
    )

    report = deploy_ledger.merge_ledgers([sealed.main_ledger], sealed.home, apply=True, stamp="20260909")

    assert report["applied"] and report["target_rows_after"] == 3
    merged = _rows(sealed.home)
    assert merged[0] == old_format
    assert [row.get("rev") for row in merged[1:]] == ["444444444444", "ffffffffffff"]
    assert (sealed.main_ledger.parent / "deploy-ledger.jsonl.migrated-20260909").is_file()


def test_migrate_aborts_when_the_target_changes_between_read_and_replace(
    sealed: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write(sealed.home, [{"action": "switch", "rev": "aaaaaaaaaaaa", "port": 8792, "unix": 1.0}])
    _write(sealed.main_ledger, [{"action": "switch", "rev": "bbbbbbbbbbbb", "port": 8792, "unix": 2.0}])
    signatures = iter([(10, 1), (11, 2)])
    monkeypatch.setattr(deploy_ledger, "_stat_signature", lambda path: next(signatures))

    report = deploy_ledger.merge_ledgers([sealed.main_ledger], sealed.home, apply=True)

    assert report["applied"] is False and report["aborted"] == "target_changed"
    assert [row["rev"] for row in _rows(sealed.home)] == ["aaaaaaaaaaaa"]
    assert sealed.main_ledger.is_file()
