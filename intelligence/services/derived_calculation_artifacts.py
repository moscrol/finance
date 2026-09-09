"""派生计算的结果视图与产物（工单 04 · 计算与产物）。

``derived_calculation`` 的 ``result`` 从 v2 起按 ``sandbox_fincalc.build_result`` 的协议
（``schema=derived_calculation.result/v1``：summary / tables / charts / params / formulas / notes）
组织；老脚本 ``emit({...})`` 出来的平铺字典仍然认——标量进 summary、其余进 extra。

这一层做三件事，都是**同一份 result 的不同出口**（正文、表、图不三处各算一遍）：

1. ``normalize_result``：把 result 读成 ``ResultView``，给证据观察值（``numeric_observations``）
   与模型观察文本（``compact_text``）用。
2. ``artifact_files``：渲染 ``calc-<id>.json``（全记录）、每张表一个 ``calc-<id>-t<n>.csv``、
   ``calc-<id>.html``（表 + 内联 SVG 图 + 参数 / 公式 / 输入 / 脚本，无脚本标签，走 legacy_html
   沙箱 iframe）。
3. ``publish_calculation_artifacts``：从 ``continuous-episode.json`` 同源的 ``private_artifact``
   里捞 ``tool_result`` 事件的 ``telemetry.derived_calculation`` 记录，经 ``RunStore.add_artifact``
   登记为 run 产物——复用既有 run / artifact 身份与下载端点，不另开文件服务。

层次：本模块不认识 ``RunStore`` 类型（duck-typed ``add_artifact``），不 import runtime。
"""

from __future__ import annotations

import csv
import html
import io
import json
import math
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field

RESULT_SCHEMA_V1 = "derived_calculation.result/v1"
ARTIFACT_PREFIX = "calc-"
CSV_RENDERER = "table"
_CALC_ID_RE = re.compile(r"^[0-9a-f]{16}$")
_MAX_TABLE_ROWS_IN_TEXT = 8
_PALETTE = ("#1f5fbf", "#d8641c", "#2e8b57", "#8b2e8b", "#b8860b", "#556b7d")


def is_calc_id(value: object) -> bool:
    return isinstance(value, str) and bool(_CALC_ID_RE.match(value))


# --------------------------------------------------------------------------- result view


@dataclass(frozen=True)
class ResultTable:
    name: str
    columns: tuple[str, ...]
    rows: tuple[tuple[object, ...], ...]
    unit: str | None = None
    note: str | None = None


@dataclass(frozen=True)
class ResultChart:
    name: str
    kind: str
    x: tuple[str, ...]
    series: Mapping[str, tuple[object, ...]]
    unit: str | None = None
    y_label: str | None = None


@dataclass(frozen=True)
class ResultView:
    schema: str
    summary: Mapping[str, object]
    tables: tuple[ResultTable, ...] = ()
    charts: tuple[ResultChart, ...] = ()
    params: Mapping[str, object] = field(default_factory=dict)
    formulas: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()
    extra: Mapping[str, object] = field(default_factory=dict)


def _is_number(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and not (isinstance(value, float) and (math.isnan(value) or math.isinf(value)))
    )


def _is_scalar(value: object) -> bool:
    return value is None or isinstance(value, (str, bool)) or _is_number(value)


def _table_from(raw: object, index: int) -> ResultTable | None:
    if not isinstance(raw, Mapping):
        return None
    columns = tuple(str(item) for item in (raw.get("columns") or ()))
    rows_raw = raw.get("rows") or ()
    rows: list[tuple[object, ...]] = []
    for row in rows_raw:
        if isinstance(row, Mapping):
            rows.append(tuple(row.get(column) for column in columns))
        elif isinstance(row, (list, tuple)):
            rows.append(tuple(row))
    if not columns and rows:
        columns = tuple(f"c{i + 1}" for i in range(len(rows[0])))
    unit = raw.get("unit")
    note = raw.get("note")
    return ResultTable(
        name=str(raw.get("name") or f"表{index + 1}"),
        columns=columns,
        rows=tuple(rows),
        unit=None if unit in (None, "") else str(unit),
        note=None if note in (None, "") else str(note),
    )


