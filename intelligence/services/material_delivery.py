"""D5 material-question delivery: identity, public substance and explicit gaps.

These are structural checks, not evidence support. A legal_gap means the writer
has disclosed a specific missing input in the matching question section. The
semantic judge must still review that disclosure and every remaining claim.
Ordinary/full contracts do not gain this material-only settlement rule.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from intelligence.services.agent_runtime import OutputEvidenceBinding
    from intelligence.services.research_contract import ResearchTaskContract


@dataclass(frozen=True)
class MaterialQuestionOutput:
    question_id: str
    output_id: str
    text: str
    delivery_kind: str = "answer"
    max_chars: int | None = None


_MEMO_REQUEST_RE = re.compile(r"(?:写|给出|输出|形成|整理|生成|提供|更新)[^。！？\n]{0,45}(?:备忘录|\bmemo\b)", re.I)
_CHAR_LIMIT_RE = re.compile(r"(?:不超过|至多|最多|限于|≤|<=)\s*(\d+)\s*字|(\d+)\s*字以内")
_HEADER_RE = re.compile(
    r"^(?:#{1,6}\s*)?(?:\*\*)?(?:【|\[)?"
    r"(?:(?:answer_)?q(?P<q>\d+)|第\s*(?P<cn>\d+)\s*题|(?P<n>\d+)[.、．)）])"
    r"(?=$|[\s:：.、．)）】\]*—-])(?:】|\])?(?:\*\*)?\s*[:：.、．)）—-]?\s*(?P<rest>.*)$",
    re.I,
)
_FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})")
_GAP_INPUT_RE = re.compile(r"(?:缺少|缺失|缺乏|未提供|未披露|未给出|尚缺|待补充|需补充)\s*([^，。；！？,;!?\n]+)")
_GAP_LIMIT_RE = re.compile(r"无法|不能|不足以|暂不|尚不能|未能")
_GENERIC_INPUT_RE = re.compile(r"(?:相关|具体|必要|更多|足够|充分|有效|完整|进一步|所需|的|材料|信息|数据|证据|内容|资料|依据|细节)")
_ALL_GAP_NOTICE = "仅凭本轮材料，以下各题均暂不能得出结论；每题缺少的输入分别列在下方。"


def material_question_outputs(contract: ResearchTaskContract) -> tuple[MaterialQuestionOutput, ...]:
    material = contract.material_contract
    if material is None or material.data_scope != "material_only" or material.needs_clarification:
        return ()
    required_ids = {item.output_id for item in contract.required_outputs if item.required}
    result = []
    for question in material.questions:
        output_id = f"answer_{question.question_id}"
        if output_id not in required_ids:
            continue
        memo = _MEMO_REQUEST_RE.search(question.text)
        # A prohibition is not a request to synthesize another output.
        is_memo = bool(memo and not re.search(r"不要|无需|不用|禁止", question.text[:memo.start()]))
        limit = _CHAR_LIMIT_RE.search(question.text) if is_memo else None
        max_chars = int(next(x for x in limit.groups() if x is not None)) if limit else None
        result.append(MaterialQuestionOutput(question.question_id, output_id, question.text, "memo" if is_memo else "answer", max_chars))
    return tuple(result)


@dataclass
class _QuestionSection:
    question_id: str
    start: int
    end: int
    lines: list[str]


def _read_question_sections(answer: str, *, include_quoted: bool = False) -> tuple[_QuestionSection, ...]:
    """One parser owns both body extraction and original-text coordinates."""
    source = str(answer or "")
    sections: list[_QuestionSection] = []
    active: _QuestionSection | None = None
    level = 0
    fence = ""
    fence_len = 0
    cursor = 0
    for line_with_ending in source.splitlines(keepends=True):
        start = cursor
        cursor += len(line_with_ending)
        raw = line_with_ending.rstrip("\r\n")
        line = raw.strip()
        fence_match = _FENCE_RE.match(raw)
        if fence_match:
            if include_quoted and active is not None:
                active.lines.append(raw)
            marker = fence_match.group(1)
            if not fence:
                fence, fence_len = marker[0], len(marker)
            elif marker[0] == fence and len(marker) >= fence_len:
                fence = ""
            continue
        if fence or line.startswith(">") or raw.startswith(("    ", "\t")):
            if include_quoted and active is not None:
                active.lines.append(raw)
            continue
        heading = re.match(r"^(#{1,6})\s*", line)
        current_level = len(heading.group(1)) if heading else 0
        match = _HEADER_RE.match(line) if not raw.startswith(" ") else None
        is_nested_list = bool(match and match.group("n") and level and not heading)
        if match and not is_nested_list and (not level or not current_level or current_level <= level):
            if active is not None:
                active.end = start
            qid = "q" + next(match.group(name) for name in ("q", "cn", "n") if match.group(name))
            active = _QuestionSection(qid, start, len(source), [] if heading else [match.group("rest")])
            sections.append(active)
            level = current_level
        elif heading and (not level or current_level <= level):
            if active is not None:
                active.end = start
            active = None
            level = 0
        elif active is not None and (not heading or include_quoted):
            active.lines.append(raw)
    return tuple(sections)


def question_sections(answer: str, *, include_quoted: bool = False) -> dict[str, tuple[str, ...]]:
    """Read original-number sections without promoting quotes/code to answers.

    Canonical form is ``## qN``. A Markdown title is not its own payload;
    nested headings stay in their question, peer headings close the section.
    Duplicate sections remain duplicates rather than last-write-wins.
    """
    result: dict[str, tuple[str, ...]] = {}
    for section in _read_question_sections(answer, include_quoted=include_quoted):
        result[section.question_id] = (*result.get(section.question_id, ()), "\n".join(section.lines).strip())
    return result


def question_section_spans(answer: str) -> tuple[tuple[str, int, int], ...]:
    """Original-text intervals, including headings; identical prose is not identity."""
    return tuple((s.question_id, s.start, s.end) for s in _read_question_sections(answer))


def append_material_supplement(
    contract: ResearchTaskContract, original: str, supplement: str,
) -> str:
    """Append within unambiguous question sections, never last-write-wins.

    Whole-answer supplements often repeat q1 while adding q2. Blindly appending
    them creates duplicate identities and makes a previously answered q1 fail.
    Use the existing parser's exact spans, not fuzzy sentence matching; genuine
    duplicate sections in either input still fail ordinary delivery validation.
    Original body text is never removed, including a disputed gap. Memo limits
    continue to count both the original and its additions.
    """
    from intelligence.services.research_annotations import append_research_supplement

    fallback = append_research_supplement(original, supplement)
    if not original.strip() or not supplement.strip() or supplement.startswith(original):
        return fallback
    if not material_question_outputs(contract):
        return fallback
    before = question_section_spans(original)
    after = question_section_spans(supplement)
    if any(len(spans) != len({qid for qid, _, _ in spans}) for spans in (before, after)):
        return fallback
    old = {qid: (start, end) for qid, start, end in before}
    insertions: dict[int, str] = {}
    remaining: list[str] = []
    cursor = 0
    for qid, start, end in after:
        remaining.append(supplement[cursor:start])
        cursor = end
        block = supplement[start:end]
        if qid not in old:
            remaining.append(block)
            continue
        old_start, old_end = old[qid]
        if original[old_start:old_end].strip() == block.strip():
            continue
        # Keep the candidate's heading words, but nest them as a supplement,
        # not a second qN identity. Nested headings count toward memo length.
        lines = block.splitlines(keepends=True)
        heading = lines[0].strip().lstrip("#").strip()
        old_header = original[old_start:old_end].splitlines()[0]
        level_match = re.match(r"^\s*(#{1,6})", old_header)
        level = len(level_match.group(1)) if level_match else 0
        candidate_heading = re.match(r"^\s*(#{1,6})", lines[0])
        # A change of heading depth could turn a nested paragraph into a peer
        # outside the question, hiding it from the memo-length check.
        if not level or level >= 6 or candidate_heading is None or len(candidate_heading.group(1)) != level:
            return fallback
        insertions[old_end] = (
            "\n\n" + "#" * (level + 1) + " 补充与修订：" + heading + "\n"
            + "".join(lines[1:]) + "\n\n"
        )
    remaining.append(supplement[cursor:])
    combined = original
    for position in sorted(insertions, reverse=True):
        combined = combined[:position] + insertions[position] + combined[position:]
    extra = "".join(remaining)
    return append_research_supplement(combined, extra)


def _normalized(text: str) -> str:
    return re.sub(r"[\W_]+", "", text, flags=re.UNICODE).casefold()


def question_body(spec: MaterialQuestionOutput, answer: str) -> str:
    blocks = question_sections(answer).get(spec.question_id, ())
    if len(blocks) != 1:
        return ""
    body = blocks[0]
    normalized = _normalized(body)
    if not normalized or normalized == _normalized(spec.text) or normalized in {"待补", "待回答", "略", "暂无", "tbd"}:
        return ""
    # Quoted/code blocks cannot establish an answer, but still take space in
    # the public memo. Count them (and Markdown decoration) conservatively;
    # never silently truncate or hide overflow in a blockquote.
    if spec.delivery_kind == "memo" and spec.max_chars is not None:
        rendered = question_sections(answer, include_quoted=True)[spec.question_id][0]
        if len(re.sub(r"\s+", "", rendered)) > spec.max_chars:
            return ""
    return body


def has_disclosed_material_gap(spec: MaterialQuestionOutput, answer: str, gap: str) -> bool:
    body = question_body(spec, answer)
    if not body or not gap.strip() or not _GAP_LIMIT_RE.search(gap):
        return False
    # Explicit missing-input clause + consequence must be public in this question.
    # Exact normalized disclosure avoids treating a neighbouring question's gap
    # or a writer-only binding as delivered. Semantic equivalence is not guessed.
    if _normalized(gap) not in _normalized(body):
        return False
    for match in _GAP_INPUT_RE.finditer(gap):
        missing_input = _normalized(match.group(1))
        specific = _GENERIC_INPUT_RE.sub("", missing_input)
        if len(specific) >= 2:
            return True
    return False


def material_delivery_missing_outputs(
    contract: ResearchTaskContract,
    answer: str,
    bindings: tuple[OutputEvidenceBinding, ...],
) -> tuple[str, ...]:
    by_id = {item.output_id: item for item in bindings}
    return tuple(
        spec.output_id for spec in material_question_outputs(contract)
        if (binding := by_id.get(spec.output_id)) is None
        or not question_body(spec, answer)
        or (binding.gap and not has_disclosed_material_gap(spec, answer, binding.gap))
    )


def with_all_material_gaps_notice(
    contract: ResearchTaskContract, answer: str, bindings: tuple[OutputEvidenceBinding, ...],
) -> str:
    specs = material_question_outputs(contract)
    if not specs:
        return answer
    by_id = {item.output_id: item for item in bindings}
    # Reconcile, not just append: a public transformation may have invalidated
    # one of the disclosures after a previous stage attached this notice.
    clean = answer.strip()
    while clean.startswith(_ALL_GAP_NOTICE):
        clean = clean[len(_ALL_GAP_NOTICE):].lstrip()
    if specs and all(
        (binding := by_id.get(spec.output_id)) is not None
        and not binding.evidence_hashes
        and has_disclosed_material_gap(spec, clean, binding.gap)
        for spec in specs
    ):
        return f"{_ALL_GAP_NOTICE}\n\n{clean}"
    return clean


def material_delivery_payload(contract: ResearchTaskContract) -> dict[str, object]:
    return {
        "questions": [asdict(spec) for spec in material_question_outputs(contract)],
        "rules": (
            "按原编号逐题用独立标题 ## qN 作答；每题仅一个 answer_qN 绑定，不合并、不重复。"
            "备忘录也是该题的交付形态，不另造第二个 memo 槽；max_chars 按正文非空白字符计数（含标点，不含题标题）。"
            "能回答的用证据支持；无法回答时在该题正文写‘缺少[具体输入]，无法[具体判断]’，"
            "将同一句交代原样放入该题 binding.gap，evidence_hashes 留空，仍保持约定的 basis。"
            "泛泛‘材料不足’或只在 binding 写缺口都算 missing。"
            "legal_gap 只证明结构上交代了缺项，不证明材料确实缺失，仍须语义审核。"
            "全部 answered 才可 completed；只要含 legal_gap 就只能 partial；遗漏须补交，不能冒充合法缺口。"
            "全题 legal_gap 须顶部声明材料不足；evidence_boundary 不是额外一道已回答的题。"
        ),
    }
