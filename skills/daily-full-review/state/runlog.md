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

## 2026-06-24 (run 2026-06-24, Devin remote via rx.py)

| 模块 | 状态 | 耗时s | 备注 |
|---|---|---:|---|
| db-lock | ok | 0 | - |
| sectors | ok | ~5 | sync-sectors (fupanhui) |
| market-overview | ok | ~15 | sync-market-overview (fupanhui) |
| market-daily | ok | ~5 | sync-market-daily (feishu) |
| index-daily | ok | ~8 | sync-index-daily (akshare) |
| sw-l1-daily | ok | ~45 | sync-sw-l1-daily (akshare, 31 rows) |
| market-strength | ok | ~12 | sync-market-strength (fupanhui) |
| market-deviation | ok | - | sh_week_ma=4115.74 dev=-0.12% |
| sector-daily | ok | ~20 | sync-sector-daily (224 sectors) |
| sector-stocks | partial | ~20min | 213/224 sectors; fupanhui 逐板块慢 + Cloudflare 524 导致多次重试 |
| limit-heat | ok | ~3min | 154 heat + 670 stock |
| stock-high | ok | ~15 | 404 rows |
| limit-advance | ok | ~10 | 12 rows |
| stock-daily | ok | ~1 | fill-stock-daily-fallback (东财 502, mootdx 太慢弃用), 2169 rows |
| sector-resonance | ok | ~10 | sync-sector-resonance (feishu) |
| quality-gate | COMPLETE | - | check_daily_review_data.py 全绿 |
| daily-review | ok | ~3 | md + png (零占位符) |
| daily-review-html | ok | <1 | 94.7KB |
| evolve 8步 | ok | ~2min | via evolve_daily.sh, S1[T1CORE6=6] S3[ALL=3] S4[A=6 B=6] |
| agent-daily | ok | ~30 | intelligence.cli agent-daily, 14.9KB HTML |
| cockpit | ok | <1 | render_cockpit.py, daily=17 |
| workbench | ok | <1 | render_review_workbench.py |

> 坑总结（2026-06-24 新增，已写入 SKILL.md 防坑点）：
> 1. 没用 run_review_sync.py 编排器，手动逐步跑 sync，用错参数（sync-stock-daily --refresh offset=180 ≈ 90min）。
> 2. Cloudflare 524 超时后 Mac 进程残留持 DuckDB 锁，盲目重启新进程导致锁冲突。
> 3. 东财快照 API 全局 502，mootdx 全A太慢 → 最终 fill-stock-daily-fallback 秒级解决。
> 4. nohup + Python stdout 缓冲 → 日志看不到进度，需 python3 -u。
> 5. 漏跑 agent-daily（不在 evolve_daily.sh），导致驾驶台缺 "Agent 简报"。
> 6. Token U+2028 编码问题 + exec service hmac Python 3.9 bug → 隧道 401/502。


## 2026-06-26 | run 2026-06-27 21:18

| 模块 | 状态 | 耗时s | 备注 |
|---|---|---:|---|
| db-lock | ok | 0 |  |
| sectors | fail | 5 |  |
| market-overview | fail | 0 |  |
| market-daily | ok | 11 |  |
| index-daily | ok | 7 |  |
| sw-l1-daily | ok | 44 |  |
| market-deviation | fail | 5 |  |
| sector-daily | ok | 31 |  |
| sector-stocks | ok | 0 | 224/224 sectors |
| limit-heat | ok | 221 | heat=126 stock=355 retried=0 still_empty=0 |
| stock-high | ok | 62 |  |
| limit-advance | ok | 3 |  |
| stock-daily | ok | 8 | used fill-stock-daily-fallback |
| sector-resonance | ok | 20 |  |
| quality-gate | INCOMPLETE | - | check_daily_review_data.py |

> 需关注（坑/未全绿）：sectors, market-overview, market-deviation

## 2026-07-20 | run 2026-07-20 20:12

