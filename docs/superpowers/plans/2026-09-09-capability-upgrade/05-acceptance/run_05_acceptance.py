#!/usr/bin/env python3
"""05 输入理解 · 真实对话入口验收客户端。

走 Workbench 的真实门：POST /api/conversations → POST /api/conversations/{id}/messages →
轮询 GET /api/runs/{run_id} 到终态 → 读该 run 目录里的 trace.jsonl（控制器一步带整份
task_frame / decision）→ GET /api/conversations/{id}/messages 取助手正文。

每题 / 每条追问链一个 conversation；链内各轮串行，上一轮到终态才发下一轮。
输出：<out_dir>/<case_id>.json（原始 task_frame、decision、助手正文、耗时、run 状态），
以及 <out_dir>/summary.json。正文只留本地，不进仓。

用法：
  run_05_acceptance.py --base-url http://127.0.0.1:8797 --users-dir <FORESIGHT_USERS_DIR> \
      --frozen frozen_questions.json --out <out_dir> [--only Q01,C2] [--turn-timeout 900]
返回码：0 全部到终态；1 有 run failed / cancelled / 超时；2 协议异常。
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

USER = "cap05"
TERMINAL = {"completed", "failed", "cancelled"}
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


class ProtocolError(RuntimeError):
    pass


def _request(method: str, url: str, payload: dict | None = None, timeout: float = 60.0):
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with _OPENER.open(req, timeout=timeout) as resp:
            body = resp.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:500]
        raise ProtocolError(f"{method} {url} → HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise ProtocolError(f"{method} {url} → {exc}") from exc
    return json.loads(body) if body else None


def _url(base: str, path: str, query: dict | None = None) -> str:
    q = f"?{urllib.parse.urlencode(query)}" if query else ""
    return f"{base.rstrip('/')}{path}{q}"


def _find_run_dir(users_dir: Path, run_id: str) -> Path | None:
    for candidate in (users_dir / USER / "runs" / run_id,):
        if candidate.is_dir():
            return candidate
    hits = list(users_dir.glob(f"*/runs/{run_id}"))
    return hits[0] if hits else None


def _controller_trace(run_dir: Path | None) -> dict:
    """trace.jsonl 里 turn_controller 那一步：task_frame / decision / turn_intent。"""
    if run_dir is None:
        return {}
    trace = run_dir / "trace.jsonl"
    if not trace.is_file():
        return {}
    picked: dict = {}
    for line in trace.read_text(encoding="utf-8").splitlines():
        try:
            step = json.loads(line)
        except json.JSONDecodeError:
            continue
        if step.get("name") == "turn_controller" or str(step.get("step_id", "")).startswith("controller"):
            # trace.jsonl 的 output_summary 是 JSON 字符串（RunStore 落盘形态），不是对象。
            payload = step.get("output_summary") or step.get("output") or step.get("payload") or {}
            if isinstance(payload, str):
                try:
                    payload = json.loads(payload)
                except json.JSONDecodeError:
                    payload = {}
            if isinstance(payload, dict) and payload.get("task_frame"):
                picked = payload
    return picked


def _episode_health(run_dir: Path | None) -> dict:
    """continuous-episode.json 里解释「为什么降级」的几个读数：判官状态、provider 失败。"""
    if run_dir is None:
        return {}
    path = run_dir / "continuous-episode.json"
    if not path.is_file():
        return {}
    try:
        episode = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    semantic = episode.get("semantic_verifier") or {}
    metrics = episode.get("metrics") or {}
    errors: list[str] = []
    for event in episode.get("events") or []:
        payload = (event or {}).get("payload") or {}
        err = payload.get("error") or payload.get("failure_reason")
        if isinstance(err, str) and err and err not in errors:
            errors.append(err[:120])
    return {
        "judge_status": semantic.get("judge_status"),
        "semantic_status": semantic.get("status"),
        "structural_status": metrics.get("structural_status"),
        "provider_attempts": metrics.get("provider_attempts"),
        "provider_errors": errors[:4],
    }


def _grep_trace_for_task_frame(run_dir: Path | None) -> dict:
    """兜底：trace.jsonl 任一行里带 task_frame 键的对象。"""
    if run_dir is None:
        return {}
    trace = run_dir / "trace.jsonl"
    if not trace.is_file():
        return {}
    found: dict = {}

    def walk(node):
        nonlocal found
        if isinstance(node, dict):
            if "task_frame" in node and isinstance(node["task_frame"], dict) and not found:
                found = node
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    for line in trace.read_text(encoding="utf-8").splitlines():
        try:
            walk(json.loads(line))
        except json.JSONDecodeError:
            continue
        if found:
            break
    return found


def _wait_terminal(base: str, run_id: str, timeout: float) -> dict:
    deadline = time.monotonic() + timeout
    last: dict = {}
    while time.monotonic() < deadline:
        last = _request("GET", _url(base, f"/api/runs/{urllib.parse.quote(run_id, safe='')}", {"user": USER})) or {}
        if str(last.get("status")) in TERMINAL:
            return last
        time.sleep(3.0)
    last["status"] = last.get("status") or "timeout"
    last["_timeout"] = True
    return last


def _assistant_messages(base: str, conversation_id: str) -> list[dict]:
    items = _request(
        "GET",
        _url(base, f"/api/conversations/{urllib.parse.quote(conversation_id, safe='')}/messages", {"user": USER}),
    )
    return items if isinstance(items, list) else []


def run_case(base: str, users_dir: Path, case_id: str, turns: list[dict], turn_timeout: float) -> dict:
    started = time.time()
    conversation = _request("POST", _url(base, "/api/conversations"), {"title": f"cap05 {case_id}", "user": USER})
    conversation_id = str(conversation["conversation_id"])
    results: list[dict] = []
    for index, turn in enumerate(turns, start=1):
        text = turn["text"]
        t0 = time.monotonic()
        created = _request(
            "POST",
            _url(base, f"/api/conversations/{urllib.parse.quote(conversation_id, safe='')}/messages"),
            {"content": text, "skill_mode": "hybrid", "selected_skill_ids": [], "user": USER},
            timeout=120.0,
        )
        run_id = str(created.get("run_id"))
        terminal = _wait_terminal(base, run_id, turn_timeout)
        elapsed = time.monotonic() - t0
        run_dir = _find_run_dir(users_dir, run_id)
        controller = _controller_trace(run_dir) or _grep_trace_for_task_frame(run_dir)
        messages = _assistant_messages(base, conversation_id)
        assistant = [m for m in messages if m.get("role") == "assistant" and m.get("run_id") == run_id]
        answer = assistant[-1].get("content", "") if assistant else ""
        results.append(
            {
                "turn": index,
                "text": text,
                "expected": turn.get("expected", {}),
                "run_id": run_id,
                "run_status": terminal.get("status"),
                "degrades": terminal.get("degrades"),
                "error": terminal.get("error"),
                "elapsed_seconds": round(elapsed, 1),
                "task_frame": controller.get("task_frame"),
                "decision": controller.get("decision"),
                "turn_intent": controller.get("turn_intent"),
                "answer": answer,
                "run_dir": str(run_dir) if run_dir else None,
                "episode_health": _episode_health(run_dir),
            }
        )
        print(
            f"[{case_id}#{index}] status={terminal.get('status')} {elapsed:.0f}s "
            f"lane={(controller.get('decision') or {}).get('lane')} "
            f"qt={(controller.get('task_frame') or {}).get('question_type')} "
            f"subject={(controller.get('task_frame') or {}).get('subject')}",
            flush=True,
        )
        if terminal.get("_timeout"):
            break
    return {
        "case_id": case_id,
        "conversation_id": conversation_id,
        "turns": results,
        "wall_seconds": round(time.time() - started, 1),
    }


def _expand(frozen: dict) -> dict[str, list[dict]]:
    materials = frozen.get("materials", {})
    by_id = {q["id"]: q for q in frozen["questions"]}

    def render(text: str) -> str:
        for key, value in materials.items():
            text = text.replace("{" + key + "}", value)
        return text

    cases: dict[str, list[dict]] = {}
    for q in frozen["questions"]:
        cases[q["id"]] = [{"text": render(q["text"]), "expected": q.get("expected", {})}]
    for chain in frozen.get("chains", []):
        turns = []
        for turn in chain["turns"]:
            if "ref" in turn:
                ref = by_id[turn["ref"]]
                turns.append({"text": render(ref["text"]), "expected": ref.get("expected", {})})
            else:
                turns.append({"text": render(turn["text"]), "expected": turn.get("expected", {})})
        cases[chain["id"]] = turns
    return cases


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--users-dir", required=True)
    parser.add_argument("--frozen", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--only", default="")
    parser.add_argument("--turn-timeout", type=float, default=900.0)
    args = parser.parse_args(argv)

    frozen = json.loads(Path(args.frozen).read_text(encoding="utf-8"))
    cases = _expand(frozen)
    only = {item.strip() for item in args.only.split(",") if item.strip()}
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    users_dir = Path(args.users_dir)

    # readiness 只记录不拦：生产 8792 同样因 market_data_consistency 报 503 not_ready，
    # 消息入口照常工作；拦在这里会把「数据一致性」这条 08 的事混进 05 的读数。
    try:
        ready = _request("GET", _url(args.base_url, "/api/health/ready"))
    except ProtocolError as exc:
        ready = {"error": str(exc)[:400]}
    health = _request("GET", _url(args.base_url, "/api/health")) or {}
    revision = (health.get("runtime") or {}).get("source_revision")
    print(f"readiness: {json.dumps(ready, ensure_ascii=False)[:300]}", flush=True)
    print(f"server revision: {revision} code_root: {(health.get('runtime') or {}).get('code_root')}", flush=True)

    summary: dict = {
        "base_url": args.base_url,
        "server_revision": revision,
        "server_code_root": (health.get("runtime") or {}).get("code_root"),
        "readiness": ready if isinstance(ready, dict) and "error" in ready else {"status": (ready or {}).get("status"), "missing_critical": (ready or {}).get("missing_critical")},
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "cases": {},
    }
    worst = 0
    for case_id, turns in cases.items():
        if only and case_id not in only:
            continue
        try:
            result = run_case(args.base_url, users_dir, case_id, turns, args.turn_timeout)
        except ProtocolError as exc:
            print(f"[{case_id}] protocol error: {exc}", flush=True)
            summary["cases"][case_id] = {"error": str(exc)}
            worst = max(worst, 2)
            continue
        (out_dir / f"{case_id}.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        statuses = [t["run_status"] for t in result["turns"]]
        summary["cases"][case_id] = {
            "statuses": statuses,
            "wall_seconds": result["wall_seconds"],
            "frames": [
                {
                    "turn": t["turn"],
                    "lane": (t.get("decision") or {}).get("lane"),
                    "question_type": (t.get("task_frame") or {}).get("question_type"),
                    "subject": (t.get("task_frame") or {}).get("subject"),
                    "timeframe": (t.get("task_frame") or {}).get("timeframe"),
                    "clarification_question": (t.get("task_frame") or {}).get("clarification_question"),
                }
                for t in result["turns"]
            ],
        }
        if any(s not in {"completed"} for s in statuses):
            worst = max(worst, 1)
        (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    summary["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return worst


if __name__ == "__main__":
    sys.exit(main())
