from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from intelligence import userspace
from intelligence.paths import ProjectPaths, default_paths, vector_index_dir_for
from intelligence.runner import run_command_step
from intelligence.summary import WorkflowStep, WorkflowSummary, now_iso
from scripts.notify_feishu import send_alert


@dataclass(frozen=True)
class CommandSpec:
    name: str
    argv: list[str]
    outputs: list[str]
    timeout_sec: float | None = None

    @property
    def command_line(self) -> str:
        return " ".join(self.argv)


@dataclass(frozen=True)
class DailyReviewOptions:
    date: str
    user: str | None = None
    skip_sync: bool = False
    skip_long: bool = False
    skip_theme: bool = False
    skip_agent: bool = False
    skip_legacy_theme: bool = False
    skip_workbench: bool = False
    start_date: str | None = None
    dry_run: bool = False
    from_step: str | None = None
    only_step: str | None = None
    continue_on_warn: bool = False
    kb_wiki: str | Path | None = None
    step_timeout_sec: float = 1800
    alerts_enabled: bool = True
    alert_on_warn: bool = False

    def __post_init__(self) -> None:
        if self.step_timeout_sec <= 0:
            raise ValueError("step_timeout_sec must be positive")


def build_daily_review_plan(options: DailyReviewOptions, paths: ProjectPaths | None = None) -> list[CommandSpec]:
    paths = paths or default_paths()
    if options.kb_wiki:
        knowledge_wiki = Path(options.kb_wiki).expanduser()
        paths = ProjectPaths(
            finance_root=paths.finance_root,
            knowledge_wiki=knowledge_wiki,
            finance_site=paths.finance_site,
            market_snapshot_dir=paths.market_snapshot_dir,
            vector_index_dir=vector_index_dir_for(knowledge_wiki),
        )
    date = options.date
    exports = paths.market_exports
    daily_dir = paths.review_daily_root / date
    plan: list[CommandSpec] = []

    if not options.skip_sync:
        plan.append(CommandSpec(
            name="preflight-db-lock",
            argv=["python3", "scripts/check_db_lock.py"],
            outputs=[],
            timeout_sec=30,
        ))
        argv = ["python3", "-m", "market_feature_store.cli", "daily-update", "--trade-date", date]
        if options.skip_long:
            argv.append("--skip-long")
        argv.extend([
            "--status-json",
            str(paths.finance_root / "skills" / "daily-full-review" / "state" / f"daily-update-{date}.json"),
        ])
        plan.append(CommandSpec(name="daily-update", argv=argv, outputs=[]))

    plan.append(CommandSpec(
        name="quality-gate",
        argv=["python3", "scripts/check_daily_review_data.py", date, "--phase", "data"],
        outputs=[],
    ))

    plan.append(CommandSpec(
        name="cross-day-quality-gate",
        argv=[
            "python3", "-m", "market_feature_store.cli", "check-daily",
            "--trade-date", date,
            "--json", str(paths.finance_root / "skills" / "daily-full-review" / "state" / f"quality-{date}.json"),
        ],
        outputs=[],
    ))

    plan.append(CommandSpec(
        name="export-increment",
        argv=[
            "python3",
            "skills/daily-full-review/scripts/export_increment.py",
            "--date",
            date,
        ],
        outputs=[],
    ))

    review_argv = ["python3", "-m", "market_feature_store.cli", "daily-review", "--trade-date", date]
    if options.start_date:
        review_argv.extend(["--start-date", options.start_date])
    plan.append(CommandSpec(
        name="daily-review",
        argv=review_argv,
        outputs=[
            str(exports / f"{date}-daily-review.md"),
            str(exports / f"{date}-advancers-ma5.png"),
        ],
    ))

    plan.append(CommandSpec(
        name="daily-review-html",
        argv=["python3", "scripts/render_daily_review_briefing.py", date],
        outputs=[str(daily_dir / f"{date}-daily-review.html")],
    ))

    # 框架解读（perspective-lab P1）：按 user_framework 画像解读当日硬数据，
    # 判断自动落 T+1/T+3 checkpoint（带 framework_version）；profile 缺失时该步优雅跳过（exit 0）。
    plan.append(CommandSpec(
        name="framework-interpretation",
        argv=[
            "python3", "-m", "intelligence.cli", "perspective", "framework-daily",
            "--date", date,
            "--daily-review-md", str(exports / f"{date}-daily-review.md"),
            "--out-md", str(exports / f"{date}-framework-interpretation.md"),
        ],
        outputs=[],
    ))

    # T+1/T+3 回检：到期可证伪点交给 resolver 核对并落 verdicts（缺数据自动 unverifiable，不编造）。
    plan.append(CommandSpec(
        name="checkpoint-recheck",
        argv=[
            "python3", "-m", "intelligence.cli", "checkpoint", "recheck",
            "--date", date, "--kb-wiki", str(paths.knowledge_wiki), "--apply",
        ],
        outputs=[],
    ))

    if not options.skip_theme:
        plan.append(CommandSpec(
            name="theme-candidates",
            argv=[
                "python3",
                "-m",
                "intelligence.cli",
                "theme",
                "--date",
                date,
                "--market-triggered",
                "--out-json",
                str(exports / f"{date}-theme-candidates.json"),
                "--out-md",
                str(exports / f"{date}-theme-candidates.md"),
            ],
            outputs=[
                str(exports / f"{date}-theme-candidates.json"),
                str(exports / f"{date}-theme-candidates.md"),
            ],
        ))
        plan.append(CommandSpec(
            name="theme-backfill-queue",
            argv=["python3", "scripts/build_theme_backfill_queue.py", date],
            outputs=[str(exports / f"{date}-theme-backfill-queue.json")],
        ))
        plan.append(CommandSpec(
            name="theme-backfill-review-queue",
            argv=["python3", "scripts/build_theme_backfill_review_queue.py", date],
            outputs=[
                str(exports / f"{date}-theme-backfill-review-queue.json"),
                str(exports / f"{date}-theme-backfill-review-queue.md"),
            ],
        ))
        plan.append(CommandSpec(
            name="theme-candidates-html",
            argv=["python3", "scripts/render_theme_candidates_workbench_html.py", date],
            outputs=[str(daily_dir / f"{date}-theme-candidates.html")],
        ))
        if not options.skip_legacy_theme:
            plan.append(CommandSpec(
                name="legacy-market-triggered-theme-brief-html",
                argv=["python3", "scripts/render_market_triggered_theme_brief_html.py", date],
                outputs=[
                    str(exports / f"{date}-triggered-themes.json"),
                    str(exports / f"{date}-market-triggered-theme-brief.md"),
                    str(daily_dir / f"{date}-market-triggered-theme-brief.html"),
                ],
            ))

        if not options.skip_agent:
            plan.append(CommandSpec(
                name="agent-daily",
                argv=[
                    "python3",
                    "-m",
                    "intelligence.cli",
                    "agent-daily",
                    "--date",
                    date,
                    "--kb-wiki",
                    str(paths.knowledge_wiki),
                    "--out-json",
                    str(exports / f"{date}-daily-agent.json"),
                    "--out-md",
                    str(exports / f"{date}-daily-agent.md"),
                    "--out-html",
                    str(daily_dir / f"{date}-daily-agent.html"),
                    "--semantic-rag-top-n",
                    "0",
                ],
                outputs=[
                    str(exports / f"{date}-research-queue.json"),
                    str(exports / f"{date}-research-queue.md"),
                    str(daily_dir / f"{date}-research-queue.html"),
                    str(exports / f"{date}-daily-agent.json"),
                    str(exports / f"{date}-daily-agent.md"),
                    str(daily_dir / f"{date}-daily-agent.html"),
                ],
            ))
            # 只归档到 wiki/raw；不 apply、不改 relations。缺文件或失败由 CLI 退出 0。
            plan.append(CommandSpec(
                name="kb-ingest-receive",
                argv=[
                    "python3",
                    "-m",
                    "intelligence.cli",
                    "kb-queue-receive",
                    "--date",
                    date,
                    "--finance-root",
                    str(paths.finance_root),
                    "--kb-wiki",
                    str(paths.knowledge_wiki),
                ],
                outputs=[],
            ))
            plan.append(CommandSpec(
                name="ima-gap-report",
                argv=[
                    "python3",
                    "-m",
                    "intelligence.cli",
                    "ima-gap-report",
                    "--date",
                    date,
                    "--kb-wiki",
                    str(paths.knowledge_wiki),
                    "--finance-root",
                    str(paths.finance_root),
                ],
                outputs=[
                    str(exports / f"{date}-ima-gap.json"),
                    str(exports / f"{date}-ima-gap.md"),
                ],
            ))

    plan.append(CommandSpec(
        name="strategy1-matrix-draft",
        argv=["python3", "scripts/generate_strategy1_mechanical_row.py", "--date", date],
        outputs=[str(paths.finance_root / "复盘" / "matrices" / "strategy1-priority-stock-matrix.html")],
    ))
    plan.append(CommandSpec(
        name="strategy3-matrix",
        argv=["python3", "scripts/backfill_strategy3_touch_matrix.py", "--append-missing"],
        outputs=[str(paths.finance_root / "复盘" / "matrices" / "strategy3-touch-up-rebound-matrix.html")],
    ))
    plan.append(CommandSpec(
        name="strategy4-matrix",
        argv=["python3", "scripts/render_strategy4_dual_engine_matrix.py", "--end", date],
        outputs=[str(paths.finance_root / "复盘" / "matrices" / "strategy4-dual-engine-matrix.html")],
    ))

    if not options.skip_workbench:
        plan.append(CommandSpec(
            name="review-workbench",
            argv=["python3", "scripts/render_review_workbench.py"],
            outputs=[str(paths.review_workbench)],
        ))
        plan.append(CommandSpec(
            name="cockpit",
            argv=["python3", "scripts/render_cockpit.py", "--knowledge-root", str(paths.knowledge_wiki.parent)],
            outputs=[str(paths.finance_root / "复盘" / "index.html")],
        ))

    return plan


