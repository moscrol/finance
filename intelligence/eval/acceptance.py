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
import hashlib
import json
import sys
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from intelligence.eval.acceptance_verdict import (
    ExperienceState,
    OperationalState,
    VerdictState,
    compile_case_contract,
    evaluate_case,
    load_verdict_overlay,
)

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
    """一次真实回答的完整轨迹 —— 用户不用问我，打开这个文件就能看到发生了什么。

    字段名对齐 runtime 真实返回的形状，别自创：
    - 消息体给 ``invoked_skill_ids`` / ``citations`` / ``degrades``，**没有**
      ``tools_called``。早先版本读 ``tools_called``，于是每条轨迹的工具信息
      恒为空 —— 看板显示 tools=0 却不是真没调工具，是探针探错了地方。
    - 真正能区分「取到证据后回答」和「取不到证据而降级」的是
      ``/api/runs/{run_id}/context`` 的 ``evidence[]``：C1 绑定 6 条证据正常
      作答，A4 绑定 0 条直接降级拒答。这是判空答/假拒答的唯一可靠信号。
    """

    question: str
    answer: str | None = None
    run_id: str | None = None
    invoked_skill_ids: list[str] = field(default_factory=list)
    citations: list[dict[str, Any]] = field(default_factory=list)
    degrades: list[str] = field(default_factory=list)
    evidence_bound: int = 0
    evidence: list[dict[str, Any]] = field(default_factory=list)
    trace_steps: list[str] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)
    elapsed_s: float = 0.0
    status: str = "unknown"
    error: str | None = None


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


