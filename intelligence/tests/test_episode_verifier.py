from __future__ import annotations

import pytest

from intelligence.services.agent_research import AgentEvidence
from intelligence.services.agent_runtime import (
    AgentOutcome,
    AgentUsage,
    EpisodeEvent,
    OutputEvidenceBinding,
)
from intelligence.services.episode_issues import IssueCode
from intelligence.services.episode_verifier import verify_episode_outcome
from intelligence.services.evidence_capabilities import (
    EvidencePlan,
    EvidenceRequirement,
)
from intelligence.services.research_contract import RequiredOutput, ResearchTaskContract


TASK_HASH = "task-frame-hash"


def _contract(
    *,
    outputs: tuple[RequiredOutput, ...] | None = None,
    evidence_plan: EvidencePlan | None = None,
    allowed_capabilities: tuple[str, ...] = (
        "market_data",
        "news_search",
        "mainline_context",
    ),
) -> ResearchTaskContract:
    return ResearchTaskContract(
        task_id="episode-test",
        question="市场怎么看",
        subject="A股市场",
        subject_kind="market_pattern",
        question_type="market_forecast",
        required_outputs=outputs
        or (
            RequiredOutput(
                "direct_assessment",
                "直接判断",
                ("market_data", "news_search"),
            ),
            RequiredOutput(
                "evidence_boundary",
                "证据边界",
                ("market_data", "news_search"),
            ),
        ),
        allowed_capabilities=allowed_capabilities,
        evidence_plan=evidence_plan or EvidencePlan(),
        task_frame_hash=TASK_HASH,
    )


def _evidence(tool: str, content_hash: str) -> AgentEvidence:
    return AgentEvidence(
        tool=tool,
        title=f"{tool} evidence",
        detail="可核验事实",
        source="test-source",
        content_hash=content_hash,
    )


def _outcome(
    *,
    status: str = "completed",
    draft: str = "基于证据，当前只能做条件化判断。",
    evidence: tuple[AgentEvidence, ...] = (),
    bindings: tuple[OutputEvidenceBinding, ...] = (),
    task_hash: str = TASK_HASH,
) -> AgentOutcome:
    return AgentOutcome(
        task_frame_hash=task_hash,
        status=status,  # type: ignore[arg-type]
        draft=draft,
        evidence=evidence,
        traces=(),
        gaps=(),
        stop_reason="model_finish",
        events=(
            EpisodeEvent(
                1,
                "task",
                {"task_frame_hash": task_hash, "question": "市场怎么看"},
            ),
        ),
        bindings=bindings,
        usage=AgentUsage(llm_calls=2, tool_calls=1),
    )


def test_valid_evidence_bindings_complete_the_episode() -> None:
    market = _evidence("market_data", "market-1")
    outcome = _outcome(
        evidence=(market,),
        bindings=(
            OutputEvidenceBinding("direct_assessment", ("market-1",)),
            OutputEvidenceBinding("evidence_boundary", ("market-1",)),
        ),
    )

    verified = verify_episode_outcome(_contract(), outcome)

    assert verified.verified_status == "completed"
    assert verified.completion.business_status == "complete"
    assert {item.status for item in verified.completion.outputs} == {"fulfilled"}
    assert verified.issues == ()


@pytest.mark.parametrize("grounding_mode", ("model_reasoning", "user_premise"))
def test_non_evidence_grounding_can_complete_without_fake_hashes(
    grounding_mode: str,
) -> None:
    contract = _contract(
        outputs=(
            RequiredOutput(
                "direct_assessment",
                "直接判断",
                (),
                grounding_mode=grounding_mode,
            ),
        ),
        allowed_capabilities=(),
    )
    outcome = _outcome(
        draft="如果用户给出的承接下降前提成立，则该板块不能按主线确认。",
        bindings=(
            OutputEvidenceBinding(
                "direct_assessment",
                (),
                basis=grounding_mode,
            ),
        ),
    )

    verified = verify_episode_outcome(contract, outcome)

    assert verified.verified_status == "completed"
    assert verified.completion.outputs[0].status == "fulfilled"
    assert verified.issues == ()


