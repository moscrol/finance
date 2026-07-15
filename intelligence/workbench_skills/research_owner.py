from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import asdict, dataclass, replace

from intelligence.api.structured_reports import ask_result_modules
from intelligence.services import answer_model
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
    redact_json,
)
from intelligence.workbench_skills.owner_dag import (
    StageAdapter,
    StageExecution,
    execute_owner_dag,
)

AnswerQuery = Callable[[AskOptions], AskResult]

_PRIOR_ONLY_EVIDENCE = frozenset({"M", "ONTOLOGY", "V"})


@dataclass(frozen=True)
class ResearchOwnerConfig:
    skill_id: str
    title: str
    question_type: str
    retrieval_plan: tuple[str, ...]
    output_contract: tuple[str, ...]
    presentation_kind: str
    evidence_prefixes: tuple[str, ...]
    wiki_rag_timeout: int = 20
    module_timeout: int = 20
    use_modules: bool = True


class ResearchOwnerSkill:
    def __init__(
        self,
        config: ResearchOwnerConfig,
        *,
        answer_query_fn: AnswerQuery = answer_query,
    ) -> None:
        self.config = config
        self.skill_id = config.skill_id
        self._answer_query = answer_query_fn

    def execute(self, context: SkillExecutionContext) -> SkillOutput:
        options = AskOptions(
                query=context.query,
                user=context.user_id,
                compose=True,
                synthesize=False,
                compose_self_review=False,
                compose_revise_on_warn=False,
                use_modules=self.config.use_modules,
                wiki_rag_timeout=self.config.wiki_rag_timeout,
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
            stage_adapters=(
                self._theme_stage_adapters(context, options, envelope)
                if self.skill_id == "theme-research"
                else None
            ),
        )
        result = dag.result
        stage_artifacts = [asdict(artifact) for artifact in dag.artifacts]
        contract = self._answer_contract(
            result,
            dag.artifacts,
            query=context.query,
            matched_theme=envelope.subject,
        )
        if result is None:
            warnings = list(dag.warnings)
            raw_result_ref = self._store_partial_artifact(
                context,
                warnings=warnings,
                stage_artifacts=stage_artifacts,
                contract=contract,
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
            )
        retrieved_modules = self._modules(result)
        retrieved_citations = self._citations(result)
        warnings = list(dict.fromkeys((*result.warnings, *dag.warnings)))
        if contract is None:
            warnings.append("专项检索未形成可追溯事实，已回退基础金融回答。")
        raw_result_ref = self._store_artifact(
            context,
            result,
            citations=retrieved_citations,
            warnings=warnings,
            owned=contract is not None,
            stage_artifacts=stage_artifacts,
        )
        return SkillOutput(
            skill_id=self.skill_id,
            modules=retrieved_modules if contract is not None else [],
            citations=retrieved_citations if contract is not None else [],
            warnings=warnings,
            as_of=result.trade_date,
            raw_result_ref=raw_result_ref,
            answer_contract=contract,
            stage_artifacts=stage_artifacts,
        )

    def _answer_contract(
        self,
        result: AskResult | None,
        stage_artifacts: tuple[StageArtifact, ...] = (),
        *,
        query: str = "",
        matched_theme: str | None = None,
    ) -> SkillAnswerContract | None:
        spec = result.answer_spec if result is not None else None
        if (
            spec is None
            and self.skill_id == "theme-research"
            and self._preserves_required_theme_outputs(stage_artifacts)
        ):
            spec = self._theme_fallback_answer_spec(
                query=query,
                matched_theme=matched_theme,
                stage_artifacts=stage_artifacts,
            )
        if spec is None:
            return None
        has_traceable_fact = self._has_traceable_verified_fact(spec)
        preserves_required_theme_outputs = self._preserves_required_theme_outputs(
            stage_artifacts
        )
        if not has_traceable_fact and not preserves_required_theme_outputs:
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
        owned_spec = answer_model.finalize_answer_spec(owned_spec)
        return SkillAnswerContract(
            retrieval_plan=self.config.retrieval_plan,
            output_contract=self.config.output_contract,
            answer_spec=owned_spec,
            question_type=self.config.question_type,
        )

    def _theme_fallback_answer_spec(
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
                claim_id="theme-fallback:summary",
                text=(
                    "公司映射或回答模型未在阶段时限内完成；"
                    "仅展示已完成的市场事实、历史类比和条件情景。"
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
                "下一验证窗口复核 D6、D8 与情景触发条件。",
            ),
            sources=sources,
            system_notices=(
                "能力守恒降级：检索或回答模型失败不删除必需研究区块。",
            ),
            prompt_constraints=self.config.output_contract,
            presentation_kind=self.config.presentation_kind,
            presentation_title=self.config.title,
            research_artifacts=stage_artifacts,
            research_evidence_atoms=self._artifact_evidence_atoms(
                stage_artifacts
            ),
        )

    def _preserves_required_theme_outputs(
        self,
        stage_artifacts: tuple[StageArtifact, ...],
    ) -> bool:
        return self.skill_id == "theme-research" and any(
            artifact.required_output
            and artifact.stage
            in {
                "historical_analogs",
                "scenario_tree",
                "counterevidence",
            }
            for artifact in stage_artifacts
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
    ) -> str:
        payload: JsonObject = {
            "skill_id": self.skill_id,
            "question_type": self.config.question_type,
            "query": context.query,
            "as_of": result.trade_date,
            "owned": owned,
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
    ) -> str:
        payload: JsonObject = {
            "skill_id": self.skill_id,
            "question_type": self.config.question_type,
            "query": context.query,
            "as_of": None,
            "owned": contract is not None,
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
