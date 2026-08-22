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
import hashlib
import json
import os
import re
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace

from intelligence.services import (
    closed_loop_retrieval,
    llm_refine,
    market_news,
    web_research,
)
from intelligence.services.kb_selection_noise import filter_structural_noise
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.research_contract import InformationCutoff, ResearchDeadline
from intelligence.services.research_state import EvidenceObservation, ResearchState

ENV_MODE = "ASK_AGENT_LOOP"
ENV_MAX_STEPS = "ASK_AGENT_MAX_STEPS"
MODE_OFF = "off"
MODE_AUTO = "auto"
MODE_ON = "on"
_VALID_MODES = (MODE_OFF, MODE_AUTO, MODE_ON)

DEFAULT_MAX_STEPS = 4
MAX_CONFIGURED_STEPS = 24
DEFAULT_LLM_TIMEOUT = 15
NO_INFORMATION_GAIN_GAP = "连续两次检索未获得新增信息，无法继续补全证据。"
DEFAULT_TOTAL_SECONDS = 60.0
_MAX_OBSERVATION_CHARS = 900
# kb_search 送达窗（V3 / R-20260821-15）。
# 旧硬编码 hits[:5] + excerpt[:160] = 800 字符上限。默认与 retrieve() 对齐：
# max_hits=6（episode_tools / kb_rag.DEFAULT_RAG_K），正文走 llm_evidence
# （retrieve 已 apply_total_llm_budget，总预算 4800–8000）。
# detail_chars=0 表示送达层不再二次截断。
# retrieval-tier plan 的分档只覆盖检索 mode（remaining <15s → BM25），
# 本模块不另建字符降档——见 kb_search_delivery_limits。
KB_SEARCH_MAX_HITS = 6
KB_SEARCH_DETAIL_CHARS = 0
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
    "mainline_context": (
        "- mainline_context：本地同日主线结构（题材/板块及数据时效边界），"
        "args: {\"query\": 当前主线或盘面问题}"
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
    return max(1, min(value, MAX_CONFIGURED_STEPS))


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
class StructuredObservation:
    """证据里一个机器可读的观察值：(主体, 日期, 指标) → 数。

    住在这一层而不是 ``asof_prefetch``，因为 ``asof_prefetch`` 依赖本模块；
    反过来会成环。凡是能在格式化**之前**拿到结构化数的取数方，都该把数
    原样挂上来，别让下游回头解析 ``detail`` 文本。
    """

    subject: str
    as_of: str
    metric: str
    value: float


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
    # 内容主键贯通 ToolObservation → Citation → EvidenceAtom；空值仅表示
    # 旧 runner 未提供可稳定哈希的正文。
    content_hash: str = ""
    # 结构化观察值：``detail`` 是给模型看的文本，这里是同一批数的机器可读形态。
    # 下游（槽填数、删句连坐检测）读它，**不回头解析 detail 自由文本**。
    # 不进 ``evidence_content_hash``（该哈希只吃 tool/title/detail/source），
    # 因此补上本字段不会改变任何既有证据身份。
    observations: tuple[StructuredObservation, ...] = ()
    # V9a 只读遥测。None = 未跑重摘录（历史 run 缺字段，报不可判不报 0）。
    reexcerpted: bool | None = None
    pointer_dropped: int | None = None
    # V9b 只读遥测。None = 未跑槽位重排（历史 run 缺字段，报不可判不报 0）。
    structural_neighbor_demoted: int | None = None

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
            content_hash=self.content_hash,
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
    """Cooperative deadline and cancellation token passed to agent tools."""

    deadline: ResearchDeadline
    is_cancelled: Callable[[], bool] = field(
        default=lambda: False,
        repr=False,
        compare=False,
    )
    information_cutoff: InformationCutoff | None = None

    @property
    def cancelled(self) -> bool:
        return bool(self.is_cancelled())

    def check_cancelled(self) -> None:
        if self.cancelled:
            raise RuntimeError("agent tool cancelled")

    def remaining(self) -> float:
        self.check_cancelled()
        return self.deadline.remaining()

    def timeout(self, configured_limit: float) -> float:
        self.check_cancelled()
        timeout = self.deadline.stage_timeout(configured_limit)
        if timeout <= 0.001:
            raise TimeoutError("agent tool deadline expired")
        return timeout


# 工具执行器契约：query (+ 可选 context) -> (evidence 列表, 观察文本, trace)。
# 单参数 runner 继续兼容测试和外部扩展；内置 runner 都接收 context。
ToolRunner = Callable[..., tuple[list[AgentEvidence], str, ProviderTrace]]


# 检索**失败**与检索**没有结果**必须让模型区分得开。
#
# 失败形状（2026-08-12 历史对账，扫 44564 份 run 产物）：三个检索工具的空结果
# 一律写成「无X（{status}：{detail}）」，于是网络故障、超时、被禁用统统长得像
# 「这个世界上没有相关内容」。实测 news_search 78 次空手里：
#   12 次 request_error（URLError / deadline exhausted）—— **是故障不是没有**
#   18 次 真的 empty
#   12 次 其实是 harness 去重（「与本轮已有证据重复」），压根不是失败
# kb_search 更极端：22 次「无命中」里 20 次是故障（14 error + 6 timeout）。
#
# 危害不是「少了一条证据」，而是模型据此写出**否定结论**——把「查不到」写成
# 「不存在」。ai-agent-book ch4：静默降级会让 Agent 误以为自己看到了全部内容，
# 且**无法自行诊断**；族 A 官方 custom-tools 要求 isError 明确、并告诉模型
# 「what to try instead」。
#
# 抽成一处而不是三处各写各的：同一条规则散在三个 runner 里，改一处漏两处，
# 而漏的时候没有任何门禁会红（BUILD 模式 6：单一真本源）。
_FAILED_PROVIDER_STATUSES = frozenset(
    {"request_error", "parse_error", "proxy_unavailable", "error", "timeout",
     "fallback_failed", "disabled"}
)


def _describe_retrieval_degradation(telemetry: object) -> str:
    """检索降级了就说出来——哪怕这次有命中。

    ``kb_rag`` 会在稠密依赖不可用时把 hybrid/rerank 降到纯 BM25，且遥测里
    ``degraded`` / ``fallback_reason`` / ``recall_desc`` 全都如实记了。此前
    没有任何一条往模型那边传，所以模型看到的是一份「正常」的关键词命中。

    只在真的降级时返回文本。没降级返回空串——每次都挂一句「本次未降级」
    会训练模型忽略这一行，那比不说更糟。
    """

    if not getattr(telemetry, "degraded", False):
        return ""
    requested = str(getattr(telemetry, "requested_mode", "") or "").strip()
    effective = str(getattr(telemetry, "effective_mode", "") or "").strip()
    recall = str(getattr(telemetry, "recall_desc", "") or "").strip()
    reason = str(getattr(telemetry, "fallback_reason", "") or "").strip()
    details: list[str] = []
    if requested and effective and requested != effective:
        details.append(f"{requested}→{effective}")
    if recall:
        details.append(f"实际只用了：{recall}")
    if reason:
        details.append(f"原因 {reason}")
    head = "⚠ 本次检索已降级"
    if details:
        head = f"{head}（{'，'.join(details)}）"
    return (
        f"{head}。语义检索未生效，同义/近义表述可能整片漏掉；"
        "结果为空或偏少时不要据此下否定结论。"
    )


def describe_no_result(
    subject: str,
    miss_text: str,
    status: str,
    detail: str = "",
) -> str:
    """把「没结果」写成模型读得懂的那句话：是查不到，还是查不了。

    两个措辞参数是分开的，不能合并：``subject`` 进故障句（「知识库检索未能
    执行完成」），``miss_text`` 是真空结果的原话（「无命中」/「无资讯」）。
    第一版只传一个 ``kind`` 去拼 ``无{kind}``，对资讯/网页读得通，
    对知识库就成了「无知识库」——**共用规则不等于共用措辞**。
    """

    tail = f"：{detail[:120]}" if detail else ""
    if status in _FAILED_PROVIDER_STATUSES:
        return (
            f"{subject}检索未能执行完成（{status}{tail}）。"
            "这是检索失败，不是不存在该内容；"
            "不要据此下否定结论，可改写检索词重试或改用其他工具。"
        )
    return f"{miss_text}（{status}{tail}）"


def kb_delivery_telemetry(
    evidence: Sequence[AgentEvidence],
    observation: str,
) -> dict[str, object]:
    """kb_search 送达遥测：按**实际送给模型的**字符/条数/来源页计，不写死 800。

    送达是**两条通道**，必须分开计数（2026-08-22 钙钛矿 live 探针实测）：

    - ``delivered_chars`` = observation 串（agent loop 的工具消息，每条截
      ``detail[:80]`` 作索引摘要）；
    - ``detail_chars`` = ``evidence[].detail`` 总和（V3 粗管道拓宽的通道，
      经证据注册表进 composer/verifier——答案里的正文级事实走这条）。

    只看 delivered_chars 会把粗管道误判成没生效（580 字 vs 正文级 detail）。
    传感器和落盘共用这一处，避免两套量纲。
    """

    pages: list[str] = []
    for item in evidence:
        page = str(getattr(item, "internal_locator", "") or "").strip()
        if not page:
            page = str(getattr(item, "title", "") or "").strip()
        if page:
            pages.append(page)
    payload: dict[str, object] = {
        "delivered_chars": len(observation or ""),
        "detail_chars": sum(
            len(str(getattr(item, "detail", "") or "")) for item in evidence
        ),
        "hit_count": len(tuple(evidence)),
        "source_pages": pages,
    }
    dropped = next(
        (
            getattr(item, "pointer_dropped", None)
            for item in evidence
            if getattr(item, "pointer_dropped", None) is not None
        ),
        None,
    )
    if dropped is not None:
        payload["pointer_dropped"] = int(dropped)
    flags = [getattr(item, "reexcerpted", None) for item in evidence]
    if any(flag is not None for flag in flags):
        payload["reexcerpted"] = [bool(flag) for flag in flags]
    demoted = next(
        (
            getattr(item, "structural_neighbor_demoted", None)
            for item in evidence
            if getattr(item, "structural_neighbor_demoted", None) is not None
        ),
        None,
    )
    if demoted is not None:
        payload["structural_neighbor_demoted"] = int(demoted)
    return payload


def kb_search_delivery_limits(
    *,
    remaining_seconds: float | None = None,
) -> tuple[int, int]:
    """Return ``(max_hits, detail_chars)`` for kb_search 送达.

    ``remaining_seconds`` is accepted so callers can thread the episode
    remainder through this seam. The retrieval-tier plan's only ladder is
    remaining < 15s → BM25 (``kb_rag.select_mode_for_remaining``). This
    function must not invent a parallel char-budget ladder: delivery always
    uses ``KB_SEARCH_MAX_HITS`` / ``KB_SEARCH_DETAIL_CHARS``.
    """

    del remaining_seconds
    return KB_SEARCH_MAX_HITS, KB_SEARCH_DETAIL_CHARS


def kb_search_hit_text(hit: object, *, detail_chars: int | None = None) -> str:
    """kb_search 送达正文：接 llm_evidence 粗管道，再剥结构噪声（V5）。

    过滤在截断之前：窗口若被截，截到的应是正文头而不是标签汤。
    ``detail_chars=0`` 仍表示送达层不二次截断，过滤本身不加长度上限。
    """

    text = str(
        getattr(hit, "llm_evidence", "")
        or getattr(hit, "display_excerpt", "")
        or getattr(hit, "excerpt", "")
        or ""
    )
    text = filter_structural_noise(text)
    limit = KB_SEARCH_DETAIL_CHARS if detail_chars is None else detail_chars
    if limit > 0:
        return text[:limit]
    return text


def build_default_tools(
    kb_retrieve: Callable[[str, float], object],
) -> dict[str, ToolRunner]:
    """默认工具集：kb_search 由调用方注入（复用主链 kb_rag 配置），web/news 用现成 provider。"""

    def _kb_search(
        query: str,
        context: AgentToolContext,
    ) -> tuple[list[AgentEvidence], str, ProviderTrace]:
        rag = kb_retrieve(query, context.timeout(DEFAULT_TOTAL_SECONDS))
        context.check_cancelled()
        max_hits, detail_chars = kb_search_delivery_limits(
            remaining_seconds=context.deadline.remaining(),
        )
        hits = list(getattr(rag, "hits", ()) or ())[:max_hits]
        evidence = []
        rag_telemetry = getattr(rag, "telemetry", None)
        pointer_dropped = getattr(rag_telemetry, "pointer_dropped", None)
        structural_neighbor_demoted = getattr(
            rag_telemetry, "structural_neighbor_demoted", None
        )
        for hit in hits:
            hit_date = closed_loop_retrieval.wiki_hit_source_date(hit)
            evidence.append(
                AgentEvidence(
                    tool="kb_search",
                    title=hit.title,
                    detail=kb_search_hit_text(hit, detail_chars=detail_chars),
                    source="本地知识库",
                    internal_locator=hit.file_path,
                    source_date=hit_date.isoformat() if hit_date is not None else None,
                    reexcerpted=getattr(hit, "reexcerpted", None),
                    pointer_dropped=pointer_dropped,
                    structural_neighbor_demoted=structural_neighbor_demoted,
                )
            )
        telemetry = rag_telemetry
        status = str(getattr(telemetry, "status", "unknown") or "unknown")
        # 检索**失败**不等于知识库**没有** —— 这两件事必须让模型区分得开。
        #
        # 原来一律拼成「无命中（{status}）」，于是 status=error 时模型看到的是
        # 一句「无命中（error）」：它没有理由把括号里那个词读成故障。更糟的是
        # trace 记 status="empty"，**任何按 error 计数的下游审计都会看到零错误**。
        # 2026-08-12 历史对账实测：kb_search 22 次调用全部「无命中」，逐条统计是
        # 14 error + 6 timeout + 2 真 empty——即 20/22（91%）是故障，不是知识库空。
        # ⚠ 初版据 3 条抽样写成「22/22 全部是 error」，是把抽样当成了全称断言。
        # 修复本身不受影响（error 与 timeout 都在故障集合里），但数字已更正。
        #
        # 这条还和我们自己的行为契约互相打架：kb_search 的契约写着「无命中只说明
        # 知识库没有回填过，不等于该事实不存在」——status=error 时这句话是错的，
        # 契约在主动教模型把工具故障读成「没回填」。
        #
        # 依据：ai-agent-book ch4「静默截断同样危险——Agent 会误以为自己看到了
        # 全部内容」；族 A 官方 custom-tools「Return isError: true ... so Claude
        # can react to it」+「compose the message Claude reads」。
        failed = status in {"error", "timeout"}
        if evidence:
            observation = "；".join(
                f"{item.title}：{item.detail[:80]}" for item in evidence
            )
        else:
            observation = describe_no_result(
                "知识库",
                "无命中",
                status,
                str(getattr(telemetry, "warning", "") or "").strip(),
            )
        # 检索**降级**必须跟着结果一起走，哪怕这次有命中。
        #
        # ``kb_rag`` 在稠密依赖不可用时会把 hybrid/rerank 降到纯 BM25，并如实
        # 记 ``degraded`` / ``fallback_reason`` / ``recall_desc``——**遥测是诚实的，
        # 只是从没往上传**。于是模型拿到一份看起来完全正常的关键词命中，
        # 却不知道语义那一路根本没跑。
        #
        # 这比报错更危险：报错至少是可见的失败，而这是**成功外观下的能力降级**。
        # 模型会据此判断「知识库里没有语义相关的内容」，而真相是没检索过。
        # ai-agent-book ch3 §混合检索：稀疏检索「读不懂同义词」（搜 kitty 找不到
        # 只写 cat 的文档）——降级后丢的正是这一半能力，而这一半恰恰无法从
        # 返回结果里看出来。
        degraded_note = _describe_retrieval_degradation(telemetry)
        if degraded_note:
            observation = "；".join(part for part in (observation, degraded_note) if part)
        # 送达遥测：kb_delivery_telemetry(evidence, observation)。registry 在
        # cutoff 改写后用同一函数落盘 tool_result.telemetry，按实际字符计、不写死 800。
        trace = ProviderTrace(
            provider="agent:kb_search",
            capability="agent_loop",
            # 故障必须记成 error：记成 empty 会让「工具坏了」在所有按状态
            # 计数的审计里消失，而覆盖率类检查永远发现不了这种静默降级。
            status="success" if evidence else ("error" if failed else "empty"),
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
        context.check_cancelled()

        def source_date(item: web_research.WebSearchItem) -> str | None:
            parsed = market_news.latest_explicit_query_date(
                f"{item.title} {item.snippet}",
                reference_date=(
                    context.information_cutoff.as_of_date
                    if context.information_cutoff is not None
                    else None
                ),
            )
            return parsed.isoformat() if parsed is not None else None

        evidence = [
            AgentEvidence(
                tool="web_search",
                title=item.title,
                detail=(item.snippet or "")[:160],
                source=item.url,
                source_date=source_date(item),
                evidence_tier="public_web",
                independent_key=item.url,
            )
            for item in web.items[:5]
        ]
        observation = (
            "；".join(f"{item.title}：{item.detail[:80]}" for item in evidence)
            or describe_no_result("网页", "无结果", web.trace.status, web.trace.detail)
        )
        return evidence, observation, web.trace

    def _news_search(
        query: str,
        context: AgentToolContext,
    ) -> tuple[list[AgentEvidence], str, ProviderTrace]:
        query_cutoff = (
            market_news.query_date_cutoff(
                query,
                upper_bound=context.information_cutoff.as_of_date,
            )
            if context.information_cutoff is not None
            else None
        )
        news = market_news.fetch_eastmoney_news_result(
            query,
            timeout=context.timeout(8.0),
            as_of=query_cutoff,
        )
        context.check_cancelled()
        cutoff_text = query_cutoff.isoformat() if query_cutoff is not None else None
        after_cutoff = bool(not news.items and news.after_cutoff_items)
        source_items = news.items[:6] or news.after_cutoff_items[:6]
        evidence = [
            AgentEvidence(
                tool="news_search",
                title=(
                    f"晚于问句日 {cutoff_text}｜{item.title}"
                    if after_cutoff and cutoff_text
                    else item.title
                ),
                detail=f"{item.date} {item.source}",
                source=item.url,
                source_date=item.date[:10] or None,
                evidence_tier="news",
                independent_key=item.url,
            )
            for item in source_items
        ]
        if after_cutoff and cutoff_text:
            listed = "；".join(
                f"{item.detail}《{item.title}》" for item in evidence
            )
            observation = (
                f"源返回 {len(evidence)} 条，全部晚于问句日 {cutoff_text}，"
                f"已标注后交付；不是源里没有。{listed}"
            )
        else:
            observation = (
                "；".join(f"{item.detail}《{item.title}》" for item in evidence)
                or describe_no_result("资讯", "无资讯", news.trace.status, news.trace.detail)
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
        if context is not None:
            context.check_cancelled()
        concepts = knowledge.get_concept_matches(query, limit=5)
        exposures = knowledge.get_exposure_matches(query, limit=8)
        if context is not None:
            context.check_cancelled()
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
        if context is not None:
            context.check_cancelled()
        bundle = knowledge.get_evidence(query, limit=6)
        if context is not None:
            context.check_cancelled()
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
                source_date=str(item.get("source_date") or "") or None,
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
    detail_chars: int = 200,
    source_date: str | None = None,
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
    snapshot_date = str(source_date or "").strip() or None
    for line in lines[:limit]:
        # 一行可能同时包含窗口起止日。旧实现只取第一个日期，导致
        # ``2026-07-14 ~ 2026-07-20`` 被投影成 as_of=07-14，进而让
        # freshness、报告页和外部证据对齐都用错基准日。
        date_matches = re.findall(r"20\d{2}[-/]\d{1,2}[-/]\d{1,2}", line)
        normalized_dates = tuple(value.replace("/", "-") for value in date_matches)
        item = AgentEvidence(
            tool=tool,
            title=line[:48],
            # 结构化数据块已经由白名单 SQL/确定性 renderer 约束，不是
            # 任意网页正文。调用方可提高保真窗口，避免主线列表在证据层
            # 先被 200 字截断后，再要求模型从残片做排序。
            detail=line[: max(80, min(int(detail_chars), 1200))],
            source=source,
            source_date=(
                snapshot_date
                if snapshot_date is not None
                else max(normalized_dates)
                if normalized_dates
                else None
            ),
            evidence_tier=(
                "L4_structured"
                if tool in {"market_data", "mainline_context"}
                else "L2_structured"
                if tool == "financial_data"
                else ""
            ),
        )
        evidence.append(replace(item, content_hash=evidence_content_hash(item)))
    observation = "；".join(lines[:limit])
    return evidence, observation


_NUMBER_TOKEN_RE = re.compile(r"-?\d+(?:\.\d+)?")


def grounded_values_in_text(
    text: str,
    evidence: tuple[AgentEvidence, ...] | list[AgentEvidence],
) -> tuple[StructuredObservation, ...]:
    """文本里出现过、且在证据结构化观察值里**有据**的那些数。

    用途：判官删句之前问一句「这一刀会连坐掉哪些真值」。它**不阻止删除**——
    删除决定仍归判官，绑在同一句里的编造照删（否则假话会拿真数当免死金牌）。
    它只保证真值不随句子静默消失，好让下游按槽重新呈现。

    这是「保下限不封上限」的落点：拦的是**信息丢失**，不是模型的表达。

    刻意从严：只认与观察值逐字节相等的数字 token（``4.74`` 命中，``4.7``
    与 ``约 4.74`` 不命中）。宁可少报几条（变笨）也不误报（变错）——
    误报会把没被删的数当成缺口，反过来污染缺口统计。
    """

    tokens = {
        float(match.group())
        for match in _NUMBER_TOKEN_RE.finditer(str(text or ""))
    }
    if not tokens:
        return ()
    hits: list[StructuredObservation] = []
    seen: set[tuple[str, str, str, float]] = set()
    for item in evidence:
        for obs in item.observations:
            key = (obs.subject, obs.as_of, obs.metric, obs.value)
            if key in seen or obs.value not in tokens:
                continue
            seen.add(key)
            hits.append(obs)
    return tuple(hits)


def describe_lost_observation(obs: StructuredObservation) -> str:
    """把连坐掉的观察值写成一条缺口，供 ``AgentOutcome.gaps`` 记账。"""

    return (
        f"删句连坐：{obs.subject} {obs.as_of} {obs.metric}={obs.value:g} "
        "有据（预取观察值），随未通过核验的表述一并移除；"
        "应按槽重新呈现，不得当作无数据。"
    )


def evidence_content_hash(item: AgentEvidence) -> str:
    """Return the stable evidence identity shared by all presentation layers."""

    payload = "|".join(
        (item.tool, item.title.strip(), item.detail.strip(), item.source.strip())
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


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
    context_block: str = "",
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
    premature_gap_rejections = 0

    def untried_required_tools(assessment: str) -> tuple[str, ...]:
        """Return useful tools that have not been attempted for a required output.

        ``finish(sufficient=false)`` is a legitimate terminal action only after
        the relevant capability has actually been tried.  Without this gate an
        agent can observe one preloaded market block, immediately report an
        external-evidence gap, and leave web/news tools unused.  The gate is
        deliberately bounded to one re-plan turn; empty/error attempts still
        count, so it cannot create an unbounded retry loop.
        """

        state = result.research_state
        if state is None:
            return ()
        attempted = {
            item.tool for item in state.evidence.values()
        } | {
            step.tool for step in result.steps if step.tool in tools
        }
        candidates: list[str] = []
        hypotheses = {
            item.hypothesis_id: item for item in state.hypotheses
        }
        blocking = {
            output_id
            for gap in state.gaps
            for output_id in gap.blocks
        }
        for output_id in state.required_outputs:
            if not state.required_output_required.get(output_id, True):
                continue
            if output_id in {"direct_assessment", "answer", "conclusion"}:
                if assessment.strip():
                    continue
            else:
                hypothesis = hypotheses.get(output_id)
                if hypothesis is not None and (
                    hypothesis.supporting_evidence
                    or hypothesis.contradicting_evidence
                    or output_id in blocking
                ):
                    continue
                allowed = set(
                    state.required_output_evidence_types.get(output_id, ())
                )
                if hypothesis is None and any(
                    not allowed or item.tool in allowed
                    for item in state.evidence.values()
                ):
                    continue
            for name in state.required_output_evidence_types.get(output_id, ()):
                if name in tools and name not in attempted and name not in candidates:
                    candidates.append(name)
        return tuple(candidates)

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
            f"当前时间与数据上下文：\n{context_block or '（未提供）'}\n\n"
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
            # “证据不足”不能替代一次本可执行的检索。允许代码把第一次
            # 过早 gap 退回给模型重新规划；第二次仍选择结束则尊重模型，
            # 保留 partial，避免把 soft planner 变成隐藏固定管线。
            untried = untried_required_tools(result.assessment)
            if (
                not requested_sufficient
                and untried
                and premature_gap_rejections == 0
            ):
                premature_gap_rejections += 1
                result.steps.append(
                    AgentStep(
                        tool="finish",
                        query="",
                        reason=action_reason,
                        observation=(
                            "结束请求被延迟：相关白名单能力尚未尝试。"
                            f" 请优先尝试 {', '.join(untried)}；"
                            "若工具为空或报错，再如实报告不可补缺口。"
                        ),
                        hit_count=0,
                        elapsed_ms=0,
                    )
                )
                continue
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
            missing_requirements = tuple(dict.fromkeys((*uncovered, *missing_outputs)))
            # 只允许一次“完成请求被延迟”重新规划；若模型仍重复 finish，
            # 以 partial 结束并把未覆盖情景或 output 作为 gap，避免循环耗尽预算。
            if requested_sufficient and missing_requirements and finish_rejections == 0:
                finish_rejections += 1
                result.sufficient = False
                missing_text = "、".join(missing_requirements)
                result.gaps = tuple(
                    dict.fromkeys(
                        (*result.gaps, f"尚未覆盖必需项：{missing_text}")
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
            # 第二次 finish 也不能因“没有 hypothesis”而绕过普通 required
            # output（例如必须的结构化行情、比较依据）。明确保留 gap，供
            # ResearchState 和 completion report 一致判为 partial。
            if requested_sufficient and missing_requirements:
                result.gaps = tuple(
                    dict.fromkeys(
                        (
                            *result.gaps,
                            f"尚未满足必需输出：{'、'.join(missing_requirements)}",
                        )
                    )
                )
            result.sufficient = requested_sufficient and not missing_requirements
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
            evidence = [
                item
                if item.content_hash
                else replace(item, content_hash=evidence_content_hash(item))
                for item in evidence
            ]
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
            result.gaps = tuple(dict.fromkeys((*result.gaps, NO_INFORMATION_GAIN_GAP)))
            if result.research_state is not None:
                result.research_state.add_gap(
                    "no_information_gain",
                    NO_INFORMATION_GAIN_GAP,
                    blocks=tuple(result.research_state.required_outputs),
                )
                result.research_state.set_stop_reason(result.stop_reason)
                result.state_revision = result.research_state.revision
            break
    else:
        result.stop_reason = "预算耗尽：步数"
    return result
