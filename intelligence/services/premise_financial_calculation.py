"""Bounded, source-bound financial arithmetic for explicit user exercises.

This is not a financial fact source or a general natural-language parser. The
supported grammar is inline annual amounts with explicit units, one company,
and explicit cross-turn replacements. Unknown/ambiguous inputs stay gaps.
Only trusted user records enter; model prose never supplies calculation inputs.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from typing import TYPE_CHECKING
import hashlib
import math
import re

from intelligence.services.sandbox_fincalc import pct, pct_change, safe_div, to_yi
from intelligence.services.user_task import _protected_layout

if TYPE_CHECKING:
    from intelligence.services.task_frame import TaskFrame

CALCULATION_MARKER = "[[PREMISE_CALCULATION]]"
_SCHEMA = "premise_financial_calculation/v1"
_NUMBER = r"[+-]?(?:\d+(?:\.\d+)?|\.\d+)"
_METRICS = {
    "经营活动现金流量净额": "cash_flow",
    "经营现金流": "cash_flow",
    "归母净利润": "profit",
    "营业收入": "revenue",
    "收入": "revenue",
    "总股本": "shares",
    "股本": "shares",
    "股价": "price",
}
_AMOUNT = re.compile(
    r"(?P<metric>" + "|".join(_METRICS) + r")\s*"
    r"(?:(?:由|从)(?P<old_value>"
    + _NUMBER
    + r")(?P<old_unit>亿元|万元|元|亿股|万股|股)\s*)?"
    r"(?:改为|改成|更正为|调整为|为|是|[:：=])?\s*"
    r"(?P<approx>约|大约|超过|不足)?(?P<value>" + _NUMBER + r")\s*"
    r"(?P<unit>亿美元|亿元|百万元|万元|千元|元|亿股|万股|股)"
)
_QUANTITY = re.compile(
    r"(?P<value>"
    + _NUMBER
    + r")\s*(?P<unit>亿美元|亿元|百万元|万元|千元|元|亿股|万股|股|%)"
)
_MONEY_UNIT = re.compile(r"亿美元|亿元|百万元|万元|千元|元|亿(?!股)")
_YEAR = re.compile(r"(?P<year>(?:19|20)\d{2})年")
_SUBJECT = re.compile(
    r"(?:^|[。；;\n])\s*(?:更正[:：]\s*)?([^。；;\n，、：:]{1,24}公司)"
)
_REPLACEMENT = re.compile(r"改为|改成|更正|调整为|修改")
_NATURE = re.compile(r"预测|预计|预期|假设|实际|已实现")
_NON_ANNUAL = re.compile(r"上半年|下半年|半年|季度|单季|前三季|Q[1-4]|[一二三四]季")
_EXPLICIT_BASIS = re.compile(
    r"(?:用|按|以)\s*((?:19|20)\d{2})年(?:的)?归母净利润.{0,12}(?:计算|算|作为).{0,12}静态市盈率"
)
_SCENARIO = re.compile(
    r"(?:下一年|次年|明年)归母净利润(?P<direction>下降|减少|增长|增加)(?P<rate>"
    + _NUMBER
    + r")%"
)


@dataclass(frozen=True)
class PremiseSource:
    source_message_id: str
    text: str

    @classmethod
    def from_dict(cls, value: object) -> PremiseSource:
        if not isinstance(value, dict) or set(value) != {"source_message_id", "text"}:
            raise ValueError("invalid user premise source")
        if any(
            not isinstance(item, str) or not item.strip() for item in value.values()
        ):
            raise ValueError("empty user premise source")
        return cls(**value)


@dataclass(frozen=True)
class FinancialInput:
    ref: str
    source_message_id: str
    source_hash: str
    start: int
    end: int
    source_text: str
    subject: str
    period: int | None
    metric: str
    nature: str
    value: float
    unit: str


@dataclass(frozen=True)
class CalculationRow:
    metric: str
    label: str
    formula: str
    value: float | None
    unit: str
    input_refs: tuple[str, ...]
    note: str = ""


def _fmt(value: float | None) -> str:
    return "不适用" if value is None else f"{value:.4f}".rstrip("0").rstrip(".")


@dataclass(frozen=True)
class PremiseCalculation:
    sources: tuple[PremiseSource, ...]
    reference_year: int
    inputs: tuple[FinancialInput, ...]
    rows: tuple[CalculationRow, ...]
    issues: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        # JSON normalization keeps the persisted contract byte-comparable on replay.
        return {
            "schema": _SCHEMA,
            "reference_year": self.reference_year,
            "sources": [asdict(source) for source in self.sources],
            "inputs": [asdict(item) for item in self.inputs],
            "rows": [
                {**asdict(row), "input_refs": list(row.input_refs)} for row in self.rows
            ],
            "issues": list(self.issues),
        }

    @classmethod
    def from_dict(cls, value: object) -> PremiseCalculation:
        if not isinstance(value, dict) or value.get("schema") != _SCHEMA:
            raise ValueError("invalid premise calculation schema")
        sources = value.get("sources")
        year = value.get("reference_year")
        if (
            not isinstance(sources, list)
            or type(year) is not int
            or not 1900 <= year <= 2100
        ):
            raise ValueError("invalid premise calculation source collection/year")
        rebuilt = compile_calculation(
            tuple(PremiseSource.from_dict(source) for source in sources),
            reference_year=year,
        )
        if rebuilt.to_dict() != value:
            raise ValueError("premise calculation does not match original user sources")
        return rebuilt

    @property
    def table(self) -> str:
        lines = ["按题设计算：", "| 指标 | 公式与基数 | 结果 |", "| --- | --- | --- |"]
        for row in self.rows:
            result = _fmt(row.value) + (row.unit if row.value is not None else "")
            lines.append(
                f"| {row.label} | {row.formula} | {result}{'；' + row.note if row.note else ''} |"
            )
        if not self.rows:
            lines = ["题设计算暂缺可确认的完整输入。"]
        if any(row.metric.startswith("scenario_") for row in self.rows):
            lines.append("情景结果仅表示假设成立时的计算，不是盈利预测。")
        if self.issues:
            lines.append("待明确：" + "；".join(self.issues) + "。")
        return "\n".join(lines)

    def admit(self, draft: str, *, status: str) -> tuple[str, str]:
        if self.issues and status == "completed":
            return draft, "题设计算存在未明确输入：" + "；".join(self.issues)
        if draft.count(CALCULATION_MARKER) == 1 and self.table not in draft:
            outside = draft.replace(CALCULATION_MARKER, "")
            rendered = draft.replace(CALCULATION_MARKER, self.table)
        elif draft.count(self.table) == 1 and CALCULATION_MARKER not in draft:
            outside = draft.replace(self.table, "")
            rendered = draft
        else:
            return (
                draft,
                "计算表缺失或被改写；请在 draft 中原样保留一次 " + CALCULATION_MARKER,
            )
        review = self.review_prose(outside)
        if review["conflicts"]:
            return draft, "表外数字与题设计算冲突：" + "；".join(review["conflicts"])
        by_metric = {row.metric: row.value for row in self.rows}
        if (
            (by_metric.get("profit_yoy") or 0) > 0
            and (by_metric.get("revenue_yoy") or 0) > 0
            and "增收不增利" in outside
        ):
            return draft, "收入和利润同比均增长，不能写成增收不增利"
        return rendered, ""

    def review_prose(self, text: str) -> dict[str, object]:
        """Proven contradictions block; unparsed prose is not a mechanical pass."""
        text = text.replace(self.table, "").replace(CALCULATION_MARKER, "")
        aliases = {
            "revenue_yoy": r"收入(?:同比增速|同比增长率|同比)",
            "profit_yoy": r"(?:归母)?净利润(?:同比增速|同比增长率|同比)",
            "cash_profit_ratio": r"经营现金流(?:/|与)(?:归母)?净利润(?:的)?(?:比值|比率)?",
            "market_cap": r"(?:当前)?总市值",
            "static_pe": r"静态市盈率",
            "margin_change": r"(?:归母)?净利率",
            "scenario_pe": r"情景市盈率",
            "scenario_profit": r"(?:下一年|次年|假设)(?:的)?归母净利润",
        }
        covered: set[int] = set()
        conflicts: list[str] = []
        latest_margin = max(
            (
                row.metric
                for row in self.rows
                if re.fullmatch(r"margin_\d{4}", row.metric)
            ),
            default="",
        )
        for row in self.rows:
            if row.value is None:
                continue
            alias = aliases.get(row.metric)
            year = re.match(r"(\d{4})年", row.label)
            if row.metric.startswith("margin_") and row.metric != "margin_change":
                alias = r"(?:归母)?净利率"
            if not alias:
                continue
            year_prefix = ""
            if year:
                year_prefix = re.escape(year[0]) + r"(?:的)?"
                if row.metric == latest_margin or not row.metric.startswith("margin_"):
                    year_prefix = "(?:" + year_prefix + ")?"
            pattern = re.compile(
                year_prefix + alias + r"(?P<link>[^\d。；;，,\n|]{0,12}?)"
                r"(?P<value>" + _NUMBER + r")\s*(?:\*\*)?" + re.escape(row.unit)
            )
            for match in pattern.finditer(text):
                # Transitions, paired lists and qualified alternatives are not
                # scalar assertions about the current result.
                clause_prefix = re.split(r"[。；;，,\n]", text[: match.start()])[-1]
                if (
                    re.search(
                        r"由|从|至|不是|并非|不等于|高于|低于|原来|过去|此前|上轮",
                        match["link"],
                    )
                    or re.search(
                        r"假设|如果|若|此前|上轮|\d{4}\s*[/、]\s*$", clause_prefix
                    )
                    or re.match(r"\s*[/、]\s*\d", text[match.end() :])
                ):
                    continue
                expected = row.value
                preceding_year = re.search(r"(\d{4})年(?:的)?$", text[: match.start()])
                expected_years = {
                    item.period
                    for item in self.inputs
                    if item.ref in row.input_refs and item.period is not None
                }
                if preceding_year and year and preceding_year[1] != year[1]:
                    continue
                if preceding_year and int(preceding_year[1]) not in expected_years:
                    conflicts.append(preceding_year[0] + match[0])
                    continue
                number = float(match["value"])
                falling = bool(re.search(r"下降|降低|减少|下滑", match["link"]))
                rising = bool(re.search(r"上升|提高|增加|增长", match["link"]))
                is_change = row.metric.endswith("_yoy") or row.metric == "margin_change"
                if (falling or rising) and not is_change:
                    previous = next(
                        (
                            item
                            for item in self.rows
                            if year and item.metric == f"margin_{int(year[1]) - 1}"
                        ),
                        None,
                    )
                    if (
                        row.metric != latest_margin
                        or previous is None
                        or previous.value in {None, 0}
                    ):
                        continue
                    expected = pct_change(row.value, previous.value, digits=None)
                if falling:
                    if number < 0:
                        conflicts.append(match[0])
                        continue
                    number = -number
                if rising and number < 0:
                    conflicts.append(match[0])
                    continue
                decimals = len(match["value"].partition(".")[2])
                tolerance = 0.5 * 10**-decimals + 1e-9
                if not math.isclose(number, expected, rel_tol=0, abs_tol=tolerance):
                    conflicts.append(match[0])
                    continue
                covered.update(range(match.start(), match.end()))
                if row.metric == "cash_profit_ratio":
                    comparison = re.match(
                        r"[，,\s]*(低于|高于|等于)100%", text[match.end() :]
                    )
                    if comparison:
                        if not {
                            "低于": row.value < 100,
                            "高于": row.value > 100,
                            "等于": row.value == 100,
                        }[comparison[1]]:
                            conflicts.append(match[0] + comparison[0])
                        else:
                            covered.update(
                                range(match.end(), match.end() + comparison.end())
                            )
        by_metric = {row.metric: row for row in self.rows}
        pe, cap = by_metric.get("static_pe"), by_metric.get("market_cap")
        if pe and cap and pe.value is not None:
            profit = next(
                item
                for item in self.inputs
                if item.ref in pe.input_refs and item.metric == "profit"
            )
            formula = re.compile(
                r"静态市盈率\s*[:：=为]*\s*("
                + _NUMBER
                + r")\s*/\s*("
                + _NUMBER
                + r")\s*=\s*("
                + _NUMBER
                + r")倍"
            )
            for match in formula.finditer(text):
                actual = tuple(float(match[index]) for index in (1, 2, 3))
                if actual[:2] != (cap.value, profit.value) or not math.isclose(
                    actual[2], pe.value, rel_tol=0, abs_tol=0.0001
                ):
                    conflicts.append(match[0])
                else:
                    covered.update(range(match.start(), match.end()))
        unverified = [
            match[0].strip()
            for match in re.finditer(r"[^。！？\n]+", text)
            if any(
                text[index].isdigit() and index not in covered
                for index in range(match.start(), match.end())
            )
        ]
        return {
            "conflicts": list(dict.fromkeys(conflicts)),
            "unverified_numeric_fragments": list(dict.fromkeys(unverified)),
            "scope": "owned_table_and_recognized_result_restatements_only",
        }


def _visible(text: str) -> str:
    lines, _, _ = _protected_layout(text.split("\n"))
    return "\n".join(lines)


def calculation_for_frame(
    frame: TaskFrame, *, today: str | None = None
) -> PremiseCalculation | None:
    material = frame.material_contract
    if not material or not material.premise_calculation:
        return None
    history = frame.conversation_materials
    sources = (
        history.calculation_sources
        if (material.continuation_requested and history and not history.unavailable)
        else ()
    )
    if (
        not any("静态市盈率" in source.text for source in sources)
        and "静态市盈率" not in frame.raw_question
    ):
        return None
    # Current input is anchored to raw_question and its frame hash. Historical
    # inputs carry their persisted message IDs; "current" is not a fake DB ID.
    sources = (*sources, PremiseSource("current", frame.raw_question))
    reference_year = date.fromisoformat(today[:10]).year if today else date.today().year
    return compile_calculation(sources, reference_year=reference_year)


def compile_calculation(
    sources: tuple[PremiseSource, ...], *, reference_year: int
) -> PremiseCalculation:
    """Rebuild from original users each time; no derived value becomes an input."""
    active: dict[tuple[str, int | None, str, str], FinancialInput] = {}
    issues: list[str] = []
    subjects: set[str] = set()
    for source in sources:
        visible = _visible(source.text)
        digest = hashlib.sha256(source.text.encode()).hexdigest()
        declared = {match[1].strip() for match in _SUBJECT.finditer(visible)}
        # A continuation may mention a known company in prose; it cannot rename it.
        declared = {
            name for name in declared if not any(old in name for old in subjects)
        }
        subjects.update(declared)
        if len(subjects) != 1:
            issues.append("只支持主体明确的单公司算例，请分开列明各公司输入")
            continue
        subject = next(iter(subjects))
        consumed = [(match.start(), match.end()) for match in _AMOUNT.finditer(visible)]
        consumed.extend(
            (match.start(), match.end()) for match in _SCENARIO.finditer(visible)
        )
        for clause_match in re.finditer(r"[^。；;\n]+", visible):
            clause = clause_match[0]
            matches = list(_AMOUNT.finditer(clause))
            for match in matches:
                metric = _METRICS[match["metric"]]
                prefix = clause[: match.start()]
                years = list(_YEAR.finditer(prefix))
                year = int(years[-1]["year"]) if years else None
                period_scope = prefix[years[-1].start() :] if years else prefix
                if years:
                    preceding_nature = re.search(
                        r"(预测|预计|预期|假设|实际|已实现)\s*$",
                        prefix[: years[-1].start()],
                    )
                    if preceding_nature:
                        period_scope = preceding_nature[0] + period_scope
                nature_matches = list(_NATURE.finditer(period_scope))
                nature_word = nature_matches[-1][0] if nature_matches else "实际"
                nature = (
                    "forecast"
                    if nature_word in {"预测", "预计", "预期"}
                    else "scenario"
                    if nature_word == "假设"
                    else "actual"
                )
                period = year
                if metric in {"price", "shares"} and (
                    "如果" in prefix or "假设" in prefix
                ):
                    issues.append("情景中的股价或股本变更需单独明确，不能覆盖当前值")
                    continue
                if metric in {"price", "shares"} and ("当前" in prefix or year is None):
                    period, nature = None, "current"
                if metric in {"revenue", "profit", "cash_flow"} and (
                    year is None or _NON_ANNUAL.search(period_scope)
                ):
                    issues.append(f"{match['metric']}未明确完整年度")
                    continue
                if year is not None and year >= reference_year and nature == "actual":
                    issues.append(f"{year}年尚不是已完成年度，需明确实际期间或预测性质")
                    continue
                unit, number = match["unit"], float(match["value"])
                if match["approx"] or not math.isfinite(number):
                    issues.append(f"{match['metric']}不是精确有限输入")
                    continue
                if metric == "shares":
                    scale = {"亿股": 1.0, "万股": 0.0001, "股": 1e-8}.get(unit)
                    value = number * scale if scale is not None else None
                    canonical_unit = "亿股"
                elif metric == "price":
                    value = number if unit == "元" else None
                    canonical_unit = "元"
                else:
                    value, canonical_unit = to_yi(number, unit), "亿元"
                if value is None or not math.isfinite(value):
                    issues.append(f"{match['metric']}单位无法换算：{unit}")
                    continue
                if metric in {"shares", "price"} and value <= 0:
                    issues.append(f"{match['metric']}必须为正数")
                    continue
                start, end = (
                    clause_match.start() + match.start(),
                    clause_match.start() + match.end(),
                )
                item = FinancialInput(
                    f"P:{digest}:{start}:{end}",
                    source.source_message_id,
                    digest,
                    start,
                    end,
                    source.text[start:end],
                    subject,
                    period,
                    metric,
                    nature,
                    value,
                    canonical_unit,
                )
                key = (subject, period, metric, nature)
                old = active.get(key)
                if match["old_value"] is not None:
                    old_number, old_unit = float(match["old_value"]), match["old_unit"]
                    claimed_old = (
                        (old_number if old_unit == "元" else None)
                        if metric == "price"
                        else (
                            old_number
                            * {"亿股": 1.0, "万股": 0.0001, "股": 1e-8}.get(
                                old_unit, math.nan
                            )
                            if metric == "shares"
                            else to_yi(old_number, old_unit)
                        )
                    )
                    if old is None or claimed_old != old.value:
                        issues.append(f"{match['metric']}变更所称原值与可信历史不一致")
                        continue
                if (
                    old is not None
                    and old.value != value
                    and not _REPLACEMENT.search(clause)
                ):
                    issues.append(
                        f"{period or '当前'}{match['metric']}有冲突，需明确更正"
                    )
                    continue
                active[key] = item
        for quantity in _QUANTITY.finditer(visible):
            if any(
                start <= quantity.start() and quantity.end() <= end
                for start, end in consumed
            ):
                continue
            # A repeated price in '24元股价均不变' is a constraint, not a new value.
            unchanged = re.match(r"股价(?:均)?不变", visible[quantity.end() :])
            price = active.get((subject, None, "price", "current"))
            if (
                unchanged
                and quantity["unit"] == "元"
                and price
                and float(quantity["value"]) == price.value
            ):
                consumed.append((quantity.start(), quantity.end()))
                continue
            issues.append("存在未解析或冲突的数值前提：" + quantity[0])
        if any(
            not any(
                start <= unit.start() and unit.end() <= end for start, end in consumed
            )
            for unit in _MONEY_UNIT.finditer(visible)
        ):
            issues.append("存在未解析的金额或单位，需明确为带单位的数值输入")
    inputs = tuple(active.values())
    if len(subjects) != 1:
        return PremiseCalculation(
            sources, reference_year, inputs, (), tuple(dict.fromkeys(issues))
        )
    actual = {
        (item.period, item.metric): item for item in inputs if item.nature == "actual"
    }
    current = {item.metric: item for item in inputs if item.nature == "current"}
    years = sorted({period for period, _ in actual if period is not None})
    latest = years[-1] if years else None
    text = _visible(sources[-1].text) if sources else ""
    basis_year = latest
    for source in sources:
        instruction = _visible(source.text)
        selected = list(_EXPLICIT_BASIS.finditer(instruction))
        if selected:
            basis_year = int(selected[-1][1])
        elif re.search(r"(?:改用|恢复|回到)(?:最近|最新)", instruction):
            basis_year = latest
    profit = actual.get((basis_year, "profit"))
    price, shares = current.get("price"), current.get("shares")
    rows: list[CalculationRow] = []

    def add(metric, label, formula, value, unit, inputs_used, note=""):
        if value is not None and not math.isfinite(value):
            issues.append(label + "计算结果超出有限数值范围")
            value = None
        rows.append(
            CalculationRow(
                metric,
                label,
                formula,
                value,
                unit,
                tuple(item.ref for item in inputs_used),
                note,
            )
        )

    if latest is not None:
        for metric, label in (("revenue", "收入"), ("profit", "归母净利润")):
            new, old = actual.get((latest, metric)), actual.get((latest - 1, metric))
            if new and old:
                add(
                    metric + "_yoy",
                    f"{latest}年{label}同比",
                    f"({_fmt(new.value)} - {_fmt(old.value)}) / abs({_fmt(old.value)}) × 100%",
                    pct_change(new.value, old.value, digits=None),
                    "%",
                    (new, old),
                )
        margins = []
        for year in years:
            revenue, annual_profit = (
                actual.get((year, "revenue")),
                actual.get((year, "profit")),
            )
            if revenue and annual_profit:
                margin = pct(annual_profit.value, revenue.value, digits=None)
                add(
                    f"margin_{year}",
                    f"{year}年归母净利率",
                    f"{_fmt(annual_profit.value)} / {_fmt(revenue.value)} × 100%",
                    margin,
                    "%",
                    (annual_profit, revenue),
                )
                margins.append(rows[-1])
        if len(margins) >= 2 and all(row.value is not None for row in margins[-2:]):
            before, after = margins[-2:]
            rows.append(
                CalculationRow(
                    "margin_change",
                    "归母净利率变化",
                    f"{_fmt(after.value)}% - {_fmt(before.value)}%",
                    round(after.value - before.value, 10),
                    "个百分点",
                    before.input_refs + after.input_refs,
                )
            )
        cash, annual_profit = (
            actual.get((latest, "cash_flow")),
            actual.get((latest, "profit")),
        )
        if cash and annual_profit:
            add(
                "cash_profit_ratio",
                f"{latest}年经营现金流/归母净利润",
                f"{_fmt(cash.value)} / {_fmt(annual_profit.value)} × 100%",
                pct(cash.value, annual_profit.value, digits=None),
                "%",
                (cash, annual_profit),
            )
    if not price or not shares:
        issues.append("缺少明确的当前股价或总股本")
    if profit is None:
        issues.append(
            "缺少选定的最近已完成年度归母净利润，不能自行回退旧年度或使用预测值"
        )
    if price and shares:
        cap = price.value * shares.value
        add(
            "market_cap",
            "当前总市值",
            f"{_fmt(price.value)}元 × {_fmt(shares.value)}亿股",
            cap,
            "亿元",
            (price, shares),
        )
        if profit and not issues:
            pe = safe_div(cap, profit.value) if profit.value > 0 else None
            add(
                "static_pe",
                "静态市盈率",
                f"{_fmt(cap)}亿元 / {basis_year}年归母净利润{_fmt(profit.value)}亿元",
                pe,
                "倍",
                (price, shares, profit),
                "利润非正，市盈率不适用" if pe is None else "",
            )
            scenarios = list(_SCENARIO.finditer(text))
            if len(scenarios) > 1:
                issues.append("多个情景需分别明确输入与适用范围")
            elif scenarios:
                scenario = scenarios[0]
                rate = float(scenario["rate"])
                sign = -1 if scenario["direction"] in {"下降", "减少"} else 1
                if rate < 0 or (sign < 0 and rate > 100):
                    issues.append("情景利润变化比例不适用")
                else:
                    # The scenario starts from the most recent actual profit, not
                    # an explicitly requested old-year comparison denominator.
                    base = actual.get((latest, "profit"))
                    if base:
                        projected = base.value * (1 + sign * rate / 100)
                        digest = hashlib.sha256(sources[-1].text.encode()).hexdigest()
                        scenario_input = FinancialInput(
                            f"P:{digest}:{scenario.start()}:{scenario.end()}",
                            sources[-1].source_message_id,
                            digest,
                            scenario.start(),
                            scenario.end(),
                            sources[-1].text[scenario.start() : scenario.end()],
                            base.subject,
                            latest + 1,
                            "profit_change",
                            "scenario",
                            sign * rate,
                            "%",
                        )
                        inputs = (*inputs, scenario_input)
                        add(
                            "scenario_profit",
                            "下一年假设归母净利润",
                            f"{latest}年{_fmt(base.value)}亿元 × (1 {'-' if sign < 0 else '+'} {_fmt(rate)}%)",
                            projected,
                            "亿元",
                            (base, scenario_input),
                        )
                        add(
                            "scenario_pe",
                            "情景市盈率",
                            f"{_fmt(cap)}亿元 / 假设利润{_fmt(projected)}亿元",
                            safe_div(cap, projected) if projected > 0 else None,
                            "倍",
                            (price, shares, base, scenario_input),
                        )
    # Detect requested quantities the bounded parser could not supply. Do not
    # call a partial table a complete solution merely because PE was computable.
    requested = {
        "收入同比": "revenue_yoy",
        "净利润同比": "profit_yoy",
        "现金流/": "cash_profit_ratio",
    }
    present = {row.metric for row in rows}
    for phrase, metric in requested.items():
        if phrase in text and metric not in present:
            issues.append(f"{phrase}缺少可比的实际年度输入")
    if (
        "情景市盈率" in text or "下一年归母净利润" in text
    ) and "scenario_pe" not in present:
        issues.append("情景缺少可确认的利润变动与基数")
    return PremiseCalculation(
        sources, reference_year, inputs, tuple(rows), tuple(dict.fromkeys(issues))
    )
