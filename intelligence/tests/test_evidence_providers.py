# -*- coding: utf-8 -*-
"""evidence_providers 的独立单测（端到端行为由 test_golden_answers.py 保护）。"""
from __future__ import annotations

import unittest
from types import SimpleNamespace

from intelligence.adapters.knowledge import evidence_status
from intelligence.services.ask_types import AskOptions, AskResult, Citation
from intelligence.services.entity_anchor import EntityAnchor
from intelligence.services import evidence_providers as ep

_CHANGDIAN_BASELINE = (
    "长电科技|先进封装|2026-04-08|[[长电科技 2025年度报告 baseline 2026-04-08]]|"
    "XDFOI芯粒高密度多维异构集成系列工艺已进入量产阶段"
)
_GUOJU_HIKE = "国巨自7/1起上调全系列电容售价、首次纳入EMS/OEM直接客户"


class _CatalogKnowledge:
    """按 target/concept 精确过滤，复现 adapter 把错位概念绑到锚定实体时的空命中。

    排序/丢弃规则对齐 ``KnowledgeAdapter.get_evidence``：invalidated 默认丢，
    superseded 排在全部 active 之后。旁路扫描另走 ``get_stale_edges``。
    """

    def __init__(self, catalog: dict[str, list[dict]]) -> None:
        self.catalog = catalog
        self.calls: list[tuple[str, str | None]] = []
        self.stale_calls: list[str] = []
        self.stale_concept_args: list[str | None] = []

    def get_evidence(self, target, concept=None, limit=20, include_invalidated=False):
        self.calls.append((target, concept))
        items = list(self.catalog.get(target, []))
        if concept:
            items = [item for item in items if item.get("concept") == concept]
        kept = []
        for item in items:
            if evidence_status(item) == "invalidated" and not include_invalidated:
                continue
            kept.append(item)
        kept.sort(key=lambda item: evidence_status(item) == "superseded")
        matched = kept[:limit]
        return {"found": bool(matched), "items": matched}

    def get_stale_edges(self, target, concept=None):
        # 故意接收 concept：若生产旁路把概念袋传进来，测试能抓到。
        self.stale_calls.append(target)
        self.stale_concept_args.append(concept)
        items = [
            item
            for item in self.catalog.get(target, [])
            if evidence_status(item) in {"superseded", "invalidated"}
        ]
        if concept:
            items = [item for item in items if item.get("concept") == concept]
        return {"found": bool(items), "target": target, "items": items}


def _item(
    target: str,
    *,
    evidence: str,
    source: str = "[[src]]",
    source_date: str = "2026-03-01",
    status: str = "active",
    **extra: object,
) -> dict:
    row = {
        "target": target,
        "evidence": evidence,
        "source": source,
        "source_date": source_date,
        "confidence": "high",
        "status": status,
    }
    row.update(extra)
    return row


def _actives(target: str, n: int, *, prefix: str = "active") -> list[dict]:
    return [
        _item(target, evidence=f"{prefix}-{i:02d}", source=f"[[{prefix}-{i:02d}]]")
        for i in range(n)
    ]


def _bypass_notes(notes: list[str], target: str) -> list[str]:
    needle = f"{target} 有 "
    return [note for note in notes if note.startswith(needle) and "条证据已被取代" in note]


def _evidence_ctx(
    *,
    query: str,
    knowledge,
    anchor: EntityAnchor | None = None,
    matched_theme: str | None = None,
) -> ep.EvidenceContext:
    options = AskOptions(query=query, max_evidence=8)
    result = AskResult(
        query=query,
        trade_date=None,
        matched_theme=matched_theme,
        candidate_tier=None,
        priority_score=None,
    )
    citations: list[Citation] = []

    def cite(prefix: str, source: str, detail: str = "") -> str:
        tag = f"{prefix}{sum(1 for item in citations if item.tag.startswith(prefix)) + 1}"
        citations.append(Citation(tag=tag, source=source, detail=detail))
        return f"[{tag}]"

    return ep.EvidenceContext(
        options=options,
        result=result,
        knowledge=knowledge,
        question_plan=SimpleNamespace(),
        anchor=anchor,
        candidate=None,
        doc={},
        export_name="export.json",
        claim_theme=query,
        graph_query=query,
        cite=cite,
        structured_claims=[],
        company_candidates=[],
        is_stale=lambda _item: False,
        confidence_score=lambda _value: None,
        stage_timeout=lambda limit: limit,
    )