def _chart_from(raw: object, index: int) -> ResultChart | None:
    if not isinstance(raw, Mapping):
        return None
    series_raw = raw.get("series") or {}
    if not isinstance(series_raw, Mapping):
        return None
    kind = str(raw.get("kind") or "line").lower()
    return ResultChart(
        name=str(raw.get("name") or f"图{index + 1}"),
        kind=kind if kind in {"line", "bar"} else "line",
        x=tuple(str(item) for item in (raw.get("x") or ())),
        series={str(label): tuple(values or ()) for label, values in series_raw.items()},
        unit=None if raw.get("unit") in (None, "") else str(raw.get("unit")),
        y_label=None if raw.get("y_label") in (None, "") else str(raw.get("y_label")),
    )


def normalize_result(result: Mapping[str, object] | None) -> ResultView:
    """result → ``ResultView``。v1 协议按键读；平铺字典：标量进 summary，其余进 extra。"""

    data = dict(result or {})
    if data.get("schema") == RESULT_SCHEMA_V1:
        summary_raw = data.get("summary")
        summary = (
            {str(k): v for k, v in summary_raw.items() if _is_scalar(v)}
            if isinstance(summary_raw, Mapping)
            else {}
        )
        tables = tuple(
            item
            for index, raw in enumerate(data.get("tables") or ())
            if (item := _table_from(raw, index)) is not None
        )
        charts = tuple(
            item
            for index, raw in enumerate(data.get("charts") or ())
            if (item := _chart_from(raw, index)) is not None
        )
        params_raw = data.get("params")
        known = {"schema", "summary", "tables", "charts", "params", "formulas", "notes"}
        return ResultView(
            schema="v1",
            summary=summary,
            tables=tables,
            charts=charts,
            params=dict(params_raw) if isinstance(params_raw, Mapping) else {},
            formulas=tuple(str(item) for item in (data.get("formulas") or ())),
            notes=tuple(str(item) for item in (data.get("notes") or ())),
            extra={key: value for key, value in data.items() if key not in known},
        )
    return ResultView(
        schema="plain",
        summary={key: value for key, value in data.items() if _is_scalar(value)},
        extra={key: value for key, value in data.items() if not _is_scalar(value)},
    )


def _row_label(table: ResultTable, row: Sequence[object], index: int) -> str:
    first = row[0] if row else None
    if isinstance(first, str) and first.strip():
        return first.strip()
    return f"r{index + 1}"


def numeric_observations(view: ResultView) -> tuple[tuple[str, float], ...]:
    """结果里每一个数：(指标名, 值)。summary 标量按键名；表格按 ``表名.列名[行标签]``。

    这些数进派生证据的 ``observations``，判官按逐字节相等认「有据」；正文引用的表格数字
    因此有出处，删句时也不会被静默连坐掉。
    """

    out: list[tuple[str, float]] = []
    for key, value in view.summary.items():
        if _is_number(value):
            out.append((str(key), float(value)))
    for table in view.tables:
        for index, row in enumerate(table.rows):
            label = _row_label(table, row, index)
            for column, cell in zip(table.columns, row):
                if _is_number(cell) and not (column == table.columns[0] and isinstance(row[0], str)):
                    out.append((f"{table.name}.{column}[{label}]", float(cell)))
    return tuple(out)


def _fmt(value: object) -> str:
    if value is None:
        return "缺"
    if isinstance(value, bool):
        return "是" if value else "否"
    if _is_number(value):
        number = float(value)
        if number == int(number) and abs(number) < 1e15:
            return str(int(number))
        text = f"{number:.4f}".rstrip("0").rstrip(".")
        return text
    return str(value)


