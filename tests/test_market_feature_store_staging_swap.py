"""bookgap S7: 行情同步 staging 写 + 原子换库。

判据映射 (spec 2026-08-15-bookgap-s7 §4):
- 判据 1 (并发零失败) → test_readonly_probes_never_fail_during_staged_sync
  对照现状臂 → test_current_behavior_readonly_fails_under_rw_writer
- 判据 2 (crash 安全) → test_sigkill_during_staging_leaves_production_bytes_unchanged
- 判据 3 (收据在场) → test_receipt_row_present_after_swap
- 判据 4 (端到端真同步) 在 live 环境执行, 不在单测里。
真子进程、真文件锁: 除编排函数注入 child_argv 外不打桩。
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import duckdb
import pytest

from market_feature_store import db
from market_feature_store.sync import sync_daily_full as sdf


def _make_db(path: Path, dates: tuple[str, ...] = ("2026-08-13", "2026-08-14")) -> None:
    con = duckdb.connect(str(path))
    try:
        con.execute("CREATE TABLE fact_market_daily (trade_date DATE, total_amount DOUBLE)")
        for d in dates:
            con.execute("INSERT INTO fact_market_daily VALUES (?, 10000)", [d])
    finally:
        con.close()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _child(code: str) -> list[str]:
    return [sys.executable, "-c", code]


# 子进程剧本: 全部从 env 读 staging 路径——与真实 daily-full-exec 同一契约。
CHILD_PRELUDE = (
    "import duckdb, os, sys, time\n"
    "path = os.environ['MARKET_FEATURE_STORE_DB']\n"
    "con = duckdb.connect(path)\n"
    "con.execute('CREATE TABLE IF NOT EXISTS sync_marker (note TEXT)')\n"
    "con.execute(\"INSERT INTO sync_marker VALUES ('written-by-child')\")\n"
    "con.execute(\"INSERT INTO fact_market_daily VALUES ('2026-08-15', 12345)\")\n"
)

CHILD_OK = CHILD_PRELUDE + "con.close()\nsys.exit(0)\n"
CHILD_FAILED_STEP = CHILD_PRELUDE + "con.close()\nsys.exit(1)\n"
CHILD_SELFKILL = CHILD_PRELUDE + (
    "import signal\n"
    "os.kill(os.getpid(), signal.SIGKILL)\n"
)
# 持锁 ~2.5s 模拟长事务同步窗口, 期间主线程对生产路径打只读探针。
CHILD_SLOW = CHILD_PRELUDE + (
    "for _ in range(25):\n"
    "    con.execute(\"INSERT INTO sync_marker VALUES ('tick')\")\n"
    "    time.sleep(0.1)\n"
    "con.close()\nsys.exit(0)\n"
)


@pytest.fixture()
def prod_db(tmp_path, monkeypatch):
    target = tmp_path / "market_feature_store.duckdb"
    _make_db(target)
    monkeypatch.setattr(db, "DB_PATH", target)
    monkeypatch.setattr(db, "DB_DIR", target.parent)
    return target


# ---------------------------------------------------------------------------
# db.py 工具单测
# ---------------------------------------------------------------------------

def test_staging_path_derivation(tmp_path):
    target = tmp_path / "x.duckdb"
    staging = db.staging_path(target)
    assert staging.parent == target.parent  # 同目录=同卷, os.replace 才原子
    assert staging.name == "x.duckdb.staging"


def test_atomic_swap_moves_staging_and_refuses_wal(tmp_path):
    target = tmp_path / "t.duckdb"
    staging = tmp_path / "t.duckdb.staging"
    target.write_bytes(b"old")
    staging.write_bytes(b"new")

    wal = Path(str(staging) + ".wal")
    wal.write_bytes(b"dirty")
    with pytest.raises(RuntimeError, match="WAL"):
        db.atomic_swap_into_place(staging, target)
    assert target.read_bytes() == b"old"
    wal.unlink()

    target_wal = Path(str(target) + ".wal")
    target_wal.write_bytes(b"other-writer")
    with pytest.raises(RuntimeError, match="第三方"):
        db.atomic_swap_into_place(staging, target)
    target_wal.unlink()

    db.atomic_swap_into_place(staging, target)
    assert target.read_bytes() == b"new"
    assert not staging.exists()


def test_remove_stale_staging(tmp_path):
    staging = tmp_path / "t.duckdb.staging"
    assert db.remove_stale_staging(staging) is False
    staging.write_bytes(b"leftover")
    Path(str(staging) + ".wal").write_bytes(b"leftover-wal")
    assert db.remove_stale_staging(staging) is True
    assert not staging.exists()
    assert not Path(str(staging) + ".wal").exists()


def test_probe_no_active_writer_detects_cross_process_lock(tmp_path):
    target = tmp_path / "t.duckdb"
    _make_db(target)
    db.probe_no_active_writer(target)  # 无写者: 不抛

    ready = tmp_path / "ready"
    holder = subprocess.Popen(_child(
        "import duckdb, sys, time, pathlib\n"
        f"con = duckdb.connect({str(target)!r})\n"
        f"pathlib.Path({str(ready)!r}).touch()\n"
        "time.sleep(30)\n"
    ))
    try:
        deadline = time.monotonic() + 15
        while not ready.exists():
            assert time.monotonic() < deadline, "rw 持锁子进程未就绪"
            time.sleep(0.05)
        with pytest.raises(db.DatabaseLockedError):
            db.probe_no_active_writer(target)
    finally:
        holder.kill()
        holder.wait()


# ---------------------------------------------------------------------------
# 编排: 成功路径 / 收据 (判据 3 的离线臂)
# ---------------------------------------------------------------------------

def test_receipt_row_present_after_swap(prod_db):
    result = sdf.run_daily_full_staged(child_argv=_child(CHILD_OK))
    assert result["swapped"] is True
    assert result["rc"] == 0
    assert result["copy"]["method"] in ("clonefile", "copy")
    assert not Path(result["staging"]).exists()

    con = duckdb.connect(str(prod_db), read_only=True)
    try:
        assert con.execute("SELECT count(*) FROM sync_marker").fetchone()[0] == 1
        row = con.execute(
            """
            SELECT run_id, kind, plan, ok, pid, child_pid,
                   started_at, finished_at, rows_summary, copy_method
            FROM ops_sync_run
            """
        ).fetchone()
    finally:
        con.close()
    run_id, kind, plan, ok, pid, child_pid, started, finished, rows_json, method = row
    assert run_id == result["run_id"]
    assert (kind, plan, ok) == ("daily-full", "staging-swap", True)
    assert pid == os.getpid() and child_pid == result["child_pid"]
    assert started is not None and finished is not None
    assert json.loads(rows_json)["fact_market_daily"] == 3  # 2 行克隆 + 1 行子进程
    assert method == result["copy"]["method"]


def test_failed_step_still_lands_like_today(prod_db):
    """现状口径: 失败步不回滚已提交写入——子进程 rc=1 仍换库, 出口 rc=1。"""
    result = sdf.run_daily_full_staged(child_argv=_child(CHILD_FAILED_STEP))
    assert result["swapped"] is True
    assert result["rc"] == 1
    con = duckdb.connect(str(prod_db), read_only=True)
    try:
        assert con.execute("SELECT ok FROM ops_sync_run").fetchone()[0] is False
    finally:
        con.close()


def test_fresh_database_bootstrap(tmp_path, monkeypatch):
    target = tmp_path / "fresh.duckdb"
    monkeypatch.setattr(db, "DB_PATH", target)
    monkeypatch.setattr(db, "DB_DIR", target.parent)
    code = (
        "import duckdb, os, sys\n"
        "con = duckdb.connect(os.environ['MARKET_FEATURE_STORE_DB'])\n"
        "con.execute('CREATE TABLE fact_market_daily (trade_date DATE, total_amount DOUBLE)')\n"
        "con.close()\nsys.exit(0)\n"
    )
    result = sdf.run_daily_full_staged(child_argv=_child(code))
    assert result["swapped"] is True and result["copy"] is None
    assert target.exists()


# ---------------------------------------------------------------------------
# 判据 1: 同步进行中, 生产路径 read_only 连接零失败 (离线臂)
# ---------------------------------------------------------------------------

def test_readonly_probes_never_fail_during_staged_sync(prod_db):
    outcome: dict = {}

    def _run():
        outcome["result"] = sdf.run_daily_full_staged(child_argv=_child(CHILD_SLOW))

    worker = threading.Thread(target=_run)
    worker.start()
    probes = 0
    failures: list[str] = []
    while worker.is_alive():
        try:
            con = duckdb.connect(str(prod_db), read_only=True)
            con.execute("SELECT count(*) FROM fact_market_daily").fetchone()
            con.close()
            probes += 1
        except Exception as exc:  # 判据要求零失败, 全量记录
            failures.append(repr(exc))
        time.sleep(0.05)
    worker.join()

    assert failures == []
    assert probes >= 10, f"探针样本过少 ({probes}), 未覆盖同步窗口"
    assert outcome["result"]["swapped"] is True
    # 换名后新连接读到新库
    con = duckdb.connect(str(prod_db), read_only=True)
    try:
        assert con.execute("SELECT count(*) FROM sync_marker").fetchone()[0] >= 1
    finally:
        con.close()


def test_current_behavior_readonly_fails_under_rw_writer(tmp_path):
    """现状对照臂: rw 写者持锁期间, 跨进程 read_only 连接立即失败。

    这是 2026-08-15 晨 批 #2 塌方的最小复现 (锁语义前提), 若 duckdb
    未来放开多进程并发使本测试失败, staging 方案可以退役。
    """
    target = tmp_path / "t.duckdb"
    _make_db(target)
    holder = duckdb.connect(str(target))  # rw 持锁 (模拟旧 daily-full)
    try:
        probe = subprocess.run(
            _child(
                "import duckdb, sys\n"
                f"duckdb.connect({str(target)!r}, read_only=True)\n"
            ),
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert probe.returncode != 0
        assert "lock" in probe.stderr.lower()
    finally:
        holder.close()
    # 写者收工后同一探针立即成功
    probe = subprocess.run(
        _child(
            "import duckdb, sys\n"
            f"duckdb.connect({str(target)!r}, read_only=True)\n"
        ),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert probe.returncode == 0


# ---------------------------------------------------------------------------
# 判据 2: crash 安全 (kill -9 不留半成品在生产路径)
# ---------------------------------------------------------------------------

def test_sigkill_during_staging_leaves_production_bytes_unchanged(prod_db):
    before = _sha256(prod_db)
    result = sdf.run_daily_full_staged(child_argv=_child(CHILD_SELFKILL))
    assert result["swapped"] is False
    assert result["rc"] == 2
    assert "信号" in result["reason"]
    assert _sha256(prod_db) == before  # 字节不变
    con = duckdb.connect(str(prod_db), read_only=True)  # 且可正常打开
    try:
        assert con.execute("SELECT count(*) FROM fact_market_daily").fetchone()[0] == 2
    finally:
        con.close()
    # 残留 staging 由下一轮开工清理
    assert Path(result["staging"]).exists()
    result2 = sdf.run_daily_full_staged(child_argv=_child(CHILD_OK))
    assert result2["stale_staging_removed"] is True
    assert result2["swapped"] is True


# ---------------------------------------------------------------------------
# 第三方写者守卫 (换名不覆盖同步期间的旁路写入)
# ---------------------------------------------------------------------------

def test_third_party_writer_guard_blocks_swap(prod_db):
    # 子进程既扮演同步写者 (写 staging), 又扮演第三方 (改生产库):
    # 模拟同步窗口内 backfill 等旁路写者落笔。
    code = CHILD_PRELUDE + (
        "con.close()\n"
        f"third = duckdb.connect({str(prod_db)!r})\n"
        "third.execute(\"INSERT INTO fact_market_daily VALUES ('2026-08-12', 1)\")\n"
        "third.close()\n"
        "sys.exit(0)\n"
    )
    before_rows = 2
    result = sdf.run_daily_full_staged(child_argv=_child(code))
    assert result["swapped"] is False
    assert result["rc"] == 2
    assert "第三方写者守卫" in result["reason"]
    con = duckdb.connect(str(prod_db), read_only=True)
    try:
        # 生产库保留第三方写入 (3 行), 未被 staging (含 2026-08-15) 覆盖
        rows = con.execute("SELECT count(*) FROM fact_market_daily").fetchone()[0]
        tables = [r[0] for r in con.execute("SHOW TABLES").fetchall()]
    finally:
        con.close()
    assert rows == before_rows + 1
    assert "sync_marker" not in tables
    assert Path(result["staging"]).exists()  # 留作取证
