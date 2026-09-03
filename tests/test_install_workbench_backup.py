"""异地备份运行器：本地目标端到端（快照 + 硬链接 + latest + 保留期 + 预检拒绝）。

远端 ssh 路径不在这里测（需要真机）；``Target.parse`` 的两种形态在这里定死。
"""

from __future__ import annotations

import datetime as dt
import importlib.util
import shutil
import sys
from pathlib import Path

import pytest

_SCRIPT = (
    Path(__file__).resolve().parents[1] / "scripts" / "install_workbench_backup.py"
)
_spec = importlib.util.spec_from_file_location("install_workbench_backup", _SCRIPT)
backup = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
# dataclass 解析字符串注解时要查 sys.modules[cls.__module__]，按文件加载必须先登记。
sys.modules[_spec.name] = backup
_spec.loader.exec_module(backup)

pytestmark = pytest.mark.skipif(shutil.which("rsync") is None, reason="需要 rsync")


def _seed(source: Path) -> None:
    (source / "u1" / "runs" / "r1").mkdir(parents=True)
    (source / "u1" / "runs" / "r1" / "run.json").write_text('{"status":"completed"}')
    (source / "u1" / "corrections.jsonl").write_text("c1\n")


def test_target_parse_remote_vs_local(tmp_path):
    remote = backup.Target.parse("vps:/srv/backup/finance-workbench/")
    assert (remote.host, remote.root) == ("vps", "/srv/backup/finance-workbench")
    assert (
        remote.rsync_dest("2026-09-03")
        == "vps:/srv/backup/finance-workbench/2026-09-03/"
    )
    local = backup.Target.parse(str(tmp_path / "bk"))
    assert local.host is None and local.root == str(tmp_path / "bk")
    with pytest.raises(ValueError):
        backup.Target.parse("vps:relative/path")
    with pytest.raises(ValueError):
        backup.Target.parse("")


def test_snapshots_hardlink_unchanged_files_and_rotate_latest(tmp_path):
    source = tmp_path / "users"
    _seed(source)
    target = backup.Target.parse(str(tmp_path / "bk"))

    day1 = dt.date(2026, 9, 1)
    assert (
        backup.run_backup(source=source, target=target, keep_days=14, today=day1) == 0
    )
    snap1 = tmp_path / "bk" / "2026-09-01"
    assert (snap1 / "u1" / "corrections.jsonl").read_text() == "c1\n"
    assert (tmp_path / "bk" / "latest").resolve() == snap1.resolve()
    assert "2026-09-01" in (tmp_path / "bk" / "last-success.txt").read_text()

    (source / "u1" / "corrections.jsonl").write_text("c1\nc2\n")
    day2 = dt.date(2026, 9, 2)
    assert (
        backup.run_backup(source=source, target=target, keep_days=14, today=day2) == 0
    )
    snap2 = tmp_path / "bk" / "2026-09-02"
    unchanged1 = (snap1 / "u1" / "runs" / "r1" / "run.json").stat()
    unchanged2 = (snap2 / "u1" / "runs" / "r1" / "run.json").stat()
    assert unchanged1.st_ino == unchanged2.st_ino, "没变的文件应是硬链接，不占新空间"
    assert (snap1 / "u1" / "corrections.jsonl").read_text() == "c1\n", (
        "旧快照保留旧版本"
    )
    assert (snap2 / "u1" / "corrections.jsonl").read_text() == "c1\nc2\n"
    assert (tmp_path / "bk" / "latest").resolve() == snap2.resolve()


def test_retention_prunes_only_dated_snapshots(tmp_path):
    source = tmp_path / "users"
    _seed(source)
    root = tmp_path / "bk"
    root.mkdir()
    for name in ("2026-08-01", "2026-08-20", "notes", "latest.tmp"):
        (root / name).mkdir()
    target = backup.Target.parse(str(root))
    assert (
        backup.run_backup(
            source=source, target=target, keep_days=14, today=dt.date(2026, 9, 1)
        )
        == 0
    )
    assert not (root / "2026-08-01").exists(), "超过 14 天的快照应被清理"
    assert (root / "2026-08-20").exists()
    assert (root / "notes").exists(), "非日期目录一律不碰"
    assert (root / "2026-09-01").exists()


def test_preflight_refuses_empty_source(tmp_path):
    source = tmp_path / "users"
    source.mkdir()
    target = backup.Target.parse(str(tmp_path / "bk"))
    assert backup.run_backup(source=source, target=target, keep_days=14) == 2
    assert not (tmp_path / "bk" / "latest").exists()
