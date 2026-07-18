"""受预算约束的 agent 检索循环（L3）：LLM 自主决定「查什么→够不够→换查法」。

现状主链是固定管线：代码决定检索几轮/用哪些块，LLM 只做分类和成稿；长尾问题
一旦不在预设轨道上，证据跑题也没有任何一步能纠偏。本模块把控制权反转：

- LLM 在循环里逐步决定下一个工具调用（kb_search / web_search / news_search），
  看到观察结果后自行判断继续检索、改写查询或 finish；
- 执行仍是确定性代码：工具白名单钳制、步数/时长预算硬上限、重复查询去重，
  每步写 ``ProviderTrace``，产出证据带来源可回查——审计性不丢；
- LLM 未配置/超时/输出不合法 → 已收集证据照常返回，主链行为可降级不中断。

灰度开关 ``ASK_AGENT_LOOP``：
- ``off``（默认）：不启用，行为逐字节不变；
- ``auto``：仅当 controller 能力需求含 web_search/market_news（route 未命中
  任何 skill 的长尾兜底车道）时启用；
- ``on``：所有 compose 问题启用。
"""
from __future__ import annotations

import json
import os
import re
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from intelligence.services import llm_refine, market_news, web_research
from intelligence.services.provider_observability import ProviderTrace

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
}
_TOOL_NAMES = (*_TOOL_DESCRIPTIONS, "finish")


def loop_mode() -> str:
    mode = str(os.environ.get(ENV_MODE) or MODE_OFF).strip().lower()
    return mode if mode in _VALID_MODES else MODE_OFF


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
    source: str  # kb file_path 或 url


@dataclass(frozen=True)
class AgentStep:
    tool: str
    query: str
    reason: str
    observation: str
    hit_count: int
    elapsed_ms: int

    def to_dict(self) -> dict[str, object]:
        return {
            "tool": self.tool,
            "query": self.query,
            "reason": self.reason,
            "observation": self.observation[:200],
            "hit_count": self.hit_count,
            "elapsed_ms": self.elapsed_ms,
        }


@dataclass
class AgentLoopResult:
    steps: list[AgentStep] = field(default_factory=list)
    evidence: list[AgentEvidence] = field(default_factory=list)
    traces: list[ProviderTrace] = field(default_factory=list)
    sufficient: bool | None = None
    gaps: tuple[str, ...] = ()
    stop_reason: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "steps": [step.to_dict() for step in self.steps],
            "evidence_count": len(self.evidence),
            "sufficient": self.sufficient,
            "gaps": list(self.gaps),
            "stop_reason": self.stop_reason,
        }


# 工具执行器契约：query -> (evidence 列表, 观察文本, trace)。
ToolRunner = Callable[[str], tuple[list[AgentEvidence], str, ProviderTrace]]


