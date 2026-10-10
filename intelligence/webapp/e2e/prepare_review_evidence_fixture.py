"""Synthetic archives only; writes exclusively to webapp/test-results/review-evidence."""
from __future__ import annotations

import json
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[1] / "test-results/review-evidence/workspace/market_feature_store/exports"
    root.mkdir(parents=True, exist_ok=True)
    for day in ("2026-09-21", "2026-09-22", "2026-09-24"):
        sections = []
        for index, mode in enumerate(("double_red_matrix", "stock_highs", "limit_up")):
            sections.append({"id": mode, "index": index, "title": mode, "blocks": [
                {"kind": "heading", "text": "电子"},
                {"kind": "table", "columns": ["子板块", "09-18", day[5:]],
                 "rows": [[f"合成子板块{i:02d}", "旧列不得补档", "🔥1.0%/15.0/800" if mode == "double_red_matrix" else i] for i in range(14)]},
            ]})
        sections.append({"id": "industry_engines", "index": 4, "title": "个股发动机", "blocks": [
            {"kind": "heading", "text": "电子"},
            {"kind": "table", "columns": ["排序", "股票", "代码", "原始得分"],
             "rows": [[i, f"合成股票{i:02d}", f"{i:06d}.SZ", f"{i}.50"] for i in range(1, 82)]},
        ]})
        data = {"schema": "daily-review/v1", "trade_date": day, "generated_at": "2026-09-29 20:00:00",
                "warnings": ["纯合成浏览器测试，不是真行情"],
                "facts": {"focus_sw_l1": ["电子"], "top_amount_sw_l1": ["机械设备"] if day.endswith("22") else ["电子"],
                          "total_amount": 12000, "advancers_ma5": 1500.2, "strength_avg_pct": -1.25,
                          "top3_industry_ratio": 42.7, "double_red_count": 0, "stock_high_120d_count": 56},
                "sections": sections}
        (root / f"{day}-daily-review.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    # Missing and malformed cases are distinct and deterministic across reruns.
    (root / "2026-09-23-daily-review.json").unlink(missing_ok=True)
    (root / "2026-09-18-daily-review.json").write_text("invalid synthetic archive", encoding="utf-8")


if __name__ == "__main__":
    main()
