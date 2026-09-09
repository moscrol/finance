"""能力升级任务包 02（深读检索）验收尺：20 题三段损耗。

三段：候选召回（期望页进 kb_rag 命中）→ 进入模型上下文（关键短语出现在模型可见的
工具结果里）→ 最终使用（关键短语出现在公开答案里）。

- ``outline``  选题辅助：打印知识库页的章节结构与含指定词的节，人工定「正确原文位置」。
- ``offline``  第一、二段离线确定性测量：真实 kb_rag 检索 + 真实 kb_search 工具函数 +
               harness 真实投影链（prune → budget → strip_hashes），不调模型。
               ``--deep off`` 用 ``KB_DEEP_READ_TOTAL_CHARS=0`` / ``KB_STALE_RECOVERY=0`` 关掉
               02 的两项能力得到基线；同一套题、同一索引、同一检索模式。
- ``live``     第三段：经 Workbench ``/api/conversations`` 真实对话入口跑题，读 answer.md 与
               continuous-episode.json，报关键短语是否进入模型可见工具结果、是否进入答案，
               以及耗时 / 工具调用数 / 模型用量。
- ``report``   两份 offline 或 live 结果 JSON 对照成表。

冻结集格式（JSONL）：
    {"case_id": "dr-01", "question": "…", "expected_pages": ["wiki/entities/x.md"],
     "section": "面包屑", "key_phrases": ["必须出现的短语（任一即中）"], "note": "…"}

纪律：只读；不改题、不删题；每题逐条输出，失败也列出来。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import sys
import time
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

DEFAULT_SET = _REPO / "intelligence" / "eval" / "fixtures" / "cap02-deep-read-twenty-2026-09-09.jsonl"


def _squash(text: str) -> str:
    return re.sub(r"\s+", "", str(text or "")).casefold()


def load_cases(path: Path) -> list[dict[str, object]]:
    cases: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        cases.append(json.loads(line))
    return cases


def _phrase_hit(phrases: list[str], text: str) -> str | None:
    hay = _squash(text)
    for phrase in phrases:
        if _squash(phrase) and _squash(phrase) in hay:
            return phrase
    return None


# ---------------------------------------------------------------------------
# outline
# ---------------------------------------------------------------------------
def cmd_outline(args: argparse.Namespace) -> int:
    from intelligence.services import kb_rag
    from intelligence.services.kb_window_reexcerpt import split_sections

    wiki = Path(args.wiki).expanduser()
    terms = [t for t in (args.terms or []) if t]
    for rel in args.pages:
        page = kb_rag.resolve_wiki_page(wiki, rel)
        if page is None:
            print(f"## {rel}: NOT FOUND")
            continue
        raw = page.read_text(encoding="utf-8")
        sections = split_sections(kb_rag._strip_frontmatter_text(raw))
        print(f"## {rel} ({len(raw)} chars, {len(sections)} sections)")
        for crumb, text in sections:
            flag = ""
            if terms and any(t.casefold() in text.casefold() for t in terms):
                flag = " *"
            print(f"  - [{len(text):5d}] {crumb}{flag}")
            if flag and args.show:
                compact = re.sub(r"\s+", " ", text)
                for t in terms:
                    pos = compact.casefold().find(t.casefold())
                    if pos >= 0:
                        start = max(0, pos - 80)
                        print(f"      …{compact[start:start + 220]}…")
                        break
    return 0


# ---------------------------------------------------------------------------
# offline
# ---------------------------------------------------------------------------
@dataclass
class OfflineRow:
    case_id: str
    question: str
    expected_pages: list[str]
    key_phrases: list[str]
    hit_pages: list[str] = field(default_factory=list)
    candidate_recall: bool = False
    phrase_in_raw_evidence: str | None = None
    phrase_in_model_view: str | None = None
    model_view_chars: int = 0
    evidence_items: int = 0
    deep_read_items: int = 0
    stale_recovered: int = 0
    stale_unrecoverable: int = 0
    retrieval_status: str = ""
    retrieval_warning: str = ""
    latency_ms: int = 0
    error: str = ""


def _model_view(tool: str, query: str, evidence: list[object], observation: str) -> str:
    """复用 harness 的三步投影，得到模型真正看到的工具结果字节。"""
    from intelligence.services.agent_runtime import public_agent_evidence
    from intelligence.services.episode_protocol import strip_hashes_for_model
    from intelligence.services.tool_observation_noise import prune_tool_observation
    from intelligence.services.tool_result_budget import budget_tool_observation

    payload = {
        "ok": True,
        "tool": tool,
        "query": query,
        "observation": observation,
        "evidence": [
            {**public_agent_evidence(item), "evidence_id": f"E{index}"}  # type: ignore[arg-type]
            for index, item in enumerate(evidence, 1)
        ],
        "gaps": [],
    }
    pruned, _seen = prune_tool_observation(payload, seen_prose=frozenset())
    return json.dumps(strip_hashes_for_model(budget_tool_observation(pruned)), ensure_ascii=False)


def cmd_offline(args: argparse.Namespace) -> int:
    if args.deep == "off":
        os.environ["KB_DEEP_READ_TOTAL_CHARS"] = "0"
        os.environ["KB_STALE_RECOVERY"] = "0"
    else:
        os.environ.pop("KB_DEEP_READ_TOTAL_CHARS", None)
        os.environ.pop("KB_STALE_RECOVERY", None)
    if args.worker:
        os.environ["RAG_WORKER_ENABLED"] = "1"

    from intelligence.services import agent_research, kb_rag
    from intelligence.services.agent_research import AgentToolContext
    from intelligence.services.research_contract import ResearchDeadline

    wiki = Path(args.wiki).expanduser()
    cases = load_cases(Path(args.set))
    rows: list[OfflineRow] = []
    if args.worker:
        # 冷加载 bge-m3 约 60 s，会吃掉第一题的工具窗；先预热，和生产 app.py lifespan 一样。
        started = time.monotonic()
        try:
            status = kb_rag.prewarm(wiki, timeout=float(args.prewarm_timeout))
            print(f"prewarm {int((time.monotonic() - started) * 1000)}ms {json.dumps(status, ensure_ascii=False)[:200]}", flush=True)
        except Exception as exc:  # noqa: BLE001
            print(f"prewarm failed: {type(exc).__name__}: {exc}", flush=True)

    def retrieve_kb(query: str, timeout: float):
        return kb_rag.retrieve(
            query,
            wiki,
            k=6,
            mode=args.mode,
            timeout=min(timeout, float(args.timeout)),
            excerpt_chars=240,
            budget_query=query,
            require_fresh=True,
            cache_scope=None,
        )

    tool = agent_research.build_default_tools(retrieve_kb)["kb_search"]
    for case in cases:
        row = OfflineRow(
            case_id=str(case["case_id"]),
            question=str(case["question"]),
            expected_pages=[str(p) for p in case.get("expected_pages", [])],
            key_phrases=[str(p) for p in case.get("key_phrases", [])],
        )
        started = time.monotonic()
        try:
            context = AgentToolContext(ResearchDeadline.from_timeout(float(args.timeout) + 30.0), lambda: False, None)
            evidence, observation, trace = tool(row.question, context)
            row.latency_ms = int((time.monotonic() - started) * 1000)
            primary = [item for item in evidence if not getattr(item, "deep_read", False)]
            row.hit_pages = [str(getattr(item, "internal_locator", "")) for item in primary]
            row.candidate_recall = any(page in row.hit_pages for page in row.expected_pages)
            row.evidence_items = len(evidence)
            row.deep_read_items = len(evidence) - len(primary)
            raw_text = "\n".join(str(getattr(item, "detail", "")) for item in evidence) + "\n" + observation
            row.phrase_in_raw_evidence = _phrase_hit(row.key_phrases, raw_text)
            view = _model_view("kb_search", row.question, evidence, observation)
            row.model_view_chars = len(view)
            row.phrase_in_model_view = _phrase_hit(row.key_phrases, view)
            row.retrieval_status = str(trace.status)
            row.retrieval_warning = observation[:200] if not primary else ""
            # 新鲜度恢复读数：kb_search 不透出遥测，直接再查一次结果缓存外的 retrieve 太贵；
            # 用 observation 里的告警文本判读。
            match = re.search(r"(\d+) 条过期命中已当轮重读原页恢复", observation)
            row.stale_recovered = int(match.group(1)) if match else 0
            match = re.search(r"丢弃 (\d+) 条非 fresh 命中", observation)
            row.stale_unrecoverable = int(match.group(1)) if match else 0
        except Exception as exc:  # noqa: BLE001 — 每题独立，一题炸不影响其余
            row.error = f"{type(exc).__name__}: {exc}"[:300]
            row.latency_ms = int((time.monotonic() - started) * 1000)
        rows.append(row)
        mark = "✓" if row.phrase_in_model_view else ("~" if row.candidate_recall else "✗")
        print(
            f"{mark} {row.case_id} recall={int(row.candidate_recall)} raw={int(bool(row.phrase_in_raw_evidence))} "
            f"view={int(bool(row.phrase_in_model_view))} items={row.evidence_items}(+{row.deep_read_items}) "
            f"view_chars={row.model_view_chars} {row.latency_ms}ms {row.error}",
            flush=True,
        )

    summary = {
        "deep": args.deep,
        "mode": args.mode,
        "cases": len(rows),
        "candidate_recall": sum(r.candidate_recall for r in rows),
        "phrase_in_raw_evidence": sum(bool(r.phrase_in_raw_evidence) for r in rows),
        "phrase_in_model_view": sum(bool(r.phrase_in_model_view) for r in rows),
        "errors": sum(bool(r.error) for r in rows),
        "model_view_chars_median": int(statistics.median([r.model_view_chars for r in rows])) if rows else 0,
        "latency_ms_median": int(statistics.median([r.latency_ms for r in rows])) if rows else 0,
    }
    print(json.dumps(summary, ensure_ascii=False))
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(
            json.dumps({"summary": summary, "rows": [asdict(r) for r in rows]}, ensure_ascii=False, indent=1),
            encoding="utf-8",
        )
        print(f"written {args.out}")
    return 0


# ---------------------------------------------------------------------------
# live
# ---------------------------------------------------------------------------
def _call(base: str, path: str, payload: dict[str, object] | None = None, timeout: float = 30.0) -> object:
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(
        base + path,
        data=data,
        headers={"Content-Type": "application/json"} if data else {},
        method="POST" if data is not None else "GET",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read())


def _run_dir_for(users_root: Path, user: str, run_id: str) -> Path | None:
    candidate = users_root / user / "runs" / run_id
    return candidate if candidate.is_dir() else None


def _model_visible_tool_text(episode_path: Path) -> tuple[str, int, dict[str, int]]:
    """按 harness 的投影重算每条 tool_result 的模型视图，拼成一串；顺带数工具调用。"""
    from intelligence.services.episode_protocol import strip_hashes_for_model
    from intelligence.services.tool_observation_noise import prune_tool_observation
    from intelligence.services.tool_result_budget import budget_tool_observation

    try:
        data = json.loads(episode_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "", 0, {}
    events = data.get("events") if isinstance(data, dict) else data
    if not isinstance(events, list):
        return "", 0, {}
    seen: frozenset[str] = frozenset()
    chunks: list[str] = []
    tools: dict[str, int] = {}
    turns = 0
    for event in events:
        kind = event.get("kind")
        if kind == "model_turn":
            turns += 1
        if kind != "tool_result":
            continue
        payload = event.get("payload") or {}
        tools[str(payload.get("tool"))] = tools.get(str(payload.get("tool")), 0) + 1
        view = {k: v for k, v in payload.items() if k not in {"telemetry"}}
        try:
            pruned, seen = prune_tool_observation(view, seen_prose=seen)
            chunks.append(json.dumps(strip_hashes_for_model(budget_tool_observation(pruned)), ensure_ascii=False))
        except Exception:  # noqa: BLE001
            chunks.append(json.dumps(payload, ensure_ascii=False))
    return "\n".join(chunks), turns, tools


_CLARIFY_MARKERS = ("我还缺少一点信息", "你问的是", "请确认")
DEFAULT_CLARIFY_REPLY = "就按我原来的问题字面意思回答，用知识库里的材料。"


def _wait_assistant(base: str, conversation_id: str, user: str, *, after: int, deadline: float, poll: float) -> tuple[str, str, int]:
    """等第 ``after`` 条之后出现新的 assistant 消息；返回 (正文, run_id, 消息总数)。"""
    while time.monotonic() < deadline:
        time.sleep(poll)
        messages = _call(base, f"/api/conversations/{conversation_id}/messages?user={user}")
        items = messages.get("messages") if isinstance(messages, dict) else messages
        items = list(items or [])
        for message in items[after:]:
            if message.get("role") == "assistant" and str(message.get("content") or "").strip():
                return str(message.get("content")), str(message.get("run_id") or message.get("runId") or ""), len(items)
    return "", "", -1


def _looks_like_clarification(users_root: Path, user: str, run_id: str, answer: str) -> bool:
    run_dir = _run_dir_for(users_root, user, run_id) if run_id else None
    if run_dir is not None and (run_dir / "report.json").is_file():
        try:
            report = json.loads((run_dir / "report.json").read_text(encoding="utf-8"))
            if str(report.get("task_type") or "") == "clarify":
                return True
        except (OSError, json.JSONDecodeError):
            pass
    head = answer.strip()[:40]
    return any(marker in head for marker in _CLARIFY_MARKERS)


def cmd_live(args: argparse.Namespace) -> int:
    base = f"http://127.0.0.1:{args.port}"
    users_root = Path(args.users_root).expanduser()
    cases = load_cases(Path(args.set))
    if args.only:
        wanted = set(args.only.split(","))
        cases = [c for c in cases if str(c["case_id"]) in wanted]
    results: list[dict[str, object]] = []
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    for case in cases:
        case_id = str(case["case_id"])
        question = str(case["question"])
        phrases = [str(p) for p in case.get("key_phrases", [])]
        user = f"{args.user_prefix}-{case_id}"
        record: dict[str, object] = {"case_id": case_id, "question": question, "user": user}
        started = time.monotonic()
        try:
            conversation = _call(base, "/api/conversations", {"user": user, "title": question[:24]})
            conversation_id = conversation["conversation_id"]  # type: ignore[index]
            _call(
                base,
                f"/api/conversations/{conversation_id}/messages",
                {"user": user, "content": question, "skill_mode": args.skill_mode},
                timeout=60.0,
            )
            deadline = time.monotonic() + float(args.timeout)
            answer, run_id, seen = _wait_assistant(
                base, conversation_id, user, after=0, deadline=deadline, poll=float(args.poll_seconds)
            )
            record["clarified"] = False
            if answer and _looks_like_clarification(users_root, user, run_id, answer):
                # 澄清门（task_frame）先问一句再研究——真实用户会回一句，这里也回一句，
                # 用题目自带的 ``clarify``（不含答案短语），没有就用通用回复。
                record["clarified"] = True
                record["clarification"] = answer[:200]
                reply = str(case.get("clarify") or DEFAULT_CLARIFY_REPLY)
                _call(
                    base,
                    f"/api/conversations/{conversation_id}/messages",
                    {"user": user, "content": reply, "skill_mode": args.skill_mode},
                    timeout=60.0,
                )
                answer, run_id, seen = _wait_assistant(
                    base, conversation_id, user, after=max(seen, 0), deadline=deadline, poll=float(args.poll_seconds)
                )
            record["elapsed_s"] = round(time.monotonic() - started, 1)
            record["conversation_id"] = conversation_id
            record["answered"] = bool(answer)
            record["answer_chars"] = len(answer)
            record["phrase_in_answer"] = _phrase_hit(phrases, answer)
            run_dir = _run_dir_for(users_root, user, run_id) if run_id else None
            if run_dir is None:
                runs = sorted((users_root / user / "runs").glob("run_*"), key=lambda p: p.stat().st_mtime)
                run_dir = runs[-1] if runs else None
            record["run_dir"] = str(run_dir) if run_dir else ""
            if run_dir is not None:
                tool_text, turns, tools = _model_visible_tool_text(run_dir / "continuous-episode.json")
                record["phrase_in_model_view"] = _phrase_hit(phrases, tool_text)
                record["model_turns"] = turns
                record["tool_calls"] = tools
                report_path = run_dir / "report.json"
                if report_path.is_file():
                    try:
                        report = json.loads(report_path.read_text(encoding="utf-8"))
                        record["llm"] = report.get("llm")
                        record["metrics"] = {
                            k: v
                            for k, v in (report.get("metrics") or {}).items()
                            if k in {"judge_usage", "elapsed_seconds", "tool_calls", "status"}
                        }
                    except (OSError, json.JSONDecodeError):
                        pass
                answer_file = run_dir / "answer.md"
                if answer_file.is_file():
                    (out_dir / f"{case_id}.answer.md").write_text(answer_file.read_text(encoding="utf-8"), encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            record["error"] = f"{type(exc).__name__}: {exc}"[:300]
            record["elapsed_s"] = round(time.monotonic() - started, 1)
        results.append(record)
        print(json.dumps(record, ensure_ascii=False)[:400], flush=True)
        (out_dir / "live-results.json").write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    summary = {
        "cases": len(results),
        "answered": sum(bool(r.get("answered")) for r in results),
        "phrase_in_model_view": sum(bool(r.get("phrase_in_model_view")) for r in results),
        "phrase_in_answer": sum(bool(r.get("phrase_in_answer")) for r in results),
        "errors": sum(bool(r.get("error")) for r in results),
        "elapsed_s_median": statistics.median([float(r.get("elapsed_s") or 0) for r in results]) if results else 0,
    }
    print(json.dumps(summary, ensure_ascii=False))
    (out_dir / "live-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------
def cmd_report(args: argparse.Namespace) -> int:
    def load(path: str) -> dict[str, dict[str, object]]:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        rows = data.get("rows") if isinstance(data, dict) else data
        return {str(r["case_id"]): r for r in rows}

    left, right = load(args.baseline), load(args.treatment)
    keys = [k for k in ("candidate_recall", "phrase_in_raw_evidence", "phrase_in_model_view", "phrase_in_answer") if any(k in r for r in left.values())]
    print("| case | " + " | ".join(f"{k}(基线→本单)" for k in keys) + " | view_chars(基线→本单) |")
    print("|---|" + "---|" * (len(keys) + 1))
    totals = {k: [0, 0] for k in keys}
    for case_id in sorted(set(left) | set(right)):
        a, b = left.get(case_id, {}), right.get(case_id, {})
        cells = []
        for k in keys:
            va, vb = bool(a.get(k)), bool(b.get(k))
            totals[k][0] += va
            totals[k][1] += vb
            cells.append(f"{int(va)}→{int(vb)}")
        print(f"| {case_id} | " + " | ".join(cells) + f" | {a.get('model_view_chars', a.get('answer_chars', 0))}→{b.get('model_view_chars', b.get('answer_chars', 0))} |")
    print("| **合计** | " + " | ".join(f"{totals[k][0]}→{totals[k][1]}" for k in keys) + " | |")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    outline = sub.add_parser("outline")
    outline.add_argument("pages", nargs="+")
    outline.add_argument("--wiki", default=os.environ.get("KNOWLEDGE_WIKI", str(Path.home() / "knowledge-base-private" / "wiki")))
    outline.add_argument("--terms", nargs="*")
    outline.add_argument("--show", action="store_true")
    outline.set_defaults(func=cmd_outline)

    offline = sub.add_parser("offline")
    offline.add_argument("--set", default=str(DEFAULT_SET))
    offline.add_argument("--wiki", default=os.environ.get("KNOWLEDGE_WIKI", str(Path.home() / "knowledge-base-private" / "wiki")))
    offline.add_argument("--deep", choices=["on", "off"], default="on")
    offline.add_argument("--mode", default="hybrid")
    offline.add_argument("--timeout", type=float, default=120.0)
    offline.add_argument("--worker", action="store_true", help="常驻 worker（进程内单例，一次加载模型）")
    offline.add_argument("--prewarm-timeout", type=float, default=300.0, dest="prewarm_timeout")
    offline.add_argument("--out")
    offline.set_defaults(func=cmd_offline)

    live = sub.add_parser("live")
    live.add_argument("--set", default=str(DEFAULT_SET))
    live.add_argument("--port", type=int, required=True)
    live.add_argument("--users-root", required=True, dest="users_root")
    live.add_argument("--user-prefix", default="cap02", dest="user_prefix")
    live.add_argument("--skill-mode", default="manual", dest="skill_mode")
    live.add_argument("--timeout", type=float, default=900.0)
    live.add_argument("--poll-seconds", type=float, default=10.0, dest="poll_seconds")
    live.add_argument("--only")
    live.add_argument("--out", required=True)
    live.set_defaults(func=cmd_live)

    report = sub.add_parser("report")
    report.add_argument("--baseline", required=True)
    report.add_argument("--treatment", required=True)
    report.set_defaults(func=cmd_report)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
