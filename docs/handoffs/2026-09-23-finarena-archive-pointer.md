# 工单 #82：FinArena 本期归档，保留重启入口

用户在本会话针对“确认按归档方案执行吗？确认后给 #816/#817 留完整指针再关闭，保留分支和原件，并沉淀事务原则”的问题回复：**「执行」**。据此选择归档路径 B；本评论是关闭前的接替指针，不是合并或删除授权。

## 处置理由与替代物

本期不落地邀请制偏好评测产品，优先处理 Workbench 的事实核对、给定条件计算与追问交付。竞技场的偏好票不能替代金融事实认证；本期归档不等于代码验收通过，也不等于永远放弃评测。

- [产品两路决策](http://127.0.0.1:3300/a77/finance-workspace-private/src/branch/docs/finarena-decision-0923/docs/superpowers/specs/2026-09-23-finarena-decision.md)，初始决策固定提交 `79f72b3851629daa1360259b140fac02aeba96bc`。
- [三条旧质量样本移交 #76](http://127.0.0.1:3300/a77/finance-workspace-private/src/commit/79f72b3851629daa1360259b140fac02aeba96bc/docs/handoffs/2026-09-23-finarena-quality-transfer.md)：财务算例被证据合同拦截、同会话追问未交付、行情漏项与来源错误。仅登记待授权补充，不重跑、不更改原“续问 0”预算。
- 可迁移原则已沉淀到共享知识库 `10_knowledge/completion-state-artifact-atomicity.md`：完成态与产物同事务、未知运行先核实再恢复、发布变更与审计同事务。不是复制 Arena 成新的默认运行模块。

## 保留清单

| 对象 | 固定提交 / 路径 |
|---|---|
| #816 分支 | `fix/arena-main-ready-0921@a8fab956bd1368518013fc3e80c892ddd0d914d0` |
| #817 分支，重启代码起点 | `fix/arena-recovery-0921@2f2eb31cc910d8af09a6830e9cb3477866bc2877` |
| ops 合流历史，与 #817 同树 | `ops/arena-recovery-gates-0921@7d10eea9aad1565955838e967ffe8ba7dd0e3145` |
| 旧报告与工程证据 | `~/.finance-runtime/reviews/arena-main-ready-v2-20260921/` |
| 旧真实三轮原件 | `~/.local/share/finance-arena/probes/8792-20260920T144303Z/`，本次决策阶段核验 18/18 哈希一致 |

仅关闭 #816/#817；保留上述本地及远端分支、原工作树和原件，不删除数据库，不启停 8816/8792，不调用真实参赛端点，不合 main。#811 已关闭，继续按其原指针追溯。

## 失效对策与重启条件

旧工程收据只签各自旧版本，不能因本次归档移签 #817 或未来 main。未来重启先明确使用者、参赛版本、审核负责人、材料权限和预算，再从 #817 新建候选、前向至当时 main，跑完整四类门禁、Arena 专项与事务故障反证，交 #75 独立复审，合入另等授权。历史修复只能作为起点，不是即插即用的已验模块。
