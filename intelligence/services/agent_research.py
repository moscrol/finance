"""受预算约束的 agent 检索循环（L3）：LLM 自主决定「查什么→够不够→换查法」。

现状主链是固定管线：代码决定检索几轮/用哪些块，LLM 只做分类和成稿；长尾问题
一旦不在预设轨道上，证据跑题也没有任何一步能纠偏。本模块把控制权反转：

- LLM 在循环里逐步决定下一个工具调用（kb_search / web_search / news_search），
  看到观察结果后自行判断继续检索、改写查询或 finish；
- 执行仍是确定性代码：工具白名单钳制、步数/时长预算硬上限、重复查询去重，
  每步写 ``ProviderTrace``，产出证据带来源可回查——审计性不丢；
- LLM 未配置/超时/输出不合法 → 已收集证据照常返回，主链行为可降级不中断。

灰度开关 ``ASK_AGENT_LOOP``：
- ``auto``（默认，2026-07-19 转正）：仅当 controller 能力需求含
  web_search/market_news（route 未命中任何 skill 的长尾兜底车道）时启用；
- ``off``：不启用；
- ``on``：所有 compose 问题启用。
"""
from __future__ import annotations

import inspect
import json
import os
import re
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace

from intelligence.services import llm_refine, market_news, web_research
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.research_contract import ResearchDeadline
from intelligence.services.research_state import EvidenceObservation, ResearchState

ENV_MODE = "ASK_AGENT_LOOP"
ENV_MAX_STEPS = "ASK_AGENT_MAX_STEPS"
MODE_OFF = "off"
MODE_AUTO = "auto"
MODE_ON = "on"
_VALID_MODES = (MODE_OFF, MODE_AUTO, MODE_ON)

DEFAULT_MAX_STEPS = 4
DEFAULT_LLM_TIMEOUT = 15
DEFAULT_TOTAL_SECONDS = 60.0
_MAX_OBSERVATION_CHARS = 900
# 工具描述注册表：system prompt 按「实际注册的工具」动态生成——宣传清单与
# 注册表不再可能漂移（此前静态 prompt 宣传未注册工具会触发"非法工具"中断）。
_TOOL_DESCRIPTIONS = {
    "kb_search": (
        "- kb_search：检索本地知识库（公司逻辑卡/题材/研究笔记），"
        "args: {\"query\": 检索式}"
    ),
    "web_search": (
        "- web_search：全网网页搜索（时效性事实/指数点位/宏观数据），"
        "args: {\"query\": 检索式}"
    ),
    "news_search": (
        "- news_search：财经资讯检索（近段时间新闻事件），"
        "args: {\"query\": 关键词}"
    ),
    "graph_lookup": (
        "- graph_lookup：查询本地知识图谱——概念命中与公司暴露分层"
        "（core/peripheral，附证据层级），发现新实体/新题材后先用它定位映射，"
        "args: {\"query\": 题材或公司名}"
    ),
    "evidence_lookup": (
        "- evidence_lookup：查询证据索引——公司/题材已登记的公告、研报证据"
        "条目（含日期与质量），args: {\"query\": 公司或题材名}"
    ),
    "l3_lookup": (
        "- l3_lookup：官方证据补查——运行时抓取公告/互动易等公司级硬证据"
        "（L3 层，比证据索引新），args: {\"query\": 公司名或题材}"
    ),
    "market_data": (
        "- market_data：本地盘面数据——按问题自动路由到时序直查/中期趋势/"
        "市场总览（DuckDB 确定性取数），args: {\"query\": 自然语言数据问题，"
        "如'XX题材近20日成交额趋势'}"
    ),
}
_TOOL_NAMES = (*_TOOL_DESCRIPTIONS, "finish")


def loop_mode() -> str:
    # 默认 auto（2026-07-19 转正）：仅 controller 能力含 web_search/market_news
    # 的长尾兜底车道启用 agent 补检索；头部 owner 意图不受影响。该 flag 此前
    # 默认 off 等待的安全基建（LLM 硬预算、QueryLedger 去重、Deadline 钳制、
    # candidate_facts 证据通道）已全部就位。ASK_AGENT_LOOP=off 可整体关闭。
    mode = str(os.environ.get(ENV_MODE) or MODE_AUTO).strip().lower()
    return mode if mode in _VALID_MODES else MODE_AUTO


