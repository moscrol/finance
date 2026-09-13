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
    "import duckdb, json, os, pathlib, sys, time\n"
    "path = os.environ['MARKET_FEATURE_STORE_DB']\n"
    "con = duckdb.connect(path)\n"
    "con.execute('CREATE TABLE IF NOT EXISTS sync_marker (note TEXT)')\n"
    "con.execute(\"INSERT INTO sync_marker VALUES ('written-by-child')\")\n"
    "con.execute(\"INSERT INTO fact_market_daily VALUES ('2026-08-15', 12345)\")\n"
)
CHILD_WRITE_STATUS = (
    "pathlib.Path(path + '.status.json').write_text("
    "json.dumps({'trade_date': '2026-08-15', 'ok': True, 'steps': [], "
    "'run_id': os.environ.get('MARKET_FEATURE_STORE_RUN_ID')}))\n"
)

CHILD_OK = CHILD_PRELUDE + "con.close()\n" + CHILD_WRITE_STATUS + "sys.exit(0)\n"
# 崩了没交 status.json: 编排必须 fail-closed, 不得按 rc=1 换库。
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
    "con.close()\n"
) + CHILD_WRITE_STATUS + "sys.exit(0)\n"


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


def test_receipt_kind_reflects_custom_child(prod_db):
    """修复类调用方传 kind → 收据不落 \"daily-full\" 冒充日更管道。"""
    result = sdf.run_daily_full_staged(
        child_argv=_child(CHILD_OK), kind="repair-stock-daily-hithink"
    )
    assert result["swapped"] is True
    con = duckdb.connect(str(prod_db), read_only=True)
    try:
        kind = con.execute("SELECT kind FROM ops_sync_run").fetchone()[0]
    finally:
        con.close()
    assert kind == "repair-stock-daily-hithink"


def test_failed_step_still_lands_like_today(prod_db):
    """现状口径: 失败步不回滚已提交写入——子进程 rc=1 仍换库, 出口 rc=1。

    与「进程崩了没写 status.json」区分: 后者走 fail-closed, 见下一测。
    """
    # 真 daily-full-exec 在收笔时写 status.json; 这里模拟「管道跑完但有失败步」。
    code = CHILD_FAILED_STEP.replace(
        "sys.exit(1)\n",
        (
            "import json, pathlib\n"
            "p = pathlib.Path(path + '.status.json')\n"
            "p.write_text(json.dumps({'trade_date': '2026-08-15', 'ok': False, 'steps': [], "
            "'run_id': os.environ.get('MARKET_FEATURE_STORE_RUN_ID')}))\n"
            "sys.exit(1)\n"
        ),
    )
    result = sdf.run_daily_full_staged(child_argv=_child(code))
    assert result["swapped"] is True
    assert result["rc"] == 1
    con = duckdb.connect(str(prod_db), read_only=True)
    try:
        assert con.execute("SELECT ok FROM ops_sync_run").fetchone()[0] is False
    finally:
        con.close()


def test_crash_without_status_json_does_not_swap(prod_db):
    """子进程异常退出且没交 status.json = 没跑完, 不得按 rc=1 换库。

    2026-08-15 实测: worktree 缺 shared/feishu_utils, 子进程 import 期崩,
    旧逻辑把 rc=1 当成「失败步仍落库」换了名——收据在、数据没动, 但语义错。
    """
    before = _sha256(prod_db)
    result = sdf.run_daily_full_staged(child_argv=_child(CHILD_FAILED_STEP))
    assert result["swapped"] is False
    assert result["rc"] == 2
    assert "status.json" in result["reason"]
    assert _sha256(prod_db) == before


