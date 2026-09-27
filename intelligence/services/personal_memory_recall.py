"""Personal recall intent and its closed, non-market delivery contract."""
from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from intelligence.services.agent_research import AgentEvidence
    from intelligence.services.agent_runtime import AgentOutcome
    from intelligence.services.research_contract import ResearchTaskContract

QUESTION_TYPE = "personal_memory_recall"

# Moved unchanged from episode_factory: a candidate for semantic arbitration,
# never sufficient on its own to replace a financial research contract.
_PRIOR_REFERENCE_RE = re.compile(
    r"(?:我(?:之前|此前|过去|原来|先前|上次|当初)"
    r"|之前(?:我|的)(?:判断|看法|观点|结论)"
    r"|我(?:的)?(?:判断|看法|观点|逻辑)(?:还|是否|对不对|成立)"
    r"|跟我(?:上次|之前)"
    r"|(?:还|是否)(?:成立|站得住|有效))"
)


def references_personal_prior(query: str) -> bool:
    return bool(_PRIOR_REFERENCE_RE.search(query))


def is_personal_recall_contract(contract: ResearchTaskContract | None) -> bool:
    if contract is None or contract.question_type != QUESTION_TYPE:
        return False
    outputs = contract.required_outputs
    return bool(
        len(outputs) == 1
        and outputs[0].output_id == "prior_recall"
        and outputs[0].required
        and outputs[0].grounding_mode == "user_premise"
        and outputs[0].evidence_types == ("memory_lookup",)
        and contract.allowed_capabilities == ("memory_lookup",)
    )


_GAP_NOTICES = {
    "empty": "本次在你的可用个人记录中未找到相关内容，暂时无法回顾你此前的判断或纠偏。这不代表你从未表达过。",
    "future_of_cutoff": "相关个人记录晚于本次信息截止日，未纳入本次回顾；这不代表没有记录。",
    "outside_window": "相关个人记录在本次允许的历史范围之外，未纳入本次回顾；这不代表没有记录。",
    "date_unavailable": "相关个人记录的日期无法核验，暂时不能纳入本次回顾；这不代表没有记录。",
    "timeout": "本次读取个人记录超时，尚未确认是否有相关内容，暂时无法回顾。",
    "unavailable": "本次未能读取个人记录，尚未确认是否有相关内容，暂时无法回顾。",
    "busy": "本次个人记录读取繁忙，尚未完成读取，暂时无法回顾。",
}


def memory_gap_public_notice(
    contract: ResearchTaskContract | None, evidence: tuple[AgentEvidence, ...],
) -> str:
    """Render only a collected recall state, never a model's absence claim."""
    from intelligence.services.agent_research import evidence_content_hash

    if not is_personal_recall_contract(contract) or not evidence:
        return ""
    notices = []
    for item in evidence:
        if (
            item.tool != "memory_lookup" or item.evidence_tier != "user_memory_gap"
            or item.io_effect != "local_read" or item.content_hash != evidence_content_hash(item)
        ):
            return ""
        status = item.detail.partition(" ")[0].removeprefix("status=")
        notice = _GAP_NOTICES.get(status)
        if not notice:
            return ""
        if notice not in notices:
            notices.append(notice)
    return "\n\n".join(notices)


def is_recall_gap_delivery(contract: ResearchTaskContract | None, outcome: AgentOutcome) -> bool:
    """A legal partial is exactly the collected state, with no claimed prior."""
    notice = memory_gap_public_notice(contract, outcome.evidence)
    bindings = outcome.bindings
    return bool(
        notice and outcome.draft == notice and len(bindings) == 1
        and bindings[0].output_id == "prior_recall" and bindings[0].basis == "user_premise"
        and not bindings[0].evidence_hashes and not bindings[0].claims
        and bindings[0].gap == notice
    )
