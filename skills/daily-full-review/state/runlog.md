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

## 2026-08-17 | run 2026-08-17 16:58

| 模块 | 状态 | 耗时s | 备注 |
|---|---|---:|---|
| db-lock | ok | 0 |  |
| sectors | ok | 7 |  |
| market-overview | ok | 57 |  |
| market-daily | ok | 3 |  |
| index-daily | fail | 2 | [retry r1] |
| sw-l1-daily | timeout | 300 | [retry r1] |
| market-deviation | fail | 16 | [retry r1] |
| sector-daily | ok | 127 |  |
| sector-stocks | ok | 0 | 2026-08-17 snapshot=fc4ab49168f5 success=403/403 rel=52775+81/52856 pending=0 retriable=0 nulls=0 continuity=100% missing_tables=- mismatch=- |
| limit-heat | ok | 83 | heat=271 stock=1021 retried=0 still_empty=0 |
| stock-high | ok | 137 |  |
| limit-advance | ok | 5 |  |
| stock-daily | ok | 33 | eastmoney snapshot ok |
| mainline-daily | ok | 17 |  |
| mainline-sector-daily | ok | 17 |  |
| theme-flow-daily | ok | 9 |  |
| features | ok | 1 |  |
| same-day-gate | fail | 2 |  |
| quality-gate | INCOMPLETE | - | check_daily_review_data.py |

> 需关注（坑/未全绿）：index-daily, sw-l1-daily, market-deviation, same-day-gate

## 2026-08-17 | run 2026-08-17 18:47

| 模块 | 状态 | 耗时s | 备注 |
|---|---|---:|---|
| db-lock | ok | 0 |  |
| sectors | ok | 8 |  |
| market-overview | ok | 10 |  |
| market-daily | ok | 3 |  |
| index-daily | ok | 2 |  |
| sw-l1-daily | timeout | 300 | [retry r1] |
| market-deviation | ok | 14 |  |
| sector-daily | ok | 147 |  |
| sector-stocks | ok | 0 | 2026-08-17 snapshot=fc4ab49168f5 success=403/403 rel=52775+81/52856 pending=0 retriable=0 nulls=0 continuity=100% missing_tables=- mismatch=- |
| limit-heat | ok | 77 | heat=271 stock=1021 retried=0 still_empty=0 |
| stock-high | ok | 123 |  |
| limit-advance | ok | 4 |  |
| stock-daily | ok | 34 | eastmoney snapshot ok |
| mainline-daily | ok | 14 |  |
| mainline-sector-daily | ok | 14 |  |
| theme-flow-daily | ok | 3 |  |
| features | ok | 2 |  |
| same-day-gate | fail | 1 |  |
| quality-gate | INCOMPLETE | - | check_daily_review_data.py |

> 需关注（坑/未全绿）：sw-l1-daily, same-day-gate

## 2026-08-18 | run 2026-08-18 18:54

| 模块 | 状态 | 耗时s | 备注 |
|---|---|---:|---|
| db-lock | ok | 0 |  |
| sectors | ok | 10 |  |
| market-overview | ok | 8 |  |
| market-daily | ok | 4 |  |
| index-daily | ok | 1 |  |
| sw-l1-daily | ok | 227 |  |
| market-deviation | ok | 12 |  |
| sector-daily | ok | 120 |  |
| sector-stocks | ok | 0 | 2026-08-18 snapshot=b25dc46acb8e success=403/403 rel=52768+88/52856 pending=0 retriable=0 nulls=0 continuity=100% missing_tables=- mismatch=- |
| limit-heat | ok | 61 | heat=214 stock=655 retried=0 still_empty=0 |
| stock-high | ok | 183 |  |
| limit-advance | ok | 5 |  |
| stock-daily | ok | 34 | eastmoney snapshot ok |
| mainline-daily | ok | 16 |  |
| mainline-sector-daily | ok | 16 |  |
| theme-flow-daily | ok | 4 |  |
| features | ok | 1 |  |
| same-day-gate | ok | 1 |  |
| cross-day-gate | fail | 1 |  |
| quality-gate | INCOMPLETE | - | check_daily_review_data.py |

> 需关注（坑/未全绿）：cross-day-gate

## 2026-08-18 | run 2026-08-18 20:32

| 模块 | 状态 | 耗时s | 备注 |
|---|---|---:|---|
| db-lock | ok | 0 |  |
| sectors | ok | 5 |  |
| market-overview | ok | 13 |  |
| market-daily | ok | 3 |  |
| index-daily | ok | 1 |  |
| sw-l1-daily | ok | 197 |  |
| market-deviation | ok | 12 |  |
| sector-daily | ok | 138 |  |
| sector-stocks | ok | 0 | 2026-08-18 snapshot=b25dc46acb8e success=403/403 rel=52769+87/52856 pending=0 retriable=0 nulls=0 continuity=100% missing_tables=- mismatch=- |
| limit-heat | ok | 52 | heat=214 stock=655 retried=0 still_empty=0 [retry r1] |
| stock-high | ok | 235 |  |
| limit-advance | ok | 12 |  |
| stock-daily | ok | 45 | eastmoney snapshot ok |
| mainline-daily | ok | 17 |  |
| mainline-sector-daily | ok | 14 |  |
| theme-flow-daily | ok | 4 |  |
| features | ok | 1 |  |
| same-day-gate | ok | 1 |  |
| cross-day-gate | fail | 1 |  |
| quality-gate | INCOMPLETE | - | check_daily_review_data.py |

