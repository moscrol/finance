# moneyflow — Level2 大单资金流分析（数据源：ClickHouse）

基于逐笔成交数据（深圳 `share.trans` / 上海 `share.ngts_tick`，库在 `db.base32.cn`）
的大单资金流分析工具集。**盘后运行**，禁止盘中大批量查询。

榜单扫描在 ClickHouse 端用 `PREWHERE` 限定同日同股并完成大单聚合，只返回主买净额、
总买净额、涨幅或聚合后的买方委托金额；只有单股画图 `moneyflow.py` 拉取 raw tick。
同日同股的聚合结果写入共享断点缓存，涨停榜、成交额榜和量化榜重复运行时不重复查询。

## 口径

- **大单**：同一委托单当日累计成交额 ≥ 阈值（默认 50 万）
- **主动方向**：委托编号大的一方为主动方（`BuyNo > SellNo` ⇒ 主动买）
- **主买净额** = 主动买入 − 主动卖出（大单口径，累计）
- **总买净额** = 主买净额 + 被动净额（挂单承接）
- **综合得分** = (0.7×主买 + 0.3×总买) ÷ 流通市值 ×100，即净流入强度(%)
- **量化单**：大买单中金额落在 ±1% 窄带、反复出现 ≥10 笔的簇（单笔 ≥ 量化阈值，默认 200 万）

## 用法

凭证走环境变量（不入库）：`CH_HOST` / `CH_PORT` / `CH_USER` / `CH_PASSWORD`

```bash
cd scripts/moneyflow

# 个股图：分时价格 + 大单散点 + 主买/总买净额曲线 + 量化单标注
CH_PASSWORD=... python3 moneyflow.py 300775 2026-07-03 50

# 昨日涨停股扫描（净额阈值默认2000万，大单阈值默认50万）
CH_PASSWORD=... python3 scan_limitup.py 2026-07-06

# 全市场成交额前100资金流榜
CH_PASSWORD=... python3 scan_top100.py 2026-07-06 50

# 规律量化买单榜（大单阈值50万，量化单阈值200万）
CH_PASSWORD=... python3 scan_quant.py 2026-07-06 50 200
```

产物（CSV/PNG/名单缓存）统一落 `outputs/`（gitignored）。

## DuckDB 特征表

每次扫描后自动把榜单结果写入 market_feature_store（原始 tick 留在 ClickHouse，
DuckDB 只落每日计算结果）：

- `feature_l2_capital_flow_daily`：涨停榜(`scan_type='limitup'`) / 前100榜(`'top100'`)
  的主买、总买、流通市值、综合得分、名次
- `feature_l2_quant_orders_daily`：量化单总额、占大单买入比例、簇数、最大簇

也可用 CSV 手工回填：`python3 write_to_duckdb.py outputs/top100_scan_2026-07-06.csv top100 2026-07-06`

join 示例（大单资金流 × UP线偏离度）：

```sql
SELECT f.trade_date, f.stock_name, f.score, t.deviation_pct
FROM feature_l2_capital_flow_daily f
JOIN feature_stock_technical_daily t
  ON t.trade_date = f.trade_date AND t.stock_ts_code = f.stock_ts_code
WHERE f.scan_type = 'top100' AND f.rank <= 20
ORDER BY f.score DESC;
```

## 数据库注意事项

- 只在盘后运行；逐股查询间隔 0.3s 限速
- 榜单查询使用 ClickHouse 服务端聚合，raw tick 仅供单股画图
- 共享聚合缓存：`outputs/l2_query_cache_<date>.json`
- 全市场聚合仅用于取名单（涨停名单 / 成交额前100），且按代码前缀分批 + 重试 + 本地缓存
- 服务器繁忙时查询会自动退避重连
