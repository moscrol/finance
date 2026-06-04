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
        LIMIT 3
        """,
        [trade_date],
    ))


def _group_sector_rows(rows):
    grouped = defaultdict(list)
    for row in rows:
        grouped[row.get("sw_l1") or "未映射"].append(row)
    order = sorted(grouped, key=lambda sw: (-len(grouped[sw]), sw))
    return [(sw, grouped[sw]) for sw in order]


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
        "fact_market_daily", "fact_sector_daily", "fact_sector_stock_daily",
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


def build_daily_review(trade_date: str | None = None, output_path: str | None = None, chart_path: str | None = None) -> dict:
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
            WHERE trade_date = ? AND diff_ratio > 10 AND amount > 500
            ORDER BY sw_l1, diff_ratio DESC, amount DESC
            """,
            [td],
        ))
        single_red = _dict_rows(con.execute(
            """
            SELECT sector_name, sw_l1, pct_chg, diff_ratio, amount
            FROM fact_sector_daily
            WHERE trade_date = ? AND diff_ratio > 10 AND (amount <= 500 OR amount IS NULL)
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
        period_tops = {period: _period_top_sectors(con, td, period) for period in [1, 3, 5, 10]}
        period_focus = _join_names([r["sector_name"] for period in [1, 3, 5, 10] for r in period_tops[period]], 6)
        ten_day_leader = period_tops[10][0]["sector_name"] if period_tops[10] else "-"
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
        lines.append("- [4. 1/3/5/10 日板块涨幅前三](#4-13510-日板块涨幅前三)")
        lines.append("- [5. 双红题材：按申万一级分组](#5-双红题材按申万一级分组)")
        lines.append("- [6. 单红题材：按申万一级分组](#6-单红题材按申万一级分组)")
        lines.append("- [7. 120日新高](#7-120日新高)")
        lines.append("- [8. 涨停题材](#8-涨停题材)")
        lines.append("- [9. 3板及以上个股](#9-3板及以上个股)")
        lines.append("- [10. 市场强度](#10-市场强度)")
        lines.append("- [11. 近五日加权涨幅 Top10](#11-近五日加权涨幅-top10)")
        lines.append("- [12. 数据覆盖检查](#12-数据覆盖检查)")
        lines.append("- [13. 市场环境总评](#13-市场环境总评)")
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
            lines.append("")
            lines.append(f"[![涨家数MA5]({rel})]({rel})")
            lines.append("")
            lines.append(f"> [点击在旁边窗口预览涨家数 MA5 图]({rel})")
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
        lines.append("## 4. 1/3/5/10 日板块涨幅前三")
        for period in [1, 3, 5, 10]:
            rows = period_tops[period]
            lines.append(f"### {period}日")
            lines.append(_table(
                ["板块", "申万一级", "涨幅", "成交额", "边际量"],
                [[r["sector_name"], r["sw_l1"], _pct(r["ret"]), _yi(r["amount"]), _fmt(r["diff_ratio"])] for r in rows],
            ))
            lines.append("")
        lines.append(f"> **结论**：短期涨幅榜显示 {period_focus} 等方向活跃；10日维度由 {ten_day_leader} 领涨。")
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
        lines.append("## 6. 单红题材：按申万一级分组")
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
        lines.append("## 7. 120日新高")
        lines.append(f"> 120日新高数量：**{len(stock_highs)}**；前三申万一级：{top_high_sw_text}。")
        lines.append("")
        lines.append(_table(["申万一级", "数量"], [[sw, cnt] for sw, cnt in high_sw.most_common(20)]))
        lines.append("")
        for sw in top_high_sw:
            rows = [r for r in stock_highs if (r.get("sw_l1") or "未映射") == sw]
            by_plate = defaultdict(list)
            for row in rows:
                by_plate[row["plate_display"]].append(row)
            lines.append(f"### {sw}：题材与个股")
            table_rows = []
            for plate, items in sorted(by_plate.items(), key=lambda kv: (-len(kv[1]), kv[0])):
                table_rows.append([plate, len(items), "、".join(i["stock_name"] for i in items[:10])])
            lines.append(_table(["题材", "个股数", "个股"], table_rows))
            lines.append("")
        lines.append(f"> **结论**：120日新高主要承载在 {_join_names(top_high_sw, 3)}；题材集中于 {high_plate_text}。")
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("## 8. 涨停题材")
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
        lines.append("## 9. 3板及以上个股")
        lines.append(_table(
            ["股票", "代码", "连板数", "首板日期", "题材", "涨幅", "晋级率"],
            [[r["stock_name"], r["stock_ts_code"], r["boards"], r["first_limit_date"], r["theme"], _pct(r["pct_chg"]), r["promotion_rate"]] for r in limit_advance],
        ))
        lines.append("")
        lines.append(f"> **结论**：3板及以上个股 {len(limit_advance)} 只，最高连板 {max([r['boards'] for r in limit_advance], default='-')} 板。")
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("## 10. 市场强度")
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
        lines.append("## 11. 近五日加权涨幅 Top10")
        lines.append(_table(
            ["股票", "代码", "5日涨幅", "成交额", "加权涨幅", "申万一级", "主要题材"],
            [[r["stock_name"], r["stock_ts_code"], _pct(r["gain5"]), _yi(r["amount_yi"]), _fmt(r["weighted"]), r["sw_l1"], r["sectors"]] for r in weighted],
        ))
        lines.append("")
        lines.append(f"> **结论**：近五日加权强股前列为 {top_weighted_text}，主要关联 {weighted_theme_text}。")
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("## 12. 数据覆盖检查")
        lines.append(_table(["表", "最新日期", "总行数", "目标日行数", "状态"], _coverage(con, td)))
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("## 13. 市场环境总评")
        lines.append(f"> {td} 市场性质为 **{nature}**，市场阶段为 **{today.get('market_stage') or '-'}**。成交额 {_yi(today.get('total_amount'))}，较昨日 {_pct(today.get('amount_vs_yesterday_pct'))}；前三行业占比 {_pct(today.get('top3_industry_ratio'))}。主线集中在 {market_mainline} 相关方向，强度状态为 **{today.get('strength_status') or '-'}**。")
        lines.append("")
        lines.append(f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        out_path.write_text("\n".join(lines), encoding="utf-8")
        return {"trade_date": str(td), "output_path": str(out_path), "chart_path": str(chart_file) if chart_file else None}
    finally:
        con.close()