def test_evidence_output_cannot_be_laundered_as_model_reasoning() -> None:
    outcome = _outcome(
        draft="当前市场已经转强。",
        bindings=(
            OutputEvidenceBinding(
                "direct_assessment",
                (),
                basis="model_reasoning",
            ),
            OutputEvidenceBinding(
                "evidence_boundary",
                (),
                basis="model_reasoning",
            ),
        ),
    )

    verified = verify_episode_outcome(_contract(), outcome)

    assert verified.verified_status == "partial"
    assert any("grounding basis" in issue for issue in verified.issues)


def test_shared_hash_is_structural_only_and_does_not_overload_supports() -> None:
    market = _evidence("market_data", "market-1")
    outcome = _outcome(
        evidence=(market,),
        bindings=(
            OutputEvidenceBinding("direct_assessment", ("market-1",)),
            OutputEvidenceBinding("evidence_boundary", ("market-1",)),
        ),
    )

    verified = verify_episode_outcome(_contract(), outcome)

    assert verified.verified_status == "completed"
    assert all(item.status == "fulfilled" for item in verified.completion.outputs)


def test_missing_required_output_downgrades_completed_outcome() -> None:
    market = _evidence("market_data", "market-1")
    outcome = _outcome(
        evidence=(market,),
        bindings=(OutputEvidenceBinding("direct_assessment", ("market-1",)),),
    )

    verified = verify_episode_outcome(_contract(), outcome)

    assert verified.verified_status == "partial"
    assert verified.completion.missing_required[0].output_id == "evidence_boundary"


def test_unknown_evidence_hash_fails_closed() -> None:
    market = _evidence("market_data", "market-1")
    outcome = _outcome(
        evidence=(market,),
        bindings=(
            OutputEvidenceBinding("direct_assessment", ("unknown",)),
            OutputEvidenceBinding("evidence_boundary", ("market-1",)),
        ),
    )

    verified = verify_episode_outcome(_contract(), outcome)

    assert verified.verified_status == "partial"
    assert any("unknown evidence hash" in issue for issue in verified.issues)


def test_wrong_tool_type_cannot_launder_a_required_output() -> None:
    web = _evidence("web_search", "web-1")
    outcome = _outcome(
        evidence=(web,),
        bindings=(
            OutputEvidenceBinding("direct_assessment", ("web-1",)),
            OutputEvidenceBinding("evidence_boundary", ("web-1",)),
        ),
    )

    verified = verify_episode_outcome(_contract(), outcome)

    assert verified.verified_status == "partial"
    assert any("evidence type" in issue for issue in verified.issues)


def test_mixed_binding_strips_illegal_type_and_keeps_legal_hashes() -> None:
    """SPT 复现（run_20260819_130854）：prime 槽混绑合法行情 + 越界 finance_query。

    剔除式判据：非法哈希被剔出槽位，合法行情哈希保住、槽位照常履行，
    整篇不再因一条越界引用降级。剔除动作以 stripped 前缀留痕。
    """

    contract = _contract(
        outputs=(
            RequiredOutput(
                "direct_assessment",
                "直接判断",
                ("market_data", "finance_query"),
            ),
            RequiredOutput("prime_quote", "最新行情要点", ("market_data",)),
        ),
        allowed_capabilities=("market_data", "finance_query"),
    )
    market = _evidence("market_data", "market-1")
    overview = _evidence("finance_query", "finance-1")
    outcome = _outcome(
        evidence=(market, overview),
        bindings=(
            OutputEvidenceBinding("direct_assessment", ("market-1", "finance-1")),
            OutputEvidenceBinding("prime_quote", ("market-1", "finance-1")),
        ),
    )

    verified = verify_episode_outcome(contract, outcome)

    assert verified.verified_status == "completed"
    by_id = {item.output_id: item for item in verified.completion.outputs}
    assert by_id["prime_quote"].status == "fulfilled"
    assert by_id["prime_quote"].evidence_ids == ("market-1",)
    assert by_id["direct_assessment"].evidence_ids == ("market-1", "finance-1")
    assert [item.code for item in verified.issue_items] == [
        IssueCode.EVIDENCE_TYPE_STRIPPED,
    ]
    assert verified.issue_items[0].subject == "prime_quote"
    assert "finance_query" in verified.issue_items[0].message
    assert verified.missing_outputs == ()


