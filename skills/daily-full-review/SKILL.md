---
name: daily-full-review
description: 单日全量复盘的同步编排与防坑流程。触发词：今日全量复盘、单日复盘、跑一下今天的复盘、补全今天的复盘数据、daily full review、复盘同步卡住了。用于把某个交易日的 market_feature_store 同步按"已验证的模块顺序 + 逐模块超时 + 自动兜底 + 经验记录"跑完，再交给 intelligence.cli daily 生成日报/题材/HTML/工作台。专治 daily-update monolith 静默挂起后乱手搓的问题。
---

# 单日全量复盘（Daily Full Review）

## 这个 skill 存在的理由（必须先读）

`python3 -m intelligence.cli daily` 内部第一步是 monolith `daily-update`
（`market_feature_store/sync/sync_daily_full.py:run_daily_update`），它把全部同步
模块串在一个进程里。**只要其中任意一个重模块（sector-stocks / limit-heat /
stock-daily）静默挂起，整个 daily 就卡死且无进度输出。**

历史教训（2026-06-16）：monolith 卡住后，没有切到已验证的"按模块逐个跑 + 兜底
脚本"路径，而是临时手搓 inline 批次，导致：
1. 没按已验证脚本回填（该用 `backfill_review_hot_data.py` / 逐模块 CLI / fallback）。
2. 没分模块批量回填，反复在同一种卡法上重试。
3. 没记录经验，下次还会踩同样的坑。

**本 skill = 限制提示词 + 模块化批量同步脚本 + runlog 经验记录。**

## 硬性限制提示词（每次开工前默念）

- **禁止手搓 inline 批次**：所有同步只能走 `python3 -m market_feature_store.cli <sync-*>`
  或本 skill 的 `scripts/run_review_sync.py`，不允许临时写 SQL/heredoc 凑数。
- **逐模块隔离 + 超时**：每个模块单独子进程跑，带超时；一个挂了不拖死整轮。
- **静默挂起即停**：模块无输出且 CPU≈0 约 2 分钟 → 终止，按下表走兜底路径，
  不要盲目重试同一条命令。
- **重模块先看进度**：`limit-heat` 必须能看到 `[limit-heat] detail chunk i/N` 进度；
  看不到就是被 PIPE 吞了，改成直跑（继承 stdout）。
- **每模块审计**：写完用 `check_daily_review_data.py` 或行数查询确认，再进下一模块。
- **每轮必记 runlog**：跑完把每个模块的 状态/耗时/走了哪条路径 追加到
  `state/runlog.md`，顺的路径记住，坑的路径下次规避。

## Git 安全

开工先报告：

```bash
git status --short
git branch --show-current
```

不要 `git add .`。复盘产物（`market_feature_store/exports/*`、`复盘/daily/*`、
矩阵 HTML）和 DuckDB 本地状态与源码改动分开提交。

## 标准编排：单日全量复盘

### 一键入口（推荐）

```bash
python3 skills/daily-full-review/scripts/run_review_sync.py --date YYYY-MM-DD
```

脚本按下面的"已验证模块顺序"逐个跑，逐模块超时 + 自动兜底 + 写 runlog。
同步全绿后再跑生成段：

```bash
python3 -m intelligence.cli daily --date YYYY-MM-DD --skip-sync --from-step daily-review \
  --summary-json market_feature_store/exports/YYYY-MM-DD-daily-workflow-summary.json
```

### 已验证模块顺序与兜底（核心知识）

顺序对齐 `run_daily_update`，但拆成可隔离、可续跑的模块：

