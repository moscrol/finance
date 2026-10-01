"""两家以上公司被点名、又没写「分别 / 比较」这类落点词时，仍按比较题路由。

来源：2026-10-01 Mac 改写探针 v1（`scripts/route_paraphrase_probe.py`，16 个锚点）。
uq15-q04 原题「亨通光电和长飞光纤当天分别表现如何」命中比较；三个口语改写
（顿号并列、「各自」、「vs」）全部落到 stock_deep_dive，只深挖第一家，第二家整个丢掉。

沙箱默认没有知识库、公司名解析不出来，旧测试看不到这个 bug；这里用临时词典
复现有词典的环境。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from intelligence.adapters.knowledge import KnowledgeAdapter
from intelligence.services.query_resolution import QueryResolver
from intelligence.services.research_contract import TurnIntent
from intelligence.services.turn_controller import decide_turn

_NAMES = {
    "亨通光电": "600487.SH",
    "长飞光纤": "601869.SH",
    "中际旭创": "300308.SZ",
    "宁德时代": "300750.SZ",
    "强瑞技术": "301128.SZ",
    "冰轮环境": "000811.SZ",
    "英维克": "002837.SZ",
    "高澜股份": "300499.SZ",
    "申菱环境": "301018.SZ",
}


@pytest.fixture
def resolver(tmp_path: Path) -> QueryResolver:
    relations = tmp_path / "relations"
    relations.mkdir()
    (relations / "entity_exposures.json").write_text(
        json.dumps(
            {"entities": {n: {"codes": [c], "concepts": {"光通信": {}}} for n, c in _NAMES.items()}},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (relations / "aliases.json").write_text(json.dumps({"aliases": {}}), encoding="utf-8")
    return QueryResolver(KnowledgeAdapter(wiki_root=tmp_path))


def _no_llm(*_args, **_kwargs):  # pragma: no cover - 走到这里即失败
    raise AssertionError("确定性路由不应调用 LLM")


@pytest.mark.parametrize(
    "query",
    [
        # uq15-q04 原题与三个改写（route_paraphrase_v1.jsonl）
        "2026-08-14 板块涨幅榜前三是哪几个？光纤光缆板块里亨通光电和长飞光纤当天分别表现如何？",
        "8月14号涨得最多的三个板块是哪些？亨通光电、长飞光纤那天咋样？",
        "亨通光电和长飞光纤在 2026-08-14 各自涨跌如何？当天板块涨幅前三是哪些？",
        "2026-08-14 板块前三，亨通光电 vs 长飞光纤",
    ],
)
def test_q04_seed_and_paraphrases_route_to_one_comparison(resolver: QueryResolver, query: str) -> None:
    resolution = resolver.resolve(query)
    assert resolution.envelope.question_type == "comparison"
    assert resolution.envelope.subject == "亨通光电、长飞光纤"
    assert resolution.envelope.subject_kind == "company"

    decision = decide_turn(query, resolver=resolver, llm_complete=_no_llm)
    assert decision.lane == "research"
    assert decision.question_type == "comparison"
    assert decision.subject == "亨通光电、长飞光纤"


def test_plain_pair_without_any_comparison_word(resolver: QueryResolver) -> None:
    resolution = resolver.resolve("中际旭创和宁德时代最近怎么样")
    assert resolution.envelope.question_type == "comparison"
    assert resolution.envelope.subject == "中际旭创、宁德时代"


@pytest.mark.parametrize(
    ("query", "question_type", "subject"),
    [
        # 单家公司：照旧单股深挖
        ("中际旭创怎么看", "stock_deep_dive", "中际旭创"),
        # 问两家之间的关系：不是比较
        ("亨通光电是长飞光纤的客户吗", "stock_deep_dive", "亨通光电"),
        ("中际旭创有没有给宁德时代供货", "fact_check", "中际旭创"),
    ],
)
def test_single_company_and_relation_questions_unchanged(
    resolver: QueryResolver, query: str, question_type: str, subject: str
) -> None:
    resolution = resolver.resolve(query)
    assert "comparison" not in resolution.envelope.operators
    assert resolution.envelope.question_type == question_type
    assert resolution.envelope.subject == subject


def test_follow_up_comparison_keeps_owner_and_both_entities(resolver: QueryResolver) -> None:
    """A16：追问里横向比两家，owner 继承上一轮；比较对象两家都在（修前只剩高澜股份）。"""
    previous = TurnIntent(
        primary_subject="英维克",
        secondary_topics=("液冷",),
        question_type="stock_deep_dive",
        answer_owner="stock-deep-dive",
        comparison_entities=(),
        inherited_from_turn=None,
    )
    decision = decide_turn(
        "和高澜股份、申菱环境横向比，市场奖励谁、犹豫谁、抛弃谁？",
        resolver=resolver,
        previous_intent=previous,
        previous_turn_id="msg-a15",
        llm_complete=_no_llm,
    )
    assert decision.subject == "英维克"
    assert decision.turn_intent is not None
    assert decision.turn_intent.answer_owner == "stock-deep-dive"
    assert decision.turn_intent.inherited_from_turn == "msg-a15"
    assert decision.turn_intent.comparison_entities == ("高澜股份", "申菱环境")


def test_follow_up_comparison_entities_are_split_not_joined(resolver: QueryResolver) -> None:
    """A04：比较信封主体是「甲、乙」，comparison_entities 必须拆回两个实体。"""
    previous = TurnIntent(
        primary_subject="液冷",
        secondary_topics=(),
        question_type="theme_analysis",
        answer_owner="theme-research",
        comparison_entities=(),
        inherited_from_turn=None,
    )
    decision = decide_turn(
        "强瑞技术和冰轮环境，谁的证据更硬？只按可核验事实比较。",
        resolver=resolver,
        previous_intent=previous,
        previous_turn_id="msg-previous",
        llm_complete=_no_llm,
    )
    assert decision.subject == "液冷"
    assert decision.turn_intent is not None
    assert decision.turn_intent.answer_owner == "theme-research"
    assert decision.turn_intent.comparison_entities == ("强瑞技术", "冰轮环境")
