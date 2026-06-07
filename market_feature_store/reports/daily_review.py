from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from ..db import PROJECT_DIR, connect


def _fmt(value, digits: int = 2):
    if value is None:
        return "-"
    if isinstance(value, int):
        return str(value)
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return str(value)


def _pct(value, digits: int = 2):
    return "-" if value is None else f"{float(value):.{digits}f}%"


def _yi(value, digits: int = 2):
    return "-" if value is None else f"{float(value):.{digits}f}亿"


def _pp(value, digits: int = 2):
    if value is None:
        return "-"
    sign = "+" if float(value) > 0 else ""
    return f"{sign}{float(value):.{digits}f}pct"


def _change_text(current, previous, unit: str = ""):
    if current is None or previous is None:
        return "缺少昨日可比数据"
    delta = float(current) - float(previous)
    if abs(delta) < 1e-9:
        return "与昨日持平"
    verb = "增加" if delta > 0 else "减少"
    if float(current).is_integer() and float(previous).is_integer():
        value = str(int(abs(delta)))
    else:
        value = f"{abs(delta):.2f}"
    return f"较昨日{verb}{value}{unit}"


def _join_names(items, limit: int = 5):
    names = []
    for item in items:
        if item and item not in names:
            names.append(item)
        if len(names) >= limit:
            break
    return "、".join(names) if names else "-"


def _cell(value):
    text = "" if value is None else str(value)
    return text.replace("|", "／").replace("\n", " ")


def _table(headers, rows):
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    for row in rows:
        out.append("| " + " | ".join(_cell(v) for v in row) + " |")
    return "\n".join(out)


def _latest_date(con, table: str):
    row = con.execute(f"SELECT MAX(trade_date) FROM {table}").fetchone()
    return row[0] if row else None


def _prev_market_date(con, trade_date):
    row = con.execute(
        "SELECT MAX(trade_date) FROM fact_market_daily WHERE trade_date < ?",
        [trade_date],
    ).fetchone()
    return row[0] if row else None


def _dict_row(cur):
    names = [d[0] for d in cur.description]
    row = cur.fetchone()
    return dict(zip(names, row)) if row else {}


def _dict_rows(cur):
    names = [d[0] for d in cur.description]
    return [dict(zip(names, row)) for row in cur.fetchall()]


def _market_label(today, yesterday):
    price_day = bool(
        yesterday.get("sh_deviation_pct") is not None
        and today.get("sh_deviation_pct") is not None
        and yesterday["sh_deviation_pct"] < 0
        and today["sh_deviation_pct"] > 0
    )
    volume_day = bool(
        today.get("amount_vs_yesterday_pct") is not None
        and today.get("volume_ratio") is not None
        and today["amount_vs_yesterday_pct"] > 10
        and today["volume_ratio"] < 120
    )
    double_volume_day = bool(
        today.get("amount_vs_yesterday_pct") is not None
        and today.get("volume_ratio") is not None
        and today["amount_vs_yesterday_pct"] > 10
        and today["volume_ratio"] > 120
    )
    if price_day and double_volume_day:
        nature = "共振日"
    elif price_day and volume_day:
        nature = "转点日"
    else:
        nature = "普通交易日"
    return price_day, volume_day, double_volume_day, nature


def _advancers_series(con, trade_date):
    rows = con.execute(
        """
        SELECT trade_date, advancers
        FROM fact_market_daily
        WHERE trade_date <= ? AND advancers IS NOT NULL
        ORDER BY trade_date
        """,
        [trade_date],
    ).fetchall()
    series = []
    for i, (d, adv) in enumerate(rows):
        window = [r[1] for r in rows[max(0, i - 4): i + 1]]
        series.append({"date": d, "advancers": adv, "ma5": round(sum(window) / len(window), 2)})
    return series


def _ma5_wave_summary(series, window: int = 60, swing_delta: float = 700):
    if not series:
        return None
    from ..query import _zigzag
    recent = series[-window:]
    current = recent[-1]
    previous = series[-2] if len(series) >= 2 else None
    current_ma5 = float(current["ma5"])
    recent8 = recent[-8:]
    signs = []
    for left, right in zip(recent8, recent8[1:]):
        day_delta = float(right["ma5"]) - float(left["ma5"])
        if abs(day_delta) < 80:
            signs.append(0)
        elif day_delta > 0:
            signs.append(1)
        else:
            signs.append(-1)
    non_zero = [s for s in signs if s]
    sign_changes = sum(1 for a, b in zip(non_zero, non_zero[1:]) if a != b)
    recent_range = max(float(x["ma5"]) for x in recent8) - min(float(x["ma5"]) for x in recent8) if recent8 else 0
    is_shock = len(recent8) >= 6 and (sign_changes >= 3 or recent_range < swing_delta)
    pivots = []
    for idx, kind in _zigzag([float(x["ma5"]) for x in recent], swing_delta):
        row = recent[idx]
        if row["date"] == current["date"] and is_shock:
            continue
        pivots.append({**row, "kind": "波峰" if kind == "峰" else "波谷"})
    all_ma5 = [float(x["ma5"]) for x in recent]
    peak_ma5 = max(all_ma5)
    trough_ma5 = min(all_ma5)
    amplitude = peak_ma5 - trough_ma5
    if is_shock:
        position = "震荡区间"
    elif amplitude <= 1e-9:
        position = "窄幅震荡区"
    elif current_ma5 >= peak_ma5 * 0.85:
        position = "高位区"
    elif current_ma5 <= trough_ma5 + amplitude * 0.25:
        position = "低位区"
    else:
        position = "中位区"
    if is_shock:
        trend = "震荡"
    elif previous is None:
        trend = "缺少昨日可比数据"
    else:
        prev_ma5 = float(previous["ma5"])
        if abs(current_ma5 - prev_ma5) <= 1e-9:
            trend = "震荡"
        elif current_ma5 > prev_ma5:
            trend = "上升"
        else:
            trend = "下降"
    confirmed_peak = next((x for x in reversed(pivots) if x["kind"] == "波峰"), None)
    confirmed_trough = next((x for x in reversed(pivots) if x["kind"] == "波谷"), None)
    peak_text = f"上一确认波峰 {confirmed_peak['date']} MA5 {_fmt(confirmed_peak['ma5'], 1)}" if confirmed_peak else "暂无确认波峰"
    trough_text = f"上一确认波谷 {confirmed_trough['date']} MA5 {_fmt(confirmed_trough['ma5'], 1)}" if confirmed_trough else "暂无确认波谷"
    interval_rows = []
    for start, end in zip(pivots[-4:], pivots[-3:]):
        start_ma5 = float(start["ma5"])
        end_ma5 = float(end["ma5"])
        status = "上升" if end_ma5 > start_ma5 else "下降"
        interval_rows.append([
            f"{start['kind']}→{end['kind']}",
            f"{start['date']}→{end['date']}",
            status,
            f"{_fmt(start_ma5, 1)}→{_fmt(end_ma5, 1)}",
            f"{end_ma5 - start_ma5:+.1f}",
        ])
    if is_shock and recent8:
        start = recent8[0]
        start_ma5 = float(start["ma5"])
        interval_rows.append([
            "当前震荡区间",
            f"{start['date']}→{current['date']}",
            "震荡",
            f"{_fmt(start_ma5, 1)}→{_fmt(current_ma5, 1)}",
            f"{current_ma5 - start_ma5:+.1f}",
        ])
    elif pivots:
        start = pivots[-1]
        start_ma5 = float(start["ma5"])
        current_delta = current_ma5 - start_ma5
        if abs(current_delta) < swing_delta:
            status = "震荡"
        else:
            status = "上升" if current_delta > 0 else "下降"
        interval_rows.append([
            f"{start['kind']}→当前",
            f"{start['date']}→{current['date']}",
            status,
            f"{_fmt(start_ma5, 1)}→{_fmt(current_ma5, 1)}",
            f"{current_delta:+.1f}",
        ])
    else:
        start = recent8[0] if recent8 else current
        start_ma5 = float(start["ma5"])
        interval_rows.append([
            "当前区间",
            f"{start['date']}→{current['date']}",
            "震荡" if is_shock else trend,
            f"{_fmt(start_ma5, 1)}→{_fmt(current_ma5, 1)}",
            f"{current_ma5 - start_ma5:+.1f}",
        ])
    return {
        "rows": interval_rows[-4:],
        "position": position,
        "trend": trend,
        "peak_text": peak_text,
        "trough_text": trough_text,
    }


