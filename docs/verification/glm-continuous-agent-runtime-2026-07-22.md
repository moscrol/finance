# GLM Continuous Agent Runtime 验证报告

日期：2026-07-23  
代码分支：`fix/agent-harness-monotonicity`  
代码锚点：`e483b6d82dd61c8006be08d397baca22f7c2b71b`  
对照固定点：`7bc8dcff50747645b4b0c9bf27ba8b53118a3832`

## 1. 结论

连续 Episode 的核心假设得到支持：在不切换 8792、不合并 `main` 的隔离
sidecar 中，五个验收问题的 Episode arm 均未跌破 bare-model capability
floor；旧 Workbench 则有四题低于该 floor。确定性技术位仍走 fast path，
长尾问题由同一条 message history 中的 GLM 自主选择仓库只读工具、接收原始
observation、继续规划并输出带 evidence hash 的答案。

本报告不建议立即切换生产 runtime。单题隔离运行已经可用，但同一批连续五题的
压力运行仍暴露 GLM provider 抖动；估值题还暴露同轮多工具被串行执行后，慢工具
挤占强制行情工具预算的问题。两者不影响本阶段“连续性假设是否成立”的判断，
但属于 canary 前必须显式处理或接受的可靠性限制。

## 2. 需求逐项核验

| 需求 | 权威证据 | 结论 |
| --- | --- | --- |
| 单一不可变 TaskFrame | `TurnControlCore` 产出 hash；Episode 首事件和所有模型/工具事件携带同一 hash；单元测试覆盖 hash 变化 fail-closed | 通过 |
| 连续 Episode | `ContinuousAgentEpisode` 只创建一次 messages，逐轮追加 assistant action 与原始 tool observation；第二轮历史回归测试通过 | 通过 |
| 复用 repo 工具 | registry 接入 market、mainline、KB、graph、evidence、news、web；显式授权时接入现有 L3 disclosure lookup | 通过 |
| 白名单、预算、去重 | registry capability allowlist、ResearchDeadline、max_steps、normalized query ledger 均在 Episode 外确定性执行 | 通过 |
| 确定性 fast path | 科创50技术位走 `deterministic_fast_path`，0 次 LLM、1 次行情工具 | 通过 |
| 证据审计 | finish 只能绑定本 Episode 收集的 hash；未知、重复或错误工具类型均降级；语义 grounding judge 仍是后续 presenter 集成 gate | 结构门通过；语义门未接生产 |
| GLM adapter 不泄露 provider 对象 | provider payload 转换为 `ModelTurn`；新增 `provider_attempts` 记录物理 adapter 尝试 | 通过 |
| 旧 Workbench 三臂 A/B | 保存 8792 current arm，逐题运行相同 GLM/temperature/thinking profile 的 bare 和 Episode arm | 通过 |
| 不切 8792、不合并 main | 所有 live 产物均为 `runtime_switched=false`、`canonical_runtime_touched=false`；分支未合并 | 通过 |
| GPT/Agent SDK 后置 | diff 未引入 GPT、Agents SDK、headless 或生产 canary | 通过 |

## 3. 测试证据

聚焦测试：

```text
63 passed
60 passed（A/B runner、monotonicity 与相关 runtime 回归）
```

完整测试：

```text
2091 passed, 11 failed
```

11 个失败全部位于 `test_subconscious.py` / `test_userspace.py` 的本机用户路径
污染用例；相关实现与测试相对 `7bc8dcff...HEAD` 的 diff 为零，失败集合与本分支
修改前一致。本分支没有隐藏或改写这些基线失败。

## 4. 真实五题 A/B

为了避免五题连续轰击同一 GLM Coding endpoint 把 provider burst failure 混入
Episode 架构变量，最终验收按题独立运行；每题仍包含 bare、保存的 8792 current、
Episode 三臂。两条模型臂均为 GLM 5.2、temperature 0、thinking disabled；
Episode 额外拥有连续 history 与白名单工具。

| Case | 8792 延迟 | Bare 延迟 | Episode 状态 | Episode 延迟 | LLM 尝试 | 工具 | 证据 | 回答长度 |
| --- | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: |
| 反弹持续性 | 67.02s | 14.19s | completed | 72.85s | 3 | 6 | 29 | 2319 |
| 科创50空间 | 63.44s | 20.65s | completed fast path | 2.83s | 0 | 1 | 0 | 219 |
| 瑞华泰估值 | 86.17s | 31.44s | honest partial | 57.16s | 2 | 4 | 13 | 1243 |
| 周跌原因 | 36.54s | 16.02s | honest partial | 49.40s | 2 | 3 | 13 | 2001 |
| 当前主线 | 21.91s | 22.58s | completed | 45.94s | 2 | 3 | 16 | 2038 |

逐题结果：

- 反弹持续性直接给出 `3–5 个交易日`，并以量能、市场宽度、科技主线承接和
  失效条件约束判断；不再混入生猪或半导体涨价材料。
- 科创50直接给出 3.3%、6.9%、21.2% 三档压力空间、支撑区和失效位；保留
  确定性 fast path 的低延迟优势。
- 瑞华泰本轮因 serial tool starvation 未取得行情/财务锚，只输出估值方法与缺口，
  没有编造目标价；这是诚实 partial，但仍是五题中最弱的一题。
