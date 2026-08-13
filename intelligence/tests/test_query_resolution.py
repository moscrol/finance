from __future__ import annotations

import json
from pathlib import Path

import pytest

from intelligence.adapters.knowledge import KnowledgeAdapter
from intelligence.services.query_resolution import QueryResolver


@pytest.fixture
def resolver(tmp_path: Path) -> QueryResolver:
    relations = tmp_path / "relations"
    relations.mkdir()
    (relations / "entity_exposures.json").write_text(
        json.dumps(
            {
                "entities": {
                    "中际旭创": {
                        "codes": ["300308.SZ"],
                        "concepts": {"CPO": {}, "光模块": {}},
                    },
                    "宁德时代": {
                        "codes": ["300750.SZ"],
                        "concepts": {"新能源": {}},
                    },
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (relations / "aliases.json").write_text(
        json.dumps(
            {"aliases": {"光模块代工": "光模块", "光通信模块": "光模块"}},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return QueryResolver(KnowledgeAdapter(wiki_root=tmp_path))


def test_resolver_anchors_known_entity(resolver: QueryResolver) -> None:
    resolution = resolver.resolve("中际旭创怎么看")

    assert resolution.envelope.subject == "中际旭创"
    assert resolution.envelope.subject_kind == "company"
    assert resolution.envelope.question_type == "stock_deep_dive"
    assert resolution.reference_kind == "none"


def test_resolver_anchors_ticker(resolver: QueryResolver) -> None:
    resolution = resolver.resolve("300308怎么看")

    assert resolution.envelope.subject == "中际旭创"
    assert resolution.anchor is not None
    assert resolution.anchor.matched_by == "code"


def test_resolver_matches_registered_theme_alias(resolver: QueryResolver) -> None:
    resolution = resolver.resolve("光通信模块怎么看")

    assert resolution.envelope.subject == "光模块"
    assert resolution.envelope.subject_kind == "theme"
    assert resolution.envelope.question_type == "theme_analysis"


def test_theme_term_embedded_in_a_longer_name_is_not_stolen(
    resolver: QueryResolver,
) -> None:
    """生产 R13-A3：「立新能源」是个股 001258，主题「新能源」不得从名字里抠出来。

    实体锚定因 wiki 未登记落空后，旧的无边界子串匹配把问题偷进
    theme_analysis / theme-research，零证据终局。国新能源、宝新能源、
    华润新能源同形状。降级到 general QA 是可接受的失败，被偷走不是。
    """

    resolution = resolver.resolve("立新能源怎么看")

    assert resolution.envelope.subject != "新能源"
    assert resolution.envelope.subject_kind != "theme"
    assert resolution.envelope.question_type != "theme_analysis"


def test_bare_theme_term_still_matches(resolver: QueryResolver) -> None:
    resolution = resolver.resolve("新能源怎么看")

    assert resolution.envelope.subject == "新能源"
    assert resolution.envelope.subject_kind == "theme"


def test_theme_term_extended_to_the_right_still_matches(
    resolver: QueryResolver,
) -> None:
    """右邻延伸（新能源汽车）是主题短语的形状，刻意不 veto。

    更长的别名在词表里按长度降序先匹配；词表缺失时把它归到「新能源」
    大体无害——与左邻嵌入（公司名后缀）不对称是设计决定。
    """

    resolution = resolver.resolve("新能源汽车板块怎么看")

    assert resolution.envelope.subject == "新能源"
    assert resolution.envelope.subject_kind == "theme"


def test_punctuation_before_theme_term_is_a_clean_boundary(
    resolver: QueryResolver,
) -> None:
    resolution = resolver.resolve("光伏、新能源怎么看")

    assert resolution.envelope.subject == "新能源"
    assert resolution.envelope.subject_kind == "theme"


@pytest.mark.parametrize(
    ("query", "kind"),
    (
        ("这个逻辑呢", "logic"),
        ("这个方向怎么看", "direction"),
        ("这条链有哪些公司", "chain"),
        ("边际变化呢", "market_change"),
        ("那它的客户呢", "entity_pronoun"),
        ("继续看反证", "continuation"),
    ),
)
def test_resolver_classifies_contextual_reference(
    query: str,
    kind: str,
    resolver: QueryResolver,
) -> None:
    resolution = resolver.resolve(query)

    assert resolution.context_dependent is True
    assert resolution.reference_kind == kind


def test_complete_question_is_not_contextual_reference(resolver: QueryResolver) -> None:
    resolution = resolver.resolve("光模块现在处于产业周期什么阶段")

    assert resolution.context_dependent is False
    assert resolution.reference_kind == "none"


def test_relation_operators_are_structured_outputs(resolver: QueryResolver) -> None:
    resolution = resolver.resolve("光模块上游有哪些公司，最近有什么边际变化")

    assert resolution.envelope.operators == (
        "relation",
        "company_mapping",
        "market_change",
    )
    assert resolution.envelope.required_outputs == (
        "relation_map",
        "company_mapping",
        "market_change",
    )
