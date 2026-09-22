"""Deterministic output-to-evidence verification for continuous episodes.

The verifier proves structural grounding only: a declared output is bound to
evidence that was actually collected by an authorized evidence type. Semantic
claim support remains the responsibility of the shared grounding judge before
public presentation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from intelligence.services.agent_research import (
    AgentEvidence,
    HistoricalEvidenceProvenance,
    evidence_content_hash,
)
from intelligence.services.agent_runtime import AgentOutcome
from intelligence.services.episode_issues import Issue, IssueCode, serialize_issues
from intelligence.services.episode_output_substance import (
    required_output_evidence_floor,
    required_outputs_without_substance,
)
from intelligence.services.evidence_capabilities import collect_satisfied_plan_capabilities
from intelligence.services.generic_research_owner import CompletionReport
from intelligence.services.material_grounding import binding_source_errors, grounding_scope
from intelligence.services.material_delivery import (
    has_disclosed_material_gap,
    material_question_outputs,
)
from intelligence.services.research_contract import (
    OutputStatus,
    ResearchTaskContract,
)


VerifiedStatus = Literal["completed", "partial", "clarification", "failed"]


@dataclass(frozen=True)
class VerifiedEpisodeOutcome:
    outcome: AgentOutcome
    completion: CompletionReport
    verified_status: VerifiedStatus
    issue_items: tuple[Issue, ...] = ()
    issues: tuple[str, ...] = ()
    # Keep the immutable contract alongside the structural result.  The
    # semantic gate needs the exact required-output identities when a repair
    # is parsed and re-verified; reconstructing a weaker contract from prose
    # would make that second verification unsound.
    contract: ResearchTaskContract | None = None
    missing_outputs: tuple[str, ...] = ()
    mandatory_missing_capabilities: tuple[str, ...] = ()
    # 契约外、但引用的哈希都在证据池里的输出绑定（「扩展区」）。它们不参与结构
    # 完成度，也不进 completion.outputs；正文仍由语义判官逐句核验。
    extension_outputs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "issues", serialize_issues(self.issue_items))

    def to_dict(self) -> dict[str, object]:
        return {
            "verified_status": self.verified_status,
            "issues": list(self.issues),
            "completion": self.completion.to_dict(),
            "outcome": self.outcome.to_dict(),
            "missing_outputs": list(self.missing_outputs),
            "mandatory_missing_capabilities": list(
                self.mandatory_missing_capabilities
            ),
            "extension_outputs": list(self.extension_outputs),
        }


def _valid_history_identity(item: AgentEvidence) -> bool:
    provenance = item.history_provenance
    if not isinstance(provenance, HistoricalEvidenceProvenance):
        return False
    try:
        provenance.validate()
    except ValueError:
        return False
    return (
        item.tool in {"history_query", "read_history_result"}
        and item.content_hash == evidence_content_hash(item)
        and item.internal_locator == provenance.result_ref
        and item.independent_key == provenance.query_id
    )


def verify_episode_outcome(
    contract: ResearchTaskContract,
    outcome: AgentOutcome,
) -> VerifiedEpisodeOutcome:
    """Derive structural completion from bindings, not model confidence."""

    if (
        not contract.task_frame_hash
        or outcome.task_frame_hash != contract.task_frame_hash
    ):
        raise ValueError("contract/outcome task frame hash mismatch")

    issues: list[Issue] = []
    evidence_by_hash = {}
    duplicate_hashes: set[str] = set()
    for item in outcome.evidence:
        content_hash = item.content_hash.strip()
        if not content_hash:
            issues.append(
                Issue(
                    IssueCode.EVIDENCE_EMPTY_HASH,
                    item.tool,
                    f"evidence from {item.tool} has empty content hash",
                )
            )
            continue
        if content_hash in evidence_by_hash:
            duplicate_hashes.add(content_hash)
            issues.append(
                Issue(
                    IssueCode.EVIDENCE_DUPLICATE_HASH,
                    content_hash,
                    f"duplicate evidence hash: {content_hash}",
                )
            )
            continue
        evidence_by_hash[content_hash] = item

    required_by_id = {
        required.output_id: required for required in contract.required_outputs
    }
    bindings = {binding.output_id: binding for binding in outcome.bindings}
    # #819 零读复核恢复的旧工具输入：从 durable 的 model_input(prior_tool_evidence) 事件读回
    # 它们的 hash，冻结范围检查放行这一组，其余证据引用照旧受 P6 材料范围规则约束。
    from intelligence.services.prior_evidence import restored_prior_hashes

    frozen_prior_hashes = restored_prior_hashes(outcome.events)
    # 契约外的输出绑定不再连坐已完成的必需输出（2026-09-09 判官修复 01 第一刀）。
    # 复现：两个必需输出都 fulfilled、正文与证据完全一样，只多绑一个引用真实证据
    # 的 extra_analysis，旧判据就把整篇打成 partial 并拒绝部分放行，语义判官连核心
    # 答案都没看到。现在按「引用是否可核验」分两档：哈希都在池里 → 扩展区
    # （EXTRA_OUTPUT_BINDING，STRIP_OK，隔离出结构完成度）；引用了池里没有 /
    # 重复的哈希 → 编造引用（UNKNOWN_OUTPUT_BINDING，仍 BLOCK）。
    extension_outputs: list[str] = []
    forged_extra_outputs: list[str] = []
    for output_id in sorted(set(bindings) - set(required_by_id)):
        binding = bindings[output_id]
        unverifiable = tuple(
            content_hash
            for content_hash in binding.evidence_hashes
            if content_hash not in evidence_by_hash or content_hash in duplicate_hashes
        )
        source_errors = binding_source_errors(
            contract, binding, outcome.draft, outcome.evidence, frozen_prior_hashes=frozen_prior_hashes
        )
        if source_errors:
            forged_extra_outputs.append(output_id)
            issues.append(Issue(IssueCode.MATERIAL_SOURCE_VIOLATION, output_id, "; ".join(source_errors)))
            continue
        if unverifiable:
            forged_extra_outputs.append(output_id)
            issues.append(
                Issue(
                    IssueCode.UNKNOWN_OUTPUT_BINDING,
                    output_id,
                    (
                        f"unknown output binding: {output_id} cites unverifiable "
                        "evidence hash " + ",".join(unverifiable)
                    ),
                )
            )
            continue
        extension_outputs.append(output_id)
        issues.append(
            Issue(
                IssueCode.EXTRA_OUTPUT_BINDING,
                output_id,
                f"extension output binding isolated from contract: {output_id}",
            )
        )

    statuses: list[OutputStatus] = []
    material_specs = {spec.output_id: spec for spec in material_question_outputs(contract)}
    stripped_hashes: set[str] = set()
    for required in contract.required_outputs:
        binding = bindings.get(required.output_id)
        if binding is None:
            gap = f"仍缺少：{required.description}"
            statuses.append(
                OutputStatus(
                    required.output_id,
                    "missing" if required.required else "gap",
                    (),
                    gap,
                )
            )
            if required.required:
                issues.append(
                    Issue(
                        IssueCode.MISSING_REQUIRED_OUTPUT,
                        required.output_id,
                        f"missing required output: {required.output_id}",
                    )
                )
            continue

        source_errors = binding_source_errors(
            contract, binding, outcome.draft, outcome.evidence, frozen_prior_hashes=frozen_prior_hashes
        )
        if source_errors:
            issues.append(Issue(IssueCode.MATERIAL_SOURCE_VIOLATION, required.output_id, "; ".join(source_errors)))
        basis_mismatch = binding.basis != required.grounding_mode
        if basis_mismatch:
            issues.append(
                Issue(
                    IssueCode.GROUNDING_BASIS_MISMATCH,
                    required.output_id,
                    (
                        f"grounding basis mismatch for {required.output_id}: "
                        f"expected {required.grounding_mode}, got {binding.basis}"
                    ),
                )
            )

        unknown_hashes = tuple(
            content_hash
            for content_hash in binding.evidence_hashes
            if content_hash not in evidence_by_hash
        )
        collided_hashes = tuple(
            content_hash
            for content_hash in binding.evidence_hashes
            if content_hash in duplicate_hashes
        )
        if unknown_hashes:
            issues.append(
                Issue(
                    IssueCode.UNKNOWN_EVIDENCE_HASH,
                    required.output_id,
                    (
                        f"unknown evidence hash for {required.output_id}: "
                        + ",".join(unknown_hashes)
                    ),
                )
            )
        if collided_hashes:
            issues.append(
                Issue(
                    IssueCode.AMBIGUOUS_EVIDENCE_HASH,
                    required.output_id,
                    (
                        f"ambiguous evidence hash for {required.output_id}: "
                        + ",".join(collided_hashes)
                    ),
                )
            )
        if binding.gap:
            spec = material_specs.get(required.output_id)
            legal_gap = bool(
                spec is not None
                and not basis_mismatch
                and not source_errors
                and not binding.claims
                and not binding.evidence_hashes
                and has_disclosed_material_gap(spec, outcome.draft, binding.gap)
            )
            statuses.append(OutputStatus(
                required.output_id,
                "legal_gap" if legal_gap else ("missing" if required.required else "gap"),
                (),
                binding.gap,
            ))
            if required.required and not legal_gap:
                issues.append(Issue(
                    IssueCode.REQUIRED_OUTPUT_GAP,
                    required.output_id,
                    f"required output reports gap: {required.output_id}",
                ))
            continue

        evidence_items = tuple(
            evidence_by_hash[content_hash]
            for content_hash in binding.evidence_hashes
            if content_hash in evidence_by_hash and content_hash not in duplicate_hashes
        )
        wrong_types = tuple(
            item.tool
            for item in evidence_items
            if required.evidence_types and item.tool not in required.evidence_types
        )
        history_items = tuple(
            item for item in evidence_items
            if item.tool in {"history_query", "read_history_result"}
            or item.history_provenance is not None
        )
        unsupported_history = tuple(
            item
            for item in history_items
            if required.allowed_history_operations
            and isinstance(item.history_provenance, HistoricalEvidenceProvenance)
            and (
                item.history_provenance.operation
                not in required.allowed_history_operations
                or item.tool not in {"history_query", "read_history_result"}
            )
        )
        invalid_history_qualification = tuple(
            item
            for item in history_items
            if required.allowed_history_operations
            and not _valid_history_identity(item)
        )
        # 「引错算子」按剔除处理，不整槽作废：剪掉该引用，槽里还有合法证据就
        # 让回答出门；整格无合法证据才 BLOCK。理由是比例，与下方类型白名单
        # 同一口径：一张引错槽的卡不应让整篇有据的回答退成缺口模板。
        # （查过：allowed_history_operations 确实随 契约 to_dict 发给了模型，
        # 模型不是无从得知；因此这里不是在补偿信息缺口，而是在控制惩罚力度。）
        # 伪造或降级身份（invalid_history_qualification）不适用此例：那是账本完整性
        # 问题，哪怕旁边还有合法引用也必须拦住。
        history_details = tuple(
            (item.history_provenance.operation or "unknown")
            if isinstance(item.history_provenance, HistoricalEvidenceProvenance)
            and isinstance(item.history_provenance.operation, str)
            else "missing_provenance" if item.history_provenance is None
            else "invalid_provenance"
            for item in (*unsupported_history, *invalid_history_qualification)
        )
        # 类型白名单按「剔除非法、保留合法」执行，不再整槽作废（2026-08-19，
        # run_20260819_130854：prime_quote 绑了 market_data + finance_query
        # 各若干条，旧判据把合法行情哈希一并清掉 → 整篇换缺口模板）。
        # 混绑时剔掉非法哈希、槽位靠剩余合法证据继续成立；整格找不出一条
        # 合法证据才判 missing。「拿行情洗白财务锚」不靠这条挡——它由下面的
        # evidence floor（missing required evidence type）硬性拦住。
        kept_hashes = tuple(
            content_hash
            for content_hash in binding.evidence_hashes
            if content_hash in evidence_by_hash
            and content_hash not in duplicate_hashes
            and (
                not required.evidence_types
                or evidence_by_hash[content_hash].tool in required.evidence_types
            )
            and evidence_by_hash[content_hash] not in unsupported_history
            and evidence_by_hash[content_hash] not in invalid_history_qualification
        )
        kept_items = tuple(
            evidence_by_hash[content_hash] for content_hash in kept_hashes
        )
        if unsupported_history or invalid_history_qualification:
            blocked = bool(invalid_history_qualification) or not kept_items
            prefix = "" if blocked else "stripped "
            issues.append(
                Issue(
                    (
                        IssueCode.HISTORY_OPERATION_UNSUPPORTED
                        if blocked
                        else IssueCode.HISTORY_OPERATION_STRIPPED
                    ),
                    required.output_id,
                    (
                        f"{prefix}history evidence is not eligible for "
                        f"{required.output_id}: " + ",".join(history_details)
                    ),
                )
            )
            stripped_hashes.update(
                item.content_hash
                for item in (*unsupported_history, *invalid_history_qualification)
                if item.content_hash.strip()
            )
        if wrong_types:
            prefix = "stripped " if kept_items else ""
            type_message = (
                f"{prefix}unsupported evidence type for {required.output_id}: "
                + ",".join(wrong_types)
            )
            issues.append(
                Issue(
                    (
                        IssueCode.EVIDENCE_TYPE_STRIPPED
                        if kept_items
                        else IssueCode.EVIDENCE_TYPE_UNSUPPORTED
                    ),
                    required.output_id,
                    type_message,
                )
            )
            stripped_hashes.update(
                item.content_hash
                for item in evidence_items
                if required.evidence_types
                and item.tool not in required.evidence_types
                and item.content_hash.strip()
            )

        evidence_floor = required_output_evidence_floor(required.output_id)
        missing_floor = tuple(
            tool
            for tool in evidence_floor
            if not any(item.tool == tool for item in kept_items)
        )
        if missing_floor:
            issues.append(
                Issue(
                    IssueCode.FINANCIAL_ANCHOR_MISSING,
                    required.output_id,
                    (
                        f"missing required evidence type for {required.output_id}: "
                        + ",".join(missing_floor)
                    ),
                )
            )

        valid = bool(
            (
                required.grounding_mode != "evidence"
                or bool(kept_hashes)
                or (grounding_scope(contract) == "material_only" and bool(binding.claims))
            )
            and not source_errors
            and not unknown_hashes
            and not collided_hashes
            and (not wrong_types or bool(kept_hashes))
            and not missing_floor
            and not basis_mismatch
            # 引错算子与类型白名单同一口径：剪掉那条引用，剩下合法证据槽位继续成立。
            # 身份无效是账本完整性问题，不给这条出路。
            and (not unsupported_history or bool(kept_hashes))
            and not invalid_history_qualification
            and len(evidence_items) == len(binding.evidence_hashes)
        )
        if valid:
            statuses.append(
                OutputStatus(
                    required.output_id,
                    "fulfilled",
                    kept_hashes,
                )
            )
        else:
            gap = f"{required.description}未绑定可验证证据"
            statuses.append(
                OutputStatus(
                    required.output_id,
                    "missing" if required.required else "gap",
                    (),
                    gap,
                )
            )

    usable_evidence = tuple(
        item
        for item in outcome.evidence
        if item.content_hash.strip()
        and item.content_hash not in stripped_hashes
        and str(item.detail or "").strip()
        and "预取失败" not in str(item.detail)
    )
    available_capabilities = collect_satisfied_plan_capabilities(
        usable_evidence,
        outcome.traces,
    )
    mandatory_missing = tuple(
        capability
        for capability in contract.evidence_plan.mandatory_capabilities
        if capability not in available_capabilities
    )
    if mandatory_missing:
        joined = ",".join(mandatory_missing)
        issues.append(
            Issue(
                IssueCode.MISSING_MANDATORY_CAPABILITY,
                joined,
                f"missing mandatory capability evidence: {joined}",
            )
        )

    missing_substance = required_outputs_without_substance(contract, outcome.draft)
    if missing_substance:
        missing_set = set(missing_substance)
        statuses = [
            OutputStatus(
                status.output_id,
                "missing",
                (),
                f"{required_by_id[status.output_id].description}缺少实质内容",
            )
            if status.output_id in missing_set
            else status
            for status in statuses
        ]
        issues.extend(
            Issue(
                IssueCode.REQUIRED_OUTPUT_NO_SUBSTANCE,
                output_id,
                f"required output lacks substantive answer: {output_id}",
            )
            for output_id in missing_substance
        )

    required_statuses = tuple(
        status
        for required, status in zip(contract.required_outputs, statuses)
        if required.required
    )
    missing_outputs = tuple(
        status.output_id
        for required, status in zip(contract.required_outputs, statuses)
        if required.required and status.status not in {"fulfilled", "legal_gap"}
    )
    all_required_fulfilled = all(
        status.status == "fulfilled" for status in required_statuses
    )
    structurally_complete = bool(
        all_required_fulfilled
        and not mandatory_missing
        and not forged_extra_outputs
        and outcome.draft.strip()
    )

    if outcome.status in {"clarification", "failed"}:
        verified_status = outcome.status
    elif structurally_complete and outcome.status == "completed":
        verified_status = "completed"
    else:
        # Verification may preserve or downgrade the runtime status, never
        # upgrade it. A structurally complete partial can still enter the
        # semantic gate and release useful prose as a first-class partial.
        verified_status = "partial"

    completion = CompletionReport(
        status="completed" if verified_status == "completed" else "partial",
        outputs=tuple(statuses),
        factual_grounding=("fulfilled" if all_required_fulfilled else "partial"),
        causal_adequacy="unknown",
        task_coverage=("fulfilled" if all_required_fulfilled else "partial"),
        business_status=("complete" if verified_status == "completed" else "partial"),
    )
    return VerifiedEpisodeOutcome(
        outcome=outcome,
        completion=completion,
        verified_status=verified_status,
        issue_items=tuple(dict.fromkeys(issues)),
        contract=contract,
        missing_outputs=missing_outputs,
        mandatory_missing_capabilities=mandatory_missing,
        extension_outputs=tuple(extension_outputs),
    )


__all__ = [
    "VerifiedEpisodeOutcome",
    "VerifiedStatus",
    "verify_episode_outcome",
]
