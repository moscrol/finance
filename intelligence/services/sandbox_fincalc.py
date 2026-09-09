"""fincalc — 沙箱内的财务计算助手（工单 04 · 计算与产物）。

**这个文件会被原样拷进沙箱工作目录**（``calculation_sandbox`` 写成 ``fincalc.py``，prelude
``from fincalc import *``），所以它必须是**纯标准库**、不 import 本仓任何模块、在没有
``evidence.json`` 的宿主进程里也能 import（测试直接 import 它、把证据列表当参数传）。

为什么要有它：模型写的计算脚本此前要自己解析 markdown 表格行、自己对齐报告期、自己判
「累计还是单季」。这三件事每次都重写一遍，每次都可能错一处。把它们收成几个有名字的函数，
错误就只可能出在一个地方，也只用在一个地方修。三条设计约束：

1. **不吞错**：分母为零、缺上一期累计、单位不认识，一律返回 ``None`` 并在结果行里写 ``note``，
   不抛异常也不填 0——0 会被当成真值传下去。
2. **口径写进名字**：``to_single_quarter`` 只吃累计序列；``to_yi`` 只做单位换算；同比 / 环比分开。
3. **修订值可见**：同一 (subject, as_of, metric) 有两个不同的数时，取来源日期更新的那条，并把被
   替换的值记进 ``revised_from``——沙箱数与某个来源不一致时先看这里，不要二选一。

结果协议（``build_result`` 产出，``emit_result`` 直接发）：

    {"schema": "derived_calculation.result/v1",
     "summary": {标量...}, "tables": [{name, columns, rows, unit, note}],
     "charts": [{name, kind, x, series, unit, y_label}],
     "params": {...}, "formulas": [...], "notes": [...]}

宿主侧 ``derived_calculation_artifacts`` 按这个形状渲染 CSV / HTML / JSON 产物，正文、表、
图都从同一份 ``result`` 生成，不三处各算一遍。
"""

from __future__ import annotations

import json
import math
import os

__all__ = [
    "PARAMS_FILE",
    "EVIDENCE_FILE",
    "SCHEMA",
    "evidence",
    "params",
    "observations",
    "subjects",
    "metrics",
    "series",
    "value_at",
    "quarter_of",
    "year_of",
    "period_label",
    "to_single_quarter",
    "yoy",
    "qoq",
    "ratio_series",
    "safe_div",
    "pct",
    "pct_change",
    "to_yi",
    "growth_path",
    "scenario_table",
    "sensitivity_grid",
    "table",
    "chart",
    "build_result",
    "fmt",
]

PARAMS_FILE = "params.json"
EVIDENCE_FILE = "evidence.json"
SCHEMA = "derived_calculation.result/v1"

_STATE: dict = {"evidence": None, "params": None}


def _load_json(name, default):
    try:
        with open(os.path.join(os.getcwd(), name), "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


def evidence():
    """沙箱工作目录里的 ``evidence.json``（与 prelude 的 ``EVIDENCE`` 是同一份）；宿主进程里为空列表。"""

    if _STATE["evidence"] is None:
        loaded = _load_json(EVIDENCE_FILE, [])
        _STATE["evidence"] = list(loaded) if isinstance(loaded, list) else []
    return _STATE["evidence"]


def params():
    """本次调用的 ``params``（模型传的假设 / 参数），没有就是空字典。"""

    if _STATE["params"] is None:
        loaded = _load_json(PARAMS_FILE, {})
        raw = loaded.get("params") if isinstance(loaded, dict) else None
        _STATE["params"] = dict(raw) if isinstance(raw, dict) else {}
    return _STATE["params"]


# --------------------------------------------------------------------------- numbers


def _is_number(value):
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and not (isinstance(value, float) and (math.isnan(value) or math.isinf(value)))
    )


def _round(value, digits):
    if value is None or digits is None:
        return value
    return round(float(value), int(digits))


def fmt(value, digits=2):
    """给正文用的数字文本：None → ``缺``；其余按位数四舍五入。"""

    if value is None:
        return "缺"
    if isinstance(value, bool):
        return str(value)
    if _is_number(value):
        return f"{round(float(value), digits):.{digits}f}"
    return str(value)


def safe_div(numerator, denominator, *, scale=1.0, digits=None):
    """安全除法：分子或分母缺、分母为零 → ``None``，绝不返回 0 或 inf。"""

    if not _is_number(numerator) or not _is_number(denominator):
        return None
    if float(denominator) == 0.0:
        return None
    return _round(float(numerator) / float(denominator) * float(scale), digits)


def pct(numerator, denominator, digits=2):
    """比率（%）：``numerator / denominator × 100``；零分母 → None。"""

    return safe_div(numerator, denominator, scale=100.0, digits=digits)


