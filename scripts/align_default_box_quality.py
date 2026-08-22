#!/usr/bin/env python3
"""默认盒 vs 对照树：解耦后「模型看见的那一层」必须对齐。

质量棘轮的第一刀不是 live 答案字符串——同一模型连跑两次也会漂。
解耦验收是：默认不拧开关时，路由 / 授权面 / 宪法 / 预取 与对照树一致。
对照树必须是**当前主链**（本脚本 --control），不能是这棵树改之前的旧 HEAD。

用法（cwd 随意；路径一律走参数，不写死家目录）：

    python3 scripts/align_default_box_quality.py \\
        --treated <解耦树> --control <当前主链树> --db <duckdb>

本文件只允许 import 主链上也有的符号，这样同一份脚本能在对照树里跑 dump。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any

CASES = Path("intelligence/tests/fixtures/episode_seam_ladder_cases.json")

CASE_FIELDS = (
    "question_type",
    "subject",
    "dated_market_review",
    "capabilities",
    "allowed_capabilities",
    "mandatory_capabilities",
    "prefetch",
    "dual_red_counts",
)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def dump_surface() -> dict[str, Any]:
    """在 *cwd 这棵树* 上解算默认盒表面。"""

    repo = Path.cwd()
    if str(repo) not in sys.path:
        sys.path.insert(0, str(repo))

    from intelligence.paths import default_market_db_path
    from intelligence.runtime.glm_agent_runtime import GLMAgentRuntime
    from intelligence.services.asof_prefetch import (
        _connect,
        _prior_trade_dates,
        collect_prefetch_items,
        dual_red_counts,
    )
    from intelligence.services.episode_factory import build_episode_context
    from intelligence.services.foresight import ForesightOptions, load_methodology
    from intelligence.services.query_understanding import (
        is_dated_market_review,
        understand_query,
    )
    from intelligence.services.research_contract import release_root_budget
    from market_feature_store.signals import DOUBLE_RED_SQL
    from scripts.run_episode_seam_ladder import load_cases, resolve_control

    methodology, methodology_path, methodology_warn = load_methodology(ForesightOptions())
    db_path = default_market_db_path()
    con = _connect(db_path)
    cases: list[dict[str, Any]] = []
    try:
        for case in load_cases(repo / CASES):
            envelope = understand_query(case.question)
            control = resolve_control(case)
            frame = control.task_frame
            as_of = date.fromisoformat(case.as_of)
            prefetch = collect_prefetch_items(
                question=case.question,
                question_type=frame.question_type,
                subject=frame.subject or "",
                as_of=as_of,
            )
            counts: dict[str, Any] = {}
            if con is not None:
                days = _prior_trade_dates(con, as_of, 3)
                if days:
                    counts = dual_red_counts(con, days)
            episode_id = f"align-default:{case.case_id}"
            try:
                ctx = build_episode_context(
                    frame,
                    task_id=episode_id,
                    capabilities=control.capabilities,
                    tier=case.tier,
                    timeout=case.timeout,
                    today=case.as_of,
                    latest_data_date=case.as_of,
                    synthesis_reserve=GLMAgentRuntime.synthesis_reserve_for_task(
                        tier=case.tier,
                        question_type=frame.question_type,
                    ),
                )
                allowed = list(ctx.contract.allowed_capabilities)
                mandatory = list(ctx.contract.evidence_plan.mandatory_capabilities)
            finally:
                release_root_budget(episode_id)
            cases.append(
                {
                    "id": case.case_id,
                    "question": case.question,
                    "as_of": case.as_of,
                    "question_type": frame.question_type,
                    "subject": frame.subject,
                    "dated_market_review": is_dated_market_review(case.question, envelope),
                    "capabilities": list(control.capabilities),
                    "allowed_capabilities": allowed,
                    "mandatory_capabilities": mandatory,
                    "prefetch": [
                        {"title": item.title, "detail_sha": _sha(item.detail)}
                        for item in prefetch
                    ],
                    "dual_red_counts": counts,
                }
            )
    finally:
        if con is not None:
            con.close()
    return {
        "db_path": str(db_path),
        "db_connected": con is not None,
        "double_red_sql": DOUBLE_RED_SQL,
        "methodology_sha": _sha(methodology),
        "methodology_path": methodology_path,
        "methodology_warn": methodology_warn,
        "methodology_chars": len(methodology),
        "cases": cases,
    }


def _run_dump(
    tree: Path,
    python: Path,
    script: Path,
    *,
    db: Path | None,
) -> dict[str, Any]:
    env = os.environ.copy()
    if db is not None:
        env["MARKET_FEATURE_STORE_DB"] = str(db.resolve())
    proc = subprocess.run(
        [str(python), str(script), "--dump-only"],
        cwd=str(tree),
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(proc.stdout)


def _diff(treated: dict[str, Any], control: dict[str, Any]) -> list[str]:
    gaps: list[str] = []
    if not treated.get("db_connected") or not control.get("db_connected"):
        gaps.append(
            f"db not connected treated={treated.get('db_connected')} "
            f"control={control.get('db_connected')} path={treated.get('db_path')}"
        )
    for key in ("double_red_sql", "methodology_sha", "methodology_chars"):
        if treated.get(key) != control.get(key):
            gaps.append(f"{key}: treated={treated.get(key)!r} control={control.get(key)!r}")
    treated_cases = {item["id"]: item for item in treated["cases"]}
    control_cases = {item["id"]: item for item in control["cases"]}
    if treated_cases.keys() != control_cases.keys():
        gaps.append(f"case ids: {sorted(treated_cases)} vs {sorted(control_cases)}")
        return gaps
    for case_id, left in treated_cases.items():
        right = control_cases[case_id]
        for field in CASE_FIELDS:
            if left.get(field) != right.get(field):
                gaps.append(
                    f"{case_id}.{field}: treated={left.get(field)!r} control={right.get(field)!r}"
                )
    return gaps


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dump-only", action="store_true", help="只向 stdout 打一份表面 JSON")
    parser.add_argument("--treated", type=Path, help="解耦后的树")
    parser.add_argument("--control", type=Path, help="当前主链树")
    parser.add_argument(
        "--python",
        type=Path,
        default=Path(sys.executable),
        help="两棵树共用的解释器（默认=正在跑本脚本的那个）",
    )
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument(
        "--db",
        type=Path,
        default=None,
        help="两棵树共用的 DuckDB。不传则看 MARKET_FEATURE_STORE_DB / FINANCE_WS",
    )
    args = parser.parse_args(argv)

    if args.db is not None:
        os.environ["MARKET_FEATURE_STORE_DB"] = str(args.db.resolve())

    if args.dump_only:
        json.dump(dump_surface(), sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return 0

    if args.treated is None or args.control is None:
        parser.error("对打需要 --treated 和 --control")
    script = Path(__file__).resolve()
    treated = _run_dump(args.treated.resolve(), args.python, script, db=args.db)
    control = _run_dump(args.control.resolve(), args.python, script, db=args.db)
    gaps = _diff(treated, control)
    report = {
        "treated_root": str(args.treated.resolve()),
        "control_root": str(args.control.resolve()),
        "aligned": not gaps,
        "gaps": gaps,
        "treated": treated,
        "control": control,
    }
    text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    if gaps:
        print(f"❌ 默认盒与主链未对齐（{len(gaps)} 处）")
        for gap in gaps:
            print(f"  - {gap}")
        return 1
    print("✅ 默认盒与主链对齐：路由 / 授权面 / 宪法 / 预取 / 双红 SQL 一致")
    print(
        f"   题 {len(treated['cases'])} 道 · 宪法 {treated['methodology_chars']} 字 · "
        f"SQL {treated['double_red_sql']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
