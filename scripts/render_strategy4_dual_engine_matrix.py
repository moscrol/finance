"""生成策略4双引擎每日优选矩阵 HTML（D0口径，仅用当日及以前数据）。

用法:
    python3 scripts/render_strategy4_dual_engine_matrix.py [--start 2026-04-08] [--end YYYY-MM-DD]

口径（与 research/market-hypothesis/strategy4-dual-engine-regime-validation.md 一致）:
- 开关v2: 双红题材数MA5>MA20 且 top3r 40~45（黄金窗）；软开关: top3r<45
- 引擎A: 单日加权(pct*sqrt(amount)) Top20 ∩ 容量前三行业 ∩ (当日涨停近似>=9.8% 或 近7个交易日重复进Top20)
- 引擎B: 当日≥1年新高 ∩ 近5个交易日新高≥3天 ∩ 容量前三行业
输出: 复盘/matrices/strategy4-dual-engine-matrix.html
"""
from __future__ import annotations

import argparse
import html as h
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "db/market_feature_store.duckdb"
OUT = ROOT / "复盘/matrices/strategy4-dual-engine-matrix.html"

LONG_HIGH = ("1y", "2y", "3y", "history")


def build(start: str, end: str | None):
    con = duckdb.connect()
    con.execute(f"ATTACH '{DB}' AS db (READ_ONLY)")
    if end is None:
        end = con.execute("SELECT max(trade_date) FROM db.fact_stock_daily").fetchone()[0].isoformat()

    con.execute("""
    CREATE TEMP TABLE drd AS
    SELECT trade_date, count(*) dr_count,
      string_agg(sector_name, '、' ORDER BY amount DESC) dr_names
    FROM db.fact_sector_daily
    WHERE pct_chg>0 AND diff_ratio>10 AND amount>500 GROUP BY 1""")

    con.execute("""
    CREATE TEMP TABLE mkt AS
    SELECT m.trade_date, m.market_stage, m.advancers, m.sh_index_pct_chg,
      m.industry_1, m.industry_2, m.industry_3, m.top3_industry_ratio top3r,
      COALESCE(d.dr_count,0) dr_count, d.dr_names,
      AVG(COALESCE(d.dr_count,0)) OVER w5 dr_ma5,
      AVG(COALESCE(d.dr_count,0)) OVER w20 dr_ma20
    FROM db.fact_market_daily m LEFT JOIN drd d USING (trade_date)
    WINDOW w5 AS (ORDER BY m.trade_date ROWS BETWEEN 4 PRECEDING AND CURRENT ROW),
           w20 AS (ORDER BY m.trade_date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW)""")

    con.execute("""
    CREATE TEMP TABLE swmap AS
    SELECT stock_ts_code, mode(sw_l1) sw_l1 FROM db.fact_sector_stock_daily GROUP BY 1""")

    con.execute(f"""
    CREATE TEMP TABLE w20 AS
    SELECT trade_date, stock_ts_code, stock_name, pct_chg, amount, w_rank FROM (
      SELECT trade_date, stock_ts_code, stock_name, pct_chg, amount,
        ROW_NUMBER() OVER (PARTITION BY trade_date ORDER BY pct_chg*sqrt(GREATEST(amount,0)) DESC) w_rank
      FROM db.fact_stock_daily WHERE pct_chg>0)
    WHERE w_rank<=20""")

    eng_a = con.execute(f"""
    SELECT w.trade_date, w.stock_ts_code, w.stock_name, sm.sw_l1, w.pct_chg, w.amount, w.w_rank,
      (SELECT count(*) FROM w20 p WHERE p.stock_ts_code=w.stock_ts_code
        AND p.trade_date<w.trade_date AND p.trade_date>=w.trade_date-INTERVAL 11 DAY) prior7,
      (w.pct_chg>=9.8)::int is_limit
    FROM w20 w
    JOIN swmap sm USING (stock_ts_code)
    JOIN mkt m ON w.trade_date=m.trade_date
    WHERE sm.sw_l1 IN (m.industry_1, m.industry_2, m.industry_3)
      AND w.trade_date BETWEEN DATE '{start}' AND DATE '{end}'
    ORDER BY w.trade_date, w.w_rank""").fetchall()

    eng_b = con.execute(f"""
    WITH hd AS (
      SELECT trade_date, stock_ts_code, stock_name, primary_high_period, primary_high_label,
        pct_chg, amount, sw_l1,
        (SELECT count(DISTINCT p.trade_date) FROM db.fact_stock_high_daily p
          WHERE p.stock_ts_code=fact_stock_high_daily.stock_ts_code
            AND p.trade_date<=fact_stock_high_daily.trade_date
            AND p.trade_date>fact_stock_high_daily.trade_date-INTERVAL 8 DAY) hi5
      FROM db.fact_stock_high_daily
      WHERE trade_date BETWEEN DATE '{start}' AND DATE '{end}')
    SELECT hd.trade_date, hd.stock_ts_code, hd.stock_name, hd.sw_l1, hd.pct_chg, hd.amount,
      hd.primary_high_label, hd.hi5
    FROM hd JOIN mkt m ON hd.trade_date=m.trade_date
    WHERE hd.primary_high_period IN {LONG_HIGH}
      AND hd.hi5>=3
      AND hd.sw_l1 IN (m.industry_1, m.industry_2, m.industry_3)
    ORDER BY hd.trade_date, hd.amount DESC""").fetchall()

    days = con.execute(f"""
    SELECT trade_date, market_stage, advancers, sh_index_pct_chg,
      industry_1, industry_2, industry_3, top3r, dr_count, dr_names,
      round(dr_ma5,1), round(dr_ma20,1)
    FROM mkt WHERE trade_date BETWEEN DATE '{start}' AND DATE '{end}'
    ORDER BY trade_date""").fetchall()
    return days, eng_a, eng_b, end


