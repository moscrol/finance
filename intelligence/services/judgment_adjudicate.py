"""KC-10：到期裁决 job。

扫 ``checkpoints.jsonl`` 里到期且无终态 verdict 的点，交给已有
``checkpoint_resolvers.resolve_checkpoint``（与 ``checkpoint recheck`` 同一套）：

- 判据可机读（``stock_return`` / ``kb_evidence`` / ``market_daily``）且拿到
  hit/miss/partial → 只 **追加** ``verdicts.jsonl``（``auto=True``），附 evidence 行。
- 判据不可机读（manual / 无 metric）→ 人工队列，**不写** verdict。
- 可机读但缺数（unverifiable）→ 延期，不写终态，下次再判。
- **不回改** ``judgments.jsonl`` / ``checkpoints.jsonl`` 原文。

空到期日（没有 due <= today 的待裁决项）再跑一次：零新行。
禁止再开 ``judgments-ledger.jsonl``。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from intelligence.services import checkpoint_resolvers, checkpoints

MACHINE_METRIC_TYPES = frozenset({"stock_return", "kb_evidence", "market_daily"})
ResolveFn = Callable[[dict[str, Any]], checkpoint_resolvers.ResolveOutcome]


@dataclass(frozen=True)
class AdjudicationItem:
    id: str
    bucket: str
    verdict: str | None
    reason: str
    observed: dict[str, Any]
    applied: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "bucket": self.bucket,
            "verdict": self.verdict,
            "reason": self.reason,
            "observed": self.observed,
            "applied": self.applied,
        }


@dataclass(frozen=True)
class AdjudicationReport:
    auto: tuple[AdjudicationItem, ...]
    queued: tuple[AdjudicationItem, ...]
    deferred: tuple[AdjudicationItem, ...]
    judgments_unchanged: bool
    verdicts_appended: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "auto": [item.to_dict() for item in self.auto],
            "queued": [item.to_dict() for item in self.queued],
            "deferred": [item.to_dict() for item in self.deferred],
            "judgments_unchanged": self.judgments_unchanged,
            "verdicts_appended": self.verdicts_appended,
        }


def is_machine_readable(checkpoint: dict[str, Any]) -> bool:
    metric = checkpoint.get("metric") or {}
    return str(metric.get("type") or "").strip() in MACHINE_METRIC_TYPES


def run_adjudication_job(
    *,
    judgments_path: str | Path,
    checkpoints_path: str | Path,
    verdicts_path: str | Path,
    today: str | None = None,
    apply: bool = True,
    resolve: ResolveFn | None = None,
    db_path: str | None = None,
    wiki_root: str | None = None,
    market_returns_fn: checkpoint_resolvers.ReturnsFn | None = None,
    checked_at: str | None = None,
) -> AdjudicationReport:
    """跑一轮到期裁决。只追加 verdicts，不改判断/检查点原文。"""
    jpath = Path(judgments_path).expanduser()
    cpath = Path(checkpoints_path).expanduser()
    vpath = Path(verdicts_path).expanduser()
    before_judgments = _file_bytes(jpath)
    before_checkpoints = _file_bytes(cpath)

    cks, _ = checkpoints.load_checkpoints(cpath)
    vds, _ = checkpoints.load_verdicts(vpath)
    due = checkpoints.due_checkpoints(cks, vds, today=today)
    resolver = resolve or (
        lambda ck: checkpoint_resolvers.resolve_checkpoint(
            ck,
            db_path=db_path,
            wiki_root=wiki_root,
            market_returns_fn=market_returns_fn,
        )
    )

    auto: list[AdjudicationItem] = []
    queued: list[AdjudicationItem] = []
    deferred: list[AdjudicationItem] = []
    appended = 0

    for ck in due:
        cid = str(ck.get("id") or "").strip()
        if not cid:
            continue
        if not is_machine_readable(ck):
            queued.append(
                AdjudicationItem(
                    id=cid,
                    bucket="queued",
                    verdict=None,
                    reason="判据不可机读，待人工 `checkpoint score`",
                    observed={},
                    applied=False,
                )
            )
            continue
        outcome = resolver(ck)
        if outcome.verdict in checkpoints.TERMINAL_VERDICTS:
            applied = False
            if apply:
                checkpoints.record_verdict(
                    vpath,
                    id=cid,
                    verdict=outcome.verdict,
                    score=outcome.score,
                    observed=outcome.observed,
                    data_source=outcome.data_source,
                    reason=outcome.reason,
                    degradation=outcome.degradation,
                    auto=True,
                    checked_at=checked_at,
                )
                appended += 1
                applied = True
            auto.append(
                AdjudicationItem(
                    id=cid,
                    bucket="auto",
                    verdict=outcome.verdict,
                    reason=outcome.reason,
                    observed=dict(outcome.observed or {}),
                    applied=applied,
                )
            )
            continue
        deferred.append(
            AdjudicationItem(
                id=cid,
                bucket="deferred",
                verdict=outcome.verdict,
                reason=outcome.reason,
                observed=dict(outcome.observed or {}),
                applied=False,
            )
        )

    after_judgments = _file_bytes(jpath)
    after_checkpoints = _file_bytes(cpath)
    if after_checkpoints != before_checkpoints:
        raise RuntimeError("裁决 job 不得改写 checkpoints.jsonl")
    return AdjudicationReport(
        auto=tuple(auto),
        queued=tuple(queued),
        deferred=tuple(deferred),
        judgments_unchanged=after_judgments == before_judgments,
        verdicts_appended=appended,
    )


def _file_bytes(path: Path) -> bytes:
    if not path.exists():
        return b""
    return path.read_bytes()