class CompanyExposureTierTests(unittest.TestCase):
    def test_core_requires_direct_company_evidence(self) -> None:
        row = {"strength": "core", "confidence": "high", "evidence_layer": "L3"}
        self.assertEqual(ep._company_exposure_tier(row), "core")

    def test_graph_only_is_peripheral(self) -> None:
        row = {"strength": "core", "confidence": "high", "evidence_layer": "graph_only"}
        self.assertEqual(ep._company_exposure_tier(row), "peripheral")

    def test_default_other(self) -> None:
        row = {"strength": "medium", "confidence": "mid", "evidence_layer": "L2"}
        self.assertEqual(ep._company_exposure_tier(row), "other")


class PriorConclusionPageTests(unittest.TestCase):
    def test_synthesis_and_briefings_are_prior(self) -> None:
        self.assertTrue(ep._is_prior_conclusion_page("synthesis/2026-07-01.md"))
        self.assertTrue(ep._is_prior_conclusion_page("briefings/foo.md"))
        self.assertTrue(ep._is_prior_conclusion_page("/synthesis/foo.md"))

    def test_other_pages_are_not_prior(self) -> None:
        self.assertFalse(ep._is_prior_conclusion_page("concepts/液冷.md"))


class CompanyNameFromOfficialTitleTests(unittest.TestCase):
    def test_extracts_company_before_keyword(self) -> None:
        self.assertEqual(
            ep._company_name_from_official_title("申菱环境：投资者关系活动记录"),
            "申菱环境",
        )

    def test_rejects_non_name_prefix(self) -> None:
        self.assertIsNone(
            ep._company_name_from_official_title("关于近期市场传闻的说明！？公告"),
        )


class CollectEvidenceIndexAnchorTests(unittest.TestCase):
    """R 通道：锚定实体不能被图谱暴露概念滤空。"""

    def _catalog(self) -> dict[str, list[dict]]:
        return {
            "长电科技": [
                {
                    "target": "长电科技",
                    "concept": "AI算力",
                    "source": "[[AI算力产业新格局与供应链深度研究报告]]",
                    "evidence": "2025年前三季度营收 286.69 亿元，同比增长 18%",
                    "source_date": "2025-10-31",
                    "confidence": "high",
                }
            ],
            "富信科技": [
                {
                    "target": "富信科技",
                    "concept": "CPO",
                    "source": "[[富信科技_688662_最新逻辑跟踪_20260612]]",
                    "evidence": "Micro TEC国产替代",
                    "source_date": "2026-06-12",
                    "confidence": "medium",
                }
            ],
        }

    def test_anchored_entity_evidence_survives_mismatched_graph_concept(self) -> None:
        knowledge = _CatalogKnowledge(self._catalog())
        ctx = _evidence_ctx(
            query="长电科技的营收规模怎么看",
            knowledge=knowledge,
            anchor=EntityAnchor(entity="长电科技", ticker="600584", matched_by="name"),
        )
        bundle = ep.collect_evidence_index(
            ctx,
            {"长电科技": "1.6T CPO", "富信科技": "CPO"},
        )
        joined = "\n".join(bundle.lines)
        self.assertIn("286.69", joined)
        self.assertIn("长电科技", joined)
        self.assertIn(("长电科技", None), knowledge.calls)

    def test_unanchored_query_still_uses_graph_concept_filter(self) -> None:
        knowledge = _CatalogKnowledge(self._catalog())
        ctx = _evidence_ctx(
            query="光模块温控怎么看",
            knowledge=knowledge,
            anchor=None,
        )
        bundle = ep.collect_evidence_index(ctx, {"富信科技": "CPO", "长电科技": "1.6T CPO"})
        joined = "\n".join(bundle.lines)
        self.assertIn("富信科技", joined)
        self.assertIn("Micro TEC", joined)
        self.assertNotIn("286.69", joined)
        self.assertIn(("富信科技", "CPO"), knowledge.calls)
        self.assertIn(("长电科技", "1.6T CPO"), knowledge.calls)


