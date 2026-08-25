#!/usr/bin/env python3
"""dataset 注册审计 — 入库了的表，agent 够不够得着。

--------------------------------------------------------------------------
它抓的是什么
--------------------------------------------------------------------------

一张表从「写进 DuckDB」到「agent 能查」要过两道：

    schema.sql 建表 → 有写入链填数 → 注册进 finance_query._DATASETS

**采集侧有 daily-full 这条天天跑的流水线，暴露侧没有对应的门。** 于是历史上反复
出现同一个形状：表建好了、数灌满了、覆盖率审计全绿，而 agent 问到它时答「查不到」。
2026-08-13 接复盘会 6 张表时踩过一次（asset-inventory §9 原话：「入库 ≠ agent
能查到」），2026-08-25 查 UP 线/偏离度时又踩一次——203 万行躺在库里，语义层没有。

姊妹病是**「建表 ≠ 入库」**：``fact_top_gainers`` 只有 schema、没有写入链，
注册它只会得到一个永远返回 0 行的 dataset。这一条 grep 抓不到，只有 COUNT(*) 抓得到。

--------------------------------------------------------------------------
判据取自哪一侧（关键）
--------------------------------------------------------------------------

表清单取自 **``market_feature_store/schema.sql`` 的 DDL**，不取自 ``_DATASETS``。

姊妹脚本 ``audit_tool_reachability.py`` 的注释里记着一次教训：初版拿声明本身去合成
装配输入，于是「够不着」恒空、报了一次假绿。同一个坑在这里长这样——若从
``_DATASETS`` 出发去核对，那「没注册的表」按定义就是空集，审计变成照镜子。

--------------------------------------------------------------------------
两条规则
--------------------------------------------------------------------------

1. **二选一**：schema.sql 里每张 ``fact_*`` / ``feature_*`` 表，要么在 ``_DATASETS``
   注册，要么在 ``_UNREGISTERED_TABLES`` 写明理由。两边都没有 → 失败。
   这是棘轮：存量 25 张已带理由免检，**只拦新增**。

2. **空表不许静默注册**：注册了但 COUNT(*)=0 的表，必须列进 ``_EMPTY_BY_DESIGN``。
   需要真实 DuckDB，**没有库时这条自动跳过**（worktree 里 db/ 是 gitignore 的，
   fail closed 会让每棵树都提交不了）。规则 1 不依赖库，任何环境都硬拦。

退出码：0 = 通过；1 = 有表两边都没有，或有未声明的空表注册。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

SCHEMA_PATH = REPO_ROOT / "market_feature_store" / "schema.sql"
_CREATE_TABLE_RE = re.compile(
    r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([A-Za-z_][A-Za-z0-9_]*)",
    re.IGNORECASE,
)
# 只管这两个前缀：dim_ 是维度、ops_ 是台账，都不是 agent 该直接查的事实面。
_AUDITED_PREFIXES = ("fact_", "feature_")


def schema_tables(path: Path = SCHEMA_PATH) -> list[str]:
    """从 DDL 抽表名——**独立于 _DATASETS 的那一侧**。"""

    if not path.is_file():
        raise FileNotFoundError(f"找不到 schema：{path}")
    names = set(_CREATE_TABLE_RE.findall(path.read_text(encoding="utf-8")))
    return sorted(n for n in names if n.startswith(_AUDITED_PREFIXES))


def _count_rows(db_path: Path, tables: list[str]) -> dict[str, int] | None:
    """返回每张表的行数；库不可用时返回 None（跳过规则 2，不是判失败）。"""

    if not db_path.is_file():
        return None
    try:
        import duckdb
    except ImportError:
        return None
    con = None
    try:
        con = duckdb.connect(str(db_path), read_only=True)
        counts: dict[str, int] = {}
        for table in tables:
            try:
                row = con.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()
                counts[table] = int(row[0] or 0) if row else 0
            except Exception:
                # 表在 schema 里但库里还没建——不是本审计要抓的形状，跳过。
                continue
        return counts
    except Exception:
        return None
    finally:
        if con is not None:
            con.close()


def audit(db_path: Path | None = None) -> dict[str, object]:
    from intelligence.services.finance_query import (  # noqa: PLC0415
        _DATASETS,
        _EMPTY_BY_DESIGN,
        _UNREGISTERED_TABLES,
    )

    declared = schema_tables()
    registered = {d.table for d in _DATASETS.values()}
    exempted = set(_UNREGISTERED_TABLES)

    undeclared = sorted(set(declared) - registered - exempted)
    # 豁免名单里写了、但 schema.sql 里已经没有的表：陈旧条目，报告但不失败。
    stale_exemptions = sorted(exempted - set(declared))
    # 注册表里还有 VIEW（fact_sector_daily 等，CREATE VIEW 不是 CREATE TABLE），
    # 它们不在 declared 里。分开数，否则「注册+豁免」加起来会大于 declared，
    # 出现一个对不上账的总数——门禁自己的读数也得可复现。
    registered_in_schema = sorted(registered & set(declared))
    registered_views = sorted(registered - set(declared))

    empty_registered: list[str] = []
    counts = _count_rows(db_path, sorted(registered)) if db_path else None
    if counts is not None:
        empty_registered = sorted(
            t for t, n in counts.items() if n == 0 and t not in _EMPTY_BY_DESIGN
        )

    return {
        "declared": declared,
        "registered": sorted(registered),
        "registered_in_schema": registered_in_schema,
        "registered_views": registered_views,
        "exempted": sorted(exempted),
        "undeclared": undeclared,
        "stale_exemptions": stale_exemptions,
        "empty_registered": empty_registered,
        "row_check_ran": counts is not None,
        "ok": not undeclared and not empty_registered,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="机器可读输出（供 CI）")
    parser.add_argument(
        "--db",
        default=None,
        help="market_feature_store DuckDB 路径；给了且可读才跑「空表不许注册」那条",
    )
    args = parser.parse_args()

    db_path = Path(args.db).expanduser() if args.db else None
    result = audit(db_path)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["ok"] else 1

    print("=" * 72)
    print("dataset 注册审计 — 入库 vs agent 够得着（存量免检，只拦新增）")
    print("=" * 72)
    n_declared = len(result["declared"])
    n_in_schema = len(result["registered_in_schema"])
    n_exempt = len(result["exempted"])
    n_views = len(result["registered_views"])
    print(f"  schema.sql 声明   {n_declared} 张 fact_/feature_ 表（CREATE TABLE）")
    print(f"    ├ 已注册        {n_in_schema}")
    print(f"    └ 已写明豁免    {n_exempt}")
    print(f"  另注册 VIEW       {n_views} 个（不在 CREATE TABLE 里，单列以免总数对不上）")
    print(
        "  空表检查          "
        + ("已跑" if result["row_check_ran"] else "跳过（未提供可读的 DuckDB）")
    )
    print()

    if result["stale_exemptions"]:
        print("  ⓘ 豁免名单里有 schema.sql 已不存在的表（陈旧条目，可清理）：")
        for name in result["stale_exemptions"]:
            print(f"      - {name}")
        print()

    failed = False
    if result["undeclared"]:
        failed = True
        print(f"❌ {len(result['undeclared'])} 张表既没注册、也没写明豁免：")
        for name in result["undeclared"]:
            print(f"      - {name}")
        print()
        print("  二选一，都在 intelligence/services/finance_query.py：")
        print("    · 要给 agent 查 → 加进 _DATASETS（记得写 population/coverage）")
        print("    · 不给 agent 查 → 加进 _UNREGISTERED_TABLES，一行写清为什么")
        print("  别只在文档正文里写理由——那不是机器可读的，下一个人会读成「漏了」。")
        print()

    if result["empty_registered"]:
        failed = True
        print(f"❌ {len(result['empty_registered'])} 张注册了的表当前是空的：")
        for name in result["empty_registered"]:
            print(f"      - {name}")
        print()
        print("  空表注册进语义层 = 一个永远返回 0 行的 dataset，模型会据此答「暂无数据」。")
        print("  确属有意（如诚实闸锚点）就加进 _EMPTY_BY_DESIGN；否则先接上写入链。")
        print()

    if failed:
        return 1

    print("✅ 每张 fact_/feature_ 表都有归属（注册或写明豁免）")
    print()
    print(
        f"结论：通过（{n_in_schema} 注册 + {n_exempt} 豁免 = schema.sql 全部 "
        f"{n_declared} 张；另有 {n_views} 个注册的 VIEW）"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
