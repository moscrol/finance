from __future__ import annotations

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

from intelligence.api.structured_reports import (
    ask_result_modules,
    complete_report,
    new_structured_report,
    render_daily_review_answer,
    upsert_report_module,
)
from intelligence.services import answer_model, followups as followups_svc
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
from intelligence.services.answer_orchestrator import (
    QUESTION_CONCEPT_DEFINITION,
    QUESTION_MARKET_REVIEW,
    plan_answer_question,
)
from intelligence.services.conversation_store import (
    Conversation,
    ConversationStore,
    Message,
)
from intelligence.services.llm_refine import LLMStreamCancelled
from intelligence.services.lane_generation import (
    LaneAnswer,
    generate_lane_answer,
    knowledge_evidence,
    render_knowledge_fallback,
)
from intelligence.services import perspective_lab
from intelligence.services.query_understanding import understand_query
from intelligence.services.research_policy import (
    ResearchExecutionBudget,
    ResearchExecutionPolicy,
)
from intelligence.services.research_contract import (
    OWNER_WORKFLOW_SPECS,
    ResearchDeadline,
    ResearchPlan,
    TurnIntent,
    build_turn_intent,
    contextualize_intent_query,
)
from intelligence.services.run_store import RunStore, redact
from intelligence.services.turn_controller import TurnDecision, decide_turn
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


def _parallel_skills_enabled() -> bool:
    return os.environ.get("WORKBENCH_PARALLEL_SKILLS", "1").strip().lower() not in {
        "0",
        "false",
        "off",
    }


_INTERNAL_CITATION_PATTERN = re.compile(
    r"\[(?:D|P|L|G|R|S|W)\d+\]"
)
_INTERNAL_CODE_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_])[DPGRSW]\d+(?![A-Za-z0-9_])"
)
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


