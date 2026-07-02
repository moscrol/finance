#!/usr/bin/env python3
"""策略一矩阵机械初稿行生成（D0口径，供全量复盘收尾自动跑）。

用法:
    python3 scripts/generate_strategy1_mechanical_row.py --date YYYY-MM-DD [--dry-run]

口径（对齐 skills/strategy1-matrix 标准口径，机械可算部分）:
- 候选池: 成交前三申万一级行业内、行业开根加权(pct*sqrt(amount)) Top20、当日上涨
- 双红命中: 个股所属板块中满足 pct_chg>0 AND diff_ratio>10 AND amount>500 的个数
- 强确认: 当日新高（fact_stock_high_daily）或 涨停/连板（fact_limit_advance_daily / limit_status）
- 分层（机械近似）:
    T1  = 双红命中 且 行业加权前10 且 具备新高/多双红(>=3)/涨停之一
    T1- = 双红命中 且 行业加权前10，但无强确认
    T2  = 行业加权11~20 且 (双红命中 或 新高/涨停)
    OBS = 其余双红命中>=2的前排股（扩散验证用）

产出的行标注「机械初稿·待人工复核」，替换人工判断的是初稿不是结论；
人工复核仍走 skills/strategy1-matrix 流程（同日期行会被人工行覆盖）。
写入复用 skills/strategy1-matrix/scripts/update_matrix.py（HTML 转义 + upsert 单行）。
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "db/market_feature_store.duckdb"
UPDATER = ROOT / "skills/strategy1-matrix/scripts/update_matrix.py"
MATRIX = ROOT / "复盘/matrices/strategy1-priority-stock-matrix.html"


def fetch(date: str) -> dict:
    con = duckdb.connect()
    con.execute(f"ATTACH '{DB}' AS db (READ_ONLY)")

    top3 = [r[0] for r in con.execute(
        "SELECT sw_l1 FROM db.fact_sw_l1_daily WHERE trade_date=? "
        "AND sw_l1 IS NOT NULL ORDER BY amount DESC LIMIT 3", [date]).fetchall()]

    dr_sectors = con.execute(
        "SELECT sector_ts_code, sector_name FROM db.fact_sector_daily "
        "WHERE trade_date=? AND pct_chg>0 AND diff_ratio>10 AND amount>500", [date]).fetchall()
    dr_codes = [r[0] for r in dr_sectors]

    # 个股双红命中数 + 命中题材名
    dr_hits: dict[str, list[str]] = {}
    if dr_codes:
        rows = con.execute(
            "SELECT stock_ts_code, sector_name FROM db.fact_sector_stock_daily "
            f"WHERE trade_date=? AND sector_ts_code IN ({','.join('?' * len(dr_codes))})",
            [date, *dr_codes]).fetchall()
        for code, sec in rows:
            dr_hits.setdefault(code, []).append(sec)

    # 行业内开根加权排名（成交前三行业）
    ranked = con.execute("""
    SELECT sw, stock_ts_code, stock_name, pct_chg, amount, w_rank FROM (
      SELECT m.sw_industry sw, s.stock_ts_code, s.stock_name, s.pct_chg, s.amount,
        ROW_NUMBER() OVER (PARTITION BY m.sw_industry
          ORDER BY s.pct_chg*sqrt(GREATEST(s.amount,0)) DESC) w_rank
      FROM db.fact_stock_daily s
      JOIN (SELECT stock_ts_code, any_value(sw_industry) sw_industry
            FROM db.fact_sector_stock_daily
            WHERE trade_date=? AND sw_industry IS NOT NULL GROUP BY 1) m USING (stock_ts_code)
      WHERE s.trade_date=? AND s.pct_chg>0 AND s.amount IS NOT NULL)
    WHERE w_rank<=20 AND sw IN (SELECT sw_l1 FROM db.fact_sw_l1_daily
      WHERE trade_date=? ORDER BY amount DESC LIMIT 3)
    ORDER BY sw, w_rank""", [date, date, date]).fetchall()

    highs = {r[0]: r[1] for r in con.execute(
        "SELECT stock_ts_code, COALESCE(primary_high_label, primary_high_period) "
        "FROM db.fact_stock_high_daily WHERE trade_date=?", [date]).fetchall()}

    limits = {r[0]: r[1] for r in con.execute(
        "SELECT stock_ts_code, boards FROM db.fact_limit_advance_daily WHERE trade_date=?",
        [date]).fetchall()}

    adv = con.execute(
        "SELECT advancers, sh_index_pct_chg, market_stage FROM db.fact_market_daily "
        "WHERE trade_date=?", [date]).fetchone() or (None, None, None)

    con.close()
    return {
        "top3": top3, "n_dr": len(dr_sectors), "dr_hits": dr_hits,
        "ranked": ranked, "highs": highs, "limits": limits, "market": adv,
    }


def build_row(date: str, data: dict) -> dict:
    t1, t2, obs = [], [], []
    for sw, code, name, pct, amount, rank in data["ranked"]:
        hits = data["dr_hits"].get(code, [])
        high = data["highs"].get(code)
        boards = data["limits"].get(code)
        confirms = []
        if high:
            confirms.append(f"新高{high}")
        if boards:
            confirms.append(f"{boards}连板")
        if len(hits) >= 3:
            confirms.append(f"双红命中{len(hits)}")
        facts = (
            f"机械口径：{sw}加权第{rank}，涨{pct:+.1f}%，"
            f"双红命中{len(hits)}" + (f"（{'、'.join(hits[:3])}）" if hits else "")
            + (f"，{'，'.join(confirms)}" if confirms else "")
        )
        item = {"name": name, "code": code, "reason": facts}
        if hits and rank <= 10 and confirms:
            item["tag"] = "T1"
            t1.append(item)
        elif hits and rank <= 10:
            item["tag"] = "T1-"
            t1.append(item)
        elif rank <= 20 and (hits or confirms):
            item["tag"] = "T2"
            t2.append(item)
        elif len(hits) >= 2:
            item["tag"] = "OBS"
            obs.append(item)
    adv, shp, stage = data["market"]
    state = (
        f"机械初稿·待人工复核。容量前三 {'/'.join(data['top3']) or '-'}，"
        f"双红题材 {data['n_dr']} 个，涨家数 {adv if adv is not None else '-'}，"
        f"上证 {f'{shp:+.2f}%' if shp is not None else '-'}"
        + (f"，阶段 {stage}" if stage else "") + "。"
    )
    verify = (
        "机械口径初稿（D0）：候选=容量前三行业×行业开根加权Top20×当日上涨；"
        "分层仅按双红命中/加权排名/新高/连板机械判定，"
        "人工按 skills/strategy1-matrix 复核后覆盖本行。"
    )
    return {
        "date": date, "state": state,
        "t1": t1[:4], "t2": t2[:5], "obs": obs[:4],
        "verify": verify,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", required=True)
    ap.add_argument("--matrix", default=str(MATRIX))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    matrix_path = Path(args.matrix)
    if matrix_path.exists():
        m = re.search(
            rf'<tr[^>]*>\s*<td class="date">{re.escape(args.date)}</td>.*?</tr>',
            matrix_path.read_text(encoding="utf-8"), re.S)
        if m and "机械初稿" not in m.group(0):
            print(f"[strategy1] {args.date} 已有人工行，不覆盖")
            return 0

    data = fetch(args.date)
    if not data["ranked"]:
        print(f"[strategy1] {args.date} 无候选（fact_stock_daily/fact_sw_l1_daily 缺数据？），跳过")
        return 1
    row = build_row(args.date, data)
    row_path = Path(f"/tmp/strategy1-row-{args.date}.json")
    row_path.write_text(json.dumps(row, ensure_ascii=False, indent=1), encoding="utf-8")

    cmd = [sys.executable, str(UPDATER), "--row-json", str(row_path), "--matrix", args.matrix]
    if args.dry_run:
        cmd.append("--dry-run")
    return subprocess.call(cmd)


if __name__ == "__main__":
    raise SystemExit(main())
