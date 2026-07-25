# Agent Runtime Backends 验收记录

日期：2026-07-25
状态：三路执行内核已隔离实现并完成 GLM 真实 A/B；GPT 与 Codex headless 仍是未完成的质量上界对照，不得宣称已验收。

## 版本与运行边界

| 项目 | 值 |
| --- | --- |
| source revision | `c46736674964d96dfa72b2c8d0fd4ff75a4170f5` |
| code root | `/Users/a77/.finance-runtime/agent-runtime-backends-c4673667` |
| finance root | `/Users/a77/finance-workspace-private` |
| dirty | `false` |
| 最新市场数据 | `2026-07-24` |
| canonical `main` / 8792 | 未修改、未切换 |

隔离端口：

- `8795`：`continuous_glm`，自建 Continuous Episode 控制臂；
- `8796`：`sdk_glm`，OpenAI Agents SDK runner + GLM OpenAI-compatible provider；
- `8797`：`codex_headless`，仅 benchmark，不能作为生产依赖。

三个端口的 `/api/health` 均报告同一 revision、`dirty=false`、同一 finance root 和 `2026-07-24` 数据边界。运行时失败不会静默切换到另一 backend。

## 共用契约

三路都经过同一 `TaskFrame`、`ResearchRunContext`、只读 `ResearchToolRegistry`、预算/截止时间、`AgentOutcome`、结构 verifier、语义 verifier，以及 Conversation/Run/artifact/SSE/UI 投影。

实现入口：

- `intelligence/services/agent_runtime.py`：provider-neutral runtime contract；
- `intelligence/services/continuous_turn_adapter.py`：唯一产品 adapter；
- `intelligence/services/episode_tools.py`：白名单工具组成；
- `intelligence/services/episode_verifier.py` 与 `episode_semantic_verifier.py`：出口校验；
- `intelligence/services/agent_runtime_factory.py`：显式 backend 选择与 readiness；
- `scripts/run_agent_runtime_benchmark.py`：冻结题集、独立 arm、统一 artifact。

确定性技术位等头部问题继续走原有 fast path；本轮 backend 实验只比较需要研究循环的任务。

## 九题真实 A/B

产物：

- `/Users/a77/.finance-runtime/evals/agent-runtime-backends-2026-07-25-final.json`
- `/Users/a77/.finance-runtime/evals/agent-runtime-backends-2026-07-25-final-blind.json`
- `/Users/a77/.finance-runtime/evals/agent-runtime-backends-2026-07-25-final-review.json`

结果摘要：

- 9 题 × 2 GLM backend = 18 个 arm，全部有终局产物；TaskFrame contract gap `0`；citation `18/18`；数据截止均为 `2026-07-24`；重复检索 `0`；
- `continuous_glm` 协议问题 4 个，`sdk_glm` 协议问题 0 个；
- Continuous 中位延迟约 `53.5s`，SDK 中位延迟约 `48.5s`；
- 盲评总分：Continuous `195`，SDK `175`（6 维、0-4 分制；不是协议分）；
- Continuous 在反弹持续性、题材比较、反事实主线、方法论和部分谨慎性上更好；SDK 在估值、周跌归因、上下文追问、协议稳定性和延迟上更好；技术位结果一致。

这说明 SDK 不是单调优于自建 Episode。当前可以证明的是：SDK runner 的协议稳定性/延迟更好，但在 GLM 同模型下，整体答案质量尚未超过 Continuous。

## UI / Run / SSE 验收

在 `8796` 新建问答并提交：`目前市场的主线是什么？给我你的判断依据`。

实际 run：`run_20260725_095639_774077`。

验收证据：

- `/api/runs/{id}`：`status=completed`、`source_date=2026-07-24`、无 degrade；
- `/api/runs/{id}/report`：`as_of=2026-07-24`；
- `/api/runs/{id}/context`：15 条 `bound_evidence`，全部 `status=hit`，无 gap；
- UI 正文直接回答半导体主线，并给出持续性、盘面验证、阶段属性、风险与确认条件；
- UI 研究检查器显示“证据 15、产物 3”，没有 backend、model、trace、内部控制字段泄漏到正文；
- `/api/runs/{id}/events`：SSE 只出现一个终局 `event: run`，并在此前保留 trace/citation/answer snapshot；最终状态为 `completed`；
- 页面截图在本次验收会话中取得，证明正文与证据检查器同时可见。

## 回归

在隔离 runtime：

```text
2864 passed, 3 skipped, 8 warnings
```

前端：

```text
Vitest: 62 passed
pnpm lint: passed
pnpm typecheck: passed
pnpm build: passed
```

警告仅为既有 `datetime.utcnow()` 弃用提示，不属于本次 backend 变更失败。

## GPT 与 headless 边界

`sdk_gpt` 已实现并有离线/缺凭证 readiness 测试，但当前环境没有 `OPENAI_API_KEY`，所以没有真实 GPT 分数。不得把实现存在当成 GPT live 验收。

`codex_headless` 已实现为独立 subprocess benchmark adapter，并新增显式 `local_exec` 传输：通过 Codex Desktop 的 `28080/api/exec` 在当前已登录会话中启动 CLI，不需要 `OPENAI_API_KEY`。本次 local route smoke 已确认 `/api/ping`、CLI 启动和 adapter 嵌套工具网关均连通；真实 Codex arm 最终被账号 `headless_usage_limit` 阻塞。因此它仍只能作为待补的质量上界，不是本轮有效的第三臂，也不应接入生产 UI。

## 结论与下一步

当前推荐把 `sdk_glm` 作为隔离的下一阶段 production candidate 继续观察：它的协议问题为 0、延迟略低，并在估值/归因/上下文追问上更稳；但在补齐 GPT live 和 headless 上界前，不切换 canonical 8792，也不能宣称已达到 Codex/Knevo 级别。

下一步按优先级：

1. 在不写入仓库的前提下注入 `OPENAI_API_KEY`，复跑同一冻结九题并加入盲评；
2. 解除或更换 Codex headless 账号额度后，复跑同一题集；
3. 针对 Continuous 的 4 个协议问题补回归，再决定是否扩大 SDK 灰度；
4. 只有三路比较结果达到设计文档的 production gate 后，另行提出 8792 蓝绿切换申请。
