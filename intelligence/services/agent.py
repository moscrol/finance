"""Agent loop (P1 MVP) over the same multi-source retrieval as :mod:`ask`.

Where ``ask.answer_query`` runs a *fixed* pipeline (always query S/G/R/W +
route 模块, then assemble), this module lets the LLM decide — per turn — *which*
read-only retrieval tool to call, with *what* arguments, inspect the result, and
either call more tools or write a grounded final answer. The tools are thin
wrappers over the exact same adapters/services ``ask`` uses, so the evidence and
``[S#]/[G#]/[R#]/[W#]`` citation scheme are identical; only the orchestration is
now model-driven instead of hard-coded.

Design constraints (same discipline as the rest of the `ask` stack):
- **Opt-in, default off.** Nothing here runs unless the caller invokes the
  ``agent`` entrypoint. Template / ``--compose`` / multi-turn ``chat`` are
  untouched.
- **Read-only tools only.** Every tool reads committed snapshots / the KB; none
  writes, shells out arbitrary commands, or mutates state. (题材模块 run the same
  vetted ``radar.py`` subprocess ``ask`` already runs.)
- **Graceful degrade.** No LLM key, HTTP error, or a model that never emits a
  tool call → :class:`AgentResult` carries ``answer=None`` + a reason so callers
  fall back (e.g. to template / compose).
- **Grounding preserved.** Tools return evidence lines already tagged with
  citation numbers; the system prompt forbids citing anything a tool did not
  return.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from intelligence.adapters.knowledge import KnowledgeAdapter
from intelligence.services import kb_rag, llm_refine
from intelligence.services.ask import (
    AskOptions,
    Citation,
    _evidence_is_stale,
    load_theme_candidates,
    match_candidate,
)
from intelligence.services.theme_modules import ALL_MODULES, run_module

DEFAULT_MAX_STEPS = 6


_AGENT_SYSTEM_PROMPT = (
    "你是资深A股题材研究员，现在以 agent 方式工作：你可以调用工具去检索多源证据，"
    "自己决定调用哪些工具、用什么关键词、要不要再补一刀，直到证据足够再作答。\n"
    "可用证据源：盘面快照(S)、知识图谱概念与公司分层(G)、证据库条目(R)、"
    "wiki 语义召回(W)、题材模块产出(brief/front-map/deep-dive/replay/scan/migrate)。\n"
    "工作准则：\n"
    "1) 先想清楚问题要什么，再按需调用工具；不要无脑把所有工具都调一遍，也不要在证据不足时硬答；\n"
    "2) 只能使用工具实际返回过的事实/公司/数字，严禁编造工具没返回的内容；\n"
    "3) 最终回答里，关键判断/公司/数字/催化之后必须用方括号标注引用编号（如 [S1][R4][G2]），"
    "这些编号来自工具返回的证据；\n"
    "4) 务必区分「核心/真实暴露」与「graph_only 低置信待验证」两类公司，后者只能当预期差线索、"
    "不可当基本面依据；\n"
    "5) 收尾要自然连贯（短段落即可，别堆 markdown 标题），内容覆盖：一句话结论 → 当前盘面状态 → "
    "产业链与公司分层 → 关键催化与证据 → 分歧与风险 → 接下来该跟踪什么；\n"
    "6) 不输出任何买卖指令，结尾以「（非投资建议）」收尾；证据确实不足就直说「证据不足」，不要编造。"
)

_FORCE_FINAL_NUDGE = (
    "（已达到工具调用步数上限。请仅基于上面工具已经返回的证据，直接给出最终回答，"
    "不要再调用工具；继续用 [编号] 标注引用，证据不足就直说，结尾以「（非投资建议）」收尾。）"
)

_MODULE_DESC = (
    "运行一个题材模块并返回其要点（带 [G#] 引用）。module 取值："
    "brief=产业维速览(产业链分层+核心个股)、front-map=前瞻信息地图、deep-dive=题材深拆、"
    "replay=时间维发酵复盘(带日期的硬证据时间线)、scan=全库横扫、migrate=横向迁移对标。"
)

AGENT_TOOLS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "search_market_snapshot",
            "description": (
                "查询某题材在盘面快照(theme-candidates 导出)里的信号与市场环境，返回带 [S#] 引用的"
                "盘面证据（信号触发、评分、市场环境）。盘面快照是某交易日的导出、非实时。题材未命中返回提示。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "theme": {"type": "string", "description": "题材/概念词，如 液冷、光模块、固态电池"}
                },
                "required": ["theme"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_graph",
            "description": (
                "在知识图谱里检索该题材命中的概念，以及相关公司的分层暴露（核心层/中间层/外围弱关联层），"
                "返回带 [G#] 引用的图谱证据。用于「拆解产业链/公司分层」。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "题材/概念/公司词"}
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_evidence",
            "description": (
                "在证据库(evidence_index)里检索某个题材或公司的具体证据条目（公告/订单/送样/认证/产能等），"
                "返回带 [R#] 引用、含来源与日期、过期会标注 ⚠️。用于核实「某公司证据硬不硬」。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "target": {"type": "string", "description": "题材或公司名，如 液冷 / 强瑞技术"}
                },
                "required": ["target"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_wiki",
            "description": (
                "对知识库 wiki 做语义召回(hybrid 向量检索)，返回带 [W#] 引用的相关页摘录。用于补充"
                "产业链路线定义、行业规模数字等图谱里没有的背景。索引缺失/超时会返回提示。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "语义检索词"},
                    "k": {"type": "integer", "description": "返回页数，默认 6", "default": 6},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_theme_module",
            "description": _MODULE_DESC,
            "parameters": {
                "type": "object",
                "properties": {
                    "module": {
                        "type": "string",
                        "enum": list(ALL_MODULES),
                        "description": "模块名",
                    },
                    "query": {"type": "string", "description": "题材词；留空则用本轮问题"},
                },
                "required": ["module"],
            },
        },
    },
]


@dataclass
class AgentStep:
    """One tool invocation in the agent's trace (for transparency/eval)."""

    tool: str
    args: dict[str, Any]
    result_preview: str


