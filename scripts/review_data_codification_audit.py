#!/usr/bin/env python3
"""复盘数据代码化审计：抓回来的东西，有多少变成了可算的量。

「代码化」的判据取自终局 §2 钦定词：**轨上每条都是带 as-of / 实体 / 硬度 / 来源哈希的
对象，规则可重算**；反面是「prompt 里的散文、截图、口头经验」。落到库上就是三问：

1. **写进来了吗** —— 列存在但填充率为 0，等于声明了没人写；
2. **有人读吗** —— 填满了但全仓没有生产代码读它，等于抓了存着看不见；
3. **读得动吗** —— 读的是整段散文还是结构化字段。散文能进 prompt，但**不能重算**，
   所以它进不了统计门、进不了聚类、进不了回放。

第 2 问的判据是**同一个 .py 文件里既提到那张表、又提到那一列**。单独 grep 列名会被
`note` / `title` / `reason` 这种普通词淹掉（实测 `note` 单独 grep 出 381 处，
共现法之后只剩 20 处且全是真读取方）。测试文件与写入方（sync / cli）不计入生产读取方：
只有测试读它，说明它没有真实消费者。

散文的判据（都要满足，任一不满足就不算散文，避免把枚举字段误判）：
平均长度 ≥ 40 字符，且去重率 ≥ 0.5（枚举字段去重率极低）。

用法::

    python3 scripts/review_data_codification_audit.py            # 人读
    python3 scripts/review_data_codification_audit.py --json     # 收据
    python3 scripts/review_data_codification_audit.py --only-gaps  # 只看有问题的

只读，不改库。
"""

from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_DB = "db/market_feature_store.duckdb"

# 扫这些前缀的表。ops_ 是运维台账、feature_ 已知无活跃消费者，单列不混入主结论。
FACT_PREFIXES = ("fact_", "dim_", "config_")

# 这些列是每张表都有的元数据，不参与「有没有人读」的判定——它们本来就不是被读的量。
META_COLUMNS = frozenset(
    {"source", "updated_at", "created_at", "trade_date", "sector_universe_snapshot_id"}
)

PROSE_MIN_LEN = 40
PROSE_MIN_DISTINCT_RATIO = 0.5


@dataclass
class ColumnAudit:
    table: str
    column: str
    dtype: str
    rows: int
    filled: int
    distinct: int
    avg_len: float | None
    readers: list[str] = field(default_factory=list)
    test_only: list[str] = field(default_factory=list)

    @property
    def fill_rate(self) -> float:
        return self.filled / self.rows if self.rows else 0.0

    @property
    def distinct_ratio(self) -> float:
        return self.distinct / self.filled if self.filled else 0.0

    @property
    def is_prose(self) -> bool:
        return (
            self.dtype == "VARCHAR"
            and (self.avg_len or 0) >= PROSE_MIN_LEN
            and self.distinct_ratio >= PROSE_MIN_DISTINCT_RATIO
        )

    @property
    def verdict(self) -> str:
        """一列的代码化状态。顺序即优先级：空列最严重，其次没人读，再次散文。"""
        if self.rows == 0:
            return "table_empty"
        if self.filled == 0:
            return "never_written"  # 列声明了，从来没写进过值
        if not self.readers:
            return "unread_by_production"  # 存着，但生产代码看不见
        if self.is_prose:
            return "prose_readable_not_computable"  # 有人读，但读的是散文，不可重算
        return "codified"

    def to_dict(self) -> dict[str, Any]:
        return {
            "table": self.table,
            "column": self.column,
            "dtype": self.dtype,
            "rows": self.rows,
            "fill_rate": round(self.fill_rate, 4),
            "distinct": self.distinct,
            "avg_len": None if self.avg_len is None else round(self.avg_len, 1),
            "verdict": self.verdict,
            "readers": self.readers,
            "test_only_readers": self.test_only,
        }


def _load_sources(root: Path) -> dict[str, str]:
    """一次性读入全部 .py。逐列 grep 会跑上千次子进程，这里换成内存里查。"""
    skip = re.compile(r"(^|/)(\.venv|\.git|tmp|node_modules|__pycache__|\.code-review-graph)(/|$)")
    out: dict[str, str] = {}
    for path in root.rglob("*.py"):
        rel = str(path.relative_to(root))
        if skip.search(rel):
            continue
        try:
            out[rel] = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
    return out


def _is_writer(rel: str) -> bool:
    name = Path(rel).name
    return "sync" in rel or name in {"cli.py", "schema.sql"} or "/migrations/" in rel


def _is_test(rel: str) -> bool:
    name = Path(rel).name
    return rel.startswith("tests/") or "/tests/" in rel or name.startswith("test_")


