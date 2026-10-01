"""金融问题不该掉进不检索的车道（2026-10-01 无检索车道排查，57 题电池）。

上一轮「分析题被当定义题」是撞见的；这一轮把 57 道覆盖公司 / 题材 / 市场宏观 / 口语 / 知识
的问题统一过 decide_turn，找落进 chat 或 knowledge+needs_retrieval=False 的。修前 11 道
非正常（5 道是合理的知识题），修后 6 道（5 道知识题 + 「茅台咋样」依赖真实知识库别名）。

修的形状：
- 「两融余额创新高意味着什么」「现在适合加仓吗」：词表没有两融 / 北向 / 加仓 / A股 这类词，
  交控制器 LLM，不可用时降级成不检索的普通对话。
- 「帮我看看光纤光缆」：知识库独有的题材被「看看X」当成公司名 → stock_deep_dive；
  「看看立新能源为什么涨停」主体被贪婪捕获成「立新能源为什么涨停」，下游查不到实体；
  「研究一下蓝思科技」带「一下」整句放弃。
- 「什么叫戴维斯双击」「市净率怎么计算」：定义问法没收，落闲聊车道。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from intelligence.adapters.knowledge import KnowledgeAdapter
from intelligence.services.query_resolution import QueryResolver
from intelligence.services.turn_controller import decide_turn

_THEMES = ["光纤光缆", "光模块", "储能"]


def _no_llm(*_args, **_kwargs):
    raise RuntimeError("controller LLM disabled in this test")


@pytest.fixture()
def resolver(tmp_path: Path) -> QueryResolver:
    relations = tmp_path / "relations"
    relations.mkdir()
    entities = {"亨通光电": {"codes": ["600487.SH"], "concepts": {theme: {} for theme in _THEMES}}}
    (relations / "entity_exposures.json").write_text(json.dumps({"entities": entities}, ensure_ascii=False))
    (relations / "aliases.json").write_text(json.dumps({"aliases": {}}))
    return QueryResolver(KnowledgeAdapter(wiki_root=tmp_path))


def _decide(question: str, resolver: QueryResolver | None = None):
    return decide_turn(question, resolver=resolver, llm_complete=_no_llm, previous_intent=None)


@pytest.mark.parametrize(
    "question",
    ["两融余额创新高意味着什么", "现在适合加仓吗", "今年A股的主线是什么", "北向资金最近在买什么", "美股今晚怎么走"],
)
def test_market_questions_do_not_fall_into_no_retrieval_chat(question: str) -> None:
    decision = _decide(question)
    assert decision.lane == "research"


@pytest.mark.parametrize(
    ("question", "question_type", "subject"),
    [
        ("帮我看看光纤光缆", "theme_analysis", "光纤光缆"),
        ("看看光纤光缆为什么大涨", "market_cause", "光纤光缆"),
        ("看看光模块龙头", "theme_analysis", "光模块"),
        ("帮我分析一下储能", "theme_analysis", "储能"),
        ("看看立新能源为什么涨停", "stock_deep_dive", "立新能源"),
        ("研究一下蓝思科技", "stock_deep_dive", "蓝思科技"),
        ("帮我深挖一下中天科技", "stock_deep_dive", "中天科技"),
        ("帮我看看亨通光电", "stock_deep_dive", "亨通光电"),
    ],
)
def test_look_at_x_subject(resolver: QueryResolver, question: str, question_type: str, subject: str) -> None:
    envelope = resolver.resolve(question).envelope
    assert (envelope.question_type, envelope.subject) == (question_type, subject)


@pytest.mark.parametrize("question", ["什么叫戴维斯双击", "市净率怎么计算", "什么是市盈率", "ROE 是什么意思"])
def test_definition_questions_land_in_knowledge(question: str) -> None:
    decision = _decide(question)
    assert (decision.lane, decision.question_type) == ("knowledge", "concept_definition")


@pytest.mark.parametrize("question", ["这道数学题怎么计算", "你好", "帮我写一首关于秋天的诗", "人民币怎么换美元"])
def test_everyday_wording_stays_out_of_research(question: str) -> None:
    decision = _decide(question)
    assert decision.lane != "research"
    assert decision.question_type != "concept_definition"
