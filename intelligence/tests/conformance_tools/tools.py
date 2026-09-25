"""参数表（逐工具，解析器数）+ 能力声明表 + 探针替身。

与运行时后端缝的关键差别（判据的一部分，见 README）：运行时缝的四个后端
是**各自为政的实现**（才会有 REDUCED / UNSUPPORTED 声明）；工具缝的契约
由 ``ResearchToolRegistry`` **单点强制**，N 个工具是同一实现的 N 份配置，
因此默认注册面（``default_registry``）下全部声明 SUPPORTED 是如实的。
漂移风险在**装配面**：生产 ``build_episode_registry`` 会给个别工具换
schema / parse_arguments（如 finance_query 的语义查询 schema），那是各工具
独立演化的入口——本套件钉住注册表层契约，装配面差异登记在 README。
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field

from intelligence.services.agent_research import AgentEvidence, AgentToolContext
from intelligence.services.evidence_capabilities import EvidencePlan
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.research_contract import (
    RequiredOutput,
    ResearchDeadline,
    ResearchPolicy,
    ResearchRunContext,
    ResearchTaskContract,
)
from intelligence.services.research_tool_registry import (
    _DEFAULT_TOOL_METADATA,
    ResearchToolRegistry,
    ToolSpec,
    default_registry,
    parse_snapshot_arguments,
)
from intelligence.services.task_frame import TaskFrame

# 工具个数用解析器数（AGENTS.md「数数别用固定行号」）：直接枚举唯一事实源。
TOOL_NAMES: tuple[str, ...] = tuple(_DEFAULT_TOOL_METADATA)

TOOL_EVIDENCE_HASH = "conformance-tool-hash"

T_INVARIANT_IDS: tuple[str, ...] = ("T-1", "T-2", "T-3", "T-4", "T-5", "T-6", "T-7")

# 能力声明表：注册表层契约由 ResearchToolRegistry 单点强制，逐工具全部
# SUPPORTED；notes 承载逐工具的已知形状差异（断言按 spec 运行时分派，
# 不靠这张表写死 kind）。
TOOL_DECLARATIONS: dict[str, dict[str, str]] = {
    name: {inv: "supported" for inv in T_INVARIANT_IDS} for name in TOOL_NAMES
}
TOOL_NOTES: dict[str, str] = {
    "memory_lookup": (
        "生产装配为条件工具（需 memory_user 输入，tool-reachability 门禁"
        "已声明）；注册表层契约不受影响。"
    ),
    "finance_query": (
        "生产装配（build_episode_registry）给它换语义查询 schema 与"
        " parse_arguments——装配面独立演化的实例；本套件断注册表默认面，"
        "生产 schema 校验由 finance_query 自己的单测管。"
    ),
    "financial_data": (
        "快照工具但带一个可选 report_period（P0b，2026-09-03）：空参合法，"
        "多余键仍拒；窗口语义由 test_capability_amplification_p0 钉。"
    ),
    "web_fetch": (
        "参数面是一个必填 url（不是 query）；拒绝条件与来源分档由"
        " test_web_fetch_tool 钉。授权派生自 web_search（runtime_capabilities_for_frame）。"
    ),
}


@dataclass
class ToolProbe:
    """runner 替身的观测记录。"""

    invocations: list[tuple[str, object]] = field(default_factory=list)
    contexts: list[AgentToolContext] = field(default_factory=list)


def probe_runner(
    tool_name: str,
    probe: ToolProbe,
    *,
    extra_evidence: tuple[AgentEvidence, ...] = (),
) -> Callable[..., tuple]:
    """一个记录输入、发一条带 hash 证据的 legacy 元组 runner。"""

    def runner(value, context: AgentToolContext):
        probe.invocations.append((tool_name, value))
        probe.contexts.append(context)
        evidence = AgentEvidence(
            tool=tool_name,
            title=f"{tool_name} 的替身证据",
            detail="conformance 探针产出",
            source="conformance-double",
            source_date="2026-07-24",
            evidence_tier="L4",
            content_hash=TOOL_EVIDENCE_HASH,
        )
        return (
            [evidence, *extra_evidence],
            f"{tool_name} 观察值",
            ProviderTrace(
                provider=f"double:{tool_name}",
                capability=tool_name,
                status="success",
                source_trade_date="2026-07-24",
                result_count=1 + len(extra_evidence),
            ),
        )

    return runner


def make_tool_registry(
    probe: ToolProbe,
    *,
    extra_evidence: tuple[AgentEvidence, ...] = (),
) -> ResearchToolRegistry:
    """官方构造面 ``default_registry``：真实元数据 × 探针 runner，零 IO。"""

    return default_registry(
        {
            name: probe_runner(name, probe, extra_evidence=extra_evidence)
            for name in TOOL_NAMES
        }
    )


def is_snapshot_tool(spec: ToolSpec) -> bool:
    """按 spec 运行时判形状，不写死名单（default_registry 的分派即事实源）。

    快照契约的判据是 ``query_scope == "episode"``（一回合一份完整快照，空参合法），
    不是「解析器恒等于 parse_snapshot_arguments」——financial_data 自 P0b 起带一个
    可选 ``report_period``，仍是快照，但解析器换了。
    """

    return spec.query_scope == "episode" or spec.parse_arguments is parse_snapshot_arguments


def is_url_tool(spec: ToolSpec) -> bool:
    """参数面只有一个 ``url`` 的取页类工具（web_fetch）。"""

    properties = spec.parameters.get("properties")
    return isinstance(properties, Mapping) and set(properties) == {"url"}


def valid_arguments(spec: ToolSpec) -> Mapping[str, object]:
    if is_snapshot_tool(spec):
        return {}
    if is_url_tool(spec):
        return {"url": "https://example.invalid/report/600519"}
    return {"query": "瑞华泰 产能"}


def invalid_arguments(spec: ToolSpec) -> Mapping[str, object]:
    """每种形状各自的坏参数：快照多给键、取页给空 url、query 给空串。"""

    if is_snapshot_tool(spec):
        return {"query": "多余参数"}
    if is_url_tool(spec):
        return {"url": ""}
    return {"query": ""}


def make_tool_context(
    *,
    task_id: str,
    allowed_capabilities: tuple[str, ...],
    timeout: float = 30.0,
) -> ResearchRunContext:
    frame = TaskFrame(
        raw_question="目前市场怎么看",
        user_goal="判断当前市场结构",
        question_type="market_forecast",
        subject="A股市场",
        subject_kind="market_pattern",
        market_scope="A股",
        timeframe="最近交易日",
        required_outputs=("direct_assessment",),
        assumptions=(),
        ambiguities=(),
        clarification_question=None,
        evidence_policy="current_market_scenarios",
        confidence=0.9,
    )
    return ResearchRunContext(
        contract=ResearchTaskContract(
            task_id=task_id,
            question=frame.raw_question,
            subject=frame.subject,
            subject_kind=frame.subject_kind,
            question_type=frame.question_type,
            required_outputs=(
                RequiredOutput("direct_assessment", "直接判断", (), True),
            ),
            allowed_capabilities=allowed_capabilities,
            research_tier="quick",
            freshness="current",
            evidence_plan=EvidencePlan(),
            task_frame_hash=frame.task_frame_hash,
        ),
        deadline=ResearchDeadline.from_timeout(timeout),
        policy=ResearchPolicy("quick", 3, timeout, 0.0),
        trace_parent_id=task_id,
        today="2026-07-25",
        latest_data_date="2026-07-24",
    )