def test_fresh_database_bootstrap(tmp_path, monkeypatch):
    target = tmp_path / "fresh.duckdb"
    monkeypatch.setattr(db, "DB_PATH", target)
    monkeypatch.setattr(db, "DB_DIR", target.parent)
    code = (
        "import duckdb, json, os, pathlib, sys\n"
        "path = os.environ['MARKET_FEATURE_STORE_DB']\n"
        "con = duckdb.connect(path)\n"
        "con.execute('CREATE TABLE fact_market_daily (trade_date DATE, total_amount DOUBLE)')\n"
        "con.close()\n"
        "pathlib.Path(path + '.status.json').write_text("
        "json.dumps({'trade_date': '2026-08-15', 'ok': True, 'steps': [], "
        "'run_id': os.environ.get('MARKET_FEATURE_STORE_RUN_ID')}))\n"
        "sys.exit(0)\n"
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
        + CHILD_WRITE_STATUS
        + f"third = duckdb.connect({str(prod_db)!r})\n"
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


# ---------------------------------------------------------------------------
# QC S4（2026-09-13）：换名前可验明备份（修复类调用方的执行前提）
# ---------------------------------------------------------------------------


def test_pre_swap_backup_created_with_fingerprint_and_receipt(prod_db):
    pre_swap_sha = _sha256(prod_db)
    result = sdf.run_daily_full_staged(
        child_argv=_child(CHILD_OK), pre_swap_backup=True
    )
    assert result["swapped"] is True
    backup = result["backup"]
    assert backup is not None
    backup_path = Path(backup["backup_path"])
    assert backup_path.exists()
    # 指纹与换库前状态一致（备份拷的是守卫验过的待换库状态）
    assert backup["backup_sha256"] == _sha256(backup_path) == pre_swap_sha
    assert backup["source_size_bytes"] == backup["backup_bytes"]
    # 收据带恢复步骤，且备份只读打开能看到换库前内容（无 sync_marker）
    receipt = json.loads(
        Path(str(backup_path) + ".receipt.json").read_text(encoding="utf-8")
    )
    assert receipt["kind"] == "pre-swap-backup"
    assert receipt["run_id"] == result["run_id"]
    assert any("cp -c" in step for step in receipt["restore_steps"])
    con = duckdb.connect(str(backup_path), read_only=True)
    try:
        assert con.execute(
            "SELECT count(*) FROM fact_market_daily"
        ).fetchone()[0] == 2
        assert con.execute(
            "SELECT count(*) FROM information_schema.tables"
            " WHERE table_name='sync_marker'"
        ).fetchone()[0] == 0
    finally:
        con.close()


def test_pre_swap_backup_default_off(prod_db):
    """日更默认不备份（每晚 3.6G 级文件会打爆磁盘）。"""
    result = sdf.run_daily_full_staged(child_argv=_child(CHILD_OK))
    assert result["swapped"] is True
    assert result["backup"] is None
    assert list(prod_db.parent.glob("*.bak-*")) == []


def test_pre_swap_backup_failure_blocks_swap(prod_db, monkeypatch):
    """备份失败 → fail closed 不换名，生产库字节不动。"""
    pre = _sha256(prod_db)

    def _boom(*_a, **_k):
        raise RuntimeError("disk full")

    monkeypatch.setattr(db, "backup_before_swap", _boom)
    result = sdf.run_daily_full_staged(
        child_argv=_child(CHILD_OK), pre_swap_backup=True
    )
    assert result["swapped"] is False
    assert result["rc"] == 2
    assert "备份失败" in result["reason"]
    assert _sha256(prod_db) == pre


# ---------------------------------------------------------------- QC 复审二轮 P1


def test_stale_status_from_previous_round_does_not_swap(prod_db):
    """QC stale-status-min 复现的反向版本：预置上一轮成功 status，
    本轮子进程 rc=1 且不写 status —— 父进程不得误读旧 JSON 换库。"""
    staging = db.staging_path(prod_db)
    before = _sha256(prod_db)
    Path(str(staging) + ".status.json").write_text(
        json.dumps({"trade_date": "2026-08-15", "ok": True, "steps": []})
    )
    result = sdf.run_daily_full_staged(
        trade_date="2026-08-15",
        child_argv=_child(CHILD_PRELUDE + "con.close()\nsys.exit(1)\n"),
    )
    assert result["rc"] == 2
    assert result["swapped"] is False
    assert result["stale_status_removed"] is True  # 开工即删旧 status
    assert _sha256(prod_db) == before
    con = duckdb.connect(str(prod_db), read_only=True)
    try:
        assert "sync_marker" not in {
            r[0] for r in con.execute("SHOW TABLES").fetchall()
        }
    finally:
        con.close()


def test_status_run_id_mismatch_refused(prod_db):
    """子进程写了 status 但 run_id 对不上本轮（错轮/伪造）→ 不换库。"""
    before = _sha256(prod_db)
    code = (
        CHILD_PRELUDE
        + "pathlib.Path(path + '.status.json').write_text("
          "json.dumps({'trade_date': '2026-08-15', 'ok': True, 'steps': [], "
          "'run_id': 'bogus-run-id'}))\n"
        + "con.close()\n"
    )
    result = sdf.run_daily_full_staged(
        trade_date="2026-08-15", child_argv=_child(code)
    )
    assert result["rc"] == 2
    assert result["swapped"] is False
    assert "run_id" in result["reason"]
    assert _sha256(prod_db) == before


def test_hold_swap_lock_excludes_writers_allows_readers(tmp_path):
    """换库锁是 SH：排写不排读（S7 判据 1 不因换库锁破坏）。"""
    target = tmp_path / "prod.duckdb"
    _make_db(target)
    with db.hold_swap_lock(target):
        with pytest.raises(duckdb.IOException):
            duckdb.connect(str(target))  # rw 写者进不来
        ro = duckdb.connect(str(target), read_only=True)  # 读者照常
        ro.close()
    con = duckdb.connect(str(target))  # 锁释放后写者立即可进
    con.close()


def test_hold_swap_lock_senses_active_writer(tmp_path):
    """duckdb rw 写者在场时换库锁获取失败（获取时刻即能感知写者）。"""
    target = tmp_path / "prod.duckdb"
    _make_db(target)
    writer = duckdb.connect(str(target))
    try:
        with pytest.raises(db.DatabaseLockedError):
            with db.hold_swap_lock(target):
                pass
    finally:
        writer.close()


def test_clone_window_write_cannot_land(prod_db, monkeypatch):
    """QC 复审三轮 P1-1 复现的反向：克隆与基线在同一锁窗口内，窗口写不进。

    QC 原复现：克隆(10000) → 第三方提交(17000) → 基线误记 17000 → 换入
    10000，写入被静默撤销。修复后窗口内第三方 rw 打开必失败；窗口外
    （子进程阶段）的写入仍由末端 stat 守卫兜底
    （test_third_party_writer_guard_blocks_swap）。"""
    attack: dict = {}
    real_clone = db.clone_to_staging

    def clone_then_attack(src, dst):
        copy = real_clone(src, dst)
        try:
            con = duckdb.connect(str(src))
            con.execute("INSERT INTO fact_market_daily VALUES ('2026-08-14', 17000)")
            con.close()
            attack["landed"] = True
        except duckdb.IOException as exc:
            attack["landed"] = False
            attack["error"] = str(exc)
        return copy

    monkeypatch.setattr(db, "clone_to_staging", clone_then_attack)
    result = sdf.run_daily_full_staged(
        trade_date="2026-08-15",
        child_argv=_child(CHILD_OK),
        pre_swap_backup=True,
    )
    assert result["swapped"] is True, result["reason"]
    assert attack["landed"] is False  # 基线窗口内攻击必失败
    con = duckdb.connect(str(prod_db), read_only=True)
    try:
        assert con.execute(
            "SELECT COUNT(*) FROM fact_market_daily WHERE total_amount=17000"
        ).fetchone()[0] == 0
    finally:
        con.close()


def test_run_mutex_refuses_second_round_before_any_cleanup(prod_db):
    """外部占住运行互斥锁 → 新一轮在任何清理之前被拒，现场原样保留。"""
    import fcntl

    lock_path = Path(str(prod_db) + ".run.lock")
    leftover = Path(str(db.staging_path(prod_db)) + ".status.json")
    leftover.write_text("{}")  # 模拟上一轮在现场的遗留；若清理会发生它会被删
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o644)
    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    before = _sha256(prod_db)
    try:
        result = sdf.run_daily_full_staged(
            trade_date="2026-08-15", child_argv=_child(CHILD_OK)
        )
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)
        lock_path.unlink(missing_ok=True)
    assert result["rc"] == 2
    assert result["swapped"] is False
    assert "互斥" in result["reason"]
    assert leftover.exists()  # 任何清理都未发生
    assert _sha256(prod_db) == before


