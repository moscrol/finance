"""R3/R4 leftovers: a conclusion with two expiry dates, and a baseline that is never obtained.

Source originals (read-only, quoted verbatim so the regression tests the shipped
shape rather than a paraphrase):
``~/.finance-runtime/reviews/8792-boundary-retest-20260918/cases/{f1-opt-out,
positive-persistence}/artifacts/answer.md``.

These are offline text/structure checks. They do not certify financial
correctness, replay an Episode, call a model, or re-judge the sealed 0/4 live
results. Different conclusions are allowed to carry different review deadlines —
only a single conclusion restated with a conflicting expiry is a defect.
"""
from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest

from intelligence.services.agent_research import AgentEvidence, StructuredObservation
from intelligence.services.track_contract import contract_receipt, parse_valid_until

QUERY = "跟踪中际旭创的利润增长与回款兑现，并安排复查。"
BASE = "无上期基线，本期建立基线。\n"

# F1 原件第 9–10 行：声明的复核期限是用户指定复查日 2026-10-22，
# 同一条结论的尾句又按默认 30 天写成 2026-10-17。
F1_DECLARED = "**复核期限：2026-10-22**（用户指定的复查日，非公司披露承诺日）。"
F1_WATCH = (
    "**下期关注清单（仅一条）**：事项=2026年三季报（截至2026-09-30）经营活动现金流量净额及其累计净现比；"
    "时间节点=按创业板三季报法定披露窗口内公司实际披露日（不晚于2026-10-31），并于2026-10-22核查披露进度；"
    "若累计净现比显著回升（如回到2025年报1.009的水平附近及以上），则回落为“支持/无变化”。"
    "本结论30天内（至2026-10-17）未复核即视为待复核。本次研究不登记为长期跟踪。"
)
F1 = BASE + F1_DECLARED + "\n" + F1_WATCH

WATCH = "下期关注：指标=经营现金流；时间节点=2026-10-22；触发条件=若回款继续恶化，则削弱判断。"

# 阳性原件：两期经营现金流均未取得、净现比不可算，触发条件却要比「两期中较低值」。
POSITIVE_FACTS = (
    "经营现金流净额两期均未取得（计算编号916a234093beb69b，缺值未补数），净现比不可算，"
    "故「支持/削弱/无变化」均不成立。"
)
POSITIVE_WATCH = (
    "下期关注：指标/事件=2026年三季报累计经营活动现金流净额及净现比；时间节点=复查日2026-10-22前实际披露时；"
    "触发条件（可证伪）=若三季报经营现金流净额为正且与归母净利同向增长、净现比可计算且不低于两期中较低值，"
    "则升级为「支持经营质量改善」；若为负或显著低于净利润，则降级为「削弱」"
)


def _evidence(periods: dict[str, dict[str, float]]) -> tuple[AgentEvidence, ...]:
    """结构化财务证据；只放实际取到的指标，不给缺失项造占位值。"""
    return tuple(
        AgentEvidence(
            "financial_data",
            f"300308 {period}",
            f"{period} 结构化财报读数。",
            "结构化财报",
            source_date="2026-08-22",
            content_hash=f"financial-{period}",
            observations=tuple(
                StructuredObservation("300308.SZ", period, metric, value)
                for metric, value in metrics.items()
            ),
        )
        for period, metrics in periods.items()
    )


BOTH_METRICS = {
    "2025-12-31": {"ocf_cum_yi": 108.96, "net_profit_cum_yi": 107.97},
    "2026-06-30": {"ocf_cum_yi": 18.0, "net_profit_cum_yi": 136.51},
}
PROFIT_ONLY = {
    "2025-12-31": {"net_profit_cum_yi": 107.97},
    "2026-06-30": {"net_profit_cum_yi": 136.51},
}


# —— 形状 A：同一条结论被标注了两个互相矛盾的有效期 ——


def test_restated_conclusion_ttl_conflicting_with_the_declared_one_is_reported():
    from intelligence.services.track_contract import conclusion_ttl_conflicts

    conflicts = conclusion_ttl_conflicts(F1)
    assert len(conflicts) == 1
    assert "2026-10-17" in conflicts[0] and "2026-10-22" in conflicts[0]
    # 声明值本身不被改写：修的是「没人查冲突」，不是把首个匹配换一个日期。
    assert parse_valid_until(F1) == "2026-10-22"


