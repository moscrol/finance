"""Typed payload checks for structured Episode answer slots.

Evidence bindings prove that supporting material exists.  They do not prove
that a structured public slot still contains an answer.  This module owns the
small deterministic checks needed at both initial verification and
deletion-only semantic repair.
"""

from __future__ import annotations

import re

from intelligence.services.research_contract import ResearchTaskContract
from intelligence.services.task_fulfillment import (
    answer_has_non_boundary_substance,
    answer_has_output_marker,
)

JUDGMENT_OUTPUT_IDS = frozenset({"direct_answer", "direct_assessment"})

_SENTENCE_RE = re.compile(r"(?<=[。！？!?；;])|\n+")
_EXISTING_ANALYSIS_LABEL_RE = re.compile(
    r"^(?:据此判断|这说明|这意味着|基准判断|直接判断|当前判断|"
    r"替代判断|验证路径|情景判断)"
)
_INFERENCE_CUE_RE = re.compile(
    r"(?:说明|构成|更偏|不宜|优先观察|若.{0,24}则)"
)
_EXTERNAL_CAUSE_RE = re.compile(
    r"(?:政策|消息|事件|新闻).{0,16}(?:导致|因为)|"
    r"(?:导致|因为|由于).{0,12}(?:政策|消息|事件|新闻)"
)
_LABEL_PREFIX = "据此判断："


_SECTION_HEADING_RE = re.compile(
    r"^(?:#{1,6}\s*|【|(?:\d+|[一二三四五六七八九十]+)[、.．）)]\s*)"
)
_SCENARIO_SECTION_RE = re.compile(
    r"(?:(?:情景|估值)(?:区间|范围)|(?:条件化|估值)情景)"
)
_SCENARIO_LABEL_RE = re.compile(r"(?:保守|悲观|下行|中性|基准|乐观|上行)")
_INLINE_SCENARIO_LABEL_RE = re.compile(
    r"(?:保守|悲观|下行|中性|基准|乐观|上行)情景"
)
_VALUATION_VALUE_RE = re.compile(
    r"[+-]?\d+(?:\.\d+)?"
    r"(?:\s*(?:至|到|~|～|—|-)\s*[+-]?\d+(?:\.\d+)?)?"
    r"\s*(?:倍|[xX]|元|亿元|万亿元|%|％)"
)
_EXPLICIT_RANGE_VALUE_RE = re.compile(
    r"[+-]?\d+(?:\.\d+)?\s*(?:至|到|~|～|—|-)\s*"
    r"[+-]?\d+(?:\.\d+)?\s*(?:倍|[xX]|元|亿元|万亿元|%|％)?"
)
_SCENARIO_GAP_RE = re.compile(
    r"(?:无法|不能|暂不|缺少|不足|待补|待核验|尚未|未能)"
)
_SCENARIO_TABLE_HEADER_RE = re.compile(
    r"^\|.*情景.*(?:关键条件|隐含\s*(?:PB|PE|PS)|对应市值|估值).*(?:\||$)",
    re.IGNORECASE,
)
_MARKDOWN_TABLE_DIVIDER_RE = re.compile(
    r"^\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?$"
)