def test_concurrent_rounds_serialize(prod_db):
    """QC 复审三轮 P1-2 复现的反向：A 跑长事务期间 B 开工 → B 立即 rc=2，
    A 正常发布自己的 staging（最终库是 A 的成功产物，不是 B 的半成品）。"""
    outcome: dict = {}

    def run_a():
        outcome["a"] = sdf.run_daily_full_staged(
            trade_date="2026-08-15", child_argv=_child(CHILD_SLOW)
        )

    t = threading.Thread(target=run_a)
    t.start()
    time.sleep(1.0)  # A 已过克隆，子进程正在写 staging
    b = sdf.run_daily_full_staged(
        trade_date="2026-08-15", child_argv=_child(CHILD_OK)
    )
    t.join(timeout=60)
    a = outcome["a"]
    assert b["rc"] == 2 and b["swapped"] is False and "互斥" in b["reason"]
    assert a["swapped"] is True, a["reason"]
    con = duckdb.connect(str(prod_db), read_only=True)
    try:
        assert con.execute(
            "SELECT COUNT(*) FROM fact_market_daily WHERE trade_date='2026-08-15'"
        ).fetchone()[0] == 1  # A 的行在
        assert "sync_marker" in {
            r[0] for r in con.execute("SHOW TABLES").fetchall()
        }
    finally:
        con.close()


