# 受托收尾：合并与工作树去向（10-05）

日期：2026-10-05 10:45–11:15 CST。授权：用户原话「你按照最优推进合并等事项」（Claude Code 会话 `74dae9f9-1568-4f13-9063-40253d68445e`）。
以下每一项都是 Claude 的受托代拍，用户一句话即可推翻。委托不含生产部署。
前情见 [10-04 收尾快照](2026-10-04-pi-closeout-and-audit-followthrough.md) 与 [状态页](../verification/2026-10-04-harness-followthrough-status.md)。

## 决策与被否方案

| 事项 | 代拍 | 依据 | 被否方案 |
|---|---|---|---|
| #43 回收工具 `--reason` 配对 | 合入（`364120613`），锁定审过的头 `f7ca7f1c2` | 五项 CI 全绿；本机 ruff 通过，回收与安全两组测试 71 passed；diff 已审：0/1/N 配对，错配退 5（自定义 `_Parser`），`--plan` 不混用。只改开发工具 | 等用户再确认：已整体委托，且不涉生产 |
| #38 材料题金融语义常驻规则 | 关闭，分支 `cc1888e71` 双远端保留 | 无模型验证；常驻追加到所有材料题、作者与判官同改，与规格 §5.2 相反；CI 基于 `ae02f420`，之后 #40/#44/#45 改过同一条链；用户 10-04 决定它不作对照臂，无执行者。完整理由与翻转条件见 PR 评论 | 合入：无质量证据，还需部署。开着或转 Draft：等于去向未知 |
| #30 Pi 集成候选 | 维持 Draft 搁置 | 等 8792 vs Pi 对照；合入前须与最新 main 重新合成并重跑门禁 | 现在合或关：证据不够 |
| #47 market-pack-entry | 不碰 | 另一会话 10:52 刚开，在途 | — |
| 回收 12 棵树 | 拆树，分支保留，HEAD 钉 Gitea `refs/archive/wt-20261005/*` | 预演 12/12 无阻塞；内容在 main、PR #30 头或 Gitea；卷可用 +5.38 GiB | 留给 Codex 侧清：长期无人清，只占清单 |
| 本人已合远端分支 | 删 `claude/acceptance-handoff-summary-57fc87` | 已在 main；“合完的分支直接删”（08-12 长期授权） | — |
| `/private/tmp` 与嵌套在主检出下的树 | 暂留 | `worktree_safety` 按路径前缀判“被 launchd 引用”，误报挡住；已开独立任务修 | 手工复刻回收步骤：等于再写一轮一次性脚本 |
| 本分支 inflight | 本 PR 删除 | 已合入，内容在 10-04 日期快照里 | 留到批量转换：main 上会一直写“未合” |

回收的 12 棵：Codex 的 `7d30`、`9c8d`、`cb6f`、`cf60`、`9020`、`8792-quote-repair-review`、`remote-sync-handoff-0930`；`fwp-wt-takeover-closeout-1004`、`fwp-wt-material-financial-baseline-1004`、`fwp-wt-material-financial-semantics-1004`、`fwp-wt-harness-plan-ownership-1002`、`fwp-wt-owner-output-contract-1002`。
其中 `fix/owner-output-contract-1002` 带一个没进 main、也没进 PR #30 的代码修复 `4cba44a63`；是否已被 PR #30 的 `output_requirement` 取代，随 PR #30 的去留一起评估。
收据：`~/.finance-runtime/reviews/harness-followthrough-20261004/closeout-1005/{plan-1005,dry-20261005T105438,apply-20261005T105541}.json`。

## 部署

线上 8792 是 `58d04e3780f4`（#46，另一会话 04:33 合入后切换），healthy，ready 13/13，源码干净且与仓库一致。
main 比线上只多 #43 的脚本、测试、lessons 和交接，不进运行时，无需部署。

## 工作树最终清单（29 棵，11:05 看板）

| 去向 | 树 |
|---|---|
| 生产快照（9）：按部署账本保留或轮换，本轮不动 | `58d04e37`（当前）、`927cf7d`、`347bc6`、`bd2c58b`、`04799bc6`、`45a7dc`、`40fd5a`（被 sidecar 启动器引用，脏 2）、`2c3949` 与 `ffe1`（上锁） |
| 运行依赖（3）：不动 | 主检出（夜跑运营叠层，加本人 5 处视图对齐，撤销说明在 FINANCEWORKS-13）；`finance-sync-7eec31`（夜跑同步代码根）；`finance-s7-sync`（被 nightly-review-sync-staged 引用） |
| 在途或活动（6）：不动 | `fwp-wt-harness-integration-1003`（Pi，#30）；`fwp-wt-harness-unconstraint-1005`（#47）；`fwp-wt-deploy-pr44-1005`（部署会话，HEAD 未上远端）；会话树 `8792-pi-performance-analysis`、`nervous-bardeen`（#43）、本会话树 |
| 已落地，等误报修好或会话归档后回收（6） | `.claude/worktrees/` 下的 `blissful-noether`、`kind-engelbart`、`pi-session-cleanup`；`.worktrees/capture-quotes-0929`；`/private/tmp` 下的 `arena-harness-release-1002`、`pr10-gates-1002` |
| 有未合内容，等误报修好后回收（4）：分支已在 Gitea | `.worktrees/arena-8792-harness-takeover-0929`（c+30，84% 在 main）；`/private/tmp/review-pr16-1002`（c+27，PR16 已关）；`/private/tmp/harness-opt`（c+24，脏 3）；其下 `harness-release-1002`（脏 3，文件已由 #39 回收进 main） |
| 归属不明的未提交改动（1） | `.claude/worktrees/unclosed-session-stats-838ac4`（`tests/test_main_gate_receipt.py` 多 22 行）。回收时走 salvage 保全 |

## 还开着的

- PR：#30（搁置，等对照）、#47（另一会话在途）。
- 任务板：FINANCEWORKS-2、3 已关。父任务 1 的质量目标仍没有配对证据。
- 主检出那 5 处工作区改动：同步前先撤，命令见 FINANCEWORKS-13 评论。
