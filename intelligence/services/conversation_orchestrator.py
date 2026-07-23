from __future__ import annotations

import contextvars
import json
import os
import re
import time
from collections.abc import Callable, Sequence
from concurrent.futures import (
    Future,
    ThreadPoolExecutor,
    TimeoutError as FuturesTimeoutError,
)
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from threading import Event, Lock, Thread
from typing import Protocol

from intelligence.api.structured_reports import (
    ask_result_modules,
    complete_report,
    new_structured_report,
    render_daily_review_answer,
    upsert_report_module,
)
from intelligence.services import answer_model, followups as followups_svc
from intelligence.services import task_fulfillment
from intelligence.services import run_store as rs
from intelligence.services.ask import (
    AskOptions,
    AskResult,
    Citation,
    PreparedAnswer,
    answer_query,
    prepare_existing_answer,
    render_conversation_answer,
    synthesize_prepared_answer,
    synthesize_shadow_grounded_answer,
)
from intelligence.services.answer_stream import AnswerSnapshot
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.answer_orchestrator import (
    QUESTION_CONCEPT_DEFINITION,
    QUESTION_GENERAL,
    QUESTION_METHODOLOGY,
    QUESTION_MARKET_REVIEW,
    QUESTION_MARKET_CAUSE,
    QUESTION_MARKET_FORECAST,
    QUESTION_EXTERNAL_MARKET,
    QUESTION_MARKET_TECHNICAL,
    plan_answer_question,
)
from intelligence.services.conversation_store import (
    Conversation,
    ConversationStore,
    Message,
)
from intelligence.services.continuous_turn_adapter import ContinuousTurnResult
from intelligence.services import llm_refine
from intelligence.services import query_ledger
from intelligence.services.llm_refine import LLMStreamCancelled
from intelligence.services.lane_generation import (
    LaneAnswer,
    generate_lane_answer,
    knowledge_evidence,
    render_knowledge_fallback,
)
from intelligence.services import perspective_lab
from intelligence.services.query_understanding import (
    envelope_from_task_frame,
    project_task_frame,
    understand_query,
)
from intelligence.services.evidence_capabilities import resolve_evidence_plan
from intelligence.services.research_policy import (
    ResearchExecutionBudget,
    ResearchExecutionPolicy,
)
from intelligence.services.research_contract import (
    OWNER_WORKFLOW_SPECS,
    ResearchDeadline,
    ResearchPolicy,
    ResearchPlan,
    RequiredOutput,
    ResearchTaskContract,
    TurnIntent,
    build_turn_intent,
    contextualize_intent_query,
    is_contextual_follow_up,
)
from intelligence.services.run_store import RunStore, redact, redact_value
from intelligence.paths import default_paths
from intelligence.services.turn_control_core import (
    TurnControlResult,
    project_turn_decision,
)
from intelligence.services.turn_controller import TurnDecision, decide_turn
from intelligence.services.task_frame import TaskFrame, build_task_frame
from intelligence import userspace
from intelligence.workbench_skills.contracts import (
    SkillExecutionContext,
    SkillOutput,
)
from intelligence.workbench_skills.registry import (
    SkillRegistry,
    builtin_skill_registry,
)
from intelligence.workbench_skills.router import (
    SkillMode,
    SkillRouteResult,
    route_skills,
)
from intelligence.services.query_resolution import is_contextual_reference

RECENT_MESSAGE_LIMIT = 6
SUMMARY_CHAR_LIMIT = 2400
_SKILL_POOL_WORKERS = 3


class ContinuousTurnHandler(Protocol):
    def handle(
        self,
        *,
        frame: TaskFrame,
        control: TurnControlResult,
    ) -> ContinuousTurnResult: ...


def _sanitize_market_cause_answer_text(text: str, query: str) -> str:
    """原因归因题不夹带用户未询问的交易策略段。"""
    if not re.search(
        r"(?:本周|这一周|这周|近一周|过去一周).{0,20}(?:行情|大盘|市场).{0,20}"
        r"(?:下跌|走弱).{0,20}(?:原因|为什么|驱动|归因)",
        query,
    ):
        return text
    forbidden = (
        "操作层面",
        "仓位",
        "买入",
        "卖出",
        "防御和观察",
        "宜以防御",
        "博弈单边反转",
        "非投资建议",
    )
    lines = [
        line
        for line in text.splitlines()
        if not any(term in line for term in forbidden)
    ]
    return "\n".join(lines).strip()


def _build_generic_research_contract(
    query: str,
    *,
    task_id: str,
    turn_intent: TurnIntent,
    task_frame: TaskFrame | None = None,
) -> ResearchTaskContract:
    """为未命中专项 Owner 的问题生成保守、可审计的任务契约。"""

    semantic_query = task_frame.raw_question if task_frame is not None else query
    normalized = semantic_query.replace(" ", "")
    tier = (
        "deep"
        if any(term in normalized for term in ("深挖", "深入", "系统研究"))
        else "quick"
        if any(term in normalized for term in ("简单说", "快答", "一句话"))
        else "standard"
    )
    is_market_cause = turn_intent.question_type == QUESTION_MARKET_CAUSE
    is_market_forecast = turn_intent.question_type == QUESTION_MARKET_FORECAST
    is_event_forecast = turn_intent.question_type == "event_forecast"
    is_comparison = turn_intent.question_type == "comparison"
    is_fact_check = turn_intent.question_type == "fact_check"
    is_relation_query = bool(
        {"relation", "company_mapping"}.intersection(turn_intent.operators)
    )
    # “甲和乙是否合作/供货”仍走 L3 hard-fact 核验；“甲的客户有哪些/客户的
    # 竞争对手是谁”是关系地图任务，不能被普通个股事实契约吞掉。
    is_relation_fact_check = is_relation_query and bool(
        re.search(
            r"(?:是否|有无|有没有|能否|是不是|是否已经).{0,16}"
            r"(?:合作|供货|供应(?:商)?|订单|合同|认证|定点|客户关系)"
            r"|(?:合作|供货|供应(?:商)?|订单|合同|认证|定点|客户关系).{0,8}"
            r"(?:是否|有无|有没有|能否|吗|么|是不是)",
            normalized,
        )
    )
    is_relation_map = (
        is_relation_query
        and not is_relation_fact_check
        and bool(
            re.search(
                r"(?:哪些|有谁|是谁|名单|竞争对手|合作方|供应商|客户)",
                normalized,
            )
        )
    )
    is_general_fact_check = (
        is_fact_check and not is_relation_fact_check and not is_relation_map
    )
    is_methodology = bool(
        re.search(
            r"(?:怎么做|如何做|为什么会|原理|架构|编排|RAG|BM25|Agent|模板化|质检)",
            semantic_query,
            re.IGNORECASE,
        )
    )
    evidence_plan = resolve_evidence_plan(
        semantic_query,
        question_type=(
            task_frame.question_type
            if task_frame is not None
            else turn_intent.question_type
        ),
        freshness="current",
    )
    is_current_mainline = (
        evidence_plan.profile == "mainline_current" and not is_methodology
    )
    is_current_market_fact = evidence_plan.profile == "current_market_fact"
    needs_l3 = bool(
        re.search(
            r"(?:客户|合作|订单|合同|中标|认证|定点|送样|导入|量产|供货|出货|收入占比|供应商)",
            semantic_query,
        )
    )
    if is_current_mainline:
        required_outputs = (
            RequiredOutput(
                "direct_assessment",
                "直接回答当前市场主线，并区分增量启动、持续主线和分歧修复",
                ("market_data", "mainline_context"),
                True,
            ),
            RequiredOutput(
                "supporting_evidence",
                "列出同日市场总览与主线结构依据",
                ("market_data", "mainline_context"),
                True,
            ),
        )
    elif is_current_market_fact:
        required_outputs = (
            RequiredOutput(
                "direct_assessment",
                "先解释问题中的指标定义，再直接回答当前市场事实",
                ("mainline_context",),
                True,
            ),
            RequiredOutput(
                "supporting_evidence",
                "给出定义来源和同日结构化事实依据",
                ("mainline_context",),
                True,
            ),
        )
    elif is_general_fact_check:
        required_outputs = (
            RequiredOutput(
                "direct_assessment",
                "先核对用户问题中的前提，再给出对后续影响的直接判断",
                ("web_search", "news_search", "kb_search", "evidence_lookup"),
                True,
            ),
            RequiredOutput(
                "premise_check",
                "用当前可回查来源确认、修正或否定问题前提",
                ("web_search", "news_search", "kb_search", "evidence_lookup"),
                True,
            ),
            RequiredOutput(
                "supporting_evidence",
                "至少一条能直接核对前提的时效来源",
                ("web_search", "news_search", "kb_search", "evidence_lookup"),
                True,
            ),
        )
    elif is_relation_map:
        required_outputs = (
            RequiredOutput(
                "direct_assessment",
                "直接回答关系问题，并区分已核验关系、候选关系和未找到关系边",
                (
                    "graph_lookup",
                    "evidence_lookup",
                    "kb_search",
                    "web_search",
                    "news_search",
                ),
                True,
            ),
            RequiredOutput(
                "relation_map",
                "给出与问题方向一致的关系边、关系角色或明确的缺边结论",
                (
                    "graph_lookup",
                    "evidence_lookup",
                    "kb_search",
                    "web_search",
                    "news_search",
                ),
                True,
            ),
            RequiredOutput(
                "supporting_evidence",
                "至少一条可回查的关系来源或明确的缺口证据",
                (
                    "graph_lookup",
                    "evidence_lookup",
                    "kb_search",
                    "web_search",
                    "news_search",
                ),
                True,
            ),
        )
    elif is_market_forecast:
        # 预测不是一句“涨/跌”。显式登记两种情景和失效条件，避免只拿到
        # 一个方向的证据就被 soft planner 误判为完成。
        required_outputs = (
            RequiredOutput(
                "direct_assessment",
                "针对预测窗口的直接判断，并明确当前基准情景",
                ("market_data", "web_search", "news_search"),
                True,
            ),
            RequiredOutput(
                "rebound_case",
                "反弹情景：触发条件、支持证据与观察窗口",
                ("market_data", "web_search", "news_search"),
                True,
            ),
            RequiredOutput(
                "decline_case",
                "继续下跌情景：触发条件、支持证据与观察窗口",
                ("market_data", "web_search", "news_search"),
                True,
            ),
            RequiredOutput(
                "invalidation",
                "使当前判断失效的反证或关键监测指标",
                ("market_data", "web_search", "news_search"),
                True,
            ),
            RequiredOutput(
                "supporting_evidence",
                "至少一条可回查的当前盘面或外部来源",
                ("market_data", "web_search", "news_search"),
                True,
            ),
        )
    elif is_event_forecast:
        # 事件题不是盘面涨跌题：必须先核对事件本身，再说明传导方向、谁会
        # 受益/受损，以及在哪个窗口用什么新事实验证或证伪，不能套用反弹/下跌
        # 的市场情景模板。
        required_outputs = (
            RequiredOutput(
                "direct_assessment",
                "针对事件可能性或影响窗口的直接判断，并明确条件边界",
                (
                    "web_search",
                    "news_search",
                    "kb_search",
                    "graph_lookup",
                    "evidence_lookup",
                ),
                True,
            ),
            RequiredOutput(
                "event_facts",
                "事件已知事实、尚未发生的条件与对应时间窗口",
                ("web_search", "news_search", "kb_search", "evidence_lookup"),
                True,
            ),
            RequiredOutput(
                "event_transmission",
                "事件到行业、公司或资产的传导链，并说明受益/受损方向与边界",
                (
                    "kb_search",
                    "graph_lookup",
                    "evidence_lookup",
                    "web_search",
                    "news_search",
                ),
                True,
            ),
            RequiredOutput(
                "verification_window",
                "验证当前推演所需的新事实、指标或披露，以及观察窗口",
                ("web_search", "news_search", "kb_search", "evidence_lookup"),
                True,
            ),
            RequiredOutput(
                "falsification_window",
                "会证伪当前传导或方向判断的反向事实，以及观察窗口",
                ("web_search", "news_search", "kb_search", "evidence_lookup"),
                True,
            ),
            RequiredOutput(
                "supporting_evidence",
                "至少一条支持事件事实或传导链的可回查来源",
                (
                    "web_search",
                    "news_search",
                    "kb_search",
                    "graph_lookup",
                    "evidence_lookup",
                ),
                True,
            ),
            RequiredOutput(
                "counter_evidence",
                "至少一条反证、相反传导方向或明确的证据边界",
                (
                    "web_search",
                    "news_search",
                    "kb_search",
                    "graph_lookup",
                    "evidence_lookup",
                ),
                True,
            ),
        )
    elif is_comparison:
        required_outputs = (
            RequiredOutput(
                "direct_assessment",
                "直接给出比较结论和比较维度",
                ("kb_search", "web_search", "news_search", "graph_lookup"),
                True,
            ),
            RequiredOutput(
                "comparison_basis",
                "至少两个可回查的比较事实或指标",
                ("kb_search", "web_search", "news_search", "evidence_lookup"),
                True,
            ),
            RequiredOutput(
                "key_difference",
                "指出决定差异的关键变量及其边界",
                ("kb_search", "web_search", "news_search", "graph_lookup"),
                True,
            ),
            RequiredOutput(
                "supporting_evidence",
                "至少一条可回查来源",
                ("kb_search", "web_search", "news_search", "evidence_lookup"),
                True,
            ),
        )
    elif is_market_cause:
        required_outputs = (
            RequiredOutput(
                "direct_assessment",
                "针对用户问题的直接判断，必须明确回答指定周窗口",
                ("market_data", "web_search", "news_search"),
                True,
            ),
            RequiredOutput(
                "cause_attribution",
                "至少一个由周内市场数据支撑、明确标注为机制判断或已核验原因的主要下跌机制",
                ("market_data",),
                True,
            ),
            RequiredOutput(
                "external_cause_evidence",
                "与该周时间窗口对齐的宏观、政策、外盘或资金事件证据",
                ("web_search", "news_search"),
                True,
            ),
            RequiredOutput(
                "supporting_evidence",
                "至少一条可回查来源",
                ("market_data", "web_search", "news_search", "evidence_lookup"),
                True,
            ),
        )
    else:
        required_outputs = (
            RequiredOutput(
                "direct_assessment",
                "针对用户问题的直接判断",
                (
                    "kb_search",
                    "web_search",
                    "news_search",
                    "graph_lookup",
                    *(("l3_lookup",) if needs_l3 else ()),
                ),
                True,
            ),
            RequiredOutput(
                "supporting_evidence",
                "至少一条可回查来源",
                (
                    "kb_search",
                    "web_search",
                    "news_search",
                    "evidence_lookup",
                    *(("l3_lookup",) if needs_l3 else ()),
                ),
                True,
            ),
            *(
                (
                    RequiredOutput(
                        "customer_validation",
                        "核验是否存在公告、合同、订单、客户认证或官方互动等 L3 证据；缺失时必须明确说尚不能确认",
                        ("l3_lookup",),
                        True,
                    ),
                )
                if needs_l3
                else ()
            ),
        )
    if is_current_mainline:
        capabilities = (
            "market_data",
            "mainline_context",
            "web_search",
            "news_search",
        )
    elif is_current_market_fact:
        capabilities = ("mainline_context", "market_data", "kb_search")
    elif is_general_fact_check:
        capabilities = (
            "web_search",
            "news_search",
            "kb_search",
            "evidence_lookup",
        )
    elif is_relation_map:
        capabilities = (
            "graph_lookup",
            "evidence_lookup",
            "kb_search",
            "web_search",
            "news_search",
        )
    elif is_market_forecast:
        capabilities = ("market_data", "web_search", "news_search")
    elif is_event_forecast:
        capabilities = (
            "web_search",
            "news_search",
            "kb_search",
            "graph_lookup",
            "evidence_lookup",
        )
    elif is_comparison:
        capabilities = (
            "kb_search",
            "web_search",
            "news_search",
            "graph_lookup",
            "evidence_lookup",
        )
    elif is_market_cause:
        capabilities = (
            "market_data",
            "web_search",
            "news_search",
            "kb_search",
            "evidence_lookup",
            *(("l3_lookup",) if needs_l3 else ()),
        )
    else:
        capabilities = (
            "kb_search",
            "web_search",
            "news_search",
            "graph_lookup",
            "evidence_lookup",
            *(("l3_lookup",) if needs_l3 else ()),
        )
    contract_outputs = (
        *required_outputs,
        *(
            ()
            if (
                is_market_forecast
                or is_event_forecast
                or is_comparison
                or is_relation_map
            )
            else (
                RequiredOutput(
                    "counterpoint",
                    "反方或证据边界",
                    ("kb_search", "web_search", "news_search", "market_data"),
                    False,
                ),
            )
        ),
    )
    if task_frame is not None:
        contract_outputs = _merge_frame_outputs(
            contract_outputs,
            task_frame,
            capabilities,
        )
    subject = (
        task_frame.subject if task_frame is not None else turn_intent.primary_subject
    )
    if (is_market_forecast or is_event_forecast) and not subject:
        subject = "A股市场"
    return ResearchTaskContract(
        task_id=task_id,
        question=semantic_query,
        subject=subject,
        subject_kind=(
            task_frame.subject_kind
            if task_frame is not None
            else "market_pattern"
            if is_current_mainline
            or is_current_market_fact
            or is_market_cause
            or is_market_forecast
            else "event"
            if is_event_forecast
            else "company_relation"
            if is_relation_map
            else None
        ),
        question_type=(
            task_frame.question_type
            if task_frame is not None
            else turn_intent.question_type
        ),
        required_outputs=contract_outputs,
        allowed_capabilities=capabilities,
        research_tier=tier,
        presentation_profile=(
            "mainline_current"
            if is_current_mainline
            else "market_fact_current"
            if is_current_market_fact
            else "forecast"
            if is_market_forecast or is_event_forecast
            else "comparison"
            if is_comparison
            else "relation"
            if is_relation_map
            else "causal"
            if is_market_cause
            else "methodology"
            if is_methodology
            else "general"
        ),
        freshness="current",
        timeframe=(
            task_frame.timeframe if task_frame is not None else turn_intent.timeframe
        ),
        evidence_plan=evidence_plan,
        task_frame_hash=(task_frame.task_frame_hash if task_frame is not None else ""),
    )