def test_malformed_status_json_refused(prod_db):
    """status 内容为 '{'：解析失败 → 明确 rc=2 拒绝，不抛异常不换库。"""
    before = _sha256(prod_db)
    code = (
        CHILD_PRELUDE
        + "con.close()\n"
        + "pathlib.Path(path + '.status.json').write_text('{')\n"
    )
    result = sdf.run_daily_full_staged(
        trade_date="2026-08-15", child_argv=_child(code)
    )
    assert result["rc"] == 2
    assert result["swapped"] is False
    assert "解析失败" in result["reason"]
    assert _sha256(prod_db) == before


def test_non_object_status_refused(prod_db):
    """status 内容为 '[1]'：不是对象 → 明确 rc=2 拒绝，不抛 AttributeError。"""
    before = _sha256(prod_db)
    code = (
        CHILD_PRELUDE
        + "con.close()\n"
        + "pathlib.Path(path + '.status.json').write_text('[1]')\n"
    )
    result = sdf.run_daily_full_staged(
        trade_date="2026-08-15", child_argv=_child(code)
    )
    assert result["rc"] == 2
    assert result["swapped"] is False
    assert "不是 JSON 对象" in result["reason"]
    assert _sha256(prod_db) == before


def test_swap_lock_contention_aborts_before_any_write(prod_db, monkeypatch):
    """换库锁拿不到（任一窗口）→ rc=2，不动生产库。"""
    def _busy(_path):
        raise db.DatabaseLockedError("simulated contention")

    monkeypatch.setattr(db, "hold_swap_lock", _busy)
    before = _sha256(prod_db)
    result = sdf.run_daily_full_staged(
        trade_date="2026-08-15",
        child_argv=_child(CHILD_OK),
        pre_swap_backup=True,
    )
    assert result["rc"] == 2
    assert result["swapped"] is False
    assert "锁" in result["reason"]
    assert _sha256(prod_db) == before


