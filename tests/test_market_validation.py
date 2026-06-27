import json
import tempfile
import unittest
from pathlib import Path

from intelligence.services.market_validation import build_market_validation_snapshot, load_market_validation_context


def candidate(
    theme: str,
    date: str,
    priority: float,
    triggers: list[str],
    limit_up: int = 0,
    high_count: int = 0,
    strong_stocks: list[dict] | None = None,
    pct_chg: float | None = None,
    diff_ratio: float | None = None,
    amount: float | None = None,
    capacity_top3: bool = False,
) -> dict:
    return {
        "market_theme": theme,
        "canonical_concept": theme,
        "trade_date": date,
        "priority_score": priority,
        "trigger_types": triggers,
        "market_evidence": {
            "sector_metrics": {
                "pct_chg": pct_chg,
                "diff_ratio": diff_ratio,
                "amount": amount,
                "in_capacity_top3": capacity_top3,
            },
            "limit_heat": {"limit_up_count": limit_up},
            "new_high_direction": {"high_count": high_count, "in_capacity_top3": capacity_top3},
            "strong_stocks": strong_stocks or [],
        },
    }


class MarketValidationTest(unittest.TestCase):
    def test_strong_market_validation_from_multi_signal_expansion(self):
        current = candidate(
            "光刻胶",
            "2026-06-11",
            184.57,
            ["double_red", "capacity_industry", "limit_heat", "new_high_direction", "new_high_cluster"],
            limit_up=5,
            high_count=14,
            pct_chg=2.21,
            diff_ratio=31.59,
            amount=954.38,
            capacity_top3=True,
            strong_stocks=[
                {"stock_name": "华特气体", "pct_chg": 20.0, "amount": 36.4, "high_status_label": "历史新高"},
                {"stock_name": "兴福电子", "pct_chg": 20.0, "amount": 19.59, "high_status_label": "历史新高"},
                {"stock_name": "雅克科技", "pct_chg": 10.0, "amount": 75.05, "high_status_label": "历史新高"},
            ],
        )
        history = [candidate("光刻胶", "2026-06-10", 150, ["double_red"], limit_up=1, high_count=4)]

        snapshot = build_market_validation_snapshot(current, history)

        self.assertEqual(snapshot["盘面验证强度"], "强验证")
        self.assertGreater(snapshot["边际变化"]["priority变化"], 0)
        self.assertGreater(snapshot["边际变化"]["涨停变化"], 0)
        self.assertIn("多信号共振", snapshot["验证结论"])
        self.assertIn("华特气体", snapshot["强势股"][0])

    def test_medium_market_validation_from_single_cluster(self):
        current = candidate(
            "液冷服务器",
            "2026-06-11",
            88,
            ["double_red", "limit_heat"],
            limit_up=2,
            high_count=1,
            strong_stocks=[{"stock_name": "强瑞技术", "pct_chg": 12.3}],
        )

        snapshot = build_market_validation_snapshot(current, [])

        self.assertEqual(snapshot["盘面验证强度"], "中等验证")
        self.assertIn("有盘面信号", snapshot["验证结论"])

    def test_weak_market_validation_from_low_diffusion(self):
        current = candidate(
            "冷门题材",
            "2026-06-11",
            42,
            ["double_red"],
            limit_up=0,
            high_count=0,
            strong_stocks=[],
        )

        snapshot = build_market_validation_snapshot(current, [])

        self.assertEqual(snapshot["盘面验证强度"], "弱验证")
        self.assertIn("扩散不足", snapshot["验证结论"])

    def test_first_seen_candidate_does_not_report_fake_delta_from_zero(self):
        current = candidate(
            "小金属",
            "2026-06-11",
            163.23,
            ["double_red", "limit_heat", "new_high_direction"],
            limit_up=7,
            high_count=10,
            strong_stocks=[{"stock_name": "云南锗业", "pct_chg": 10.0}],
        )

        snapshot = build_market_validation_snapshot(current, [])

        self.assertEqual(snapshot["边际变化"]["priority变化"], 0.0)
        self.assertIn("当前首次进入观察窗口", snapshot["验证结论"])

    def test_load_market_validation_context_reads_current_and_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            exports = Path(tmp)
            for day, priority in [("2026-06-10", 70), ("2026-06-11", 88)]:
                (exports / f"{day}-theme-candidates.json").write_text(
                    json.dumps(
                        {
                            "trade_date": day,
                            "candidates": [
                                candidate("液冷服务器", day, priority, ["double_red"], strong_stocks=[{"stock_name": "强瑞技术"}])
                            ],
                        },
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )

            current, history = load_market_validation_context(
                exports,
                ["2026-06-10", "2026-06-11"],
                "2026-06-11",
                top_per_date=5,
            )

            self.assertIn("液冷服务器", current)
            self.assertEqual(current["液冷服务器"]["priority_score"], 88)
            self.assertEqual(len(history["液冷服务器"]), 1)


if __name__ == "__main__":
    unittest.main()
