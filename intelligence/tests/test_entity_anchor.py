from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from intelligence.adapters.knowledge import KnowledgeAdapter
from intelligence.services.entity_anchor import (
    _clear_entity_lexicon_cache,
    resolve_entity_anchor,
)


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
        _clear_entity_lexicon_cache()
        self._tmp = TemporaryDirectory()
        self.wiki_root = Path(self._tmp.name)
        _write_relations(self.wiki_root)
        self.knowledge = KnowledgeAdapter(wiki_root=self.wiki_root)

    def tearDown(self) -> None:
        _clear_entity_lexicon_cache()
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

    def test_relation_is_loaded_once_while_fingerprint_is_unchanged(self) -> None:
        calls = 0
        original = KnowledgeAdapter.load_relation

        def counted(adapter: KnowledgeAdapter, name: str):
            nonlocal calls
            calls += 1
            return original(adapter, name)

        KnowledgeAdapter.load_relation = counted
        try:
            self.assertIsNotNone(resolve_entity_anchor("中际旭创怎么看", self.knowledge))
            self.assertIsNotNone(resolve_entity_anchor("中际旭创估值", self.knowledge))
        finally:
            KnowledgeAdapter.load_relation = original
        self.assertEqual(calls, 1)

    def test_relation_change_refreshes_cached_lexicon(self) -> None:
        self.assertIsNone(resolve_entity_anchor("新增公司怎么看", self.knowledge))
        relation_path = self.knowledge.relation_path("entity_exposures")
        relation = json.loads(relation_path.read_text(encoding="utf-8"))
        relation["entities"]["新增公司"] = {
            "codes": ["688888.SH"],
            "concepts": {"新增题材": {}},
        }
        relation_path.write_text(
            json.dumps(relation, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        anchor = resolve_entity_anchor("新增公司怎么看", self.knowledge)

        assert anchor is not None
        self.assertEqual(anchor.entity, "新增公司")

    def test_different_wiki_roots_do_not_share_cache(self) -> None:
        with TemporaryDirectory() as tmp:
            other_root = Path(tmp)
            _write_relations(other_root)
            path = other_root / "relations" / "entity_exposures.json"
            relation = json.loads(path.read_text(encoding="utf-8"))
            relation["entities"] = {
                "另一家公司": {
                    "codes": ["688889.SH"],
                    "concepts": {"另一个题材": {}},
                }
            }
            path.write_text(json.dumps(relation, ensure_ascii=False), encoding="utf-8")
            other = KnowledgeAdapter(wiki_root=other_root)

            self.assertIsNone(resolve_entity_anchor("中际旭创怎么看", other))
            anchor = resolve_entity_anchor("另一家公司怎么看", other)
            assert anchor is not None
            self.assertEqual(anchor.entity, "另一家公司")


def _write_securities_db(path: Path) -> None:
    import duckdb

    con = duckdb.connect(str(path))
    try:
        con.execute(
            "create table fact_stock_daily("
            "trade_date date, stock_ts_code varchar, stock_name varchar)"
        )
        con.execute(
            "insert into fact_stock_daily values "
            "('2026-07-23','001258.SZ','立新能源'),"
            "('2026-07-23','300308.SZ','旭创科技曾用名'),"
            "('2026-07-23','000002.SZ','万科'),"  # 2 字名：回退词典不收
            "('2026-07-22','001258.SZ','立新能源')"  # 同名多日去重
        )
    finally:
        con.close()


class SecurityMasterFallbackTests(unittest.TestCase):
    """第二本词典（DuckDB 证券名单）：wiki 未登记个股的锚定回退。

    R13-A3 生产形状：「立新能源怎么看」wiki 未登记 → 锚定落空 → 被主题
    词典误抢/落进通用问答。全市场名单一直在 fact_stock_daily 里。
    """

    def setUp(self) -> None:
        _clear_entity_lexicon_cache()
        self._tmp = TemporaryDirectory()
        root = Path(self._tmp.name)
        _write_relations(root)
        self.knowledge = KnowledgeAdapter(wiki_root=root)
        self.db_path = root / "securities.duckdb"
        _write_securities_db(self.db_path)

    def tearDown(self) -> None:
        _clear_entity_lexicon_cache()
        self._tmp.cleanup()

    def test_unregistered_stock_anchors_via_security_master(self) -> None:
        anchor = resolve_entity_anchor(
            "立新能源怎么看",
            self.knowledge,
            securities_db_path=self.db_path,
        )
        assert anchor is not None
        self.assertEqual(anchor.entity, "立新能源")
        self.assertEqual(anchor.ticker, "001258.SZ")
        self.assertEqual(anchor.matched_by, "name")
        self.assertEqual(anchor.concepts, ())
        self.assertTrue(any("证券名单" in item for item in anchor.warnings))

    def test_code_match_falls_back_to_security_master(self) -> None:
        anchor = resolve_entity_anchor(
            "001258 怎么看",
            self.knowledge,
            securities_db_path=self.db_path,
        )
        assert anchor is not None
        self.assertEqual(anchor.entity, "立新能源")
        self.assertEqual(anchor.matched_by, "code")

    def test_wiki_entity_still_wins_over_security_master(self) -> None:
        # 中际旭创两本词典都可能命中；wiki 带概念暴露，必须优先。
        anchor = resolve_entity_anchor(
            "中际旭创怎么看",
            self.knowledge,
            securities_db_path=self.db_path,
        )
        assert anchor is not None
        self.assertEqual(anchor.entity, "中际旭创")
        self.assertIn("CPO", anchor.concepts)

    def test_two_char_security_name_is_not_in_the_fallback_lexicon(self) -> None:
        # 2 字简称常用词碰撞面太大；仍可经 wiki 登记或 6 位代码锚定。
        self.assertIsNone(
            resolve_entity_anchor(
                "万科怎么看",
                self.knowledge,
                securities_db_path=self.db_path,
            )
        )

    def test_missing_db_fails_closed_to_wiki_only(self) -> None:
        anchor = resolve_entity_anchor(
            "立新能源怎么看",
            self.knowledge,
            securities_db_path=Path(self._tmp.name) / "missing.duckdb",
        )
        self.assertIsNone(anchor)

    def test_env_zero_disables_the_fallback(self) -> None:
        # conftest 已把 ENTITY_ANCHOR_SECURITIES_DB 钉成 "0"：不传参数时
        # 第二本词典必须关死，测试才不会在有真实库的机器上变环境依赖。
        self.assertIsNone(resolve_entity_anchor("立新能源怎么看", self.knowledge))


if __name__ == "__main__":
    unittest.main()
