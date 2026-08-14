# PRD: Span-Level IO Trace Bridge

> **状态**：Draft v2（经代码审阅修正），待审
> **作者**：Devin + 用户
> **日期**：2026-08-06
> **审阅目标**：确认 gap 定位准确、方案不重造轮子、接口契约可落地、scope 边界合理
>
> **v2 修订摘要**：v1 误将 `input_summary` / `output_summary` / `retrieval` / `tokens` 标为"不存在"；误用 PASS/FAIL/WARN 作为 status 值域；误将 `llm_call_ledger` 当作 trace.jsonl 顶层字段；误用 `normalize_harness_trace.py` 的校验型正则替代 `run_store.redact` 的采集型脱敏；§3.3 `tool_request` 映射与 G3 验收标准冲突。v2 逐条修正。

---

## 0. TL;DR（给审阅 agent 的 30 秒摘要）

本项目已有 D3 级 trace 体系（`trace.jsonl` + `append_step` 已内建脱敏 + `WorkflowStep` + `normalize_harness_trace.py`），且 `append_step` **已经提供** `input_summary` / `output_summary` / `retrieval` / `tokens` 字段。真正的 gap 不是"字段不存在"，而是：

1. **`input_summary` 有字段但无写入者**——唯一调用方 `_trace()` 只传 `output_summary`；
2. **IO 是扁平 `str`（`json.dumps(output)`），不是结构化 dict**——分诊时能读但不能按字段做 A/B 差分；
3. **`parent_span_id` 确实不存在**——无法重建因果传播链；
4. **`span_type` 不存在**——归一化靠 `step_id` + `name` 关键词匹配，没有显式类型。

**本 PRD 不是新建 trace 系统，也不是从零补 IO 字段，是在 `append_step` 已有能力上接线 + 结构化升级 + 补因果链。**

灵感来源：cc-haha 的 model trace 在运行时记录每轮模型请求的状态与耗时，是"轻量运行时版本"的可观测性。本 PRD 吸收其"边跑边录"的思路，但接入本项目已有的 `agent-run-triage` 分诊方法论。

---

## 1. 问题定义

### 1.1 现状：已有三层 trace 基础设施

| 层 | 已有资产 | 记录了什么 | 文件 |
|---|---|---|---|
| **工作流执行** | `WorkflowStep` / `WorkflowSummary` | subprocess 级 status / duration / stdout_tail / errors | `intelligence/runner.py`, `intelligence/summary.py` |
| **运行时控制面** | `trace.jsonl`（per run） | `step_id` / `name` / `status` / `started_at` / `finished_at` / `input_summary` / `output_summary` / `warnings` / `tokens?` / `retrieval?`（见 `append_step`） | `$FORESIGHT_USERS_DIR/<user>/runs/<run_id>/trace.jsonl` |
| **UI 推送协议** | `stream_events.json` | trace.step / skill.start / skill.result / report.* | `intelligence/api/stream_events.py` |
| **L1 归一化** | `normalize_harness_trace.py` | 映射到九步管道 configure→...→stop；**不搬运自由文本**（见 `normalize_records` docstring） | `intelligence/eval/normalize_harness_trace.py` |
| **事后分诊** | `agent-run-triage` skill | L0/L1/L2 + fix_type + A/B diff | `~/Documents/skill/skills/agent-run-triage/` |

当前 `trace_depth` 已达 **D3**（见 `docs/trace-profile.md` §3），可定位到 grounded phase 的入口余量、grant、耗时、状态和失败原因。

> **注意**：`llm_call_ledger` / `research_execution_budget` **不是 `trace.jsonl` 的顶层字段**。它们是某些 step 的 `name` / `step_id` 取值（如 `step_id="controller"`, `name="llm_call_ledger"`），在归一化产物里体现为 `"source_event_type": "llm_call_ledger"`。

### 1.2 缺口：IO 字段存在但未接线 + 缺因果链

`append_step()` 是 `trace.jsonl` 的**唯一写入者**（`run_store.py:258`），签名已包含：

