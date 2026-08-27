"""KC-07：召回自评四问——装配完只披露缺口，不补搜。"""
from __future__ import annotations

from datetime import date

from intelligence.services.recall_audit import (
    GAP_FEW_SOURCES,
    GAP_NO_CHAIN,
    GAP_NO_COUNTER,
    GAP_NO_FRESH,
    GAP_NO_SUPPORT,
    audit_recall,
)

AS_OF = date(2026, 8, 18)


def _line(text: str, source: str, day: str, *, counter: bool = False) -> str:
    mark = "[反] " if counter else ""
    return f"{mark}{text}（{source}, {day}, 质量 high） [R1]"


def test_counter_question_reports_zero_when_only_support() -> None:
    audit = audit_recall(
        [
            _line("营收增长", "年报", "2026-08-01"),
            _line("订单饱满", "公告", "2026-08-10"),
            _line("扩产落地", "研报", "2026-08-12"),
        ],
        as_of=AS_OF,
    )
    assert GAP_NO_COUNTER in audit.gaps
    assert GAP_NO_SUPPORT not in audit.gaps


def test_support_question_reports_zero_when_only_counter() -> None:
    audit = audit_recall(
        [
            _line("产能过剩", "年报", "2026-08-01", counter=True),
            _line("价格战", "公告", "2026-08-10", counter=True),
            _line("需求不及", "研报", "2026-08-12", counter=True),
        ],
        as_of=AS_OF,
    )
    assert GAP_NO_SUPPORT in audit.gaps
    assert GAP_NO_COUNTER not in audit.gaps


def test_missing_counter_disclosure_is_not_a_hit() -> None:
    audit = audit_recall(
        [
            "未检索到反方证据",
            _line("营收增长", "年报", "2026-08-01"),
            _line("订单饱满", "公告", "2026-08-10"),
            _line("扩产落地", "研报", "2026-08-12"),
        ],
        as_of=AS_OF,
    )
    assert GAP_NO_COUNTER in audit.gaps


def test_chain_question_reports_zero_without_upstream_terms() -> None:
    audit = audit_recall(
        [
            _line("营收增长", "年报", "2026-08-01"),
            _line("客户验证通过", "公告", "2026-08-10", counter=True),
            _line("扩产落地", "研报", "2026-08-12"),
        ],
        as_of=AS_OF,
    )
    assert GAP_NO_CHAIN in audit.gaps


def test_chain_question_passes_on_supplier_hit() -> None:
    audit = audit_recall(
        [
            _line("上游树脂供应商扩产", "年报", "2026-08-01"),
            _line("产能过剩", "公告", "2026-08-10", counter=True),
            _line("扩产落地", "研报", "2026-08-12"),
        ],
        as_of=AS_OF,
    )
    assert GAP_NO_CHAIN not in audit.gaps


def test_freshness_question_reports_zero_when_all_older_than_30_days() -> None:
    audit = audit_recall(
        [
            _line("上游扩产", "年报", "2026-06-01"),
            _line("产能过剩", "公告", "2026-05-20", counter=True),
            _line("订单饱满", "研报", "2026-04-08"),
        ],
        as_of=AS_OF,
    )
    assert GAP_NO_FRESH in audit.gaps


def test_freshness_question_passes_when_one_line_within_30_days() -> None:
    audit = audit_recall(
        [
            _line("上游扩产", "年报", "2026-06-01"),
            _line("产能过剩", "公告", "2026-08-10", counter=True),
            _line("订单饱满", "研报", "2026-04-08"),
        ],
        as_of=AS_OF,
    )
    assert GAP_NO_FRESH not in audit.gaps


def test_independent_sources_same_doc_counts_as_one() -> None:
    audit = audit_recall(
        [
            _line("上游扩产", "同一研报", "2026-08-01"),
            _line("产能过剩", "同一研报", "2026-08-10", counter=True),
            _line("订单饱满", "同一研报", "2026-08-12"),
        ],
        as_of=AS_OF,
    )
    assert GAP_FEW_SOURCES in audit.gaps


def test_independent_sources_three_docs_pass() -> None:
    audit = audit_recall(
        [
            _line("上游扩产", "年报", "2026-08-01"),
            _line("产能过剩", "公告", "2026-08-10", counter=True),
            _line("订单饱满", "研报", "2026-08-12"),
        ],
        as_of=AS_OF,
    )
    assert GAP_FEW_SOURCES not in audit.gaps


def test_all_four_pass_emits_no_disclosure() -> None:
    audit = audit_recall(
        [
            _line("上游树脂供应商扩产", "年报", "2026-08-01"),
            _line("行业产能过剩", "公告", "2026-08-10", counter=True),
            _line("订单饱满", "研报", "2026-08-12"),
        ],
        as_of=AS_OF,
    )
    assert audit.gaps == ()
    assert audit.disclosure_lines() == ()


def test_disclosure_lines_prefix_each_gap() -> None:
    audit = audit_recall([], as_of=AS_OF)
    assert audit.disclosure_lines() == (
        f"召回自评：{GAP_NO_SUPPORT}",
        f"召回自评：{GAP_NO_COUNTER}",
        f"召回自评：{GAP_NO_CHAIN}",
        f"召回自评：{GAP_NO_FRESH}",
        f"召回自评：{GAP_FEW_SOURCES}",
    )
