"""同花顺目录/成员逐逻辑请求审计；不是第二个 canonical 发布器。

每次调用一个新 capture_id：外呼前落计划，成功结果保存白名单字段和指纹，
终态不可覆盖。HTTP 客户端内部重试仍归同一逻辑请求，不宣称逐网络尝试审计。
request_complete 仅表示所声明范围的计划与结果自洽；供应商没有独立完整分母，
provider_completeness 始终 unverified。写入由既有同步器承接，读取只按显式批次。
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import date, datetime
import hashlib
import json
from typing import Callable
from uuid import uuid4
from zoneinfo import ZoneInfo

from .hithink_sector_contract import (
    CATALOG_TAGS,
    CONTRACT_VERSION,
    SOURCE_CATALOG,
    SOURCE_CONSTITUENT,
    normalize_catalog_items,
    normalize_constituent_items,
)

_SHANGHAI = ZoneInfo("Asia/Shanghai")


def _now() -> datetime:
    return datetime.now(_SHANGHAI)


def _time(value: datetime) -> datetime:
    # 同步器已有上海无时区墙钟；这里只在明确的时钟注入边界补时区。
    if not isinstance(value, datetime):
        raise ValueError("capture clock must return datetime")
    return (value.replace(tzinfo=_SHANGHAI) if value.tzinfo is None else value.astimezone(_SHANGHAI))


def _json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _hash(value) -> str:
    return hashlib.sha256(_json(value).encode()).hexdigest()


def _normalized(kind: str, key: str, rows) -> list[dict]:
    if kind == "catalog":
        normalized = normalize_catalog_items(rows, key)
    elif kind == "members":
        normalized = [
            {"thscode": row["thscode"], "ticker": row["ticker"]}
            for row in normalize_constituent_items(rows)
        ]
    else:
        raise ValueError("unknown request kind")
    return sorted(normalized, key=lambda row: row["thscode"])


def _stamp(value) -> str | None:
    return _time(value).isoformat() if value is not None else None


def _read_capture(con, capture_id: str) -> tuple[dict, dict]:
    """同一次读取得到审计与已验证输入，消费者不能通过后再读一次未验证行。"""
    header = con.execute(
        "SELECT contract_version, requested_end_date, include_members, member_limit, members_planned, status, "
        "started_at, finished_at, manifest_sha256 FROM ops_hithink_sector_capture WHERE capture_id=?",
        [capture_id],
    ).fetchone()
    if header is None:
        raise ValueError("unknown capture_id")
    version, end, include, limit, planned, status, started, finished, sealed = header
    request_rows = con.execute(
        "SELECT kind, request_key, status, requested_at, received_at, row_count, "
        "normalized_rows, rows_sha256, error_code FROM ops_hithink_sector_request "
        "WHERE capture_id=? ORDER BY kind, request_key", [capture_id],
    ).fetchall()
    requests, gaps, decoded = [], [], {}
    if version != CONTRACT_VERSION:
        gaps.append("unsupported-contract-version")
    for kind, key, state, sent, received, n, raw, fingerprint, error in request_rows:
        request = {
            "kind": kind, "request_key": key, "status": state,
            "requested_at": _stamp(sent), "received_at": _stamp(received),
            "row_count": n, "rows_sha256": fingerprint, "error_code": error,
        }
        requests.append(request)
        identity = (kind, key)
        if state != "success":
            gaps.append(f"{kind}:{key}:{state}")
            continue
        try:
            rows = json.loads(raw)
            normalized = _normalized(kind, key, rows)
            if rows != normalized or _hash(normalized) != fingerprint or n != len(normalized):
                raise ValueError("response integrity")
            if (sent is None or received is None or not started <= sent <= received
                    or (finished is not None and received > finished)):
                raise ValueError("response time")
            decoded[identity] = normalized
        except (ValueError, TypeError, RuntimeError):
            gaps.append(f"{kind}:{key}:invalid-response-or-time")
    catalog_keys = {r["request_key"] for r in requests if r["kind"] == "catalog"}
    if catalog_keys != set(CATALOG_TAGS):
        gaps.append("catalog-plan-mismatch")
    catalogs_ok = all(("catalog", tag) in decoded for tag in CATALOG_TAGS)
    codes = {row["thscode"] for tag in CATALOG_TAGS for row in decoded.get(("catalog", tag), [])}
    member_keys = {r["request_key"] for r in requests if r["kind"] == "members"}
    if include:
        if not planned or not catalogs_ok or not codes or member_keys != codes:
            gaps.append("member-plan-mismatch")
    elif planned or member_keys:
        gaps.append("unexpected-member-plan")
    document = {
        "capture_id": capture_id, "contract_version": version,
        "requested_end_date": str(end), "include_members": include,
        "member_limit": limit, "members_planned": planned, "status": status,
        "started_at": _stamp(started), "finished_at": _stamp(finished), "requests": requests,
    }
    manifest = _hash(document)
    if status != "running" and (finished is None or finished < started or sealed != manifest):
        gaps.append("capture-manifest-mismatch")
    dates = sorted({r["received_at"][:10] for r in requests if r["received_at"] is not None})
    return {
        **document, "scope": "catalog-and-members" if include else "catalog-only",
        "capture_dates": dates, "manifest_sha256": sealed, "computed_manifest_sha256": manifest,
        "request_complete": status == "complete" and not gaps,
        "provider_completeness": "unverified", "gaps": sorted(set(gaps)),
    }, decoded


def audit_capture(con, capture_id: str) -> dict:
    """只读重新核对计划、终态、白名单原件/计数/指纹/时间，不信一列 complete。"""
    return _read_capture(con, capture_id)[0]


class SectorCapture:
    """既有同步器唯一调用的审计写者；类不建库、不打开数据库或请求供应商。"""

    def __init__(self, con, capture_id: str, clock: Callable[[], datetime]):
        self.con, self.capture_id, self.clock = con, capture_id, clock

    @classmethod
    def start(cls, con, *, requested_end_date: date, include_members: bool,
              member_limit: int | None = None, clock: Callable[[], datetime] = _now):
        if type(requested_end_date) is not date or type(include_members) is not bool:
            raise ValueError("capture needs an explicit date and member scope")
        if member_limit is not None and (type(member_limit) is not int or member_limit < 0):
            raise ValueError("member_limit must be a nonnegative integer")
        capture_id = uuid4().hex
        started = _time(clock())
        con.execute("BEGIN TRANSACTION")
        try:
            con.execute(
                "INSERT INTO ops_hithink_sector_capture "
                "(capture_id, contract_version, requested_end_date, include_members, member_limit, status, started_at) "
                "VALUES (?, ?, ?, ?, ?, 'running', ?)",
                [capture_id, CONTRACT_VERSION, requested_end_date, include_members, member_limit, started],
            )
            con.executemany(
                "INSERT INTO ops_hithink_sector_request (capture_id, kind, request_key, status) "
                "VALUES (?, 'catalog', ?, 'pending')", [(capture_id, tag) for tag in CATALOG_TAGS],
            )
            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
            raise
        return cls(con, capture_id, clock)

    @contextmanager
    def _writing(self):
        """短事务先争用同一批次头，防检查终态后到更新之间被另一写者封存。"""
        self.con.execute("BEGIN TRANSACTION")
        try:
            row = self.con.execute(
                "UPDATE ops_hithink_sector_capture SET status=status "
                "WHERE capture_id=? AND status='running' AND contract_version=? "
                "RETURNING include_members, member_limit, members_planned", [self.capture_id, CONTRACT_VERSION],
            ).fetchone()
            if row is None:
                raise ValueError("capture is not running")
            yield row
            self.con.execute("COMMIT")
        except Exception:
            self.con.execute("ROLLBACK")
            raise

    def request(self, kind: str, key: str, fetch: Callable[[], list[dict]]):
        with self._writing():
            reserved = self.con.execute(
                "UPDATE ops_hithink_sector_request SET status='requesting', requested_at=? "
                "WHERE capture_id=? AND kind=? AND request_key=? AND status='pending' RETURNING request_key",
                [_time(self.clock()), self.capture_id, kind, key],
            ).fetchone()
            if reserved is None:
                raise ValueError("request is not pending in this capture")
        try:
            fetched = fetch()
            received = _time(self.clock())
            normalized = _normalized(kind, key, fetched)
        except Exception:
            try:
                with self._writing():
                    self.con.execute(
                        "UPDATE ops_hithink_sector_request SET status='error', received_at=?, error_code='request-error' "
                        "WHERE capture_id=? AND kind=? AND request_key=? AND status='requesting'",
                        [_time(self.clock()), self.capture_id, kind, key],
                    )
            except Exception:
                # 审计介质故障时保留 requesting；不能盖掉第一次失败或伪造成功。
                pass
            raise
        with self._writing():
            recorded = self.con.execute(
                "UPDATE ops_hithink_sector_request SET status='success', received_at=?, row_count=?, "
                "normalized_rows=?, rows_sha256=? "
                "WHERE capture_id=? AND kind=? AND request_key=? AND status='requesting' RETURNING request_key",
                [received, len(normalized), _json(normalized), _hash(normalized), self.capture_id, kind, key],
            ).fetchone()
            if recorded is None:
                raise ValueError("request reservation no longer active")
        return normalized, received

    def plan_members(self) -> list[str]:
        with self._writing() as (include, limit, planned):
            report, decoded = _read_capture(self.con, self.capture_id)
            if not include or planned or report["gaps"] != ["member-plan-mismatch"]:
                raise ValueError("member plan requires all valid catalogs, once, with member scope")
            codes = sorted({row["thscode"] for tag in CATALOG_TAGS for row in decoded[("catalog", tag)]})
            selected = codes if limit is None else codes[:limit]
            selected_set = set(selected)
            self.con.executemany(
                "INSERT INTO ops_hithink_sector_request "
                "(capture_id, kind, request_key, status, error_code) VALUES (?, 'members', ?, ?, ?)",
                [(self.capture_id, code, "pending" if code in selected_set else "skipped",
                  None if code in selected_set else "limit") for code in codes],
            )
            self.con.execute(
                "UPDATE ops_hithink_sector_capture SET members_planned=true WHERE capture_id=?", [self.capture_id],
            )
        return selected

    def _finish(self, failed: bool) -> dict:
        with self._writing():
            report = audit_capture(self.con, self.capture_id)
            if any(r["status"] == "requesting" for r in report["requests"]):
                raise ValueError("cannot seal capture with an active request")
            state = "failed" if failed else ("partial" if report["gaps"] else "complete")
            self.con.execute(
                "UPDATE ops_hithink_sector_capture SET status=?, finished_at=? WHERE capture_id=?",
                [state, _time(self.clock()), self.capture_id],
            )
            report = audit_capture(self.con, self.capture_id)
            if state == "complete" and any(gap != "capture-manifest-mismatch" for gap in report["gaps"]):
                self.con.execute(
                    "UPDATE ops_hithink_sector_capture SET status='partial' WHERE capture_id=?", [self.capture_id],
                )
                report = audit_capture(self.con, self.capture_id)
            self.con.execute(
                "UPDATE ops_hithink_sector_capture SET manifest_sha256=? WHERE capture_id=?",
                [report["computed_manifest_sha256"], self.capture_id],
            )
        return audit_capture(self.con, self.capture_id)

    def finish(self) -> dict:
        return self._finish(False)

    def fail(self) -> dict:
        return self._finish(True)


class CaptureNotReadyError(ValueError):
    """批次已找到但不可消费；只携带固定字段审计，不带原响应或供应商消息。"""

    def __init__(self, audit: dict):
        super().__init__("capture requests incomplete or member scope unavailable")
        self.audit = audit


def capture_inputs(con, capture_id: str, category: str) -> tuple[list, list, dict]:
    """给只读计算器的批次投影；无最新目录回退，不从被覆盖的每日成员表补行。"""
    if category not in CATALOG_TAGS:
        raise ValueError("invalid capture category")
    audit, payloads = _read_capture(con, capture_id)
    if not audit["request_complete"] or audit["scope"] != "catalog-and-members":
        raise CaptureNotReadyError(audit)
    request_by_key = {(r["kind"], r["request_key"]): r for r in audit["requests"]}
    catalog_at = datetime.fromisoformat(request_by_key[("catalog", category)]["received_at"]).replace(tzinfo=None)
    sectors, members = [], []
    for row in payloads[("catalog", category)]:
        code = row["thscode"]
        stocks = payloads[("members", code)]
        received = datetime.fromisoformat(request_by_key[("members", code)]["received_at"]).replace(tzinfo=None)
        sectors.append((code, row["name"], catalog_at, len(stocks), received, SOURCE_CATALOG))
        members.extend((code, stock["thscode"], SOURCE_CONSTITUENT, received) for stock in stocks)
    return sectors, members, audit
