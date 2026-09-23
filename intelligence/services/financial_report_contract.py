"""Report selection is about periods and availability, not arbitrary pairs of numbers.

Pure, bounded checks for an explicit 'latest N reports' request. This is not a
financial judgment or proof that the provider returned its complete universe.
"""
from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date

from intelligence.services.agent_research import AgentEvidence
from intelligence.services.market_financials import FinancialsBundle, QuarterFinancials, build_financials_block
from intelligence.services.research_contract import InformationCutoff

_RECENT_REPORTS = re.compile(
    r"(?:最近|最新|近)\s*([1-8一二两三四五六七八])\s*(?:份|期)\s*"
    r"(?:已披露(?:的)?\s*)?(?:(?:定期报告|财务报告|财报|报告)|(?=的?(?:收入|营收|净利|归母|经营)))"
)
_COUNTS = dict(zip("一二两三四五六七八", (1, 2, 2, 3, 4, 5, 6, 7, 8)))
_METRICS = (
    (r"营收|营业(?:总)?收入|收入", "revenue_cum_yi"),
    (r"归母|净利润|净利", "net_profit_cum_yi"),
    (r"经营(?:活动)?现金流|经营活动产生的现金流", "ocf_cum_yi"),
)


def recent_report_count(question: str) -> int | None:
    match = _RECENT_REPORTS.search(question)
    if not match:
        return None
    value = match.group(1)
    return int(value) if value.isdigit() else _COUNTS[value]


def _date(value: str | None) -> date | None:
    try:
        return date.fromisoformat(str(value or ""))
    except ValueError:
        return None


@dataclass(frozen=True)
class ReportSelection:
    bundle: FinancialsBundle
    receipt: dict[str, object]
    hint: str
    gaps: tuple[str, ...]


def select_reports(
    bundle: FinancialsBundle, *, question: str, cutoff: InformationCutoff,
) -> ReportSelection:
    """Keep usable input rows; select latest N by report end (not publication order).

    Missing disclosure dates do not prove historical availability. Excluded rows
    stay in the receipt, never disguised as 'the company has no report'. Extra
    historical rows remain available for same-period YoY and single-quarter math.
    """
    count = recent_report_count(question)
    strict = cutoff.source == "requested"
    candidates: list[dict[str, object]] = []
    usable: list[QuarterFinancials] = []
    gaps: list[str] = []
    subject = bundle.ts_code
    # A provider may repeat a row or return revisions without a revision id.
    # Exact duplicates collapse; conflicting versions are not arbitrarily merged
    # into one supposedly available report. Preserve their candidate receipts.
    by_period: dict[str, list[QuarterFinancials]] = {}
    for row in bundle.rows:
        group = by_period.setdefault(row.report_date, [])
        if row not in group:
            group.append(row)
    rows = [row for group in by_period.values() for row in group]
    for row in sorted(rows, key=lambda r: r.report_date, reverse=True):
        period, notice = _date(row.report_date), _date(row.notice_date)
        reason = "eligible"
        if period is None:
            reason = "invalid_report_period"
        elif period > cutoff.as_of_date or (notice and notice > cutoff.as_of_date):
            reason = "after_cutoff"
        elif notice and notice < period:
            reason = "disclosure_before_period_end"
        elif len(by_period[row.report_date]) > 1:
            reason = "conflicting_report_rows"
        elif notice is None:
            reason = "disclosure_unverified"
        candidates.append({
            "report_period": row.report_date, "report_name": row.report_name,
            "disclosed_at": row.notice_date, "reason": reason,
        })
        if reason == "eligible" or (reason == "disclosure_unverified" and not strict):
            usable.append(row)
        if reason != "eligible":
            gaps.append(f"{subject} {row.report_date}：{reason}；不能据此确认在截止日前已披露")
    periods = sorted({r.report_date for r in usable}, reverse=True)
    selected = periods[:count] if count else []
    if count and len(selected) < count:
        gaps.append(f"{subject} 最近{count}期报告仅确认{len(selected)}期，来源全集未核实")
    hint = ""
    if count:
        hint = (
            f"报告选择：{subject} 截止{cutoff.as_of_date.isoformat()}，"
            f"最近{count}期按报告期新→旧为{'、'.join(selected) or '未确认'}；"
            "较旧各期只供同口径对照，不得跳过较新一期改称最近两期。"
            "累计期间长度不同不能直接作环比；来源候选不代表官方报告全集。"
        )
    projected = bundle
    if tuple(usable) != bundle.rows:
        projected = replace(
            bundle, rows=tuple(usable),
            block=build_financials_block(
                bundle.name, bundle.ts_code, usable, fetch_result=bundle.result,
            ),
        )
    return ReportSelection(projected, {
        "subject": subject, "information_cutoff": cutoff.as_of_date.isoformat(),
        "requested_count": count, "selected_periods": selected,
        "candidates": candidates, "universe_complete": False,
    }, hint, tuple(gaps))


