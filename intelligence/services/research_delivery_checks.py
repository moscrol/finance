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
_ABSENCE = re.compile(r"(?:没有|并无|不存在|无|零|未发布)(?:新增|新的|新)?公告|零披露|(?:新增)?官方信息差|尚未兑现|没有兑现")
_INFERENCE = re.compile(r"因此|所以|说明|表明|证明|坐实|意味着|可判定|可以认定|即可|即无")
_UNKNOWN = re.compile(r"不能|无法|不足以|不代表|不等于|不意味着|不说明|不得|不可|未能|尚不能|不成立|无依据|错误推断")
_CLAUSE = re.compile(r"[^。！？；;\n]+[。！？；;]?")
# Keep raw offsets: deleting formatting before locating edits corrupts spans.
_ASSERTION_SEPARATOR = r"[,，、—]+|--+|但是|然而|不过|但|(?<=\])而|(?<=\])[ \t]+"
_ASSERTION_PART = re.compile(rf"(?:^|{_ASSERTION_SEPARATOR})(?P<claim>(?:(?!{_ASSERTION_SEPARATOR}).)+)")
_ATTRIBUTED = re.compile(r"(?:官方公告|公告原文|公司原文|交易所披露平台|巨潮资讯网)(?:称|明确说明|说明|显示)")
_HYPOTHESIS = re.compile(r"^(?:若|如果|假设)")
_DEPENDENT = re.compile(r"^(?:即|也就是说|换言之|据此|因此|由此)")


def _rejected_assertion_spans(raw: str) -> tuple[tuple[int, int], ...]:
    """Sentence context establishes the inference; only its bad parts are removed.

    Merge adjacent rejected parts before choosing one separator to remove. Keep
    the separator between surviving parts and the original sentence terminator.
    Formatting/citations in a surviving part are never reconstructed.
    """
    parts = list(_ASSERTION_PART.finditer(raw))
    values = [re.sub(r"[*_`]+", "", part.group("claim")).strip() for part in parts]
    rejected = [bool(_ABSENCE.search(value) and _INFERENCE.search(value) and not _UNKNOWN.search(value))
                for value in values]
    # An invalid premise cannot leave an uncited/re-cited restatement or a
    # dependent recommendation behind. A citation alone isn't independence.
    has_rejected_premise = any(rejected)
    prior_rejection = False
    for index, value in enumerate(values):
        if rejected[index]:
            prior_rejection = True
        elif has_rejected_premise:
            independent = bool(
                _UNKNOWN.search(value) or _HYPOTHESIS.search(value)
                or (re.search(r"\[E\d+\]", value) and (
                    _ATTRIBUTED.search(value)
                    or (index > 0 and _ATTRIBUTED.search(values[index - 1]) and not rejected[index - 1])
                ))
            )
            residue = bool(_ABSENCE.search(value) or (prior_rejection and _DEPENDENT.match(value)))
            rejected[index] = residue and not independent
            prior_rejection = prior_rejection or rejected[index]
    spans = []
    i = 0
    while i < len(parts):
        if not rejected[i]:
            i += 1
            continue
        first = i
        while i + 1 < len(parts) and rejected[i + 1]:
            i += 1
        start, end = parts[first].start("claim"), parts[i].end("claim")
        if first:
            separator = raw[parts[first - 1].end("claim"):start]
            connective = re.search(r"但是|然而|不过|但|而", separator)
            if connective:
                start = parts[first - 1].end("claim") + connective.start()
        if i + 1 < len(parts):
            end = parts[i + 1].start("claim")  # also remove the following separator
        elif first:
            start = parts[first - 1].end("claim")  # final run: remove preceding separator
            if raw[-1:] in {"。", "！", "？", "；", ";"}:
                end -= 1
        if first == 0:
            start = 0  # include any leading conjunction of the rejected run
        spans.append((start, end))
        i += 1
    return tuple(spans)


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
        # Search context may live in a different comma part. Do not split the
        # detection window, but don't revoke independent neighbors when editing.
        search_claim = bool(_SEARCH_GAP.search(value))
        collapsed_gap = incomplete and bool(re.search(r"(?:窗口|期间|期内|本期).*无.*公告.*即无", value))
        if search_claim or collapsed_gap:
            findings.extend(
                DeliveryFinding(clause.start() + start, clause.start() + end, "disclosure_absence_inference")
                for start, end in _rejected_assertion_spans(clause.group())
            )
    return tuple(findings)


