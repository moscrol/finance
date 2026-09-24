# 在途：输入与底座验收

## 这个分支做什么
阶段A基线与B离线前置，不是生产恢复单。规格：`docs/superpowers/specs/2026-09-24-architecture-input-foundation-audit-spec.md`。

## 决策与被否方案
- 未知不归零；票据/装配/请求送达/采用质量分报。
- 晨汇固定KB、临时标签；否碰脏源/换生产库。
- 风远七条剥数、三条改措辞有旧记录；否自动恢复或相似度代批。
- 保留真实adapter/episode到首次provider回调，用本地截停代替网络；否假答案代签消费。
- 决策：`docs/handoffs/2026-09-25-perspective-delivery-decisions.md`，前篇09-24-perspective-reconciliation-decisions。

## 当前状态
A实现6e6a2eac2；B前置7863fa125、6365501ba；请求检查507872eed，证据663cce791已提交。未推送/PR/合main/部署。
09-24 16:11Z生产readiness仍503，market_data_consistency失败。晨汇生产阻塞未解除。
风远147/147、SPT92/92当前四字段装配；两者完整上下文均达首次GLM请求，中立无视角字段。但总审计仍FAIL：风远历史95/105，十条替代关系未闭合；SPT缺卷且边界字段为空。风远余42条、人工字段/原授权仍待追溯。

## 未验证 / 已知边界
未调新模型、写用户目录、补生产/换库/部署/建索引/恢复采集。离线固定框架不签API身份/选角/路由/后续轮次/模型采用/回答质量；合成编排测试也不是真HTTP入口。487P是定向回归，不是全量发布门禁。旧SPT run有署名但缺完整视角输入、判官partial/unavailable，不能补签质量。

## 下一步
1. 读 `docs/verification/2026-09-25-perspective-delivery/README.md`；晨汇断点在09-24-architecture-consumption。
2. #61修行情身份/范围/字段/日历；KB/#87发布固定正文/投影/标签。09-18晨汇仍受09-22字段空值阻断。
3. 视角owner衔接修订与原审批；Q-002 #12-#30已在docs/fengyuan-distill-0916，不重建。SPT考卷至少2已知+1边题由用户确认，不从画像反推金标。
4. 前置与预算闭合后按#76验真入口，再做跨日稳定和配对优化。合入另冻结候选、全量门禁、用户确认。

## 已验证
663cce791干净487P/0F/0S，dirty=false，收据在本轮目录clean-targeted-receipt.json。Ruff、diff-check、提交钩子通过。风远旧考卷2+1均过，SPT缺卷显式FAIL；不改runtime。输入前后哈希不变。

## 踩过的坑
构造器默认函数已绑定，patch模块名不一定注入实例。专用BaseException避免截停被重试吞掉。考卷存在性要在请求捕获之后终检。主干未登记不等于他分支没有；health绿非readiness绿。工具复用scripts，不建第二审批器。
