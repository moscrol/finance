"""Review explicit research checklists without treating witnesses as semantic proof."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from intelligence.services.user_task import classify_top_level_regions

if TYPE_CHECKING:
    from intelligence.services.research_contract import ResearchTaskContract


REQUIREMENT_CHECK_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "question_id": {"type": "string"},
            "parts": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "part_index": {"type": "integer", "minimum": 1},
                        "status": {
                            "type": "string",
                            "enum": ["fulfilled", "partial", "missing"],
                        },
                        "answer_sentence_indexes": {
                            "type": "array",
                            "items": {"type": "integer", "minimum": 1},
                            "uniqueItems": True,
                        },
                        "reason": {"type": "string", "minLength": 1},
                        "missing_aspects": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                    "required": [
                        "part_index",
                        "status",
                        "answer_sentence_indexes",
                        "reason",
                        "missing_aspects",
                    ],
                },
            },
        },
        "required": ["question_id", "parts"],
    },
}

REQUIREMENT_CHECK_RULE = (
    " 本轮另须返回 requirement_checks，恰好覆盖 requirement_review 的每个 question_id，"
    "每个 parts 恰好覆盖给定 part_index。逐项独立审查原要求，全文前置候选集合、定义与数量同样有效。"
    "每项返回 status(fulfilled/partial/missing)、answer_sentence_indexes、reason、missing_aspects。"
    "fulfilled 必须有实际回答位置且 missing_aspects=[]；partial 须有回答位置及具体缺项；"
    "missing 须无回答位置并列具体缺项。理由必须说明实际满足了哪些对象、数量、时间窗和分支，"
    "不能只说已满足。父项要求对每个对象成立时，子项也须逐个对象检查，不允许只找到一个例子。"
    "至少N项要数不同有效项，不把标题、复述要求或重复项目当答案；分别/各自的数量分别计数。"
    "公司选择、逐公司矩阵和最终分组须是同一集合，核对每组数量、重复和换入换出；"
    "逐信号核对出现、不出现/反向及第三解释，泛泛风险段不能代替逐项分析。"
    "禁止项按全文审查，fulfilled 可引用体现范围的正文，但不能因免责声明而忽略正文违规。"
    "资料缺失可以诚实披露，但披露不等于所问判断已经完成，无法核验标partial或missing。"
    "数量、集合、分母、来源期间和字数限制要实际核对；不把正增长写成未增长，"
    "不把单日量价直接当成盈利兑现或估值透支的证明。"
    "漏答不等于事实错，不为漏答捏造拒句，不删除已有正确事实。"
    "这份完成回执与逐句事实审核独立，顶层passed不能覆盖缺项；遗漏任何回执即无效。"
)


def requirement_review_rows(
    contract: ResearchTaskContract | None,
) -> list[dict[str, object]]:
    """Use the frozen questions; bullet coordinates do not create output identities."""
    if contract is None:
        return []
    material = contract.material_contract
    if (
        material is None
        or material.needs_clarification
        or material.data_scope not in {"full", "local_only"}
        or not material.questions
        or not classify_top_level_regions(contract.question).request_checklist
    ):
        return []
    rows = []
    for question in material.questions:
        # Split only explicit bullet lines. Prose/count interpretation stays semantic.
        chunks = re.split(r"(?m)^\s*[-*]\s+", question.text)
        parts = [chunk.strip() for chunk in chunks if chunk.strip()]
        rows.append(
            {
                "question_id": question.question_id,
                "text": question.text,
                "parts": [
                    {"part_index": i, "text": text} for i, text in enumerate(parts, 1)
                ],
            }
        )
    return rows


def requirement_gap_id(question_id: str) -> str:
    return f"requirement_{question_id}"


def reconcile_requirement_checks(
    payload: dict,
    requirements: list[dict[str, object]],
    sentences: list[dict[str, object]],
) -> tuple[dict[str, object], ...] | None:
    """Validate total coverage and exact witnesses, not the judge's interpretation."""
    checks = payload.get("requirement_checks")
    if not isinstance(checks, list) or len(checks) != len(requirements):
        return None
    expected = {row["question_id"]: row for row in requirements}
    candidates = {row["index"]: row for row in sentences}
    seen = set()
    results = []
    for check in checks:
        if not isinstance(check, dict) or set(check) != {"question_id", "parts"}:
            return None
        qid, parts = check["question_id"], check["parts"]
        if (
            not isinstance(qid, str)
            or qid not in expected
            or qid in seen
            or not isinstance(parts, list)
        ):
            return None
        source_parts = {row["part_index"]: row for row in expected[qid]["parts"]}
        if len(parts) != len(source_parts):
            return None
        seen_parts = set()
        reviewed = []
        for part in parts:
            keys = set(
                REQUIREMENT_CHECK_SCHEMA["items"]["properties"]["parts"]["items"][
                    "required"
                ]
            )
            if not isinstance(part, dict) or set(part) != keys:
                return None
            index, status = part["part_index"], part["status"]
            witnesses, reason, missing = (
                part["answer_sentence_indexes"],
                part["reason"],
                part["missing_aspects"],
            )
            if (
                type(index) is not int
                or index not in source_parts
                or index in seen_parts
                or not isinstance(status, str)
                or status not in {"fulfilled", "partial", "missing"}
                or not isinstance(reason, str)
                or not reason.strip()
                or not isinstance(missing, list)
                or any(not isinstance(x, str) or not x.strip() for x in missing)
                or not isinstance(witnesses, list)
                or any(type(i) is not int or i not in candidates for i in witnesses)
                or len(set(witnesses)) != len(witnesses)
                or (status != "missing") != bool(witnesses)
                or (status != "fulfilled") != bool(missing)
            ):
                return None
            if (
                any(i in payload["rejected_sentence_indexes"] for i in witnesses)
                and status == "fulfilled"
            ):
                status = "partial"
                missing = ["回答依据包含本轮被拒绝的句子，须修订后重新核验。"]
            reviewed.append(
                {
                    **part,
                    "status": status,
                    "missing_aspects": missing,
                    "text": source_parts[index]["text"],
                    "answer_sentences": [dict(candidates[i]) for i in witnesses],
                }
            )
            seen_parts.add(index)
        results.append(
            {"question_id": qid, "text": expected[qid]["text"], "parts": reviewed}
        )
        seen.add(qid)
    return tuple(results)


def invalidate_rejected_requirement_witnesses(
    checks: tuple[dict[str, object], ...],
    rejected_indexes: tuple[int, ...],
) -> tuple[dict[str, object], ...]:
    """Later fact gates can reject witnesses after the model report was parsed."""
    rejected = frozenset(rejected_indexes)
    if not rejected:
        return checks
    return tuple(
        {
            **row,
            "parts": [
                {
                    **part,
                    "status": "partial",
                    "missing_aspects": [
                        "回答依据包含本轮被拒绝的句子，须修订后重新核验。"
                    ],
                }
                if part["status"] == "fulfilled"
                and rejected.intersection(part["answer_sentence_indexes"])
                else part
                for part in row["parts"]
            ],
        }
        for row in checks
    )


def requirement_repair_notes(checks: tuple[dict[str, object], ...]) -> tuple[str, ...]:
    return tuple(
        f"原要求 {row['question_id']}：{row['text']}\n"
        f"未完成部分：{part['text']}\n缺项：{'；'.join(part['missing_aspects'])}"
        for row in checks
        for part in row["parts"]
        if part["status"] != "fulfilled"
    )