class CollectEvidenceIndexStaleBypassTests(unittest.TestCase):
    """方案 D：top-8 名额不动，截断外旁路扫 superseded/invalidated。"""

    def _collect(self, catalog, *, query, anchor=None, theme=None, concepts=None):
        knowledge = _CatalogKnowledge(catalog)
        ctx = _evidence_ctx(
            query=query,
            knowledge=knowledge,
            anchor=anchor,
            matched_theme=theme,
        )
        bundle = ep.collect_evidence_index(ctx, concepts or {})
        return knowledge, bundle

    def test_changdian_rich_host_gets_one_bypass_note_without_quota_squeeze(self) -> None:
        catalog = {
            "长电科技": [
                *_actives("长电科技", 32),
                _item(
                    "长电科技",
                    evidence="作为全球第三、中国大陆第一的集成电路封测企业，2024 年营收 359.62 亿元。",
                    source="[[先进封装研报]]",
                    source_date="2026-01-29",
                    status="superseded",
                    concept="先进封装",
                    superseded_by=_CHANGDIAN_BASELINE,
                ),
                _item(
                    "长电科技",
                    evidence="2024 年营收 359.61 亿元，同比增长 21.24%。",
                    source="[[存储芯片研报]]",
                    source_date="2026-01-29",
                    status="superseded",
                    concept="存储芯片",
                    superseded_by=_CHANGDIAN_BASELINE,
                ),
            ]
        }
        knowledge, bundle = self._collect(
            catalog,
            query="长电科技的营收规模怎么看",
            anchor=EntityAnchor(entity="长电科技", ticker="600584", matched_by="name"),
            concepts={"长电科技": "1.6T CPO"},
        )
        self.assertEqual(len(bundle.lines), 8)
        self.assertTrue(all("359.62" not in line and "⚠️" not in line for line in bundle.lines))
        self.assertEqual(
            [line.split("：", 1)[1][:9] for line in bundle.lines],
            [f"active-{i:02d}" for i in range(8)],
        )
        notes = _bypass_notes(bundle.stale_notes, "长电科技")
        self.assertEqual(len(notes), 1, bundle.stale_notes)
        note = notes[0]
        self.assertIn("有 2 条证据已被取代", note)
        self.assertIn("2026-04-08", note)
        self.assertIn("baseline", note)
        self.assertIn("长电科技", knowledge.stale_calls)
        self.assertTrue(all(arg is None for arg in knowledge.stale_concept_args))

    def test_dram_sparse_host_keeps_window_markers_and_does_not_repeat_bypass(self) -> None:
        catalog = {
            "DRAM": [
                *_actives("DRAM", 5),
                _item(
                    "DRAM",
                    evidence="长鑫招股书细化：26Q1收入508亿",
                    source="[[招股书]]",
                    source_date="2026-05-18",
                    status="superseded",
                    superseded_by="DRAM||2026-07-24|[[晚间卖方研报20260724]]|华西深度",
                ),
                _item(
                    "DRAM",
                    evidence="华西计算机长鑫科技深度：国产DRAM研发设计制造一体化龙头",
                    source="[[晚间卖方研报20260724]]",
                    source_date="2026-07-24",
                    status="superseded",
                    superseded_by="DRAM||2026-07-27|[[晚间卖方研报20260727]]|长鑫上市",
                ),
            ]
        }
        _, bundle = self._collect(catalog, query="DRAM")
        self.assertEqual(sum("⚠️已被新证据取代" in line for line in bundle.lines), 2)
        self.assertEqual(len(_bypass_notes(bundle.stale_notes, "DRAM")), 0, bundle.stale_notes)
        self.assertEqual(
            sum("该条证据已被取代" in note for note in bundle.stale_notes),
            2,
        )

    def test_mlcc_seventh_month_hike_stays_eighth_active(self) -> None:
        actives = _actives("MLCC", 16)
        actives[7] = _item(
            "MLCC",
            evidence=_GUOJU_HIKE,
            source="[[晚间卖方研报20260701]]",
            source_date="2026-07-01",
        )
        catalog = {
            "MLCC": [
                *actives,
                *[
                    _item(
                        "MLCC",
                        evidence=f"old-usage-{i}",
                        source=f"[[old-{i}]]",
                        source_date="2026-02-22",
                        status="superseded",
                        superseded_by="MLCC||2026-07-27|[[晚间卖方研报20260727]]|太诱再涨价",
                    )
                    for i in range(6)
                ],
            ]
        }
        _, bundle = self._collect(catalog, query="MLCC")
        self.assertEqual(len(bundle.lines), 8)
        self.assertIn(_GUOJU_HIKE, bundle.lines[7])
        self.assertTrue(all("⚠️" not in line for line in bundle.lines))

    def test_invalidated_overlay_hard_gets_bypass_note(self) -> None:
        catalog = {
            "风华高科": [
                *_actives("风华高科", 6),
                _item(
                    "风华高科",
                    evidence="国内 MLCC 龙头，全球市占率 7%",
                    source="[[旧研报]]",
                    source_date="2026-01-29",
                    status="invalidated",
                    status_note="回链：2026-06-03 否认（证伪·待人工复核）",
                ),
                _item(
                    "风华高科",
                    evidence="MLCC现货价上调20%量价齐升",
                    source="[[0205强势脱水]]",
                    source_date="2026-02-05",
                    status="invalidated",
                    status_note="回链：2026-06-03 否认（证伪·待人工复核）",
                ),
            ]
        }
        _, bundle = self._collect(
            catalog,
            query="风华高科怎么看",
            anchor=EntityAnchor(entity="风华高科", ticker="000636", matched_by="name"),
        )
        self.assertEqual(len(bundle.lines), 6)
        notes = _bypass_notes(bundle.stale_notes, "风华高科")
        self.assertEqual(len(notes), 1, bundle.stale_notes)
        self.assertIn("有 2 条证据已被取代", notes[0])
        self.assertIn("2026-06-03", notes[0])

    def test_theme_bypass_survives_company_quota_fill(self) -> None:
        catalog = {
            "长电科技": _actives("长电科技", 10),
            "电子布": [
                *_actives("电子布", 3, prefix="cloth"),
                _item(
                    "电子布",
                    evidence="巨石 0 库存",
                    source="[[电子布旧口径]]",
                    source_date="2026-06-25",
                    status="superseded",
                    superseded_by="电子布||2026-07-20|[[新口径]]|供给缺口",
                ),
            ],
        }
        _, bundle = self._collect(
            catalog,
            query="长电科技的电子布封测怎么看",
            anchor=EntityAnchor(entity="长电科技", ticker="600584", matched_by="name"),
            theme="电子布",
            concepts={"长电科技": "先进封装"},
        )
        self.assertEqual(len(bundle.lines), 8)
        self.assertTrue(all(line.startswith("长电科技") for line in bundle.lines))
        notes = _bypass_notes(bundle.stale_notes, "电子布")
        self.assertEqual(len(notes), 1, bundle.stale_notes)
        self.assertIn("供给缺口", notes[0])

    def test_bypass_note_char_budget_and_zero_when_no_stale(self) -> None:
        catalog = {
            "干净宿主": _actives("干净宿主", 3),
            "长电科技": [
                *_actives("长电科技", 9),
                _item(
                    "长电科技",
                    evidence="2024 年营收 359.62 亿元",
                    source="[[旧]]",
                    source_date="2026-01-29",
                    status="superseded",
                    superseded_by=_CHANGDIAN_BASELINE + ("｜" + "很长指针" * 40),
                ),
            ],
        }
        _, clean = self._collect(catalog, query="干净宿主")
        self.assertEqual(_bypass_notes(clean.stale_notes, "干净宿主"), [])
        _, rich = self._collect(
            catalog,
            query="长电科技",
            anchor=EntityAnchor(entity="长电科技", ticker="600584", matched_by="name"),
        )
        notes = _bypass_notes(rich.stale_notes, "长电科技")
        self.assertEqual(len(notes), 1)
        self.assertLessEqual(len(notes[0]), 180)
        self.assertGreaterEqual(len(notes[0]), 80)


