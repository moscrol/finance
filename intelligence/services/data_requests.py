"""问题驱动补数：回答里的数据缺口 → 结构化补数请求 → 补齐完成信号 → 恢复原研究。

这条链此前断在第一步：``finance_query`` 合法查询、请求窗落在库覆盖之外时，
runtime 只在给模型的 observation 里写一句「没有结构化结果」，不留任何机器可读痕迹。
``tool_hunger.record_window_uncovered`` 补上了痕迹（每 run 一份 ``tool_hunger.jsonl``），
本模块只做三件事，且都不新建写入链：

1. **build**：读各 run 的 ``window_uncovered`` 事件，按「同 dataset、窗口重叠」合并成请求，
   消费者（run / 用户 / 原问题 / 会话）取并集，按消费者数与新鲜度排优先级；
   补数路线来自代码内的 ``FILL_ROUTES``（已有 writer 才叫可补，否则显示真正缺什么）。
2. **check**：对每个请求在指定库上做覆盖检查——交易日历取自 ``fact_stock_daily``，
   关键字段非空率、日期与来源合理性一起看；满足时给出带 ``data_version`` 的完成结果。
   「有行但值全空」「历史日被实时源覆写」「只补了一半」都不算完成。
3. **resume**：满足条件的请求沿真实对话入口重问消费者的原问题；回执落
   ``users/<user>/data_request_receipts.jsonl``（唯一写入者是 ``intelligence.cli data-requests resume``），
   同一 ``(request_id, data_version, consumer_run_id)`` 只恢复一次，重放不产生重复副作用。

补数写入仍由现有 writer 完成（``sync_akshare_index_daily`` / ``sync_akshare_sw_l1_daily`` /
``compute_market_overview_local``），``fill`` 只在隔离 staging 库上编排它们，指向生产库会拒绝。
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Callable

from intelligence.services.tool_hunger import EVENT_WINDOW_UNCOVERED, HUNGER_FILENAME

SCHEMA_VERSION = "data-requests/v1"
RECEIPTS_FILENAME = "data_request_receipts.jsonl"
REQUEST_ID_PREFIX = "dr-"

STATUS_OPEN = "open"
STATUS_PARTIAL = "partial"
STATUS_INVALID = "invalid"
STATUS_SATISFIED = "satisfied"
STATUS_CALENDAR_UNKNOWN = "calendar_unknown"
STATUS_SOURCE_FAILED = "source_failed"

ROUTE_AUTO = "auto"
ROUTE_AUTO_HEAVY = "auto_heavy"
ROUTE_MANUAL = "manual"
ROUTE_PENDING_SYNC = "pending_sync"

# 关键字段非空率低于此值视为「有行但值空」，不算补齐。
KEY_FIELD_MIN_COVERAGE = 0.9
# 历史日不许被实时源覆写：这些来源片段出现在早于今天的行上，即判 invalid。
REALTIME_SOURCE_MARKERS = ("index_realtime_sw", "realtime")

# OPT-03 §3.1 三项占位：本单只消费状态，不重建状态门、不排期、不外呼。
PENDING_SYNC_SOURCES: dict[str, dict[str, str]] = {
    "l2_moneyflow": {
        "label": "L2 资金数据",
        "sync_status": "pending_sync",
        "status_basis": "user_confirmed",
        "writer_ref": "scripts/moneyflow/（实施前核验具体 writer）",
        "note": "待同步窗口的资金计算返回 pending_sync；不能从成交额推算资金流",
    },
    "sellside_evening": {
        "label": "晚间卖方",
        "sync_status": "pending_sync",
        "status_basis": "user_confirmed",
        "writer_ref": "知识库 wiki/raw/sellside/ → 台账地图观点提取流程",
        "note": "不把未同步当「没有覆盖 / 舆论降温」，不生成伪造观点事件",
    },
    "morning_briefing": {
        "label": "晨汇",
        "sync_status": "pending_sync",
        "status_basis": "user_confirmed",
        "writer_ref": "IMA 原料获取 + morning-briefing；知识库 wiki/raw/briefings/",
        "note": "不把缺批次当「当日无事件」，不以其他日报冒充晨汇",
    },
}

_FUPANHUI_MANUAL = {
    "mode": ROUTE_MANUAL,
    "source_family": "fupanhui",
    "condition": (
        "复盘会（fupanhui）数据源：需要 CDP proxy 与登录态、用户在场，"
        "由 daily-full 维护者按日回补；本单只登记，不自动重试"
    ),
    "writer": "python3 -m market_feature_store.cli daily-full --trade-date <date>",
    "parts": [],
}

# dataset → 补数路线。只有已有 writer 的才叫「可补」；其余显示真正缺什么。
# parts[].depends_on 指同窗口的其他 dataset：完成结果会逐项报告依赖是否已满足。
FILL_ROUTES: dict[str, dict[str, Any]] = {
    "market_daily": {
        "mode": ROUTE_AUTO,
        "source_family": "akshare+local",
        "parts": [
            {
                "name": "sh_index",
                "columns": [
                    "sh_index_close",
                    "sh_index_pct_chg",
                    "sh_index_open",
                    "sh_index_high",
                    "sh_index_low",
                    "sh_index_volume",
                ],
                "source": "akshare:stock_zh_index_daily:sh000001",
                "writer": "market_feature_store.sync.sync_akshare_index_daily.sync_akshare_index_daily(start_date, end_date)",
                "depends_on": [],
            },
            {
                "name": "aggregates",
                "columns": [
                    "total_amount",
                    "advancers",
                    "limit_up",
                    "limit_down",
                    "amount_ma20",
                    "amount_vs_yesterday_pct",
                    "volume_ratio",
                ],
                "source": "local:fact_stock_daily",
                "writer": "market_feature_store.sync.compute_local_stats.compute_market_overview_local(trade_date)",
                "depends_on": ["stock_daily"],
            },
            {
                "name": "industry",
                "columns": [
                    "industry_1",
                    "industry_1_ratio",
                    "industry_2",
                    "industry_3",
                    "top3_industry_ratio",
                    "concentration_state",
                ],
                "source": "local:fact_sw_l1_daily",
                "writer": "同 aggregates（compute_market_overview_local 读 fact_sw_l1_daily）",
                "depends_on": ["sw_l1_daily"],
            },
            {
                "name": "editorial",
                "columns": ["market_stage", "stage_day", "ice_point", "note"],
                "mode": ROUTE_MANUAL,
                "condition": "复盘会编辑字段：需创始人从数据中台导出参照标注（工单 #33 A），不可自动回补",
                "depends_on": [],
            },
        ],
    },
    "sw_l1_daily": {
        "mode": ROUTE_AUTO,
        "source_family": "akshare",
        "parts": [
            {
                "name": "index",
                "columns": ["close", "pct_chg", "amount"],
                "source": "akshare:index_hist_sw",
                "writer": "market_feature_store.sync.sync_akshare_sw_l1_daily.sync_akshare_sw_l1_daily(trade_date, days)",
                "depends_on": ["market_daily"],
                "note": "_target_dates 从 fact_market_daily 取日期：窗口内先要有 market_daily 的行",
            }
        ],
    },
    "stock_daily": {
        "mode": ROUTE_AUTO_HEAVY,
        "source_family": "mootdx",
        "parts": [
            {
                "name": "ohlc",
                "columns": ["close", "pct_chg", "amount"],
                "source": "mootdx",
                "writer": "python3 -m market_feature_store.cli sync-stock-daily --start-date <d> --end-date <d>",
                "depends_on": [],
                "note": "全市场逐股，量大；本单不执行，交 duckdb-backfill / daily-full 维护者",
            }
        ],
    },
}


# ---------------------------------------------------------------------------
# 事件收集
# ---------------------------------------------------------------------------


@dataclass
class GapEvent:
    run_id: str
    run_dir: Path
    dataset: str
    table: str
    metrics: list[str]
    dimensions: list[str]
    requested_start: str | None
    requested_end: str | None
    covered_range: str | None
    row_count: int
    uncovered: str
    ts: str


def discover_run_dirs(runs_root: Path) -> list[Path]:
    root = Path(runs_root).expanduser()
    if not root.is_dir():
        return []
    direct = sorted(p for p in root.iterdir() if p.is_dir() and p.name.startswith("run_"))
    if direct:
        return direct
    return sorted(p for p in root.glob("*/runs/run_*") if p.is_dir())


def _parse_ts(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.now().astimezone().tzinfo)
    return parsed


def parse_since(value: str | None, *, now: datetime | None = None) -> datetime | None:
    if not value or str(value).strip() in {"", "all"}:
        return None
    text = str(value).strip()
    current = now or datetime.now().astimezone()
    if text.endswith("d") and text[:-1].isdigit():
        return current - timedelta(days=int(text[:-1]))
    if text.endswith("h") and text[:-1].isdigit():
        return current - timedelta(hours=int(text[:-1]))
    return _parse_ts(text)


def collect_gap_events(runs_root: Path, *, since: datetime | None = None) -> list[GapEvent]:
    events: list[GapEvent] = []
    for run_dir in discover_run_dirs(runs_root):
        path = run_dir / HUNGER_FILENAME
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for line in text.splitlines():
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue
            if str(payload.get("event_type") or "") != EVENT_WINDOW_UNCOVERED:
                continue
            stamped = _parse_ts(payload.get("ts"))
            if since is not None and stamped is not None and stamped < since:
                continue
            dataset = str(payload.get("dataset") or payload.get("requested_name") or "").strip()
            if not dataset:
                continue
            events.append(
                GapEvent(
                    run_id=str(payload.get("run_id") or run_dir.name),
                    run_dir=run_dir,
                    dataset=dataset,
                    table=str(payload.get("table") or ""),
                    metrics=[str(m) for m in payload.get("metrics") or []],
                    dimensions=[str(d) for d in payload.get("dimensions") or []],
                    requested_start=payload.get("requested_start") or None,
                    requested_end=payload.get("requested_end") or None,
                    covered_range=payload.get("covered_range") or None,
                    row_count=int(payload.get("row_count") or 0),
                    uncovered=str(payload.get("uncovered") or "all"),
                    ts=str(payload.get("ts") or ""),
                )
            )
    return events


def _load_run_meta(run_dir: Path) -> dict[str, Any]:
    path = run_dir / "run.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


# ---------------------------------------------------------------------------
# 请求构建（合并重复缺口，保留消费者列表）
# ---------------------------------------------------------------------------


@dataclass
class DataRequest:
    request_id: str
    dataset: str
    table: str
    window_start: str
    window_end: str
    fields: list[str]
    consumers: list[dict[str, Any]]
    sources_tried: list[str]
    fill_route: dict[str, Any]
    priority: float
    first_asked_at: str | None
    last_asked_at: str | None
    event_count: int
    after_fill: str = "重算受影响子问题并恢复原会话研究，不让用户重新问整题"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _window_of(event: GapEvent) -> tuple[str, str] | None:
    start = event.requested_start or event.requested_end
    end = event.requested_end or event.requested_start
    if not start or not end:
        return None
    if start > end:
        start, end = end, start
    return start, end


def _overlaps(a: tuple[str, str], b: tuple[str, str]) -> bool:
    return a[0] <= b[1] and b[0] <= a[1]


def request_id_for(dataset: str, window_start: str, window_end: str) -> str:
    digest = hashlib.sha1(f"{dataset}|{window_start}|{window_end}".encode("utf-8")).hexdigest()
    return f"{REQUEST_ID_PREFIX}{digest[:10]}"


def route_for(dataset: str) -> dict[str, Any]:
    route = FILL_ROUTES.get(dataset)
    if route is not None:
        return json.loads(json.dumps(route, ensure_ascii=False))
    pending = PENDING_SYNC_SOURCES.get(dataset)
    if pending is not None:
        return {
            "mode": ROUTE_PENDING_SYNC,
            "source_family": dataset,
            "condition": f"{pending['label']}：{pending['sync_status']}（{pending['status_basis']}）；{pending['note']}",
            "writer": pending["writer_ref"],
            "parts": [],
        }
    return json.loads(json.dumps(_FUPANHUI_MANUAL, ensure_ascii=False))


def _describe_source_tried(event: GapEvent) -> str:
    covered = event.covered_range or "库内该窗无行"
    side = {
        "all": "整窗未覆盖",
        "front": "窗口前端未覆盖",
        "back": "窗口末端未覆盖",
        "both": "窗口两端未覆盖",
    }.get(event.uncovered, event.uncovered)
    return f"finance_query dataset={event.dataset} 返回 {event.row_count} 行（{side}；实际覆盖 {covered}）"


def _priority(consumers: list[dict[str, Any]], route: dict[str, Any], last_asked: str | None, *, now: datetime) -> float:
    distinct_runs = len({c["run_id"] for c in consumers})
    distinct_questions = len({str(c.get("question") or "").strip() for c in consumers if c.get("question")})
    score = 2.0 * distinct_runs + 1.0 * distinct_questions
    if route.get("mode") == ROUTE_AUTO:
        score += 1.0
    stamped = _parse_ts(last_asked)
    if stamped is not None:
        age_days = (now - stamped).days
        if age_days <= 7:
            score += 1.0
        elif age_days > 30:
            # 长期无人再问的缺口降优先。
            score -= 1.0
    return round(score, 2)


def build_requests(
    events: list[GapEvent],
    *,
    now: datetime | None = None,
) -> list[DataRequest]:
    """同 dataset 且窗口重叠的事件合并为一个请求；窗口取并集，消费者取并集。"""

    current = now or datetime.now().astimezone()
    groups: dict[str, list[dict[str, Any]]] = {}
    for event in events:
        window = _window_of(event)
        if window is None:
            continue
        bucket = groups.setdefault(event.dataset, [])
        merged = False
        for group in bucket:
            if _overlaps(group["window"], window):
                group["window"] = (min(group["window"][0], window[0]), max(group["window"][1], window[1]))
                group["events"].append(event)
                merged = True
                break
        if not merged:
            bucket.append({"window": window, "events": [event]})
    # 合并后可能出现新的重叠（A-B 分开、C 把两者连起来），再收敛一轮。
    for dataset, bucket in groups.items():
        changed = True
        while changed and len(bucket) > 1:
            changed = False
            for i in range(len(bucket)):
                for j in range(i + 1, len(bucket)):
                    if _overlaps(bucket[i]["window"], bucket[j]["window"]):
                        a, b = bucket[i], bucket[j]
                        a["window"] = (min(a["window"][0], b["window"][0]), max(a["window"][1], b["window"][1]))
                        a["events"].extend(b["events"])
                        del bucket[j]
                        changed = True
                        break
                if changed:
                    break

    requests: list[DataRequest] = []
    for dataset, bucket in groups.items():
        route = route_for(dataset)
        for group in bucket:
            window_start, window_end = group["window"]
            consumers: dict[str, dict[str, Any]] = {}
            fields: list[str] = []
            sources: list[str] = []
            timestamps: list[str] = []
            table = ""
            for event in group["events"]:
                table = table or event.table
                for metric in event.metrics:
                    if metric not in fields:
                        fields.append(metric)
                tried = _describe_source_tried(event)
                if tried not in sources:
                    sources.append(tried)
                if event.ts:
                    timestamps.append(event.ts)
                if event.run_id not in consumers:
                    meta = _load_run_meta(event.run_dir)
                    consumers[event.run_id] = {
                        "run_id": event.run_id,
                        "user": str(meta.get("user") or event.run_dir.parent.parent.name),
                        "question": str(meta.get("question") or ""),
                        "conversation_id": meta.get("session_id") or None,
                        "asked_at": meta.get("created_at") or event.ts or None,
                        "run_status": meta.get("status") or None,
                        "sub_question": f"{dataset} {window_start}..{window_end} 的 {'、'.join(event.metrics) or '结构化数据'}",
                    }
            timestamps.sort()
            consumer_list = list(consumers.values())
            requests.append(
                DataRequest(
                    request_id=request_id_for(dataset, window_start, window_end),
                    dataset=dataset,
                    table=table,
                    window_start=window_start,
                    window_end=window_end,
                    fields=fields,
                    consumers=consumer_list,
                    sources_tried=sources,
                    fill_route=route,
                    priority=_priority(consumer_list, route, timestamps[-1] if timestamps else None, now=current),
                    first_asked_at=timestamps[0] if timestamps else None,
                    last_asked_at=timestamps[-1] if timestamps else None,
                    event_count=len(group["events"]),
                )
            )
    requests.sort(key=lambda r: (-r.priority, r.dataset, r.window_start))
    return requests


# ---------------------------------------------------------------------------
# 完成检查（覆盖 / 关键值 / 日期与来源合理性）→ 完成结果
# ---------------------------------------------------------------------------


@dataclass
class Completion:
    request_id: str
    dataset: str
    table: str
    window_start: str
    window_end: str
    status: str
    reason: str
    expected_dates: int
    present_dates: int
    missing_dates: list[str]
    field_coverage: dict[str, float]
    invalid_rows: list[dict[str, Any]]
    satisfied_dependencies: dict[str, str]
    data_version: str | None
    affected_consumers: list[dict[str, Any]]
    checked_at: str
    db_path: str
    parts: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _connect_read_only(db_path: Path):
    import duckdb

    return duckdb.connect(str(db_path), read_only=True)


def _dataset_definition(dataset: str):
    try:
        from intelligence.services import finance_query

        return finance_query._DATASETS.get(dataset)  # noqa: SLF001 - 只读注册表
    except Exception:
        return None


def _table_columns(con, table: str) -> list[str]:
    try:
        return [str(row[0]) for row in con.execute(f"DESCRIBE {table}").fetchall()]
    except Exception:
        return []


def _key_columns(request: DataRequest, columns: list[str]) -> dict[str, list[str]]:
    """请求字段 → 物理列，按路线分组；没请求具体指标时用路线各部分的首列。"""

    definition = _dataset_definition(request.dataset)
    mapped: list[str] = []
    for name in request.fields:
        column = None
        if definition is not None:
            spec = definition.fields.get(name)
            column = getattr(spec, "column", None) if spec is not None else None
        column = column or name
        if column in columns and column not in mapped:
            mapped.append(column)
    parts: dict[str, list[str]] = {}
    route_parts = [p for p in request.fill_route.get("parts") or [] if p.get("mode") != ROUTE_MANUAL]
    if route_parts:
        for part in route_parts:
            part_cols = [c for c in part.get("columns") or [] if c in columns]
            wanted = [c for c in mapped if c in part_cols]
            if not mapped and part_cols:
                wanted = part_cols[:1]
            if wanted:
                parts[str(part["name"])] = wanted
        if not parts and mapped:
            parts["requested"] = mapped
    elif mapped:
        parts["requested"] = mapped
    return parts


def _trading_calendar(con, window_start: str, window_end: str) -> list[str]:
    try:
        rows = con.execute(
            "SELECT DISTINCT trade_date FROM fact_stock_daily WHERE trade_date BETWEEN ? AND ? ORDER BY trade_date",
            [window_start, window_end],
        ).fetchall()
    except Exception:
        return []
    return [str(row[0]) for row in rows]


def check_request(
    request: DataRequest,
    *,
    db_path: Path,
    today: date | None = None,
    connect: Callable[[Path], Any] | None = None,
) -> Completion:
    checked_at = datetime.now().astimezone().isoformat(timespec="seconds")
    current_day = today or date.today()
    opener = connect or _connect_read_only
    table = request.table
    definition = _dataset_definition(request.dataset)
    if not table and definition is not None:
        table = definition.table
    time_field = getattr(definition, "time_field", None) or "trade_date"
    base = dict(
        request_id=request.request_id,
        dataset=request.dataset,
        table=table,
        window_start=request.window_start,
        window_end=request.window_end,
        affected_consumers=list(request.consumers),
        checked_at=checked_at,
        db_path=str(db_path),
    )
    if not table:
        return Completion(
            status=STATUS_OPEN,
            reason="dataset 未注册到语义层，无物理表可查",
            expected_dates=0,
            present_dates=0,
            missing_dates=[],
            field_coverage={},
            invalid_rows=[],
            satisfied_dependencies={},
            data_version=None,
            **base,
        )
    try:
        con = opener(Path(db_path))
    except Exception as exc:
        return Completion(
            status=STATUS_SOURCE_FAILED,
            reason=f"库不可读：{type(exc).__name__}",
            expected_dates=0,
            present_dates=0,
            missing_dates=[],
            field_coverage={},
            invalid_rows=[],
            satisfied_dependencies={},
            data_version=None,
            **base,
        )
    try:
        columns = _table_columns(con, table)
        calendar = _trading_calendar(con, request.window_start, request.window_end)
        if table == "fact_stock_daily":
            calendar = calendar or []
        present_rows = con.execute(
            f"SELECT DISTINCT {time_field} FROM {table} WHERE {time_field} BETWEEN ? AND ? ORDER BY 1",
            [request.window_start, request.window_end],
        ).fetchall()
        present = [str(row[0]) for row in present_rows]
        if not calendar:
            expected = present
        else:
            expected = calendar
        missing = sorted(set(expected) - set(present))
        parts = _key_columns(request, columns)
        field_coverage: dict[str, float] = {}
        part_status: dict[str, str] = {}
        row_count = 0
        if present:
            row_count = int(
                con.execute(
                    f"SELECT COUNT(*) FROM {table} WHERE {time_field} BETWEEN ? AND ?",
                    [request.window_start, request.window_end],
                ).fetchone()[0]
            )
        for part_name, cols in parts.items():
            ok = True
            for col in cols:
                if row_count:
                    non_null = con.execute(
                        f"SELECT COUNT({col}) FROM {table} WHERE {time_field} BETWEEN ? AND ?",
                        [request.window_start, request.window_end],
                    ).fetchone()[0]
                    ratio = round(float(non_null) / float(row_count), 4)
                else:
                    ratio = 0.0
                field_coverage[col] = ratio
                if ratio < KEY_FIELD_MIN_COVERAGE:
                    ok = False
            part_status[part_name] = STATUS_SATISFIED if ok and not missing and present else STATUS_PARTIAL
        invalid_rows: list[dict[str, Any]] = []
        source_cols = [c for c in columns if c == "source" or c.endswith("_source")]
        if present and source_cols:
            for col in source_cols:
                try:
                    rows = con.execute(
                        f"SELECT {time_field}, {col} FROM {table} WHERE {time_field} BETWEEN ? AND ? AND {col} IS NOT NULL",
                        [request.window_start, request.window_end],
                    ).fetchall()
                except Exception:
                    continue
                for day, source in rows:
                    day_text = str(day)
                    if day_text < current_day.isoformat() and any(
                        marker in str(source) for marker in REALTIME_SOURCE_MARKERS
                    ):
                        invalid_rows.append({"trade_date": day_text, "column": col, "source": str(source), "reason": "历史日被实时源覆写"})
        future_rows = [d for d in present if d > current_day.isoformat()]
        for day in future_rows:
            invalid_rows.append({"trade_date": day, "column": time_field, "source": None, "reason": "日期晚于今天"})
        max_updated = None
        if "updated_at" in columns and present:
            try:
                max_updated = con.execute(
                    f"SELECT MAX(updated_at) FROM {table} WHERE {time_field} BETWEEN ? AND ?",
                    [request.window_start, request.window_end],
                ).fetchone()[0]
            except Exception:
                max_updated = None
        dependencies: dict[str, str] = {}
        for part in request.fill_route.get("parts") or []:
            for dep in part.get("depends_on") or []:
                if dep in dependencies:
                    continue
                dep_def = _dataset_definition(dep)
                dep_table = getattr(dep_def, "table", None)
                if not dep_table:
                    dependencies[dep] = "unknown"
                    continue
                try:
                    dep_present = con.execute(
                        f"SELECT COUNT(DISTINCT trade_date) FROM {dep_table} WHERE trade_date BETWEEN ? AND ?",
                        [request.window_start, request.window_end],
                    ).fetchone()[0]
                except Exception:
                    dependencies[dep] = "unknown"
                    continue
                if expected and int(dep_present) >= len(expected):
                    dependencies[dep] = STATUS_SATISFIED
                elif int(dep_present) > 0:
                    dependencies[dep] = STATUS_PARTIAL
                else:
                    dependencies[dep] = STATUS_OPEN
    finally:
        try:
            con.close()
        except Exception:
            pass

    if not present:
        status, reason = STATUS_OPEN, "窗口内无行"
        if not calendar and table != "fact_stock_daily":
            status, reason = STATUS_CALENDAR_UNKNOWN, "fact_stock_daily 在该窗无交易日历，无法判定应有哪些日"
    elif invalid_rows:
        status, reason = STATUS_INVALID, f"{len(invalid_rows)} 行日期/来源不合理（{invalid_rows[0]['reason']}）"
    elif missing:
        status, reason = STATUS_PARTIAL, f"缺 {len(missing)}/{len(expected)} 个交易日"
    elif parts and any(v != STATUS_SATISFIED for v in part_status.values()):
        weak = [c for c, r in field_coverage.items() if r < KEY_FIELD_MIN_COVERAGE]
        status, reason = STATUS_PARTIAL, f"有行但关键字段值空：{'、'.join(weak) or '关键列缺失'}"
    else:
        status, reason = STATUS_SATISFIED, f"{len(present)}/{len(expected)} 个交易日、关键字段非空"

    data_version = None
    if status == STATUS_SATISFIED:
        stable = json.dumps(
            {
                "table": table,
                "window": [request.window_start, request.window_end],
                "present": present,
                "max_updated_at": str(max_updated) if max_updated is not None else None,
                "field_coverage": field_coverage,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        data_version = hashlib.sha1(stable.encode("utf-8")).hexdigest()[:12]
    return Completion(
        status=status,
        reason=reason,
        expected_dates=len(expected),
        present_dates=len(present),
        missing_dates=missing[:60],
        field_coverage=field_coverage,
        invalid_rows=invalid_rows[:20],
        satisfied_dependencies=dependencies,
        data_version=data_version,
        parts=part_status,
        **base,
    )


def check_requests(
    requests: list[DataRequest],
    *,
    db_path: Path,
    today: date | None = None,
    connect: Callable[[Path], Any] | None = None,
) -> list[Completion]:
    return [check_request(r, db_path=db_path, today=today, connect=connect) for r in requests]


# ---------------------------------------------------------------------------
# 回执（完成信号只落一次；恢复只做一次）
# ---------------------------------------------------------------------------


def receipts_path(users_dir: Path, user: str) -> Path:
    return Path(users_dir).expanduser() / user / RECEIPTS_FILENAME


def load_receipts(users_dir: Path, user: str) -> list[dict[str, Any]]:
    path = receipts_path(users_dir, user)
    if not path.is_file():
        return []
    out: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            out.append(payload)
    return out


def append_receipt(users_dir: Path, user: str, record: dict[str, Any]) -> Path:
    path = receipts_path(users_dir, user)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(record)
    payload.setdefault("ts", datetime.now().astimezone().isoformat(timespec="seconds"))
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
    return path


@dataclass
class ResumeAction:
    request_id: str
    data_version: str
    consumer_run_id: str
    user: str
    conversation_id: str | None
    question: str
    completion: dict[str, Any]


def plan_resume(
    completions: list[Completion],
    *,
    users_dir: Path,
) -> tuple[list[ResumeAction], list[dict[str, Any]]]:
    """满足条件的请求 × 尚未恢复的消费者。已恢复过的同 data_version 跳过（重放幂等）。"""

    actions: list[ResumeAction] = []
    skipped: list[dict[str, Any]] = []
    cache: dict[str, list[dict[str, Any]]] = {}
    for completion in completions:
        if completion.status != STATUS_SATISFIED or not completion.data_version:
            continue
        for consumer in completion.affected_consumers:
            user = str(consumer.get("user") or "").strip()
            run_id = str(consumer.get("run_id") or "")
            question = str(consumer.get("question") or "").strip()
            if not user or not run_id or not question:
                skipped.append({"request_id": completion.request_id, "run_id": run_id, "reason": "消费者缺 user / question"})
                continue
            receipts = cache.setdefault(user, load_receipts(users_dir, user))
            done = any(
                r.get("event") == "resumed"
                and r.get("request_id") == completion.request_id
                and r.get("data_version") == completion.data_version
                and r.get("consumer_run_id") == run_id
                for r in receipts
            )
            if done:
                skipped.append(
                    {
                        "request_id": completion.request_id,
                        "run_id": run_id,
                        "reason": f"已按 data_version={completion.data_version} 恢复过，重放不重复",
                    }
                )
                continue
            actions.append(
                ResumeAction(
                    request_id=completion.request_id,
                    data_version=completion.data_version,
                    consumer_run_id=run_id,
                    user=user,
                    conversation_id=consumer.get("conversation_id") or None,
                    question=question,
                    completion=completion.to_dict(),
                )
            )
    return actions, skipped


def _http_json(url: str, *, method: str = "GET", payload: dict[str, Any] | None = None, timeout: float = 30) -> Any:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(url, data=data, method=method)
    request.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - 本机 Workbench
        body = response.read().decode("utf-8")
    return json.loads(body) if body else None


def record_completions(
    completions: list[Completion],
    *,
    users_dir: Path,
) -> list[dict[str, Any]]:
    """每个满足条件的 (request_id, data_version) 只落一条 completed 回执；重放不重复。"""

    written: list[dict[str, Any]] = []
    for completion in completions:
        if completion.status != STATUS_SATISFIED or not completion.data_version:
            continue
        users = sorted({str(c.get("user") or "") for c in completion.affected_consumers if c.get("user")})
        for user in users:
            existing = load_receipts(users_dir, user)
            if any(
                r.get("event") == "completed"
                and r.get("request_id") == completion.request_id
                and r.get("data_version") == completion.data_version
                for r in existing
            ):
                continue
            record = {
                "event": "completed",
                "request_id": completion.request_id,
                "dataset": completion.dataset,
                "table": completion.table,
                "window": [completion.window_start, completion.window_end],
                "data_version": completion.data_version,
                "satisfied_dependencies": completion.satisfied_dependencies,
                "field_coverage": completion.field_coverage,
                "affected_run_ids": [c.get("run_id") for c in completion.affected_consumers if c.get("user") == user],
                "db_path": completion.db_path,
            }
            append_receipt(users_dir, user, record)
            written.append({**record, "user": user})
    return written


def execute_resume(
    actions: list[ResumeAction],
    *,
    users_dir: Path,
    workbench_url: str | None,
    dry_run: bool = False,
    poll_timeout_sec: float = 600,
    poll_interval_sec: float = 3.0,
    http: Callable[..., Any] | None = None,
    sleep: Callable[[float], None] | None = None,
) -> list[dict[str, Any]]:
    """沿 Workbench 真实对话入口重问原问题；每个动作落一条 resumed 回执。"""

    import time

    call = http or _http_json
    wait = sleep or time.sleep
    results: list[dict[str, Any]] = []
    for action in actions:
        result: dict[str, Any] = {
            "request_id": action.request_id,
            "data_version": action.data_version,
            "consumer_run_id": action.consumer_run_id,
            "user": action.user,
            "conversation_id": action.conversation_id,
            "question": action.question,
        }
        if dry_run or not workbench_url:
            result["status"] = "planned" if dry_run else "no_workbench_url"
            results.append(result)
            continue
        base = workbench_url.rstrip("/")
        conversation_id = action.conversation_id
        try:
            if conversation_id:
                try:
                    call(f"{base}/api/conversations/{conversation_id}?user={urllib.parse.quote(action.user)}")
                except urllib.error.HTTPError as exc:
                    if exc.code != 404:
                        raise
                    conversation_id = None
            if not conversation_id:
                created = call(
                    f"{base}/api/conversations",
                    method="POST",
                    payload={"title": f"补数恢复 {action.request_id}", "user": action.user},
                )
                conversation_id = str(created.get("conversation_id"))
            submitted = call(
                f"{base}/api/conversations/{conversation_id}/messages",
                method="POST",
                payload={"content": action.question, "skill_mode": "auto", "user": action.user},
            )
            new_run_id = str(submitted.get("run_id") or "")
            status = "submitted"
            deadline = time.monotonic() + poll_timeout_sec
            while new_run_id and time.monotonic() < deadline:
                run = call(f"{base}/api/runs/{new_run_id}?user={urllib.parse.quote(action.user)}")
                status = str((run or {}).get("status") or "")
                if status in {"completed", "failed", "cancelled"}:
                    break
                wait(poll_interval_sec)
            result.update({"conversation_id": conversation_id, "new_run_id": new_run_id, "status": status})
        except Exception as exc:  # noqa: BLE001 - 单个消费者失败不阻断其余
            result.update({"status": "error", "error": f"{type(exc).__name__}: {str(exc)[:200]}"})
        record = {"event": "resumed", **{k: v for k, v in result.items() if k != "question"}}
        append_receipt(users_dir, action.user, record)
        results.append(result)
    return results


# ---------------------------------------------------------------------------
# fill：只在隔离 staging 库上编排现有 writer
# ---------------------------------------------------------------------------


def production_db_path() -> Path | None:
    try:
        from intelligence.paths import default_paths

        return (Path(default_paths().finance_root) / "db" / "market_feature_store.duckdb").resolve()
    except Exception:
        return None


def is_production_db(db_path: Path) -> bool:
    prod = production_db_path()
    try:
        return prod is not None and Path(db_path).expanduser().resolve() == prod
    except OSError:
        return False


def _iter_days(start: str, end: str) -> list[str]:
    a = date.fromisoformat(start)
    b = date.fromisoformat(end)
    out = []
    while a <= b:
        out.append(a.isoformat())
        a += timedelta(days=1)
    return out


_FILL_SCRIPT = r"""
import json, sys
from datetime import date
from unittest import mock
from market_feature_store import db
plan = json.loads(sys.argv[1])
out = {"steps": []}
con = None
try:
    if plan["dataset"] == "market_daily":
        parts = set(plan["parts"])
        if "sh_index" in parts:
            from market_feature_store.sync.sync_akshare_index_daily import sync_akshare_index_daily
            stats = sync_akshare_index_daily(start_date=plan["start"], end_date=plan["end"])
            out["steps"].append({"part": "sh_index", "stats": {k: str(v) for k, v in (stats or {}).items()}})
        if "aggregates" in parts or "industry" in parts:
            from market_feature_store.sync.compute_local_stats import compute_market_overview_local
            con = db.connect()
            days = [r[0].isoformat() for r in con.execute(
                "SELECT DISTINCT trade_date FROM fact_stock_daily WHERE trade_date BETWEEN ? AND ? ORDER BY 1",
                [plan["start"], plan["end"]]).fetchall()]
            done = []
            for td in days:
                res = compute_market_overview_local(td, con=con)
                done.append(str(res.get("action") or "written"))
            out["steps"].append({"part": "aggregates+industry", "days": len(days), "actions": sorted(set(done))})
    elif plan["dataset"] == "sw_l1_daily":
        import market_feature_store.sync.sync_akshare_sw_l1_daily as mod
        con = db.connect()
        days = [r[0] for r in con.execute(
            "SELECT trade_date FROM fact_market_daily WHERE trade_date BETWEEN ? AND ? ORDER BY 1",
            [plan["start"], plan["end"]]).fetchall()]
        con.close(); con = None
        if not days:
            out["steps"].append({"part": "index", "error": "fact_market_daily 在窗内无行：先补 market_daily（依赖未满足）"})
        else:
            end = days[-1]
            historical = plan.get("historical_workaround", True) and end < date.today()
            if historical:
                # 历史窗：writer 会把「当前实时快照」写到窗口末日上（为日更设计），
                # 这里只在隔离库里关掉实时步；正式修法归 writer 维护者（见 blocked/08.md）。
                with mock.patch.object(mod, "_fetch_realtime", return_value={}):
                    stats = mod.sync_akshare_sw_l1_daily(trade_date=end.isoformat(), days=len(days))
            else:
                stats = mod.sync_akshare_sw_l1_daily(trade_date=end.isoformat(), days=len(days))
            out["steps"].append({"part": "index", "historical_workaround": historical,
                                 "stats": {k: str(v)[:200] for k, v in (stats or {}).items()}})
    else:
        out["steps"].append({"error": f"no auto route for {plan['dataset']}"})
