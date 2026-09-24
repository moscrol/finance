#!/usr/bin/env python3
"""列出「多条 SELECT 拼一份结论、却没绑定单快照」的函数——审计辅助，不是门禁。

## 缺陷是什么

DuckDB 自动提交模式下**每条 SELECT 各取一次快照**。于是一个发出 N 条 SELECT 的函数，
可以拼出一份由「从未同时成立」的数字组成的报告：里面每个数都真实存在过。这种报告比
直接报错危险——它看上去完全正常。

实例见 ``market_feature_store/hithink_sector_preview.py``（旧名单 + 新价格）与
``market_feature_store/query.py`` 的 ``health()``（体检单能算出「有成分股的板块比维表里
存在的板块还多」）。修法是 ``db.read_snapshot()``：``BEGIN TRANSACTION READ ONLY``。

## 为什么是列表不是闸

判「该不该绑快照」需要语义，AST 判不了（见下「不算同类」）。做成闸就必然要么误报连篇、
要么靠白名单养蛆，两种都会让人开始用 ``--no-verify``。所以这里只给候选 + 判据，人来裁。

## 人工判据（按顺序问）

1. **它把多条读取拼成一个对外结论吗？** 只是顺序执行几条无关查询（如逐表建索引）不算。
2. **这些读取之间有跨表依赖吗？** 例：早先读出的总数被后面的计数拿来比。
3. **读取是否全部以同一个不可变键为锚？** 若是，**不算同类**。
   ``sector_universe.completion_audit`` 就是这样：它第一条读出 ``snapshot_id``，其后每条
   都 ``WHERE snapshot_id = ?``，代际内的行不会被改写，所以内部不会打架。
   绑定快照能治「内部不自洽」，治不了「结论陈旧」——任何读取都只是某一时刻的。
4. **它是写者自己吗？** 写者持写事务时本就在单快照里；此时再调 ``read_snapshot`` 会
   因已持事务而 fail-closed，并把调用方事务置为 aborted（未提交改动丢失）。
   所以务必先确认调用点不在事务内，再施修。

用法::

    python scripts/audit_unsnapshotted_reads.py [包名 ...]   # 默认 market_feature_store
"""
from __future__ import annotations

import ast
import pathlib
import sys

GUARDS = ("read_snapshot", "BEGIN TRANSACTION")


def _select_count(node: ast.AST) -> int:
    """函数体内直接发出的 SELECT 条数（``con.execute("SELECT ...")`` 及 f-string 拼接）。"""
    total = 0
    for sub in ast.walk(node):
        if not isinstance(sub, ast.Call):
            continue
        if not isinstance(sub.func, ast.Attribute) or sub.func.attr not in {"execute", "sql"}:
            continue
        for arg in sub.args[:1]:
            text = None
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                text = arg.value
            elif isinstance(arg, ast.JoinedStr):
                # f-string 里只取字面量段：变量段的内容编译期不可知，宁可少算不可瞎猜。
                text = "".join(v.value for v in arg.values if isinstance(v, ast.Constant))
            if text and "SELECT" in text.upper():
                total += 1
    return total


def scan(roots: list[str]) -> list[tuple[int, bool, str, str]]:
    rows: list[tuple[int, bool, str, str]] = []
    for root in roots:
        for path in sorted(pathlib.Path(root).rglob("*.py")):
            try:
                source = path.read_text(errors="ignore")
                tree = ast.parse(source)
            except (SyntaxError, OSError):
                continue  # 扫不动的文件不该让整次审计失败
            for fn in [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
                count = _select_count(fn)
                if count < 2:
                    continue
                segment = ast.get_source_segment(source, fn) or ""
                guarded = any(g in segment for g in GUARDS)
                rows.append((count, guarded, f"{path}:{fn.lineno}", fn.name))
    rows.sort(key=lambda r: (-r[0], r[2]))
    return rows


def main(argv: list[str]) -> int:
    roots = argv[1:] or ["market_feature_store"]
    rows = scan(roots)
    unguarded = [r for r in rows if not r[1]]
    print(f"发出 ≥2 条 SELECT 的函数：{len(rows)} 个；已绑快照/事务：{len(rows) - len(unguarded)}")
    print("下列为**候选**，不是判决——请按脚本 docstring 的四条判据人工裁定：\n")
    for count, _, location, name in unguarded:
        print(f"  {count:>3} 条  {location}  {name}")
    print("\n退出码恒为 0：这是审计辅助，不是门禁。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
