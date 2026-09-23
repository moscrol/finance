"""Bounded research observations, using the existing staging write path.

Latest-only endpoints are never backdated. Raw successful responses and their
request scope are retained; fact tables contain the latest observed value for
each natural date/key, not a point-in-time backtest dataset.
"""

from __future__ import annotations

import json
import math
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Sequence
from uuid import uuid4
from zoneinfo import ZoneInfo

import duckdb

from ..db import DB_PATH, init_db
from ..hithink_client import (
    HithinkRateLimitError,
    get_json,
    has_api_key,
    ms_to_shanghai_date,
)
from ..write_path import is_canonical_production

SHANGHAI = ZoneInfo("Asia/Shanghai")
PATHS = {
    "anomaly": "/api/a-share/special-data/anomaly-analysis-list",
    "heat_trend": "/api/a-share/special-data/hot-stock-rank-trend",
    "valuation": "/api/a-share/valuations/snapshot",
}
VALUATION_FIELDS = ("pe_ttm", "pe_mrq", "pb_mrq", "ps_ttm", "pcf_ttm")
MAX_CODES = 100
DEFAULT_SCOPE_SIZE = 30
DEFAULT_LOOKBACK_DAYS = 30
CODE = re.compile(r"[0-9]{6}\.(SH|SZ|BJ)\Z")
GetJson = Callable[..., dict[str, Any]]


class HithinkResearchError(RuntimeError):
    """Safe error text: no upstream message, credentials or response body."""


class HithinkCaptureError(HithinkResearchError):
    """A failed request with safe metadata for the enclosing capture run."""

    def __init__(
        self,
        *,
        kind: str,
        request_id: str,
        error_type: str,
        rate_limited: bool,
    ) -> None:
        self.kind = kind
        self.request_id = request_id
        self.error_type = error_type
        self.rate_limited = rate_limited
        super().__init__(
            f"{kind} failed ({error_type}); see request {request_id}"
        )


def _now() -> datetime:
    return datetime.now(SHANGHAI)


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True)


def normalize_codes(codes: Sequence[str]) -> list[str]:
    if not codes or len(codes) > MAX_CODES:
        raise HithinkResearchError("scope must contain 1..100 codes")
    result = []
    for code in codes:
        if not isinstance(code, str) or not CODE.fullmatch(code.strip().upper()):
            raise HithinkResearchError("scope requires six digits and SH/SZ/BJ suffix")
        if code.strip().upper() not in result:
            result.append(code.strip().upper())
    return result


def _number(value: Any, *, integer: bool = False) -> float | int | None:
    if value is None:
        return None
    if (
        isinstance(value, bool)
        or not isinstance(value, (float, int))
        or not math.isfinite(value)
    ):
        raise HithinkResearchError("invalid numeric field")
    if integer and (value != int(value) or value < 1):
        raise HithinkResearchError("rank must be a positive integer or null")
    return int(value) if integer else value