def max_steps() -> int:
    try:
        value = int(os.environ.get(ENV_MAX_STEPS) or DEFAULT_MAX_STEPS)
    except ValueError:
        return DEFAULT_MAX_STEPS
    return max(1, min(value, 8))


def should_run(controller_capabilities: tuple[str, ...]) -> bool:
    mode = loop_mode()
    if mode == MODE_ON:
        return True
    if mode == MODE_AUTO:
        return bool(
            {"web_search", "market_news"}.intersection(controller_capabilities)
        )
    return False


@dataclass(frozen=True)
class AgentEvidence:
    """一条 agent 补检索证据：来源可回查（kb 路径 / web url / 资讯链接）。"""

    tool: str
    title: str
    detail: str  # excerpt / snippet / 日期+媒体
    source: str  # 用户可见来源标签或公开 URL
    internal_locator: str = ""  # 仅控制面追踪，不得进入 Citation/AnswerSpec
    source_date: str | None = None
    evidence_tier: str = ""
    supports: tuple[str, ...] = ()
    contradicts: tuple[str, ...] = ()
    independent_key: str = ""
    freshness: str = "unknown"

    def to_observation(self, evidence_id: str) -> EvidenceObservation:
        return EvidenceObservation(
            evidence_id=evidence_id,
            tool=self.tool,
            title=self.title,
            detail=self.detail,
            source=self.source,
            source_date=self.source_date,
            evidence_tier=self.evidence_tier,
            supports=self.supports,
            contradicts=self.contradicts,
            independent_key=self.independent_key,
            freshness=self.freshness,
        )


@dataclass(frozen=True)
class AgentStep:
    tool: str
    query: str
    reason: str
    observation: str
    hit_count: int
    elapsed_ms: int
    hypothesis_ids: tuple[str, ...] = ()
    stance: str = "context"

    def to_dict(self) -> dict[str, object]:
        return {
            "tool": self.tool,
            "query": self.query,
            "reason": self.reason,
            "observation": self.observation[:200],
            "hit_count": self.hit_count,
            "elapsed_ms": self.elapsed_ms,
            "hypothesis_ids": list(self.hypothesis_ids),
            "stance": self.stance,
        }


@dataclass
class AgentLoopResult:
    steps: list[AgentStep] = field(default_factory=list)
    evidence: list[AgentEvidence] = field(default_factory=list)
    traces: list[ProviderTrace] = field(default_factory=list)
    sufficient: bool | None = None
    assessment: str = ""
    gaps: tuple[str, ...] = ()
    stop_reason: str = ""
    research_state: ResearchState | None = None
    state_revision: int = 0

    def to_dict(self) -> dict[str, object]:
        return {
            "steps": [step.to_dict() for step in self.steps],
            "evidence_count": len(self.evidence),
            "sufficient": self.sufficient,
            "assessment": self.assessment,
            "gaps": list(self.gaps),
            "stop_reason": self.stop_reason,
            "research_state": (
                self.research_state.to_dict()
                if self.research_state is not None
                else None
            ),
            "state_revision": self.state_revision,
        }


@dataclass(frozen=True)
class AgentToolContext:
    """Cooperative absolute deadline passed to agent tools."""

    deadline: ResearchDeadline

    def remaining(self) -> float:
        return self.deadline.remaining()

    def timeout(self, configured_limit: float) -> float:
        timeout = self.deadline.stage_timeout(configured_limit)
        if timeout <= 0.001:
            raise TimeoutError("agent tool deadline expired")
        return timeout


# 工具执行器契约：query (+ 可选 context) -> (evidence 列表, 观察文本, trace)。
# 单参数 runner 继续兼容测试和外部扩展；内置 runner 都接收 context。
ToolRunner = Callable[..., tuple[list[AgentEvidence], str, ProviderTrace]]