def _write_advancers_chart(series, output_path: Path):
    if not series:
        return None
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.dates as mdates
        import matplotlib.pyplot as plt
    except Exception:
        return None
    plt.rcParams["font.sans-serif"] = ["Arial Unicode MS", "PingFang SC", "Heiti TC", "STHeiti"]
    plt.rcParams["axes.unicode_minus"] = False
    output_path.parent.mkdir(parents=True, exist_ok=True)
    dates = [x["date"] for x in series]
    adv = [x["advancers"] for x in series]
    ma5 = [x["ma5"] for x in series]
    width = min(max(14, len(series) * 0.12), 30)
    fig, ax = plt.subplots(figsize=(width, 6))
    ax.plot(dates, adv, color="#2196F3", linewidth=1.2, label="涨家数", alpha=0.85)
    ax.plot(dates, ma5, color="#F44336", linewidth=1.8, linestyle="--", label="MA5")
    ax.axhline(y=2500, color="gray", linewidth=0.5, linestyle=":", alpha=0.5)
    ax.set_title("A股 涨家数走势", fontsize=16, fontweight="bold", pad=15)
    ax.set_ylabel("涨家数", fontsize=12)
    ax.legend(loc="upper left", fontsize=10)
    ax.grid(True, alpha=0.3)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
    if len(series) > 30:
        ax.xaxis.set_major_locator(mdates.WeekdayLocator(interval=1))
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()
    return output_path


def _period_top_sectors(con, trade_date, period: int):
    return _dict_rows(con.execute(
        f"""
        WITH dates AS (
          SELECT DISTINCT trade_date
          FROM fact_sector_daily
          WHERE trade_date <= ?
          ORDER BY trade_date DESC
          LIMIT {int(period)}
        ), calc AS (
          SELECT sector_name, any_value(sw_l1) sw_l1,
                 (exp(sum(ln(1 + pct_chg / 100))) - 1) * 100 ret,
                 arg_max(amount, trade_date) amount,
                 arg_max(diff_ratio, trade_date) diff_ratio,
                 count(*) cnt
          FROM fact_sector_daily
          WHERE trade_date IN (SELECT trade_date FROM dates)
            AND pct_chg IS NOT NULL
            AND pct_chg > -100
          GROUP BY sector_ts_code, sector_name
          HAVING count(*) = {int(period)}
        )
        SELECT sector_name, sw_l1, ret, amount, diff_ratio
        FROM calc
        ORDER BY ret DESC
        LIMIT 5
        """,
        [trade_date],
    ))


def _group_sector_rows(rows):
    grouped = defaultdict(list)
    for row in rows:
        grouped[row.get("sw_l1") or "未映射"].append(row)
    order = sorted(grouped, key=lambda sw: (-len(grouped[sw]), sw))
    return [(sw, grouped[sw]) for sw in order]


def _focus_sw_l1(today, double_groups, limit: int = 3):
    out = []
    for key in ("industry_1", "industry_2", "industry_3"):
        sw = today.get(key)
        if sw and sw not in out:
            out.append(sw)
    for sw, _rows in double_groups:
        if sw and sw not in out:
            out.append(sw)
        if len(out) >= limit:
            break
    return out[:limit]


def _sw_l1_double_red_matrix(con, trade_date, sw_l1: str, days: int = 15):
    date_rows = con.execute(
        """
        SELECT trade_date
        FROM fact_market_daily
        WHERE trade_date <= ?
        ORDER BY trade_date DESC
        LIMIT ?
        """,
        [trade_date, int(days)],
    ).fetchall()
    dates = [r[0] for r in reversed(date_rows)]
    if not dates:
        return {"sw_l1": sw_l1, "dates": [], "rows": []}
    start, end = dates[0], dates[-1]
    sectors = [
        r[0] for r in con.execute(
            """
            SELECT DISTINCT sector_name
            FROM fact_sector_daily
            WHERE trade_date BETWEEN ? AND ?
              AND sw_l1 = ?
              AND pct_chg > 0
              AND diff_ratio > 10
              AND amount > 500
            ORDER BY sector_name
            """,
            [start, end, sw_l1],
        ).fetchall()
    ]
    if not sectors:
        return {"sw_l1": sw_l1, "dates": dates, "rows": []}
    placeholders = ",".join("?" for _ in sectors)
    data_rows = con.execute(
        f"""
        SELECT trade_date, sector_name, pct_chg, diff_ratio, amount
        FROM fact_sector_daily
        WHERE trade_date BETWEEN ? AND ?
          AND sw_l1 = ?
          AND sector_name IN ({placeholders})
        """,
        [start, end, sw_l1] + sectors,
    ).fetchall()
    data = {(r[1], r[0]): (r[2], r[3], r[4]) for r in data_rows}
    parent_rows = con.execute(
        """
        SELECT trade_date, fupanhui_ratio, pct_chg
        FROM fact_sw_l1_daily
        WHERE trade_date BETWEEN ? AND ?
          AND sw_l1 = ?
        """,
        [start, end, sw_l1],
    ).fetchall()
    parent_data = {r[0]: (r[1], r[2]) for r in parent_rows}
    market_rows = con.execute(
        """
        WITH ranked AS (
          SELECT trade_date, total_amount, sh_index_pct_chg,
                 AVG(total_amount) OVER (
                   ORDER BY trade_date
                   ROWS BETWEEN 119 PRECEDING AND CURRENT ROW
                 ) AS amount_ma120
          FROM fact_market_daily
          WHERE trade_date <= ?
        )
        SELECT trade_date, total_amount, amount_ma120, sh_index_pct_chg
        FROM ranked
        WHERE trade_date BETWEEN ? AND ?
        """,
        [end, start, end],
    ).fetchall()
    market_data = {r[0]: (r[1], r[2], r[3]) for r in market_rows}
    rows = []
    parent_row = [f"申万一级：{sw_l1}（占比/涨跌幅）"]
    index_row = ["上证指数（120日均量比/涨跌幅）"]
    for d in dates:
        ratio, pct = parent_data.get(d, (None, None))
        if ratio is None and pct is None:
            parent_row.append("-")
        else:
            parent_row.append(f"{_pct(ratio, 1)}/{_pct(pct, 1)}")
        total_amount, amount_ma120, sh_pct = market_data.get(d, (None, None, None))
        market_volume_ratio = (total_amount / amount_ma120) if total_amount is not None and amount_ma120 else None
        if market_volume_ratio is None and sh_pct is None:
            index_row.append("-")
        else:
            index_row.append(f"{_fmt(market_volume_ratio, 2)}x/{_pct(sh_pct, 1)}")
    rows.append(parent_row)
    rows.append(index_row)
    for sector in sectors:
        row = [sector]
        for d in dates:
            pct, diff, amount = data.get((sector, d), (None, None, None))
            if diff is None or amount is None:
                row.append("-")
                continue
            cell = f"{_pct(pct, 1)}/{_fmt(diff, 1)}/{_fmt(amount, 0)}"
            if pct is not None and pct > 0 and diff > 10 and amount > 500:
                cell = f"🔥{cell}"
            row.append(cell)
        rows.append(row)
    return {"sw_l1": sw_l1, "dates": dates, "rows": rows}


