"""AKShare 板块涨幅查询脚本 - 一级行业、二级行业、概念板块并行查询。

输出 JSON 格式：{level1: [...], level2: [...], concept: [...]}
每个条目: [名称, 涨幅%]
"""
import json
import sys
import akshare as ak
from concurrent.futures import ThreadPoolExecutor, as_completed

LEVEL1 = ["农林牧渔","基础化工","钢铁","有色金属","电子","家用电器","食品饮料",
    "纺织服饰","轻工制造","医药生物","公用事业","交通运输","房地产","商贸零售",
    "社会服务","综合","建筑材料","建筑装饰","电力设备","国防军工","计算机",
    "传媒","通信","银行","非银金融","汽车","机械设备","煤炭","石油石化","环保","美容护理"]

NOISE_KEYWORDS = ['昨日涨停','昨日首板','昨日连板','昨日跌幅','今日涨停','今日首板',
    '融资融券','深股通','沪股通','转融券','富时罗素','MSCI','央企改革',
    'ST板块','次新股','注册制','破发股','高股息','预盈预增','预亏预减',
    '一季报','年报','中报','业绩预升','业绩预降','减持','增持','回购',
    '重组','壳资源','送转','分红','股权','转让','质押','解禁','定增',
    '举牌','要约','退市','停牌','复牌','首发']

CONCEPT_LIMIT = 50


def get_industry_gain(name, start, end):
    try:
        h = ak.stock_board_industry_hist_em(symbol=name, period="日k", start_date=start, end_date=end, adjust="")
        if len(h) >= 2:
            first, last = float(h.iloc[0]["收盘"]), float(h.iloc[-1]["收盘"])
            return (name, round((last - first) / first * 100, 2))
    except Exception:
        pass
    return None


def get_concept_gain(name, code, start, end):
    try:
        h = ak.stock_board_concept_hist_em(symbol=code, period="daily", start_date=start, end_date=end, adjust="")
        if len(h) >= 2:
            first, last = float(h.iloc[0]["收盘"]), float(h.iloc[-1]["收盘"])
            return (name, round((last - first) / first * 100, 2))
    except Exception:
        pass
    return None


def validate_date(s):
    """校验 YYYYMMDD 格式。"""
    if len(s) != 8 or not s.isdigit():
        return False
    y, m, d = int(s[:4]), int(s[4:6]), int(s[6:8])
    return 2000 <= y <= 2099 and 1 <= m <= 12 and 1 <= d <= 31


def main():
    if len(sys.argv) != 3:
        print("Usage: python query_sectors.py YYYYMMDD YYYYMMDD", file=sys.stderr)
        sys.exit(1)

    start, end = sys.argv[1], sys.argv[2]
    for d in [start, end]:
        if not validate_date(d):
            print(f"无效日期格式: {d}，需要 YYYYMMDD", file=sys.stderr)
            sys.exit(1)
    if start > end:
        print(f"起始日期 {start} 晚于结束日期 {end}", file=sys.stderr)
        sys.exit(1)

    # 获取二级行业名称
    idf = ak.stock_board_industry_name_em()
    level2 = idf[idf['板块名称'].str.endswith('Ⅱ')]['板块名称'].tolist()

    # 获取概念板块（过滤噪声）
    cdf = ak.stock_board_concept_name_em()
    filtered = cdf[~cdf['板块名称'].apply(lambda x: any(n in str(x) for n in NOISE_KEYWORDS))]
    concepts = filtered.head(CONCEPT_LIMIT)[['板块名称','板块代码']].values.tolist()

    # 并行查询
    results_l1, results_l2, results_concept = [], [], []
    total_tasks = len(LEVEL1) + len(level2) + len(concepts)
    done_count = 0

    with ThreadPoolExecutor(max_workers=40) as executor:
        futs = {executor.submit(get_industry_gain, n, start, end): ('l1', n) for n in LEVEL1}
        futs.update({executor.submit(get_industry_gain, n, start, end): ('l2', n) for n in level2})
        futs.update({executor.submit(get_concept_gain, n, c, start, end): ('concept', n) for n, c in concepts})
        for f in as_completed(futs):
            tag, name = futs[f]
            done_count += 1
            if done_count % 50 == 0:
                print(f"进度: {done_count}/{total_tasks}", file=sys.stderr)
            r = f.result()
            if r and r[1] is not None:
                if tag == 'l1':
                    results_l1.append(r)
                elif tag == 'l2':
                    results_l2.append(r)
                else:
                    results_concept.append(r)

    results_l1.sort(key=lambda x: x[1], reverse=True)
    results_l2.sort(key=lambda x: x[1], reverse=True)
    results_concept.sort(key=lambda x: x[1], reverse=True)

    output = {
        "level1": results_l1,
        "level2": results_l2[:10],
        "concept": results_concept[:10],
    }
    print(json.dumps(output, ensure_ascii=False))

if __name__ == "__main__":
    main()
