"""旧教学旁路库（没有 first_known_at 列）必须给可操作的中止，而不是裸 Binder Error。"""
from __future__ import annotations

import duckdb
import pytest

from intelligence.services.teaching_framework.river_objects import (
    StaleTeachingSidecarError,
    _require_pit_column,
)

_OLD_DDL = (
    "CREATE TABLE history_teaching_labels ("
    "trade_date DATE, entity_type VARCHAR, entity_id VARCHAR, label VARCHAR, value_num DOUBLE, "
    "value_text VARCHAR, framework_version VARCHAR, status VARCHAR, computed_at TIMESTAMP)"
)
_NEW_DDL = _OLD_DDL[:-1] + ", first_known_at TIMESTAMP)"


def test_old_sidecar_raises_actionable_error() -> None:
    con = duckdb.connect(":memory:")
    con.execute(_OLD_DDL)
    with pytest.raises(StaleTeachingSidecarError) as err:
        _require_pit_column(con)
    msg = str(err.value)
    assert "first_known_at" in msg
    assert "reset-teaching" in msg, "必须点名补救命令，否则用户不知道该做什么"


def test_current_sidecar_passes() -> None:
    con = duckdb.connect(":memory:")
    con.execute(_NEW_DDL)
    _require_pit_column(con)


def test_absent_table_is_not_an_error() -> None:
    """表根本没有 ≠ 表是旧的：前者由 _has_table 分支正常处理成「没有对象」。"""
    _require_pit_column(duckdb.connect(":memory:"))
