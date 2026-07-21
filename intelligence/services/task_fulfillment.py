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


@dataclass(frozen=True)
class FulfillmentItem:
    output_id: str
    status: ItemStatus
    evidence_ids: tuple[str, ...] = ()
    answer_spans: tuple[str, ...] = ()
    gap: str = ""


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
            "items": [
                {
                    "output_id": item.output_id,
                    "status": item.status,
                    "evidence_ids": list(item.evidence_ids),
                    "answer_spans": list(item.answer_spans),
                    "gap": item.gap,
                }
                for item in self.items
            ],
        }


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
}


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
        return preferred
    if normalized == "supporting_evidence":
        return tuple(
            claim
            for claim in claims
            if claim.evidence_ids
            and claim.claim_type in {"supporting_fact", "fact", "summary"}
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

        if bound and (marker or output_id in {"supporting_evidence", "direct_assessment"}):
            items.append(
                FulfillmentItem(
                    required.output_id,
                    "fulfilled",
                    tuple(dict.fromkeys(item for _, ids in bound for item in ids)),
                    tuple(claim.text for claim, _ in bound),
                )
            )
            continue
        if _gap_for_output(output_id, answer_text):
            items.append(
                FulfillmentItem(
                    required.output_id,
                    "partial",
                    gap=f"仍缺少：{required.description}",
                )
            )
            continue
        items.append(
            FulfillmentItem(
                required.output_id,
                "missing",
                gap=f"仍缺少：{required.description}",
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
) -> AnswerSpec:
    """Project an incomplete answer into the existing evidence-gap renderer.

    The gate must change the public projection, not only attach a red status to
    a still-misleading draft.  This keeps the control-plane verdict and the
    displayed text consistent while preserving the original AnswerSpec in the
    trace before projection.
    """

    missing = tuple(
        item.gap or f"仍缺少：{item.output_id}"
        for item in verdict.items
        if item.status != "fulfilled"
    )
    detail = "；".join(dict.fromkeys(missing)) or "本轮回答未覆盖用户问题的全部必需部分。"
    gap = Claim(
        claim_id="task_fulfillment:gap",
        text=f"本轮尚未完成问题所需的直接回答：{detail}",
        claim_type="evidence_gap",
        theme=answer_spec.research_spec.theme,
        status=ClaimStatus.MISSING,
    )
    return replace(
        answer_spec,
        summary=(gap,),
        verified_facts=(),
        company_table=(),
        counter_evidence=(),
        triggers=(),
        candidate_facts=(),
        gaps=(gap,),
        next_actions=("补齐上述问题相关的数据或证据后重新核验。",),
        sources=(),
        presentation_kind="evidence_gap",
        presentation_title=answer_spec.presentation_title or "证据缺口",
    )
