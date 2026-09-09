#!/usr/bin/env python3
"""06 号单读数：把一条臂的 12 题收成一张表——完成度、关键成果命中、自适应行为、成本。

读三处产物：``probe.json``（smoke 收据：run_id / 耗时 / 判官 / 终态）、run 目录里的
``continuous-episode.json`` + ``answer.md``（终态、绑定、公开答案）、旁车独立的 durable
事件流 ``events.jsonl``（含投影里没有的 ``tool_budget_state`` → ``runtime_budget.research_progress``）。

自适应行为读法（两臂通用，纯事件事实）：
- 每批新证据数：按 ``model_turn`` 切批，``tool_result.evidence_hashes`` 相对此前集合去重。
- 停滞批数：新证据为 0 的批。
- 重复查询：同 (tool, 归一化 query) 出现 ≥2 次。
- 换路：某批某工具空手 / 重复之后，下一批模型换了工具或改了查询（``switched_after_stall``）。
- 候选臂另有：进展块给过哪些建议码，建议之后下一批是否换路（``acted_on_suggestion``）。

key_outcomes 检查器是确定性规则（答案关键词 + 事件事实），题集里写死，跑前冻结。

用法：
    .venv-workbench/bin/python scripts/cap06_read_runs.py --arm base [--root ~/.finance-runtime/cap06-20260909]
"""

from __future__ import annotations

import argparse
from collections import Counter
import glob
import json
import os
from pathlib import Path
import re
import sys

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from intelligence.runtime.research_progress import normalize_query  # noqa: E402
from intelligence.services.episode_store import JsonlEpisodeStore  # noqa: E402

FIXTURE = REPO / "intelligence/eval/fixtures/adaptive-research-06.questions.json"
_NO_PROGRESS = {"duplicate", "empty", "error", "timeout", "rejected"}


