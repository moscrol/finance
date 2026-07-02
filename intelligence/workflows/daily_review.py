from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from intelligence.paths import ProjectPaths, default_paths, vector_index_dir_for
from intelligence.runner import run_command_step
from intelligence.summary import WorkflowStep, WorkflowSummary, now_iso


@dataclass(frozen=True)
class CommandSpec:
    name: str
    argv: list[str]
    outputs: list[str]

    @property
    def command_line(self) -> str:
        return " ".join(self.argv)


@dataclass(frozen=True)
class DailyReviewOptions:
    date: str
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
        ))
        argv = ["python3", "-m", "market_feature_store.cli", "daily-update", "--trade-date", date]
        if options.skip_long:
            argv.append("--skip-long")
        plan.append(CommandSpec(name="daily-update", argv=argv, outputs=[]))

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
        name="quality-gate",
        argv=["python3", "scripts/check_daily_review_data.py", date],
        outputs=[],
    ))

    plan.append(CommandSpec(
        name="daily-review-html",
        argv=["python3", "scripts/render_daily_review_briefing.py", date],
        outputs=[str(daily_dir / f"{date}-daily-review.html")],
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
                ],
                outputs=[
                    str(exports / f"{date}-daily-agent.json"),
                    str(exports / f"{date}-daily-agent.md"),
                    str(daily_dir / f"{date}-daily-agent.html"),
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
        return plan[index:], warnings
    if options.only_step:
        if options.only_step not in step_names:
            return [], [f"unknown --only-step: {options.only_step}; allowed: {', '.join(step_names)}"]
        warnings.append(f"running only step: {options.only_step}")
        return [step for step in plan if step.name == options.only_step], warnings
    return plan, warnings


def summary_inputs(options: DailyReviewOptions, dry_run: bool) -> dict:
    return {
        "date": options.date,
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
    combined_tail = "\n".join(step.stdout_tail + step.stderr_tail)
    return "质检: OK" in combined_tail


def downgrade_daily_update_failure(step: WorkflowStep) -> None:
    step.status = "WARN"
    step.warnings.append("daily-update returned non-zero but stdout_tail contains 质检: OK; downgraded by --continue-on-warn")
    step.errors = []


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
        return invalid_plan_summary(options, plan_messages, dry_run=False)
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
        result = run_command_step(step.name, step.argv, cwd=paths.finance_root, outputs=step.outputs)
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
    return summary
