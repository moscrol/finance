"""Final semantic task-completion gate.

The existing evidence and grounding gates answer "can this sentence be
checked?".  This module answers the narrower, separate question "did the
public answer cover each required output of the turn?".  It deliberately uses
the existing structured claim/source registry first; no LLM is needed for the
first deterministic gate.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Iterable, Literal, Mapping

from intelligence.services.answer_model import (
    AnswerSpec,
    Claim,
    ClaimStatus,
    EvidenceRef,
)
from intelligence.services.research_contract import RequiredOutput


FulfillmentStatus = Literal["complete", "partial", "missing"]
ItemStatus = Literal["fulfilled", "partial", "missing"]

# 未绑定的机器可读原因。``gap`` 那句中文是给人看的，但它把四种成因写进了同一个
# 句子里——想统计「到底哪一种最常见」就得反过来解析中文，而那句话的措辞随时会改。
#
# 这四个码对应 ``evaluate_task_fulfillment`` 里那组 if/elif 分支，一一对应，
# 不多不少：
#   no_candidate_claim  registry 里没有该输出对应的 claim（候选取不到）
#   text_absent         有候选，但正文里没有出现它们的文本
#   evidence_unbound    正文写到了，但证据没能绑上
#   marker_absent       已绑定，但正文缺少该输出的措辞标记
#   unspecified         以上都不是（兜底，正常情况下不该出现）
#
# ``task_fulfillment`` 那段注释自己写了原因：「四种情况长得一模一样，正是这道
# 门禁坏了很久没被发现的原因」。把成因升成字段，是让那句话在数据层也成立。
FulfillmentReasonCode = Literal[
    "",
    "no_candidate_claim",
    "text_absent",
    "evidence_unbound",
    "marker_absent",
    "unspecified",
]


@dataclass(frozen=True)
class FulfillmentItem:
    output_id: str
    status: ItemStatus
    evidence_ids: tuple[str, ...] = ()
    answer_spans: tuple[str, ...] = ()
    gap: str = ""
    # 只在 status != "fulfilled" 时有值；fulfilled 项留空字符串。
    reason_code: FulfillmentReasonCode = ""
    # 该输出实际取到了几条候选 claim。配合 reason_code 才能区分
    # 「一条都没取到」和「取到了但对不上」——这两种要修的地方完全不同。
    candidate_count: int = 0


@dataclass(frozen=True)
class FulfillmentVerdict:
    status: FulfillmentStatus
    items: tuple[FulfillmentItem, ...]
    reason: str = ""

    @property
    def missing_required(self) -> tuple[FulfillmentItem, ...]:
        return tuple(item for item in self.items if item.status != "fulfilled")

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "reason": self.reason,
            # 本轮**实际被评估**的 output_id 全集（post-alias）。
            #
            # 这不等于 TaskFrame 的 required_outputs：契约在到达这里之前经过
            # ``_merge_frame_outputs`` 的别名归一（direct_answer→direct_assessment
            # 等），所以「门禁到底按哪张词表打分」只有在这一层才是确定的。
            # 落盘之前，下游想复算就只能拿 frame 词表去猜，猜的和实际评的不是
            # 同一张表。
            "evaluated_output_ids": [item.output_id for item in self.items],
            # 未绑定成因的分布，省掉下游解析中文 gap 的步骤。
            "reason_code_counts": _reason_code_counts(self.items),
            "items": [
                {
                    "output_id": item.output_id,
                    "status": item.status,
                    "evidence_ids": list(item.evidence_ids),
                    "answer_spans": list(item.answer_spans),
                    "gap": item.gap,
                    "reason_code": item.reason_code,
                    "candidate_count": item.candidate_count,
                }
                for item in self.items
            ],
        }


def _reason_code_counts(items: tuple[FulfillmentItem, ...]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        if not item.reason_code:
            continue
        counts[item.reason_code] = counts.get(item.reason_code, 0) + 1
    return counts


_GAP_PATTERN = re.compile(
    r"(?:仍缺少|尚缺少|缺少.+(?:证据|数据|资料)|无法确认|暂不下结论|"
    r"未取得|不足以独立确认|不能形成可靠定性|只能作为线索)"
)
_TOKEN_PATTERN = re.compile(r"[\u4e00-\u9fff]{2,8}|[A-Za-z][A-Za-z0-9_.-]{1,}|\d+(?:\.\d+)?")
_TOKEN_STOPWORDS = frozenset(
    {
        "当前",
        "市场",
        "问题",
        "依据",
        "判断",
        "数据",
        "证据",
        "本轮",
        "相关",
        "同日",
        "情况",
        "条件",
        "情景",
        "需要",
        "进行",
        "可能",
        "如果",
        "继续",
        "以及",
    }
)
# 这些必需输出的内容本质上可以没有出处：证伪条件、风险和「尚无反向证据」是推理
# 结论，不是可回查的事实。对它们只校验「有没有写进正文」，不校验「有没有出处」。
#
# evidence_boundary 同理，而且更彻底：它陈述的是「本轮证据到哪为止」——覆盖范围、
# 数据日期、缺口。这是关于证据集合本身的陈述，不是集合里的一条事实，要求它再绑一
# 条出处是范畴错误。
_UNSOURCEABLE_OUTPUTS = frozenset(
    {"counterpoint", "counter_evidence", "risk", "evidence_boundary"}
)
# 生产者实际写进 Claim.claim_type 的值。注意不要用 marker 里看到的
# expectation/gap——那是 _grounded_claim_type() 按 ClaimStatus 推出来的显示类型，
# 不是 claim_type 本身。第一版豁免就是照着显示类型写的，所以一次都没触发过。
# evidence_gap 是同一个坑的第二例：marker 里显示成 gap，ask.py 写进去的是 evidence_gap。
_UNSOURCEABLE_CLAIM_TYPES = frozenset(
    {"counter_evidence", "risk", "expectation", "gap", "skill_gap", "evidence_gap"}
)

_MARKERS: dict[str, tuple[str, ...]] = {
    "direct_assessment": (
        "当前主线",
        "主线是",
        "基准判断",
        "当前判断",
        "直接判断",
        "基准偏向",
        "更偏向",
        "更可能",
        "倾向",
        "暂不下结论",
    ),
    "supporting_evidence": (
        "依据",
        "证据",
        "数据",
        "盘面",
        "涨停",
        "成交",
        "市场宽度",
    ),
    "rebound_case": ("反弹",),
    "decline_case": ("继续下跌", "下跌情景", "走弱"),
    "invalidation": ("失效条件", "失效", "证伪"),
    "counterpoint": ("反证", "风险", "相反", "但", "除非"),
    # Canonical TaskFrame slots.  These stay semantic (what the answer must
    # contain) instead of being collapsed into a loosely related legacy slot.
    "current_baseline": ("当前基准", "最新基线", "基准判断", "当前状态"),
    "duration_assessment": (
        "反弹持续时间",
        "持续时间",
        "持续多久",
        "持续性",
        "延续时间",
        "观察窗口",
    ),
    "continuation_conditions": (
        "继续成立的条件",
        "延续条件",
        "继续条件",
        "成立条件",
        "触发条件",
    ),
    "invalidation_conditions": ("失效条件", "失效", "证伪"),
    # episode_factory 给这个输出的规范描述是「说明证据覆盖范围、数据日期与缺口」，
    # 措辞标记就照这三件事收：覆盖 / 日期 / 缺口。刻意不收「不构成」（会命中
    # 「不构成投资建议」这句免责模板）和裸「缺口」（行情语境里是跳空缺口）。
    "evidence_boundary": (
        "证据边界",
        "数据边界",
        "证据覆盖",
        "覆盖范围",
        "数据截至",
        "数据日期",
        "证据缺口",
        "关键缺口",
        "独立证据",
        "不等同于",
    ),
    "scenario_paths": ("情景路径", "情景", "路径"),
    # episode_factory 给 prior_recall 的规范描述是「复述用户此前对该主体的判断或
    # 纠偏原则，并说明与当前的差异」，所以措辞标记按这两件事收：复述先验 + 差异。
    #
    # 没有这一条时 output_marker_is_checkable("prior_recall") 恒为 False，而
    # answer_has_output_marker 对「缺这一格」和「没法看这一格」返回同一个 False——
    # 于是覆盖度统计会把一个瞎仪表读成 0% 覆盖。既有注释已经点过这个坑，新槽位
    # 不能再犯一次。
    "prior_recall": (
        "此前判断",
        "之前判断",
        "上次判断",
        "过去判断",
        "历史判断",
        "原有判断",
        "先前看法",
        "此前看法",
        "纠偏原则",
        "相比上次",
        "与此前",
        "较此前",
        "变化在于",
    ),
    "chain_mapping": ("产业链", "上游", "中游", "下游", "链条"),
    "financial_assessment": ("财务判断", "收入", "利润", "盈利", "现金流"),
    "metric_evidence": ("财务指标", "指标", "同比", "毛利率", "净利率"),
}

# 措辞门禁的豁免槽位：这两格的语义（判断动词 / 证据名词）几乎必然出现在任何
# 合格答案里，强行要求标记词只会制造假缺口。evaluate_task_fulfillment 的
# fulfilled 分支与 marker_vocabulary_hint 共用这一份，别在两处各写一个集合。
_MARKER_EXEMPT_OUTPUTS = frozenset({"supporting_evidence", "direct_assessment"})


def _tokens(text: str) -> set[str]:
    result: set[str] = set()
    for token in _TOKEN_PATTERN.findall(str(text or "")):
        if token in _TOKEN_STOPWORDS:
            continue
        result.add(token)
        if re.fullmatch(r"[\u4e00-\u9fff]+", token):
            for width in (2, 3, 4):
                result.update(
                    token[index : index + width]
                    for index in range(0, len(token) - width + 1)
                )
    return result


def _normalise(text: str) -> str:
    without_citations = re.sub(r"\[[A-Z]\d+\]", "", str(text or ""))
    return re.sub(r"\s+", "", without_citations).strip("：:，,。；; ")


def _claim_text_present(claim: Claim, answer_text: str) -> bool:
    claim_text = _normalise(claim.text)
    answer = _normalise(answer_text)
    if claim_text and claim_text in answer:
        return True
    overlap = _tokens(claim.text).intersection(_tokens(answer_text))
    return len(overlap) >= 2


# 研究 owner 的 claim_id 命名空间 → required output。
#
# 上面的 exact 判定做的是 `output_id in claim_id`，方向正好反了：owner 发的是
# `counter:1`，而 `"counterpoint" in "counter:1"` 恒为假。于是 counterpoint、
# chain_mapping 这些 output 一条候选都取不到，题材类问题在结构上永远无法完成——
# 实测一份 905 字、带 claim_ids 与 evidence_atom_ids 内联绑定的完整答案
# （固态电池：盘面转强但公司层面无可回查证据）被整份丢弃，换成 190 字的
# 「请补充数据源或稍后重试」。
_OUTPUT_CLAIM_NAMESPACES: dict[str, frozenset[str]] = {
    "direct_assessment": frozenset({"summary", "generic", "assessment"}),
    "answer": frozenset({"summary", "generic", "assessment"}),
    "conclusion": frozenset({"summary", "generic", "assessment"}),
    # direct_definition 走同一组命名空间：定义题的「直接回答」就是那句定义，owner
    # 把它和别的结论一样写在 summary:/generic: 下，没有单独的定义命名空间。此前它
    # 不在本表、不在 _OUTPUT_CLAIM_TYPES、也不会被 claim_id/正文精确命中，
    # _claim_candidates 三条路径全不命中 → 候选恒为空 → no_candidate_claim 恒成立。
    # 于是只要 TaskFrame 要求这一项（concept_definition 题型必然要求；个股深挖的
    # 追问会因为 user_goal 落在「解释定义」而一并要求），答案再完整也整份
    # fail-closed。2026-08-02 起 E2E「个股深挖追问」实测就是这样被打成 378 字的
    # 「请补充数据源或稍后重试」，而同一份正文里 direct_assessment 认领的正是
    # 「英维克的研究范围是：…」那句定义。
    "direct_definition": frozenset({"summary", "generic", "assessment"}),
    "counterpoint": frozenset({"counter", "risk"}),
    "counter_evidence": frozenset({"counter", "risk"}),
    "risk": frozenset({"counter", "risk"}),
    "chain_mapping": frozenset({"chain", "company", "exposure"}),
}

# 有些必需输出靠 claim_id 命名空间根本认不出来：预测题里 ask.py 写出的每一条
# claim 都在 `generic:` 下（generic:verified:6、generic:gap:1、generic:rebound_case
# …），命名空间不带任何区分度，按它取候选等于全取或全不取。这类输出改按
# claim_type 认领——那才是生产者留下的语义标签。
#
# evidence_boundary 对应的就是 ask.py 写的 evidence_gap claim（「未取得可直接预测
# 下一交易日方向的独立证据；以上仅为条件化情景，不给出概率」）。它一直存在、一直
# 写进了正文，只是门禁没有任何一条规则会去认领它，于是恒判「registry 里没有该输
# 出对应的 claim」，整份答案被 fail-closed。
_OUTPUT_CLAIM_TYPES: dict[str, frozenset[str]] = {
    "evidence_boundary": frozenset({"evidence_gap", "gap", "skill_gap"}),
}


def _claim_candidates(
    output_id: str,
    claims: tuple[Claim, ...],
) -> tuple[Claim, ...]:
    normalized = output_id.casefold()
    exact = tuple(
        claim
        for claim in claims
        if normalized in claim.claim_id.casefold()
        or normalized in claim.text.casefold()
    )
    if exact:
        return exact
    if normalized in {"direct_assessment", "answer", "conclusion"}:
        preferred = tuple(
            claim
            for claim in claims
            if claim.claim_id in {"generic:summary", "generic:assessment"}
            or claim.claim_type in {"summary", "cause_attribution"}
        )
        # 空就继续往下走命名空间映射，不要提前返回：研究 owner 发的是
        # summary:market / summary:company-gap，claim_type 是 fact，
        # 两个条件都不满足，于是结论候选恒为空。
        if preferred:
            return preferred
    if normalized == "supporting_evidence":
        return tuple(
            claim
            for claim in claims
            if claim.evidence_ids
            and claim.claim_type in {"supporting_fact", "fact", "summary"}
            and not any(
                marker in claim.text
                for marker in ("使用边界", "不等于题材主线", "证据边界")
            )
        )
    namespaces = _OUTPUT_CLAIM_NAMESPACES.get(normalized)
    if namespaces:
        by_namespace = tuple(
            claim
            for claim in claims
            if claim.claim_id.split(":", 1)[0].casefold() in namespaces
        )
        if by_namespace:
            return by_namespace
    claim_types = _OUTPUT_CLAIM_TYPES.get(normalized)
    if claim_types:
        return tuple(
            claim
            for claim in claims
            if str(claim.claim_type or "").casefold() in claim_types
        )
    return ()


def _source_text(source: EvidenceRef) -> str:
    return " ".join(
        value
        for value in (source.source, source.detail, source.source_date or "")
        if value
    )


def _evidence_supports_claim(
    claim: Claim,
    sources: Mapping[str, EvidenceRef],
    *,
    output_id: str,
) -> bool:
    bound_sources = tuple(
        sources[evidence_id]
        for evidence_id in claim.evidence_ids
        if evidence_id in sources and sources[evidence_id].freshness != "stale"
    )
    if not bound_sources:
        return False
    claim_tokens = _tokens(claim.text)
    source_tokens = set().union(*(_tokens(_source_text(item)) for item in bound_sources))
    if claim_tokens.intersection(source_tokens):
        return True
    # 图谱映射类 claim 的来源描述是文件路径（knowledge-base · wiki/relations/
    # entity_exposures.json），而 claim 是中文句子，词元交集恒为空——凡是来自知识
    # 图谱的 claim 都永远绑不上，chain_mapping 因此无论正文怎么写都判缺。
    #
    # 对这类 claim，「图谱里有这条边」本身就是它的证据：claim 是那条边的复述，
    # 图谱文件就是出处。要求它和路径字符串有字面重合是范畴错误。仍然要求 claim
    # 真的绑定到了一个未过期的来源，只是不再要求字面重合。
    if claim.claim_type in {"company_mapping", "theme_mapping"}:
        return True
    # Scenario claims are conditional projections of current market facts.  A
    # market-data source can support the branch structure without containing the
    # literal word “反弹” or “下跌”; unrelated sources cannot.
    if output_id in {"rebound_case", "decline_case", "invalidation"}:
        market_tokens = {"指数", "市场", "涨停", "跌停", "成交", "上涨", "下跌", "盘面", "结构"}
        return bool(source_tokens.intersection(market_tokens))
    if output_id == "direct_assessment" and claim.claim_type in {
        "summary",
        "cause_attribution",
    }:
        # A forecast's baseline can be a conditional projection rather than a
        # literal restatement of one data row.  It still needs a current market
        # source; an unrelated industry review must not satisfy this branch.
        market_tokens = {"指数", "市场", "涨停", "跌停", "成交", "上涨", "下跌", "盘面", "结构"}
        return bool(source_tokens.intersection(market_tokens))
    return False


def _has_output_marker(output_id: str, answer_text: str) -> bool:
    normalized = _normalise(answer_text)
    markers = _MARKERS.get(output_id, ())
    return any(marker in normalized for marker in markers)


def answer_has_output_marker(output_id: str, answer_text: str) -> bool:
    """Return whether a known required-output marker appears in public prose."""

    return _has_output_marker(output_id, answer_text)


def output_marker_is_checkable(output_id: str) -> bool:
    """Return whether ``_MARKERS`` can decide this output at all.

    ``answer_has_output_marker`` returns ``False`` both when the prose is
    missing the slot and when no marker vocabulary exists for it.  A caller
    that only records "absent" therefore cannot tell "the answer skipped it"
    from "we have no way to look".  Observation call sites must split those
    two, otherwise the resulting numbers read as coverage failures when they
    are really instrument gaps.
    """

    return bool(_MARKERS.get(output_id.casefold(), ()))


def marker_vocabulary_hint(output_id: str, *, limit: int = 6) -> str:
    """该输出若受措辞门禁约束，返回「接受的标记词」提示；否则空串。

    门禁按 ``_MARKERS`` 的子串判 ``marker_absent``，而模型此前看不到这张词表。
    实测（08-01 验收 C5）：24 条证据全部绑定，只因 counterpoint 缺一个标记词，
    整份答案被换成缺口模板——模型在一张它看不见的评分表上被打分，且回灌的
    诊断只说「缺少措辞标记」、不说哪些词算数，补写轮也无从改起。

    提示注入两处：初次合成的 ``prompt_constraints``（``render_prompt_constraint``）
    与 ``marker_absent`` 的 gap 文本（补写回灌自动携带）。都走本函数，
    词表只有 ``_MARKERS`` 一处真源。

    豁免槽位（``_MARKER_EXEMPT_OUTPUTS``）返回空串：门禁本就不对它们做措辞
    要求，提示只会稀释真正需要遵守的那几条。
    """

    key = str(output_id or "").casefold()
    if key in _MARKER_EXEMPT_OUTPUTS:
        return ""
    phrases = _MARKERS.get(key, ())
    if not phrases:
        return ""
    return "验收接受的措辞标记（正文含任一即可）：" + "、".join(phrases[:limit])


def render_prompt_constraint(required: RequiredOutput) -> str:
    """合成 prompt 里一行验收标准：``output_id：描述（+标记词提示）``。

    ``answer_model`` 按「output_id：描述」在第一个全角冒号处拆分登记合法标题
    （``_legal_heading_subjects``），提示追加在描述之后、括号内，拆分不受影响。
    """

    hint = marker_vocabulary_hint(required.output_id)
    suffix = f"（{hint}）" if hint else ""
    return f"{required.output_id}：{required.description}{suffix}"


def evaluate_marker_coverage(
    required_outputs: Iterable[str],
    answer_text: str,
) -> dict[str, object]:
    """Record which required outputs' wording reached the public prose.

    This is the marker half of ``evaluate_task_fulfillment``, split out so both
    engines can run it.  The full gate needs an ``AnswerSpec`` claim registry.
    Engine A (continuous episode) has none, and Engine B's ``POST /api/runs``
    path does not build one either.  Running those paths through
    ``evaluate_answer_spec_fulfillment`` with empty claims would take the
    ``no_candidate_claim`` branch for every output and report a wall of false
    gaps.  The marker check needs only the prose, so it works on both — which
    also makes the two engines' completion numbers comparable for the first
    time.

    ``uncheckable`` is counted apart from ``absent`` on purpose.
    ``answer_has_output_marker`` returns ``False`` both for "the prose skipped
    this slot" and for "no marker vocabulary exists for this slot"; folding
    them together would report instrument gaps as coverage failures.
    """

    present: list[str] = []
    absent: list[str] = []
    uncheckable: list[str] = []
    output_ids = tuple(
        dict.fromkeys(str(item) for item in required_outputs if str(item).strip())
    )
    for output_id in output_ids:
        normalized = output_id.casefold()
        if not output_marker_is_checkable(normalized):
            uncheckable.append(output_id)
        elif answer_has_output_marker(normalized, answer_text):
            present.append(output_id)
        else:
            absent.append(output_id)
    checked = len(present) + len(absent)
    return {
        "required_output_count": len(output_ids),
        "checked_count": checked,
        "present": present,
        "absent": absent,
        "uncheckable": uncheckable,
        # 只在真的检了东西时才给判定；全 uncheckable 时给 None 而不是 "complete"，
        # 否则「没得检」会被读成「检过且通过」——那正是 answer_status 现在的毛病。
        "marker_coverage": (
            "complete" if checked and not absent
            else "incomplete" if absent
            else None
        ),
        "observation_only": True,
    }


def _gap_for_output(output_id: str, answer_text: str) -> bool:
    if not _GAP_PATTERN.search(answer_text):
        return False
    normalized = output_id.casefold()
    if normalized == "direct_assessment":
        if (
            "仍缺少针对用户问题的直接判断" in _normalise(answer_text)
            and "当前主线判断" not in _normalise(answer_text)
            and "基准判断" not in _normalise(answer_text)
        ):
            return False
        return any(
            marker in _normalise(answer_text)
            for marker in ("直接判断", "当前主线判断", "基准判断", "当前判断")
        )
    return _has_output_marker(output_id, answer_text)


def evaluate_task_fulfillment(
    *,
    question: str,
    required_outputs: tuple[RequiredOutput, ...],
    answer_text: str,
    claims: Iterable[Claim] = (),
    sources: Iterable[EvidenceRef] = (),
) -> FulfillmentVerdict:
    """Evaluate the final public answer without rewriting it.

    ``question`` is retained in the interface and trace call sites even though
    the first deterministic implementation relies on the already resolved
    ``required_outputs``.  This keeps the seam ready for a later semantic-judge
    adapter without making the current hard gate model-dependent.
    """

    is_forecast = bool(re.search(r"(?:明天|反弹|继续下跌|下一交易日)", question))
    output_items = tuple(required_outputs)
    if not output_items:
        return FulfillmentVerdict("complete", ())

    claim_items = tuple(claims)
    source_map = {
        source.evidence_id: source
        for source in sources
        if source.evidence_id
    }
    items: list[FulfillmentItem] = []
    for required in output_items:
        output_id = required.output_id.casefold()
        candidates = _claim_candidates(output_id, claim_items)
        marker = _has_output_marker(output_id, answer_text)
        bound: list[tuple[Claim, tuple[str, ...]]] = []
        for claim in candidates:
            evidence_ids = tuple(
                evidence_id
                for evidence_id in claim.evidence_ids
                if evidence_id in source_map
            )
            claim_in_answer = _claim_text_present(claim, answer_text)
            if output_id == "supporting_evidence" and not claim_in_answer:
                claim_in_answer = bool(
                    _tokens(claim.text).intersection(_tokens(answer_text))
                )
            if output_id == "direct_assessment" and is_forecast and not claim_in_answer:
                # 预测基准是从当前市场结构推出的条件化判断，原文不必复制
                # 每个证据短语；仍要求来源是当前市场域且不是旧/无关材料。
                claim_in_answer = _normalise(claim.text) in _normalise(answer_text)
            if (
                evidence_ids
                and _evidence_supports_claim(
                    claim,
                    source_map,
                    output_id=output_id,
                )
                and claim_in_answer
            ):
                bound.append((claim, evidence_ids))
            elif (
                claim_in_answer
                and not evidence_ids
                and output_id in _UNSOURCEABLE_OUTPUTS
                and claim.claim_type in _UNSOURCEABLE_CLAIM_TYPES
            ):
                # 反证/风险常常本来就没有证据：「若公司在互动易否认，这条逻辑会弱化」
                # 是证伪条件，不是有出处的事实。要求它绑定证据是范畴错误——实测
                # counter:1/counter:2 的 evidence_atom_ids 恒为空、claim_type=expectation，
                # 于是 counterpoint 永远判缺、整份答案被 fail-closed。
                #
                # generic_research_owner 早就有同样的例外（「尚无反向证据」是可审计
                # 结论），只是它精确匹配 counter_evidence，而这里的 id 叫 counterpoint。
                #
                # 门禁仍然校验：该证伪条件必须真的写进了正文。只是不再要求它有出处。
                bound.append((claim, ()))

        marker_required = bool(_MARKERS.get(output_id))
        if bound and (
            marker
            or not marker_required
            or output_id in _MARKER_EXEMPT_OUTPUTS
        ):
            items.append(
                FulfillmentItem(
                    required.output_id,
                    "fulfilled",
                    tuple(dict.fromkeys(item for _, ids in bound for item in ids)),
                    tuple(claim.text for claim, _ in bound),
                )
            )
            continue
        # 说清楚为什么没绑上。「仍缺少 X」不说原因，正是这道门禁坏了很久没被发现的
        # 原因：候选取不到、正文没写、证据对不上、marker 缺失，四种情况长得一模一样。
        #
        # ``reason_code`` 是同一组判断的机器可读版本，和下面的中文一一对应。加它
        # 而不是让下游解析中文，因为那句措辞随时会改，而统计要跨版本可比。
        if not candidates:
            why = "registry 里没有该输出对应的 claim"
            reason_code: FulfillmentReasonCode = "no_candidate_claim"
        elif not any(_claim_text_present(c, answer_text) for c in candidates):
            why = f"候选 {len(candidates)} 条，但正文里没有出现它们的文本"
            reason_code = "text_absent"
        elif not bound:
            why = f"候选 {len(candidates)} 条且正文已写到，但证据未能绑定"
            reason_code = "evidence_unbound"
        elif marker_required and not marker:
            # 带上接受的标记词：这段 gap 会原样进补写回灌
            # （fulfillment_revision_user_content），只说「缺少标记」不说哪些词
            # 算数，模型无从改起——同「把工具拒绝的具体原因回灌给模型」一条纪律。
            hint = marker_vocabulary_hint(output_id)
            why = "已绑定，但正文缺少该输出的措辞标记" + (
                f"；{hint}" if hint else ""
            )
            reason_code = "marker_absent"
        else:
            why = "未满足"
            reason_code = "unspecified"
        detail = f"仍缺少：{required.description}（{why}）"
        if _gap_for_output(output_id, answer_text):
            items.append(
                FulfillmentItem(
                    required.output_id,
                    "partial",
                    gap=detail,
                    reason_code=reason_code,
                    candidate_count=len(candidates),
                )
            )
            continue
        items.append(
            FulfillmentItem(
                required.output_id,
                "missing",
                gap=detail,
                reason_code=reason_code,
                candidate_count=len(candidates),
            )
        )

    required_items = tuple(
        item
        for required, item in zip(output_items, items)
        if required.required
    )
    if all(item.status == "fulfilled" for item in required_items):
        return FulfillmentVerdict("complete", tuple(items))
    if any(item.status == "partial" for item in required_items):
        return FulfillmentVerdict("partial", tuple(items), "存在问题相关但尚未完成的输出")
    return FulfillmentVerdict("missing", tuple(items), "至少一个必需输出未出现在最终正文")


def evaluate_answer_spec_fulfillment(
    *,
    question: str,
    required_outputs: tuple[RequiredOutput, ...],
    answer_text: str,
    answer_spec: AnswerSpec,
) -> FulfillmentVerdict:
    """Adapter from the existing AnswerSpec registry to the deep gate seam."""

    claims = tuple(
        dict.fromkeys(
            (
                *answer_spec.summary,
                *answer_spec.verified_facts,
                *answer_spec.counter_evidence,
                *answer_spec.gaps,
                *answer_spec.triggers,
                *answer_spec.candidate_facts,
                *(
                    claim
                    for company in answer_spec.company_table
                    for claim in company.claims
                ),
            )
        )
    )
    return evaluate_task_fulfillment(
        question=question,
        required_outputs=required_outputs,
        answer_text=answer_text,
        claims=claims,
        sources=answer_spec.sources,
    )


def fail_closed_answer_spec(
    answer_spec: AnswerSpec,
    verdict: FulfillmentVerdict,
    *,
    llm_failure_summary: str | None = None,
) -> AnswerSpec:
    """Project an incomplete answer into the existing evidence-gap renderer.

    The gate must change the public projection, not only attach a red status to
    a still-misleading draft.  This keeps the control-plane verdict and the
    displayed text consistent while preserving the original AnswerSpec in the
    trace before projection.

    When *llm_failure_summary* is provided (e.g. "3 次调用均失败（timeout×2,
    http_502×1）"), it is prepended to the gap text so the user can distinguish
    "the AI model was unavailable" from "we have no data on this topic".
    """

    missing = tuple(
        item.gap or f"仍缺少：{item.output_id}"
        for item in verdict.items
        if item.status != "fulfilled"
    )
    detail = "；".join(dict.fromkeys(missing)) or "本轮回答未覆盖用户问题的全部必需部分。"
    gap_text = f"本轮尚未完成问题所需的直接回答：{detail}"
    if llm_failure_summary:
        gap_text = f"{llm_failure_summary}。{gap_text}"
    gap = Claim(
        claim_id="task_fulfillment:gap",
        text=gap_text,
        claim_type="evidence_gap",
        theme=answer_spec.research_spec.theme,
        status=ClaimStatus.MISSING,
    )
    # 已经绑定到真实证据的事实予以保留：契约未完成说的是「这份回答没覆盖用户
    # 问题的全部必需部分」，不是「查到的东西都是假的」。原先一律清空，导致
    # 一个缺失的措辞标记（counterpoint 只要求正文出现 反证/风险/相反/但/除非
    # 之一）就把整张公司表和全部已核验事实一起丢掉——C5 那道纯查价题就是这么
    # 变成一句失败桩的。渲染仍切到 evidence_gap，缺口仍排在最前，不会把没完成
    # 的草稿当成完整回答呈现。
    kept_facts = tuple(
        claim for claim in answer_spec.verified_facts if claim.evidence_ids
    )
    kept_companies = tuple(
        company
        for company in answer_spec.company_table
        if any(claim.evidence_ids for claim in company.claims)
    )
    kept_sources = ()
    if kept_facts or kept_companies:
        bound_ids = {
            evidence_id
            for claim in (
                *kept_facts,
                *(claim for company in kept_companies for claim in company.claims),
            )
            for evidence_id in claim.evidence_ids
        }
        kept_sources = tuple(
            source for source in answer_spec.sources if source.evidence_id in bound_ids
        )
    return replace(
        answer_spec,
        summary=(gap,),
        verified_facts=kept_facts,
        company_table=kept_companies,
        counter_evidence=(),
        triggers=(),
        candidate_facts=(),
        gaps=(gap,),
        next_actions=("补齐上述问题相关的数据或证据后重新核验。",),
        sources=kept_sources,
        presentation_kind="evidence_gap",
        presentation_title=answer_spec.presentation_title or "证据缺口",
    )