def build_default_tools(
    kb_retrieve: Callable[[str, float], object],
) -> dict[str, ToolRunner]:
    """默认工具集：kb_search 由调用方注入（复用主链 kb_rag 配置），web/news 用现成 provider。"""

    def _kb_search(
        query: str,
        context: AgentToolContext,
    ) -> tuple[list[AgentEvidence], str, ProviderTrace]:
        rag = kb_retrieve(query, context.timeout(DEFAULT_TOTAL_SECONDS))
        hits = list(getattr(rag, "hits", ()) or ())[:5]
        evidence = [
            AgentEvidence(
                tool="kb_search",
                title=hit.title,
                detail=(hit.excerpt or "")[:160],
                source="本地知识库",
                internal_locator=hit.file_path,
            )
            for hit in hits
        ]
        observation = (
            "；".join(f"{item.title}：{item.detail[:80]}" for item in evidence)
            or f"无命中（{getattr(getattr(rag, 'telemetry', None), 'status', 'unknown')}）"
        )
        trace = ProviderTrace(
            provider="agent:kb_search",
            capability="agent_loop",
            status="success" if evidence else "empty",
            detail=query[:120],
            result_count=len(evidence),
        )
        return evidence, observation, trace

    def _web_search(
        query: str,
        context: AgentToolContext,
    ) -> tuple[list[AgentEvidence], str, ProviderTrace]:
        web = web_research.fetch_web_search(
            query,
            timeout=context.timeout(20.0),
        )
        evidence = [
            AgentEvidence(
                tool="web_search",
                title=item.title,
                detail=(item.snippet or "")[:160],
                source=item.url,
                source_date=(
                    match.group(0).replace("/", "-")
                    if (match := re.search(r"20\d{2}[-/]\d{1,2}[-/]\d{1,2}", f"{item.title} {item.snippet}"))
                    else None
                ),
                evidence_tier="public_web",
                independent_key=item.url,
            )
            for item in web.items[:5]
        ]
        observation = (
            "；".join(f"{item.title}：{item.detail[:80]}" for item in evidence)
            or f"无结果（{web.trace.status}：{web.trace.detail}）"
        )
        return evidence, observation, web.trace

    def _news_search(
        query: str,
        context: AgentToolContext,
    ) -> tuple[list[AgentEvidence], str, ProviderTrace]:
        news = market_news.fetch_eastmoney_news_result(
            query,
            timeout=context.timeout(8.0),
        )
        evidence = [
            AgentEvidence(
                tool="news_search",
                title=item.title,
                detail=f"{item.date} {item.source}",
                source=item.url,
                source_date=item.date[:10] or None,
                evidence_tier="news",
                independent_key=item.url,
            )
            for item in news.items[:6]
        ]
        observation = (
            "；".join(f"{item.detail}《{item.title}》" for item in evidence)
            or f"无资讯（{news.trace.status}：{news.trace.detail}）"
        )
        return evidence, observation, news.trace

    return {
        "kb_search": _kb_search,
        "web_search": _web_search,
        "news_search": _news_search,
    }


def build_graph_tools(knowledge) -> dict[str, ToolRunner]:
    """基于 KnowledgeAdapter 构建图谱/证据索引工具（P1-B agent 覆盖面扩展）。

    此前 agent 只有 kb/web/news 三个最弱工具，碰不到知识图谱与证据索引——
    发现新实体后无法定位公司映射、无法核对已登记证据。两个工具都是纯本地
    JSON 查询（快、零外呼），与固定管线 G/R provider 消费同一数据源。
    ``knowledge`` 为 KnowledgeAdapter（鸭子类型：get_concept_matches /
    get_exposure_matches / get_evidence）。"""

    def _graph_lookup(
        query: str,
        context: AgentToolContext | None = None,
    ) -> tuple[list[AgentEvidence], str, ProviderTrace]:
        del context
        concepts = knowledge.get_concept_matches(query, limit=5)
        exposures = knowledge.get_exposure_matches(query, limit=8)
        evidence: list[AgentEvidence] = []
        for item in (concepts.get("items") or [])[:5]:
            evidence.append(
                AgentEvidence(
                    tool="graph_lookup",
                    title=f"概念 {item.get('concept')}",
                    detail=f"匹配分 {item.get('score')}",
                    source="本地知识图谱",
                    internal_locator="wiki/relations/concept_graph.json",
                )
            )
        for row in (exposures.get("items") or [])[:8]:
            company = str(row.get("company") or "").strip()
            if not company:
                continue
            evidence.append(
                AgentEvidence(
                    tool="graph_lookup",
                    title=company,
                    detail=(
                        f"{row.get('concept')}｜{row.get('strength') or '?'}"
                        f"/{row.get('evidence_layer') or '?'}"
                    ),
                    source="本地知识图谱",
                    internal_locator="wiki/relations/entity_exposures.json",
                )
            )
        observation = (
            "；".join(f"{item.title}（{item.detail}）" for item in evidence)
            or "图谱无命中（概念与公司暴露均为空）"
        )
        trace = ProviderTrace(
            provider="agent:graph_lookup",
            capability="agent_loop",
            status="success" if evidence else "empty",
            detail=query[:120],
            result_count=len(evidence),
        )
        return evidence, observation, trace

    def _evidence_lookup(
        query: str,
        context: AgentToolContext | None = None,
    ) -> tuple[list[AgentEvidence], str, ProviderTrace]:
        del context
        bundle = knowledge.get_evidence(query, limit=6)
        evidence = [
            AgentEvidence(
                tool="evidence_lookup",
                title=str(item.get("target") or query),
                detail=(
                    f"{str(item.get('evidence'))[:120]}"
                    f"（{item.get('source')}，{item.get('source_date') or '无日期'}，"
                    f"质量 {item.get('confidence') or '?'}）"
                ),
                source="本地证据索引",
                internal_locator="wiki/relations/evidence_index.json",
            )
            for item in (bundle.get("items") or [])[:6]
            if isinstance(item, dict)
        ]
        observation = (
            "；".join(f"{item.title}：{item.detail}" for item in evidence)
            or "证据索引无命中"
        )
        trace = ProviderTrace(
            provider="agent:evidence_lookup",
            capability="agent_loop",
            status="success" if evidence else "empty",
            detail=query[:120],
            result_count=len(evidence),
        )
        return evidence, observation, trace

    return {
        "graph_lookup": _graph_lookup,
        "evidence_lookup": _evidence_lookup,
    }


