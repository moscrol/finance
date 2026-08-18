"""`contains` 过滤器的真库门禁。

守的形状：2026-08-16 实测发现 `contains` 生成的 SQL 里 `ESCAPE '\\'` 是两个字符，
DuckDB 直接抛语法错，而 episode_tools 把它归进兜底分支、返回 `ok=true` + 零证据。
模型以为查过了，实际一行没拿到——题材题按主题名筛选的唯一自然写法全线失效。

**必须打真库**：这个 bug 只在 SQL 执行期暴露，任何 mock connection 都测不出来。
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from intelligence.paths import default_paths
from intelligence.services import finance_query as fq
from intelligence.services.research_contract import (
    InformationCutoff,
    ResearchDeadline,
)

# 走 paths.py（路径真本源）而不是写死家目录。finance_root 与
# default_market_db_path() 现已同源（data_repo_root 不再读 WORKBENCH_REPO_ROOT）。
# 这里仍用 finance_root：本测试要打的是真实数据根下那一个库。
_DB: Path = default_paths().finance_root / "db" / "market_feature_store.duckdb"

pytestmark = pytest.mark.skipif(
    not _DB.exists(), reason="需要本地 market_feature_store.duckdb"
)


def _run(filters: tuple[dict, ...]):
    q = fq.FinanceQuery(_DB)
    spec = fq.FinanceQuerySpec.from_arguments(
        {
            "dataset": "mainline_sector_daily",
            "dimensions": ["trade_date", "theme_name"],
            "metrics": ["amount"],
            "filters": list(filters),
            "time_range": {"start": "2026-04-01", "end": "2026-08-14"},
            "limit": 10,
        }
    )
    return q.run(
        spec,
        information_cutoff=InformationCutoff(date(2026, 8, 16), "runtime_default"),
        deadline=ResearchDeadline.from_timeout(60.0),
    )


def test_contains_filter_executes_against_real_duckdb() -> None:
    """`contains` 必须能真的跑起来——这条直接钉住 ESCAPE 那一个字符。"""

    result = _run(({"field": "theme_name", "op": "contains", "value": "算力"},))
    assert len(result.rows) > 0, "contains 命中 0 行；该主题在库里确有数据"


def test_contains_matches_same_rows_as_equality() -> None:
    """行为判据：`contains 算力` 至少要覆盖 `eq AI算力` 的结果。

    只断言「不抛异常」会被一个永远返回空集的实现骗过；这条钉住它真的在筛。
    """

    contains = _run(({"field": "theme_name", "op": "contains", "value": "算力"},))
    equals = _run(({"field": "theme_name", "op": "eq", "value": "AI算力"},))
    assert len(equals.rows) > 0
    assert len(contains.rows) >= len(equals.rows)


def test_contains_still_escapes_sql_wildcards() -> None:
    """修 ESCAPE 不能顺手把转义关掉：`_` 必须当字面量，不当单字符通配符。"""

    literal = _run(({"field": "theme_name", "op": "contains", "value": "_"},))
    wildcard_would_match_everything = _run(())
    assert len(wildcard_would_match_everything.rows) > 0
    assert len(literal.rows) < len(wildcard_would_match_everything.rows), (
        "`_` 被当成通配符了——转义失效"
    )


@pytest.mark.parametrize("value", ["AI", "算力", "服务", "%", "\\"])
def test_contains_never_raises_on_ordinary_values(value: str) -> None:
    """普通值（含 SQL 元字符）都不得抛异常——抛了就会静默变成零证据。"""

    _run(({"field": "theme_name", "op": "contains", "value": value},))