def _parse_plate(plate, whitelist_json):
    if plate and plate != "-":
        return plate
    try:
        items = json.loads(whitelist_json or "[]")
    except Exception:
        items = []
    for item in items:
        if isinstance(item, dict) and item.get("type") != "I" and item.get("name"):
            return item["name"].strip()
    return "未映射主板块"


def _stock_high_rows(con, trade_date):
    rows = _dict_rows(con.execute(
        """
        SELECT stock_name, stock_ts_code, pct_chg, amount, sw_l1, plate, whitelist_sectors_json, primary_high_label
        FROM fact_stock_high_daily
        WHERE trade_date = ? AND high_periods_json LIKE '%120d%'
        ORDER BY amount DESC NULLS LAST
        """,
        [trade_date],
    ))
    for row in rows:
        row["plate_display"] = _parse_plate(row.get("plate"), row.get("whitelist_sectors_json"))
    return rows


def _stock_high_sw_l1_matrix(con, trade_date, sw_l1: str, days: int = 15, top: int = 20):
    date_rows = con.execute(
        "SELECT trade_date FROM fact_market_daily WHERE trade_date <= ? ORDER BY trade_date DESC LIMIT ?",
        [trade_date, int(days)],
    ).fetchall()
    dates = [r[0] for r in reversed(date_rows)]
    if not dates:
        return {"sw_l1": sw_l1, "dates": [], "rows": []}
    start, end = dates[0], dates[-1]
    data_rows = con.execute(
        """
        SELECT trade_date,
               COALESCE(NULLIF(plate, '-'), '未映射主板块') AS sector_name,
               COUNT(DISTINCT stock_ts_code) AS cnt
        FROM fact_stock_high_daily
        WHERE trade_date BETWEEN ? AND ?
          AND sw_l1 = ?
          AND high_periods_json LIKE '%120d%'
        GROUP BY 1, 2
        """,
        [start, end, sw_l1],
    ).fetchall()
    counts = {}
    totals = Counter()
    for trade_date, sector_name, cnt in data_rows:
        counts[(sector_name, trade_date)] = cnt
        totals[sector_name] += cnt
    matrix_rows = []
    for sector_name, _cnt in totals.most_common(top):
        matrix_rows.append([sector_name] + [counts.get((sector_name, d), "-") for d in dates])
    return {"sw_l1": sw_l1, "dates": dates, "rows": matrix_rows}


def _limit_up_sw_l1_matrix(con, trade_date, sw_l1: str, days: int = 15, top: int = 20):
    date_rows = con.execute(
        "SELECT trade_date FROM fact_market_daily WHERE trade_date <= ? ORDER BY trade_date DESC LIMIT ?",
        [trade_date, int(days)],
    ).fetchall()
    dates = [r[0] for r in reversed(date_rows)]
    if not dates:
        return {"sw_l1": sw_l1, "dates": [], "rows": []}
    start, end = dates[0], dates[-1]
    data_rows = con.execute(
        """
        WITH limit_stocks AS (
            SELECT DISTINCT trade_date, stock_ts_code
            FROM fact_theme_limit_stock_daily
            WHERE trade_date BETWEEN ? AND ?
        )
        SELECT s.trade_date, s.sector_name, COUNT(DISTINCT s.stock_ts_code) AS cnt
        FROM fact_sector_stock_daily s
        JOIN limit_stocks l
          ON s.trade_date = l.trade_date AND s.stock_ts_code = l.stock_ts_code
        WHERE s.trade_date BETWEEN ? AND ?
          AND s.sw_l1 = ?
        GROUP BY 1, 2
        """,
        [start, end, start, end, sw_l1],
    ).fetchall()
    counts = {}
    totals = Counter()
    for trade_date, sector_name, cnt in data_rows:
        counts[(sector_name, trade_date)] = cnt
        totals[sector_name] += cnt
    matrix_rows = []
    for sector_name, _cnt in totals.most_common(top):
        matrix_rows.append([sector_name] + [counts.get((sector_name, d), "-") for d in dates])
    return {"sw_l1": sw_l1, "dates": dates, "rows": matrix_rows}


def _clean_md_text(value):
    return "".join(ch for ch in str(value or "") if ch >= " " and ch != "\x7f").strip()


def _high_status_text(primary_label, periods_json):
    if primary_label:
        return _clean_md_text(primary_label)
    if not periods_json:
        return "否"
    try:
        periods = json.loads(periods_json)
    except (TypeError, json.JSONDecodeError):
        return _clean_md_text(periods_json) or "否"
    labels = []
    for item in periods if isinstance(periods, list) else []:
        label = item.get("label") if isinstance(item, dict) else None
        if label and label not in labels:
            labels.append(label)
    return "、".join(labels) if labels else "否"


