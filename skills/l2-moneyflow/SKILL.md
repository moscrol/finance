---
name: l2-moneyflow
description: Level2 大单资金流分析（闲鱼日包逐笔成交 → 榜单/个股图 → DuckDB 特征表）。触发词：大单资金流、主买净额、总买净额、涨停股资金流、资金流榜单、量化单、量化买单、大单扫描、moneyflow。注意：问财口径的资金流向查询用 hithink-market-query；本 skill 是自有大单口径（委托编号判主动方向）的逐笔级分析。
---

# Level2 大单资金流分析

代码：`scripts/moneyflow/`（详见其 README.md）。

**夜跑数据源**是闲鱼按日 `.7z`（分享入口只写在 gitignore 的 `state/l2-baidu-share.json`，会每日更新）：本机百度网盘客户端登录 → 转存 `/L2-inbox` → PCS 分片下载 → 只解开名单内个股的「逐笔成交.csv」→ 同一套主买/总买口径写 DuckDB → 删本地副本。**不打 ClickHouse。**

入口：`scripts/moneyflow/run_l2_pipeline.sh <日期>`（全量复盘 finalize @20:40 调用）。已入库则跳过。

## 三个榜单

名单来自本地 DuckDB（昨日涨停、当日成交额前 100），不是全市场扫逐笔。

```bash
FINANCE_PYTHON=.venv-workbench/bin/python \
  scripts/moneyflow/run_l2_pipeline.sh 2026-09-09
```

旧的 `scan_*.py` / `moneyflow.py` 仍连 ClickHouse，夜跑不用。

## 关键口径

- 大单 = 同一委托单当日累计成交额 ≥100万（夜跑；`L2_BIG_THR_WAN`）
- 主动方 = 委托编号大的一方
- 综合得分 = (0.7×主买净额 + 0.3×总买净额) / 流通市值 ×100（净流入强度%）
- 量化单 = 金额±1%窄带、≥10笔的簇，单笔≥200万

## 结果落库

`feature_l2_capital_flow_daily`、`feature_l2_quant_orders_daily`，
可与其它 feature_* 表按 trade_date + stock_ts_code join。
`source` = `baidu-share:xianyu-l2-7z`。

## 红线

- 仅盘后运行；不做全市场逐笔扫描
- 分享 URL / 网盘 Cookie / 密码不入库、不打印
- outputs/ 与本地 7z 不提交；算完删本地副本

## 历史恢复与停牌

历史日包仍走 `process_l2_archive.py`，日期早于上海当天时只读取同日日线名称和涨幅，不调用即时行情；缺少同日流通市值时市值与综合得分写 NULL，净额保留，缺得分行按主买净额排序，榜单与回答披露限制。不能拿当前市值或按价格缩放的基线市值回填历史得分。

缺 CSV 时先核供应商原包与公司/交易所公告。只有已人工核对的全天停牌才能通过 `L2_SUSPENSION_EVIDENCE` 指定本轮 JSON 输入：`trade_date` 必须精确等于目标日，`entries` 每项包含 `stock_code/reason/source_url/evidence_path/evidence_sha256`。URL 使用官方披露域，文件 SHA256 绑定归档原件；代码须在昨日涨停名单内、不能在当日 top100 或涨幅集合中，也不能有同日日线非零成交量/额（即使涨幅为 NULL）。该输入只用于本轮恢复，事实回执由现有 writer 写入 `ops_pipeline_run_daily.message`（原候选数、排除代码、公告 URL/哈希），不生成一条零资金流记录。缺证据、日期不符、原件变化或与行情矛盾均停止。

生产恢复先持有全量复盘共享锁，再用 `market_feature_store.db.clone_to_staging` 的 APFS 克隆隔离重算；验各扫描 `processed_count=input_count`、top100=100、缺失市值明确 NULL，非空净额与当日日线涨幅一致后才按现有 S7 换库协议发布。失败保留原包和日志；正常夜跑的原包清理仍由现有入口负责。
