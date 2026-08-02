# Handoff：GLM Continuous Agent Runtime

更新时间：2026-07-22（Asia/Shanghai）
状态：暂停在 Task 1 完成后，尚未进入 Task 2；没有切换 8792，没有合并 `main`。

## 目标

实现一个 provider-neutral（与模型供应商无关）的连续研究 Episode：长尾金融问题由同一个 GLM 对话连续决定“下一步查什么、如何改写、何时停止”，复用仓库现有只读工具、证据链和 verifier；与旧 Workbench 做隔离 A/B，证明是否解决“端到端成功但回答仍模板化/答非所问”。

第一阶段只验证连续上下文这一变量。GPT/OpenAI Agents SDK、headless、上下文压缩、UI/SSE 接入和 canonical 8792 灰度均暂不做。

## 当前代码位置

- Worktree：`/Users/a77/.codex/worktrees/finance-task-fulfillment`
- 分支：`fix/agent-harness-monotonicity`
- 当前工作区：clean
- 主仓库 `/Users/a77/finance-workspace-private` 的脏改动没有触碰
- 设计规格：`docs/superpowers/specs/2026-07-22-glm-agent-runtime-design.md`
- 实施计划：`docs/superpowers/plans/2026-07-22-glm-continuous-agent-runtime.md`

## 已完成提交

1. `7bc8dcff docs: define GLM agent runtime boundary`
   - 确立 Workbench control plane → continuous episode → tool registry → evidence/verifier 的边界。
   - 明确一条 Episode 保留原始 assistant action、tool request、原始 observation、trace、gap 和终止判断；不保存隐藏思维链。

2. `1762d5dd docs: plan glm continuous agent runtime`
   - 8 个任务的 TDD 实施计划，包含文件、测试、命令和 A/B 验收标准。

3. `56deed9f fix: close continuous runtime control seam`
   - 初版 `TurnControlCore`、runtime capability projection、5 类 route-table TaskFrame 映射。

4. `a9b8a727 fix: harden control projections for episode`
   - 根据独立规格审查修复真实 seam 缺陷。

## Task 1 已完成内容

修改文件：

- `intelligence/services/task_frame.py`
- `intelligence/services/evidence_capabilities.py`
- `intelligence/services/turn_control_core.py`
- `intelligence/tests/test_task_frame.py`
- `intelligence/tests/test_turn_control_core.py`

已锁定的不变量：

- stable knowledge / model reasoning 且没有当前事实需求时，进入 `non_research`，不调用检索。
- clarification 是阻塞终态：`needs_retrieval=False`、`capabilities=()`，不启动研究。
- 复合问题“什么是双红，现在哪些板块双红”不会被 `concept_definition` 误杀；validated decision、TaskFrame policy、evidence plan 任一要求当前证据时进入 research。
- 旧 lane 返回 chat 不能把金融 TaskFrame 降为零检索；research 必须有新的 registry capability 名称。
- `execution_route` 不再冒充 `question_type`：chat/meta/clarify 使用真实终态键，research 使用经过验证的题型。
- pending `TurnIntent` 优先保留原始 TaskFrame；intent-only follow-up 会投影 `question_type/subject/timeframe/required_outputs`，不会被无关 `previous_frame` 覆盖。
- 真实 default controller 注入 route JSON 时，`quick_fact`、`theme_track`、`kol_review`、`comparison_analog`、`trade_advice` 不会退成 `general_finance_qa` 或粗粒度 owner 题型。
- 旧能力名显式映射到新工具名并过滤：`market_quote→market_data`、`market_news→news_search`、`graph→graph_lookup`、`filings→l3_lookup`、`financials→evidence_lookup`、`web_fetch→web_search`、`memory→kb_search`；旧 alias 不得泄漏给 Episode。
- `TurnControlCore` 仍是旁路，没有生产 consumer；旧 TurnController 的能力 namespace 未改。

## 已验证

实现者报告：

```text
python3 -m pytest -q intelligence/tests/test_turn_control_core.py \
  intelligence/tests/test_task_frame.py \
  intelligence/tests/test_turn_controller.py
=> 115 passed in 0.20s
```

规格复审已通过（独立审查者）：

- 聚焦回归：121 passed
- controller/query/conversation 回归：117 passed
- `git diff --check`、`compileall` 通过
- 没有 P0/P1/P2 规格问题

代码质量复审在用户要求 handoff 时被主动暂停，不能把 Task 1 标记为最终质量批准；恢复后应先完成这一审查。