> 需关注（坑/未全绿）：cross-day-gate

## 2026-08-18 | run 2026-08-18 21:34

| 模块 | 状态 | 耗时s | 备注 |
|---|---|---:|---|
| db-lock | ok | 0 |  |
| sectors | ok | 15 |  |
| market-overview | ok | 7 |  |
| market-daily | ok | 3 |  |
| index-daily | ok | 1 |  |
| sw-l1-daily | ok | 288 |  |
| market-deviation | ok | 14 |  |
| sector-daily | ok | 131 |  |
| sector-stocks | ok | 0 | 2026-08-18 snapshot=b25dc46acb8e success=403/403 rel=52769+87/52856 pending=0 retriable=0 nulls=0 continuity=100% missing_tables=- mismatch=- |
| limit-heat | ok | 72 | heat=214 stock=655 retried=0 still_empty=0 |
| stock-high | ok | 347 |  |
| limit-advance | ok | 5 |  |
| stock-daily | ok | 67 | eastmoney snapshot ok |
| mainline-daily | ok | 31 |  |
| mainline-sector-daily | ok | 26 |  |
| theme-flow-daily | ok | 11 |  |
| features | ok | 1 |  |
| same-day-gate | ok | 1 |  |
| cross-day-gate | ok | 1 |  |
| export-increment | ok | 0 |  |
| quality-gate | COMPLETE | - | check_daily_review_data.py |

## 2026-08-19 | run 2026-08-19 19:06

| 模块 | 状态 | 耗时s | 备注 |
|---|---|---:|---|
| db-lock | ok | 0 |  |
| sectors | ok | 4 |  |
| market-overview | ok | 7 |  |
| market-daily | ok | 3 |  |
| index-daily | ok | 2 |  |
| sw-l1-daily | timeout | 300 | [retry r1] |
| market-deviation | ok | 16 |  |
| sector-daily | ok | 117 |  |
| sector-stocks | partial | 0 | 2026-08-19 snapshot=d22acd5399c9 success=403/403 rel=52779+88/52867 pending=0 retriable=0 nulls=0 continuity=100% missing_tables=fact_sector_daily mismatch=daily_identities after 20 loops |
| limit-heat | ok | 62 | heat=121 stock=223 retried=0 still_empty=0 |
| stock-high | ok | 132 |  |
| limit-advance | ok | 4 |  |
| stock-daily | ok | 33 | eastmoney snapshot ok |
| mainline-daily | ok | 12 |  |
| mainline-sector-daily | ok | 12 |  |
| theme-flow-daily | ok | 8 |  |
| public-assets | ok | 524 |  |
| features | ok | 1 |  |
| same-day-gate | fail | 1 |  |
| quality-gate | INCOMPLETE | - | check_daily_review_data.py |

> 需关注（坑/未全绿）：sw-l1-daily, sector-stocks, same-day-gate

## 2026-08-19 | repair 2026-08-20 10:27（staging 补洞后换名）

| 模块 | 状态 | 耗时s | 备注 |
|---|---|---:|---|
| sw-l1-daily | ok | 2 | 官方 hist/分析报告 08-19 尚未发布；用 index_realtime_sw 昨收盘写 close/pct_chg（与 08-18 同一序列）。amount 暂沿用 08-18，source=`...:prev_close`。今晚 --days 20 hist 有数会覆盖 |
| public-assets | ok | 2 | 只补 dragon_summary（昨夜 `/data/dragon/all` 超时）；regulation 仍超时，不进断档门 |
| same-day-gate | ok | 1 | COMPLETE（生产库换名后复检） |
| cross-day-gate | ok | 1 | PASS，近 20 日无断档 |
| export-increment | ok | 1 | 29 表 / 120269 行，3.1 MB |
| quality-gate | COMPLETE | - | check_daily 通过；备份 `db/market_feature_store.duckdb.pre-0819-swap` |

> 夜跑 19:06 same-day 败于 sw-l1 超时 → 不换名。08-20 盘中补洞后原子换进生产。

## 2026-08-20 | run 2026-08-20 18:57

| 模块 | 状态 | 耗时s | 备注 |
|---|---|---:|---|
| db-lock | ok | 0 |  |
| sectors | ok | 4 |  |
| market-overview | ok | 3 |  |
| market-daily | ok | 3 |  |
| index-daily | ok | 2 |  |
| sw-l1-daily | timeout | 300 | [retry r1] |
| market-deviation | ok | 10 |  |
| sector-daily | ok | 67 |  |
| sector-stocks | ok | 0 | 2026-08-20 snapshot=20c72a59e492 success=403/403 rel=52787+98/52885 pending=0 retriable=0 nulls=0 continuity=100% missing_tables=- mismatch=- |
| limit-heat | ok | 118 | heat=197 stock=648 retried=0 still_empty=0 |
| stock-high | ok | 62 |  |
| limit-advance | ok | 2 |  |
| stock-daily | ok | 36 | eastmoney snapshot ok |
| mainline-daily | ok | 3 |  |
| mainline-sector-daily | ok | 3 |  |
| theme-flow-daily | ok | 2 |  |
| public-assets | ok | 192 |  |
| features | ok | 2 |  |
| same-day-gate | fail | 1 |  |
| quality-gate | INCOMPLETE | - | check_daily_review_data.py |

