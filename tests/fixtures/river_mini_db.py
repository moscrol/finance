"""时间长河契约测试用的最小夹具库。

**为什么要有这个文件。** `tests/test_river_slice.py` / `test_river_window.py` /
`test_river_query.py` / `test_river_cutoff_guard.py` 四个文件整份
``skipif(not DB.exists())``，而 ``.gitignore`` 把 ``db/`` 与 ``*.duckdb`` 全排除——
GitHub Actions 的 runner 上不可能有真库。于是这条河**最核心的契约（六轨联立、
无前视、幂等、可回溯）在 CI 上一次都没跑过**，只在开发机上验证过。本仓已经有过
「活测试被误扫进 archive、全树 pytest 停摆 33 天没人发现」的前科，同一类风险
不该在这条河上留第二个入口。

**为什么不是直接把这个库喂给那四个文件。** 它们断言的是**真实数据语义**：
2026 年板块供应商 .TI → .FP 的换源日、2026-01 那次回填批次让累计覆盖失真、
资金轨只有 12% 的日子有数、`fact_theme_fundamental_doc` 只有 5/37 份挂了
linked_sectors。合成库能让这些断言「变绿」，但绿得毫无意义——那正是本仓
反复警告的假门禁（AGENTS.md「红灯或无结论的 PR 照样能点合并」那一节）。
所以**真库测试原样保留**，本夹具只承载**可移植的契约断言**：那些不依赖任何
真实世界读数、换一套数据也必须成立的不变量。

**为什么从 ``schema.sql`` 建表而不是手写 DDL。** 手写 DDL 会和真 schema 悄悄漂开，
夹具于是测的是一个已经不存在的形状。从 SSOT 建表的代价是本模块要容忍
schema.sql 里少数非 DDL 片段（中文注释行被 ``;`` 切碎），收益是**列改了夹具会
立刻报错**——``_require_tables`` 显式断言河要用的十张表都建出来了，建不出就抛错，
不静默降级成「少测几条」。

用法::

    from tests.fixtures.river_mini_db import build_mini_db
    db = build_mini_db(tmp_path / "mini.duckdb")
    sl = slice_river("2026-08-31", "算力租赁", db_path=db, checkpoints_path=...)
"""

from __future__ import annotations

import json
import re
from datetime import date, timedelta
from pathlib import Path

SCHEMA = Path(__file__).resolve().parents[2] / "market_feature_store" / "schema.sql"

# 河要用到的表。建不出任何一张就抛错——夹具少一张表 = 对应那条轨恒缺口，
# 断言会「通过」但什么都没守住。
REQUIRED_TABLES = (
    "fact_market_daily",
    "fact_sector_daily",
    "fact_sector_stock_daily",
    "fact_stock_daily",
    "fact_theme_flow_daily",
    "fact_theme_limit_heat_daily",
    "fact_theme_limit_stock_daily",
    "fact_theme_fundamental_doc",
    "fact_research_report_catalog",
    "config_sector_alias",
)

# ---- 夹具的世界观（故意构造，用来触达具体分支，不是模拟真实行情）----------- #
START = date(2026, 8, 17)
DAYS = 15  # 交易日数（跳过周末）

ENTITY = "算力租赁"
ENTITY_CODE = "801080.TI"

# 换源实体：前半段挂旧代码 .TI，后半段挂新代码 .FP，别名表把旧映到新。
# 用来守「entity_id 跨换源稳定 / alias_applied 如实标记 / ref 不被归一改写」。
ALIAS_ENTITY = "半导体"
ALIAS_OLD_CODE = "801081.TI"
ALIAS_NEW_CODE = "801081.FP"
ALIAS_SWITCH_INDEX = 8  # 第 8 个交易日起换成新代码

# 无卖方覆盖的实体：用来守「舆论轨缺口是 no_data 且 detail 写明原因」。
BARE_ENTITY = "冷门板块"
BARE_CODE = "801099.TI"

RECORDED_HOUR = "18:00:00"  # 所有事实行的 updated_at：当日盘后


