"""日常复盘要两条腿：盘面说哪个方向在走，知识库说我对它研究到什么程度。

修完意图识别后，2026-07-30 端到端实测的复盘答案 2 条引用全是本地日报，知识图谱
0 概念 0 公司暴露——盘面那条腿修好了，知识库那条腿从来没接上。用户的原话是
「一个是盘面数据，一个是知识库的数据」。

按主线方向逐个取锚，不是把整句问题当题材名去匹配：市场级问题里根本没有题材名，
match_candidate 在这类问题上必然落空（那正是「当日盘面候选未命中」的来历）。
"""
from __future__ import annotations

import pytest

from intelligence.services import ask_blocks


class _FakeKnowledge:
    def __init__(self, coverage: dict[str, dict[str, list[dict]]]) -> None:
        self._coverage = coverage

    def _items(self, kind: str, theme: str) -> dict:
        return {"items": self._coverage.get(theme, {}).get(kind, []), "warnings": []}

    def get_concept_matches(self, theme: str, limit: int = 3) -> dict:
        return self._items("concepts", theme)

    def get_exposure_matches(self, theme: str, limit: int = 4) -> dict:
        return self._items("exposures", theme)

    def get_evidence(self, theme: str, limit: int = 3) -> dict:
        return self._items("evidence", theme)


@pytest.fixture
def patched(monkeypatch):
    def _apply(directions: list[str], coverage: dict) -> None:
        monkeypatch.setattr(
            ask_blocks,
            "_mainline_theme_names",
            lambda *a, **k: ("2026-07-29", directions),
        )
        import intelligence.adapters.knowledge as knowledge_module

        monkeypatch.setattr(
            knowledge_module,
            "KnowledgeAdapter",
            lambda **kwargs: _FakeKnowledge(coverage),
        )

    return _apply


def test_covered_direction_reports_concepts_exposures_and_evidence(patched) -> None:
    patched(
        ["半导体"],
        {
            "半导体": {
                "concepts": [{"concept": "半导体"}, {"concept": "功率半导体"}],
                "exposures": [{"company": "中微公司", "role": "前道关键设备供应商"}],
                "evidence": [{"title": "某券商深度"}],
            }
        },
    )

    block = ask_blocks._market_review_knowledge_anchor_block_for_llm(None)

    assert "半导体：" in block
    assert "概念页 2（半导体、功率半导体）" in block
    assert "中微公司（前道关键设备供应商）" in block
    assert "已入库证据 1 条" in block


def test_direction_with_no_coverage_is_named_as_a_research_gap(patched) -> None:
    """盘面已进主线、库里一条都没有——这是当天最该补研究的方向，必须说出来。"""
    patched(
        ["半导体", "电力"],
        {"半导体": {"concepts": [{"concept": "半导体"}], "exposures": [], "evidence": []}},
    )

    block = ask_blocks._market_review_knowledge_anchor_block_for_llm(None)

    assert "知识库尚无积累的主线方向：电力" in block
    assert "最该补研究" in block
    # 有积累的方向不能被误列进缺口。
    assert "知识库尚无积累的主线方向：电力（" in block


def test_no_mainline_directions_yields_no_block(patched) -> None:
    """没有同日主线汇总时不编造一个空块出来。"""
    patched([], {})

    assert ask_blocks._market_review_knowledge_anchor_block_for_llm(None) == ""


def test_block_states_the_two_legs_are_separate(patched) -> None:
    """知识库有积累 ≠ 当日盘面强；两者不能互相推导。"""
    patched(["半导体"], {"半导体": {"concepts": [{"concept": "半导体"}], "exposures": [], "evidence": []}})

    block = ask_blocks._market_review_knowledge_anchor_block_for_llm(None)

    assert "知识库有积累不等于当日盘面强" in block
    assert "盘面强也不等于库内有依据" in block
    assert "不得把 graph_only" in block


def test_market_review_answer_carries_the_knowledge_citation(monkeypatch) -> None:
    """块非空时必须留下 D5 引用，否则用户看不到这条腿的来源。"""
    from intelligence.services import ask
    from intelligence.services.ask import AskOptions, answer_query

    monkeypatch.setattr(
        ask,
        "_market_review_knowledge_anchor_block_for_llm",
        lambda *a, **k: "## 主线方向的知识库积累 [D5]\n- 半导体：概念页 1",
    )

    result = answer_query(
        AskOptions(
            query="今天大盘处于什么阶段？当前主线是哪几个方向？",
            compose=False,
            synthesize=False,
        )
    )

    assert result.question_plan is not None
    assert result.question_plan.question_type == "market_review"
    assert "D5" in {citation.tag for citation in result.citations}


def test_no_knowledge_citation_when_the_block_is_empty(monkeypatch) -> None:
    """块为空就不能留引用——引用必须对应真的看过的东西。"""
    from intelligence.services import ask
    from intelligence.services.ask import AskOptions, answer_query

    monkeypatch.setattr(
        ask,
        "_market_review_knowledge_anchor_block_for_llm",
        lambda *a, **k: "",
    )

    result = answer_query(
        AskOptions(
            query="今天大盘处于什么阶段？当前主线是哪几个方向？",
            compose=False,
            synthesize=False,
        )
    )

    assert "D5" not in {citation.tag for citation in result.citations}