def _fill_run_detail(base: str, trace: TurnTrace) -> None:
    """补 run 级证据绑定与步骤。取不到不算失败 —— 答案本身已经拿到了。"""
    if not trace.run_id:
        return
    try:
        ctx = _get(f"{base}/api/runs/{trace.run_id}/context", timeout=15)
    except (urllib.error.URLError, TimeoutError, OSError):
        ctx = {}
    evidence = ctx.get("evidence") or []
    trace.evidence = list(evidence)
    trace.evidence_bound = sum(
        1 for e in evidence if isinstance(e, dict) and e.get("status") == "hit"
    )
    trace.gaps = list(ctx.get("gaps") or [])
    try:
        steps = _get(f"{base}/api/runs/{trace.run_id}/trace", timeout=15)
    except (urllib.error.URLError, TimeoutError, OSError):
        steps = []
    if isinstance(steps, list):
        trace.trace_steps = [
            str(s.get("name")) for s in steps if isinstance(s, dict) and s.get("name")
        ]


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
            trace.run_id = last.get("run_id")
            trace.invoked_skill_ids = list(last.get("invoked_skill_ids") or [])
            trace.citations = list(last.get("citations") or [])
            trace.degrades = list(last.get("degrades") or [])
            _fill_run_detail(base, trace)
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
        degraded = " ⚠降级" if head and head.degrades else ""
        print(
            f"{head.status if head else 'n/a'}  {head.elapsed_s if head else 0}s  "
            f"证据={head.evidence_bound if head else 0}{degraded}"
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

    overlay = load_verdict_overlay()
    print(f"# 验收看板 · {header_note}\n")
    print("| 题 | 组 | 运行 | 真值 | 体验 | 耗时 | 绑定证据 | 说明 |")
    print("|---|---|---|---|---|---:|---:|---|")
    operational_tally = {state: 0 for state in OperationalState}
    truth_tally = {state: 0 for state in VerdictState}
    experience_tally = {state: 0 for state in ExperienceState}
    operational_labels = {
        OperationalState.NOT_RUN: "⬜ 未跑",
        OperationalState.BLOCKED: "⚫ 阻塞",
        OperationalState.FAILED: "🔴 未产出",
        OperationalState.DEGRADED: "🟠 降级完成",
        OperationalState.COMPLETED: "🟢 完成",
    }
    truth_labels = {
        VerdictState.NOT_RUN: "—",
        VerdictState.PASS: "✅ 通过",
        VerdictState.FAIL: "❌ 失败",
        VerdictState.UNJUDGEABLE: "❔ 不可判",
    }
    experience_labels = {
        ExperienceState.UNLABELED: "未标注",
        ExperienceState.LABELED: "已盲标",
        ExperienceState.INELIGIBLE: "不适用",
    }
    for c in cases:
        r = by_id.get(c["id"])
        contract = compile_case_contract(c, overlay[c["id"]])
        verdict = evaluate_case(contract, r)
        operational_tally[verdict.operational.state] += 1
        truth_tally[verdict.truth.state] += 1
        experience_tally[verdict.experience.state] += 1
        t0 = (r.get("turns") or [None])[0] if r else None
        detail = ""
        if verdict.truth.state is VerdictState.FAIL:
            failures = [
                rule.reason
                for rule in verdict.truth.rules
                if rule.state is VerdictState.FAIL
            ]
            detail = failures[0] if failures else "deterministic truth rule failed"
        elif verdict.truth.state is VerdictState.UNJUDGEABLE:
            pending = [
                rule.reason
                for rule in verdict.truth.rules
                if rule.state is VerdictState.UNJUDGEABLE
            ]
            detail = pending[0] if pending else verdict.operational.reason
        elif verdict.operational.state in {
            OperationalState.BLOCKED,
            OperationalState.FAILED,
        }:
            detail = verdict.operational.reason
        print(
            f"| {c['id']} | {c['tier']} | "
            f"{operational_labels[verdict.operational.state]} | "
            f"{truth_labels[verdict.truth.state]} | "
            f"{experience_labels[verdict.experience.state]} | "
            f"{(t0 or {}).get('elapsed_s', '—')}"
            f"{'s' if t0 else ''} | {(t0 or {}).get('evidence_bound') or 0 if t0 else '—'} | "
            f"{detail} |"
        )

    total = len(cases)
    completed_count = (
        operational_tally[OperationalState.COMPLETED]
        + operational_tally[OperationalState.DEGRADED]
    )
    print(
        f"\n**运行口径**：{total} 道题里，未跑 "
        f"{operational_tally[OperationalState.NOT_RUN]}、阻塞 "
        f"{operational_tally[OperationalState.BLOCKED]}、未产出 "
        f"{operational_tally[OperationalState.FAILED]}、降级完成 "
        f"{operational_tally[OperationalState.DEGRADED]}、正常完成 "
        f"{operational_tally[OperationalState.COMPLETED]}（完成合计 {completed_count}）。"
    )
    judged = truth_tally[VerdictState.PASS] + truth_tally[VerdictState.FAIL]
    rate_note = (
        f"可判子集通过率 {truth_tally[VerdictState.PASS]}/{judged}"
        if judged
        else "尚无可判子集通过率"
    )
    print(
        f"**真值口径**：通过 {truth_tally[VerdictState.PASS]}、失败 "
        f"{truth_tally[VerdictState.FAIL]}、不可判 "
        f"{truth_tally[VerdictState.UNJUDGEABLE]}、未跑 "
        f"{truth_tally[VerdictState.NOT_RUN]}；{rate_note}（不是 28 题产品通过率）。"
    )
    print(
        f"**体验口径**：已盲标 {experience_tally[ExperienceState.LABELED]}、"
        f"未标注 {experience_tally[ExperienceState.UNLABELED]}、"
        f"不适用 {experience_tally[ExperienceState.INELIGIBLE]}。"
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
    if turn.get("degrades") and not (turn.get("evidence_bound") or 0):
        # 服务健康、模型答了，但一条证据都没绑上就降级 —— 这是检索/绑定的业务
        # 缺陷（可能是假拒答），不是部署接缝，别混进接缝账里当"环境没配好"。
        return "业务质量:零证据降级"
    return "业务质量"


# --------------------------------------------------------------------------- #
# freeze —— 参照快照必须外部冻结
# --------------------------------------------------------------------------- #
def cmd_freeze(args: argparse.Namespace) -> int:
    """冻结外部参照答案。

    ``via`` 必填：参照答案的价值全在来源可追溯。codex 走
    ``codex exec -m gpt-5.5``（与 dual_blind_flows.sh 同一条路）；knevo 有两条路 ——
    ``manual_paste``（人工转贴，有转写损耗、可能丢工具轨迹）与 ``cdp_readback``
    （CDP 驱动用户自己已登录的 Chrome，读 /api/conversations/{id} 的 transcript）。
    后者保真度更高且带工具调用轨迹，但**必须记住答案仍是用户账号里人工提问产生的**，
    不是我们自动跑的。半年后回看快照，必须能分清"这是机器跑的"还是"这是人问的"、
    以及问的是哪一天 —— 否则基准不可复核。

    ``answer_sha256`` 是防篡改锚：冻结后任何改动都会让哈希对不上。
    ``--meta-file`` 收 JSON，落到 ``source_meta``：cdp_readback 用它存会话 id、
    原始提问、工具调用轨迹 —— 工具轨迹能和题目的 expect_tools 直接对照，
    是"它怎么答出来的"而不只是"它答了什么"。
    """
    doc = load_cases()
    ids = {c["id"] for c in doc["cases"]}
    if args.case_id not in ids:
        print(f"❌ 未知题号 {args.case_id}。可用：{sorted(ids)}")
        return 2
    if args.agent not in doc["reference_agents"]:
        print(f"❌ agent 必须是 {doc['reference_agents']} 之一")
        return 2
    if args.answer_file == "-":
        text = sys.stdin.read()
    else:
        text = Path(args.answer_file).read_text(encoding="utf-8")
    if not text.strip():
        print("❌ 答案为空，拒绝冻结")
        return 2
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    out = SNAPSHOT_DIR / f"{args.case_id}.{args.agent}.json"
    if out.exists() and not args.overwrite:
        print(
            f"❌ {out.name} 已存在。参照快照一旦冻结不应重生成；确需覆盖加 --overwrite"
        )
        return 2
    meta = None
    if getattr(args, "meta_file", None):
        meta = json.loads(Path(args.meta_file).read_text(encoding="utf-8"))
    out.write_text(
        json.dumps(
            {
                "case_id": args.case_id,
                "agent": args.agent,
                "frozen_at": datetime.now(timezone.utc).isoformat(),
                "via": args.via,
                "asked_at": args.asked_at,
                "answer_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "source_meta": meta,
                "answer": text,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"✅ 已冻结 {_rel(out)}（{len(text)} 字，via={args.via}）")
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
    f.add_argument("answer_file", help="答案文件路径；写 - 表示从 stdin 读")
    f.add_argument(
        "--via",
        required=True,
        choices=["manual_paste", "cdp_readback", "codex_exec", "cli"],
        help=(
            "来源：manual_paste=人工转贴；cdp_readback=CDP 读用户已登录 Chrome 的"
            "会话 transcript（保真、带工具轨迹，仍是人工提问）；codex_exec=codex exec 自动跑"
        ),
    )
    f.add_argument("--asked-at", help="实际提问日期 YYYY-MM-DD（与题目锚定日可能不同）")
    f.add_argument("--meta-file", help="JSON 文件，落到 source_meta（会话 id / 原始提问 / 工具轨迹）")
    f.add_argument("--overwrite", action="store_true")
    f.set_defaults(func=cmd_freeze)

    args = p.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
