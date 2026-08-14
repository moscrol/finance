"""质检闸门 vs duckdb 写锁：撞锁要等、等不到要如实说"没跑成"。

背景（2026-08-13 夜间）：backfill 进程持写锁期间，check_daily_review_data
只读连接当场炸 IOException，外层把"检查没执行"误报成"数据不完整"。
契约：锁冲突有界重试；重试穷尽退出码 3（BLOCKED），与 1/2（INCOMPLETE）
分流；非锁类 IO 故障原样抛出，不被重试吞掉。
"""
from __future__ import annotations

import duckdb
import pytest

from market_feature_store import db
from scripts import check_daily_review_data

LOCK_MSG = (
    'IO Error: Could not set lock on file "/tmp/x.duckdb": '
    "Conflicting lock is held in PID 12345"
)


class _Opener:
    """先失败 N 次再成功的连接桩，记录调用次数。"""

    def __init__(self, failures: int, error: Exception, result: object = "CON"):
        self.failures = failures
        self.error = error
        self.result = result
        self.calls = 0

    def __call__(self) -> object:
        self.calls += 1
        if self.calls <= self.failures:
            raise self.error
        return self.result


def test_lock_conflict_retries_until_writer_releases() -> None:
    opener = _Opener(failures=2, error=duckdb.IOException(LOCK_MSG))
    sleeps: list[float] = []

    con = db.connect_read_only_with_retry(
        attempts=5,
        delay_seconds=0.25,
        opener=opener,
        sleep=sleeps.append,
    )

    assert con == "CON"
    assert opener.calls == 3
    assert sleeps == [0.25, 0.25]


def test_lock_held_beyond_window_raises_database_locked() -> None:
    opener = _Opener(failures=99, error=duckdb.IOException(LOCK_MSG))
    sleeps: list[float] = []

    with pytest.raises(db.DatabaseLockedError) as excinfo:
        db.connect_read_only_with_retry(
            attempts=3,
            delay_seconds=0.25,
            opener=opener,
            sleep=sleeps.append,
        )

    assert opener.calls == 3
    # 最后一轮失败后不再空等
    assert sleeps == [0.25, 0.25]
    assert "PID 12345" in str(excinfo.value)


def test_non_lock_io_error_is_not_retried() -> None:
    opener = _Opener(failures=99, error=duckdb.IOException("IO Error: disk full"))

    with pytest.raises(duckdb.IOException, match="disk full"):
        db.connect_read_only_with_retry(
            attempts=5,
            delay_seconds=0.25,
            opener=opener,
            sleep=lambda _s: None,
        )

    assert opener.calls == 1


def test_main_reports_blocked_with_exit_code_3(monkeypatch, capsys) -> None:
    """撞锁穷尽后：rc=3 + RESULT: BLOCKED，绝不冒充 INCOMPLETE。"""

    def locked_connect(read_only: bool = False):
        raise duckdb.IOException(LOCK_MSG)

    monkeypatch.setattr(check_daily_review_data, "connect", locked_connect)
    monkeypatch.setenv("REVIEW_GATE_LOCK_ATTEMPTS", "2")
    monkeypatch.setenv("REVIEW_GATE_LOCK_DELAY_SECONDS", "0")

    rc = check_daily_review_data.main("2026-07-10", data_only=True)

    out = capsys.readouterr().out
    assert rc == check_daily_review_data.EXIT_BLOCKED == 3
    assert "RESULT: BLOCKED" in out
    assert "INCOMPLETE" not in out