def test_financial_anchor_strip_keeps_real_financial_floor() -> None:
    """混绑时财务锚照常成立：剔掉多绑的行情，真财务哈希满足地板。"""

    contract = _contract(
        outputs=(
            RequiredOutput(
                "valuation_assessment",
                "估值判断",
                ("market_data", "financial_data"),
            ),
            RequiredOutput(
                "financial_business_anchor",
                "财务或业务硬数据锚点",
                ("financial_data", "kb_search"),
            ),
        ),
        allowed_capabilities=("market_data", "financial_data", "kb_search"),
    )
    market = _evidence("market_data", "market-1")
    financial = _evidence("financial_data", "financial-1")
    outcome = _outcome(
        draft="当前PB为4.33倍，Q2营收环比+18%。",
        evidence=(market, financial),
        bindings=(
            OutputEvidenceBinding("valuation_assessment", ("market-1",)),
            OutputEvidenceBinding(
                "financial_business_anchor",
                ("financial-1", "market-1"),
            ),
        ),
    )

    verified = verify_episode_outcome(contract, outcome)

    assert verified.verified_status == "completed"
    anchor = verified.completion.outputs[1]
    assert anchor.status == "fulfilled"
    assert anchor.evidence_ids == ("financial-1",)
    assert [item.code for item in verified.issue_items] == [
        IssueCode.EVIDENCE_TYPE_STRIPPED,
    ]
    assert verified.issue_items[0].subject == "financial_business_anchor"
    assert "market_data" in verified.issue_items[0].message


def test_stripped_evidence_cannot_satisfy_mandatory_capability() -> None:
    """被剔除的越界哈希不得反过来给强制能力记账。"""

    contract = _contract(
        outputs=(
            RequiredOutput(
                "direct_assessment",
                "直接判断",
                ("market_data",),
            ),
        ),
        evidence_plan=EvidencePlan(
            "current_mainline",
            (
                EvidenceRequirement("MARKET_DAILY", "market_data", True),
                EvidenceRequirement("D4", "mainline_context", True),
            ),
        ),
        allowed_capabilities=("market_data", "mainline_context"),
    )
    market = _evidence("market_data", "market-1")
    mainline = _evidence("mainline_context", "mainline-1")
    outcome = _outcome(
        evidence=(market, mainline),
        bindings=(
            OutputEvidenceBinding(
                "direct_assessment",
                ("market-1", "mainline-1"),
            ),
        ),
    )

    verified = verify_episode_outcome(contract, outcome)

    assert verified.verified_status == "partial"
    codes = {item.code for item in verified.issue_items}
    assert IssueCode.EVIDENCE_TYPE_STRIPPED in codes
    assert IssueCode.MISSING_MANDATORY_CAPABILITY in codes
    assert any(
        item.subject == "direct_assessment" and "mainline_context" in item.message
        for item in verified.issue_items
        if item.code == IssueCode.EVIDENCE_TYPE_STRIPPED
    )
    assert any(
        "mainline_context" in item.subject
        for item in verified.issue_items
        if item.code == IssueCode.MISSING_MANDATORY_CAPABILITY
    )


def test_unbound_unstripped_prefetch_satisfies_mandatory_capability() -> None:
    """桌上已有、未绑定也未被 strip 的预取，不得再报 missing_mandatory。"""

    contract = _contract(
        outputs=(
            RequiredOutput(
                "direct_assessment",
                "直接判断",
                ("market_data",),
            ),
        ),
        evidence_plan=EvidencePlan(
            "current_mainline",
            (
                EvidenceRequirement("MARKET_DAILY", "market_data", True),
                EvidenceRequirement("D4", "mainline_context", True),
            ),
        ),
        allowed_capabilities=("market_data", "mainline_context"),
    )
    market = _evidence("market_data", "prefetch-market-1")
    outcome = _outcome(
        status="partial",
        evidence=(market,),
        bindings=(
            OutputEvidenceBinding(
                "direct_assessment",
                (),
                "预取未写入 binding",
            ),
        ),
    )

    verified = verify_episode_outcome(contract, outcome)

    missing = [
        item
        for item in verified.issue_items
        if item.code == IssueCode.MISSING_MANDATORY_CAPABILITY
    ]
    assert missing
    assert all("market_data" not in item.subject for item in missing)
    assert any("mainline_context" in item.subject for item in missing)


