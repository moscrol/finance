import csv
import math
from collections import defaultdict

from market_feature_store.db import connect

START = "2026-04-08"
END = "2026-06-05"
LAST_CLOSE_DATE = "2026-06-04"
TRADES_OUT = "research/market-hypothesis/strategy1-theme-cycles-0408-0605-trades.csv"
TRANS_OUT = "research/market-hypothesis/strategy1-theme-cycles-0408-0605-transitions.csv"
SUMMARY_OUT = "research/market-hypothesis/strategy1-theme-cycles-0408-0605-summary.csv"

HIGH_RANK = {"历史新高": 7, "3年新高": 6, "2年新高": 5, "1年新高": 4, "120日新高": 3, "60日新高": 2, "20日新高": 1, "": 0, None: 0}


def best_high(a, b):
    return a if HIGH_RANK.get(a, 0) >= HIGH_RANK.get(b, 0) else b


def pct_ret(a, b):
    if not a or not b:
        return ""
    return round((b / a - 1) * 100, 2)


def avg(xs):
    vals = [x for x in xs if x != ""]
    if not vals:
        return ""
    return round(sum(vals) / len(vals), 2)


con = connect(read_only=True)
trade_dates = [str(x[0]) for x in con.execute("""
select trade_date from fact_market_daily
where trade_date between ? and ?
order by trade_date
""", [START, END]).fetchall()]
next_date = {d: trade_dates[i + 1] for i, d in enumerate(trade_dates[:-1])}
market_rows = con.execute("""
select cast(trade_date as varchar), industry_1, industry_2, industry_3
from fact_market_daily
where trade_date between ? and ?
""", [START, END]).fetchall()
market_top3 = {d: {x.strip() for x in [i1, i2, i3] if x} for d, i1, i2, i3 in market_rows}
market_top3_names = {d: "/".join([x for x in [i1, i2, i3] if x]) for d, i1, i2, i3 in market_rows}
sector_rows = con.execute("""
select cast(trade_date as varchar), sector_ts_code, sector_name, sw_l1, pct_chg, diff_ratio, amount
from fact_sector_daily
where trade_date between ? and ?
  and pct_chg > 0 and diff_ratio > 10 and amount > 500
order by trade_date, sw_l1, amount desc
""", [START, END]).fetchall()
stock_rows = con.execute("""
select cast(trade_date as varchar), stock_ts_code, stock_name, sw_l1, sw_industry, sector_ts_code,
       sector_name, pct_chg, amount, high_status_label
from fact_sector_stock_daily
where trade_date between ? and ? and pct_chg is not null and amount is not null
""", [START, END]).fetchall()
stock_daily_rows = con.execute("""
select cast(trade_date as varchar), stock_ts_code, pct_chg, close
from fact_stock_daily
where trade_date between ? and ?
""", [START, LAST_CLOSE_DATE]).fetchall()
sw_rows = con.execute("""
select cast(trade_date as varchar), sw_l1, pct_chg
from fact_sw_l1_daily
where trade_date between ? and ?
""", [START, END]).fetchall()
con.close()

sector_by_day = defaultdict(dict)
sector_dates = defaultdict(list)
sector_info = {}
for day, sec_code, sec_name, sw_l1, pct, diff, amount in sector_rows:
    sw = (sw_l1 or "").strip()
    if sw not in market_top3.get(day, set()):
        continue
    info = {"sector_ts_code": sec_code, "sector_name": sec_name, "sw_l1": sw, "pct_chg": pct, "diff_ratio": diff, "amount": amount}
    sector_by_day[day][sec_code] = info
    sector_dates[sec_code].append(day)
    sector_info[sec_code] = {"sector_name": sec_name, "sw_l1": sw}

stocks_by_day = defaultdict(list)
stock_pct_fallback = {}
stock_name_latest = {}
for row in stock_rows:
    day, code, name, sw, ind, sec_code, sec_name, pct, amount, high = row
    stocks_by_day[day].append(row)
    stock_name_latest[code] = name
    old = stock_pct_fallback.get((day, code))
    if old is None or abs(pct or 0) > abs(old):
        stock_pct_fallback[(day, code)] = pct

stock_day = {(d, c): {"pct": pct, "close": close} for d, c, pct, close in stock_daily_rows}
sw_day = {(d, sw): pct for d, sw, pct in sw_rows}


def get_pct(day, code):
    rec = stock_day.get((day, code))
    if rec and rec.get("pct") is not None:
        return rec["pct"]
    return stock_pct_fallback.get((day, code))


def get_close(day, code):
    rec = stock_day.get((day, code))
    if rec and rec.get("close"):
        return rec["close"]
    if day == END:
        base = stock_day.get((LAST_CLOSE_DATE, code), {}).get("close")
        pct = get_pct(END, code)
        if base and pct is not None:
            return base * (1 + pct / 100)
    return None