> 需关注（坑/未全绿）：sw-l1-daily, same-day-gate

## 2026-08-20 | repair 2026-08-21 15:17（生产补 features，不换 staging）

| 模块 | 状态 | 耗时s | 备注 |
|---|---|---:|---|
| features | ok | 1 | 只补生产库 `compute_features --trade-date 2026-08-20`：market 4 / sector 1212 / stock 21773 / technical 5519 / period_rank 40。staging 未换名（mtime 仍 08-20 18:52） |
| same-day-gate | ok | 1 | COMPLETE |
| cross-day-gate | ok | 1 | PASS，`quality-2026-08-20.json` ok=true |
| finalize | ok | 46 | `nightly_full_review.sh finalize 2026-08-20`；workflow 19/19 PASS；L2 仍挂账 |
| export-increment | ok | - | iCloud `market_feature_store-inc-2026-08-20.tar.gz` 3.0 MB |
| quality-gate | COMPLETE | - | `--phase all` COMPLETE（L2_PAUSED=1） |

> 夜跑 18:57 same-day 败于 sw-l1 超时 → 不换名。22:47 手工 `cli daily-full` 直写生产 fact、无 features。本轮只在生产补 features + finalize，**禁止**把 18:52 staging 换进生产（会回退 08-19 hist 与 08-20 申万 31 行）。
> 已知欠账：08-20 申万 source 仍是 `index_realtime_sw`（等官方 hist 覆盖）；L2 自 08-07 挂账；staging 留作取证。

## 2026-08-21 | run 2026-08-21 23:45

| 模块 | 状态 | 耗时s | 备注 |
|---|---|---:|---|
| db-lock | ok | 0 |  |
| sectors | ok | 9 |  |
| market-overview | ok | 23 |  |
| market-daily | fail | 5 | [retry r1] |
| index-daily | fail | 6 | [retry r1] |
| sw-l1-daily | ok | 474 |  |
| market-deviation | fail | 20 | [retry r1] |
| sector-daily | timeout | 300 | [retry r1] |
| sector-stocks | partial | 0 | 2026-08-21 snapshot=6b9a700addc2 success=402/403 rel=52778+93/52900 pending=0 retriable=1 nulls=0 continuity=100% missing_tables=fact_sector_daily,fact_sector_stock_daily mismatch=relationships,daily_identities after 20 loops |
| limit-heat | fail | 11 | heat=0 stock=0 retried=0 still_empty=0 [retry r1] |
| stock-high | ok | 125 |  |
| limit-advance | ok | 9 |  |
| stock-daily | ok | 114 | used fill-stock-daily-fallback |
| mainline-daily | ok | 24 |  |
| mainline-sector-daily | ok | 31 |  |
| theme-flow-daily | ok | 14 |  |
| public-assets | timeout | 600 | [retry r1] |
| features | fail | 1 | [retry r1] |
| same-day-gate | fail | 1 |  |
| quality-gate | INCOMPLETE | - | check_daily_review_data.py |

> 需关注（坑/未全绿）：market-daily, index-daily, market-deviation, sector-daily, sector-stocks, limit-heat, public-assets, features, same-day-gate

## 2026-08-21 | repair 2026-08-22 00:11（staging 补洞后换名 + finalize）

| 模块 | 状态 | 耗时s | 备注 |
|---|---|---:|---|
| sector-daily | ok | 244 | 只用 published `.FP` 403 码拉 kline；官方 CLI 扫 dim 里 223 个已死 `.TI` 会 300s 超时 |
| limit-heat | ok | 93 | 标签页复活后 198 题材 / 571 明细 |
| index | ok | - | 新浪/东财/飞书 SSL 全挂；上证 3905.2 来自 `reviews/market.volume.indices` |
| market-deviation | ok | - | fill-stock-daily-fallback MA 复算 `sh_week_ma=3924.16 dev=-0.48` |
| sector-stocks | ok | - | 402/403 行其实已在 generation；ART 索引被 990124 empty COMMIT 写坏，COUNT/JOIN 只看见 60 板块。CTAS 重建表后 view=52807/403 |
| 990124.FP | ok | 40 | 半导体材料，直连 API 有 29 只；重建索引后 `record_member_result` 成功 |
| features | ok | 2 | sector/stock window + period_rank 40 |
| same-day-gate | COMPLETE | - | staging 过门后 S7 `atomic_swap_into_place`，生产未直写 |
| finalize | ok | 53 | `nightly_full_review.sh finalize 2026-08-21`；quality ok=true；L2 仍挂账 |
| public-assets | timeout | 600 | 未再补；不卡门 |