def pct_change(current, prior, digits=2):
    """变动率（%）：``(current − prior) / |prior| × 100``；基期为零或缺 → None。"""

    if not _is_number(current) or not _is_number(prior) or float(prior) == 0.0:
        return None
    return _round((float(current) - float(prior)) / abs(float(prior)) * 100.0, digits)


# 单位 → 一亿元里有多少个该单位（做除法，2.5e9 元 / 1e8 = 25.0 精确，乘 1e-8 会带浮点尾数）。
_UNITS_PER_YI = {
    "亿": 1.0,
    "亿元": 1.0,
    "yi": 1.0,
    "百万": 100.0,
    "百万元": 100.0,
    "million": 100.0,
    "万": 1e4,
    "万元": 1e4,
    "wan": 1e4,
    "千元": 1e5,
    "千": 1e5,
    "元": 1e8,
    "yuan": 1e8,
    "十亿": 0.1,
    "billion": 0.1,
}


def to_yi(value, unit="亿元"):
    """把带单位的数换成亿元。单位不认识 → None（不猜）。"""

    if not _is_number(value):
        return None
    divisor = _UNITS_PER_YI.get(str(unit or "").strip().lower())
    if divisor is None:
        divisor = _UNITS_PER_YI.get(str(unit or "").strip())
    if divisor is None:
        return None
    return float(value) / divisor


# --------------------------------------------------------------------------- periods

_QUARTER_BY_MONTH_DAY = {"03-31": 1, "06-30": 2, "09-30": 3, "12-31": 4}


def year_of(as_of):
    text = str(as_of or "")
    return int(text[:4]) if len(text) >= 4 and text[:4].isdigit() else None


def quarter_of(as_of):
    """报告期截止日 → 季度序号 1–4；不是季末日 → None。"""

    text = str(as_of or "")
    if len(text) < 10:
        return None
    return _QUARTER_BY_MONTH_DAY.get(text[5:10])


def period_label(as_of):
    """``2026-06-30`` → ``2026Q2``；解析不了就原样返回。"""

    year, quarter = year_of(as_of), quarter_of(as_of)
    if year is None or quarter is None:
        return str(as_of or "")
    return f"{year}Q{quarter}"


# --------------------------------------------------------------------------- evidence → observations


def observations(items=None, *, subject=None, metric=None, tool=None):
    """把证据里的结构化观察值摊平成行：subject / as_of / metric / value / ref / tool / evidence_as_of / title。

    只认数值型 value；``subject`` / ``metric`` / ``tool`` 可选过滤（精确匹配）。
    """

    rows = []
    for item in evidence() if items is None else items:
        if not isinstance(item, dict):
            continue
        if tool is not None and item.get("tool") != tool:
            continue
        for obs in item.get("observations") or ():
            if not isinstance(obs, dict) or not _is_number(obs.get("value")):
                continue
            if subject is not None and obs.get("subject") != subject:
                continue
            if metric is not None and obs.get("metric") != metric:
                continue
            rows.append(
                {
                    "subject": obs.get("subject"),
                    "as_of": obs.get("as_of"),
                    "metric": obs.get("metric"),
                    "value": float(obs.get("value")),
                    "ref": item.get("ref"),
                    "tool": item.get("tool"),
                    "evidence_as_of": item.get("as_of"),
                    "title": item.get("title"),
                }
            )
    return rows


def subjects(items=None):
    return sorted({row["subject"] for row in observations(items) if row["subject"]})


def metrics(items=None, subject=None):
    return sorted({row["metric"] for row in observations(items, subject=subject) if row["metric"]})


def series(subject, metric, items=None):
    """某标的某指标按报告期升序的序列：``[{as_of, value, ref, revised_from}]``。

    同一 as_of 出现多个不同值（同一来源修订、或两个来源）时取 ``evidence_as_of`` 最新的那条，
    被替换的值进 ``revised_from``（列表）。相同值只留一条。
    """

    by_as_of = {}
    for row in observations(items, subject=subject, metric=metric):
        key = str(row["as_of"] or "")
        current = by_as_of.get(key)
        if current is None:
            by_as_of[key] = {
                "as_of": key,
                "value": row["value"],
                "ref": row["ref"],
                "evidence_as_of": row["evidence_as_of"] or "",
                "revised_from": [],
            }
            continue
        if row["value"] == current["value"]:
            continue
        incoming = str(row["evidence_as_of"] or "")
        if incoming > str(current["evidence_as_of"] or ""):
            current["revised_from"].append(
                {"value": current["value"], "ref": current["ref"]}
            )
            current.update(
                value=row["value"], ref=row["ref"], evidence_as_of=incoming
            )
        else:
            current["revised_from"].append({"value": row["value"], "ref": row["ref"]})
    out = []
    for key in sorted(by_as_of):
        point = by_as_of[key]
        out.append(
            {
                "as_of": point["as_of"],
                "value": point["value"],
                "ref": point["ref"],
                "revised_from": list(point["revised_from"]),
            }
        )
    return out


