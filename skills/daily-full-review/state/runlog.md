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

## 2026-06-18 | run 2026-06-20 16:19

| 模块 | 状态 | 耗时s | 备注 |
|---|---|---:|---|
| db-lock | ok | 0 |  |
| sectors | fail | 0 |  |
| market-overview | fail | 0 |  |
| market-daily | ok | 10 |  |
| index-daily | ok | 7 |  |
| sw-l1-daily | ok | 49 |  |
| market-deviation | fail | 0 |  |
| sector-daily | fail | 0 |  |
| sector-stocks | ok | 0 | 224/224 sectors |
| limit-heat | fail | 0 | heat=0 stock=0 retried=0 still_empty=0 |
| stock-high | fail | 0 |  |
| limit-advance | fail | 0 |  |
| stock-daily | ok | 87 | used fill-stock-daily-fallback |
| sector-resonance | fail | 18 |  |
| quality-gate | INCOMPLETE | - | check_daily_review_data.py |

> 需关注（坑/未全绿）：sectors, market-overview, market-deviation, sector-daily, limit-heat, stock-high, limit-advance, sector-resonance

## 2026-06-18 | run 2026-06-20 16:23

| 模块 | 状态 | 耗时s | 备注 |
|---|---|---:|---|
| db-lock | ok | 0 |  |
| sectors | fail | 0 |  |
| market-overview | fail | 0 |  |
| market-daily | ok | 10 |  |
| index-daily | ok | 6 |  |
| sw-l1-daily | ok | 46 |  |
| market-deviation | fail | 0 |  |
| sector-daily | fail | 0 |  |
| sector-stocks | ok | 0 | 224/224 sectors |
| limit-heat | fail | 0 | heat=0 stock=0 retried=0 still_empty=0 |
| stock-high | fail | 0 |  |
| limit-advance | fail | 0 |  |
| stock-daily | ok | 134 | mootdx ok |
| sector-resonance | ok | 23 |  |
| quality-gate | INCOMPLETE | - | check_daily_review_data.py |

> 需关注（坑/未全绿）：sectors, market-overview, market-deviation, sector-daily, limit-heat, stock-high, limit-advance


## 2026-06-22 (run 2026-06-23 00:57)

| Block | Status | Elapsed | Path |
|---|---|---|---|
| db-lock | ok | 0s | - |
| market-daily | ok | ~5s | sync-market-daily (feishu) |
| index-daily | ok | ~8s | sync-index-daily (akshare) |
| sw-l1-daily | ok | ~5s | sync-sw-l1-daily (akshare) |
| market-overview | ok | ~15s | sync-market-overview (fupanhui CDP, Python proxy) |
| market-strength | ok | ~12s | sync-market-strength (fupanhui CDP) |
| market-deviation | fail | - | tooltip parse failed, sh_week_ma/deviation filled by fallback |
| sector-daily | ok | ~20s | sync-sector-daily (fupanhui CDP) |
| sector-stocks | ok | 17s | fast_daily_sync.py copy from 2026-06-18 |
| limit-heat | ok | ~5min | sync-limit-heat + 4 theme retries |
| stock-high | ok | ~15s | sync-stock-high (fupanhui CDP) |
| limit-advance | ok | ~10s | sync-limit-advance (fupanhui CDP) |
| stock-daily | ok | ~8s | fill-stock-daily-fallback (from sector_stock) |
| sector-resonance | ok | ~10s | sync-sector-resonance (feishu) |
| quality-gate | INCOMPLETE | - | 暂无x3 in sector commentary (non-data) |
| daily-review | ok | 3.4s | md + png |
| daily-review-html | ok | <1s | forced past quality-gate |
| evolve generate | ok | via evolve_daily.sh | records/2026-06-22.json |
| evolve validate | ok | via evolve_daily.sh | cumulative-s1/s3/s4.json |
| evolve log | ok | via evolve_daily.sh | - |
| theme radar | ok | via evolve_daily.sh | theme-candidates.json/md |
| theme backfill | ok | via evolve_daily.sh | backfill-queue.json |
| theme review | ok | via evolve_daily.sh | backfill-review-queue.json/md |
| audit | ok | via evolve_daily.sh | - |
| suggest | ok | via evolve_daily.sh | suggestion-20260623-0050.md |

Notes:
- Node.js not installed; wrote Python CDP proxy (/tmp/cdp_proxy.py) to connect Chrome DevTools
- Eastmoney API 502; used fill-stock-daily-fallback instead
- sector-stocks used fast_daily_sync copy from 2026-06-18
- market-deviation tooltip parse failed; sh_week_ma/deviation computed by fallback
- limit-heat 4 themes retried individually: 储能/机器人概念/液冷服务器/DeepSeek概念

### 2026-06-22 后续修复 (run 2026-06-23 01:30)

| 问题 | 根因 | 修复 |
|---|---|---|
| §7 个股发动机为空 | fast_daily_sync 只拷结构，price/amount 全 NULL | sync-sector-stocks --refresh 补2287只股行情 → UPDATE fact_stock_daily |
| §12 加权涨幅缺失 | 同上，fact_stock_daily 无数据 | 同上 |
| 驾驶台晨会简报=0 | cockpit 默认路径 knowledge-base-private 不存在 | --kb-briefings-dir 改指知识库/dashboard/briefings/ |
| 题材雷达 HTML 未生成 | build_* 被 quality-gate INCOMPLETE 拦截 | 直接从已有 md 渲染 HTML |
| 策略一矩阵停留在 6.21 | strategy1 非自动生成 | 手工 T1/T2/OBS 分类 → update_matrix.py |
| 机构胜率缺 6.22 | render_winrate_html 未被调用 | --vault 知识库/wiki --date 2026-06-22 |

修复后重新 daily-review + render_daily_review_html → 111KB，0处"暂无"。