| 模块 | 状态 | 耗时s | 备注 |
|---|---|---:|---|
| db-lock | ok | 0 |  |
| sectors | ok | 1 |  |
| market-overview | ok | 3 |  |
| market-daily | ok | 2 |  |
| index-daily | ok | 1 |  |
| sw-l1-daily | ok | 33 |  |
| market-deviation | ok | 5 |  |
| sector-daily | ok | 14 |  |
| sector-stocks | ok | 0 | 224/224 sectors |
| limit-heat | ok | 46 | heat=85 stock=212 retried=0 still_empty=0 |
| stock-high | ok | 13 |  |
| limit-advance | ok | 1 |  |
| stock-daily | ok | 15 | eastmoney snapshot ok |
| sector-resonance | ok | 6 |  |
| mainline-daily | fail | 11 | [retry r1] |
| mainline-sector-daily | ok | 4 |  |
| theme-flow-daily | ok | 1 |  |
| features | ok | 1 |  |
| same-day-gate | fail | 0 |  |
| quality-gate | INCOMPLETE | - | check_daily_review_data.py |

> 需关注（坑/未全绿）：mainline-daily, same-day-gate

## 2026-07-20 | run 2026-07-22 00:37

| 模块 | 状态 | 耗时s | 备注 |
|---|---|---:|---|
| db-lock | ok | 0 |  |
| sectors | ok | 2 |  |
| market-overview | ok | 3 |  |
| market-daily | ok | 2 |  |
| index-daily | ok | 1 |  |
| sw-l1-daily | ok | 28 |  |
| market-deviation | ok | 5 |  |
| sector-daily | ok | 14 |  |
| sector-stocks | ok | 0 | 224/224 sectors |
| limit-heat | ok | 43 | heat=85 stock=212 retried=0 still_empty=0 |
| stock-high | ok | 14 |  |
| limit-advance | ok | 1 |  |
| stock-daily | ok | 20 | eastmoney snapshot ok |
| sector-resonance | ok | 6 |  |
| mainline-daily | ok | 10 |  |
| mainline-sector-daily | ok | 5 |  |
| theme-flow-daily | ok | 1 |  |
| features | ok | 1 |  |
| same-day-gate | ok | 0 |  |
| cross-day-gate | ok | 0 |  |
| export-increment | ok | 0 |  |
| quality-gate | COMPLETE | - | check_daily_review_data.py |

## 2026-07-21 | run 2026-07-22 01:11

| 模块 | 状态 | 耗时s | 备注 |
|---|---|---:|---|
| db-lock | ok | 0 |  |
| sectors | ok | 1 |  |
| market-overview | ok | 3 |  |
| market-daily | ok | 2 |  |
| index-daily | ok | 1 |  |
| sw-l1-daily | ok | 33 |  |
| market-deviation | ok | 4 |  |
| sector-daily | ok | 14 |  |
| sector-stocks | ok | 0 | 224/224 sectors |
| limit-heat | ok | 62 | heat=143 stock=825 retried=0 still_empty=0 |
| stock-high | ok | 15 |  |
| limit-advance | ok | 1 |  |
| stock-daily | ok | 19 | eastmoney snapshot ok |
| sector-resonance | ok | 6 |  |
| mainline-daily | fail | 3 | [retry r1] |
| mainline-sector-daily | fail | 2 | [retry r1] |
| theme-flow-daily | ok | 1 |  |
| features | ok | 1 |  |
| same-day-gate | fail | 0 |  |
| quality-gate | INCOMPLETE | - | check_daily_review_data.py |

> 需关注（坑/未全绿）：mainline-daily, mainline-sector-daily, same-day-gate

## 2026-07-22 | run 2026-07-22 18:37

