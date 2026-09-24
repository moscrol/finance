# 在途：输入与底座验收

## 这个分支做什么
阶段A基线与B离线前置，不是生产恢复单。规格见 `docs/superpowers/specs/2026-09-24-architecture-input-foundation-audit-spec.md`。

## 决策与被否方案
- 缺报告保留未知；文件盘点不当消费。
- 晨汇固定KB版本、临时建标签；否碰脏源/换生产库。
- 风远七条剥数、三条改措辞有旧记录；否自动恢复旧值或相似度代批。
- 当前装配/历史票据/已知考卷分开报，否旧考卷代独立质量验证。
- 展开见 `docs/handoffs/2026-09-24-perspective-reconciliation-decisions.md` 及同日consumption前篇。

## 当前状态
A实现6e6a2eac2；B前置7863fa125；本轮6365501ba已提交，未推送/开PR/合main/部署。
09-24 14:44Z生产readiness仍503，market_data_consistency失败。晨汇生产阻塞未解除。
风远四字段147/147进入上下文；历史approved原值95/105，十条有改写意图记录但缺逐patch替代关系。52条无等值批准票据中含十条改写，余42条仍需追溯；旧记载14条人工写入仅4条本轮字面互证。SPT92/92装配，但无考卷。

## 未验证 / 已知边界
未调新模型、写用户目录、补生产/换库/部署/建索引/恢复采集。原始授权对话、手工框架全量、真实Episode/CLI采用及质量、跨日稳定与优化对照未签。162P是定向回归，不是四叶发布门禁；生产/KB/视角原owner仍负责修复。

## 下一步
1. 读 `docs/verification/2026-09-24-perspective-reconciliation/README.md`；晨汇重跑命令与断点在相邻architecture-consumption目录。
2. #61修行情身份/范围/字段/日历；KB/#87发布固定正文、投影与标签。09-18晨汇受09-22关键字段空值阻断。
3. 视角owner衔接修订记录及未合文档；Q-002 #12-#30已在docs/fengyuan-distill-0916，不重建队列。SPT需独立冻结考卷，不从画像自造金标。
4. 前置和预算闭合后按#76验真入口；合入另冻结候选、全量门禁和用户确认。

## 已验证
6365501ba干净树162P/0F/0S，dirty=false，第三轮目录clean-targeted-receipt.json只绑定该SHA。Ruff、diff-check、实现提交钩子通过。
风远既有考卷2已知+1边题均过；SPT缺卷显式FAIL。检查器增加漂移候选、当前装配、可选考卷及九个反例，不改runtime。

## 踩过的坑
health绿不等于readiness；default不是服务账户；当前画像不等于历史patch原值。主干没看到记录不等于其他分支没登记。考卷曾用于改措辞，不能证明未见题。工具归已有scripts，政策语义仍须人工判断。
