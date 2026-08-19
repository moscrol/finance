from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# NOTE: workflow modules are imported lazily inside each command handler so the
# CLI (and the duckdb-free `ask` command) can run in environments without the
# market database driver installed.


def _resolve_kb_mode(
    query: str, kb_mode_arg: str | None, wiki_rag_mode_arg: str
) -> tuple[str, str | None, str]:
    """把 --kb-mode（或问句自然语言触发词）解析成（检索方式, 索引目录覆盖）。

    --kb-mode 显式优先；否则按问句触发词；都没有 → 结构版默认（行为逐字节不变）。
    --wiki-rag-mode 被显式改成非默认 hybrid 时，作为低层逃生口覆盖模式档里的检索方式。
    返回 (wiki_rag_mode, wiki_rag_index_dir, error)；error 非空表示 --kb-mode 取值非法。
    """
    from intelligence.services import kb_rag

    if kb_mode_arg:
        canonical = kb_rag.normalize_kb_mode(kb_mode_arg)
        if canonical is None:
            return "hybrid", None, (
                f"\u65e0\u6cd5\u8bc6\u522b --kb-mode\u300c{kb_mode_arg}\u300d\uff1b\u53ef\u7528\uff1a"
                "structured/fast/\u7ed3\u6784/\u7ed3\u6784\u7248/\u901f\u67e5 \u6216 full/deep/\u5168\u6587/\u5168\u6587\u7248/\u6df1\u5ea6"
            )
        mode_name: str | None = canonical
    else:
        mode_name = kb_rag.detect_kb_mode(query)  # None → 结构版

    index_dir, rag_mode = kb_rag.kb_mode_profile(mode_name)
    if wiki_rag_mode_arg and wiki_rag_mode_arg != "hybrid":
        rag_mode = wiki_rag_mode_arg  # 显式 --wiki-rag-mode 覆盖模式档检索方式
    return rag_mode, index_dir, ""


_WIKI_RAG_MODES = ("bm25", "dense", "hybrid", "rerank")


def add_shared_retrieval_arguments(
    parser: argparse.ArgumentParser,
    *,
    with_module_fanout: bool = True,
) -> None:
    """Retrieval knobs shared by ask / chat / agent. Escape hatches, not the default door."""

    parser.add_argument(
        "--date",
        default=None,
        help="theme-candidates export date YYYY-MM-DD; defaults to latest",
    )
    parser.add_argument(
        "--exports-dir", default=None, help="Override market_feature_store/exports dir"
    )
    parser.add_argument(
        "--kb-wiki",
        default=None,
        help="Knowledge-base wiki root (contains relations/); defaults to env/auto",
    )
    parser.add_argument(
        "--top-companies", type=int, default=12, help="Max exposed companies to recall"
    )
    if with_module_fanout:
        parser.add_argument(
            "--modules",
            default=None,
            help="Comma-separated theme-radar backends to fan out to "
            "(brief,front-map,deep-dive,replay,scan,migrate). Default: auto-route by query.",
        )
        parser.add_argument(
            "--no-modules",
            action="store_true",
            help="Disable theme-radar module fan-out (graph+盘面 only)",
        )
        parser.add_argument(
            "--no-wiki-rag",
            action="store_true",
            help="Disable the W source (knowledge-base hybrid 向量语义召回 wiki 候选页). "
            "Auto-skips anyway when the KB repo / rag_index.py / 向量索引 is unavailable.",
        )
    parser.add_argument(
        "--module-timeout",
        type=int,
        default=180,
        help="Per-module subprocess timeout in seconds",
    )
    parser.add_argument(
        "--wiki-rag-k",
        type=int,
        default=6,
        help="Max wiki pages to recall via vector search (W source)",
    )
    parser.add_argument(
        "--wiki-rag-mode",
        default="hybrid",
        choices=list(_WIKI_RAG_MODES),
        help="Retrieval mode for the W source (default hybrid = BM25 + dense RRF; rerank = 全文版专用)",
    )
    parser.add_argument(
        "--wiki-rag-timeout",
        type=int,
        default=90,
        help="W source rag_index.py subprocess timeout in seconds",
    )
    parser.add_argument(
        "--kb-mode",
        default=None,
        metavar="MODE",
        help="W 源查询模式：structured(默认，别名 fast/结构/速查)=.rag_index+hybrid；"
        "full(别名 deep/全文/深度)=.rag_index_full+rerank。不指定则按问句自然语言触发词"
        "(深挖/看原文/原文/权威/完整版/深度)自动判定；无触发词时为 structured（与历史逐字节一致）。",
    )


def add_ask_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "ask", help="Unified multi-source ask: KB graph (G/R) + market 盘面 snapshot (S) + wiki 向量语义召回 (W)"
    )
    parser.add_argument("query", help="Question / theme term, e.g. 液冷服务器")
    add_shared_retrieval_arguments(parser)
    parser.add_argument(
        "--llm",
        action="store_true",
        help="Refine 结论/交易含义 with an LLM (needs DEEPSEEK_API_KEY/MOONSHOT_API_KEY/"
        "DASHSCOPE_API_KEY/ZHIPU_API_KEY/OPENAI_API_KEY or LLM_API_KEY). No key -> template fallback.",
    )
    parser.add_argument(
        "--compose",
        action="store_true",
        help="让 LLM 把多源证据有机融合成一段对话式回答（带内联引用），附在六段证据之上。"
        "需 DEEPSEEK_API_KEY 等；无 key/失败则降级为模板（与 --llm 互不影响）。",
    )
    parser.add_argument("--llm-model", default=None, help="Override LLM model id (else provider default / LLM_MODEL)")
    parser.add_argument("--llm-timeout", type=int, default=60, help="LLM HTTP timeout in seconds")
    parser.add_argument(
        "--detail",
        action="store_true",
        help="Append each routed module's FULL report as a per-module 钻取 appendix (折叠块).",
    )
    parser.add_argument("--user", default=None, help="用户 id；compose 时读取该用户的 experience_cards.jsonl")
    parser.add_argument("--experience-cards-window", type=int, default=12, help="compose 时最多读取最近 N 张经验卡片")
    parser.add_argument(
        "--no-score",
        action="store_true",
        help="关闭回答后自动 rubric 评分（默认开启：纯规则零成本，记 users/<id>/answer_scores.jsonl，低分自动沉淀经验卡候选）。",
    )
    parser.add_argument(
        "--l3-lookup",
        action="store_true",
        help="启用 L3 官方证据工具补查（公告/问询函/互动易）。需配置 FINANCE_L3_CNINFO_CMD / FINANCE_L3_SSE_EINTERACT_CMD。",
    )
    parser.add_argument("--l3-lookup-timeout", type=int, default=480, help="单个 L3 工具调用超时秒数；SSE 首跑建 uid 缓存可能接近 7 分钟")
    parser.add_argument("--l3-lookup-limit", type=int, default=5, help="单个 L3 工具最多注入证据条数")
    parser.add_argument("--summary-json", default=None, help="Write workflow summary JSON")
    parser.add_argument(
        "--brief-json",
        default=None,
        help="个股深挖时把 StockResearchBrief（证据分层审计/检索遥测/反证计划/八步研究路径）写入 JSON 文件；非深挖问题无简报时跳过",
    )
    parser.add_argument(
        "--audit-ledger",
        default=None,
        help="检索审计台账 JSONL 路径：每次回答追加一条 query→命中→质量记录（检索模式/命中分布/分数/降级/证据裁定/失败标签），供 recall 评估与失败样本复盘",
    )
    parser.add_argument(
        "--no-clarify",
        action="store_true",
        help="关闭澄清追问前置门（默认开：空问题/纯空泛词面先反问不硬答；带实质内容的问题不受影响）。",
    )
    parser.add_argument(
        "--serial-blocks",
        action="store_true",
        help="关闭 compose 取数块并行（退回串行，调试用；输出与并行逐字节一致）。",
    )
    parser.set_defaults(func=cmd_ask)


def add_chat_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "chat",
        help="多轮对话（追问）：首轮多源检索(S/G/R/W/模块)+有机合成，后续追问复用首轮证据+对话历史"
        "（带记忆，仍守 grounding/引用、不重新检索）。需 LLM key；无 key 无法进入多轮、退回模板。",
    )
    parser.add_argument("query", help="首轮问题 / 题材词，如 液冷")
    add_shared_retrieval_arguments(parser)
    parser.add_argument("--llm-model", default=None, help="Override LLM model id (else provider default / LLM_MODEL)")
    parser.add_argument("--llm-timeout", type=int, default=60, help="LLM HTTP timeout in seconds")
    parser.add_argument("--user", default=None, help="用户 id；首轮 compose 时读取该用户的 experience_cards.jsonl")
    parser.add_argument("--experience-cards-window", type=int, default=12, help="首轮 compose 时最多读取最近 N 张经验卡片")
    parser.add_argument(
        "--no-score",
        action="store_true",
        help="关闭首轮回答后自动 rubric 评分（默认开启；只评首轮全量检索合成的回答，追问不评）。",
    )
    parser.add_argument(
        "-f", "--follow-up", dest="follow_ups", action="append", default=[],
        help="追问（可重复）。提供后走非交互：首轮+依次跑完所有追问即退出（便于脚本/演示）。"
        "不提供则进入交互 REPL（输入追问，空行 / exit / quit 退出）。",
    )
    parser.add_argument(
        "--no-clarify",
        action="store_true",
        help="关闭澄清追问前置门（默认开：首轮问题明确模糊时先反问、不烧整次检索）。",
    )
    parser.set_defaults(func=cmd_chat)


def cmd_chat(args: argparse.Namespace) -> int:
    from intelligence.services.ask import AskOptions
    from intelligence.services.ask_chat import AskConversation

    modules = tuple(m.strip() for m in args.modules.split(",") if m.strip()) if args.modules else None
    rag_mode, kb_index_dir, kb_err = _resolve_kb_mode(args.query, args.kb_mode, args.wiki_rag_mode)
    if kb_err:
        print(kb_err, file=sys.stderr)
        return 2
    conv = AskConversation(
        AskOptions(
            query=args.query,
            date=args.date,
            exports_dir=args.exports_dir,
            kb_wiki=args.kb_wiki,
            top_companies=args.top_companies,
            use_modules=not args.no_modules,
            modules=modules,
            module_timeout=args.module_timeout,
            use_wiki_rag=not args.no_wiki_rag,
            wiki_rag_k=args.wiki_rag_k,
            wiki_rag_mode=rag_mode,
            wiki_rag_timeout=args.wiki_rag_timeout,
            wiki_rag_index_dir=kb_index_dir,
            compose=True,
            user=args.user,
            experience_cards_window=args.experience_cards_window,
            clarify=not args.no_clarify,
        ),
        model_override=args.llm_model,
        timeout=args.llm_timeout,
    )

    def _emit(turn) -> None:
        who = f"助手·{turn.provider}" if turn.provider else "助手"
        print(f"## 你\n{turn.question}\n")
        print(f"## {who}\n{turn.answer}\n")
        if turn.warning and not turn.composed:
            print(f"> ⚠ {turn.warning}\n")

    print(f"# chat：{args.query}\n")
    first = conv.start()
    _emit(first)
    if conv.first_result is not None and conv.first_result.clarify is not None:
        # 澄清追问：结构化追问已作为首轮回复印出，用户补充后重新发起 chat。
        return 0
    if first.composed and not args.no_score:
        _auto_score_answer(args.query, first.answer, user=args.user)
    if not conv.ready:
        # No LLM key / turn-1 degraded — fall back to the structured template once.
        if conv.first_result is not None:
            from intelligence.services.ask import render_answer

            print("---\n")
            print(render_answer(conv.first_result), end="")
        return 1

    follow_ups = list(args.follow_ups)
    if follow_ups:
        for q in follow_ups:
            _emit(conv.ask(q))
        return 0

    # Interactive REPL.
    print("（多轮对话已就绪。输入追问后回车；空行 / exit / quit 退出。）\n")
    while True:
        try:
            line = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not line or line.lower() in {"exit", "quit", ":q"}:
            break
        print()
        _emit(conv.ask(line))
    return 0


def add_agent_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "agent",
        help="Agent loop（真·每轮自主调工具）：LLM 自己决定调哪个只读检索工具(盘面快照/图谱/证据库/wiki语义/题材模块)、"
        "用什么关键词、要不要再补一刀，直到证据足够再作答（带 [编号] 引用、不编造）。"
        "需 LLM key；无 key/失败优雅降级。默认与现有 ask/chat 互不影响。",
    )
    parser.add_argument("query", help="问题 / 题材词，如 液冷")
    add_shared_retrieval_arguments(parser, with_module_fanout=False)
    parser.add_argument(
        "--market-db-path", default=None,
        help="本地 market_feature_store DuckDB 路径；提供且可打开时启用 opt-in 实时盘面工具 search_market_live（默认关闭，不影响其余工具）",
    )
    parser.add_argument("--max-steps", type=int, default=6, help="Max agent tool-calling rounds before a forced final answer")
    parser.add_argument("--llm-model", default=None, help="Override LLM model id (else provider default / LLM_MODEL)")
    parser.add_argument("--llm-timeout", type=int, default=90, help="Per LLM round-trip HTTP timeout in seconds")
    parser.add_argument("--show-trace", action="store_true", help="Print the tool-call trace (which tools the agent chose, with args)")
    parser.add_argument(
        "-f", "--follow-up", dest="follow_ups", action="append", default=[],
        help="追问（可重复）。提供后走非交互：首轮+依次跑完所有追问即退出。"
        "不提供则进入交互 REPL（输入追问，空行 / exit / quit 退出）。",
    )
    parser.set_defaults(func=cmd_agent)


def cmd_agent(args: argparse.Namespace) -> int:
    from intelligence.runtime.agent import AgentSession
    from intelligence.services.ask import AskOptions

    rag_mode, kb_index_dir, kb_err = _resolve_kb_mode(args.query, args.kb_mode, args.wiki_rag_mode)
    if kb_err:
        print(kb_err, file=sys.stderr)
        return 2
    options = AskOptions(
        query=args.query,
        date=args.date,
        exports_dir=args.exports_dir,
        kb_wiki=args.kb_wiki,
        market_db_path=args.market_db_path,
        top_companies=args.top_companies,
        module_timeout=args.module_timeout,
        wiki_rag_k=args.wiki_rag_k,
        wiki_rag_mode=rag_mode,
        wiki_rag_timeout=args.wiki_rag_timeout,
        wiki_rag_index_dir=kb_index_dir,
        compose=True,
    )

    # 单个持久会话：跨轮记忆 + 累积引用注册表；每轮仍由 LLM 自主决定调哪些工具。
    session = AgentSession(
        options,
        model_override=args.llm_model,
        timeout=args.llm_timeout,
        max_steps=args.max_steps,
    )
    state = {"seen": 0, "turn": 0}

    def _emit(question: str, res) -> int:
        state["turn"] += 1
        print(f"## 你\n{question}\n")
        if args.show_trace or not res.ok:
            if res.steps:
                print("### 工具调用轨迹")
                for i, st in enumerate(res.steps, 1):
                    print(f"{i}. `{st.tool}`({_fmt_args(st.args)}) → {st.result_preview.splitlines()[0] if st.result_preview else ''}")
                print()
            elif state["turn"] > 1:
                print("> （本轮未调工具，直接基于上文已抓到的证据作答）\n")
            else:
                print("> （本轮未调用任何工具）\n")
        who = f"助手·agent·{res.provider}" if res.provider else "助手·agent"
        if res.ok:
            print(f"## {who}\n{res.answer}\n")
            new = res.citations[state["seen"]:]
            state["seen"] = len(res.citations)
            if new:
                print("### 引用来源" if state["turn"] == 1 else "### 引用来源（本轮新增）")
                for c in new:
                    print(f"- [{c.tag}] {c.source}" + (f"（{c.detail}）" if c.detail else ""))
                print()
            return 0
        print(f"## {who}\n（无回答）\n")
        print(f"> ⚠ {res.reason}\n")
        return 1

    print(f"# agent：{args.query}\n")
    rc = _emit(args.query, session.start(args.query))
    if rc != 0:
        # turn-1 degraded (no key / failure) — don't drop into an unusable REPL.
        return rc
    follow_ups = list(args.follow_ups)
    if follow_ups:
        for q in follow_ups:
            print("---\n")
            _emit(q, session.ask(q))
        return 0
    print("（agent 多轮已就绪：带记忆连续对话，每轮仍自主决定要不要再调工具补查。输入追问；空行 / exit / quit 退出。）\n")
    while True:
        try:
            line = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not line or line.lower() in {"exit", "quit", ":q"}:
            break
        print()
        print("---\n")
        _emit(line, session.ask(line))
    return 0


def _fmt_args(args: dict) -> str:
    return ", ".join(f"{k}={v!r}" for k, v in args.items())


_DEFAULT_AGENT_CASES = Path(__file__).resolve().parent / "eval" / "cases" / "agent_cases.json"


def add_agent_eval_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "agent-eval",
        help="Agent 评测闸：对 golden 用例集跑 agent → 确定性评分（引用可解析/免责声明/实体召回/选源/W指标）→ "
        "记分卡 + 退出码（0 过 / 1 不过 / 2 降级）。可当回归闸：--save-run 存基线，--from-run 离线重评不耗 LLM。",
    )
    parser.add_argument("--cases", default=str(_DEFAULT_AGENT_CASES), help="Golden 用例集 JSON（默认内置 agent_cases.json）")
    parser.add_argument("--case-id", action="append", default=[], help="只跑指定 case id（可重复）；默认全跑")
    parser.add_argument("--date", default=None, help="覆盖所有 case 的盘面快照日期 YYYY-MM-DD")
    parser.add_argument("--kb-wiki", default=None, help="Knowledge-base wiki root；默认 env/auto")
    parser.add_argument("--exports-dir", default=None, help="覆盖 market_feature_store/exports 目录")
    parser.add_argument("--top-companies", type=int, default=12)
    parser.add_argument("--module-timeout", type=int, default=180)
    parser.add_argument("--wiki-rag-k", type=int, default=6)
    parser.add_argument("--wiki-rag-mode", default="hybrid", choices=["bm25", "dense", "hybrid"])
    parser.add_argument("--wiki-rag-timeout", type=int, default=90)
    parser.add_argument("--max-steps", type=int, default=6)
    parser.add_argument("--llm-model", default=None)
    parser.add_argument("--llm-timeout", type=int, default=90)
    parser.add_argument("--gate", type=float, default=None, help="覆盖聚合通过率闸值（默认取用例集 aggregate_gate）")
    parser.add_argument("--json", action="store_true", help="输出机读记分卡 JSON（否则 markdown）")
    parser.add_argument("--save-run", default=None, help="把本次 live 跑的原始输入存成 JSON（之后可 --from-run 离线重评）")
    parser.add_argument("--from-run", default=None, help="从已存 run JSON 离线重评，不调用 LLM/KB（确定性回归）")
    parser.add_argument("--skip-grounding-check", action="store_true", help="跳过 live 跑前的用例接地预检（默认会先核对 expect/forbid 实体是否对齐知识库）")
    parser.set_defaults(func=cmd_agent_eval)


