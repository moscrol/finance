"""Finite, deterministic checks at the *delivered-text* boundary.

Not a general semantic judge: catches explicit absence-from-search inferences
and period-labeled OCF/net-profit ratio transcription. Never fetches, executes
scripts, rewrites numbers or infers source completeness. A match withholds its
clause or replaces its bad cell with a gap; unrelated facts survive.
"""
from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN

from intelligence.services.agent_research import AgentEvidence
from intelligence.services.provider_observability import ProviderTrace, provider_trace_tool_name


@dataclass(frozen=True)
class DeliveryFinding:
    start: int
    end: int
    code: str
    replacement: str = ""


# The search outcome is NOT an assertion about the company's real-world state.
# A failure elsewhere does not revoke an independently sourced company statement.
_SEARCH_GAP = re.compile(
    r"(?:查询|检索|搜索|接口|返回|清单|列表|抓取).{0,32}"
    r"(?:失败|空白|为空|无结果|无记录|未返回|不完整|空集|未找到|查不到|没有结果)"
)
_ABSENCE = re.compile(r"(?:没有|并无|不存在|无(?:新增|新的|新)?|零|未发布(?:新)?)公告|(?:新增)?官方信息差|尚未兑现|没有兑现")
_INFERENCE = re.compile(r"因此|所以|说明|表明|证明|坐实|意味着|可判定|可以认定|即可|即无")
_UNKNOWN = re.compile(r"不能|无法|不足以|不代表|不等于|不意味着|不说明|不得|不可|未能|尚不能|不成立|无依据|错误推断")
_CLAUSE = re.compile(r"[^。！？；;\n]+[。！？；;]?")


def disclosure_absence_findings(text: str, traces: Sequence[ProviderTrace]) -> tuple[DeliveryFinding, ...]:
    """Flag explicit inference from a search gap, not all negative prose.

    Conditional 'if a query is empty, it proves no disclosure' is still an
    invalid inference. 'If the company has no disclosures, then...' without a
    query claim remains a hypothesis. Successful L3 lookups are not universe
    completeness certificates either.
    """
    disclosure_traces = [t for t in traces if provider_trace_tool_name(t) == "l3_lookup"]
    if not disclosure_traces:
        return ()  # not a blanket ban on examples in a methodology/critique answer
    incomplete = any(t.status not in {"success", "fallback_success"} for t in disclosure_traces)
    findings = []
    for clause in _CLAUSE.finditer(text):
        value = re.sub(r"[*_`]+", "", clause.group())
        if not _ABSENCE.search(value) or not _INFERENCE.search(value):
            continue
        # Scope disclaimers to their own comma clause, not the whole sentence.
        # '不能查全，但无公告即...' must not inherit the first clause's exemption.
        tails = re.split(r"[,，]|但是|但", value)
        assertions = [p for p in tails if _ABSENCE.search(p) and _INFERENCE.search(p)]
        if not assertions or all(_UNKNOWN.search(p) for p in assertions):
            continue
        search_claim = bool(_SEARCH_GAP.search(value))
        collapsed_gap = incomplete and bool(re.search(r"(?:窗口|期间|期内|本期).*无.*公告.*即无", value))
        if search_claim or collapsed_gap:
            findings.append(DeliveryFinding(clause.start(), clause.end(), "disclosure_absence_inference"))
    return tuple(findings)


_PERIOD = re.compile(
    r"20\d{2}-\d{2}-\d{2}|20\d{2}\s*年?\s*(?:半年度报告|年度报告|半年报|一季报|三季报|"
    r"一季度|二季度|三季度|四季度|中报|年报|上半年|前三季|H1|FY|Q[1-4])", re.I,
)
_RATIO_NAME = re.compile(
    r"含金量|净现比|(?:OCF|经营(?:活动)?现金流(?:量)?(?:净额)?)[\s_/(（÷]*"
    r"(?:除以|对)?[\s_]*(?:归母)?(?:净利(?:润)?|net[_ ]?profit)", re.I,
)
_NUMBER = r"[-+]?\d+(?:\.\d+)?"
_DELTA_UNIT = re.compile(r"百分点|基点|(?<![A-Za-z])bps?(?![A-Za-z])", re.I)
_RATIO_UNIT = r"个百分点|百分点|基点|bps?|百分比|%|倍"
_NUMBER_CELL = re.compile(rf"^\s*({_NUMBER})\s*({_RATIO_UNIT})?\s*$", re.I)
_PROSE_VALUE = re.compile(
    rf"\s*(?:[（(]\s*(?P<label_unit>{_RATIO_UNIT})\s*[）)])?"
    rf"\s*(?:为|是|=|：|:)?\s*(?P<value>{_NUMBER})\s*(?P<unit>{_RATIO_UNIT})?", re.I,
)


