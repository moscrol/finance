"""用已落库的板块成分资金流，加总成题材资金面板。

复盘会 `/data/theme/panels` 是编辑部 50 来个格子；分组规则还原不了。
本质相同的是「一篮子股票今天的资金进了还是出了」——篮子用当日 published
板块成分，金额用成分上的 `fund_flow_1d` / `amount`。

写入仍落 `fact_theme_flow_daily`，`source` 标明本地加总，不冒充复盘会面板。

口径纪律（2026-09-12 修正，三条都是实测复现出来的缺陷）：

1. **不混口径**。`fund_flow_1d` 这一列里躺着两种东西：`source='fupanhui'` 行是
   供应商自有口径，`source='local:stitch'` 行是东财主力净额（超大单+大单）。
   同股同日实测差很远（招金黄金 0.64 vs 2.21；中际旭创 -30.66 vs -25.99）。
   旧实现 `sum(fund_flow_1d)` 不分 source 直接加，跨边界日会把两种口径加成一个
   数。现在必须指定 `member_source`，只汇总该口径的成分；一天里若有多种口径
   带资金，拒绝猜测、直接报错要求调用方指定。

2. **没有资金的篮子不写行**。旧实现 `HAVING count(*) > 0` 恒真，全空篮子也写出
   `total_fund=NULL, stock_count=2` 的面板行——闸门只数行数就放行，典型空壳过门。
   现在按「有资金的成分数 > 0」过滤。

3. **缺值是未知，不是 0**。篮子里部分成分没资金时，只加有值的那些必然低估，
   所以同时落 `member_count`（篮子总成分）与 `fund_coverage`（有效资金覆盖率），
   让使用端能判断这个数值可不可信，而不是拿一个看着合理的数去支撑判断。
   `stock_count` 改为「实际贡献资金的成分数」，保持 total_fund 与 stock_count 自洽
   （与 09-02 复盘会面板 fund=Σn 只个股 的不变量一致）。
"""
from __future__ import annotations

from datetime import datetime, timezone

from ..db import connect, init_db

# 成分行 source → 资金口径标识。写进面板 source，跨日对比必须按它分段。
FUND_CALIBERS = {
    "local:stitch": "em-main-net",      # 东财主力净额 = 超大单+大单
    "fupanhui": "fupanhui-native",      # 复盘会自有口径（供应商未公开算法）
}
SOURCE_PREFIX = "local:sector-basket"

# 新增列：老库没有这几列，发布时随代码一起 ensure（可空、幂等、可回滚）。
# universe_snapshot_id：篮子实际用的成分版本。同一题材名下成分换了，资金和就不是
# 同一个东西，跨日比较必须带上它；成分版本不唯一（如编辑篮子）时写 NULL=明确未知。
ENSURE_COLUMNS = (
    ("member_count", "INTEGER"),
    ("fund_coverage", "DOUBLE"),
    ("fund_caliber", "TEXT"),
    ("universe_snapshot_id", "TEXT"),
)

UPSERT_SQL = """
    INSERT INTO fact_theme_flow_daily
        (trade_date, theme_code, theme_name, total_fund, total_amount,
         stock_count, member_count, fund_coverage, fund_caliber,
         universe_snapshot_id, source, updated_at)
    VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
    ON CONFLICT (trade_date, theme_code) DO UPDATE SET
        theme_name = excluded.theme_name,
        total_fund = excluded.total_fund,
        total_amount = excluded.total_amount,
        stock_count = excluded.stock_count,
        member_count = excluded.member_count,
        fund_coverage = excluded.fund_coverage,
        fund_caliber = excluded.fund_caliber,
        universe_snapshot_id = excluded.universe_snapshot_id,
        source = excluded.source,
        updated_at = excluded.updated_at
"""

DELETE_ALL_OWN_SQL = """
    DELETE FROM fact_theme_flow_daily
    WHERE trade_date = ? AND source LIKE ? || ':%'
"""


# 本次不再产出的旧面板必须撤销：否则成分变空/题材消失后，上一轮的数会以
# “当日有效面板”的身份留在库里被查到。只删本口径自己负责的那批，不动其他来源。
# 注意范围是「本模块写过的全部口径」(LIKE 前缀) 而非「本轮 source」:
# 同日先写东财口径 A, 再换复盘会口径 B 重建时, 只清本轮 source 会把 A 留在库里,
# 变成同一天两套口径的面板共存——下游一汇总就又是混口径。供应商原生面板
# (如 source='fupanhui') 不带本前缀, 不受影响。
DELETE_STALE_SQL = """
    DELETE FROM fact_theme_flow_daily
    WHERE trade_date = ? AND source LIKE ? || ':%'
      AND theme_code NOT IN (SELECT theme_code FROM _panel_keep)
"""

# total_fund / total_amount / stock_count 三者都只统计「该口径且有资金」的成分,
# 保证 fund = Σ(这 stock_count 只) 自洽; member_count 另记篮子全量。
AGG_SQL = """
    SELECT
        sector_ts_code,
        any_value(sector_name) AS sector_name,
        sum(fund_flow_1d) FILTER (WHERE contributes) AS total_fund,
        sum(amount) FILTER (WHERE contributes) AS total_amount,
        count(*) FILTER (WHERE contributes) AS fund_stock_count,
        count(*) AS member_count,
        CASE WHEN count(DISTINCT snap) = 1 THEN any_value(snap) END AS universe_snapshot_id
    FROM (
        SELECT sector_ts_code, sector_name, fund_flow_1d, amount,
               sector_universe_snapshot_id AS snap,
               (fund_flow_1d IS NOT NULL AND source = ?) AS contributes
        FROM fact_sector_stock_daily
        WHERE trade_date = ?
    )
    GROUP BY sector_ts_code
    HAVING count(*) FILTER (WHERE contributes) > 0
"""

