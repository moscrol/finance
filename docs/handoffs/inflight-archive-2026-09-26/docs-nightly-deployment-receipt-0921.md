# 夜跑发布证据封存

## 这个分支做什么
封存#827复验、精确快进合入与18:43窄发布事实；不改运行代码。

## 决策与被否方案
运行/测试收据签c097，文档另枝；否追加文档后冒签同一全量。原模型报告和日志保留，不修字节洗绿。背景与被否方案见`../2026-09-21-nightly-deployment-complete.md`。

## 当前状态
#827已合main=c097d712f；两个夜跑job已装三adcda固定根，复核idle/runs0，无kickstart/手动采集。此枝是文档与证据，不是新的源码候选。原件`~/.finance-runtime/reviews/nightly-deploy-resume-20260921/`，manifest在`docs/verification/2026-09-21-nightly-deploy-resume/`。

## 已验证
c097全量12502P/0F/0error/85S/2X；前端110P/E2E34P2S，registry/边界/hooks0。独立Spec@2ea6/Quality@b0cf，8安装输入一致、最终树根复跑21+62断言。合main后精确收据校验0；实际装机/loaded/备份、旧根/库/8792与其他job不变。

## 未验证 / 已知边界
文档尖不继承全量；独立范围不含上游#830。新根真实采集/报告/L2/生成未执行验收。旧18:30自然sync退出2，东财连接断开、当日空数，staging拒换库；readiness503仍在。8792由他会话部署f2c3，本轮未动。

## 下一步
审合此文档枝；生产配置不需重复切。观察正常计划的真实收据，若当日补采先另确认；不要删失败staging/旧根或重跑一次性发布脚本。

## 踩过的坑
manifest只校验原件集合；文档解释不能替代原件。最后装机发布结果看deployment/result，不倒改合入前QC的merged=false快照。
