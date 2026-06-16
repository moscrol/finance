# 单日全量复盘 Runlog

每次跑 `scripts/run_review_sync.py` 自动追加一段；人工可补注释。
顺的路径记住，坑的路径下次规避。

## 2026-06-16 | run（人工补录，本 skill 诞生当天）

| 模块 | 状态 | 耗时s | 备注 |
|---|---|---:|---|
| sector-stocks | ok | - | 逐批 --limit 续跑，224/224 板块抓全 |
| limit-heat | partial→ok | - | 直跑看 chunk 进度 25/25；失败 3 题材 储能/机器人概念/军工 逐个 --sector --detail-chunk 1 补齐 |
| limit-advance | ok | - | --min-boards 2，最高 4 板，31 行 |
| stock-daily | fallback | - | sync-stock-daily 静默挂起持锁，改 fill-stock-daily-fallback，5507 行，sh_week_ma=4040.02 dev=1.28 |
| quality-gate | COMPLETE | - | check_daily_review_data.py 全绿 |

> 坑总结：
> 1. monolith `daily-update` 卡住后手搓 inline 批次，没用已验证脚本 → 本 skill 修正。
> 2. `backfill_review_hot_data.py` 跑 limit-heat 时 stdout 被 PIPE 吞，看不到进度误判挂死 → 改直跑继承 stdout。
> 3. `sync-stock-daily` mootdx 全A 会低 CPU 持锁静默挂 → 直接 `fill-stock-daily-fallback`。
> 4. limit-heat 个别题材失败留空明细 → 逐个 `--sector` 重试，别整轮重跑。

## 2026-06-16 | run 2026-06-17 01:27

| 模块 | 状态 | 耗时s | 备注 |
|---|---|---:|---|
| db-lock | ok | 0 |  |
| quality-gate | COMPLETE | - | check_daily_review_data.py |