def compact_text(view: ResultView, *, budget: int = 700) -> str:
    """给模型看的紧凑文本：摘要 → 表（逐行）→ 公式 / 说明。超预算就截行并注明「完整见产物」。

    模型上下文里一次工具观察只有 900 字符（``tool_result_budget``），表格必须压成一行一行的
    ``行标签: 列=值`` 才装得下；装不下的行不是丢了，在 CSV / HTML 产物里。
    """

    parts: list[str] = []
    if view.summary:
        parts.append(
            "摘要 " + "，".join(f"{key}={_fmt(value)}" for key, value in view.summary.items())
        )
    for table in view.tables:
        header = f"表「{table.name}」" + (f"（{table.unit}）" if table.unit else "")
        rendered_rows: list[str] = []
        for index, row in enumerate(table.rows):
            label = _row_label(table, row, index)
            cells = [
                f"{column}={_fmt(cell)}"
                for column, cell in zip(table.columns, row)
                if not (column == table.columns[0] and isinstance(row[0], str))
            ]
            rendered_rows.append(f"{label}: " + " ".join(cells))
        shown = rendered_rows[:_MAX_TABLE_ROWS_IN_TEXT]
        text = header + " " + "；".join(shown)
        if len(rendered_rows) > len(shown):
            text += f"；…共 {len(rendered_rows)} 行，完整见产物"
        parts.append(text)
    if view.charts:
        parts.append("图 " + "、".join(f"「{chart.name}」({chart.kind})" for chart in view.charts))
    if view.formulas:
        parts.append("公式 " + "；".join(view.formulas[:3]))
    if view.notes:
        parts.append("说明 " + "；".join(view.notes[:3]))
    if view.schema == "plain" and view.extra:
        parts.append("其他 " + json.dumps(view.extra, ensure_ascii=False, default=str)[:200])
    joined = "｜".join(parts)
    if len(joined) <= budget:
        return joined
    # 从表格行开始砍：保留摘要与每张表的前几行，直到装得下。
    trimmed: list[str] = []
    remaining = budget
    for part in parts:
        if len(part) <= remaining:
            trimmed.append(part)
            remaining -= len(part) + 1
            continue
        cut = part[: max(0, remaining - 12)]
        if cut:
            trimmed.append(cut + "…（完整见产物）")
        break
    return "｜".join(trimmed)


# --------------------------------------------------------------------------- files


@dataclass(frozen=True)
class ArtifactFile:
    filename: str
    content: str
    renderer: str
    title: str


def planned_artifact_names(calc_id: str, view: ResultView) -> tuple[str, ...]:
    names = [f"{ARTIFACT_PREFIX}{calc_id}.json", f"{ARTIFACT_PREFIX}{calc_id}.html"]
    if view.tables:
        names.extend(f"{ARTIFACT_PREFIX}{calc_id}-t{index + 1}.csv" for index in range(len(view.tables)))
    elif view.summary:
        names.append(f"{ARTIFACT_PREFIX}{calc_id}-summary.csv")
    return tuple(names)


def render_json(record: Mapping[str, object]) -> str:
    return json.dumps(record, ensure_ascii=False, indent=2, default=str, sort_keys=True)


def _csv_text(columns: Sequence[str], rows: Iterable[Sequence[object]]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(list(columns))
    for row in rows:
        writer.writerow(["" if cell is None else _fmt(cell) if _is_number(cell) else str(cell) for cell in row])
    # UTF-8 BOM：Excel 直接双击打开中文列名不乱码。
    return "﻿" + buffer.getvalue()


def render_csv(table: ResultTable) -> str:
    return _csv_text(table.columns, table.rows)


def render_summary_csv(view: ResultView) -> str:
    return _csv_text(("指标", "值"), ((key, value) for key, value in view.summary.items()))


def _svg_chart(chart: ResultChart) -> str:
    width, height = 640, 320
    left, right, top, bottom = 64, 16, 28, 48
    plot_w, plot_h = width - left - right, height - top - bottom
    numeric_series = {
        label: [float(v) if _is_number(v) else None for v in values]
        for label, values in chart.series.items()
    }
    values = [v for series in numeric_series.values() for v in series if v is not None]
    if not values or not chart.x:
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="80">'
            f'<text x="8" y="40" font-size="13">{html.escape(chart.name)}：无可绘数值</text></svg>'
        )
    low, high = min(0.0, min(values)), max(0.0, max(values))
    if high == low:
        high = low + 1.0
    span = high - low

    def sy(value: float) -> float:
        return top + plot_h - (value - low) / span * plot_h

    n = max(1, len(chart.x))
    step = plot_w / n
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="{html.escape(chart.name)}">',
        f'<text x="{left}" y="18" font-size="14" font-weight="600">{html.escape(chart.name)}'
        + (f"（{html.escape(chart.unit)}）" if chart.unit else "")
        + "</text>",
    ]
    for tick in range(5):
        value = low + span * tick / 4
        y = sy(value)
        parts.append(
            f'<line x1="{left}" y1="{y:.1f}" x2="{width - right}" y2="{y:.1f}" stroke="#e3e3e3"/>'
            f'<text x="{left - 6}" y="{y + 4:.1f}" font-size="11" text-anchor="end">{_fmt(round(value, 4))}</text>'
        )
    zero_y = sy(0.0)
    parts.append(
        f'<line x1="{left}" y1="{zero_y:.1f}" x2="{width - right}" y2="{zero_y:.1f}" stroke="#666"/>'
    )
    for index, label in enumerate(chart.x):
        x = left + step * (index + 0.5)
        parts.append(
            f'<text x="{x:.1f}" y="{height - bottom + 16}" font-size="11" text-anchor="middle">{html.escape(label)}</text>'
        )
    series_count = max(1, len(numeric_series))
    for s_index, (label, series) in enumerate(numeric_series.items()):
        color = _PALETTE[s_index % len(_PALETTE)]
        if chart.kind == "bar":
            bar_w = step / (series_count + 1)
            for index, value in enumerate(series[:n]):
                if value is None:
                    continue
                x = left + step * index + bar_w * (s_index + 0.5)
                y0, y1 = sorted((sy(value), zero_y))
                parts.append(
                    f'<rect x="{x:.1f}" y="{y0:.1f}" width="{bar_w:.1f}" height="{max(0.5, y1 - y0):.1f}" fill="{color}"/>'
                )
        else:
            points = [
                f"{left + step * (index + 0.5):.1f},{sy(value):.1f}"
                for index, value in enumerate(series[:n])
                if value is not None
            ]
            if points:
                parts.append(
                    f'<polyline fill="none" stroke="{color}" stroke-width="2" points="{" ".join(points)}"/>'
                )
                for point in points:
                    x, y = point.split(",")
                    parts.append(f'<circle cx="{x}" cy="{y}" r="3" fill="{color}"/>')
        legend_x = left + 8 + s_index * 120
        parts.append(
            f'<rect x="{legend_x}" y="{height - 14}" width="10" height="10" fill="{color}"/>'
            f'<text x="{legend_x + 14}" y="{height - 5}" font-size="11">{html.escape(label)}</text>'
        )
    parts.append("</svg>")
    return "".join(parts)


