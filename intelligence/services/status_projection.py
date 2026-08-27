"""三份 artifact status 的唯一投影（R-20260816-18）。

``continuous-episode.json`` 的 ``outcome.status`` 是研究终态。
``run.json`` / ``report.json`` 必须从它（与 delivery status 的合流）投影，
不能各自发明。合流规则：研究失败赢——有缺口文案也不能把 failed 升成
completed。这样 ``outcome=failed ∧ run.json=completed`` 不会再出现。

delivery 仍可以是 degraded/partial（证据边界降级、核验未齐），那些
``run.json=completed`` 是「请求走完了」，不是「研究成功了」。
"""

from __future__ import annotations

from dataclasses import dataclass

_EPISODE_STATUSES = frozenset(
    {"completed", "partial", "degraded", "failed", "cancelled"}
)


@dataclass(frozen=True)
class ArtifactStatuses:
    episode: str
    run: str
    report: str
    report_business: str
    transport: str


def coalesce_episode_status(
    turn_status: str,
    outcome_status: str | None,
) -> str:
    """研究失败压过 delivery 降级；其余保留 delivery 自己的档。"""

    turn = str(turn_status or "").strip()
    outcome = str(outcome_status or "").strip()
    if outcome == "failed" or turn == "failed":
        return "failed"
    if outcome == "cancelled" or turn == "cancelled":
        return "cancelled"
    # 运输 completed 不能盖掉研究未完成，否则会投影成 business_status=complete。
    if turn == "completed" and outcome in {"partial", "degraded"}:
        return outcome
    return turn or "failed"


def episode_status_from_turn(result: object) -> str:
    artifact = getattr(result, "private_artifact", None) or {}
    outcome_status = None
    if isinstance(artifact, dict):
        outcome = artifact.get("outcome")
        if isinstance(outcome, dict):
            raw = str(outcome.get("status") or "").strip()
            outcome_status = raw or None
    return coalesce_episode_status(
        str(getattr(result, "status", "") or ""),
        outcome_status,
    )


def project_artifact_statuses(episode_status: str) -> ArtifactStatuses:
    status = str(episode_status or "").strip()
    if status not in _EPISODE_STATUSES:
        status = "failed"
    if status == "failed":
        return ArtifactStatuses(
            episode="failed",
            run="failed",
            report="blocked",
            report_business="blocked",
            transport="failed",
        )
    if status == "cancelled":
        return ArtifactStatuses(
            episode="cancelled",
            run="cancelled",
            report="partial",
            report_business="partial",
            transport="completed",
        )
    if status == "completed":
        return ArtifactStatuses(
            episode="completed",
            run="completed",
            report="completed",
            report_business="complete",
            transport="completed",
        )
    return ArtifactStatuses(
        episode=status,
        run="completed",
        report="partial",
        report_business="partial",
        transport="completed",
    )