| 阶段 | 模块 | 已验证命令 | 卡住兜底 |
|---|---|---|---|
| 0 预检 | db-lock | `python3 scripts/check_db_lock.py` | 有锁先查占用进程，勿强删库 |
| 1 轻 | sectors | `sync-sectors --trade-date D` | 一般不卡 |
| 1 轻 | market-overview | `sync-market-overview --trade-date D --days 60` | CDP 500 重试 |
| 1 轻 | market-daily | `sync-market-daily` | 飞书表，少卡 |
| 1 轻 | index-daily | `sync-index-daily --trade-date D` | AkShare，少卡 |
| 1 轻 | sw-l1-daily | `sync-sw-l1-daily --trade-date D --days 20` | 少卡 |
| 1 轻 | market-deviation | `sync-market-deviation --trade-date D` | 缺则日报偏离度占位 |
| 1 轻 | sector-daily | `sync-sector-daily --trade-date D --days 25` | CDP 500 重试 |
| 2 重 | sector-stocks | 循环 `sync-sector-stocks --trade-date D --limit 20 --sleep 0.05` 直到 `count(distinct sector_ts_code) >= dim_sector` | 默认跳过已抓板块，可续跑；逐批超时后直接续下一批 |
| 2 重 | limit-heat | **直跑** `sync-limit-heat --trade-date D --detail-chunk 6 --sleep 0.05`（看 chunk 进度） | 写完若有题材"有涨停但明细为空"，逐个 `--sector <题材> --detail-chunk 1` 重试 |
| 2 重 | stock-high | `sync-stock-high --trade-date D --page-size 200` | 个别日期会挂，超时则记 skip |
| 2 重 | limit-advance | `sync-limit-advance --trade-date D --min-boards 2` | 少卡 |
| 3 兜底 | stock-daily | 先 `sync-stock-daily --start-date D --offset 5 --timeout 10 --progress-every 500` | **超时/失败 → `fill-stock-daily-fallback --trade-date D`**（用 sector_stock 聚合，已验证当日可用） |
| 4 轻 | sector-resonance | `sync-sector-resonance` | 飞书 checkbox，少卡 |
| 5 审计 | quality-gate | `python3 scripts/check_daily_review_data.py D` | 必须 RESULT: COMPLETE |

### 关键防坑点（顺/坑 速查）

- **limit-heat 被 PIPE 吞进度 = 看起来挂死**：通过子脚本 `backfill_review_hot_data.py`
  跑时 stdout 被 PIPE 缓冲，看不到 chunk 进度会误判挂起。**直跑 `sync-limit-heat`
  继承 stdout** 就能看到 `detail chunk i/N`，2026-06-16 验证 25 个 chunk 顺利跑完。
- **limit-heat 个别题材失败**：整体跑完会打印 `失败 N: code/题材`（如 储能/机器人概念/
  军工）。逐个 `--sector <题材> --detail-chunk 1` 重试即可补齐明细，避免质检报
  "有涨停但明细为空"。
- **stock-daily 会静默挂（mootdx 全 A）**：低 CPU 且持 DB 写锁。别死等，**直接切
  `fill-stock-daily-fallback`**，当日用 `fact_sector_stock_daily` 聚合补，并复算上证
  周均线/偏离度。
- **sector-stocks 逐板块提交**：默认跳过已抓板块，超时杀掉再跑会从断点续，安全。
  用 `count(distinct sector_ts_code)` vs `dim_sector` 判断完成度。
- **strategy1 矩阵不要喂 evolution record**：那是另一个流程的坑。策略一走
  `skills/strategy1-matrix`，本 skill 只管同步段。

## 生成段与矩阵段（同步全绿后）

1. 生成：`intelligence.cli daily --skip-sync --from-step daily-review`（见上）。
2. 策略记录：`python3 scripts/evolve.py generate --date D`。
3. 策略一矩阵：走 `skills/strategy1-matrix`（事实层 → row JSON → update_matrix.py，
   先 `--dry-run`）。
4. 其余矩阵按需：`render_strategy4_dual_engine_matrix.py`、`backfill_strategy3_touch_matrix.py` 等。

## 迭代规则

每次单日复盘后：

- 把本轮每模块 状态/耗时/路径 追加到 `state/runlog.md`（脚本自动写，人工可补注释）。
- 如果某模块用了新的兜底或踩了新坑，**立即更新本 SKILL.md 的"顺/坑 速查"表**，
  再继续，让下次少踩坑。
