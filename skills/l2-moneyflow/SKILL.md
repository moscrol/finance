---
name: l2-moneyflow
description: Level2 大单资金流分析（ClickHouse 逐笔成交 → 榜单/个股图 → DuckDB 特征表）。触发词：大单资金流、主买净额、总买净额、涨停股资金流、资金流榜单、量化单、量化买单、大单扫描、moneyflow。注意：问财口径的资金流向查询用 hithink-market-query；本 skill 是自有大单口径（委托编号判主动方向）的逐笔级分析。
---

# Level2 大单资金流分析

代码：`scripts/moneyflow/`（详见其 README.md）。数据源为 ClickHouse
`db.base32.cn`（share 库逐笔成交/快照），凭证走环境变量 `CH_PASSWORD` 等。

## 三个榜单 + 个股图

```bash
cd scripts/moneyflow
CH_PASSWORD=... python3 scan_limitup.py <日期>          # 昨日涨停股资金流榜
CH_PASSWORD=... python3 scan_top100.py <日期> [大单阈值万]  # 全市场成交额前100榜
CH_PASSWORD=... python3 scan_quant.py <日期> [大单阈值万] [量化单阈值万]  # 量化单榜
CH_PASSWORD=... python3 moneyflow.py <代码> <日期> [大单阈值万]  # 个股资金流图
```

## 关键口径

- 大单 = 同一委托单当日累计成交额 ≥50万；主动方 = 委托编号大的一方
- 综合得分 = (0.7×主买净额 + 0.3×总买净额) / 流通市值 ×100（净流入强度%）
- 榜单入选：主买、总买均 >0；输出前20
- 量化单 = 金额±1%窄带、≥10笔的簇，单笔≥200万

## 结果落库

扫描后自动写 DuckDB（market_feature_store）：
`feature_l2_capital_flow_daily`、`feature_l2_quant_orders_daily`，
可与其它 feature_* 表按 trade_date + stock_ts_code join。

## 红线

- 仅盘后运行；不做全市场逐笔扫描（名单聚合分批+缓存，逐股限速0.3s）
- 凭证不入库；outputs/ 产物不提交