def _skill_owner_result(query: str, output: SkillOutput) -> AskResult:
    contract = output.answer_contract
    if contract is None:
        raise ValueError("skill owner output requires an answer contract")
    citations = [
        Citation(
            tag=f"K{index}",
            source=str(
                citation.get("title")
                or citation.get("source")
                or output.skill_id
            ),
            detail=str(citation.get("source") or ""),
        )
        for index, citation in enumerate(output.citations, start=1)
    ]
    return AskResult(
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
        return {
            redact(str(key)): _redact_object(item)
            for key, item in value.items()
        }
    return value


def _sanitize_citation_list(
    citations: list[dict[str, object]],
) -> list[dict[str, object]]:
    sanitized: list[dict[str, object]] = []
    for citation in citations:
        item = dict(citation)
        for key in ("source", "detail", "label", "title"):
            value = item.get(key)
            if isinstance(value, str):
                item[key] = sanitize_user_visible_artifact_text(value)
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
    if re.search(r"HF_TOKEN|Hugging\s*Face", cleaned, re.IGNORECASE):
        return "外部语义检索当前不可用或受限，未使用其结果。"
    if _INTERNAL_RETRIEVAL_DIAGNOSTIC_PATTERN.search(cleaned):
        return "外部语义检索当前不可用或受限，未使用其结果。"
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
        "外部语义检索当前不可用或受限，未使用其结果。",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = _INTERNAL_FIELD_PATTERN.sub("", cleaned)
    cleaned = _EVIDENCE_LAYER_SUMMARY_PATTERN.sub("", cleaned)
    cleaned = _INTERNAL_CITATION_PATTERN.sub("", cleaned)
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
    cleaned = re.sub(
        r"公司基础资料(?:\s*(?:公司)?基础资料)+", "公司基础资料", cleaned
    )
    cleaned = re.sub(r"盘面信号(?:\s*盘面信号)+", "盘面信号", cleaned)
    cleaned = re.sub(r"盘面\s*盘面信号", "盘面信号", cleaned)
    cleaned = re.sub(
        r"(?<=[\u4e00-\u9fff])_(?:market_signal|market_context)\b",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"公告等硬证据\s*(?=(?:公告|订单|认证|量产|客户验证))", "", cleaned)
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
            self.research_policy.max_elapsed_seconds
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
            raw_envelope = understand_query(query)
            inherited_message = previous_turn_message(context)
            inherited_intent = (
                TurnIntent.from_dict(inherited_message.turn_intent)
                if inherited_message is not None
                else None
            )
            inherited_turn_id = (
                inherited_message.message_id
                if inherited_message is not None
                else None
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
            turn_intent = decision.turn_intent or build_turn_intent(
                query,
                raw_envelope,
                previous_intent=inherited_intent,
                previous_turn_id=inherited_turn_id,
            )
            research_plan = ResearchPlan.from_intent(turn_intent)
            decision = replace(
                decision,
                question_type=turn_intent.question_type,
                subject=turn_intent.primary_subject,
                turn_intent=turn_intent,
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
            routing_envelope = understand_query(contextual_query)
            report["task_type"] = decision.lane
            legacy_lane = (
                "knowledge"
                if routing_envelope.question_type == "concept_definition"
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
                if decision.lane == "knowledge" and lane_answer.fallback_reason:
                    retrieval_attempted = True
                    fallback_started = time.monotonic()
                    try:
                        result = self.answer_query(
                            AskOptions(
                                query=contextual_query,
                                user=self.run_store.user_id,
                                compose=False,
                                synthesize=False,
                                market_db_path=(
                                    self.repo_root
                                    / "db"
                                    / "market_feature_store.duckdb"
                                ),
                                conversation_context=context.to_prompt_block(),
                                include_memory_block=decision.needs_memory,
                                include_recall_block=decision.needs_memory,
                                question_type_override=QUESTION_CONCEPT_DEFINITION,
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
                                    "completed"
                                    if result.citations
                                    else "degraded"
                                ),
                                "citation_count": len(result.citations),
                                "elapsed_ms": self._elapsed_ms(fallback_started),
                            },
                        )
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
                    citations=lane_citations,
                    warnings=lane_warnings,
                    as_of=lane_as_of,
                )
            route_started = time.monotonic()
            if decision.lane == "knowledge":
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
                    else tuple(
                        dict.fromkeys((*turn_intent.skill_ids, *selected))
                    )
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
                    "router_skipped": decision.lane == "knowledge",
                    "controller_lane": decision.lane,
                    "query_envelope": routing_envelope.to_dict(),
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
                future = skill_pool.submit(
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
                        self.skill_registry.definitions[
                            skill_id
                        ].timeout_seconds,
                        research_budget.remaining_seconds,
                    )
                    output = future.result(
                        timeout=max(
                            0.001,
                            allowed_seconds
                            - (time.monotonic() - skill_started),
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
                    if output.answer_contract is not None:
                        pending_selections.clear()
                        execution_feedback.clear()
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
                        fallback_route_kwargs["answer_owner"] = (
                            turn_intent.answer_owner
                        )
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
                            "elapsed_ms": self._elapsed_ms(
                                fallback_route_started
                            ),
                        },
                    )
                    execution_feedback.clear()
                    if replacements:
                        for item in replacements:
                            if item.skill_id not in selected:
                                selected.append(item.skill_id)
                        pending_selections.extend(replacements)
            skill_pool.shutdown(wait=False, cancel_futures=True)
            budget_trace = research_budget.to_trace()
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
                },
                retrieval={"research_budget": budget_trace},
            )

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
            owner_output = next(
                (
                    output
                    for output in skill_outputs
                    if output.answer_contract is not None
                ),
                None,
            )
            daily_review_output = next(
                (
                    output
                    for output in skill_outputs
                    if output.skill_id == "daily-review"
                ),
                None,
            )
            market_review_requested = (
                plan_answer_question(contextual_query).question_type
                == QUESTION_MARKET_REVIEW
            )
            ask_options = AskOptions(
                query=contextual_query,
                date=(
                    daily_review_output.as_of
                    if daily_review_output is not None
                    and market_review_requested
                    else None
                ),
                user=self.run_store.user_id,
                compose=True,
                synthesize=False,
                compose_self_review=False,
                compose_revise_on_warn=False,
                market_db_path=self.repo_root
                / "db"
                / "market_feature_store.duckdb",
                conversation_context=context.to_prompt_block(),
                wiki_rag_cache_scope=(
                    f"{self.run_store.user_id}:{conversation_id or run_id}"
                ),
                supplemental_evidence=self._skill_evidence(skill_outputs),
                include_memory_block=decision.needs_memory,
                include_recall_block=decision.needs_memory,
                question_type_override=(
                    QUESTION_CONCEPT_DEFINITION
                    if decision.lane == "knowledge"
                    else turn_intent.question_type
                ),
                controller_capabilities=(
                    tuple(
                        dict.fromkeys((*decision.capabilities, "web_search"))
                    )
                    if route.base_finance_fallback
                    else decision.capabilities
                ),
                perspective_mode=perspective_mode,
                perspective_ids=tuple(selected_perspective_ids),
                stream_text_delta=capture_safe_text,
                stream_cancel_check=self.is_cancelled,
                deadline=research_deadline,
            )
            if owner_output is not None:
                result = _skill_owner_result(query, owner_output)
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
                    },
                )
            elif owner_timed_out:
                result = _deadline_partial_result(contextual_query, warnings)
                prepared = prepare_existing_answer(ask_options, result)
            else:
                result = self.answer_query(ask_options)
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
                    block
                    for block in (perspective_header, draft_text)
                    if block
                )
            )
            has_answer_snapshot = (
                result.answer_spec is not None
                and decision.lane in {"research", "workflow"}
            )
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
                        "validated"
                        if result.synthesis is not None
                        else "fallback"
                    ),
                    "fallback_reason": result.llm_fallback_reason,
                    "stream": result.llm_stream_telemetry,
                },
            )

            warnings.extend(result.warnings)
            for warning in result.warnings:
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
                )
                else ""
            )
            answer_prefix = "\n\n".join(
                block for block in (perspective_header, fallback_notice) if block
            )
            answer_text = sanitize_conversation_answer(
                "\n\n".join(
                    block for block in (answer_prefix, answer_text) if block
                )
            )
            turn_intent = replace(
                turn_intent,
                skill_ids=(
                    tuple(dict.fromkeys((*invoked, *selected)))
                    if skill_mode == "manual"
                    else tuple(
                        dict.fromkeys(
                            (*turn_intent.skill_ids, *invoked, *selected)
                        )
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
                    asdict(followup)
                    for followup in followup_result.followups
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
                and result.synthesis is None
                and owner_output is None
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
                            "validated_synthesis"
                            if result.synthesis is not None
                            else "verified_fallback"
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
                    (
                        shadow.to_dict()
                        if shadow is not None
                        else {"status": "not_run"}
                    ),
                )

            complete_report(
                report,
                as_of=result.trade_date,
                warnings=warnings,
                llm_provider=result.llm_provider,
                llm_model=answer_model_name if result.llm_provider else None,
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
                shadow_payload = (
                    result.grounded_composer_shadow.to_dict()
                )
                if (
                    result.grounded_composer_shadow.decision_brief
                    is not None
                ):
                    shadow_brief = (
                        result.grounded_composer_shadow.decision_brief
                    )
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
                    result.grounded_composer_shadow.status
                    in {"accepted", "repaired"}
                    and result.grounded_composer_shadow.presented_answer
                    is not None
                ):
                    self.run_store.add_artifact(
                        run_id,
                        "grounded_composer_shadow.md",
                        redact(
                            result.grounded_composer_shadow.presented_answer
                        ),
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
        citations: Sequence[dict[str, object]] = (),
        warnings: Sequence[str] = (),
        as_of: str | None = None,
    ) -> TurnResult:
        answer_text = sanitize_conversation_answer(answer.answer)
        self._emit(
            run_id,
            assistant_message_id,
            "text:000001",
            "text.delta",
            {"delta": answer_text},
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
    ) -> None:
        step = self.run_store.append_step(
            run_id,
            step_id=step_id,
            name=name,
            status="completed",
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
                lines.append(
                    "- 数据质量提示：" + "；".join(output.warnings[:3])
                )
        return "\n".join(lines)

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