def test_explicit_gap_is_partial_not_fake_completed() -> None:
    outcome = _outcome(
        status="partial",
        draft="目前无法确认。",
        bindings=(
            OutputEvidenceBinding(
                "direct_assessment",
                (),
                "仍缺同日市场数据",
            ),
            OutputEvidenceBinding(
                "evidence_boundary",
                (),
                "仍缺同日市场数据",
            ),
        ),
    )

    verified = verify_episode_outcome(_contract(), outcome)

    assert verified.verified_status == "partial"
    assert all(item.status == "missing" for item in verified.completion.outputs)


def test_leftover_binding_gap_still_drops_hashes() -> None:
    """绕过 protocol normalize 时，verifier 仍把非空 gap 当 missing（判据不变）。"""

    market = _evidence("market_data", "market-1")
    outcome = _outcome(
        status="partial",
        evidence=(market,),
        bindings=(
            OutputEvidenceBinding("direct_assessment", ("market-1",), "附带限制"),
            OutputEvidenceBinding("evidence_boundary", ("market-1",), "附带限制"),
        ),
    )

    verified = verify_episode_outcome(_contract(), outcome)

    assert {item.status for item in verified.completion.outputs} == {"missing"}
    assert all(not item.evidence_ids for item in verified.completion.outputs)
    assert any("required output reports gap:" in issue for issue in verified.issues)


def test_fulfilled_bindings_do_not_upgrade_declared_partial_status() -> None:
    market = _evidence("market_data", "market-1")
    outcome = _outcome(
        status="partial",
        evidence=(market,),
        bindings=(
            OutputEvidenceBinding("direct_assessment", ("market-1",)),
            OutputEvidenceBinding("evidence_boundary", ("market-1",)),
        ),
    )

    verified = verify_episode_outcome(_contract(), outcome)

    assert verified.verified_status == "partial"
    assert verified.completion.business_status == "partial"
    assert {item.status for item in verified.completion.outputs} == {"fulfilled"}


def test_missing_mandatory_evidence_capability_downgrades_completion() -> None:
    contract = _contract(
        outputs=(
            RequiredOutput(
                "direct_assessment",
                "直接判断",
                ("market_data", "mainline_context"),
            ),
        ),
        evidence_plan=EvidencePlan(
            "current_mainline",
            (
                EvidenceRequirement("MARKET_DAILY", "market_data", True),
                EvidenceRequirement("D4", "mainline_context", True),
            ),
        ),
    )
    market = _evidence("market_data", "market-1")
    outcome = _outcome(
        evidence=(market,),
        bindings=(OutputEvidenceBinding("direct_assessment", ("market-1",)),),
    )

    verified = verify_episode_outcome(contract, outcome)

    assert verified.verified_status == "partial"
    assert any("mandatory capability" in issue for issue in verified.issues)