_TASK_FRAME_OUTPUT_DESCRIPTIONS: dict[str, str] = {
    "current_baseline": "当前基准状态与起点",
    "duration_assessment": "持续时间或观察窗口判断",
    "continuation_conditions": "继续成立或延续的条件",
    "invalidation_conditions": "使当前判断失效的条件",
    "scenario_paths": "条件化情景与演绎路径",
    "chain_mapping": "产业链层级、角色与关键环节",
    "financial_assessment": "公司财务表现的直接判断",
    "metric_evidence": "支撑财务判断的指标证据",
}


def _task_frame_required_output(
    output_id: str,
    *,
    evidence_types: tuple[str, ...] = (),
) -> RequiredOutput:
    return RequiredOutput(
        output_id=output_id,
        description=_TASK_FRAME_OUTPUT_DESCRIPTIONS.get(
            output_id,
            f"TaskFrame 要求的输出：{output_id}",
        ),
        evidence_types=evidence_types,
        required=True,
    )


def _merge_frame_outputs(
    existing: tuple[RequiredOutput, ...],
    frame: TaskFrame,
    capabilities: tuple[str, ...],
) -> tuple[RequiredOutput, ...]:
    """Keep legacy execution slots while exposing every canonical frame slot."""

    known = {item.output_id for item in existing}
    legacy_aliases = {
        "direct_answer": "direct_assessment",
        "current_baseline": "direct_assessment",
        "evidence_boundary": "counterpoint",
        "continuation_conditions": "rebound_case",
        "invalidation_conditions": "invalidation",
        "scenario_paths": "rebound_case",
    }
    evidence_types = tuple(capabilities) or ("evidence_boundary",)
    additions = tuple(
        _task_frame_required_output(
            output_id,
            evidence_types=evidence_types,
        )
        for output_id in frame.required_outputs
        if output_id not in known
        and legacy_aliases.get(output_id, output_id) not in known
    )
    return (*existing, *additions)


def _specialized_owner_required_outputs(
    output: SkillOutput | None,
    frame: TaskFrame,
) -> tuple[RequiredOutput, ...]:
    """Project a canonical owner contract into the shared verifier schema.

    Empty fields mean a legacy/third-party contract and retain the old behavior.
    A hash mismatch fails closed to the orchestrator's immutable TaskFrame rather
    than allowing a stale owner contract to narrow the user's requested outputs.
    """

    if output is None or output.answer_contract is None:
        return ()
    contract = output.answer_contract
    if not contract.required_outputs:
        return ()
    # A matching hash proves which frame the owner saw; it does not grant the
    # owner permission to enlarge or narrow that frame's completion gate.
    # Legacy contracts without a canonical frame can still use their own IDs.
    output_ids = frame.required_outputs or contract.required_outputs
    return tuple(
        _task_frame_required_output(output_id)
        for output_id in dict.fromkeys(output_ids)
    )


def _generic_research_deadline(
    root_deadline: ResearchDeadline,
    contract: ResearchTaskContract,
) -> ResearchDeadline:
    """把 Owner 档位预算钳制到 turn 根 deadline，避免预算重复计算。"""
    policy = ResearchPolicy.for_tier(contract.research_tier)
    policy_deadline = ResearchDeadline.from_timeout(
        policy.total_seconds,
        synthesis_reserve=policy.synthesis_reserve,
    )
    return ResearchDeadline(
        min(root_deadline.expires_at, policy_deadline.expires_at),
        synthesis_reserve=max(
            root_deadline.synthesis_reserve,
            policy.synthesis_reserve,
        ),
    )


def _parallel_skills_enabled() -> bool:
    return os.environ.get("WORKBENCH_PARALLEL_SKILLS", "1").strip().lower() not in {
        "0",
        "false",
        "off",
    }


_INTERNAL_CITATION_PATTERN = re.compile(r"\[(?:D|P|L|G|R|S|W)\d+\]")
_INTERNAL_CODE_PATTERN = re.compile(r"(?<![A-Za-z0-9_])[DPGRSW]\d+(?![A-Za-z0-9_])")
_EVIDENCE_LAYER_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_])L([1-4])(?:\s*级(?:别)?)?(?![A-Za-z0-9_])"
)
_INTERNAL_TIER_TOKEN_PATTERN = re.compile(
    r"(?:high/)?L[1-4](?:_L[1-4])+(?:_[A-Za-z0-9]+)*",
    re.IGNORECASE,
)
_EVIDENCE_LAYER_SUMMARY_PATTERN = re.compile(
    r"(?:整体)?证据层分布为\s*"
    r"L[1-4](?:\s*[×x*]\s*\d+)?"
    r"(?:\s*[、,，]\s*L[1-4](?:\s*[×x*]\s*\d+)?)*"
    r"\s*[，,]?\s*"
)
_INTERNAL_FIELD_PATTERN = re.compile(
    r'"?(?:candidate_tier|priority_score|cycle_status|warnings?)"?'
    r'\s*[:=]\s*(?:"[^"]*"|[^,，}\]\n]+)[,，]?',
    re.IGNORECASE,
)
_JSON_BLOCK_PATTERN = re.compile(
    r"```(?:json)?\s*[\[{].*?[\]}]\s*```",
    re.IGNORECASE | re.DOTALL,
)
_HUMAN_READABLE_REPLACEMENTS = (
    (
        "knowledge-base · wiki/relations/entity_exposures.json",
        "本地知识库 · 公司题材关联",
    ),
    (
        "knowledge-base · wiki/relations/evidence_index.json",
        "本地知识库 · 公司证据索引",
    ),
    ("knowledge-base · wiki/relations/", "本地知识库 · "),
    ("daily-agent", "每日复盘流程"),
    ("Daily Review 确定性投影数据", "本地复盘数据"),
    ("Daily Review", "本地复盘"),
    ("本地复盘确定性投影数据", "本地复盘数据"),
    ("本地复盘确定性投影", "本地复盘数据"),
    ('并被系统标注为"沸点"', '，盘面状态达到"沸点"'),
    ("系统统一标注为", "盘面表现为"),
    ("盘面 L4 信号", "盘面信号"),
    ("盘面L4信号", "盘面信号"),
    ("L4 信号", "盘面信号"),
    ("L4信号", "盘面信号"),
    ("L3 硬证据", "公告等硬证据"),
    ("L3硬证据", "公告等硬证据"),
    ("RAG检索的wiki向量源降级未接入", "知识库资料没有提供可用补充"),
    ("RAG 检索的 wiki 向量源降级未接入", "知识库资料没有提供可用补充"),
    ("replay 发酵信号也未匹配到任何主题", "历史发酵信号也未提供可用信息"),
    ("replay 发酵信号", "历史发酵信号"),
    ("模块 replay", "历史信号回检"),
    ("replay", "历史信号回检"),
    ("wiki 向量检索无可用命中", "知识库没有提供可用补充"),
    ("wiki 向量检索", "知识库检索"),
    ("wiki向量源", "知识库资料"),
    ("wiki 向量源", "知识库资料"),
    ("wiki-rag", "知识库检索"),
    ("图谱命中的", "知识图谱关联到的"),
    ("图谱命中", "知识图谱关联"),
    ("graph_only低置信关联", "低置信关联"),
    ("graph_only/低置信暴露", "低置信关联"),
    ("graph_only", "低置信关联"),
    ("DuckDB 同题材强势替代队列为空", "本地盘面数据没有提供同题材强势替代方向"),
    ("snapshot/export", "历史盘面快照"),
    ("capacity_industry", "成交容量居前"),
    ("market_context", "市场环境"),
    ("knowledge_evidence", "知识库候选资料"),
    ("exposure_only", "仅有概念关联"),
    ("L1_L3_candidate", "候选资料，需公告或年报确认"),
    ("DuckDB", "本地市场数据"),
    ("命中主题=", "相关主题："),
    ("命中主要来自", "现有信息主要来自"),
    ("cycle_status", "阶段状态"),
    ("candidate_tier", "候选分层"),
    ("priority_score", "优先级"),
    ("diff_ratio", "成交边际变化"),
    ("模块路由", "分析路径"),
    ("deep-dive", "产业链研究"),
    ("disclosure-archive → apply", "官方公告与年报"),
    ("图谱·语义召回(知识库向量)", "知识库补充"),
    ("图谱·语义召回(wiki 向量)", "知识库补充"),
    ("检索可观测", "资料覆盖情况"),
    ("输出质检", "回答质量检查"),
    ("theme-radar", "题材盘面快照"),
    ("double_red", "涨幅与边际量同步增强"),
    ("new_high_cluster", "新高个股聚集"),
    ("new_high_direction", "新高方向确认"),
    ("limit_advance_cluster", "连板晋级聚集"),
    ("limit_heat", "涨停热度"),
    ("super_capacity", "超大容量"),
    ("long_tail", "长尾观察"),
    ("score_detail.", "盘面信号."),
    ("medium/", "中置信/"),
    ("low/", "低置信/"),
    ("high/", "高置信/"),
    (
        "Temporal Facts 层尚未接入：以上证据仅按 source_date 标注新鲜度；"
        "正式版应把会过期/被证伪的事实建成带 status(active/superseded/invalidated) 的时序边",
        "时效边界：以上证据仅按来源日期标注，使用前需复核是否仍然有效。",
    ),
    ("substitutes_and_harmed_directions", "替代与受损方向"),
    ("prior_period_comparison", "前期比较"),
    ("financial_transmission", "财务传导"),
    ("original_disclosure", "原文披露"),
    ("segment_disclosure", "分部披露"),
    ("impact_transmission", "影响传导"),
    ("financial_metrics", "财务指标"),
    ("historical_analogs", "历史类比"),
    ("market_lifecycle", "中期趋势"),
    ("company_mapping", "公司映射"),
    ("company_evidence", "公司证据"),
    ("company_master", "公司本体"),
    ("counterevidence", "反证核验"),
    ("scenario_tree", "情景树"),
    ("market_choice", "市场选择"),
    ("report_period", "报告期锚定"),
    ("event_facts", "事件事实"),
    ("chain_stages", "产业链拆解"),
    ("rerank", "检索重排"),
    ("RAG 遥测", "检索诊断"),
    ("RAG", "知识库检索"),
    ("wiki", "知识库"),
    ("降权", "降低可信度"),
)
_EVIDENCE_LAYER_REPLACEMENTS = {
    "1": "行业资料",
    "2": "公司基础资料",
    "3": "公告等硬证据",
    "4": "盘面信号",
}
_CREDENTIAL_IDENTIFIER_PATTERN = re.compile(
    r"\b[A-Z][A-Z0-9_]*(?:API_KEY|TOKEN|SECRET|PASSWORD)\b"
)
_LOCAL_PATH_PATTERN = re.compile(r"/(?:Users|home)/|[A-Za-z]:\\")
_INTERNAL_ERROR_PATTERN = re.compile(
    r"Traceback|File \".+\", line \d+|"
    r"\b[A-Za-z_][\w.]+(?:Error|Exception)\b"
)
_INTERNAL_RETRIEVAL_DIAGNOSTIC_PATTERN = re.compile(
    r"Fetching\s+\d+\s+files:|Loading weights:|"
    r"检索方式=hybrid|BM25|BGE-m3|RRF|"
    r"\bchunk(?:_id)?=|\bhash=|\bindex=|\bk=\d+|耗时=\d+ms|状态=empty|"
    r"[DMVW]\s*源|命中来源分布|检索质量裁定|公告等硬证据覆盖|"
    r"--mode\b|\b\w+\.py\b",
    re.IGNORECASE,
)
_PUBLIC_REPORT_REPLACEMENTS = (
    ("research_1_summary", "结论"),
    ("research_2_evidence", "证据链"),
    ("research_3_risks", "分歧反证"),
    ("research_4_actions", "后续验证点"),
    ("research_5_telemetry", "资料覆盖情况"),
    ("research_6_review", "回答质量检查"),
    ("research_7_implications", "交易含义"),
    ("research_8_sources", "引用来源"),
    (
        "llm_unavailable_template_answer",
        "自然语言综合暂时不可用；已保留可核验数据与结构化产物。",
    ),
    ("answer-orchestrator", "问题理解"),
    ("ask_retrieval_pipeline", "研究检索流程"),
    ("deterministic_projection", "确定性数据整理"),
    ("deterministic_duckdb_query", "本地数据查询"),
    ("retrieved_evidence", "已检索证据"),
    ("canonical", "原始来源"),
    ("disclosure-archive → apply", "官方公告与年报"),
    ("图谱·语义召回(知识库向量)", "知识库补充"),
    ("图谱·语义召回(wiki 向量)", "知识库补充"),
    (
        "模块·deep-dive（产业维 · radar.py --mode deep-dive 题材深拆）",
        "产业链研究",
    ),
    ("模块·deep-dive", "产业链研究"),
    ("[deep-dive]", ""),
    (
        "Temporal Facts 层尚未接入：以上证据仅按 source_date 标注新鲜度；"
        "正式版应把会过期/被证伪的事实建成带 status(active/superseded/invalidated) 的时序边",
        "时效边界：以上证据仅按来源日期标注，使用前需复核是否仍然有效。",
    ),
)


@dataclass(frozen=True)
class ConversationContext:
    summary: str
    recent_messages: tuple[Message, ...]

    def to_prompt_block(self) -> str:
        recent = "\n".join(
            f"{message.role}: {message.content}" for message in self.recent_messages
        )
        return (
            "## 较早消息摘要\n"
            f"{self.summary or '（无较早消息）'}\n\n"
            "## 最近消息原文\n"
            f"{recent or '（无历史消息）'}"
        )


@dataclass(frozen=True)
class TurnResult:
    status: str
    content: str
    selected_skill_ids: tuple[str, ...]
    invoked_skill_ids: tuple[str, ...]