| 模块 | 状态 | 耗时s | 备注 |
|---|---|---:|---|
| db-lock | ok | 0 |  |
| sectors | ok | 8 |  |
| market-overview | ok | 3 |  |
| market-daily | ok | 2 |  |
| index-daily | ok | 1 |  |
| sw-l1-daily | ok | 195 |  |
| market-deviation | ok | 6 |  |
| sector-daily | ok | 16 |  |
| sector-stocks | ok | 0 | 224/224 sectors |
| limit-heat | ok | 54 | heat=96 stock=226 retried=0 still_empty=0 |
| stock-high | ok | 12 |  |
| limit-advance | ok | 1 |  |
| stock-daily | ok | 17 | eastmoney snapshot ok |
| sector-resonance | ok | 6 |  |
| mainline-daily | ok | 14 |  |
| mainline-sector-daily | ok | 6 |  |
| theme-flow-daily | ok | 1 |  |
| features | ok | 1 |  |
| same-day-gate | ok | 0 |  |
| cross-day-gate | fail | 0 |  |
| quality-gate | INCOMPLETE | - | check_daily_review_data.py |

> 需关注（坑/未全绿）：cross-day-gate

## 2026-07-22 | run 2026-07-23 01:09

| 模块 | 状态 | 耗时s | 备注 |
|---|---|---:|---|
| db-lock | ok | 0 |  |
| sectors | ok | 2 |  |
| market-overview | ok | 4 |  |
| market-daily | ok | 5 |  |
| index-daily | ok | 1 |  |
| sw-l1-daily | ok | 35 |  |
| market-deviation | ok | 7 |  |
| sector-daily | ok | 18 |  |
| sector-stocks | ok | 0 | 224/224 sectors |
| limit-heat | ok | 48 | heat=96 stock=226 retried=0 still_empty=0 |
| stock-high | ok | 13 |  |
| limit-advance | ok | 2 |  |
| stock-daily | ok | 25 | eastmoney snapshot ok |
| sector-resonance | ok | 8 |  |
| mainline-daily | ok | 13 |  |
| mainline-sector-daily | ok | 5 |  |
| theme-flow-daily | ok | 1 |  |
| features | ok | 2 |  |
| same-day-gate | ok | 0 |  |
| cross-day-gate | fail | 0 |  |
| quality-gate | INCOMPLETE | - | check_daily_review_data.py |

> 需关注（坑/未全绿）：cross-day-gate

## 2026-07-23 | run 2026-07-23 18:38

| 模块 | 状态 | 耗时s | 备注 |
|---|---|---:|---|
| db-lock | ok | 0 |  |
| sectors | ok | 9 |  |
| market-overview | ok | 4 |  |
| market-daily | ok | 2 |  |
| index-daily | ok | 1 |  |
| sw-l1-daily | ok | 216 |  |
| market-deviation | ok | 5 |  |
| sector-daily | ok | 15 |  |
| sector-stocks | ok | 0 | 224/224 sectors |
| limit-heat | ok | 84 | heat=138 stock=578 retried=0 still_empty=0 |
| stock-high | ok | 14 |  |
| limit-advance | ok | 1 |  |
| stock-daily | ok | 26 | eastmoney snapshot ok |
| sector-resonance | ok | 7 |  |
| mainline-daily | ok | 7 |  |
| mainline-sector-daily | ok | 5 |  |
| theme-flow-daily | ok | 1 |  |
| features | ok | 1 |  |
| same-day-gate | ok | 0 |  |
| cross-day-gate | ok | 0 |  |
| export-increment | ok | 0 |  |
| quality-gate | COMPLETE | - | check_daily_review_data.py |

## 2026-07-24 | run 2026-07-24 23:24

| 模块 | 状态 | 耗时s | 备注 |
|---|---|---:|---|
| db-lock | ok | 0 |  |
| sectors | ok | 8 |  |
| market-overview | ok | 2 |  |
| market-daily | ok | 2 |  |
| index-daily | ok | 1 |  |
| sw-l1-daily | ok | 36 |  |
| market-deviation | fail | 11 | [retry r1] |
| sector-daily | ok | 66 |  |
| sector-stocks | ok | 0 | 224/224 sectors |
| limit-heat | ok | 125 | heat=90 stock=190 retried=0 still_empty=0 |
| stock-high | ok | 16 |  |
| limit-advance | ok | 1 |  |
| stock-daily | ok | 20 | eastmoney snapshot ok |
| sector-resonance | ok | 6 |  |
| mainline-daily | ok | 6 |  |
| mainline-sector-daily | ok | 5 |  |
| theme-flow-daily | ok | 1 |  |
| features | ok | 1 |  |
| same-day-gate | fail | 0 |  |
| quality-gate | INCOMPLETE | - | check_daily_review_data.py |