def _ratio_unit(value: str) -> str:
    # A difference unit cannot be hidden by a percent/multiple marker elsewhere
    # in the same label. It is never converted into an absolute ratio level.
    if delta := _DELTA_UNIT.search(value):
        return delta.group().lower()
    if "%" in value or "百分比" in value:
        return "%"
    return "倍" if "倍" in value else ""


def _absolute_ratio_label(value: str) -> bool:
    return bool(_RATIO_NAME.search(value)) and not re.search(r"同比|环比|增长|增速|变化|变动|差额|增量", value)


def _period(value: str) -> str | None:
    match = _PERIOD.search(value)
    if not match:
        return None
    token = match.group()
    try:
        return date.fromisoformat(token).isoformat()
    except ValueError:
        from intelligence.services.market_financials import target_report_end_from_query
        parsed = target_report_end_from_query(token)
        return parsed.isoformat() if parsed else None


def _display_matches(raw: str, value: float, unit: str = "") -> bool:
    """Only declared precision rounding; not a tolerance over arbitrary numbers."""
    try:
        displayed = Decimal(raw)
        expected = Decimal(str(value)) * (100 if unit == "%" else 1)
        return displayed == expected.quantize(Decimal(1).scaleb(displayed.as_tuple().exponent), rounding=ROUND_HALF_EVEN)
    except (InvalidOperation, ValueError):
        return False


def _ratio_products(evidence: Sequence[AgentEvidence]) -> dict[str, set[float]]:
    by_hash = {e.content_hash: e for e in evidence}
    # Multiple companies need an explicit subject-bearing result contract; do
    # not certify or reject one company's number using another company's set.
    subjects = {o.subject for e in evidence for o in e.observations
                if o.metric in {"ocf_cum_yi", "net_profit_cum_yi"}}
    if len(subjects) != 1:
        return {}
    products: dict[str, set[float]] = {}
    inapplicable_periods: set[str] = set()
    for item in evidence:
        if item.tool != "derived_calculation" or not item.derived_from:
            continue
        inputs = [by_hash[h] for h in item.derived_from if h in by_hash]
        metrics = {o.metric for e in inputs for o in e.observations}
        if not {"ocf_cum_yi", "net_profit_cum_yi"} <= metrics:
            continue
        for obs in item.observations:
            # For tables inspect the COLUMN, not a 'cash ratio' purpose/table
            # name covering unrelated revenue columns. Row label supplies time.
            column = obs.metric.rsplit(".", 1)[-1].split("[", 1)[0]
            if not _absolute_ratio_label(column):
                continue
            # A year in the table name must not override the row's report period.
            label = obs.metric.rsplit("[", 1)[-1].rstrip("]") if "[" in obs.metric else obs.metric
            period = _period(label)
            if period and _DELTA_UNIT.search(column):
                inapplicable_periods.add(period)
                continue
            if period and Decimal(str(obs.value)).is_finite():
                ratio = obs.value / 100 if _ratio_unit(column) == "%" else obs.value
                products.setdefault(period, set()).add(ratio)
    # An empty known period is an unverified product, distinct from no product.
    # A second, valid-looking value cannot waive the first product's unit gap.
    for period in inapplicable_periods:
        products[period] = set()
    return products