```python
def append_step(self, run_id, *, step_id, name, status,
                input_summary="",          # ← 有字段
                output_summary="",         # ← 有字段
                started_at=None, finished_at=None,
                warnings=None, tokens=None,
                retrieval=None) -> dict    # ← retrieval 已是结构化 dict
```

但唯一调用方 `conversation_orchestrator._trace()` **只传了 `output_summary`**，`input_summary` 永远是默认空串：

```python
# conversation_orchestrator.py:3905-3912
step = self.run_store.append_step(
    run_id, step_id=step_id, name=name, status=status,
    output_summary=json.dumps(output, ensure_ascii=False),  # ← 有
    retrieval=retrieval,                                     # ← 有
    # input_summary 未传                                     # ← gap
)
```

真实 gap 逐条对照 `agent-run-triage` 的 `generic-jsonl.md` canonical fields：

| agent-run-triage 需要 | 现有 trace 提供 | 真实 gap |
|---|---|---|
| `span_id` | `step_id`（如 `retrieve`、`valuation-asof:1`） | ⚠️ 扁平阶段名，同 run 内可重复，**非唯一键**——需加 ordinal |
| `status` | `running` / `completed` / `failed` / `skipped` | ✅ 值域已明确（非 PASS/FAIL/WARN）；`running` 需映射 `unknown` |
| `timestamp` | `started_at` / `finished_at` | ✅ 有 |
| `name` / `span_type` | `name` 有；`span_type` 无 | 需补 `span_type` 枚举（可选——归一化靠 `step_id`+`name` 关键词匹配，不依赖 `span_type`） |
| `input` | `input_summary` 字段**存在**，但**无写入者**（永远空串） | **接线 + 结构化** |
| `output` | `output_summary` 字段**存在且有写入者**，但是 `json.dumps(str)` 扁平化 | **结构化升级**（str→dict） |
| `error` | `warnings: list[str]`；`status="failed"` | ⚠️ 有但不在 span 级结构化 error；可从 `status`+`warnings` 组合 |
| `parent_span_id` | ❌ 不存在 | **新增**（唯一真正从零补的字段） |
| `metadata`（model/tokens/latency） | `tokens` 有；`retrieval` dict 有部分指标；`llm_call_ledger` 是独立 step 的 output | 可在 span 级补 `metadata` dict |

**核心 gap 一句话**：`append_step` 已经有 IO 字段骨架和采集侧脱敏，但 input 侧没接线、output 侧是扁平 str 无法 A/B 差分，且缺 `parent_span_id` 因果链。工作量是"接线 + 结构化 + 补一个字段"，不是"新建通道 + 全套脱敏"。

### 1.3 症状

`agent-run-triage` skill 在以下场景输出 `INSUFFICIENT_TRACE`：

1. 金融 Agent 做完一个个股分析，结论偏差大，想定位是数据抓错、检索召回垃圾、还是模型幻觉——但 `output_summary` 是 `json.dumps` 字符串，`input_summary` 永远空，分诊者拿不到"第 2 步检索召回了什么"的结构化证据。
2. A/B 对照两次 run，想找第一次分叉——`normalize_harness_trace.py` 的 `compare_sequences()` 能对齐 step 顺序，但归一化产物是 frozen dataclass（不含 IO 原文），差分只能比 `step`+`source_event_type`，不能比同一步的 IO 差异。
3. `trace-profile.md` §2 已记录的字段陷阱（如 `turn.status=completed` 实际含确定性 fallback）说明：只有状态、没有内容时，即使经验丰富的分诊者也会误判。

---

## 2. 目标与非目标

### 2.1 目标

