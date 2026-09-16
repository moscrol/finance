# Knevo 工作纪律增量交接

## 背景与发现顺序

用户要求执行剩余炼化，并查询“elevemem 和 mem0”记忆机制 PR。
主树 detached `b4a35fa2` 有他人未提交改动，因此从最新 `gitea/main=c29a6401`
创建独立工作树 `~/fwp-wt-knevo-absorption`、分支 `feat/knevo-absorption-closeout`。

1. 核对 44 轮原文与上次重叠表，确认 8 项是未逐条对账，不是缺 8 套能力。
2. 按现有五类题型吸收工作纪律，复用两个既有生成入口；未新造路由、权限表或工具。
3. 测实际 ask 计划时发现研报材料 `kol_review` 信封被后续分类为 `financial_analysis`；
   只修规则投递的意图丢失，保留显式 override 优先。普通自然语言误路由没有全面修复。
4. 复读生产风远画像，发现另一会话已经完成四批写入和 7 张结构化规则。
   本轮不重复 ingest 或覆盖；旧 README 的“一条未写”增加后续状态指针。
5. 工具描述变化触发生成目录保鲜门，正式重生成 `docs/runtime/tools.md`。
6. 代码提交 `ae86336c`，推送并建立 PR #774（文档头 `b2e5951b`）；2026-09-17 经独立 QC 与完整门禁后由用户确认合入 main（`c67413c7`，见文末）。固定干净提交重跑相关回归。

## 决策与被否方案

| 选择 | 被否方案 | 理由 |
|---|---|---|
| 单一题型规则供两条引擎消费 | 新建平行八套 skill/owner | 已有能力在，只缺增量规则；不制造新入口 |
| 生成规则明确标软约束 | 把提示词称作程序化审查门 | 是否读懂财报/因果等不能由关键词或标题验真 |
| 现有权限与证据门不变 | 直接抄 memory_write、通用 shell | 外部接口不是本仓授权依据 |
| 旧 ask 意图投递修复 | 本轮扩一套关键词路由 | 只修已有识别信号丢失，避免扩大题型面 |
| 风远只核已有生产文件 | 按旧台账再次整包抽取 | 已有另一会话写入，重做可能重复或覆盖 |

逐项来源、拒绝迁移项及效果边界：
[工作纪律吸收记录](../learning/knevo-distill/workflow-absorption-2026-09-16.md)。

## 验证

- 固定干净 `ae86336c15f69a3ae6db40f10b3d0d2c8ad51382`：575 passed / 0 failed，
  收据 `~/.finance-runtime/test-receipts/20260916T141351Z-ae86336c.json`，dirty=false。
- 全仓 Ruff、pre-commit（层级/路径/字段/dataset/工具可达性/运行目录）通过。
- 旧风远考卷 2 已知 + 1 边界通过，API 可见 24 篇。旧卷不覆盖新增全部规则。
- 能力图谱审计 exit 0；新增节点按本分支符号核对为 PENDING，默认主树仍旧且脏。
  其他在途/未校验项不因 exit 0 变成已部署。
- 本轮没跑全仓 pytest、前端/e2e、完整 registry 发布门禁、真实模型 A/B 或独立 QC。
- 健康接口 22:09 仍是生产 `db2963d4fbaa`、healthy、source_dirty=false；未切生产。

## 记忆 PR 查询

按 elevemem / EvolveMem / EverMem / mem0 及变体，查 finance 全分支日志与 Gitea PR 标题/正文，
以及 agent-memory、harness-reference、知识库等资料/PR，未唯一定位用户指定项。
旧 GitHub #324 合并记录存在于本地（memory quality review），现在 origin API 查询 404，
不能据此给指定 PR 状态。已确认的相关项是六 slice `230076a7`、Gitea #41 `bcde2851`
离线候选链，以及 #692 方法飞轮；它们都不是找到目标名称的证据。
`bcde2851` 是当前部署 revision 的祖先。Mem0 在旧审计中是设计参照，不是本仓换装其框架。
需要用户给目标 PR 链接、编号或准确项目名后补最终定位。

## 后续与禁止项

PR #774 已于 2026-09-17 由用户确认合入 main（`c67413c7`）。合并前独立 QC 在合并预演 `47adcfe9`（merge-tree 于 `gitea/main@0ab15e9b`）上完成：全量 pytest 11395 passed / 0 failed（收据 `20260916T170425Z-47adcfe9.json`，`check_test_receipt.py` 八项全过）、ruff 0、vitest 107、e2e 34 passed / 2 skipped、registry 五项 exit 0；代码复核无路由 / 工具 / 权限扩张，读数留在 PR #774 评论。已随 `ce0097185443` 于 2026-09-17 01:19 切 8792（health 三读全对、readiness 13/13、长电题 grounded 探针 `run_20260917_012253_640026` 通过：fact_stock_daily×8、数据日 09-15 == 库内 max；收据 `~/.finance-runtime/cutover-20260917-ce009718-8792.md`）；inflight 交接已随合入归档删除。
五类规则效果需隔离模型样本验证；不能用 575 项接线回归称质量提升。
三处 Knevo 自述矛盾保留；W3 阈值仍不启用；冻结 28 题及 q18 runner 未动；B 线未擅自暂停。
本轮没有新增跨项目工具：复用现有生成器、审计器、测试收据；不修改已有他改的 harness-reference/BUILD.md。