_PERIOD = re.compile(
    r"20\d{2}-\d{2}-\d{2}|20\d{2}\s*年?\s*(?:半年度报告|年度报告|半年报|一季报|三季报|"
    r"一季度|二季度|三季度|四季度|中报|年报|上半年|前三季|H1|FY|Q[1-4])", re.I,
)
_RATIO_NAME = re.compile(
    r"含金量|净现比|(?:OCF|经营(?:活动)?现金流(?:量)?(?:净额)?)[\s_/(（÷]*"
    r"(?:除以|对)?[\s_]*(?:归母)?(?:净利(?:润)?|net[_ ]?profit)", re.I,
)
# A grouped decimal is one token: don't scan the prefix of 1,234.56 as 1.
_NUMBER = r"[-+]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"
# Basis points are an explicit unit of the value slot: recognize them so a
# wrong "158.7bp" is compared, not silently skipped as an unknown suffix.
_RATIO_UNIT = r"元\s*[/／]\s*元|个百分点|[bB][pP]|基点|%|倍"
_BASIS_POINTS = re.compile(r"[bB][pP]|基点")
_NUMBER_CELL = re.compile(rf"^\s*({_NUMBER})\s*({_RATIO_UNIT})?\s*$")


def _absolute_ratio_label(value: str) -> bool:
    return bool(_RATIO_NAME.search(value)) and not re.search(r"同比|环比|增速|变化|变动|差额|增量", value)


# '2025年报（截止 2025-12-31，披露 2026-04-17）' names ONE period and then dates
# it. Reading the qualifier as a second claim ends the first one's scope early,
# which is how a wrong value after the parenthesis escaped every check.
_QUALIFIER_DATE = re.compile(r"(?:截[止至]|披露|公告|发布|更新|报告期截止)(?:日期?|于|时间)?\s*[:：]?\s*$")


def _claim_periods(value: str) -> list[re.Match]:
    """Period tokens that assert a period, dropping ones that merely date it."""
    return [m for m in _PERIOD.finditer(value) if not _QUALIFIER_DATE.search(value[:m.start()])]


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
    # Percentage points describe a difference, never an absolute OCF/profit ratio.
    if unit == "个百分点":
        return False
    # Basis points quote a spread or a change; no scalar in them is the level.
    if _BASIS_POINTS.fullmatch(unit):
        return False
    try:
        displayed = Decimal(raw.replace(",", ""))
        expected = Decimal(str(value)) * (100 if unit == "%" else 1)
        return displayed == expected.quantize(Decimal(1).scaleb(displayed.as_tuple().exponent), rounding=ROUND_HALF_EVEN)
    except (InvalidOperation, ValueError):
        return False


def _near_miss(raw: str, unit: str, value: float) -> bool:
    """A printed number one last-digit step away from the product.

    Transcription slips (0.7474 -> 0.7473) land here; an unrelated fact in the
    same sentence does not. Correct rounding is excluded by the caller, so this
    only ever fires on a number that claims to be, but isn't, that product.
    """
    # Points and basis points quote a change, never the level; and an integer
    # token ('1 份公告') is not a printed ratio.
    if unit == "个百分点" or _BASIS_POINTS.fullmatch(unit) or "." not in raw:
        return False
    try:
        displayed = Decimal(raw.replace(",", ""))
        expected = Decimal(str(value)) * (100 if unit == "%" else 1)
    except (InvalidOperation, ValueError):
        return False
    ulp = Decimal(1).scaleb(displayed.as_tuple().exponent)
    return abs(displayed - expected) <= Decimal("1.5") * ulp


def _input_ratio_truth(inputs: Sequence[AgentEvidence]) -> dict[str, dict[str, float]]:
    """Per-period OCF and profit under their canonical metric names.

    These names come from the financial-data contract, not from the script, so
    they are the one part of a calculation the producer cannot rename.
    """
    truth: dict[str, dict[str, float]] = {}
    for item in inputs:
        for obs in item.observations:
            if obs.metric not in {"ocf_cum_yi", "net_profit_cum_yi"}:
                continue
            period = _period(obs.as_of or "")
            if period:
                truth.setdefault(period, {})[obs.metric] = obs.value
    return truth


