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
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    matches = KnowledgeAdapter(wiki_root=tmp_path).get_exposure_matches(
        "深研“稳定币支付”题材：给出A股相关公司分层、每家公司可验证证据和证据缺口。"
    )

    assert [item["company"] for item in matches["items"]] == ["四方精创"]