def test_conflicting_ttl_reaches_the_machine_readable_receipt():
    receipt = contract_receipt(F1, query=QUERY, as_of="2026-09-18")
    assert receipt["valid_until"] == "2026-10-22"
    assert receipt["ttl_status"] == "current"
    assert receipt["ttl_conflicts"] == [
        "结论有效期自相矛盾：正文声明「复核期限：2026-10-22」，同一条结论又写明至 2026-10-17 未复核即视为待复核"
    ]


@pytest.mark.parametrize("answer", [
    # 契约本来就允许每条结论各标有效期（跟踪级 30 天 / 框架级 90 天），不能逼它们一致。
    BASE + "结论一：产能爬坡。复核期限：2026-10-17。\n结论二：行业格局。复核期限：2026-12-17。\n" + WATCH,
    # 重述与声明一致。
    BASE + "复核期限：2026-10-22。本结论30天内（至2026-10-22）未复核即视为待复核。\n" + WATCH,
    # 披露截止日、复查进度日都不是结论有效期。
    BASE + "复核期限：2026-10-22。披露截止不晚于2026-10-31，并于2026-10-22核查披露进度。\n" + WATCH,
    # 只有重述、没有声明：那是缺 TTL，由 missing_contract_elements 报，不算冲突。
    BASE + "本结论30天内（至2026-10-17）未复核即视为待复核。\n" + WATCH,
    BASE + WATCH,
    "",
])
def test_legitimate_dates_are_not_forced_to_agree(answer):
    from intelligence.services.track_contract import conclusion_ttl_conflicts

    assert conclusion_ttl_conflicts(answer) == ()


def test_non_track_answers_do_not_carry_a_conflict_field():
    receipt = contract_receipt(F1, query="今天上证收盘多少点？", question_type="quick_fact")
    assert receipt["track_intent"] is False
    assert receipt["ttl_conflicts"] == []


# —— 形状 B：触发条件依赖一个本轮根本没有取到的比较基线 ——


def test_condition_on_a_baseline_the_answer_never_obtained_is_a_gap():
    from intelligence.services.financial_claim_checks import comparison_baseline_gaps

    evidence = _evidence(PROFIT_ONLY)
    rows = [{"index": 4, "text": POSITIVE_FACTS}, {"index": 5, "text": POSITIVE_WATCH}]
    gaps = comparison_baseline_gaps(
        rows, evidence, [item.content_hash for item in evidence], subject="300308",
    )
    assert len(gaps) == 1
    assert "两期中较低值" in gaps[0] and "净现比" in gaps[0]


def test_same_condition_is_accepted_once_both_periods_are_bound():
    from intelligence.services.financial_claim_checks import comparison_baseline_gaps

    evidence = _evidence(BOTH_METRICS)
    rows = [{"index": 5, "text": POSITIVE_WATCH}]
    assert comparison_baseline_gaps(
        rows, evidence, [item.content_hash for item in evidence], subject="300308",
    ) == ()


@pytest.mark.parametrize("half", ["ocf_cum_yi", "net_profit_cum_yi"])
def test_half_of_the_ratio_inputs_is_still_no_baseline(half):
    """净现比要两个输入；只拿到其中一个，基准依旧算不出来。"""
    from intelligence.services.financial_claim_checks import comparison_baseline_gaps

    evidence = _evidence({
        period: {half: metrics[half]} for period, metrics in BOTH_METRICS.items()
    })
    rows = [{"index": 5, "text": POSITIVE_WATCH}]
    assert len(comparison_baseline_gaps(
        rows, evidence, [item.content_hash for item in evidence], subject="300308",
    )) == 1


@pytest.mark.parametrize("text", [
    # F1 的条件自带基线值 1.009——数值是否有证据支持归既有数量门，不在本检查。
    "若累计净现比显著回升（如回到2025年报1.009的水平附近及以上），则回落为“支持/无变化”。",
    # 写出了具体数值的比较：同样归数量支持门，本检查不重复管。
    "若三季报净现比不低于上期0.5的水平，则升级为「支持」。",
    # 单期同比、无历史基线引用。
    "若三季报经营现金流净额为正且与归母净利同向增长，则升级为「支持」。",
    # 定性表述，不含比较基线。
    "若回款继续恶化，则削弱判断。",
])
def test_conditions_without_a_relative_baseline_are_not_flagged(text):
    from intelligence.services.financial_claim_checks import comparison_baseline_gaps

    evidence = _evidence(PROFIT_ONLY)
    assert comparison_baseline_gaps(
        [{"index": 1, "text": text}], evidence, [item.content_hash for item in evidence],
        subject="300308",
    ) == ()