def _html_table(columns: Sequence[str], rows: Iterable[Sequence[object]]) -> str:
    head = "".join(f"<th>{html.escape(str(column))}</th>" for column in columns)
    body = "".join(
        "<tr>" + "".join(f"<td>{html.escape(_fmt(cell))}</td>" for cell in row) + "</tr>" for row in rows
    )
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def render_html(record: Mapping[str, object], view: ResultView) -> str:
    """自包含 HTML：无 <script>，样式内联，图是内联 SVG。走 legacy_html 的沙箱 iframe 展示。"""

    calc_id = str(record.get("calc_id") or "")
    purpose = str(record.get("purpose") or "派生计算")
    as_of = str(record.get("as_of") or "未定日期")
    inputs = record.get("inputs") or ()
    sections: list[str] = [
        "<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'>",
        f"<title>{html.escape(purpose)} · 计算 {html.escape(calc_id)}</title>",
        "<style>body{font:14px/1.5 -apple-system,'PingFang SC',sans-serif;margin:24px;color:#222}"
        "table{border-collapse:collapse;margin:8px 0 16px}th,td{border:1px solid #ccc;padding:4px 8px;text-align:right}"
        "th:first-child,td:first-child{text-align:left}h1{font-size:20px}h2{font-size:16px;margin-top:24px}"
        "code,pre{background:#f5f5f5;padding:2px 4px}pre{padding:8px;overflow:auto}.meta{color:#555}</style></head><body>",
        f"<h1>{html.escape(purpose)}</h1>",
        f"<p class='meta'>计算编号 <code>{html.escape(calc_id)}</code> · as_of {html.escape(as_of)}（取输入最旧）· "
        f"隔离 {html.escape(str(record.get('enforcement') or ''))} · 输入 {len(inputs)} 条证据</p>",
    ]
    if view.params:
        sections.append("<h2>参数 / 假设</h2>" + _html_table(("参数", "值"), view.params.items()))
    if view.summary:
        sections.append("<h2>摘要</h2>" + _html_table(("指标", "值"), view.summary.items()))
    for table in view.tables:
        title = html.escape(table.name) + (f"（{html.escape(table.unit)}）" if table.unit else "")
        sections.append(f"<h2>{title}</h2>" + _html_table(table.columns, table.rows))
        if table.note:
            sections.append(f"<p class='meta'>{html.escape(table.note)}</p>")
    for chart in view.charts:
        sections.append(f"<h2>{html.escape(chart.name)}</h2>" + _svg_chart(chart))
    if view.formulas:
        sections.append(
            "<h2>公式</h2><ul>" + "".join(f"<li>{html.escape(item)}</li>" for item in view.formulas) + "</ul>"
        )
    if view.notes:
        sections.append(
            "<h2>说明</h2><ul>" + "".join(f"<li>{html.escape(item)}</li>" for item in view.notes) + "</ul>"
        )
    if inputs:
        rows = [
            (
                str(item.get("ref") or ""),
                str(item.get("tool") or ""),
                str(item.get("title") or "")[:60],
                str(item.get("source") or "")[:60],
                str(item.get("as_of") or ""),
                str(item.get("hash") or "")[:12],
            )
            for item in inputs
            if isinstance(item, Mapping)
        ]
        sections.append("<h2>输入证据</h2>" + _html_table(("编号", "工具", "标题", "来源", "日期", "哈希"), rows))
    script = str(record.get("script") or "")
    if script:
        sections.append(f"<details><summary>计算脚本（原样）</summary><pre>{html.escape(script)}</pre></details>")
    sections.append("</body></html>")
    return "".join(sections)


