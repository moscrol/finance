"""数值条件无出处：标注而非删句（2026-09-28，用户选 A）。

默认模式下，可证伪条件里找不到出处的数不再让整句消失：句子留在公开稿，句内就地
点名「待核」；判决账记 delivery / marked，不进修稿反馈，不把回答压成 partial。
删除语义本身（回滚路径）由 ``numeric_delete_mode`` 夹具下的老测试继续守护。
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from intelligence.services.answer_model import JUDGE_REASON_FACT_BEYOND_EVIDENCE
from intelligence.services.episode_semantic_verifier import (
    _NUMERIC_CONDITION_ISSUE,
    NUMERIC_CONDITION_MARK_ENV,
    VERDICT_MARKED,
    VERDICT_REASON_JUDGE,
    VERDICT_REASON_NUMERIC,
    VERDICT_STAGE_DELIVERY,
    SemanticEpisodeVerifier,
    _with_numeric_doubt_note,
    numeric_condition_unsupported,
    numeric_doubt_note,
    recheck_material_public_delivery,
    semantic_repair_feedback,
    with_unresolved_review_publication,
)
from intelligence.services.research_contract import RequiredOutput, ResearchDeadline
from intelligence.services.research_harness import PublicationAssessment
from intelligence.tests.test_boundary_retest_regressions import BAD_CONDITIONS, SAFE
from intelligence.tests.test_episode_semantic_verifier import _judge, _structural

SUPPORTED = "若净现比低于0.2则下调判断。"
UNSUPPORTED = "若成交额跌破1800亿则量能失效。"
DRAFT = f"{SAFE}\n{SUPPORTED}\n{UNSUPPORTED}"
DETAIL = "现金流观察基准0.2。"
NOTE = numeric_doubt_note(("1800亿",))


def _verify(frame, verified, judge=None):
    return SemanticEpisodeVerifier(judge_fn=judge or _judge(True)).verify(
        frame=frame, structurally_verified=verified, deadline=ResearchDeadline.from_timeout(5),
    )


def _marked(result):
    return [row for row in result.sentence_verdicts if row["decision"] == VERDICT_MARKED]


@pytest.mark.parametrize("mode", ["off", "llm"])
def test_unsupported_condition_stays_and_names_the_number(monkeypatch, mode):
    monkeypatch.setenv("ASK_SEMANTIC_JUDGE", mode)
    frame, verified = _structural(DRAFT, detail=DETAIL)
    # 补证照旧先去取这个数：标注是终局处置，不取消 W5 的取数机会。
    assert numeric_condition_unsupported(verified)

    result = _verify(frame, verified)

    assert NOTE == "（待核：「1800亿」未在证据中找到出处）"
    assert f"若成交额跌破1800亿则量能失效{NOTE}。" in result.public_answer
    assert SUPPORTED in result.public_answer and SAFE in result.public_answer
    assert result.public_answer.count("（待核：") == 1
    assert result.status == "completed"
    assert [
        (row["stage"], row["sentence"], row["reasons"]) for row in _marked(result)
    ] == [(VERDICT_STAGE_DELIVERY, UNSUPPORTED, [VERDICT_REASON_NUMERIC])]
    assert not any(row["decision"] == "deleted" for row in result.sentence_verdicts)
    assert _NUMERIC_CONDITION_ISSUE.serialize() in result.issues
    # 标注不是拒句：不驱动修稿轮，也不给整份回答盖「未完成修订」。
    assert semantic_repair_feedback(result) == ()
    assert with_unresolved_review_publication(PublicationAssessment(), result).max_status == "completed"
    # 草稿真值句不改，只改公开稿。
    assert UNSUPPORTED in result.verified.outcome.draft


@pytest.mark.parametrize("mode", ["off", "llm"])
@pytest.mark.parametrize("condition", BAD_CONDITIONS)
def test_same_unsupported_condition_is_marked_across_layouts(monkeypatch, mode, condition):
    """删除模式的孪生（test_same_unsupported_condition_is_removed_across_layouts）：
    同一批排版，标注模式下句子全在、说明落在句内、表格行不被拆。"""

    monkeypatch.setenv("ASK_SEMANTIC_JUDGE", mode)
    frame, verified = _structural(SAFE + "\n" + condition, detail="现金流仍待核实。")
    result = _verify(frame, verified)

    marked = _marked(result)
    assert marked and all(
        row["stage"] == VERDICT_STAGE_DELIVERY and row["reasons"] == [VERDICT_REASON_NUMERIC]
        for row in marked
    )
    assert not any(row["decision"] == "deleted" for row in result.sentence_verdicts)
    assert result.public_answer.count("未在证据中找到出处）") == len(marked)
    assert SAFE in result.public_answer
    assert any(number in result.public_answer for number in ("50%", "20%", "0.5", "0.2", "80"))
    for line in result.public_answer.splitlines():
        if line.startswith("|"):
            assert line.endswith("|"), line


def test_recall_answers_keep_deletion_while_market_answers_are_marked(monkeypatch):
    """#948：复述用户先验的回答里，借用记忆数字的市场判断照删——那里的数不是没出处，
    而是出处不对。同一句话在纯市场回答里只标注。"""

    monkeypatch.setenv("ASK_SEMANTIC_JUDGE", "off")
    condition = "若指数跌破3870点则行情失效。"
    frame, market = _structural(SAFE + "\n" + condition, detail="现金流仍待核实。")
    marked = _verify(frame, market)
    assert condition not in marked.public_answer
    assert "若指数跌破3870点则行情失效（待核：「3870点」未在证据中找到出处）。" in marked.public_answer

    recall_contract = replace(market.contract, required_outputs=(
        *market.contract.required_outputs,
        RequiredOutput("prior_recall", "回顾用户先验", (), required=False, grounding_mode="user_premise"),
    ))
    recall = _verify(frame, replace(market, contract=recall_contract))
    assert "3870" not in recall.public_answer and "（待核：" not in recall.public_answer
    assert any(
        row["decision"] == "deleted" and VERDICT_REASON_NUMERIC in row["reasons"]
        for row in recall.sentence_verdicts
    )


@pytest.mark.parametrize("value", ["0", "off", "false"])
def test_rollback_env_restores_whole_sentence_deletion(monkeypatch, value):
    monkeypatch.setenv("ASK_SEMANTIC_JUDGE", "off")
    monkeypatch.setenv(NUMERIC_CONDITION_MARK_ENV, value)
    frame, verified = _structural(DRAFT, detail=DETAIL)
    result = _verify(frame, verified)
    assert "1800" not in result.public_answer and "（待核：" not in result.public_answer
    assert SUPPORTED in result.public_answer
    assert not _marked(result)


def _rejecting_judge(code: str | None):
    """首判拒第 3 句（可带理由码），之后复判放行。"""

    calls: list[dict[str, object]] = []

    def run(request):
        calls.append(request)
        if len(calls) > 1:
            return {"passed": True, "rejected_sentence_indexes": [], "issues": []}
        report = {"passed": False, "rejected_sentence_indexes": [3], "issues": ["第3句与证据不符"]}
        if code:
            report["reason_codes"] = [{"sentence_index": 3, "code": code}]
        return report

    return run


def test_judge_fact_rejection_of_a_flagged_sentence_deletes_it_as_the_judge():
    """数值门不再是机械删句：判官以「事实超出证据」拒掉的句子照删，理由记判官。"""

    frame, verified = _structural(DRAFT, detail=DETAIL)
    result = _verify(frame, verified, _rejecting_judge(JUDGE_REASON_FACT_BEYOND_EVIDENCE))

    assert "1800" not in result.public_answer
    rows = [row for row in result.sentence_verdicts if row["sentence"] == UNSUPPORTED]
    assert [(row["decision"], row["reasons"]) for row in rows] == [("deleted", [VERDICT_REASON_JUDGE])]
    assert not _marked(result)


def test_uncoded_judge_rejection_in_required_block_is_demoted_and_still_marked():
    """无码的语义拒句在必答槽内按 V8 降级保留；数字仍无出处，于是同时被点名待核。
    删除模式下数值门会把这句归成机械删句——标注模式不再替判官加码。"""

    frame, verified = _structural(DRAFT, detail=DETAIL)
    result = _verify(frame, verified, _rejecting_judge(None))

    assert f"若成交额跌破1800亿则量能失效{NOTE}。" in result.public_answer
    rows = [row for row in result.sentence_verdicts if row["sentence"] == UNSUPPORTED]
    assert sorted((row["stage"], row["decision"], tuple(row["reasons"])) for row in rows) == [
        (VERDICT_STAGE_DELIVERY, VERDICT_MARKED, (VERDICT_REASON_NUMERIC,)),
        ("judge", "demoted_to_issue", (VERDICT_REASON_JUDGE,)),
    ]


@pytest.mark.parametrize(("sentence", "expected"), [
    ("若A跌破1800亿则失效。", "若A跌破1800亿则失效{note}。"),
    ("若A跌破1800亿则失效；", "若A跌破1800亿则失效{note}；"),
    ("**若A跌破1800亿则失效。**", "**若A跌破1800亿则失效{note}。**"),
    ("“若A跌破1800亿则失效。”", "“若A跌破1800亿则失效{note}。”"),
    ("若A跌破1800亿则失效（E1）。", "若A跌破1800亿则失效（E1）{note}。"),
    ("| 回款 | 净现比≥0.5 | 改善 |", "| 回款 | 净现比≥0.5 | 改善{note} |"),
    ("- 净现比≥0.5", "- 净现比≥0.5{note}"),
    ("若A跌破1800亿则失效。\n", "若A跌破1800亿则失效{note}。\n"),
])
def test_note_is_placed_inside_its_own_sentence(sentence, expected):
    assert _with_numeric_doubt_note(sentence, NOTE) == expected.format(note=NOTE)


def test_note_names_each_number_once():
    assert numeric_doubt_note(("1800亿", "31 日", "1800亿")) == "（待核：「1800亿」、「31 日」未在证据中找到出处）"


def test_marking_is_idempotent_and_survives_delivery_recheck(monkeypatch):
    monkeypatch.setenv("ASK_SEMANTIC_JUDGE", "off")
    frame, verified = _structural(DRAFT, detail=DETAIL)
    verifier = SemanticEpisodeVerifier(judge_fn=_judge(True))
    result = verifier.verify(
        frame=frame, structurally_verified=verified, deadline=ResearchDeadline.from_timeout(5),
    )

    again = verifier._mark_numeric_condition_doubts(result)
    assert again.public_answer == result.public_answer
    assert recheck_material_public_delivery(result).public_answer == result.public_answer
