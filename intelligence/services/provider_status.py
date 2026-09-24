"""``provider_status``：模型点任何取数工具之前，先看一眼「哪些源现在真的 ready」。

抄的是 knevo ``finance_provider_status`` 的**形状**（spec capability-amplification §3.6）：他 22 次
调用里 ``finance_statement`` 无 provider、``finance_graph_context`` 找不到实体、``finance_shareholders``
失败——工具挂在菜单上、底下没源，模型试了才知道。我们把「试了才知道」改成「调用前自述」。

契约自己做（§3.6 三条）：

1. 空结果语义：「一个源都没 ready」本身是事实，不是证据缺口；本工具 ``produces=()``，不铸证据。
2. 来源分档与 as_of：本工具是元工具，自身无档次无 as_of；它**转述**每个工具的档次与 as_of 来源
   （`TOOL_FACTS` 表——与 `_TOOL_CONTRACTS` 说的同一件事的结构化形态，改一处两处都要改，
   `test_provider_status` 钉住两边一致）。
3. 参数：可选 ``tools`` 过滤；未知工具名 → ``error=unknown_tool:<name>``，不静默回空。

§4 同一份数据：列出的是**本轮授权**的工具（``contract.allowed_capabilities`` ∩ 注册表），与产物里
的 ``authorized_capabilities`` 同源——模型看到的可用面 == 产物记的。就绪探针只做存在性 / 开关检查
（env 标志、库文件、知识库目录、解释器），**绝不外呼**：探针本身不能是一次取数。
"""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from intelligence.paths import default_market_db_path, default_paths
from intelligence.services import calculation_sandbox
from intelligence.services.agent_research import AgentToolContext
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.research_contract import ResearchRunContext
from intelligence.services.research_tool_registry import (
    ToolRunResult,
    ToolSpec,
    provider_status_tool_spec,
)

PROVIDER_STATUS_TOOL = "provider_status"
_PROVIDER = "registry:provider_status"


@dataclass(frozen=True)
class ToolFacts:
    """一个工具的来源档次与 as_of 来源——结构化、给自述与产物读，不给模型编。"""

    tier: str
    as_of_source: str


# 与 _TOOL_CONTRACTS 的散文同一份事实；test_provider_status 钉两边一致（档次 / as_of 关键词都要在契约里）。
TOOL_FACTS: dict[str, ToolFacts] = {
    "finance_query": ToolFacts("L4_structured", "交易日（数据日）"),
    "market_data": ToolFacts("L4_structured", "交易日（数据日）"),
    "mainline_context": ToolFacts("L4_structured", "交易日（数据日）"),
    "financial_data": ToolFacts("L2_structured", "披露日（缺则报告期截止日）"),
    "web_search": ToolFacts("public_web（二手）", "抓取日；正文日期以取页为准"),
    "web_fetch": ToolFacts("public_web（二手）", "页面日期；取不到记抓取日"),
    "news_search": ToolFacts("news（二手）", "资讯发布日"),
    "kb_search": ToolFacts("知识库（回填材料）", "文档自述日期；无则未定"),
    "evidence_search": ToolFacts("知识证据（回填材料）", "证据登记日期"),
    "evidence_lookup": ToolFacts("证据索引（回填材料）", "证据登记日期；标「无日期」者不支撑时效结论"),
    "graph_lookup": ToolFacts("概念图谱（关系，不是数值）", "无（关系无日期）"),
    "memory_lookup": ToolFacts("用户记忆（用户自己的判断）", "判断记录日"),
    "l3_lookup": ToolFacts("L3 公告（一手）", "披露日"),
    "sub_research": ToolFacts("继承分支实际调用的工具", "继承分支证据"),
    "derived_calculation": ToolFacts("derived_calculation（不高于输入最低档）", "输入证据里最旧的 as_of"),
    PROVIDER_STATUS_TOOL: ToolFacts("元工具（不铸证据）", "无"),
}


@dataclass(frozen=True)
class ToolReadiness:
    tool: str
    ready: bool
    why: str
    tier: str
    as_of_source: str
    produces: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "tool": self.tool,
            "ready": self.ready,
            "why": self.why,
            "tier": self.tier,
            "as_of_source": self.as_of_source,
            "produces": list(self.produces),
        }