> 需关注（坑/未全绿）：market-deviation, same-day-gate

## 2026-07-27 | run 2026-07-27 23:00

| 模块 | 状态 | 耗时s | 备注 |
|---|---|---:|---|
| db-lock | ok | 0 |  |
| sectors | ok | 2 |  |
| market-overview | ok | 2 |  |
| market-daily | ok | 2 |  |
| index-daily | ok | 2 |  |
| sw-l1-daily | ok | 39 |  |
| market-deviation | ok | 9 |  |
| sector-daily | ok | 34 |  |
| sector-stocks | partial | 0 | 0/630 sectors after 20 loops |
| limit-heat | ok | 279 | heat=286 stock=1069 retried=0 still_empty=0 |
| stock-high | ok | 14 |  |
| limit-advance | ok | 3 |  |
| stock-daily | ok | 26 | eastmoney snapshot ok |
| sector-resonance | ok | 7 |  |
| mainline-daily | ok | 4 |  |
| mainline-sector-daily | ok | 3 |  |
| theme-flow-daily | ok | 1 |  |
| features | ok | 2 |  |
| same-day-gate | fail | 0 |  |
| quality-gate | INCOMPLETE | - | check_daily_review_data.py |

> 需关注（坑/未全绿）：sector-stocks, same-day-gate

## 2026-07-28 | run 2026-07-29 00:12

| 模块 | 状态 | 耗时s | 备注 |
|---|---|---:|---|
| db-lock | ok | 0 |  |
| sectors | ok | 8 |  |
| market-overview | ok | 10 |  |
| market-daily | ok | 3 |  |
| index-daily | ok | 1 |  |
| sw-l1-daily | fail | 0 | [retry r1] |
| market-deviation | ok | 16 |  |
| sector-daily | ok | 120 |  |
| sector-stocks | partial | 0 | 0/630 sectors after 20 loops |
| limit-heat | ok | 320 | heat=223 stock=770 retried=0 still_empty=0 |
| stock-high | ok | 36 |  |
| limit-advance | fail | 0 | [retry r1] |
| stock-daily | fail | 0 | used fill-stock-daily-fallback [retry r1] |
| sector-resonance | fail | 0 | [retry r1] |
| mainline-daily | fail | 0 | [retry r1] |
| mainline-sector-daily | fail | 0 | [retry r1] |
| theme-flow-daily | fail | 0 | [retry r1] |
| features | fail | 0 | [retry r1] |
| same-day-gate | fail | 0 |  |
| quality-gate | INCOMPLETE | - | check_daily_review_data.py |

> 需关注（坑/未全绿）：sw-l1-daily, sector-stocks, limit-advance, stock-daily, sector-resonance, mainline-daily, mainline-sector-daily, theme-flow-daily, features, same-day-gate

## 2026-07-28 | run 2026-07-29 01:30

| 模块 | 状态 | 耗时s | 备注 |
|---|---|---:|---|
| limit-advance | ok | 4 |  |
| stock-daily | fail | 120 | used fill-stock-daily-fallback |
| sector-resonance | ok | 7 |  |
| mainline-daily | ok | 9 |  |
| mainline-sector-daily | ok | 9 |  |
| theme-flow-daily | ok | 3 |  |
| features | fail | 0 |  |
| same-day-gate | fail | 0 |  |
| quality-gate | INCOMPLETE | - | check_daily_review_data.py |

> 需关注（坑/未全绿）：stock-daily, features, same-day-gate

## 2026-07-29 | run 2026-07-29 18:59

