from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, replace

from intelligence.api.structured_reports import ask_result_modules
from intelligence.services import answer_model
from intelligence.services.ask import AskOptions, AskResult, answer_query
from intelligence.workbench_skills.contracts import (
    JsonObject,
    SkillAnswerContract,
    SkillExecutionContext,
    SkillOutput,
    redact_json,
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
        llm_timeout = (
            max(
                1,
                int(context.execution_budget.child_timeout(30, reserve=3) / 2),
            )
            if context.execution_budget is not None
            else 30
        )
        if context.runtime_inputs is not None:
            market_db_path = context.runtime_inputs.market_db_path
            exports_dir = context.runtime_inputs.exports_dir
            kb_wiki = context.runtime_inputs.knowledge_wiki
            wiki_rag_index_dir = context.runtime_inputs.vector_index_dir
        else:
            market_db_path = (
                context.repo_root / "db" / "market_feature_store.duckdb"
            )
            exports_dir = context.repo_root / "market_feature_store" / "exports"
            kb_wiki = context.repo_root / "wiki"
            wiki_rag_index_dir = context.repo_root / ".rag_index"
        result = self._answer_query(
            AskOptions(
                query=context.query,
                user=context.user_id,
                compose=True,
                synthesize=False,
                compose_self_review=False,
                compose_revise_on_warn=False,
                market_db_path=market_db_path,
                exports_dir=exports_dir,
                kb_wiki=kb_wiki,
                wiki_rag_index_dir=wiki_rag_index_dir,
                conversation_context=context.conversation_context,
                include_memory_block=True,
                include_recall_block=True,
                question_type_override=self.config.question_type,
                execution_budget=context.execution_budget,
                progress_callback=context.progress_callback,
                llm_timeout=llm_timeout,
            )
        )
        retrieved_modules = self._modules(result)
        retrieved_citations = self._citations(result)
        warnings = list(result.warnings)
        contract = self._answer_contract(result)
        if contract is None:
            warnings.append("专项检索未形成可追溯事实，已回退基础金融回答。")
        raw_result_ref = self._store_artifact(
            context,
            result,
            citations=retrieved_citations,
            warnings=warnings,
            owned=contract is not None,
        )
        return SkillOutput(
            skill_id=self.skill_id,
            modules=retrieved_modules if contract is not None else [],
            citations=retrieved_citations if contract is not None else [],
            warnings=warnings,
            as_of=result.trade_date,
            raw_result_ref=raw_result_ref,
            answer_contract=contract,
        )

    def _answer_contract(
        self,
        result: AskResult,
    ) -> SkillAnswerContract | None:
        spec = result.answer_spec
        if spec is None or not self._has_traceable_verified_fact(spec):
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
        )
        owned_spec = answer_model.finalize_answer_spec(owned_spec)
        return SkillAnswerContract(
            retrieval_plan=self.config.retrieval_plan,
            output_contract=self.config.output_contract,
            answer_spec=owned_spec,
            question_type=self.config.question_type,
        )

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
        "区分领先核心、同步确认、补涨和被抛弃方向",
        "主动检索替代技术、需求证伪和竞争受损线索",
    ),
    output_contract=(
        "先给题材定义、产业链位置和当前阶段",
        "按上游、中游、下游和二阶受益分层",
        "核心公司必须绑定暴露证据，不因概念关联直接升级",
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