# ── 就绪探针：只做存在性 / 开关检查，绝不外呼 ──────────────────────────


def _flag_on(name: str, default: str = "1") -> bool:
    return os.environ.get(name, default).strip().lower() not in {"0", "false", "off"}


def _flag_opt_in(name: str) -> bool:
    return str(os.environ.get(name) or "").strip().lower() in {"1", "true", "yes", "on"}


def _probe_duckdb() -> tuple[bool, str]:
    path = default_market_db_path()
    return (True, f"本地行情库在（{path.name}）") if path.exists() else (False, f"本地行情库不存在：{path}")


def _probe_knowledge_wiki() -> tuple[bool, str]:
    wiki = Path(default_paths().knowledge_wiki)
    return (True, "知识库目录在") if wiki.is_dir() else (False, f"知识库目录不存在：{wiki}")


def _probe_graph() -> tuple[bool, str]:
    wiki = Path(default_paths().knowledge_wiki)
    graph = wiki / "relations" / "concept_graph.json"
    return (True, "概念图谱文件在") if graph.exists() else (False, f"概念图谱文件不存在：{graph}")


def _probe_env(flag: str, *, label: str) -> Callable[[], tuple[bool, str]]:
    def probe() -> tuple[bool, str]:
        return (True, f"{label}开着") if _flag_on(flag) else (False, f"{flag}=0（{label}已关）")

    return probe


def _probe_l3() -> tuple[bool, str]:
    if _flag_opt_in("FINANCE_L3_LOOKUP_ENABLED"):
        return True, "公告查询已启用"
    return False, "FINANCE_L3_LOOKUP_ENABLED 未开（默认关，需显式打开）"


def _probe_sandbox() -> tuple[bool, str]:
    if not sys.executable or not os.path.exists(sys.executable):
        return False, "沙箱解释器不存在"
    layer = "seatbelt+process" if calculation_sandbox.seatbelt_available() else "process"
    return True, f"沙箱可用（enforcement={layer}）"


def _probe_registered() -> tuple[bool, str]:
    return True, "已装配（按 episode 绑定）"


_PROBES: dict[str, Callable[[], tuple[bool, str]]] = {
    "finance_query": _probe_duckdb,
    "market_data": _probe_duckdb,
    "mainline_context": _probe_duckdb,
    "financial_data": _probe_env("FINANCE_FINANCIALS_FETCH", label="财务取数"),
    "web_search": _probe_env("FINANCE_WEB_SEARCH", label="网页检索"),
    "web_fetch": _probe_env("FINANCE_WEB_FETCH", label="取页"),
    "news_search": _probe_env("FINANCE_NEWS_FETCH", label="资讯检索"),
    "kb_search": _probe_knowledge_wiki,
    "evidence_search": _probe_knowledge_wiki,
    "evidence_lookup": _probe_knowledge_wiki,
    "graph_lookup": _probe_graph,
    "l3_lookup": _probe_l3,
    "memory_lookup": _probe_registered,
    "sub_research": _probe_registered,
    "derived_calculation": _probe_sandbox,
    PROVIDER_STATUS_TOOL: _probe_registered,
}


def probe_tool(name: str) -> tuple[bool, str]:
    probe = _PROBES.get(name, _probe_registered)
    try:
        return probe()
    except Exception as exc:  # noqa: BLE001 - 探针坏了要说「探针坏了」，不能装作 ready
        return False, f"探针异常：{type(exc).__name__}"


def readiness_for(
    specs: Sequence[ToolSpec],
    *,
    allowed_capabilities: Sequence[str],
    only: Sequence[str] = (),
) -> tuple[ToolReadiness, ...]:
    """本轮授权工具的就绪自述（§4：与 authorized_capabilities 同一份数据）。"""

    allowed = set(allowed_capabilities)
    wanted = set(only)
    rows: list[ToolReadiness] = []
    for spec in specs:
        if spec.capability not in allowed:
            continue
        if wanted and spec.name not in wanted:
            continue
        ready, why = probe_tool(spec.name)
        facts = TOOL_FACTS.get(spec.name, ToolFacts("未登记", "未登记"))
        rows.append(
            ToolReadiness(
                tool=spec.name,
                ready=ready,
                why=why,
                tier=facts.tier,
                as_of_source=facts.as_of_source,
                produces=tuple(sorted(spec.produces)),
            )
        )
    return tuple(rows)


