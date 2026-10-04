## 这个分支做什么

FINANCEWORKS-8：个人回顾范围仲裁失败时停止未经确认的任务、保留原题。PR36 已合入并发布；完整发布事实见 [`docs/handoffs/2026-10-04-recall-failure-deploy.md`](../2026-10-04-recall-failure-deploy.md)。

## 决策与被否方案

| 采用 | 未采用 | 理由 |
|---|---|---|
| 仲裁失败停止且尊重取消 | 自动改纯回顾、覆盖取消 | 不改变混合诉求或取消意图；细节见日期快照 |

## 当前状态

失败出口修复已发布于 `04799bc6fb60`，本修复树已回收。后续内容验收由 FINANCEWORKS-8/6 跟进，发布与工作区状态以 FINANCEWORKS-13 最新评论为准。

## 已验证

发布 revision 的全量 `20398 passed / 78 skipped / 2 xfailed`、前端、生产健康与一条真实 Episode 链通过；原件路径见日期快照，不移签后续 revision。

## 未验证 / 已知边界

弱模型/强模型配对收益、真实自然题、必要后续限定和记忆候选语义验收仍未完成；`FINANCEWORKS-1` 不得标完成。Pi 的 PR30/`feat/harness-integration-1003` 仍在途，不得接管或清理。其他 worktree 只按任务板和 `worktree_closeout.py` 点名处理。

## 下一步

Pi 完成 PR30 后，按 FINANCEWORKS-3 验收；FINANCEWORKS-6 继续内容真值和双模型验收，FINANCEWORKS-9 跟进数据源。下一次代码发布重新做 main-tip 门禁和真实业务烟测。

## 踩过的坑

Controller 临时 TaskFrame 不是用户已确认的目标，故障不能冒充没有记录。当前生产 venv 依赖回滚快照 `ffe1c60d84da`，回收前须核实际引用；详见日期快照。
