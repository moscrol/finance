"""dataset 注册审计的 pytest 侧复挂。

同一判据挂 pre-commit 和 pytest 两处，理由与 ``test_tool_reachability_audit`` 相同：
它保护的故障（表灌满了数、覆盖率审计全绿，而 agent 问到答「查不到」）没人会主动去查。

本文件里**证伪用的三条比通过用的那条更重要**：一个永远不会红的门禁等于没装。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts import audit_dataset_registration as audit_mod  # noqa: E402


def test_every_fact_table_is_registered_or_exempted() -> None:
    """二选一：要么进 _DATASETS，要么在 _UNREGISTERED_TABLES 写明为什么不进。"""

    result = audit_mod.audit()

    assert result["undeclared"] == [], (
        f"以下表既没注册也没写明豁免：{result['undeclared']}。"
        "二选一，都在 intelligence/services/finance_query.py。"
        "理由只写在文档正文里不算——那不是机器可读的，下一个人会读成「漏了」。"
    )


def test_schema_side_is_independent_of_registry() -> None:
    """判据取自 schema.sql，不取自 _DATASETS——否则「没注册的表」按定义是空集。

    姊妹脚本 audit_tool_reachability 初版就栽在这里：拿声明本身当判据，
    结果报了一次「12/12 一致」的假绿。这条钉住两侧**能够**不同。
    """

    from intelligence.services.finance_query import _DATASETS

    declared = set(audit_mod.schema_tables())
    registered = {d.table for d in _DATASETS.values()}

    assert declared, "schema.sql 抽不出表名，正则可能被 DDL 改动打断了"
    # 有表在 schema 里却没注册（豁免表）→ 两侧确实独立
    assert declared - registered, "declared ⊆ registered，判据可能退化成照镜子了"
    # 有注册项不在 CREATE TABLE 里（两个 VIEW）→ 反方向也不重合
    assert registered - declared, "registered ⊆ declared，VIEW 那两个应当在差集里"


def test_new_unclaimed_table_fails_the_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    """证伪①：schema.sql 新增一张没人认领的表 → 必须红。"""

    real = audit_mod.schema_tables
    monkeypatch.setattr(
        audit_mod, "schema_tables", lambda *a, **k: [*real(), "fact_brand_new_daily"]
    )

    result = audit_mod.audit()

    assert result["ok"] is False
    assert result["undeclared"] == ["fact_brand_new_daily"]


def test_registered_but_empty_table_fails_the_gate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """证伪②：注册了但 0 行、又没声明 _EMPTY_BY_DESIGN → 必须红。

    这一条抓的是「建表 ≠ 入库」——grep 抓不到，只有 COUNT(*) 抓得到。
    本仓 fact_top_gainers 就是这个形状（只有 schema、无写入链）。
    """

    monkeypatch.setattr(
        audit_mod, "_count_rows", lambda db, tables: {"fact_market_daily": 0}
    )

    result = audit_mod.audit(db_path=Path("/nonexistent-but-truthy"))

    assert result["ok"] is False
    assert result["empty_registered"] == ["fact_market_daily"]


def test_empty_by_design_table_does_not_fail(monkeypatch: pytest.MonkeyPatch) -> None:
    """证伪③的反面：诚实闸锚点是有意留空的，不该被判红。

    fact_stock_technical_snapshot 存在的意义就是让「问技术面快照」这一口径
    如实回「暂无数据」（honesty_gates._EMPTY_CALIBER_TABLE）。
    """

    monkeypatch.setattr(
        audit_mod,
        "_count_rows",
        lambda db, tables: {"fact_stock_technical_snapshot": 0},
    )

    result = audit_mod.audit(db_path=Path("/nonexistent-but-truthy"))

    assert result["empty_registered"] == []
    assert result["ok"] is True


def test_row_check_skipped_without_db() -> None:
    """没有 DuckDB 时规则 2 跳过，规则 1 照常硬拦。

    worktree 里 db/ 是 gitignore 的；这条若 fail closed，每棵树都提交不了。
    """

    result = audit_mod.audit(db_path=None)

    assert result["row_check_ran"] is False
    assert result["empty_registered"] == []
    assert result["ok"] is True