@dataclass
class AgentResult:
    answer: str | None
    steps: list[AgentStep] = field(default_factory=list)
    citations: list[Citation] = field(default_factory=list)
    provider: str | None = None
    reason: str = ""
    sources_used: set[str] = field(default_factory=set)

    @property
    def ok(self) -> bool:
        return bool(self.answer)


class AgentSession:
    """Drives a single agent run: holds retrieval context + a shared citation
    registry, exposes the read-only tools, and runs the tool-calling loop."""

    def __init__(
        self,
        options: AskOptions,
        model_override: str | None = None,
        timeout: int = 90,
        max_steps: int = DEFAULT_MAX_STEPS,
    ) -> None:
        self.options = options
        self.model_override = model_override
        self.timeout = timeout
        self.max_steps = max_steps
        self.knowledge = KnowledgeAdapter(wiki_root=options.kb_wiki)
        self.citations: list[Citation] = []
        self.sources_used: set[str] = set()
        self._export_name: str | None = None
        # multi-turn conversation state (持续对话 + 跨轮证据复用)
        self.messages: list[dict] | None = None
        self.provider_name: str | None = None

    # --- citation registry (mirrors ask.answer_query's `cite` closure) ---
    def _cite(self, prefix: str, source: str, detail: str = "") -> str:
        n = sum(1 for c in self.citations if c.tag.startswith(prefix)) + 1
        tag = f"{prefix}{n}"
        self.citations.append(Citation(tag=tag, source=source, detail=detail))
        return f"[{tag}]"

    # --- tools (each returns a text block the LLM reads as a tool result) ---
    def tool_search_market_snapshot(self, theme: str) -> str:
        loaded = load_theme_candidates(self.options.exports_dir, self.options.date)
        if not loaded["found"]:
            return "盘面快照不可用：" + "；".join(loaded.get("warnings") or ["未找到导出文件"])
        self._export_name = Path(loaded.get("path", "")).name
        doc = loaded["doc"]
        candidate = match_candidate(theme or self.options.query, doc)
        if not candidate:
            return f"盘面快照（{doc.get('trade_date') or self.options.date}）未命中题材「{theme}」。"
        self.sources_used.add("S")
        lines: list[str] = [
            f"盘面快照日期：{doc.get('trade_date')}；命中题材："
            f"{candidate.get('canonical_concept') or candidate.get('market_theme')}"
            f"（{candidate.get('candidate_tier') or '?'}层，priority {candidate.get('priority_score')}）"
        ]
        for sd in (candidate.get("score_detail") or [])[:5]:
            tag = self._cite("S", f"{self._export_name} · score_detail.{sd.get('signal')}", str(sd.get("source", "")))
            lines.append(f"信号 {sd.get('signal')}（{sd.get('score')}）：{sd.get('reason', '')} {tag}")
        ctx = doc.get("market_context") or {}
        if ctx:
            caps = "、".join(
                f"{s.get('name')}({s.get('ratio')}%,{s.get('capacity_type')})"
                for s in (ctx.get("capacity_sectors") or [])[:3]
            )
            tag = self._cite("S", f"{self._export_name} · market_context")
            lines.append(
                f"市场环境：{ctx.get('market_stage')}，成交 {ctx.get('total_amount')}，"
                f"涨停 {ctx.get('limit_up')} / 跌停 {ctx.get('limit_down')}，容量前三 {caps} {tag}"
            )
        triggers = "、".join(candidate.get("trigger_types", []) or []) or "无盘面触发"
        lines.append(f"触发类型：{triggers}")
        return "\n".join(lines)

    def tool_search_graph(self, query: str) -> str:
        lines: list[str] = []
        concepts = self.knowledge.get_concept_matches(query, limit=self.options.top_concepts)
        if concepts.get("found"):
            self.sources_used.add("G")
            names = "、".join(f"{i['concept']}({i['score']})" for i in concepts["items"])
            tag = self._cite("G", "knowledge-base · wiki/relations/concept_graph.json")
            lines.append(f"命中概念：{names} {tag}")
        exposures = self.knowledge.get_exposure_matches(query, limit=self.options.top_companies)
        if exposures.get("found"):
            self.sources_used.add("G")
            tiers: dict[str, list[str]] = {"core": [], "peripheral": [], "other": []}
            for row in exposures["items"]:
                strength = str(row.get("strength") or "").lower()
                conf = str(row.get("confidence") or "")
                layer = str(row.get("evidence_layer") or "")
                label = f"{row.get('company')}({row.get('ticker')}|{row.get('role') or '—'}|{conf or '?'}/{layer or '?'})"
                if strength in {"core", "strong"} or conf == "high":
                    tiers["core"].append(label)
                elif strength in {"peripheral", "weak"} or layer == "graph_only":
                    tiers["peripheral"].append(label)
                else:
                    tiers["other"].append(label)
            tag = self._cite("G", "knowledge-base · wiki/relations/entity_exposures.json")
            if tiers["core"]:
                lines.append(f"核心层（真实暴露）：{'、'.join(tiers['core'])} {tag}")
            if tiers["other"]:
                lines.append(f"中间层：{'、'.join(tiers['other'])} {tag}")
            if tiers["peripheral"]:
                lines.append(
                    f"外围/弱关联层（graph_only 低置信，待验证、只作预期差线索）：{'、'.join(tiers['peripheral'])} {tag}"
                )
        if not lines:
            return f"知识图谱未命中「{query}」（可能是新词/别名未登记）。"
        return "\n".join(lines)

    def tool_search_evidence(self, target: str) -> str:
        ev = self.knowledge.get_evidence(target, limit=self.options.max_evidence)
        if not ev.get("found") or not ev.get("items"):
            return f"证据库未命中「{target}」。"
        self.sources_used.add("R")
        lines: list[str] = []
        for item in ev["items"][: self.options.max_evidence]:
            stale = _evidence_is_stale(item, self.options.stale_days)
            tag = self._cite(
                "R",
                "knowledge-base · wiki/relations/evidence_index.json",
                f"target={item.get('target')} source={item.get('source')}",
            )
            mark = " ⚠️过期" if stale else ""
            lines.append(
                f"{item.get('target')}：{str(item.get('evidence'))[:120]}"
                f"（{item.get('source')}, {item.get('source_date') or '无日期'}, "
                f"质量 {item.get('confidence') or '?'}{mark}） {tag}"
            )
        return "\n".join(lines)

    def tool_search_wiki(self, query: str, k: int | None = None) -> str:
        wr = kb_rag.retrieve(
            query,
            self.options.kb_wiki,
            k=k or self.options.wiki_rag_k,
            mode=self.options.wiki_rag_mode,
            timeout=self.options.wiki_rag_timeout,
            excerpt_chars=self.options.wiki_rag_excerpt,
        )
        if not wr.ok:
            return f"wiki 语义召回不可用：{wr.warning or '未知原因'}"
        if not wr.hits:
            return f"wiki 语义召回无命中：「{query}」"
        self.sources_used.add("W")
        lines: list[str] = []
        for h in wr.hits:
            nb = "·邻居扩展" if h.via_neighbor else ""
            tag = self._cite("W", f"knowledge-base · {h.file_path}", f"{wr.command}｜{h.title}")
            lines.append(f"{h.title}（相关度 {round(h.score, 4)}{nb}）：{h.excerpt} {tag}")
        return "\n".join(lines)

    def tool_run_theme_module(self, module: str, query: str | None = None) -> str:
        if module not in ALL_MODULES:
            return f"未知模块「{module}」；可选：{'、'.join(ALL_MODULES)}"
        mr = run_module(module, query or self.options.query, self.options.kb_wiki, self.options.module_timeout)
        if not mr.ok or not mr.highlights:
            return f"模块 {module} 无产出：{mr.warning or '无产出'}"
        self.sources_used.add("module")
        tag = self._cite(
            "G",
            mr.citation_source,
            f"{mr.command}" + (f" | {mr.citation_detail}" if mr.citation_detail else ""),
        )
        lines = [f"模块 {module}（{mr.title}）："]
        lines.extend(f"{hl} {tag}" for hl in mr.highlights)
        if mr.follow_ups:
            lines.append("可继续追问：" + "；".join(mr.follow_ups[:3]))
        return "\n".join(lines)

    @property
    def _dispatch(self) -> dict[str, Callable[..., str]]:
        return {
            "search_market_snapshot": self.tool_search_market_snapshot,
            "search_graph": self.tool_search_graph,
            "search_evidence": self.tool_search_evidence,
            "search_wiki": self.tool_search_wiki,
            "run_theme_module": self.tool_run_theme_module,
        }

    def _run_tool(self, name: str, args: dict[str, Any]) -> str:
        fn = self._dispatch.get(name)
        if fn is None:
            return f"未知工具「{name}」。"
        try:
            return fn(**args)
        except TypeError as exc:
            return f"工具「{name}」参数错误：{exc}"
        except Exception as exc:  # pragma: no cover - defensive
            return f"工具「{name}」执行失败（{type(exc).__name__}）：{exc}"

    # --- the loop（multi-turn: 记忆 + 每轮自主调工具）---
    def run(self, query: str) -> AgentResult:
        """One-shot 便捷封装 == 在一段全新对话上调 :meth:`start`。"""
        return self.start(query)

    def start(self, query: str) -> AgentResult:
        """Turn 1：开一段新对话（system + 首问），自主调工具后作答。"""
        self.messages = [
            {"role": "system", "content": _AGENT_SYSTEM_PROMPT},
            {"role": "user", "content": self._user_prompt(query)},
        ]
        return self._drive()

    def ask(self, query: str) -> AgentResult:
        """追问：复用既有对话历史 + 已抓到的证据（引用编号跨轮延续），本轮仍由
        LLM 自主决定要不要再调工具补查。若本轮没拿到回答则回滚，保持历史一致以便重试。"""
        if self.messages is None:
            return self.start(query)
        msg_mark = len(self.messages)
        cite_mark = len(self.citations)
        self.messages.append({"role": "user", "content": self._followup_prompt(query)})
        res = self._drive()
        if not res.ok:
            del self.messages[msg_mark:]
            del self.citations[cite_mark:]
        return res

    def _drive(self) -> AgentResult:
        """跑工具调用循环（操作 self.messages，跨轮持久）。"""
        assert self.messages is not None
        steps: list[AgentStep] = []
        for _ in range(self.max_steps):
            msg, provider, reason = llm_refine.chat_with_tools(
                self.messages,
                AGENT_TOOLS,
                model_override=self.model_override,
                timeout=self.timeout,
            )
            if msg is None:
                return self._result(None, steps, provider, reason)
            tool_calls = msg.get("tool_calls") or []
            if not tool_calls:
                answer = (msg.get("content") or "").strip() or None
                if answer:
                    self.messages.append({"role": "assistant", "content": answer})
                return self._result(answer, steps, provider, "" if answer else "LLM 未给出回答")
            self.messages.append(_assistant_echo(msg))
            for tc in tool_calls:
                fn = tc.get("function") or {}
                name = fn.get("name") or ""
                raw_args = fn.get("arguments")
                try:
                    args = json.loads(raw_args) if isinstance(raw_args, str) and raw_args.strip() else (raw_args or {})
                    if not isinstance(args, dict):
                        args = {}
                except Exception:
                    args = {}
                out = self._run_tool(name, args)
                steps.append(AgentStep(tool=name, args=args, result_preview=out[:300]))
                self.messages.append({"role": "tool", "tool_call_id": tc.get("id"), "content": out})

        # exhausted the step budget → force a tool-free final answer（nudge 不写进长期历史）
        final_messages = self.messages + [{"role": "user", "content": _FORCE_FINAL_NUDGE}]
        content, provider, reason = llm_refine.complete(
            final_messages, model_override=self.model_override, timeout=self.timeout
        )
        answer = (content or "").strip() or None
        if answer:
            self.messages.append({"role": "assistant", "content": answer})
        return self._result(
            answer, steps, provider,
            reason or ("达到工具调用步数上限，已强制收尾" if answer else "达到步数上限且无回答"),
        )

    def _result(self, answer, steps, provider, reason) -> AgentResult:
        if provider is not None:
            self.provider_name = provider.name
        return AgentResult(
            answer=answer,
            steps=steps,
            citations=self.citations,
            provider=self.provider_name,
            reason=reason,
            sources_used=self.sources_used,
        )

    def _user_prompt(self, query: str) -> str:
        date_note = f"（盘面快照参考日期：{self.options.date}）" if self.options.date else ""
        return f"题材问题：{query}{date_note}\n请按需调用工具检索证据后作答。"

    def _followup_prompt(self, query: str) -> str:
        return (
            f"追问：{query}\n"
            "可以直接复用上文工具已经返回过的证据作答；若需要新的事实，再自行调用工具补查。"
            "仍然只能引用工具实际返回过的内容（带 [编号]），不要编造；结尾以「（非投资建议）」收尾。"
        )


def _assistant_echo(msg: dict) -> dict:
    """Echo the assistant turn (incl. tool_calls) back into the message list so
    the next round-trip has valid tool-call context."""
    echo: dict = {"role": "assistant", "content": msg.get("content")}
    if msg.get("tool_calls"):
        echo["tool_calls"] = msg["tool_calls"]
    return echo