| # | 目标 | 验收标准 |
|---|---|---|
| G1 | 在 `append_step` 已有字段上：①给 `_trace()` 补 `input_summary` 写入；②将 `input`/`output` 从扁平 `str` 升级为结构化 dict；③新增 `parent_span_id`；④可选新增 `span_type` | 新 run 的 trace.jsonl 能被 `agent-run-triage` 的 `generic-jsonl.md` adapter 直接消费，不输出 `INSUFFICIENT_TRACE` |
| G2 | IO 内容按金融数据安全规则截断脱敏 | 复用 `run_store.redact()` / `redact_value()`（采集侧脱敏，已作用于 `input_summary`/`output_summary`/`warnings`）；单字段截断上限 configurable |
| G3 | 与 `normalize_harness_trace.py` 兼容 | 归一化产物仍带 `vocabulary: triage-l1-9`，`events` 正常映射，`unmapped` 不显著增加。**注意**：归一化器按 `step_id`+`name`+`event_type` 关键词映射（`_workbench_mapping`），不读 `span_type`——新增 `span_type` 字段对 normalizer 是透明的 |
| G4 | 不破坏现有 `trace-profile.md` 字段语义 | 新字段以 **additive** 方式加入，不改已有字段含义。**特别**：`trace-profile.md` §2 中"`unpaired_tool_requests` 对 workbench-trace 必须为 null"这一条，只有在 workbench-trace 不引入 tool request/response 词表时才成立——若引入 `span_type=tool_request/tool_return`，需同步更新该陷阱条目（见 §3.3 决策） |

### 2.2 非目标（scope 边界）

| # | 不做什么 | 为什么 |
|---|---|---|
| N1 | 不建 Web dashboard / GUI trace 查看器 | cc-haha 的桌面 GUI 不适用于本项目 Python + 飞书交付栈 |
| N2 | 不做实时 streaming trace 推送 | 现有 `stream_events.json` 已覆盖 UI 推送；本 PRD 只管事后分析的 JSONL 落盘 |
| N3 | 不做分布式 tracing（OpenTelemetry / Jaeger） | 本项目是单机 Agent，无跨服务 span 传播需求 |
| N4 | 不重写 `normalize_harness_trace.py` | 它已稳定且有 acceptance test 覆盖；只扩展输入兼容性 |
| N5 | 不做旧 run 回填 | `trace-profile.md` 已明确"不回填；只用新 run 或受控 replay" |
| N6 | 不改 `agent-run-triage` skill 本身 | skill 是 harness-agnostic 方法论，不应因某个项目的 trace 格式而改 |
| **N7** | **不改 `NormalizedEvent` schema** | `NormalizedEvent` 是 10 字段 frozen dataclass（`normalize_harness_trace.py:110-121`），没有 `attributes`/`metadata`/`input`/`output`。改它会违反 N4。IO 内容**不进归一化产物**，分诊必须读原始 `trace.jsonl` |
| **N8** | **不改 `STEP_STATUSES` 值域** | 当前值域为 `("running", "completed", "failed", "skipped")`（`run_store.py:62`）。新增 `span_type` 语义时不得顺手加 `PASS`/`WARN` 等值——那会触发 `append_step` 的 `ValueError` 并污染已有 status 语义 |

---

## 3. 技术方案

### 3.1 核心决策：扩展现有 `trace.jsonl` + `append_step`，不新建旁路文件

| 方案 | 优点 | 缺点 | 决定 |
|---|---|---|---|
| **A. 扩展 `append_step` + 接线 `_trace()`** | 零新增文件；`append_step` 已有 IO 字段骨架和内建脱敏；现有 pipeline 直接受益 | `output_summary` 从 `str` 升级为 `dict` 是 breaking change（需兼容读取） | ✅ **选这个** |
| B. 新建 `span_io.jsonl` 旁路 | 不碰现有 trace，风险隔离 | 两个文件要关联，维护成本翻倍；"哪个文件是权威"歧义 | ❌ |
| C. 扩展 `stream_events.json` 协议 | UI 能实时看到 IO | 事件协议变重，全量 IO 不适合 push | ❌ |

**选 A 的理由**：`append_step` 已经是唯一写入者且已内建 `redact()` / `redact_value()` 脱敏，`input_summary` / `output_summary` / `retrieval` / `tokens` 字段已经在签名里。这不是"扩展 schema"，几乎是"接线"。新增旁路文件会在这套已有能力之上重造一层。

