"""headtohead_ledger.py 的选股解析单测（确定性、无网络 / 无 DuckDB）。

覆盖 load_selections / _selection_codes：
- 从选股 markdown 抽取 6 位代码并统一成 sh|sz|bj 前缀（按交易所后缀判定，不靠首位猜，
  920510.BJ 才能正确落到 bj 而非 sz）；
- 默认只计「梯队」选股、跳过「观察组」；--include-observation 时全计入；
- 日期取自文件名里的 YYYY-MM-DD；目录会聚合多篇、按日期归并并去重保序。

放 intelligence/tests/，import 走 scripts/ 的 headtohead_ledger（模块导入不触网）。
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))

import headtohead_ledger as h2h  # noqa: E402


SAMPLE = """# 2026-06-05 双红题材优选记录

## 四、最终优选池

### 第一梯队

| 板块 | 股票 | 代码 | 入选理由 |
|---|---|---|---|
| 机械设备 | 绿的谐波 | 688017.SH | 开根加权第1 |
| 通信 | 中兴通讯 | 000063.SZ | 60日新高 |

### 第二梯队

| 板块 | 股票 | 代码 | 入选理由 |
|---|---|---|---|
| 机械设备 | 丰光精密 | 920510.BJ | 北交所弹性 |
| 机械设备 | 绿的谐波 | 688017.SH | 重复应去重 |

### 观察组

| 板块 | 股票 | 代码 | 观察原因 |
|---|---|---|---|
| 电子 | 信维通信 | 300136.SZ | 缺新高确认 |
"""


class TestSelectionCodes(unittest.TestCase):
    def test_default_excludes_observation_and_normalizes_suffix(self):
        codes = h2h._selection_codes(SAMPLE, include_observation=False)
        # 688017.SH -> sh688017；000063.SZ -> sz000063；920510.BJ -> bj920510（靠后缀，不靠首位）
        self.assertEqual(codes, ["sh688017", "sz000063", "bj920510"])
        self.assertNotIn("sz300136", codes)  # 观察组默认排除

    def test_include_observation_adds_watchlist(self):
        codes = h2h._selection_codes(SAMPLE, include_observation=True)
        self.assertEqual(codes, ["sh688017", "sz000063", "bj920510", "sz300136"])

    def test_dedup_preserves_order(self):
        codes = h2h._selection_codes(SAMPLE, include_observation=False)
        self.assertEqual(len(codes), len(set(codes)))


class TestLoadSelections(unittest.TestCase):
    def test_file_keyed_by_filename_date(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "2026-06-05-double-red-selection.md"
            p.write_text(SAMPLE, encoding="utf-8")
            out = h2h.load_selections(p)
            self.assertEqual(set(out), {"2026-06-05"})
            self.assertEqual(out["2026-06-05"], ["sh688017", "sz000063", "bj920510"])

    def test_directory_aggregates_dates_and_skips_undated(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "2026-06-05-a.md").write_text(SAMPLE, encoding="utf-8")
            (Path(d) / "2026-06-06-b.md").write_text(
                "### 第一梯队\n| x | y | 600519.SH | z |\n", encoding="utf-8")
            (Path(d) / "notes.md").write_text("无日期，整篇跳过 600000.SH\n", encoding="utf-8")
            out = h2h.load_selections(Path(d))
            self.assertEqual(set(out), {"2026-06-05", "2026-06-06"})
            self.assertEqual(out["2026-06-06"], ["sh600519"])


if __name__ == "__main__":
    unittest.main()