def add_answer_score_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "answer-score",
        help="金融回答质量评分：按垂直行业 rubric 评价本地数据优先、证据分层、盘面阶段、反方审稿等。",
    )
    parser.add_argument("--question", required=True, help="原始问题，例如：瑞华泰还有上涨空间吗")
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--answer", default=None, help="直接传入回答文本")
    src.add_argument("--answer-file", default=None, help="从文件读取回答文本")
    parser.add_argument(
        "--local-source",
        action="append",
        default=[],
        help="本轮应优先使用的本地来源标识，可重复，例如 knowledge-base-private / market_feature_store",
    )
    parser.add_argument(
        "--question-type",
        default="auto",
        help="题型（与 answer_orchestrator 对齐，如 market_forecast）；"
        "auto=按问题自动分类，none=只跑通用 7 维。market_forecast 会追加复盘专用维度组。",
    )
    parser.add_argument("--json", action="store_true", help="输出机器可读 JSON（默认 markdown 记分卡）")
    parser.add_argument("--user", default=None, help="用户 id；保存经验卡片时使用（默认 default 或 FORESIGHT_USER）")
    parser.add_argument("--save-card", action="store_true", help="把本次评分同时沉淀为 users/<user>/experience_cards.jsonl")
    parser.add_argument("--card-file", default=None, help="覆盖经验卡片保存路径")
    parser.add_argument("--corrected-principle", default=None, help="从本次扣分抽象出的可复用原则")
    parser.add_argument("--prompt-rule", default=None, help="下次回答同类问题时应注入的提示规则")
    parser.add_argument("--applies-to", action="append", default=[], help="适用问题类型/场景，可重复")
    parser.add_argument("--user-feedback", default=None, help="用户对本次回答的反馈摘要")
    parser.add_argument(
        "--promotion",
        default="candidate",
        choices=["candidate", "promoted", "methodology"],
        help="经验卡片状态",
    )
    parser.set_defaults(func=cmd_answer_score)


def add_route_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "route",
        help="问题分诊：先判断走固定 workflow、Planner 组合分析、补数据，还是需要追问；只输出计划，不直接回答。",
    )
    parser.add_argument("query", help="用户问题，例如：玻璃基板今天为什么动，是旧逻辑唤醒吗")
    parser.add_argument("--json", action="store_true", help="输出机器可读 JSON")
    parser.add_argument("--summary-json", default=None, help="写出 workflow summary JSON")
    parser.set_defaults(func=cmd_route)


def add_orchestrate_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "orchestrate",
        help="薄编排层：先分诊，再渲染 workflow 命令；默认只预览，--execute 仅执行 low-risk auto path。",
    )
    parser.add_argument("query", help="用户问题，例如：今天该看什么")
    parser.add_argument("--date", default=None, help="交易日 YYYY-MM-DD")
    parser.add_argument("--kb-wiki", default=None, help="知识库 wiki 根目录；默认走 env/auto")
    parser.add_argument("--finance-root", default=None, help="覆盖金融仓路径")
    parser.add_argument("--recent", type=int, default=5, help="批量路径 recent 参数")
    parser.add_argument("--top-per-date", type=int, default=10, help="批量路径 top_per_date 参数")
    parser.add_argument("--execute", action="store_true", help="执行允许自动执行的 low-risk path；默认只预览")
    parser.add_argument("--json", action="store_true", help="输出机器可读 JSON")
    parser.add_argument("--summary-json", default=None, help="写出 workflow summary JSON")
    parser.set_defaults(func=cmd_orchestrate)


def add_logic_match_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "logic-match",
        help="逻辑-盘面匹配：把 theme-candidates 与知识库 concept/entity/evidence 对齐，输出旧逻辑唤醒/新逻辑/噪音/数据缺口。",
    )
    parser.add_argument("query", help="题材/概念/关键词，例如 液冷服务器")
    parser.add_argument("--date", default=None, help="theme-candidates 日期 YYYY-MM-DD；为空则使用最新导出")
    parser.add_argument("--exports-dir", default=None, help="覆盖 market_feature_store/exports 目录")
    parser.add_argument("--kb-wiki", default=None, help="知识库 wiki 根目录；默认走 env/auto")
    parser.add_argument("--top-companies", type=int, default=12, help="最多返回公司暴露/强势股数量")
    parser.add_argument("--max-evidence", type=int, default=8, help="最多返回 evidence 条数")
    parser.add_argument("--out-json", default=None, help="写出匹配结果 JSON")
    parser.add_argument("--out-md", default=None, help="写出匹配结果 Markdown")
    parser.add_argument("--json", action="store_true", help="输出机器可读 JSON")
    parser.add_argument("--summary-json", default=None, help="写出 workflow summary JSON")
    parser.set_defaults(func=cmd_logic_match)


def add_logic_match_batch_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "logic-match-batch",
        help="批量逻辑-盘面匹配：扫描最近/指定 theme-candidates，生成高优先级补数据队列。",
    )
    parser.add_argument("--dates", default=None, help="逗号分隔日期列表；为空则使用最近 N 个 theme-candidates")
    parser.add_argument("--recent", type=int, default=5, help="未指定 --dates 时扫描最近 N 个日期")
    parser.add_argument("--top-per-date", type=int, default=10, help="每个日期扫描 priority_score 最高的 N 个候选")
    parser.add_argument("--exports-dir", default=None, help="覆盖 market_feature_store/exports 目录")
    parser.add_argument("--kb-wiki", default=None, help="知识库 wiki 根目录；默认走 env/auto")
    parser.add_argument("--top-companies", type=int, default=8, help="每个候选最多返回公司暴露/强势股数量")
    parser.add_argument("--max-evidence", type=int, default=5, help="每个候选最多返回 evidence 条数")
    parser.add_argument("--out-json", default=None, help="写出批量结果 JSON")
    parser.add_argument("--out-md", default=None, help="写出批量结果 Markdown")
    parser.add_argument("--json", action="store_true", help="输出机器可读 JSON")
    parser.add_argument("--summary-json", default=None, help="写出 workflow summary JSON")
    parser.set_defaults(func=cmd_logic_match_batch)


def add_effectiveness_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "effectiveness",
        help="P4 历史有效性：为某题材从 theme-candidates 历史算成绩单（胜率/半衰期/回撤/扩散/相对强度/叙事-事实偏离/CAR）。",
    )
    parser.add_argument("theme", help="题材/概念名，例如 光刻胶")
    parser.add_argument("--date", required=True, help="截至交易日 YYYY-MM-DD")
    parser.add_argument("--window", type=int, default=20, help="回看的 theme-candidates 交易日数")
    parser.add_argument("--top-per-date", type=int, default=10, help="每个日期扫描 priority_score 最高的 N 个候选")
    parser.add_argument("--exports-dir", default=None, help="覆盖 market_feature_store/exports 目录")
    parser.add_argument("--market-snapshot-dir", default=None, help="覆盖 market_snapshot 目录（用于 CAR；默认走 env/auto）")
    parser.add_argument("--min-samples", type=int, default=3, help="低于该观察天数判为样本不足")
    parser.add_argument("--json", action="store_true", help="输出机器可读 JSON")
    parser.set_defaults(func=cmd_effectiveness)


def cmd_effectiveness(args: argparse.Namespace) -> int:
    import json as _json

    from intelligence.paths import default_paths
    from intelligence.services import logic_effectiveness
    from intelligence.services.logic_market_match import available_candidate_dates

    paths = default_paths()
    exports_dir = Path(args.exports_dir).expanduser() if args.exports_dir else paths.market_exports
    snapshot_dir = Path(args.market_snapshot_dir).expanduser() if args.market_snapshot_dir else paths.market_snapshot_dir
    dates = [item for item in available_candidate_dates(exports_dir) if item <= args.date][-args.window:]
    history = logic_effectiveness.load_effectiveness_history(
        exports_dir, dates, args.date, top_per_date=args.top_per_date
    )
    panel = logic_effectiveness.load_market_return_panel(snapshot_dir, dates)
    scorecard = logic_effectiveness.build_effectiveness_scorecard(
        args.theme,
        history.get(args.theme, []),
        return_panel=panel,
        min_samples=args.min_samples,
    )
    print(_json.dumps(scorecard, ensure_ascii=False, indent=2))
    return 0


def add_daily_agent_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "agent-daily",
        help="每日研究入口：写出 canonical 研究队列；完整 daily-agent 日报仅在 fidelity 1.2 通过时落盘。",
    )
    parser.add_argument("--date", required=True, help="交易日 YYYY-MM-DD")
    parser.add_argument("--finance-root", default=None, help="覆盖金融仓路径")
    parser.add_argument("--kb-wiki", default=None, help="知识库 wiki 根目录；默认走 env/auto")
    parser.add_argument("--recent", type=int, default=1, help="扫描截至该日期的最近 N 个 theme-candidates；默认只扫当日")
    parser.add_argument("--top-per-date", type=int, default=10, help="每个日期扫描 priority_score 最高的 N 个候选")
    parser.add_argument("--top-companies", type=int, default=8, help="每个候选最多返回公司暴露/强势股数量")
    parser.add_argument("--max-evidence", type=int, default=5, help="每个候选最多返回 evidence 条数")
    parser.add_argument("--semantic-rag-top-n", type=int, default=3, help="对优先级最高的 N 个候选补 wiki 语义召回；0=关闭")
    parser.add_argument("--wiki-rag-k", type=int, default=3, help="每个候选最多补充 N 个 W 命中")
    parser.add_argument("--wiki-rag-mode", default="hybrid", choices=["bm25", "dense", "hybrid"], help="agent 日报语义召回模式")
    parser.add_argument("--wiki-rag-timeout", type=int, default=120, help="单次 W 召回超时时间")
    parser.add_argument("--effectiveness-window", type=int, default=20, help="历史有效性评估回看的 theme-candidates 交易日数")
    parser.add_argument("--catalyst-window-days", type=int, default=5, help="催化归因回看的自然日数（卖方观点/晨汇）")
    parser.add_argument("--out-json", default=None, help="写出完整 agent 日报 JSON（best-effort；研究队列写在其 sibling）")
    parser.add_argument("--out-md", default=None, help="写出完整 agent 日报 Markdown（best-effort）")
    parser.add_argument("--out-html", default=None, help="写出完整 agent 日报 HTML（best-effort；工作台优先读研究队列 HTML）")
    parser.add_argument("--json", action="store_true", help="输出机器可读 JSON；否则输出 Markdown")
    parser.add_argument("--summary-json", default=None, help="写出 workflow summary JSON")
    parser.set_defaults(func=cmd_daily_agent)