def filter_plan(plan: list[CommandSpec], options: DailyReviewOptions) -> tuple[list[CommandSpec], list[str]]:
    warnings: list[str] = []
    step_names = [step.name for step in plan]
    if options.from_step and options.only_step:
        return [], ["--from-step and --only-step cannot be used together"]
    if options.from_step:
        if options.from_step not in step_names:
            return [], [f"unknown --from-step: {options.from_step}; allowed: {', '.join(step_names)}"]
        index = step_names.index(options.from_step)
        warnings.append(f"starting from step: {options.from_step}")
        release_index = step_names.index("export-increment")
        if index > release_index:
            prerequisites = [
                step
                for step in plan
                if step.name in {"quality-gate", "cross-day-quality-gate", "export-increment"}
            ]
            warnings.append("pre-report quality gates and export were prepended; downstream steps cannot bypass them")
            return prerequisites + plan[index:], warnings
        return plan[index:], warnings
    if options.only_step:
        if options.only_step not in step_names:
            return [], [f"unknown --only-step: {options.only_step}; allowed: {', '.join(step_names)}"]
        warnings.append(f"running only step: {options.only_step}")
        index = step_names.index(options.only_step)
        release_index = step_names.index("export-increment")
        selected = [step for step in plan if step.name == options.only_step]
        if index > release_index:
            prerequisites = [
                step
                for step in plan
                if step.name in {"quality-gate", "cross-day-quality-gate", "export-increment"}
            ]
            warnings.append("pre-report quality gates and export were prepended; downstream steps cannot bypass them")
            return prerequisites + selected, warnings
        return selected, warnings
    return plan, warnings


