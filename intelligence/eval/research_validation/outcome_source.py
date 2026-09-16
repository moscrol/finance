"""旁路库结果源：``service.OutcomeSource`` 的只读实现。"""

from __future__ import annotations

from datetime import timezone
from pathlib import Path
from typing import Any, Mapping

from intelligence.services.methodology_backtest.store import open_labels_db, read_meta
from intelligence.services.research_validation.contracts import ContractError, utc_iso


class LabelsDbOutcomeSource:
    """按 ``history_outcomes`` 主键查一行；``describe`` 报水位、版本与日历。"""

    def __init__(self, labels_db: str | Path, *, metric: str = "fwd_return") -> None:
        if metric not in ("fwd_return", "max_return", "days_to_peak", "drawdown_after_peak"):
            raise ContractError(f"未知 metric {metric!r}")
        self.path = Path(labels_db).expanduser()
        self.metric = metric

    def describe(self) -> Mapping[str, Any]:
        con = open_labels_db(self.path, read_only=True)
        try:
            meta = read_meta(con)
            outcomes = meta.get("outcomes") or {}
            labels = meta.get("labels") or {}
            calendar = [str(r[0]) for r in con.execute("SELECT trade_date FROM history_calendar ORDER BY idx").fetchall()]
        finally:
            con.close()
        if not outcomes or not labels:
            raise ContractError("旁路库缺构建记录")
        return {
            "source_ref": str(self.path),
            "source_max_trade_date": str(outcomes.get("source_max_trade_date")),
            "version_hashes": {
                "label_version": str(labels.get("label_version")),
                "source_db": str(labels.get("source_db")),
            },
            "calendar": calendar,
        }

    def lookup(self, *, entity_type: str, entity_id: str, as_of: str, horizon: int) -> Mapping[str, Any] | None:
        con = open_labels_db(self.path, read_only=True)
        try:
            row = con.execute(
                f"SELECT status, {self.metric}, computed_at FROM history_outcomes "
                "WHERE entity_type = ? AND entity_id = ? AND trade_date = ? AND horizon = ?",
                [entity_type, entity_id, as_of, int(horizon)],
            ).fetchone()
        finally:
            con.close()
        if row is None:
            return None
        status, value, computed = row
        computed_at = None
        if computed is not None:
            ts = computed if getattr(computed, "tzinfo", None) is not None else computed.replace(tzinfo=timezone.utc)
            computed_at = utc_iso(ts)
        return {"status": str(status), "metric_value": value, "computed_at": computed_at}


__all__ = ["LabelsDbOutcomeSource"]
