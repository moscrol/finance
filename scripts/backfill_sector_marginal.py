"""板块边际量抓取脚本（只抓不写，输出 JSON）。

通过 CDP proxy 调 fupanhui API，抓取指定日期的板块边际量。
输出 JSON 到 stdout，由主 agent 写入 DuckDB。

用法:
    python3 scripts/backfill_sector_marginal.py 2025-11-11,2025-11-12,2025-11-13 304309661040170EC630BB8EB1EC9E0A

输出格式:
    {"2025-11-11": {"885537.TI": {"diff_ratio": 0.82, ...}, ...}, ...}
"""
import sys
import json
import urllib.request
import urllib.parse

CDP_PROXY = "http://localhost:3456"

FALLBACK_SECTOR_CODES = [
    "885537.TI","886037.TI","886071.TI","886019.TI","886108.TI","886070.TI",
    "886099.TI","886085.TI","886074.TI","886053.TI","885927.TI","886031.TI",
    "885947.TI","886100.TI","886039.TI","885878.TI","886095.TI","881271.TI",
    "885925.TI","886040.TI","886046.TI","885959.TI","886020.TI","886026.TI",
    "886068.TI","886007.TI","886017.TI","886000.TI","885540.TI","881118.TI",
    "881141.TI","885362.TI","881177.TI","885728.TI","886069.TI","885946.TI",
    "886067.TI","886016.TI","881156.TI","886013.TI","885921.TI","881270.TI",
    "886009.TI","885531.TI","881279.TI","886054.TI","885864.TI","881122.TI",
    "886011.TI","886084.TI","881149.TI","886033.TI","881123.TI","881282.TI",
    "881179.TI","881102.TI","885700.TI","886076.TI","881276.TI","881166.TI",
    "881103.TI","881263.TI","885825.TI","886051.TI","886008.TI","886015.TI",
    "881138.TI","881109.TI","881140.TI","881108.TI","881264.TI","881144.TI",
    "881175.TI","881143.TI","881121.TI","884229.TI","886091.TI","886093.TI",
    "886058.TI","886094.TI","881174.TI","886065.TI","886077.TI","886078.TI",
    "886032.TI","881265.TI","881283.TI","886062.TI","886063.TI","885566.TI","886043.TI",
    "886042.TI","886012.TI","881139.TI","881173.TI","886064.TI","886098.TI",
    "881170.TI","885552.TI","885930.TI","881168.TI","881268.TI","881115.TI",
    "881116.TI","881274.TI","886030.TI","881153.TI","886087.TI","881178.TI",
    "886034.TI","885866.TI","885887.TI","886023.TI","886041.TI","881164.TI",
    "886057.TI","881160.TI","885736.TI","886036.TI","886055.TI","886059.TI",
    "886090.TI","885912.TI","881136.TI","885517.TI","886002.TI","881151.TI",
    "885633.TI","886052.TI","881266.TI","886035.TI","885960.TI","885551.TI",
    "885823.TI","881125.TI","881128.TI","881126.TI","881107.TI","885939.TI",
    "881124.TI","886044.TI","881148.TI","881275.TI","881105.TI","885775.TI",
    "881146.TI","881152.TI","885425.TI","881284.TI","881181.TI","884059.TI",
    "881142.TI","886005.TI","881145.TI","881172.TI","881277.TI","881281.TI",
    "881278.TI","881131.TI","881273.TI","885922.TI","886060.TI","885781.TI",
    "881180.TI","885650.TI","885863.TI","881101.TI","885343.TI","886010.TI",
    "886049.TI","886050.TI","881135.TI","885988.TI","886081.TI","881165.TI",
    "881182.TI","881267.TI","886047.TI","881171.TI","885884.TI","885756.TI",
    "886048.TI","886004.TI","886028.TI","881130.TI","881157.TI","886080.TI",
    "881169.TI","881159.TI","886038.TI","885886.TI","881269.TI","881272.TI",
    "885909.TI","881162.TI","881129.TI","881117.TI","881137.TI","885730.TI",
    "881114.TI","885865.TI","885971.TI","885973.TI","885970.TI","885969.TI",
    "886003.TI","886006.TI","885928.TI","881112.TI","886073.TI","881155.TI",
    "884286.TI","884309.TI","886061.TI","886056.TI","886105.TI","881158.TI",
    "881167.TI","885641.TI","881280.TI","886066.TI","881134.TI","881133.TI",
    "886001.TI","886018.TI","885530.TI","881132.TI",
]


def cdp_eval(js_expr, target, timeout=120):
    data = js_expr.encode()
    req = urllib.request.Request(
        f"{CDP_PROXY}/eval?target={target}",
        data=data, method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            result = json.loads(resp.read())
            return result.get("value")
    except Exception as e:
        print(f"CDP eval 失败: {e}", file=sys.stderr)
        return None


def fetch_sector_codes(trade_date, target):
    """Fetch the sector universe for a date, falling back to the bundled list."""
    query = urllib.parse.urlencode({"trade_date": trade_date, "mode": "auto"})
    js = (
        "(async()=>{"
        f"const r=await fetch('/api/v1/client/reviews/sectors/search?{query}');"
        "const d=await r.json();"
        "const sectors=d.data?.sectors||d.data?.data||d.data||[];"
        "return JSON.stringify(sectors.map(s=>s.ts_code).filter(Boolean));"
        "})()"
    )
    raw = cdp_eval(js, target, timeout=60)
    if raw:
        try:
            codes = json.loads(raw)
            if codes:
                return codes
        except json.JSONDecodeError:
            pass
    print(f"  {trade_date} 板块列表获取失败，回退到内置列表", file=sys.stderr)
    return FALLBACK_SECTOR_CODES


def fetch_kline_for_date(trade_date, target):
    codes_json = json.dumps(fetch_sector_codes(trade_date, target))
    js = (
        "(async()=>{"
        "const sectors=" + codes_json + ";"
        "const results={};"
        "const BATCH=15;"
        "for(let i=0;i<sectors.length;i+=BATCH){"
        "const batch=sectors.slice(i,i+BATCH);"
        "const promises=batch.map(ts=>"
        "fetch('/api/v1/client/reviews/sector-cycle/'+ts+'/kline"
        "?trade_date=" + trade_date + "&days=20&period=daily&mode=auto')"
        ".then(r=>r.json()).then(d=>{"
        "const kline=d.data?.kline||[];"
        "if(kline.length>0){"
        "const last=kline[kline.length-1];"
        "results[ts]={diff_ratio:last.diff_ratio,amount:last.amount,pct_chg:last.pct_chg};"
        "}"
        "}).catch(()=>{}));"
        "await Promise.all(promises);"
        "}"
        "return JSON.stringify(results);"
        "})()"
    )
    return cdp_eval(js, target, timeout=120)


def main():
    if len(sys.argv) < 3:
        print("用法: python3 backfill_sector_marginal.py <逗号分隔日期> <target_id>", file=sys.stderr)
        sys.exit(1)

    dates = sys.argv[1].split(",")
    target = sys.argv[2]

    all_results = {}
    for date_str in dates:
        print(f"抓取 {date_str}...", file=sys.stderr)
        raw = fetch_kline_for_date(date_str.strip(), target)
        if raw:
            try:
                all_results[date_str.strip()] = json.loads(raw)
            except json.JSONDecodeError:
                print(f"  {date_str} 解析失败", file=sys.stderr)

    # JSON 输出到 stdout
    print(json.dumps(all_results, ensure_ascii=False))


if __name__ == "__main__":
    main()