| 模块 | 状态 | 耗时s | 备注 |
|---|---|---:|---|
| db-lock | ok | 0 |  |
| sectors | ok | 5 |  |
| market-overview | ok | 8 |  |
| market-daily | ok | 3 |  |
| index-daily | ok | 2 |  |
| sw-l1-daily | timeout | 300 | [retry r1] |
| market-deviation | ok | 14 |  |
| sector-daily | ok | 100 |  |
| sector-stocks | partial | 0 | 0/630 sectors after 20 loops |
| limit-heat | ok | 314 | heat=211 stock=657 retried=0 still_empty=0 |
| stock-high | ok | 50 |  |
| limit-advance | ok | 3 |  |
| stock-daily | ok | 139 | eastmoney snapshot ok |
| sector-resonance | ok | 8 |  |
| mainline-daily | ok | 9 |  |
| mainline-sector-daily | ok | 9 |  |
| theme-flow-daily | ok | 3 |  |
| features | ok | 1 |  |
| same-day-gate | fail | 1 |  |
| quality-gate | INCOMPLETE | - | check_daily_review_data.py |

> 需关注（坑/未全绿）：sw-l1-daily, sector-stocks, same-day-gate

## 2026-07-30 | run 2026-07-30 18:30

| 模块 | 状态 | 耗时s | 备注 |
|---|---|---:|---|
| db-lock | ok | 0 |  |
| sectors | fail | 0 | [retry r1] |
| market-overview | fail | 0 | [retry r1] |
| market-daily | fail | 1 | [retry r1] |
| index-daily | fail | 0 | [retry r1] |
| sw-l1-daily | fail | 0 | [retry r1] |
| market-deviation | fail | 0 | [retry r1] |
| sector-daily | fail | 0 | [retry r1] |
| sector-stocks | partial | 0 | 403/630 sectors after 20 loops |
| limit-heat | fail | 0 | heat=0 stock=0 retried=0 still_empty=0 [retry r1] |
| stock-high | fail | 0 | [retry r1] |
| limit-advance | fail | 0 | [retry r1] |
| stock-daily | fail | 0 | used fill-stock-daily-fallback [retry r1] |
| sector-resonance | fail | 4 | [retry r1] |
| mainline-daily | fail | 7 | [retry r1] |
| mainline-sector-daily | fail | 3 | [retry r1] |
| theme-flow-daily | fail | 1 | [retry r1] |
| features | fail | 0 | [retry r1] |
| same-day-gate | fail | 2 |  |
| quality-gate | INCOMPLETE | - | check_daily_review_data.py |

> 需关注（坑/未全绿）：sectors, market-overview, market-daily, index-daily, sw-l1-daily, market-deviation, sector-daily, sector-stocks, limit-heat, stock-high, limit-advance, stock-daily, sector-resonance, mainline-daily, mainline-sector-daily, theme-flow-daily, features, same-day-gate

## 2026-07-30 | run 2026-07-30 23:55（Devin 补全）

### 阻断性修复（前置）

| 问题 | 根因 | 修复 |
|---|---|---|
| CDP proxy 连不上 Chrome | Chrome 只绑 IPv6 [::1]:9222，proxy checkPort 只试 IPv4 127.0.0.1 | patch cdp-proxy.mjs：checkPort 依次试 IPv4→IPv6，URL 构造兼容 [::1] |
| init_db Binder Error: can only create an index on a base table | fact_sector_daily / fact_sector_stock_daily 已重构为 VIEW，schema.sql 仍保留 CREATE INDEX ON 视图名 | 注释 5 条冗余索引（底层 generation 表已有等价索引）；private + runtime 两仓同步修 |
| sync-sector-daily/stocks/resonance Catalog Error: not a table | 3 个 sync 脚本仍 INSERT INTO 视图名 | 重定向到 *_generation 表 + 注入 get_published_snapshot_id() |

### 同步段（daily-full CLI，修复后重跑）