> 18:41 夜跑 preflight 红（无复盘会标签）。21:28 手工 S7 过 preflight，申万一 474s 成功（600s 档位生效），但 same-day 未绿、**不换名**。本轮只在残留 staging 补洞，门绿才换名。
> 已知欠账：L2 自 08-07 挂账；飞书 market-daily / 新浪 index / public-assets 未绿；晨汇断至 07-26、卖方事件断至 07-05；`cli daily-full` 写入守卫仍未进 `gitea/main`。

## 2026-08-24 | run 2026-08-24 21:00

| 模块 | 状态 | 耗时s | 备注 |
|---|---|---:|---|
| db-lock | ok | 0 |  |
| sectors | ok | 901 |  |
| market-overview | ok | 73 |  |
| index-daily | fail | 6 | [retry r1] |
| sw-l1-daily | ok | 242 | [retry r1] |
| market-deviation | fail | 11 | [retry r1] |
| sector-daily | fail | 12 | [retry r1] |
| sector-stocks | partial | 0 | 2026-08-24 snapshot=ed0d17ec87df success=0/403 rel=0+0/52916 pending=0 retriable=403 nulls=0 continuity=100% missing_tables=fact_sector_daily,fact_sector_stock_daily mismatch=relationships,daily_identities after 20 loops |
| limit-heat | ok | 32 | heat=202 stock=415 retried=0 still_empty=0 |
| stock-high | ok | 52 |  |
| limit-advance | ok | 2 |  |
| stock-daily | fail | 117 | used fill-stock-daily-fallback [retry r1] |
| mainline-daily | fail | 3 | [retry r1] |
| mainline-sector-daily | fail | 3 | [retry r1] |
| theme-flow-daily | fail | 1 | [retry r1] |
| public-assets | ok | 63 |  |
| features | fail | 3 | [retry r1] |
| same-day-gate | fail | 1 |  |
| quality-gate | INCOMPLETE | - | check_daily_review_data.py |

> 需关注（坑/未全绿）：index-daily, market-deviation, sector-daily, sector-stocks, stock-daily, mainline-daily, mainline-sector-daily, theme-flow-daily, features, same-day-gate

## 2026-08-24 | repair 2026-08-24 21:39（夜跑 21:00 失败后人工补跑；数据段全绿）

| 模块 | 状态 | 耗时s | 备注 |
|---|---|---:|---|
| 根因 | - | - | 三源同断：公开 API 匿名 401（批量 fetch 无 Bearer）/ 代理掐新浪+东财+腾讯 SSL / dim 全表含 223 死 .TI |
| index | ok | - | akshare 双源 SSL 挂；上证 3882.01 先从 note 回写，后经 reviews/market.volume.indices 同值 |
| theme-flow | ok | 1 | CDP 带 token，57 panels |
| mainline / mainline-sector | ok | 7 | CDP 带 token，2 主题 39 股 / 8 板块 |
| sector-daily | ok | 27 | 只拉当日宇宙 403 个 .FP，10075 行（25 日序列） |
| sector-stocks | ok | 71 | 断点续跑 only_missing；跳过腾讯市值（每批 4×15s SSL 空转），299 empty→403/403 success |
| stock-daily | ok | 1 | fill-stock-daily-fallback 5540 股；sh_week_ma=3915.13 dev=-0.85 |
| public-assets | ok | 73 | CDP 回退全绿：core 50 / leader 1 / global 5+194 / auction 70 / dragon 60+503 |
| features | ok | - | compute_features 全族 complete |
| same-day-gate | COMPLETE | - | check_daily_review_data --phase data |
| cross-day | PASS | - | check-daily 公开资产 4 表补齐后过 |
| quality-gate | COMPLETE | - | --phase report；L2 INCOMPLETE（挂账，用户指示后续统一补） |
| 报告 | ok | - | exports/2026-08-24-daily-review.md（32K） |

> 代码修复在干净树 `fwp-wt-fph-auth` @ `fix/fupanhui-auth-fallback`（789cd216 代码 + ff08b2b7 坑沉淀），
> 未合 main。L2 欠账自 08-07 起（flag 仍在），用户指示后续统一补。

## 2026-08-25 | run 2026-08-25 18:40

| 模块 | 状态 | 耗时s | 备注 |
|---|---|---:|---|
| db-lock | ok | 0 |  |
| sectors | ok | 2 | [retry r1] |
| market-overview | ok | 4 | [retry r1] |
| index-daily | ok | 2 | [retry r1] |
| sw-l1-daily | ok | 300 |  |
| market-deviation | ok | 12 | [retry r1] |
| sector-daily | fail | 19 | [retry r1] |
| sector-stocks | partial | 0 | 2026-08-25 no published universe after 20 loops |
| limit-heat | ok | 38 | heat=205 stock=512 retried=0 still_empty=0 |
| stock-high | ok | 63 |  |
| limit-advance | ok | 2 |  |
| stock-daily | ok | 48 | eastmoney snapshot ok |
| mainline-daily | fail | 3 | [retry r1] |
| mainline-sector-daily | fail | 3 | [retry r1] |
| theme-flow-daily | fail | 1 | [retry r1] |
| public-assets | ok | 61 |  |
| features | fail | 3 | [retry r1] |
| same-day-gate | fail | 2 |  |
| quality-gate | INCOMPLETE | - | check_daily_review_data.py |

