"""Finite financial contradictions, checked against bound structured observations.

These checks reject specific arithmetic/duration contradictions, not arbitrary
financial prose. They do not infer causes, fetch inputs, fix numbers silently,
or treat a successful calculation id as proof of every sentence in an answer.
Ambiguous subjects/versions are not resolved by picking a convenient value.
"""
from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import re

from intelligence.services.agent_research import AgentEvidence

_NUMBER = r"[+\-−]?\d+(?:\.\d+)?"
_PERIOD = re.compile(
    r"(?P<year>20\d{2})\s*年?\s*(?:"
    r"(?P<iso>-(?:03-31|06-30|09-30|12-31))|"
    r"(?P<label>一季报|一季度|中报|半年报|半年度|上半年|三季报|前三季度|年报|年度|全年|H1|Q[1-4]|FY))",
    re.IGNORECASE,
)
_MONTH = {"一季报": 3, "一季度": 3, "Q1": 3, "中报": 6, "半年报": 6,
          "半年度": 6, "上半年": 6, "H1": 6, "Q2": 6, "三季报": 9,
          "前三季度": 9, "Q3": 9, "年报": 12, "年度": 12, "全年": 12, "FY": 12, "Q4": 12}
_PERIOD_LABEL = re.compile("|".join(sorted(_MONTH, key=len, reverse=True)), re.I)
_RATIO = r"(?:含金量|净现比|OCF\s*[/／÷]\s*(?:归母)?净利(?:润)?|经营现金流对归母净利的覆盖率)"
_DELTA_UNIT = re.compile(r"百分点|基点|(?<![A-Za-z])bps?(?![A-Za-z])", re.I)
_RATIO_UNIT = r"个百分点|百分点|基点|bps?|百分比|%|倍"
_RATIO_VALUE = re.compile(
    rf"{_RATIO}\s*(?:[（(]\s*(?P<label_unit>{_RATIO_UNIT})\s*[）)])?"
    rf"\s*(?:约为|为|约|是|[：:=])?\s*(?P<value>{_NUMBER})\s*(?P<unit>{_RATIO_UNIT})?", re.I,
)
_COMPARISON = re.compile(r"同累计长度|同口径对照|降至|降到|回升|走弱|恶化|改善|较.+(?:升|降)")
_COMPARISON_CAVEAT = re.compile(r"(?:不能|不可|不宜|不应|不直接).{0,8}比较|仅.{0,6}列示|不据此判断")
_EQUATION = re.compile(rf"(?P<a>{_NUMBER})\s*[−-]\s*(?P<b>{_NUMBER})\s*[=＝]\s*(?P<result>{_NUMBER})")
_SINGLE_OCF = re.compile(
    rf"(?P<quarter>[二三四234])季度?单季经营(?:活动)?现金流(?:量净额)?"
    rf"(?:为|是|约为|约|[：:=])?\s*(?P<direction>净流出|净流入)?(?:约)?\s*(?P<value>{_NUMBER})\s*亿"
)
_STOCK_MOVE = re.compile(rf"(?P<a>{_NUMBER})\s*(?:亿元?|亿)?\s*→\s*(?P<b>{_NUMBER})")
_DURATION = re.compile(r"(?P<half>半年)(?!度|报)|(?P<months>[一二三四六九十\d]+)个月")
_CN_NUM = {"一": 1, "二": 2, "三": 3, "四": 4, "六": 6, "九": 9, "十": 10}
# 向**历史**基准比的条件（「不低于两期中较低值」「回到上期水平」）。未来数据未到手是正常的，
# 但基准取不到时，条件到复查日也无法被评判——看着可证伪，实际不可证伪。
_BASELINE_COMPARISON = re.compile(
    r"(?:不低于|不高于|低于|高于|回升至?|回到|恢复至|超过|达到)[^，,。；;、]{0,8}?"
    r"(?P<scope>最近两期|前两期|两期中|两期|上一期|上期|同期)[^，,。；;、]{0,6}?"
    r"(?:较低值|较高值|均值|平均值|水平|值|数)"
)
_BASELINE_SCOPE_PERIODS = {
    "最近两期": 2, "前两期": 2, "两期中": 2, "两期": 2,
    "上一期": 1, "上期": 1, "同期": 1,
}


def _decimal(raw: object) -> Decimal | None:
    try:
        value = Decimal(str(raw).replace("−", "-"))
        return value if value.is_finite() else None
    except InvalidOperation:
        return None