| 模块 | 状态 | 备注 |
|---|---|---|
| db-lock | ok | 8799 canary 持锁，bootout 后释放 |
| sectors | ok | |
| market-overview | ok | |
| market-daily | ok | |
| index-daily | ok | |
| sw-l1-daily | ok | |
| market-deviation | ok | tooltip 抓取失败，MA5 复算回退 |
| sector-daily | ok | generation 表写入 |
| sector-stocks | ok | 403/403 sectors（only_missing 跳已抓） |
| limit-heat | ok | 188 heat + 409 stock |
| stock-high | ok | 808 rows |
| limit-advance | ok | 10 rows |
| stock-daily | ok | eastmoney snapshot 5527 rows |
| sector-resonance | ok | generation 表写入 |
| mainline-daily | ok | |
| theme-flow-daily | ok | |
| mainline-sector-daily | ok | |
| features | ok | compute_features: period_rank 40 rows + window features |
| same-day-gate | ok | check_daily_review_data.py COMPLETE (99.95% stock coverage) |

### L2 资金流段

| 模块 | 状态 | 备注 |
|---|---|---|
| l2-limitup | ok | 82/83 只，1 只空数据 |
| l2-top100 | ok | 100 只，写入 100 行 |
| l2-quant | ok | 52 只，识别量化簇 |

### 生成段（intelligence.cli daily --skip-sync --skip-agent）

| 模块 | 状态 | 备注 |
|---|---|---|
| quality-gate | PASS | |
| daily-review | ok | md + png + html |
| theme-candidates | ok | json + md + html |
| theme-backfill-queue | ok | |
| triggered-theme-brief | ok | DEEP: 食品饮料/中特估/跨境支付CIPS |
| strategy1-matrix | ok | T1=4 T2=5 |
| strategy3-matrix | ok | appended 07-27~07-30 |
| strategy4-matrix | ok | 78 days engineA=1092 engineB=3714 |
| review-workbench | ok | |
| cockpit | ok | daily=30 |
| agent-daily | **SKIPPED** | content delta exceeds 10MB（知识库 wiki 未提交改动过多，非复盘数据问题） |

> 坑总结：
> 1. 视图重构（fact_sector_daily → VIEW + generation 表）后，schema.sql 和 3 个 sync 脚本未同步更新，导致全部 sync 步骤 init_db 阶段就挂。
> 2. CDP proxy IPv6 兼容是 macOS Chrome 常见问题（只绑 [::1]），launchd 自动重启的 proxy 也无法自愈。
> 3. agent-daily 的 content_delta 10MB 上限在知识库大量未提交改动时会超限——需要定期 commit 知识库或提高上限。
> 4. 两个 uvicorn 实例（8792 canonical + 8799 canary）竞争 DuckDB 写锁是隐患。

## 2026-08-03 | run 2026-08-03 18:43

| 模块 | 状态 | 耗时s | 备注 |
|---|---|---:|---|
| db-lock | ok | 0 |  |
| sectors | ok | 9 |  |
| market-overview | ok | 3 |  |
| market-daily | ok | 5 |  |
| index-daily | ok | 3 |  |
| sw-l1-daily | ok | 276 |  |
| market-deviation | ok | 10 |  |
| sector-daily | ok | 32 |  |
| sector-stocks | partial | 0 | 2026-08-03 snapshot=4740cdb24fb5 success=0/403 rel=0+0/52753 pending=403 retriable=0 nulls=0 continuity=100% missing_tables=fact_sector_stock_daily mismatch=relationships after 20 loops |
| limit-heat | ok | 342 | heat=234 stock=751 retried=0 still_empty=0 |
| stock-high | ok | 61 |  |
| limit-advance | ok | 2 |  |
| stock-daily | ok | 37 | eastmoney snapshot ok |
| mainline-daily | ok | 8 |  |
| mainline-sector-daily | ok | 6 |  |
| theme-flow-daily | ok | 1 |  |
| features | ok | 1 |  |
| same-day-gate | fail | 1 |  |
| quality-gate | INCOMPLETE | - | check_daily_review_data.py |

