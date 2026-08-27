"""W6 部署切换审计账本。

HTTP 一律 mock，禁止打 reserved 端口 8792。不 kickstart sidecar。
"""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path
from typing import Any

import pytest

from intelligence.runtime import deploy_ledger

REPO = Path(__file__).resolve().parents[2]


def _row(path: Path) -> dict[str, Any]:
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert lines, f"expected JSONL rows in {path}"
    return json.loads(lines[-1])


def test_append_startup_row_shape(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ledger = tmp_path / "deploy-ledger.jsonl"
    monkeypatch.setenv("FINANCE_DEPLOY_LEDGER", str(ledger))
    monkeypatch.delenv("FINANCE_WS", raising=False)

    written = deploy_ledger.record_event(
        action="startup",
        rev="b42a82d6ce8a96744e269308d9b8cc6bb89d383d",
        snapshot_path="/tmp/fake-snapshot/intelligence",
        port=8796,
        pid=4242,
        argv=["uvicorn", "intelligence.api.app:app", "--port", "8796"],
    )

    assert written == ledger
    row = _row(ledger)
    assert row["action"] == "startup"
    assert row["rev"].startswith("b42a82d6")
    assert row["snapshot_path"].endswith("intelligence")
    assert row["port"] == 8796
    assert row["pid"] == 4242
    assert row["argv"][0] == "uvicorn"
    assert "T" in row["ts"] and row["ts"].endswith("Z")
    assert isinstance(row["unix"], float)


def test_audit_ok_when_rev_matches(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ledger = tmp_path / "deploy-ledger.jsonl"
    monkeypatch.setenv("FINANCE_DEPLOY_LEDGER", str(ledger))
    deploy_ledger.record_event(
        action="switch",
        rev="a7e2d74f7789abcd",
        snapshot_path=tmp_path / "snap",
    )
    report = deploy_ledger.check_against_health(
        ledger,
        {"runtime": {"source_revision": "a7e2d74f7789abcd000000000000000000000000"}},
    )
    assert report["ok"] is True
    assert report["reason"] == "ok"


def test_audit_fail_when_rev_mismatches(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ledger = tmp_path / "deploy-ledger.jsonl"
    monkeypatch.setenv("FINANCE_DEPLOY_LEDGER", str(ledger))
    deploy_ledger.record_event(action="startup", rev="aaaaaaaaaaaa")
    report = deploy_ledger.check_against_health(
        ledger,
        {"runtime": {"source_revision": "bbbbbbbbbbbb"}},
    )
    assert report["ok"] is False
    assert report["reason"] == "rev_mismatch"


def test_audit_fail_when_ledger_missing(tmp_path: Path) -> None:
    report = deploy_ledger.check_against_health(
        tmp_path / "missing.jsonl",
        {"runtime": {"source_revision": "aaaaaaaaaaaa"}},
    )
    assert report["ok"] is False
    assert report["reason"] == "missing_ledger_row"


def test_check_filters_sidecar_rows_by_port(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """实测失败形状（2026-08-19）：8796 sidecar 启动行顶掉 8792 生产对账。"""

    ledger = tmp_path / "deploy-ledger.jsonl"
    monkeypatch.setenv("FINANCE_DEPLOY_LEDGER", str(ledger))
    deploy_ledger.record_event(action="startup", rev="a" * 12, port=8792)
    deploy_ledger.record_event(action="startup", rev="b" * 12, port=8796)

    health = {"runtime": {"source_revision": "a" * 12}}
    filtered = deploy_ledger.check_against_health(ledger, health, port=8792)
    assert filtered["ok"] is True
    assert filtered["port"] == 8792

    unfiltered = deploy_ledger.check_against_health(ledger, health)
    assert unfiltered["ok"] is False
    assert unfiltered["reason"] == "rev_mismatch"


def test_check_counts_portless_rows_for_any_port(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """旧版 switch 行没记端口：必须计入任何端口，否则漏报失败的重启。"""

    ledger = tmp_path / "deploy-ledger.jsonl"
    monkeypatch.setenv("FINANCE_DEPLOY_LEDGER", str(ledger))
    deploy_ledger.record_event(action="startup", rev="a" * 12, port=8792)
    deploy_ledger.record_event(action="switch", rev="c" * 12, port=None)

    switched = deploy_ledger.check_against_health(
        ledger, {"runtime": {"source_revision": "c" * 12}}, port=8792
    )
    assert switched["ok"] is True
    assert switched["ledger_action"] == "switch"

    stale = deploy_ledger.check_against_health(
        ledger, {"runtime": {"source_revision": "a" * 12}}, port=8792
    )
    assert stale["ok"] is False
    assert stale["reason"] == "rev_mismatch"


def test_cli_check_derives_port_from_url(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import sys

    sys.path.insert(0, str(REPO))
    from scripts import audit_deploy_ledger as cli

    ledger = tmp_path / "deploy-ledger.jsonl"
    monkeypatch.setenv("FINANCE_DEPLOY_LEDGER", str(ledger))
    deploy_ledger.record_event(action="startup", rev="a" * 12, port=8792)
    deploy_ledger.record_event(action="startup", rev="b" * 12, port=8796)

    monkeypatch.setattr(
        cli,
        "fetch_health",
        lambda url, timeout=5.0: {"runtime": {"source_revision": "a" * 12}},
    )
    assert cli.main(["check", "--url", "http://127.0.0.1:8792/api/health"]) == 0


def test_record_from_app_fail_open_on_unwritable_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    blocked = tmp_path / "not-a-dir"
    blocked.write_text("x", encoding="utf-8")
    monkeypatch.setenv("FINANCE_DEPLOY_LEDGER", str(blocked / "ledger.jsonl"))
    result = deploy_ledger.record_startup(
        rev="deadbeef",
        snapshot_path=tmp_path,
        repo_root=tmp_path,
    )
    assert result is None


def test_cli_check_ok_with_mocked_http(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import sys

    sys.path.insert(0, str(REPO))
    from scripts import audit_deploy_ledger as cli

    ledger = tmp_path / "deploy-ledger.jsonl"
    monkeypatch.setenv("FINANCE_DEPLOY_LEDGER", str(ledger))
    deploy_ledger.record_event(action="startup", rev="cafebabecafebabe")

    def fake_fetch(url: str, timeout: float = 5.0) -> dict[str, Any]:
        assert "8792" in url
        return {"runtime": {"source_revision": "cafebabecafebabe"}}

    monkeypatch.setattr(cli, "fetch_health", fake_fetch)
    assert cli.main(["check", "--url", "http://127.0.0.1:8792/api/health"]) == 0


def test_cli_check_mismatch_exits_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import sys

    sys.path.insert(0, str(REPO))
    from scripts import audit_deploy_ledger as cli

    ledger = tmp_path / "deploy-ledger.jsonl"
    monkeypatch.setenv("FINANCE_DEPLOY_LEDGER", str(ledger))
    deploy_ledger.record_event(action="switch", rev="111111111111")
    monkeypatch.setattr(
        cli,
        "fetch_health",
        lambda url, timeout=5.0: {"runtime": {"source_revision": "222222222222"}},
    )
    assert cli.main(["check"]) == 1


def test_cli_help_lists_subcommands() -> None:
    import sys

    sys.path.insert(0, str(REPO))
    from scripts import audit_deploy_ledger as cli

    with pytest.raises(SystemExit) as exited:
        cli.build_parser().parse_args(["--help"])
    assert exited.value.code == 0
    help_text = cli.build_parser().format_help()
    assert "record" in help_text
    assert "check" in help_text


def test_cli_record_switch_from_health_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import sys

    sys.path.insert(0, str(REPO))
    from scripts import audit_deploy_ledger as cli

    ledger = tmp_path / "deploy-ledger.jsonl"
    health = {
        "runtime": {
            "source_revision": "0df866122c73abcd",
            "loaded_code_root": str(tmp_path / "snap" / "intelligence"),
        }
    }
    assert (
        cli.main(
            [
                "record",
                "--action",
                "switch",
                "--health-json",
                json.dumps(health),
                "--snapshot-path",
                str(tmp_path / "snap"),
                "--ledger",
                str(ledger),
                "--port",
                "8792",
            ]
        )
        == 0
    )
    row = _row(ledger)
    assert row["action"] == "switch"
    assert row["rev"].startswith("0df86612")
    assert row["snapshot_path"].endswith("snap")
    assert row["port"] == 8792


def test_deploy_script_and_chain_cut_docs_call_record_cli() -> None:
    """接线必须存在：脚本/文档写了但不调用 = 失败形状还会再来一次。"""

    deploy = (REPO / "scripts" / "deploy_workbench_runtime.sh").read_text(encoding="utf-8")
    workflow = (REPO / "docs" / "workflows" / "acceptance-workflow.md").read_text(
        encoding="utf-8"
    )
    assert "audit_deploy_ledger.py" in deploy
    assert "--action switch" in deploy
    ln_index = workflow.index("ln -sfh")
    record_index = workflow.index("audit_deploy_ledger.py")
    assert record_index > ln_index
    assert "kickstart" in deploy


def test_gitignore_covers_repo_root_state_not_skill_state() -> None:
    gitignore = (REPO / ".gitignore").read_text(encoding="utf-8")
    assert "/state/" in gitignore or "state/deploy-ledger.jsonl" in gitignore
    # skills/*/state 仍被跟踪，不能用无锚点的 state/
    assert "\nstate/\n" not in gitignore


def test_create_app_lifespan_writes_startup_row(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from intelligence.api import app as app_module

    ledger = tmp_path / "deploy-ledger.jsonl"
    users = tmp_path / "users"
    wiki = tmp_path / "wiki"
    (wiki / "relations").mkdir(parents=True)
    snapshot = tmp_path / "market_snapshot"
    snapshot.mkdir()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.setenv("FINANCE_DEPLOY_LEDGER", str(ledger))
    monkeypatch.setenv("FORESIGHT_USERS_DIR", str(users))
    monkeypatch.setenv("FINANCE_WS", str(repo_root))
    monkeypatch.setenv("KB_VAULT", str(wiki))
    monkeypatch.setenv("MARKET_SNAPSHOT_DIR", str(snapshot))
    monkeypatch.setenv("RAG_WORKER_ENABLED", "0")
    monkeypatch.setattr(app_module.kb_rag.rag_worker, "close_all", lambda: None)

    with TestClient(app_module.create_app(repo_root=repo_root)):
        pass

    assert ledger.is_file()
    row = _row(ledger)
    assert row["action"] == "startup"
    assert "rev" in row
    assert row["pid"] == os.getpid()


def test_ledger_parent_is_created(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ledger = tmp_path / "nested" / "dir" / "deploy-ledger.jsonl"
    monkeypatch.setenv("FINANCE_DEPLOY_LEDGER", str(ledger))
    deploy_ledger.record_event(action="startup", rev="abcdabcdabcd")
    assert ledger.is_file()
    assert stat.S_ISREG(ledger.stat().st_mode)