def block_lines_to_evidence(
    tool: str,
    block: str,
    source: str,
    *,
    limit: int = 6,
) -> tuple[list[AgentEvidence], str]:
    """把确定性数据块文本（D 块/总览）转成 agent 证据行 + 观察摘要。

    跳过标题/空行，正文行截断为 title/detail；供 market_data 等包装
    确定性取数函数的工具复用。"""
    lines = [
        stripped
        for raw in str(block or "").splitlines()
        if (stripped := raw.strip().lstrip("-").strip())
        and not stripped.startswith("#")
    ]
    evidence: list[AgentEvidence] = []
    for line in lines[:limit]:
        date_match = re.search(r"20\d{2}[-/]\d{1,2}[-/]\d{1,2}", line)
        evidence.append(
            AgentEvidence(
                tool=tool,
                title=line[:48],
                detail=line[:200],
                source=source,
                source_date=(
                    date_match.group(0).replace("/", "-")
                    if date_match is not None
                    else None
                ),
                evidence_tier=(
                    "L4_structured" if tool == "market_data" else ""
                ),
            )
        )
    observation = "；".join(lines[:limit])
    return evidence, observation


def evidence_display_text(item: AgentEvidence) -> str:
    """Render one evidence item without repeating a title copied from its detail."""
    title = item.title.strip()
    detail = item.detail.strip()
    if not title:
        return detail
    if not detail:
        return title
    normalized_title = re.sub(r"\s+", "", title).rstrip("：:；;。. ")
    normalized_detail = re.sub(r"\s+", "", detail)
    if normalized_detail.startswith(normalized_title):
        return detail
    return f"{title}：{detail}"


CompleteFn = Callable[..., tuple[str | None, object, str]]

def _system_prompt(tools: dict[str, ToolRunner]) -> str:
    """按实际注册的工具动态生成 system prompt（宣传=注册，不会漂移）。"""
    tool_lines = [
        _TOOL_DESCRIPTIONS[name]
        for name in _TOOL_DESCRIPTIONS
        if name in tools
    ]
    return (
        "你是金融研究检索 agent。根据用户问题和已收集的证据，决定下一步动作。\n"
        "可用工具：\n"
        + "\n".join(tool_lines)
        + "\n- finish：证据足够或确认无法补齐时结束，"
        "args: {\"sufficient\": true/false, \"assessment\": \"覆盖任务要求的简洁分析草稿（只基于已有证据）\", \"gaps\": [\"仍缺什么\"]}\n"
        "原则：\n"
        "1. 检索结果与问题无关时要改写检索式或换工具，不要把无关结果当证据；\n"
        "2. 同一检索式不要重复；证据足够就尽早 finish；\n"
        "3. 工具 args 可选 hypothesis_ids（当前任务中的假设 id）和 stance（support/contradict/context），"
        "将本次结果绑定到对应情景；未知 id 会被忽略。\n"
        "4. 拿不到的数据在 finish 的 gaps 里如实写明，不要编造。\n"
        "只输出 JSON（无 markdown 代码栏）："
        '{"tool": "工具名", "args": {...}, "reason": "一句话理由"}'
    )


