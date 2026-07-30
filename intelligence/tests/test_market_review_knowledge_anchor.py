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
    """块非空时必须留下 MAINLINE_KB 引用，否则用户看不到这条腿的来源。"""
    from intelligence.services import ask
    from intelligence.services.ask import AskOptions, answer_query

    monkeypatch.setattr(
        ask,
        "_market_review_knowledge_anchor_block_for_llm",
        lambda *a, **k: "## 主线方向的知识库积累 [MAINLINE_KB]\n- 半导体：概念页 1",
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
    assert "MAINLINE_KB" in {citation.tag for citation in result.citations}


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

    assert "MAINLINE_KB" not in {citation.tag for citation in result.citations}


def test_daily_review_skill_carries_the_knowledge_module(monkeypatch, tmp_path) -> None:
    """日报 skill 拥有工作台里的日常复盘答案，知识库这条腿必须接在这里。

    market_watch 走 workflow 车道，daily-review skill 直接拥有答案，ask 侧的
    _answer_market_review 根本不执行。只把知识库块挂在 ask 侧，用户在工作台里
    一个字都看不到——实测就是这样：引用只有日报 .md，正文零概念页零公司暴露。
    """
    from intelligence.workbench_skills import daily_review as skill_module

    monkeypatch.setattr(
        skill_module,
        "mainline_knowledge_module",
        lambda *a, **k: {
            "module_id": "daily_knowledge_anchor",
            "title": "主线方向的知识库积累",
            "kind": "list",
            "status": "complete",
            "summary": "口径说明",
            "content": None,
            "metrics": [],
            "items": [{"title": "半导体", "summary": "概念页 1（半导体）"}],
        },
    )
    monkeypatch.setattr(
        skill_module,
        "daily_projection_modules",
        lambda *a, **k: ("2026-07-29", [{"module_id": "daily_overview", "title": "今日核心"}], []),
    )

    class _Store:
        def add_artifact(self, *a, **k):
            class _A:
                path = "daily-review-skill-result.json"

            return _A()

    class _Ctx:
        query = "今天大盘处于什么阶段？当前主线是哪几个方向？"
        repo_root = tmp_path
        run_store = _Store()
        run_id = "run_test"

    output = skill_module.DailyReviewSkill().execute(_Ctx())

    module_ids = [str(module.get("module_id")) for module in output.modules]
    assert "daily_knowledge_anchor" in module_ids
    assert any(
        str(citation.get("title")) == "主线方向的知识库积累"
        for citation in output.citations
    )


def test_stale_mainline_summary_is_reported_but_missing_db_is_not(monkeypatch) -> None:
    """主线汇总不同日要说；整个盘面库读不到是另一层的问题，不在这里重复报。"""
    notes: list[str] = []
    monkeypatch.setattr(ask_blocks, "_mainline_theme_names", lambda *a, **k: ("2026-07-24", []))
    ask_blocks.mainline_knowledge_coverage(None, warnings=notes)
    assert any("主线方向汇总与盘面不同日" in note for note in notes)

    notes.clear()
    monkeypatch.setattr(ask_blocks, "_mainline_theme_names", lambda *a, **k: ("", []))
    ask_blocks.mainline_knowledge_coverage(None, warnings=notes)
    assert notes == []


def _run_skill(monkeypatch, tmp_path, *, date_text: str, with_module: bool):
    from intelligence.workbench_skills import daily_review as skill_module

    monkeypatch.setattr(
        skill_module,
        "mainline_knowledge_module",
        lambda *a, **k: (
            {
                "module_id": "daily_knowledge_anchor",
                "title": "主线方向的知识库积累",
                "kind": "list",
                "status": "complete",
                "summary": "口径",
                "content": None,
                "metrics": [],
                "items": [{"title": "半导体", "summary": "概念页 1"}],
            }
            if with_module
            else None
        ),
    )
    monkeypatch.setattr(
        skill_module,
        "daily_projection_modules",
        lambda *a, **k: (
            date_text,
            [
                {
                    "module_id": "daily_overview",
                    "title": "今日核心",
                    "kind": "summary",
                    "status": "complete",
                    "summary": "市场处于底部横盘阶段的第1个交易日",
                    "content": None,
                    "metrics": [],
                    "items": [],
                }
            ],
            [],
        ),
    )

    class _Store:
        def add_artifact(self, *a, **k):
            class _A:
                path = "x.json"

            return _A()

    class _Ctx:
        query = "今天大盘处于什么阶段"
        repo_root = tmp_path
        run_store = _Store()
        run_id = "r"

    return skill_module.DailyReviewSkill().execute(_Ctx())


def test_output_contract_requires_writing_the_knowledge_layer(monkeypatch, tmp_path) -> None:
    """模块进了 contract 但 contract 不要求写它，模型就不写。

    实测：知识库模块和引用都到位，正文里一个概念页都没提——因为 output_contract
    只说了「市场状态、最强数据、主要风险、验证点」。
    """
    output = _run_skill(monkeypatch, tmp_path, date_text="2026-07-29", with_module=True)

    contract = output.answer_contract
    assert contract is not None
    joined = "".join(contract.output_contract)
    assert "知识库" in joined
    assert "概念页" in joined and "公司暴露" in joined
    assert "尚无积累" in joined
    assert "不得互相推导" in joined


def test_output_contract_omits_the_knowledge_clause_when_there_is_no_module(
    monkeypatch, tmp_path
) -> None:
    """没有知识库模块时不能要求模型写它，否则只会逼出编造。"""
    output = _run_skill(monkeypatch, tmp_path, date_text="2026-07-29", with_module=False)

    assert output.answer_contract is not None
    assert "知识库" not in "".join(output.answer_contract.output_contract)


def test_output_contract_demands_the_date_when_data_is_not_from_today(
    monkeypatch, tmp_path
) -> None:
    output = _run_skill(monkeypatch, tmp_path, date_text="2026-07-29", with_module=True)

    first = output.answer_contract.output_contract[0]
    assert "数据截至 2026-07-29" in first
    assert "不得把它称作今天" in first


def test_output_contract_stays_quiet_when_data_is_from_today(monkeypatch, tmp_path) -> None:
    from datetime import date

    output = _run_skill(
        monkeypatch, tmp_path, date_text=date.today().isoformat(), with_module=True
    )

    joined = "".join(output.answer_contract.output_contract)
    assert "不得把它称作今天" not in joined
