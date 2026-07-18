# Workbench P0 Routing Verification

- 日期：2026-07-16
- 分支：`fix/workbench-product-maturity-p0`
- 基线：`origin/main@07edd75`
- 范围：P0 Routing Maturity
- 结论：代码与本地验收通过；待 PR 复核，未合并 `main`，未部署 canonical 8792

## 1. 交付结果

本批建立了一个统一查询解析控制面：

1. `QueryResolver` 在通用意图分类前完成实体代码/名称锚定、主题 alias 匹配和追问指代分类。
2. 实体与主题词典来自知识库 relation，按 `mtime_ns + size` 文件指纹缓存；文件变化自动刷新。
3. `TurnController` 每轮只解析一次，并把同一 `QueryEnvelope` 交给 intent、lane 和 owner 决策。
4. `ResearchContract` 与 `ConversationOrchestrator` 复用同一追问分类，不再各维护一份 pattern。
5. 新增 `relation`、`company_mapping`、`market_change` 研究算子；关系和公司映射显式申请 `graph` capability。
6. 实体锚定保留财报、公告等具体任务类型，不再把所有已登记公司粗化成 `stock_deep_dive`。

## 2. 黄金路由矩阵

| Case | 输入 | 上下文 | 实际 subject | 实际 owner/lane | operators | 结果 |
|---|---|---|---|---|---|---|
| stock_entity_opinion | 中际旭创怎么看 | 无 | 中际旭创 | stock-deep-dive / research | — | PASS |
| theme_opinion | 光模块怎么看 | 无 | 光模块 | theme-research / research | — | PASS |
| logic_followup | 这个逻辑呢 | 中际旭创个股深挖 | 中际旭创 | stock-deep-dive / research | — | PASS |
| direction_followup | 这个方向怎么看 | 光模块题材研究 | 光模块 | theme-research / research | — | PASS |
| chain_followup | 这条链有哪些公司 | 光模块题材研究 | 光模块 | theme-research / research | company_mapping | PASS |
| marginal_change_followup | 边际变化呢 | 中际旭创个股深挖 | 中际旭创 | stock-deep-dive / research | market_change | PASS |
| relation_question | 光模块上游有哪些公司 | 无 | 光模块 | theme-research / research | relation, company_mapping | PASS |
| reference_without_context | 这个逻辑呢 | 无 | — | — / clarify | — | PASS |
| vague_opinion_without_context | 你怎么看 | 无 | — | — / clarify | — | PASS |

黄金集位于 `intelligence/tests/fixtures/workbench_routing_golden.json`，业务断言位于
`intelligence/tests/test_workbench_routing_golden.py`。测试使用最小 relation fixture，
不依赖生产知识库正文。

## 3. 自动化验证

### 3.1 Python

聚焦路由回归：

```text
139 passed in 0.76s
```

覆盖 entity anchor、query resolver、query understanding、controller、orchestrator、
skill router 与黄金路由集。

全仓测试（清洁环境）：

```text
1798 passed, 1 skipped, 8 warnings in 125.06s
```

8 个 warning 均为既有 `datetime.utcnow()` 弃用提示，与本批无关。

### 3.2 Frontend / Workbench

```text
eslint: PASS
TypeScript typecheck: PASS
Vitest: 56 passed
production build: PASS
Playwright E2E: 15 passed（desktop/tablet/mobile）
```

### 3.3 Registry

```text
check-parseability: PASS
check: PASS
backfill-tables --check: PASS
generate-views --check: PASS
```

当前 worktree 只 checkout 本仓，registry 跨仓项按脚本设计跳过；本仓一致性检查通过。

## 4. 环境隔离说明

本机 SessionStart 注入了 `FORESIGHT_USER`、`FORESIGHT_USERS_DIR` 和
`SUBCONSCIOUS_VAULT`。第一次全仓测试因此让用户空间测试读到了真实共享路径，表现为
11 个失败；清除变量后相关 49 项和全仓 1798 项均通过。

第一次 E2E 同样因继承 `FORESIGHT_USER`，页面写入用户与 API 查询的 `default` 用户不一致，
导致 12 个失败；清除该变量后 15/15 通过。结论是环境污染，不是产品代码回归。
后续 canonical runbook 和 CI 本地复现命令应显式建立清洁测试环境。

## 5. 架构取舍

- 采用确定性词典而非全量 LLM 路由：延迟更低、结果可复现、便于审计；代价是需要维护 relation。
- 采用进程内文件指纹缓存而非 Redis：适合当前单机 Workbench，零额外服务；未来多进程部署时可换成版本化快照或共享缓存。
- 研究算子与题型分离：`company_mapping` 描述“需要什么输出”，owner 描述“谁负责回答”，避免为每种问法创建新 owner。

这套“解析结果单一来源 + 控制面/执行面分离”也可迁移到客服 Agent、代码 Agent 和
多工具 RAG 系统；系统设计面试通常会追问如何避免重复分类、缓存失效和 LLM 路由不可复现。

## 6. 未完成边界

以下内容明确未在本批实现：

- P0.5：可终止 stage、取消 telemetry、snapshot readiness。
- P1：BGE-m3 常驻 worker、AkShare 独立数据环境、followups v2。
- P2：胜率看板、错因/批注候选审批闭环。
- canonical：未切换 `/Users/a77/finance-workspace-runtime`，8792 仍未部署本分支。

因此本报告只声明 **P0 Routing 本地代码验收通过**，不声明整个 Workbench 已达到最终成熟门。
