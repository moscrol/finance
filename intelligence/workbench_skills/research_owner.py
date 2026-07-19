from __future__ import annotations

import datetime
import hashlib
import json
from collections.abc import Callable
from dataclasses import asdict, dataclass, replace

from intelligence.api.structured_reports import ask_result_modules
from intelligence.services import answer_model, web_research
from intelligence.services.ask import AskOptions, AskResult, answer_query
from intelligence.services.market_analogs import load_historical_analog_artifact
from intelligence.services.market_midterm import load_midterm_trend_artifact
from intelligence.services.query_understanding import QueryEnvelope, understand_query
from intelligence.services.research_contract import (
    EvidenceAtom,
    OWNER_WORKFLOW_SPECS,
    StageArtifact,
)
from intelligence.services.scenario_tree import build_scenario_tree_artifact
from intelligence.workbench_skills.contracts import (
    JsonObject,
    SkillAnswerContract,
    SkillExecutionContext,
    SkillOutput,
    SkillResultStatus,
    redact_json,
)
from intelligence.workbench_skills.owner_dag import (
    StageAdapter,
    StageExecution,
    execute_owner_dag,
)

AnswerQuery = Callable[[AskOptions], AskResult]
WebSearch = Callable[..., web_research.WebSearchResult]

_EXTERNAL_NEWS_TIMEOUT_SECONDS = 15.0
_EXTERNAL_NEWS_LOCAL_STAGES = frozenset({"original_disclosure", "event_facts"})

_PRIOR_ONLY_EVIDENCE = frozenset({"M", "ONTOLOGY", "V"})
_STRUCTURAL_STAGES = frozenset(
    {
        "definition",
        "chain_stages",
        "company_master",
    }
)

# BGE-m3 is prewarmed at API startup, but the first real owner query still has to
# populate query-specific retrieval caches.  Production replay measured that path
# at about 28 seconds, so keep a bounded margin below the 120-second research
# deadline instead of treating a healthy first query as a 20-second timeout.
_OWNER_INITIAL_STAGE_TIMEOUT_SECONDS = 40


@dataclass(frozen=True)
class ResearchOwnerConfig:
    skill_id: str
    title: str
    question_type: str
    retrieval_plan: tuple[str, ...]
    output_contract: tuple[str, ...]
    presentation_kind: str
    evidence_prefixes: tuple[str, ...]
    wiki_rag_timeout: int = _OWNER_INITIAL_STAGE_TIMEOUT_SECONDS
    module_timeout: int = 20
    use_modules: bool = True


