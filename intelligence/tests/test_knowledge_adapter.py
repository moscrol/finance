from __future__ import annotations

import json

from intelligence.adapters.knowledge import KnowledgeAdapter


def test_long_theme_query_matches_named_concept_not_generic_company_terms(
    tmp_path,
) -> None:
    relations = tmp_path / "relations"
    relations.mkdir()
    (relations / "entity_exposures.json").write_text(
        json.dumps(
            {
                "items": [
                    {
                        "company": "四方精创",
                        "concept": "稳定币",
                        "strength": "related",
                        "confidence": "low",
                        "evidence_layer": "L2",
                    },
                    {
                        "company": "无关公司",
                        "concept": "信创",
                        "role": "公司级证据待验证",
                        "strength": "related",
                        "confidence": "high",
                        "evidence_layer": "L1_L3_candidate",
                    },
                    {
                        "company": "另一无关公司",
                        "concept": "光学膜",
                        "reason": "不得把弱关联公司写成核心受益。",
                        "strength": "related",
                        "confidence": "high",
                        "evidence_layer": "L1_L3_candidate",
                    },
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    matches = KnowledgeAdapter(wiki_root=tmp_path).get_exposure_matches(
        "深研“稳定币支付”题材：给出题材定义、产业链上下游、A股相关公司分层、"
        "每家公司可验证证据、证据缺口、反证、触发条件和下一步核验动作。"
        "明确区分事实、推测和待验证项，不得把弱关联公司写成核心受益。"
    )

    assert [item["company"] for item in matches["items"]] == ["四方精创"]


def test_get_evidence_filters_company_facts_by_concept(tmp_path) -> None:
    relations = tmp_path / "relations"
    relations.mkdir()
    (relations / "evidence_index.json").write_text(
        json.dumps(
            {
                "items": [
                    {
                        "target": "天阳科技",
                        "concept": "稳定币",
                        "evidence": "公司披露稳定币跨境支付场景适配。",
                    },
                    {
                        "target": "天阳科技",
                        "concept": "算力租赁",
                        "evidence": "公司投资算力租赁设备。",
                    },
                    {
                        "target": "天阳科技",
                        "concept": "金融IT",
                        "evidence": "公司布局算力和航空场景，并提及稳定币政策。",
                    },
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    evidence = KnowledgeAdapter(wiki_root=tmp_path).get_evidence(
        "天阳科技",
        concept="稳定币",
    )

    assert [item["concept"] for item in evidence["items"]] == ["稳定币"]
