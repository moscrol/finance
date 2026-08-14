from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from intelligence.services import refresh_profile as svc
from intelligence.summary import WorkflowStep, WorkflowSummary, now_iso
from intelligence.userspace import effective_profile, user_space


@dataclass(frozen=True)
class RefreshProfileWorkflowOptions:
    user: str | None = None
    lookback: int = 20
    date: str | None = None
    top: int = 12
    kb_wiki: str | Path | None = None
    db_path: str | Path | None = None
    apply: bool = False


def run_refresh_profile(
    options: RefreshProfileWorkflowOptions,
) -> tuple[WorkflowSummary, dict, dict, str]:
    summary = WorkflowSummary(
        workflow="refresh-profile",
        status="PASS",
        started_at=now_iso(),
        inputs={
            "user": options.user or "default",
            "date": options.date,
            "top": options.top,
            "apply": options.apply,
        },
    )

    us = user_space(options.user)
    current_profile, profile_warnings = effective_profile(us)

    proposal = svc.derive(
        svc.RefreshOptions(
            user=us.user_id,
            lookback=options.lookback,
            date=options.date,
            top=options.top,
            kb_wiki=options.kb_wiki,
            db_path=options.db_path,
        )
    )
    diff = svc.diff_against_profile(current_profile, proposal)

    srcs = proposal.get("sources", {})
    summary.steps.append(
        WorkflowStep(
            name="sources",
            status="PASS" if (srcs.get("duckdb", {}).get("ok") or srcs.get("kb", {}).get("ok")) else "WARN",
            outputs=[
                f"duckdb={'ok' if srcs.get('duckdb', {}).get('ok') else 'off'}",
                f"kb={'ok' if srcs.get('kb', {}).get('ok') else 'off'}",
                f"duckdb_as_of={proposal.get('as_of', {}).get('duckdb')}",
                f"kb_as_of={proposal.get('as_of', {}).get('kb')}",
            ],
        )
    )
    summary.steps.append(
        WorkflowStep(
            name="derive",
            status="PASS" if proposal.get("focus_themes") or proposal.get("watchlist") else "WARN",
            outputs=[
                f"focus_candidates={len(proposal.get('focus_themes') or [])}",
                f"watch_candidates={len(proposal.get('watchlist') or [])}",
                f"new_themes={len(diff.get('new_themes') or [])}",
                f"new_watchlist={len(diff.get('new_watchlist') or [])}",
            ],
        )
    )

    applied_path = None
    if options.apply:
        applied_path, stats = svc.apply_derived(us, proposal)
        summary.steps.append(
            WorkflowStep(
                name="apply",
                status="PASS",
                outputs=[f"path={applied_path}", *[f"{k}={v}" for k, v in stats.items()]],
            )
        )
    else:
        summary.steps.append(WorkflowStep(name="apply", status="SKIP", outputs=["preview only (no --apply)"]))

    answer = svc.render(proposal, diff, applied_path=applied_path)

    summary.warnings = list(profile_warnings) + list(proposal.get("warnings") or [])
    summary.outputs = [t["theme"] for t in diff.get("new_themes") or []]
    summary.next_actions = [
        "审阅 diff 后用 `--apply` 落盘 profile.derived.json；钉住项请手动写进 profile.json。",
        "PR2：用 interactions.jsonl 的点击/采纳反馈给常互动题材升权、给未碰派生项加速衰减。",
    ]
    summary.finish(proposal.get("status", "PASS"))
    return summary, proposal, diff, answer