class CollectEvidenceIndexCounterReserveTests(unittest.TestCase):
    """KC-05：top-8 里保底反方槽；无命中显式披露，不空占。"""

    def _collect(self, catalog, *, query, anchor=None, theme=None, concepts=None):
        knowledge = _CatalogKnowledge(catalog)
        ctx = _evidence_ctx(
            query=query,
            knowledge=knowledge,
            anchor=anchor,
            matched_theme=theme,
        )
        bundle = ep.collect_evidence_index(ctx, concepts or {})
        return knowledge, bundle

    def test_buried_counter_keeps_reserved_slot_and_mark(self) -> None:
        catalog = {
            "长电科技": [
                *_actives("长电科技", 8),
                _item(
                    "长电科技",
                    evidence="封测同行扩产过快，供给过剩压力上升",
                    source="[[反方研报]]",
                ),
                _item(
                    "长电科技",
                    evidence="部分客户需求不及预期，订单下滑",
                    source="[[反方纪要]]",
                ),
                _item(
                    "长电科技",
                    evidence="第三条反方不应挤进保底槽",
                    source="[[多余]]",
                ),
            ]
        }
        _, bundle = self._collect(
            catalog,
            query="长电科技怎么看",
            anchor=EntityAnchor(entity="长电科技", ticker="600584", matched_by="name"),
        )
        self.assertEqual(len(bundle.lines), 8)
        counter_lines = [line for line in bundle.lines if line.startswith("[反]")]
        self.assertEqual(len(counter_lines), 2, bundle.lines)
        self.assertTrue(all("长电科技：" in line for line in counter_lines))
        self.assertTrue(any("供给过剩" in line for line in counter_lines))
        self.assertTrue(any("需求不及预期" in line for line in counter_lines))
        self.assertFalse(any("第三条反方" in line for line in bundle.lines))
        support_lines = [line for line in bundle.lines if not line.startswith("[反]")]
        self.assertEqual(len(support_lines), 6)
        self.assertIsNone(bundle.counter_disclosure)

    def test_no_counter_hit_discloses_instead_of_silence(self) -> None:
        catalog = {"长电科技": _actives("长电科技", 8)}
        _, bundle = self._collect(
            catalog,
            query="长电科技怎么看",
            anchor=EntityAnchor(entity="长电科技", ticker="600584", matched_by="name"),
        )
        self.assertEqual(len(bundle.lines), 8)
        self.assertTrue(all(not line.startswith("[反]") for line in bundle.lines))
        self.assertEqual(bundle.counter_disclosure, "未检索到反方证据")

    def test_single_counter_does_not_empty_occupy(self) -> None:
        catalog = {
            "长电科技": [
                _item("长电科技", evidence="营收同比增长 18%"),
                _item("长电科技", evidence="同行打价格战，毛利率承压"),
            ]
        }
        _, bundle = self._collect(
            catalog,
            query="长电科技怎么看",
            anchor=EntityAnchor(entity="长电科技", ticker="600584", matched_by="name"),
        )
        self.assertEqual(len(bundle.lines), 2)
        self.assertTrue(bundle.lines[0].startswith("长电科技："))
        self.assertTrue(bundle.lines[1].startswith("[反]"))
        self.assertIn("价格战", bundle.lines[1])
        self.assertIsNone(bundle.counter_disclosure)


