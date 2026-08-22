"""批量机械回填策略3 Touch UP矩阵的空日期行（D0口径）。

用法:
    python3 scripts/backfill_strategy3_touch_matrix.py [--append-missing]

--append-missing: 对 DuckDB 已有数据但矩阵 HTML 尚无行的日期，按日期序追加新机械行
（全量复盘收尾自动跑时用；默认只替换已有的"待回填"/机械行，不新增）。

口径（与策略三文档/回测一致）:
- 核心池: 严格近15个交易日内进过单日加权涨幅(pct*sqrt(amount)) Top20
- UP = MA26 + 0.764*STDDEV_POP26（与人工行6.5/6.8口径对账一致）, 偏离度 dev = 100*(close/UP-1)
- S3-L-A 刚Touch首买: 当日 dev ∈ [-3,+3] 且前一日 dev > +3
- 提前观察: dev ∈ (+3,+5]
- S3-L-B 动态窗口: 1~10个交易日前发生过touch，当前 dev ∈ [-3,+5]
- SELL: 窗口内touch后从touch收盘涨幅 ≥ +5%
- RISK: 窗口内touch后当前 dev < -1.5（深破，2026-06-10新规则）
- 环境: E1=涨家数<1500且上证<-0.5%；E2=涨家数<2400；其余E3
仅替换矩阵中"待回填"的行，已人工填写的行不动；机械行打"机械回填"标签。
"""
from __future__ import annotations

import argparse
import html as h
import re
from pathlib import Path

import duckdb
from market_feature_store.signals import DOUBLE_RED_SQL

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "db/market_feature_store.duckdb"
MATRIX = ROOT / "复盘/matrices/strategy3-touch-up-rebound-matrix.html"


def clean(name):
    return (name or "").replace("\x00", "").strip()


def fetch():
    con = duckdb.connect()
    con.execute(f"ATTACH '{DB}' AS db (READ_ONLY)")

    con.execute("""
    CREATE TEMP TABLE w20 AS
    SELECT trade_date, stock_ts_code, stock_name, w_rank FROM (
      SELECT trade_date, stock_ts_code, stock_name,
        ROW_NUMBER() OVER (PARTITION BY trade_date ORDER BY pct_chg*sqrt(GREATEST(amount,0)) DESC) w_rank
      FROM db.fact_stock_daily WHERE pct_chg>0)
    WHERE w_rank<=20 AND trade_date >= DATE '2026-02-15'""")

    con.execute("""
    CREATE TEMP TABLE tdates AS
    SELECT trade_date, ROW_NUMBER() OVER (ORDER BY trade_date) rn
    FROM (SELECT DISTINCT trade_date FROM db.fact_market_daily)""")

    con.execute("""
    CREATE TEMP TABLE dev AS
    SELECT trade_date, stock_ts_code, stock_name, close, pct_chg,
      100.0*(close/(ma26+0.764*sd26)-1) dev,
      LAG(100.0*(close/(ma26+0.764*sd26)-1)) OVER (PARTITION BY stock_ts_code ORDER BY trade_date) pdev
    FROM (
      SELECT trade_date, stock_ts_code, stock_name, close, pct_chg,
        AVG(close) OVER w26 ma26, STDDEV_POP(close) OVER w26 sd26
      FROM db.fact_stock_daily
      WHERE stock_ts_code IN (SELECT DISTINCT stock_ts_code FROM w20)
      WINDOW w26 AS (PARTITION BY stock_ts_code ORDER BY trade_date ROWS BETWEEN 25 PRECEDING AND CURRENT ROW))
    WHERE trade_date >= DATE '2026-03-01'""")

    con.execute("""
    CREATE TEMP TABLE pool AS
    SELECT d.trade_date, d.stock_ts_code,
      min(w.w_rank) best_rank, max(w.trade_date) last_w20
    FROM dev d
    JOIN tdates td ON td.trade_date=d.trade_date
    JOIN tdates tw ON tw.rn BETWEEN td.rn-15 AND td.rn-1
    JOIN w20 w ON w.stock_ts_code=d.stock_ts_code AND w.trade_date=tw.trade_date
    GROUP BY 1,2""")

    con.execute("""
    CREATE TEMP TABLE touch AS
    SELECT d.trade_date, d.stock_ts_code, d.close touch_close
    FROM dev d JOIN pool p USING (trade_date, stock_ts_code)
    WHERE d.dev BETWEEN -3 AND 3 AND d.pdev > 3""")

    rows = con.execute("""
    SELECT d.trade_date, d.stock_ts_code, d.stock_name, d.close, d.pct_chg,
      round(d.dev,2), round(d.pdev,2), p.best_rank, p.last_w20,
      t.trade_date AS touch_date, t.touch_close
    FROM dev d
    JOIN pool p USING (trade_date, stock_ts_code)
    LEFT JOIN (
      SELECT td.trade_date cur_date, t.stock_ts_code, max_by(t.trade_date, t.trade_date) trade_date,
        max_by(t.touch_close, t.trade_date) touch_close
      FROM tdates td
      JOIN tdates tw ON tw.rn BETWEEN td.rn-10 AND td.rn-1
      JOIN touch t ON t.trade_date=tw.trade_date
      GROUP BY 1,2) t ON t.cur_date=d.trade_date AND t.stock_ts_code=d.stock_ts_code
    WHERE d.trade_date >= DATE '2026-04-08'
    ORDER BY d.trade_date, abs(d.dev)""").fetchall()

    con.execute(f"""
    CREATE TEMP TABLE drd AS
    SELECT trade_date, count(*) dr_count FROM db.fact_sector_daily
    WHERE {DOUBLE_RED_SQL} GROUP BY 1""")
    mkt = con.execute("""
    SELECT m.trade_date, m.market_stage, m.advancers,
      round(AVG(m.advancers) OVER (ORDER BY m.trade_date ROWS BETWEEN 4 PRECEDING AND CURRENT ROW),0) adv_ma5,
      m.sh_index_pct_chg, m.industry_1, m.industry_2, m.industry_3,
      m.top3_industry_ratio, COALESCE(d.dr_count,0)
    FROM db.fact_market_daily m LEFT JOIN drd d USING (trade_date)
    QUALIFY m.trade_date >= DATE '2026-04-08'
    ORDER BY m.trade_date""").fetchall()
    return rows, mkt