def _parse_action(content: str) -> dict[str, object] | None:
    text = content.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    if fenced:
        text = fenced.group(1)
    else:
        brace = re.search(r"\{.*\}", text, re.S)
        if brace:
            text = brace.group(0)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _tool_accepts_context(runner: ToolRunner) -> bool:
    try:
        signature = inspect.signature(runner)
    except (TypeError, ValueError):
        return False
    positional = [
        parameter
        for parameter in signature.parameters.values()
        if parameter.kind
        in {
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
        }
    ]
    return (
        len(positional) >= 2
        or any(
            parameter.kind is inspect.Parameter.VAR_POSITIONAL
            for parameter in signature.parameters.values()
        )
    )


def _run_tool(
    runner: ToolRunner,
    query: str,
    context: AgentToolContext,
) -> tuple[list[AgentEvidence], str, ProviderTrace]:
    if context.deadline.expired:
        raise TimeoutError("agent tool deadline expired")
    if _tool_accepts_context(runner):
        return runner(query, context)
    return runner(query)


def _research_state_block(
    state: ResearchState | None,
    steps: list[AgentStep],
) -> str:
    if state is not None:
        recent_steps = "\n".join(
            f"步骤{index} {step.tool}(\"{step.query}\")：{step.observation[:240]}"
            for index, step in enumerate(
                steps[-2:], start=max(1, len(steps) - 1)
            )
        )
        return (
            f"{state.summary_for_agent()}\n"
            f"最近工具步骤：{recent_steps or '（无）'}"
        )
    if not steps:
        return "（尚未执行任何检索）"
    lines: list[str] = []
    for index, step in enumerate(steps, start=1):
        lines.append(
            f"步骤{index} {step.tool}(\"{step.query}\")：{step.observation}"
        )
    return "\n".join(lines)


