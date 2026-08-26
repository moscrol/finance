# 已作废：DSH 吸收遗留问题修复（2026-08-20 初稿）

- 状态：**Superseded**
- 作废原因：把并发共享窗口误写成「剩余预算 / 工具数」均分；把次数闸（每批第 5 槽）当成时间饿死；把「工具饥饿」观测链当成预算验收；又另写一套追问模板，和已有编排 spec 冲突。评审见会话 2026-08-20。

**不要按本文实施。**

| 原问题 | 现在去哪 |
|---|---|
| 工具批次预算 / `kb_search` 12s 窗口超时 | `docs/superpowers/specs/2026-08-20-retrieval-tier-by-remaining-budget-design.md`（`R-20260817-02`） |
| Followup `view()` 合同 | `docs/superpowers/specs/2026-08-17-followup-angle-composer-design.md`（T-E：新 compose 不要复用 `generate_followups`；不是拆现网 gap 镜像） |
| 公开答案唯一投影 | 已合 PR #134，不重做 |
