# 2026-08-22 收口：08-21 全量复盘质检对齐 + 飞书 market-daily 退役

主检出仍是别人的 `feat/reading-rules-baseline-batch1`（脏树）。**本单不写进该 inflight**。飞书退役在干净树 `fix/retire-feishu-market-daily`（`/Users/a77/fwp-wt-retire-feishu-market-daily`）。

## 结论

08-21 **与 08-18/19/20 对齐**：same-day / 跨日 / workflow 形状同构，日报 15 节齐全、不是空壳过门。差异是盘面和来源标注，不是缺表缺字段。

独立复跑（2026-08-22 00:22，生产库；须 `unset MARKET_FEATURE_STORE_DB`，会话里曾残留已换名消失的 `.staging` 路径）：

| 检查 | 结果 |
|------|------|
| `check_daily_review_data.py 2026-08-21 --phase data` | COMPLETE rc=0 |
| 同上 `--phase all` + `L2_PAUSED=1` | COMPLETE rc=0（L2 挂账跳过） |
| `cli check-daily --trade-date 2026-08-21` | PASS，gaps 空 |
| `quality-2026-08-21.json` | `ok=true` |
| workflow | PASS **19/19**，步骤名与 08-19/20 相同 |
| 板块名连续性 | 402/402 = 100%（08-19 曾 99.75%） |
| 个股覆盖 | 5538/5538 = 100% |
| features | market 4 / sector 1212 / stock 21765 / technical 5516（有派生层） |
| 日报 | 15 节齐，§1 数字对库（上证 3905.2 / 0.04%，成交 18791.51 亿，周均 3924.16，偏离 -0.48%） |
| 产物 | `复盘/daily/2026-08-21/` 6 文件；exports 集合与前三日同构 |
| 增量包 | iCloud `…-inc-2026-08-21.tar.gz` 2.6 MB |
| public-assets | core 50 / global 5+194 / dragon 54 / seat 482 / summary 1（夜跑该步超时，表里已有数，龙虎榜 mtime 15:35） |

对照行数（盘面波动，不是缺口）：sector 403×4 日；成分 52769→52807；涨停题材 198/571（08-20 为 197/648）；新高 287（前两日 ~430）；双红 2（08-20=17，08-19=0）。策略 1：T1=0 T2=5，与 08-19 同形。

## 来源差（记下来，不当今天的洞）

- 上证 `sh_index_source=fupanhui:reviews/market`（前三日是新浪 via AkShare）。TLS 当晚全挂后的兜底，点位进了日报。
- 申万一 `source=akshare:index_realtime_sw`（前三日是 `index_hist_sw`）。**不是昨收盘占位**：31/31 的 `pre_close` 等于 08-20 close，当日 close/amount 全不同。
- 飞书 `sync-market-daily`：用户确认 Bitable 已退役。干净树已从编排/`daily-full`/CLI 拿掉，模块改退役闸门。夜跑脏树编排已去掉该步。未合 `main`。
- 新浪 `index-daily` 仍在编排里；要换复盘会顺手落 `sh_index_*` 另说。

## 已知欠账（别当 08-21 的洞）

- L2 自 08-07 挂账（`state/l2-paused.flag`）
- 官方 `sync-sector-daily` 仍扫 `.TI`；今晚是手工按 published `.FP` 才过
- `public-assets` 夜跑 600s 超时（表已有数，regulation 仍弱）
- 晨汇断至 07-26、卖方事件断至 07-05
- 写入守卫 `c785c3a2`、飞书退役、sector-daily 根修均未进 `gitea/main`
- `db/market_feature_store.duckdb.pre-0819-swap` 仍留着

## 本单可认领

干净树：飞书退役 8 文件 + 本文件 + `docs/handoffs/inflight/fix-retire-feishu-market-daily.md`。脏树夜跑：`run_review_sync.py`（去 market-daily）、`runlog.md`、08-21 产物。

**不要动**：`docs/handoffs/inflight/feat-reading-rules-baseline-batch1.md`、forecast-ledger 那批 `M`。

## 下一步

1. 用户确认后：干净树提交并合飞书退役；新浪是否改复盘会。
2. 另开干净树修 `sync-sector-daily` 只扫 published `.FP`。
3. 写入守卫合 `main` 仍等确认。