def test_third_party_write_during_backup_window_cannot_land(prod_db, monkeypatch):
    """QC backup-race 复现的反向版本：备份→换名全程持锁，第三方写不进。

    攻击脚本在备份刚完成的瞬间 rw 打开生产库试图提交一行；锁内该打开
    必失败（flock 互斥，本机实测）。换库完成后新库不含攻击行——不再存在
    「写进去了却被静默覆盖」。"""
    attack_outcome: dict = {}
    real_backup = db.backup_before_swap

    def backup_then_attack(target, *, run_id, writer_lock_held=False):
        receipt = real_backup(target, run_id=run_id, writer_lock_held=writer_lock_held)
        try:
            con = duckdb.connect(str(target))
            con.execute("CREATE TABLE third_party (note TEXT)")
            con.execute("INSERT INTO third_party VALUES ('raced')")
            con.close()
            attack_outcome["landed"] = True
        except duckdb.IOException as exc:
            attack_outcome["landed"] = False
            attack_outcome["error"] = str(exc)
        return receipt

    monkeypatch.setattr(db, "backup_before_swap", backup_then_attack)
    result = sdf.run_daily_full_staged(
        trade_date="2026-08-15",
        child_argv=_child(CHILD_OK),
        pre_swap_backup=True,
    )
    assert result["swapped"] is True, result["reason"]
    assert attack_outcome["landed"] is False  # 锁内攻击必然失败
    con = duckdb.connect(str(prod_db), read_only=True)
    try:
        assert "third_party" not in {
            r[0] for r in con.execute("SHOW TABLES").fetchall()
        }
    finally:
        con.close()


# ---------------------------------------------------------------- QC 复审四轮 P1
#
# 四轮复现：临界区只有 pre_swap_backup=True 才进换库锁，日更默认
# （pre_swap_backup=False）走的是「最终守卫 → 无锁 os.replace」。守卫与使用之间
# 是裸窗口，第三方 rw 在窗口内提交 17000，编排照样 rc=0/swapped=true，新库却不含
# 17000——写入已提交、被换名静默覆盖。下面两测把窗口两端各钉一次：
#   - 不带备份的写者竞态（本节第一测）→ 锁必须与备份解耦；
#   - 目标路径被整文件替换（后三测）→ flock 锁 inode、检查与换名走路径，
#     两者必须确认是同一个身份。


def test_third_party_write_before_swap_without_backup_cannot_land(prod_db, monkeypatch):
    """日更口径（pre_swap_backup=False）：最终守卫之后、换名之前的窗口也排写。

    注入点就是 QC 指定的那一刻——守卫已过、os.replace 未发。验收判据取 QC 的
    反向表述：不得出现「rc=0 + swapped=true + 写入静默丢失」。
    """
    attack: dict = {}
    real_swap = db.atomic_swap_into_place

    # **kwargs 透传而不是写死 expect_identity: 这一测要能在「修复前」的代码上
    # 因为**行为**变红（写入落地后被静默覆盖），而不是因为签名对不上变红。
    def attack_then_swap(staging, target, **kwargs):
        try:
            con = duckdb.connect(str(target))
            con.execute("INSERT INTO fact_market_daily VALUES ('2026-08-14', 17000)")
            con.close()
            attack["landed"] = True
        except duckdb.IOException as exc:
            attack["landed"] = False
            attack["error"] = str(exc)
        return real_swap(staging, target, **kwargs)

    monkeypatch.setattr(db, "atomic_swap_into_place", attack_then_swap)
    result = sdf.run_daily_full_staged(
        trade_date="2026-08-15", child_argv=_child(CHILD_OK)
    )
    assert result["backup"] is None  # 确实跑在日更那条路径上

    con = duckdb.connect(str(prod_db), read_only=True)
    try:
        survived = con.execute(
            "SELECT COUNT(*) FROM fact_market_daily WHERE total_amount=17000"
        ).fetchone()[0]
    finally:
        con.close()

    # 判据（与机制无关）：已提交的第三方写入不得被静默吞掉。
    assert not (attack["landed"] and result["swapped"] and survived == 0), (
        "日更换库窗口丢写: 第三方已提交 17000，编排仍 "
        f"rc={result['rc']} swapped={result['swapped']}，新库不含该行"
    )
    # 本设计的实现口径：锁内第三方 rw 根本打不开，压根落不了笔。
    assert attack["landed"] is False, attack.get("error")
    assert result["swapped"] is True, result["reason"]
    assert survived == 0


