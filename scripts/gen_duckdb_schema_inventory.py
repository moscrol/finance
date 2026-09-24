#!/usr/bin/env python3
"""把 market_feature_store/schema.sql 的对象清单投影进 CLAUDE.md 的生成块。

## 为什么要有它

CLAUDE.md「本地数据库 (DuckDB)」节原来手写「截至 2026-07-03 共 29 张表」——
两个月后生产库是 49 表 + 2 视图, 没人改那句话, 门禁也照常发绿。同一份清单存两处
必漂, 漂的时候没人知道 (AGENTS.md 已把这条写成纪律)。处方与 skills 表一样:
文档里只放**从 SSOT 生成的块**, 手写正文只放指针与契约。

## 放什么、不放什么

- 放: 对象名、表/视图、分层 (dim_/fact_/config_/feature_/ops_)。这些来自 schema.sql,
  提交即确定, `--check` 可在 CI 复核。
- 不放: 行数、日期范围、文件大小。它们每天变, 生成进文档等于每天一个 diff;
  要看现状跑 `python3 -m market_feature_store.cli info`。

用法:
    python3 scripts/gen_duckdb_schema_inventory.py            # 写回 CLAUDE.md
    python3 scripts/gen_duckdb_schema_inventory.py --check    # 只比对, 漂了退出码 1
    python3 scripts/gen_duckdb_schema_inventory.py --print    # 打印块内容
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = REPO_ROOT / "market_feature_store" / "schema.sql"
DOC_PATH = REPO_ROOT / "CLAUDE.md"

MARKER_BEGIN = (
    "<!-- BEGIN GENERATED: duckdb-schema-inventory | scripts/gen_duckdb_schema_inventory.py"
    " | 来源 market_feature_store/schema.sql；行数等易变数字不进文档，看 cli info -->"
)
MARKER_END = "<!-- END GENERATED: duckdb-schema-inventory -->"

_TABLE_RE = re.compile(
    r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([A-Za-z_][A-Za-z0-9_]*)", re.IGNORECASE
)
_VIEW_RE = re.compile(
    r"CREATE\s+(?:OR\s+REPLACE\s+)?VIEW\s+([A-Za-z_][A-Za-z0-9_]*)", re.IGNORECASE
)

# 分层前缀与一句话职责; 顺序即文档顺序。
LAYERS: tuple[tuple[str, str], ...] = (
    ("dim_", "维度"),
    ("fact_", "事实镜像 (外部来源, 可重建)"),
    ("config_", "人工配置"),
    ("feature_", "特征 (由事实计算, 可删重算)"),
    ("ops_", "运行台账 / 收据"),
)


def parse_schema(text: str) -> tuple[list[str], list[str]]:
    tables = sorted(set(_TABLE_RE.findall(text)))
    views = sorted(set(_VIEW_RE.findall(text)))
    return tables, views


def _layer_of(name: str) -> str:
    for prefix, _ in LAYERS:
        if name.startswith(prefix):
            return prefix
    return "other"


def render_block(tables: list[str], views: list[str]) -> str:
    view_set = set(views)
    by_layer: dict[str, list[str]] = {prefix: [] for prefix, _ in LAYERS}
    by_layer["other"] = []
    for name in sorted(set(tables) | view_set):
        by_layer[_layer_of(name)].append(name)

    lines = [
        MARKER_BEGIN,
        f"共 {len(tables)} 张表 + {len(views)} 个视图（`schema.sql` 声明；生产库以 `cli info` 为准）。"
        "带 `(V)` 的是 VIEW。",
        "",
        "| 层 | 数量 | 对象 |",
        "|---|---|---|",
    ]
    for prefix, desc in LAYERS + (("other", "未分层"),):
        names = by_layer.get(prefix) or []
        if not names:
            continue
        n_tables = sum(1 for n in names if n not in view_set)
        n_views = len(names) - n_tables
        count = f"{n_tables} 表" + (f" + {n_views} 视图" if n_views else "")
        rendered = ", ".join(f"`{n}`" + (" (V)" if n in view_set else "") for n in names)
        lines.append(f"| `{prefix}` {desc} | {count} | {rendered} |")
    lines.append(MARKER_END)
    return "\n".join(lines)


def splice(doc: str, block: str) -> str:
    start = doc.find(MARKER_BEGIN)
    end = doc.find(MARKER_END)
    if start == -1 or end == -1 or end < start:
        raise SystemExit(
            f"CLAUDE.md 里找不到成对的生成块标记；请先在「本地数据库 (DuckDB)」节放入:\n"
            f"{MARKER_BEGIN}\n{MARKER_END}"
        )
    end += len(MARKER_END)
    return doc[:start] + block + doc[end:]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="只比对, 文档块与 schema.sql 不一致时退出码 1")
    mode.add_argument("--print", action="store_true", help="打印生成块, 不写文件")
    args = parser.parse_args(argv)

    tables, views = parse_schema(SCHEMA_PATH.read_text(encoding="utf-8"))
    block = render_block(tables, views)
    if args.print:
        print(block)
        return 0

    doc = DOC_PATH.read_text(encoding="utf-8")
    updated = splice(doc, block)
    if args.check:
        if updated == doc:
            print(f"✅ CLAUDE.md DuckDB 清单与 schema.sql 一致 ({len(tables)} 表 + {len(views)} 视图)")
            return 0
        print("❌ CLAUDE.md DuckDB 清单落后于 schema.sql；跑 python3 scripts/gen_duckdb_schema_inventory.py 回写")
        return 1
    if updated != doc:
        DOC_PATH.write_text(updated, encoding="utf-8")
        print(f"已回写 CLAUDE.md 生成块 ({len(tables)} 表 + {len(views)} 视图)")
    else:
        print("CLAUDE.md 生成块已是最新")
    return 0


if __name__ == "__main__":
    sys.exit(main())
