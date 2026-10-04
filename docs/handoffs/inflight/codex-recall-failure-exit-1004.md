## 这个分支做什么

FINANCEWORKS-8：个人回顾范围仲裁失败时停止未经确认的任务、保留原题。PR36 已合入并发布；完整发布事实见 [`docs/handoffs/2026-10-04-recall-failure-deploy.md`](../2026-10-04-recall-failure-deploy.md)。

## 当前状态

- 合并提交：`04799bc6fb60472e5207275720f09d2ab0935c0c`；`origin/main` 与 `gitea/main` 一致。
- 合并后全量收据：`/Users/a77/.finance-runtime/test-receipts/gate-rzY8XTss/pytest.json`，`20398 passed / 78 skipped / 2 xfailed`，full-scope 已核验。
- 生产快照：`/Users/a77/.finance-runtime/finance-workspace-04799bc6fb60`；回滚点 `ffe1c60d84da`。health/readiness、真实 Episode 烟测、Gitea 备份和验收树拆除均有正式记录指针。

## 未完成与边界

弱模型/强模型配对收益、真实自然题、必要后续限定和记忆候选语义验收仍未完成；`FINANCEWORKS-1` 不得标完成。Pi 的 PR30/`feat/harness-integration-1003` 仍在途，不得接管或清理。其他 worktree 只按任务板和 `worktree_closeout.py` 点名处理。

## 下一步

Pi 完成 PR30 后，按 FINANCEWORKS-3 验收；再处理 FINANCEWORKS-6/9 的内容真值和双模型验收。下一次发布必须重新做 main-tip 全量门禁、健康/就绪检查和真实业务烟测。

## 建议调用的 skills

`manage-taskboard`、`code-review`、`harness-architecture-review`、`handoff`。