_PROVIDER_TRACE_FIELDS = frozenset(
    (
        "provider",
        "capability",
        "status",
        "detail",
        "source_trade_date",
        "result_count",
        "parent_id",
        "step_id",
    )
)


def _rehydrate_provider_traces(
    payloads: Sequence[dict[str, object]],
) -> list[ProviderTrace]:
    """把 SkillOutput.provider_traces（JSON dict）还原成 ProviderTrace。

    P1-A（手术版）：owner 输出重建 AskResult 时不再丢内部检索 trace，
    _record_retrieval 记到的不再是"干净但失真"的结果。字段按白名单过滤，
    坏形态条目跳过不炸主链。"""
    traces: list[ProviderTrace] = []
    for payload in payloads:
        if not isinstance(payload, dict):
            continue
        kwargs = {
            key: value
            for key, value in payload.items()
            if key in _PROVIDER_TRACE_FIELDS
        }
        if not kwargs.get("provider") or not kwargs.get("capability"):
            continue
        try:
            traces.append(ProviderTrace(**kwargs))
        except TypeError:
            continue
    return traces


_OWNER_RAW_RESULT_CACHE_PREFIX = "owner_raw_result:"


def _resolve_owner_result(
    query: str,
    output: SkillOutput,
    retrieval_cache: dict[str, object],
) -> AskResult:
    """优先消费 owner 放入 turn 缓存的完整 AskResult（P1-B：去有损重建）。

    raw 结果保留 owner 内部的真实 trade_date/warnings/provider_traces/
    检索遥测/原生 citations（含 chunk/hash 溯源）；answer_spec 以 owner
    契约为准——若契约 spec 与 raw spec 不是同一对象（继承合并等场景），
    清除 owner 预备的合成消息，下游按契约 spec 重建（防旧 registry 的
    claim_id 失配触发门禁拒稿）。缓存未命中时回退有损重建路径。"""
    contract = output.answer_contract
    if contract is None:
        raise ValueError("skill owner output requires an answer contract")
    raw = retrieval_cache.get(f"{_OWNER_RAW_RESULT_CACHE_PREFIX}{output.skill_id}")
    if not isinstance(raw, AskResult):
        return _skill_owner_result(query, output)
    if raw.answer_spec is not contract.answer_spec:
        raw.prepared_synthesis_messages = None
    raw.answer_spec = contract.answer_spec
    return raw


def _skill_owner_result(query: str, output: SkillOutput) -> AskResult:
    contract = output.answer_contract
    if contract is None:
        raise ValueError("skill owner output requires an answer contract")
    citations = [
        Citation(
            tag=f"K{index}",
            source=str(
                citation.get("title") or citation.get("source") or output.skill_id
            ),
            detail=str(citation.get("source") or ""),
        )
        for index, citation in enumerate(output.citations, start=1)
    ]
    result = AskResult(
        query=query,
        trade_date=output.as_of,
        matched_theme=None,
        candidate_tier=None,
        priority_score=None,
        found_graph=bool(contract.answer_spec.verified_facts),
        question_plan=plan_answer_question(
            query,
            question_type_override=contract.question_type,
        ),
        citations=citations,
        answer_spec=contract.answer_spec,
    )
    result.provider_traces.extend(_rehydrate_provider_traces(output.provider_traces))
    return result


def _skill_output_compatible_with_turn(
    output: SkillOutput,
    *,
    definition: object | None,
    lane: str,
    question_type: str | None,
    explicit_manual: bool = False,
) -> bool:
    """Prevent an unrelated skill contract from replacing the turn contract.

    A skill may contribute evidence/modules, but only a declared workflow or a
    terminal owner whose question type matches the controller may terminate a
    research turn.  A missing question type is accepted only for an explicitly
    declared terminal owner on a legacy untyped turn; default metadata remains
    fail-closed.  ``explicit_manual`` is retained for call-site compatibility,
    but manual selection never weakens this owner contract gate.
    """
    contract = output.answer_contract
    if contract is None:
        return False
    # A manual selection may request execution, but must never turn an
    # untyped/unknown contributor into the answer owner.  Keep this argument in
    # the signature for callers that pass it while intentionally ignoring it.
    del explicit_manual
    can_own_answer = bool(getattr(definition, "can_own_answer", False))
    if not can_own_answer:
        return False
    role = str(getattr(definition, "role", "workflow"))
    if lane == "workflow":
        return role in {"workflow", "terminal_owner"}
    if lane != "research":
        return False
    if question_type is None:
        return role == "terminal_owner"
    contract_type = contract.question_type
    accepted_question_types = tuple(
        str(item) for item in (getattr(definition, "accepted_question_types", ()) or ())
    )
    if accepted_question_types and question_type not in accepted_question_types:
        return False
    return role == "terminal_owner" and contract_type == question_type


def _deadline_partial_result(query: str, warnings: Sequence[str]) -> AskResult:
    return AskResult(
        query=query,
        trade_date=None,
        matched_theme=None,
        candidate_tier=None,
        priority_score=None,
        warnings=list(dict.fromkeys(warnings)),
        sections={
            "结论": ["专项研究达到统一截止时间，未启动第二套完整问答流程。"],
            "证据链": [],
            "分歧反证": ["未完成阶段保持未知，不能据此推断为没有证据。"],
            "后续验证点": ["增加研究预算后，从未完成的 owner stage 继续。"],
            "交易含义": ["当前证据不足，不新增交易判断。"],
            "数据源状态": ["owner_timeout；返回截止前 partial artifacts。"],
            "引用来源": [],
        },
    )


def _summarize_messages(messages: Sequence[Message]) -> str:
    text = "\n".join(f"{message.role}: {message.content}" for message in messages)
    if len(text) <= SUMMARY_CHAR_LIMIT:
        return text
    return "…" + text[-(SUMMARY_CHAR_LIMIT - 1) :]


def _redact_object(value: object) -> object:
    if isinstance(value, str):
        return sanitize_user_visible_artifact_text(value)
    if isinstance(value, list):
        return [_redact_object(item) for item in value]
    if isinstance(value, dict):
        return {redact(str(key)): _redact_object(item) for key, item in value.items()}
    return value


def _sanitize_citation_list(
    citations: list[dict[str, object]],
) -> list[dict[str, object]]:
    sanitized: list[dict[str, object]] = []
    seen: set[tuple[str, tuple[str, ...]]] = set()
    for citation in citations:
        item = dict(citation)
        for key in ("source", "detail", "label", "title"):
            value = item.get(key)
            if isinstance(value, str):
                item[key] = sanitize_user_visible_artifact_text(value)
        identity_values = tuple(
            sorted(
                {
                    str(item.get(key) or "").strip().casefold()
                    for key in ("source", "detail", "label", "title", "url")
                    if str(item.get(key) or "").strip()
                }
            )
        )
        identity = (
            str(item.get("tag") or "").strip().casefold(),
            identity_values,
        )
        if identity in seen:
            continue
        seen.add(identity)
        sanitized.append(item)
    return sanitized


def sanitize_user_visible_artifact_text(text: str) -> str:
    cleaned = redact(text)
    cleaned = re.sub(
        r"(?:LLM\s*合成未采用[:：]\s*)?provider_timeout",
        "模型精修超时；已保留可核验版本。",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"untrusted\s+index\s+freshness:\s*missing",
        "知识库索引时效无法确认；本轮未采用该检索结果。",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"narrow\s+retrieval\s+empty\s+after\s+\d+\s+attempts?",
        "未检索到可核验的公司专项资料；已按证据缺口处理。",
        cleaned,
        flags=re.IGNORECASE,
    )
    if re.search(r"未配置 LLM key", cleaned, re.IGNORECASE):
        return "自然语言综合暂时不可用；已保留可核验数据与结构化产物。"
    # P0 修复：命中内部诊断特征时只声明"已隐藏"，不得改写成"检索不可用"——
    # 此前一条成功检索的说明只要含 BM25/chunk/.py 等词就会被整体替换成
    # 与事实相反的降级声明（把真话洗成假话）。降级与否只能由降级路径自己写。
    if re.search(r"HF_TOKEN|Hugging\s*Face", cleaned, re.IGNORECASE):
        return "（内部检索诊断信息已隐藏。）"
    if _INTERNAL_RETRIEVAL_DIAGNOSTIC_PATTERN.search(cleaned):
        return "（内部检索诊断信息已隐藏。）"
    if _LOCAL_PATH_PATTERN.search(cleaned):
        return "本地研究数据（路径已隐藏）。"
    if _INTERNAL_ERROR_PATTERN.search(cleaned):
        return "研究过程中出现内部错误；相关结果未纳入结论。"
    cleaned = sanitize_conversation_answer(cleaned)
    cleaned = _CREDENTIAL_IDENTIFIER_PATTERN.sub("模型服务凭据", cleaned)
    for internal, readable in _PUBLIC_REPORT_REPLACEMENTS:
        cleaned = cleaned.replace(internal, readable)
    return cleaned