def clean(name: str | None) -> str:
    return (name or "").replace("\x00", "").strip()


def tag(cls: str, text: str) -> str:
    return f'<span class="tag {cls}">{h.escape(text)}</span>'


def stock_block(parts: list[str]) -> str:
    return "".join(f'<span class="stock">{p}</span>' for p in parts) if parts else '<span class="stock"><span class="tag obstag">当日无</span> 引擎无输出，不强行标的。</span>'


def render(days, eng_a, eng_b, start: str, end: str) -> str:
    a_by_day: dict[str, list] = {}
    for r in eng_a:
        a_by_day.setdefault(r[0].isoformat(), []).append(r)
    b_by_day: dict[str, list] = {}
    for r in eng_b:
        b_by_day.setdefault(r[0].isoformat(), []).append(r)

    rows = []
    for (td, stage, adv, shp, i1, i2, i3, top3r, drc, drn, dma5, dma20) in days:
        d = td.isoformat()
        gate = dma5 is not None and dma20 is not None and dma5 > dma20 and top3r is not None and 40 <= top3r <= 45
        soft = top3r is not None and top3r < 45
        a_all = a_by_day.get(d, [])
        b_all = b_by_day.get(d, [])
        a_qual = [r for r in a_all if r[7] >= 1 or r[8] == 1]
        b_codes = {r[1] for r in b_all}

        if gate:
            mode_tag = tag("buytag", "开关期·引擎B主攻")
            mode_txt = "双红MA5>MA20 且 top3r 40~45 黄金窗：引擎B（长周期新高∩容量前三）按主仓执行，引擎A辅助。"
        elif soft:
            mode_tag = tag("watchtag", "软开关·小仓")
            mode_txt = "top3r<45 但未进黄金窗：双引擎只做小仓，优先双引擎重叠票。"
        else:
            mode_tag = tag("risk", "开关关·仅观察")
            mode_txt = "top3r≥45 容量过度集中：历史上该状态全市场中位为负，只记录不执行。"

        dr_trend = "扩张" if (dma5 or 0) > (dma20 or 0) else "收缩"
        state = (
            f'{mode_tag}{tag("obstag", "仅D0")}<br>'
            f'<b>市场</b>：{h.escape(stage or "-")}，涨家数 <span class="num">{adv if adv is not None else "-"}</span>，'
            f'上证 <span class="num">{f"{shp:+.2f}%" if shp is not None else "-"}</span><br>'
            f'<b>容量前三</b>：{h.escape("/".join(x for x in (i1, i2, i3) if x))}，'
            f'top3r <span class="num">{f"{top3r:.1f}" if top3r is not None else "-"}</span><br>'
            f'<b>双红时钟</b>：当日 <span class="num">{drc}</span> 个，MA5 <span class="num">{dma5}</span> vs MA20 <span class="num">{dma20}</span>（{dr_trend}）'
            + (f'<br><b>双红题材</b>：{h.escape((drn or "")[:90])}' if drn else "")
        )

        a_parts = []
        for r in a_qual[:6]:
            _, code, name, sw, pct, amt, rk, prior7, is_limit = r
            trig = []
            if is_limit:
                trig.append("涨停")
            if prior7 >= 1:
                trig.append(f"近7日重复{prior7}次")
            both = " " + tag("sellt", "双引擎") if code in b_codes else ""
            a_parts.append(
                f'{tag("buytag", "引擎A")}{both} <b>{h.escape(clean(name))} {code}</b><br>'
                f'加权第{rk}，{h.escape(sw or "-")}，当日 <span class="num">{pct:+.2f}%</span>，'
                f'成交 <span class="num">{amt:.1f}亿</span>，触发：{h.escape("+".join(trig))}'
            )

        b_parts = []
        a_codes = {r[1] for r in a_qual}
        for r in b_all[:6]:
            _, code, name, sw, pct, amt, hilabel, hi5 = r
            both = " " + tag("sellt", "双引擎") if code in a_codes else ""
            b_parts.append(
                f'{tag("watchtag", "引擎B")}{both} <b>{h.escape(clean(name))} {code}</b><br>'
                f'{h.escape(hilabel or "-")}，近5日新高{hi5}天，{h.escape(sw or "-")}，'
                f'当日 <span class="num">{pct:+.2f}%</span>，成交 <span class="num">{(amt or 0):.1f}亿</span>'
            )

        verify = (
            f'<b>模式</b>：{mode_txt}<br>'
            f'<b>检验要点</b>：1) 引擎票次日/10日内是否给出可兑现反弹；'
            f'2) 双引擎重叠票是否显著强于单引擎；'
            f'3) 开关关闭日若引擎票仍走强，记录为反例。'
        )

        overlap = a_codes & b_codes
        if overlap:
            verify += f'<br><b>双引擎重叠</b>：<span class="strong">{len(overlap)}只</span>'

        rows.append(
            f'<tr class="filled"><td class="date">{d}</td>'
            f'<td>{state}</td>'
            f'<td>{stock_block(a_parts)}</td>'
            f'<td>{stock_block(b_parts)}</td>'
            f'<td>{verify}</td></tr>'
        )

    n_days = len(days)
    body = "\n".join(rows)
    return f'''<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>策略4双引擎每日优选矩阵 {start}~{end}</title>
<style>
:root{{--bg:#07080d;--panel:#111824;--line:#273548;--text:#edf4ff;--muted:#91a3b8;--green:#64f4ac;--amber:#ffd166;--blue:#7cc7ff;--red:#ff7171;--purple:#c792ea}}*{{box-sizing:border-box}}body{{margin:0;background:radial-gradient(circle at 9% 0%,#173457,transparent 26%),radial-gradient(circle at 84% 10%,#33234d,transparent 26%),linear-gradient(180deg,#07080d,#101723);color:var(--text);font-family:'Avenir Next','PingFang SC','Microsoft YaHei',sans-serif}}.wrap{{max-width:1880px;margin:0 auto;padding:24px}}.hero{{border:1px solid var(--line);border-radius:28px;background:linear-gradient(135deg,#151f2d,#0a0f17);padding:28px 32px;margin-bottom:18px;box-shadow:0 20px 80px #0008}}.eyebrow{{color:var(--amber);letter-spacing:.22em;font-size:12px;font-weight:900}}.hero h1{{margin:8px 0 10px;font-size:38px;line-height:1.1}}.meta{{display:flex;flex-wrap:wrap;gap:10px;color:var(--muted)}}.pill{{border:1px solid var(--line);border-radius:999px;padding:7px 11px;background:#0d141dcc}}.legend{{display:flex;gap:8px;flex-wrap:wrap;margin-top:14px}}.tag{{display:inline-block;border:1px solid var(--line);border-radius:999px;padding:3px 8px;margin:2px 4px 4px 0;font-size:12px;font-weight:900}}.buytag{{color:#07110b;background:var(--green);border-color:var(--green)}}.watchtag{{color:#06131b;background:var(--blue);border-color:var(--blue)}}.sellt{{color:#161004;background:var(--amber);border-color:var(--amber)}}.risk{{color:#1b0606;background:var(--red);border-color:var(--red)}}.obstag{{color:#160d20;background:var(--purple);border-color:var(--purple)}}.rules{{display:grid;grid-template-columns:repeat(4,minmax(210px,1fr));gap:12px;margin:18px 0}}.rule{{border:1px solid var(--line);border-radius:18px;background:#0d141bcc;padding:14px;line-height:1.55}}.rule b{{color:var(--amber)}}.toolbar{{display:flex;gap:10px;align-items:center;margin:18px 0;flex-wrap:wrap}}.toolbar input,.toolbar select{{border:1px solid var(--line);background:#0b1218;color:var(--text);border-radius:12px;padding:10px 12px}}.toolbar input{{min-width:320px}}.table-wrap{{border:1px solid var(--line);border-radius:18px;overflow:auto;background:#0c121acc;max-height:78vh}}table{{border-collapse:collapse;width:100%;min-width:1700px}}th,td{{border-bottom:1px solid var(--line);padding:11px 12px;vertical-align:top;font-size:13.5px;line-height:1.6}}th{{position:sticky;top:0;background:#101a27;z-index:3;text-align:left;color:var(--amber)}}td.date{{white-space:nowrap;font-weight:900;color:var(--blue)}}.stock{{display:block;border:1px solid var(--line);border-radius:12px;background:#0d141d;padding:8px 9px;margin:0 0 7px}}.num{{color:var(--amber);font-weight:900}}.strong{{color:var(--green);font-weight:900}}.bad{{color:var(--red);font-weight:900}}.hide{{display:none}}.foot{{color:var(--muted);margin-top:12px;line-height:1.6}}body.compact td{{font-size:12px;line-height:1.45}}td:nth-child(2){{min-width:330px}}td:nth-child(3),td:nth-child(4){{min-width:380px}}td:nth-child(5){{min-width:300px}}</style>
</head>
<body>
<div class="wrap">
<section class="hero"><div class="eyebrow">STRATEGY 4 DUAL ENGINE MATRIX</div><h1>策略4 双引擎每日优选矩阵</h1><div class="meta"><span class="pill">行：交易日期</span><span class="pill">开关v2：双红MA5&gt;MA20 且 top3r 40~45</span><span class="pill">引擎A：加权Top20∩容量前三∩(涨停或近7日重复)</span><span class="pill">引擎B：≥1年新高∩近5日新高≥3天∩容量前三</span><span class="pill">日期范围：{start} ~ {end}（{n_days}个交易日）</span></div><div class="legend"><span class="tag buytag">引擎A 加权动量</span><span class="tag watchtag">引擎B 长高趋势</span><span class="tag sellt">双引擎重叠</span><span class="tag risk">开关关·仅观察</span><span class="tag obstag">D0 仅当日数据</span></div></section>
<section class="rules"><div class="rule"><b>开关状态</b><br>黄金窗=双红题材数MA5&gt;MA20 且 top3r 40~45，引擎B按主仓执行；top3r&lt;45 软开关只做小仓；top3r≥45 仅观察。</div><div class="rule"><b>引擎A</b><br>单日加权(涨幅×√成交额)Top20，限容量前三行业，再要求当日涨停或近7个交易日重复进Top20。偏动量爆发。</div><div class="rule"><b>引擎B</b><br>当日≥1年新高（1年/2年/3年/历史），近5个交易日新高≥3天，限容量前三行业。偏趋势抱团，验证期望最高。</div><div class="rule"><b>验证目标</b><br>全周期回测：引擎B@黄金窗 10日中位+3.21%/胜率67%；开关关 -1.73%/43%。人工检验重点是开关状态与个股质量是否一致。</div></section>
<div class="toolbar"><input id="q" placeholder="搜索日期/股票/代码/行业/开关"><select id="gatef"><option value="">全部日期</option><option value="开关期">只看黄金窗开</option><option value="软开关">只看软开关</option><option value="仅观察">只看开关关</option></select><button id="compact">紧凑</button></div>
<div class="table-wrap"><table id="matrix"><thead><tr><th class="date">日期</th><th>市场/开关状态</th><th>引擎A 优选<br>加权动量∩容量前三</th><th>引擎B 优选<br>长周期新高∩容量前三</th><th>模式建议 / 人工检验要点</th></tr></thead><tbody>
{body}
</tbody></table></div>
<div class="foot">D0纪律：本矩阵每行只使用当日及以前可见数据生成，不含任何后续收益；人工检验时请独立记录每只票的后续表现，再与开关状态对照。口径与 research/market-hypothesis/strategy4-dual-engine-regime-validation.md 一致。重新生成：python3 scripts/render_strategy4_dual_engine_matrix.py</div>
</div>
<script>
const q=document.getElementById('q'),f=document.getElementById('gatef'),rows=[...document.querySelectorAll('#matrix tbody tr')];
function apply(){{const text=q.value.trim().toLowerCase(),mode=f.value;rows.forEach(r=>{{const okText=!text||r.innerText.toLowerCase().includes(text);const okMode=!mode||r.innerText.includes(mode);r.classList.toggle('hide',!(okText&&okMode));}})}}
q.oninput=apply;f.onchange=apply;document.getElementById('compact').onclick=()=>document.body.classList.toggle('compact');
</script>
</body>
</html>
'''


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--start", default="2026-04-08")
    p.add_argument("--end", default=None)
    args = p.parse_args()
    days, eng_a, eng_b, end = build(args.start, args.end)
    OUT.write_text(render(days, eng_a, eng_b, args.start, end), encoding="utf-8")
    print(OUT)
    print(f"days={len(days)} engineA_rows={len(eng_a)} engineB_rows={len(eng_b)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
