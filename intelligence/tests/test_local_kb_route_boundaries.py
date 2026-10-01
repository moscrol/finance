"""真实词表探针发现的日期/市场前缀边界，以独立词表锁定路由，不调用模型。"""

import json

import pytest

from intelligence.adapters.knowledge import KnowledgeAdapter
from intelligence.services.query_resolution import QueryResolver
from intelligence.services.query_understanding import has_clean_theme_occurrence, is_market_watch_query
from intelligence.services.turn_controller import decide_turn


@pytest.fixture()
def resolver(tmp_path):
    relations = tmp_path / "relations"
    relations.mkdir()
    entities = {"样本公司": {"concepts": {name: {} for name in ("稀有金属", "医疗服务", "医疗器械", "新能源")}}}
    (relations / "entity_exposures.json").write_text(json.dumps({"entities": entities}, ensure_ascii=False))
    (relations / "aliases.json").write_text(json.dumps({"aliases": {}}))
    return QueryResolver(KnowledgeAdapter(wiki_root=tmp_path))


def _no_llm(*_args, **_kwargs):
    raise AssertionError("these deterministic routes must not call a model")


@pytest.mark.parametrize(
    ("question", "subject"),
    [
        ("8月14号稀有金属涨了两个多点，在炒什么？哪些票是代表？", "稀有金属"),
        ("9月20日稀有金属的投资逻辑是什么？", "稀有金属"),
        ("A股医疗服务有哪些代表公司？它和医疗器械的边界在哪？上中下游分别是什么？", "医疗服务"),
    ],
)
def test_theme_after_date_or_market_prefix_keeps_its_subject(resolver, question, subject):
    decision = decide_turn(question, resolver=resolver, llm_complete=_no_llm, previous_intent=None)
    assert (decision.lane, decision.question_type, decision.subject) == ("research", "theme_analysis", subject)
    assert decision.needs_retrieval
    assert not decision.llm_failure_reason


@pytest.mark.parametrize("company", ["立新能源", "国新能源", "华润新能源", "宝新能源"])
def test_date_prefix_does_not_split_a_company_suffix(company):
    assert not has_clean_theme_occurrence(f"8月14号{company}怎么看", "新能源")


@pytest.mark.parametrize("query", ["今日大盘 成交额", "今天两市成交额", "今日A股成交量"])
def test_terse_today_market_summary(query):
    decision = decide_turn(query, llm_complete=_no_llm, previous_intent=None)
    assert (decision.lane, decision.question_type) == ("workflow", "market_watch")


@pytest.mark.parametrize("query", ["今日光伏成交额", "2026-08-14 大盘成交额", "跟我随便聊聊大盘呗", "今天亨通光电成交额"])
def test_terse_market_route_stays_within_its_scope(query):
    assert not is_market_watch_query(query)
