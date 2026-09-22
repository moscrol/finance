# 独立 QC 批（工单 #75）候选队列

各工单往本文件追加一行，#75 只消费不改写候选。格式：工单号 / PR / head SHA / 候选检出路径（绝对）/ 证据目录 / 主张清单来源 / 状态。状态由 #75 回写（待审 → 审中 → PASS / PASS_WITH_LIMITS / FAIL / BLOCKED_*）。

| 工单 | PR | head SHA | 候选检出路径 | 证据目录 | 主张清单来源 | 状态 |
|---|---|---|---|---|---|---|
| #67 | #863 | `65fde6171e15d3a73c493b2808d076ae6c45cb7c` | `/Users/a77/.finance-runtime/reviews/research-tail-union-resume-20260922/candidate/finance-workspace-private` | `/Users/a77/.finance-runtime/reviews/research-tail-union-resume-20260922/` | PR #863 描述「主张清单」6 条（原件同目录 `PR-BODY-draft.md`） | 已合入 main `8e79893729da`（2026-09-23 00:3x，用户授权）。合前 Claude 子代理做 Quality 轴：PASS_WITH_LIMITS（F1 / F2 见 #863 描述「独立审查」）。#75 若事后审，对象改为该合并提交，Spec 轴主张清单不变 |
| #69 | #843 | `7a4326630` （代码 `e7e12a189f05d5a30357ac70a388b2013cd509dd`，其后仅 inflight 文档提交） | `/Users/a77/.finance-runtime/reviews/runtime-pr843-k3-20260922-followup-01/host-qc-01/candidate-e7e12a189`（作者导出的只读候选）；三层合一审可直接用下面 #865 的候选 | `/Users/a77/.finance-runtime/reviews/runtime-pr843-k3-20260922-followup-01/host-qc-01/` | PR #843 描述 + 分支 inflight「决策与被否方案」4 条 | 待审（2026-09-22 登记；栈底层，#843 → #864 → #865 按序合） |
| #69 | #864 | `1516b94b9`（代码 `691d0ad5c`，门页 `e3024f621`） | `/Users/a77/.finance-runtime/reviews/runtime-identity-effects-20260922/candidate/finance-workspace-private`（detached @ #865 head `0075f9b3b1130b17875c6f3311ecd43a3bcb7a55`，含本层全部代码） | `/Users/a77/.finance-runtime/reviews/runtime-identity-effects-20260922/` | PR #864 描述「主张清单」C1–C7 | 待审（2026-09-22 登记；栈 2/3） |
| #69 | #865 | `0075f9b3b1130b17875c6f3311ecd43a3bcb7a55`（代码 `aec5a6d50`，门页 `a737888b3`；含 `gitea/main@f24a61a8a` 前向合并与下两层 tip） | `/Users/a77/.finance-runtime/reviews/runtime-identity-effects-20260922/candidate/finance-workspace-private` | `/Users/a77/.finance-runtime/reviews/runtime-identity-effects-20260922/`（`positive-controls/`、`gate-*/`） | PR #865 描述「主张清单」E1–E9 | 待审（2026-09-22 登记；栈顶层，四叶收据绑此 head，三层可合一审） |