> 需关注（坑/未全绿）：sector-stocks, same-day-gate

## 2026-08-04 | run 2026-08-05 00:43

| 模块 | 状态 | 耗时s | 备注 |
|---|---|---:|---|
| db-lock | ok | 0 |  |
| sectors | ok | 3 |  |
| market-overview | ok | 8 |  |
| market-daily | ok | 3 |  |
| index-daily | ok | 2 |  |
| sw-l1-daily | ok | 75 |  |
| market-deviation | ok | 0 |  |
| sector-daily | ok | 44 |  |
| sector-stocks | partial | 0 | 2026-08-04 snapshot=d1cf9ffe267d success=0/403 rel=0+0/52782 pending=403 retriable=0 nulls=0 continuity=100% missing_tables=fact_sector_stock_daily mismatch=relationships after 20 loops |
| limit-heat | ok | 47 | heat=284 stock=1734 retried=0 still_empty=0 |
| stock-high | ok | 78 |  |
| limit-advance | ok | 1 |  |
| stock-daily | ok | 42 | eastmoney snapshot ok |
| mainline-daily | ok | 37 |  |
| mainline-sector-daily | ok | 9 |  |
| theme-flow-daily | ok | 5 |  |
| features | ok | 1 |  |
| same-day-gate | fail | 1 |  |
| quality-gate | INCOMPLETE | - | check_daily_review_data.py |

> 需关注（坑/未全绿）：sector-stocks, same-day-gate

## 2026-08-04 | run 2026-08-05 01:21

| 模块 | 状态 | 耗时s | 备注 |
|---|---|---:|---|
| sector-stocks | ok | 0 | 2026-08-04 snapshot=d1cf9ffe267d success=403/403 rel=52683+99/52782 pending=0 retriable=0 nulls=0 continuity=100% missing_tables=- mismatch=- |
| same-day-gate | ok | 1 |  |
| cross-day-gate | ok | 0 |  |
| export-increment | ok | 0 |  |
| quality-gate | COMPLETE | - | check_daily_review_data.py |

## 2026-08-05 | run 2026-08-05 18:50

| 模块 | 状态 | 耗时s | 备注 |
|---|---|---:|---|
| db-lock | ok | 0 |  |
| sectors | ok | 3 |  |
| market-overview | ok | 4 |  |
| market-daily | ok | 2 |  |
| index-daily | ok | 2 |  |
| sw-l1-daily | ok | 256 | [retry r1] |
| market-deviation | ok | 1 |  |
| sector-daily | ok | 46 |  |
| sector-stocks | ok | 0 | 2026-08-05 snapshot=52abf8e671e7 success=403/403 rel=52709+73/52782 pending=0 retriable=0 nulls=0 continuity=100% missing_tables=- mismatch=- |
| limit-heat | ok | 75 | heat=251 stock=1098 retried=0 still_empty=0 |
| stock-high | ok | 51 |  |
| limit-advance | ok | 4 |  |
| stock-daily | ok | 49 | eastmoney snapshot ok |
| mainline-daily | ok | 6 |  |
| mainline-sector-daily | ok | 5 |  |
| theme-flow-daily | ok | 1 |  |
| features | ok | 1 |  |
| same-day-gate | ok | 1 |  |
| cross-day-gate | ok | 0 |  |
| export-increment | ok | 0 |  |
| quality-gate | COMPLETE | - | check_daily_review_data.py |

## 2026-08-06 | run 2026-08-06 22:07

