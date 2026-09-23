# 2026-09-23 #72 / PR #868 最新 main 前向与合入前质检

## 背景

PR #868 原远端 head 是 `7deedffba`，其代码尖 `b7a479e6a` 的旧四叶收据绑定在更早的 main 合流树。质检时发现 `gitea/main` 先后从 `3b7e473575` 前进到 `760248ece`，因此不能把旧收据外推到新合流树。

## 决策与取舍

1. **先前向再重跑，不复用旧收据。** 在功能 worktree 先以 `--no-ff` 合入 `gitea/main@3b7e473575` 得 `24ada4f80`；main 再前进后，无内容冲突地合入 `760248ece` 得 `7ad61a0d3`。选择前向而非重做历史，是因为功能枝已有较长提交链；最终仍以新合流尖的门禁为准。
2. **测试冲突两边语义都保留。** `test_draft_stream_end_to_end.py` 保留 main 的 `complete=False/True` 及 `finish_reason` 断言，同时保留传输层 seam `intelligence.services.llm_http_transport.urlopen`；不要退回旧的 `urllib.request.urlopen` mock。
3. **发现并修正 C2 计数。** AST 逐调用点核出 `_open_deadline_http_response` 实际为 5 处（1167/1219/1424/1546/2304），均传 `deadline`；此前 PR 文字写“四处”不准确，代码行为没有因此改变。
4. **保持 WIP 守卫。** 门禁通过不等于用户授权合 main；PR 临时标题守卫保留，直到用户明确确认合入。推送功能分支和更新 PR 描述不属于合入。

## 新合流尖验证

隔离、加锁 worktree：`/Users/a77/.finance-runtime/reviews/pr868-forward-20260923/finance-workspace-private`。

- 定向冲突相关回归：`63 passed`。
- 四叶收据：`~/.finance-runtime/reviews/pr868-forward-20260923/gate-7ad61a0d3/`。
- ruff、pytest 全量、前端六步、registry ×4 + ledger crosswalk、严格截止探针全部 exit 0。
- pytest：`14921 passed / 85 skipped / 2 xfailed / 0 failed`，收据 revision、解释器、依赖指纹、干净树均通过校验。
- 前端：120 单测，E2E 34 passed / 2 skipped。
- 严格探针：`deadline_violations=[]`。

## 未覆盖

真实模型改稿复核 #76、第二方 Spec/Quality #75、内容层旧的 absence-live 问题仍未完成；`is_cancelled=` 转发的停顿期阳性变异仍存活。合流尖之后只允许 docs 变更，若 main 再前进须重新 conflict-check，代码树收据不能自动外推。

## 后续

提交本文件及 README/QUEUE/在途交接更新；推送新 head；跑本机 `conflict-check` 并回读 PR head。保持 WIP，等待用户授权后才执行 `gitea_pr.py merge --yes`。