def calculation_copy_findings(
    text: str, evidence: Sequence[AgentEvidence], *, calculation_required: bool = False,
) -> tuple[DeliveryFinding, ...]:
    """Compare explicit period+ratio cells/prose to that period's actual product.

    Does not prove the product's formula or that its script read the inputs.
    Conflicting products remain unverifiable. No bag-of-numbers matching: the
    same numeric token in another period/metric cannot certify this claim.
    """
    subjects = {o.subject for e in evidence for o in e.observations
                if o.metric in {"ocf_cum_yi", "net_profit_cum_yi"}}
    if len(subjects) != 1:
        return ()
    products = _ratio_products(evidence)
    require_product = calculation_required or bool(re.search(r"计算编号\s*[0-9a-f]{16}", text))
    if not products and not require_product:
        return ()

    def failure_code(values: set[float] | None, raw: str, unit: str, label_unit: str = "") -> str:
        if _DELTA_UNIT.search(unit) or _DELTA_UNIT.search(label_unit):
            return "calculation_value_unverified"
        if values is None or len(values) != 1:
            return "calculation_value_unverified" if require_product or values is not None else ""
        unit = _ratio_unit(unit or label_unit)
        return "" if _display_matches(raw, next(iter(values)), unit) else "calculation_value_mismatch"

    findings: list[DeliveryFinding] = []
    ratio_columns: tuple[tuple[int, str], ...] = ()
    period_column: int | None = None
    offset = 0
    for line in text.splitlines(keepends=True):
        if line.lstrip().startswith("|"):
            cells = [re.sub(r"[*`]+", "", c.strip()) for c in line.strip().strip("|").split("|")]
            headers = tuple((i, _ratio_unit(c))
                            for i, c in enumerate(cells) if _absolute_ratio_label(c))
            if headers:
                ratio_columns = headers
                period_column = next((i for i, c in enumerate(cells) if c in {"报告期", "期间", "期别"}), None)
            elif period_column is not None and period_column < len(cells):
                period = _period(cells[period_column])
                values = products.get(period or "")
                for index, header_unit in ratio_columns:
                    match = _NUMBER_CELL.fullmatch(cells[index]) if index < len(cells) else None
                    code = failure_code(values, match[1], match[2] or "", header_unit) if match and period else ""
                    if code:
                        # Remove only the incorrect cell, not the independent
                        # OCF/profit facts in the same row. Never write a guessed
                        # replacement number, even when a product exists.
                        raw_cells = list(re.finditer(r"(?<=\|)[^|]*(?=\|)", line))
                        if index < len(raw_cells):
                            cell = raw_cells[index]
                            findings.append(DeliveryFinding(
                                offset + cell.start(), offset + cell.end(),
                                code, " 待核对 ",
                            ))
        else:
            ratio_columns, period_column = (), None
            # Prose needs an explicit ratio label locally. Broader semantic
            # matching (e.g. ambiguous bare 1.588) stays with the existing judge.
            for clause in _CLAUSE.finditer(line):
                value = re.sub(r"[*`]+", "", clause.group())
                for period_match in _PERIOD.finditer(value):
                    tail = value[period_match.end():]
                    ratio = _RATIO_NAME.match(tail.lstrip())
                    if ratio is not None:
                        remainder = tail.lstrip()[ratio.end():]
                    elif (re.search(r"(?:比率|净现比|含金量)[^。；;]*[:：]", value[:period_match.start()])
                          and not re.search(r"同比|环比|增长|增速|变化|变动|差额|增量", value[:period_match.start()])):
                        # Explicitly labeled same-clause comparison, e.g.
                        # '比率同期对照：2026中报1.588 vs 2025中报0.289'.
                        remainder = tail
                    else:
                        continue
                    number = _PROSE_VALUE.match(remainder)
                    values = products.get(_period(period_match.group()) or "")
                    code = failure_code(
                        values, number["value"], number["unit"] or "", number["label_unit"] or "",
                    ) if number else ""
                    if code:
                        findings.append(DeliveryFinding(offset + clause.start(), offset + clause.end(), code))
                        break
        offset += len(line)
    return tuple(findings)


def remove_findings(text: str, findings: Sequence[DeliveryFinding]) -> str:
    """Exact spans, not global replacements; no computed numbers are inserted."""
    spans: list[tuple[int, int, str]] = []
    for f in sorted(set(findings), key=lambda f: (f.start, f.end)):
        if spans and f.start < spans[-1][1]:
            # Overlap may mix clause and cell checks. Conservatively omit the
            # union rather than inserting one cell's label into unrelated prose.
            spans[-1] = (spans[-1][0], max(spans[-1][1], f.end), "")
        else:
            spans.append((f.start, f.end, f.replacement))
    for start, end, replacement in reversed(spans):
        text = text[:start] + replacement + text[end:]
    return text.strip()