def cmd_route(args: argparse.Namespace) -> int:
    import json as _json

    from intelligence.workflows.route import RouteWorkflowOptions, run_route

    summary, decision, answer = run_route(RouteWorkflowOptions(query=args.query))
    if args.summary_json:
        summary.write_json(args.summary_json)
    if args.json:
        print(_json.dumps(decision.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(answer, end="")
    return 0 if summary.status in {"PASS", "WARN", "SKIP"} else 1


def cmd_orchestrate(args: argparse.Namespace) -> int:
    import json as _json

    from intelligence.workflows.agent_orchestrator import OrchestratorOptions, run_agent_orchestrator

    summary, result, answer = run_agent_orchestrator(
        OrchestratorOptions(
            query=args.query,
            date=args.date,
            knowledge_wiki=args.kb_wiki,
            finance_root=args.finance_root,
            recent=args.recent,
            top_per_date=args.top_per_date,
            execute=args.execute,
        )
    )
    if args.summary_json:
        summary.write_json(args.summary_json)
    if args.json:
        print(_json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(answer, end="")
    return 0 if summary.status in {"PASS", "WARN", "SKIP"} else 1


def cmd_logic_match(args: argparse.Namespace) -> int:
    import json as _json

    from intelligence.workflows.logic_match import LogicMatchOptions, run_logic_match

    summary, result, answer = run_logic_match(
        LogicMatchOptions(
            query=args.query,
            date=args.date,
            exports_dir=args.exports_dir,
            kb_wiki=args.kb_wiki,
            top_companies=args.top_companies,
            max_evidence=args.max_evidence,
        )
    )
    if args.summary_json:
        summary.write_json(args.summary_json)
    if args.out_json:
        Path(args.out_json).expanduser().parent.mkdir(parents=True, exist_ok=True)
        Path(args.out_json).expanduser().write_text(result.to_json() + "\n", encoding="utf-8")
    if args.out_md:
        Path(args.out_md).expanduser().parent.mkdir(parents=True, exist_ok=True)
        Path(args.out_md).expanduser().write_text(answer, encoding="utf-8")
    if args.json:
        print(_json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(answer, end="")
    return 0 if summary.status in {"PASS", "WARN", "SKIP"} else 1


def cmd_logic_match_batch(args: argparse.Namespace) -> int:
    import json as _json

    from intelligence.workflows.logic_match import LogicMatchBatchOptions, run_logic_match_batch

    dates = tuple(item.strip() for item in args.dates.split(",") if item.strip()) if args.dates else ()
    summary, result, answer = run_logic_match_batch(
        LogicMatchBatchOptions(
            dates=dates,
            recent=args.recent,
            top_per_date=args.top_per_date,
            exports_dir=args.exports_dir,
            kb_wiki=args.kb_wiki,
            top_companies=args.top_companies,
            max_evidence=args.max_evidence,
        )
    )
    if args.summary_json:
        summary.write_json(args.summary_json)
    if args.out_json:
        Path(args.out_json).expanduser().parent.mkdir(parents=True, exist_ok=True)
        Path(args.out_json).expanduser().write_text(result.to_json() + "\n", encoding="utf-8")
    if args.out_md:
        Path(args.out_md).expanduser().parent.mkdir(parents=True, exist_ok=True)
        Path(args.out_md).expanduser().write_text(answer, encoding="utf-8")
    if args.json:
        print(_json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(answer, end="")
    return 0 if summary.status in {"PASS", "WARN", "SKIP"} else 1


def cmd_daily_agent(args: argparse.Namespace) -> int:
    import json as _json

    from intelligence.paths import default_paths
    from intelligence.services.research_queue import sibling_queue_path
    from intelligence.workflows.daily_agent import DailyAgentOptions, run_daily_agent, write_daily_agent_outputs

    summary, report, answer = run_daily_agent(
        DailyAgentOptions(
            date=args.date,
            finance_root=args.finance_root,
            kb_wiki=args.kb_wiki,
            recent=args.recent,
            top_per_date=args.top_per_date,
            top_companies=args.top_companies,
            max_evidence=args.max_evidence,
            semantic_rag_top_n=args.semantic_rag_top_n,
            wiki_rag_k=args.wiki_rag_k,
            wiki_rag_mode=args.wiki_rag_mode,
            wiki_rag_timeout=args.wiki_rag_timeout,
            effectiveness_window=args.effectiveness_window,
            catalyst_window_days=args.catalyst_window_days,
        )
    )
    paths = default_paths()
    finance_root = Path(args.finance_root).expanduser() if args.finance_root else paths.finance_root
    out_json = Path(args.out_json).expanduser() if args.out_json else finance_root / "market_feature_store" / "exports" / f"{args.date}-daily-agent.json"
    out_md = Path(args.out_md).expanduser() if args.out_md else finance_root / "market_feature_store" / "exports" / f"{args.date}-daily-agent.md"
    out_html = Path(args.out_html).expanduser() if args.out_html else finance_root / "复盘" / "daily" / args.date / f"{args.date}-daily-agent.html"
    queue_json = sibling_queue_path(out_json)
    queue_md = sibling_queue_path(out_md)
    queue_html = sibling_queue_path(out_html)
    kb_queue_path = out_json.with_name(f"{args.date}-kb-ingest-queue.json")
    full_written = True
    try:
        write_daily_agent_outputs(report, answer, out_json, out_md, out_html)
    except ValueError as exc:
        if not str(exc).startswith("invalid fidelity contract"):
            raise
        full_written = False
        summary.warnings.append(str(exc))
        print(f"WARN 完整 daily-agent 未落盘：{exc}", file=sys.stderr)
        print(f"研究队列已落盘：{queue_json}", file=sys.stderr)
    summary.outputs.extend([str(queue_json), str(queue_md), str(queue_html), str(kb_queue_path)])
    if full_written:
        summary.outputs.extend([str(out_json), str(out_md), str(out_html)])
    if args.summary_json:
        summary.write_json(args.summary_json)
    if args.json:
        print(_json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(answer, end="")
        print(f"\n输出: {queue_md}\n输出: {queue_json}\n输出: {queue_html}")
        print(f"输出: {kb_queue_path}")
        if full_written:
            print(f"输出: {out_md}\n输出: {out_json}\n输出: {out_html}")
        else:
            print("完整 daily-agent 因 fidelity 1.2 未落盘；研究队列已作为 canonical 产物写出。")
    return 0 if summary.status in {"PASS", "WARN", "SKIP"} else 1


def cmd_agent_eval(args: argparse.Namespace) -> int:
    import json

    from intelligence.eval import runner as R

    specs, gate = R.load_cases(args.cases)
    if args.case_id:
        wanted = set(args.case_id)
        specs = [s for s in specs if s.id in wanted]
        if not specs:
            print(f"没有匹配的 case id：{sorted(wanted)}", file=sys.stderr)
            return 2
    if args.gate is not None:
        gate = args.gate

    if args.from_run:
        run_record = json.loads(Path(args.from_run).read_text(encoding="utf-8"))
        card = R.score_run(run_record, specs, gate)
        degraded = False
    else:
        if not args.skip_grounding_check:
            from scripts.validate_agent_cases_grounding import (
                grounding_report_for_kb,
                render_markdown as render_grounding,
                resolve_kb_wiki,
            )

            kb_wiki = resolve_kb_wiki(args.kb_wiki)
            grounding = grounding_report_for_kb(specs, kb_wiki)
            if grounding is None:
                print("⚠ 跳过用例接地预检：未找到知识库 relations（entity_exposures/concept_graph）。", file=sys.stderr)
            elif not grounding["passed"]:
                print(render_grounding(grounding), file=sys.stderr)
                print(
                    f"\n⚠ 用例接地预检不通过：{grounding['failed_ids']} 的 expect/forbid 实体未对齐知识库。"
                    "先修用例或加 --skip-grounding-check 跳过；未消耗 LLM。",
                    file=sys.stderr,
                )
                return 2
        if args.date:
            for s in specs:
                s.date = args.date
        opts = R.EvalRunOptions(
            kb_wiki=args.kb_wiki,
            exports_dir=args.exports_dir,
            top_companies=args.top_companies,
            module_timeout=args.module_timeout,
            wiki_rag_k=args.wiki_rag_k,
            wiki_rag_mode=args.wiki_rag_mode,
            wiki_rag_timeout=args.wiki_rag_timeout,
            max_steps=args.max_steps,
            llm_model=args.llm_model,
            llm_timeout=args.llm_timeout,
        )
        card, run_record = R.run_eval(specs, gate, opts)
        if args.save_run:
            Path(args.save_run).write_text(
                json.dumps(run_record, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        # 全部首轮未作答 = 环境降级（多半无 LLM key），既非「过」也非真实「不过」。
        degraded = bool(card.cases) and all(
            c.turns and not c.turns[0].answered for c in card.cases
        )

    if args.json:
        print(json.dumps(card.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(R.format_scorecard(card))

    if degraded:
        print(
            "\n⚠ 全部 case 首轮未作答：多半是无 LLM key / 检索环境未就绪，agent 走了优雅降级。"
            "这不是评分意义上的「不过」——请设好 DEEPSEEK_API_KEY 并接好 W 源后重跑。",
            file=sys.stderr,
        )
        return 2
    return 0 if card.passed else 1


def cmd_answer_score(args: argparse.Namespace) -> int:
    import json

    from intelligence.eval import finance_answer_rubric as rubric
    from intelligence.services.answer_orchestrator import plan_answer_question

    if args.answer_file:
        answer = Path(args.answer_file).expanduser().read_text(encoding="utf-8")
    else:
        answer = args.answer or ""
    question_type = args.question_type
    if question_type == "auto":
        question_type = plan_answer_question(args.question).question_type
    elif question_type == "none":
        question_type = None
    scored = rubric.score_answer(
        args.question,
        answer,
        local_sources=list(args.local_source or []),
        question_type=question_type,
    )
    card_path: Path | None = None
    card: dict | None = None
    if args.save_card:
        from intelligence import userspace
        from intelligence.services import experience_cards

        us = userspace.user_space(args.user)
        card_path = Path(args.card_file).expanduser() if args.card_file else us.experience_cards_path
        card = experience_cards.build_card_from_score(
            scored,
            answer=answer,
            corrected_principle=args.corrected_principle,
            applies_to=list(args.applies_to or []),
            prompt_rule=args.prompt_rule,
            user_feedback=args.user_feedback,
            local_sources=list(args.local_source or []),
            promotion=args.promotion,
        )
        experience_cards.record_card(card_path, card)
    if args.json:
        payload = scored.to_dict()
        if card_path is not None and card is not None:
            payload["experience_card_path"] = str(card_path)
            payload["experience_card"] = card
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(rubric.format_score(scored))
        if card_path is not None:
            print(f"\n经验卡片已保存 → {card_path}")
    return 0


def add_foresight_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "foresight",
        help="猜你想问 / 潜意识：基于盘面现实+用户画像，主动生成「你还没想到但该问」的追问",
    )
    parser.add_argument("--user", default=None, help="用户 id（应用态命名空间 intelligence/users/<id>/；默认 default 或环境变量 FORESIGHT_USER）")
    parser.add_argument("--profile", default=None, help="显式画像 JSON 单文件（覆盖用户命名空间；默认走 users/<user>/ 合并）")
    parser.add_argument("--news-file", default=None, help="可选实时情报文件（今日财经日历/新闻），无则跳过实时层")
    parser.add_argument("--date", default=None, help="theme-candidates 盘面快照日期 YYYY-MM-DD；默认取最新")
    parser.add_argument("--exports-dir", default=None, help="覆盖 market_feature_store/exports 目录")
    parser.add_argument("--kb-wiki", default=None, help="知识库 wiki 根（含 relations/）；默认读 env KNOWLEDGE_WIKI/auto，把 theme_signals 题材当发问素材")
    parser.add_argument("--no-kb", dest="use_kb", action="store_false", help="不调知识库题材当发问素材（默认开启）")
    parser.add_argument("--kb-themes", type=int, default=6, help="从知识库取认知最靠前的前 N 个题材当发问素材（默认 6）")
    parser.set_defaults(use_kb=True)
    parser.add_argument("-n", "--num", type=int, default=3, help="最终展示问题数（默认 3）")
    parser.add_argument("--candidates", type=int, default=8, help="让 LLM 先生成的候选数（默认 8，再排序取前 N）")
    parser.add_argument(
        "--llm-model",
        default=None,
        help="覆盖 LLM 模型 id（需 DEEPSEEK_API_KEY/MOONSHOT_API_KEY/DASHSCOPE_API_KEY/"
        "ZHIPU_API_KEY/OPENAI_API_KEY 或 LLM_API_KEY；无 key 自动降级为摘要+提示词预览）",
    )
    parser.add_argument("--llm-timeout", type=int, default=60, help="LLM HTTP 超时秒数")
    parser.add_argument("--temperature", type=float, default=0.8, help="生成温度，越高越发散（默认 0.8）")
    parser.add_argument("--memory-file", default=None, help="问过的问题记忆 jsonl（默认 intelligence/foresight_memory.jsonl，已 gitignore）")
    parser.add_argument("--no-memory", dest="use_memory", action="store_false", help="不读/不写记忆回路（默认开启）")
    parser.add_argument("--memory-window", type=int, default=50, help="只用最近 N 条历史提问去重（默认 50）")
    parser.set_defaults(use_memory=True)
    parser.add_argument("--interactions-file", default=None, help="用户反馈记录 jsonl（默认 users/<user>/interactions.jsonl，已 gitignore）")
    parser.add_argument("--no-interactions", dest="use_interactions", action="store_false", help="不读反馈回路、排序不加亲和加成（默认开启）")
    parser.add_argument("--interactions-window", type=int, default=200, help="只聚合最近 N 条反馈算亲和度（默认 200）")
    parser.add_argument("--affinity-half-life", type=float, default=14.0, help="反馈时间衰减半衰期（天，默认 14）")
    parser.add_argument("--affinity-boost", type=float, default=0.2, help="反馈加成上限权重（默认 0.2；0 关闭加成）")
    parser.set_defaults(use_interactions=True)
    parser.add_argument("--methodology-file", default=None, help="复盘认知框架/方法论文件（默认 intelligence/foresight_methodology.md，注入「思考宪法」）")
    parser.add_argument("--no-methodology", dest="use_methodology", action="store_false", help="不注入复盘认知框架（默认注入）")
    parser.set_defaults(use_methodology=True)
    parser.add_argument("--corrections-file", default=None, help="纠偏记录 jsonl（默认 users/<user>/corrections.jsonl，已 gitignore）")
    parser.add_argument("--no-corrections", dest="use_corrections", action="store_false", help="不注入纠偏记录（默认注入）")
    parser.add_argument("--corrections-window", type=int, default=20, help="只注入最近 N 条纠偏（默认 20）")
    parser.set_defaults(use_corrections=True)
    parser.add_argument("--judgments-file", default=None, help="核心判断台账 jsonl（默认 users/<user>/judgments.jsonl，已 gitignore）")
    parser.add_argument("--no-judgments", dest="use_judgments", action="store_false", help="不注入近期核心判断（默认注入）")
    parser.add_argument("--judgments-window", type=int, default=10, help="只注入最近 N 条核心判断（默认 10）")
    parser.set_defaults(use_judgments=True)
    parser.add_argument("--checkpoints-file", default=None, help="可证伪点台账 jsonl（默认 users/<user>/checkpoints.jsonl，已 gitignore）")
    parser.add_argument("--verdicts-file", default=None, help="回检打分台账 jsonl（默认 users/<user>/verdicts.jsonl，已 gitignore）")
    parser.add_argument("--no-calibration", dest="use_calibration", action="store_false", help="不注入二阶推演校准（默认注入）")
    parser.add_argument("--calibration-min-n", type=int, default=2, help="某类二阶推演至少回检 N 条才注入校准（默认 2）")
    parser.set_defaults(use_calibration=True)
    parser.add_argument("--json", action="store_true", help="输出机器可读 JSON 而非 Markdown")
    parser.add_argument("--summary-json", default=None, help="写出 workflow summary JSON")
    parser.set_defaults(func=cmd_foresight)


def add_prime_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "prime",
        help="检索前置：每轮回答前必跑——问题→自动查 checkpoint 校准+个人库（画像/亲和/纠偏/判断）+图谱→拼上下文前缀（只读、可离线）",
    )
    parser.add_argument("query", help="本轮用户问题 / 题材词，如 液冷服务器")
    parser.add_argument("--user", default=None, help="用户 id（默认 default 或环境变量 FORESIGHT_USER）")
    parser.add_argument("--kb-wiki", default=None, help="知识库 wiki 根目录（含 relations/）；默认 env/auto")
    parser.add_argument("--top-concepts", type=int, default=5, help="图谱概念命中上限（默认5）")
    parser.add_argument("--top-companies", type=int, default=8, help="公司暴露召回上限（默认8）")
    parser.add_argument("--max-evidence", type=int, default=6, help="证据条数上限（默认6）")
    parser.add_argument("--affinity-top", type=int, default=8, help="反馈亲和条数上限（默认8，问题相关的优先）")
    parser.add_argument("--corrections-window", type=int, default=5, help="注入最近几条纠偏（默认5）")
    parser.add_argument("--judgments-window", type=int, default=5, help="注入最近几条核心判断（默认5）")
    parser.add_argument("--calibration-min-n", type=int, default=2, help="校准类别最小样本数（默认2）")
    parser.add_argument("--wiki-rag", action="store_true", help="附带 W（wiki 向量语义召回，较慢；失败只降级）")
    parser.add_argument("--wiki-rag-k", type=int, default=4, help="W 召回条数（默认4）")
    parser.add_argument("--wiki-rag-timeout", type=int, default=30, help="W 超时秒数（默认30）")
    parser.add_argument("--json", action="store_true", help="输出机器可读 JSON（含 prefix 字段）")
    parser.set_defaults(func=cmd_prime)


def cmd_prime(args: argparse.Namespace) -> int:
    import json as _json

    from intelligence.services.prime import (
        PrimeOptions,
        build_prime,
        render_prefix,
        result_to_dict,
    )

    result = build_prime(
        PrimeOptions(
            query=args.query,
            user=args.user,
            kb_wiki=args.kb_wiki,
            top_concepts=args.top_concepts,
            top_companies=args.top_companies,
            max_evidence=args.max_evidence,
            affinity_top=args.affinity_top,
            corrections_window=args.corrections_window,
            judgments_window=args.judgments_window,
            calibration_min_n=args.calibration_min_n,
            use_wiki_rag=args.wiki_rag,
            wiki_rag_k=args.wiki_rag_k,
            wiki_rag_timeout=args.wiki_rag_timeout,
        )
    )
    if args.json:
        print(_json.dumps(result_to_dict(result), ensure_ascii=False, indent=2))
    else:
        print(render_prefix(result))
    return 0


def add_record_interaction_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "record-interaction",
        help="反馈回路：记一条对「猜你想问」的反馈（点开/追问/喜欢/忽略/打分）→ 越用越懂",
    )
    parser.add_argument("--user", default=None, help="用户 id（默认 default 或环境变量 FORESIGHT_USER）")
    parser.add_argument(
        "--kind",
        required=True,
        help="反馈类型：click/open/ask/like/follow/pin/view/skip/ignore/dismiss/mute/dislike/rate",
    )
    parser.add_argument("--question", default=None, help="被反馈的问题原文（可选，仅留痕）")
    parser.add_argument("--theme", dest="themes", action="append", default=[], help="关联题材（可多次）")
    parser.add_argument("--stock", dest="stocks", action="append", default=[], help="关联个股（可多次）")
    parser.add_argument("--weight", type=float, default=None, help="显式权重（覆盖 kind 默认；正升负降）")
    parser.add_argument("--rating", type=float, default=None, help="1~5 星评分（kind=rate 时用，映射到 [-1,1]）")
    parser.add_argument("--note", default=None, help="备注（可选）")
    parser.add_argument("--interactions-file", default=None, help="覆盖反馈记录文件路径")
    parser.add_argument("--json", action="store_true", help="输出机器可读 JSON")
    parser.add_argument("--summary-json", default=None, help="写出 workflow summary JSON")
    parser.set_defaults(func=cmd_record_interaction)


def add_record_correction_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "record-correction",
        help="纠偏回路：记一条你对 foresight 回答的纠正（原话/纠成什么/抽象原则）→ 注入发问「别再犯」",
    )
    parser.add_argument("--user", default=None, help="用户 id（默认 default 或环境变量 FORESIGHT_USER）")
    parser.add_argument("--correction", required=True, help="你把它纠正成什么（必填）")
    parser.add_argument("--original", default=None, help="它原来的说法 / 答错的点（可选）")
    parser.add_argument("--principle", default=None, help="从这次纠正抽象出的、可复用的原则（可选，最该被记住）")
    parser.add_argument("--theme", dest="themes", action="append", default=[], help="关联题材（可多次）")
    parser.add_argument("--corrections-file", default=None, help="覆盖纠偏记录文件路径")
    parser.add_argument("--json", action="store_true", help="输出机器可读 JSON")
    parser.set_defaults(func=cmd_record_correction)


def add_memory_status_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "memory-status",
        help="记忆退出机制：归档/撤销/恢复一条核心判断或纠偏（追加状态行，不改历史；归档后不再被召回）",
    )
    parser.add_argument("--user", default=None, help="用户 id（默认 default 或环境变量 FORESIGHT_USER）")
    parser.add_argument(
        "--ledger", required=True, choices=("judgments", "corrections"),
        help="目标台账：judgments（核心判断）或 corrections（纠偏）",
    )
    parser.add_argument(
        "--target-ts", required=True,
        help="目标记录的 ts 或 id（原样精确匹配；同秒多条记录时用 id 精确退出其中一条）",
    )
    parser.add_argument(
        "--status", required=True, choices=("archived", "rejected", "reinstated"),
        help="archived=过时归档 / rejected=错记撤销 / reinstated=恢复召回",
    )
    parser.add_argument("--reason", default="", help="归档/撤销理由（留审计链，建议填）")
    parser.add_argument("--ledger-file", default=None, help="覆盖台账文件路径（测试用）")
    parser.add_argument("--json", action="store_true", help="输出机器可读 JSON")
    parser.set_defaults(func=cmd_memory_status)


def cmd_memory_status(args: argparse.Namespace) -> int:
    import json as _json

    from intelligence import userspace
    from intelligence.services import memory_status

    if args.ledger_file:
        path = args.ledger_file
    else:
        us = userspace.user_space(args.user)
        path = us.judgments_path if args.ledger == "judgments" else us.corrections_path
    ledger_path = Path(path).expanduser()
    if not ledger_path.exists():
        print(f"台账不存在：{ledger_path}", file=sys.stderr)
        return 2
    # 目标必须真实存在：状态行指向不存在的 target 只会制造悬空审计链。
    # id/ts 双键：新行认 id（同秒并发不碰撞），旧行仍认 ts。
    target = str(args.target_ts).strip()
    found = False
    for line in ledger_path.read_text(encoding="utf-8").splitlines():
        try:
            rec = _json.loads(line)
        except Exception:
            continue
        if (
            isinstance(rec, dict)
            and not memory_status.is_status_record(rec)
            and target
            in {
                str(rec.get("ts") or "").strip(),
                str(rec.get("id") or "").strip(),
            }
        ):
            found = True
            break
    if not found:
        print(f"目标记录不存在：{target}（ts/id 均未命中；先用台账文件核对）", file=sys.stderr)
        return 2
    _, record = memory_status.record_status(
        ledger_path,
        target_ts=target,
        status=args.status,
        reason=args.reason,
    )
    if args.json:
        print(_json.dumps(record, ensure_ascii=False, indent=2))
    else:
        verb = {"archived": "已归档", "rejected": "已撤销", "reinstated": "已恢复"}[args.status]
        print(f"{verb} {args.ledger} 记录 target={target} → {ledger_path}")
        print("历史行未改动（追加式状态覆盖）；归档/撤销的记录不再进入 [M] 召回与 foresight 注入。")
    return 0


def add_migrate_workbench_store_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "migrate-workbench-store",
        help="存量 run/conversation JSON → workbench.sqlite3 一次性回填（幂等，可重复跑）",
    )
    parser.add_argument("--user", default=None, help="用户 id（默认 default 或环境变量 FORESIGHT_USER）")
    parser.set_defaults(func=cmd_migrate_workbench_store)


def cmd_migrate_workbench_store(args: argparse.Namespace) -> int:
    from intelligence.services.workbench_migrate import migrate_user

    counts = migrate_user(args.user)
    print(json.dumps(counts, ensure_ascii=False))
    return 0


def add_refresh_profile_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "refresh-profile",
        help="第 2 层：从 DuckDB 强势股 + 知识库 theme_signals 自动派生画像候选（不碰飞书）",
    )
    parser.add_argument("--user", default=None, help="用户 id（默认 default 或环境变量 FORESIGHT_USER）")
    parser.add_argument("--lookback", type=int, default=20, help="回看交易日数（预留，当前按最新快照派生）")
    parser.add_argument("--date", default=None, help="盘面快照日期 YYYY-MM-DD；默认取 DuckDB 最新")
    parser.add_argument("--top", type=int, default=12, help="候选 focus_themes / watchlist 各取前 N（默认 12）")
    parser.add_argument("--kb-wiki", default=None, help="知识库 wiki 根（含 relations/）；默认 env/auto")
    parser.add_argument("--db-path", default=None, help="覆盖 DuckDB 路径；默认 market_feature_store 约定路径")
    parser.add_argument("--apply", action="store_true", help="落盘 users/<user>/profile.derived.json（默认仅预览 diff）")
    parser.add_argument("--json", action="store_true", help="输出机器可读 JSON（proposal+diff）而非 Markdown")
    parser.add_argument("--summary-json", default=None, help="写出 workflow summary JSON")
    parser.set_defaults(func=cmd_refresh_profile)


def add_adapter_smoke_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("adapter-smoke", help="Run read-only adapter smoke checks")
    parser.add_argument("--date", default=None, help="Trade date YYYY-MM-DD; defaults to latest available")
    parser.add_argument("--entity", default="ASML", help="Entity name for knowledge adapter checks")
    parser.add_argument("--concept", default=None, help="Optional concept filter for evidence lookup")
    parser.add_argument("--summary-json", default=None, help="Write workflow summary JSON")
    parser.set_defaults(func=cmd_adapter_smoke)


def add_daily_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("daily", help="Run daily review workflow")
    parser.add_argument("--date", required=True, help="Trade date YYYY-MM-DD")
    parser.add_argument("--user", default=None, help="User id for runtime metrics isolation")
    parser.add_argument("--kb-wiki", default=None, help="知识库 wiki 根目录；会传给 agent-daily，并用于刷新驾驶舱晨汇链接")
    parser.add_argument("--skip-sync", action="store_true", help="Skip market data sync")
    parser.add_argument("--skip-long", action="store_true", help="Pass --skip-long to daily-update")
    parser.add_argument("--skip-theme", action="store_true", help="Skip market-triggered theme brief")
    parser.add_argument("--skip-agent", action="store_true", help="Skip daily agent brief generation")
    parser.add_argument("--skip-legacy-theme", action="store_true", help="Skip legacy triggered-themes brief")
    parser.add_argument("--skip-workbench", action="store_true", help="Skip review workbench render")
    parser.add_argument("--start-date", default=None, help="Optional start date for daily-review")
    parser.add_argument(
        "--from-step",
        "--resume-from",
        dest="from_step",
        default=None,
        help="Start workflow from this step",
    )
    parser.add_argument("--only-step", default=None, help="Run only this step")
    parser.add_argument("--continue-on-warn", action="store_true", help="Continue when a recoverable step is downgraded to WARN")
    parser.add_argument("--step-timeout-sec", type=float, default=1800, help="Maximum runtime for each workflow step")
    parser.add_argument("--no-alert", action="store_true", help="Disable operational alerts for failed workflows")
    parser.add_argument("--alert-on-warn", action="store_true", help="Also alert when the workflow finishes with WARN")
    parser.add_argument("--summary-json", default=None, help="Write workflow summary JSON")
    parser.add_argument("--dry-run", action="store_true", help="Print command plan without execution")
    parser.set_defaults(func=cmd_daily)


def add_kb_queue_receive_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "kb-queue-receive",
        help="把当日 kb-ingest-queue.json 归档进知识库 wiki/raw（只 receive，不入库、不 apply）",
    )
    parser.add_argument("--date", required=True, help="交易日 YYYY-MM-DD")
    parser.add_argument("--finance-root", default=None, help="覆盖金融仓路径")
    parser.add_argument("--kb-wiki", default=None, help="知识库 wiki 根目录；默认 env/auto")
    parser.set_defaults(func=cmd_kb_queue_receive)


def cmd_kb_queue_receive(args: argparse.Namespace) -> int:
    from intelligence.paths import default_paths
    from intelligence.services.kb_queue_receive import receive_kb_ingest_queue

    paths = default_paths()
    finance_root = Path(args.finance_root).expanduser() if args.finance_root else paths.finance_root
    kb_wiki = Path(args.kb_wiki).expanduser() if args.kb_wiki else paths.knowledge_wiki
    result = receive_kb_ingest_queue(date=args.date, finance_root=finance_root, kb_wiki=kb_wiki)
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    if result.status == "warn":
        print(f"WARN kb-queue-receive: {result.reason}", file=sys.stderr)
    # 归档失败不阻断复盘；skipped/warn 都当成功退出。
    return 0


def add_kb_queue_status_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "kb-queue-status",
        help="读知识库仓跨仓回补队列回执（receipt.json），看哪些缺口已补/待处理",
    )
    parser.add_argument("--kb-wiki", default=None, help="知识库 wiki 根目录；默认 KB_VAULT 或约定路径")
    parser.add_argument("--since", default=None, help="只看该日期（YYYY-MM-DD）及之后的回执")
    parser.set_defaults(func=cmd_kb_queue_status)


def cmd_kb_queue_status(args: argparse.Namespace) -> int:
    from intelligence import paths as project_paths
    from intelligence.services import kb_queue_receipt

    kb_wiki = Path(args.kb_wiki).expanduser() if args.kb_wiki else project_paths.default_paths().knowledge_wiki
    print(kb_queue_receipt.render_status(kb_wiki, since=args.since))
    return 0


def add_theme_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("theme", help="Run theme radar workflows")
    parser.add_argument("--date", required=True, help="Trade date YYYY-MM-DD")
    parser.add_argument("--market-triggered", action="store_true", required=True, help="Build market-triggered theme candidates")
    parser.add_argument("--top", type=int, default=50, help="Maximum number of market-triggered candidates")
    parser.add_argument("--out-json", default=None, help="Write market-triggered candidates JSON")
    parser.add_argument("--out-md", default=None, help="Write market-triggered candidates Markdown brief")
    parser.add_argument("--summary-json", default=None, help="Write workflow summary JSON")
    parser.set_defaults(func=cmd_theme)


def add_l3_ingest_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "l3-ingest",
        help="Runtime disclosure lookup -> L3 candidate payload -> optional wiki L3 evidence assets.",
    )
    sub = parser.add_subparsers(dest="action", required=True)

    p_company = sub.add_parser("company", help="查公司公告/互动易并抽取可复核 L3 候选事实")
    p_company.add_argument("company", help="公司名或股票代码，如 瑞华泰 / 688323")
    p_company.add_argument("--source", default="cninfo", help="逗号分隔数据源：cninfo,sse_einteract")
    p_company.add_argument("--days", type=int, default=30, help="查询近 N 天")
    p_company.add_argument("--limit", type=int, default=20, help="最多处理工具返回的 N 条结果")
    p_company.add_argument("--out-json", default=None, help="写出 L3 候选 payload JSON")
    p_company.add_argument("--summary-json", default=None, help="Write workflow summary JSON")
    p_company.set_defaults(func=cmd_l3_ingest)

    p_apply = sub.add_parser("apply", help="把 l3-ingest company 生成的候选 payload 沉淀为 wiki L3 证据资产")
    p_apply.add_argument("payload", help="l3-ingest company --out-json 生成的 JSON")
    p_apply.add_argument(
        "--kb-wiki",
        default="/Users/a77/knowledge-base-private/wiki",
        help="知识库 wiki 根目录；默认 /Users/a77/knowledge-base-private/wiki",
    )
    p_apply.add_argument("--apply", action="store_true", help="真正写入 wiki；不加则只 dry-run 预览写入计划")
    p_apply.add_argument("--reviewed", action="store_true", help="标记为已人工复核；默认 review_required=true")
    p_apply.add_argument("--summary-json", default=None, help="Write workflow summary JSON")
    p_apply.set_defaults(func=cmd_l3_apply)