def _timestamp(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise HithinkResearchError("invalid provider timestamp")
    if value == 0:
        return None
    try:
        ms_to_shanghai_date(value)
    except (ValueError, OverflowError, OSError):
        raise HithinkResearchError("invalid provider timestamp") from None
    return value


def _parse(
    kind: str,
    payload: dict,
    params: dict,
    captured_at: datetime,
) -> tuple[list[dict], int | None]:
    if not isinstance(payload, dict) or payload.get("code") != 0:
        raise HithinkResearchError("unsuccessful response")
    data = payload.get("data")
    if not isinstance(data, dict) or not isinstance(data.get("item"), list):
        raise HithinkResearchError("response must contain data.item array")
    items = data["item"]
    timestamp = _timestamp(data.get("timestamp"))
    if kind == "valuation" and data.get("total") != len(items):
        raise HithinkResearchError("valuation total does not match item count")
    if kind == "anomaly" and items:
        if timestamp is None or ms_to_shanghai_date(timestamp) != captured_at.date():
            raise HithinkResearchError("anomaly snapshot is not dated today")
    expected = (
        set(params.get("thscodes", "").split(",")) if kind == "valuation" else set()
    )
    result, seen = [], set()
    for item in items:
        if not isinstance(item, dict):
            raise HithinkResearchError("invalid row")
        code = normalize_codes([item.get("thscode")])[0]
        row = {"stock_ts_code": code}
        if kind == "heat_trend":
            try:
                day = date.fromisoformat(item["date"])
                start = date.fromisoformat(params["start_date"])
                end = date.fromisoformat(params["end_date"])
            except (KeyError, TypeError, ValueError):
                raise HithinkResearchError("invalid heat trend date") from None
            if code != params["thscode"] or not start <= day <= end:
                raise HithinkResearchError("heat trend row outside requested scope")
            if (
                _timestamp(item.get("date_ms")) is None
                or ms_to_shanghai_date(item["date_ms"]) != day
            ):
                raise HithinkResearchError("heat trend date/date_ms mismatch")
            if "rank" not in item:
                raise HithinkResearchError("missing rank field")
            row.update(observation_date=day, rank=_number(item["rank"], integer=True))
            identity = (day, code)
        elif kind == "valuation":
            if code not in expected or any(
                field not in item for field in VALUATION_FIELDS
            ):
                raise HithinkResearchError(
                    "valuation row outside scope or missing fields"
                )
            row.update(observation_date=captured_at.date())
            row.update({field: _number(item[field]) for field in VALUATION_FIELDS})
            identity = code
        else:
            content, tag, keywords = (
                item.get("analysis_content"),
                item.get("tag_name"),
                item.get("keyword_list"),
            )
            if (
                not isinstance(content, str)
                or not content.strip()
                or not isinstance(tag, str)
                or not tag.strip()
            ):
                raise HithinkResearchError("missing anomaly content or tag")
            if not isinstance(keywords, list) or not all(
                isinstance(word, str) for word in keywords
            ):
                raise HithinkResearchError("invalid anomaly keywords")
            row.update(
                observation_date=captured_at.date(),
                tag_name=tag,
                analysis_content=content,
                keywords_json=_json(keywords),
            )
            identity = (code, tag)
        if identity in seen:
            raise HithinkResearchError("duplicate response identity")
        seen.add(identity)
        result.append(row)
    return result, timestamp


def _store_rows(
    con,
    kind: str,
    rows: list[dict],
    request_id: str,
    captured_at: datetime,
    timestamp: int | None,
):
    tables = {
        "anomaly": "fact_stock_anomaly_hithink",
        "heat_trend": "fact_hot_stock_trend_hithink",
        "valuation": "fact_stock_valuation_hithink",
    }
    for row in rows:
        row = {
            **row,
            "captured_date": captured_at.date(),
            "captured_at": captured_at,
            "provider_timestamp_ms": timestamp,
            "request_id": request_id,
            "source": "hithink:" + PATHS[kind].rsplit("/", 1)[-1],
        }
        columns = ", ".join(row)
        placeholders = ", ".join("?" for _ in row)
        con.execute(
            f"INSERT OR REPLACE INTO {tables[kind]} ({columns}) VALUES ({placeholders})",
            list(row.values()),
        )


def _capture(
    con, kind: str, params: dict, target: date, getter: GetJson, clock
) -> dict:
    request_id = uuid4().hex
    started = clock().astimezone(SHANGHAI)
    con.execute(
        "INSERT INTO ops_hithink_research_request "
        "(request_id, kind, target_date, started_at, params_json, status) VALUES (?, ?, ?, ?, ?, 'pending')",
        [request_id, kind, target, started, _json(params)],
    )
    try:
        payload = getter(PATHS[kind], params=params)
        captured_at = clock().astimezone(SHANGHAI)
        if kind != "heat_trend" and captured_at.date() != target:
            raise HithinkResearchError("latest-only request crossed target day")
        rows, timestamp = _parse(kind, payload, params, captured_at)
        # The full response is kept for audit, not offered as trusted company evidence.
        raw_json = _json(
            {"request_id": payload.get("request_id"), "data": payload["data"]}
        )
        value_rows = sum(
            bool(row.get("analysis_content"))
            if kind == "anomaly"
            else row.get("rank") is not None
            if kind == "heat_trend"
            else any(row.get(field) is not None for field in VALUATION_FIELDS)
            for row in rows
        )
        expected_rows = (
            len(params["thscodes"].split(",")) if kind == "valuation" else None
        )
        status = "empty" if not rows else "ok"
        if rows and (
            value_rows < len(rows)
            or (expected_rows is not None and len(rows) < expected_rows)
        ):
            status = "partial"
        con.execute("BEGIN TRANSACTION")
        try:
            _store_rows(con, kind, rows, request_id, captured_at, timestamp)
            con.execute(
                "UPDATE ops_hithink_research_request SET status=?, captured_at=?, provider_request_id=?, "
                "provider_timestamp_ms=?, row_count=?, value_rows=?, payload_json=? WHERE request_id=?",
                [
                    status,
                    captured_at,
                    payload.get("request_id"),
                    timestamp,
                    len(rows),
                    value_rows,
                    raw_json,
                    request_id,
                ],
            )
            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
            raise
        return {
            "kind": kind,
            "status": status,
            "rows": len(rows),
            "value_rows": value_rows,
            "request_id": request_id,
        }
    except Exception as exc:
        # Do not persist/echo upstream exception messages, which may contain secrets.
        con.execute(
            "UPDATE ops_hithink_research_request SET status='failed', error_type=? WHERE request_id=?",
            [type(exc).__name__, request_id],
        )
        raise HithinkCaptureError(
            kind=kind,
            request_id=request_id,
            error_type=type(exc).__name__,
            rate_limited=isinstance(exc, HithinkRateLimitError),
        ) from None


def _capture_allow_rate_limit_gap(
    con, kind: str, params: dict, target: date, getter: GetJson, clock
) -> dict:
    """Keep the rest of a run alive when one endpoint exhausts rate-limit backoff."""

    try:
        return _capture(con, kind, params, target, getter, clock)
    except HithinkCaptureError as exc:
        if not exc.rate_limited:
            raise
        return {
            "kind": exc.kind,
            "status": "failed",
            "rows": 0,
            "value_rows": 0,
            "request_id": exc.request_id,
            "error_type": exc.error_type,
            "reason": "rate_limit",
        }


def sync_hithink_research(
    *,
    end_date: date | None = None,
    codes: Sequence[str] | None = None,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    history_only: bool = False,
    db_path: Path | str | None = None,
    getter: GetJson | None = None,
    clock: Callable[[], datetime] | None = None,
) -> dict:
    """Capture a bounded scope; default scope is the target day's hot Top30.

    Historical mode only calls heat-trend. Latest snapshots cannot be collected
    for an old end_date. Production is never a direct write destination.
    """
    clock = clock or _now
    target_path = Path(db_path) if db_path is not None else DB_PATH
    if is_canonical_production(target_path):
        raise HithinkResearchError(
            "direct production write refused; use daily-full staging"
        )
    today = clock().astimezone(SHANGHAI).date()
    target = end_date or today
    if (
        not isinstance(target, date)
        or target > today
        or (not history_only and target != today)
    ):
        raise HithinkResearchError(
            "latest snapshots require today; use history-only for past dates"
        )
    if (
        not isinstance(lookback_days, int)
        or isinstance(lookback_days, bool)
        or not 1 <= lookback_days <= 365
    ):
        raise HithinkResearchError("lookback_days must be 1..365")
    start = target - timedelta(days=lookback_days - 1)
    if start < today - timedelta(days=364):
        raise HithinkResearchError("heat trend window exceeds the rolling year")
    scope = normalize_codes(codes) if codes is not None else None
    if getter is None and not has_api_key():
        return {"status": "skip", "reason": "no-key", "requests": []}
    target_path.parent.mkdir(parents=True, exist_ok=True)
    # A lock conflict must fail. A sidecar would be discarded by staging swap.
    con = duckdb.connect(str(target_path))
    try:
        init_db(con)
        if scope is None:
            scope = [
                row[0]
                for row in con.execute(
                    "SELECT stock_ts_code FROM fact_hot_stock_rank_hithink "
                    "WHERE trade_date=? AND rank IS NOT NULL ORDER BY rank, stock_ts_code LIMIT ?",
                    [target, DEFAULT_SCOPE_SIZE],
                ).fetchall()
            ]
            if not scope:
                raise HithinkResearchError(
                    "no target-day hot-rank scope; refusing stale fallback"
                )
            scope = normalize_codes(scope)
        requests = []
        get = getter or get_json

        def capture(kind: str, params: dict) -> None:
            requests.append(
                _capture_allow_rate_limit_gap(
                    con, kind, params, target, get, clock
                )
            )

        if not history_only:
            capture("anomaly", {})
            capture("valuation", {"thscodes": ",".join(scope)})
        for code in scope:
            capture(
                "heat_trend",
                {
                    "thscode": code,
                    "start_date": start.isoformat(),
                    "end_date": target.isoformat(),
                },
            )
        missing = [
            {"kind": row["kind"], "request_id": row["request_id"]}
            for row in requests
            if row["status"] == "failed"
        ]
        if missing:
            status = "partial"
        elif any(row["status"] != "ok" for row in requests):
            status = "complete_with_gaps"
        else:
            status = "ok"
        return {
            "status": status,
            "target_date": target.isoformat(),
            "history_only": history_only,
            "scope": scope,
            "requests": requests,
            "missing": missing,
            "coverage": "declared scope only; historical rows are not point-in-time versions",
        }
    finally:
        con.close()
