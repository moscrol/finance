# 2026-09-22 第二方 Spec + Quality 队列（工单 #75 消费）

各作者单**只追加一行**，#75 按行消费；不改别人的行。列义：工单号 / PR / head SHA（被门禁的代码尖；其上若只有 docs 提交请注明）/ 候选检出路径（绝对）/ 证据目录 / 主张清单来源 / 状态。
若多单并发创建本文件，合并时按行合并即可（行之间无依赖）。

| 工单 | PR | head SHA | 候选检出路径 | 证据目录 | 主张清单来源 | 状态 |
|---|---|---|---|---|---|---|
| #72 | #868 | `7ad61a0d3`（最新代码尖；由 `24ada4f80` 前向 `gitea/main@760248ece` 得到；PR head 若更高只多 docs 提交） | `/Users/a77/.finance-runtime/reviews/pr868-forward-20260923/finance-workspace-private`（只读引用，审查者应自建树） | `~/.finance-runtime/reviews/pr868-forward-20260923/gate-7ad61a0d3/`（九项全绿：pytest 14921P/85S/2X、前端六步、registry×4+crosswalk、探针 0 越窗）；旧复核 / 变异记录仍见 `docs/verification/2026-09-22-adaptive-deadline/` | PR #868 描述「主张清单」C1–C7（C2 已更正为 5 处 wrapper 调用，C7 以 README「`7ad61a0d3` 三次前向」节为准） | 待审（最新前向工程绿已齐；PR 保持 WIP，合 main 等用户确认） |
