# 在途：输入与底座验收

## 这个分支做什么
阶段 A 基线及 B 离线前置；不是生产恢复单。规格 `docs/superpowers/specs/2026-09-24-architecture-input-foundation-audit-spec.md`。

## 决策与被否方案
- 缺报告用未知，不归零；保留 inventory_only 边界。
- 晨汇只从固定 KB 提交导出，在临时目录建标签；否改脏源/换生产库。
- 风远批准值消失只报漂移，否自动重应用：可能有人有意删改。
- 验收复用排名输入与六位精度合同，否放宽容差。
- 展开：`docs/handoffs/2026-09-24-architecture-consumption-decisions.md`；A 决策见同日前篇。

## 当前状态
A 实现6e6a2eac2，B离线前置/审计器修复7863fa125已提交；未推送/开PR/合main/部署。
09-24本轮末生产readiness仍503，版本3b7e473575b0。KB已合a2cfb2b8的09-18晨汇未出现在生产投影。
SPT原文/批准/上下文限定范围PASS。风远105条引文可追，但10条批准值已不在画像；另52条值无当前approved patch票据，语义待审。

## 未验证 / 已知边界
未调用新模型、改用户目录、生产补数/换库/部署/重建索引/恢复采集。实际Episode/回答质量、审批权属、手工框架字段、方法卡生成、跨日稳定、优化对照未签。
137P不是全量Python/前端/E2E/registry发布门禁。生产/KB原owner继续持有修复权。

## 下一步
1. 读 `docs/verification/2026-09-24-architecture-consumption/README.md` 的结果、patch差异、重跑命令；A总表仍在相邻architecture-audit目录。
2. #61先修身份/范围/字段/日历。09-18晨汇按现有日历落到09-22，该日六个关键字段NULL，隔离重建仍失败。
3. KB/#87发布固定版本并重建标签；Perspective owner裁定十条漂移与人工条目，不代批。
4. 前置与预算满足后按#76做真入口；合入另冻结候选、跑完整门禁并等用户确认。

## 已验证
7863fa125干净树137P/0F/0S、dirty=false；收据在第二轮目录clean-targeted-receipt.json，只绑该SHA。Ruff/diff-check及提交钩子通过。
隔离09-14晨汇进入半导体长河，严格截止过滤晚录教学对象；生产同例仍FAIL。SPT92批准值/引文进入上下文；真实账户linxiaoqi5111，两视角均召回3段原文。三份读取模块与部署版哈希相同，不证明模型用对。

## 踩过的坑
health绿不等于readiness；default不是服务账户；文件盘点不是消费。长河entity要用存在的板块，不用market。比回读值要复用写端输入/规范化，NULL不当零。工具已落scripts及反例测试，不另造健康服务。