def _same_display(expected: Decimal, shown: str) -> bool:
    actual = _decimal(shown)
    if actual is None:
        return False
    # The claim's displayed precision is the tolerance, not a hard-coded epsilon.
    try:
        return expected.quantize(Decimal(1).scaleb(actual.as_tuple().exponent), rounding=ROUND_HALF_UP) == actual
    except InvalidOperation:
        # An absurd displayed precision is not a license to crash publication.
        return False


def _subject(value: str) -> str:
    return value.upper().removesuffix(".SZ").removesuffix(".SH").removesuffix(".BJ")


def _periods(text: str) -> list[tuple[int, int, str]]:
    periods = []
    for match in _PERIOD.finditer(text):
        month = int(match["iso"][1:3]) if match["iso"] else _MONTH[match["label"].upper()]
        day = 31 if month in (3, 12) else 30
        periods.append((match.start(), match.end(), f"{match['year']}-{month:02}-{day}"))
    return periods


def _observations(evidence: Sequence[AgentEvidence], bound: set[str], subject: str | None):
    items = [item for item in evidence if item.tool == "financial_data" and item.content_hash in bound]
    subjects = {_subject(obs.subject) for item in items for obs in item.observations}
    target = _subject(subject or "")
    if target not in subjects:
        matches = {_subject(obs.subject) for item in items if subject and subject in item.title
                   for obs in item.observations}
        if len(matches) != 1:
            return {}
        target = matches.pop()
    values: dict[tuple[str, str], set[Decimal]] = {}
    for item in items:
        for obs in item.observations:
            value = _decimal(obs.value)
            try:
                date.fromisoformat(obs.as_of)
            except ValueError:
                continue
            if _subject(obs.subject) == target and value is not None:
                values.setdefault((obs.as_of, obs.metric), set()).add(value)
    return {key: next(iter(group)) for key, group in values.items() if len(group) == 1}


def calculation_ratio_gaps(
    evidence: Sequence[AgentEvidence], bound_hashes: Sequence[str], *, subject: str | None,
) -> tuple[str, ...]:
    """Cross-check named ratio result cells using their own finite input chain.

    The renderer encodes table columns as table.column[row label]. Ignore
    non-ratio columns even in a table named '净现比', and never use calc.as_of
    as the report period (it is the oldest input's disclosure date).
    """
    bound = set(bound_hashes)
    gaps = []
    for item in evidence:
        if item.tool != "derived_calculation" or item.content_hash not in bound:
            continue
        inputs = [row for row in evidence if row.content_hash in item.derived_from]
        input_subjects = {_subject(obs.subject) for row in inputs for obs in row.observations
                          if obs.metric in {"ocf_cum_yi", "net_profit_cum_yi"}}
        if len(input_subjects) != 1:
            # Product rows have no typed company key. Do not assign a peer's
            # result to the requested company, even when both inputs exist.
            continue
        values = _observations(inputs, set(item.derived_from), subject)
        for obs in item.observations:
            column = obs.metric.split("[", 1)[0].rsplit(".", 1)[-1]
            if not re.search(_RATIO, column, re.I) or re.search(r"同比|环比|增长|增速|变化|变动|差额|增量", column):
                continue
            label = obs.metric.rsplit("[", 1)[-1].rstrip("]") if "[" in obs.metric else obs.metric
            periods = {period for _start, _end, period in _periods(label)}
            if len(periods) != 1:
                continue
            period = periods.pop()
            ocf, profit = values.get((period, "ocf_cum_yi")), values.get((period, "net_profit_cum_yi"))
            if ocf is not None and profit and _DELTA_UNIT.search(column):
                gaps.append(f"计算产物 {item.source.removeprefix('sandbox:')} 的 {obs.metric} 使用差值单位，不适用于绝对比例核验")
                continue
            multiplier = 100 if "%" in column or "百分比" in column else 1
            if ocf is not None and profit and not _same_display(ocf / profit * multiplier, str(obs.value)):
                gaps.append(f"计算产物 {item.source.removeprefix('sandbox:')} 的 {obs.metric} 与同报告期原始输入复算不一致")
    return tuple(dict.fromkeys(gaps))