def _derived_ratio_columns(
    item: AgentEvidence, truth: dict[str, dict[str, float]],
) -> set[str]:
    """Which columns ARE the ratio, decided by arithmetic, not by their name.

    The script names its own columns, so a name list can only ever cover the
    names we already thought of: the live run called it '现金流/净利润' and every
    check downstream went quiet. A column instead qualifies when its cells
    reproduce OCF/profit for the period on that row. Two independent rows are
    required, so one coincidental cell cannot promote an unrelated column.
    """
    hits: dict[str, int] = {}
    for obs in item.observations:
        column = obs.metric.rsplit(".", 1)[-1].split("[", 1)[0]
        label = obs.metric.rsplit("[", 1)[-1].rstrip("]") if "[" in obs.metric else obs.metric
        period = _period(label)
        row = truth.get(period or "", {})
        ocf, profit = row.get("ocf_cum_yi"), row.get("net_profit_cum_yi")
        if ocf is None or not profit:
            continue
        scaled = obs.value / 100 if "%" in column or "百分比" in column else obs.value
        if _display_matches(str(scaled), ocf / profit):
            hits[column] = hits.get(column, 0) + 1
    return {column for column, seen in hits.items() if seen >= 2}


def _ratio_products(evidence: Sequence[AgentEvidence]) -> dict[str, set[float]]:
    by_hash = {e.content_hash: e for e in evidence}
    # Multiple companies need an explicit subject-bearing result contract; do
    # not certify or reject one company's number using another company's set.
    subjects = {o.subject for e in evidence for o in e.observations
                if o.metric in {"ocf_cum_yi", "net_profit_cum_yi"}}
    if len(subjects) != 1:
        return {}
    products: dict[str, set[float]] = {}
    for item in evidence:
        if item.tool != "derived_calculation" or not item.derived_from:
            continue
        inputs = [by_hash[h] for h in item.derived_from if h in by_hash]
        metrics = {o.metric for e in inputs for o in e.observations}
        if not {"ocf_cum_yi", "net_profit_cum_yi"} <= metrics:
            continue
        structural = _derived_ratio_columns(item, _input_ratio_truth(inputs))
        for obs in item.observations:
            # For tables inspect the COLUMN, not a 'cash ratio' purpose/table
            # name covering unrelated revenue columns. Row label supplies time.
            column = obs.metric.rsplit(".", 1)[-1].split("[", 1)[0]
            if not (_absolute_ratio_label(column) or column in structural):
                continue
            # A year in the table name must not override the row's report period.
            label = obs.metric.rsplit("[", 1)[-1].rstrip("]") if "[" in obs.metric else obs.metric
            period = _period(label)
            if period and Decimal(str(obs.value)).is_finite():
                ratio = obs.value / 100 if "%" in column or "百分比" in column else obs.value
                products.setdefault(period, set()).add(ratio)
    return products


def _prose_value_finding(
    raw: str, start: int, end: int, *, offset: int, code: str,
) -> DeliveryFinding:
    """Map an unformatted numeric token back to raw text, retaining Markdown.

    Exclude a trailing percent/multiple unit too. Formatting that wraps the
    value (possibly inside the unit) is preserved, not rebuilt from plain text.
    """
    positions = [i for i, char in enumerate(raw) if char not in "*`"]
    raw_start, raw_end = positions[start], positions[end - 1] + 1
    # Keep a balanced wrapper around the whole value, but discard formatting
    # that starts/ends inside a numeric token (1.**587**, **1.5**87).
    prefix = re.search(r"[*`]+$", raw[:raw_start])
    suffix = re.match(r"[*`]+", raw[raw_end:])
    left = prefix.group() if prefix else ""
    right = suffix.group() if suffix else ""
    internal = re.sub(r"[^*`]", "", raw[raw_start:raw_end])
    if internal and (left != internal + right or re.search(r"[*`]+[\d.]", raw[raw_start:raw_end])):
        raw_start -= len(left)
        raw_end += len(right)
        marks = ""
    else:
        marks = internal
    return DeliveryFinding(offset + raw_start, offset + raw_end, code, "待核对" + marks)