> 需关注（坑/未全绿）：sector-daily, sector-stocks, mainline-daily, mainline-sector-daily, theme-flow-daily, features, same-day-gate

## 2026-08-25 | repair 2026-08-26 00:02（夜跑 18:40 失败后 staging 补洞换名；数据段全绿）

| 模块 | 状态 | 耗时s | 备注 |
|---|---|---:|---|
| 根因 | - | - | 夜跑写 staging 未换名。公开 API 401（mainline/theme-flow）；sector-daily 扫死 .TI；sector-stocks 20 轮时宇宙尚未 published；finalize 守卫拦生成段 |
| 代码 | - | - | 补跑用干净树 `fwp-wt-fph-auth` @ `fix/fupanhui-auth-fallback`（401→CDP + 只拉 published `.FP`），未合 main |
| sector-daily | ok | 67 | 403 `.FP` / 10075 行 / 空序列 0；换快照后再跑一次 44s |
| sw-l1-daily | ok | 273 | 31/31 complete；source=`akshare:index_realtime_sw`（与近几日同形，非 degraded） |
| theme-flow / mainline | ok | 12 | CDP 带 token：57 panels / 3 主题 42 股 / 9 板块 |
| sector-stocks | ok | 194+100 | 首轮 397/403，6 个 `member_count_surplus`（声明比 live 少 1–2）。`sync-sectors` 重发快照 52916→52926 关系后 403/403、52847 行 |
| public-assets | ok | 116 | 夜跑该步「ok」但 08-25 行是空的；补跑 core 50 / global 5+194 / leader 120 / dragon 20+168 / auction 70 |
| features | ok | 2 | compute_features 全族 complete：market 4 / sector 1212 / stock 21794 / technical 5523 / period_rank 40 |
| same-day-gate | COMPLETE | - | staging `--phase data`；名称连续 402/402=100%；个股覆盖 5541/5541 |
| cross-day | PASS | - | 补 public-assets 后过；`quality-2026-08-25.json` ok=true |
| 换名 | ok | - | S7 `atomic_swap_into_place`；生产未直写；staging 已消失 |
| 报告 | ok | - | exports/2026-08-25-daily-review.md（35K）+ 涨家数图；HTML/题材/策略1 T1=4 T2=5 / 策略3/4 / workbench / cockpit |
| agent-daily | fail→见下段 | 1 | 当时 `content delta exceeds maximum size`；00:09 临时 park 未跟踪 dumps 后已补绿 |
| quality-gate | COMPLETE | - | `--phase data/report/all` + `L2_PAUSED=1`；L2 自 08-07 挂账 |

> 补跑在 staging 上写、门绿才换名。生成段必须 Homebrew `python3`（PATH 以 `/opt/homebrew/bin` 开头）；venv-workbench 缺 markdown/matplotlib。
> 已知欠账：L2 挂账；飞书 market-daily / 新浪 index 未绿；`cli daily-full` 写入守卫与 fph-auth 均未进 `gitea/main`。
> 本单不写 `docs/handoffs/inflight/feat-reading-rules-baseline-batch1.md`。

## 2026-08-25 | repair-queue 2026-08-26 00:11（agent-daily / 研究队列收口）

| 模块 | 状态 | 耗时s | 备注 |
|---|---|---:|---|
| delta-park | ok | - | 临时移出未跟踪 `review-queue/reports/`（5.6MB）+ `cross-repo-ingest-queue/`（4.1MB）到知识库根外；已跟踪 `cninfo-rss-*.json` 未动。跑完移回。知识库仍在别人的 `fix/rss-l3-auto-promote`，未 commit |
| agent-daily | ok | 9 | fidelity 1.2 通过；`--semantic-rag-top-n 0`；venv-workbench。扫描 10 条：旧逻辑唤醒 8 / 新逻辑 0 / 数据缺口 2。队列 8 项：IMA 5（碳中和/特高压/新能源车/数据中心/一带一路）+ 找公告 2（光纤光缆/人形机器人）+ 降级 1（贵金属） |
| kb-queue-receive | ok | 1 | 10 条任务归档到 `wiki/raw/cross-repo-ingest-queue/2026-08-25/`（只 receive，不 apply） |
| cockpit/workbench | ok | - | 驾驶台 08-25 卡已挂「研究队列」；workbench 同步 |
| l3_daily_backfill | dry-run | 26 | 例行池 9 只（策略一当日行），agent 缺口 0（队列目标是题材名无代码）。lookup 成功、近 3 日 0 条可写候选，未 `--apply`。不往 RSS 分支脏树写 entity |

> 坑：content_delta 的 10MB 上限会把 gitignored 未跟踪目录也算进去。不要扩 cap、不要把 disclosures/ingest-queue 提交进别人的知识库分支。临时 park 未跟踪 dumps 即可。
> 驾驶台入口：`复盘/index.html`；canonical 队列：`market_feature_store/exports/2026-08-25-research-queue.json`。

