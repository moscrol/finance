# Cross-Harness Shared-Layer Audit

Date: 2026-08-03
Status: **trace normalization complete; fair paired A/B not eligible**

## Scope and fixed inputs

T4 的目标是把 Codex rollout 与自建 Workbench trace 先投影到同一套
`configure / intent / route / retrieve / observe / synthesize / stop` 词表，
再比较首次分叉。本轮只复用已经存在的收据，不启动服务、不调用模型、不重跑
A4，也不把旧失败样本重写成成功样本。

| input | source revision / identity | SHA-256 | normalized output |
|---|---|---|---|
| Codex headless five-case receipt | `e179b15c`，`gpt-5.6-sol`，cutoff `2026-07-24` | `cb7e0d1ad81b989e0c3b00d7d2af33d59a31073e1fd39e82beb0644a479d8b40` | `intelligence/eval/measurements/2026-08-03-cross-harness/codex-runtime-benchmark-e179b15c.json` |
| Workbench grounded daily-review trace (mapping smoke only) | `run_20260803_171452_043073` | `6ab2f09a196c64a566783d742022d9b428352640ff1c66893014dc0b58cebf56` | `intelligence/eval/measurements/2026-08-03-cross-harness/workbench-a4-daily-review-171452.json` |

归一化器是 `intelligence/eval/normalize_harness_trace.py`。Codex receipt
实际包含 5 个 case、32 个可读控制事件，其中 2 个 `tool_error` 保持
`unmapped`；Workbench smoke 有 8 个 native 事件、0 个 unmapped。输出只保存
事件身份、状态/计数摘要、时间戳和输入哈希，不保存 prompt、答案正文、工具
参数、stdout、绝对路径或凭据。

## Frozen task set

五题的题面、`as_of=2026-07-24` 和 task-frame hash 来自 Codex receipt，未在
两侧之间重新生成：

| case | question | Codex terminal observation |
|---|---|---|
| `rebound-duration` | 昨天的反弹能持续多久 | `partial / headless_timeout`，有 invalid action |
| `ruihuatai-valuation` | 瑞华泰的合理估值 | `completed / semantic_repair` |
| `weekly-market-cause` | 这一周行情下跌的主要原因是什么 | `partial / headless_timeout`，有 invalid action |
| `current-mainline` | 目前市场的主线是什么 | `completed / model_finish` |
| `unfamiliar-methodology` | 一个没有历史胜率的新题材，应该如何判断它是主线候选还是一天噪音 | `completed / model_finish` |

这里的“可读”不等于“成功”：5/5 有 artifact，终态是 3 个 completed、2 个
partial；特别是 `weekly-market-cause` 不是成功样本，不能用它支持能力胜负。

## Paired comparison result

旧 self-use 目录只留下了部分最终验收 JSON；对应的 Workbench
`trace.jsonl` 没有随这些五题收据保留。已有的 Workbench trace 是 A4
daily-review mapping smoke，不是上述五题的同题同 cutoff 对照。因此每一行都
按缺证据规则输出 `not_evaluable`，而不是把格式差异冒充行为差异。

| case | Workbench raw trace | pre_divergence_equivalence | first_divergence_step | primary finding | SDK relevance |
|---|---|---|---|---|---|
| `rebound-duration` | 缺失（self-use 终态无 run_id） | `not_evaluable` | `null` | 没有 paired trace | `false` |
| `ruihuatai-valuation` | 缺失（最终 JSON 无 trace） | `not_evaluable` | `null` | Codex 有结构完成，但无同题 Workbench 控制面序列 | `false` |
| `weekly-market-cause` | 缺失（self-use 为 protocol error） | `not_evaluable` | `null` | Codex 自身已 timeout/partial，不能当质量基线 | `false` |
| `current-mainline` | 缺失（最终 JSON 无 trace） | `not_evaluable` | `null` | 只有 Codex 侧 `completed/model_finish` | `false` |
| `unfamiliar-methodology` | 缺失（最终 JSON 无 trace） | `not_evaluable` | `null` | 只有 Codex 侧 `completed/model_finish` | `false` |

`first_divergence_step=null` 是证据不足的显式结果，不是“没有分叉”。如果
强行把 Codex 的首个 `tool_request` 与 Workbench 的 `intent` 对齐，会把
Codex artifact 没有保存 `thread.started/turn.started` 的可观测性缺口误判为
产品行为缺陷。

## Findings

1. **PRIMARY：旧 Codex artifact 的 trace 深度不足以做跨 harness 首次分叉。**
   `codex_headless_runtime.py` 只把 stdout JSONL 投影成 final text、thread id、
   token usage、issues 和有限 diagnostics；原始 rollout 事件不会进入 artifact。
   因此不能补推 `configure`、`intent` 或原始 message/tool span。

2. **SECONDARY：这批五题不是可发布的质量对照。** 其中两题是 timeout/partial，
   `weekly-market-cause` 明确不是成功样本；另外三题即使 terminal completed，
   也缺少 Workbench 的同题 trace，不能形成有效分母。

3. **T4 可交付项：确定性 normalizer 和证据边界已经落地。** Workbench 原生
   step 标记为 `native`；Codex/runtime-benchmark 映射标记为 `normalized`；
   未知事件标记为 `unmapped`。`compare_sequences()` 在一侧没有 mapped event
   时返回 `not_established`，不会制造假分叉。

## Conclusion and next gate

本轮没有证据支持“换 SDK”或“某 harness 能力更强”的结论。下一次公平审计必须
先冻结同一 PIT（point-in-time，时间截面）fixture、cutoff 和 task contract，
并让两侧同时保留原生控制面事件；至少拿到同题的 `configure → intent → route`
前缀后，`first_divergence_step` 才有行为含义。此前只应把本收据当作 trace
契约和数据缺口审计。