def cmd_ask(args: argparse.Namespace) -> int:
    from intelligence.services.ask import AskOptions
    from intelligence.workflows.ask import run_ask

    modules = tuple(m.strip() for m in args.modules.split(",") if m.strip()) if args.modules else None
    rag_mode, kb_index_dir, kb_err = _resolve_kb_mode(args.query, args.kb_mode, args.wiki_rag_mode)
    if kb_err:
        print(kb_err, file=sys.stderr)
        return 2
    summary, _result, answer = run_ask(
        AskOptions(
            query=args.query,
            date=args.date,
            exports_dir=args.exports_dir,
            kb_wiki=args.kb_wiki,
            top_companies=args.top_companies,
            use_modules=not args.no_modules,
            modules=modules,
            module_timeout=args.module_timeout,
            use_wiki_rag=not args.no_wiki_rag,
            wiki_rag_k=args.wiki_rag_k,
            wiki_rag_mode=rag_mode,
            wiki_rag_timeout=args.wiki_rag_timeout,
            wiki_rag_index_dir=kb_index_dir,
            use_llm=args.llm,
            compose=args.compose,
            llm_model=args.llm_model,
            llm_timeout=args.llm_timeout,
            detail=args.detail,
            user=args.user,
            experience_cards_window=args.experience_cards_window,
            use_l3_lookup=args.l3_lookup,
            l3_lookup_timeout=args.l3_lookup_timeout,
            l3_lookup_limit=args.l3_lookup_limit,
            clarify=not args.no_clarify,
            parallel_blocks=not args.serial_blocks,
        )
    )
    if _result.clarify is not None:
        # 澄清追问短路：印出结构化追问即退出（未检索、不评分）。
        if args.summary_json:
            summary.write_json(args.summary_json)
        print(answer, end="")
        return 0
    if args.summary_json:
        summary.write_json(args.summary_json)
    if args.brief_json:
        if _result.stock_brief is not None:
            Path(args.brief_json).write_text(_result.stock_brief.to_json() + "\n", encoding="utf-8")
        else:
            print(f"[brief-json] 非个股深挖问题，未生成研究简报，跳过 {args.brief_json}", file=sys.stderr)
    if args.audit_ledger and _result.evidence_audit is not None and _result.retrieval_telemetry is not None:
        from intelligence.services import retrieval_audit

        record = retrieval_audit.build_audit_record(
            query=_result.query,
            question_type=(_result.question_plan.question_type if _result.question_plan else "unknown"),
            trade_date=_result.trade_date,
            audit=_result.evidence_audit,
            telemetry=_result.retrieval_telemetry,
            market_phase=(_result.market_state.phase if _result.market_state else None),
            d_block_stats=_result.d_block_stats,
        )
        retrieval_audit.append_record(args.audit_ledger, record)
        if record.is_failure:
            print(f"[audit-ledger] 已记为失败样本：{'、'.join(record.failure_tags)}", file=sys.stderr)
    print(answer, end="")
    if not args.no_score:
        _auto_score_answer(args.query, _result.synthesis or answer, user=args.user)
    return 0 if summary.status in {"PASS", "WARN", "SKIP"} else 1


def _auto_score_answer(question: str, answer: str, *, user: str | None) -> None:
    """回答后自动评分（闭环评估节点）；任何异常只降级为 stderr 警告，不影响回答。"""
    try:
        from intelligence.services import auto_eval

        outcome = auto_eval.evaluate_answer(question, answer, user=user)
        print(auto_eval.render_notice(outcome), file=sys.stderr)
        for warn in outcome.warnings:
            print(f"[answer-score] ⚠ {warn}", file=sys.stderr)
    except Exception as exc:  # pragma: no cover - defensive
        print(f"[answer-score] ⚠ 自动评分失败（不影响回答）：{exc}", file=sys.stderr)


def cmd_l3_ingest(args: argparse.Namespace) -> int:
    from intelligence.workflows.l3_ingest import L3IngestWorkflowOptions, run_l3_ingest

    sources = tuple(source.strip() for source in str(args.source or "").split(",") if source.strip())
    summary, _result, report = run_l3_ingest(
        L3IngestWorkflowOptions(
            company=args.company,
            sources=sources or ("cninfo",),
            days=args.days,
            limit=args.limit,
            out_json=args.out_json,
        )
    )
    if args.summary_json:
        summary.write_json(args.summary_json)
    print(report, end="")
    return 0 if summary.status in {"PASS", "WARN", "SKIP"} else 1


def cmd_l3_apply(args: argparse.Namespace) -> int:
    from intelligence.workflows.l3_ingest import L3ApplyWorkflowOptions, run_l3_apply

    summary, _result, report = run_l3_apply(
        L3ApplyWorkflowOptions(
            payload_path=args.payload,
            kb_wiki=args.kb_wiki,
            apply=args.apply,
            reviewed=args.reviewed,
        )
    )
    if args.summary_json:
        summary.write_json(args.summary_json)
    print(report, end="")
    return 0 if summary.status in {"PASS", "WARN", "SKIP"} else 1


def cmd_foresight(args: argparse.Namespace) -> int:
    import json as _json

    from intelligence.services.foresight import render, result_to_dict
    from intelligence.workflows.foresight import ForesightWorkflowOptions, run_foresight

    summary, result, answer = run_foresight(
        ForesightWorkflowOptions(
            profile=args.profile,
            user=args.user,
            news_file=args.news_file,
            date=args.date,
            exports_dir=args.exports_dir,
            kb_wiki=args.kb_wiki,
            use_kb=args.use_kb,
            kb_themes=args.kb_themes,
            n=args.num,
            candidates=args.candidates,
            llm_model=args.llm_model,
            llm_timeout=args.llm_timeout,
            temperature=args.temperature,
            memory_file=args.memory_file,
            use_memory=args.use_memory,
            memory_window=args.memory_window,
            interactions_file=args.interactions_file,
            use_interactions=args.use_interactions,
            interactions_window=args.interactions_window,
            affinity_half_life=args.affinity_half_life,
            affinity_boost=args.affinity_boost,
            methodology_file=args.methodology_file,
            use_methodology=args.use_methodology,
            corrections_file=args.corrections_file,
            use_corrections=args.use_corrections,
            corrections_window=args.corrections_window,
            judgments_file=args.judgments_file,
            use_judgments=args.use_judgments,
            judgments_window=args.judgments_window,
            checkpoints_file=args.checkpoints_file,
            verdicts_file=args.verdicts_file,
            use_calibration=args.use_calibration,
            calibration_min_n=args.calibration_min_n,
        )
    )
    if args.summary_json:
        summary.write_json(args.summary_json)
    if args.json:
        print(_json.dumps(result_to_dict(result), ensure_ascii=False, indent=2))
    else:
        print(render(result), end="")
    return 0 if summary.status in {"PASS", "WARN", "SKIP"} else 1


def cmd_record_interaction(args: argparse.Namespace) -> int:
    import json as _json

    from intelligence.workflows.record_interaction import (
        RecordInteractionOptions,
        render,
        run_record_interaction,
    )

    summary, record = run_record_interaction(
        RecordInteractionOptions(
            kind=args.kind,
            user=args.user,
            question=args.question,
            themes=args.themes,
            stocks=args.stocks,
            weight=args.weight,
            rating=args.rating,
            note=args.note,
            interactions_file=args.interactions_file,
        )
    )
    if args.summary_json:
        summary.write_json(args.summary_json)
    if args.json:
        print(_json.dumps(record, ensure_ascii=False, indent=2))
    else:
        path = summary.steps[0].outputs[0].split("=", 1)[1] if summary.steps else ""
        print(render(record, path), end="")
    return 0 if summary.status in {"PASS", "WARN", "SKIP"} else 1


def cmd_record_correction(args: argparse.Namespace) -> int:
    import json as _json

    from intelligence import userspace
    from intelligence.services import corrections

    path = args.corrections_file or userspace.user_space(args.user).corrections_path
    _, record = corrections.record_correction(
        path,
        correction=args.correction,
        original=args.original,
        principle=args.principle,
        themes=args.themes,
    )
    if args.json:
        print(_json.dumps(record, ensure_ascii=False, indent=2))
    else:
        print(f"已记纠偏 → {path}")
        if record.get("principle"):
            print(f"  原则：{record['principle']}")
        if record.get("original"):
            print(f"  原话：{record['original']}")
        print(f"  应为：{record['correction']}")
        print("下次 foresight 发问会自动带上此纠偏，避免重犯。")
    return 0


def cmd_refresh_profile(args: argparse.Namespace) -> int:
    import json as _json

    from intelligence.workflows.refresh_profile import RefreshProfileWorkflowOptions, run_refresh_profile

    summary, proposal, diff, answer = run_refresh_profile(
        RefreshProfileWorkflowOptions(
            user=args.user,
            lookback=args.lookback,
            date=args.date,
            top=args.top,
            kb_wiki=args.kb_wiki,
            db_path=args.db_path,
            apply=args.apply,
        )
    )
    if args.summary_json:
        summary.write_json(args.summary_json)
    if args.json:
        print(_json.dumps({"proposal": proposal, "diff": diff}, ensure_ascii=False, indent=2))
    else:
        print(answer, end="")
    return 0 if summary.status in {"PASS", "WARN", "SKIP"} else 1


def cmd_daily(args: argparse.Namespace) -> int:
    from intelligence.workflows.daily_review import DailyReviewOptions, dry_run_daily_review, run_daily_review

    options = DailyReviewOptions(
        date=args.date,
        user=args.user,
        skip_sync=args.skip_sync,
        skip_long=args.skip_long,
        skip_theme=args.skip_theme,
        skip_agent=args.skip_agent,
        skip_legacy_theme=args.skip_legacy_theme,
        skip_workbench=args.skip_workbench,
        start_date=args.start_date,
        dry_run=args.dry_run,
        from_step=args.from_step,
        only_step=args.only_step,
        continue_on_warn=args.continue_on_warn,
        kb_wiki=args.kb_wiki,
        step_timeout_sec=args.step_timeout_sec,
        alerts_enabled=not args.no_alert,
        alert_on_warn=args.alert_on_warn,
    )
    summary = dry_run_daily_review(options) if args.dry_run else run_daily_review(options)
    if args.summary_json:
        summary.write_json(args.summary_json)
    print(summary.to_json(), end="")
    return 0 if summary.status in {"PASS", "WARN", "SKIP"} else 1


def cmd_adapter_smoke(args: argparse.Namespace) -> int:
    from intelligence.workflows.adapter_smoke import AdapterSmokeOptions, run_adapter_smoke

    options = AdapterSmokeOptions(
        date=args.date,
        entity=args.entity,
        concept=args.concept,
    )
    summary = run_adapter_smoke(options)
    if args.summary_json:
        summary.write_json(args.summary_json)
    print(summary.to_json(), end="")
    return 0 if summary.status in {"PASS", "WARN", "SKIP"} else 1


def add_serve_parser(subparsers: argparse._SubParsersAction) -> None:
    from intelligence import server

    parser = subparsers.add_parser(
        "serve",
        help="启动本地 Web GUI（猜你想问卡片流 + 亲和度榜 + 画像 + 策略 overlay；零依赖）",
    )
    server.add_arguments(parser)
    parser.set_defaults(func=cmd_serve)


def cmd_serve(args: argparse.Namespace) -> int:
    from intelligence import server

    server.serve(server.build_config(args))
    return 0


