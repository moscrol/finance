#!/usr/bin/env python3
"""模型准入闸：逐回合核对「请求的模型」与「对端实际服务的模型」（2026-10-01 质检 P0③）。

09-29 实验配的是 glm-5.3，事后才发现实际跑的是 glm-5.3-flash；08-08 也出过 health
报 glm-5.2、实际跑 gpt-5.6-sol。A/B 读数在这种情况下没有意义，所以实验收据必须
先过这道闸。

输入：一个或多个 episode 的 ``events.jsonl``（或包含它们的目录，递归找）。
输出：每个 episode 一行 JSON 摘要；``--json`` 时整体输出一个 JSON 对象。

退出码：
  0  全部回合 requested == served
  1  至少一个回合不一致（served_model_mismatch）
  2  无不一致，但有回合判不了（对端没回 model 字段 / 没记 requested_model），且带了 --strict
  3  输入里找不到任何 model_turn 事件
用法：
  python3 scripts/check_served_model.py ~/.finance-runtime/<实验目录> --expect glm-5.3
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from intelligence.services.agent_runtime import served_model_mismatch  # noqa: E402


def _event_files(paths: list[Path]) -> list[Path]:
    out: list[Path] = []
    for path in paths:
        if path.is_dir():
            out.extend(sorted(path.rglob("events.jsonl")))
        elif path.is_file():
            out.append(path)
    return out


def summarize(events_path: Path, expect: str | None = None) -> dict[str, object]:
    requested: set[str] = set()
    served: set[str] = set()
    turns = mismatched = undecidable = 0
    for line in events_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        event = json.loads(line)
        if event.get("kind") != "model_turn":
            continue
        payload = event.get("payload") or {}
        if payload.get("served_model") is None and payload.get("provider_attempts") == 0:
            continue  # 没到达 provider 的回合不参与比对
        turns += 1
        want = expect or payload.get("requested_model")
        got = payload.get("served_model")
        if isinstance(payload.get("requested_model"), str):
            requested.add(payload["requested_model"])
        if isinstance(got, str) and got:
            served.add(got)
        verdict = served_model_mismatch(want, got)
        if verdict is None:
            undecidable += 1
        elif verdict:
            mismatched += 1
    return {
        "events": str(events_path),
        "model_turns": turns,
        "requested_models": sorted(requested),
        "served_models": sorted(served),
        "expected_model": expect,
        "mismatched_turns": mismatched,
        "undecidable_turns": undecidable,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--expect", help="以这个模型名为准核对（覆盖事件里的 requested_model）")
    parser.add_argument("--strict", action="store_true", help="判不了的回合也算不通过（退出 2）")
    parser.add_argument("--json", action="store_true", help="输出单个 JSON 对象")
    args = parser.parse_args(argv)

    rows = [summarize(path, args.expect) for path in _event_files(args.paths)]
    rows = [row for row in rows if row["model_turns"]]
    total = {
        "episodes": len(rows),
        "model_turns": sum(int(r["model_turns"]) for r in rows),
        "mismatched_turns": sum(int(r["mismatched_turns"]) for r in rows),
        "undecidable_turns": sum(int(r["undecidable_turns"]) for r in rows),
        "served_models": sorted({m for r in rows for m in r["served_models"]}),
    }
    if args.json:
        print(json.dumps({"total": total, "episodes": rows}, ensure_ascii=False, indent=2))
    else:
        for row in rows:
            print(json.dumps(row, ensure_ascii=False))
        print(json.dumps({"total": total}, ensure_ascii=False))
    if not rows:
        print("[check_served_model] 找不到任何 model_turn 事件", file=sys.stderr)
        return 3
    if total["mismatched_turns"]:
        print(f"[check_served_model] ✗ {total['mismatched_turns']} 个回合实际服务的模型与请求不一致："
              f"{total['served_models']}", file=sys.stderr)
        return 1
    if args.strict and total["undecidable_turns"]:
        print(f"[check_served_model] ✗ {total['undecidable_turns']} 个回合判不了（对端未回 model 字段）",
              file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