> **`output_summary` 类型升级的兼容性处理**：从 `str` 改为 `dict | str`。读取侧（归一化器、分诊 adapter）已按 `str` 处理，需加一层 `isinstance(x, dict)` 判断：dict 直接用，str 走旧路径。`append_step` 落盘时统一 `json.dumps` 序列化。

### 3.2 字段设计：additive 扩展

在 `trace.jsonl` 现有事件结构上 **additive 新增**以下字段。不改已有字段名或语义。

```jsonc
// 现有事件示例（真实字段，简化）
{
  "step_id": "retrieve",                    // 扁平阶段名，非 run_id 前缀
  "name": "ask_retrieve_compose",
  "status": "completed",                    // 非 PASS/FAIL/WARN
  "started_at": "2026-08-06T14:30:22+08:00",
  "finished_at": "2026-08-06T14:30:25+08:00",
  "input_summary": "",                      // ← 有字段但当前永远空（gap）
  "output_summary": "{\"hit_count\": 3}",   // ← json.dumps 字符串（gap: 扁平化）
  "warnings": [],
  "tokens": 1200,                           // 可选
  "retrieval": { "hit_count": 3 },          // 可选，结构化 dict

  // ===== 新增字段（本 PRD 的核心） =====
  "span_type": "tool_return",               // 见 §3.3 枚举（可选）
  "parent_span_id": "route",                // 因果链（新增）
  "input": {                                // 结构化输入，已脱敏截断（替代/补充 input_summary）
    "query": "茅台2025Q1收入拆解",
    "source": "rag"
  },
  "output": {                               // 结构化输出，已脱敏截断（替代/补充 output_summary）
    "hit_count": 3,
    "top_score": 0.87,
    "snippets": ["...（截断）"]
  },
  "error": null,                            // 非 null 时为 {"type": "...", "message": "..."}
  "metadata": {                             // 扩展（tokens/retrieval 可合并到此）
    "model": "claude-sonnet-4-20250514",
    "latency_ms": 3200,
    "tokens_in": 1200,
    "tokens_out": 800
  }
}
```

> **`input_summary` / `output_summary` vs `input` / `output` 的关系**：v2 保留 `*_summary` 字段不动（向后兼容），新增 `input` / `output` 结构化字段。`append_step` 签名新增 `input: dict | None = None` 和 `output: dict | None = None` 参数；`_trace()` 优先写结构化字段，`*_summary` 保持旧值不删。

### 3.3 `span_type` 枚举与 G3/G4 冲突的解决

对齐 `agent-run-triage` 的 `generic-jsonl.md` canonical `span_type`，但映射到本项目实际事件类型：

| span_type | 对应本项目场景 | `_workbench_mapping` 实际命中的 L1 |
|---|---|---|
| `user` | 用户请求 / 飞书消息入站 | `intent`（`"controller"` 或 `"intent"` 关键词） |
| `system` | system/developer prompt 装配 | `configure`（`"configure"` 或 `"assembly"` 关键词） |
| `agent` | 主 Agent 决策点 | `plan` / `route` |
| `llm` | LLM 调用（含 brief/composer/judge） | `synthesize`（`"synth"`/`"compose"`/`"grounded"`/`"shadow"` 关键词） |
| `tool_request` | 工具调用发起（DuckDB query / RAG / 抓数） | ⚠️ **`_workbench_mapping` 无 `tool` 分支** → 会落到 `retrieve`（含 `"retrieve"` 关键词）或 `unmapped` |
| `tool_return` | 工具返回结果 | `observe`（`"observe"`/`"validate"`/`"budget"`/`"ledger"` 关键词） |
| `error` | 异常 / 超时 / 失败 | `stop`（`"stop"`/`"complete"`/`"finish"`/`"error"` 关键词） |
| `state` | 状态变化 / 预算更新 | 不映射（控制面） |