def sanitize_conversation_answer(text: str) -> str:
    cleaned = _JSON_BLOCK_PATTERN.sub("", text)
    cleaned = re.sub(
        r"(?m)^.*(?:Fetching\s+\d+\s+files:|Loading weights:|"
        r"检索方式=hybrid|BM25|BGE-m3|RRF|"
        r"\bchunk(?:_id)?=|\bhash=|\bindex=|\bk=\d+|"
        r"耗时=\d+ms|状态=empty|[DMVW]\s*源|命中来源分布|"
        r"检索质量裁定|公告等硬证据覆盖|--mode\b|\b\w+\.py\b).*$",
        "（内部检索诊断信息已隐藏。）",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = _INTERNAL_FIELD_PATTERN.sub("", cleaned)
    cleaned = _EVIDENCE_LAYER_SUMMARY_PATTERN.sub("", cleaned)
    cleaned = re.sub(
        r"(?<![A-Za-z0-9_])L([1-4])_(structured|market_signal|market_context|candidate)\b",
        lambda match: (
            "结构化数据"
            if match.group(2).lower() == "structured"
            else "候选资料"
            if match.group(2).lower() == "candidate"
            else _EVIDENCE_LAYER_REPLACEMENTS[match.group(1)]
        ),
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"\[\s*(?:[DPLGRSW]\d+\s*(?:[,，、]\s*)?)+\]",
        "",
        cleaned,
    )
    cleaned = _INTERNAL_CITATION_PATTERN.sub("", cleaned)
    # Removing each internal marker separately used to leave punctuation shells
    # such as ``[, ,]`` in the public report.  Strip only bracket groups that no
    # longer contain semantic text; ordinary financial brackets are preserved.
    cleaned = re.sub(r"\[\s*(?:[,，]\s*)*\]", "", cleaned)
    # Section ordinals belong to the presentation layer, not to the grounded
    # content.  A rejected sentence can otherwise turn 一/二/三 into 一/三/五.
    cleaned = re.sub(
        r"(?m)^(#{1,3}\s+)[一二三四五六七八九十]+、\s*",
        r"\1",
        cleaned,
    )
    cleaned = re.sub(
        r"\bMarketAdapter\.get_[A-Za-z0-9_]+\b",
        "本地盘面数据",
        cleaned,
    )
    for internal, readable in _HUMAN_READABLE_REPLACEMENTS:
        cleaned = cleaned.replace(internal, readable)
    cleaned = re.sub(
        r"\b(?:True|False)\b",
        lambda match: "是" if match.group(0) == "True" else "否",
        cleaned,
    )
    cleaned = _INTERNAL_TIER_TOKEN_PATTERN.sub("较高置信候选", cleaned)
    cleaned = _EVIDENCE_LAYER_PATTERN.sub(
        lambda match: _EVIDENCE_LAYER_REPLACEMENTS[match.group(1)],
        cleaned,
    )
    cleaned = re.sub(
        r"公告等硬证据(?:\s*(?:的\s*)?(?:硬)?证据)+",
        "公告等硬证据",
        cleaned,
    )
    cleaned = re.sub(r"行业资料(?:\s*行业资料)+", "行业资料", cleaned)
    cleaned = re.sub(r"公司基础资料(?:\s*(?:公司)?基础资料)+", "公司基础资料", cleaned)
    cleaned = re.sub(r"盘面信号(?:\s*盘面信号)+", "盘面信号", cleaned)
    cleaned = re.sub(r"盘面\s*盘面信号", "盘面信号", cleaned)
    cleaned = re.sub(
        r"(?<=[\u4e00-\u9fff])_(?:market_signal|market_context)\b",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"公告等硬证据\s*(?=(?:公告|订单|认证|量产|客户验证))", "", cleaned
    )
    cleaned = re.sub(
        r"(?<![A-Za-z])local(?![A-Za-z])", "本地", cleaned, flags=re.IGNORECASE
    )
    cleaned = re.sub(r"本地\s*本地", "本地", cleaned)
    cleaned = re.sub(r"本地复盘\s*确定性投影(?:数据)?", "本地复盘数据", cleaned)
    cleaned = cleaned.replace("知识知识图谱", "知识图谱")
    cleaned = cleaned.replace("确定性投影", "数据")
    cleaned = re.sub(r"本地复盘数据(?:\s*数据)+", "本地复盘数据", cleaned)
    cleaned = re.sub(r"\bnormal\b", "常规容量", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"质量\s+medium\b", "质量中等", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"质量\s+high\b", "质量较高", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"质量\s+low\b", "质量较低", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(
        r"\btarget=([^\s]+)\s+source=",
        r"对象=\1；来源=",
        cleaned,
    )
    cleaned = cleaned.replace("[[", "").replace("]]", "")
    cleaned = _INTERNAL_CODE_PATTERN.sub("", cleaned)
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"(?<=[\u4e00-\u9fff]) (?=[\u4e00-\u9fff])", "", cleaned)
    cleaned = re.sub(r" +([，。；：、])", r"\1", cleaned)
    cleaned = re.sub(r"([，。；：、（(]) +(?=[\u4e00-\u9fff])", r"\1", cleaned)
    cleaned = re.sub(r"(?m)^ +(?=[\u4e00-\u9fff])", "", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    deduped_lines: list[str] = []
    for line in cleaned.splitlines():
        if line and deduped_lines and line == deduped_lines[-1]:
            continue
        deduped_lines.append(line)
    cleaned = "\n".join(deduped_lines)
    cleaned = cleaned.replace("盘面信号_盘面信号", "盘面信号")
    return cleaned.strip()


def build_conversation_context(
    conversation: Conversation,
    messages: Sequence[Message],
    *,
    current_run_id: str,
) -> ConversationContext:
    history = [
        message
        for message in messages
        if message.run_id != current_run_id
        and message.status == "completed"
        and message.role in {"user", "assistant"}
        and message.content.strip()
    ]
    recent = tuple(history[-RECENT_MESSAGE_LIMIT:])
    older = history[:-RECENT_MESSAGE_LIMIT]
    summary = _summarize_messages(older) if older else conversation.summary
    return ConversationContext(summary=summary, recent_messages=recent)


def contextualize_follow_up_query(
    query: str,
    context: ConversationContext,
) -> str:
    cleaned = query.strip()
    if not is_contextual_reference(cleaned):
        return cleaned
    previous_user = next(
        (
            message.content.strip()
            for message in reversed(context.recent_messages)
            if message.role == "user" and message.content.strip()
        ),
        "",
    )
    if not previous_user:
        return cleaned
    return f"{previous_user}\n追问：{cleaned}"


def previous_turn_intent(
    context: ConversationContext,
) -> tuple[TurnIntent | None, str | None]:
    message = previous_turn_message(context)
    if message is not None:
        return TurnIntent.from_dict(message.turn_intent), message.message_id
    return None, None


def previous_turn_message(context: ConversationContext) -> Message | None:
    for message in reversed(context.recent_messages):
        intent = TurnIntent.from_dict(message.turn_intent)
        if intent is not None:
            return message
    return None


class TurnOrchestrator:
    def __init__(
        self,
        *,
        repo_root: Path,
        conversation_store: ConversationStore,
        run_store: RunStore,
        answer_query_fn: Callable[[AskOptions], AskResult] | None = None,
        route_skills_fn: Callable[..., SkillRouteResult] | None = None,
        skill_registry: SkillRegistry | None = None,
        llm_model: str | None = None,
        turn_controller_fn: Callable[..., TurnDecision] | None = None,
        lane_answer_fn: Callable[..., LaneAnswer] | None = None,
        research_policy: ResearchExecutionPolicy | None = None,
        is_cancelled: Callable[[], bool] | None = None,
        cancellation_reason: Callable[[], str | None] | None = None,
        event_id_prefix: str = "",
        continuous_turn_adapter: ContinuousTurnHandler | None = None,
    ) -> None:
        self.repo_root = repo_root
        self.conversation_store = conversation_store
        self.run_store = run_store
        self.answer_query = answer_query_fn or answer_query
        self.route_skills = route_skills_fn or route_skills
        self.skill_registry = skill_registry or builtin_skill_registry()
        self.llm_model = llm_model
        self.turn_controller = turn_controller_fn or decide_turn
        self.generate_lane_answer = lane_answer_fn or generate_lane_answer
        self.research_policy = research_policy or ResearchExecutionPolicy()
        self.is_cancelled = is_cancelled or (lambda: False)
        self.cancellation_reason = cancellation_reason or (lambda: None)
        self.event_id_prefix = event_id_prefix
        self.continuous_turn_adapter = continuous_turn_adapter

    def _market_db_path(self) -> Path:
        """Resolve the data root separately from the runtime code checkout.

        Workbench deployments intentionally run code from a clean detached
        runtime while sharing the private DuckDB through ``FINANCE_WS``.  Use a
        fixture-local DB when one exists (tests), otherwise use the configured
        data root.  Never silently turn a missing DB into a successful
        boundary-only evidence block.
        """

        local_path = self.repo_root / "db" / "market_feature_store.duckdb"
        if local_path.is_file():
            return local_path
        configured_path = (
            default_paths().finance_root / "db" / "market_feature_store.duckdb"
        )
        return configured_path if configured_path.is_file() else local_path

    def run_turn(
        self,
        *,
        conversation_id: str,
        run_id: str,
        assistant_message_id: str,
        query: str,
        skill_mode: SkillMode,
        selected_skill_ids: Sequence[str],
        perspective_mode: str = perspective_lab.PERSPECTIVE_MODE_NEUTRAL,
        selected_perspective_ids: Sequence[str] = (),
    ) -> TurnResult:
        # P1-B：turn 级 LLM 调用台账 + 检索查询台账。controller/judge/agent/
        # 合成/修订/影子链的每次 provider 尝试记入同一本账（skill 线程经
        # copy_context 传播）；同 provider+query 的检索每 turn 只真实执行一次。
        # 两本账结束前以 trace 落盘——预算不再只统计 skill 次数。
        with (
            llm_refine.call_ledger_scope(max_calls=self.research_policy.max_llm_calls),
            query_ledger.query_ledger_scope(),
        ):
            return self._run_turn_ledgered(
                conversation_id=conversation_id,
                run_id=run_id,
                assistant_message_id=assistant_message_id,
                query=query,
                skill_mode=skill_mode,
                selected_skill_ids=selected_skill_ids,
                perspective_mode=perspective_mode,
                selected_perspective_ids=selected_perspective_ids,
            )

    def _run_turn_ledgered(
        self,
        *,
        conversation_id: str,
        run_id: str,
        assistant_message_id: str,
        query: str,
        skill_mode: SkillMode,
        selected_skill_ids: Sequence[str],
        perspective_mode: str = perspective_lab.PERSPECTIVE_MODE_NEUTRAL,
        selected_perspective_ids: Sequence[str] = (),
    ) -> TurnResult:
        report = new_structured_report(
            run_id=run_id,
            question=query,
            task_type="ask",
        )
        selected: list[str] = []
        manual_selected = list(dict.fromkeys(selected_skill_ids))
        invoked: list[str] = []
        warnings: list[str] = []
        citations: list[dict[str, object]] = []
        text_chunks: list[str] = []
        skill_outputs: list[SkillOutput] = []
        answer_model_name = self.llm_model
        research_deadline = ResearchDeadline.from_timeout(
            self.research_policy.max_elapsed_seconds,
            # P0：为最终合成硬保留 20 秒，前置检索不得消费（见 ResearchDeadline）。
            synthesis_reserve=20.0,
        )
        self._emit(
            run_id,
            assistant_message_id,
            "message:start",
            "message.start",
            {"status": "running"},
            conversation_id,
        )
        self._emit(
            run_id,
            assistant_message_id,
            "report:start",
            "report.start",
            {"report": report},
            conversation_id,
        )
        try:
            conversation = self.conversation_store.load_conversation(conversation_id)
            context = build_conversation_context(
                conversation,
                self.conversation_store.load_messages(conversation_id),
                current_run_id=run_id,
            )
            self.conversation_store.update_summary_text(
                conversation_id, context.summary
            )
            inherited_message = previous_turn_message(context)
            inherited_intent = (
                TurnIntent.from_dict(inherited_message.turn_intent)
                if inherited_message is not None
                else None
            )
            inherited_turn_id = (
                inherited_message.message_id if inherited_message is not None else None
            )
            if (
                inherited_intent is not None
                and inherited_message is not None
                and not inherited_intent.skill_ids
                and inherited_message.invoked_skill_ids
            ):
                inherited_intent = replace(
                    inherited_intent,
                    skill_ids=tuple(inherited_message.invoked_skill_ids),
                )
            controller_started = time.monotonic()
            decision = self.turn_controller(
                query,
                context=context.to_prompt_block(),
                skill_mode=skill_mode,
                selected_skill_ids=selected_skill_ids,
                previous_intent=inherited_intent,
                previous_turn_id=inherited_turn_id,
            )
            controller_question_type_supplied = decision.question_type is not None
            task_frame = decision.task_frame
            if task_frame is None:
                # Compatibility boundary for injected/legacy controllers: turn
                # their one decision into a TaskFrame once, then freeze it.
                legacy_envelope = understand_query(query)
                if decision.question_type is not None:
                    legacy_envelope = replace(
                        legacy_envelope,
                        question_type=decision.question_type,
                        subject=decision.subject,
                        timeframe=decision.timeframe or legacy_envelope.timeframe,
                    )
                task_frame = build_task_frame(
                    query,
                    legacy_envelope,
                    inherited_subject=(
                        inherited_intent.primary_subject
                        if inherited_intent is not None
                        and is_contextual_follow_up(
                            query,
                            legacy_envelope,
                            inherited_intent,
                        )
                        else None
                    ),
                )
                raw_envelope = project_task_frame(task_frame, legacy_envelope)
            else:
                raw_envelope = envelope_from_task_frame(task_frame)
            turn_intent = decision.turn_intent or build_turn_intent(
                query,
                raw_envelope,
                previous_intent=inherited_intent,
                previous_turn_id=inherited_turn_id,
                task_frame=task_frame,
            )
            turn_intent = replace(
                turn_intent,
                primary_subject=task_frame.subject,
                question_type=task_frame.question_type,
                timeframe=task_frame.timeframe,
                required_outputs=task_frame.required_outputs,
                task_frame_hash=task_frame.task_frame_hash,
            )
            research_plan = ResearchPlan.from_intent(turn_intent)
            # 单一事实源：controller 返回的 decision 已与 turn_intent 对齐
            # （见 turn_controller._attach_turn_intent）。仅当 controller 未
            # 附带 intent（异常降级路径）时才用本地重建的 intent 回填，
            # 不再无条件用 intent 覆盖 controller 的路由裁决。
            if decision.turn_intent is None:
                decision = replace(
                    decision,
                    question_type=turn_intent.question_type,
                    subject=turn_intent.primary_subject,
                    turn_intent=turn_intent,
                    task_frame=task_frame,
                )
            contextual_query = contextualize_intent_query(query, turn_intent)
            inherited_answer_spec = (
                self._load_answer_spec(inherited_message.run_id)
                if (
                    inherited_message is not None
                    and turn_intent.inherited_from_turn is not None
                )
                else None
            )
            inherited_stage_artifacts = self._json_object_tuple(
                inherited_answer_spec,
                "research_artifacts",
            )
            inherited_evidence_atoms = self._json_object_tuple(
                inherited_answer_spec,
                "research_evidence_atoms",
            )
            # Route is an execution projection of the same frame.  In
            # particular, never re-run semantic understanding on the contextual
            # retrieval query: that query is allowed to add context, not to
            # replace the user's original task.
            routing_envelope = replace(
                project_task_frame(task_frame, raw_envelope),
                operators=turn_intent.operators,
                required_outputs=task_frame.required_outputs,
                time_horizon=turn_intent.time_horizon,
            )
            report["task_type"] = decision.lane
            report["task_frame"] = task_frame.to_dict()
            report["task_frame_hash"] = task_frame.task_frame_hash
            legacy_lane = (
                "knowledge"
                if routing_envelope.question_type
                in {QUESTION_CONCEPT_DEFINITION, QUESTION_METHODOLOGY}
                else "research"
            )
            self._trace(
                run_id,
                assistant_message_id,
                conversation_id,
                "controller",
                "turn_controller",
                {
                    "decision": decision.to_dict(),
                    "task_frame": task_frame.to_dict(),
                    "task_frame_hash": task_frame.task_frame_hash,
                    "turn_intent": turn_intent.to_dict(),
                    "research_plan": research_plan.to_dict(),
                    "legacy_query_envelope": routing_envelope.to_dict(),
                    "legacy_lane": legacy_lane,
                    "decision_diverged_from_legacy": decision.lane != legacy_lane,
                    "router_allowed": decision.lane in {"research", "workflow"},
                    "elapsed_ms": self._elapsed_ms(controller_started),
                },
            )
            self._check_cancelled()
            if self.continuous_turn_adapter is not None:
                continuous_control = project_turn_decision(
                    decision,
                    task_frame=task_frame,
                    turn_intent=turn_intent,
                )
                continuous_result = self.continuous_turn_adapter.handle(
                    frame=task_frame,
                    control=continuous_control,
                )
                self._check_cancelled()
                if continuous_result.handled:
                    return self._complete_continuous_turn(
                        conversation_id=conversation_id,
                        run_id=run_id,
                        assistant_message_id=assistant_message_id,
                        query=query,
                        report=report,
                        result=continuous_result,
                        task_frame=task_frame,
                        selected_skill_ids=manual_selected,
                        turn_intent=turn_intent,
                        research_plan=research_plan,
                    )
            if decision.lane in {"chat", "meta", "clarify"} or (
                decision.lane == "knowledge" and not decision.needs_retrieval
            ):
                lane_answer = self.generate_lane_answer(
                    query,
                    decision,
                    context=context.to_prompt_block(),
                    model_override=self.llm_model,
                )
                lane_citations: list[dict[str, object]] = []
                lane_warnings: list[str] = []
                lane_as_of: str | None = None
                retrieval_attempted = False
                if (
                    decision.lane == "knowledge"
                    and lane_answer.fallback_reason
                    and decision.question_type != QUESTION_METHODOLOGY
                ):
                    retrieval_attempted = True
                    fallback_started = time.monotonic()
                    try:
                        result = self.answer_query(
                            AskOptions(
                                query=contextual_query,
                                user=self.run_store.user_id,
                                compose=False,
                                synthesize=False,
                                market_db_path=(self._market_db_path()),
                                conversation_context=context.to_prompt_block(),
                                include_memory_block=decision.needs_memory,
                                include_recall_block=decision.needs_memory,
                                question_type_override=turn_intent.question_type,
                                deadline=research_deadline,
                            )
                        )
                    except Exception as exc:  # noqa: BLE001
                        warning = "一般知识检索暂时不可用"
                        lane_warnings.append(warning)
                        self.run_store.add_degrade(run_id, warning)
                        lane_answer = LaneAnswer(
                            answer=(
                                "当前自然语言生成暂时不可用，本轮也未取得足够可靠的资料；"
                                "请稍后重试，或提供可核验来源。"
                            ),
                            fallback_reason=lane_answer.fallback_reason,
                        )
                        self._trace(
                            run_id,
                            assistant_message_id,
                            conversation_id,
                            "knowledge_fallback",
                            "knowledge_fallback_retrieval",
                            {
                                "status": "failed",
                                "failure_reason": type(exc).__name__,
                                "elapsed_ms": self._elapsed_ms(fallback_started),
                            },
                        )
                    else:
                        if not result.citations:
                            warning = "一般知识检索未取得可核验资料"
                            if warning not in result.warnings:
                                lane_warnings.append(warning)
                                self.run_store.add_degrade(run_id, warning)
                        lane_answer = LaneAnswer(
                            answer=render_knowledge_fallback(result),
                            fallback_reason=lane_answer.fallback_reason,
                        )
                        lane_as_of = result.trade_date
                        lane_warnings.extend(result.warnings)
                        lane_citations.extend(
                            {
                                "tag": citation.tag,
                                "source": citation.source,
                                "detail": citation.detail,
                            }
                            for citation in result.citations
                        )
                        for index, module in enumerate(
                            ask_result_modules(result),
                            start=1,
                        ):
                            self._emit_module(
                                run_id,
                                assistant_message_id,
                                conversation_id,
                                report,
                                module,
                                f"knowledge:fallback:module:{index}",
                            )
                        self._record_retrieval(
                            run_id,
                            assistant_message_id,
                            conversation_id,
                            result,
                            elapsed_ms=self._elapsed_ms(fallback_started),
                        )
                        self.run_store.update_provenance(
                            run_id,
                            source_date=result.trade_date,
                        )
                        self._trace(
                            run_id,
                            assistant_message_id,
                            conversation_id,
                            "knowledge_fallback",
                            "knowledge_fallback_retrieval",
                            {
                                "status": (
                                    "completed" if result.citations else "degraded"
                                ),
                                "citation_count": len(result.citations),
                                "elapsed_ms": self._elapsed_ms(fallback_started),
                            },
                        )
                if (
                    decision.question_type == QUESTION_METHODOLOGY
                    and lane_answer.fallback_reason
                ):
                    warning = "方法论回答生成暂时不可用"
                    lane_warnings.append(warning)
                    self.run_store.add_degrade(run_id, warning)
                self._trace(
                    run_id,
                    assistant_message_id,
                    conversation_id,
                    "generate",
                    "lane_direct_answer",
                    {
                        "lane": decision.lane,
                        "retrieval_attempted": retrieval_attempted,
                        "provider": lane_answer.provider,
                        "fallback_reason": lane_answer.fallback_reason,
                    },
                )
                return self._complete_lane_turn(
                    conversation_id=conversation_id,
                    run_id=run_id,
                    assistant_message_id=assistant_message_id,
                    query=query,
                    report=report,
                    answer=lane_answer,
                    selected_skill_ids=manual_selected,
                    turn_intent=turn_intent,
                    research_plan=research_plan,
                    citations=lane_citations,
                    warnings=lane_warnings,
                    as_of=lane_as_of,
                )
            route_started = time.monotonic()
            relation_guard_requested = bool(
                "relation" in turn_intent.operators
                and turn_intent.inherited_from_turn is None
                and re.search(
                    r"(?:上游|下游|产业链位置|处于.{0,8}环节|"
                    r"客户.{0,8}(?:竞争对手|替代)|竞争对手|供应商|合作方)",
                    contextual_query,
                )
            )
            generic_owner_requested = (
                decision.lane == "research"
                and turn_intent.question_type
                not in {QUESTION_MARKET_TECHNICAL, QUESTION_EXTERNAL_MARKET}
                # 真实 controller 总会附带 TurnIntent；若某个旧的测试/第三方
                # controller 只返回无 question_type 的裸 TurnDecision，保留
                # 旧 route 行为，避免把兼容层误判为“ownerless research”。
                and (
                    controller_question_type_supplied
                    or turn_intent.question_type != QUESTION_GENERAL
                )
                and (turn_intent.answer_owner is None or relation_guard_requested)
                and skill_mode in {"auto", "hybrid"}
                and not selected_skill_ids
            )
            router_skipped = bool(
                decision.lane == "knowledge"
                or turn_intent.question_type == "market_technical"
                or relation_guard_requested
                or generic_owner_requested
            )
            if router_skipped:
                # market_technical：controller 已确定性定型，走 ask 内的
                # 结构化行情技术位管线，跳过语义 skill router 的额外 LLM。
                # ownerless general：由 GenericResearchOwner 先接管，固定
                # provider 只作为它的工具，不再预跑整条 Ask 管线。
                route = SkillRouteResult(
                    (),
                    fallback_to_ask=True,
                    base_finance_fallback=False,
                )
            else:
                route_kwargs: dict[str, object] = {
                    "registry": self.skill_registry.definitions,
                    "query_envelope": routing_envelope,
                }
                if turn_intent.answer_owner is not None:
                    route_kwargs["answer_owner"] = turn_intent.answer_owner
                if turn_intent.inherited_from_turn is not None:
                    route_kwargs["inherited_skill_ids"] = turn_intent.skill_ids
                route = self.route_skills(
                    contextual_query,
                    "ask",
                    skill_mode,
                    selected_skill_ids,
                    **route_kwargs,
                )
            selected = [selection.skill_id for selection in route.selections]
            turn_intent = replace(
                turn_intent,
                skill_ids=(
                    tuple(selected)
                    if skill_mode == "manual"
                    else tuple(dict.fromkeys((*turn_intent.skill_ids, *selected)))
                ),
            )
            research_plan = ResearchPlan.from_intent(turn_intent)
            self._trace(
                run_id,
                assistant_message_id,
                conversation_id,
                "route",
                "route_skills",
                {
                    "selected": [
                        {
                            "skill_id": selection.skill_id,
                            "source": selection.selection_source,
                            "reason": selection.reason,
                        }
                        for selection in route.selections
                    ],
                    "fallback_to_ask": route.fallback_to_ask,
                    "base_finance_fallback": route.base_finance_fallback,
                    "router_skipped": router_skipped,
                    "generic_owner_requested": generic_owner_requested,
                    "relation_guard_requested": relation_guard_requested,
                    "controller_lane": decision.lane,
                    "query_envelope": routing_envelope.to_dict(),
                    "task_frame_hash": task_frame.task_frame_hash,
                    "elapsed_ms": self._elapsed_ms(route_started),
                },
            )
            self._check_cancelled()

            research_budget = ResearchExecutionBudget(
                self.research_policy,
                deadline=research_deadline,
            )
            seen_skill_ids: set[str] = set()
            retrieval_cache: dict[str, object] = {}
            pending_selections = list(route.selections)
            execution_feedback: list[dict[str, str]] = []
            fallback_route_round = 0
            owner_timed_out = False
            parallel_skills = _parallel_skills_enabled()
            # 池容量 = 并行度上限 + 超时残留线程的余量；串行模式下并行度
            # 仍由“消费时才提交”控制为 1，超时未结束的 skill 不阻塞后续。
            skill_pool = ThreadPoolExecutor(
                max_workers=_SKILL_POOL_WORKERS * 2,
                thread_name_prefix="workbench-skill",
            )
            prestarted: dict[str, tuple[Future[SkillOutput], float]] = {}

            def submit_skill(skill_id: str) -> tuple[Future[SkillOutput], float]:
                # copy_context：让 skill 线程共享本 turn 的 LLM 调用台账等
                # ContextVar（每次 submit 独立拷贝，台账对象引用共享）。
                run_context = contextvars.copy_context()
                future = skill_pool.submit(
                    run_context.run,
                    self.skill_registry.executors[skill_id].execute,
                    SkillExecutionContext(
                        query=contextual_query,
                        task_type="ask",
                        user_id=self.run_store.user_id,
                        run_id=run_id,
                        conversation_id=conversation_id,
                        repo_root=self.repo_root,
                        run_store=self.run_store,
                        conversation_context=context.to_prompt_block(),
                        task_frame=task_frame,
                        turn_intent=turn_intent.to_dict(),
                        research_plan=research_plan.to_dict(),
                        inherited_answer_spec=inherited_answer_spec,
                        inherited_stage_artifacts=inherited_stage_artifacts,
                        inherited_evidence_atoms=inherited_evidence_atoms,
                        deadline=research_deadline,
                        retrieval_cache=retrieval_cache,
                    ),
                )
                return future, time.monotonic()

            def prestart_pending(selections: list) -> None:
                # 并行模式：把本轮已路由、未重复且预算内的 skill 提前提交，
                # 结果仍按路由顺序消费，保证输出确定性。
                if not parallel_skills:
                    return
                for item in selections:
                    candidate = item.skill_id
                    if candidate in seen_skill_ids or candidate in prestarted:
                        continue
                    if (
                        research_budget.call_count + len(prestarted)
                        >= self.research_policy.max_skill_calls
                    ):
                        break
                    if research_budget.remaining_seconds <= 0:
                        break
                    prestarted[candidate] = submit_skill(candidate)

            while pending_selections:
                prestart_pending(pending_selections)
                selection = pending_selections.pop(0)
                self._check_cancelled()
                skill_id = selection.skill_id
                if skill_id in seen_skill_ids:
                    warning = f"Skill {skill_id} 因重复选择而跳过"
                    warnings.append(warning)
                    self.run_store.add_degrade(run_id, warning)
                    research_budget.record(
                        skill_id,
                        input_summary=contextual_query,
                        provider="skill_registry",
                        status="skipped_duplicate",
                        elapsed_ms=0,
                        failure_reason=warning,
                    )
                    continue
                if not research_budget.can_start():
                    warning = f"Skill {skill_id} 因研究调用预算耗尽而跳过"
                    warnings.append(warning)
                    self.run_store.add_degrade(run_id, warning)
                    research_budget.record(
                        skill_id,
                        input_summary=contextual_query,
                        provider="skill_registry",
                        status="skipped_budget",
                        elapsed_ms=0,
                        failure_reason=warning,
                    )
                    if skill_id == turn_intent.answer_owner:
                        owner_timed_out = True
                        pending_selections.clear()
                    continue
                seen_skill_ids.add(skill_id)
                invoked.append(skill_id)
                if skill_id == turn_intent.answer_owner:
                    workflow_spec = OWNER_WORKFLOW_SPECS[skill_id]
                    self._emit(
                        run_id,
                        assistant_message_id,
                        f"workflow:{skill_id}:loaded",
                        "workflow.loaded",
                        {
                            **workflow_spec.to_dict(),
                            "status": "loaded",
                        },
                        conversation_id,
                    )
                self._emit(
                    run_id,
                    assistant_message_id,
                    f"skill:{skill_id}:start",
                    "skill.start",
                    {
                        "skill_id": skill_id,
                        "selection_source": selection.selection_source,
                        "reason": selection.reason,
                    },
                    conversation_id,
                )
                future = None
                skill_started = time.monotonic()
                try:
                    launched = prestarted.pop(skill_id, None)
                    if launched is None:
                        launched = submit_skill(skill_id)
                    future, skill_started = launched
                    allowed_seconds = min(
                        self.skill_registry.definitions[skill_id].timeout_seconds,
                        research_budget.remaining_seconds,
                    )
                    output = future.result(
                        timeout=max(
                            0.001,
                            allowed_seconds - (time.monotonic() - skill_started),
                        )
                    )
                except Exception as exc:  # noqa: BLE001
                    warning = (
                        f"Skill {skill_id} 执行超时"
                        if isinstance(exc, FuturesTimeoutError)
                        else f"Skill {skill_id} 执行失败（{type(exc).__name__}）"
                    )
                    research_budget.record(
                        skill_id,
                        input_summary=contextual_query,
                        provider="skill_registry",
                        status=(
                            "timeout"
                            if isinstance(exc, FuturesTimeoutError)
                            else "failed"
                        ),
                        elapsed_ms=self._elapsed_ms(skill_started),
                        failure_reason=warning,
                    )
                    warnings.append(warning)
                    self.run_store.add_degrade(run_id, warning)
                    if (
                        isinstance(exc, FuturesTimeoutError)
                        and skill_id == turn_intent.answer_owner
                    ):
                        owner_timed_out = True
                        pending_selections.clear()
                    module = self._skill_warning_module(skill_id, warning)
                    self._emit_module(
                        run_id,
                        assistant_message_id,
                        conversation_id,
                        report,
                        module,
                        f"skill:{skill_id}:warning",
                    )
                    self._emit(
                        run_id,
                        assistant_message_id,
                        f"skill:{skill_id}:result",
                        "skill.result",
                        {
                            "skill_id": skill_id,
                            "status": "degraded",
                            "warnings": [warning],
                            "elapsed_ms": self._elapsed_ms(skill_started),
                            "task_may_continue": (
                                isinstance(exc, FuturesTimeoutError)
                                and future is not None
                                and not future.done()
                            ),
                        },
                        conversation_id,
                    )
                    execution_feedback.append(
                        {
                            "skill_id": skill_id,
                            "status": (
                                "timeout"
                                if isinstance(exc, FuturesTimeoutError)
                                else "failed"
                            ),
                            "failure_reason": warning,
                        }
                    )
                else:
                    execution_status = output.status or (
                        "degraded" if output.warnings else "completed"
                    )
                    research_budget.record(
                        skill_id,
                        input_summary=contextual_query,
                        provider="skill_registry",
                        status=execution_status,
                        elapsed_ms=self._elapsed_ms(skill_started),
                        failure_reason="；".join(output.warnings),
                    )
                    skill_outputs.append(output)
                    warnings.extend(output.warnings)
                    citations.extend(output.citations)
                    output_can_own_turn = _skill_output_compatible_with_turn(
                        output,
                        definition=self.skill_registry.definitions.get(skill_id),
                        lane=decision.lane,
                        question_type=turn_intent.question_type,
                        explicit_manual=skill_mode == "manual",
                    )
                    if output.answer_contract is not None and output_can_own_turn:
                        pending_selections.clear()
                        execution_feedback.clear()
                    elif output.answer_contract is not None:
                        # An answer contract is not automatically a turn owner.
                        # Keep the route continuation alive so a mismatched
                        # workflow/profile cannot suppress the generic owner or
                        # a later compatible skill.
                        execution_feedback.append(
                            {
                                "skill_id": skill_id,
                                "status": "rejected",
                                "failure_reason": (
                                    "skill contract 与当前 turn question_type 不兼容"
                                ),
                            }
                        )
                    for warning in output.warnings:
                        self.run_store.add_degrade(run_id, warning)
                    for index, module in enumerate(output.modules, start=1):
                        self._emit_module(
                            run_id,
                            assistant_message_id,
                            conversation_id,
                            report,
                            module,
                            f"skill:{skill_id}:module:{index}",
                        )
                    self._emit(
                        run_id,
                        assistant_message_id,
                        f"skill:{skill_id}:result",
                        "skill.result",
                        {
                            "skill_id": skill_id,
                            "status": execution_status,
                            "output": asdict(output),
                            "elapsed_ms": self._elapsed_ms(skill_started),
                            "task_may_continue": False,
                        },
                        conversation_id,
                    )
                    if output.warnings and not output.modules and not output.citations:
                        execution_feedback.append(
                            {
                                "skill_id": skill_id,
                                "status": "degraded",
                                "failure_reason": "；".join(output.warnings),
                            }
                        )
                self._check_cancelled()
                if (
                    not pending_selections
                    and execution_feedback
                    and not owner_timed_out
                    and skill_mode != "manual"
                    and research_budget.can_start()
                ):
                    fallback_route_round += 1
                    fallback_route_started = time.monotonic()
                    fallback_route_kwargs: dict[str, object] = {
                        "registry": self.skill_registry.definitions,
                        "query_envelope": routing_envelope,
                        "excluded_skill_ids": tuple(seen_skill_ids),
                        "execution_feedback": tuple(execution_feedback),
                    }
                    if turn_intent.answer_owner is not None:
                        fallback_route_kwargs["answer_owner"] = turn_intent.answer_owner
                    fallback_route = self.route_skills(
                        contextual_query,
                        "ask",
                        skill_mode,
                        selected_skill_ids,
                        **fallback_route_kwargs,
                    )
                    replacements = [
                        item
                        for item in fallback_route.selections
                        if item.skill_id not in seen_skill_ids
                    ]
                    self._trace(
                        run_id,
                        assistant_message_id,
                        conversation_id,
                        f"route_after_tool_failure_{fallback_route_round}",
                        "route_skills_after_tool_failure",
                        {
                            "failed": list(execution_feedback),
                            "selected": [
                                {
                                    "skill_id": item.skill_id,
                                    "source": item.selection_source,
                                    "reason": item.reason,
                                }
                                for item in replacements
                            ],
                            "elapsed_ms": self._elapsed_ms(fallback_route_started),
                        },
                    )
                    execution_feedback.clear()
                    if replacements:
                        for item in replacements:
                            if item.skill_id not in selected:
                                selected.append(item.skill_id)
                        pending_selections.extend(replacements)
            skill_pool.shutdown(wait=False, cancel_futures=True)

            def capture_safe_text(text: str) -> None:
                self._check_cancelled()
                safe_text = sanitize_conversation_answer(text)
                if safe_text:
                    text_chunks.append(safe_text)

            def emit_text_delta(delta: str) -> None:
                capture_safe_text(delta)
                self._emit(
                    run_id,
                    assistant_message_id,
                    f"text:{len(text_chunks):06d}",
                    "text.delta",
                    {"delta": delta},
                    conversation_id,
                )

            compose_started = time.monotonic()
            rejected_owner_outputs: list[dict[str, object]] = []
            owner_output = next(
                (
                    output
                    for output in skill_outputs
                    if output.answer_contract is not None
                    and _skill_output_compatible_with_turn(
                        output,
                        definition=self.skill_registry.definitions.get(output.skill_id),
                        lane=decision.lane,
                        question_type=turn_intent.question_type,
                        explicit_manual=skill_mode == "manual",
                    )
                ),
                None,
            )
            for output in skill_outputs:
                if output.answer_contract is None:
                    continue
                if owner_output is output:
                    continue
                if _skill_output_compatible_with_turn(
                    output,
                    definition=self.skill_registry.definitions.get(output.skill_id),
                    lane=decision.lane,
                    question_type=turn_intent.question_type,
                    explicit_manual=skill_mode == "manual",
                ):
                    continue
                rejected_owner_outputs.append(
                    {
                        "skill_id": output.skill_id,
                        "expected_question_type": turn_intent.question_type,
                        "actual_question_type": output.answer_contract.question_type,
                        "reason": "skill contract 与 controller turn contract 不兼容",
                    }
                )
            if rejected_owner_outputs:
                for rejection in rejected_owner_outputs:
                    warning = (
                        f"Skill {rejection['skill_id']} 已降级为证据贡献者；"
                        "需显式声明 owner 元数据后才能接管答案"
                    )
                    if warning not in warnings:
                        warnings.append(warning)
                        self.run_store.add_degrade(run_id, warning)
                self._trace(
                    run_id,
                    assistant_message_id,
                    conversation_id,
                    "compose_owner_contract_guard",
                    "owner_contract_rejected",
                    {"rejected": rejected_owner_outputs},
                )
            daily_review_output = next(
                (
                    output
                    for output in skill_outputs
                    if output.skill_id == "daily-review"
                ),
                None,
            )
            market_review_requested = turn_intent.question_type in {
                "market_watch",
                "dated_market_review",
            }
            generic_contract = (
                _build_generic_research_contract(
                    contextual_query,
                    task_id=run_id,
                    turn_intent=turn_intent,
                    task_frame=task_frame,
                )
                if generic_owner_requested
                else None
            )
            generic_deadline = (
                _generic_research_deadline(research_deadline, generic_contract)
                if generic_contract is not None
                else research_deadline
            )
            skill_claims, skill_citations = self._skill_claim_bundle(skill_outputs)
            ask_options = AskOptions(
                query=contextual_query,
                date=(
                    daily_review_output.as_of
                    if daily_review_output is not None and market_review_requested
                    else None
                ),
                user=self.run_store.user_id,
                compose=True,
                synthesize=False,
                compose_revise_on_warn=False,
                market_db_path=self._market_db_path(),
                conversation_context=context.to_prompt_block(),
                wiki_rag_cache_scope=(
                    f"{self.run_store.user_id}:{conversation_id or run_id}"
                ),
                supplemental_evidence=self._skill_evidence(skill_outputs),
                supplemental_claims=skill_claims,
                supplemental_citations=skill_citations,
                include_memory_block=decision.needs_memory,
                include_recall_block=decision.needs_memory,
                question_type_override=(
                    QUESTION_MARKET_REVIEW
                    if turn_intent.question_type
                    in {"market_watch", "dated_market_review"}
                    else turn_intent.question_type
                ),
                research_task_contract=generic_contract,
                controller_capabilities=(
                    tuple(dict.fromkeys((*decision.capabilities, "web_search")))
                    if (
                        route.base_finance_fallback
                        and turn_intent.question_type == QUESTION_GENERAL
                    )
                    else decision.capabilities
                ),
                perspective_mode=perspective_mode,
                perspective_ids=tuple(selected_perspective_ids),
                stream_text_delta=capture_safe_text,
                stream_cancel_check=self.is_cancelled,
                deadline=generic_deadline,
            )
            if owner_output is not None:
                result = _resolve_owner_result(query, owner_output, retrieval_cache)
                prepared = prepare_existing_answer(ask_options, result)
                self._trace(
                    run_id,
                    assistant_message_id,
                    conversation_id,
                    "compose",
                    "skill_answer_owner",
                    {
                        "skill_id": owner_output.skill_id,
                        "retrieval_plan": list(
                            owner_output.answer_contract.retrieval_plan
                        ),
                        "output_contract": list(
                            owner_output.answer_contract.output_contract
                        ),
                        "required_outputs": list(
                            owner_output.answer_contract.required_outputs
                        ),
                        "task_frame_hash": (
                            owner_output.answer_contract.task_frame_hash
                        ),
                    },
                )
            elif owner_timed_out:
                result = _deadline_partial_result(contextual_query, warnings)
                prepared = prepare_existing_answer(ask_options, result)
            else:
                result = self._run_answer_query_with_watchdog(
                    ask_options,
                    run_id=run_id,
                    message_id=assistant_message_id,
                    conversation_id=conversation_id,
                    warnings=warnings,
                )
                prepared = (
                    PreparedAnswer(options=ask_options, result=result)
                    if decision.lane == "knowledge"
                    else prepare_existing_answer(ask_options, result)
                )
            self._check_cancelled()
            is_market_review = (
                owner_output is None
                and daily_review_output is not None
                and market_review_requested
            )
            if (
                is_market_review
                and daily_review_output is not None
                and result.trade_date is None
            ):
                result.trade_date = daily_review_output.as_of
            self._record_retrieval(
                run_id,
                assistant_message_id,
                conversation_id,
                result,
                elapsed_ms=self._elapsed_ms(compose_started),
            )
            self.run_store.update_provenance(run_id, source_date=result.trade_date)
            citations.extend(
                {
                    "tag": citation.tag,
                    "source": citation.source,
                    "detail": citation.detail,
                }
                for citation in result.citations
            )
            citations = _sanitize_citation_list(citations)
            for index, module in enumerate(ask_result_modules(result), start=1):
                self._emit_module(
                    run_id,
                    assistant_message_id,
                    conversation_id,
                    report,
                    module,
                    f"ask:module:{index}",
                )
            for index, citation in enumerate(citations, start=1):
                self._emit(
                    run_id,
                    assistant_message_id,
                    f"citation:{index:04d}",
                    "citation.ready",
                    {"citation": citation},
                    conversation_id,
                )

            if decision.lane == "knowledge":
                lane_answer = self.generate_lane_answer(
                    query,
                    decision,
                    context=context.to_prompt_block(),
                    evidence=knowledge_evidence(result),
                    model_override=self.llm_model,
                )
                result.synthesis = (
                    render_knowledge_fallback(result)
                    if lane_answer.fallback_reason
                    else lane_answer.answer
                )
                result.llm_provider = lane_answer.provider
                result.llm_fallback_reason = lane_answer.fallback_reason
                result.prepared_synthesis_messages = []
                answer_model_name = lane_answer.model or self.llm_model
                self._trace(
                    run_id,
                    assistant_message_id,
                    conversation_id,
                    "generate",
                    "knowledge_lane_answer",
                    {
                        "retrieval_attempted": True,
                        "provider": lane_answer.provider,
                        "fallback_reason": lane_answer.fallback_reason,
                    },
                )

            draft_text = render_conversation_answer(result)
            if (
                result.synthesis is None
                and is_market_review
                and daily_review_output is not None
            ):
                draft_text = render_daily_review_answer(
                    date_text=daily_review_output.as_of,
                    modules=daily_review_output.modules,
                    warnings=daily_review_output.warnings,
                )
            perspective_header = (
                perspective_lab.runtime_answer_header(
                    userspace.user_space(self.run_store.user_id),
                    mode=perspective_mode,
                    perspective_ids=tuple(selected_perspective_ids),
                )
                if decision.lane in {"research", "workflow"}
                else ""
            )
            draft_text = sanitize_conversation_answer(
                "\n\n".join(
                    block for block in (perspective_header, draft_text) if block
                )
            )
            draft_text = _sanitize_market_cause_answer_text(draft_text, query)
            has_answer_snapshot = result.answer_spec is not None and decision.lane in {
                "research",
                "workflow",
            }
            if has_answer_snapshot:
                emit_text_delta(draft_text)
                self._emit(
                    run_id,
                    assistant_message_id,
                    "answer:snapshot:1",
                    "answer.snapshot",
                    AnswerSnapshot(
                        revision=1,
                        phase="verified_draft",
                        text=draft_text,
                        final=False,
                    ).payload(),
                    conversation_id,
                )
            elif not text_chunks:
                emit_text_delta(draft_text)

            if (
                decision.lane in {"research", "workflow"}
                and result.synthesis is None
                and result.prepared_synthesis_messages
            ):
                synthesize_prepared_answer(
                    PreparedAnswer(
                        options=prepared.options,
                        result=result,
                    )
                )
            self._check_cancelled()
            self._trace(
                run_id,
                assistant_message_id,
                conversation_id,
                "synthesize",
                "answer_synthesis",
                {
                    "status": (
                        "validated" if result.synthesis is not None else "fallback"
                    ),
                    "fallback_reason": result.llm_fallback_reason,
                    "stream": result.llm_stream_telemetry,
                },
            )

            # owner raw 结果的 warnings 在 skill 阶段已并入过（output.warnings），
            # 只追加新增项，避免 degrades 重复落账。
            fresh_result_warnings = [
                warning for warning in result.warnings if warning not in warnings
            ]
            warnings.extend(fresh_result_warnings)
            for warning in fresh_result_warnings:
                self.run_store.add_degrade(run_id, warning)
            answer_text = render_conversation_answer(result)
            if (
                result.synthesis is None
                and is_market_review
                and daily_review_output is not None
            ):
                answer_text = render_daily_review_answer(
                    date_text=daily_review_output.as_of,
                    modules=daily_review_output.modules,
                    warnings=daily_review_output.warnings,
                )
            fallback_notice = (
                perspective_lab.runtime_fallback_notice(perspective_mode)
                if (
                    decision.lane in {"research", "workflow"}
                    and result.synthesis is None
                    and owner_output is None
                    and not generic_owner_requested
                )
                else ""
            )
            answer_prefix = "\n\n".join(
                block for block in (perspective_header, fallback_notice) if block
            )
            answer_text = sanitize_conversation_answer(
                "\n\n".join(block for block in (answer_prefix, answer_text) if block)
            )
            answer_text = _sanitize_market_cause_answer_text(answer_text, query)
            fulfillment_outputs = (
                generic_contract.required_outputs
                if generic_contract is not None
                else _specialized_owner_required_outputs(
                    owner_output,
                    task_frame,
                )
            )
            if fulfillment_outputs and result.answer_spec is not None:
                fulfillment = task_fulfillment.evaluate_answer_spec_fulfillment(
                    question=task_frame.raw_question,
                    required_outputs=fulfillment_outputs,
                    answer_text=answer_text,
                    answer_spec=result.answer_spec,
                )
                result.answer_status = fulfillment.status
                result.fulfillment_report = fulfillment.to_dict()
                result.fulfillment_report["task_frame_hash"] = (
                    task_frame.task_frame_hash
                )
                report["task_fulfillment"] = result.fulfillment_report
                self._trace(
                    run_id,
                    assistant_message_id,
                    conversation_id,
                    "task_fulfillment",
                    "task_fulfillment",
                    result.fulfillment_report,
                )
                if fulfillment.status != "complete":
                    # 只标 status 不够：result.synthesis 会优先于 AnswerSpec
                    # 渲染，仍可能把答非所问草稿发给用户。切到现有
                    # evidence-gap renderer，保留缺口而不是重写成另一份模板。
                    result.synthesis = None
                    result.answer_spec = task_fulfillment.fail_closed_answer_spec(
                        result.answer_spec,
                        fulfillment,
                    )
                    answer_text = render_conversation_answer(result)
                    warning = "最终回答未完成任务契约，已按部分完成标记。"
                    if warning not in warnings:
                        warnings.append(warning)
                        self.run_store.add_degrade(run_id, warning)
            elif result.answer_status == "unknown":
                # Deterministic heads and explicit skill owners keep their
                # existing verifier outcome until they expose a TurnContract.
                result.answer_status = (
                    result.business_status
                    if result.business_status
                    in {"complete", "partial", "gap", "missing"}
                    else "complete"
                )
            turn_intent = replace(
                turn_intent,
                skill_ids=(
                    tuple(dict.fromkeys((*invoked, *selected)))
                    if skill_mode == "manual"
                    else tuple(
                        dict.fromkeys((*turn_intent.skill_ids, *invoked, *selected))
                    )
                ),
            )
            research_plan = ResearchPlan.from_intent(turn_intent)
            followup_payload: list[dict[str, object]] = []
            if result.answer_spec is not None:
                atom_ids = tuple(
                    atom.atom_id
                    for atom in answer_model.evidence_atoms_from_answer_spec(
                        result.answer_spec
                    )
                )
                stage_artifact_ids = tuple(
                    ":".join(
                        part
                        for part in (
                            artifact.producer,
                            artifact.stage,
                            artifact.input_hash,
                        )
                        if part
                    )
                    for artifact in result.answer_spec.research_artifacts
                )
                turn_intent = replace(
                    turn_intent,
                    evidence_atom_ids=atom_ids,
                    stage_artifact_ids=stage_artifact_ids,
                )
                research_plan = ResearchPlan.from_intent(turn_intent)
                followup_result = followups_svc.generate_answer_spec_followups(
                    result.answer_spec,
                    subject=turn_intent.primary_subject,
                )
                followup_payload = [
                    asdict(followup) for followup in followup_result.followups
                ]
                self._trace(
                    run_id,
                    assistant_message_id,
                    conversation_id,
                    "validate",
                    "evidence_atom_validation",
                    {
                        "status": "completed",
                        "evidence_atom_count": len(atom_ids),
                        "evidence_atom_ids": list(atom_ids),
                        "stage_artifact_ids": list(stage_artifact_ids),
                        "quality_gate": (
                            result.llm_fallback_reason
                            or "structured_claim_ids_validated"
                        ),
                    },
                )
            if (
                decision.lane in {"research", "workflow"}
                and decision.needs_template is True
                and not generic_owner_requested
                and result.synthesis is None
                and owner_output is None
                and (
                    result.answer_spec is None
                    or result.answer_spec.presentation_kind != "evidence_gap"
                )
            ):
                fallback = "llm_unavailable_template_answer"
                warnings.append(fallback)
                self.run_store.add_degrade(run_id, fallback)
            if has_answer_snapshot:
                text_chunks.append(answer_text)
                self._emit(
                    run_id,
                    assistant_message_id,
                    "answer:snapshot:2",
                    "answer.snapshot",
                    AnswerSnapshot(
                        revision=2,
                        phase=(
                            "evidence_gap_fallback"
                            if result.answer_status != "complete"
                            else (
                                "decision_brief_fallback"
                                if result.answer_spec is not None
                                and result.answer_spec.presentation_kind
                                == "generic_research"
                                else "verified_fallback"
                            )
                            if result.grounded_fallback_used
                            else "validated_synthesis"
                            if result.synthesis is not None
                            # 质检未过的模板降级不得伪装成 verified：
                            # 此时 render 层已 fail-closed 为证据缺口短答。
                            else (
                                "evidence_gap_fallback"
                                if (
                                    result.answer_spec is not None
                                    and (
                                        result.answer_spec.presentation_kind
                                        == "evidence_gap"
                                        or answer_model.quality_requires_fail_closed(
                                            result.answer_spec
                                        )
                                    )
                                )
                                else "verified_fallback"
                            )
                        ),
                        text=answer_text,
                        final=True,
                    ).payload(),
                    conversation_id,
                )
            elif not text_chunks or text_chunks[-1] != answer_text:
                emit_text_delta(answer_text)

            if (
                prepared.options.shadow_grounded_composer
                and result.answer_spec is not None
                and result.answer_spec.presentation_kind
                not in {"market_technical", "evidence_gap"}
            ):
                try:
                    synthesize_shadow_grounded_answer(
                        PreparedAnswer(
                            options=prepared.options,
                            result=result,
                        )
                    )
                except Exception as exc:
                    result.grounded_composer_shadow = (
                        answer_model.GroundedComposerShadow(
                            status="internal_error",
                            failure_reason=type(exc).__name__,
                        )
                    )
                shadow = result.grounded_composer_shadow
                self._trace(
                    run_id,
                    assistant_message_id,
                    conversation_id,
                    "shadow_synthesize",
                    "grounded_composer_shadow",
                    (shadow.to_dict() if shadow is not None else {"status": "not_run"}),
                )

            llm_ledger = llm_refine.current_call_ledger()
            if llm_ledger is not None and llm_ledger.records:
                ledger_summary = llm_ledger.summary()
                self._trace(
                    run_id,
                    assistant_message_id,
                    conversation_id,
                    "llm_budget",
                    "llm_call_ledger",
                    {
                        "summary": (
                            f"本轮 LLM 调用 {ledger_summary['call_count']} 次"
                            f"（失败 {ledger_summary['failure_count']} 次，"
                            f"合计 {ledger_summary['total_elapsed_ms']}ms）"
                        ),
                        "by_caller": ledger_summary["by_caller"],
                        "records": ledger_summary["records"],
                    },
                )
            turn_query_ledger = query_ledger.current_query_ledger()
            if turn_query_ledger is not None and turn_query_ledger.entries:
                query_summary = turn_query_ledger.summary()
                self._trace(
                    run_id,
                    assistant_message_id,
                    conversation_id,
                    "query_budget",
                    "query_ledger",
                    {
                        "summary": (
                            f"本轮外部检索真实执行 {query_summary['executed_count']} 次，"
                            f"账本去重 {query_summary['deduped_count']} 次"
                        ),
                        "by_provider": query_summary["by_provider"],
                        "records": query_summary["records"],
                    },
                )
            # 研究预算必须在 owner/agent loop 完成后发布。旧位置位于
            # GenericResearchOwner 之前，长尾问题会看到“研究工具 0 次”，
            # 而 query/LLM 台账已经真实消耗，造成预算重复计算和 trace 断裂。
            # 保留旧的 research_budget 字段，同时把同一 turn 的 LLM/查询计数
            # 放入同一控制面事件，展示层不读取这些内部明细。
            budget_trace = research_budget.to_trace()
            shared_ledger: dict[str, object] = {}
            if llm_ledger is not None and llm_ledger.records:
                shared_ledger["llm"] = {
                    "call_count": ledger_summary["call_count"],
                    "failure_count": ledger_summary["failure_count"],
                }
            if turn_query_ledger is not None and turn_query_ledger.entries:
                shared_ledger["queries"] = {
                    "executed_count": query_summary["executed_count"],
                    "deduped_count": query_summary["deduped_count"],
                }
            self._trace(
                run_id,
                assistant_message_id,
                conversation_id,
                "budget",
                "research_execution_budget",
                {
                    "summary": (
                        f"研究工具调用 {budget_trace['call_count']} 次，"
                        f"记录 {budget_trace['attempt_count']} 次尝试"
                    ),
                    "elapsed_ms": budget_trace["elapsed_ms"],
                    "shared_ledger": shared_ledger,
                },
                retrieval={
                    "research_budget": budget_trace,
                    "shared_ledger": shared_ledger,
                },
            )
            complete_report(
                report,
                as_of=result.trade_date,
                warnings=warnings,
                llm_provider=result.llm_provider,
                llm_model=answer_model_name if result.llm_provider else None,
                business_status=result.business_status,
                answer_status=result.answer_status,
            )
            public_report = _redact_object(report)
            if isinstance(public_report, dict):
                report = public_report
            self.run_store.add_artifact(
                run_id,
                "answer.md",
                redact(answer_text),
                renderer="markdown",
                title=redact(f"对话回答：{query[:24]}"),
            )
            if result.answer_spec is not None:
                self.run_store.add_artifact(
                    run_id,
                    "answer_spec.json",
                    json.dumps(
                        result.answer_spec.to_dict(),
                        ensure_ascii=False,
                        indent=2,
                    ),
                    renderer="json",
                    title="回答事实边界",
                )
                self.run_store.add_artifact(
                    run_id,
                    "followups.json",
                    json.dumps(
                        {
                            "followups": followup_payload,
                            "llm_used": False,
                            "llm_provider": None,
                            "warnings": [],
                        },
                        ensure_ascii=False,
                        indent=2,
                    ),
                    renderer="json",
                    title="猜你想问",
                )
            if result.grounded_composer_shadow is not None:
                shadow_payload = result.grounded_composer_shadow.to_dict()
                if result.grounded_composer_shadow.decision_brief is not None:
                    shadow_brief = result.grounded_composer_shadow.decision_brief
                    decision_brief_payload = shadow_brief.to_dict()
                    self.run_store.add_artifact(
                        run_id,
                        "decision_brief.json",
                        redact(
                            json.dumps(
                                decision_brief_payload,
                                ensure_ascii=False,
                                indent=2,
                            )
                        ),
                        renderer="json",
                        title="影子论证计划",
                    )
                self.run_store.add_artifact(
                    run_id,
                    "grounded_composer_shadow.json",
                    redact(
                        json.dumps(
                            shadow_payload,
                            ensure_ascii=False,
                            indent=2,
                        )
                    ),
                    renderer="json",
                    title="Grounded Composer 影子实验",
                )
                if (
                    result.grounded_composer_shadow.status in {"accepted", "repaired"}
                    and result.grounded_composer_shadow.presented_answer is not None
                ):
                    self.run_store.add_artifact(
                        run_id,
                        "grounded_composer_shadow.md",
                        redact(result.grounded_composer_shadow.presented_answer),
                        renderer="markdown",
                        title="Grounded Composer 影子答案",
                    )
            self.run_store.add_artifact(
                run_id,
                "report.json",
                json.dumps(report, ensure_ascii=False, indent=2),
                renderer="structured_report",
                title="结构化对话报告",
            )
            self._check_cancelled()
            assistant = self.conversation_store.revise_message(
                conversation_id,
                assistant_message_id,
                content=answer_text,
                status="completed",
                selected_skill_ids=manual_selected,
                invoked_skill_ids=invoked,
                citations=citations,
                degrades=warnings,
                followups=followup_payload,
                turn_intent=turn_intent.to_dict(),
                research_plan=research_plan.to_dict(),
            )
            self._emit(
                run_id,
                assistant_message_id,
                "report:complete",
                "report.complete",
                {"report": report},
                conversation_id,
            )
            self._emit(
                run_id,
                assistant_message_id,
                "message:complete",
                "message.complete",
                {"message": asdict(assistant)},
                conversation_id,
            )
            self.run_store.finish_run(run_id, rs.STATUS_COMPLETED)
            return TurnResult(
                status=rs.STATUS_COMPLETED,
                content=assistant.content,
                selected_skill_ids=tuple(selected),
                invoked_skill_ids=tuple(invoked),
            )
        except LLMStreamCancelled:
            if self.cancellation_reason() == "executor_timeout":
                return self._fail(
                    conversation_id,
                    run_id,
                    assistant_message_id,
                    report,
                    selected,
                    manual_selected,
                    invoked,
                    warnings,
                    citations,
                    text_chunks,
                    TimeoutError("executor_timeout"),
                )
            return self._cancel(
                conversation_id,
                run_id,
                assistant_message_id,
                report,
                selected,
                manual_selected,
                invoked,
                warnings,
                citations,
                text_chunks,
            )
        except Exception as exc:  # noqa: BLE001
            return self._fail(
                conversation_id,
                run_id,
                assistant_message_id,
                report,
                selected,
                manual_selected,
                invoked,
                warnings,
                citations,
                text_chunks,
                exc,
            )

    def _complete_lane_turn(
        self,
        *,
        conversation_id: str,
        run_id: str,
        assistant_message_id: str,
        query: str,
        report: dict,
        answer: LaneAnswer,
        selected_skill_ids: Sequence[str],
        turn_intent: TurnIntent,
        research_plan: ResearchPlan,
        citations: Sequence[dict[str, object]] = (),
        warnings: Sequence[str] = (),
        as_of: str | None = None,
    ) -> TurnResult:
        answer_text = sanitize_conversation_answer(answer.answer)
        self._emit(
            run_id,
            assistant_message_id,
            "answer:snapshot:1",
            "answer.snapshot",
            AnswerSnapshot(
                revision=1,
                phase="verified_draft",
                text=answer_text,
                final=False,
            ).payload(),
            conversation_id,
        )
        self._emit(
            run_id,
            assistant_message_id,
            "text:000001",
            "text.delta",
            {"delta": answer_text},
            conversation_id,
        )
        self._emit(
            run_id,
            assistant_message_id,
            "answer:snapshot:2",
            "answer.snapshot",
            AnswerSnapshot(
                revision=2,
                phase=(
                    "validated_synthesis"
                    if answer.provider is not None
                    else "verified_fallback"
                ),
                text=answer_text,
                final=True,
            ).payload(),
            conversation_id,
        )
        complete_report(
            report,
            as_of=as_of,
            warnings=list(warnings),
            llm_provider=answer.provider,
            llm_model=answer.model,
        )
        public_report = _redact_object(report)
        if isinstance(public_report, dict):
            report = public_report
        self.run_store.add_artifact(
            run_id,
            "answer.md",
            redact(answer_text),
            renderer="markdown",
            title=redact(f"对话回答：{query[:24]}"),
        )
        self.run_store.add_artifact(
            run_id,
            "report.json",
            json.dumps(report, ensure_ascii=False, indent=2),
            renderer="structured_report",
            title="结构化对话报告",
        )
        assistant = self.conversation_store.revise_message(
            conversation_id,
            assistant_message_id,
            content=answer_text,
            status="completed",
            selected_skill_ids=selected_skill_ids,
            invoked_skill_ids=(),
            citations=_sanitize_citation_list(list(citations)),
            degrades=tuple(warnings),
            turn_intent=turn_intent.to_dict(),
            research_plan=research_plan.to_dict(),
        )
        self._emit(
            run_id,
            assistant_message_id,
            "report:complete",
            "report.complete",
            {"report": report},
            conversation_id,
        )
        self._emit(
            run_id,
            assistant_message_id,
            "message:complete",
            "message.complete",
            {"message": asdict(assistant)},
            conversation_id,
        )
        self.run_store.finish_run(run_id, rs.STATUS_COMPLETED)
        return TurnResult(
            status=rs.STATUS_COMPLETED,
            content=assistant.content,
            selected_skill_ids=(),
            invoked_skill_ids=(),
        )

    def _complete_continuous_turn(
        self,
        *,
        conversation_id: str,
        run_id: str,
        assistant_message_id: str,
        query: str,
        report: dict[str, object],
        result: ContinuousTurnResult,
        task_frame: TaskFrame,
        selected_skill_ids: Sequence[str],
        turn_intent: TurnIntent,
        research_plan: ResearchPlan,
    ) -> TurnResult:
        """Persist one Episode-owned terminal result without legacy synthesis."""

        private_artifact = dict(result.private_artifact or {})
        private_artifact["task_frame"] = task_frame.to_dict()
        private_artifact["turn_intent"] = turn_intent.to_dict()
        safe_private_artifact = redact_value(private_artifact)
        warnings = list(dict.fromkeys(result.warnings))
        for warning in warnings:
            self.run_store.add_degrade(run_id, warning)
        if result.status == "degraded" and not warnings:
            warning = "连续研究已按证据边界降级。"
            warnings.append(warning)
            self.run_store.add_degrade(run_id, warning)

        for index, event in enumerate(result.events, start=1):
            self._emit(
                run_id,
                assistant_message_id,
                f"continuous:step:{index}",
                "trace.step",
                {
                    "step": {
                        "step_id": f"continuous:{index}",
                        "name": str(event.get("stage") or "research"),
                        "status": str(event.get("status") or "completed"),
                        "output_summary": str(event.get("message") or ""),
                    }
                },
                conversation_id,
            )
        citations = _sanitize_citation_list(list(result.citations))
        for index, citation in enumerate(citations, start=1):
            self._emit(
                run_id,
                assistant_message_id,
                f"continuous:citation:{index}",
                "citation.ready",
                {"citation": citation},
                conversation_id,
            )

        answer_text = redact(result.answer).strip()
        if result.status == "failed" or not answer_text:
            failure_text = answer_text or "本轮连续研究未取得可公开答案。"
            report["execution_kind"] = "continuous_episode"
            report["task_frame_hash"] = turn_intent.task_frame_hash
            report["turn_intent"] = turn_intent.to_dict()
            report["status"] = "blocked"
            report["transport_status"] = "failed"
            report["research_status"] = "blocked"
            report["answer_status"] = "missing"
            report["business_status"] = "blocked"
            report["as_of"] = result.as_of
            report["warnings"] = warnings
            self._check_cancelled()
            self._claim_terminal_run(
                run_id,
                rs.STATUS_FAILED,
                error="continuous_runtime_failed",
            )
            self.run_store.add_artifact(
                run_id,
                "continuous-episode.json",
                json.dumps(
                    safe_private_artifact,
                    ensure_ascii=False,
                    indent=2,
                ),
                renderer="json",
                title="连续研究私有审计",
            )
            self.run_store.add_artifact(
                run_id,
                "answer.md",
                failure_text,
                renderer="markdown",
                title=redact(f"对话回答：{query[:24]}"),
            )
            self.run_store.add_artifact(
                run_id,
                "report.json",
                json.dumps(
                    _redact_object(report),
                    ensure_ascii=False,
                    indent=2,
                ),
                renderer="structured_report",
                title="结构化对话报告",
            )
            assistant = self.conversation_store.revise_message(
                conversation_id,
                assistant_message_id,
                content=failure_text,
                status="failed",
                selected_skill_ids=list(selected_skill_ids),
                invoked_skill_ids=[],
                citations=citations,
                degrades=warnings,
                turn_intent=turn_intent.to_dict(),
                research_plan=research_plan.to_dict(),
            )
            self._emit(
                run_id,
                assistant_message_id,
                "report:error",
                "report.error",
                {"report": _redact_object(report)},
                conversation_id,
            )
            self._emit(
                run_id,
                assistant_message_id,
                "message:error",
                "message.error",
                {"message": asdict(assistant)},
                conversation_id,
            )
            return TurnResult(
                status=rs.STATUS_FAILED,
                content=assistant.content,
                selected_skill_ids=(),
                invoked_skill_ids=(),
            )

        report["execution_kind"] = "continuous_episode"
        report["turn_intent"] = turn_intent.to_dict()
        complete_report(
            report,
            as_of=result.as_of,
            warnings=warnings,
            llm_provider=None,
            llm_model=self.llm_model,
            business_status=("complete" if result.status == "completed" else "partial"),
            answer_status=("complete" if result.status == "completed" else "partial"),
        )
        public_report = _redact_object(report)
        if isinstance(public_report, dict):
            report = public_report
        self._check_cancelled()
        self._claim_terminal_run(run_id, rs.STATUS_COMPLETED)
        self.run_store.update_provenance(run_id, source_date=result.as_of)
        self.run_store.add_artifact(
            run_id,
            "answer.md",
            answer_text,
            renderer="markdown",
            title=redact(f"对话回答：{query[:24]}"),
        )
        self.run_store.add_artifact(
            run_id,
            "continuous-episode.json",
            json.dumps(
                safe_private_artifact,
                ensure_ascii=False,
                indent=2,
            ),
            renderer="json",
            title="连续研究私有审计",
        )
        self.run_store.add_artifact(
            run_id,
            "report.json",
            json.dumps(report, ensure_ascii=False, indent=2),
            renderer="structured_report",
            title="结构化对话报告",
        )
        assistant = self.conversation_store.revise_message(
            conversation_id,
            assistant_message_id,
            content=answer_text,
            status="completed",
            selected_skill_ids=list(selected_skill_ids),
            invoked_skill_ids=[],
            citations=citations,
            degrades=warnings,
            turn_intent=turn_intent.to_dict(),
            research_plan=research_plan.to_dict(),
        )
        self._emit(
            run_id,
            assistant_message_id,
            "continuous:text",
            "text.delta",
            {"delta": answer_text},
            conversation_id,
        )
        self._emit(
            run_id,
            assistant_message_id,
            "continuous:answer",
            "answer.snapshot",
            AnswerSnapshot(
                revision=1,
                phase=(
                    "validated_synthesis"
                    if result.status == "completed"
                    else "evidence_gap_fallback"
                ),
                text=answer_text,
                final=True,
            ).payload(),
            conversation_id,
        )
        self._emit(
            run_id,
            assistant_message_id,
            "report:complete",
            "report.complete",
            {"report": report},
            conversation_id,
        )
        self._emit(
            run_id,
            assistant_message_id,
            "message:complete",
            "message.complete",
            {"message": asdict(assistant)},
            conversation_id,
        )
        return TurnResult(
            status=rs.STATUS_COMPLETED,
            content=assistant.content,
            selected_skill_ids=(),
            invoked_skill_ids=(),
        )

    def _claim_terminal_run(
        self,
        run_id: str,
        status: str,
        *,
        error: str | None = None,
    ) -> None:
        """Linearize one terminal owner before publishing its terminal events."""

        terminal = self.run_store.finish_run(run_id, status, error=error)
        if terminal.status == status:
            return
        if terminal.status == rs.STATUS_CANCELLED:
            raise LLMStreamCancelled()
        raise RuntimeError(f"run terminal state already claimed: {terminal.status}")

    def _emit(
        self,
        run_id: str,
        message_id: str,
        event_id: str,
        event_type: str,
        payload: dict[str, object],
        conversation_id: str,
    ) -> None:
        self.run_store.append_stream_event(
            run_id,
            event_id=f"{self.event_id_prefix}{event_id}",
            event_type=event_type,
            payload=payload,
            conversation_id=conversation_id,
            message_id=message_id,
        )

    def _check_cancelled(self) -> None:
        if self.is_cancelled():
            raise LLMStreamCancelled()

    def _emit_module(
        self,
        run_id: str,
        message_id: str,
        conversation_id: str,
        report: dict,
        module: dict,
        event_id: str,
    ) -> None:
        public_module = _redact_object(module)
        if not isinstance(public_module, dict):
            return
        upsert_report_module(report, public_module)
        self._emit(
            run_id,
            message_id,
            event_id,
            "report.module",
            {"module": public_module},
            conversation_id,
        )

    def _run_answer_query_with_watchdog(
        self,
        options: AskOptions,
        *,
        run_id: str,
        message_id: str,
        conversation_id: str,
        warnings: list[str],
    ) -> AskResult:
        """运行通用 Ask，并以 turn 根 deadline 作为最终返回上限。

        各 provider 仍负责使用自己的 I/O timeout；本看门狗只保证用户请求
        不被一个遗漏 cooperative deadline 的同步调用无限阻塞。
        """

        progress_open = Event()
        progress_open.set()
        progress_lock = Lock()
        progress_sequence = 0

        def record_progress(
            stage: str,
            stage_status: str,
            detail: dict[str, object],
        ) -> None:
            nonlocal progress_sequence
            if not progress_open.is_set():
                return
            with progress_lock:
                if not progress_open.is_set():
                    return
                progress_sequence += 1
                sequence = progress_sequence
            safe_stage = re.sub(r"[^a-zA-Z0-9_]+", "_", stage).strip("_")
            safe_stage = safe_stage[:48] or "unknown"
            trace_status = {
                "started": "running",
                "completed": "completed",
                "failed": "failed",
            }.get(stage_status, "completed")
            self._trace(
                run_id,
                message_id,
                conversation_id,
                f"ask:{sequence:03d}:{safe_stage}:{stage_status}",
                f"ask_stage_{safe_stage}",
                {
                    "stage": safe_stage,
                    "stage_status": stage_status,
                    **detail,
                },
                status=trace_status,
            )

        original_text_delta = options.stream_text_delta
        original_cancel_check = options.stream_cancel_check

        def guarded_text_delta(delta: str) -> None:
            if progress_open.is_set() and original_text_delta is not None:
                original_text_delta(delta)

        def guarded_cancel_check() -> bool:
            return not progress_open.is_set() or (
                original_cancel_check is not None and original_cancel_check()
            )

        guarded_options = replace(
            options,
            progress_callback=record_progress,
            stream_text_delta=guarded_text_delta,
            stream_cancel_check=guarded_cancel_check,
        )
        deadline = guarded_options.deadline
        if deadline is None:
            deadline = ResearchDeadline.from_timeout(
                self.research_policy.max_elapsed_seconds
            )
            guarded_options = replace(guarded_options, deadline=deadline)

        future: Future[AskResult] | None = None
        try:
            if deadline.expired:
                timeout_warning = "通用研究主链达到统一截止时间，已返回结构化缺口。"
                if timeout_warning not in warnings:
                    warnings.append(timeout_warning)
                    self.run_store.add_degrade(run_id, timeout_warning)
                self._trace(
                    run_id,
                    message_id,
                    conversation_id,
                    "ask:root:timeout",
                    "ask_root_timeout",
                    {"remaining_ms": 0, "worker_started": False},
                    status="failed",
                )
                return _deadline_partial_result(options.query, warnings)

            run_context = contextvars.copy_context()
            future = Future()

            def run_answer_query() -> None:
                assert future is not None
                if not future.set_running_or_notify_cancel():
                    return
                try:
                    answer_result = run_context.run(
                        self.answer_query,
                        guarded_options,
                    )
                except BaseException as exc:
                    future.set_exception(exc)
                else:
                    future.set_result(answer_result)

            worker = Thread(
                target=run_answer_query,
                name="workbench-ask-watchdog",
                daemon=True,
            )
            worker.start()
            while True:
                self._check_cancelled()
                remaining = deadline.remaining()
                if remaining <= 0:
                    timeout_warning = "通用研究主链达到统一截止时间，已返回结构化缺口。"
                    if timeout_warning not in warnings:
                        warnings.append(timeout_warning)
                        self.run_store.add_degrade(run_id, timeout_warning)
                    self._trace(
                        run_id,
                        message_id,
                        conversation_id,
                        "ask:root:timeout",
                        "ask_root_timeout",
                        {
                            "remaining_ms": 0,
                            "worker_started": True,
                            "task_may_continue": not future.done(),
                        },
                        status="failed",
                    )
                    return _deadline_partial_result(options.query, warnings)
                try:
                    return future.result(timeout=min(0.05, remaining))
                except FuturesTimeoutError:
                    if future.done():
                        return future.result()
        finally:
            progress_open.clear()
            if future is not None and not future.done():
                future.cancel()

    def _trace(
        self,
        run_id: str,
        message_id: str,
        conversation_id: str,
        step_id: str,
        name: str,
        output: dict[str, object],
        *,
        retrieval: dict[str, object] | None = None,
        status: str = "completed",
    ) -> None:
        step = self.run_store.append_step(
            run_id,
            step_id=step_id,
            name=name,
            status=status,
            output_summary=json.dumps(output, ensure_ascii=False),
            retrieval=retrieval,
        )
        self._emit(
            run_id,
            message_id,
            f"trace:{step_id}",
            "trace.step",
            {"step": step},
            conversation_id,
        )

    def _record_retrieval(
        self,
        run_id: str,
        message_id: str,
        conversation_id: str,
        result: AskResult,
        *,
        elapsed_ms: int,
    ) -> None:
        wiki_telemetry = result.wiki_rag_telemetry
        citation_counts: dict[str, int] = {}
        citation_records: list[dict[str, str]] = []
        for citation in result.citations:
            prefix = citation.tag[:1]
            if prefix:
                citation_counts[prefix] = citation_counts.get(prefix, 0) + 1
            citation_records.append(
                {
                    "tag": citation.tag,
                    "source": citation.source,
                    "detail": citation.detail,
                }
            )
        self._trace(
            run_id,
            message_id,
            conversation_id,
            "retrieve",
            "ask_retrieve_compose",
            {
                "trade_date": result.trade_date,
                "matched_theme": result.matched_theme,
                "citation_count": len(result.citations),
                "elapsed_ms": elapsed_ms,
                "wiki_rag": (
                    {
                        "status": wiki_telemetry.status,
                        "requested_mode": wiki_telemetry.requested_mode,
                        "effective_mode": wiki_telemetry.effective_mode,
                        "fallback_reason": wiki_telemetry.fallback_reason,
                        "hit_count": wiki_telemetry.hit_count,
                        "latency_ms": wiki_telemetry.latency_ms,
                    }
                    if wiki_telemetry is not None
                    else None
                ),
                "closed_loop_retrieval": (
                    result.closed_loop_retrieval.inspector_dict()
                    if result.closed_loop_retrieval is not None
                    else None
                ),
                # GenericResearchOwner 的完成度是控制面审计字段；展示层只
                # 消费 AnswerSpec，不把内部 missing/gap 诊断拼进正文。
                "completion_report": result.completion_report,
                "provider_traces": [
                    trace.to_dict() for trace in result.provider_traces
                ],
            },
            retrieval={
                "citations": citation_records,
                "citation_counts": citation_counts,
            },
        )

    @staticmethod
    def _elapsed_ms(started: float) -> int:
        return max(0, round((time.monotonic() - started) * 1000))

    def _ensure_terminal_safe_snapshot(
        self,
        *,
        run_id: str,
        message_id: str,
        conversation_id: str,
        fallback_text: str,
    ) -> str:
        snapshots = [
            event
            for event in self.run_store.load_stream_events(run_id)
            if event["event_type"] == "answer.snapshot"
        ]
        if not snapshots:
            return fallback_text
        latest = max(
            snapshots,
            key=lambda event: int(event["payload"]["revision"]),
        )
        payload = latest["payload"]
        latest_text = str(payload["text"])
        if payload["final"] is True:
            return latest_text
        revision = int(payload["revision"]) + 1
        self._emit(
            run_id,
            message_id,
            f"answer:snapshot:{revision}",
            "answer.snapshot",
            AnswerSnapshot(
                revision=revision,
                phase="verified_fallback",
                text=latest_text,
                final=True,
            ).payload(),
            conversation_id,
        )
        return latest_text

    def _cancel(
        self,
        conversation_id: str,
        run_id: str,
        message_id: str,
        report: dict,
        selected: list[str],
        manual_selected: list[str],
        invoked: list[str],
        warnings: list[str],
        citations: list[dict[str, object]],
        text_chunks: list[str],
    ) -> TurnResult:
        warning = "用户已取消本轮执行"
        if warning not in warnings:
            warnings.append(warning)
        self.run_store.add_degrade(run_id, warning)
        report["status"] = rs.STATUS_CANCELLED
        report["warnings"] = list(dict.fromkeys(warnings))
        content = self._ensure_terminal_safe_snapshot(
            run_id=run_id,
            message_id=message_id,
            conversation_id=conversation_id,
            fallback_text=sanitize_conversation_answer(
                text_chunks[-1] if text_chunks else ""
            ),
        )
        assistant = self.conversation_store.revise_message(
            conversation_id,
            message_id,
            content=content,
            status=rs.STATUS_CANCELLED,
            selected_skill_ids=manual_selected,
            invoked_skill_ids=invoked,
            citations=citations,
            degrades=warnings,
        )
        self.run_store.add_artifact(
            run_id,
            "answer.md",
            redact(content),
            renderer="markdown",
            title="已取消的对话回答",
        )
        self.run_store.add_artifact(
            run_id,
            "report.json",
            json.dumps(_redact_object(report), ensure_ascii=False, indent=2),
            renderer="structured_report",
            title="已取消的结构化对话报告",
        )
        self._emit(
            run_id,
            message_id,
            "message:cancelled",
            "message.error",
            {"status": rs.STATUS_CANCELLED, "message": asdict(assistant)},
            conversation_id,
        )
        self.run_store.finish_run(run_id, rs.STATUS_CANCELLED)
        return TurnResult(
            status=rs.STATUS_CANCELLED,
            content=assistant.content,
            selected_skill_ids=tuple(selected),
            invoked_skill_ids=tuple(invoked),
        )

    def _fail(
        self,
        conversation_id: str,
        run_id: str,
        message_id: str,
        report: dict,
        selected: list[str],
        manual_selected: list[str],
        invoked: list[str],
        warnings: list[str],
        citations: list[dict[str, object]],
        text_chunks: list[str],
        error: Exception,
    ) -> TurnResult:
        warning = f"本轮执行失败（{type(error).__name__}）"
        warnings.append(warning)
        report["status"] = rs.STATUS_FAILED
        report["warnings"] = list(dict.fromkeys(warnings))
        content = self._ensure_terminal_safe_snapshot(
            run_id=run_id,
            message_id=message_id,
            conversation_id=conversation_id,
            fallback_text=sanitize_conversation_answer(
                text_chunks[-1] if text_chunks else ""
            ),
        )
        assistant = self.conversation_store.revise_message(
            conversation_id,
            message_id,
            content=content,
            status=rs.STATUS_FAILED,
            selected_skill_ids=manual_selected,
            invoked_skill_ids=invoked,
            citations=citations,
            degrades=warnings,
        )
        self.run_store.add_artifact(
            run_id,
            "answer.md",
            redact(content),
            renderer="markdown",
            title="失败前保留的对话回答",
        )
        self._emit(
            run_id,
            message_id,
            "report:error",
            "report.error",
            {"report": report},
            conversation_id,
        )
        self._emit(
            run_id,
            message_id,
            "message:error",
            "message.error",
            {"status": rs.STATUS_FAILED, "message": asdict(assistant)},
            conversation_id,
        )
        self.run_store.finish_run(
            run_id,
            rs.STATUS_FAILED,
            error=warning,
        )
        return TurnResult(
            status=rs.STATUS_FAILED,
            content=assistant.content,
            selected_skill_ids=tuple(selected),
            invoked_skill_ids=tuple(invoked),
        )

    def _load_answer_spec(self, run_id: str | None) -> dict[str, object] | None:
        if not run_id:
            return None
        path = self.run_store.run_dir(run_id) / "answer_spec.json"
        if not path.is_file():
            return None
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return value if isinstance(value, dict) else None

    @staticmethod
    def _json_object_tuple(
        value: dict[str, object] | None,
        key: str,
    ) -> tuple[dict[str, object], ...]:
        if value is None:
            return ()
        items = value.get(key)
        if not isinstance(items, list):
            return ()
        return tuple(dict(item) for item in items if isinstance(item, dict))

    @staticmethod
    def _skill_evidence(outputs: Sequence[SkillOutput]) -> str:
        if not outputs:
            return ""
        lines: list[str] = []
        for output in outputs:
            as_of = f"（截至 {output.as_of}）" if output.as_of else ""
            lines.append(f"### {output.skill_id}{as_of}")
            for module in output.modules:
                title = module.get("title")
                if isinstance(title, str) and title.strip():
                    lines.append(f"- {title.strip()}")
                summary = module.get("summary")
                if isinstance(summary, str) and summary.strip():
                    lines.append(f"  - 摘要：{summary.strip()}")
                content = module.get("content")
                if isinstance(content, str) and content.strip():
                    lines.append(f"  - 正文：{content.strip()}")
                metrics = module.get("metrics")
                if isinstance(metrics, list):
                    metric_bits: list[str] = []
                    for metric in metrics:
                        if not isinstance(metric, dict):
                            continue
                        label = metric.get("label")
                        value = metric.get("value")
                        if isinstance(label, str) and value is not None:
                            metric_bits.append(f"{label}={value}")
                    if metric_bits:
                        lines.append("  - 指标：" + "；".join(metric_bits))
                items = module.get("items")
                if isinstance(items, list):
                    for item in items:
                        if not isinstance(item, dict):
                            continue
                        title = item.get("title")
                        summary = item.get("summary")
                        if not isinstance(summary, str) or not summary.strip():
                            continue
                        prefix = (
                            f"{title.strip()}："
                            if isinstance(title, str) and title.strip()
                            else ""
                        )
                        lines.append(f"  - {prefix}{summary.strip()}")
            if output.warnings:
                lines.append("- 数据质量提示：" + "；".join(output.warnings[:3]))
        return "\n".join(lines)

    @staticmethod
    def _skill_claim_bundle(
        outputs: Sequence[SkillOutput],
    ) -> tuple[tuple[answer_model.Claim, ...], tuple[Citation, ...]]:
        """把非 owner skill 的结构化模块接入统一 claim/citation 通道。

        ``supplemental_evidence`` 仍保留给模型做上下文阅读；这里额外铸造
        候选 claim，确保 Grounded Presenter 的 registry 能合法引用这些事实，
        而不是出现“skill 查到了、合成层却看不见”的半死证据。
        """

        claims: list[answer_model.Claim] = []
        citations: list[Citation] = []
        for output in outputs:
            if not output.modules or not output.citations:
                continue
            tags: list[str] = []
            for citation in output.citations[:8]:
                if not isinstance(citation, dict):
                    continue
                tag = f"SK{len(citations) + 1}"
                source = str(
                    citation.get("title") or citation.get("source") or output.skill_id
                )
                detail = str(citation.get("source") or "")
                citations.append(Citation(tag, source, detail))
                tags.append(tag)
            if not tags:
                continue
            for module_index, module in enumerate(output.modules, start=1):
                if not isinstance(module, dict):
                    continue
                bits: list[str] = []
                for key in ("title", "summary", "content"):
                    value = module.get(key)
                    if isinstance(value, str) and value.strip():
                        bits.append(value.strip())
                if not bits:
                    continue
                text = "：".join(bits[:2])[:600]
                claims.append(
                    answer_model.make_claim(
                        claim_id=f"skill:{output.skill_id}:{module_index}",
                        text=text,
                        claim_type="theme_evidence",
                        theme=output.skill_id,
                        status=answer_model.ClaimStatus.CANDIDATE,
                        evidence_tier="skill_candidate",
                        evidence_ids=tuple(tags),
                    )
                )
        return tuple(claims), tuple(citations)

    @staticmethod
    def _skill_warning_module(skill_id: str, warning: str) -> dict[str, object]:
        return {
            "module_id": f"skill_{skill_id}_warning",
            "title": f"{skill_id} 降级",
            "kind": "warning",
            "status": "degraded",
            "summary": warning,
            "content": None,
            "metrics": [],
            "items": [],
            "table": None,
            "warnings": [warning],
            "provenance": {
                "source": skill_id,
                "as_of": None,
                "generated_by": "turn_orchestrator",
            },
        }
