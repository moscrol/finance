"""换库锁跨平台自检：结论要和真实后果一致，自检出错按「不排」处理，每进程只测一次。

背景（2026-09-30 质检 P2）：hold_swap_lock 用 flock，duckdb 的写者锁是 POSIX 记录锁。
两者只在 macOS 上互斥；Linux 上换库锁形同虚设，而测试此前只是「在 Linux 上红 6 条」，
没有任何东西把这件事说成一句话。
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import duckdb
import pytest

from market_feature_store import db

REPO = Path(__file__).resolve().parents[1]


def test_probe_reports_both_directions():
    result = db.swap_lock_platform_probe()
    assert result["platform"] == sys.platform
    assert isinstance(result["writer_blocks_lock"], bool)
    assert isinstance(result["lock_blocks_writer"], bool)
    assert result["excludes_writers"] == (result["writer_blocks_lock"] and result["lock_blocks_writer"])
    if sys.platform == "darwin":
        # 生产平台：排他必须成立。这里红 = Mac 上换库锁也排不掉跨进程写者，是真缺陷。
        assert result["excludes_writers"], result
    if sys.platform.startswith("linux"):
        assert not result["excludes_writers"], "Linux 上 flock 与 POSIX 记录锁互不相干"


def test_probe_agrees_with_the_real_consequence(tmp_path):
    """持换库锁期间，另一个进程的写入落不落得了库——结论必须与自检一致。"""

    target = tmp_path / "prod.duckdb"
    con = duckdb.connect(str(target))
    con.execute("CREATE TABLE t (v INTEGER)")
    con.close()
    writer = (
        "import sys, duckdb\n"
        "try:\n"
        "    c = duckdb.connect(sys.argv[1]); c.execute('INSERT INTO t VALUES (17000)'); c.close()\n"
        "except duckdb.IOException:\n"
        "    pass\n"
    )
    with db.hold_swap_lock(target):
        subprocess.run([sys.executable, "-c", writer, str(target)], check=True, timeout=60)
    landed = duckdb.connect(str(target), read_only=True).execute("SELECT count(*) FROM t").fetchone()[0]
    assert (landed == 0) == db.swap_lock_platform_probe()["lock_blocks_writer"]


@pytest.mark.parametrize(
    ("child", "needle"),
    [
        ("print('NOPE', flush=True)", "没拿到写者连接"),
        ("import time; time.sleep(30)", "(超时)"),
    ],
)
def test_probe_fails_closed_when_the_child_misbehaves(monkeypatch, child, needle):
    monkeypatch.setattr(db, "_SWAP_LOCK_PROBE_CHILD", child)
    result = db.swap_lock_platform_probe(timeout=1.0)
    assert result["excludes_writers"] is False
    assert "自检没做完" in result["detail"] and needle in result["detail"]


def test_verdict_is_measured_once_per_process(monkeypatch):
    calls = []

    def fake_probe(**_kwargs):
        calls.append(1)
        return {"excludes_writers": True}

    monkeypatch.setattr(db, "_SWAP_LOCK_VERDICT", [])
    monkeypatch.setattr(db, "swap_lock_platform_probe", fake_probe)
    assert db.swap_lock_excludes_writers() is True
    assert db.swap_lock_excludes_writers() is True
    assert calls == [1]


def test_cli_exit_code_follows_the_verdict():
    proc = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "check_swap_lock_platform.py"), "--json"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    verdict = json.loads(proc.stdout)
    assert proc.returncode == (0 if verdict["excludes_writers"] else 1)