> **⚠️ G3 冲突说明**：`_workbench_mapping`（`normalize_harness_trace.py:252-276`）的关键词分支里**没有 `tool`**——它只有 `configure`/`plan`/`controller(intent)`/`route`/`observe`/`retrieve`/`synthesize`/`stop`。`span_type=tool_request` 会被归一化器**忽略**（它不读 `span_type`），映射结果取决于 `step_id`+`name` 的关键词：如果 step_id 是 `retrieve` 则落到 `retrieve`，否则可能 `unmapped`。
>
> **决策**：本 PRD **不要求** `span_type=tool_request` 必须映射到 L1 `tool`。`span_type` 是给 `agent-run-triage` adapter 的标注层，归一化器继续按现有关键词逻辑跑。如果后续想让工具调用独立映射到 L1 `tool`，那是改 `_workbench_mapping`（违反 N4），应作为后续独立提案。
>
> **⚠️ G4 冲突说明**：`normalize_harness_trace.py:488` 对 `workbench-trace` 硬编码 `_count_unpaired_tool_requests` 返回 `None`。`trace-profile.md` §2 将此解释为"workbench-trace 没有逐工具词表"。如果本 PRD 引入 `span_type=tool_request/tool_return`，那条陷阱条目的理由需要更新——但函数仍返回 `None`（因为 N4 不改 normalizer），所以**实际行为不变**，只是文档措辞要从"没有词表"改为"有词表但 normalizer 暂不计算配对"。

### 3.4 IO 截断与脱敏规则

| 规则 | 参数 | 默认值 |
|---|---|---|
| 单字段截断 | `TRACE_IO_MAX_CHARS` | 2000 字符 |
| 嵌套深度 | `TRACE_IO_MAX_DEPTH` | 3 层 |
| 列表截断 | `TRACE_IO_MAX_LIST_ITEMS` | 10 项 |
| **脱敏组件** | **复用 `run_store.redact()` / `redact_value()`**（采集侧脱敏，已作用于 `input_summary`/`output_summary`/`warnings`） | — |
| DuckDB 结果截断 | schema + 前 5 行 + 行数 + **数值列 min/max/sum 摘要** | — |

> **设计理由——为什么不用 `normalize_harness_trace.py` 的正则**：
>
> `normalize_harness_trace.py` 的 `_SAFE_TOKEN` / `_SECRET` / `_ABSOLUTE_PATH` 是**校验器不是脱敏器**。`_SAFE_TOKEN` 是白名单 fullmatch，`_string_token()` 用法是不合规就整体退回 `"unknown"`——拿它处理自由文本会把整段 IO 变成 `"unknown"`。`_SECRET` 只匹配 `key: value` 形状，裸密钥串它不管。
>
> 更关键的是分层：`normalize_harness_trace.py` 在 `intelligence/eval/`（评测层），`run_store.py` 在 `intelligence/services/`（生产服务层）。生产服务不应反向依赖评测工具。
>
> **可复用知识点（面试常问）**：读侧 sanitizer 和写侧 sanitizer 不能互换。`normalize_harness_trace.py` 的正则是**产物校验**用的（白名单式，不合规就降级为 unknown，宁缺毋滥）；`run_store.redact` 是**采集脱敏**用的（保内容、去敏感片段）。同一个词"脱敏"在两侧的目标函数相反：一侧优化"绝不泄露结构化身份"，另一侧优化"保留足够证据"。微服务日志治理、PII scrubber 分层里同样的坑反复出现。
>
> **DuckDB 聚合摘要的理由**：只存前 5 行会漏掉聚合类错误（如 120 日资金流求和口径错，前 5 行全对而总计错）。对数值列额外存 min/max/sum，比多存几行更省空间也更能定位数值传导错误。

### 3.5 插桩方式：扩展 `append_step` + context manager

`append_step` 已是唯一写入者。推荐两种使用方式：

```python
# 方式 1：直接调用 append_step（最简，推荐 Phase 1）
self.run_store.append_step(
    run_id, step_id="retrieve", name="ask_retrieve_compose",
    status="completed",
    input={"query": query, "source": "rag"},       # 新参数
    output={"hit_count": len(results), "top_score": results[0].score},
    parent_span_id="route",                          # 新参数
    retrieval=telemetry,
)

# 方式 2：context manager（适合需要自动计时和异常捕获的工具调用）
from intelligence.tracing import span

with span(self.run_store, run_id, "rag_search", span_type="tool_request",
          parent=current_span_id) as s:
    results = rag.search(query)
    s.set_output({"hit_count": len(results)})
```

