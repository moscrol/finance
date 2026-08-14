# fix/smoke-gap-anchor — smoke 语义门锚点倒挂

日期：2026-08-14 ｜ worktree：`/Users/a77/fwp-wt-smoke-gate` ｜ 状态：**已提交，未合 main**

## 这个分支做什么

修 `scripts/smoke_workbench_self_use.py` 的语义门：它在**奖励「复述问题然后拒答」、
惩罚「给实质内容并具体说明缺口」**。

## 当前状态

- 已提交 `e9343b8b`，工作区干净，未 push、未合 main。
- 两处改动缺一不可（实测单改任一条只翻正一半）：
  ① 锚点优先用 `report.task_frame.subject`（上游已抽好，就在 smoke 已读的 payload 里）；
  ② 排除复述题干的段落（阈值 15 字）。
- 取不到 subject 时**退回原行为，不 fail closed**——这个门只该拦「说不清缺口」。

## 已验证

- 真实收据端到端跑 `semantic_answer_issues`：741 字实质回答 判红→**通过**；
  185 字复述题干拒答 通过→**判红**；443 字缺口笼统 判红→判红（不变，合理）。
- `tests/test_smoke_workbench_self_use.py` 31 passed（26 原有 + 5 新增，含 2 条变异测试）。
- `ruff check` 通过。

## 未验证 / 已知边界

- **只验了「主线」那一支**。`_task_gap_anchors` 还有估值 / 反弹 / 因果三支，
  改动对它们是加 subject（不减原锚点），逻辑上只放宽不收紧，但没跑真实样本。
- `ruff format` 报这两个文件要重排——**改之前就报**，是既有状态，故意没动，
  免得混进无关 diff。
- 未跑全量 `intelligence/tests`（该分支只动 scripts/ 与 tests/）。

## 下一步

1. 用估值题（含「估值」关键词）跑一次真实 smoke，确认那一支没被 15 字阈值误伤。
2. 合并后重跑今天的样本，**smoke 判红率会变**——今天之前的红/绿读数不可与之后比较。

## 踩过的坑

- **别在共享主检出树 `/Users/a77/finance-workspace-private` 上开分支。** 本轮就是
  这么干的，结果另一个 agent 的提交落到了我的分支上，还被它的未跟踪 WIP
  （写死家目录）触发 path-literals 门禁挡住提交。pre-commit 的 workspace-facts
  hook 当场警告过「这是主检出树」，我没当回事。开分支去自己的 worktree。
- 判据「从原始字符串猜实体」几乎总是错层——上游一般已经抽好了。同形状见
  `docs/handoffs/2026-08-05-user-memory-recall-cjk.md`（已标作废：修错了层）。
