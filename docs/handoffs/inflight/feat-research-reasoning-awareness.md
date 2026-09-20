# 研究求证意识候选

## 这个分支做什么
培养机制求证、竞争解释与接受反证的习惯，不固定流动性视角或研究模板。

## 当前状态
代码与实验记录已提交 `696e309a`，未 push/PR/合 main/部署。
树：`~/fwp-wt-research-reasoning-awareness`，基座 `728f3271`。
`FINANCE_RESEARCH_REASONING` 默认 off。8792 仍为 `bf662e9310ff`；两份测试服务已关闭。

## 决策与被否方案
- 用动态题型规则与原工具预算事件提醒；否了固定视角菜单、强制反思轮与新增权限。
- 不复制 `feat/adaptive-research-loop` 的 PLAN 视角载体，不依赖其未合代码。
- 不撤知识门控、不注入整份流动性笔记；否了“提示送达即证明有效”。
- 背景/被否方案：`docs/handoffs/2026-09-20-research-reasoning-awareness.md`。

## 未验证 / 已知边界
行为验收未通过：行情开启组仍有过强归因；虚构材料两臂都被 evidence 合同拦下。
反证追问开启组 unknown E1 降级、关闭组交付；n=1 不能认定开关导致回归或改善。
quick_fact 确认不注入，但两臂都额外查数/展开。旧基线仍有全局强制领域规则，尚未厘清适用条件。
未跑剩余留出场景、重复配对、独立语义审核、前端/E2E及合流门禁；不启用生产。

## 下一步
先协同材料/E2 owner 处理材料前提资格、续轮证据身份和窗口，再处理领域规则适用边界。
保留原失败证据，用 fixture 新场景及留出题重验；不放松证据门、不把旧答案变事实。
合并与部署须用户确认。

## 已验证
新测试44项；相关回归570项；全仓 Python 11957P/85S/2X，exit0；Ruff及提交门禁绿。
全量是未提交候选树收据 `~/.finance-runtime/test-receipts/20260920T160916Z-728f3271.json`，不是合流收据。
真实 Workbench 4组8run；仅证实开场/批后送达与 quick_fact 排除，不证明质量增益。
详情：`docs/verification/2026-09-20-research-reasoning-awareness.md`；原件 `~/.finance-runtime/research-reasoning-20260920/`。

## 踩过的坑
开场原文在 `outcome.events`，顶层 events 已脱敏；verifier 含事件副本，不递归累加批数。
probe 打印的用户产物路径写死生产根，实际在各臂 users/。复用既有量具，无新通用工具需沉淀。