def trading_days(start: date = START, count: int = DAYS) -> list[str]:
    """跳过周末的连续交易日。夹具不处理法定节假日——河的契约不依赖日历正确性，
    依赖它的是 `trading_days.py`，那是另一个对象的测试。"""
    out: list[str] = []
    d = start
    while len(out) < count:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def _statements(sql: str) -> list[str]:
    """把 schema.sql 切成可执行语句。

    先剥块注释与整行 ``--`` 注释再按 ``;`` 切：schema.sql 的行尾注释里有中文句号与
    分号，不剥的话会把一条 CREATE TABLE 切成三段，报出三个看不懂的 Parser Error。
    """
    sql = re.sub(r"/\*.*?\*/", "", sql, flags=re.S)
    sql = "\n".join(line for line in sql.splitlines() if not line.strip().startswith("--"))
    return [s.strip() for s in sql.split(";") if s.strip()]


def _require_tables(con) -> None:
    present = {r[0] for r in con.execute("SELECT table_name FROM information_schema.tables").fetchall()}
    missing = [t for t in REQUIRED_TABLES if t not in present]
    if missing:
        raise RuntimeError(
            f"夹具库缺表 {missing}——schema.sql 可能改过名或本模块的解析漏了语句。"
            " 不要靠跳过这些表继续跑：少一张表那条轨就恒缺口，断言会假绿。"
        )


def build_mini_db(path: str | Path) -> str:
    """按 ``schema.sql`` 建库并灌入确定性夹具数据，返回库路径。

    数据全部由下标算出，无随机、无当前时间依赖——同一份代码两次构建的库里
    每一行都相同，否则「幂等」那条断言守的就是夹具的稳定性而不是河的。
    """
    import duckdb

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()

    con = duckdb.connect(str(path))
    try:
        for stmt in _statements(SCHEMA.read_text(encoding="utf-8")):
            try:
                con.execute(stmt)
            except Exception:  # noqa: BLE001
                # schema.sql 里混有少量非 DDL 片段（被注释里的分号切出来的残行）。
                # 逐条容错、最后用 _require_tables 兜底：关心的是「河要的表在不在」，
                # 不是「每条语句都跑通」。
                continue
        _require_tables(con)
        _seed(con)
    finally:
        con.close()
    return str(path)


# 下面四条逐日序列的唯一目的，是让每个「单日切片可判」的注册标签在这 15 天里
# **三种结局都出现过**（真 / 假 / 缺原料）。不这么做，测试会在「整列恒为 None」
# 上假绿：断言照样通过，但它什么都没验到——这正是本仓反复点名的假门禁形状。
# 覆盖本身由 test_夹具必须让每个可判标签都出现过真_假_缺三种结局 守住。
#
# diff_ratio：阈值 DUAL_RED_DIFF_RATIO_GT=10。>10 且 pct>0 且 amount>500 → dual_red_strict True。
#   None 用来打出三值逻辑的「已知的都为真、仍有缺失」那一格。
#   注意不能整列为 0：>90% published 板块 diff_ratio=0 会被判成 data_gap 日。
DIFF_RATIO_BY_DAY: tuple[float | None, ...] = (
    0.6, 12.0, 15.0, 11.5, None, 0.6, 13.0, 14.0, 0.6, None, 12.5, 0.6, 16.0, 11.0, 0.6,
)
# multi_period_resonance：布尔列直接投影，三值全覆盖。
RESONANCE_BY_DAY: tuple[bool | None, ...] = (
    None, True, True, False, None, False, True, True, False, None, True, False, True, True, False,
)
# amount_vs_yesterday_pct：阈值 VOLUME_SURGE_PCT=10，严格大于才算放量。
#   刻意放一个恰好等于 10.0 的日子——边界用 > 还是 >= 写错时，只有这一格会红。
VOLUME_PCT_BY_DAY: tuple[float | None, ...] = (
    None, 25.0, 30.0, 10.0, -5.0, 3.0, 18.0, 22.0, -12.0, None, 15.0, 2.0, 28.0, 9.99, -3.0,
)
# 涨停热度名次：1 名次越小越热；留两天 None 给「当天没进榜」。
HEAT_RANK_BY_DAY: tuple[int | None, ...] = (
    None, 12, 7, 3, 2, 8, 4, 1, 5, None, 6, 15, 2, 3, 9,
)


