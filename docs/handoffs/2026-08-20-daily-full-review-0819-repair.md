# 2026-08-20 收口：08-19 全量复盘补洞 + 双盲夜跑退役

提交分支：`chore/retire-dual-blind-nightly`（从 `gitea/main` 长出）。主仓脏树 `feat/reading-rules-baseline-batch1` 未碰其 inflight、未在那棵树上提交。未合 main、未 push。

## 结论

08-19 生产库与日报已齐；独立复跑闸门 **PASS**。双盲答卷已从夜跑拆掉，今晚 20:40 finalize 不会再调 recheck/auto_verdict。

## 独立质检（2026-08-20 10:37，不凭记忆）

| 检查 | 结果 |
|------|------|
| `check_daily_review_data.py 2026-08-19 --phase data` | COMPLETE rc=0 |
| 同上 `--phase all` + `L2_PAUSED=1` | COMPLETE rc=0（L2 挂账跳过） |
| `cli check-daily --trade-date 2026-08-19` | PASS，`calendar_gaps` 空 |
| `quality-2026-08-19.json` | `ok=true`，gaps/anomalies 空 |
| workflow `2026-08-19-daily-workflow-summary.json` | `PASS` 19/19，无 FAIL |
| `fact_market_daily` max | 2026-08-19；08-20 仍 0 行（盘中，预期） |
| `fact_sw_l1_daily` 08-19 | 31/31，无 null、无 `degraded`；source 全是 `…:prev_close`；amount **31/31 等于 08-18**（占位）；close 31/31 与 08-18 不同 |
| `fact_dragon_summary_daily` 08-19 | 1 行，74 只上榜，source=`fupanhui:public-api/data/dragon/all` |
| public-assets | core 50 / global 5+194 / leader 1 / tiger 74 / seat 675 / summary 1 |
| 板块名连续性 | 401/402=99.75%，缺「半导体封测」（过 95% 门，与夜跑诊断一致） |
| L2 | `l2-paused.flag` 仍在；两张 feature 表 max=08-07 |
| 报告 | `复盘/daily/2026-08-19/` 6 文件，mtime 10:29–10:30 |
| 增量包 | iCloud `market_feature_store-inc-2026-08-19.tar.gz` 3.0 MB |
| 换名备份 | `db/market_feature_store.duckdb.pre-0819-swap` 仍在（gitignore，COW） |
| staging | 已不存在（换名后正常） |
| 双盲夜跑 | `~/.local/bin/nightly_full_review.sh` + 仓内源 + runtime 副本：无 python 调用，仅退役注释。launchd finalize 仍指向 `~/.local/bin` |

workflow 里的 `checkpoint-recheck` PASS 是 foresight 可证伪点回检，**不是**双盲答卷。

## 复验（2026-08-20 11:06）

闸门与抽查与 10:37 一致，无漂移：same-day data/all COMPLETE、cross-day PASS、申万 31/`prev_close`/amount=08-18、dragon_summary 74、public-assets 行数不变、08-20 仍 0 行、双盲三份脚本仍无 python 调用、inflight 未改。

## 发生了什么（给接手）

夜跑 08-19 18:30：S7 写 staging，same-day 败于申万一（两次 300s timeout）→ **不换名**。public-assets 当晚第一次真跑，但 `dragon_summary`/`regulation` 超时；summary 在 GAP 表里，即使补上 sw-l1 也会被 cross-day 拦住。20:40 finalize 读生产仍 08-18。

08-20 盘中：staging 补 sw-l1（官方 hist 当时 0 行 → `index_realtime_sw` **昨收盘**当 08-19 close，禁用最新价）+ dragon_summary → 双门绿 → `atomic_swap` 进生产 → finalize 10:30:43 完成。

## 已知欠账（别当今天的洞）

- **申万 amount 占位**：成交额复制 08-18。今晚 18:30 `--days 20` hist 有数应 ON CONFLICT 覆盖；届时抽查 `source` 不再含 `prev_close`。
- **regulation** 公开 API 仍超时；不进 GAP 门，未补。
- **L2** 自 08-07 挂账；鉴权恢复后按 `2026-08-18-daily-full-review-recovery.md` 回补。
- **板块** 缺「半导体封测」一名。
- **备份** `*.pre-0819-swap`：今晚夜跑顺利后再删。
- **编排债**（另开干净树）：sw-l1 timeout 300s 偏紧；public-assets 失败子任务应收尾重试。
- 仓外部署副本 `~/.local/bin/nightly_full_review.sh` 与 runtime 副本已拆线，不进本 commit。
- 主仓脏树上 08-17/08-18 `runlog` 段仍未提交（他人足迹），本 commit 只带 08-19。

## 本 commit 文件

`nightly_full_review.sh`、`ledger-map.md`、`runlog.md`（仅 08-19）、本文件、`2026-08-18-daily-full-review-recovery.md`（08-19 质检 + 收口，保留 main 上已有 Round 1/2）。

**不要动**：forecast-ledger 那批 `M`；`docs/handoffs/inflight/feat-reading-rules-baseline-batch1.md`。

## 工具沉淀

没有抽成新脚本。T+1 用昨收盘、S7 不换名是一次性运维。若申万 hist 再在 T+1 上午连续空两次，再把「昨收盘兜底 + source 标注」做成 sync 旁路，并加变异测试「禁止写最新价」。

## 下一步

1. 今晚看 18:30 S7 是否换名、sw-l1 `source` 是否被 hist 覆盖。
2. 合 main 等确认；本分支未 push。
3. L2 / regulation / 半导体封测 / 备份删除：按上面欠账，不堵今晚复盘。