# One finite list of same-ratio continuation labels; the value prefix and the
# clause joiner derive from it so "该比率为" cannot be joined but not consumed.
_CONTINUATION_LABEL = r"(?:实际|该值|本期|该比率|比率)为"
_VALUE_PREFIX = rf"\s*(?:{_CONTINUATION_LABEL}|分别为|为|是|=|：|:)?\s*"
_PROSE_NUMBER = re.compile(rf"{_VALUE_PREFIX}({_NUMBER})\s*({_RATIO_UNIT})?")
_WITHHELD_SLOT = re.compile(rf"{_VALUE_PREFIX}待核对")
_VALUE_CONTINUATION = re.compile(rf"\s*[,，；;]\s*(?={_CONTINUATION_LABEL})")
# Only explicit same-ratio continuations inherit across a semicolon. Do not
# widen disclosure detection or join independent sentences/paragraphs.
_RATIO_CLAUSE = re.compile(rf"[^。！？；;\n]+(?:[；;]\s*(?=[*`]*{_CONTINUATION_LABEL})[^。！？；;\n]+)*[。！？；;]?")
_NON_RATIO_SUFFIX = re.compile(r"\s*(?:年|中报|年报|季|半年|H1|Q[1-4]|月|日|天|亿|万|元|家|人|名|位|次|项|个|百分点)", re.I)
# An explicitly labeled sample/count is its own fact, not an unlocated ratio.
_COUNT_LABEL = re.compile(
    r"(?:样本量|样本数|样本容量|数量|家数|只数|个数|次数|人数|笔数|条数|户数|份数|期数|天数|数目)"
    r"\s*[Nn]?\s*(?:为|是|约|达|=|：|:)?\s*$"
)
_UNLOCATED_RATIO_MARK = "〔比率对应关系待核对〕"


def _prose_number(value: str, start: int) -> tuple[int, int, str, str] | None:
    """A period/ranking count isn't a ratio value; never match its numeric prefix."""
    number = _PROSE_NUMBER.match(value, start)
    if number is None:
        return None
    if (not number[2] and _NON_RATIO_SUFFIX.match(value, number.end(1))) or _PERIOD.match(value, number.start(1)):
        return None
    if number[2] == "倍" and re.match(r"\s*(?:于|高于|低于|多于|少于)", value[number.end():]):
        return None
    return number.start(1), number.end(2 if number[2] else 1), number[1], number[2] or ""


def _parallel_ratio_values(value: str, periods: list[re.Match]) -> tuple[dict[int, tuple[int, int, str, str] | None], int]:
    """Only an explicit ordered 'periods 分别为 values' binds adjacent period labels."""
    if len(periods) < 2:
        return {}, 0
    if any(not re.fullmatch(r"[\s、，,和与及/]*", value[a.end():b.start()].replace(_UNLOCATED_RATIO_MARK, ""))
           for a, b in zip(periods, periods[1:])):
        return {}, 0
    marker = re.match(r"\s*分别为", value[periods[-1].end():])
    if marker is None:
        return {}, 0
    cursor = periods[-1].end() + marker.end()
    result = {}
    for index, period_match in enumerate(periods):
        if index:
            separator = re.match(r"\s*(?:与|和|及|、|，|,|vs)\s*", value[cursor:])
            if separator is None:
                return {}, 0
            cursor += separator.end()
        gap = re.match(r"\s*待核对", value[cursor:])
        number = _prose_number(value, cursor)
        if gap:
            result[period_match.start()] = None
            cursor += gap.end()
        elif number:
            result[period_match.start()] = number
            cursor = number[1]
        else:
            return {}, 0
    return result, cursor


def _ratio_scope_end(value: str, periods: list[re.Match], index: int) -> int:
    """Stop at the next period claim, not a referenced '2025中报的1.2倍'."""
    for following in periods[index + 1:]:
        if not re.match(rf"\s*的\s*{_NUMBER}\s*倍", value[following.end():]):
            return following.start()
    return len(value)


