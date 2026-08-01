"""Fail-closed verdicts for the 28-case product acceptance board.

The module is deliberately pure: callers provide a compiled case contract and a
serialized run, and receive immutable operational/truth/experience verdicts. It
does not call a model, database, knowledge base, or product runtime.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import date
from enum import Enum
from pathlib import Path
from typing import Any, Mapping


REPO = Path(__file__).resolve().parents[2]
VERDICT_OVERLAY_PATH = (
    REPO / "intelligence/eval/cases/acceptance_verdict_contracts.json"
)

_KNOWN_CASE_FIELDS = frozenset(
    {
        "id",
        "tier",
        "query",
        "date",
        "followups",
        "pass_rule",
        "expect_tools",
        "must_mention",
        "expect_facts",
        "expect_entities",
        "expect_answer_set",
        "exact_set",
        "expect_refusal",
        "forbid_phrases",
        "forbid_future_data",
        "require_falsifiable",
        "require_flag_inconsistency",
        "check_citation_registry",
        "check_cross_turn_consistency",
        "known_data_bug",
        "cross_check_hint",
        "inherit_from",
    }
)
# 相对时间词：问题问的是「现在」，答案就跟着真实日期走。
_RELATIVE_TIME_MARKS = ("现在", "今天", "最近", "当前", "目前", "近期", "本周", "昨天", "明天")

_KNOWN_OVERLAY_FIELDS = frozenset(
    {
        "coverage",
        "reason",
        "required_any_phrases",
        "required_all_phrases",
        "fact_aliases",
        "phrase_equivalents",
        "phrase_discharged_by",
    }
)

# 别名窗口：把数字绑定到字段名，避免「正文里恰好有这个数」就算命中。
# 回看原来只有 8 字，而中文的修饰语在名词前面和后面一样常见——
# 「21949.97 亿元的成交额」数字落在别名前 13 字，被 8 字窗口切掉，
# 于是「答对了但语序不同」长得跟「答错了」一模一样。改成对称。
# 实测扫描（3 次运行 57 条数值断言）：回看放宽到 16 字以上直到完全不设窗口，
# 命中数都停在 25/57 且只多这一条——说明窗口不是红的主因，只有不对称是缺陷。
_ALIAS_WINDOW_BACK = 40
_ALIAS_WINDOW_FORWARD = 40

_NUMBER_RE = re.compile(r"(?<![\w])[-+]?\d[\d,]*(?:\.\d+)?%?")
_TAG_RE = re.compile(r"\[([SGRWE]\d+)\]")
_ISO_DATE_RE = re.compile(r"\b(20\d{2})-(\d{1,2})-(\d{1,2})\b")
_CN_DATE_RE = re.compile(r"(?<!\d)(\d{1,2})月(\d{1,2})日")
_REFUSAL_MARKS = (
    "无数据",
    "没有数据",
    "没有可用",
    "无可用",
    "不可用",
    "无法",
    "不能可靠回答",
    "超出覆盖",
    "0 行",
    "0行",
    "不存在",
    "休市",
    "非交易日",
)
_INCONSISTENCY_MARKS = (
    "矛盾",
    "不一致",
    "异常",
    "冲突",
    "不可能",
    "重复",
    "质疑",
)
_CONDITION_MARKS = ("若", "如果", "一旦", "跌破", "突破", "失效", "证伪")
_CONTEXT_LOSS_MARKS = (
    "你指的是",
    "请补充",
    "请明确",
    "哪家公司、题材",
    "哪个板块",
    "上一条研究逻辑",
)
_PREDICTIVE_MARKS = ("预计", "预期", "大概率", "可能", "研判", "若", "如果", "或将")
_REALIZED_MARKS = ("实际", "收涨", "收跌", "收盘", "上涨", "下跌", "涨停", "跌停", "成交额")


class VerdictState(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    UNJUDGEABLE = "unjudgeable"
    NOT_RUN = "not_run"


class OperationalState(str, Enum):
    NOT_RUN = "not_run"
    BLOCKED = "blocked"
    FAILED = "failed"
    DEGRADED = "degraded"
    COMPLETED = "completed"


class ExperienceState(str, Enum):
    UNLABELED = "unlabeled"
    LABELED = "labeled"
    INELIGIBLE = "ineligible"


@dataclass(frozen=True)
class RuleVerdict:
    rule_id: str
    kind: str
    state: VerdictState
    reason: str


@dataclass(frozen=True)
class OperationalVerdict:
    state: OperationalState
    reason: str


@dataclass(frozen=True)
class TruthVerdict:
    state: VerdictState
    rules: tuple[RuleVerdict, ...] = ()


@dataclass(frozen=True)
class ExperienceVerdict:
    state: ExperienceState = ExperienceState.UNLABELED
    label: str | None = None
    reason: str = "blind experience label not supplied"


@dataclass(frozen=True)
class CaseVerdict:
    case_id: str
    operational: OperationalVerdict
    truth: TruthVerdict
    experience: ExperienceVerdict = field(default_factory=ExperienceVerdict)

    def to_dict(self) -> dict[str, Any]:
        return _serialize(asdict(self))


@dataclass(frozen=True)
class CaseContract:
    case_id: str
    tier: str
    query: str
    cutoff_date: str | None
    pass_rule: str
    coverage: str
    coverage_reason: str | None
    required_any_phrases: tuple[str, ...]
    required_all_phrases: tuple[str, ...]
    fact_aliases: Mapping[str, tuple[str, ...]]
    case: Mapping[str, Any]
    phrase_equivalents: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    phrase_discharged_by: Mapping[str, str] = field(default_factory=dict)
    reproducible: bool = True
    diagnostics: tuple[str, ...] = ()

    def phrase_observed(self, phrase: str, text: str) -> bool:
        """措辞断言：正典短语或它的等价表达任一在场即算命中。

        等价类只用来吸收「同一事实的不同合法中文说法」，不放松事实本身——
        数值仍由 expect_facts 按容差判定，枚举仍不许跨值。
        """

        for variant in self.phrase_equivalents.get(phrase, (phrase,)):
            if variant in text:
                return True
        return False


def load_verdict_overlay(path: Path | None = None) -> dict[str, dict[str, Any]]:
    """Load the additive verdict overlay, returning only its case mapping."""

    payload = json.loads((path or VERDICT_OVERLAY_PATH).read_text(encoding="utf-8"))
    cases = payload.get("cases")
    if not isinstance(cases, dict):
        raise ValueError("verdict overlay must contain an object-valued cases field")
    return {str(case_id): dict(entry) for case_id, entry in cases.items()}


def _reproducibility_diagnostics(case: Mapping[str, Any]) -> list[str]:
    """题目问「现在」、期望值却冻结在某一天 —— 这种红永远不会变绿。

    runner 只把 `case["query"]` 发给产品（`acceptance.py`），`date` 字段仅供判官
    做 cutoff。所以问题正文里没有日期锚时，产品答的是真实今天。

    A8 实测：query「现在市场处于什么阶段，第几天了」，产品答「截至 2026-07-30，
    底部横盘阶段，第 2 个交易日」——完全正确；而 expect_facts 冻结的是
    `反弹阶段 / 第 3 天`（2026-07-23 的事实）。判官把它记成产品失败，
    且这条红会随行情漂移，不是稳定信号。

    对照 A1：query 是「2026-07-23 今天市场怎么样」，日期写进了正文，可复现。

    只在**期望值本身随日期变化**时才报（expect_facts / expect_answer_set）。
    expect_entities 不算——B8 的「立新能源」写在问题里，跟哪天问无关。
    """

    query = str(case.get("query") or "")
    marks = [mark for mark in _RELATIVE_TIME_MARKS if mark in query]
    if not marks:
        return []
    cutoff = str(case.get("date") or "")
    if cutoff and cutoff in query:
        return []  # 日期锚已写进正文，产品收得到
    dated_expectations = [
        name
        for name in ("expect_facts", "expect_answer_set")
        if case.get(name)
    ]
    if not dated_expectations:
        return []
    return [
        "case is not reproducible: query is relative-time "
        f"({', '.join(marks)}) but {', '.join(dated_expectations)} is frozen to "
        f"{cutoff or 'an unstated date'}; the date anchor never reaches the product"
    ]


def compile_case_contract(
    case: Mapping[str, Any], overlay: Mapping[str, Any] | None = None
) -> CaseContract:
    """Compile one canonical case plus its additive verdict overlay."""

    overlay = dict(overlay or {})
    diagnostics: list[str] = []
    unknown_case = sorted(set(case) - _KNOWN_CASE_FIELDS)
    if unknown_case:
        diagnostics.append("unknown case fields: " + ", ".join(unknown_case))
    unknown_overlay = sorted(set(overlay) - _KNOWN_OVERLAY_FIELDS)
    if unknown_overlay:
        diagnostics.append("unknown overlay fields: " + ", ".join(unknown_overlay))

    reproducibility = _reproducibility_diagnostics(case)
    diagnostics.extend(reproducibility)

    coverage = str(overlay.get("coverage") or "semantic_required")
    if coverage not in {"structured", "semantic_required"}:
        diagnostics.append(f"invalid coverage: {coverage}")
        coverage = "semantic_required"
    aliases_raw = overlay.get("fact_aliases") or {}
    aliases = {
        str(field_name): tuple(str(item) for item in values)
        for field_name, values in aliases_raw.items()
    }
    equivalents_raw = overlay.get("phrase_equivalents") or {}
    equivalents: dict[str, tuple[str, ...]] = {}
    for phrase_raw, variants_raw in equivalents_raw.items():
        phrase = str(phrase_raw)
        variants = tuple(str(item) for item in variants_raw)
        if not variants:
            diagnostics.append(f"empty phrase_equivalents class: {phrase}")
            continue
        if phrase not in variants:
            # 等价类必须含正典短语本身。否则一个笔误就会把原断言整条换掉，
            # 而看板上完全看不出来——这正是「悄悄放宽判据」最容易溜进来的缝。
            diagnostics.append(
                f"phrase_equivalents class for {phrase} does not contain the phrase itself"
            )
            continue
        equivalents[phrase] = variants

    declared_phrases = {str(item) for item in (case.get("must_mention") or [])}
    available_rules = {"falsifiable", "refusal", "inconsistency", "expected_entities"} | {
        f"fact:{item.get('field')}" for item in (case.get("expect_facts") or [])
    }
    discharged_by: dict[str, str] = {}
    for phrase_raw, rule_raw in (overlay.get("phrase_discharged_by") or {}).items():
        phrase, rule_id = str(phrase_raw), str(rule_raw)
        if phrase not in declared_phrases:
            diagnostics.append(f"phrase_discharged_by names undeclared phrase: {phrase}")
            continue
        if rule_id not in available_rules:
            # 打错规则名不能静默失效：那样这条措辞断言会永远解除不掉（假红），
            # 或者反过来看着像被守住其实没有。fail-closed，报进 diagnostics。
            diagnostics.append(
                f"phrase_discharged_by for {phrase} names unknown rule: {rule_id}"
            )
            continue
        discharged_by[phrase] = rule_id
    return CaseContract(
        case_id=str(case["id"]),
        tier=str(case.get("tier") or "unknown"),
        query=str(case.get("query") or ""),
        cutoff_date=str(case["date"]) if case.get("date") else None,
        pass_rule=str(case.get("pass_rule") or ""),
        coverage=coverage,
        coverage_reason=(
            str(overlay["reason"]) if overlay.get("reason") is not None else None
        ),
        required_any_phrases=tuple(
            str(item) for item in (overlay.get("required_any_phrases") or [])
        ),
        required_all_phrases=tuple(
            str(item) for item in (overlay.get("required_all_phrases") or [])
        ),
        fact_aliases=aliases,
        case=dict(case),
        phrase_equivalents=equivalents,
        phrase_discharged_by=discharged_by,
        reproducible=not reproducibility,
        diagnostics=tuple(diagnostics),
    )


def evaluate_case(
    contract: CaseContract,
    case_run: Mapping[str, Any] | None,
    *,
    observations: Mapping[str, Any] | None = None,
) -> CaseVerdict:
    """Evaluate one case without conflating absence, operation, and quality."""

    if case_run is None:
        return CaseVerdict(
            case_id=contract.case_id,
            operational=OperationalVerdict(
                state=OperationalState.NOT_RUN,
                reason="no case run recorded",
            ),
            truth=TruthVerdict(state=VerdictState.NOT_RUN),
        )
    operational = _evaluate_operational(case_run)
    external = observations or {}
    truth = _evaluate_truth(contract, case_run, operational, external)
    return CaseVerdict(
        case_id=contract.case_id,
        operational=operational,
        truth=truth,
        experience=_evaluate_experience(external),
    )


def _evaluate_operational(case_run: Mapping[str, Any]) -> OperationalVerdict:
    blocked_reason = case_run.get("blocked_reason")
    turns = case_run.get("turns") or []
    if blocked_reason and not turns:
        return OperationalVerdict(
            state=OperationalState.BLOCKED,
            reason=str(blocked_reason),
        )
    if not turns:
        return OperationalVerdict(
            state=OperationalState.FAILED,
            reason="case run has no turns",
        )

    statuses = [str(turn.get("status") or "unknown") for turn in turns]
    if any(status != "completed" for status in statuses):
        errors = [str(turn.get("error")) for turn in turns if turn.get("error")]
        reason = ", ".join(errors) if errors else "terminal states: " + ", ".join(statuses)
        return OperationalVerdict(state=OperationalState.FAILED, reason=reason)
    if any(turn.get("degrades") for turn in turns):
        return OperationalVerdict(
            state=OperationalState.DEGRADED,
            reason="one or more completed turns reported degradation",
        )
    return OperationalVerdict(
        state=OperationalState.COMPLETED,
        reason="all recorded turns completed",
    )


def _evaluate_truth(
    contract: CaseContract,
    case_run: Mapping[str, Any],
    operational: OperationalVerdict,
    observations: Mapping[str, Any],
) -> TruthVerdict:
    if operational.state in {OperationalState.BLOCKED, OperationalState.FAILED}:
        return TruthVerdict(state=VerdictState.UNJUDGEABLE)

    if not contract.reproducible:
        # 判据本身坏了就不该产出「产品失败」。A8 的 expect_facts 冻在 2026-07-23，
        # 而问题问的是「现在」——那些 fact 红一条都不成立，可 FAIL 在聚合里优先于
        # UNJUDGEABLE，会盖掉缺陷标记，让题目缺陷长得和产品缺陷一模一样。
        return TruthVerdict(
            state=VerdictState.UNJUDGEABLE,
            rules=(
                RuleVerdict(
                    rule_id="case_reproducibility",
                    kind="contract",
                    state=VerdictState.UNJUDGEABLE,
                    reason="; ".join(contract.diagnostics),
                ),
            ),
        )

    turns = [turn for turn in (case_run.get("turns") or []) if isinstance(turn, Mapping)]
    answers = [str(turn.get("answer") or "") for turn in turns]
    text = "\n".join(answers)
    rules: list[RuleVerdict] = [
        _bool_rule(
            "answer_present",
            "answer",
            bool(text.strip()),
            "at least one answer is present",
            "all answer texts are empty",
        )
    ]
    case = contract.case

    if case.get("expect_refusal"):
        refused = any(mark in text for mark in _REFUSAL_MARKS)
        rules.append(
            _bool_rule(
                "refusal",
                "refusal",
                refused,
                "answer explicitly reports unavailable/no data",
                "answer does not explicitly report unavailable/no data",
            )
        )

    forbidden = tuple(str(item) for item in (case.get("forbid_phrases") or []))
    if forbidden:
        hits = [item for item in forbidden if item in text]
        rules.append(
            _bool_rule(
                "forbidden_phrases",
                "forbidden_text",
                not hits,
                "no forbidden phrase observed",
                "forbidden phrases observed: " + ", ".join(hits),
            )
        )

    if contract.required_any_phrases:
        hits = [item for item in contract.required_any_phrases if item in text]
        rules.append(
            _bool_rule(
                "required_any_phrases",
                "required_text",
                bool(hits),
                "required alternative observed: " + ", ".join(hits),
                "none of the required alternatives was observed",
            )
        )
    if contract.required_all_phrases:
        missing = [item for item in contract.required_all_phrases if item not in text]
        rules.append(
            _bool_rule(
                "required_all_phrases",
                "required_text",
                not missing,
                "all required phrases observed",
                "missing required phrases: " + ", ".join(missing),
            )
        )

    expected_entities = tuple(str(item) for item in (case.get("expect_entities") or []))
    if expected_entities:
        missing = [item for item in expected_entities if item not in text]
        rules.append(
            _bool_rule(
                "expected_entities",
                "entity_presence",
                not missing,
                "all expected entities observed",
                "missing expected entities: " + ", ".join(missing),
            )
        )

    fact_rules: list[RuleVerdict] = [
        _evaluate_fact(item, text, contract.fact_aliases, contract)
        for item in case.get("expect_facts") or []
    ]
    rules.extend(fact_rules)

    if case.get("forbid_future_data"):
        rules.append(_evaluate_cutoff(contract.cutoff_date, turns, text))

    if case.get("check_citation_registry"):
        rules.append(_evaluate_citation_integrity(turns, text))

    if case.get("require_flag_inconsistency"):
        rules.append(_evaluate_inconsistency(text, fact_rules))

    if case.get("require_falsifiable"):
        has_condition = any(mark in text for mark in _CONDITION_MARKS)
        has_number = bool(_extract_numbers(text))
        rules.append(
            _bool_rule(
                "falsifiable",
                "semantic_marker",
                has_condition and has_number,
                "answer contains a condition and numeric threshold",
                "answer lacks a condition or numeric threshold",
            )
        )

    # must_mention 放在最后判：它可以被前面更严的规则「解除」（见 phrase_discharged_by）。
    must_mention = tuple(str(item) for item in (case.get("must_mention") or []))
    if must_mention:
        rules.append(_evaluate_must_mention(contract, must_mention, text, rules))

    if case.get("check_cross_turn_consistency"):
        lost = any(mark in answer for answer in answers[1:] for mark in _CONTEXT_LOSS_MARKS)
        if lost:
            rules.append(
                RuleVerdict(
                    rule_id="cross_turn_consistency",
                    kind="multi_turn",
                    state=VerdictState.FAIL,
                    reason="follow-up lost already established conversation context",
                )
            )
        else:
            rules.append(
                _observation_or_unjudgeable(
                    observations,
                    "cross_turn_consistency",
                    "multi_turn",
                    "text alone cannot prove set/count consistency",
                )
            )

    if case.get("expect_answer_set") and contract.coverage == "structured":
        rules.append(
            _evaluate_answer_set(
                observations,
                tuple(str(item) for item in case.get("expect_answer_set") or []),
                exact=bool(case.get("exact_set")),
            )
        )

    if case.get("inherit_from"):
        rules.append(
            _observation_or_unjudgeable(
                observations,
                "inherited_golden",
                "agent_eval",
                "historical acceptance trace lacks agent_eval TurnInput observations",
            )
        )

    if contract.coverage == "semantic_required":
        rules.append(
            _observation_or_unjudgeable(
                observations,
                "pass_rule",
                "semantic",
                contract.coverage_reason or "pass rule needs semantic observation",
            )
        )

    if contract.diagnostics:
        rules.append(
            RuleVerdict(
                rule_id="contract_diagnostics",
                kind="contract",
                state=VerdictState.UNJUDGEABLE,
                reason="; ".join(contract.diagnostics),
            )
        )

    return TruthVerdict(state=_aggregate_rules(rules), rules=tuple(rules))


def _evaluate_fact(
    raw: Mapping[str, Any],
    text: str,
    aliases_by_field: Mapping[str, tuple[str, ...]],
    contract: CaseContract | None = None,
) -> RuleVerdict:
    field_name = str(raw.get("field") or "unknown")
    if "value" not in raw:
        return RuleVerdict(
            rule_id=f"fact:{field_name}",
            kind="fact",
            state=VerdictState.UNJUDGEABLE,
            reason="fact expectation has no value",
        )
    expected = raw["value"]
    aliases = aliases_by_field.get(field_name, ())
    candidate_text = _alias_windows(text, aliases) if aliases else text
    is_literal = isinstance(expected, str)
    if is_literal and contract is not None and not contract.phrase_observed(str(expected), text):
        # 字符串型 fact 找不到就是真找不到：一个字面量不在全文里，不存在
        # 「定位不到」的可能。别名未命中→不可判那条规则是为数值设计的
        # （光有个数字不能证明它绑在这个字段上），套到字面量上会误触发。
        # A9 实测：别名表 ["状态","沸点"] 里「沸点」既是定位别名又是期望值，
        # 于是「沸点没出现」被记成「定位不到」，三次运行在 ❔/❌ 之间来回翻，
        # 而事实是三次都没出现——稳定的 FAIL 才是诚实裁决。
        return RuleVerdict(
            rule_id=f"fact:{field_name}",
            kind="fact",
            state=VerdictState.FAIL,
            reason=f"expected fact {field_name}={expected!r} absent from the whole answer",
        )
    if aliases and not candidate_text:
        # 别名一个都没命中 = 判官没找到该在哪儿看，不等于产品答错了。
        # 原来这里会一路走到「数字不在空字符串里」然后判 FAIL——于是「别名表
        # 没跟上答案措辞」这种配置疏漏，长得和「产品答错」一模一样。
        # A 组基线实测：答案写「较上一交易日缩减 17.27%」，别名表是
        # ["环比","较昨日"]，窗口长度 0，直接被记成一次失败。
        return RuleVerdict(
            rule_id=f"fact:{field_name}",
            kind="fact",
            state=VerdictState.UNJUDGEABLE,
            reason=(
                f"fact {field_name} aliases {list(aliases)} not found in answer; "
                "cannot locate the value"
            ),
        )
    if isinstance(expected, bool):
        matched = str(expected).lower() in candidate_text.lower()
    elif isinstance(expected, (int, float)):
        numbers = _extract_numbers(candidate_text)
        if float(expected) < 0:
            # 中文把符号放在方向词上，不放在数字上：「较上一交易日缩减 17.27%」
            # 抽出来是 +17.27。只在期望为负时补候选，且必须有减少类方向词紧邻——
            # 方向写反（「增加 17.27%」）依然判错，符号错误不会被放过。
            numbers = numbers + _decrease_signed_numbers(candidate_text)
        tolerance = 0.0
        if raw.get("tol_abs") is not None:
            tolerance = abs(float(raw["tol_abs"]))
        elif raw.get("tol_pct") is not None:
            tolerance = abs(float(expected)) * abs(float(raw["tol_pct"])) / 100.0
        matched = any(abs(value - float(expected)) <= tolerance + 1e-9 for value in numbers)
    elif contract is not None:
        # 字符串型 fact（枚举标签，如 market_stage=反弹阶段）本质是措辞断言，
        # 走和 must_mention 同一套等价类：同一枚举值的合法别称算命中，跨值不算。
        matched = contract.phrase_observed(str(expected), candidate_text)
    else:
        matched = str(expected) in candidate_text
    return _bool_rule(
        f"fact:{field_name}",
        "fact",
        matched,
        f"expected fact {field_name} observed",
        f"expected fact {field_name}={expected!r} not observed within tolerance",
    )


def _evaluate_must_mention(
    contract: CaseContract,
    must_mention: tuple[str, ...],
    text: str,
    prior_rules: list[RuleVerdict],
) -> RuleVerdict:
    """措辞断言：等价表达命中，或更严的结构化规则已经证明了同一件事。

    A 组实测的两类假红：
      1. 同义改写——答案写「处于反弹阶段」而断言要「反弹阶段」，靠 phrase_equivalents。
      2. **冗余断言**——A1 要求正文出现「缩量」，可同一题的
         `fact:amount_vs_yesterday_pct=-17.27`（±0.5）已经断言了同一事实。
         run2 答案写「较昨日减少 17.27%」：数值规则判 PASS，措辞规则判 FAIL。
         那条 FAIL 一点信息量都没有，纯粹是在测模型用不用某个词。

    第 2 类不能靠往词表里堆变体解决——中文会把数值插在名词和动词之间
    （「成交额 21949.97 亿元、较昨日减少 17.27%」），子串永远追不完，
    而且照着答案补词就是过拟合到某次运行。所以改成声明式的蕴含：
    指定一条更严的规则，它 PASS 就解除这条措辞要求。

    这不是放宽——被解除时，同一事实仍被一条**带容差的数值规则**守着；
    数值规则没过，措辞要求原样生效。
    """

    states = {rule.rule_id: rule.state for rule in prior_rules}
    missing: list[str] = []
    discharged: list[str] = []
    for phrase in must_mention:
        if contract.phrase_observed(phrase, text):
            continue
        by = contract.phrase_discharged_by.get(phrase)
        if by is not None and states.get(by) is VerdictState.PASS:
            discharged.append(f"{phrase}←{by}")
            continue
        missing.append(phrase)
    if missing:
        return RuleVerdict(
            "must_mention",
            "product_language",
            VerdictState.FAIL,
            "missing product terms: " + ", ".join(missing),
        )
    reason = "all product terms observed"
    if discharged:
        reason += "; discharged by stricter rules: " + ", ".join(discharged)
    return RuleVerdict("must_mention", "product_language", VerdictState.PASS, reason)


def _evaluate_inconsistency(
    text: str, fact_rules: list[RuleVerdict]
) -> RuleVerdict:
    """陷阱题：光有「矛盾」两个字不算指出了**这个**矛盾。

    原来只在全文里找关键词。A 组实测：A9 三次运行「沸点」和「-66.3%」一个都
    没出现过，可前两次却因为正文别处写了「矛盾」判 PASS——那是假绿；第三次
    没写「矛盾」判 FAIL，同样无信息量。两种状态都读不出东西，还在看板上来回翻。

    改成锚定：题目声明了 expect_facts 时，那些值就是矛盾的两端。两端都没在
    答案里出现，就不可能是在说这个矛盾。这是**收紧**不是放宽——它先杀掉假绿。
    没声明 expect_facts 的题（C5 靠重复值发现矛盾）没有可锚的结构化端点，
    维持原关键词行为。
    """

    found = any(mark in text for mark in _INCONSISTENCY_MARKS)
    if not found:
        return RuleVerdict(
            "inconsistency",
            "semantic_marker",
            VerdictState.FAIL,
            "answer does not flag the required inconsistency",
        )
    if not fact_rules:
        return RuleVerdict(
            "inconsistency",
            "semantic_marker",
            VerdictState.PASS,
            "answer flags an inconsistency; contract declares no operand to anchor it",
        )
    missing = [rule.rule_id for rule in fact_rules if rule.state is VerdictState.FAIL]
    if missing:
        return RuleVerdict(
            "inconsistency",
            "semantic_marker",
            VerdictState.FAIL,
            "answer flags some inconsistency, but the contract's operands are absent "
            "(" + ", ".join(missing) + "); it cannot be the required contradiction",
        )
    unproven = [
        rule.rule_id for rule in fact_rules if rule.state is VerdictState.UNJUDGEABLE
    ]
    if unproven:
        return RuleVerdict(
            "inconsistency",
            "semantic_marker",
            VerdictState.UNJUDGEABLE,
            "answer flags an inconsistency, but operands are unlocatable "
            "(" + ", ".join(unproven) + "); cannot confirm which contradiction",
        )
    return RuleVerdict(
        "inconsistency",
        "semantic_marker",
        VerdictState.PASS,
        "answer flags the inconsistency and both contract operands are observed",
    )


def _evaluate_cutoff(
    cutoff_text: str | None,
    turns: list[Mapping[str, Any]],
    answer_text: str,
) -> RuleVerdict:
    try:
        cutoff = date.fromisoformat(str(cutoff_text))
    except (TypeError, ValueError):
        return RuleVerdict(
            "cutoff",
            "temporal",
            VerdictState.UNJUDGEABLE,
            "case cutoff date is missing or invalid",
        )
    citation_dates: list[date] = []
    for turn in turns:
        for citation in turn.get("citations") or []:
            if not isinstance(citation, Mapping) or not citation.get("date"):
                continue
            try:
                citation_dates.append(date.fromisoformat(str(citation["date"])))
            except ValueError:
                continue
    future = sorted({item.isoformat() for item in citation_dates if item > cutoff})
    if future or _has_realized_future_claim(answer_text, cutoff):
        detail = ", ".join(future) if future else "future realized claim in answer text"
        return RuleVerdict(
            "cutoff",
            "temporal",
            VerdictState.FAIL,
            "future-of-cutoff evidence observed: " + detail,
        )
    if not citation_dates:
        return RuleVerdict(
            "cutoff",
            "temporal",
            VerdictState.UNJUDGEABLE,
            "no structured citation dates available to prove cutoff compliance",
        )
    return RuleVerdict(
        "cutoff",
        "temporal",
        VerdictState.PASS,
        "all structured citation dates are on or before the cutoff",
    )


def _evaluate_citation_integrity(
    turns: list[Mapping[str, Any]], answer_text: str
) -> RuleVerdict:
    cited = set(_TAG_RE.findall(answer_text))
    minted: set[str] = set()
    for turn in turns:
        for evidence in turn.get("evidence") or []:
            if isinstance(evidence, Mapping):
                minted.update(_TAG_RE.findall(str(evidence.get("label") or "")))
    dangling = sorted(cited - minted)
    return _bool_rule(
        "citation_integrity",
        "citation",
        not dangling,
        "all cited tags were minted; no tags is vacuously clean",
        "unminted citation tags: " + ", ".join(dangling),
    )


def _evaluate_answer_set(
    observations: Mapping[str, Any], expected: tuple[str, ...], *, exact: bool
) -> RuleVerdict:
    raw = (observations.get("truth_observations") or {}).get("answer_set")
    if not isinstance(raw, Mapping) or not isinstance(raw.get("values"), list):
        return RuleVerdict(
            "answer_set",
            "set",
            VerdictState.UNJUDGEABLE,
            "typed answer_set observation not supplied",
        )
    observed = {str(item) for item in raw["values"]}
    expected_set = set(expected)
    passed = observed == expected_set if exact else expected_set <= observed
    return _bool_rule(
        "answer_set",
        "set",
        passed,
        "observed answer set satisfies the contract",
        f"observed answer set {sorted(observed)} does not satisfy {sorted(expected_set)}",
    )


def _observation_or_unjudgeable(
    observations: Mapping[str, Any], rule_id: str, kind: str, missing_reason: str
) -> RuleVerdict:
    raw = (observations.get("truth_observations") or {}).get(rule_id)
    if not isinstance(raw, Mapping):
        return RuleVerdict(rule_id, kind, VerdictState.UNJUDGEABLE, missing_reason)
    try:
        state = VerdictState(str(raw.get("state")))
    except ValueError:
        state = VerdictState.UNJUDGEABLE
    if state is VerdictState.NOT_RUN:
        state = VerdictState.UNJUDGEABLE
    return RuleVerdict(
        rule_id=rule_id,
        kind=kind,
        state=state,
        reason=str(raw.get("reason") or "external typed observation"),
    )


def _evaluate_experience(observations: Mapping[str, Any]) -> ExperienceVerdict:
    raw = observations.get("experience_verdict")
    if not isinstance(raw, Mapping):
        return ExperienceVerdict()
    if raw.get("eligible") is False:
        return ExperienceVerdict(
            state=ExperienceState.INELIGIBLE,
            reason=str(raw.get("reason") or "reference is ineligible for this case/dimension"),
        )
    label = raw.get("label")
    if label:
        return ExperienceVerdict(
            state=ExperienceState.LABELED,
            label=str(label),
            reason=str(raw.get("reason") or "external blind label"),
        )
    return ExperienceVerdict()


def _bool_rule(
    rule_id: str,
    kind: str,
    passed: bool,
    pass_reason: str,
    fail_reason: str,
) -> RuleVerdict:
    return RuleVerdict(
        rule_id=rule_id,
        kind=kind,
        state=VerdictState.PASS if passed else VerdictState.FAIL,
        reason=pass_reason if passed else fail_reason,
    )


def _aggregate_rules(rules: list[RuleVerdict]) -> VerdictState:
    if not rules:
        return VerdictState.UNJUDGEABLE
    if any(rule.state is VerdictState.FAIL for rule in rules):
        return VerdictState.FAIL
    if any(rule.state is VerdictState.UNJUDGEABLE for rule in rules):
        return VerdictState.UNJUDGEABLE
    return VerdictState.PASS


def _extract_numbers(text: str) -> list[float]:
    values: list[float] = []
    for raw in _NUMBER_RE.findall(text):
        normalized = raw.rstrip("%").replace(",", "")
        try:
            values.append(float(normalized))
        except ValueError:
            continue
    return values


_DECREASE_WORD_RE = re.compile(
    r"(?:缩减|减少|下降|下滑|回落|下跌|收窄|萎缩|缩量|降低|减小|少了|降|跌)"
    r"[了至到约]?\s*([-+]?\d[\d,]*(?:\.\d+)?)%?"
)


def _decrease_signed_numbers(text: str) -> list[float]:
    """把「缩减 17.27%」这类中文减量表达读成 -17.27。

    只认紧跟在减量方向词后面的数字（中间最多一个「了/至/到/约」和空白）。
    增量方向词一律不碰——期望是负数而答案说「增加」，那就是答错了，
    不该被这条兜回来。
    """
    values: list[float] = []
    for raw in _DECREASE_WORD_RE.findall(text):
        try:
            value = float(raw.replace(",", ""))
        except ValueError:
            continue
        values.append(-abs(value))
    return values


def _alias_windows(text: str, aliases: tuple[str, ...]) -> str:
    windows: list[str] = []
    for alias in aliases:
        start = 0
        while True:
            index = text.find(alias, start)
            if index < 0:
                break
            windows.append(
                text[
                    max(0, index - _ALIAS_WINDOW_BACK) : index
                    + len(alias)
                    + _ALIAS_WINDOW_FORWARD
                ]
            )
            start = index + len(alias)
    return "\n".join(windows)


def _has_realized_future_claim(text: str, cutoff: date) -> bool:
    sentences = re.split(r"[。！？!?；;\n]", text)
    for sentence in sentences:
        observed: list[date] = []
        for year, month, day in _ISO_DATE_RE.findall(sentence):
            try:
                observed.append(date(int(year), int(month), int(day)))
            except ValueError:
                continue
        for month, day in _CN_DATE_RE.findall(sentence):
            try:
                observed.append(date(cutoff.year, int(month), int(day)))
            except ValueError:
                continue
        if not any(item > cutoff for item in observed):
            continue
        predictive = any(mark in sentence for mark in _PREDICTIVE_MARKS)
        realized = any(mark in sentence for mark in _REALIZED_MARKS)
        if realized and not predictive:
            return True
    return False


def _serialize(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {key: _serialize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serialize(item) for item in value]
    return value