def _seed(con) -> None:
    days = trading_days()
    stages = ["震荡", "震荡", "主升", "主升", "主升", "分歧", "分歧", "主升",
              "主升", "退潮", "退潮", "震荡", "震荡", "主升", "主升"]

    for i, day in enumerate(days):
        rec = f"{day} {RECORDED_HOUR}"
        stage = stages[i % len(stages)]
        pct = round(((i * 37) % 13) - 4 + 0.5, 2)
        diff = DIFF_RATIO_BY_DAY[i]
        resonance = RESONANCE_BY_DAY[i]
        vol_pct = VOLUME_PCT_BY_DAY[i]
        heat_rank = HEAT_RANK_BY_DAY[i]

        con.execute(
            """INSERT OR REPLACE INTO fact_market_daily
               (trade_date, market_stage, total_amount, amount_ma20, amount_vs_yesterday_pct,
                advancers, limit_up, limit_down,
                sh_week_ma, sh_deviation_pct, sh_index_close, sh_index_pct_chg, volume_state,
                source, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,'fixture',?)""",
            [day, stage, 1.5e12 + (i % 5) * 8e10, 1.6e12, vol_pct,
             2500 + i * 40, 60 + (i * 7) % 40,
             10 + i % 7, 3300.0, round(i * 0.3 - 2, 2), 3300 + i * 9, pct, "放量", rec],
        )
        con.execute(
            """INSERT OR REPLACE INTO ops_sector_universe_snapshot_daily
               (trade_date, snapshot_id, provider_source, sector_count,
                declared_relationship_count, status, captured_at)
               VALUES (?, 'snap1', 'fixture', 3, 3, 'published', ?)""",
            [day, rec],
        )

        alias_code = ALIAS_OLD_CODE if i < ALIAS_SWITCH_INDEX else ALIAS_NEW_CODE
        sectors = [
            (ENTITY_CODE, ENTITY),
            (alias_code, ALIAS_ENTITY),
            (BARE_CODE, BARE_ENTITY),
        ]
        for code, name in sectors:
            con.execute(
                """INSERT OR REPLACE INTO fact_sector_daily_generation
                   (trade_date, sector_universe_snapshot_id, sector_ts_code, sector_name,
                    sw_l1, pct_chg, amount, diff_ratio, strength, multi_period_resonance,
                    source, updated_at)
                   VALUES (?, 'snap1', ?, ?, ?, ?, ?, ?, ?, ?, 'fixture', ?)""",
                [day, code, name, name, pct, 8e10 + i * 1e9, diff, round(1 + i * 0.1, 2),
                 resonance, rec],
            )
            con.execute(
                """INSERT OR REPLACE INTO fact_sector_stock_daily_generation
                   (trade_date, sector_universe_snapshot_id, sector_ts_code, sector_name,
                    stock_ts_code, stock_name, price, pct_chg, amount,
                    fund_flow_1d, fund_flow_5d, limit_times, high_status_label,
                    source, updated_at)
                   VALUES (?, 'snap1', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'fixture', ?)""",
                [day, code, name, f"300{i:03d}.SZ", f"{name}龙头", 100.0 + i, pct, 5.5e9,
                 3e8 - i * 2e7, 7.7e8, i % 4, f"{i % 4}板", rec],
            )
            con.execute(
                """INSERT OR REPLACE INTO fact_theme_limit_heat_daily
                   (trade_date, sector_ts_code, sector_name, dimension, scope,
                    limit_up_count, total_count, limit_up_ratio, rank, source, updated_at)
                   VALUES (?, ?, ?, 'concept', 'all', ?, 30, ?, ?, 'fixture', ?)""",
                [day, code, name, (i * 3) % 9, round(((i * 3) % 9) / 30, 4), heat_rank, rec],
            )
            # 涨停成分：up_stat 是「1/1」这种字符串，sync 已把它解析成两个整数列。
            # 题材轨断言读的是整数列，夹具必须把两边都填上，否则守不住「不要再去解析字符串」。
            con.execute(
                """INSERT OR REPLACE INTO fact_theme_limit_stock_daily
                   (trade_date, sector_ts_code, sector_name, stock_ts_code, stock_name,
                    price, pct_chg, amount, limit_times, limit_status, first_limit_time,
                    up_stat, up_stat_days, up_stat_boards, high_status, high_status_label,
                    source, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, '涨停', '09:35:00', ?, ?, ?, ?, ?, 'fixture', ?)""",
                [day, code, name, f"300{i:03d}.SZ", f"{name}龙头", 100.0 + i, 10.0, 5.5e9,
                 1 + i % 3, f"{1 + i % 3}/{1 + i % 3}", 1 + i % 3, 1 + i % 3,
                 f"{1 + i % 3}板", f"{1 + i % 3}板", rec],
            )
            con.execute(
                """INSERT OR REPLACE INTO fact_theme_flow_daily
                   (trade_date, theme_code, theme_name, total_fund, total_amount,
                    stock_count, fund_caliber, source, updated_at)
                   VALUES (?, ?, ?, ?, ?, 30, 'main', 'fixture', ?)""",
                [day, f"T{code}", name, 4e8 - i * 1e7, 8.8e10, rec],
            )
            con.execute(
                """INSERT OR REPLACE INTO fact_stock_daily
                   (trade_date, stock_ts_code, stock_name, close, pre_close, pct_chg,
                    amount, turnover, source, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'fixture', ?)""",
                [day, f"300{i:03d}.SZ", f"{name}龙头", 100.0 + i, 99.0 + i, pct, 5.5e9, 4.1, rec],
            )

    # 别名表：旧代码 → 新代码。note 照真表的口径写清「归一身份不归一可比性」。
    con.execute(
        """INSERT OR REPLACE INTO config_sector_alias
           (alias, sector_ts_code, sector_name, confidence, note, updated_at)
           VALUES (?, ?, ?, 1.0, '两套口径成分不同，跨切换日数值不可直接比较', ?)""",
        [ALIAS_OLD_CODE, ALIAS_NEW_CODE, ALIAS_ENTITY, f"{days[0]} {RECORDED_HOUR}"],
    )

    # 研报：标签是 JSON 数组（`_report_tags` 用 json.loads 解析，逗号串会被整条丢掉）。
    # 只给 ENTITY 与 ALIAS_ENTITY 发覆盖，BARE_ENTITY 一份都不给——
    # 「无覆盖 → no_data 缺口」这条分支要有阳性对照才算守住。
    for n, day in enumerate(days[:6]):
        con.execute(
            """INSERT OR REPLACE INTO fact_research_report_catalog
               (report_id, title, report_date, report_type, is_hot, sector_tags,
                concept_tags, stock_count, stocks, created_at, source, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,'fixture',?)""",
            [n + 1, f"{ENTITY}深度 {n + 1}", day, "深度", n % 2 == 0,
             json.dumps([ENTITY], ensure_ascii=False), json.dumps([ENTITY], ensure_ascii=False),
             1, json.dumps([f"300{n:03d}.SZ"]),
             f"{day} 09:00:00",
             # updated_at 故意设成全表同一天（复刻真表被批量重写抹平的形状），
             # 逼着舆论轨去读 created_at——读错列这条断言会红。
             f"{days[-1]} 23:00:00"],
        )

    con.execute(
        """INSERT OR REPLACE INTO fact_theme_fundamental_doc
           (document_pk, title, produced_at, workflow_name, analysis_type, core_theme,
            verification_points, linked_themes, linked_sectors, kb_path, source, updated_at)
           VALUES (1, ?, ?, 'fixture-flow', '产业链', ?, ?, ?, ?, 'kb/fixture.md', 'fixture', ?)""",
        [f"{ENTITY}产业链梳理", f"{days[2]}T10:00:00", f"{ENTITY}的核心逻辑是算力租赁价格",
         json.dumps(["订单兑现"], ensure_ascii=False), json.dumps([ENTITY], ensure_ascii=False),
         # linked_sectors 是 **dict 列表**（`{sector_code, sector_name}`），不是字符串列表。
         # 写成字符串列表时 `_fundamental_docs` 的 `x.get(...)` 会整条跳过，
         # 文档静默接不上——这正是 2026-09-06 审计发现「整表无生产读取方」的形状。
         json.dumps([{"sector_code": ENTITY_CODE, "sector_name": ENTITY}], ensure_ascii=False),
         f"{days[2]} 10:00:00"],
    )


def checkpoint_fixture(as_of: str, entity: str = ENTITY) -> dict:
    """判断轨夹具记录。形状逐字段照抄真实 checkpoints.jsonl，不简化。

    `conftest.py` 会 delenv ``FORESIGHT_USERS_DIR``（防测试读写真人目录），所以
    判断轨必须显式喂文件，否则它在测试进程里恒为缺口——依赖它的断言会永远
    跳过，是假门禁。
    """
    return {
        "id": f"ck-{as_of}-fixture",
        "ts": f"{as_of}T16:31:49+00:00",
        "claim": f"[{as_of}][旧逻辑唤醒] {entity}：旧逻辑唤醒将获得新证据支撑",
        "category": "theme_evidence",
        "themes": [entity],
        "stocks": [],
        "metric": {"type": "kb_evidence", "op": ">=", "target": 1.0, "target_name": entity},
        "due": "2026-09-07",
        "source": "test-fixture",
    }