def _ratio_value_slots(value: str, start: int, end: int) -> tuple[list[tuple[int, int, str, str]], int]:
    """Consume exact value slots, not the rest of a period after a withheld slot.

    Explicit same-ratio continuations are checked individually. Any unconsumed
    numeric residue is still UNKNOWN; finding one valid value isn't a waiver.
    """
    numbers = []
    cursor = start
    while cursor < end:
        gap = _WITHHELD_SLOT.match(value, cursor, end)
        number = _prose_number(value[:end], cursor)
        if gap:
            cursor = gap.end()
        elif number:
            numbers.append(number)
            cursor = number[1]
        else:
            break
        continuation = _VALUE_CONTINUATION.match(value, cursor, end)
        if continuation is None:
            break
        cursor = continuation.end()
    return numbers, cursor


def _has_unlocated_ratio_number(residual: str) -> bool:
    # Mask roles, not individual digits. Keep separation so removing a period
    # or citation cannot accidentally concatenate two unrelated numeric tokens.
    residual = _PERIOD.sub(lambda m: " " * len(m.group()), residual)
    for role in (
        r"\[E\d+\]",
        r"(?:创)?\d+(?:年|个?季|个?月)(?:新高|新低|高点|低点|最高|最低)",
        r"(?:附注|注释|注)\s*[（(]?\d+[）)]?",
        r"(?:排名第?|位列第?|第)\s*\d+(?!\d|[.,]\d)",
    ):
        residual = re.sub(role, lambda m: " " * len(m.group()), residual)
    for number in re.finditer(_NUMBER, residual):
        unit = re.match(rf"\s*({_RATIO_UNIT})", residual[number.end():])
        if unit:
            # A separately stated delta has its own dimension. Unattributed
            # points/currency-ratio values must not hide behind the amount rule.
            delta = re.search(r"(?:增加|增长|提升|下降|减少|变化|变动|差额|增量)\s*(?:了|为|是)?\s*$",
                              residual[:number.start()])
            if unit[1] == "个百分点" and delta:
                continue
            # "同比增长12%" / "同比增加15bp" state a change rate, not the level.
            if delta and (unit[1] == "%" or _BASIS_POINTS.fullmatch(unit[1])):
                continue
            return True
        if _COUNT_LABEL.search(residual[:number.start()]):
            continue
        if not _NON_RATIO_SUFFIX.match(residual, number.end()):
            return True
    return False