def test_market_snapshot_cannot_launder_a_valuation_financial_anchor() -> None:
    contract = _contract(
        outputs=(
            RequiredOutput(
                "valuation_assessment",
                "估值判断",
                ("market_data",),
            ),
            RequiredOutput(
                "financial_business_anchor",
                "财务或业务硬数据锚点",
                ("financial_data",),
            ),
        ),
        evidence_plan=EvidencePlan(
            "valuation_current_anchor",
            (
                EvidenceRequirement("VALUATION_MARKET", "market_data", True),
                EvidenceRequirement(
                    "VALUATION_FINANCIAL",
                    "financial_data",
                    True,
                ),
            ),
        ),
        allowed_capabilities=("market_data", "financial_data"),
    )
    market = _evidence("market_data", "market-1")
    outcome = _outcome(
        draft="当前PB为4.33倍，但逐季财务锚点未取得。",
        evidence=(market,),
        bindings=(
            OutputEvidenceBinding("valuation_assessment", ("market-1",)),
            OutputEvidenceBinding("financial_business_anchor", ("market-1",)),
        ),
    )

    verified = verify_episode_outcome(contract, outcome)

    assert verified.verified_status == "partial"
    assert verified.completion.outputs[1].status == "missing"
    assert any("unsupported evidence type" in issue for issue in verified.issues)
    assert any("financial_data" in issue for issue in verified.issues)


def test_financial_anchor_requires_own_financial_hash_even_with_business_context() -> (
    None
):
    contract = _contract(
        outputs=(
            RequiredOutput(
                "valuation_assessment",
                "估值判断",
                ("market_data", "financial_data"),
            ),
            RequiredOutput(
                "financial_business_anchor",
                "财务或业务硬数据锚点",
                ("financial_data", "kb_search"),
            ),
        ),
        evidence_plan=EvidencePlan(
            "valuation_current_anchor",
            (
                EvidenceRequirement("VALUATION_MARKET", "market_data", True),
                EvidenceRequirement(
                    "VALUATION_FINANCIAL",
                    "financial_data",
                    True,
                ),
            ),
        ),
        allowed_capabilities=("market_data", "financial_data", "kb_search"),
    )
    market = _evidence("market_data", "market-1")
    financial = _evidence("financial_data", "financial-1")
    business = _evidence("kb_search", "business-1")
    outcome = _outcome(
        draft="当前PB为4.33倍；业务材料显示公司为PI薄膜厂商。",
        evidence=(market, financial, business),
        bindings=(
            OutputEvidenceBinding(
                "valuation_assessment",
                ("market-1", "financial-1"),
            ),
            OutputEvidenceBinding(
                "financial_business_anchor",
                ("business-1",),
            ),
        ),
    )

    verified = verify_episode_outcome(contract, outcome)

    assert verified.verified_status == "partial"
    assert verified.completion.outputs[1].status == "missing"
    assert any(
        item.code == IssueCode.FINANCIAL_ANCHOR_MISSING
        and item.subject == "financial_business_anchor"
        and "financial_data" in item.message
        for item in verified.issue_items
    )


def test_contract_and_outcome_task_hash_must_match() -> None:
    outcome = _outcome(status="partial", task_hash="different-hash")

    with pytest.raises(ValueError, match="task frame hash"):
        verify_episode_outcome(_contract(), outcome)


def test_preset_gap_replaces_generic_gap_wording_for_unfilled_slot() -> None:
    """W2a：预检降级格未填时，gap 文案用预置缺口声明而非泛化措辞。

    「chain_mapping未绑定可验证证据」把结构性无供给说成模型没干活；
    预置声明「知识库暂无该题材产业链证据」才是把责任放对位置的公开口径。
    """

    contract = _contract(
        outputs=(
            RequiredOutput(
                "direct_assessment",
                "直接判断",
                ("market_data", "news_search"),
            ),
            RequiredOutput(
                "chain_mapping",
                "产业链层级、角色与关键环节",
                ("market_data", "news_search"),
                required=False,
                preset_gap="知识库暂无该题材产业链证据",
            ),
        ),
    )
    market = _evidence("market_data", "market-1")
    outcome = _outcome(
        evidence=(market,),
        bindings=(OutputEvidenceBinding("direct_assessment", ("market-1",)),),
    )

    verified = verify_episode_outcome(contract, outcome)

    slot = next(
        item
        for item in verified.completion.outputs
        if item.output_id == "chain_mapping"
    )
    assert slot.status == "gap", "optional 格未填应记 gap 而非 missing"
    assert slot.gap == "知识库暂无该题材产业链证据"
    # 未降级格保持泛化文案——preset 只属于机械预检确认过的格。
    assert verified.verified_status == "completed"
