"""跨进程边界：#857 那类「两条读取之间有人提交」在 DuckDB 里只可能发生在**同一进程**内。

工单 #74 要求一条「第二个进程在两条读取之间提交」的阳性对照。实测它做不出来：
DuckDB 对同一个库文件的跨进程并发打开一律拒绝（RW+RW / RO+RW / RW+RO 三种组合都报
Conflicting lock）。生产上夜跑写者也从不与读者共用文件——它写 staging 副本，再用
``os.replace`` 原子换名（``market_feature_store/db.py`` 「staging 写 + 原子换名」）。

所以跨进程能造成的唯一「混代际」形态是：一个函数在一次调用里**多次 connect()**，
前一次连接全部关掉后文件被换了，下一次 connect 打开的是新代际。``read_snapshot``
绑不住这种——它只绑一条连接。本文件把这条边界钉成断言，三件事分别证：

1. 引擎拒绝第二进程打开同一文件（所以「多进程用例先红后绿」这个验收在引擎层面不可满足）；
2. 持有中的连接跨越 ``os.replace`` 仍读旧代际（fd 钉住旧 inode），单连接函数天然免疫；
3. 每读一次就重新 connect 的函数会跨代际拼接——``strong_subtheme_trace`` 逐日各开一条
   连接就是这个形态，见 ``docs/verification/2026-09-22-unsnapshotted-reads-triage.md``。

用真子进程、真文件、真 ``os.replace``，不 mock：mock 只能证明「我以为的并发」。
"""
from __future__ import annotations

import subprocess
import sys
import textwrap

import duckdb
import pytest


def _seed(path) -> None:
    with duckdb.connect(str(path)) as con:
        con.execute("CREATE TABLE t(gen INT); INSERT INTO t VALUES (1)")
        con.execute("CHECKPOINT")


def _second_process(code: str) -> str:
    proc = subprocess.run(
        [sys.executable, "-c", textwrap.dedent(code)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    return (proc.stdout + proc.stderr).strip()


def _swap_in_second_process(path, staging) -> str:
    """生产形态的写者：拷副本 → 在副本上写 → os.replace 换名。从不打开生产文件。"""
    return _second_process(
        f"""
        import duckdb, os, shutil
        shutil.copyfile({str(path)!r}, {str(staging)!r})
        with duckdb.connect({str(staging)!r}) as w:
            w.execute("UPDATE t SET gen = 2")
            w.execute("CHECKPOINT")
        os.replace({str(staging)!r}, {str(path)!r})
        print("SWAPPED")
        """
    )


@pytest.mark.parametrize(
    "holder_ro, other_ro",
    [(False, False), (True, False), (False, True)],
    ids=["rw+rw", "ro+rw", "rw+ro"],
)
def test_engine_refuses_second_process_on_same_file(tmp_path, holder_ro, other_ro):
    """「第二个进程在两条读取之间提交」在引擎层面就不成立：文件锁把它挡在 connect。"""
    path = tmp_path / "shared.duckdb"
    _seed(path)
    holder = duckdb.connect(str(path), read_only=holder_ro)
    try:
        out = _second_process(
            f"""
            import duckdb
            try:
                con = duckdb.connect({str(path)!r}, read_only={other_ro!r})
                con.execute("SELECT count(*) FROM t").fetchall()
                print("OPENED")
            except Exception as exc:
                print("REFUSED", type(exc).__name__, str(exc)[:100])
            """
        )
    finally:
        holder.close()
    assert out.startswith("REFUSED IOException"), out
    assert "lock" in out.lower(), out


def test_held_connection_pins_old_generation_across_swap(tmp_path):
    """单连接函数（health / collect_daily_review 一类）对换库天然免疫：fd 钉住旧 inode。"""
    path, staging = tmp_path / "prod.duckdb", tmp_path / "prod.duckdb.staging"
    _seed(path)
    reader = duckdb.connect(str(path), read_only=True)
    try:
        assert reader.execute("SELECT gen FROM t").fetchone()[0] == 1
        assert _swap_in_second_process(path, staging) == "SWAPPED"
        # 同一条连接：仍是代际 1。
        assert reader.execute("SELECT gen FROM t").fetchone()[0] == 1
        # 同进程再 connect 同一路径：DuckDB 按路径复用数据库实例，看到的还是代际 1。
        sibling = duckdb.connect(str(path), read_only=True)
        try:
            assert sibling.execute("SELECT gen FROM t").fetchone()[0] == 1
        finally:
            sibling.close()
    finally:
        reader.close()
    # 全部关掉后重开：实例被回收，这次打开的才是换进来的文件。
    with duckdb.connect(str(path), read_only=True) as fresh:
        assert fresh.execute("SELECT gen FROM t").fetchone()[0] == 2


def _reconnect_per_read(path, between) -> list[int]:
    """每读一次重新 connect 的读者——一份报告的两个数字可以来自两个代际。"""
    seen = []
    for i in range(2):
        with duckdb.connect(str(path), read_only=True) as con:
            seen.append(con.execute("SELECT gen FROM t").fetchone()[0])
        if i == 0:
            between()
    return seen


def _single_connection(path, between) -> list[int]:
    seen = []
    with duckdb.connect(str(path), read_only=True) as con:
        for i in range(2):
            seen.append(con.execute("SELECT gen FROM t").fetchone()[0])
            if i == 0:
                between()
    return seen


def test_reconnect_per_read_straddles_swap_but_single_connection_does_not(tmp_path):
    """跨进程唯一能混代际的形态是「多次 connect」；read_snapshot 只绑一条连接，管不到它。"""

    def run(reader):
        path = tmp_path / f"{reader.__name__}.duckdb"
        staging = tmp_path / f"{reader.__name__}.staging"
        _seed(path)
        return reader(path, lambda: _swap_in_second_process(path, staging))

    assert run(_reconnect_per_read) == [1, 2]
    assert run(_single_connection) == [1, 1]
