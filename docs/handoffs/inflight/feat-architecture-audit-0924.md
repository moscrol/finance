# 在途：输入与底座验收

## 这个分支做什么
阶段A基线与B离线前置，不是生产恢复单。规格：`docs/superpowers/specs/2026-09-24-architecture-input-foundation-audit-spec.md`。

## 决策与被否方案
- 未知不归零；票据/装配/请求送达/采用质量分报。
- 晨汇固定KB、临时标签；否碰脏源/换生产库。
- 风远剥数/改措辞有旧记录；否自动恢复或相似度代批。
- SPT从原文拟题先冻结后预演；否画像反推金标、复制画像句刷绿或自动入卷。即使模拟全过仍BLOCKED。
- 决策：`docs/handoffs/2026-09-25-spt-exam-proposal-decisions.md`，前篇同日perspective-delivery。

## 当前状态
A实现6e6a2eac2；请求检查507872eed；SPT草案/预演4dece383e、证据88ddfa5b0已提交。未推送/PR/合main/部署。
SPT三题待用户逐项确认：风险PASS、机会none/FAIL、边题未弃权/FAIL；内存加拟议边界后边题PASS。机会规则已有approved pp-ed109ca9f818，缺在字面触发，不是规则丢失。正式考卷仍缺、画像未改。
09-25 00:29就绪曾多报rag_query_protocol，00:32复查该项通过但仍HTTP503/market_data_consistency=false；前次原因未知。行情/Workbench原owner仍数据HOLD。
风远147/147、SPT92/92装配且完整上下文到首次GLM请求；风远历史95/105，十条替代关系、余42条及人工原授权仍待追溯。

## 未验证 / 已知边界
未调新模型、写用户目录、补生产/换库/部署/建索引/恢复采集。草案不是金标、不是未见题；预演非模型质量。固定框架不签API/路由/续轮。旧SPT run有署名但无完整输入、判官partial。509P是定向回归，不是全量发布门禁。

## 下一步
1. 读 `docs/verification/2026-09-25-spt-exam-proposal/README.md` 的三项确认页；用户先确认立场与边界，再由owner处理机会题评分合同，不把期望改none求绿。
2. 视角owner补风远修订/审批；Q-002 #12-#30已在docs/fengyuan-distill-0916，不重建。
3. #61及发布owner闭合行情身份/字段/日期，KB/#87发布固定正文/投影/标签；复查检索不稳定，不自归因。
4. 前置/预算闭合后按#76验真入口，再做阶段C/D。合入需新候选、完整门禁、用户确认。

## 已验证
88ddfa5b0干净509P/0F/0S、dirty=false，收据在本轮目录clean-targeted-receipt.json。22个新增预演保护；Ruff/提交钩子过。输入前后未变。风远旧考卷2+1过；SPT总验收仍BLOCKED。

## 踩过的坑
none不是弃权；规则存在不等于词面匹配触发。先固定草案再评分，防结果倒灌题目。构造器默认函数要patch实例；考卷存在性须最后终检。首readiness仅终端摘要，勿补造HTTP码。工具归scripts，无第二审批器。
