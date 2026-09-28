"""数值条件无出处：标注而非删句（2026-09-28，用户选 A）。

默认模式下，可证伪条件里找不到出处的数不再让整句消失：句子留在公开稿，句内就地
点名「待核」；判决账记 delivery / marked，不进修稿反馈，不把回答压成 partial。
删除语义本身（回滚路径）由 ``numeric_delete_mode`` 夹具下的老测试继续守护。
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from intelligence.services.agent_research import AgentEvidence, evidence_content_hash
from intelligence.services.agent_runtime import OutputEvidenceBinding
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
from intelligence.services.episode_verifier import verify_episode_outcome
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


_PRIOR_SLOT = RequiredOutput(
    "prior_recall", "回顾用户先验", (), required=False, grounding_mode="user_premise",
)


def _memory(detail: str, *, tier: str = "user_memory", title: str = "用户历史判断") -> AgentEvidence:
    item = AgentEvidence(
        tool="memory_lookup", title=title, source="用户记忆，非市场事实",
        detail=detail, evidence_tier=tier, source_date="2026-07-21", io_effect="local_read",
    )
    return replace(item, content_hash=evidence_content_hash(item))


def _with_prior(verified, memory: AgentEvidence | None, *, bound: bool, gap: str = ""):
    """给回答挂上可选先验槽；memory 为 None 时只有槽（与装配层给研究题挂的一样）。"""

    contract = replace(
        verified.contract, allowed_capabilities=("market_data", "memory_lookup"),
        required_outputs=(*verified.contract.required_outputs, _PRIOR_SLOT),
    )
    evidence = verified.outcome.evidence if memory is None else (*verified.outcome.evidence, memory)
    binding = OutputEvidenceBinding(
        "prior_recall", (memory.content_hash,) if bound and memory is not None else (),
        basis="user_premise", gap=gap,
    )
    outcome = replace(
        verified.outcome, evidence=evidence, bindings=(*verified.outcome.bindings, binding),
    )
    return verify_episode_outcome(contract, outcome)


def test_bound_recall_answers_keep_deletion_while_market_answers_are_marked(monkeypatch):
    """#948：复述用户先验的回答里，借用记忆数字的市场判断照删——那里的数不是没出处，
    而是出处不对。同一句话在纯市场回答里只标注。"""

    monkeypatch.setenv("ASK_SEMANTIC_JUDGE", "off")
    condition = "若指数跌破3870点则行情失效。"
    frame, market = _structural(SAFE + "\n" + condition, detail="现金流仍待核实。")
    marked = _verify(frame, market)
    assert condition not in marked.public_answer
    assert "若指数跌破3870点则行情失效（待核：「3870点」未在证据中找到出处）。" in marked.public_answer

    recall = _verify(frame, _with_prior(market, _memory("若指数跌破3870点则暂缓追涨。"), bound=True))
    assert "3870" not in recall.public_answer and "（待核：" not in recall.public_answer
    assert any(
        row["decision"] == "deleted" and VERDICT_REASON_NUMERIC in row["reasons"]
        for row in recall.sentence_verdicts
    )


@pytest.mark.parametrize("judge_mode", ["off", "llm"])
def test_advisory_prior_slot_with_empty_memory_is_still_marked(monkeypatch, judge_mode):
    """2026-09-29 #76 L6 批 4 U1 / 切后 8792 探针的形状：装配层给研究题挂了可选先验槽，
    记忆无命中（缺口条目 + 缺口绑定）。这不是复述先验的回答，无出处的数照常标注。
    此前按「契约挂了槽」划界，这类回答整份退回删除模式，U1 里有出处的条件因此被删。"""

    monkeypatch.setenv("ASK_SEMANTIC_JUDGE", judge_mode)
    frame, market = _structural(DRAFT, detail=DETAIL)
    gap = _memory("status=empty 用户记忆无相关命中；不得编造用户此前的看法。", tier="user_memory_gap", title="用户记忆缺口")
    only_slot = _verify(frame, _with_prior(market, None, bound=False))
    empty = _verify(frame, _with_prior(market, gap, bound=False, gap="用户记忆无相关命中"))

    for result in (only_slot, empty):
        assert f"若成交额跌破1800亿则量能失效{NOTE}。" in result.public_answer
        assert [row["sentence"] for row in _marked(result)] == [UNSUPPORTED]
        assert not any(row["decision"] == "deleted" for row in result.sentence_verdicts)


@pytest.mark.parametrize("judge_mode", ["off", "llm"])
def test_unbound_memory_numbers_and_citations_are_deleted_sentence_by_sentence(monkeypatch, judge_mode):
    """记忆命中了但没绑进先验槽：整份回答照常标注，只有倚靠记忆的条件句照删——
    借了记忆里的数（3,870.50 与 3870.5 是同一个数），或引着记忆证据的编号改写原话。"""

    monkeypatch.setenv("ASK_SEMANTIC_JUDGE", judge_mode)
    borrowed = "若指数跌破3870.5点则行情失效。"
    rewritten = "原文：若指数跌破5000点则暂缓追涨（E2）。"
    frame, market = _structural(f"{SAFE}\n{borrowed}\n{rewritten}\n{UNSUPPORTED}", detail=DETAIL)
    result = _verify(frame, _with_prior(market, _memory("若指数跌破 3,870.50 点，则暂缓追涨。"), bound=False))

    assert "3870" not in result.public_answer and "5000" not in result.public_answer
    assert f"若成交额跌破1800亿则量能失效{NOTE}。" in result.public_answer
    assert SAFE in result.public_answer
    deleted = {row["sentence"] for row in result.sentence_verdicts if row["decision"] == "deleted"}
    assert {borrowed, rewritten} <= deleted
    assert [row["sentence"] for row in _marked(result)] == [UNSUPPORTED]


def test_recall_status_notice_numbers_are_not_user_numbers(monkeypatch):
    """召回状态通知里的条数、字符预算是系统的数，不是用户的：与之撞数的条件照常标注。"""

    monkeypatch.setenv("ASK_SEMANTIC_JUDGE", "off")
    condition = "若连续3日成交额跌破1800亿则量能失效。"
    notice = _memory(
        "status=bounded 用户记忆按每类3条与1800字符预算展示；3条正文已截断，1800条记录已省略；"
        "完整内容保留在原台账；仅作先验，非市场事实。",
        tier="user_memory_gap", title="用户记忆缺口",
    )
    frame, market = _structural(SAFE + "\n" + condition, detail=DETAIL)
    result = _verify(frame, _with_prior(market, notice, bound=False, gap="用户记忆按预算展示"))

    assert "1800" in result.public_answer and "（待核：" in result.public_answer
    assert not any(row["decision"] == "deleted" for row in result.sentence_verdicts)


@pytest.mark.parametrize("judge_mode", ["off", "llm"])
def test_misquoted_user_note_is_still_deleted_not_marked(monkeypatch, judge_mode):
    """#948 的保证在标注模式下不打折：把用户笔记里的 3870 复述成 5000，照删，不留待核版。

    #948 自己的测试按「整句原文不在公开稿」断言删除；标注模式会在句内插说明、改掉原句
    字面，那种断言对「留句 + 标注」是盲的，所以这里按数字断言。
    """

    monkeypatch.setenv("ASK_SEMANTIC_JUDGE", judge_mode)
    frame, baseline = _structural(
        "原文：若指数跌破5000点则暂缓追涨（E2）。当前市场结构仍需验证。若指数跌破3870点则行情失效。"
    )
    memory = AgentEvidence(
        tool="memory_lookup", title="用户历史判断", source="用户记忆，非市场事实",
        detail="若指数跌破3870点则暂缓追涨。", evidence_tier="user_memory",
        source_date="2026-07-21", io_effect="local_read",
    )
    memory = replace(memory, content_hash=evidence_content_hash(memory))
    contract = replace(
        baseline.contract, allowed_capabilities=("market_data", "memory_lookup"),
        required_outputs=(*baseline.contract.required_outputs, RequiredOutput(
            "prior_recall", "回顾用户先验", (), required=False, grounding_mode="user_premise",
        )),
    )
    outcome = replace(
        baseline.outcome, evidence=(*baseline.outcome.evidence, memory),
        bindings=(*baseline.outcome.bindings, OutputEvidenceBinding(
            "prior_recall", (memory.content_hash,), basis="user_premise",
        )),
    )
    result = _verify(frame, verify_episode_outcome(contract, outcome))

    assert "5000" not in result.public_answer
    assert "则行情失效" not in result.public_answer
    assert "（待核：" not in result.public_answer
    assert "当前市场结构仍需验证。" in result.public_answer


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