def comparison_baseline_gaps(
    sentences: Sequence[dict[str, object]], evidence: Sequence[AgentEvidence],
    bound_hashes: Sequence[str], *, subject: str | None,
) -> tuple[str, ...]:
    """Flag conditions whose *historical* comparison baseline was never obtained.

    A watch condition may reference data that does not exist yet -- that is what
    a watch is for. What it may not do is compare against a prior-period baseline
    this answer never bound: at recheck time there is nothing to compare with, so
    the condition only looks falsifiable. Clauses carrying a literal value stay
    with the existing numeric-support gate, qualitative conditions are untouched,
    and a peer company's readings never stand in for the requested subject.
    """
    bound = set(bound_hashes)
    values = _observations(evidence, bound, subject)
    if not values:
        # 契约主体常写中文名（「中际旭创」），而带读数的证据标题里只有代码；
        # 含公司名的那条往往是 0 读数的表头，标题反查因此落空（实测于封存回合
        # 8792-boundary-retest-20260918/positive-persistence）。仅当已绑定读数只指向
        # **一个**主体时回退；同业对比等多主体场景继续失败关闭，不猜。
        subjects = {
            obs.subject for item in evidence
            if item.tool == "financial_data" and item.content_hash in bound
            for obs in item.observations
        }
        if len(subjects) != 1:
            return ()
        values = _observations(evidence, bound, subjects.pop())
        if not values:
            return ()
    available = {
        period for period, metric in values
        if metric == "ocf_cum_yi" and (period, "net_profit_cum_yi") in values
    }
    gaps = []
    for sentence in sentences:
        text = str(sentence.get("text") or "").replace("**", "").replace("__", "")
        for clause in re.split(r"[，,。；;、]", text):
            if re.search(r"\d", clause):
                continue
            ratio = re.search(_RATIO, clause, re.I)
            match = _BASELINE_COMPARISON.search(clause)
            if ratio is None or match is None:
                continue
            required = _BASELINE_SCOPE_PERIODS[match["scope"]]
            if len(available) >= required:
                continue
            gaps.append(
                f"触发条件「{match[0]}」依赖{ratio[0]}的历史比较基准，"
                f"但已绑定证据只够算 {len(available)} 期、需要 {required} 期"
            )
    return tuple(dict.fromkeys(gaps))


def _relative_ratio_comparison_mismatch(text: str) -> bool:
    """Carry a level's period into a same-sentence '较/相较于' counterpart.

    Callers segment sentences, so this only spans clauses inside one sentence.
    Keep it separate from generic previous-period context: an inventory or
    revenue clause is not a ratio anchor. A comparison whose antecedent is
    ambiguous stays deferred rather than guessed in either direction.
    """
    ratio_period: str | None = None
    for segment in re.split(r"但是|但|然而|却", text):
        caveat = bool(_COMPARISON_CAVEAT.search(segment))
        for clause in re.split(r"[，,]", segment):
            if not clause.strip():
                continue
            periods = _periods(clause)
            relative = re.match(r"\s*(?:相较于?|相比于?|较)", clause)
            if len(periods) != 1:
                if not _COMPARISON_CAVEAT.search(clause):
                    ratio_period = None
                continue
            start, end, period = periods[0]
            tail = clause[end:].lstrip().removeprefix("累计").lstrip()
            level = _RATIO_VALUE.match(tail)
            value = level or re.match(rf"(?:的)?\s*{_NUMBER}(?![\d.])", tail)
            # A named metric after the number ends the narrow ellipsis,
            # e.g. '较2025全年1.009亿元收入增长'.
            counterpart = value and re.match(
                r"\s*(?:倍|%)?\s*(?:明显|显著|有所)?\s*(?:走弱|恶化|改善|回升|上升|升|下降|降)",
                tail[value.end():],
            )
            if (relative and not clause[relative.end():start].strip()
                    and counterpart and ratio_period and not caveat
                    and _COMPARISON.search(clause) and "单季" not in clause):
                if period[5:7] != ratio_period[5:7]:
                    return True
            # Only an explicitly named ratio level anchors a later clause: a
            # bare number does not establish which metric it is. A caveat
            # without a dated fact may carry across 'but'; anything else clears.
            ratio_period = period if level and "单季" not in clause else None
    return False


