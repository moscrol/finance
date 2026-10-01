"""内容正确性题集的确定性判分（2026-10-01，质检 P1「内容正确性题集」）。

为什么要有它：09-29 地图的结论是「格式和流程层的改进没有换来内容正确」——判官
deterministic passed 的三份首发答卷，内容里照样有源文错误。现有尺子（关键词 rubric、
结构门禁）都只查形状。本模块只量三类**已在真实答卷里出现过**的语义错误：

- ``timepoint``   时点：把「D0 未获单」写成「D3 仍无订单」；把「预计」写成「已发生」。
- ``stock_flow``  存量与流量：让净利润去承担现金资本开支（应当用经营现金流）。
- ``cfo_bridge``  CFO 起点：间接法里非现金项目与营运资本调整的方向。

三条设计约束：

1. **标准答案由代码算，不手填。** 每道题只给事实（数表），``expected`` 和陷阱值都由
   本模块里有名字的恒等式算出来——「会计恒等式由代码算，不交给模型推」。手填的数字
   会和题面漂移，而且审题人也会算错。
2. **以数值为主干。** 从答案里抽数字、换算到题目单位、按绝对值比对（符号错误在题目
   设计上就会导致量级不同，见 ``_assert_traps_distinct``）。必须出现正确值；**陷阱值一旦
   出现就判错**——陷阱值是错误推理的指纹，不是题面事实，正确答卷没有理由写出它。
3. **文字检查只用受控词表，而且只用在数字表达不了的地方**（时点断言）。每条规则在
   测试夹具里都有正例和反例；它判的是「有没有对材料覆盖不到的时点下断言」，不是
   「写得好不好」。

不做的事：不调模型、不读网络、不评价文风与结构、不替判官打总分。输出是每题
pass/fail + 失败原因，按错误类别汇总。
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date
import json
from pathlib import Path
import re
from typing import Any

ERROR_CLASSES = ("timepoint", "stock_flow", "cfo_bridge")

# ---------------------------------------------------------------------------
# 会计恒等式（单位一律是题目单位，默认亿元）
# ---------------------------------------------------------------------------


def cfo_indirect(f: Mapping[str, float]) -> float:
    """间接法经营现金流 = 净利润 + 非现金费用 − 非现金收益 − 营运资本占用增加。

    营运资本：应收、存货增加 → 占用现金 → 减；应付增加 → 少付现金 → 加。
    """

    return (
        f["net_income"]
        + f.get("depreciation_amortization", 0.0)
        + f.get("impairment", 0.0)
        + f.get("share_based_comp", 0.0)
        - f.get("gain_on_asset_sale", 0.0)
        - f.get("increase_receivables", 0.0)
        - f.get("increase_inventory", 0.0)
        + f.get("increase_payables", 0.0)
    )


def _cfo(f: Mapping[str, float]) -> float:
    return f["cfo"] if "cfo" in f else cfo_indirect(f)


IDENTITIES = {
    "cfo_indirect": cfo_indirect,
    # 自由现金流（经营口径）= 经营现金流 − 现金资本开支
    "fcf": lambda f: _cfo(f) - f["capex"],
    # 覆盖资本开支和分红后的现金盈余 / 缺口
    "fcf_after_dividend": lambda f: _cfo(f) - f["capex"] - f.get("dividends", 0.0),
}

# 陷阱：真实答卷里出现过的错误推理，各自算出的「错误答案」。
TRAPS = {
    # 存量与流量：用净利润去承担资本开支
    "ni_minus_capex": lambda f: f["net_income"] - f["capex"],
    "ni_minus_capex_dividend": lambda f: f["net_income"] - f["capex"] - f.get("dividends", 0.0),
    # CFO 起点：营运资本方向整体做反
    "cfo_wc_sign_flipped": lambda f: (
        f["net_income"]
        + f.get("depreciation_amortization", 0.0)
        + f.get("impairment", 0.0)
        + f.get("share_based_comp", 0.0)
        - f.get("gain_on_asset_sale", 0.0)
        + f.get("increase_receivables", 0.0)
        + f.get("increase_inventory", 0.0)
        - f.get("increase_payables", 0.0)
    ),
    # CFO 起点：资产处置收益当成要加回的项目
    "cfo_gain_added_back": lambda f: cfo_indirect(f) + 2 * f.get("gain_on_asset_sale", 0.0),
    # CFO 起点：只加回折旧摊销，漏掉减值等其他非现金费用
    "cfo_only_da": lambda f: cfo_indirect(f) - f.get("impairment", 0.0) - f.get("share_based_comp", 0.0),
}

# ---------------------------------------------------------------------------
# 数字抽取
# ---------------------------------------------------------------------------

_UNIT_SCALE = {"亿元": 1.0, "亿": 1.0, "万元": 1e-4, "万": 1e-4, "元": 1e-8}
# 左边界只排除 ASCII 字母数字：Python 的 \w 也匹配汉字，用它会把「盈余2.4亿元」漏掉。
_NUM_RE = re.compile(
    r"(?<![A-Za-z0-9_.])[-−+]?\d{1,3}(?:,\d{3})+(?:\.\d+)?|(?<![A-Za-z0-9_.])[-−+]?\d+(?:\.\d+)?"
)
_UNIT_AFTER = re.compile(r"\s*(亿元|亿|万元|万|元)")


def extract_amounts(text: str, *, default_unit: str = "亿元") -> list[float]:
    """抽出答案里的金额，换算到 ``default_unit``，返回绝对值列表。

    跳过日期（2026-09-01、9月1日）、季度（Q4）、百分比和 D0/D3 这类时点记号——
    它们不是金额，混进来会和陷阱值撞车。
    """

    target = _UNIT_SCALE[default_unit]
    cleaned = re.sub(r"\d{4}[-/.年]\d{1,2}(?:[-/.月]\d{1,2}日?)?", " ", text)
    cleaned = re.sub(r"\d{1,2}月\d{1,2}日", " ", cleaned)
    cleaned = re.sub(r"(?<![A-Za-z])[DQ]\d+(?![0-9])|\d{4}\s*Q\d", " ", cleaned)
    values: list[float] = []
    for match in _NUM_RE.finditer(cleaned):
        tail = cleaned[match.end():]
        if tail.lstrip().startswith(("%", "％", "个百分点", "倍", "年", "月", "日", "天", "家", "只")):
            continue
        raw = match.group(0).replace(",", "").replace("−", "-")
        try:
            number = abs(float(raw))
        except ValueError:
            continue
        unit = _UNIT_AFTER.match(tail)
        scale = _UNIT_SCALE[unit.group(1)] if unit else target
        values.append(number * scale / target)
    return values


def _close(a: float, b: float, *, abs_tol: float, rel_tol: float) -> bool:
    return abs(a - b) <= max(abs_tol, rel_tol * max(abs(a), abs(b)))


# ---------------------------------------------------------------------------
# 时点：日期写法与受控词表
# ---------------------------------------------------------------------------

_HEDGE = re.compile(
    r"无法确认|无法判断|不能确定|不确定|未知|尚不清楚|不清楚|无从|"
    r"没有(?:相关|更新|后续|新的)?(?:信息|证据|披露|材料|数据)|未(?:见|有)(?:相关|后续|新的)?(?:披露|公告|信息)|"
    r"材料(?:未|没有)覆盖|需(?:要)?(?:进一步)?核实|有待核实|待核实|不在材料"
)
# 「现在时」分两档。强词说的就是提问时点，引用了观察日期也不豁免（「根据 9 月 1 日
# 公告，公司目前仍未获单」照样是对 9 月 4 日下断言）；弱词只有在句子没有锚到观察
# 时点（日期或「当时 / 公告时」）时才算。
_NOW_STRONG = re.compile(r"截至目前|截至今天|截至今日|截至提问日|目前|至今|现在|当前|如今")
_NOW_WEAK = re.compile(r"仍然|依然|仍旧|仍|还是|还没|一直")
_THEN = re.compile(r"当时|公告时|公告日|彼时|那时|发布时|截至[^，。；]{0,16}公告")
_SENTENCE_SPLIT = re.compile(r"[。！？!?；;\n]")


def date_variants(iso: str) -> list[str]:
    d = date.fromisoformat(iso)
    return [
        iso,
        f"{d.year}年{d.month}月{d.day}日",
        f"{d.month}月{d.day}日",
        f"{d.month:02d}-{d.day:02d}",
        f"{d.month}/{d.day}",
        f"{d.month}.{d.day}",
    ]


def _mentions(text: str, variants: Iterable[str]) -> bool:
    return any(v in text for v in variants)


# ---------------------------------------------------------------------------
# 题目与判分
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Case:
    id: str
    error_class: str
    company: str
    question: str
    facts: dict[str, Any]
    unit: str = "亿元"
    expected_identity: str | None = None
    traps: tuple[str, ...] = ()
    # 时点题
    observed_at: str | None = None
    asked_at: str | None = None
    status_terms: tuple[str, ...] = ()
    # 「预计 / 计划」被写成「已发生」：不论带什么日期，未加限定地说出来就错。
    forbidden_claims: tuple[str, ...] = ()
    note: str = ""

    @property
    def expected(self) -> float | None:
        if self.expected_identity is None:
            return None
        return round(IDENTITIES[self.expected_identity](self.facts), 4)

    def trap_values(self) -> dict[str, float]:
        return {name: round(TRAPS[name](self.facts), 4) for name in self.traps}

    def prompt(self) -> str:
        """给被测方的题面：材料 + 问题。四个实验臂拿到的文本逐字相同。"""

        lines = [f"【材料】{self.company}（虚构公司，数据仅用于本题）"]
        labels = _FACT_LABELS
        for key, value in self.facts.items():
            if key in labels:
                lines.append(f"- {labels[key]}：{_fmt(value)} {self.unit}")
            elif isinstance(value, str):
                lines.append(f"- {value}")
        lines.append(f"【问题】{self.question}")
        return "\n".join(lines)


_FACT_LABELS = {
    "net_income": "净利润",
    "depreciation_amortization": "折旧与摊销",
    "impairment": "资产减值损失",
    "share_based_comp": "股份支付费用",
    "gain_on_asset_sale": "处置固定资产收益",
    "increase_receivables": "应收账款较期初增加",
    "increase_inventory": "存货较期初增加",
    "increase_payables": "应付账款较期初增加",
    "cfo": "经营活动产生的现金流量净额",
    "capex": "购建固定资产等支付的现金（资本开支）",
    "dividends": "拟现金分红",
}


def _fmt(value: float) -> str:
    return f"{value:g}"


@dataclass
class CaseResult:
    case_id: str
    error_class: str
    passed: bool
    failures: list[str] = field(default_factory=list)


def score(case: Case, answer: str) -> CaseResult:
    failures: list[str] = []
    text = str(answer or "")
    if not text.strip():
        return CaseResult(case.id, case.error_class, False, ["空答案"])

    if case.expected is not None:
        amounts = extract_amounts(text, default_unit=case.unit)
        expected = abs(case.expected)
        if not any(_close(a, expected, abs_tol=0.011, rel_tol=0.005) for a in amounts):
            failures.append(f"缺正确值 {expected:g}{case.unit}（{case.expected_identity}）")
        for name, trap in case.trap_values().items():
            if any(_close(a, abs(trap), abs_tol=0.011, rel_tol=0.005) for a in amounts):
                failures.append(f"出现陷阱值 {abs(trap):g}{case.unit}（{name}）")

    if case.error_class == "timepoint":
        failures.extend(_timepoint_failures(case, text))

    return CaseResult(case.id, case.error_class, not failures, failures)


def _timepoint_failures(case: Case, text: str) -> list[str]:
    failures: list[str] = []
    assert case.observed_at and case.asked_at
    if not _mentions(text, date_variants(case.observed_at)) and "D0" not in text:
        failures.append(f"没有交代材料的观察时点 {case.observed_at}")
    sentences = _SENTENCE_SPLIT.split(text)
    for sentence in sentences:
        claim = next((c for c in case.forbidden_claims if c in sentence), None)
        if claim and not _HEDGE.search(sentence):
            failures.append(f"把预计/计划写成了已发生（「{claim}」）：「{sentence.strip()[:40]}」")
            break
    if not case.status_terms:
        return failures
    asked = date_variants(case.asked_at) + ["D3"]
    status = re.compile("|".join(map(re.escape, case.status_terms)))
    for sentence in sentences:
        if not status.search(sentence):
            continue
        anchored_then = _THEN.search(sentence) is not None
        cites_observed = _mentions(sentence, date_variants(case.observed_at)) or "D0" in sentence
        about_later = (
            _mentions(sentence, asked)
            or (_NOW_STRONG.search(sentence) is not None and not anchored_then)
            or (_NOW_WEAK.search(sentence) is not None and not anchored_then and not cites_observed)
        )
        if about_later and not _HEDGE.search(sentence):
            failures.append(f"对材料没覆盖的时点下了断言：「{sentence.strip()[:40]}」")
            break
    return failures


# ---------------------------------------------------------------------------
# 题集加载、自检与汇总
# ---------------------------------------------------------------------------

CASES_PATH = Path(__file__).resolve().parent / "cases" / "content_correctness_v1.jsonl"


def load_cases(path: Path = CASES_PATH) -> list[Case]:
    cases = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        row["traps"] = tuple(row.get("traps", ()))
        row["status_terms"] = tuple(row.get("status_terms", ()))
        row["forbidden_claims"] = tuple(row.get("forbidden_claims", ()))
        row.pop("fixtures", None)
        cases.append(Case(**row))
    for case in cases:
        _assert_well_formed(case)
    return cases


def load_fixtures(path: Path = CASES_PATH) -> dict[str, dict[str, list[str]]]:
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            out[row["id"]] = row.get("fixtures", {})
    return out


def _assert_well_formed(case: Case) -> None:
    if case.error_class not in ERROR_CLASSES:
        raise ValueError(f"{case.id}: 未知错误类别 {case.error_class}")
    if case.error_class == "timepoint":
        if not (case.observed_at and case.asked_at and (case.status_terms or case.forbidden_claims)):
            raise ValueError(f"{case.id}: 时点题必须给 observed_at / asked_at，以及 status_terms 或 forbidden_claims")
    elif case.expected_identity is None or not case.traps:
        raise ValueError(f"{case.id}: 数值题必须给 expected_identity 和至少一个陷阱")
    _assert_traps_distinct(case)


def _assert_traps_distinct(case: Case) -> None:
    """陷阱值必须和正确值、题面事实都分得开，否则「出现陷阱值」就不是错误指纹。"""

    if case.expected is None:
        return
    facts = [abs(v) for v in case.facts.values() if isinstance(v, (int, float))]
    reference = [abs(case.expected), *facts]
    for name, trap in case.trap_values().items():
        for ref in reference:
            if _close(abs(trap), ref, abs_tol=0.05, rel_tol=0.01):
                raise ValueError(f"{case.id}: 陷阱 {name}={trap:g} 与正确值或题面事实 {ref:g} 撞车")


def summarize(results: Iterable[CaseResult]) -> dict[str, Any]:
    by_class: dict[str, list[CaseResult]] = {c: [] for c in ERROR_CLASSES}
    rows = list(results)
    for r in rows:
        by_class[r.error_class].append(r)
    return {
        "total": len(rows),
        "passed": sum(r.passed for r in rows),
        "pass_rate": round(sum(r.passed for r in rows) / len(rows), 3) if rows else None,
        "by_class": {
            c: {"n": len(v), "passed": sum(r.passed for r in v)} for c, v in by_class.items() if v
        },
        "failures": {r.case_id: r.failures for r in rows if not r.passed},
    }