def add_feishu_bot_parser(subparsers: argparse._SubParsersAction) -> None:
    from intelligence.chat import feishu_bot

    parser = subparsers.add_parser(
        "feishu-bot",
        help="飞书 chat bot（B-S2，长连接 + in-process 调 ask 回六段；--echo 退回 B-S0 自检；"
        "凭证走 env / ~/.claude/shared/feishu_config.json）",
    )
    feishu_bot.add_arguments(parser)
    parser.set_defaults(func=cmd_feishu_bot)


def cmd_feishu_bot(args: argparse.Namespace) -> int:
    from intelligence.chat import feishu_bot

    return feishu_bot.run(feishu_bot.build_config(args))


def add_dream_collect_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "dream-collect",
        help="dream-loop：对话源（feishu/claude-code/claude-mem/windsurf/devin）归一化+脱敏 → transcript store + manifest + 脱敏 digest（suggest-only，不碰 DuckDB）",
    )
    from intelligence.dream import collector as _collector

    parser.add_argument(
        "--source",
        default="feishu",
        choices=sorted(_collector.KNOWN_SOURCES),
        help="对话源：feishu/claude-code/claude-mem/windsurf/devin",
    )
    parser.add_argument("--events", default=None, help="原始事件 jsonl（每行一个事件/消息/会话/observation，视源而定）")
    parser.add_argument(
        "--store-dir",
        default=None,
        help="transcript store 根目录（默认 env DREAM_TRANSCRIPT_STORE > 知识库 raw/transcripts > 本仓 _local 回退）",
    )
    parser.add_argument("--repo", default=None, help="标注来源仓库 tag（可选）")
    parser.add_argument("--digest-only", action="store_true", help="只用现有 store 重建 digest，不读 events")
    parser.add_argument("--json", action="store_true", help="输出机器可读 JSON 摘要")
    parser.set_defaults(func=cmd_dream_collect)


def cmd_dream_collect(args: argparse.Namespace) -> int:
    import json as _json

    from intelligence.dream import collector

    summary = collector.run_collect(
        collector.CollectOptions(
            events_path=args.events,
            store_dir=args.store_dir,
            source=args.source,
            repo=args.repo,
            digest_only=args.digest_only,
        )
    )
    if args.json:
        print(_json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(collector.render_summary(summary), end="")
    return 0


def add_dream_evolve_suggest_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "dream-evolve-suggest",
        help="dream-loop C-1C/7A：只读跑 evolve.py suggest → 有新增 suggestion-*.md 才切 dream-loop/evolve-suggest-<date> 分支白名单提交（绝不合 main、绝不写 params.json、绝不起第二个 DuckDB 写进程）",
    )
    parser.add_argument("--repo-dir", required=True, help="用于提交建议的 git clone 目录（独立于用户工作区）")
    parser.add_argument("--python", default=None, help="跑 evolve.py 的 python 解释器（默认当前解释器）")
    parser.add_argument("--user", default=None, help="透传 evolve.py --user（默认共享基线）")
    parser.add_argument(
        "--suggest-subdir",
        default="evolution/suggestions",
        help="suggestion-*.md 相对 repo-dir 的目录（默认 evolution/suggestions；--user 时一般为 evolution/users/<id>/suggestions）",
    )
    parser.add_argument("--branch-prefix", default="dream-loop/evolve-suggest", help="分支名前缀（实际分支带 -<date>）")
    parser.add_argument("--base", default="main", help="切分支的基（默认 main）")
    parser.add_argument("--remote", default="origin", help="git remote（默认 origin）")
    parser.add_argument("--date", default=None, help="覆盖日期（默认机器今日 YYYY-MM-DD）")
    parser.add_argument("--no-run", action="store_true", help="跳过跑 evolve suggest，只把现有新增建议提交到分支")
    parser.add_argument("--timeout", type=int, default=900, help="evolve suggest 子进程超时秒数（默认 900）")
    parser.add_argument("--push", action="store_true", help="提交后 push 分支（默认只本地 commit，绝不合并）")
    parser.add_argument("--json", action="store_true", help="输出机器可读 JSON 摘要")
    parser.set_defaults(func=cmd_dream_evolve_suggest)


def cmd_dream_evolve_suggest(args: argparse.Namespace) -> int:
    import json as _json

    from intelligence.dream import evolve_suggest

    summary = evolve_suggest.run_evolve_suggest(
        evolve_suggest.EvolveSuggestOptions(
            repo_dir=args.repo_dir,
            python=args.python,
            user=args.user,
            suggest_subdir=args.suggest_subdir,
            branch_prefix=args.branch_prefix,
            base=args.base,
            remote=args.remote,
            date=args.date,
            run=not args.no_run,
            timeout=args.timeout,
            push=args.push,
        )
    )
    if args.json:
        print(_json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(evolve_suggest.render_summary(summary))
    return 0


def add_dream_kb_candidates_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "dream-kb-candidates",
        help="dream-loop C-1C/7B：把（已脱敏的）digest/lessons 候选条目 → 保守 KB 事实回写候选 payload（红线写死 graph_only/exposure_only/review_candidate/L1_L3_candidate/peripheral，绝不写 entity 正文）",
    )
    parser.add_argument("--input", required=True, help="候选输入 JSON（含 source_name + candidates 列表）")
    parser.add_argument(
        "--kb-dir",
        default=None,
        help="候选输出目录（默认 env KB_CANDIDATES_DIR > 本仓 gitignore staging intelligence/dream/_kb_candidates；写真实库须显式指 <知识库>/wiki/raw/entity-delta-backfill）",
    )
    parser.add_argument("--json", action="store_true", help="输出机器可读 JSON 摘要")
    parser.set_defaults(func=cmd_dream_kb_candidates)


def cmd_dream_kb_candidates(args: argparse.Namespace) -> int:
    import json as _json

    from intelligence.dream import kb_candidates

    spec = _json.loads(Path(args.input).expanduser().read_text(encoding="utf-8"))
    inputs, meta = kb_candidates.load_inputs(spec)
    payload = kb_candidates.build_payload(
        inputs,
        source_name=meta["source_name"],
        source_date=meta["source_date"],
        raw_sources=meta["raw_sources"],
        source_file=meta["source_file"],
        concept=meta["concept"],
    )
    summary = kb_candidates.write_payload(payload, kb_dir=args.kb_dir)
    if args.json:
        print(_json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(kb_candidates.render_summary(summary))
    return 0 if summary.get("written") else 1


def add_dream_nightly_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "dream-nightly",
        help="dream-loop 采集半：collect → 从 main 切 dream-loop/transcripts-<date> 分支提交脱敏 digest（suggest-only，绝不合并 main、不提交正文、不碰 DuckDB）",
    )
    parser.add_argument("--repo-dir", required=True, help="用于提交 digest 的 git clone 目录（须独立于用户工作区）")
    parser.add_argument("--events", default=None, help="原始事件 jsonl（采集时读取，如飞书 bot 的 --transcript-log 产物）")
    parser.add_argument("--source", default="feishu", help="对话源（默认 feishu）")
    parser.add_argument("--store-subdir", default="raw/transcripts", help="store 相对 repo-dir 的子目录（默认 raw/transcripts，正文按 .gitignore 忽略）")
    parser.add_argument("--branch-prefix", default="dream-loop/transcripts", help="分支名前缀（默认 dream-loop/transcripts，实际分支带 -<date>）")
    parser.add_argument("--base", default="main", help="切分支的基线（默认 main）")
    parser.add_argument("--remote", default="origin", help="git remote（默认 origin）")
    parser.add_argument("--date", default=None, help="覆盖日期（默认本机当日 YYYY-MM-DD）")
    parser.add_argument("--no-collect", action="store_true", help="跳过采集，只提交 store 里已有的 digest")
    parser.add_argument("--push", action="store_true", help="提交后 push 分支（默认只本地 commit，不 push、不合并）")
    parser.add_argument("--json", action="store_true", help="输出机器可读 JSON 摘要")
    parser.set_defaults(func=cmd_dream_nightly)


def cmd_dream_nightly(args: argparse.Namespace) -> int:
    import json as _json

    from intelligence.dream import nightly

    summary = nightly.run_nightly(
        nightly.NightlyOptions(
            repo_dir=args.repo_dir,
            events_path=args.events,
            source=args.source,
            store_subdir=args.store_subdir,
            branch_prefix=args.branch_prefix,
            base=args.base,
            remote=args.remote,
            date=args.date,
            collect=not args.no_collect,
            push=args.push,
        )
    )
    if args.json:
        print(_json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(nightly.render_summary(summary))
    return 0


def add_subconscious_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "subconscious",
        help="潜意识模式：可开关的会话级记忆巩固——开启 → 多轮对话逐轮记信号 → 退出回读出 diff → "
        "确认后双层落盘（interactions.jsonl 机器层 + Obsidian 沉淀 vault 人类层）",
    )
    sub = parser.add_subparsers(dest="action", required=True)

    p_start = sub.add_parser("start", help="开启潜意识模式（写 active 标记 + 建 session buffer）")
    p_start.add_argument("--user", default=None, help="用户 id（默认 default 或环境变量 FORESIGHT_USER）")
    p_start.add_argument("--session", default=None, help="会话 id（默认 YYYY-MM-DD-HHMM）")
    p_start.add_argument("--vault", default=None, help="Obsidian 沉淀 vault 路径（默认 env SUBCONSCIOUS_VAULT）")
    p_start.add_argument("--json", action="store_true", help="输出机器可读 JSON")
    p_start.set_defaults(func=cmd_subconscious_start)

    p_note = sub.add_parser("note", help="记一条本轮信号到 buffer（确认前不进 interactions.jsonl）")
    p_note.add_argument("--user", default=None, help="用户 id（默认 default 或环境变量 FORESIGHT_USER）")
    p_note.add_argument("--session", default=None, help="会话 id（默认取 active）")
    p_note.add_argument("--kind", required=True, help="反馈类型 click/follow/pin/ask/view/skip/dismiss/mute/rate…")
    p_note.add_argument("--theme", dest="themes", action="append", default=[], help="关联题材（可多次）")
    p_note.add_argument("--stock", dest="stocks", action="append", default=[], help="关联个股（可多次）")
    p_note.add_argument("--question", default=None, help="foresight 抛出的问题原文（可选，进「它问我的」节）")
    p_note.add_argument("--quote", default=None, help="用户原话片段（可选，跟在信号后「」里）")
    p_note.add_argument("--memo", default=None, help="深挖纪要（可选，自由 markdown 文本，进「深挖纪要」节：核心判断+可证伪点/关键指标）")
    p_note.add_argument("--weight", type=float, default=None, help="显式权重（覆盖 kind 默认）")
    p_note.add_argument("--rating", type=float, default=None, help="1~5 星评分（kind=rate 时用）")
    p_note.add_argument("--note", default=None, help="备注（可选）")
    p_note.add_argument("--json", action="store_true", help="输出机器可读 JSON")
    p_note.set_defaults(func=cmd_subconscious_note)

    p_review = sub.add_parser("review", help="回读 buffer → 出记忆提案 diff（只读，不落盘）")
    p_review.add_argument("--user", default=None, help="用户 id（默认 default 或环境变量 FORESIGHT_USER）")
    p_review.add_argument("--session", default=None, help="会话 id（默认取 active）")
    p_review.add_argument("--vault", default=None, help="Obsidian 沉淀 vault 路径（默认 active/env）")
    p_review.add_argument("--json", action="store_true", help="输出机器可读 JSON")
    p_review.set_defaults(func=cmd_subconscious_review)

    p_commit = sub.add_parser(
        "commit",
        help="确认落盘：append interactions.jsonl + 写 Obsidian 沉淀日志（需 --apply；缺省等同 review 只预览）",
    )
    p_commit.add_argument("--user", default=None, help="用户 id（默认 default 或环境变量 FORESIGHT_USER）")
    p_commit.add_argument("--session", default=None, help="会话 id（默认取 active）")
    p_commit.add_argument("--vault", default=None, help="Obsidian 沉淀 vault 路径（默认 active/env/回退）")
    p_commit.add_argument("--apply", action="store_true", help="真正落盘（缺省只预览提案）")
    p_commit.add_argument("--json", action="store_true", help="输出机器可读 JSON")
    p_commit.set_defaults(func=cmd_subconscious_commit)

    p_status = sub.add_parser("status", help="看当前是否在潜意识模式 + buffer 计数")
    p_status.add_argument("--user", default=None, help="用户 id（默认 default 或环境变量 FORESIGHT_USER）")
    p_status.add_argument("--json", action="store_true", help="输出机器可读 JSON")
    p_status.set_defaults(func=cmd_subconscious_status)


def cmd_subconscious_start(args: argparse.Namespace) -> int:
    import json as _json

    from intelligence import userspace
    from intelligence.services import subconscious

    us = userspace.user_space(args.user)
    us.ensure_dir()
    state = subconscious.start_session(us, session_id=args.session, vault=args.vault)
    synced = userspace.users_dir() != userspace.USERS_DIR
    if args.json:
        print(_json.dumps(
            {"user": us.user_id, "users_dir": str(userspace.users_dir()), "synced": synced, **state},
            ensure_ascii=False, indent=2,
        ))
    else:
        print(f"潜意识模式已开启：user={us.user_id} session={state['session_id']}")
        print(f"  buffer：{state['buffer']}")
        print(f"  大脑目录：{userspace.users_dir()}" + ("（跨机同步）" if synced else "（仓库内、单机；设 FORESIGHT_USERS_DIR 可跨机同步）"))
        print("  逐轮记信号：`subconscious note --kind click --theme 液冷 --stock 中际旭创`")
        print("  退出回读：`subconscious review` → `subconscious commit --apply`")
    return 0


def cmd_subconscious_note(args: argparse.Namespace) -> int:
    import json as _json

    from intelligence import userspace
    from intelligence.services import subconscious

    us = userspace.user_space(args.user)
    rec = subconscious.append_signal(
        us,
        session_id=args.session,
        kind=args.kind,
        themes=args.themes,
        stocks=args.stocks,
        question=args.question,
        quote=args.quote,
        memo=args.memo,
        note=args.note,
        weight=args.weight,
        rating=args.rating,
    )
    if args.json:
        print(_json.dumps(rec, ensure_ascii=False, indent=2))
    else:
        tags = "、".join(rec["themes"] + rec["stocks"]) or "（无题材/个股）"
        print(f"已记入 buffer：{rec['kind']} · {tags}")
    return 0


def _subconscious_build_proposal(args: argparse.Namespace):
    from intelligence import userspace
    from intelligence.services import subconscious

    us = userspace.user_space(args.user)
    session_id = subconscious._resolve_session(us, args.session)
    buffer = subconscious.load_buffer(us, session_id)
    proposal = subconscious.consolidate(buffer, user_id=us.user_id, session_id=session_id)
    return us, subconscious, proposal


def _proposal_to_dict(proposal, *, interactions_path, note_path, vault_is_fallback, applied):
    return {
        "user": proposal.user_id,
        "session": proposal.session_id,
        "turns": proposal.turns,
        "applied": applied,
        "interactions_path": str(interactions_path),
        "note_path": str(note_path),
        "vault_is_fallback": vault_is_fallback,
        "questions": proposal.questions,
        "memos": proposal.memos,
        "rows": [
            {
                "target": r.target,
                "label": r.label,
                "kind": r.kind,
                "weight": r.weight,
                "count": r.count,
            }
            for r in proposal.rows
        ],
    }


def cmd_subconscious_review(args: argparse.Namespace) -> int:
    import json as _json

    us, subconscious, proposal = _subconscious_build_proposal(args)
    vault_path, is_fallback = subconscious.resolve_vault(us, explicit=args.vault)
    note_path = vault_path / subconscious.VAULT_SUBDIR / f"{proposal.session_id}.md"
    if args.json:
        print(_json.dumps(
            _proposal_to_dict(proposal, interactions_path=us.interactions_path,
                              note_path=note_path, vault_is_fallback=is_fallback, applied=False),
            ensure_ascii=False, indent=2,
        ))
    else:
        print(subconscious.render_proposal(
            proposal, interactions_path=us.interactions_path, note_path=note_path,
            vault_is_fallback=is_fallback, applied=False,
        ), end="")
    return 0


def cmd_subconscious_commit(args: argparse.Namespace) -> int:
    import json as _json

    us, subconscious, proposal = _subconscious_build_proposal(args)
    if not args.apply:
        vault_path, is_fallback = subconscious.resolve_vault(us, explicit=args.vault)
        note_path = vault_path / subconscious.VAULT_SUBDIR / f"{proposal.session_id}.md"
        if args.json:
            print(_json.dumps(
                _proposal_to_dict(proposal, interactions_path=us.interactions_path,
                                  note_path=note_path, vault_is_fallback=is_fallback, applied=False),
                ensure_ascii=False, indent=2,
            ))
        else:
            print(subconscious.render_proposal(
                proposal, interactions_path=us.interactions_path, note_path=note_path,
                vault_is_fallback=is_fallback, applied=False,
            ), end="")
        return 0

    result = subconscious.commit(us, proposal, vault=args.vault)
    subconscious.archive_session(us, proposal.session_id)
    if args.json:
        print(_json.dumps(
            _proposal_to_dict(proposal, interactions_path=result.interactions_path,
                              note_path=result.note_path, vault_is_fallback=result.vault_is_fallback,
                              applied=True),
            ensure_ascii=False, indent=2,
        ))
    else:
        print(subconscious.render_proposal(
            proposal, interactions_path=result.interactions_path, note_path=result.note_path,
            vault_is_fallback=result.vault_is_fallback, applied=True,
        ), end="")
        jtail = f" + {result.judgments_written} 条核心判断台账" if result.judgments_written else ""
        print(
            f"写入 {result.written_records} 条反馈 + 1 篇沉淀日志{jtail}；"
            f"下次 `foresight --user {us.user_id}` 即生效。"
        )
    return 0


def cmd_subconscious_status(args: argparse.Namespace) -> int:
    import json as _json

    from intelligence import userspace
    from intelligence.services import subconscious

    us = userspace.user_space(args.user)
    active = subconscious.load_active(us)
    pending = 0
    if active and active.get("session_id"):
        pending = len(subconscious.load_buffer(us, str(active["session_id"])))
    synced = userspace.users_dir() != userspace.USERS_DIR
    if args.json:
        print(_json.dumps(
            {"user": us.user_id, "users_dir": str(userspace.users_dir()), "synced": synced,
             "active": active, "buffer_signals": pending},
            ensure_ascii=False, indent=2,
        ))
    else:
        if active:
            print(f"潜意识模式：开启中（user={us.user_id} session={active.get('session_id')}，"
                  f"buffer {pending} 条待巩固）")
        else:
            print(f"潜意识模式：未开启（user={us.user_id}）。`subconscious start` 开启。")
        print(f"  大脑目录：{userspace.users_dir()}" + ("（跨机同步）" if synced else "（仓库内、单机）"))
    return 0