def run_agent_loop(
    query: str,
    *,
    tools: dict[str, ToolRunner],
    existing_evidence_summary: str = "",
    steps_budget: int | None = None,
    total_seconds: float = DEFAULT_TOTAL_SECONDS,
    llm_timeout: int = DEFAULT_LLM_TIMEOUT,
    deadline: ResearchDeadline | None = None,
    complete_fn: CompleteFn | None = None,
    attempted_queries: Sequence[tuple[str, str]] = (),
    task_instructions: str = "",
    research_state: ResearchState | None = None,
) -> AgentLoopResult:
    """跑一轮 agent 检索循环；任何失败都返回已收集的部分结果（可降级）。

    ``attempted_queries`` 为主链固定管线已执行过的 ``(tool, query)``（如
    closed-loop 的各光圈查询、Web 兜底），用于跨管线去重——agent 重发这些
    查询会被当场拦截并提示改写，避免同一 turn 内重复检索同一语料。
    """
    result = AgentLoopResult(research_state=research_state)
    complete = complete_fn or llm_refine.complete
    budget = steps_budget if steps_budget is not None else max_steps()
    stage_deadline = ResearchDeadline.from_timeout(total_seconds)
    if deadline is not None:
        stage_deadline = ResearchDeadline(
            min(stage_deadline.expires_at, deadline.expires_at),
            # 保留主链为 grounded synthesis 预留的尾部预算；此前这里
            # 重建 deadline 时丢掉 synthesis_reserve，agent loop 可能把
            # 合成保留段提前耗尽，造成“检索成功但出口超时”。
            synthesis_reserve=deadline.synthesis_reserve,
        )
    tool_context = AgentToolContext(stage_deadline)
    seen_queries: set[tuple[str, str]] = {
        (tool, re.sub(r"\s+", "", attempted))
        for tool, attempted in attempted_queries
        if attempted.strip()
    }
    system_prompt = _system_prompt(tools)
    no_information_steps = 0
    finish_rejections = 0

    def available_stage_seconds() -> float:
        """检索阶段可消费的预算，不侵占 synthesis reserve。"""
        remaining = stage_deadline.remaining()
        return stage_deadline.stage_timeout(remaining)

    for _ in range(budget + 1):  # +1 给 finish 留一次决策机会
        remaining = available_stage_seconds()
        if remaining <= 0.001:
            result.stop_reason = "预算耗尽：总时长"
            break
        executed_steps = sum(1 for step in result.steps if step.tool != "finish")
        user_prompt = (
            f"用户问题：{query}\n\n"
            f"任务契约与完成要求：\n{task_instructions or '（未提供）'}\n\n"
            f"主链已有证据摘要：\n{existing_evidence_summary or '（无）'}\n\n"
            f"研究状态与最近观察：\n"
            f"{_research_state_block(result.research_state, result.steps)}\n\n"
            f"剩余检索步数预算：{budget - executed_steps}"
        )
        try:
            content, _provider, reason = complete(
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                timeout=min(float(llm_timeout), remaining),
                temperature=0.0,
            )
        except Exception as exc:  # noqa: BLE001 - provider failure is a gap
            # A rejected finish may require one replanning turn. If the
            # provider then fails/exhausts its scripted response, preserve the
            # collected evidence as partial instead of leaking an exception out
            # of the research owner.
            result.stop_reason = f"LLM 调用失败：{type(exc).__name__}"
            break
        if content is None:
            result.stop_reason = f"LLM 不可用：{reason}"
            break
        action = _parse_action(content)
        if action is None:
            result.stop_reason = "LLM 输出非法 JSON"
            break
        tool = str(action.get("tool") or "").strip()
        args = action.get("args") if isinstance(action.get("args"), dict) else {}
        action_reason = str(action.get("reason") or "").strip()

        if tool == "finish":
            requested_sufficient = bool(args.get("sufficient"))
            result.assessment = str(args.get("assessment") or "").strip()[:1600]
            raw_gaps = args.get("gaps")
            result.gaps = tuple(
                str(gap).strip()
                for gap in (raw_gaps if isinstance(raw_gaps, list) else [])
                if str(gap).strip()
            )
            uncovered = ()
            missing_outputs: tuple[str, ...] = ()
            if requested_sufficient and result.research_state is not None:
                uncovered = tuple(
                    hypothesis.hypothesis_id
                    for hypothesis in result.research_state.hypotheses
                    if not (
                        hypothesis.supporting_evidence
                        or hypothesis.contradicting_evidence
                        or any(
                            hypothesis.hypothesis_id in gap.blocks
                            for gap in result.research_state.gaps
                        )
                    )
                )
                missing: list[str] = []
                for output_id in result.research_state.required_outputs:
                    if not result.research_state.required_output_required.get(
                        output_id, True
                    ):
                        continue
                    if output_id in uncovered:
                        continue
                    if output_id in {"direct_assessment", "answer", "conclusion"}:
                        if not result.assessment:
                            missing.append(output_id)
                        continue
                    allowed_tools = set(
                        result.research_state.required_output_evidence_types.get(
                            output_id, ()
                        )
                    )
                    if not any(
                        not allowed_tools or item.tool in allowed_tools
                        for item in result.research_state.evidence.values()
                    ):
                        missing.append(output_id)
                missing_outputs = tuple(missing)
            # 只允许一次“完成请求被延迟”重新规划；若模型仍重复 finish，
            # 以 partial 结束并把未覆盖情景作为 gap，避免循环耗尽预算。
            if requested_sufficient and (uncovered or missing_outputs) and finish_rejections == 0:
                finish_rejections += 1
                result.sufficient = False
                missing_text = "、".join((*uncovered, *missing_outputs))
                result.gaps = tuple(
                    dict.fromkeys(
                        (*result.gaps, f"尚未覆盖必需情景：{missing_text}")
                    )
                )
                result.steps.append(
                    AgentStep(
                        tool="finish",
                        query="",
                        reason=action_reason,
                        observation=(
                            "完成请求被延迟：仍缺少假设覆盖；请继续检索或明确 gap。"
                            f" 未覆盖={missing_text}"
                        ),
                        hit_count=0,
                        elapsed_ms=0,
                    )
                )
                continue
            result.sufficient = requested_sufficient and not uncovered
            result.steps.append(
                AgentStep(
                    tool="finish",
                    query="",
                    reason=action_reason,
                    observation=(
                        f"sufficient={result.sufficient} assessment={result.assessment} "
                        f"gaps={list(result.gaps)}"
                    ),
                    hit_count=0,
                    elapsed_ms=0,
                )
            )
            result.stop_reason = "agent finish"
            if result.research_state is not None:
                result.research_state.set_assessment(result.assessment)
                for gap_index, gap in enumerate(result.gaps, start=1):
                    result.research_state.add_gap(
                        f"agent_gap_{gap_index}",
                        gap,
                        blocks=tuple(result.research_state.required_outputs),
                    )
                result.research_state.set_stop_reason(result.stop_reason)
                result.state_revision = result.research_state.revision
            break

        if tool not in tools or tool not in _TOOL_NAMES:
            result.stop_reason = f"非法工具：{tool!r}"
            break
        if executed_steps >= budget:
            result.stop_reason = "预算耗尽：步数"
            break
        tool_query = str(args.get("query") or "").strip()
        if not tool_query:
            result.stop_reason = f"{tool} 缺少 query 参数"
            break
        dedupe_key = (tool, re.sub(r"\s+", "", tool_query))
        if dedupe_key in seen_queries:
            result.steps.append(
                AgentStep(
                    tool=tool,
                    query=tool_query,
                    reason=action_reason,
                    observation="重复查询已拦截：请改写检索式、换工具或 finish",
                    hit_count=0,
                    elapsed_ms=0,
                )
            )
            continue
        seen_queries.add(dedupe_key)

        if available_stage_seconds() <= 0.001:
            result.stop_reason = "预算耗尽：总时长"
            break
        state_revision_before = result.research_state.revision if result.research_state is not None else 0
        raw_hypothesis_ids = args.get("hypothesis_ids", ())
        if isinstance(raw_hypothesis_ids, str):
            raw_hypothesis_ids = (raw_hypothesis_ids,)
        hypothesis_ids = tuple(
            dict.fromkeys(
                str(item).strip()
                for item in (raw_hypothesis_ids if isinstance(raw_hypothesis_ids, (list, tuple)) else ())
                if str(item).strip()
                and result.research_state is not None
                and any(
                    hypothesis.hypothesis_id == str(item).strip()
                    for hypothesis in result.research_state.hypotheses
                )
            )
        )
        stance = str(args.get("stance") or "context").strip().lower()
        if stance not in {"support", "contradict", "context"}:
            stance = "context"
        started = time.monotonic()
        try:
            evidence, observation, trace = _run_tool(
                tools[tool],
                tool_query,
                tool_context,
            )
        except Exception as exc:  # noqa: BLE001 —— 单工具失败不炸整轮循环
            evidence, observation = [], f"工具执行失败：{exc}"
            trace = ProviderTrace(
                provider=f"agent:{tool}",
                capability="agent_loop",
                status="request_error",
                detail=str(exc)[:200],
            )
        elapsed_ms = int((time.monotonic() - started) * 1000)
        result.traces.append(trace)
        if hypothesis_ids and stance in {"support", "contradict"}:
            evidence = [
                replace(
                    item,
                    supports=hypothesis_ids if stance == "support" else (),
                    contradicts=hypothesis_ids if stance == "contradict" else (),
                )
                for item in evidence
            ]
        result.evidence.extend(evidence)
        if result.research_state is not None:
            evidence_start = len(result.evidence) - len(evidence) + 1
            for offset, item in enumerate(evidence):
                result.research_state.add_evidence(
                    item.to_observation(
                        f"agent:{evidence_start + offset}:{item.tool}"
                    )
                )
            result.state_revision = result.research_state.revision
        result.steps.append(
            AgentStep(
                tool=tool,
                query=tool_query,
                reason=action_reason,
                observation=observation[:_MAX_OBSERVATION_CHARS],
                hit_count=len(evidence),
                elapsed_ms=elapsed_ms,
                hypothesis_ids=hypothesis_ids,
                stance=stance,
            )
        )
        state_changed = result.research_state is not None and result.state_revision > state_revision_before
        if evidence and (result.research_state is None or state_changed):
            no_information_steps = 0
        else:
            no_information_steps += 1
        if no_information_steps >= 2:
            result.stop_reason = "no_information_gain"
            if result.research_state is not None:
                result.research_state.set_stop_reason(result.stop_reason)
                result.state_revision = result.research_state.revision
            break
    else:
        result.stop_reason = "预算耗尽：步数"
    return result
