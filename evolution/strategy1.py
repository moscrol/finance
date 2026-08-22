"""策略一 · 无前视确定性生成器。

只读取 D0 当日三张事实表，绝不引用 D0 之后的任何列，因此：
- 无前视（no lookahead）：复盘当天即可生成，事后验证才用 fact_stock_daily 的未来收盘。
- 可复现（deterministic）：同参数 + 同库 → 完全相同的名单（排序按 weighted 降序、代码升序兜底）。

硬条件（全部 D0）：
  1. 个股主行业 ∈ 当日成交额前三申万一级行业（fact_market_daily.industry_1/2/3）
  2. 个股所属题材当日"双红"（口径见 market_feature_store/signals.py::DOUBLE_RED_SQL；本策略的阈值取自 params.json，与正典由一致性测试对齐）且该题材 sw_l1 ∈ 前三行业
  3. 行业内"开根加权" weighted = pct_chg * sqrt(amount) 进入前 1/quintile 分位
  4. 新高（high_status_label 非空）或 双红命中题材数 >= dr_hits_min
分层：ALL（满足 3 且 4）⊃ NEWHIGH（ALL 中新高）⊃ T1CORE6（NEWHIGH 中 weighted 前 t1core_size）。
"""
import math


def _norm(s):
    return (s or "").strip()


def generate_for_date(con, date, params):
    """生成某交易日的策略一结果。

    返回 dict（含 picks 与 counts），若当日无行情（fact_market_daily 无该日）返回 None。
    """
    s1 = params["strategy1"]
    dr = s1["double_red"]
    q = int(s1["quintile"])
    gate_min = int(s1["candidate_gate"]["dr_hits_min"])
    k = int(s1["t1core_size"])

    mrow = con.execute(
        "select industry_1, industry_2, industry_3 from fact_market_daily where trade_date=?",
        [date],
    ).fetchone()
    if not mrow:
        return None
    top = {_norm(x) for x in mrow if x}

    sec = con.execute(
        "select sector_ts_code, sw_l1 from fact_sector_daily "
        "where trade_date=? and pct_chg>? and diff_ratio>? and amount>?",
        [date, dr["pct_chg_min"], dr["diff_ratio_min"], dr["amount_min"]],
    ).fetchall()
    dr_sectors = {c for c, sw in sec if _norm(sw) in top}

    stocks = con.execute(
        "select stock_ts_code, stock_name, sw_l1, sw_industry, sector_ts_code, sector_name, "
        "pct_chg, amount, high_status_label from fact_sector_stock_daily "
        "where trade_date=? and pct_chg is not null and amount is not null",
        [date],
    ).fetchall()

    pool = {}
    for code, name, sw, ind, sec_code, sec_name, pct, amount, high in stocks:
        main = _norm(ind).split("-")[0] or _norm(sw)
        if main not in top or sec_code not in dr_sectors:
            continue
        w = (pct or 0) * math.sqrt(amount or 0)
        it = pool.setdefault(code, {
            "code": code, "name": name, "sw_l1": _norm(sw),
            "weighted": -1.0, "pct_chg": pct, "amount": amount,
            "high": "", "sectors": set(),
        })
        if w > it["weighted"]:
            it.update(weighted=w, high=_norm(high), pct_chg=pct, amount=amount, name=name)
        it["sectors"].add(sec_name)

    result = {
        "date": date,
        "params_version": params["version"],
        "top3_industries": sorted(top),
        "coverage": {
            "double_red_sectors_in_top3": len(dr_sectors),
            "stocks_scanned": len(stocks),
            "pool_size": len(pool),
        },
        "picks": [],
        "counts": {"ALL": 0, "NEWHIGH": 0, "T1CORE6": 0},
    }
    if not pool:
        return result

    vals = sorted((it["weighted"] for it in pool.values()), reverse=True)
    cut = vals[max(1, len(vals) // q) - 1]

    candidates = {
        c: it for c, it in pool.items()
        if it["weighted"] >= cut and (bool(it["high"]) or len(it["sectors"]) >= gate_min)
    }
    newhigh = {c: it for c, it in candidates.items() if it["high"]}
    ordered_nh = sorted(newhigh.items(), key=lambda kv: (-kv[1]["weighted"], kv[0]))
    t1core_codes = {c for c, _ in ordered_nh[:k]}

    def finalize(it, scope):
        return {
            "code": it["code"], "name": it["name"], "sw_l1": it["sw_l1"],
            "pct_chg": round(it["pct_chg"], 2), "amount": round(it["amount"], 2),
            "weighted": round(it["weighted"], 4), "high": it["high"],
            "dr_hits": len(it["sectors"]),
            "conditions": {
                "weighted_top_quintile": it["weighted"] >= cut,
                "is_new_high": bool(it["high"]),
                "dr_hits_ge_min": len(it["sectors"]) >= gate_min,
            },
            "scope": scope,
        }

    picks = []
    for c, it in sorted(candidates.items(), key=lambda kv: (-kv[1]["weighted"], kv[0])):
        scope = "T1CORE6" if c in t1core_codes else ("NEWHIGH" if c in newhigh else "ALL")
        picks.append(finalize(it, scope))

    result["picks"] = picks
    result["counts"] = {"ALL": len(candidates), "NEWHIGH": len(newhigh), "T1CORE6": len(t1core_codes)}
    return result


def payload_for_date(con, date, params):
    """多策略记录用：返回策略一子负载 {top3_industries, coverage, counts, picks}，无行情返回 None。"""
    rec = generate_for_date(con, date, params)
    if rec is None:
        return None
    return {
        "top3_industries": rec["top3_industries"],
        "coverage": rec["coverage"],
        "counts": rec["counts"],
        "picks": rec["picks"],
    }


_RANK = {"ALL": 0, "NEWHIGH": 1, "T1CORE6": 2}


def picks_in_scope(record, scope):
    """按口径过滤：T1CORE6 ⊂ NEWHIGH ⊂ ALL。record 可为完整记录或子负载（含 picks 即可）。"""
    want = _RANK[scope]
    return [p for p in record.get("picks", []) if _RANK[p["scope"]] >= want]