def cmd_theme(args: argparse.Namespace) -> int:
    from intelligence.workflows.theme_radar import ThemeRadarOptions, run_theme_radar

    options = ThemeRadarOptions(
        date=args.date,
        market_triggered=args.market_triggered,
        top=args.top,
        out_json=args.out_json,
        out_md=args.out_md,
    )
    summary = run_theme_radar(options)
    if args.summary_json:
        summary.write_json(args.summary_json)
    print(summary.to_json(), end="")
    return 0 if summary.status in {"PASS", "WARN", "SKIP"} else 1


def add_checkpoint_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "checkpoint",
        help="可证伪点回检（C方案）：登记带到期日的判断 → 到期拉盘面/知识库核对对错打分 → "
        "校准你哪类二阶推演靠谱，再回注 foresight 发问",
    )
    sub = parser.add_subparsers(dest="action", required=True)

    p_reg = sub.add_parser("register", help="登记一个可证伪点（陈述 + 到期日 + 类别 + 可选机检规格）")
    p_reg.add_argument("--user", default=None, help="用户 id（默认 default 或环境变量 FORESIGHT_USER）")
    p_reg.add_argument("--claim", required=True, help="可证伪陈述（必填）")
    p_reg.add_argument("--due", required=True, help="到期回检日 YYYY-MM-DD（必填）")
    p_reg.add_argument("--category", default=None, help="二阶推演类型（校准聚合维度，如 估值切换/产能时点/情绪扩散）")
    p_reg.add_argument("--source", default=None, help="判断产出模块（校准第二聚合维度，如 logic_lifecycle/framework_interpretation；手工登记可缺省）")
    p_reg.add_argument("--theme", dest="themes", action="append", default=[], help="关联题材（可多次）")
    p_reg.add_argument("--stock", dest="stocks", action="append", default=[], help="关联个股（可多次）")
    p_reg.add_argument("--metric-type", default=None, choices=["stock_return", "kb_evidence", "market_daily", "manual"], help="机检规格类型；缺省走人工判定")
    p_reg.add_argument("--op", default=">=", choices=[">=", ">", "<=", "<", "=="], help="阈值比较符（默认 >=）")
    p_reg.add_argument("--target", type=float, default=None, help="数值阈值（stock_return=涨幅%%，kb_evidence=新增证据条数）")
    p_reg.add_argument("--window-days", type=int, default=None, help="stock_return 回看窗口天数（默认 60）")
    p_reg.add_argument("--target-name", default=None, help="机检主标的名（个股/题材/公司，缺省取首个 stock/theme）")
    p_reg.add_argument("--condition", dest="conditions", action="append", default=[], help="market_daily 阈值条件（可多次），形如 advancers>=3000、limit_down<=25（字段=fact_market_daily 列名）")
    p_reg.add_argument("--trade-date", default=None, help="market_daily 取数交易日（缺省用 due）")
    p_reg.add_argument("--from-judgment", default=None, help="反链 B 核心判断的 ts（可选）")
    p_reg.add_argument("--session", default=None, help="来源会话 id（可选）")
    p_reg.add_argument("--checkpoints-file", default=None, help="覆盖可证伪点台账路径")
    p_reg.add_argument("--json", action="store_true", help="输出机器可读 JSON")
    p_reg.set_defaults(func=cmd_checkpoint_register)

    p_due = sub.add_parser("due", help="列出到期且尚未拿到终态打分的检查点")
    p_due.add_argument("--user", default=None, help="用户 id（默认 default 或环境变量 FORESIGHT_USER）")
    p_due.add_argument("--date", default=None, help="判定到期的基准日 YYYY-MM-DD（默认今天）")
    p_due.add_argument("--checkpoints-file", default=None, help="覆盖可证伪点台账路径")
    p_due.add_argument("--verdicts-file", default=None, help="覆盖回检打分台账路径")
    p_due.add_argument("--json", action="store_true", help="输出机器可读 JSON")
    p_due.set_defaults(func=cmd_checkpoint_due)

    p_re = sub.add_parser("recheck", help="到期点交给 resolver 拉数核对（缺数据自动降级 unverifiable，绝不编造）")
    p_re.add_argument("--user", default=None, help="用户 id（默认 default 或环境变量 FORESIGHT_USER）")
    p_re.add_argument("--id", default=None, help="只回检指定 id（缺省回检全部到期点）")
    p_re.add_argument("--date", default=None, help="判定到期的基准日 YYYY-MM-DD（默认今天）")
    p_re.add_argument("--db-path", default=None, help="覆盖 DuckDB 路径（盘面 resolver；本机有库才跑真数）")
    p_re.add_argument("--kb-wiki", default=None, help="知识库 wiki 根（知识库 resolver；默认 env/auto）")
    p_re.add_argument("--apply", action="store_true", help="真正把 verdict 落盘 verdicts.jsonl（缺省只预览）")
    p_re.add_argument("--checkpoints-file", default=None, help="覆盖可证伪点台账路径")
    p_re.add_argument("--verdicts-file", default=None, help="覆盖回检打分台账路径")
    p_re.add_argument("--vault", default=None, help="回检日志写入的 Obsidian vault 根（默认 env SUBCONSCIOUS_VAULT，缺则落 users/<id>/_vault）")
    p_re.add_argument("--no-vault-digest", action="store_true", help="不写人类可读回检日志（仅落 verdicts.jsonl）")
    p_re.add_argument("--json", action="store_true", help="输出机器可读 JSON")
    p_re.set_defaults(func=cmd_checkpoint_recheck)

    p_score = sub.add_parser("score", help="人工给某检查点打分（机检规格为 manual 或机检无法判定时）")
    p_score.add_argument("--user", default=None, help="用户 id（默认 default 或环境变量 FORESIGHT_USER）")
    p_score.add_argument("--id", required=True, help="目标检查点 id（必填）")
    p_score.add_argument("--verdict", required=True, choices=["hit", "miss", "partial", "unverifiable"], help="判定结果")
    p_score.add_argument("--score", type=float, default=None, help="覆盖分数（默认按 verdict 映射 hit=1/partial=0.5/miss=0）")
    p_score.add_argument("--reason", default=None, help="判定理由（可选）")
    p_score.add_argument("--verdicts-file", default=None, help="覆盖回检打分台账路径")
    p_score.add_argument("--checkpoints-file", default=None, help="覆盖可证伪点台账路径")
    p_score.add_argument("--kb-wiki", default=None, help="知识库 wiki 根（miss 裁决写回证伪回链 overlay；默认 env/auto）")
    p_score.add_argument("--json", action="store_true", help="输出机器可读 JSON")
    p_score.set_defaults(func=cmd_checkpoint_score)

    p_cal = sub.add_parser("calibrate", help="按类别聚合已回检判断的胜率，定位你哪类二阶推演靠谱/偏差")
    p_cal.add_argument("--user", default=None, help="用户 id（默认 default 或环境变量 FORESIGHT_USER）")
    p_cal.add_argument("--date", default=None, help="判定到期/待回检的基准日 YYYY-MM-DD（默认今天）")
    p_cal.add_argument("--checkpoints-file", default=None, help="覆盖可证伪点台账路径")
    p_cal.add_argument("--verdicts-file", default=None, help="覆盖回检打分台账路径")
    p_cal.add_argument("--json", action="store_true", help="输出机器可读 JSON")
    p_cal.set_defaults(func=cmd_checkpoint_calibrate)

    p_st = sub.add_parser("status", help="台账概览：登记数 / 待回检 / 已打分 / 暂无法判定")
    p_st.add_argument("--user", default=None, help="用户 id（默认 default 或环境变量 FORESIGHT_USER）")
    p_st.add_argument("--date", default=None, help="判定到期的基准日 YYYY-MM-DD（默认今天）")
    p_st.add_argument("--checkpoints-file", default=None, help="覆盖可证伪点台账路径")
    p_st.add_argument("--verdicts-file", default=None, help="覆盖回检打分台账路径")
    p_st.add_argument("--json", action="store_true", help="输出机器可读 JSON")
    p_st.set_defaults(func=cmd_checkpoint_status)

    p_pend = sub.add_parser("pending", help="列出尚未批处理入账的前瞻判断候选（KC-09）")
    p_pend.add_argument("--user", default=None, help="用户 id（默认 FORESIGHT_USER 或 default）")
    p_pend.add_argument("--judgments-file", default=None, help="覆盖 judgments.jsonl 路径")
    p_pend.add_argument("--json", action="store_true", help="输出机器可读 JSON")
    p_pend.set_defaults(func=cmd_checkpoint_pending)

    p_acc = sub.add_parser("accept", help="批处理入账 pending 前瞻判断，并登记 checkpoint（不做 -i）")
    p_acc.add_argument("--user", default=None, help="用户 id（默认 FORESIGHT_USER 或 default）")
    p_acc.add_argument("--id", dest="ids", action="append", default=[], help="指定 pending id（可多次）")
    p_acc.add_argument("--all", action="store_true", help="入账当前全部 pending")
    p_acc.add_argument("--judgments-file", default=None, help="覆盖 judgments.jsonl 路径")
    p_acc.add_argument("--checkpoints-file", default=None, help="覆盖 checkpoints.jsonl 路径")
    p_acc.add_argument("--json", action="store_true", help="输出机器可读 JSON")
    p_acc.set_defaults(func=cmd_checkpoint_accept)

    p_adj = sub.add_parser(
        "adjudicate",
        help="KC-10 到期裁决 job：可机读写 verdicts，不可机读入人工队列，不改判断原文",
    )
    p_adj.add_argument("--user", default=None, help="用户 id（默认 FORESIGHT_USER 或 default）")
    p_adj.add_argument("--date", default=None, help="判定到期的基准日 YYYY-MM-DD（默认今天）")
    p_adj.add_argument("--apply", action="store_true", help="把可机读终态 verdict 落盘（缺省只预览）")
    p_adj.add_argument("--judgments-file", default=None, help="覆盖 judgments.jsonl 路径")
    p_adj.add_argument("--checkpoints-file", default=None, help="覆盖 checkpoints.jsonl 路径")
    p_adj.add_argument("--verdicts-file", default=None, help="覆盖 verdicts.jsonl 路径")
    p_adj.add_argument("--db-path", default=None, help="覆盖 DuckDB 路径")
    p_adj.add_argument("--kb-wiki", default=None, help="知识库 wiki 根")
    p_adj.add_argument("--json", action="store_true", help="输出机器可读 JSON")
    p_adj.set_defaults(func=cmd_checkpoint_adjudicate)


def add_red_team_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "red-team",
        help="红队反方（devils-advocate）：对一条判断拉出最强反面——同类历史纠偏 + "
        "低胜率推演类别 + 固定反方叙事骨架；不给结论不打分，只保证你按钮前见过反面",
    )
    parser.add_argument("--user", default=None, help="用户 id（默认 default 或环境变量 FORESIGHT_USER）")
    parser.add_argument("--claim", required=True, help="被审的判断（必填）")
    parser.add_argument("--theme", dest="themes", action="append", default=[], help="关联题材（可多次，用于匹配历史纠偏）")
    parser.add_argument("--category", default=None, help="本判断的二阶推演类别（用于对照低胜率类别）")
    parser.add_argument("--corrections-window", type=int, default=200, help="回看最近多少条纠偏（默认 200）")
    parser.add_argument("--json", action="store_true", help="输出机器可读 JSON")
    parser.set_defaults(func=cmd_red_team)


def cmd_red_team(args: argparse.Namespace) -> int:
    import json as _json

    from intelligence import userspace
    from intelligence.services import checkpoints, corrections, red_team

    us = userspace.user_space(args.user)
    recs, cwarn = corrections.load_corrections(us.corrections_path, window=args.corrections_window)
    cal, cal_warnings = checkpoints.load_calibration(us.checkpoints_path, us.verdicts_path)
    brief = red_team.build_red_team_brief(
        args.claim,
        themes=args.themes,
        category=args.category,
        corrections=recs,
        calibration=cal,
    )
    warnings = ([cwarn] if cwarn else []) + cal_warnings
    if args.json:
        print(_json.dumps({"brief": brief.to_dict(), "warnings": warnings}, ensure_ascii=False, indent=2))
    else:
        print(brief.to_markdown(), end="")
        for w in warnings:
            print(f"[warn] {w}", file=sys.stderr)
    return 0


def add_retrieval_audit_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "retrieval-audit",
        help="检索审计台账报表：summary=命中来源/失败率聚合；pages=页级命中排行"
        "（档案维护降级的数据底座——零命中页停止精修投入，不删页）",
    )
    sub = parser.add_subparsers(dest="action", required=True)

    p_sum = sub.add_parser("summary", help="台账聚合：命中来源分布 / L3 覆盖率 / 失败率 / 失败标签分布")
    p_sum.add_argument("--ledger", required=True, help="检索审计台账 JSONL 路径（ask --audit-ledger 落的那份）")
    p_sum.set_defaults(func=cmd_retrieval_audit_summary)

    p_pg = sub.add_parser("pages", help="页级命中排行：每个 wiki 页被命中几次、最后命中时间")
    p_pg.add_argument("--ledger", required=True, help="检索审计台账 JSONL 路径（ask --audit-ledger 落的那份）")
    p_pg.add_argument("--top", type=int, default=50, help="只显示前 N 页（默认 50；JSON 输出不截断）")
    p_pg.add_argument("--json", action="store_true", help="输出机器可读 JSON")
    p_pg.set_defaults(func=cmd_retrieval_audit_pages)


def cmd_retrieval_audit_summary(args: argparse.Namespace) -> int:
    import json as _json

    from intelligence.services import retrieval_audit

    print(_json.dumps(retrieval_audit.summarize_ledger(args.ledger), ensure_ascii=False, indent=2))
    return 0


def cmd_retrieval_audit_pages(args: argparse.Namespace) -> int:
    import json as _json

    from intelligence.services import retrieval_audit

    summary = retrieval_audit.summarize_pages(args.ledger)
    if args.json:
        print(_json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    print(
        f"台账 {summary['total_records']} 条记录 · 含 wiki 命中 {summary['records_with_wiki_pages']} 条 · "
        f"命中过 {summary['distinct_pages']} 个不同页"
    )
    for st in summary["pages"][: args.top]:
        print(f"  {st['hits']:>4} 次 · 最后命中 {st['last_hit'][:10] or '?'} · {st['page']}")
    if summary["distinct_pages"] > args.top:
        print(f"  …（其余 {summary['distinct_pages'] - args.top} 页略，--top 调大或 --json 看全量）")
    return 0


def add_perspective_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "perspective",
        help="Perspective Lab 多角色认知编程（P0）：角色画像 + 文章 ingest + 多角色合议落档；"
        "角色只是解释硬数据的镜头，不改写事实（设计见 docs/superpowers/specs/2026-07-03-perspective-lab-design.md）",
    )
    sub = parser.add_subparsers(dest="action", required=True)

    p_init = sub.add_parser("init", help="创建角色：空/内置画像 + 文章目录（blogger 需 ingest 训练；其余三类带内置画像）")
    p_init.add_argument("--user", default=None, help="用户 id（默认 default 或环境变量 FORESIGHT_USER）")
    p_init.add_argument("--id", required=True, help="角色 id（字母数字 . _ -，如 blogger_x）")
    p_init.add_argument("--name", default="", help="人读名称（如 某博主；缺省用 id 或内置名）")
    p_init.add_argument(
        "--type", default="blogger",
        choices=["blogger", "trend_trader", "value_investor", "user_framework", "kol_fengyuan"],
        help="角色类型（默认 blogger）",
    )
    p_init.set_defaults(func=cmd_perspective_init)

    p_ing = sub.add_parser("ingest", help="上传文章：保存原文到本地私有目录 + 写 manifest（内容哈希去重）+ 更新画像置信度")
    p_ing.add_argument("--user", default=None, help="用户 id（默认 default 或环境变量 FORESIGHT_USER）")
    p_ing.add_argument("--perspective", required=True, help="目标角色 id")
    p_ing.add_argument("--input", required=True, help="文章文件路径（Markdown/TXT）")
    p_ing.add_argument("--title", required=True, help="文章标题（必填）")
    p_ing.add_argument("--date", default=None, help="文章日期 YYYY-MM-DD（默认今天）")
    p_ing.add_argument("--source", default=None, help="来源（如 博主名/公众号名）")
    p_ing.add_argument("--json", action="store_true", help="输出机器可读 JSON")
    p_ing.set_defaults(func=cmd_perspective_ingest)

    p_prof = sub.add_parser("profile", help="查看角色画像：镜头/偏好/风险信号/证伪风格 + 样本数与置信度")
    p_prof.add_argument("--user", default=None, help="用户 id（默认 default 或环境变量 FORESIGHT_USER）")
    p_prof.add_argument("--perspective", required=True, help="角色 id")
    p_prof.add_argument("--json", action="store_true", help="输出机器可读 JSON")
    p_prof.set_defaults(func=cmd_perspective_profile)

    p_deb = sub.add_parser(
        "debate",
        help="多角色合议（P0 确定性版）：画像规则 × 用户提供的硬事实摘要 → 结构化报告（事实/角色解释/证伪条件分离）",
    )
    p_deb.add_argument("--user", default=None, help="用户 id（默认 default 或环境变量 FORESIGHT_USER）")
    p_deb.add_argument("--query", required=True, help="要合议的问题（如 明天市场怎么看）")
    p_deb.add_argument(
        "--perspective", dest="perspectives", action="append", default=[], required=True,
        help="参与角色 id（至少 2 个，可多次）",
    )
    p_deb.add_argument("--facts", default=None, help="硬事实摘要文本（P0 必填其一；P1 起自动接 ask）")
    p_deb.add_argument("--facts-file", default=None, help="硬事实摘要文件路径（与 --facts 二选一）")
    p_deb.add_argument("--date", default=None, help="市场数据日期 YYYY-MM-DD（默认今天）")
    p_deb.add_argument("--no-save", action="store_true", help="不写 debates.jsonl（仅打印报告）")
    p_deb.set_defaults(func=cmd_perspective_debate)

    p_ext = sub.add_parser(
        "extract-cards",
        help="学习闭环第一步（P1）：LLM 把已 ingest 的文章逐篇抽成结构化认知卡片"
        "（claims/推理步骤/风险提示/画像候选，含引文逐字核验）；"
        "需配置 LLM key，失败时明确报错、不写半成品",
    )
    p_ext.add_argument("--user", default=None, help="用户 id（默认 default 或环境变量 FORESIGHT_USER）")
    p_ext.add_argument("--perspective", required=True, help="角色 id")
    p_ext.add_argument("--article-id", default=None, help="只抽这一篇（形如 pa-xxxx；默认抽所有未抽的）")
    p_ext.add_argument("--limit", type=int, default=None, help="本次最多抽几篇（控制 LLM 调用量）")
    p_ext.add_argument("--force", action="store_true", help="已有卡片也重抽（覆盖）")
    p_ext.add_argument("--json", action="store_true", help="输出机器可读 JSON")
    p_ext.set_defaults(func=cmd_perspective_extract_cards)

    p_pp = sub.add_parser(
        "propose-patches",
        help="学习闭环第二步（P1）：聚合认知卡片里引文核验通过的画像候选 → pending patch"
        "（确定性聚合，不调 LLM、不自动改画像；同一候选幂等）",
    )
    p_pp.add_argument("--user", default=None, help="用户 id（默认 default 或环境变量 FORESIGHT_USER）")
    p_pp.add_argument("--perspective", required=True, help="角色 id")
    p_pp.add_argument("--json", action="store_true", help="输出机器可读 JSON")
    p_pp.set_defaults(func=cmd_perspective_propose_patches)

    p_pl = sub.add_parser("patches", help="查看画像 patch 候选（pending/approved/rejected）")
    p_pl.add_argument("--user", default=None, help="用户 id（默认 default 或环境变量 FORESIGHT_USER）")
    p_pl.add_argument("--perspective", required=True, help="角色 id")
    p_pl.add_argument("--status", default=None, choices=["pending", "approved", "rejected"], help="按状态过滤")
    p_pl.add_argument("--json", action="store_true", help="输出机器可读 JSON")
    p_pl.set_defaults(func=cmd_perspective_list_patches)

    p_rv = sub.add_parser(
        "review-patch",
        help="学习闭环第三步（P1）：人工确认 patch。--approve 写入画像并在 patch_history 留溯源；"
        "--reject 只改状态。LLM 候选不经这步永远进不了画像",
    )
    p_rv.add_argument("--user", default=None, help="用户 id（默认 default 或环境变量 FORESIGHT_USER）")
    p_rv.add_argument("--perspective", required=True, help="角色 id")
    p_rv.add_argument("--patch-id", required=True, help="patch id（形如 pp-xxxx）")
    decision = p_rv.add_mutually_exclusive_group(required=True)
    decision.add_argument("--approve", action="store_true", help="确认写入画像")
    decision.add_argument("--reject", action="store_true", help="拒绝该候选")
    p_rv.add_argument("--note", default="", help="评审备注（可选）")
    p_rv.set_defaults(func=cmd_perspective_review_patch)

    p_fw = sub.add_parser(
        "framework-daily",
        help="框架解读步（P1）：按 user_framework 画像解读当日 daily-review 硬数据，"
        "命中判断自动落 T+1/T+3 checkpoint（带 framework_version）；profile 缺失时优雅跳过",
    )
    p_fw.add_argument("--user", default=None, help="用户 id（默认 default 或环境变量 FORESIGHT_USER）")
    p_fw.add_argument("--date", required=True, help="市场数据日期 YYYY-MM-DD")
    p_fw.add_argument("--daily-review-md", default=None, help="daily-review markdown 路径（默认 exports/<date>-daily-review.md）")
    p_fw.add_argument("--out-md", default=None, help="框架解读报告输出路径（默认 exports/<date>-framework-interpretation.md）")
    p_fw.add_argument("--json", action="store_true", help="输出机器可读 JSON（不打印报告正文）")
    p_fw.set_defaults(func=cmd_perspective_framework_daily)