def _subject_key(value: str) -> str:
    return value.upper().removesuffix(".SZ").removesuffix(".SH").removesuffix(".BJ")


def report_binding_gaps(
    question: str, evidence: Sequence[AgentEvidence], bound_hashes: Sequence[str],
    *, draft: str, subject: str | None = None,
    selections: Sequence[Mapping[str, object]] = (),
) -> tuple[str, ...]:
    """Missing declared metrics/periods in this slot, not a blanket answer veto.

    Structured observations, not coincidental date/number strings, carry the
    check. Text-only sources remain a disclosed verification gap here; this
    does not declare those sources false. Derived evidence cannot replace the
    user's requested raw financial inputs.
    """
    count = recent_report_count(question)
    if count is None:
        return ()
    metrics = tuple(metric for pattern, metric in _METRICS if re.search(pattern, question))
    if not metrics:
        return ()
    # A peer fetched for context cannot add obligations to the requested company.
    scope = {_subject_key(subject)} if subject else set()
    if subject:
        for item in evidence:
            if item.tool == "financial_data" and subject in item.title:
                scope.update(_subject_key(o.subject) for o in item.observations)
    available: dict[str, set[str]] = {}
    bound: set[tuple[str, str, str]] = set()
    hashes = set(bound_hashes)
    for item in evidence:
        if item.tool != "financial_data":
            continue
        for obs in item.observations:
            key = _subject_key(obs.subject)
            if scope and key not in scope:
                continue
            if _date(obs.as_of) is None or obs.metric not in {m for _, m in _METRICS}:
                continue
            available.setdefault(key, set()).add(obs.as_of)
            if item.content_hash in hashes and math.isfinite(obs.value):
                bound.add((key, obs.as_of, obs.metric))
    gaps = []
    # Tool receipts preserve candidates with no numeric rows and unknown disclosure.
    # Take the last receipt per subject, so an earlier failed lookup is not forever sticky.
    latest = {_subject_key(str(s.get("subject") or "")): s for s in selections}
    for key, selection in latest.items():
        if scope and key not in scope:
            continue
        selected = [p for p in selection.get("selected_periods", ()) if _date(p)]
        available.setdefault(key, set()).update(selected)
        floor = min(selected) if len(selected) >= count else ""
        for candidate in selection.get("candidates", ()):
            if not isinstance(candidate, Mapping):
                continue
            reason = candidate.get("reason")
            period = str(candidate.get("report_period") or "")
            if reason in {"disclosure_unverified", "invalid_report_period", "disclosure_before_period_end", "conflicting_report_rows"}:
                if not floor or period >= floor:
                    gaps.append(f"{key} {period}：{reason}，最近{count}期的披露可用性未核实")
    if not available:
        return (f"最近{count}期报告尚无结构化报告期与指标可核对",)

    for subject, dates in sorted(available.items()):
        selected = sorted(dates, reverse=True)[:count]
        if len(selected) < count:
            gaps.append(f"{subject} 最近{count}期仅取得{len(selected)}期")
        for period in selected:
            missing = [metric for metric in metrics if (subject, period, metric) not in bound]
            if missing:
                gaps.append(f"{subject} {period} 未绑定 {','.join(missing)}")
            if not _mentions_period(draft, period):
                gaps.append(f"{subject} 正文未列示最近报告期 {period}")
    return tuple(dict.fromkeys(gaps))


def _mentions_period(draft: str, period: str) -> bool:
    year, month, _ = period.split("-")
    labels = {
        "03": r"(?:一季报|一季度|Q1)",
        "06": r"(?:中报|半年报|上半年|半年度|H1|Q2)",
        "09": r"(?:三季报|三季度|前三季度|Q3)",
        "12": r"(?:年报|年度|全年|FY|Q4)",
    }
    label = labels.get(month)
    if period in draft or f"{year}年{int(month)}月{int(period[-2:])}日" in draft:
        return True
    return bool(label and re.search(
        rf"{year}\s*年?\s*{label}|{label}\s*{year}(?!\d)", draft, re.IGNORECASE,
    ))


_RATIO_NAME = r"(?:净现比|经营(?:活动(?:产生的)?)?现金流量?(?:净额)?\s*[/／÷]\s*(?:归母)?净利(?:润)?)"
_RATIO_CLAIM = re.compile(rf"{_RATIO_NAME}\s*(?:约为|约|为|是|[:：=＝])\s*[+-]?\d")
_RATIO_REQUEST = re.compile(
    rf"(?:计算|测算|核算)\s*(?:(?:各|每|两|[1-8一二三四五六七八])(?:报告)?期(?:的)?\s*)?"
    rf"{_RATIO_NAME}|{_RATIO_NAME}.{{0,8}}(?:多少|计算|测算)"
)


