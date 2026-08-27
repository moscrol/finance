#!/usr/bin/env python3
"""三方逐题对照：改前基线 / 纯尺子(Phase1+2+3) / 含产品(Phase1-4.5)。

自证优先：先证明三份都解析出 28 题且真值列非空，再看结论。
真值列 = markdown 表第 5 列。
"""

from __future__ import annotations

import re
import sys
from collections import Counter

COLS = ["题", "组", "来源", "运行", "真值"]


def parse(path: str) -> dict[str, str]:
    rows: dict[str, str] = {}
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if not line.startswith("|"):
                continue
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) < 5 or not re.match(r"^[ABC]\d+-", cells[0]):
                continue
            rows[cells[0]] = cells[4]
    return rows


def selfcheck(tag: str, rows: dict[str, str]) -> None:
    nonempty = sum(1 for v in rows.values() if v)
    print(f"  {tag:<10} 解析 {len(rows):>2} 题 / 真值非空 {nonempty:>2}")
    if len(rows) != 28 or nonempty != 28:
        sys.exit(f"❌ {tag} 解析数不等于 28，先修脚本再看结论")


def main() -> None:
    base_p, pure_p, prod_p = sys.argv[1], sys.argv[2], sys.argv[3]
    base, pure, prod = parse(base_p), parse(pure_p), parse(prod_p)

    print("自证（先证明读到了值）：")
    selfcheck("改前基线", base)
    selfcheck("纯尺子", pure)
    selfcheck("含产品", prod)

    print("\n真值分布：")
    for tag, rows in (("改前基线", base), ("纯尺子", pure), ("含产品", prod)):
        c = Counter(rows.values())
        print(f"  {tag:<10} 通过 {c.get('✅ 通过',0):>2} / 失败 {c.get('❌ 失败',0):>2} / 不可判 {c.get('❔ 不可判',0):>2}")

    print("\n逐题三方对照（只列有变化的）：")
    print(f"  {'题':<32} {'改前':<8} {'纯尺子':<8} {'含产品':<8} 归因")
    ruler_only, product_only, both, regress = [], [], [], []
    for k in sorted(base, key=lambda x: (x[0], int(re.match(r"[ABC](\d+)", x).group(1)))):
        b, u, p = base[k], pure.get(k, "?"), prod.get(k, "?")
        if b == u == p:
            continue
        if b != u and u == p:
            tag, bucket = "量具", ruler_only
        elif b == u and u != p:
            tag, bucket = "产品", product_only
        else:
            tag, bucket = "两者", both
        bucket.append(k)
        if u == "✅ 通过" and p != "✅ 通过":
            regress.append(k)
            tag += " ⚠回退"
        print(f"  {k:<32} {b:<8} {u:<8} {p:<8} {tag}")

    print("\n归因汇总：")
    print(f"  只由量具（判分器+题集）带来的变化：{len(ruler_only)} 题 {ruler_only}")
    print(f"  只由产品（Phase 4/4.5）带来的变化：{len(product_only)} 题 {product_only}")
    print(f"  两者叠加才变的：{len(both)} 题 {both}")
    if regress:
        print(f"  ⚠️ 纯尺子已绿、加产品后掉绿：{regress}")


if __name__ == "__main__":
    main()