except Exception as exc:
    out["error"] = f"{type(exc).__name__}: {str(exc)[:300]}"
finally:
    if con is not None:
        con.close()
print(json.dumps(out, ensure_ascii=False, default=str))
"""


def fill_request(
    request: DataRequest,
    *,
    db_path: Path,
    dry_run: bool = False,
    historical_workaround: bool = True,
    python: str | None = None,
    repo_root: Path | None = None,
    timeout_sec: float = 900,
) -> dict[str, Any]:
    """按路线在隔离库上调现有 writer。生产库直接拒绝；manual / pending_sync 只显示真正缺什么。"""

    target = Path(db_path).expanduser()
    route = request.fill_route
    result: dict[str, Any] = {
        "request_id": request.request_id,
        "dataset": request.dataset,
        "window": [request.window_start, request.window_end],
        "route_mode": route.get("mode"),
        "db_path": str(target),
    }
    if is_production_db(target):
        result.update({"status": "refused", "reason": "指向生产库：生产事实写入由 daily-full 维护者执行，本命令只在隔离 staging 上跑"})
        return result
    if route.get("mode") in {ROUTE_MANUAL, ROUTE_PENDING_SYNC}:
        result.update(
            {
                "status": route.get("mode"),
                "reason": route.get("condition") or "无自动路线",
                "writer": route.get("writer"),
                "really_missing": route.get("condition"),
            }
        )
        return result
    if route.get("mode") == ROUTE_AUTO_HEAVY:
        result.update({"status": "not_executed", "reason": "量大路线不在本命令内执行", "writer": route.get("parts", [{}])[0].get("writer")})
        return result
    parts = [str(p["name"]) for p in route.get("parts") or [] if p.get("mode") != ROUTE_MANUAL]
    plan = {
        "dataset": request.dataset,
        "start": request.window_start,
        "end": request.window_end,
        "parts": parts,
        "historical_workaround": historical_workaround,
    }
    result["plan"] = plan
    if dry_run:
        result["status"] = "planned"
        return result
    env = dict(os.environ)
    env["MARKET_FEATURE_STORE_DB"] = str(target)
    cwd = str(repo_root) if repo_root else None
    try:
        proc = subprocess.run(
            [python or sys.executable, "-c", _FILL_SCRIPT, json.dumps(plan, ensure_ascii=False)],
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            env=env,
            cwd=cwd,
            check=False,
        )
    except subprocess.TimeoutExpired:
        result.update({"status": STATUS_SOURCE_FAILED, "reason": f"writer 超时 {timeout_sec}s"})
        return result
    stdout = (proc.stdout or "").strip().splitlines()
    payload: dict[str, Any] | None = None
    for line in reversed(stdout):
        try:
            candidate = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(candidate, dict):
            payload = candidate
            break
    result["returncode"] = proc.returncode
    result["stderr_tail"] = (proc.stderr or "")[-600:]
    if payload is None:
        result.update({"status": STATUS_SOURCE_FAILED, "reason": "writer 无结构化输出"})
        return result
    result["steps"] = payload.get("steps")
    if payload.get("error"):
        result.update({"status": STATUS_SOURCE_FAILED, "reason": str(payload["error"])})
    else:
        result["status"] = "filled"
    return result


# ---------------------------------------------------------------------------
# 产物封装 / 渲染
# ---------------------------------------------------------------------------


def wrap_artifact(
    requests: list[DataRequest],
    completions: list[Completion] | None = None,
    *,
    runs_root: Path,
    since: str | None,
    db_path: Path | None,
) -> dict[str, Any]:
    by_status: dict[str, int] = {}
    for completion in completions or []:
        by_status[completion.status] = by_status.get(completion.status, 0) + 1
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "runs_root": str(runs_root),
        "since": since,
        "db_path": str(db_path) if db_path else None,
        "summary": {
            "requests": len(requests),
            "consumers": sum(len(r.consumers) for r in requests),
            "auto_routes": sum(1 for r in requests if r.fill_route.get("mode") == ROUTE_AUTO),
            "manual_routes": sum(1 for r in requests if r.fill_route.get("mode") in {ROUTE_MANUAL, ROUTE_PENDING_SYNC}),
            "by_status": dict(sorted(by_status.items())),
        },
        "requests": [r.to_dict() for r in requests],
        "completions": [c.to_dict() for c in (completions or [])],
        "pending_sync_sources": PENDING_SYNC_SOURCES,
        "notes": [
            "请求由各 run 的 tool_hunger.jsonl 中 window_uncovered 事件聚合而来，可随时重建；不是第二份台账。",
            "补数写入仍由现有 writer 完成；fill 子命令拒绝指向生产库。",
            "完成信号与恢复回执落 users/<user>/data_request_receipts.jsonl，同一 data_version 只恢复一次。",
        ],
    }


def render_markdown(artifact: dict[str, Any]) -> str:
    lines = [
        "# 补数请求（问题驱动）",
        "",
        f"- 生成：{artifact.get('generated_at')}",
        f"- runs：{artifact.get('runs_root')}（since={artifact.get('since') or 'all'}）",
        f"- 库：{artifact.get('db_path') or '-'}",
        f"- 请求 {artifact['summary']['requests']} 个 / 消费者 {artifact['summary']['consumers']} 个 / 可自动补 {artifact['summary']['auto_routes']} / 只登记 {artifact['summary']['manual_routes']}",
        "",
        "| 请求 | dataset | 窗口 | 字段 | 消费者 | 路线 | 优先级 | 状态 | 说明 |",
        "| --- | --- | --- | --- | ---: | --- | ---: | --- | --- |",
    ]
    completions = {c["request_id"]: c for c in artifact.get("completions") or []}
    for item in artifact.get("requests") or []:
        completion = completions.get(item["request_id"]) or {}
        status = completion.get("status") or "-"
        reason = completion.get("reason") or (item["fill_route"].get("condition") or "")
        lines.append(
            f"| {item['request_id']} | {item['dataset']} | {item['window_start']}..{item['window_end']} | "
            f"{'、'.join(item['fields']) or '-'} | {len(item['consumers'])} | {item['fill_route'].get('mode')} | "
            f"{item['priority']} | {status} | {reason} |"
        )
    lines.append("")
    for item in artifact.get("requests") or []:
        lines.append(f"## {item['request_id']} · {item['dataset']} {item['window_start']}..{item['window_end']}")
        lines.append(
            f"- 提问 {item['event_count']} 次：首问 {item.get('first_asked_at') or '-'}｜末问 {item.get('last_asked_at') or '-'}"
            f"｜补完后：{item.get('after_fill')}"
        )
        for consumer in item["consumers"]:
            lines.append(f"- 消费者 {consumer['run_id']}（{consumer.get('user')}）：{consumer.get('question') or '-'}")
        for tried in item["sources_tried"]:
            lines.append(f"- 已尝试：{tried}")
        route = item["fill_route"]
        if route.get("mode") in {ROUTE_MANUAL, ROUTE_PENDING_SYNC}:
            lines.append(f"- 真正缺什么：{route.get('condition')}")
        else:
            for part in route.get("parts") or []:
                if part.get("mode") == ROUTE_MANUAL:
                    lines.append(f"- {part['name']}：{part.get('condition')}")
                else:
                    deps = "、".join(part.get("depends_on") or []) or "无"
                    lines.append(f"- {part['name']} ← {part.get('source')}（writer {part.get('writer')}；依赖 {deps}）")
        completion = completions.get(item["request_id"])
        if completion:
            lines.append(
                f"- 检查：{completion['status']}｜{completion['reason']}｜有行 {completion.get('present_dates')}/{completion.get('expected_dates')} 日"
                f"｜data_version={completion.get('data_version') or '-'}｜依赖 {completion.get('satisfied_dependencies') or {}}"
            )
            for bad in (completion.get("invalid_rows") or [])[:3]:
                lines.append(f"- 不合理行：{bad.get('trade_date')} {bad.get('column')}={bad.get('source')}（{bad.get('reason')}）")
        lines.append("")
    return "\n".join(lines)


__all__ = [
    "Completion",
    "DataRequest",
    "FILL_ROUTES",
    "GapEvent",
    "PENDING_SYNC_SOURCES",
    "RECEIPTS_FILENAME",
    "ResumeAction",
    "SCHEMA_VERSION",
    "STATUS_INVALID",
    "STATUS_OPEN",
    "STATUS_PARTIAL",
    "STATUS_SATISFIED",
    "append_receipt",
    "build_requests",
    "check_request",
    "check_requests",
    "collect_gap_events",
    "execute_resume",
    "fill_request",
    "is_production_db",
    "load_receipts",
    "parse_since",
    "plan_resume",
    "receipts_path",
    "record_completions",
    "render_markdown",
    "request_id_for",
    "route_for",
    "wrap_artifact",
]
