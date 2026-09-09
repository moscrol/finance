#!/usr/bin/env python3
"""工单 04 · 用 Workbench 真实对话入口跑冻结题，对照独立参照判卷。

它只走公开 API（与 UI 同一条路：``POST /api/conversations`` → ``POST .../messages`` →
轮询 ``GET /api/runs/{run_id}`` → 下载 ``GET /api/runs/{run_id}/artifacts/{name}``），不 import
本仓模块、不读 run 目录——判的是用户看得见的东西。

判卷点（每题分别记，不合成一个百分数）：

- ``run_status``：run 终态；``message_status``：助手气泡终态。
- ``artifacts``：本 run 的 calc-<id>.json / .csv / .html 有没有落下来、能不能下载。
- ``calc_hits``：参照里 must_have 的每个数，在**计算产物**（summary / tables 的数字）里能否按容差找到。
- ``answer_hits``：headline 数字是否出现在回答正文里（用户不看产物也该看到结论数）。
- 追问（改假设 / 修订数据）：在同一会话里发第二句，检查新产物有新值、旧产物文件仍可下载、
  「不应变」的数没变。

用法::

    python3 scripts/calc_case_acceptance.py --base-url http://127.0.0.1:8794 \
        --cases docs/.../progress/04-cases.json --out docs/.../progress/04-acceptance-<tag>.json \
        [--only 01_single_quarter,04_revenue_scenarios] [--answer-only]

``--answer-only``：基线实例（没有计算产物的旧代码）只按回答正文判数字。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

TERMINAL_RUN = {"completed", "failed", "cancelled"}
TERMINAL_MESSAGE = {"completed", "failed", "cancelled", "degraded", "partial"}
NUMBER_RE = re.compile(r"-?\d+(?:,\d{3})*(?:\.\d+)?")


class Client:
    def __init__(self, base_url: str, user: str | None) -> None:
        self.base_url = base_url.rstrip("/")
        self.user = user

    def _url(self, path: str, **query: object) -> str:
        params = {k: v for k, v in query.items() if v is not None}
        if self.user and "user" not in params:
            params["user"] = self.user
        return self.base_url + path + (f"?{urllib.parse.urlencode(params)}" if params else "")

    def request(self, method: str, path: str, body: dict | None = None, *, raw: bool = False, **query: object):
        data = None
        headers = {}
        if body is not None:
            payload = dict(body)
            if self.user and "user" not in payload:
                payload["user"] = self.user
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(self._url(path, **query), data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                content = response.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:400]
            raise RuntimeError(f"{method} {path} → HTTP {exc.code}: {detail}") from exc
        if raw:
            return content
        return json.loads(content.decode("utf-8")) if content else None

    def health(self) -> dict:
        return self.request("GET", "/api/health")

    def create_conversation(self, title: str) -> str:
        return str(self.request("POST", "/api/conversations", {"title": title})["conversation_id"])

    def send(self, conversation_id: str, content: str) -> dict:
        return self.request(
            "POST",
            f"/api/conversations/{conversation_id}/messages",
            {"content": content, "skill_mode": "auto", "selected_skill_ids": []},
        )

    def run(self, run_id: str) -> dict:
        return self.request("GET", f"/api/runs/{run_id}")

    def messages(self, conversation_id: str) -> list[dict]:
        return self.request("GET", f"/api/conversations/{conversation_id}/messages")

    def artifact(self, run_id: str, name: str) -> bytes:
        return self.request("GET", f"/api/runs/{run_id}/artifacts/{name}", raw=True)


def wait_for_run(client: Client, run_id: str, *, timeout: float, poll: float = 3.0) -> dict:
    started = time.monotonic()
    last = None
    while time.monotonic() - started < timeout:
        last = client.run(run_id)
        if str(last.get("status")) in TERMINAL_RUN:
            return last
        time.sleep(poll)
    return last or {"status": "timeout"}


def numbers_in(value: object, out: list[float]) -> None:
    if isinstance(value, bool):
        return
    if isinstance(value, (int, float)):
        out.append(float(value))
    elif isinstance(value, dict):
        for item in value.values():
            numbers_in(item, out)
    elif isinstance(value, (list, tuple)):
        for item in value:
            numbers_in(item, out)


def numbers_in_text(text: str) -> list[float]:
    out: list[float] = []
    for match in NUMBER_RE.finditer(text or ""):
        try:
            out.append(float(match.group().replace(",", "")))
        except ValueError:
            continue
    return out


def hit(expected: dict, pool: list[float]) -> bool:
    value = expected.get("value")
    if not isinstance(value, (int, float)):
        return False
    tol = float(expected.get("tol") or 0.01)
    return any(abs(candidate - float(value)) <= tol + 1e-9 for candidate in pool)


def score(expectations: list[dict], pool: list[float]) -> dict:
    hits = [{"label": item["label"], "value": item["value"], "hit": hit(item, pool)} for item in expectations]
    return {"n": sum(1 for item in hits if item["hit"]), "m": len(hits), "items": hits}


def collect_calc_results(client: Client, run: dict) -> tuple[list[dict], list[str], list[float]]:
    """下载本 run 全部 calc-*.json，取出数字池；同时验证 csv / html 能下载。"""

    records: list[dict] = []
    downloadable: list[str] = []
    pool: list[float] = []
    for artifact in run.get("artifacts") or []:
        name = str(artifact.get("path") or "")
        if not name.startswith("calc-"):
            continue
        try:
            content = client.artifact(str(run["run_id"]), name)
        except RuntimeError as exc:
            downloadable.append(f"{name}: FAILED {exc}")
            continue
        downloadable.append(f"{name}: {len(content)} bytes")
        if name.endswith(".json"):
            try:
                record = json.loads(content.decode("utf-8"))
            except ValueError:
                continue
            records.append(record)
            numbers_in(record.get("result"), pool)
    return records, downloadable, pool


def assistant_message(client: Client, conversation_id: str, run_id: str) -> dict | None:
    for message in client.messages(conversation_id):
        if message.get("role") == "assistant" and message.get("run_id") == run_id:
            return message
    return None


def run_prompt(client: Client, conversation_id: str, prompt: str, *, timeout: float, answer_only: bool) -> dict:
    started = time.monotonic()
    submitted = client.send(conversation_id, prompt)
    run_id = str(submitted["run_id"])
    run = wait_for_run(client, run_id, timeout=timeout)
    elapsed = round(time.monotonic() - started, 1)
    message = assistant_message(client, conversation_id, run_id) or {}
    answer = str(message.get("content") or "")
    records, downloadable, calc_pool = ([], [], []) if answer_only else collect_calc_results(client, run)
    return {
        "run_id": run_id,
        "prompt": prompt,
        "elapsed_s": elapsed,
        "run_status": run.get("status"),
        "run_error": run.get("error"),
        "degrades": run.get("degrades") or [],
        "message_status": message.get("status"),
        "answer_chars": len(answer),
        "answer_excerpt": answer[:600],
        "artifacts": [str(item.get("path")) for item in (run.get("artifacts") or [])],
        "calc_downloads": downloadable,
        "calc_ids": [str(record.get("calc_id")) for record in records],
        "calc_pool": calc_pool,
        "answer_pool": numbers_in_text(answer),
    }


def judge(case: dict, turn: dict, *, answer_only: bool) -> dict:
    calc_pool = turn["calc_pool"]
    answer_pool = turn["answer_pool"]
    verdict = {
        "calc_hits": None if answer_only else score(case.get("must_have", []), calc_pool),
        "answer_hits": score(case.get("headline", case.get("must_have", [])), answer_pool),
        "answer_must_have": score(case.get("must_have", []), answer_pool),
    }
    if answer_only:
        verdict["pass"] = verdict["answer_must_have"]["n"] == verdict["answer_must_have"]["m"] and turn["run_status"] == "completed"
    else:
        verdict["pass"] = (
            turn["run_status"] == "completed"
            and bool(turn["calc_ids"])
            and verdict["calc_hits"]["n"] == verdict["calc_hits"]["m"]
            and verdict["answer_hits"]["n"] >= 1
        )
    return verdict


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--user", default=None)
    parser.add_argument("--cases", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--only", default="", help="逗号分隔的 case id 子集")
    parser.add_argument("--timeout", type=float, default=900.0, help="单轮等待秒数")
    parser.add_argument("--answer-only", action="store_true", help="基线实例：只按回答正文判数字")
    parser.add_argument("--skip-follow-ups", action="store_true")
    args = parser.parse_args(argv)

    client = Client(args.base_url, args.user)
    health = client.health()
    document = json.loads(Path(args.cases).read_text(encoding="utf-8"))
    wanted = {item.strip() for item in args.only.split(",") if item.strip()}
    report: dict = {
        "schema": "calc-acceptance/v1",
        "started_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "base_url": args.base_url,
        "answer_only": args.answer_only,
        "health": {k: health.get(k) for k in ("status", "source_revision", "loaded_code_root", "runtime_backend") if k in health},
        "cases_fetched_at": document.get("fetched_at"),
        "results": [],
    }
    for case in document["cases"]:
        if wanted and case["id"] not in wanted:
            continue
        print(f"▶ {case['id']} {case['title']}", flush=True)
        conversation_id = client.create_conversation(f"calc-04 {case['id']}")
        entry: dict = {"id": case["id"], "title": case["title"], "conversation_id": conversation_id}
        try:
            turn = run_prompt(client, conversation_id, case["prompt"], timeout=args.timeout, answer_only=args.answer_only)
        except Exception as exc:  # noqa: BLE001 - 一题炸了不影响其余题
            entry["error"] = f"{type(exc).__name__}: {exc}"
            report["results"].append(entry)
            print(f"  ✗ error {entry['error']}", flush=True)
            continue
        entry["turn"] = turn
        entry["verdict"] = judge(case, turn, answer_only=args.answer_only)
        status = "✓" if entry["verdict"]["pass"] else "✗"
        calc = entry["verdict"]["calc_hits"]
        print(
            f"  {status} run={turn['run_status']} msg={turn['message_status']} {turn['elapsed_s']}s "
            f"calc={'-' if calc is None else f'{calc['n']}/{calc['m']}'} "
            f"answer={entry['verdict']['answer_hits']['n']}/{entry['verdict']['answer_hits']['m']} "
            f"artifacts={len(turn['artifacts'])} calc_ids={turn['calc_ids']}",
            flush=True,
        )
        follow_up = case.get("follow_up")
        if follow_up and not args.skip_follow_ups:
            print(f"  ↳ {follow_up['id']} {follow_up['title']}", flush=True)
            try:
                second = run_prompt(client, conversation_id, follow_up["prompt"], timeout=args.timeout, answer_only=args.answer_only)
            except Exception as exc:  # noqa: BLE001
                entry["follow_up"] = {"id": follow_up["id"], "error": f"{type(exc).__name__}: {exc}"}
                print(f"    ✗ error {entry['follow_up']['error']}", flush=True)
                report["results"].append(entry)
                continue
            verdict = judge(follow_up, second, answer_only=args.answer_only)
            pool = second["answer_pool"] if args.answer_only else second["calc_pool"]
            verdict["unchanged"] = score(follow_up.get("unchanged", []), pool)
            # 旧结果仍可查看：上一轮的 calc 产物还能下载。
            previous_ok = True
            if not args.answer_only:
                for name in turn["artifacts"]:
                    if name.startswith("calc-"):
                        try:
                            client.artifact(turn["run_id"], name)
                        except RuntimeError:
                            previous_ok = False
            verdict["previous_artifacts_still_downloadable"] = previous_ok
            verdict["reused_inputs"] = any(
                isinstance(record, dict) and record.get("base_calc_id")
                for record in _records_for(client, second)
            )
            verdict["pass"] = bool(verdict["pass"]) and previous_ok and verdict["unchanged"]["n"] == verdict["unchanged"]["m"]
            entry["follow_up"] = {"id": follow_up["id"], "title": follow_up["title"], "turn": second, "verdict": verdict}
            status = "✓" if verdict["pass"] else "✗"
            print(
                f"    {status} run={second['run_status']} {second['elapsed_s']}s "
                f"calc={'-' if verdict['calc_hits'] is None else f'{verdict['calc_hits']['n']}/{verdict['calc_hits']['m']}'} "
                f"unchanged={verdict['unchanged']['n']}/{verdict['unchanged']['m']} reused_inputs={verdict['reused_inputs']}",
                flush=True,
            )
        report["results"].append(entry)

    report["finished_at"] = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    passed = sum(1 for item in report["results"] if item.get("verdict", {}).get("pass"))
    total = len(report["results"])
    follow_passed = sum(1 for item in report["results"] if item.get("follow_up", {}).get("verdict", {}).get("pass"))
    follow_total = sum(1 for item in report["results"] if "follow_up" in item)
    report["summary"] = {"cases_passed": passed, "cases_total": total, "follow_ups_passed": follow_passed, "follow_ups_total": follow_total}
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n{passed}/{total} cases · {follow_passed}/{follow_total} follow-ups · report → {out}")
    return 0 if passed == total and follow_passed == follow_total else 1


def _records_for(client: Client, turn: dict) -> list[dict]:
    records: list[dict] = []
    for name in turn.get("artifacts") or []:
        if name.startswith("calc-") and name.endswith(".json"):
            try:
                records.append(json.loads(client.artifact(turn["run_id"], name).decode("utf-8")))
            except (RuntimeError, ValueError):
                continue
    return records


if __name__ == "__main__":
    sys.exit(main())
