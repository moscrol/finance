# 上线回执 · 2026-09-30 00:26：夜跑补名步更正过时名（#982）+ 夜跑代码根 `541ef50ba2b2 → 9c1e3154f613`

写完不改；更正走 `record-correction`。执行者：Claude Code 云端会话 `session_01CBRwJztt4t57Zzr8VMeZZM`，经 exec 隧道操作 Mac。
授权：用户 09-29 约 23:50 回复「同意，你按照最优推进就行」，批准的是 `2026-09-29-namefix-publish.md` §5 的合同 1 扩展。
做法与理由见 `docs/handoffs/2026-09-29-capture-name-refresh.md`。

## 1. 合入

- **首轮门禁**：预演 `4ecd6a18`，基于 main `47a05e36`。python 叶 18659 过、0 挂。
- **重跑**：其间 #980 合入（只动 `docs/handoffs`，但有测试会扫描这个目录），于是改在新基线上整轮重跑四叶：
  - 预演 `4d59850c5cdb`（树 `62cb653b19b9`）= main `e9354fa4b416` + `feat/capture-name-refresh-0929@4fcc334e8962`；
  - python：pytest 18659 过 / 0 挂 / 0 错 / 75 跳过 / 2 xfail；收据 `gate-Vnkxs7IP`，`--require-full-scope` 可采信；
  - registry：五项全过；
  - frontend：vitest 125 过，build 通过；
  - e2e：34 过 / 2 跳过。
  - 读数贴在 #982 评论 7769。
- **合入**（00:26:27）：`gitea_pr.py merge 982 --expect-head 4fcc334e8962 --expect-base e9354fa4b416 --record`。
  - main 为 `79c25224b137`；
  - 回读：`base_points_at_merge_commit`、`head_is_parent`、`tree_matches_preview` 全为 true；
  - 记录在 `~/.finance-runtime/reviews/name-refresh-0929/merge-records/merge-982.json`。

## 2. 夜跑代码根切换（00:26:42 完成）

脚本 `~/.finance-runtime/reviews/name-refresh-0929/switch-sync-root2.sh`，参数为合后 main 的完整 SHA。脚本先做四项前置检查：
- main 没移动；
- `9c1e3154` 是 main 的祖先；
- sync / finalize 两个任务都不在运行；
- 没有夜跑进程。

| 项 | 结果 |
|---|---|
| 新根 | `~/.finance-runtime/finance-sync-9c1e3154f613`，detached、加锁，HEAD `9c1e3154f613…` |
| 状态延续 | `runlog.md` 与旧根逐字节相同；`quality-*.json` 共 40 份带过来 |
| 装机件 | 两个 plist 与 `nightly-full-review-s7.sh` 都从 main `79c25224` 原样写回，与仓内逐字一致。先做了备份，后缀 `.bak-pre-20260929-9c1e315` |
| launchd | sync：`FINANCE_SYNC_CODE_ROOT` 与 `FINANCE_CODE_ROOT` 都指向新根。finalize：`FINANCE_SYNC_CODE_ROOT` 指向新根，`FINANCE_CODE_ROOT` 仍为 `finance-workspace-runtime`（设计如此）。调度仍为 18:30 / 20:40 |
| 计划探针 | 用 plist 自带的环境导入新根的 `run_review_sync`，local 计划顺序为 `stock-daily → capture-dated-quotes → attach-capture-names → bridge-gap-fill → …`，补名步带 `--refresh-stale-names`，输出 `PLAN_OK` |

- **回滚锚**：`finance-sync-541ef50ba2b2`，保留、加锁。
- **回滚做法**：用 `.bak-pre-20260929-9c1e315` 恢复两个 plist 与 s7，再 bootout / bootstrap 两个任务。

## 3. 没动的

- **8792 仍是 `8e31301b05f4`，不切**：
  - #982 只改夜跑侧，即 `skills/duckdb-backfill`、`run_review_sync`、夜跑装机件和文档，8792 读不到这些代码；
  - finalize 从 `finance-workspace-runtime` 跑，不经过补名步。
- **09-29 当天那 45 行过时名不回头修**，理由见交接 §「没做」。

## 4. 09-30 首晚看点

- 18:30 sync：`db/quote-captures/tencent/attach-receipts/2026-09-30-*.json` 里的 `refresh_stale=true`、`refreshed`、`refresh_skipped`。
  - `refreshed` 应在几十行量级，大多是更名、摘帽、除权次日；
  - `refresh_skipped` 非空时，逐条看 bar 为什么对不上。
- 补名步拒跑，也就是补空名全有或全无失败时，`refresh` 整步不写，收据会写明原因。
- 两源补行和申万一级 09-28 前收自愈的看点，同 `2026-09-29-cutover-post977.md` §4。
