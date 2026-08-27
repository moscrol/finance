# 2026-08-26 收口：08-25 全量复盘补跑 + 研究队列 + skill 纠偏

主检出仍是别人的 `feat/reading-rules-baseline-batch1`（脏树，reading-rules **已弃用**）。**本单不写该 inflight，不在这 rebase / 不合 / 不 commit。** 活代码在 `/Users/a77/fwp-wt-reading-rules-baseline` @ `feat/reading-rules-baseline-r2`。

## 结论

08-25 **驾驶台可用**：数据换名进生产、生成段齐、研究队列 + kb receive 已落。00:16 闸门重跑 COMPLETE/PASS，空壳抽查无 NULL 行情。

入口：`复盘/index.html` → 08-25「研究队列」。Canonical：`market_feature_store/exports/2026-08-25-research-queue.json`（IMA 5 / 找公告 2 / 降级 1）。

## 发生了什么

夜跑 18:30 S7 写 staging，same-day 败（公开 API 401、sector-daily 扫死 `.TI`、成分股 20 轮时宇宙未 published）→ **不换名**。20:40 finalize 被守卫拦住。public-assets 步骤标 ok，当日行仍空。

补跑：staging 上用未合 main 的 `/Users/a77/fwp-wt-fph-auth` @ `fix/fupanhui-auth-fallback` 补洞 → 门绿 → `atomic_swap`。成分首轮 397/403 是 `member_count_surplus`：`sync-sectors` 重发快照后再跑 daily **和** stocks。

生成段必须 PATH 以 `/opt/homebrew/bin` 开头（venv 无 markdown/matplotlib）。`agent-daily` 先被 wiki 脏区撑破 content-delta 10MB；临时移出未跟踪 `review-queue/reports/` + `cross-repo-ingest-queue/`（不动已跟踪 rss json）后 9s 出队列，fidelity 1.2 过。知识库在 `fix/rss-l3-auto-promote`，只 receive 不 apply。L3 dry-run 9 只 / 0 候选。

## 独立质检（2026-08-26 00:16，生产库）

| 检查 | 结果 |
|------|------|
| `--phase data/report/all` + `L2_PAUSED=1` | COMPLETE；402/402 名称；5541/5541 个股 |
| `check-daily` | PASS，gaps 空 |
| 空壳 | sector_stock 52847，price/pct/amount 0 空；板块 403 值齐 |
| 公开资产 vs 08-24 | core 50 / global 5+194 / dragon 60 / auction 70。`leader_height` 每日 1 行 |
| 产物 | 日报/题材/队列/agent/矩阵 1·3·4/workbench/cockpit；增量 4.1MB |
| receive | receipt `received=10` |
| 锁 / staging | 均无 |

`daily-workflow-summary.json` 仍是 00:02 的 `skip_agent=true`，**不能当队列证据**。

## 本单可认领（未提交）

脏树：`skills/daily-full-review/SKILL.md`、`references/ops-pitfalls.md`、`state/runlog.md`、08-25 产物、本文件。

Skill 已改：S7 禁直写生产；行数不够要抽查值；两个 python；cockpit `--knowledge-root`；HTML 走 `render_daily_review_briefing.py`；KB=`/Users/a77/knowledge-base-private`；胜率/晨汇/evolve 不是完成判据。

**不要动**：`inflight/feat-reading-rules-baseline-batch1.md`、知识库 `fix/rss-l3-auto-promote`、forecast-ledger 那批 `M`。

## 已知欠账（别当 08-25 洞）

L2 自 08-07；飞书 market-daily / 新浪指数；`fph-auth` 与写入守卫未进 `gitea/main`；framework 无 `user_framework` 跳过。

## 下一步

1. skill 改动另开干净 `docs/` 或 `fix/` 树再提，**不要**从本脏树带 reading-rules 一起合。
2. `fph-auth` 合 main 等你确认。
3. IMA 五条（碳中和/特高压/新能源车/数据中心/一带一路）你点头再开。

## 工具沉淀

content-delta 临时 park、空壳抽查是手法（一次、要看知识库是否别人的分支），未抽脚本。可迁移形状已在 skill / ops-pitfalls：快照范围 ≠ gitignore；`COUNT(*)` 过门 ≠ 值在。
