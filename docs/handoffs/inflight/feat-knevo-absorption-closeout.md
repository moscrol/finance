# feat/knevo-absorption-closeout

## 这个分支做什么
Knevo 15-28 轮剩余对账与五类研究纪律双引擎接线；另查询用户所称 elevemem/mem0 PR。

## 决策与被否方案
- 复用既有题型/工具/证据门，不新建八套能力；规则是生成指导，不是语义验真器。
- 旧 ask 保留信封专项意图，显式 override 优先；不扩大关键词路由。
- 风远生产画像已有其他会话四批写入及7张结构化规则；只读复核，不重复 ingest/覆盖。
- 详情与被否方案见 `docs/handoffs/2026-09-16-knevo-workflow-absorption.md`。

## 当前状态
代码 `ae86336c` 已提交推送，PR #774 open、未合、未部署。树为 `~/fwp-wt-knevo-absorption`。
生产健康接口仍 `db2963d4fbaa`。主树他改完全未动。

## 已验证
干净固定 `ae86336c` 575P/0F；收据 `~/.finance-runtime/test-receipts/20260916T141351Z-ae86336c.json`。
全仓ruff、pre-commit与工具生成目录保鲜通过。能力图谱新增分支符号已核、整体审计exit0。
风远旧考卷2已知+1边界通过，API可见24篇；不是新规则全验。

## 未验证 / 已知边界
未跑全仓pytest、前端/e2e、完整发布registry门禁、独立QC或真实模型A/B。
自然语言路由仍可能识别不到专项；新提示不保证模型遵守。
Knevo三处架构自述矛盾未裁决，W3降权阈值/q18 runner/冻结28题均未动。
目标 elevemem/mem0 PR未唯一定位；旧Mem0审计是设计参照，不能冒充目标已完成。

## 下一步
1. PR #774 独立复核与完整门禁后请用户确认合并，部署另验。
2. 有界样本验证五类规则的模型效果与遗漏路由。
3. 用户提供记忆PR链接/编号/准确名称后补定位；#41候选链已合且在部署祖先中不等于目标PR。

## 踩过的坑
旧台账说风远“一条未写”已过时，要读启动器实际用户空间。旧ask最终题型与信封会不同。
原文26轮是同会话假设性去skill，不是隔离消融。graph_audit在agent-memory/scripts，不在finance/scripts。