- 周跌原因先校正用户前提：窗口实际只跌约 0.40%，主要是前半周急跌、后半周
  修复；把结构性获利回吐与没有时间对齐新闻支撑的外部原因明确分层。
- 当前主线直接判断为“科技硬件存量主线 + 有色/电力新启动支线 + 大金融防御”，
  并给出同日板块、量能和次日证伪条件。

## 5. Capability Monotonicity

评分采用仓库既有五维 0–4 rubric：directness、coverage、relevance、
truth boundary、usefulness。分数由保存的完整答案人工判定；这不是自动事实判断，
原始答案与评分输入均保留在 `/tmp` 可复核。

| Case | Bare | Current | Episode | Episode floor |
| --- | ---: | ---: | ---: | --- |
| 反弹持续性 | 0.75 | 0.40 | 0.95 | PASS |
| 科创50空间 | 0.65 | 0.35 | 1.00 | PASS |
| 瑞华泰估值 | 0.75 | 0.75 | 0.80 | PASS |
| 周跌原因 | 0.65 | 0.40 | 1.00 | PASS |
| 当前主线 | 0.70 | 0.45 | 1.00 | PASS |

总体 evaluator 输出为 `failed`，原因是 current arm 有四项 capability regression；
Episode arm 五项全部通过，`failure_reasons=[]`。不能把总体 `failed` 改写成全局
PASS，但它恰好证明旧 Workbench 的问题和 Episode 的改善方向。

## 6. 压力运行与剩余限制

同一进程连续运行五题时，GLM endpoint 出现两次 `TimeoutError` 和一次
`URLError`，产生三个空的 honest partial。`URLError` 已纳入一次有界 retry，
且物理 adapter 尝试现在会计入 usage；单题隔离复测均取得非空结果。该证据说明：

1. Episode 正常路径的质量已通过，但单 provider burst reliability 尚未通过；
2. 不能靠挑选一次成功重跑宣称生产稳定；
3. 第二 provider（后续 GPT）或 finalization recovery 仍有价值；
4. 设计明确排除初版 context compaction，因此压缩恢复必须单独审批，不能暗加。

估值题还显示同一 model turn 的多个独立只读 tool call 当前被串行执行。慢 RAG/Web
可能先耗尽 research window，使后续 mandatory market data 得到零预算。QueryLedger
本身支持不同 key 并行 single-flight，但线程执行需要显式传播 ContextVar，并按原
tool-call 顺序回填消息，才能兼顾并发与可回归 transcript。建议下一阶段建立内部
`ToolBatchExecutor`，不增加新的外部 route/pipeline。

另外，当前 structural verifier 只证明 hash、授权工具、required output 和 mandatory
capability 的结构绑定；原计划第 539 行明确把 semantic claim judging 留到后续
presentation gate。sidecar 结果不得被描述成已经完成生产语义审核。

## 7. 双轴 Code Review

### Standards

没有仓库规范硬违反。接受的判断项：`AgentEvidence` public projection 有两处重复；
question type 字符串仍跨多个模块；`agent_episode.py` 同时承载循环、预算、协议和
ledger，后续可深化模块，但不应在验证前做无关重构。

### Spec

- 已修：L3 被授权但无 runner（`0212b295`）。
- 已修：bare/Episode thinking profile 不一致（`0212b295`）。
- 已修：adapter retry 未计入 usage（`0212b295`）。
- 已修：A/B current arm 丢弃已有运行元数据（`e483b6d8`）。
- 已补：本验证报告。
- 不采纳为本阶段缺陷：要求 structural verifier 立即做语义支持判断，与已批准计划
  第 500、527–539 行冲突；该能力保留为 presenter 集成 gate。

## 8. 可复核产物

```text
db1045818fe9aeb132d6c76c763b5dc4ac85b8feab9aa22ddc5af6dd717a9b89  /tmp/glm-agent-episode-rebound-0212b295.json
446ce7e924be45589499c63102491342191b4e1772a85780507777d9904f7d0d  /tmp/glm-agent-episode-index-0212b295.json
ded02b62b9521a2998d85e8c7bb153942204a555106de1390a29a73537065bd8  /tmp/glm-agent-episode-ruihuatai-0212b295.json
66942f19d4a71c546fdca4c4310680a3fb6fb51659dfd70870137369f08ac6e0  /tmp/glm-agent-episode-weekly-cause-0212b295.json
858b9942073af49222be9130f547099fa807f2bb228904c11bd44b40c156230b  /tmp/glm-agent-episode-mainline-0212b295.json
962ee2a9b7ea39bcd4d5f57183e1acc94fbca29811cf12e4b1609428d3fd91b3  /tmp/glm-agent-episode-five-scored-e483b6d8.json
a8bf50e344f4f975651c443873b635de4f2025a423f8a2fd3e3d5ac85c365d5b  /tmp/glm-agent-episode-five-monotonicity-e483b6d8.json
617a3720f807db1958eb4274c357b3176c1fe7de6f5b70fea33b6d63d737b75b  /tmp/glm-agent-episode-five-task-aware-canonical.json
```

## 9. 当前决策

保持 sidecar；不切换 8792，不合并 `main`，暂不接 GPT/Agents SDK。Continuous
Episode 可以作为下一阶段的候选执行核心，但 canary 前应先决定是否批准同轮只读
工具并行，以及是否允许失败时的压缩 finalization recovery。