方式 1 改动最小（给 `_trace()` 补 `input` 参数即可），方式 2 适合后续大规模插桩。

---

## 4. 实现计划

### 4.1 文件变更清单

| 文件 | 变更类型 | 说明 |
|---|---|---|
| `intelligence/services/run_store.py` | **修改** | `append_step` 新增 `input` / `output` / `parent_span_id` / `span_type` / `error` 参数；落盘时脱敏走已有 `redact_value()` |
| `intelligence/services/conversation_orchestrator.py` | **修改** | `_trace()` 补传 `input`（从调用上下文提取） |
| `intelligence/tracing/__init__.py` | 新建（可选，Phase 2+） | 导出 `span` context manager |
| `intelligence/tracing/spanctx.py` | 新建（可选，Phase 2+） | ~40 行：context manager，封装 `append_step` + 自动计时 |
| `docs/trace-profile.md` | 修改 | §1 新增字段说明；§3 盲区表更新；§2 `unpaired_tool_requests` 条目措辞更新 |

> **与 v1 的区别**：v1 计划新建 `emitter.py` + `sanitizer.py`，但 `append_step` 已经是 emitter 且 `redact_value()` 已经是 sanitizer。v2 只在需要 context manager 语法糖时才新建 `tracing/` 模块。

### 4.2 插桩优先级（哪些步骤先加）

按 `agent-run-triage` 的 L1 管道和 `generic-jsonl.md` 的证据权重：

| 优先级 | L1 阶段 | 对应代码 | 为什么优先 |
|---|---|---|---|
| **P0a** | `retrieve` | `_trace()` retrieve step | 检索召回质量是金融分析最常见失败源；`retrieval` dict 已在写，只需补 `input` |
| **P0a** | `configure` | system prompt / skill 装配 | `generic-jsonl.md` 第 5 条："装配层事件体积小但常含 PRIMARY"；插桩成本最低（纯输入侧） |
| P0b | `tool`（observe） | DuckDB query、数据抓取 | 数据源错误会传播到全链；`output_summary` 已有，需结构化 |
| P1 | `synthesize` | LLM 分析调用（brief/composer/judge） | 模型幻觉 / 推理断裂 |

> **与 v1 的区别**：`configure` 从 P1 提到 P0a——它成本最低（prompt 装配是纯输入侧）、`generic-jsonl.md` 明确说装配层常含 PRIMARY。P0 拆成 P0a（给 `_trace()` 补 input，约十行）和 P0b（结构化 IO），P0a 一天内能出可验证成果。

### 4.3 分阶段交付

| 阶段 | 交付物 | 验收 |
|---|---|---|
| Phase 1 | `append_step` 签名扩展 + `_trace()` 补 `input` + 单元测试 | 新 run 的 trace.jsonl 含结构化 `input`/`output`；`redact_value()` test pass |
| Phase 2 | P0a 插桩（retrieve + configure） | 一次真实 RAG run 产出的 trace.jsonl 能被 `agent-run-triage` 消费且不输出 `INSUFFICIENT_TRACE` |
| Phase 3 | P0b + P1 插桩（tool observe + synthesize） | `normalize_harness_trace.py` 产物 `unmapped` 不显著增加 |
| Phase 4 | `trace-profile.md` 更新 + 回归测试 | 现有字段陷阱表条目仍成立（`unpaired_tool_requests` 条目措辞更新） |

---

## 5. 接口契约（给审阅 agent 的重点）

### 5.1 trace.jsonl 事件 schema（扩展后）