class ResearchOwnerSkill:
    def __init__(
        self,
        config: ResearchOwnerConfig,
        *,
        answer_query_fn: AnswerQuery = answer_query,
        web_search_fn: WebSearch = web_research.fetch_web_search,
    ) -> None:
        self.config = config
        self.skill_id = config.skill_id
        self._answer_query = answer_query_fn
        self._web_search = web_search_fn

    def execute(self, context: SkillExecutionContext) -> SkillOutput:
        options = AskOptions(
            query=context.query,
            user=context.user_id,
            compose=True,
            synthesize=False,
            compose_revise_on_warn=False,
            use_modules=self.config.use_modules,
            wiki_rag_timeout=self.config.wiki_rag_timeout,
            wiki_rag_cache_scope=(
                f"{context.user_id}:{context.conversation_id or context.run_id}"
            ),
            module_timeout=self.config.module_timeout,
            market_db_path=(
                context.repo_root / "db" / "market_feature_store.duckdb"
            ),
            conversation_context=context.conversation_context,
            include_memory_block=True,
            include_recall_block=True,
            question_type_override=self.config.question_type,
            deadline=context.deadline,
        )
        stages = OWNER_WORKFLOW_SPECS[self.config.skill_id].retrieval_stages
        envelope = understand_query(context.query)
        dag = execute_owner_dag(
            cache_key=f"{self.skill_id}:{context.query}",
            stages=stages,
            retrieve=lambda: self._answer_query(options),
            cache=context.retrieval_cache,
            deadline=context.deadline,
            stage_adapters=self._stage_adapters(context, options, envelope),
        )
        result = dag.result
        stage_artifacts = [asdict(artifact) for artifact in dag.artifacts]
        contract = self._answer_contract(
            result,
            dag.artifacts,
            query=context.query,
            matched_theme=envelope.subject,
            inherited_answer_spec=context.inherited_answer_spec,
        )
        if result is None:
            warnings = list(dag.warnings)
            status = self._owner_result_status(
                contract,
                dag.artifacts,
                warnings,
            )
            raw_result_ref = self._store_partial_artifact(
                context,
                warnings=warnings,
                stage_artifacts=stage_artifacts,
                contract=contract,
                status=status,
            )
            return SkillOutput(
                skill_id=self.skill_id,
                modules=[],
                citations=[],
                warnings=warnings,
                as_of=None,
                raw_result_ref=raw_result_ref,
                answer_contract=contract,
                stage_artifacts=stage_artifacts,
                status=status,
            )
        retrieved_modules = self._modules(result)
        retrieved_citations = self._citations(result)
        warnings = list(dict.fromkeys((*result.warnings, *dag.warnings)))
        if contract is None:
            warnings.append("专项检索未形成可追溯事实，已回退基础金融回答。")
        status = self._owner_result_status(
            contract,
            dag.artifacts,
            warnings,
        )
        raw_result_ref = self._store_artifact(
            context,
            result,
            citations=retrieved_citations,
            warnings=warnings,
            owned=contract is not None,
            stage_artifacts=stage_artifacts,
            status=status,
        )
        # P1-B：完整 ResearchResult 通道——raw AskResult 以对象引用放入 turn 级
        # retrieval_cache（进程内传递、不经序列化），orchestrator 侧优先消费它，
        # 替代 _skill_owner_result 的有损重建（真实 trade_date/warnings/
        # provider_traces/telemetry/原生 citations 全保留）。
        context.retrieval_cache[f"owner_raw_result:{self.skill_id}"] = result
        return SkillOutput(
            skill_id=self.skill_id,
            modules=retrieved_modules if contract is not None else [],
            citations=retrieved_citations if contract is not None else [],
            warnings=warnings,
            as_of=result.trade_date,
            raw_result_ref=raw_result_ref,
            answer_contract=contract,
            stage_artifacts=stage_artifacts,
            status=status,
            provider_traces=self._retrieval_traces(result),
        )

    def _retrieval_traces(self, result: AskResult) -> list[dict]:
        """把 owner 内部检索可观测序列化成 JSON trace 列表（穿透 skill 边界）。

        闭环检索与 wiki 遥测没有独立通道，折叠为合成 ProviderTrace 并入同一
        列表，_record_retrieval 的 trace payload 会原样带出。"""
        traces = [trace.to_dict() for trace in result.provider_traces]
        if result.wiki_rag_telemetry is not None:
            telemetry = result.wiki_rag_telemetry
            traces.append(
                {
                    "provider": "wiki_rag",
                    "capability": "owner_retrieval_telemetry",
                    "status": telemetry.status,
                    "detail": telemetry.summary_line(),
                    "source_trade_date": None,
                    "result_count": telemetry.hit_count,
                }
            )
        if result.closed_loop_retrieval is not None:
            inspector = result.closed_loop_retrieval.inspector_dict()
            traces.append(
                {
                    "provider": "closed_loop_retrieval",
                    "capability": "owner_retrieval_telemetry",
                    "status": "success",
                    "detail": json.dumps(inspector, ensure_ascii=False)[:800],
                    "source_trade_date": None,
                    "result_count": int(
                        inspector.get("buckets", {}).get("conclusion", 0)
                    ),
                }
            )
        return traces

    def _owner_result_status(
        self,
        contract: SkillAnswerContract | None,
        stage_artifacts: tuple[StageArtifact, ...],
        warnings: list[str],
    ) -> SkillResultStatus:
        required = tuple(
            artifact
            for artifact in stage_artifacts
            if artifact.required_output
        )
        if contract is None or not required:
            return "failed"
        if all(
            artifact.status in {"failed", "timeout", "skipped"}
            for artifact in required
        ):
            return "failed"
        if any(artifact.status != "completed" for artifact in required):
            return "partial"
        if any(
            not self._stage_meets_evidence_threshold(artifact)
            for artifact in required
        ):
            return "degraded"
        if not contract.answer_spec.quality.passed:
            return "degraded"
        if contract.answer_spec.quality.issues or warnings:
            return "degraded"
        return "completed"

    @classmethod
    def _stage_meets_evidence_threshold(
        cls,
        artifact: StageArtifact,
    ) -> bool:
        if artifact.payload.get("available") is False:
            return False
        if artifact.stage in _STRUCTURAL_STAGES:
            return True
        if artifact.stage == "company_evidence":
            claims = artifact.payload.get("claims")
            return isinstance(claims, list) and any(
                cls._payload_has_hard_company_evidence(claim)
                for claim in claims
                if isinstance(claim, dict)
            )
        return bool(artifact.evidence_atom_ids)

    @staticmethod
    def _payload_has_hard_company_evidence(
        claim: dict[str, object],
    ) -> bool:
        evidence_ids = claim.get("evidence_ids")
        if not isinstance(evidence_ids, list):
            return False
        return bool(
            claim.get("company")
            and claim.get("status") == answer_model.ClaimStatus.VERIFIED.value
            and answer_model.is_hard_evidence_tier(
                str(claim.get("evidence_tier") or ""),
                tuple(str(item) for item in evidence_ids),
            )
        )

    def _answer_contract(
        self,
        result: AskResult | None,
        stage_artifacts: tuple[StageArtifact, ...] = (),
        *,
        query: str = "",
        matched_theme: str | None = None,
        inherited_answer_spec: JsonObject | None = None,
    ) -> SkillAnswerContract | None:
        spec = result.answer_spec if result is not None else None
        used_fallback = False
        if (
            spec is None
            and self._preserves_required_owner_outputs(stage_artifacts)
        ):
            spec = self._owner_fallback_answer_spec(
                query=query,
                matched_theme=matched_theme,
                stage_artifacts=stage_artifacts,
            )
            used_fallback = True
        if spec is None:
            return None
        has_traceable_fact = self._has_traceable_verified_fact(spec)
        inherited_atoms = (
            inherited_answer_spec.get("research_evidence_atoms", [])
            if inherited_answer_spec
            else []
        )
        has_inherited_evidence = bool(
            isinstance(inherited_atoms, list)
            and any(EvidenceAtom.from_dict(value) is not None for value in inherited_atoms)
        )
        if (
            not has_traceable_fact
            and not has_inherited_evidence
            and not used_fallback
        ):
            return None
        owned_spec = replace(
            spec,
            prompt_constraints=tuple(
                dict.fromkeys(
                    (
                        *spec.prompt_constraints,
                        *self.config.output_contract,
                    )
                )
            ),
            presentation_kind=self.config.presentation_kind,
            presentation_title=self.config.title,
            research_artifacts=tuple(stage_artifacts),
            research_evidence_atoms=tuple(
                {
                    atom.atom_id: atom
                    for atom in (
                        *spec.research_evidence_atoms,
                        *self._artifact_evidence_atoms(stage_artifacts),
                    )
                }.values()
            ),
        )
        owned_spec = self._merge_inherited_answer_spec(
            owned_spec,
            inherited_answer_spec,
        )
        owned_spec = answer_model.finalize_answer_spec(owned_spec)
        return SkillAnswerContract(
            retrieval_plan=self.config.retrieval_plan,
            output_contract=self.config.output_contract,
            answer_spec=owned_spec,
            question_type=self.config.question_type,
        )

    @classmethod
    def _merge_inherited_answer_spec(
        cls,
        current: answer_model.AnswerSpec,
        inherited: JsonObject | None,
    ) -> answer_model.AnswerSpec:
        if not inherited:
            return current

        def claims(key: str) -> tuple[answer_model.Claim, ...]:
            values = inherited.get(key)
            if not isinstance(values, list):
                return ()
            return tuple(
                claim
                for value in values
                if (claim := cls._claim_from_dict(value)) is not None
            )

        def merge_claims(
            existing: tuple[answer_model.Claim, ...],
            extra: tuple[answer_model.Claim, ...],
        ) -> tuple[answer_model.Claim, ...]:
            return tuple(
                {
                    claim.claim_id: claim
                    for claim in (*extra, *existing)
                }.values()
            )

        sources = tuple(
            source
            for value in inherited.get("sources", [])
            if (source := cls._evidence_ref_from_dict(value)) is not None
        ) if isinstance(inherited.get("sources"), list) else ()
        companies = tuple(
            company
            for value in inherited.get("company_table", [])
            if (company := cls._company_from_dict(value)) is not None
        ) if isinstance(inherited.get("company_table"), list) else ()
        artifacts = tuple(
            artifact
            for value in inherited.get("research_artifacts", [])
            if (artifact := StageArtifact.from_dict(value)) is not None
        ) if isinstance(inherited.get("research_artifacts"), list) else ()
        atoms = tuple(
            atom
            for value in inherited.get("research_evidence_atoms", [])
            if (atom := EvidenceAtom.from_dict(value)) is not None
        ) if isinstance(inherited.get("research_evidence_atoms"), list) else ()
        actions = inherited.get("next_actions")
        inherited_actions = (
            tuple(str(item) for item in actions if str(item).strip())
            if isinstance(actions, list)
            else ()
        )
        return replace(
            current,
            summary=merge_claims(current.summary, claims("summary")),
            verified_facts=merge_claims(
                current.verified_facts,
                claims("verified_facts"),
            ),
            company_table=tuple(
                {
                    (company.company, company.ticker): company
                    for company in (*companies, *current.company_table)
                }.values()
            ),
            counter_evidence=merge_claims(
                current.counter_evidence,
                claims("counter_evidence"),
            ),
            gaps=merge_claims(current.gaps, claims("gaps")),
            triggers=merge_claims(current.triggers, claims("triggers")),
            next_actions=tuple(
                dict.fromkeys((*current.next_actions, *inherited_actions))
            ),
            sources=tuple(
                {
                    source.evidence_id: source
                    for source in (*sources, *current.sources)
                }.values()
            ),
            research_artifacts=tuple(
                {
                    (
                        artifact.stage,
                        artifact.producer,
                        artifact.input_hash,
                    ): artifact
                    for artifact in (*artifacts, *current.research_artifacts)
                }.values()
            ),
            research_evidence_atoms=tuple(
                {
                    atom.atom_id: atom
                    for atom in (*atoms, *current.research_evidence_atoms)
                }.values()
            ),
        )

    @staticmethod
    def _claim_from_dict(value: object) -> answer_model.Claim | None:
        if not isinstance(value, dict):
            return None
        try:
            status = answer_model.ClaimStatus(str(value.get("status") or "candidate"))
            evidence_ids = value.get("evidence_ids", [])
            counter_evidence = value.get("counter_evidence", [])
            if not isinstance(evidence_ids, list) or not isinstance(
                counter_evidence,
                list,
            ):
                return None
            confidence = value.get("confidence")
            return answer_model.Claim(
                claim_id=str(value["claim_id"]),
                text=str(value["text"]),
                claim_type=str(value["claim_type"]),
                theme=str(value.get("theme") or ""),
                evidence_ids=tuple(str(item) for item in evidence_ids),
                evidence_tier=str(value.get("evidence_tier") or ""),
                freshness=(
                    str(value["freshness"])
                    if value.get("freshness") is not None
                    else None
                ),
                confidence=(
                    float(confidence)
                    if isinstance(confidence, (int, float))
                    else None
                ),
                counter_evidence=tuple(
                    str(item) for item in counter_evidence
                ),
                status=status,
                company=(
                    str(value["company"])
                    if value.get("company") is not None
                    else None
                ),
            )
        except (KeyError, TypeError, ValueError):
            return None

    @staticmethod
    def _evidence_ref_from_dict(
        value: object,
    ) -> answer_model.EvidenceRef | None:
        if not isinstance(value, dict):
            return None
        try:
            return answer_model.EvidenceRef(
                evidence_id=str(value["evidence_id"]),
                source=str(value["source"]),
                detail=str(value.get("detail") or ""),
                tier=str(value.get("tier") or ""),
                source_date=(
                    str(value["source_date"])
                    if value.get("source_date") is not None
                    else None
                ),
                freshness=str(value.get("freshness") or "unknown"),
            )
        except KeyError:
            return None

    @classmethod
    def _company_from_dict(
        cls,
        value: object,
    ) -> answer_model.CompanyAssessment | None:
        if not isinstance(value, dict):
            return None
        raw_claims = value.get("claims", [])
        raw_gaps = value.get("evidence_gaps", [])
        if not isinstance(raw_claims, list) or not isinstance(raw_gaps, list):
            return None
        try:
            tier = answer_model.CompanyTier(str(value.get("tier") or "candidate"))
            return answer_model.CompanyAssessment(
                company=str(value["company"]),
                ticker=str(value.get("ticker") or ""),
                chain_stage=str(value.get("chain_stage") or "待确认"),
                directness=str(value.get("directness") or "待确认"),
                tier=tier,
                claims=tuple(
                    claim
                    for item in raw_claims
                    if (claim := cls._claim_from_dict(item)) is not None
                ),
                evidence_gaps=tuple(str(item) for item in raw_gaps),
            )
        except (KeyError, ValueError):
            return None

    def _owner_fallback_answer_spec(
        self,
        *,
        query: str,
        matched_theme: str | None,
        stage_artifacts: tuple[StageArtifact, ...],
    ) -> answer_model.AnswerSpec:
        research_spec = answer_model.resolve_theme_research_spec(
            query,
            matched_theme,
        )
        gap_artifacts = tuple(
            artifact
            for artifact in stage_artifacts
            if artifact.required_output and artifact.status != "completed"
        )
        gaps = tuple(
            answer_model.make_claim(
                claim_id=f"theme-fallback:gap:{index}",
                text=(
                    artifact.degrade_reason
                    or f"{artifact.stage} 未形成完整输出"
                ),
                claim_type="research_gap",
                theme=research_spec.theme,
                status=answer_model.ClaimStatus.MISSING,
            )
            for index, artifact in enumerate(gap_artifacts, start=1)
        )
        summary = (
            answer_model.make_claim(
                claim_id=f"{self.skill_id}:fallback:summary",
                text=(
                    "专项检索或回答模型未在阶段时限内完成；"
                    "仅展示已完成的结构化阶段，并明确保留缺失区块。"
                ),
                claim_type="research_scope",
                theme=research_spec.theme,
                status=answer_model.ClaimStatus.MISSING,
            ),
        )
        sources = tuple(
            answer_model.EvidenceRef(
                evidence_id=evidence_id,
                source=source,
                detail=detail,
                tier="L4",
            )
            for stage, evidence_id, source, detail in (
                (
                    "market_lifecycle",
                    "D6",
                    "market_midterm.D6",
                    "本地 DuckDB 多日题材趋势",
                ),
                (
                    "historical_analogs",
                    "D8",
                    "market_analogs.D8",
                    "本地 DuckDB 历史类似窗口",
                ),
            )
            if any(
                artifact.stage == stage and artifact.evidence_atom_ids
                for artifact in stage_artifacts
            )
        )
        return answer_model.AnswerSpec(
            research_spec=research_spec,
            summary=summary,
            verified_facts=(),
            company_table=(),
            counter_evidence=(),
            gaps=gaps,
            triggers=(),
            next_actions=(
                "补齐公司级 L3 证据后再升级公司判断。",
                "下一验证窗口复核中期趋势、历史类比与情景触发条件。",
            ),
            sources=sources,
            system_notices=(
                "能力守恒降级：阶段失败不删除其他已完成区块或必需标题。",
            ),
            prompt_constraints=self.config.output_contract,
            presentation_kind=self.config.presentation_kind,
            presentation_title=self.config.title,
            research_artifacts=stage_artifacts,
            research_evidence_atoms=self._artifact_evidence_atoms(
                stage_artifacts
            ),
        )

    def _preserves_required_owner_outputs(
        self,
        stage_artifacts: tuple[StageArtifact, ...],
    ) -> bool:
        owner_stages = set(
            OWNER_WORKFLOW_SPECS[self.config.skill_id].retrieval_stages
        )
        if self.skill_id == "theme-research":
            owner_stages &= {
                "historical_analogs",
                "scenario_tree",
                "counterevidence",
            }
        return any(
            artifact.required_output and artifact.stage in owner_stages
            for artifact in stage_artifacts
        )

    def _stage_adapters(
        self,
        context: SkillExecutionContext,
        options: AskOptions,
        envelope: QueryEnvelope,
    ) -> dict[str, StageAdapter]:
        if self.skill_id == "theme-research":
            return self._theme_stage_adapters(context, options, envelope)
        if self.skill_id == "stock-deep-dive":
            return self._stock_stage_adapters(context, options, envelope)
        if self.skill_id == "financial-analysis":
            return self._financial_stage_adapters(context, options, envelope)
        return self._news_stage_adapters(context, options, envelope)

    def _stage_adapter(
        self,
        context: SkillExecutionContext,
        envelope: QueryEnvelope,
        stage: str,
        *,
        producer: str,
        artifact_type: str,
        timeout_seconds: float,
        on_failure: str,
        required_output: bool = True,
        execute: Callable[
            [AskResult | None, tuple[StageArtifact, ...]],
            StageExecution,
        ],
    ) -> StageAdapter:
        return StageAdapter(
            producer=producer,
            input_hash=self._stage_input_hash(context, envelope, stage),
            artifact_type=artifact_type,
            required_output=required_output,
            timeout_seconds=timeout_seconds,
            on_failure=on_failure,
            execute=execute,
        )

    def _stock_stage_adapters(
        self,
        context: SkillExecutionContext,
        options: AskOptions,
        envelope: QueryEnvelope,
    ) -> dict[str, StageAdapter]:
        def company_master(
            _result: AskResult | None,
            _artifacts: tuple[StageArtifact, ...],
        ) -> StageExecution:
            result = self._answer_query(options)
            anchor = result.anchored_entity
            company = anchor.entity if anchor is not None else ""
            ticker = anchor.ticker if anchor is not None else ""
            if not company and result.answer_spec is not None:
                first_company = next(
                    iter(result.answer_spec.company_table),
                    None,
                )
                if first_company is not None:
                    company = first_company.company
                    ticker = first_company.ticker
            if not company:
                company = envelope.subject or result.matched_theme or ""
            available = bool(company)
            spec = result.answer_spec
            return StageExecution(
                status="completed" if available else "partial",
                payload={
                    "company": company,
                    "ticker": ticker,
                    "matched_by": (
                        anchor.matched_by if anchor is not None else "query"
                    ),
                    "concepts": (
                        list(anchor.concepts) if anchor is not None else []
                    ),
                    "as_of": result.trade_date,
                    "available": available,
                },
                evidence_atom_ids=self._claim_atom_ids(
                    spec,
                    self._company_claims(spec),
                ),
                result=result,
                degrade_reason=None if available else "未能锚定公司主体",
            )

        def company_evidence(
            result: AskResult | None,
            _artifacts: tuple[StageArtifact, ...],
        ) -> StageExecution:
            spec = result.answer_spec if result is not None else None
            claims = self._company_claims(spec)
            return self._claim_stage_execution(
                result,
                spec,
                claims,
                payload_key="claims",
                degrade_reason="未形成公司级可追溯证据",
            )

        def financial_transmission(
            result: AskResult | None,
            _artifacts: tuple[StageArtifact, ...],
        ) -> StageExecution:
            spec = result.answer_spec if result is not None else None
            claims = self._matching_claims(
                spec,
                ("收入", "营收", "利润", "毛利", "成本", "订单", "产能", "兑现"),
            )
            payload = {
                "claims": [claim.to_dict() for claim in claims],
                "valuation_gaps": (
                    result.valuation_note.to_dict()
                    if result is not None and result.valuation_note is not None
                    else {}
                ),
                "evidence_gaps": (
                    result.gap_radar.to_dict()
                    if result is not None and result.gap_radar is not None
                    else {}
                ),
            }
            return self._claim_stage_execution(
                result,
                spec,
                claims,
                payload=payload,
                degrade_reason="未形成可验证的财务传导链",
            )

        def market_choice(
            result: AskResult | None,
            _artifacts: tuple[StageArtifact, ...],
        ) -> StageExecution:
            spec = result.answer_spec if result is not None else None
            claims = self._matching_claims(
                spec,
                ("盘面", "涨停", "新高", "成交", "相对强度", "生命周期", "同链", "替代"),
            )
            payload = {
                "claims": [claim.to_dict() for claim in claims],
                "market_state": (
                    result.market_state.to_dict()
                    if result is not None and result.market_state is not None
                    else {}
                ),
                "theme_lifecycle": (
                    result.theme_lifecycle.to_dict()
                    if result is not None
                    and result.theme_lifecycle is not None
                    else {}
                ),
            }
            return self._claim_stage_execution(
                result,
                spec,
                claims,
                payload=payload,
                degrade_reason="未形成市场选择或同链比较证据",
            )

        def counterevidence(
            result: AskResult | None,
            _artifacts: tuple[StageArtifact, ...],
        ) -> StageExecution:
            spec = result.answer_spec if result is not None else None
            claims = (
                (*spec.counter_evidence, *spec.gaps, *spec.triggers)
                if spec is not None
                else ()
            )
            payload = {
                "claims": [claim.to_dict() for claim in claims],
                "plan": (
                    result.counterevidence.to_dict()
                    if result is not None
                    and result.counterevidence is not None
                    else {}
                ),
            }
            return self._claim_stage_execution(
                result,
                spec,
                claims,
                payload=payload,
                degrade_reason="未形成反证、降级与证伪条件",
            )

        return {
            "company_master": self._stage_adapter(
                context,
                envelope,
                "company_master",
                producer="answer_query.company_master",
                artifact_type="CompanyMasterArtifact",
                timeout_seconds=self.config.wiki_rag_timeout,
                on_failure="continue_with_unresolved_company",
                execute=company_master,
            ),
            "company_evidence": self._stage_adapter(
                context,
                envelope,
                "company_evidence",
                producer="answer_spec.company_evidence",
                artifact_type="CompanyEvidenceArtifact",
                timeout_seconds=2,
                on_failure="continue_without_company_promotion",
                execute=company_evidence,
            ),
            "financial_transmission": self._stage_adapter(
                context,
                envelope,
                "financial_transmission",
                producer="answer_spec.financial_transmission",
                artifact_type="FinancialTransmissionArtifact",
                timeout_seconds=2,
                on_failure="render_financial_transmission_gap",
                execute=financial_transmission,
            ),
            "market_choice": self._stage_adapter(
                context,
                envelope,
                "market_choice",
                producer="market_structure.choice",
                artifact_type="MarketChoiceArtifact",
                timeout_seconds=2,
                on_failure="render_market_choice_gap",
                execute=market_choice,
            ),
            "counterevidence": self._stage_adapter(
                context,
                envelope,
                "counterevidence",
                producer="research_brief.counterevidence",
                artifact_type="CounterEvidenceArtifact",
                timeout_seconds=2,
                on_failure="render_falsification_placeholder",
                execute=counterevidence,
            ),
        }

    def _financial_stage_adapters(
        self,
        context: SkillExecutionContext,
        options: AskOptions,
        envelope: QueryEnvelope,
    ) -> dict[str, StageAdapter]:
        def report_period(
            _result: AskResult | None,
            _artifacts: tuple[StageArtifact, ...],
        ) -> StageExecution:
            result = self._answer_query(options)
            spec = result.answer_spec
            source_dates = (
                sorted(
                    {
                        source.source_date
                        for source in spec.sources
                        if source.source_date
                    },
                    reverse=True,
                )
                if spec is not None
                else []
            )
            periods = (
                sorted(
                    {
                        claim.freshness
                        for claim in self._all_claims(spec)
                        if claim.freshness
                    },
                    reverse=True,
                )
                if spec is not None
                else []
            )
            available = bool(periods or source_dates or result.trade_date)
            return StageExecution(
                status="completed" if available else "partial",
                payload={
                    "subject": envelope.subject or result.matched_theme,
                    "report_periods": periods,
                    "source_dates": source_dates,
                    "as_of": result.trade_date,
                    "available": available,
                },
                evidence_atom_ids=tuple(
                    atom.atom_id
                    for atom in (
                        answer_model.evidence_atoms_from_answer_spec(spec)
                        if spec is not None
                        else ()
                    )
                ),
                result=result,
                degrade_reason=None if available else "未识别报告期间",
            )

        def financial_metrics(
            result: AskResult | None,
            _artifacts: tuple[StageArtifact, ...],
        ) -> StageExecution:
            spec = result.answer_spec if result is not None else None
            claims = self._matching_claims(
                spec,
                ("营收", "营业收入", "净利润", "归母", "毛利率", "净利率", "现金流"),
            )
            return self._claim_stage_execution(
                result,
                spec,
                claims,
                payload_key="metrics",
                degrade_reason="未形成带来源的财务指标",
            )

        def segment_disclosure(
            result: AskResult | None,
            _artifacts: tuple[StageArtifact, ...],
        ) -> StageExecution:
            spec = result.answer_spec if result is not None else None
            claims = self._matching_claims(
                spec,
                ("分部", "主营", "业务", "产品", "收入结构", "收入占比", "客户"),
            )
            return self._claim_stage_execution(
                result,
                spec,
                claims,
                payload_key="segments",
                degrade_reason="未形成分部或业务披露",
            )

        def prior_period_comparison(
            result: AskResult | None,
            _artifacts: tuple[StageArtifact, ...],
        ) -> StageExecution:
            spec = result.answer_spec if result is not None else None
            claims = self._matching_claims(
                spec,
                ("同比", "环比", "上期", "去年", "增长", "下降", "改善", "恶化", "变化"),
            )
            return self._claim_stage_execution(
                result,
                spec,
                claims,
                payload_key="comparisons",
                degrade_reason="未形成可回查的前期比较",
            )

        return {
            "report_period": self._stage_adapter(
                context,
                envelope,
                "report_period",
                producer="answer_query.report_period",
                artifact_type="ReportPeriodArtifact",
                timeout_seconds=self.config.wiki_rag_timeout,
                on_failure="continue_with_period_gap",
                execute=report_period,
            ),
            "financial_metrics": self._stage_adapter(
                context,
                envelope,
                "financial_metrics",
                producer="answer_spec.financial_metrics",
                artifact_type="FinancialMetricsArtifact",
                timeout_seconds=2,
                on_failure="render_financial_metrics_gap",
                execute=financial_metrics,
            ),
            "segment_disclosure": self._stage_adapter(
                context,
                envelope,
                "segment_disclosure",
                producer="answer_spec.segment_disclosure",
                artifact_type="SegmentDisclosureArtifact",
                timeout_seconds=2,
                on_failure="render_segment_disclosure_gap",
                execute=segment_disclosure,
            ),
            "prior_period_comparison": self._stage_adapter(
                context,
                envelope,
                "prior_period_comparison",
                producer="answer_spec.prior_period_comparison",
                artifact_type="PriorPeriodComparisonArtifact",
                timeout_seconds=2,
                on_failure="render_prior_period_comparison_gap",
                execute=prior_period_comparison,
            ),
        }

    def _news_stage_adapters(
        self,
        context: SkillExecutionContext,
        options: AskOptions,
        envelope: QueryEnvelope,
    ) -> dict[str, StageAdapter]:
        def original_disclosure(
            _result: AskResult | None,
            _artifacts: tuple[StageArtifact, ...],
        ) -> StageExecution:
            result = self._answer_query(options)
            spec = result.answer_spec
            sources = (
                [
                    source.to_dict()
                    for source in spec.sources
                    if source.evidence_id.startswith(("L3", "R", "W"))
                ]
                if spec is not None
                else []
            )
            available = any(
                term in f"{source['source']} {source['detail']}"
                for source in sources
                for term in ("公告", "披露", "政策", "通知", "文件", "原文")
            )
            source_ids = {
                str(source["evidence_id"])
                for source in sources
                if source.get("evidence_id")
            }
            return StageExecution(
                status="completed" if available else "partial",
                payload={
                    "event": envelope.subject or context.query,
                    "sources": sources,
                    "available": available,
                },
                evidence_atom_ids=tuple(
                    atom.atom_id
                    for atom in (
                        answer_model.evidence_atoms_from_answer_spec(spec)
                        if spec is not None
                        else ()
                    )
                    if atom.source_id in source_ids
                ),
                result=result,
                degrade_reason=None if available else "未命中原始披露或政策原文",
            )

        def event_facts(
            result: AskResult | None,
            _artifacts: tuple[StageArtifact, ...],
        ) -> StageExecution:
            spec = result.answer_spec if result is not None else None
            claims = spec.verified_facts if spec is not None else ()
            return self._claim_stage_execution(
                result,
                spec,
                claims,
                payload_key="facts",
                degrade_reason="未形成可核验的事件事实",
            )

        def external_news(
            _result: AskResult | None,
            artifacts: tuple[StageArtifact, ...],
        ) -> StageExecution:
            local_available = any(
                artifact.stage in _EXTERNAL_NEWS_LOCAL_STAGES
                and artifact.payload.get("available") is True
                for artifact in artifacts
            )
            if local_available and not web_research.needs_fresh_web(context.query):
                return StageExecution(
                    status="skipped",
                    payload={
                        "available": False,
                        "items": [],
                        "reason": "本地披露与事件事实已命中，未触发外部检索",
                    },
                )
            search = self._web_search(
                context.query,
                timeout=_EXTERNAL_NEWS_TIMEOUT_SECONDS,
            )
            fetched_at = datetime.date.today().isoformat()
            rows = [
                {
                    "title": item.title,
                    "url": item.url,
                    "snippet": item.snippet,
                    "fetched_at": fetched_at,
                }
                for item in search.items[:4]
            ]
            input_hash = self._stage_input_hash(
                context,
                envelope,
                "external_news",
            )
            available = bool(rows)
            return StageExecution(
                status="completed" if available else "partial",
                payload={
                    "available": available,
                    "items": rows,
                    "provider_trace": search.trace.to_dict(),
                },
                evidence_atom_ids=tuple(
                    self._stage_atom_id("external_news", input_hash, index)
                    for index in range(len(rows))
                ),
                degrade_reason=(
                    None
                    if available
                    else f"外部资讯检索未返回可用来源（{search.trace.status}）"
                ),
            )

        def impact_transmission(
            result: AskResult | None,
            _artifacts: tuple[StageArtifact, ...],
        ) -> StageExecution:
            spec = result.answer_spec if result is not None else None
            claims = self._matching_claims(
                spec,
                ("产业链", "传导", "收入", "利润", "成本", "价格", "产能", "弹性"),
            )
            payload = {
                "claims": [claim.to_dict() for claim in claims],
                "event_brief": (
                    result.event_brief.to_dict()
                    if result is not None and result.event_brief is not None
                    else {}
                ),
            }
            return self._claim_stage_execution(
                result,
                spec,
                claims,
                payload=payload,
                available=bool(
                    claims
                    or (
                        result is not None
                        and result.event_brief is not None
                    )
                ),
                degrade_reason="未形成事件到财务科目的影响传导",
            )

        def substitutes_and_harmed_directions(
            result: AskResult | None,
            _artifacts: tuple[StageArtifact, ...],
        ) -> StageExecution:
            spec = result.answer_spec if result is not None else None
            claims = self._matching_claims(
                spec,
                ("替代", "受损", "竞争", "一阶", "二阶", "错杀", "误分类", "反证"),
                include_risks=True,
            )
            return self._claim_stage_execution(
                result,
                spec,
                claims,
                payload_key="directions",
                degrade_reason="未形成受益、替代与受损方向",
            )

        return {
            "original_disclosure": self._stage_adapter(
                context,
                envelope,
                "original_disclosure",
                producer="answer_query.original_disclosure",
                artifact_type="OriginalDisclosureArtifact",
                timeout_seconds=self.config.wiki_rag_timeout,
                on_failure="continue_as_unverified_event",
                execute=original_disclosure,
            ),
            "event_facts": self._stage_adapter(
                context,
                envelope,
                "event_facts",
                producer="answer_spec.event_facts",
                artifact_type="EventFactsArtifact",
                timeout_seconds=2,
                on_failure="render_event_fact_gap",
                execute=event_facts,
            ),
            "external_news": self._stage_adapter(
                context,
                envelope,
                "external_news",
                producer="web_research.external_news",
                artifact_type="ExternalNewsArtifact",
                timeout_seconds=_EXTERNAL_NEWS_TIMEOUT_SECONDS,
                on_failure="continue_without_external_news",
                required_output=False,
                execute=external_news,
            ),
            "impact_transmission": self._stage_adapter(
                context,
                envelope,
                "impact_transmission",
                producer="event_transmission.impact",
                artifact_type="ImpactTransmissionArtifact",
                timeout_seconds=2,
                on_failure="render_impact_transmission_gap",
                execute=impact_transmission,
            ),
            "substitutes_and_harmed_directions": self._stage_adapter(
                context,
                envelope,
                "substitutes_and_harmed_directions",
                producer="event_transmission.directions",
                artifact_type="ImpactDirectionsArtifact",
                timeout_seconds=2,
                on_failure="render_direction_gap",
                execute=substitutes_and_harmed_directions,
            ),
        }

    @staticmethod
    def _all_claims(
        spec: answer_model.AnswerSpec | None,
    ) -> tuple[answer_model.Claim, ...]:
        if spec is None:
            return ()
        return (
            *spec.summary,
            *spec.verified_facts,
            *spec.counter_evidence,
            *spec.gaps,
            *spec.triggers,
        )

    @classmethod
    def _matching_claims(
        cls,
        spec: answer_model.AnswerSpec | None,
        terms: tuple[str, ...],
        *,
        include_risks: bool = False,
    ) -> tuple[answer_model.Claim, ...]:
        if spec is None:
            return ()
        candidates = (
            cls._all_claims(spec)
            if include_risks
            else (*spec.summary, *spec.verified_facts, *spec.triggers)
        )
        return tuple(
            dict.fromkeys(
                claim
                for claim in candidates
                if any(term in claim.text for term in terms)
            )
        )

    @staticmethod
    def _company_claims(
        spec: answer_model.AnswerSpec | None,
    ) -> tuple[answer_model.Claim, ...]:
        if spec is None:
            return ()
        company_claims = tuple(
            claim
            for company in spec.company_table
            for claim in company.claims
        )
        return tuple(
            dict.fromkeys(company_claims or spec.verified_facts)
        )

    @staticmethod
    def _claim_atom_ids(
        spec: answer_model.AnswerSpec | None,
        claims: tuple[answer_model.Claim, ...],
    ) -> tuple[str, ...]:
        if spec is None or not claims:
            return ()
        claim_ids = {claim.claim_id for claim in claims}
        return tuple(
            atom.atom_id
            for atom in answer_model.evidence_atoms_from_answer_spec(spec)
            if atom.provenance.get("claim_id") in claim_ids
        )

    @classmethod
    def _claim_stage_execution(
        cls,
        result: AskResult | None,
        spec: answer_model.AnswerSpec | None,
        claims: tuple[answer_model.Claim, ...],
        *,
        payload_key: str = "claims",
        payload: dict[str, object] | None = None,
        available: bool | None = None,
        degrade_reason: str,
    ) -> StageExecution:
        is_available = bool(claims) if available is None else available
        stage_payload = (
            payload
            if payload is not None
            else {payload_key: [claim.to_dict() for claim in claims]}
        )
        stage_payload["available"] = is_available
        return StageExecution(
            status="completed" if is_available else "partial",
            payload=stage_payload,
            evidence_atom_ids=cls._claim_atom_ids(spec, claims),
            result=result,
            degrade_reason=None if is_available else degrade_reason,
        )

    def _theme_stage_adapters(
        self,
        context: SkillExecutionContext,
        options: AskOptions,
        envelope: QueryEnvelope,
    ) -> dict[str, StageAdapter]:
        required_outputs = set(envelope.required_outputs)
        subject = envelope.subject or context.query
        stage_hashes = {
            stage: self._stage_input_hash(context, envelope, stage)
            for stage in OWNER_WORKFLOW_SPECS[
                self.config.skill_id
            ].retrieval_stages
        }
        research_spec = answer_model.resolve_theme_research_spec(
            context.query,
            envelope.subject,
        )

        def adapter(
            stage: str,
            *,
            producer: str,
            artifact_type: str,
            required_output: bool,
            timeout_seconds: float,
            on_failure: str,
            execute: Callable[
                [AskResult | None, tuple[StageArtifact, ...]],
                StageExecution,
            ],
        ) -> StageAdapter:
            return StageAdapter(
                producer=producer,
                input_hash=stage_hashes[stage],
                artifact_type=artifact_type,
                required_output=required_output,
                timeout_seconds=timeout_seconds,
                on_failure=on_failure,
                execute=execute,
            )

        def definition(
            _result: AskResult | None,
            _artifacts: tuple[StageArtifact, ...],
        ) -> StageExecution:
            available = bool(research_spec.definition)
            reason = None if available else "题材定义缺失"
            return StageExecution(
                status="completed" if available else "partial",
                payload={
                    "theme": research_spec.theme,
                    "definition": research_spec.definition,
                    "available": available,
                },
                degrade_reason=reason,
            )

        def chain_stages(
            _result: AskResult | None,
            _artifacts: tuple[StageArtifact, ...],
        ) -> StageExecution:
            available = bool(research_spec.chain_stages)
            reason = None if available else "产业链阶段缺失"
            return StageExecution(
                status="completed" if available else "partial",
                payload={
                    "theme": research_spec.theme,
                    "chain_stages": list(research_spec.chain_stages),
                    "company_scope": research_spec.company_scope,
                    "available": available,
                },
                degrade_reason=reason,
            )

        def company_mapping(
            _result: AskResult | None,
            _artifacts: tuple[StageArtifact, ...],
        ) -> StageExecution:
            result = self._answer_query(options)
            spec = result.answer_spec
            if spec is None:
                return StageExecution(
                    status="partial",
                    payload={
                        "theme": subject,
                        "companies": [],
                        "available": False,
                    },
                    result=result,
                    degrade_reason="公司映射未形成 AnswerSpec",
                )
            atoms = answer_model.evidence_atoms_from_answer_spec(spec)
            companies = [
                {
                    "company": company.company,
                    "ticker": company.ticker,
                    "tier": company.tier.value,
                    "directness": company.directness,
                    "evidence_gaps": list(company.evidence_gaps),
                }
                for company in spec.company_table
            ]
            return StageExecution(
                status="completed" if companies else "partial",
                payload={
                    "theme": spec.research_spec.theme,
                    "companies": companies,
                    "available": bool(companies),
                },
                evidence_atom_ids=tuple(atom.atom_id for atom in atoms),
                result=result,
                degrade_reason=(
                    None if companies else "未形成达到展示门槛的公司映射"
                ),
            )

        def market_lifecycle(
            result: AskResult | None,
            _artifacts: tuple[StageArtifact, ...],
        ) -> StageExecution:
            if envelope.time_horizon == "unspecified":
                return StageExecution(
                    status="skipped",
                    payload={"available": False, "reason": "未请求中期时间尺度"},
                )
            artifact = load_midterm_trend_artifact(
                context.query,
                envelope.subject,
                options.market_db_path,
            )
            atoms = tuple(
                self._stage_atom_id(
                    "market_lifecycle",
                    stage_hashes["market_lifecycle"],
                    index,
                )
                for index, _trend in enumerate(artifact.trends)
            )
            return StageExecution(
                status="completed" if artifact.available else "partial",
                payload=artifact.to_payload(),
                evidence_atom_ids=atoms,
                degrade_reason=artifact.degrade_reason,
            )

        def historical_analogs(
            result: AskResult | None,
            _artifacts: tuple[StageArtifact, ...],
        ) -> StageExecution:
            if "historical_analogs" not in required_outputs:
                return StageExecution(
                    status="skipped",
                    payload={"available": False, "reason": "未请求历史类比"},
                )
            artifact = load_historical_analog_artifact(
                context.query,
                envelope.subject,
                options.market_db_path,
            )
            analog_count = sum(
                len(theme.get("analogs") or ())
                for theme in artifact.themes
            )
            atoms = tuple(
                self._stage_atom_id(
                    "historical_analogs",
                    stage_hashes["historical_analogs"],
                    index,
                )
                for index in range(analog_count)
            )
            return StageExecution(
                status="completed" if artifact.available else "partial",
                payload=artifact.to_payload(),
                evidence_atom_ids=atoms,
                degrade_reason=artifact.degrade_reason,
            )

        def scenario_tree(
            result: AskResult | None,
            artifacts: tuple[StageArtifact, ...],
        ) -> StageExecution:
            if "scenario_tree" not in required_outputs:
                return StageExecution(
                    status="skipped",
                    payload={"available": False, "reason": "未请求情景树"},
                )
            spec = result.answer_spec if result is not None else None
            verified_facts = (
                *self._claim_dicts(
                    spec.verified_facts if spec is not None else ()
                ),
                *self._artifact_scenario_facts(artifacts),
            )
            artifact = build_scenario_tree_artifact(
                theme=(
                    spec.research_spec.theme
                    if spec is not None
                    else research_spec.theme
                ),
                horizon=envelope.time_horizon,
                verified_facts=verified_facts,
                triggers=self._claim_dicts(
                    spec.triggers if spec is not None else ()
                ),
                counterevidence=self._claim_dicts(
                    spec.counter_evidence if spec is not None else ()
                ),
                gaps=self._claim_dicts(spec.gaps if spec is not None else ()),
            )
            atoms = tuple(
                dict.fromkeys(
                    (
                        *self._evidence_atoms(result),
                        *(
                            evidence_id
                            for fact in verified_facts
                            for evidence_id in fact.get("evidence_ids", ())
                            if isinstance(evidence_id, str)
                        ),
                    )
                )
            )
            return StageExecution(
                status=(
                    "completed"
                    if artifact.available and artifact.degrade_reason is None
                    else "partial"
                ),
                payload=artifact.to_payload(),
                evidence_atom_ids=atoms,
                degrade_reason=artifact.degrade_reason,
            )

        def counterevidence(
            result: AskResult | None,
            artifacts: tuple[StageArtifact, ...],
        ) -> StageExecution:
            spec = result.answer_spec if result is not None else None
            scenario_upgrade, scenario_downgrade = (
                self._scenario_conditions(artifacts)
            )
            upgrade = (
                *self._claim_dicts(
                    spec.triggers if spec is not None else ()
                ),
                *scenario_upgrade,
            )
            downgrade = (
                *self._claim_dicts(
                    (
                        *spec.counter_evidence,
                        *spec.gaps,
                    )
                    if spec is not None
                    else ()
                ),
                *scenario_downgrade,
            )
            available = bool(upgrade or downgrade)
            evidence_atom_ids = tuple(
                dict.fromkeys(
                    (
                        *self._evidence_atoms(result),
                        *(
                            evidence_id
                            for condition in (*upgrade, *downgrade)
                            for evidence_id in condition.get(
                                "evidence_ids",
                                (),
                            )
                            if isinstance(evidence_id, str)
                        ),
                    )
                )
            )
            return StageExecution(
                status="completed" if available else "partial",
                payload={
                    "theme": research_spec.theme,
                    "available": available,
                    "upgrade_conditions": list(upgrade),
                    "downgrade_and_falsification_conditions": list(downgrade),
                },
                evidence_atom_ids=evidence_atom_ids,
                degrade_reason=(
                    None if available else "未形成升级、降级与证伪条件"
                ),
            )

        return {
            "definition": adapter(
                "definition",
                producer="theme_spec.resolve",
                artifact_type="ThemeDefinitionArtifact",
                required_output=True,
                timeout_seconds=2,
                on_failure="continue_with_definition_gap",
                execute=definition,
            ),
            "chain_stages": adapter(
                "chain_stages",
                producer="theme_spec.chain",
                artifact_type="ThemeChainArtifact",
                required_output=True,
                timeout_seconds=2,
                on_failure="continue_with_chain_gap",
                execute=chain_stages,
            ),
            "company_mapping": adapter(
                "company_mapping",
                producer="answer_query.company_mapping",
                artifact_type="CompanyMappingArtifact",
                required_output=True,
                timeout_seconds=self.config.wiki_rag_timeout,
                on_failure="continue_without_company_promotion",
                execute=company_mapping,
            ),
            "market_lifecycle": adapter(
                "market_lifecycle",
                producer="market_midterm.D6",
                artifact_type="MidtermTrendArtifact",
                required_output=envelope.time_horizon != "unspecified",
                timeout_seconds=8,
                on_failure="continue_with_market_data_gap",
                execute=market_lifecycle,
            ),
            "historical_analogs": adapter(
                "historical_analogs",
                producer="market_analogs.D8",
                artifact_type="HistoricalAnalogArtifact",
                required_output="historical_analogs" in required_outputs,
                timeout_seconds=8,
                on_failure="render_historical_analog_gap",
                execute=historical_analogs,
            ),
            "scenario_tree": adapter(
                "scenario_tree",
                producer="scenario_tree.deterministic",
                artifact_type="ScenarioTreeArtifact",
                required_output="scenario_tree" in required_outputs,
                timeout_seconds=2,
                on_failure="render_scenario_placeholder",
                execute=scenario_tree,
            ),
            "counterevidence": adapter(
                "counterevidence",
                producer="answer_spec.counterevidence",
                artifact_type="CounterEvidenceArtifact",
                required_output=(
                    "falsification_conditions" in required_outputs
                ),
                timeout_seconds=2,
                on_failure="render_falsification_placeholder",
                execute=counterevidence,
            ),
        }

    @staticmethod
    def _claim_dicts(
        claims: tuple[answer_model.Claim, ...],
    ) -> tuple[dict[str, object], ...]:
        return tuple(claim.to_dict() for claim in claims)

    @staticmethod
    def _artifact_scenario_facts(
        artifacts: tuple[StageArtifact, ...],
    ) -> tuple[dict[str, object], ...]:
        facts: list[dict[str, object]] = []
        for artifact in artifacts:
            if artifact.stage == "market_lifecycle":
                rows = artifact.payload.get("trends")
                if not isinstance(rows, list):
                    continue
                for index, row in enumerate(rows):
                    if not isinstance(row, dict):
                        continue
                    evidence_ids = (
                        (artifact.evidence_atom_ids[index],)
                        if index < len(artifact.evidence_atom_ids)
                        else ()
                    )
                    facts.append(
                        {
                            "text": (
                                f"{row.get('theme', '题材')}中期趋势覆盖"
                                f"{row.get('days', '未知')}个交易日，"
                                f"双红{row.get('double_red_days', '未知')}天"
                            ),
                            "evidence_ids": evidence_ids,
                            "status": "verified",
                        }
                    )
            elif artifact.stage == "historical_analogs":
                themes = artifact.payload.get("themes")
                if not isinstance(themes, list):
                    continue
                atom_index = 0
                for theme in themes:
                    if not isinstance(theme, dict):
                        continue
                    analogs = theme.get("analogs")
                    if not isinstance(analogs, list):
                        continue
                    for analog in analogs:
                        if not isinstance(analog, dict):
                            continue
                        evidence_ids = (
                            (artifact.evidence_atom_ids[atom_index],)
                            if atom_index < len(artifact.evidence_atom_ids)
                            else ()
                        )
                        atom_index += 1
                        facts.append(
                            {
                                "text": (
                                    f"{theme.get('theme', '题材')}存在历史类似窗口"
                                    f"{analog.get('start_date', '未知')}至"
                                    f"{analog.get('end_date', '未知')}"
                                ),
                                "evidence_ids": evidence_ids,
                                "status": "verified",
                            }
                        )
        return tuple(facts)

    @staticmethod
    def _scenario_conditions(
        artifacts: tuple[StageArtifact, ...],
    ) -> tuple[
        tuple[dict[str, object], ...],
        tuple[dict[str, object], ...],
    ]:
        scenario = next(
            (
                artifact
                for artifact in artifacts
                if artifact.stage == "scenario_tree"
            ),
            None,
        )
        if scenario is None:
            return (), ()
        branches = scenario.payload.get("branches")
        if not isinstance(branches, list):
            return (), ()
        upgrade: list[dict[str, object]] = []
        downgrade: list[dict[str, object]] = []
        for branch in branches:
            if not isinstance(branch, dict):
                continue
            branch_id = branch.get("branch_id")
            target = (
                upgrade
                if branch_id == "upgrade"
                else downgrade
                if branch_id == "downgrade"
                else None
            )
            if target is None:
                continue
            evidence_ids = tuple(
                evidence_id
                for evidence_id in branch.get("evidence_ids", ())
                if isinstance(evidence_id, str)
            )
            for trigger in branch.get("triggers", ()):
                if isinstance(trigger, str) and trigger.strip():
                    target.append(
                        {
                            "text": trigger.strip(),
                            "evidence_ids": evidence_ids,
                        }
                    )
        return tuple(upgrade), tuple(downgrade)

    @staticmethod
    def _evidence_atoms(
        result: AskResult | None,
        source_prefixes: tuple[str, ...] = (),
    ) -> tuple[str, ...]:
        if result is None or result.answer_spec is None:
            return ()
        atoms = answer_model.evidence_atoms_from_answer_spec(result.answer_spec)
        return tuple(
            atom.atom_id
            for atom in atoms
            if not source_prefixes
            or atom.source_id.startswith(source_prefixes)
        )

    @staticmethod
    def _stage_input_hash(
        context: SkillExecutionContext,
        envelope: QueryEnvelope,
        stage: str,
    ) -> str:
        payload = {
            "stage": stage,
            "query": context.query,
            "subject": envelope.subject,
            "horizon": envelope.time_horizon,
            "operators": envelope.operators,
        }
        if stage in {"market_lifecycle", "historical_analogs"}:
            market_db_path = (
                context.repo_root
                / "db"
                / "market_feature_store.duckdb"
            )
            if market_db_path.exists():
                stat = market_db_path.stat()
                payload["market_db"] = {
                    "size": stat.st_size,
                    "mtime_ns": stat.st_mtime_ns,
                }
        return hashlib.sha256(
            json.dumps(
                payload,
                ensure_ascii=False,
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()[:16]

    @staticmethod
    def _stage_atom_id(stage: str, input_hash: str, index: int) -> str:
        digest = hashlib.sha256(
            f"{stage}|{input_hash}|{index}".encode("utf-8")
        ).hexdigest()[:16]
        return f"atom-stage-{digest}"

    def _artifact_evidence_atoms(
        self,
        artifacts: tuple[StageArtifact, ...],
    ) -> tuple[EvidenceAtom, ...]:
        atoms: list[EvidenceAtom] = []
        for artifact in artifacts:
            if artifact.stage == "market_lifecycle":
                rows = artifact.payload.get("trends")
                if not isinstance(rows, list):
                    continue
                for index, row in enumerate(rows):
                    if not isinstance(row, dict):
                        continue
                    atom_id = self._stage_atom_id(
                        artifact.stage,
                        artifact.input_hash,
                        index,
                    )
                    atoms.append(
                        EvidenceAtom(
                            atom_id=atom_id,
                            claim_text=(
                                f"{row.get('theme', '题材')}中期趋势覆盖"
                                f"{row.get('days', '未知')}个交易日，"
                                f"双红{row.get('double_red_days', '未知')}天"
                            ),
                            entity_id=str(row.get("theme") or "") or None,
                            metric="midterm_trend",
                            value=None,
                            unit=None,
                            period=str(row.get("end_date") or "") or None,
                            evidence_tier="L4",
                            source_id="D6",
                            source_date=str(row.get("end_date") or "") or None,
                            provenance={
                                "producer": artifact.producer,
                                "input_hash": artifact.input_hash,
                                "row": row,
                            },
                        )
                    )
            elif artifact.stage == "external_news":
                rows = artifact.payload.get("items")
                if not isinstance(rows, list):
                    continue
                for index, row in enumerate(rows):
                    if not isinstance(row, dict):
                        continue
                    title = str(row.get("title") or "").strip()
                    if not title:
                        continue
                    snippet = str(row.get("snippet") or "").strip()
                    fetched_at = str(row.get("fetched_at") or "") or None
                    atoms.append(
                        EvidenceAtom(
                            atom_id=self._stage_atom_id(
                                artifact.stage,
                                artifact.input_hash,
                                index,
                            ),
                            claim_text=(
                                f"{title}：{snippet or '搜索结果未提供摘要'}"
                            ),
                            entity_id=None,
                            metric="external_web_snapshot",
                            value=None,
                            unit=None,
                            period=fetched_at,
                            evidence_tier="L1",
                            source_id=f"E{index + 1}",
                            source_date=fetched_at,
                            provenance={
                                "producer": artifact.producer,
                                "input_hash": artifact.input_hash,
                                "url": str(row.get("url") or ""),
                                "row": row,
                            },
                        )
                    )
            elif artifact.stage == "historical_analogs":
                themes = artifact.payload.get("themes")
                if not isinstance(themes, list):
                    continue
                index = 0
                for theme in themes:
                    if not isinstance(theme, dict):
                        continue
                    analogs = theme.get("analogs")
                    if not isinstance(analogs, list):
                        continue
                    for analog in analogs:
                        if not isinstance(analog, dict):
                            continue
                        atom_id = self._stage_atom_id(
                            artifact.stage,
                            artifact.input_hash,
                            index,
                        )
                        index += 1
                        atoms.append(
                            EvidenceAtom(
                                atom_id=atom_id,
                                claim_text=(
                                    f"{theme.get('theme', '题材')}历史类似窗口："
                                    f"{analog.get('start_date', '未知')}至"
                                    f"{analog.get('end_date', '未知')}"
                                ),
                                entity_id=str(theme.get("theme") or "") or None,
                                metric="historical_analog",
                                value=analog.get("distance"),
                                unit="shape_distance",
                                period=(
                                    f"{analog.get('start_date', '')}/"
                                    f"{analog.get('end_date', '')}"
                                ),
                                evidence_tier="L4",
                                source_id="D8",
                                source_date=str(analog.get("end_date") or "") or None,
                                provenance={
                                    "producer": artifact.producer,
                                    "input_hash": artifact.input_hash,
                                    "row": analog,
                                },
                            )
                        )
        return tuple(atoms)

    def _has_traceable_verified_fact(
        self,
        spec: answer_model.AnswerSpec,
    ) -> bool:
        source_ids = {
            source.evidence_id
            for source in spec.sources
            if source.evidence_id not in _PRIOR_ONLY_EVIDENCE
        }
        return any(
            claim.status == answer_model.ClaimStatus.VERIFIED
            and any(
                evidence_id in source_ids
                and evidence_id.startswith(self.config.evidence_prefixes)
                for evidence_id in claim.evidence_ids
            )
            for claim in spec.verified_facts
        )

    @staticmethod
    def _modules(result: AskResult) -> list[JsonObject]:
        redacted = redact_json(ask_result_modules(result))
        if not isinstance(redacted, list):
            return []
        return [module for module in redacted if isinstance(module, dict)]

    @staticmethod
    def _citations(result: AskResult) -> list[JsonObject]:
        return [
            {
                "tag": citation.tag,
                "title": citation.source,
                "source": citation.detail,
                "as_of": result.trade_date,
            }
            for citation in result.citations
        ]

    def _store_artifact(
        self,
        context: SkillExecutionContext,
        result: AskResult,
        *,
        citations: list[JsonObject],
        warnings: list[str],
        owned: bool,
        stage_artifacts: list[JsonObject],
        status: SkillResultStatus,
    ) -> str:
        payload: JsonObject = {
            "skill_id": self.skill_id,
            "question_type": self.config.question_type,
            "query": context.query,
            "as_of": result.trade_date,
            "owned": owned,
            "status": status,
            "retrieval_plan": list(self.config.retrieval_plan),
            "output_contract": list(self.config.output_contract),
            "citations": citations,
            "warnings": warnings,
            "stage_artifacts": stage_artifacts,
            "answer_spec": (
                result.answer_spec.to_prompt_block()
                if result.answer_spec is not None
                else None
            ),
        }
        safe_payload = redact_json(payload)
        artifact = context.run_store.add_artifact(
            context.run_id,
            f"{self.skill_id}-skill-result.json",
            json.dumps(safe_payload, ensure_ascii=False, indent=2) + "\n",
            renderer="json",
            title=f"{self.config.title} Skill 原始结果",
        )
        return artifact.path

    def _store_partial_artifact(
        self,
        context: SkillExecutionContext,
        *,
        warnings: list[str],
        stage_artifacts: list[JsonObject],
        contract: SkillAnswerContract | None = None,
        status: SkillResultStatus,
    ) -> str:
        payload: JsonObject = {
            "skill_id": self.skill_id,
            "question_type": self.config.question_type,
            "query": context.query,
            "as_of": None,
            "owned": contract is not None,
            "status": status,
            "retrieval_plan": list(self.config.retrieval_plan),
            "output_contract": list(self.config.output_contract),
            "citations": [],
            "warnings": warnings,
            "stage_artifacts": stage_artifacts,
            "answer_spec": (
                contract.answer_spec.to_prompt_block()
                if contract is not None
                else None
            ),
        }
        artifact = context.run_store.add_artifact(
            context.run_id,
            f"{self.skill_id}-skill-result.json",
            json.dumps(redact_json(payload), ensure_ascii=False, indent=2) + "\n",
            renderer="json",
            title=f"{self.config.title} Skill 部分结果",
        )
        return artifact.path


STOCK_DEEP_DIVE = ResearchOwnerConfig(
    skill_id="stock-deep-dive",
    title="个股深挖",
    question_type="stock_deep_dive",
    retrieval_plan=(
        "锚定公司名称与证券代码，核对当前数据截止日",
        "按公司、代码和产业链别名做窄口径、宽口径与反方检索",
        "核对公司本体、客户订单、产能量产和公告级证据",
        "读取个股相对强度、题材生命周期、同链替代和市场价值",
        "召回用户纠偏与历史回检，但只作为先验，不替代当前事实",
    ),
    output_contract=(
        "先给公司定位和当前核心矛盾",
        "只把可追溯事实写入最强证据，弱线索进入缺口",
        "融合公司本体、市场选择、生命周期、二阶导和反证",
        "结尾给升级、降级和证伪条件，不输出买卖指令",
    ),
    presentation_kind="theme_research",
    evidence_prefixes=("G", "R", "W", "D7", "L3"),
)

THEME_RESEARCH = ResearchOwnerConfig(
    skill_id="theme-research",
    title="题材研究",
    question_type="theme_analysis",
    retrieval_plan=(
        "先定义题材、替代表达和产业链边界",
        "检索概念图谱、公司暴露、研报证据和相邻概念",
        "读取题材强度、涨停扩散、新高集群、容量与边际量",
        "按请求读取多日中期趋势和历史类似窗口",
        "用已绑定证据构造条件情景树，不生成无来源概率",
        "区分领先核心、同步确认、补涨和被抛弃方向",
        "主动检索替代技术、需求证伪和竞争受损线索",
    ),
    output_contract=(
        "先给题材定义、产业链位置和当前阶段",
        "按上游、中游、下游和二阶受益分层",
        "核心公司必须绑定暴露证据，不因概念关联直接升级",
        "历史类比、情景树和证伪区块在缺数时仍显式保留",
        "结尾给信号层缺口、升级、降级和证伪条件",
    ),
    presentation_kind="theme_research",
    evidence_prefixes=("S", "G", "R", "W", "D1", "D4"),
)

NEWS_IMPACT = ResearchOwnerConfig(
    skill_id="news-impact",
    title="消息与公告冲击",
    question_type="news_impact",
    retrieval_plan=(
        "先核对新闻、公告或原文的日期、来源与事实层",
        "检索近期资讯、公司公告、互动与历史相邻事件",
        "映射产业链位置、公司暴露和一阶、二阶传导",
        "检查消息是否已经被盘面交易以及潜在兑现分歧",
        "主动检索替代、竞争、受损和不及预期线索",
    ),
    output_contract=(
        "先区分新事实、旧事实、观点和传闻",
        "再写需求变化到财务科目和公司弹性的传导链",
        "明确一阶受益、二阶受益、替代和受损方向",
        "缺原文或公告时只披露缺口，不根据标题扩写",
    ),
    presentation_kind="theme_research",
    evidence_prefixes=("R", "W", "L3"),
)

FINANCIAL_ANALYSIS = ResearchOwnerConfig(
    skill_id="financial-analysis",
    title="财报分析",
    question_type="financial_analysis",
    retrieval_plan=(
        "锚定公司与报告期，确认披露日期和累计或单季口径",
        "读取逐季营收、归母净利、毛利率、净利率及同比方向",
        "核对定期报告、业绩公告、订单、产能和客户证据",
        "比较同业兑现节奏，并检查业绩是否已被市场定价",
        "召回历史判断与纠偏，但由当前财务和公告事实终审",
    ),
    output_contract=(
        "先给业绩兑现结论和最关键的增长质量变化",
        "拆分营收、利润、利润率、异常项和持续性",
        "明确报告期、数据口径、证据来源和缺失项",
        "结尾给下一报告期的升级、降级和证伪条件",
    ),
    presentation_kind="base_finance",
    evidence_prefixes=("R", "D7", "L3"),
)