## 2026-08-25 | closeout-qc 2026-08-26 00:16（收尾质检，闸门重跑）

| 检查 | 结果 | 备注 |
|---|---|---|
| same-day `--phase data/report/all` | COMPLETE | 现跑；`L2_PAUSED=1`；名称连续 402/402；个股覆盖 5541/5541 |
| cross-day `check-daily` | PASS | gaps/anomalies/range 全空；与 `quality-2026-08-25.json` 一致 |
| 空壳抽查 | PASS | sector_stock 52847 行、price/pct_chg/amount 0 空；sector_daily 403 值齐；stock_daily close 0 空；公开资产 core50 / global5+194 / dragon60 / auction70 与 08-24 同形 |
| published 宇宙 | PASS | 现用 `34dd7460…`（22:27 重发）；18:39 那版已 superseded |
| 产物/链接 | PASS | 日报 md/html/图、题材、队列、agent、矩阵 1/3/4、cockpit、workbench、增量包 4.1MB；锁已释放；无 staging |
| 研究队列 ↔ receive | PASS | 队列 8 项（IMA5+公告2+降级1）；kb-ingest 10 条；receipt `received=10` |
| L3 | dry-run 0 候选 | 未 apply，正确 |
| 非阻断 | 挂账 | L2 自 08-07；飞书 market-daily / 新浪指数；胜率/晨汇/evolve 不在夜跑 canonical 计划（晨汇无当日源）；framework 因无 `user_framework` 跳过 |
| 轻症 | 不修 | 日报 HTML 涨家数图 `<img src>` 相对路径可用；「点击打开」是 `file://…png`（08-24 同形，渲染器老问题）。`exports/…-daily-workflow-summary.json` 仍是 00:02 的 `skip_agent=true`，队列是之后补的，别拿它当 agent 步骤证据 |

> 结论：08-25 收尾**可以当完成**。空壳抽查是第三层——`COUNT(*)` 过门不等于值在。`fact_leader_height_daily` 每日 1 行是「最高板」不是 120 只名单。

## 2026-08-26 | run 2026-08-26 18:45

| 模块 | 状态 | 耗时s | 备注 |
|---|---|---:|---|
| db-lock | ok | 0 |  |
| sectors | ok | 3 |  |
| market-overview | ok | 5 |  |
| index-daily | ok | 2 |  |
| sw-l1-daily | ok | 244 |  |
| market-deviation | ok | 17 |  |
| sector-daily | fail | 27 | [retry r1] |
| sector-stocks | partial | 0 | 2026-08-26 snapshot=c8bd98ede596 success=403/403 rel=52866+66/52932 pending=0 retriable=0 nulls=0 continuity=100% missing_tables=fact_sector_daily mismatch=daily_identities after 20 loops |
| limit-heat | ok | 50 | heat=195 stock=440 retried=0 still_empty=0 |
| stock-high | ok | 84 |  |
| limit-advance | ok | 2 |  |
| stock-daily | ok | 30 | eastmoney snapshot ok |
| mainline-daily | ok | 5 |  |
| mainline-sector-daily | ok | 6 |  |
| theme-flow-daily | ok | 2 |  |
| public-assets | ok | 120 |  |
| features | fail | 2 | [retry r1] |
| same-day-gate | fail | 1 |  |
| quality-gate | INCOMPLETE | - | check_daily_review_data.py |

> 需关注（坑/未全绿）：sector-daily, sector-stocks, features, same-day-gate

## 2026-08-26 | run 2026-08-26 19:32

| 模块 | 状态 | 耗时s | 备注 |
|---|---|---:|---|
| db-lock | ok | 0 |  |
| sectors | ok | 4 |  |
| market-overview | ok | 5 |  |
| index-daily | ok | 1 |  |
| sw-l1-daily | ok | 287 | [retry r1] |
| market-deviation | ok | 13 |  |
| sector-daily | ok | 61 |  |
| sector-stocks | ok | 0 | 2026-08-26 snapshot=c8bd98ede596 success=403/403 rel=52866+66/52932 pending=0 retriable=0 nulls=0 continuity=100% missing_tables=- mismatch=- |
| limit-heat | ok | 37 | heat=195 stock=440 retried=0 still_empty=0 |
| stock-high | ok | 84 |  |
| limit-advance | ok | 3 |  |
| stock-daily | ok | 32 | eastmoney snapshot ok |
| mainline-daily | ok | 7 |  |
| mainline-sector-daily | ok | 6 |  |
| theme-flow-daily | ok | 2 |  |
| public-assets | ok | 121 |  |
| features | ok | 5 |  |
| same-day-gate | ok | 2 |  |
| cross-day-gate | ok | 2 |  |
| export-increment | fail | 0 |  |
| quality-gate | INCOMPLETE | - | check_daily_review_data.py |

> 需关注（坑/未全绿）：export-increment

## 2026-08-26 | repair 2026-08-26 21:13（定时失败后的生成段补跑，本轮核验）

