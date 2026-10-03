"""测试套件不许往真实的「待重判」队列里写。

2026-09-30 实测：workbench HTTP 用例把运行交给后台线程，线程在用例结束后才写
``~/.finance-runtime/rejudge-pending/index.jsonl``。那时 PYTEST_CURRENT_TEST 已被
pytest 清掉，模块自带的「测试中不写默认路径」闸失效，一次全量灌进 138 条假条目。
根 conftest 现在把 ``FINANCE_REJUDGE_PENDING_INDEX`` 改道到会话临时文件；这里钉住
改道生效，并复现「用例结束后才写」的后台线程形状。
"""

from __future__ import annotations

import os
import tempfile
import threading
from pathlib import Path

from intelligence.services import rejudge_pending

_LATE_WRITES: list[Path | None] = []
_LATE_THREAD: list[threading.Thread] = []
_RELEASE = threading.Event()


def _artifact() -> dict:
    return {
        "run_id": "run_isolation_probe",
        "published_answer": "a",
        "semantic_verifier": {"judge_status": "unavailable", "public_answer": "a"},
    }


def test_default_index_is_redirected_away_from_home():
    path = rejudge_pending.pending_index_path()
    assert path != rejudge_pending.DEFAULT_INDEX
    assert Path(tempfile.gettempdir()) in path.parents
    assert Path.home() / ".finance-runtime" not in path.parents


def test_background_write_outliving_the_test_starts_here():
    """起一个比本用例活得久的线程：它等到下一个用例里才写。"""

    def late_writer() -> None:
        _RELEASE.wait(timeout=10)
        _LATE_WRITES.append(rejudge_pending.append_pending_from_artifact(_artifact()))

    thread = threading.Thread(target=late_writer, name="workbench-run-probe", daemon=True)
    thread.start()
    _LATE_THREAD.append(thread)


def test_background_write_lands_in_the_session_temp_index():
    assert _LATE_THREAD, "依赖上一个用例起的线程（同文件顺序执行）"
    before = rejudge_pending.DEFAULT_INDEX.read_bytes() if rejudge_pending.DEFAULT_INDEX.exists() else None
    # 模拟「用例之间」：PYTEST_CURRENT_TEST 不在时，旧闸会放行写默认路径。
    saved = os.environ.pop("PYTEST_CURRENT_TEST", None)
    try:
        _RELEASE.set()
        _LATE_THREAD[0].join(timeout=10)
    finally:
        if saved is not None:
            os.environ["PYTEST_CURRENT_TEST"] = saved
    assert _LATE_WRITES and _LATE_WRITES[0] is not None
    assert _LATE_WRITES[0] != rejudge_pending.DEFAULT_INDEX
    after = rejudge_pending.DEFAULT_INDEX.read_bytes() if rejudge_pending.DEFAULT_INDEX.exists() else None
    assert after == before, "真实的待重判队列被测试写入了"