def audit(db_path: Path, root: Path) -> dict[str, Any]:
    import duckdb

    if not db_path.exists():
        raise SystemExit(f"数据库不存在：{db_path}（不自动创建）")
    sources = _load_sources(root)

    con = duckdb.connect(str(db_path), read_only=True)
    try:
        tables = [
            (t, ty)
            for t, ty in con.execute(
                """
                SELECT table_name, table_type FROM information_schema.tables
                WHERE table_schema = 'main' ORDER BY table_name
                """
            ).fetchall()
            if str(t).startswith(FACT_PREFIXES)
        ]
        # VIEW 的底层 *_generation 表已单独审计，跳过以免同一列算两遍。
        tables = [(t, ty) for t, ty in tables if ty == "BASE TABLE"]

        results: list[ColumnAudit] = []
        for table, _ty in tables:
            cols = con.execute(
                """
                SELECT column_name, data_type FROM information_schema.columns
                WHERE table_schema = 'main' AND table_name = ? ORDER BY ordinal_position
                """,
                [table],
            ).fetchall()
            n_rows = con.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]  # noqa: S608
            files_with_table = {rel for rel, text in sources.items() if table in text}
            for col, dtype in cols:
                if n_rows:
                    if dtype == "VARCHAR":
                        filled, distinct, avg_len = con.execute(
                            f'SELECT COUNT("{col}"), COUNT(DISTINCT "{col}"), '  # noqa: S608
                            f'AVG(LENGTH("{col}")) FROM "{table}"'
                        ).fetchone()
                    else:
                        filled, distinct = con.execute(
                            f'SELECT COUNT("{col}"), COUNT(DISTINCT "{col}") FROM "{table}"'  # noqa: S608
                        ).fetchone()
                        avg_len = None
                else:
                    filled = distinct = 0
                    avg_len = None
                hits = [rel for rel in files_with_table if col in sources[rel]]
                readers = sorted(r for r in hits if not _is_writer(r) and not _is_test(r))
                tests = sorted(r for r in hits if _is_test(r))
                results.append(
                    ColumnAudit(
                        table=table,
                        column=str(col),
                        dtype=str(dtype),
                        rows=n_rows,
                        filled=filled or 0,
                        distinct=distinct or 0,
                        avg_len=avg_len,
                        readers=readers,
                        test_only=tests,
                    )
                )
    finally:
        con.close()

    business = [c for c in results if c.column not in META_COLUMNS]
    by_verdict: dict[str, list[ColumnAudit]] = {}
    for c in business:
        by_verdict.setdefault(c.verdict, []).append(c)
    return {
        "db": str(db_path),
        "tables_audited": len(tables),
        "columns_total": len(results),
        "columns_business": len(business),
        "summary": {k: len(v) for k, v in sorted(by_verdict.items())},
        "by_verdict": {k: [c.to_dict() for c in v] for k, v in by_verdict.items()},
    }


_LABEL = {
    "codified": "✅ 已代码化（有生产读取方，且不是散文）",
    "prose_readable_not_computable": "📄 散文：有人读，但不可重算",
    "unread_by_production": "❌ 存了没人读（生产代码里无读取方）",
    "never_written": "⭕ 声明了从没写过值（填充率 0）",
    "table_empty": "⬜ 空表",
}


def render(result: dict[str, Any], only_gaps: bool = False) -> str:
    out = [
        f"复盘数据代码化审计  db={result['db']}",
        f"  {result['tables_audited']} 张表 / {result['columns_total']} 列"
        f"（去掉 source、updated_at 等元数据列后 {result['columns_business']} 列参与判定）",
        "",
    ]
    for verdict, count in sorted(result["summary"].items(), key=lambda kv: -kv[1]):
        out.append(f"  {_LABEL.get(verdict, verdict):<34} {count:>4} 列")
    out.append("")
    order = ["never_written", "unread_by_production", "prose_readable_not_computable", "table_empty"]
    if not only_gaps:
        order.append("codified")
    for verdict in order:
        items = result["by_verdict"].get(verdict) or []
        if not items:
            continue
        out.append(f"── {_LABEL.get(verdict, verdict)}（{len(items)}）" + "─" * 20)
        items.sort(key=lambda d: (-d["rows"], d["table"], d["column"]))
        for d in items[:60]:
            extra = ""
            if verdict == "prose_readable_not_computable":
                extra = f"  平均 {d['avg_len']:.0f} 字符  读取方 {len(d['readers'])}"
            elif verdict == "unread_by_production":
                extra = f"  填充 {d['fill_rate']:.0%}" + (
                    f"  仅测试读 {len(d['test_only_readers'])} 处" if d["test_only_readers"] else ""
                )
            out.append(f"  {d['table']}.{d['column']:<28} 行 {d['rows']:>9,}{extra}")
        if len(items) > 60:
            out.append(f"  …… 另有 {len(items) - 60} 列，用 --json 看全量")
        out.append("")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=os.environ.get("MARKET_FEATURE_STORE_DB", DEFAULT_DB))
    ap.add_argument("--root", default=".", help="代码扫描根目录")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--only-gaps", action="store_true", help="只列有问题的，不列已代码化的")
    args = ap.parse_args()

    result = audit(Path(args.db).expanduser(), Path(args.root).resolve())
    print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else render(result, args.only_gaps))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