def _load_json(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _load_events(path: Path) -> list[dict]:
    events: list[dict] = []
    if not path.is_file():
        return events
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            events.append(item)
    return events


def _find_run_dir(users_root: Path, run_id: str) -> Path | None:
    hits = glob.glob(str(users_root / "*" / "runs" / run_id))
    return Path(hits[0]) if hits else None


def _batches(events: list[dict]) -> list[list[dict]]:
    """按 model_turn 切批：一次模型轮之后到下一次模型轮之前的 tool_request/result/error。"""

    batches: list[list[dict]] = []
    current: list[dict] | None = None
    for event in events:
        kind = event.get("kind")
        if kind == "model_turn":
            if current:
                batches.append(current)
            current = []
        elif kind in {"tool_request", "tool_result", "tool_error", "tool_budget_state"}:
            if current is None:
                current = []
            current.append(event)
    if current:
        batches.append(current)
    return [batch for batch in batches if any(e.get("kind") in {"tool_result", "tool_error"} for e in batch)]


def _call_rows(batch: list[dict], seen_hashes: set[str]) -> list[dict]:
    """一批里逐调用的 (tool, query, status, new_evidence)。"""

    requests = {
        e["payload"].get("call_id"): e["payload"] for e in batch if e.get("kind") == "tool_request"
    }
    rows: list[dict] = []
    for event in batch:
        kind = event.get("kind")
        payload = event.get("payload") or {}
        if kind == "tool_result":
            hashes = [str(h) for h in payload.get("evidence_hashes") or []]
            new = [h for h in hashes if h not in seen_hashes]
            seen_hashes.update(new)
            query = payload.get("query") or (requests.get(payload.get("call_id")) or {}).get("arguments")
            status = "new" if new else ("duplicate" if hashes else "empty")
            rows.append(
                {
                    "tool": payload.get("tool"),
                    "query": normalize_query(query),
                    "status": status,
                    "new_evidence": len(new),
                    "dataset": payload.get("dataset"),
                    "hashes": hashes,
                }
            )
        elif kind == "tool_error":
            request = requests.get(payload.get("call_id")) or {}
            rows.append(
                {
                    "tool": payload.get("tool") or request.get("name"),
                    "query": normalize_query(request.get("arguments")),
                    "status": "duplicate" if payload.get("error") == "duplicate_query" else "error",
                    "new_evidence": 0,
                    "dataset": None,
                    "hashes": [],
                }
            )
    return rows


def _adaptive_metrics(events: list[dict]) -> dict:
    batches = _batches(events)
    seen: set[str] = set()
    per_batch: list[dict] = []
    for batch in batches:
        rows = _call_rows(batch, seen)
        progress = None
        for event in batch:
            if event.get("kind") == "tool_budget_state":
                budget = (event.get("payload") or {}).get("runtime_budget") or {}
                progress = budget.get("research_progress")
        per_batch.append({"calls": rows, "new_evidence": sum(r["new_evidence"] for r in rows), "progress": progress})

    pair_counter: Counter[tuple[str, str]] = Counter()
    for batch in per_batch:
        for row in batch["calls"]:
            pair_counter[(str(row["tool"]), str(row["query"]))] += 1
    repeated_pairs = sum(1 for count in pair_counter.values() if count >= 2)

    switched_after_stall = 0
    stall_opportunities = 0
    acted_on_suggestion = 0
    suggestions_given = 0
    suggestion_codes: Counter[str] = Counter()
    for index in range(len(per_batch) - 1):
        current, following = per_batch[index], per_batch[index + 1]
        stalled_calls = [row for row in current["calls"] if row["status"] in _NO_PROGRESS]
        if stalled_calls:
            stall_opportunities += 1
            stalled_keys = {(row["tool"], row["query"]) for row in stalled_calls}
            following_keys = {(row["tool"], row["query"]) for row in following["calls"]}
            if following_keys and not (following_keys & stalled_keys):
                switched_after_stall += 1
        progress = current.get("progress") or {}
        codes = [str(code) for code in progress.get("suggestion") or []]
        if codes:
            suggestions_given += 1
            for code in codes:
                suggestion_codes[code.split(":")[0]] += 1
            if any(code.startswith(("switch_query", "switch_tool", "stalled")) for code in codes):
                repeated_keys = {
                    (str(row["tool"]), str(row["query"])) for row in progress.get("repeated_queries") or []
                }
                stale_tools = {code.split(":")[1].split("→")[0] for code in codes if code.startswith("switch_tool:")}
                following_keys = {(row["tool"], row["query"]) for row in following["calls"]}
                following_tools = {row["tool"] for row in following["calls"]}
                if following_keys and not (following_keys & repeated_keys) and not (following_tools & stale_tools):
                    acted_on_suggestion += 1

    kinds = Counter(e.get("kind") for e in events)
    finalization_reasons = [
        str((e.get("payload") or {}).get("reason")) for e in events if e.get("kind") == "finalization"
    ]
    branches = [e.get("payload") or {} for e in events if e.get("kind") in {"branch_completed", "branch_failed"}]
    input_tokens = sum(
        int((e.get("payload") or {}).get("input_tokens") or 0)
        for e in events
        if e.get("kind") in {"model_turn", "branch_completed"}
    )
    output_tokens = sum(
        int((e.get("payload") or {}).get("output_tokens") or 0)
        for e in events
        if e.get("kind") in {"model_turn", "branch_completed"}
    )
    return {
        "model_turns": kinds.get("model_turn", 0),
        "tool_requests": kinds.get("tool_request", 0),
        "tool_results": kinds.get("tool_result", 0),
        "tool_errors": kinds.get("tool_error", 0),
        "batches": len(per_batch),
        "new_evidence_per_batch": [b["new_evidence"] for b in per_batch],
        "stalled_batches": sum(1 for b in per_batch if b["new_evidence"] == 0),
        "distinct_tools": sorted({str(row["tool"]) for b in per_batch for row in b["calls"]}),
        "distinct_pairs": len(pair_counter),
        "repeated_pairs": repeated_pairs,
        "stall_opportunities": stall_opportunities,
        "switched_after_stall": switched_after_stall,
        "suggestions_given": suggestions_given,
        "suggestion_codes": dict(suggestion_codes),
        "acted_on_suggestion": acted_on_suggestion,
        "sub_research_requests": sum(
            1 for e in events if e.get("kind") == "tool_request" and (e.get("payload") or {}).get("name") == "sub_research"
        ),
        "branches": [
            {"branch_id": b.get("branch_id"), "status": b.get("status"), "evidence": b.get("evidence_count"), "gaps": b.get("gap_count")}
            for b in branches
        ],
        "finalization_reasons": finalization_reasons,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "per_batch": per_batch,
    }


def _bound_tools(episode: dict, events: list[dict]) -> tuple[set[str], set[str]]:
    """终局 bindings 绑到的证据 → (工具集合, dataset 集合)。"""

    outcome = episode.get("outcome") or {}
    bound_hashes: set[str] = set()
    for binding in outcome.get("bindings") or []:
        for digest in binding.get("evidence_hashes") or []:
            bound_hashes.add(str(digest))
    hash_tool: dict[str, str] = {}
    for item in outcome.get("evidence") or []:
        digest = str(item.get("content_hash") or "")
        if digest:
            hash_tool[digest] = str(item.get("tool") or "")
    hash_dataset: dict[str, str] = {}
    for event in events:
        if event.get("kind") != "tool_result":
            continue
        payload = event.get("payload") or {}
        for digest in payload.get("evidence_hashes") or []:
            hash_dataset[str(digest)] = str(payload.get("dataset") or "")
    tools = {hash_tool[h] for h in bound_hashes if h in hash_tool}
    datasets = {hash_dataset[h] for h in bound_hashes if hash_dataset.get(h) and hash_dataset[h] != "unknown"}
    return tools, datasets


def _check_outcome(check: dict, *, answer: str, bound_tools: set[str], bound_datasets: set[str], queries: list[tuple[str, str]]) -> bool:
    kind = check.get("type")
    keywords = [str(k) for k in check.get("keywords") or []]
    if kind == "answer_any":
        return any(k in answer for k in keywords)
    if kind == "answer_count_any":
        return sum(1 for k in keywords if k in answer) >= int(check.get("min", 1))
    if kind == "answer_each_min":
        return all(answer.count(k) >= int(check.get("min", 1)) for k in keywords)
    if kind == "answer_all_groups":
        return all(any(k in answer for k in group) for group in check.get("groups") or [])
    if kind == "regex_any":
        return re.search(str(check.get("pattern")), answer) is not None
    if kind == "regex_distinct_count":
        return len(set(re.findall(str(check.get("pattern")), answer))) >= int(check.get("min", 1))
    if kind == "bound_tool_any":
        return bool(bound_tools & set(check.get("tools") or []))
    if kind == "bound_tool_families_min":
        families = check.get("families") or {}
        hit = sum(1 for tools in families.values() if bound_tools & set(tools))
        return hit >= int(check.get("min", 1))
    if kind == "bound_dataset_min":
        return len(bound_datasets) >= int(check.get("min", 1))
    if kind == "queries_each_min":
        if check.get("or_tool") and any(tool == check["or_tool"] for tool, _ in queries):
            return True
        return all(
            sum(1 for _tool, query in queries if k.lower() in query) >= int(check.get("min", 1)) for k in keywords
        )
    raise ValueError(f"unknown check type: {kind!r}")


def read_case(case: dict, *, arm_dir: Path, users_root: Path, episodes_root: Path) -> dict:
    row: dict = {"case": case["id"], "group": case.get("group")}
    probe = _load_json(arm_dir / case["id"] / "probe.json")
    if not probe:
        row["status"] = "no_probe"
        return row
    run_id = str(probe.get("run_id") or "")
    receipt = probe.get("gate_receipt") or {}
    row.update(
        run_id=run_id,
        elapsed_s=probe.get("elapsed_seconds"),
        terminal=probe.get("terminal_outcome"),
        judge=receipt.get("judge_status"),
        engine=receipt.get("engine"),
        degrade=probe.get("degrade_count"),
    )
    run_dir = _find_run_dir(users_root, run_id) if run_id else None
    if run_dir is None:
        row["status"] = "no_run_dir"
        return row
    episode = _load_json(run_dir / "continuous-episode.json")
    answer_path = run_dir / "answer.md"
    answer = answer_path.read_text(encoding="utf-8") if answer_path.is_file() else ""
    outcome = episode.get("outcome") or {}
    if not answer:
        answer = str(outcome.get("draft") or "")
    contract = episode.get("contract") or {}
    task_id = str(contract.get("task_id") or "")
    events: list[dict] = []
    if task_id:
        events = _load_events(JsonlEpisodeStore(episodes_root).episode_dir(task_id) / "events.jsonl")
    if not events:
        events = list(outcome.get("events") or episode.get("events") or [])
        row["events_source"] = "projection"
    else:
        row["events_source"] = "durable"
    row.update(
        research_status=outcome.get("status"),
        stop_reason=outcome.get("stop_reason"),
        answer_chars=len(answer),
        evidence_total=len(outcome.get("evidence") or []),
        tier=contract.get("research_tier"),
    )
    metrics = _adaptive_metrics(events)
    per_batch = metrics.pop("per_batch")
    row.update(metrics)
    bound_tools, bound_datasets = _bound_tools(episode, events)
    row["bound_tools"] = sorted(bound_tools)
    queries = [(str(r["tool"]), str(r["query"])) for b in per_batch for r in b["calls"]]
    # 失败 / 降级模板不算成果：第一次 429 批里 C2 的「仍需核验：…提供主要反证」这类兜底
    # 文案会撞上关键词。终态 failed 或公开答案不足 300 字时，答案类检查一律记未命中。
    answer_countable = row.get("terminal") != "failed" and len(answer) >= 300
    row["answer_countable"] = answer_countable
    hits = []
    for outcome_spec in case.get("key_outcomes") or []:
        check = outcome_spec.get("check") or {}
        try:
            ok = _check_outcome(
                check,
                answer=answer if answer_countable else "",
                bound_tools=bound_tools,
                bound_datasets=bound_datasets,
                queries=queries,
            )
        except ValueError as exc:
            ok = False
            row.setdefault("check_errors", []).append(str(exc))
        hits.append({"id": outcome_spec.get("id"), "hit": bool(ok)})
    row["key_outcomes"] = hits
    row["key_outcome_hits"] = sum(1 for h in hits if h["hit"])
    row["key_outcome_total"] = len(hits)
    if case.get("group") == "simple":
        row["simple_ok"] = bool(
            row["sub_research_requests"] == 0
            and int(row["tool_requests"]) <= 6
            and row["research_status"] == "completed"
        )
    return row


def _markdown(rows: list[dict], arm: str) -> str:
    lines = [
        f"### 臂 `{arm}` 读数",
        "",
        "| 题 | 终态 | 判官 | 耗时 s | 模型轮 | 工具 | 批 | 停滞批 | 重复对 | 停滞后换路 | 建议→换路 | 子研究 | 关键成果 | tokens in/out |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        if row.get("status") in {"no_probe", "no_run_dir"}:
            lines.append(f"| {row['case']} | {row.get('status')} | | | | | | | | | | | | |")
            continue
        lines.append(
            "| {case} | {research_status}/{terminal} | {judge} | {elapsed_s} | {model_turns} | {tool_requests} | {batches} | {stalled_batches} | {repeated_pairs} | {switched_after_stall}/{stall_opportunities} | {acted_on_suggestion}/{suggestions_given} | {sub_research_requests} | {key_outcome_hits}/{key_outcome_total} | {input_tokens}/{output_tokens} |".format(
                **{k: row.get(k) for k in (
                    "case", "research_status", "terminal", "judge", "elapsed_s", "model_turns", "tool_requests",
                    "batches", "stalled_batches", "repeated_pairs", "switched_after_stall", "stall_opportunities",
                    "acted_on_suggestion", "suggestions_given", "sub_research_requests", "key_outcome_hits",
                    "key_outcome_total", "input_tokens", "output_tokens",
                )}
            )
        )
    complex_rows = [r for r in rows if r.get("group") == "complex" and "key_outcome_hits" in r]
    simple_rows = [r for r in rows if r.get("group") == "simple" and "simple_ok" in r]
    lines.append("")
    lines.append(
        f"复杂题关键成果合计 {sum(int(r['key_outcome_hits']) for r in complex_rows)}/{sum(int(r['key_outcome_total']) for r in complex_rows)}"
        f"（{len(complex_rows)} 题有收据）；简单题无多 Agent 调度且 ≤6 次工具且 completed：{sum(1 for r in simple_rows if r['simple_ok'])}/{len(simple_rows)}。"
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--arm", required=True)
    parser.add_argument("--root", default=str(Path.home() / ".finance-runtime/cap06-20260909"))
    parser.add_argument("--json", action="store_true", help="同时打印 JSON 行")
    parser.add_argument("--users-root", default=None, help="缺省 <root>/users-<arm>")
    parser.add_argument("--episodes-root", default=None, help="缺省 <root>/episodes-<arm>")
    args = parser.parse_args()

    root = Path(args.root).expanduser()
    arm_dir = root / "arms" / args.arm
    users_root = Path(args.users_root).expanduser() if args.users_root else root / f"users-{args.arm}"
    episodes_root = (
        Path(args.episodes_root).expanduser() if args.episodes_root else root / f"episodes-{args.arm}"
    )
    if not arm_dir.is_dir():
        raise SystemExit(f"没有臂目录 {arm_dir}")
    cases = json.loads(FIXTURE.read_text(encoding="utf-8"))["cases"]
    rows = [read_case(case, arm_dir=arm_dir, users_root=users_root, episodes_root=episodes_root) for case in cases]
    (arm_dir / "readings.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(_markdown(rows, args.arm))
    if args.json:
        for row in rows:
            print(json.dumps(row, ensure_ascii=False))
    print(f"\nreadings → {arm_dir / 'readings.json'}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    sys.exit(main())
