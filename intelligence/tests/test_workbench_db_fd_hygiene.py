"""fd 卫生：WorkbenchDB 连接必须确定性关闭，不得依赖周期 GC 兜底。

生产事故（2026-08-26，8792，台账 R-20260826-03）：``with sqlite3.connect(...)``
只管事务提交不管关闭，连接对象等周期 GC 回收；UI/探针轮询让分配速度超过
GC 回收速度，进程 fd 顶到 launchd 默认软上限 256，EMFILE 以
``sqlite3.OperationalError: unable to open database file`` 形态间歇打爆
``/api/conversations`` 与 ``/api/runs``（HTTP 500）。隔离复现：50 次
RunStore 实例化泄 93 个 fd，``gc.collect()`` 后归零——证明是「无引用但
被环持有、只有周期 GC 能收」的连接。

测试口径：``gc.disable()`` 下做 N 次操作，fd 不得随 N 增长——确定性关闭
成立时增长为 0；靠 GC 兜底时增长 ≈ 2N（db + wal 各一个）。
"""

from __future__ import annotations

import gc
import os
from pathlib import Path

from intelligence.services.workbench_db import WorkbenchDB


def _open_fds() -> int:
    return len(os.listdir("/dev/fd"))


def test_init_and_ops_close_connections_deterministically(tmp_path: Path) -> None:
    warm = WorkbenchDB(tmp_path / "warm.sqlite3")
    warm.upsert_run(
        {"run_id": "w", "user": "u", "status": "s", "created_at": "t"}
    )

    gc.disable()
    try:
        base = _open_fds()
        db = WorkbenchDB(tmp_path / "probe.sqlite3")
        for index in range(30):
            db.upsert_run(
                {
                    "run_id": f"r{index}",
                    "user": "u",
                    "status": "running",
                    "created_at": "2026-08-26T00:00:00",
                }
            )
            db.get_run(f"r{index}")
        grown = _open_fds() - base
    finally:
        gc.enable()
        gc.collect()
    assert grown <= 3, (
        f"61 次连接后 fd 增长 {grown}（>3）：连接未确定性关闭，"
        "在轮询负载下会顶到 launchd fd 上限并以 500 打爆 API"
    )


def test_run_store_instantiation_does_not_leak_fds(
    tmp_path: Path, monkeypatch
) -> None:
    """模拟 API 层 ``store_for``：每请求新建 RunStore 不得累积 fd。"""

    monkeypatch.setenv("FORESIGHT_USERS_DIR", str(tmp_path / "users"))
    from intelligence.services.run_store import RunStore

    RunStore(user_id="fd-probe", root=tmp_path / "warm")

    gc.disable()
    try:
        base = _open_fds()
        for _ in range(30):
            RunStore(user_id="fd-probe", root=tmp_path / "store")
        grown = _open_fds() - base
    finally:
        gc.enable()
        gc.collect()
    assert grown <= 3, (
        f"30 次 RunStore 实例化后 fd 增长 {grown}（>3）："
        "WorkbenchDB.__init__ 的建表连接未确定性关闭"
    )