```jsonc
{
  // ===== 现有字段（不改） =====
  "step_id": "retrieve",                   // 扁平阶段名
  "name": "ask_retrieve_compose",
  "status": "completed",                   // running/completed/failed/skipped
  "started_at": "2026-08-06T14:30:22+08:00",
  "finished_at": "2026-08-06T14:30:25+08:00",
  "input_summary": "",                     // 保留旧字段（向后兼容）
  "output_summary": "{\"hit_count\": 3}",  // 保留旧字段
  "warnings": [],
  "tokens": 1200,                          // 可选
  "retrieval": { "hit_count": 3 },         // 可选

  // ===== 新增字段 =====
  "span_type": "tool_return",              // 可选，见 §3.3
  "parent_span_id": "route",               // 新增，因果链
  "input": { /* 脱敏截断后的结构化输入 */ } | null,
  "output": { /* 脱敏截断后的结构化输出 */ } | null,
  "error": { "type": "string", "message": "string" } | null,
  "metadata": {
    "model": "string | null",
    "latency_ms": "int | null",
    "tokens_in": "int | null",
    "tokens_out": "int | null"
  }
}
```

> **注意**：`llm_call_ledger` / `research_execution_budget` **不在事件顶层**。它们是独立 step 的 `name` 值，不是同一事件的字段。

### 5.2 与 `agent-run-triage` generic-jsonl.md 的映射

| generic-jsonl canonical field | 本 PRD trace.jsonl 字段 | 备注 |
|---|---|---|
| `run_id` | **从目录路径提取**（`runs/<run_id>/trace.jsonl`） | step_id 无 run_id 前缀 |
| `span_id` | `step_id` + **ordinal 组合**（`<run_id>/<step_id>.<n>`） | step_id 扁平可重复，需加 ordinal 保证唯一 |
| `parent_span_id` | `parent_span_id` | 新增 |
| `sequence` | 按 `started_at` timestamp 排序，或文件行号 ordinal | step_id 无序号后缀 |
| `timestamp` | `started_at` / `finished_at` | 直接复用 |
| `span_type` | `span_type` | 新增（可选），归一化器不读此字段 |
| `name` | `name` | 直接复用 |
| `input` | `input`（结构化 dict） | 新增；`input_summary`（str）为旧兼容 |
| `output` | `output`（结构化 dict） | 新增；`output_summary`（str）为旧兼容 |
| `error` | `error` | 新增（可从 `status="failed"` + `warnings` 组合） |
| `status` | `status` | `completed→success`, `failed→error`, `skipped→unknown`, **`running→unknown`**（非终态，不可当成功） |
| `metadata` | `metadata`（可选） | 新增；`tokens`/`retrieval` 可合并到此 |

> **与 v1 的区别**：
> - `run_id` 从"step_id 前缀提取"改为"目录路径提取"——step_id 无 run_id 前缀；
> - `span_id` 从"直接复用 step_id"改为"step_id + ordinal 组合"——step_id 扁平可重复；
> - `status` 映射从 `PASS/FAIL/WARN` 改为真实值域 `running/completed/failed/skipped`，并补 `running→unknown`。

### 5.3 与 `normalize_harness_trace.py` 的兼容性

- ✅ `normalize_harness_trace.py` 已有 `kind = "workbench-trace"` 处理路径（`_workbench_mapping`）
- ✅ 新增字段不影响映射逻辑：normalizer 按 `step_id`+`name`+`event_type` 关键词映射（`_workbench_mapping`），**不依赖 `input`/`output`/`span_type`**
- ⚠️ **IO 内容不进归一化产物**：`NormalizedEvent` 是 10 字段 frozen dataclass（无 `input`/`output`/`metadata`/`attributes`），且 `normalize_records()` docstring 明确"without reading or copying free-form text"。分诊必须读原始 `trace.jsonl`，不能只靠 normalized artifact
- ❌ ~~`metadata` 可被 normalizer 透传到 `attributes`~~ — `NormalizedEvent` 没有 `attributes` 字段，透传需改 dataclass（违反 N4/N7）

---

## 6. 风险与缓解

