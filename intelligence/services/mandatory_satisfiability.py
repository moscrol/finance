"""必需项可满足性：静态 KB 供给预检 + 动态不可达降级。

形状 B（见 ``docs/superpowers/specs/2026-08-21-ceiling-shape-closeout-design.md`` W2）：
mandatory 清单设计时写死，证据供给/预算运行时动态。联立无解时不要逼模型
在「违禁编造」和「缺格被删」之间选，改成结构化缺口声明。

两级对账，都不猜「工具会不会返回有用数据」：

- 静态：contract 下发时查 relations 有没有该题材的公司暴露。查不到 →
  ``chain_mapping`` 降 optional 并预置缺口。relations 不在场 → 不定，保持
  mandatory（fail closed，避免新误判层）。
- 动态：``unreachable_repair_goal`` 非空且 ``reopen_tools=False`` → 那些
  evidence 必填格 + 全部 mandatory capability 降级。不跳过修复轮（salvage
  刚写出的 FINAL_JSON 仍要跑；2026-08-21 已回退过「整轮 skip」）。

本模块只做裁决。观测字段 ``unreachable_without_tools`` 仍由
``agent_episode.resume`` 投进 trace。
"""

from __future__ import annotations

from dataclasses import replace

from intelligence.adapters.knowledge import KnowledgeAdapter
from intelligence.services.repair_coordinator import RepairGoal, unreachable_repair_goal
from intelligence.services.research_contract import (
    RequiredOutput,
    ResearchTaskContract,
)

CHAIN_MAPPING_OUTPUT_ID = "chain_mapping"
CHAIN_MAPPING_KB_GAP = "知识库暂无该题材产业链证据"
UNREACHABLE_MANDATORY_GAP = "当前无法补取该必填项的证据，记为结构缺口"
_GAP_HEADING = "【结构缺口】"


def theme_chain_evidence_present(
    theme: str,
    *,
    knowledge: KnowledgeAdapter | None = None,
) -> bool | None:
    """机械查 KB 是否有该题材的公司链路暴露。

    ``True``：至少一家公司暴露。
    ``False``：relations 在场且查询为空。
    ``None``：无法机械判定（无题材名 / 文件不在场 / 读失败）→ 保持 mandatory。
    """

    subject = str(theme or "").strip()
    if not subject:
        return None
    adapter = knowledge if knowledge is not None else KnowledgeAdapter()
    relation = adapter.load_relation("entity_exposures")
    if not relation.get("found"):
        return None
    matches = adapter.get_exposure_matches(subject, limit=1)
    items = matches.get("items") or []
    return any(str(row.get("company") or "").strip() for row in items)


def apply_static_chain_mapping_precheck(
    contract: ResearchTaskContract,
    *,
    knowledge: KnowledgeAdapter | None = None,
) -> ResearchTaskContract:
    """无链路证据时把 ``chain_mapping`` 降 optional 并预置缺口。"""

    if not any(
        item.output_id == CHAIN_MAPPING_OUTPUT_ID for item in contract.required_outputs
    ):
        return contract
    present = theme_chain_evidence_present(
        str(contract.subject or ""),
        knowledge=knowledge,
    )
    if present is not False:
        return contract
    return replace(
        contract,
        required_outputs=tuple(
            replace(item, required=False, preplaced_gap=CHAIN_MAPPING_KB_GAP)
            if item.output_id == CHAIN_MAPPING_OUTPUT_ID and item.required
            else item
            for item in contract.required_outputs
        ),
    )


def evidence_required_output_ids(contract: ResearchTaskContract) -> frozenset[str]:
    return frozenset(
        item.output_id
        for item in contract.required_outputs
        if item.required and item.grounding_mode == "evidence"
    )


def repair_goal_for_model(
    goal: RepairGoal,
    unreachable: tuple[str, ...],
) -> RepairGoal:
    """模型侧修复指令去掉不可达必填格，避免被压着调错口径替代工具。"""

    blocked = frozenset(unreachable)
    if not blocked:
        return goal
    return replace(
        goal,
        missing_answer_elements=tuple(
            item for item in goal.missing_answer_elements if item not in blocked
        ),
        missing_evidence_modes=(),
    )


def apply_unreachable_downgrade(
    contract: ResearchTaskContract,
    goal: RepairGoal,
) -> tuple[ResearchTaskContract, RepairGoal]:
    """``unreachable && !reopen`` 时降级 contract，并返回模型侧 goal。

    观测用的原始 goal 由调用方继续投递；这里只改裁决后的契约与指令。
    """

    unreachable = unreachable_repair_goal(
        goal,
        evidence_output_ids=evidence_required_output_ids(contract),
    )
    if not unreachable or goal.reopen_tools:
        return contract, goal
    blocked = frozenset(unreachable)
    new_outputs = tuple(
        _downgrade_output(item) if item.output_id in blocked else item
        for item in contract.required_outputs
    )
    new_plan = replace(
        contract.evidence_plan,
        requirements=tuple(
            replace(requirement, mandatory=False)
            for requirement in contract.evidence_plan.requirements
        ),
    )
    downgraded = replace(
        contract,
        required_outputs=new_outputs,
        evidence_plan=new_plan,
    )
    return downgraded, repair_goal_for_model(goal, unreachable)


def ensure_preplaced_gap_sections(
    draft: str,
    contract: ResearchTaskContract,
    *,
    only_output_ids: frozenset[str] | set[str] | None = None,
) -> str:
    """预置缺口声明的收据拼装。生产公开稿不得再调用本函数。

    未兑现槽若要出现在用户可见正文，必须作为 ``TerminalFacts.unknown_slots``
    由 ``session_projection.view`` 渲成用户语言。``only_output_ids`` 仍供
    单测核对接缝；adapter 出口缝合已拆除。
    """

    text = str(draft or "")
    extras: list[str] = []
    for item in contract.required_outputs:
        if only_output_ids is not None and item.output_id not in only_output_ids:
            continue
        gap = str(getattr(item, "preplaced_gap", "") or "").strip()
        if not gap or gap in text:
            continue
        label = item.description.strip() or item.output_id
        extras.append(f"{_GAP_HEADING}{label}：{gap}")
    if not extras:
        return text
    suffix = "\n".join(extras)
    if not text.strip():
        return suffix
    return text.rstrip() + "\n\n" + suffix


def _downgrade_output(item: RequiredOutput) -> RequiredOutput:
    return replace(
        item,
        required=False,
        preplaced_gap=item.preplaced_gap or UNREACHABLE_MANDATORY_GAP,
    )


__all__ = [
    "CHAIN_MAPPING_KB_GAP",
    "CHAIN_MAPPING_OUTPUT_ID",
    "UNREACHABLE_MANDATORY_GAP",
    "apply_static_chain_mapping_precheck",
    "apply_unreachable_downgrade",
    "ensure_preplaced_gap_sections",
    "evidence_required_output_ids",
    "repair_goal_for_model",
    "theme_chain_evidence_present",
]
