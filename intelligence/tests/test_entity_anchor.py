from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from intelligence.adapters.knowledge import KnowledgeAdapter
from intelligence.services.entity_anchor import resolve_entity_anchor


def _write_relations(wiki_root: Path) -> None:
    relations = wiki_root / "relations"
    relations.mkdir(parents=True)
    (relations / "entity_exposures.json").write_text(
        json.dumps(
            {
                "entities": {
                    "深信服": {
                        "codes": ["300454.SZ"],
                        "concepts": {"网络安全": {}, "信创": {}},
                    },
                    "中际旭创": {
                        "codes": ["300308.SZ"],
                        "concepts": {"CPO": {}, "800G光模块": {}},
                    },
                    "三花智控": {
                        "codes": ["002050.SZ"],
                        "concepts": {"机器人执行器": {}},
                    },
                    "无概念公司": {"codes": ["600000.SH"], "concepts": {}},
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


class EntityAnchorTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = TemporaryDirectory()
        self.wiki_root = Path(self._tmp.name)
        _write_relations(self.wiki_root)
        self.knowledge = KnowledgeAdapter(wiki_root=self.wiki_root)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_anchors_valuation_question_to_entity_concepts(self) -> None:
        anchor = resolve_entity_anchor("深信服现在 PE TTM 80 倍，贵不贵？", self.knowledge)
        assert anchor is not None
        self.assertEqual(anchor.entity, "深信服")
        self.assertEqual(anchor.ticker, "300454.SZ")
        self.assertIn("网络安全", anchor.concepts)
        self.assertIn("网络安全", anchor.graph_query)
        self.assertNotIn("PE", anchor.graph_query)

    def test_anchors_earnings_question(self) -> None:
        anchor = resolve_entity_anchor("中际旭创下周出中报预告，怎么提前推演？", self.knowledge)
        assert anchor is not None
        self.assertEqual(anchor.entity, "中际旭创")
        self.assertIn("CPO", anchor.concepts)

    def test_code_match_takes_priority(self) -> None:
        anchor = resolve_entity_anchor("300308 中报预告怎么看", self.knowledge)
        assert anchor is not None
        self.assertEqual(anchor.entity, "中际旭创")
        self.assertEqual(anchor.matched_by, "code")

    def test_no_entity_returns_none(self) -> None:
        self.assertIsNone(resolve_entity_anchor("今天数据要素板块怎么样", self.knowledge))
        self.assertIsNone(resolve_entity_anchor("", self.knowledge))

    def test_entity_without_concepts_degrades_with_warning(self) -> None:
        anchor = resolve_entity_anchor("无概念公司值得买吗", self.knowledge)
        assert anchor is not None
        self.assertEqual(anchor.concepts, ())
        self.assertEqual(anchor.graph_query, "无概念公司")
        self.assertTrue(anchor.warnings)

    def test_missing_relation_file_returns_none(self) -> None:
        with TemporaryDirectory() as tmp:
            knowledge = KnowledgeAdapter(wiki_root=Path(tmp))
            self.assertIsNone(resolve_entity_anchor("深信服估值", knowledge))


if __name__ == "__main__":
    unittest.main()
