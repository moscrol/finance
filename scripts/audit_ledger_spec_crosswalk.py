#!/usr/bin/env python3
"""spec↔台账双向对账：spec 引用的 R- 号必须在 prediction-ledger 有且仅有一行。

## 治的形状（2026-08-27 工单 §P1-b，全部实测）

- `R-20260824-25/-26/-27`：实施 PR #359 已合并、spec §8 写明判据，台账**零行**。
  它不是 pending，它不存在——「pending 太久」类扫描永远捞不出来。
- `R-20260821-03`：一号两行，一 `confirmed` 一 `pending`，按号取状态得到不确定答案。
- 「解说层真、台账层漂」：spec 正文说「台账 -28…-30 保持 pending」，其中两个号无行。

## 三个方向

- 正向（error）：``docs/superpowers/specs/**`` 里每个 ``R-YYYYMMDD-NN`` 引用，
  台账必须有且仅有一行。缺行红，报错点名哪份 spec 第几行引的。
- 重号（error）：台账同号多行直接红，不给 warning 档——重号让「按号取状态」这个
  最常见的读法失去确定性。
- 反向（默认 warning）：台账每行应回指至少一份 spec / handoff / verification
  （行内含 ``docs/`` 路径即认）。存量清干净后升 error：调用处显式传
  ``--reverse-severity error``，**升档那天把生效 revision 写进调用处**，
  不要让它长期停在 warning（降 severity = 把决定权交给下游）。

退出码：0 无 error 级发现；2 有缺号 / 重号（或反向升 error 后有孤儿行）。
exit 0 只对当前工作树内容成立，输出里自述树与 revision。
"""

from __future__ import annotations

import argparse
import re
import subprocess
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
_ID_RE = re.compile(r"R-\d{8}-\d{2}")
# 回指判据：行内出现任一这些路径前缀即认为可追溯。
_BACKREF_PREFIXES = (
    "docs/superpowers/specs/",
    "docs/handoffs/",
    "docs/verification/",
    "docs/workflows/",
)


@dataclass
class CrosswalkReport:
    missing: dict[str, list[str]] = field(default_factory=dict)
    duplicated: dict[str, int] = field(default_factory=dict)
    orphans: dict[str, str] = field(default_factory=dict)


def _ledger_rows(root: Path) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """返回 (全文表行, Open 主表行)，元素为 (台账号, 整行)。

    台账结构 = ``### Open（pending）`` 主表 + 一堆历史回填段（同一号在多个
    回填段出现是**过程记录**，不是重号）。重号与孤儿检查只对主表段生效，
    正向缺号检查用全文（号只要在任何段有行就算存在）。
    带超码后缀的留档行（如 ``R-…-03a``）不匹配号型，天然豁免。
    """
    ledger = root / "docs" / "prediction-ledger.md"
    all_rows: list[tuple[str, str]] = []
    open_rows: list[tuple[str, str]] = []
    if not ledger.is_file():
        return all_rows, open_rows
    in_open = False
    for line in ledger.read_text(encoding="utf-8").splitlines():
        if line.startswith("### "):
            in_open = line.startswith("### Open")
        m = re.match(r"^\|\s*`(R-\d{8}-\d{2})`\s*\|", line)
        if m:
            all_rows.append((m.group(1), line))
            if in_open:
                open_rows.append((m.group(1), line))
    return all_rows, open_rows


def _spec_refs(root: Path) -> dict[str, list[str]]:
    """spec 里出现的每个 R- 号 → [``文件:行号``, …]。"""
    refs: dict[str, list[str]] = {}
    specs_dir = root / "docs" / "superpowers" / "specs"
    if not specs_dir.is_dir():
        return refs
    for path in sorted(specs_dir.rglob("*.md")):
        rel = path.relative_to(root)
        for lineno, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), 1
        ):
            for rid in _ID_RE.findall(line):
                refs.setdefault(rid, []).append(f"{rel}:{lineno}")
    return refs


def crosswalk(root: Path) -> CrosswalkReport:
    report = CrosswalkReport()
    all_rows, open_rows = _ledger_rows(root)
    row_ids = {rid for rid, _ in all_rows}

    counts = Counter(rid for rid, _ in open_rows)
    for rid, n in sorted(counts.items()):
        if n > 1:
            report.duplicated[rid] = n

    for rid, wheres in sorted(_spec_refs(root).items()):
        if rid not in row_ids:
            report.missing[rid] = wheres

    for rid, line in open_rows:
        # 重号行不重复报孤儿。
        if rid in report.duplicated:
            continue
        if not any(prefix in line for prefix in _BACKREF_PREFIXES):
            report.orphans[rid] = line[:80]
    return report


def _revision(root: Path) -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short=12", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return out.stdout.strip() or "(unknown)"
    except (OSError, subprocess.SubprocessError):
        return "(unknown)"


def run(root: Path, *, reverse_severity: str = "warning") -> int:
    report = crosswalk(root)
    print("=" * 72)
    print("spec↔台账双向对账 — spec 引的号必须在台账有且仅有一行")
    print(f"  树        {root}")
    print(f"  revision  {_revision(root)}")
    print("=" * 72)

    hard = 0
    if report.missing:
        hard += len(report.missing)
        print(f"\n✗ 缺号（spec 引了、台账无行）：{len(report.missing)} 个")
        for rid, wheres in report.missing.items():
            print(f"    {rid}  ← {wheres[0]}" + (
                f"（另 {len(wheres) - 1} 处引用）" if len(wheres) > 1 else ""
            ))
    else:
        print("\n✓ 正向：spec 引用的号台账全有行")

    if report.duplicated:
        hard += len(report.duplicated)
        print(f"\n✗ 重号（同号多行，按号取状态不确定）：{len(report.duplicated)} 个")
        for rid, n in report.duplicated.items():
            print(f"    {rid} × {n} 行")
    else:
        print("✓ 重号：无")

    if report.orphans:
        mark = "✗" if reverse_severity == "error" else "⚠"
        print(f"\n{mark} 反向（台账行回指不了 spec/handoff/verification）："
              f"{len(report.orphans)} 行（severity={reverse_severity}）")
        for rid, head in list(report.orphans.items())[:10]:
            print(f"    {rid}  {head}")
        if len(report.orphans) > 10:
            print(f"    …另 {len(report.orphans) - 10} 行")
        if reverse_severity == "error":
            hard += len(report.orphans)
    else:
        print("✓ 反向：台账行全部可回指")

    if hard:
        print(f"\n🔴 {hard} 个 error 级发现（exit 2）")
        return 2
    print("\n✅ 通过（exit 0 只对上面那个 revision 的工作树内容成立）")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__ and __doc__.splitlines()[0])
    ap.add_argument("--root", default=str(REPO), help="仓库根（默认本仓）")
    ap.add_argument(
        "--reverse-severity",
        choices=("warning", "error"),
        default="warning",
        help="反向检查档位；存量清干净后升 error，升档时在调用处注明生效 revision",
    )
    args = ap.parse_args()
    return run(Path(args.root), reverse_severity=args.reverse_severity)


if __name__ == "__main__":
    raise SystemExit(main())
