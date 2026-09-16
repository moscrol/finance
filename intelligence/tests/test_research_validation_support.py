"""03 轨测试的共享构造器（本文件不含测试）。

所有数据 synthetic；旁路库现场生成到 tmp_path，不落仓。
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Mapping
from zoneinfo import ZoneInfo

from intelligence.services.methodology_backtest.labels import LABEL_SPEC, LABEL_VERSION
from intelligence.services.methodology_backtest.store import open_labels_db, write_meta
from intelligence.services.research_validation import Repository
from intelligence.services.research_validation.contracts import market_close, utc_iso

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "research_evolution" / "03"
OWNER = "u_test"
SH = ZoneInfo("Asia/Shanghai")
HORIZON = 5


def load_fixture(name: str) -> dict[str, Any]:
    data = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    data.pop("_comment", None)
    return data


def weekdays(start: str, n: int) -> list[str]:
    out: list[str] = []
    d = date.fromisoformat(start)
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def sh(day: str, hour: int = 16, minute: int = 0) -> datetime:
    y, m, d = (int(x) for x in day.split("-"))
    return datetime(y, m, d, hour, minute, tzinfo=SH)


def make_repo(tmp_path: Path, owner: str = OWNER) -> Repository:
    return Repository(tmp_path / "users" / owner / "research_validation", owner)


def forward_body(cal: list[str], *, n_forward: int = 55, **overrides: Any) -> dict[str, Any]:
    body = load_fixture("forward_protocol_synthetic.json")
    fs_idx = cal.index("2026-09-14")
    body["calendar"] = list(cal)
    body["forward_start"] = cal[fs_idx]
    body["evaluation_end"] = cal[fs_idx + n_forward - 1]
    body.update(overrides)
    return body


def forecast_input(entity_id: str, as_of: str, arm_id: str, p: float, *, origin: str = "deterministic", **extra: Any) -> dict[str, Any]:
    item: dict[str, Any] = {
        "entity_id": entity_id,
        "as_of": as_of,
        "arm_id": arm_id,
        "p": p,
        "forecast_at": utc_iso(market_close(as_of) + timedelta(minutes=30)),
        "origin": origin,
    }
    if origin == "deterministic":
        item["probability_recipe_hash"] = "0000000000000000000000000000000000000000000000000000000000000abc"
    item.update(extra)
    return item


class DictOutcomeSource:
    """内存结果源：rows[(entity_type, entity_id, as_of, horizon)] = {"status", "metric_value", "computed_at"}。"""

    def __init__(
        self,
        *,
        calendar: list[str],
        watermark: str,
        version_hashes: Mapping[str, str] | None = None,
        rows: Mapping[tuple[str, str, str, int], Mapping[str, Any]] | None = None,
        source_ref: str = "synthetic://dict-outcome-source",
    ) -> None:
        self.calendar = list(calendar)
        self.watermark = watermark
        self.version_hashes = dict(version_hashes or {"label_version": "synthetic-v1"})
        self.rows = dict(rows or {})
        self.source_ref = source_ref
        self.lookups = 0

    def describe(self) -> Mapping[str, Any]:
        return {
            "source_ref": self.source_ref,
            "source_max_trade_date": self.watermark,
            "version_hashes": self.version_hashes,
            "calendar": self.calendar,
        }

    def lookup(self, *, entity_type: str, entity_id: str, as_of: str, horizon: int) -> Mapping[str, Any] | None:
        self.lookups += 1
        return self.rows.get((entity_type, entity_id, as_of, int(horizon)))


def settled_row(as_of: str, metric_value: float, *, cal: list[str], horizon: int = HORIZON) -> dict[str, Any]:
    due = cal[cal.index(as_of) + horizon]
    return {"status": "ok", "metric_value": metric_value, "computed_at": utc_iso(market_close(due) + timedelta(hours=1))}


class FakePitVerifier:
    def __init__(self, table: Mapping[str, Mapping[str, Any]]) -> None:
        self.table = dict(table)

    def verify(self, capture_receipt_ref: str) -> Mapping[str, Any] | None:
        return self.table.get(capture_receipt_ref)


def make_labels_db(
    tmp_path: Path,
    *,
    calendar: list[str],
    sectors: list[str],
    label_fn: Callable[[int, str, str], Mapping[str, Any]],
    outcome_fn: Callable[[int, str, str], float | None],
    now: datetime,
    label_version: str = LABEL_VERSION,
    horizon: int = HORIZON,
    name: str = "labels.duckdb",
) -> Path:
    """现场生成 history_labels.duckdb 形状的旁路库；outcome 窗伸出日历 → status pending。"""
    path = tmp_path / name
    con = open_labels_db(path, read_only=False)
    computed = now.astimezone(timezone.utc).replace(tzinfo=None)
    try:
        con.executemany("INSERT INTO history_calendar VALUES (?, ?)", list(enumerate(calendar)))
        label_rows: list[tuple] = []
        outcome_rows: list[tuple] = []
        for idx, day in enumerate(calendar):
            label_rows.append(("market", "market", day, "market_stage", None, "主升", label_version, computed))
            for sector in sectors:
                for label, value in label_fn(idx, day, sector).items():
                    label_rows.append(("sector", sector, day, label, value, None, label_version, computed))
                if idx + horizon < len(calendar):
                    ret = outcome_fn(idx, day, sector)
                    if ret is None:
                        outcome_rows.append(("sector", sector, day, horizon, None, None, None, None, "missing", computed))
                    else:
                        outcome_rows.append(("sector", sector, day, horizon, ret, max(ret, 0.0), 1, -0.5, "ok", computed))
                else:
                    outcome_rows.append(("sector", sector, day, horizon, None, None, None, None, "pending", computed))
        con.executemany("INSERT INTO history_labels VALUES (?, ?, ?, ?, ?, ?, ?, ?)", label_rows)
        con.executemany("INSERT INTO history_outcomes VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", outcome_rows)
        for kind in ("labels", "outcomes"):
            write_meta(
                con,
                build_kind=kind,
                label_version=label_version,
                source_db=tmp_path / "source.duckdb",
                source_max_trade_date=calendar[-1],
                source_row_counts={"label_spec": LABEL_SPEC, **({"window_start_offset": 1} if kind == "outcomes" else {})},
                row_count=len(label_rows) if kind == "labels" else len(outcome_rows),
                horizons=(horizon,) if kind == "outcomes" else None,
                computed_at=now,
            )
    finally:
        con.close()
    return path
