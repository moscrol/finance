"""题内先行词：回指的对象就在同一条消息里时，首轮不该整题反问（2026-10-01 路由探针）。

题材不在知识库词表里时 subject / 实体锚都为空，「空芯光纤这个方向：……」（uq15-q10 原题）、
「医疗服务这条产业链能帮我理一下吗」「A股医疗服务有哪些代表公司？它和医疗器械的边界在哪」
（q09 改写）此前全部落 clarify 车道——研究一次都没发生。注入临时知识库的路由探针上，反问
4 → 0、改写一致率 0.711 → 0.800。

真追问仍要反问：首句就带指代、前缀是话头 / 时间词 / 动词短语 / 「的」字结构、前句自己也在
回指（「这段走势」）、或者出现「上次 / 刚才 / 你说的 / 上面」这类显式跨轮标记。
"""

from __future__ import annotations

import pytest

from intelligence.services.turn_controller import _reference_has_in_question_antecedent, decide_turn


def _no_llm(*_args, **_kwargs):
    raise RuntimeError("controller LLM disabled in this test")


def _lane(question: str) -> str:
    return decide_turn(question, llm_complete=_no_llm, previous_intent=None).lane


@pytest.mark.parametrize(
    "question",
    [
        "空芯光纤这个方向：技术优势是什么，产业链上中下游怎么分，国内哪些公司卡位在哪些环节？",
        "医疗服务这条产业链能帮我理一下吗？上中下游是啥，跟医疗器械怎么划界，A股有哪些公司？",
        "A股医疗服务有哪些代表公司？它和医疗器械的边界在哪？上中下游分别是什么？",
        "固态电池这个赛道现在到哪一步了？",
        "低空经济这条链有哪些环节？",
        "那么钠电池这个方向还值得跟踪吗？",
        "光纤光缆行情很猛。这个方向还能持续吗？",
        "人形机器人的减速器环节谁在供货？这条链的瓶颈在哪？",
    ],
)
def test_reference_with_an_antecedent_in_the_same_message_is_researched(question: str) -> None:
    assert _lane(question) != "clarify"


@pytest.mark.parametrize(
    "question",
    [
        "那它的毛利率呢？",
        "这条链呢？",
        "接着上次继续。",
        "这个逻辑呢",
        "这个方向怎么看",
        "这条链有哪些公司",
        "那这个方向呢",
        "现在这条链兑现到哪了",
        "你说的这条链还成立吗？",
        "帮我推一下这个逻辑",
        "刚才那个方向再展开一下。它的风险呢？",
        "怎么看？它还能涨吗",
        "你觉得这个方向怎么样",
        "上面提到的这个逻辑靠谱吗",
        "继续分析这个方向。它的估值呢？",
        "其实这个逻辑我不太信",
    ],
)
def test_true_cross_turn_reference_still_asks(question: str) -> None:
    assert _lane(question) == "clarify"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # 话头词不是先行词；话头后面跟着真名词才是
        ("比如这条链", False),
        ("说实话这个逻辑", False),
        ("不过这个方向我不看好", False),
        ("其实固态电池这个方向我不太信", True),
        ("不过光模块这条链还行", True),
        # 前句自己也在回指，不立题
        ("事后复盘这段走势。它们各自表现如何，与大盘相比呢？", False),
        ("看完这波行情了。这个方向还能追吗？", False),
        # 没有任何指代：本函数不负责放行
        ("光模块景气度如何", False),
    ],
)
def test_antecedent_shapes(text: str, expected: bool) -> None:
    assert _reference_has_in_question_antecedent(text) is expected