def summary_inputs(options: DailyReviewOptions, dry_run: bool) -> dict:
    return {
        "date": options.date,
        "user": options.user,
        "skip_sync": options.skip_sync,
        "skip_long": options.skip_long,
        "skip_theme": options.skip_theme,
        "skip_agent": options.skip_agent,
        "skip_legacy_theme": options.skip_legacy_theme,
        "skip_workbench": options.skip_workbench,
        "start_date": options.start_date,
        "from_step": options.from_step,
        "only_step": options.only_step,
        "continue_on_warn": options.continue_on_warn,
        "kb_wiki": str(options.kb_wiki) if options.kb_wiki else None,
        "step_timeout_sec": options.step_timeout_sec,
        "alerts_enabled": options.alerts_enabled,
        "alert_on_warn": options.alert_on_warn,
        "dry_run": dry_run,
    }


def invalid_plan_summary(options: DailyReviewOptions, errors: list[str], dry_run: bool) -> WorkflowSummary:
    summary = WorkflowSummary(
        workflow="daily",
        status="FAIL",
        started_at=now_iso(),
        inputs=summary_inputs(options, dry_run),
        errors=errors,
        next_actions=["Adjust --from-step/--only-step or run --dry-run to inspect the available plan."],
    )
    summary.finish("FAIL")
    return summary


def can_downgrade_daily_update_failure(step: WorkflowStep, options: DailyReviewOptions) -> bool:
    if not options.continue_on_warn:
        return False
    if step.name != "daily-update":
        return False
    if step.status != "FAIL":
        return False
    structured = step.structured_result or {}
    return structured.get("status") == "WARN" and structured.get("recoverable") is True


def downgrade_daily_update_failure(step: WorkflowStep) -> None:
    step.status = "WARN"
    step.warnings.append("daily-update returned structured WARN status; downgraded by --continue-on-warn")
    step.errors = []