def _scenario_range_has_substance(answer: str) -> bool:
    in_scenario_section = False
    for raw_line in str(answer or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        is_heading = bool(_SECTION_HEADING_RE.match(line))
        if is_heading:
            in_scenario_section = bool(_SCENARIO_SECTION_RE.search(line))
            if not in_scenario_section:
                continue

        names_slot = bool(_SCENARIO_SECTION_RE.search(line))
        if in_scenario_section:
            if _SCENARIO_LABEL_RE.search(line) and _VALUATION_VALUE_RE.search(line):
                return True
            if _EXPLICIT_RANGE_VALUE_RE.search(line):
                return True
            if _SCENARIO_GAP_RE.search(line) and (
                "区间" in line
                or "范围" in line
                or "倍数" in line
                or "数值" in line
            ):
                return True
            continue

        if names_slot and (
            _EXPLICIT_RANGE_VALUE_RE.search(line)
            or _SCENARIO_GAP_RE.search(line)
        ):
            return True
        if (
            len(_INLINE_SCENARIO_LABEL_RE.findall(line)) >= 2
            and _VALUATION_VALUE_RE.search(line)
        ):
            return True
    return False


def required_outputs_without_substance(
    contract: ResearchTaskContract,
    answer: str,
) -> tuple[str, ...]:
    """Return required typed slots whose presentation shell has no payload."""

    return tuple(
        item.output_id
        for item in contract.required_outputs
        if item.required
        and item.output_id == "scenario_range"
        and not _scenario_range_has_substance(answer)
    )


def required_output_evidence_floor(output_id: str) -> tuple[str, ...]:
    """Return evidence types that must occur in this output's own binding."""

    if output_id == "financial_business_anchor":
        return ("financial_data",)
    return ()


def lost_required_output_substance(
    contract: ResearchTaskContract,
    before: str,
    after: str,
) -> tuple[str, ...]:
    """Return typed slots emptied by a deletion-only semantic repair."""

    lost: list[str] = []
    for item in contract.required_outputs:
        if not item.required:
            continue
        if item.output_id == "scenario_range":
            before_present = _scenario_range_has_substance(before)
            after_present = _scenario_range_has_substance(after)
        elif item.output_id == "direct_answer":
            # 无 marker 词表：只能看判断正文是否被删到只剩边界句。
            before_present = answer_has_non_boundary_substance(before)
            after_present = answer_has_non_boundary_substance(after)
        else:
            before_present = answer_has_output_marker(item.output_id, before)
            after_present = answer_has_output_marker(item.output_id, after)
        if before_present and not after_present:
            lost.append(item.output_id)
    return tuple(lost)


def remove_lost_output_scaffolding(
    answer: str,
    output_ids: tuple[str, ...],
) -> str:
    """Remove empty headings/table shells for a slot already marked missing."""

    if "scenario_range" not in output_ids:
        return answer
    kept: list[str] = []
    scenario_heading_removed = False
    scenario_table_header_removed = False
    for raw_line in str(answer or "").splitlines():
        line = raw_line.strip()
        if _SECTION_HEADING_RE.match(line) and _SCENARIO_SECTION_RE.search(line):
            scenario_heading_removed = True
            scenario_table_header_removed = False
            continue
        if scenario_heading_removed and _SCENARIO_TABLE_HEADER_RE.search(line):
            scenario_table_header_removed = True
            continue
        if scenario_table_header_removed and _MARKDOWN_TABLE_DIVIDER_RE.fullmatch(
            line
        ):
            scenario_heading_removed = False
            scenario_table_header_removed = False
            continue
        if line:
            scenario_heading_removed = False
            scenario_table_header_removed = False
        kept.append(raw_line)
    return "\n".join(kept).strip()


def _should_label_inference(sentence: str) -> bool:
    text = sentence.strip()
    if not text:
        return False
    if _EXISTING_ANALYSIS_LABEL_RE.match(text):
        return False
    if answer_has_output_marker("evidence_boundary", text):
        return False
    if _EXTERNAL_CAUSE_RE.search(text):
        return False
    return bool(_INFERENCE_CUE_RE.search(text))


def label_unlabelled_analytical_inferences(draft: str) -> str:
    """Prefix bare analytical inferences with the judge's explicit marker.

    Only adds ``据此判断：``. Does not invent facts, does not label boundary
    sentences, numeric-only observations, or external-cause claims.
    """

    source = str(draft or "")
    if not source.strip():
        return source
    result = source
    cursor = 0
    for raw in _SENTENCE_RE.split(source):
        text = raw.strip()
        if not text:
            continue
        start = result.find(text, cursor)
        if start < 0:
            continue
        if _should_label_inference(text):
            labeled = f"{_LABEL_PREFIX}{text}"
            result = f"{result[:start]}{labeled}{result[start + len(text):]}"
            cursor = start + len(labeled)
        else:
            cursor = start + len(text)
    return result


def contract_has_model_reasoning_judgment(contract: object) -> bool:
    return any(
        str(getattr(item, "output_id", "")) in JUDGMENT_OUTPUT_IDS
        and str(getattr(item, "grounding_mode", "evidence")) == "model_reasoning"
        for item in getattr(contract, "required_outputs", ())
    )


__all__ = [
    "JUDGMENT_OUTPUT_IDS",
    "contract_has_model_reasoning_judgment",
    "label_unlabelled_analytical_inferences",
    "lost_required_output_substance",
    "remove_lost_output_scaffolding",
    "required_output_evidence_floor",
    "required_outputs_without_substance",
]
