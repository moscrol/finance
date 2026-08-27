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
- 订正传播（warning）：spec 自称订正过（含订正/撤回/已修正/勘误）时，
  同号 ``docs/handoffs/inflight/`` 的交接必须也带订正痕迹。治的形状见下。

## 第三向治的形状（2026-08-27 实测，写这条的人自己犯的）

停更工单 ``R-20260827-09`` 撤回了两条结论，spec 与台账都改了，在途交接
**一字未动**，仍逐字传播「本单是那句预言的兑现」与「改 episode_tools.py:212」
——而后者会打穿 PIT，且按仓规接手者**先读交接**。
同一结论存 spec/台账/交接三处，订正只覆盖两处：**订正的传播半径 = 该结论被
复制的份数**，不是「改了源头就行」。

**这条不做语义比对**（措辞矛盾但双方都没写标记 → 抓不到）。语义级检查放
对抗审查流程，不进门：判定不了还硬拦，就是造一个稳定噪声源。

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


# 订正标记词表：spec 里出现任一即视为「本单自称订正过某条结论」。
# 刻意小而显式——判据只在 spec **自称**订正时才触发，普通迭代（补章节、
# 改错字）不比对，否则会变成稳定误报，而每周固定误报的告警一周内就会被
# 训练成忽略（比不做更糟）。
_CORRECTION_MARKERS = ("订正", "撤回", "已修正", "勘误")


@dataclass
class CrosswalkReport:
    missing: dict[str, list[str]] = field(default_factory=dict)
    duplicated: dict[str, int] = field(default_factory=dict)
    orphans: dict[str, str] = field(default_factory=dict)
    stale_handoffs: dict[str, list[str]] = field(default_factory=dict)


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


def _refs_in(root: Path, rel_dir: str, *, recurse: bool = True) -> dict[str, list[Path]]:
    """``rel_dir`` 下每个 R- 号 → [文件绝对路径, …]。"""

    refs: dict[str, list[Path]] = {}
    base = root / rel_dir
    if not base.is_dir():
        return refs
    paths = sorted(base.rglob("*.md") if recurse else base.glob("*.md"))
    for path in paths:
        text = path.read_text(encoding="utf-8", errors="replace")
        for rid in set(_ID_RE.findall(text)):
            refs.setdefault(rid, []).append(path)
    return refs


def _owning_specs(root: Path) -> dict[str, tuple[str, ...]]:
    """R- 号 → 台账行里点名的 spec 相对路径。

    归属靠台账行自述，而不是「谁提到过这个号」：一份工单常引用别的号当
    历史证据，那不代表它拥有那个号。
    """

    owners: dict[str, tuple[str, ...]] = {}
    all_rows, _ = _ledger_rows(root)
    pat = re.compile(r"docs/superpowers/specs/[^\s`）)，,]+\.md")
    for rid, line in all_rows:
        found = tuple(dict.fromkeys(pat.findall(line)))
        if found:
            owners[rid] = owners.get(rid, ()) + found
    return owners


def _has_correction_marker(path: Path) -> bool:
    text = path.read_text(encoding="utf-8", errors="replace")
    return any(marker in text for marker in _CORRECTION_MARKERS)


def _stale_inflight_handoffs(root: Path) -> dict[str, list[str]]:
    """spec 自称订正过，同号在途交接却无订正痕迹 → 可能仍在传播旧结论。

    为什么只查 ``docs/handoffs/inflight/``：已归档交接是**历史快照**，
    本就不该跟着 spec 走；在途交接则是接手者按仓规**第一个读**的文件，
    它和 spec 说的不是同一件事时，实施方会照交接施工。

    **这条判据不做语义比对**：它只回答「spec 声明订正过 / 同号交接有没有
    订正痕迹」。两份文档措辞矛盾但双方都没写标记时，它抓不到——那属于
    语义级检查，放对抗审查流程，不进门（判定不了硬拦就是造噪声源）。
    """

    inflight_refs = _refs_in(root, "docs/handoffs/inflight", recurse=False)
    owners = _owning_specs(root)
    stale: dict[str, list[str]] = {}
    for rid, handoffs in sorted(inflight_refs.items()):
        # **只看台账行点名的那份 spec**。仅仅提到该号的 spec 不算——
        # 实测误报：`R-20260826-01` 曾被报，只因另一份工单引用它当历史证据，
        # 而那份工单里的「订正」说的是另一个号。标记与号同在一个文件
        # ≠ 标记是关于那个号的（又一次「断言粒度比被保护物粗一档」）。
        specs = [root / rel for rel in owners.get(rid, ()) if (root / rel).is_file()]
        if not any(_has_correction_marker(s) for s in specs):
            continue  # 归属 spec 没自称订正（或台账行没点名 spec）→ 不比对
        unmarked = [
            str(h.relative_to(root)) for h in handoffs if not _has_correction_marker(h)
        ]
        if unmarked:
            stale[rid] = unmarked
    return stale


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

    report.stale_handoffs = _stale_inflight_handoffs(root)
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

    if report.stale_handoffs:
        print(f"\n⚠ 订正未传播（spec 自称订正、同号在途交接无订正痕迹）："
              f"{len(report.stale_handoffs)} 个（severity=warning）")
        for rid, files in list(report.stale_handoffs.items())[:10]:
            print(f"    {rid}  → {', '.join(files)}")
        if len(report.stale_handoffs) > 10:
            print(f"    …另 {len(report.stale_handoffs) - 10} 个")
        print("    （接手者按仓规先读交接；只改 spec 不改交接 = 旧结论仍在投递）")
    else:
        print("✓ 订正传播：无同号在途交接落后于 spec")

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
