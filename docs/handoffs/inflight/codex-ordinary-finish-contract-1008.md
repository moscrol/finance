## 这个分支做什么

统一普通Episode的作者合同；当前只完成纯接口Task1，用户新架构问题改变了接续优先级。

## 决策与被否方案

| 选了什么 | 否了什么 | 为什么 |
|---|---|---|
| 先审既有研究职责，再接Task2/3 | 继续只扩成稿或加末端词法规则 | 合同不一致只是一个缺口，集合/连续性/因果错误仍在 |
| 复用Frame/Plan/Harness | 新增重复总控、整套重写 | 现有循环、权限、预算与观测有效 |
| 保留Task1独立成果 | reset旧失败或把定向绿当全文合格 | 原收据与失败需可追溯 |

展开：[架构审查快照](../2026-10-09-knevo-architecture-review.md)。

## 当前状态

代码HEAD=f5847f33、tree=4c7b7eef；两入口finish_authoring及protocol兼容接线已提交，四路径。Task2初始真实system、Task3repair/finalizer/restore未改，保持hold。当前分支未合/未部署。

## 已验证

f584定向121 collected=121 passed、无收窄，locked解释器；独立Spec 18离线控制通过，Standards零实质发现。旧e4定向223P另账，原F1失败保留。不签全量。

## 未验证 / 已知边界

新合同未进入真实模型初始/修订/恢复路径，无新模型调用。生产bd66唯一首答全文NOT_PASSED：重复群组当去重数、跨度当连续、量价推贡献、未来条件当当日反证。Knevo隐藏路由/发送前硬校未知，n=1不证明全面胜Pi或记忆收益。

## 下一步

以架构审查为起点，沿既有TaskFrame→ResearchPlan→FinanceResearchHarness写具体职责与验收设计，再决定Task2/3如何接入。保留相关性选择与有限恢复，知识/记忆不每题强制全调用；不擅开判官或增预算。先优化上线，再登记唯一首答验整篇。

## 踩过的坑

schema支持≠真实system采用；refs送达≠被消费；来源/格式合格≠自由结论正确。AST拒绝码盘点要读三个实际owner的constructor调用，不能只扫直接raise或抄常量。Pi树与harness-reference/BUILD.md他人改动不碰。