def render_observation(
    rows: Sequence[ToolReadiness], *, unauthorized: int, checked_at: str
) -> str:
    if not rows:
        return (
            f"本轮没有任何已授权的取数 / 检索源（checked_at={checked_at}）。"
            "这是事实不是证据缺口：只能基于已有证据作答或说明无法取证。"
        )
    lines = []
    for row in rows:
        mark = "✓" if row.ready else "✗"
        lines.append(
            f"{mark} {row.tool} — {row.why}｜档次 {row.tier}｜as_of {row.as_of_source}"
            + (f"｜可产出 {'/'.join(row.produces)}" if row.produces else "")
        )
    ready = sum(1 for row in rows if row.ready)
    head = f"本轮授权 {len(rows)} 个源，就绪 {ready} 个（checked_at={checked_at}）"
    if unauthorized:
        head += f"；另有 {unauthorized} 个已装配工具本轮未授权，不可点"
    tail = "未就绪的源不要点；点了会得到失败而不是「没有该信息」。档次与 as_of 来源是引用时的口径。"
    return head + "：\n" + "\n".join(lines) + "\n" + tail


# ── 绑定 ────────────────────────────────────────────────────────────────


def bind_provider_status_tool(
    *,
    registry_specs: Callable[[], Sequence[ToolSpec]],
    current_context: Callable[[], ResearchRunContext],
    now: Callable[[], datetime] | None = None,
) -> ToolSpec:
    """绑出这一个 episode 的 ``provider_status``。

    ``registry_specs`` / ``current_context`` 都是可调用：注册表在绑定后还会并进别的 episode 期
    工具，context 在 PLAN 升档时会换——自述要读**此刻**的授权面。
    """

    clock = now if now is not None else (lambda: datetime.now().astimezone())

    def runner(args_json: str, tool_context: AgentToolContext) -> ToolRunResult:
        args = json.loads(args_json)
        tool_context.check_cancelled()
        only = tuple(str(item) for item in (args.get("tools") or ()))
        specs = tuple(registry_specs())
        known = {spec.name for spec in specs}
        unknown = [name for name in only if name not in known]
        if unknown:
            detail = "unknown_tool:" + ",".join(unknown)
            return ToolRunResult(
                evidence=(),
                observation=(
                    f"参数 tools 里有不存在的工具名：{', '.join(unknown)}；"
                    f"可选的是 {', '.join(sorted(known))}。"
                ),
                trace=ProviderTrace(
                    provider=_PROVIDER,
                    capability=PROVIDER_STATUS_TOOL,
                    status="error",
                    detail=detail,
                    result_count=0,
                ),
            )
        allowed = current_context().contract.allowed_capabilities
        rows = readiness_for(specs, allowed_capabilities=allowed, only=only)
        unauthorized = sum(1 for spec in specs if spec.capability not in set(allowed))
        checked_at = clock().isoformat(timespec="seconds")
        return ToolRunResult(
            evidence=(),
            observation=render_observation(rows, unauthorized=unauthorized, checked_at=checked_at),
            trace=ProviderTrace(
                provider=_PROVIDER,
                capability=PROVIDER_STATUS_TOOL,
                status="success",
                detail=json.dumps(
                    {"authorized": len(rows), "ready": sum(1 for r in rows if r.ready)},
                    ensure_ascii=False,
                ),
                result_count=sum(1 for row in rows if row.ready),
            ),
        )

    return provider_status_tool_spec(runner)


def readiness_snapshot(
    specs: Sequence[ToolSpec], *, allowed_capabilities: Sequence[str]
) -> list[Mapping[str, object]]:
    """给产物 / 审计用的同一份数据（不经模型）。"""

    return [row.to_dict() for row in readiness_for(specs, allowed_capabilities=allowed_capabilities)]
