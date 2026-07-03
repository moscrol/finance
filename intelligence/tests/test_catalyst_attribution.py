from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from intelligence.services import catalyst_attribution


def _write_kb(tmp: str, *, events: list[dict] | None = None, briefings: dict[str, str] | None = None) -> Path:
    kb_wiki = Path(tmp) / "wiki"
    if events is not None:
        store = kb_wiki / "raw" / "theme-radar" / "opinion-store"
        store.mkdir(parents=True, exist_ok=True)
        (store / "opinion-events.jsonl").write_text(
            "\n".join(json.dumps(event, ensure_ascii=False) for event in events),
            encoding="utf-8",
        )
    for day, text in (briefings or {}).items():
        briefings_dir = kb_wiki / "briefings"
        briefings_dir.mkdir(parents=True, exist_ok=True)
        (briefings_dir / f"{day}.md").write_text(text, encoding="utf-8")
    return kb_wiki


class CatalystAttributionTests(unittest.TestCase):
    def test_opinion_event_hit_by_theme_term(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            kb_wiki = _write_kb(
                tmp,
                events=[
                    {
                        "report_date": "2026-07-02",
                        "source": "某卖方晚报",
                        "term": "人形机器人",
                        "concept": "人形机器人",
                        "target": "绿的谐波",
                        "stance": "看多",
                        "catalysts": ["宇树发布新一代人形机器人，产业链关注度升温"],
                    }
                ],
            )
            index = catalyst_attribution.build_catalyst_index(kb_wiki, "2026-07-03")
            result = catalyst_attribution.attribute_theme(index, "人形机器人", ["绿的谐波"])
            self.assertEqual(result["status"], catalyst_attribution.STATUS_NARRATIVE_HIT)
            self.assertEqual(result["events"][0]["source_type"], "sellside_opinion")
            self.assertIn("宇树", result["events"][0]["excerpt"])
            self.assertIn("题材词", result["events"][0]["matched_by"])

    def test_opinion_event_hit_by_strong_stock(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            kb_wiki = _write_kb(
                tmp,
                events=[
                    {
                        "report_date": "2026-07-01",
                        "source": "国投硬科技",
                        "term": "CPO",
                        "concept": "1.6T CPO",
                        "target": "天孚通信",
                        "stance": "看多",
                        "hard_evidence": ["1.6T 订单开始放量"],
                    }
                ],
            )
            index = catalyst_attribution.build_catalyst_index(kb_wiki, "2026-07-03")
            result = catalyst_attribution.attribute_theme(index, "光模块", ["天孚通信"])
            self.assertEqual(result["status"], catalyst_attribution.STATUS_NARRATIVE_HIT)
            self.assertIn("强势股", result["events"][0]["matched_by"])

    def test_briefing_hit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            kb_wiki = _write_kb(
                tmp,
                events=[],
                briefings={"2026-07-02": "# 晨汇\n\n- 减速器：多家券商夜报覆盖谐波减速器涨价预期。\n"},
            )
            index = catalyst_attribution.build_catalyst_index(kb_wiki, "2026-07-03")
            result = catalyst_attribution.attribute_theme(index, "减速器", [])
            self.assertEqual(result["status"], catalyst_attribution.STATUS_NARRATIVE_HIT)
            self.assertEqual(result["events"][0]["source_type"], "morning_briefing")
            self.assertEqual(result["events"][0]["date"], "2026-07-02")

    def test_market_only_when_no_hit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            kb_wiki = _write_kb(
                tmp,
                events=[{"report_date": "2026-07-02", "term": "CPO", "concept": "CPO", "target": "天孚通信"}],
                briefings={"2026-07-02": "# 晨汇\n\n- 今日无相关内容。\n"},
            )
            index = catalyst_attribution.build_catalyst_index(kb_wiki, "2026-07-03")
            result = catalyst_attribution.attribute_theme(index, "军工装备", ["中国船舶"])
            self.assertEqual(result["status"], catalyst_attribution.STATUS_MARKET_ONLY)
            self.assertEqual(result["events"], [])

    def test_source_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            kb_wiki = _write_kb(tmp)
            index = catalyst_attribution.build_catalyst_index(kb_wiki, "2026-07-03")
            self.assertFalse(index.sources_available)
            self.assertTrue(index.warnings)
            result = catalyst_attribution.attribute_theme(index, "人形机器人", [])
            self.assertEqual(result["status"], catalyst_attribution.STATUS_SOURCE_MISSING)

    def test_event_outside_window_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            kb_wiki = _write_kb(
                tmp,
                events=[
                    {
                        "report_date": "2026-06-20",
                        "term": "人形机器人",
                        "concept": "人形机器人",
                        "target": "绿的谐波",
                        "catalysts": ["旧消息"],
                    }
                ],
            )
            index = catalyst_attribution.build_catalyst_index(kb_wiki, "2026-07-03", window_days=5)
            result = catalyst_attribution.attribute_theme(index, "人形机器人", [])
            self.assertEqual(result["status"], catalyst_attribution.STATUS_MARKET_ONLY)

    def test_freshness_problems_fresh_sources(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            kb_wiki = _write_kb(
                tmp,
                events=[{"report_date": "2026-07-02", "term": "CPO", "concept": "CPO", "target": "天孚通信"}],
                briefings={"2026-07-03": "# 晨汇\n\n- 今日要点。\n"},
            )
            self.assertEqual(catalyst_attribution.freshness_problems(kb_wiki, "2026-07-03"), [])

    def test_freshness_problems_stale_sources(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            kb_wiki = _write_kb(
                tmp,
                events=[{"report_date": "2026-06-20", "term": "CPO", "concept": "CPO", "target": "天孚通信"}],
                briefings={"2026-06-30": "# 晨汇\n\n- 旧要点。\n"},
            )
            problems = catalyst_attribution.freshness_problems(kb_wiki, "2026-07-03")
            self.assertEqual(len(problems), 2)
            self.assertTrue(any("晨汇断更" in p for p in problems))
            self.assertTrue(any("卖方观点事件断更" in p for p in problems))

    def test_freshness_problems_missing_sources(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            kb_wiki = _write_kb(tmp)
            problems = catalyst_attribution.freshness_problems(kb_wiki, "2026-07-03")
            self.assertEqual(len(problems), 2)
            self.assertTrue(any("晨汇目录缺失" in p for p in problems))
            self.assertTrue(any("卖方观点事件缺失" in p for p in problems))

    def test_enrich_queues_and_brief(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            kb_wiki = _write_kb(
                tmp,
                events=[
                    {
                        "report_date": "2026-07-02",
                        "source": "夜报",
                        "term": "减速器",
                        "concept": "减速器",
                        "target": "绿的谐波",
                        "catalysts": ["谐波减速器涨价"],
                    }
                ],
            )
            index = catalyst_attribution.build_catalyst_index(kb_wiki, "2026-07-03")
            research_queue = {"today_do_ima": [{"目标": "减速器", "强势股": ["绿的谐波"]}], "today_find_official_evidence": []}
            catalyst_attribution.enrich_research_queue(index, research_queue)
            item = research_queue["today_do_ima"][0]
            self.assertEqual(item["催化归因"]["status"], catalyst_attribution.STATUS_NARRATIVE_HIT)

            kb_queue = {"tasks": [{"theme": "减速器", "strong_stocks": ["绿的谐波"]}]}
            catalyst_attribution.enrich_kb_ingest_queue(index, kb_queue)
            task = kb_queue["tasks"][0]
            self.assertEqual(task["catalyst"]["status"], catalyst_attribution.STATUS_NARRATIVE_HIT)

            brief = catalyst_attribution.catalyst_brief(task["catalyst"])
            self.assertIn("叙事驱动", brief)
            self.assertIn("涨价", brief)
            self.assertEqual(catalyst_attribution.catalyst_brief(None), "-")


if __name__ == "__main__":
    unittest.main()
