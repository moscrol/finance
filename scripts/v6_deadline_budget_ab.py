#!/usr/bin/env python3
"""V6 deadline 预算分臂实验 harness（R-20260821-18 / spec §V6）。

本脚本只出实验读数，不改生产 timeout / 预算默认值。

分臂：
    control     打生产 8792（现状，零覆盖）
    reserve60   候选①：独立 sidecar + 进程内影子（成稿轮 planning 地板 60s）

影子机制（论证见报告）：双实例 sidecar，不写环境变量进 8792，
不改 ``_BALANCED_SYNTHESIS_RESERVE`` / T / ``_REPAIR_SECONDS_CAP``。
候选①把 ``MIN_PLANNING_TURN_SECONDS`` 从 8 抬到 60——planning 授窗
低于 60s 就进 finalize，成稿轮走 ``synthesis_timeout``（含 60s reserve），
而不是 ``stage_timeout = remaining−60`` 的残值。

探针字段是 ``user`` 不是 ``user_id``（spec 纪律 5）。
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import socket
import statistics
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

PROBE_USER = "probe-v6-0821"
CONTROL_PORT = 8792
CANDIDATE_PORT_DEFAULT = 8803
RESERVED_PORTS = frozenset({8792, 8793, 8795, 8799, 8801})
CANDIDATE1_PLANNING_FLOOR = 60.0
PRODUCTION_PLANNING_FLOOR = 8.0
MIN_N_PER_ARM = 50
MODEL_FINISH_LIFT_PP = 15.0
POLL_SECONDS = 10
DEFAULT_PROBE_TIMEOUT = 720
DEFAULT_USERS_DIR = Path.home() / ".local/share/finance-workbench/users"
RUNTIME_ROOT = Path.home() / ".finance-runtime" / "v6-deadline-budget-ab"
DEFAULT_LEDGER = RUNTIME_ROOT / "trials.jsonl"
DEFAULT_PYTHON = (
    Path.home() / "finance-workspace-private" / ".venv-workbench" / "bin" / "python"
)
DEFAULT_LAUNCHER = Path.home() / ".local/bin" / "start-finance-workbench"
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))

ARMS = ("control", "reserve60")

# 发酵/题材题：走 conversations → continuous episode，不走 /api/runs ask 泳道。
QUESTION_POOL = (
    "CXO概念这波是怎么发酵到 2026-08-20 的",
    "减肥药板块最近的发酵链路怎么看",
    "钙钛矿电池这条线到 2026-08-18 走到哪了",
    "液冷概念当前处于发酵期还是共识期",
    "固态电池主线最近有没有走弱",
    "PCB概念到 2026-08-07 的双红和成交怎么读",
    "创新药这条线近两周的主线位置变了吗",
    "AI算力题材 8 月之后还在主线名单里吗",
    "机器人概念最近是补涨还是主升",
    "商业航天这块的发酵证据到哪一步了",
)

_DEGRADE_MARKERS = (
    "URLError",
    "已降级为模板",
    "Grounded Presenter自然语言合成未通过门禁",
    "LLM 合成失败",
)


def _as_dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _events(episode: dict[str, Any]) -> list[dict[str, Any]]:
    raw = episode.get("events") or []
    return [item for item in raw if isinstance(item, dict)]


def _finish_payloads(episode: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        _as_dict(item.get("payload"))
        for item in _events(episode)
        if item.get("kind") == "finish"
    ]


def inspect_episode(episode: dict[str, Any] | None) -> dict[str, Any]:
    """从 continuous-episode.json 抽 §V6 五项指标。缺字段报不可判，不报 0。"""

    if not episode:
        return {
            "reached_episode": False,
            "stop_reason": None,
            "stop_reason_status": "unjudgeable",
            "model_finish": None,
            "carried_draft_chars": None,
            "carried_status": "unjudgeable",
            "carried_positive": None,
            "used_repair": False,
            "repair_status": "unjudgeable",
            "answer_chars": None,
            "answer_status": "unjudgeable",
            "judge_status": None,
            "judge_status_status": "unjudgeable",
            "tool_events": 0,
            "model_turns": 0,
        }

    events = _events(episode)
    finishes = _finish_payloads(episode)
    first_finish = finishes[0] if finishes else {}
    stop_reason = first_finish.get("stop_reason")
    stop_ok = isinstance(stop_reason, str) and bool(stop_reason)
    carried = first_finish.get("carried_draft_chars")
    carried_ok = isinstance(carried, (int, float))
    used_repair = any(item.get("kind") == "repair_reentry" for item in events)
    draft = _as_dict(episode.get("outcome")).get("draft")
    draft_ok = isinstance(draft, str)
    judge = _as_dict(episode.get("semantic_verifier")).get("judge_status")
    judge_ok = isinstance(judge, str) and bool(judge)
    tool_events = sum(
        1 for item in events if item.get("kind") in {"tool_request", "tool_result"}
    )
    model_turns = sum(1 for item in events if item.get("kind") == "model_turn")
    # 走到 episode = 有成稿轮 + finish。工具调用不是必要条件：
    # 候选①提早 finalize 时可能只靠 prefetch、零 tool_request。
    # URLError 降级模板没有 continuous-episode.json，进不了这里。
    reached = model_turns > 0 and stop_ok
    return {
        "reached_episode": reached,
        "stop_reason": stop_reason if stop_ok else None,
        "stop_reason_status": "ok" if stop_ok else "unjudgeable",
        "model_finish": (stop_reason == "model_finish") if stop_ok else None,
        "carried_draft_chars": int(carried) if carried_ok else None,
        "carried_status": "ok" if carried_ok else "unjudgeable",
        "carried_positive": (int(carried) > 0) if carried_ok else None,
        "used_repair": used_repair,
        "repair_status": "ok",
        "answer_chars": len(draft) if draft_ok else None,
        "answer_status": "ok" if draft_ok else "unjudgeable",
        "judge_status": judge if judge_ok else None,
        "judge_status_status": "ok" if judge_ok else "unjudgeable",
        "tool_events": tool_events,
        "model_turns": model_turns,
    }


def load_episode(run_dir: Path) -> dict[str, Any] | None:
    path = run_dir / "continuous-episode.json"
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def answer_looks_degraded(text: str) -> bool:
    return any(marker in text for marker in _DEGRADE_MARKERS)


def run_dir_for(users_dir: Path, user: str, run_id: str) -> Path:
    return users_dir / user / "runs" / run_id


def aggregate_arm(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """聚合一臂读数。分母只计可判行；n 是实际试次数。"""

    n = len(rows)
    mf_rows = [row for row in rows if row.get("model_finish") is not None]
    carried_rows = [row for row in rows if row.get("carried_positive") is not None]
    answer_rows = [
        row for row in rows if isinstance(row.get("answer_chars"), int)
    ]
    repair_rows = [row for row in rows if row.get("repair_status") == "ok"]
    judge_rows = [row for row in rows if row.get("judge_status_status") == "ok"]
    model_finish_rate = (
        sum(1 for row in mf_rows if row["model_finish"]) / len(mf_rows)
        if mf_rows
        else None
    )
    carried_positive_rate = (
        sum(1 for row in carried_rows if row["carried_positive"]) / len(carried_rows)
        if carried_rows
        else None
    )
    repair_rate = (
        sum(1 for row in repair_rows if row["used_repair"]) / len(repair_rows)
        if repair_rows
        else None
    )
    lengths = [int(row["answer_chars"]) for row in answer_rows]
    return {
        "n": n,
        "n_reached_episode": sum(1 for row in rows if row.get("reached_episode")),
        "n_model_finish_judgeable": len(mf_rows),
        "model_finish_rate": model_finish_rate,
        "n_carried_judgeable": len(carried_rows),
        "carried_positive_rate": carried_positive_rate,
        "n_repair_judgeable": len(repair_rows),
        "repair_dependency_rate": repair_rate,
        "n_answer_judgeable": len(answer_rows),
        "answer_chars_median": (
            float(statistics.median(lengths)) if lengths else None
        ),
        "answer_chars_mean": (
            float(statistics.mean(lengths)) if lengths else None
        ),
        "judge_status_n": len(judge_rows),
        "judge_status_dist": dict(Counter(row["judge_status"] for row in judge_rows)),
    }


def compare_arms(
    control: dict[str, Any],
    candidate: dict[str, Any],
    *,
    min_n: int = MIN_N_PER_ARM,
    lift_pp: float = MODEL_FINISH_LIFT_PP,
) -> dict[str, Any]:
    """预注册判据。n<50 不得下达标/未达标以外的样本量结论。"""

    n_ok = int(control.get("n") or 0) >= min_n and int(candidate.get("n") or 0) >= min_n
    if not n_ok:
        return {
            "verdict": "进行中/未达标样本量",
            "reason": (
                f"对照 n={control.get('n')} 候选 n={candidate.get('n')}，"
                f"预注册每臂 n≥{min_n}"
            ),
            "model_finish_lift_pp": None,
            "answer_length_not_down": None,
        }
    ctrl_mf = control.get("model_finish_rate")
    cand_mf = candidate.get("model_finish_rate")
    ctrl_len = control.get("answer_chars_median")
    cand_len = candidate.get("answer_chars_median")
    if ctrl_mf is None or cand_mf is None:
        return {
            "verdict": "进行中/未达标样本量",
            "reason": "model_finish 率不可判（缺 stop_reason）",
            "model_finish_lift_pp": None,
            "answer_length_not_down": None,
        }
    lift_pp_value = (float(cand_mf) - float(ctrl_mf)) * 100.0
    length_ok = (
        ctrl_len is None or cand_len is None or float(cand_len) >= float(ctrl_len)
    )
    if lift_pp_value >= lift_pp and length_ok and ctrl_len is not None:
        verdict = "达标"
        reason = (
            f"候选 model_finish 较对照 +{lift_pp_value:.1f}pp，"
            f"答案长度中位数 {cand_len} ≥ 对照 {ctrl_len}"
        )
    else:
        verdict = "未达标"
        missing = []
        if lift_pp_value < lift_pp:
            missing.append(f"model_finish 提升 {lift_pp_value:.1f}pp < {lift_pp}pp")
        if not length_ok:
            missing.append(f"答案长度下降（候选 {cand_len} < 对照 {ctrl_len}）")
        if ctrl_len is None or cand_len is None:
            missing.append("答案长度不可判")
        reason = "；".join(missing) or "未过预注册门槛"
    return {
        "verdict": verdict,
        "reason": reason,
        "model_finish_lift_pp": lift_pp_value,
        "answer_length_not_down": length_ok,
    }


def install_candidate1_shadow() -> float:
    """只在候选 sidecar 进程里调用。生产 8792 不 import 本函数。"""

    from intelligence.runtime import agent_episode as episode_mod

    previous = float(episode_mod.MIN_PLANNING_TURN_SECONDS)
    episode_mod.MIN_PLANNING_TURN_SECONDS = CANDIDATE1_PLANNING_FLOOR
    return previous


def restore_planning_floor(value: float) -> None:
    from intelligence.runtime import agent_episode as episode_mod

    episode_mod.MIN_PLANNING_TURN_SECONDS = float(value)


def port_is_listening(port: int, host: str = "127.0.0.1") -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(0.2)
    try:
        return sock.connect_ex((host, port)) == 0
    finally:
        sock.close()


def _request_json(
    method: str,
    url: str,
    *,
    payload: dict[str, Any] | None = None,
    timeout: float = 30,
) -> Any:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    with _OPENER.open(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def health(port: int) -> dict[str, Any]:
    payload = _request_json("GET", f"http://127.0.0.1:{port}/api/health", timeout=5)
    return payload if isinstance(payload, dict) else {}


def post_conversation_probe(
    *,
    port: int,
    user: str,
    question: str,
    timeout: float = DEFAULT_PROBE_TIMEOUT,
    skill_mode: str = "auto",
) -> dict[str, Any]:
    """POST /api/conversations → /messages，字段名钉死 ``user``。"""

    base = f"http://127.0.0.1:{port}"
    created = _request_json(
        "POST",
        f"{base}/api/conversations",
        payload={"user": user, "title": f"v6 {question[:20]}"},
        timeout=30,
    )
    if not isinstance(created, dict) or not created.get("conversation_id"):
        raise RuntimeError(f"create conversation failed: {created!r}")
    conversation_id = str(created["conversation_id"])
    posted = _request_json(
        "POST",
        f"{base}/api/conversations/{conversation_id}/messages",
        payload={"content": question, "skill_mode": skill_mode, "user": user},
        timeout=30,
    )
    if not isinstance(posted, dict) or not posted.get("run_id"):
        raise RuntimeError(f"post message failed: {posted!r}")
    run_id = str(posted["run_id"])
    deadline = time.monotonic() + timeout
    last_answer = ""
    last_status = ""
    while time.monotonic() < deadline:
        time.sleep(POLL_SECONDS)
        try:
            run = _request_json(
                "GET",
                f"{base}/api/runs/{run_id}?user={user}",
                timeout=15,
            )
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            continue
        if not isinstance(run, dict):
            continue
        last_status = str(run.get("status") or "")
        if last_status in {"completed", "failed", "cancelled"}:
            try:
                messages = _request_json(
                    "GET",
                    f"{base}/api/conversations/{conversation_id}/messages?user={user}",
                    timeout=15,
                )
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
                messages = []
            items = (
                messages
                if isinstance(messages, list)
                else _as_dict(messages).get("messages") or []
            )
            for message in items:
                if not isinstance(message, dict):
                    continue
                if message.get("role") == "assistant":
                    last_answer = str(message.get("content") or "")
            return {
                "conversation_id": conversation_id,
                "run_id": run_id,
                "status": last_status,
                "answer": last_answer,
                "timed_out": False,
            }
    return {
        "conversation_id": conversation_id,
        "run_id": run_id,
        "status": last_status or "timeout",
        "answer": last_answer,
        "timed_out": True,
    }


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            rows.append(item)
    return rows


def score_trial(
    *,
    users_dir: Path,
    user: str,
    run_id: str,
    public_answer: str = "",
) -> dict[str, Any]:
    run_dir = run_dir_for(users_dir, user, run_id)
    episode = load_episode(run_dir)
    metrics = inspect_episode(episode)
    metrics["run_id"] = run_id
    metrics["run_dir"] = str(run_dir)
    metrics["has_episode_file"] = episode is not None
    metrics["public_answer_chars"] = len(public_answer)
    metrics["public_degraded"] = answer_looks_degraded(public_answer)
    if episode is None and public_answer:
        metrics["reached_episode"] = False
    return metrics


def sidecar_zsh(*, port: int, repo_root: Path, users_dir: Path, python: Path) -> str:
    """独立 sidecar：源 launcher 只取 export，不执行生产 uvicorn。

    不检查 ``/tmp/finance-8792-live.lock``——那把锁是保护 8792 不被第二份
    生产实例顶掉，不是禁止旁路实验口。本进程绑定非保留端口。
    """

    launcher = shlex.quote(str(DEFAULT_LAUNCHER))
    repo = shlex.quote(str(repo_root))
    users = shlex.quote(str(users_dir))
    py = shlex.quote(str(python))
    return f"""
