# A股研究交付候选 · 2026-09-18

## 这个分支做什么
复用数据链，修计算不可展示/终稿错数、查询空错推成无公告；不造第二取数或事实写链。

## 当前状态
树 `~/fwp-wt-research-data-readiness`；业务 **a31b572f** 已提交，后续收口仅文档。工程通过，**自然回答质量仍not_passed**；finance未push/PR/合main/部署，8792未动，8907保持停服。
详情：`docs/handoffs/2026-09-18-research-delivery-guards.md`；新manifest：`docs/verification/2026-09-18-research-delivery/manifest.json`。
原件 `~/.finance-runtime/research-delivery-20260918/`（DELIVERY）。旧readiness快照/194件封印保留，不代表新状态。

## 决策与被否方案
- 新结果成功前验格式；否改旧归一化器漂白失败，格式不证公式。
- 公开正文局部拒错/错格待核；否删整答或静默替模型改数。
- 同会话原证据/权限/预算续修，错因进原请求；否缺口即增资源、耗尽即取消必答。
- 只保原绑定且仍引用的可信卡，最终投影再验；否复活已拒槽或借草稿凭据。
- 首次核验前总期限到期即核验未完成；否把未验稿当可信前稿。

## 未验证 / 已知边界
- 本轮0新自然模型/0新取数。旧公告与计算真实失败不翻案；SDK替身37例、冻结沙箱/展示重放不代签自然修复与整篇正确。
- guard仅单公司、显式期别/绝对现金流净利比率及有限公告推断；多公司/隐含期别/来源/公式/任意脚本消费另验，跳过非认证。
- cninfo403/互动易字段错未恢复；历史解禁缺披露时点，不能当前回填。弱先验/扩题、event_daily过宽新鲜度提示未修。
- 未整合R5选期/缓存等；独立QC、真人视觉、合流版验收未跑，旧预算碰撞/溯源偶发根因未定。

## 下一步
1. 审边界/对齐并行已提交版本，不复制WIP。
2. 授权后固定题集/revision/模型/壳/预算，走真实conversations首发；核gpt-5.6-sol与Keychain，别沿用旧GLM launcher或重采样挑绿。
3. 合流SHA另跑批次门，用户确认才合并/部署。自然调度/方法协议/KB apply继续分案。

## 已验证
a31 clean全量 **11635P/83S/2x**、Ruff、前端lint/typecheck/build绿；前端107P、E2E34P/2S、registry四项/crosswalk绿。收据 `20260918T122214Z-a31b572f.json`；DELIVERY/candidate-a31b572f/result.json。
新13组拆保护均真实断言红、还原绿，基线/恢复107P。默认extraction35组兼容复跑，恢复165P（含变异运行异常，不全称断言红）。338件新封印，旧194件hash不变。

## 踩过的坑
主树.venv-workbench、净环境/umask022。工具关窗≠root到期≠额度耗尽；回调内assert可能被吞，外部再验载荷。代码目录由源码生成。图谱PENDING/代码地图missing不证明无能力或已上线。
