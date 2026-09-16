"""双红口径单一真本源（R-20260830-03）：阈值只许在一处，其余按名引用。

背景：改之前树里有三份互不引用的实现，数值恰好一致——所以谁都没发现，
而且每一份自己都自洽：

  ① ``market_feature_store.signals.DOUBLE_RED_SQL``（包 / D 块 / 时序侧写死字面量）
  ② ``theme_lifecycle_timeline.DOUBLE_RED_*``（Engine A 的 ``asof_prefetch`` 用这份）
  ③ ``market_regime_analogs._AUX_QUERIES``（D10 里再写死一次）

分家线正好压在 A 侧与 B 侧之间——这就是勒死单 P1 说的「两份 SQL」在本仓的实物。
D10 尤其要命：它同时供 A 预取和 B compose，改阈值时两边一起错、读数还自洽。

**断言形状为什么是源码扫描而不是数值比对**：
「三处数值相等」这种断言在三份各自硬编码时**也全绿**——那正是改之前的状态，
它证明不了单一真本源。要对「某处又偷偷写死回去」敏感，只能去源码里看还有没有
字面量。所以本文件的主门禁是棘轮式源码扫描：存量免检、新增拦截。

第二个也是运行时能测的：``is_double_red`` 的行字典版必须**委托**给标量版，
不得自带一套比较逻辑（两份比较实现会让同一天的块与时间线互相矛盾）。
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path
from unittest import mock

from market_feature_store import signals

_REPO_ROOT = Path(__file__).resolve().parents[2]

# 双红三件套的字面量谓词（允许换行/大小写/空白差异）。第三项放宽到
# `amount` 出现即可，好把 daily_review 那条「反向近似」也算进来
# （`amount <= 500 OR amount IS NULL`，是同一口径的补集，同样会漂）。
_HARDCODED_RE = re.compile(
    r"pct_chg\s*>\s*0\s+AND\s+diff_ratio\s*>\s*10\b",
    re.IGNORECASE,
)

# 存量基线：改本单时已存在的硬编码处，本单不动它们（不同消费域，见下方
# 说明）。新增一处即红。数字是**扫出来的**，不是拍的。
_BASELINE: dict[str, int] = {
    # 复盘日报渲染器。四处：三条正向 + 一条反向近似（amount<=500）。
    # 归 T6 另开单——它属报表域，改动面与 A/B 缝无关，混在本单会把
    # 回归面从 4 个模块扩到整条日报链路。
    "market_feature_store/reports/daily_review.py": 4,
}

# 扫描范围：生产代码。research/ 与 archive 是一次性脚本，不进门禁。
_SCAN_DIRS = ("intelligence", "market_feature_store")
_SKIP_PARTS = ("tests", "archive", "research", ".venv", "__pycache__")


def _scan_hardcoded_sites() -> dict[str, int]:
    found: dict[str, int] = {}
    for top in _SCAN_DIRS:
        for path in (_REPO_ROOT / top).rglob("*.py"):
            rel = path.relative_to(_REPO_ROOT).as_posix()
            if any(part in _SKIP_PARTS for part in path.parts):
                continue
            if rel == "market_feature_store/signals.py":
                continue  # 唯一允许写数字的地方
            hits = len(_HARDCODED_RE.findall(path.read_text(encoding="utf-8")))
            if hits:
                found[rel] = hits
    return found


class HardcodedCaliberRatchetTests(unittest.TestCase):
    def test_no_new_hardcoded_double_red_predicate(self) -> None:
        """棘轮：除基线外，生产代码不得再出现写死的双红谓词。

        本条是唯一对「把 signals 引用换回字面量」敏感的断言——数值比对类
        断言在那种变异下全绿。
        """
        found = _scan_hardcoded_sites()
        new = {k: v for k, v in found.items() if v > _BASELINE.get(k, 0)}
        self.assertEqual(
            new,
            {},
            f"新增写死的双红谓词：{new}。阈值只许在 market_feature_store/signals.py，"
            "其余按名引用 DOUBLE_RED_SQL / DOUBLE_RED_PCT/DIFF/AMOUNT。",
        )

    def test_baseline_is_still_accurate(self) -> None:
        """基线只许缩不许涨；清账后要顺手把它改小，否则门禁会松一格。"""
        found = _scan_hardcoded_sites()
        for rel, expected in _BASELINE.items():
            actual = found.get(rel, 0)
            self.assertLessEqual(
                actual,
                expected,
                f"{rel} 的硬编码处数从 {expected} 涨到 {actual}",
            )

    def test_engine_a_side_no_longer_defines_its_own_numbers(self) -> None:
        """A 侧那份同值常量必须已改成转出——这是本单要治的分家点。"""
        src = (
            _REPO_ROOT / "intelligence/services/theme_lifecycle_timeline.py"
        ).read_text(encoding="utf-8")
        for name in ("DOUBLE_RED_PCT", "DOUBLE_RED_DIFF", "DOUBLE_RED_AMOUNT"):
            # 必须 MULTILINE：不带它时 `^` 只匹配整份源码的开头，这条断言
            # 会永远为真——初版就是这么写的，变异 B（把常量改回自带数值）
            # 当场逃掉。行锚点类断言尤其容易变成假门禁。
            self.assertIsNone(
                re.search(rf"^{name}\s*=\s*[\d.]+", src, re.MULTILINE),
                f"{name} 又在 theme_lifecycle_timeline 里被直接赋数值了",
            )


class DerivationTests(unittest.TestCase):
    def test_predicate_string_unchanged_from_hand_written_version(self) -> None:
        """生成式改写不得改变谓词串——B 侧一切既有 SQL 逐字节不变。"""
        self.assertEqual(
            signals.DOUBLE_RED_SQL,
            "pct_chg > 0 AND diff_ratio > 10 AND amount > 500",
        )
        self.assertEqual(
            signals.DOUBLE_RED_DESCRIPTION,
            "题材涨幅为正、边际量大于 10 且成交额大于 500 亿。",
        )

    def test_every_surface_matches_the_generated_predicate(self) -> None:
        """三个消费面的口径都必须等于按常量生成的那一份。"""
        from intelligence.services import market_regime_analogs, theme_lifecycle_timeline

        expected = (
            f"pct_chg > {signals.DOUBLE_RED_PCT:g} "
            f"AND diff_ratio > {signals.DOUBLE_RED_DIFF:g} "
            f"AND amount > {signals.DOUBLE_RED_AMOUNT:g}"
        )
        self.assertEqual(signals.DOUBLE_RED_SQL, expected)
        self.assertIn(expected, market_regime_analogs._AUX_QUERIES["double_red_theme_count"])
        self.assertEqual(
            (
                theme_lifecycle_timeline.DOUBLE_RED_PCT,
                theme_lifecycle_timeline.DOUBLE_RED_DIFF,
                theme_lifecycle_timeline.DOUBLE_RED_AMOUNT,
            ),
            (signals.DOUBLE_RED_PCT, signals.DOUBLE_RED_DIFF, signals.DOUBLE_RED_AMOUNT),
        )

    def test_row_predicate_delegates_to_scalar_predicate(self) -> None:
        """行字典版必须委托给标量版，不得自带一套比较逻辑。

        运行时可测：把 signals 的阈值调到 42，行版若自己比较就仍按 10 判真。
        """
        from intelligence.services import theme_lifecycle_timeline as tl

        row = {"pct_chg": 1.0, "diff_ratio": 20.0, "amount": 900.0}
        self.assertTrue(tl.is_double_red(row))  # 20 > 10，旧阈值下为真
        with mock.patch.object(signals, "DOUBLE_RED_DIFF", 42.0):
            self.assertFalse(tl.is_double_red(row))  # 20 < 42，必须跟着变


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
