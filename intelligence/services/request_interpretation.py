"""A request content anchor is not an authorization or a semantic proof.

This slice versions only the model's goal interpretation. It deliberately does
not rebuild the TaskFrame, execution contract, evidence ledger or root budget.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import hashlib
import json
import re
from typing import TYPE_CHECKING

from intelligence.services.material_contract import MaterialContract
from intelligence.services.output_requirement import RequiredOutput

if TYPE_CHECKING:
    from intelligence.services.research_contract import ResearchRunContext, ResearchTaskContract
    from intelligence.services.research_plan import ResearchPlan


def _validate(request_ref: str, revision: int, goal: str, reason: str, *, minimum: int) -> None:
    if not isinstance(request_ref, str) or re.fullmatch(r"request:[0-9a-f]{64}", request_ref) is None:
        raise ValueError("interpretation request_ref must be a root request content reference")
    if type(revision) is not int or revision < minimum:
        raise ValueError("interpretation revision must be a non-negative integer")
    for name, value, maximum in (("goal", goal, 500), ("reason", reason, 300)):
        if not isinstance(value, str) or not value.strip() or len(value) > maximum:
            raise ValueError(f"interpretation {name} must contain 1-{maximum} characters")


@dataclass(frozen=True)
class InterpretationProposal:
    request_ref: str
    base_revision: int
    goal: str
    reason: str

    def __post_init__(self) -> None:
        _validate(self.request_ref, self.base_revision, self.goal, self.reason, minimum=0)

    @classmethod
    def from_dict(cls, value: object) -> InterpretationProposal:
        if not isinstance(value, dict) or set(value) != {"request_ref", "base_revision", "goal", "reason"}:
            raise ValueError("interpretation proposal fields are incomplete or unknown")
        return cls(**value)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class TaskInterpretation:
    request_ref: str
    revision: int
    goal: str
    reason: str

    def __post_init__(self) -> None:
        _validate(self.request_ref, self.revision, self.goal, self.reason, minimum=1)

    @classmethod
    def from_dict(cls, value: object) -> TaskInterpretation:
        if not isinstance(value, dict) or set(value) != {"request_ref", "revision", "goal", "reason"}:
            raise ValueError("accepted interpretation fields are incomplete or unknown")
        return cls(**value)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _canonical(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


@dataclass(frozen=True)
class RootRequest:
    """Captured once at context creation, not rebuilt from a repair contract.

    Content identity only: entry identity, current authorization and the episode
    writer still own authentication/authority. This is not a semantic proof.
    """
    raw_question: str
    task_frame_hash: str
    required_outputs: tuple[RequiredOutput, ...]
    material_contract: MaterialContract | None = None

    @classmethod
    def from_contract(cls, contract: ResearchTaskContract) -> RootRequest:
        return cls(contract.question, contract.task_frame_hash, contract.required_outputs, contract.material_contract)

    def to_dict(self) -> dict[str, object]:
        payload = {
            "raw_question": self.raw_question,
            "task_frame_hash": self.task_frame_hash,
            "required_outputs": [item.to_dict() for item in self.required_outputs],
            **({"material_contract": self.material_contract.to_dict()} if self.material_contract is not None else {}),
        }
        return {"request_ref": "request:" + hashlib.sha256(_canonical(payload).encode()).hexdigest(), **payload}

    @classmethod
    def from_dict(cls, value: object) -> RootRequest:
        fields = {"request_ref", "raw_question", "task_frame_hash", "required_outputs"}
        if not isinstance(value, dict) or set(value) not in (fields, fields | {"material_contract"}):
            raise ValueError("root request fields are incomplete or unknown")
        if any(not isinstance(value[key], str) for key in ("raw_question", "task_frame_hash")):
            raise ValueError("root request question/hash must be strings")
        if not isinstance(value["required_outputs"], (list, tuple)):
            raise ValueError("root request outputs must be a list")
        root = cls(
            value["raw_question"], value["task_frame_hash"],
            tuple(RequiredOutput.from_dict(row) for row in value["required_outputs"]),
            MaterialContract.from_dict(value["material_contract"]) if "material_contract" in value else None,
        )
        if _canonical(root.to_dict()) != _canonical(value):
            raise ValueError("root request content/reference is noncanonical")
        return root


def root_request_payload(contract: ResearchTaskContract) -> dict[str, object]:
    """Project an initial trusted contract; live runs use their frozen root."""
    return RootRequest.from_contract(contract).to_dict()


def interpretation_payload(context: ResearchRunContext, *, initial_goal: str = "") -> dict[str, object]:
    assert context.root_request is not None
    root = context.root_request.to_dict()
    current = context.interpretation
    if current is not None and current.request_ref != root["request_ref"]:
        raise ValueError("accepted interpretation request_ref does not match current root request")
    return {
        "root_request": root,
        "interpretation": current.to_dict() if current is not None else {
            "request_ref": root["request_ref"], "revision": 0,
            "goal": initial_goal or context.contract.question, "reason": "initial_interpretation",
        },
        "interpretation_rule": (
            "root_request 是不可覆盖的原请求与输出清单；interpretation 只是当前目标解释，不是事实或授权。"
            "可在 PLAN.interpretation 提交 request_ref、base_revision、goal、reason；基线必须等于当前解释 revision。"
            "解释版本与 PLAN revision 独立。未携带 interpretation 时保留当前解释；原 TaskFrame 只是初始解释。"
            "本接口不修改题型、主体、时间窗、输出、读取权限或预算；这些字段不得放入提案。"
            "解释提案不得与工具调用同包；先单独提交，收到接纳回执后再调用工具。"
            "必须仍回答完整原题、保留用户义务；旧证据原件保留，但不能仅因修订而声称支持新结论。"
        ),
    }


def accept_interpretation(plan: ResearchPlan, *, context: ResearchRunContext) -> ResearchRunContext:
    proposal = plan.interpretation
    if proposal is None:
        return context
    assert context.root_request is not None
    root = context.root_request.to_dict()
    current = context.interpretation
    if proposal.request_ref != root["request_ref"] or (current is not None and current.request_ref != proposal.request_ref):
        raise ValueError("interpretation request_ref does not match current root request")
    revision = current.revision if current is not None else 0
    if proposal.base_revision != revision:
        raise ValueError(f"stale interpretation: base_revision must match {revision}")
    return replace(context, interpretation=TaskInterpretation(
        proposal.request_ref, revision + 1, proposal.goal, proposal.reason,
    ))
