# 2026-09-23 302132 历史回填验收整合工单（#83）

可独立分发。执行方无需读聊天记录，本单自带背景、证据路径、步骤、验收与红线。
来源：`docs/handoffs/2026-09-23-orphan-inventory.md`。前置：无；但**真实生产回填**另需用户逐字授权，本单默认只到「PR 合入就绪」。

## 背景与动机

302132 的历史日线回填做成了 `market_feature_store.cli` 下的专用父子命令（staging 编排 + 子进程写入 + 验收脚本 `scripts/verify_302132_backfill_acceptance.py`），09-20 在 `fix/backfill-302132-scoped` 上完成，验收绑定修复叠为 #802（base 仍是那条分支），09-21 前向到当时 main 成 **PR #813**（`fix/backfill-main-ready-0921`，只动 4 个源码/测试文件）。之后 #812/#813/#814 被合成冻结组合 `6eb12c1b8`（基线 `c615adbd`）跑出全量 12461P / 0F，但 **K3 独立复审两轴在 08:40Z 同时 exit 1（Spec 明确 ENOSPC），无终稿**，标 BLOCKED_INFRASTRUCTURE，复审暂停后无人接手。#814 后来随 #863 进了 main。

今天核对 [实测]：#813 对当前 main **0 冲突**；#802/#813 新增的 ~2550 行非文档代码在 main 中只找到 105 行（4%），未落地。父命令「`--db` 在文件探针 / 编排前返回 2」已修（#813 handoff）。真实的「冻结输入 + 完整库副本父子发布 + 备份恢复演练」与生产回填**从未执行**。

已定形态：写入仍走 `market_feature_store.cli` 内部（AGENTS.md：复盘事实只走 `daily-full`，不开第二条写入链——本命令是 `daily-full` 同包内的专用回填，不是旁路）。

## 目标

1. #813 前向到当前 main（预期 0 冲突），干净树四叶收据绑定新 head。
2. 在隔离目录用**库副本**做一次父子发布演练：冻结输入 → staging → 原子换库 → `verify_302132_backfill_acceptance.py` 通过 → 回滚到副本原状；全程不碰 `db/market_feature_store.duckdb`。
3. 覆盖率审计按 AGENTS.md 抓值不抓行：回填后抽 `price / pct_chg / amount` 非空率并做跨日期 diff（memory：snapshot backfill silently clones dates）。
4. #802 关闭留指针（→ #813），`fix/backfill-302132-scoped` 分支保留。
5. 登记 #75 QUEUE 一行；合入等用户确认；生产回填另开授权（本单给出一条可复制的命令行 + 回滚命令）。

## 非目标

- ❌ 对生产库执行回填——需要用户对「命令 + 日期范围 + 回滚点」逐字授权，记进 `--record`。
- ❌ 顺手把其他股票的历史缺口一起补——登记到 #33（市场级历史回补 314 天）。
- ❌ 改 `fact_stock_daily` 的 schema 或名称清洗（`stock_name` 的 `\x00` 填充是 #46）。
- ❌ 重启 8792 / 改 launchd。

## 证据路径表

| 文件 | 看什么 |
|---|---|
| `python3 scripts/gitea_pr.py show 813` 及评论（含 `ownership-v4-6eb12c1b8-pr813`、`…-interrupted-…`） | 范围、验证读数、K3 中断原因 |
| `gitea/fix/backfill-main-ready-0921:docs/handoffs/inflight/fix-backfill-main-ready-0921.md` | 父命令退出码语义、原来源树位置 |
| `git diff gitea/main...gitea/fix/backfill-main-ready-0921 -- market_feature_store scripts tests` | 4 个文件净 diff |
| `market_feature_store/sync/repair_backfill_stock_history.py` | 父子命令边界、staging 与换库点 |
| `scripts/verify_302132_backfill_acceptance.py` | 验收判据（含「拒绝巨大数值」） |
| `docs/learning/current-duckdb-source.md` | 验鲜口径：先查各 `fact_*` 的 `max(trade_date)` |
| `docs/superpowers/specs/2026-09-22-worktree-safe-reclaim-workorder.md`（#64） | 6eb12 组合的 12 棵 ownership 树处置归 #84，本单不碰 |

## 步骤

1. 开工三连 + `git fetch gitea`；`git worktree add /Users/a77/fwp-wt-backfill-302132-0923 gitea/fix/backfill-main-ready-0921`；`git merge gitea/main`。
2. 定向：`.venv-workbench/bin/python -m pytest -q tests/test_repair_backfill_stock_history.py`；然后四叶（`bash scripts/run_main_gate.sh`、前端四步、E2E、`build_registry.py check`）。
3. 演练：`cp -c db/market_feature_store.duckdb /Users/a77/.finance-runtime/reviews/backfill-302132-0923/copy.duckdb`（clonefile，#876 已把改前快照做成惯例）；`MARKET_FEATURE_STORE_DB=<副本>` 跑父命令；跑验收脚本；抽非空率与跨日 diff；记录退出码与耗时；演练结束删副本。
4. `python3 scripts/gitea_pr.py close 802 --pointer-file <指针>`。
5. 贴读数到 #813 评论；QUEUE.md 追加；inflight ≤3K；INDEX #83 状态行；把「生产回填命令 + 回滚命令」写成一段等授权。

## 验收

- [ ] `merge-tree` 干净；四叶收据 revision == head、`dirty=false`、failed=0。
- [ ] 副本演练：父命令 exit 0，验收脚本 exit 0，`price/pct_chg/amount` 非空率 ≥ 回填前，跨日 diff 无「整日克隆」形状。
- [ ] 阳性对照：给副本注入一行 `amount` 为 1e15 的脏值，验收脚本必须 exit ≠ 0。
- [ ] 生产库 `stat` 的 mtime 与 `max(trade_date)` 在演练前后一致（证明没碰生产）。
- [ ] #802 已关闭且指针含替代物；INDEX #83 行已改。

## 红线

- pathspec 提交；合 main 等用户确认；不强推；关闭必留指针。
- `.venv-workbench/bin/python`；DuckDB 第二进程拿不到已持有连接（memory），演练前确认无夜跑在写库（`launchctl list | grep financeworkspace`，20:40 finalize 窗口避开）。
- 不写生产库；不跑 `daily-update` / `daily-full-exec`；不恢复任何已退役脚本。
- 不提交 `*.duckdb`。