def value_at(subject, metric, as_of, items=None):
    for point in series(subject, metric, items):
        if point["as_of"] == str(as_of):
            return point["value"]
    return None


def _points(points):
    """接受 ``[{as_of, value}]`` 或 ``[(as_of, value)]``，统一成 dict 列表并按 as_of 升序。"""

    out = []
    for point in points or ():
        if isinstance(point, dict):
            as_of, value = point.get("as_of"), point.get("value")
        else:
            as_of, value = point[0], point[1]
        out.append({"as_of": str(as_of or ""), "value": float(value) if _is_number(value) else None})
    return sorted(out, key=lambda item: item["as_of"])


# --------------------------------------------------------------------------- caliber conversions


def to_single_quarter(cumulative_points, digits=4):
    """累计序列 → 单季序列。**只吃累计口径**（东财 F10 / 新浪的季报数都是累计）。

    Q1 单季 = Q1 累计；Qn 单季 = Qn 累计 − Q(n−1) 累计（同一年）。上一期累计缺了就 ``value=None``
    并写 note，不外推、不填 0。返回 ``[{period, as_of, quarter, cumulative, value, method, note}]``。
    ``digits`` 只吸掉浮点减法的尾数噪声（396.5100000000001 → 396.51），不是口径。
    """

    points = _points(cumulative_points)
    by_as_of = {point["as_of"]: point["value"] for point in points}
    out = []
    for point in points:
        as_of, cumulative = point["as_of"], point["value"]
        year, quarter = year_of(as_of), quarter_of(as_of)
        row = {
            "period": period_label(as_of),
            "as_of": as_of,
            "quarter": quarter,
            "cumulative": cumulative,
            "value": None,
            "method": "",
            "note": "",
        }
        if year is None or quarter is None:
            row["note"] = "不是季末报告期，无法判定季度"
        elif cumulative is None:
            row["note"] = "本期累计缺失"
        elif quarter == 1:
            row["value"] = cumulative
            row["method"] = "Q1 单季 = Q1 累计"
        else:
            prior_md = {2: "03-31", 3: "06-30", 4: "09-30"}[quarter]
            prior_as_of = f"{year}-{prior_md}"
            prior = by_as_of.get(prior_as_of)
            if prior is None:
                row["note"] = f"缺上一期累计（{prior_as_of}），单季不可还原"
            else:
                row["value"] = _round(cumulative - prior, digits)
                row["method"] = f"Q{quarter} 单季 = {as_of} 累计 − {prior_as_of} 累计"
        out.append(row)
    return out


def yoy(points, digits=2):
    """同比：与上一年同一报告期比。``[{as_of, value, prior_as_of, prior, yoy_pct}]``；基期缺 → None。"""

    normalized = _points(points)
    by_as_of = {point["as_of"]: point["value"] for point in normalized}
    out = []
    for point in normalized:
        as_of = point["as_of"]
        year = year_of(as_of)
        prior_as_of = f"{year - 1}{as_of[4:]}" if year is not None and len(as_of) >= 10 else ""
        prior = by_as_of.get(prior_as_of)
        out.append(
            {
                "as_of": as_of,
                "value": point["value"],
                "prior_as_of": prior_as_of,
                "prior": prior,
                "yoy_pct": pct_change(point["value"], prior, digits=digits),
            }
        )
    return out


def qoq(points, digits=2):
    """环比：与序列里紧邻的上一点比（调用方保证是单季序列）。"""

    normalized = _points(points)
    out = []
    prior = None
    for point in normalized:
        out.append(
            {
                "as_of": point["as_of"],
                "period": period_label(point["as_of"]),
                "value": point["value"],
                "prior": prior,
                "qoq_pct": pct_change(point["value"], prior, digits=digits),
            }
        )
        prior = point["value"]
    return out


def ratio_series(numerator_points, denominator_points, *, scale=1.0, digits=2):
    """两条序列按 as_of 对齐做比值（如 经营现金流 / 归母净利润）；缺一边或分母为零 → ratio=None。"""

    numerators = {point["as_of"]: point["value"] for point in _points(numerator_points)}
    denominators = {point["as_of"]: point["value"] for point in _points(denominator_points)}
    out = []
    for as_of in sorted(set(numerators) | set(denominators)):
        numerator, denominator = numerators.get(as_of), denominators.get(as_of)
        out.append(
            {
                "as_of": as_of,
                "period": period_label(as_of),
                "numerator": numerator,
                "denominator": denominator,
                "ratio": safe_div(numerator, denominator, scale=scale, digits=digits),
            }
        )
    return out