def notify_daily_review(summary: WorkflowSummary, options: DailyReviewOptions) -> None:
    should_alert = summary.status == "FAIL" or (
        summary.status == "WARN" and options.alert_on_warn
    )
    if not options.alerts_enabled or not should_alert:
        return
    failed_steps = [step.name for step in summary.steps if step.status == "FAIL"]
    warning_steps = [step.name for step in summary.steps if step.status == "WARN"]
    parts = [
        f"[daily-review {summary.status}] date={options.date}",
        f"failed={','.join(failed_steps) or '-'}",
        f"warn={','.join(warning_steps) or '-'}",
    ]
    if summary.errors:
        parts.append(f"error={summary.errors[0]}")
    if not send_alert(" | ".join(parts)):
        summary.warnings.append("operational alert delivery failed")


def record_daily_review_metrics(
    summary: WorkflowSummary,
    options: DailyReviewOptions,
) -> None:
    record = {
        "ts": summary.finished_at or now_iso(),
        "workflow_id": f"daily:{options.date}:{summary.started_at}",
        "workflow": summary.workflow,
        "date": options.date,
        "status": summary.status,
        "failed_steps": [
            step.name for step in summary.steps if step.status == "FAIL"
        ],
        "duration_sec": round(
            sum(step.duration_sec or 0 for step in summary.steps),
            3,
        ),
        "degradations": list(summary.warnings),
    }
    path = userspace.user_space(options.user).root / "workflow_metrics.jsonl"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError as exc:
        summary.warnings.append(f"workflow metrics write failed: {exc}")


def dry_run_daily_review(options: DailyReviewOptions, paths: ProjectPaths | None = None) -> WorkflowSummary:
    base_plan = build_daily_review_plan(options, paths)
    plan, plan_messages = filter_plan(base_plan, options)
    if not plan and plan_messages:
        return invalid_plan_summary(options, plan_messages, dry_run=True)
    summary = WorkflowSummary(
        workflow="daily",
        status="SKIP",
        started_at=now_iso(),
        inputs=summary_inputs(options, dry_run=True),
        warnings=plan_messages,
        next_actions=["Run without --dry-run after reviewing the command plan."],
    )
    summary.steps = [
        WorkflowStep(
            name=step.name,
            status="SKIP",
            command=step.command_line,
            outputs=step.outputs,
            warnings=["dry-run only; command not executed"],
        )
        for step in plan
    ]
    summary.outputs = [output for step in plan for output in step.outputs]
    summary.finish("SKIP")
    return summary


def run_daily_review(options: DailyReviewOptions, paths: ProjectPaths | None = None) -> WorkflowSummary:
    paths = paths or default_paths()
    base_plan = build_daily_review_plan(options, paths)
    plan, plan_messages = filter_plan(base_plan, options)
    if not plan and plan_messages:
        summary = invalid_plan_summary(options, plan_messages, dry_run=False)
        notify_daily_review(summary, options)
        record_daily_review_metrics(summary, options)
        return summary
    summary = WorkflowSummary(
        workflow="daily",
        status="PASS",
        started_at=now_iso(),
        inputs=summary_inputs(options, dry_run=False),
        warnings=plan_messages,
    )

    blocked = False
    for step in plan:
        if blocked:
            summary.steps.append(WorkflowStep(
                name=step.name,
                status="SKIP",
                command=step.command_line,
                outputs=step.outputs,
                warnings=["skipped because a previous required step failed"],
            ))
            continue
        result = run_command_step(
            step.name,
            step.argv,
            cwd=paths.finance_root,
            outputs=step.outputs,
            timeout_sec=step.timeout_sec or options.step_timeout_sec,
        )
        if can_downgrade_daily_update_failure(result, options):
            downgrade_daily_update_failure(result)
        summary.steps.append(result)
        if result.status == "FAIL":
            blocked = True

    summary.outputs = [output for step in summary.steps if step.status in {"PASS", "WARN"} for output in step.outputs]
    summary.errors = [error for step in summary.steps for error in step.errors]
    summary.warnings = summary.warnings + [warning for step in summary.steps for warning in step.warnings]
    if any(step.status == "FAIL" for step in summary.steps):
        summary.next_actions.append("Fix the failed step, then re-run the workflow from the appropriate point.")
        summary.finish("FAIL")
    elif any(step.status == "WARN" for step in summary.steps):
        summary.next_actions.append("Review warnings before treating the workflow as fully clean.")
        summary.finish("WARN")
    elif any(step.status == "SKIP" for step in summary.steps):
        summary.finish("WARN")
    else:
        summary.finish("PASS")
    notify_daily_review(summary, options)
    record_daily_review_metrics(summary, options)
    return summary
