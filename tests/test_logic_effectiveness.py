from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from intelligence.services import logic_effectiveness as le


def hist(date: str, priority: float, stocks: int, *, triggers=None, evidence="-"):
    return {
        "date": date,
        "priority_score": priority,
        "trigger_types": triggers or [],
        "strong_stocks": [f"S{i}" for i in range(stocks)],
        "evidence_status": evidence,
    }


class EffectivenessScorecardTest(unittest.TestCase):
    def test_insufficient_samples_is_flagged_not_fabricated(self):
        card = le.build_effectiveness_scorecard("光刻胶", [hist("2026-06-01", 100, 3), hist("2026-06-02", 110, 4)])
        self.assertEqual(card["状态"], le.STATUS_INSUFFICIENT)
        self.assertNotIn("胜率", card)
        self.assertEqual(card["CAR"]["状态"], le.CAR_STATUS_NO_PANEL)

    def test_full_scorecard_metrics(self):
        rows = [
            hist("2026-06-01", 100, 2, evidence="旧逻辑待验证"),
            hist("2026-06-02", 140, 4),
            hist("2026-06-03", 200, 6),  # peak
            hist("2026-06-04", 150, 5),
            hist("2026-06-05", 90, 3),
        ]
        card = le.build_effectiveness_scorecard("先进封装", rows)
        self.assertEqual(card["状态"], le.STATUS_OK)
        self.assertEqual(card["样本天数"], 5)
        # 升 升 降 降 -> 2/4 次日不低于当日
        self.assertAlmostEqual(card["胜率"], 0.5)
        # 峰值 200，半值 100，峰后第 2 个交易日 (90) 跌破
        self.assertEqual(card["半衰期"]["交易日"], 2)
        # 峰 200 -> 谷 90 回撤 0.55
        self.assertAlmostEqual(card["最大回撤"]["比例"], 0.55)
        # 强势股 2->3 净增、区间 [2,3]
        self.assertEqual(card["强势股扩散率"]["区间强势股"], [2, 3])
        self.assertEqual(card["相对强度变化"]["方向"], "走弱")

    def test_half_life_not_reached_returns_none(self):
        rows = [hist(f"2026-06-0{i}", 100 + i, 3) for i in range(1, 6)]
        card = le.build_effectiveness_scorecard("液冷", rows)
        self.assertIsNone(card["半衰期"]["交易日"])

    def test_narrative_fact_deviation_flags_overheating(self):
        rows = [
            hist("2026-06-01", 50, 2, evidence="-"),
            hist("2026-06-02", 100, 3, evidence="-"),
            hist("2026-06-03", 100, 3, evidence="-"),
        ]
        card = le.build_effectiveness_scorecard("商业航天", rows)
        dev = card["叙事事实偏离"]
        self.assertGreaterEqual(dev["偏离值"], 0.4)
        self.assertIn("透支", dev["判断"])


class CarTest(unittest.TestCase):
    def _panel(self):
        # 锚点 2026-06-02 后 5 个交易日；A 题材成分股 000001 跑赢基准
        dates = ["2026-06-01", "2026-06-02", "2026-06-03", "2026-06-04", "2026-06-05", "2026-06-06", "2026-06-07", "2026-06-08"]
        returns = {}
        benchmark = {}
        theme_stocks = {}
        for d in dates:
            returns[d] = {"000001": 3.0, "000002": 0.0}
            benchmark[d] = 1.0
            theme_stocks[d] = {"A题材": ["000001"]}
        return {"trade_dates": dates, "returns": returns, "benchmark": benchmark, "theme_stocks": theme_stocks}

    def test_compute_car_excess_over_benchmark(self):
        panel = self._panel()
        # 5 日，每日超额 2.0 -> CAR(0,5)=10.0
        self.assertAlmostEqual(le.compute_car(panel, "A题材", "2026-06-02", 5), 10.0)

    def test_compute_car_insufficient_forward_days(self):
        panel = self._panel()
        # 最后一天没有前向 5 日
        self.assertIsNone(le.compute_car(panel, "A题材", "2026-06-08", 5))

    def test_scorecard_with_panel_emits_car(self):
        panel = self._panel()
        rows = [hist(d, 100 + i * 10, 3, triggers=["double_red"]) for i, d in enumerate(panel["trade_dates"][:5])]
        card = le.build_effectiveness_scorecard("A题材", rows, return_panel=panel, forward_windows=(5,))
        self.assertEqual(card["CAR"]["状态"], le.CAR_STATUS_OK)
        self.assertIsNotNone(card["CAR"]["CAR(0,5)"])

    def test_scorecard_without_panel_degrades_car(self):
        rows = [hist(f"2026-06-0{i}", 100, 3) for i in range(1, 5)]
        card = le.build_effectiveness_scorecard("A题材", rows, return_panel=None)
        self.assertEqual(card["CAR"]["状态"], le.CAR_STATUS_NO_PANEL)


class LoaderTest(unittest.TestCase):
    def test_load_market_return_panel_reads_snapshots(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            doc = {
                "schema_version": "1",
                "trade_date": "2026-06-02",
                "strong_stocks": [
                    {"stock_ts_code": "000001", "pct_chg": 5.0, "concepts": ["光刻胶"]},
                    {"stock_ts_code": "000002", "pct_chg": -1.0, "concepts": ["光刻胶", "半导体"]},
                ],
            }
            (base / "2026-06-02.json").write_text(json.dumps(doc), encoding="utf-8")
            panel = le.load_market_return_panel(base, ["2026-06-02"])
            self.assertEqual(panel["trade_dates"], ["2026-06-02"])
            self.assertAlmostEqual(panel["benchmark"]["2026-06-02"], 2.0)
            self.assertEqual(panel["theme_stocks"]["2026-06-02"]["光刻胶"], ["000001", "000002"])

    def test_load_market_return_panel_missing_dir_returns_empty(self):
        panel = le.load_market_return_panel("/no/such/dir", ["2026-06-02"])
        self.assertEqual(panel["trade_dates"], [])


class DecisionEnrichmentTest(unittest.TestCase):
    def test_build_effectiveness_for_decision_attaches_scorecard(self):
        decision = {
            "old_logic_wakeup": [{"query": "光刻胶", "data_gaps": []}],
            "new_logic_candidate": [],
            "data_gap": [{"query": "占位", "data_gaps": ["placeholder_market_theme"]}],
        }
        history = {"光刻胶": [hist(f"2026-06-0{i}", 100 + i, 3) for i in range(1, 5)]}
        le.build_effectiveness_for_decision(decision, history)
        self.assertIn("logic_effectiveness", decision["old_logic_wakeup"][0])
        self.assertEqual(decision["old_logic_wakeup"][0]["logic_effectiveness"]["状态"], le.STATUS_OK)
        # placeholder 不挂成绩单
        self.assertNotIn("logic_effectiveness", decision["data_gap"][0])

    def test_summarize_effectiveness_counts(self):
        decision = {
            "old_logic_wakeup": [{"query": "光刻胶", "data_gaps": []}],
            "new_logic_candidate": [{"query": "新词", "data_gaps": []}],
            "data_gap": [],
        }
        history = {
            "光刻胶": [hist(f"2026-06-0{i}", 100 + i, 3) for i in range(1, 5)],
            "新词": [hist("2026-06-01", 100, 3)],
        }
        le.build_effectiveness_for_decision(decision, history)
        summary = le.summarize_effectiveness(decision)
        self.assertEqual(summary["已评估逻辑数"], 1)
        self.assertEqual(summary["样本不足逻辑数"], 1)


if __name__ == "__main__":
    unittest.main()
