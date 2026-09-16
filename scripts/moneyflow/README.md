# moneyflow — Level2 大单资金流

夜跑只走闲鱼按日 `.7z`（百度分享，入口在 gitignore 的 `state/l2-baidu-share.json`）：
转存到网盘 `/L2-inbox` → PCS 4MB 分片下载 → 只解开名单内「逐笔成交.csv」→
同一套主买/总买口径写 DuckDB → 删本地副本。不打 ClickHouse。

入口：`scripts/moneyflow/run_l2_pipeline.sh YYYY-MM-DD`（finalize @20:40 调用）。

## 口径

- **大单**：同一委托单当日累计成交额 ≥ 阈值（夜跑默认 **100 万**，`L2_BIG_THR_WAN`）
- **主动方向**：委托编号大的一方为主动方（`BuyNo > SellNo` ⇒ 主动买）
- **主买净额** = 主动买入 − 主动卖出（大单口径，累计）
- **总买净额** = 主买净额 + 被动净额（挂单承接）
- **综合得分** = (0.7×主买 + 0.3×总买) ÷ 流通市值 ×100，即净流入强度(%)
- **量化单**：大买单中金额落在 ±1% 窄带、反复出现 ≥10 笔的簇（单笔 ≥ 量化阈值，默认 200 万）

名单来自本地 DuckDB：昨日涨停 + 当日成交额前 100。不是全市场逐笔扫描。

## 用法

```bash
# 夜跑同款（要本机百度网盘客户端已登录，分享 json 在 state/）
FINANCE_PYTHON=.venv-workbench/bin/python \
  scripts/moneyflow/run_l2_pipeline.sh 2026-09-09

# 已有 7z 时只解算
.venv-workbench/bin/python scripts/moneyflow/process_l2_archive.py \
  2026-09-09 /path/to/20260909.7z
```

`scan_*.py` / `moneyflow.py` 仍是旧 ClickHouse 客户端，夜跑不调用。

产物（CSV/PNG/名单缓存）统一落 `outputs/`（gitignored）。

## DuckDB 特征表

- `feature_l2_capital_flow_daily`：涨停榜(`scan_type='limitup'`) / 前100榜(`'top100'`)
- `feature_l2_quant_orders_daily`：量化单总额、占大单买入比例、簇数、最大簇

`source` 默认 `baidu-share:xianyu-l2-7z`（环境变量 `L2_SOURCE` 可改）。

join 示例：

```sql
SELECT f.trade_date, f.stock_name, f.score, t.deviation_pct
FROM feature_l2_capital_flow_daily f
JOIN feature_stock_technical_daily t
  ON t.trade_date = f.trade_date AND t.stock_ts_code = f.stock_ts_code
WHERE f.scan_type = 'top100' AND f.rank <= 20
ORDER BY f.score DESC;
```

## 运维

- 仅盘后；日包约 5–6GB，磁盘不够就一天一天来
- 分享还没上当日文件时会等（`L2_SHARE_WAIT_ATTEMPTS` × `L2_SHARE_WAIT_SECONDS`，默认 8×180s）
- 凭证：本机网盘客户端 Cookie，不入库；分享密码只在 `state/l2-baidu-share.json`