def _sw_l1_stock_engines(con, trade_date, sw_l1: str, top: int = 20):
    rows = _dict_rows(con.execute(
        """
        WITH double_sectors AS (
            SELECT DISTINCT sector_name
            FROM fact_sector_daily
            WHERE trade_date = ?
              AND sw_l1 = ?
              AND pct_chg > 0
              AND diff_ratio > 10
              AND amount > 500
        ),
        stock_base AS (
            SELECT stock_ts_code,
                   any_value(stock_name) AS stock_name,
                   max(pct_chg) AS pct_chg,
                   max(amount) AS amount_yi
            FROM fact_sector_stock_daily
            WHERE trade_date = ?
              AND NULLIF(split_part(sw_industry, '-', 1), '') = ?
              AND pct_chg > 0
              AND amount IS NOT NULL
            GROUP BY stock_ts_code
        ),
        double_hits AS (
            SELECT stock_ts_code,
                   string_agg(DISTINCT sector_name, '、' ORDER BY sector_name) AS double_sectors
            FROM fact_sector_stock_daily
            WHERE trade_date = ?
              AND sw_l1 = ?
              AND sector_name IN (SELECT sector_name FROM double_sectors)
            GROUP BY stock_ts_code
        ),
        high_stocks AS (
            SELECT stock_ts_code, primary_high_label, high_periods_json
            FROM fact_stock_high_daily
            WHERE trade_date = ?
        ),
        ranked AS (
            SELECT row_number() OVER (ORDER BY sqrt(b.amount_yi) * b.pct_chg DESC NULLS LAST) AS rank,
                   b.stock_name, b.stock_ts_code, b.pct_chg, b.amount_yi,
                   sqrt(b.amount_yi) * b.pct_chg AS weighted,
                   h.primary_high_label, h.high_periods_json,
                   dh.double_sectors
            FROM stock_base b
            LEFT JOIN high_stocks h ON h.stock_ts_code = b.stock_ts_code
            LEFT JOIN double_hits dh ON dh.stock_ts_code = b.stock_ts_code
        )
        SELECT *
        FROM ranked
        WHERE rank <= ?
        ORDER BY rank
        """,
        [trade_date, sw_l1, trade_date, sw_l1, trade_date, sw_l1, trade_date, int(top)],
    ))
    stock_table = []
    for row in rows:
        double_sectors = _clean_md_text(row["double_sectors"])
        stock_table.append([
            row["rank"],
            _clean_md_text(row["stock_name"]),
            _clean_md_text(row["stock_ts_code"]),
            _pct(row["pct_chg"]),
            _yi(row["amount_yi"], 1),
            _fmt(row["weighted"], 2),
            _high_status_text(row["primary_high_label"], row["high_periods_json"]),
            "是" if double_sectors else "否",
            double_sectors or "-",
        ])
    return {"sw_l1": sw_l1, "trade_date": trade_date, "stock_rows": stock_table}


def _normalize_start_sector(name):
    mapping = {
        "PCB概念": "PCB",
        "芯片概念": "芯片",
        "英伟达概念": "英伟达",
        "6G概念": "6G",
    }
    return mapping.get(name, name)


def _startup_role(weighted, amount_yi, is_high120, is_limit):
    weighted_value = float(weighted or 0)
    amount_value = float(amount_yi or 0)
    if is_high120 and weighted_value >= 100 and amount_value >= 50:
        return "容量趋势发动机"
    if weighted_value >= 100 and amount_value >= 50:
        return "容量确认股"
    if is_limit and weighted_value >= 60:
        return "情绪发动机"
    if is_high120:
        return "趋势确认股"
    return "扩散确认股"


def _start_day_confirmation(con, start_date, sw_l1: str, top: int = 15):
    sector_rows = _dict_rows(con.execute(
        """
        SELECT sector_name, pct_chg, diff_ratio, amount
        FROM fact_sector_daily
        WHERE trade_date = ?
          AND sw_l1 = ?
          AND pct_chg > 0
          AND diff_ratio > 10
          AND amount > 500
        ORDER BY amount DESC
        LIMIT ?
        """,
        [start_date, sw_l1, int(top)],
    ))
    high_counts = Counter()
    for plate, cnt in con.execute(
        """
        SELECT COALESCE(NULLIF(plate, '-'), '未映射主板块') AS sector_name,
               COUNT(DISTINCT stock_ts_code) AS cnt
        FROM fact_stock_high_daily
        WHERE trade_date = ?
          AND sw_l1 = ?
          AND high_periods_json LIKE '%120d%'
        GROUP BY 1
        """,
        [start_date, sw_l1],
    ).fetchall():
        high_counts[_normalize_start_sector(plate)] += cnt
    limit_total = con.execute(
        "SELECT COUNT(*) FROM fact_theme_limit_stock_daily WHERE trade_date = ?",
        [start_date],
    ).fetchone()[0]
    limit_counts = Counter()
    if limit_total:
        for sector_name, cnt in con.execute(
            """
            WITH limit_stocks AS (
                SELECT DISTINCT trade_date, stock_ts_code
                FROM fact_theme_limit_stock_daily
                WHERE trade_date = ?
            )
            SELECT s.sector_name, COUNT(DISTINCT s.stock_ts_code) AS cnt
            FROM fact_sector_stock_daily s
            JOIN limit_stocks l
              ON s.trade_date = l.trade_date AND s.stock_ts_code = l.stock_ts_code
            WHERE s.trade_date = ?
              AND s.sw_l1 = ?
            GROUP BY 1
            """,
            [start_date, start_date, sw_l1],
        ).fetchall():
            limit_counts[sector_name] += cnt
    sector_names = [row["sector_name"] for row in sector_rows]
    sector_table = []
    for row in sector_rows:
        sector = row["sector_name"]
        limit_value = limit_counts.get(sector, 0) if limit_total else "数据缺失"
        if high_counts.get(sector, 0) >= 3 and row["amount"] >= 2000:
            status = "趋势容量核心"
        elif row["amount"] >= 1500:
            status = "容量确认"
        else:
            status = "扩散确认"
        sector_table.append([
            sector,
            _pct(row["pct_chg"]),
            _fmt(row["diff_ratio"], 1),
            _yi(row["amount"], 0),
            "是",
            high_counts.get(sector, 0),
            limit_value,
            status,
        ])
    if not sector_names:
        return {"sw_l1": sw_l1, "start_date": start_date, "sector_rows": [], "stock_rows": []}
    placeholders = ",".join("?" for _ in sector_names)
    stock_rows = _dict_rows(con.execute(
        f"""
        WITH sector_stocks AS (
            SELECT trade_date, stock_ts_code,
                   string_agg(DISTINCT sector_name, '、') AS sectors
            FROM fact_sector_stock_daily
            WHERE trade_date = ?
              AND sw_l1 = ?
              AND sector_name IN ({placeholders})
            GROUP BY 1, 2
        ),
        high_stocks AS (
            SELECT stock_ts_code, high_periods_json
            FROM fact_stock_high_daily
            WHERE trade_date = ?
              AND high_periods_json LIKE '%120d%'
        ),
        limit_stocks AS (
            SELECT DISTINCT stock_ts_code
            FROM fact_theme_limit_stock_daily
            WHERE trade_date = ?
        )
        SELECT d.stock_name, d.stock_ts_code, s.sectors,
               d.pct_chg, d.amount AS amount_yi,
               sqrt(d.amount) * d.pct_chg AS weighted,
               h.high_periods_json IS NOT NULL AS is_high120,
               l.stock_ts_code IS NOT NULL AS is_limit
        FROM fact_stock_daily d
        JOIN sector_stocks s USING (trade_date, stock_ts_code)
        LEFT JOIN high_stocks h ON h.stock_ts_code = d.stock_ts_code
        LEFT JOIN limit_stocks l ON l.stock_ts_code = d.stock_ts_code
        WHERE d.trade_date = ?
        ORDER BY weighted DESC NULLS LAST
        LIMIT ?
        """,
        [start_date, sw_l1] + sector_names + [start_date, start_date, start_date, int(top)],
    ))
    stock_table = []
    for row in stock_rows:
        is_high120 = bool(row["is_high120"])
        is_limit = bool(row["is_limit"])
        stock_table.append([
            _clean_md_text(row["stock_name"]),
            _clean_md_text(row["stock_ts_code"]),
            _clean_md_text(row["sectors"]),
            _pct(row["pct_chg"]),
            _yi(row["amount_yi"], 1),
            _fmt(row["weighted"], 2),
            "是" if is_high120 else "否",
            "是" if is_limit else ("数据缺失" if not limit_total else "否"),
            _startup_role(row["weighted"], row["amount_yi"], is_high120, is_limit),
        ])
    return {"sw_l1": sw_l1, "start_date": start_date, "sector_rows": sector_table, "stock_rows": stock_table}