def _unlocated_ratio_finding(raw: str, period_start: int, *, offset: int) -> DeliveryFinding:
    positions = [i for i, char in enumerate(raw) if char not in "*`"]
    insertion = positions[period_start]
    wrapper = re.search(r"[*`]+$", raw[:insertion])
    if wrapper:
        insertion -= len(wrapper.group())
    # The marker belongs to this period only, never to all the clause's facts.
    # A Markdown-wrapped marker is still the marker: never insert a second one.
    marked = re.sub(r"[*`]+", "", raw[:insertion]).rstrip().endswith(_UNLOCATED_RATIO_MARK)
    return DeliveryFinding(offset + insertion, offset + insertion, "calculation_value_unlocated",
                           "" if marked else _UNLOCATED_RATIO_MARK)


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

    def failure_code(values: set[float], raw: str, unit: str) -> str:
        if len(values) != 1:
            return "calculation_value_unverified" if require_product or values else ""
        return "" if _display_matches(raw, next(iter(values)), unit) else "calculation_value_mismatch"

    findings: list[DeliveryFinding] = []
    ratio_columns: tuple[tuple[int, str], ...] = ()
    period_column: int | None = None
    offset = 0
    for line in text.splitlines(keepends=True):
        if line.lstrip().startswith("|"):
            cells = [re.sub(r"[*`]+", "", c.strip()) for c in line.strip().strip("|").split("|")]
            headers = tuple((i, "个百分点" if "个百分点" in c else "%" if "%" in c or "百分比" in c else "")
                            for i, c in enumerate(cells) if _absolute_ratio_label(c))
            if headers:
                ratio_columns = headers
                period_column = next((i for i, c in enumerate(cells) if c in {"报告期", "期间", "期别"}), None)
            elif period_column is not None and period_column < len(cells):
                period = _period(cells[period_column])
                values = products.get(period or "", set())
                for index, header_unit in ratio_columns:
                    match = _NUMBER_CELL.fullmatch(cells[index]) if index < len(cells) else None
                    code = failure_code(values, match[1], match[2] or header_unit) if match and period else ""
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
            for clause in _RATIO_CLAUSE.finditer(line):
                value = re.sub(r"[*`]+", "", clause.group())
                periods = _claim_periods(value)
                parallel_values, parallel_end = _parallel_ratio_values(value, periods)
                for period_index, period_match in enumerate(periods):
                    scope_end = _ratio_scope_end(value, periods, period_index)
                    tail = value[period_match.end():scope_end]
                    label_prefix = re.match(r"\s*(?:的\s*)?", tail).end()
                    ratio = _RATIO_NAME.match(tail, label_prefix)
                    if ratio is not None:
                        remainder_start = period_match.end() + ratio.end()
                        remainder = value[remainder_start:scope_end]
                    elif (re.search(r"(?:比率|净现比|含金量)[^。；;]*[:：]", value[:period_match.start()])
                          and not re.search(r"同比|环比|增速|变化|变动|差额|增量", value[:period_match.start()])):
                        # Explicitly labeled same-clause comparison, e.g.
                        # '比率同期对照：2026中报1.588 vs 2025中报0.289'.
                        remainder_start = period_match.end()
                        remainder = tail
                    else:
                        # No local ratio label. The writer picks its own wording
                        # ('比值 0.7473') just as the script picks its own column
                        # names, so neither may gate the comparison. Fall back
                        # to numeric identity: only a last-digit neighbour of
                        # this period's product is a claim about that product.
                        values = products.get(_period(period_match.group()) or "", set())
                        if len(values) == 1 and period_match.start() not in parallel_values:
                            product = next(iter(values))
                            region = value[period_match.end():scope_end]
                            for token in re.finditer(rf"({_NUMBER})\s*({_RATIO_UNIT})?", region):
                                raw, unit = token[1], token[2] or ""
                                if _NON_RATIO_SUFFIX.match(value, period_match.end() + token.end()):
                                    continue
                                if _display_matches(raw, product, unit):
                                    continue
                                if not _near_miss(raw, unit, product):
                                    continue
                                start = period_match.end() + token.start(1)
                                findings.append(_prose_value_finding(
                                    clause.group(), start, start + len(raw),
                                    offset=offset + clause.start(),
                                    code="calculation_value_mismatch",
                                ))
                        continue
                    if period_match.start() in parallel_values:
                        number = parallel_values[period_match.start()]
                        numbers = [number] if number else []
                        # The ordered list owns only its slots. Extra numbers
                        # after the final slot are not assigned a guessed period.
                        residual = value[parallel_end:] if period_index == len(periods) - 1 else ""
                    else:
                        slot_start = remainder_start
                        if ratio is not None:
                            # This finite preface doesn't authorize arbitrary
                            # later numbers (revenue or another report period).
                            preface = re.match(r"\s*(?:创)?\d+(?:年|个?季|个?月)(?:新高|新低|高点|低点)[,，]\s*(?:实际|本期|比率)为", remainder)
                            if preface:
                                slot_start += preface.end()
                        numbers, consumed_end = _ratio_value_slots(value, slot_start, scope_end)
                        residual = value[consumed_end:scope_end]
                    values = products.get(_period(period_match.group()) or "", set())
                    marked = value[:period_match.start()].rstrip().endswith(_UNLOCATED_RATIO_MARK)
                    unlocated = marked or bool((values or require_product) and _has_unlocated_ratio_number(residual))
                    for number in numbers:
                        code = failure_code(values, number[2], number[3])
                        if code:
                            findings.append(_prose_value_finding(
                                clause.group(), number[0], number[1],
                                offset=offset + clause.start(), code=code,
                            ))
                    if unlocated:
                        # A pre-existing marker is still uncertainty until the
                        # writer resolves it; it never suppresses gap/repair.
                        findings.append(_unlocated_ratio_finding(
                            clause.group(), period_match.start(), offset=offset + clause.start(),
                        ))
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