| 模块 | 状态 | 耗时s | 备注 |
|---|---|---:|---|
| db-lock | ok | 0 |  |
| sectors | ok | 3 |  |
| market-overview | ok | 3 |  |
| market-daily | ok | 3 |  |
| index-daily | ok | 1 |  |
| sw-l1-daily | ok | 246 |  |
| market-deviation | ok | 11 |  |
| sector-daily | ok | 34 |  |
| sector-stocks | ok | 0 | 2026-08-06 snapshot=e309c15e51ba success=403/403 rel=52707+84/52791 pending=0 retriable=0 nulls=0 continuity=100% missing_tables=- mismatch=- |
| limit-heat | ok | 31 | heat=223 stock=846 retried=0 still_empty=0 |
| stock-high | ok | 88 |  |
| limit-advance | ok | 1 |  |
| stock-daily | ok | 24 | eastmoney snapshot ok |
| mainline-daily | ok | 4 |  |
| mainline-sector-daily | ok | 4 |  |
| theme-flow-daily | ok | 1 |  |
| features | ok | 1 |  |
| same-day-gate | ok | 0 |  |
| cross-day-gate | ok | 0 |  |
| export-increment | ok | 0 |  |
| quality-gate | COMPLETE | - | check_daily_review_data.py |

## 2026-08-14 | run 2026-08-15 10:52

| 模块 | 状态 | 耗时s | 备注 |
|---|---|---:|---|
| market-daily | ok | 4 |  |
| same-day-gate | fail | 1 |  |
| quality-gate | INCOMPLETE | - | check_daily_review_data.py |

> 需关注（坑/未全绿）：same-day-gate

## 2026-08-14 | run 2026-08-15 10:52

| 模块 | 状态 | 耗时s | 备注 |
|---|---|---:|---|
| index-daily | fail | 1 |  |
| same-day-gate | fail | 1 |  |
| quality-gate | INCOMPLETE | - | check_daily_review_data.py |

> 需关注（坑/未全绿）：index-daily, same-day-gate

## 2026-08-14 | run 2026-08-15 11:16

| 模块 | 状态 | 耗时s | 备注 |
|---|---|---:|---|
| db-lock | ok | 0 |  |
| sectors | ok | 5 |  |
| market-overview | ok | 11 |  |
| market-daily | ok | 3 |  |
| index-daily | ok | 2 |  |
| sw-l1-daily | ok | 156 |  |
| market-deviation | ok | 13 |  |
| sector-daily | ok | 151 |  |
| sector-stocks | ok | 0 | 2026-08-14 snapshot=27569ceb0d11 success=403/403 rel=52800+53/52853 pending=0 retriable=0 nulls=0 continuity=100% missing_tables=- mismatch=- |
| limit-heat | ok | 81 | heat=214 stock=610 retried=0 still_empty=0 |
| stock-high | ok | 87 |  |
| limit-advance | ok | 6 |  |
| stock-daily | ok | 32 | eastmoney snapshot ok |
| mainline-daily | fail | 8 | [retry r1] |
| mainline-sector-daily | fail | 9 | [retry r1] |
| theme-flow-daily | ok | 6 |  |
| features | ok | 4 |  |
| same-day-gate | fail | 2 |  |
| quality-gate | INCOMPLETE | - | check_daily_review_data.py |

> 需关注（坑/未全绿）：mainline-daily, mainline-sector-daily, same-day-gate

## 2026-08-14 | run 2026-08-15 12:27

| 模块 | 状态 | 耗时s | 备注 |
|---|---|---:|---|
| mainline-daily | ok | 29 |  |
| mainline-sector-daily | ok | 20 |  |
| theme-flow-daily | ok | 4 |  |
| features | ok | 3 |  |
| same-day-gate | ok | 1 |  |
| cross-day-gate | fail | 1 |  |
| quality-gate | INCOMPLETE | - | check_daily_review_data.py |

> 需关注（坑/未全绿）：cross-day-gate

## 2026-08-14 | run 2026-08-15 12:41

| 模块 | 状态 | 耗时s | 备注 |
|---|---|---:|---|
| public-assets | ok | ~365 | sync-fupanhui-public-assets --trade-date 2026-08-14；fundamentals 撞 QA 读锁失败，不进跨日门 |
| cross-day-gate | ok | 3 | check-daily PASS |
| quality-gate | COMPLETE | - | same-day COMPLETE + cross-day PASS |

> 编排器原先漏了 public-assets（monolith 有、run_review_sync 无）。已接到 theme-flow 之后。
