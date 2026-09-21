"""E2 的不可变输入语义载体；不执行 IO、不授予能力、不从助手答案猜基底。"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import re

from intelligence.services.user_task import (
    TopLevelRegions,
    is_material_only_instruction,
    _B_RELAX_PHRASES,
    _FICTIONAL_SENT_RE,
    _HYPOTHESIS_STRONG_RE,
    _is_local_only_head,
    _state_head,
)


@dataclass(frozen=True)
class PremiseMark:
    text_ref: str
    authenticity: str
    source_turn: int
    scope: str


@dataclass(frozen=True)
class MaterialQuestion:
    question_id: str
    text: str


@dataclass(frozen=True)
class MaterialContract:
    """A轴与B轴独立；未确认的值是None，不能序列化成默认full。"""

    classification: str
    authenticity: str | None
    data_scope: str | None
    premise_marks: tuple[PremiseMark, ...] = ()
    questions: tuple[MaterialQuestion, ...] = ()
    continuation_requested: bool = False
    uncertain_reasons: tuple[str, ...] = ()
    data_scope_declared: bool = False

    @property
    def needs_clarification(self) -> bool:
        return self.classification in {"boundary_uncertain", "state_unavailable"}

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: object) -> MaterialContract:
        """非法/残缺持久化合同拒绝恢复；调用方不能悄悄丢字段再走默认权限。"""
        if not isinstance(value, dict):
            raise ValueError("invalid material contract")
        status = value.get("classification")
        if status not in {"constraint_confirmed", "no_constraint_confirmed", "boundary_uncertain", "state_unavailable"}:
            raise ValueError("invalid material boundary status")
        authenticity = value.get("authenticity")
        data_scope = value.get("data_scope")
        if authenticity not in {None, "real", "fictional"} or data_scope not in {None, "full", "local_only", "material_only"}:
            raise ValueError("invalid material axes")
        if status in {"constraint_confirmed", "no_constraint_confirmed"} and (authenticity is None or data_scope is None):
            raise ValueError("confirmed material contract requires both axes")
        if status == "state_unavailable" and (authenticity is not None or data_scope is not None):
            raise ValueError("unavailable base cannot restore resolved axes")
        continuation = value.get("continuation_requested", False)
        declared = value.get("data_scope_declared", False)
        if not isinstance(continuation, bool) or not isinstance(declared, bool):
            raise ValueError("invalid continuation flag")
        marks = value.get("premise_marks", ())
        questions = value.get("questions", ())
        reasons = value.get("uncertain_reasons", ())
        if any(not isinstance(items, (list, tuple)) for items in (marks, questions, reasons)):
            raise ValueError("invalid material contract collections")
        parsed_marks = []
        for mark in marks:
            if not isinstance(mark, dict):
                raise ValueError("invalid premise mark")
            source_turn = mark.get("source_turn")
            scope = mark.get("scope")
            text_ref = mark.get("text_ref")
            if (
                not isinstance(source_turn, int) or isinstance(source_turn, bool) or source_turn < 0
                or mark.get("authenticity") not in {"fictional", "unverified_belief"}
                or not isinstance(scope, str) or not re.fullmatch(r"message|q\d+", scope)
                or not isinstance(text_ref, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", text_ref)
            ):
                raise ValueError("invalid premise mark fields")
            parsed_marks.append(PremiseMark(text_ref, mark["authenticity"], source_turn, scope))
        parsed_questions = []
        for question in questions:
            if not isinstance(question, dict):
                raise ValueError("invalid material question")
            qid, text = question.get("question_id"), question.get("text")
            if not isinstance(qid, str) or not re.fullmatch(r"q\d+", qid) or not isinstance(text, str) or not text.strip():
                raise ValueError("invalid material question fields")
            parsed_questions.append(MaterialQuestion(qid, text))
        if len({q.question_id for q in parsed_questions}) != len(parsed_questions):
            raise ValueError("duplicate material question")
        if any(not isinstance(reason, str) or not reason for reason in reasons):
            raise ValueError("invalid material uncertainty reason")
        return cls(status, authenticity, data_scope, tuple(parsed_marks), tuple(parsed_questions), continuation, tuple(reasons), declared)


def blocks_contract_blind_pipelines(
    contract: MaterialContract | None, *, has_material_context: bool = False
) -> bool:
    """约束轮不得进入没有材料合同意识的执行面（引擎 B / 确定性 owner 管线）。

    这些管线按题型直接检索、读库或外呼，读不到 data_scope 也读不到待澄清状态；
    material_only、local_only 与材料语境下的待澄清合同一旦进入，P3 的读取收窄
    整体失效。adapter 让路判定与 orchestrator 掉落总闸共用本谓词——两处各自
    维护会改一漏一。

    分界：state_unavailable 声明的是「基底未知」而不是「受限边界」——任何裸
    「继续/接着」的日常追问都会编出它。只有带材料语境（题组、材料、可信历史）
    时才算禁区；普通续轮保持既有引擎 B 行为。boundary_uncertain（材料与指令
    粘连）本身就是材料语境，一律算。
    """

    if contract is None:
        return False
    if contract.data_scope in {"material_only", "local_only"}:
        return True
    if contract.classification == "boundary_uncertain":
        return True
    if contract.classification == "state_unavailable":
        return bool(has_material_context or contract.questions)
    return False


def compile_material_contract(
    regions: TopLevelRegions, *, source_turn: int = 0,
    inherited_contract: MaterialContract | None = None,
) -> MaterialContract | None:
    """解释D1可见指令；仅显式续轮继承调用方提供的可信用户指令基底。"""
    if not regions.instructions and not regions.sub_questions and regions.classification == "no_constraint_confirmed":
        return None
    if isinstance(source_turn, bool) or not isinstance(source_turn, int) or source_turn < 0:
        raise ValueError("source_turn must be a nonnegative integer")
    questions = tuple(MaterialQuestion(qid, text) for qid, text in zip(regions.question_ids, regions.sub_questions, strict=True))
    continuation = any(s.kind == "continuation" and s.scope == "message" for s in regions.instructions)
    if regions.classification == "boundary_uncertain":
        return MaterialContract("boundary_uncertain", None, None, questions=questions,
                                continuation_requested=continuation, uncertain_reasons=regions.uncertain_reasons)
    if continuation and (inherited_contract is None or inherited_contract.needs_clarification):
        return MaterialContract("state_unavailable", None, None, questions=questions,
                                continuation_requested=True, uncertain_reasons=("base_state_unavailable",))
    base = inherited_contract if continuation else None
    authenticity = base.authenticity if base else "real"
    data_scope = base.data_scope if base else "full"
    data_scope_declared = False
    # 题级标注带原轮次，不能因续轮又出现q1就改成当前轮次的前提。
    marks = list(base.premise_marks) if base else []
    for span in regions.instructions:
        # text保留完整原文供锚定；识别必须读D1掩码，引用里的虚构/放宽不能变权限。
        text = span.visible_text
        head = _state_head(text)
        if _FICTIONAL_SENT_RE.search(text) or _HYPOTHESIS_STRONG_RE.match(head):
            marks.append(PremiseMark("sha256:" + hashlib.sha256(span.text.encode()).hexdigest(), "fictional", source_turn, span.scope))
            if span.scope == "message":
                authenticity = "fictional"
        if span.scope != "message":
            continue
        if is_material_only_instruction(head):
            data_scope, data_scope_declared = "material_only", True
        elif head.startswith(_B_RELAX_PHRASES):
            data_scope, data_scope_declared = "full", True
        elif _is_local_only_head(head):
            data_scope_declared = True
            if data_scope == "full":
                data_scope = "local_only"
    return MaterialContract(regions.classification, authenticity, data_scope, _settled_marks(marks), questions,
                            continuation_requested=continuation, data_scope_declared=data_scope_declared)


def _settled_marks(marks: list[PremiseMark]) -> tuple[PremiseMark, ...]:
    """同值重申幂等：同一句、同作用域的前提只留最早那一次（D7.2 第④格）。

    `text_ref` 是原句哈希，所以重申会得到同 ref、同 scope、只差 source_turn 的第二条。
    按整条去重挡不住它——续一轮就多一条模型可见标注，且两条指向同一个前提。
    保留最早轮次与既有注释一致：题级标注带原轮次，不因续轮改写成当前轮。
    """
    settled: dict[tuple[str, str, str], PremiseMark] = {}
    for mark in marks:
        key = (mark.text_ref, mark.authenticity, mark.scope)
        kept = settled.get(key)
        if kept is None or mark.source_turn < kept.source_turn:
            settled[key] = mark
    return tuple(settled.values())
