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


def _write_status_index(tmp_path) -> None:
    relations = tmp_path / "relations"
    relations.mkdir()
    (relations / "evidence_index.json").write_text(
        json.dumps(
            {
                "items": [
                    {
                        "target": "英维克",
                        "evidence": "旧口径：液冷收入占比 10%。",
                        "status": "superseded",
                        "superseded_by": "2026-07 中报口径",
                    },
                    {
                        "target": "英维克",
                        "evidence": "已证伪：并未中标该项目。",
                        "status": "invalidated",
                    },
                    {
                        "target": "英维克",
                        "evidence": "新口径：液冷收入占比 25%。",
                        "status": "active",
                    },
                    {
                        "target": "英维克",
                        "evidence": "无状态字段的存量条目。",
                    },
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def test_get_evidence_excludes_invalidated_and_deprioritizes_superseded(
    tmp_path,
) -> None:
    _write_status_index(tmp_path)

    evidence = KnowledgeAdapter(wiki_root=tmp_path).get_evidence("英维克")

    texts = [item["evidence"] for item in evidence["items"]]
    assert "已证伪：并未中标该项目。" not in texts
    assert texts == [
        "新口径：液冷收入占比 25%。",
        "无状态字段的存量条目。",
        "旧口径：液冷收入占比 10%。",
    ]


def test_get_evidence_can_include_invalidated_for_audit(tmp_path) -> None:
    _write_status_index(tmp_path)

    evidence = KnowledgeAdapter(wiki_root=tmp_path).get_evidence(
        "英维克",
        include_invalidated=True,
    )

    texts = [item["evidence"] for item in evidence["items"]]
    assert "已证伪：并未中标该项目。" in texts


def test_get_evidence_applies_invalidation_overlay(tmp_path) -> None:
    relations = tmp_path / "relations"
    relations.mkdir()
    hard_item = {
        "target": "东方日升",
        "concept": "钙钛矿",
        "source_date": "2026-05-01",
        "source": "[[旧研报]]",
        "evidence": "公司钙钛矿中试线即将投产。",
    }
    soft_item = {
        "target": "东方日升",
        "concept": "钙钛矿",
        "source_date": "2026-05-10",
        "source": "[[旧纪要]]",
        "evidence": "预计三季度产能爬坡。",
    }
    (relations / "evidence_index.json").write_text(
        json.dumps({"items": [hard_item, soft_item]}, ensure_ascii=False),
        encoding="utf-8",
    )

    def key(item: dict) -> str:
        return "|".join(
            (
                item["target"],
                item["concept"],
                item["source_date"],
                item["source"],
                item["evidence"][:80],
            )
        )

    (relations / "invalidation_links.json").write_text(
        json.dumps(
            {
                "schema": "invalidation_links/v1",
                "links": [
                    {
                        "target": "东方日升",
                        "concept": "钙钛矿",
                        "strength": "hard",
                        "negation": {
                            "source_date": "2026-06-01",
                            "source": "[[公司公告]]",
                            "hits": ["终止"],
                        },
                        "invalidates": [{"key": key(hard_item)}],
                    },
                    {
                        "target": "东方日升",
                        "concept": "钙钛矿",
                        "strength": "soft",
                        "negation": {
                            "source_date": "2026-06-05",
                            "source": "[[调研纪要]]",
                            "hits": ["不及预期"],
                        },
                        "invalidates": [{"key": key(soft_item)}],
                    },
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    evidence = KnowledgeAdapter(wiki_root=tmp_path).get_evidence("东方日升")

    texts = [item["evidence"] for item in evidence["items"]]
    assert "公司钙钛矿中试线即将投产。" not in texts
    assert texts == ["预计三季度产能爬坡。"]
    weakened = evidence["items"][0]
    assert weakened["status"] == "superseded"
    assert "回链" in weakened["status_note"]


def test_relation_cache_avoids_reparsing_unchanged_file(tmp_path, monkeypatch) -> None:
    """同一份 relations 在一次问答里会被读十几次，不应每次全量重解析。"""
    from intelligence.adapters import knowledge

    knowledge.clear_relation_cache()
    relations = tmp_path / "relations"
    relations.mkdir()
    (relations / "concept_graph.json").write_text(
        json.dumps({"concepts": {"国产算力": {"note": "x"}}}, ensure_ascii=False),
        encoding="utf-8",
    )

    parses = {"n": 0}
    original = knowledge.json.loads

    def counting_loads(*args, **kwargs):
        parses["n"] += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(knowledge.json, "loads", counting_loads)

    adapter = KnowledgeAdapter(wiki_root=tmp_path)
    for _ in range(5):
        assert adapter.load_relation("concept_graph")["found"] is True

    assert parses["n"] == 1


def test_relation_cache_invalidates_when_kb_is_rebuilt(tmp_path) -> None:
    """KB 每天重建；mtime/size 变化必须让缓存失效，不得返回陈旧图谱。"""
    import os

    from intelligence.adapters import knowledge

    knowledge.clear_relation_cache()
    relations = tmp_path / "relations"
    relations.mkdir()
    path = relations / "concept_graph.json"
    path.write_text(json.dumps({"concepts": {"旧": {}}}), encoding="utf-8")

    adapter = KnowledgeAdapter(wiki_root=tmp_path)
    assert "旧" in adapter.load_relation("concept_graph")["data"]["concepts"]

    path.write_text(
        json.dumps({"concepts": {"新": {}, "新2": {}}}), encoding="utf-8"
    )
    stat = path.stat()
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000_000))

    concepts = adapter.load_relation("concept_graph")["data"]["concepts"]
    assert "新" in concepts
    assert "旧" not in concepts


def test_missing_relation_still_reports_not_found(tmp_path) -> None:
    from intelligence.adapters import knowledge

    knowledge.clear_relation_cache()
    (tmp_path / "relations").mkdir()

    relation = KnowledgeAdapter(wiki_root=tmp_path).load_relation("concept_graph")

    assert relation["found"] is False
    assert relation["warnings"] == ["relation file not found"]
