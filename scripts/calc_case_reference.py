#!/usr/bin/env python3
"""工单 04 · 冻结 6 道计算题的输入与独立参照（不 import 本仓任何模块）。

为什么独立：验收比的是「Agent 从自然语言到真实计算」的结果对不对，参照如果也走 Agent 那条
取数 / 计算链，链上的错会两边一起错、比对永远通过。这里只用标准库直接读东财 F10 原始行
（元），自己换算成亿、自己做减法与比值——与 Agent 链共享的只有数据源本身。

用法::

    python3 scripts/calc_case_reference.py --out docs/superpowers/plans/2026-09-09-capability-upgrade/progress/04-cases.json

产出 JSON：每道题的自然语言题干（Workbench 输入）、追问（改假设 / 修订数据）、必须命中的数值
（带容差）、以及计算所用的原始输入快照与抓取时间。容差 0.02 亿 / 0.05 个百分点：Agent 链把每个
累计值先四舍五入到两位小数（亿）再做减法，与直接从元算会差一个尾数。
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

F10_URL = "https://datacenter.eastmoney.com/securities/api/data/v1/get"
COMPANIES = {
    "600519.SH": "贵州茅台",
    "000858.SZ": "五粮液",
    "000568.SZ": "泸州老窖",
}
ABS_TOL_YI = 0.02
ABS_TOL_PCT = 0.05
QUARTER = {"03-31": 1, "06-30": 2, "09-30": 3, "12-31": 4}


def fetch_rows(secucode: str, page_size: int = 10) -> list[dict]:
    params = {
        "reportName": "RPT_F10_FINANCE_MAINFINADATA",
        "columns": "ALL",
        "filter": f'(SECUCODE="{secucode}")',
        "pageSize": str(page_size),
        "sortColumns": "REPORT_DATE",
        "sortTypes": "-1",
        "source": "HSF10",
        "client": "PC",
    }
    request = urllib.request.Request(
        f"{F10_URL}?{urllib.parse.urlencode(params)}",
        headers={"User-Agent": "Mozilla/5.0", "Referer": "https://emweb.securities.eastmoney.com/"},
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if payload.get("code") != 0:
        raise SystemExit(f"F10 code={payload.get('code')} for {secucode}")
    return list(((payload.get("result") or {}).get("data")) or [])


def yi(value: object) -> float | None:
    if not isinstance(value, (int, float)):
        return None
    return round(float(value) / 1e8, 2)


def pct(value: object) -> float | None:
    if not isinstance(value, (int, float)):
        return None
    return round(float(value), 2)


def period_label(report_date: str) -> str:
    return f"{report_date[:4]}Q{QUARTER[report_date[5:10]]}"


def snapshot(rows: list[dict]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for row in rows:
        report_date = str(row.get("REPORT_DATE") or "")[:10]
        if report_date[5:10] not in QUARTER:
            continue
        out[report_date] = {
            "period": period_label(report_date),
            "notice_date": str(row.get("NOTICE_DATE") or "")[:10] or None,
            "revenue_cum_yi": yi(row.get("TOTALOPERATEREVE")),
            "revenue_yoy_pct": pct(row.get("TOTALOPERATEREVETZ")),
            "net_profit_cum_yi": yi(row.get("PARENTNETPROFIT")),
            "net_profit_yoy_pct": pct(row.get("PARENTNETPROFITTZ")),
            "gross_margin_pct": pct(row.get("XSMLL")),
            "net_margin_pct": pct(row.get("XSJLL")),
            "ocf_cum_yi": yi(row.get("NETCASH_OPERATE_PK")),
            "raw": {
                key: row.get(key)
                for key in (
                    "TOTALOPERATEREVE",
                    "PARENTNETPROFIT",
                    "NETCASH_OPERATE_PK",
                    "TOTALOPERATEREVETZ",
                    "PARENTNETPROFITTZ",
                    "XSMLL",
                    "XSJLL",
                )
            },
        }
    return out


def single_quarter(snap: dict[str, dict], metric: str, periods: list[str]) -> dict[str, float | None]:
    out: dict[str, float | None] = {}
    for report_date in periods:
        row = snap.get(report_date)
        if row is None or row[metric] is None:
            out[period_label(report_date)] = None
            continue
        quarter = QUARTER[report_date[5:10]]
        if quarter == 1:
            out[row["period"]] = row[metric]
            continue
        prior_date = f"{report_date[:4]}-{ {2: '03-31', 3: '06-30', 4: '09-30'}[quarter] }"
        prior = snap.get(prior_date)
        out[row["period"]] = (
            None if prior is None or prior[metric] is None else round(row[metric] - prior[metric], 2)
        )
    return out


def must(value: float | None, *, tol: float, label: str, unit: str = "亿元") -> dict:
    return {"label": label, "value": value, "tol": tol, "unit": unit}


def build_cases(snaps: dict[str, dict[str, dict]]) -> list[dict]:
    mt = snaps["600519.SH"]
    latest_dates = sorted(mt)[-6:]
    q_periods = [d for d in sorted(mt) if d >= "2025-03-31"]
    sq_revenue = single_quarter(mt, "revenue_cum_yi", q_periods)
    sq_profit = single_quarter(mt, "net_profit_cum_yi", q_periods)
    fy2025 = mt["2025-12-31"]["revenue_cum_yi"]
    q1_2026 = mt["2026-03-31"]["revenue_cum_yi"]

    cases: list[dict] = []
    # 1 累计转单季
    cases.append(
        {
            "id": "01_single_quarter",
            "title": "累计转单季（贵州茅台）",
            "prompt": (
                "贵州茅台从 2025 年一季报到 2026 年中报，把营业总收入和归母净利润从累计值还原成单季值，"
                "列一张表给我，并说明每个单季是怎么算出来的。"
            ),
            "must_have": [
                must(sq_revenue[p], tol=ABS_TOL_YI, label=f"{p} 单季营收") for p in sq_revenue if sq_revenue[p] is not None
            ]
            + [must(sq_profit[p], tol=ABS_TOL_YI, label=f"{p} 单季归母净利") for p in sq_profit if sq_profit[p] is not None],
            "headline": [must(sq_revenue["2026Q2"], tol=ABS_TOL_YI, label="2026Q2 单季营收")],
            "follow_up": {
                "id": "06_revision_recompute",
                "title": "数据修正后重算（2026 中报营收修订）",
                "prompt": "假设 2026 年中报的营业总收入修订为 925.00 亿元（原 922.78 亿元），其余不变，只重算 2026Q2 的单季营收，并告诉我改了哪些格。",
                "must_have": [must(round(925.00 - q1_2026, 2), tol=ABS_TOL_YI, label="修订后 2026Q2 单季营收")],
                "unchanged": [must(sq_revenue["2026Q1"], tol=ABS_TOL_YI, label="2026Q1 单季营收（不应变）")],
            },
        }
    )
    # 2 经营现金流与利润对照
    ratios = {}
    for report_date in latest_dates:
        row = mt[report_date]
        ratios[row["period"]] = (
            None
            if not row["ocf_cum_yi"] or not row["net_profit_cum_yi"]
            else round(row["ocf_cum_yi"] / row["net_profit_cum_yi"], 2)
        )
    cases.append(
        {
            "id": "02_ocf_vs_profit",
            "title": "经营现金流与利润对照（贵州茅台）",
            "prompt": (
                "贵州茅台最近 6 个报告期，把经营活动现金流净额和归母净利润（都用累计口径）放在一起对照，"
                "算出每期「经营现金流 ÷ 归母净利润」的比值，指出哪几期低于 1。"
            ),
            "must_have": [must(v, tol=0.011, label=f"{p} 现金流/净利润比", unit="倍") for p, v in ratios.items() if v is not None],
            "headline": [must(ratios[mt[latest_dates[-1]]["period"]], tol=0.011, label="最新期比值", unit="倍")],
            "below_one": [p for p, v in ratios.items() if v is not None and v < 1],
        }
    )
    # 3 多公司同口径比较
    peers = []
    for code, name in COMPANIES.items():
        row = snaps[code].get("2026-06-30")
        if row is None:
            continue
        peers.append({"code": code, "name": name, **{k: row[k] for k in ("revenue_cum_yi", "net_profit_cum_yi", "revenue_yoy_pct", "net_profit_yoy_pct", "gross_margin_pct", "net_margin_pct")}})
    ranking = [p["name"] for p in sorted(peers, key=lambda p: (p["revenue_yoy_pct"] is None, -(p["revenue_yoy_pct"] or 0)))]
    cases.append(
        {
            "id": "03_peer_compare",
            "title": "多公司同口径比较（2026 中报）",
            "prompt": (
                "对比贵州茅台、五粮液、泸州老窖 2026 年中报：营业总收入、归母净利润、营收同比、归母净利同比、"
                "销售毛利率、销售净利率，同一口径放进一张表，并按营收同比从高到低排序。"
            ),
            "must_have": [
                must(p["revenue_cum_yi"], tol=ABS_TOL_YI, label=f"{p['name']} 2026H1 营收")
                for p in peers
            ]
            + [must(p["net_profit_cum_yi"], tol=ABS_TOL_YI, label=f"{p['name']} 2026H1 归母净利") for p in peers]
            + [must(p["gross_margin_pct"], tol=ABS_TOL_PCT, label=f"{p['name']} 2026H1 毛利率", unit="%") for p in peers],
            "headline": [must(p["revenue_yoy_pct"], tol=ABS_TOL_PCT, label=f"{p['name']} 营收同比", unit="%") for p in peers],
            "ranking_by_revenue_yoy": ranking,
        }
    )
    # 4 收入情景（+ 改假设追问）
    scen = {"悲观": -3.0, "中性": 0.0, "乐观": 5.0}
    scen_values = {k: round(fy2025 * (1 + g / 100), 2) for k, g in scen.items()}
    cases.append(
        {
            "id": "04_revenue_scenarios",
            "title": "收入情景（贵州茅台 2026 全年）",
            "prompt": (
                "以贵州茅台 2025 年报的营业总收入为基期，做 2026 年全年收入情景：悲观 -3%、中性 0%、乐观 +5%，"
                "给出三种情景下的收入（亿元）和较基期的变动额，列成表。"
            ),
            "must_have": [must(v, tol=ABS_TOL_YI, label=f"{k}情景收入") for k, v in scen_values.items()]
            + [must(fy2025, tol=ABS_TOL_YI, label="基期 2025 年报营收")],
            "headline": [must(scen_values["乐观"], tol=ABS_TOL_YI, label="乐观情景收入")],
            "follow_up": {
                "id": "04b_scenario_change",
                "title": "改假设重算（乐观改 +8%）",
                "prompt": "把乐观情景改成 +8%，其余两个情景不变，重算这张情景表。",
                "must_have": [must(round(fy2025 * 1.08, 2), tol=ABS_TOL_YI, label="乐观 +8% 情景收入")],
                "unchanged": [must(scen_values["悲观"], tol=ABS_TOL_YI, label="悲观情景收入（不应变）")],
            },
        }
    )
    # 5 利润率敏感性（+ 加一档追问）
    growths = [-3.0, 0.0, 3.0]
    margins = [48.0, 50.0, 52.0]
    grid = {f"g{g:+.0f}_m{m:.0f}": round(fy2025 * (1 + g / 100) * m / 100, 2) for g in growths for m in margins}
    cases.append(
        {
            "id": "05_margin_sensitivity",
            "title": "利润率敏感性（贵州茅台）",
            "prompt": (
                "以贵州茅台 2025 年报营业总收入为基数，做一张归母净利润敏感性表：营收增速取 -3%、0%、+3%，"
                "销售净利率取 48%、50%、52%，表格每一格是对应的归母净利润（亿元）。"
            ),
            "must_have": [must(v, tol=ABS_TOL_YI, label=f"敏感性 {k}") for k, v in grid.items()],
            "headline": [must(grid["g+0_m50"], tol=ABS_TOL_YI, label="增速 0% × 净利率 50%")],
            "follow_up": {
                "id": "05b_add_margin_row",
                "title": "改假设重算（净利率加一档 54%）",
                "prompt": "净利率再加一档 54%，其余不变，重算敏感性表。",
                "must_have": [must(round(fy2025 * (1 + g / 100) * 0.54, 2), tol=ABS_TOL_YI, label=f"增速 {g:+.0f}% × 净利率 54%") for g in growths],
                "unchanged": [must(grid["g+0_m50"], tol=ABS_TOL_YI, label="增速 0% × 净利率 50%（不应变）")],
            },
        }
    )
    return cases


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", required=True, help="输出 JSON 路径")
    args = parser.parse_args(argv)

    fetched_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    snaps = {code: snapshot(fetch_rows(code)) for code in COMPANIES}
    for code, snap in snaps.items():
        if "2026-06-30" not in snap or "2025-12-31" not in snap:
            print(f"warning: {code} lacks 2026-06-30 or 2025-12-31 rows", file=sys.stderr)
    document = {
        "schema": "calc-cases/v1",
        "fetched_at": fetched_at,
        "source": "东财 F10 RPT_F10_FINANCE_MAINFINADATA（元→亿 四舍五入两位，与 Agent 链同口径）",
        "tolerance": {"abs_yi": ABS_TOL_YI, "abs_pct": ABS_TOL_PCT},
        "companies": COMPANIES,
        "inputs": {code: {date: {k: v for k, v in row.items() if k != "raw"} for date, row in snap.items()} for code, snap in snaps.items()},
        "raw_inputs": {code: {date: row["raw"] for date, row in snap.items()} for code, snap in snaps.items()},
        "cases": build_cases(snaps),
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {out} · {len(document['cases'])} cases · fetched_at={fetched_at}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