def cmd_perspective_framework_daily(args: argparse.Namespace) -> int:
    from intelligence import userspace
    from intelligence.paths import default_paths
    from intelligence.services import framework_interpretation

    us = userspace.user_space(args.user)
    exports = default_paths().market_exports
    md_path = Path(args.daily_review_md).expanduser() if args.daily_review_md else exports / f"{args.date}-daily-review.md"
    out_md = Path(args.out_md).expanduser() if args.out_md else exports / f"{args.date}-framework-interpretation.md"
    result = framework_interpretation.run(us, date=args.date, daily_review_md_path=md_path, out_md=out_md)
    if args.json:
        payload = {k: v for k, v in result.items() if k != "report"}
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    elif result.get("status") == "ok":
        print(result["report"], end="")
        print(
            f"\n[框架解读] version={result['framework_version']} 判断 {result['judgments']} 条，"
            f"新登记 checkpoint {result['checkpoints_added']} 条 → {result['checkpoints_path']}",
        )
    else:
        print(f"[框架解读] 跳过：{result.get('reason')}")
    return 0


def cmd_perspective_init(args: argparse.Namespace) -> int:
    from intelligence import userspace
    from intelligence.services import perspective_lab

    us = userspace.user_space(args.user)
    try:
        path, profile = perspective_lab.init_perspective(
            us, args.id, display_name=args.name, ptype=args.type,
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"已创建角色「{profile['display_name']}」（{profile['id']} / {profile['type']}）")
    print(f"  画像：{path}")
    if profile["type"] == "blogger":
        print(
            f"  下一步：`perspective ingest --user {us.user_id} --perspective {profile['id']} "
            f"--input 文章.md --title 标题 --date YYYY-MM-DD` 上传文章训练画像"
        )
    else:
        print("  已带内置画像，可直接参与 debate；也可手工编辑该 JSON 定制")
    return 0