def test_swap_refused_when_target_replaced_by_another_inode(prod_db, tmp_path, monkeypatch):
    """路径身份变异：换名前最后一刻 target 被换成另一个 inode → 拒绝换名。

    mtime/size 挡不住这一类——cp -c / copy2 会把 mtime 一并带过去，造一个版本
    读数完全一致的新 inode 是可行的。这里直接把冒名文件 os.replace 到生产路径
    上（我方持的 SH 锁锁的是旧 inode，拦不住 rename），验证末端身份守卫接住。
    """
    impostor_src = tmp_path / "impostor.duckdb"
    _make_db(impostor_src, dates=("2026-08-20",))
    impostor_sha = _sha256(impostor_src)
    real_swap = db.atomic_swap_into_place

    def replace_then_swap(staging, target, **kwargs):  # **kwargs: 同上, 为红得对
        os.replace(impostor_src, target)  # 同路径, 换了 inode
        return real_swap(staging, target, **kwargs)

    monkeypatch.setattr(db, "atomic_swap_into_place", replace_then_swap)
    result = sdf.run_daily_full_staged(
        trade_date="2026-08-15", child_argv=_child(CHILD_OK)
    )
    assert result["swapped"] is False
    assert result["rc"] == 2
    assert "身份" in result["reason"]
    # 冒名者的字节原样还在——我们没覆盖一个不是自己基线的文件
    assert _sha256(prod_db) == impostor_sha
    assert Path(result["staging"]).exists()  # staging 留作取证


def test_atomic_swap_refuses_on_identity_mismatch(tmp_path):
    """db 层单测：expect_identity 对不上 → SwapTargetReplacedError, 不覆盖。"""
    target = tmp_path / "t.duckdb"
    staging = tmp_path / "t.duckdb.staging"
    target.write_bytes(b"baseline")
    staging.write_bytes(b"new")
    baseline_identity = db.file_identity(target)

    impostor = tmp_path / "impostor"
    impostor.write_bytes(b"impostor")
    os.replace(impostor, target)
    assert db.file_identity(target) != baseline_identity

    with pytest.raises(db.SwapTargetReplacedError, match="路径身份已变"):
        db.atomic_swap_into_place(staging, target, expect_identity=baseline_identity)
    assert target.read_bytes() == b"impostor"  # 未被覆盖
    assert staging.exists()

    # 目标整个消失同样拒绝（os.replace 本会闷声新建一个）
    vanished_identity = db.file_identity(target)
    target.unlink()
    with pytest.raises(db.SwapTargetReplacedError, match="已不存在"):
        db.atomic_swap_into_place(staging, target, expect_identity=vanished_identity)
    assert not target.exists()

    # 身份对得上时照常换名
    target.write_bytes(b"impostor")
    db.atomic_swap_into_place(
        staging, target, expect_identity=db.file_identity(target)
    )
    assert target.read_bytes() == b"new"


def test_hold_swap_lock_yields_locked_inode_identity(tmp_path):
    """锁 fd 的身份要能被调用方拿到, 才能跟检查/换名对齐到同一个目标。

    .stat() 读的是被锁 inode 自身 (fstat): 路径 stat 拿到的可能已经是别人换
    上来的文件, 基线版本必须从锁定的那个 inode 读 (QC 复审五轮)。
    """
    target = tmp_path / "prod.duckdb"
    _make_db(target)
    with db.hold_swap_lock(target) as lock:
        assert lock.identity == db.file_identity(target)
        db.assert_same_target(target, lock.identity, stage="自测")
        assert lock.stat().st_ino == lock.ino
        assert lock.stat().st_size == target.stat().st_size


# ---------------------------------------------------------------- QC 复审五轮
#
# 五轮三项：P1 身份检查与 os.replace 非原子（收窄声明 + 钉住边界）、
# P2 target 被删时 FileNotFoundError 逃逸编排、基线阶段没用上锁 yield 的身份。


