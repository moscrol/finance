from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from intelligence.services.market_snapshot_contract import validate_market_snapshot_root


def write_snapshot(root: Path, date: str = "2026-06-11") -> None:
    doc = {
        "schema_version": "1.0",
        "trade_date": date,
        "generated_at": "2026-06-11T18:00:00+08:00",
        "market": {
            "stage": "主升",
            "total_amount": 12345.6,
            "amount_ratio": 12.3,
            "advancers": 3200,
            "decliners": 1800,
            "limit_up": 68,
            "limit_down": 5,
            "capacity_top3": [{"name": "电子", "ratio": 29.0}],
        },
        "themes": [
            {
                "concept": "光刻胶",
                "priority_score": 184.57,
                "trigger_types": ["double_red", "limit_heat"],
                "limit_up_count": 5,
                "new_high_count": 14,
                "strong_stock_count": 8,
            }
        ],
        "strong_stocks": [
            {
                "stock_name": "华特气体",
                "stock_ts_code": "688268.SH",
                "concepts": ["光刻胶"],
                "pct_chg": 20.0,
                "amount": 36.4,
            }
        ],
    }
    (root / f"{date}.json").write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    (root / "latest.json").write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    (root / "meta.json").write_text(
        json.dumps({"schema_version": "1.0", "latest_trade_date": date, "updated_at": "2026-06-11T18:01:00+08:00"}, ensure_ascii=False),
        encoding="utf-8",
    )


class MarketSnapshotContractTest(unittest.TestCase):
    def test_valid_snapshot_root_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_snapshot(root)

            result = validate_market_snapshot_root(root, "2026-06-11")

            self.assertEqual(result["status"], "PASS")
            self.assertEqual(result["date"], "2026-06-11")
            self.assertEqual(result["summary"]["theme_count"], 1)
            self.assertEqual(result["summary"]["strong_stock_count"], 1)

    def test_missing_daily_file_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "meta.json").write_text(json.dumps({"latest_trade_date": "2026-06-11"}), encoding="utf-8")

            result = validate_market_snapshot_root(root, "2026-06-11")

            self.assertEqual(result["status"], "FAIL")
            self.assertIn("missing daily snapshot", " ".join(result["errors"]))

    def test_missing_required_market_fields_warns(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            doc = {
                "schema_version": "1.0",
                "trade_date": "2026-06-11",
                "market": {"stage": "主升"},
                "themes": [],
                "strong_stocks": [],
            }
            (root / "2026-06-11.json").write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")

            result = validate_market_snapshot_root(root, "2026-06-11")

            self.assertEqual(result["status"], "WARN")
            self.assertIn("market.total_amount", " ".join(result["warnings"]))

    def test_latest_date_mismatch_warns(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_snapshot(root, "2026-06-11")
            (root / "meta.json").write_text(json.dumps({"latest_trade_date": "2026-06-10"}), encoding="utf-8")

            result = validate_market_snapshot_root(root, "2026-06-11")

            self.assertEqual(result["status"], "WARN")
            self.assertIn("meta latest_trade_date", " ".join(result["warnings"]))


if __name__ == "__main__":
    unittest.main()
