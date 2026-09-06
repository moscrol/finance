"""周均线口径与来源标记的回归测试。

这里钉的不是某天的数值，是**口径**：`sh_week_ma` 是日 MA5（一周 = 5 个交易日），
不是 55 周均线。判据用 fupanhui 真抓的那批行（`unknown_preexisting`）做，
不用回填行——回填行按定义就是 MA5，拿它验 MA5 是循环论证。
"""

from __future__ import annotations

import statistics
from pathlib import Path

import pytest

from scripts.backfill_market_deviation import (
    MA_WINDOW,
    SOURCE_BACKFILL,
    SOURCE_UNKNOWN,
    compute_backfill,
    verify,
)

DB = Path("db/market_feature_store.duckdb")
pytestmark = pytest.mark.skipif(not DB.exists(), reason="需要真库 db/market_feature_store.duckdb")


@pytest.fixture(scope="module")
def con():
    import duckdb

    c = duckdb.connect(str(DB), read_only=True)
    yield c
    c.close()


def test_周均线是日MA5不是55周均线(con) -> None:
    """拿 fupanhui 真抓的行做判据：日 MA5 的误差必须比 55 周均线小一个数量级以上。

    2026-09-05 实测 MAE：日 MA5 = 3.70 点，周 MA55 = 271.54 点。
    """
    rows = con.execute(
        """
        SELECT CAST(trade_date AS DATE), sh_index_close, sh_week_ma, sh_week_ma_source
        FROM fact_market_daily WHERE sh_index_close IS NOT NULL ORDER BY trade_date
        """
    ).fetchall()
    closes = [r[1] for r in rows]
    scraped = [(i, r) for i, r in enumerate(rows) if r[3] == SOURCE_UNKNOWN and r[2] is not None]
    assert len(scraped) >= 100, f"真抓样本只有 {len(scraped)} 条，证不了口径"

    def mae(window: int) -> float:
        errs = []
        for i, r in scraped:
            if i < window - 1:
                continue
            seg = closes[i - window + 1 : i + 1]
            if any(c is None for c in seg):
                continue
            errs.append(abs(sum(float(c) for c in seg) / window - float(r[2])))
        return statistics.mean(errs) if errs else float("inf")

    mae_ma5 = mae(MA_WINDOW)
    mae_55w = mae(55 * 5)  # 55 周 ≈ 275 个交易日
    assert mae_ma5 < 20, f"日 MA5 误差 {mae_ma5:.2f} 异常大，口径可能变了"
    assert mae_55w > mae_ma5 * 10, f"55 周均线({mae_55w:.2f}) 没有明显差于日 MA5({mae_ma5:.2f})"


def test_偏离度就是收盘对周均线的百分比(con) -> None:
    rows = con.execute(
        """
        SELECT sh_index_close, sh_week_ma, sh_deviation_pct FROM fact_market_daily
        WHERE sh_deviation_pct IS NOT NULL AND sh_week_ma IS NOT NULL
              AND sh_index_close IS NOT NULL AND sh_week_ma_source = ?
        """,
        [SOURCE_BACKFILL],
    ).fetchall()
    assert rows, "没有回填行，本用例证不了公式"
    for close, ma, dev in rows:
        assert abs((float(close) / float(ma) - 1) * 100 - float(dev)) < 0.01


def test_来源必须可分辨_不得把存量冒充抓取(con) -> None:
    """存量证不了是 tooltip 还是当时就走了复算兜底，只能标 unknown。

    把它标成 tooltip 就是把推断写成事实——下游会据此认为那 221 天口径一致。
    """
    sources = {
        r[0]
        for r in con.execute(
            "SELECT DISTINCT sh_week_ma_source FROM fact_market_daily "
            "WHERE sh_week_ma_source IS NOT NULL"
        ).fetchall()
    }
    assert SOURCE_UNKNOWN in sources
    assert "tooltip" not in sources or SOURCE_UNKNOWN in sources


def test_回填不覆盖任何已有值(con) -> None:
    """compute_backfill 只产出 sh_deviation_pct IS NULL 的行。回填已完成时应为空。"""
    pending = compute_backfill(con)
    still_null = con.execute(
        "SELECT COUNT(*) FROM fact_market_daily WHERE sh_deviation_pct IS NULL"
    ).fetchone()[0]
    assert len(pending) <= still_null, "待补数超过了空值数——说明它打算覆盖已有值"


def test_覆盖率与阈值线读数自洽(con) -> None:
    """+1.5 / −2.5 是词表里的阶段判定线；回填后它们的天数必须从有值的行里数得出来。"""
    rep = verify(con)
    assert rep["fill_rate"] > 0.9, f"回填后覆盖率仍只有 {rep['fill_rate']:.1%}"
    assert rep["by_source"].get(SOURCE_BACKFILL, 0) > 0
    counted = con.execute(
        "SELECT COUNT(*) FILTER (WHERE sh_deviation_pct >= 1.5), "
        "COUNT(*) FILTER (WHERE sh_deviation_pct <= -2.5) FROM fact_market_daily"
    ).fetchone()
    assert (rep["days_ge_1.5"], rep["days_le_-2.5"]) == counted
