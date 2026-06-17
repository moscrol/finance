from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from intelligence.services.foresight import ForesightOptions, ForesightResult, generate, render
from intelligence.summary import WorkflowStep, WorkflowSummary, now_iso


@dataclass(frozen=True)
class ForesightWorkflowOptions:
    profile: str | Path | None = None
    user: str | None = None
    news_file: str | Path | None = None
    date: str | None = None
    exports_dir: str | Path | None = None
    kb_wiki: str | Path | None = None
    n: int = 3
    candidates: int = 8
    llm_model: str | None = None
    llm_timeout: int = 60
    temperature: float = 0.8
    memory_file: str | Path | None = None
    use_memory: bool = True
    memory_window: int = 50
    interactions_file: str | Path | None = None
    use_interactions: bool = True
    interactions_window: int = 200
    affinity_half_life: float = 14.0
    affinity_boost: float = 0.2


def run_foresight(options: ForesightWorkflowOptions) -> tuple[WorkflowSummary, ForesightResult, str]:
    summary = WorkflowSummary(
        workflow="foresight",
        status="PASS",
        started_at=now_iso(),
        inputs={
            "user": options.user or "default",
            "profile": str(options.profile or "(user-space)"),
            "date": options.date,
            "n": options.n,
        },
    )
    result = generate(
        ForesightOptions(
            profile=options.profile,
            user=options.user,
            news_file=options.news_file,
            date=options.date,
            exports_dir=options.exports_dir,
            kb_wiki=options.kb_wiki,
            n=options.n,
            candidates=options.candidates,
            llm_model=options.llm_model,
            llm_timeout=options.llm_timeout,
            temperature=options.temperature,
            memory_file=options.memory_file,
            use_memory=options.use_memory,
            memory_window=options.memory_window,
            interactions_file=options.interactions_file,
            use_interactions=options.use_interactions,
            interactions_window=options.interactions_window,
            affinity_half_life=options.affinity_half_life,
            affinity_boost=options.affinity_boost,
        )
    )
    answer = render(result)

    summary.steps.append(
        WorkflowStep(
            name="context",
            status="PASS" if result.trade_date else "WARN",
            outputs=[f"trade_date={result.trade_date}", f"profile={result.profile_name}"],
        )
    )
    summary.steps.append(
        WorkflowStep(
            name="llm-generate",
            status="PASS" if result.llm_used else "WARN",
            outputs=[f"provider={result.llm_provider or '-'}", f"questions={len(result.questions)}"],
        )
    )
    summary.steps.append(
        WorkflowStep(
            name="memory",
            status="PASS" if options.use_memory else "SKIP",
            outputs=[
                f"loaded={result.memory_loaded}",
                f"appended={result.memory_appended}",
                f"path={result.memory_path or '-'}",
            ],
        )
    )
    summary.steps.append(
        WorkflowStep(
            name="interactions",
            status="PASS" if options.use_interactions else "SKIP",
            outputs=[
                f"loaded={result.interactions_loaded}",
                f"boosted={result.affinity_applied}",
                f"path={result.interactions_path or '-'}",
            ],
        )
    )
    summary.warnings = list(result.warnings)
    summary.outputs = [q.question for q in result.questions]
    summary.next_actions = [
        "接入实时情报源（财经日历/新闻 web-access）替代手动 --news-file。",
        "把每条问题落回 daily-loop：记录用户点过哪条 → 反馈进画像，提升相关度。",
    ]
    summary.finish(result.status)
    return summary, result, answer
