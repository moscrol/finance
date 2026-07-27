"""验收台账：28 道题的进度只从这里生成，不从记忆里写。

三个子命令：
  board   读最近一次 run 记录，打印看板（题 / 期望 / 实测 / 通过 / 失败分类 / 证据路径）
  run     走用户真实点击的那条路径（POST /api/conversations/{id}/messages），落 trace
  freeze  冻结 codex / knevo 的参照答案快照（人工粘贴，禁止被测方自己生成）

设计取舍：
- **不内联评分逻辑。** 判定沿用 intelligence/eval/agent_eval.py 的确定性闸；这里只负责
  「跑真实路径 + 落证据 + 出看板」。分数是可复算的数，不是叙述。
- **trace 落成 JSONL 而不是接 OpenTelemetry。** 当前瓶颈是"用户看不到中间过程"，
  不是"查询不方便"；等题量上规模再换 Langfuse / OTel 这类带 UI 的方案。
- **参照快照必须外部冻结。** 被测方不得重新生成自己的基准，否则考生兼出题人。
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
CASES_PATH = REPO / "intelligence/eval/cases/acceptance_cases.json"
RUNS_DIR = REPO / "intelligence/eval/runs"
SNAPSHOT_DIR = REPO / "intelligence/eval/cases/reference_snapshots"
DEFAULT_BASE = "http://127.0.0.1:8799"
DEFAULT_USER = "linxiaoqi5111"


def load_cases() -> dict[str, Any]:
    return json.loads(CASES_PATH.read_text(encoding="utf-8"))


def _rel(path: Path) -> str:
    """相对仓库根显示；路径在仓库外时退回绝对路径而不是抛异常。"""
    try:
        return str(path.relative_to(REPO))
    except ValueError:
        return str(path)


@dataclass
class TurnTrace:
    """一次真实回答的完整轨迹 —— 用户不用问我，打开这个文件就能看到发生了什么。"""

    question: str
    answer: str | None = None
    tools_called: list[str] = field(default_factory=list)
    registry_tags: list[str] = field(default_factory=list)
    elapsed_s: float = 0.0
    status: str = "unknown"
    error: str | None = None
    raw_events: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class CaseRun:
    case_id: str
    tier: str
    turns: list[TurnTrace] = field(default_factory=list)
    blocked_reason: str | None = None


# --------------------------------------------------------------------------- #
# run —— 走用户真实点击的那条路径
# --------------------------------------------------------------------------- #
def _post(url: str, payload: dict[str, Any], timeout: float = 30.0) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8") or "{}")


def _get(url: str, timeout: float = 30.0) -> Any:
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8") or "{}")


def preflight(base: str) -> tuple[bool, str]:
    """部署接缝前置检查。跑不过就不许报进度 —— 这四道缝各自坑过一次。

    注意 /api/llm/config 当前恒定阻塞约 6s（疑似 Keychain 查询），所以 timeout
    必须给到 10s 以上，否则前置检查会因自身超时而误报『不可达』。
    """
    try:
        health = _get(f"{base}/api/health", timeout=10)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return False, f"服务不可达: {exc}"

    runtime = health.get("runtime") or {}
    agent_runtime = runtime.get("agent_runtime") or {}
    deps = health.get("dependencies") or {}
    revision = runtime.get("source_revision") or ""

    failed: list[str] = []
    if health.get("status") != "healthy":
        failed.append(f"status={health.get('status')}")
    if not runtime.get("finance_root"):
        failed.append("finance_root 缺失")
    if not revision:
        failed.append("source_revision 缺失")
    for dep in ("repo_root", "knowledge_wiki", "relations", "market_snapshot"):
        if deps.get(dep) is False:
            failed.append(f"依赖 {dep} 不可用")
    if agent_runtime.get("ready") is False:
        failed.append(
            f"agent_runtime 未就绪（backend={agent_runtime.get('backend')}, "
            f"reason={agent_runtime.get('reason')}）"
        )

    try:
        cfg = _get(f"{base}/api/llm/config", timeout=15)
        if cfg.get("ready") is False:
            failed.append("llm_config.ready=false（BYOK 凭据未就绪）")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        failed.append(f"llm/config 不可达: {type(exc).__name__}")

    if failed:
        return False, "; ".join(failed)
    return True, f"revision={revision[:8]} backend={agent_runtime.get('backend')}"


def ask_once(base: str, user: str, question: str, timeout: float) -> TurnTrace:
    """真实提问一次并轮询到终态。返回可复核的轨迹。"""
    trace = TurnTrace(question=question)
    started = time.monotonic()
    try:
        conv = _post(f"{base}/api/conversations", {"title": "acceptance", "user": user})
        conv_id = conv.get("conversation_id") or conv.get("id")
        if not conv_id:
            trace.status = "error"
            trace.error = f"未拿到 conversation_id: {conv}"
            return trace
        _post(
            f"{base}/api/conversations/{conv_id}/messages",
            {"content": question, "skill_mode": "auto", "user": user},
        )
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            time.sleep(2.0)
            msgs = _get(f"{base}/api/conversations/{conv_id}/messages?user={user}")
            items = msgs if isinstance(msgs, list) else msgs.get("messages", [])
            assistant = [m for m in items if m.get("role") == "assistant"]
            if not assistant:
                continue
            last = assistant[-1]
            if last.get("status") in {"pending", "running", None}:
                continue
            trace.answer = last.get("content")
            trace.status = last.get("status") or "unknown"
            trace.tools_called = list(last.get("tools_called") or [])
            trace.registry_tags = list(last.get("registry_tags") or [])
            trace.raw_events = list(last.get("events") or [])
            break
        else:
            trace.status = "timeout"
            trace.error = f"超过 {timeout}s 未返回终态"
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        trace.status = "error"
        trace.error = str(exc)
    trace.elapsed_s = round(time.monotonic() - started, 1)
    return trace


def cmd_run(args: argparse.Namespace) -> int:
    doc = load_cases()
    ok, detail = preflight(args.base)
    if not ok and not args.force:
        print(f"❌ 前置检查未通过：{detail}")
        print("   这是部署接缝问题，不是题目失败。修好再跑，或 --force 强跑留证据。")
        return 2
    print(f"✅ 前置检查：{detail}" if ok else f"⚠️  强跑（前置未过）：{detail}")

    selected = [
        c
        for c in doc["cases"]
        if (not args.tier or c["tier"] == args.tier)
        and (not args.case or c["id"] in args.case)
    ]
    print(f"选中 {len(selected)} / {len(doc['cases'])} 道题\n")
    runs: list[CaseRun] = []
    for i, case in enumerate(selected, 1):
        cr = CaseRun(case_id=case["id"], tier=case["tier"])
        print(f"[{i}/{len(selected)}] {case['id']} … ", end="", flush=True)
        questions = [case["query"], *case.get("followups", [])]
        for q in questions:
            t = ask_once(args.base, args.user, q, args.timeout)
            cr.turns.append(t)
            if t.status in {"error", "timeout"}:
                break
        head = cr.turns[0] if cr.turns else None
        print(
            f"{head.status if head else 'n/a'}  {head.elapsed_s if head else 0}s  "
            f"tools={len(head.tools_called) if head else 0}"
        )
        runs.append(cr)

    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = RUNS_DIR / f"{stamp}.json"
    out.write_text(
        json.dumps(
            {
                "generated_at": stamp,
                "base": args.base,
                "preflight_ok": ok,
                "preflight_detail": detail,
                "cases": [asdict(r) for r in runs],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\ntrace 已落盘：{_rel(out)}")
    print("看板：python3 -m intelligence.eval.acceptance board")
    return 0


# --------------------------------------------------------------------------- #
# board —— 进度只从这里生成
# --------------------------------------------------------------------------- #
def latest_run() -> Path | None:
    if not RUNS_DIR.exists():
        return None
    runs = sorted(RUNS_DIR.glob("*.json"))
    return runs[-1] if runs else None


def cmd_board(args: argparse.Namespace) -> int:
    doc = load_cases()
    cases = doc["cases"]
    run_path = latest_run()
    by_id: dict[str, dict[str, Any]] = {}
    header_note = "尚无真实运行记录"
    if run_path:
        rec = json.loads(run_path.read_text(encoding="utf-8"))
        by_id = {c["case_id"]: c for c in rec.get("cases", [])}
        header_note = (
            f"最近一次真实运行 {run_path.stem}"
            f"（前置检查{'通过' if rec.get('preflight_ok') else '未过'}）"
        )

    print(f"# 验收看板 · {header_note}\n")
    print("| 题 | 组 | 状态 | 耗时 | 工具数 | 失败分类 |")
    print("|---|---|---|---|---|---|")
    tally: dict[str, int] = {"passed": 0, "failed": 0, "not_run": 0}
    for c in cases:
        r = by_id.get(c["id"])
        if not r or not r.get("turns"):
            tally["not_run"] += 1
            print(f"| {c['id']} | {c['tier']} | ⬜ 未跑 | — | — | — |")
            continue
        t0 = r["turns"][0]
        status = t0.get("status")
        # 注意：这里只报「真实运行是否拿到答案」。是否算通过要过 agent_eval 的
        # 确定性闸 + 人工盲比参照快照，看板不自作判断。
        if status == "complete":
            mark, cls = "🟡 有答案待判", ""
        else:
            tally["failed"] += 1
            mark, cls = "🔴 未产出", classify_failure(t0)
            print(
                f"| {c['id']} | {c['tier']} | {mark} | {t0.get('elapsed_s')}s | "
                f"{len(t0.get('tools_called') or [])} | {cls} |"
            )
            continue
        print(
            f"| {c['id']} | {c['tier']} | {mark} | {t0.get('elapsed_s')}s | "
            f"{len(t0.get('tools_called') or [])} | {cls} |"
        )

    total = len(cases)
    print(
        f"\n**口径**：{total} 道题里，未跑 {tally['not_run']}、"
        f"未产出 {tally['failed']}。通过数须经 agent_eval 闸 + 盲比后回填，"
        "看板不自己判通过。"
    )
    snaps = list(SNAPSHOT_DIR.glob("*.json")) if SNAPSHOT_DIR.exists() else []
    print(f"**参照快照**：已冻结 {len(snaps)} / {total} 道（codex/knevo）")
    return 0


def classify_failure(turn: dict[str, Any]) -> str:
    """把失败分成『部署接缝』和『业务质量』—— 前者不该算题目分数。"""
    err = (turn.get("error") or "").lower()
    status = turn.get("status")
    if status == "timeout":
        return "接缝:超时"
    if "urlopen" in err or "refused" in err or "conversation_id" in err:
        return "接缝:服务/路由"
    if "api_key" in err or "missing" in err or "credential" in err:
        return "接缝:凭据"
    if "schema" in err or "400" in err or "invalid" in err:
        return "接缝:协议/Schema"
    if status == "error":
        return "接缝:未分类"
    return "业务质量"


# --------------------------------------------------------------------------- #
# freeze —— 参照快照必须外部冻结
# --------------------------------------------------------------------------- #
def cmd_freeze(args: argparse.Namespace) -> int:
    doc = load_cases()
    ids = {c["id"] for c in doc["cases"]}
    if args.case_id not in ids:
        print(f"❌ 未知题号 {args.case_id}。可用：{sorted(ids)}")
        return 2
    if args.agent not in doc["reference_agents"]:
        print(f"❌ agent 必须是 {doc['reference_agents']} 之一")
        return 2
    text = Path(args.answer_file).read_text(encoding="utf-8")
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    out = SNAPSHOT_DIR / f"{args.case_id}.{args.agent}.json"
    if out.exists() and not args.overwrite:
        print(
            f"❌ {out.name} 已存在。参照快照一旦冻结不应重生成；确需覆盖加 --overwrite"
        )
        return 2
    out.write_text(
        json.dumps(
            {
                "case_id": args.case_id,
                "agent": args.agent,
                "frozen_at": datetime.now(timezone.utc).isoformat(),
                "answer": text,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"✅ 已冻结 {_rel(out)}（{len(text)} 字）")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="acceptance", description="28 道验收题台账")
    sub = p.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("board", help="打印看板（进度唯一来源）")
    b.set_defaults(func=cmd_board)

    r = sub.add_parser("run", help="走真实路径跑题并落 trace")
    r.add_argument("--base", default=DEFAULT_BASE)
    r.add_argument("--user", default=DEFAULT_USER)
    r.add_argument("--tier", choices=["high_freq", "mid_freq", "long_tail"])
    r.add_argument("--case", action="append", help="只跑指定题号，可重复")
    r.add_argument("--timeout", type=float, default=300.0)
    r.add_argument("--force", action="store_true", help="前置检查未过也强跑")
    r.set_defaults(func=cmd_run)

    f = sub.add_parser("freeze", help="冻结 codex/knevo 参照答案")
    f.add_argument("case_id")
    f.add_argument("agent")
    f.add_argument("answer_file")
    f.add_argument("--overwrite", action="store_true")
    f.set_defaults(func=cmd_freeze)

    args = p.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
