---
name: stock-technicals
metadata:
  pattern: query
description: 个股技术位本地计算：均线（MA5/10/20/26）、UP 线与偏离度、中期/短线回踩筛选，支持自选股清单与历史回溯。触发词：UP线、偏离度、自选股、回踩、均线、MA10、MA20、技术位。注意：数据来自 DuckDB fact_stock_daily，不联网、不依赖外部表格；问历史某天必须传 --as-of。
---

# 个股技术位

## 这个 skill 取代了什么

原先有三个 skill 干这件事的三个切片，都把清单存在飞书多维表格里、指标靠逐只
问 iFinD 拿：`up-line`（UP/偏离度）、`watchlist-ma`（自选股回踩）、
`top-gainers-feishu`（强势股回踩）。飞书 2026-09-11 退役后合并到这里。

**变化**：清单来源改成本地文件或直接传参；指标改成一条 SQL 从
`fact_stock_daily` 批量算；新增 `--as-of`，能回答历史某天的技术位。
**不变**：UP = MA26 + 0.764×STD26、两条回踩口径的判定式。

## 用法

```bash
export MARKET_FEATURE_STORE_DB=/Users/a77/finance-workspace-private/db/market_feature_store.duckdb
FQ=/Users/a77/finance-workspace-private/.venv-workbench/bin/python

# 自选股全量技术位
$FQ -m market_feature_store.cli stock-technicals --watchlist default

# 指定几只（名称、代码、纯数字都认，可混写）
$FQ -m market_feature_store.cli stock-technicals --codes 贵州茅台 601127 000001.SZ

# 只看命中某口径的
$FQ -m market_feature_store.cli stock-technicals --watchlist default --screen pullback

# 回溯历史某天（问「7月10日那天」就必须传，否则拿的是今天的均线）
$FQ -m market_feature_store.cli stock-technicals --codes 贵州茅台 --as-of 2026-07-10

# 给下游/agent 用的结构化输出
$FQ -m market_feature_store.cli stock-technicals --watchlist default --screen pullback --json
```

## 三个筛选口径

| `--screen` | 含义 | 判定 |
|---|---|---|
| `pullback` | 中期回踩 | MA20 < 现价 < MA10 |
| `short-pullback` | 短线回踩 | MA10 < 现价 < MA5 |
| `above-up` | 站上 UP 线 | 现价 > MA26 + 0.764×STD26 |

留空则不筛，输出全部技术位。判定都是**严格不等式**：价格正好等于均线不算命中。

## 自选股清单

存在 `~/.finance-runtime/watchlists/<名字>.txt`（可用 `FINANCE_WATCHLIST_DIR` 改），
一行一只，`#` 起头是注释。**故意不放仓库**——这是用户的持仓意图，不是代码。

```bash
$FQ -m market_feature_store.cli watchlist show                # 看默认清单
$FQ -m market_feature_store.cli watchlist list                # 有哪些清单
$FQ -m market_feature_store.cli watchlist add 寒武纪 --name 打板池
$FQ -m market_feature_store.cli watchlist remove 蜂助手
```

`default` 清单的 13 只是 2026-09-11 从已退役的飞书自选股表导出的，此后由本地维护。

## 接别的排行榜

清单可以来自任何地方，所以「强势股回踩」（原 `top-gainers-feishu` 干的事）现在是两步：

```bash
# 先拿区间涨幅排行的名字，再算技术位
NAMES=$($FQ -m market_feature_store.cli interval-gainers --days 20 --top 30 --json \
        | $FQ -c "import json,sys; print(' '.join(r['stock_name'] for r in json.load(sys.stdin)['rows']))")
$FQ -m market_feature_store.cli stock-technicals --codes $NAMES --screen pullback
```

## 坑

- **`--as-of` 不传就是库尾**。回答「某月某日」的问题必须传，否则算的是今天的均线——
  这个错误看不出来（数字很正常），但答案是错的。
- **样本不足给 None 不给近似**：上市不满 26 个交易日的票没有 UP 值，不是 0 也不是短期均值。
- 停牌期间没有行情行，均线按**已有交易日**算，不补停牌日。
- 同名多只时取最近有成交的那只；要精确请直接传带后缀的代码。