def build_default_tools(
    kb_retrieve: Callable[[str], object],
) -> dict[str, ToolRunner]:
    """默认工具集：kb_search 由调用方注入（复用主链 kb_rag 配置），web/news 用现成 provider。"""

    def _kb_search(query: str) -> tuple[list[AgentEvidence], str, ProviderTrace]:
        rag = kb_retrieve(query)
        hits = list(getattr(rag, "hits", ()) or ())[:5]
        evidence = [
            AgentEvidence(
                tool="kb_search",
                title=hit.title,
                detail=(hit.excerpt or "")[:160],
                source=hit.file_path,
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

    def _web_search(query: str) -> tuple[list[AgentEvidence], str, ProviderTrace]:
        web = web_research.fetch_web_search(query)
        evidence = [
            AgentEvidence(
                tool="web_search",
                title=item.title,
                detail=(item.snippet or "")[:160],
                source=item.url,
            )
            for item in web.items[:5]
        ]
        observation = (
            "；".join(f"{item.title}：{item.detail[:80]}" for item in evidence)
            or f"无结果（{web.trace.status}：{web.trace.detail}）"
        )
        return evidence, observation, web.trace

    def _news_search(query: str) -> tuple[list[AgentEvidence], str, ProviderTrace]:
        news = market_news.fetch_eastmoney_news_result(query)
        evidence = [
            AgentEvidence(
                tool="news_search",
                title=item.title,
                detail=f"{item.date} {item.source}",
                source=item.url,
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

    def _graph_lookup(query: str) -> tuple[list[AgentEvidence], str, ProviderTrace]:
        concepts = knowledge.get_concept_matches(query, limit=5)
        exposures = knowledge.get_exposure_matches(query, limit=8)
        evidence: list[AgentEvidence] = []
        for item in (concepts.get("items") or [])[:5]:
            evidence.append(
                AgentEvidence(
                    tool="graph_lookup",
                    title=f"概念 {item.get('concept')}",
                    detail=f"匹配分 {item.get('score')}",
                    source="knowledge-base · wiki/relations/concept_graph.json",
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
                    source="knowledge-base · wiki/relations/entity_exposures.json",
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

    def _evidence_lookup(query: str) -> tuple[list[AgentEvidence], str, ProviderTrace]:
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
                source="knowledge-base · wiki/relations/evidence_index.json",
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
        "args: {\"sufficient\": true/false, \"gaps\": [\"仍缺什么\"]}\n"
        "原则：\n"
        "1. 检索结果与问题无关时要改写检索式或换工具，不要把无关结果当证据；\n"
        "2. 同一检索式不要重复；证据足够就尽早 finish；\n"
        "3. 拿不到的数据在 finish 的 gaps 里如实写明，不要编造。\n"
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


def _transcript_block(steps: list[AgentStep]) -> str:
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
    complete_fn: CompleteFn | None = None,
    attempted_queries: Sequence[tuple[str, str]] = (),
) -> AgentLoopResult:
    """跑一轮 agent 检索循环；任何失败都返回已收集的部分结果（可降级）。

    ``attempted_queries`` 为主链固定管线已执行过的 ``(tool, query)``（如
    closed-loop 的各光圈查询、Web 兜底），用于跨管线去重——agent 重发这些
    查询会被当场拦截并提示改写，避免同一 turn 内重复检索同一语料。
    """
    result = AgentLoopResult()
    complete = complete_fn or llm_refine.complete
    budget = steps_budget if steps_budget is not None else max_steps()
    deadline = time.monotonic() + max(1.0, total_seconds)
    seen_queries: set[tuple[str, str]] = {
        (tool, re.sub(r"\s+", "", attempted))
        for tool, attempted in attempted_queries
        if attempted.strip()
    }
    system_prompt = _system_prompt(tools)

    for _ in range(budget + 1):  # +1 给 finish 留一次决策机会
        if time.monotonic() >= deadline:
            result.stop_reason = "预算耗尽：总时长"
            break
        executed_steps = sum(1 for step in result.steps if step.tool != "finish")
        user_prompt = (
            f"用户问题：{query}\n\n"
            f"主链已有证据摘要：\n{existing_evidence_summary or '（无）'}\n\n"
            f"已执行步骤与观察：\n{_transcript_block(result.steps)}\n\n"
            f"剩余检索步数预算：{budget - executed_steps}"
        )
        content, _provider, reason = complete(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            timeout=llm_timeout,
            temperature=0.0,
        )
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
            result.sufficient = bool(args.get("sufficient"))
            raw_gaps = args.get("gaps")
            result.gaps = tuple(
                str(gap).strip()
                for gap in (raw_gaps if isinstance(raw_gaps, list) else [])
                if str(gap).strip()
            )
            result.steps.append(
                AgentStep(
                    tool="finish",
                    query="",
                    reason=action_reason,
                    observation=f"sufficient={result.sufficient} gaps={list(result.gaps)}",
                    hit_count=0,
                    elapsed_ms=0,
                )
            )
            result.stop_reason = "agent finish"
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

        started = time.monotonic()
        try:
            evidence, observation, trace = tools[tool](tool_query)
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
        result.evidence.extend(evidence)
        result.steps.append(
            AgentStep(
                tool=tool,
                query=tool_query,
                reason=action_reason,
                observation=observation[:_MAX_OBSERVATION_CHARS],
                hit_count=len(evidence),
                elapsed_ms=elapsed_ms,
            )
        )
    else:
        result.stop_reason = "预算耗尽：步数"
    return result