def _requests_ratio(question: str) -> bool:
    return any(
        _RATIO_REQUEST.search(clause) and not re.search(r"不要|无需|不必|不用|别", clause)
        for clause in re.split(r"[，,。；;\n]", question)
    )


_CALC_REFERENCE = re.compile(r"计算编号\s*([0-9a-f]{16})(?![0-9a-f])")
_DOCUMENT_REQUEST = re.compile(
    r"(?:选用|使用|引用|检索|查阅|获取|取得|查找).{0,70}(?:公告|定期报告|半年报|年报).{0,12}(?:原文|文档)|"
    r"(?:选用|使用|引用).{0,25}(?:确实|实际|真实).{0,55}(?:公告|定期报告)|"
    r"(?:检索|查阅|获取|取得|查找).{0,20}(?:公告|定期报告).{0,10}(?:发布日期|披露日期)"
)
_DOCUMENT_CLAIM = re.compile(
    r"(?:本次|已经|已)?(?:实际|确实)?取得(?:并引用)?的?(?:报告|公告)|"
    r"(?:已|实际)(?:获取|检索到|查阅).{0,20}(?:原文|文档)"
)


def _bound_report_documents(evidence, bound_hashes, *, subject: str | None):
    hashes = set(bound_hashes)
    # Search listings / structured financial rows are not fetched documents.
    # Old L3 records lack typed body/date provenance; keep them as useful
    # evidence, but do not silently promote them to this stronger delivery.
    return tuple(item for item in evidence if (
        item.content_hash in hashes and item.tool == "web_fetch"
        and item.document_type in {"periodic_report", "announcement"}
        and _date(item.source_date) is not None and item.detail.strip()
        and item.source.startswith(("https://", "http://"))
        and (not subject or _subject_key(subject) in item.title or _subject_key(subject) in item.detail)
    ))


def report_document_binding_gaps(
    question: str, evidence: Sequence[AgentEvidence], bound_hashes: Sequence[str],
    *, subject: str | None,
) -> tuple[str, ...]:
    clauses = re.split(r"[。；;\n]", question)
    requested = any(_DOCUMENT_REQUEST.search(clause) and not re.search(
        r"不(?:用|必|要|需要)|无需", clause,
    ) for clause in clauses)
    if not requested:
        return ()
    documents = _bound_report_documents(evidence, bound_hashes, subject=subject)
    if documents:
        return ()
    return ("尚未绑定所要求的公告/报告文档及明确发布日期；结构化财务行不能替代文档交付",)


def report_document_claim_mismatches(
    sentences: Sequence[Mapping[str, object]], evidence: Sequence[AgentEvidence],
    bound_hashes: Sequence[str], *, subject: str | None,
) -> tuple[int, ...]:
    if _bound_report_documents(evidence, bound_hashes, subject=subject):
        return ()
    return tuple(int(row["index"]) for row in sentences if (
        isinstance(row.get("index"), int)
        and _DOCUMENT_CLAIM.search(str(row.get("text") or ""))
        and not re.search(r"未(?:能)?取得|未获取|未检索到|没有取得", str(row.get("text") or ""))
    ))


def calculation_binding_gaps(
    question: str, draft: str, evidence: Sequence[AgentEvidence], bound_hashes: Sequence[str],
) -> tuple[str, ...]:
    """A claimed numeric ratio/calculation id must bind an actual result.

    No computation requirement for raw-value/qualitative research, and a failed
    optional attempt does not poison a later successful result or unrelated fact.
    This checks product existence/dependency only, not mathematical semantics.
    """
    bound = set(bound_hashes)
    products = [e for e in evidence if e.tool == "derived_calculation"
                and e.content_hash in bound and e.derived_from]
    gaps = []
    ratio_products = [p for p in products if any(
        math.isfinite(o.value) and (
            re.search(_RATIO_NAME, o.metric)
            or re.search(r"(?i)ratio|cash.{0,16}profit|ocf.{0,16}profit", o.metric)
        ) for o in p.observations
    )]
    if (_requests_ratio(question) or _RATIO_CLAIM.search(draft)) and not ratio_products:
        gaps.append("净现比计算未绑定有对应数值的实际产物；原始值可保留，派生结论仍缺计算支持")
    known = {e.source.removeprefix("sandbox:") for e in products}
    for calc_id in _CALC_REFERENCE.findall(draft):
        if calc_id not in known:
            gaps.append(f"计算编号 {calc_id} 没有对应的已绑定计算产物")
    return tuple(gaps)
