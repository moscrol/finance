# feat/adaptive-research-loop

## 这个分支做什么
模型自主选视角并随证据调整；不固定股票池。继续同会话反馈/公开保真，不转K3外审。树 `~/finance-worktrees/adaptive-research-loop`。

## 决策与被否方案
- 原句/阶段回原REPAIR_GOAL；否按删句后编号猜原句。
- 诊断与授权分离；否让诊断改预算/增额度。数字补证诊断仅在授权后投递。
- SDK复用领域消息，否私自截短/另造提示；缺历史仍闭工具。
- 发布只对未解决机械/前置反馈降级；`judge`语义删句或降级为issue算已处理，否一律降级会误伤合法历史完成态。
- 不恢复拒句/拼私有gaps。完整理由见 `docs/handoffs/2026-09-21-adaptive-repair-publication.md`。

## 当前状态
代码已提交：`88a12753c`、`d3a2202f0`、`7172ba30e`；当前树干净，未push/PR/合main/部署。公开发布上限已接入并完成误降级修正。证据目录 `~/.finance-runtime/adaptive-repair-publication-20260921/` 已保存最终全量与撤线结果；此前73文件交付目录未改。

## 已验证
最终全量 `12096P/85S/2X/17 warnings`，收据 `~/.finance-runtime/test-receipts/20260920T220029Z-7172ba30.json`，精确绑定 `7172ba30e`。定向历史4P、发布矩阵21P、跨后端24P、Ruff通过。最终撤线：去发布上限16F/恢复24P；误把已解决语义修订当未解决3F/恢复22P；隔离树干净。

## 未验证 / 已知边界
自然模型公开保真、披露重要限制、持续观察后改向未验；脚本模型/SDK runner不代表质量。其他后端、真实费用/上下文窗口、裸代码后缀、监管覆盖、独立Spec/Quality、合流/部署未验。judge off不审gaps；17 warnings非零warning结论。

## 下一步
明确模型额度后，以未见题做真实模型公开保真与持续改向验收，保留原稿/事件/审查/各阶段稿。复验另建目录。不要push、合main、部署、K3、付费外审或删生产，除非明确授权。

## 踩过的坑
`judge_status=repaired`不是单独发布判据；必须结合`sentence_verdicts`阶段/原因。历史`demoted_to_issue`是已完成的保留式语义降级，不是残句。撤线前先固定提交并让临时树指向精确revision；收据不能移绑后续文档tip。