# --------------------------------------------------------------------------- scenarios


def growth_path(base, rates_pct, labels=None, digits=2):
    """从基期值按逐期增速推演：``[{label, growth_pct, value}]``。基期缺 → 全 None。"""

    out = []
    current = float(base) if _is_number(base) else None
    for index, rate in enumerate(rates_pct or ()):
        label = labels[index] if labels and index < len(labels) else f"T+{index + 1}"
        if current is None or not _is_number(rate):
            out.append({"label": label, "growth_pct": rate, "value": None})
            current = None
            continue
        current = current * (1.0 + float(rate) / 100.0)
        out.append({"label": label, "growth_pct": float(rate), "value": _round(current, digits)})
    return out


def scenario_table(base, scenarios, *, name="收入情景", base_label="基期", unit="亿元", digits=2):
    """一期情景表：每个情景一个增速（%）→ 推演值与较基期变动。``scenarios`` 是 {情景名: 增速%}。"""

    rows = []
    for label, rate in (scenarios or {}).items():
        value = (
            _round(float(base) * (1.0 + float(rate) / 100.0), digits)
            if _is_number(base) and _is_number(rate)
            else None
        )
        rows.append([label, rate, value, None if value is None else _round(value - float(base), digits)])
    return table(
        name,
        ["情景", "增速%", f"推演值({unit})", f"较{base_label}变动({unit})"],
        rows,
        unit=unit,
        note=f"{base_label}={fmt(base, digits)} {unit}；推演值 = 基期 × (1 + 增速)",
    )


def sensitivity_grid(row_values, col_values, fn, *, name, row_name, col_name, unit=None, digits=2):
    """二维敏感性表：行变量 × 列变量，每格 ``fn(row, col)``；``fn`` 抛错或返回非数 → 该格 None。"""

    columns = [f"{row_name}\\{col_name}"] + [fmt(col, digits) for col in col_values]
    rows = []
    for row_value in row_values:
        cells = [fmt(row_value, digits)]
        for col_value in col_values:
            try:
                cell = fn(row_value, col_value)
            except Exception:  # noqa: BLE001 - 单格失败不拖垮整表
                cell = None
            cells.append(_round(cell, digits) if _is_number(cell) else None)
        rows.append(cells)
    return table(name, columns, rows, unit=unit, note=f"行={row_name}，列={col_name}；格值={fn.__doc__ or '按传入函数计算'}")


# --------------------------------------------------------------------------- result protocol


def _json_safe(value):
    if _is_number(value) or value is None or isinstance(value, (str, bool)):
        return value
    if isinstance(value, float):
        return None
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return str(value)


def table(name, columns, rows, *, unit=None, note=None):
    """一张表：``columns`` 列名、``rows`` 行（每行与列同长）。行里的 None 就是「缺」，别填 0。"""

    return {
        "name": str(name),
        "columns": [str(column) for column in columns],
        "rows": [[_json_safe(cell) for cell in row] for row in rows],
        "unit": None if unit is None else str(unit),
        "note": None if note is None else str(note),
    }


def chart(name, kind, x, series_by_label, *, unit=None, y_label=None):
    """一张图的数据：``kind`` 是 line 或 bar；``x`` 是横轴标签；``series_by_label`` 是 {系列名: 数值列表}。"""

    kind_text = str(kind or "line").lower()
    if kind_text not in {"line", "bar"}:
        kind_text = "line"
    return {
        "name": str(name),
        "kind": kind_text,
        "x": [str(item) for item in x],
        "series": {str(label): [_json_safe(v) for v in values] for label, values in dict(series_by_label).items()},
        "unit": None if unit is None else str(unit),
        "y_label": None if y_label is None else str(y_label),
    }


def build_result(summary=None, tables=(), charts=(), params=None, formulas=(), notes=(), **extra):
    """拼出结果协议 v1 的字典；``emit_result`` 直接把它 emit 出去。"""

    result = {
        "schema": SCHEMA,
        "summary": _json_safe(dict(summary or {})),
        "tables": [_json_safe(item) for item in tables or ()],
        "charts": [_json_safe(item) for item in charts or ()],
        "params": _json_safe(dict(params if params is not None else {})),
        "formulas": [str(item) for item in formulas or ()],
        "notes": [str(item) for item in notes or ()],
    }
    for key, value in extra.items():
        result[str(key)] = _json_safe(value)
    return result
