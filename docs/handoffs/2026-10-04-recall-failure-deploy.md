# 2026-10-04 个人回顾失败出口发布收口

本记录把 FINANCEWORKS-8 的最终发布事实集中到一个可复核位置。实现是“个人回顾范围仲裁失败时停止未经确认的任务并保留原题”；它不代表弱模型、强模型或两档模型配对的内容收益已经验收。

## 决策与部署注意点

范围仲裁故障原先仍会执行临时的定义或金融研究目标；修复先停止该错误路径，独立审查随后补齐取消竞态，才进行完整门禁和发布。

| 采用 | 未采用 | 原因 |
|---|---|---|
| 消费已有个人回顾失败标识、复用 failed 终态 | 自动改为纯回顾或添加关键词路线 | 混合诉求不能因服务故障丢掉用户要求的外部事实研究 |
| 仅拦截个人回顾范围未判定 | 所有 Controller 失败都拒绝 | 本次证据只覆盖个人回顾仲裁失败；普通金融合同沿原路径 |
| 写失败终态前再核对取消信号 | Controller 返回失败即强制覆盖终态 | 取消可能在两步之间到达，必须保留 cancelled |

第一次切换暴露启动器依赖快照下 `.venv-workbench`，缺少它会以 exit 127 反复启动。补齐受控环境链接后启动及烟测成功。当前快照复用回滚快照的 venv，所以回滚目录同时承载运行依赖，回收前必须检查实际解释器引用。未另建工具：现有收据校验、部署账本和点名回收脚本已承担核验；本次补的是发布事实与环境依赖说明。

## 已完成

- PR [#36](https://github.com/moscrol/finance/pull/36) 已于 `2026-10-04T04:27:50Z` 合入，合并提交为 `04799bc6fb60472e5207275720f09d2ab0935c0c`。发布回读时 `origin/main` 与 `gitea/main` 均指向该提交；后续文档提交不改变本发布收据的 revision。
- GitHub 必需叶子 `python`、`frontend`、`e2e`、`registry-check` 与聚合 `workbench-check` 均成功。合并后独立 Python 全量收据为 `/Users/a77/.finance-runtime/test-receipts/gate-rzY8XTss/pytest.json`：`20398 passed / 78 skipped / 2 xfailed`，`collected=20478`，`failed=0 / error=0`；`scripts/check_test_receipt.py --require-full-scope` 已在产生收据的 Python 3.12.13 环境核验通过。前端 lint、typecheck、210 个 Vitest 与 build 也已完成。
- 生产已切到 `/Users/a77/.finance-runtime/finance-workspace-04799bc6fb60`，运行软链为 `/Users/a77/finance-workspace-runtime`；回滚快照 `ffe1c60d84da` 保留。发布后的 health/readiness 见 `/Users/a77/.finance-runtime/deploy-20261004-04799-post/`：revision、加载树指纹、`dirty=false` 一致，RAG ready，workers 无排队任务，4 个历史 open episode 与发布前一致。
- 发布后真实 Workbench Episode `deploy-post-04799-20261004/runs/run_20261004_131800_255854` 留有 `continuous-episode.json`，`judge_status=passed`、`content_degraded_count=0`、`judge_unavailable_count=0`；它证明一条真实业务链可运行，不替代内容质量样本集。
- GitHub 到 Gitea 的本地备份成功，状态见 `/Users/a77/.finance-runtime/github-backup/finance/status.json`，覆盖 342 个源引用；bundle 为 `/Users/a77/backups/github-finance/2026-10-04/repository-cd9e7b195a495c6e133613c1e00db799827effba766b15f1079d86f86ae62ece.bundle`。
- PR36 验收树已按 `/Users/a77/.finance-runtime/reviews/worktree-closeout-20261004/apply-20261004T132726.json` 保全并拆除。Pi 的 `/Users/a77/fwp-wt-harness-integration-1003` 和 PR30 仍在途，不能清理或覆盖。

## 仍未完成

- 本次发布只证明工程门禁、启动环境和一条真实 Episode 链健康。真实自然题、必要后续限定、BGE/记忆候选的人工语义确认，以及弱模型/强模型配对收益仍未通过；因此 `FINANCEWORKS-1` 不得标完成。
- `FINANCEWORKS-3` 仍在研，`FINANCEWORKS-6` 与 `FINANCEWORKS-9` 尚未完成。Pi 完成 PR30 后，需按任务板验收标准在独立树复验，再决定下一次发布。
- `worktree_board.py --landed` 仍会显示其他 agent 的活动树或带补丁树；它们属于在途成果，不能因本次发布批量拆除。生产快照和回滚点也必须保留。

## 建议调用的 skills

- `manage-taskboard`：回读并推进 FINANCEWORKS-13/父任务状态。
- `code-review`：对 PR30 或下一候选固定提交做 Standards/Spec 双轴审查。
- `harness-architecture-review`：审查 harness 六层约束、验证和纠正是否覆盖目标。
- `handoff`：下一轮结束时更新对应 inflight 文件并保留本正式记录作为发布事实索引。

## 下一轮启动 prompt

先读 `AGENTS.md`、本记录、`docs/superpowers/specs/2026-10-04-personal-recall-failure-exit.md` 和任务板最新评论；运行 `git worktree list && git status --short`，认领工作树后再动手。Pi 的 `feat/harness-integration-1003` 与 PR30 不得覆盖或清理。只接受固定提交、完整收据、独立内容验收和真实入口烟测都齐备的候选；不要把工程绿灯或一次 smoke 当成弱/强模型收益结论。