def build_core(day):
    div = next_date.get(day)
    if not div:
        return {}, "no_next_day"
    top = market_top3.get(day, set())
    dr = {code: info for code, info in sector_by_day.get(day, {}).items() if info["sw_l1"] in top}
    if not dr:
        return {}, "no_double_red"
    pool = {}
    for _, code, name, sw, ind, sec_code, sec_name, pct, amount, high in stocks_by_day.get(day, []):
        main = ((ind or "").split("-")[0] or sw or "").strip()
        if main not in top or sec_code not in dr:
            continue
        weighted = (pct or 0) * math.sqrt(amount or 0)
        item = pool.setdefault(code, {
            "code": code,
            "name": name,
            "sw_l1": main,
            "pct_event": pct,
            "amount_event": amount,
            "weighted": -1,
            "high_event": "",
            "sector_codes": set(),
            "sector_names": set(),
        })
        if weighted > item["weighted"]:
            item.update({"pct_event": pct, "amount_event": amount, "weighted": weighted})
        item["high_event"] = best_high(item["high_event"], high or "")
        item["sector_codes"].add(sec_code)
        item["sector_names"].add(sec_name)
    if not pool:
        return {}, "empty_pool"
    vals = sorted([x["weighted"] for x in pool.values()], reverse=True)
    cut = vals[max(1, len(vals) // 5) - 1]
    by_sector = defaultdict(dict)
    for item in pool.values():
        sp = get_pct(div, item["code"])
        ip = sw_day.get((div, item["sw_l1"]))
        if sp is None or ip is None:
            path = "unknown"
            rel = ""
        elif sp >= 0 and sp >= ip:
            path = "抗住且相对强"
            rel = sp - ip
        elif sp < 0 and sp >= ip:
            path = "补跌但相对强"
            rel = sp - ip
        elif sp >= 0 and sp < ip:
            path = "上涨但弱于行业"
            rel = sp - ip
        else:
            path = "补跌且弱于行业"
            rel = sp - ip
        weighted_top20 = item["weighted"] >= cut
        high_or_dr3 = bool(item["high_event"]) or len(item["sector_codes"]) >= 3
        rel_strong = path in {"抗住且相对强", "补跌但相对强"}
        if not (weighted_top20 and high_or_dr3 and rel_strong):
            continue
        enriched = dict(item)
        enriched.update({
            "confirm_date": div,
            "pct_confirm": sp,
            "rel_confirm": rel,
            "confirm_path": path,
            "double_red_hits": len(item["sector_codes"]),
            "all_sector_names": "、".join(sorted(item["sector_names"])),
            "reason": "+".join(["加权Top20", "新高" if item["high_event"] else "双红>=3", path]),
        })
        for sec_code in item["sector_codes"]:
            by_sector[sec_code][item["code"]] = enriched
    return by_sector, "ok"

core_cache = {}
core_status = {}
for day in trade_dates:
    cores, status = build_core(day)
    core_cache[day] = cores
    core_status[day] = status

trade_rows = []
transition_rows = []
summary = []
for sec_code, ds in sorted(sector_dates.items(), key=lambda kv: (sector_info[kv[0]]["sw_l1"], sector_info[kv[0]]["sector_name"])):
    dates = sorted(set(ds))
    info = sector_info[sec_code]
    if len(dates) < 2:
        continue
    appeared = set()
    for i in range(len(dates) - 1):
        start_day = dates[i]
        reflow_day = dates[i + 1]
        confirm_day = next_date.get(start_day, "")
        start_core = core_cache.get(start_day, {}).get(sec_code, {})
        reflow_core = core_cache.get(reflow_day, {}).get(sec_code, {})
        reflow_status = core_status.get(reflow_day, "")
        prev_codes = set(start_core)
        cur_codes = set(reflow_core)
        continued = prev_codes & cur_codes
        new_core = cur_codes - appeared - prev_codes
        rotated_in = cur_codes - prev_codes
        dropped = prev_codes - cur_codes
        start_rets = []
        confirm_rets = []
        for code, item in start_core.items():
            start_close = get_close(start_day, code)
            confirm_close = get_close(confirm_day, code) if confirm_day else None
            sell_close = get_close(reflow_day, code)
            ret_start = pct_ret(start_close, sell_close)
            ret_confirm = pct_ret(confirm_close, sell_close)
            start_rets.append(ret_start)
            confirm_rets.append(ret_confirm)
            if code in continued:
                role = "延续核心"
            elif reflow_status != "ok":
                role = "回流日无法确认新核心"
            else:
                role = "兑现掉队"
            trade_rows.append({
                "sector_ts_code": sec_code,
                "sector_name": info["sector_name"],
                "sw_l1": info["sw_l1"],
                "cycle_no": i + 1,
                "cycle_phase": "周期首发" if i == 0 else "后续回流",
                "start_date": start_day,
                "confirm_date": confirm_day,
                "reflow_date": reflow_day,
                "top3_industries_start": market_top3_names.get(start_day, ""),
                "code": code,
                "name": item["name"],
                "role_at_reflow": role,
                "pct_event": round(item["pct_event"] or 0, 2),
                "amount_event": round(item["amount_event"] or 0, 2),
                "weighted_event": round(item["weighted"], 2),
                "high_event": item["high_event"],
                "double_red_hits": item["double_red_hits"],
                "confirm_path": item["confirm_path"],
                "rel_confirm": "" if item["rel_confirm"] == "" else round(item["rel_confirm"], 2),
                "buy_start_to_reflow_pct": ret_start,
                "buy_confirm_to_reflow_pct": ret_confirm,
                "sell_price_estimated": "1" if reflow_day == END else "0",
                "selection_reason": item["reason"],
                "all_event_sectors": item["all_sector_names"][:200],
            })
        transition_rows.append({
            "sector_ts_code": sec_code,
            "sector_name": info["sector_name"],
            "sw_l1": info["sw_l1"],
            "cycle_no": i + 1,
            "start_date": start_day,
            "confirm_date": confirm_day,
            "reflow_date": reflow_day,
            "start_core_n": len(prev_codes),
            "reflow_core_n": "" if reflow_status != "ok" else len(cur_codes),
            "continued_n": "" if reflow_status != "ok" else len(continued),
            "new_core_n": "" if reflow_status != "ok" else len(new_core),
            "rotated_in_n": "" if reflow_status != "ok" else len(rotated_in),
            "dropped_n": "" if reflow_status != "ok" else len(dropped),
            "avg_buy_start_to_reflow_pct": avg(start_rets),
            "avg_buy_confirm_to_reflow_pct": avg(confirm_rets),
            "continued_names": "、".join([start_core[c]["name"] for c in sorted(continued)])[:200],
            "new_core_names": "、".join([reflow_core[c]["name"] for c in sorted(new_core)])[:200],
            "dropped_names": "、".join([start_core[c]["name"] for c in sorted(dropped)])[:200],
            "reflow_core_status": reflow_status,
        })
        appeared.update(prev_codes)
    appeared.update(core_cache.get(dates[-1], {}).get(sec_code, {}).keys())

with open(TRADES_OUT, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=list(trade_rows[0].keys()))
    writer.writeheader()
    writer.writerows(trade_rows)
with open(TRANS_OUT, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=list(transition_rows[0].keys()))
    writer.writeheader()
    writer.writerows(transition_rows)

valid_start = [r["buy_start_to_reflow_pct"] for r in trade_rows if r["buy_start_to_reflow_pct"] != ""]
valid_confirm = [r["buy_confirm_to_reflow_pct"] for r in trade_rows if r["buy_confirm_to_reflow_pct"] != ""]
valid_trans = [r for r in transition_rows if r["reflow_core_status"] == "ok"]
summary.append({"metric": "cycle_trade_rows", "value": len(trade_rows)})
summary.append({"metric": "theme_transitions", "value": len(transition_rows)})
summary.append({"metric": "transitions_with_reflow_core", "value": len(valid_trans)})
summary.append({"metric": "avg_buy_start_to_reflow_pct", "value": avg(valid_start)})
summary.append({"metric": "avg_buy_confirm_to_reflow_pct", "value": avg(valid_confirm)})
summary.append({"metric": "positive_buy_start_pct", "value": round(sum(x > 0 for x in valid_start) / len(valid_start) * 100, 2) if valid_start else ""})
summary.append({"metric": "positive_buy_confirm_pct", "value": round(sum(x > 0 for x in valid_confirm) / len(valid_confirm) * 100, 2) if valid_confirm else ""})
summary.append({"metric": "transitions_with_new_core_pct", "value": round(sum(int(r["new_core_n"] or 0) > 0 for r in valid_trans) / len(valid_trans) * 100, 2) if valid_trans else ""})
summary.append({"metric": "transitions_with_continued_core_pct", "value": round(sum(int(r["continued_n"] or 0) > 0 for r in valid_trans) / len(valid_trans) * 100, 2) if valid_trans else ""})
summary.append({"metric": "transitions_with_dropped_core_pct", "value": round(sum(int(r["dropped_n"] or 0) > 0 for r in valid_trans) / len(valid_trans) * 100, 2) if valid_trans else ""})
with open(SUMMARY_OUT, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=["metric", "value"])
    writer.writeheader()
    writer.writerows(summary)

print(TRADES_OUT, len(trade_rows))
print(TRANS_OUT, len(transition_rows))
for row in summary:
    print(row)
print("top trades")
for r in sorted([x for x in trade_rows if x["buy_start_to_reflow_pct"] != ""], key=lambda x: -x["buy_start_to_reflow_pct"])[:30]:
    print(r["sector_name"], r["start_date"], "->", r["reflow_date"], r["name"], r["code"], r["role_at_reflow"], r["buy_start_to_reflow_pct"], r["buy_confirm_to_reflow_pct"], r["selection_reason"])
