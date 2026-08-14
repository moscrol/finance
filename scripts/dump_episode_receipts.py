#!/usr/bin/env python3
"""把一份验收 run JSON 展开成逐题的 episode 修复收据表。

防的失败形状：跨轮归因时每个 agent 手扒一遍 continuous-episode.json
（2026-08-12/13 的 R2→R5 四轮全是临时 heredoc 重新发明），且容易漏看
repair_model_retry 的 timeout_asked / seconds_granted——那两个数才能判
「重试窗口给对了没有」，光看 stop_reason 分不清「没重试」和「重试了但窗口太小」。

用法：
    python3 scripts/dump_episode_receipts.py <eval_run.json> \
        [--runs-dir ~/.local/share/finance-workbench/users/<uid>/runs] \
        [--case A7-mainline ...]

runs-dir 默认按 RunStore 的规则解析（FORESIGHT_USERS_DIR 优先）；
生产 8792 的用户目录不在仓内 intelligence/users/，别用相对路径猜。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _default_runs_dir(user: str) -> Path:
    sys.path.insert(0, str(REPO))
    from intelligence import userspace

    return userspace.user_space(user).root / "runs"


def _episode_lines(ep: dict) -> list[str]:
    lines: list[str] = []
    contract = ep.get("contract") or {}
    outcome = ep.get("outcome") or {}
    lines.append(
        f"tier={contract.get('research_tier')} qtype={contract.get('question_type')} "
        f"stop={outcome.get('stop_reason')} "
        f"repair={ep.get('repair_attempts')}/{ep.get('repair_cycles')}"
    )
    for event in ep.get("events") or []:
        kind = event.get("kind")
        payload = event.get("payload") or {}
        if kind == "repair_reentry":
            lines.append(
                f"  reentry granted={payload.get('granted_seconds')} "
                f"asked={round(float(payload.get('timeout_asked') or 0), 1)} "
                f"configured={payload.get('timeout_configured')}"
            )
        elif kind == "repair_model_retry":
            lines.append(
                f"  RETRY asked={round(float(payload.get('timeout_asked') or 0), 1)} "
                f"granted={payload.get('seconds_granted')} "
                f"grant_id={payload.get('grant_id')}"
            )
        elif kind == "model_turn" and payload.get("error"):
            lines.append(
                f"  model_err[{payload.get('phase') or 'main'}] {payload.get('error')}"
            )
        elif kind == "finish":
            slips = payload.get("caveat_slips")
            slips_s = slips if slips is not None else "<ABSENT>"
            lines.append(
                f"  finish stop={payload.get('stop_reason')} "
                f"status={payload.get('status')} "
                f"caveat_slips={slips_s}"
            )
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("eval_run", help="intelligence/eval/runs/*.json 验收产物")
    parser.add_argument("--runs-dir", help="run 目录根（默认按 userspace 规则解析）")
    parser.add_argument("--user", default="linxiaoqi5111")
    parser.add_argument("--case", action="append", help="只看指定题号，可重复")
    args = parser.parse_args()

    doc = json.loads(Path(args.eval_run).read_text(encoding="utf-8"))
    runs_dir = Path(args.runs_dir) if args.runs_dir else _default_runs_dir(args.user)

    for case in doc.get("cases") or []:
        case_id = case.get("case_id")
        if args.case and case_id not in args.case:
            continue
        turn = (case.get("turns") or [{}])[0]
        run_id = turn.get("run_id")
        print(
            f"\n{case_id}: elapsed={turn.get('elapsed_s')} status={turn.get('status')} "
            f"evidence={turn.get('evidence_bound')} degrades={len(turn.get('degrades') or [])}"
        )
        episode_path = runs_dir / str(run_id or "") / "continuous-episode.json"
        if not run_id or not episode_path.exists():
            print(f"  (no episode artifact: {episode_path})")
            continue
        for line in _episode_lines(json.loads(episode_path.read_text(encoding="utf-8"))):
            print(f"  {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
