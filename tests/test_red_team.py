"""red_team（制度化反方）与 retrieval_audit 页级统计的单元测试。"""

from __future__ import annotations

import json
from pathlib import Path

from intelligence.services import red_team, retrieval_audit
from intelligence.services.checkpoints import Calibration, CategoryStat


def test_red_team_brief_surfaces_past_mistakes_and_weak_categories() -> None:
    corrections = [
        {"correction": "液冷的驱动是订单不是涨价", "original": "液冷涨价驱动", "themes": ["液冷"]},
        {"correction": "无关纠偏", "original": "别的", "themes": ["机器人"]},
    ]
    cal = Calibration(
        by_category=[
            CategoryStat(category="预期差", n=10, hits=2, miss=8, score_sum=2.0),
            CategoryStat(category="趋势延续", n=10, hits=8, miss=2, score_sum=8.0),
        ],
        scored=20,
    )
    brief = red_team.build_red_team_brief(
        "液冷是真瓶颈，T+3 板块应双红",
        themes=["液冷"],
        category="预期差",
        corrections=corrections,
        calibration=cal,
    )
    assert any("液冷" in str(m.get("correction")) for m in brief.past_mistakes)
    assert not any("机器人" in str(m.get("themes")) for m in brief.past_mistakes)
    assert [wc["category"] for wc in brief.weak_categories] == ["预期差"]
    assert brief.category_warning  # 本判断类别本身低胜率 → 显式警告
    assert brief.checkable  # 含 T+3 数值表述 → 可回检
    md = brief.to_markdown()
    assert "红队反方" in md and "预期差" in md


def test_red_team_brief_without_history_still_outputs_rebuttals() -> None:
    brief = red_team.build_red_team_brief("某题材要涨", corrections=[], calibration=None)
    assert brief.rebuttals  # 通用反方骨架永远存在
    assert not brief.past_mistakes
    assert not brief.checkable  # 无数值阈值 → 不可回检并提示补证伪条件
    assert brief.checkability_note


def test_summarize_pages_counts_hits_and_last_hit(tmp_path: Path) -> None:
    ledger = tmp_path / "audit.jsonl"
    rows = [
        {"ts": "2026-07-04T01:00:00Z", "wiki_pages": ["wiki/entities/A.md", "wiki/concepts/B.md"]},
        {"ts": "2026-07-05T01:00:00Z", "wiki_pages": ["wiki/entities/A.md"]},
        {"ts": "2026-07-05T02:00:00Z", "wiki_pages": []},
    ]
    ledger.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    summary = retrieval_audit.summarize_pages(ledger)
    assert summary["total_records"] == 3
    assert summary["records_with_wiki_pages"] == 2
    assert summary["distinct_pages"] == 2
    top = summary["pages"][0]
    assert top["page"] == "wiki/entities/A.md"
    assert top["hits"] == 2
    assert top["last_hit"].startswith("2026-07-05")