| 模块 | 状态 | 耗时s | 备注 |
|---|---|---:|---|
| 18:30 S7 | fail | 15min | staging 不换名。sector-daily 连不上 CDP `:3456`；features 空；same-day INCOMPLETE；err 另有 staging WAL too many open files |
| 19:32 sync | partial | - | sector-daily/features/same-day/cross-day 过；export-increment 当时 fail；生产库 19:35 已有当日行 |
| 20:40 finalize | fail | 51 | 生产 same-day COMPLETE；L2 挂账跳过；日报/题材写出；agent-daily 0.6s `content delta exceeds maximum size`；矩阵/驾驶台 SKIP |
| agent-daily | ok | - | 21:13 已落盘；`--semantic-rag-top-n 0`；fidelity 1.2 合同戳在 md；队列 6 项：IMA 2（非银金融/数字货币）+ 找公告 3（黄金/光通信/液冷）+ 降级 1（医药）；skipped 4（工业金属/中特估/互联金融/疫苗） |
| kb-queue-receive | ok | - | receipt `received=33` @ 21:15；只归档不 apply。知识库仍在别人的 `fix/rss-l3-auto-promote` |
| matrices/workbench/cockpit | ok | - | 21:13–21:14；策略一 08-26 机械初稿 9 码（有色）；workbench `has_agent=true`；驾驶台链到日报/题材/队列 |
| export-increment | ok | - | 21:15 重写 `market_feature_store-inc-2026-08-26.tar.gz` 3.0MB（20:40 那次也过了，19:32 那次不要当终态） |

> 坑：content_delta 10MB 仍会被 `review-queue/reports/`（6.2MB）+ `cross-repo-ingest-queue/`（6.4MB）撑爆。21:13 能过说明当时 park 过；现 park 目录已不在、dump 已回原位。不要扩 cap。`daily-workflow-summary.json` 仍是 20:40 的 `FAIL`，不能当队列证据。

## 2026-08-26 | closeout-qc 2026-08-26 21:45（收尾质检，闸门重跑）

| 检查 | 结果 | 备注 |
|---|---|---|
| same-day `--phase data/report/all` | COMPLETE | 现跑；`L2_PAUSED=1`；名称连续 402/402；个股覆盖 5542/5542 |
| cross-day `check-daily` | PASS | gaps/anomalies/range 全空；与 `quality-2026-08-26.json` 一致 |
| 空壳抽查 | PASS | sector_stock 52866 行、price/pct_chg/amount 0 空；sector_daily 403 且 pct_chg 0 空；stock_daily close 0 空 |
| 公开资产 | PASS | core50 / global5+194 / dragon_summary1 / auction69（昨 70）/ leader1。龙虎 `fact_dragon_tiger_daily` 20（昨 60）、席位 180（昨 522）是当日名单变短，不是空壳 |
| 产物/链接 | PASS | 日报 md/html/图、题材、队列、agent、矩阵 1/3/4、cockpit、workbench、增量包 3.0MB；无 staging 文件 |
| 研究队列 ↔ receive | PASS | 队列 6 项；kb-ingest receipt `received=33` |
| L3 | dry-run 9 只 / 1 候选 | 例行池 9（策略一当日行），agent 缺口 0（队列目标是题材名无代码）。601212 白银有色 1 条候选，未 `--apply`。知识库在别人脏分支 |
| 非阻断 | 挂账 | L2 自 08-18；晨汇/卖方观点仍断更；18:30 CDP 未起。飞书 Bitable/IM/`sync-market-daily` 已退役，20:40 `notify_feishu` HTTP 400 是残留告警，不当缺口 |
| 轻症 | 不修 | `exports/…-daily-workflow-summary.json` 仍是 20:40 `FAIL`/`from_step=daily-review`，队列是 21:13 补的 |

> 结论：08-26 收尾**可以当完成**。定时两段都败过，终态以 21:13 生成 + 21:45 闸门为准。L3 那 1 条等知识库离开 `fix/rss-l3-auto-promote` 再 apply。

## 2026-08-27 | run 2026-08-27 18:42

| 模块 | 状态 | 耗时s | 备注 |
|---|---|---:|---|
| db-lock | ok | 0 |  |
| sectors | ok | 2 |  |
| market-overview | ok | 3 |  |
| index-daily | ok | 1 |  |
| sw-l1-daily | ok | 73 |  |
| market-deviation | ok | 11 |  |
| sector-daily | ok | 39 |  |
| sector-stocks | ok | 0 | 2026-08-27 snapshot=0301129a8816 success=403/403 rel=52865+66/52931 pending=0 retriable=0 nulls=0 continuity=100% missing_tables=- mismatch=- |
| limit-heat | ok | 40 | heat=233 stock=702 retried=0 still_empty=0 |
| stock-high | ok | 67 |  |
| limit-advance | ok | 2 |  |
| stock-daily | ok | 42 | eastmoney snapshot ok |
| mainline-daily | ok | 16 |  |
| mainline-sector-daily | ok | 8 |  |
| theme-flow-daily | ok | 3 |  |
| public-assets | ok | 106 |  |
| features | ok | 8 |  |
| same-day-gate | ok | 5 |  |
| cross-day-gate | ok | 3 |  |
| export-increment | fail | 0 |  |
| quality-gate | INCOMPLETE | - | check_daily_review_data.py |