class _HopKnowledge(_CatalogKnowledge):
    def __init__(self, catalog, lexicon: tuple[str, ...]) -> None:
        super().__init__(catalog)
        self.lexicon = lexicon

    def get_concept_matches(self, term, limit=5):
        del term
        return {
            "found": True,
            "items": [{"concept": name} for name in self.lexicon[:limit]],
        }

    def get_exposure_matches(self, term, limit=12):
        del term, limit
        return {"found": False, "items": []}


class CollectEvidenceIndexSecondHopTests(unittest.TestCase):
    """KC-06：窄命中/邻居抽出的第二跳 target，行上标跳数，不加行。"""

    def test_neighbor_second_hop_fills_sparse_first_round(self) -> None:
        knowledge = _HopKnowledge(
            {
                "树脂": [
                    _item("树脂", evidence="电子级树脂供给偏紧，光刻胶上游涨价")
                ]
            },
            ("树脂", "光引发剂", "单体"),
        )
        ctx = _evidence_ctx(
            query="光刻胶现在处于什么阶段",
            knowledge=knowledge,
            matched_theme="光刻胶",
        )
        bundle = ep.collect_evidence_index(ctx, {})
        hop_lines = [line for line in bundle.lines if "〔第2跳〕" in line]
        self.assertTrue(any("树脂" in line for line in hop_lines), bundle.lines)
        self.assertIn(("树脂", None), knowledge.calls)
        self.assertEqual(len(bundle.lines), 1)

    def test_second_hop_target_calls_capped_at_three(self) -> None:
        lexicon = ("树脂", "光引发剂", "单体", "晶圆厂", "ArF")
        catalog = {
            name: [_item(name, evidence=f"{name} 供给")]
            for name in lexicon
        }
        knowledge = _HopKnowledge(catalog, lexicon)
        ctx = _evidence_ctx(
            query="光刻胶现在处于什么阶段",
            knowledge=knowledge,
            matched_theme="光刻胶",
        )
        ep.collect_evidence_index(ctx, {})
        hop_targets = [target for target, _concept in knowledge.calls if target in lexicon]
        self.assertEqual(hop_targets, ["树脂", "光引发剂", "单体"])

    def test_second_hop_does_not_add_rows_beyond_max_evidence(self) -> None:
        knowledge = _HopKnowledge(
            {
                "光刻胶": _actives("光刻胶", 8),
                "树脂": _actives("树脂", 4, prefix="resin"),
            },
            ("树脂",),
        )
        ctx = _evidence_ctx(
            query="光刻胶",
            knowledge=knowledge,
            matched_theme="光刻胶",
        )
        bundle = ep.collect_evidence_index(ctx, {})
        self.assertEqual(len(bundle.lines), 8)
        self.assertIn(("树脂", None), knowledge.calls)
        self.assertEqual(sum("〔第2跳〕" in line for line in bundle.lines), 1)
        self.assertTrue(any("树脂" in line for line in bundle.lines))


if __name__ == "__main__":
    unittest.main()