def financial_claim_mismatches(
    sentences: Sequence[dict[str, object]], evidence: Sequence[AgentEvidence],
    bound_hashes: Sequence[str], *, subject: str | None,
) -> tuple[int, ...]:
    """Return sentence indexes with a provable, scoped numeric/period mismatch.

    Supported shapes: explicit subtraction; period-labelled OCF/profit ratio;
    uniquely dated single-quarter OCF; inventory endpoints plus elapsed months;
    cumulative-ratio comparisons across unequal lengths. No general NLP claim.
    """
    values = _observations(evidence, set(bound_hashes), subject)
    if not values:
        return ()
    rejected = []
    previous_period: str | None = None
    for sentence in sentences:
        index = sentence.get("index")
        text = str(sentence.get("text") or "").replace("**", "").replace("__", "")
        if not isinstance(index, int):
            continue
        periods = _periods(text)
        if re.search(r"(?:假设|例如|举例|反例|错误写法).{0,8}[：:]|(?:不是|并非).{0,8}[=＝]", text):
            # Quoted counterexamples are not presented as computed results.
            continue
        mentioned_codes = set(re.findall(r"(?<!\d)[0368]\d{5}(?!\d)", text))
        if mentioned_codes and mentioned_codes != {_subject(subject or "")}:
            # Do not use the requested company's inputs to disprove a peer.
            continue
        bad = False
        financial = bool(re.search(r"现金流|OCF|存货|净利润", text, re.I) or re.search(_RATIO, text, re.I))
        if financial:
            bad |= _relative_ratio_comparison_mismatch(text)
            for equation in _EQUATION.finditer(text):
                a, b = _decimal(equation["a"]), _decimal(equation["b"])
                if a is not None and b is not None:
                    bad |= not _same_display(a - b, equation["result"])
            for ratio in _RATIO_VALUE.finditer(text):
                preceding = [item for item in periods if item[1] <= ratio.start()]
                # Only an explicitly labelled ratio is recomputed. A nearer
                # yearless label must not borrow a DIFFERENT period's inputs;
                # skip ambiguity rather than guessing a report year.
                if not preceding:
                    continue
                _start, end, period = preceding[-1]
                if _PERIOD_LABEL.search(text[end:ratio.start()]):
                    continue
                ocf = values.get((period, "ocf_cum_yi"))
                profit = values.get((period, "net_profit_cum_yi"))
                if ocf is not None and profit:
                    unit, label_unit = ratio["unit"] or "", ratio["label_unit"] or ""
                    if _DELTA_UNIT.search(unit) or _DELTA_UNIT.search(label_unit):
                        bad = True
                    else:
                        multiplier = 100 if (unit or label_unit) in {"%", "百分比"} else 1
                        bad |= not _same_display(ocf / profit * multiplier, ratio["value"])
            for quarter in _SINGLE_OCF.finditer(text):
                q = _CN_NUM.get(quarter["quarter"], int(quarter["quarter"]) if quarter["quarter"].isdigit() else 0)
                end_month, start_month = q * 3, (q - 1) * 3
                pairs = []
                preceding = [p for start, _end, p in periods if start < quarter.start()]
                # A following annual comparison cannot change which year's Q2
                # the preceding cumulative values describe.
                anchor = preceding[-1] if preceding else None
                for (period, metric), value in values.items():
                    if metric != "ocf_cum_yi" or int(period[5:7]) != end_month:
                        continue
                    if anchor and period[:4] != anchor[:4]:
                        continue
                    prior = f"{period[:4]}-{start_month:02}-{'31' if start_month == 3 else '30'}"
                    if (prior, metric) in values:
                        pairs.append(value - values[prior, metric])
                if len(pairs) == 1:
                    expected = -pairs[0] if quarter["direction"] == "净流出" else pairs[0]
                    bad |= not _same_display(expected, quarter["value"])
            if "存货" in text and (duration := _DURATION.search(text)):
                months_text = duration["months"] or ""
                months = 6 if duration["half"] else _CN_NUM.get(months_text, int(months_text) if months_text.isdigit() else 0)
                for move in _STOCK_MOVE.finditer(text):
                    endpoints = []
                    for group in ("a", "b"):
                        endpoints.append([p for (p, metric), value in values.items()
                                          if metric == "inventory_yi" and _same_display(value, move[group])])
                    if all(len(dates) == 1 for dates in endpoints) and months:
                        first, last = (date.fromisoformat(dates[0]) for dates in endpoints)
                        actual_months = (last.year - first.year) * 12 + last.month - first.month
                        bad |= actual_months != months
            # A disclaimer before 'but' cannot excuse the assertion after it.
            # Nor may an annual reference in an unrelated clause contaminate a
            # correctly labelled H1/H1 comparison. Only borrow local context for
            # an explicitly elided counterpart, or 'same cumulative length'.
            context_period = previous_period
            for segment in re.split(r"但是|但|然而|却", text):
                for clause in re.split(r"[，,；;]", segment):
                    clause_periods = _periods(clause)
                    if (re.search(_RATIO, clause, re.I) and _COMPARISON.search(clause)
                            and not _COMPARISON_CAVEAT.search(segment) and "单季" not in clause):
                        months = {int(p[5:7]) for _s, _e, p in clause_periods}
                        months.update(_MONTH[m.group().upper()] for m in _PERIOD_LABEL.finditer(clause))
                        if (len(months) == 1 and context_period
                                and re.search(r"同累计长度|从.+(?:降至|降到|回升)", clause)):
                            months.add(int(context_period[5:7]))
                        bad |= len(months) > 1
                    if clause_periods:
                        context_period = clause_periods[-1][2]
        if periods and financial:
            previous_period = periods[-1][2]
        if bad:
            rejected.append(index)
    return tuple(rejected)
