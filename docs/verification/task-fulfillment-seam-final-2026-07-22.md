# Task Fulfillment Seam 验证记录（2026-07-22）

## 范围与版本

- 实现分支：`fix/task-fulfillment-seam`
- Task Fulfillment 代码提交：`b1531247ec53f878cb4a40e6df008bbdf99fe5b6`
- Overview 双根修复提交：`5c9adfe515427a9cbc16e6713c628ca54892e64f`
- 候选基线：`fix/unified-evidence-capabilities`（`db86e860`）
- `main` 与 canonical `8792` 未修改、未合并、未切换。
- 实现说明：[`2026-07-22-task-fulfillment-seam-design.md`](../superpowers/specs/2026-07-22-task-fulfillment-seam-design.md)
- 执行计划：[`2026-07-22-task-fulfillment-seam.md`](../superpowers/plans/2026-07-22-task-fulfillment-seam.md)

## 这轮验证了什么

这轮不再把“请求已完成、检索跑过、模型返回过”当成用户任务已完成。最终公共回答在渲染前经过独立的 task-fulfillment gate：

1. 必须有问题所要求的直接结论或明确、问题相关的缺口；
2. 声称已经完成的结论必须能回指证据，且证据没有过期；
3. 仅有“找到来源/证据边界/下一步补查”的控制面文字不能充当任务证据；
4. 不满足契约时，保留可核验的缺口短答，清除候选/来源/verified facts 的误导性展示，状态标为 `partial/degraded`；
5. `transport_status`、`research_status`、`answer_status` 分开记录，避免 HTTP 或研究完成掩盖答案未完成。

它与原有真值硬门、EvidenceAtom/grounding gate 是串联关系，不替代它们，也不通过放松事实校验来换取自然语言完整度。

## 全量回归

在候选分支执行：

```text
1859 passed, 2 skipped, 11 failed, 3 subtests passed
```

11 个失败全部集中在既有 `subconscious/userspace` 本机路径/环境隔离测试，涉及默认 `agent-memory`、用户目录和潜意识 buffer 的旧运行环境假设；未出现本轮 task-fulfillment、orchestrator、answer rendering、runtime provenance 或语义验收新增失败。候选基线同类失败已存在，故不把它们误报为本轮回归。

## 隔离 runtime 端到端验收

验证 runtime：`http://127.0.0.1:8795`，代码根为本分支 worktree，数据根为私有金融数据目录；`/api/health` 的 source revision、dirty 状态、代码根、Python 运行时和依赖指纹全部通过。验收脚本：`scripts/semantic_acceptance.py`。

固定三问：

| 问题 | 结果 | 语义验收 | 说明 |
|---|---|---|---|
| 科创50现在的支撑位在哪里，失效条件是什么 | `completed` | 通过 | 走确定性指数技术位路径，返回真实日线、支撑区、截止日和失效条件。 |
| 明天是反弹还是继续下跌，分别给出理由 | `degraded` | 通过 | LLM 未配置时保留结构化行情与双情景理由，不伪造概率；只降级自然语言精修。 |
| 你觉得目前市场的主线是什么，给我你的判断依据 | `degraded` | 通过 | 当前主线表相对最新交易日滞后，系统明确返回“直接判断仍缺少”的问题相关 gap，不把旧题材列表冒充当前主线。 |

本轮验收汇总为 `semantic acceptance outcome: passed`。`degraded` 是诚实的运行状态，不等同于静默模板成功：用户最终可见回答必须包含直接回答或明确缺口，并经过语义验收。

## 关键架构修复

- 新增 [`intelligence/services/task_fulfillment.py`](../../intelligence/services/task_fulfillment.py)：把“任务是否被回答”做成可测试的深模块，并提供 fail-closed AnswerSpec 投影。
- `conversation_orchestrator.py` 在最终渲染前执行 gate；不完整答案不再以 `completed/verified_fallback` 伪装。
- `ask.py` 不再把仅有来源列表或证据边界提升成长尾问题的直接结论；mainline stale boundary 只能生成 gap。
- `ResearchDeadline` 和 LLM/query ledger 的预算痕迹在 owner/agent 之后统一输出，减少接缝处的重复计费和 trace 断裂。
- `_market_db_path()` 统一代码根与数据根选择，避免 worktree 有代码、运行时却读取另一份空/旧市场库。
- 新增 [`intelligence/services/runtime_provenance.py`](../../intelligence/services/runtime_provenance.py)：health 输出代码 revision、dirty、路径和依赖指纹，防止“验的是一个版本、跑的是另一个版本”。
- 新增 [`scripts/semantic_acceptance.py`](../../scripts/semantic_acceptance.py)：验收最终用户消息和 `answer_status`，而不是只看 API 200 或 run completed。

## Overview 双根故障修复补充

用户在隔离 8795 首页观察到“数据缺失，全部是 7 月 1 日”。直接 API 复现为：

```text
as_of_date=None
signal_date=2026-07-01
database=missing
agent_artifact=<code worktree>/market_feature_store/exports/2026-07-01-daily-agent.json
```

根因不是私有数据过期：DuckDB 多数核心表最新为 `2026-07-21`，正式 Daily Agent 最新为 `2026-07-20`。问题是 `/api/workbench/overview` 将代码 `repo_root` 同时用于查找 DB 和 exports；clean worktree 没有私有 DB，只残留 7 月 1 日测试/版本化产物。对话 Orchestrator 的双根修复没有覆盖这一条首页链路。

修复后，应用 composition root 将 `default_paths().finance_root` 显式注入 Overview，服务参数也改名为 `finance_root`；health 同时公开 `code_root` 和 `finance_root`。公共 API 回归使用两个不同目录，确保旧 worktree 产物不能覆盖私有数据根。

隔离 runtime 原始复现已转绿：

```text
as_of_date=2026-07-21
signal_date=2026-07-20
market_stage=反弹阶段
agent_artifact=market_feature_store/exports/2026-07-20-daily-agent.json
missing_database=false
code_root=/Users/a77/.codex/worktrees/finance-task-fulfillment
finance_root=/Users/a77/finance-workspace-private
source_dirty=false
```

验证结果：

- Overview/API/runtime provenance 聚焦回归：`76 passed`
- intelligence 全量：`1934 passed, 11 failed`；11 个仍为既有 `subconscious/userspace` 本机路径/环境失败，本轮无新增失败
- 当前 revision 再跑三问：`semantic acceptance outcome: passed`

## 已知边界与后续优先级

1. 本轮 task gate 是确定性契约检查，不是完整的 LLM/NLI 因果蕴含判定；后者应作为证据语义审判层的增强，不应替代现有 fail-closed。
2. 当前隔离环境没有配置自然语言 LLM provider，因此 forecast/mainline 的“精修表达”降级是预期现象；真实 provider smoke 仍需在目标 runtime 的凭据与版本条件下单独验收。
3. mainline 数据新鲜度不足时，正确行为是报告 gap；要得到主线判断，先补齐同日主题/行业/强势股证据并重跑验收。
4. 合并与 8792 cutover 尚未授权；下一步应先 review 本分支，再在干净 detached runtime 运行同一 acceptance，最后才考虑原子切换。
