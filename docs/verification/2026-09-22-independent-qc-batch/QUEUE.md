# 2026-09-22 第二方 Spec + Quality 队列（工单 #75 消费）

各作者单**只追加一行**，#75 按行消费；不改别人的行。列义：工单号 / PR / head SHA（被门禁的代码尖；其上若只有 docs 提交请注明）/ 候选检出路径（绝对）/ 证据目录 / 主张清单来源 / 状态。
若多单并发创建本文件，合并时按行合并即可（行之间无依赖）。

| 工单 | PR | head SHA | 候选检出路径 | 证据目录 | 主张清单来源 | 状态 |
|---|---|---|---|---|---|---|
| #72 | #868 | `b7a479e6a`（= `013eb5c4a` + 二次前向合 main@8e7989372 `3020e42df` + 两处语义冲突收尾；PR head 若更高只多 docs 提交） | `/Users/a77/fwp-wt-adaptive-deadline-0922`（只读引用，审查者应自建树） | `~/.finance-runtime/adaptive-deadline-0922/`（`gate-b7a479e6a/` 九项全绿：pytest 14616P/85S/2X、前端六步、registry×4+crosswalk、探针 0 越窗；复核 / 变异记录见 `docs/verification/2026-09-22-adaptive-deadline/`）；作者侧 `~/.finance-runtime/adaptive-advance-20260922/` | PR #868 描述「主张清单」C1–C7（C7 的读数以 README「`b7a479e6a` 四叶」节为准） | 待审（作者工程绿已齐；合 main 等用户确认） |
