## 这个分支做什么

收口 FINANCEWORKS-13 的发布、双远程与工作树记录；正文见 [`docs/handoffs/2026-10-04-recall-failure-deploy.md`](../2026-10-04-recall-failure-deploy.md)。

## 当前状态

- 本分支提交 `329c47e25`，PR [#37](https://github.com/moscrol/finance/pull/37) 尚未合入；它只有两份 Markdown，服务代码仍是已发布的 `04799bc6fb60472e5207275720f09d2ab0935c0c`。
- PR37 的 frontend、e2e、registry 已通过；python 全量仍在 GitHub Actions 运行。通过后合入，再回读 GitHub/Gitea 两端和备份。
- 生产 `/Users/a77/.finance-runtime/finance-workspace-04799bc6fb60` 健康，`source_revision=04799bc6fb60472e5207275720f09d2ab0935c0c`、`source_dirty=false`、`code_matches_repo=true`；回滚快照 `ffe1c60d84da` 保留。
- GitHub 当前开放 PR 为 Pi 的草稿 PR30 和本 PR37；Pi 的 `/Users/a77/fwp-wt-harness-integration-1003` 不得接管或清理。看板快照显示 36 棵树、15 棵有 cherry+、6 棵脏；只能逐树点名收口。

## 未完成 / 已知边界

- 任务板最后已知 FINANCEWORKS-13 为 `in_progress`、version 8；本轮回读时 `127.0.0.1:47823` 不可达，恢复后需补评论并移到 `in_review`。父任务 FINANCEWORKS-1 继续 `in_progress`。
- `FINANCEWORKS-3`（PR30）、`FINANCEWORKS-6`（内容缺陷与双模型配对）、`FINANCEWORKS-9`（数据源/AIHOT）仍未完成。工程绿、部署成功和单次 Episode smoke 都不能代替弱模型/强模型收益证明。

## 下一步

先等 PR37 python 检查成功；合入后确认 `origin/main == gitea/main`，运行一次备份状态回读，再在任务板补证据评论并移本项 `in_review`。只回收本次文档树；生产、回滚、Pi 活动树和其他在途树保留。

## 建议调用的 skills

`manage-taskboard`、`handoff`、`code-review`、`harness-architecture-review`。