## 尚未完成

按实施计划，下一步从 Task 2 开始：

### Task 2：provider-neutral runtime contract

创建：

- `intelligence/services/agent_runtime.py`
- `intelligence/tests/test_agent_runtime.py`

定义并测试：`ModelToolCall`、`ModelTurn`、`AgentModelClient`、`OutputEvidenceBinding`、`EpisodeEvent`、`AgentUsage`、`AgentOutcome`、`AgentRuntime`。`AgentOutcome` 要校验 `task_frame_hash` 不变、事件序号连续，且 provider-specific 对象不得越过接口。

### Task 3：tool schema

在 `research_tool_registry.py` 增加受授权 capability 过滤后的 OpenAI-compatible `tool_definitions()`，不泄漏 runner 实现。

### Task 4：continuous episode

创建 `agent_episode.py`：

- 一次创建 messages，之后只 append，不重建 `[system,user]`。
- 记录 assistant tool-call 原文、tool result 原文、evidence hashes、ProviderTrace、错误和 gap。
- 未知工具、重复 query、工具异常都回到同一个 Episode，不偷偷切旧管线。
- 只允许一次 invalid-action repair；预算耗尽返回 `partial`，不调用无关模板。
- terminal content 采用结构化 `FINAL_JSON`，必须声明 status/draft/gaps/bindings；完成不能绑定未知 evidence hash。

### Task 5：GLM adapter

创建 `glm_agent_runtime.py`，包装现有 `llm_refine.chat_with_tools`，把 provider message 转为 `ModelTurn`；Episode 核心不依赖 `LLMProvider`。

### Task 6：contract factory + verifier

创建 `episode_factory.py` 和 `episode_verifier.py`，从 TaskFrame 直接构造 `ResearchTaskContract/ResearchRunContext`，不能 import `conversation_orchestrator.py` 私有 builder；完成状态只能被 verifier 降级，不能被 verifier 越权升级。

### Task 7：隔离 A/B

创建 `scripts/run_agent_episode_ab.py`，支持 dry-run、GLM episode arm、bare arm 和读取已保存的 canonical-8792 current arm；不切 8792，不把缺少的 current answer 伪造成结果。

### Task 8：验证报告

先跑脚本化测试，再跑真实 GLM 五题：

1. `昨天的反弹能持续多久`
2. `科创50你认为反弹空间有多少`
3. `瑞华泰的合理估值`
4. `这一周行情下跌的主要原因是什么`
5. `目前市场的主线是什么`

比较任务对齐、证据相关性/时效、required-output 覆盖、unsupported claims、重复检索、延迟、LLM/tool 次数。Episode arm 不得低于现有 bare-model capability floor。

## 恢复命令

```bash
cd /Users/a77/.codex/worktrees/finance-task-fulfillment
git status --short
git branch --show-current
git log --oneline -5
```

恢复后第一件事：

1. 对 `a9b8a727` 做代码质量复审并记录结论；
2. 若通过，将计划中的 Task 1 标为 completed、Task 2 标为 in_progress；
3. 继续用 `subagent-driven-development`，每个任务都执行“实现者 → 规格复审 → 代码质量复审”；
4. 每个任务独立提交，避免把连续 loop 与控制 seam、verifier、A/B 混成一个不可回滚提交。

聚焦测试命令：

```bash
python3 -m pytest -q \
  intelligence/tests/test_turn_control_core.py \
  intelligence/tests/test_task_frame.py \
  intelligence/tests/test_turn_controller.py
```

## 不要做的事

- 不要在 `/Users/a77/finance-workspace-private` 主仓库直接改动。
- 不要切换 `/Users/a77/finance-workspace-runtime` 或端口 8792。
- 不要合并 `main`，除非用户单独确认。
- 不要把 GLM adapter 直接接进旧 `conversation_orchestrator`，在真实 A/B 之前保持 sidecar。
- 不要用重新压缩的 state summary 替代连续 messages；这会重新引入本次要验证的根因。
- 不要为了“回答完整”放松 evidence/verifier；Episode 可以表达 gap，但不能编造。

## 当前判断

Task 1 证明了控制接缝此前确实存在多个假绿路径，但还没有证明连续 Episode 会改善最终回答。只有完成 Task 2–8、拿到同题三路 A/B 结果后，才能判断根因是“消息连续性”为主，还是还叠加了模型思考预算、工具粒度、提示词和展示出口问题。
