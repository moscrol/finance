"""口语行情题要被确定性层认成研究，日常用语不能被卷进来（2026-10-01 改写探针 uq15-q07）。

「8月14号稀有金属涨了两个多点，在炒什么？哪些票是代表？」一个书面金融词都不含，此前交给
控制器 LLM；控制器不可用时降级成不检索的普通对话。注入临时知识库的路由探针上，
llm_fallback 2 → 0。
"""

from __future__ import annotations

import pytest

from intelligence.services.turn_controller import decide_turn


def _no_llm(*_args, **_kwargs):
    raise RuntimeError("controller LLM disabled in this test")


def _lane(question: str) -> str:
    return decide_turn(question, llm_complete=_no_llm, previous_intent=None).lane


@pytest.mark.parametrize(
    "question",
    [
        "8月14号稀有金属涨了两个多点，在炒什么？哪些票是代表？",
        "稀有金属 8/14 上涨原因 代表股",
        "储能这几天大涨，龙头股是谁？",
        "光伏为什么跌幅这么大",
        "低空经济概念股有哪些",
    ],
)
def test_colloquial_market_question_is_researched(question: str) -> None:
    assert _lane(question) == "research"


@pytest.mark.parametrize(
    "question",
    ["水龙头坏了怎么修", "我买了张车票", "最近体重上涨了怎么办", "帮我写一首关于秋天的诗", "这个月房租涨了"],
)
def test_everyday_wording_is_not_pulled_into_research(question: str) -> None:
    assert _lane(question) != "research"