def _theme_representatives(con, trade_date, theme_names):
    out = {}
    for theme in theme_names:
        rows = con.execute(
            """
            SELECT stock_name
            FROM fact_theme_limit_stock_daily
            WHERE trade_date = ? AND sector_name = ?
            ORDER BY amount DESC NULLS LAST
            LIMIT 5
            """,
            [trade_date, theme],
        ).fetchall()
        out[theme] = "、".join(r[0] for r in rows if r[0])
    return out


def _coverage(con, trade_date):
    tables = [
        "fact_market_daily", "fact_sector_daily", "fact_sw_l1_daily", "fact_sector_stock_daily",
        "fact_stock_high_daily", "fact_theme_limit_heat_daily",
        "fact_theme_limit_stock_daily", "fact_limit_advance_daily", "fact_stock_daily",
    ]
    rows = []
    for table in tables:
        max_date, cnt, target_cnt = con.execute(
            f"""
            SELECT MAX(trade_date), COUNT(*), COUNT(*) FILTER (WHERE trade_date = ?)
            FROM {table}
            """,
            [trade_date],
        ).fetchone()
        rows.append([table, str(max_date), cnt, target_cnt, "OK" if target_cnt > 0 else "缺目标日"])
    return rows


def build_daily_review(trade_date: str | None = None, output_path: str | None = None, chart_path: str | None = None, start_date: str | None = None) -> dict:
    con = connect(read_only=True)
    try:
        td = trade_date or str(_latest_date(con, "fact_market_daily"))
        prev_td = _prev_market_date(con, td)
        today = _dict_row(con.execute("SELECT * FROM fact_market_daily WHERE trade_date = ?", [td]))
        yesterday = _dict_row(con.execute("SELECT * FROM fact_market_daily WHERE trade_date = ?", [prev_td])) if prev_td else {}
        if not today:
            raise RuntimeError(f"fact_market_daily 未找到交易日: {td}")

        exports = PROJECT_DIR / "market_feature_store" / "exports"
        exports.mkdir(parents=True, exist_ok=True)
        out_path = Path(output_path) if output_path else exports / f"{td}-daily-review.md"
        img_path = Path(chart_path) if chart_path else exports / f"{td}-advancers-ma5.png"

        price_day, volume_day, double_volume_day, nature = _market_label(today, yesterday)
        adv_series = _advancers_series(con, td)
        chart_file = _write_advancers_chart(adv_series, img_path)
        cur_adv = adv_series[-1] if adv_series else {}
        prev_adv = adv_series[-2] if len(adv_series) >= 2 else {}
        ma5_wave = _ma5_wave_summary(adv_series)

        concentration = []
        for label, row in (("昨日", yesterday), ("今日", today)):
            if row:
                concentration.append([
                    label, row.get("top3_industry_ratio"), row.get("concentration_state"),
                    row.get("industry_1"), row.get("industry_1_ratio"),
                    row.get("industry_2"), row.get("industry_2_ratio"),
                    row.get("industry_3"), row.get("industry_3_ratio"),
                ])

        double_red = _dict_rows(con.execute(
            """
            SELECT sector_name, sw_l1, pct_chg, diff_ratio, amount
            FROM fact_sector_daily
            WHERE trade_date = ? AND pct_chg > 0 AND diff_ratio > 10 AND amount > 500
            ORDER BY sw_l1, diff_ratio DESC, amount DESC
            """,
            [td],
        ))
        single_red = _dict_rows(con.execute(
            """
            SELECT sector_name, sw_l1, pct_chg, diff_ratio, amount
            FROM fact_sector_daily
            WHERE trade_date = ? AND pct_chg > 0 AND diff_ratio > 10 AND (amount <= 500 OR amount IS NULL)
            ORDER BY sw_l1, diff_ratio DESC, amount DESC
            """,
            [td],
        ))

        stock_highs = _stock_high_rows(con, td)
        high_sw = Counter(row.get("sw_l1") or "未映射" for row in stock_highs)
        high_plate = defaultdict(list)
        for row in stock_highs:
            high_plate[row["plate_display"]].append(row)
        top_high_sw = [sw for sw, _ in high_sw.most_common(3)]

        limit_heat = _dict_rows(con.execute(
            """
            SELECT h.sector_name, COALESCE(fs.sw_l1, d.sw_l1, '未映射') sw_l1,
                   h.limit_up_count, h.total_count, h.market_share, h.fd_amount
            FROM fact_theme_limit_heat_daily h
            LEFT JOIN fact_sector_daily fs ON h.trade_date = fs.trade_date AND h.sector_ts_code = fs.sector_ts_code
            LEFT JOIN dim_sector d ON h.sector_ts_code = d.sector_ts_code
            WHERE h.trade_date = ?
            ORDER BY h.limit_up_count DESC, h.market_share DESC
            LIMIT 20
            """,
            [td],
        ))
        representatives = _theme_representatives(con, td, [row["sector_name"] for row in limit_heat[:10]])
        limit_sw = _dict_rows(con.execute(
            """
            SELECT COALESCE(sw_l1, '未映射') sw_l1, COUNT(DISTINCT stock_ts_code) cnt
            FROM fact_theme_limit_stock_daily
            WHERE trade_date = ?
            GROUP BY 1
            ORDER BY cnt DESC
            LIMIT 20
            """,
            [td],
        ))

        limit_advance = _dict_rows(con.execute(
            """
            SELECT stock_name, stock_ts_code, boards, first_limit_date, theme, pct_chg, promotion_rate
            FROM fact_limit_advance_daily
            WHERE trade_date = ? AND boards >= 3
            ORDER BY boards DESC, stock_name
            """,
            [td],
        ))

        weighted = _dict_rows(con.execute(
            """
            WITH base AS (
              SELECT f.stock_name, f.stock_ts_code, f.pct_chg_5d, f.amount, f.sector_name, f.sw_industry
              FROM fact_sector_stock_daily f
              WHERE f.trade_date = ? AND f.pct_chg_5d IS NOT NULL AND f.amount IS NOT NULL
            ),
            ranked AS (
              SELECT stock_name, stock_ts_code,
                     max(pct_chg_5d) gain5,
                     max(amount) amount_yi,
                     max(pct_chg_5d) * max(amount) / 100 weighted,
                     string_agg(sector_name, '、' ORDER BY amount DESC) FILTER (WHERE rn <= 5) sectors
              FROM (
                SELECT stock_name, stock_ts_code, pct_chg_5d, amount, sector_name,
                       row_number() OVER (PARTITION BY stock_ts_code ORDER BY amount DESC NULLS LAST) rn
                FROM base
              )
              GROUP BY stock_name, stock_ts_code
            ),
            stock_sw AS (
              SELECT stock_ts_code, standard_sw_l1
              FROM (
                SELECT stock_ts_code,
                       NULLIF(split_part(sw_industry, '-', 1), '') standard_sw_l1,
                       row_number() OVER (PARTITION BY stock_ts_code ORDER BY amount DESC NULLS LAST) rn
                FROM base
                WHERE sw_industry IS NOT NULL
              )
              WHERE rn = 1
            )
            SELECT r.stock_name, r.stock_ts_code, r.gain5, r.amount_yi, r.weighted,
                   COALESCE(st.standard_sw_l1, h.sw_l1, l.sw_l1, '未映射') sw_l1,
                   r.sectors
            FROM ranked r
            LEFT JOIN fact_stock_high_daily h
              ON h.trade_date = ? AND h.stock_ts_code = r.stock_ts_code
            LEFT JOIN (
              SELECT stock_ts_code, any_value(sw_l1) sw_l1
              FROM fact_theme_limit_stock_daily
              WHERE trade_date = ? AND sw_l1 IS NOT NULL
              GROUP BY stock_ts_code
            ) l ON l.stock_ts_code = r.stock_ts_code
            LEFT JOIN stock_sw st ON st.stock_ts_code = r.stock_ts_code
            ORDER BY r.weighted DESC
            LIMIT 10
            """,
            [td, td, td],
        ))

        double_groups = _group_sector_rows(double_red)
        single_groups = _group_sector_rows(single_red)
        focus_sw_l1 = _focus_sw_l1(today, double_groups)
        top_amount_sw_l1 = []
        for key in ("industry_1", "industry_2", "industry_3"):
            sw = today.get(key)
            if sw and sw not in top_amount_sw_l1:
                top_amount_sw_l1.append(sw)
        focus_matrices = [_sw_l1_double_red_matrix(con, td, sw) for sw in focus_sw_l1]
        high_matrices = [_stock_high_sw_l1_matrix(con, td, sw) for sw in focus_sw_l1]
        limit_matrices = [_limit_up_sw_l1_matrix(con, td, sw) for sw in focus_sw_l1]
        industry_stock_engines = [_sw_l1_stock_engines(con, td, sw) for sw in top_amount_sw_l1]
        top_double_sw = "、".join(f"{sw}({len(rows)})" for sw, rows in double_groups[:5])
        top_single_sw = "、".join(f"{sw}({len(rows)})" for sw, rows in single_groups[:5])
        top_high_sw_text = "、".join(f"{sw}({cnt})" for sw, cnt in high_sw.most_common(5))
        top_limit_text = "、".join(f"{r['sector_name']}({r['limit_up_count']})" for r in limit_heat[:5])
        top_weighted_text = "、".join(r["stock_name"] for r in weighted[:5])
        amount_delta = None
        if today.get("total_amount") is not None and yesterday.get("total_amount") is not None:
            amount_delta = today["total_amount"] - yesterday["total_amount"]
        concentration_delta = None
        if today.get("top3_industry_ratio") is not None and yesterday.get("top3_industry_ratio") is not None:
            concentration_delta = today["top3_industry_ratio"] - yesterday["top3_industry_ratio"]
        period_list = [1, 3, 5, 10]
        period_tops = {period: _period_top_sectors(con, td, period) for period in period_list}
        period_counts = Counter(r["sector_name"] for period in period_list for r in period_tops[period])
        multi_period = sorted(
            ((name, count) for name, count in period_counts.items() if count >= 2),
            key=lambda x: (-x[1], x[0]),
        )
        full_period = sorted(name for name, count in period_counts.items() if count == len(period_list))
        period_focus = _join_names([r["sector_name"] for period in period_list for r in period_tops[period]], 6)
        ten_day_leader = period_tops[10][0]["sector_name"] if period_tops[10] else "-"
        multi_period_text = "、".join(f"{name}({count}次)" for name, count in multi_period) or "无"
        full_period_text = "、".join(full_period) or "无"
        double_focus = "、".join(sw for sw, _ in double_groups[:5]) or "-"
        single_focus = "、".join(sw for sw, _ in single_groups[:5]) or "-"
        high_plate_text = "、".join(f"{plate}({len(items)})" for plate, items in sorted(high_plate.items(), key=lambda kv: (-len(kv[1]), kv[0]))[:5])
        limit_focus = _join_names([r["sector_name"] for r in limit_heat], 7)
        weighted_theme_counter = Counter()
        for row in weighted[:5]:
            for sector in (row.get("sectors") or "").split("、"):
                if sector:
                    weighted_theme_counter[sector] += 1
        weighted_theme_text = "、".join(name for name, _ in weighted_theme_counter.most_common(5)) or "-"
        market_mainline = double_focus if double_red else _join_names([r["sw_l1"] for r in limit_heat], 4)

        lines = []
        lines.append(f"# {td} 每日市场复盘")
        lines.append("")
        lines.append("> 自动生成自 `market_feature_store` 本地 DuckDB。报告只读取已入库数据，不临时编造缺失项。")
        lines.append("")
        lines.append("## 核心看板")
        lines.append(_table(
            ["维度", "结论"],
            [
                ["市场性质", f"{nature} / {today.get('market_stage') or '-'} 第{today.get('stage_day') or '-'}天"],
                ["指数表现", f"上证 {_fmt(today.get('sh_index_close'), 3)}，涨幅 {_pct(today.get('sh_index_pct_chg'))}，偏离度 {_pct(today.get('sh_deviation_pct'))}"],
                ["量能状态", f"成交额 {_yi(today.get('total_amount'))}，较昨日 {_pct(today.get('amount_vs_yesterday_pct'))}，相对20日均量 {_pct(today.get('volume_ratio'))}"],
                ["情绪状态", f"涨家数 {cur_adv.get('advancers', '-')}，MA5 {cur_adv.get('ma5', '-')}，涨停 {today.get('limit_up') or '-'}，跌停 {today.get('limit_down') or '-'}"],
                ["成交集中", f"前三行业 {_pct(today.get('top3_industry_ratio'))}，较昨日 {_pp(concentration_delta)}"],
                ["题材量能", f"双红 {len(double_red)} 个，单红 {len(single_red)} 个；双红主线：{top_double_sw}"],
                ["新高方向", f"120日新高 {len(stock_highs)} 只；前三申万：{top_high_sw_text}"],
                ["涨停方向", f"核心涨停题材：{top_limit_text}"],
                ["强度状态", f"{today.get('strength_status') or '-'}，强度加权涨幅 {_pct(today.get('strength_avg_pct'))}，强度成交占比 {_pct(today.get('strength_amount_pct'))}"],
                ["加权强股", top_weighted_text],
            ],
        ))
        lines.append("")
        lines.append("## 目录")
        lines.append("- [1. 指数 / 量能 / 偏离度 / 市场阶段](#1-指数--量能--偏离度--市场阶段)")
        lines.append("- [2. 市场情绪](#2-市场情绪)")
        lines.append("- [3. 成交前三行业](#3-成交前三行业)")
        lines.append("- [4. 1/3/5/10 日板块涨幅前五](#4-13510-日板块涨幅前五)")
        lines.append("- [5. 双红题材：按申万一级分组](#5-双红题材按申万一级分组)")
        lines.append("- [6. 重点申万一级近15日子板块双红矩阵](#6-重点申万一级近15日子板块双红矩阵)")
        lines.append("- [7. 单红题材：按申万一级分组](#7-单红题材按申万一级分组)")
        lines.append("- [8. 120日新高](#8-120日新高)")
        lines.append("- [9. 涨停题材](#9-涨停题材)")
        lines.append("- [10. 3板及以上个股](#10-3板及以上个股)")
        lines.append("- [11. 市场强度](#11-市场强度)")
        lines.append("- [12. 近五日加权涨幅 Top10](#12-近五日加权涨幅-top10)")
        lines.append("- [13. 数据覆盖检查](#13-数据覆盖检查)")
        lines.append("- [14. 市场环境总评](#14-市场环境总评)")
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("## 1. 指数 / 量能 / 偏离度 / 市场阶段")
        lines.append(_table(
            ["项目", "数值"],
            [
                ["市场阶段", f"{today.get('market_stage') or '-'} 第{today.get('stage_day') or '-'}天"],
                ["上证指数", f"{_fmt(today.get('sh_index_close'), 3)} / {_pct(today.get('sh_index_pct_chg'))}"],
                ["成交额", _yi(today.get("total_amount"))],
                ["较昨日比", _pct(today.get("amount_vs_yesterday_pct"))],
                ["20日均量", _yi(today.get("amount_ma20"))],
                ["相对量能比", _pct(today.get("volume_ratio"))],
                ["周均线", _fmt(today.get("sh_week_ma"))],
                ["偏离度", _pct(today.get("sh_deviation_pct"))],
                ["价日", "是" if price_day else "否"],
                ["量日", "是" if volume_day else "否"],
                ["双量日", "是" if double_volume_day else "否"],
                ["市场性质", nature],
            ],
        ))
        lines.append("")
        lines.append(f"> **结论**：今日为 **{nature}**；成交额较昨日变化 {_pct(today.get('amount_vs_yesterday_pct'))}，相对20日均量 {_pct(today.get('volume_ratio'))}，偏离度 {_pct(today.get('sh_deviation_pct'))}。")
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("## 2. 市场情绪")
        lines.append(_table(
            ["项目", "今日", "昨日"],
            [
                ["涨家数", cur_adv.get("advancers", "-"), prev_adv.get("advancers", "-")],
                ["涨家数 MA5", cur_adv.get("ma5", "-"), prev_adv.get("ma5", "-")],
                ["涨停", today.get("limit_up"), yesterday.get("limit_up")],
                ["跌停", today.get("limit_down"), yesterday.get("limit_down")],
            ],
        ))
        if chart_file:
            rel = chart_file.relative_to(out_path.parent)
            chart_uri = chart_file.resolve().as_uri()
            lines.append("")
            lines.append(f"[![涨家数MA5]({rel})]({chart_uri})")
            lines.append("")
            lines.append(f"> [点击打开涨家数 MA5 图]({chart_uri})")
        if ma5_wave:
            lines.append("")
            lines.append("### 涨家数 MA5 波段区间")
            lines.append(_table(["区间", "日期区间", "状态", "MA5区间", "变化"], ma5_wave["rows"]))
            lines.append("")
            lines.append(f"> **MA5位置**：当前处于 **{ma5_wave['position']}**，趋势为 **{ma5_wave['trend']}**；{ma5_wave['peak_text']}，{ma5_wave['trough_text']}。")
        lines.append("")
        lines.append(f"> **结论**：涨家数 {cur_adv.get('advancers', '-')}，MA5 {cur_adv.get('ma5', '-')}；涨停{_change_text(today.get('limit_up'), yesterday.get('limit_up'), '只')}，跌停{_change_text(today.get('limit_down'), yesterday.get('limit_down'), '只')}。")
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("## 3. 成交前三行业")
        lines.append(_table(
            ["日期", "前三占比", "集中度", "行业1", "占比1", "行业2", "占比2", "行业3", "占比3"],
            [[r[0], _pct(r[1]), r[2], r[3], _pct(r[4]), r[5], _pct(r[6]), r[7], _pct(r[8])] for r in concentration],
        ))
        lines.append("")
        lines.append(f"> **结论**：前三行业占比 {_pct(today.get('top3_industry_ratio'))}，较昨日 {_pp(concentration_delta)}；成交继续集中在 {today.get('industry_1') or '-'}、{today.get('industry_2') or '-'}、{today.get('industry_3') or '-'}。")
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("## 4. 1/3/5/10 日板块涨幅前五")
        for period in period_list:
            rows = period_tops[period]
            lines.append(f"### {period}日")
            lines.append(_table(
                ["板块", "申万一级", "涨幅", "成交额", "边际量"],
                [[r["sector_name"], r["sw_l1"], _pct(r["ret"]), _yi(r["amount"]), _fmt(r["diff_ratio"])] for r in rows],
            ))
            lines.append("")
        lines.append(f"> **结论**：短期涨幅榜显示 {period_focus} 等方向活跃；10日维度由 {ten_day_leader} 领涨。多周期共振题材（出现≥2次）：{multi_period_text}；全周期共振题材：{full_period_text}。")
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("## 5. 双红题材：按申万一级分组")
        lines.append(f"> 双红题材数量：**{len(double_red)}**；主线申万一级：{top_double_sw}。")
        lines.append("")
        for sw, rows in double_groups:
            lines.append(f"### {sw}")
            lines.append(_table(
                ["题材", "涨幅", "边际量", "成交额"],
                [[r["sector_name"], _pct(r["pct_chg"]), _fmt(r["diff_ratio"]), _yi(r["amount"])] for r in rows],
            ))
            lines.append("")
        lines.append(f"> **结论**：双红集中在 {double_focus} 等方向。")
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("## 6. 重点申万一级近15日子板块双红矩阵")
        lines.append("> 子板块单元格格式：当日涨幅/边际量/成交额亿；母板块行格式：成交占比/涨跌幅；上证指数行格式：120日均量比/涨跌幅；🔥 表示当日满足双红（日涨幅 > 0、边际量 > 10 且成交额 > 500亿）。")
        lines.append("")
        for matrix in focus_matrices:
            if not matrix["dates"]:
                continue
            lines.append(f"### {matrix['sw_l1']}")
            if matrix["rows"]:
                lines.append(_table(
                    ["子板块"] + [str(d)[5:] for d in matrix["dates"]],
                    matrix["rows"],
                ))
            else:
                lines.append("近15个交易日暂无双红子板块。")
            lines.append("")
        lines.append(f"> **结论**：重点观察申万一级为 {_join_names(focus_sw_l1, 3)}；🔥越连续，说明子板块边际量与成交额越持续。")
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("## 7. 申万一级行业个股发动机：成交占比前三行业")
        lines.append("> 每个成交占比前三申万一级行业列出当日开根加权 Top20；当日开根加权 = sqrt(成交额亿) × 当日涨幅，用于和双红题材、新高状态做事实层对比。")
        lines.append("")
        for item in industry_stock_engines:
            lines.append(f"### {item['sw_l1']}")
            if item["stock_rows"]:
                lines.append(_table(
                    ["排序", "股票", "代码", "涨幅", "成交额", "当日开根加权", "新高状态", "命中双红", "双红题材"],
                    item["stock_rows"],
                ))
            else:
                lines.append("当日暂无可排序的行业个股发动机。")
            lines.append("")
        lines.append("> **结论**：先看行业内高开根加权个股是否集中命中双红题材，再结合新高状态判断行业发动机与题材归因是否一致；定性角色后续交给 serenity alpha 补全。")
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("## 8. 单红题材：按申万一级分组")
        lines.append(f"> 单红题材数量：**{len(single_red)}**；主要分布：{top_single_sw}。")
        lines.append("")
        for sw, rows in single_groups:
            lines.append(f"### {sw}")
            lines.append(_table(
                ["题材", "涨幅", "边际量", "成交额"],
                [[r["sector_name"], _pct(r["pct_chg"]), _fmt(r["diff_ratio"]), _yi(r["amount"])] for r in rows],
            ))
            lines.append("")
        lines.append(f"> **结论**：单红以 {single_focus} 等方向为主。")
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("## 9. 120日新高")
        lines.append(f"> 120日新高数量：**{len(stock_highs)}**；前三申万一级：{top_high_sw_text}。")
        lines.append("")
        lines.append(_table(["申万一级", "数量"], [[sw, cnt] for sw, cnt in high_sw.most_common(20)]))
        lines.append("")
        lines.append("### 近15日120日新高映射矩阵")
        lines.append("> 单元格为当日120日新高去重个股数；按申万一级分组，行是该申万一级内的题材映射。")
        lines.append("")
        for matrix in high_matrices:
            if not matrix["dates"]:
                continue
            lines.append(f"### {matrix['sw_l1']}")
            if matrix["rows"]:
                lines.append(_table(
                    ["题材"] + [str(d)[5:] for d in matrix["dates"]],
                    matrix["rows"],
                ))
            else:
                lines.append("近15个交易日暂无120日新高映射。")
            lines.append("")
        lines.append(f"> **结论**：120日新高主要承载在 {_join_names(top_high_sw, 3)}；题材集中于 {high_plate_text}。")
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("## 10. 涨停题材")
        lines.append("### 近15日子板块涨停矩阵")
        lines.append("> 单元格为该申万一级子板块成分股中，当日涨停的去重个股数；行口径与第6节子板块双红矩阵一致。")
        lines.append("")
        for matrix in limit_matrices:
            if not matrix["dates"]:
                continue
            lines.append(f"### {matrix['sw_l1']}")
            if matrix["rows"]:
                lines.append(_table(
                    ["题材"] + [str(d)[5:] for d in matrix["dates"]],
                    matrix["rows"],
                ))
            else:
                lines.append("近15个交易日暂无涨停映射。")
            lines.append("")
        lines.append("### 当日涨停题材 Top20")
        lines.append(_table(
            ["题材", "申万一级映射", "涨停数", "市场占比", "封单金额", "代表涨停股"],
            [[r["sector_name"], r["sw_l1"], r["limit_up_count"], _pct(r["market_share"]), _yi((r["fd_amount"] or 0) / 10000), representatives.get(r["sector_name"], "")] for r in limit_heat[:20]],
        ))
        lines.append("")
        lines.append("### 涨停个股所属申万一级分布")
        lines.append(_table(["申万一级", "涨停个股数"], [[r["sw_l1"], r["cnt"]] for r in limit_sw]))
        lines.append("")
        lines.append(f"> **结论**：涨停题材核心集中在 {limit_focus}。")
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("## 11. 3板及以上个股")
        lines.append(_table(
            ["股票", "代码", "连板数", "首板日期", "题材", "涨幅", "晋级率"],
            [[r["stock_name"], r["stock_ts_code"], r["boards"], r["first_limit_date"], r["theme"], _pct(r["pct_chg"]), r["promotion_rate"]] for r in limit_advance],
        ))
        lines.append("")
        lines.append(f"> **结论**：3板及以上个股 {len(limit_advance)} 只，最高连板 {max([r['boards'] for r in limit_advance], default='-')} 板。")
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("## 12. 市场强度")
        lines.append(_table(
            ["指标", "今日", "昨日"],
            [
                ["强度加权涨幅", _pct(today.get("strength_avg_pct")), _pct(yesterday.get("strength_avg_pct"))],
                ["强度成交占比", _pct(today.get("strength_amount_pct")), _pct(yesterday.get("strength_amount_pct"))],
                ["强度成交额", _yi(today.get("strength_amount")), _yi(yesterday.get("strength_amount"))],
                ["强度成交环比", _pct(today.get("strength_marginal_pct")), _pct(yesterday.get("strength_marginal_pct"))],
                ["强度 MA5", _pct(today.get("strength_ma5_avg_pct")), _pct(yesterday.get("strength_ma5_avg_pct"))],
                ["强度 MA20", _pct(today.get("strength_ma20_avg_pct")), _pct(yesterday.get("strength_ma20_avg_pct"))],
                ["强度状态", today.get("strength_status"), yesterday.get("strength_status")],
            ],
        ))
        lines.append("")
        lines.append(f"> **结论**：市场强度状态为 **{today.get('strength_status') or '-'}**，强度成交占比 {_pct(today.get('strength_amount_pct'))}。")
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("## 13. 近五日加权涨幅 Top10")
        lines.append(_table(
            ["股票", "代码", "5日涨幅", "成交额", "加权涨幅", "申万一级", "主要题材"],
            [[r["stock_name"], r["stock_ts_code"], _pct(r["gain5"]), _yi(r["amount_yi"]), _fmt(r["weighted"]), r["sw_l1"], r["sectors"]] for r in weighted],
        ))
        lines.append("")
        lines.append(f"> **结论**：近五日加权强股前列为 {top_weighted_text}，主要关联 {weighted_theme_text}。")
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("## 14. 数据覆盖检查")
        lines.append(_table(["表", "最新日期", "总行数", "目标日行数", "状态"], _coverage(con, td)))
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("## 15. 市场环境总评")
        lines.append(f"> {td} 市场性质为 **{nature}**，市场阶段为 **{today.get('market_stage') or '-'}**。成交额 {_yi(today.get('total_amount'))}，较昨日 {_pct(today.get('amount_vs_yesterday_pct'))}；前三行业占比 {_pct(today.get('top3_industry_ratio'))}。主线集中在 {market_mainline} 相关方向，强度状态为 **{today.get('strength_status') or '-'}**。")
        lines.append("")
        lines.append(f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        out_path.write_text("\n".join(lines), encoding="utf-8")
        return {"trade_date": str(td), "output_path": str(out_path), "chart_path": str(chart_file) if chart_file else None}
    finally:
        con.close()