def env_label(adv, shp):
    if adv is not None and shp is not None and adv < 1500 and shp < -0.5:
        return "E1", "E1冰点分歧"
    if adv is not None and adv < 2400:
        return "E2", "E2标准分歧"
    return "E3", "E3修复/亢奋"


def tag(cls, text):
    return f'<span class="tag {cls}">{h.escape(text)}</span>'


def stock(parts):
    return "".join(f'<span class="stock">{p}</span>' for p in parts) if parts else '<span class="empty">-</span>'


def build_rows():
    rows, mkt = fetch()
    by_day: dict[str, list] = {}
    for r in rows:
        by_day.setdefault(r[0].isoformat(), []).append(r)

    out: dict[str, str] = {}
    for (td, stage, adv, adv5, shp, i1, i2, i3, top3r, drc) in mkt:
        d = td.isoformat()
        day = by_day.get(d, [])
        e, ename = env_label(adv, shp)

        first_touch, early, window, sell, risk = [], [], [], [], []
        for r in day:
            _, code, name, close, pct, dv, pdv, brank, lastw, tdate, tclose = r
            name = clean(name)
            if dv is None:
                continue
            if pdv is not None and pdv > 3 and -3 <= dv <= 3:
                first_touch.append((r, name))
            elif 3 < dv <= 5 and (pdv or 0) > 5:
                early.append((r, name))
            elif tdate is not None:
                gain = 100.0 * (close / tclose - 1) if tclose else 0.0
                if gain >= 5:
                    sell.append((r, name, gain))
                elif dv < -1.5:
                    risk.append((r, name))
                elif -3 <= dv <= 5:
                    window.append((r, name))

        a_parts = []
        for (r, name) in first_touch[:5]:
            _, code, _, close, pct, dv, pdv, brank, lastw, *_ = r
            a_parts.append(
                f'{tag("buytag", f"S3-L-A-{e}")} <b>{h.escape(name)} {code}</b><br>'
                f'近15交易日加权最好第{brank}（{lastw.isoformat()[5:]}），首次Touch，偏离UP '
                f'<span class="num">{dv:+.2f}%</span>（前日{pdv:+.2f}%），当日 <span class="num">{pct:+.2f}%</span>'
            )
        if early:
            names = "、".join(f"{n}" for (_, n) in early[:5])
            a_parts.append(
                f'{tag("obstag", "提前观察")} <b>{h.escape(names)}</b><br>'
                f'偏离UP +3%~+5%，提前观察区，不作首买。'
            )

        b_parts = []
        for (r, name) in window[:5]:
            _, code, _, close, pct, dv, pdv, brank, lastw, tdate, tclose = r
            b_parts.append(
                f'{tag("watchtag", "S3-L-B")} <b>{h.escape(name)} {code}</b><br>'
                f'{tdate.isoformat()[5:]} Touch，当前偏离UP <span class="num">{dv:+.2f}%</span>，'
                f'当日 <span class="num">{pct:+.2f}%</span>'
            )

        s_parts = []
        for (r, name, gain) in sorted(sell, key=lambda x: -x[2])[:4]:
            _, code, _, close, pct, dv, pdv, brank, lastw, tdate, tclose = r
            s_parts.append(
                f'{tag("sellt", "SELL")} <b>{h.escape(name)} {code}</b><br>'
                f'{tdate.isoformat()[5:]} Touch后已 <span class="strong">{gain:+.1f}%</span>，'
                f'+5%兑现纪律触发，当日 <span class="num">{pct:+.2f}%</span>'
            )

        r_parts = []
        for (r, name) in risk[:4]:
            _, code, _, close, pct, dv, pdv, brank, lastw, tdate, tclose = r
            r_parts.append(
                f'{tag("risk", "RISK")} <b>{h.escape(name)} {code}</b><br>'
                f'{tdate.isoformat()[5:]} Touch后深破UP，偏离 <span class="bad">{dv:+.2f}%</span>'
                f'（&lt;-1.5%深破剔除），当日 <span class="num">{pct:+.2f}%</span>'
            )

        state = (
            f'{tag("buytag" if e != "E3" else "obstag", f"S3-L-{e}")}{tag("risk", "机械回填")}<br>'
            f'<b>市场状态</b>：{h.escape(stage or "-")}，涨家数 <span class="num">{adv}</span>'
            f'（MA5约 <span class="num">{int(adv5) if adv5 else "-"}</span>），上证 '
            f'<span class="num">{f"{shp:+.2f}%" if shp is not None else "-"}</span>。'
            f'容量前三 {h.escape("/".join(x for x in (i1, i2, i3) if x))}，top3r '
            f'<span class="num">{f"{top3r:.1f}" if top3r is not None else "-"}</span>，双红题材 '
            f'<span class="num">{drc}</span> 个。<br>'
            f'<b>环境标签</b>：{tag("buytag" if e != "E3" else "obstag", ename)}'
            f'（机械口径：E1=涨家数&lt;1500且上证&lt;-0.5%；E2=涨家数&lt;2400；其余E3）。'
        )

        n_ft = len(first_touch)
        verify = (
            f'机械口径回填，人工检验用。'
            f'当日刚Touch <span class="num">{n_ft}</span> 只。'
            f'纪律：{e}下touch日尾盘仅1/3底仓，次日首阳或不破touch低点再加；'
            f'+5%先兑现；深破-1.5%剔除。'
        )

        out[d] = (
            f'<tr class="filled backfill"><td class="date">{d}</td>'
            f'<td>{state}</td><td>{stock(a_parts)}</td><td>{stock(b_parts)}</td>'
            f'<td>{stock(s_parts)}</td><td>{stock(r_parts)}</td><td>{verify}</td></tr>'
        )
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--append-missing", action="store_true",
                    help="矩阵中不存在的日期行按日期序追加（不覆盖人工行）")
    args = ap.parse_args()

    html_text = MATRIX.read_text(encoding="utf-8")
    gen = build_rows()
    empty_pat = re.compile(
        r'<tr><td class="date">(\d{4}-\d{2}-\d{2})</td><td class="empty">待回填</td>'
        r'(?:<td class="empty">-</td>)+</tr>'
        r'|<tr class="filled backfill"><td class="date">(\d{4}-\d{2}-\d{2})</td>.*?</tr>'
    )
    replaced = []

    def sub(m):
        d = m.group(1) or m.group(2)
        if d in gen:
            replaced.append(d)
            return gen[d]
        return m.group(0)

    html_text = empty_pat.sub(sub, html_text)

    appended = []
    if args.append_missing:
        existing = set(re.findall(r'<td class="date">(\d{4}-\d{2}-\d{2})</td>', html_text))
        marker = "</tbody>"
        for d in sorted(gen):
            if d not in existing and marker in html_text:
                html_text = html_text.replace(marker, gen[d] + marker, 1)
                appended.append(d)
    html_text = html_text.replace(
        "当前已填：2026-05-29、2026-06-01、2026-06-02、2026-06-03、2026-06-04、2026-06-05、2026-06-08、2026-06-09",
        "当前已填：全部日期（5.29起为人工D0回填，4.8~5.28为机械口径批量回填，行内标「机械回填」）",
    )
    html_text = html_text.replace(
        "逐步回填模式：4.8-6.9 日期已铺好；当前已填 2026-05-29、2026-06-01、2026-06-02、2026-06-03、2026-06-04、2026-06-05、2026-06-08、2026-06-09。",
        "全部日期已填：5.29 之后为人工 D0 回填；4.8~5.28 为机械口径批量回填（近15日加权Top20池 + UP=MA26+0.764×STD26 + E1/E2/E3机械环境标签），供人工检验。重新生成机械行：python3 scripts/backfill_strategy3_touch_matrix.py。",
    )
    MATRIX.write_text(html_text, encoding="utf-8")
    print(MATRIX)
    print(f"replaced {len(replaced)} empty rows: {replaced[:3]} ... {replaced[-3:]}")
    if appended:
        print(f"appended {len(appended)} new rows: {appended}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