def cmd_perspective_ingest(args: argparse.Namespace) -> int:
    import json as _json

    from intelligence import userspace
    from intelligence.services import perspective_lab

    us = userspace.user_space(args.user)
    try:
        result = perspective_lab.ingest_article(
            us, args.perspective, args.input,
            title=args.title, date=args.date, source=args.source,
        )
    except (ValueError, FileNotFoundError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if args.json:
        print(_json.dumps(result, ensure_ascii=False, indent=2))
    elif result["duplicate"]:
        print(f"内容重复，跳过：{result['article_id']}（已存在 {result['raw_path']}）")
    else:
        print(f"已入档 {result['article_id']} → {result['raw_path']}（该角色样本 {result['article_count']} 篇）")
    return 0


def cmd_perspective_profile(args: argparse.Namespace) -> int:
    import json as _json

    from intelligence import userspace
    from intelligence.services import perspective_lab

    us = userspace.user_space(args.user)
    try:
        profile = perspective_lab.load_profile(us, args.perspective)
    except (ValueError, FileNotFoundError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if args.json:
        print(_json.dumps(profile, ensure_ascii=False, indent=2))
    else:
        print(perspective_lab.render_profile_text(profile), end="")
    return 0


def cmd_perspective_debate(args: argparse.Namespace) -> int:
    from intelligence import userspace
    from intelligence.services import perspective_lab

    us = userspace.user_space(args.user)
    facts = args.facts or ""
    if args.facts_file:
        fpath = Path(args.facts_file).expanduser()
        if not fpath.is_file():
            print(f"硬事实文件不存在：{fpath}", file=sys.stderr)
            return 1
        facts = fpath.read_text(encoding="utf-8")
    try:
        report, _record = perspective_lab.run_debate(
            us,
            query=args.query,
            perspective_ids=args.perspectives,
            facts=facts,
            date=args.date,
            save=not args.no_save,
        )
    except (ValueError, FileNotFoundError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(report, end="")
    return 0


def cmd_perspective_extract_cards(args: argparse.Namespace) -> int:
    import json as _json

    from intelligence import userspace
    from intelligence.services import perspective_learning

    us = userspace.user_space(args.user)
    try:
        summary = perspective_learning.extract_cards(
            us,
            args.perspective,
            article_id=args.article_id,
            limit=args.limit,
            force=args.force,
        )
    except (ValueError, FileNotFoundError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if args.json:
        print(_json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(
            f"[卡片抽取] {summary['perspective_id']}：文章 {summary['articles']} 篇，"
            f"本次抽取 {len(summary['extracted'])}，已有跳过 {len(summary['skipped_existing'])}，"
            f"失败 {len(summary['failed'])}"
        )
        for item in summary["failed"]:
            print(f"  ✗ {item['article_id']}：{item['reason']}")
        if summary["extracted"]:
            print(
                f"  下一步：`perspective propose-patches --user {us.user_id} "
                f"--perspective {summary['perspective_id']}` 聚合画像候选"
            )
    return 1 if summary["failed"] else 0


def cmd_perspective_propose_patches(args: argparse.Namespace) -> int:
    import json as _json

    from intelligence import userspace
    from intelligence.services import perspective_learning

    us = userspace.user_space(args.user)
    try:
        summary = perspective_learning.propose_patches(us, args.perspective)
    except (ValueError, FileNotFoundError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if args.json:
        print(_json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(
            f"[patch 聚合] {summary['perspective_id']}：候选 {summary['candidates']} 条，"
            f"新建 pending {len(summary['created'])}，画像已有跳过 "
            f"{len(summary['skipped_already_in_profile'])}，已有 patch 跳过 "
            f"{len(summary['skipped_existing_patch'])}"
        )
        if summary["created"]:
            print(
                f"  下一步：`perspective patches --user {us.user_id} --perspective "
                f"{summary['perspective_id']} --status pending` 查看后逐条 review-patch"
            )
    return 0


def cmd_perspective_list_patches(args: argparse.Namespace) -> int:
    import json as _json

    from intelligence import userspace
    from intelligence.services import perspective_learning

    us = userspace.user_space(args.user)
    try:
        patches = perspective_learning.list_patches(us, args.perspective, status=args.status)
    except (ValueError, FileNotFoundError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if args.json:
        print(_json.dumps(patches, ensure_ascii=False, indent=2))
        return 0
    if not patches:
        print("无 patch" + (f"（状态 {args.status}）" if args.status else ""))
        return 0
    for patch in patches:
        print(
            f"[{patch.get('status')}] {patch.get('patch_id')} · {patch.get('field')} · "
            f"{patch.get('value')}（{patch.get('supporting_article_count')} 篇支持）"
        )
        for ev in patch.get("evidence") or []:
            quote = str(ev.get("quote") or "")
            print(f"    ↳ {ev.get('date')} {ev.get('title')}：「{quote}」")
    return 0


def cmd_perspective_review_patch(args: argparse.Namespace) -> int:
    from intelligence import userspace
    from intelligence.services import perspective_learning

    us = userspace.user_space(args.user)
    try:
        patch = perspective_learning.review_patch(
            us,
            args.perspective,
            args.patch_id,
            approve=args.approve,
            note=args.note,
        )
    except (ValueError, FileNotFoundError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if patch["status"] == "approved":
        applied = "已写入画像" if patch.get("applied") else "画像已有同义条目，未重复写入"
        print(f"已确认 {patch['patch_id']}：{patch['field']} ← {patch['value']}（{applied}）")
    else:
        print(f"已拒绝 {patch['patch_id']}")
    return 0


def _checkpoint_paths(args: argparse.Namespace) -> tuple[Path, Path]:
    from intelligence import userspace

    us = userspace.user_space(args.user)
    cpath = Path(args.checkpoints_file).expanduser() if getattr(args, "checkpoints_file", None) else us.checkpoints_path
    vpath = Path(args.verdicts_file).expanduser() if getattr(args, "verdicts_file", None) else us.verdicts_path
    return cpath, vpath


def _judgments_path(args: argparse.Namespace) -> Path:
    from intelligence import userspace

    if getattr(args, "judgments_file", None):
        return Path(args.judgments_file).expanduser()
    return userspace.user_space(args.user).judgments_path


def cmd_checkpoint_pending(args: argparse.Namespace) -> int:
    import json as _json

    from intelligence.services import judgment_extract

    path = _judgments_path(args)
    pending = judgment_extract.list_pending(path)
    if args.json:
        print(_json.dumps({"path": str(path), "pending": pending}, ensure_ascii=False, indent=2))
        return 0
    if not pending:
        print(f"没有 pending 前瞻判断（{path}）")
        return 0
    print(f"pending {len(pending)} 条（{path}）")
    for row in pending:
        due = (row.get("verify_by") or {}).get("due") or "?"
        print(f"- {row.get('id')} 到期 {due} ｜ {row.get('claim')}")
    print("入账：`checkpoint accept --all` 或 `--id <id>`（可多次）")
    return 0


def cmd_checkpoint_accept(args: argparse.Namespace) -> int:
    import json as _json

    from intelligence.services import judgment_extract

    if not args.all and not args.ids:
        print("需要 --all 或至少一个 --id")
        return 2
    jpath = _judgments_path(args)
    cpath, _ = _checkpoint_paths(args)
    accepted = judgment_extract.accept_judgments(
        jpath,
        cpath,
        ids=args.ids,
        accept_all=bool(args.all),
    )
    if args.json:
        print(
            _json.dumps(
                {"judgments": str(jpath), "checkpoints": str(cpath), "accepted": accepted},
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    if not accepted:
        print("没有新入账的前瞻判断（可能已 accept 过）")
        return 0
    print(f"已入账 {len(accepted)} 条，并登记 checkpoint")
    for row in accepted:
        print(f"- {row.get('id')} ｜ {row.get('claim')}")
    return 0


def cmd_checkpoint_adjudicate(args: argparse.Namespace) -> int:
    import json as _json

    from intelligence.services.judgment_adjudicate import run_adjudication_job

    jpath = _judgments_path(args)
    cpath, vpath = _checkpoint_paths(args)
    report = run_adjudication_job(
        judgments_path=jpath,
        checkpoints_path=cpath,
        verdicts_path=vpath,
        today=args.date,
        apply=bool(args.apply),
        db_path=args.db_path,
        wiki_root=args.kb_wiki,
    )
    payload = report.to_dict()
    payload["applied"] = bool(args.apply)
    payload["judgments"] = str(jpath)
    payload["checkpoints"] = str(cpath)
    payload["verdicts"] = str(vpath)
    if args.json:
        print(_json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    verb = "裁决并落盘" if args.apply else "裁决（预览，未落盘；加 --apply 落盘）"
    print(
        f"{verb} 自动 {len(report.auto)} 条 · 人工队列 {len(report.queued)} 条 · "
        f"延期 {len(report.deferred)} 条"
    )
    for item in report.auto:
        print(f"- 自动 {item.id}｜{item.verdict}：{item.reason}")
    for item in report.queued:
        print(f"- 人工 {item.id}：{item.reason}")
    for item in report.deferred:
        print(f"- 延期 {item.id}｜{item.verdict}：{item.reason}")
    if report.judgments_unchanged:
        print("判断原文未动")
    if not args.apply and (report.auto or report.queued or report.deferred):
        print("加 --apply 把可机读终态写入 verdicts.jsonl；人工项请 `checkpoint score`")
    return 0


def cmd_checkpoint_register(args: argparse.Namespace) -> int:
    import json as _json

    from intelligence.services import checkpoints

    cpath, _ = _checkpoint_paths(args)
    metric: dict[str, object] | None = None
    if args.metric_type:
        metric = {"type": args.metric_type}
        if args.metric_type == "market_daily":
            metric["conditions"] = list(args.conditions or [])
            if args.trade_date:
                metric["trade_date"] = args.trade_date
        elif args.metric_type != "manual":
            metric["op"] = args.op
            metric["target"] = args.target
            if args.window_days is not None:
                metric["window_days"] = args.window_days
        if args.target_name:
            metric["target_name"] = args.target_name
    _, record = checkpoints.register_checkpoint(
        cpath,
        claim=args.claim,
        due=args.due,
        category=args.category,
        source=args.source,
        themes=args.themes,
        stocks=args.stocks,
        metric=metric,
        source_judgment_ts=args.from_judgment,
        session_id=args.session,
    )
    if args.json:
        print(_json.dumps({"path": str(cpath), "checkpoint": record}, ensure_ascii=False, indent=2))
    else:
        mtail = f"｜机检 {record['metric']['type']}" if record.get("metric") else "｜人工判定"
        print(f"已登记可证伪点 {record['id']}（到期 {record['due']}{mtail}）")
        print(f"  {record['claim']}")
        print(f"  → 到期跑 `checkpoint recheck --user {args.user or 'default'} --apply`")
    return 0


def cmd_checkpoint_due(args: argparse.Namespace) -> int:
    import json as _json

    from intelligence.services import checkpoints

    cpath, vpath = _checkpoint_paths(args)
    cks, cwarn = checkpoints.load_checkpoints(cpath)
    vds, vwarn = checkpoints.load_verdicts(vpath)
    due = checkpoints.due_checkpoints(cks, vds, today=args.date)
    if args.json:
        print(_json.dumps({"date": args.date or checkpoints._today(), "due": due, "warnings": [w for w in (cwarn, vwarn) if w]}, ensure_ascii=False, indent=2))
    else:
        print(f"到期待回检 {len(due)} 条（基准日 {args.date or checkpoints._today()}）")
        for c in due:
            mt = (c.get("metric") or {}).get("type", "manual")
            print(f"- {c['id']}｜到期 {c['due']}｜{c.get('category') or '未分类'}｜机检 {mt}")
            print(f"    {c.get('claim')}")
    return 0


def cmd_checkpoint_recheck(args: argparse.Namespace) -> int:
    import json as _json

    from intelligence.services import checkpoints, checkpoint_resolvers

    cpath, vpath = _checkpoint_paths(args)
    cks, _ = checkpoints.load_checkpoints(cpath)
    vds, _ = checkpoints.load_verdicts(vpath)
    if args.id:
        targets = [c for c in cks if str(c.get("id")) == args.id]
    else:
        targets = checkpoints.due_checkpoints(cks, vds, today=args.date)
    results: list[dict[str, object]] = []
    for c in targets:
        outcome = checkpoint_resolvers.resolve_checkpoint(
            c, db_path=args.db_path, wiki_root=args.kb_wiki,
        )
        entry: dict[str, object] = {
            "id": c.get("id"),
            "claim": c.get("claim"),
            "category": c.get("category"),
            "verdict": outcome.verdict,
            "score": outcome.score,
            "data_source": outcome.data_source,
            "reason": outcome.reason,
            "observed": outcome.observed,
            "degradation": outcome.degradation,
            "applied": False,
        }
        if args.apply:
            _, verdict_record = checkpoints.record_verdict(
                vpath,
                id=str(c.get("id")),
                verdict=outcome.verdict,
                score=outcome.score,
                observed=outcome.observed,
                data_source=outcome.data_source,
                reason=outcome.reason,
                degradation=outcome.degradation,
                auto=True,
            )
            entry["applied"] = True
            entry["writeback"] = _checkpoint_miss_writeback(c, verdict_record, args.kb_wiki)
        results.append(entry)

    # 人类层回检日志：落盘时同步写一份可读 markdown 到 Obsidian vault，让夜间 recheck 不黑盒。
    digest_path: str | None = None
    if args.apply and results and not args.no_vault_digest:
        from datetime import date as _date

        from intelligence import userspace

        us = userspace.user_space(args.user)
        eff_date = args.date or _date.today().isoformat()
        vault, is_fallback = checkpoints.resolve_recheck_vault(us.root, explicit=args.vault)
        section = checkpoints.build_recheck_digest_section(results, applied=True)
        note = checkpoints.write_recheck_digest(vault, section, date=eff_date)
        digest_path = str(note)

    if args.json:
        print(_json.dumps(
            {"applied": args.apply, "results": results, "digest_path": digest_path},
            ensure_ascii=False, indent=2,
        ))
    else:
        verb = "回检并落盘" if args.apply else "回检（预览，未落盘；加 --apply 落盘）"
        print(f"{verb} {len(results)} 条")
        for r in results:
            print(f"- {r['id']}｜{r['verdict']}（{r['data_source']}）：{r['reason']}")
        if digest_path:
            tail = "（回退路径，非你的 Obsidian；指 --vault / SUBCONSCIOUS_VAULT 落到 vault）" if is_fallback else ""
            print(f"人类可读回检日志：{digest_path}{tail}")
        if not args.apply and results:
            print("加 --apply 把以上 verdict 写入 verdicts.jsonl")
    return 0


def _checkpoint_miss_writeback(
    checkpoint: dict[str, object] | None,
    verdict_record: dict[str, object],
    kb_wiki: str | None,
) -> dict[str, object] | None:
    """miss 裁决落盘后把关联证据写回知识库证伪回链 overlay；失败只告警不阻断。"""
    if checkpoint is None or str(verdict_record.get("verdict") or "") != "miss":
        return None
    from intelligence.services import checkpoint_writeback

    try:
        return checkpoint_writeback.writeback_miss_verdict(
            checkpoint, verdict_record, wiki_root=kb_wiki
        )
    except Exception as exc:  # noqa: BLE001 - 写回是增强不是闸门
        print(f"[checkpoint] 证伪回链写回失败（不影响回检落盘）：{exc}", file=sys.stderr)
        return {"written": 0, "matched": 0, "skipped_reason": f"写回异常：{exc}"}


def cmd_checkpoint_score(args: argparse.Namespace) -> int:
    import json as _json

    from intelligence.services import checkpoints

    cpath, vpath = _checkpoint_paths(args)
    _, record = checkpoints.record_verdict(
        vpath,
        id=args.id,
        verdict=args.verdict,
        score=args.score,
        data_source="manual",
        reason=args.reason or "",
        auto=False,
    )
    cks, _ = checkpoints.load_checkpoints(cpath)
    checkpoint = next((c for c in cks if str(c.get("id")) == args.id), None)
    writeback = _checkpoint_miss_writeback(checkpoint, record, getattr(args, "kb_wiki", None))
    if args.json:
        print(_json.dumps(
            {"path": str(vpath), "verdict": record, "writeback": writeback},
            ensure_ascii=False, indent=2,
        ))
    else:
        print(f"已人工打分 {record['id']}｜{record['verdict']}（分数 {record['score']}）")
        if writeback and writeback.get("written"):
            print(f"已将 {writeback['written']} 条关联证据写回证伪回链 overlay（invalidated）")
    return 0


def cmd_checkpoint_calibrate(args: argparse.Namespace) -> int:
    import json as _json

    from intelligence.services import checkpoints

    cpath, vpath = _checkpoint_paths(args)
    cal, warnings = checkpoints.load_calibration(cpath, vpath, today=args.date)
    if args.json:
        print(_json.dumps(
            {
                "scored": cal.scored,
                "pending": cal.pending,
                "unverifiable": cal.unverifiable,
                "overall_rate": round(cal.overall_rate, 4),
                "by_category": [
                    {
                        "category": s.category,
                        "n": s.n,
                        "hits": s.hits,
                        "partial": s.partial,
                        "miss": s.miss,
                        "hit_rate": round(s.hit_rate, 4),
                        "reliability": s.reliability,
                        "samples": s.samples,
                    }
                    for s in cal.by_category
                ],
                "by_source": [
                    {
                        "source": s.category,
                        "n": s.n,
                        "hits": s.hits,
                        "partial": s.partial,
                        "miss": s.miss,
                        "hit_rate": round(s.hit_rate, 4),
                        "reliability": s.reliability,
                        "samples": s.samples,
                    }
                    for s in cal.by_source
                ],
                "warnings": warnings,
            },
            ensure_ascii=False, indent=2,
        ))
    else:
        print(checkpoints.render_report(cal), end="")
    return 0


def cmd_checkpoint_status(args: argparse.Namespace) -> int:
    import json as _json

    from intelligence.services import checkpoints

    cpath, vpath = _checkpoint_paths(args)
    cks, cwarn = checkpoints.load_checkpoints(cpath)
    vds, vwarn = checkpoints.load_verdicts(vpath)
    cal = checkpoints.calibrate(cks, vds, today=args.date)
    payload = {
        "checkpoints": len(cks),
        "verdicts": len(vds),
        "scored": cal.scored,
        "pending": cal.pending,
        "unverifiable": cal.unverifiable,
        "checkpoints_path": str(cpath),
        "verdicts_path": str(vpath),
        "warnings": [w for w in (cwarn, vwarn) if w],
    }
    if args.json:
        print(_json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"可证伪点台账：登记 {payload['checkpoints']} 条 · 已打分 {payload['scored']} 条 · "
              f"待回检 {payload['pending']} 条 · 暂无法判定 {payload['unverifiable']} 条")
        print(f"  checkpoints: {cpath}")
        print(f"  verdicts:    {vpath}")
    return 0


def _self_use_ledger_path(args: argparse.Namespace) -> Path:
    if args.ledger:
        return Path(args.ledger).expanduser()

    from intelligence import userspace

    return userspace.user_space(args.user).root / "self-use" / "events.jsonl"


def _self_use_approval_path(ledger_path: Path) -> Path:
    return ledger_path.parent / "approval.json"


def _self_use_trading_days(args: argparse.Namespace) -> list[str]:
    """解析 canonical A 股交易日历：显式 --trading-day / --calendar-db / 默认本地 DuckDB。"""
    from intelligence.paths import default_market_db_path
    from intelligence.services.self_use_maturity import trading_days_from_duckdb

    injected = getattr(args, "trading_day", None)
    if injected:
        return sorted(set(injected))
    calendar_db = getattr(args, "calendar_db", None)
    if not calendar_db:
        # 与盘面层共用同一个解析器：双根架构下代码根是 runtime 快照，库在数据根。
        # 原先写死代码根，导致自用门禁恒报 trading_calendar_unavailable——不是
        # 缺日历，是找错了地方（同一个 bug 在 18 处盘面调用点已修，见 75b6e46e）。
        calendar_db = default_market_db_path()
    return trading_days_from_duckdb(calendar_db)


def _self_use_run_store(args: argparse.Namespace):
    from intelligence.services.run_store import RunStore

    run_root = getattr(args, "run_root", None)
    return RunStore(args.user, root=Path(run_root).expanduser() if run_root else None)


def cmd_self_use_record(args: argparse.Namespace) -> int:
    from dataclasses import asdict

    from intelligence.services.self_use_maturity import (
        RunBindingError,
        SelfUseEvent,
        SelfUseLedger,
        ingest_self_use_event,
    )

    try:
        recorded = ingest_self_use_event(
            SelfUseLedger(_self_use_ledger_path(args)),
            SelfUseEvent(
                trade_date=args.date,
                workflow=args.workflow,
                outcome=args.outcome,
                manual_rescue=args.manual_rescue,
                severe_fact_error=args.severe_fact_error,
                useful=args.useful,
                run_id=args.run_id,
                note=args.note,
            ),
            run_store=_self_use_run_store(args),
            trading_days=_self_use_trading_days(args),
            today=getattr(args, "today", None),
        )
    except (OSError, TypeError, ValueError, RunBindingError) as exc:
        print(f"self-use record failed: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(asdict(recorded), ensure_ascii=False, indent=2))
    return 0


def cmd_self_use_status(args: argparse.Namespace) -> int:
    from dataclasses import asdict

    from intelligence.services.self_use_maturity import (
        MINIMUM_TRADE_DATES,
        WORKFLOWS,
        SelfUseApprovalStore,
        SelfUseLedger,
        evaluate_maturity,
    )

    try:
        ledger_path = _self_use_ledger_path(args)
        events = SelfUseLedger(ledger_path).load()
        trading_days = _self_use_trading_days(args)
        base = evaluate_maturity(
            events,
            trading_days=trading_days,
            today=getattr(args, "today", None),
            require_consecutive_trading_days=args.require_consecutive_trading_days,
        )
        approvals = SelfUseApprovalStore(_self_use_approval_path(ledger_path))
        persisted_approval = approvals.is_approved_for(base)
        user_approved = bool(persisted_approval or args.user_approved)
        result = evaluate_maturity(
            events,
            trading_days=trading_days,
            today=getattr(args, "today", None),
            user_approved=user_approved,
            require_consecutive_trading_days=args.require_consecutive_trading_days,
        )
    except (OSError, TypeError, ValueError) as exc:
        print(f"self-use status failed: {exc}", file=sys.stderr)
        return 2

    if args.json:
        payload = asdict(result)
        payload["persisted_approval"] = persisted_approval
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        metrics = result.metrics
        workflows = metrics["covered_workflows"]
        blockers = ", ".join(result.blockers) if result.blockers else "none"
        print(
            f"{metrics['distinct_trade_dates']}/{MINIMUM_TRADE_DATES}交易日 · "
            f"workflow {len(workflows)}/{len(WORKFLOWS)}"
        )
        print(f"blockers: {blockers}")
        print(f"passed: {str(result.passed).lower()}")
    return 0 if result.passed else 1


def cmd_self_use_approve(args: argparse.Namespace) -> int:
    from intelligence.services.self_use_maturity import (
        SelfUseApprovalStore,
        SelfUseLedger,
        evaluate_maturity,
    )

    try:
        ledger_path = _self_use_ledger_path(args)
        events = SelfUseLedger(ledger_path).load()
        result = evaluate_maturity(
            events,
            trading_days=_self_use_trading_days(args),
            today=getattr(args, "today", None),
            require_consecutive_trading_days=args.require_consecutive_trading_days,
        )
        if not result.eligible_for_user_decision:
            print(
                "self-use approve rejected: not eligible_for_user_decision "
                f"(blockers: {', '.join(result.blockers)})",
                file=sys.stderr,
            )
            return 2
        record = SelfUseApprovalStore(_self_use_approval_path(ledger_path)).approve(
            result, approved_by=args.by
        )
    except (OSError, TypeError, ValueError) as exc:
        print(f"self-use approve failed: {exc}", file=sys.stderr)
        return 2

    print(
        json.dumps(
            {
                "approved_at": record.approved_at,
                "approved_by": record.approved_by,
                "eligibility_fingerprint": record.eligibility_fingerprint,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def _add_self_use_calendar_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--calendar-db",
        default=None,
        help="DuckDB path holding fact_stock_daily (defaults to db/market_feature_store.duckdb)",
    )
    parser.add_argument(
        "--trading-day",
        action="append",
        default=None,
        help="Inject a canonical trading day (repeatable; for testing/diagnostics)",
    )
    parser.add_argument(
        "--today",
        default=None,
        help="Override 'today' for the future-date check (ISO date; testing/diagnostics)",
    )
    parser.add_argument(
        "--require-consecutive-trading-days",
        action="store_true",
        help="Apply the optional product policy requiring one consecutive trading-day streak",
    )


def add_self_use_parser(subparsers: argparse._SubParsersAction) -> None:
    from intelligence.services.self_use_maturity import OUTCOMES, WORKFLOWS

    parser = subparsers.add_parser(
        "self-use", help="Record and evaluate the private self-use maturity gate"
    )
    commands = parser.add_subparsers(dest="self_use_command", required=True)

    record = commands.add_parser("record", help="Record one explicit self-use event")
    record.add_argument("--user", default=None, help="User id for the default private ledger")
    record.add_argument("--ledger", default=None, help="Explicit ledger path for testing or diagnostics")
    record.add_argument("--date", required=True, help="Trading date in YYYY-MM-DD format")
    record.add_argument("--workflow", required=True, choices=sorted(WORKFLOWS))
    record.add_argument("--outcome", required=True, choices=sorted(OUTCOMES))
    useful = record.add_mutually_exclusive_group(required=True)
    useful.add_argument("--useful", dest="useful", action="store_true")
    useful.add_argument("--not-useful", dest="useful", action="store_false")
    record.add_argument("--manual-rescue", action="store_true")
    record.add_argument("--severe-fact-error", action="store_true")
    record.add_argument("--run-id", default=None, help="Workbench run_id to bind (required)")
    record.add_argument("--run-root", default=None, help="RunStore root override for testing or diagnostics")
    record.add_argument("--note", default="")
    _add_self_use_calendar_args(record)
    record.set_defaults(func=cmd_self_use_record)

    status = commands.add_parser("status", help="Evaluate the self-use maturity gate")
    status.add_argument("--user", default=None, help="User id for the default private ledger")
    status.add_argument("--ledger", default=None, help="Explicit ledger path for testing or diagnostics")
    status.add_argument("--json", action="store_true", help="Print the complete result as JSON")
    status.add_argument(
        "--user-approved",
        action="store_true",
        help="Transient diagnostic approval for this evaluation only (not persisted)",
    )
    _add_self_use_calendar_args(status)
    status.set_defaults(func=cmd_self_use_status)

    approve = commands.add_parser(
        "approve", help="Persist an auditable user approval bound to the current evaluation"
    )
    approve.add_argument("--user", default=None, help="User id for the default private ledger")
    approve.add_argument("--ledger", default=None, help="Explicit ledger path for testing or diagnostics")
    approve.add_argument("--by", required=True, help="Approver identity recorded as approved_by")
    _add_self_use_calendar_args(approve)
    approve.set_defaults(func=cmd_self_use_approve)


def add_news_alias_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("news-alias", help="W7 中英别名表：从 wiki 提案，人工确认后入表（KC-14）")
    sub = parser.add_subparsers(dest="action", required=True)
    p_prop = sub.add_parser("propose", help="从 wiki 概念/实体页确定性抽取中英候选，不写入别名表")
    p_prop.add_argument("--wiki", default=None, help="wiki 根（含 concepts/ entities）；默认 KNOWLEDGE_WIKI")
    p_prop.add_argument("--limit", type=int, default=50)
    p_prop.add_argument("--json", action="store_true")
    p_prop.set_defaults(func=cmd_news_alias_propose)
    p_acc = sub.add_parser("accept", help="人工确认一条中英对，写入 news_keyword_aliases.json")
    p_acc.add_argument("--zh", required=True)
    p_acc.add_argument("--en", required=True)
    p_acc.add_argument("--aliases-file", default=None, help="覆盖别名表路径")
    p_acc.add_argument("--json", action="store_true")
    p_acc.set_defaults(func=cmd_news_alias_accept)


def cmd_news_alias_propose(args: argparse.Namespace) -> int:
    import json as _json
    from intelligence.paths import default_paths
    from intelligence.services.news_alias_propose import propose_alias_candidates

    wiki = Path(args.wiki).expanduser() if args.wiki else default_paths().knowledge_wiki
    found = propose_alias_candidates(wiki, limit=args.limit)
    payload = [item.to_dict() for item in found]
    if args.json:
        print(_json.dumps({"wiki": str(wiki), "candidates": payload}, ensure_ascii=False, indent=2))
        return 0
    print(f"候选 {len(found)} 条（未入表；`news-alias accept --zh … --en …`）")
    for item in found:
        print(f"- {item.zh} → {item.en} ｜ {item.source}")
    return 0


def cmd_news_alias_accept(args: argparse.Namespace) -> int:
    import json as _json
    from intelligence.services.news_alias_propose import accept_alias

    written = accept_alias(args.zh, args.en, path=args.aliases_file)
    if args.json:
        print(_json.dumps(written, ensure_ascii=False, indent=2))
        return 0
    zh, en = next(iter(written.items()))
    print(f"已入表：{zh} → {en}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Financial intelligence product CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)
    add_ask_parser(subparsers)
    add_chat_parser(subparsers)
    add_agent_parser(subparsers)
    add_agent_eval_parser(subparsers)
    add_answer_score_parser(subparsers)
    add_route_parser(subparsers)
    add_orchestrate_parser(subparsers)
    add_logic_match_parser(subparsers)
    add_logic_match_batch_parser(subparsers)
    add_daily_agent_parser(subparsers)
    add_effectiveness_parser(subparsers)
    add_foresight_parser(subparsers)
    add_prime_parser(subparsers)
    add_record_interaction_parser(subparsers)
    add_record_correction_parser(subparsers)
    add_memory_status_parser(subparsers)
    add_refresh_profile_parser(subparsers)
    add_migrate_workbench_store_parser(subparsers)
    add_adapter_smoke_parser(subparsers)
    add_daily_parser(subparsers)
    add_theme_parser(subparsers)
    add_kb_queue_status_parser(subparsers)
    add_kb_queue_receive_parser(subparsers)
    add_l3_ingest_parser(subparsers)
    add_serve_parser(subparsers)
    add_feishu_bot_parser(subparsers)
    add_dream_collect_parser(subparsers)
    add_dream_evolve_suggest_parser(subparsers)
    add_dream_kb_candidates_parser(subparsers)
    add_dream_nightly_parser(subparsers)
    add_subconscious_parser(subparsers)
    add_checkpoint_parser(subparsers)
    add_red_team_parser(subparsers)
    add_retrieval_audit_parser(subparsers)
    add_perspective_parser(subparsers)
    add_self_use_parser(subparsers)
    add_news_alias_parser(subparsers)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