SOURCES_WITH_FUND_SQL = """
    SELECT DISTINCT source
    FROM fact_sector_stock_daily
    WHERE trade_date = ? AND fund_flow_1d IS NOT NULL
    ORDER BY 1
"""


def ensure_columns(con) -> None:
    """幂等补列。老库建表时没有覆盖率字段，发布流程里随代码一起执行。"""
    for name, typ in ENSURE_COLUMNS:
        con.execute(f"ALTER TABLE fact_theme_flow_daily ADD COLUMN IF NOT EXISTS {name} {typ}")


def detect_member_source(con, trade_date: str) -> str | None:
    """当日带资金的成分口径；0 种返回 None，多种抛错（拒绝替调用方猜）。"""
    found = [r[0] for r in con.execute(SOURCES_WITH_FUND_SQL, [trade_date]).fetchall()]
    if not found:
        return None
    if len(found) > 1:
        raise ValueError(
            f"{trade_date} 有多种口径的资金流成分 {found}；不同口径不可相加，"
            f"请显式指定 member_source（见 FUND_CALIBERS）"
        )
    return found[0]


def _revoke_all(con, trade_date: str, *, manage_transaction: bool) -> dict:
    """当日无可用资金：删光**本模块写过的**当日面板，不动供应商原生面板。"""
    if manage_transaction:
        con.execute("BEGIN TRANSACTION")
    try:
        removed = con.execute(DELETE_ALL_OWN_SQL, [trade_date, SOURCE_PREFIX]).fetchall()
        stale = int(removed[0][0]) if removed else 0
        if manage_transaction:
            con.execute("COMMIT")
    except Exception:
        if manage_transaction:
            con.execute("ROLLBACK")
        raise
    return {
        "panels": 0, "source": None, "member_source": None,
        "caliber": None, "skipped_no_fund": 0, "stale_removed": stale,
    }


def sync_from_sector_baskets(trade_date: str, *, con=None, member_source: str | None = None,
                             manage_transaction: bool = True) -> dict:
    """按板块成分加总写入 `fact_theme_flow_daily`（单一口径）。

    Args:
        member_source: 只汇总该 source 的成分行；留空则自动探测当日唯一口径。
        manage_transaction: 本函数是否自己 BEGIN/COMMIT。**已在外层事务里调用时必须
            传 False**（嵌套 BEGIN 会抛错并把外层事务置为 aborted）。

    Returns: {"panels", "source", "member_source", "caliber", "skipped_no_fund", "stale_removed"}
    """
    own = con is None
    if own:
        init_db()
        con = connect()
    try:
        ensure_columns(con)
        if member_source is None:
            member_source = detect_member_source(con, trade_date)
        if member_source is None:
            # 当日没任何可用资金→本次不产出任何面板。但**不能就此返回**:
            # 上一轮的面板会以「当日有效」的身份留在库里。撤销不需要探测口径——
            # 本模块写过的面板 source 都以 SOURCE_PREFIX 开头, 只删自己写的那批,
            # 供应商原生面板(如 fupanhui)不受影响。
            return _revoke_all(con, trade_date, manage_transaction=manage_transaction)
        caliber = FUND_CALIBERS.get(member_source, f"unknown:{member_source}")
        source = f"{SOURCE_PREFIX}:{caliber}"

        rows = con.execute(AGG_SQL, [member_source, trade_date]).fetchall()
        total_baskets = con.execute(
            "SELECT count(DISTINCT sector_ts_code) FROM fact_sector_stock_daily WHERE trade_date = ?",
            [trade_date],
        ).fetchone()[0]

        now = datetime.now(timezone.utc).isoformat()
        payload = []
        for code, name, fund, amount, fund_n, member_n, snap in rows:
            if not code:
                continue
            fund_n, member_n = int(fund_n), int(member_n)
            payload.append((
                trade_date, code, name, fund, amount,
                fund_n, member_n,
                round(fund_n / member_n, 4) if member_n else None,
                caliber, snap, source, now,
            ))

        # 写入与撤销必须同一事务: 否则中途失败会留下「新旧混杆」的当日面板集。
        # 事务归属由调用方**显式声明**，不靠捕获 BEGIN 异常来猜：在 DuckDB 里
        # 那个异常会把外层事务置为 aborted，接下来每一条语句都失败——用“容错”的
        # 写法把可恢复的情况变成不可恢复的。
        if manage_transaction:
            con.execute("BEGIN TRANSACTION")
        try:
            con.execute("CREATE OR REPLACE TEMP TABLE _panel_keep (theme_code VARCHAR)")
            if payload:
                con.executemany(
                    "INSERT INTO _panel_keep VALUES (?)", [(p[1],) for p in payload]
                )
                con.executemany(UPSERT_SQL, payload)
            removed = con.execute(DELETE_STALE_SQL, [trade_date, SOURCE_PREFIX]).fetchall()
            stale = int(removed[0][0]) if removed else 0
            con.execute("DROP TABLE IF EXISTS _panel_keep")
            if manage_transaction:
                con.execute("COMMIT")
        except Exception:
            if manage_transaction:
                con.execute("ROLLBACK")
            raise
        return {
            "panels": len(payload),
            "source": source,
            "member_source": member_source,
            "caliber": caliber,
            "skipped_no_fund": int(total_baskets) - len(payload),
            "stale_removed": stale,
        }
    finally:
        if own:
            con.close()