def artifact_files(record: Mapping[str, object]) -> tuple[ArtifactFile, ...]:
    """一条计算记录 → 全部产物文件。文件名只由 calc_id 决定，同一计算再跑一次得到同一组文件。"""

    calc_id = str(record.get("calc_id") or "")
    if not is_calc_id(calc_id):
        return ()
    view = normalize_result(record.get("result") if isinstance(record.get("result"), Mapping) else {})
    purpose = str(record.get("purpose") or "派生计算")[:24]
    files = [
        ArtifactFile(
            f"{ARTIFACT_PREFIX}{calc_id}.json",
            render_json(record),
            "json",
            f"计算记录：{purpose}",
        ),
        ArtifactFile(
            f"{ARTIFACT_PREFIX}{calc_id}.html",
            render_html(record, view),
            "html",
            f"计算报告：{purpose}",
        ),
    ]
    if view.tables:
        for index, table in enumerate(view.tables):
            files.append(
                ArtifactFile(
                    f"{ARTIFACT_PREFIX}{calc_id}-t{index + 1}.csv",
                    render_csv(table),
                    CSV_RENDERER,
                    f"数据表：{table.name[:24]}",
                )
            )
    elif view.summary:
        files.append(
            ArtifactFile(
                f"{ARTIFACT_PREFIX}{calc_id}-summary.csv",
                render_summary_csv(view),
                CSV_RENDERER,
                f"数据表：{purpose}",
            )
        )
    return tuple(files)


# --------------------------------------------------------------------------- publishing


def calc_records_from_private_artifact(private_artifact: Mapping[str, object] | None) -> list[dict[str, object]]:
    """``continuous-episode.json`` 同源的私有产物 → 其中全部派生计算记录（按 calc_id 去重，保留后者）。"""

    records: dict[str, dict[str, object]] = {}
    events = (private_artifact or {}).get("events") if isinstance(private_artifact, Mapping) else None
    for event in events or ():
        if not isinstance(event, Mapping) or event.get("kind") != "tool_result":
            continue
        payload = event.get("payload")
        if not isinstance(payload, Mapping) or payload.get("tool") != "derived_calculation":
            continue
        telemetry = payload.get("telemetry")
        record = telemetry.get("derived_calculation") if isinstance(telemetry, Mapping) else None
        if isinstance(record, Mapping) and is_calc_id(record.get("calc_id")):
            records[str(record["calc_id"])] = dict(record)
    return list(records.values())


def publish_calculation_artifacts(run_store, run_id: str, private_artifact: Mapping[str, object] | None) -> list[str]:
    """把本轮全部计算记录渲染成文件并登记为 run 产物；返回写出的文件名。

    ``run_store`` 只要求 ``add_artifact(run_id, filename, content, *, renderer, title)``。
    同名产物重复登记会覆盖（``RunStore.add_artifact`` 语义），所以幂等。
    """

    written: list[str] = []
    for record in calc_records_from_private_artifact(private_artifact):
        for item in artifact_files(record):
            run_store.add_artifact(
                run_id,
                item.filename,
                item.content,
                renderer=item.renderer,
                title=item.title,
            )
            written.append(item.filename)
    return written