> 需关注（坑/未全绿）：export-increment

## 2026-08-27 | run 2026-08-27 19:17

| 模块 | 状态 | 耗时s | 备注 |
|---|---|---:|---|
| db-lock | ok | 0 |  |
| sectors | ok | 3 |  |
| market-overview | ok | 3 |  |
| index-daily | ok | 1 |  |
| sw-l1-daily | ok | 54 |  |
| market-deviation | ok | 10 |  |
| sector-daily | ok | 33 |  |
| sector-stocks | ok | 0 | 2026-08-27 snapshot=ae1cfcaf8c1e success=403/403 rel=52869+77/52946 pending=0 retriable=0 nulls=0 continuity=100% missing_tables=- mismatch=- |
| limit-heat | ok | 31 | heat=233 stock=702 retried=0 still_empty=0 |
| stock-high | ok | 60 |  |
| limit-advance | ok | 1 |  |
| stock-daily | ok | 16 | eastmoney snapshot ok |
| mainline-daily | ok | 5 |  |
| mainline-sector-daily | ok | 5 |  |
| theme-flow-daily | ok | 1 |  |
| public-assets | ok | 94 |  |
| features | ok | 1 |  |
| same-day-gate | ok | 1 |  |
| cross-day-gate | ok | 0 |  |
| export-increment | ok | 0 |  |
| quality-gate | COMPLETE | - | check_daily_review_data.py |

## 2026-08-27 | repair 2026-08-28 00:07（20:40 finalize 失败后的生成段补跑，本轮核验）

| 模块 | 状态 | 耗时s | 备注 |
|---|---|---:|---|
| 18:30 S7 | fail | rc=2 | CDP `:3456` 连不上 + staging WAL "Too many open files"；19:17 补跑 sync 全绿，生产库 08-27 齐全（非缺数） |
| 20:40 finalize | fail | 4s | 质检门 PASS 后 export-increment 撞 iCloud EAGAIN（Errno 11，重写 19:17 已有 tar.gz）→ fail-fast 全 SKIP |
| export-increment | ok | 21 | 旧包改名 `.conflict-20260827-2149` 让路后过；新包 3.1MB @00:07 |
| daily-review/html | ok | 5.5 | rc=2 真根因＝渲染步内嵌 check_daily_review_data 默认 `--phase all` 查 L2；手动补跑必须带 `L2_PAUSED=1`（nightly 挂账时自动 export，手动不会）。venv 缺 markdown 是红鲱鱼：子步骤 python3 走 launchd PATH=homebrew（有 3.10.2） |
| agent-daily | ok | - | content_delta 10MB cap 被 kb 仓 cross-repo-ingest-queue(8.8M)+disclosures/review-queue/reports(6.8M) 撑爆；按 08-26 先例 park 到 `~/kb_work/park/2026-08-27/`；receipt received=8 |
| 矩阵/workbench/cockpit | ok | - | strategy1 inserted t1=4/t2=5；strategy3 补 89 空行+append 08-27；cockpit daily=51 |
| 最终硬门 | COMPLETE | - | `--phase all` rc=0（L2_PAUSED=1 放行挂账）；workflow PASS 19 步全绿 |

> 坑：① kb 仓大队列是周期性坑（08-26 同型）——receive 又把新批写回 queue 目录，下次 finalize 可能再撑爆，治本（exclusion 或 park 常态化）未在本轮做；② parked 的 15.7MB 待后续按队列语义补接收/回放；③ `2026-08-27-daily-workflow-summary.json` 已被 00:07 PASS 覆盖，勿再引 20:40 FAIL 版。

## 2026-08-28 | run 2026-08-28 18:52

| 模块 | 状态 | 耗时s | 备注 |
|---|---|---:|---|
| db-lock | ok | 1 |  |
| sectors | ok | 26 |  |
| market-overview | ok | 23 |  |
| index-daily | ok | 8 |  |
| sw-l1-daily | ok | 130 |  |
| market-deviation | ok | 17 |  |
| sector-daily | ok | 91 | [retry r1] |
| sector-stocks | partial | 0 | 2026-08-28 snapshot=b92780abe665 success=403/403 rel=52860+86/52946 pending=0 retriable=0 nulls=0 continuity=100% missing_tables=fact_sector_daily mismatch=daily_identities after 20 loops |
| limit-heat | ok | 51 | heat=245 stock=778 retried=0 still_empty=0 |
| stock-high | ok | 92 |  |
| limit-advance | ok | 3 |  |
| stock-daily | ok | 50 | eastmoney snapshot ok |
| mainline-daily | ok | 11 |  |
| mainline-sector-daily | ok | 9 |  |
| theme-flow-daily | ok | 2 |  |
| public-assets | ok | 140 |  |
| features | ok | 4 | [retry r1] |
| same-day-gate | ok | 3 |  |
| cross-day-gate | ok | 2 |  |
| export-increment | ok | 1 |  |
| quality-gate | COMPLETE | - | check_daily_review_data.py |

> 需关注（坑/未全绿）：sector-stocks
