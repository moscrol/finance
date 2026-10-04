## 这个分支做什么
核查 Pi 的 PR #30 收尾和 09-30 质检的落实情况，并受托完成四项收尾。PR #42 只改文档。

## 决策与被否方案
| 选择 | 否决 / 理由 |
|---|---|
| FINANCEWORKS-3 改 done，只关工程 | 留 in_review：条件已满足，挂着像还有缺口 |
| PR #30 留 Draft 搁置 | 现在合：质量未验，且 main 已含交叠的 #40；现在关：结果出来前白丢 |
| 主检出只改工作区 5 处 | 整体快进或暂存：有 113 处他人改动，索引共享 |
| 回收两棵树，分支保留 | 等 PR #30 定案：树里无独有内容，随时可重建 |
展开见[日期快照](../2026-10-04-pi-closeout-and-audit-followthrough.md)。

## 当前状态
- 状态页、日期快照、本交接已提交；PR #42 等 CI 和用户确认，未合。
- 主检出 ~/finance-workspace-private 有本轮 5 处工作区改动，与 main 逐字相同，未提交。
- PR #30 正文和 FINANCEWORKS-3（v12 done）已写；FINANCEWORKS-2 只加了评论，状态没动。

## 未验证 / 已知边界
- 没发任何模型调用。
- 记忆召回、Knevo 0/12、四格 0/0/1/0 取自已有文档，未复跑；换库锁未复测。
- G 列冒烟 n=1。数据空列是 23:29 的只读快照。

## 下一步
1. PR #42 出绿后，请用户确认合入。
2. 主检出整体同步前，先撤掉 5 处，命令见 ~/.finance-runtime/reviews/harness-followthrough-20261004/skill-view/README.md。
3. 8792 vs Pi 出结果后，定 PR #30 的去留。

## 踩过的坑
- worktree_closeout 给多个 --reason 时只取最后一个；要按树分别写理由，用 --plan（已另开任务）。
- 桌面 worktree 会话从主检出加载技能和开场事实；在 worktree 里要重跑 session_facts.sh。

## 已验证
- PR #30 文档头 CI 五项 success；52/52 收据哈希一致。
- 两棵树 apply 2/0/0，Gitea 归档钉回读一致。
- 主检出视图与 main 一致，本会话技能列表已热更新。
- 工具沉淀：这轮的度量分属四个子系统，归各自任务（7/9/12），没另写聚合脚本。
