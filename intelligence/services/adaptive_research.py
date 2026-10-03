"""Model-owned research perspectives; guidance and diagnostics, never authority."""

from __future__ import annotations

from collections.abc import Iterable
import json
import os

from intelligence.services.agent_research import AgentEvidence
from intelligence.services.episode_protocol import evidence_ordinal_table
from intelligence.services.research_plan import ResearchPlan, perspective_to_dict

ADAPTIVE_RESEARCH_ENV = "WORKBENCH_ADAPTIVE_RESEARCH"


def adaptive_research_enabled() -> bool:
    # Keep the candidate opt-in until paired live evidence supports deployment.
    return os.environ.get(ADAPTIVE_RESEARCH_ENV, "off").strip().lower() in {
        "1", "true", "on",
    }


def adaptive_research_instructions() -> str:
    return (
        "自主研究：按本题目标提出可能改变结论的研究视角，不套固定股票池、表或工具清单。"
        "简单事实题可直接取证；比较、筛选或推演题先在 PLAN 的可选 perspectives 中登记视角。"
        "每项字段为 perspective_id（稳定标识）、question（研究问题）、"
        "status（open|supported|contested|blocked|not_relevant）、"
        "supporting_evidence（E序号数组）、contradicting_evidence（E序号数组）、"
        "assessment（当前判断、缺口或不适用理由）、next_check（什么信息可能改变判断）。"
        "最多8个视角，不要求凑数；每个证据数组最多8个编号，可空；supported 必须有支持证据，"
        "contested 必须有反证，blocked/not_relevant 必须说明理由。"
        "每批观察回来后判断：哪些假设改变了，哪些重要方向尚未考虑，"
        "哪项未决信息最可能改变结论；新证据条数不等于视角覆盖质量。"
        "需要补查时可在同一响应正文提交递增 revision 的完整 PLAN 并同时调用工具，"
        "避免额外计划往返；提供 base_revision（首次为0，其后为已接受的 revision），"
        "可撤回自拟的 answer_elements、branch_goals 和 perspectives，撤回时给出 revision_reason。"
        "不采用 base_revision 的旧式计划仍须逐字保留原项；"
        "具体基线和旧式保留项见 plan_revision_constraints。"
        "自拟研究意图不是用户义务；修订不能删除原题或合同必需输出，也不授予工具权限或改变预算。"
        "收口前检查候选范围是否过早收窄、是否有反证、入选与落选理由是否一致。"
        "未知不能写成负面事实，未核验不能写成已排除；重要缺口及其影响须进入 draft 和 gaps。"
        "名单变更后同步正文所有相关结论。预算关闭后直接 FINAL_JSON，不再提交 PLAN；"
        "只靠观点不能补足证据，不能为了填完视角而耗尽预算。"
    )


def needs_perspective_checkpoint(plan: ResearchPlan | None, *, research_tier: str) -> bool:
    return (
        adaptive_research_enabled()
        and research_tier in {"deep", "max"}
        and (plan is None or not plan.perspectives)
    )


def _plan_revision_constraints(plan: ResearchPlan | None) -> dict[str, object] | None:
    if plan is None:
        return None
    if plan.base_revision is not None:
        return {
            "minimum_revision": plan.revision + 1,
            "base_revision": plan.revision,
            "retraction_requires_revision_reason": True,
        }
    return {
        "minimum_revision": plan.revision + 1,
        "preserve_answer_elements": list(plan.answer_elements),
        "preserve_branch_goals": list(plan.branch_goals),
        "preserve_perspective_ids": [item.perspective_id for item in plan.perspectives],
    }


def perspective_checkpoint_message(plan: ResearchPlan | None = None) -> str:
    instruction = (
        "首批取证后的研究复核：这一次不提供工具。"
        "若本题是单一事实且已有证据足够回答，直接 FINAL_JSON，不必提交 PLAN 或凑视角。"
        "否则输出一个完整 kind=PLAN JSON，字段为 task_summary、answer_elements、"
        "hypotheses、evidence_needs、candidate_actions、open_gaps、requested_mode、revision，"
        "以及 perspectives，可带 branch_goals。"
        "revision 严格递增；提供 base_revision（首次为0，其后为已接受的 revision），"
        "撤回自拟项须给出 revision_reason。已采用基线后不能省略；"
        "旧式无基线修订仍须逐字保留原项，具体见 plan_revision_constraints。"
        "修订仅改变研究意图，不删除原题或合同必需输出，不授予任何新权限或完成资格。"
        "自行判断本题有哪些可能改变结论的视角，哪些已得到证据、哪些仍未知或有反证，"
        "尤其检查第一批资料是否让研究范围过早收窄；不要求固定视角或固定股票池。"
        "每项使用 perspective_id、question、status、supporting_evidence、"
        "contradicting_evidence、assessment、next_check；最多8个视角，每个证据数组最多8项，"
        "仅引用已经看见的 E 序号。空 perspectives 的理由可写在 task_summary 或 open_gaps，"
        "不要新增协议之外的说明字段。"
        "这次复核仍消耗原时间预算，不增加工具额度；复核后按剩余预算继续研究或交付。"
    )
    return json.dumps({
        "instruction": instruction,
        "plan_revision_constraints": _plan_revision_constraints(plan),
    }, ensure_ascii=False)


def perspective_diagnostics(
    plan: ResearchPlan | None,
    *,
    evidence: Iterable[AgentEvidence],
) -> tuple[str, ...]:
    """Check references at submission time, not against future tool results."""
    known = set(evidence_ordinal_table(tuple(evidence)).values())
    if plan is None:
        return ()
    return tuple(sorted({
        reference
        for item in plan.perspectives
        for reference in (*item.supporting_evidence, *item.contradicting_evidence)
        if reference not in known
    }))


def perspective_progress(
    plan: ResearchPlan | None,
    *,
    batch: int,
    plan_batch: int,
    unknown_evidence_ids: tuple[str, ...],
) -> dict[str, object]:
    """Expose model claims separately from host-observed bookkeeping."""
    perspectives = plan.perspectives if plan is not None else ()
    return {
        "plan_revision": plan.revision if plan is not None else None,
        "plan_revision_constraints": _plan_revision_constraints(plan),
        "plan_recorded_after_batch": plan_batch if plan is not None else None,
        "batches_since_plan": max(0, batch - plan_batch),
        "model_reported_perspectives": [perspective_to_dict(item) for item in perspectives],
        "unknown_evidence_ids_at_submission": list(unknown_evidence_ids),
        "unresolved_perspective_ids": [
            item.perspective_id for item in perspectives
            if item.status in {"open", "contested", "blocked"}
        ],
        "instruction": (
            "这是模型自报的研究状态，不是覆盖率评分或事实核验结论。"
            "尚无视角时自行判断本题是否需要多视角研究；已有视角时根据本批新观察修订判断。"
            "检查是否遗漏可能改变结论的方向或反证，自主决定补查、改方向或结束。"
            "unknown_evidence_ids_at_submission 在提交时不存在，不能为判断背书；"
            "即使编号存在也不证明它支持该视角。"
            "需要修订时按 plan_revision_constraints 提供已接受的 base_revision；"
            "撤回自拟项时给出 revision_reason。旧式无基线修订仍须逐字保留原项；"
            "计划不能撤销用户原题或合同必需输出。"
            "用完整 PLAN 与下一批工具调用同轮提交，不增加纯计划轮；"
            "无需补查时直接 FINAL_JSON，把关键未决问题及其影响写入 draft 和 gaps。"
            "预算关闭时不得继续 PLAN 或工具调用。"
        ),
    }