| 风险 | 影响 | 缓解 |
|---|---|---|
| IO 内容膨胀导致 trace.jsonl 过大 | 磁盘 / 分诊读取慢 | 截断上限 + DuckDB 只存 schema+5 行+聚合摘要；大 trace 走 `generic-jsonl.md` 的 failure window 策略 |
| 脱敏遗漏导致 secret 泄露 | 安全风险 | 复用 `run_store.redact()` / `redact_value()`（已验证的采集侧脱敏）；Phase 1 加脱敏单元测试 |
| `output_summary` 从 str 升级为 dict 的 breaking change | 旧读取侧崩溃 | `append_step` 落盘时统一 `json.dumps`；读取侧加 `isinstance(x, dict)` 判断 |
| 插桩侵入业务代码 | 维护负担 | Phase 1 只改 `_trace()` 签名（约十行）；context manager 为可选 Phase 2+ |
| 现有 `normalize_harness_trace.py` 假设被破坏 | 归一化失败 | Phase 3 验收包含 `unmapped` 不显著增加的回归断言 |
| `span_type=tool_request/tool_return` 与 `trace-profile.md` §2 `unpaired_tool_requests` 条目措辞冲突 | 文档不一致 | Phase 4 同步更新该条目措辞（行为不变，函数仍返回 None） |

---

## 7. 面试关联（教学备注）

> 这块如果面试被问到，可以这样讲：
>
> "Agent 系统的可观测性分三层：**运行时采集**（record every span's IO/status/latency）、**归一化映射**（project heterogeneous events to a fixed pipeline vocabulary）、**事后分诊**（locate the first error transformation with causal evidence）。大部分团队只做了第一层的状态记录——像 OpenTelemetry 那样打日志——但缺 IO 内容和因果归因方法。我们做的是全三层：运行时采集带 IO 内容的 span、用 L1 九步管道归一化、用固定方法论做因果分诊。"
>
> 可迁移知识点：这套 producer（trace emitter）→ normalizer（L1 mapping）→ consumer（triage）的分层模式，在微服务可观测性、ML pipeline 监控、数据质量治理场景都能用。另外，"读侧 sanitizer vs 写侧 sanitizer 不能互换"这个坑，在 PII scrubber 分层、日志脱敏管线里反复出现。

---

## 8. 审阅清单（给审阅 agent）

> v2 已根据首轮审阅修正，以下为修订后状态。

1. **Gap 定位**：~~§1.2 的 gap 分析是否准确？~~ → ✅ **已修正**。v1 误标 `input_summary`/`output_summary` 为"不存在"；v2 确认字段存在但 `input_summary` 无写入者、`output_summary` 是扁平 str，真实 gap 是"接线 + 结构化 + 补 parent_span_id"。
2. **不重造轮子**：~~§3.1 选择扩展现有 trace.jsonl 而非新建文件，是否正确？~~ → ✅ **确认正确**，且理由比 v1 更强——`append_step` 已有 IO 字段骨架和内建脱敏。
3. **接口契约**：~~§5 的 schema 设计能否被 `agent-run-triage` 的 `generic-jsonl.md` 直接消费？~~ → ✅ **已修正**。v1 的 `step_id` 格式假设（`run_20260806_001.retrieve.3`）和 `status` 值域（PASS/FAIL/WARN）均与真实代码不符；v2 改为真实值域。
4. **兼容性**：~~§5.3 与 `normalize_harness_trace.py` 的兼容性判断是否成立？~~ → ✅ **已修正**。v1 第三条"metadata 可透传到 attributes"不成立（`NormalizedEvent` 无此字段）；v2 明确 IO 不进归一化产物。
5. **Scope 边界**：~~§2.2 的非目标是否合理？~~ → ✅ **已补充 N7（不改 NormalizedEvent）/ N8（不改 STEP_STATUSES）**。
6. **插桩优先级**：~~§4.2 的 P0/P1 排序是否符合实际失败频率？~~ → ✅ **已调整**。`configure` 提到 P0a；P0 拆为 P0a（接线）/ P0b（结构化）。
7. **截断策略**：~~§3.4 的截断上限是否合理？DuckDB 只存 schema+5 行会不会丢关键信息？~~ → ✅ **已修正**。脱敏组件从 `normalize_harness_trace.py` 正则改为 `run_store.redact()`；DuckDB 补数值列 min/max/sum 聚合摘要。