set -euo pipefail
set -a
if [[ -f {launcher} ]]; then
  . <(grep '^export ' {launcher})
fi
set +a
export WORKBENCH_REPO_ROOT={repo}
export PYTHONPATH={repo}
export FORESIGHT_USERS_DIR={users}
export FORESIGHT_USER={PROBE_USER}
export V6_DEADLINE_SHADOW=reserve60
export V6_SIDECAR_PORT={int(port)}
mkdir -p {users}
cd {repo}
exec {py} -c 'from scripts.v6_deadline_budget_ab import sidecar_entry; sidecar_entry()'
""".strip()


def sidecar_entry() -> None:
    previous = install_candidate1_shadow()
    port = int(os.environ.get("V6_SIDECAR_PORT") or CANDIDATE_PORT_DEFAULT)
    if port in RESERVED_PORTS:
        raise SystemExit(f"sidecar refused reserved port {port}")
    import uvicorn

    sys.stderr.write(
        f"v6 shadow reserve60: MIN_PLANNING_TURN_SECONDS "
        f"{previous} -> {CANDIDATE1_PLANNING_FLOOR} port={port}\n"
    )
    uvicorn.run(
        "intelligence.api.app:app",
        host="127.0.0.1",
        port=port,
        log_level="info",
    )


def start_candidate_sidecar(
    *,
    port: int,
    repo_root: Path,
    users_dir: Path,
    python: Path,
    log_path: Path,
) -> int:
    if port in RESERVED_PORTS:
        raise RuntimeError(f"port {port} is reserved")
    if port_is_listening(port):
        raise RuntimeError(f"port {port} already listening")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    script = sidecar_zsh(
        port=port, repo_root=repo_root, users_dir=users_dir, python=python
    )
    with log_path.open("ab") as log:
        process = subprocess.Popen(
            ["zsh", "-c", script],
            stdout=log,
            stderr=log,
            start_new_session=True,
        )
    deadline = time.monotonic() + 90
    last_error = "not contacted"
    while time.monotonic() < deadline:
        if process.poll() is not None:
            tail = (
                log_path.read_text(encoding="utf-8", errors="replace")[-2000:]
                if log_path.is_file()
                else ""
            )
            raise RuntimeError(f"sidecar exited {process.returncode}: {tail}")
        try:
            payload = health(port)
            if payload.get("status") in {"healthy", "ready", "ok"}:
                return process.pid
            last_error = f"status={payload.get('status')!r}"
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = str(exc)
        time.sleep(0.5)
    process.terminate()
    raise RuntimeError(f"sidecar health not ready: {last_error}")


def stop_pid(pid: int) -> None:
    try:
        os.kill(pid, 15)
    except OSError:
        return


def _iso_now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _cmd_smoke(args: argparse.Namespace) -> int:
    port = int(args.port)
    if not port_is_listening(port):
        print(json.dumps({"ok": False, "block": f"port {port} not listening"}, ensure_ascii=False))
        return 2
    try:
        info = health(port)
    except (urllib.error.URLError, TimeoutError) as exc:
        print(json.dumps({"ok": False, "block": f"health failed: {exc}"}, ensure_ascii=False))
        return 2
    users_dir = Path(info.get("users_dir") or args.users_dir)
    question = args.question or QUESTION_POOL[0]
    try:
        probe = post_conversation_probe(
            port=port,
            user=args.user,
            question=question,
            timeout=args.timeout,
        )
    except (urllib.error.URLError, TimeoutError, RuntimeError) as exc:
        print(json.dumps({"ok": False, "block": f"probe failed: {exc}"}, ensure_ascii=False))
        return 2
    metrics = score_trial(
        users_dir=users_dir,
        user=args.user,
        run_id=probe["run_id"],
        public_answer=str(probe.get("answer") or ""),
    )
    reached = bool(metrics["reached_episode"] and metrics["has_episode_file"])
    row = {
        "ts": _iso_now(),
        "phase": "smoke",
        "arm": "control",
        "user": args.user,
        "port": port,
        "question": question,
        **probe,
        **metrics,
    }
    append_jsonl(Path(args.ledger), row)
    print(json.dumps({"ok": reached, "smoke": row, "health": {
        "source_revision": _as_dict(info.get("runtime")).get("source_revision"),
        "source_dirty": _as_dict(info.get("runtime")).get("source_dirty"),
        "agent_runtime": info.get("agent_runtime"),
    }}, ensure_ascii=False, indent=2))
    return 0 if reached else 1


def _cmd_run(args: argparse.Namespace) -> int:
    ledger = Path(args.ledger)
    users_dir_control = Path(args.users_dir)
    users_dir_candidate = Path(args.candidate_users_dir)
    n = int(args.n)
    start = int(args.start)
    sidecar_pid = 0
    if args.arm in {"reserve60", "both"}:
        if not port_is_listening(args.candidate_port):
            sidecar_pid = start_candidate_sidecar(
                port=int(args.candidate_port),
                repo_root=Path(args.repo_root),
                users_dir=users_dir_candidate,
                python=Path(args.python),
                log_path=RUNTIME_ROOT / "sidecar.log",
            )
            print(f"sidecar pid={sidecar_pid} port={args.candidate_port}", flush=True)
    try:
        for index in range(start, start + n):
            question = QUESTION_POOL[index % len(QUESTION_POOL)]
            if args.arm == "both":
                arm = "control" if (index - start) % 2 == 0 else "reserve60"
            else:
                arm = args.arm
            port = CONTROL_PORT if arm == "control" else int(args.candidate_port)
            users_dir = users_dir_control if arm == "control" else users_dir_candidate
            print(f"[{index}] arm={arm} port={port} q={question[:24]}", flush=True)
            try:
                probe = post_conversation_probe(
                    port=port,
                    user=args.user,
                    question=question,
                    timeout=args.timeout,
                )
            except (urllib.error.URLError, TimeoutError, RuntimeError) as exc:
                append_jsonl(
                    ledger,
                    {
                        "ts": _iso_now(),
                        "phase": "run",
                        "arm": arm,
                        "user": args.user,
                        "port": port,
                        "question": question,
                        "error": str(exc),
                        "reached_episode": False,
                    },
                )
                print(f"  block: {exc}", flush=True)
                if "URLError" in str(exc) or "Connection" in str(exc):
                    return 2
                continue
            metrics = score_trial(
                users_dir=users_dir,
                user=args.user,
                run_id=str(probe["run_id"]),
                public_answer=str(probe.get("answer") or ""),
            )
            append_jsonl(
                ledger,
                {
                    "ts": _iso_now(),
                    "phase": "run",
                    "arm": arm,
                    "user": args.user,
                    "port": port,
                    "question": question,
                    **probe,
                    **metrics,
                },
            )
            print(
                f"  run_id={probe['run_id']} reached={metrics['reached_episode']} "
                f"stop={metrics.get('stop_reason')} carried={metrics.get('carried_draft_chars')}",
                flush=True,
            )
    finally:
        if sidecar_pid:
            stop_pid(sidecar_pid)
    return 0


def _cmd_score(args: argparse.Namespace) -> int:
    rows = load_jsonl(Path(args.ledger))
    if args.phase:
        rows = [row for row in rows if row.get("phase") == args.phase]
    by_arm = {arm: [row for row in rows if row.get("arm") == arm] for arm in ARMS}
    summary = {arm: aggregate_arm(items) for arm, items in by_arm.items()}
    comparison = compare_arms(summary["control"], summary["reserve60"])
    payload = {
        "ledger": str(args.ledger),
        "preregistered_criterion": (
            "候选臂 model_finish 率较对照 +15pp 以上且答案长度不降 → "
            "该候选进实施立项；否则记「未达标」并留读数。"
        ),
        "min_n_per_arm": MIN_N_PER_ARM,
        "arms": summary,
        "comparison": comparison,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _cmd_sidecar(args: argparse.Namespace) -> int:
    if args.action == "start":
        pid = start_candidate_sidecar(
            port=int(args.candidate_port),
            repo_root=Path(args.repo_root),
            users_dir=Path(args.candidate_users_dir),
            python=Path(args.python),
            log_path=RUNTIME_ROOT / "sidecar.log",
        )
        print(json.dumps({"pid": pid, "port": args.candidate_port}, ensure_ascii=False))
        return 0
    pid_path = RUNTIME_ROOT / "sidecar.pid"
    if args.pid:
        stop_pid(int(args.pid))
    elif pid_path.is_file():
        stop_pid(int(pid_path.read_text().strip()))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--user", default=PROBE_USER)
    parser.add_argument("--ledger", default=str(DEFAULT_LEDGER))
    parser.add_argument("--users-dir", default=str(DEFAULT_USERS_DIR))
    parser.add_argument(
        "--candidate-users-dir",
        default=str(RUNTIME_ROOT / "users"),
    )
    parser.add_argument("--python", default=str(DEFAULT_PYTHON))
    parser.add_argument(
        "--repo-root",
        default=str(Path(__file__).resolve().parents[1]),
    )
    parser.add_argument("--candidate-port", type=int, default=CANDIDATE_PORT_DEFAULT)
    parser.add_argument("--timeout", type=float, default=DEFAULT_PROBE_TIMEOUT)
    sub = parser.add_subparsers(dest="cmd", required=True)

    smoke = sub.add_parser("smoke", help="n=1 打对照口，验证是否走到 episode")
    smoke.add_argument("--port", type=int, default=CONTROL_PORT)
    smoke.add_argument("--question", default="")
    smoke.set_defaults(func=_cmd_smoke)

    run = sub.add_parser("run", help="分批跑臂（交替）；n 不够不得下结论")
    run.add_argument("--arm", choices=("control", "reserve60", "both"), default="both")
    run.add_argument("--n", type=int, default=1, help="本批试次数（不是每臂目标）")
    run.add_argument("--start", type=int, default=0)
    run.set_defaults(func=_cmd_run)

    score = sub.add_parser("score", help="从 trials.jsonl 复算五项指标")
    score.add_argument("--phase", default="")
    score.set_defaults(func=_cmd_score)

    sidecar = sub.add_parser("sidecar", help="起停候选① sidecar")
    sidecar.add_argument("action", choices=("start", "stop"))
    sidecar.add_argument("--pid", type=int, default=0)
    sidecar.set_defaults(func=_cmd_sidecar)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