def test_identity_check_and_replace_are_not_atomic(tmp_path, monkeypatch):
    """⚠️ 本测试断言的是一条**已声明的边界**, 不是期望行为。

    身份检查与 os.replace 是两条相邻语句, 不是一个原子操作。不拿锁的第三方
    （mv/cp）在「检查之后、换名之前」把冒名文件换到目标路径上, 仍会被覆盖。
    POSIX 没有「比对 inode 再换名」的原子原语（renamex_np(RENAME_SWAP) 只保
    证交换本身原子, RENAME_EXCL 只判存在与否）, 详见 db.py 顶部威胁模型。

    对照: 替换发生在检查**之前**时是能拒绝的, 见
    test_atomic_swap_refuses_on_identity_mismatch。expect_identity 的价值到此
    为止——把一类静默覆盖变成明确拒绝, 不是原子发布。

    **若哪天真把这个窗口闭合了, 本测试必须改, 并同步改 db.py 顶部威胁模型、
    atomic_swap_into_place 的 docstring 与交接里的措辞。**
    """
    target = tmp_path / "t.duckdb"
    staging = tmp_path / "t.duckdb.staging"
    impostor = tmp_path / "impostor"
    target.write_bytes(b"baseline")
    staging.write_bytes(b"new")
    impostor.write_bytes(b"impostor")
    identity = db.file_identity(target)

    real_replace = os.replace

    def race(src, dst):
        # 攻击点严格在最终身份检查之后: 此刻 assert_same_target 已经放行。
        real_replace(impostor, target)
        return real_replace(src, dst)

    monkeypatch.setattr(os, "replace", race)
    db.atomic_swap_into_place(staging, target, expect_identity=identity)
    monkeypatch.undo()

    # 边界成立: 冒名者被覆盖了。这正是当前实现做不到、也没有声称做到的部分。
    assert target.read_bytes() == b"new"
    assert not impostor.exists()


def test_target_deleted_before_lock_returns_rc2_not_traceback(prod_db, monkeypatch):
    """QC 五轮 P2：锁外守卫通过后 target 被删 → 结构化 rc=2, 不能抛裸异常。

    复现窗口: 最终守卫已过 → 第三方 unlink → hold_swap_lock 的 os.open 抛
    FileNotFoundError。编排只捕 DatabaseLockedError 家族, 裸 FileNotFoundError
    会直接逃出 run_daily_full_staged, 违反 fail-closed 合同。
    """
    real_probe = db.probe_no_active_writer
    calls = {"n": 0}

    def probe_then_delete(path):
        real_probe(path)
        calls["n"] += 1
        if calls["n"] == 2:  # 第 2 次 = 锁外最终守卫, 正好在拿锁之前
            os.unlink(path)

    monkeypatch.setattr(db, "probe_no_active_writer", probe_then_delete)
    result = sdf.run_daily_full_staged(  # 不得抛异常
        trade_date="2026-08-15", child_argv=_child(CHILD_OK)
    )
    assert calls["n"] >= 2, "守卫未被触达, 窗口没对上"
    assert result["rc"] == 2
    assert result["swapped"] is False
    assert "不存在" in result["reason"]
    assert not prod_db.exists()  # 我们没有把库「重建」出来掩盖删除


def test_clone_window_replacement_detected_at_baseline(prod_db, tmp_path, monkeypatch):
    """QC 五轮第三项：基线身份必须来自锁, 并在克隆之后复查。

    「锁住 A → 克隆 A → 路径被换成 B → 从路径 stat 得到 B」会让 staging 是 A
    的副本、基线却记成 B, 两边都不自知。复查点在克隆之后。
    """
    impostor_src = tmp_path / "impostor.duckdb"
    _make_db(impostor_src, dates=("2026-08-20",))
    impostor_sha = _sha256(impostor_src)
    real_clone = db.clone_to_staging

    def clone_then_replace(src, dst):
        copy = real_clone(src, dst)
        os.replace(impostor_src, src)  # 克隆窗口内整文件替换（flock 拦不住 rename）
        return copy

    monkeypatch.setattr(db, "clone_to_staging", clone_then_replace)
    result = sdf.run_daily_full_staged(
        trade_date="2026-08-15", child_argv=_child(CHILD_OK)
    )
    assert result["rc"] == 2
    assert result["swapped"] is False
    assert "克隆后基线" in result["reason"]
    assert _sha256(prod_db) == impostor_sha  # 冒名者字节原样, 没被我们覆盖