# —— 接线：检查得真的被生产路径调用，否则只是一段没人读的代码 ——


def _context(**contract_fields):
    fields = {"question": QUERY, "question_type": "financial_analysis",
              "required_outputs": (), "material_contract": None, "subject_kind": "company"}
    return SimpleNamespace(contract=SimpleNamespace(**{**fields, **contract_fields}), today="2026-09-18")


def test_conflicting_ttl_is_disclosed_rather_than_silently_accepted():
    from intelligence.runtime.continuous_turn_adapter import _track_public_delivery

    answer, notices, receipt = _track_public_delivery(F1, _context())
    # 契约元素一个不缺，缺件检查看不见这条矛盾——所以它必须走披露，而不是被放过。
    assert receipt["missing_outputs"] == []
    assert answer == F1, "只披露，不替用户挑日期、不改写正文"
    assert len(notices) == 1
    assert "2026-10-17" in notices[0] and "2026-10-22" in notices[0]


def test_a_consistent_answer_gets_no_extra_notice():
    from intelligence.runtime.continuous_turn_adapter import _track_public_delivery

    clean = BASE + "复核期限：2026-10-22。本结论30天内（至2026-10-22）未复核即视为待复核。\n" + WATCH
    answer, notices, _ = _track_public_delivery(clean, _context())
    assert (answer, notices) == (clean, ())


def _verified(draft, *, keep_ocf):
    from intelligence.tests.test_financial_r6_regressions import _financial

    _, verified = _financial(draft)
    if keep_ocf:
        return verified
    outcome = replace(verified.outcome, evidence=tuple(
        replace(item, observations=tuple(
            obs for obs in item.observations if obs.metric != "ocf_cum_yi"
        ))
        for item in verified.outcome.evidence
    ))
    return replace(verified, outcome=outcome)


@pytest.mark.parametrize("keep_ocf,unsupported", [(True, False), (False, True)])
def test_missing_baseline_reaches_the_verifier_gate(keep_ocf, unsupported):
    from intelligence.services.episode_semantic_verifier import comparison_baseline_unsupported

    verified = _verified(POSITIVE_WATCH, keep_ocf=keep_ocf)
    assert comparison_baseline_unsupported(verified) is unsupported
    # 非财务题不借这条路做通用文本判断。
    other = replace(verified, contract=replace(verified.contract, question_type="quick_fact"))
    assert comparison_baseline_unsupported(other) is False


def test_missing_baseline_asks_for_the_number_instead_of_deleting_the_sentence():
    from intelligence.runtime.continuous_turn_adapter import _issue_backfill_plan

    verified = _verified(POSITIVE_WATCH, keep_ocf=False)
    plan = _issue_backfill_plan(verified, _context())
    assert plan is not None and plan.missing_capabilities == ("finance_query",)
    assert verified.outcome.draft == POSITIVE_WATCH, "补数路径不动正文"
    assert _issue_backfill_plan(_verified(POSITIVE_WATCH, keep_ocf=True), _context()) is None


def test_unbound_or_missing_financial_evidence_is_not_guessed():
    from intelligence.services.financial_claim_checks import comparison_baseline_gaps

    evidence = _evidence(PROFIT_ONLY)
    rows = [{"index": 5, "text": POSITIVE_WATCH}]
    # 一条都没绑定：本检查无从判断，交给绑定/证据门，不在这里臆断。
    assert comparison_baseline_gaps(rows, evidence, (), subject="300308") == ()
    assert comparison_baseline_gaps(rows, (), (), subject="300308") == ()
    # 别家公司的读数不能用来证明本公司的基线存在。
    peer = _evidence({"2025-12-31": {"ocf_cum_yi": 1.0, "net_profit_cum_yi": 1.0}})
    peer = tuple(
        AgentEvidence(
            item.tool, item.title, item.detail, item.source,
            source_date=item.source_date, content_hash="peer",
            observations=tuple(
                StructuredObservation("000001.SZ", obs.as_of, obs.metric, obs.value)
                for obs in item.observations
            ),
        )
        for item in peer
    )
    assert len(comparison_baseline_gaps(
        rows, (*evidence, *peer), [item.content_hash for item in (*evidence, *peer)],
        subject="300308",
    )) == 1
