#!/usr/bin/env python3
"""门禁：双红三阈值的复印件扫描（三种形状）。

原稿只写了「`rg` 那条 SQL 失败」。实测：那条命令在 `daily_review.py` 上命中 **0**
处，而该文件有 3 处跨行 SQL + 1 处 Python 内联——本仓最重要的消费者，单行检法一
处都抓不到。所以扫描必须分三种形状：

    形状一  SQL 三条件，单行        16 个实验脚本那种
    形状二  SQL 三条件，跨行        daily_review.py:403-405 / 612-614 / 707-709
    形状三  Python 内联比较          daily_review.py:478（变量名已改短，前两条都不命中）

形状一是形状二的子集（同一条正则加 DOTALL 即可），所以实现里只有两条正则。

**散文抄写抓不到**：`daily_review.py:1228` 的 🔥 图例用中文写同一组阈值，三种形状
都不覆盖。那一处走「引用 `DOUBLE_RED_DESCRIPTION` / 生成」，不靠本门禁。

用法：
    python3 scripts/check_double_red_copies.py [路径...]     # 默认扫生产目录
    退出码 0 = 无命中；1 = 有命中（逐条打印文件:行）
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# 默认只扫生产代码。实验脚本按目录整体豁免——手维护的文件 allowlist 会立刻变成
# 下一份复印件，且它自己没有棘轮。
DEFAULT_ROOTS = ("market_feature_store", "intelligence", "evolution", "scripts")
EXEMPT_DIRS = (
    "research/market-hypothesis/_scripts",
    # 钉字面测试本来就该包含那条字面（test_asof_prefetch_dual_red 等）。用目录规则，
    # 不用文件清单——手维护的 allowlist 会变成下一份会漂的名单。
    "intelligence/tests",
)
# 正典是稿里写明的唯一文件例外。扫描器自己靠 __file__ 跳过，不进手维护名单。
CANONICAL_FILE = "market_feature_store/signals.py"

# 形状一 + 二：SQL 三条件。限长间隔避免跨越无关代码把两段凑成一处误报。
SQL_SHAPE = re.compile(
    r"pct_chg\s*>\s*0[\s\S]{0,120}?diff_ratio\s*>\s*10[\s\S]{0,120}?amount\s*>\s*500",
    re.IGNORECASE,
)
# 形状三：Python 内联比较，变量名任意（`pct > 0 and diff > 10 and amount > 500`）。
INLINE_SHAPE = re.compile(
    r">\s*0\s+and\b[^\n]{0,80}?>\s*10\s+and\b[^\n]{0,80}?>\s*500"
)


@dataclass(frozen=True)
class Hit:
    path: str
    line: int
    shape: str
    excerpt: str


def scan_text(text: str, *, path: str = "<text>") -> list[Hit]:
    """扫一份源码文本，返回三种形状的全部命中。"""

    hits: list[Hit] = []
    for match in SQL_SHAPE.finditer(text):
        line = text.count("\n", 0, match.start()) + 1
        shape = "sql-multiline" if "\n" in match.group(0) else "sql-inline"
        hits.append(Hit(path, line, shape, match.group(0).split("\n")[0].strip()))
    for match in INLINE_SHAPE.finditer(text):
        line = text.count("\n", 0, match.start()) + 1
        if any(hit.line == line and hit.shape.startswith("sql") for hit in hits):
            continue  # 同一行已被 SQL 形状记过，不重复计数
        hits.append(Hit(path, line, "python-inline", match.group(0).strip()))
    return sorted(hits, key=lambda hit: (hit.line, hit.shape))


def _is_exempt(rel: str, path: Path) -> bool:
    if path.resolve() == Path(__file__).resolve():
        return True
    return rel == CANONICAL_FILE or any(rel.startswith(prefix) for prefix in EXEMPT_DIRS)


def scan_paths(roots: tuple[str, ...] = DEFAULT_ROOTS) -> list[Hit]:
    hits: list[Hit] = []
    for root in roots:
        base = REPO / root
        if not base.exists():
            continue
        targets = [base] if base.is_file() else sorted(base.rglob("*.py"))
        for path in targets:
            rel = path.relative_to(REPO).as_posix()
            if _is_exempt(rel, path):
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            hits.extend(scan_text(text, path=rel))
    return hits


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", help="限定扫描根，默认扫生产目录")
    args = parser.parse_args()
    roots = tuple(args.paths) if args.paths else DEFAULT_ROOTS
    hits = scan_paths(roots)
    for hit in hits:
        print(f"{hit.path}:{hit.line}\t{hit.shape}\t{hit.excerpt}")
    print(f"\n{len(hits)} hit(s) across {len({hit.path for hit in hits})} file(s)")
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())
